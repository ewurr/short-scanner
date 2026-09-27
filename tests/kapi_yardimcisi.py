"""Tek karar noktasi testlerinin sentetik donem kayitlari (kapi sertlestirme turu, denetci F1K2 D-B2).

`pozisyon.olay_karari` donem sinirlarini cagirandan almaz; commit edilmis evren tablosundan sembol ve donem
numarasiyla okur (`pozisyon.donem_kaydi`) ve sembolun grubunu bolme tablosundan denetler (`grup_dogrula`).
Sentetik fiyat serisi kullanan testler donemlerini burada kaydeder: `donem(bas, bitis)` deterministik bir
sentetik sembol adi uretir, kaydi `SENTETIK_DONEMLER`e yazar ve `olay_karari`nin anahtar sozcuklerini
(`sembol`, `donem_no`) doner. `tests/conftest.py`deki otomatik fikstur `pozisyon._kayitlar`i GERCEK
kayitlar + sentetik kayitlar birlesimiyle degistirir; gercek tablo okuma yolu (`_kayitlar`in kendisi) her
testte calisir ve gercek semboller testlerde de kullanilabilir. Sentetik adlar `TEST` onekiyle baslar ve
gercek evrende yoktur. Aga cikmaz.
"""

from __future__ import annotations

import hashlib
from types import MappingProxyType

import pandas as pd

from data import pencere

SENTETIK_DONEMLER: dict[tuple[str, int], tuple[pd.Timestamp, pd.Timestamp, bool]] = {}
SENTETIK_GRUPLAR: dict[str, str] = {}


def donem(bas, bitis, *, grup: str = "A", funding_yok: bool = False) -> dict:
    """Sentetik bir listeleme donemi kaydeder; `{"sembol": ..., "donem_no": 0}` doner. Varsayilan grup A:
    KESIF ve C2 kumelerine aittir (C1 icin `grup="B"`)."""
    b = pencere.donem_siniri(bas, "bas")
    s = pencere.donem_siniri(bitis, "bitis")
    ozet = hashlib.sha1(f"{b.isoformat()}|{s.isoformat()}|{grup}|{funding_yok}".encode()).hexdigest()[:12].upper()
    sembol = f"TEST{ozet}USDT"
    SENTETIK_DONEMLER[(sembol, 0)] = (b, s, bool(funding_yok))
    SENTETIK_GRUPLAR[sembol] = grup
    return {"sembol": sembol, "donem_no": 0}


def birlesik_kayitlar(gercek):
    """`pozisyon._kayitlar` yerine gecen fonksiyonu kurar: gercek kayitlar + sentetik kayitlar."""

    def _kayitlar():
        donemler, gruplar = gercek()
        return (MappingProxyType({**donemler, **SENTETIK_DONEMLER}),
                MappingProxyType({**gruplar, **SENTETIK_GRUPLAR}))

    return _kayitlar
