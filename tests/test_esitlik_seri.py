"""Gercek veri deger esitligi betigi (`analysis/00_veri_denetimi/esitlik_seri.py`; RESULTS §14.48). Sentetik girdi.

Betigin karsilastirmasi once burada sinanir: bozulmamis seri kuruculari 0 uyusmazlik verir; bilerek bozulmus BIR deger
(bir barda bir ULP, bir bool cevrilmesi) tam o deger adinda 1 uyusmazlik olarak yakalanir; seri duzeyindeki hata
referansta karsiligi yoksa butun barlari uyusmayan yapar (G10). Cikti deger tasimaz.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from data import seri_kurucu
import test_seri_kurucu as tsk

KOK = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("_esitlik_seri", KOK / "analysis/00_veri_denetimi/esitlik_seri.py")
es = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = es
_spec.loader.exec_module(es)

BAS = tsk.BAS
SON = tsk.U("2024-06-30 20:00")
SINIRLAR = (None, None, BAS, SON)


@pytest.fixture(scope="module")
def dunya():
    m = tsk.mumlar(son=SON, bozuk=[tsk.U("2024-03-05 08:00")], eksik=[tsk.U("2024-04-01 12:00")])
    return m, tsk.fonlama(son=SON), tsk.gunluk(m, son=SON)


def _izgara(hipotez, m, g):
    return tsk.izgara_1d(g) if hipotez == "H3" else tsk.izgara_4h(m, son=SON)


def _y(hipotez):
    from data import sinyal
    return sinyal.izgara(hipotez)[0]


def _kos(hipotez, dunya, seri=seri_kurucu, kirp=None):
    m, f, g = dunya
    z = _izgara(hipotez, m, g)
    if kirp is not None:
        z = z[kirp]
    return es.birim_karsilastir(hipotez, _y(hipotez), z, m, f, g, SINIRLAR, seri=seri)


@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_bozulmamis_seri_sifir_uyusmazlik(hipotez, dunya):
    m, _, g = dunya
    n = len(_izgara(hipotez, m, g)[-400:])
    sayi = _kos(hipotez, dunya, kirp=slice(-400, None))
    assert set(sayi) == set(es.DEGERLER[hipotez] + es.ORTAK)
    assert all(v["uyusmayan_bar"] == 0 and v["beklenmeyen_hata_referans"] == 0 and v["hata"] == "" for v in sayi.values())
    assert n > 100 and all(v["karsilastirilan_bar"] == n for v in sayi.values())


class _Bozuk(types.SimpleNamespace):
    pass


def _bozuk_seri(bozan):
    """`seri_kurucu`nun bir kopyasi; `bozan(ad, deger)` secilen ciktiyi degistirir."""
    s = _Bozuk(**{ad: getattr(seri_kurucu, ad) for ad in dir(seri_kurucu) if not ad.startswith("__")})
    asil_capasiz, asil_uygunluk = seri_kurucu.capasiz_pencereler, seri_kurucu.uygunluk
    s.capasiz_pencereler = lambda *a, **k: {ad: bozan(ad, d) for ad, d in asil_capasiz(*a, **k).items()}
    s.uygunluk = lambda *a, **k: bozan("uygunluk", asil_uygunluk(*a, **k))
    return s


def _bir_ulp(hedef, sira):
    def bozan(ad, deger):
        if ad != hedef:
            return deger
        d = np.array(deger, dtype=float, copy=True)
        i = np.nonzero(np.isfinite(d))[0][sira]
        d[i] = np.nextafter(d[i], np.inf)
        return d
    return bozan


@pytest.mark.parametrize("hipotez,hedef", [("H1", "hacim_medyani_180"), ("H2", "kirilim_dip"), ("H3", "sma50")])
def test_bilerek_bozulmus_tek_deger_tek_uyusmazlik(hipotez, hedef, dunya):
    sayi = _kos(hipotez, dunya, seri=_bozuk_seri(_bir_ulp(hedef, 5)), kirp=slice(-300, None))
    assert sayi[hedef]["uyusmayan_bar"] == 1
    assert all(v["uyusmayan_bar"] == 0 for ad, v in sayi.items() if ad != hedef)


def test_bilerek_cevrilmis_uygunluk_yakalanir(dunya):
    def bozan(ad, deger):
        if ad != "uygunluk":
            return deger
        t = deger.copy()
        t.iloc[7, t.columns.get_loc("uygun")] = not bool(t["uygun"].iloc[7])
        return t
    sayi = _kos("H2", dunya, seri=_bozuk_seri(bozan), kirp=slice(-200, None))
    assert sayi["uygun"]["uyusmayan_bar"] == 1 and sayi["uygunluk_medyan_hacim"]["uyusmayan_bar"] == 0


def test_seri_hatasi_referansta_karsiligi_yoksa_butun_barlar_uyusmaz(dunya):
    def bozan(ad, deger):
        raise ValueError("bilerek")
    sayi = _kos("H3", dunya, seri=_bozuk_seri(bozan), kirp=slice(-50, None))
    assert all(v["hata"] == "ValueError" and v["uyusmayan_bar"] == v["karsilastirilan_bar"] == 50
               for v in sayi.values())


def test_cikti_deger_tasimaz():
    assert set(es.SUTUNLAR) == {"sembol", "donem_no", "hipotez", "yapilandirma", "deger", "bar_kumesi", "genel_tohum",
                                "numpy_surumu", "pandas_surumu", "karsilastirilan_bar", "uyusmayan_bar",
                                "beklenmeyen_hata_referans", "hata"}
    satir = es._bos_satir("XUSDT", 0, "H1", "y", "dip")
    assert set(satir) == set(es.SUTUNLAR)
    metin = (KOK / "analysis/00_veri_denetimi/esitlik_seri.py").read_text(encoding="utf-8")
    for yasak in ("sure_s", "perf_counter", "olay_karari", "sinyal_kosulu", "kosullar_saglandi", "ilk_20"):
        assert yasak not in metin, yasak


def test_h1_capa_kurali_esitlik_kapi_ile_ayni():
    spec = importlib.util.spec_from_file_location("_ek_capa", KOK / "analysis/00_veri_denetimi/esitlik_kapi.py")
    ek = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = ek
    spec.loader.exec_module(ek)
    z = pd.date_range("2024-01-01", periods=40, freq="4h", tz="UTC")
    assert list(es.h1_capalari(z)) == [ek.h1_capasi(t, i) for i, t in enumerate(z)]
