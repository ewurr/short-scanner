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

C1 ve C2 yalnizca `onay=True` ile acilir; her acilis ONAY_KAYDI.md'ye eklenir.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import subprocess
from pathlib import Path
from typing import Mapping

import pandas as pd

import config
from data import klines
from data.pencere import KumeSiniriHatasi, adim


class OnayGerekli(PermissionError):
    """Onay kumesine `onay=True` olmadan erisim denendi (CLAUDE.md §3.3)."""


# --- Bolme -------------------------------------------------------------------


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
    return pd.DataFrame(satirlar, columns=["sembol", "varlik_anahtari", "grup"])


def split_yaz(cerceve: pd.DataFrame, yol: Path | None = None) -> Path:
    """split.csv'yi yazar. Dosya varsa uzerine yazmaz (CLAUDE.md §3.2)."""
    hedef = config.SPLIT_CSV if yol is None else yol
    if hedef.exists():
        raise FileExistsError(
            f"{hedef} zaten var. Veri bolmesi dokunulmazdir (CLAUDE.md §3.2)."
        )
    hedef.parent.mkdir(parents=True, exist_ok=True)
    cerceve.to_csv(hedef, index=False, lineterminator="\n")
    return hedef


def split_oku(yol: Path | None = None) -> pd.DataFrame:
    hedef = config.SPLIT_CSV if yol is None else yol
    if not hedef.exists():
        raise FileNotFoundError(f"{hedef} yok. Once split.csv uretilip commit edilmeli.")
    return pd.read_csv(hedef)


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


def ufuk_kumeye_sigar_mi(sinyal_zamani, ufuk: int, bar: str, kume: str) -> bool:
    """Olayin ufku ait oldugu kumenin tarih araligina tam olarak sigiyor mu?

    On-kayit §3 rev.4: sigmayan olay o kumede hic olusmaz; kirpilmis getiri
    kullanilmaz ve komsu kumeden veri odunc alinmaz. Ikincil ufuklar ayni
    kurala kendi uzunluklariyla tabidir.

    - Olayin kumesi, sinyal barinin (t) dustugu kumedir: `bas <= t`.
    - Pozisyon t+1..t+h tutulur (§4), cikis bari t+h: `t + h x adim <= son`.
    - Bar zamani acilis zamanidir; kumenin son bari, acilisi kume sonuna esit
      ya da ondan once olan bardir (`klines.donem_kes` ile ayni kural).
    """
    if ufuk < 1:
        raise ValueError(f"ufuk en az 1 bar olmali: {ufuk}")
    bas, son = kume_araligi(kume)
    t = pd.Timestamp(sinyal_zamani)
    return bool(bas <= t and t + ufuk * adim(bar) <= son)


def _git_commit() -> str:
    try:
        cikti = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=config.KOK,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return cikti.stdout.strip() or "bilinmiyor"
    except Exception:
        return "bilinmiyor"


def _cagiran_betik() -> str:
    import __main__

    yol = getattr(__main__, "__file__", None)
    return Path(yol).name if yol else "etkilesimli"


def onay_kaydet(kume: str, sembol: str, not_metni: str = "", yol: Path | None = None) -> None:
    """ONAY_KAYDI.md'ye bir satir ekler. Yalnizca ekleme yapar (CLAUDE.md §3.3)."""
    hedef = config.ONAY_KAYDI if yol is None else yol
    zaman = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    satir = (
        f"| {zaman} | {kume} | {_cagiran_betik()} | {_git_commit()[:12]} | "
        f"{sembol} {not_metni}".rstrip()
        + " |\n"
    )
    with hedef.open("a", encoding="utf-8") as dosya:
        dosya.write(satir)


def _bos_mum_cercevesi() -> pd.DataFrame:
    from data import binance_vision as bv

    return pd.DataFrame(columns=[s for s in bv.MUM_SUTUNLARI if s != "ignore"])


def yukle(
    sembol: str,
    bar: str,
    kume: str,
    onay: bool = False,
    split: pd.DataFrame | None = None,
    mum_yukleyici=None,
) -> pd.DataFrame:
    """Bir sembolun mumlarini kume kisitlarina uyarak yukler.

    KESIF disindaki kumeler (C1, C2) `onay=True` istemez ise `OnayGerekli`
    (PermissionError) firlatir ve kayit dosyasina hicbir sey yazilmaz.

    Sembol istenen kumenin grubunda degilse bos cerceve doner.
    """
    if kume not in config.KUMELER:
        raise ValueError(f"Bilinmeyen kume: {kume!r}. Gecerli degerler: {config.KUMELER}")

    if kume in config.ONAY_KUMELERI and not onay:
        raise OnayGerekli(
            f"{kume} bir onay kumesidir ve tek atistir. Erisim icin onay=True "
            f"gerekir; her erisim ONAY_KAYDI.md'ye yazilir (CLAUDE.md §3.3)."
        )

    gruplar, bas, son = kume_tanimi(kume)
    tablo = split_oku() if split is None else split
    satir = tablo.loc[tablo["sembol"] == sembol]
    if satir.empty:
        raise KeyError(f"{sembol} split.csv icinde yok.")

    # onay=True ile yapilan HER cagri kaydedilir; sembol kumenin grubunda
    # olmasa bile onay verisine uzanma girisimi ize birakir (CLAUDE.md §3.3).
    if kume in config.ONAY_KUMELERI:
        onay_kaydet(kume, sembol, f"bar={bar}")

    if satir["grup"].iloc[0] not in gruplar:
        return _bos_mum_cercevesi()

    yukleyici = klines.mumlari_yukle if mum_yukleyici is None else mum_yukleyici
    return klines.donem_kes(yukleyici(sembol, bar), bas, son)
