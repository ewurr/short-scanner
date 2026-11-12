"""Performans 2b-2, 0. asama: kapiya baglanmadan once kapanan bulgular (RESULTS §14.48 kararlari, §14.49). Aga cikmaz.

Her madde kendi basligi altinda; test adlari madde koduyla baslar. Degerler yazdirilmaz; testler yalnizca esitligi,
NaN konumunu ve hata sinifini sinar. Sentetik dunya `tests/test_seri_kurucu.py`nin yardimcilaridir.
"""

from __future__ import annotations

import functools

import numpy as np
import pandas as pd
import pytest

import config
from data import _skaler_referans as ref
from data import pencere, seri_kurucu as sk

import test_seri_kurucu as tsk
from test_seri_kurucu import BAS, G, H, U, ayni, uyusmayan

S_FUNDING = {"kume_baslangic": None, "kume_bitis": None, "donem_baslangic": BAS}


# --- D-B1: cok barli izgarada funding gelecege bakis ve oran dilimi ------------------------------------------------

def _uzun_izgara(n=60, bas=U("2024-05-01 00:00")):
    m = tsk.mumlar()
    z = tsk.izgara_4h(m)
    z = z[z >= bas][:n]
    assert len(z) == n >= 50
    return z


def _sonrasini_boz(f: pd.DataFrame, kapanis: pd.Timestamp, kip: str) -> pd.DataFrame:
    """t'nin kapanisindan (tolerans payinin disinda) SONRAKI funding kayitlarini bozar, degistirir ya da ekler."""
    f = f.copy()
    f["oran_8h"] = f["oran_8h"].astype(float)
    sonra = f["odeme_zamani"] > kapanis + pd.Timedelta(minutes=1)
    if kip == "bozuk":
        f.loc[sonra, "oran_8h"] = np.nan
    elif kip == "degistirilmis":
        f.loc[sonra, "oran_8h"] = f.loc[sonra, "oran_8h"] * 1000 + 1e-3
    else:  # eklenmis: kapanistan sonra ızgara disi zamanlarda iki yeni kayit
        ek = pd.DataFrame({"odeme_zamani": [kapanis + pd.Timedelta(hours=2), kapanis + pd.Timedelta(hours=13)],
                           "aralik_saat": [8.0, 8.0], "oran": [5e-2, -5e-2], "oran_8h": [5e-2, -5e-2]})
        f = pd.concat([f, ek], ignore_index=True).sort_values("odeme_zamani", kind="stable").reset_index(drop=True)
    return f


@pytest.mark.parametrize("kip", ["bozuk", "degistirilmis", "eklenmis"])
@pytest.mark.parametrize("j", [3, 10])
def test_D_B1_cok_barli_izgarada_sonraki_funding_erken_t_yi_degistirmez(kip, j):
    """60 barlik izgara; erken bir t'nin kapanisindan sonraki funding kaydi bozulur / degisir / eklenir. Seri yolunda
    t ve ondan onceki her barin `funding_24s` degeri degismez ve skalerle bit duzeyinde aynidir. Bozmanin etkili oldugu
    da sinanir: sonraki barlardan en az biri degisir (yoksa test bir sey olcmezdi)."""
    z = _uzun_izgara()
    f = tsk.fonlama()
    temel = sk.h2_funding_24s(f, z, **S_FUNDING)
    t = z[j]
    f2 = _sonrasini_boz(f, t + H(1), kip)
    yeni = sk.h2_funding_24s(f2, z, **S_FUNDING)
    skaler = [ref.h2_funding_24s(f2, x, **S_FUNDING) for x in z[:j + 1]]
    assert np.isfinite(temel[:j + 1]).all(), "kurulum: erken barlarin degeri hesaplanabilir olmali"
    assert uyusmayan(yeni[:j + 1], temel[:j + 1]) == 0
    assert uyusmayan(yeni[:j + 1], skaler) == 0
    assert any(not ayni(yeni[i], temel[i]) for i in range(j + 1, len(z))), "kurulum: bozma sonraki barlari etkilemeli"


def _bagimsiz_dilim(f: pd.DataFrame, t: pd.Timestamp) -> tuple[int, int]:
    """t penceresinin kayitlari, `funding.sinyal_penceresi_ayrintisi`ndan BAGIMSIZ: (kapanis - 24 saat, kapanis],
    iki uc da tolerans payiyla (on-kayit §4 "Zaman toleransi": 1 dakikadan kucuk fark ayni an)."""
    zaman = pd.DatetimeIndex(f["odeme_zamani"])
    kapanis = t + H(1)
    bas = kapanis - pd.Timedelta(hours=config.H2_FUNDING_PENCERESI_SAAT)
    tol = pd.Timedelta(minutes=1)
    secim = np.nonzero(np.asarray((zaman >= bas + tol) & (zaman < kapanis + tol)))[0]
    return int(secim.min()), int(secim.max())


def _dilim_uyusmazligi(f, z) -> int:
    return uyusmayan(sk.h2_funding_24s(f, z, **S_FUNDING), [ref.h2_funding_24s(f, x, **S_FUNDING) for x in z])


def test_D_B1_dilim_uclari_bagimsiz_secimle_ayni():
    """Penceredeki ilk ve son kaydin sira numarasi, bagimsiz bir zaman secimiyle ayni (iki uc ayri ayri)."""
    from data import funding

    z = _uzun_izgara()
    f = tsk.fonlama()
    a = funding.sinyal_penceresi_ayrintisi(f, z, config.BAR_4H, saat=config.H2_FUNDING_PENCERESI_SAAT, **S_FUNDING)
    hesap = a["hesaplanabilir"].to_numpy(dtype=bool)
    assert hesap.all(), "kurulum"
    for j, t in enumerate(z):
        assert (int(a["ilk"].iloc[j]), int(a["son"].iloc[j])) == _bagimsiz_dilim(f, t), j


@pytest.mark.parametrize("kaydirma", [{"son_kaydirma": 1}, {"son_kaydirma": -1}, {"ilk_kaydirma": 1},
                                      {"ilk_kaydirma": -1}])
def test_D_B1_kaydirilmis_dilim_testi_kirmiziya_dondurur(monkeypatch, kaydirma):
    """Kaynak degistirilmeden: dilim fonksiyonu parametreyle bozulur (ör. `son+1`) ve ayni olcum uyusmazlik verir.
    Yani dilimin uclari gercekten sinaniyor; korunmayan bir uc olsaydi bozma fark edilmezdi."""
    z = _uzun_izgara()
    f = tsk.fonlama()
    assert _dilim_uyusmazligi(f, z) == 0
    monkeypatch.setattr(sk, "_funding_dilimi", functools.partial(sk._funding_dilimi, **kaydirma))
    assert _dilim_uyusmazligi(f, z) > 0, kaydirma


# --- D-B2: uygunluk ve 1d pencerelerinde G3 ------------------------------------------------------------------------

T_UYGUN_4H = U("2024-06-01 12:00")
T_UYGUN_1D = U("2024-06-01")


def _uygunluk_iki_taraf(g, z, bar, *, donem_bas=BAS, kume_bas=None):
    esik = config.ASGARI_HACIM_4H if bar == config.BAR_4H else config.ASGARI_HACIM_1D
    yas = config.ASGARI_LISTELEME_YASI_GUN
    tablo = sk.uygunluk(g, z, bar, donem_baslangic=donem_bas, donem_bitis=tsk.SON, kume_baslangic=kume_bas,
                        asgari_hacim=esik, asgari_listeleme_yasi_gun=yas)
    gh = ref.gunluk_hacim_serisi(g)
    medyan = [ref.medyan_hacim(gh, t, donem_baslangic=donem_bas, kume_baslangic=kume_bas,
                               pencere_gun=config.HACIM_PENCERESI_GUN) for t in z]
    uygun = [ref.uygunluk_karari(gh, t, bar, donem_baslangic=donem_bas, donem_bitis=tsk.SON, kume_baslangic=kume_bas,
                                 asgari_hacim=esik, asgari_listeleme_yasi_gun=yas) for t in z]
    return tablo, medyan, uygun


@pytest.mark.parametrize("bar,t", [(config.BAR_4H, T_UYGUN_4H), (config.BAR_1D, T_UYGUN_1D)])
def test_D_B2_uygunluk_hacim_penceresinin_her_konumunda_tek_eksik_gun(bar, t):
    """Hacim penceresi t'nin gunu HARIC onceki 30 tam gundur (on-kayit §2 "Uygunluk penceresi ve t günü"). 30 konumun
    her birinde tek gun eksikken (gunun 08:00 bari silinir; gun 1d serisinden duser) iki tarafta medyan NaN ve bar
    uygun degil. Pencerenin hemen disindaki iki gun (t'nin gunu ve t-31) medyani hesaplanamaz yapmaz."""
    gun = t.floor("D")
    for j in range(1, config.HACIM_PENCERESI_GUN + 1):
        g = tsk.gunluk(tsk.mumlar(eksik=[gun - G(j) + H(2)]))
        tablo, medyan, uygun = _uygunluk_iki_taraf(g, pd.DatetimeIndex([t]), bar)
        assert np.isnan(medyan[0]) and np.isnan(tablo["medyan_hacim"].iloc[0]), j
        assert uygun == [False] and list(tablo["uygun"]) == [False], j
    disarida = [config.HACIM_PENCERESI_GUN + 1] + ([0] if bar == config.BAR_4H else [])
    for j in disarida:
        g = tsk.gunluk(tsk.mumlar(eksik=[gun - G(j) + H(2)]))
        tablo, medyan, uygun = _uygunluk_iki_taraf(g, pd.DatetimeIndex([t]), bar)
        assert np.isfinite(medyan[0]) and ayni(tablo["medyan_hacim"].iloc[0], medyan[0]), j
        assert list(tablo["uygun"]) == uygun, j


@pytest.mark.parametrize("bar", [config.BAR_4H, config.BAR_1D])
def test_D_B2_uygunlukta_kume_basi_ve_donem_basi_maskesi_seride_oncesi_veri_varken(bar):
    """Seride kume ve donem oncesi 60 gunluk veri VAR (1d serisi de o gunleri tasir). Hacim penceresi kume basini
    ya da donem basini asarsa medyan NaN; sinirla ayni gun baslayan pencere gecer. Iki maske ayri ayri."""
    m = tsk.mumlar(oncesi_gun=60)
    g = tsk.gunluk(m, bas=BAS - G(60))
    ilk_tam = BAS + G(config.HACIM_PENCERESI_GUN)          # penceresi tam BAS'ta baslayan gun
    gunler = [ilk_tam - G(1), ilk_tam, ilk_tam + G(1)]
    z = pd.DatetimeIndex(gunler if bar == config.BAR_1D else [x + H(3) for x in gunler])
    for sinir in ({"donem_bas": BAS - G(60), "kume_bas": BAS}, {"donem_bas": BAS, "kume_bas": None}):
        tablo, medyan, uygun = _uygunluk_iki_taraf(g, z, bar, **sinir)
        assert uyusmayan(tablo["medyan_hacim"], medyan) == 0, sinir
        assert list(tablo["uygun"]) == uygun, sinir
        assert np.isnan(medyan[0]) and np.isfinite(medyan[1]) and np.isfinite(medyan[2]), sinir


@pytest.mark.parametrize("ad", list(tsk.PENCERELER_1D))
def test_D_B2_h3_1d_pencerelerinde_donem_basi_ve_kume_basi_maskesi(ad):
    """H3'un 1d pencereleri; seride donem ve kume oncesi veri VAR. Pencere basi sinirdan bir gun once ise NaN, sinirla
    ayni gun ise hesaplanir; donem basi ve kume basi ayri ayri sinanir."""
    m = tsk.mumlar(oncesi_gun=60)
    g = tsk.gunluk(m, bas=BAS - G(60))
    n, ofset = tsk.PENCERELER_1D[ad]
    t = BAS + G(n - 1 + ofset)                  # pencere basi = BAS
    z = pd.DatetimeIndex([t - G(1), t, t + G(1)])
    for sinir in ({"kume_bas": BAS, "donem_bas": BAS - G(60)}, {"kume_bas": None, "donem_bas": BAS}):
        v = tsk._vektor_1d(g, z, **sinir)[ad]
        s = tsk._skaler_1d(g, z, **sinir)[ad]
        assert uyusmayan(v, s) == 0, sinir
        assert np.isnan(v[0]) and np.isfinite(v[1]) and np.isfinite(v[2]), sinir
