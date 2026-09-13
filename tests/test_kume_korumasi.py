"""Yukleyicilerde kume korumasi (CLAUDE.md §3.2-3.3, denetci bulgusu B5).

`klines.mumlari_yukle` ve `funding.funding_yukle`, `split.yukle` ile ayni kapidan
gecer: kume zorunlu, C1/C2 icin onay=True sart, onayli cagri kaydedilir,
onaysiz cagri kayda yazmadan reddedilir, yanlis grup bos doner, veri kume
araligina kesilir. Korumasiz `ham_*` yukleyiciler yalnizca veri katmani ve F1
kapsama denetimi icindir.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pandas as pd
import pytest

import config
from data import funding, klines, split

KOK = Path(__file__).resolve().parents[1]


@pytest.fixture
def tablo():
    return pd.DataFrame(
        {"sembol": ["AAUSDT", "BBUSDT"], "varlik_anahtari": ["AAUSDT", "BBUSDT"], "grup": ["A", "B"]}
    )


@pytest.fixture
def kayit(tmp_path, monkeypatch):
    yol = tmp_path / "ONAY_KAYDI.md"
    yol.write_text("bas\n", encoding="utf-8")
    monkeypatch.setattr(config, "ONAY_KAYDI", yol)
    return yol


@pytest.fixture
def sahte_ham(monkeypatch):
    """KESIF/C2 sinirini kapsayan sahte ham veri; ag kullanilmaz."""

    def mumlar(sembol, bar=config.BAR_4H, yenile=False):
        zaman = pd.date_range("2025-08-25", "2025-09-10", freq="4h", tz="UTC")
        cerceve = pd.DataFrame(
            {
                "open_time": zaman, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
                "volume": 1.0, "close_time": zaman, "quote_volume": 1.0, "count": 1,
                "taker_buy_volume": 1.0, "taker_buy_quote_volume": 1.0,
            }
        )
        return klines.gunluge_cevir(cerceve) if bar == config.BAR_1D else cerceve

    def fund(sembol, yenile=False):
        zaman = pd.date_range("2025-08-25", "2025-09-10", freq="8h", tz="UTC")
        return pd.DataFrame({"odeme_zamani": zaman, "aralik_saat": 8, "oran": 1e-4, "oran_8h": 1e-4})

    monkeypatch.setattr(klines, "ham_mumlari_yukle", mumlar)
    monkeypatch.setattr(funding, "ham_funding_yukle", fund)


# --- Kume zorunlu ------------------------------------------------------------


@pytest.mark.parametrize("fonksiyon", [klines.mumlari_yukle, funding.funding_yukle])
def test_kume_parametresinin_varsayilani_yok(fonksiyon):
    assert inspect.signature(fonksiyon).parameters["kume"].default is inspect.Parameter.empty


def test_kumesiz_cagri_hata_verir():
    with pytest.raises(TypeError):
        klines.mumlari_yukle("AAUSDT", config.BAR_4H)
    with pytest.raises(TypeError):
        funding.funding_yukle("AAUSDT")


@pytest.mark.parametrize(
    "cagri",
    [
        lambda t: klines.mumlari_yukle("AAUSDT", config.BAR_4H, "C3", split=t),
        lambda t: funding.funding_yukle("AAUSDT", "C3", split=t),
    ],
)
def test_bilinmeyen_kume_reddedilir(cagri, tablo):
    with pytest.raises(ValueError):
        cagri(tablo)


def test_split_disindaki_sembol_reddedilir(tablo, sahte_ham):
    with pytest.raises(KeyError):
        funding.funding_yukle("ZZUSDT", "KESIF", split=tablo)


# --- Mumlar ------------------------------------------------------------------


def test_mum_kesif_a_grubu_kume_araligina_kesilir(tablo, sahte_ham):
    bas, son = split.kume_araligi("KESIF")
    mumlar = klines.mumlari_yukle("AAUSDT", config.BAR_4H, "KESIF", split=tablo)
    assert not mumlar.empty
    assert mumlar["open_time"].min() >= bas
    assert mumlar["open_time"].max() <= son
    assert (mumlar["open_time"] < pd.Timestamp("2025-09-01", tz="UTC")).all()


def test_mum_kesif_b_grubu_bos_doner(tablo, sahte_ham):
    assert klines.mumlari_yukle("BBUSDT", config.BAR_4H, "KESIF", split=tablo).empty


def test_gunluk_mum_da_kume_araligina_kesilir(tablo, sahte_ham):
    _, son = split.kume_araligi("KESIF")
    gunluk = klines.mumlari_yukle("AAUSDT", config.BAR_1D, "KESIF", split=tablo)
    assert not gunluk.empty
    assert gunluk["open_time"].max() <= son


@pytest.mark.parametrize("kume", ["C1", "C2"])
def test_mum_onay_kumesi_onaysiz_reddedilir_kayit_yazilmaz(kume, tablo, sahte_ham, kayit):
    with pytest.raises(PermissionError):
        klines.mumlari_yukle("BBUSDT", config.BAR_4H, kume, split=tablo)
    assert kayit.read_text(encoding="utf-8") == "bas\n"


def test_mum_onayli_cagri_kaydedilir(tablo, sahte_ham, kayit):
    klines.mumlari_yukle("BBUSDT", config.BAR_4H, "C1", onay=True, split=tablo)
    metin = kayit.read_text(encoding="utf-8")
    assert metin.startswith("bas\n")
    assert "| C1 |" in metin and "BBUSDT" in metin


def test_mum_c2_donemi_c2_araligina_kesilir(tablo, sahte_ham, kayit):
    bas, _ = split.kume_araligi("C2")
    mumlar = klines.mumlari_yukle("AAUSDT", config.BAR_4H, "C2", onay=True, split=tablo)
    assert mumlar["open_time"].min() >= bas


# --- Funding -----------------------------------------------------------------


def test_funding_kesif_a_grubu_kume_araligina_kesilir(tablo, sahte_ham):
    bas, son = split.kume_araligi("KESIF")
    fund = funding.funding_yukle("AAUSDT", "KESIF", split=tablo)
    assert not fund.empty
    assert fund["odeme_zamani"].min() >= bas
    assert fund["odeme_zamani"].max() <= son


def test_funding_kesif_b_grubu_bos_doner(tablo, sahte_ham):
    fund = funding.funding_yukle("BBUSDT", "KESIF", split=tablo)
    assert fund.empty
    assert list(fund.columns) == funding.FUNDING_CIKTI_SUTUNLARI


@pytest.mark.parametrize("kume", ["C1", "C2"])
def test_funding_onay_kumesi_onaysiz_reddedilir_kayit_yazilmaz(kume, tablo, sahte_ham, kayit):
    with pytest.raises(PermissionError):
        funding.funding_yukle("BBUSDT", kume, split=tablo)
    assert kayit.read_text(encoding="utf-8") == "bas\n"


def test_funding_onayli_cagri_kaynagiyla_kaydedilir(tablo, sahte_ham, kayit):
    funding.funding_yukle("BBUSDT", "C1", onay=True, split=tablo)
    metin = kayit.read_text(encoding="utf-8")
    assert metin.startswith("bas\n")
    assert "| C1 |" in metin and "BBUSDT" in metin and "kaynak=funding" in metin


def test_funding_yanlis_gruba_onayli_uzanma_da_kaydedilir(tablo, sahte_ham, kayit):
    """split.yukle ile ayni: grup uymasa bile onay verisine uzanma iz birakir."""
    fund = funding.funding_yukle("AAUSDT", "C1", onay=True, split=tablo)
    assert fund.empty
    assert "AAUSDT" in kayit.read_text(encoding="utf-8")


def test_funding_c2_donemi_c2_araligina_kesilir(tablo, sahte_ham, kayit):
    bas, _ = split.kume_araligi("C2")
    fund = funding.funding_yukle("BBUSDT", "C2", onay=True, split=tablo)
    assert not fund.empty
    assert fund["odeme_zamani"].min() >= bas


# --- Ortak kapi ve ham yukleyici disiplini -----------------------------------


def test_kume_erisimi_ortak_kapidir(tablo):
    izinli, bas, son = split.kume_erisimi("AAUSDT", "KESIF", split=tablo)
    assert izinli is True
    assert (bas, son) == split.kume_araligi("KESIF")
    assert split.kume_erisimi("BBUSDT", "KESIF", split=tablo)[0] is False


def test_analiz_kodu_ham_yukleyici_cagirmaz():
    """Korumasiz ham yukleyiciler yalnizca data/ ve F1 kapsama denetiminde kullanilir.

    events/, study/ ve diger analizler (F2 ve sonrasi) bunlari cagirirsa kume
    korumasi sessizce atlanir; bu test onu yakalar.
    """
    izinli = {KOK / "data", KOK / "tests", KOK / "analysis" / "00_veri_denetimi", KOK / ".claude"}
    desen = re.compile(r"\bham_(mumlari|funding)_yukle\b")
    ihlaller = []
    for yol in KOK.rglob("*.py"):
        if any(p in izinli for p in yol.parents) or "cache" in yol.parts:
            continue
        if desen.search(yol.read_text(encoding="utf-8", errors="replace")):
            ihlaller.append(str(yol.relative_to(KOK)))
    assert ihlaller == []
