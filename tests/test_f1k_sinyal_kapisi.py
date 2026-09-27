"""Karar noktasi hipotezin butun sinyal degerlerini sart kosar (F1 kapanis turu, denetci D-B1).

On-kayit §2 "Tamlik sarti": "Pencerede beklenen barlardan biri bile eksikse deger hesaplanmaz ve o barda
olay ya da kontrol olusmaz." §4 "Funding sinyal penceresinin tamligi": "... degilse deger hesaplanmaz ve
o barda olay ya da kontrol olusmaz."

- `pozisyon.olay_karari` hipotezin sinyal degerlerini tam olarak ister (`pozisyon.SINYAL_DEGERLERI`):
  eksik ya da fazla ad TypeError, NaN/sonsuz/None deger `SinyalPenceresiTamDegil`.
- H2'nin funding penceresi kapida YAPISAL olarak yeniden kurulur: cagiran sonlu bir sayi verse bile
  pencere hesaplanamiyorsa olay da kontrol de olusmaz. Olaylar ve kontroller (K1, K2) ayni cagriyi
  kullanir; asagidaki "kontrol" cagrilari bir kontrol barinin karar noktasina gidisidir.
Oranlar sentetik; getiri hesaplanmaz. Aga cikmaz.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import config
from data import funding, pencere, pozisyon
from kume_yardimcisi import kume_adi
from sinyal_yardimcisi import sinyal
from uygunluk_yardimcisi import uygunluk

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


def _karar(hipotez, fr, degerler, t=None, **sinir):
    tanim = pencere.hipotez_ufuklari(hipotez)
    s = {"kume": kume_adi(SINYAL_T[hipotez] if t is None else t)}
    s.update(sinir)
    return pozisyon.olay_karari(MUM, fr, SINYAL_T[hipotez] if t is None else t, tanim.birincil, tanim.bar,
                                hipotez=hipotez, birincil_ufuk=tanim.birincil, donem_baslangic=DB, donem_bitis=B,
                                sinyal_degerleri=degerler, **s, **uygunluk(tanim.bar, DB, B))


def test_h2_penceresi_hesaplanamayan_barda_kontrol_olusmaz():
    """Kontrol cagrisi funding degerini hesaplamadan sonlu bir sayi verse bile reddedilir."""
    assert np.isnan(funding.funding_ortalamasi(BOSLUKLU_FUND, T_KONTROL, config.BAR_4H,
                                               saat=config.H2_FUNDING_PENCERESI_SAAT, kume_baslangic=None,
                                               kume_bitis=None, donem_baslangic=DB))
    with pytest.raises(pozisyon.SinyalPenceresiTamDegil) as hata:
        _karar("H2", BOSLUKLU_FUND, sinyal("H2", funding_24s=0.0005))  # sahte ama sonlu deger
    assert pencere.ret_gerekcesi(hata.value) == "sinyal_penceresi_tam_degil"
    # Ayni bar, tam funding: kontrol olusur.
    assert _karar("H2", TAM_FUND, sinyal("H2")).hipotez == "H2"


def test_h2_olay_tarafi_da_ayni():
    with pytest.raises(pozisyon.SinyalPenceresiTamDegil):
        _karar("H2", BOSLUKLU_FUND, sinyal("H2", funding_24s=0.01))


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
        pozisyon.olay_karari(mum, fr, t, tanim.birincil, tanim.bar, hipotez="H2", birincil_ufuk=tanim.birincil,
                             kume="KESIF", donem_baslangic=db, donem_bitis=b, sinyal_degerleri=sinyal("H2"),
                             **uygunluk(tanim.bar, db, b))
    # Karsi-ornek (ic adim): kume basi pencere basinda olsaydi pencere hesaplanabilirdi.
    a = funding.sinyal_penceresi_ayrintisi(fr, [t], config.BAR_4H, saat=config.H2_FUNDING_PENCERESI_SAAT,
                                           kume_baslangic=t + H(4) - H(24), kume_bitis=None,
                                           donem_baslangic=db).iloc[0]
    assert bool(a["hesaplanabilir"])


def test_funding_penceresi_yalnizca_h2_icin_denetlenir():
    """H1 ve H3 funding sinyali kullanmaz; ayni bosluk onlarda olay kumesini degistirmez."""
    assert _karar("H1", BOSLUKLU_FUND, sinyal("H1")).hipotez == "H1"
    assert pozisyon.FUNDING_SINYALI in pozisyon.SINYAL_DEGERLERI["H2"]
    assert all(pozisyon.FUNDING_SINYALI not in pozisyon.SINYAL_DEGERLERI[h] for h in ("H1", "H3"))


@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_her_sinyal_degeri_nan_ise_olusmaz(hipotez):
    for ad in pozisyon.SINYAL_DEGERLERI[hipotez]:
        for kotu in (float("nan"), float("inf"), None):
            with pytest.raises(pozisyon.SinyalPenceresiTamDegil):
                _karar(hipotez, TAM_FUND, sinyal(hipotez, **{ad: kotu}))


@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_eksik_ya_da_fazla_ad_programlama_hatasi(hipotez):
    tam = sinyal(hipotez)
    ilk = next(iter(tam))
    eksik = {k: v for k, v in tam.items() if k != ilk}
    with pytest.raises(TypeError, match="sinyal_degerleri"):
        _karar(hipotez, TAM_FUND, eksik)
    with pytest.raises(TypeError, match="sinyal_degerleri"):
        _karar(hipotez, TAM_FUND, {**tam, "fazla": 1.0})
    baska = "H1" if hipotez != "H1" else "H3"
    with pytest.raises(TypeError, match="sinyal_degerleri"):
        _karar(hipotez, TAM_FUND, sinyal(baska))


def test_eksik_ad_nan_denetiminden_once_yakalanir():
    """Eksik ad bir ret gerekcesi degil programlama hatasidir: NaN deger olsa da once TypeError."""
    degerler = sinyal("H1", pump_dip=float("nan"))
    del degerler["tepe"]
    with pytest.raises(TypeError):
        _karar("H1", TAM_FUND, degerler)


def test_tanim_on_kayit_kosullarini_kapsar():
    assert set(pozisyon.SINYAL_DEGERLERI) == set(config.HIPOTEZ_IZGARASI)
    for adlar in pozisyon.SINYAL_DEGERLERI.values():
        assert len(adlar) == len(set(adlar)) and adlar
