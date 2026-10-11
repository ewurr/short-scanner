"""Karar noktasi veriyi kendisi yukler; sonlu olmayan degerler ve UTC (kapi sertlestirme turu 2).

- Denetci KS D-B1, KS D-B2: fiyat, funding ve 1d cerceveleri cagirandan alinmaz. Kapi sembol ve kume adiyla
  kume korumali yukleyiciden okur, kume araligina keser, 1d serisini 4h barlardan tek yol
  `klines.gunluge_cevir` ile turetir (on-kayit §2 rev.8 "1 gunluk barlar": "Bu seri tektir").
- Denetci KS D-B3: sinyal bari (t) hipotezin izgarasindaki donem ici seride yoksa olay ya da kontrol
  olusmaz (`SinyalBariYok`).
- Sizinti testcisinin inf bulgusu: sonlu olmayan funding toplami, P0, P1 ya da MAE penceresindeki high
  acik ValueError. On-kayit bu durumu tanimlamaz; kapi bir olay-olusmaz kurali icat etmez.
- Denetci KS D-B5 (dogrulandi): UTC disi saat dilimli sinyal zamani H1/H2 olaylarini sessizce `UygunDegil`
  ile dusuruyordu; kapi artik acik hata verir.
Aga cikmaz.
"""

from __future__ import annotations

import dataclasses
import inspect

import numpy as np
import pandas as pd
import pytest

import config
from data import eligibility, funding, pencere, pozisyon
from kapi_yardimcisi import SENTETIK_VERI, veri
from sinyal_yardimcisi import kontrol
from uygunluk_yardimcisi import esikler

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H = lambda n: pd.Timedelta(hours=n)  # noqa: E731

# Rev.12 (§6 rev.12 "Kontrol barinda sinyal pencereleri"): kontrol bari capasiz
# pencerelerin hesaplanabilmesini gerektirir (H1: 185 bar, H3: 121 gun gecmis), bu yuzden
# donem basi sinyalden yeterince geriye alindi. Testlerin iddialari degismedi.
DB, B = T("2024-09-01"), T("2025-06-30 20:00")
Z = pd.date_range(T("2025-03-01"), B, freq="4h")
MUM = pd.DataFrame({"open_time": Z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
FUND = pd.DataFrame({"odeme_zamani": pd.date_range(DB, B + H(4), freq="8h"), "aralik_saat": 8.0,
                     "oran": 1e-4, "oran_8h": 1e-4})
SINYAL_T = {"H1": T("2025-03-10 04:00"), "H2": T("2025-03-10 04:00"), "H3": T("2025-03-10")}


def _karar(hipotez="H1", mum=MUM, fr=FUND, t=None, **ek):
    tanim = pencere.hipotez_ufuklari(hipotez)
    return pozisyon.olay_karari(SINYAL_T[hipotez] if t is None else t, tanim.birincil, tanim.bar, hipotez=hipotez,
                                birincil_ufuk=tanim.birincil, kume="KESIF",
                                **veri(mum, fr, DB, B, uygun_bas=DB, **ek), **kontrol(hipotez),
                                **esikler(tanim.bar))


# --- 1. Cerceveler cagirandan alinmaz --------------------------------------------------------------


def test_karar_noktasi_cerceve_parametresi_almaz():
    parametreler = set(inspect.signature(pozisyon.olay_karari).parameters)
    assert not parametreler & {"mumlar_4h", "funding", "gunluk_mumlar"}
    assert "sembol" in parametreler and "kume" in parametreler
    assert set(inspect.signature(pozisyon.mae).parameters) == {"pozisyon"}
    assert set(inspect.signature(funding.pozisyon_fundingi).parameters) == {"pozisyon"}


@pytest.mark.parametrize("ad", ["mumlar_4h", "funding", "gunluk_mumlar"])
def test_cerceve_anahtar_sozcukle_de_verilemez(ad):
    with pytest.raises(TypeError, match="unexpected keyword"):
        tanim = pencere.hipotez_ufuklari("H1")
        pozisyon.olay_karari(SINYAL_T["H1"], tanim.birincil, tanim.bar, hipotez="H1", birincil_ufuk=tanim.birincil,
                             kume="KESIF", **veri(MUM, FUND, DB, B, uygun_bas=DB), **kontrol("H1"),
                             **esikler(tanim.bar), **{ad: pd.DataFrame()})


@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_kapi_kayittaki_veriyi_kullanir(hipotez):
    p = _karar(hipotez)
    pozisyon.onay_dogrula(p)
    assert (p.sembol, p.kume, p.donem_no) == (p.sembol, "KESIF", 0) and p.sembol.startswith("TESTV")


def test_imza_kimligi_kapsar():
    p = _karar()
    for alan, deger in (("sembol", "BTCUSDT"), ("kume", "C2"), ("donem_no", 1)):
        with pytest.raises(ValueError):
            pozisyon.pozisyon_fiyatlari(dataclasses.replace(p, **{alan: deger}))


def test_kume_sonrasi_veri_kapida_kesilir():
    """Yukleyici kume disina tasan veri dondurse de kapi kume araligina keser: giris bari C2'de ise yok."""
    db = T("2025-06-01")
    z = pd.date_range(db, T("2025-09-10 20:00"), freq="4h")
    mum = pd.DataFrame({"open_time": z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
    fr = pd.DataFrame({"odeme_zamani": pd.date_range(db, T("2025-09-11"), freq="8h"), "aralik_saat": 8.0,
                       "oran": 0.0, "oran_8h": 0.0})
    tanim = pencere.hipotez_ufuklari("H1")
    with pytest.raises(pencere.GirisBariYok):
        pozisyon.olay_karari(T("2025-08-31 20:00"), tanim.birincil, tanim.bar, hipotez="H1",
                             birincil_ufuk=tanim.birincil, kume="KESIF",
                             **veri(mum, fr, db, T("2025-09-10 20:00"), uygun_bas=db), **kontrol("H1"),
                             **esikler(tanim.bar))


# --- 1d serisi 4h barlardan turetilir (tek seri) -------------------------------------------------------


def test_bir_4h_bari_eksik_gun_uygunluk_penceresinde_eksik_sayilir():
    """Borsanin 1d dosyasi 4h bari eksik gunu de satir olarak tasir (denetci KS D-B2). Kapinin 1d serisi o
    gunu olusturmaz (alti barin tamami sart); uygunluk penceresi tam olmaz ve olay olusmaz.

    Hipotez H2 ve eksik bar t'den 10 gun geride: rev.12 ile kontrol bari capasiz pencerelerin
    hesaplanabilmesini de gerektiriyor (§6) ve H1'in 185 barlik hacim penceresi uygunluk
    penceresinin tamamini kapsiyor; H2'nin en genis capasiz penceresi 31 bar (5,17 gun) oldugu icin
    uygunluk gerekcesi onda tek basina olculebilir. Iddia degismedi: ret gerekcesi `uygun_degil`."""
    eksik_bar = SINYAL_T["H2"].floor("D") - pd.Timedelta(days=10) + H(8)
    tam = veri(MUM, FUND, DB, B, uygun_bas=DB)
    m, f = SENTETIK_VERI[tam["sembol"]]
    tanim = pencere.hipotez_ufuklari("H2")
    assert (m["open_time"] == eksik_bar).any(), "test kurulumu: eksik bar seride olmali"
    kayit = veri(m.loc[m["open_time"] != eksik_bar], f, DB, B, ham=True)
    ortak = dict(hipotez="H2", birincil_ufuk=tanim.birincil, kume="KESIF", **kontrol("H2"),
                 **esikler(tanim.bar))
    pozisyon.onay_dogrula(pozisyon.olay_karari(SINYAL_T["H2"], tanim.birincil, tanim.bar, **ortak, **tam))
    with pytest.raises(pozisyon.UygunDegil) as hata:
        pozisyon.olay_karari(SINYAL_T["H2"], tanim.birincil, tanim.bar, **ortak, **kayit)
    assert pencere.ret_gerekcesi(hata.value) == "uygun_degil"


# --- Sinyal bari (t) seride olmali (KS D-B3) ---------------------------------------------------------------


def test_4h_sinyal_bari_eksikse_olay_olusmaz():
    t = SINYAL_T["H1"]
    eksik = MUM.loc[MUM["open_time"] != t]
    assert (MUM["open_time"] == t + H(4)).any()  # t+1 var
    with pytest.raises(pozisyon.SinyalBariYok) as hata:
        _karar("H1", mum=eksik)
    assert pencere.ret_gerekcesi(hata.value) == "sinyal_bari_yok"


def test_1d_sinyal_gunu_eksikse_olay_olusmaz():
    """H3: t gununun tek bir 4h bari eksikse t gunu 1d serisinde yoktur; ertesi gun (giris) tamdir."""
    t = SINYAL_T["H3"]
    eksik = MUM.loc[MUM["open_time"] != t + H(8)]
    with pytest.raises(pozisyon.SinyalBariYok):
        _karar("H3", mum=eksik)
    pozisyon.onay_dogrula(_karar("H3"))


# --- 2. Sonlu olmayan degerler -----------------------------------------------------------------------------


def test_funding_kaydinda_inf_oran_pozisyonu_reddeder():
    """Pozisyon penceresi icindeki (giristen sonraki) bir kayitta oran = inf: onaylanmaz.

    REV.11 madde 8 ("Gecerli oran") bu durumu TANIMLADI: "NaN, +sonsuz ya da -sonsuz oran
    tasiyan pozisyonun funding'i tam degildir ve pozisyon olusmaz." Yani bu bir VeriHatasi
    degil bir RET GEREKCESIDIR; denetim kayit duzeyinde (`oran_gecerli`) yapilir ve kapi
    `_sonlu`ya hic ulasmaz. Rev.11 oncesi beklenti "funding toplami sonlu degil" (ValueError)
    idi."""
    p = _karar()
    icerde = FUND.index[(FUND["odeme_zamani"] > p.plan.giris) & (FUND["odeme_zamani"] <= p.plan.cikis_ani)]
    for deger in (float("inf"), float("-inf")):
        fr = FUND.copy()
        fr.loc[icerde[0], "oran"] = deger
        with pytest.raises(pozisyon.FundingTamDegil):
            _karar(fr=fr)


def test_nan_oran_funding_tam_degil_olarak_kalir():
    """NaN oran onceki davranisinda kalir (FundingTamDegil). Rev.11 madde 8 bunu on-kayita
    yazdi ve ayni gerekceyi +-sonsuza da genisletti (yukaridaki test)."""
    p = _karar()
    fr = FUND.copy()
    fr.loc[FUND.index[FUND["odeme_zamani"] > p.plan.giris][0], "oran"] = float("nan")
    with pytest.raises(pozisyon.FundingTamDegil):
        _karar(fr=fr)


@pytest.mark.parametrize("deger", [float("inf"), float("-inf"), float("nan")])
@pytest.mark.parametrize("yer", ["P0", "P1", "high"])
def test_sonlu_olmayan_fiyat_reddedilir(yer, deger):
    p = _karar()
    m = MUM.copy()
    if yer == "P0":
        m.loc[m["open_time"] == p.plan.giris, "open"] = deger
    elif yer == "P1":
        m.loc[m["open_time"] == p.plan.cikis.zaman, p.plan.cikis.fiyat_alani] = deger
    else:
        m.loc[m["open_time"] == p.plan.giris + H(8), "high"] = deger
    with pytest.raises(ValueError, match="sonlu degil"):
        _karar(mum=m)


def test_sonsuz_sinyal_degeri_tamlik_kapisinda_kalir():
    """Rev.11 madde 4: sonsuz bir sinyal degeri artik CAGIRANDAN verilemez; deger kapida
    hesaplanir. Iddia veriye tasindi: funding oraninda +sonsuz varsa H2 ortalamasi hesaplanmaz
    (on-kayit §4 rev.11 "Penceredeki kayitlarin oranlarindan biri ... sonlu degilse ortalama
    hesaplanmaz") ve o barda ne olay ne K2 kontrolu olusur."""
    tanim = pencere.hipotez_ufuklari("H2")
    fr = FUND.copy()
    pencere_ici = (fr["odeme_zamani"] > SINYAL_T["H2"] + H(4) - H(config.H2_FUNDING_PENCERESI_SAAT))         & (fr["odeme_zamani"] <= SINYAL_T["H2"] + H(4))
    assert int(pencere_ici.sum()) >= 1
    fr.loc[fr.index[pencere_ici][0], "oran_8h"] = float("inf")
    with pytest.raises(pozisyon.SinyalPenceresiTamDegil):
        pozisyon.olay_karari(SINYAL_T["H2"], tanim.birincil, tanim.bar, hipotez="H2", birincil_ufuk=tanim.birincil,
                             kume="KESIF", **veri(MUM, fr, DB, B, uygun_bas=DB),
                             **kontrol("H2", "K2"), **esikler(tanim.bar))


# --- 3. UTC (KS D-B5) ----------------------------------------------------------------------------------------


def test_utc_disi_saat_dilimi_uygunlukta_gunu_kaydirir():
    """Dogrulama (mekanizma): ayni an, UTC disi saat dilimiyle verildiginde uygunluk penceresinin gun siniri
    yerel saate kayar ve deger NaN olur (sessiz dusme kaynagi). Kapi bu yuzden UTC disini reddeder."""
    tam = veri(MUM, FUND, DB, B, uygun_bas=DB)
    m, _ = SENTETIK_VERI[tam["sembol"]]
    from data import klines

    gunluk = klines.gunluge_cevir(m, donemler=[pozisyon._DonemSiniri(DB, B)])
    hacim = eligibility.gunluk_hacim_serisi(gunluk)
    t = SINYAL_T["H1"]
    ortak = dict(donem_baslangic=DB, kume_baslangic=None, pencere_gun=config.HACIM_PENCERESI_GUN)
    assert np.isfinite(eligibility.medyan_hacim(hacim, t, **ortak))
    assert np.isnan(eligibility.medyan_hacim(hacim, t.tz_convert("Europe/Istanbul"), **ortak))


@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
@pytest.mark.parametrize("tz", ["Europe/Istanbul", "America/New_York", "Asia/Kolkata"])
def test_utc_disi_sinyal_zamani_acik_hata(hipotez, tz):
    with pytest.raises(ValueError, match="UTC olmali"):
        _karar(hipotez, t=SINYAL_T[hipotez].tz_convert(tz))
    pozisyon.onay_dogrula(_karar(hipotez))


def test_saat_dilimsiz_sinyal_zamani_reddedilir():
    with pytest.raises(TypeError):
        _karar("H1", t=SINYAL_T["H1"].tz_localize(None))


@pytest.mark.parametrize("utc", ["UTC", "Etc/UTC"])
def test_utc_esdegerleri_kabul_edilir(utc):
    pozisyon.onay_dogrula(_karar("H1", t=SINYAL_T["H1"].tz_convert(utc)))


# --- mae ve pozisyon_fundingi de veriyi kendisi yukler ----------------------------------------------------


def test_mae_ve_funding_kimlikle_yukler():
    p = _karar()
    assert np.isfinite(pozisyon.mae(p))
    assert funding.pozisyon_fundingi(p) == p.funding_toplami
    with pytest.raises(TypeError):
        pozisyon.mae(MUM, p)
    with pytest.raises(TypeError):
        funding.pozisyon_fundingi(FUND, p)


def test_mae_karar_sonrasi_degisen_veriyi_okur_ama_kimligi_ayni():
    """`mae` kararla ayni yoldan (sembol, kume) yukler; onayli pozisyon kimligi imzali oldugu icin baska
    bir sembolun verisiyle MAE uretilemez."""
    p = _karar()
    with pytest.raises(ValueError):
        pozisyon.mae(dataclasses.replace(p, sembol="BTCUSDT"))
