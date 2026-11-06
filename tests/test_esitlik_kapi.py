"""Gercek veri esitlik betiginin (`analysis/00_veri_denetimi/esitlik_kapi.py`) kendi testi (performans 2a adim 3;
performans 2b-0 adim 3: D-B2, D-B3, D-C4, S-17, S-18, S-28, S-29).

Betik gercek veride kosar; burada kucuk sentetik girdiyle sinanir:
  - iki yol ayniyken uyusmazlik 0;
  - BILEREK bozulmus bir sonuc (onayli pozisyonun bir alani, ret gerekcesi sinifi, ret MESAJI, funding satirinin bir NaN
    konumu) uyusmazlik olarak zaman damgasiyla yakalanir;
  - iki tarafin ayni sinifla dusmesi uyusmazlik sayilmaz ama iki tarafta da "beklenmeyen hata" sayilir;
  - cikti satirlari yalnizca sayi, zaman damgasi ve sinif adi tasir; hata mesaji (deger icerebilir) disari cikmaz;
  - bar kipi acik parametredir, tohum ve kip satira yazilir; agac temizligi kesif kaydindan okunur.
Aga cikmaz.
"""

from __future__ import annotations

import ast
import contextlib
import dataclasses
import sys
import types

import pandas as pd
import pytest

from data import _skaler_referans as ref
from data import funding, pencere, pozisyon, sinyal
from esitlik_yardimcisi import dunya
from tarama_yardimcisi import KOK

sys.path.insert(0, str(KOK / "analysis" / "00_veri_denetimi"))
import esitlik_kapi as ek  # noqa: E402

BAS, BITIS = "2021-01-01", "2021-11-26 20:00"
SENTINEL = "DEGER=0.987654321"


def _kur(tohum, hipotez="H2"):
    kimlik, _ = dunya(tohum, BAS, BITIS)
    izgara = ek.bar_izgarasi(kimlik, hipotez)
    siralar = sorted(ek.tohumlu_siralar(len(izgara), 25, 5))
    return kimlik, izgara, siralar, dict(sinyal.izgara(hipotez)[0])


def _ozet(sayac):
    return sayac.karsilastirilan, len(sayac.uyusmayan), [z.isoformat() for z in sorted(sayac.uyusmayan)[:20]]


def _onayli_sira(kimlik, izgara, siralar, y, rol="K1"):
    for i in siralar:
        if isinstance(ek.karar(pozisyon, "H2", y, rol, izgara[i], kimlik, i), pozisyon.OnaylanmisPozisyon):
            return i
    pytest.fail("ornekte onayli pozisyon yok (dunya kurulusu)")


class _BozukReferans:
    """Referansi sarar; tek bir barda (ya da her barda) sonucu bilerek bozar."""

    def __init__(self, hedef, bozucu):
        self.hedef, self.bozucu = hedef, bozucu

    def olay_karari(self, t, *args, **kwargs):
        try:
            sonuc = ref.olay_karari(t, *args, **kwargs)
        except Exception as hata:  # noqa: BLE001
            sonuc = hata
        if self.hedef is None or t == self.hedef:
            sonuc = self.bozucu(sonuc)
        if isinstance(sonuc, BaseException):
            raise sonuc
        return sonuc

    def __getattr__(self, ad):
        return getattr(ref, ad)


class _BozukKapi(_BozukReferans):
    def olay_karari(self, t, *args, **kwargs):
        try:
            sonuc = pozisyon.olay_karari(t, *args, **kwargs)
        except Exception as hata:  # noqa: BLE001
            sonuc = hata
        if self.hedef is None or t == self.hedef:
            sonuc = self.bozucu(sonuc)
        if isinstance(sonuc, BaseException):
            raise sonuc
        return sonuc

    def __getattr__(self, ad):
        return getattr(pozisyon, ad)


# --- Esitlik ve bozulmus sonuc -----------------------------------------------------------------------------------

@pytest.mark.parametrize("rol", ("olay", "K1", "K2"))
def test_iki_yol_ayniyken_uyusmazlik_ve_beklenmeyen_hata_sifir(rol):
    kimlik, izgara, siralar, y = _kur(202)
    barlar = [izgara[i] for i in siralar]
    sayac = ek.karsilastir(barlar, siralar, "H2", y, rol, kimlik)
    assert _ozet(sayac) == (len(barlar), 0, [])
    assert (sayac.beklenmeyen_referans, sayac.beklenmeyen_yeni) == (0, 0)


def test_h1_olay_rolunde_capa_sabit_kuralla_verilir_ve_iki_yol_ayni():
    kimlik, izgara, siralar, y = _kur(203, "H1")
    barlar = [izgara[i] for i in siralar]
    assert len(ek.karsilastir(barlar, siralar, "H1", y, "olay", kimlik).uyusmayan) == 0
    assert ek.h1_capasi(izgara[30], 30) == izgara[30] - 7 * ek.H4   # 1 + 30 mod 12 = 7


@pytest.mark.parametrize("bozucu", [
    pytest.param(lambda p: dataclasses.replace(p, funding_toplami=p.funding_toplami + 1e-12), id="funding_toplami"),
    pytest.param(lambda p: dataclasses.replace(p, kuyruk_kismi=not p.kuyruk_kismi), id="bayrak"),
    pytest.param(lambda p: dataclasses.replace(p, gecersizlik_seviyesi=0.0), id="nan_konumu"),
    pytest.param(lambda p: pozisyon.UygunDegil("bozuk"), id="onay_yerine_ret"),
])
def test_bilerek_bozulan_onay_uyusmazlik_olarak_yakalanir(bozucu):
    kimlik, izgara, siralar, y = _kur(204)
    i = _onayli_sira(kimlik, izgara, siralar, y)
    barlar = [izgara[j] for j in siralar]
    sayac = ek.karsilastir(barlar, siralar, "H2", y, "K1", kimlik, ref=_BozukReferans(izgara[i], bozucu))
    assert _ozet(sayac) == (len(barlar), 1, [izgara[i].isoformat()])


def test_bilerek_degistirilen_ret_sinifi_yakalanir():
    kimlik, izgara, siralar, y = _kur(205)
    hedef = next(j for j in siralar if isinstance(ek.karar(pozisyon, "H2", y, "K1", izgara[j], kimlik, j),
                                                   pozisyon.SinyalPenceresiTamDegil))
    barlar = [izgara[j] for j in siralar]
    bozuk = _BozukReferans(izgara[hedef], lambda h: pozisyon.UygunDegil("bozuk"))
    assert _ozet(ek.karsilastir(barlar, siralar, "H2", y, "K1", kimlik, ref=bozuk))[1:] == (1, [izgara[hedef].isoformat()])


def test_ayni_sinifta_degistirilen_ret_mesaji_yakalanir():
    """D-B2: ret MESAJI da karsilastirilir (bellekte); ayni sinif, farkli mesaj uyusmazliktir."""
    kimlik, izgara, siralar, y = _kur(205)
    hedef = next(j for j in siralar if isinstance(ek.karar(pozisyon, "H2", y, "K1", izgara[j], kimlik, j),
                                                   pencere.OlayOlusmaz))
    barlar = [izgara[j] for j in siralar]
    bozuk = _BozukReferans(izgara[hedef], lambda h: type(h)(str(h) + " (bozuk)"))
    sayac = ek.karsilastir(barlar, siralar, "H2", y, "K1", kimlik, ref=bozuk)
    assert _ozet(sayac)[1:] == (1, [izgara[hedef].isoformat()])
    assert (sayac.beklenmeyen_referans, sayac.beklenmeyen_yeni) == (0, 0)   # OlayOlusmaz ailesi beklenen hatadir


def test_iki_tarafin_ayni_sinifla_dusmesi_beklenmeyen_hata_sayilir():
    """D-B2: iki yol ayni `TypeError` ile duserse bar uyusmaz sayilmaz, ama iki tarafta da beklenmeyen hata sayilir; "0
    uyusmayan" tek basina esitlik kaniti olamaz."""
    kimlik, izgara, siralar, y = _kur(208)
    barlar = [izgara[j] for j in siralar]
    hata = lambda s: TypeError(SENTINEL)  # noqa: E731
    sayac = ek.karsilastir(barlar, siralar, "H2", y, "K1", kimlik, kapi=_BozukKapi(None, hata),
                           ref=_BozukReferans(None, hata))
    assert len(sayac.uyusmayan) == 0
    assert sayac.beklenmeyen_referans == sayac.beklenmeyen_yeni == len(barlar)
    alanlar = sayac.alanlar(kapsam_yazilir=True)
    assert alanlar["kapsam_bar"] == 0
    assert alanlar["ilk_20_beklenmeyen"].split(";")[0] == f"referans:TypeError@{barlar[0].isoformat()}"
    assert SENTINEL not in repr(alanlar)


def test_yalnizca_bir_tarafin_beklenmeyen_hatasi_o_tarafa_sayilir():
    kimlik, izgara, siralar, y = _kur(209)
    barlar = [izgara[j] for j in siralar]
    sayac = ek.karsilastir(barlar, siralar, "H2", y, "K2", kimlik, kapi=_BozukKapi(barlar[3], lambda s: KeyError("x")))
    assert (len(sayac.uyusmayan), sayac.beklenmeyen_referans, sayac.beklenmeyen_yeni) == (1, 0, 1)


def test_kapsam_kontrol_rollerinde_sayilir_olay_rolunde_yazilmaz():
    """K1/K2: iki tarafin ayni onayli pozisyonu verdigi bar sayisi (kontrol rolleri kosula bakmaz). Olay rolunde onay
    sayisi olay sayisidir: `kapsam_bar` bos yazilir."""
    kimlik, izgara, siralar, y = _kur(204)
    barlar = [izgara[j] for j in siralar]
    k1 = ek.karsilastir(barlar, siralar, "H2", y, "K1", kimlik)
    assert k1.kapsam > 0 and k1.alanlar(kapsam_yazilir=True)["kapsam_bar"] == k1.kapsam
    olay = ek.karsilastir(barlar, siralar, "H2", y, "olay", kimlik)
    assert olay.kapsam == 0 and olay.alanlar(kapsam_yazilir=False)["kapsam_bar"] == ""


# --- Funding satiri ------------------------------------------------------------------------------------------

class _BozukFunding:
    """Kapinin funding modulunu sarar; tek bir planda satirin bir NaN konumunu ya da toplami bozar."""

    def __init__(self, hedef, alan):
        self.hedef, self.alan = hedef, alan

    def pozisyon_funding_ayrintisi(self, fr, plan):
        satir = funding.pozisyon_funding_ayrintisi(fr, plan).copy()
        if plan.sinyal_zamani == self.hedef and self.alan == "satir":
            satir["capa_aralik_saat"] = float("nan") if pd.notna(satir["capa_aralik_saat"]) else 8.0
        return satir

    def _plan_fundingi(self, fr, plan):
        toplam = funding._plan_fundingi(fr, plan)
        return toplam + 1.0 if (plan.sinyal_zamani == self.hedef and self.alan == "toplam") else toplam

    def _satirdan_toplam(self, fr, plan, tamlik):
        if plan.sinyal_zamani == self.hedef and self.alan == "beklenmeyen":
            raise ZeroDivisionError(SENTINEL)
        toplam = funding._satirdan_toplam(fr, plan, tamlik)
        return toplam + 1.0 if (plan.sinyal_zamani == self.hedef and self.alan == "toplu_toplam") else toplam

    def __getattr__(self, ad):
        return getattr(funding, ad)


@pytest.mark.parametrize("alan", ("satir", "toplam", "toplu_toplam", "beklenmeyen"))
def test_funding_satiri_ve_toplami_bozulunca_yakalanir(alan):
    kimlik, izgara, siralar, y = _kur(206)
    barlar = [izgara[j] for j in siralar]
    temiz = ek.funding_karsilastir(barlar, "H2", kimlik)
    assert (len(temiz.uyusmayan), temiz.beklenmeyen_referans, temiz.beklenmeyen_yeni) == (0, 0, 0)
    assert temiz.kapsam > 0
    hedef = izgara[_onayli_sira(kimlik, izgara, siralar, y)]
    sayac = ek.funding_karsilastir(barlar, "H2", kimlik, kapi_funding=_BozukFunding(hedef, alan))
    assert _ozet(sayac)[1:] == (1, [hedef.isoformat()])
    assert (sayac.beklenmeyen_referans, sayac.beklenmeyen_yeni) == (0, 1 if alan == "beklenmeyen" else 0)
    assert SENTINEL not in repr(sayac.alanlar(kapsam_yazilir=True))


# --- Sembol isi: cikti sozlesmesi --------------------------------------------------------------------------------

def _kucuk_sinirlar(monkeypatch):
    for ad, deger in (("SINIR_DONEM", 3), ("SINIR_KUME", 3), ("SINIR_RITIM", 2)):
        monkeypatch.setattr(ek, ad, deger)


def _ayar(bar="ornek", hipotezler=("H2", "H3"), roller=("olay", "K1", "K2")):
    return {"hipotezler": list(hipotezler), "yapilandirma": "ilk", "roller": list(roller), "funding_satiri": True,
            "bar": bar, "n": 5}


def test_sembol_isi_satirlari_yalnizca_sayi_zaman_damgasi_ve_sinif_adi_tasir(monkeypatch):
    kimlik, _ = dunya(207, BAS, BITIS)
    monkeypatch.setattr(ek, "_donemler", lambda sembol: [0])
    _kucuk_sinirlar(monkeypatch)
    satirlar = ek.sembol_isi(kimlik["sembol"], _ayar())
    assert all(set(s) == set(ek.SUTUNLAR) for s in satirlar)
    birimler = [s for s in satirlar if s["rol"] != "TOPLAM_SURE"]
    assert len(birimler) == 2 * 4
    for s in birimler:
        assert s["hata"] == "" and s["uyusmayan_bar"] == 0 and s["karsilastirilan_bar"] > 0
        assert s["beklenmeyen_hata_referans"] == 0 and s["beklenmeyen_hata_yeni"] == 0
        for alan in ek.SAYI_ALANLARI:
            assert type(s[alan]) is int
        assert s["bar_kumesi"] == "ornek_5+sinir"
        # Tohum yazilir ve birimin tohum kuralindan gelir (D-C4).
        assert s["tohum"] == str(ek.tohum(kimlik["sembol"], 0, s["hipotez"], s["yapilandirma"], s["rol"]))
        assert s["genel_tohum"] == ek.config.TOHUM
        if s["rol"] == "olay":
            # §14.46 (D-C2, D-C3, S-39): olay rolunde kapsam, birim suresi ve zaman damgalari yazilmaz.
            assert s["kapsam_bar"] == "" and s["sure_s"] == ""
            assert s["ilk_20_uyusmayan"] == "" and s["ilk_20_beklenmeyen"] == ""
            assert not any(isinstance(v, float) for v in s.values())
        else:
            assert type(s["kapsam_bar"]) is int
            assert s["sure_s"] == ""   # §14.46 (denetci kapanis D-B1): birim suresi hicbir rolde yazilmaz
            assert not any(isinstance(v, float) for v in s.values())


def test_tum_kipinde_butun_izgara_barlari_sorulur_ve_tohum_bos(monkeypatch):
    kimlik, _ = dunya(207, BAS, BITIS)
    monkeypatch.setattr(ek, "_donemler", lambda sembol: [0])
    asil = ek.bar_izgarasi
    monkeypatch.setattr(ek, "bar_izgarasi", lambda k, h: asil(k, h)[:7])
    satirlar = ek.sembol_isi(kimlik["sembol"], _ayar("tum", ("H2",), ("K1",)))
    birim = [s for s in satirlar if s["rol"] != "TOPLAM_SURE"]
    assert [(s["bar_kumesi"], s["tohum"], s["karsilastirilan_bar"]) for s in birim] == [("tum", "", 7), ("tum", "", 7)]


@pytest.mark.parametrize("kip", ("uyarlamali", "", None, "TUM"))
def test_bar_kipi_acik_parametredir_sureye_gore_secilmez(kip):
    """D-B3, D-C4: kalibrasyon ve uyarlamali kip kaldirildi; yalnizca `tum` ve `ornek`."""
    with pytest.raises(ValueError):
        ek.sembol_isi("X", _ayar(kip))
    assert not hasattr(ek, "KALIBRASYON")
    with pytest.raises(SystemExit):
        ek.main(["--isci", "1"])      # --bar zorunlu
    with pytest.raises(SystemExit):
        ek.main(["--bar", "uyarlamali"])


def test_birim_disi_hata_yalnizca_sinif_adiyla_tek_satir_olur(monkeypatch):
    """S-18: donem listesi gibi birim disi bir adim duserse hata mesaji disari cikmaz."""
    def bozuk(sembol):
        raise RuntimeError(SENTINEL)

    monkeypatch.setattr(ek, "_donemler", bozuk)
    satirlar = ek._guvenli_sembol_isi("X", _ayar())
    assert [(s["rol"], s["hata"]) for s in satirlar] == [("HATA", "RuntimeError")]
    assert SENTINEL not in repr(satirlar)


def test_main_hata_mesajini_yazdirmaz(monkeypatch, capsys):
    def bozuk(*a, **k):
        raise RuntimeError(SENTINEL)

    monkeypatch.setattr(ek, "kos", bozuk)
    assert ek.main(["--bar", "ornek", "--sembol", "YOK", "--etiket", "pytest_s18"]) == 3
    cikti = capsys.readouterr()
    assert SENTINEL not in cikti.out + cikti.err and "RuntimeError" in cikti.err


# --- Referans ve agac temizligi ---------------------------------------------------------------------------

def test_esitlik_betigi_bugunku_olay_karari_ve_referansi_karsilastirir(monkeypatch):
    """Varsayilan `ref` skaler referanstir (fonksiyon icinde ice aktarilir); kapi bugunku `data.pozisyon`."""
    assert ek.pozisyon_modulu is pozisyon and ek.funding_modulu is funding
    kimlik, izgara, siralar, y = _kur(202)
    barlar = [izgara[i] for i in siralar[:5]]

    def bozuk(*a, **k):
        raise pozisyon.UygunDegil("referans bozuldu")

    monkeypatch.setattr(ref, "olay_karari", bozuk)
    assert len(ek.karsilastir(barlar, siralar[:5], "H2", y, "K1", kimlik).uyusmayan) > 0


def test_esitlik_betiginin_modul_duzeyinde_referansi_veren_adi_yok():
    """S-17: bu modulu ice aktaran kod referansa adsiz ulasamaz (ne modul niteligi ne varsayilan arguman)."""
    for ad, deger in vars(ek).items():
        assert deger is not ref, ad
        for alt in (getattr(deger, "__defaults__", None) or ()), (getattr(deger, "__kwdefaults__", None) or {}).values():
            assert all(x is not ref for x in alt), ad
    agac = ast.parse((KOK / "analysis" / "00_veri_denetimi" / "esitlik_kapi.py").read_text(encoding="utf-8"))
    ust = [d for d in agac.body if isinstance(d, (ast.Import, ast.ImportFrom))]
    assert all("skaler_referans" not in ast.unparse(d) for d in ust)


def test_agac_temizligi_kesif_kaydindan_okunur_betik_kendisi_hesaplamaz(monkeypatch, tmp_path):
    """S-28, S-29, D-C7: ikinci uygulama yok; `KesifKaydi.agac_temiz` True degilse hicbir sembol kosmaz."""
    assert not hasattr(ek, "agac_temiz") and not hasattr(ek, "subprocess")
    cagrilan = []
    _sahte_kosu(monkeypatch, "a" * 40, cagrilan, agac_temiz=False)
    with pytest.raises(ek.AgacTemizDegil):
        ek.kos(["X"], {"bar": "ornek"}, 1, tmp_path)
    assert cagrilan == [] and list(tmp_path.iterdir()) == []
    _sahte_kosu(monkeypatch, "a" * 40, cagrilan, agac_temiz=None)
    with pytest.raises(ek.AgacTemizDegil):
        ek.kos(["X"], {"bar": "ornek"}, 1, None)
    assert cagrilan == []


class _SahteKayit:
    def __init__(self, head, agac_temiz=True):
        self.head, self.temiz = head, agac_temiz

    def alanlar(self):
        return {"head_commit": self.head, "agac_temiz": self.temiz}


def _sahte_kosu(monkeypatch, head, cagrilan, agac_temiz=True):
    @contextlib.contextmanager
    def kosu():
        yield _SahteKayit(head, agac_temiz)

    monkeypatch.setattr(ek, "split_modulu", types.SimpleNamespace(kesif_kosusu=kosu))

    def isi(s, ayar):
        cagrilan.append(s)
        return [{"sembol": s, "donem_no": 0, "rol": "K1", "karsilastirilan_bar": 1, "uyusmayan_bar": 0}]

    monkeypatch.setattr(ek, "sembol_isi", isi)


def test_ara_dizin_kesilen_kosuyu_kaldigi_yerden_surdurur(monkeypatch, tmp_path):
    cagrilan = []
    _sahte_kosu(monkeypatch, "a" * 40, cagrilan)
    ayar = {"bar": "ornek"}
    ek.kos(["X", "Y"], ayar, 1, tmp_path)
    assert cagrilan == ["X", "Y"]
    (tmp_path / "Y.json").unlink()                     # Y'de kesilmis gibi
    tablo, kayitlar = ek.kos(["X", "Y"], ayar, 1, tmp_path)
    assert cagrilan == ["X", "Y", "Y"] and sorted(tablo["sembol"]) == ["X", "Y"] and len(kayitlar) == 2
    _sahte_kosu(monkeypatch, "b" * 40, cagrilan)       # baska HEAD: birlestirilmez
    with pytest.raises(SystemExit):
        ek.kos(["X", "Y"], ayar, 1, tmp_path)
    _sahte_kosu(monkeypatch, "a" * 40, cagrilan)       # baska ayar: birlestirilmez
    with pytest.raises(SystemExit):
        ek.kos(["X", "Y"], {"bar": "tum"}, 1, tmp_path)


def test_ara_dizin_depo_icinde_olamaz():
    with pytest.raises(SystemExit):
        ek._ara_dizin_dogrula(KOK / "analysis" / "ara")


def test_tohum_kosu_sirasindan_bagimsiz_ve_parcalara_bagli():
    a = ek.tohum("SOLUSDT", 0, "H2", "phi=0.0003|k=3", "K1")
    assert a == ek.tohum("SOLUSDT", 0, "H2", "phi=0.0003|k=3", "K1")
    assert a != ek.tohum("SOLUSDT", 0, "H2", "phi=0.0003|k=3", "K2")
    assert ek.tohumlu_siralar(100, 10, a) == ek.tohumlu_siralar(100, 10, a)
