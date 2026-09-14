"""Listeleme donemi mantigi (on-kayit §2 rev.7).

On-kayit §2 rev.7 "Listeleme donemi":
  - Donem, sifir olmayan hacimli ilk barda baslar ve sifir olmayan hacimli son
    barda biter. Sinir BAR duzeyindedir, ay duzeyinde degil.
  - 6 veya daha fazla ardisik sifir hacimli bar (bir gun) donemi boler. Bu barlar
    delist edilmis ya da henuz yeniden listelenmemis bir sozlesmenin dolgu
    verisidir ve hicbir hesaba girmez.
  - 7 gunden uzun eksik bar boslugu donemi boler. Bundan kisa bosluklar borsa
    kesintisi sayilir ve rev.3'un veri boslugu kurallarina tabidir.
  - Yeniden adlandirma zincirindeki her sembol ayri bir donemdir (sembol basina
    ayri seri; burada birlestirme yapilmaz).
  - Listeleme yasi her donem basinda sifirlanir; geriye bakis pencereleri donem
    baslangicini asamaz; ufuk donem sonunu asarsa cikis donemin son barinin
    kapanisidir (data/pencere.py, data/eligibility.py).

Karantina (SETTLED ayi) kurali rev.7 ile kaldirildi; bu modulde karantina yoktur.

Sinir temsili: `baslangic` ilk gercek barin, `bitis` son gercek barin ACILIS
zamanidir (CLAUDE.md §5: bar zamani acilis zamanidir). `pencere.cikis_bari`
acilisi `donem_bitis`e esit ya da ondan once olan barlari donem icinde sayar.

Bu modul tamamen saftir: ag veya disk kullanmaz.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

import config
from data import pencere as pencere_modulu


@dataclass(frozen=True)
class Donem:
    """Bir listeleme donemi (on-kayit §2 rev.7)."""

    baslangic: pd.Timestamp  # sifir olmayan hacimli ilk barin acilisi
    bitis: pd.Timestamp  # sifir olmayan hacimli son barin acilisi
    bar_sayisi: int  # baslangic..bitis arasindaki mevcut bar sayisi
    gercek_bar_sayisi: int  # bunlardan sifir olmayan hacimli olanlar


@dataclass(frozen=True)
class DolguKosusu:
    """Donemi bolen (ya da serinin basinda/sonunda kalan) sifir hacimli bar kosusu."""

    baslangic: pd.Timestamp
    bitis: pd.Timestamp
    bar_sayisi: int
    konum: str  # "bas", "ic" ya da "son"


def gercek_bar_maskesi(hacim) -> np.ndarray:
    """Sifir olmayan hacimli barlar. NaN hacim gercek islem sayilmaz (ihtiyatli)."""
    degerler = pd.to_numeric(pd.Series(np.asarray(hacim)), errors="coerce").to_numpy(dtype=float)
    return np.nan_to_num(degerler, nan=0.0) > 0


def _kosular(sifir: np.ndarray) -> list[tuple[int, int]]:
    """Ardisik True kosularinin [bas, son] indeksleri (son dahil)."""
    degisim = np.flatnonzero(np.diff(np.r_[0, sifir.astype(np.int8), 0]))
    return [(int(b), int(e) - 1) for b, e in zip(degisim[::2], degisim[1::2])]


def _hazirla(zamanlar, hacim, bar: str):
    indeks = pencere_modulu._zaman_dizisi_dogrula(zamanlar, "listeleme_donemleri")
    if len(indeks) != len(np.asarray(hacim)):
        raise ValueError("zamanlar ve hacim ayni uzunlukta olmali.")
    adim = pencere_modulu.adim(bar)
    return indeks, gercek_bar_maskesi(hacim), adim


def dolgu_kosulari(zamanlar, hacim, bar: str) -> list[DolguKosusu]:
    """Esigi (`config.DOLGU_KOSU_ESIGI_BAR`) gecen sifir hacim kosulari (denetim)."""
    indeks, gercek, _ = _hazirla(zamanlar, hacim, bar)
    sonuc = []
    for b, e in _kosular(~gercek):
        n = e - b + 1
        if n < config.DOLGU_KOSU_ESIGI_BAR:
            continue
        konum = "bas" if b == 0 else ("son" if e == len(indeks) - 1 else "ic")
        sonuc.append(DolguKosusu(indeks[b], indeks[e], n, konum))
    return sonuc


def kisa_sifir_kosulari(zamanlar, hacim, bar: str) -> list[DolguKosusu]:
    """Serinin ORTASINDA kalan, esikten kisa (1..esik-1 bar) sifir hacim kosulari.

    F1 olcumu S2: evrende boyle bir kosu yoktu. Cikarsa bir likidite boslugunun
    donemin parcasi sayildigini gosterir ve denetim testi uyarir.
    """
    indeks, gercek, _ = _hazirla(zamanlar, hacim, bar)
    sonuc = []
    for b, e in _kosular(~gercek):
        n = e - b + 1
        if n >= config.DOLGU_KOSU_ESIGI_BAR or b == 0 or e == len(indeks) - 1:
            continue
        sonuc.append(DolguKosusu(indeks[b], indeks[e], n, "ic"))
    return sonuc


def listeleme_donemleri(zamanlar, hacim, bar: str) -> list[Donem]:
    """Bar serisinden listeleme donemleri (on-kayit §2 rev.7). Saf fonksiyon.

    `zamanlar`: kesin artan, tekrarsiz, UTC bar acilis zamanlari.
    `hacim`: ayni uzunlukta hacim dizisi (quote_volume).
    """
    indeks, gercek, adim = _hazirla(zamanlar, hacim, bar)
    n = len(indeks)
    if n == 0:
        return []

    dolgu = np.zeros(n, dtype=bool)
    for b, e in _kosular(~gercek):
        if e - b + 1 >= config.DOLGU_KOSU_ESIGI_BAR:
            dolgu[b:e + 1] = True

    # Ardisik iki mevcut bar arasindaki EKSIK sure: sonraki acilis - onceki acilis - adim.
    eksik_sure = (indeks[1:] - indeks[:-1]) - adim
    uzun_bosluk = np.r_[False, np.asarray(eksik_sure > pd.Timedelta(config.AZAMI_EKSIK_BAR_BOSLUGU), dtype=bool)]

    parca = np.full(n, -1)
    kimlik = -1
    ayirici = True
    for i in range(n):
        if dolgu[i]:
            ayirici = True
            continue
        if ayirici or uzun_bosluk[i]:
            kimlik += 1
            ayirici = False
        parca[i] = kimlik

    donemler = []
    for k in range(kimlik + 1):
        idx = np.flatnonzero(parca == k)
        g = idx[gercek[idx]]
        if len(g) == 0:
            continue
        ilk, son = int(g[0]), int(g[-1])
        donemler.append(Donem(indeks[ilk], indeks[son], son - ilk + 1, int(gercek[ilk:son + 1].sum())))
    return donemler


def donem_sinirlari(donemler: list[Donem]) -> pd.DataFrame:
    """Donemleri tabloya cevirir: donem_id, donem_baslangic, donem_bitis (bar acilislari)."""
    return pd.DataFrame(
        [
            {
                "donem_id": i,
                "donem_baslangic": d.baslangic,
                "donem_bitis": d.bitis,
                "donem_bar_sayisi": d.bar_sayisi,
                "donem_gercek_bar_sayisi": d.gercek_bar_sayisi,
            }
            for i, d in enumerate(donemler)
        ],
        columns=["donem_id", "donem_baslangic", "donem_bitis", "donem_bar_sayisi", "donem_gercek_bar_sayisi"],
    )


def donem_bul(t, donemler: list[Donem]) -> int | None:
    """t bar acilis aninin dustugu donemin sirasi; hicbirine dusmuyorsa None."""
    zaman = pencere_modulu.utc_zamani(t, "t")
    for i, d in enumerate(donemler):
        if d.baslangic <= zaman <= d.bitis:
            return i
    return None
