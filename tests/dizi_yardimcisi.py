"""Gercek `dizi.Olay` nesneleri ureten test yardimcisi (on-kayit §4 rev.12, §6 rev.11).

`ornekleme.k1_adaylari` ve `k2_adaylari` artik ham bar damgasi ya da sembol listesi degil,
DOGRULANMIS olay nesneleri alir (denetci bulgusu D-B2): modul, kendisinin turetebilecegi bir
olguyu ("bu bar o yapilandirmanin olusmus olaylarindan biridir") cagirandan serbest bicimde kabul
etmez. Olay nesnesi yalnizca `dizi.olay_dizisi`den cikar, bu yuzden testler olaylari GERCEK dizi
cagrisiyla uretir; kosul ve karar sahte cagirilabilirlerdir (`pozisyon._test_onayi`), yani veri
yuklenmez ve getiri hesaplanmaz.

H1'de olay bir izlemenin teyit baridir: istenen her bar icin iki barlik ayri bir dizi kosulur
(pump = bir onceki bar, teyit = istenen bar), boylece olayin capasi tanimli olur ve bekleme
suresi araya girmez. H2 ve H3'te tek cagri yeter.

Aga cikmaz.
"""

from __future__ import annotations

import pandas as pd

import config
from data import dizi, pencere, pozisyon, sinyal


def _yap(hipotez, yapilandirma):
    return dict(sinyal.izgara(hipotez)[0]) if yapilandirma is None else yapilandirma


def _karar_kur(hipotez, y, kume, sembol, donem_no):
    def karar(t, capa):
        return pozisyon._test_onayi(hipotez=hipotez, yapilandirma=y, t=t, rol="olay", capa=capa,
                                    sembol=sembol, kume=kume, donem_no=donem_no)

    return karar


def olaylar_kur(zamanlar, *, hipotez: str = "H2", yapilandirma=None, kume: str = "KESIF",
                sembol: str = "AAVEUSDT", donem_no: int = 0) -> tuple[dizi.Olay, ...]:
    """Verilen barlarda gercek `dizi.Olay` nesneleri uretir.

    Kosul her barda saglanir. H2/H3'te tek dizi cagrisi yapilir, bu yuzden donen olaylar dizi
    kurallarinin (bekleme suresi, H3'te "ilk gun") suzgecinden gecmis olabilir: barlar birincil
    ufuktan uzak degilse donen olay sayisi istenenden az olur. H1'de her bar icin ayri cagri
    yapilir ve her bar bir olay uretir.
    """
    ad = sinyal._hipotez_dogrula(hipotez)
    y = _yap(ad, yapilandirma)
    bar = config.HIPOTEZ_IZGARASI[ad]
    adim = pencere.adim(bar)
    indeks = pd.DatetimeIndex(zamanlar)
    karar = _karar_kur(ad, y, kume, sembol, donem_no)
    ortak = dict(bar=bar, birincil_ufuk=config.BIRINCIL_UFUK[bar], karar=karar)
    # Dizinin kimligi cagriya verilir (madde 3a, bulgu K-B1): `karar`in uretecegi onayla ayni uclu.
    kimlik = dict(sembol=sembol, kume=kume, donem_no=donem_no)

    if ad in dizi.IZLEMELI_HIPOTEZLER:
        olaylar: list[dizi.Olay] = []
        for t in indeks:
            ikili = pd.DatetimeIndex([t - adim, t])
            sonuc = dizi.olay_dizisi(ad, y, ikili, ortak["bar"],
                                     birincil_ufuk=ortak["birincil_ufuk"],
                                     kosul=lambda t2, capa, t=t: capa is not None or t2 != t,
                                     karar=karar, **kimlik)
            assert len(sonuc.olaylar) == 1, (t, sonuc)
            olaylar.append(sonuc.olaylar[0])
        return tuple(olaylar)

    sonuc = dizi.olay_dizisi(ad, y, indeks, ortak["bar"], birincil_ufuk=ortak["birincil_ufuk"],
                             kosul=lambda t, capa: True, karar=karar, **kimlik)
    return sonuc.olaylar


def tek_olay(t, **ek) -> dizi.Olay:
    """Tek bir barda tek bir olay."""
    olaylar = olaylar_kur([t], **ek)
    assert len(olaylar) == 1, olaylar
    return olaylar[0]


def olaylar_sembollerde(semboller, *, t, **ek) -> tuple[dizi.Olay, ...]:
    """Ayni t barinda, verilen her sembol icin bir olay (K2'nin "olay ureten coinler" girdisi)."""
    return tuple(tek_olay(t, sembol=s, **ek) for s in semboller)
