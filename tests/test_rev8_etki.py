"""Rev.8 etki sayimlari (analysis/00_veri_denetimi/rev8_etki.py). Aga cikmaz.

Sayimlarin gercek kod yolundan geldigini, kume kiriliminin sinyal zamanina ve
sembolun grubuna gore yapildigini, "yalniz baslangic" sayiminin yalnizca rev.8
baslangic kosulunun dusurdugu pozisyonlari saydigini ve betigin oran ya da fiyat
okumadigini sabitler.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import sys
import textwrap

import numpy as np
import pandas as pd
import pytest

import config
from data import funding as funding_modulu
from data import pencere as pencere_modulu
from data.donem import Donem

DIZIN = config.ANALIZ_DIZINI / "00_veri_denetimi"
sys.path.insert(0, str(DIZIN))
_spec = importlib.util.spec_from_file_location("_rev8_etki", DIZIN / "rev8_etki.py")
etki = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(etki)

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
BAS, B = T("2025-01-01 00:00"), T("2025-02-10 20:00")
D = Donem(BAS, B, 246, 246)
KUMELER = etki.kume_sinirlari()


def _mumlar(z):
    """Fiyat sutunlari sabit 1.0; betik fiyat OKUMAZ (bunu `test_oran_ve_fiyat_okunmaz` AST
    taramasiyla garanti eder). Rev.11'e kadar bu sutunlar NaN veriliyordu (okunmadiklarini
    gostermek icin); on-kayit §2 rev.11 ile NaN fiyat hucresi bari eksik sayar ve 1d serisinde
    hic gun olusmaz, bu yuzden sonlu degere gecildi. Testlerin iddialari degismedi."""
    z = pd.DatetimeIndex(z)
    return pd.DataFrame({"open_time": z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
                         "volume": 1.0, "close_time": z + pd.Timedelta(hours=4), "quote_volume": 1.0, "count": 1,
                         "taker_buy_volume": 0.0, "taker_buy_quote_volume": 0.0})


def _fund(z, aralik=8.0):
    return pd.DataFrame({"odeme_zamani": pd.DatetimeIndex(z), "aralik_saat": aralik})


def test_sinyal_kumesi_grup_ve_zamana_gore():
    assert etki.sinyal_kumesi(T("2025-08-31 20:00"), "A", KUMELER) == "KESIF"
    assert etki.sinyal_kumesi(T("2025-08-31 20:00"), "B", KUMELER) == "C1"
    assert etki.sinyal_kumesi(T("2025-09-01 00:00"), "A", KUMELER) == "C2"
    assert etki.sinyal_kumesi(T("2025-09-01 00:00"), "B", KUMELER) == "C2"
    assert etki.sinyal_kumesi(T("2019-12-31 20:00"), "A", KUMELER) is None


def test_yalniz_baslangic_gercek_tamlikla_ayni():
    """Butun sayimlar gercek plan ve gercek tamlik ayrintisindan: tekil yolla ayni."""
    z = pd.date_range(BAS, B, freq="4h")
    # 8h -> 2h gecisi: gecis kaydi (01-20 08:00) onceki kayittan 8 saat sonra gelir ama
    # kisa araligi (2) tasir; girisi 04:00'ten once olan pozisyonlarda baslangic kosulu bozulur.
    fund = list(pd.date_range(BAS, T("2025-01-20"), freq="8h")) + list(pd.date_range(T("2025-01-20 08:00"), B + pd.Timedelta(hours=4), freq="2h"))
    fr = _fund(fund)
    fr.loc[fr["odeme_zamani"] >= T("2025-01-20 08:00"), "aralik_saat"] = 2.0
    satirlar = etki.baslangic_etkisi("X", "A", [D], _mumlar(z), fr, KUMELER)
    s4 = next(s for s in satirlar if s["bar"] == config.BAR_4H)
    beklenen_tam = beklenen_yalniz = plan_sayisi = 0
    for t in z:
        try:
            plan = pencere_modulu.pozisyon_plani(z, t, 18, config.BAR_4H, birincil_ufuk=18,
                                                 kume_baslangic=KUMELER["KESIF"][1], kume_bitis=KUMELER["KESIF"][2],
                                                 donem_baslangic=BAS, donem_bitis=B)
        except pencere_modulu.OlayOlusmaz:
            continue
        plan_sayisi += 1
        # Rev.9 veri katmanindaki kurali degistirdi; betik ve kehanet Rev.8 tanimini donmus kopyadan okur.
        a = etki.rev8_tamlik_ayrintisi(fr, [plan.giris], [etki.rev8_pencere_sonu(plan)]).iloc[0]
        beklenen_tam += bool(a["tam"])
        beklenen_yalniz += bool(a["kayit_var"] and a["aralik_gecerli"] and a["ic_tam"] and a["son_tam"]
                                and not a["baslangic_tam"])
    assert s4["sinyal"] == len(z) and s4["plan"] == plan_sayisi
    assert s4["tam"] == beklenen_tam and s4["yalniz_baslangic"] == beklenen_yalniz
    assert s4["yalniz_baslangic"] > 0  # 8h -> 2h gecisinde baslangic kosulu tetiklenir
    assert s4["tam"] + s4["bozuk"] == s4["plan"]


def test_1d_sinyalleri_rev8_gunluk_seriden():
    """1d sinyalleri yalnizca donem ici tam gunler (klines.gunluge_cevir, rev.8)."""
    z = pd.date_range(BAS, B, freq="4h")
    satirlar = etki.baslangic_etkisi("X", "A", [D], _mumlar(z), _fund(pd.date_range(BAS, B, freq="8h")), KUMELER)
    s1 = next(s for s in satirlar if s["bar"] == config.BAR_1D)
    assert s1["sinyal"] == 41  # 01-01 .. 02-10 (son gun 20:00 dahil tam)


def test_kume_sonuna_tasan_plan_ret_sayilir():
    b = T("2025-08-31 20:00")
    d = Donem(T("2025-08-20 00:00"), b, 72, 72)
    z = pd.date_range(d.baslangic, b, freq="4h")
    s4 = next(s for s in etki.baslangic_etkisi("X", "A", [d], _mumlar(z), _fund(z), KUMELER)
              if s["bar"] == config.BAR_4H)
    # Cikisi K'da (09-01 00:00, kume sonundan sonra) olan 18 sinyal reddedilir; son barin
    # (B) giris bari donem disi. Cikisi B'den once olanlar olusur.
    assert s4["ret_kume_siniri"] == 18 and s4["ret_giris_bari_yok"] == 1
    assert s4["plan"] == s4["sinyal"] - 19


def test_donem_sonu_satiri_eski_ve_rev8_cikis():
    z = pd.date_range(BAS, T("2025-02-12 20:00"), freq="4h")  # dolgu barlariyla bitis gunu tam
    d = Donem(BAS, T("2025-02-10 08:00"), 1, 1)
    s = etki.donem_sonu_satirlari("X", [d], ["delist_SETTLING"], _mumlar(z), _fund([BAS]), {0: False})[0]
    assert s["cikis_1d_eski"] == T("2025-02-11 00:00") and s["cikis_1d_rev8"] == T("2025-02-10 12:00")
    assert s["funding_var_rev8"] is True
    kisa = pd.date_range(BAS, T("2025-02-10 08:00"), freq="4h")  # bitis gunu eksik
    s = etki.donem_sonu_satirlari("X", [d], ["delist_SETTLING"], _mumlar(kisa), _fund([]), {})[0]
    assert s["cikis_1d_eski"] == T("2025-02-10 00:00") and s["funding_var_rev8"] is False


def test_saat_sapmasi():
    z = pd.DatetimeIndex([T("2025-01-01 00:00") + pd.Timedelta(milliseconds=31), T("2025-01-01 08:00")
                          - pd.Timedelta(seconds=30)])
    assert list(etki._saat_sapmasi(z)) == [np.timedelta64(31, "ms"), np.timedelta64(30, "s")]


@pytest.mark.parametrize("ad", ["baslangic_etkisi", "donem_sonu_satirlari", "sembol_etki", "_saat_sapmasi"])
def test_oran_ve_fiyat_okunmaz(ad):
    fonk = getattr(etki, ad)
    agac = ast.parse(textwrap.dedent(inspect.getsource(fonk)))
    belge = ast.get_docstring(agac.body[0])
    adlar = {d.value for d in ast.walk(agac) if isinstance(d, ast.Constant) and isinstance(d.value, str)
             and d.value != belge}
    adlar |= {d.attr for d in ast.walk(agac) if isinstance(d, ast.Attribute)}
    assert not (adlar & {"open", "high", "low", "close", "oran", "oran_8h"})
