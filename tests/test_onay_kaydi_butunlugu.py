"""Onay kaydi ve kosu butunlugu turu (denetci KS3 D-B1, D-B2, D-B3, D-C3).

Koruma olcutu: ayni surec icinden mutlak koruma mumkun degil. Amac, onay kaydini atlatmanin kazayla olmamasi ve
gecmiste iz birakmayan bir yolla yapilamamasi. Testler:
  - D-B1: `onay_kosusu`'nun `yol=` parametresi yok; `config.ONAY_KAYDI` yeniden atanamaz; `split._AKTIF_KOSU`
    dogrudan yazilamaz; modul sozlugu uzerinden kurulan kosu kayitta acik bir satir olmadan erisim acamaz.
  - D-B2: kirli agacta, git yokken, etkilesimli oturumda ya da izlenmeyen betikten kosu acilmaz; commit hash'i
    kayda yazilir.
  - D-B3: kosu sonucu (ya da hatasi) UTC baslangic ve bitisle kayda yazilir; ayni cift ikinci kez kosulamaz.
  - D-C3: `cikis_bari` ve `pozisyon_fundingi`'nin veri hatalari `VeriHatasi`.
Gercek kayit dosyasina yazilmaz; kayit `split._test_kaydi_ayarla` ile gecici dosyaya yonlenir.
"""

from __future__ import annotations

import inspect
import re

import pandas as pd
import pytest

import config
from data import funding, pencere, split
from onay_yardimcisi import gecici_kayit, kosu
from tarama_yardimcisi import ONAY_ATLATMA_DESENI, ihlaller

B_SEMBOLU = "BTCUSDT"  # gercek split.csv'de B grubu (C1 erisim denemesi icin; veri yuklenmez)
COMMIT = "0123456789abcdef" * 2 + "01234567"


@pytest.fixture
def kayit(tmp_path):
    yol = tmp_path / "onay_gecici.md"
    yol.write_text("bas\n", encoding="utf-8")
    return gecici_kayit(yol, head=COMMIT)


def _satirlar(yol) -> list[dict[str, str]]:
    return split.kayit_satirlari(yol.read_text(encoding="utf-8"))


def _c1_erisimi():
    return split.kume_erisimi(B_SEMBOLU, "C1", onay=True)


# --- D-B1: uc atlatma yolu ----------------------------------------------------------------------------


def test_onay_kosusu_yol_parametresi_almaz(kayit):
    assert list(inspect.signature(split.onay_kosusu).parameters) == ["hipotez", "kume"]
    with pytest.raises(TypeError):
        with split.onay_kosusu("H1", "C1", yol=kayit):
            pytest.fail("yol= ile kosu acilmamali")
    assert kayit.read_text(encoding="utf-8") == "bas\n"
    assert not hasattr(split, "onay_kaydet"), "yol alan eski kayit yazicisi kaldirildi"


def test_config_onay_kaydi_yeniden_atanamaz(tmp_path):
    once = config.ONAY_KAYDI
    with pytest.raises(config.SabitDegistirilemez):
        config.ONAY_KAYDI = tmp_path / "baska.md"
    with pytest.raises(config.SabitDegistirilemez):
        setattr(config, "ONAY_KAYDI", tmp_path / "baska.md")
    with pytest.raises(config.SabitDegistirilemez):
        del config.ONAY_KAYDI
    assert config.ONAY_KAYDI == once
    config.SPLIT_CSV = config.SPLIT_CSV  # korunmayan adlar etkilenmez


def test_config_sozlugunden_degistirilen_yol_artik_okumayi_hic_etkilemiyor(tmp_path, kayit):
    """`vars(config)` yazimi kayit yolunu DEGISTIREMEZ: `config.ONAY_KAYDI` artik veri
    tanimlayicisindan okunur (koruma turu madde 5), yani sozluge yazim okumaya hic ulasmaz.

    Testin ilk hali ikinci savunma katmanini sabitliyordu: sozluk yazimi okumayi degistirebiliyor,
    ama `split` yolu yukleme aninda sabitledigi icin farki `OnayKorumasi` ("tek kaynak") ile
    yakaliyordu. Madde 5'ten sonra BIRINCI katman tutuyor: fark hic olusmuyor, bu yuzden koşu
    normal acilir ve kayit GERCEK dosyaya yazilir. Hukum ayni ve daha gucludur: sozluk yolu
    kaydi baska bir dosyaya yonlendiremez."""
    sozluk = vars(config)
    once = sozluk["ONAY_KAYDI"]
    sahte = tmp_path / "baska.md"
    try:
        sozluk["ONAY_KAYDI"] = sahte
        assert config.ONAY_KAYDI == once, "okuma veri tanimlayicisindan gelmeli"
        with split.onay_kosusu("H1", "C1") as tutamak:
            tutamak.sonuc_bildir("TEST")
    finally:
        sozluk["ONAY_KAYDI"] = once
    assert not sahte.exists(), "kayit sahte yola yazilmamali"
    metin = kayit.read_text(encoding="utf-8")
    assert "H1" in metin and "C1" in metin and "BITTI" in metin, metin


def test_split_yukleme_aninda_sabitlenen_yol_denetimi_yerinde(kayit):
    """Ikinci katman kaldirilmadi: `split` yolu yukleme aninda sabitler ve farki denetler.

    Madde 5 sozluk yolunu etkisiz kildigi icin fark artik `config` uzerinden uretilemiyor; denetimin
    kendisi `_kayit_yolu`nun modul sabitiyle karsilastirilmasidir ve yerinde durur."""
    assert split._KAYIT_YOLU == config.ONAY_KAYDI or split._TEST_AYARI is not None
    assert "tek kaynak" in split.OnayKorumasi.__doc__


@pytest.mark.parametrize("ad", ["_AKTIF_KOSU", "_TEST_AYARI", "_KAYIT_YOLU", "_kayit_yolu", "_git", "_acik_kosu",
                                "_kosu_ortami", "kume_erisimi", "onay_baglami_dogrula", "aktif_onay_kosusu",
                                "kayittaki_kosular", "onay_kosusu"])
def test_korunan_adlar_disaridan_atanamaz(ad, kayit):
    once = getattr(split, ad)
    with pytest.raises(split.OnayKorumasi):
        setattr(split, ad, ("H1", "C1") if ad == "_AKTIF_KOSU" else (lambda *a, **k: None))
    with pytest.raises(split.OnayKorumasi):
        delattr(split, ad)
    assert getattr(split, ad) is once


def test_aktif_kosu_dogrudan_yazilamaz_ve_c1_acilmaz(kayit):
    with pytest.raises(split.OnayKorumasi):
        split._AKTIF_KOSU = ("H1", "C1")
    with pytest.raises(split.OnayGerekli):
        _c1_erisimi()
    assert kayit.read_text(encoding="utf-8") == "bas\n"


def test_modul_sozlugunden_kurulan_kosu_kayitsiz_erisim_acamaz(kayit):
    """Korumanin gormedigi `vars(split)` yolu: bellekte kurulan kosu, kayitta bu surece ait acik bir BASLADI
    satiri olmadan C1 acamaz."""
    import os

    sozluk = vars(split)
    try:
        sozluk["_AKTIF_KOSU"] = ("H1", "C1")
        with pytest.raises(split.OnayKorumasi):
            _c1_erisimi()
        sozluk["_AKTIF_KOSU"] = split._Kosu("H1", "C1", "sahte0000000", COMMIT, "x.py", "2026-01-01T00:00:00Z",
                                           os.getpid())
        with pytest.raises(split.OnayGerekli):
            _c1_erisimi()
        with pytest.raises(split.OnayGerekli):
            split.onay_baglami_dogrula("H1", "C1")
    finally:
        sozluk["_AKTIF_KOSU"] = None
    assert kayit.read_text(encoding="utf-8") == "bas\n"


def test_cokmus_kosunun_satiri_baska_surecte_kullanilamaz(kayit):
    """Surec oldurulurse BASLADI satiri asili kalir. Baska bir surecte o satirin kimligiyle bellekte kurulan kosu
    erisim acamaz (satirdaki surec numarasi bu surecinki degil)."""
    import os

    kimlik = "cokmus000000"
    kayit.write_text("bas\n| Tarih (UTC) | Kume | Cagiran betik | Commit | Not |\n|---|---|---|---|---|\n"
                     f"| 2026-01-01 00:00:00 | C1 | a.py | {COMMIT} (temiz) | hipotez=H1 kosu={kimlik} "
                     f"surec={os.getpid() + 1} durum=BASLADI baslangic=2026-01-01T00:00:00Z |\n", encoding="utf-8")
    sozluk = vars(split)
    try:
        sozluk["_AKTIF_KOSU"] = split._Kosu("H1", "C1", kimlik, COMMIT, "a.py", "2026-01-01T00:00:00Z", os.getpid())
        with pytest.raises(split.OnayGerekli):
            _c1_erisimi()
    finally:
        sozluk["_AKTIF_KOSU"] = None
    with pytest.raises(split.OnayTekrari):  # asili satir cifti harcamis sayar
        with split.onay_kosusu("H1", "C1"):
            pytest.fail("kosu acilmamali")


def test_kayit_kosu_sirasinda_degisirse_erisim_kapanir_ve_iz_kalir(kayit):
    with pytest.raises(split.OnayKorumasi):
        with split.onay_kosusu("H2", "C1"):
            assert _c1_erisimi()[0]
            kayit.write_text("bas\n", encoding="utf-8")  # BASLADI satiri silindi
            _c1_erisimi()
    satirlar = _satirlar(kayit)
    assert [s["durum"] for s in satirlar] == ["HATA"] and satirlar[0]["hata"] == "OnayGerekli"
    assert split.aktif_onay_kosusu() is None


def test_test_kaydi_yalnizca_pytest_testinde_ve_yalnizca_o_testte(tmp_path, monkeypatch):
    yol = gecici_kayit(tmp_path / "k.md")
    assert split._kayit_yolu() == yol
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/baska.py::test_baska (call)")
    assert split._kayit_yolu() == config.ONAY_KAYDI, "ayar kuran test bitince gecersizlesmeli"
    monkeypatch.delenv("PYTEST_CURRENT_TEST")
    with pytest.raises(split.OnayKorumasi):
        split._test_kaydi_ayarla(tmp_path / "k2.md")


def test_test_kaydi_olmadan_gercek_ortamda_kosu_acilmaz():
    """pytest'in ana betigi depo disinda (ya da agac kirli): gercek ortam denetimi kosuyu acmaz; gercek kayda
    hicbir sey yazilmaz."""
    once = config.ONAY_KAYDI.read_bytes()
    with pytest.raises(split.OnayOrtamiHatasi):
        with split.onay_kosusu("H1", "C1"):
            pytest.fail("kosu acilmamali")
    assert config.ONAY_KAYDI.read_bytes() == once


def test_onay_atlatma_deseni_analiz_kodunda_yok():
    # config.py kayit yolunun tanimini tasir (tek kaynak); izinli.
    assert [y for y in ihlaller(ONAY_ATLATMA_DESENI) if y != "config.py"] == []


@pytest.mark.parametrize("satir", [
    "from data import split\nsplit._AKTIF_KOSU = ('H1', 'C1')\n",
    "vars(split)['_AKTIF_KOSU'] = x\n",
    "split.__dict__['x'] = 1\n",
    "vars(config)['ONAY_KAYDI'] = p\n",
    "split._test_kaydi_ayarla(p)\n",
    "os.environ['PYTEST_CURRENT_TEST'] = 'x'\n",
    "open(config.ONAY_KAYDI, 'a')\n",
    "from onay_yardimcisi import kosu\n",
])
def test_onay_atlatma_deseni_yakalar(tmp_path, satir):
    (tmp_path / "study").mkdir()
    (tmp_path / "study" / "k.py").write_text(satir, encoding="utf-8")
    assert ihlaller(ONAY_ATLATMA_DESENI, kok=tmp_path) == ["study/k.py"]


# --- D-B2: temiz agac ---------------------------------------------------------------------------------


@pytest.mark.parametrize(("ortam", "desen"), [
    ({"durum": " M data/split.py\n"}, "temiz"),
    ({"durum": "?? yeni.py\n"}, "temiz"),
    ({"durum": None}, "durumu okunamadi"),
    ({"head": None}, "git"),
    ({"head": "bilinmiyor"}, "git"),
    ({"betik": None}, "etkilesimli"),
    ({"izleniyor": False}, "izlenen"),
])
def test_temiz_olmayan_ortamda_kosu_acilmaz(tmp_path, ortam, desen):
    yol = tmp_path / "k.md"
    yol.write_text("bas\n", encoding="utf-8")
    gecici_kayit(yol, **{"head": COMMIT, **ortam})
    with pytest.raises(split.OnayOrtamiHatasi, match=desen):
        with split.onay_kosusu("H1", "C1"):
            pytest.fail("kosu acilmamali")
    assert yol.read_text(encoding="utf-8") == "bas\n"
    assert split.aktif_onay_kosusu() is None


def test_ortam_karari_saftir():
    ortam = split.ortam_karari(COMMIT + "\n", "", "analysis/H2/onay.py", True)
    assert ortam == split.KosuOrtami(COMMIT, "analysis/H2/onay.py")
    with pytest.raises(split.OnayOrtamiHatasi):
        split.ortam_karari(COMMIT, "", "a|b.py", True)


def test_commit_hash_iki_satira_da_yazilir(kayit):
    with kosu("H3", "C2"):
        pass
    satirlar = _satirlar(kayit)
    assert [s["commit"] for s in satirlar] == [COMMIT, COMMIT]
    assert all(s["betik"] == "tests/onay_testi.py" for s in satirlar)


# --- D-B3: sonuc ve hata kaydi, tek atis --------------------------------------------------------------

ISO = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


def test_sonuc_kayda_yazilir(kayit):
    with split.onay_kosusu("H2", "C1") as k:
        assert _c1_erisimi()[0]
        k.sonuc_bildir("YETERSIZ GUC")
    bas, son = _satirlar(kayit)
    assert (bas["hipotez"], bas["kume"], bas["durum"]) == ("H2", "C1", "BASLADI")
    assert (son["hipotez"], son["kume"], son["durum"], son["sonuc"]) == ("H2", "C1", "BITTI", "YETERSIZ GUC")
    assert son["kosu"] == bas["kosu"] == k.kimlik and son["commit"] == COMMIT
    assert ISO.fullmatch(son["baslangic"]) and ISO.fullmatch(son["bitis"])
    assert son["baslangic"] == bas["baslangic"] <= son["bitis"]
    assert split.aktif_onay_kosusu() is None


def test_hata_ile_biten_kosu_kayda_gecer(kayit):
    with pytest.raises(ZeroDivisionError):
        with split.onay_kosusu("H1", "C2"):
            1 / 0
    bas, son = _satirlar(kayit)
    assert bas["durum"] == "BASLADI"
    assert (son["durum"], son["hata"], son["hipotez"], son["kume"]) == ("HATA", "ZeroDivisionError", "H1", "C2")
    assert ISO.fullmatch(son["baslangic"]) and ISO.fullmatch(son["bitis"]) and "sonuc" not in son
    with pytest.raises(split.OnayTekrari):
        with split.onay_kosusu("H1", "C2"):
            pytest.fail("hata ile biten kosunun cifti de harcanmistir")


def test_kesinti_ile_biten_kosu_kayda_gecer(kayit):
    with pytest.raises(KeyboardInterrupt):
        with split.onay_kosusu("H1", "C1"):
            raise KeyboardInterrupt
    assert [(s["durum"], s.get("hata")) for s in _satirlar(kayit)] == [("BASLADI", None),
                                                                        ("HATA", "KeyboardInterrupt")]


def test_sonuc_bildirilmeyen_kosu_hata_olarak_kayda_gecer(kayit):
    with pytest.raises(split.OnaySonucuYok):
        with split.onay_kosusu("H3", "C1"):
            pass
    assert [(s["durum"], s.get("hata")) for s in _satirlar(kayit)] == [("BASLADI", None), ("HATA", "OnaySonucuYok")]


@pytest.mark.parametrize("ilk", ["BITTI", "HATA", "BASLADI"])
def test_ikinci_kosu_reddedilir(kayit, ilk):
    if ilk == "BITTI":
        with kosu("H2", "C2"):
            pass
    elif ilk == "HATA":
        with pytest.raises(RuntimeError):
            with split.onay_kosusu("H2", "C2"):
                raise RuntimeError("deneme")
    else:  # yarida kalan kosu: yalnizca BASLADI satiri
        kayit.write_text(kayit.read_text(encoding="utf-8") + "| Tarih (UTC) | Kume | Cagiran betik | Commit | Not |\n"
                         f"|---|---|---|---|---|\n| 2026-01-01 00:00:00 | C2 | a.py | {COMMIT} (temiz) | "
                         "hipotez=H2 kosu=yarim0000000 surec=1 durum=BASLADI baslangic=2026-01-01T00:00:00Z |\n",
                         encoding="utf-8")
    once = kayit.read_bytes()
    with pytest.raises(split.OnayTekrari):
        with split.onay_kosusu("H2", "C2"):
            pytest.fail("ikinci kosu acilmamali")
    assert kayit.read_bytes() == once
    assert split.aktif_onay_kosusu() is None


@pytest.mark.parametrize("deger", ["", " KALDI", "KALDI ", "A  B", "A|B", "A\nB", 1, None, b"KALDI"])
def test_gecersiz_sonuc_reddedilir(kayit, deger):
    with split.onay_kosusu("H1", "C1") as k:
        with pytest.raises((TypeError, ValueError)):
            k.sonuc_bildir(deger)
        k.sonuc_bildir("KALDI")
        with pytest.raises(RuntimeError, match="zaten"):
            k.sonuc_bildir("GECTI")
    with pytest.raises(RuntimeError):
        k.sonuc_bildir("GECTI")
    assert _satirlar(kayit)[-1]["sonuc"] == "KALDI"


def test_asili_kilit_kosuyu_acmaz(kayit, monkeypatch):
    import time

    monkeypatch.setattr(time, "sleep", lambda _s: None)
    kilit = kayit.with_name("." + kayit.name + ".kilit")
    kilit.write_text("", encoding="utf-8")
    with pytest.raises(split.OnayKorumasi, match="kilid"):
        with split.onay_kosusu("H1", "C1"):
            pytest.fail("kosu acilmamali")
    assert kayit.read_text(encoding="utf-8") == "bas\n"


# --- D-C3: veri hatalari VeriHatasi ---------------------------------------------------------------------

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H = lambda n: pd.Timedelta(hours=n)  # noqa: E731


def test_cikis_bari_bos_ve_eksik_seri_veri_hatasi():
    b = T("2025-06-30 20:00")
    z = pd.date_range(T("2025-03-01"), b, freq="4h")
    giris = T("2025-03-10 08:00")
    with pytest.raises(pencere.VeriHatasi, match="bos"):
        pencere.cikis_bari(z[:0], giris, 18, config.BAR_4H, birincil_ufuk=18, donem_bitis=b, kume_bitis=None)
    hedef_acilis = pencere.cikis_hedefi(giris, 18, config.BAR_4H) - H(4)
    with pytest.raises(pencere.VeriHatasi, match="donem ici bar"):
        pencere.cikis_bari(z[z < hedef_acilis], giris, 18, config.BAR_4H, birincil_ufuk=18, donem_bitis=b,
                           kume_bitis=None)


def test_pozisyon_fundingi_seri_farki_veri_hatasi(monkeypatch):
    from kapi_yardimcisi import SENTETIK_VERI
    from test_ks_funding_onayli import FUND, _onayli

    p = _onayli()
    mumlar, _ = SENTETIK_VERI[p.sembol]
    monkeypatch.setitem(SENTETIK_VERI, p.sembol, (mumlar, FUND.assign(oran=2e-4)))
    with pytest.raises(pencere.VeriHatasi, match="ayni degil"):
        funding.pozisyon_fundingi(p)
