"""Rev.11 uygulamasi madde 3: 4h barda eksik hucre gununu dusurur (on-kayit §2 "1 gunluk barlar").

On-kayit §2 (rev.11): "Bir barin mevcut sayilmasi icin satirinin bulunmasi yetmez (rev.11):
fiyat ve hacim hucrelerinin tamami sayi olmalidir. Hucrelerinden biri NaN ya da sonlu degilse o
bar eksiktir ve gununu dusurur; eksik hucre sifir sayilmaz."

Testler her hucre sutununu tek tek, uc bozuk degerle (NaN, +sonsuz, -sonsuz) ve sayisal olmayan
degerle sinar; ayrica eksik hucrenin toplama 0 gibi GIRMEDIGINI (gun hic olusmadigini) ve
`count` sutununun kural kapsaminda OLMADIGINI (belgeli sinir) gosterir. Aga cikmaz.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import config
from data import klines
from donem_yardimcisi import tum_seri_donemi

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731


def _dort_saatlik(gun_sayisi: int = 2, hacim: float = 1_000_000.0) -> pd.DataFrame:
    zaman = pd.date_range(T("2021-01-01"), periods=6 * gun_sayisi, freq="4h")
    return pd.DataFrame({
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
    })


def _gunluk(mumlar: pd.DataFrame) -> pd.DataFrame:
    return klines.gunluge_cevir(mumlar, donemler=tum_seri_donemi(mumlar))


def test_tam_seride_iki_gun_olusur():
    assert len(_gunluk(_dort_saatlik(2))) == 2


@pytest.mark.parametrize("sutun", klines.HUCRE_SUTUNLARI)
@pytest.mark.parametrize("bozuk", [float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("sira", [0, 3, 5])
def test_her_fiyat_ve_hacim_hucresi_gunu_dusurur(sutun, bozuk, sira):
    """Hangi hucre, hangi bozuk deger ve gunun hangi bari olursa olsun gun dusmeli."""
    mumlar = _dort_saatlik(2)
    mumlar.loc[sira, sutun] = bozuk
    gunluk = _gunluk(mumlar)
    assert list(pd.DatetimeIndex(gunluk["open_time"])) == [T("2021-01-02")], (
        f"{sutun} = {bozuk} olan bar gununu dusurmedi")


@pytest.mark.parametrize("sutun", klines.HUCRE_SUTUNLARI)
def test_sayisal_olmayan_hucre_gunu_dusurur(sutun):
    mumlar = _dort_saatlik(2)
    mumlar[sutun] = mumlar[sutun].astype(object)
    mumlar.loc[2, sutun] = "bozuk"
    assert list(pd.DatetimeIndex(_gunluk(mumlar)["open_time"])) == [T("2021-01-02")]


def test_eksik_hucre_sifir_sayilmaz():
    """"Eksik hucre sifir sayilmaz": gun olussa toplam eksik cikardi; gun hic olusmaz."""
    mumlar = _dort_saatlik(1)
    mumlar.loc[3, "quote_volume"] = float("nan")
    gunluk = _gunluk(mumlar)
    assert gunluk.empty
    # Ayni seride hucre tamken gun olusur ve toplam ALTI barin toplamidir (sessiz eksilme yok).
    tam = _gunluk(_dort_saatlik(1))
    assert len(tam) == 1 and tam["quote_volume"].iloc[0] == pytest.approx(6 * 1_000_000.0)


def test_bes_bari_tam_bir_bari_bozuk_gun_dusmez_diye_sayilmaz():
    """Sinir durumu: gunde alti bar var ama biri bozuk -> bes tam bar kalir, gun alti bara
    ulasmadigi icin dusuyor (bar sayisi kurali ile ayni sonuc)."""
    mumlar = _dort_saatlik(1)
    mumlar.loc[1, "low"] = float("nan")
    assert _gunluk(mumlar).empty


def test_count_hucresi_kural_kapsaminda_degil():
    """Belgeli sinir: `count` islem sayisidir, on-kayit cumlesi "fiyat ve hacim hucreleri" der.
    Eksik bir `count` gunu dusurmez; gunun `count` toplami sessizce eksilir. Bu bir acik
    noktadir ve hicbir olay, uygunluk ya da getiri hesabina girmez."""
    assert "count" not in klines.HUCRE_SUTUNLARI
    mumlar = _dort_saatlik(1)
    mumlar.loc[3, "count"] = float("nan")
    gunluk = _gunluk(mumlar)
    assert len(gunluk) == 1
    assert gunluk["count"].iloc[0] == pytest.approx(25.0)  # 5 bar x 5; eksik hucre atlandi


def test_hucreleri_tam_mi_saftir():
    mumlar = _dort_saatlik(1)
    once = mumlar.copy()
    mumlar.loc[2, "high"] = float("nan")
    maske = klines.hucreleri_tam_mi(mumlar)
    assert list(maske) == [True, True, False, True, True, True]
    assert klines.hucreleri_tam_mi(once).all()


def test_hucre_sutunlari_fiyat_ve_hacim():
    assert set(klines.HUCRE_SUTUNLARI) == {
        "open", "high", "low", "close", "volume", "quote_volume",
        "taker_buy_volume", "taker_buy_quote_volume"}


def test_eksik_hucre_uygunluk_hacmini_de_dusurur():
    """1d serisi tektir (on-kayit §2 rev.8): dusen gun uygunluk hacim penceresinde de eksiktir.
    Burada yalnizca gunun seriden dustugu gosterilir; uygunluk degeri hesaplanmaz."""
    mumlar = _dort_saatlik(3)
    mumlar.loc[8, "volume"] = float("inf")  # ikinci gunun barlarindan biri
    gunler = list(pd.DatetimeIndex(_gunluk(mumlar)["open_time"]))
    assert gunler == [T("2021-01-01"), T("2021-01-03")]
