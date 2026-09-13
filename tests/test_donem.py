"""Listeleme donemi testleri (on-kayit §2, revizyon 2)."""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import donem, pencere


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


# --- Ufuk kirpma (getiri hesabinda F2'de kullanilacak) -----------------------


def _cikis(zamanlar, giris_indeksi, ufuk, donem_bitis):
    return pencere.cikis_bari(
        zamanlar, zamanlar[giris_indeksi], ufuk, config.BAR_4H,
        donem_bitis=donem_bitis, karantina_aylari=None, kume_bitis=None,
    )


def test_ufuk_donem_icindeyse_kirpilmaz():
    zamanlar = pd.date_range("2021-01-01", periods=50, freq="4h", tz="UTC")
    bitis = pd.Timestamp("2021-12-31", tz="UTC")
    # giris t+1 = indeks 5 -> t = 4 -> cikis t+18 = indeks 22 (on-kayit §4)
    assert _cikis(zamanlar, 5, 18, bitis).indeks == 22


def test_ufuk_donem_sonunu_asarsa_son_bara_kirpilir():
    """On-kayit rev.2: cikis, donemin son barinin kapanisidir."""
    zamanlar = pd.date_range("2021-01-01", periods=20, freq="4h", tz="UTC")
    bitis = pd.Timestamp("2021-12-31", tz="UTC")

    sonuc = _cikis(zamanlar, 15, 18, bitis)

    assert sonuc.indeks == 19  # son bar
    assert sonuc.zaman == zamanlar[-1] and sonuc.fiyat_alani == "close"


def test_ufuk_zaman_siniriyla_da_kirpilir():
    """Bar listesi donemden uzun olsa bile donem_bitis siniri uygulanir."""
    zamanlar = pd.date_range("2021-01-01", periods=100, freq="4h", tz="UTC")
    bitis = pd.Timestamp("2021-01-02 23:59:59", tz="UTC")  # ilk 12 bar

    sonuc = _cikis(zamanlar, 2, 18, bitis)

    assert sonuc.zaman <= bitis
    assert sonuc.indeks == 11 and sonuc.kirpma_nedeni == "donem_sonu"


def test_cikis_bar_indeksi_sarmalayicisi_kaldirildi():
    """F1 kapanis bulgusu 1: sarmalayici kume_bitis iletmiyor, fiyat_alani'ni
    kaybediyor ve bar=4h varsayilani tasiyordu. Tek kapi pencere.cikis_bari."""
    assert not hasattr(donem, "cikis_bar_indeksi")


# --- B4 / B9 -----------------------------------------------------------------


def test_donem_pencere_gecerlilik_yardimcisi_kaldirildi():
    """B4: donem.pencere_gecerli_mi, pencere.pencere_dilimi ile bir bar celisiyordu.

    [t - uzunluk, t] N+1 barlik yer isterken pencere_dilimi N bar istiyor. Uretim
    kodunda kullanilmayan olu koddu ve F2'de yanlislikla secilebilirdi. Donem
    baslangici kontrolu yalnizca data/pencere.py icinde yapilir.
    """
    assert not hasattr(donem, "pencere_gecerli_mi")


def test_ay_donemi_acik_fonksiyon():
    """B9: pencere.py artik baska modulun ozel _ay fonksiyonunu cagirmiyor."""
    assert donem.ay_donemi("2025-12") == pd.Period("2025-12", freq="M")
    assert donem.ay_donemi(pd.Period("2021-06", freq="M")) == pd.Period("2021-06", freq="M")
    assert not hasattr(donem, "_ay")

