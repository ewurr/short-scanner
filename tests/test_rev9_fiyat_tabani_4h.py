"""Denetci bulgusu D-B3: tek karar noktasi fiyat okuma tabaninin 4h serisi oldugunu denetler.

On-kayit §4 rev.8 "Fiyat okuma tabani": "Pozisyonun butun fiyat okumalari ise her hipotezde
donem ici 4h barlardan yapilir." 1d cercevesi 4h cercevesiyle ayni sutun adlarini tasir;
sessizce kabul edilseydi her cikis ileri kaymaya duser, MAE gunluk high'lardan hesaplanirdi.
Aga cikmaz: `klines.ham_mumlari_yukle` sentetik seriyle degistirilir, `mumlari_yukle`
gercek kapidan (kume, 1d tek yolu `gunluge_cevir`) gecer.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import klines, pozisyon, split
from data.donem import Donem
from sinyal_yardimcisi import sinyal
from kume_yardimcisi import kume_sinirlari
from uygunluk_yardimcisi import uygunluk

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
BAS, B = T("2024-01-01 00:00"), T("2024-04-30 20:00")
Z = pd.date_range(BAS, B, freq="4h")
DONEM = Donem(BAS, B, len(Z), len(Z))


def _dort_saat() -> pd.DataFrame:
    return pd.DataFrame({"open_time": Z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0,
                         "close_time": Z + H4 - pd.Timedelta(milliseconds=1), "quote_volume": 1e7, "count": 1,
                         "taker_buy_volume": 0.0, "taker_buy_quote_volume": 0.0})


@pytest.fixture
def sembol(monkeypatch):
    """KESIF grubundaki bir sembol; ham yukleyici sentetik seri doner (1d: tek yol gunluge_cevir)."""
    tablo = split.split_oku()
    s = str(tablo.loc[tablo["grup"] == "A", "sembol"].iloc[0])

    def sahte(sembol_, bar=config.BAR_4H, yenile=False):
        if bar == config.BAR_1D:
            return klines.gunluge_cevir(_dort_saat(), donemler=[DONEM])
        return _dort_saat()

    monkeypatch.setattr(klines, "ham_mumlari_yukle", sahte)
    return s


def _fund():
    z = pd.date_range(BAS, B, freq="8h")
    return pd.DataFrame({"odeme_zamani": z, "aralik_saat": 8.0, "oran": 0.0, "oran_8h": 0.0})


def _karar(mumlar, bar=config.BAR_1D, t=T("2024-03-10")):
    return pozisyon.olay_karari(
        mumlar, _fund(), t, 14 if bar == config.BAR_1D else 18, bar,
        hipotez="H3" if bar == config.BAR_1D else "H1", birincil_ufuk=14 if bar == config.BAR_1D else 18, **kume_sinirlari(t),
        donem_baslangic=BAS, donem_bitis=B, sinyal_degerleri=sinyal("H3" if bar == config.BAR_1D else "H1"), **uygunluk(bar, BAS, B))


def test_mumlari_yukle_1d_ciktisi_karar_noktasinda_hata_verir(sembol):
    gunluk = klines.mumlari_yukle(sembol, config.BAR_1D, "KESIF")
    assert len(gunluk) > 100 and (gunluk["open_time"] == gunluk["open_time"].dt.floor("D")).all()
    with pytest.raises(ValueError, match="4h"):
        _karar(gunluk)


def test_mumlari_yukle_4h_ciktisi_kabul_edilir(sembol):
    dort = klines.mumlari_yukle(sembol, config.BAR_4H, "KESIF")
    p = _karar(dort)
    assert p.plan.giris == T("2024-03-11") and p.cikis_turu == "olagan"
    assert p.plan.cikis.zaman == T("2024-03-24 20:00")  # kapanisi T (03-25 00:00) olan 4h bar


def test_close_time_olmadan_1d_cercevesi_de_reddedilir(sembol):
    gunluk = klines.mumlari_yukle(sembol, config.BAR_1D, "KESIF").drop(columns=["close_time"])
    with pytest.raises(ValueError, match="4h"):
        _karar(gunluk)


def test_mae_de_1d_cercevesini_reddeder(sembol):
    dort = klines.mumlari_yukle(sembol, config.BAR_4H, "KESIF")
    p = _karar(dort)
    with pytest.raises(ValueError, match="4h"):
        pozisyon.mae(klines.mumlari_yukle(sembol, config.BAR_1D, "KESIF"), p)


def test_izgara_disi_acilis_reddedilir():
    kaymis = _dort_saat()
    kaymis["open_time"] = kaymis["open_time"] + pd.Timedelta(hours=1)
    kaymis["close_time"] = kaymis["close_time"] + pd.Timedelta(hours=1)
    with pytest.raises(ValueError, match="izgara"):
        _karar(kaymis, bar=config.BAR_4H, t=T("2024-03-10 01:00"))
