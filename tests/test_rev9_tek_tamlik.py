"""Rev.9 funding tamlik kuralinin tek uygulamasi `funding.funding_tamlik_ayrintisi`dir; olcum
betiklerinde ikinci bir kopyasi yoktur (Rev.9 uygulamasi, madde 6).

Rev.9 metni `rev9_hazirlik.py` (`capa_duzeltme_tamlik_ayrintisi`) ve `rev9_ritim.py` olcum
fonksiyonlarinin sayilariyla yazildi. Rev.9 koda gectikten sonra bu fonksiyonlar gercek kodu
cagirir. Tarihsel tanimlar (Rev.8 donmus kopyasi, birinci-dorduncu tur onerileri) yururlukte
degildir; adlari asagida acikca sayilir ve baska bir yerde capa aramasi yapan fonksiyon cikarsa
test kirilir. Aga cikmaz.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import sys
import textwrap

import pandas as pd

import config
from data import funding as funding_modulu
from tarama_yardimcisi import KOK

DIZIN = config.ANALIZ_DIZINI / "00_veri_denetimi"
sys.path.insert(0, str(DIZIN))


def _yukle(ad, dosya):
    spec = importlib.util.spec_from_file_location(ad, DIZIN / dosya)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


r9 = _yukle("_rev9_hazirlik_tek", "rev9_hazirlik.py")
rt = _yukle("_rev9_ritim_tek", "rev9_ritim.py")
uyg = _yukle("_rev9_uygulama_tek", "rev9_uygulama.py")

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
BAS = T("2025-01-01")
SERI = pd.DataFrame({"odeme_zamani": pd.date_range(T("2025-01-01"), T("2025-01-03"), freq="4h"),
                     "aralik_saat": 4.0})
GIRIS, SONLAR = [T("2025-01-01 04:00"), T("2025-01-01 08:00")], [T("2025-01-01 20:00"), T("2025-01-02 04:00")]


def _casus(monkeypatch):
    gercek = funding_modulu.funding_tamlik_ayrintisi
    cagri = []

    def casus(funding, girisler, sonlar, **kw):
        cagri.append(len(pd.DatetimeIndex(girisler)))
        sonuc = gercek(funding, girisler, sonlar, **kw)
        for k in (*funding_modulu.TAMLIK_KOSULLARI, "tam", "kuyruk_kismi", "tek_ritim"):
            sonuc[k] = ~sonuc[k]
        sonuc["capa_aralik_saat"] = 99.0
        return sonuc

    monkeypatch.setattr(funding_modulu, "funding_tamlik_ayrintisi", casus)
    return cagri


def test_capa_duzeltme_gercek_koddan_okur(monkeypatch):
    once = r9.capa_duzeltme_tamlik_ayrintisi(SERI, GIRIS, SONLAR, [BAS] * 2)
    assert once["tam"].all()
    cagri = _casus(monkeypatch)
    sonra = r9.capa_duzeltme_tamlik_ayrintisi(SERI, GIRIS, SONLAR, [BAS] * 2)
    assert cagri and not sonra["tam"].any()
    for k in ("capa_var", "aralik_gecerli", "zincir_tam", "son_tam", "kuyruk_kismi"):
        assert (sonra[k] == ~once[k]).all(), k


def test_ritim_etiketleri_gercek_koddan_okunur(monkeypatch):
    once = rt.pozisyon_ritmi(SERI, GIRIS, SONLAR, [BAS] * 2)
    assert (once["capa_aralik"] == 4.0).all() and once["tek_ritim"].all()
    cagri = _casus(monkeypatch)
    sonra = rt.pozisyon_ritmi(SERI, GIRIS, SONLAR, [BAS] * 2)
    assert cagri and (sonra["capa_aralik"] == 99.0).all() and not sonra["tek_ritim"].any()


def test_capa_duzeltme_vektorel_sonucu_gercek_kodla_ayni():
    """Kural sutunlari ve bayraklar gercek fonksiyonun ciktisiyla birebir ayni."""
    seri = SERI.loc[SERI["odeme_zamani"] != T("2025-01-01 12:00")].reset_index(drop=True)
    girisler = list(pd.date_range(T("2025-01-01"), periods=10, freq="4h"))
    sonlar = [g + pd.Timedelta(hours=h) for g, h in zip(girisler, [0, 4, 6, 8, 12, 16, 20, 24, 28, 30])]
    cd = r9.capa_duzeltme_tamlik_ayrintisi(seri, girisler, sonlar, [BAS] * 10)
    g = funding_modulu.funding_tamlik_ayrintisi(seri, girisler, sonlar, donem_baslari=[BAS] * 10)
    # `oran_gecerli` Rev.11'de (madde 8) eklendi ve Rev.9 doneminin olcum yeniden kurulumunda
    # yok; karsilastirma Rev.9'un kosullariyla yapilir. `tam` yine karsilastirilir: bu fiksturde
    # butun oranlar sonlu oldugu icin yeni kosul `tam`i degistirmez.
    rev9_kosullari = tuple(k for k in funding_modulu.TAMLIK_KOSULLARI if k != "oran_gecerli")
    assert "oran_gecerli" not in cd
    for k in (*rev9_kosullari, "tam", "kuyruk_kismi", "kuyruk_sifir", "son_esitlik_affi"):
        assert cd[k].tolist() == g[k].tolist(), k


def _cagrilar_ve_adlar(fonk):
    agac = ast.parse(textwrap.dedent(inspect.getsource(fonk)))
    cagri = {d.func.attr if isinstance(d.func, ast.Attribute) else getattr(d.func, "id", None)
             for d in ast.walk(agac) if isinstance(d, ast.Call)}
    return cagri


def test_rev9_olcum_fonksiyonlarinda_kural_yapi_taslari_yok():
    """Rev.9 olcum fonksiyonlari capa aramasi (searchsorted), cift kontrolu (maximum) ya da
    birikimli sayim (cumsum) yapmaz; gercek fonksiyonu cagirir."""
    for fonk in (r9.capa_duzeltme_tamlik_ayrintisi, r9._capa_duzeltme_tanilari, rt.pozisyon_ritmi,
                 rt.pozisyon_satirlari, uyg._ayrinti, uyg.baslangic_ve_ritim, uyg.donem_sonu_satirlari,
                 uyg.tk_satirlari):
        cagri = _cagrilar_ve_adlar(fonk)
        assert not cagri & {"searchsorted", "maximum", "cumsum", "_odemeler_tam_mi"}, fonk.__name__
    assert "funding_tamlik_ayrintisi" in _cagrilar_ve_adlar(r9.capa_duzeltme_tamlik_ayrintisi)
    assert "funding_tamlik_ayrintisi" in _cagrilar_ve_adlar(rt.pozisyon_ritmi)


# Capa aramasi yapan (girisi `ayni_an_sonu`/`ayni_an_basi` ile arayan) fonksiyonlar. Yururlukteki
# tek kural: data/funding.py. Digerleri tarihsel olcum tanimlari (yururlukte degil).
IZINLI_CAPA_ARAMASI = {
    ("data/funding.py", "funding_tamlik_ayrintisi"),
    ("analysis/00_veri_denetimi/rev8_tamlik.py", "rev8_tamlik_ayrintisi"),
    ("analysis/00_veri_denetimi/rev9_hazirlik.py", "oneri_tamlik_ayrintisi"),
    ("analysis/00_veri_denetimi/rev9_hazirlik.py", "son_hal_tamlik_ayrintisi"),
    ("analysis/00_veri_denetimi/rev9_hazirlik.py", "tahmin_yok_tamlik_ayrintisi"),
}


def test_capa_aramasi_yalnizca_gercek_kodda_ve_tarihsel_tanimlarda():
    bulunan = set()
    for yol in sorted(KOK.rglob("*.py")):
        goreli = yol.relative_to(KOK).as_posix()
        if goreli.startswith(("tests/", "cache/", ".claude/")) or "/cache/" in goreli:
            continue
        metin = yol.read_text(encoding="utf-8")
        for d in ast.walk(ast.parse(metin)):
            if isinstance(d, ast.FunctionDef):
                kaynak = ast.get_source_segment(metin, d) or ""
                if "ayni_an_sonu(girisler" in kaynak or "ayni_an_basi(girisler" in kaynak:
                    bulunan.add((goreli, d.name))
    assert bulunan == IZINLI_CAPA_ARAMASI


def test_tarihsel_rev8_kopyasi_karar_yoluna_girmez():
    """Donmus Rev.8 kopyasini yalnizca tarihsel olcum betikleri import eder; veri katmani ve
    gercek kod yolunu kullanan betikler (A1, rev9_uygulama, rev9_ritim) etmez."""
    for yol in list((KOK / "data").glob("*.py")) + [DIZIN / "a1_olcumu.py", DIZIN / "rev9_uygulama.py",
                                                    DIZIN / "rev9_ritim.py", DIZIN / "calistir.py"]:
        assert "rev8_tamlik" not in yol.read_text(encoding="utf-8"), yol.name
