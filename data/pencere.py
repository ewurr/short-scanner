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


# --- Tamlik ------------------------------------------------------------------


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
    son = pd.Timestamp(t) if t_dahil else pd.Timestamp(t) - adim(bar)
    return pd.date_range(end=son, periods=bar_sayisi, freq=adim(bar))


def pencere_tam_mi(zamanlar, t, bar_sayisi: int, bar: str, *, t_dahil: bool) -> bool:
    """Penceredeki beklenen barlarin TAMAMI mevcut mu? (on-kayit §2 rev.3)

    Tek bir bar eksikse False doner; cagiran taraf degeri hesaplamaz.
    """
    beklenen = beklenen_zamanlar(t, bar_sayisi, bar, t_dahil=t_dahil)
    mevcut = pd.DatetimeIndex(zamanlar)
    return bool(beklenen.isin(mevcut).all())


def _kume_baslangic_dogrula(kume_baslangic) -> pd.Timestamp | None:
    """On-kayit §3 rev.5: kume baslangici cagiran tarafindan acikca verilir.

    Varsayilan yoktur; anahtar sozcuk unutulursa Python TypeError verir. Deger
    ya bir zaman damgasidir (`split.kume_araligi(kume)[0]`) ya da bilincli
    olarak `None`'dir. `None` yalnizca bir kumeye ait olmayan hesaplar icindir
    (ör. tum gecmisi olcen F1 veri denetimi); F2 ve F3 hesaplari kume
    baslangicini vermek zorundadir.
    """
    if kume_baslangic is None:
        return None
    if isinstance(kume_baslangic, bool):
        raise TypeError(
            "kume_baslangic bir zaman damgasi ya da acikca None olmali "
            f"(on-kayit §3 rev.5). Verilen: {kume_baslangic!r}"
        )
    return pd.Timestamp(kume_baslangic)


def pencere_dilimi(
    seri: pd.Series,
    t,
    bar_sayisi: int,
    bar: str,
    *,
    t_dahil: bool,
    kume_baslangic,
    donem_baslangic=None,
    karantina_aylari=(),
) -> pd.Series | None:
    """Zamanla tanimli pencereyi doner; kurallardan biri saglanmazsa None.

    Sirasiyla su kosullar aranir:
      1. Pencere donem baslangicini asmamali (on-kayit §2 rev.2),
      2. Pencere kume baslangicini asmamali (on-kayit §3 rev.5),
      3. Pencerenin hicbir bari karantina ayina dusmemeli,
      4. Penceredeki beklenen barlarin tamami mevcut olmali (rev.3 tamlik sarti).

    Kume siniri, seride kume oncesi veri BULUNSA BILE uygulanir: kural verinin
    kume sinirinda kesilmis olmasina dayanmaz. `kume_baslangic` zorunludur.
    """
    kume_bas = _kume_baslangic_dogrula(kume_baslangic)
    beklenen = beklenen_zamanlar(t, bar_sayisi, bar, t_dahil=t_dahil)

    if donem_baslangic is not None:
        if beklenen[0] < pd.Timestamp(donem_baslangic):
            return None

    if kume_bas is not None and beklenen[0] < kume_bas:
        return None  # pencere kume oncesi veriyi odunc alamaz (rev.5)

    if len(karantina_aylari):
        karantina = {donem_modulu.ay_donemi(a) for a in karantina_aylari}
        if any(pd.Period(t, freq="M") in karantina for t in beklenen):
            return None

    indeks = _zaman_dizisi_dogrula(seri.index, "pencere_dilimi")
    if not beklenen.isin(indeks).all():
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
    islev="median",
    donem_baslangic=None,
    karantina_aylari=(),
) -> float:
    """Zamanla tanimli pencereye bir toplayici uygular; kural ihlalinde NaN.

    `islev` bir Series metodu adi ("median", "mean", "min", "max", "sum") ya da
    Series alan bir cagrilabilirdir. `t_dahil` (on-kayit §5 rev.4) ve
    `kume_baslangic` (on-kayit §3 rev.5) zorunludur.
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


# --- Giris ve cikis ----------------------------------------------------------


def giris_bari(zamanlar, sinyal_zamani, bar: str) -> pd.Timestamp | None:
    """t+1 barinin zamani; o bar eksikse None (on-kayit §2 rev.3: olay olusmaz).

    Gelecege bakis yoktur: sinyal t barinin kapanisinda hesaplanir, islem t+1
    barinin acilisinda acilir (CLAUDE.md §3.6).
    """
    hedef = pd.Timestamp(sinyal_zamani) + adim(bar)
    return hedef if hedef in pd.DatetimeIndex(zamanlar) else None


def _karantina_siniri(giris: pd.Timestamp, karantina_aylari) -> pd.Timestamp | None:
    """Giristen sonraki ilk karantina ayinin baslangicindan hemen onceki an.

    Hicbir cikis (ileri kaymali olan dahil) bu anin otesine gecemez. Giris bir
    karantina ayinin icindeyse ValueError: karantina ayinda olay olamaz
    (on-kayit §2 rev.2).
    """
    if not len(karantina_aylari):
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


def cikis_bari(
    zamanlar,
    giris_zamani,
    ufuk: int,
    bar: str,
    donem_bitis=None,
    karantina_aylari=(),
    kume_bitis=None,
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
    - `kume_bitis` verilirse (on-kayit §3 rev.4): cikis bari t+h ya da ileri
      kaymali cikis bari kume sonunu asiyorsa `KumeSiniriHatasi` firlatilir.
      Kume sinirinda kirpma YAPILMAZ; komsu kumeden veri okunmaz. Kume icinde
      verinin gercekten bitmesi (delist) ise §4 uyarinca kirpilmaya devam eder.

    Getiri HESAPLAMAZ; yalnizca cikis barini ve hangi fiyat alanindan
    okunacagini soyler.
    """
    indeks = _zaman_dizisi_dogrula(zamanlar, "cikis_bari")
    if len(indeks) == 0:
        raise ValueError("Bar listesi bos.")
    giris = pd.Timestamp(giris_zamani)
    if giris not in indeks:
        raise KeyError(f"Giris bari seride yok: {giris}")
    if ufuk < 1:
        raise ValueError(f"ufuk en az 1 bar olmali: {ufuk}")

    # giris = t+1; cikis bari t+h = giris + (h-1) x adim (on-kayit §4).
    hedef = giris + (ufuk - 1) * adim(bar)

    kume_son = pd.Timestamp(kume_bitis) if kume_bitis is not None else None
    if kume_son is not None and hedef > kume_son:
        raise KumeSiniriHatasi(
            f"Ufuk kume sinirini asiyor: cikis bari {hedef} > kume sonu {kume_son} "
            "(on-kayit §3 rev.4: olay bu kumede olusmaz)"
        )

    adaylar: list[tuple[pd.Timestamp, str]] = []
    karantina_siniri = _karantina_siniri(giris, karantina_aylari)
    if karantina_siniri is not None:
        adaylar.append((karantina_siniri, "karantina"))
    if donem_bitis is not None:
        adaylar.append((pd.Timestamp(donem_bitis), "donem_sonu"))
    adaylar.append((indeks[-1], "seri_sonu"))
    sinir, sinir_nedeni = min(adaylar, key=lambda aday: aday[0])

    def _kirp() -> CikisSonucu:
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
    if kume_son is not None and ilk > kume_son:
        raise KumeSiniriHatasi(
            f"Ileri kayma kume sinirini asiyor: {ilk} > kume sonu {kume_son} "
            "(on-kayit §3 rev.4: kumeler arasi veri odunc alinmaz)"
        )
    return CikisSonucu(
        indeks=int(np.flatnonzero(indeks == ilk)[0]),
        zaman=ilk,
        fiyat_alani="open",
        kaydi=True,
        kirpildi=False,
    )
