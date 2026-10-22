"""F1 kapatma turu madde 1a: `config`teki on-kayit sabitlerinin kapsami ve degismezligi.

Bulgu 25: `_DEGISMEZ_ADLAR` yalnizca §5, §7 ve kume sabitlerini kapsiyordu; maliyet (§4),
uygunluk esikleri (§2), donem sinirlari (§2), bolme tuzu (§3), funding penceresi (§5) ve hipotez
izgarasi (§2) calisma aninda yeniden atanabiliyordu.

Testler kapsami ELLE SAYMAZ: `config.py`nin kaynagini okur, modul duzeyindeki acik sabitleri
AST'den cikarir ve her sabitin hangi bolumde yazildigina bakar. "ON-KAYIT DEGILDIR" diye
isaretlenmemis bir bolumdeki her sabit korunmak zorundadir, yani on-kayit kaynakli yeni bir sabit
eklendiginde bu test kirmizi olur. Aga cikmaz.
"""

from __future__ import annotations

import ast
import datetime as dt
import types

import pytest

import config

KAYNAK = config.KOK / "config.py"
_METIN = KAYNAK.read_text(encoding="utf-8")
_SATIRLAR = _METIN.splitlines()


def _bolum_basliklari() -> list[tuple[int, str]]:
    """(satir no, baslik) ciftleri: `# --- ... ---` bicimindeki bolum basliklari."""
    return [(i + 1, s) for i, s in enumerate(_SATIRLAR) if s.startswith("# ---")]


def _bolum_metni(satir: int) -> str:
    """Sabitin ait oldugu bolumun BASLIGI ve basliktan sonraki yorum blogu."""
    basliklar = _bolum_basliklari()
    oncekiler = [b for b in basliklar if b[0] <= satir]
    if not oncekiler:
        return ""
    bas = oncekiler[-1][0]
    sonrakiler = [b[0] for b in basliklar if b[0] > bas]
    son = min(sonrakiler) if sonrakiler else len(_SATIRLAR) + 1
    return "\n".join(_SATIRLAR[bas - 1:son - 1])


def _sabitler() -> dict[str, int]:
    """Modul duzeyindeki acik (BUYUK_HARFLI, alt cizgisiz baslayan) atamalar -> satir no."""
    agac = ast.parse(_METIN)
    bulunan: dict[str, int] = {}
    for dugum in agac.body:
        hedefler = []
        if isinstance(dugum, ast.Assign):
            hedefler = dugum.targets
        elif isinstance(dugum, ast.AnnAssign):
            hedefler = [dugum.target]
        for hedef in hedefler:
            if isinstance(hedef, ast.Name) and hedef.id.isupper() and not hedef.id.startswith("_"):
                bulunan.setdefault(hedef.id, dugum.lineno)
    return bulunan


SABITLER = _sabitler()


def test_sabit_listesi_kaynaktan_turetiliyor():
    """Dayanak: testin kendisi. AST taramasi calisiyor ve bilinen sabitleri buluyor."""
    assert len(SABITLER) > 40
    for ad in ("TOHUM", "TEK_YON_MALIYET", "KESIF_BASI", "IZGARA", "DENETIM_KISA_DONEM_GUN"):
        assert ad in SABITLER, ad
    for ad in SABITLER:
        assert hasattr(config, ad), ad


def test_her_sabit_tam_bir_siniftadir():
    """Dayanak: madde 1a. `_DEGISMEZ_ADLAR` ve `_ON_KAYIT_DISI` butun sabitleri BOLER.

    Siniflandirilmamis bir sabit (yeni eklenmis bir on-kayit degeri dahil) bu testi kirar.
    """
    siniflanmamis = sorted(a for a in SABITLER
                           if a not in config._DEGISMEZ_ADLAR and a not in config._ON_KAYIT_DISI)
    assert not siniflanmamis, f"siniflandirilmamis config sabiti: {siniflanmamis}"
    ikisinde = sorted(set(config._DEGISMEZ_ADLAR) & set(config._ON_KAYIT_DISI))
    assert not ikisinde, f"iki sinifta birden: {ikisinde}"


def test_on_kayit_bolumundeki_her_sabit_korunuyor():
    """Dayanak: madde 1a. "ON-KAYIT DEGILDIR" isaretli olmayan bolumdeki her sabit korunur.

    Kapsam on-kaydin BOLUMLERINDEN turetilir: sinif, sabitin adiyla degil yazildigi bolumun
    isaretiyle belirlenir.
    """
    korunmayan = []
    for ad, satir in SABITLER.items():
        bolum = _bolum_metni(satir)
        if "ON-KAYIT DEGILDIR" in bolum:
            continue
        if ad not in config._DEGISMEZ_ADLAR:
            korunmayan.append(ad)
    assert not korunmayan, (f"on-kayit bolumunde yazili ama korunmayan sabit(ler): {sorted(korunmayan)}; "
                            "`_DEGISMEZ_ADLAR`a eklenmeli ya da bolum 'ON-KAYIT DEGILDIR' olarak isaretlenmeli")


def test_on_kayit_disi_sayilan_sabitler_isaretli_bolumdedir():
    """Dayanak: madde 1a. `_ON_KAYIT_DISI`ndaki her ad "ON-KAYIT DEGILDIR" blogunda yazilmali."""
    isaretsiz = [ad for ad in config._ON_KAYIT_DISI
                 if ad in SABITLER and "ON-KAYIT DEGILDIR" not in _bolum_metni(SABITLER[ad])]
    assert not isaretsiz, f"on-kayit disi sayilip isaretsiz bolumde yazilan sabit(ler): {sorted(isaretsiz)}"


@pytest.mark.parametrize("ad", sorted(a for a in _sabitler() if a in config._DEGISMEZ_ADLAR))
def test_korunan_sabit_yeniden_atanamaz(ad):
    """Dayanak: madde 1a. Her korunan sabit icin atama ve silme reddedilir. Atama GERI ALINIR."""
    asil = getattr(config, ad)
    degisti = False
    try:
        try:
            setattr(config, ad, "bozuk")
            degisti = getattr(config, ad) == "bozuk"
        except config.SabitDegistirilemez:
            pass
        with pytest.raises(config.SabitDegistirilemez):
            delattr(config, ad)
    finally:
        if degisti:
            object.__setattr__(config, ad, asil)
    assert not degisti, f"config.{ad} yeniden atandi"
    assert getattr(config, ad) is asil or getattr(config, ad) == asil


@pytest.mark.parametrize("ad", sorted(a for a, d in vars(config).items()
                                      if a.isupper() and isinstance(d, (dict, types.MappingProxyType))))
def test_sozluk_sabitleri_yerinde_degistirilemez(ad):
    """Dayanak: madde 1a. Ad korumasi yerinde yazimi engellemez; sozlukler dondurulmus olmali."""
    sozluk = getattr(config, ad)
    anahtar = next(iter(sozluk))
    with pytest.raises(TypeError):
        sozluk[anahtar] = "bozuk"


def test_pencere_ve_klines_on_kayit_sayilarini_configten_okur():
    """Dayanak: bulgu S-C2, S-C3. Zaman toleransi ve 1d turetme sayilari tek yerde yazilidir."""
    from data import klines, pencere

    import pandas as pd

    assert pencere.tolerans() == pd.Timedelta(config.ZAMAN_TOLERANSI) == pd.Timedelta(minutes=1)
    assert pencere.ZAMAN_TOLERANSI == pencere.tolerans()
    assert klines.GUNLUK_BAR_SAYISI == config.GUNLUK_BAR_SAYISI == 6
    assert klines.GUNLUK_IZGARA_ADIMI == pencere.adim(config.BAR_4H)
    assert pencere.GUNUN_SON_4H_BARI == (config.GUNLUK_BAR_SAYISI - 1) * pencere.adim(config.BAR_4H)
    assert pencere.ADIMLAR[config.BAR_4H] == pd.Timedelta(hours=config.IZGARA_ADIMI_SAAT[config.BAR_4H])
    assert pencere.ADIMLAR[config.BAR_1D] == pd.Timedelta(hours=config.IZGARA_ADIMI_SAAT[config.BAR_1D])


def test_zaman_toleransi_on_kayit_degeridir():
    """Dayanak: on-kayit §4 rev.8 "Zaman toleransi": 1 dakika, kesin kucuk."""
    assert config.ZAMAN_TOLERANSI == dt.timedelta(minutes=1)
