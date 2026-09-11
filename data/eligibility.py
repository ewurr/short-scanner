"""t anindaki uygunluk filtresi (on-kayit §2, CLAUDE.md §3.6).

Kosullar:
  - Listeleme yasi >= 30 gun,
  - H1, H2 (4h bar) : son 30 gunun medyan gunluk hacmi >= 10.000.000 USDT,
  - H3 (1d bar)     : son 30 gunun medyan gunluk hacmi >=  2.000.000 USDT.

Gelecege bakis yoktur: t anindaki uygunluk yalnizca t'ye kadar (t dahil) kapanmis
gunlerin verisiyle hesaplanir. Gunluk hacim, kullanici karari uyarinca 4h
barlardan turetilen gunluk veriden gelir (bkz. klines.gunluge_cevir) ve her uc
hipotez icin ayni kaynagi kullanir.

Bu modul saftir: ag veya disk kullanmaz.
"""

from __future__ import annotations

import pandas as pd

import config


def gunluk_hacim_serisi(gunluk: pd.DataFrame) -> pd.Series:
    """Gunluk quote hacmini, gunun acilis zamaniyla indekslenmis seri olarak doner."""
    seri = pd.Series(
        pd.to_numeric(gunluk["quote_volume"], errors="coerce").values,
        index=pd.DatetimeIndex(gunluk["open_time"]),
    )
    return seri.sort_index()


def medyan_hacim(gunluk_hacim: pd.Series, t, pencere_gun: int = config.HACIM_PENCERESI_GUN) -> float:
    """t anina kadarki son `pencere_gun` tam gunun medyan hacmi.

    t'nin ait oldugu gun HENUZ KAPANMADIGI icin pencereye alinmaz; yalnizca
    t'den once kapanmis gunler sayilir. Bu, gelecege bakisi imkansiz kilar.
    """
    zaman = pd.Timestamp(t)
    kapanmis = gunluk_hacim.loc[gunluk_hacim.index + pd.Timedelta(days=1) <= zaman]
    if kapanmis.empty:
        return float("nan")
    son = kapanmis.iloc[-pencere_gun:]
    if len(son) < pencere_gun:
        return float("nan")
    return float(son.median())


def listeleme_yasi_gun(ilk_bar_zamani, t) -> float:
    """t anindaki listeleme yasi, gun cinsinden."""
    return (pd.Timestamp(t) - pd.Timestamp(ilk_bar_zamani)) / pd.Timedelta(days=1)


def hacim_esigi(bar: str) -> float:
    """Bar tipine gore on-kayit §2'deki hacim esigi."""
    if bar == config.BAR_4H:
        return config.ASGARI_HACIM_4H
    if bar == config.BAR_1D:
        return config.ASGARI_HACIM_1D
    raise ValueError(f"Bilinmeyen bar: {bar!r}")


def uygun_mu(gunluk_hacim: pd.Series, ilk_bar_zamani, t, bar: str) -> bool:
    """t aninda sembol uygun mu? Yalnizca t'ye kadarki veriyi kullanir."""
    if listeleme_yasi_gun(ilk_bar_zamani, t) < config.ASGARI_LISTELEME_YASI_GUN:
        return False
    medyan = medyan_hacim(gunluk_hacim, t)
    if pd.isna(medyan):
        return False
    return medyan >= hacim_esigi(bar)


def uygunluk_serisi(gunluk_hacim: pd.Series, ilk_bar_zamani, zamanlar, bar: str) -> pd.Series:
    """Verilen zamanlarin her biri icin uygunluk bayragi.

    Denetim raporunda "esigi en az bir gun gecen sembol" sayimi icin kullanilir.
    """
    indeks = pd.DatetimeIndex(zamanlar)
    return pd.Series(
        [uygun_mu(gunluk_hacim, ilk_bar_zamani, t, bar) for t in indeks],
        index=indeks,
    )
