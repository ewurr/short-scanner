"""t anindaki uygunluk filtresi (on-kayit §2, CLAUDE.md §3.6).

Kosullar:
  - Listeleme yasi >= 30 gun (donem basinda sifirlanir, on-kayit rev.2),
  - H1, H2 (4h bar) : son 30 gunun medyan gunluk hacmi >= 10.000.000 USDT,
  - H3 (1d bar)     : son 30 gunun medyan gunluk hacmi >=  2.000.000 USDT.

Gelecege bakis yoktur: t anindaki uygunluk yalnizca t'ye kadar (t dahil) kapanmis
gunlerin verisiyle hesaplanir. Gunluk hacim, on-kayit rev.2 uyarinca 4h barlardan
turetilen gunluk veriden gelir (bkz. klines.gunluge_cevir) ve her uc hipotez icin
ayni kaynagi kullanir.

Listeleme donemi (on-kayit rev.2):
  - Geriye bakis penceresi donem baslangicini ASAMAZ; asiyorsa deger hesaplanmaz
    (NaN) ve o barda olay olusmaz.
  - Karantina ayindaki barlar uygun sayilmaz.

Bu modul saftir: ag veya disk kullanmaz.
"""

from __future__ import annotations

import pandas as pd

import config
from data import donem as donem_modulu
from data import pencere as pencere_modulu


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
    donem_baslangic=None,
    pencere_gun: int = config.HACIM_PENCERESI_GUN,
    karantina_aylari=(),
    *,
    kume_baslangic,
) -> float:
    """t anina kadarki son `pencere_gun` GUNUN medyan hacmi (on-kayit §2 rev.3).

    Pencere zamanla tanimlidir ve `data.pencere` yardimcisindan gecer:
      - t'nin ait oldugu gun HENUZ KAPANMADIGI icin pencereye alinmaz; pencere
        t'den once kapanmis son gunde biter. Bu, gelecege bakisi imkansiz kilar.
      - Pencere donem baslangicini asamaz (rev.2).
      - Pencere kume baslangicini asamaz (on-kayit §3 rev.5); `kume_baslangic`
        zorunludur, kume disi hesaplarda acikca None verilir.
      - Penceredeki gunlerden biri bile eksikse NaN doner (rev.3 tamlik sarti).
        Eksik gun, 6 adet 4h barin tamami olmayan gundur.
    """
    zaman = pd.Timestamp(t)

    # Pencere t'nin kendi GUNUNU icermez: o gun henuz kapanmadi. Pencere, t'nin
    # gunune gore t_dahil=False ile tanimlanir; son gun t'den onceki gundur
    # (on-kayit §5 rev.4: pencere siniri acikca belirtilir).
    return pencere_modulu.pencere_degeri(
        gunluk_hacim,
        t=zaman.floor("D"),
        bar_sayisi=pencere_gun,
        bar=config.BAR_1D,
        t_dahil=False,
        kume_baslangic=kume_baslangic,
        islev="median",
        donem_baslangic=donem_baslangic,
        karantina_aylari=karantina_aylari,
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


def uygun_mu(
    gunluk_hacim: pd.Series,
    donem_baslangic,
    t,
    bar: str,
    karantina_aylari=(),
    donem_bitis=None,
    *,
    kume_baslangic,
) -> bool:
    """t aninda sembol uygun mu? Yalnizca t'ye kadarki veriyi kullanir.

    On-kayit rev.2 gereklilikleri:
      - t bir karantina ayina dusuyorsa uygun DEGILDIR,
      - t donem sinirlarinin disindaysa uygun degildir,
      - listeleme yasi donem baslangicina gore olculur,
      - hacim penceresi donem baslangicini asamaz.
    On-kayit §3 rev.5: hacim penceresi kume baslangicini da asamaz
    (`kume_baslangic` zorunlu; kume disi hesaplarda acikca None).
    """
    zaman = pd.Timestamp(t)

    if donem_modulu.karantinada_mi(zaman, karantina_aylari):
        return False
    if zaman < pd.Timestamp(donem_baslangic):
        return False
    if donem_bitis is not None and zaman > pd.Timestamp(donem_bitis):
        return False

    if listeleme_yasi_gun(donem_baslangic, zaman) < config.ASGARI_LISTELEME_YASI_GUN:
        return False

    medyan = medyan_hacim(
        gunluk_hacim,
        zaman,
        donem_baslangic,
        karantina_aylari=karantina_aylari,
        kume_baslangic=kume_baslangic,
    )
    if pd.isna(medyan):
        return False
    return medyan >= hacim_esigi(bar)


def uygunluk_serisi(
    gunluk_hacim: pd.Series,
    donem_baslangic,
    zamanlar,
    bar: str,
    karantina_aylari=(),
    donem_bitis=None,
    *,
    kume_baslangic,
) -> pd.Series:
    """Verilen zamanlarin her biri icin uygunluk bayragi.

    Denetim raporunda "esigi en az bir gun gecen sembol" sayimi icin kullanilir.
    `kume_baslangic` zorunludur (on-kayit §3 rev.5).
    """
    indeks = pd.DatetimeIndex(zamanlar)
    return pd.Series(
        [
            uygun_mu(
                gunluk_hacim,
                donem_baslangic,
                t,
                bar,
                karantina_aylari,
                donem_bitis,
                kume_baslangic=kume_baslangic,
            )
            for t in indeks
        ],
        index=indeks,
    )
