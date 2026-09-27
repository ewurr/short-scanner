"""Rev.10 hazirligi, kapatmalar: tek karar noktasinin iki girdi denetimi. Aga cikmaz.

1. Fiyat okuma tabani (on-kayit §4 rev.8): close_time sutunu olmayan tek satirlik cerceve 4h serisi
   oldugu dogrulanamadigi icin reddedilir (sizinti testcisi Rev.9 bulgusu; D-B3'un kalan acigi).
2. Sinyal pencereleri (on-kayit §2 "Tamlik sarti"): `sinyal_degerleri` bool kabul etmez (denetci
   bulgusu D-C1): olumsuzlanmis bir kosul NaN pencereyi True ile gizleyebilir.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import config
from data import pozisyon
from sinyal_yardimcisi import sinyal as _tam_sinyal
from kume_yardimcisi import kume_sinirlari
from uygunluk_yardimcisi import uygunluk

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)


@pytest.mark.parametrize("acilis", ["2025-03-01 00:00", "2025-03-01 04:00"])
def test_tek_satir_close_time_siz_reddedilir(acilis):
    with pytest.raises(ValueError, match="dogrulanamiyor"):
        pozisyon._mum_zamanlari(pd.DataFrame({"open_time": [T(acilis)]}))


def test_tek_satir_close_time_ile_sureye_gore_karar():
    dort = pd.DataFrame({"open_time": [T("2025-03-01 04:00")], "close_time": [T("2025-03-01 07:59:59.999")]})
    assert len(pozisyon._mum_zamanlari(dort)) == 1
    gun = pd.DataFrame({"open_time": [T("2025-03-01")], "close_time": [T("2025-03-01 23:59:59.999")]})
    with pytest.raises(ValueError, match="4 saati"):
        pozisyon._mum_zamanlari(gun)


def test_iki_satir_close_time_siz_ardisik_farkla_karar():
    assert len(pozisyon._mum_zamanlari(pd.DataFrame({"open_time": [T("2025-03-01"), T("2025-03-01 04:00")]}))) == 2
    with pytest.raises(ValueError):
        pozisyon._mum_zamanlari(pd.DataFrame({"open_time": [T("2025-03-01"), T("2025-03-02")]}))


def test_bos_cerceve_denetimden_hata_vermeden_doner():
    assert len(pozisyon._mum_zamanlari(pd.DataFrame({"open_time": pd.DatetimeIndex([], tz="UTC")}))) == 0


DB, B = T("2025-01-01"), T("2025-04-10 20:00")
Z = pd.date_range(T("2025-03-01"), B, freq="4h")
MUM = pd.DataFrame({"open_time": Z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
FUND = pd.DataFrame({"odeme_zamani": pd.date_range(DB, B, freq="8h"), "aralik_saat": 8.0, "oran": 0.0, "oran_8h": 0.0})


def _karar(sinyal):
    return pozisyon.olay_karari(MUM, FUND, T("2025-03-05 04:00"), 6, config.BAR_4H, hipotez="H1", birincil_ufuk=18,
                                **kume_sinirlari(T('2025-03-05 04:00')), donem_baslangic=DB, donem_bitis=B,
                                sinyal_degerleri=sinyal, **uygunluk(config.BAR_4H, DB, B))


@pytest.mark.parametrize("deger", [True, False, np.bool_(True), np.bool_(False)])
def test_sinyal_degerleri_bool_kabul_etmez(deger):
    with pytest.raises(TypeError, match="bool"):
        _karar({"pencere": 1.0, "kosul": deger})


def test_nan_pencere_olumsuz_kosulla_gizlenemez():
    x, y = float("nan"), 0.5
    with pytest.raises(TypeError):
        _karar({"kosul": not (x < y)})  # NaN ile True olurdu
    with pytest.raises(pozisyon.SinyalPenceresiTamDegil):
        # dogru kullanim: pencere degerleri. F1 kapanis turu: kapi hipotezin butun sinyal degerlerini ister.
        _karar(_tam_sinyal("H1", pump_dip=x, tepe=y))


@pytest.mark.parametrize("deger", [1, 1.0, np.int64(2), np.float64(0.5)])
def test_sayisal_degerler_kabul_edilir(deger):
    assert _karar(_tam_sinyal("H1", pump_dip=deger)).plan.sinyal_zamani == T("2025-03-05 04:00")
