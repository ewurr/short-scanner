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

Donem ve karantina kisitlari da buradan gecer (on-kayit §2 rev.2).

Sinir parametreleri (F1 kapanis bulgulari 1 ve 2): donem, karantina ve kume
sinirlari pencere ve cikis fonksiyonlarinda ANAHTAR SOZCUKLE ve VARSAYILANSIZ
verilir. Unutulan sinir TypeError verir; sinir gercekten yoksa cagiran taraf
bunu acikca `None` ile soyler. Boylece bir kuralin sessizce atlanmasi mumkun
olmaz.

Bu modul tamamen saftir: ag veya disk kullanmaz.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

import config
from data import donem as donem_modulu

# Bar tipine gore izgara adimi.
ADIMLAR = {
    config.BAR_4H: pd.Timedelta(hours=4),
    config.BAR_1D: pd.Timedelta(days=1),
}


def adim(bar: str) -> pd.Timedelta:
    """Bar tipinin zaman izgarasi adimi."""
    try:
        return ADIMLAR[bar]
    except KeyError:
        raise ValueError(f"Bilinmeyen bar: {bar!r}") from None


@dataclass(frozen=True)
class CikisSonucu:
    """Ufuk sonucu. Getiri HESAPLANMAZ; yalnizca hangi barda, hangi fiyat
    alanindan cikilacagi soylenir."""

    indeks: int
    zaman: pd.Timestamp
    fiyat_alani: str  # "close" (normal) veya "open" (ileri kaymali cikis)
    kaydi: bool  # hedef bar eksikti, sonraki mevcut bara kayildi mi?
    kirpildi: bool  # donem sonu / seri sonu / karantina nedeniyle kirpildi mi?
    # Kirpildiysa neden: "karantina", "donem_sonu" ya da "seri_sonu" (delist
    # veya verinin bittigi yer). Kirpilmadiysa None.
    kirpma_nedeni: str | None = None


class KumeSiniriHatasi(ValueError):
    """Olayin ufku ait oldugu kumenin tarih araligina sigmiyor (on-kayit §3 rev.4).

    Kume sinirinda kirpilmis cikis kullanilmaz ve komsu kumeden veri okunmaz;
    olay o kumede hic olusmaz. Kume sinirlari `split.kume_araligi` uzerinden gelir.
    """


class IleriKaymaSiniriHatasi(ValueError):
    """Hedef cikis bari eksik ve sonraki mevcut bar ileri kayma sinirindan uzak
    (on-kayit §4 rev.6).

    Ileri kayma, olayin birincil ufku kadar sureyle sinirlidir (H1, H2: 18 bar;
    H3: 14 gun). Daha uzaktaki bardan cikilmaz ve kirpilmis getiri kullanilmaz;
    olay olusmaz.
    """


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


def karantina_dogrula(karantina_aylari) -> tuple:
    """Karantina aylari: ay listesi ya da bilincli `None` (karantina yok).

    Tek bir ay metni (`"2025-12"`) reddedilir: karakter karakter dolasilip sessizce
    yanlis bir kume olusturulurdu.
    """
    if karantina_aylari is None:
        return ()
    if isinstance(karantina_aylari, (str, bytes)):
        raise TypeError(
            f"karantina_aylari bir ay LISTESI olmali, tek metin degil. Verilen: {karantina_aylari!r}"
        )
    return tuple(karantina_aylari)


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
    donem, kume ve karantina sinirlarini bilmez. Eskiden herkese acik
    `pencere_tam_mi` olarak duruyordu ve F2'de tek basina kapi olarak
    kullanilsaydi, kume oncesi veriyi iceren tam bir pencereye "gecerli"
    derdi -- yani kume kuralini sessizce atlardi. Sinirlari zorunlu parametre
    olarak eklemek `pencere_dilimi`nin ikinci bir kopyasini yaratirdi ve iki
    kopya zamanla birbirinden ayrisabilirdi (B4'teki `donem.pencere_gecerli_mi`
    ornegi). Bu yuzden tek kapi `pencere_dilimi` / `pencere_degeri`dir; bu
    fonksiyon yalnizca onun, donem/kume/karantina kontrolleri GECILDIKTEN
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
    karantina_aylari,
) -> pd.Series | None:
    """Zamanla tanimli pencereyi doner; kurallardan biri saglanmazsa None.

    Sirasiyla su kosullar aranir:
      1. Pencere donem baslangicini asmamali (on-kayit §2 rev.2),
      2. Pencere kume baslangicini asmamali (on-kayit §3 rev.5),
      3. Pencerenin hicbir bari karantina ayina dusmemeli,
      4. Penceredeki beklenen barlarin tamami mevcut olmali (rev.3 tamlik sarti).

    Kume siniri, seride kume oncesi veri BULUNSA BILE uygulanir: kural verinin
    kume sinirinda kesilmis olmasina dayanmaz. `kume_baslangic`,
    `donem_baslangic` ve `karantina_aylari` zorunludur; sinir yoksa acikca None.
    """
    kume_bas = sinir_zamani(kume_baslangic, "kume_baslangic")
    donem_bas = sinir_zamani(donem_baslangic, "donem_baslangic")
    karantina_listesi = karantina_dogrula(karantina_aylari)
    beklenen = beklenen_zamanlar(t, bar_sayisi, bar, t_dahil=t_dahil)

    if donem_bas is not None and beklenen[0] < donem_bas:
        return None

    if kume_bas is not None and beklenen[0] < kume_bas:
        return None  # pencere kume oncesi veriyi odunc alamaz (rev.5)

    if karantina_listesi:
        karantina = {donem_modulu.ay_donemi(a) for a in karantina_listesi}
        if any(pd.Period(z, freq="M") in karantina for z in beklenen):
            return None

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
    karantina_aylari,
    islev="median",
) -> float:
    """Zamanla tanimli pencereye bir toplayici uygular; kural ihlalinde NaN.

    `islev` bir Series metodu adi ("median", "mean", "min", "max", "sum") ya da
    Series alan bir cagrilabilirdir. `t_dahil` (on-kayit §5 rev.4) ile
    `kume_baslangic`, `donem_baslangic`, `karantina_aylari` zorunludur.
    """
    dilim = pencere_dilimi(
        seri,
        t,
        bar_sayisi,
        bar,
        t_dahil=t_dahil,
        kume_baslangic=kume_baslangic,
        donem_baslangic=donem_baslangic,
        karantina_aylari=karantina_aylari,
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
    karantina_aylari,
) -> float:
    """Ic pencere degerlerinin dis penceredeki toplayicisi; kural ihlalinde NaN.

    Tanim (zamanla):
      - Dis izgara: `beklenen_zamanlar(t, dis_bar_sayisi, t_dahil=dis_t_dahil)`.
      - Her dis bar s icin ic deger: `ic_islev` uygulanmis
        `beklenen_zamanlar(s, ic_bar_sayisi, t_dahil=ic_t_dahil)` penceresi.
      - Sonuc: ic degerlere `dis_islev`.
    Ornek, H1'in hacim kosulu: dis 180 bar (t dahil) x ic 6 barlik toplam, medyan.

    Tum ic pencerelerin birlesimi tek bir kesintisiz araliktir; o aralik
    `pencere_dilimi`nden gecer. Boylece HER ic pencere tamlik, donem, kume ve
    karantina kontrolunden gecmis olur; biri bile gecemezse sonuc NaN.
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
        karantina_aylari=karantina_aylari,
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
    karantina_aylari,
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
        karantina_aylari=karantina_aylari,
    )


# --- Giris ve cikis ----------------------------------------------------------


def giris_bari(zamanlar, sinyal_zamani, bar: str) -> pd.Timestamp | None:
    """t+1 barinin zamani; o bar eksikse None (on-kayit §2 rev.3: olay olusmaz).

    Gelecege bakis yoktur: sinyal t barinin kapanisinda hesaplanir, islem t+1
    barinin acilisinda acilir (CLAUDE.md §3.6).
    """
    hedef = utc_zamani(sinyal_zamani, "sinyal_zamani") + adim(bar)
    return hedef if hedef in pd.DatetimeIndex(zamanlar) else None


def cikis_hedefi(giris_zamani, ufuk: int, bar: str) -> pd.Timestamp:
    """Hedef cikis barinin zamani: t+h = giris + (h-1) x adim (on-kayit §4).

    Giris t+1 barindadir ve pozisyon t+1..t+h arasinda h bar tutulur.
    """
    if ufuk < 1:
        raise ValueError(f"ufuk en az 1 bar olmali: {ufuk}")
    return utc_zamani(giris_zamani, "giris_zamani") + (ufuk - 1) * adim(bar)


def _kume_sonunu_asar(zaman: pd.Timestamp, kume_son: pd.Timestamp | None) -> bool:
    """On-kayit §3 rev.4'un TEK uygulamasi: bir cikis ani kume sonunu asiyor mu?

    Bar zamani acilis zamanidir; kumenin son bari, acilisi kume sonuna esit ya da
    ondan once olan bardir (`klines.donem_kes` ile ayni kural). Hem
    `ufuk_kumeye_sigar_mi` hem `cikis_bari` bu fonksiyonu kullanir; kuralin
    ikinci bir kopyasi yoktur.
    """
    return kume_son is not None and zaman > kume_son


def ufuk_kumeye_sigar_mi(sinyal_zamani, ufuk: int, bar: str, *, kume_baslangic, kume_bitis) -> bool:
    """Olayin ufku ait oldugu kumenin tarih araligina tam olarak sigiyor mu?

    On-kayit §3 rev.4: sigmayan olay o kumede hic olusmaz; kirpilmis getiri
    kullanilmaz ve komsu kumeden veri odunc alinmaz. Ikincil ufuklar ayni
    kurala kendi uzunluklariyla tabidir.

    - Olayin kumesi, sinyal barinin (t) dustugu kumedir: `bas <= t`.
    - Cikis bari t+h, `cikis_bari` ile ayni hedef ve ayni sinir fonksiyonuyla
      denetlenir (`cikis_hedefi`, `_kume_sonunu_asar`).
    """
    t = utc_zamani(sinyal_zamani, "sinyal_zamani")
    kume_bas = sinir_zamani(kume_baslangic, "kume_baslangic")
    kume_son = sinir_zamani(kume_bitis, "kume_bitis")
    hedef = cikis_hedefi(t + adim(bar), ufuk, bar)
    if kume_bas is not None and t < kume_bas:
        return False
    return not _kume_sonunu_asar(hedef, kume_son)


def _karantina_siniri(giris: pd.Timestamp, karantina_aylari: tuple) -> pd.Timestamp | None:
    """Giristen sonraki ilk karantina ayinin baslangicindan hemen onceki an.

    Hicbir cikis (ileri kaymali olan dahil) bu anin otesine gecemez. Giris bir
    karantina ayinin icindeyse ValueError: karantina ayinda olay olamaz
    (on-kayit §2 rev.2).
    """
    if not karantina_aylari:
        return None
    for ay in sorted({donem_modulu.ay_donemi(a) for a in karantina_aylari}):
        bas, son = ay.start_time, ay.end_time
        if giris.tzinfo is not None:
            bas, son = bas.tz_localize("UTC"), son.tz_localize("UTC")
        if bas <= giris <= son:
            raise ValueError(f"Giris bari karantina ayinda: {giris} ({ay})")
        if giris < bas:
            return bas - pd.Timedelta(1, "ns")
    return None


def cikis_ani(cikis: CikisSonucu, bar: str) -> pd.Timestamp:
    """Pozisyonun kapandigi AN (on-kayit §4 rev.6 funding siniri icin).

    Bar zamani acilis zamanidir. Kapanistan cikista an `zaman + adim`, ileri
    kaymali (acilistan) cikista an `zaman`dir. Funding hesabi cikis anini bu
    fonksiyondan alir; bar zamanini cikis ani sanmak son odemeyi kacirirdi.
    """
    cikis_tutarliligi_dogrula(cikis)
    if cikis.fiyat_alani == "close":
        return cikis.zaman + adim(bar)
    return cikis.zaman


KIRPMA_NEDENLERI = ("karantina", "donem_sonu", "seri_sonu")


def cikis_tutarliligi_dogrula(cikis: CikisSonucu) -> None:
    """Elle kurulmus bir CikisSonucu'nun `cikis_bari`nin uretebilecegi bir bicimde
    oldugunu dogrular (F1 kapanis denetimi bulgu 5); degilse ValueError.

    `cikis_bari` yalnizca su bicimleri uretir:
      - normal cikis     : fiyat_alani="close", kaydi=False, kirpildi=False, neden None
      - ileri kaymali    : fiyat_alani="open",  kaydi=True,  kirpildi=False, neden None
      - kirpilmis cikis  : fiyat_alani="close", kaydi=False, kirpildi=True,
                           neden KIRPMA_NEDENLERI'nden biri
    Sinira gore dogrulama (cikis bari donem sonu ya da karantina sinirini asiyor
    mu) sinirlari bilen cagiran tarafta yapilir (`funding.pozisyon_fundingi`).
    """
    if not isinstance(cikis, CikisSonucu):
        raise TypeError(f"cikis bir CikisSonucu olmali (cikis_bari ciktisi). Verilen: {cikis!r}")
    utc_zamani(cikis.zaman, "cikis.zaman")
    if cikis.fiyat_alani not in ("close", "open"):
        raise ValueError(f"Bilinmeyen fiyat_alani: {cikis.fiyat_alani!r}")
    if cikis.kaydi is not (cikis.fiyat_alani == "open"):
        raise ValueError(f"Tutarsiz cikis: kaydi={cikis.kaydi!r} ama fiyat_alani={cikis.fiyat_alani!r}")
    if cikis.kirpildi is True:
        if cikis.fiyat_alani != "close" or cikis.kirpma_nedeni not in KIRPMA_NEDENLERI:
            raise ValueError(
                f"Tutarsiz kirpilmis cikis: fiyat_alani={cikis.fiyat_alani!r}, "
                f"kirpma_nedeni={cikis.kirpma_nedeni!r}"
            )
    elif cikis.kirpildi is False:
        if cikis.kirpma_nedeni is not None:
            raise ValueError(f"Kirpilmamis cikista kirpma_nedeni olamaz: {cikis.kirpma_nedeni!r}")
    else:
        raise ValueError(f"kirpildi bool olmali: {cikis.kirpildi!r}")


def cikis_bari(
    zamanlar,
    giris_zamani,
    ufuk: int,
    bar: str,
    *,
    birincil_ufuk: int,
    donem_bitis,
    karantina_aylari,
    kume_bitis,
) -> CikisSonucu:
    """Ufuk sonundaki cikis barini secer (on-kayit §2 rev.3, §4 rev.4).

    - On-kayit §4: `P0 = open[t+1]`, `P1 = close[t+h]`. Pozisyon t+1..t+h
      arasinda h bar tutulur. `giris_zamani` t+1 barinin zamanidir, dolayisiyla
      hedef cikis bari `giris + (h-1) x adim` = t+h'dir. Ufuk zamanla olculur.
    - Hedef bar mevcutsa cikis o barin KAPANISIDIR.
    - Hedef bar eksikse cikis, sonraki ilk mevcut barin ACILISIDIR (ileri kayma).
    - Ileri kaymadan ONCELIKLI uc sinir vardir; en erken olan uygulanir ve cikis
      sinirdan onceki son barin KAPANISIDIR:
        * karantina : giristen sonraki ilk karantina ayinin baslangici (rev.4),
        * donem_sonu: listeleme doneminin bitisi,
        * seri_sonu : serinin son bari (delist ya da verinin bittigi yer).
      Esitlikte oncelik bu siradadir.
    - `kume_bitis` (on-kayit §3 rev.4): cikis bari t+h ya da ileri kaymali cikis
      bari kume sonunu asiyorsa `KumeSiniriHatasi` firlatilir. Kume sinirinda
      kirpma YAPILMAZ; komsu kumeden veri okunmaz. Kume icinde verinin gercekten
      bitmesi (delist) ise §4 uyarinca kirpilmaya devam eder.
    - `birincil_ufuk` (on-kayit §4 rev.6): ileri kaymanin ust siniri, olayin
      BIRINCIL ufku kadar suredir (bar sayisi; H1, H2: 18, H3: 14). Ikincil
      ufuklar da ayni siniri kullanir. Kayma, hedef bardan sonraki mevcut bara
      olan mesafedir (`sonraki - hedef`); `birincil_ufuk x adim`dan uzunsa
      `IleriKaymaSiniriHatasi` (olay olusmaz). Donem sonu, delist ve karantina
      bu kuraldan onceliklidir: sinir bu kayma araliginin icindeyse kirpilir.

    `birincil_ufuk`, `donem_bitis`, `karantina_aylari` ve `kume_bitis`
    zorunludur; sinir yoksa acikca None (`birincil_ufuk` icin None yoktur).
    Getiri HESAPLAMAZ; yalnizca cikis barini ve hangi fiyat alanindan
    okunacagini soyler.
    """
    if isinstance(birincil_ufuk, bool) or not isinstance(birincil_ufuk, (int, np.integer)):
        raise TypeError(f"birincil_ufuk tamsayi bar sayisi olmali: {birincil_ufuk!r}")
    if birincil_ufuk < 1:
        raise ValueError(f"birincil_ufuk en az 1 bar olmali: {birincil_ufuk}")
    indeks = _zaman_dizisi_dogrula(zamanlar, "cikis_bari")
    if len(indeks) == 0:
        raise ValueError("Bar listesi bos.")
    giris = utc_zamani(giris_zamani, "giris_zamani")
    if giris not in indeks:
        raise KeyError(f"Giris bari seride yok: {giris}")
    donem_son = sinir_zamani(donem_bitis, "donem_bitis")
    kume_son = sinir_zamani(kume_bitis, "kume_bitis")
    karantina_listesi = karantina_dogrula(karantina_aylari)

    hedef = cikis_hedefi(giris, ufuk, bar)
    if _kume_sonunu_asar(hedef, kume_son):
        raise KumeSiniriHatasi(
            f"Ufuk kume sinirini asiyor: cikis bari {hedef} > kume sonu {kume_son} "
            "(on-kayit §3 rev.4: olay bu kumede olusmaz)"
        )

    adaylar: list[tuple[pd.Timestamp, str]] = []
    karantina_siniri = _karantina_siniri(giris, karantina_listesi)
    if karantina_siniri is not None:
        adaylar.append((karantina_siniri, "karantina"))
    if donem_son is not None:
        adaylar.append((donem_son, "donem_sonu"))
    adaylar.append((indeks[-1], "seri_sonu"))
    sinir, sinir_nedeni = min(adaylar, key=lambda aday: aday[0])

    def _kirp() -> CikisSonucu:
        # F1 kapanis bulgusu 5: kume icinde calisirken serinin bitmesi iki sey
        # olabilir -- gercek delist ya da verinin kume sinirinda KESILMIS olmasi.
        # Kesim delist sayilirsa kirpilmis cikis kullanilir (rev.4 ihlali). Seri
        # sonu ancak sembolun donemi kumenin icinde bitiyorsa delisttir; donem
        # bilinmiyorsa ya da kumeden sonra suruyorsa bir sonraki mevcut bar kume
        # disindadir ve olay bu kumede olusmaz.
        if sinir_nedeni == "seri_sonu" and kume_son is not None:
            if donem_son is None or donem_son > kume_son:
                raise KumeSiniriHatasi(
                    f"Seri {indeks[-1]}'de bitiyor ama hedef cikis {hedef} kume icinde ve "
                    f"sembolun donemi kume icinde bitmiyor (donem_bitis={donem_son}); bu "
                    "bir delist degil kume kesimidir (on-kayit §3 rev.4: olay olusmaz)."
                )
        gecerli = indeks[indeks <= sinir]
        if len(gecerli) == 0:
            raise ValueError("Sinir icinde hic bar yok.")
        son = gecerli[-1]
        return CikisSonucu(
            indeks=int(np.flatnonzero(indeks == son)[0]),
            zaman=son,
            fiyat_alani="close",
            kaydi=False,
            kirpildi=True,
            kirpma_nedeni=sinir_nedeni,
        )

    if hedef > sinir:
        return _kirp()

    if hedef in indeks:
        return CikisSonucu(
            indeks=int(np.flatnonzero(indeks == hedef)[0]),
            zaman=hedef,
            fiyat_alani="close",
            kaydi=False,
            kirpildi=False,
        )

    # Hedef bar eksik: sinir icindeki sonraki ilk mevcut barin ACILISI.
    sonrakiler = indeks[(indeks > hedef) & (indeks <= sinir)]
    if len(sonrakiler) == 0:
        return _kirp()
    ilk = sonrakiler[0]
    if _kume_sonunu_asar(ilk, kume_son):
        raise KumeSiniriHatasi(
            f"Ileri kayma kume sinirini asiyor: {ilk} > kume sonu {kume_son} "
            "(on-kayit §3 rev.4: kumeler arasi veri odunc alinmaz)"
        )
    kayma_siniri = int(birincil_ufuk) * adim(bar)
    if ilk - hedef > kayma_siniri:
        raise IleriKaymaSiniriHatasi(
            f"Hedef cikis bari {hedef} eksik ve sonraki mevcut bar {ilk} ileri kayma "
            f"sinirindan ({birincil_ufuk} bar = {kayma_siniri}) uzak "
            "(on-kayit §4 rev.6: olay olusmaz)"
        )
    return CikisSonucu(
        indeks=int(np.flatnonzero(indeks == ilk)[0]),
        zaman=ilk,
        fiyat_alani="open",
        kaydi=True,
        kirpildi=False,
    )
