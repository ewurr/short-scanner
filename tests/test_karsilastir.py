"""analysis/00_veri_denetimi/karsilastir.py: onceki kosuyla cikti karsilastirmasi
(denetci bulgusu D-B1). Saf fonksiyon; aga ve git'e cikmaz."""

from __future__ import annotations

import importlib.util
import sys

import pytest

import config

DIZIN = config.ANALIZ_DIZINI / "00_veri_denetimi"
sys.path.insert(0, str(DIZIN))
_spec = importlib.util.spec_from_file_location("_karsilastir", DIZIN / "karsilastir.py")
k = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(k)


def test_ayni_metin_ayni():
    s = k.tablo_karsilastir("a,b\n1,2\n", "a,b\n1,2\n")
    assert s["durum"] == "ayni" and s["yalniz_onceki_satir"] == s["yalniz_yeni_satir"] == 0


def test_eklenen_sutun_ortak_satirlari_degistirmez():
    s = k.tablo_karsilastir("a,b\n1,2\n3,4\n", "a,b,c\n1,2,x\n3,4,y\n")
    assert s["durum"] == "farkli"
    assert s["eklenen_sutunlar"] == "c" and s["cikan_sutunlar"] == ""
    assert s["yalniz_onceki_satir"] == s["yalniz_yeni_satir"] == 0


def test_degisen_satir_sayilir():
    s = k.tablo_karsilastir("a\n1\n2\n2\n", "a\n1\n2\n5\n")
    assert (s["yalniz_onceki_satir"], s["yalniz_yeni_satir"]) == (1, 1)


def test_sira_farki_satir_farki_degildir_ama_ayni_da_degildir():
    s = k.tablo_karsilastir("a\n1\n2\n", "a\n2\n1\n")
    assert s["durum"] == "farkli" and s["yalniz_onceki_satir"] == s["yalniz_yeni_satir"] == 0


def test_yeni_ve_kaldirilan():
    assert k.tablo_karsilastir(None, "a\n1\n")["durum"] == "yeni"
    assert k.tablo_karsilastir("a\n1\n", None)["durum"] == "kaldirildi"
    with pytest.raises(ValueError):
        k.tablo_karsilastir(None, None)
