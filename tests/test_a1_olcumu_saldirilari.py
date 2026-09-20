"""analysis/00_veri_denetimi/a1_olcumu.py icin sizinti/saldiri testleri.

Bu betik bir olcum betigi (CLAUDE.md §1: "getiri hesaplamaz"), ancak saf
fonksiyonlari (`sembol_olc`, `konum`, `oran_karsilastir`) referans/tolerans
sinirlarini yanlis uygularsa yanlis "veri butunlugu" sonucuna varabilir; bu da
sonraki hipotez tasarimini yanlis yonlendirir. Testler bu fonksiyonlari
dogrudan saldiriya ugratir; a1_olcumu.py disk/ag erismez, dogrudan import
edilebilir (betik degil paket oldugu icin importlib.util kullanilir).

Not: `oran_karsilastir` ve onu acan bayrak D-B1 karariyla koddan kaldirildi.
O fonksiyonun testleri de bu dosyadan silindi; oran degeri yolunun
bulunmadigini tests/test_a1_deger_yolu_yok.py sabitler.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pytest

KOK = Path(__file__).resolve().parents[1]
A1_YOLU = KOK / "analysis" / "00_veri_denetimi" / "a1_olcumu.py"

sys.path.insert(0, str(KOK))


def _a1_yukle():
    """a1_olcumu.py'yi paket olmadan dogrudan modul olarak yukler (saf import, ag yok)."""
    spec = importlib.util.spec_from_file_location("a1_olcumu_test_hedefi", A1_YOLU)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


a1 = _a1_yukle()
from data import pencere as pencere_modulu  # noqa: E402
from data import funding as funding_modulu  # noqa: E402

TOL = funding_modulu.ODEME_TOLERANSI


@dataclass(frozen=True)
class SahteDonem:
    """data.donem.Donem'in testler icin minimal kopyasi (yalniz baslangic/bitis kullanilir)."""

    baslangic: pd.Timestamp
    bitis: pd.Timestamp
    bar_sayisi: int = 1
    gercek_bar_sayisi: int = 1


def _fund(zamanlar, oranlar=None, aralik=8.0):
    n = len(zamanlar)
    if oranlar is None:
        oranlar = [0.0001] * n
    return pd.DataFrame({
        "odeme_zamani": pd.to_datetime(zamanlar, utc=True),
        "oran": oranlar,
        "oran_8h": oranlar,
        "aralik_saat": [aralik] * n,
    })


# ---------------------------------------------------------------------------
# konum(): 1 dakika tolerans siniri
# ---------------------------------------------------------------------------

def test_konum_tam_acilista_teslimsiz():
    """konum(), acilis anindaki kaydi 'son_bar_acilisi' olarak etiketlemeli (ODEME_TOLERANSI, data/pencere.py)."""
    acilis = pd.Timestamp("2025-01-01", tz="UTC")
    kapanis = acilis + pencere_modulu.adim("4h")
    assert a1.konum(acilis, acilis, kapanis, None) == "son_bar_acilisi"


def test_konum_acilis_tolerans_icinde_59_saniye():
    """Acilistan 59 sn sonrasi hala tolerans icinde sayilmali (1 dk sinir, data/pencere.py ODEME_TOLERANSI)."""
    acilis = pd.Timestamp("2025-01-01", tz="UTC")
    kapanis = acilis + pencere_modulu.adim("4h")
    z = acilis + pd.Timedelta(seconds=59)
    assert a1.konum(z, acilis, kapanis, None) == "son_bar_acilisi"


def test_konum_acilis_tolerans_disinda_61_saniye():
    """Acilistan 61 sn sonrasi tolerans disina cikmali ve 'son_bar_ici' donmeli."""
    acilis = pd.Timestamp("2025-01-01", tz="UTC")
    kapanis = acilis + pencere_modulu.adim("4h")
    z = acilis + pd.Timedelta(seconds=61)
    assert a1.konum(z, acilis, kapanis, None) == "son_bar_ici"


def test_konum_kapaniste_tam():
    """Kapanis anindaki kayit 'son_bar_kapanisi' olmali."""
    acilis = pd.Timestamp("2025-01-01", tz="UTC")
    kapanis = acilis + pencere_modulu.adim("4h")
    assert a1.konum(kapanis, acilis, kapanis, None) == "son_bar_kapanisi"


def test_konum_kapanistan_hemen_sonra():
    """Kapanistan 61 sn sonraki kayit 'son_bardan_sonra' olmali; kapanis tolerensina sizmamali."""
    acilis = pd.Timestamp("2025-01-01", tz="UTC")
    kapanis = acilis + pencere_modulu.adim("4h")
    z = kapanis + pd.Timedelta(seconds=61)
    assert a1.konum(z, acilis, kapanis, None) == "son_bardan_sonra"


def test_konum_teslim_none_ile_teslim_etiketi_eklenmez():
    """teslim=None ise donen deger '|teslim' iceren bir sonek almamali (deliveryDate'i olmayan semboller icin)."""
    acilis = pd.Timestamp("2025-01-01", tz="UTC")
    kapanis = acilis + pencere_modulu.adim("4h")
    sonuc = a1.konum(acilis, acilis, kapanis, None)
    assert "teslim" not in sonuc


def test_konum_teslim_nat_ile_teslim_etiketi_eklenmez():
    """teslim=pd.NaT durumunda da 'teslim_aninda/once/sonra' etiketi eklenmemeli (pd.isna kontrolu)."""
    acilis = pd.Timestamp("2025-01-01", tz="UTC")
    kapanis = acilis + pencere_modulu.adim("4h")
    sonuc = a1.konum(acilis, acilis, kapanis, pd.NaT)
    assert "teslim" not in sonuc


def test_konum_teslim_aninda_tam_esit():
    """Kayit zamani teslim anina esitse 'teslim_aninda' etiketi eklenmeli."""
    acilis = pd.Timestamp("2025-01-01", tz="UTC")
    kapanis = acilis + pencere_modulu.adim("4h")
    teslim = acilis + pd.Timedelta(hours=1)
    z = teslim
    assert a1.konum(z, acilis, kapanis, teslim).endswith("|teslim_aninda")


def test_konum_teslim_tolerans_siniri_61_saniye_sonra():
    """Teslimden 61 sn sonraki kayit 'teslimden_sonra' etiketlenmeli, 'teslim_aninda' degil."""
    acilis = pd.Timestamp("2025-01-01", tz="UTC")
    kapanis = acilis + pencere_modulu.adim("4h")
    teslim = acilis + pd.Timedelta(hours=1)
    z = teslim + pd.Timedelta(seconds=61)
    assert a1.konum(z, acilis, kapanis, teslim).endswith("|teslimden_sonra")


def test_konum_acilis_ile_teslim_ayni_anda_cakismaz():
    """Kayit hem acilis hem teslim anindaysa iki etiket de dogru birlesmeli (cakisma testi)."""
    acilis = pd.Timestamp("2025-01-01", tz="UTC")
    kapanis = acilis + pencere_modulu.adim("4h")
    sonuc = a1.konum(acilis, acilis, kapanis, acilis)
    assert sonuc == "son_bar_acilisi|teslim_aninda"


# ---------------------------------------------------------------------------
# sembol_olc(): cikis anina denklik, donem sinirlari, bos veri
# ---------------------------------------------------------------------------

def test_sembol_olc_bos_funding_ile_bos_liste_doner():
    """Bos funding cercevesi verilirse sembol_olc patlamamali, bos liste donmeli."""
    donem = SahteDonem(pd.Timestamp("2025-01-01", tz="UTC"), pd.Timestamp("2025-01-05", tz="UTC"))
    sonuc = a1.sembol_olc("TEST", pd.Timestamp("2025-01-05", tz="UTC"), donem, _fund([]))
    assert sonuc == []


def test_sembol_olc_teslimden_once_gelen_kayit_disarida_kalir():
    """teslim'den ONCE gelen bir odeme 'sonra' filtresine (z > teslim + tol) takilip
    listeye girmemeli; girerse gelecege degil gecmise ait bir kaydi 'uzlasma sonrasi' sayar."""
    donem_bitis = pd.Timestamp("2025-01-05", tz="UTC")
    donem = SahteDonem(pd.Timestamp("2025-01-01", tz="UTC"), donem_bitis)
    teslim = donem_bitis + pd.Timedelta(hours=2)
    oncesi = teslim - pd.Timedelta(hours=1)
    fund = _fund([oncesi])
    sonuc = a1.sembol_olc("TEST", teslim, donem, fund)
    assert sonuc == []


def test_sembol_olc_cikis_anina_tam_denk_gelen_kayit_isaretlenir():
    """odeme_zamani cikis anina (donem.bitis + adim) tam denk geliyorsa cikis_anina_denk True olmali."""
    donem_bitis = pd.Timestamp("2025-01-05", tz="UTC")
    donem = SahteDonem(pd.Timestamp("2025-01-01", tz="UTC"), donem_bitis)
    cikis_ani = donem_bitis + pencere_modulu.adim("4h")
    teslim = donem_bitis  # teslim, cikistan once
    fund = _fund([cikis_ani])
    sonuc = a1.sembol_olc("TEST", teslim, donem, fund)
    assert len(sonuc) == 1
    assert sonuc[0]["cikis_anina_denk"] is True


def test_sembol_olc_cikis_anindan_uzak_kayit_denk_sayilmamali():
    """cikis_anina_denk, uzlasma sonrasi ama cikis anindan uzak (1 saat once) bir
    kayda True dememeli. NOT: cikis_ani + tol SINIRINDAN SONRASI zaten
    `_donem_icinde` tarafindan donem disi sayilip elenir (ust sinir tam
    cikis_ani + ODEME_TOLERANSI); bu yuzden tolerans disini "once" tarafinda
    sinamak gerekir, "sonra" tarafinda deneme donem sinirina takilir."""
    donem_bitis = pd.Timestamp("2025-01-05", tz="UTC")
    donem = SahteDonem(pd.Timestamp("2025-01-01", tz="UTC"), donem_bitis)
    cikis_ani = donem_bitis + pencere_modulu.adim("4h")
    teslim = donem_bitis - pd.Timedelta(hours=2)
    z = cikis_ani - pd.Timedelta(hours=1)
    fund = _fund([z])
    sonuc = a1.sembol_olc("TEST", teslim, donem, fund)
    assert len(sonuc) == 1
    assert sonuc[0]["cikis_anina_denk"] is False


def test_sembol_olc_donem_icinde_ile_tutarli_ust_sinir():
    """sembol_olc'nin kullandigi `icinde` maskesi funding._donem_icinde ile ayni ust
    sinira (donem.bitis + adim + ODEME_TOLERANSI, HARIC) uymali. Bu sinirin hemen
    disindaki (>= ust) bir kayit 'donem icinde' sayilmamali (dolgu/uzlasma sonrasi
    donem disi kaydi donem sinirina sizdirmama testi, on-kayit §2 rev.7)."""
    donem_bitis = pd.Timestamp("2025-01-05", tz="UTC")
    donem = SahteDonem(pd.Timestamp("2025-01-01", tz="UTC"), donem_bitis)
    ust_sinir = donem_bitis + pencere_modulu.adim("4h") + TOL  # HARIC sinir
    teslim = donem_bitis - pd.Timedelta(hours=4)
    fund = _fund([ust_sinir])  # tam sinirda, HARIC oldugu icin disarida kalmali
    sonuc = a1.sembol_olc("TEST", teslim, donem, fund)
    assert sonuc == []


def test_sembol_olc_1ms_kayik_calc_time_yine_de_yakalanir():
    """Odeme zamani cikis anindan 1 ms once ise (borsa saat kaymasi) 'cikis_anina_denk'
    hala True olmali (1 dk toleransin icinde kalir)."""
    donem_bitis = pd.Timestamp("2025-01-05", tz="UTC")
    donem = SahteDonem(pd.Timestamp("2025-01-01", tz="UTC"), donem_bitis)
    cikis_ani = donem_bitis + pencere_modulu.adim("4h")
    teslim = donem_bitis
    z = cikis_ani - pd.Timedelta(milliseconds=1)
    fund = _fund([z])
    sonuc = a1.sembol_olc("TEST", teslim, donem, fund)
    assert len(sonuc) == 1
    assert sonuc[0]["cikis_anina_denk"] is True
