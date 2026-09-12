"""Zamanla tanimli pencere, tamlik kontrolu ve ufuk (on-kayit §2, revizyon 3).

Revizyon 3'ten once her hesap penceresini kendi indeksleriyle sayiyordu; bu,
eksik bar bulunan seride pencerenin sessizce gecmise uzamasina yol aciyordu.
Bu modul o mantigi tek yere toplar.

Kurallar (on-kayit §2 rev.3):
  - **Pencereler zamanla tanimlanir.** "Son N bar" = son N x adim sureli zaman
    araligi. Bar sayisiyla degil, zaman damgasiyla hesaplanir.
  - **Tamlik sarti.** Pencerede beklenen barlardan biri bile eksikse deger
    hesaplanmaz (NaN) ve o barda olay ya da kontrol olusmaz.
  - **Ufuk.** Ufuk zamanla olculur: h bar = h x adim. Hedef cikis bari eksikse
    cikis, sonraki ilk mevcut barin ACILIS fiyatindandir. Donem sonu ve delist
    kurallari onceliklidir.
  - **Giris.** t+1 bari eksikse olay olusmaz.
  - Ayni kurallar K1 ve K2 kontrol barlarina da uygulanir.

Donem ve karantina kisitlari da buradan gecer (on-kayit §2 rev.2).

Bu modul tamamen saftir: ag veya disk kullanmaz.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

import config
from data import donem as donem_modulu

# Bar tipine gore izgara adimi.
ADIMLAR = {
    config.BAR_4H: pd.Timedelta(hours=4),
    config.BAR_1D: pd.Timedelta(days=1),
}


def adim(bar: str) -> pd.Timedelta:
    """Bar tipinin zaman izgarasi adimi."""
    try:
        return ADIMLAR[bar]
    except KeyError:
        raise ValueError(f"Bilinmeyen bar: {bar!r}") from None


@dataclass(frozen=True)
class CikisSonucu:
    """Ufuk sonucu. Getiri HESAPLANMAZ; yalnizca hangi barda, hangi fiyat
    alanindan cikilacagi soylenir."""

    indeks: int
    zaman: pd.Timestamp
    fiyat_alani: str  # "close" (normal) veya "open" (ileri kaymali cikis)
    kaydi: bool  # hedef bar eksikti, sonraki mevcut bara kayildi mi?
    kirpildi: bool  # donem sonu / delist nedeniyle kirpildi mi?


# --- Tamlik ------------------------------------------------------------------


def beklenen_zamanlar(bitis, bar_sayisi: int, bar: str) -> pd.DatetimeIndex:
    """`bitis` dahil, geriye dogru `bar_sayisi` adetlik beklenen izgara.

    Pencere zamanla tanimlidir: [bitis - (bar_sayisi-1) x adim, bitis].
    """
    if bar_sayisi < 1:
        raise ValueError("bar_sayisi en az 1 olmali.")
    son = pd.Timestamp(bitis)
    return pd.date_range(end=son, periods=bar_sayisi, freq=adim(bar))


def pencere_tam_mi(zamanlar, bitis, bar_sayisi: int, bar: str) -> bool:
    """Penceredeki beklenen barlarin TAMAMI mevcut mu? (on-kayit §2 rev.3)

    Tek bir bar eksikse False doner; cagiran taraf degeri hesaplamaz.
    """
    beklenen = beklenen_zamanlar(bitis, bar_sayisi, bar)
    mevcut = pd.DatetimeIndex(zamanlar)
    return bool(beklenen.isin(mevcut).all())


def pencere_dilimi(
    seri: pd.Series,
    bitis,
    bar_sayisi: int,
    bar: str,
    donem_baslangic=None,
    karantina_aylari=(),
) -> pd.Series | None:
    """Zamanla tanimli pencereyi doner; kurallardan biri saglanmazsa None.

    Sirasiyla su kosullar aranir:
      1. Pencere donem baslangicini asmamali (on-kayit §2 rev.2),
      2. Pencerenin hicbir bari karantina ayina dusmemeli,
      3. Penceredeki beklenen barlarin tamami mevcut olmali (rev.3 tamlik sarti).
    """
    son = pd.Timestamp(bitis)
    beklenen = beklenen_zamanlar(son, bar_sayisi, bar)

    if donem_baslangic is not None:
        if beklenen[0] < pd.Timestamp(donem_baslangic):
            return None

    if len(karantina_aylari):
        karantina = {donem_modulu._ay(a) for a in karantina_aylari}
        if any(pd.Period(t, freq="M") in karantina for t in beklenen):
            return None

    indeks = pd.DatetimeIndex(seri.index)
    if not beklenen.isin(indeks).all():
        return None  # tamlik sarti saglanmadi

    return seri.reindex(beklenen)


def pencere_degeri(
    seri: pd.Series,
    bitis,
    bar_sayisi: int,
    bar: str,
    islev="median",
    donem_baslangic=None,
    karantina_aylari=(),
) -> float:
    """Zamanla tanimli pencereye bir toplayici uygular; kural ihlalinde NaN.

    `islev` bir Series metodu adi ("median", "mean", "min", "max", "sum") ya da
    Series alan bir cagrilabilirdir.
    """
    dilim = pencere_dilimi(seri, bitis, bar_sayisi, bar, donem_baslangic, karantina_aylari)
    if dilim is None or dilim.isna().any():
        return float("nan")
    if callable(islev):
        return float(islev(dilim))
    return float(getattr(dilim, islev)())


# --- Giris ve cikis ----------------------------------------------------------


def giris_bari(zamanlar, sinyal_zamani, bar: str) -> pd.Timestamp | None:
    """t+1 barinin zamani; o bar eksikse None (on-kayit §2 rev.3: olay olusmaz).

    Gelecege bakis yoktur: sinyal t barinin kapanisinda hesaplanir, islem t+1
    barinin acilisinda acilir (CLAUDE.md §3.6).
    """
    hedef = pd.Timestamp(sinyal_zamani) + adim(bar)
    return hedef if hedef in pd.DatetimeIndex(zamanlar) else None


def cikis_bari(
    zamanlar,
    giris_zamani,
    ufuk: int,
    bar: str,
    donem_bitis=None,
) -> CikisSonucu:
    """Ufuk sonundaki cikis barini secer (on-kayit §2 rev.3).

    - Ufuk zamanla olculur: `giris + ufuk x adim`.
    - Hedef bar mevcutsa cikis o barin KAPANISIDIR.
    - Hedef bar eksikse cikis, sonraki ilk mevcut barin ACILISIDIR.
    - Donem sonu (ve delist = serinin son bari) onceliklidir: kirpma yapilir ve
      cikis o barin kapanisidir.

    Getiri HESAPLAMAZ; yalnizca cikis barini ve hangi fiyat alanindan
    okunacagini soyler.
    """
    indeks = pd.DatetimeIndex(zamanlar)
    if len(indeks) == 0:
        raise ValueError("Bar listesi bos.")
    giris = pd.Timestamp(giris_zamani)
    if giris not in indeks:
        raise KeyError(f"Giris bari seride yok: {giris}")

    sinir = indeks[-1]
    if donem_bitis is not None:
        sinir = min(sinir, pd.Timestamp(donem_bitis))

    hedef = giris + ufuk * adim(bar)

    # Donem sonu / delist onceliklidir.
    if hedef >= sinir:
        gecerli = indeks[indeks <= sinir]
        if len(gecerli) == 0:
            raise ValueError("Donem siniri icinde hic bar yok.")
        son = gecerli[-1]
        return CikisSonucu(
            indeks=int(np.flatnonzero(indeks == son)[0]),
            zaman=son,
            fiyat_alani="close",
            kaydi=False,
            kirpildi=hedef > sinir,
        )

    if hedef in indeks:
        return CikisSonucu(
            indeks=int(np.flatnonzero(indeks == hedef)[0]),
            zaman=hedef,
            fiyat_alani="close",
            kaydi=False,
            kirpildi=False,
        )

    # Hedef bar eksik: sonraki ilk mevcut barin ACILISI.
    sonrakiler = indeks[(indeks > hedef) & (indeks <= sinir)]
    if len(sonrakiler) == 0:
        gecerli = indeks[indeks <= sinir]
        son = gecerli[-1]
        return CikisSonucu(
            indeks=int(np.flatnonzero(indeks == son)[0]),
            zaman=son,
            fiyat_alani="close",
            kaydi=False,
            kirpildi=True,
        )
    ilk = sonrakiler[0]
    return CikisSonucu(
        indeks=int(np.flatnonzero(indeks == ilk)[0]),
        zaman=ilk,
        fiyat_alani="open",
        kaydi=True,
        kirpildi=False,
    )
