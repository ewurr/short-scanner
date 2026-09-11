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


# --- Kapsam netlestirmesi ve karantina (on-kayit rev.2) ----------------------


def test_tradifi_kapsam_disi():
    """contractType = TRADIFI_PERPETUAL kripto varlik degildir (rev.2)."""
    g = universe.haric_gerekce("AMZNUSDT", config.TRADIFI_TIPI, "EQUITY")
    assert "TRADIFI_PERPETUAL" in g
    assert universe.haric_gerekce("BTCUSDT", config.PERPETUAL_TIPI, "COIN") == ""


def test_underlying_index_haric():
    g = universe.haric_gerekce("ALLUSDT", config.PERPETUAL_TIPI, config.ENDEKS_TIPI)
    assert "INDEX" in g


def test_delist_endeksler_kesin_listeden_gelir():
    """exchangeInfo'da olmayan delist endeksler icin sinif bilgisi None'dir."""
    for s in ("BLUEBIRDUSDT", "DOTECOUSDT", "FOOTBALLUSDT"):
        assert universe.haric_gerekce(s, None, None) != ""


def test_stablecoin_benzerleri_evrende_kalir():
    """Rev.2 tanimi: bagini koruyan token. FRAX/USTC/STBL/STABLE kalir."""
    for s in ("FRAXUSDT", "USTCUSDT", "STBLUSDT", "STABLEUSDT"):
        assert universe.haric_gerekce(s, config.PERPETUAL_TIPI, "COIN") == ""
        assert universe.haric_mi(s) is False


def test_usdcusdt_haric():
    assert universe.haric_gerekce("USDCUSDT", config.PERPETUAL_TIPI, "COIN") != ""


def test_karantina_kirpma_sembol_donemine_gore():
    """Sembolun ilk/son ayi disindaki SETTLED kayitlari karantina degildir."""
    aylar = ["2024-05", "2025-04", "2026-07"]
    kirpik = universe.karantina_kirp(aylar, "2024-09", "2026-06")
    assert kirpik == ["2025-04"]


def test_karantina_kirpma_bos_liste():
    assert universe.karantina_kirp([], "2024-01", "2025-01") == []
