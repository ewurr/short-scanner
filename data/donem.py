"""Listeleme donemi mantigi (on-kayit §2, revizyon 2).

Bir sembolun verisi bir veya daha fazla **listeleme donemine** ayrilir. Donemi
bolen iki olay vardir:

  1. **Karantina ayi.** Bucket'ta `<SEMBOL>SETTLED` dizininde dosyasi bulunan ve
     sembolun ilk ile son ayi arasinda kalan her ay. Sozlesme yerinde kapatilip
     yeniden acilmis demektir; token yeniden fiyatlandirmasi fiyat serisinde
     yapay bir sicrama birakir.
  2. **3 aydan uzun dosya boslugu.**

Donem kurallari (on-kayit §2, revizyon 2):
  - Listeleme yasi her donem basinda sifirlanir.
  - Tum geriye bakis pencereleri donem baslangicini asamaz; asiyorsa deger
    hesaplanmaz (NaN) ve o barda olay olusmaz.
  - Ufuk donem sonunu asarsa cikis, donemin son barinin kapanisidir.
  - Karantina ayindaki barlar olay veya kontrol bari olamaz.
  - Ayni kurallar K1 ve K2 kontrol barlarina da uygulanir.

Bu modul tamamen saftir: ag veya disk kullanmaz.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import config


def _ay(deger) -> pd.Period:
    return deger if isinstance(deger, pd.Period) else pd.Period(str(deger), freq="M")


def listeleme_donemleri(
    mevcut_aylar,
    karantina_aylari=(),
    azami_bosluk: int = config.AZAMI_BOSLUK_AY,
) -> list[tuple[pd.Period, pd.Period]]:
    """Ay listesinden listeleme donemlerini cikarir.

    `mevcut_aylar`: sembolun 4h dosyasi bulunan aylar.
    `karantina_aylari`: SETTLED isaretli aylar; bunlar donemi boler ve hicbir
    donemin icinde yer almaz.

    Doner: [(baslangic_ayi, bitis_ayi), ...] ay sirasinda.
    """
    aylar = sorted({_ay(a) for a in mevcut_aylar})
    karantina = {_ay(a) for a in karantina_aylari}

    donemler: list[tuple[pd.Period, pd.Period]] = []
    su_anki: list[pd.Period] = []
    onceki: pd.Period | None = None

    for ay in aylar:
        if ay in karantina:
            if su_anki:
                donemler.append((su_anki[0], su_anki[-1]))
                su_anki = []
            onceki = ay
            continue
        if onceki is not None and (ay - onceki).n - 1 > azami_bosluk:
            if su_anki:
                donemler.append((su_anki[0], su_anki[-1]))
                su_anki = []
        su_anki.append(ay)
        onceki = ay

    if su_anki:
        donemler.append((su_anki[0], su_anki[-1]))
    return donemler


def donem_sinirlari(donemler) -> pd.DataFrame:
    """Ay donemlerini UTC zaman damgasi sinirlarina cevirir.

    Baslangic = ilk ayin ilk ani, bitis = son ayin son ani.
    """
    satirlar = []
    for i, (bas, son) in enumerate(donemler):
        satirlar.append(
            {
                "donem_id": i,
                "donem_bas_ay": str(bas),
                "donem_son_ay": str(son),
                "donem_baslangic": bas.to_timestamp(how="start").tz_localize("UTC"),
                "donem_bitis": son.to_timestamp(how="end").tz_localize("UTC"),
            }
        )
    return pd.DataFrame(
        satirlar,
        columns=[
            "donem_id",
            "donem_bas_ay",
            "donem_son_ay",
            "donem_baslangic",
            "donem_bitis",
        ],
    )


def karantinada_mi(t, karantina_aylari) -> bool:
    """t ani bir karantina ayina mi dusuyor?"""
    if not len(karantina_aylari):
        return False
    return pd.Period(pd.Timestamp(t), freq="M") in {_ay(a) for a in karantina_aylari}


def donem_bul(t, donemler) -> int | None:
    """t aninin dustugu donemin kimligi; hicbirine dusmuyorsa None."""
    ay = pd.Period(pd.Timestamp(t), freq="M")
    for i, (bas, son) in enumerate(donemler):
        if bas <= ay <= son:
            return i
    return None


def pencere_gecerli_mi(t, donem_baslangic, pencere_uzunlugu) -> bool:
    """Geriye bakis penceresi donem baslangicini asmiyor mu? (on-kayit §2)

    `pencere_uzunlugu` bir pd.Timedelta'dir. Pencere [t - uzunluk, t] araligidir;
    donem baslangicindan once basliyorsa gecersizdir.
    """
    return pd.Timestamp(t) - pd.Timedelta(pencere_uzunlugu) >= pd.Timestamp(donem_baslangic)


def cikis_bar_indeksi(
    bar_zamanlari,
    giris_indeksi: int,
    ufuk: int,
    donem_bitis,
    bar: str = config.BAR_4H,
) -> int:
    """Ufuk sonundaki cikis barinin indeksi (on-kayit §2 rev.2 + rev.3).

    Revizyon 3'ten beri mantik `data.pencere.cikis_bari` icindedir: ufuk zamanla
    olculur, hedef bar eksikse sonraki ilk mevcut bara kayilir, donem sonu ve
    delist onceliklidir. Bu sarmalayici geriye donuk uyumluluk icindir ve
    yalnizca indeksi doner; cikisin hangi fiyat alanindan (close / open)
    okunacagini ogrenmek icin dogrudan `pencere.cikis_bari` kullanilmalidir.

    Getiri HESAPLAMAZ.
    """
    from data import pencere as pencere_modulu

    zamanlar = pd.DatetimeIndex(bar_zamanlari)
    if len(zamanlar) == 0:
        raise ValueError("Bar listesi bos.")
    if not 0 <= giris_indeksi < len(zamanlar):
        raise IndexError(f"Giris indeksi donem disinda: {giris_indeksi}")

    sonuc = pencere_modulu.cikis_bari(
        zamanlar,
        giris_zamani=zamanlar[giris_indeksi],
        ufuk=ufuk,
        bar=bar,
        donem_bitis=donem_bitis,
    )
    return sonuc.indeks
