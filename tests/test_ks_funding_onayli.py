"""`funding.pozisyon_fundingi` yalnizca onayli pozisyon kabul eder (kapi sertlestirme turu, denetci F1K2 D-B3).

On-kayit §4 "Olayin kumede olusma olcutu": tek karar noktasi; karar noktasinin disinda uygulanan kod yolu
kabul edilmez. Net getirinin funding girdisi kapidan gecmemis bir plandan (`pencere.pozisyon_plani`) elde
edilemez. Ic adim `funding._plan_fundingi` yalnizca kapinin kendisi ve testler icindir; analiz kodunda
kaynak taramasiyla yasaklidir. Aga cikmaz.
"""

from __future__ import annotations

import dataclasses

import pandas as pd
import pytest

from data import funding, pencere, pozisyon
from kapi_yardimcisi import donem, veri
from kume_yardimcisi import kume_adi
from sinyal_yardimcisi import sinyal
from tarama_yardimcisi import CIKIS_KAPI_DISI_DESENI, ihlaller
from uygunluk_yardimcisi import esikler, uygunluk

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H = lambda n: pd.Timedelta(hours=n)  # noqa: E731

DB, B = T("2025-01-01"), T("2025-06-30 20:00")
Z = pd.date_range(T("2025-03-01"), B, freq="4h")
MUM = pd.DataFrame({"open_time": Z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
FUND = pd.DataFrame({"odeme_zamani": pd.date_range(DB, B + H(4), freq="8h"), "aralik_saat": 8.0,
                     "oran": 1e-4, "oran_8h": 1e-4})
T_SINYAL = T("2025-03-10 04:00")


def _plan():
    return pencere.pozisyon_plani(Z, T_SINYAL, 18, "4h", birincil_ufuk=18, kume_baslangic=None, kume_bitis=None,
                                  donem_baslangic=DB, donem_bitis=B)


def _onayli():
    return pozisyon.olay_karari(T_SINYAL, 18, "4h", hipotez="H1", birincil_ufuk=18,
                                sinyal_degerleri=sinyal("H1"), kume=kume_adi(T_SINYAL), **veri(MUM, FUND, DB, B, uygun_bas=DB),
                                **esikler("4h"))


def test_kapidan_gecmemis_plan_reddedilir():
    with pytest.raises(TypeError, match="Onaylanmis pozisyon"):
        funding.pozisyon_fundingi(_plan())


def test_onayli_pozisyon_kararin_toplamini_verir():
    p = _onayli()
    assert funding.pozisyon_fundingi(p) == p.funding_toplami
    assert p.funding_toplami == funding._plan_fundingi(FUND, p.plan)


def test_degistirilmis_onayli_pozisyon_reddedilir():
    p = _onayli()
    with pytest.raises(ValueError):
        funding.pozisyon_fundingi(dataclasses.replace(p, funding_toplami=1.0))


def test_baska_funding_serisi_reddedilir():
    p = _onayli()
    with pytest.raises(ValueError, match="ayni degil"):
        # Kapi sertlestirme turu 2: funding cercevesi verilemez; veri karardan sonra degisirse (kayitta
        # baska seri) toplam kararinkiyle ayni olmaz.
        from kapi_yardimcisi import SENTETIK_VERI

        mumlar, _ = SENTETIK_VERI[p.sembol]
        SENTETIK_VERI[p.sembol] = (mumlar, FUND.assign(oran=2e-4))
        funding.pozisyon_fundingi(p)


def test_ic_adim_analiz_kodunda_taramaya_takilir(tmp_path):
    (tmp_path / "study").mkdir()
    (tmp_path / "study" / "k.py").write_text("f = funding._plan_fundingi(fr, plan)\n", encoding="utf-8")
    assert ihlaller(CIKIS_KAPI_DISI_DESENI, kok=tmp_path) == ["study/k.py"]
