"""Kontrol havuzu testlerinin aday kurucusu (on-kayit §6 "Ornekleme kurallari", rev.13).

Rev.13 ile adaylik ornekelemeden ONCE belirlenir ve `data.ornekleme` ham bar damgasi ya da sembol
adi kabul etmez: adaylar tek karar noktasinin (`pozisyon.olay_karari`, `rol="K1"` / `rol="K2"`)
urettigi onayli pozisyonlardan `ornekleme.adaylari_kur` ile kurulur. Ornekleme KURALLARINI
(yakinlik, iadesizlik, 10'dan az aday, alt tohum) sinayan testler icin kapiyi gercek veriyle
cagirmak hem yavas olur hem de testin sinadigi seyi veri kurulumuna gomer; bu yardimci aradaki
onaylari `pozisyon._test_onayi` ile kurar (veri yuklemeden, imzali; yalnizca pytest icinde).

Aga cikmaz; getiri hesaplanmaz.
"""

from __future__ import annotations

import pandas as pd

from data import ornekleme, pozisyon, sinyal

VARSAYILAN = {"hipotez": "H2", "kume": "KESIF", "sembol": "AAVEUSDT"}


def _yap(hipotez, yapilandirma):
    return dict(sinyal.izgara(hipotez)[0]) if yapilandirma is None else yapilandirma


def k1_adaylari_kur(barlar, *, hipotez: str = "H2", yapilandirma=None, kume: str = "KESIF",
                    sembol: str = "AAVEUSDT") -> ornekleme.Adaylar:
    """Verilen bar zamanlarini K1 ADAYI yapar (ayni coin, ayni kume, ayni yapilandirma)."""
    y = _yap(hipotez, yapilandirma)
    onaylar = [pozisyon._test_onayi(hipotez=hipotez, yapilandirma=y, t=t, rol="K1", sembol=sembol,
                                    kume=kume) for t in pd.DatetimeIndex(barlar)]
    return ornekleme.adaylari_kur(onaylar, rol="K1")


def k2_adaylari_kur(semboller, *, t, hipotez: str = "H2", yapilandirma=None,
                    kume: str = "KESIF") -> ornekleme.Adaylar:
    """Verilen sembolleri AYNI t barinda K2 ADAYI yapar."""
    y = _yap(hipotez, yapilandirma)
    onaylar = [pozisyon._test_onayi(hipotez=hipotez, yapilandirma=y, t=t, rol="K2", sembol=s,
                                    kume=kume) for s in semboller]
    return ornekleme.adaylari_kur(onaylar, rol="K2")


def ornekle(adaylar: ornekleme.Adaylar, *, sembol: str = "AAVEUSDT", olay_zamani=None, **ek):
    """`ornekleme.ornekle`; olay zamani verilmezse sabit bir deterministik an kullanilir."""
    t = pd.Timestamp("2025-03-01", tz="UTC") if olay_zamani is None else olay_zamani
    return ornekleme.ornekle(adaylar, sembol=sembol, olay_zamani=t, **ek)
