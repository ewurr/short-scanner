"""`dizi.olay_dizisi` icin test cagri yardimcisi: donem sinirlarini `zamanlar`dan turetir.

P-C3 (F1 kapatma turu madde 1d) ile `olay_dizisi` dizinin DONEM SINIRLARINI zorunlu argüman
olarak alir ve her barin o donemin (ve kumenin) icinde oldugunu dogrular. Dizi KURALLARINI
(bekleme suresi, H1'de tek izleme, H3'te ilk gun) sinayan testlerin konusu sinirlar degildir:
hepsi "butun barlar ayni donemin icinde" kurgusunu varsayar. Bu yardimci o kurguyu tek yerde
kurar -- sinirlari verilen barlarin ucundan turetir -- boylece testlerin beklentileri
degismeden kalir.

Sinirlarin DOGRULANMASI ayri bir test dosyasinda sinanir
(`tests/test_f1_dizi_donem_siniri.py`); orada `dizi.olay_dizisi` dogrudan cagrilir.

Aga cikmaz.
"""

from __future__ import annotations

import pandas as pd

import config
from data import dizi, pencere

# Bozuk `zamanlar` girdileriyle (tz'siz, sirasiz, tekrarli) cagrilan testler icin: sinir
# turetilemezse cok genis bir aralik verilir ve denetim `olay_dizisi`nin kendi girdi
# dogrulamasina kalir (testin sinadigi hata orada firlatilir).
GENIS_BAS = pd.Timestamp("2019-01-01", tz="UTC")
GENIS_SON = pd.Timestamp("2027-01-01", tz="UTC")


def sinirlar(zamanlar, bar: str) -> dict:
    """Verilen barlari kapsayan en kucuk donem sinirlari (`donem_baslangic`, `donem_bitis`)."""
    try:
        indeks = pd.DatetimeIndex(zamanlar)
        if len(indeks) == 0 or indeks.tz is None:
            raise ValueError
        bas, son = indeks.min(), indeks.max()
        if bar == config.BAR_1D:
            # 1d bar donem ici sayilmasi icin gunun ALTI 4h barinin tamami donem ici olmali.
            son = son + pencere.GUNUN_SON_4H_BARI
        return {"donem_baslangic": bas, "donem_bitis": son}
    except Exception:
        return {"donem_baslangic": GENIS_BAS, "donem_bitis": GENIS_SON}


def cagir(hipotez, yapilandirma, zamanlar, bar: str, **ek):
    """`dizi.olay_dizisi`, donem sinirlari verilmediyse `zamanlar`dan turetilerek."""
    if "donem_baslangic" not in ek and "donem_bitis" not in ek:
        ek.update(sinirlar(zamanlar, bar))
    return dizi.olay_dizisi(hipotez, yapilandirma, zamanlar, bar, **ek)
