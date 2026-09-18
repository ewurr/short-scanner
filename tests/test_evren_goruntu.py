"""evren_kur sozlesme/dayanak tipini depodaki exchangeInfo goruntusunden okur
(denetci bulgusu D-B4).

Canli exchangeInfo zamanla degisir; evren tablosunun depodaki veriden yeniden
uretilebilmesi icin tip bilgisi goruntuden gelmelidir. Testler aga cikmaz.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

import config
from data import binance_vision as bv
from data import funding as funding_modulu
from data import klines as klines_modulu
from data import universe


def _goruntu_yaz(yol, semboller):
    ham = json.dumps({"serverTime": 1, "symbols": semboller})
    g = universe.exchange_info_anlik_goruntu(ham, pd.Timestamp("2026-09-18 11:31", tz="UTC"))
    yol.write_text(json.dumps(g), encoding="utf-8")


def _sembol(ad, tip, dayanak):
    return {"symbol": ad, "contractType": tip, "underlyingType": dayanak, "status": "TRADING",
            "deliveryDate": 4133404800000, "onboardDate": 1569398400000}


def test_anlik_siniflar_goruntuden_okunur(tmp_path):
    yol = tmp_path / "ei.json"
    _goruntu_yaz(yol, [_sembol("AUSDT", "PERPETUAL", "COIN"), _sembol("TUSDT", "TRADIFI_PERPETUAL", "EQUITY")])
    assert universe.exchange_info_anlik_siniflari(yol) == {
        "AUSDT": ("PERPETUAL", "COIN"), "TUSDT": ("TRADIFI_PERPETUAL", "EQUITY"),
    }


def test_evren_kur_canli_uc_noktaya_gitmez(tmp_path, monkeypatch):
    """Goruntu dosyasi yerindeyken evren_kur requests.get cagirmaz; tip goruntuden
    gelir, goruntude olmayan sembolun tipi bos kalir."""
    yol = tmp_path / "ei.json"
    _goruntu_yaz(yol, [_sembol("AUSDT", "PERPETUAL", "COIN"), _sembol("TUSDT", "TRADIFI_PERPETUAL", "EQUITY")])
    monkeypatch.setattr(config, "EXCHANGE_INFO_ANLIK", yol)

    def ag_yasak(*a, **k):
        raise AssertionError("evren_kur canli exchangeInfo'ya gitmemeli")

    monkeypatch.setattr(universe.requests, "get", ag_yasak)
    zamanlar = pd.date_range("2026-08-01", periods=12, freq="4h", tz="UTC")
    mumlar = pd.DataFrame({"open_time": zamanlar, "quote_volume": 1.0})
    fund = pd.DataFrame({"odeme_zamani": zamanlar[::2], "aralik_saat": 8, "oran": 0.0, "oran_8h": 0.0})
    monkeypatch.setattr(bv, "tum_sembol_dizinleri", lambda: ["AUSDT", "TUSDT", "YOKUSDT"])
    monkeypatch.setattr(bv, "mum_dosyalari", lambda s, bar: [f"{bv.MUM_ONEKI}/{s}/{s}-4h-2026-08.zip"])
    monkeypatch.setattr(bv, "funding_dosyalari", lambda s: [f"{bv.FUNDING_ONEKI}/{s}/{s}-fundingRate-2026-08.zip"])
    monkeypatch.setattr(klines_modulu, "ham_mumlari_yukle", lambda s, bar=config.BAR_4H, yenile=False: mumlar.copy())
    monkeypatch.setattr(funding_modulu, "ham_funding_yukle", lambda s, yenile=False: fund.copy())

    evren = universe.evren_kur().drop_duplicates("sembol").set_index("sembol")
    assert evren.at["AUSDT", "sozlesme_tipi"] == "PERPETUAL" and not evren.at["AUSDT", "haric"]
    assert evren.at["TUSDT", "sozlesme_tipi"] == "TRADIFI_PERPETUAL" and evren.at["TUSDT", "haric"]
    assert evren.at["YOKUSDT", "sozlesme_tipi"] is None


def test_goruntu_yoksa_evren_kur_sessizce_canliya_donmez(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "EXCHANGE_INFO_ANLIK", tmp_path / "yok.json")
    monkeypatch.setattr(bv, "tum_sembol_dizinleri", lambda: ["AUSDT"])
    with pytest.raises(FileNotFoundError):
        universe.evren_kur()
