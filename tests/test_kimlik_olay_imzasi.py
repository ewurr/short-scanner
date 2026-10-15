"""Sizinti bulgusu S-C1: olayin imzasi POZISYONU da kapsar (on-kayit §4 rev.12).

On-kayit §4 "Olayin kumede olusma olcutu" (rev.12): "dizi kurallarindan gecmemis bir onay olay
DEGILDIR ve hicbir hesaba, hicbir kontrol olcutune girmez." Olay nesnesi bu yuzden imzalidir.

Bulgu: `_olay_imzasi` pozisyonun KENDI `_imza` ALANINI karistiriyordu; `dataclasses.replace` o
alani oldugu gibi kopyaladigi icin `p1` ya da `funding_toplami` bozulmus bir pozisyon tasiyan olay
dogrulamayi geciyordu. `pozisyon.onay_dogrula` imzayi ALANLARDAN yeniden hesaplar, bu yuzden
`olay_dogrula` artik onu da cagiriyor.

Aga cikmaz; getiri hesaplanmaz.
"""

from __future__ import annotations

import dataclasses

import pandas as pd
import pytest

import config
from data import dizi, ornekleme, pozisyon
from dizi_yardimcisi import olaylar_kur, tek_olay
from ornekleme_yardimcisi import k1_adaylari_kur

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
UFUK = config.BIRINCIL_UFUK[config.BAR_4H]
TB = T("2025-03-10 04:00")
BARLAR = [T("2025-03-01") + i * H4 for i in range(10)]


def _bozuk_olay(**degisen) -> dizi.Olay:
    """Pozisyonu degistirilmis, ama olayin kendi alanlari degismemis bir olay."""
    olay = tek_olay(TB)
    return dataclasses.replace(olay, pozisyon=dataclasses.replace(olay.pozisyon, **degisen))


# --- 1. Bozulmus pozisyon tasiyan olay reddedilir ---------------------------------------------


@pytest.mark.parametrize("alan,deger", [("p1", 0.5), ("p0", 2.0), ("funding_toplami", 0.01),
                                        ("gecersizlik_seviyesi", 3.0), ("sembol", "ZZZUSDT"),
                                        ("kume", "C1"), ("donem_no", 7)])
def test_bozulmus_pozisyon_tasiyan_olay_reddedilir(alan, deger):
    bozuk = _bozuk_olay(**{alan: deger})
    with pytest.raises(ValueError, match="OnaylanmisPozisyon|elle kurulmus|degistirilmis"):
        dizi.olay_dogrula(bozuk)


def test_pozisyonu_imzasiz_nesneyle_degistirilmis_olay_reddedilir():
    olay = tek_olay(TB)
    for sahte in (None, "onay", 1.0, object()):
        with pytest.raises((TypeError, ValueError)):
            dizi.olay_dogrula(dataclasses.replace(olay, pozisyon=sahte))


def test_havuz_olcutu_de_bozulmus_olayi_reddeder():
    """Ayni denetim `ornekleme`nin olcut girdisinde de isler (denetci bulgusu D-B2 ile birlikte)."""
    bozuk = _bozuk_olay(p1=0.5)
    with pytest.raises(ValueError):
        ornekleme.k1_adaylari(k1_adaylari_kur(BARLAR), [bozuk], UFUK, config.BAR_4H)


# --- 2. Degismemis olay gecer; iddialar korundu -----------------------------------------------


def test_gercek_olay_gecer():
    for olay in olaylar_kur([BARLAR[0]]):
        dizi.olay_dogrula(olay)
        pozisyon.onay_dogrula(olay.pozisyon)


def test_olayin_kendi_alanlarinin_degismesi_de_reddedilir():
    """Rev.13'te kurulan denetim korundu (zaman ve capa imzada)."""
    olay = tek_olay(TB)
    for degisen in ({"zaman": TB + H4}, {"capa": TB}):
        with pytest.raises(ValueError, match="elle kurulmus|degistirilmis"):
            dizi.olay_dogrula(dataclasses.replace(olay, **degisen))


def test_elle_kurulmus_olay_reddedilir():
    with pytest.raises(ValueError, match="elle kurulmus"):
        dizi.olay_dogrula(dizi.Olay(TB, None, tek_olay(TB).pozisyon))
