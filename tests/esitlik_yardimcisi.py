"""Skaler referans esitlik testlerinin ortak yardimcisi (performans 2a; plan v2 karar 3).

Sentetik bir "dunya" kurar: rastgele yuruyus fiyatlari, enjekte edilmis pump ve dusus kesitleri, eksik barlar
(uzun ve tek bar bosluk), bozuk hucreli bir bar, donem icinde gec baslayan, ritmi 8 -> 4 -> 1 saat degisen, bir
kaydi eksik ve bir orani NaN olan funding serisi. Dunya `kapi_yardimcisi.veri` ile kaydedilir; kapi ve referans
veriyi AYNI yoldan (`pozisyon._karar_verisi`) okur. Deger raporlanmaz: testler yalnizca iki yolun sonucunun
ayni oldugunu (ret gerekcesi sinifi ya da onayli pozisyonun butun alanlari) denetler. Aga cikmaz.
"""

from __future__ import annotations

import dataclasses
import math

import numpy as np
import pandas as pd

import config
from kapi_yardimcisi import veri
from uygunluk_yardimcisi import esikler

H4 = pd.Timedelta(hours=4)


def _utc(x) -> pd.Timestamp:
    z = pd.Timestamp(x)
    return z.tz_localize("UTC") if z.tzinfo is None else z.tz_convert("UTC")


def dunya(tohum: int, bas, bitis, *, funding_gec_gun: int = 45, funding_yok: bool = False) -> tuple[dict, dict]:
    """Sentetik donem + 4h mumlari + funding. Doner: (`olay_karari`nin `sembol`, `donem_no` anahtar sozcukleri,
    enjekte edilen kesitlerin barlari: "pump" (H1 pump bari), "h2" (H2 kirilim bari))."""
    rng = np.random.default_rng(tohum)
    b, s = _utc(bas), _utc(bitis)
    z = pd.date_range(b, s, freq=H4)
    n = len(z)
    gun = np.asarray((z - b) / pd.Timedelta(days=1), dtype=float)
    adim = rng.normal(0.0, 0.03, n)
    hacim = rng.lognormal(np.log(6e6), 0.5, n)
    # Pump + dusus kesitleri (H1 pump ve teyit adaylari); pump bari i + 5.
    pumplar = list(range(200, n - 30, 170))
    for i in pumplar:
        adim[i:i + 6] += 0.08
        hacim[i:i + 6] *= 8.0
        adim[i + 6:i + 14] -= 0.05
    # H2 kesitleri: 30 bar yukselis, sonra sert kirilim (bar j).
    h2 = [j for j in range(290, n - 30, 340)]
    for j in h2:
        adim[j - 30:j] += 0.025
        adim[j] -= 0.35
    # H3 adayi: son 50 gunde hacim duser, fiyat asagi kayar; 4h uygunlugu da bu kesitte duser.
    gec = gun >= gun[-1] - 50
    hacim[gec] *= 0.25
    adim[gec] -= 0.004
    kapanis = 10.0 * np.exp(np.cumsum(adim))
    acilis = np.r_[10.0, kapanis[:-1]]
    yuksek = np.maximum(acilis, kapanis) * (1 + np.abs(rng.normal(0, 0.01, n)))
    dusuk = np.minimum(acilis, kapanis) * (1 - np.abs(rng.normal(0, 0.01, n)))
    m = pd.DataFrame({"open_time": z, "open": acilis, "high": yuksek, "low": dusuk, "close": kapanis,
                      "volume": hacim / kapanis, "quote_volume": hacim, "count": 10,
                      "taker_buy_volume": 0.0, "taker_buy_quote_volume": 0.0,
                      "close_time": z + H4 - pd.Timedelta(milliseconds=1)})
    # Bosluklar: 60. gunden 3 gun, 100. gunde tek bar; 120. gunde bozuk hucreli bar.
    dus = ((gun >= 60) & (gun < 63)) | (np.abs(gun - 100.5) < 1e-9)
    m.loc[np.abs(gun - 120.5) < 1e-9, "volume"] = np.nan
    m = m.loc[~dus].reset_index(drop=True)
    # Funding: donem basindan `funding_gec_gun` sonra baslar (varsayilan 45: uygunlugun 30 gunluk listeleme yasindan
    # sonra, yani capasiz pozisyonlar `FundingTamDegil` olur); ritim 8 -> 4 -> 1 saat.
    zamanlar, araliklar = [], []
    t = b + pd.Timedelta(days=funding_gec_gun)
    while t <= s + H4:
        g = (t - b) / pd.Timedelta(days=1)
        a = 8.0 if g < 80 else (4.0 if g < 140 else 1.0)
        zamanlar.append(t)
        araliklar.append(a)
        t = t + pd.Timedelta(hours=a)
    f = pd.DataFrame({"odeme_zamani": pd.DatetimeIndex(zamanlar), "aralik_saat": araliklar})
    f["oran"] = rng.normal(0.0002, 0.0003, len(f))
    fg = np.asarray((f["odeme_zamani"] - b) / pd.Timedelta(days=1), dtype=float)
    f.loc[np.argmin(np.abs(fg - 130.3)), "oran"] = np.nan
    # H2 kesitlerinden onceki 30 saatte funding yuksek (funding_24s esigi).
    for j in h2:
        yakin = np.asarray((f["odeme_zamani"] > z[j] - pd.Timedelta(hours=30)) & (f["odeme_zamani"] <= z[j]))
        f.loc[yakin, "oran"] = 0.0015 * f.loc[yakin, "aralik_saat"] / 8.0
    f = f.drop(index=int(np.argmin(np.abs(fg - 100.2)))).reset_index(drop=True)
    f["oran_8h"] = f["oran"] * 8.0 / f["aralik_saat"]
    kimlik = veri(m, f, b, s, ham=True, funding_yok=funding_yok)
    return kimlik, {"pump": [z[i + 5] for i in pumplar], "h2": [z[j] for j in h2]}


def karar_cagrisi(modul, hipotez, kimlik, t, *, kume="KESIF", yapilandirma=None, rol="K1", capa=None, ufuk=None):
    """`modul.olay_karari` cagrisi (modul: `data.pozisyon` ya da `data._skaler_referans`); sonuc ya da hata."""
    from data import pencere, sinyal

    tanim = pencere.hipotez_ufuklari(hipotez)
    y = dict(sinyal.izgara(hipotez)[0]) if yapilandirma is None else yapilandirma
    try:
        return modul.olay_karari(t, tanim.birincil if ufuk is None else ufuk, tanim.bar, hipotez=hipotez,
                                 yapilandirma=y, rol=rol, capa=capa, birincil_ufuk=tanim.birincil, kume=kume,
                                 **kimlik, **esikler(tanim.bar))
    except Exception as hata:  # noqa: BLE001 - sinif karsilastirilir
        return hata


def kosul_cagrisi(modul, hipotez, kimlik, t, *, kume="KESIF", yapilandirma=None, capa=None):
    from data import sinyal

    y = dict(sinyal.izgara(hipotez)[0]) if yapilandirma is None else yapilandirma
    try:
        return modul.sinyal_kosulu(t, hipotez=hipotez, yapilandirma=y, capa=capa, kume=kume, **kimlik)
    except Exception as hata:  # noqa: BLE001
        return hata


def _deger_esit(a, b) -> bool:
    if type(a) is not type(b):
        return False
    if dataclasses.is_dataclass(a):
        return all(_deger_esit(getattr(a, f.name), getattr(b, f.name)) for f in dataclasses.fields(a) if f.compare)
    if isinstance(a, float):
        return (math.isnan(a) and math.isnan(b)) or a == b
    if a is pd.NaT or b is pd.NaT:
        return a is b
    return bool(a == b)


def sonuc_esit(a, b) -> bool:
    """Iki yolun sonucu ayni mi? Hata: ayni sinif. Onayli pozisyon: bütün alanlar (`compare=True`), NaN konumu
    dahil (NaN == NaN sayilir; `==` NaN'da False verir). Kosul: ayni deger ve ayni tur (`True`/`False`/`None`)."""
    if isinstance(a, BaseException) or isinstance(b, BaseException):
        return type(a) is type(b)
    return _deger_esit(a, b)


def sinif(x) -> str:
    """Sonucun sinifi (rapor icin; deger icermez)."""
    if isinstance(x, BaseException):
        return type(x).__name__
    if x is None or isinstance(x, bool):
        return repr(x)
    return type(x).__name__


def ornek_barlar(kimlik, adet: int, tohum: int, bar: str = config.BAR_4H, sinir: int = 10) -> list[pd.Timestamp]:
    """Dunyanin donemindeki barlardan tohumlu `adet` bar + donemin ilk ve son `sinir` bari (sinir barlari)."""
    from data import pozisyon

    bas, bitis, _ = pozisyon.donem_kaydi(kimlik["sembol"], kimlik["donem_no"])
    adim = H4 if bar == config.BAR_4H else pd.Timedelta(days=1)
    z = pd.date_range(bas, bitis, freq=adim)
    rng = np.random.default_rng(tohum)
    secim = set(rng.choice(len(z), size=min(adet, len(z)), replace=False).tolist())
    secim |= set(range(min(sinir, len(z)))) | set(range(max(0, len(z) - sinir), len(z)))
    return [z[i] for i in sorted(secim)]
