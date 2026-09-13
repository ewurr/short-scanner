"""Ileri kaymanin ust siniri testleri (on-kayit §4 rev.6).

Hedef cikis bari eksikse ileri kayma, olayin birincil ufku kadar sureyle
sinirlidir (H1, H2: 18 bar; H3: 14 gun). Sonraki mevcut bar bu sinirdan uzaksa
olay olusmaz; kirpilmis getiri kullanilmaz. Donem sonu, delist ve karantina
kurallari onceliklidir.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import pencere

DORT_SAAT = pd.Timedelta(hours=4)
SINIRSIZ = dict(donem_bitis=None, karantina_aylari=None, kume_bitis=None)


def _izgara(bas: str, adet: int, bar=config.BAR_4H) -> pd.DatetimeIndex:
    return pd.date_range(bas, periods=adet, freq=pencere.adim(bar), tz="UTC")


def _bosluklu(zamanlar: pd.DatetimeIndex, hedef: pd.Timestamp, kayma_bar: int, bar=config.BAR_4H):
    """hedef'ten baslayarak `kayma_bar` bari siler: sonraki mevcut bar hedef + kayma_bar x adim."""
    silinecek = pd.date_range(hedef, periods=kayma_bar, freq=pencere.adim(bar), tz="UTC")
    return zamanlar.drop(silinecek)


def _cikis(zamanlar, giris, ufuk, birincil, bar=config.BAR_4H, **sinirlar):
    return pencere.cikis_bari(zamanlar, giris, ufuk, bar, birincil_ufuk=birincil, **{**SINIRSIZ, **sinirlar})


# --- Sinirin kendisi ---------------------------------------------------------


def test_birincil_ufuk_kadar_kayma_kabul_edilir():
    zamanlar = _izgara("2021-01-01", 120)
    giris = zamanlar[5]
    hedef = pencere.cikis_hedefi(giris, 18, config.BAR_4H)
    eksik = _bosluklu(zamanlar, hedef, 18)

    sonuc = _cikis(eksik, giris, 18, 18)
    assert sonuc.zaman == hedef + 18 * DORT_SAAT
    assert sonuc.fiyat_alani == "open" and sonuc.kaydi is True


def test_birincil_ufuktan_uzun_kayma_olay_olusturmaz():
    zamanlar = _izgara("2021-01-01", 120)
    giris = zamanlar[5]
    hedef = pencere.cikis_hedefi(giris, 18, config.BAR_4H)
    eksik = _bosluklu(zamanlar, hedef, 19)

    with pytest.raises(pencere.IleriKaymaSiniriHatasi):
        _cikis(eksik, giris, 18, 18)


def test_ikincil_ufuk_birincil_ufkun_sinirini_kullanir():
    """6 barlik ikincil ufukta 10 barlik kayma: sinir 6 degil 18 bardir."""
    zamanlar = _izgara("2021-01-01", 120)
    giris = zamanlar[5]
    hedef = pencere.cikis_hedefi(giris, 6, config.BAR_4H)
    eksik = _bosluklu(zamanlar, hedef, 10)

    assert _cikis(eksik, giris, 6, 18).zaman == hedef + 10 * DORT_SAAT
    with pytest.raises(pencere.IleriKaymaSiniriHatasi):
        _cikis(_bosluklu(zamanlar, hedef, 19), giris, 6, 18)


def test_uzun_ikincil_ufukta_da_sinir_birincil_ufuktur():
    zamanlar = _izgara("2021-01-01", 200)
    giris = zamanlar[5]
    hedef = pencere.cikis_hedefi(giris, 42, config.BAR_4H)
    assert _cikis(_bosluklu(zamanlar, hedef, 18), giris, 42, 18).kaydi is True
    with pytest.raises(pencere.IleriKaymaSiniriHatasi):
        _cikis(_bosluklu(zamanlar, hedef, 19), giris, 42, 18)


def test_gunluk_barda_sinir_14_gun():
    zamanlar = _izgara("2021-01-01", 120, bar=config.BAR_1D)
    giris = zamanlar[40]
    hedef = pencere.cikis_hedefi(giris, 14, config.BAR_1D)

    kabul = _cikis(_bosluklu(zamanlar, hedef, 14, config.BAR_1D), giris, 14, 14, bar=config.BAR_1D)
    assert kabul.zaman == hedef + pd.Timedelta(days=14)
    with pytest.raises(pencere.IleriKaymaSiniriHatasi):
        _cikis(_bosluklu(zamanlar, hedef, 15, config.BAR_1D), giris, 14, 14, bar=config.BAR_1D)


def test_hedef_mevcutsa_sinir_devreye_girmez():
    zamanlar = _izgara("2021-01-01", 60)
    sonuc = _cikis(zamanlar, zamanlar[5], 18, 1)
    assert sonuc.fiyat_alani == "close" and sonuc.kaydi is False


# --- Oncelik: donem sonu, delist, karantina ----------------------------------


def test_donem_sonu_uzun_boslugun_icindeyse_kirpilir():
    zamanlar = _izgara("2021-01-01", 120)
    giris = zamanlar[5]
    hedef = pencere.cikis_hedefi(giris, 18, config.BAR_4H)
    eksik = _bosluklu(zamanlar, hedef, 30)
    donem_bitis = hedef + 5 * DORT_SAAT  # bosluk icinde

    sonuc = _cikis(eksik, giris, 18, 18, donem_bitis=donem_bitis)
    assert sonuc.kirpildi and sonuc.kirpma_nedeni == "donem_sonu"
    assert sonuc.zaman == hedef - DORT_SAAT


def test_delist_uzun_boslugun_yerine_gecerse_kirpilir():
    zamanlar = _izgara("2021-01-01", 40)
    giris = zamanlar[5]
    hedef = pencere.cikis_hedefi(giris, 18, config.BAR_4H)
    delist = zamanlar[zamanlar < hedef]

    sonuc = _cikis(delist, giris, 18, 18)
    assert sonuc.kirpma_nedeni == "seri_sonu"


def test_karantina_uzun_boslugun_icindeyse_kirpilir():
    zamanlar = _izgara("2021-05-25", 200)
    giris = pd.Timestamp("2021-05-28 00:00", tz="UTC")
    hedef = pencere.cikis_hedefi(giris, 18, config.BAR_4H)  # 05-30 20:00
    eksik = _bosluklu(zamanlar, hedef, 60)  # bosluk haziran icine uzanir

    sonuc = _cikis(eksik, giris, 18, 18, karantina_aylari=["2021-06"])
    assert sonuc.kirpma_nedeni == "karantina"
    assert sonuc.zaman == hedef - DORT_SAAT


def test_kume_siniri_hatasi_ayri_kalir():
    """Kume disina kayma hala KumeSiniriHatasi'dir; iki kural karistirilmaz."""
    zamanlar = _izgara("2021-01-01", 120)
    giris = zamanlar[5]
    hedef = pencere.cikis_hedefi(giris, 18, config.BAR_4H)
    eksik = _bosluklu(zamanlar, hedef, 3)
    with pytest.raises(pencere.KumeSiniriHatasi):
        _cikis(eksik, giris, 18, 18, kume_bitis=hedef + DORT_SAAT)
    assert not issubclass(pencere.IleriKaymaSiniriHatasi, pencere.KumeSiniriHatasi)


# --- Zorunluluk --------------------------------------------------------------


def test_birincil_ufuk_unutulursa_hata():
    zamanlar = _izgara("2021-01-01", 60)
    with pytest.raises(TypeError):
        pencere.cikis_bari(zamanlar, zamanlar[5], 18, config.BAR_4H, **SINIRSIZ)


@pytest.mark.parametrize("deger,hata", [(None, TypeError), (True, TypeError), (18.0, TypeError), ("18", TypeError), (0, ValueError), (-18, ValueError)])
def test_birincil_ufuk_gecersiz_deger_reddedilir(deger, hata):
    zamanlar = _izgara("2021-01-01", 60)
    with pytest.raises(hata):
        _cikis(zamanlar, zamanlar[5], 18, deger)
