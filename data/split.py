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
from data import klines, pencere
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
    # GIT_TERMINAL_PROMPT=0: kimlik bilgisi istenirse beklemek yerine hata (ag islemleri).
    ortam = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        cikti = subprocess.run(
            ["git", *argumanlar], cwd=_depo(), capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=sure, env=ortam,
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
KILIT_ALANLARI = ("hipotez", "hukum", "gerekce", "yapilandirma", "parametreler", "olusmus_olay",
                  "analize_giren_olay", "k2_farki", "kesif_commit", "kesif_zamani", "tohum")
# Hukum "hipotez kapandi" iken yapilandirmaya ait alanlar bos olabilir ("-").
KILIT_SECIM_ALANLARI = ("yapilandirma", "parametreler", "k2_farki")
# On-kayit §8 madde 5'in alan listesinde ORTALAMA NET GETIRI yoktur, ama §8 madde 4 secimin
# kosullarindan biri olarak onu da sayar ("K2 farki > 0" ve "ortalama net getiri > 0"). Alan
# ZORUNLU kilinmaz (on-kayitin listesi genisletilmez); kayitta varsa denetlenir.
KILIT_ISTEGE_BAGLI_ALANLAR = ("ortalama_net_getiri",)


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

    gecerliler = [sinyal_modulu.yapilandirma_kimligi(hipotez, y) for y in sinyal_modulu.izgara(hipotez)]
    if kimlik not in gecerliler:
        raise KilitBozuk(
            f"{hipotez} KILIT.md: yapilandirma {kimlik!r} {hipotez} izgarasinda yok (on-kayit §5). "
            f"Gecerli kimlikler: {gecerliler}. Izgara disi bir kimlik, kosu acildiktan sonra her "
            "pozisyonu reddeder ve onay cifti bos yere yanar (on-kayit §8 madde 5, §9).")
    return kimlik


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
        if not re.fullmatch(r"\d{1,3}(\.\d{3})+|\d+", ham):
            raise KilitBozuk(
                f"{hipotez} KILIT.md: `{ad}` negatif olmayan bir tamsayi olmali (binlik ayirici nokta "
                f"olabilir: '1.500'); verilen {alanlar[ad]!r}. Ondalikli, isaretli ya da sayi olmayan "
                "deger kabul edilmez (on-kayit §8 madde 5).")
        return int(ham.replace(".", ""))

    def _ondalik(ad: str) -> float | None:
        if not secildi:
            return None
        try:
            return float(str(alanlar[ad]).replace(",", ".").strip())
        except ValueError:
            raise KilitBozuk(f"{hipotez} KILIT.md: `{ad}` bir sayi olmali; verilen {alanlar[ad]!r}.") from None

    if secildi:
        bos = [a for a in KILIT_SECIM_ALANLARI if not alanlar[a].strip() or alanlar[a].strip() in ("-", "—")]
        if bos:
            raise KilitBozuk(f"{hipotez} KILIT.md: hukum '{KILIT_SECILDI}' iken {bos} alan(lari) bos olamaz "
                             "(on-kayit §8 madde 5).")
        _kilit_yapilandirmasi_dogrula(alanlar["yapilandirma"].strip(), hipotez)
    elif not alanlar["gerekce"].strip() or alanlar["gerekce"].strip() in ("-", "—"):
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
    return KilitKaydi(hipotez=hipotez, hukum=alanlar["hukum"], gerekce=alanlar["gerekce"],
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
        raise OnayOrtamiHatasi(
            f"Onay kosusu yalnizca temiz calisma agacinda acilir; {len(kirli)} degisiklik var "
            f"(ornek: {kirli[:5]}). Once commit edin.")
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
    return ortam_karari(_git("rev-parse", "HEAD"), _git("status", "--porcelain"), betik, izleniyor)


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


def _pytest_testi() -> str | None:
    """Calisan pytest testinin kimligi; pytest disinda None."""
    deger = os.environ.get("PYTEST_CURRENT_TEST")
    if not deger or "pytest" not in sys.modules:
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
        raise OnayKaydiCommitsiz(f"Onay kaydi commit edilemedi ({mesaj}). Kayit satiri calisma agacinda; elle "
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


# --- Kume kapisi -------------------------------------------------------------


def _bos_mum_cercevesi() -> pd.DataFrame:
    from data import binance_vision as bv

    return pd.DataFrame(columns=[s for s in bv.MUM_SUTUNLARI if s != "ignore"])


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
) -> pd.DataFrame:
    """Bir sembolun mumlarini kume kisitlarina uyarak yukler.

    Kume kapisi `kume_erisimi`dir. Sembol istenen kumenin grubunda degilse bos
    cerceve doner; veri kume araligina kesilir.
    """
    izinli, bas, son = kume_erisimi(sembol, kume, onay=onay)
    if not izinli:
        return _bos_mum_cercevesi()

    yukleyici = klines.ham_mumlari_yukle if mum_yukleyici is None else mum_yukleyici
    from data import binance_vision as bv

    # Kapidan gecildi; ham okuma (butun aylar) onay verisi izniyle, ardindan kume araligina kesilir.
    with bv.onay_verisi_izni(f"split.yukle({sembol}, {bar}, {kume})"):
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
    "_onay_kumesi_dogrula", "_sonuc_dogrula", "aktif_onay_kosusu", "onay_baglami_dogrula", "onay_kosusu",
    "kume_erisimi",
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
