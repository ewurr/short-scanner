"""Uygunluk testleri (on-kayit §2, CLAUDE.md §3.6: gelecege bakis yok)."""

from __future__ import annotations

import pandas as pd

import config
from data import eligibility as uyg


def _hacim_serisi(bas: str, gun: int, hacim: float) -> pd.Series:
    indeks = pd.date_range(bas, periods=gun, freq="D", tz="UTC")
    return pd.Series([hacim] * gun, index=indeks)


def test_gelecege_bakmaz_t_sonrasi_degisiklik_sonucu_degistirmez():
    """t+1'deki hacim degisikligi t'deki sonucu degistirmemeli."""
    seri = _hacim_serisi("2021-01-01", 60, 20_000_000.0)
    t = pd.Timestamp("2021-02-10", tz="UTC")
    once = uyg.medyan_hacim(seri, t)

    # t'den SONRAKI gunlerin hacmini sifira cek
    bozuk = seri.copy()
    bozuk.loc[bozuk.index >= t] = 0.0
    sonra = uyg.medyan_hacim(bozuk, t)

    assert once == sonra


def test_t_gunu_henuz_kapanmadigi_icin_pencereye_girmez():
    seri = _hacim_serisi("2021-01-01", 60, 20_000_000.0)
    t = pd.Timestamp("2021-02-10 12:00", tz="UTC")

    bozuk = seri.copy()
    bozuk.loc[pd.Timestamp("2021-02-10", tz="UTC")] = 0.0  # t'nin kendi gunu

    assert uyg.medyan_hacim(seri, t) == uyg.medyan_hacim(bozuk, t)


def test_pencere_dolmadan_uygunluk_verilmez():
    seri = _hacim_serisi("2021-01-01", 10, 50_000_000.0)
    t = pd.Timestamp("2021-01-08", tz="UTC")
    assert pd.isna(uyg.medyan_hacim(seri, t))  # 30 tam gun yok


def test_listeleme_yasi_esigi():
    seri = _hacim_serisi("2021-01-01", 120, 50_000_000.0)
    ilk = pd.Timestamp("2021-01-01", tz="UTC")

    erken = ilk + pd.Timedelta(days=config.ASGARI_LISTELEME_YASI_GUN - 1)
    gec = ilk + pd.Timedelta(days=config.ASGARI_LISTELEME_YASI_GUN + 5)

    assert uyg.uygun_mu(seri, ilk, erken, config.BAR_4H) is False
    assert uyg.uygun_mu(seri, ilk, gec, config.BAR_4H) is True


def test_hacim_esikleri_bar_tipine_gore_ayrisir():
    """5M USDT: H1/H2 (10M) icin yetersiz, H3 (2M) icin yeterli."""
    seri = _hacim_serisi("2021-01-01", 120, 5_000_000.0)
    ilk = pd.Timestamp("2021-01-01", tz="UTC")
    t = pd.Timestamp("2021-03-01", tz="UTC")

    assert uyg.uygun_mu(seri, ilk, t, config.BAR_4H) is False
    assert uyg.uygun_mu(seri, ilk, t, config.BAR_1D) is True


def test_esik_degerleri_on_kayitla_ayni():
    assert uyg.hacim_esigi(config.BAR_4H) == 10_000_000.0
    assert uyg.hacim_esigi(config.BAR_1D) == 2_000_000.0
    assert config.ASGARI_LISTELEME_YASI_GUN == 30
