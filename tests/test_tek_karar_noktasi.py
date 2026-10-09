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
from kapi_yardimcisi import veri
from sinyal_yardimcisi import kontrol, olay, yapilandirma
from uygunluk_yardimcisi import UYGUN_ONCELIK, esikler

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
BAS, B = T("2025-01-01 00:00"), T("2025-02-10 08:00")
Z = pd.date_range(BAS, B, freq="4h")
MUM = pd.DataFrame({"open_time": Z, "open": np.arange(len(Z)) + 0.25, "high": np.arange(len(Z)) + 0.9,
                    "low": np.arange(len(Z)) + 0.0, "close": np.arange(len(Z)) + 0.5})
# Rev.9 §4: uygunluk tek karar noktasinin parcasi. Donem, mum serisinden UYGUN_ONCELIK once baslar
# (listeleme yasi >= 30 gun) ve uygunluk hacmi o gunden itibaren esigin ustundedir.
# Kapi sertlestirme turu: donem sinirlari evren kaydindan okunur; turu 2: kapi veriyi kendisi yukler,
# sentetik veri ve donem `kapi_yardimcisi.veri` ile kaydedilir.
DONEM_BAS = BAS - UYGUN_ONCELIK


def _fund(bas=BAS, son=B + H4, aralik=8):
    z = pd.date_range(bas, son, freq=f"{aralik}h")
    return pd.DataFrame({"odeme_zamani": z, "aralik_saat": float(aralik), "oran": 1e-4, "oran_8h": 1e-4})


def _karar(t, ufuk=18, bar=config.BAR_4H, fr=None, mum=MUM, rol="K1", donem_bas=DONEM_BAS, donem_bitis=B,
           **ek):
    """Rev.11 madde 4/5: kapi sinyal degerlerini kendisi hesaplar; bu dosya sinyal kurallarini
    degil karar noktasinin OTEKI adimlarini (plan, cikis, uygunluk, funding tamligi) sinar, bu
    yuzden varsayilan rol K1'dir: kontrol barinda hipotezin sinyal kosullari aranmaz
    (on-kayit §6 rev.11) ve duz sentetik seri kapidan gecer."""
    hipotez = "H1" if bar == config.BAR_4H else "H3"
    return pozisyon.olay_karari(t, ufuk, bar, hipotez=hipotez, birincil_ufuk=18,
                                kume="KESIF", **veri(mum, _fund() if fr is None else fr, donem_bas, donem_bitis,
                                                     uygun_bas=DONEM_BAS),
                                **kontrol(hipotez, rol), **ek, **esikler(bar))


def test_onayli_pozisyon_plan_fiyat_ve_funding_tasir():
    p = _karar(T("2025-01-05 04:00"))
    assert p.plan.giris == T("2025-01-05 08:00") and p.cikis_turu == "olagan"
    i0 = int(np.flatnonzero(Z == p.plan.giris)[0])
    i1 = int(np.flatnonzero(Z == p.plan.cikis.zaman)[0])
    assert pozisyon.pozisyon_fiyatlari(p) == (MUM["open"][i0], MUM["close"][i1])
    assert p.funding_toplami == funding.pozisyon_fundingi(p)


def test_funding_tam_olmayan_olay_brut_hesapta_da_olusmaz():
    """Plan kurulabilir, ama funding eksik: karar olay olusturmaz ve brut getirinin tek
    girdisi (`pozisyon_fiyatlari`) plana verilemez."""
    fr = _fund()
    fr = fr.loc[fr["odeme_zamani"] != T("2025-01-06 00:00")]  # pencere icinden bir odeme eksik
    t = T("2025-01-05 04:00")
    plan = pencere.pozisyon_plani(Z, t, 18, config.BAR_4H, birincil_ufuk=18, kume_baslangic=config.KESIF_BASI,
                                  kume_bitis=config.KESIF_SONU, donem_baslangic=DONEM_BAS,
                                  donem_bitis=B)  # plan var (ic adim)
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


def test_sinyal_penceresi_tam_degilse_olusmaz():
    """On-kayit §2 "Tamlik sarti". Rev.11 madde 4'ten beri deger CAGIRANDAN alinmaz, bu yuzden
    iddia veriye tasindi: tepe penceresindeki bir bar eksikse K2 kontrolu de olay da olusmaz.
    (Eski kurgu `sinyal_degerleri=...` ile NaN/None/inf veriyordu; o parametre kalkti.)"""
    t = T("2025-01-05 04:00")
    capa = t - 2 * H4
    z = pd.DatetimeIndex(MUM["open_time"])
    mum = MUM.loc[z != t - H4].reset_index(drop=True)  # tepe penceresi [capa .. t-1] icinde
    with pytest.raises(pozisyon.SinyalPenceresiTamDegil) as hata:
        pozisyon.olay_karari(t, 18, config.BAR_4H, hipotez="H1", birincil_ufuk=18, kume="KESIF",
                             **veri(mum, _fund(), DONEM_BAS, B, uygun_bas=DONEM_BAS),
                             **olay("H1", capa=capa), **esikler(config.BAR_4H))
    assert pencere.ret_gerekcesi(hata.value) == "sinyal_penceresi_tam_degil"


def test_sinyal_degerleri_anahtar_sozcugu_kabul_edilmez():
    """Rev.11 madde 4: "Sinyal degerleri disaridan verilemesin." (Eski iddia: bos eslem
    reddedilir; artik eslemin kendisi verilemez.)"""
    with pytest.raises(TypeError, match="sinyal_degerleri"):
        _karar(T("2025-01-05 04:00"), sinyal_degerleri={})


def test_diger_kurallar_ayni_noktadan_gerekceyle():
    with pytest.raises(pencere.GirisBariYok):
        _karar(T("2025-01-05 04:00"), mum=MUM.loc[MUM["open_time"] != T("2025-01-05 08:00")])
    # Kapi sertlestirme turu: kume siniri artik cagirandan alinmaz (kapi `split.kume_araligi`ndan okur).
    # Kume sonu kurali gercek KESIF sonunda sinanir: 2025-08-30 04:00 sinyalinin 18 barlik ufku C2'ye tasar.
    son = pd.date_range(T("2025-07-01"), T("2025-09-10 20:00"), freq="4h")
    son_mum = pd.DataFrame({"open_time": son, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
    with pytest.raises(pencere.KumeSiniriHatasi):
        _karar(T("2025-08-30 04:00"), mum=son_mum, fr=_fund(T("2025-07-01"), T("2025-09-11")),
               donem_bas=T("2025-07-01"), donem_bitis=T("2025-09-10 20:00"))
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
