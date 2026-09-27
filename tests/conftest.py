"""Test ortak yardimcilari. Hicbir test aga cikmaz (CLAUDE.md §5)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def ag_kapali(monkeypatch):
    """Testler sirasinda her HTTP cagrisini hata firlatacak sekilde kapatir."""
    import requests

    def yasak(*_args, **_kwargs):
        raise AssertionError("Testler aga cikamaz (CLAUDE.md §5).")

    monkeypatch.setattr(requests.Session, "get", yasak)
    monkeypatch.setattr(requests, "get", yasak)


@pytest.fixture(autouse=True)
def sentetik_donem_kayitlari(monkeypatch):
    """Tek karar noktasi donem sinirlarini evren tablosundan okur (kapi sertlestirme turu). Sentetik seri
    kullanan testlerin donemleri `kapi_yardimcisi.donem` ile kaydedilir; burada gercek kayitlara eklenir."""
    from data import pozisyon
    from kapi_yardimcisi import birlesik_kayitlar

    monkeypatch.setattr(pozisyon, "_kayitlar", birlesik_kayitlar(pozisyon._kayitlar))


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
