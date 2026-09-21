"""D kurali ve 1 gunluk tamlik sayimlari deger icermez (denetci bulgusu D-B4, RESULTS §14).

Bu sayimlar B grubunu ve C2 donemini de kapsar. Veri denetimi sinirinda
(CLAUDE.md §3.1, RESULTS §14.9) kalmalarinin kosulu yalnizca funding kaydinin
varligini, zaman damgasini ve kaydin aralik alanini; mumlarin zaman damgasini ve
hacmin sifir olup olmadigini kullanmalaridir. Testler bunu kodda gosterir:

1. `a1_olcumu.d_kurali_olc` funding cercevesinde oran sutunu HIC yokken de
   calisir ve oran degerleri ne olursa olsun ayni satirlari uretir.
2. `calistir.gunluk_sinir_tablosu` fiyat sutunlari NaN, sifir olmayan hacimler
   rastgele olsa da ayni tabloyu uretir.
3. Bu fonksiyonlarin kaynaginda fiyat ya da oran sutununun adi gecmez.

Aga cikmaz.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import sys
import textwrap

import numpy as np
import pandas as pd

from tests.donem_yardimcisi import tum_seri_donemi
import pytest

import config
from data import klines
from data.donem import Donem

DIZIN = config.ANALIZ_DIZINI / "00_veri_denetimi"
sys.path.insert(0, str(DIZIN))


def _yukle(ad: str, dosya: str):
    spec = importlib.util.spec_from_file_location(ad, DIZIN / dosya)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


calistir = _yukle("_deger_calistir", "calistir.py")
a1 = _yukle("_deger_a1", "a1_olcumu.py")

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
FIYAT_VE_ORAN = {"open", "high", "low", "close", "oran", "oran_8h"}

D0 = Donem(T("2025-04-01 00:00"), T("2025-04-10 08:00"), 57, 57)
D1 = Donem(T("2025-04-20 08:00"), T("2025-04-30 08:00"), 61, 61)


def _funding(oranli: bool, tohum: int) -> pd.DataFrame:
    z = list(pd.date_range(T("2025-04-01 00:00"), T("2025-04-10 12:00"), freq="4h"))
    z += list(pd.date_range(T("2025-04-20 08:00"), T("2025-04-30 12:00"), freq="8h"))
    f = pd.DataFrame({"odeme_zamani": pd.DatetimeIndex(z),
                      "aralik_saat": [4] * 57 + [8] * (len(z) - 57)})
    if oranli:
        rng = np.random.default_rng(tohum)
        f["oran"] = rng.normal(0, 0.01, len(f))
        f["oran_8h"] = rng.normal(0, 0.01, len(f))
    return f


@pytest.mark.parametrize("bar", [config.BAR_4H, config.BAR_1D])
def test_d_kurali_olc_oran_degerinden_bagimsiz(bar):
    turler = ["dolgu_kosusu", "delist_SETTLING"]
    oransiz = a1.d_kurali_olc("X", [D0, D1], turler, _funding(False, 0), bar)
    for tohum in (1, 2):
        assert a1.d_kurali_olc("X", [D0, D1], turler, _funding(True, tohum), bar) == oransiz


def _mumlar(fiyat, hacim_olcegi: float) -> pd.DataFrame:
    z = pd.date_range(T("2025-04-01 00:00"), T("2025-05-05 20:00"), freq="4h")
    gercek = ((z >= D0.baslangic) & (z <= D0.bitis)) | ((z >= D1.baslangic) & (z <= D1.bitis))
    hacim = np.where(gercek, hacim_olcegi * (1 + np.arange(len(z))), 0.0)
    return pd.DataFrame({
        "open_time": z, "open": fiyat, "high": fiyat, "low": fiyat, "close": fiyat,
        "volume": hacim, "close_time": z + pd.Timedelta(hours=4), "quote_volume": hacim,
        "count": 1, "taker_buy_volume": 0.0, "taker_buy_quote_volume": 0.0,
    })


def _detay(mumlar):
    return {"sembol": "X", "_donemler": [D0, D1], "_mumlar": mumlar, "_gunluk": klines.gunluge_cevir(mumlar, donemler=tum_seri_donemi(mumlar))}


def test_gunluk_sinir_tablosu_fiyat_ve_hacim_degerinden_bagimsiz():
    delist = pd.DataFrame({"sembol": ["X"], "sinif": ["SETTLING"]})
    taban = calistir.gunluk_sinir_tablosu([_detay(_mumlar(1.0, 1.0))], delist)
    assert len(taban) == 2
    for fiyat, olcek in ((np.nan, 1.0), (123.4, 1e9), (0.001, 7.5)):
        diger = calistir.gunluk_sinir_tablosu([_detay(_mumlar(fiyat, olcek))], delist)
        pd.testing.assert_frame_equal(diger, taban)


@pytest.mark.parametrize("modul,ad", [
    ("calistir", "gunluk_sinir_satirlari"), ("calistir", "_gun_bar_sayilari"),
    ("calistir", "gunluk_sinir_tablosu"), ("calistir", "donem_sonu_turleri"),
    ("a1", "d_kurali_olc"), ("a1", "temsili_plan"),
])
def test_kaynakta_fiyat_ya_da_oran_sutunu_yok(modul, ad):
    """Sayim fonksiyonlarinin kaynaginda (belge metni haric) fiyat ya da oran
    sutununun adi dizge sabiti ya da oznitelik olarak gecmez. Sinir: adi
    yazmadan degere ulasan yollari yakalamaz (bkz. test_a1_deger_yolu_yok)."""
    fonk = getattr(calistir if modul == "calistir" else a1, ad)
    agac = ast.parse(textwrap.dedent(inspect.getsource(fonk)))
    belge = ast.get_docstring(agac.body[0])
    adlar = {d.value for d in ast.walk(agac) if isinstance(d, ast.Constant) and isinstance(d.value, str)
             and d.value != belge}
    adlar |= {d.attr for d in ast.walk(agac) if isinstance(d, ast.Attribute)}
    assert not (adlar & FIYAT_VE_ORAN), adlar & FIYAT_VE_ORAN
