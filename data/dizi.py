"""Olay dizisi kurallari: bekleme suresi, H1'de tek izleme, H3'te "ilk gun" (on-kayit §5, rev.11).

Bu kurallar tek bar duzeyinde tanimlanamaz: bir barin olay olup olmadigi, ayni coinde ayni
yapilandirmanin daha onceki barlarina baglidir. Rev.11'den once kodda hic yoktu (RESULTS §14.19
maddeleri 11, 15, 16: "bekleme suresini uygulayan kod yok", "pump, tepe ve izleme kodu yok",
"H3 sinyal kodu yok").

On-kayit §5 (rev.11):
  - **Bekleme suresi.** "Ayni coinde bir olaydan sonra, o hipotezin birincil ufku boyunca yeni
    olay sayilmaz (bekleme suresi). Sure olay barindan (t) olculur ve t + birincil ufuk anina
    kadar surer. Bekleme yalnizca olusmus olaylar icin isler: §4'teki karar noktasindan gecmemis
    bir aday beklemeyi baslatmaz. Bekleme yapilandirma basina isler; her yapilandirma kendi olay
    dizisini uretir. Bekleme donem sinirini asmaz: yeni donemde sifirlanir."
  - **H1 tek izleme** (§5 H1 madde 4). "Bir coinde ayni anda yalnizca bir izleme yurur. Izleme
    surerken pump kosulunu saglayan yeni bir bar gelirse yok sayilir: tepe ve 12 barlik sayac
    ilk pump barindan olculmeye devam eder. Izleme, teyit bariyla ya da 12 bar doldugunda biter;
    yeni bir izleme ancak bundan sonra (ve olay olustuysa bekleme suresi dolduktan sonra)
    baslayabilir. Boylece bir teyit bari en cok bir olay sayar."
  - **Izleme penceresinin donem ve kume siniri** (§5 H1 madde 4, rev.13). "Izleme yalnizca donem
    ici ve kume ici barlar uzerinde yurur, bu barlar arasinda teyit gelmezse izleme olay
    uretmeden kapanir. Donemin ya da kumenin sonuna 12 bardan az kalmisken baslayan bir pump
    bari, bu yuzden hic olay uretmeyebilir. ... Ayni kural bir olayin dayandigi butun barlar icin
    gecerlidir: sinyal pencereleri, izleme penceresi ve pump barinin kendisi ayni donemin ve ayni
    kumenin icinde olmalidir."

    Bu kural iki parcadan gelir. (1) `zamanlar` SOZLESME geregi yalnizca donem ici ve kume ici
    sinyal barlarini tasir (asagidaki argument aciklamasi), yani izleme bu barlarin disina
    cikamaz ve donem/kume sonundan sonra teyit arayamaz. (2) 12 barlik sinir TAKVIMLE olculur,
    barlarin varligiyla degil (rev.13; sizinti bulgusu S-B3): teyit araligi
    `(pump, pump + 12 x adim]`dir. Ikisi birlikte, teyidi onay verisinde ya da donem disinda
    arayan bir yolu kapatir.
  - **H3 ilk gun** (§5 H3 madde 3). "'Ilk gun', iki kosulun birlikte saglandigi KESINTISIZ
    dizinin ilk gunudur. Dizi, kosullardan biri saglanmadigi ya da §2 'Tamlik sarti' geregi
    hesaplanamadigi gunde kesilir; dizi kesildikten sonra kosullar yeniden birlikte saglanirsa
    o gun yeni bir 'ilk gun'dur ve bekleme suresi ayrica uygulanir. Kesintisiz suren bir dizinin
    icinde, bekleme suresi dolsa bile yeni olay sayilmaz."
  - **H3 dizisinin tanimi** (§5 H3 madde 3, rev.13). "Dizi kosullarla tanimlidir, karar
    noktasinin onayiyla degil: bir gun iki kosulu birlikte sagliyorsa diziye aittir, o gunde olay
    olusup olusmadigina bakilmaz. Bunun sonucu olarak, dizinin ilk gunu karar noktasindan
    gecmezse (or. funding tamligi saglanmadigi ya da giris bari bulunmadigi icin) o dizi hic olay
    uretmez; dizinin ikinci gunu 'ilk gun' sayilmaz." Kodda bu, diziyi kapi denemesinden ONCE ve
    onun sonucundan bagimsiz kurmak demektir. Dizi ayrica TAKVIMLE kesilir: seride bulunmayan
    (bar olmayan, §2 geregi hesaplanamaz) bir gun diziyi keser, listenin bitisikligine
    bakilmaz (sizinti bulgusu S-B2).

**Beklemenin ust ucu (uygulama karari, on-kayitta acikca yazili degil).** "t + birincil ufuk
anina kadar surer" cumlesi, tam o ana denk gelen barin beklemenin icinde mi disinda mi oldugunu
soylemez. Bu modul YARI ACIK okumayi uygular: bekleme araligi `(t0, t0 + h × adim]`, yani tam o
ana denk gelen bar hala beklemededir ve ilk serbest bar `t0 + (h + 1) × adim`'dir. Gerekce
on-kaydin baska yerlerdeki ayni yapisidir (§4 "Funding odemesinin sinirlari": "giris anindaki
odeme haric, cikis anindaki dahildir"; §4 "Funding sinyal penceresinin tamligi": "pencere
basina tam denk gelen kayit girmez, pencere sonuna denk gelen girer"; rev.10 bu benzetmeyi
acikca kullanir). Ilk serbest bar, olayin pozisyonunun cikis aninda (giris + h × adim) kapanan
bardir; yani yeni olay ancak oncekinin pozisyonu kapandiktan sonra sayilir. Secim tek sabitte
(`BEKLEME_UST_UC_DAHIL`) toplanmistir ve rapora acik nokta olarak yazilmistir.

**Kapinin ciktisi DOGRULANIR (sizinti bulgusu S-B1).** Rev.13'ten once `_dene`, `karar`in
dondurdugu HER nesneyi olay sayiyor ve kendi beklemesini baslatiyordu; `pozisyon.onay_dogrula`
cagrilmiyordu. Dizi ile kapi arasindaki tek baglanti denetimsiz oldugu icin olay kumesine
kapidan gecmemis bir nesne, bir KONTROL (K1/K2) pozisyonu ya da baska bir yapilandirmanin olayi
girebiliyordu. Artik her donus su dort noktada denetlenir (`_olay_dogrula`):
  1. imza: nesne gercekten `pozisyon.olay_karari`dan geldi ve degistirilmedi,
  2. rol: "olay" (on-kayit §6 rev.11 "Kontrolun ne olctugu": roller ayridir),
  3. hipotez ve yapilandirma kimligi: dizinin kostugu demetle ayni (on-kayit §5 rev.11: "Bekleme
     yapilandirma basina isler; her yapilandirma kendi olay dizisini uretir"),
  4. sorulan (t, capa) cifti: pozisyonun sinyal zamani t, capasi ise dizinin verdigi capa. H1'de
     bu, capanin IZLEMENIN ILK pump bari oldugunu garanti eder ve "bir teyit bari en cok bir olay
     sayar" (on-kayit §5 H1 madde 4) kuralini denetlenebilir kilar.
Denetim `pozisyon` modulunu import eder ama kapiyi CAGIRMAZ: cagri hala cagirandan gelir.

Modul veri yuklemez ve kapiyi kendisi cagirmaz. Kapi ve kosul degerlendirmesi cagiran tarafindan
iki cagrilabilirle verilir; boylece dizi kurallari veriden bagimsiz sinanabilir. Getiri
hesaplamaz.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

import config
from data import pencere as pencere_modulu
from data import pozisyon as pozisyon_modulu
from data import sinyal as sinyal_modulu

# Beklemenin ust ucu penceredeki gibi DAHILDIR (yukaridaki uygulama karari). False yapilirsa
# bekleme `(t0, t0 + h × adim)` olur ve tam o ana denk gelen bar serbest kalir.
BEKLEME_UST_UC_DAHIL = True

# H3'un "ilk gun" kurali: kesintisiz dizinin yalnizca ilk gunu olaydir.
DIZI_ILK_GUN_HIPOTEZLERI = ("H3",)
# H1'in tek izleme kurali.
IZLEMELI_HIPOTEZLER = ("H1",)


class KosulHesaplanamaz:
    """`kosul` cagrilabilirinin "deger hesaplanamadi" yaniti (on-kayit §2 "Tamlik sarti").

    `None` ile ayni anlamda kullanilir; adlandirilmis olmasi cagiranin niyetini okunur kilar.
    """


_OLAY_GIZLI = object()


@dataclass(frozen=True)
class Olay:
    """Dizi kurallarindan VE kapidan gecmis bir olay. Yalnizca `olay_dizisi` uretir.

    On-kayit §4 "Olayin kumede olusma olcutu" (rev.12): "Tek karar noktasinin onayi, bir olayin
    olusmasi icin gereklidir ama YETERLI DEGILDIR: §5'teki dizi kurallari (bekleme suresi, H1'de
    tek izleme, H3'te ilk gun) da saglanmalidir. Olay kumesi yalnizca iki kosulun birlikte
    saglandigi barlardan olusur; dizi kurallarindan gecmemis bir onay olay DEGILDIR ve hicbir
    hesaba, hicbir kontrol olcutune girmez."

    Bu yuzden nesne IMZALIDIR (`olay_dogrula`): "olay" tipi yalnizca `olay_dizisi`den cikar,
    elle kurulamaz. Kapinin onayi (`pozisyon.OnaylanmisPozisyon`) tek basina bir olay nesnesi
    uretmez; F2'nin olay kumesi `DiziSonucu.olaylar`dir. Tersi yon `_olay_dogrula`dadir: dizi de
    kapidan gecmemis bir onayi olay saymaz. Ikinci (ve zayif) bir savunma kaynak taramasidir
    (`tests/tarama_yardimcisi.DIZI_ATLATMA_DESENI`, `olay_rolu_ihlalleri`).
    """

    zaman: pd.Timestamp
    capa: pd.Timestamp | None
    pozisyon: object
    _imza: int = field(default=0, repr=False, compare=False)


def _olay_imzasi(o: Olay) -> int:
    return hash((_OLAY_GIZLI, o.zaman, o.capa, getattr(o.pozisyon, "_imza", None),
                 getattr(o.pozisyon, "rol", None), getattr(o.pozisyon, "hipotez", None),
                 getattr(o.pozisyon, "yapilandirma", None)))


def _olay_kur(zaman, capa, pozisyon) -> Olay:
    o = Olay(zaman, capa, pozisyon)
    return replace(o, _imza=_olay_imzasi(o))


def olay_dogrula(olay) -> None:
    """`olay_dizisi`nin urettigi ve degistirilmemis bir olay mi? (on-kayit §4 rev.12)

    F2'nin olay kumesini tuketen her kod bu yuklemle baslar: dizi kurallarindan gecmemis bir
    onay, elle kurulmus bir `Olay` nesnesiyle olay kumesine sokulamaz.
    """
    if not isinstance(olay, Olay):
        raise TypeError(f"Olay gerekir (dizi.olay_dizisi ciktisi); verilen: {type(olay).__name__}. Kapinin "
                        "onayi tek basina olay DEGILDIR (on-kayit §4 rev.12: dizi kurallari da gerekli).")
    if olay._imza != _olay_imzasi(olay):
        raise ValueError("Olay elle kurulmus ya da degistirilmis; yalnizca dizi.olay_dizisi uretir.")
    # Olayin tasidigi ONAY da degismemis olmali (sizinti bulgusu S-C1). `_olay_imzasi` pozisyonun
    # kendi `_imza` ALANINI karistirir; `dataclasses.replace` o alani oldugu gibi kopyaladigi icin
    # `p1` ya da `funding_toplami` bozulmus bir pozisyon tasiyan olay imza denetimini geciyordu.
    # `pozisyon.onay_dogrula` imzayi ALANLARDAN yeniden hesaplar, yani degisiklik burada duser.
    # Gerekce: olayin "hangi pozisyona ait oldugu" kimliginin parcasidir; bozulmus fiyat ya da
    # funding tasiyan bir onay, on-kayit §4'teki tek karar noktasindan gecmis onay degildir.
    pozisyon_modulu.onay_dogrula(olay.pozisyon)


@dataclass(frozen=True)
class Ret:
    """Dizi ya da kapi tarafindan reddedilen aday; yalnizca sayim ve iz icin."""

    zaman: pd.Timestamp
    capa: pd.Timestamp | None
    gerekce: str


@dataclass(frozen=True)
class DiziSonucu:
    olaylar: tuple[Olay, ...] = ()
    retler: tuple[Ret, ...] = ()

    @property
    def olay_zamanlari(self) -> tuple[pd.Timestamp, ...]:
        return tuple(o.zaman for o in self.olaylar)


def bekleme_sonu(olay_zamani, birincil_ufuk: int, bar: str) -> pd.Timestamp:
    """Beklemenin bittigi an: `t + birincil ufuk × adim` (on-kayit §5 rev.11)."""
    t = pencere_modulu.utc_zamani(olay_zamani, "olay_zamani")
    h = pencere_modulu.birincil_ufuk_dogrula(birincil_ufuk, bar)
    return t + h * pencere_modulu.adim(bar)


def beklemede_mi(t, olay_zamani, birincil_ufuk: int, bar: str) -> bool:
    """t bari, `olay_zamani`nda olusmus olayin bekleme suresinin icinde mi? (on-kayit §5 rev.11)

    Aralik `(olay_zamani, bekleme_sonu]` (yukaridaki uygulama karari; `BEKLEME_UST_UC_DAHIL`).
    Karsilastirmalar §4 "Zaman toleransi"na gore.
    """
    zaman = pencere_modulu.utc_zamani(t, "t")
    t0 = pencere_modulu.utc_zamani(olay_zamani, "olay_zamani")
    son = bekleme_sonu(t0, birincil_ufuk, bar)
    if not pencere_modulu.sonra(zaman, t0):
        return False  # olay barinin kendisi ve oncesi bekleme degildir
    if BEKLEME_UST_UC_DAHIL:
        return bool(pencere_modulu.ayni_ya_da_once(zaman, son))
    return bool(pencere_modulu.once(zaman, son))


def _zamanlar_dogrula(zamanlar, bar: str) -> pd.DatetimeIndex:
    indeks = pd.DatetimeIndex(zamanlar)
    if len(indeks) and indeks.tz is None:
        raise TypeError("zamanlar saat dilimsiz (tz-naive); butun zaman damgalari UTC olmali.")
    if not indeks.is_monotonic_increasing or indeks.has_duplicates:
        raise ValueError("zamanlar artan ve tekrarsiz olmali (donem ici sinyal barlari).")
    return indeks


def _kosul_sonucu(deger, yer: str):
    """`kosul` cagrilabilirinin yanitini uc duruma indirir: True, False, hesaplanamaz."""
    if deger is None or deger is KosulHesaplanamaz or isinstance(deger, KosulHesaplanamaz):
        return None
    if not isinstance(deger, (bool, np.bool_)):
        raise TypeError(f"{yer}: kosul yaniti bool ya da hesaplanamaz olmali; verilen {deger!r}.")
    return bool(deger)


def _olay_dogrula(pozisyon, *, hipotez: str, yapilandirma_kimligi: str, t, capa) -> None:
    """`karar`in dondurdugu nesne gercekten SORULAN olayin onayi mi? (sizinti bulgusu S-B1)

    On-kayit §4 "Olayin kumede olusma olcutu" (rev.12): "Tek karar noktasinin onayi, bir olayin
    olusmasi icin gereklidir ama yeterli degildir." Bu fonksiyon iliskiyi ters yonde kapatir:
    dizi kurallarindan gecen bir bar da ancak KAPININ onayiyla olay olur ve o onay baska bir
    barin, baska bir rolun ya da baska bir yapilandirmanin onayi olamaz.
    """
    pozisyon_modulu.onay_dogrula(pozisyon)      # imzasiz / elle kurulmus nesne burada duser
    if pozisyon.rol != "olay":
        raise ValueError(f"dizi yalnizca 'olay' rolundeki onayi olay sayar; verilen rol {pozisyon.rol!r} "
                         "(on-kayit §6 rev.11: kontrol ve olay roller ayridir).")
    if pozisyon.hipotez != hipotez or pozisyon.yapilandirma != yapilandirma_kimligi:
        raise ValueError(
            f"onayli pozisyon baska bir demete ait: ({pozisyon.hipotez}, {pozisyon.yapilandirma}); dizi "
            f"({hipotez}, {yapilandirma_kimligi}) kosuyor. Bekleme yapilandirma basina isler ve her "
            "yapilandirma kendi olay dizisini uretir (on-kayit §5 rev.11).")
    if not pencere_modulu.ayni_an(pozisyon.plan.sinyal_zamani, t):
        raise ValueError(f"onayli pozisyonun sinyal zamani {pozisyon.plan.sinyal_zamani}, dizi {t} barini "
                         "sordu.")
    if (capa is None) != (pozisyon.capa is None) or (
            capa is not None and not pencere_modulu.ayni_an(pozisyon.capa, capa)):
        raise ValueError(f"onayli pozisyonun capasi {pozisyon.capa}, dizi {capa} capasini sordu. H1'de capa "
                         "izlemenin ILK pump baridir (on-kayit §5 H1 madde 4: bir teyit bari en cok bir "
                         "olay sayar).")


def olay_dizisi(hipotez, yapilandirma, zamanlar, bar: str, *, birincil_ufuk: int, kosul, karar) -> DiziSonucu:
    """Bir (sembol, donem, kume, yapilandirma) dizisinde olaylari sirayla bulur (on-kayit §5 rev.11).

    `zamanlar`: hipotezin izgarasindaki DONEM ICI ve KUME ICI sinyal barlari, artan sirada. Dizi
    kurallari donem ve kume basina isler; bekleme donem sinirini asmaz (on-kayit §5: "yeni
    donemde sifirlanir"), bu yuzden her donem icin ayri cagri yapilir.

    `kosul(t, capa)`: o barda hipotezin §5 kosullari saglandi mi? `True` / `False` / `None`
    (deger hesaplanamadi, §2 "Tamlik sarti"). H1'de `capa=None` cagrisi PUMP kosulunu, `capa=p`
    cagrisi p capali TEYIT kosulunu sorar. H2 ve H3'te `capa` her zaman `None`'dir.

    `karar(t, capa)`: tek karar noktasi (`pozisyon.olay_karari`). Olay olusursa onayli pozisyon
    doner, olusmazsa `pencere.OlayOlusmaz` alt sinifi firlatir. Kapidan gecmeyen aday beklemeyi
    BASLATMAZ (on-kayit §5 rev.11).

    Doner: `DiziSonucu` (olaylar ve retler). Getiri hesaplanmaz, deger raporlanmaz.
    """
    ad = sinyal_modulu._hipotez_dogrula(hipotez)
    gecerli = sinyal_modulu.yapilandirma_dogrula(ad, yapilandirma)
    kimlik = sinyal_modulu.yapilandirma_kimligi(ad, gecerli)
    if bar != config.HIPOTEZ_IZGARASI[ad]:
        raise ValueError(f"{ad} izgarasi {config.HIPOTEZ_IZGARASI[ad]}; verilen {bar!r} (on-kayit §2).")
    h = pencere_modulu.birincil_ufuk_dogrula(birincil_ufuk, bar)
    indeks = _zamanlar_dogrula(zamanlar, bar)

    olaylar: list[Olay] = []
    retler: list[Ret] = []
    son_olay = None          # bekleme suresinin cikti olay bari
    izleme_pump = None       # H1: yuruyen izlemenin pump bari
    dizi_suruyor = False     # H3: kesintisiz dizi suruyor mu
    onceki_bar = None        # H3: dizinin takvim bitisikligi icin islenen son bar
    adim = pencere_modulu.adim(bar)

    def _beklemede(t) -> bool:
        return son_olay is not None and beklemede_mi(t, son_olay, h, bar)

    def _dene(t, capa):
        """Kapiyi cagirir; olay olustuysa kaydeder ve beklemeyi baslatir."""
        nonlocal son_olay
        try:
            pozisyon = karar(t, capa)
        except pencere_modulu.OlayOlusmaz as hata:
            retler.append(Ret(t, capa, pencere_modulu.ret_gerekcesi(hata)))
            return False
        _olay_dogrula(pozisyon, hipotez=ad, yapilandirma_kimligi=kimlik, t=t, capa=capa)
        olaylar.append(_olay_kur(t, capa, pozisyon))
        son_olay = t
        return True

    for t in indeks:
        if ad in IZLEMELI_HIPOTEZLER:
            if izleme_pump is not None:
                # Izleme penceresi TAKVIMLE sinirlidir (on-kayit §5 H1 madde 3-4, rev.13; sizinti
                # bulgusu S-B3): teyit, pump barindan sonraki 12 bar ICINDE olmali, yani
                # `(pump, pump + 12 x adim]` araliginda. Rev.13 oncesi sinir yalnizca islenen
                # barlarin varligina bagliydi: `zamanlar`da 12. bar yoksa 13. bar hala teyit adayi
                # sayiliyordu. Simdi sinir barlarin degil takvimin isi.
                izleme_sonu = izleme_pump + config.H1_IZLEME_BAR * adim
                if pencere_modulu.ayni_ya_da_once(t, izleme_sonu):
                    # Izleme suruyor: bu bar teyit adayidir, yeni pump bari YOK SAYILIR (madde 4).
                    teyit = _kosul_sonucu(kosul(t, izleme_pump), f"{ad} teyit {t}")
                    if teyit:
                        _dene(t, izleme_pump)   # teyit bari en cok bir olay sayar
                        izleme_pump = None      # izleme teyit bariyla biter
                    elif teyit is None:
                        retler.append(Ret(t, izleme_pump, "sinyal_penceresi_tam_degil"))
                    if izleme_pump is not None and not pencere_modulu.once(t, izleme_sonu):
                        # 12 bar doldu. "Izlemeyi bitiren bar o izlemenin parcasidir ve yeni bir
                        # pump bari olarak degerlendirilmez" (rev.12): bu yuzden `continue`.
                        izleme_pump = None
                    continue
                # Bar izleme penceresinin DISINDA: takvimde 12 bar dolmus ve o anda (ya da o ana
                # kadar) teyit gelmemis. "Bu barlar arasinda teyit gelmezse izleme olay uretmeden
                # kapanir" (rev.13). Izlemeyi bitiren bir bar YOKTUR -- sinir takvimde dolmustur --
                # bu yuzden bu bar izlemenin parcasi degildir ve yeni bir pump bari olabilir;
                # bitisik seride ayni davranis gecerlidir (orada sinira denk gelen bar izlemenin
                # parcasidir ve bir sonraki bar serbesttir).
                izleme_pump = None
            if _beklemede(t):
                retler.append(Ret(t, None, "bekleme_suresi"))
                continue
            pump = _kosul_sonucu(kosul(t, None), f"{ad} pump {t}")
            if pump:
                izleme_pump = t
            elif pump is None:
                retler.append(Ret(t, None, "sinyal_penceresi_tam_degil"))
            continue

        # Dizi TAKVIMLE kesilir, listenin bitisikligiyle degil (on-kayit §5 H3 madde 3, rev.13;
        # sizinti bulgusu S-B2). Iki islenen gun arasinda bir adimdan fazla bosluk varsa aradaki
        # gun(ler) seride YOKTUR; on-kayit §2 "Tamlik sarti" geregi o gunlerde kosul hesaplanamaz
        # ve "dizi ... §2 'Tamlik sarti' geregi hesaplanamadigi gunde kesilir". Rev.13 oncesi
        # `dizi_suruyor` yalnizca ISLENEN barlarda sifirlaniyordu, bu yuzden eksik (silinmis) gun
        # diziyi kesmiyor ve sonraki gun "ilk gun" sayilmiyordu.
        if onceki_bar is not None and not pencere_modulu.ayni_an(t, onceki_bar + adim):
            dizi_suruyor = False
        onceki_bar = t
        saglandi = _kosul_sonucu(kosul(t, None), f"{ad} kosul {t}")
        if saglandi is None:
            dizi_suruyor = False               # tamlik gereği hesaplanamayan gun diziyi KESER
            retler.append(Ret(t, None, "sinyal_penceresi_tam_degil"))
            continue
        if not saglandi:
            dizi_suruyor = False
            continue
        # Dizi KOSULLARLA tanimlidir, karar noktasinin onayiyla degil (on-kayit §5 H3 madde 3,
        # rev.13): "bir gun iki kosulu birlikte sagliyorsa diziye aittir, o gunde olay olusup
        # olusmadigina bakilmaz." Bu yuzden `dizi_suruyor` ASAGIDAKI kapi denemesinden ONCE ve
        # onun sonucundan BAGIMSIZ olarak kurulur: dizinin ilk gunu kapidan gecmezse (funding
        # tamligi, giris bari vb.) o dizi hic olay uretmez ve ikinci gun "ilk gun" sayilmaz.
        ilk_gun = not (ad in DIZI_ILK_GUN_HIPOTEZLERI and dizi_suruyor)
        dizi_suruyor = True
        if not ilk_gun:
            # Kesintisiz dizinin icinde: bekleme dolsa bile yeni olay sayilmaz (madde 3).
            retler.append(Ret(t, None, "dizi_ilk_gun_degil"))
            continue
        if _beklemede(t):
            retler.append(Ret(t, None, "bekleme_suresi"))
            continue
        _dene(t, None)

    return DiziSonucu(tuple(olaylar), tuple(retler))
