"""Bar tabanli pencerelerde donem ve kume basi karsilastirmasi zaman toleransina baglidir (on-kayit §4
rev.8 "Zaman toleransi"; Rev.10 uygulamasi madde 2, kod hatasi).

`pencere.pencere_dilimi` donem ve kume basini once ham `<` ile karsilastiriyordu (sizinti testcisinin
Rev.10 hazirlik bulgusu 1). Artik iki sinir da ayni yardimciyla (`pencere.once`) karsilastirilir:
toleransla ayni an olan pencere basi siniri asmis sayilmaz, tam 1 dakika once olan asmis sayilir.
Iki sinir birbirinin aynisi davranir (donem ve kume bakisimsizligi yok). Aga cikmaz.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import config
from data import pencere

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
DAKIKA = pd.Timedelta(minutes=1)
NS = pd.Timedelta(1, "ns")
UZAK_DONEM = T("2030-01-01")


def _dilim(t, sinir_turu, sinir):
    seri = pd.Series([1.0], index=pd.DatetimeIndex([t]))
    if sinir_turu == "donem":
        return pencere.pencere_dilimi(seri, t, 1, config.BAR_4H, t_dahil=True, kume_baslangic=None,
                                      donem_baslangic=sinir)
    return pencere.pencere_dilimi(seri, t, 1, config.BAR_4H, t_dahil=True, kume_baslangic=sinir,
                                  donem_baslangic=UZAK_DONEM)


@pytest.mark.parametrize("sinir_turu", ["donem", "kume"])
@pytest.mark.parametrize("fark, gecerli", [
    (pd.Timedelta(0), True),                  # tam ayni an
    (NS, True),                               # 1 ns sonra baslayan sinir: ayni an
    (pd.Timedelta(seconds=59), True),         # 59 sn: ayni an
    (DAKIKA - NS, True),                      # 1 dk'dan kesin kucuk: ayni an
    (DAKIKA, False),                          # tam 1 dk: ayni an DEGIL, pencere siniri asar
    (pd.Timedelta(hours=4), False),
])
def test_sinir_toleransla_karsilastirilir(sinir_turu, fark, gecerli):
    t = T("2031-03-01 08:00")
    sonuc = _dilim(t, sinir_turu, t + fark)
    assert (sonuc is not None) is gecerli


@pytest.mark.parametrize("sinir_turu", ["donem", "kume"])
def test_sinirdan_sonra_baslayan_pencere_etkilenmez(sinir_turu):
    t = T("2031-03-01 08:00")
    assert _dilim(t, sinir_turu, t - pd.Timedelta(seconds=30)) is not None
    assert _dilim(t, sinir_turu, t - pd.Timedelta(hours=4)) is not None


@pytest.mark.parametrize("fark", [pd.Timedelta(0), NS, DAKIKA - NS, DAKIKA, pd.Timedelta(hours=1)])
def test_donem_ve_kume_ayni_karari_verir(fark):
    """Bakisimsizlik yok: ayni fark donem ve kume sinirinda ayni sonucu verir."""
    t = T("2031-03-01 08:00")
    assert (_dilim(t, "donem", t + fark) is None) == (_dilim(t, "kume", t + fark) is None)


def test_cok_barli_pencerede_ilk_beklenen_bar_karsilastirilir():
    """6 barlik pencere (t haric): ilk beklenen bar t - 24 saat. Sinir o bardan 30 sn sonra ise ayni
    an, pencere gecerli; 2 dk sonra ise pencere siniri asar."""
    t = T("2031-03-02 00:00")
    zaman = pd.date_range(t - pd.Timedelta(hours=40), t, freq="4h")
    seri = pd.Series(np.arange(len(zaman), dtype=float), index=zaman)
    ilk = t - pd.Timedelta(hours=24)
    for sinir, gecerli in ((ilk + pd.Timedelta(seconds=30), True), (ilk + pd.Timedelta(minutes=2), False)):
        for ad in ("donem_baslangic", "kume_baslangic"):
            sinirlar = {"donem_baslangic": UZAK_DONEM - pd.Timedelta(days=3650), "kume_baslangic": None}
            sinirlar[ad] = sinir
            dilim = pencere.pencere_dilimi(seri, t, 6, config.BAR_4H, t_dahil=False, **sinirlar)
            assert (dilim is not None) is gecerli, (ad, sinir)


def test_pencere_degeri_de_ayni_kapidan_gecer():
    t = T("2031-03-01 08:00")
    seri = pd.Series([2.0], index=pd.DatetimeIndex([t]))
    ortak = dict(t_dahil=True, islev="sum")
    assert pencere.pencere_degeri(seri, t, 1, config.BAR_4H, kume_baslangic=t + NS, donem_baslangic=t + NS,
                                  **ortak) == 2.0
    assert np.isnan(pencere.pencere_degeri(seri, t, 1, config.BAR_4H, kume_baslangic=t + DAKIKA,
                                           donem_baslangic=UZAK_DONEM - pd.Timedelta(days=3650), **ortak))
