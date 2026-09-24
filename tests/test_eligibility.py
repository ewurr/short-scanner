"""Uygunluk testleri (on-kayit §2 + rev.2, CLAUDE.md §3.6: gelecege bakis yok)."""

from __future__ import annotations

import pandas as pd

import config
from donem_yardimcisi import TOPLAM_DONEM_B, TOPLAM_DONEM_BASI  # noqa: E402
from data import eligibility as uyg


def _hacim_serisi(bas: str, gun: int, hacim: float) -> pd.Series:
    indeks = pd.date_range(bas, periods=gun, freq="D", tz="UTC")
    return pd.Series([hacim] * gun, index=indeks)


# --- Gelecege bakis ----------------------------------------------------------


def test_gelecege_bakmaz_t_sonrasi_degisiklik_sonucu_degistirmez():
    """t+1'deki hacim degisikligi t'deki sonucu degistirmemeli."""
    seri = _hacim_serisi("2021-01-01", 60, 20_000_000.0)
    t = pd.Timestamp("2021-02-10", tz="UTC")
    once = uyg.medyan_hacim(seri, t, kume_baslangic=None, donem_baslangic=TOPLAM_DONEM_BASI, pencere_gun=config.HACIM_PENCERESI_GUN)

    bozuk = seri.copy()
    bozuk.loc[bozuk.index >= t] = 0.0
    sonra = uyg.medyan_hacim(bozuk, t, kume_baslangic=None, donem_baslangic=TOPLAM_DONEM_BASI, pencere_gun=config.HACIM_PENCERESI_GUN)

    assert once == sonra


def test_t_gunu_henuz_kapanmadigi_icin_pencereye_girmez():
    seri = _hacim_serisi("2021-01-01", 60, 20_000_000.0)
    t = pd.Timestamp("2021-02-10 12:00", tz="UTC")

    bozuk = seri.copy()
    bozuk.loc[pd.Timestamp("2021-02-10", tz="UTC")] = 0.0

    assert uyg.medyan_hacim(seri, t, kume_baslangic=None, donem_baslangic=TOPLAM_DONEM_BASI, pencere_gun=config.HACIM_PENCERESI_GUN) == uyg.medyan_hacim(bozuk, t, kume_baslangic=None, donem_baslangic=TOPLAM_DONEM_BASI, pencere_gun=config.HACIM_PENCERESI_GUN)


def test_pencere_gun_varsayilansizdir():
    """F1 kapanis denetimi bulgu 9: yanlis gun sayisi sessizce gecmemeli."""
    seri = _hacim_serisi("2021-01-01", 60, 20_000_000.0)
    t = pd.Timestamp("2021-02-10", tz="UTC")
    try:
        uyg.medyan_hacim(seri, t, kume_baslangic=None, donem_baslangic=TOPLAM_DONEM_BASI)
    except TypeError:
        return
    raise AssertionError("pencere_gun verilmeden medyan_hacim calisti")


def test_pencere_dolmadan_uygunluk_verilmez():
    seri = _hacim_serisi("2021-01-01", 10, 50_000_000.0)
    t = pd.Timestamp("2021-01-08", tz="UTC")
    assert pd.isna(uyg.medyan_hacim(seri, t, kume_baslangic=None, donem_baslangic=TOPLAM_DONEM_BASI, pencere_gun=config.HACIM_PENCERESI_GUN))


# --- Listeleme donemi (rev.2) ------------------------------------------------


def test_donem_baslangicini_asan_pencere_nan_doner():
    """On-kayit rev.2: geriye bakis penceresi donem baslangicini asamaz."""
    seri = _hacim_serisi("2021-01-01", 200, 50_000_000.0)
    donem_bas = pd.Timestamp("2021-03-01", tz="UTC")

    # t, donem baslangicindan yalnizca 10 gun sonra -> 30 gunluk pencere asiyor
    erken = pd.Timestamp("2021-03-11", tz="UTC")
    assert pd.isna(uyg.medyan_hacim(seri, erken, donem_baslangic=donem_bas, kume_baslangic=None, pencere_gun=config.HACIM_PENCERESI_GUN))

    # t, donem baslangicindan 40 gun sonra -> pencere donem icinde
    gec = pd.Timestamp("2021-04-10", tz="UTC")
    assert not pd.isna(uyg.medyan_hacim(seri, gec, donem_baslangic=donem_bas, kume_baslangic=None, pencere_gun=config.HACIM_PENCERESI_GUN))


def test_pencere_donem_oncesi_veriyi_kullanmaz():
    """Donem oncesi hacim degisse bile donem ici sonuc degismemeli."""
    seri = _hacim_serisi("2021-01-01", 200, 10_000_000.0)
    donem_bas = pd.Timestamp("2021-03-01", tz="UTC")
    t = pd.Timestamp("2021-04-10", tz="UTC")

    bozuk = seri.copy()
    bozuk.loc[bozuk.index < donem_bas] = 999_000_000.0  # donem oncesi cop veri

    assert uyg.medyan_hacim(seri, t, donem_baslangic=donem_bas, kume_baslangic=None, pencere_gun=config.HACIM_PENCERESI_GUN) == uyg.medyan_hacim(bozuk, t, donem_baslangic=donem_bas, kume_baslangic=None, pencere_gun=config.HACIM_PENCERESI_GUN)


def test_listeleme_yasi_donem_basinda_sifirlanir():
    """On-kayit rev.2: yas sembolun ilk barina gore degil, DONEM basina gore."""
    seri = _hacim_serisi("2021-01-01", 400, 50_000_000.0)
    ilk_bar = pd.Timestamp("2021-01-01", tz="UTC")
    donem_bas = pd.Timestamp("2021-06-01", tz="UTC")
    t = pd.Timestamp("2021-06-20", tz="UTC")  # donemden 19 gun sonra

    # Sembolun ilk barina gore yas 170 gun; donem basina gore 19 gun.
    assert uyg.listeleme_yasi_gun(ilk_bar, t) > config.ASGARI_LISTELEME_YASI_GUN
    assert uyg.listeleme_yasi_gun(donem_bas, t) < config.ASGARI_LISTELEME_YASI_GUN

    # Donem basina gore olculdugu icin uygun DEGIL
    assert uyg.uygun_mu(seri, t, config.BAR_4H, donem_baslangic=donem_bas, kume_baslangic=None, donem_bitis=TOPLAM_DONEM_B) is False

    # 31 gun sonra uygun
    gec = pd.Timestamp("2021-07-05", tz="UTC")
    assert uyg.uygun_mu(seri, gec, config.BAR_4H, donem_baslangic=donem_bas, kume_baslangic=None, donem_bitis=TOPLAM_DONEM_B) is True


def test_donem_disindaki_bar_uygun_degildir():
    seri = _hacim_serisi("2021-01-01", 400, 50_000_000.0)
    bas = pd.Timestamp("2021-03-01", tz="UTC")
    bitis = pd.Timestamp("2021-09-30 23:59", tz="UTC")

    assert uyg.uygun_mu(seri, pd.Timestamp("2021-02-01", tz="UTC"), config.BAR_4H, donem_baslangic=bas, donem_bitis=bitis, kume_baslangic=None) is False
    assert uyg.uygun_mu(seri, pd.Timestamp("2021-10-05", tz="UTC"), config.BAR_4H, donem_baslangic=bas, donem_bitis=bitis, kume_baslangic=None) is False
    assert uyg.uygun_mu(seri, pd.Timestamp("2021-06-05", tz="UTC"), config.BAR_4H, donem_baslangic=bas, donem_bitis=bitis, kume_baslangic=None) is True


# --- Esikler -----------------------------------------------------------------


def test_hacim_esikleri_bar_tipine_gore_ayrisir():
    """5M USDT: H1/H2 (10M) icin yetersiz, H3 (2M) icin yeterli."""
    seri = _hacim_serisi("2021-01-01", 120, 5_000_000.0)
    bas = pd.Timestamp("2021-01-01", tz="UTC")
    t = pd.Timestamp("2021-03-01", tz="UTC")

    assert uyg.uygun_mu(seri, t, config.BAR_4H, donem_baslangic=bas, kume_baslangic=None, donem_bitis=TOPLAM_DONEM_B) is False
    assert uyg.uygun_mu(seri, t, config.BAR_1D, donem_baslangic=bas, kume_baslangic=None, donem_bitis=TOPLAM_DONEM_B) is True


def test_esik_degerleri_on_kayitla_ayni():
    assert uyg.hacim_esigi(config.BAR_4H) == 10_000_000.0
    assert uyg.hacim_esigi(config.BAR_1D) == 2_000_000.0
    assert config.ASGARI_LISTELEME_YASI_GUN == 30
