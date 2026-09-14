"""t anindaki uygunluk filtresi (on-kayit §2, CLAUDE.md §3.6).

Kosullar:
  - Listeleme yasi >= 30 gun (donem basinda sifirlanir, on-kayit rev.2),
  - H1, H2 (4h bar) : son 30 gunun medyan gunluk hacmi >= 10.000.000 USDT,
  - H3 (1d bar)     : son 30 gunun medyan gunluk hacmi >=  2.000.000 USDT.

Gelecege bakis yoktur: t anindaki uygunluk, t barinin ait oldugu UTC gunu HARIC,
ondan onceki tam gunlerin verisiyle hesaplanir (on-kayit §2 rev.6 "Uygunluk
penceresi ve t gunu"; 4h ve 1d barda ayni kural). Gunluk hacim, on-kayit rev.2 uyarinca 4h barlardan
turetilen gunluk veriden gelir (bkz. klines.gunluge_cevir) ve her uc hipotez icin
ayni kaynagi kullanir.

Listeleme donemi (on-kayit rev.2):
  - Geriye bakis penceresi donem baslangicini ASAMAZ; asiyorsa deger hesaplanmaz
    (NaN) ve o barda olay olusmaz.

Sinir parametreleri (F1 kapanis bulgulari 2 ve 15): donem ve kume
sinirlari anahtar sozcukle ve VARSAYILANSIZ verilir; unutulan sinir TypeError
verir, sessizce atlanmaz. Tum fonksiyonlarda konumsal sira aynidir: once seri,
sonra t (ya da zamanlar), sonra bar.

Bu modul saftir: ag veya disk kullanmaz.
"""

from __future__ import annotations

import pandas as pd

import config
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
    `donem_baslangic` ve `kume_baslangic` zorunludur; sinir
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


def uygun_mu(
    gunluk_hacim: pd.Series,
    t,
    bar: str,
    *,
    donem_baslangic,
    donem_bitis,
    kume_baslangic,
) -> bool:
    """t aninda sembol uygun mu? Yalnizca t'ye kadarki veriyi kullanir.

    On-kayit rev.2 gereklilikleri:
      - t donem sinirlarinin disindaysa uygun degildir,
      - listeleme yasi donem baslangicina gore olculur,
      - hacim penceresi donem baslangicini asamaz.
    On-kayit §3 rev.5: hacim penceresi kume baslangicini da asamaz.

    Tum sinirlar zorunlu anahtar sozcuktur. `donem_baslangic` None OLAMAZ:
    listeleme yasi onsuz hesaplanamaz. Digerleri sinir yoksa acikca None alir.
    """
    zaman = pencere_modulu.utc_zamani(t, "t")
    donem_bas = pencere_modulu.sinir_zamani(donem_baslangic, "donem_baslangic")
    if donem_bas is None:
        raise TypeError("uygun_mu: donem_baslangic None olamaz; listeleme yasi donem basina gore olculur.")
    donem_son = pencere_modulu.sinir_zamani(donem_bitis, "donem_bitis")

    if zaman < donem_bas:
        return False
    if donem_son is not None and zaman > donem_son:
        return False

    if listeleme_yasi_gun(donem_bas, zaman) < config.ASGARI_LISTELEME_YASI_GUN:
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
    return medyan >= hacim_esigi(bar)


def uygunluk_serisi(
    gunluk_hacim: pd.Series,
    zamanlar,
    bar: str,
    *,
    donem_baslangic,
    donem_bitis,
    kume_baslangic,
) -> pd.Series:
    """Verilen zamanlarin her biri icin uygunluk bayragi.

    Denetim raporunda "esigi en az bir gun gecen sembol" sayimi icin kullanilir.
    Sinirlar `uygun_mu` ile aynidir ve zorunludur.
    """
    indeks = pd.DatetimeIndex(zamanlar)
    return pd.Series(
        [
            uygun_mu(
                gunluk_hacim,
                t,
                bar,
                donem_baslangic=donem_baslangic,
                donem_bitis=donem_bitis,
                kume_baslangic=kume_baslangic,
            )
            for t in indeks
        ],
        index=indeks,
    )
