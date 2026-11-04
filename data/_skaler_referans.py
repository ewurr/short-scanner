"""F2 oncesi skaler karar yolunun DONDURULMUS REFERANSI (performans 2a, plan v2 karar 3).

BU MODUL DEGISTIRILMEZ. Dosyanin SHA256'si `tests/test_skaler_referans.py` icinde sabittir; tek bir bayt
degisirse test kirmizi olur. Yalnizca su yerler kullanir:
  - esitlik testleri (`tests/`),
  - gercek veri esitlik betigi (`analysis/00_veri_denetimi/esitlik_*.py`),
  - F3 golge kosusu (plan v2 karar 7, D-B6: F3'te vektorel yol birincil, bu referans golgedir; uyusmazlik
    "GECERSIZ: uygulama hatasi" hukmu verir. Kural F3 planinda kesinlesir).
Analiz kodu taramasi bu modulun adini yasaklar (`tests/tarama_yardimcisi.SKALER_REFERANS_DESENI`); istisnalar
`tests/` ve `analysis/00_veri_denetimi/esitlik_*.py`dir.

Neden var: performans 2 turlari (P2a-P2d) tek kapiyi (`pozisyon.olay_karari`) seri hesaba tasiyacak. Tasima
sirasinda "bugunku karar ne idi?" sorusunun cevabi degisen kodun icinde kalirsa esitlik kanitlanamaz. Bu modul
o cevabi 4e63037 commit'indeki haliyle dondurur.

ICERIK. `data/pencere.py`, `data/funding.py`, `data/eligibility.py`, `data/sinyal.py` ve `data/pozisyon.py`
dosyalarindan, `pozisyon.olay_karari` ve `pozisyon.sinyal_kosulu`nun gecisli cagri grafigindeki KURAL
fonksiyonlari ve sabitleri 4e63037 commit'inden metin olarak, kaynak sirasiyla kopyalanmistir (asagidaki
bolumler). Bes modulun takma adlari (`pencere_modulu`, `sinyal_modulu`, `funding_modulu`,
`eligibility_modulu`) BU MODULUN KENDISINI gosterir; yani kopyalanan her fonksiyon digerlerinin KOPYASINI
cagirir, `data/`daki (degisecek) asillarini degil.

Metinde yapilan uc mekanik degisiklik (baska hicbir degisiklik yoktur):
  1. `data/funding.py` fonksiyonlarinin govdesindeki `from data import pencere as pencere_modulu` satirlari
     silindi. Aksi halde `funding.sinyal_penceresi_ayrintisi` kopyalanan `donem_siniri` ve `sinir_zamani`
     fonksiyonlarinin asillarini cagirirdi.
  2. `data/sinyal.py`deki `_sonlu(deger) -> bool`, `data/pozisyon.py`deki `_sonlu(deger, ad) -> float` ile ayni
     adi tasir; sinyal kopyasinda `_sinyal_sonlu` adini aldi (tanim ve cagrilar).
  3. `olay_karari` donen `OnaylanmisPozisyon`u IMZALAMAZ (`_imza` = 0). Referans ikinci bir onay kaynagi
     degildir: ciktisi `pozisyon.onay_dogrula`dan gecemez, yani getiri tarafina giremez. Alan esitligi
     (`==`) imzaya bakmaz (`_imza` alani `compare=False`), bu yuzden esitlik karsilastirmasi etkilenmez.

DAYANILAN (kopyalanmayan) adlar. Bunlar kural degil; veri yolu, erisim denetimi, zaman toleransi, siniflar:
  - `config` (on-kayit sabitleri; kendi degismezlik korumasi var).
  - `data.pencere`: zaman toleransi yardimcilari (`ayni_an`, `sonra`, `once`, `ayni_ya_da_once`,
    `ayni_ya_da_sonra`, `ayni_an_sonu`, `ayni_an_basi`, `ODEME_TOLERANSI`), izgara adimi (`adim`, `ADIMLAR`,
    `ADIM_4H`), zaman dogrulamasi (`utc_zamani`, `_zaman_dizisi_dogrula`), plan imzasi (`_plan_imzasi`,
    `plan_dogrula`), siniflar (`OlayOlusmaz`, `KumeSiniriHatasi`, `IleriKaymaSiniriHatasi`, `DonemDisiSinyal`,
    `GirisBariYok`, `VeriHatasi`, `ZamanDizisiHatasi`, `CikisSonucu`, `PozisyonPlani`, `HipotezUfuklari`).
  - `data.sinyal`: siniflar `TepePenceresiKurulamaz`, `YapilandirmaHatasi`.
  - `data.pozisyon`: siniflar (`SinyalPenceresiTamDegil`, `UygunDegil`, `FundingTamDegil`,
    `SinyalKosuluSaglanmadi`, `SinyalBariYok`, `OnaylanmisPozisyon`); veri ve tablo yolu (`_karar_verisi`,
    `donem_kaydi`, `grup_dogrula`, `kume_sinirlari`). Bu dort fonksiyon cagri aninda `data.pozisyon`
    uzerinden cozulur (asagidaki ince sarmalayicilar): kapi ile referans AYNI veriyi, ayni erisim
    denetimiyle (kume korumasi, onay kosusu, kesif kosusu, `kume_bellegi`) okur.
  - `data.split` (`onay_baglami_dogrula`, `kesif_baglami_dogrula`) ve `data.klines` (`hucreleri_tam_mi`).
Siniflar ayni nesne olmalidir: ret gerekcesi sinifi ve onayli pozisyonun alanlari (`PozisyonPlani` dahil)
kapiyla `==` ve `type(...) is` ile karsilastirilir.

Ag ve disk erisimi yoktur; veri yalnizca dayanilan `data.pozisyon._karar_verisi` uzerinden gelir.
Getiri HESAPLAMAZ.
"""

from __future__ import annotations

import functools
import functools as _functools
import itertools
import math
import sys
import types as _types
from dataclasses import dataclass, field, replace
from types import MappingProxyType

import numpy as np
import pandas as pd

import config
from data import klines as klines_modulu
from data import pozisyon as _pozisyon_asli
from data import split as split_modulu
from data.pencere import (  # dayanilan: zaman toleransi, izgara adimi, zaman dogrulamasi, plan imzasi
    ADIM_4H, ADIMLAR, ODEME_TOLERANSI, _plan_imzasi, _zaman_dizisi_dogrula, adim, ayni_an, ayni_an_basi,
    ayni_an_sonu, ayni_ya_da_once, ayni_ya_da_sonra, once, plan_dogrula, sonra, utc_zamani,
)
from data.pencere import (  # dayanilan: siniflar
    CikisSonucu, DonemDisiSinyal, GirisBariYok, HipotezUfuklari, IleriKaymaSiniriHatasi, KumeSiniriHatasi,
    OlayOlusmaz, PozisyonPlani, VeriHatasi, ZamanDizisiHatasi,
)
from data.pozisyon import (  # dayanilan: siniflar
    FundingTamDegil, OnaylanmisPozisyon, SinyalBariYok, SinyalKosuluSaglanmadi, SinyalPenceresiTamDegil,
    UygunDegil,
)
from data.sinyal import TepePenceresiKurulamaz, YapilandirmaHatasi  # dayanilan: siniflar

# Kopyalanan bes modulun takma adlari bu modulun kendisidir (modul aciklamasi, "ICERIK").
pencere_modulu = sinyal_modulu = funding_modulu = eligibility_modulu = sys.modules[__name__]

# Dayanilan kopyalanmamis adlarin TAM listesi; `tests/test_skaler_referans.py` bu listeyi denetler.
DAYANILAN = MappingProxyType({
    "config": ("*",),
    "data.pencere": ("ADIM_4H", "ADIMLAR", "ODEME_TOLERANSI", "_plan_imzasi", "_zaman_dizisi_dogrula", "adim",
                     "ayni_an", "ayni_an_basi", "ayni_an_sonu", "ayni_ya_da_once", "ayni_ya_da_sonra", "once",
                     "plan_dogrula", "sonra", "utc_zamani", "CikisSonucu", "DonemDisiSinyal", "GirisBariYok",
                     "HipotezUfuklari", "IleriKaymaSiniriHatasi", "KumeSiniriHatasi", "OlayOlusmaz",
                     "PozisyonPlani", "VeriHatasi", "ZamanDizisiHatasi"),
    "data.sinyal": ("TepePenceresiKurulamaz", "YapilandirmaHatasi"),
    "data.pozisyon": ("FundingTamDegil", "OnaylanmisPozisyon", "SinyalBariYok", "SinyalKosuluSaglanmadi",
                      "SinyalPenceresiTamDegil", "UygunDegil", "_karar_verisi", "donem_kaydi", "grup_dogrula",
                      "kume_sinirlari"),
    "data.split": ("onay_baglami_dogrula", "kesif_baglami_dogrula"),
    "data.klines": ("hucreleri_tam_mi",),
})


# --- Dayanilan veri ve tablo yolu: cagri aninda `data.pozisyon` uzerinden ------------------------------

def _karar_verisi(*args, **kwargs):
    return _pozisyon_asli._karar_verisi(*args, **kwargs)


def donem_kaydi(*args, **kwargs):
    return _pozisyon_asli.donem_kaydi(*args, **kwargs)


def grup_dogrula(*args, **kwargs):
    return _pozisyon_asli.grup_dogrula(*args, **kwargs)


def kume_sinirlari(*args, **kwargs):
    return _pozisyon_asli.kume_sinirlari(*args, **kwargs)


# ====================================================================================================
# data/pencere.py (4e63037) kopyasi
# ====================================================================================================


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


GUNUN_SON_4H_BARI = (config.GUNLUK_BAR_SAYISI - 1) * ADIMLAR[config.BAR_4H]


def _sonuc(deger):
    """Skaler karsilastirmada bool, dizide numpy bool dizisi."""
    if np.ndim(deger) == 0:
        return bool(deger)
    return np.asarray(deger, dtype=bool)


CIKIS_TURLERI = ("olagan", "ileri_kayma", "donem_sonu")


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


def giris_ani(sinyal_zamani, bar: str) -> pd.Timestamp:
    """Giris ani = t barinin kapanis ani = t + adim (on-kayit §4 rev.8)."""
    return utc_zamani(sinyal_zamani, "sinyal_zamani") + adim(bar)


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
        raise VeriHatasi("Bar listesi bos.")  # denetci KS3 D-C3
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
        raise VeriHatasi(f"{neden}; donem ici bar seride olmali (bozuk ya da eksik seri).")  # KS3 D-C3

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
    # Ileri kayma sinirini `config.ILERI_KAYMA_SINIRI` verir, `birincil_ufuk` parametresi DEGIL
    # (F1 kapatma turu madde 1a, bulgu S-C4). On-kayit §4 rev.6 "Ileri kaymanin ust siniri" ayri
    # bir kuraldir ve rev.10 "yalnizca bu on-kayitta tanimlidir" der; degerce birincil ufka esit
    # olmasi tesadufi degil ama parametreden beslenmek kurali cagirana baglardi.
    kayma_siniri = config.ILERI_KAYMA_SINIRI[bar]
    sinir = hedef_acilis + int(kayma_siniri) * adim(bar)
    if sonra(ilk, sinir):
        raise IleriKaymaSiniriHatasi(
            f"Hedef bar {hedef_acilis} eksik ve sonraki mevcut bar {ilk} ileri kayma sinirindan "
            f"({kayma_siniri} x {adim(bar)}) uzak (on-kayit §4 rev.8: olay olusmaz).")
    return _kume_icinde(CikisSonucu(_sira(ilk), ilk, "open", ilk, "ileri_kayma", hedef, ilk - hedef_acilis))


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


# ====================================================================================================
# data/funding.py (4e63037) kopyasi
# ====================================================================================================


def sinyal_penceresi_ayrintisi(funding: pd.DataFrame, t_ler, bar: str, *, saat: int, kume_baslangic,
                               kume_bitis, donem_baslangic) -> pd.DataFrame:
    """H2 funding sinyal penceresinin kurallari, t basina (vektorel). Yalnizca odeme ZAMANI ve ARALIGI
    okunur; oran bu fonksiyonun hicbir kararina girmez. (Cagirdigi `funding_tamlik_ayrintisi`
    Rev.11'den beri oranin SONLU olup olmadigini da hesaplar -- `oran_gecerli` --, ama bu
    fonksiyon o sutunu okumaz: sinyal penceresinin oran kosulu `funding_ortalamasi`dedir.)
    `funding_ortalamasi` degeri bunun ustune kurar.

    On-kayit §4 "Funding sinyal penceresinin tamligi" (rev.9, rev.10):
      - Pencere t barinin kapanisinda biter ve `saat` saat geriye uzanir; YARI ACIKTIR: pencere
        basina tam denk gelen kayit ortalamaya girmez, pencere sonuna denk gelen girer (ikisi de
        tolerans payiyla, `pencere.sonra` / `pencere.ayni_ya_da_once`). `ilk`, `son`: penceredeki ilk
        ve son kaydin sirasi (kayit yoksa `son < ilk`).
      - `kume_icinde`: pencerenin tamami kumenin (ve donemin) icinde: pencere basi kume basindan ve
        donem basindan once degil, kapanis kume sonundan sonra degil; karsilastirmalar toleransla
        (kume sonu 23:59:59 ile son barin kapanisi 00:00 ayni an; son bar dusmez).
      - `capa_var`, `aralik_gecerli`, `zincir_tam`: tek tamlik kodu `funding_tamlik_ayrintisi`, giris =
        pencere basi, pencere sonu = kapanis, taban = donem basi ile kume basinin gec olani. Capa
        pencere basinda ya da oncesinde kalan son kayit; zincir capadan pencere sonuna; ilk ciftte
        taban pencere basi; dizideki her kaydin araligi sonlu ve > 0 ("Gecerli aralik", rev.10).
        **Son kosulu uygulanmaz** (`son_tam` okunmaz).
      - `kayit_var`: pencerede en az bir kayit (ortalama tanimli).
      - `kume_sonu_kaydi_disarida` (rev.11): "Pencere sonuna denk gelen kayit yalnizca AYNI
        KUMEYE aitse ortalamaya girer: sonraki kumenin ilk kaydi, tolerans payiyla pencere sonuna
        denk gelse bile okunmaz ve o barda deger hesaplanmaz, cunku §3 geregi kumeler arasi veri
        odunc alinmaz." Pencere sonuna denk gelen kaydin hangi kumeye ait oldugu TAKVIMLE
        belirlenir: pencere sonu (t barinin kapanisi) kume sonundan sonraysa (TOLERANSSIZ
        karsilastirma) o ana denk gelen kayit sonraki kumenin kaydidir ve pencere hesaplanamaz.
        Bu kosul `kume_icinde`den ayridir: `kume_icinde` rev.10'un kuralidir ve toleransli
        kalir (kumenin son barinin kapanisi ile kume sonu arasindaki bir saniye ayni andir), bu
        yuzden kumenin son barini dusurmez; rev.11'in kosulu ise tam o barlari dusurur
        ("Bu, kesif kumesinin son barlarini dusurur"). Kume sonu verilmemisse (None) kosul
        uygulanmaz.
    `hesaplanabilir` = hepsi. Kapanistan sonraki kayitlar karara girmez (zincir ve aralik yalnizca
    capadan pencere sonuna); `funding_ortalamasi` seriyi ayrica kapanista keser. Sinirlar zorunlu
    anahtar sozcuktur; donem basi None olamaz, kume siniri yoksa acikca None. Saf.
    """
    if not isinstance(saat, int) or isinstance(saat, bool) or saat < 1:
        raise ValueError(f"saat pozitif bir tamsayi olmali: {saat!r}")
    if saat != config.H2_FUNDING_PENCERESI_SAAT:
        raise ValueError(f"saat {saat} on-kayit degeri degil; H2 funding penceresi "
                         f"{config.H2_FUNDING_PENCERESI_SAAT} saattir (on-kayit §5 H2 madde 1; "
                         "config.H2_FUNDING_PENCERESI_SAAT).")
    kume_bas = pencere_modulu.sinir_zamani(kume_baslangic, "kume_baslangic")
    kume_son = pencere_modulu.sinir_zamani(kume_bitis, "kume_bitis")
    donem_bas = pencere_modulu.donem_siniri(donem_baslangic, "donem_baslangic")
    t = pd.DatetimeIndex(t_ler)
    if t.tz is None:
        if len(t):
            raise TypeError("t_ler saat dilimsiz (tz-naive); tum zaman damgalari UTC olmali.")
        t = t.tz_localize("UTC")
    kapanis = t + pencere_modulu.adim(bar)
    bas = kapanis - pd.Timedelta(hours=saat)
    n = len(t)

    kume_icinde = ~np.asarray(once(bas, donem_bas), dtype=bool)
    if kume_bas is not None:
        kume_icinde &= ~np.asarray(once(bas, kume_bas), dtype=bool)
    if kume_son is not None:
        kume_icinde &= ~np.asarray(sonra(kapanis, kume_son), dtype=bool)
    # Kume sonundaki kayit (rev.11): pencere sonu kume sonundan sonraysa, pencere sonuna denk
    # gelen kayit SONRAKI kumeye aittir ve okunamaz. Karsilastirma TOLERANSSIZ: §4 "Zaman
    # toleransi" iki ani ayni sayar, ama kume UYELIGI takvim sorusudur (KESIF 23:59:59'da biter,
    # C2 00:00:00'da baslar) ve on-kayit bu kaydin "tolerans payiyla pencere sonuna denk gelse
    # bile" okunmayacagini yazar.
    if kume_son is not None:
        kume_sonu_kaydi_disarida = ~np.asarray(kapanis > kume_son, dtype=bool)
    else:
        kume_sonu_kaydi_disarida = np.ones(n, dtype=bool)

    taban = donem_bas if kume_bas is None else max(donem_bas, kume_bas)
    tamlik = funding_tamlik_ayrintisi(funding, bas, kapanis, donem_baslari=[taban] * n)
    if n and not funding.empty:
        zamanlar = _zaman_dizisi(funding, "sinyal_penceresi_ayrintisi")
        # Sirali dizide tek kenar tanimlari (`ayni_an_sonu`): sonra(z, bas) <=> z >= bas + tol;
        # ayni_ya_da_once(z, kapanis) <=> z < kapanis + tol.
        ilk = zamanlar.searchsorted(pencere_modulu.ayni_an_sonu(bas), side="left")
        son = zamanlar.searchsorted(pencere_modulu.ayni_an_sonu(kapanis), side="left") - 1
    else:
        ilk = np.zeros(n, dtype=int)
        son = np.full(n, -1, dtype=int)
    sonuc = pd.DataFrame({
        "kume_icinde": kume_icinde,
        "kume_sonu_kaydi_disarida": kume_sonu_kaydi_disarida,
        "capa_var": tamlik["capa_var"].to_numpy(dtype=bool),
        "aralik_gecerli": tamlik["aralik_gecerli"].to_numpy(dtype=bool),
        "zincir_tam": tamlik["zincir_tam"].to_numpy(dtype=bool),
        "kayit_var": np.asarray(son >= ilk, dtype=bool),
        "ilk": np.asarray(ilk, dtype=int),
        "son": np.asarray(son, dtype=int),
    })
    sonuc.insert(0, "hesaplanabilir", sonuc["kume_icinde"] & sonuc["kume_sonu_kaydi_disarida"]
                 & sonuc["capa_var"] & sonuc["aralik_gecerli"] & sonuc["zincir_tam"] & sonuc["kayit_var"])
    return sonuc


def funding_ortalamasi(
    funding: pd.DataFrame,
    t,
    bar: str,
    *,
    saat: int,
    kume_baslangic,
    kume_bitis,
    donem_baslangic,
) -> float:
    """t barinin kapanisina kadarki son `saat` saatteki 8 saate normallestirilmis funding oranlarinin
    ortalamasi (on-kayit §5 H2 madde 1); kural ihlalinde NaN.

    Pencere kurallari `sinyal_penceresi_ayrintisi`dir (on-kayit §4 "Funding sinyal penceresinin
    tamligi", rev.9 + rev.10): yari acik pencere (basa denk gelen kayit girmez, sona denk gelen girer),
    capa, zincir (ilk ciftte taban pencere basi), gecerli aralik, son kosulu yok, pencerenin tamami
    kumenin icinde, pencere sonundaki kaydin ayni kumeye ait olmasi (rev.11). "t barinin
    kapanisindan sonraki hicbir kayit okunmaz": seri, hicbir denetimden once kapanisla ayni an ya
    da once olan kayitlara kesilir. Penceredeki bir oran sayi degilse ya da sonlu degilse (NaN,
    +-sonsuz) deger hesaplanmaz (rev.11).
    Bir dakikadan yakin iki kayit bozuk veridir -> `ZamanDizisiHatasi`.

    Tum sinirlar zorunlu anahtar sozcuktur (kume sonu Rev.10 ile eklendi). Donem basi None olamaz;
    kume siniri yoksa acikca None. Saf fonksiyon.
    """
    zaman = pencere_modulu.utc_zamani(t, "t")
    kapanis = zaman + pencere_modulu.adim(bar)
    ham = pd.DatetimeIndex(funding["odeme_zamani"])
    if len(ham) and ham.tz is None:
        raise pencere_modulu.ZamanDizisiHatasi(
            "funding_ortalamasi: odeme zamanlari saat dilimsiz (tz-naive); tum zaman damgalari UTC olmali.")
    gecmis = funding.loc[np.asarray(ayni_ya_da_once(ham, kapanis), dtype=bool)].reset_index(drop=True)
    a = sinyal_penceresi_ayrintisi(gecmis, [zaman], bar, saat=saat, kume_baslangic=kume_baslangic,
                                   kume_bitis=kume_bitis, donem_baslangic=donem_baslangic).iloc[0]
    if not bool(a["hesaplanabilir"]):
        return float("nan")
    oran = pd.to_numeric(gecmis["oran_8h"].iloc[int(a["ilk"]):int(a["son"]) + 1], errors="coerce")
    # On-kayit §4 rev.11: "Penceredeki kayitlarin oranlarindan biri sayi degilse ya da sonlu
    # degilse ortalama hesaplanmaz." NaN'in yaninda +-sonsuz da elenir (rev.11'den once yalnizca
    # NaN denetleniyordu; sonsuz bir oran ortalamayi sonsuz yapiyordu).
    if not bool(np.isfinite(oran.to_numpy(dtype=float)).all()):
        return float("nan")
    return float(oran.mean())


TAMLIK_KOSULLARI = ("capa_var", "aralik_gecerli", "zincir_tam", "son_tam", "oran_gecerli")


TAMLIK_BAYRAKLARI = ("kuyruk_kismi", "kuyruk_sifir", "son_esitlik_affi", "capa_aralik_saat", "son_aralik_saat",
                     "tek_ritim", "funding_ritmi_saat", "karisik_ritim", "ritim_sinifi")


RITIM_SINIFLANMAMIS = "siniflanmamis"


_RITIM_SAATLERI = {8.0: "8", 4.0: "4", 2.0: "2", 1.0: "1"}


def ritim_sinifi(saat) -> str | None:
    """Funding ritmi (saat) -> sinif (on-kayit §4 "Pozisyonun funding ritmi", rev.10). "Aralik alani 8,
    4, 2 ya da 1 saat disinda bir degerse pozisyon 'siniflanmamis' sinifinda raporlanir. Capasi olmayan
    pozisyon olusmadigi icin siniflanmaz": NaN (capa yok) -> None. Saf."""
    deger = float(saat)
    if np.isnan(deger):
        return None
    return _RITIM_SAATLERI.get(deger, RITIM_SINIFLANMAMIS)


TAMLIK_ZAMANLARI = ("capa_zamani", "son_kayit_zamani")


def funding_penceresi_sonu(plan) -> pd.Timestamp:
    """Pozisyonun funding penceresinin ust ucu (dahil). On-kayit §4 rev.8: olagan
    cikista ve ileri kaymada cikis ani ("cikis anindaki dahil"); donem sonuna ulasan
    pozisyonda donem bitisi B ("Donem sonu istisnasi": B'den sonraki odemeler, K
    dahil, hesaba girmez; tamlik son odemeyi B'ye gore arar)."""
    pencere_modulu.plan_dogrula(plan)
    return plan.donem_bitis if plan.donem_sonu_mu else plan.cikis_ani


def _zaman_dizisi(funding: pd.DataFrame, yer: str) -> pd.DatetimeIndex:
    """Sirali, tekrarsiz ve ardisik iki kaydi ayni an olmayan odeme zamanlari (bozuk veri ->
    ZamanDizisiHatasi)."""
    zamanlar = pencere_modulu._zaman_dizisi_dogrula(funding["odeme_zamani"], yer)
    if len(zamanlar) > 1:
        yakin = np.asarray(ayni_an(zamanlar[1:], zamanlar[:-1]), dtype=bool)
        if yakin.any():
            ilk = int(yakin.argmax())
            raise pencere_modulu.ZamanDizisiHatasi(
                f"{yer}: {zamanlar[ilk]} ve {zamanlar[ilk + 1]} ayni an ({ODEME_TOLERANSI}'dan yakin); "
                "ayni odeme iki kez yazilmis olabilir (bozuk veri)."
            )
    return zamanlar


def funding_tamlik_ayrintisi(funding: pd.DataFrame, girisler, pencere_sonlari, *, donem_baslari) -> pd.DataFrame:
    """Pozisyon funding tamliginin TEK uygulamasi, kosul kosul (on-kayit §4 rev.9
    "Funding tamligi"; pencere: §4 "Funding odemesinin sinirlari", "Donem sonu
    istisnasi"). Vektorel: `girisler[i]`, `pencere_sonlari[i]` ve `donem_baslari[i]`
    bir pozisyondur. Odeme ZAMANI ve ARALIGI okunur; oranin DEGERI okunmaz, yalnizca sonlu bir
    sayi olup olmadigi denetlenir (rev.11 "Gecerli oran").

    Kural odeme ani TAHMIN ETMEZ; yalnizca kayitlar arasindaki bosluklari olcer. Bes madde (rev.10):
      - `capa_var` (**Capa**): giris aninda ya da oncesinde kalan son donem ici kayit
        (donem basiyla ayni an ya da sonra). "Capa yoksa funding tam degildir."
      - `zincir_tam` (**Zincir**, **Ilk cift**): capadan pencere sonuna kadar art arda
        iki kayitta sonraki, oncekinin ustune iki kaydin araliklarindan buyugu eklenerek
        bulunan andan SONRA degil. Ilk ciftte (capa -> sonraki kayit) taban capa degil
        giris anidir.
      - `son_tam` (**Son**): penceredeki son kayit + araligi pencere sonundan ONCE degil;
        "tam pencere sonuna denk gelmesi yeterlidir". Pencerede capadan sonra kayit
        yoksa dizinin son kaydi capadir (rev.9 "hic kayit yok" cumlesini kaldirdi).
      - `aralik_gecerli` (**Gecerli aralik**, rev.10): capadan son kayda kadar her kaydin
        araligi sonlu ve > 0; aralik olmadan zincir ve son maddeleri olculemez.
      - `oran_gecerli` (**Gecerli oran**, rev.11): "Pozisyonun funding penceresine giren her
        kaydin oran degeri sonlu bir sayi olmalidir; NaN, +sonsuz ya da -sonsuz oran tasiyan
        pozisyonun funding'i tam degildir ve pozisyon olusmaz. Toplamin isaretine ya da
        buyuklugune bakilmaz; denetim kayit duzeyindedir." Denetlenen kayitlar POZISYONUN
        ODEME PENCERESINE girenlerdir: giris anindan SONRA, pencere sonuna kadar (dahil) --
        yani toplama giren kayitlar (§4 "Funding odemesinin sinirlari"). Capanin orani toplama
        girmedigi icin denetlenmez; "pencereye giren kayit" ifadesinin capayi da kapsayacak
        okumasi, sonucu etkilemeyen veriyle pozisyon dusururdu (rapora acik nokta olarak
        yazildi). Bu madde oranin DEGERINI degil yalnizca sonlu bir sayi olup olmadigini okur.
    "Beklenen odeme ani yukaridaki maddeler disinda hicbir yerde uretilmez." Butun zaman
    karsilastirmalari §4 "Zaman toleransi"na gore (`pencere.ayni_an` ve turevleri):
    tolerans payi ayni an tanimidir, tam 1 dakikalik fark ayni an degildir.

    Bilinen sinirlarin bayraklari (on-kayit §4 rev.9 "Funding tamliginin bilinen
    sinirlari", "F2 sarti"; `tam`a GIRMEZ, yalnizca tam pozisyonlarda True olabilir):
      - `kuyruk_kismi`: son kayittan pencere sonuna kalan dilim bir tam araliktan kisa
        (0 < dilim; son kayit + araligi pencere sonundan SONRA ve son kayit pencere
        sonuyla ayni an degil). O dilimdeki eksik bir odeme gorulemez.
      - `kuyruk_sifir`: son kayit pencere sonuyla ayni an; dogrulanamayan dilim yok.
      - `son_esitlik_affi`: son kayit + araligi tam pencere sonuna denk geliyor; orada
        kayit yok ve pozisyon tam sayiliyor ("Pencere sonundaki esitlik").
    Ritim etiketleri (F2 sarti "funding ritmi basina"; hukme girmez): `capa_aralik_saat`
    (capanin araligi), `son_aralik_saat` (dizideki son kaydin araligi), `tek_ritim`
    (capadan son kayda kadar butun araliklar ayni). Capa yoksa araliklar NaN.
    Pozisyonun funding ritmi (on-kayit §4 "Pozisyonun funding ritmi", rev.10): `funding_ritmi_saat`
    = dizideki son kaydin araligi (kismi kuyrugun uzunlugunu belirleyen); `karisik_ritim` = capa var
    ve capadan son kayda araliklar ayni degil; `ritim_sinifi` = `ritim_sinifi(funding_ritmi_saat)`:
    "8", "4", "2", "1" ya da "siniflanmamis"; capa yoksa None.
    Dizinin uclari (`capa_zamani`, `son_kayit_zamani`; capa yoksa NaT) olcum betiklerinin tani
    sutunlari icindir; kural baska yerde yeniden kurulmasin diye buradan verilir.
    Saf.
    """
    girisler = pd.DatetimeIndex(girisler)
    sonlar = pd.DatetimeIndex(pencere_sonlari)
    baslar = pd.DatetimeIndex(donem_baslari)
    if not (len(girisler) == len(sonlar) == len(baslar)):
        raise ValueError("girisler, pencere_sonlari ve donem_baslari ayni uzunlukta olmali.")
    n = len(girisler)
    sonuc = pd.DataFrame({k: np.zeros(n, dtype=bool) for k in (*TAMLIK_KOSULLARI, "tam", *TAMLIK_BAYRAKLARI)})
    sonuc["capa_aralik_saat"] = np.full(n, np.nan)
    sonuc["son_aralik_saat"] = np.full(n, np.nan)
    sonuc["funding_ritmi_saat"] = np.full(n, np.nan)
    sonuc["ritim_sinifi"] = pd.Series([None] * n, index=sonuc.index, dtype=object)
    for k in TAMLIK_ZAMANLARI:
        sonuc[k] = pd.Series(pd.NaT, index=sonuc.index, dtype="datetime64[ns, UTC]")
    if n == 0 or funding.empty:
        return sonuc
    zamanlar = _zaman_dizisi(funding, "funding_tamlik_ayrintisi")
    aralik = pd.to_numeric(funding["aralik_saat"], errors="coerce").to_numpy(dtype=float)
    # Gecerli oran (rev.11): yalnizca sonlu olup olmadigi okunur, deger okunmaz. `oran` sutunu
    # bulunmayan cerceve (yalnizca zaman ve aralik tasiyan olcum girdileri) bu kosuldan gecer:
    # denetlenecek oran yoktur.
    if "oran" in funding:
        oran_kotu = ~np.isfinite(pd.to_numeric(funding["oran"], errors="coerce").to_numpy(dtype=float))
    else:
        oran_kotu = np.zeros(len(funding), dtype=bool)
    iyi = np.isfinite(aralik) & (aralik > 0)
    a_saat = np.where(iyi, aralik, 0.0)
    aralik_td = pd.to_timedelta(a_saat, unit="h")

    # Tek kenar tanimiyla (`ayni_an_sonu`): z < x + 1 dk <=> ayni_ya_da_once(z, x).
    j = zamanlar.searchsorted(pencere_modulu.ayni_an_sonu(girisler), side="left") - 1  # capa
    jj = np.maximum(j, 0)
    son_i = np.maximum(zamanlar.searchsorted(pencere_modulu.ayni_an_sonu(sonlar), side="left") - 1, jj)
    capa_var = (j >= 0) & np.asarray(pencere_modulu.ayni_ya_da_sonra(zamanlar[jj], baslar), dtype=bool)
    p_aralik = np.r_[0, np.cumsum(~iyi)]
    aralik_gecerli = capa_var & ((p_aralik[son_i + 1] - p_aralik[jj]) == 0)

    # Zincir: cift (i, i+1) icin sonraki kayit, onceki + iki araligin buyugunden SONRA olamaz.
    if len(zamanlar) > 1:
        adim = np.maximum(a_saat[1:], a_saat[:-1])
        kotu_cift = np.asarray(pencere_modulu.sonra(
            zamanlar[1:], zamanlar[:-1] + pd.to_timedelta(adim, unit="h")), dtype=bool)
    else:
        adim = np.zeros(0)
        kotu_cift = np.zeros(0, dtype=bool)
    p_cift = np.r_[0, np.cumsum(kotu_cift)]
    ilk_cift_var = son_i > jj
    # Ilk ciftten sonraki ciftler [jj + 1, son_i - 1]: p[son_i] - p[min(jj + 1, son_i)].
    sonraki_ciftler_kotu = (p_cift[son_i] - p_cift[np.minimum(jj + 1, son_i)]) > 0
    if len(adim):
        # Ilk cift (capa -> sonraki kayit): taban giris ani.
        k = np.minimum(jj, len(adim) - 1)
        ilk_adim = pd.to_timedelta(np.where(ilk_cift_var, adim[k], 0.0), unit="h")
        sonraki_kayit = zamanlar[np.minimum(jj + 1, len(zamanlar) - 1)]
        ilk_cift_kotu = ilk_cift_var & np.asarray(
            pencere_modulu.sonra(sonraki_kayit, girisler + ilk_adim), dtype=bool)
    else:
        ilk_cift_kotu = np.zeros(n, dtype=bool)
    zincir_tam = capa_var & aralik_gecerli & ~sonraki_ciftler_kotu & ~ilk_cift_kotu

    # Son: son kayit + araligi pencere sonundan ONCE olamaz (esitlik yeterli).
    sonraki = zamanlar[son_i] + aralik_td[son_i]
    son_tam = capa_var & aralik_gecerli & ~np.asarray(pencere_modulu.once(sonraki, sonlar), dtype=bool)
    # Gecerli oran (rev.11): odeme penceresindeki kayitlar [jj + 1, son_i]; capa (jj) haric.
    p_oran = np.r_[0, np.cumsum(oran_kotu)]
    ilk_odeme = np.minimum(jj + 1, son_i + 1)
    oran_gecerli = capa_var & ((p_oran[son_i + 1] - p_oran[ilk_odeme]) == 0)
    tam = capa_var & aralik_gecerli & zincir_tam & son_tam & oran_gecerli

    sonuc["capa_var"] = capa_var
    sonuc["aralik_gecerli"] = aralik_gecerli
    sonuc["zincir_tam"] = zincir_tam
    sonuc["son_tam"] = son_tam
    sonuc["oran_gecerli"] = oran_gecerli
    sonuc["tam"] = tam
    dolmamis = tam & np.asarray(pencere_modulu.sonra(sonraki, sonlar), dtype=bool)
    son_kayit_sonda = np.asarray(pencere_modulu.ayni_an(zamanlar[son_i], sonlar), dtype=bool)
    sonuc["kuyruk_kismi"] = dolmamis & ~son_kayit_sonda
    sonuc["kuyruk_sifir"] = dolmamis & son_kayit_sonda
    sonuc["son_esitlik_affi"] = tam & np.asarray(pencere_modulu.ayni_an(sonraki, sonlar), dtype=bool)
    degisim = (aralik[1:] != aralik[:-1]) if len(aralik) > 1 else np.zeros(0, dtype=bool)
    p_degisim = np.r_[0, np.cumsum(degisim)]
    sonuc["capa_aralik_saat"] = np.where(capa_var, aralik[jj], np.nan)
    sonuc["son_aralik_saat"] = np.where(capa_var, aralik[son_i], np.nan)
    sonuc["tek_ritim"] = capa_var & ((p_degisim[son_i] - p_degisim[jj]) == 0)
    sonuc["funding_ritmi_saat"] = sonuc["son_aralik_saat"].to_numpy()
    sonuc["karisik_ritim"] = capa_var & ~sonuc["tek_ritim"].to_numpy(dtype=bool)
    sonuc["ritim_sinifi"] = pd.Series([ritim_sinifi(s) for s in sonuc["funding_ritmi_saat"].to_numpy()],
                                      index=sonuc.index, dtype=object)
    sonuc["capa_zamani"] = zamanlar[jj].where(capa_var)
    sonuc["son_kayit_zamani"] = zamanlar[son_i].where(capa_var)
    return sonuc


def pozisyon_funding_ayrintisi(funding: pd.DataFrame, plan) -> pd.Series:
    """Planin funding tamligi, kosullari ve bayraklariyla (on-kayit §4 rev.9): tek satir
    `funding_tamlik_ayrintisi`. Pencere `funding_penceresi_sonu`, capa tabani planin donem
    basi. Tek karar noktasi (`data.pozisyon.olay_karari`) bunu kullanir."""
    pencere_modulu.plan_dogrula(plan)
    return funding_tamlik_ayrintisi(funding, [plan.giris], [funding_penceresi_sonu(plan)],
                                    donem_baslari=[plan.donem_baslangic]).iloc[0]


def pozisyon_funding_tam_mi(funding: pd.DataFrame, plan) -> bool:
    """Planin funding'i tam mi (on-kayit §4 rev.9 "Funding tamligi")? Yalnizca odeme
    zamani ve araligi okunur."""
    return bool(pozisyon_funding_ayrintisi(funding, plan)["tam"])


def _plan_fundingi(funding: pd.DataFrame, plan) -> float:
    """Short pozisyonun tuttugu sure boyunca aldigi (+) ya da odedigi (-) funding.

    On-kayit §4: her funding aninda `+oran` (GERCEK odeme orani, `oran`;
    8 saate normallestirilmis `oran_8h` kullanilmaz). Toplam doner.

    MODUL DISINA KAPALI ic adim: yalnizca tek karar noktasi (`pozisyon.olay_karari`) cagirir;
    getiri tarafi funding'i onayli pozisyondan (`funding_toplami` ya da `pozisyon_fundingi`) okur.
    Testler dogrudan cagirabilir; analiz kodu icin kaynak taramasinda yasaklidir.

    Yalnizca `pencere.pozisyon_plani`nin urettigi PLANI alir. Sinirlar (on-kayit §4
    rev.8): giris anindaki odeme HARIC, cikis anindaki DAHIL; donem sonuna ulasan
    pozisyonda pencere B'de (dahil) kapanir. Tamlik `funding_tamlik_ayrintisi`dir (rev.9).

    NaN yalnizca VERI EKSIKLIGIDIR (tamlik saglanmadi ya da oran NaN). Plan olmayan
    girdi TypeError, degistirilmis plan ValueError, bozuk zaman dizisi
    `ZamanDizisiHatasi`. Saf fonksiyon.
    """
    pencere_modulu.plan_dogrula(plan)
    zamanlar = _zaman_dizisi(funding, "_plan_fundingi")
    if not pozisyon_funding_tam_mi(funding, plan):
        return float("nan")
    maske = (np.asarray(sonra(zamanlar, plan.giris), dtype=bool)
             & np.asarray(ayni_ya_da_once(zamanlar, funding_penceresi_sonu(plan)), dtype=bool))
    oran = pd.to_numeric(funding.loc[maske, "oran"], errors="coerce")
    if oran.isna().any():
        return float("nan")
    return float(oran.sum())


# ====================================================================================================
# data/eligibility.py (4e63037) kopyasi
# ====================================================================================================


def gunluk_hacim_serisi(gunluk: pd.DataFrame) -> pd.Series:
    """Gunluk quote hacmini, gunun acilis zamaniyla indekslenmis seri olarak doner."""
    seri = pd.Series(
        pd.to_numeric(gunluk["quote_volume"], errors="coerce").values,
        index=pd.DatetimeIndex(gunluk["open_time"]),
    )
    return seri.sort_index()


def medyan_hacim(
    gunluk_hacim: pd.Series,
    t,
    *,
    donem_baslangic,
    kume_baslangic,
    pencere_gun: int,
) -> float:
    """t gunu haric, ondan onceki son `pencere_gun` GUNUN medyan hacmi (on-kayit §2 rev.3, rev.6).

    `pencere_gun` zorunludur (varsayilan yoktur); on-kayit degeri
    `config.HACIM_PENCERESI_GUN`.

    Pencere zamanla tanimlidir ve `data.pencere` yardimcisindan gecer:
      - t'nin ait oldugu gun HENUZ KAPANMADIGI icin pencereye alinmaz; pencere
        t'den once kapanmis son gunde biter. Bu, gelecege bakisi imkansiz kilar.
      - Pencere donem baslangicini asamaz (rev.2).
      - Pencere kume baslangicini asamaz (on-kayit §3 rev.5).
      - Penceredeki gunlerden biri bile eksikse NaN doner (rev.3 tamlik sarti).
        Eksik gun, 6 adet 4h barin tamami olmayan gundur.
    `donem_baslangic` ve `kume_baslangic` zorunludur; donem siniri None olamaz (D-C6), kume
    yoksa acikca None verilir.
    """
    zaman = pencere_modulu.utc_zamani(t, "t")

    # Pencere t'nin kendi GUNUNU icermez: o gun henuz kapanmadi. Pencere, t'nin
    # gunune gore t_dahil=False ile tanimlanir; son gun t'den onceki gundur
    # (on-kayit §5 rev.4: pencere siniri acikca belirtilir).
    return pencere_modulu.pencere_degeri(
        gunluk_hacim,
        zaman.floor("D"),
        pencere_gun,
        config.BAR_1D,
        t_dahil=False,
        kume_baslangic=kume_baslangic,
        islev="median",
        donem_baslangic=donem_baslangic,
    )


def listeleme_yasi_gun(donem_baslangic, t) -> float:
    """t anindaki listeleme yasi, gun cinsinden.

    On-kayit rev.2: yas her listeleme donemi basinda sifirlanir, bu yuzden
    referans sembolun ilk bari degil, icinde bulunulan DONEMIN baslangicidir.
    """
    return (pd.Timestamp(t) - pd.Timestamp(donem_baslangic)) / pd.Timedelta(days=1)


def hacim_esigi(bar: str) -> float:
    """Bar tipine gore on-kayit §2'deki hacim esigi."""
    if bar == config.BAR_4H:
        return config.ASGARI_HACIM_4H
    if bar == config.BAR_1D:
        return config.ASGARI_HACIM_1D
    raise ValueError(f"Bilinmeyen bar: {bar!r}")


def esikleri_dogrula(bar: str, *, asgari_hacim, asgari_listeleme_yasi_gun) -> None:
    """Verilen uygunluk esikleri on-kayit §2'dekilerle ayni mi? Degilse ValueError.

    Esikler on-kayitta sabittir (H1, H2: 10 milyon USDT; H3: 2 milyon USDT; listeleme yasi
    30 gun); cagiranin acikca yazmasi istenir ama baska bir deger verilemez."""
    for ad, deger in (("asgari_hacim", asgari_hacim), ("asgari_listeleme_yasi_gun", asgari_listeleme_yasi_gun)):
        if isinstance(deger, bool) or not isinstance(deger, (int, float)):
            raise TypeError(f"{ad} bir sayi olmali: {deger!r}")
    if asgari_hacim != hacim_esigi(bar):
        raise ValueError(f"asgari_hacim on-kayit §2 esigi olmali ({bar}: {hacim_esigi(bar)}); verilen {asgari_hacim}")
    if asgari_listeleme_yasi_gun != config.ASGARI_LISTELEME_YASI_GUN:
        raise ValueError(f"asgari_listeleme_yasi_gun on-kayit §2 esigi olmali ({config.ASGARI_LISTELEME_YASI_GUN}); "
                         f"verilen {asgari_listeleme_yasi_gun}")


def uygunluk_karari(
    gunluk_hacim: pd.Series,
    t,
    bar: str,
    *,
    donem_baslangic,
    donem_bitis,
    kume_baslangic,
    asgari_hacim,
    asgari_listeleme_yasi_gun,
) -> bool:
    """t aninda sembol uygun mu? Uygunlugun TEK uygulamasi (on-kayit §2 "Uygunluk",
    "Uygunluk penceresi ve t gunu"; §4 rev.9 "Olayin kumede olusma olcutu"). Yalnizca
    t'ye kadarki veriyi kullanir.

    On-kayit rev.2 gereklilikleri:
      - t donem ici degilse uygun degildir (on-kayit §6 rev.8 "Donem uyeligi";
        1d barda gunun alti 4h barinin tamami donem ici olmali),
      - listeleme yasi donem baslangicina gore olculur ve `asgari_listeleme_yasi_gun`u
        gecmeli,
      - hacim penceresi donem baslangicini asamaz; medyan hesaplanabilmis olmali VE
        `asgari_hacim`i gecmeli ("Uygunluk degerinin hesaplanabilmis olmasi yeterli
        degildir; esigi de gecmelidir").
    On-kayit §3 rev.5: hacim penceresi kume baslangicini da asamaz.

    Esikler on-kayit degerleri olmalidir (`esikleri_dogrula`). Tum sinirlar zorunlu anahtar
    sozcuktur. Donem sinirlari (`donem_baslangic`, `donem_bitis`) None OLAMAZ (denetci bulgusu
    D-C6; listeleme yasi ve donem uyeligi onlara gore olculur); `kume_baslangic` sinir yoksa
    acikca None alir.
    """
    esikleri_dogrula(bar, asgari_hacim=asgari_hacim, asgari_listeleme_yasi_gun=asgari_listeleme_yasi_gun)
    zaman = pencere_modulu.utc_zamani(t, "t")
    donem_bas = pencere_modulu.donem_siniri(donem_baslangic, "donem_baslangic")
    donem_son = pencere_modulu.donem_siniri(donem_bitis, "donem_bitis")

    # Donem uyeligi (on-kayit §6 rev.8): 4h barda acilis [donem basi, B]; 1d barda
    # gunun alti 4h barinin tamami donem ici. Tek yuklem `pencere.donem_ici_mi`.
    if not pencere_modulu.donem_ici_mi(zaman, bar, donem_baslangic=donem_bas, donem_bitis=donem_son):
        return False

    if listeleme_yasi_gun(donem_bas, zaman) < asgari_listeleme_yasi_gun:
        return False

    medyan = medyan_hacim(
        gunluk_hacim,
        zaman,
        donem_baslangic=donem_bas,
        kume_baslangic=kume_baslangic,
        pencere_gun=config.HACIM_PENCERESI_GUN,
    )
    if pd.isna(medyan):
        return False
    return bool(medyan >= asgari_hacim)


# ====================================================================================================
# data/sinyal.py (4e63037) kopyasi
# ====================================================================================================


PARAMETRELER = MappingProxyType({
    "H1": ("theta", "delta"),      # θ ∈ {0.20, 0.30, 0.40} × δ ∈ {0.08, 0.12, 0.16}
    "H2": ("phi", "k"),            # φ ∈ {0.03%, 0.05%, 0.10%} × k ∈ {3, 6, 12}
    "H3": ("nu", "tau"),           # ν ∈ {0.50, 0.65, 0.80} × τ ∈ {0.15, 0.25, 0.35}
})


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


def _seri(mumlar: pd.DataFrame, alan: str) -> pd.Series:
    """Mum cercevesinin bir alanini, acilis zamaniyla indekslenmis seri olarak doner. Saf.

    Alan sayisal degilse (string, nesne) `pd.to_numeric` NaN uretir; SONLU OLMAYAN deger
    (+-sonsuz) de NaN'a cevrilir.

    **Barin mevcutlugu BAR duzeyindedir (on-kayit §2, rev.12).** "Bu, barin mevcutlugunun genel
    tanimidir (rev.12): olcut alan duzeyinde degil bar duzeyindedir ve her izgarada, her
    pencerede ve her hesapta gecerlidir — hucresi bozuk bir bar 4 saatlik sinyal pencerelerinde
    de mevcut sayilmaz, ilgili hucresi gecerli olsa bile." Bu yuzden seri yalnizca ISTENEN alani
    denetlemez: barin butun fiyat ve hacim hucreleri (`klines.HUCRE_SUTUNLARI`) sonlu bir sayi
    olmalidir; biri bozuksa o barin damgasi her alanda NaN olur ve §2 "Tamlik sarti" o bari
    iceren her pencereyi hesaplanamaz yapar. Olcut `klines.hucreleri_tam_mi`dir, yani 1d
    turetmesiyle (ayni on-kayit cumlesi) TEK bir yerden gelir; cercevede bulunmayan bir hucre
    sutunu denetlenmez (sentetik ve kismi cerceveler).

    Islem sayisi (`count`) kapsam DISINDADIR (on-kayit §2 rev.12: "hicbir olay, uygunluk ya da
    getiri hesabina girmedigi icin eksikligi bari dusurmez"); `HUCRE_SUTUNLARI` onu icermez.

    Rev.12'den once olcut alan duzeyindeydi: ayni bar bir pencerede mevcut, baska bir pencerede
    eksik sayilabiliyordu. F1 olcumunde donem ici 4h barlarda bozuk hucre bulunmamistir, yani bu
    kural bugunku veride hicbir bari dusurmez (etki olcumu: RESULTS §14.30).
    """
    if alan not in mumlar:
        raise KeyError(f"Mum cercevesinde {alan!r} sutunu yok (sinyal penceresi kurulamaz).")
    degerler = pd.to_numeric(mumlar[alan], errors="coerce").to_numpy(dtype=float)
    degerler = np.where(np.isfinite(degerler), degerler, np.nan)
    # Bar duzeyli olcut (on-kayit §2 rev.12): barin herhangi bir fiyat ya da hacim hucresi bozuksa
    # bar hicbir pencerede mevcut degildir, istenen hucresi gecerli olsa bile.
    degerler = np.where(klines_modulu.hucreleri_tam_mi(mumlar), degerler, np.nan)
    seri = pd.Series(degerler, index=pd.DatetimeIndex(mumlar["open_time"]))
    return seri.sort_index()


def bar_degeri(mumlar: pd.DataFrame, t, alan: str) -> float:
    """t barinin `alan` degeri; bar yoksa ya da deger sonlu degilse NaN. Saf.

    On-kayit §2 (rev.11): "Bir barin mevcut sayilmasi icin satirinin bulunmasi yetmez: fiyat ve
    hacim hucrelerinin tamami sayi olmalidir." Olcut BAR duzeyindedir (rev.12; `_seri`): t
    barinin `close` hucresi saglam olsa bile baska bir fiyat ya da hacim hucresi bozuksa bar
    mevcut degildir ve deger hesaplanmaz.
    """
    zaman = pencere_modulu.utc_zamani(t, "t")
    seri = _seri(mumlar, alan)
    bar = pencere_modulu.ayni_andaki_bar(pd.DatetimeIndex(seri.index), zaman)
    if bar is None:
        return float("nan")
    deger = float(seri.loc[bar])
    return deger if math.isfinite(deger) else float("nan")


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
        raise TepePenceresiKurulamaz(f"teyit bari {teyit} pump barinin ({pump}) 4h izgarasinda degil.")
    sayi = int(fark / adim)
    if sayi < 1:
        raise TepePenceresiKurulamaz(
            f"teyit bari ({teyit}) pump barindan ({pump}) sonra olmali (on-kayit §5 H1 madde 3).")
    if sayi > config.H1_IZLEME_BAR:
        raise TepePenceresiKurulamaz(
            f"teyit bari pump barindan {sayi} bar sonra; on-kayit §5 H1 madde 3 en fazla "
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


def yuksek_30_max(mumlar: pd.DataFrame, t, bar: str, *, kume_baslangic, donem_baslangic) -> float:
    """`max(high[t-30..t])` (on-kayit §5 H2 madde 4, H3 madde 4 rev.13).

    Iki uclu kapali aralik, `kapanis_30_once` ile AYNI tamlik penceresi: `[t-30 .. t]`, yani 31
    bar (§5 "Pencere sinirlarinin tamami", rev.11); araliktaki beklenen barlardan biri bile
    eksikse deger hesaplanmaz. `bar` izgaradir: H2'de 4h serisi, H3'te 1 gunluk seri (rev.13:
    "pencere 1 gunluk seridedir ve tamlik sarti §5 'Pencere sinirlari'na goredir").
    """
    return pencere_modulu.pencere_degeri(
        _seri(mumlar, "high"), t, config.OTUZ_BAR_ONCE + 1, bar, t_dahil=True,
        kume_baslangic=kume_baslangic, donem_baslangic=donem_baslangic, islev="max")


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


def _izgara_degeri(hipotez: str, parametre: str, deger):
    """Tek bir parametrenin izgarada bulundugunu denetler; izgaradaki degeri doner."""
    gecerli = config.IZGARA[hipotez][parametre]
    for aday in gecerli:
        if not isinstance(deger, bool) and isinstance(deger, (int, float, np.integer, np.floating)) \
                and float(deger) == float(aday):
            return aday
    raise YapilandirmaHatasi(f"{hipotez}.{parametre} = {deger!r} izgarada yok; on-kayit §5: {gecerli}.")


DEGER_ADLARI = MappingProxyType({
    "H1": ("pump_dip", "pump_hacim_6", "pump_hacim_medyani_180", "tepe", "pump_kapanis", "kapanis", "yuksek"),
    "H2": ("funding_24s", "kapanis_30_once", "kirilim_dip", "kapanis"),
    "H3": ("hacim_medyani_30g", "hacim_medyani_120_31", "sma50", "kapanis_30_once", "kapanis"),
})


CAPALI_HIPOTEZLER = ("H1",)


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
    return [a for a in gereken if not _sinyal_sonlu(degerler[a])]


def _sinyal_sonlu(deger) -> bool:
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
    _fiyatlari_dogrula(ad, d)
    if ad == "H1":
        pump = (d["pump_kapanis"] / d["pump_dip"] - 1 >= float(y["theta"])
                and d["pump_hacim_6"] >= config.H1_HACIM_CARPANI * d["pump_hacim_medyani_180"])
        teyit = d["kapanis"] <= d["tepe"] * (1 - float(y["delta"])) and d["yuksek"] < d["tepe"]
        return bool(pump and teyit)
    if ad == "H2":
        return bool(d["funding_24s"] >= float(y["phi"])
                    and d["kapanis"] / d["kapanis_30_once"] - 1 >= config.H2_YUKSELIS_ESIGI
                    and d["kapanis"] < d["kirilim_dip"])
    return bool(d["hacim_medyani_30g"] <= (1 - float(y["nu"])) * d["hacim_medyani_120_31"]
                and d["kapanis"] < d["sma50"]
                and d["kapanis"] / d["kapanis_30_once"] - 1 <= -float(y["tau"]))


FIYAT_DEGERLERI = {
    "H1": ("pump_dip", "tepe", "pump_kapanis", "kapanis", "yuksek"),
    "H2": ("kapanis_30_once", "kirilim_dip", "kapanis"),
    "H3": ("kapanis_30_once", "sma50", "kapanis"),
}


H1_PUMP_FIYATLARI = ("pump_dip", "pump_kapanis")


def _fiyatlari_dogrula(hipotez: str, degerler: dict[str, float]) -> None:
    """Hipotezin butun FIYAT degerleri sonlu ve pozitif olmali (madde 1b, bulgu 19)."""
    for a in FIYAT_DEGERLERI[hipotez]:
        _pozitif(degerler[a], f"{hipotez} sinyal degeri {a}")


def _pozitif(deger: float, ad: str) -> float:
    """On-kayit §5'teki oranlarin bolenleri pozitif bir FIYAT olmalidir; sifir ya da negatif bir
    fiyat bozuk veridir ve acik hata verir (`pencere.VeriHatasi`). Kapi bir olay-olusmaz kurali
    ICAT ETMEZ: on-kayit sifir ya da negatif fiyati tanimlamaz (Rev.9 D-C5 ile ayni tutum,
    `pozisyon._sonlu`). Veri denetlenmelidir."""
    if deger <= 0:
        raise pencere_modulu.VeriHatasi(
            f"{ad} pozitif bir fiyat olmali; verilen {deger!r}. On-kayit §5'teki oran bu degerle "
            "tanimsiz olurdu ve kapi kural icat etmez: veri denetlenmeli.")
    # Altnormal deger (madde 1b, bulgu 21): `pozisyon._pozitif_fiyat` ile ayni esik.
    if deger < sys.float_info.min:
        raise pencere_modulu.VeriHatasi(
            f"{ad} altnormal bir fiyat ({deger!r}); §5'teki oran onunla sonsuza gider. Veri denetlenmeli.")
    return deger


CAPASIZ_PENCERELER = MappingProxyType({
    "H1": ("dip", "hacim_6", "hacim_medyani_180"),
    "H2": ("kirilim_dip", "kapanis_30_once", "funding_24s"),
    "H3": ("hacim_medyani_30g", "hacim_medyani_120_31", "sma50", "kapanis_30_once"),
})


def capasiz_pencere_degerleri(hipotez, yapilandirma, t, *, mumlar_4h, gunluk, funding,
                              kume_baslangic, kume_bitis, donem_baslangic) -> dict[str, float]:
    """Hipotezin CAPASIZ sinyal pencereleri, t barinda (on-kayit §6 rev.12). Saf.

    Hesaplanamayan deger NaN'dir. Kosullar DEGERLENDIRILMEZ: bu fonksiyonun tek isi, kontrol
    barinda pencerelerin hesaplanabilir olup olmadigini soylemektir. H1'in tepe penceresi ve
    pump barinin kendi kapanisi (capali degerler) burada yoktur.
    """
    ad = _hipotez_dogrula(hipotez)
    y = yapilandirma_dogrula(ad, yapilandirma)
    sinir = {"kume_baslangic": kume_baslangic, "donem_baslangic": donem_baslangic}
    if ad == "H1":
        return {
            "dip": h1_dip(mumlar_4h, t, **sinir),
            "hacim_6": h1_hacim_6(mumlar_4h, t, **sinir),
            "hacim_medyani_180": h1_hacim_medyani_180(mumlar_4h, t, **sinir),
        }
    if ad == "H2":
        return {
            "kirilim_dip": h2_kirilim_dip(mumlar_4h, t, y["k"], **sinir),
            "kapanis_30_once": kapanis_30_once(mumlar_4h, t, config.BAR_4H, **sinir),
            "funding_24s": h2_funding_24s(funding, t, kume_baslangic=kume_baslangic,
                                          kume_bitis=kume_bitis, donem_baslangic=donem_baslangic),
        }
    return {
        "hacim_medyani_30g": h3_hacim_medyani_30g(gunluk, t, **sinir),
        "hacim_medyani_120_31": h3_hacim_medyani_120_31(gunluk, t, **sinir),
        "sma50": h3_sma50(gunluk, t, **sinir),
        "kapanis_30_once": kapanis_30_once(gunluk, t, config.BAR_1D, **sinir),
    }


def capasiz_hesaplanamayan(hipotez, degerler) -> list[str]:
    """Hesaplanamayan capasiz pencere adlari (on-kayit §6 rev.12). Saf."""
    ad = _hipotez_dogrula(hipotez)
    gereken = CAPASIZ_PENCERELER[ad]
    if set(degerler) != set(gereken):
        raise TypeError(f"{ad} icin capasiz pencereler tam olarak {gereken} olmali; eksik "
                        f"{sorted(set(gereken) - set(degerler))}, fazla {sorted(set(degerler) - set(gereken))}.")
    return [a for a in gereken if not _sinyal_sonlu(degerler[a])]


def gecersizlik_seviyesi(hipotez, t, *, mumlar_4h, gunluk, capa, kume_baslangic,
                         donem_baslangic) -> float:
    """Olayin gecersizlik (stop) seviyesi; hesaplanamazsa NaN. Saf.

    `capa` yalnizca H1'de verilir (pump bari) ve zorunludur; H2 ve H3'te `None` olmalidir --
    `sinyal_degerleri` ile ayni sozlesme. Taban pencereleri §2 "Tamlik sarti" kapsamindadir.
    """
    ad = _hipotez_dogrula(hipotez)
    if (capa is not None) != (ad in CAPALI_HIPOTEZLER):
        raise ValueError(
            f"{ad} icin capa {'zorunludur' if ad in CAPALI_HIPOTEZLER else 'verilemez'} "
            "(on-kayit §5 H1 madde 5: seviye tepeye, yani pump barina capalidir).")
    sinir = {"kume_baslangic": kume_baslangic, "donem_baslangic": donem_baslangic}
    if ad == "H1":
        taban = h1_tepe(mumlar_4h, capa, t, **sinir)
    elif ad == "H2":
        taban = yuksek_30_max(mumlar_4h, t, config.BAR_4H, **sinir)
    else:
        taban = yuksek_30_max(gunluk, t, config.BAR_1D, **sinir)
    if not _sinyal_sonlu(taban):
        return float("nan")
    # Taban bir FIYAT penceresinin en yuksek degeridir (madde 1b, bulgu 20): butun high'lar sifir
    # ya da negatifse seviye de sifir ya da negatif cikiyordu ve kapi bunu sessizce kaydediyordu.
    # Seviye yalnizca F4 icin kayittir ama bozuk veriyle kaydedilen bir stop seviyesi de kayittir.
    _pozitif(float(taban), f"{ad} gecersizlik seviyesinin tabani")
    return float(taban) * config.GECERSIZLIK_CARPANI


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
    if any(not _sinyal_sonlu(degerler[a]) for a in H1_PUMP_ADLARI):
        return None
    d = {a: float(degerler[a]) for a in H1_PUMP_ADLARI}
    for a in H1_PUMP_FIYATLARI:                     # madde 1b, bulgu 19
        _pozitif(d[a], f"H1 pump degeri {a}")
    return bool(d["pump_kapanis"] / d["pump_dip"] - 1 >= float(y["theta"])
                and d["pump_hacim_6"] >= config.H1_HACIM_CARPANI * d["pump_hacim_medyani_180"])


# ====================================================================================================
# data/pozisyon.py (4e63037) kopyasi
# ====================================================================================================


ROLLER = ("olay", "K1", "K2")


KONTROL_ROLLERI = ("K1", "K2")


def _close_time_nat_yok(mumlar: pd.DataFrame, ad: str) -> None:
    """`close_time` sutunu varsa hicbir satiri NaT olamaz. NaT ile yapilan sure karsilastirmasi her
    zaman False doner; NaT'li bir 1d cercevesi 4h denetiminden (ya da tersi) sessizce gecerdi
    (sizinti testcisinin Rev.10 hazirlik bulgusu 2; on-kayit §4 "Fiyat okuma tabani")."""
    if bool(pd.isna(mumlar["close_time"]).any()):
        raise pencere_modulu.VeriHatasi(f"{ad}: close_time sutununda NaT var; bar suresi dogrulanamaz "
                         "(on-kayit §4 'Fiyat okuma tabani').")


def _gunluk_hacim(gunluk_mumlar: pd.DataFrame) -> pd.Series:
    """Uygunluk hacminin girdisi: sembolun 1d serisi (`klines.mumlari_yukle(s, "1d", ...)`,
    tek 1d yolu `klines.gunluge_cevir`). 1d olmayan cerceve (ör. 4h mumlari) acik hata verir:
    acilislar gun basi olmali ve `close_time` varsa bar suresi 4 saati asmali."""
    if not isinstance(gunluk_mumlar, pd.DataFrame) or "open_time" not in gunluk_mumlar:
        raise TypeError("gunluk_mumlar sembolun 1d mum cercevesi olmali (open_time, quote_volume).")
    acilis = pencere_modulu._zaman_dizisi_dogrula(pd.DatetimeIndex(gunluk_mumlar["open_time"]), "gunluk_mumlar")
    if len(acilis) and not bool((acilis == acilis.floor("D")).all()):
        raise pencere_modulu.VeriHatasi("gunluk_mumlar 1d serisi olmali: acilislar UTC gun basi degil (4h cercevesi verilmis olabilir).")
    if "close_time" in gunluk_mumlar and len(acilis):
        _close_time_nat_yok(gunluk_mumlar, "gunluk_mumlar")
        sure = pd.DatetimeIndex(gunluk_mumlar["close_time"]) - acilis
        if bool((sure <= pencere_modulu.ADIM_4H).any()):
            raise pencere_modulu.VeriHatasi("gunluk_mumlar 1d serisi olmali: bar suresi 4 saati asmiyor.")
    return eligibility_modulu.gunluk_hacim_serisi(gunluk_mumlar)


def _mum_zamanlari(mumlar: pd.DataFrame) -> pd.DatetimeIndex:
    """Fiyat okuma tabaninin 4h serisi oldugunu denetler (on-kayit §4 rev.8 "Fiyat okuma
    tabani": pozisyonun butun fiyat okumalari her hipotezde donem ici 4h barlardan; denetci
    bulgusu D-B3). 1d cercevesi (ör. `klines.mumlari_yukle(s, "1d", ...)`) ayni sutun adlarini
    tasidigi icin sessizce kabul edilirse her cikis ileri kaymaya duser; burada acik hata verir:
      - acilislar 4h izgarasinda (gun basindan 0, 4, ..., 20 saat) olmali,
      - `close_time` varsa hicbir barin suresi 4 saati asmamali; yoksa en az iki bar olmali,
      - `close_time` YOKSA ardisik iki acilis arasindaki en kucuk fark 4 saat olmali.

    Ardisiklik sarti yalnizca `close_time` yoksa aranir (bulgu K-C8, koruma turu madde 7). Bar
    duzeyli mevcutluk olcutu (D-B3) bozuk hucreli barlari seriden DUSURUR; dar bir donemde geriye
    yalnizca komsu olmayan barlar kalirsa ardisiklik sarti `VeriHatasi` firlatiyordu -- yani bir
    ret gerekcesi yerine yukari cikan bir hata. Oysa eksik barin normal yolu rettir (`GirisBariYok`,
    tamlik). 4h serisi oldugunu dogrulayan asil olcutler IZGARA ve BAR SURESIDIR; ikisi de yerinde
    kalir, bu yuzden 1d cercevesinin 4h gibi verilmesi (D-B3'un amaci) yine yakalanir.
    """
    zamanlar = pencere_modulu._zaman_dizisi_dogrula(pd.DatetimeIndex(mumlar["open_time"]), "olay_karari")
    if len(zamanlar) == 0:
        return zamanlar
    adim = pencere_modulu.ADIM_4H
    if bool(((zamanlar - zamanlar.floor("D")) % adim != pd.Timedelta(0)).any()):
        raise pencere_modulu.VeriHatasi("mumlar_4h 4h izgarasinda degil (acilislar 00/04/08/12/16/20 UTC olmali).")
    if "close_time" not in mumlar and len(zamanlar) < 2:
        # Tek satirlik ve close_time'siz cerceve: gece yarisi acilisli bir 1d bari izgaraya uyar
        # ve ardisik fark olculemez; 4h serisi oldugu dogrulanamaz (sizinti testcisi bulgusu).
        raise pencere_modulu.VeriHatasi("mumlar_4h 4h serisi oldugu dogrulanamiyor: tek satir ve close_time yok "
                         "(on-kayit §4 'Fiyat okuma tabani').")
    if "close_time" in mumlar:
        _close_time_nat_yok(mumlar, "mumlar_4h")
        sure = pd.DatetimeIndex(mumlar["close_time"]) - zamanlar
        if bool((sure > adim).any()):
            raise pencere_modulu.VeriHatasi("mumlar_4h 4h serisi olmali: bar suresi 4 saati asiyor (1d cercevesi verilmis olabilir; "
                             "on-kayit §4 'Fiyat okuma tabani').")
    if "close_time" not in mumlar and len(zamanlar) > 1 and (zamanlar[1:] - zamanlar[:-1]).min() != adim:
        raise pencere_modulu.VeriHatasi("mumlar_4h 4h serisi olmali: ardisik acilislar arasinda 4 saatlik fark yok "
                         "(1d cercevesi verilmis olabilir; on-kayit §4 'Fiyat okuma tabani').")
    return zamanlar


def _bar_degeri(mumlar: pd.DataFrame, zamanlar: pd.DatetimeIndex, zaman: pd.Timestamp, alan: str) -> float:
    bar = pencere_modulu.ayni_andaki_bar(zamanlar, zaman)
    if bar is None:
        raise pencere_modulu.VeriHatasi(f"{zaman} bari mum cercevesinde yok (karar ile ayni seri verilmeli).")
    return float(mumlar[alan].to_numpy()[int(zamanlar.get_loc(bar))])


def _utc_sinyal_zamani(sinyal_zamani) -> pd.Timestamp:
    """Sinyal zamani UTC olmali (CLAUDE.md §5 "Tum zaman damgalari UTC"). Saat dilimi olan ama UTC olmayan
    bir zaman, uygunluk penceresinin gun sinirini yerel saate kaydirir ve H1/H2 olaylarini sessizce
    `UygunDegil` ile dusururdu (kapi sertlestirme turu 2, denetci KS D-B5; testle dogrulandi). Acik hata."""
    zaman = pencere_modulu.utc_zamani(sinyal_zamani, "sinyal_zamani")
    if zaman.utcoffset() != pd.Timedelta(0) or zaman.tzname() != "UTC":
        raise ValueError(f"sinyal_zamani UTC olmali; verilen saat dilimi {zaman.tzinfo!r} ({zaman}). "
                         "UTC'ye cevrilerek verilmeli (CLAUDE.md §5).")
    return zaman


def _sonlu(deger: float, ad: str) -> float:
    """Sonlu olmayan (NaN, +-inf) fiyat ya da funding degeri acik hatadir (`VeriHatasi`): on-kayit bu durumu tanimlamaz;
    kapi bir olay-olusmaz kurali icat etmez (kapi sertlestirme turu 2, sizinti testcisi inf bulgusu)."""
    if not math.isfinite(deger):
        raise pencere_modulu.VeriHatasi(f"{ad} sonlu degil ({deger!r}); pozisyon onaylanmaz. On-kayit sonlu olmayan veriyi "
                         "tanimlamaz: veri denetlenmeli.")
    return deger


def _pozitif_fiyat(deger: float, ad: str) -> float:
    """Kapinin okudugu FIYAT sonlu VE POZITIF olmali; aksi halde `VeriHatasi` (koruma turu madde 2b).

    Gerekce: sifir ya da negatif bir perpetual fiyati mesru bir piyasa durumu degil, bozuk
    veridir. Olculdu (`koruma_olcumu.py --olcum pozitif_fiyat`, butun evren, temiz agac): donem
    ici 3.378.942 4h barin HICBIRINDE open/high/low/close sifir ya da negatif degil (sembol 0).
    Olcum sifir cikmasi muafiyet degildir (RESULTS §14.13): kapi bu durumu sessizce "olay olusmaz"
    diye gecmez, acik hata verir. Bu bir KURAL degil HATA yoludur, bu yuzden on-kayit degisikligi
    gerektirmez (`sinyal._pozitif` ile ayni tutum; Rev.9 D-C5).

    P0 ≤ 0 ayrica MAE'yi (`max(H, P1) / P0 - 1`) sifira bolmeye goturuyordu (sizinti bulgusu).

    ALTNORMAL deger de reddedilir (F1 kapatma turu madde 1b, bulgu 21): 1e-320 sonlu ve
    pozitiftir, ama `max(H, P1) / P0 - 1` orani onunla SONSUZA gider. Esik `sys.float_info.min`
    (yaklasik 2.2e-308); gercek bir perpetual fiyati bu buyuklugun yanina yaklasmaz (en kucuk
    tick 1e-8 duzeyindedir), bu yuzden esik hicbir mesru fiyati dislamaz. Bu da bir KURAL degil
    HATA yoludur.
    """
    _sonlu(deger, ad)
    if deger <= 0:
        raise pencere_modulu.VeriHatasi(
            f"{ad} pozitif bir fiyat olmali; verilen {deger!r}. Sifir ya da negatif fiyat bozuk veridir ve "
            "on-kayitta tanimlanmaz: kapi kural icat etmez, veri denetlenmeli (RESULTS §14.33).")
    if deger < sys.float_info.min:
        raise pencere_modulu.VeriHatasi(
            f"{ad} altnormal bir fiyat ({deger!r}); normal cift duyarlikli en kucuk degerin "
            f"({sys.float_info.min!r}) altinda. Boyle bir fiyat bozuk veridir ve oranlari sonsuza "
            "goturur (madde 1b, bulgu 21): veri denetlenmeli.")
    return deger


def _mae_tepesi(mumlar_4h: pd.DataFrame, zamanlar: pd.DatetimeIndex, plan, p1: float) -> float:
    """MAE'nin H'si (on-kayit §4 rev.8): giris anindan once acilmayan, cikis anindan sonra kapanmayan donem
    ici 4h barlarin en yuksek high'i ile P1'in buyugu. Secilen high'lar sonlu VE POZITIF olmali
    (`_pozitif_fiyat`; koruma turu madde 2b)."""
    kapanislar = zamanlar + pencere_modulu.ADIM_4H
    secim = (np.asarray(pencere_modulu.ayni_ya_da_sonra(zamanlar, plan.giris), dtype=bool)
             & np.asarray(pencere_modulu.ayni_ya_da_once(kapanislar, plan.cikis_ani), dtype=bool)
             & np.asarray(pencere_modulu.donem_ici_4h_maskesi(
                 zamanlar, donem_baslangic=plan.donem_baslangic, donem_bitis=plan.donem_bitis), dtype=bool))
    tepe = p1
    if secim.any():
        yuksekler = mumlar_4h["high"].to_numpy(dtype=float)[secim]
        for deger in yuksekler:
            _pozitif_fiyat(float(deger), "pozisyon penceresindeki high")
        tepe = max(float(np.max(yuksekler)), p1)
    return tepe


def _rol_dogrula(rol) -> str:
    """Bar hangi rolde karar noktasina geliyor (on-kayit §6 rev.11)? Bilinmeyen rol programlama
    hatasidir; `str` alt sinifi da reddedilir (`__eq__` ile yalan soyleyebilir)."""
    if type(rol) is not str:
        raise TypeError(f"rol bir rol adi olmali {ROLLER}; verilen: {rol!r}")
    if rol not in ROLLER:
        raise ValueError(f"Bilinmeyen rol {rol!r}; gecerli: {ROLLER} (on-kayit §6 rev.11 "
                         "'Kontrolun ne olctugu').")
    return rol


def _capa_dogrula(hipotez: str, rol: str, capa):
    """Capa (H1'in pump bari) bu hipotez ve rolde verilmeli mi? (on-kayit §5 H1, §6 rev.11)

    Capa YALNIZCA H1'in olay rolunde verilir: H1'in sinyali bir pump barina capalidir. Kontrol
    rollerinde capa verilemez, cunku "H1'in kontrol barinda pump bari, dip penceresi ve tepe
    aranmaz". H2 ve H3'un butun degerleri t barindan hesaplanir, onlarda capa hicbir rolde
    verilemez. Capa bir deger degil bir BAR ZAMANIDIR ve kapi onu ayrica dogrular: pump kosulu
    capada yeniden hesaplanir (`sinyal.kosullar_saglandi`), yani cagiran uydurma bir capayla
    olay uretemez.
    """
    capali = hipotez in sinyal_modulu.CAPALI_HIPOTEZLER and rol == "olay"
    if capali:
        if capa is None:
            raise TypeError(f"{hipotez} olay rolunde capa (pump bari) zorunludur (on-kayit §5 H1).")
        return pencere_modulu.utc_zamani(capa, "capa")
    if capa is not None:
        raise TypeError(f"{hipotez} / rol {rol} icin capa verilemez (on-kayit §6 rev.11: kontrol "
                        "barinda pump bari aranmaz; H2 ve H3 t barindan hesaplanir).")
    return None


def olay_karari(
    sinyal_zamani,
    ufuk: int,
    bar: str,
    *,
    hipotez: str,
    yapilandirma,
    rol: str,
    capa,
    birincil_ufuk: int,
    kume: str,
    sembol: str,
    donem_no: int,
    asgari_hacim,
    asgari_listeleme_yasi_gun,
) -> OnaylanmisPozisyon:
    """TEK KARAR NOKTASI (on-kayit §4 rev.8, rev.9). Olay ya da kontrol olusursa
    `OnaylanmisPozisyon`, olusmazsa `OlayOlusmaz` alt sinifi (ret gerekcesi:
    `pencere.ret_gerekcesi`). Olaylar ve kontroller ayni cagriyi kullanir.

    Fiyat, funding ve 1d cerceveleri cagirandan alinmaz: kapi `sembol` ve `kume` ile yukler
    (`_kume_verisi`), 1d serisini 4h barlardan turetir (`klines.gunluge_cevir`). `sinyal_zamani` UTC
    olmali; sinyal bari hipotezin izgarasinda donem ici seride bulunmali (`SinyalBariYok`). Sonlu
    olmayan fiyat ya da funding toplami acik hatadir.

    SINYAL DEGERLERI CAGIRANDAN ALINMAZ (Rev.11 madde 4): kapi hipotezin butun sinyal degerlerini
    `data.sinyal`in pencere kuruculariyla kendisi hesaplar. `yapilandirma`: hipotezin izgarasindaki
    bir parametre demeti (on-kayit §5 rev.11; izgarada olmayan demet `sinyal.YapilandirmaHatasi`).
    `rol`: "olay", "K1" ya da "K2" (modul aciklamasindaki "Rol" basligi). `capa`: yalnizca H1'in
    olay rolunde pump bari, baska her durumda `None` (`_capa_dogrula`).
    `asgari_hacim`, `asgari_listeleme_yasi_gun`:
    uygunluk esikleri, on-kayit §2 degerleri olmalidir (`eligibility.esikleri_dogrula`).
    `hipotez` ("H1", "H2", "H3") zorunludur: `bar`, `ufuk` ve `birincil_ufuk` hipotezden tureyen on-kayit
    degerleriyle uyumlu olmalidir (`pencere.hipotez_baglamini_dogrula`; F2 kodu bunlari
    `pencere.hipotez_ufuklari`ndan okur). Onayli pozisyon hipotezi imzali tasir.
    Butun sinirlar ve esikler zorunlu anahtar sozcuktur; varsayilan yoktur. `kume`: kumenin ADI
    ("KESIF", "C1", "C2"); sinirlari kapi `split.kume_araligi`ndan kendisi okur (`kume_sinirlari`),
    cagiran sinir vermez. `sembol`, `donem_no`: evren tablosundaki listeleme donemi (`donem_id`);
    donem sinirlari kapida tablodan okunur (`donem_kaydi`), cagiran sinir vermez. Sembolun A/B grubu
    (bolme tablosu) kumenin gruplarindan biri olmalidir (`grup_dogrula`).
    """
    # Hipotez -> izgara -> ufuk bagi (on-kayit §4 "Ufuk degerlerinin baglanmasi", rev.10; F1 kapanis
    # turu, denetci D-B2): izgara ve ufuklar hipotezden turer; uyumsuz eslesme calisma aninda hata.
    pencere_modulu.hipotez_baglamini_dogrula(hipotez, bar, ufuk, birincil_ufuk)
    # Yapilandirma ve rol (on-kayit §5, §6 rev.11): "Olay ya da kontrol ureten her cagri, hipotezi
    # ve yapilandirmayi birlikte alir; izgarada bulunmayan bir parametre demeti hata verir."
    gecerli_yapilandirma = sinyal_modulu.yapilandirma_dogrula(hipotez, yapilandirma)
    yapilandirma_kimligi = sinyal_modulu.yapilandirma_kimligi(hipotez, gecerli_yapilandirma)
    rol = _rol_dogrula(rol)
    capa = _capa_dogrula(hipotez, rol, capa)
    # Olayin olusup olusmadigi BIRINCIL ufukta belirlenir (kapi sertlestirme turu 3, denetci KS2 D-B3; on-kayit
    # §4 "Ufuk degerlerinin baglanmasi": "Ikincil ufuklar yalnizca raporlanir; onay kararlari birincil ufka
    # gore verilir"). Ikincil ufuk istenirse ayni cagri once birincil ufukla degerlendirilir; orada olay
    # olusmazsa ayni ret gerekcesi yukari cikar ve hicbir ikincil ufukta onay verilmez. Birincil ufukta olusan
    # olayin ikincil cikisi ayrica kendi ufuk uzunluguyla kurallara tabidir (on-kayit §3 "Kume siniri ve ufuk").
    if ufuk != birincil_ufuk:
        olay_karari(sinyal_zamani, birincil_ufuk, bar, hipotez=hipotez, yapilandirma=gecerli_yapilandirma,
                    rol=rol, capa=capa, birincil_ufuk=birincil_ufuk, kume=kume, sembol=sembol,
                    donem_no=donem_no, asgari_hacim=asgari_hacim,
                    asgari_listeleme_yasi_gun=asgari_listeleme_yasi_gun)
    sinyal_zamani = _utc_sinyal_zamani(sinyal_zamani)
    # Kume sinirlari cagirandan alinmaz; kume adindan kapida okunur (kapi sertlestirme turu, denetci F1K2
    # D-B1; on-kayit §3 "Kume siniri ve geriye bakis": "kod duzeyinde ayrica dogrulanir"). Serbest sinir
    # cifti, karisik sinir (ör. KESIF basi + C2 sonu) ya da None verilemez.
    kume_baslangic, kume_bitis = kume_sinirlari(kume)
    # Onay baglami (kapi sertlestirme turu 3, denetci KS2 D-B1): C1/C2 pozisyonu yalnizca ayni (hipotez, kume)
    # ciftinin acik onay kosusunda; acik kosu varken baska pozisyon yok. Uyusmazlik `split.OnayUyusmazligi`.
    split_modulu.onay_baglami_dogrula(hipotez, kume, yapilandirma_kimligi)
    # KESIF karar noktasi acik bir kesif kosusu ister (RESULTS §14.42, denetci D-C1).
    split_modulu.kesif_baglami_dogrula(kume)
    # Donem sinirlari da cagirandan alinmaz; commit edilmis evren tablosundan sembol ve donem numarasiyla
    # okunur (kapi sertlestirme turu, denetci F1K2 D-B2; on-kayit §2 "Listeleme donemi", "Evren tablosunun
    # sabitlenmesi": "analiz bu dosyadan okur"). Sembolun grubu kumeye ait olmali (on-kayit §3 "Coin bolmesi").
    donem_baslangic, donem_bitis, donem_funding_yok = donem_kaydi(sembol, donem_no)
    grup_dogrula(sembol, kume)
    # Uygunluk girdileri her cagrida denetlenir (programlama hatasi, ret gerekcesi degil).
    eligibility_modulu.esikleri_dogrula(bar, asgari_hacim=asgari_hacim,
                                        asgari_listeleme_yasi_gun=asgari_listeleme_yasi_gun)
    # Veri kapida yuklenir (kapi sertlestirme turu 2, denetci KS D-B1, KS D-B2): cagiran cerceve vermez.
    # Kesim ve 1d turetmesi `_karar_verisi`dedir: donem kurali TEK mekanizmada durur (P-C1) ve
    # `sinyal_kosulu` ayni fonksiyonu cagirir, yani dizi durumu ile kapinin onayi ayni veriden gelir.
    # 1d serisi tektir ve donem ici 4h barlardan turetilir (on-kayit §2 rev.8 "1 gunluk barlar": "Bu seri
    # tektir: H3'un sinyal pencereleri, butun hipotezlerin uygunluk hacmi ve K1/K2 havuzlarinin 1d barlari
    # ayni seriden gelir").
    mumlar_4h, funding, gunluk_mumlar = _karar_verisi(
        sembol, kume, kume_baslangic=kume_baslangic, kume_bitis=kume_bitis,
        donem_baslangic=donem_baslangic, donem_bitis=donem_bitis)
    zamanlar = _mum_zamanlari(mumlar_4h)
    gunluk_hacim = _gunluk_hacim(gunluk_mumlar)

    plan = pencere_modulu.pozisyon_plani(
        zamanlar, sinyal_zamani, ufuk, bar, birincil_ufuk=birincil_ufuk, kume_baslangic=kume_baslangic,
        kume_bitis=kume_bitis, donem_baslangic=donem_baslangic, donem_bitis=donem_bitis)
    # Sinyal bari t seride olmali (kapi sertlestirme turu 2, denetci KS D-B3): plan yalnizca t+1'i arar.
    # 4h: t acilisli donem ici bar; 1d: t gunu turetilmis 1d serisinde (alti 4h barin tamami donem ici).
    if bar == config.BAR_4H:
        t_bari = pencere_modulu.ayni_andaki_bar(zamanlar, plan.sinyal_zamani)
    else:
        t_bari = pencere_modulu.ayni_andaki_bar(pd.DatetimeIndex(gunluk_mumlar["open_time"]), plan.sinyal_zamani)
    if t_bari is None:
        raise SinyalBariYok(f"{sembol}: sinyal bari {plan.sinyal_zamani} ({bar}) donem ici seride yok; olay ya da "
                            "kontrol olusmaz.")
    # Sinyal degerleri KAPIDA hesaplanir (Rev.11 madde 4; on-kayit §5 "Pencere sinirlari"). Kume ve
    # donem sinirlari plandan okunur; pencerelerin tamlik, donem ve kume kurallari `data.sinyal`
    # uzerinden `data.pencere`nin tek kapisindan gecer. H2'nin funding penceresi de burada, gercek
    # funding serisinden kurulur (`funding.funding_ortalamasi`).
    # Kontrol barinda CAPASIZ sinyal pencereleri hesaplanabilir olmali (on-kayit §6 "Kontrol barinda
    # sinyal pencereleri", rev.12): "hesaplanamiyorsa o bar kontrol olamaz ... her iki kontrol kumesi
    # icin gecerlidir". Kosullar aranmaz; yalnizca hesaplanabilirlik. H1'in tepe penceresi capali
    # oldugu icin kontrol barinda aranmaz.
    if rol in KONTROL_ROLLERI:
        capasiz = sinyal_modulu.capasiz_pencere_degerleri(
            hipotez, gecerli_yapilandirma, plan.sinyal_zamani, mumlar_4h=mumlar_4h,
            gunluk=gunluk_mumlar, funding=funding, kume_baslangic=plan.kume_baslangic,
            kume_bitis=plan.kume_bitis, donem_baslangic=plan.donem_baslangic)
        capasiz_eksik = sinyal_modulu.capasiz_hesaplanamayan(hipotez, capasiz)
        if capasiz_eksik:
            raise SinyalPenceresiTamDegil(
                f"Kontrol barinda capasiz sinyal penceresi tam degil: {capasiz_eksik} (on-kayit §6 "
                f"rev.12); {plan.sinyal_zamani} barinda kontrol olusmaz.")
    # Sinyal KOSULLARI yalnizca olay rolunde hesaplanir (on-kayit §6, rev.12): "Kontrol barinda
    # sinyal kosullari hicbir amacla hesaplanmaz. K2'nin 'o anda olay uretmemis' sarti, kosullarin
    # saglanip saglanmadigina degil, o barin ayni yapilandirmanin olusmus olay kumesinde bulunup
    # bulunmadigina gore uygulanir (§6 'Ornekleme kurallari'). Kontrol barinda hesaplanan tek sey,
    # capasiz pencerelerin hesaplanabilirligidir." Bu yuzden rev.11'in `OlayUretmis` ret gerekcesi ve
    # H1'in K2 istisnasi konusuz kalmistir: uc hipotez ayni yolu kullanir.
    gecersizlik = float("nan")   # kontrol barinda tanimsiz (asagida yalnizca olay rolunde kurulur)
    if rol == "olay":
        degerler = sinyal_modulu.sinyal_degerleri(
            hipotez, gecerli_yapilandirma, plan.sinyal_zamani, mumlar_4h=mumlar_4h,
            gunluk=gunluk_mumlar, funding=funding, capa=capa, kume_baslangic=plan.kume_baslangic,
            kume_bitis=plan.kume_bitis, donem_baslangic=plan.donem_baslangic)
        hesaplanamayan = sinyal_modulu.hesaplanamayan(hipotez, degerler)
        if hesaplanamayan:
            raise SinyalPenceresiTamDegil(
                f"Sinyal penceresi tam degil: {hesaplanamayan} (on-kayit §2 'Tamlik sarti'); "
                f"{plan.sinyal_zamani} barinda olay olusmaz.")
        if not sinyal_modulu.kosullar_saglandi(hipotez, gecerli_yapilandirma, degerler):
            raise SinyalKosuluSaglanmadi(
                f"{hipotez} kosullari {plan.sinyal_zamani} barinda saglanmadi (on-kayit §5); olay olusmaz.")
        # Gecersizlik seviyesi (on-kayit §5 H1 madde 5, H2 madde 4, H3 madde 4 rev.13): olay basina
        # kayit, F4 icin. Tabani (H1'de tepe, H2/H3'te `max(high[t-30..t])`) olayin kosullarinin
        # zaten kullandigi penceredir, bu yuzden kosullari saglayan bir barda her zaman hesaplanir;
        # hesaplanamazsa acik hatadir (kapi sertlestirme turu 2 ile ayni tutum, `_sonlu`).
        gecersizlik = _sonlu(sinyal_modulu.gecersizlik_seviyesi(
            hipotez, plan.sinyal_zamani, mumlar_4h=mumlar_4h, gunluk=gunluk_mumlar, capa=capa,
            kume_baslangic=plan.kume_baslangic, donem_baslangic=plan.donem_baslangic),
            "gecersizlik seviyesi")
    # Uygunluk (on-kayit §4 rev.9): esik gecilmeli, hesaplanabilmis olmasi yetmez.
    if not eligibility_modulu.uygunluk_karari(
            gunluk_hacim, plan.sinyal_zamani, bar, donem_baslangic=plan.donem_baslangic,
            donem_bitis=plan.donem_bitis, kume_baslangic=plan.kume_baslangic, asgari_hacim=asgari_hacim,
            asgari_listeleme_yasi_gun=asgari_listeleme_yasi_gun):
        raise UygunDegil(f"Sinyal bari {plan.sinyal_zamani} ({bar}) uygun degil: listeleme yasi ya da medyan "
                         "hacim esigi gecilmiyor (on-kayit §2 'Uygunluk').")
    # On-kayit §2 "Funding'i bulunmayan donemler": hic funding kaydi olmayan donem hicbir hipotezde olay ya da
    # kontrol uretmez. Cagiranin verdigi funding cercevesinden bagimsiz olarak tablodaki bayraktan uygulanir.
    if donem_funding_yok:
        raise FundingTamDegil(f"{sembol} donem {donem_no}: evren tablosunda funding kaydi yok (on-kayit §2 "
                              "'Funding'i bulunmayan donemler'); olay ya da kontrol olusmaz.")
    ayrinti = funding_modulu.pozisyon_funding_ayrintisi(funding, plan)
    if not bool(ayrinti["tam"]):
        raise FundingTamDegil(f"Pozisyonun funding'i tam degil: giris {plan.giris}, cikis {plan.cikis_ani} "
                              f"({plan.cikis_turu}); olay brut dahil hicbir hesapta olusmaz.")
    toplam = funding_modulu._plan_fundingi(funding, plan)
    if math.isnan(toplam):
        raise FundingTamDegil(f"Pozisyonun funding'i hesaplanamadi (oran NaN): giris {plan.giris}.")
    # Sonlu olmayan degerler (kapi sertlestirme turu 2): +-inf funding toplami, fiyat ve MAE penceresi.
    _sonlu(toplam, "funding toplami")
    p0 = _pozitif_fiyat(_bar_degeri(mumlar_4h, zamanlar, plan.giris, "open"), "P0")
    p1 = _pozitif_fiyat(_bar_degeri(mumlar_4h, zamanlar, plan.cikis.zaman, plan.cikis.fiyat_alani), "P1")
    _mae_tepesi(mumlar_4h, zamanlar, plan, p1)
    sonuc = OnaylanmisPozisyon(plan, p0, p1, toplam, kuyruk_kismi=bool(ayrinti["kuyruk_kismi"]),
                               son_esitlik_affi=bool(ayrinti["son_esitlik_affi"]),
                               capa_aralik_saat=float(ayrinti["capa_aralik_saat"]),
                               son_aralik_saat=float(ayrinti["son_aralik_saat"]), tek_ritim=bool(ayrinti["tek_ritim"]),
                               funding_ritmi_saat=float(ayrinti["funding_ritmi_saat"]),
                               karisik_ritim=bool(ayrinti["karisik_ritim"]),
                               ritim_sinifi=ayrinti["ritim_sinifi"],
                               gecersizlik_seviyesi=gecersizlik, hipotez=hipotez,
                               yapilandirma=yapilandirma_kimligi, rol=rol, capa=capa, sembol=sembol,
                               kume=kume, donem_no=int(donem_no))
    return sonuc  # REFERANS: imzalanmaz (modul aciklamasi, degisiklik 3)


def sinyal_kosulu(t, *, hipotez: str, yapilandirma, capa, kume: str, sembol: str, donem_no: int):
    """Hipotezin §5'teki sinyal kosullari t barinda saglandi mi? `True` / `False` / `None`.

    `None` = deger hesaplanamadi (on-kayit §2 "Tamlik sarti"). Bu fonksiyon `data.dizi`nin
    `kosul` argumanidir: olay dizisi kurallari (bekleme suresi, H1'de tek izleme, H3'te "ilk
    gun"; on-kayit §5 rev.11) bar bar bunu sorar, sonra kapiyi (`olay_karari`) cagirir.

    Veri kapiyla AYNI yoldan yuklenir (`_kume_verisi`, `klines.gunluge_cevir`); sinirlar kume
    adindan ve evren tablosundan okunur, cagiran sinir vermez. Degerler `data.sinyal`in pencere
    kuruculariyla hesaplanir.

    H1 iki adimlidir (on-kayit §5 H1): `capa=None` cagrisi madde 1'in PUMP kosulunu sorar
    (`sinyal.h1_pump_saglandi`), `capa=p` cagrisi p capali madde 3'un TEYIT kosulunu sorar.
    H2 ve H3'te `capa` her zaman `None`'dir.

    Bu fonksiyon KARAR VERMEZ: uygunluk, dönem üyeliği, plan ve funding tamligi yalnizca
    `olay_karari`dadir (on-kayit §4 "tek karar noktasi"). Getiri hesaplamaz, deger raporlamaz.
    """
    bar = pencere_modulu.hipotez_izgarasi(hipotez)
    gecerli = sinyal_modulu.yapilandirma_dogrula(hipotez, yapilandirma)
    zaman = _utc_sinyal_zamani(t)
    kume_baslangic, kume_bitis = kume_sinirlari(kume)
    split_modulu.onay_baglami_dogrula(hipotez, kume, sinyal_modulu.yapilandirma_kimligi(hipotez, gecerli))
    split_modulu.kesif_baglami_dogrula(kume)  # RESULTS §14.42, denetci D-C1
    donem_baslangic, donem_bitis, _ = donem_kaydi(sembol, donem_no)
    grup_dogrula(sembol, kume)
    # Veri kume araligina VE DONEME kesilir (bulgu K-B1; on-kayit §2 "Listeleme donemi": "Donem
    # disindaki hiçbir bar ... hicbir hesaba girmez"). Rev.13'te yalnizca kume araligina
    # kesiliyordu: donem bitisinden SONRAKI bir t icin kosul hesaplanabiliyor ve penceresi
    # donemler arasi barlari (dolgu barlari, sonraki donemin barlari) icerebiliyordu. Sonucu
    # olay kumesini de etkiler, cunku dizi durumu (H1 izlemesi, H3 dizisi) kosulun sonucuna
    # gore degisir -- kapinin onayina degil (rev.13: "dizi kosullarla tanimlidir").
    #
    # Kesim KAPIYLA AYNI fonksiyondan gelir (`_karar_verisi`; P-C1): kural iki ayri mekanizmada
    # degil tek yerde durur.
    mumlar_4h, funding, gunluk_mumlar = _karar_verisi(
        sembol, kume, kume_baslangic=kume_baslangic, kume_bitis=kume_bitis,
        donem_baslangic=donem_baslangic, donem_bitis=donem_bitis)
    _mum_zamanlari(mumlar_4h)
    sinir = {"kume_baslangic": kume_baslangic, "donem_baslangic": donem_baslangic}

    if hipotez in sinyal_modulu.CAPALI_HIPOTEZLER and capa is None:
        degerler = sinyal_modulu.h1_pump_degerleri(mumlar_4h, zaman, **sinir)
        return sinyal_modulu.h1_pump_saglandi(gecerli, degerler)

    try:
        degerler = sinyal_modulu.sinyal_degerleri(
            hipotez, gecerli, zaman, mumlar_4h=mumlar_4h, gunluk=gunluk_mumlar, funding=funding,
            capa=capa, kume_bitis=kume_bitis, **sinir)
    except sinyal_modulu.TepePenceresiKurulamaz:
        # Tepe penceresi bu (pump, teyit) cifti icin TANIMSIZ (ör. teyit bari pump barindan 12
        # bardan uzak): izleme kurallari bu bari teyit adayi saymaz; kosul hesaplanamaz.
        #
        # Yakalama rev.13'te daraltildi (denetci bulgusu D-C2): eskiden `except ValueError` idi ve
        # `pencere.VeriHatasi` ile `ZamanDizisiHatasi` da (ikisi de `ValueError` alt sinifi) bu
        # yoldan sessizce "kosul hesaplanamaz" oluyordu. Veri hatasi bir ret gerekcesi DEGILDIR:
        # `pencere.OlayOlusmaz` ailesinden ayridir ve yukari cikmalidir (`pencere.VeriHatasi`
        # aciklamasi; `sinyal._pozitif` ile ayni tutum).
        return None
    if sinyal_modulu.hesaplanamayan(hipotez, degerler):
        return None
    return sinyal_modulu.kosullar_saglandi(hipotez, gecerli, degerler)
