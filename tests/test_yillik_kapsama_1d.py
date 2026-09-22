"""`calistir.yillik_kapsama` 1d uygunlugu yalnizca gun acilisinda sorar (on-kayit §6
rev.8 "Donem uyeligi"; 1d barin zamani UTC gun acilisidir).

Madde 2'den sonra `pencere.donem_ici_mi` gun ortasi 1d zamanini reddeder; rev.8
oncesi kod 1d uygunlugunu her 4h anda soruyordu ve tam denetim kosusu tablo
asamasinda ValueError ile duruyordu (testlerde yakalanmamisti). Aga cikmaz.
"""

from __future__ import annotations

import importlib.util
import sys

import pandas as pd

import config
from data import eligibility
from data.donem import Donem

DIZIN = config.ANALIZ_DIZINI / "00_veri_denetimi"
sys.path.insert(0, str(DIZIN))
_spec = importlib.util.spec_from_file_location("_yk_calistir", DIZIN / "calistir.py")
calistir = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(calistir)

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731


def _detay():
    z = pd.date_range(T("2024-01-01 08:00"), T("2024-06-30 20:00"), freq="4h")
    mm = pd.DataFrame({"open_time": z, "quote_volume": 1e9})
    gunluk = pd.DataFrame({"open_time": pd.date_range(T("2024-01-02"), T("2024-06-30"), freq="1D"),
                           "quote_volume": 6e9})
    return {"sembol": "XUSDT", "_donemler": [Donem(z[0], z[-1], len(z), len(z))], "_mumlar": mm,
            "_gunluk": gunluk}


def _evren():
    return pd.DataFrame({"sembol": ["XUSDT"], "donem_id": [0], "donem_funding_yok": [False]})


def test_4h_seriyle_cokmez_ve_1d_yalniz_gun_acilisinda_sorulur(monkeypatch):
    gercek = eligibility.uygun_mu
    sorulan = []

    def casus(hacim, t, bar, **k):
        if bar == config.BAR_1D:
            sorulan.append(t)
        return gercek(hacim, t, bar, **k)

    monkeypatch.setattr(calistir.uyg, "uygun_mu", casus)
    tablo = calistir.yillik_kapsama([_detay()], _evren())
    assert sorulan and all(t == t.floor("D") for t in sorulan)
    satir = tablo.loc[tablo["yil"] == 2024].iloc[0]
    assert satir["veri_bulunan_sembol"] == 1
    assert satir["esik_10M_gecen"] == 1 and satir["esik_2M_gecen"] == 1
