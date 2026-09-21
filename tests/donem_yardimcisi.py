"""Testler icin donem yardimcisi.

`klines.gunluge_cevir` rev.8'den beri sembolun listeleme donemlerini zorunlu alir
(on-kayit §2 rev.8 "1 gunluk barlar"). Donem sinirlariyla ilgilenmeyen testler,
serinin ilk ve son barini kapsayan tek bir donem verir.
"""

from __future__ import annotations

import pandas as pd

from data.donem import Donem


def tum_seri_donemi(cerceve: pd.DataFrame) -> list[Donem]:
    """Cercevenin ilk barindan son barina tek donem (sentetik testler icin)."""
    z = pd.DatetimeIndex(cerceve["open_time"]).sort_values()
    return [Donem(z[0], z[-1], len(z), len(z))]
