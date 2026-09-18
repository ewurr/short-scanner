"""SETTLED icerik karsilastirmasi (denetci bulgusu C3, on-kayit §2 rev.7).

Rev.7: "SETTLED bilgisi yalnizca denetim amaciyla tutulur." Bu testler denetim
olcumunun kendisini sinar: SETTLED dizini eslemesi ve ayni zaman damgali
barlarin bar bar karsilastirilmasi. Sentetik veri, ag yok.
"""

from __future__ import annotations

import pandas as pd

from data import klines


def _seri(bas: str, n: int, fiyat: float = 1.0, hacim: float = 100.0) -> pd.DataFrame:
    z = pd.date_range(bas, periods=n, freq="4h", tz="UTC")
    return pd.DataFrame({"open_time": z, "open": fiyat, "high": fiyat, "low": fiyat, "close": fiyat,
                         "volume": hacim, "quote_volume": hacim})


def test_settled_dizini_eslemesi_son_ekleri_ve_alt_cizgiyi_tanir():
    dizinler = ["ICPUSDT", "ICPUSDT_SETTLED", "BNXUSDTSETTLED", "BNXUSDT", "ABNXUSDTSETTLED", "TLMUSDTSETTLEDSETTLED"]
    assert klines.settled_dizinleri("ICPUSDT", dizinler) == ["ICPUSDT_SETTLED"]
    assert klines.settled_dizinleri("BNXUSDT", dizinler) == ["BNXUSDTSETTLED"]  # ABNXUSDT eslesmez
    assert klines.settled_dizinleri("TLMUSDT", dizinler) == ["TLMUSDTSETTLEDSETTLED"]
    assert klines.settled_dizinleri("ETHUSDT", dizinler) == []


def test_ayni_barlar_fark_vermez_eksikler_ayri_sayilir():
    ana = _seri("2022-05-01", 186)
    settled = ana.drop(index=[10, 11]).reset_index(drop=True)
    sonuc = klines.settled_ay_karsilastir(ana, settled, "2022-05")
    assert (sonuc["ortak_bar"], sonuc["yalniz_ana"], sonuc["yalniz_settled"]) == (184, 2, 0)
    assert sonuc["fiyat_farkli_bar"] == 0 and sonuc["hacim_farkli_bar"] == 0


def test_tek_bardaki_fiyat_ve_hacim_farki_yakalanir():
    ana = _seri("2022-05-01", 186)
    settled = ana.copy()
    settled.loc[50, "close"] = 1.2
    settled.loc[60, "quote_volume"] = 0.0
    sonuc = klines.settled_ay_karsilastir(ana, settled, "2022-05")
    assert sonuc["fiyat_farkli_bar"] == 1 and sonuc["hacim_farkli_bar"] == 1
    assert abs(sonuc["azami_fiyat_bagil_fark"] - (0.2 / 1.2)) < 1e-12


def test_ay_disindaki_barlar_sayilmaz():
    """Karsilastirma yalnizca verilen takvim ayindaki barlari kapsar."""
    ana = _seri("2022-04-30", 12)  # 6 bar Nisan, 6 bar Mayis
    settled = ana.copy()
    settled.loc[0, "close"] = 9.0  # Nisan'daki fark Mayis sonucuna sizmamali
    sonuc = klines.settled_ay_karsilastir(ana, settled, "2022-05")
    assert sonuc["ana_bar"] == 6 and sonuc["fiyat_farkli_bar"] == 0


def test_iki_tarafta_da_sifir_hacim_fark_sayilmaz():
    ana = _seri("2022-05-01", 6, hacim=0.0)
    sonuc = klines.settled_ay_karsilastir(ana, ana.copy(), "2022-05")
    assert sonuc["hacim_farkli_bar"] == 0
