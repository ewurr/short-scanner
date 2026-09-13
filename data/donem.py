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


def ay_donemi(deger) -> pd.Period:
    """Ay degerini ("2025-12", Period ya da zaman damgasi) aylik pd.Period'a cevirir.

    Acik (alt cizgisiz) bir fonksiyondur: data/pencere.py karantina kontrollerinde
    kullanir.
    """
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
    aylar = sorted({ay_donemi(a) for a in mevcut_aylar})
    karantina = {ay_donemi(a) for a in karantina_aylari}

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
    return pd.Period(pd.Timestamp(t), freq="M") in {ay_donemi(a) for a in karantina_aylari}


def donem_bul(t, donemler) -> int | None:
    """t aninin dustugu donemin kimligi; hicbirine dusmuyorsa None."""
    ay = pd.Period(pd.Timestamp(t), freq="M")
    for i, (bas, son) in enumerate(donemler):
        if bas <= ay <= son:
            return i
    return None


# Cikis bari secimi yalnizca `data.pencere.cikis_bari` icindedir. Eskiden burada
# duran `cikis_bar_indeksi` sarmalayicisi F1 kapanis denetiminde (bulgu 1)
# kaldirildi: `kume_bitis` iletmiyordu, `fiyat_alani` bilgisini kaybediyordu
# (ileri kaymali cikista acilis yerine kapanis okunurdu) ve `bar=4h` varsayilani
# vardi.
