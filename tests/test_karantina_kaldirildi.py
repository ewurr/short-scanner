"""Karantina kuralinin koddan kaldirilmasi (on-kayit §2 rev.7).

Rev.7: "Rev.2'de getirilen SETTLED tabanli karantina kurali yururlukten
kalkmistir. ... SETTLED bilgisi yalnizca denetim amaciyla tutulur." Donem
bolme kurallari (dolgu kosusu, uzun eksik bar boslugu) ayni riski kapsar.

Bu testler karantinanin hicbir hesaba geri sizmadigini dogrular: sinir
parametresi olarak verilemez (TypeError) ve karantina yardimcilari yoktur.
Eskiden karantina testlerinin korudugu amac -- pencere, uygunluk, cikis ve
funding'in donem disina tasmamasi -- donem sinirlariyla test edilir
(test_pencere, test_eligibility, test_pozisyon_fundingi, test_funding_penceresi).
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import donem, eligibility, funding, pencere

KAR = {"karantina_aylari": ["2021-06"]}


def _seri():
    return pd.Series(1.0, index=pd.date_range("2021-05-01", periods=300, freq="4h", tz="UTC"))


def _fund():
    zaman = pd.date_range("2021-05-01", "2021-07-31", freq="8h", tz="UTC")
    fr = pd.DataFrame({"odeme_zamani": zaman, "aralik_saat": 8.0, "oran": 1e-4})
    fr["oran_8h"] = fr["oran"]
    return fr


@pytest.mark.parametrize(
    "cagri",
    [
        pytest.param(lambda: pencere.pencere_degeri(_seri(), _seri().index[100], 6, config.BAR_4H, t_dahil=True,
                                                    kume_baslangic=None, donem_baslangic=None, **KAR), id="pencere_degeri"),
        pytest.param(lambda: pencere.pencere_dilimi(_seri(), _seri().index[100], 6, config.BAR_4H, t_dahil=True,
                                                    kume_baslangic=None, donem_baslangic=None, **KAR), id="pencere_dilimi"),
        pytest.param(lambda: pencere.ofsetli_pencere_degeri(_seri(), _seri().index[100], 6, config.BAR_4H, bitis_ofseti=1,
                                                            islev="sum", kume_baslangic=None, donem_baslangic=None, **KAR),
                     id="ofsetli_pencere_degeri"),
        pytest.param(lambda: pencere.cikis_bari(_seri().index, _seri().index[100], 18, config.BAR_4H, birincil_ufuk=18,
                                                donem_bitis=None, kume_bitis=None, **KAR), id="cikis_bari"),
        pytest.param(lambda: funding.funding_ortalamasi(_fund(), pd.Timestamp("2021-06-10", tz="UTC"), config.BAR_4H, saat=24,
                                                        kume_baslangic=None, donem_baslangic=None, **KAR), id="funding_ortalamasi"),
        pytest.param(lambda: funding.pozisyon_fundingi(
            _fund(), pd.Timestamp("2021-06-10", tz="UTC"),
            pencere.CikisSonucu(0, pd.Timestamp("2021-06-12", tz="UTC"), "close", False, False), config.BAR_4H,
            kume_baslangic=None, kume_bitis=None, donem_baslangic=None, donem_bitis=None, **KAR), id="pozisyon_fundingi"),
        pytest.param(lambda: eligibility.uygun_mu(
            pd.Series(5e7, index=pd.date_range("2021-01-01", periods=200, freq="D", tz="UTC")),
            pd.Timestamp("2021-06-10", tz="UTC"), config.BAR_4H,
            donem_baslangic=pd.Timestamp("2021-01-01", tz="UTC"), donem_bitis=None, kume_baslangic=None, **KAR), id="uygun_mu"),
        pytest.param(lambda: eligibility.medyan_hacim(
            pd.Series(5e7, index=pd.date_range("2021-01-01", periods=200, freq="D", tz="UTC")),
            pd.Timestamp("2021-06-10", tz="UTC"), donem_baslangic=None, kume_baslangic=None,
            pencere_gun=config.HACIM_PENCERESI_GUN, **KAR), id="medyan_hacim"),
    ],
)
def test_karantina_siniri_verilemez(cagri):
    with pytest.raises(TypeError):
        cagri()


def test_karantina_yardimcilari_yok():
    assert not hasattr(pencere, "karantina_dogrula")
    assert not hasattr(pencere, "_karantina_siniri")
    assert not hasattr(donem, "karantinada_mi")
    assert "karantina" not in pencere.KIRPMA_NEDENLERI


def test_karantina_nedenli_cikis_gecersizdir():
    """Eski kodun urettigi "karantina" kirpma nedeni artik tutarsiz bir cikistir."""
    eski = pencere.CikisSonucu(0, pd.Timestamp("2021-05-31 20:00", tz="UTC"), "close", False, True, "karantina")
    with pytest.raises(ValueError):
        pencere.cikis_ani(eski, config.BAR_4H)
