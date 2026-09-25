"""On-kayit §4 rev.8 "Zaman toleransi": iki an arasindaki fark 1 dakikadan KESIN
olarak kucukse ayni an; tam 1 dakika ayni an degildir. Aga cikmaz.

Her kullanim yerinde uc kenar denenir: tam 1 dk, 1 dk - 1 ns, 1 dk + 1 ns.
Pozisyon funding'inin giris/cikis kenarlari tests/test_rev8_funding.py'de.
"""

from __future__ import annotations

import importlib.util
import sys

import numpy as np
import pandas as pd
import pytest

import config
from donem_yardimcisi import TOPLAM_DONEM_B, TOPLAM_DONEM_BASI  # noqa: E402
from data import funding, pencere
from data.donem import Donem

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
DK = pd.Timedelta(minutes=1)
NS = pd.Timedelta(1, "ns")
KENARLAR = [(DK - NS, True), (DK, False), (DK + NS, False)]  # (fark, ayni_an_mi)

DIZIN = config.ANALIZ_DIZINI / "00_veri_denetimi"
sys.path.insert(0, str(DIZIN))


def _yukle(ad, dosya):
    spec = importlib.util.spec_from_file_location(ad, DIZIN / dosya)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# --- Tek tanim ve turevleri ---------------------------------------------------------


@pytest.mark.parametrize("fark,ayni", KENARLAR)
def test_ayni_an_ve_iliskiler(fark, ayni):
    a = T("2025-01-01 08:00")
    for b in (a + fark, a - fark):
        assert pencere.ayni_an(a, b) is ayni
    assert pencere.sonra(a + fark, a) is (not ayni)
    assert pencere.once(a - fark, a) is (not ayni)
    assert pencere.ayni_ya_da_once(a + fark, a) is ayni
    assert pencere.ayni_ya_da_sonra(a - fark, a) is ayni
    # iliskiler birbirinin tumleyeni
    assert pencere.ayni_ya_da_once(a + fark, a) is not pencere.sonra(a + fark, a)
    assert pencere.ayni_ya_da_sonra(a - fark, a) is not pencere.once(a - fark, a)


@pytest.mark.parametrize("fark,ayni", KENARLAR)
def test_kenarlar_iliskilerle_ayni(fark, ayni):
    x = T("2025-01-01 08:00")
    an = x + fark
    assert (an < pencere.ayni_an_sonu(x)) is pencere.ayni_ya_da_once(an, x)
    assert (an >= pencere.ayni_an_sonu(x)) is pencere.sonra(an, x)
    an = x - fark
    assert (an > pencere.ayni_an_basi(x)) is pencere.ayni_ya_da_sonra(an, x)
    assert (an <= pencere.ayni_an_basi(x)) is pencere.once(an, x)


def test_dizilerde_numpy_bool():
    x = T("2025-01-01 08:00")
    z = pd.DatetimeIndex([x + DK - NS, x + DK, x + DK + NS])
    assert pencere.ayni_an(z, x).tolist() == [True, False, False]
    assert isinstance(pencere.sonra(z, x), np.ndarray)


# --- funding: donem penceresi (alt ve ust uc) ----------------------------------------

D = Donem(T("2025-01-01 00:00"), T("2025-01-10 08:00"), 55, 55)


@pytest.mark.parametrize("fark,ayni", KENARLAR)
def test_donem_icinde_alt_uc(fark, ayni):
    """Rev.7'de donem basindan tam 1 dk onceki kayit dahildi; rev.8'de degil."""
    z = pd.DatetimeIndex([D.baslangic - fark])
    assert bool(funding._donem_icinde(z, D, config.BAR_4H)[0]) is ayni
    # donem oncesi sayilan kayit ile donem ici sayilan kayit ayrik ve tam
    kalan = funding.donem_sonrasi_kayitlari_at(
        pd.DataFrame({"odeme_zamani": z, "aralik_saat": [8]}), [D], config.BAR_4H)
    assert len(kalan) == 1


# --- funding: ardisik bosluk kurali -------------------------------------------------


@pytest.mark.parametrize("fark,ayni", KENARLAR)
def test_bosluk_kurali_kenari(fark, ayni):
    """Sonraki odeme, onceki + araligin buyugunden tam 1 dk sonra geliyorsa eksik;
    1 dk - 1 ns sonra geliyorsa ayni an, tam.

    Rev.10 uygulamasi: H2 penceresinin zinciri artik tek tamlik kodundan
    (`funding.sinyal_penceresi_ayrintisi` -> `funding_tamlik_ayrintisi`); eski ic fonksiyon
    `_odemeler_tam_mi` kaldirildi. Ayni kenar ayni ciftle denenir: capa pencere basinda
    (00:00), sonraki kayit 08:00 + fark (ilk ciftte taban pencere basi)."""
    z = pd.DatetimeIndex([T("2025-01-02 00:00"), T("2025-01-02 08:00") + fark])
    f = pd.DataFrame({"odeme_zamani": z, "aralik_saat": [8, 8]})
    a = funding.sinyal_penceresi_ayrintisi(f, [T("2025-01-02 20:00")], config.BAR_4H, saat=24, kume_baslangic=None,
                                           kume_bitis=None, donem_baslangic=TOPLAM_DONEM_BASI).iloc[0]
    assert bool(a["zincir_tam"]) is ayni


# --- funding_ortalamasi: pencere kenarlari ------------------------------------------


def _fund8(zamanlar):
    z = pd.DatetimeIndex(zamanlar)
    return pd.DataFrame({"odeme_zamani": z, "aralik_saat": 8.0, "oran": 1e-4, "oran_8h": 1e-4})


@pytest.mark.parametrize("fark,ayni", KENARLAR)
def test_funding_ortalamasi_kapanis_kenari(fark, ayni):
    """Rev.10 (on-kayit §4 "Funding sinyal penceresinin tamligi"): pencere sonuna denk gelen kayit
    ortalamaya GIRER, karsilastirma tolerans payiyla. Kapanistan 1 dk - 1 ns sonra gelen kayit
    kapanisla ayni an, girer; tam 1 dk (ve sonrasi) kapanistan sonradir, okunmaz.

    Rev.10 oncesi bu test tersini sabitliyordu (kapanisla ayni an sayilan odeme alinmaz, pencere
    `[bas, kapanis)`); Rev.10 pencereyi `(bas, kapanis]` yapti."""
    t = T("2025-01-03 04:00")  # kapanis 08:00, pencere (2025-01-02 08:00, kapanis]
    kapanis = t + pd.Timedelta(hours=4)
    fr = _fund8([T("2025-01-02 00:00"), T("2025-01-02 08:00"), T("2025-01-02 16:00"),
                 T("2025-01-03 00:00"), kapanis + fark])
    fr.loc[fr.index[-1], "oran_8h"] = 9e-4
    deger = funding.funding_ortalamasi(fr, t, config.BAR_4H, saat=24, kume_baslangic=None, kume_bitis=None,
                                       donem_baslangic=TOPLAM_DONEM_BASI)
    assert deger == pytest.approx((1e-4 + 1e-4 + 9e-4) / 3 if ayni else 1e-4)


# --- Kume olcutu --------------------------------------------------------------------


@pytest.mark.parametrize("fark,ayni", KENARLAR)
def test_kume_olcutu_kenari(fark, ayni):
    """Cikis ani ile ayni sayilan son an kume sonunu asmamali."""
    kume_son = T("2025-08-31 23:59:59")
    an = kume_son - fark + NS
    # an ile ayni sayilan son an = an + 1 dk - 1 ns = kume_son - fark + 1 dk
    assert pencere._cikis_odemesi_kume_disinda(an, kume_son) is (fark < DK)


# --- Analiz betikleri -------------------------------------------------------------------


@pytest.mark.parametrize("fark,ayni", KENARLAR)
def test_calistir_gecikme_esigi(fark, ayni):
    calistir = _yukle("_tol_calistir", "calistir.py")
    saat = (pd.Timedelta(hours=config.DENETIM_ILK_GECIKME_SAAT) + fark) / pd.Timedelta(hours=1)
    assert bool(calistir._gecikme_esik_icinde(pd.Series([saat]))[0]) is ayni


@pytest.mark.parametrize("fark,ayni", KENARLAR)
def test_a1_konum_kenari(fark, ayni):
    a1 = _yukle("_tol_a1", "a1_olcumu.py")
    acilis, kapanis = T("2025-01-10 08:00"), T("2025-01-10 12:00")
    assert (a1.konum(acilis + fark, acilis, kapanis, None) == "son_bar_acilisi") is ayni
    assert (a1.konum(kapanis - fark, acilis, kapanis, None) == "son_bar_kapanisi") is ayni
