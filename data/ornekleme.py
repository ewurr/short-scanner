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

**Adaylik ornekelemeden ONCE belirlenir (on-kayit §6, rev.13).** "Bir bar ya da coin, §6'daki
butun kontrol gereksinimlerini ve §4'teki tek karar noktasinin butun kosullarini sagliyorsa
adaydir; ornekleme yalnizca adaylar arasindan yapilir ve secilen bir aday sonradan DUSMEZ.
Gerekce: 'aday sayisi 10'dan azsa' kurali ancak adaylik ornekelemeden once tanimliysa anlam
tasir; once ornekleyip sonra elemek havuz boyutunu adaylarin varligina degil cekimin sansina
baglardi. Bunun sonucu olarak her olayin havuzu, aday sayisi yeterliyse tam 10 kontrol icerir."

Bu kural rev.13'te SOZLESME duzeyine cikarilmistir. Adaylar artik ham bar damgasi ya da sembol
adi degil, `Adaylar` nesnesidir ve `Adaylar` yalnizca `adaylari_kur` ile, tek karar noktasinin
urettigi ONAYLI POZISYONLARDAN (`pozisyon.olay_karari`, `rol="K1"` / `rol="K2"`) kurulur. Her
onay `pozisyon.onay_dogrula` ile dogrulanir; kapidan gecmemis bir aday (ham damga, imzasiz nesne,
"olay" rolundeki ya da baska bir hipotezin/yapilandirmanin/kumenin pozisyonu) acik hata verir ve
sessizce havuza giremez. `k1_adaylari` ve `k2_adaylari` ayiklamayi ornekelemeden ONCE yapar ve
yine `Adaylar` dondurur; `ornekle` yalnizca `Adaylar` kabul eder.

`ornekle` TOHUMU CAGIRANDAN ALMAZ (denetci bulgusu D-C5): §7'deki tohumdan (hipotez,
yapilandirma, kume, sembol, olay zamani) demetiyle kendisi turetir ve `sayi` icin on-kayitin 10
degerinden baskasini kabul etmez.

Adayligin ICERIGI (uygunluk, donem uyeligi, fiyat ve funding tamligi, capasiz pencereler) kapinin
isidir; bu modul onu yeniden hesaplamaz, yalnizca kapidan gectigini dogrular. Modul veri yuklemez
ve kapiyi CAGIRMAZ; getiri hesaplamaz.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

import config
from data import dizi as dizi_modulu
from data import pencere as pencere_modulu
from data import pozisyon as pozisyon_modulu
from data import sinyal as sinyal_modulu


@dataclass(frozen=True)
class KontrolHavuzu:
    """Bir olayin kontrol havuzu: secilenler, aday sayisi ve cekimin alt tohumu.

    On-kayit §6: "Aday sayisi 10'dan azsa adaylarin tamami alinir ve SAYI sonuc dosyasina yazilir";
    §8 madde 1 (rev.13) raporlanacak kalemler arasinda "tohum ve ALT TOHUM TURETME DEMETI" de var.
    Denetci bulgusu D-C6: p-degeri tarafinda bu iki alan `istatistik.PSonucu`da tasiniyordu, ama
    ornekleme tarafinda hicbir yerde tasinmiyordu ve F2'nin yeniden turetmesi gerekiyordu. Simdi
    simetrik: cekimi yapan alt tohum ve onu ureten demet havuzla birlikte doner.

    `alt_tohum_demeti`: (yapilandirma kimligi, kume, sembol, olay zamani ISO) -- OLAYIN kimligi.
    Bos havuzda cekim yapilmaz ama kimlik ve tohum yine tasinir (madde 3d, bulgu K-C5).

    IMZALI (madde 3c, bulgu K-C6 ve sizinti 3): havuzu yalnizca `ornekle` uretir. Imzasiz havuz,
    `olay_sayilari`ndan gecip ANALIZE GIREN olay sayisini sisirebiliyordu; o sayi F2'nin aday
    esigi (150) ve F3'un guc esigi (100) demektir, yani hukmu degistirir.
    """

    secilenler: tuple
    aday_sayisi: int
    tohum: int = 0
    alt_tohum_demeti: tuple = ()
    genel_tohum: int = 0
    rol: str = ""
    _imza: int = field(default=0, repr=False, compare=False)

    @property
    def eksik(self) -> bool:
        """Aday sayisi on-kayitin istedigi 10'dan az mi?"""
        return self.aday_sayisi < config.KONTROL_SAYISI

    def __len__(self) -> int:
        return len(self.secilenler)


_HAVUZ_GIZLI = object()


def _havuz_imzasi(h: KontrolHavuzu) -> int:
    return hash((_HAVUZ_GIZLI, h.secilenler, h.aday_sayisi, h.tohum, h.alt_tohum_demeti,
                 h.genel_tohum, h.rol))


def _havuz_kur(secilenler, aday_sayisi, *, rol, tohum, alt_tohum_demeti, genel_tohum) -> KontrolHavuzu:
    h = KontrolHavuzu(tuple(secilenler), int(aday_sayisi), int(tohum), tuple(alt_tohum_demeti),
                      int(genel_tohum), str(rol))
    return replace(h, _imza=_havuz_imzasi(h))


def havuz_dogrula(havuz) -> KontrolHavuzu:
    """`ornekle`nin urettigi ve degistirilmemis bir kontrol havuzu mu? (madde 3c)"""
    if not isinstance(havuz, KontrolHavuzu):
        raise TypeError(f"Kontrol havuzu gerekir (ornekleme.ornekle ciktisi); verilen: "
                        f"{type(havuz).__name__}.")
    if havuz._imza != _havuz_imzasi(havuz):
        raise ValueError("Kontrol havuzu elle kurulmus ya da degistirilmis; yalnizca ornekleme.ornekle "
                         "uretir (madde 3c: olay sayilari bu havuzlardan sayilir).")
    if havuz.rol not in pozisyon_modulu.KONTROL_ROLLERI:
        raise ValueError(f"Kontrol havuzunun rolu {pozisyon_modulu.KONTROL_ROLLERI} olmali; "
                         f"verilen {havuz.rol!r}.")
    if len(havuz.secilenler) > havuz.aday_sayisi or len(havuz.secilenler) > config.KONTROL_SAYISI:
        raise ValueError(f"secilen kontrol sayisi ({len(havuz.secilenler)}) aday sayisini "
                         f"({havuz.aday_sayisi}) ya da on-kayit sayisini ({config.KONTROL_SAYISI}) asamaz "
                         "(on-kayit §6 rev.13).")
    if len(set(havuz.secilenler)) != len(havuz.secilenler):
        raise ValueError("ornekleme iadesizdir: secilenler tekrarsiz olmali (on-kayit §6 rev.11).")
    return havuz


def tohum_turet(*parcalar) -> int:
    """§7'deki tohumdan bir alt tohum turetir: TEK turetme yolu (on-kayit §6 rev.11, §7 rev.13).

    Parcalar `|` ile birlestirilir, SHA256 ozetinin ilk 8 baytı tamsayiya cevrilir. Turetme
    deterministiktir ve kosu sirasindan bagimsizdir: ayni demet her zaman ayni tohumu verir.
    Hem §6'nin olay basina ornekleme alt tohumu hem de §7'nin p-degeri alt tohumu bu yoldan gecer
    ("alt tohum §6'daki ornekleme deseniyle aynidir", rev.13).
    """
    if not parcalar or any(not isinstance(p, str) or not p or "|" in p for p in parcalar):
        raise ValueError(f"alt tohum parcalari bos olmayan, '|' icermeyen metinler olmali: {parcalar!r}")
    metin = "|".join((str(config.TOHUM), *parcalar))
    return int.from_bytes(hashlib.sha256(metin.encode("utf-8")).digest()[:8], "big")


def alt_tohum(hipotez, yapilandirma, kume, sembol, olay_zamani) -> int:
    """Olay basina alt tohum: (hipotez, yapilandirma, kume, sembol, olay zamani) demetinden
    §7'deki tohumla turetilir (on-kayit §6 rev.11, §7 "Tohum").

    Zaman damgasi UTC'ye NORMALLESTIRILIR ve ISO biciminde, nanosaniye duyarliginda yazilir
    (sizinti bulgusu S-B4): `pencere.utc_zamani` yalnizca saat dilimsiz damgayi reddediyordu,
    bu yuzden ayni an UTC disi bir saat diliminde tasindiginda (`...+03:00`) metin degisiyor ve
    AYNI OLAY FARKLI TOHUM aliyordu. CLAUDE.md §5: "Tum zaman damgalari UTC."
    """
    ad = sinyal_modulu._hipotez_dogrula(hipotez)
    # Yapilandirma ya izgaradaki parametre demeti ya da onun KIMLIGIDIR (`Adaylar` kimligi tasir).
    kimlik = (yapilandirma if isinstance(yapilandirma, str)
              else sinyal_modulu.yapilandirma_kimligi(ad, yapilandirma))
    if isinstance(yapilandirma, str):
        # Kimlik §5'teki IZGARADA bulunmali (madde 3b). Onceden yalnizca `H2:` oneki
        # denetleniyordu, yani izgara disi bir demetin kimligi (ör. `H2:phi=9,k=9`) kabul ediliyor
        # ve kendi alt tohumunu aliyordu. On-kayit §5 rev.11: "izgarada bulunmayan bir parametre
        # demeti hata verir".
        gecerliler = {sinyal_modulu.yapilandirma_kimligi(ad, y) for y in sinyal_modulu.izgara(ad)}
        if kimlik not in gecerliler:
            raise ValueError(f"{ad} yapilandirma kimligi §5 izgarasinda bulunmali; verilen {kimlik!r}. "
                             "Izgarada bulunmayan bir parametre demeti hata verir (on-kayit §5 rev.11).")
    k = _kume_dogrula(kume)
    if not isinstance(sembol, str) or not sembol:
        raise TypeError(f"sembol bos olmayan bir str olmali: {sembol!r}")
    t = pencere_modulu.utc_zamani(olay_zamani, "olay_zamani").tz_convert("UTC")
    return tohum_turet(kimlik, k, sembol, t.isoformat())


def alt_tohum_demeti(hipotez, yapilandirma, kume, sembol, olay_zamani) -> tuple[str, str, str, str]:
    """Alt tohumu ureten demet, raporlanacak bicimde (on-kayit §8 madde 1: "tohum ve alt tohum
    TURETME DEMETI"). Denetci bulgusu D-C6: p-degeri tarafinda demet `PSonucu.alt_tohum_demeti`
    ile tasiniyordu, ornekleme tarafinda hic tasinmiyordu."""
    ad = sinyal_modulu._hipotez_dogrula(hipotez)
    kimlik = (yapilandirma if isinstance(yapilandirma, str)
              else sinyal_modulu.yapilandirma_kimligi(ad, yapilandirma))
    k = _kume_dogrula(kume)
    t = pencere_modulu.utc_zamani(olay_zamani, "olay_zamani").tz_convert("UTC")
    return (kimlik, k, str(sembol), t.isoformat())


def _kume_dogrula(kume) -> str:
    if not isinstance(kume, str) or kume not in config.KUMELER:
        raise ValueError(f"Bilinmeyen kume {kume!r}; on-kayit §3: {config.KUMELER}.")
    return kume


# --- Adaylik (on-kayit §6 "Ornekleme kurallari", rev.13) --------------------------------------

_ADAY_GIZLI = object()


@dataclass(frozen=True)
class Adaylar:
    """Kapidan gecmis kontrol adaylari. YALNIZCA `adaylari_kur` ve ayiklayicilari uretir.

    `ogeler`: K1'de aday BAR zamanlari, K2'de aday SEMBOLLER. `rol`, `hipotez`, `yapilandirma`
    (kimlik) ve `kume` butun adaylarda aynidir ve ornekelemenin alt tohumuna girer.
    """

    rol: str
    hipotez: str
    yapilandirma: str
    kume: str
    ogeler: tuple
    # K2'de adaylarin ORTAK bar zamani (§6 K2 "ayni t barinda"); K1'de `None`, cunku K1'in
    # adaylari zaten farkli barlardir. `k2_adaylari` olay kumesinin bu bara ait oldugunu bununla
    # dogrular (denetci bulgusu D-B2).
    bar_zamani: pd.Timestamp | None = None
    # K1'de adaylarin ORTAK sembolu ve listeleme donemi (§6 K1: "ayni coinden, ayni kume ve donem
    # icinden"); K2'de `None`, cunku K2'nin adaylari zaten farkli coinlerdir. `ornekle` olayin
    # bu coine ve bu doneme ait oldugunu bunlarla dogrular (bulgu K-C4, madde 3b): onceden olayin
    # kimligi `ornekle`ye SERBEST METIN olarak giriyordu ve adaylarla hicbir yerde
    # karsilastirilmiyordu.
    sembol: str | None = None
    donem_no: int | None = None
    _imza: int = field(default=0, repr=False, compare=False)

    def __len__(self) -> int:
        return len(self.ogeler)


def _aday_imzasi(a: Adaylar) -> int:
    return hash((_ADAY_GIZLI, a.rol, a.hipotez, a.yapilandirma, a.kume, a.ogeler, a.bar_zamani,
                 a.sembol, a.donem_no))


def aday_dogrula(adaylar) -> Adaylar:
    """`adaylari_kur`un urettigi ve degistirilmemis bir aday kumesi mi? (on-kayit §6 rev.13)"""
    if not isinstance(adaylar, Adaylar):
        raise TypeError(f"Kapidan gecmis aday kumesi gerekir (ornekleme.adaylari_kur ciktisi); verilen: "
                        f"{type(adaylar).__name__}. Ham bar damgasi ya da sembol listesi aday DEGILDIR "
                        "(on-kayit §6 rev.13: adaylik ornekelemeden once belirlenir).")
    if adaylar._imza != _aday_imzasi(adaylar):
        raise ValueError("Adaylar elle kurulmus ya da degistirilmis; yalnizca ornekleme.adaylari_kur uretir.")
    return adaylar


def _aday_kur(rol, hipotez, yapilandirma, kume, ogeler, bar_zamani=None, sembol=None,
              donem_no=None) -> Adaylar:
    a = Adaylar(rol, hipotez, yapilandirma, kume, tuple(ogeler), bar_zamani, sembol, donem_no)
    return replace(a, _imza=_aday_imzasi(a))


def adaylari_kur(onaylar, *, rol: str, hipotez: str = None, yapilandirma=None, kume: str = None,
                 sembol: str = None, donem_no: int = None, bar_zamani=None) -> Adaylar:
    """Tek karar noktasindan `rol` rolunde gecmis onaylardan aday kumesi kurar (on-kayit §6 rev.13).

    `onaylar`: `pozisyon.olay_karari` ciktilari (`rol="K1"` ya da `rol="K2"`). Dogrulanan: imza
    (nesne gercekten kapidan geldi ve degistirilmedi), ROL, ve demetin kendi icinde tutarliligi
    (hipotez, yapilandirma, kume). K1 "ayni coin"dir: butun adaylar ayni sembol VE ayni listeleme
    donemi olmali. K2 "ayni zaman"dir: butun adaylarin sinyal zamani ayni olmali.

    Kimlik argumanlari (`hipotez`, `yapilandirma`, `kume`, `sembol`, `donem_no`, `bar_zamani`)
    isteğe baglidir ve verilirse onaylardan TURETILENLE karsilastirilir; uyusmazlik hatadir.
    Aday listesi BOSSA zorunludurlar (bulgu K-C5, madde 3d): "aday yok" on-kayit §6 rev.13'e gore
    mesru bir durumdur ("her iki havuzu da bossa o olay analize girmez") ve kimligi kaybolmamali.
    Onceden bos listede demet `(None, None, None)` oluyordu; ardindan `k1_adaylari`/`k2_adaylari`
    ayni yapilandirmanin olaylariyla cagrildiginda demet karsilastirmasi `ValueError` veriyordu,
    yani mesru bir durum HATA olarak gorunuyordu.

    Doner: K1'de aday bar zamanlari, K2'de aday semboller tasiyan `Adaylar`.
    """
    if rol not in pozisyon_modulu.KONTROL_ROLLERI:
        raise ValueError(f"rol {pozisyon_modulu.KONTROL_ROLLERI} olmali (on-kayit §6); verilen {rol!r}.")
    liste = list(onaylar)
    for onay in liste:
        pozisyon_modulu.onay_dogrula(onay)        # ham damga / imzasiz nesne burada duser
        if onay.rol != rol:
            raise ValueError(f"aday {rol} rolunde kapidan gecmis olmali; verilen rol {onay.rol!r} "
                             "(on-kayit §6 rev.13: adaylik ornekelemeden once belirlenir).")
    kimlikler = {(o.hipotez, o.yapilandirma, o.kume) for o in liste}
    if len(kimlikler) > 1:
        raise ValueError(f"butun adaylar ayni (hipotez, yapilandirma, kume) olmali; bulunan "
                         f"{sorted(kimlikler)} (on-kayit §5, §6 rev.11: havuzlar yapilandirma basinadir).")
    if liste:
        turetilen = next(iter(kimlikler))
        # Verilen yapilandirma parametre demeti de olabilir; karsilastirma KIMLIK uzerinden yapilir.
        verilen_kimlik = (yapilandirma if yapilandirma is None or isinstance(yapilandirma, str)
                          else sinyal_modulu.yapilandirma_kimligi(turetilen[0], yapilandirma))
        for ad, verilen, bulunan in zip(("hipotez", "yapilandirma", "kume"),
                                        (hipotez, verilen_kimlik, kume), turetilen):
            if verilen is not None and verilen != bulunan:
                raise ValueError(f"verilen {ad} {verilen!r}, adaylardan turetilen {bulunan!r} "
                                 "(kimlik argumanlari onaylarla ayni olmali).")
        hipotez, yapilandirma, kume = turetilen
    else:
        # Bos aday kumesi: kimlik CAGRIDAN gelir (bulgu K-C5).
        eksik = [ad for ad, deger in (("hipotez", hipotez), ("yapilandirma", yapilandirma),
                                      ("kume", kume)) if deger is None]
        if rol == "K1":
            eksik += [ad for ad, deger in (("sembol", sembol), ("donem_no", donem_no)) if deger is None]
        elif bar_zamani is None:
            eksik.append("bar_zamani")
        if eksik:
            raise ValueError(
                f"bos aday kumesinde kimlik argumanlari zorunludur; eksik: {eksik}. 'Aday yok' mesru "
                "bir durumdur (on-kayit §6 rev.13) ve kimligi kaybolmamali (bulgu K-C5).")
        hipotez = sinyal_modulu._hipotez_dogrula(hipotez)
        yapilandirma = (yapilandirma if isinstance(yapilandirma, str)
                        else sinyal_modulu.yapilandirma_kimligi(hipotez, yapilandirma))
        kume = _kume_dogrula(kume)
    if rol == "K1":
        if bar_zamani is not None:
            raise ValueError("K1 adaylari farkli barlardir: `bar_zamani` K1'de verilemez (on-kayit §6 K1).")
        semboller = {o.sembol for o in liste}
        if len(semboller) > 1:
            raise ValueError(f"K1 ayni coinden ornekler (on-kayit §6 K1); bulunan {sorted(semboller)}.")
        if semboller and sembol is not None and sembol not in semboller:
            raise ValueError(f"verilen sembol {sembol!r}, adaylardan turetilen {sorted(semboller)} "
                             "(kimlik argumanlari onaylarla ayni olmali).")
        # K1 ayni LISTELEME DONEMI icinden ornekler (on-kayit §6 K1: "ayni coinden, ayni kume ve
        # donem icinden"; §6 "Donem uyeligi" rev.8). Denetci bulgusu D-B1: sembol birligi
        # denetleniyordu, donem birligi denetlenmiyordu; iki listeleme donemi olan bir coinde
        # (delist sonrasi yeniden listelenen) baska donemin bari havuza girebiliyordu. O bar
        # kapidan gecmis oldugu icin hicbir yerde dusmezdi, ama ON-KAYITIN YASAKLADIGI bir
        # rejimden (baska bir listeleme donemi, cogu kez baska likidite ve fiyat duzeyi) kontrol
        # tasirdi.
        donemler = {o.donem_no for o in liste}
        if donemler and donem_no is not None and donem_no not in donemler:
            raise ValueError(f"verilen donem_no {donem_no!r}, adaylardan turetilen {sorted(donemler)} "
                             "(kimlik argumanlari onaylarla ayni olmali).")
        if len(donemler) > 1:
            raise ValueError(f"K1 ayni donem icinden ornekler (on-kayit §6 K1); bulunan donem numaralari "
                             f"{sorted(donemler)}. Ayni sembolun baska listeleme donemi baska bir rejimdir.")
        ogeler = pd.DatetimeIndex([o.plan.sinyal_zamani for o in liste])
        _k1_tekrarsiz(ogeler)
        return _aday_kur(rol, hipotez, yapilandirma, kume, ogeler,
                         sembol=next(iter(semboller)) if semboller else sembol,
                         donem_no=next(iter(donemler)) if donemler else donem_no)
    zamanlar = pd.DatetimeIndex([o.plan.sinyal_zamani for o in liste])
    if len(zamanlar) and not all(pencere_modulu.ayni_an(z, zamanlar[0]) for z in zamanlar):
        raise ValueError("K2 ayni t barindan ornekler (on-kayit §6 K2); adaylarin sinyal zamanlari farkli: "
                         f"{sorted({str(z) for z in zamanlar})}.")
    if len(zamanlar) and bar_zamani is not None and not pencere_modulu.ayni_an(zamanlar[0], bar_zamani):
        raise ValueError(f"verilen bar_zamani {bar_zamani}, adaylardan turetilen {zamanlar[0]} "
                         "(kimlik argumanlari onaylarla ayni olmali).")
    if len(liste) and (sembol is not None or donem_no is not None):
        raise ValueError("K2 adaylari farkli coinlerdir: `sembol`/`donem_no` K2'de verilemez "
                         "(on-kayit §6 K2 'diger coinlerden').")
    return _aday_kur(rol, hipotez, yapilandirma, kume, sembol_sirasi([o.sembol for o in liste]),
                     zamanlar[0] if len(zamanlar) else pencere_modulu.utc_zamani(bar_zamani, "bar_zamani"))

def _k1_tekrarsiz(ogeler: pd.DatetimeIndex) -> None:
    """K1 adaylari tekrarsiz olmali: ayni bar iki kez aday olamaz (on-kayit §6 K1, §6 rev.11).

    Karsilastirma §4 "Zaman toleransi"na gore yapilir (madde 3e): tam esitlik aranirsa t ve
    t + 30 saniye IKI AYRI aday sayilir, oysa on-kayitin zaman toleransi (bir dakikadan kisa
    fark) onlari AYNI AN sayar. Ornekleme iadesiz oldugu icin bu, ayni bari iki kez cekme
    olasiligi demekti ve havuzun aday sayisini da sisiriyordu.
    """
    if not len(ogeler):
        return
    sirali = ogeler.sort_values()
    for onceki, sonraki in zip(sirali[:-1], sirali[1:]):
        if pencere_modulu.ayni_an(onceki, sonraki):
            raise ValueError(
                f"K1 adaylari tekrarsiz olmali (ayni bar iki kez aday olamaz); {onceki} ile {sonraki} "
                "zaman toleransina gore AYNI andir (on-kayit §4 'Zaman toleransi').")


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


def _olaylari_dogrula(olaylar, adaylar: Adaylar, *, yer: str) -> tuple:
    """Havuz olcutlerinin girdisi: DOGRULANMIS olay nesneleri (denetci bulgusu D-B2).

    On-kayit §6 "Ornekleme kurallari" (rev.11, rev.12): K1'deki "o hipotezin herhangi bir olayi"
    ve K2'deki "olay uretmemis", AYNI YAPILANDIRMANIN olusmus olay kumesine gore uygulanir;
    "kapidan gecmemis (reddedilmis) adaylar ve baska yapilandirmalarin olaylari sayilmaz".

    Bulgu: iki olcut de ham `DatetimeIndex` / sembol kumesi aliyordu ve bu listenin gercekten
    olusmus olaylardan geldigi hicbir yerde dogrulanmiyordu. Eksik ya da yanlis bir liste
    (reddedilmis adaylarin da verilmesi, ya da bos kume verilmesi) sessizce yanlis havuz uretir:
    birinci durumda havuz gereginden dar, ikincisinde olay barlari K2 havuzunda kalir -- ikisi de
    OLCULEN FARKIN YONUNU degistirir. Modul, kendisinin turetebilecegi bir olguyu cagirandan
    serbest bicimde kabul etmemeli (kapi sertlestirmesinin ilkesi).

    Dogrulanan: her oge gercek bir `dizi.Olay` (imzali, elle kurulamaz) ve olayin pozisyonu
    adaylarla ayni (hipotez, yapilandirma, kume) demetine ait. SEMBOL kapsamı K1 icin ON-KAYITTA
    BELIRSIZDIR ("o hipotezin herhangi bir olayi" baska coinlerin olaylarini da kapsiyor olabilir)
    ve burada DARALTILMAZ; K2'de olcut zaten "ayni t barinda ... diger coinlerden"dir, bu yuzden
    orada bar zamani dogrulanir.
    """
    liste = list(olaylar)
    for i, olay in enumerate(liste):
        try:
            dizi_modulu.olay_dogrula(olay)
        except TypeError as hata:
            raise TypeError(f"{yer}[{i}]: {hata} Ham bar damgasi ya da sembol adi, olusmus bir olayin "
                            "YERINE gecmez (on-kayit §6 rev.11; denetci bulgusu D-B2).") from None
        p = olay.pozisyon
        if (p.hipotez, p.yapilandirma, p.kume) != (adaylar.hipotez, adaylar.yapilandirma, adaylar.kume):
            raise ValueError(
                f"{yer}[{i}]: olay ({p.hipotez}, {p.yapilandirma}, {p.kume}) demetine ait; adaylar "
                f"({adaylar.hipotez}, {adaylar.yapilandirma}, {adaylar.kume}). Havuz olcutu AYNI "
                "yapilandirmanin olay kumesine gore uygulanir (on-kayit §6 rev.11).")
    return tuple(liste)


def k1_adaylari(adaylar: Adaylar, olaylar, birincil_ufuk: int, bar: str) -> Adaylar:
    """K1 adaylarindan, ayni yapilandirmanin olaylarina yakin olanlari ayiklar (ORNEKLEMEDEN ONCE).

    `adaylar`: `adaylari_kur(..., rol="K1")` ciktisi -- ayni coinin, ayni kume ve donem icindeki,
    kapidan gecmis barlari. `olaylar`: AYNI YAPILANDIRMANIN olusmus olaylari, yani
    `dizi.olay_dizisi`nin urettigi `dizi.Olay` nesneleri; ham zaman damgasi kabul edilmez
    (denetci bulgusu D-B2). Reddedilmis adaylar ve baska yapilandirmalarin olaylari verilemez
    (on-kayit §6 rev.11) -- ikisi de `_olaylari_dogrula`da duser.

    Doner: ayiklanmis `Adaylar`. Ayiklama yalnizca BURADA yapilir; `ornekle` secilen bir adayi
    sonradan dusurmez (on-kayit §6 rev.13).
    """
    gecerli = aday_dogrula(adaylar)
    if gecerli.rol != "K1":
        raise ValueError(f"k1_adaylari K1 rolunde aday bekler; verilen {gecerli.rol!r}.")
    dogrulanmis = _olaylari_dogrula(olaylar, gecerli, yer="olaylar")
    zamanlar = pd.DatetimeIndex([o.zaman for o in dogrulanmis])
    kalan = tuple(t for t in pd.DatetimeIndex(gecerli.ogeler)
                  if k1_uzak_mi(t, zamanlar, birincil_ufuk, bar))
    return _aday_kur(gecerli.rol, gecerli.hipotez, gecerli.yapilandirma, gecerli.kume, kalan,
                     gecerli.bar_zamani, gecerli.sembol, gecerli.donem_no)


def k2_adaylari(adaylar: Adaylar, olaylar, *, olay_sembolu: str) -> Adaylar:
    """K2 adaylarindan, o anda olay ureten coinleri ve olayin kendi coinini ayiklar (ORNEKLEMEDEN ONCE).

    `adaylar`: `adaylari_kur(..., rol="K2")` ciktisi -- AYNI t barinda kapidan gecmis coinler.
    `olaylar`: o barda AYNI YAPILANDIRMANIN olayini ureten `dizi.Olay` nesneleri (on-kayit §6
    rev.12: olcut kosullar degil, o yapilandirmanin olusmus OLAY KUMESIDIR); ham sembol adi kabul
    edilmez (denetci bulgusu D-B2) ve her olayin bari adaylarin bariyla AYNI an olmali. On-kayit
    §6 K2 "diger coinlerden" dedigi icin olayin kendi sembolu de ayiklanir.

    Doner: ayiklanmis `Adaylar` (semboller alfabetik sirada; on-kayit §6 rev.11).
    """
    gecerli = aday_dogrula(adaylar)
    if gecerli.rol != "K2":
        raise ValueError(f"k2_adaylari K2 rolunde aday bekler; verilen {gecerli.rol!r}.")
    dogrulanmis = _olaylari_dogrula(olaylar, gecerli, yer="olaylar")
    for i, olay in enumerate(dogrulanmis):
        if gecerli.bar_zamani is None or not pencere_modulu.ayni_an(olay.zaman, gecerli.bar_zamani):
            raise ValueError(
                f"olaylar[{i}]: olay bari {olay.zaman}, K2 adaylarinin bari {gecerli.bar_zamani}. "
                "K2'nin 'o anda olay uretmemis' olcutu AYNI t barina gore uygulanir (on-kayit §6 K2).")
    ureten = {o.pozisyon.sembol for o in dogrulanmis}
    kalan = tuple(s for s in gecerli.ogeler if s != olay_sembolu and s not in ureten)
    return _aday_kur(gecerli.rol, gecerli.hipotez, gecerli.yapilandirma, gecerli.kume, kalan,
                     gecerli.bar_zamani, gecerli.sembol, gecerli.donem_no)


def _olayin_kimligi(adaylar: Adaylar, olay) -> tuple[str, pd.Timestamp]:
    """`ornekle`nin olayla adaylari CAPRAZ dogrulamasi (bulgu K-C4 ve sizinti 2, madde 3b).

    Olayin kimligi onceden `ornekle`ye serbest metin olarak (`sembol`, `olay_zamani`) giriyordu ve
    adaylarla hicbir yerde karsilastirilmiyordu. Sonuclari: (i) kaymis bir `olay_zamani` sessizce
    BASKA bir alt tohum uretir -- cekim deterministik kalir ama on-kaydin tanimladigi demetten
    gelmez ve rapordaki demet de ayni yanlis degeri tasidigi icin fark raporda GORUNMEZ;
    (ii) K1 adaylari baska coinden olabilir; (iii) olayin KENDI bari K1 kontrolu, KENDI coini K2
    kontrolu olabilir -- ikisi de olculen farki hipotez lehine kaydirir.

    Dogrulanan: olay gercek bir `dizi.Olay`; (hipotez, yapilandirma, kume) adaylarla ayni; K1'de
    olayin sembolu ve donemi adaylarin sembolu ve donemiyle ayni ve olayin kendi bari adaylar
    arasinda DEGIL; K2'de olayin bari adaylarin bariyla ayni an ve olayin kendi coini adaylar
    arasinda degil (on-kayit §6 K1, K2).
    """
    dizi_modulu.olay_dogrula(olay)
    p = olay.pozisyon
    if (p.hipotez, p.yapilandirma, p.kume) != (adaylar.hipotez, adaylar.yapilandirma, adaylar.kume):
        raise ValueError(
            f"olay ({p.hipotez}, {p.yapilandirma}, {p.kume}) demetine ait; adaylar "
            f"({adaylar.hipotez}, {adaylar.yapilandirma}, {adaylar.kume}). Ornekleme AYNI "
            "yapilandirmanin olayi icin yapilir (on-kayit §6 rev.11).")
    if adaylar.rol == "K1":
        if p.sembol != adaylar.sembol or p.donem_no != adaylar.donem_no:
            raise ValueError(
                f"K1 ayni coinden, ayni donem icinden ornekler (on-kayit §6 K1); olay "
                f"({p.sembol}, donem {p.donem_no}), adaylar ({adaylar.sembol}, donem {adaylar.donem_no}).")
        for aday in pd.DatetimeIndex(adaylar.ogeler):
            if pencere_modulu.ayni_an(aday, olay.zaman):
                raise ValueError(
                    f"olayin kendi bari ({olay.zaman}) K1 kontrolu olamaz: K1 adaylari olaya birincil "
                    "ufuk mesafesinden yakin olmayan barlardir (on-kayit §6 K1); `k1_adaylari` "
                    "ayiklamasi atlanmis olmali.")
    else:
        if adaylar.bar_zamani is None or not pencere_modulu.ayni_an(olay.zaman, adaylar.bar_zamani):
            raise ValueError(
                f"K2 ayni t barindan ornekler (on-kayit §6 K2); olay bari {olay.zaman}, adaylarin bari "
                f"{adaylar.bar_zamani}.")
        if p.sembol in adaylar.ogeler:
            raise ValueError(
                f"olayin kendi coini ({p.sembol}) K2 kontrolu olamaz (on-kayit §6 K2 'diger "
                "coinlerden'); `k2_adaylari` ayiklamasi atlanmis olmali.")
    return p.sembol, olay.zaman


def ornekle(adaylar: Adaylar, *, olay, sayi: int = None) -> KontrolHavuzu:
    """Adaylardan IADESIZ on-kayit §6'daki 10 tane ceker.

    On-kayit §6 rev.11: "Iki havuzda da ornekleme iadesizdir. Aday sayisi 10'dan azsa adaylarin
    tamami alinir ve sayi sonuc dosyasina yazilir. ... Ornekleme, §7'deki tohumdan (hipotez,
    yapilandirma, kume, sembol, olay zamani) demetiyle turetilen alt tohumla yapilir."

    `adaylar`: `adaylari_kur` / `k1_adaylari` / `k2_adaylari` ciktisi; ham liste kabul edilmez
    (on-kayit §6 rev.13). `olay`: ornekelemenin yapildigi OLAY (`dizi.Olay`); sembol ve bar zamani
    ondan OKUNUR, cagirandan serbest metin olarak alinmaz (bulgu K-C4, madde 3b) ve adaylarla
    capraz dogrulanir (`_olayin_kimligi`). Hipotez, yapilandirma ve kume `adaylar`dan gelir.
    TOHUM CAGIRANDAN ALINMAZ ve `sayi` on-kayit degeridir (denetci bulgusu D-C5); serbest deger
    acik hata verir.

    Adaylar once siralanir, boylece sonuc cagirandaki sirayla degismez. Secilenler aday sirasinda
    doner. Secilen aday sonradan DUSMEZ (on-kayit §6 rev.13): secilenler adaylarin alt kumesidir
    ve sayilari `min(10, aday sayisi)`dir; bu donuste denetlenir.
    """
    hedef = config.KONTROL_SAYISI if sayi is None else int(sayi)
    if isinstance(sayi, bool) or hedef != config.KONTROL_SAYISI:
        raise ValueError(f"sayi on-kayit §6 degeri olmali ({config.KONTROL_SAYISI}); verilen {sayi!r}.")
    gecerli = aday_dogrula(adaylar)
    sembol, olay_zamani = _olayin_kimligi(gecerli, olay)
    sirali = _sirala(gecerli.ogeler)
    n = len(sirali)
    tohum = alt_tohum(gecerli.hipotez, gecerli.yapilandirma, gecerli.kume, sembol, olay_zamani)
    # Alt tohum ve onu ureten demet havuzla birlikte doner (on-kayit §8 madde 1; denetci D-C6):
    # F2 raporunda yeniden turetilmesi gerekmez ve p-degeri tarafiyla simetriktir.
    kimlik_demeti = alt_tohum_demeti(gecerli.hipotez, gecerli.yapilandirma, gecerli.kume, sembol,
                                     olay_zamani)
    iz = dict(tohum=int(tohum), alt_tohum_demeti=kimlik_demeti, genel_tohum=config.TOHUM,
              rol=gecerli.rol)
    if n == 0:
        # Bos havuz da kimligini tasir (bulgu K-C5, madde 3d): "aday yok" mesru bir durumdur ve
        # §8 madde 1 geregi rapora yazilacak tohum alani 0 degil ON-KAYIT TOHUMU olmalidir.
        return _havuz_kur((), 0, **iz)
    if n <= hedef:
        havuz = _havuz_kur(tuple(sirali), n, **iz)
    else:
        uretec = np.random.default_rng(int(tohum))
        secilen = sorted(int(i) for i in uretec.choice(n, size=hedef, replace=False))
        havuz = _havuz_kur(tuple(sirali[i] for i in secilen), n, **iz)
    if len(havuz) != min(hedef, n) or not set(havuz.secilenler) <= set(sirali):
        raise AssertionError("secilen aday sonradan dusmemeli (on-kayit §6 rev.13).")
    return havuz


def _sirala(adaylar):
    liste = list(adaylar)
    if len(set(liste)) != len(liste):
        raise ValueError("adaylar tekrarsiz olmali (ornekleme iadesizdir).")
    return sorted(liste)


def olay_analize_girer(k1: KontrolHavuzu, k2: KontrolHavuzu) -> bool:
    """TEK YUKLEM: bu olay analize giriyor mu? (on-kayit §6 rev.11, §8 madde 2 rev.13)

    §6 rev.11: "Bir olayin her iki havuzu da bossa o olay analize girmez; en az bir kontrolu olan
    olay kalir." §8 madde 2 (rev.13): "Buradaki ve §9'daki olay sayisi, ANALIZE GIREN olaylarin
    sayisidir." Iki yer ayni olcute bakar, bu yuzden olcut tek bir yuklemde durur ve hem F2'nin
    aday esigi (150) hem F3'un guc esigi (100) bu yuklemle sayilan olaylari kullanir.
    """
    return bool(len(k1) or len(k2))


@dataclass(frozen=True)
class OlaySayilari:
    """Bir yapilandirmanin iki olay sayisi (on-kayit §8 madde 1: "olusmus olay sayisi; analize
    giren olay sayisi" -- ikisi de raporlanir)."""

    olusmus: int
    analize_giren: int

    def esigi_gecer(self, esik: int) -> bool:
        """Esik ANALIZE GIREN olay sayisina uygulanir (on-kayit §8 madde 2, rev.13)."""
        return self.analize_giren >= int(esik)


def olay_sayilari(havuz_ciftleri) -> OlaySayilari:
    """Olusmus ve analize giren olay sayilari (on-kayit §8 madde 1-2, rev.13). Saf.

    `havuz_ciftleri`: olusmus her olay icin `(k1, k2)` kontrol havuzu cifti, olay sirasinda.
    Olusmus olay sayisi ciftlerin sayisidir; analize giren olay sayisi `olay_analize_girer`
    yuklemini saglayanlarin sayisidir. Baska bir sayim yolu yoktur: iki sayi da buradan uretilir.
    """
    ciftler = list(havuz_ciftleri)
    gorulen = {}
    for i, cift in enumerate(ciftler):
        if not (isinstance(cift, tuple) and len(cift) == 2
                and all(isinstance(h, KontrolHavuzu) for h in cift)):
            raise TypeError(f"havuz_ciftleri[{i}] (K1, K2) `KontrolHavuzu` cifti olmali; verilen {cift!r}.")
        k1, k2 = (havuz_dogrula(h) for h in cift)       # imza, rol ve tutarlilik (madde 3c)
        if (k1.rol, k2.rol) != ("K1", "K2"):
            raise ValueError(f"havuz_ciftleri[{i}]: cift (K1, K2) sirasinda olmali; verilen roller "
                             f"({k1.rol}, {k2.rol}).")
        # Iki havuz AYNI OLAYIN havuzu olmali ve her olay bir kez sayilmali (bulgu K-C6): sayim yolu
        # tek oldugu icin (§8 madde 1-2) tekrarlanan ya da baska yapilandirmadan karisan bir cift
        # esigi sessizce gecirirdi.
        if k1.alt_tohum_demeti != k2.alt_tohum_demeti:
            raise ValueError(f"havuz_ciftleri[{i}]: K1 ve K2 ayni olayin havuzu olmali; demetler "
                             f"{k1.alt_tohum_demeti} ve {k2.alt_tohum_demeti}.")
        demet = k1.alt_tohum_demeti
        if demet in gorulen:
            raise ValueError(f"havuz_ciftleri[{i}]: ayni olay iki kez sayilamaz; {demet} daha once "
                             f"{gorulen[demet]}. indeksinde gorundu (on-kayit §8 madde 1-2).")
        gorulen[demet] = i
        if i and demet[:2] != ciftler[0][0].alt_tohum_demeti[:2]:
            raise ValueError(f"havuz_ciftleri[{i}]: butun ciftler ayni (yapilandirma, kume) demetine ait "
                             f"olmali; {demet[:2]} ile {ciftler[0][0].alt_tohum_demeti[:2]} karisti "
                             "(havuzlar yapilandirma basinadir, on-kayit §6 rev.11).")
    return OlaySayilari(olusmus=len(ciftler),
                        analize_giren=sum(1 for k1, k2 in ciftler if olay_analize_girer(k1, k2)))


def olay_esigi_dogrula(esik, *, asama: str) -> int:
    """Olay sayisi esigi on-kayit degeri olmali (on-kayit §8 madde 2, §9 madde 6; rev.13).

    `asama`: "F2" (aday esigi, 150) ya da "F3" (guc esigi, 100). Serbest deger kabul edilmez:
    esikler "sonuc gorulduk sonra degistirilmez" (CLAUDE.md §3 madde 4) ve kodda tek yerden,
    `config`ten okunur.
    """
    beklenen = {"F2": config.ADAY_OLAY_ESIGI, "F3": config.ONAY_OLAY_ESIGI}
    if asama not in beklenen:
        raise ValueError(f"asama 'F2' ya da 'F3' olmali; verilen {asama!r}.")
    if isinstance(esik, bool) or int(esik) != beklenen[asama]:
        raise ValueError(f"{asama} olay sayisi esigi on-kayit degeri olmali ({beklenen[asama]}); "
                         f"verilen {esik!r}.")
    return int(esik)
