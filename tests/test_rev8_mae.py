"""On-kayit §4 rev.8 "MAE": `max(H, P1) / P0 - 1`; H, acilisi giris anindan once
olmayan ve kapanisi cikis anindan sonra olmayan donem ici 4h barlarin en yuksek high'i.
Yalnizca sentetik veri; gercek veride calistirilmaz, sonuc raporlanmaz. Aga cikmaz.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import config
from data import klines, pozisyon
from data.donem import Donem
from uygunluk_yardimcisi import UYGUN_ONCELIK, uygunluk

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
BAS, B = T("2025-01-01 00:00"), T("2025-02-10 20:00")


def _mum(z, high=None):
    z = pd.DatetimeIndex(z)
    n = len(z)
    return pd.DataFrame({"open_time": z, "open": 100.0, "high": 101.0 if high is None else high,
                         "low": 99.0, "close": 100.0, "volume": 1.0, "close_time": z, "quote_volume": 1.0,
                         "count": 1, "taker_buy_volume": 0.0, "taker_buy_quote_volume": 0.0})


def _fund():
    z = pd.date_range(BAS, B + H4, freq="8h")
    return pd.DataFrame({"odeme_zamani": z, "aralik_saat": 8.0, "oran": 1e-4, "oran_8h": 1e-4})


def _karar(mum, t, ufuk=18, bar=config.BAR_4H, b=B):
    # Rev.9 §4: uygunluk karar noktasinda; donem mum serisinden UYGUN_ONCELIK once baslar.
    return pozisyon.olay_karari(mum, _fund(), t, ufuk, bar, birincil_ufuk=18 if bar == config.BAR_4H else 14,
                                kume_baslangic=None, kume_bitis=None, donem_baslangic=BAS - UYGUN_ONCELIK,
                                donem_bitis=b, sinyal_degerleri={"p": 1.0},
                                **uygunluk(bar, BAS - UYGUN_ONCELIK, b))


def test_pencere_giris_barindan_cikis_barina():
    z = pd.date_range(BAS, B, freq="4h")
    m = _mum(z)
    p = _karar(m, T("2025-01-05 04:00"), ufuk=6)  # giris 08:00 .. cikis ani 2025-01-06 08:00
    # pencere disindaki barlara ve pencere icine yuksek tepe koy
    m.loc[m["open_time"] == T("2025-01-05 04:00"), "high"] = 500.0  # t bari: giristen once
    m.loc[m["open_time"] == T("2025-01-06 08:00"), "high"] = 400.0  # kapanisi cikistan sonra
    m.loc[m["open_time"] == T("2025-01-06 04:00"), "high"] = 130.0  # son pencere bari
    p = _karar(m, T("2025-01-05 04:00"), ufuk=6)
    assert pozisyon.mae(m, p) == pytest.approx(130.0 / 100.0 - 1)


def test_p1_tepeden_buyukse_p1_kullanilir():
    """Ileri kaymada bosluk uzerinden gelen cikis fiyati ara zarar olarak kaybolmaz."""
    z = pd.date_range(BAS, B, freq="4h")
    eksik = z[(z < T("2025-01-08 04:00")) | (z > T("2025-01-09 04:00"))]
    m = _mum(eksik)
    m.loc[m["open_time"] == T("2025-01-09 08:00"), "open"] = 150.0  # bosluk sonrasi acilis (P1)
    p = _karar(m, T("2025-01-05 04:00"))  # T = 2025-01-08 08:00; hedef bar 04:00 eksik
    assert p.cikis_turu == "ileri_kayma" and p.p1 == 150.0
    assert pozisyon.mae(m, p) == pytest.approx(0.5)


def test_donem_sonunda_b_deki_bar_dahil_sonrasi_degil():
    b = T("2025-01-20 08:00")
    z = pd.date_range(BAS, B, freq="4h")
    m = _mum(z)
    m.loc[m["open_time"] == b, "high"] = 120.0
    m.loc[m["open_time"] == b + H4, "high"] = 999.0  # donem disi (dolgu) bar
    p = _karar(m, T("2025-01-18 08:00"), b=b)
    assert p.cikis_turu == "donem_sonu"
    assert pozisyon.mae(m, p) == pytest.approx(0.2)


def test_eksik_bar_mae_yi_hesaplanamaz_yapmaz():
    z = pd.date_range(BAS, B, freq="4h")
    m = _mum(z.drop([T("2025-01-06 00:00"), T("2025-01-06 04:00")]))
    p = _karar(m, T("2025-01-05 04:00"))
    assert np.isfinite(pozisyon.mae(m, p))


def test_tam_gunlerde_1d_tanimiyla_ayni():
    """Eksiksiz gunlerde 4h tanimi max(high[t+1..t+h]) / P0 - 1 ile ayni sonucu verir."""
    z = pd.date_range(BAS, B, freq="4h")
    rng = np.random.default_rng(config.TOHUM)
    m = _mum(z, high=100.0 + rng.random(len(z)) * 20)
    gunluk = klines.gunluge_cevir(m, donemler=[Donem(BAS, B, len(z), len(z))]).set_index("open_time")
    t, h = T("2025-01-10"), 14
    p = _karar(m, t, ufuk=h, bar=config.BAR_1D)
    gunler = pd.date_range(t + pd.Timedelta(days=1), t + h * pd.Timedelta(days=1), freq="1D")
    beklenen = max(gunluk.loc[gunler, "high"].max(), gunluk.loc[gunler[-1], "close"]) / gunluk.loc[gunler[0], "open"] - 1
    assert pozisyon.mae(m, p) == pytest.approx(beklenen)


def test_yalnizca_onayli_pozisyon():
    z = pd.date_range(BAS, B, freq="4h")
    m = _mum(z)
    p = _karar(m, T("2025-01-05 04:00"))
    with pytest.raises(TypeError):
        pozisyon.mae(m, p.plan)
