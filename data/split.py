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
        with split.onay_kosusu("H2", "C1"):
            mumlari_yukle(sembol, bar, "C1", onay=True)
  - Kosu acilirken ONAY_KAYDI.md'ye KOSU BASINA TEK SATIR yazilir: tarih,
    kume, cagiran betik, commit hash ve calisma agacinin temiz olup olmadigi,
    hipotez adi. Sembol basina satir yazilmaz.
  - Ayni (hipotez, kume) cifti kayitta zaten varsa kosu reddedilir: tek atis.
  - `onay` yalnizca gercek `True` ile kapiyi acar; `"False"` gibi dogruluk
    degeri tasiyan baska her sey reddedilir.

Bolme tablosu (F1 kapanis bulgusu 9): `split_oku` tabloyu okurken her satiri
bolme kuralina gore yeniden hesaplar; yukleyicilere disaridan tablo verme yolu
yoktur.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import subprocess
from contextlib import contextmanager
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


def _git(*argumanlar: str) -> str | None:
    try:
        cikti = subprocess.run(
            ["git", *argumanlar], cwd=config.KOK, capture_output=True, text=True, timeout=10
        )
    except Exception:
        return None
    if cikti.returncode != 0:
        return None
    return cikti.stdout


def _git_commit() -> str:
    cikti = _git("rev-parse", "HEAD")
    return cikti.strip() if cikti and cikti.strip() else "bilinmiyor"


def _calisma_agaci_durumu() -> str:
    """`temiz`, `KIRLI` (commit edilmemis ya da izlenmeyen dosya var) ya da `bilinmiyor`."""
    cikti = _git("status", "--porcelain")
    if cikti is None:
        return "bilinmiyor"
    return "temiz" if not cikti.strip() else "KIRLI"


def _cagiran_betik() -> str:
    import __main__

    yol = getattr(__main__, "__file__", None)
    return Path(yol).name if yol else "etkilesimli"


ONAY_TABLO_BASLIGI = "| Tarih (UTC) |"


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


def kayittaki_kosular(metin: str) -> set[tuple[str, str]]:
    """Kayit metnindeki onay kosularinin (hipotez, kume) ciftleri. Saf.

    Satir bicimi: `| tarih | kume | betik | commit (durum) | hipotez=<ad> |`.
    """
    kosular: set[tuple[str, str]] = set()
    for satir in metin.splitlines():
        if not satir.startswith("|") or satir.startswith(ONAY_TABLO_BASLIGI):
            continue
        hucreler = [h.strip() for h in satir.strip().strip("|").split("|")]
        if len(hucreler) < 5:
            continue
        for parca in hucreler[4].split():
            if parca.startswith("hipotez="):
                kosular.add((parca[len("hipotez="):], hucreler[1]))
    return kosular


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


def onay_baglami_dogrula(hipotez: str, kume: str) -> None:
    """Karar noktasinin onay baglami (kapi sertlestirme turu 3, denetci KS2 D-B1): C1/C2 pozisyonu yalnizca
    ayni (hipotez, kume) ciftinin acik onay kosusu icinde; acik bir onay kosusu varken baska hicbir
    (hipotez, kume) pozisyonu, KESIF dahil, olusturulamaz. Uyusmazlik `OnayUyusmazligi`."""
    aktif = _AKTIF_KOSU
    if kume in config.ONAY_KUMELERI or aktif is not None:
        if aktif != (hipotez, kume):
            raise OnayUyusmazligi(
                f"Pozisyon ({hipotez}, {kume}) acik onay kosusuyla ({aktif}) eslesmiyor. C1/C2 pozisyonu yalnizca "
                f"`with split.onay_kosusu({hipotez!r}, {kume!r}):` icinde; acik kosu varken baska pozisyon "
                "olusturulamaz.")


def onay_kaydet(hipotez: str, kume: str, yol: Path | None = None) -> None:
    """ONAY_KAYDI.md tablosuna BIR onay kosusu satiri ekler (CLAUDE.md §3.3).

    - Yalnizca ekleme yapar; mevcut satirlar bayt bayt korunur.
    - Ayni (hipotez, kume) kayitta varsa `OnayTekrari`: hicbir sey yazilmaz.
    - Satir: tarih (UTC), kume, cagiran betik, commit hash + calisma agaci
      durumu (temiz / KIRLI / bilinmiyor), hipotez adi.
    """
    _hipotez_dogrula(hipotez)
    _onay_kumesi_dogrula(kume)
    hedef = config.ONAY_KAYDI if yol is None else Path(yol)

    # newline="" satir sonlarini cevirmeden okur/yazar; aksi halde Windows'ta tum
    # dosyanin LF'leri CRLF'e donusur ve mevcut satirlar degismis olur.
    eski = ""
    if hedef.exists():
        with hedef.open("r", encoding="utf-8", newline="") as dosya:
            eski = dosya.read()
    if (hipotez, kume) in kayittaki_kosular(eski):
        raise OnayTekrari(
            f"{hipotez} icin {kume} onay kosusu zaten kayitli. Onay kumeleri her hipotez "
            "icin BIR KEZ kosulur (CLAUDE.md §3.3, on-kayit §9)."
        )

    zaman = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    satir = (
        f"| {zaman} | {kume} | {_cagiran_betik()} | "
        f"{_git_commit()[:12]} ({_calisma_agaci_durumu()}) | hipotez={hipotez} |"
    )
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


_AKTIF_KOSU: tuple[str, str] | None = None


def aktif_onay_kosusu() -> tuple[str, str] | None:
    """Acik onay kosusu varsa (hipotez, kume)."""
    return _AKTIF_KOSU


@contextmanager
def onay_kosusu(hipotez: str, kume: str, yol: Path | None = None):
    """Bir hipotez icin bir onay kumesinin TEK kosusunu acar.

    Girerken kayda tek satir yazilir (tekrar ise `OnayTekrari`, hicbir sey
    yazilmaz); blok icinde o kumeye `onay=True` ile erisilebilir; cikista kosu
    kapanir. Ic ice kosu acilamaz.
    """
    global _AKTIF_KOSU
    if _AKTIF_KOSU is not None:
        raise RuntimeError(f"Zaten acik bir onay kosusu var: {_AKTIF_KOSU}. Ic ice kosu acilamaz.")
    onay_kaydet(hipotez, kume, yol=yol)
    _AKTIF_KOSU = (hipotez, kume)
    try:
        yield
    finally:
        _AKTIF_KOSU = None


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
      3. C1/C2 icin `onay is True` ve ayni kumeye ait acik bir `onay_kosusu`
         yoksa -> `OnayGerekli`; kayda hicbir sey yazilmaz.
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
        if _AKTIF_KOSU is None or _AKTIF_KOSU[1] != kume:
            raise OnayGerekli(
                f"{kume} verisine yalnizca `with split.onay_kosusu(hipotez, {kume!r}):` blogu "
                f"icinde erisilir. Acik kosu: {_AKTIF_KOSU}."
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
    return klines.donem_kes(yukleyici(sembol, bar), bas, son)
