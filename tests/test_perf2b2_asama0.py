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
