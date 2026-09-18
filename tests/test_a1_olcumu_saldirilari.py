"""analysis/00_veri_denetimi/a1_olcumu.py icin sizinti/saldiri testleri.

Bu betik bir olcum betigi (CLAUDE.md §1: "getiri hesaplamaz"), ancak saf
fonksiyonlari (`sembol_olc`, `konum`, `oran_karsilastir`) referans/tolerans
sinirlarini yanlis uygularsa yanlis "veri butunlugu" sonucuna varabilir; bu da
sonraki hipotez tasarimini yanlis yonlendirir. Testler bu fonksiyonlari
dogrudan saldiriya ugratir; a1_olcumu.py disk/ag erismez, dogrudan import
edilebilir (betik degil paket oldugu icin importlib.util kullanilir).
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
# oran_karsilastir(): referans penceresi, medyan, bolme, tekrar
# ---------------------------------------------------------------------------

def test_referans_son_30_ile_sinirli_31inci_eski_kayit_medyana_girmemeli():
    """PREREGISTRATION rev.7: referans yalniz sembolun uzlasma-oncesi son REFERANS_KAYIT
    kaydiyla sinirli olmali; daha eski (31.) bir kayit medyani etkilerse referans
    penceresi sinirsizca gecmise uzuyor demektir (gizli bir 'daha fazla veri kullan' sizintisi)."""
    zamanlar = pd.date_range("2025-01-01", periods=31, freq="8h", tz="UTC")
    # ilk (en eski) kayit disaridaki cok buyuk bir oran: medyani domine edecek sekilde tasarlandi
    oranlar = [10.0] + [0.0001] * 30
    referans = _fund(zamanlar, oranlar)
    incelenen = _fund([zamanlar[-1] + pd.Timedelta(hours=8)], [0.0002])
    sonuc = a1.oran_karsilastir(incelenen, referans)
    # son 30 kayit disinda kalan 10.0 medyana girmemeli
    assert sonuc["referans_medyan_abs_oran"].iloc[0] == pytest.approx(0.0001)
    assert sonuc["referans_kayit"].iloc[0] == 30


def test_referans_bos_ise_medyan_nan_ve_hata_yok():
    """Referans tamamen bossa (ilk uzlasan sembol vb.) fonksiyon patlamamali, medyan NaN donmeli."""
    incelenen = _fund(["2025-01-01"], [0.0001])
    bos_referans = _fund([])
    sonuc = a1.oran_karsilastir(incelenen, bos_referans)
    assert pd.isna(sonuc["referans_medyan_abs_oran"].iloc[0])
    assert sonuc["referans_kayit"].iloc[0] == 0


def test_referans_medyan_8h_sifirsa_bolme_infinite_degil_nan():
    """Medyan 8h sifirsa (tum referans oranlari 0) abs_oran_8h_medyana_orani NaN olmali,
    0/0 -> ZeroDivisionError ya da sessiz inf sizdirmamali."""
    zamanlar = pd.date_range("2025-01-01", periods=5, freq="8h", tz="UTC")
    referans = _fund(zamanlar, [0.0] * 5)
    incelenen = _fund([zamanlar[-1] + pd.Timedelta(hours=8)], [0.0003])
    sonuc = a1.oran_karsilastir(incelenen, referans)
    assert pd.isna(sonuc["abs_oran_8h_medyana_orani"].iloc[0])


def test_sifir_oran_isareti_dogru_etiketlenir():
    """oran==0 olan kayit 'isaret' sutununda 'sifir' olmali, 'pozitif' ya da 'negatif' olmamali."""
    incelenen = _fund(["2025-01-01"], [0.0])
    referans = _fund(pd.date_range("2024-12-01", periods=10, freq="8h", tz="UTC"))
    sonuc = a1.oran_karsilastir(incelenen, referans)
    assert sonuc["isaret"].iloc[0] == "sifir"


def test_incelenen_kayit_referansa_sizmamali():
    """Incelenen kaydin kendisi referans kumesine dahil edilmemeli; aksi halde kayit
    kendi medyanini hesaplarken kendisini de sayar (dairesel referans / sizinti)."""
    zamanlar = pd.date_range("2025-01-01", periods=5, freq="8h", tz="UTC")
    referans = _fund(zamanlar, [0.0001] * 5)
    # incelenen kayit referanstaki son kayitla AYNI zamanda ama cok farkli bir oranla verilirse
    # (yani caller yanlislikla incelenen kaydi da referansa katmis olsaydi) medyan degismemeli.
    incelenen = _fund([zamanlar[-1]], [9.0])
    sonuc = a1.oran_karsilastir(incelenen, referans)
    assert sonuc["referans_medyan_abs_oran"].iloc[0] == pytest.approx(0.0001)


def test_referans_30_kayit_sabitse_isaretlenir():
    """Referansin son 30 kaydi tamamen ayni degerse (yapay/dolgu funding suphesi)
    referans_30_kayit_sabit True olmali."""
    zamanlar = pd.date_range("2025-01-01", periods=30, freq="8h", tz="UTC")
    referans = _fund(zamanlar, [0.00005] * 30)
    incelenen = _fund([zamanlar[-1] + pd.Timedelta(hours=8)], [0.0001])
    sonuc = a1.oran_karsilastir(incelenen, referans)
    assert bool(sonuc["referans_30_kayit_sabit"].iloc[0]) is True


def test_incelenenler_icinde_tekrar_dogru_isaretlenir():
    """Incelenen kayitlar arasinda ayni oran degeri tekrar ediyorsa 'incelenenler_icinde_tekrar' True olmali."""
    incelenen = _fund(pd.date_range("2025-01-01", periods=3, freq="8h", tz="UTC"), [0.0001, 0.0002, 0.0001])
    referans = _fund(pd.date_range("2024-12-01", periods=10, freq="8h", tz="UTC"))
    sonuc = a1.oran_karsilastir(incelenen, referans)
    assert sonuc["incelenenler_icinde_tekrar"].tolist() == [True, False, True]


def test_referans_son_oranla_ayni_dogru_karsilastirir():
    """referans_son_oranla_ayni, incelenen oranin referansin SON kaydiyla (30. degil, en sonuncuyla) esit olup olmadigini gostermeli."""
    zamanlar = pd.date_range("2025-01-01", periods=5, freq="8h", tz="UTC")
    referans = _fund(zamanlar, [0.0001, 0.0002, 0.0003, 0.0004, 0.0009])
    incelenen = _fund([zamanlar[-1] + pd.Timedelta(hours=8)], [0.0009])
    sonuc = a1.oran_karsilastir(incelenen, referans)
    assert bool(sonuc["referans_son_oranla_ayni"].iloc[0]) is True
    assert sonuc["referans_son_oran"].iloc[0] == pytest.approx(0.0009)


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


# ---------------------------------------------------------------------------
# Ters/karisik sira ve gelecek tarihli bar saldirisi (CLAUDE.md §3.6 geleceğe bakış)
# ---------------------------------------------------------------------------

def test_oran_karsilastir_referans_sirasi_ters_verilirse_medyan_degismez_ama_son_ref_degisir():
    """referans DataFrame'i zaman sirali degil de ters sirada gelirse, fonksiyon
    ic sirayi varsayar (tail/iloc[-1]); bu durumda referans_son_oran yanlis kayda
    isaret edebilir. Cagiran (main) fund'i zaman sirali kullaniyor; burada
    fonksiyonun kendisinin sira varsayimina baglimliligini belgeliyoruz."""
    zamanlar = pd.date_range("2025-01-01", periods=5, freq="8h", tz="UTC")
    referans_dogru_sira = _fund(zamanlar, [0.0001, 0.0002, 0.0003, 0.0004, 0.0009])
    referans_ters_sira = referans_dogru_sira.iloc[::-1].reset_index(drop=True)
    incelenen = _fund([zamanlar[-1] + pd.Timedelta(hours=8)], [0.0009])

    sonuc_dogru = a1.oran_karsilastir(incelenen, referans_dogru_sira)
    sonuc_ters = a1.oran_karsilastir(incelenen, referans_ters_sira)

    # Fonksiyon zaman sirasi varsayimina dayandigi icin ters sirada referans_son_oran
    # farkli (yanlis) bir kayda isaret eder -- bu, cagiranin (main) fund'i her zaman
    # zaman sirali tutmasina baglidir; burada bu kirilgan varsayimi belgeliyoruz.
    assert sonuc_dogru["referans_son_oran"].iloc[0] == pytest.approx(0.0009)
    assert sonuc_ters["referans_son_oran"].iloc[0] == pytest.approx(0.0001)
