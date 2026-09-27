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

import config
from data import pencere, split

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


# --- Sentetik veri (kapi sertlestirme turu 2) -------------------------------------------------------
#
# Karar noktasi fiyat ve funding cercevelerini cagirandan almaz; `pozisyon._veri_yukle` ile sembol ve kume
# adindan yukler. Testler sentetik seriyi `veri(...)` ile kaydeder; `tests/conftest.py` otomatik fiksturu
# `_veri_yukle`yi sentetik semboller icin bu kayitla, gercek semboller icin gercek yukleyiciyle cevaplar.
# 1d serisi kapida 4h barlardan turetildigi icin (on-kayit §2 "1 gunluk barlar"), eski testlerin ayri
# verdigi uygunluk 1d cercevesinin karsiligi burada 4h serisinin ONCESINE eklenen duz, hacimli barlardir
# (`uygun_bas`'tan fiksturun ilk barina kadar). Fiksturun kendi barlari degistirilmez.

SENTETIK_VERI: dict[str, tuple[pd.DataFrame, pd.DataFrame]] = {}
_SAYAC = [0]
_ADIM = pd.Timedelta(hours=4)
_BAR_BASINA = 6  # 4h barlik gunde alti bar


def _gun_hacmi(zamanlar: pd.DatetimeIndex, hacim: float):
    """Gunun butun quote hacmi 00:00 barinda, digerleri 0: gunluk toplam tam `hacim` olur (kayan nokta
    bolmesi esik testlerinde esitligi bozmasin)."""
    import numpy as np

    return np.where(pd.DatetimeIndex(zamanlar).hour == 0, float(hacim), 0.0)


def _hazirla(mumlar: pd.DataFrame, *, uygun_bas, hacim: float, eksik_gunler) -> pd.DataFrame:
    m = mumlar.copy().sort_values("open_time").reset_index(drop=True)
    m["open_time"] = pd.DatetimeIndex(m["open_time"])
    if uygun_bas is not None and len(m):
        bas = pd.Timestamp(uygun_bas).floor("D")
        ilk = m["open_time"].iloc[0]
        if bas < ilk:
            onek = pd.date_range(bas, ilk - _ADIM, freq=_ADIM)
            fiyat = float(m["open"].iloc[0])
            m = pd.concat([pd.DataFrame({"open_time": onek, "open": fiyat, "high": fiyat, "low": fiyat,
                                         "close": fiyat, "quote_volume": _gun_hacmi(onek, hacim)}), m],
                          ignore_index=True)
    if "quote_volume" not in m:
        m["quote_volume"] = _gun_hacmi(pd.DatetimeIndex(m["open_time"]), hacim)
    else:
        m["quote_volume"] = m["quote_volume"].fillna(
            pd.Series(_gun_hacmi(pd.DatetimeIndex(m["open_time"]), hacim), index=m.index))
    varsayilan = {"volume": 1.0, "count": 1, "taker_buy_volume": 0.0, "taker_buy_quote_volume": 0.0}
    for sutun, deger in varsayilan.items():
        if sutun not in m:
            m[sutun] = deger
        else:
            m[sutun] = m[sutun].fillna(deger)
    if "close_time" not in m:
        m["close_time"] = m["open_time"] + _ADIM - pd.Timedelta(milliseconds=1)
    else:
        m["close_time"] = m["close_time"].fillna(m["open_time"] + _ADIM - pd.Timedelta(milliseconds=1))
    if eksik_gunler:
        gunler = {pd.Timestamp(g).floor("D") for g in eksik_gunler}
        m = m.loc[~pd.DatetimeIndex(m["open_time"]).floor("D").isin(list(gunler))].reset_index(drop=True)
    return m


def veri(mumlar: pd.DataFrame, funding: pd.DataFrame, bas, bitis, *, uygun_bas=None, hacim: float = 5e7,
         grup: str = "A", funding_yok: bool = False, ham: bool = False, eksik_gunler=()) -> dict:
    """Sentetik bir sembol icin donem + 4h mumlari + funding kaydeder; `olay_karari`nin `sembol` ve
    `donem_no` anahtar sozcuklerini doner. Her cagri yeni bir sembol adi uretir (onceki kayitlar
    degismez; `mae` ve `pozisyon_fundingi` sonradan ayni veriyi yukler).

    - `uygun_bas`: eski `uygunluk(bar, bas, son)` fiksturunun baslangici; 4h serisi fiksturun ilk barindan
      geriye bu gunun basina kadar duz, `hacim` gunluk hacimli barlarla uzatilir (uygunluk penceresi).
    - `hacim`: eklenen barlarin ve hacim sutunu olmayan fikstur barlarinin gunluk quote hacmi.
    - `eksik_gunler`: bu gunlerin butun 4h barlari cikarilir (1d serisinde eksik gun).
    - `ham=True`: cerceve hic degistirilmeden kaydedilir (bicim denetimlerini sinayan testler icin).
    """
    _SAYAC[0] += 1
    sembol = f"TESTV{_SAYAC[0]:06d}USDT"
    b = pencere.donem_siniri(bas, "bas")
    s = pencere.donem_siniri(bitis, "bitis")
    SENTETIK_DONEMLER[(sembol, 0)] = (b, s, bool(funding_yok))
    SENTETIK_GRUPLAR[sembol] = grup
    m = mumlar.copy() if ham else _hazirla(mumlar, uygun_bas=uygun_bas, hacim=hacim, eksik_gunler=eksik_gunler)
    SENTETIK_VERI[sembol] = (m, funding.copy())
    return {"sembol": sembol, "donem_no": 0}


def birlesik_veri_yukle(gercek):
    """`pozisyon._veri_yukle` yerine gecen fonksiyon: sentetik semboller kayittan, gercekler gercek yoldan.
    Verisi kaydedilmemis sentetik sembol (`donem(...)` ile yalniz donem kaydi) KeyError verir."""

    def _veri_yukle(sembol, kume):
        if sembol in SENTETIK_VERI:
            # Gercek yukleyicinin onay kosulu (`split.kume_erisimi`) sentetik yolda da uygulanir: C1/C2 icin
            # ayni kumeye ait acik bir `split.onay_kosusu` sart.
            if kume in config.ONAY_KUMELERI:
                aktif = split.aktif_onay_kosusu()
                if aktif is None or aktif[1] != kume:
                    raise split.OnayGerekli(f"{kume} sentetik verisine yalnizca acik bir onay kosusu icinde erisilir.")
            m, f = SENTETIK_VERI[sembol]
            return m.copy(), f.copy()
        if sembol.startswith("TEST"):
            raise KeyError(f"{sembol}: sentetik verisi kaydedilmemis (kapi_yardimcisi.veri).")
        return gercek(sembol, kume)

    return _veri_yukle
