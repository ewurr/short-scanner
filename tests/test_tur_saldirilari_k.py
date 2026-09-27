"""F1 kapanis turu saldiri testleri (K turu).

Hedef: `data/pozisyon.py` `olay_karari` tek karar noktasinin (F1 kapanis turu 2 ile
degisen) iki maddesi:
  1. Sinyal eslemi bir kez duz `dict`'e kopyalanir (`sinyal_degerleri = dict(sinyal_degerleri)`);
     bu turda kopyalama adiminin `dict` ALT SINIFLARINA (yalnizca genel `Mapping`'e degil; J
     turundaki `.items()` ile `__iter__`/`__getitem__` ayrismasi saldirisinin dict alt sinifina
     genellenmis hali dahil) karsi da saglam olup olmadigi, ChainMap/MappingProxyType/OrderedDict
     gibi bilinen turlerle davranisin dogru oldugu sinanir.
  2. Kume siniri (`kume_baslangic`, `kume_bitis`) yalnizca `None` icin reddedilir; kapinin
     bu iki sinirin GERCEK bir kumeye (`split.kume_araligi`) ait olup olmadigini dogrulayip
     dogrulamadigi, ters sirali sinirlarin ve "bos gibi" degerlerin (0, "", bool, NaT,
     np.datetime64('NaT')) davranisi sinanir.

Yaklasim kodu KIRMAYA calismaktir; gecen (xfail olmayan) testler savusturulan
saldirilardir, `xfail(strict=True)` ile isaretli testler basarili saldirilardir.
Aga cikmaz.
"""

from __future__ import annotations

import enum
from collections import ChainMap, OrderedDict
from collections.abc import Mapping
from types import MappingProxyType

import numpy as np
import pandas as pd
import pytest

import config
from data import pencere, pozisyon
from kapi_yardimcisi import donem
from kume_yardimcisi import kume_adi
from sinyal_yardimcisi import sinyal
from uygunluk_yardimcisi import uygunluk

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H = lambda n: pd.Timedelta(hours=n)  # noqa: E731

DB, B = T("2025-01-01"), T("2025-06-30 20:00")
Z = pd.date_range(T("2025-03-01"), B, freq="4h")
MUM = pd.DataFrame({"open_time": Z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
TAM_FUND = pd.DataFrame({"odeme_zamani": pd.date_range(DB, B + H(4), freq="8h"), "aralik_saat": 8.0,
                         "oran": 0.0, "oran_8h": 0.0})
SINYAL_T = {"H1": T("2025-03-10 04:00"), "H2": T("2025-03-10 04:00"), "H3": T("2025-03-10")}


def _karar(hipotez, degerler=None, mumlar=MUM, fr=TAM_FUND, donem_bas=DB, donem_son=B, **sinir):
    tanim = pencere.hipotez_ufuklari(hipotez)
    if degerler is None:
        degerler = sinyal(hipotez)
    s = {"kume": kume_adi(SINYAL_T[hipotez])}
    s.update(sinir)
    return pozisyon.olay_karari(mumlar, fr, SINYAL_T[hipotez], tanim.birincil, tanim.bar, hipotez=hipotez,
                                birincil_ufuk=tanim.birincil, **donem(donem_bas, donem_son),
                                sinyal_degerleri=degerler, **s, **uygunluk(tanim.bar, donem_bas, donem_son))


# --- Saldiri 1: gercek KESIF siniriyla dogru sekilde reddedilir (temel olcum) ------------------------


def test_ufku_c2ye_tasan_kesif_olayi_gercek_kesif_siniriyla_reddedilir():
    """Temel olcum: ufku C2 verisine tasan bir H2 olayi, GERCEK KESIF kume sinirlariyla
    (kume_bitis = config.KESIF_SONU) reddedilmeli (on-kayit §3 'Kumeler arasi veri odunc
    alinmaz': 'kesif kumesindeki bir olayin ufku C2 verisine uzanamaz'). Karsilastirma icin;
    asil saldiri asagidaki testtedir (savusturuldu)."""
    sinyal_zamani = T("2025-08-29 04:00")
    donem_bas, donem_son = T("2025-01-01"), T("2025-12-31 20:00")
    mumlar = pd.DataFrame({"open_time": pd.date_range(T("2025-01-01"), T("2026-01-05"), freq="4h"),
                           "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
    fr = pd.DataFrame({"odeme_zamani": pd.date_range(donem_bas, donem_son + H(4), freq="8h"),
                       "aralik_saat": 8.0, "oran": 0.0, "oran_8h": 0.0})
    tanim = pencere.hipotez_ufuklari("H2")
    with pytest.raises(pencere.KumeSiniriHatasi):
        pozisyon.olay_karari(
            mumlar, fr, sinyal_zamani, tanim.birincil, tanim.bar, hipotez="H2", birincil_ufuk=tanim.birincil,
            **donem(donem_bas, donem_son), sinyal_degerleri=sinyal("H2"),
            kume="KESIF",  # kapi sertlestirme turu: sinirlar kume adindan kapida okunur
            **uygunluk(tanim.bar, donem_bas, donem_son))


# SALDIRI BULGUSU (F1 kapanis turu 2, xfail idi): `olay_karari` kume_baslangic/kume_bitis'in gercek bir
# `split.kume_araligi()` ciktisi oldugunu dogrulamiyordu; KESIF basi + C2 sonu karisimi, ufku C2'ye tasan
# bir KESIF olayini onaylatiyordu (on-kayit §3 "Kumeler arasi veri odunc alinmaz"). Kapi sertlestirme
# turunda kapandi: kapi yalnizca kume ADINI alir, sinirlari kendisi okur. xfail isareti kaldirildi. Eski
# govde serbest sinir cifti verdigi icin artik kurulamiyor; ayni iddia (karisim olay uretemez) su bicimde
# sinanir: (1) serbest sinir cifti kapiya verilemez, (2) ayni sinyal hicbir gercek kumeyle onaylanmaz.
# Eski adi: test_kesif_basi_ile_c2_sonu_karisimi_kume_disi_veriyi_odunc_aldirir.
def test_kesif_basi_ile_c2_sonu_karisimi_verilemez():
    sinyal_zamani = T("2025-08-29 04:00")
    donem_bas, donem_son = T("2025-01-01"), T("2025-12-31 20:00")
    mumlar = pd.DataFrame({"open_time": pd.date_range(T("2025-01-01"), T("2026-01-05"), freq="4h"),
                           "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
    fr = pd.DataFrame({"odeme_zamani": pd.date_range(donem_bas, donem_son + H(4), freq="8h"),
                       "aralik_saat": 8.0, "oran": 0.0, "oran_8h": 0.0})
    tanim = pencere.hipotez_ufuklari("H2")
    ortak = dict(hipotez="H2", birincil_ufuk=tanim.birincil, **donem(donem_bas, donem_son),
                 sinyal_degerleri=sinyal("H2"), **uygunluk(tanim.bar, donem_bas, donem_son))
    with pytest.raises(TypeError):
        pozisyon.olay_karari(mumlar, fr, sinyal_zamani, tanim.birincil, tanim.bar, **ortak,
                             kume_baslangic=pd.Timestamp(config.KESIF_BASI), kume_bitis=pd.Timestamp(config.C2_SONU))
    for kume in ("KESIF", "C2"):
        with pytest.raises(pencere.OlayOlusmaz):
            pozisyon.olay_karari(mumlar, fr, sinyal_zamani, tanim.birincil, tanim.bar, **ortak, kume=kume)
    # C1 (B grubu): sentetik sembol A grubunda; kapi grup denetiminde reddeder (kapi sertlestirme turu).
    with pytest.raises(ValueError):
        pozisyon.olay_karari(mumlar, fr, sinyal_zamani, tanim.birincil, tanim.bar, **ortak, kume="C1")


# --- Saldiri 2: ters sirali kume sinirlari (kume_baslangic > kume_bitis) her zaman reddedilir --------


@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_ters_sirali_kume_siniri_olay_olusturmaz(hipotez):
    """kume_baslangic kume_bitis'ten SONRA verilirse (C2 basi ile KESIF sonu ters cevrilmis gibi) hicbir
    sinyal zamani ikisinin arasina dusemez; olay ya baslangic kontrolunde (sinyal kume basindan once) ya
    da cikis/giris kontrolunde (kume sonundan sonra) reddedilmeli, sessizce olusmamali (on-kayit §3
    'Kume siniri ve geriye bakis'; savusturuldu)."""
    # Kapi sertlestirme turu: serbest sinir cifti artik kapiya verilemez (TypeError); onceki beklenti
    # OlayOlusmaz idi. Ters sirali bir kume `split.kume_araligi`nda yoktur.
    with pytest.raises(TypeError):
        _karar(hipotez, kume_baslangic=pd.Timestamp(config.C2_BASI), kume_bitis=pd.Timestamp(config.KESIF_SONU))


# --- Saldiri 3: "bos gibi" kume sinirlari (None disi) --------------------------------------------------


@pytest.mark.parametrize("bos", [0, "", 0.0])
@pytest.mark.parametrize("ad", ["kume_baslangic", "kume_bitis"])
def test_sifir_ve_bos_string_kume_siniri_reddedilir(ad, bos):
    """`None` disindaki 'bos gibi' degerler (0, '', 0.0) bir zaman damgasina cevrilemez ya da saat
    dilimsiz kabul edilir; kume siniri sessizce gecerli bir tarihe donusmemeli (on-kayit §3 'Kume
    siniri ve geriye bakis: kod duzeyinde ayrica dogrulanir'; savusturuldu)."""
    # Kapi sertlestirme turu: sinir yerine kume adi verilir; 'bos gibi' deger kume adi olarak reddedilir.
    del ad  # iki sinir artik tek `kume` girdisidir; parametre adlari korunur
    with pytest.raises((TypeError, ValueError)):
        _karar("H1", kume=bos)


@pytest.mark.parametrize("ad", ["kume_baslangic", "kume_bitis"])
@pytest.mark.parametrize("deger", [True, False])
def test_bool_kume_siniri_reddedilir(ad, deger):
    """bool bir zaman damgasi degildir (`0`/`1` gibi sayica gecerli gorunse de); kume siniri olarak
    kabul edilmemeli (on-kayit §3; savusturuldu)."""
    del ad  # kapi sertlestirme turu: tek `kume` girdisi
    with pytest.raises(TypeError):
        _karar("H1", kume=deger)


def test_np_datetime64_nat_kume_siniri_reddedilir():
    """`np.datetime64('NaT')` da `pd.NaT` gibi saat dilimsiz/gecersiz bir zamana cevrilir; kume siniri
    olarak sessizce kabul edilmemeli (on-kayit §3; savusturuldu)."""
    with pytest.raises(TypeError):
        _karar("H2", kume=np.datetime64("NaT"))  # kapi sertlestirme turu: tek `kume` girdisi


# --- Saldiri 4: dict alt siniflari ve bilinen Mapping turleri kopyalama adimini atlatamaz -------------


class _SahteDict(dict):
    """`dict` ALT SINIFI (Mapping degil): temel `dict` deposu GERCEK (bozuk) degerleri tasir
    (`super().__init__(gercek)`); yalnizca `.items()` override edilip GORUNEN (baska, TAM)
    degerleri donduruyor -- J turundaki `_SahteEslem` (`collections.abc.Mapping`) ile ayni
    desen, ama bu kez dogrudan bir `dict` alt sinifi uzerinde. `keys()`/`__getitem__`/`__iter__`
    OVERRIDE EDILMEDI: `dict(sinyal_degerleri)` kopyalama adimi (ister CPython'un ic depoyu
    dogrudan kopyalayan hizli yolundan, ister `.keys()` + `__getitem__` jenerik yolundan gecsin)
    `.items()`'e HICBIR ZAMAN bakmaz; boylece hangi yoldan gecilirse gecilsin gercek (bozuk) deger
    kopyaya girer, `.items()`'teki gorunen (sahte) deger kopyaya hic girmez. Ayrica kopyalamadan
    SONRAKI butun denetimler `sahte` degil KOPYA uzerinden calistigi icin `sahte.items()` bir daha
    hic cagrilmaz."""

    def __init__(self, gercek: dict, gorunen: dict):
        super().__init__(gercek)
        self._gorunen = gorunen

    def items(self):
        return self._gorunen.items()


def test_dict_alt_sinifi_items_override_deger_kontrolunu_atlatamaz():
    """`dict` alt sinifinda `.items()` override'i (J turundaki Mapping saldirisinin dict alt
    sinifina genellenmis hali) tamlik kapisini atlatamamali: gercek (bozuk, NaN) deger temel
    depoda oldugu icin kopyaya girer, gorunen (sahte, tam) `.items()` hic cagrilmaz (F1 kapanis
    turu 2 duzeltmesinin dict alt siniflarina da genellendigini dogrular; savusturuldu)."""
    gorunen = sinyal("H1")  # gorunen: hepsi 1.0, tam
    gercek = sinyal("H1", pump_dip=float("nan"))  # temel depodaki GERCEK deger NaN
    sahte = _SahteDict(gercek, gorunen)
    with pytest.raises(pozisyon.SinyalPenceresiTamDegil):
        _karar("H1", sahte)


def test_dict_alt_sinifi_items_override_bool_degerini_gizleyemez():
    """Ayni `dict` alt sinifi deseni bir bool GERCEK degerle de yakalanmali (kosul sonucu, pencere
    degeri degil); gorunen (sahte) `.items()` degeri onu gizleyemez (savusturuldu)."""
    gorunen = sinyal("H3")
    gercek = sinyal("H3", sma50=True)  # temel depodaki GERCEK deger bool
    sahte = _SahteDict(gercek, gorunen)
    with pytest.raises(TypeError, match="bool"):
        _karar("H3", sahte)


def test_chainmap_on_taraftaki_deger_dogru_degerlendirilir():
    """`ChainMap` gercek bir `Mapping`dir (MutableMapping alt sinifi); on taraftaki esleme
    arka esleme uzerine yazar. On tarafa konan bozuk (NaN) deger sessizce arka (tam) degerle
    gizlenmemeli, kopyada ON taraftaki deger gecerli olmali (savusturuldu; normal Python
    Mapping semantigi, atlatma degil)."""
    arka = sinyal("H1")  # hepsi 1.0, tam
    on = {"pump_dip": float("nan")}
    zincir = ChainMap(on, arka)
    with pytest.raises(pozisyon.SinyalPenceresiTamDegil):
        _karar("H1", zincir)


def test_mappingproxy_salt_okunur_esleme_normal_calisir():
    """`types.MappingProxyType` salt-okunur bir `Mapping` gorunumudur; tam bir esleme sarilinca
    normal kabul edilmeli, icinde NaN varsa reddedilmeli (savusturuldu; salt-okunurlugun kapiyi
    atlatan bir yani yok)."""
    tam = MappingProxyType(sinyal("H2"))
    if not isinstance(tam, Mapping):
        pytest.skip("Bu Python surumunde types.MappingProxyType collections.abc.Mapping olarak "
                    "kaydedilmemis; olay_karari zaten 'isinstance(..., Mapping)' degilse TypeError verir.")
    p = _karar("H2", tam)
    assert pozisyon.onay_dogrula(p) is None
    bozuk = MappingProxyType(sinyal("H2", funding_24s=float("nan")))
    with pytest.raises(pozisyon.SinyalPenceresiTamDegil):
        _karar("H2", bozuk)


class _SahteOrderedDict(OrderedDict):
    """`OrderedDict` da bir `dict` alt sinifidir; `_SahteDict` ile ayni desen (temel depoda
    GERCEK deger, yalnizca `.items()` override edilip GORUNEN deger donduruluyor) burada da
    sinanir."""

    def __init__(self, gercek: dict, gorunen: dict):
        super().__init__(gercek)
        self._gorunen = gorunen

    def items(self):
        return self._gorunen.items()


def test_ordereddict_alt_sinifi_items_override_enum_degerini_gizleyemez():
    """`OrderedDict` alt sinifinda `.items()` override'iyla gizlenmis bir Enum uyesi (kosul
    sonucu tasiyabilir) de kapida reddedilmeli; gorunen (sahte) `.items()` onu gizleyemez
    (savusturuldu)."""

    class Kosul(enum.IntEnum):
        EVET = 1

    gorunen = sinyal("H1")
    gercek = sinyal("H1", pump_dip=Kosul.EVET)  # temel depodaki GERCEK deger enum uyesi
    sahte = _SahteOrderedDict(gercek, gorunen)
    with pytest.raises(TypeError, match="enum"):
        _karar("H1", sahte)
