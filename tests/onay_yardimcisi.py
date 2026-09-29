"""Onay kosusu test yardimcilari (onay kaydi ve kosu butunlugu turu, denetci KS3 D-B1, D-B3).

Kayit yolu artik `config.ONAY_KAYDI` monkeypatch'iyle degistirilemez; testler `split._test_kaydi_ayarla` ile
kendi testleri suresince gecici bir kayda yonlenir (git ortami da orada sahte: temiz agac, sabit commit).

Onay kosusu blogu sonuc bildirilmeden biterse `OnaySonucuYok` verir. Kosuyu yalnizca erisim acmak icin kullanan
testler `kosu(...)` ile acar: blok hatasiz biterse sonuc "TEST" bildirilir; blok icindeki hata aynen yukari cikar.
"""

from __future__ import annotations

from contextlib import contextmanager

from data import split


def gecici_kayit(yol, **ortam):
    """Bu test suresince onay kaydini `yol`a yonlendirir; `ortam` `split._test_kaydi_ayarla`ya gider."""
    return split._test_kaydi_ayarla(yol, **ortam)


@contextmanager
def kosu(hipotez, kume, sonuc: str = "TEST"):
    """`split.onay_kosusu`; blok hatasiz biterse ve sonuc bildirilmediyse `sonuc` bildirilir."""
    with split.onay_kosusu(hipotez, kume) as tutamak:
        yield tutamak
        if tutamak.sonuc is None:
            tutamak.sonuc_bildir(sonuc)
