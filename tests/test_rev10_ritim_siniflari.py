"""Pozisyonun funding ritmi sinifi (on-kayit §4 "Pozisyonun funding ritmi", rev.10; "F2 sarti").

"Bir pozisyonun funding ritmi, ... kayit dizisinin (capadan pencere sonundaki son kayda kadar) son
kaydinin aralik alanidir, saat cinsinden ... Dizideki butun kayitlarin aralik alani ayni degilse
pozisyon ayrica 'karisik ritimli' isaretlenir ve yine son kaydin araligina gore siniflanir;
karisik ritimlilerin payi her sinifta ayrica yazilir. Aralik alani 8, 4, 2 ya da 1 saat disinda bir
degerse pozisyon 'siniflanmamis' sinifinda raporlanir. Capasi olmayan pozisyon olusmadigi icin
siniflanmaz."

Kodda sinif adi `funding.RITIM_SINIFLANMAMIS` ("siniflanmamis"). Aga cikmaz.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

import config
from data import funding, pozisyon
from sinyal_yardimcisi import sinyal
from kapi_yardimcisi import donem, veri
from kume_yardimcisi import kume_adi
from uygunluk_yardimcisi import esikler, uygunluk

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
DB, B = T("2025-01-01"), T("2025-04-10 20:00")
Z = pd.date_range(T("2025-03-01"), B, freq="4h")
MUM = pd.DataFrame({"open_time": Z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
SINYAL = T("2025-03-05 04:00")  # giris 08:00, birincil ufuk 18 bar -> cikis 03-08 08:00


def _fund(parcalar):
    z, a = [], []
    for bas, son, saat in parcalar:
        r = pd.date_range(T(bas), T(son), freq=pd.Timedelta(hours=saat))
        z += list(r)
        a += [float(saat)] * len(r)
    return pd.DataFrame({"odeme_zamani": pd.DatetimeIndex(z), "aralik_saat": a, "oran": 0.0, "oran_8h": 0.0})


def _karar(fr):
    return pozisyon.olay_karari(SINYAL, 18, config.BAR_4H, hipotez="H1", birincil_ufuk=18, kume=kume_adi(SINYAL), **veri(MUM, fr, DB, B, uygun_bas=DB), sinyal_degerleri=sinyal("H1"),
                                **esikler(config.BAR_4H))


def test_sinif_adlari():
    assert funding.RITIM_SINIFLANMAMIS == "siniflanmamis"
    assert funding.RITIM_SINIFLARI == ("8", "4", "2", "1", "siniflanmamis")


@pytest.mark.parametrize("saat, sinif", [
    (8.0, "8"), (4.0, "4"), (2.0, "2"), (1.0, "1"), (8, "8"), (np.float64(4.0), "4"),
    (16.0, "siniflanmamis"), (3.0, "siniflanmamis"), (0.5, "siniflanmamis"), (6.0, "siniflanmamis"),
    (np.inf, "siniflanmamis"), (-8.0, "siniflanmamis"), (8.000001, "siniflanmamis")])
def test_ritim_sinifi(saat, sinif):
    assert funding.ritim_sinifi(saat) == sinif


def test_capa_yoksa_siniflanmaz():
    assert funding.ritim_sinifi(float("nan")) is None
    seri = pd.DataFrame({"odeme_zamani": pd.DatetimeIndex([T("2025-01-02 08:00")]), "aralik_saat": [8.0]})
    a = funding.funding_tamlik_ayrintisi(seri, [T("2025-01-02")], [T("2025-01-02 12:00")], donem_baslari=[DB]).iloc[0]
    assert a["ritim_sinifi"] is None


@pytest.mark.parametrize("parcalar, sinif, karisik", [
    ([("2025-01-01", "2025-04-10 20:00", 8)], "8", False),
    ([("2025-01-01", "2025-04-10 20:00", 2)], "2", False),
    ([("2025-01-01", "2025-03-06 00:00", 8), ("2025-03-06 04:00", "2025-04-10 20:00", 4)], "4", True),
    ([("2025-01-01", "2025-03-06 00:00", 4), ("2025-03-06 08:00", "2025-04-10 16:00", 8)], "8", True),
    # 8'den 16 saate (ornek, veride yok): son kaydin araligi 16 -> siniflanmamis, karisik.
    ([("2025-01-01", "2025-03-06 00:00", 8), ("2025-03-06 16:00", "2025-04-10 16:00", 16)], "siniflanmamis", True),
])
def test_onayli_pozisyonda_sinif_ve_karisik(parcalar, sinif, karisik):
    p = _karar(_fund(parcalar))
    assert p.ritim_sinifi == sinif
    assert p.karisik_ritim is karisik
    assert p.ritim_sinifi == funding.ritim_sinifi(p.funding_ritmi_saat)


def test_sinif_imzali():
    p = _karar(_fund([("2025-01-01", "2025-04-10 20:00", 8)]))
    sahte = replace(p, ritim_sinifi="4")
    with pytest.raises(ValueError):
        pozisyon.onay_dogrula(sahte)


def test_ozet_her_sinifta_karisik_payini_ayri_verir():
    siniflar = ["8", "8", "4", "siniflanmamis", "8", "1", "4"]
    karisik = [False, True, True, True, False, False, False]
    ozet = funding.ritim_sinifi_ozeti(siniflar, karisik)
    assert list(ozet.index) == list(funding.RITIM_SINIFLARI)
    assert ozet.loc["8", "pozisyon"] == 3 and ozet.loc["8", "karisik"] == 1
    assert ozet.loc["4", "pozisyon"] == 2 and ozet.loc["4", "karisik"] == 1
    assert ozet.loc["2", "pozisyon"] == 0 and ozet.loc["2", "karisik"] == 0
    assert ozet.loc["1", "pozisyon"] == 1 and ozet.loc["1", "karisik"] == 0
    assert ozet.loc["siniflanmamis", "pozisyon"] == 1 and ozet.loc["siniflanmamis", "karisik"] == 1
    assert ozet.loc["8", "karisik_payi"] == pytest.approx(1 / 3)
    assert np.isnan(ozet.loc["2", "karisik_payi"])


def test_ozet_bilinmeyen_sinifi_reddeder():
    with pytest.raises(ValueError):
        funding.ritim_sinifi_ozeti(["8", "diger"], [False, False])
    with pytest.raises(ValueError):
        funding.ritim_sinifi_ozeti([None], [False])  # capasiz pozisyon siniflanmaz
    with pytest.raises(ValueError):
        funding.ritim_sinifi_ozeti(["8"], [False, True])
