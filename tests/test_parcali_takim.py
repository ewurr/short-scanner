"""`tools/parcali_takim.py`: bolme yontemi, ozet okuma ve cikis kodu. Pytest alt sureci baslatilmaz."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_YOL = Path(__file__).resolve().parents[1] / "tools" / "parcali_takim.py"
_OZELLIK = importlib.util.spec_from_file_location("parcali_takim", _YOL)
pt = importlib.util.module_from_spec(_OZELLIK)
_OZELLIK.loader.exec_module(pt)


def test_bolme_sirali_round_robin_ve_girdi_sirasindan_bagimsiz():
    dosyalar = [f"t{i}.py" for i in range(7)]
    beklenen = [["t0.py", "t4.py"], ["t1.py", "t5.py"], ["t2.py", "t6.py"], ["t3.py"]]
    assert pt.gruplara_bol(dosyalar, 4) == beklenen
    assert pt.gruplara_bol(list(reversed(dosyalar)), 4) == beklenen


def test_bolme_her_dosyayi_tam_bir_kez_kullanir():
    dosyalar = [f"t{i}.py" for i in range(23)]
    gruplar = pt.gruplara_bol(dosyalar, 4)
    assert sorted(d for g in gruplar for d in g) == sorted(dosyalar)
    assert max(map(len, gruplar)) - min(map(len, gruplar)) <= 1


def test_bolme_gecersiz_grup_sayisi():
    with pytest.raises(ValueError):
        pt.gruplara_bol(["a"], 0)


def test_ozet_butun_alanlari_okur():
    cikti = "...\n3 failed, 10 passed, 2 skipped, 4 xfailed, 1 xpassed, 1 error, 1 warning in 12.34s\n"
    assert pt.ozet_oku(cikti) == {"gecen": 10, "xfail": 4, "basarisiz": 4, "XPASS": 1, "atlanan": 2}


def test_strict_xpass_basarisizdan_ayrilir():
    cikti = "F.\n[XPASS(strict)] S-6: neden\nFAILED tests/a.py::t\n1 failed, 1 passed in 1.00s\n"
    assert pt.ozet_oku(cikti) == {"gecen": 1, "xfail": 0, "basarisiz": 0, "XPASS": 1, "atlanan": 0}


@pytest.mark.parametrize("cikti", ["", "ImportError: yok\n", "toplama yarida kesildi\n"])
def test_ozet_satiri_yoksa_none(cikti):
    assert pt.ozet_oku(cikti) is None


@pytest.mark.parametrize("sonuclar, kod", [
    ([{"gecen": 5, "xfail": 2, "basarisiz": 0, "XPASS": 0, "atlanan": 1}], 0),
    ([{"gecen": 5, "xfail": 0, "basarisiz": 1, "XPASS": 0, "atlanan": 0}], 1),
    ([{"gecen": 5, "xfail": 0, "basarisiz": 0, "XPASS": 1, "atlanan": 0}], 1),
    ([{"gecen": 5, "xfail": 0, "basarisiz": 0, "XPASS": 0, "atlanan": 0}, None], 1),
])
def test_cikis_kodu(sonuclar, kod):
    assert pt.cikis_kodu(sonuclar) == kod


def test_tablo_toplamlari():
    bir = {"gecen": 5, "xfail": 2, "basarisiz": 0, "XPASS": 0, "atlanan": 1}
    iki = {"gecen": 7, "xfail": 1, "basarisiz": 0, "XPASS": 0, "atlanan": 0}
    metin = pt.tablo([("0", 3, bir, 1.0), ("1", 2, iki, 2.5)])
    assert "| Toplam | 5 | 12 | 3 | 0 | 0 | 1 | 3.50 |" in metin
