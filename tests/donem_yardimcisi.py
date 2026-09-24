"""Testler icin donem yardimcisi.

`klines.gunluge_cevir` rev.8'den beri sembolun listeleme donemlerini zorunlu alir
(on-kayit §2 rev.8 "1 gunluk barlar"). Donem sinirlariyla ilgilenmeyen testler,
serinin ilk ve son barini kapsayan tek bir donem verir.
"""

from __future__ import annotations

import pandas as pd

import config
from data.donem import Donem

# Toplam donemin sinirlari (on-kayit §2 "Toplam donem"): donem basi ve son 4h barin acilisi (B).
# Donem siniriyla ilgilenmeyen pencere ve uygunluk testleri bunlari GERCEK donem siniri olarak verir;
# donem siniri None olamaz (denetci bulgusu D-C6). Verisi toplam donem icinde olan testte sonuc
# `None` ile birebir aynidir: pencere donem basini asamaz, donem uyeligi her bar icin saglanir.
TOPLAM_DONEM_BASI = pd.Timestamp(config.DONEM_BASI)
TOPLAM_DONEM_B = pd.Timestamp(config.DONEM_SONU).floor("4h")


def tum_seri_donemi(cerceve: pd.DataFrame) -> list[Donem]:
    """Cercevenin ilk barindan son barina tek donem (sentetik testler icin)."""
    z = pd.DatetimeIndex(cerceve["open_time"]).sort_values()
    return [Donem(z[0], z[-1], len(z), len(z))]
