"""Zamanla tanimli pencere, tamlik kontrolu ve ufuk (on-kayit §2, revizyon 3).

Revizyon 3'ten once her hesap penceresini kendi indeksleriyle sayiyordu; bu,
eksik bar bulunan seride pencerenin sessizce gecmise uzamasina yol aciyordu.
Bu modul o mantigi tek yere toplar.

Kurallar (on-kayit §2 rev.3):
  - **Pencereler zamanla tanimlanir.** "Son N bar" = son N x adim sureli zaman
    araligi. Bar sayisiyla degil, zaman damgasiyla hesaplanir.
  - **Tamlik sarti.** Pencerede beklenen barlardan biri bile eksikse deger
    hesaplanmaz (NaN) ve o barda olay ya da kontrol olusmaz.
  - **Ufuk.** Ufuk zamanla olculur: h bar = h x adim. Hedef cikis bari eksikse
    cikis, sonraki ilk mevcut barin ACILIS fiyatindandir. Donem sonu ve delist
    kurallari onceliklidir.
  - **Giris.** t+1 bari eksikse olay olusmaz.
  - Ayni kurallar K1 ve K2 kontrol barlarina da uygulanir.

Donem kisitlari da buradan gecer. On-kayit §2 rev.7: donem sinirlari bar
duzeyindedir ve karantina kurali kaldirilmistir; bu modulde karantina kavrami yoktur.

Sinir parametreleri (F1 kapanis bulgulari 1 ve 2): donem ve kume
sinirlari pencere ve cikis fonksiyonlarinda ANAHTAR SOZCUKLE ve VARSAYILANSIZ
verilir. Unutulan sinir TypeError verir; sinir gercekten yoksa cagiran taraf
bunu acikca `None` ile soyler. Boylece bir kuralin sessizce atlanmasi mumkun
olmaz.

Bu modul tamamen saftir: ag veya disk kullanmaz.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

import config

# Bar tipine gore izgara adimi.
ADIMLAR = {
    config.BAR_4H: pd.Timedelta(hours=4),
    config.BAR_1D: pd.Timedelta(days=1),
}

# --- Zaman toleransi (on-kayit §4 rev.8 "Zaman toleransi") --------------------
#
# "Projedeki butun zaman karsilastirmalarinda iki an arasindaki fark 1 dakikadan
# kesin olarak kucukse bu iki an ayni sayilir; tam 1 dakikalik fark ayni an
# degildir." Tek tanim `ayni_an`dir; asagidaki iliskiler ve iki kenar ondan turer
# ve projedeki zaman karsilastirmalari (funding kaydi, donem siniri, cikis ani)
# yalnizca bunlari kullanir. Bar acilislari 4h izgarasinda tam hizalidir
# (on-kayit §2 rev.8 "1 gunluk barlar", RESULTS §14.11); bar-bar karsilastirmasi
# icin tam esitlik ile `ayni_an` ayni sonucu verir.
ZAMAN_TOLERANSI = pd.Timedelta(minutes=1)
# Eski ad; ayni sabit.
ODEME_TOLERANSI = ZAMAN_TOLERANSI


# --- Donem bitisi (B), donem kapanisi (K), donem uyeligi (on-kayit §2 rev.8) ------
#
# "Donemin son 4 saatlik barinin acilis anina donem bitisi (B), kapanis anina donem
# kapanisi (K = B + 4 saat) denir." B, `Donem.bitis`tir; K yalnizca
# `donem_kapanisi`ndan hesaplanir (`Donem.kapanis` onu cagirir). Baska hicbir modul
# B + 4 saati yeniden hesaplamaz.


def donem_kapanisi(donem_bitis) -> pd.Timestamp:
    """K = B + 4 saat (on-kayit §2 rev.8 "Listeleme donemi")."""
    return utc_zamani(donem_bitis, "donem_bitis") + ADIMLAR[config.BAR_4H]


def donem_ici_mi(t, bar: str, *, donem_baslangic, donem_bitis) -> bool:
    """TEK donem uyeligi yuklemi (on-kayit §6 rev.8 "Donem uyeligi").

    "Bir bar, onu olusturan butun 4h barlar ayni donemin icindeyse donem icidir:
    4h barda acilis [donem basi, B] araligindadir; 1d barda §2 '1 gunluk
    barlar'daki alti barin tamami donem icidir." 1d barin `t`si UTC gun
    acilisidir; alti bar t, t+4h, ..., t+20h'dir. Yalnizca zamana bakar; barlarin
    mevcut olup olmadigini soylemez (o `klines.gunluge_cevir`in isidir).
    `eligibility.uygun_mu`, `pozisyon_plani` ve K1/K2 kodu bu yuklemi kullanir.
    """
    zaman = utc_zamani(t, "t")
    bas = utc_zamani(donem_baslangic, "donem_baslangic")
    bitis = utc_zamani(donem_bitis, "donem_bitis")
    if bar == config.BAR_4H:
        return bool(donem_ici_4h_maskesi(zaman, donem_baslangic=bas, donem_bitis=bitis))
    if bar == config.BAR_1D:
        if zaman != zaman.floor("D"):
            raise ValueError(f"1d bar zamani gun acilisi olmali: {zaman}")
        return bool(donem_ici_4h_maskesi(zaman, donem_baslangic=bas, donem_bitis=bitis)
                    and donem_ici_4h_maskesi(zaman + GUNUN_SON_4H_BARI, donem_baslangic=bas, donem_bitis=bitis))
    raise ValueError(f"Bilinmeyen bar: {bar!r}")


def donem_ici_4h_maskesi(zamanlar, *, donem_baslangic, donem_bitis):
    """4h bar acilis(lar)i [donem basi, B] icinde mi (zaman toleransiyla). `donem_ici_mi`nin
    4h dali ve 1d serisinin kurulmasi (`klines.gunluge_cevir`) bu tek ifadeyi kullanir."""
    return _sonuc(np.asarray(ayni_ya_da_sonra(zamanlar, donem_baslangic), dtype=bool)
                  & np.asarray(ayni_ya_da_once(zamanlar, donem_bitis), dtype=bool))


# 1d barin son 4h barinin acilisi gun acilisindan 20 saat sonradir (on-kayit §2 rev.8).
GUNUN_SON_4H_BARI = pd.Timedelta(hours=20)


def _sonuc(deger):
    """Skaler karsilastirmada bool, dizide numpy bool dizisi."""
    if np.ndim(deger) == 0:
        return bool(deger)
    return np.asarray(deger, dtype=bool)


def ayni_an(a, b):
    """a ile b ayni an mi: `|a - b| < 1 dk` (kesin kucuk)."""
    return _sonuc(abs(a - b) < ZAMAN_TOLERANSI)


def sonra(a, b):
    """a, b'den SONRA mi (ayni an degil): `a - b >= 1 dk`."""
    return _sonuc((a - b) >= ZAMAN_TOLERANSI)


def once(a, b):
    """a, b'den ONCE mi (ayni an degil): `b - a >= 1 dk`."""
    return _sonuc((b - a) >= ZAMAN_TOLERANSI)


def ayni_ya_da_once(a, b):
    """a, b ile ayni an ya da ondan once mi (`not sonra(a, b)`)."""
    return _sonuc((a - b) < ZAMAN_TOLERANSI)


def ayni_ya_da_sonra(a, b):
    """a, b ile ayni an ya da ondan sonra mi (`not once(a, b)`)."""
    return _sonuc((b - a) < ZAMAN_TOLERANSI)


def ayni_an_sonu(x):
    """x ile ayni sayilan anlarin ust kenari (HARIC): `an < ayni_an_sonu(x)` <=>
    `ayni_ya_da_once(an, x)`; `an >= ayni_an_sonu(x)` <=> `sonra(an, x)`.
    Siralanmis dizilerde `searchsorted` icin tek kenar tanimi."""
    return x + ZAMAN_TOLERANSI


def ayni_an_basi(x):
    """x ile ayni sayilan anlarin alt kenari (HARIC): `an > ayni_an_basi(x)` <=>
    `ayni_ya_da_sonra(an, x)`; `an <= ayni_an_basi(x)` <=> `once(an, x)`."""
    return x - ZAMAN_TOLERANSI


def adim(bar: str) -> pd.Timedelta:
    """Bar tipinin zaman izgarasi adimi."""
    try:
        return ADIMLAR[bar]
    except KeyError:
        raise ValueError(f"Bilinmeyen bar: {bar!r}") from None


CIKIS_TURLERI = ("olagan", "ileri_kayma", "donem_sonu")


@dataclass(frozen=True)
class CikisSonucu:
    """Pozisyonun cikisi (on-kayit §4 rev.8 "Fiyat okuma tabani", "Donem sonu ve
    cikis", §2 "Ufuk"). Getiri HESAPLANMAZ; hangi donem ici 4h bardan, hangi
    fiyat alanindan ve hangi anda cikildigi soylenir. Her izgarada fiyat 4h
    barlardan okunur.

    - `tur = "olagan"`: hedef bar (kapanisi T) mevcut; `close`, cikis ani T.
    - `tur = "ileri_kayma"`: hedef bar eksik; acilisi T'ye esit ya da sonra olan
      ilk donem ici 4h barin `open`i, cikis ani o barin acilisi.
    - `tur = "donem_sonu"`: T >= K (rev.9); B'de acilan barin `close`u, cikis ani K.
    """

    indeks: int  # fiyatin okundugu 4h barin verilen seri icindeki sirasi
    zaman: pd.Timestamp  # fiyatin okundugu donem ici 4h barin acilisi
    fiyat_alani: str  # "close" (olagan, donem sonu) ya da "open" (ileri kayma)
    cikis_ani: pd.Timestamp  # gercek cikis ani: T, sonraki barin acilisi ya da K
    tur: str  # CIKIS_TURLERI
    hedef_cikis_ani: pd.Timestamp  # T = giris ani + h x adim
    ileri_kayma: pd.Timedelta  # ileri kaymada (bar acilisi - (T - 4h)); aksi halde 0

    @property
    def kaydi(self) -> bool:
        return self.tur == "ileri_kayma"

    @property
    def kirpildi(self) -> bool:
        return self.tur == "donem_sonu"

    @property
    def kirpma_nedeni(self) -> str | None:
        return "donem_sonu" if self.tur == "donem_sonu" else None


class OlayOlusmaz(ValueError):
    """Kural geregi olay (ya da kontrol) OLUSMAZ; programlama hatasi ya da veri
    bozuklugu degildir. Tek kapi `pozisyon_plani` bu sinifin alt siniflarini
    firlatir; olay dusme nedenleri raporu nedeni `gerekce` ozelliginden okur
    (on-kayit §4 rev.8: reddedilen her olay bir ret gerekcesi tasir)."""

    gerekce = "olay_olusmaz"


class KumeSiniriHatasi(OlayOlusmaz):
    """Olayin ufku ait oldugu kumenin tarih araligina sigmiyor (on-kayit §3 rev.4, §4 rev.7).

    Kume sinirinda kirpilmis cikis kullanilmaz ve komsu kumeden veri okunmaz;
    olay o kumede hic olusmaz. Kume sinirlari `split.kume_araligi` uzerinden gelir.
    """

    gerekce = "kume_siniri"


class IleriKaymaSiniriHatasi(OlayOlusmaz):
    """Hedef cikis bari eksik ve sonraki mevcut bar ileri kayma sinirindan uzak
    (on-kayit §4 rev.6).

    Ileri kayma, olayin birincil ufku kadar sureyle sinirlidir (H1, H2: 18 bar;
    H3: 14 gun). Daha uzaktaki bardan cikilmaz ve kirpilmis getiri kullanilmaz;
    olay olusmaz.
    """

    gerekce = "ileri_kayma_siniri"


class DonemDisiSinyal(ValueError):
    """Sinyal bari donem ici degil (on-kayit §6 rev.8 "Donem uyeligi").

    Programlama hatasidir, `OlayOlusmaz` degildir: uygunluk (`eligibility.uygun_mu`)
    ayni yuklemle donem disi bari zaten reddeder; buraya gelen bir sinyal cagiran
    kodun uygunluk filtresini atladigini gosterir."""


class GirisBariYok(OlayOlusmaz):
    """Acilisi giris anina esit donem ici 4h bar yok (on-kayit §4 rev.8 "Fiyat okuma
    tabani"; §2 rev.3 "Giris": olay olusmaz)."""

    gerekce = "giris_bari_yok"


class ZamanDizisiHatasi(ValueError):
    """Zaman damgalari sirasiz ya da tekrarli: bu bir VERI BOZUKLUGUDUR.

    On-kayit §2 rev.3'un "deger hesaplanmaz (NaN)" kurali EKSIK bar icindir;
    sirasiz ya da tekrarli damga eksik veri degil bozuk veridir ve sessizce
    NaN'a cevrilmez, hata olarak yuzeye cikar.
    """


def _zaman_dizisi_dogrula(zamanlar, yer: str) -> pd.DatetimeIndex:
    """Zaman dizisinin kesin artan ve tekrarsiz oldugunu dogrular.

    Gecilen DatetimeIndex nesnesinin kendisi kullanilir; pandas monotonluk ve
    tekrar kontrollerini nesne uzerinde onbellege aldigi icin ayni seri ile
    tekrarlanan cagrilar her seferinde tum diziyi taramaz.
    """
    indeks = zamanlar if isinstance(zamanlar, pd.DatetimeIndex) else pd.DatetimeIndex(zamanlar)
    if len(indeks) and indeks.tz is None:
        raise ZamanDizisiHatasi(
            f"{yer}: zaman dizisi saat dilimsiz (tz-naive). Tum zaman damgalari UTC olmali "
            "(CLAUDE.md §5); saat dilimsiz dizi UTC'li bir anla karsilastirilinca her "
            "pencere sessizce NaN olurdu."
        )
    if indeks.has_duplicates:
        tekrarlar = [str(z) for z in indeks[indeks.duplicated()].unique()[:3]]
        raise ZamanDizisiHatasi(
            f"{yer}: zaman dizisinde tekrarlanan damga var (ornek: {', '.join(tekrarlar)}). "
            "Bu bir veri bozuklugudur, eksik bar degildir; deger NaN'a cevrilmez."
        )
    if not indeks.is_monotonic_increasing:
        raise ZamanDizisiHatasi(
            f"{yer}: zaman dizisi artan sirada degil. Bu bir veri bozuklugudur; "
            "girdi zamana gore siralanmadan pencere ya da cikis hesaplanmaz."
        )
    return indeks


# --- Sinir parametreleri -----------------------------------------------------


def utc_zamani(deger, ad: str) -> pd.Timestamp:
    """Bir ani saat dilimli zaman damgasina cevirir; saat dilimsizse TypeError.

    F1 kapanis bulgusu 15: saat dilimsiz bir t, UTC'li bir seriyle
    karsilastirilinca hicbir bar eslesmez ve her pencere sessizce NaN, her giris
    sessizce None olur -- calisma "negatif sonuc" gibi gorunur. Tum zaman
    damgalari UTC'dir (CLAUDE.md §5); saat dilimsiz deger bir programlama
    hatasidir ve acikca reddedilir.
    """
    zaman = pd.Timestamp(deger)
    if zaman.tzinfo is None:
        raise TypeError(
            f"{ad} saat dilimsiz (tz-naive): {deger!r}. Tum zaman damgalari UTC olmali "
            "(CLAUDE.md §5); ör. pd.Timestamp('2025-09-01', tz='UTC')."
        )
    return zaman


def sinir_zamani(deger, ad: str) -> pd.Timestamp | None:
    """Bir donem ya da kume siniri: zaman damgasi ya da bilincli `None`.

    Parametrenin kendisi zorunludur (varsayilan yoktur); `None` yalnizca o sinirin
    gercekten olmadigini soyler (ör. tum gecmisi olcen F1 veri denetimi kume
    disidir). `True`/`False` gibi bool degerler reddedilir.
    """
    if deger is None:
        return None
    if isinstance(deger, bool):
        raise TypeError(f"{ad} bir zaman damgasi ya da acikca None olmali. Verilen: {deger!r}")
    return utc_zamani(deger, ad)


def donem_siniri(deger, ad: str) -> pd.Timestamp:
    """Bir donem siniri: zaman damgasi olmali, `None` OLAMAZ (denetci bulgusu D-C6; on-kayit §2
    "Tum geriye bakis pencereleri donem baslangicini asamaz"). Kume sinirinin aksine donem
    siniri her zaman vardir: sembolun her bari bir listeleme donemine aittir."""
    if deger is None:
        raise TypeError(f"{ad} None olamaz: donem siniri her hesapta verilir (on-kayit §2 'Listeleme donemi').")
    return sinir_zamani(deger, ad)


def _t_dahil_dogrula(t_dahil) -> bool:
    """On-kayit §5 rev.4: pencerenin t barini icerip icermedigi acikca verilir.

    Varsayilan davranis yoktur. Anahtar sozcuk zorunlu oldugu icin unutulursa
    Python zaten TypeError verir; bu kontrol `None` gibi bool olmayan degerleri
    de reddeder.
    """
    if not isinstance(t_dahil, bool):
        raise TypeError(
            "t_dahil acikca True ya da False verilmeli (on-kayit §5 rev.4: pencere "
            f"sinirlari acikca belirtilir, varsayilan yoktur). Verilen: {t_dahil!r}"
        )
    return t_dahil


# --- Tamlik ------------------------------------------------------------------


def beklenen_zamanlar(t, bar_sayisi: int, bar: str, *, t_dahil: bool) -> pd.DatetimeIndex:
    """t'ye gore geriye dogru `bar_sayisi` adetlik beklenen izgara.

    Pencere zamanla tanimlidir (on-kayit §2 rev.3) ve t barini icerip icermedigi
    cagiran tarafindan acikca belirtilir (on-kayit §5 rev.4):
      - t_dahil=True : [t - (N-1) x adim, t]    ör. H2'nin 30 barlik yukselisi,
                                               H1'in 180 barlik hacim penceresi
      - t_dahil=False: [t - N x adim, t - adim] ör. H1'in 6 barlik dip penceresi
                                               (t-6..t-1), H2'nin k barlik
                                               kirilim penceresi (t-k..t-1)
    """
    _t_dahil_dogrula(t_dahil)
    if bar_sayisi < 1:
        raise ValueError("bar_sayisi en az 1 olmali.")
    zaman = utc_zamani(t, "t")
    son = zaman if t_dahil else zaman - adim(bar)
    return pd.date_range(end=son, periods=bar_sayisi, freq=adim(bar))


def _pencere_tam_mi(beklenen: pd.DatetimeIndex, mevcut: pd.DatetimeIndex) -> bool:
    """Penceredeki beklenen barlarin TAMAMI mevcut mu? (on-kayit §2 rev.3)

    Tek bir bar eksikse False doner.

    Neden modul ici (on-kayit §3 rev.5): bu kontrol YALNIZCA tamligi olcer;
    donem ve kume sinirlarini bilmez. Eskiden herkese acik
    `pencere_tam_mi` olarak duruyordu ve F2'de tek basina kapi olarak
    kullanilsaydi, kume oncesi veriyi iceren tam bir pencereye "gecerli"
    derdi -- yani kume kuralini sessizce atlardi. Sinirlari zorunlu parametre
    olarak eklemek `pencere_dilimi`nin ikinci bir kopyasini yaratirdi ve iki
    kopya zamanla birbirinden ayrisabilirdi (B4'teki `donem.pencere_gecerli_mi`
    ornegi). Bu yuzden tek kapi `pencere_dilimi` / `pencere_degeri`dir; bu
    fonksiyon yalnizca onun, donem/kume kontrolleri GECILDIKTEN
    SONRA cagirdigi ic adimdir. Modul disindan cagrilmaz.
    """
    return bool(beklenen.isin(mevcut).all())


def pencere_dilimi(
    seri: pd.Series,
    t,
    bar_sayisi: int,
    bar: str,
    *,
    t_dahil: bool,
    kume_baslangic,
    donem_baslangic,
) -> pd.Series | None:
    """Zamanla tanimli pencereyi doner; kurallardan biri saglanmazsa None.

    Sirasiyla su kosullar aranir:
      1. Pencere donem baslangicini asmamali (on-kayit §2 rev.7),
      2. Pencere kume baslangicini asmamali (on-kayit §3 rev.5),
      3. Penceredeki beklenen barlarin tamami mevcut olmali (rev.3 tamlik sarti).

    Kume siniri, seride kume oncesi veri BULUNSA BILE uygulanir: kural verinin
    kume sinirinda kesilmis olmasina dayanmaz. `kume_baslangic` ve
    `donem_baslangic` zorunludur; kume siniri yoksa acikca None, donem siniri None OLAMAZ
    (`donem_siniri`; denetci bulgusu D-C6).
    """
    kume_bas = sinir_zamani(kume_baslangic, "kume_baslangic")
    donem_bas = donem_siniri(donem_baslangic, "donem_baslangic")
    beklenen = beklenen_zamanlar(t, bar_sayisi, bar, t_dahil=t_dahil)

    # Iki sinir da ayni yardimciyla, zaman toleransiyla (on-kayit §4 rev.8 "Zaman toleransi"): sinirla
    # ayni an olan pencere basi siniri asmis sayilmaz (Rev.10 uygulamasi madde 2; sizinti bulgusu).
    if once(beklenen[0], donem_bas):
        return None

    if kume_bas is not None and once(beklenen[0], kume_bas):
        return None  # pencere kume oncesi veriyi odunc alamaz (rev.5)

    indeks = _zaman_dizisi_dogrula(seri.index, "pencere_dilimi")
    if not _pencere_tam_mi(beklenen, indeks):
        return None  # tamlik sarti saglanmadi

    return seri.reindex(beklenen)


def pencere_degeri(
    seri: pd.Series,
    t,
    bar_sayisi: int,
    bar: str,
    *,
    t_dahil: bool,
    kume_baslangic,
    donem_baslangic,
    islev="median",
) -> float:
    """Zamanla tanimli pencereye bir toplayici uygular; kural ihlalinde NaN.

    `islev` bir Series metodu adi ("median", "mean", "min", "max", "sum") ya da
    Series alan bir cagrilabilirdir. `t_dahil` (on-kayit §5 rev.4) ile
    `kume_baslangic` ve `donem_baslangic` zorunludur.
    """
    dilim = pencere_dilimi(
        seri,
        t,
        bar_sayisi,
        bar,
        t_dahil=t_dahil,
        kume_baslangic=kume_baslangic,
        donem_baslangic=donem_baslangic,
    )
    if dilim is None or dilim.isna().any():
        return float("nan")
    if callable(islev):
        return float(islev(dilim))
    return float(getattr(dilim, islev)())


# --- Ic ice ve ofsetli pencereler (F1 kapanis bulgusu 3) ----------------------
#
# Turetilmis bir seriyi (ör. `seri.rolling(6).sum()`) `pencere_degeri`ne vermek
# kapiyi atlatir: kapi yalnizca DIS pencerenin damgalarini denetler; ilk ic
# pencere kume/donem basindan onceki barlari icerebilir ve rolling bar sayisiyla
# calistigi icin bosluk uzerinden toplar. Asagidaki iki fonksiyon turetilmis
# serinin kendisini de ayni kapidan gecirir. Analiz kodu (events/, study/)
# bar sayisiyla calisan turetilmis seri islemleri kullanmaz; bir kaynak tarama
# testi bunu dogrular.


def _islev_uygula(dilim: pd.Series, islev) -> float:
    if callable(islev):
        return float(islev(dilim))
    return float(getattr(dilim, islev)())


def ic_ice_pencere_degeri(
    seri: pd.Series,
    t,
    bar: str,
    *,
    dis_bar_sayisi: int,
    dis_t_dahil: bool,
    dis_islev,
    ic_bar_sayisi: int,
    ic_t_dahil: bool,
    ic_islev,
    kume_baslangic,
    donem_baslangic,
) -> float:
    """Ic pencere degerlerinin dis penceredeki toplayicisi; kural ihlalinde NaN.

    Tanim (zamanla):
      - Dis izgara: `beklenen_zamanlar(t, dis_bar_sayisi, t_dahil=dis_t_dahil)`.
      - Her dis bar s icin ic deger: `ic_islev` uygulanmis
        `beklenen_zamanlar(s, ic_bar_sayisi, t_dahil=ic_t_dahil)` penceresi.
      - Sonuc: ic degerlere `dis_islev`.
    Ornek, H1'in hacim kosulu: dis 180 bar (t dahil) x ic 6 barlik toplam, medyan.

    Tum ic pencerelerin birlesimi tek bir kesintisiz araliktir; o aralik
    `pencere_dilimi`nden gecer. Boylece HER ic pencere tamlik, donem ve kume
    kontrolunden gecmis olur; biri bile gecemezse sonuc NaN.
    Bu aralik tam oldugu icin icerdeki bar sayisiyla hesap zamanla hesapla aynidir.
    Tum parametreler zorunludur; varsayilan yoktur.
    """
    _t_dahil_dogrula(dis_t_dahil)
    _t_dahil_dogrula(ic_t_dahil)
    if dis_bar_sayisi < 1 or ic_bar_sayisi < 1:
        raise ValueError("dis_bar_sayisi ve ic_bar_sayisi en az 1 olmali.")

    dis = beklenen_zamanlar(t, dis_bar_sayisi, bar, t_dahil=dis_t_dahil)
    kapsam_sonu = dis[-1] if ic_t_dahil else dis[-1] - adim(bar)
    kapsam_uzunlugu = dis_bar_sayisi + ic_bar_sayisi - 1

    dilim = pencere_dilimi(
        seri,
        kapsam_sonu,
        kapsam_uzunlugu,
        bar,
        t_dahil=True,
        kume_baslangic=kume_baslangic,
        donem_baslangic=donem_baslangic,
    )
    if dilim is None or dilim.isna().any():
        return float("nan")

    degerler = np.array(
        [_islev_uygula(dilim.iloc[i : i + ic_bar_sayisi], ic_islev) for i in range(dis_bar_sayisi)]
    )
    return _islev_uygula(pd.Series(degerler, index=dis), dis_islev)


def ofsetli_pencere_degeri(
    seri: pd.Series,
    t,
    bar_sayisi: int,
    bar: str,
    *,
    bitis_ofseti: int,
    islev,
    kume_baslangic,
    donem_baslangic,
) -> float:
    """t'den `bitis_ofseti` bar once biten `bar_sayisi` barlik pencere; ihlalde NaN.

    Pencere: `[t - (bitis_ofseti + bar_sayisi - 1) x adim, t - bitis_ofseti x adim]`.
    Ornek, H3'un "gun -120 ile -31": `bar_sayisi=90, bitis_ofseti=31`.
    `bitis_ofseti=0` t dahil, `1` t haric pencereyle aynidir. Negatif ofset
    gelecege bakis olurdu ve reddedilir. Pencere `pencere_dilimi`nden gecer.
    Tum parametreler zorunludur; varsayilan yoktur.
    """
    if isinstance(bitis_ofseti, bool) or not isinstance(bitis_ofseti, (int, np.integer)):
        raise TypeError(f"bitis_ofseti tamsayi olmali: {bitis_ofseti!r}")
    if bitis_ofseti < 0:
        raise ValueError(f"bitis_ofseti negatif olamaz (gelecege bakis): {bitis_ofseti}")
    son = utc_zamani(t, "t") - int(bitis_ofseti) * adim(bar)
    return pencere_degeri(
        seri,
        son,
        bar_sayisi,
        bar,
        t_dahil=True,
        islev=islev,
        kume_baslangic=kume_baslangic,
        donem_baslangic=donem_baslangic,
    )


# --- Giris ve cikis (on-kayit §4 rev.8) -------------------------------------------
#
# "Olay, sinyalin hesaplandigi izgarada tespit edilir (H1, H2: 4h; H3: 1d).
# Pozisyonun butun fiyat okumalari ise her hipotezde donem ici 4h barlardan
# yapilir." `zamanlar` her izgarada 4h barlarin acilis zamanlaridir.

ADIM_4H = ADIMLAR[config.BAR_4H]


def giris_ani(sinyal_zamani, bar: str) -> pd.Timestamp:
    """Giris ani = t barinin kapanis ani = t + adim (on-kayit §4 rev.8)."""
    return utc_zamani(sinyal_zamani, "sinyal_zamani") + adim(bar)


def giris_bari(zamanlar, sinyal_zamani, bar: str) -> pd.Timestamp | None:
    """P0'in okundugu 4h bar: acilisi giris anina esit olan bar; yoksa None
    (on-kayit §4 rev.8 "Fiyat okuma tabani": olay olusmaz). Donem uyeligini
    `pozisyon_plani` denetler."""
    return ayni_andaki_bar(pd.DatetimeIndex(zamanlar), giris_ani(sinyal_zamani, bar))


def ayni_andaki_bar(zamanlar: pd.DatetimeIndex, an) -> pd.Timestamp | None:
    """Acilisi `an` ile ayni an (on-kayit §4 rev.8 "Zaman toleransi") olan bar; yoksa
    None. Barlar 4 saat arayla oldugu icin en fazla bir bar eslesir. Sirali dizide
    `ayni_an_basi` / `ayni_an_sonu` kenarlariyla aranir."""
    ilk = int(zamanlar.searchsorted(ayni_an_basi(an), side="right"))
    if ilk < len(zamanlar) and zamanlar[ilk] < ayni_an_sonu(an):
        return zamanlar[ilk]
    return None


def _ufuk_tamsayisi(deger, ad: str) -> int:
    if isinstance(deger, bool) or not isinstance(deger, (int, np.integer)):
        raise TypeError(f"{ad} tamsayi bar sayisi olmali: {deger!r}")
    return int(deger)


def ufuk_dogrula(ufuk, bar: str) -> int:
    """Ufuk on-kayit degerlerinden biri mi (on-kayit §4 "Ufuk degerlerinin baglanmasi", rev.10)?
    Izgaranin birincil ya da ikincil ufku (`config.UFUKLAR`) degilse ValueError; tamsayi degilse
    TypeError. Getiri, olay ya da kontrol ureten her cagri bundan gecer."""
    deger = _ufuk_tamsayisi(ufuk, "ufuk")
    adim(bar)
    if deger not in config.UFUKLAR[bar]:
        raise ValueError(f"ufuk {deger} ({bar}) on-kayit degeri degil; gecerli: {config.UFUKLAR[bar]} "
                         "(on-kayit §4 'Ufuk degerlerinin baglanmasi').")
    return deger


def birincil_ufuk_dogrula(birincil_ufuk, bar: str) -> int:
    """Birincil ufuk izgaranin on-kayit degeri mi (`config.BIRINCIL_UFUK`; on-kayit §4 rev.10)?"""
    deger = _ufuk_tamsayisi(birincil_ufuk, "birincil_ufuk")
    adim(bar)
    if deger != config.BIRINCIL_UFUK[bar]:
        raise ValueError(f"birincil_ufuk {deger} ({bar}) on-kayit degeri degil; on-kayit degeri "
                         f"{config.BIRINCIL_UFUK[bar]} (on-kayit §4 'Ufuk degerlerinin baglanmasi').")
    return deger


@dataclass(frozen=True)
class HipotezUfuklari:
    """Bir hipotezin izgarasi ve ufuklari; hepsi `config`'in on-kayit bolumunden turer (on-kayit §4
    "Ufuk degerlerinin baglanmasi", rev.10; F1 kapanis turu, denetci D-B2). Yalnizca `hipotez_ufuklari`
    uretir."""

    hipotez: str
    bar: str
    birincil: int
    ikincil: tuple[int, ...]
    ileri_kayma_siniri: int
    ufuklar: tuple[int, ...]


def hipotez_izgarasi(hipotez) -> str:
    """Hipotezin izgarasi (`config.HIPOTEZ_IZGARASI`: H1, H2 4h; H3 1d). Bilinmeyen hipotez ValueError,
    metin olmayan TypeError."""
    if not isinstance(hipotez, str):
        raise TypeError(f"hipotez 'H1', 'H2' ya da 'H3' olmali: {hipotez!r}")
    if hipotez not in config.HIPOTEZ_IZGARASI:
        raise ValueError(f"Bilinmeyen hipotez {hipotez!r}; on-kayit hipotezleri: {tuple(config.HIPOTEZ_IZGARASI)}.")
    return config.HIPOTEZ_IZGARASI[hipotez]


def hipotez_ufuklari(hipotez) -> HipotezUfuklari:
    """Hipotez -> izgara -> ufuklar, tek kaynaktan (`config`). F2 kodu ufuk ve izgarayi buradan okur."""
    bar = hipotez_izgarasi(hipotez)
    return HipotezUfuklari(hipotez, bar, config.BIRINCIL_UFUK[bar], tuple(config.IKINCIL_UFUKLAR[bar]),
                           config.ILERI_KAYMA_SINIRI[bar], tuple(config.UFUKLAR[bar]))


def hipotez_baglamini_dogrula(hipotez, bar: str, ufuk, birincil_ufuk) -> HipotezUfuklari:
    """Verilen izgara, ufuk ve birincil ufuk hipotezden tureyen degerlerle uyumlu mu? Uyumsuzluk
    calisma aninda ValueError (ör. H3 icin `bar="4h"`, H2 icin `ufuk=14`). Tek kapi
    `pozisyon.olay_karari` her cagrida bunu uygular."""
    tanim = hipotez_ufuklari(hipotez)
    if bar != tanim.bar:
        raise ValueError(f"{hipotez} izgarasi {tanim.bar}; verilen bar {bar!r} on-kayit hipotez-izgara bagiyla "
                         "uyumsuz (config.HIPOTEZ_IZGARASI).")
    ufuk_dogrula(ufuk, tanim.bar)
    birincil_ufuk_dogrula(birincil_ufuk, tanim.bar)
    return tanim


def cikis_hedefi(giris_zamani, ufuk: int, bar: str) -> pd.Timestamp:
    """Hedef cikis ani T = giris ani + h x adim (on-kayit §4 rev.8); adim 4h
    izgarasinda 4 saat, 1d izgarasinda 24 saat. Hedef bar, kapanisi T olan 4h bardir.

    Ic adim: ufkun on-kayit degeri oldugunu tek kapi `pozisyon.olay_karari` denetler
    (`ufuk_dogrula`; on-kayit §4 rev.10). Analiz kodu ic adimlari cagirmaz (kaynak taramasi)."""
    if isinstance(ufuk, bool) or not isinstance(ufuk, (int, np.integer)) or ufuk < 1:
        raise ValueError(f"ufuk en az 1 bar olan bir tamsayi olmali: {ufuk!r}")
    return utc_zamani(giris_zamani, "giris_zamani") + int(ufuk) * adim(bar)


def _cikis_odemesi_kume_disinda(an: pd.Timestamp, kume_son: pd.Timestamp | None) -> bool:
    """On-kayit §4 rev.8 "Olayin kumede olusma olcutu"nun TEK uygulamasi.

    "Cikis ani ile funding tolerans payi birlikte kume sonunu asmamalidir. Cikis
    ani, izgaranin adimindan turetilmez; ... olagan cikista T, ileri kaymada
    sonraki barin acilisi, donem sonunda K." Cikis aniyla ayni sayilan son an
    `ayni_an_sonu(an) - 1 ns`dir (§4 "Zaman toleransi"); o an kume sonunu
    asiyorsa olay kumede olusmaz. Karar ZAMANLA verilir.
    """
    return kume_son is not None and ayni_an_sonu(an) - pd.Timedelta(1, "ns") > kume_son


def cikis_ani(cikis: CikisSonucu) -> pd.Timestamp:
    """Pozisyonun gercek cikis ani (on-kayit §4 rev.8); tutarlilik dogrulanir."""
    cikis_tutarliligi_dogrula(cikis)
    return cikis.cikis_ani


def cikis_tutarliligi_dogrula(cikis: CikisSonucu) -> None:
    """Elle kurulmus bir CikisSonucu'nun `cikis_bari`nin uretebilecegi bicimde
    oldugunu dogrular (F1 kapanis denetimi bulgu 5); degilse ValueError.

      - olagan     : close, cikis ani = bar acilisi + 4h = T, kayma 0
      - ileri_kayma: open,  cikis ani = bar acilisi, kayma = acilis - (T - 4h) > 0
      - donem_sonu : close, cikis ani = bar acilisi + 4h = K, T >= K (rev.9), kayma 0
    """
    if not isinstance(cikis, CikisSonucu):
        raise TypeError(f"cikis bir CikisSonucu olmali (cikis_bari ciktisi). Verilen: {cikis!r}")
    zaman = utc_zamani(cikis.zaman, "cikis.zaman")
    an = utc_zamani(cikis.cikis_ani, "cikis.cikis_ani")
    hedef = utc_zamani(cikis.hedef_cikis_ani, "cikis.hedef_cikis_ani")
    if cikis.tur not in CIKIS_TURLERI:
        raise ValueError(f"Bilinmeyen cikis turu: {cikis.tur!r}")
    beklenen_alan = "open" if cikis.tur == "ileri_kayma" else "close"
    if cikis.fiyat_alani != beklenen_alan:
        raise ValueError(f"Tutarsiz cikis: tur={cikis.tur!r} ama fiyat_alani={cikis.fiyat_alani!r}")
    if not isinstance(cikis.ileri_kayma, pd.Timedelta):
        raise ValueError(f"ileri_kayma bir Timedelta olmali: {cikis.ileri_kayma!r}")
    if cikis.tur == "ileri_kayma":
        if an != zaman or cikis.ileri_kayma <= pd.Timedelta(0) or cikis.ileri_kayma != zaman - (hedef - ADIM_4H):
            raise ValueError(f"Tutarsiz ileri kaymali cikis: {cikis!r}")
    else:
        if an != zaman + ADIM_4H or cikis.ileri_kayma != pd.Timedelta(0):
            raise ValueError(f"Tutarsiz cikis ani: {cikis!r}")
        if cikis.tur == "olagan" and not ayni_an(hedef, an):
            raise ValueError(f"Olagan cikista cikis ani T olmali: {cikis!r}")
        if cikis.tur == "donem_sonu" and not ayni_ya_da_sonra(hedef, an):
            raise ValueError(f"Donem sonu cikisinda T >= K olmali (on-kayit §4 rev.9): {cikis!r}")


def cikis_bari(
    zamanlar,
    giris_zamani,
    ufuk: int,
    bar: str,
    *,
    birincil_ufuk: int,
    donem_bitis,
    kume_bitis,
) -> CikisSonucu:
    """Cikis (on-kayit §4 rev.8 "Fiyat okuma tabani", rev.9 "Donem sonu ve cikis",
    "Ileri kaymanin ust siniri"; §2 "Ufuk", "Ileri kaymanin olcusu").

    `zamanlar`: donem ici 4h bar acilislari (her izgarada). `giris_zamani`:
    giris ani (t barinin kapanisi; P0 barinin acilisi). Sirasiyla:

      1. `T = giris + h x adim`, `K = B + 4 saat`. T >= K ise (kapanis anlariyla,
         zaman toleransiyla; rev.9 esitligi dahil etti) donem sonu: B'de acilan barin
         kapanisi, cikis ani K. "Donem sonu ve delist kurallari ileri kayma kuralindan
         onceliklidir: once T >= K denetlenir; ileri kayma kurali yalnizca T < K ise
         uygulanir."
      2. T < K: kapanisi T olan 4h bar (acilisi T - 4h) mevcutsa olagan cikis,
         cikis ani T.
      3. Hedef bar eksik: acilisi T'ye esit ya da sonra olan ilk donem ici 4h bar
         (B'den sonra olamaz); cikis ani o barin acilisi. Ileri kayma = bu
         acilis - hedef barin acilisi (T - 4h); birincil ufuk x adimi ASARSA
         (sinir dahil) `IleriKaymaSiniriHatasi`.

    `donem_bitis` (B) zorunludur ve None olamaz (donem sonu kurali). Verilen
    seride gereken bar yoksa ve seri kume sonunda kesilmisse `KumeSiniriHatasi`
    (cikis kume disinda kalir). Kume olcutu (`_cikis_odemesi_kume_disinda`)
    tek kapi `pozisyon_plani`nda gercek cikis anina uygulanir. Getiri HESAPLAMAZ.
    """
    if isinstance(birincil_ufuk, bool) or not isinstance(birincil_ufuk, (int, np.integer)):
        raise TypeError(f"birincil_ufuk tamsayi bar sayisi olmali: {birincil_ufuk!r}")
    if birincil_ufuk < 1:
        raise ValueError(f"birincil_ufuk en az 1 bar olmali: {birincil_ufuk}")
    indeks = _zaman_dizisi_dogrula(zamanlar, "cikis_bari")
    if len(indeks) == 0:
        raise ValueError("Bar listesi bos.")
    giris = utc_zamani(giris_zamani, "giris_zamani")
    if ayni_andaki_bar(indeks, giris) is None:
        raise KeyError(f"Giris bari seride yok: {giris}")
    b = sinir_zamani(donem_bitis, "donem_bitis")
    if b is None:
        raise TypeError("cikis_bari: donem_bitis (B) None olamaz; donem sonu kurali B'ye dayanir (on-kayit §4 rev.8).")
    kume_son = sinir_zamani(kume_bitis, "kume_bitis")
    k = donem_kapanisi(b)
    hedef = cikis_hedefi(giris, ufuk, bar)

    def _sira(z: pd.Timestamp) -> int:
        return int(indeks.get_loc(z))

    def _seride_yok(neden: str):
        if kume_son is not None and b > kume_son:
            raise KumeSiniriHatasi(
                f"{neden}; seri kume sonunda ({kume_son}) kesilmis ve donem kumeden sonra suruyor "
                "(on-kayit §4 rev.8: cikis kume disinda, olay olusmaz).")
        raise ValueError(f"{neden}; donem ici bar seride olmali (bozuk ya da eksik seri).")

    def _kume_icinde(sonuc: CikisSonucu) -> CikisSonucu:
        # Kume olcutu gercek cikis anina (tek uygulama `_cikis_odemesi_kume_disinda`);
        # `pozisyon_plani` ayni fonksiyonu bir kez daha uygular.
        if _cikis_odemesi_kume_disinda(sonuc.cikis_ani, kume_son):
            raise KumeSiniriHatasi(
                f"Cikis ani {sonuc.cikis_ani} ({sonuc.tur}) ve cikis anindaki odeme kume sonunu "
                f"({kume_son}) asiyor (on-kayit §4 rev.8: olay bu kumede olusmaz).")
        return sonuc

    # 1. Donem sonu (T >= K, kapanis anlariyla; on-kayit §4 rev.9). T ile K ayni an
    # sayiliyorsa (fark 1 dk'dan kesin kucuk) T >= K'dir; T < K yalnizca once(T, K).
    if ayni_ya_da_sonra(hedef, k):
        b_bari = ayni_andaki_bar(indeks, b)
        if b_bari is None:
            _seride_yok(f"Donem bitis bari {b} seride yok")
        return _kume_icinde(
            CikisSonucu(_sira(b_bari), b_bari, "close", b_bari + ADIM_4H, "donem_sonu", hedef, pd.Timedelta(0)))

    # 2. Olagan cikis: kapanisi T olan bar.
    hedef_acilis = hedef - ADIM_4H
    hedef_bari = ayni_andaki_bar(indeks, hedef_acilis)
    if hedef_bari is not None:
        return _kume_icinde(CikisSonucu(_sira(hedef_bari), hedef_bari, "close", hedef_bari + ADIM_4H, "olagan",
                                        hedef, pd.Timedelta(0)))

    # 3. Ileri kayma: acilisi T'ye esit ya da sonra olan ilk donem ici bar (B dahil).
    sonrakiler = indeks[np.asarray(ayni_ya_da_sonra(indeks, hedef), dtype=bool)
                        & np.asarray(ayni_ya_da_once(indeks, b), dtype=bool)]
    if len(sonrakiler) == 0:
        _seride_yok(f"Hedef bar {hedef_acilis} eksik ve {hedef} ile B ({b}) arasinda bar yok")
    ilk = sonrakiler[0]
    # Kume olcutu ileri kayma sinirindan once (rev.4'ten beri kume siniri kosulsuz
    # onceliklidir; rev.8 bu sirayi degistirmez).
    if _cikis_odemesi_kume_disinda(ilk, kume_son):
        raise KumeSiniriHatasi(
            f"Ileri kaymali cikis {ilk} kume sonunu ({kume_son}) asiyor (on-kayit §4 rev.8: olay olusmaz).")
    sinir = hedef_acilis + int(birincil_ufuk) * adim(bar)
    if sonra(ilk, sinir):
        raise IleriKaymaSiniriHatasi(
            f"Hedef bar {hedef_acilis} eksik ve sonraki mevcut bar {ilk} ileri kayma sinirindan "
            f"({birincil_ufuk} x {adim(bar)}) uzak (on-kayit §4 rev.8: olay olusmaz).")
    return _kume_icinde(CikisSonucu(_sira(ilk), ilk, "open", ilk, "ileri_kayma", hedef, ilk - hedef_acilis))


# --- Pozisyon plani (on-kayit §4 rev.8) ---------------------------------------------
#
# `pozisyon_plani` giris, cikis ve kume olcutunu uygular. Funding tamligi ve sinyal
# penceresi tamligi dahil TEK karar noktasi `data.pozisyon.olay_karari`dir (on-kayit
# §4 rev.8 "Olayin kumede olusma olcutu"); brut getiri, MAE, funding ve K1/K2
# kontrol barlari o kararin ciktisini kullanir. `cikis_bari` ve `pozisyon_plani`
# o kapinin ic adimlaridir; analiz kodu (events/, study/) onlari dogrudan cagirmaz
# (kaynak taramasi: tests/tarama_yardimcisi).

_PLAN_GIZLI = object()


@dataclass(frozen=True)
class PozisyonPlani:
    """Kurallardan gecmis bir pozisyon. Yalnizca `pozisyon_plani` uretir.

    `_imza` alanlarin icerigine ve modul ici gizli bir nesneye baglidir: elle
    kurulan ya da `dataclasses.replace` ile degistirilen plan `plan_dogrula`dan
    gecemez. `giris` giris anidir (P0 barinin acilisi); `cikis_ani` gercek cikis
    anidir. `cikis.tur` cikis turunu tasir (olagan / ileri kayma / donem sonu).
    """

    sinyal_zamani: pd.Timestamp
    giris: pd.Timestamp
    cikis: CikisSonucu
    cikis_ani: pd.Timestamp
    bar: str
    ufuk: int
    birincil_ufuk: int
    kume_baslangic: pd.Timestamp | None
    kume_bitis: pd.Timestamp | None
    donem_baslangic: pd.Timestamp
    donem_bitis: pd.Timestamp
    _imza: int = field(default=0, repr=False, compare=False)

    @property
    def cikis_turu(self) -> str:
        return self.cikis.tur

    @property
    def donem_sonu_mu(self) -> bool:
        return self.cikis.tur == "donem_sonu"


def _plan_imzasi(plan: PozisyonPlani) -> int:
    return hash((
        _PLAN_GIZLI, plan.sinyal_zamani, plan.giris, plan.cikis, plan.cikis_ani, plan.bar, plan.ufuk,
        plan.birincil_ufuk, plan.kume_baslangic, plan.kume_bitis, plan.donem_baslangic, plan.donem_bitis,
    ))


def plan_dogrula(plan) -> None:
    """Plan `pozisyon_plani`nin urettigi ve degistirilmemis bir plan mi?"""
    if not isinstance(plan, PozisyonPlani):
        raise TypeError(f"plan bir PozisyonPlani olmali (pencere.pozisyon_plani ciktisi). Verilen: {type(plan).__name__}")
    if plan._imza != _plan_imzasi(plan):
        raise ValueError(
            "PozisyonPlani elle kurulmus ya da degistirilmis; yalnizca pencere.pozisyon_plani "
            "plan uretir (on-kayit §4 rev.8)."
        )


def pozisyon_plani(
    zamanlar,
    sinyal_zamani,
    ufuk: int,
    bar: str,
    *,
    birincil_ufuk: int,
    kume_baslangic,
    kume_bitis,
    donem_baslangic,
    donem_bitis,
) -> PozisyonPlani:
    """Pozisyon plani: t barinda (bar izgarasinda) tespit edilen olayin pozisyonu
    olusur mu, nereden girilir, nereden ve ne zaman cikilir? (on-kayit §4 rev.8)

    `zamanlar`: sembolun donem ici 4h bar acilislari; her izgarada fiyat 4h
    barlardan okunur. Sirasiyla:
      1. Sinyal kume baslangicindan once olamaz -> `KumeSiniriHatasi`.
      2. Sinyal bari donem ici olmali (`donem_ici_mi`; 1d'de gunun alti 4h bari)
         -> `DonemDisiSinyal` (programlama hatasi: uygunluk bunu engeller).
      3. Giris ani = t'nin kapanisi; giris ani kume sonundan sonraysa
         `KumeSiniriHatasi`; acilisi giris anina esit donem ici 4h bar mevcut
         olmali -> `GirisBariYok` (olay olusmaz).
      4. `cikis_bari`: donem sonu (T >= K, rev.9), olagan cikis, ileri kayma ve siniri.
      5. Gercek cikis ani + tolerans kume sonunu asmamali -> `KumeSiniriHatasi`.

    Kural geregi olay olusmazsa `OlayOlusmaz` alt sinifi firlatir; her alt sinif
    bir ret gerekcesidir (`ret_gerekcesi`). Donem sinirlari zorunludur ve None
    olamaz; kume sinirlari yoksa acikca None. Saf fonksiyon; getiri hesaplamaz.
    """
    t = utc_zamani(sinyal_zamani, "sinyal_zamani")
    kume_bas = sinir_zamani(kume_baslangic, "kume_baslangic")
    kume_son = sinir_zamani(kume_bitis, "kume_bitis")
    donem_bas = sinir_zamani(donem_baslangic, "donem_baslangic")
    donem_son = sinir_zamani(donem_bitis, "donem_bitis")
    if donem_bas is None or donem_son is None:
        raise TypeError("pozisyon_plani: donem_baslangic ve donem_bitis None olamaz (on-kayit §2, §4 rev.8).")

    if kume_bas is not None and once(t, kume_bas):
        raise KumeSiniriHatasi(f"Sinyal {t} kume baslangicindan ({kume_bas}) once (olay bu kumede olusmaz).")
    if not donem_ici_mi(t, bar, donem_baslangic=donem_bas, donem_bitis=donem_son):
        raise DonemDisiSinyal(f"Sinyal bari {t} ({bar}) donem ici degil [{donem_bas}, {donem_son}] "
                              "(on-kayit §6 rev.8).")
    indeks = _zaman_dizisi_dogrula(zamanlar, "pozisyon_plani")
    giris = giris_ani(t, bar)
    if kume_son is not None and sonra(giris, kume_son):
        raise KumeSiniriHatasi(f"Giris ani {giris} kume sonundan ({kume_son}) sonra (olay bu kumede olusmaz).")
    giris_4h = ayni_andaki_bar(indeks, giris)
    if giris_4h is None or not donem_ici_4h_maskesi(giris_4h, donem_baslangic=donem_bas, donem_bitis=donem_son):
        raise GirisBariYok(f"Acilisi giris anina ({giris}) esit donem ici 4h bar yok "
                           "(on-kayit §4 rev.8 'Fiyat okuma tabani': olay olusmaz).")

    cikis = cikis_bari(indeks, giris_4h, ufuk, bar, birincil_ufuk=birincil_ufuk, donem_bitis=donem_son,
                       kume_bitis=kume_son)
    an = cikis_ani(cikis)
    if _cikis_odemesi_kume_disinda(an, kume_son):
        raise KumeSiniriHatasi(
            f"Cikis ani {an} ve cikis anindaki funding odemesi kume sonunu ({kume_son}) asiyor "
            "(on-kayit §4 rev.8: olay bu kumede olusmaz)."
        )
    plan = PozisyonPlani(t, giris_4h, cikis, an, bar, int(ufuk), int(birincil_ufuk), kume_bas, kume_son,
                         donem_bas, donem_son)
    return replace(plan, _imza=_plan_imzasi(plan))


def ret_gerekcesi(hata: BaseException) -> str:
    """Reddedilen olayin gerekcesi (on-kayit §4 rev.8): `OlayOlusmaz` alt sinifinin
    `gerekce` ozelligi. OlayOlusmaz olmayan hata programlama hatasidir."""
    if not isinstance(hata, OlayOlusmaz):
        raise TypeError(f"{type(hata).__name__} bir ret gerekcesi degil (programlama hatasi): {hata}")
    return hata.gerekce
