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

    `alt_tohum_demeti`: (hipotez, yapilandirma kimligi, kume, sembol, olay zamani ISO). Bos
    havuzda cekim yapilmadigi icin `tohum` 0 ve demet bostur.
    """

    secilenler: tuple
    aday_sayisi: int
    tohum: int = 0
    alt_tohum_demeti: tuple = ()
    genel_tohum: int = 0

    @property
    def eksik(self) -> bool:
        """Aday sayisi on-kayitin istedigi 10'dan az mi?"""
        return self.aday_sayisi < config.KONTROL_SAYISI

    def __len__(self) -> int:
        return len(self.secilenler)


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
    if isinstance(yapilandirma, str) and not kimlik.startswith(f"{ad}:"):
        raise ValueError(f"{ad} yapilandirma kimligi {ad!r} ile baslamali; verilen {kimlik!r}.")
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
    _imza: int = field(default=0, repr=False, compare=False)

    def __len__(self) -> int:
        return len(self.ogeler)


def _aday_imzasi(a: Adaylar) -> int:
    return hash((_ADAY_GIZLI, a.rol, a.hipotez, a.yapilandirma, a.kume, a.ogeler, a.bar_zamani))


def aday_dogrula(adaylar) -> Adaylar:
    """`adaylari_kur`un urettigi ve degistirilmemis bir aday kumesi mi? (on-kayit §6 rev.13)"""
    if not isinstance(adaylar, Adaylar):
        raise TypeError(f"Kapidan gecmis aday kumesi gerekir (ornekleme.adaylari_kur ciktisi); verilen: "
                        f"{type(adaylar).__name__}. Ham bar damgasi ya da sembol listesi aday DEGILDIR "
                        "(on-kayit §6 rev.13: adaylik ornekelemeden once belirlenir).")
    if adaylar._imza != _aday_imzasi(adaylar):
        raise ValueError("Adaylar elle kurulmus ya da degistirilmis; yalnizca ornekleme.adaylari_kur uretir.")
    return adaylar


def _aday_kur(rol, hipotez, yapilandirma, kume, ogeler, bar_zamani=None) -> Adaylar:
    a = Adaylar(rol, hipotez, yapilandirma, kume, tuple(ogeler), bar_zamani)
    return replace(a, _imza=_aday_imzasi(a))


def adaylari_kur(onaylar, *, rol: str) -> Adaylar:
    """Tek karar noktasindan `rol` rolunde gecmis onaylardan aday kumesi kurar (on-kayit §6 rev.13).

    `onaylar`: `pozisyon.olay_karari` ciktilari (`rol="K1"` ya da `rol="K2"`). Dogrulanan: imza
    (nesne gercekten kapidan geldi ve degistirilmedi), ROL, ve demetin kendi icinde tutarliligi
    (hipotez, yapilandirma, kume). K1 "ayni coin"dir: butun adaylar ayni sembol olmali. K2 "ayni
    zaman"dir: butun adaylarin sinyal zamani ayni olmali.

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
    hipotez, yapilandirma, kume = next(iter(kimlikler)) if liste else (None, None, None)
    if rol == "K1":
        semboller = {o.sembol for o in liste}
        if len(semboller) > 1:
            raise ValueError(f"K1 ayni coinden ornekler (on-kayit §6 K1); bulunan {sorted(semboller)}.")
        # K1 ayni LISTELEME DONEMI icinden ornekler (on-kayit §6 K1: "ayni coinden, ayni kume ve
        # donem icinden"; §6 "Donem uyeligi" rev.8). Denetci bulgusu D-B1: sembol birligi
        # denetleniyordu, donem birligi denetlenmiyordu; iki listeleme donemi olan bir coinde
        # (delist sonrasi yeniden listelenen) baska donemin bari havuza girebiliyordu. O bar
        # kapidan gecmis oldugu icin hicbir yerde dusmezdi, ama ON-KAYITIN YASAKLADIGI bir
        # rejimden (baska bir listeleme donemi, cogu kez baska likidite ve fiyat duzeyi) kontrol
        # tasirdi.
        donemler = {o.donem_no for o in liste}
        if len(donemler) > 1:
            raise ValueError(f"K1 ayni donem icinden ornekler (on-kayit §6 K1); bulunan donem numaralari "
                             f"{sorted(donemler)}. Ayni sembolun baska listeleme donemi baska bir rejimdir.")
        ogeler = pd.DatetimeIndex([o.plan.sinyal_zamani for o in liste])
        if len(ogeler) and ogeler.has_duplicates:
            raise ValueError("K1 adaylari tekrarsiz olmali (ayni bar iki kez aday olamaz).")
        return _aday_kur(rol, hipotez, yapilandirma, kume, ogeler)
    zamanlar = pd.DatetimeIndex([o.plan.sinyal_zamani for o in liste])
    if len(zamanlar) and not all(pencere_modulu.ayni_an(z, zamanlar[0]) for z in zamanlar):
        raise ValueError("K2 ayni t barindan ornekler (on-kayit §6 K2); adaylarin sinyal zamanlari farkli: "
                         f"{sorted({str(z) for z in zamanlar})}.")
    return _aday_kur(rol, hipotez, yapilandirma, kume, sembol_sirasi([o.sembol for o in liste]),
                     zamanlar[0] if len(zamanlar) else None)

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
                     gecerli.bar_zamani)


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
                     gecerli.bar_zamani)


def ornekle(adaylar: Adaylar, *, sembol: str, olay_zamani, sayi: int = None) -> KontrolHavuzu:
    """Adaylardan IADESIZ on-kayit §6'daki 10 tane ceker.

    On-kayit §6 rev.11: "Iki havuzda da ornekleme iadesizdir. Aday sayisi 10'dan azsa adaylarin
    tamami alinir ve sayi sonuc dosyasina yazilir. ... Ornekleme, §7'deki tohumdan (hipotez,
    yapilandirma, kume, sembol, olay zamani) demetiyle turetilen alt tohumla yapilir."

    `adaylar`: `adaylari_kur` / `k1_adaylari` / `k2_adaylari` ciktisi; ham liste kabul edilmez
    (on-kayit §6 rev.13). `sembol` ve `olay_zamani`: OLAYIN sembolu ve bar zamani; hipotez,
    yapilandirma ve kume `adaylar`dan gelir. TOHUM CAGIRANDAN ALINMAZ ve `sayi` on-kayit
    degeridir (denetci bulgusu D-C5); serbest deger acik hata verir.

    Adaylar once siralanir, boylece sonuc cagirandaki sirayla degismez. Secilenler aday sirasinda
    doner. Secilen aday sonradan DUSMEZ (on-kayit §6 rev.13): secilenler adaylarin alt kumesidir
    ve sayilari `min(10, aday sayisi)`dir; bu donuste denetlenir.
    """
    hedef = config.KONTROL_SAYISI if sayi is None else int(sayi)
    if isinstance(sayi, bool) or hedef != config.KONTROL_SAYISI:
        raise ValueError(f"sayi on-kayit §6 degeri olmali ({config.KONTROL_SAYISI}); verilen {sayi!r}.")
    gecerli = aday_dogrula(adaylar)
    sirali = _sirala(gecerli.ogeler)
    n = len(sirali)
    if n == 0:
        return KontrolHavuzu((), 0)
    tohum = alt_tohum(gecerli.hipotez, gecerli.yapilandirma, gecerli.kume, sembol, olay_zamani)
    # Alt tohum ve onu ureten demet havuzla birlikte doner (on-kayit §8 madde 1; denetci D-C6):
    # F2 raporunda yeniden turetilmesi gerekmez ve p-degeri tarafiyla simetriktir.
    kimlik_demeti = alt_tohum_demeti(gecerli.hipotez, gecerli.yapilandirma, gecerli.kume, sembol,
                                     olay_zamani)
    iz = dict(tohum=int(tohum), alt_tohum_demeti=kimlik_demeti, genel_tohum=config.TOHUM)
    if n <= hedef:
        havuz = KontrolHavuzu(tuple(sirali), n, **iz)
    else:
        uretec = np.random.default_rng(int(tohum))
        secilen = sorted(int(i) for i in uretec.choice(n, size=hedef, replace=False))
        havuz = KontrolHavuzu(tuple(sirali[i] for i in secilen), n, **iz)
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
    for i, cift in enumerate(ciftler):
        if not (isinstance(cift, tuple) and len(cift) == 2
                and all(isinstance(h, KontrolHavuzu) for h in cift)):
            raise TypeError(f"havuz_ciftleri[{i}] (K1, K2) `KontrolHavuzu` cifti olmali; verilen {cift!r}.")
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
