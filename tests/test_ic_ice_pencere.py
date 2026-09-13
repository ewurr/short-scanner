"""Ic ice ve ofsetli pencere kapisi (F1 kapanis bulgusu 3).

H1: "son 6 barin toplam hacmi >= onceki 180 barin 6'li toplam hacim medyaninin
3 kati" -> ic ice pencere (6 barlik toplamlarin 180 barlik medyani).
H3: "gun -120 ile -31 arasindaki medyan gunluk hacim" -> ofsetli pencere.

En dogal pandas yolu `seri.rolling(6).sum()` sonucunu `pencere_degeri`ne vermektir;
kapi o zaman yalnizca DIS pencerenin damgalarini denetler: ilk toplam kume/donem
basindan onceki barlari icerir, rolling bar sayisiyla calistigi icin bosluk
uzerinden toplar. Bu testler yeni kapinin turetilmis serinin KENDISINI de tamlik,
kume, donem ve karantina kontrolunden gecirdigini dogrular.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import config
from data import pencere, split
from tarama_yardimcisi import TURETILMIS_SERI_DESENI, ihlaller

DORT_SAAT = pd.Timedelta(hours=4)
GUN = pd.Timedelta(days=1)
C2_BAS = split.kume_araligi("C2")[0]
SINIRSIZ = dict(kume_baslangic=None, donem_baslangic=None, karantina_aylari=None)
H1 = dict(dis_bar_sayisi=180, dis_t_dahil=True, dis_islev="median", ic_bar_sayisi=6, ic_t_dahil=True, ic_islev="sum")


def _seri(bas, bitis, bar=config.BAR_4H, tohum=20260911) -> pd.Series:
    indeks = pd.date_range(bas, bitis, freq=pencere.adim(bar), tz="UTC")
    rng = np.random.default_rng(tohum)
    return pd.Series(rng.uniform(1.0, 100.0, len(indeks)), index=indeks)


def _ic_ice(seri, t, **sinirlar):
    return pencere.ic_ice_pencere_degeri(seri, t, config.BAR_4H, **H1, **{**SINIRSIZ, **sinirlar})


# --- Ic ice pencere: deger ---------------------------------------------------


def test_ic_ice_deger_elle_hesapla_ayni():
    seri = _seri("2021-01-01", "2021-03-31 20:00")
    t = pd.Timestamp("2021-03-01 00:00", tz="UTC")

    toplamlar = [seri.loc[s - 5 * DORT_SAAT: s].sum() for s in pd.date_range(end=t, periods=180, freq="4h")]
    assert _ic_ice(seri, t) == pytest.approx(float(np.median(toplamlar)))


def test_ic_t_dahil_false_ic_pencereyi_bir_bar_geri_kaydirir():
    seri = _seri("2021-01-01", "2021-03-31 20:00")
    t = pd.Timestamp("2021-03-01 00:00", tz="UTC")
    parametreler = {**H1, "ic_t_dahil": False}
    toplamlar = [seri.loc[s - 6 * DORT_SAAT: s - DORT_SAAT].sum() for s in pd.date_range(end=t, periods=180, freq="4h")]
    deger = pencere.ic_ice_pencere_degeri(seri, t, config.BAR_4H, **parametreler, **SINIRSIZ)
    assert deger == pytest.approx(float(np.median(toplamlar)))


def test_ic_ice_t_sonrasi_veri_sonucu_degistirmez():
    seri = _seri("2021-01-01", "2021-03-31 20:00")
    t = pd.Timestamp("2021-03-01 00:00", tz="UTC")
    bozuk = seri.copy()
    bozuk[bozuk.index > t] = 1e12
    assert _ic_ice(seri, t) == _ic_ice(bozuk, t)


# --- Ic ice pencere: saldirilar ----------------------------------------------


def test_ic_pencere_kume_basini_asarsa_nan_turetilmis_yol_ise_sizdirir():
    """Dis pencere tam kume basinda baslar; ilk 6'li toplam kume oncesi 5 bari icerir."""
    seri = _seri("2025-07-01", "2025-11-30 20:00")
    t = C2_BAS + 179 * DORT_SAAT  # dis pencere [C2_BAS, t]

    # Turetilmis seri yolu: kapi yalnizca dis damgalari gorur ve bir deger uretir.
    toplamlar = seri.rolling(6).sum()
    sizan = pencere.pencere_degeri(toplamlar, t, 180, config.BAR_4H, t_dahil=True, islev="median", kume_baslangic=C2_BAS, donem_baslangic=None, karantina_aylari=None)
    assert not pd.isna(sizan), "kurulum: turetilmis yol sizintiyi gostermeli"

    assert pd.isna(_ic_ice(seri, t, kume_baslangic=C2_BAS))
    # Ic pencereler de kume icine girdiginde deger doner.
    assert not pd.isna(_ic_ice(seri, t + 5 * DORT_SAAT, kume_baslangic=C2_BAS))
    assert pd.isna(_ic_ice(seri, t + 4 * DORT_SAAT, kume_baslangic=C2_BAS))


def test_yalnizca_ic_pencerenin_gordugu_bosluk_nan():
    """Eksik bar dis pencerenin disinda ama ilk ic pencerenin icinde."""
    seri = _seri("2021-01-01", "2021-03-31 20:00")
    t = pd.Timestamp("2021-03-01 00:00", tz="UTC")
    dis_bas = t - 179 * DORT_SAAT
    eksik = seri.drop(dis_bas - 2 * DORT_SAAT)

    toplamlar = eksik.rolling(6).sum()  # bar sayisiyla: boslugu fark etmez
    assert not pd.isna(pencere.pencere_degeri(toplamlar, t, 180, config.BAR_4H, t_dahil=True, islev="median", **SINIRSIZ))
    assert pd.isna(_ic_ice(eksik, t))


def test_ic_pencere_donem_basini_asarsa_nan():
    seri = _seri("2021-01-01", "2021-03-31 20:00")
    t = pd.Timestamp("2021-03-01 00:00", tz="UTC")
    donem_bas = t - 179 * DORT_SAAT - 2 * DORT_SAAT
    assert pd.isna(_ic_ice(seri, t, donem_baslangic=donem_bas))
    assert not pd.isna(_ic_ice(seri, t, donem_baslangic=donem_bas - 3 * DORT_SAAT))


def test_ic_pencere_karantina_ay_sinirinda():
    """Dis pencere tam 2021-02-01 00:00'da baslar; ilk ic pencere Ocak'a uzanir."""
    seri = _seri("2021-01-01", "2021-04-30 20:00")
    t = pd.Timestamp("2021-02-01 00:00", tz="UTC") + 179 * DORT_SAAT
    assert pd.isna(_ic_ice(seri, t, karantina_aylari=["2021-01"]))
    assert not pd.isna(_ic_ice(seri, t + 5 * DORT_SAAT, karantina_aylari=["2021-01"]))


def test_nan_degerli_bar_nan():
    seri = _seri("2021-01-01", "2021-03-31 20:00")
    t = pd.Timestamp("2021-03-01 00:00", tz="UTC")
    seri.loc[t - 181 * DORT_SAAT] = float("nan")  # yalnizca ilk ic pencerede
    assert pd.isna(_ic_ice(seri, t))


# --- Ofsetli pencere (H3) ----------------------------------------------------


def _ofsetli(seri, t, **sinirlar):
    return pencere.ofsetli_pencere_degeri(
        seri, t, 90, config.BAR_1D, bitis_ofseti=31, islev="median", **{**SINIRSIZ, **sinirlar}
    )


def test_ofsetli_pencere_gun_eksi_120_ile_eksi_31():
    seri = _seri("2021-01-01", "2021-12-31", bar=config.BAR_1D)
    t = pd.Timestamp("2021-08-01", tz="UTC")
    beklenen = seri.loc[t - 120 * GUN: t - 31 * GUN]
    assert len(beklenen) == 90
    assert _ofsetli(seri, t) == pytest.approx(float(beklenen.median()))


def test_ofsetli_pencere_disindaki_gunler_etkilemez():
    seri = _seri("2021-01-01", "2021-12-31", bar=config.BAR_1D)
    t = pd.Timestamp("2021-08-01", tz="UTC")
    once = _ofsetli(seri, t)

    bozuk = seri.copy()
    bozuk.loc[t - 30 * GUN:] = 1e12  # gun -30 .. sonrasi
    bozuk.loc[: t - 121 * GUN] = 1e12  # gun -121 .. oncesi
    assert _ofsetli(bozuk, t) == once

    icerde = seri.copy()
    icerde.loc[t - 31 * GUN] = 1e12
    icerde.loc[t - 120 * GUN] = 1e12
    icerde.loc[t - 60 * GUN] = 1e12
    assert _ofsetli(icerde, t) != once


def test_ofsetli_pencere_kume_basini_asarsa_nan():
    seri = _seri("2025-01-01", "2026-03-31", bar=config.BAR_1D)
    ilk_gecerli = C2_BAS + 120 * GUN  # gun -120 = kume basi
    assert not pd.isna(_ofsetli(seri, ilk_gecerli, kume_baslangic=C2_BAS))
    assert pd.isna(_ofsetli(seri, ilk_gecerli - GUN, kume_baslangic=C2_BAS))


def test_ofsetli_pencere_tamlik_ve_donem():
    seri = _seri("2021-01-01", "2021-12-31", bar=config.BAR_1D)
    t = pd.Timestamp("2021-08-01", tz="UTC")
    assert pd.isna(_ofsetli(seri.drop(t - 100 * GUN), t))
    assert not pd.isna(_ofsetli(seri.drop(t - 10 * GUN), t))  # pencere disinda
    assert pd.isna(_ofsetli(seri, t, donem_baslangic=t - 100 * GUN))


def test_ofset_sifir_t_dahil_bir_t_haric():
    seri = _seri("2021-01-01", "2021-12-31", bar=config.BAR_1D)
    t = pd.Timestamp("2021-08-01", tz="UTC")
    for ofset, t_dahil in ((0, True), (1, False)):
        ofsetli = pencere.ofsetli_pencere_degeri(seri, t, 30, config.BAR_1D, bitis_ofseti=ofset, islev="median", **SINIRSIZ)
        duz = pencere.pencere_degeri(seri, t, 30, config.BAR_1D, t_dahil=t_dahil, islev="median", **SINIRSIZ)
        assert ofsetli == duz


# --- Zorunluluk --------------------------------------------------------------


@pytest.mark.parametrize(
    "eksik",
    ["dis_bar_sayisi", "dis_t_dahil", "dis_islev", "ic_bar_sayisi", "ic_t_dahil", "ic_islev",
     "kume_baslangic", "donem_baslangic", "karantina_aylari"],
)
def test_ic_ice_parametre_unutulursa_hata(eksik):
    seri = _seri("2021-01-01", "2021-03-31 20:00")
    parametreler = {**H1, **SINIRSIZ}
    del parametreler[eksik]
    with pytest.raises(TypeError):
        pencere.ic_ice_pencere_degeri(seri, seri.index[-1], config.BAR_4H, **parametreler)


@pytest.mark.parametrize("eksik", ["bitis_ofseti", "islev", "kume_baslangic", "donem_baslangic", "karantina_aylari"])
def test_ofsetli_parametre_unutulursa_hata(eksik):
    seri = _seri("2021-01-01", "2021-12-31", bar=config.BAR_1D)
    parametreler = {"bitis_ofseti": 31, "islev": "median", **SINIRSIZ}
    del parametreler[eksik]
    with pytest.raises(TypeError):
        pencere.ofsetli_pencere_degeri(seri, seri.index[-1], 90, config.BAR_1D, **parametreler)


@pytest.mark.parametrize("ofset, hata", [(-1, ValueError), (True, TypeError), (1.5, TypeError)])
def test_gecersiz_ofset(ofset, hata):
    seri = _seri("2021-01-01", "2021-12-31", bar=config.BAR_1D)
    with pytest.raises(hata):
        pencere.ofsetli_pencere_degeri(seri, seri.index[-1], 30, config.BAR_1D, bitis_ofseti=ofset, islev="median", **SINIRSIZ)


# --- Kapiyi atlayan yol kalmamali ---------------------------------------------


def test_analiz_kodu_turetilmis_seri_islemi_kullanmaz():
    """events/, study/ ve analizler (F2 ve sonrasi) bar sayisiyla calisan turetilmis
    seri islemleri (rolling, shift, diff, pct_change ...) kullanamaz; ic ice ve
    ofsetli pencereler yalnizca data.pencere kapisindan hesaplanir."""
    assert ihlaller(TURETILMIS_SERI_DESENI) == []


def test_tarama_turetilmis_seri_kullanimini_yakalar(tmp_path):
    (tmp_path / "events").mkdir()
    (tmp_path / "events" / "h1.py").write_text("toplam = hacim.rolling(6).sum()\n", encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "pencere.py").write_text("x = s.rolling(6).sum()\n", encoding="utf-8")
    assert ihlaller(TURETILMIS_SERI_DESENI, kok=tmp_path) == ["events/h1.py"]
