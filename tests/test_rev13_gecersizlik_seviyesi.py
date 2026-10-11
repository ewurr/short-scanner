"""Gecersizlik (stop) seviyesi: uc hipotez, tek fonksiyon (on-kayit §5, rev.13 (c)).

On-kayit §5:
  - H1 madde 5: "Gecersizlik seviyesi (F4 icin kayit): `tepe × 1.02`"
  - H2 madde 4: "Gecersizlik seviyesi (F4 icin kayit): `max(high[t-30..t]) × 1.02`"
  - H3 madde 4 (rev.13): "`max(high[t-30..t]) × 1.02`. H3'un capasi olmadigi icin seviye H2 ile
    ayni bicimde, dusus trendi kosulunun zaten kullandigi pencereden kurulur; pencere 1 gunluk
    seridedir ve tamlik sarti §5 'Pencere sinirlari'na goredir."

Rev.13'ten once bu seviye HICBIR hipotez icin hesaplanmiyordu. Simdi tek bir fonksiyon
(`sinyal.gecersizlik_seviyesi`) ucunu de kuruyor ve deger onayli pozisyonda alan olarak
tasiniyor (on-kayit §8 madde 1: "Olay basina ham kayitta ayrica MAE ve gecersizlik seviyesi
saklanir (F4 icin)"). Hicbir F2/F3 karari bu degere bakmaz.

Aga cikmaz; getiri hesaplanmaz.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

import config
from data import pencere, pozisyon, sinyal
from kapi_yardimcisi import veri
from kume_yardimcisi import kume_adi
from sinyal_yardimcisi import kontrol, olay, yapilandirma
from uygunluk_yardimcisi import esikler

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
HACIM = 1e7
DB, B = T("2024-09-01"), T("2025-06-30 20:00")
KUME = {"kume_baslangic": T(config.KESIF_BASI.isoformat()), "kume_bitis": T(config.KESIF_SONU.isoformat())}
SINIR = {"kume_baslangic": KUME["kume_baslangic"], "donem_baslangic": DB}


def _duz(bas, son, fiyat=1.0, hacim=HACIM) -> pd.DataFrame:
    z = pd.date_range(bas, son, freq="4h")
    return pd.DataFrame({"open_time": z, "open": fiyat, "high": fiyat, "low": fiyat, "close": fiyat,
                         "quote_volume": float(hacim)})


def _fund(bas, son, oran=0.0005) -> pd.DataFrame:
    z = pd.date_range(bas, son, freq="8h")
    return pd.DataFrame({"odeme_zamani": z, "aralik_saat": 8.0, "oran": 0.0, "oran_8h": float(oran)})


def _ayarla(mumlar, zaman, **alanlar):
    m = mumlar.copy()
    maske = pd.DatetimeIndex(m["open_time"]) == pd.Timestamp(zaman)
    assert bool(maske.any())
    for alan, deger in alanlar.items():
        m.loc[maske, alan] = deger
    return m


def _aralik_ayarla(mumlar, bas, son, **alanlar):
    m = mumlar.copy()
    z = pd.DatetimeIndex(m["open_time"])
    maske = (z >= pd.Timestamp(bas)) & (z <= pd.Timestamp(son))
    assert bool(maske.any())
    for alan, deger in alanlar.items():
        m.loc[maske, alan] = deger
    return m


def _seviye(hipotez, t, mumlar, capa=None, gunluk=None):
    return sinyal.gecersizlik_seviyesi(hipotez, t, mumlar_4h=mumlar, gunluk=gunluk, capa=capa, **SINIR)


# --- 1. Carpan ve taban --------------------------------------------------------------------


def test_carpan_on_kayit_degeri_ve_degistirilemez():
    assert config.GECERSIZLIK_CARPANI == 1.02
    with pytest.raises(config.SabitDegistirilemez):
        config.GECERSIZLIK_CARPANI = 1.05


def test_h2_tabani_max_high_30_bar():
    """`max(high[t-30..t])`: aralik iki uclu ve KAPALI. t-30'daki tepe girer, t-31'deki girmez."""
    t = T("2025-03-10 04:00")
    m = _ayarla(_duz(DB, B), t - 30 * H4, high=2.0)
    assert _seviye("H2", t, m) == pytest.approx(2.0 * 1.02)
    m2 = _ayarla(_duz(DB, B), t - 31 * H4, high=2.0)
    assert _seviye("H2", t, m2) == pytest.approx(1.0 * 1.02)


def test_h2_tabani_t_barini_icerir():
    """t barinin kendi `high` degeri de tabana girer (aralik `[t-30 .. t]`)."""
    t = T("2025-03-10 04:00")
    assert _seviye("H2", t, _ayarla(_duz(DB, B), t, high=3.0)) == pytest.approx(3.0 * 1.02)


def test_h1_tabani_tepedir():
    """H1'de taban pump barindan teyit barinin BIR ONCESINE kadar gorulen en yuksek `high`;
    teyit barinin kendi `high`i girmez (on-kayit §5 H1 madde 2, rev.11)."""
    pump, teyit = T("2025-03-10 04:00"), T("2025-03-10 16:00")
    m = _ayarla(_duz(DB, B), pump + H4, high=1.5)
    m = _ayarla(m, teyit, high=9.0)        # teyit barinin high'i tepeye GIRMEZ
    tepe = sinyal.h1_tepe(m, pump, teyit, kume_baslangic=KUME["kume_baslangic"], donem_baslangic=DB)
    assert tepe == pytest.approx(1.5)
    assert _seviye("H1", teyit, m, capa=pump) == pytest.approx(1.5 * 1.02)


def test_h3_tabani_1_gunluk_seride():
    """H3'un penceresi 1 GUNLUK seridedir: 30 gun geriye uzanir, 31 gun geriye uzanmaz."""
    from data import klines

    t = T("2025-03-10")
    sinir_donem = pozisyon._DonemSiniri(DB, B)
    def _tam(mumlar):
        z = pd.DatetimeIndex(mumlar["open_time"])
        return mumlar.assign(volume=1.0, count=1, taker_buy_volume=0.0, taker_buy_quote_volume=0.0,
                             close_time=z + H4 - pd.Timedelta(milliseconds=1))

    m = _ayarla(_duz(DB, B), t - pd.Timedelta(days=30), high=2.0)
    gunluk = klines.gunluge_cevir(_tam(m), donemler=[sinir_donem])
    assert _seviye("H3", t, m, gunluk=gunluk) == pytest.approx(2.0 * 1.02)
    m2 = _ayarla(_duz(DB, B), t - pd.Timedelta(days=31), high=2.0)
    gunluk2 = klines.gunluge_cevir(_tam(m2), donemler=[sinir_donem])
    assert _seviye("H3", t, m2, gunluk=gunluk2) == pytest.approx(1.0 * 1.02)


def test_h2_ve_h3_ayni_pencereyi_paylasir():
    """Rev.13 gerekcesi: "H3'un capasi olmadigi icin seviye H2 ile ayni bicimde ... kurulur."
    Tamlik penceresi `close[t-30]` ile de aynidir (§5 "Pencere sinirlarinin tamami")."""
    t = T("2025-03-10 04:00")
    m = _duz(DB, B)
    eksik = m.loc[pd.DatetimeIndex(m["open_time"]) != t - 20 * H4].reset_index(drop=True)
    assert math.isnan(_seviye("H2", t, eksik))
    assert math.isnan(sinyal.kapanis_30_once(eksik, t, config.BAR_4H,
                                             kume_baslangic=KUME["kume_baslangic"], donem_baslangic=DB))


# --- 2. Sozlesme: capa yalnizca H1'de ------------------------------------------------------


def test_capa_sozlesmesi_sinyal_degerleriyle_ayni():
    t = T("2025-03-10 04:00")
    m = _duz(DB, B)
    with pytest.raises(ValueError, match="capa"):
        _seviye("H1", t, m, capa=None)
    for hipotez in ("H2", "H3"):
        with pytest.raises(ValueError, match="capa"):
            _seviye(hipotez, t, m, capa=t)


def test_tamlik_donem_basini_asan_pencerede_nan():
    """Pencere donem basini asarsa deger hesaplanmaz (on-kayit §2 "Tamlik sarti")."""
    db = T("2025-03-01")
    m = _duz(db, B)
    assert math.isnan(sinyal.gecersizlik_seviyesi("H2", db + 5 * H4, mumlar_4h=m, gunluk=None,
                                                  capa=None, donem_baslangic=db,
                                                  kume_baslangic=KUME["kume_baslangic"]))
    assert math.isfinite(sinyal.gecersizlik_seviyesi("H2", db + 40 * H4, mumlar_4h=m, gunluk=None,
                                                     capa=None, donem_baslangic=db,
                                                  kume_baslangic=KUME["kume_baslangic"]))


# --- 3. Onayli pozisyonda alan olarak tasinir (on-kayit §8 madde 1) ------------------------

FUND = _fund(DB, B + H4)
T2 = T("2025-03-10 04:00")
P1 = T("2025-03-10 04:00")
T1 = P1 + 3 * H4


def _karar(hipotez, mumlar, t, **ek):
    tanim = pencere.hipotez_ufuklari(hipotez)
    return pozisyon.olay_karari(t, tanim.birincil, tanim.bar, hipotez=hipotez,
                                birincil_ufuk=tanim.birincil, kume=kume_adi(t),
                                **veri(mumlar, FUND, DB, B, uygun_bas=DB, hacim=6 * HACIM),
                                **ek, **esikler(tanim.bar))


def _h2_olay_serisi(tepe=2.0) -> pd.DataFrame:
    m = _aralik_ayarla(_duz(DB, B), T2 - 3 * H4, T2 - H4, low=1.5, high=1.5, close=1.0, open=1.0)
    m = _ayarla(m, T2 - 10 * H4, high=float(tepe))
    return _ayarla(m, T2, close=1.2, high=1.2, low=1.2, open=1.2)


def test_h2_olayinda_seviye_alan_olarak_tasinir():
    p = _karar("H2", _h2_olay_serisi(tepe=2.0), T2, **olay("H2"))
    assert p.gecersizlik_seviyesi == pytest.approx(2.0 * 1.02)
    pozisyon.onay_dogrula(p)


def test_h1_olayinda_seviye_tepeye_dayanir():
    m = _aralik_ayarla(_duz(DB, B), P1 - 5 * H4, P1, quote_volume=3 * HACIM)
    m = _ayarla(m, P1, close=1.25, high=1.30, low=1.0, open=1.0)
    p = _karar("H1", m, T1, **olay("H1", capa=P1))
    assert p.gecersizlik_seviyesi == pytest.approx(1.30 * 1.02)


def test_kontrol_barinda_seviye_tanimsiz():
    """Seviye OLAY basina kayittir (on-kayit §8 madde 1); kontrol barinda tanimsizdir (NaN)."""
    for rol in ("K1", "K2"):
        p = _karar("H2", _duz(DB, B), T2, **kontrol("H2", rol))
        assert math.isnan(p.gecersizlik_seviyesi)


def test_seviye_imzaya_baglidir():
    """Elle degistirilmis seviye `onay_dogrula`da reddedilir (kayit guvenilir olmali)."""
    import dataclasses

    p = _karar("H2", _h2_olay_serisi(), T2, **olay("H2"))
    with pytest.raises(ValueError):
        pozisyon.onay_dogrula(dataclasses.replace(p, gecersizlik_seviyesi=1.0))
