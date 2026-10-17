"""config sabit korumasinin kapatilan iki yolu (koruma turu madde 5).

Gerekce: `config` on-kayit degerlerini tasir (tohum, esikler, izgaralar, kume sinirlari). Calisma
aninda degisirse butun alt tohumlar ve hukumler SESSIZCE kayar -- sonuc dosyasina yazilan
`genel_tohum` da kaydigi icin fark raporda gorunmez.

Sizinti bulgusu (uc yol): (i) `type(config).__setattr__ = types.ModuleType.__setattr__`,
(ii) `object.__setattr__(config, "TOHUM", 1)`, (iii) `vars(config)["TOHUM"] = 1`. Ilk ikisi bu
turda kapatildi; ucuncusu `config.py`'de bilincli sinir olarak yazilidir ve ARTIK OKUMALARI
ETKILEMEZ (degismez adlar veri tanimlayicisina baglidir).

Testler config'i gercekten bozmaya calisir; her test kendi degisikligini geri alir (koruma
calisiyorsa degisiklik hic olmaz).
"""

from __future__ import annotations

import types

import pytest

import config

DEGISMEZ_ORNEKLER = ["TOHUM", "PERMUTASYON_TEKRAR", "ALFA_BONFERRONI", "ADAY_OLAY_ESIGI",
                     "ONAY_OLAY_ESIGI", "KONTROL_SAYISI", "KUMELER", "ONAY_KUMELERI",
                     "KESIF_BASI", "KESIF_SONU", "C2_BASI", "C2_SONU", "IZGARA",
                     "GECERSIZLIK_CARPANI", "ONAY_KAYDI", "UZAK_DEPO_ADRESI"]


# --- 1. Onceki turlarin kapattigi yollar korundu ---------------------------------------------


@pytest.mark.parametrize("ad", DEGISMEZ_ORNEKLER)
def test_dogrudan_atama_ve_silme_reddedilir(ad):
    asil = getattr(config, ad)
    with pytest.raises(config.SabitDegistirilemez):
        setattr(config, ad, "bozuk")
    with pytest.raises(config.SabitDegistirilemez):
        delattr(config, ad)
    assert getattr(config, ad) == asil


@pytest.mark.parametrize("ad", ["TOHUM", "IZGARA", "ADAY_OLAY_ESIGI"])
def test_monkeypatch_reddedilir(ad):
    """`undo()` CAGRILMAZ: atama hic gerceklesmedigi icin geri alinacak bir sey yok ve geri alma
    denemesi ayni korumaya takilir (pytest fikstur sokumunde hata verir)."""
    yama = pytest.MonkeyPatch()
    asil = getattr(config, ad)
    with pytest.raises(config.SabitDegistirilemez):
        yama.setattr(config, ad, "bozuk")
    assert getattr(config, ad) == asil


def test_modul_sinifi_atamasi_reddedilir():
    asil = type(config)
    with pytest.raises(config.SabitDegistirilemez):
        config.__class__ = types.ModuleType
    assert type(config) is asil


# --- 2. Madde 5: yeni kapatilan iki yol ------------------------------------------------------


@pytest.mark.parametrize("ozellik", ["__setattr__", "__delattr__", "TOHUM", "yeni_ozellik"])
def test_modul_sinifinin_ozellikleri_degistirilemez(ozellik):
    """(i) `type(config).__setattr__ = ...`: sinifin ozel yontemini degistirmek butun korumayi tek
    satirda kaldiriyordu."""
    tur = type(config)
    with pytest.raises(config.SabitDegistirilemez):
        setattr(tur, ozellik, types.ModuleType.__setattr__)
    with pytest.raises(config.SabitDegistirilemez):
        delattr(tur, ozellik)
    assert config.TOHUM == 20260911
    with pytest.raises(config.SabitDegistirilemez):
        setattr(config, "TOHUM", 1)


@pytest.mark.parametrize("ad", DEGISMEZ_ORNEKLER)
def test_object_setattr_ile_atama_reddedilir(ad):
    """(ii) `object.__setattr__` modulun ornek sozlugune dogrudan yaziyor ve `__setattr__`
    atlanabiliyordu. Degismez adlar artik VERI TANIMLAYICISIDIR: `object.__setattr__` da
    tanimlayicinin `__set__`ini cagirmak zorundadir."""
    asil = getattr(config, ad)
    with pytest.raises(config.SabitDegistirilemez):
        object.__setattr__(config, ad, "bozuk")
    with pytest.raises((config.SabitDegistirilemez, AttributeError)):
        object.__delattr__(config, ad)
    assert getattr(config, ad) == asil


def test_veri_tanimlayicisi_sozluk_yazimini_etkisiz_kilar():
    """Bilincli sinir (iii) duruyor ama ETKISI yok: sozluge yazim okumayi degistirmez."""
    asil = config.TOHUM
    vars(config)["TOHUM"] = 1
    try:
        assert config.TOHUM == asil, "okuma veri tanimlayicisindan gelmeli"
        assert vars(config)["TOHUM"] == 1, "sozluk yazimi engellenmiyor (bilincli sinir)"
    finally:
        vars(config)["TOHUM"] = asil


def test_degismez_adlarin_hepsi_tanimlayiciya_bagli():
    """Liste ile tanimlayicilar ayrismamali: `_DEGISMEZ_ADLAR`daki her ad (modulde tanimliysa)
    veri tanimlayicisiyla korunur."""
    tur = type(config)
    for ad in config._DEGISMEZ_ADLAR:
        if ad == "__class__":
            continue
        if ad not in vars(config):
            continue
        ozellik = getattr(tur, ad, None)
        assert isinstance(ozellik, property), f"config.{ad} veri tanimlayicisina bagli degil"


# --- 3. Degerler ON-KAYIT degerleri (degismedi) ----------------------------------------------


def test_on_kayit_degerleri_okunabiliyor():
    assert config.TOHUM == 20260911
    assert config.PERMUTASYON_TEKRAR == 10_000
    assert config.ADAY_OLAY_ESIGI == 150 and config.ONAY_OLAY_ESIGI == 100
    assert config.KONTROL_SAYISI == 10
    assert config.KUMELER == ("KESIF", "C1", "C2") and config.ONAY_KUMELERI == ("C1", "C2")
    assert set(config.IZGARA) == set(config.HIPOTEZLER)


def test_degismez_olmayan_adlar_hala_yazilabilir():
    """Koruma yalnizca `_DEGISMEZ_ADLAR` icindir; modulun geri kalani normal calisir."""
    config.gecici_deneme_adi = 5
    try:
        assert config.gecici_deneme_adi == 5
    finally:
        del config.gecici_deneme_adi
