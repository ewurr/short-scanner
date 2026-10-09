"""Hipotezlerin sinyal pencereleri, sinyal degerleri ve kosullari (on-kayit §5, rev.11).

Bu modul, on-kayit §5'teki her geriye bakis penceresinin TEK kurucusudur. Rev.11'den once
pencere sinirlari (hangi pencere t barini icerir, hangi pencere kac bardir) kodda hic yoktu:
`pozisyon.olay_karari` sinyal degerlerini cagirandan aliyordu ve her cagiran sinirlari kendisi
secmek zorundaydi. On-kayit §5 "Pencere sinirlari" (rev.4) ve "Pencere sinirlarinin tamami"
(rev.11) bu sinirlari yaziya dokmustur; bu modul onlari tek yerde uygular.

On-kayit §5 "Pencere sinirlari": "Her kosulun geriye bakis penceresinin t barini icerip
icermedigi ... uygulamada acikca belirtilir. ... Varsayilan davranis yoktur; belirtilmeyen
cagri hata verir." Bu yuzden hicbir kurucunun bar sayisi, t sinirlari ya da izgara parametresi
icin varsayilani yoktur: uzunluklar `config`teki on-kayit sabitlerinden gelir, kume ve donem
sinirlari zorunlu anahtar sozcuktur.

Butun pencereler on-kayit §2 "Tamlik sarti" kapsamindadir: beklenen barlardan biri bile
eksikse deger hesaplanmaz (NaN) ve o barda olay ya da kontrol olusmaz. Tamlik, donem ve kume
sinirlari `data.pencere`nin tek kapisindan (`pencere_dilimi`) gecer; bu modul kendi tamlik
kodunu yazmaz.

Izgara (on-kayit §5): "Izgara parametreleri (θ, δ, φ, k, ν, τ) yalnizca bu on-kayitta
tanimlidir ve kod bu degerleri tek bir yerden, on-kayit degeri olarak okur (rev.11). Olay ya da
kontrol ureten her cagri, hipotezi ve yapilandirmayi birlikte alir; izgarada bulunmayan bir
parametre demeti hata verir." Degerler `config.IZGARA`da; `yapilandirma_dogrula` demetin
izgarada bulundugunu denetler.

Bu modul tamamen saftir: ag veya disk kullanmaz. Getiri hesaplamaz.
"""

from __future__ import annotations

import itertools
import math
from types import MappingProxyType

import numpy as np
import pandas as pd

import config
from data import funding as funding_modulu
from data import pencere as pencere_modulu

# --- Izgara (on-kayit §5) ----------------------------------------------------

# Hipotez basina parametre adlari, on-kayitta yazili sirada.
PARAMETRELER = MappingProxyType({
    "H1": ("theta", "delta"),      # θ ∈ {0.20, 0.30, 0.40} × δ ∈ {0.08, 0.12, 0.16}
    "H2": ("phi", "k"),            # φ ∈ {0.03%, 0.05%, 0.10%} × k ∈ {3, 6, 12}
    "H3": ("nu", "tau"),           # ν ∈ {0.50, 0.65, 0.80} × τ ∈ {0.15, 0.25, 0.35}
})


class YapilandirmaHatasi(ValueError):
    """Izgarada bulunmayan bir parametre demeti (on-kayit §5 rev.11)."""


def izgara(hipotez) -> tuple[MappingProxyType, ...]:
    """Hipotezin kesif izgarasi: 9 yapilandirma, parametre adlarina gore eslem.

    On-kayit §5: "Her hipotezin kesif izgarasi en fazla 9 yapilandirmadir." Sira on-kayittaki
    parametre sirasina gore kartezyen carpimdir; deterministiktir.
    """
    ad = _hipotez_dogrula(hipotez)
    adlar = PARAMETRELER[ad]
    degerler = [config.IZGARA[ad][p] for p in adlar]
    return tuple(MappingProxyType(dict(zip(adlar, demet))) for demet in itertools.product(*degerler))


def _hipotez_dogrula(hipotez) -> str:
    if not isinstance(hipotez, str) or type(hipotez) is not str:
        raise TypeError(f"hipotez bir str olmali (on-kayit §5: 'H1', 'H2', 'H3'): {hipotez!r}")
    if hipotez not in config.HIPOTEZLER:
        raise ValueError(f"Bilinmeyen hipotez {hipotez!r}; on-kayit §5: {config.HIPOTEZLER}.")
    return hipotez


def yapilandirma_dogrula(hipotez, yapilandirma) -> MappingProxyType:
    """Yapilandirma izgarada mi? Izgaradaki esleme (degismez) doner, degilse `YapilandirmaHatasi`.

    On-kayit §5 (rev.11): "Olay ya da kontrol ureten her cagri, hipotezi ve yapilandirmayi
    birlikte alir; izgarada bulunmayan bir parametre demeti hata verir." Denetim deger
    duzeyindedir: adlar tam olarak hipotezin parametreleri olmali ve degerler izgaradaki bir
    demete BIREBIR esit olmali. Yuvarlanmis ya da yaklasik bir deger (ör. θ = 0.2000001)
    izgarada degildir.
    """
    ad = _hipotez_dogrula(hipotez)
    adlar = PARAMETRELER[ad]
    if isinstance(yapilandirma, (tuple, list)):
        if len(yapilandirma) != len(adlar):
            raise YapilandirmaHatasi(f"{ad} yapilandirmasi {len(adlar)} parametre tasir {adlar}; "
                                     f"verilen {len(yapilandirma)}.")
        yapilandirma = dict(zip(adlar, yapilandirma))
    if not isinstance(yapilandirma, (dict, MappingProxyType)):
        try:
            yapilandirma = dict(yapilandirma)
        except TypeError:
            raise TypeError(f"yapilandirma bir eslem ya da demet olmali: {yapilandirma!r}") from None
    if set(yapilandirma) != set(adlar):
        raise YapilandirmaHatasi(
            f"{ad} yapilandirmasi tam olarak {adlar} parametrelerini tasimali; eksik "
            f"{sorted(set(adlar) - set(yapilandirma))}, fazla {sorted(set(yapilandirma) - set(adlar))} "
            "(on-kayit §5 rev.11).")
    for p, deger in yapilandirma.items():
        if isinstance(deger, bool) or not isinstance(deger, (int, float, np.integer, np.floating)):
            raise YapilandirmaHatasi(f"{ad}.{p} sayisal bir izgara degeri olmali: {deger!r}")
    for aday in izgara(ad):
        if all(float(yapilandirma[p]) == float(aday[p]) for p in adlar):
            return aday
    raise YapilandirmaHatasi(
        f"{ad} icin {dict(yapilandirma)} izgarada yok (on-kayit §5 rev.11). Izgara: "
        f"{[dict(y) for y in izgara(ad)]}.")


def yapilandirma_kimligi(hipotez, yapilandirma) -> str:
    """Yapilandirmanin deterministik kimligi: `H2:phi=0.0005,k=6`. Tohum ve dosya adlarinda kullanilir."""
    ad = _hipotez_dogrula(hipotez)
    gecerli = yapilandirma_dogrula(ad, yapilandirma)
    return f"{ad}:" + ",".join(f"{p}={_sayi_metni(gecerli[p])}" for p in PARAMETRELER[ad])


def _sayi_metni(deger) -> str:
    if float(deger).is_integer():
        return str(int(deger))
    return repr(float(deger))


# --- Seri yardimcilari -------------------------------------------------------


def _seri(mumlar: pd.DataFrame, alan: str) -> pd.Series:
    """Mum cercevesinin bir alanini, acilis zamaniyla indekslenmis seri olarak doner. Saf.

    Alan sayisal degilse (string, nesne) `pd.to_numeric` NaN uretir; SONLU OLMAYAN deger
    (+-sonsuz) de NaN'a cevrilir. On-kayit §2 (rev.11): "Bir barin mevcut sayilmasi icin
    satirinin bulunmasi yetmez: fiyat ve hacim hucrelerinin tamami sayi olmalidir. Hucrelerinden
    biri NaN ya da sonlu degilse o bar eksiktir"; §2 "Tamlik sarti" eksik bari iceren pencereyi
    hesaplanamaz yapar. Boylece sonsuz bir hucre pencereden sessizce gecmez ve degerler
    sessizce 0 ya da metin olarak toplanmaz. (On-kayit cumlesi 1d barlarin kurulusu baglaminda
    yazilidir; burada ayni olcut 4h ve 1d sinyal pencerelerine de uygulanir. F1 olcumunde donem
    ici 4h barlarda boyle bir hucre bulunmamistir.)
    """
    if alan not in mumlar:
        raise KeyError(f"Mum cercevesinde {alan!r} sutunu yok (sinyal penceresi kurulamaz).")
    degerler = pd.to_numeric(mumlar[alan], errors="coerce").to_numpy(dtype=float)
    degerler = np.where(np.isfinite(degerler), degerler, np.nan)
    seri = pd.Series(degerler, index=pd.DatetimeIndex(mumlar["open_time"]))
    return seri.sort_index()


def bar_degeri(mumlar: pd.DataFrame, t, alan: str) -> float:
    """t barinin `alan` degeri; bar yoksa ya da deger sonlu degilse NaN. Saf.

    On-kayit §2 (rev.11): "Bir barin mevcut sayilmasi icin satirinin bulunmasi yetmez: fiyat ve
    hacim hucrelerinin tamami sayi olmalidir." Sinyal kosullari t barinin kendi `close` ve
    `high` degerlerini okur; o hucre eksikse deger hesaplanmaz.
    """
    zaman = pencere_modulu.utc_zamani(t, "t")
    seri = _seri(mumlar, alan)
    bar = pencere_modulu.ayni_andaki_bar(pd.DatetimeIndex(seri.index), zaman)
    if bar is None:
        return float("nan")
    deger = float(seri.loc[bar])
    return deger if math.isfinite(deger) else float("nan")


# --- H1 pencereleri (on-kayit §5 H1) ----------------------------------------


def h1_dip(mumlar_4h: pd.DataFrame, t, *, kume_baslangic, donem_baslangic) -> float:
    """`min(low[t-6..t-1])` (on-kayit §5 H1 madde 1).

    Pencere t barini ICERMEZ (§5 "Pencere sinirlari": "H1'in 6 barlik dip penceresi ... t'yi
    icermez (t-6..t-1)"). Uzunluk `config.H1_DIP_BAR` = 6.
    """
    return pencere_modulu.pencere_degeri(
        _seri(mumlar_4h, "low"), t, config.H1_DIP_BAR, config.BAR_4H, t_dahil=False,
        kume_baslangic=kume_baslangic, donem_baslangic=donem_baslangic, islev="min")


def h1_hacim_6(mumlar_4h: pd.DataFrame, t, *, kume_baslangic, donem_baslangic) -> float:
    """"Son 6 barin toplam hacmi" (on-kayit §5 H1 madde 1).

    Pencere t barini ICERIR (§5 "Pencere sinirlari": "6 barlik toplam pencereleri t barini
    icerir"), yani `[t-5 .. t]`, `config.H1_HACIM_TOPLAM_BAR` = 6 bar. Hacim = quote hacmi
    (on-kayit §2 "Uygunluk" ile ayni hacim tanimi: USDT cinsinden islem hacmi).
    """
    return pencere_modulu.pencere_degeri(
        _seri(mumlar_4h, "quote_volume"), t, config.H1_HACIM_TOPLAM_BAR, config.BAR_4H, t_dahil=True,
        kume_baslangic=kume_baslangic, donem_baslangic=donem_baslangic, islev="sum")


def h1_hacim_medyani_180(mumlar_4h: pd.DataFrame, t, *, kume_baslangic, donem_baslangic) -> float:
    """"Onceki 180 barin 6'li toplam hacim medyani" (on-kayit §5 H1 madde 1).

    "H1'in 6'li toplam hacim medyani kayan pencereyle hesaplanir: her bar icin son 6 barin
    toplami alinir ve bu toplamlarin 180 barlik medyani kullanilir. Ardisik, cakismayan
    bloklara bolunmez." Dis pencere t barini ICERIR (§5 "Pencere sinirlari": "H1'in 180 barlik
    hacim medyani t barini icerir"), yani `[t-179 .. t]`, `config.H1_HACIM_MEDYAN_BAR` = 180 dis
    bar; her dis barin ic penceresi o bari iceren 6 barlik toplamdir. Ic pencerelerin birlesimi
    (`[t-184 .. t]`) tek parca olarak tamlik, donem ve kume kapisindan gecer
    (`pencere.ic_ice_pencere_degeri`).
    """
    return pencere_modulu.ic_ice_pencere_degeri(
        _seri(mumlar_4h, "quote_volume"), t, config.BAR_4H,
        dis_bar_sayisi=config.H1_HACIM_MEDYAN_BAR, dis_t_dahil=True, dis_islev="median",
        ic_bar_sayisi=config.H1_HACIM_TOPLAM_BAR, ic_t_dahil=True, ic_islev="sum",
        kume_baslangic=kume_baslangic, donem_baslangic=donem_baslangic)


def h1_tepe_bar_sayisi(pump_bari, teyit_bari) -> int:
    """Tepe penceresinin bar sayisi: pump barindan teyit barinin BIR ONCESINE kadar (dahil).

    On-kayit §5 H1 madde 2 (rev.11): "Tepe: pump bari dahil, teyit barindan bir onceki bara
    kadar gorulen en yuksek `high`; en fazla 12 bar izlenir. Teyit barinin kendi `high` degeri
    tepeye girmez." Teyit bari pump barindan sonra ve en fazla
    `config.H1_IZLEME_BAR` = 12 bar sonra olmalidir (madde 3: "pump barindan sonraki 12 bar
    icinde"); aksi hali programlama hatasidir.
    """
    pump = pencere_modulu.utc_zamani(pump_bari, "pump_bari")
    teyit = pencere_modulu.utc_zamani(teyit_bari, "teyit_bari")
    adim = pencere_modulu.adim(config.BAR_4H)
    fark = teyit - pump
    if fark % adim != pd.Timedelta(0):
        raise ValueError(f"teyit bari {teyit} pump barinin ({pump}) 4h izgarasinda degil.")
    sayi = int(fark / adim)
    if sayi < 1:
        raise ValueError(f"teyit bari ({teyit}) pump barindan ({pump}) sonra olmali (on-kayit §5 H1 madde 3).")
    if sayi > config.H1_IZLEME_BAR:
        raise ValueError(f"teyit bari pump barindan {sayi} bar sonra; on-kayit §5 H1 madde 3 en fazla "
                         f"{config.H1_IZLEME_BAR} bar izler.")
    return sayi


def h1_tepe(mumlar_4h: pd.DataFrame, pump_bari, teyit_bari, *, kume_baslangic, donem_baslangic) -> float:
    """Tepe: `max(high[pump .. teyit-1])` (on-kayit §5 H1 madde 2, rev.11).

    Pencere pump barini ICERIR ve teyit barini ICERMEZ. "Tepe penceresi §2 'Tamlik sarti'
    kapsamindadir: pump barindan teyit barinin bir oncesine kadar beklenen barlardan biri bile
    eksikse tepe hesaplanmaz ve olay olusmaz."
    """
    sayi = h1_tepe_bar_sayisi(pump_bari, teyit_bari)
    return pencere_modulu.pencere_degeri(
        _seri(mumlar_4h, "high"), teyit_bari, sayi, config.BAR_4H, t_dahil=False,
        kume_baslangic=kume_baslangic, donem_baslangic=donem_baslangic, islev="max")


# --- H2 pencereleri (on-kayit §5 H2) ----------------------------------------


def kapanis_30_once(mumlar: pd.DataFrame, t, bar: str, *, kume_baslangic, donem_baslangic) -> float:
    """`close[t-30]`; tamlik penceresi `[t-30 .. t]` = 31 bar (on-kayit §5 rev.11).

    "`close[t-30]` iki uclu bir orandir: t'den 30 × adim onceki barin kapanisi. Tamlik penceresi
    kapali araliktir: `[t-30 .. t]`, yani 31 bar; araliktaki beklenen barlardan biri bile
    eksikse deger hesaplanmaz. Bu, H2'nin 30 barlik yukselis penceresi ile H3'un dusus trendi
    orani icin aynidir." Uzunluk `config.OTUZ_BAR_ONCE` = 30 adim, tamlik 31 bar.
    """
    dilim = pencere_modulu.pencere_dilimi(
        _seri(mumlar, "close"), t, config.OTUZ_BAR_ONCE + 1, bar, t_dahil=True,
        kume_baslangic=kume_baslangic, donem_baslangic=donem_baslangic)
    if dilim is None or dilim.isna().any():
        return float("nan")
    return float(dilim.iloc[0])


def h2_kirilim_dip(mumlar_4h: pd.DataFrame, t, k, *, kume_baslangic, donem_baslangic) -> float:
    """`min(low[t-k..t-1])` (on-kayit §5 H2 madde 3).

    Pencere t barini ICERMEZ (§5 "Pencere sinirlari": "H2'nin k barlik kirilim penceresi t'yi
    icermez (t-k..t-1)") ve k bardir. `k` izgara degeri olmali (on-kayit §5 rev.11).
    """
    gecerli = _izgara_degeri("H2", "k", k)
    return pencere_modulu.pencere_degeri(
        _seri(mumlar_4h, "low"), t, int(gecerli), config.BAR_4H, t_dahil=False,
        kume_baslangic=kume_baslangic, donem_baslangic=donem_baslangic, islev="min")


def h2_funding_24s(funding: pd.DataFrame, t, *, kume_baslangic, kume_bitis, donem_baslangic) -> float:
    """Son 24 saatteki 8 saate normallestirilmis funding ortalamasi (on-kayit §5 H2 madde 1).

    Pencere kurallari `funding.funding_ortalamasi`dir (on-kayit §4 "Funding sinyal penceresinin
    tamligi"); bu modul ortalamayi kendisi kurmaz. Pencere t barinin kapanisinda biter ve
    `config.H2_FUNDING_PENCERESI_SAAT` = 24 saat geriye uzanir.
    """
    return funding_modulu.funding_ortalamasi(
        funding, t, config.BAR_4H, saat=config.H2_FUNDING_PENCERESI_SAAT,
        kume_baslangic=kume_baslangic, kume_bitis=kume_bitis, donem_baslangic=donem_baslangic)


# --- H3 pencereleri (on-kayit §5 H3) ----------------------------------------


def h3_hacim_medyani_30g(gunluk: pd.DataFrame, t, *, kume_baslangic, donem_baslangic) -> float:
    """"Son 30 gunun medyan gunluk hacmi" (on-kayit §5 H3 madde 1).

    Pencere t gununu ICERIR (§5 rev.11: "'son 30 gun' t gununu icerir (`[t-29 .. t]`)"),
    uzunluk `config.H3_HACIM_YAKIN_GUN` = 30. Bu pencere uygunluk hacminden AYRIDIR: uygunluk
    penceresi t gununu disarida birakir (on-kayit §2 "Uygunluk penceresi ve t gunu").
    """
    return pencere_modulu.pencere_degeri(
        _seri(gunluk, "quote_volume"), t, config.H3_HACIM_YAKIN_GUN, config.BAR_1D, t_dahil=True,
        kume_baslangic=kume_baslangic, donem_baslangic=donem_baslangic, islev="median")


def h3_hacim_medyani_120_31(gunluk: pd.DataFrame, t, *, kume_baslangic, donem_baslangic) -> float:
    """"Gun -120 ile -31 arasindaki medyan gunluk hacim" (on-kayit §5 H3 madde 1).

    §5 rev.11: "'gun −120 ile −31 arasi' t gunune gore sayilir (`[t-120 .. t-31]`, 90 gun). Iki
    pencere arasindaki t-30 gunu hicbir pencereye girmez; bu, yazili sayilarin dogrudan
    sonucudur ve bilerek korunmustur." Uzunluk `config.H3_HACIM_UZAK_GUN` = 90,
    bitis ofseti `config.H3_HACIM_UZAK_OFSET` = 31.
    """
    return pencere_modulu.ofsetli_pencere_degeri(
        _seri(gunluk, "quote_volume"), t, config.H3_HACIM_UZAK_GUN, config.BAR_1D,
        bitis_ofseti=config.H3_HACIM_UZAK_OFSET, islev="median",
        kume_baslangic=kume_baslangic, donem_baslangic=donem_baslangic)


def h3_sma50(gunluk: pd.DataFrame, t, *, kume_baslangic, donem_baslangic) -> float:
    """SMA50: son 50 gunun kapanis ortalamasi, t gunu DAHIL (on-kayit §5 rev.11).

    "SMA50, 1 gunluk seride son 50 gunun kapanislarinin basit ortalamasidir ve t gununu icerir
    (`[t-49 .. t]`)." Uzunluk `config.H3_SMA_GUN` = 50.
    """
    return pencere_modulu.pencere_degeri(
        _seri(gunluk, "close"), t, config.H3_SMA_GUN, config.BAR_1D, t_dahil=True,
        kume_baslangic=kume_baslangic, donem_baslangic=donem_baslangic, islev="mean")


# --- Izgara degeri yardimcisi ------------------------------------------------


def _izgara_degeri(hipotez: str, parametre: str, deger):
    """Tek bir parametrenin izgarada bulundugunu denetler; izgaradaki degeri doner."""
    gecerli = config.IZGARA[hipotez][parametre]
    for aday in gecerli:
        if not isinstance(deger, bool) and isinstance(deger, (int, float, np.integer, np.floating)) \
                and float(deger) == float(aday):
            return aday
    raise YapilandirmaHatasi(f"{hipotez}.{parametre} = {deger!r} izgarada yok; on-kayit §5: {gecerli}.")
# --- Sinyal degerleri ve kosullari (on-kayit §5; Rev.11 uygulamasi madde 4) -------------------
#
# Rev.11'den once `pozisyon.olay_karari` bu degerleri CAGIRANDAN aliyordu (F1 kapanis bulgusu
# D-B1). On-kayit §5 "Pencere sinirlari" ve "Pencere sinirlarinin tamami" (rev.11) butun
# sinirlari yaziya dokunce kapi degerleri kendisi hesaplayabilir hale geldi. Asagidaki iki
# fonksiyon kapinin kullandigi tek yoldur: `deger_adlari` + `sinyal_degerleri` (pencere ve bar
# degerleri) ve `kosullar_saglandi` (§5'teki esik karsilastirmalari).

# Hipotez basina hesaplanan deger adlari. Pencere degerleri on-kayit §5'teki kosullarin geriye
# bakis pencereleridir; `kapanis` ve `yuksek` t barinin KENDI hucreleridir ve kosullarda okunur
# (on-kayit §5 H1 madde 3 `close`/`high`, H2 madde 2-3 `close[t]`, H3 madde 2 `close[t]`).
# `pump_kapanis` H1'in pump barinin kapanisidir (madde 1).
DEGER_ADLARI = MappingProxyType({
    "H1": ("pump_dip", "pump_hacim_6", "pump_hacim_medyani_180", "tepe", "pump_kapanis", "kapanis", "yuksek"),
    "H2": ("funding_24s", "kapanis_30_once", "kirilim_dip", "kapanis"),
    "H3": ("hacim_medyani_30g", "hacim_medyani_120_31", "sma50", "kapanis_30_once", "kapanis"),
})

# H1'in sinyali bir pump barina capalidir (on-kayit §5 H1; §6 rev.11 gerekcesi). Yalnizca H1
# capa alir; H2 ve H3'un butun degerleri t barindan hesaplanir.
CAPALI_HIPOTEZLER = ("H1",)


def deger_adlari(hipotez) -> tuple[str, ...]:
    return DEGER_ADLARI[_hipotez_dogrula(hipotez)]


def sinyal_degerleri(hipotez, yapilandirma, t, *, mumlar_4h, gunluk, funding, capa,
                     kume_baslangic, kume_bitis, donem_baslangic) -> dict[str, float]:
    """Hipotezin butun sinyal degerleri (ad -> deger); hesaplanamayan deger NaN'dir. Saf.

    Butun pencereler bu modulun kuruculari uzerinden gecer, yani on-kayit §5'teki sinirlar ve
    §2 "Tamlik sarti" her degerde uygulanir. `capa`: H1'in pump bari (zorunlu); H2 ve H3'te
    `None` olmalidir. Sinirlar zorunlu anahtar sozcuktur; donem basi None olamaz, kume siniri
    yoksa acikca None.

    Izgara: H2'nin `k` parametresi `kirilim_dip` penceresinin uzunlugudur, bu yuzden
    yapilandirma degerler hesaplanirken de gereklidir (on-kayit §5 rev.11: "Olay ya da kontrol
    ureten her cagri, hipotezi ve yapilandirmayi birlikte alir").
    """
    ad = _hipotez_dogrula(hipotez)
    y = yapilandirma_dogrula(ad, yapilandirma)
    sinir = {"kume_baslangic": kume_baslangic, "donem_baslangic": donem_baslangic}
    if (capa is not None) != (ad in CAPALI_HIPOTEZLER):
        raise ValueError(
            f"{ad} icin capa {'zorunludur' if ad in CAPALI_HIPOTEZLER else 'verilemez'} "
            "(on-kayit §5 H1: sinyal pump barina capalidir; H2 ve H3 t barindan hesaplanir).")

    if ad == "H1":
        return {
            "pump_dip": h1_dip(mumlar_4h, capa, **sinir),
            "pump_hacim_6": h1_hacim_6(mumlar_4h, capa, **sinir),
            "pump_hacim_medyani_180": h1_hacim_medyani_180(mumlar_4h, capa, **sinir),
            "tepe": h1_tepe(mumlar_4h, capa, t, **sinir),
            "pump_kapanis": bar_degeri(mumlar_4h, capa, "close"),
            "kapanis": bar_degeri(mumlar_4h, t, "close"),
            "yuksek": bar_degeri(mumlar_4h, t, "high"),
        }
    if ad == "H2":
        return {
            "funding_24s": h2_funding_24s(funding, t, kume_baslangic=kume_baslangic, kume_bitis=kume_bitis,
                                          donem_baslangic=donem_baslangic),
            "kapanis_30_once": kapanis_30_once(mumlar_4h, t, config.BAR_4H, **sinir),
            "kirilim_dip": h2_kirilim_dip(mumlar_4h, t, y["k"], **sinir),
            "kapanis": bar_degeri(mumlar_4h, t, "close"),
        }
    return {
        "hacim_medyani_30g": h3_hacim_medyani_30g(gunluk, t, **sinir),
        "hacim_medyani_120_31": h3_hacim_medyani_120_31(gunluk, t, **sinir),
        "sma50": h3_sma50(gunluk, t, **sinir),
        "kapanis_30_once": kapanis_30_once(gunluk, t, config.BAR_1D, **sinir),
        "kapanis": bar_degeri(gunluk, t, "close"),
    }


def hesaplanamayan(hipotez, degerler) -> list[str]:
    """Hesaplanamayan (sonlu olmayan) deger adlari. On-kayit §2 "Tamlik sarti": biri bile
    hesaplanamazsa o barda olay ya da kontrol olusmaz. Saf."""
    ad = _hipotez_dogrula(hipotez)
    gereken = DEGER_ADLARI[ad]
    if set(degerler) != set(gereken):
        raise TypeError(f"{ad} icin degerler tam olarak {gereken} olmali; eksik "
                        f"{sorted(set(gereken) - set(degerler))}, fazla {sorted(set(degerler) - set(gereken))}.")
    return [a for a in gereken if not _sonlu(degerler[a])]


def _sonlu(deger) -> bool:
    if isinstance(deger, (bool, np.bool_)) or deger is None:
        return False
    if not isinstance(deger, (int, float, np.integer, np.floating)):
        return False
    return math.isfinite(float(deger))


def kosullar_saglandi(hipotez, yapilandirma, degerler) -> bool:
    """Hipotezin §5'teki sinyal kosullari bu barda saglandi mi? Saf.

    Butun degerler hesaplanmis olmali (`hesaplanamayan` bos); aksi halde ValueError. Kosullar
    on-kayit §5'ten birebir:
      - H1 (madde 1 + 3): pump barinda `close/dip - 1 >= θ` ve `hacim_6 >= 3 × medyan_180`;
        teyit barinda `close <= tepe × (1 - δ)` ve `high < tepe`.
      - H2 (madde 1-3): `funding_24s >= φ`, `close[t]/close[t-30] - 1 >= 0.10`,
        `close[t] < min(low[t-k..t-1])`.
      - H3 (madde 1-2): `medyan_30g <= (1 - ν) × medyan_120_31`, `close[t] < SMA50[t]`,
        `close[t]/close[t-30] - 1 <= -τ`.
    Esik yonleri ve esitlik durumlari on-kayitta yazildigi gibidir: H1 ve H2'nin yukselis
    esikleri ">=", H1'in teyidi "<=", H1'in `high < tepe` ve H2'nin kirilimi kesin "<",
    H3'un hacim ve trend kosullari "<=".
    """
    ad = _hipotez_dogrula(hipotez)
    y = yapilandirma_dogrula(ad, yapilandirma)
    eksik = hesaplanamayan(ad, degerler)
    if eksik:
        raise ValueError(f"{ad} kosullari hesaplanamayan degerle sinanamaz: {eksik} "
                         "(on-kayit §2 'Tamlik sarti'; once tamlik denetlenir).")
    d = {a: float(degerler[a]) for a in DEGER_ADLARI[ad]}
    if ad == "H1":
        _pozitif(d["pump_dip"], "pump dibi min(low[p-6..p-1])")
        pump = (d["pump_kapanis"] / d["pump_dip"] - 1 >= float(y["theta"])
                and d["pump_hacim_6"] >= config.H1_HACIM_CARPANI * d["pump_hacim_medyani_180"])
        teyit = d["kapanis"] <= d["tepe"] * (1 - float(y["delta"])) and d["yuksek"] < d["tepe"]
        return bool(pump and teyit)
    if ad == "H2":
        _pozitif(d["kapanis_30_once"], "close[t-30]")
        return bool(d["funding_24s"] >= float(y["phi"])
                    and d["kapanis"] / d["kapanis_30_once"] - 1 >= config.H2_YUKSELIS_ESIGI
                    and d["kapanis"] < d["kirilim_dip"])
    _pozitif(d["kapanis_30_once"], "close[t-30]")
    return bool(d["hacim_medyani_30g"] <= (1 - float(y["nu"])) * d["hacim_medyani_120_31"]
                and d["kapanis"] < d["sma50"]
                and d["kapanis"] / d["kapanis_30_once"] - 1 <= -float(y["tau"]))


def _pozitif(deger: float, ad: str) -> float:
    """On-kayit §5'teki oranlarin bolenleri pozitif bir FIYAT olmalidir; sifir ya da negatif bir
    fiyat bozuk veridir ve acik hata verir (`pencere.VeriHatasi`). Kapi bir olay-olusmaz kurali
    ICAT ETMEZ: on-kayit sifir ya da negatif fiyati tanimlamaz (Rev.9 D-C5 ile ayni tutum,
    `pozisyon._sonlu`). Veri denetlenmelidir."""
    if deger <= 0:
        raise pencere_modulu.VeriHatasi(
            f"{ad} pozitif bir fiyat olmali; verilen {deger!r}. On-kayit §5'teki oran bu degerle "
            "tanimsiz olurdu ve kapi kural icat etmez: veri denetlenmeli.")
    return deger


# --- H1'in pump kosulu, teyit barindan bagimsiz (on-kayit §5 H1 madde 1) ----------------------
#
# H1'in sinyali iki adimdir: pump bari (madde 1) ve teyit bari (madde 3). Tepe penceresi teyit
# barina kadar uzandigi icin `sinyal_degerleri` ancak teyit bari BILINDIGINDE hesaplanabilir.
# Izleme kurallari (on-kayit §5 H1 madde 4; `data.dizi`) bir bari pump bari olarak TANIMAK icin
# yalnizca madde 1'e ihtiyac duyar; asagidaki iki fonksiyon o adimdir.

H1_PUMP_ADLARI = ("pump_dip", "pump_hacim_6", "pump_hacim_medyani_180", "pump_kapanis")


def h1_pump_degerleri(mumlar_4h, t, *, kume_baslangic, donem_baslangic) -> dict[str, float]:
    """H1'in pump kosulunun (madde 1) degerleri, t barinda. Saf; hesaplanamayan deger NaN."""
    sinir = {"kume_baslangic": kume_baslangic, "donem_baslangic": donem_baslangic}
    return {
        "pump_dip": h1_dip(mumlar_4h, t, **sinir),
        "pump_hacim_6": h1_hacim_6(mumlar_4h, t, **sinir),
        "pump_hacim_medyani_180": h1_hacim_medyani_180(mumlar_4h, t, **sinir),
        "pump_kapanis": bar_degeri(mumlar_4h, t, "close"),
    }


def h1_pump_saglandi(yapilandirma, degerler) -> bool | None:
    """Pump kosulu saglandi mi? Degerlerden biri hesaplanamiyorsa `None` (on-kayit §2 "Tamlik
    sarti"; `data.dizi` bunu "hesaplanamaz" yaniti olarak okur). Saf.

    Kosul (on-kayit §5 H1 madde 1): `close[t] / min(low[t-6..t-1]) - 1 >= θ` ve son 6 barin
    toplam hacmi >= 3 x onceki 180 barin 6'li toplam hacim medyani.
    """
    y = yapilandirma_dogrula("H1", yapilandirma)
    if any(not _sonlu(degerler[a]) for a in H1_PUMP_ADLARI):
        return None
    d = {a: float(degerler[a]) for a in H1_PUMP_ADLARI}
    _pozitif(d["pump_dip"], "pump dibi min(low[t-6..t-1])")
    return bool(d["pump_kapanis"] / d["pump_dip"] - 1 >= float(y["theta"])
                and d["pump_hacim_6"] >= config.H1_HACIM_CARPANI * d["pump_hacim_medyani_180"])
