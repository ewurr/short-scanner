"""F2 ritim sinifi (Rev.10 icin kullanici karari; on-kayda Rev.10'da yazilacak): pozisyonun funding
ritmi dizideki son kaydin araligidir; ritim pencere icinde degistiyse ayrica `karisik_ritim`.
Tek kaynak `funding.funding_tamlik_ayrintisi`; `pozisyon.olay_karari` onayli pozisyona tasir. Aga cikmaz.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

import config
from data import funding, pozisyon
from uygunluk_yardimcisi import uygunluk

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
DB, B = T("2025-01-01"), T("2025-04-10 20:00")
Z = pd.date_range(T("2025-03-01"), B, freq="4h")
MUM = pd.DataFrame({"open_time": Z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})


def _fund(parcalar):
    z, a = [], []
    for bas, son, saat in parcalar:
        r = pd.date_range(T(bas), T(son), freq=f"{saat}h")
        z += list(r)
        a += [float(saat)] * len(r)
    return pd.DataFrame({"odeme_zamani": pd.DatetimeIndex(z), "aralik_saat": a, "oran": 0.0, "oran_8h": 0.0})


def _karar(fr, ufuk=3):
    return pozisyon.olay_karari(MUM, fr, T("2025-03-05 04:00"), ufuk, config.BAR_4H, birincil_ufuk=18,
                                kume_baslangic=None, kume_bitis=None, donem_baslangic=DB, donem_bitis=B,
                                sinyal_degerleri={"x": 1.0}, **uygunluk(config.BAR_4H, DB, B))


def test_tek_ritim():
    p = _karar(_fund([("2025-01-01", "2025-04-10 20:00", 8)]))
    assert p.funding_ritmi_saat == 8.0 and not p.karisik_ritim


def test_karisik_ritimde_sinif_son_kaydin_araligi():
    """8 saatten 4 saate: capa 8h, pencerenin son kaydi 4h -> sinif 4, karisik."""
    fr = _fund([("2025-01-01", "2025-03-05 08:00", 8), ("2025-03-05 12:00", "2025-04-10 20:00", 4)])
    p = _karar(fr)
    assert p.funding_ritmi_saat == 4.0 and p.karisik_ritim
    assert p.capa_aralik_saat == 8.0 and p.son_aralik_saat == 4.0 and not p.tek_ritim


def test_capa_yoksa_sinif_nan_ve_karisik_degil():
    seri = pd.DataFrame({"odeme_zamani": pd.DatetimeIndex([T("2025-01-02 08:00")]), "aralik_saat": [8.0]})
    a = funding.funding_tamlik_ayrintisi(seri, [T("2025-01-02")], [T("2025-01-02 12:00")], donem_baslari=[DB]).iloc[0]
    assert np.isnan(a["funding_ritmi_saat"]) and not a["karisik_ritim"]


def test_sinif_ve_bayrak_gercek_satirla_ayni_ve_imzali():
    fr = _fund([("2025-01-01", "2025-03-05 08:00", 8), ("2025-03-05 12:00", "2025-04-10 20:00", 4)])
    p = _karar(fr)
    a = funding.pozisyon_funding_ayrintisi(fr, p.plan)
    assert (p.funding_ritmi_saat, p.karisik_ritim) == (a["funding_ritmi_saat"], bool(a["karisik_ritim"]))
    for alan, deger in (("funding_ritmi_saat", 8.0), ("karisik_ritim", False)):
        with pytest.raises(ValueError):
            pozisyon.pozisyon_fiyatlari(replace(p, **{alan: deger}))
