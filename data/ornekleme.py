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
from data import pencere as pencere_modulu
from data import pozisyon as pozisyon_modulu
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
    # Yapilandirma ya izgaradaki parametre demeti ya da onun KIMLIGIDIR (`Adaylar` kimligi tasir).
    kimlik = (yapilandirma if isinstance(yapilandirma, str)
              else sinyal_modulu.yapilandirma_kimligi(ad, yapilandirma))
    if isinstance(yapilandirma, str) and not kimlik.startswith(f"{ad}:"):
        raise ValueError(f"{ad} yapilandirma kimligi {ad!r} ile baslamali; verilen {kimlik!r}.")
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
    _imza: int = field(default=0, repr=False, compare=False)

    def __len__(self) -> int:
        return len(self.ogeler)


def _aday_imzasi(a: Adaylar) -> int:
    return hash((_ADAY_GIZLI, a.rol, a.hipotez, a.yapilandirma, a.kume, a.ogeler))


def aday_dogrula(adaylar) -> Adaylar:
    """`adaylari_kur`un urettigi ve degistirilmemis bir aday kumesi mi? (on-kayit §6 rev.13)"""
    if not isinstance(adaylar, Adaylar):
        raise TypeError(f"Kapidan gecmis aday kumesi gerekir (ornekleme.adaylari_kur ciktisi); verilen: "
                        f"{type(adaylar).__name__}. Ham bar damgasi ya da sembol listesi aday DEGILDIR "
                        "(on-kayit §6 rev.13: adaylik ornekelemeden once belirlenir).")
    if adaylar._imza != _aday_imzasi(adaylar):
        raise ValueError("Adaylar elle kurulmus ya da degistirilmis; yalnizca ornekleme.adaylari_kur uretir.")
    return adaylar


def _aday_kur(rol, hipotez, yapilandirma, kume, ogeler) -> Adaylar:
    a = Adaylar(rol, hipotez, yapilandirma, kume, tuple(ogeler))
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
        ogeler = pd.DatetimeIndex([o.plan.sinyal_zamani for o in liste])
        if len(ogeler) and ogeler.has_duplicates:
            raise ValueError("K1 adaylari tekrarsiz olmali (ayni bar iki kez aday olamaz).")
        return _aday_kur(rol, hipotez, yapilandirma, kume, ogeler)
    zamanlar = pd.DatetimeIndex([o.plan.sinyal_zamani for o in liste])
    if len(zamanlar) and not all(pencere_modulu.ayni_an(z, zamanlar[0]) for z in zamanlar):
        raise ValueError("K2 ayni t barindan ornekler (on-kayit §6 K2); adaylarin sinyal zamanlari farkli: "
                         f"{sorted({str(z) for z in zamanlar})}.")
    return _aday_kur(rol, hipotez, yapilandirma, kume, sembol_sirasi([o.sembol for o in liste]))

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


def k1_adaylari(adaylar: Adaylar, olay_zamanlari, birincil_ufuk: int, bar: str) -> Adaylar:
    """K1 adaylarindan, ayni yapilandirmanin olaylarina yakin olanlari ayiklar (ORNEKLEMEDEN ONCE).

    `adaylar`: `adaylari_kur(..., rol="K1")` ciktisi -- ayni coinin, ayni kume ve donem icindeki,
    kapidan gecmis barlari. `olay_zamanlari`: AYNI YAPILANDIRMANIN olusmus olaylarinin zamanlari;
    reddedilmis adaylar ve baska yapilandirmalarin olaylari verilmez (on-kayit §6 rev.11).

    Doner: ayiklanmis `Adaylar`. Ayiklama yalnizca BURADA yapilir; `ornekle` secilen bir adayi
    sonradan dusurmez (on-kayit §6 rev.13).
    """
    gecerli = aday_dogrula(adaylar)
    if gecerli.rol != "K1":
        raise ValueError(f"k1_adaylari K1 rolunde aday bekler; verilen {gecerli.rol!r}.")
    kalan = tuple(t for t in pd.DatetimeIndex(gecerli.ogeler)
                  if k1_uzak_mi(t, olay_zamanlari, birincil_ufuk, bar))
    return _aday_kur(gecerli.rol, gecerli.hipotez, gecerli.yapilandirma, gecerli.kume, kalan)


def k2_adaylari(adaylar: Adaylar, olay_ureten_semboller, *, olay_sembolu: str) -> Adaylar:
    """K2 adaylarindan, o anda olay ureten coinleri ve olayin kendi coinini ayiklar (ORNEKLEMEDEN ONCE).

    `adaylar`: `adaylari_kur(..., rol="K2")` ciktisi -- AYNI t barinda kapidan gecmis coinler.
    `olay_ureten_semboller`: o barda AYNI YAPILANDIRMANIN olayini ureten coinler (on-kayit §6
    rev.12: olcut kosullar degil, o yapilandirmanin olusmus OLAY KUMESIDIR). On-kayit §6 K2 "diger
    coinlerden" dedigi icin olayin kendi sembolu de ayiklanir.

    Doner: ayiklanmis `Adaylar` (semboller alfabetik sirada; on-kayit §6 rev.11).
    """
    gecerli = aday_dogrula(adaylar)
    if gecerli.rol != "K2":
        raise ValueError(f"k2_adaylari K2 rolunde aday bekler; verilen {gecerli.rol!r}.")
    ureten = set(olay_ureten_semboller)
    kalan = tuple(s for s in gecerli.ogeler if s != olay_sembolu and s not in ureten)
    return _aday_kur(gecerli.rol, gecerli.hipotez, gecerli.yapilandirma, gecerli.kume, kalan)


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
    if n <= hedef:
        havuz = KontrolHavuzu(tuple(sirali), n)
    else:
        uretec = np.random.default_rng(int(tohum))
        secilen = sorted(int(i) for i in uretec.choice(n, size=hedef, replace=False))
        havuz = KontrolHavuzu(tuple(sirali[i] for i in secilen), n)
    if len(havuz) != min(hedef, n) or not set(havuz.secilenler) <= set(sirali):
        raise AssertionError("secilen aday sonradan dusmemeli (on-kayit §6 rev.13).")
    return havuz


def _sirala(adaylar):
    liste = list(adaylar)
    if len(set(liste)) != len(liste):
        raise ValueError("adaylar tekrarsiz olmali (ornekleme iadesizdir).")
    return sorted(liste)


def olay_analize_girer(k1: KontrolHavuzu, k2: KontrolHavuzu) -> bool:
    """On-kayit §6 rev.11: "Bir olayin her iki havuzu da bossa o olay analize girmez; en az bir
    kontrolu olan olay kalir." """
    return bool(len(k1) or len(k2))
