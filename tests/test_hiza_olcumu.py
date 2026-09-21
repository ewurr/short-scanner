"""analysis/00_veri_denetimi/hiza_olcumu.py (denetci bulgusu D-C5). Saf sayim; aga cikmaz."""

from __future__ import annotations

import importlib.util
import sys

import pandas as pd

import config
from data import klines

DIZIN = config.ANALIZ_DIZINI / "00_veri_denetimi"
sys.path.insert(0, str(DIZIN))
_spec = importlib.util.spec_from_file_location("_hiza", DIZIN / "hiza_olcumu.py")
h = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h)

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731


def _gun(saatler, gun="2025-04-01"):
    return [T(gun) + pd.Timedelta(hours=x) for x in saatler]


def test_hizali_tam_gun_sayilmaz():
    s = h.hiza_say("X", pd.DatetimeIndex(_gun([0, 4, 8, 12, 16, 20])))
    assert (s["hizasiz_satir"], s["alti_satirli_gun"], s["alti_satirli_hizasiz_gun"]) == (0, 1, 0)


def test_alti_satirli_hizasiz_gun_sayilir_ve_gunluge_cevir_onu_tam_sayar():
    """20:00 bari eksik, yerine 13:00'te hizasiz bir satir var: 6 satir. Olcum bunu
    hizasiz gun sayar; bugunku `gunluge_cevir` ayni gunu tam gun olarak seriye alir
    (bulgunun kendisi)."""
    z = pd.DatetimeIndex(_gun([0, 4, 8, 12, 13, 16]))
    s = h.hiza_say("X", z)
    assert (s["hizasiz_satir"], s["alti_satirli_gun"], s["alti_satirli_hizasiz_gun"]) == (1, 1, 1)
    assert s["ilk_hizasiz_gun"] == T("2025-04-01")
    mumlar = pd.DataFrame({"open_time": z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0,
                           "close_time": z, "quote_volume": 1.0, "count": 1, "taker_buy_volume": 0.0,
                           "taker_buy_quote_volume": 0.0})
    assert len(klines.gunluge_cevir(mumlar)) == 1


def test_dakika_kaymasi_da_hizasiz():
    s = h.hiza_say("X", pd.DatetimeIndex(_gun([0, 4, 8, 12, 16]) + [T("2025-04-01 20:00:01")]))
    assert s["alti_satirli_hizasiz_gun"] == 1


def test_eksik_gun_alti_satirli_sayilmaz():
    s = h.hiza_say("X", pd.DatetimeIndex(_gun([0, 4, 8, 13])))
    assert (s["hizasiz_satir"], s["alti_satirli_gun"]) == (1, 0)
