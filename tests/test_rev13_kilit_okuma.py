"""Onay kosusu F2'nin kilitledigi yapilandirmayi okur (on-kayit §8 madde 5, rev.13 (k)).

On-kayit §8 madde 5 (rev.13): "Secim, onay kosusundan once `analysis/<hipotez>/KILIT.md` dosyasiyla
commit edilir. Dosyanin yolu bu on-kayitta yazili olandir ve olusturuldugu andan itibaren kilitli
dosyalar arasina girer. Dosya su alanlari tasir: hipotez; hukum (yapilandirma secildi / hipotez
kapandi) ve kapandiysa gerekcesi; secildiyse yapilandirmanin kimligi ve butun parametre degerleri;
analize giren ve olusmus olay sayilari; K2 farki; kesif kosusunun commit hash'i ve UTC zamani;
tohum. Onay kosusu, kostugu hipotezin yapilandirmasini bu dosyadan okur; dosyada kaydi olmayan ya
da hukmu 'hipotez kapandi' olan bir hipotez icin onay kosusu acilmaz. Dosya da yalnizca ekleme
kuralina tabidir: bir hipotezin kaydi yazildiktan sonra degistirilmez."

Bu dosya YALNIZCA okuma tarafini sinar: KILIT.md'yi F2 yazar (faz siniri, CLAUDE.md §4) ve bu turda
yazma kodu yazilmadi. Testler sahte git kipinde, gecici bir kilit kokunde calisir; gercek depodaki
`analysis/<hipotez>/KILIT.md` dosyalarina dokunulmaz (kilitli dosyalar).

Aga cikmaz; getiri hesaplanmaz.
"""

from __future__ import annotations

import pytest

import config
from data import split
from onay_yardimcisi import gecici_kayit, kilit_metni, kilit_yaz, kosu


@pytest.fixture
def kayit(tmp_path):
    """Sahte git kipinde onay kaydi + uc hipotez icin varsayilan kilit kaydi."""
    yol = tmp_path / "onay_gecici.md"
    yol.write_text("bas\n", encoding="utf-8")
    gecici_kayit(yol)
    return yol


@pytest.fixture
def bos_kilit(tmp_path):
    """Kilit koku BOS: hicbir hipotezin kaydi yok."""
    yol = tmp_path / "onay_gecici.md"
    yol.write_text("bas\n", encoding="utf-8")
    kok = tmp_path / "bos_kok"
    kok.mkdir()
    gecici_kayit(yol, kilit_koku=kok)
    return kok


# --- 1. Kaydi olmayan hipotez icin kosu acilmaz ----------------------------------------------


def test_kaydi_olmayan_hipotez_icin_kosu_acilmaz_ve_kayda_yazilmaz(bos_kilit, tmp_path):
    kayit_yolu = tmp_path / "onay_gecici.md"
    once = kayit_yolu.read_bytes()
    with pytest.raises(split.KilitYok):
        with kosu("H2", "C1"):
            pytest.fail("kaydi olmayan hipotez icin kosu acilmamali")
    # Hicbir sey yazilmadi: onay cifti HARCANMADI (on-kayit §8 madde 4).
    assert kayit_yolu.read_bytes() == once
    assert split.aktif_onay_kosusu() is None
    assert split.kayittaki_kosular(kayit_yolu.read_text(encoding="utf-8")) == set()


def test_kilit_okuma_hipotez_adini_dogrular(bos_kilit):
    for bozuk in ("h2", "H2 ", "", None, 2, "H4"):
        with pytest.raises((ValueError, TypeError)):
            split.kilit_oku(bozuk)


def test_kilit_yolu_on_kayitta_yazili_olan_yoldur(bos_kilit):
    for hipotez in config.HIPOTEZLER:
        yol = split.kilit_yolu(hipotez)
        assert yol.parent.name == hipotez and yol.parent.parent.name == "analysis"
        assert yol.name == split.KILIT_ADI == "KILIT.md"


# --- 2. Hukmu "hipotez kapandi" olan hipotez icin kosu acilmaz --------------------------------


def test_kapanmis_hipotez_icin_kosu_acilmaz(bos_kilit, tmp_path):
    kilit_yaz(bos_kilit, "H2", hukum=split.KILIT_KAPANDI, gerekce="aday yok",
              yapilandirma="-", parametreler="-", k2_farki="-")
    kayit_yolu = tmp_path / "onay_gecici.md"
    once = kayit_yolu.read_bytes()
    with pytest.raises(split.HipotezKapandi):
        with kosu("H2", "C1"):
            pytest.fail("kapanmis hipotez icin kosu acilmamali")
    assert kayit_yolu.read_bytes() == once, "kapanmis hipotez icin onay cifti harcanmaz"
    assert split.aktif_onay_kosusu() is None

    kayit = split.kilit_oku("H2")
    assert kayit.secildi is False and kayit.gerekce == "aday yok"


def test_secilmis_hipotez_icin_kosu_acilir_ve_kilit_kosuya_baglanir(kayit):
    with kosu("H2", "C1"):
        assert split.aktif_onay_kosusu() == ("H2", "C1")
    kilit = split.kilit_oku("H2")
    assert kilit.secildi and kilit.hukum == split.KILIT_SECILDI
    assert kilit.yapilandirma == "H2:phi=0.0003,k=3"


# --- 3. Alanlarin tamami zorunlu; ikinci kez yazilan alan ekleme kuralini bozar ---------------


@pytest.mark.parametrize("eksik", split.KILIT_ALANLARI)
def test_eksik_alan_kilit_bozuk(eksik):
    metin = kilit_metni("H2")
    kirpik = "\n".join(s for s in metin.splitlines() if not s.startswith(f"| {eksik} |"))
    with pytest.raises(split.KilitBozuk, match="eksik alan"):
        split.kilit_kaydi_coz(kirpik, "H2")


def test_iki_kez_yazilan_alan_ekleme_kuralini_bozar():
    """On-kayit §8 madde 5: "bir hipotezin kaydi yazildiktan sonra degistirilmez"."""
    metin = kilit_metni("H2") + "| k2_farki | 0.9999 |\n"
    with pytest.raises(split.KilitBozuk, match="birden fazla kez"):
        split.kilit_kaydi_coz(metin, "H2")


def test_baska_hipotezin_kaydi_okunmaz():
    with pytest.raises(split.KilitBozuk, match="hipotez alani"):
        split.kilit_kaydi_coz(kilit_metni("H1"), "H2")


@pytest.mark.parametrize("hukum", ["secildi", "GECTI", "", "hipotez kapandi ", "yapilandirma secildi."])
def test_bilinmeyen_hukum_reddedilir(hukum):
    with pytest.raises(split.KilitBozuk, match="hukum"):
        split.kilit_kaydi_coz(kilit_metni("H2", hukum=hukum), "H2")


@pytest.mark.parametrize("alan", split.KILIT_SECIM_ALANLARI)
def test_secildi_hukmunde_secim_alanlari_bos_olamaz(alan):
    metin = kilit_metni("H2", **{alan: "-"})
    with pytest.raises(split.KilitBozuk, match="bos olamaz"):
        split.kilit_kaydi_coz(metin, "H2")


def test_kapandi_hukmunde_gerekce_zorunlu():
    """On-kayit §8 madde 4: "kapanma gerekcesi 'aday yok' olarak yazilir"."""
    with pytest.raises(split.KilitBozuk, match="gerekce"):
        split.kilit_kaydi_coz(kilit_metni("H2", hukum=split.KILIT_KAPANDI, gerekce="-",
                                          yapilandirma="-", parametreler="-", k2_farki="-"), "H2")
    # Gerekce yazildiysa cozulur ve secildi FALSE'tur.
    kayit = split.kilit_kaydi_coz(
        kilit_metni("H2", hukum=split.KILIT_KAPANDI, gerekce="aday yok", yapilandirma="-",
                    parametreler="-", k2_farki="-"), "H2")
    assert kayit.secildi is False


def test_tohum_on_kayit_degeri_olmali():
    with pytest.raises(split.KilitBozuk, match="tohum"):
        split.kilit_kaydi_coz(kilit_metni("H2", tohum=config.TOHUM + 1), "H2")
    with pytest.raises(split.KilitBozuk, match="tamsayi"):
        split.kilit_kaydi_coz(kilit_metni("H2", tohum="yok"), "H2")


def test_analize_giren_olusmusu_asamaz():
    """On-kayit §8 madde 2: analize giren olaylar olusmus olaylarin ALT kumesidir."""
    with pytest.raises(split.KilitBozuk, match="asamaz"):
        split.kilit_kaydi_coz(kilit_metni("H2", olusmus=100, analize_giren=101), "H2")
    # Esitlik gecerlidir (hicbir olay havuzsuz kalmamis olabilir).
    kayit = split.kilit_kaydi_coz(kilit_metni("H2", olusmus=100, analize_giren=100), "H2")
    assert kayit.olusmus_olay == kayit.analize_giren_olay == 100


def test_cozulen_kayit_on_kayit_alanlarini_tasir():
    kayit = split.kilit_kaydi_coz(kilit_metni("H2"), "H2")
    assert kayit.hipotez == "H2" and kayit.yapilandirma == "H2:phi=0.0003,k=3"
    assert kayit.parametreler == "phi=0.0003 k=3"
    assert kayit.olusmus_olay == 400 and kayit.analize_giren_olay == 380
    assert kayit.k2_farki == pytest.approx(0.0210)
    assert kayit.kesif_commit == "0" * 40 and kayit.tohum == config.TOHUM
    assert kayit.kesif_zamani.endswith("+00:00")


# --- 4. Kosu, KILIT.md'deki yapilandirmayi pozisyonun yapilandirmasiyla eslestirir ------------


def test_baska_yapilandirma_onay_kosusunda_reddedilir(kayit):
    """On-kayit §8 madde 5: "Onay kosusu, kostugu hipotezin yapilandirmasini bu dosyadan okur";
    §9: "Secilen yapilandirma C1 ve C2'de birer kez kosulur"."""
    with kosu("H2", "C1"):
        split.onay_baglami_dogrula("H2", "C1", "H2:phi=0.0003,k=3")       # kilitli olan
        for baska in ("H2:phi=0.0003,k=6", "H2:phi=0.0005,k=3", "H1:theta=0.2,delta=0.08"):
            with pytest.raises(split.OnayUyusmazligi, match="KILIT.md"):
                split.onay_baglami_dogrula("H2", "C1", baska)


def test_yapilandirma_verilmezse_eski_denetim_korunur(kayit):
    """`yapilandirma=None`: rev.13 oncesi davranis (yalnizca hipotez + kume eslestirmesi)."""
    with kosu("H2", "C1"):
        split.onay_baglami_dogrula("H2", "C1")
        with pytest.raises(split.OnayUyusmazligi):
            split.onay_baglami_dogrula("H1", "C1", "H1:theta=0.2,delta=0.08")


def test_kesif_kosusunda_kilit_eslestirmesi_yapilmaz(kayit):
    """KESIF'te acik kosu yoktur; kilit eslestirmesi yalnizca acik onay kosusunda islerdir
    (on-kayit §3: kesif serbest)."""
    split.onay_baglami_dogrula("H2", "KESIF", "H2:phi=0.0005,k=12")
