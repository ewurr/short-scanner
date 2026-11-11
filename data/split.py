"""Veri bolmesi ve donem korumasi (on-kayit §3, CLAUDE.md §3.2-3.3).

Bolme kurali (on-kayit §3): `SHA256("short-lab-v1:" + ANAHTAR)` hesaplanir;
onaltilik ozetin tamsayi degeri cift ise A, tek ise B grubudur.

Anahtar, on-kayit revizyonu uyarinca sembol degil **varlik anahtaridir**: bir
yeniden adlandirma zincirindeki en eski sembol. Tek sembollu varliklarda anahtar
sembolun kendisidir. Bu sayede MATICUSDT ve POLUSDT gibi ayni varligin iki adi
her zaman ayni gruba duser ve bolme sizintisi olusmaz.

Donem korumasi:
  - KESIF  : yalnizca A grubu, 2020-01-01 -> 2025-08-31
  - C1     : yalnizca B grubu, 2020-01-01 -> 2025-08-31  (onay, tek atis)
  - C2     : A + B,            2025-09-01 -> 2026-08-31  (onay, tek atis)

Onay kumeleri (F1 kapanis bulgusu 8):
  - C1 ve C2 yalnizca bir **onay kosusu** icinde acilir:
        with split.onay_kosusu("H2", "C1") as kosu:
            mumlari_yukle(sembol, bar, "C1", onay=True)
            kosu.sonuc_bildir(...)
  - Kosu yalnizca temiz calisma agacinda, git'te izlenen bir depo betiginden
    acilir (onay kaydi ve kosu butunlugu turu, denetci KS3 D-B2).
  - Kayda KOSU BASINA IKI SATIR yazilir (KS3 D-B3): acilirken BASLADI (tarih,
    kume, cagiran betik, commit hash'i, hipotez, kosu kimligi), kapanirken
    BITTI (sonucla) ya da HATA. Sembol basina satir yazilmaz.
  - Ayni (hipotez, kume) cifti kayitta zaten varsa kosu reddedilir: tek atis.
  - Kayit yolu parametre almaz, kosu durumu modul disindan atanamaz (KS3 D-B1);
    ayrinti "Onay kaydi" bolumunde.
  - `onay` yalnizca gercek `True` ile kapiyi acar; `"False"` gibi dogruluk
    degeri tasiyan baska her sey reddedilir.

Bolme tablosu (F1 kapanis bulgusu 9): `split_oku` tabloyu okurken her satiri
bolme kuralina gore yeniden hesaplar; yukleyicilere disaridan tablo verme yolu
yoktur.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import math
import re
import subprocess
import sys
import time
import types
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import pandas as pd

import config
from data import klines, kume_bellegi, pencere
from data.pencere import KumeSiniriHatasi  # noqa: F401  (disari acik ad)


class OnayGerekli(PermissionError):
    """Onay kumesine gecerli bir onay kosusu olmadan erisim denendi (CLAUDE.md §3.3)."""


class OnayUyusmazligi(OnayGerekli):
    """Acik onay kosusunun (hipotez, kume) cifti, karar noktasina gelen pozisyonunkiyle uyusmuyor
    (kapi sertlestirme turu 3, denetci KS2 D-B1; onay kumeleri her hipotez icin BIR KEZ kosulur).
    Ornek: `onay_kosusu("H2", "C1")` icinde H1 pozisyonu ya da acik bir onay kosusu icinde KESIF pozisyonu."""


class OnayTekrari(PermissionError):
    """Ayni hipotez icin ayni onay kumesi ikinci kez kosulmak istendi (tek atis)."""


class BolmeTutarsizligi(ValueError):
    """Bolme tablosu on-kayit §3 kuraliyla uyusmuyor (CLAUDE.md §3.2)."""


# --- Bolme -------------------------------------------------------------------

BOLME_SUTUNLARI = ["sembol", "varlik_anahtari", "grup"]


def grup(anahtar: str) -> str:
    """Varlik anahtarindan A/B grubunu hesaplar (on-kayit §3). Saf fonksiyon."""
    ozet = hashlib.sha256((config.BOLME_TUZU + anahtar).encode("utf-8")).hexdigest()
    return "A" if int(ozet, 16) % 2 == 0 else "B"


def varlik_anahtari(sembol: str, zincirler: Mapping[str, str] | None = None) -> str:
    """Sembolun varlik anahtari: yeniden adlandirma zincirindeki en eski sembol.

    `zincirler` sozlugu {yeni_sembol: eski_sembol} eslemesidir; zincir birden
    fazla adimsa kok bulunana kadar izlenir. Verilmezse on-kayit §3 rev.2'deki
    dokuz kabul edilmis zincir kullanilir.
    """
    if zincirler is None:
        zincirler = config.YENIDEN_ADLANDIRMA
    if not zincirler:
        return sembol
    gorulen = {sembol}
    su_an = sembol
    while su_an in zincirler:
        su_an = zincirler[su_an]
        if su_an in gorulen:  # dongu korumasi
            break
        gorulen.add(su_an)
    return su_an


def split_uret(semboller: list[str], zincirler: Mapping[str, str] | None = None) -> pd.DataFrame:
    """Bolme tablosunu uretir: sembol, varlik_anahtari, grup.

    Cikti sembol adina gore siralidir ve deterministiktir. Saf fonksiyon.
    `zincirler` verilmezse on-kayit §3 rev.2'deki dokuz zincir kullanilir.
    """
    satirlar = []
    for sembol in sorted(set(semboller)):
        anahtar = varlik_anahtari(sembol, zincirler)
        satirlar.append({"sembol": sembol, "varlik_anahtari": anahtar, "grup": grup(anahtar)})
    return pd.DataFrame(satirlar, columns=BOLME_SUTUNLARI)


def split_dogrula(tablo: pd.DataFrame) -> pd.DataFrame:
    """Bolme tablosunu on-kayit §3 kuralina gore dogrular; uyusmazlikta hata.

    Grubu TURETMEK icin degil DOGRULAMAK icindir: commit edilmis tablo tek
    kaynaktir, ama betikle degistirilmis ya da elle duzeltilmis bir tablo
    (hook yalnizca arac cagrilarini kilitler) burada yakalanir. Denetlenenler:
      - sutunlar tam olarak sembol, varlik_anahtari, grup,
      - bos hucre yok, tekrarlanan sembol yok,
      - grup yalnizca A ya da B,
      - varlik anahtari kabul edilmis zincirlerle yeniden hesaplanan anahtara esit,
      - grup, varlik anahtarinin SHA256 kuraliyla yeniden hesaplanan grubuna esit.
    """
    if list(tablo.columns) != BOLME_SUTUNLARI:
        raise BolmeTutarsizligi(f"Bolme tablosu sutunlari {BOLME_SUTUNLARI} olmali: {list(tablo.columns)}")
    if tablo.isna().any().any() or (tablo.astype(str).apply(lambda s: s.str.strip()) == "").any().any():
        raise BolmeTutarsizligi("Bolme tablosunda bos hucre var.")
    tekrar = tablo["sembol"][tablo["sembol"].duplicated()]
    if not tekrar.empty:
        raise BolmeTutarsizligi(f"Bolme tablosunda tekrarlanan sembol: {sorted(set(tekrar))[:5]}")
    gecersiz = tablo.loc[~tablo["grup"].isin(["A", "B"]), "grup"]
    if not gecersiz.empty:
        raise BolmeTutarsizligi(f"A/B disi grup degeri: {sorted(set(gecersiz))[:5]}")

    hatali = []
    for sembol, anahtar, grp in tablo[BOLME_SUTUNLARI].itertuples(index=False):
        beklenen_anahtar = varlik_anahtari(sembol)
        if anahtar != beklenen_anahtar or grp != grup(beklenen_anahtar):
            hatali.append(sembol)
    if hatali:
        raise BolmeTutarsizligi(
            f"{len(hatali)} satir bolme kuraliyla uyusmuyor (ornek: {hatali[:5]}). "
            "Veri bolmesi dokunulmazdir (CLAUDE.md §3.2)."
        )
    return tablo


def split_yaz(cerceve: pd.DataFrame, yol: Path | None = None) -> Path:
    """split.csv'yi yazar. Dosya varsa uzerine yazmaz (CLAUDE.md §3.2)."""
    hedef = config.SPLIT_CSV if yol is None else yol
    if hedef.exists():
        raise FileExistsError(
            f"{hedef} zaten var. Veri bolmesi dokunulmazdir (CLAUDE.md §3.2)."
        )
    split_dogrula(cerceve)
    hedef.parent.mkdir(parents=True, exist_ok=True)
    cerceve.to_csv(hedef, index=False, lineterminator="\n")
    return hedef


def split_oku(yol: Path | None = None) -> pd.DataFrame:
    """Commit edilmis bolme tablosunu okur ve `split_dogrula`dan gecirir."""
    hedef = config.SPLIT_CSV if yol is None else yol
    if not hedef.exists():
        raise FileNotFoundError(f"{hedef} yok. Once split.csv uretilip commit edilmeli.")
    return split_dogrula(pd.read_csv(hedef, dtype=str, keep_default_na=False))


# --- Donem korumasi ----------------------------------------------------------


def kume_tanimi(kume: str) -> tuple[tuple[str, ...], dt.datetime, dt.datetime]:
    """Bir kumenin (gruplar, baslangic, bitis) tanimini doner (on-kayit §3)."""
    if kume == "KESIF":
        return ("A",), config.KESIF_BASI, config.KESIF_SONU
    if kume == "C1":
        return ("B",), config.KESIF_BASI, config.KESIF_SONU
    if kume == "C2":
        return ("A", "B"), config.C2_BASI, config.C2_SONU
    raise ValueError(f"Bilinmeyen kume: {kume!r}. Gecerli degerler: {config.KUMELER}")


def kume_araligi(kume: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Kumenin kapali tarih araligi [bas, son] (UTC).

    Tek kaynak `kume_tanimi`dir; kume sinirlari baska bir yerde elle yazilmaz.
    """
    _, bas, son = kume_tanimi(kume)
    return pd.Timestamp(bas), pd.Timestamp(son)


# --- Onay kaydi --------------------------------------------------------------
#
# Onay kaydi ve kosu butunlugu turu (denetci KS3 D-B1, D-B2, D-B3). Koruma olcutu: ayni surec icinden mutlak
# koruma mumkun degil; amac, onay kaydini atlatmanin kazayla olmamasi ve gecmiste iz birakmayan bir yolla
# yapilamamasidir.
#   - Kayit yolu tek kaynaktan gelir: `config.ONAY_KAYDI` (config'te yeniden atanamaz). Bu modul degeri yukleme
#     aninda sabitler ve her kullanimda config'le karsilastirir. Hicbir onay fonksiyonu yol parametresi almaz.
#   - Kosu durumu (`_AKTIF_KOSU`) ve kosu yolundaki adlar modul disindan atanamaz (`_KorunanModul`); durum
#     yalnizca `onay_kosusu` baglam yoneticisiyle degisir.
#   - Onay kumesine her erisimde acik kosu kayit dosyasinda dogrulanir: kosunun tek bir BASLADI satiri var,
#     bitis satiri yok. Bellekte kurulan bir kosu, gercek kayda satir yazilmadan erisim acamaz.
#   - Kosu yalnizca temiz calisma agacinda ve git'te izlenen bir depo betiginden acilir; kosunun kodu kayda
#     yazilan commit'tedir.
#   - Kosu basina iki satir: acilirken BASLADI, kapanirken BITTI (sonucla) ya da HATA. Surec oldurulurse
#     BASLADI satiri kalir; o (hipotez, kume) cifti yine harcanmis sayilir.
#   - Kayit git'e baglidir (onay kaydi ikinci tur, denetci OK D-B1). Her kayit satiri yazildigi anda kosunun
#     kendisi tarafindan commit edilir (yalnizca kayit dosyasi). Tek atis denetimi calisma agacina ek olarak git
#     gecmisine bakar: bir kez commit edilmis her satir, sonradan silinse bile, cifti harcar (`--all --reflog`).
#     Calisma agacindaki kayit HEAD'dekiyle ayni degilse yeni kosu acilmaz. Boylece `git checkout .`,
#     `git stash`, `reset --hard` tek atisi geri getirmez.
#   - Kayit uzak depoya baglidir (onay kaydi kapanis turu). Kosu acilmadan once `origin/main` alinir (ag yoksa
#     kosu acilmaz, yerel kipe dusulmez); HEAD'deki kayitta `origin/main`'e itilmemis satir varsa ya da HEAD
#     `origin/main`'i icermiyorsa kosu acilmaz. BASLADI ve bitis satirlari commit edildikleri anda
#     `origin/main`'e itilir; itilemezse kayda `durum=ITILEMEDI` satiri yazilir (yerelde commit edilir) ve hata
#     verilir. Tek atis denetimi `origin/main` gecmisine de bakar. Yerel gecmis sahibince yeniden yazilabilir;
#     uzak depodaki commit yazilamaz. Kalan yollar (ayri worktree, yeniden klonlama, bagimsiz HEAD, birlestirmede
#     tek tarafa cozum, gecmisi yeniden yazip zorla itme, duz atamayla modul degistirme) kasitli ve cok adimlidir;
#     itme sayesinde her biri uzak depoda iz birakir (RESULTS §14.26).
#   - Sinir (koruma olcutu): ayni surec icinden mutlak koruma mumkun degildir; amac kazayla atlatmayi imkansiz,
#     kasitli atlatmayi gorunur kilmaktir. `split`'in modul bagimliliklari (`config`, `subprocess`, `klines`,
#     `split_dogrula`, ...) bu yuzden korunmaz; koruma listesi sonsuza kadar uzayamaz.


class OnayKorumasi(OnayGerekli):
    """Onay kosusu durumu ya da kosu yolundaki bir ad modul disindan degistirilmek istendi, kayit yolu
    tek kaynaktan gelmiyor ya da kayit dosyasi acik kosuyla uyusmuyor (denetci KS3 D-B1)."""


class OnayOrtamiHatasi(OnayGerekli):
    """Onay kosusu temiz olmayan bir ortamda acilmak istendi: git yok, calisma agaci kirli ya da cagiran betik
    git'te izlenen bir depo dosyasi degil (denetci KS3 D-B2)."""


class OnayKaydiCommitsiz(OnayOrtamiHatasi):
    """Onay kaydinin calisma agacindaki satirlari HEAD'deki kayitla ayni degil ya da kosunun kayit satiri commit
    edilemedi (onay kaydi ikinci tur, denetci OK D-B1). Commit edilmemis kayit satiri varken yeni kosu acilmaz."""


class OnayUzakHatasi(OnayOrtamiHatasi):
    """Onay kaydi uzak depoya (`origin/main`) baglanamadi (onay kaydi kapanis turu): `origin/main` alinamadi (ag
    yok), HEAD'deki kayitta itilmemis satir var, HEAD `origin/main`'i icermiyor ya da kosunun kayit commit'i
    itilemedi. Kosu yerel kipe dusmez."""


class OnaySonucuYok(RuntimeError):
    """Onay kosusu blogu sonuc bildirilmeden bitti (denetci KS3 D-B3). Kayda HATA satiri yazilir."""


ONAY_TABLO_BASLIGI = "| Tarih (UTC) |"
KOSU_DURUMLARI = ("BASLADI", "BITTI", "HATA", "ITILEMEDI")
_SONUC_AZAMI_UZUNLUK = 200

# Uzak depo ve dal (onay kaydi kapanis turu). ON-KAYIT DEGILDIR.
UZAK_DEPO = "origin"
UZAK_DAL = "main"
_UZAK_REF = f"refs/remotes/{UZAK_DEPO}/{UZAK_DAL}"
_AG_SURESI = 120  # sn; fetch ve push

# Tek kaynak: config.ONAY_KAYDI (yukleme anindaki deger).
_KAYIT_YOLU: Path = Path(config.ONAY_KAYDI)


def _git(*argumanlar: str, sure: int = 30) -> str | None:
    # Onay kaydinin git cagrilari (performans 2b-0; sizinti S-23, P-7): bag ve kesif kaydiyla AYNI beyaz listeli ortam
    # (`_bag_ortami`). Replace referanslari ortamdaki GIT_NO_REPLACE_OBJECTS=1 ile yok sayilir (komut satiri ayni kalir).
    # GIT_TERMINAL_PROMPT=0: kimlik bilgisi istenirse beklemek yerine hata (ag islemleri).
    try:
        cikti = subprocess.run(
            ["git", *argumanlar], cwd=_depo(), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=sure, env=_bag_ortami(),
        )
    except Exception:
        return None
    if cikti.returncode != 0:
        return None
    return cikti.stdout


def _tablo_zamani() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _iso_zaman() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- Kosu ortami (KS3 D-B2) --------------------------------------------------


class KilitYok(OnayOrtamiHatasi):
    """Hipotezin `analysis/<hipotez>/KILIT.md` kaydi yok ya da commit edilmemis (on-kayit §8 madde 5,
    rev.13): "Secim, onay kosusundan once `analysis/<hipotez>/KILIT.md` dosyasiyla commit edilir.
    Onay kosusu, kostugu hipotezin yapilandirmasini bu dosyadan okur; dosyada kaydi olmayan ... bir
    hipotez icin onay kosusu acilmaz." """


class KilitBozuk(OnayOrtamiHatasi):
    """KILIT.md okunabildi ama on-kayit §8 madde 5'teki alanlari tasimiyor, ya da bir alan birden
    fazla kez yazilmis (ekleme kurali: "bir hipotezin kaydi yazildiktan sonra degistirilmez")."""


class HipotezKapandi(OnayOrtamiHatasi):
    """KILIT.md'nin hukmu "hipotez kapandi" (on-kayit §8 madde 4): secilecek yapilandirma yoktur ve
    onay verisi harcanmaz; koşu acilmaz."""


# --- F2'nin kilitledigi yapilandirma (on-kayit §8 madde 5, rev.13) ----------------------------
#
# Dosya `analysis/<hipotez>/KILIT.md`dir ve olusturuldugu andan itibaren kilitli dosyalar arasina
# girer (CLAUDE.md "Koruma katmani"; `.claude/hooks/kilitli_dosya_korumasi.py`). Alanlari on-kayit
# §8 madde 5'te sayilidir ve yetkili metin odur; burada yalnizca OKUNUR, yazilmaz.
KILIT_ADI = "KILIT.md"
KILIT_SECILDI = "yapilandirma secildi"
KILIT_KAPANDI = "hipotez kapandi"
KILIT_HUKUMLERI = (KILIT_SECILDI, KILIT_KAPANDI)

# On-kayit §8 madde 5: "Dosya su alanlari tasir: hipotez; hukum ... ve kapandiysa gerekcesi;
# secildiyse yapilandirmanin kimligi ve butun parametre degerleri; analize giren ve olusmus olay
# sayilari; K2 farki; kesif kosusunun commit hash'i ve UTC zamani; tohum."
KILIT_ALANLARI = ("hipotez", "hukum", "yapilandirma", "parametreler", "olusmus_olay",
                  "analize_giren_olay", "k2_farki", "kesif_commit", "kesif_zamani", "tohum")
# Hukum "hipotez kapandi" iken yapilandirmaya ait alanlar bos olabilir ("-").
KILIT_SECIM_ALANLARI = ("yapilandirma", "parametreler", "k2_farki")
# `gerekce` yalnizca "hipotez kapandi" hukmunde ZORUNLUDUR (madde 4c; bulgu K-C1). On-kayit §8
# madde 5 alani "hukum ... VE KAPANDIYSA gerekcesi" diye sayar; kod onu her hukumde zorunlu
# tutuyordu. Dosya hem hook ile kilitli hem ekleme kurallı oldugu icin, on-kaydin harfine uyup
# "secildi" hukmunde gerekce yazmayan bir kayit KURTARILAMAZ duruma dusuyordu: duzeltmenin tek
# yolu ya kilidi acip dosyayi degistirmek ya da ekleme kuralini bozan ikinci bir commit yazmakti.
# `ortalama_net_getiri` ise "secildi" hukmunde ZORUNLUDUR (madde 4b): §8 madde 4 secimin iki
# kosulundan birini ona baglar ("ortalama net getiri > 0") ve alan yazilmazsa o kosul kod
# duzeyinde HIC denetlenemez.
KILIT_ISTEGE_BAGLI_ALANLAR = ("gerekce", "ortalama_net_getiri")
KILIT_KAPANIS_ALANLARI = ("gerekce",)
KILIT_SECIM_ZORUNLU_ALANLAR = ("ortalama_net_getiri",)


@dataclass(frozen=True)
class KilitKaydi:
    """F2'nin bir hipotez icin kilitledigi karar (on-kayit §8 madde 5). Salt okunur."""

    hipotez: str
    hukum: str
    gerekce: str
    yapilandirma: str
    parametreler: str
    olusmus_olay: int
    analize_giren_olay: int
    # Hukum "hipotez kapandi" iken K2 farki HESAPLANAMAZ'dir ve `None` ile gosterilir; NaN
    # kullanilamaz, cunku `NaN != NaN` yuzunden iki ayni metnin cozumu esit cikmaz ve
    # `kilit_oku`nun HEAD ile calisma agacini karsilastirmasi yanlis ret verir (sizinti S-C8).
    k2_farki: float | None
    kesif_commit: str
    kesif_zamani: str
    tohum: int

    @property
    def secildi(self) -> bool:
        return self.hukum == KILIT_SECILDI


def _kilit_yapilandirmasi_dogrula(kimlik: str, hipotez: str) -> str:
    """Kayittaki yapilandirma, hipotezin §5'teki IZGARASINDA bulunan bir demetin kimligi mi?

    On-kayit §8 madde 5: "secildiyse yapilandirmanin KIMLIGI ve butun parametre degerleri"; §5
    (rev.11): "Izgara parametreleri ... yalnizca bu on-kayitta tanimlidir ... izgarada bulunmayan
    bir parametre demeti hata verir"; §9: "Secilen yapilandirma C1 ve C2'de birer kez kosulur."

    Sizinti bulgusu S-C5 ve denetci bulgusu D-C4: alan yalnizca "bos degil" diye denetleniyordu.
    Izgara disi ya da bicimi bozuk bir kimlik, kosu ACILDIKTAN sonra -- ilk `olay_karari`
    cagrisinda, `onay_baglami_dogrula` icinde -- `OnayUyusmazligi` olarak patliyordu; BASLADI
    satiri yazildigi icin (hipotez, kume) cifti bos yere yaniyordu. Denetim bu yuzden kaydi
    cozerken, yani kosu acilmadan once yapilir.

    `data.sinyal` YEREL olarak ice alinir: `sinyal` -> `klines` -> `split` zinciri modul duzeyinde
    bir dongu olusturur.
    """
    from data import sinyal as sinyal_modulu

    try:
        gecerliler = [sinyal_modulu.yapilandirma_kimligi(hipotez, y) for y in sinyal_modulu.izgara(hipotez)]
    except Exception as hata:          # §5'te izgarasi olmayan ad (ör. calisma aninda eklenmis)
        raise KilitBozuk(f"{hipotez} icin on-kayit §5'te bir izgara yok, dolayisiyla gecerli bir "
                         f"yapilandirma kimligi de yok ({type(hata).__name__}: {hata}).") from None
    if kimlik not in gecerliler:
        raise KilitBozuk(
            f"{hipotez} KILIT.md: yapilandirma {kimlik!r} {hipotez} izgarasinda yok (on-kayit §5). "
            f"Gecerli kimlikler: {gecerliler}. Izgara disi bir kimlik, kosu acildiktan sonra her "
            "pozisyonu reddeder ve onay cifti bos yere yanar (on-kayit §8 madde 5, §9).")
    return kimlik


def _kilit_parametrelerini_dogrula(deger: str, kimlik: str, hipotez: str) -> dict[str, float]:
    """Kayittaki `parametreler` alani, `yapilandirma` KIMLIGIYLE ayni demeti gostermeli (madde 4b).

    On-kayit §8 madde 5: "secildiyse yapilandirmanin kimligi VE BUTUN PARAMETRE DEGERLERI". Alan
    onceden yalnizca "bos degil" diye denetleniyordu (bulgu K-C7): kod kimligi kullandigi icin
    kosu dogru koşardı, ama KALICI KAYIT kimlikle celisen parametreler gosterebilirdi -- yani
    rapor yanlis olurdu ve dosya ekleme kuralina tabi oldugu icin duzeltilemezdi.

    Bicim: `ad=deger` ciftleri, bosluk, virgul ya da noktali virgulle ayrilmis. Karsilastirma
    SAYISALDIR ("0.0003" ile "0.00030" ayni), ad kumesi tam eslesmeli.
    """
    ciftler = [p for p in re.split(r"[\s,;]+", str(deger).strip()) if p]
    if not ciftler:
        raise KilitBozuk(f"{hipotez} KILIT.md: `parametreler` bos olamaz (on-kayit §8 madde 5).")
    okunan: dict[str, float] = {}
    for cift in ciftler:
        if "=" not in cift:
            raise KilitBozuk(f"{hipotez} KILIT.md: `parametreler` `ad=deger` ciftlerinden olusmali; "
                             f"okunamayan parca {cift!r} (on-kayit §8 madde 5).")
        ad, ham = cift.split("=", 1)
        ad = ad.strip().lower()
        if ad in okunan:
            raise KilitBozuk(f"{hipotez} KILIT.md: `parametreler` alaninda `{ad}` iki kez yazilmis.")
        if not re.fullmatch(r"[+-]?\d+(\.\d+)?", ham.strip().replace(",", "."), re.ASCII):
            raise KilitBozuk(f"{hipotez} KILIT.md: `parametreler` icindeki `{ad}` duz ondalik bir sayi "
                             f"olmali; verilen {ham!r}.")
        okunan[ad] = float(ham.strip().replace(",", "."))
    # Kimlik: `H2:phi=0.0003,k=3`
    beklenen = {}
    for parca in kimlik.split(":", 1)[1].split(","):
        ad, ham = parca.split("=", 1)
        beklenen[ad.strip().lower()] = float(ham)
    if set(okunan) != set(beklenen) or any(okunan[a] != beklenen[a] for a in beklenen):
        raise KilitBozuk(
            f"{hipotez} KILIT.md: `parametreler` ({okunan}) `yapilandirma` kimligiyle ({kimlik}) ayni "
            "demeti gostermiyor. On-kayit §8 madde 5 ikisini birlikte ister; kalici kayit kimlikle "
            "celisen parametre degerleri gosteremez (madde 4b).")
    return okunan


def _kilit_commiti_dogrula(deger: str, hipotez: str) -> str:
    """On-kayit §8 madde 5: "kesif kosusunun commit hash'i". Tam 40 haneli onaltilik (git SHA-1).

    Sizinti bulgusu S-C7: alan hic denetlenmiyordu; "yok" ya da 39 haneli bir deger de geciyordu.
    Hash kaydin tekrarlanabilirlik baglantisidir (CLAUDE.md §5 "tohum ve commit sonuc dosyasina
    yazilir"), bu yuzden bicimi denetlenir -- varligi git'te ARANMAZ: kesif kosusunun commit'i
    baska bir dalda ya da henuz itilmemis olabilir.
    """
    ham = str(deger).strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", ham):
        raise KilitBozuk(f"{hipotez} KILIT.md: `kesif_commit` 40 haneli onaltilik bir git hash'i olmali; "
                         f"verilen {deger!r} (on-kayit §8 madde 5).")
    return ham


def _kilit_zamani_dogrula(deger: str, hipotez: str) -> str:
    """On-kayit §8 madde 5: "kesif kosusunun ... UTC zamani". ISO 8601, saat dilimi UTC.

    CLAUDE.md §5: "Tum zaman damgalari UTC." Saat dilimsiz ya da UTC disi bir damga reddedilir
    (sizinti bulgusu S-C7); "dun" gibi serbest metin de.
    """
    ham = str(deger).strip()
    try:
        zaman = pd.Timestamp(ham)
    except (ValueError, TypeError):
        raise KilitBozuk(f"{hipotez} KILIT.md: `kesif_zamani` ISO 8601 bir zaman damgasi olmali; verilen "
                         f"{deger!r} (on-kayit §8 madde 5).") from None
    if zaman.tz is None or zaman.utcoffset() != dt.timedelta(0):
        raise KilitBozuk(f"{hipotez} KILIT.md: `kesif_zamani` UTC olmali (ör. '2026-10-20T12:00:00+00:00'); "
                         f"verilen {deger!r} (CLAUDE.md §5: 'Tum zaman damgalari UTC').")
    return ham


def kilit_kaydi_coz(metin: str, hipotez: str) -> KilitKaydi:
    """KILIT.md metnini `KilitKaydi`ya cevirir. SAF.

    Bicim: `| alan | deger |` satirlari (tablo basligi ve ayirici satirlari atlanir). Her zorunlu
    alan TAM BIR KEZ bulunmali; iki kez bulunan alan dosyanin degistirildigini ya da ikinci bir
    kayit yazildigini gosterir ve ekleme kuralini (on-kayit §8 madde 5) bozar.
    """
    alanlar: dict[str, str] = {}
    for satir in metin.splitlines():
        s = satir.strip()
        if not s.startswith("|"):
            continue
        hucreler = [h.strip() for h in s.strip("|").split("|")]
        if len(hucreler) != 2 or set(hucreler[0]) <= set("-: ") or hucreler[0].lower() == "alan":
            continue
        ad = hucreler[0].lower()
        if ad not in KILIT_ALANLARI and ad not in KILIT_ISTEGE_BAGLI_ALANLAR:
            continue
        if ad in alanlar:
            raise KilitBozuk(f"{hipotez} KILIT.md: `{ad}` alani birden fazla kez yazilmis. Dosya yalnizca "
                             "ekleme kuralina tabidir: bir hipotezin kaydi yazildiktan sonra degistirilmez "
                             "(on-kayit §8 madde 5).")
        alanlar[ad] = hucreler[1]
    eksik = [a for a in KILIT_ALANLARI if a not in alanlar]
    if eksik:
        raise KilitBozuk(f"{hipotez} KILIT.md: eksik alan(lar) {eksik}; on-kayit §8 madde 5'teki butun "
                         f"alanlar bulunmali ({list(KILIT_ALANLARI)}).")
    if alanlar["hipotez"] != hipotez:
        raise KilitBozuk(f"KILIT.md'nin hipotez alani {alanlar['hipotez']!r}, dosya {hipotez} icin okundu.")
    if alanlar["hukum"] not in KILIT_HUKUMLERI:
        raise KilitBozuk(f"{hipotez} KILIT.md: hukum {KILIT_HUKUMLERI} olmali; verilen {alanlar['hukum']!r}.")
    secildi = alanlar["hukum"] == KILIT_SECILDI

    def _tam(ad: str) -> int:
        """Olay sayisi ve tohum: NEGATIF OLMAYAN tamsayi (sizinti bulgusu S-C6).

        Nokta yalnizca BINLIK ayirici olarak kabul edilir ("1.500" = 1500) ve yalnizca uclu
        gruplar halinde; onceki uygulama butun noktalari siliyordu, bu yuzden "1.5" sessizce 15
        okunuyordu ve isaret hic denetlenmiyordu ("-5" -> -5 kabul ediliyordu).
        """
        ham = str(alanlar[ad]).strip()
        # `re.ASCII` (madde 4b): Python'da `\d` Unicode rakamlarini da eslestirir, bu yuzden tam
        # genislikli "１５０" ya da baska bir yazi sisteminin rakami sessizce sayi olarak okunuyordu.
        #
        # F1 kapatma turu madde 1c (bulgu 22): gruplu bicimin ilk grubu SIFIRLA BASLAMAZ. Onceki
        # desen `\d{1,3}(\.\d{3})+` oldugu icin "0.150" gecerli bir binlik yazim sayiliyor ve 150
        # OKUNUYORDU; yani ondalik bir sayi (0.150) §8 madde 2'nin 150 olay esigini sessizce
        # geciriyordu. Sifir tek basina ("0") hala gecerlidir, cunku ikinci dal `\d+`dir.
        if not re.fullmatch(r"[1-9]\d{0,2}(\.\d{3})+|\d+", ham, re.ASCII):
            raise KilitBozuk(
                f"{hipotez} KILIT.md: `{ad}` negatif olmayan bir tamsayi olmali (binlik ayirici nokta "
                f"olabilir: '1.500'); verilen {alanlar[ad]!r}. Ondalikli, isaretli, sifirla baslayan "
                "gruplu ya da sayi olmayan deger kabul edilmez (on-kayit §8 madde 5).")
        rakamlar = ham.replace(".", "")
        # Bulgu 23: cok uzun rakam dizisi `int()` sinirina takiliyor ve CIPLAK `ValueError` veriyordu;
        # kaydin bozuk oldugunu bildiren tek sinif `KilitBozuk` olmali (cagiran onu yakalar).
        azami = sys.get_int_max_str_digits()
        if len(rakamlar) > azami:
            raise KilitBozuk(
                f"{hipotez} KILIT.md: `{ad}` {len(rakamlar)} haneli; tamsayi okumasi icin en cok {azami} "
                f"hane cozulebilir. Alan bir olay sayisi ya da tohumdur (on-kayit §8 madde 5).")
        return int(rakamlar)

    def _ondalik(ad: str) -> float | None:
        """Oran alanlari: isaretli DUZ ondalik sayi (madde 4b).

        `float()` tek basina `inf`, `Infinity`, `nan` ve `1e999` (= inf) degerlerini kabul
        ediyordu; `inf` K2 farki madde 4 denetimini ("> 0") sessizce geciyordu. Bicim bu yuzden
        regexle sinirlanir: ASCII rakamlar, tek bir ondalik ayirici (`.` ya da `,`), ustel gosterim
        YOK.
        """
        if not secildi:
            return None
        ham = str(alanlar[ad]).strip().replace(",", ".")
        if not re.fullmatch(r"[+-]?\d+(\.\d+)?", ham, re.ASCII):
            raise KilitBozuk(f"{hipotez} KILIT.md: `{ad}` duz ondalik bir sayi olmali (ör. '0.0123' ya da "
                             f"'-0.5'); verilen {alanlar[ad]!r}. Ustel gosterim, 'inf'/'nan' ve Unicode "
                             "rakamlar kabul edilmez (on-kayit §8 madde 4-5).")
        deger = float(ham)
        if not math.isfinite(deger):
            raise KilitBozuk(f"{hipotez} KILIT.md: `{ad}` sonlu bir sayi olmali; verilen {alanlar[ad]!r}.")
        return deger

    if secildi:
        bos = [a for a in KILIT_SECIM_ALANLARI if not alanlar[a].strip() or alanlar[a].strip() in ("-", "—")]
        if bos:
            raise KilitBozuk(f"{hipotez} KILIT.md: hukum '{KILIT_SECILDI}' iken {bos} alan(lari) bos olamaz "
                             "(on-kayit §8 madde 5).")
        kimlik = _kilit_yapilandirmasi_dogrula(alanlar["yapilandirma"].strip(), hipotez)
        eksik_secim = [a for a in KILIT_SECIM_ZORUNLU_ALANLAR if a not in alanlar]
        if eksik_secim:
            raise KilitBozuk(
                f"{hipotez} KILIT.md: hukum '{KILIT_SECILDI}' iken {eksik_secim} alan(lari) yazilmali: "
                "on-kayit §8 madde 4 secimin kosullarindan birini ortalama net getiriye baglar ve alan "
                "yazilmazsa o kosul kod duzeyinde denetlenemez (madde 4b).")
        _kilit_parametrelerini_dogrula(alanlar["parametreler"], kimlik, hipotez)
    else:
        if "gerekce" not in alanlar:
            raise KilitBozuk(f"{hipotez} KILIT.md: hukum '{KILIT_KAPANDI}' iken `gerekce` alani bulunmali "
                             "(on-kayit §8 madde 5: 'kapandiysa gerekcesi').")
        if not alanlar["gerekce"].strip() or alanlar["gerekce"].strip() in ("-", "—"):
            raise KilitBozuk(f"{hipotez} KILIT.md: hukum '{KILIT_KAPANDI}' iken gerekce yazilmali "
                             "(on-kayit §8 madde 4: 'kapanma gerekcesi').")
    if secildi:
        # On-kayit §8 madde 4: "Bir yapilandirma secilmisse, o yapilandirma icin su iki kosul
        # kesifte saglanmiyorsa hipotez ONAYA GONDERILMEDEN kapanir (onay verisi harcanmaz):
        # K2 farki > 0; ortalama net getiri > 0." Sizinti bulgusu S-C3: kayitta `k2_farki <= 0`
        # oldugu halde kosu aciliyordu ve BASLADI satiri yazildigi icin (hipotez, kume) cifti
        # harcaniyordu. Denetim bu yuzden kosu acilmadan ONCE, kaydi cozerken yapilir.
        if not (_ondalik("k2_farki") > 0):
            raise KilitBozuk(
                f"{hipotez} KILIT.md: hukum '{KILIT_SECILDI}' iken K2 farki > 0 olmali; verilen "
                f"{alanlar['k2_farki']!r}. On-kayit §8 madde 4: kosul saglanmiyorsa hipotez onaya "
                "gonderilmeden kapanir, yani hukum 'hipotez kapandi' olmaliydi.")
        if "ortalama_net_getiri" in alanlar and not (_ondalik("ortalama_net_getiri") > 0):
            raise KilitBozuk(
                f"{hipotez} KILIT.md: hukum '{KILIT_SECILDI}' iken ortalama net getiri > 0 olmali; "
                f"verilen {alanlar['ortalama_net_getiri']!r} (on-kayit §8 madde 4).")
        # On-kayit §8 madde 2-3: "Aday yapilandirmalar: olay sayisi >= 150 ... Buradaki ve §9'daki
        # olay sayisi, ANALIZE GIREN olaylarin sayisidir" ve "Adaylar arasindan K2 farki en yuksek
        # olan secilir". Esigi gecmeyen bir yapilandirma ADAY DEGILDIR, dolayisiyla secilemez;
        # madde 4'e gore hipotez "aday yok" gerekcesiyle kapanmis olmaliydi (sizinti bulgusu
        # S-C4). Esik koddan tek yerden okunur (`config.ADAY_OLAY_ESIGI`).
        if _tam("analize_giren_olay") < config.ADAY_OLAY_ESIGI:
            raise KilitBozuk(
                f"{hipotez} KILIT.md: hukum '{KILIT_SECILDI}' iken analize giren olay sayisi on-kayit "
                f"§8 madde 2 esigini gecmeli (>= {config.ADAY_OLAY_ESIGI}); verilen "
                f"{alanlar['analize_giren_olay']!r}. Esigi gecmeyen yapilandirma aday degildir; madde 4 "
                "geregi hukum 'hipotez kapandi' (gerekce: aday yok) olmaliydi.")
    _kilit_commiti_dogrula(alanlar["kesif_commit"], hipotez)
    _kilit_zamani_dogrula(alanlar["kesif_zamani"], hipotez)
    if _tam("tohum") != config.TOHUM:
        raise KilitBozuk(f"{hipotez} KILIT.md: tohum on-kayit §7 degeri olmali ({config.TOHUM}); verilen "
                         f"{alanlar['tohum']!r}.")
    if _tam("analize_giren_olay") > _tam("olusmus_olay"):
        raise KilitBozuk(f"{hipotez} KILIT.md: analize giren olay sayisi olusmus olay sayisini asamaz "
                         "(on-kayit §8 madde 2).")
    return KilitKaydi(hipotez=hipotez, hukum=alanlar["hukum"], gerekce=alanlar.get("gerekce", ""),
                      yapilandirma=alanlar["yapilandirma"], parametreler=alanlar["parametreler"],
                      olusmus_olay=_tam("olusmus_olay"), analize_giren_olay=_tam("analize_giren_olay"),
                      k2_farki=_ondalik("k2_farki"), kesif_commit=alanlar["kesif_commit"],
                      kesif_zamani=alanlar["kesif_zamani"], tohum=_tam("tohum"))


def kilit_yolu(hipotez: str) -> Path:
    """`analysis/<hipotez>/KILIT.md` (on-kayit §8 madde 5: "Dosyanin yolu bu on-kayitta yazili
    olandir"). Test kipinde kok testin verdigi gecici dizindir."""
    ad = _hipotez_dogrula(hipotez)
    test = _test_ayari()
    kok = test.kilit_koku if test is not None and test.kilit_koku is not None else _depo()
    return Path(kok) / "analysis" / ad / KILIT_ADI


def _kilit_gecmisini_denetle(goreli: str, hipotez: str) -> None:
    """Kayit git gecmisinde TAM BIR KEZ eklenmis ve sonradan degistirilmemis olmali.

    On-kayit §8 madde 5: "Dosya da yalnizca ekleme kuralina tabidir: bir hipotezin kaydi
    yazildiktan sonra degistirilmez."

    Sizinti bulgusu S-C9: `kilit_oku` yalnizca HEAD ile calisma agacini karsilastiriyordu, bu
    yuzden ikinci bir COMMIT'LE degistirilen kayit fark edilmiyordu ve ekleme kurali yalnizca
    `PreToolUse` hook'una dayaniyordu (hook arac cagrilarini yakalar, git'i degil). Denetim
    `ONAY_KAYDI` ile ayni yaklasimi kullanir: butun referanslar ve reflog (`--all --reflog
    --full-history`) taranir, yani silinmis dal, `rebase`, `amend` ve `reset` ile birakilan
    commit'ler de gorunur. Dosyayi DEGISTIREN her commit bir ihlaldir; yalnizca eklendigi tek
    commit bulunmalidir.
    """
    bloblar = _kilit_bloblari("--all", "--reflog", goreli=goreli)
    if len(bloblar) != 1:
        raise KilitBozuk(
            f"{hipotez} KILIT.md git gecmisinde {len(bloblar)} farkli icerikle bulunuyor "
            f"({sorted(bloblar)[:5]}{'...' if len(bloblar) > 5 else ''}). Dosya yalnizca EKLEME "
            "kuralina tabidir: bir hipotezin kaydi yazildiktan sonra degistirilmez (on-kayit §8 "
            "madde 5).")
    # UZAK DEPO SIMETRISI (madde 4a; bulgu K-C3 ve sizinti 4). Yerel gecmis ve reflog sahibi
    # tarafindan yeniden yazilabilir: `reset --hard` + `reflog expire --expire=now --all` eski
    # blob'u yok ettiginde DEGISTIRILMIS bir kayit yine "tek blob" gorunur. `ONAY_KAYDI` ayni
    # riski `origin/main` gecmisine bakarak kapatir (CLAUDE.md §3.3 tek atis denetimi); kilit
    # kaydi da onay kosusundan once commit edilip itilmis olmali, bu yuzden ayni denetim burada
    # da uygulanir. Uzak depoda hic gorunmeyen bir kayit itilmemis demektir.
    if not _sahte_git():
        # Uzak izleme referansi HER ZAMAN yenilenir (F1 kapatma turu madde 1c, bulgu 24). Onceki
        # kod referans varsa fetch yapmiyordu; `git update-ref refs/remotes/origin/main HEAD` ile
        # yerelde ileri sarilmis bir referans, hic itilmemis bir kilit kaydini "uzak depoda var"
        # gosteriyordu ve tek atis guvencesinin uzak depo simetrisi kalkiyordu. `_uzagi_getir`
        # zorlamali bir refspec kullanir (`+refs/heads/main:...`), yani yerelde elle yazilmis
        # referans gercek uzak degerle degisir; ag yoksa kosu acilmaz (yerel kipe dusulmez).
        #
        # Adres denetimi fetch'ten ONCE (parcali tam takimda cikan gerileme): `onay_kosusu`
        # kilidi `_uzak_adresi_denetle`den once okudugu icin, `origin` baska bir depoya
        # yonlendirilmisse artik once fetch deniyor ve hata "alinamadi" sinifina dusuyordu --
        # oysa dogru hata "beklenen depo degil"dir. Ikisi ayri durum: biri agin yokluğu, oteki
        # kaydin yanlis depoya itilmis olmasi.
        _uzak_adresi_denetle()
        _uzagi_getir()
        uzak_bloblar = _kilit_bloblari(_UZAK_REF, goreli=goreli)
        if not uzak_bloblar:
            raise KilitYok(
                f"{hipotez} KILIT.md {UZAK_DEPO}/{UZAK_DAL} gecmisinde yok: secim onay kosusundan once "
                "commit edilip ITILMIS olmali (on-kayit §8 madde 5; CLAUDE.md §3.3 ile ayni olcut).")
        if uzak_bloblar != bloblar:
            raise KilitBozuk(
                f"{hipotez} KILIT.md yerel gecmiste {sorted(bloblar)} iceriklerini, "
                f"{UZAK_DEPO}/{UZAK_DAL} gecmisinde {sorted(uzak_bloblar)} iceriklerini tasiyor. Kayit "
                "yazildiktan sonra degistirilmez (on-kayit §8 madde 5); yerel gecmis yeniden "
                "yazilmis olabilir.")


def _kilit_bloblari(*refler: str, goreli: str) -> set[str]:
    """Verilen referanslarin gecmisinde `goreli` yolunun BLOB kimlikleri (icerikleri).

    Olcut commit SAYISI degil, farkli ICERIK sayisidir: `git stash` gibi islemler butun agacin
    anlik goruntusunu commit'ler ve dosyanin icerigi degismese de yeni commit uretir; ayni blob
    tekrar gorundugunde ihlal yoktur.

    `--full-history` (madde 4a; sizinti 4): bu bayrak olmadan `rev-list` yol budamasi yapar ve
    birlestirmelerin TEK ebeveynini izler, yani yan dalda degistirilip `merge -s ours` ile
    birlestirilen bir icerik GORUNMEZ. `ONAY_KAYDI` tarafinda (`_uzak_gecmis_kaydi`) bayrak
    bastan beri vardi; burada belgede yaziliyken komutta yoktu.
    """
    cikti = _git("rev-list", *refler, "--full-history", "--objects", "--", goreli)
    if cikti is None:
        raise OnayOrtamiHatasi(f"{goreli} denetlenemedi: git gecmisi okunamadi ({' '.join(refler)}).")
    return {satir.split()[0] for satir in cikti.splitlines()
            if satir.strip().endswith(goreli) and satir.split()}


def kilit_oku(hipotez: str) -> KilitKaydi:
    """Hipotezin kilitli yapilandirmasini okur (on-kayit §8 madde 5, rev.13).

    Dosya bulunmali ve COMMIT EDILMIS olmali ("Secim, onay kosusundan once ... commit edilir");
    calisma agacindaki metin HEAD'dekinden farkliysa `KilitYok`. Sahte git kipinde (yalnizca
    testler) HEAD denetimi yapilmaz, `ONAY_KAYDI` ile ayni yaklasim.
    """
    ad = _hipotez_dogrula(hipotez)
    yol = kilit_yolu(ad)
    if not yol.exists():
        raise KilitYok(f"{ad} icin kilit dosyasi yok: {yol}. F2'nin secimi commit edilmeden onay kosusu "
                       "acilmaz (on-kayit §8 madde 5).")
    with yol.open("r", encoding="utf-8", newline="") as dosya:
        metin = dosya.read()
    if not _sahte_git():
        try:
            goreli = yol.resolve().relative_to(_depo().resolve()).as_posix()
        except ValueError:
            raise OnayOrtamiHatasi(f"{yol} git deposunun ({_depo()}) icinde degil.") from None
        agac = _git("ls-tree", "--name-only", "HEAD", "--", goreli)
        if agac is None:
            raise OnayOrtamiHatasi(f"{goreli} denetlenemedi: HEAD okunamadi.")
        if not agac.strip():
            raise KilitYok(f"{goreli} HEAD'de yok: F2'nin secimi commit edilmeden onay kosusu acilmaz "
                           "(on-kayit §8 madde 5).")
        head_metni = _git("cat-file", "blob", f"HEAD:{goreli}")
        if head_metni is None:
            raise OnayOrtamiHatasi(f"HEAD:{goreli} okunamadi.")
        # Karsilastirma kaydin ALANLARIYLA yapilir; "hipotez kapandi" hukmunde `k2_farki` artik
        # `None`dur (NaN degil), bu yuzden ayni metnin iki cozumu esittir (sizinti bulgusu S-C8).
        if kilit_kaydi_coz(head_metni, ad) != kilit_kaydi_coz(metin, ad):
            raise KilitYok(f"{goreli} calisma agacinda HEAD'dekinden farkli. Dosya yalnizca ekleme kuralina "
                           "tabidir ve onay kosusundan once commit edilir (on-kayit §8 madde 5).")
        _kilit_gecmisini_denetle(goreli, ad)
    return kilit_kaydi_coz(metin, ad)


@dataclass(frozen=True)
class KosuOrtami:
    """Onay kosusunun acildigi ortam: HEAD commit'i (40 hane) ve cagiran betigin depo icindeki yolu."""

    commit: str
    betik: str


def ortam_karari(head: str | None, durum: str | None, betik: str | None, izleniyor: bool) -> KosuOrtami:
    """Kosu ortaminin karari. Saf.

    `head`: `git rev-parse HEAD` ciktisi; `durum`: `git status --porcelain` ciktisi (None: git okunamadi);
    `betik`: cagiran betigin depo icindeki yolu (None: etkilesimli oturum ya da `python -c`); `izleniyor`:
    betik git'te izleniyor mu. Temiz agac + izlenen betik: kosunun kodu kayda yazilan commit'te bulunur.
    """
    if head is None or not re.fullmatch(r"[0-9a-f]{40}", head.strip()):
        raise OnayOrtamiHatasi("Onay kosusu acilamaz: git commit'i okunamadi (git yok ya da depo degil).")
    if durum is None:
        raise OnayOrtamiHatasi("Onay kosusu acilamaz: calisma agacinin durumu okunamadi.")
    kirli = [s for s in durum.splitlines() if s.strip()]
    if kirli:
        # RESULTS §14.46: kirli sayilan dosyalarin adi yazilmaz, yalnizca sayisi (`git status` ile ayrintiya bakilir).
        raise OnayOrtamiHatasi(
            f"Onay kosusu yalnizca temiz calisma agacinda acilir; {len(kirli)} kirli kayit var (izlenen degisiklik, "
            "assume-unchanged / skip-worktree isareti ya da .gitignore disi izlenmeyen dosya). Once commit edin.")
    if betik is None:
        raise OnayOrtamiHatasi("Onay kosusu etkilesimli oturumdan ya da `python -c` ile acilamaz; depo "
                               "icinde git'te izlenen bir betikten calistirin.")
    if not izleniyor or "|" in betik or not betik.strip():
        raise OnayOrtamiHatasi(f"Onay kosusunu acan betik ({betik}) depo icinde git'te izlenen bir dosya olmali.")
    return KosuOrtami(head.strip(), betik)


def _kosu_ortami() -> KosuOrtami:
    test = _test_ayari()
    if test is not None and test.depo is None:
        return ortam_karari(test.head, test.durum, test.betik, test.izleniyor)
    import __main__

    yol = getattr(__main__, "__file__", None)
    betik, izleniyor = None, False
    if test is not None:  # test deposu: git gercek, yalnizca cagiran betik testten gelir
        betik = test.betik
        izleniyor = betik is not None and _git("ls-files", "--error-unmatch", "--", betik) is not None
    elif yol:
        try:
            betik = Path(yol).resolve().relative_to(Path(config.KOK).resolve()).as_posix()
        except ValueError:
            betik = str(yol)  # depo disi: izlenmiyor
        else:
            izleniyor = _git("ls-files", "--error-unmatch", "--", betik) is not None
    kirli = _agac_kirlilikleri()
    durum = None if kirli is None else "".join(f"{k}\n" for k in kirli)
    return ortam_karari(_git("rev-parse", "HEAD"), durum, betik, izleniyor)


# --- Test kaydi (yalnizca pytest) --------------------------------------------


@dataclass(frozen=True)
class _TestAyari:
    test: str
    yol: Path
    head: str | None
    durum: str | None
    betik: str | None
    izleniyor: bool
    depo: Path | None
    uzak: Path | None = None
    # KILIT.md'lerin koku (on-kayit §8 madde 5). Verilmezse `_depo()`: gercek kosuda depo kokudur.
    kilit_koku: Path | None = None


_TEST_AYARI: _TestAyari | None = None


# pytest oturumu isareti (S-10, RESULTS §14.44): `tests/conftest.py` `pytest_configure` kancasinda `_pytest_oturumu_kur`
# ile kurar. Yalnizca gercek bir pytest oturumunda vardir; `import pytest` ve sahte `PYTEST_CURRENT_TEST` artik istisnayi
# acmaz. Iki ad da `_KORUNAN_ADLAR`dadir (modul disindan atanamaz) ve analiz kodunda adiyla anilmalari taramayla yasaktir
# (`tests/tarama_yardimcisi.ONAY_ATLATMA_DESENI`; RESULTS §14.46, D-B2, S-38; §14.45'e kadar bu yorum desende olmayan
# adlari desende sayiyordu). Sinir (kayitta kalir, S-37): sozlugun ogesine dogrudan yazma ve sahte bir `pytest.Config`
# nesnesi (`__new__`, `Mock(spec=...)`) bu korumadan gecer; ikisi de kasitli kod bicimi ister ve ad taramasina takilir.
_PYTEST_OTURUMU = {"config": None}


def _pytest_oturumu_kur(pytest_config) -> None:
    """YALNIZCA `tests/conftest.py` `pytest_configure`: verilen nesne gercek bir `pytest.Config` olmali."""
    import pytest

    if not isinstance(pytest_config, pytest.Config):
        raise OnayKorumasi("pytest oturumu isareti yalnizca pytest_configure kancasindan kurulur.")
    _PYTEST_OTURUMU["config"] = pytest_config


def _pytest_testi() -> str | None:
    """Calisan pytest testinin kimligi; pytest disinda (oturum isareti yoksa) None."""
    deger = os.environ.get("PYTEST_CURRENT_TEST")
    if not deger or "pytest" not in sys.modules or _PYTEST_OTURUMU["config"] is None:
        return None
    return deger.rsplit(" (", 1)[0]


def _test_kaydi_ayarla(yol, *, head: str | None = "0" * 40, durum: str | None = "",
                       betik: str | None = "tests/onay_testi.py", izleniyor: bool = True,
                       depo=None, uzak=None, kilit_koku=None) -> Path:
    """YALNIZCA TESTLER ICIN: bu pytest testi suresince kayit yolunu ve git ortamini degistirir.

    Ayar yalnizca onu kuran testin kimligiyle (`PYTEST_CURRENT_TEST`) gecerlidir; test bitince kendiliginden
    gecersizlesir. pytest disinda `OnayKorumasi`. Analiz kodunda bu adin gecmesi taramayla yasak
    (`tests/tarama_yardimcisi.ONAY_ATLATMA_DESENI`).

    Iki kip:
      - `depo=None` (sahte git): ortam `head`, `durum`, `betik`, `izleniyor` degerlerinden gelir; git gecmisi
        okunmaz ve kayit commit edilmez, kayit her an commit edilmis sayilir (HEAD = calisma agaci).
      - `depo=<gecici git deposu>` (gercek git): butun git islemleri o depoda gercekten yapilir (temiz agac,
        HEAD, `ls-files`, gecmis, commit). Testten yalnizca cagiran betigin depo icindeki yolu (`betik`) gelir;
        `head`, `durum`, `izleniyor` yok sayilir. `yol` deponun icinde olmalidir.
    `uzak` (gercek git kipi): beklenen uzak depo (yerel ciplak depo yolu; `config.UZAK_DEPO_ADRESI` yerine).
    Verilmezse ayni testin onceki ayarindaki deger kalir (klonlar ayni uzak depoya yonlendirilirken).
    """
    global _TEST_AYARI
    test = _pytest_testi()
    if test is None:
        raise OnayKorumasi("Test kaydi yalnizca bir pytest testi icinde ayarlanabilir.")
    onceki = _test_ayari()
    if uzak is None and onceki is not None:
        uzak = onceki.uzak
    if kilit_koku is None and onceki is not None:
        kilit_koku = onceki.kilit_koku
    _TEST_AYARI = _TestAyari(test, Path(yol), head, durum, betik, izleniyor, None if depo is None else Path(depo),
                             None if uzak is None else Path(uzak),
                             None if kilit_koku is None else Path(kilit_koku))
    return Path(yol)


def _test_ayari() -> _TestAyari | None:
    ayar = _TEST_AYARI
    if ayar is None or _pytest_testi() != ayar.test:
        return None
    return ayar


def _depo() -> Path:
    """Git komutlarinin calistigi depo: gercekte `config.KOK`, test deposu kipinde o depo."""
    test = _test_ayari()
    return test.depo if test is not None and test.depo is not None else Path(config.KOK)


# --- Kayit dosyasi -----------------------------------------------------------


def _kayit_yolu() -> Path:
    if Path(config.ONAY_KAYDI) != _KAYIT_YOLU:
        raise OnayKorumasi(f"config.ONAY_KAYDI ({config.ONAY_KAYDI}) yukleme anindaki degerden ({_KAYIT_YOLU}) "
                           "farkli; kayit yolu tek kaynaktan gelir.")
    test = _test_ayari()
    return test.yol if test is not None else _KAYIT_YOLU


def _kaydi_oku() -> str:
    # newline="" satir sonlarini cevirmeden okur/yazar; aksi halde Windows'ta tum
    # dosyanin LF'leri CRLF'e donusur ve mevcut satirlar degismis olur.
    hedef = _kayit_yolu()
    if not hedef.exists():
        return ""
    with hedef.open("r", encoding="utf-8", newline="") as dosya:
        return dosya.read()


@contextmanager
def _kayit_kilidi():
    """Kayit dosyasinin oku-denetle-yaz adimini surecler arasi tekil yapar (ayni cift icin es zamanli iki
    kosu). Kilit dosyasi kayitla ayni dizinde; asili kalirsa calisma agaci kirli gorunur."""
    hedef = _kayit_yolu()
    kilit = hedef.with_name("." + hedef.name + ".kilit")
    for _ in range(100):
        try:
            tanitici = os.open(kilit, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            time.sleep(0.1)
    else:
        raise OnayKorumasi(f"Onay kaydi kilidi alinamadi: {kilit}. Baska bir kosu yaziyor ya da eski bir kilit "
                           "kaldi; elle incelenmeli.")
    try:
        yield
    finally:
        os.close(tanitici)
        kilit.unlink(missing_ok=True)


def kayda_satir_ekle(metin: str, satir: str) -> str:
    """Yeni satiri onay tablosunun son satirinin hemen altina yerlestirir. Saf.

    Denetci bulgusu B7: satir eskiden dosyanin SONUNA ekleniyordu; kayit
    dosyasi tablonun altinda bir aciklama cumlesiyle bittigi icin ilk gercek onay
    kosusu tablonun disina dusecek ve tablo olarak gorunmeyecekti.

    Mevcut hicbir satir silinmez ya da degistirilmez; yalnizca bir satir eklenir
    (CLAUDE.md §3.3). Eklenen satir, tablonun satir sonu stilini (LF / CRLF) izler.
    Tablo basligi bulunamazsa satir dosyanin sonuna eklenir.
    """
    satirlar = metin.splitlines(keepends=True)
    baslik = next((i for i, s in enumerate(satirlar) if s.startswith(ONAY_TABLO_BASLIGI)), None)
    if baslik is None:
        if metin and not metin.endswith("\n"):
            metin += "\n"
        return metin + satir.rstrip("\r\n") + "\n"

    son = baslik
    while son + 1 < len(satirlar) and satirlar[son + 1].startswith("|"):
        son += 1
    sonek = "\r\n" if satirlar[baslik].endswith("\r\n") else "\n"
    if not satirlar[son].endswith("\n"):  # tablo dosyanin son satiri ve sonek yok
        satirlar[son] += sonek
    yeni = satir.rstrip("\r\n") + sonek
    return "".join(satirlar[: son + 1] + [yeni] + satirlar[son + 1 :])


def not_alanlari(hucre: str) -> dict[str, str]:
    """Not hucresinin `anahtar=deger` alanlari. Saf. `sonuc=` son alandir ve hucre sonuna kadar surer
    (sonuc metni bosluk icerebilir). Ayni anahtar birden fazlaysa ilki gecerlidir."""
    alanlar: dict[str, str] = {}
    kelimeler = hucre.split()
    for i, kelime in enumerate(kelimeler):
        anahtar, ayrac, deger = kelime.partition("=")
        if not ayrac:
            continue
        if anahtar == "sonuc":
            alanlar.setdefault("sonuc", " ".join([deger, *kelimeler[i + 1:]]))
            break
        alanlar.setdefault(anahtar, deger)
    return alanlar


def kayit_satirlari(metin: str) -> list[dict[str, str]]:
    """Kayittaki onay satirlari: `kume`, `betik`, `commit` ve Not hucresinin alanlari (`hipotez`, `kosu`,
    `durum`, ...). Saf. `hipotez=` alani olmayan satirlar (baslik, ayirici) atlanir.

    Satir bicimi: `| tarih | kume | betik | commit (durum) | hipotez=<ad> kosu=<kimlik> durum=<...> ... |`.
    """
    sonuc = []
    for satir in metin.splitlines():
        if not satir.startswith("|") or satir.startswith(ONAY_TABLO_BASLIGI):
            continue
        hucreler = [h.strip() for h in satir.strip().strip("|").split("|")]
        if len(hucreler) < 5:
            continue
        alanlar = not_alanlari(hucreler[4])
        if "hipotez" not in alanlar:
            continue
        sonuc.append({**alanlar, "kume": hucreler[1], "betik": hucreler[2], "commit": hucreler[3].split(" ")[0]})
    return sonuc


def kayittaki_kosular(metin: str) -> set[tuple[str, str]]:
    """Kayit metnindeki onay kosularinin (hipotez, kume) ciftleri. Saf.

    BASLADI, BITTI ya da HATA fark etmez: kayitta satiri olan cift harcanmistir (tek atis)."""
    return {(s["hipotez"], s["kume"]) for s in kayit_satirlari(metin)}


# --- Kaydin git'teki hali (onay kaydi ikinci tur, denetci OK D-B1) ------------


def onay_satirlari(metin: str) -> list[str]:
    """Kayittaki onay satirlari, bas ve sondaki bosluk ve satir sonu olmadan, sirasiyla. Saf."""
    return [s.strip() for s in metin.splitlines() if kayit_satirlari(s)]


def gecmis_satirlari(log_ciktisi: str) -> str:
    """`git log -p` ciktisindan dosyaya eklenmis butun satirlar: hunk icindeki (`@@` satirindan sonra) `+` ile
    baslayan satirlar. `diff --git` ile ilk `@@` arasindaki baslik (`+++ b/...`) atlanir. Saf."""
    eklenen, baslikta = [], True
    for satir in log_ciktisi.splitlines():
        if satir.startswith("diff --git "):
            baslikta = True
        elif satir.startswith("@@"):
            baslikta = False
        elif not baslikta and satir.startswith("+"):
            eklenen.append(satir[1:])
    return "\n".join(eklenen)


def _sahte_git() -> bool:
    test = _test_ayari()
    return test is not None and test.depo is None


def _kayit_goreli() -> str:
    """Kayit dosyasinin depo icindeki yolu."""
    try:
        return _kayit_yolu().resolve().relative_to(_depo().resolve()).as_posix()
    except ValueError:
        raise OnayOrtamiHatasi(f"Onay kaydi ({_kayit_yolu()}) git deposunun ({_depo()}) icinde degil.") from None


def _head_kaydi() -> str:
    """HEAD'deki kayit metni; kayit HEAD'de yoksa bos metin. Sahte git kipinde calisma agacindaki metin."""
    if _sahte_git():
        return _kaydi_oku()
    goreli = _kayit_goreli()
    agac = _git("ls-tree", "--name-only", "HEAD", "--", goreli)
    if agac is None:
        raise OnayOrtamiHatasi("Onay kaydi denetlenemedi: HEAD okunamadi.")
    if not agac.strip():
        return ""
    metin = _git("cat-file", "blob", f"HEAD:{goreli}")
    if metin is None:
        raise OnayOrtamiHatasi(f"Onay kaydi denetlenemedi: HEAD:{goreli} okunamadi.")
    return metin


def _gecmis_kaydi() -> str:
    """Kayda git gecmisinde bir kez eklenmis butun satirlar: butun referanslar (`--all`, stash dahil) ve reflog
    (`--reflog`; `--amend`, `rebase`, `reset` ile birakilan commit'ler dahil). `--full-history` (kapanisin son
    turu): tek tarafa cozulen bir birlestirmenin ikinci ebeveynindeki kayit commit'leri de yurunur; varsayilan
    tarih sadelestirmesi onlari atliyordu (denetci OK2 D-B2, OK3 D-B3). Sahte git kipinde calisma agacindaki metin."""
    if _sahte_git():
        return _kaydi_oku()
    cikti = _git("log", "--all", "--reflog", "--full-history", "-p", "--no-color", "--no-ext-diff", "--no-textconv",
                 "--format=", "--", _kayit_goreli())
    if cikti is None:
        raise OnayOrtamiHatasi("Onay kaydi denetlenemedi: git gecmisi okunamadi.")
    return gecmis_satirlari(cikti)


def _kayit_commitli_denetle() -> None:
    """Calisma agacindaki onay satirlari HEAD'dekilerle ayni olmali; degilse `OnayKaydiCommitsiz`."""
    agac, head = onay_satirlari(_kaydi_oku()), onay_satirlari(_head_kaydi())
    if agac != head:
        eksik, fazla = [s for s in head if s not in agac], [s for s in agac if s not in head]
        raise OnayKaydiCommitsiz(
            f"Onay kaydinin calisma agacindaki satirlari HEAD'dekiyle ayni degil: {len(fazla)} commit edilmemis, "
            f"{len(eksik)} silinmis satir. Commit edilmemis kayit satiri varken yeni kosu acilmaz; once kaydi "
            "commit edin (silinen satirlar commit edilmis kayittan geri alinmali).")


def _kaydi_commit_et(mesaj: str) -> None:
    """Kayit dosyasini (yalnizca onu) commit eder; sonra HEAD'deki onay satirlari calisma agacindakilerle ayni
    olmali. Olmazsa `OnayKaydiCommitsiz`. Sahte git kipinde bir sey yapmaz."""
    if _sahte_git():
        return
    goreli = _kayit_goreli()
    if _git("add", "--", goreli) is None or _git("commit", "--only", "--quiet", "-m", mesaj, "--", goreli) is None:
        # D-B4 (RESULTS §14.46): git ortami global/sistem yapilandirmasini okumaz; kimlik yalnizca deponun yerel
        # yapilandirmasindan gelir. Eksikse hata bunu acikca soyler.
        eksik = [a for a in ("user.name", "user.email") if not (_git("config", "--local", "--get", a) or "").strip()]
        neden = (f" Deponun yerel yapilandirmasinda {'/'.join(eksik)} yok (git ortami global ve sistem yapilandirmasini "
                 "okumaz; `git config --local user.name ...` ile ekleyin, `python -m data.split git-hazirlik` ile "
                 "denetleyin)." if eksik else "")
        raise OnayKaydiCommitsiz(f"Onay kaydi commit edilemedi ({mesaj}).{neden} Kayit satiri calisma agacinda; elle "
                                 "commit edilmeden yeni kosu acilmaz.")
    _kayit_commitli_denetle()


# --- Kaydin uzak depodaki hali (onay kaydi kapanis turu) ---------------------


def _uzagi_getir() -> None:
    """`origin/main`'i alir. Alinamazsa (ag yok, uzak depo yok, kimlik bilgisi yok) `OnayUzakHatasi`; yerel kipe
    dusulmez. Sahte git kipinde bir sey yapmaz."""
    if _sahte_git():
        return
    if _git("fetch", "--quiet", "--no-tags", UZAK_DEPO, f"+refs/heads/{UZAK_DAL}:{_UZAK_REF}", sure=_AG_SURESI) is None:
        raise OnayUzakHatasi(f"{UZAK_DEPO}/{UZAK_DAL} alinamadi (ag yok ya da uzak depoya erisilemiyor). Onay kosusu "
                             "yalnizca uzak depoya baglanabildiginde acilir; yerel kipe dusulmez.")


def _uzak_gecmis_kaydi() -> str:
    """`origin/main` gecmisinde kayda bir kez eklenmis butun satirlar (`--full-history`: birlestirmelerin butun
    ebeveynleri). Sahte git kipinde calisma agacindaki metin."""
    if _sahte_git():
        return _kaydi_oku()
    cikti = _git("log", _UZAK_REF, "--full-history", "-p", "--no-color", "--no-ext-diff", "--no-textconv",
                 "--format=", "--", _kayit_goreli())
    if cikti is None:
        raise OnayUzakHatasi(f"{UZAK_DEPO}/{UZAK_DAL} gecmisi okunamadi.")
    return gecmis_satirlari(cikti)


def _itilmemis_denetle() -> None:
    """HEAD'deki kayitta `origin/main`'e itilmemis onay satiri varsa `OnayUzakHatasi`. Sahte git kipinde bir sey
    yapmaz."""
    if _sahte_git():
        return
    uzak = set(onay_satirlari(_uzak_gecmis_kaydi()))
    itilmemis = [s for s in onay_satirlari(_head_kaydi()) if s not in uzak]
    if itilmemis:
        raise OnayUzakHatasi(
            f"Onay kaydinda {UZAK_DEPO}/{UZAK_DAL}'e itilmemis {len(itilmemis)} satir var (ornek: {itilmemis[0]}). "
            "Itilmemis kayit satiri varken yeni kosu acilmaz; once kaydi itin.")


def _ileri_sarma_denetle() -> None:
    """HEAD `origin/main`'i icermiyorsa (kayit commit'i ileri sarma olarak itilemez) `OnayUzakHatasi`. Tek atis
    denetiminden sonra cagrilir: harcanmis cift once `OnayTekrari` verir. Sahte git kipinde bir sey yapmaz."""
    if _sahte_git():
        return
    if _git("merge-base", "--is-ancestor", _UZAK_REF, "HEAD") is None:
        raise OnayUzakHatasi(f"HEAD {UZAK_DEPO}/{UZAK_DAL}'i icermiyor; kosunun kayit commit'leri ileri sarma olarak "
                             "itilemez. Once uzak depoyla birlestirin.")


def _kaydi_it() -> bool:
    """HEAD'i `origin/main`'e iter (yalnizca ileri sarma; zorla itme yok). Basarida True. Sahte git kipinde True."""
    if _sahte_git():
        return True
    return _git("push", "--quiet", UZAK_DEPO, f"HEAD:refs/heads/{UZAK_DAL}", sure=_AG_SURESI) is not None


def uzak_adresi_normal(adres: str) -> str:
    """Uzak depo adresinin karsilastirma bicimi: `github.com/<sahip>/<depo>` (kucuk harf, `.git` ve sondaki `/`
    olmadan). https (`https://[kullanici@]github.com/...`), ssh (`ssh://git@github.com/...`) ve scp bicimi
    (`git@github.com:...`) ayni bicime iner; baska bicimler oldugu gibi (kucuk harf) doner. Saf."""
    a = adres.strip()
    a = re.sub(r"^[a-z+]+://", "", a, flags=re.I)  # sema
    a = re.sub(r"^[^@/]+@", "", a)  # kullanici
    a = re.sub(r"^([^/:]+):(?!\d)", r"\1/", a)  # scp bicimi host:yol
    a = re.sub(r"^([^/:]+):\d+/", r"\1/", a)  # port
    a = a.rstrip("/")
    a = a[:-4] if a.lower().endswith(".git") else a
    return a.lower()


def _uzak_adresi_denetle() -> None:
    """`origin`in okuma adresi ve butun itme adresleri (`insteadOf`, `pushurl`, `GIT_CONFIG_*` dahil, git'in
    cozdugu hali) beklenen depo olmali: `config.UZAK_DEPO_ADRESI` (test deposu kipinde testin ciplak deposu).
    Degilse `OnayUzakHatasi`: kayit baska bir depoya itilmez. Sahte git kipinde bir sey yapmaz."""
    if _sahte_git():
        return
    okuma = _git("remote", "get-url", UZAK_DEPO)
    itme = _git("remote", "get-url", "--push", "--all", UZAK_DEPO)
    if okuma is None or itme is None:
        raise OnayUzakHatasi(f"`{UZAK_DEPO}` uzak deposu tanimli degil.")
    adresler = [a for a in [okuma.strip(), *itme.split()] if a]
    test = _test_ayari()
    if test is not None and test.uzak is not None:
        def dogru(a: str) -> bool:
            try:
                return Path(a).resolve() == test.uzak.resolve()
            except (OSError, ValueError):
                return False
        beklenen = str(test.uzak)
    else:
        def dogru(a: str) -> bool:
            return uzak_adresi_normal(a) == config.UZAK_DEPO_ADRESI.lower()
        beklenen = config.UZAK_DEPO_ADRESI
    yanlis = [a for a in adresler if not dogru(a)]
    if yanlis:
        raise OnayUzakHatasi(f"`{UZAK_DEPO}` beklenen depoya ({beklenen}) gitmiyor: {yanlis}. Onay kaydi yalnizca "
                             "beklenen uzak depoya itilir; kosu acilmaz.")


def _itme_denemesi(kimlik: str) -> None:
    """Kosu acilmadan (kayda satir yazilmadan) itme yetenegini dener: bos bir deneme commit'i
    (`ONAY_KAYDI: itme denemesi (kosu=...)`) olusturup `origin/main`'e iter. Deneme commit'i her zaman gercek bir
    guncellemedir; kimlik bilgisi, dal korumasi ve uzak kancalar sinanir. Itilemezse yerel deneme commit'i geri
    alinir (`reset --soft HEAD~1`; agac temiz oldugu icin kayip yok) ve `OnayUzakHatasi`: kosu acilmaz, kayda satir
    yazilmaz, cift harcanmaz. Sahte git kipinde bir sey yapmaz."""
    if _sahte_git():
        return
    once = _git("rev-parse", "HEAD")
    if once is None or _git("commit", "--allow-empty", "--quiet", "-m",
                            f"ONAY_KAYDI: itme denemesi (kosu={kimlik})") is None:
        raise OnayUzakHatasi("Itme denemesi icin bos commit olusturulamadi; kosu acilmadi.")
    if _kaydi_it():
        return
    geri = _git("reset", "--soft", "--quiet", once.strip())
    raise OnayUzakHatasi(
        f"Itme denemesi basarisiz: {UZAK_DEPO}/{UZAK_DAL}'e itilemiyor (kimlik bilgisi, dal korumasi, uzak kanca ya da "
        "ag). Kosu acilmadi, kayda satir yazilmadi, cift harcanmadi."
        + ("" if geri is not None else " UYARI: yerel deneme commit'i geri alinamadi; HEAD'i elle duzeltin."))


def harcanan_ciftler() -> set[tuple[str, str]]:
    """Harcanmis (hipotez, kume) ciftleri: calisma agacindaki kayit, yerel git gecmisinde (OK D-B1) ve
    `origin/main` gecmisinde (kapanis turu) kayda bir kez eklenmis satirlarin birlesimi."""
    ciftler = kayittaki_kosular(_kaydi_oku()) | kayittaki_kosular(_gecmis_kaydi())
    if not _sahte_git():
        ciftler |= kayittaki_kosular(_uzak_gecmis_kaydi())
    return ciftler


def _hipotez_dogrula(hipotez) -> str:
    """Hipotez adi sabit degerlerden biri olmali (`config.HIPOTEZLER`), tam `str` turunde (kapi sertlestirme
    turu 3, denetci KS2 D-B1): serbest metin ("h2", "H2_b", "HTEST") tek atis anahtarini atlatirdi."""
    if type(hipotez) is not str or hipotez not in config.HIPOTEZLER:
        raise ValueError(f"Hipotez adi {config.HIPOTEZLER} degerlerinden biri olmali: {hipotez!r}")
    return hipotez


def _onay_kumesi_dogrula(kume) -> str:
    """Onay kumesi sabit degerlerden biri olmali (`config.ONAY_KUMELERI`), tam `str` turunde."""
    if type(kume) is not str or kume not in config.ONAY_KUMELERI:
        raise ValueError(f"{kume!r} bir onay kumesi degil: {config.ONAY_KUMELERI}")
    return kume


def _sonuc_dogrula(sonuc) -> str:
    """Kosu sonucu tek satirlik bir metin. Deger kumesi kodda sabitlenmedi: on-kayit §9 GECTI ve YETERSIZ GUC'u
    hipotez hukmu olarak tanimliyor, kume basina kosu sonucunun etiketini tanimlamiyor (kural 0; tur raporu)."""
    if type(sonuc) is not str:
        raise TypeError(f"Kosu sonucu str olmali: {sonuc!r}")
    if not sonuc or " ".join(sonuc.split()) != sonuc or "|" in sonuc or len(sonuc) > _SONUC_AZAMI_UZUNLUK:
        raise ValueError(f"Kosu sonucu bos olmayan, tek bosluklu, '|' icermeyen ve en fazla "
                         f"{_SONUC_AZAMI_UZUNLUK} karakterlik bir metin olmali: {sonuc!r}")
    return sonuc


def _onay_kaydet(eski: str, satir: str) -> None:
    """Kayit tablosuna BIR satir ekler; mevcut satirlar bayt bayt korunur (CLAUDE.md §3.3). Cagiran
    `_kayit_kilidi` icinde `eski`yi az once okumus olmalidir. Yol yalnizca `_kayit_yolu`ndan gelir."""
    hedef = _kayit_yolu()
    yeni = kayda_satir_ekle(eski, satir)

    # Yalnizca ekleme guvencesi: eklenen satir cikarilinca eski metin aynen kalmali.
    eski_satirlar = eski.splitlines()
    yeni_satirlar = yeni.splitlines()
    yeni_satirlar.remove(satir)
    if yeni_satirlar != eski_satirlar:
        raise RuntimeError("Onay kaydi yazimi mevcut satirlari degistirecekti; yazilmadi.")

    gecici = hedef.with_name(hedef.name + ".tmp")
    with gecici.open("w", encoding="utf-8", newline="") as dosya:
        dosya.write(yeni)
    gecici.replace(hedef)


# --- Onay kosusu ---------------------------------------------------------------


@dataclass(frozen=True)
class _Kosu:
    hipotez: str
    kume: str
    kimlik: str
    commit: str
    betik: str
    baslangic: str
    surec: int
    # F2'nin kilitledigi yapilandirma (on-kayit §8 madde 5): koşu acilirken okunur ve kosu
    # boyunca pozisyonlarin yapilandirmasiyla eslestirilir (`onay_baglami_dogrula`).
    kilit: KilitKaydi | None = None

    def satir(self, alanlar: str) -> str:
        return (f"| {_tablo_zamani()} | {self.kume} | {self.betik} | {self.commit} (temiz) | "
                f"hipotez={self.hipotez} kosu={self.kimlik} surec={self.surec} {alanlar} |")


_AKTIF_KOSU: _Kosu | None = None


def _acik_kosu() -> _Kosu | None:
    """Acik onay kosusu; kayit dosyasinda dogrulanmis. Kosu yoksa None.

    Kosu durumu bellekte kurulmus olabilir (ör. `vars(split)` ile); bu yuzden her erisimde kayitta kosunun
    tek bir BASLADI satiri olmali, kosu kapanmamis olmali ve satirdaki surec bu surec olmali (denetci KS3 D-B1,
    sizinti testcisi N-1). Surec sarti, cokmus bir kosunun asili kalan BASLADI satirinin baska bir surecte
    bellekte kurulan bir kosuyla yeniden kullanilmasini engeller."""
    kosu = _AKTIF_KOSU
    if kosu is None:
        return None
    if type(kosu) is not _Kosu:
        raise OnayKorumasi(f"Onay kosusu durumu gecersiz: {kosu!r}. Kosu yalnizca `onay_kosusu` ile acilir.")
    satirlar = [s for s in kayit_satirlari(_kaydi_oku()) if s.get("kosu") == kosu.kimlik]
    if (len(satirlar) != 1 or satirlar[0].get("durum") != "BASLADI" or satirlar[0]["hipotez"] != kosu.hipotez
            or satirlar[0]["kume"] != kosu.kume or satirlar[0].get("surec") != str(os.getpid())
            or kosu.surec != os.getpid()):
        raise OnayGerekli(
            f"Acik kosu ({kosu.hipotez}, {kosu.kume}, kosu={kosu.kimlik}) onay kaydinda acik degil: kayitta bu "
            "kosunun bu surece ait tek bir BASLADI satiri olmali ve kosu kapanmamis olmali.")
    return kosu


def aktif_onay_kosusu() -> tuple[str, str] | None:
    """Acik onay kosusu varsa (hipotez, kume); kayitta dogrulanmis."""
    kosu = _acik_kosu()
    return None if kosu is None else (kosu.hipotez, kosu.kume)


def onay_baglami_dogrula(hipotez: str, kume: str, yapilandirma: str | None = None) -> None:
    """Karar noktasinin onay baglami (kapi sertlestirme turu 3, denetci KS2 D-B1): C1/C2 pozisyonu yalnizca
    ayni (hipotez, kume) ciftinin acik onay kosusu icinde; acik bir onay kosusu varken baska hicbir
    (hipotez, kume) pozisyonu, KESIF dahil, olusturulamaz. Uyusmazlik `OnayUyusmazligi`.

    `yapilandirma` (yapilandirma KIMLIGI) verilirse acik kosunun KILIT.md'deki yapilandirmasiyla
    eslestirilir (on-kayit §8 madde 5, rev.13: "Onay kosusu, kostugu hipotezin yapilandirmasini bu
    dosyadan okur"). Boylece onay kosusu icinde baska bir yapilandirmanin pozisyonu olusturulamaz:
    F3 yalnizca F2'nin kilitledigi yapilandirmayi kosar (§9: "Secilen yapilandirma C1 ve C2'de birer
    kez kosulur")."""
    if kume in config.ONAY_KUMELERI or _AKTIF_KOSU is not None:
        aktif = aktif_onay_kosusu()
        if aktif != (hipotez, kume):
            raise OnayUyusmazligi(
                f"Pozisyon ({hipotez}, {kume}) acik onay kosusuyla ({aktif}) eslesmiyor. C1/C2 pozisyonu yalnizca "
                f"`with split.onay_kosusu({hipotez!r}, {kume!r}):` icinde; acik kosu varken baska pozisyon "
                "olusturulamaz.")
        kosu = _acik_kosu()
        kilit = None if kosu is None else kosu.kilit
        if yapilandirma is not None and kilit is not None and kilit.yapilandirma != yapilandirma:
            raise OnayUyusmazligi(
                f"Pozisyonun yapilandirmasi ({yapilandirma}) {hipotez} icin KILIT.md'de kilitlenen "
                f"yapilandirmayla ({kilit.yapilandirma}) eslesmiyor. Onay kosusu yalnizca F2'nin sectigi "
                "yapilandirmayi kosar (on-kayit §8 madde 5, §9).")


class OnayKosusu:
    """`onay_kosusu` blogunun tutamagi. Kosunun sonucu blok icinde `sonuc_bildir` ile bir kez bildirilir."""

    __slots__ = ("_kosu", "_sonuc", "_acik")

    def __init__(self, kosu: _Kosu):
        self._kosu = kosu
        self._sonuc: str | None = None
        self._acik = True

    hipotez = property(lambda self: self._kosu.hipotez)
    kume = property(lambda self: self._kosu.kume)
    kimlik = property(lambda self: self._kosu.kimlik)
    commit = property(lambda self: self._kosu.commit)
    sonuc = property(lambda self: self._sonuc)

    def sonuc_bildir(self, sonuc: str) -> None:
        if not self._acik or _AKTIF_KOSU is not self._kosu:
            raise RuntimeError("Sonuc yalnizca acik kosunun blogu icinde bildirilir.")
        if self._sonuc is not None:
            raise RuntimeError(f"Kosunun sonucu zaten bildirildi: {self._sonuc}")
        self._sonuc = _sonuc_dogrula(sonuc)


def _it_ya_da_kaydet(kosu: _Kosu, asama: str) -> OnayUzakHatasi | None:
    """Kayit commit'ini `origin/main`'e iter. Itilemezse kayda `durum=ITILEMEDI asama=<...>` satiri yazar ve yerelde
    commit eder (commit de olmazsa satir calisma agacinda kalir); donen hata cagiranca firlatilir. `_kayit_kilidi`
    icinde cagrilir. Itilmemis satir varken yeni kosu acilmaz (`_itilmemis_denetle`)."""
    if _kaydi_it():
        return None
    _onay_kaydet(_kaydi_oku(), kosu.satir(f"durum=ITILEMEDI asama={asama} zaman={_iso_zaman()}"))
    try:
        _kaydi_commit_et(f"ONAY_KAYDI: {kosu.hipotez} {kosu.kume} ITILEMEDI ({asama}, kosu={kosu.kimlik})")
    except OnayKaydiCommitsiz:
        pass
    return OnayUzakHatasi(
        f"Onay kosusunun ({kosu.hipotez}, {kosu.kume}, kosu={kosu.kimlik}) {asama} kaydi {UZAK_DEPO}/{UZAK_DAL}'e "
        "itilemedi; kayda ITILEMEDI yazildi. Bunu kosu raporuna yazin ve kaydi elle itin "
        f"(`git push {UZAK_DEPO} {UZAK_DAL}`); itilmeden yeni kosu acilmaz.")


def _bitis_yaz(kosu: _Kosu, durum: str, alan: str) -> None:
    """Kosunun bitis satirini yazar (BITTI ya da HATA), commit eder ve iter. Kayitta kosunun tek bir BASLADI satiri
    yoksa satir yine yazilir (iz kalir), sonra `OnayKorumasi`. Itilemezse `OnayUzakHatasi` (kayitta ITILEMEDI)."""
    commit_hatasi: OnayKaydiCommitsiz | None = None
    uzak_hatasi: OnayUzakHatasi | None = None
    with _kayit_kilidi():
        eski = _kaydi_oku()
        onceki = [s.get("durum") for s in kayit_satirlari(eski) if s.get("kosu") == kosu.kimlik]
        _onay_kaydet(eski, kosu.satir(f"durum={durum} baslangic={kosu.baslangic} bitis={_iso_zaman()} {alan}"))
        try:
            _kaydi_commit_et(f"ONAY_KAYDI: {kosu.hipotez} {kosu.kume} {durum} (kosu={kosu.kimlik})")
        except OnayKaydiCommitsiz as yakalanan:
            commit_hatasi = yakalanan
        else:
            uzak_hatasi = _it_ya_da_kaydet(kosu, durum)
    if onceki != ["BASLADI"]:
        raise OnayKorumasi(f"Onay kaydinda kosu {kosu.kimlik} icin beklenen tek BASLADI satiri yerine {onceki} "
                           "bulundu; kayit kosu sirasinda degismis.") from (commit_hatasi or uzak_hatasi)
    if commit_hatasi is not None:
        raise commit_hatasi
    if uzak_hatasi is not None:
        raise uzak_hatasi


@contextmanager
def onay_kosusu(hipotez: str, kume: str):
    """Bir hipotez icin bir onay kumesinin TEK kosusunu acar (CLAUDE.md §3.3, on-kayit §9).

        with split.onay_kosusu("H2", "C1") as kosu:
            ...
            kosu.sonuc_bildir("...")

    - Calisma agacindaki kayit HEAD'dekiyle ayni degilse (commit edilmemis ya da silinmis kayit satiri)
      `OnayKaydiCommitsiz`.
    - Yalnizca temiz calisma agacinda ve git'te izlenen bir depo betiginden acilir (`OnayOrtamiHatasi`).
    - `origin/main` alinamazsa (ag yok), HEAD'deki kayitta itilmemis satir varsa ya da HEAD `origin/main`'i
      icermiyorsa `OnayUzakHatasi`; yerel kipe dusulmez.
    - Ayni (hipotez, kume) calisma agacindaki kayitta, yerel git gecmisinde ya da `origin/main` gecmisinde kayda
      bir kez eklenmisse, hangi durumda olursa olsun, `OnayTekrari`; hicbir sey yazilmaz.
    - Acilirken kayda BASLADI satiri: tarih, kume, betik, commit hash'i, hipotez, kosu kimligi, surec numarasi,
      UTC baslangic. Satir hemen commit edilir ve itilir; commit edilemezse (`OnayKaydiCommitsiz`) ya da
      itilemezse (`OnayUzakHatasi`, kayitta ITILEMEDI) kosu acilmaz.
    - Kapanirken kayda bitis satiri (o da commit edilir ve itilir; itilemezse kayitta ITILEMEDI ve
      `OnayUzakHatasi`): UTC baslangic ve bitis ile
        - sonuc bildirildiyse `durum=BITTI sonuc=<sonuc>`;
        - blok hata ile biterse `durum=HATA hata=<hata sinifi>`, sonuc bildirilmisse ardindan `sonuc=<sonuc>`
          (hata yeniden firlatilir);
        - sonuc bildirilmediyse `durum=HATA hata=OnaySonucuYok` ve `OnaySonucuYok`.
    - Ic ice kosu acilamaz. Kayit yolu parametre olarak verilemez.
    """
    global _AKTIF_KOSU
    _hipotez_dogrula(hipotez)
    _onay_kumesi_dogrula(kume)
    if _AKTIF_KOSU is not None:
        raise RuntimeError(f"Zaten acik bir onay kosusu var: {_AKTIF_KOSU}. Ic ice kosu acilamaz.")
    # F2'nin secimi onay kosusundan ONCE okunur (on-kayit §8 madde 5, rev.13): "dosyada kaydi
    # olmayan ya da hukmu 'hipotez kapandi' olan bir hipotez icin onay kosusu acilmaz". Hicbir sey
    # yazilmadan once denetlenir, boylece kapanmis bir hipotez icin cift HARCANMAZ (madde 4).
    kilit = kilit_oku(hipotez)
    if not kilit.secildi:
        raise HipotezKapandi(
            f"{hipotez} KILIT.md'de kapanmis: hukum={kilit.hukum!r}, gerekce={kilit.gerekce!r}. Secilecek "
            "yapilandirma yoktur ve onay verisi harcanmaz (on-kayit §8 madde 4-5).")
    _kayit_commitli_denetle()
    ortam = _kosu_ortami()  # yerel denetimler once: ag islemi yalnizca temiz, izlenen bir ortamda
    _uzak_adresi_denetle()
    _uzagi_getir()
    _itilmemis_denetle()
    from data import binance_vision as bv
    from data import onbellek_manifest

    # Dondurma kaydi tam dogrulanir (on-kayit §3 rev.13; RESULTS §14.41). Kayda satir yazilmadan once: uyusmazlikta kosu
    # acilmaz, cift harcanmaz. Onay baytlari yalnizca `hashlib` ile okunur.
    if onbellek_manifest.denetim_etkin():
        with bv.onay_verisi_izni(f"split.onay_kosusu acilisi ({hipotez}, {kume})"):
            onbellek_manifest.manifest_dogrula(katman="tam")
    kosu = _Kosu(hipotez, kume, uuid.uuid4().hex[:12], ortam.commit, ortam.betik, _iso_zaman(), os.getpid(),
                 kilit)
    with _kayit_kilidi():
        eski = _kaydi_oku()
        if (hipotez, kume) in harcanan_ciftler():
            raise OnayTekrari(
                f"{hipotez} icin {kume} onay kosusu zaten kayitli (calisma agacinda, yerel git gecmisinde ya da "
                f"{UZAK_DEPO}/{UZAK_DAL} gecmisinde). Onay kumeleri her hipotez icin BIR KEZ kosulur "
                "(CLAUDE.md §3.3, on-kayit §9).")
        _ileri_sarma_denetle()
        _itme_denemesi(kosu.kimlik)  # itilemiyorsa kosu acilmaz, satir yazilmaz, cift harcanmaz
        _onay_kaydet(eski, kosu.satir(f"durum=BASLADI baslangic={kosu.baslangic}"))
        _kaydi_commit_et(f"ONAY_KAYDI: {hipotez} {kume} BASLADI (kosu={kosu.kimlik})")
        uzak_hatasi = _it_ya_da_kaydet(kosu, "BASLADI")
    if uzak_hatasi is not None:
        raise uzak_hatasi

    tutamak = OnayKosusu(kosu)
    # Acilis ve kapanis bellekteki kopyalari gecersiz kilar (on-kayit §3 rev.13). Isabetteki denetim
    # (`onay_erisimi_denetle`) bundan bagimsiz calisir.
    kume_bellegi.temizle()
    bv.donuk_bellek_temizle()
    # F3 kosusu aga cikmaz (on-kayit §3 rev.13). Yasak veri kaynaklarini kapsar: kaydin `git fetch` ve `git push`
    # adimlari `subprocess` ile calisir, veri katmanindan gecmez ve sonuca girdi saglamaz (RESULTS §14.40, §14.41).
    ag_yasagi = bv.kosu_agsiz()
    ag_yasagi.__enter__()
    _AKTIF_KOSU = kosu
    hata: BaseException | None = None
    try:
        yield tutamak
    except BaseException as yakalanan:
        hata = yakalanan
        raise
    finally:
        _AKTIF_KOSU = None
        tutamak._acik = False
        kume_bellegi.temizle()
        bv.donuk_bellek_temizle()
        ag_yasagi.__exit__(None, None, None)
        if hata is not None:
            # Sonuc bildirildikten sonra gelen hata: kayda hem hata hem sonuc (onay kaydi ikinci tur, OK D-C1).
            # `sonuc=` son alandir (`not_alanlari`).
            sonuc = "" if tutamak.sonuc is None else f" sonuc={tutamak.sonuc}"
            _bitis_yaz(kosu, "HATA", f"hata={type(hata).__name__}{sonuc}")
        elif tutamak.sonuc is None:
            _bitis_yaz(kosu, "HATA", f"hata={OnaySonucuYok.__name__}")
            raise OnaySonucuYok(f"Onay kosusu ({hipotez}, {kume}) sonuc bildirilmeden bitti; kayda HATA yazildi. "
                                "Cift harcandi (tek atis).")
        else:
            _bitis_yaz(kosu, "BITTI", f"sonuc={tutamak.sonuc}")


# --- Kesif kosusu --------------------------------------------------------------
#
# Commit bagi (RESULTS §14.42, denetci D-B2). Kesif kosusu acilirken manifest, bolme tablosu ve evren tablosunun calisma
# agacindaki hali HEAD'dekiyle ayni olmali: kosunun kullandigi dondurma kaydi ve bolme bir commit'e baglanir. Acilista
# manifestin SHA256'si sabitlenir; kapanista manifest yeniden ozetlenir ve kesif katmani yeniden dogrulanir. Kosucuya bir
# kayit nesnesi (`KesifKaydi`) verilir; F2 kosucusu onu sonuc dosyalarina yazar (F2 gereksinimi, §14.42). Resmi F2
# kosusunun temiz agac ve `origin/main` esitligi istemesi de F2 gereksinimidir: burada zorlanmaz, kayda yazilir.
#
# Test kipi: pytest icinde commit bagi yalnizca test gercek bir git deposu kurduysa (`_test_kaydi_ayarla(depo=...)`)
# denetlenir; sahte git kipinde ve test ayari yokken atlanir (`_sahte_git` ile ayni yaklasim). pytest disinda her zaman.


class KesifBagiHatasi(OnayOrtamiHatasi):
    """Kesif kosusu commit'e baglanamadi: manifest, split.csv ya da universe.csv HEAD'dekiyle ayni degil, izlenmiyor ya
    da git okunamadi; ya da kapanista manifest acilistakiyle ayni degil / kesif katmani artik dogrulanmiyor."""


class KesifKaydi:
    """Kesif kosusunun kaydi. Alanlar salt okunur; `kapanis_utc` kosu kapaninca dolar. F2 kosucusu bunu sonuc dosyalarina
    yazar (`alanlar()`)."""

    __slots__ = ("_head", "_manifest", "_temiz", "_kirli_sayisi", "_origin", "_origin_zamani", "_acilis", "_kapanis")

    def __init__(self, head, manifest_sha256, agac_temiz, origin_esit, acilis_utc, origin_ref_zamani=None,
                 agac_kirli_sayisi=None):
        self._head, self._manifest, self._temiz = head, manifest_sha256, agac_temiz
        self._kirli_sayisi = agac_kirli_sayisi
        self._origin, self._origin_zamani = origin_esit, origin_ref_zamani
        self._acilis, self._kapanis = acilis_utc, None

    head_commit = property(lambda self: self._head)
    manifest_sha256 = property(lambda self: self._manifest)
    agac_temiz = property(lambda self: self._temiz)
    # RESULTS §14.46: kirli kayit SAYISI (dosya adi degil); git okunamadiysa None.
    agac_kirli_sayisi = property(lambda self: self._kirli_sayisi)
    # D-K4 (RESULTS §14.43): esitlik yerel `refs/remotes/origin/main` ile, fetch YAPILMADAN olculur; deger o referansin
    # son guncellenme anina (reflog, UTC) gore anlamlidir. Resmi F2 kosusundan hemen once `git fetch` F2 kosucusunun isidir.
    origin_main_esit = property(lambda self: self._origin)
    origin_main_ref_zamani = property(lambda self: self._origin_zamani)
    acilis_utc = property(lambda self: self._acilis)
    kapanis_utc = property(lambda self: self._kapanis)

    def alanlar(self) -> dict:
        return {"head_commit": self._head, "manifest_sha256": self._manifest, "agac_temiz": self._temiz,
                "agac_kirli_sayisi": self._kirli_sayisi, "origin_main_esit": self._origin, "origin_main_ref_zamani": self._origin_zamani,
                "acilis_utc": self._acilis, "kapanis_utc": self._kapanis}

    def __repr__(self) -> str:
        return f"KesifKaydi({self.alanlar()})"


# Kesif baglami (RESULTS §14.42, denetci D-C1): KESIF karar noktasi (`pozisyon.olay_karari`, `pozisyon.sinyal_kosulu`)
# yalnizca acik bir kesif kosusu icinde calisir. Durum surece aittir ve `bv.kosu_agsiz` ile ayni yontemle alt sureclere
# tasinir (F2'de paralellik surecle yapilir; §14.40): baglam icinde baslatilan surec import aninda devralir, pid denetimi
# bayat ya da elle ayarlanmis degiskeni eler. Kural pytest icinde manifest denetimiyle ayni istisnaya tabidir: yalnizca
# testin kendi manifestini kurdugu testte uygulanir (`onbellek_manifest.denetim_etkin`; M-11 bu istisnayi atlatir).
_KESIF_ORTAM_ADI = "SHORT_LAB_KESIF_KOSUSU"
_KESIF_DURUMU = {"sayac": 0, "devralinan": False}


class KesifBaglamiYok(PermissionError):
    """KESIF karar noktasi acik bir `kesif_kosusu` disinda cagrildi (RESULTS §14.42, denetci D-C1)."""


def _kesif_baglamini_devral() -> None:
    """Import aninda bir kez: ust surec bir kesif kosusu icinde bu sureci baslattiysa baglam devralinir. Yan etkili."""
    deger = os.environ.get(_KESIF_ORTAM_ADI)
    if not deger or deger != str(os.getppid()):
        return
    _KESIF_DURUMU["devralinan"] = True
    os.environ[_KESIF_ORTAM_ADI] = str(os.getpid())


class _kesif_baglami:  # noqa: N801  (yalnizca `kesif_kosusu` acar)
    def __init__(self):
        self._onceki = None

    def __enter__(self):
        _KESIF_DURUMU["sayac"] += 1
        if _KESIF_DURUMU["sayac"] == 1:
            self._onceki = os.environ.get(_KESIF_ORTAM_ADI)
            os.environ[_KESIF_ORTAM_ADI] = str(os.getpid())
        return self

    def __exit__(self, *_):
        _KESIF_DURUMU["sayac"] -= 1
        if _KESIF_DURUMU["sayac"] == 0:
            if self._onceki is None:
                os.environ.pop(_KESIF_ORTAM_ADI, None)
            else:
                os.environ[_KESIF_ORTAM_ADI] = self._onceki
        return False


_kesif_baglamini_devral()


def kesif_kosusu_acik() -> bool:
    """Bu surecte acik (ya da devralinmis) bir kesif kosusu var mi."""
    return _KESIF_DURUMU["sayac"] > 0 or _KESIF_DURUMU["devralinan"]


def kesif_baglami_dogrula(kume) -> None:
    """KESIF karar noktasi acik bir kesif kosusu ister; yoksa `KesifBaglamiYok`. C1/C2 icin kural `onay_baglami_dogrula`
    dadir. pytest icinde yalnizca manifest denetimi etkin testte uygulanir (yukaridaki not)."""
    if kume != "KESIF":
        return
    from data import onbellek_manifest

    if not onbellek_manifest.denetim_etkin():
        return
    if not kesif_kosusu_acik():
        raise KesifBaglamiYok("KESIF karar noktasi (olay_karari, sinyal_kosulu) yalnizca `with split.kesif_kosusu():` "
                              "icinde cagrilir (RESULTS §14.42, denetci D-C1).")


def _kesif_git_denetimi() -> bool:
    """Commit bagi bu ortamda denetlenir mi: pytest disinda her zaman, pytest icinde yalnizca gercek git test deposunda."""
    if _pytest_testi() is None:
        return True
    test = _test_ayari()
    return test is not None and test.depo is not None


def _kesif_bagli_dosyalar() -> list[Path]:
    from data import onbellek_manifest

    return [onbellek_manifest._etkin_yol(), Path(config.SPLIT_CSV), Path(config.UNIVERSE_CSV)]


# Git cagrilarinin TEK ortam kurucusu (performans 2b-0, RESULTS §14.45; sizinti S-5, S-6, S-23, S-25, S-26, P-7, denetci
# D-C8). Bag (`kesif_bagi_denetle`), kesif kaydi (`_kesif_kaydi_kur`) ve onay kaydi (`_git`) bu ortami kullanir.
#   - Ortam BEYAZ LISTEYLE kurulur: yalnizca `_GIT_ORTAM_BEYAZ_LISTESI`ndeki surec degiskenleri gecer. Hicbir `GIT_*`
#     degiskeni ortamdan gecmez (depo, indeks, calisma agaci, nesne ve ortak dizin yonlendirmesi, `GIT_CONFIG_*` ile
#     ayar enjeksiyonu, ad alani).
#   - Sistem ve kullanici (global) yapilandirmasi okunmaz: `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=os.devnull`
#     (Windows'ta `nul`; git 2.41 ile sinandi). Yalnizca deponun kendi `.git/config`u okunur.
#   - `GIT_NO_REPLACE_OBJECTS=1` (yerel `git replace` referanslari nesne okumasini saptiramaz), `GIT_LITERAL_PATHSPECS=1`
#     (joker eslemesi yok), `GIT_TERMINAL_PROMPT=0`.
# SONUC (kullanicinin karari, RESULTS §14.45): onay kaydinin commit'i ve push'u global/sistem ayarindaki kimligi
# (`user.name`, `user.email`) ve kimlik bilgisi yardimcisini (`credential.helper`) artik gormez; onay kosusu bunlarin
# deponun yerel yapilandirmasinda bulunmasini ister. `core.autocrlf` da okunmaz.
_GIT_ORTAM_BEYAZ_LISTESI = ("PATH", "SYSTEMROOT", "USERPROFILE", "HOME", "TEMP", "TMP", "COMSPEC", "PATHEXT", "WINDIR",
                            "SYSTEMDRIVE")
_GIT_SABIT_ORTAM = {"GIT_NO_REPLACE_OBJECTS": "1", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_LITERAL_PATHSPECS": "1", "GIT_TERMINAL_PROMPT": "0"}
# Agac temizligi (S-25, S-26): izlenmeyen dosyalar komut satiriyla gosterilir; depo yapilandirmasi
# (`status.showUntrackedFiles=no`) bunu kapatamaz. `--ignored` kullanilmaz: `.gitignore`daki onbellek kirli sayilmaz.
_DURUM_KOMUTU = ("-c", "status.showUntrackedFiles=all", "status", "--porcelain", "--untracked-files=all")
# Izlenmeyen dosyalar YALNIZCA commit edilen `.gitignore` dosyalarina gore suzulur (RESULTS §14.46; S-31, S-32, S-33):
# `--exclude-standard` verilmedigi icin `.git/info/exclude`, yerel `core.excludesFile` (dogrudan ya da `include.path`
# ile) ve `$HOME/.config/git/ignore` yok sayilir (git 2.41 ile sinandi; `tests/test_agac_temizligi_tek_kaynak.py`).
_IZLENMEYEN_KOMUTU = ("ls-files", "--others", "--exclude-per-directory=.gitignore")


def _agac_kirlilikleri() -> list[str] | None:
    """Agac temizliginin TEK kaynagi (RESULTS §14.46; denetci D-B1, sizinti S-31, S-32, S-33). Kesif kaydi
    (`_kesif_kaydi_kur`) ve onay kosu ortami (`_kosu_ortami`) bunu kullanir. Uc denetim birlesir:
      - izlenen dosyalar: `_DURUM_KOMUTU` (`git status --porcelain --untracked-files=all`);
      - `--assume-unchanged` (kucuk harf etiket) ve `--skip-worktree` ("S") isaretli dosyalar: `git ls-files -v`;
      - izlenmeyen dosyalar: `_IZLENMEYEN_KOMUTU` (yalnizca `.gitignore`).
    Doner: kirli kayitlarin tekillestirilmis, sirali listesi (bos = temiz); git okunamazsa None (kapali yon). Liste
    cagirana yalnizca sayi olarak yansir: kesif kaydi ve onay hata mesaji dosya adi tasimaz. Sinir (kayitta kalir):
    depo-yerel `filter.*.clean`, `core.fsmonitor`, `diff.ignoreSubmodules` (S-34, S-35, S-36; `.git` ic dosyalarinin
    elle duzenlenmesini ister)."""
    durum = _git(*_DURUM_KOMUTU)
    isaretler = _git("ls-files", "-v")
    izlenmeyen = _git(*_IZLENMEYEN_KOMUTU)
    if durum is None or isaretler is None or izlenmeyen is None:
        return None
    kirli = {f"durum:{s[3:]}" if not s.startswith("??") else f"izlenmeyen:{s[3:]}" for s in durum.splitlines()
             if s.strip()}
    kirli |= {f"isaret:{s[2:]}" for s in isaretler.splitlines() if s and (s[:1].islower() or s[:1] == "S")}
    kirli |= {f"izlenmeyen:{s}" for s in izlenmeyen.splitlines() if s.strip()}
    return sorted(kirli)


def agac_kirli_sayisi() -> int | None:
    """Agac temizliginin TEK kaynaginin (`_agac_kirlilikleri`) analiz kodu icin acik sarmalayicisi (RESULTS §14.48,
    D-C2). Yalnizca SAYI doner (0 = temiz), dosya adi donmez; git okunamazsa None. F1 denetim betiklerinin ortam
    kaydi (`calistir.git_durumu`) bunu kullanir; kesif kaydi ve onay kosusuyla ayni hukmu verir."""
    kirli = _agac_kirlilikleri()
    return None if kirli is None else len(kirli)


def _bag_ortami() -> dict[str, str]:
    """Butun git cagrilarinin ortami (beyaz liste + sabit degiskenler)."""
    izinli = set(_GIT_ORTAM_BEYAZ_LISTESI)
    ortam = {k: v for k, v in os.environ.items() if k.upper() in izinli}
    ortam.update(_GIT_SABIT_ORTAM)
    return ortam


def _git_tani(*argumanlar: str, sure: int = 30) -> tuple[int | None, str]:
    """`git-hazirlik` tanisinin git cagrisi: ayni beyaz listeli ortam (`_bag_ortami`). Doner: (cikis kodu, stderr'in
    son satiri); calistirilamazsa (None, hata sinifi)."""
    try:
        cikti = subprocess.run(["git", *argumanlar], cwd=_depo(), capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=sure, env=_bag_ortami())
    except Exception as hata:
        return None, type(hata).__name__
    satirlar = [s for s in cikti.stderr.strip().splitlines() if s.strip()]
    return cikti.returncode, satirlar[-1].strip() if satirlar else ""


def _eposta_maskele(deger: str) -> str:
    yerel, at, alan = deger.partition("@")
    return f"{yerel[:1]}***@{alan}" if at else "***"


def git_hazirlik() -> int:
    """Tani komutu (`python -m data.split git-hazirlik`; RESULTS §14.46, D-B4). Onay kosusunun git islemlerinin bu
    makinede calisip calismayacagini, onay kosusuyla AYNI beyaz listeli ortamla sinar:
      - `git config --local --get` ile `user.name`, `user.email` (maskeli yazilir), `credential.helper`;
      - `git fetch` (onay kosusunun refspec'iyle; yalnizca `refs/remotes/origin/main` guncellenir);
      - `git push --dry-run origin main` (hicbir sey itilmez; kimlik bilgisi yardimcisi sinanir).
    Onay kosusu ACMAZ, kayda dokunmaz, commit yapmaz. Analiz kodunda adi taramayla yasaktir
    (`tests/tarama_yardimcisi.ONAY_ATLATMA_DESENI`). Doner: hepsi tamamsa 0, degilse 1."""
    tamam = True
    print(f"git-hazirlik: depo {_depo()}; ortam beyaz listeli ({', '.join(_GIT_ORTAM_BEYAZ_LISTESI)}), global ve "
          "sistem yapilandirmasi okunmaz")
    for anahtar in ("user.name", "user.email", "credential.helper"):
        deger = (_git("config", "--local", "--get", anahtar) or "").strip()
        if not deger:
            tamam = False
            print(f"  {anahtar}: YOK (deponun yerel yapilandirmasinda)")
        else:
            print(f"  {anahtar}: {_eposta_maskele(deger) if anahtar == 'user.email' else deger}")
    for ad, komut in (("fetch", ("fetch", "--quiet", "--no-tags", UZAK_DEPO, f"+refs/heads/{UZAK_DAL}:{_UZAK_REF}")),
                      ("push --dry-run", ("push", "--dry-run", UZAK_DEPO, UZAK_DAL))):
        kod, son = _git_tani(*komut, sure=_AG_SURESI)
        tamam = tamam and kod == 0
        print(f"  {ad}: {'TAMAM' if kod == 0 else 'BASARISIZ'} (cikis {kod}){': ' + son if son else ''}")
    print(f"git-hazirlik: {'TAMAM' if tamam else 'EKSIK'}")
    return 0 if tamam else 1


def _bag_git(*argumanlar: str, sure: int = 30) -> str | None:
    """Kesif kaydinin metin ciktili git cagrilari (`_bag_ortami`). Hata ya da sifirdan farkli cikis kodunda None."""
    try:
        cikti = subprocess.run(["git", "--no-replace-objects", *argumanlar], cwd=_depo(), capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=sure, env=_bag_ortami())
    except Exception:
        return None
    return cikti.stdout if cikti.returncode == 0 else None


def _git_bayt(*argumanlar: str, sure: int = 30) -> bytes | None:
    """Git ciktisini BAYT olarak doner (`cat-file blob`); pathspec'ler her zaman literal (`GIT_LITERAL_PATHSPECS=1`,
    sizinti F-4); replace referanslari yok sayilir ve depo yonlendiren ortam degiskenleri suzulur (`_bag_ortami`; S-5,
    S-6). Hata ya da sifirdan farkli cikis kodunda None."""
    ortam = _bag_ortami()
    argumanlar = ("--no-replace-objects", *argumanlar)
    try:
        cikti = subprocess.run(["git", "--literal-pathspecs", *argumanlar], cwd=_depo(), capture_output=True,
                               timeout=sure, env=ortam)
    except Exception:
        return None
    return cikti.stdout if cikti.returncode == 0 else None


def kesif_bagi_denetle() -> dict[str, str]:
    """Bagli dosyalari (manifest, split.csv, universe.csv) HEAD'e BAYT duzeyinde baglar (RESULTS §14.43; sizinti F-1..F-4,
    denetci D-K3). Her dosya icin:
      - calisma agacindaki baytlar BIR KEZ okunur;
      - `git --literal-pathspecs ls-files --error-unmatch` ile izlendigi (joker karakter eslemesi yok) ve
        `git cat-file blob HEAD:<yol>` ile HEAD'deki baytlari alinir;
      - iki baytin SHA256'si esit olmali; degilse `KesifBagiHatasi`.
    `git diff`e dayanilmaz: `--assume-unchanged` / `--skip-worktree` bayraklari ve `core.autocrlf` donusumu git'in
    "temiz" hukmunu degistirir, baytlari degistirmez. Doner: dosya yolu -> sabitlenen SHA256 (ayni okumadan). Git
    okunamazsa da hata (kapali yon)."""
    depo = _depo().resolve()
    sabit: dict[str, str] = {}
    for yol in _kesif_bagli_dosyalar():
        if yol is None:
            raise KesifBagiHatasi("Kesif kosusu manifest olmadan commit'e baglanamaz.")
        try:
            goreli = Path(yol).resolve().relative_to(depo).as_posix()
        except ValueError:
            raise KesifBagiHatasi(f"{yol} git deposunun ({depo}) icinde degil; kesif kosusu commit'e baglanamaz.") from None
        try:
            calisma = Path(yol).read_bytes()  # tek okuma: karsilastirma ve sabitleme bundan
        except OSError as hata:
            raise KesifBagiHatasi(f"{goreli} okunamadi: {hata}") from None
        if _git_bayt("ls-files", "--error-unmatch", "--", goreli) is None:
            raise KesifBagiHatasi(f"{goreli} git'te izlenmiyor; kesif kosusu commit'e baglanamaz (RESULTS §14.43).")
        head = _git_bayt("cat-file", "blob", f"HEAD:{goreli}")
        if head is None:
            raise KesifBagiHatasi(f"HEAD:{goreli} okunamadi; kesif kosusu commit'e baglanamaz.")
        ozet = hashlib.sha256(calisma).hexdigest()
        if ozet != hashlib.sha256(head).hexdigest():
            raise KesifBagiHatasi(f"{goreli} calisma agacindaki baytlari HEAD'dekinden farkli; kesif kosusu acilmaz. Once "
                                  "commit edin (RESULTS §14.43, denetci D-B2).")
        sabit[str(yol)] = ozet
    return sabit


def _dosya_sha256(yol) -> str | None:
    try:
        return hashlib.sha256(Path(yol).read_bytes()).hexdigest()
    except OSError:
        return None


def _kesif_kaydi_kur(manifest_sha256: str | None) -> KesifKaydi:
    # Bagin ortami (S-5, S-6; RESULTS §14.44): kayit da bagla ayni depodan, replace referanslari yok sayilarak okunur.
    head = _bag_git("rev-parse", "HEAD")
    head = head.strip() if head is not None and re.fullmatch(r"[0-9a-f]{40}", head.strip()) else None
    # Agac temizligi tek kaynaktan (RESULTS §14.46; D-B1): `_agac_kirlilikleri` (status + ls-files -v + .gitignore'a
    # gore izlenmeyenler). Kayitta yalnizca sayi tutulur, dosya adi tutulmaz.
    kirli = _agac_kirlilikleri()
    temiz = None if kirli is None else not kirli
    kirli_sayisi = None if kirli is None else len(kirli)
    uzak = _bag_git("rev-parse", "--verify", "--quiet", _UZAK_REF)
    origin = None if head is None or uzak is None else uzak.strip() == head
    # Yerel referansin son guncellenme ani (reflog; D-K4). Fetch yapilmaz.
    secici = _bag_git("reflog", "-1", "--date=unix", "--format=%gd", _UZAK_REF)
    eslesme = re.search(r"@\{(\d+)\}", secici or "")
    zaman = (dt.datetime.fromtimestamp(int(eslesme.group(1)), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
             if eslesme else None)
    return KesifKaydi(head, manifest_sha256, temiz, origin, _iso_zaman(), origin_ref_zamani=zaman,
                      agac_kirli_sayisi=kirli_sayisi)


@contextmanager
def kesif_kosusu():
    """F2 kosucusunun giris noktasi (on-kayit §3 rev.13: "F2 ve F3 koşuları ağa çıkmaz"; RESULTS §14.41, §14.42).

        with split.kesif_kosusu() as kayit:
            ...
            sonuc_dosyasina_yaz(kayit.alanlar())

    `bv` analiz kodunda taramayla yasak oldugu icin kosucu ag yasagini ancak bu baglamla acar. Acilista commit bagi
    denetlenir (`kesif_bagi_denetle`), kesif katmani dogrulanir (hicbir onay dosyasi acilmaz), manifestin SHA256'si
    sabitlenir, bellek ve donuk liste kopyalari duser, surec duzeyinde ag yasagi acilir. Kapanista yasak kalkar, kopyalar
    duser, manifest yeniden ozetlenir ve kesif katmani yeniden dogrulanir; uyusmazlik `KesifBagiHatasi`. Tek atis ve onay
    kaydi yoktur: kesif serbesttir (CLAUDE.md §3.3). Acik bir onay kosusu icinde acilmaz."""
    from data import binance_vision as bv
    from data import onbellek_manifest

    if _AKTIF_KOSU is not None:
        raise RuntimeError(f"Acik onay kosusu icinde kesif kosusu acilamaz: {_AKTIF_KOSU}.")
    denetim = onbellek_manifest.denetim_etkin()
    # Sabitlenen ozetler bagli dosyalarin TEK okumasindan gelir (RESULTS §14.43, F-3): git kipinde HEAD'e bayt bagindan,
    # aksi halde dogrudan okumadan. Kapanista ayni dosyalar yeniden ozetlenir (D-K3).
    if not denetim:
        sabit: dict[str, str] = {}
    elif _kesif_git_denetimi():
        sabit = kesif_bagi_denetle()
    else:
        sabit = {str(y): _dosya_sha256(y) for y in _kesif_bagli_dosyalar() if y is not None}
    manifest_ozeti = sabit.get(str(onbellek_manifest._etkin_yol())) if denetim else None
    if denetim:
        onbellek_manifest.manifest_dogrula(katman="kesif")
    kayit = _kesif_kaydi_kur(manifest_ozeti)
    kume_bellegi.temizle()
    bv.donuk_bellek_temizle()
    hata: BaseException | None = None
    try:
        with bv.kosu_agsiz(), _kesif_baglami():
            yield kayit
    except BaseException as yakalanan:
        hata = yakalanan
        raise
    finally:
        kayit._kapanis = _iso_zaman()
        try:
            if denetim:
                _kesif_kapanisi_denetle(sabit, onbellek_manifest, hata)
        finally:
            kume_bellegi.temizle()
            bv.donuk_bellek_temizle()


def _kesif_kapanisi_denetle(sabit: dict[str, str], onbellek_manifest, hata: BaseException | None) -> None:
    """Kapanista manifest acilistakiyle ayni olmali ve kesif katmani hala dogrulanmali; degilse `KesifBagiHatasi`.

    Blok zaten hatayla bittiyse o hata ayni turuyle yukari cikar (turu gizlenmez) ve kapanis uyusmazligi ona not olarak
    eklenir: kosu hatayla bittigi icin sonucu zaten yoktur; uyusmazlik yine acikca yazilir."""
    sorun = None
    manifest_yolu = str(onbellek_manifest._etkin_yol())
    degisen = [Path(y).name for y, ozet in sabit.items() if _dosya_sha256(y) != ozet]
    if manifest_yolu in sabit and Path(manifest_yolu).name in degisen:
        sorun = ("Kesif kosusu kapanisi: manifest dosyasi kosu sirasinda degisti (SHA256 acilistakiyle ayni degil). "
                 "Kosunun sonuclari bu manifeste baglanamaz (RESULTS §14.42).")
    elif degisen:
        sorun = (f"Kesif kosusu kapanisi: bagli dosya(lar) kosu sirasinda degisti: {degisen}. Kosunun bolme ve evren "
                 "tablosu acilistakiyle ayni degil (RESULTS §14.43, denetci D-K3).")
    else:
        try:
            onbellek_manifest.manifest_dogrula(katman="kesif")
        except onbellek_manifest.ManifestHatasi as dogrulama:
            sorun = ("Kesif kosusu kapanisi: kesif katmani artik manifestle dogrulanmiyor; onbellek kosu sirasinda "
                     f"degisti. Kosunun sonuclari bu manifeste baglanamaz (RESULTS §14.42). Ayrinti: {dogrulama}")
    if sorun is None:
        return
    if hata is not None:
        hata.add_note(sorun)
        return
    raise KesifBagiHatasi(sorun)


# --- Kume kapisi -------------------------------------------------------------


def _bos_mum_cercevesi() -> pd.DataFrame:
    from data import binance_vision as bv

    return pd.DataFrame(columns=[s for s in bv.MUM_SUTUNLARI if s != "ignore"])


def onay_erisimi_denetle(kume: str, onay: bool) -> None:
    """Kume kapisinin onay adimlari (`kume_erisimi` 1-3). Bellek onbelleginin her okunusunda da calisir
    (`data.kume_bellegi`; on-kayit §3 rev.13): tek kaynak burasidir. Bolme tablosu burada okunmaz, cunku grup
    denetimi karar noktasinda zaten yapilir (`pozisyon.grup_dogrula`) ve her barda tablo okumak gerekmez.

    `pozisyon.mae` ve `funding.pozisyon_fundingi` karar noktasindan gecmez, dolayisiyla `grup_dogrula`yi da
    cagirmaz: onayli pozisyonu (`onay_dogrula`, `onay_baglami_dogrula`) denetler ve veriyi ayni bellek yolundan
    (`pozisyon._kume_verisi`) alir, yani bu denetimden her okunusta gecer (denetci D-C4)."""
    if kume not in config.KUMELER:
        raise ValueError(f"Bilinmeyen kume: {kume!r}. Gecerli degerler: {config.KUMELER}")
    if not isinstance(onay, bool):
        raise OnayGerekli(
            f"onay yalnizca True ya da False olabilir; {onay!r} ({type(onay).__name__}) reddedildi."
        )
    if kume in config.ONAY_KUMELERI:
        if onay is not True:
            raise OnayGerekli(
                f"{kume} bir onay kumesidir ve tek atistir. Erisim icin onay=True ve "
                f"acik bir onay kosusu gerekir (CLAUDE.md §3.3)."
            )
        aktif = aktif_onay_kosusu()  # kayit dosyasinda dogrulanir (KS3 D-B1)
        if aktif is None or aktif[1] != kume:
            raise OnayGerekli(
                f"{kume} verisine yalnizca `with split.onay_kosusu(hipotez, {kume!r}):` blogu "
                f"icinde erisilir. Acik kosu: {aktif}."
            )


def kume_erisimi(
    sembol: str,
    kume: str,
    onay: bool = False,
) -> tuple[bool, pd.Timestamp, pd.Timestamp]:
    """Tum veri yukleyicilerinin ortak kume kapisi (CLAUDE.md §3.2-3.3).

    `yukle`, `klines.mumlari_yukle`, `klines.birincil_gunluk_indir` ve
    `funding.funding_yukle` bu kapidan gecer. Sirasiyla:
      1. Bilinmeyen kume -> ValueError.
      2. `onay` bool degilse (ör. "False") -> `OnayGerekli`.
      3. C1/C2 icin `onay is True` ve ayni kumeye ait, onay kaydinda acik
         gorunen bir `onay_kosusu` yoksa -> `OnayGerekli`; kayda hicbir sey
         yazilmaz.
      4. Bolme tablosu `split_oku` ile okunur ve dogrulanir; disaridan tablo
         verilemez. Sembol tabloda yoksa KeyError.

    Kayit sembol basina degil, `onay_kosusu` acilirken kosu basina yazilir.
    Doner: (sembol kumenin grubunda mi, kume baslangici, kume sonu).
    """
    onay_erisimi_denetle(kume, onay)

    gruplar, _, _ = kume_tanimi(kume)
    bas, son = kume_araligi(kume)
    tablo = split_oku()
    satir = tablo.loc[tablo["sembol"] == sembol]
    if satir.empty:
        raise KeyError(f"{sembol} split.csv icinde yok.")

    return bool(satir["grup"].iloc[0] in gruplar), bas, son


def yukle(
    sembol: str,
    bar: str,
    kume: str,
    onay: bool = False,
    mum_yukleyici=None,
    yenile: bool = False,
) -> pd.DataFrame:
    """Bir sembolun mumlarini kume kisitlarina uyarak yukler.

    Kume kapisi `kume_erisimi`dir. Sembol istenen kumenin grubunda degilse bos
    cerceve doner; veri kume araligina kesilir.

    Ay elemesi (RESULTS §14.42, denetci D-B1): varsayilan yukleyici yalnizca kume araligiyla kesisen aylarin dosyalarini
    acar (`klines.ham_mumlari_yukle(..., aralik=...)`). Onay verisi izni YALNIZCA C1/C2'de acilir; KESIF yuklemesi
    izinsiz calisir, yani bir onay dosyasina ulasma denemesi `OnayVerisiKorumasi` verir. `mum_yukleyici` yalnizca test
    dikisidir (`(sembol, bar)` alir; ay elemesi ve izin onun sorumlulugunda degildir).
    """
    izinli, bas, son = kume_erisimi(sembol, kume, onay=onay)
    if not izinli:
        return _bos_mum_cercevesi()

    from contextlib import nullcontext

    from data import binance_vision as bv

    if mum_yukleyici is None:
        def yukleyici(s, b):
            return klines.ham_mumlari_yukle(s, b, yenile=yenile, aralik=(bas, son))
    else:
        yukleyici = mum_yukleyici
    izin = (bv.onay_verisi_izni(f"split.yukle({sembol}, {bar}, {kume})") if kume in config.ONAY_KUMELERI
            else nullcontext())
    # Kapidan gecildi; kume araligindaki aylar okunur (onay kumesinde izinle), ardindan kume araligina kesilir.
    with izin:
        ham = yukleyici(sembol, bar)
    return klines.donem_kes(ham, bas, son)


# --- Modul korumasi (denetci KS3 D-B1) ---------------------------------------
#
# Onay kosusu durumu ve kosu yolundaki adlar modul disindan atanamaz ya da silinemez: `split._AKTIF_KOSU = ...`,
# `monkeypatch.setattr(split, "_AKTIF_KOSU", ...)` ve kayit yolunu, git ortamini ya da kosu denetimini degistiren
# yama `OnayKorumasi` verir. Modul ici `global` atamasi (yalnizca `onay_kosusu` ve `_test_kaydi_ayarla`) modul
# sozlugune dogrudan yazar ve bu korumadan gecmez.
#
# Onay kaydi ikinci tur (denetci OK D-B2, sizinti testcisi O): bolme ve kume tanimi (`split_oku`, `kume_tanimi`,
# `kume_araligi`), git'e bagli kayit adlari ve `__class__` da korunur; `split.__class__ = types.ModuleType`
# korumayi kaldiramaz. Config'teki kume sabitleri `config._DEGISMEZ_ADLAR`da.
#
# Sinir: ayni surec icinden mutlak koruma mumkun degildir. `vars(split)` / `split.__dict__` uzerinden yazim,
# `object.__setattr__` / `types.ModuleType.__setattr__` ve `sys.modules` degisimi engellenmez. Amac kazayla
# atlatmayi imkansiz, kasitli atlatmayi gorunur kilmaktir: bu yollar analiz kodunda taramayla yasaktir
# (`tests/tarama_yardimcisi.ONAY_ATLATMA_DESENI`).

_KORUNAN_ADLAR = frozenset({
    "_AKTIF_KOSU", "_TEST_AYARI", "_KAYIT_YOLU", "_KORUNAN_ADLAR", "_Kosu", "OnayKosusu", "KosuOrtami",
    "_git", "_kosu_ortami", "ortam_karari", "_pytest_testi", "_test_kaydi_ayarla", "_test_ayari",
    "_kayit_yolu", "_kaydi_oku", "_kayit_kilidi", "_onay_kaydet", "_bitis_yaz", "_acik_kosu",
    "kayda_satir_ekle", "not_alanlari", "kayit_satirlari", "kayittaki_kosular", "_hipotez_dogrula",
    "_onay_kumesi_dogrula", "_sonuc_dogrula", "aktif_onay_kosusu", "onay_baglami_dogrula", "onay_kosusu", "kesif_kosusu",
    # Kesif kosusunun commit bagi (RESULTS §14.42, D-B2).
    "KesifKaydi", "kesif_bagi_denetle", "_kesif_git_denetimi", "_kesif_bagli_dosyalar", "_kesif_kaydi_kur",
    "_kesif_kapanisi_denetle", "_dosya_sha256", "_git_bayt",
    # Kesif baglami (RESULTS §14.42, D-C1).
    "_KESIF_DURUMU", "_KESIF_ORTAM_ADI", "_kesif_baglami", "kesif_kosusu_acik", "kesif_baglami_dogrula",
    "KesifBaglamiYok",
    "kume_erisimi", "onay_erisimi_denetle",
    # Onay kaydi ikinci tur: bolme ve kume tanimi (OK D-B2, sizinti O), git'e bagli kayit (OK D-B1), sinif.
    "split_oku", "kume_tanimi", "kume_araligi",
    "_depo", "_sahte_git", "_kayit_goreli", "_head_kaydi", "_gecmis_kaydi", "_kayit_commitli_denetle",
    "_kaydi_commit_et", "harcanan_ciftler", "onay_satirlari", "gecmis_satirlari",
    "__class__",
    # Kapanis turu: uzak depo baglantisi. Modul bagimliliklari (`config`, `subprocess`, `klines`, `split_dogrula`,
    # `grup`, `varlik_anahtari`, `hashlib`, ...) bilincli olarak korunmaz (RESULTS §14.26): koruma listesi sonsuza
    # kadar uzayamaz; olcut kazayla atlatmayi imkansiz, kasitli atlatmayi gorunur kilmaktir.
    "UZAK_DEPO", "UZAK_DAL", "_UZAK_REF", "_uzagi_getir", "_uzak_gecmis_kaydi", "_itilmemis_denetle", "_ileri_sarma_denetle", "_kaydi_it",
    "_it_ya_da_kaydet", "uzak_adresi_normal", "_uzak_adresi_denetle", "_itme_denemesi",
    # Performans 2b-0 kapanisi (RESULTS §14.46; denetci D-B2, sizinti S-38): §14.45'te eklenen git ortami, durum komutu
    # ve pytest oturumu isareti. Gerileme: korunmadiklari icin siradan bir atamayla agac temizligi dusurulebiliyordu.
    "_GIT_ORTAM_BEYAZ_LISTESI", "_GIT_SABIT_ORTAM", "_DURUM_KOMUTU", "_bag_ortami", "_bag_git", "_PYTEST_OTURUMU",
    "_pytest_oturumu_kur",
    # Agac temizliginin tek kaynagi (RESULTS §14.46; D-B1, S-31..S-33).
    "_IZLENMEYEN_KOMUTU", "_agac_kirlilikleri",
    # Git hazirlik tanisi (RESULTS §14.46, D-B4).
    "git_hazirlik", "_git_tani", "_eposta_maskele",
})


class _KorunanModul(types.ModuleType):
    def __setattr__(self, ad, deger):
        if ad in _KORUNAN_ADLAR:
            raise OnayKorumasi(f"split.{ad} modul disindan atanamaz; onay kosusu yalnizca `onay_kosusu` ile "
                               "acilir ve kapanir, bolme ve kume tanimi degistirilemez (CLAUDE.md §3.2-3.3).")
        super().__setattr__(ad, deger)

    def __delattr__(self, ad):
        if ad in _KORUNAN_ADLAR:
            raise OnayKorumasi(f"split.{ad} silinemez.")
        super().__delattr__(ad)


sys.modules[__name__].__class__ = _KorunanModul


if __name__ == "__main__":
    # `python -m data.split git-hazirlik` (RESULTS §14.46, D-B4): yalnizca tani; onay kosusu acmaz, kayda dokunmaz.
    if sys.argv[1:] == ["git-hazirlik"]:
        raise SystemExit(git_hazirlik())
    raise SystemExit("kullanim: python -m data.split git-hazirlik")
