"""Denetci bulgusu D-C6 (kalan kisim): pencere, uygunluk ve funding ortalamasi fonksiyonlarinda donem
siniri `None` olamaz (on-kayit §2 "Tum geriye bakis pencereleri donem baslangicini asamaz").

Rev.9 turunda yalnizca karar noktasi ve tarama kapanmisti. Artik alt fonksiyonlar da `None`
donem sinirini TypeError ile reddeder; kume siniri `None` olabilir. Aga cikmaz.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import eligibility, funding, pencere
from donem_yardimcisi import TOPLAM_DONEM_B, TOPLAM_DONEM_BASI

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
SERI = pd.Series(1.0, index=pd.date_range(T("2021-01-01"), periods=400, freq="4h"))
GUNLUK = pd.Series(5e7, index=pd.date_range(T("2021-01-01"), periods=200, freq="D"))
FUND = pd.DataFrame({"odeme_zamani": pd.date_range(T("2021-01-01"), T("2021-03-01"), freq="8h"), "aralik_saat": 8.0,
                     "oran": 0.0, "oran_8h": 0.0})
t4 = SERI.index[300]
CAGRILAR = {
    "pencere_dilimi": lambda d: pencere.pencere_dilimi(SERI, t4, 6, config.BAR_4H, t_dahil=True, kume_baslangic=None,
                                                       donem_baslangic=d),
    "pencere_degeri": lambda d: pencere.pencere_degeri(SERI, t4, 6, config.BAR_4H, t_dahil=True, kume_baslangic=None,
                                                       donem_baslangic=d),
    "ic_ice_pencere_degeri": lambda d: pencere.ic_ice_pencere_degeri(
        SERI, t4, config.BAR_4H, dis_bar_sayisi=10, dis_t_dahil=True, dis_islev="median", ic_bar_sayisi=6,
        ic_t_dahil=True, ic_islev="sum", kume_baslangic=None, donem_baslangic=d),
    "ofsetli_pencere_degeri": lambda d: pencere.ofsetli_pencere_degeri(
        SERI, t4, 6, config.BAR_4H, bitis_ofseti=1, islev="sum", kume_baslangic=None, donem_baslangic=d),
    "medyan_hacim": lambda d: eligibility.medyan_hacim(GUNLUK, T("2021-05-01"), donem_baslangic=d, kume_baslangic=None,
                                                       pencere_gun=config.HACIM_PENCERESI_GUN),
    "funding_ortalamasi": lambda d: funding.funding_ortalamasi(FUND, T("2021-02-01"), config.BAR_4H, saat=24,
                                                               kume_baslangic=None, kume_bitis=None,
                                                               donem_baslangic=d),
}


@pytest.mark.parametrize("ad", list(CAGRILAR))
def test_donem_basi_none_hata_verir(ad):
    with pytest.raises(TypeError, match="None olamaz"):
        CAGRILAR[ad](None)
    CAGRILAR[ad](TOPLAM_DONEM_BASI)  # gercek sinirla calisir


@pytest.mark.parametrize("sinir", ["donem_baslangic", "donem_bitis"])
def test_uygunluk_donem_sinirlari_none_olamaz(sinir):
    sinirlar = {"donem_baslangic": T("2021-01-01"), "donem_bitis": TOPLAM_DONEM_B, sinir: None}
    with pytest.raises(TypeError):
        eligibility.uygun_mu(GUNLUK, T("2021-05-01"), config.BAR_4H, kume_baslangic=None, **sinirlar)
    with pytest.raises(TypeError):
        eligibility.uygunluk_serisi(GUNLUK, [T("2021-05-01")], config.BAR_4H, kume_baslangic=None, **sinirlar)


def test_kume_siniri_none_olabilir():
    assert not pd.isna(CAGRILAR["pencere_degeri"](TOPLAM_DONEM_BASI))


def test_toplam_donem_sinirlari_none_ile_ayni_sonucu_verir_toplam_donem_icinde():
    """Testlerde `None` yerine verilen toplam donem sinirlari, verisi toplam donem icinde olan
    seride pencere kapisini ve donem uyeligini degistirmez."""
    assert TOPLAM_DONEM_BASI == T("2020-01-01") and TOPLAM_DONEM_B == T("2026-08-31 20:00")
    assert eligibility.uygun_mu(GUNLUK, T("2021-05-01"), config.BAR_4H, donem_baslangic=T("2021-01-01"),
                                donem_bitis=TOPLAM_DONEM_B, kume_baslangic=None) is True
