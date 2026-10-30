"""Test ortak yardimcilari. Hicbir test aga cikmaz (CLAUDE.md §5)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def pytest_addoption(parser):
    parser.addoption("--ag", action="store_true", default=False,
                     help="`@pytest.mark.ag` testlerini de kosar; bu testler aga cikar.")


def pytest_configure(config):
    config.addinivalue_line("markers", "ag: aga cikar; yalnizca `--ag` ile kosulur, varsayilan `pytest -q` agsizdir.")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--ag"):
        return
    atla = pytest.mark.skip(reason="aga cikar; `--ag` ile kosulur")
    for oge in items:
        if oge.get_closest_marker("ag"):
            oge.add_marker(atla)


@pytest.fixture(autouse=True)
def ag_kapali(monkeypatch, request):
    """Testler sirasinda her HTTP cagrisini hata firlatacak sekilde kapatir (`ag` isaretli testler haric)."""
    import requests

    if request.node.get_closest_marker("ag"):
        return

    def yasak(*_args, **_kwargs):
        raise AssertionError("Testler aga cikamaz (CLAUDE.md §5).")

    monkeypatch.setattr(requests.Session, "get", yasak)
    monkeypatch.setattr(requests, "get", yasak)


@pytest.fixture(autouse=True)
def bellek_temiz():
    """Bellek onbellegi testler arasinda sizmaz (RESULTS §14.40)."""
    from data import kume_bellegi

    kume_bellegi.temizle()


@pytest.fixture(autouse=True)
def sentetik_donem_kayitlari(monkeypatch):
    """Tek karar noktasi donem sinirlarini evren tablosundan okur (kapi sertlestirme turu). Sentetik seri
    kullanan testlerin donemleri `kapi_yardimcisi.donem` ile kaydedilir; burada gercek kayitlara eklenir."""
    from data import pozisyon
    from kapi_yardimcisi import birlesik_kayitlar

    monkeypatch.setattr(pozisyon, "_kayitlar", birlesik_kayitlar(pozisyon._kayitlar))
    # Kapi sertlestirme turu 2: kapi veriyi kendisi yukler; sentetik semboller `kapi_yardimcisi.veri` kaydindan.
    from kapi_yardimcisi import birlesik_veri_yukle

    monkeypatch.setattr(pozisyon, "_veri_yukle", birlesik_veri_yukle(pozisyon._veri_yukle))


def sahte_4h(bas: str, bar_sayisi: int, hacim: float = 1_000_000.0) -> pd.DataFrame:
    """Duzenli 4h mum cercevesi uretir. Fiyatlar sabittir; fiyat davranisi test
    edilmez, yalnizca zaman izgarasi ve hacim mantigi test edilir."""
    zaman = pd.date_range(bas, periods=bar_sayisi, freq="4h", tz="UTC")
    return pd.DataFrame(
        {
            "open_time": zaman,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 10.0,
            "close_time": zaman + pd.Timedelta(hours=4) - pd.Timedelta(milliseconds=1),
            "quote_volume": hacim,
            "count": 5,
            "taker_buy_volume": 5.0,
            "taker_buy_quote_volume": hacim / 2,
        }
    )
