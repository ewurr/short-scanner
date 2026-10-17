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

import config
from data import ornekleme, pencere, pozisyon, sinyal

VARSAYILAN = {"hipotez": "H2", "kume": "KESIF", "sembol": "AAVEUSDT"}


def _yap(hipotez, yapilandirma):
    return dict(sinyal.izgara(hipotez)[0]) if yapilandirma is None else yapilandirma


def k1_adaylari_kur(barlar, *, hipotez: str = "H2", yapilandirma=None, kume: str = "KESIF",
                    sembol: str = "AAVEUSDT", donem_no: int = 0) -> ornekleme.Adaylar:
    """Verilen bar zamanlarini K1 ADAYI yapar (ayni coin, ayni kume, ayni yapilandirma).

    Kimlik argumanlari her zaman verilir: bos aday kumesinde zorunludurlar (madde 3d, bulgu K-C5).
    """
    y = _yap(hipotez, yapilandirma)
    onaylar = [pozisyon._test_onayi(hipotez=hipotez, yapilandirma=y, t=t, rol="K1", sembol=sembol,
                                    kume=kume, donem_no=donem_no) for t in pd.DatetimeIndex(barlar)]
    return ornekleme.adaylari_kur(onaylar, rol="K1", hipotez=hipotez, yapilandirma=y, kume=kume,
                                  sembol=sembol, donem_no=donem_no)


def k2_adaylari_kur(semboller, *, t, hipotez: str = "H2", yapilandirma=None,
                    kume: str = "KESIF") -> ornekleme.Adaylar:
    """Verilen sembolleri AYNI t barinda K2 ADAYI yapar."""
    y = _yap(hipotez, yapilandirma)
    onaylar = [pozisyon._test_onayi(hipotez=hipotez, yapilandirma=y, t=t, rol="K2", sembol=s,
                                    kume=kume) for s in semboller]
    return ornekleme.adaylari_kur(onaylar, rol="K2", hipotez=hipotez, yapilandirma=y, kume=kume,
                                  bar_zamani=t)


def ornekle(adaylar: ornekleme.Adaylar, *, sembol: str = None, olay_zamani=None, olay=None, **ek):
    """`ornekleme.ornekle`; olay verilmezse adaylarin kimligine uyan bir olay kurulur.

    Madde 3b'den beri `ornekle` olayin kendisini alir (serbest `sembol`/`olay_zamani` degil) ve
    adaylarla capraz dogrular. Bu yardimci eski cagri bicimini korur: `sembol`/`olay_zamani`
    verilirse onlarla, verilmezse adaylarin kimligiyle uyumlu bir olay uretir (K1'de adaylarin
    sembolu ve donemi, K2'de adaylarin bar zamani).
    """
    import dizi_yardimcisi

    def _izgaradan(hipotez, kimlik):
        """Kimlikten (`H2:phi=...`) izgaradaki parametre demetini bulur."""
        for y in sinyal.izgara(hipotez):
            if sinyal.yapilandirma_kimligi(hipotez, y) == kimlik:
                return dict(y)
        raise AssertionError(f"kimlik izgarada yok: {kimlik!r}")

    if olay is None:
        if adaylar.rol == "K1":
            s = sembol if sembol is not None else (adaylar.sembol or "AAVEUSDT")
            donem_no = adaylar.donem_no if adaylar.donem_no is not None else 0
            # Olayin kendi bari K1 adayi OLAMAZ (madde 3b): varsayilan olay zamani adaylardan uzak
            # bir an olarak secilir.
            if olay_zamani is not None:
                t = olay_zamani
            elif len(adaylar.ogeler):
                adim = pencere.adim(config.HIPOTEZ_IZGARASI[adaylar.hipotez])
                t = pd.DatetimeIndex(adaylar.ogeler).max() + adim
            else:
                t = pd.Timestamp("2025-03-01", tz="UTC")
        else:
            # Olayin kendi coini K2 adayi OLAMAZ (madde 3b).
            if sembol is not None:
                s = sembol
            else:
                s = "AAVEUSDT" if "AAVEUSDT" not in adaylar.ogeler else "OLAYUSDT"
            t = (olay_zamani if olay_zamani is not None
                 else (adaylar.bar_zamani if adaylar.bar_zamani is not None
                       else pd.Timestamp("2025-03-01", tz="UTC")))
            donem_no = 0
        olay = dizi_yardimcisi.tek_olay(t, hipotez=adaylar.hipotez,
                                        yapilandirma=_izgaradan(adaylar.hipotez, adaylar.yapilandirma),
                                        kume=adaylar.kume, sembol=s, donem_no=donem_no)
    return ornekleme.ornekle(adaylar, olay=olay, **ek)
