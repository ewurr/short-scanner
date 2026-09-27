"""Tek karar noktasi testlerinin ortak kume siniri girdisi (F1 kapanis turu 2, Rev.10 denetci D-C3).

`pozisyon.olay_karari` kume sinirini `None` olarak kabul etmez: her olay ve kontrol bir kumeye aittir
(on-kayit §3). Testler kume sinirini burada, `config`'teki gercek kume sinirlarindan (on-kayit §3
"Donemler") alir. Kume kurallarini sinamayan testlerde sinyal zamaninin ait oldugu gercek kume verilir.
Aga cikmaz.
"""

from __future__ import annotations

import pandas as pd

import config

KESIF = {"kume_baslangic": pd.Timestamp(config.KESIF_BASI), "kume_bitis": pd.Timestamp(config.KESIF_SONU)}
C2 = {"kume_baslangic": pd.Timestamp(config.C2_BASI), "kume_bitis": pd.Timestamp(config.C2_SONU)}


def kume_sinirlari(t) -> dict:
    """`t` aninin ait oldugu gercek kumenin sinirlari (KESIF/C1 ayni tarih araligi, C2), `olay_karari`nin
    anahtar sozcukleriyle. Hicbir kumeye dusmeyen `t` testin kurulus hatasidir: ValueError."""
    zaman = pd.Timestamp(t)
    for sinir in (KESIF, C2):
        if sinir["kume_baslangic"] <= zaman <= sinir["kume_bitis"]:
            return dict(sinir)
    raise ValueError(f"{zaman} hicbir gercek kumenin tarih araliginda degil (on-kayit §3 'Donemler').")


def kume_adi(t) -> str:
    """`t` aninin ait oldugu gercek kumenin ADI (KESIF ya da C2), `olay_karari(kume=...)` icin (kapi
    sertlestirme turu: kapi sinirlari kume adindan kendisi okur). Hicbir kumeye dusmeyen `t`: ValueError."""
    sinir = kume_sinirlari(t)
    return "KESIF" if sinir == KESIF else "C2"
