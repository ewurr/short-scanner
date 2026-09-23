"""On-kayit §4 rev.8 "Olayin kumede olusma olcutu": tek karar noktasi (`pozisyon.olay_karari`).

"Ayni karar noktasinda pozisyonun funding tamligi da saglanmalidir: funding'i tam
olmayan olay ya da kontrol, brut getiri dahil hicbir hesapta olusmaz. Boylece brut ve
net olay kumeleri her zaman aynidir." Aga cikmaz; getiri hesaplanmaz.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd
import pytest

import config
from data import funding, pencere, pozisyon
from uygunluk_yardimcisi import UYGUN_ONCELIK, uygunluk

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
BAS, B = T("2025-01-01 00:00"), T("2025-02-10 08:00")
Z = pd.date_range(BAS, B, freq="4h")
MUM = pd.DataFrame({"open_time": Z, "open": np.arange(len(Z)) + 0.25, "high": np.arange(len(Z)) + 0.9,
                    "low": np.arange(len(Z)) + 0.0, "close": np.arange(len(Z)) + 0.5})
# Rev.9 §4: uygunluk tek karar noktasinin parcasi. Donem, mum serisinden UYGUN_ONCELIK once baslar
# (listeleme yasi >= 30 gun) ve uygunluk hacmi o gunden itibaren esigin ustundedir.
SINIR = dict(kume_baslangic=None, kume_bitis=None, donem_baslangic=BAS - UYGUN_ONCELIK, donem_bitis=B)
SINYAL = {"pencere": 1.0}


def _fund(bas=BAS, son=B + H4, aralik=8):
    z = pd.date_range(bas, son, freq=f"{aralik}h")
    return pd.DataFrame({"odeme_zamani": z, "aralik_saat": float(aralik), "oran": 1e-4, "oran_8h": 1e-4})


def _karar(t, ufuk=18, bar=config.BAR_4H, fr=None, mum=MUM, sinyal=SINYAL, **sinir):
    return pozisyon.olay_karari(mum, _fund() if fr is None else fr, t, ufuk, bar, birincil_ufuk=18,
                                **{**SINIR, **sinir}, sinyal_degerleri=sinyal,
                                **uygunluk(bar, BAS - UYGUN_ONCELIK, B))


def test_onayli_pozisyon_plan_fiyat_ve_funding_tasir():
    p = _karar(T("2025-01-05 04:00"))
    assert p.plan.giris == T("2025-01-05 08:00") and p.cikis_turu == "olagan"
    i0 = int(np.flatnonzero(Z == p.plan.giris)[0])
    i1 = int(np.flatnonzero(Z == p.plan.cikis.zaman)[0])
    assert pozisyon.pozisyon_fiyatlari(p) == (MUM["open"][i0], MUM["close"][i1])
    assert p.funding_toplami == funding.pozisyon_fundingi(_fund(), p.plan)


def test_funding_tam_olmayan_olay_brut_hesapta_da_olusmaz():
    """Plan kurulabilir, ama funding eksik: karar olay olusturmaz ve brut getirinin tek
    girdisi (`pozisyon_fiyatlari`) plana verilemez."""
    fr = _fund()
    fr = fr.loc[fr["odeme_zamani"] != T("2025-01-06 00:00")]  # pencere icinden bir odeme eksik
    t = T("2025-01-05 04:00")
    plan = pencere.pozisyon_plani(Z, t, 18, config.BAR_4H, birincil_ufuk=18, **SINIR)  # plan var
    with pytest.raises(pozisyon.FundingTamDegil) as hata:
        _karar(t, fr=fr)
    assert pencere.ret_gerekcesi(hata.value) == "funding_tam_degil"
    with pytest.raises(TypeError):
        pozisyon.pozisyon_fiyatlari(plan)  # plan brut hesaba giremez


def test_funding_siz_donem_ve_gec_baslayan_funding():
    """§2 "Funding'i bulunmayan donemler": kaydi olmayan donemde olay olusmaz; funding'i
    donemin icinde gec baslayan donemde ilk kayittan onceki olaylar olusmaz."""
    with pytest.raises(pozisyon.FundingTamDegil):
        _karar(T("2025-01-05 04:00"), fr=_fund().iloc[0:0])
    gec = _fund(bas=T("2025-01-10 00:00"))
    with pytest.raises(pozisyon.FundingTamDegil):
        _karar(T("2025-01-05 04:00"), fr=gec)
    assert _karar(T("2025-01-12 04:00"), fr=gec).cikis_turu == "olagan"


@pytest.mark.parametrize("deger", [float("nan"), None, float("inf")])
def test_sinyal_penceresi_tam_degilse_olusmaz(deger):
    with pytest.raises(pozisyon.SinyalPenceresiTamDegil) as hata:
        _karar(T("2025-01-05 04:00"), sinyal={"a": 1.0, "b": deger})
    assert pencere.ret_gerekcesi(hata.value) == "sinyal_penceresi_tam_degil"


def test_sinyal_degerleri_bos_olamaz():
    with pytest.raises(TypeError):
        _karar(T("2025-01-05 04:00"), sinyal={})


def test_diger_kurallar_ayni_noktadan_gerekceyle():
    with pytest.raises(pencere.GirisBariYok):
        _karar(T("2025-01-05 04:00"), mum=MUM.loc[MUM["open_time"] != T("2025-01-05 08:00")])
    with pytest.raises(pencere.KumeSiniriHatasi):
        _karar(T("2025-01-05 04:00"), kume_bitis=T("2025-01-06 00:00"))
    eksik = MUM.loc[(MUM["open_time"] < T("2025-01-07 12:00")) | (MUM["open_time"] > T("2025-01-12 00:00"))]
    with pytest.raises(pencere.IleriKaymaSiniriHatasi):
        _karar(T("2025-01-05 04:00"), mum=eksik)


def test_donem_sonu_karari():
    p = _karar(T("2025-02-09 00:00"))
    assert p.cikis_turu == "donem_sonu" and p.plan.cikis_ani == B + H4
    assert p.p1 == MUM["close"].iloc[-1]


def test_elle_kurulan_ya_da_degistirilen_onay_reddedilir():
    p = _karar(T("2025-01-05 04:00"))
    with pytest.raises(ValueError):
        pozisyon.pozisyon_fiyatlari(dataclasses.replace(p, p1=999.0))
    with pytest.raises(TypeError):
        pozisyon.pozisyon_fiyatlari(p.plan)
