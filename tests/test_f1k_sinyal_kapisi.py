"""Karar noktasi hipotezin butun sinyal degerlerini KENDISI hesaplar (Rev.11 madde 4; F1 kapanis
turu, denetci D-B1).

On-kayit §2 "Tamlik sarti": "Pencerede beklenen barlardan biri bile eksikse deger hesaplanmaz ve o barda
olay ya da kontrol olusmaz." §4 "Funding sinyal penceresinin tamligi": "... degilse deger hesaplanmaz ve
o barda olay ya da kontrol olusmaz."

Rev.11 oncesi bu dosya `sinyal_degerleri` anahtar sozcugunu sinardi: kapi degerleri cagirandan
aliyor, yalnizca ad tamligini ve sayisalligini denetliyordu. Rev.11 madde 4 ile deger disaridan
VERILEMEZ; kapi `data.sinyal`in pencere kuruculariyla kendisi hesaplar. Bu yuzden iddialar veriye
tasindi: bir degerin "hesaplanamaz" olmasi artik bir bar ya da funding kaydi eksikligidir.

- H2'nin funding penceresi kapida gercek funding serisinden kurulur; pencere hesaplanamiyorsa olay
  (rol "olay") ve K2 kontrolu olusmaz. K1 kontrolunde sinyal HIC hesaplanmaz (on-kayit §6 rev.11).
- Pencere kume basini asiyorsa deger hesaplanmaz.
- H1 ve H3 funding sinyali kullanmaz.
Oranlar sentetik; getiri hesaplanmaz. Aga cikmaz.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

import config
from data import funding, pencere, pozisyon, sinyal
from kapi_yardimcisi import donem, veri
from kume_yardimcisi import kume_adi
from sinyal_yardimcisi import kontrol, olay, yapilandirma
from uygunluk_yardimcisi import esikler, uygunluk

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H = lambda n: pd.Timedelta(hours=n)  # noqa: E731
DB, B = T("2025-01-01"), T("2025-06-30 20:00")
Z = pd.date_range(T("2025-03-01"), B, freq="4h")
MUM = pd.DataFrame({"open_time": Z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
TAM_FUND = pd.DataFrame({"odeme_zamani": pd.date_range(DB, B + H(4), freq="8h"), "aralik_saat": 8.0,
                         "oran": 0.0, "oran_8h": 0.0})
T_KONTROL = T("2025-03-10 04:00")  # H2 penceresi (03-09 08:00, 03-10 08:00]
# Pencere icindeki 03-09 16:00 odemesi eksik: 08:00 -> 03-10 00:00 boslugu 8 saati asar. Pozisyon
# penceresi (giris 03-10 08:00'dan sonra) etkilenmez.
BOSLUKLU_FUND = TAM_FUND.loc[TAM_FUND["odeme_zamani"] != T("2025-03-09 16:00")].reset_index(drop=True)
SINYAL_T = {"H1": T_KONTROL, "H2": T_KONTROL, "H3": T("2025-03-10")}


def _karar(hipotez, fr, rol="K2", t=None, mum=MUM, **sinir):
    """Varsayilan rol K2: sinyal degerleri hesaplanir ama kosullarin SAGLANMAMASI beklenir
    (duz seride hicbir hipotezin kosulu saglanmaz), yani "kontrol adayi" yolu sinanir."""
    tanim = pencere.hipotez_ufuklari(hipotez)
    zaman = SINYAL_T[hipotez] if t is None else t
    s = {"kume": kume_adi(zaman)}
    s.update(sinir)
    rol_girdisi = olay(hipotez) if rol == "olay" else kontrol(hipotez, rol)
    return pozisyon.olay_karari(zaman, tanim.birincil, tanim.bar, hipotez=hipotez,
                                birincil_ufuk=tanim.birincil, **veri(mum, fr, DB, B, uygun_bas=DB),
                                **rol_girdisi, **s, **esikler(tanim.bar))


def test_h2_penceresi_hesaplanamayan_barda_k2_kontrolu_olusmaz():
    """Kontrol barinin sinyali K2'nin "olay uretmemis" sartini dogrulamak icin hesaplanir; veri
    eksikliginden hesaplanamiyorsa bar kontrol OLAMAZ (on-kayit §6 rev.11)."""
    assert np.isnan(funding.funding_ortalamasi(BOSLUKLU_FUND, T_KONTROL, config.BAR_4H,
                                               saat=config.H2_FUNDING_PENCERESI_SAAT, kume_baslangic=None,
                                               kume_bitis=None, donem_baslangic=DB))
    with pytest.raises(pozisyon.SinyalPenceresiTamDegil) as hata:
        _karar("H2", BOSLUKLU_FUND, rol="K2")
    assert pencere.ret_gerekcesi(hata.value) == "sinyal_penceresi_tam_degil"
    # Ayni bar, tam funding: K2 kontrolu olusur (duz seride H2 kosullari saglanmaz).
    assert _karar("H2", TAM_FUND, rol="K2").hipotez == "H2"


def test_h2_olay_tarafi_da_ayni():
    with pytest.raises(pozisyon.SinyalPenceresiTamDegil):
        _karar("H2", BOSLUKLU_FUND, rol="olay")


def test_h2_k1_kontrolunde_funding_penceresi_aranmaz():
    """On-kayit §6 rev.11: "Sinyal degerleri kontrol tarafinda yalnizca tek bir amacla hesaplanir:
    K2'nin 'o anda olay uretmemis' sartini dogrulamak." K1'in olcutu zamansal uzakliktir; ayni
    bosluk K1 kontrolunu dusurmez."""
    assert _karar("H2", BOSLUKLU_FUND, rol="K1").rol == "K1"


def test_h2_penceresi_kume_basini_asarsa_olusmaz():
    """Pencere basi kume basindan onceyse (seride kume oncesi kayit bulunsa bile) reddedilir.

    Kapi sertlestirme turu: kume siniri artik cagirandan alinmaz; kural gercek KESIF basinda (2020-01-01)
    sinanir. Donem ve funding serisi kume oncesine uzanir; 2020-01-01 04:00 sinyalinin 24 saatlik penceresi
    (2019-12-31 08:00, 2020-01-01 08:00] kume basindan once baslar."""
    db, b = T("2019-11-01"), T("2020-03-01 20:00")
    z = pd.date_range(db, b, freq="4h")
    mum = pd.DataFrame({"open_time": z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
    fr = pd.DataFrame({"odeme_zamani": pd.date_range(db, b + H(4), freq="8h"), "aralik_saat": 8.0,
                       "oran": 0.0, "oran_8h": 0.0})
    t = T("2020-01-01 04:00")
    tanim = pencere.hipotez_ufuklari("H2")
    with pytest.raises(pozisyon.SinyalPenceresiTamDegil):
        pozisyon.olay_karari(t, tanim.birincil, tanim.bar, hipotez="H2", birincil_ufuk=tanim.birincil,
                             kume="KESIF", **veri(mum, fr, db, b, uygun_bas=db), **kontrol("H2", "K2"),
                             **esikler(tanim.bar))
    # Karsi-ornek (ic adim): kume basi pencere basinda olsaydi pencere hesaplanabilirdi.
    a = funding.sinyal_penceresi_ayrintisi(fr, [t], config.BAR_4H, saat=config.H2_FUNDING_PENCERESI_SAAT,
                                           kume_baslangic=t + H(4) - H(24), kume_bitis=None,
                                           donem_baslangic=db).iloc[0]
    assert bool(a["hesaplanabilir"])


def test_funding_penceresi_yalnizca_h2_icin_denetlenir():
    """H1 ve H3 funding sinyali kullanmaz; ayni bosluk onlarda olay kumesini degistirmez."""
    assert _karar("H1", BOSLUKLU_FUND, rol="K2").hipotez == "H1"
    assert pozisyon.FUNDING_SINYALI in pozisyon.SINYAL_DEGERLERI["H2"]
    assert all(pozisyon.FUNDING_SINYALI not in pozisyon.SINYAL_DEGERLERI[h] for h in ("H1", "H3"))


@pytest.mark.parametrize("hipotez", ["H2", "H3"])
def test_eksik_bar_sinyal_penceresini_dusurur(hipotez):
    """On-kayit §2 "Tamlik sarti" veriye bagli: hipotezin pencerelerinden birinin bir bari
    eksikse deger hesaplanmaz ve o barda ne olay ne K2 kontrolu olusur. (H1'in kontrol barinda
    sinyal aranmadigi icin bu test H2 ve H3 icindir; H1'in olay yolu
    `tests/test_rev11_kapi_sinyali.py`de.)"""
    tanim = pencere.hipotez_ufuklari(hipotez)
    t = SINYAL_T[hipotez]
    adim = pencere.adim(tanim.bar)
    eksik_an = t - 10 * adim
    z = pd.DatetimeIndex(MUM["open_time"])
    # 1d izgarasinda gunun ALTI barindan birini cikarmak gunu dusurur.
    cikar = (z == eksik_an) if tanim.bar == config.BAR_4H else (z == eksik_an + H(8))
    mum = MUM.loc[~cikar].reset_index(drop=True)
    for rol in ("olay", "K2"):
        with pytest.raises(pozisyon.SinyalPenceresiTamDegil):
            _karar(hipotez, TAM_FUND, rol=rol, mum=mum)


def test_k1_sinyal_penceresindeki_eksik_bardan_etkilenmez():
    """Ayni eksiklik K1 kontrolunu dusurmez (on-kayit §6 rev.11: K1'de sinyal hesaplanmaz).

    Eksik bar, t'nin KENDI gunune (2025-03-10) konur: o gun uygunluk penceresinin disindadir
    (on-kayit §2 "Uygunluk penceresi ve t gunu": t'nin gunu haric onceki 30 tam gun), bu yuzden
    eksiklik yalnizca sinyal pencerelerini etkiler ve iki rolu ayirir."""
    z = pd.DatetimeIndex(MUM["open_time"])
    mum = MUM.loc[z != T_KONTROL - H(4)].reset_index(drop=True)
    with pytest.raises(pozisyon.SinyalPenceresiTamDegil):
        _karar("H2", TAM_FUND, rol="K2", mum=mum)
    assert _karar("H2", TAM_FUND, rol="K1", mum=mum).rol == "K1"


def test_sinyal_degerleri_anahtar_sozcugu_kalkti():
    """Rev.11 madde 4: "Sinyal degerleri disaridan verilemesin." Eski anahtar sozcuk bir
    programlama hatasidir; kapi onu sessizce yok saymaz."""
    tanim = pencere.hipotez_ufuklari("H2")
    with pytest.raises(TypeError, match="sinyal_degerleri"):
        pozisyon.olay_karari(T_KONTROL, tanim.birincil, tanim.bar, hipotez="H2",
                             birincil_ufuk=tanim.birincil, kume="KESIF",
                             **veri(MUM, TAM_FUND, DB, B, uygun_bas=DB), **kontrol("H2", "K2"),
                             sinyal_degerleri={"funding_24s": 1.0, "kapanis_30_once": 1.0,
                                               "kirilim_dip": 1.0}, **esikler(tanim.bar))


def test_tanim_on_kayit_kosullarini_kapsar():
    assert set(pozisyon.SINYAL_DEGERLERI) == set(config.HIPOTEZ_IZGARASI)
    for adlar in pozisyon.SINYAL_DEGERLERI.values():
        assert len(adlar) == len(set(adlar)) and adlar
    # Adlarin tek kaynagi `data.sinyal`dir.
    assert pozisyon.SINYAL_DEGERLERI is sinyal.DEGER_ADLARI
