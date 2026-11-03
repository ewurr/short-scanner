"""Analiz kodunda dogrudan ag erisimi taramasi (RESULTS §14.42; denetci D-C3, sizinti R3a). Aga cikilmaz."""

from __future__ import annotations

import pytest

from tarama_yardimcisi import ONBELLEK_DESENI, ONBELLEK_UZANTILARI, ihlaller


def _tara(tmp_path, metin, ad="k.py"):
    (tmp_path / "study").mkdir()
    (tmp_path / "study" / ad).write_text(metin, encoding="utf-8")
    return ihlaller(ONBELLEK_DESENI, kok=tmp_path, uzantilar=ONBELLEK_UZANTILARI)


@pytest.mark.parametrize("metin", [
    "import requests\n",
    "import os, requests\n",
    "from requests import get\n",
    "import urllib.request\n",
    "from urllib.request import urlopen\n",
    "import urllib3\n",
    "import socket\n",
    "from socket import create_connection\n",
    "import http.client\n",
    "from http.client import HTTPSConnection\n",
    "from http import client\n",
    "import aiohttp\n",
    "    import httpx\n",
    'URL = "https://example.org/x.csv"\n',
    "u = 'http://127.0.0.1:8000'\n",
    'u = "HTTPS://FAPI.BINANCE.COM/fapi/v1/klines"\n',
])
def test_ag_erisimi_yakalanir(tmp_path, metin):
    assert _tara(tmp_path, metin) == ["study/k.py"]


def test_ipynb_icindeki_ag_erisimi_yakalanir(tmp_path):
    assert _tara(tmp_path, '{"cells": [{"source": ["import requests\\n"]}]}\n', ad="k.ipynb") == ["study/k.ipynb"]


@pytest.mark.parametrize("metin", [
    "from data import split, klines\n",
    "# istekler (requests) burada yok; yalnizca kapili yukleyici\n",
    "socket_sayisi = 3\n",
    "import httpserver_disi_modul\n",
    "from data.pencere import adim\n",
    "aciklama = 'http protokolu kullanilmaz'\n",
    'for paket in ("pandas", "numpy", "pyarrow", "requests"):\n',  # ortam kaydi: paket surumu (F1 betiklerindeki satir)
])
def test_mesru_metin_yakalanmaz(tmp_path, metin):
    assert _tara(tmp_path, metin) == []


def test_depodaki_analiz_kodu_temiz_config_ve_veri_katmani_muaf():
    """`data/` (veri katmani, `requests` kullanir) `IZINLI_ALTLAR`da; config.py depo taramasinda ayrica muaftir."""
    assert [y for y in ihlaller(ONBELLEK_DESENI, uzantilar=ONBELLEK_UZANTILARI) if y != "config.py"] == []


def test_mevcut_analiz_kodu_ag_desenine_takilmaz_f1_betikleri_dahil():
    """Yanlis pozitif denetimi: ag deseni `analysis/`, `events/`, `study/` altindaki mevcut kodda (muaf F1 betikleri
    `analysis/00_veri_denetimi` DAHIL) hicbir satira takilmaz."""
    ag_deseni = ONBELLEK_DESENI[ONBELLEK_DESENI.index("|(?m:(?:^|") + 1:]
    assert ag_deseni.startswith("(?m:")
    bulunan = ihlaller(ag_deseni, izinli_altlar=("data", "tests", ".claude"), uzantilar=ONBELLEK_UZANTILARI)
    assert [y for y in bulunan if y.split("/")[0] in ("analysis", "events", "study")] == []
