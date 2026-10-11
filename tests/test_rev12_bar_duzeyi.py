"""Barin mevcutlugu BAR duzeyinde (on-kayit §2, rev.12 madde (g)).

On-kayit §2: "Bu, barin mevcutlugunun genel tanimidir (rev.12): olcut alan duzeyinde degil bar
duzeyindedir ve her izgarada, her pencerede ve her hesapta gecerlidir — hucresi bozuk bir bar 4
saatlik sinyal pencerelerinde de mevcut sayilmaz, ilgili hucresi gecerli olsa bile. Islem sayisi
(`count`) bu kuralin kapsami disindadir."

Rev.12'den once `sinyal._seri` yalnizca ISTENEN alani denetliyordu; bozuk `volume` hucresi olan
bir bar `close` penceresinden sessizce geciyordu. Bu dosya kurali hem seri, hem bar degeri, hem
de gercek sinyal pencereleri duzeyinde sabitler.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

import config
from conftest import sahte_4h
from data import klines, sinyal

BAS = "2024-03-01"
KUME_BASI = pd.Timestamp("2020-01-01", tz="UTC")


def cerceve(bar_sayisi: int = 40) -> pd.DataFrame:
    return sahte_4h(BAS, bar_sayisi)


def zaman(i: int, bar_sayisi: int = 40) -> pd.Timestamp:
    return pd.DatetimeIndex(cerceve(bar_sayisi)["open_time"])[i]


def bozuk(sutun: str, i: int, deger=float("nan"), bar_sayisi: int = 40) -> pd.DataFrame:
    m = cerceve(bar_sayisi)
    m.loc[i, sutun] = deger
    return m


# --- 1. Seri duzeyi: bozuk hucre butun alanlari dusurur -------------------------------------


@pytest.mark.parametrize("sutun", klines.HUCRE_SUTUNLARI)
@pytest.mark.parametrize("alan", ("close", "high", "low", "quote_volume"))
def test_bozuk_hucre_barin_butun_alanlarini_dusurur(sutun, alan):
    """Hangi hucre bozulursa bozulsun, barin damgasi HER alanda NaN olur (rev.12)."""
    seri = sinyal._seri(bozuk(sutun, 10), alan)
    assert math.isnan(seri.loc[zaman(10)])
    # Komsu barlar etkilenmez: kural bar duzeyindedir, seri duzeyinde degil.
    assert math.isfinite(seri.loc[zaman(9)]) and math.isfinite(seri.loc[zaman(11)])


@pytest.mark.parametrize("deger", (float("inf"), float("-inf"), float("nan"), "metin"))
def test_sonlu_olmayan_ve_sayisal_olmayan_hucre_de_bari_dusurur(deger):
    """"Hucrelerinden biri NaN ya da sonlu degilse o bar eksiktir"; metin de sayi degildir."""
    m = cerceve()
    m["volume"] = m["volume"].astype(object)
    m.loc[7, "volume"] = deger
    assert math.isnan(sinyal._seri(m, "close").loc[zaman(7)])


def test_count_kapsam_disi_bari_dusurmez():
    """On-kayit §2 rev.12: "Islem sayisi (`count`) bu kuralin kapsami disindadir"."""
    assert "count" not in klines.HUCRE_SUTUNLARI
    for deger in (float("nan"), float("inf")):
        m = cerceve()
        m["count"] = m["count"].astype(float)
        m.loc[12, "count"] = deger
        assert math.isfinite(sinyal._seri(m, "close").loc[zaman(12)])


def test_olcut_klines_hucreleri_tam_mi_ile_ayni_yerden_gelir():
    """Ikinci bir kopya kalmaz: 1d turetmesi ve sinyal pencereleri ayni yuklemi kullanir."""
    m = bozuk("taker_buy_quote_volume", 5)
    tam = klines.hucreleri_tam_mi(m)
    seri = sinyal._seri(m, "close")
    assert list(np.isfinite(seri.to_numpy())) == list(tam)


def test_cercevede_bulunmayan_hucre_sutunu_denetlenmez():
    """Kismi (sentetik) cerceveler: var olmayan sutun eksik sayilmaz, yoksa her bar duserdi."""
    m = cerceve()[["open_time", "open", "high", "low", "close", "quote_volume"]].copy()
    assert bool(np.isfinite(sinyal._seri(m, "close").to_numpy()).all())


# --- 2. Bar degeri ve gercek sinyal pencereleri ----------------------------------------------


def test_bar_degeri_bozuk_komsu_hucreyle_nan():
    """`close[t]` hucresi saglam olsa bile bar mevcut degilse deger hesaplanmaz."""
    assert math.isnan(sinyal.bar_degeri(bozuk("low", 20), zaman(20), "close"))


def test_h1_dip_penceresi_bozuk_hacim_hucresiyle_hesaplanamaz():
    """`min(low[t-6..t-1])`: penceredeki bir barin HACIM hucresi bozuksa pencere tam degildir."""
    sinir = {"kume_baslangic": KUME_BASI, "donem_baslangic": pd.Timestamp(BAS, tz="UTC")}
    t = zaman(20)
    assert math.isfinite(sinyal.h1_dip(cerceve(), t, **sinir))
    assert math.isnan(sinyal.h1_dip(bozuk("quote_volume", 16), t, **sinir))


def test_h2_kirilim_dibi_bozuk_fiyat_hucresiyle_hesaplanamaz():
    sinir = {"kume_baslangic": KUME_BASI, "donem_baslangic": pd.Timestamp(BAS, tz="UTC")}
    t = zaman(20)
    assert math.isfinite(sinyal.h2_kirilim_dip(cerceve(), t, 6, **sinir))
    assert math.isnan(sinyal.h2_kirilim_dip(bozuk("open", 15), t, 6, **sinir))


def test_kapanis_30_once_bozuk_bar_tamlik_araligini_dusurur():
    """Tamlik penceresi `[t-30 .. t]`: aradaki bir barin bozuk hucresi degeri dusurur."""
    sinir = {"kume_baslangic": KUME_BASI, "donem_baslangic": pd.Timestamp(BAS, tz="UTC")}
    t = zaman(35, 50)
    assert math.isfinite(sinyal.kapanis_30_once(cerceve(50), t, config.BAR_4H, **sinir))
    assert math.isnan(sinyal.kapanis_30_once(bozuk("high", 20, bar_sayisi=50), t, config.BAR_4H, **sinir))


def test_sinir_durumu_bozuk_bar_pencerenin_disinda_kalirsa_deger_hesaplanir():
    """Kural bari dusurur, seriyi degil: pencerenin DISINDAKI bozuk bar degeri etkilemez."""
    sinir = {"kume_baslangic": KUME_BASI, "donem_baslangic": pd.Timestamp(BAS, tz="UTC")}
    assert math.isfinite(sinyal.h1_dip(bozuk("volume", 2), zaman(20), **sinir))
