"""Ileri kaymanin ust siniri testleri (on-kayit §4 rev.6, rev.8).

Hedef cikis bari eksikse ileri kayma, olayin birincil ufku kadar sureyle
sinirlidir (H1, H2: 18 bar; H3: 14 gun). Sonraki mevcut bar bu sinirdan uzaksa
olay olusmaz; kirpilmis getiri kullanilmaz. Donem sonu ve delist
kurallari onceliklidir.

Rev.8 guncellemesi (RESULTS degisiklik kaydi): `cikis_hedefi` hedef cikis anini
(T, hedef barin KAPANISI) verir; testlerdeki `hedef` hedef barin acilisidir
(T - 4 saat) ve ileri kayma ondan olculur (§2 "Ileri kaymanin olcusu"). Seri her
izgarada 4h'tir (§4 "Fiyat okuma tabani"); donem bitisi zorunludur; delist bir
donem sonudur ("seri sonu" kirpmasi yok).
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import pencere

DORT_SAAT = pd.Timedelta(hours=4)


def _izgara(bas: str, adet: int) -> pd.DatetimeIndex:
    return pd.date_range(bas, periods=adet, freq=DORT_SAAT, tz="UTC")


def _hedef_acilis(giris, ufuk, bar=config.BAR_4H) -> pd.Timestamp:
    """Hedef barin acilisi = T - 4 saat."""
    return pencere.cikis_hedefi(giris, ufuk, bar) - DORT_SAAT


def _bosluklu(zamanlar: pd.DatetimeIndex, hedef: pd.Timestamp, sure: pd.Timedelta):
    """hedef'ten baslayarak `sure` boyunca 4h barlari siler: sonraki mevcut bar hedef + sure."""
    return zamanlar[(zamanlar < hedef) | (zamanlar >= hedef + sure)]


def _cikis(zamanlar, giris, ufuk, birincil, bar=config.BAR_4H, **sinirlar):
    varsayilan = dict(donem_bitis=zamanlar[-1], kume_bitis=None)
    return pencere.cikis_bari(zamanlar, giris, ufuk, bar, birincil_ufuk=birincil, **{**varsayilan, **sinirlar})


# --- Sinirin kendisi ---------------------------------------------------------


def test_birincil_ufuk_kadar_kayma_kabul_edilir():
    zamanlar = _izgara("2021-01-01", 120)
    giris = zamanlar[5]
    hedef = _hedef_acilis(giris, 18)
    eksik = _bosluklu(zamanlar, hedef, 18 * DORT_SAAT)

    sonuc = _cikis(eksik, giris, 18, 18)
    assert sonuc.zaman == hedef + 18 * DORT_SAAT
    assert sonuc.fiyat_alani == "open" and sonuc.kaydi is True
    assert sonuc.ileri_kayma == 18 * DORT_SAAT and sonuc.cikis_ani == sonuc.zaman


def test_birincil_ufuktan_uzun_kayma_olay_olusturmaz():
    zamanlar = _izgara("2021-01-01", 120)
    giris = zamanlar[5]
    hedef = _hedef_acilis(giris, 18)
    eksik = _bosluklu(zamanlar, hedef, 19 * DORT_SAAT)

    with pytest.raises(pencere.IleriKaymaSiniriHatasi):
        _cikis(eksik, giris, 18, 18)


def test_ikincil_ufuk_birincil_ufkun_sinirini_kullanir():
    """6 barlik ikincil ufukta 10 barlik kayma: sinir 6 degil 18 bardir."""
    zamanlar = _izgara("2021-01-01", 120)
    giris = zamanlar[5]
    hedef = _hedef_acilis(giris, 6)
    eksik = _bosluklu(zamanlar, hedef, 10 * DORT_SAAT)

    assert _cikis(eksik, giris, 6, 18).zaman == hedef + 10 * DORT_SAAT
    with pytest.raises(pencere.IleriKaymaSiniriHatasi):
        _cikis(_bosluklu(zamanlar, hedef, 19 * DORT_SAAT), giris, 6, 18)


def test_uzun_ikincil_ufukta_da_sinir_birincil_ufuktur():
    zamanlar = _izgara("2021-01-01", 200)
    giris = zamanlar[5]
    hedef = _hedef_acilis(giris, 42)
    assert _cikis(_bosluklu(zamanlar, hedef, 18 * DORT_SAAT), giris, 42, 18).kaydi is True
    with pytest.raises(pencere.IleriKaymaSiniriHatasi):
        _cikis(_bosluklu(zamanlar, hedef, 19 * DORT_SAAT), giris, 42, 18)


def test_gunluk_barda_sinir_14_gun():
    """1d izgarasinda da fiyat 4h barlardan okunur; sinir 14 x 24 saat, hedef barin
    (T - 4 saat) acilisindan olculur."""
    zamanlar = _izgara("2021-01-01", 120 * 6)
    giris = pd.Timestamp("2021-02-10", tz="UTC")  # 1d t = 2021-02-09
    hedef = _hedef_acilis(giris, 14, config.BAR_1D)
    assert hedef == pd.Timestamp("2021-02-23 20:00", tz="UTC")

    kabul = _cikis(_bosluklu(zamanlar, hedef, pd.Timedelta(days=14)), giris, 14, 14, bar=config.BAR_1D)
    assert kabul.zaman == hedef + pd.Timedelta(days=14) and kabul.kaydi
    with pytest.raises(pencere.IleriKaymaSiniriHatasi):
        _cikis(_bosluklu(zamanlar, hedef, pd.Timedelta(days=14) + DORT_SAAT), giris, 14, 14, bar=config.BAR_1D)


def test_hedef_mevcutsa_sinir_devreye_girmez():
    zamanlar = _izgara("2021-01-01", 60)
    sonuc = _cikis(zamanlar, zamanlar[5], 18, 1)
    assert sonuc.fiyat_alani == "close" and sonuc.kaydi is False


# --- Oncelik: donem sonu, delist --------------------------------------------


def test_donem_sonu_uzun_boslugun_icindeyse_kirpilir():
    """Uzun bosluk donemi boler; donem bitisi B bosluktan onceki son bardir (rev.8'de B
    her zaman mevcut bir bardir; rev.7 testi B'yi boslugun icine koyuyordu). T > K:
    donem sonu, B'deki barin kapanisi."""
    zamanlar = _izgara("2021-01-01", 120)
    giris = zamanlar[5]
    hedef = _hedef_acilis(giris, 18)
    eksik = _bosluklu(zamanlar, hedef, 30 * DORT_SAAT)
    donem_bitis = hedef - DORT_SAAT  # bosluktan onceki son bar

    sonuc = _cikis(eksik, giris, 18, 18, donem_bitis=donem_bitis)
    assert sonuc.kirpildi and sonuc.kirpma_nedeni == "donem_sonu"
    assert sonuc.zaman == hedef - DORT_SAAT and sonuc.cikis_ani == hedef


def test_delist_uzun_boslugun_yerine_gecerse_kirpilir():
    """Rev.8 §4: "Ufuk icinde sozlesme delist olursa bu bir donem sonudur";
    beklenti "seri_sonu" -> "donem_sonu"."""
    zamanlar = _izgara("2021-01-01", 40)
    giris = zamanlar[5]
    hedef = _hedef_acilis(giris, 18)
    delist = zamanlar[zamanlar < hedef]

    sonuc = _cikis(delist, giris, 18, 18)
    assert sonuc.kirpma_nedeni == "donem_sonu" and sonuc.zaman == delist[-1]


def test_kume_siniri_hatasi_ayri_kalir():
    """Kume disina kayma hala KumeSiniriHatasi'dir; iki kural karistirilmaz."""
    zamanlar = _izgara("2021-01-01", 120)
    giris = zamanlar[5]
    hedef = _hedef_acilis(giris, 18)
    eksik = _bosluklu(zamanlar, hedef, 3 * DORT_SAAT)
    with pytest.raises(pencere.KumeSiniriHatasi):
        _cikis(eksik, giris, 18, 18, kume_bitis=hedef + DORT_SAAT)
    assert not issubclass(pencere.IleriKaymaSiniriHatasi, pencere.KumeSiniriHatasi)


# --- Zorunluluk --------------------------------------------------------------


def test_birincil_ufuk_unutulursa_hata():
    zamanlar = _izgara("2021-01-01", 60)
    with pytest.raises(TypeError):
        pencere.cikis_bari(zamanlar, zamanlar[5], 18, config.BAR_4H, donem_bitis=zamanlar[-1], kume_bitis=None)


@pytest.mark.parametrize("deger,hata", [(None, TypeError), (True, TypeError), (18.0, TypeError), ("18", TypeError), (0, ValueError), (-18, ValueError)])
def test_birincil_ufuk_gecersiz_deger_reddedilir(deger, hata):
    zamanlar = _izgara("2021-01-01", 60)
    with pytest.raises(hata):
        _cikis(zamanlar, zamanlar[5], 18, deger)
