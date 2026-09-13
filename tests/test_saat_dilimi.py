"""Saat dilimsiz zaman damgasi reddi (F1 kapanis bulgusu 15, CLAUDE.md §5).

Saat dilimsiz bir t ya da seri, UTC'li veriyle karsilastirilinca hicbir bar
eslesmez: her pencere NaN, her giris None olur ve calisma sessizce "hic olay yok"
sonucuna doner. Bu testler boyle bir girdinin acik hatayla reddedildigini dogrular.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import eligibility, pencere

SINIRSIZ = dict(kume_baslangic=None, donem_baslangic=None, karantina_aylari=None)


def _seri(tz="UTC") -> pd.Series:
    return pd.Series(1.0, index=pd.date_range("2021-01-01", periods=60, freq="4h", tz=tz))


def _naive(zaman: pd.Timestamp) -> pd.Timestamp:
    return zaman.tz_localize(None)


def test_pencere_degeri_saat_dilimsiz_t():
    seri = _seri()
    t = seri.index[40]
    assert not pd.isna(pencere.pencere_degeri(seri, t, 10, config.BAR_4H, t_dahil=True, **SINIRSIZ))
    with pytest.raises(TypeError):
        pencere.pencere_degeri(seri, _naive(t), 10, config.BAR_4H, t_dahil=True, **SINIRSIZ)


def test_pencere_degeri_saat_dilimsiz_seri():
    naive = _seri(tz=None)
    with pytest.raises(pencere.ZamanDizisiHatasi):
        pencere.pencere_degeri(naive, _seri().index[40], 10, config.BAR_4H, t_dahil=True, **SINIRSIZ)


@pytest.mark.parametrize("sinir", ["kume_baslangic", "donem_baslangic"])
def test_saat_dilimsiz_baslangic_siniri(sinir):
    seri = _seri()
    parametreler = {**SINIRSIZ, sinir: pd.Timestamp("2021-01-02")}
    with pytest.raises(TypeError):
        pencere.pencere_degeri(seri, seri.index[40], 10, config.BAR_4H, t_dahil=True, **parametreler)


def test_giris_bari_saat_dilimsiz():
    seri = _seri()
    with pytest.raises(TypeError):
        pencere.giris_bari(seri.index, _naive(seri.index[5]), config.BAR_4H)


@pytest.mark.parametrize("alan", ["giris", "donem_bitis", "kume_bitis"])
def test_cikis_bari_saat_dilimsiz(alan):
    seri = _seri()
    giris = seri.index[5]
    parametreler = dict(donem_bitis=None, karantina_aylari=None, kume_bitis=None)
    if alan == "giris":
        giris = _naive(giris)
    else:
        parametreler[alan] = pd.Timestamp("2021-12-31")
    with pytest.raises(TypeError):
        pencere.cikis_bari(seri.index, giris, 6, config.BAR_4H, **parametreler, birincil_ufuk=18)


def test_uygun_mu_saat_dilimsiz_t():
    hacim = pd.Series(5e7, index=pd.date_range("2021-01-01", periods=100, freq="D", tz="UTC"))
    ortak = dict(donem_baslangic=pd.Timestamp("2021-01-01", tz="UTC"), donem_bitis=None, karantina_aylari=None, kume_baslangic=None)
    assert eligibility.uygun_mu(hacim, pd.Timestamp("2021-03-01", tz="UTC"), config.BAR_4H, **ortak) is True
    with pytest.raises(TypeError):
        eligibility.uygun_mu(hacim, pd.Timestamp("2021-03-01"), config.BAR_4H, **ortak)
