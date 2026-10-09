"""Rev.11 uygulamasi madde 2: sinyal pencerelerinin sinirlari (on-kayit §5 "Pencere sinirlari",
"Pencere sinirlarinin tamami" rev.11; §2 "Tamlik sarti").

Her pencerenin IKI UCU ayri ayri sabitlenir. Yontem: pencerenin bekledigi en eski ve en yeni
bar tek tek silinir; pencere o barlari gercekten istiyorsa deger NaN olur (§2 "Tamlik sarti").
Pencerenin DISINDA kalan komsu barlar silindiginde deger hesaplanmaya devam eder; boylece
pencerenin bir bar uzun ya da bir bar kisa olmadigi da gosterilir.

Ayrica: t-30 gununun H3'un iki hacim penceresine de girmedigi (on-kayit §5 rev.11: "Iki pencere
arasindaki t-30 gunu hicbir pencereye girmez") ve belirtilmeyen cagrinin hata verdigi.

Deger duzeyinde hicbir sinyal raporlanmaz; testler yalnizca hesaplanabilirlik ve hangi barlarin
penceredeyken degeri degistirdigini olcer. Aga cikmaz.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

import config
from data import sinyal

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
G1 = pd.Timedelta(days=1)


def _mumlar(bas, adet, adim):
    """Her bar farkli bir fiyat ve hacim tasir: pencereye giren bar degeri degistirir."""
    zaman = pd.date_range(bas, periods=adet, freq=adim)
    i = np.arange(adet, dtype=float)
    return pd.DataFrame({
        "open_time": zaman,
        "open": 100.0 + i,
        "high": 200.0 + i,
        "low": 50.0 + i,
        "close": 100.0 + i,
        "quote_volume": 1_000.0 + i,
    })


def _sil(mumlar, zamanlar):
    z = [pd.Timestamp(x) for x in (zamanlar if isinstance(zamanlar, (list, tuple)) else [zamanlar])]
    return mumlar.loc[~pd.DatetimeIndex(mumlar["open_time"]).isin(z)].reset_index(drop=True)


def _sinirlar(mumlar):
    return {"kume_baslangic": None, "donem_baslangic": pd.DatetimeIndex(mumlar["open_time"])[0]}


# --- Pencere tanimlari: (ad, cagri, en eski beklenen bar, en yeni beklenen bar) ----------------

DORT_SAATLIK = _mumlar(T("2025-01-01"), 400, "4h")
T4 = pd.DatetimeIndex(DORT_SAATLIK["open_time"])[300]

GUNLUK = _mumlar(T("2024-01-01"), 400, "D")
T1G = pd.DatetimeIndex(GUNLUK["open_time"])[300]

PENCERELER = [
    # (ad, kurucu, mumlar, t, en eski bar, en yeni bar)
    ("h1_dip", lambda m, s: sinyal.h1_dip(m, T4, **s), DORT_SAATLIK, T4, T4 - 6 * H4, T4 - H4),
    ("h1_hacim_6", lambda m, s: sinyal.h1_hacim_6(m, T4, **s), DORT_SAATLIK, T4, T4 - 5 * H4, T4),
    ("h1_hacim_medyani_180", lambda m, s: sinyal.h1_hacim_medyani_180(m, T4, **s), DORT_SAATLIK, T4,
     T4 - 184 * H4, T4),
    ("h1_tepe", lambda m, s: sinyal.h1_tepe(m, T4 - 5 * H4, T4, **s), DORT_SAATLIK, T4, T4 - 5 * H4, T4 - H4),
    ("h2_kirilim_dip_k3", lambda m, s: sinyal.h2_kirilim_dip(m, T4, 3, **s), DORT_SAATLIK, T4,
     T4 - 3 * H4, T4 - H4),
    ("h2_kirilim_dip_k12", lambda m, s: sinyal.h2_kirilim_dip(m, T4, 12, **s), DORT_SAATLIK, T4,
     T4 - 12 * H4, T4 - H4),
    ("kapanis_30_once_4h", lambda m, s: sinyal.kapanis_30_once(m, T4, config.BAR_4H, **s), DORT_SAATLIK, T4,
     T4 - 30 * H4, T4),
    ("kapanis_30_once_1d", lambda m, s: sinyal.kapanis_30_once(m, T1G, config.BAR_1D, **s), GUNLUK, T1G,
     T1G - 30 * G1, T1G),
    ("h3_hacim_medyani_30g", lambda m, s: sinyal.h3_hacim_medyani_30g(m, T1G, **s), GUNLUK, T1G,
     T1G - 29 * G1, T1G),
    ("h3_hacim_medyani_120_31", lambda m, s: sinyal.h3_hacim_medyani_120_31(m, T1G, **s), GUNLUK, T1G,
     T1G - 120 * G1, T1G - 31 * G1),
    ("h3_sma50", lambda m, s: sinyal.h3_sma50(m, T1G, **s), GUNLUK, T1G, T1G - 49 * G1, T1G),
]
KIMLIKLER = [p[0] for p in PENCERELER]


@pytest.mark.parametrize("ad,kurucu,mumlar,t,en_eski,en_yeni", PENCERELER, ids=KIMLIKLER)
def test_pencere_tam_seride_hesaplanir(ad, kurucu, mumlar, t, en_eski, en_yeni):
    assert math.isfinite(kurucu(mumlar, _sinirlar(mumlar)))


@pytest.mark.parametrize("ad,kurucu,mumlar,t,en_eski,en_yeni", PENCERELER, ids=KIMLIKLER)
def test_pencerenin_en_eski_bari_eksikse_nan(ad, kurucu, mumlar, t, en_eski, en_yeni):
    """Pencerenin ALT ucu: en eski beklenen bar silinince deger hesaplanmaz (§2 "Tamlik sarti")."""
    assert math.isnan(kurucu(_sil(mumlar, en_eski), _sinirlar(mumlar)))


@pytest.mark.parametrize("ad,kurucu,mumlar,t,en_eski,en_yeni", PENCERELER, ids=KIMLIKLER)
def test_pencerenin_en_yeni_bari_eksikse_nan(ad, kurucu, mumlar, t, en_eski, en_yeni):
    """Pencerenin UST ucu: en yeni beklenen bar silinince deger hesaplanmaz."""
    assert math.isnan(kurucu(_sil(mumlar, en_yeni), _sinirlar(mumlar)))


@pytest.mark.parametrize("ad,kurucu,mumlar,t,en_eski,en_yeni", PENCERELER, ids=KIMLIKLER)
def test_pencerenin_bir_bar_oncesi_pencerede_degil(ad, kurucu, mumlar, t, en_eski, en_yeni):
    """Pencere bir bar daha geriye uzanmiyor: en eski barin bir oncesi silinince deger durur."""
    adim = H4 if mumlar is DORT_SAATLIK else G1
    assert math.isfinite(kurucu(_sil(mumlar, en_eski - adim), _sinirlar(mumlar)))


@pytest.mark.parametrize("ad,kurucu,mumlar,t,en_eski,en_yeni", PENCERELER, ids=KIMLIKLER)
def test_t_haric_pencerelerde_t_bari_gerekmez(ad, kurucu, mumlar, t, en_eski, en_yeni):
    """t'yi icermeyen pencereler t bari silinince de hesaplanir; icerenler hesaplanmaz."""
    sonuc = kurucu(_sil(mumlar, t), _sinirlar(mumlar))
    if en_yeni == t:
        assert math.isnan(sonuc), f"{ad} t barini ICERIR; t silinince NaN olmali"
    else:
        assert math.isfinite(sonuc), f"{ad} t barini ICERMEZ; t silinince de hesaplanmali"


# --- t-30 gunu hicbir H3 hacim penceresinde degil (on-kayit §5 rev.11) --------------------------


def test_t_eksi_30_gunu_h3_hacim_pencerelerinin_ikisinde_de_yok():
    """On-kayit §5 rev.11: "Iki pencere arasindaki t-30 gunu hicbir pencereye girmez; bu, yazili
    sayilarin dogrudan sonucudur ve bilerek korunmustur." """
    s = _sinirlar(GUNLUK)
    eksik = _sil(GUNLUK, T1G - 30 * G1)
    assert math.isfinite(sinyal.h3_hacim_medyani_30g(eksik, T1G, **s))
    assert math.isfinite(sinyal.h3_hacim_medyani_120_31(eksik, T1G, **s))
    # Komsu gunler (t-29 ve t-31) ise penceredeler.
    assert math.isnan(sinyal.h3_hacim_medyani_30g(_sil(GUNLUK, T1G - 29 * G1), T1G, **s))
    assert math.isnan(sinyal.h3_hacim_medyani_120_31(_sil(GUNLUK, T1G - 31 * G1), T1G, **s))


def test_t_eksi_30_gunu_dusus_trendi_tamliginda_var():
    """`close[t-30]` penceresi kapali araliktir (`[t-30 .. t]`, 31 bar): t-30 gunu ORADA gerekir.
    Ayni gun hacim pencerelerinde gerekmez; iki kural birbirinden bagimsizdir."""
    s = _sinirlar(GUNLUK)
    assert math.isnan(sinyal.kapanis_30_once(_sil(GUNLUK, T1G - 30 * G1), T1G, config.BAR_1D, **s))


def test_kapanis_30_once_degeri_t_eksi_30_barin_kapanisi():
    """Deger, tamlik penceresinin ILK barinin kapanisidir (iki uclu oran t'den 30 adim onceyi okur)."""
    s = _sinirlar(DORT_SAATLIK)
    seri = pd.Series(DORT_SAATLIK["close"].to_numpy(dtype=float),
                     index=pd.DatetimeIndex(DORT_SAATLIK["open_time"]))
    assert sinyal.kapanis_30_once(DORT_SAATLIK, T4, config.BAR_4H, **s) == pytest.approx(seri.loc[T4 - 30 * H4])


# --- Tepe penceresinin sinirlari (on-kayit §5 H1 madde 2, rev.11) ------------------------------


def test_tepe_teyit_barinin_high_degerini_icermez():
    """Rev.11: "Teyit barinin kendi `high` degeri tepeye girmez." Teyit barinin high'ini cok
    buyuk yapmak tepeyi degistirmemeli."""
    s = _sinirlar(DORT_SAATLIK)
    pump = T4 - 5 * H4
    once = sinyal.h1_tepe(DORT_SAATLIK, pump, T4, **s)
    bozuk = DORT_SAATLIK.copy()
    bozuk.loc[pd.DatetimeIndex(bozuk["open_time"]) == T4, "high"] = 1e9
    assert sinyal.h1_tepe(bozuk, pump, T4, **s) == once


def test_tepe_pump_barini_icerir():
    s = _sinirlar(DORT_SAATLIK)
    pump = T4 - 5 * H4
    once = sinyal.h1_tepe(DORT_SAATLIK, pump, T4, **s)
    bozuk = DORT_SAATLIK.copy()
    bozuk.loc[pd.DatetimeIndex(bozuk["open_time"]) == pump, "high"] = 1e9
    assert sinyal.h1_tepe(bozuk, pump, T4, **s) == 1e9 > once


def test_tepe_en_az_bir_bar_ve_en_fazla_12_bar():
    s = _sinirlar(DORT_SAATLIK)
    assert sinyal.h1_tepe_bar_sayisi(T4 - H4, T4) == 1
    assert sinyal.h1_tepe_bar_sayisi(T4 - 12 * H4, T4) == 12
    with pytest.raises(ValueError, match="sonra olmali"):
        sinyal.h1_tepe(DORT_SAATLIK, T4, T4, **s)
    with pytest.raises(ValueError, match="en fazla"):
        sinyal.h1_tepe(DORT_SAATLIK, T4 - 13 * H4, T4, **s)
    with pytest.raises(ValueError, match="izgarasinda degil"):
        sinyal.h1_tepe(DORT_SAATLIK, T4 - 5 * H4 - pd.Timedelta(hours=1), T4, **s)


# --- Varsayilan sinir yok (on-kayit §5: "belirtilmeyen cagri hata verir") ----------------------


@pytest.mark.parametrize("eksik", ["kume_baslangic", "donem_baslangic"])
def test_sinir_verilmeyen_cagri_hata_verir(eksik):
    s = _sinirlar(DORT_SAATLIK)
    del s[eksik]
    with pytest.raises(TypeError):
        sinyal.h1_dip(DORT_SAATLIK, T4, **s)


def test_donem_baslangici_none_olamaz():
    with pytest.raises(TypeError):
        sinyal.h1_dip(DORT_SAATLIK, T4, kume_baslangic=None, donem_baslangic=None)


def test_pencere_donem_baslangicini_asamaz():
    """On-kayit §2: "Tum geriye bakis pencereleri donem baslangicini asamaz; asiyorsa deger
    hesaplanmaz." """
    assert math.isnan(sinyal.h1_dip(DORT_SAATLIK, T4, kume_baslangic=None, donem_baslangic=T4 - 5 * H4))
    assert math.isfinite(sinyal.h1_dip(DORT_SAATLIK, T4, kume_baslangic=None, donem_baslangic=T4 - 6 * H4))


def test_pencere_kume_baslangicini_asamaz():
    """On-kayit §3 "Kume siniri ve geriye bakis"."""
    assert math.isnan(sinyal.h1_dip(DORT_SAATLIK, T4, kume_baslangic=T4 - 5 * H4,
                                    donem_baslangic=pd.DatetimeIndex(DORT_SAATLIK["open_time"])[0]))


# --- Sonlu olmayan hucre (on-kayit §2 rev.11) --------------------------------------------------


@pytest.mark.parametrize("deger", [float("nan"), float("inf"), -float("inf")])
def test_penceredeki_sonsuz_ya_da_nan_hucre_degeri_nan_yapar(deger):
    s = _sinirlar(DORT_SAATLIK)
    bozuk = DORT_SAATLIK.copy()
    bozuk.loc[pd.DatetimeIndex(bozuk["open_time"]) == T4 - 3 * H4, "low"] = deger
    assert math.isnan(sinyal.h1_dip(bozuk, T4, **s))


def test_sayisal_olmayan_hucre_nan_sayilir():
    s = _sinirlar(DORT_SAATLIK)
    bozuk = DORT_SAATLIK.copy()
    bozuk["low"] = bozuk["low"].astype(object)
    bozuk.loc[pd.DatetimeIndex(bozuk["open_time"]) == T4 - 3 * H4, "low"] = "bozuk"
    assert math.isnan(sinyal.h1_dip(bozuk, T4, **s))


# --- Izgara (on-kayit §5 rev.11) ---------------------------------------------------------------


@pytest.mark.parametrize("hipotez,beklenen", [("H1", 9), ("H2", 9), ("H3", 9)])
def test_izgara_dokuz_yapilandirma(hipotez, beklenen):
    assert len(sinyal.izgara(hipotez)) == beklenen
    assert len({tuple(sorted(y.items())) for y in sinyal.izgara(hipotez)}) == beklenen


def test_izgara_degerleri_on_kayitla_ayni():
    assert config.IZGARA["H1"] == {"theta": (0.20, 0.30, 0.40), "delta": (0.08, 0.12, 0.16)}
    assert config.IZGARA["H2"] == {"phi": (0.0003, 0.0005, 0.0010), "k": (3, 6, 12)}
    assert config.IZGARA["H3"] == {"nu": (0.50, 0.65, 0.80), "tau": (0.15, 0.25, 0.35)}


@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_izgaradaki_her_yapilandirma_gecerli(hipotez):
    for y in sinyal.izgara(hipotez):
        assert sinyal.yapilandirma_dogrula(hipotez, y) == y
        assert sinyal.yapilandirma_dogrula(hipotez, dict(y)) == y


@pytest.mark.parametrize("hipotez,yapilandirma", [
    ("H1", {"theta": 0.25, "delta": 0.08}),        # izgarada olmayan theta
    ("H1", {"theta": 0.20, "delta": 0.10}),        # izgarada olmayan delta
    ("H1", {"theta": 0.2000001, "delta": 0.08}),   # yaklasik deger izgarada degil
    ("H2", {"phi": 0.0003}),                        # eksik parametre
    ("H2", {"phi": 0.0003, "k": 6, "fazla": 1}),    # fazla parametre
    ("H3", {"nu": 0.50, "tau": True}),              # bool sayi degil
    ("H2", {"phi": 0.0003, "k": "6"}),              # metin
])
def test_izgarada_olmayan_demet_hata_verir(hipotez, yapilandirma):
    with pytest.raises(sinyal.YapilandirmaHatasi):
        sinyal.yapilandirma_dogrula(hipotez, yapilandirma)


def test_kirilim_dibi_izgara_disi_k_kabul_etmez():
    s = _sinirlar(DORT_SAATLIK)
    with pytest.raises(sinyal.YapilandirmaHatasi):
        sinyal.h2_kirilim_dip(DORT_SAATLIK, T4, 4, **s)
    with pytest.raises(sinyal.YapilandirmaHatasi):
        sinyal.h2_kirilim_dip(DORT_SAATLIK, T4, True, **s)


def test_yapilandirma_kimligi_deterministik():
    assert sinyal.yapilandirma_kimligi("H2", {"phi": 0.0005, "k": 6}) == "H2:phi=0.0005,k=6"
    assert sinyal.yapilandirma_kimligi("H2", (0.0005, 6)) == "H2:phi=0.0005,k=6"


@pytest.mark.parametrize("hipotez", ["h1", "H4", "", "H1 ", 1, None])
def test_bilinmeyen_hipotez_reddedilir(hipotez):
    with pytest.raises((TypeError, ValueError)):
        sinyal.izgara(hipotez)
