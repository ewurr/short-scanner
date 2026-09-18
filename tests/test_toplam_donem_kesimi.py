"""Toplam donem kesimi: evren kurulumu ve F1 denetimi ayni siniri kullanir
(denetci bulgusu D-B3, on-kayit §2).

Bucket'a toplam donemden sonra (2026-09 ve sonrasi) eklenen aylar ne evren
tablosunun ay sinirlarini ve dosya sayilarini ne de donemleri degistirmeli.
Testler aga cikmaz; bucket, onbellek ve exchangeInfo sahte fonksiyonlarla
degistirilir.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import binance_vision as bv
from data import donem
from data import funding as funding_modulu
from data import klines as klines_modulu
from data import universe

ADIM = pd.Timedelta(hours=4)


def test_toplam_doneme_kes_uclar_dahil():
    cerceve = pd.DataFrame({"t": [
        pd.Timestamp("2019-12-31 20:00", tz="UTC"), pd.Timestamp(config.DONEM_BASI),
        pd.Timestamp(config.DONEM_SONU), pd.Timestamp("2026-09-01 00:00", tz="UTC"),
    ]})
    kesik = donem.toplam_doneme_kes(cerceve, "t")
    assert list(kesik["t"]) == [pd.Timestamp(config.DONEM_BASI), pd.Timestamp(config.DONEM_SONU)]


def test_toplam_doneme_kes_bos_cerceve():
    bos = pd.DataFrame(columns=["t"])
    assert donem.toplam_doneme_kes(bos, "t").empty


@pytest.mark.parametrize("ay,beklenen", [
    ("2019-12", False), ("2020-01", True), ("2026-08", True), ("2026-09", False),
])
def test_ay_toplam_donemde(ay, beklenen):
    assert donem.ay_toplam_donemde(ay) is beklenen


def test_denetim_ayni_kesim_fonksiyonunu_kullanir():
    import importlib.util

    yol = config.ANALIZ_DIZINI / "00_veri_denetimi" / "calistir.py"
    spec = importlib.util.spec_from_file_location("denetim_calistir", yol)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    assert modul._toplam_doneme_kes is donem.toplam_doneme_kes


def _anahtar(onek: str, sembol: str, ay: str) -> str:
    return f"{onek}/{sembol}/{sembol}-4h-{ay}.zip"


@pytest.fixture
def sahte_bucket(monkeypatch):
    """Tek sembol: 2026-08 son gun ve 2026-09 ilk gun gercek islem, bir de 2026-09 dosyasi."""
    sembol = "XUSDT"
    aylar = ["2026-08", "2026-09"]
    zamanlar = pd.date_range("2026-08-30 00:00", "2026-09-01 20:00", freq="4h", tz="UTC")
    mumlar = pd.DataFrame({"open_time": zamanlar, "quote_volume": 1.0})
    fund = pd.DataFrame({"odeme_zamani": pd.date_range("2026-08-30 00:00", "2026-09-01 16:00", freq="8h", tz="UTC"),
                         "aralik_saat": 8, "oran": 0.0, "oran_8h": 0.0})

    monkeypatch.setattr(bv, "tum_sembol_dizinleri", lambda: [sembol])
    monkeypatch.setattr(bv, "mum_dosyalari", lambda s, bar: [_anahtar(bv.MUM_ONEKI, s, a) for a in aylar])
    monkeypatch.setattr(bv, "funding_dosyalari", lambda s: [_anahtar(bv.FUNDING_ONEKI, s, a) for a in aylar])
    monkeypatch.setattr(klines_modulu, "ham_mumlari_yukle", lambda s, bar=config.BAR_4H, yenile=False: mumlar.copy())
    monkeypatch.setattr(funding_modulu, "ham_funding_yukle", lambda s, yenile=False: fund.copy())
    monkeypatch.setattr(universe, "exchange_info_anlik_siniflari",
                        lambda yol=None: {sembol: ("PERPETUAL", "COIN")})
    return sembol


def test_evren_kur_toplam_donem_sonrasini_kesmeli(sahte_bucket):
    evren = universe.evren_kur()
    satir = evren.loc[evren["sembol"] == sahte_bucket].iloc[0]
    assert satir["son_ay"] == "2026-08"
    assert satir["dosya_sayisi_4h"] == 1
    assert satir["funding_dosya_sayisi"] == 1
    # Donem, toplam donemin son barinda biter; 2026-09 barlari doneme girmez.
    assert satir["donem_bitis"] == pd.Timestamp("2026-08-31 20:00", tz="UTC")
    assert satir["donem_bar_sayisi"] == 12
