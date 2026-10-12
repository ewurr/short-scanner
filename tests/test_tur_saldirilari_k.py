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
from data import pencere, pozisyon, split
from kapi_yardimcisi import donem, veri
from kume_yardimcisi import kume_adi
from sinyal_yardimcisi import kontrol
from uygunluk_yardimcisi import esikler, uygunluk
from onay_yardimcisi import gecici_kayit, kosu

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H = lambda n: pd.Timedelta(hours=n)  # noqa: E731

DB, B = T("2025-01-01"), T("2025-06-30 20:00")
Z = pd.date_range(T("2025-03-01"), B, freq="4h")
MUM = pd.DataFrame({"open_time": Z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
TAM_FUND = pd.DataFrame({"odeme_zamani": pd.date_range(DB, B + H(4), freq="8h"), "aralik_saat": 8.0,
                         "oran": 0.0, "oran_8h": 0.0})
SINYAL_T = {"H1": T("2025-03-10 04:00"), "H2": T("2025-03-10 04:00"), "H3": T("2025-03-10")}


def _karar(hipotez, mumlar=MUM, fr=TAM_FUND, donem_bas=DB, donem_son=B, **sinir):
    """Rev.11 madde 4/5: sinyal degerleri cagirandan alinmaz; bu dosyanin saldirilari kume
    sinirlarini hedefler, bu yuzden rol K1'dir (kontrol barinda sinyal kosullari aranmaz)."""
    tanim = pencere.hipotez_ufuklari(hipotez)
    s = {"kume": kume_adi(SINYAL_T[hipotez])}
    s.update(sinir)
    return pozisyon.olay_karari(SINYAL_T[hipotez], tanim.birincil, tanim.bar, hipotez=hipotez,
                                birincil_ufuk=tanim.birincil, **veri(mumlar, fr, donem_bas, donem_son, uygun_bas=donem_bas),
                                **kontrol(hipotez), **s, **esikler(tanim.bar))


def _sinyal_degerleriyle(hipotez, degerler):
    """Eski (Rev.11 oncesi) cagri bicimi: sinyal degerlerini bir eslemeyle CAGIRANDAN vermek."""
    tanim = pencere.hipotez_ufuklari(hipotez)
    return pozisyon.olay_karari(SINYAL_T[hipotez], tanim.birincil, tanim.bar, hipotez=hipotez,
                                birincil_ufuk=tanim.birincil,
                                **veri(MUM, TAM_FUND, DB, B, uygun_bas=DB), **kontrol(hipotez),
                                sinyal_degerleri=degerler, kume=kume_adi(SINYAL_T[hipotez]),
                                **esikler(tanim.bar))


def _tam(hipotez, **degisen):
    degerler = {ad: 1.0 for ad in pozisyon.SINYAL_DEGERLERI[hipotez]}
    degerler.update(degisen)
    return degerler


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
            sinyal_zamani, tanim.birincil, tanim.bar, hipotez="H2", birincil_ufuk=tanim.birincil,
            **veri(mumlar, fr, donem_bas, donem_son, uygun_bas=donem_bas), **kontrol("H2"),
            kume="KESIF",  # kapi sertlestirme turu: sinirlar kume adindan kapida okunur
            **esikler(tanim.bar))


# SALDIRI BULGUSU (F1 kapanis turu 2, xfail idi): `olay_karari` kume_baslangic/kume_bitis'in gercek bir
# `split.kume_araligi()` ciktisi oldugunu dogrulamiyordu; KESIF basi + C2 sonu karisimi, ufku C2'ye tasan
# bir KESIF olayini onaylatiyordu (on-kayit §3 "Kumeler arasi veri odunc alinmaz"). Kapi sertlestirme
# turunda kapandi: kapi yalnizca kume ADINI alir, sinirlari kendisi okur. xfail isareti kaldirildi. Eski
# govde serbest sinir cifti verdigi icin artik kurulamiyor; ayni iddia (karisim olay uretemez) su bicimde
# sinanir: (1) serbest sinir cifti kapiya verilemez, (2) ayni sinyal hicbir gercek kumeyle onaylanmaz.
# Eski adi: test_kesif_basi_ile_c2_sonu_karisimi_kume_disi_veriyi_odunc_aldirir.
def test_kesif_basi_ile_c2_sonu_karisimi_verilemez(tmp_path, monkeypatch):
    sinyal_zamani = T("2025-08-29 04:00")
    donem_bas, donem_son = T("2025-01-01"), T("2025-12-31 20:00")
    mumlar = pd.DataFrame({"open_time": pd.date_range(T("2025-01-01"), T("2026-01-05"), freq="4h"),
                           "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
    fr = pd.DataFrame({"odeme_zamani": pd.date_range(donem_bas, donem_son + H(4), freq="8h"),
                       "aralik_saat": 8.0, "oran": 0.0, "oran_8h": 0.0})
    tanim = pencere.hipotez_ufuklari("H2")
    # Kapi sertlestirme turu 2: kapi veriyi kendisi yukler (sentetik kayit `veri`); cerceve verilemez.
    ortak = dict(hipotez="H2", birincil_ufuk=tanim.birincil,
                 **veri(mumlar, fr, donem_bas, donem_son, uygun_bas=donem_bas),
                 **kontrol("H2"), **esikler(tanim.bar))
    with pytest.raises(TypeError):
        pozisyon.olay_karari(sinyal_zamani, tanim.birincil, tanim.bar, **ortak,
                             kume_baslangic=pd.Timestamp(config.KESIF_BASI), kume_bitis=pd.Timestamp(config.C2_SONU))
    with pytest.raises(pencere.OlayOlusmaz):
        pozisyon.olay_karari(sinyal_zamani, tanim.birincil, tanim.bar, **ortak, kume="KESIF")
    # C2: kapi C2 verisini kume korumali yoldan yukler; onay kosusu olmadan OnayGerekli, kosu icinde
    # sinyal C2'de olmadigi icin OlayOlusmaz (kapi sertlestirme turu 2).
    with pytest.raises(split.OnayGerekli):
        pozisyon.olay_karari(sinyal_zamani, tanim.birincil, tanim.bar, **ortak, kume="C2")
    kayit = tmp_path / "onay_gecici.md"
    kayit.write_text("bas\n", encoding="utf-8")
    gecici_kayit(kayit)
    with kosu("H2", "C2"):
        with pytest.raises(pencere.OlayOlusmaz):
            pozisyon.olay_karari(sinyal_zamani, tanim.birincil, tanim.bar, **ortak, kume="C2")
    # C1 (B grubu): sentetik sembol A grubunda; kapi grup denetiminde reddeder (kapi sertlestirme turu).
    # Kapi sertlestirme turu 3: kosu disinda once onay baglami (OnayUyusmazligi); grup denetimi kosu icinde.
    with pytest.raises(split.OnayUyusmazligi):
        pozisyon.olay_karari(sinyal_zamani, tanim.birincil, tanim.bar, **ortak, kume="C1")
    with kosu("H2", "C1"):
        with pytest.raises(ValueError, match="kumesine ait degil"):
            pozisyon.olay_karari(sinyal_zamani, tanim.birincil, tanim.bar, **ortak, kume="C1")


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
    """`dict` ALT SINIFI: temel `dict` deposu GERCEK (bozuk) degerleri tasir
    (`super().__init__(gercek)`); yalnizca `.items()` override edilip GORUNEN (baska, TAM)
    degerleri donduruyor -- J turundeki `_SahteEslem` (`collections.abc.Mapping`) ile ayni
    desen, ama bu kez dogrudan bir `dict` alt sinifi uzerinde."""

    def __init__(self, gercek: dict, gorunen: dict):
        super().__init__(gercek)
        self._gorunen = gorunen

    def items(self):
        return self._gorunen.items()


class _SahteOrderedDict(OrderedDict):
    """`OrderedDict` da bir `dict` alt sinifidir; `_SahteDict` ile ayni desen."""

    def __init__(self, gercek: dict, gorunen: dict):
        super().__init__(gercek)
        self._gorunen = gorunen

    def items(self):
        return self._gorunen.items()


class _Kosul(enum.IntEnum):
    EVET = 1


# REV.11 MADDE 4: bu dosyadaki esleme saldirilarinin (dict alt sinifi `.items()` override,
# OrderedDict alt sinifi, ChainMap on taraf, MappingProxyType) tamami KONUSUZ kaldi: kapi
# cagirandan hicbir sinyal degeri almaz ve `sinyal_degerleri` anahtar sozcugu yoktur. Saldiri
# GIRDILERI korunarak iddia yeni bicimine tasindi: hangi esleme turu, hangi gizlenmis deger
# olursa olsun parametre REDDEDILIR. Boylece "sinyal degeri disaridan verilemez" kurali
# esleme turlerine bagli olmaksizin sabitlenir.
@pytest.mark.parametrize("hipotez,yapici", [
    ("H1", lambda h: _SahteDict(_tam(h, pump_dip=float("nan")), _tam(h))),
    ("H3", lambda h: _SahteDict(_tam(h, sma50=True), _tam(h))),
    ("H1", lambda h: _SahteOrderedDict(_tam(h, pump_dip=_Kosul.EVET), _tam(h))),
    ("H1", lambda h: ChainMap({"pump_dip": float("nan")}, _tam(h))),
    ("H2", lambda h: MappingProxyType(_tam(h))),
    ("H2", lambda h: MappingProxyType(_tam(h, funding_24s=float("nan")))),
])
def test_esleme_turleri_sinyal_degeri_gecirmek_icin_kullanilamaz(hipotez, yapici):
    with pytest.raises(TypeError, match="sinyal_degerleri"):
        _sinyal_degerleriyle(hipotez, yapici(hipotez))


def test_kontrol_rolu_duz_seride_gecer():
    """Karsi-ornek: sinyal degeri verilmeyen (rol K1) cagri normal calisir."""
    assert pozisyon.onay_dogrula(_karar("H2")) is None
