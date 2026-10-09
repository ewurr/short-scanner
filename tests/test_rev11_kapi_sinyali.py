"""Rev.11 uygulamasi madde 4 ve 5: kapi sinyal degerlerini kendisi hesaplar; rol ayrimi.

On-kayit §5 (rev.11): "Izgara parametreleri ... kod bu degerleri tek bir yerden, on-kayit degeri
olarak okur. Olay ya da kontrol ureten her cagri, hipotezi ve yapilandirmayi birlikte alir;
izgarada bulunmayan bir parametre demeti hata verir."
On-kayit §6 (rev.11) "Kontrolun ne olctugu": "Kontrol bari, olayin sinyal yapisini taklit etmez:
kontrolde hipotezin sinyal kosullari aranmaz. ... Kontrol bari icin gereken: uygunluk filtresi,
donem uyeligi, fiyat ve funding tamligi, ve §4'teki tek karar noktasinin butun kosullari. Sinyal
degerleri kontrol tarafinda yalnizca tek bir amacla hesaplanir: K2'nin 'o anda olay uretmemis'
sartini dogrulamak. ... sinyal degeri veri eksikligi yuzunden hesaplanamiyorsa o bar kontrol
olamaz; sinyal degeri hesaplanip kosulu saglamiyorsa bar kontrol adayidir."

Testler sentetik serileri §5'teki kosullari saglayacak sekilde kurar ve kapinin kararini okur;
hicbir sinyal DEGERI ya da getiri raporlanmaz. Aga cikmaz.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import config
from data import pencere, pozisyon, sinyal
from kapi_yardimcisi import veri
from kume_yardimcisi import kume_adi
from sinyal_yardimcisi import kontrol, olay, yapilandirma
from uygunluk_yardimcisi import esikler

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
G1 = pd.Timedelta(days=1)

# Gunluk quote hacmi 6 x 1e7 = 6e7; H1/H2 esigi 1e7, H3 esigi 2e6 (on-kayit §2).
HACIM = 1e7


def _duz(bas, son, fiyat=1.0, hacim=HACIM) -> pd.DataFrame:
    """Duz 4h serisi: sabit fiyat ve bar basina sabit quote hacmi."""
    z = pd.date_range(bas, son, freq="4h")
    return pd.DataFrame({"open_time": z, "open": fiyat, "high": fiyat, "low": fiyat, "close": fiyat,
                         "quote_volume": float(hacim)})


def _fund(bas, son, oran=0.0005) -> pd.DataFrame:
    z = pd.date_range(bas, son, freq="8h")
    return pd.DataFrame({"odeme_zamani": z, "aralik_saat": 8.0, "oran": 0.0, "oran_8h": float(oran)})


def _ayarla(mumlar: pd.DataFrame, zaman, **alanlar) -> pd.DataFrame:
    m = mumlar.copy()
    maske = pd.DatetimeIndex(m["open_time"]) == pd.Timestamp(zaman)
    assert bool(maske.any()), f"{zaman} seride yok"
    for alan, deger in alanlar.items():
        m.loc[maske, alan] = deger
    return m


def _aralik_ayarla(mumlar: pd.DataFrame, bas, son, **alanlar) -> pd.DataFrame:
    m = mumlar.copy()
    z = pd.DatetimeIndex(m["open_time"])
    maske = (z >= pd.Timestamp(bas)) & (z <= pd.Timestamp(son))
    assert bool(maske.any())
    for alan, deger in alanlar.items():
        m.loc[maske, alan] = deger
    return m


def _karar(hipotez, mumlar, fund, db, b, t, **ek):
    tanim = pencere.hipotez_ufuklari(hipotez)
    return pozisyon.olay_karari(t, tanim.birincil, tanim.bar, hipotez=hipotez,
                                birincil_ufuk=tanim.birincil, kume=kume_adi(t),
                                **veri(mumlar, fund, db, b, uygun_bas=db, hacim=6 * HACIM),
                                **ek, **esikler(tanim.bar))


# --- H2: kapi kosullari kendisi hesaplar -------------------------------------------------------

DB2, B2 = T("2025-01-01"), T("2025-06-30 20:00")
T2 = T("2025-03-10 04:00")
Y2 = yapilandirma("H2")      # izgaranin ilk yapilandirmasi: phi = 0.0003, k = 3
FUND2 = _fund(DB2, B2 + H4)


def _h2_olay_serisi() -> pd.DataFrame:
    """H2'nin uc kosulunu da saglayan seri (on-kayit §5 H2):
      1. funding ortalamasi 0.0005 >= φ = 0.0003,
      2. `close[t] / close[t-30] - 1 = 0.20 >= 0.10`,
      3. `close[t] = 1.2 < min(low[t-3..t-1]) = 1.5`.
    """
    m = _duz(DB2, B2)
    m = _aralik_ayarla(m, T2 - 3 * H4, T2 - H4, low=1.5, high=1.5, close=1.0, open=1.0)
    return _ayarla(m, T2, close=1.2, high=1.2, low=1.2, open=1.2)


def test_h2_olay_kapida_hesaplanan_degerlerle_olusur():
    p = _karar("H2", _h2_olay_serisi(), FUND2, DB2, B2, T2, **olay("H2"))
    assert p.hipotez == "H2" and p.rol == "olay"
    assert p.yapilandirma == sinyal.yapilandirma_kimligi("H2", Y2)


def test_h2_kirilim_olmayan_barda_olay_olusmaz():
    """`close[t] = 1.0`, dip 1.5'un altinda degil -> kirilim yok."""
    m = _aralik_ayarla(_duz(DB2, B2), T2 - 3 * H4, T2 - H4, low=1.5, high=1.5)
    with pytest.raises(pozisyon.SinyalKosuluSaglanmadi) as hata:
        _karar("H2", m, FUND2, DB2, B2, T2, **olay("H2"))
    assert pencere.ret_gerekcesi(hata.value) == "sinyal_kosulu_saglanmadi"


def test_h2_yetersiz_yukselis_olay_uretmez():
    """Kirilim var ama `close[t] / close[t-30] - 1 = 0.05 < 0.10`."""
    m = _duz(DB2, B2)
    m = _aralik_ayarla(m, T2 - 3 * H4, T2 - H4, low=1.5, high=1.5)
    m = _ayarla(m, T2, close=1.05, high=1.05, low=1.05, open=1.05)
    with pytest.raises(pozisyon.SinyalKosuluSaglanmadi):
        _karar("H2", m, FUND2, DB2, B2, T2, **olay("H2"))


def test_h2_funding_esigi_altinda_olay_uretmez():
    """φ = 0.0003; funding ortalamasi 0.0001."""
    with pytest.raises(pozisyon.SinyalKosuluSaglanmadi):
        _karar("H2", _h2_olay_serisi(), _fund(DB2, B2 + H4, oran=0.0001), DB2, B2, T2, **olay("H2"))


def test_h2_izgaradaki_phi_degeri_karari_degistirir():
    """φ = 0.0010 yapilandirmasinda ayni bar olay uretmez (funding ortalamasi 0.0005)."""
    _karar("H2", _h2_olay_serisi(), FUND2, DB2, B2, T2, **olay("H2", phi=0.0003))
    with pytest.raises(pozisyon.SinyalKosuluSaglanmadi):
        _karar("H2", _h2_olay_serisi(), FUND2, DB2, B2, T2, **olay("H2", phi=0.0010))


def test_h2_izgaradaki_k_degeri_pencereyi_degistirir():
    """k = 12 iken kirilim penceresi `[t-12..t-1]` olur; oradaki dip 1.0'dir ve `close[t] = 1.2`
    onun altinda degil -> olay uretmez. k = 3 iken (dip 1.5) uretir."""
    m = _h2_olay_serisi()
    _karar("H2", m, FUND2, DB2, B2, T2, **olay("H2", k=3))
    with pytest.raises(pozisyon.SinyalKosuluSaglanmadi):
        _karar("H2", m, FUND2, DB2, B2, T2, **olay("H2", k=12))


def test_h2_eksik_bar_sinyal_penceresini_dusurur():
    """On-kayit §2 "Tamlik sarti": `close[t-30]` tamlik penceresi `[t-30..t]`; aradaki bir bar
    eksikse deger hesaplanmaz ve olay olusmaz."""
    m = _h2_olay_serisi()
    eksik = m.loc[pd.DatetimeIndex(m["open_time"]) != T2 - 10 * H4].reset_index(drop=True)
    with pytest.raises(pozisyon.SinyalPenceresiTamDegil) as hata:
        _karar("H2", eksik, FUND2, DB2, B2, T2, **olay("H2"))
    assert pencere.ret_gerekcesi(hata.value) == "sinyal_penceresi_tam_degil"


def test_h2_funding_penceresi_bosluklu_oldugunda_olay_olusmaz():
    """H2'nin funding ortalamasi kapida gercek funding serisinden kurulur; penceredeki bir odeme
    eksikse (zincir kosulu) deger hesaplanmaz."""
    fr = FUND2.loc[FUND2["odeme_zamani"] != T("2025-03-09 16:00")].reset_index(drop=True)
    with pytest.raises(pozisyon.SinyalPenceresiTamDegil):
        _karar("H2", _h2_olay_serisi(), fr, DB2, B2, T2, **olay("H2"))


# --- Sinyal degerleri disaridan verilemez (Rev.11 madde 4) ------------------------------------


def test_sinyal_degerleri_anahtar_sozcugu_kalkti():
    """"Sinyal degerleri disaridan verilemesin." Eski anahtar sozcuk programlama hatasi verir."""
    tanim = pencere.hipotez_ufuklari("H2")
    with pytest.raises(TypeError, match="sinyal_degerleri"):
        pozisyon.olay_karari(T2, tanim.birincil, tanim.bar, hipotez="H2", birincil_ufuk=tanim.birincil,
                             kume=kume_adi(T2), **veri(_h2_olay_serisi(), FUND2, DB2, B2, uygun_bas=DB2,
                                                       hacim=6 * HACIM),
                             sinyal_degerleri={"funding_24s": 1.0}, **olay("H2"), **esikler(tanim.bar))


def test_yapilandirma_zorunlu():
    tanim = pencere.hipotez_ufuklari("H2")
    with pytest.raises(TypeError):
        pozisyon.olay_karari(T2, tanim.birincil, tanim.bar, hipotez="H2", birincil_ufuk=tanim.birincil,
                             kume=kume_adi(T2), rol="olay", capa=None,
                             **veri(_h2_olay_serisi(), FUND2, DB2, B2, uygun_bas=DB2, hacim=6 * HACIM),
                             **esikler(tanim.bar))


@pytest.mark.parametrize("bozuk", [{"phi": 0.0004, "k": 3}, {"phi": 0.0003}, {"phi": 0.0003, "k": 5}])
def test_izgarada_olmayan_yapilandirma_hata_verir(bozuk):
    with pytest.raises(sinyal.YapilandirmaHatasi):
        _karar("H2", _h2_olay_serisi(), FUND2, DB2, B2, T2,
               yapilandirma=bozuk, rol="olay", capa=None)


@pytest.mark.parametrize("bozuk", ["olay2", "k1", "K3", "", 1, None])
def test_bilinmeyen_rol_hata_verir(bozuk):
    with pytest.raises((TypeError, ValueError)):
        _karar("H2", _h2_olay_serisi(), FUND2, DB2, B2, T2,
               yapilandirma=Y2, rol=bozuk, capa=None)


# --- Rol: K1 (on-kayit §6 rev.11) -------------------------------------------------------------


def test_k1_kontrol_barinda_sinyal_kosullari_aranmaz():
    """Duz seride H2'nin hicbir kosulu saglanmaz; K1 kontrolu yine olusur."""
    p = _karar("H2", _duz(DB2, B2), FUND2, DB2, B2, T2, **kontrol("H2", "K1"))
    assert p.rol == "K1" and p.hipotez == "H2"


def test_k1_uygunluk_ve_funding_tamligini_yine_ister():
    """"Kontrol bari icin gereken: uygunluk filtresi, donem uyeligi, fiyat ve funding tamligi."""
    # Funding'i bosluklu seri: pozisyon funding'i tam degil -> kontrol olusmaz.
    fr = FUND2.loc[FUND2["odeme_zamani"] != T("2025-03-12 08:00")].reset_index(drop=True)
    with pytest.raises(pozisyon.FundingTamDegil):
        _karar("H2", _duz(DB2, B2), fr, DB2, B2, T2, **kontrol("H2", "K1"))
    # Hacmi esigin altinda seri: uygun degil -> kontrol olusmaz.
    with pytest.raises(pozisyon.UygunDegil):
        tanim = pencere.hipotez_ufuklari("H2")
        pozisyon.olay_karari(T2, tanim.birincil, tanim.bar, hipotez="H2", birincil_ufuk=tanim.birincil,
                             kume=kume_adi(T2), **veri(_duz(DB2, B2, hacim=1e3), FUND2, DB2, B2,
                                                       uygun_bas=DB2, hacim=6e3),
                             **kontrol("H2", "K1"), **esikler(tanim.bar))


def test_k1_sinyal_penceresi_eksik_olsa_bile_kontrol_olusur():
    """K1'in olcutu zamansal uzakliktir; sinyal degeri hic hesaplanmaz (on-kayit §6 rev.11).

    Eksik bar t'nin KENDI gunune (2025-03-10 00:00) konur: o gun uygunluk penceresinin disindadir
    (on-kayit §2 "Uygunluk penceresi ve t gunu"), bu yuzden eksiklik yalnizca sinyal
    pencerelerini (kirilim dibi ve `close[t-30]`) dusurur ve iki rolu ayirir."""
    m = _duz(DB2, B2)
    eksik = m.loc[pd.DatetimeIndex(m["open_time"]) != T2 - H4].reset_index(drop=True)
    p = _karar("H2", eksik, FUND2, DB2, B2, T2, **kontrol("H2", "K1"))
    assert p.rol == "K1"
    # Ayni eksiklik K2 tarafinda kontrolu dusurur.
    with pytest.raises(pozisyon.SinyalPenceresiTamDegil):
        _karar("H2", eksik, FUND2, DB2, B2, T2, **kontrol("H2", "K2"))


def test_k1_de_h2_funding_penceresi_aranmaz():
    fr = FUND2.loc[FUND2["odeme_zamani"] != T("2025-03-09 16:00")].reset_index(drop=True)
    assert _karar("H2", _duz(DB2, B2), fr, DB2, B2, T2, **kontrol("H2", "K1")).rol == "K1"


# --- Rol: K2 (on-kayit §6 rev.11) -------------------------------------------------------------


def test_k2_kosulu_saglamayan_bar_kontrol_adayidir():
    p = _karar("H2", _duz(DB2, B2), FUND2, DB2, B2, T2, **kontrol("H2", "K2"))
    assert p.rol == "K2"


def test_k2_olay_ureten_bar_kontrol_olamaz():
    """"o anda olay uretmemis diger coinlerden": kosullar saglaniyorsa bar K2 adayi degildir."""
    with pytest.raises(pozisyon.OlayUretmis) as hata:
        _karar("H2", _h2_olay_serisi(), FUND2, DB2, B2, T2, **kontrol("H2", "K2"))
    assert pencere.ret_gerekcesi(hata.value) == "olay_uretmis"


def test_k2_sinyali_hesaplanamayan_bar_kontrol_olamaz():
    """"sinyal degeri veri eksikligi yuzunden hesaplanamiyorsa o bar kontrol olamaz" (§2
    "Tamlik sarti"). Ayni eksiklik K1'de kontrolu dusurmez (yukaridaki test)."""
    m = _duz(DB2, B2)
    eksik = m.loc[pd.DatetimeIndex(m["open_time"]) != T2 - H4].reset_index(drop=True)
    with pytest.raises(pozisyon.SinyalPenceresiTamDegil):
        _karar("H2", eksik, FUND2, DB2, B2, T2, **kontrol("H2", "K2"))


def test_k2_funding_penceresi_bosluklu_oldugunda_kontrol_olamaz():
    fr = FUND2.loc[FUND2["odeme_zamani"] != T("2025-03-09 16:00")].reset_index(drop=True)
    with pytest.raises(pozisyon.SinyalPenceresiTamDegil):
        _karar("H2", _duz(DB2, B2), fr, DB2, B2, T2, **kontrol("H2", "K2"))


# --- H1: capa (on-kayit §5 H1, §6 rev.11) -----------------------------------------------------

DB1, B1 = T("2025-01-01"), T("2025-06-30 20:00")
P1 = T("2025-03-10 04:00")          # pump bari
T1 = P1 + 3 * H4                    # teyit bari
Y1 = yapilandirma("H1")             # θ = 0.20, δ = 0.08
FUND1 = _fund(DB1, B1 + H4)


def _h1_olay_serisi() -> pd.DataFrame:
    """H1'in pump ve teyit kosullarini saglayan seri (on-kayit §5 H1):
      - pump: `close[p] / min(low[p-6..p-1]) - 1 = 0.25 >= θ = 0.20`; son 6 barin hacmi
        6 x 3Q = 18Q, 180 barlik 6'li toplam medyani 6Q -> 18Q >= 3 x 6Q,
      - tepe: `max(high[p .. t-1]) = 1.3`,
      - teyit: `close[t] = 1.0 <= 1.3 x (1 - 0.08) = 1.196` ve `high[t] = 1.0 < 1.3`.
    """
    m = _duz(DB1, B1)
    m = _aralik_ayarla(m, P1 - 5 * H4, P1, quote_volume=3 * HACIM)
    m = _ayarla(m, P1, close=1.25, high=1.30, low=1.0, open=1.0)
    return m


def test_h1_olay_capayla_olusur():
    p = _karar("H1", _h1_olay_serisi(), FUND1, DB1, B1, T1, **olay("H1", capa=P1))
    assert p.hipotez == "H1" and p.rol == "olay"


def test_h1_capa_pump_kosulunu_saglamazsa_olay_olusmaz():
    """Capa cagirandan gelir ama kapi onu DOGRULAR: pump kosulu capada yeniden hesaplanir."""
    m = _duz(DB1, B1)  # hicbir barda pump yok
    m = _ayarla(m, P1, high=1.30)  # tepe var, pump yok
    with pytest.raises(pozisyon.SinyalKosuluSaglanmadi):
        _karar("H1", m, FUND1, DB1, B1, T1, **olay("H1", capa=P1))


def test_h1_teyit_esigi_gecilmezse_olay_olusmaz():
    """δ = 0.16 yapilandirmasinda esik `1.3 x 0.84 = 1.092`; `close[t] = 1.15` gecmez."""
    m = _ayarla(_h1_olay_serisi(), T1, close=1.15, high=1.15, low=1.15, open=1.15)
    _karar("H1", m, FUND1, DB1, B1, T1, **olay("H1", capa=P1, delta=0.08))
    with pytest.raises(pozisyon.SinyalKosuluSaglanmadi):
        _karar("H1", m, FUND1, DB1, B1, T1, **olay("H1", capa=P1, delta=0.16))


def test_h1_teyit_barinin_high_degeri_tepeyi_asarsa_olay_olusmaz():
    """On-kayit §5 H1 madde 3: "aynı barda `high < tepe`"."""
    m = _ayarla(_h1_olay_serisi(), T1, high=1.35)
    with pytest.raises(pozisyon.SinyalKosuluSaglanmadi):
        _karar("H1", m, FUND1, DB1, B1, T1, **olay("H1", capa=P1))


def test_h1_capa_olay_rolunde_zorunlu():
    with pytest.raises(TypeError, match="capa"):
        _karar("H1", _h1_olay_serisi(), FUND1, DB1, B1, T1,
               yapilandirma=Y1, rol="olay", capa=None)


@pytest.mark.parametrize("rol", ["K1", "K2"])
def test_h1_kontrol_rolunde_capa_verilemez(rol):
    with pytest.raises(TypeError, match="capa"):
        _karar("H1", _h1_olay_serisi(), FUND1, DB1, B1, T1,
               yapilandirma=Y1, rol=rol, capa=P1)


@pytest.mark.parametrize("hipotez,t", [("H2", T2), ("H3", T("2025-03-10"))])
def test_capasiz_hipotezlerde_capa_verilemez(hipotez, t):
    with pytest.raises(TypeError, match="capa"):
        _karar(hipotez, _duz(DB2, B2), FUND2, DB2, B2, t,
               yapilandirma=yapilandirma(hipotez), rol="olay", capa=t)


@pytest.mark.parametrize("rol", ["K1", "K2"])
def test_h1_kontrol_barinda_pump_aranmaz(rol):
    """On-kayit §6 rev.11: "H1'in kontrol barinda pump bari, dip penceresi ve tepe aranmaz."
    Duz seride (pump yok, tepe yok) H1 kontrolu olusur; K2 de ayni yoldan gecer, cunku H1'in
    "olay uretmemis" sarti ornekleme adiminda olay kumesine gore uygulanir."""
    p = _karar("H1", _duz(DB1, B1), FUND1, DB1, B1, T1, **kontrol("H1", rol))
    assert p.rol == rol and p.hipotez == "H1"


def test_h1_k2_barinda_sinyal_hic_hesaplanmaz():
    """Pump kosulunu SAGLAYAN bir bar bile H1'de K2 adayi olmaktan cikmaz: kapi H1'in kontrol
    barinda sinyal hesaplamaz (on-kayit §6 rev.11 gerekcesi: kontrol barinda capa yoktur)."""
    assert not pozisyon._sinyal_gerekli("H1", "K2")
    assert pozisyon._sinyal_gerekli("H2", "K2") and pozisyon._sinyal_gerekli("H3", "K2")
    assert pozisyon._sinyal_gerekli("H1", "olay")
    assert not pozisyon._sinyal_gerekli("H1", "K1") and not pozisyon._sinyal_gerekli("H2", "K1")
    p = _karar("H1", _h1_olay_serisi(), FUND1, DB1, B1, T1, **kontrol("H1", "K2"))
    assert p.rol == "K2"


# --- H3 (on-kayit §5 H3) ----------------------------------------------------------------------

DB3, B3 = T("2024-09-01"), T("2025-06-30 20:00")
T3 = T("2025-03-10")
Y3 = yapilandirma("H3")             # ν = 0.50, τ = 0.15
FUND3 = _fund(DB3, B3 + H4)


def _h3_olay_serisi() -> pd.DataFrame:
    """H3'un iki kosulunu da saglayan seri (on-kayit §5 H3):
      1. son 30 gunun medyan hacmi (6 x 5e5 = 3e6) <= (1 - 0.50) x gun -120..-31 medyani
         (6 x 1e7 = 6e7) -> 3e6 <= 3e7,
      2. `close[t] = 0.8 < SMA50[t]` ve `close[t] / close[t-30] - 1 = -0.20 <= -0.15`.
    H3'un uygunluk esigi 2e6; son 30 gunun medyan hacmi 3e6 esigi gecer.
    """
    m = _duz(DB3, B3)
    m = _aralik_ayarla(m, T3 - 29 * G1, T3 + G1, quote_volume=5e5)
    return _aralik_ayarla(m, T3 - 20 * G1, T3 + G1, close=0.8, open=0.8, high=0.8, low=0.8)


def test_h3_olay_olusur():
    p = _karar("H3", _h3_olay_serisi(), FUND3, DB3, B3, T3, **olay("H3"))
    assert p.hipotez == "H3" and p.rol == "olay"


def test_h3_hacim_cokusu_yoksa_olay_olusmaz():
    m = _aralik_ayarla(_duz(DB3, B3), T3 - 20 * G1, T3 + G1, close=0.8, open=0.8, high=0.8, low=0.8)
    with pytest.raises(pozisyon.SinyalKosuluSaglanmadi):
        _karar("H3", m, FUND3, DB3, B3, T3, **olay("H3"))


def test_h3_trend_kosulu_saglanmazsa_olay_olusmaz():
    m = _aralik_ayarla(_duz(DB3, B3), T3 - 29 * G1, T3 + G1, quote_volume=5e5)
    with pytest.raises(pozisyon.SinyalKosuluSaglanmadi):
        _karar("H3", m, FUND3, DB3, B3, T3, **olay("H3"))


def test_h3_tau_izgara_degeri_karari_degistirir():
    """τ = 0.35 iken `close[t] / close[t-30] - 1 = -0.20` esigi gecmez."""
    m = _h3_olay_serisi()
    _karar("H3", m, FUND3, DB3, B3, T3, **olay("H3", tau=0.15))
    with pytest.raises(pozisyon.SinyalKosuluSaglanmadi):
        _karar("H3", m, FUND3, DB3, B3, T3, **olay("H3", tau=0.35))


def test_h3_eksik_gun_sinyal_penceresini_dusurur():
    """1d serisinde eksik gun (gunun alti 4h barindan biri yok) pencereyi dusurur."""
    m = _h3_olay_serisi()
    eksik_gun = T3 - 10 * G1
    z = pd.DatetimeIndex(m["open_time"])
    m = m.loc[z != eksik_gun + pd.Timedelta(hours=8)].reset_index(drop=True)
    with pytest.raises(pozisyon.SinyalPenceresiTamDegil):
        _karar("H3", m, FUND3, DB3, B3, T3, **olay("H3"))


# --- Onayli pozisyon yapilandirma ve rol tasir ------------------------------------------------


def test_onayli_pozisyon_yapilandirma_ve_rol_tasir():
    """Ornekleme ve dizi kurallari "ayni yapilandirmanin olusmus olaylari"na gore isler."""
    p = _karar("H2", _h2_olay_serisi(), FUND2, DB2, B2, T2, **olay("H2"))
    assert p.yapilandirma == "H2:phi=0.0003,k=3" and p.rol == "olay"
    pozisyon.onay_dogrula(p)


def test_yapilandirma_ya_da_rol_degistirilmis_pozisyon_dogrulanmaz():
    import dataclasses

    p = _karar("H2", _h2_olay_serisi(), FUND2, DB2, B2, T2, **olay("H2"))
    with pytest.raises(ValueError):
        pozisyon.onay_dogrula(dataclasses.replace(p, rol="K1"))
    with pytest.raises(ValueError):
        pozisyon.onay_dogrula(dataclasses.replace(p, yapilandirma="H2:phi=0.001,k=3"))


def test_sinyal_degerleri_adlari_sinyal_modulunden():
    assert pozisyon.SINYAL_DEGERLERI is sinyal.DEGER_ADLARI
    assert set(pozisyon.SINYAL_DEGERLERI) == set(config.HIPOTEZ_IZGARASI)
