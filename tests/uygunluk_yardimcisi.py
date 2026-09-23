"""Tek karar noktasi testlerinin ortak uygunluk girdisi (on-kayit §4 rev.9: uygunluk
`pozisyon.olay_karari`nin parcasidir).

Uygunluk sartlari (on-kayit §2): listeleme yasi >= 30 gun ve t gunu haric onceki 30 tam gunun
medyan hacmi esigin ustunde. Bunu saglamak icin testler donemi sinyalden en az 60 gun once
baslatir ve o gunden itibaren esigin ustunde hacimli bir 1d serisi verir. Aga cikmaz.
"""

from __future__ import annotations

import pandas as pd

import config

# Uygun olmak icin donem basinin sinyalden en az bu kadar once olmasi yeter.
UYGUN_ONCELIK = pd.Timedelta(days=60)


def esikler(bar: str) -> dict:
    """On-kayit §2 uygunluk esikleri, `olay_karari`nin anahtar sozcukleriyle."""
    hacim = config.ASGARI_HACIM_4H if bar == config.BAR_4H else config.ASGARI_HACIM_1D
    return {"asgari_hacim": hacim, "asgari_listeleme_yasi_gun": config.ASGARI_LISTELEME_YASI_GUN}


def gunluk(bas, son, hacim: float = 5e7) -> pd.DataFrame:
    """`bas` ile `son` arasindaki her UTC gunu icin 1d mum (open_time gun basi, close_time
    gun sonu - 1 ms, sabit quote_volume). `klines.gunluge_cevir` ciktisinin bicimi."""
    gunler = pd.date_range(pd.Timestamp(bas).floor("D"), pd.Timestamp(son).floor("D"), freq="1D")
    return pd.DataFrame({"open_time": gunler, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0,
                         "close_time": gunler + pd.Timedelta(days=1) - pd.Timedelta(milliseconds=1),
                         "quote_volume": float(hacim), "count": 1, "taker_buy_volume": 0.0,
                         "taker_buy_quote_volume": 0.0})


def uygunluk(bar: str, bas, son, hacim: float = 5e7) -> dict:
    """`olay_karari`na verilecek uygunluk anahtar sozcukleri: 1d seri ve on-kayit esikleri."""
    return {"gunluk_mumlar": gunluk(bas, son, hacim), **esikler(bar)}
