"""Gercek veri esitlik betiginin (`analysis/00_veri_denetimi/esitlik_kapi.py`) kendi testi (performans 2a, adim 3).

Betik bir kez gercek veride kosar; burada kucuk sentetik girdiyle sinanir: iki yol ayniyken uyusmazlik 0, BILEREK
bozulmus bir sonuc (onayli pozisyonun bir alani, ret gerekcesi sinifi, funding satirinin bir NaN konumu) uyusmazlik
olarak zaman damgasiyla yakalanir. Cikti satirlari yalnizca sayi ve zaman damgasi tasir. Aga cikmaz.
"""

from __future__ import annotations

import dataclasses
import sys

import pandas as pd
import pytest

from data import _skaler_referans as ref
from data import funding, pozisyon, sinyal
from esitlik_yardimcisi import dunya, ornek_barlar
from tarama_yardimcisi import KOK

sys.path.insert(0, str(KOK / "analysis" / "00_veri_denetimi"))
import esitlik_kapi as ek  # noqa: E402

BAS, BITIS = "2021-01-01", "2021-11-26 20:00"


@pytest.fixture(scope="module")
def _tohum():
    return 201


def _kur(tohum, hipotez="H2"):
    kimlik, _ = dunya(tohum, BAS, BITIS)
    izgara = ek.bar_izgarasi(kimlik, hipotez)
    siralar = sorted(ek.tohumlu_siralar(len(izgara), 25, 5))
    return kimlik, izgara, siralar, dict(sinyal.izgara(hipotez)[0])


def _onayli_sira(kimlik, izgara, siralar, y, rol="K1"):
    for i in siralar:
        if isinstance(ek.karar(pozisyon, "H2", y, rol, izgara[i], kimlik, i), pozisyon.OnaylanmisPozisyon):
            return i
    pytest.fail("ornekte onayli pozisyon yok (dunya kurulusu)")


class _BozukReferans:
    """Referansi sarar; tek bir barda sonucu bilerek bozar."""

    def __init__(self, hedef, bozucu):
        self.hedef, self.bozucu = hedef, bozucu

    def olay_karari(self, t, *args, **kwargs):
        try:
            sonuc = ref.olay_karari(t, *args, **kwargs)
        except Exception as hata:  # noqa: BLE001
            sonuc = hata
        if t == self.hedef:
            sonuc = self.bozucu(sonuc)
        if isinstance(sonuc, BaseException):
            raise sonuc
        return sonuc

    def __getattr__(self, ad):
        return getattr(ref, ad)


@pytest.mark.parametrize("rol", ("olay", "K1", "K2"))
def test_iki_yol_ayniyken_uyusmazlik_sifir(rol):
    kimlik, izgara, siralar, y = _kur(202)
    barlar = [izgara[i] for i in siralar]
    n, u, ilk = ek.karsilastir(barlar, siralar, "H2", y, rol, kimlik)
    assert (n, u, ilk) == (len(barlar), 0, [])


def test_h1_olay_rolunde_capa_sabit_kuralla_verilir_ve_iki_yol_ayni():
    kimlik, izgara, siralar, y = _kur(203, "H1")
    barlar = [izgara[i] for i in siralar]
    assert ek.karsilastir(barlar, siralar, "H1", y, "olay", kimlik)[1] == 0
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
    n, u, ilk = ek.karsilastir(barlar, siralar, "H2", y, "K1", kimlik, ref=_BozukReferans(izgara[i], bozucu))
    assert (n, u, ilk) == (len(barlar), 1, [izgara[i].isoformat()])


def test_bilerek_degistirilen_ret_sinifi_yakalanir():
    kimlik, izgara, siralar, y = _kur(205)
    hedef = next(j for j in siralar if isinstance(ek.karar(pozisyon, "H2", y, "K1", izgara[j], kimlik, j),
                                                   pozisyon.SinyalPenceresiTamDegil))
    barlar = [izgara[j] for j in siralar]
    bozuk = _BozukReferans(izgara[hedef], lambda h: pozisyon.UygunDegil("bozuk"))
    assert ek.karsilastir(barlar, siralar, "H2", y, "K1", kimlik, ref=bozuk)[1:] == (1, [izgara[hedef].isoformat()])


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
        toplam = funding._satirdan_toplam(fr, plan, tamlik)
        return toplam + 1.0 if (plan.sinyal_zamani == self.hedef and self.alan == "toplu_toplam") else toplam

    def __getattr__(self, ad):
        return getattr(funding, ad)


@pytest.mark.parametrize("alan", ("satir", "toplam", "toplu_toplam"))
def test_funding_satiri_ve_toplami_bozulunca_yakalanir(alan):
    kimlik, izgara, siralar, y = _kur(206)
    barlar = [izgara[j] for j in siralar]
    assert ek.funding_karsilastir(barlar, "H2", kimlik)[1] == 0
    hedef = izgara[_onayli_sira(kimlik, izgara, siralar, y)]
    n, u, ilk = ek.funding_karsilastir(barlar, "H2", kimlik, kapi_funding=_BozukFunding(hedef, alan))
    assert (u, ilk) == (1, [hedef.isoformat()])


def test_sembol_isi_satirlari_yalnizca_sayi_ve_zaman_damgasi_tasir(monkeypatch):
    kimlik, _ = dunya(207, BAS, BITIS)
    monkeypatch.setattr(ek, "_donemler", lambda sembol: [0])
    # Sinir genislikleri kucultulur (sure); kural ayni kalir.
    monkeypatch.setattr(ek, "SINIR_DONEM", 3)
    monkeypatch.setattr(ek, "SINIR_KUME", 3)
    monkeypatch.setattr(ek, "SINIR_RITIM", 2)
    ayar = {"hipotezler": ["H2", "H3"], "yapilandirma": "ilk", "roller": ["olay", "K1", "K2"], "funding_satiri": True,
            "bar": "ornek", "n": 5, "sure_siniri_dk": 15.0}
    satirlar = ek.sembol_isi(kimlik["sembol"], ayar)
    assert all(set(s) == set(ek.SUTUNLAR) for s in satirlar)
    birimler = [s for s in satirlar if s["rol"] != "TOPLAM_SURE"]
    assert len(birimler) == 2 * 4
    for s in birimler:
        assert s["hata"] == "" and s["uyusmayan_bar"] == 0 and s["karsilastirilan_bar"] > 0
        assert isinstance(s["karsilastirilan_bar"], int) and isinstance(s["uyusmayan_bar"], int)
        assert s["bar_kumesi"] == "ornek_5+sinir"
        assert set(s) - {"sure_s"} == {k for k, v in s.items() if not isinstance(v, float)}


def test_tohum_kosu_sirasindan_bagimsiz_ve_parcalara_bagli():
    a = ek.tohum("SOLUSDT", 0, "H2", "phi=0.0003|k=3", "K1")
    assert a == ek.tohum("SOLUSDT", 0, "H2", "phi=0.0003|k=3", "K1")
    assert a != ek.tohum("SOLUSDT", 0, "H2", "phi=0.0003|k=3", "K2")
    assert ek.tohumlu_siralar(100, 10, a) == ek.tohumlu_siralar(100, 10, a)


def test_esitlik_betigi_bugunku_olay_karari_ve_referansi_karsilastirir():
    assert ek.pozisyon_modulu is pozisyon and ek.referans is ref and ek.funding_modulu is funding
