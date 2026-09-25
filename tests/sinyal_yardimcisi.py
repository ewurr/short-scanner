"""Tek karar noktasi testlerinin ortak sinyal girdisi (F1 kapanis turu, denetci D-B1).

`pozisyon.olay_karari` hipotezin butun sinyal degerlerini (`pozisyon.SINYAL_DEGERLERI`) ister. Testler
pencere degerlerini sinamiyorsa hepsini 1.0 verir; tek bir degeri bozmak icin anahtar sozcukle
degistirir. Aga cikmaz.
"""

from __future__ import annotations

from data import pozisyon


def sinyal(hipotez: str, **degisen) -> dict:
    """Hipotezin butun sinyal degerleri 1.0; `degisen` ile verilenler (yalnizca gecerli adlar) degistirilir."""
    degerler = {ad: 1.0 for ad in pozisyon.SINYAL_DEGERLERI[hipotez]}
    bilinmeyen = sorted(set(degisen) - set(degerler))
    if bilinmeyen:
        raise KeyError(f"{hipotez} sinyal degeri degil: {bilinmeyen}")
    degerler.update(degisen)
    return degerler


def ilk_ad(hipotez: str) -> str:
    return pozisyon.SINYAL_DEGERLERI[hipotez][0]
