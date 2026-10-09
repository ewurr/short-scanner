"""K1 ve K2 kontrol havuzlarinin ornekleme kurallari (on-kayit §6 "Ornekleme kurallari", rev.11).

Rev.11'den once kodda kontrol bari seceni hic yoktu (RESULTS §14.19 madde 12). On-kayit §6
(rev.11) kurallari yaziya dokmustur:

  "K1'deki 'o hipotezin herhangi bir olayi', AYNI YAPILANDIRMANIN olusmus olaylaridir: kapidan
  gecmemis (reddedilmis) adaylar ve baska yapilandirmalarin olaylari sayilmaz. K2'deki 'olay
  uretmemis' de ayni yapilandirmaya goredir. Iki havuzda da ornekleme IADESIZDIR. Aday sayisi
  10'dan azsa adaylarin tamami alinir ve sayi sonuc dosyasina yazilir. Bir olayin her iki havuzu
  da bossa o olay analize girmez; en az bir kontrolu olan olay kalir. Ornekleme, §7'deki
  tohumdan (hipotez, yapilandirma, kume, sembol, olay zamani) demetiyle turetilen alt tohumla
  yapilir; semboller alfabetik sirada islenir, boylece sonuc kosu sirasindan bagimsizdir."

  "K1 — ayni coin, rastgele zaman. Ayni coinden, ayni kume ve donem icinden, o hipotezin
  herhangi bir olayina birincil ufuk mesafesinden yakin olmayan 10 rastgele bar."
  "K2 — ayni zaman, rastgele coin. Ayni t barinda uygun olan ve o anda olay uretmemis diger
  coinlerden 10 rastgele coin."

**Adayligin kapisi.** Bir barin (ya da coinin) kontrol ADAYI olup olmadigina tek karar noktasi
hukmeder (`pozisyon.olay_karari`, `rol="K1"` / `rol="K2"`): uygunluk, donem uyeligi, fiyat ve
funding tamligi ve §4'teki butun kosullar oradan gecer (on-kayit §6 rev.11 "Kontrolun ne
olctugu"). Bu modul YALNIZCA secimi yapar ve kapidan gecmis adaylari alir. Once ornekleyip
sonra kapiya sormak, 10'dan az aday kuralini bozardi: kapi birkacini reddedince havuz, daha
fazla aday varken eksik kalirdi.

Modul SAFTIR: veri yuklemez, kapiyi cagirmaz, getiri hesaplamaz.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

import config
from data import pencere as pencere_modulu
from data import sinyal as sinyal_modulu


@dataclass(frozen=True)
class KontrolHavuzu:
    """Bir olayin kontrol havuzu: secilenler ve aday sayisi (on-kayit §6: "sayi sonuc dosyasina
    yazilir")."""

    secilenler: tuple
    aday_sayisi: int

    @property
    def eksik(self) -> bool:
        """Aday sayisi on-kayitin istedigi 10'dan az mi?"""
        return self.aday_sayisi < config.KONTROL_SAYISI

    def __len__(self) -> int:
        return len(self.secilenler)


def alt_tohum(hipotez, yapilandirma, kume, sembol, olay_zamani) -> int:
    """Olay basina alt tohum: (hipotez, yapilandirma, kume, sembol, olay zamani) demetinden
    §7'deki tohumla turetilir (on-kayit §6 rev.11, §7 "Tohum").

    Turetme deterministiktir ve kosu sirasindan bagimsizdir: ayni demet her zaman ayni tohumu
    verir. Zaman damgasi UTC ISO biciminde, nanosaniye duyarliginda yazilir.
    """
    ad = sinyal_modulu._hipotez_dogrula(hipotez)
    kimlik = sinyal_modulu.yapilandirma_kimligi(ad, yapilandirma)
    k = _kume_dogrula(kume)
    if not isinstance(sembol, str) or not sembol:
        raise TypeError(f"sembol bos olmayan bir str olmali: {sembol!r}")
    t = pencere_modulu.utc_zamani(olay_zamani, "olay_zamani")
    metin = f"{config.TOHUM}|{kimlik}|{k}|{sembol}|{t.isoformat()}"
    ozet = hashlib.sha256(metin.encode("utf-8")).digest()[:8]
    return int.from_bytes(ozet, "big")


def _kume_dogrula(kume) -> str:
    if not isinstance(kume, str) or kume not in config.KUMELER:
        raise ValueError(f"Bilinmeyen kume {kume!r}; on-kayit §3: {config.KUMELER}.")
    return kume


def sembol_sirasi(semboller) -> tuple[str, ...]:
    """Semboller alfabetik sirada islenir (on-kayit §6 rev.11). Tekrarlar reddedilir."""
    liste = list(semboller)
    if len(set(liste)) != len(liste):
        raise ValueError("sembol listesinde tekrar var.")
    return tuple(sorted(liste))


def k1_uzak_mi(t, olay_zamanlari, birincil_ufuk: int, bar: str) -> bool:
    """t bari, verilen olaylarin HICBIRINE "birincil ufuk mesafesinden yakin" degil mi?

    On-kayit §6 K1: "o hipotezin herhangi bir olayina birincil ufuk mesafesinden yakin olmayan".
    "Yakin olmayan" = iki yone de en az birincil ufuk kadar uzak; tam ufuk mesafesi yakin
    SAYILMAZ (olcut "daha yakin"dir). Karsilastirma §4 "Zaman toleransi"na gore yapilir: ufuk
    mesafesinden bir dakikadan az eksik kalan fark ayni mesafe sayilir ve bar dusmez.
    """
    zaman = pencere_modulu.utc_zamani(t, "t")
    h = pencere_modulu.birincil_ufuk_dogrula(birincil_ufuk, bar)
    mesafe = h * pencere_modulu.adim(bar)
    for olay in pd.DatetimeIndex(olay_zamanlari):
        # `once(fark, mesafe)` <=> fark, mesafeden (tolerans payindan fazla) KISA: bar yakindir.
        if pencere_modulu.once(abs(zaman - olay), mesafe):
            return False
    return True


def k1_adaylari(aday_barlar, olay_zamanlari, birincil_ufuk: int, bar: str) -> tuple[pd.Timestamp, ...]:
    """Kapidan gecmis K1 adaylarindan, ayni yapilandirmanin olaylarina yakin olanlari ayiklar.

    `aday_barlar`: ayni coinin, ayni kume ve donem icindeki, kapidan (`rol="K1"`) gecmis
    barlari. `olay_zamanlari`: AYNI YAPILANDIRMANIN olusmus olaylarinin zamanlari; reddedilmis
    adaylar ve baska yapilandirmalarin olaylari verilmez (on-kayit §6 rev.11).
    """
    barlar = pd.DatetimeIndex(aday_barlar)
    if len(barlar) and barlar.has_duplicates:
        raise ValueError("aday_barlar tekrarsiz olmali.")
    return tuple(t for t in barlar if k1_uzak_mi(t, olay_zamanlari, birincil_ufuk, bar))


def k2_adaylari(aday_semboller, olay_ureten_semboller, *, olay_sembolu: str) -> tuple[str, ...]:
    """Kapidan gecmis K2 adaylarindan, o anda olay ureten coinleri ve olayin kendi coinini ayiklar.

    `aday_semboller`: ayni t barinda kapidan (`rol="K2"`) gecmis DIGER coinler.
    `olay_ureten_semboller`: o barda AYNI YAPILANDIRMANIN olayini ureten coinler (on-kayit §6
    rev.11: "K2'deki 'olay uretmemis' de ayni yapilandirmaya goredir"). On-kayit §6 K2 "diger
    coinlerden" dedigi icin olayin kendi sembolu de ayiklanir.
    """
    ureten = set(olay_ureten_semboller)
    return tuple(s for s in sembol_sirasi(aday_semboller) if s != olay_sembolu and s not in ureten)


def ornekle(adaylar, *, tohum: int, sayi: int = None) -> KontrolHavuzu:
    """Adaylardan IADESIZ `sayi` (varsayilan on-kayit §6'daki 10) tane ceker.

    On-kayit §6 rev.11: "Iki havuzda da ornekleme iadesizdir. Aday sayisi 10'dan azsa adaylarin
    tamami alinir ve sayi sonuc dosyasina yazilir." Secim `tohum`dan tureyen bir jeneratorle
    yapilir; adaylar once siralanir, boylece sonuc cagirandaki sirayla degismez. Secilenler
    aday sirasinda doner.
    """
    hedef = config.KONTROL_SAYISI if sayi is None else int(sayi)
    if hedef < 1:
        raise ValueError(f"sayi en az 1 olmali: {hedef}")
    sirali = _sirala(adaylar)
    n = len(sirali)
    if n == 0:
        return KontrolHavuzu((), 0)
    if n <= hedef:
        return KontrolHavuzu(tuple(sirali), n)
    uretec = np.random.default_rng(int(tohum))
    secilen = sorted(int(i) for i in uretec.choice(n, size=hedef, replace=False))
    return KontrolHavuzu(tuple(sirali[i] for i in secilen), n)


def _sirala(adaylar):
    liste = list(adaylar)
    if len(set(liste)) != len(liste):
        raise ValueError("adaylar tekrarsiz olmali (ornekleme iadesizdir).")
    return sorted(liste)


def olay_analize_girer(k1: KontrolHavuzu, k2: KontrolHavuzu) -> bool:
    """On-kayit §6 rev.11: "Bir olayin her iki havuzu da bossa o olay analize girmez; en az bir
    kontrolu olan olay kalir." """
    return bool(len(k1) or len(k2))
