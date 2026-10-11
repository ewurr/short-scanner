"""Kontrol barinda capasiz sinyal pencerelerinin hesaplanabilirligi (on-kayit §6, rev.12 (d)).

On-kayit §6 "Kontrol barinda sinyal pencereleri" (rev.12): "Kontrol barinda hipotezin sinyal
KOSULLARI aranmaz, ancak capasiz sinyal pencerelerinin HESAPLANABILIR olmasi gerekir;
hesaplanamiyorsa o bar kontrol olamaz. Bu, §2 'Tamlik sarti'nin acik hukmudur ('o barda olay ya
da kontrol olusmaz') ve HER IKI kontrol kumesi icin gecerlidir. ... Capasiz pencere, tanimi
yalnizca t'ye ve gecmise dayanan penceredir: H1'in dip ve iki hacim penceresi, H2'nin kirilim,
yukselis ve funding pencereleri, H3'un iki hacim penceresi, SMA50 ve dusus trendi orani. H1'in
tepe penceresi bir pump barina capali oldugu icin kontrol barinda tanimsizdir ve aranmaz."

Rev.11'de K1 rolunde sinyal HIC hesaplanmiyordu ve K2 rolunde yalnizca "olay uretmemis" sartini
dogrulamak icin hesaplaniyordu; bu yuzden kontrol havuzuna bir olayin hicbir zaman olusamayacagi
barlar (donem baslari, bosluk sonrasi barlar) girebiliyordu. Bu dosya rev.12'nin sartini uc
hipotez ve iki kontrol rolu icin sabitler. Hicbir sinyal DEGERI ya da getiri raporlanmaz; yalnizca
kapinin karari okunur. Aga cikmaz.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

import config
from data import pencere, pozisyon, sinyal
from kapi_yardimcisi import veri
from kume_yardimcisi import kume_adi
from sinyal_yardimcisi import kontrol, yapilandirma
from uygunluk_yardimcisi import esikler

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
HACIM = 1e7

KONTROL_ROLLERI = ("K1", "K2")


def _duz(bas, son, fiyat=1.0, hacim=HACIM) -> pd.DataFrame:
    z = pd.date_range(bas, son, freq="4h")
    return pd.DataFrame({"open_time": z, "open": fiyat, "high": fiyat, "low": fiyat, "close": fiyat,
                         "quote_volume": float(hacim)})


def _fund(bas, son, oran=0.0005) -> pd.DataFrame:
    z = pd.date_range(bas, son, freq="8h")
    return pd.DataFrame({"odeme_zamani": z, "aralik_saat": 8.0, "oran": 0.0, "oran_8h": float(oran)})


def _karar(hipotez, mumlar, fund, db, b, t, **ek):
    tanim = pencere.hipotez_ufuklari(hipotez)
    return pozisyon.olay_karari(t, tanim.birincil, tanim.bar, hipotez=hipotez,
                                birincil_ufuk=tanim.birincil, kume=kume_adi(t),
                                **veri(mumlar, fund, db, b, uygun_bas=db, hacim=6 * HACIM),
                                **ek, **esikler(tanim.bar))


def _barsiz(mumlar: pd.DataFrame, zaman) -> pd.DataFrame:
    """Verilen 4h barini seriden cikarir (bosluk)."""
    z = pd.DatetimeIndex(mumlar["open_time"])
    assert bool((z == pd.Timestamp(zaman)).any()), f"{zaman} seride yok"
    return mumlar.loc[z != pd.Timestamp(zaman)].reset_index(drop=True)


# --- 1. On-kayittaki capasiz pencere listesi --------------------------------------------------


def test_capasiz_pencere_listesi_on_kayittaki_pencerelerdir():
    """On-kayit §6 rev.12'deki liste birebir: H1'in dip ve iki hacim penceresi; H2'nin kirilim,
    yukselis (`close[t-30]`) ve funding pencereleri; H3'un iki hacim penceresi, SMA50 ve dusus
    trendi orani (`close[t-30]`)."""
    assert sinyal.capasiz_pencere_adlari("H1") == ("dip", "hacim_6", "hacim_medyani_180")
    assert sinyal.capasiz_pencere_adlari("H2") == ("kirilim_dip", "kapanis_30_once", "funding_24s")
    assert sinyal.capasiz_pencere_adlari("H3") == ("hacim_medyani_30g", "hacim_medyani_120_31",
                                                   "sma50", "kapanis_30_once")


def test_h1_tepe_penceresi_capasiz_degildir_kontrol_barinda_aranmaz():
    """"H1'in tepe penceresi bir pump barina capali oldugu icin kontrol barinda tanimsizdir ve
    aranmaz." Tepe (ve pump barinin kapanisi) olay tarafinin deger adlarindadir, capasizlarda yok."""
    assert "tepe" in sinyal.deger_adlari("H1")
    assert "tepe" not in sinyal.capasiz_pencere_adlari("H1")
    assert "pump_kapanis" not in sinyal.capasiz_pencere_adlari("H1")


@pytest.mark.parametrize("hipotez", config.HIPOTEZLER)
def test_capasiz_hesaplanamayan_ad_kumesini_zorlar(hipotez):
    """Eksik ya da fazla ad programlama hatasidir (sessiz gecis olmaz)."""
    adlar = sinyal.capasiz_pencere_adlari(hipotez)
    with pytest.raises(TypeError):
        sinyal.capasiz_hesaplanamayan(hipotez, {a: 1.0 for a in adlar[:-1]})
    with pytest.raises(TypeError):
        sinyal.capasiz_hesaplanamayan(hipotez, {**{a: 1.0 for a in adlar}, "fazla": 1.0})
    assert sinyal.capasiz_hesaplanamayan(hipotez, {a: 1.0 for a in adlar}) == []
    assert sinyal.capasiz_hesaplanamayan(hipotez, {a: float("nan") for a in adlar}) == list(adlar)


# --- 2. H2: her capasiz pencere tek tek kontrolu dusurur --------------------------------------

DB2, B2 = T("2025-01-01"), T("2025-06-30 20:00")
T2 = T("2025-03-10 04:00")
FUND2 = _fund(DB2, B2 + H4)


@pytest.mark.parametrize("rol", KONTROL_ROLLERI)
def test_h2_duz_seride_kontrol_olusur_olumlu_kontrol(rol):
    """Olumlu kontrol: kosullar aranmadigi icin duz seri (kirilim yok, yukselis yok) kontrol olur."""
    assert _karar("H2", _duz(DB2, B2), FUND2, DB2, B2, T2, **kontrol("H2", rol)).rol == rol


@pytest.mark.parametrize("rol", KONTROL_ROLLERI)
def test_h2_kirilim_penceresindeki_bosluk_iki_kontrol_rolunu_de_dusurur(rol):
    """`min(low[t-k..t-1])` (k = 3) penceresindeki eksik bar: pencere hesaplanamaz.

    Eksik bar t'nin KENDI gunune konur: o gun uygunluk penceresinin disindadir (on-kayit §2
    "Uygunluk penceresi ve t gunu"), bu yuzden eksiklik uygunlugu degil sinyal penceresini dusurur.
    """
    with pytest.raises(pozisyon.SinyalPenceresiTamDegil) as hata:
        _karar("H2", _barsiz(_duz(DB2, B2), T2 - H4), FUND2, DB2, B2, T2, **kontrol("H2", rol))
    assert pencere.ret_gerekcesi(hata.value) == "sinyal_penceresi_tam_degil"


@pytest.mark.parametrize("rol", KONTROL_ROLLERI)
def test_h2_yukselis_penceresindeki_bosluk_iki_kontrol_rolunu_de_dusurur(rol):
    """`close[t-30]`in tamlik araligi `[t-30 .. t]`: kirilim penceresinin DISINDA, aralik icinde
    kalan bir bosluk da kontrolu dusurur (yalnizca `kapanis_30_once` hesaplanamaz)."""
    eksik = _barsiz(_duz(DB2, B2), T2 - 20 * H4)
    with pytest.raises(pozisyon.SinyalPenceresiTamDegil):
        _karar("H2", eksik, FUND2, DB2, B2, T2, **kontrol("H2", rol))


@pytest.mark.parametrize("rol", KONTROL_ROLLERI)
def test_h2_funding_sinyal_penceresindeki_bosluk_iki_kontrol_rolunu_de_dusurur(rol):
    """H2'nin 24 saatlik funding ortalamasi da CAPASIZ bir sinyal penceresidir (on-kayit §6 rev.12)."""
    fr = FUND2.loc[FUND2["odeme_zamani"] != T("2025-03-09 16:00")].reset_index(drop=True)
    with pytest.raises(pozisyon.SinyalPenceresiTamDegil):
        _karar("H2", _duz(DB2, B2), fr, DB2, B2, T2, **kontrol("H2", rol))


@pytest.mark.parametrize("k,hesaplanir", [(3, True), (6, True), (12, False)])
def test_h2_izgaradaki_k_capasiz_pencerenin_uzunlugunu_belirler(k, hesaplanir):
    """Yapilandirma kontrol barinda da gereklidir (on-kayit §5 rev.11: "Olay ya da kontrol ureten
    her cagri, hipotezi ve yapilandirmayi birlikte alir"): `k` kirilim penceresinin uzunlugudur.

    Sinir durumu dogrudan capasiz pencere kurucusunda olculur, cunku kapi yolunda t'ye 30 gunden
    yakin her bosluk uygunluk penceresini de dusururdu ve iki gerekce ayrisamazdi. Donem basi
    t-7'de: k = 3 ve k = 6 pencereleri (`[t-k .. t-1]`) donem icinde, k = 12 donem basini asar."""
    db = T("2025-03-01")
    m = _duz(db, T("2025-03-20"))
    t = db + 7 * H4
    degerler = sinyal.capasiz_pencere_degerleri(
        "H2", yapilandirma("H2", k=k), t, mumlar_4h=m, gunluk=None, funding=_fund(db, T("2025-03-20")),
        kume_baslangic=T("2025-01-01"), kume_bitis=T("2025-08-31 23:59:59"), donem_baslangic=db)
    assert math.isfinite(degerler["kirilim_dip"]) is hesaplanir


# --- 3. H1: dip ve iki hacim penceresi --------------------------------------------------------

DB1, B1 = T("2025-01-01"), T("2025-06-30 20:00")
T1 = T("2025-03-10 16:00")
FUND1 = _fund(DB1, B1 + H4)


@pytest.mark.parametrize("rol", KONTROL_ROLLERI)
def test_h1_duz_seride_kontrol_olusur_tepe_aranmadigi_icin(rol):
    """Olumlu kontrol: pump yok, tepe yok; capasiz pencereler hesaplanabildigi icin kontrol olur."""
    assert _karar("H1", _duz(DB1, B1), FUND1, DB1, B1, T1, **kontrol("H1", rol)).rol == rol


@pytest.mark.parametrize("rol", KONTROL_ROLLERI)
def test_h1_dip_penceresindeki_bosluk_kontrolu_dusurur(rol):
    """`min(low[t-6..t-1])`: t'nin kendi gunundeki eksik bar dip penceresini dusurur."""
    with pytest.raises(pozisyon.SinyalPenceresiTamDegil):
        _karar("H1", _barsiz(_duz(DB1, B1), T1 - H4), FUND1, DB1, B1, T1, **kontrol("H1", rol))


@pytest.mark.parametrize("rol", KONTROL_ROLLERI)
def test_h1_180_barlik_hacim_penceresindeki_uzak_bosluk_kontrolu_dusurur(rol):
    """180 barlik medyanin ic pencereleriyle birlikte `[t-184 .. t]`: dip penceresinin cok
    disinda, 100 bar geride kalan bir bosluk da kontrolu dusurur."""
    with pytest.raises(pozisyon.SinyalPenceresiTamDegil):
        _karar("H1", _barsiz(_duz(DB1, B1), T1 - 100 * H4), FUND1, DB1, B1, T1, **kontrol("H1", rol))


@pytest.mark.parametrize("rol", KONTROL_ROLLERI)
def test_h1_donem_basi_capasiz_pencereyi_dusurur_kontrol_havuzuna_girmez(rol):
    """On-kayitin gerekcesi: "kontrol havuzuna bir olayin hicbir zaman olusamayacagi barlar (donem
    baslari, bosluk sonrasi barlar) girer ve iki grup veri kalitesi bakimindan sistematik olarak
    ayrisir." 185 bardan az gecmisi olan bir barda H1'in hacim penceresi donem basini asar.

    Sinir durumu: ayni donemde 185 bardan SONRASI gecer, oncesi dusmez degil -- duser."""
    db = T("2025-01-01")
    erken = db + 100 * H4          # hacim penceresi (185 bar) donem basini asar
    gec = db + 200 * H4            # asmaz
    m = _duz(db, B1)
    with pytest.raises(pozisyon.SinyalPenceresiTamDegil):
        _karar("H1", m, _fund(db, B1 + H4), db, B1, erken, **kontrol("H1", rol))
    assert _karar("H1", m, _fund(db, B1 + H4), db, B1, gec, **kontrol("H1", rol)).rol == rol


# --- 4. H3: iki hacim penceresi, SMA50, dusus trendi orani ------------------------------------

DB3, B3 = T("2024-09-01"), T("2025-06-30 20:00")
T3 = T("2025-03-10")
FUND3 = _fund(DB3, B3 + H4)


@pytest.mark.parametrize("rol", KONTROL_ROLLERI)
def test_h3_duz_seride_kontrol_olusur_olumlu_kontrol(rol):
    assert _karar("H3", _duz(DB3, B3), FUND3, DB3, B3, T3, **kontrol("H3", rol)).rol == rol


@pytest.mark.parametrize("rol", KONTROL_ROLLERI)
@pytest.mark.parametrize("gun_ofseti", (1, 20, 40, 100))
def test_h3_eksik_gun_capasiz_pencereyi_dusurur(rol, gun_ofseti):
    """1d seride bir gunun alti 4h barindan biri eksikse o gun olusmaz (on-kayit §2 "1 gunluk
    barlar") ve o gunu iceren capasiz pencere hesaplanamaz: 1 gun geride `[t-29..t]` hacim
    penceresi ve SMA50, 40 gun geride SMA50 ve `[t-30..t]`, 100 gun geride `[t-120..t-31]`."""
    eksik_gun = T3 - pd.Timedelta(days=gun_ofseti)
    with pytest.raises(pozisyon.SinyalPenceresiTamDegil):
        _karar("H3", _barsiz(_duz(DB3, B3), eksik_gun + 2 * H4), FUND3, DB3, B3, T3,
               **kontrol("H3", rol))


@pytest.mark.parametrize("rol", KONTROL_ROLLERI)
def test_h3_donem_basi_uzak_hacim_penceresini_dusurur(rol):
    """`[t-120 .. t-31]` penceresi donem basini asarsa kontrol olusmaz; 121 gunden sonrasi gecer."""
    db = T("2025-01-01")
    m, f = _duz(db, B3), _fund(db, B3 + H4)
    with pytest.raises(pozisyon.SinyalPenceresiTamDegil):
        _karar("H3", m, f, db, B3, db + pd.Timedelta(days=100), **kontrol("H3", rol))
    assert _karar("H3", m, f, db, B3, db + pd.Timedelta(days=130), **kontrol("H3", rol)).rol == rol


# --- 5. Olay tarafi degismedi -----------------------------------------------------------------


def test_olay_rolunde_butun_degerler_hala_aranir():
    """Capasiz pencere sarti kontrol roluyle sinirlidir; olay rolu butun degerleri (tepe dahil)
    hesaplar ve §5'teki kosullari arar."""
    y = yapilandirma("H2")
    assert set(sinyal.deger_adlari("H2")) > set(sinyal.capasiz_pencere_adlari("H2"))
    with pytest.raises(pozisyon.SinyalKosuluSaglanmadi):
        _karar("H2", _duz(DB2, B2), FUND2, DB2, B2, T2, yapilandirma=y, rol="olay", capa=None)
