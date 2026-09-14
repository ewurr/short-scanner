"""Listeleme donemi testleri (on-kayit §2 rev.7).

Donem bar duzeyindedir: sifir olmayan hacimli ilk barda baslar, son barda biter;
6+ ardisik sifir hacimli bar (dolgu) ve 7 gunden uzun eksik bar boslugu donemi
boler. Karantina kurali yoktur. Testler sentetik veriyle calisir; gercek
`universe.csv`'ye bagli degildir.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import config
from data import donem, pencere

DORT_SAAT = pd.Timedelta(hours=4)


def _seri(bas: str, adet: int, hacim: float = 1e6) -> tuple[pd.DatetimeIndex, np.ndarray]:
    return pd.date_range(bas, periods=adet, freq="4h", tz="UTC"), np.full(adet, hacim)


def _donemler(z, h):
    return donem.listeleme_donemleri(z, h, config.BAR_4H)


# --- Sabitler ----------------------------------------------------------------


def test_esikler_config_ten_gelir():
    assert config.DOLGU_KOSU_ESIGI_BAR == 6
    assert pd.Timedelta(config.AZAMI_EKSIK_BAR_BOSLUGU) == pd.Timedelta(days=7)
    assert not hasattr(config, "AZAMI_BOSLUK_AY")


# --- Temel -------------------------------------------------------------------


def test_kesintisiz_seri_tek_donem_bar_duzeyinde():
    z, h = _seri("2021-01-05 08:00", 50)
    d = _donemler(z, h)
    assert d == [donem.Donem(z[0], z[-1], 50, 50)]


def test_donem_ilk_ve_son_gercek_barla_sinirli():
    """Bastaki ve sondaki sifir hacimli barlar (esikten kisa olsa bile) donem disidir."""
    z, h = _seri("2021-01-01", 40)
    h[:3] = 0  # bas: 3 bar
    h[-2:] = 0  # son: 2 bar
    d = _donemler(z, h)
    assert len(d) == 1 and d[0].baslangic == z[3] and d[0].bitis == z[-3]
    assert d[0].bar_sayisi == 35 and d[0].gercek_bar_sayisi == 35


def test_tamami_sifir_seride_donem_yok():
    z, h = _seri("2021-01-01", 30, hacim=0.0)
    assert _donemler(z, h) == []


def test_bos_seri():
    assert donem.listeleme_donemleri(pd.DatetimeIndex([], tz="UTC"), np.array([]), config.BAR_4H) == []


def test_nan_hacim_gercek_islem_sayilmaz():
    z, h = _seri("2021-01-01", 20)
    h[-4:] = np.nan
    assert _donemler(z, h)[0].bitis == z[-5]


# --- Dolgu kosusu ------------------------------------------------------------


def test_alti_barlik_sifir_kosusu_donemi_boler():
    z, h = _seri("2021-01-01", 40)
    h[10:16] = 0  # 6 bar
    d = _donemler(z, h)
    assert [(x.baslangic, x.bitis) for x in d] == [(z[0], z[9]), (z[16], z[-1])]


def test_bes_barlik_sifir_kosusu_donemi_bolmez():
    z, h = _seri("2021-01-01", 40)
    h[10:15] = 0  # 5 bar
    d = _donemler(z, h)
    assert len(d) == 1 and d[0].bar_sayisi == 40 and d[0].gercek_bar_sayisi == 35


def test_delist_sonrasi_dolgu_donem_sonunu_belirler():
    """V1 deseni (AGIX, WAVES...): uzlasma sonrasi seri sifir hacimle surer."""
    z, h = _seri("2024-06-01", 300)
    h[120:] = 0
    d = _donemler(z, h)
    assert len(d) == 1 and d[0].bitis == z[119]


def test_ic_dolgu_ve_yeniden_listeleme_iki_donem():
    """CVCUSDT deseni: delist, uzun dolgu, ayni seride yeniden listeleme."""
    z, h = _seri("2022-11-20", 1000)
    h[50:900] = 0
    d = _donemler(z, h)
    assert [(x.baslangic, x.bitis) for x in d] == [(z[0], z[49]), (z[900], z[-1])]


def test_dolgu_kosulari_denetim_ciktisi():
    z, h = _seri("2021-01-01", 60)
    h[:7] = 0
    h[20:30] = 0
    h[40:43] = 0  # kisa, dolgu degil
    h[-8:] = 0
    kosular = donem.dolgu_kosulari(z, h, config.BAR_4H)
    assert [(k.konum, k.bar_sayisi) for k in kosular] == [("bas", 7), ("ic", 10), ("son", 8)]
    assert [(k.baslangic, k.bar_sayisi) for k in donem.kisa_sifir_kosulari(z, h, config.BAR_4H)] == [(z[40], 3)]


# --- Eksik bar boslugu -------------------------------------------------------


def test_yedi_gunden_uzun_eksik_bar_boslugu_donemi_boler():
    z, h = _seri("2021-01-01", 200)
    bosluk = pd.date_range(z[50], periods=43, freq="4h")  # 43 x 4s = 7 gun 4 saat eksik
    maske = ~z.isin(bosluk)
    d = _donemler(z[maske], h[maske])
    assert [(x.baslangic, x.bitis) for x in d] == [(z[0], z[49]), (z[93], z[-1])]


def test_tam_yedi_gunluk_eksik_bar_boslugu_donemi_bolmez():
    z, h = _seri("2021-01-01", 200)
    bosluk = pd.date_range(z[50], periods=42, freq="4h")  # tam 7 gun eksik
    maske = ~z.isin(bosluk)
    assert len(_donemler(z[maske], h[maske])) == 1


def test_borsa_kesintisi_donemi_bolmez():
    """2022-02-26 kesintisi: 18 bar (72 saat) eksik."""
    z, h = _seri("2022-02-20", 100)
    maske = ~z.isin(pd.date_range("2022-02-26", periods=18, freq="4h", tz="UTC"))
    assert len(_donemler(z[maske], h[maske])) == 1


# --- Girdi dogrulama ---------------------------------------------------------


def test_sirasiz_ya_da_tekrarli_zaman_hata_verir():
    z, h = _seri("2021-01-01", 20)
    with pytest.raises(pencere.ZamanDizisiHatasi):
        _donemler(z[::-1], h)
    with pytest.raises(pencere.ZamanDizisiHatasi):
        _donemler(z.append(z[-1:]), np.r_[h, 1.0])


def test_uzunluk_uyusmazsa_hata():
    z, h = _seri("2021-01-01", 20)
    with pytest.raises(ValueError):
        _donemler(z, h[:-1])


# --- Tablo ve arama ----------------------------------------------------------


def test_donem_sinirlari_bar_duzeyinde_tablo():
    z, h = _seri("2021-01-05 08:00", 30)
    h[10:20] = 0
    tablo = donem.donem_sinirlari(_donemler(z, h))
    assert list(tablo["donem_id"]) == [0, 1]
    assert tablo.loc[0, "donem_baslangic"] == pd.Timestamp("2021-01-05 08:00", tz="UTC")
    assert tablo.loc[0, "donem_bitis"] == z[9]
    assert tablo.loc[1, "donem_baslangic"] == z[20]


def test_donem_bul_bar_duzeyinde():
    z, h = _seri("2021-01-01", 40)
    h[10:20] = 0
    d = _donemler(z, h)
    assert donem.donem_bul(z[5], d) == 0
    assert donem.donem_bul(z[15], d) is None  # dolgu bari
    assert donem.donem_bul(z[25], d) == 1
    with pytest.raises(TypeError):
        donem.donem_bul(z[5].tz_localize(None), d)


def test_ay_duzeyi_mantik_kaldirildi():
    """Rev.7: donem sinirlari ay duzeyinde degil; ay yardimcisi ve karantina yok."""
    assert not hasattr(donem, "ay_donemi")
    assert not hasattr(donem, "karantinada_mi")


# --- Ufuk kirpma (cikis_bari ile donem_bitis) ---------------------------------


def _cikis(zamanlar, giris_indeksi, ufuk, donem_bitis):
    return pencere.cikis_bari(
        zamanlar, zamanlar[giris_indeksi], ufuk, config.BAR_4H,
        donem_bitis=donem_bitis, kume_bitis=None, birincil_ufuk=18,
    )


def test_ufuk_donem_icindeyse_kirpilmaz():
    zamanlar = pd.date_range("2021-01-01", periods=50, freq="4h", tz="UTC")
    # giris t+1 = indeks 5 -> t = 4 -> cikis t+18 = indeks 22 (on-kayit §4)
    assert _cikis(zamanlar, 5, 18, zamanlar[-1]).indeks == 22


def test_ufuk_donem_sonunu_asarsa_donemin_son_barina_kirpilir():
    """Rev.7: donem_bitis son gercek barin acilisidir; cikis o barin kapanisi."""
    zamanlar = pd.date_range("2021-01-01", periods=100, freq="4h", tz="UTC")
    donem_bitis = zamanlar[11]  # sonrasi dolgu olsaydi donem burada biterdi
    sonuc = _cikis(zamanlar, 2, 18, donem_bitis)
    assert sonuc.indeks == 11 and sonuc.kirpma_nedeni == "donem_sonu" and sonuc.fiyat_alani == "close"


def test_cikis_bar_indeksi_sarmalayicisi_kaldirildi():
    """F1 kapanis bulgusu 1: sarmalayici kume_bitis iletmiyordu. Tek kapi pencere.pozisyon_plani."""
    assert not hasattr(donem, "cikis_bar_indeksi")


def test_donem_pencere_gecerlilik_yardimcisi_kaldirildi():
    """B4: donem baslangici kontrolu yalnizca data/pencere.py icinde yapilir."""
    assert not hasattr(donem, "pencere_gecerli_mi")
