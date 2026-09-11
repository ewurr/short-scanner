"""Evren suzme testleri (on-kayit §2)."""

from __future__ import annotations

import config
from data import universe


DIZINLER = [
    "BTCUSDT",
    "ETHUSDT",
    "SRMUSDT",  # delist, evrende kalmali
    "BTCUSDT_210625",  # vadeli sozlesme
    "BTCBUSD_210129",  # vadeli + BUSD
    "1000BONKUSDC",  # USDC teminat
    "ADABUSD",  # BUSD teminat
    "AERGOUSDTSETTLED",  # delist sonrasi tekil kayit
    "BUSDT",  # BU coini - stablecoin DEGIL
    "TUSDT",  # Threshold coini - stablecoin DEGIL
    "USDCUSDT",  # stablecoin cifti - haric
    "BTCDOMUSDT",  # endeks - haric
]


def test_yalnizca_usdt_perpetual_kalir():
    adaylar = universe.usdt_perpetual_adaylari(DIZINLER)

    assert "BTCUSDT" in adaylar
    assert "SRMUSDT" in adaylar  # delist sozlesme evrende (on-kayit §2)
    assert "BTCUSDT_210625" not in adaylar
    assert "BTCBUSD_210129" not in adaylar
    assert "1000BONKUSDC" not in adaylar
    assert "ADABUSD" not in adaylar
    assert "AERGOUSDTSETTLED" not in adaylar


def test_tuzak_semboller_elenmez():
    """BUSDT (BU) ve TUSDT (Threshold) stablecoin degildir; desen eslestirmesi
    bunlari yanlislikla elerdi."""
    adaylar = universe.usdt_perpetual_adaylari(DIZINLER)
    assert "BUSDT" in adaylar
    assert "TUSDT" in adaylar


def test_haric_listesi_aciktir():
    assert universe.haric_mi("USDCUSDT") is True
    assert universe.haric_mi("BTCDOMUSDT") is True
    assert universe.haric_mi("DEFIUSDT") is True
    assert universe.haric_mi("BUSDT") is False
    assert universe.haric_mi("BTCUSDT") is False


def test_haric_listesi_disaridan_verilebilir():
    ozel = frozenset({"BTCUSDT"})
    assert universe.haric_mi("BTCUSDT", ozel) is True
    assert universe.haric_mi("USDCUSDT", ozel) is False


def test_cikti_sirali_ve_tekil():
    adaylar = universe.usdt_perpetual_adaylari(DIZINLER + ["BTCUSDT", "BTCUSDT"])
    assert adaylar == sorted(set(adaylar))


def test_on_kayit_haric_listesi_config_ile_ayni():
    assert "USDCUSDT" in config.HARIC_SEMBOLLER
    assert "BTCDOMUSDT" in config.HARIC_SEMBOLLER
    assert "DEFIUSDT" in config.HARIC_SEMBOLLER
