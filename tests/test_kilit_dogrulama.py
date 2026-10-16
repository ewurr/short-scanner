"""KILIT.md kaydinin ON-KAYDA GORE dogrulanmasi (on-kayit §8 madde 2-5).

Tasarim ilkesi: dogrulama KOSU ACILMADAN ONCE calisir. Bozuk ya da on-kayda aykiri bir kilit
kaydi yuzunden tek atisin harcanmasi kabul edilemez -- sizinti bulgusu S-C3'un zarari tam budur:
`k2_farki <= 0` olan bir kayitla kosu aciliyor, BASLADI satiri yaziliyor ve (hipotez, kume) cifti
yaniyordu.

Bu dosya sirayla su bulgulari kapatir:
  2a (S-C3) §8 madde 4 olcutleri: K2 farki > 0 (ve kayitta varsa ortalama net getiri > 0).
  2b (S-C4) §8 madde 2-3 aday esigi: analize giren olay sayisi >= `config.ADAY_OLAY_ESIGI`.

Aga cikmaz; getiri hesaplanmaz.
"""

from __future__ import annotations

import pytest

import config
from data import split
from onay_yardimcisi import gecici_kayit, kilit_metni, kilit_yaz, kosu

KAPANDI_ALANLARI = dict(hukum=split.KILIT_KAPANDI, gerekce="aday yok", yapilandirma="-",
                        parametreler="-", k2_farki="-")


@pytest.fixture
def bos_kilit(tmp_path):
    """Sahte git kipinde bos bir kilit koku: kayitlari testler kendisi yazar."""
    yol = tmp_path / "onay_gecici.md"
    yol.write_text("bas\n", encoding="utf-8")
    kok = tmp_path / "kilit_koku"
    kok.mkdir()
    gecici_kayit(yol, kilit_koku=kok)
    return kok


def _coz(**alanlar):
    return split.kilit_kaydi_coz(kilit_metni("H2", **alanlar), "H2")


# --- 2a. §8 madde 4: K2 farki > 0 --------------------------------------------------------------


@pytest.mark.parametrize("deger", ["0.0000", "-0.0100", "0", "-1", "0.0", "-0.00001"])
def test_k2_farki_pozitif_olmali(deger):
    with pytest.raises(split.KilitBozuk, match="K2 farki > 0"):
        _coz(k2_farki=deger)


@pytest.mark.parametrize("deger", ["0.0001", "0.0210", "1", "0,0150"])
def test_pozitif_k2_farki_gecer(deger):
    kayit = _coz(k2_farki=deger)
    assert kayit.k2_farki > 0


def test_kapandi_hukmunde_k2_farki_aranmaz():
    """Kapanmis hipotezde secilecek yapilandirma yoktur; olcut secim icindir (§8 madde 4)."""
    kayit = split.kilit_kaydi_coz(kilit_metni("H2", **KAPANDI_ALANLARI), "H2")
    assert kayit.secildi is False


def test_k2_farki_sifir_olan_kayitla_kosu_acilmaz(bos_kilit, tmp_path):
    """S-C3'un zarari: kosu acilip cift harcanmamali."""
    kilit_yaz(bos_kilit, "H2", k2_farki="0.0000")
    kayit_yolu = tmp_path / "onay_gecici.md"
    once = kayit_yolu.read_bytes()
    with pytest.raises(split.KilitBozuk):
        with kosu("H2", "C1"):
            pytest.fail("bozuk kilit kaydiyla kosu acilmamali")
    assert kayit_yolu.read_bytes() == once, "hicbir sey yazilmadi: cift harcanmadi"
    assert split.aktif_onay_kosusu() is None
    assert split.kayittaki_kosular(kayit_yolu.read_text(encoding="utf-8")) == set()


# --- 2a. §8 madde 4: ortalama net getiri (istege bagli alan) ----------------------------------


@pytest.mark.parametrize("deger", ["0.0000", "-0.0100", "0", "-0.5"])
def test_ortalama_net_getiri_varsa_pozitif_olmali(deger):
    metin = kilit_metni("H2") + f"| ortalama_net_getiri | {deger} |\n"
    with pytest.raises(split.KilitBozuk, match="ortalama net getiri > 0"):
        split.kilit_kaydi_coz(metin, "H2")


def test_pozitif_ortalama_net_getiri_gecer():
    metin = kilit_metni("H2") + "| ortalama_net_getiri | 0.0123 |\n"
    kayit = split.kilit_kaydi_coz(metin, "H2")
    assert kayit.secildi


def test_ortalama_net_getiri_zorunlu_degil():
    """On-kayit §8 madde 5'in alan listesinde yok: alan ZORUNLU kilinmaz, varsa denetlenir."""
    assert "ortalama_net_getiri" not in split.KILIT_ALANLARI
    assert "ortalama_net_getiri" in split.KILIT_ISTEGE_BAGLI_ALANLAR
    assert _coz().secildi, "alansiz kayit gecerli"


def test_kapandi_hukmunde_ortalama_net_getiri_de_aranmaz():
    metin = kilit_metni("H2", **KAPANDI_ALANLARI) + "| ortalama_net_getiri | -0.3 |\n"
    assert split.kilit_kaydi_coz(metin, "H2").secildi is False


# --- Onceki turda kurulan denetimler korundu --------------------------------------------------


def test_rev13_denetimleri_korundu():
    with pytest.raises(split.KilitBozuk, match="eksik alan"):
        split.kilit_kaydi_coz("| hipotez | H2 |\n", "H2")
    with pytest.raises(split.KilitBozuk, match="birden fazla kez"):
        split.kilit_kaydi_coz(kilit_metni("H2") + "| tohum | 1 |\n", "H2")
    with pytest.raises(split.KilitBozuk, match="hukum"):
        _coz(hukum="GECTI")
    with pytest.raises(split.KilitBozuk, match="tohum"):
        _coz(tohum=config.TOHUM + 1)
    with pytest.raises(split.KilitBozuk, match="asamaz"):
        _coz(olusmus=200, analize_giren=201)


# --- 2b. §8 madde 2-3: aday esigi -------------------------------------------------------------


@pytest.mark.parametrize("analize", [0, 1, 149])
def test_aday_esiginin_altinda_secim_olamaz(analize):
    """On-kayit §8 madde 2-3: yalnizca analize giren olay sayisi >= 150 olanlar ADAYDIR ve secim
    adaylar arasindan yapilir. Esigin altindaki bir "secildi" kaydi madde 4 geregi "aday yok"
    gerekcesiyle kapanmis olmaliydi."""
    with pytest.raises(split.KilitBozuk, match="esigini gecmeli"):
        _coz(olusmus=400, analize_giren=analize)


def test_esik_kenari_tam_150_gecer():
    assert config.ADAY_OLAY_ESIGI == 150
    kayit = _coz(olusmus=400, analize_giren=config.ADAY_OLAY_ESIGI)
    assert kayit.analize_giren_olay == config.ADAY_OLAY_ESIGI
    with pytest.raises(split.KilitBozuk, match="esigini gecmeli"):
        _coz(olusmus=400, analize_giren=config.ADAY_OLAY_ESIGI - 1)


def test_kapandi_hukmunde_esik_aranmaz():
    """Kapanmis hipotezde olay sayisi esigin altinda olabilir; zaten bu yuzden kapanmistir."""
    kayit = split.kilit_kaydi_coz(
        kilit_metni("H2", olusmus=10, analize_giren=3, **KAPANDI_ALANLARI), "H2")
    assert kayit.secildi is False and kayit.analize_giren_olay == 3


def test_esigin_altindaki_kayitla_kosu_acilmaz(bos_kilit, tmp_path):
    kilit_yaz(bos_kilit, "H2", olusmus=200, analize_giren=149)
    kayit_yolu = tmp_path / "onay_gecici.md"
    once = kayit_yolu.read_bytes()
    with pytest.raises(split.KilitBozuk):
        with kosu("H2", "C1"):
            pytest.fail("aday esigini gecmeyen kayitla kosu acilmamali")
    assert kayit_yolu.read_bytes() == once
