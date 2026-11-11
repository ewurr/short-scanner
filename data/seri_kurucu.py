"""Vektorel seri kuruculari (performans 2b-1; plan v3 G3, G5, G6, G7, G13, G16, G17, G18, G20; RESULTS §14.48).

NE: kapinin sinyal pencerelerini, capasiz pencere hesaplanabilirligini ve uygunlugu bir sinyal IZGARASININ butun
barlari icin TEK SEFERDE kurar. Kapiya BAGLI DEGILDIR (P2b-1): `pozisyon.olay_karari` ve `sinyal_kosulu` bu turda
degismez; kapinin bu kuruculara gecisi P2b-2'nin isidir.

SAFLIK SOZLESMESI (bu modulun var olma kosulu):
  - Veri YUKLEMEZ. Girdiler kapinin bugunku veri yolunun ciktisidir: `pozisyon._karar_verisi`nin dondurdugu 4h, funding
    ve 1d cerceveleri; sinyal izgarasi `pozisyon.hipotez_izgarasi_barlari`ndan (G20); donem ve kume sinirlari.
  - Hicbir yukleyiciyi, bellek onbellegini ya da erisim denetimini cagirmaz; diske ve aga cikmaz. Yani YENI BIR VERI
    ERISIM YOLU ACMAZ: bu modulun okuyabildigi her bayt cagiranin zaten okumus oldugu bir cercevedir. Bu yuzden onay
    baglami ve kesif baglami burada denetlenmez; denetim cagiranin (kapi, P2b-2) veri yolundadir.
  - Yalnizca saf yardimcilari kullanir: `pencere`nin zaman toleransi ve donem uyeligi yuklemleri, `klines`in hucre
    olcutu (`hucreleri_tam_mi`, G4), `funding`in vektorel sinyal penceresi kurallari (`sinyal_penceresi_ayrintisi`,
    P2a), `eligibility`nin esik denetimi. Kural ICAT ETMEZ; her kural on-kayittaki yerinden ve skaler yoldaki
    karsiligindan alinir.
  - Analiz kodu taramasinda bu modulun adi YASAKTIR (`tests/tarama_yardimcisi.SERI_KURUCU_DESENI`). Kullananlar:
    kapi (P2b-2), testler ve acik adla istisna edilen gercek veri esitlik betigi.

DOGRULUK SOZLESMESI. Her deger, ayni girdide dondurulmus skaler referanstaki karsiligiyla BIT DUZEYINDE aynidir (G6).
Bunu saglayan uc kural:
  1. Pencere tamligi ACIK SAYIM MASKESIYLE kurulur (G3): seri izgaranin duzenli adimli kopyasina KESIN zaman esitligiyle
     yerlestirilir (skaler `isin`/`reindex` ile ayni); penceredeki mevcut bar sayisi tamsayi kumulatif toplamdan
     okunur ve beklenen bar sayisina esit olmayan pencere NaN olur. Mevcutluk = satir var VE barin butun fiyat/hacim
     hucreleri sonlu (on-kayit §2 rev.11/rev.12). Donem basi ve kume basi IKI AYRI maskeyle, toleransla (`pencere.once`)
     uygulanir; verinin kesilmis olmasina dayanilmaz (G13: seride kume disi veri olsa bile).
  2. YASAK: NaN atlayan indirgemenin eksik pencerede deger uretmesi; `rolling`/`expanding`; satir sayisina dayali
     `shift`/`iloc[-n:]`. Indirgeme yalnizca TAM pencerelerin 2B kopyasi uzerinde, skaler yolun pandas indirgemesiyle
     ayni numpy cekirdegiyle yapilir (`np.add.reduce`, `np.median`, `min`, `max`; satir basina ayni eleman sirasi).
     Bu esdegerlik bu ortamda (numpy 2.4.4, pandas 2.3.3, bottleneck yok) olculmustur ve G6 testleri onu her kosuda
     yeniden sinar; ortam degisirse testler kirmizi olur.
  3. Hata yolu skalerle ayni siniftadir: zaman dizisi bozuklugu `ZamanDizisiHatasi`; skaler yolun herhangi bir t'de
     yukselttigi hata, seri kurulumunda BIRIM hatasidir (G10). Hata ret koduna ya da NaN'a donusmez.

GELECEGE BAKIS (G16, CLAUDE.md §3.6). Bir t satirinin degeri yalnizca t barinin kapanisina kadarki veriye baglidir:
fiyat pencereleri t'de (ya da t'den once) biter; funding penceresi t barinin kapanisinda biter ve tolerans payi icindeki
kayit girer (G5, on-kayit §4). Funding'in zaman dizisi denetimi izgaranin son kapanisina kadarki kayitlari kapsar:
skaler yol bu kayitlari en gec t'de zaten okur, yani bozuk bir dizi skalerde de en az bir barda hata verir (G10).

Ag ve disk erisimi yoktur. Getiri hesaplamaz.
"""

from __future__ import annotations

import math
from types import MappingProxyType

import numpy as np
import pandas as pd

import config
from data import eligibility as eligibility_modulu
from data import funding as funding_modulu
from data import klines as klines_modulu
from data import pencere as pencere_modulu

# --- Sabitler (on-kayit §5; degerler `config`ten) -------------------------------------------------------------

_DORT_SAAT = pencere_modulu.ADIMLAR[config.BAR_4H]
_BIR_GUN = pencere_modulu.ADIMLAR[config.BAR_1D]

# Hipotez basina degerlerin adlari: dondurulmus referanstaki `CAPASIZ_PENCERELER` ve `DEGER_ADLARI` ile ayni.
CAPASIZ_PENCERELER = MappingProxyType({
    "H1": ("dip", "hacim_6", "hacim_medyani_180"),
    "H2": ("kirilim_dip", "kapanis_30_once", "funding_24s"),
    "H3": ("hacim_medyani_30g", "hacim_medyani_120_31", "sma50", "kapanis_30_once"),
})


# --- Ic yardimcilar ------------------------------------------------------------------------------------------

def _utc_izgara(izgara, bar: str) -> pd.DatetimeIndex:
    """Izgara UTC, kesin artan ve tekrarsiz olmali; 1d'de gun acilisi. Izgara hipotez izgarasi yardimcisindan gelir
    (G20); bu denetim yalnizca bicimi dogrular, kaynagi dogrulayamaz."""
    z = izgara if isinstance(izgara, pd.DatetimeIndex) else pd.DatetimeIndex(izgara)
    if len(z) == 0:
        return z.tz_localize("UTC") if z.tz is None else z.tz_convert("UTC")
    if z.tz is None:
        raise TypeError("izgara saat dilimsiz (tz-naive); tum zaman damgalari UTC olmali.")
    z = z.tz_convert("UTC")
    pencere_modulu._zaman_dizisi_dogrula(z, "seri_kurucu izgarasi")
    if bar == config.BAR_1D and not bool((z == z.floor("D")).all()):
        raise ValueError("1d izgarasi gun acilislarindan olusmali.")
    pencere_modulu.adim(bar)
    return z


def mum_serisi(mumlar: pd.DataFrame, alan: str) -> pd.Series:
    """Mum cercevesinin bir alani, acilis zamaniyla indeksli ve sirali (skaler `sinyal._seri` ile ayni kural).

    Sayisal olmayan ve sonlu olmayan deger NaN; barin HERHANGI bir fiyat/hacim hucresi bozuksa (`klines.hucreleri_tam_mi`,
    G4: hucre kuralinin tek kaynagi) bar her alanda NaN, yani hicbir pencerede mevcut degildir (on-kayit §2 rev.12)."""
    if alan not in mumlar:
        raise KeyError(f"Mum cercevesinde {alan!r} sutunu yok (sinyal penceresi kurulamaz).")
    degerler = pd.to_numeric(mumlar[alan], errors="coerce").to_numpy(dtype=float)
    degerler = np.where(np.isfinite(degerler), degerler, np.nan)
    degerler = np.where(klines_modulu.hucreleri_tam_mi(mumlar), degerler, np.nan)
    return pd.Series(degerler, index=pd.DatetimeIndex(mumlar["open_time"])).sort_index()


def gunluk_hacim(gunluk: pd.DataFrame) -> pd.Series:
    """Uygunluk hacminin serisi: 1d `quote_volume`, gun acilisiyla indeksli (`eligibility.gunluk_hacim_serisi`).

    DIKKAT (skalerle ayni, bilincli): bu seride hucre kurali UYGULANMAZ ve sonsuz deger NaN'a cevrilmez; yalnizca
    sayiya cevrilemeyen deger NaN'dir. 1d serisi `klines.gunluge_cevir`den geldigi icin bozuk hucreli gun zaten yoktur."""
    return eligibility_modulu.gunluk_hacim_serisi(gunluk)


class _Duzenli:
    """Bir serinin duzenli adimli (bar izgarasi) kopyasi: KESIN zaman esitligiyle yerlestirme (skaler `isin` ile ayni).

    `deger[i]`: izgaradaki i. konumun degeri (NaN = bar yok ya da bozuk); `sayim[i]`: [0, i) araligindaki mevcut bar
    sayisi (tamsayi; acik sayim maskesi, G3). Izgara disindaki (adima hizasiz) satirlar hicbir beklenen zamana esit
    olamayacagi icin yerlestirilmez; skaler yolda da hicbir pencereyi tamamlamazlar."""

    def __init__(self, seri: pd.Series, bar: str, izgara: pd.DatetimeIndex, en_uzun_geri: int):
        self.adim = pencere_modulu.adim(bar)
        self.indeks = pd.DatetimeIndex(seri.index)
        self.bar = bar
        if len(izgara):
            alt = izgara[0] - en_uzun_geri * self.adim
            ust = izgara[-1]
        else:
            alt = ust = pd.Timestamp(0, tz="UTC")
        if len(self.indeks):
            alt = min(alt, self.indeks[0].floor(self.adim) if bar == config.BAR_4H else self.indeks[0].floor("D"))
            ust = max(ust, self.indeks[-1])
        self.koken = alt.floor(self.adim) if bar == config.BAR_4H else alt.floor("D")
        uzunluk = int((ust - self.koken) // self.adim) + 1
        self.deger = np.full(uzunluk, np.nan)
        if len(self.indeks):
            fark = self.indeks - self.koken
            hizali = np.asarray(fark % self.adim == pd.Timedelta(0), dtype=bool)
            konum = np.asarray(fark // self.adim, dtype=np.int64)
            gecerli = hizali & (konum >= 0) & (konum < uzunluk)
            self.deger[konum[gecerli]] = np.asarray(seri.to_numpy(dtype=float))[gecerli]
        mevcut = ~np.isnan(self.deger)
        self.sayim = np.concatenate(([0], np.cumsum(mevcut, dtype=np.int64)))

    def konum(self, zamanlar: pd.DatetimeIndex) -> np.ndarray:
        """Zamanlarin izgara konumu (zamanlar izgaraya hizali olmali; hizasiz zaman -1)."""
        fark = zamanlar - self.koken
        hizali = np.asarray(fark % self.adim == pd.Timedelta(0), dtype=bool)
        k = np.asarray(fark // self.adim, dtype=np.int64)
        return np.where(hizali, k, -1)

    def tam_mi(self, son: np.ndarray, n: int) -> np.ndarray:
        """[son-n+1, son] penceresinin n barinin tamami mevcut mu (acik sayim)."""
        bas = son - n + 1
        icinde = (bas >= 0) & (son < len(self.deger)) & (son >= 0)
        sonuc = np.zeros(len(son), dtype=bool)
        i = np.nonzero(icinde)[0]
        sonuc[i] = (self.sayim[son[i] + 1] - self.sayim[bas[i]]) == n
        return sonuc

    def pencereler(self, son: np.ndarray, n: int) -> np.ndarray:
        """Pencerelerin C-sirali 2B kopyasi (satir = pencere, eleman sirasi zaman sirasi; skaler dilim ile ayni)."""
        return np.ascontiguousarray(self.deger[son[:, None] + np.arange(-n + 1, 1)[None, :]])


def _sinir_maskesi(baslar: pd.DatetimeIndex, *, kume_baslangic, donem_baslangic) -> np.ndarray:
    """Pencere basi donem basini ve kume basini ASMAMALI (on-kayit §2 rev.7, §3 rev.5). Iki AYRI maske, zaman
    toleransiyla (`pencere.once`; §4 rev.8): sinirla ayni an olan pencere basi siniri asmis sayilmaz. Kume siniri
    seride kume oncesi veri bulunsa bile uygulanir (G13)."""
    donem_bas = pencere_modulu.utc_zamani(donem_baslangic, "donem_baslangic") if donem_baslangic is not None else None
    if donem_bas is None:
        raise TypeError("donem_baslangic None olamaz: donem siniri her hesapta verilir (on-kayit §2 'Listeleme donemi').")
    if isinstance(kume_baslangic, bool):
        raise TypeError(f"kume_baslangic bir zaman damgasi ya da acikca None olmali. Verilen: {kume_baslangic!r}")
    kume_bas = None if kume_baslangic is None else pencere_modulu.utc_zamani(kume_baslangic, "kume_baslangic")
    donem_ok = ~np.asarray(pencere_modulu.once(baslar, donem_bas), dtype=bool)
    kume_ok = np.ones(len(baslar), dtype=bool) if kume_bas is None else \
        ~np.asarray(pencere_modulu.once(baslar, kume_bas), dtype=bool)
    return donem_ok & kume_ok


def _indirge(pencereler: np.ndarray, islev: str) -> np.ndarray:
    """Skaler yolun pandas indirgemesiyle AYNI numpy cekirdegi (G6). Yalnizca TAM pencerelere uygulanir."""
    if pencereler.shape[0] == 0:
        return np.empty(0)
    if islev == "sum":
        return np.add.reduce(pencereler, axis=1)
    if islev == "mean":
        return np.add.reduce(pencereler, axis=1) / pencereler.shape[1]
    if islev == "median":
        return np.median(pencereler, axis=1)
    if islev == "min":
        return pencereler.min(axis=1)
    if islev == "max":
        return pencereler.max(axis=1)
    if islev == "ilk":
        return pencereler[:, 0].copy()
    raise ValueError(f"Bilinmeyen islev: {islev!r}")


def pencere_serisi(seri: pd.Series, sonlar: pd.DatetimeIndex, bar_sayisi: int, bar: str, *, islev: str,
                   kume_baslangic, donem_baslangic) -> np.ndarray:
    """Her `son` icin `[son-(N-1)×adim, son]` penceresinin degeri; kural ihlalinde NaN. Skaler `pencere_dilimi` +
    `pencere_degeri` (t_dahil=True bicimi; t haric ve ofsetli pencereler `son`u kaydirarak buraya iner).

    Kurallar skalerle ayni sirada: (1) pencere donem basini asmamali, (2) kume basini asmamali, (3) beklenen barlarin
    tamami mevcut olmali (acik sayim). Bir t (1) ve (2)'den gecerse skaler yol serinin zaman dizisini dogrular;
    burada da en az bir son siniri gecerse dogrulanir (tekrarli damga -> `ZamanDizisiHatasi`, skalerle ayni sinif).
    `islev`: "sum", "mean", "median", "min", "max" ya da "ilk" (`close[t-30]`: pencerenin ilk degeri)."""
    if isinstance(bar_sayisi, bool) or not isinstance(bar_sayisi, (int, np.integer)) or bar_sayisi < 1:
        raise ValueError("bar_sayisi en az 1 olan bir tamsayi olmali.")
    n = int(bar_sayisi)
    adim = pencere_modulu.adim(bar)
    sonlar = pd.DatetimeIndex(sonlar)
    sonuc = np.full(len(sonlar), np.nan)
    if len(sonlar) == 0:
        return sonuc
    sinir_ok = _sinir_maskesi(sonlar - (n - 1) * adim, kume_baslangic=kume_baslangic, donem_baslangic=donem_baslangic)
    if not sinir_ok.any():
        return sonuc
    seri = seri.sort_index()
    pencere_modulu._zaman_dizisi_dogrula(pd.DatetimeIndex(seri.index), "pencere_dilimi")
    d = _Duzenli(seri, bar, sonlar.sort_values(), n)
    konum = d.konum(sonlar)
    tam = sinir_ok & (konum >= 0) & d.tam_mi(konum, n)
    i = np.nonzero(tam)[0]
    sonuc[i] = _indirge(d.pencereler(konum[i], n), islev)
    return sonuc


def bar_degeri_serisi(seri: pd.Series, zamanlar: pd.DatetimeIndex) -> np.ndarray:
    """t barinin degeri; bar yoksa ya da deger sonlu degilse NaN (skaler `sinyal.bar_degeri`: ayni an, toleransla)."""
    seri = seri.sort_index()
    indeks = pd.DatetimeIndex(seri.index)
    degerler = seri.to_numpy(dtype=float)
    zamanlar = pd.DatetimeIndex(zamanlar)
    sonuc = np.full(len(zamanlar), np.nan)
    if len(indeks) == 0 or len(zamanlar) == 0:
        return sonuc
    ilk = indeks.searchsorted(pencere_modulu.ayni_an_basi(zamanlar), side="right")
    var = ilk < len(indeks)
    var[var] = indeks[ilk[var]] < pencere_modulu.ayni_an_sonu(zamanlar[var])
    sonuc[var] = degerler[ilk[var]]
    return np.where(np.isfinite(sonuc), sonuc, np.nan)


def ic_ice_serisi(seri: pd.Series, sonlar: pd.DatetimeIndex, *, dis_bar_sayisi: int, ic_bar_sayisi: int,
                  dis_islev: str, ic_islev: str, kume_baslangic, donem_baslangic) -> np.ndarray:
    """Ic pencere degerlerinin dis penceredeki indirgemesi (skaler `ic_ice_pencere_degeri`, iki pencere de t dahil).

    H1: dis 180 bar × ic 6 barlik toplam, medyan. Ic pencerelerin birlesimi `[t-(D+I-2) .. t]` tek parcadir ve TEK
    pencere olarak tamlik, donem ve kume kapisindan gecer; gecemezse NaN. Ic degerler her konum icin bir kez, skalerin
    `dilim.iloc[i:i+I].sum()` ile ayni cekirdekle hesaplanir; dis indirgeme onlarin 2B kopyasi uzerindedir."""
    n_dis, n_ic = int(dis_bar_sayisi), int(ic_bar_sayisi)
    kapsam = n_dis + n_ic - 1
    sonlar = pd.DatetimeIndex(sonlar)
    sonuc = np.full(len(sonlar), np.nan)
    if len(sonlar) == 0:
        return sonuc
    adim = pencere_modulu.adim(config.BAR_4H)
    sinir_ok = _sinir_maskesi(sonlar - (kapsam - 1) * adim, kume_baslangic=kume_baslangic,
                              donem_baslangic=donem_baslangic)
    if not sinir_ok.any():
        return sonuc
    seri = seri.sort_index()
    pencere_modulu._zaman_dizisi_dogrula(pd.DatetimeIndex(seri.index), "pencere_dilimi")
    d = _Duzenli(seri, config.BAR_4H, sonlar.sort_values(), kapsam)
    konum = d.konum(sonlar)
    tam = sinir_ok & (konum >= 0) & d.tam_mi(konum, kapsam)
    i = np.nonzero(tam)[0]
    if len(i) == 0:
        return sonuc
    # Ic degerler yalnizca TAM kapsamlarin icindeki konumlarda kullanilir; orada her ic pencere tamdir.
    gereken = np.unique((konum[i][:, None] + np.arange(-n_dis + 1, 1)[None, :]).ravel())
    ic = np.full(len(d.deger), np.nan)
    ic[gereken] = _indirge(d.pencereler(gereken, n_ic), ic_islev)
    dis = np.ascontiguousarray(ic[konum[i][:, None] + np.arange(-n_dis + 1, 1)[None, :]])
    sonuc[i] = _indirge(dis, dis_islev)
    return sonuc


# --- Hipotez pencereleri (on-kayit §5; adlar dondurulmus referanstaki fonksiyonlarla ayni) ---------------------

def _t_haric_sonlar(izgara: pd.DatetimeIndex, bar: str) -> pd.DatetimeIndex:
    return izgara - pencere_modulu.adim(bar)


def h1_dip(mumlar_4h, izgara, *, kume_baslangic, donem_baslangic) -> np.ndarray:
    """`min(low[t-6..t-1])` (§5 H1 madde 1; t HARIC)."""
    z = _utc_izgara(izgara, config.BAR_4H)
    return pencere_serisi(mum_serisi(mumlar_4h, "low"), _t_haric_sonlar(z, config.BAR_4H), config.H1_DIP_BAR,
                          config.BAR_4H, islev="min", kume_baslangic=kume_baslangic, donem_baslangic=donem_baslangic)


def h1_hacim_6(mumlar_4h, izgara, *, kume_baslangic, donem_baslangic) -> np.ndarray:
    """Son 6 barin toplam quote hacmi `[t-5 .. t]` (§5 H1 madde 1; t DAHIL)."""
    z = _utc_izgara(izgara, config.BAR_4H)
    return pencere_serisi(mum_serisi(mumlar_4h, "quote_volume"), z, config.H1_HACIM_TOPLAM_BAR, config.BAR_4H,
                          islev="sum", kume_baslangic=kume_baslangic, donem_baslangic=donem_baslangic)


def h1_hacim_medyani_180(mumlar_4h, izgara, *, kume_baslangic, donem_baslangic) -> np.ndarray:
    """Onceki 180 barin 6'li toplam hacim medyani; birlesim penceresi `[t-184 .. t]` (§5 H1 madde 1, rev.11)."""
    z = _utc_izgara(izgara, config.BAR_4H)
    return ic_ice_serisi(mum_serisi(mumlar_4h, "quote_volume"), z, dis_bar_sayisi=config.H1_HACIM_MEDYAN_BAR,
                         ic_bar_sayisi=config.H1_HACIM_TOPLAM_BAR, dis_islev="median", ic_islev="sum",
                         kume_baslangic=kume_baslangic, donem_baslangic=donem_baslangic)


class TepePenceresiTanimsiz(ValueError):
    """Teyit bari pump barindan 1..12 bar sonra degil ya da 4h izgarasinda degil (skalerde
    `sinyal.TepePenceresiKurulamaz`). Cagiran yalnizca tanimli teyit barlarini sorar."""


def h1_tepe_bar_sayilari(capa, teyitler: pd.DatetimeIndex) -> np.ndarray:
    """Her teyit bari icin tepe penceresinin bar sayisi: pump bari dahil, teyit barinin bir oncesine kadar (§5 H1
    madde 2 rev.11); 1..`config.H1_IZLEME_BAR`. Disinda kalan teyit icin skaler yol `TepePenceresiKurulamaz` verir;
    burada ayni sinif (`data.sinyal`deki) yukseltilir: degeri NaN'a cevirmek bir hata yolunu sessizlestirirdi."""
    from data import sinyal as sinyal_modulu  # yalnizca sinif (dayanilan)

    pump = pencere_modulu.utc_zamani(capa, "pump_bari")
    fark = pd.DatetimeIndex(teyitler) - pump
    if bool((fark % _DORT_SAAT != pd.Timedelta(0)).any()):
        raise sinyal_modulu.TepePenceresiKurulamaz("teyit bari pump barinin 4h izgarasinda degil.")
    sayi = np.asarray(fark // _DORT_SAAT, dtype=np.int64)
    if len(sayi) and (sayi.min() < 1 or sayi.max() > config.H1_IZLEME_BAR):
        raise sinyal_modulu.TepePenceresiKurulamaz(
            f"teyit bari pump barindan 1..{config.H1_IZLEME_BAR} bar sonra olmali (on-kayit §5 H1 madde 3).")
    return sayi


def h1_tepe(mumlar_4h, capa, teyitler, *, kume_baslangic, donem_baslangic) -> np.ndarray:
    """Tepe `max(high[pump .. teyit-1])` her teyit bari icin (§5 H1 madde 2 rev.11; G18). Pencere pump barini ICERIR,
    teyit barini ICERMEZ, en cok 12 bar; tamlik, donem ve kume kurali her pencerede (pump bari donem/kume disindaysa
    NaN). Pencere uzunlugu teyide gore degistigi icin her uzunluk ayri gruplanir."""
    z = _utc_izgara(teyitler, config.BAR_4H)
    sayi = h1_tepe_bar_sayilari(capa, z)
    seri = mum_serisi(mumlar_4h, "high")
    sonuc = np.full(len(z), np.nan)
    for n in np.unique(sayi):
        i = np.nonzero(sayi == n)[0]
        sonuc[i] = pencere_serisi(seri, _t_haric_sonlar(z[i], config.BAR_4H), int(n), config.BAR_4H, islev="max",
                                  kume_baslangic=kume_baslangic, donem_baslangic=donem_baslangic)
    return sonuc


def kapanis_30_once(mumlar, izgara, bar: str, *, kume_baslangic, donem_baslangic) -> np.ndarray:
    """`close[t-30]`; tamlik penceresi `[t-30 .. t]` = 31 bar (§5 rev.11)."""
    z = _utc_izgara(izgara, bar)
    return pencere_serisi(mum_serisi(mumlar, "close"), z, config.OTUZ_BAR_ONCE + 1, bar, islev="ilk",
                          kume_baslangic=kume_baslangic, donem_baslangic=donem_baslangic)


def yuksek_30_max(mumlar, izgara, bar: str, *, kume_baslangic, donem_baslangic) -> np.ndarray:
    """`max(high[t-30..t])`, 31 bar (§5 H2 madde 4, H3 madde 4 rev.13; gecersizlik seviyesinin tabani)."""
    z = _utc_izgara(izgara, bar)
    return pencere_serisi(mum_serisi(mumlar, "high"), z, config.OTUZ_BAR_ONCE + 1, bar, islev="max",
                          kume_baslangic=kume_baslangic, donem_baslangic=donem_baslangic)


def h2_kirilim_dip(mumlar_4h, izgara, k, *, kume_baslangic, donem_baslangic) -> np.ndarray:
    """`min(low[t-k..t-1])` (§5 H2 madde 3; t HARIC). `k` izgara degeri olmali."""
    if isinstance(k, bool) or not any(isinstance(k, (int, float, np.integer, np.floating)) and float(k) == float(a)
                                      for a in config.IZGARA["H2"]["k"]):
        from data import sinyal as sinyal_modulu
        raise sinyal_modulu.YapilandirmaHatasi(f"H2.k = {k!r} izgarada yok; on-kayit §5: {config.IZGARA['H2']['k']}.")
    z = _utc_izgara(izgara, config.BAR_4H)
    return pencere_serisi(mum_serisi(mumlar_4h, "low"), _t_haric_sonlar(z, config.BAR_4H), int(k), config.BAR_4H,
                          islev="min", kume_baslangic=kume_baslangic, donem_baslangic=donem_baslangic)


def h2_funding_24s(funding: pd.DataFrame, izgara, *, kume_baslangic, kume_bitis, donem_baslangic) -> np.ndarray:
    """Son 24 saatteki 8 saate normallestirilmis funding ortalamasi, her t icin (§5 H2 madde 1; §4 "Funding sinyal
    penceresinin tamligi" rev.9-rev.11; G5, G17).

    Pencere kurallari (yari acik pencere, capa, zincir, gecerli aralik, kume ici, kume sonundaki kayit) skalerle ayni
    vektorel uygulamadan gelir: `funding.sinyal_penceresi_ayrintisi` (P2a). G5: t'nin degeri yalnizca t barinin
    kapanisina kadarki kayitlara (tolerans payi icindeki kayit DAHIL) baglidir; oran dilimi `[ilk, son]` o pencerenin
    kayitlaridir. G17: dilimdeki oranlardan biri sayi degilse ya da sonlu degilse deger NaN (ortalama hesaplanmaz;
    NaN atlayan `mean` kullanilmaz). Ortalama skalerin `Series.mean`i ile ayni cekirdektir (`add.reduce / n`); dilim
    uzunlugu t'ye gore degistigi icin satir satir hesaplanir.

    Zaman dizisi: saat dilimsiz odeme zamani ve (izgaranin son kapanisina kadarki kayitlarda) sirasiz ya da tekrarli
    damga `ZamanDizisiHatasi` (skalerle ayni sinif)."""
    z = _utc_izgara(izgara, config.BAR_4H)
    sonuc = np.full(len(z), np.nan)
    ham = pd.DatetimeIndex(funding["odeme_zamani"])
    if len(ham) and ham.tz is None:
        raise pencere_modulu.ZamanDizisiHatasi(
            "funding_ortalamasi: odeme zamanlari saat dilimsiz (tz-naive); tum zaman damgalari UTC olmali.")
    if len(z) == 0:
        return sonuc
    son_kapanis = z[-1] + _DORT_SAAT
    gecmis = funding.loc[np.asarray(pencere_modulu.ayni_ya_da_once(ham, son_kapanis), dtype=bool)].reset_index(
        drop=True)
    a = funding_modulu.sinyal_penceresi_ayrintisi(
        gecmis, z, config.BAR_4H, saat=config.H2_FUNDING_PENCERESI_SAAT, kume_baslangic=kume_baslangic,
        kume_bitis=kume_bitis, donem_baslangic=donem_baslangic)
    oran = pd.to_numeric(gecmis["oran_8h"], errors="coerce").to_numpy(dtype=float) if len(gecmis) else np.empty(0)
    hesap = a["hesaplanabilir"].to_numpy(dtype=bool)
    ilk = a["ilk"].to_numpy(dtype=np.int64)
    son = a["son"].to_numpy(dtype=np.int64)
    for j in np.nonzero(hesap)[0]:
        dilim = oran[ilk[j]:son[j] + 1]
        if np.isfinite(dilim).all():
            sonuc[j] = np.add.reduce(dilim) / len(dilim)
    return sonuc


def h3_hacim_medyani_30g(gunluk, izgara, *, kume_baslangic, donem_baslangic) -> np.ndarray:
    """Son 30 gunun medyan gunluk hacmi `[t-29 .. t]` (§5 H3 madde 1; t gunu DAHIL)."""
    z = _utc_izgara(izgara, config.BAR_1D)
    return pencere_serisi(mum_serisi(gunluk, "quote_volume"), z, config.H3_HACIM_YAKIN_GUN, config.BAR_1D,
                          islev="median", kume_baslangic=kume_baslangic, donem_baslangic=donem_baslangic)


def h3_hacim_medyani_120_31(gunluk, izgara, *, kume_baslangic, donem_baslangic) -> np.ndarray:
    """Gun -120 ile -31 arasi medyan hacim `[t-120 .. t-31]`, 90 gun (§5 H3 madde 1 rev.11). t-30 gunu hicbir
    pencereye girmez."""
    z = _utc_izgara(izgara, config.BAR_1D)
    return pencere_serisi(mum_serisi(gunluk, "quote_volume"), z - config.H3_HACIM_UZAK_OFSET * _BIR_GUN,
                          config.H3_HACIM_UZAK_GUN, config.BAR_1D, islev="median", kume_baslangic=kume_baslangic,
                          donem_baslangic=donem_baslangic)


def h3_sma50(gunluk, izgara, *, kume_baslangic, donem_baslangic) -> np.ndarray:
    """SMA50 `[t-49 .. t]`, kapanislarin basit ortalamasi (§5 rev.11; t gunu DAHIL)."""
    z = _utc_izgara(izgara, config.BAR_1D)
    return pencere_serisi(mum_serisi(gunluk, "close"), z, config.H3_SMA_GUN, config.BAR_1D, islev="mean",
                          kume_baslangic=kume_baslangic, donem_baslangic=donem_baslangic)


def kapanis(mumlar, izgara, bar: str) -> np.ndarray:
    """`close[t]` (skaler `bar_degeri(..., "close")`)."""
    return bar_degeri_serisi(mum_serisi(mumlar, "close"), _utc_izgara(izgara, bar))


def yuksek(mumlar, izgara, bar: str) -> np.ndarray:
    """`high[t]` (skaler `bar_degeri(..., "high")`)."""
    return bar_degeri_serisi(mum_serisi(mumlar, "high"), _utc_izgara(izgara, bar))


# --- Capasiz pencereler ve hesaplanabilirlik (on-kayit §6 rev.12) ------------------------------------------------

def capasiz_pencereler(hipotez: str, k, izgara, *, mumlar_4h, gunluk, funding, kume_baslangic, kume_bitis,
                       donem_baslangic) -> dict[str, np.ndarray]:
    """Hipotezin CAPASIZ sinyal pencereleri, izgaranin her barinda (dondurulmus referanstaki
    `capasiz_pencere_degerleri`). Kosullar DEGERLENDIRILMEZ. `k`: H2'de kirilim penceresinin uzunlugu (yapilandirmanin
    `k`si), H1 ve H3'te None."""
    sinir = {"kume_baslangic": kume_baslangic, "donem_baslangic": donem_baslangic}
    if hipotez == "H1":
        return {"dip": h1_dip(mumlar_4h, izgara, **sinir), "hacim_6": h1_hacim_6(mumlar_4h, izgara, **sinir),
                "hacim_medyani_180": h1_hacim_medyani_180(mumlar_4h, izgara, **sinir)}
    if hipotez == "H2":
        return {"kirilim_dip": h2_kirilim_dip(mumlar_4h, izgara, k, **sinir),
                "kapanis_30_once": kapanis_30_once(mumlar_4h, izgara, config.BAR_4H, **sinir),
                "funding_24s": h2_funding_24s(funding, izgara, kume_baslangic=kume_baslangic, kume_bitis=kume_bitis,
                                              donem_baslangic=donem_baslangic)}
    if hipotez == "H3":
        return {"hacim_medyani_30g": h3_hacim_medyani_30g(gunluk, izgara, **sinir),
                "hacim_medyani_120_31": h3_hacim_medyani_120_31(gunluk, izgara, **sinir),
                "sma50": h3_sma50(gunluk, izgara, **sinir),
                "kapanis_30_once": kapanis_30_once(gunluk, izgara, config.BAR_1D, **sinir)}
    raise ValueError(f"Bilinmeyen hipotez {hipotez!r}.")


def capasiz_hesaplanabilir(hipotez: str, pencereler: dict[str, np.ndarray]) -> np.ndarray:
    """Her barda capasiz pencerelerin TAMAMI sonlu mu (skaler `capasiz_hesaplanamayan` bos mu)?"""
    adlar = CAPASIZ_PENCERELER[hipotez]
    if set(pencereler) != set(adlar):
        raise TypeError(f"{hipotez} icin capasiz pencereler tam olarak {adlar} olmali.")
    return np.logical_and.reduce([np.isfinite(pencereler[a]) for a in adlar])


# --- Uygunluk (on-kayit §2; G7) ----------------------------------------------------------------------------------

def uygunluk(gunluk, izgara, bar: str, *, donem_baslangic, donem_bitis, kume_baslangic, asgari_hacim,
             asgari_listeleme_yasi_gun) -> pd.DataFrame:
    """Uygunluk, izgaranin her barinda (skaler `eligibility.uygunluk_karari`; G7).

    Tanim on-kayit §2'den: "Uygunluk (t anında…)" -- t donem ici olmali (§6 rev.8 "Donem uyeligi"; 1d barda gunun alti
    4h barinin tamami), listeleme yasi icinde bulunulan DONEMIN basindan olculur ve esigi gecmeli, medyan hacim
    hesaplanabilmis olmali VE esigi gecmeli. "Uygunluk penceresi ve t günü": hacim penceresi t'nin GUNUNU icermez,
    t'den once kapanmis son 30 TAM gundur; pencere donem basini ve kume basini asamaz, gunlerden biri eksikse
    hesaplanmaz (§2 rev.3, rev.11).

    Vektorel bicim: medyan UTC GUN basina bir kez hesaplanir ve o gunun barlarina dagitilir; listeleme yasi BAR basina
    olculur (`(t - donem_basi) / 1 gun`, skalerle ayni bolme; bit esitligi G6 testinde). Zaman toleransi (§4) butun
    zaman karsilastirmalarini kapsar ve donem uyeligi burada da toleransli yuklemle (`pencere.donem_ici_4h_maskesi`)
    olculur; donem basi ve t 4h izgarasinda oldugu icin tolerans bugun sonucu degistirmez (G7 gerekcesi).

    Doner: `medyan_hacim` (t'nin gunu icin; donem/yas kosulundan bagimsiz, NaN = hesaplanamadi), `listeleme_yasi_gun`,
    `donem_ici`, `uygun` (bool)."""
    eligibility_modulu.esikleri_dogrula(bar, asgari_hacim=asgari_hacim,
                                        asgari_listeleme_yasi_gun=asgari_listeleme_yasi_gun)
    z = _utc_izgara(izgara, bar)
    if donem_baslangic is None or donem_bitis is None:
        raise TypeError("donem sinirlari None olamaz (on-kayit §2 'Listeleme donemi').")
    donem_bas = pencere_modulu.utc_zamani(donem_baslangic, "donem_baslangic")
    donem_son = pencere_modulu.utc_zamani(donem_bitis, "donem_bitis")
    donem_ici = np.asarray(pencere_modulu.donem_ici_4h_maskesi(z, donem_baslangic=donem_bas, donem_bitis=donem_son),
                           dtype=bool)
    if bar == config.BAR_1D:
        donem_ici &= np.asarray(pencere_modulu.donem_ici_4h_maskesi(
            z + pencere_modulu.GUNUN_SON_4H_BARI, donem_baslangic=donem_bas, donem_bitis=donem_son), dtype=bool)
    yas = np.asarray((z - donem_bas) / pd.Timedelta(days=1), dtype=float)
    gunler = z.floor("D")
    essiz, ters = np.unique(np.asarray(gunler.asi8), return_inverse=True)
    essiz_gun = pd.DatetimeIndex(essiz, tz="UTC")
    medyan_gun = pencere_serisi(gunluk_hacim(gunluk), essiz_gun - _BIR_GUN, config.HACIM_PENCERESI_GUN,
                                config.BAR_1D, islev="median", kume_baslangic=kume_baslangic,
                                donem_baslangic=donem_bas)
    medyan = medyan_gun[ters] if len(z) else np.empty(0)
    with np.errstate(invalid="ignore"):
        uygun = donem_ici & (yas >= asgari_listeleme_yasi_gun) & ~np.isnan(medyan) & (medyan >= asgari_hacim)
    return pd.DataFrame({"medyan_hacim": medyan, "listeleme_yasi_gun": yas, "donem_ici": donem_ici,
                         "uygun": uygun}, index=z)
