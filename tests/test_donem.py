"""Listeleme donemi testleri (on-kayit §2, revizyon 2)."""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import donem


def test_karantinasiz_kesintisiz_seri_tek_donem():
    aylar = ["2021-01", "2021-02", "2021-03", "2021-04"]
    assert donem.listeleme_donemleri(aylar) == [
        (pd.Period("2021-01"), pd.Period("2021-04"))
    ]


def test_karantina_ayi_donemi_boler():
    """TLMUSDT/BNXUSDT deseni: sozlesme yerinde kapatilip yeniden aciliyor."""
    aylar = ["2021-11", "2021-12", "2022-01", "2022-02", "2022-03"]
    donemler = donem.listeleme_donemleri(aylar, karantina_aylari=["2022-01"])

    assert donemler == [
        (pd.Period("2021-11"), pd.Period("2021-12")),
        (pd.Period("2022-02"), pd.Period("2022-03")),
    ]
    # Karantina ayi hicbir donemin icinde degil
    for bas, son in donemler:
        assert not (bas <= pd.Period("2022-01") <= son)


def test_ardisik_karantina_aylari_tek_bolme_yapar():
    aylar = ["2022-03", "2022-04", "2022-05", "2022-06", "2022-07"]
    donemler = donem.listeleme_donemleri(aylar, karantina_aylari=["2022-04", "2022-05"])
    assert donemler == [
        (pd.Period("2022-03"), pd.Period("2022-03")),
        (pd.Period("2022-06"), pd.Period("2022-07")),
    ]


def test_uc_aydan_uzun_bosluk_donemi_boler():
    # 2021-02 ile 2021-07 arasi 4 ay eksik -> boler
    aylar = ["2021-01", "2021-02", "2021-07", "2021-08"]
    assert donem.listeleme_donemleri(aylar) == [
        (pd.Period("2021-01"), pd.Period("2021-02")),
        (pd.Period("2021-07"), pd.Period("2021-08")),
    ]


def test_uc_aylik_bosluk_donemi_bolmez():
    # 2021-02 ile 2021-06 arasi tam 3 ay eksik -> esik "uzun" oldugu icin bolmez
    aylar = ["2021-01", "2021-02", "2021-06"]
    assert donem.listeleme_donemleri(aylar) == [
        (pd.Period("2021-01"), pd.Period("2021-06"))
    ]


def test_esik_config_ten_gelir():
    assert config.AZAMI_BOSLUK_AY == 3


def test_donem_sinirlari_utc_zaman_damgasi():
    sinirlar = donem.donem_sinirlari([(pd.Period("2021-01"), pd.Period("2021-02"))])
    satir = sinirlar.iloc[0]

    assert satir["donem_baslangic"] == pd.Timestamp("2021-01-01 00:00", tz="UTC")
    assert satir["donem_bitis"] >= pd.Timestamp("2021-02-28 23:59", tz="UTC")
    assert satir["donem_bitis"] < pd.Timestamp("2021-03-01", tz="UTC")
    assert satir["donem_id"] == 0


def test_karantinada_mi():
    assert donem.karantinada_mi(pd.Timestamp("2022-01-15", tz="UTC"), ["2022-01"]) is True
    assert donem.karantinada_mi(pd.Timestamp("2022-02-01", tz="UTC"), ["2022-01"]) is False
    assert donem.karantinada_mi(pd.Timestamp("2022-01-15", tz="UTC"), []) is False


def test_donem_bul():
    donemler = [
        (pd.Period("2021-01"), pd.Period("2021-03")),
        (pd.Period("2021-06"), pd.Period("2021-08")),
    ]
    assert donem.donem_bul(pd.Timestamp("2021-02-10", tz="UTC"), donemler) == 0
    assert donem.donem_bul(pd.Timestamp("2021-07-10", tz="UTC"), donemler) == 1
    assert donem.donem_bul(pd.Timestamp("2021-04-10", tz="UTC"), donemler) is None


def test_pencere_gecerli_mi():
    bas = pd.Timestamp("2021-01-01", tz="UTC")
    otuz = pd.Timedelta(days=30)

    assert donem.pencere_gecerli_mi(pd.Timestamp("2021-02-15", tz="UTC"), bas, otuz) is True
    assert donem.pencere_gecerli_mi(pd.Timestamp("2021-01-10", tz="UTC"), bas, otuz) is False


# --- Ufuk kirpma (getiri hesabinda F2'de kullanilacak) -----------------------


def test_ufuk_donem_icindeyse_kirpilmaz():
    zamanlar = pd.date_range("2021-01-01", periods=50, freq="4h", tz="UTC")
    bitis = pd.Timestamp("2021-12-31", tz="UTC")
    assert donem.cikis_bar_indeksi(zamanlar, giris_indeksi=5, ufuk=18, donem_bitis=bitis) == 23


def test_ufuk_donem_sonunu_asarsa_son_bara_kirpilir():
    """On-kayit rev.2: cikis, donemin son barinin kapanisidir."""
    zamanlar = pd.date_range("2021-01-01", periods=20, freq="4h", tz="UTC")
    bitis = pd.Timestamp("2021-12-31", tz="UTC")

    indeks = donem.cikis_bar_indeksi(zamanlar, giris_indeksi=15, ufuk=18, donem_bitis=bitis)

    assert indeks == 19  # son bar
    assert zamanlar[indeks] == zamanlar[-1]


def test_ufuk_zaman_siniriyla_da_kirpilir():
    """Bar listesi donemden uzun olsa bile donem_bitis siniri uygulanir."""
    zamanlar = pd.date_range("2021-01-01", periods=100, freq="4h", tz="UTC")
    bitis = pd.Timestamp("2021-01-02 23:59:59", tz="UTC")  # ilk 12 bar

    indeks = donem.cikis_bar_indeksi(zamanlar, giris_indeksi=2, ufuk=18, donem_bitis=bitis)

    assert zamanlar[indeks] <= bitis
    assert indeks == 11


def test_gecersiz_giris_indeksi_hata_verir():
    zamanlar = pd.date_range("2021-01-01", periods=10, freq="4h", tz="UTC")
    with pytest.raises(IndexError):
        donem.cikis_bar_indeksi(zamanlar, 99, 1, pd.Timestamp("2021-12-31", tz="UTC"))
