"""KILIT.md kaydinin ON-KAYDA GORE dogrulanmasi (on-kayit §8 madde 2-5).

Tasarim ilkesi: dogrulama KOSU ACILMADAN ONCE calisir. Bozuk ya da on-kayda aykiri bir kilit
kaydi yuzunden tek atisin harcanmasi kabul edilemez -- sizinti bulgusu S-C3'un zarari tam budur:
`k2_farki <= 0` olan bir kayitla kosu aciliyor, BASLADI satiri yaziliyor ve (hipotez, kume) cifti
yaniyordu.

Bu dosya sirayla su bulgulari kapatir:
  2a (S-C3) §8 madde 4 olcutleri: K2 farki > 0 (ve kayitta varsa ortalama net getiri > 0).
  2b (S-C4) §8 madde 2-3 aday esigi: analize giren olay sayisi >= `config.ADAY_OLAY_ESIGI`.
  2c (S-C5 / D-C4) §5, §8 madde 5: yapilandirma kimligi izgarada bulunmali.
  2d (S-C6) §8 madde 5: olay sayilari negatif olamaz, ondalik ayirici sessizce atilmaz.
  2e (S-C7) §8 madde 5: kesif commit hash'i 40 haneli onaltilik, kesif zamani UTC ve ISO.
  2f (S-C8) §8 madde 4-5: kapanmis hipotez `HipotezKapandi` verir (`KilitYok` degil).
  2g (S-C9) §8 madde 5: ekleme kurali git GECMISINDEN denetlenir (hook'a dayanmaz).

Aga cikmaz; getiri hesaplanmaz.
"""

from __future__ import annotations

import pytest

import config
from data import split
from onay_yardimcisi import gecici_depo, gecici_kayit, git, kilit_metni, kilit_yaz, kosu

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


# --- 2c. §5, §8 madde 5: yapilandirma kimligi izgarada --------------------------------------


@pytest.mark.parametrize("kimlik", ["H2:phi=0.0003,k=4", "H2:phi=0.0004,k=3", "H2", "baska",
                                    "H1:theta=0.2,delta=0.08", "h2:phi=0.0003,k=3",
                                    "phi=0.0003,k=3", "H2:k=3,phi=0.0003"])
def test_izgara_disi_kimlik_reddedilir(kimlik):
    """On-kayit §5 (rev.11): "Izgara parametreleri ... yalnizca bu on-kayitta tanimlidir ...
    izgarada bulunmayan bir parametre demeti hata verir." §9: secilen yapilandirma C1 ve C2'de
    birer kez kosulur -- bozuk kimlik, kosu acildiktan sonra her pozisyonu reddeder ve onay hakki
    bos yere yanar."""
    with pytest.raises(split.KilitBozuk, match="izgarasinda yok"):
        _coz(yapilandirma=kimlik)


def test_sondaki_bosluk_kirpilir():
    """Bicim denetimi degerin KIRPILMIS halini kullanir; tablo hucresindeki bosluk kaydi bozmaz."""
    assert _coz(yapilandirma="H2:phi=0.0003,k=3 ").yapilandirma.strip() == "H2:phi=0.0003,k=3"


@pytest.mark.parametrize("kimlik", ["H2:phi=0.0003,k=3", "H2:phi=0.0005,k=6", "H2:phi=0.001,k=12"])
def test_izgaradaki_kimlik_gecer(kimlik):
    from data import sinyal

    gecerliler = [sinyal.yapilandirma_kimligi("H2", y) for y in sinyal.izgara("H2")]
    assert kimlik in gecerliler, "test kurulumu: kimlik gercekten izgarada"
    assert _coz(yapilandirma=kimlik).yapilandirma == kimlik


def test_butun_izgara_kimlikleri_kabul_edilir():
    from data import sinyal

    for y in sinyal.izgara("H2"):
        kimlik = sinyal.yapilandirma_kimligi("H2", y)
        assert _coz(yapilandirma=kimlik).secildi


def test_baska_hipotezin_izgara_kimligi_reddedilir():
    from data import sinyal

    h1_kimlik = sinyal.yapilandirma_kimligi("H1", sinyal.izgara("H1")[0])
    with pytest.raises(split.KilitBozuk, match="izgarasinda yok"):
        _coz(yapilandirma=h1_kimlik)


def test_kapandi_hukmunde_kimlik_aranmaz():
    kayit = split.kilit_kaydi_coz(kilit_metni("H2", **KAPANDI_ALANLARI), "H2")
    assert kayit.secildi is False and kayit.yapilandirma == "-"


# --- 2g. §8 madde 5: ekleme kurali git gecmisinden ---------------------------------------------


def test_gecmiste_degistirilmis_kayit_reddedilir(tmp_path):
    """On-kayit §8 madde 5: "Dosya da yalnizca ekleme kuralina tabidir: bir hipotezin kaydi
    yazildiktan sonra degistirilmez." Onceki uygulama yalnizca HEAD ile calisma agacini
    karsilastiriyordu, bu yuzden IKINCI BIR COMMIT'LE degistirilen kayit fark edilmiyordu ve
    ekleme kurali yalnizca `PreToolUse` hook'una dayaniyordu (hook arac cagrilarini yakalar,
    calisan git'i degil)."""
    depo = gecici_depo(tmp_path, kilitler=("H1", "H3"))
    kilit_yaz(depo, "H2")
    git(depo, "add", ".")
    git(depo, "commit", "-q", "-m", "H2 kaydi")
    split.kilit_oku("H2")                               # tek commit: gecerli

    kilit_yaz(depo, "H2", yapilandirma="H2:phi=0.0005,k=6", parametreler="phi=0.0005 k=6")
    git(depo, "add", ".")
    git(depo, "commit", "-q", "-m", "H2 kaydi degistirildi")
    with pytest.raises(split.KilitBozuk, match="farkli icerikle"):
        split.kilit_oku("H2")


def test_gecmiste_degistirilmis_kayitla_kosu_acilmaz(tmp_path):
    depo = gecici_depo(tmp_path, kilitler=("H1", "H3"))
    kilit_yaz(depo, "H2")
    git(depo, "add", ".")
    git(depo, "commit", "-q", "-m", "H2 kaydi")
    git(depo, "push", "-q", "origin", "main")
    kilit_yaz(depo, "H2", k2_farki="0.9999")
    git(depo, "add", ".")
    git(depo, "commit", "-q", "-m", "K2 farki buyutuldu")
    git(depo, "push", "-q", "origin", "main")
    once = (depo / "ONAY_KAYDI.md").read_bytes()
    with pytest.raises(split.KilitBozuk, match="farkli icerikle"):
        with kosu("H2", "C1"):
            pytest.fail("gecmiste degistirilmis kayitla kosu acilmamali")
    assert (depo / "ONAY_KAYDI.md").read_bytes() == once
    assert split.aktif_onay_kosusu() is None


def test_tek_committe_eklenen_kayit_gecerli(tmp_path):
    """Ekleme ile degistirme ayirt edilir: tek commit'te eklenen kayit sorunsuz okunur."""
    depo = gecici_depo(tmp_path, kilitler=("H1", "H3"))
    kilit_yaz(depo, "H2")
    git(depo, "add", ".")
    git(depo, "commit", "-q", "-m", "H2 kaydi")
    kayit = split.kilit_oku("H2")
    assert kayit.secildi and kayit.hipotez == "H2"
    # Baska dosyalari degistiren commit'ler kaydi etkilemez.
    (depo / "analysis" / "baska.txt").write_text("x\n", encoding="utf-8")
    git(depo, "add", ".")
    git(depo, "commit", "-q", "-m", "ilgisiz degisiklik")
    assert split.kilit_oku("H2").secildi


def test_ayni_icerikle_yeniden_eklenen_kayit_gecerli(tmp_path):
    """Olcut commit SAYISI degil, farkli ICERIK sayisidir: silinip ayni icerikle geri eklenen
    kayit ekleme kuralini bozmaz (ve `git stash` gibi agac anlik goruntuleri yanlis pozitif
    uretmez)."""
    depo = gecici_depo(tmp_path, kilitler=("H1", "H3"))
    yol = kilit_yaz(depo, "H2")
    metin = yol.read_text(encoding="utf-8")
    git(depo, "add", ".")
    git(depo, "commit", "-q", "-m", "H2 kaydi")
    yol.unlink()
    git(depo, "add", "-A")
    git(depo, "commit", "-q", "-m", "kayit silindi")
    yol.write_text(metin, encoding="utf-8", newline="")
    git(depo, "add", "-A")
    git(depo, "commit", "-q", "-m", "ayni kayit geri")
    assert split.kilit_oku("H2").secildi


def test_sahte_git_kipinde_gecmis_aranmaz(bos_kilit):
    """Sahte git kipi (yalnizca pytest) HEAD ve gecmis denetimlerini atlar; `ONAY_KAYDI` ile ayni
    yaklasim. Gercek kipte iki denetim de calisir (yukaridaki testler)."""
    kilit_yaz(bos_kilit, "H2")
    assert split.kilit_oku("H2").secildi


# --- 2f. §8 madde 4-5: kapanmis hipotezin hata sinifi -----------------------------------------


def test_ayni_kapandi_metninin_iki_cozumu_esit():
    """Kok neden: kapandi kaydinda `k2_farki` NaN'di ve `NaN != NaN` oldugu icin ayni metnin iki
    cozumu esit cikmiyordu; `kilit_oku`nun HEAD/calisma agaci karsilastirmasi bu yuzden kapandi
    kayitlarinda HER ZAMAN "farkli" diyor ve `KilitYok` veriyordu (sizinti bulgusu S-C8)."""
    metin = kilit_metni("H2", **KAPANDI_ALANLARI)
    assert split.kilit_kaydi_coz(metin, "H2") == split.kilit_kaydi_coz(metin, "H2")


def test_kapandi_hukmunde_k2_farki_none():
    """"Hesaplanamaz" `None` ile gosterilir; NaN kullanilmaz (esitlik bozulmasin)."""
    kayit = split.kilit_kaydi_coz(kilit_metni("H2", **KAPANDI_ALANLARI), "H2")
    assert kayit.k2_farki is None


def test_secildi_hukmunde_k2_farki_sayi():
    assert _coz().k2_farki == pytest.approx(0.0210)


def test_kapanmis_hipotez_hipotez_kapandi_verir(bos_kilit, tmp_path):
    """On-kayit §8 madde 5: "hukmu 'hipotez kapandi' olan bir hipotez icin onay kosusu acilmaz."
    Red dogruydu, SINIFI yanlisti (sahte git kipinde `HipotezKapandi`, gercek kipte `KilitYok`)."""
    kilit_yaz(bos_kilit, "H2", **KAPANDI_ALANLARI)
    kayit_yolu = tmp_path / "onay_gecici.md"
    once = kayit_yolu.read_bytes()
    with pytest.raises(split.HipotezKapandi):
        with kosu("H2", "C1"):
            pytest.fail("kapanmis hipotez icin kosu acilmamali")
    assert kayit_yolu.read_bytes() == once


# --- 2e. §8 madde 5: commit hash'i ve UTC zamani ----------------------------------------------


@pytest.mark.parametrize("deger", ["yok", "", "0" * 39, "0" * 41, "g" * 40, "0123456789",
                                   "0" * 40 + " ", "HEAD", "0" * 20 + "-" + "0" * 19])
def test_bozuk_kesif_commiti_reddedilir(deger):
    """On-kayit §8 madde 5: "kesif kosusunun commit hash'i". Tam 40 haneli onaltilik (git SHA-1).

    Sondaki bosluk kirpilir, bu yuzden "0"*40 + " " gecerli sayilir -- onu ayri test eder."""
    if deger.strip() == "0" * 40:
        assert _coz(commit=deger).kesif_commit.strip() == "0" * 40
        return
    with pytest.raises(split.KilitBozuk, match="40 haneli onaltilik"):
        _coz(commit=deger)


@pytest.mark.parametrize("deger", ["0" * 40, "a1b2c3d4e5" * 4, ("A1B2C3D4E5" * 4)])
def test_gecerli_commit_hashi_gecer(deger):
    """Buyuk harfli hash de gecerlidir (git ciktisi kucuk harf olsa da kayit elle yazilir)."""
    assert _coz(commit=deger).kesif_commit == deger


@pytest.mark.parametrize("deger", ["dun", "", "2026-13-45", "yakinda",
                                   "2026-10-20T12:00:00", "2026-10-20 12:00:00",
                                   "2026-10-20T12:00:00+03:00", "2026-10-20T12:00:00-05:00"])
def test_bozuk_kesif_zamani_reddedilir(deger):
    """On-kayit §8 madde 5: "kesif kosusunun ... UTC zamani"; CLAUDE.md §5: butun damgalar UTC.
    Saat dilimsiz ve UTC disi damga reddedilir."""
    with pytest.raises(split.KilitBozuk, match="ISO 8601|UTC olmali"):
        _coz(zaman=deger)


@pytest.mark.parametrize("deger", ["2026-10-20T12:00:00+00:00", "2026-10-20 12:00:00+00:00",
                                   "2026-10-20T12:00:00Z", "2026-01-01T00:00:00+00:00"])
def test_gecerli_utc_zamani_gecer(deger):
    assert _coz(zaman=deger).kesif_zamani == deger


def test_bozuk_commitle_kosu_acilmaz(bos_kilit, tmp_path):
    kilit_yaz(bos_kilit, "H2", commit="yok")
    kayit_yolu = tmp_path / "onay_gecici.md"
    once = kayit_yolu.read_bytes()
    with pytest.raises(split.KilitBozuk, match="40 haneli"):
        with kosu("H2", "C1"):
            pytest.fail("bozuk commit hash'iyle kosu acilmamali")
    assert kayit_yolu.read_bytes() == once


def test_commitin_varligi_gitte_aranmaz():
    """Bicim denetlenir, VARLIK aranmaz: kesif kosusunun commit'i baska bir dalda ya da henuz
    itilmemis olabilir."""
    assert _coz(commit="f" * 40).kesif_commit == "f" * 40


# --- 2d. §8 madde 5: sayi ayristirmasi --------------------------------------------------------


@pytest.mark.parametrize("deger", ["-5", "-1", "- 5", "+5", "1.5", "0.5", "151.5", "1,5",
                                   "yok", "", " ", "1e3", "0x10", "nan", "inf", "1 500"])
def test_bozuk_olay_sayisi_reddedilir(deger):
    """Sayilar sayimdir: negatif, isaretli, ondalikli ya da sayi olmayan deger kabul edilmez.
    Onceki uygulama butun noktalari siliyordu, bu yuzden "1.5" sessizce 15 okunuyordu."""
    with pytest.raises(split.KilitBozuk, match="negatif olmayan bir tamsayi"):
        _coz(olusmus=deger, analize_giren=200)
    with pytest.raises(split.KilitBozuk, match="negatif olmayan bir tamsayi"):
        _coz(olusmus=400, analize_giren=deger)


@pytest.mark.parametrize("ham,beklenen", [("200", 200), ("1500", 1500), ("1.500", 1500),
                                          ("12.345.678", 12345678), (" 200 ", 200)])
def test_gecerli_tamsayi_bicimleri(ham, beklenen):
    """Nokta yalnizca BINLIK ayirici olarak, uclu gruplar halinde kabul edilir."""
    kayit = _coz(olusmus=ham, analize_giren="200")
    assert kayit.olusmus_olay == beklenen


@pytest.mark.parametrize("deger", ["1.50", "1.5000", "12.34", "1.500.00"])
def test_uclu_olmayan_gruplar_reddedilir(deger):
    with pytest.raises(split.KilitBozuk, match="negatif olmayan bir tamsayi"):
        _coz(olusmus=deger, analize_giren=200)


def test_tohum_alani_da_ayni_ayristirmadan_gecer():
    with pytest.raises(split.KilitBozuk, match="negatif olmayan bir tamsayi"):
        _coz(tohum="-20260911")
    with pytest.raises(split.KilitBozuk, match="negatif olmayan bir tamsayi"):
        _coz(tohum="2.0260911")


def test_negatif_sayilarla_kosu_acilmaz(bos_kilit, tmp_path):
    kilit_yaz(bos_kilit, "H2", olusmus="-5", analize_giren="-6")
    kayit_yolu = tmp_path / "onay_gecici.md"
    once = kayit_yolu.read_bytes()
    with pytest.raises(split.KilitBozuk):
        with kosu("H2", "C1"):
            pytest.fail("negatif olay sayilariyla kosu acilmamali")
    assert kayit_yolu.read_bytes() == once


def test_izgara_disi_kimlikle_kosu_acilmaz(bos_kilit, tmp_path):
    """D-C4'un zarari: bozuk kimlik kosu ACILDIKTAN sonra patliyordu, cift harcaniyordu."""
    kilit_yaz(bos_kilit, "H2", yapilandirma="H2:phi=0.0003,k=4")
    kayit_yolu = tmp_path / "onay_gecici.md"
    once = kayit_yolu.read_bytes()
    with pytest.raises(split.KilitBozuk, match="izgarasinda yok"):
        with kosu("H2", "C1"):
            pytest.fail("izgara disi kimlikle kosu acilmamali")
    assert kayit_yolu.read_bytes() == once
