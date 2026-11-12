"""Performans 2b-2, 0. asama: gercek veri deger esitligi betiginin (`esitlik_seri.py`) bozma ve hata dali testleri.

- D-C9: bozma testi `kapanis`, `yuksek`, `tepe` ve `yuksek_30_max`i (capasiz pencerelerin DISINDAKI degerler) ve iki
  hata dalini kapsar: (a) referans beklenmeyen hata verir, seri deger verir -> o deger adinda uyusmayan + beklenmeyen;
  (b) seri birim hatasi verir ve referansta ayni birimde beklenmeyen hata vardir -> butun barlar uyusmayan SAYILMAZ.
- D-C10: referansin `OlayOlusmaz` alt sinifi birimi cokertmez; uyusmayan bar olarak siniflandirilir, beklenmeyen hata
  sayilmaz.
Mevcut `tests/test_esitlik_seri.py` degismedi. Sentetik girdi; aga cikmaz.
"""

from __future__ import annotations

import types

import numpy as np
import pytest

from data import _skaler_referans as ref_modulu
from data import pencere, seri_kurucu

import test_esitlik_seri as tes
import test_seri_kurucu as tsk

es = tes.es


@pytest.fixture(scope="module")
def dunya():
    m = tsk.mumlar(son=tes.SON, bozuk=[tsk.U("2024-03-05 08:00")], eksik=[tsk.U("2024-04-01 12:00")])
    return m, tsk.fonlama(son=tes.SON), tsk.gunluk(m, son=tes.SON)


def _bozuk_seri(hedef: str, sira: int = 5):
    """`seri_kurucu`nun kopyasi; `hedef` adli degerin `sira`ncı sonlu elemani bir ULP kaydirilir. Capasiz pencerelerin
    disindaki dort deger (`kapanis`, `yuksek`, `tepe`, `yuksek_30_max`) kendi kurucularindan bozulur."""
    s = types.SimpleNamespace(**{ad: getattr(seri_kurucu, ad) for ad in dir(seri_kurucu) if not ad.startswith("__")})
    kurucu = {"kapanis": "kapanis", "yuksek": "yuksek", "tepe": "h1_tepe", "yuksek_30_max": "yuksek_30_max"}[hedef]
    asil = getattr(seri_kurucu, kurucu)

    def bozuk(*a, **k):
        d = np.array(asil(*a, **k), dtype=float, copy=True)
        i = np.nonzero(np.isfinite(d))[0][sira]
        d[i] = np.nextafter(d[i], np.inf)
        return d

    setattr(s, kurucu, bozuk)
    return s


@pytest.mark.parametrize("hipotez,hedef", [("H1", "kapanis"), ("H1", "yuksek"), ("H1", "tepe"),
                                           ("H2", "kapanis"), ("H2", "yuksek_30_max"),
                                           ("H3", "kapanis"), ("H3", "yuksek_30_max")])
def test_D_C9_capasiz_disindaki_degerler_bir_ulp_ile_yakalanir(hipotez, hedef, dunya):
    sayi = tes._kos(hipotez, dunya, seri=_bozuk_seri(hedef), kirp=slice(-300, None))
    assert sayi[hedef]["uyusmayan_bar"] == 1, (hipotez, hedef)
    assert all(v["uyusmayan_bar"] == 0 for ad, v in sayi.items() if ad != hedef)


def _ref_kopyasi(hata_t, hata_sinifi):
    """Referansin kopyasi; `bar_degeri` yalnizca `hata_t` barinda `hata_sinifi` ile duser."""
    r = types.SimpleNamespace(**{ad: getattr(ref_modulu, ad) for ad in dir(ref_modulu) if not ad.startswith("__")})
    asil = ref_modulu.bar_degeri

    def bar_degeri(mumlar, t, alan):
        if t == hata_t:
            raise hata_sinifi("bilerek")
        return asil(mumlar, t, alan)

    r.bar_degeri = bar_degeri
    return r


def _kos_ref(hipotez, dunya, ref, seri=seri_kurucu, n=60):
    m, f, g = dunya
    z = tes._izgara(hipotez, m, g)[-n:]
    return es.birim_karsilastir(hipotez, tes._y(hipotez), z, m, f, g, tes.SINIRLAR, seri=seri, ref=ref), z


def test_D_C9_hata_dali_a_referans_beklenmeyen_hata_seri_deger(dunya):
    m, _, g = dunya
    hedef_t = tes._izgara("H2", m, g)[-60:][10]
    sayi, _ = _kos_ref("H2", dunya, _ref_kopyasi(hedef_t, ValueError))
    assert sayi["kapanis"]["beklenmeyen_hata_referans"] == 1 and sayi["kapanis"]["uyusmayan_bar"] == 1
    assert all(v["uyusmayan_bar"] == 0 and v["beklenmeyen_hata_referans"] == 0
               for ad, v in sayi.items() if ad != "kapanis")


def test_D_C9_hata_dali_b_seri_birim_hatasi_referansta_karsiligi_var(dunya):
    """Seri birim hatasi verir; referans ayni birimde bir barda beklenmeyen hata verir -> G10 karsiligi var: birim
    hatasi yazilir, butun barlar uyusmayan sayilmaz (referansin beklenmeyen hatasi sayilir)."""
    m, _, g = dunya
    hedef_t = tes._izgara("H3", m, g)[-60:][7]

    def bozan(*a, **k):
        raise ValueError("bilerek")

    s = types.SimpleNamespace(**{ad: getattr(seri_kurucu, ad) for ad in dir(seri_kurucu) if not ad.startswith("__")})
    s.capasiz_pencereler = bozan
    sayi, _ = _kos_ref("H3", dunya, _ref_kopyasi(hedef_t, ValueError), seri=s)
    assert all(v["hata"] == "ValueError" for v in sayi.values())
    assert all(v["uyusmayan_bar"] == 0 for v in sayi.values())
    assert sayi["kapanis"]["beklenmeyen_hata_referans"] == 1


class _OlaganRet(pencere.OlayOlusmaz):
    gerekce = "test_olagan_ret"


def test_D_C10_referansin_olay_olusmaz_alt_sinifi_birimi_cokertmez(dunya):
    m, _, g = dunya
    hedef_t = tes._izgara("H1", m, g)[-60:][3]
    sayi, z = _kos_ref("H1", dunya, _ref_kopyasi(hedef_t, _OlaganRet))
    assert all(v["hata"] == "" and v["karsilastirilan_bar"] == len(z) for v in sayi.values())
    assert sayi["kapanis"]["uyusmayan_bar"] == 1 and sayi["kapanis"]["beklenmeyen_hata_referans"] == 0
    assert all(v["uyusmayan_bar"] == 0 for ad, v in sayi.items() if ad not in ("kapanis", "yuksek"))
    assert sayi["yuksek"]["uyusmayan_bar"] == 1, "bar_degeri high icin de ayni barda olagan ret verir"
