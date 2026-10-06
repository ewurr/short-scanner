"""Onay kaydi kapanis turu: onbellege (`cache/`) dogrudan erisim taramasi (RESULTS §14.26, madde 3)."""

from __future__ import annotations

import pytest

from tarama_yardimcisi import ONBELLEK_DESENI, ONBELLEK_UZANTILARI, ihlaller


def test_analiz_kodunda_onbellege_dogrudan_erisim_yok():
    # config.py onbellek dizininin tanimini tasir (tek kaynak); izinli.
    assert [y for y in ihlaller(ONBELLEK_DESENI, uzantilar=ONBELLEK_UZANTILARI) if y != "config.py"] == []


@pytest.mark.parametrize(("ad", "metin"), [
    ("k.py", "pd.read_parquet('cache/klines/4h/BTCUSDT.parquet')\n"),
    ("k.py", 'yol = KOK / "cache" / "funding"\n'),
    ("k.py", "p = config.ONBELLEK_DIZINI / 'x'\n"),
    ("k.py", r"open('D:\Projeler\short_scanner\cache\a.parquet')" + "\n"),
    ("k.ipynb", '{"cells": [{"source": ["pd.read_parquet(\\"cache/klines/x.parquet\\")"]}]}\n'),
    # Kapanisin son turu: onbellek yardimcilari ve onay verisi izni.
    ("k.py", "from data import binance_vision as bv\n"),
    ("k.py", "from data.klines import bv\ndf = bv.onbellekten_oku(p)\n"),
    ("k.py", "with bv.onay_verisi_izni('x'):\n    pass\n"),
    ("k.py", "bv._IZIN['sayac'] = 1\n"),
    ("k.py", "govde = zip_indir(anahtar)\n"),
    ("k.pyw", "df = pd.read_parquet(p)\n"),
    # Kapanis (OK4 D-B1): izin alt sureclere ortam degiskeniyle tasiniyor; degiskeni analiz kodu ayarlayamaz.
    ("k.py", 'os.environ["SHORT_LAB_ONAY_VERISI_IZNI"] = str(os.getpid())\n'),
    ("k.py", "os.environ[bv._IZIN_ORTAM_ADI] = str(os.getpid())\n"),
    ("k.py", "bv._izni_devral()\n"),
    ("k.py", "bv._DEVRALINAN_IZIN['var'] = True\n"),
])
def test_onbellek_deseni_yakalar(tmp_path, ad, metin):
    (tmp_path / "study").mkdir()
    (tmp_path / "study" / ad).write_text(metin, encoding="utf-8")
    assert ihlaller(ONBELLEK_DESENI, kok=tmp_path, uzantilar=ONBELLEK_UZANTILARI) == [f"study/{ad}"]


@pytest.mark.parametrize("metin", ["onbellek_kullan = True\n", "# cache'lenmis sonuc yok\n", "cached = 1\n"])
def test_onbellek_deseni_mesru_metni_yakalamaz(tmp_path, metin):
    (tmp_path / "study").mkdir()
    (tmp_path / "study" / "k.py").write_text(metin, encoding="utf-8")
    assert ihlaller(ONBELLEK_DESENI, kok=tmp_path, uzantilar=ONBELLEK_UZANTILARI) == []
