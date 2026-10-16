"""Denetci bulgusu D-B4: §7'deki tohum ve tekrar sayisi calisma aninda degistirilemez.

CLAUDE.md §5: "Rastgelelik her zaman sabit tohumla (seed) ve tohum sonuc dosyasina yazilir."
On-kayit §7: "Tohum: 20260911, sonuc dosyalarina yazilir"; "p-degeri: 10.000 tekrarli ...".

Bulgu: `IZGARA`, `KONTROL_SAYISI`, `ADAY_OLAY_ESIGI`, `GECERSIZLIK_CARPANI` gibi on-kayit sabitleri
`config._DEGISMEZ_ADLAR` ile korunurken `TOHUM` ve `PERMUTASYON_TEKRAR` korunmuyordu. Tohum
rev.13'ten beri IKI turetme yolunun girdisidir (§6'nin olay basina ornekleme alt tohumu ve §7'nin
p-degeri alt tohumu); calisma aninda degistirilirse butun alt tohumlar sessizce kayar ve sonuc
dosyasina yazilan `genel_tohum` da kaydigi icin fark raporda gorunmez.

Aga cikmaz; getiri hesaplanmaz.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import istatistik, ornekleme


@pytest.mark.parametrize("ad", ["TOHUM", "PERMUTASYON_TEKRAR", "ALFA_BONFERRONI"])
def test_atama_reddedilir(ad):
    with pytest.raises(config.SabitDegistirilemez):
        setattr(config, ad, 1)


@pytest.mark.parametrize("ad", ["TOHUM", "PERMUTASYON_TEKRAR", "ALFA_BONFERRONI"])
def test_silme_reddedilir(ad):
    with pytest.raises(config.SabitDegistirilemez):
        delattr(config, ad)


@pytest.mark.parametrize("ad", ["TOHUM", "PERMUTASYON_TEKRAR", "ALFA_BONFERRONI"])
def test_monkeypatch_da_reddedilir(ad):
    """`monkeypatch.setattr` da ayni yoldan gecer: koruma modul `__setattr__`indedir.

    `undo()` CAGRILMAZ: atama hic gerceklesmedigi icin geri alinacak bir sey yok ve geri alma
    denemesi ayni korumaya takilir (pytest fikstur sokumunde hata verir)."""
    yama = pytest.MonkeyPatch()
    with pytest.raises(config.SabitDegistirilemez):
        yama.setattr(config, ad, 2)
    assert getattr(config, ad) != 2


@pytest.mark.parametrize("ad", ["TOHUM", "PERMUTASYON_TEKRAR", "ALFA_BONFERRONI"])
def test_degismezler_listesinde(ad):
    assert ad in config._DEGISMEZ_ADLAR


def test_on_kayit_degerleri():
    assert config.TOHUM == 20260911
    assert config.PERMUTASYON_TEKRAR == 10_000
    assert config.ALFA_BONFERRONI == pytest.approx(0.05 / 3)


def test_iki_turetme_yolu_da_ayni_tohuma_bagli():
    """Tohumun neden korunmasi gerektigi: iki alt tohum da ondan turer."""
    y = {"phi": 0.0003, "k": 3}
    ornekleme_tohumu = ornekleme.alt_tohum("H2", y, "KESIF", "AAVEUSDT", pd.Timestamp("2025-03-01", tz="UTC"))
    p_tohumu, demet = istatistik.alt_tohum("H2", y, "KESIF", "K1")
    assert isinstance(ornekleme_tohumu, int) and isinstance(p_tohumu, int)
    assert ornekleme_tohumu != p_tohumu, "demetler farkli, tohumlar da farkli"
    # Ikisi de tek turetme yolundan (`ornekleme.tohum_turet`) gecer ve §7'deki tohumu girdi alir.
    assert p_tohumu == ornekleme.tohum_turet(demet[1], demet[2], demet[3])
