"""F1 kapanis turu saldiri testleri (J turu).

Hedef: `data/pozisyon.py` `olay_karari` tek karar noktasinin sinyal TAMLIK kapisi
(on-kayit §2 "Tamlik sarti"), `config.H2_FUNDING_PENCERESI_SAAT` sabitinin tur
disiplini (on-kayit §5 H2 madde 1) ve `OnaylanmisPozisyon` imzasinin (`_imza`)
bozulmazligi. Ayrica `tests/tarama_yardimcisi.py` `KUME_NONE_DESENI`'nin
bilinen (belgelenmis) kor noktasi (D-C3).

Yaklasim kodu KIRMAYA calismaktir; gecen (xfail olmayan) testler savusturulan
saldirilardir, `xfail(strict=True)` ile isaretli testler basarili saldirilardir.
Aga cikmaz.
"""

from __future__ import annotations

import enum
import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction

import numpy as np
import pandas as pd
import pytest

import config
from data import funding, pencere, pozisyon
from kapi_yardimcisi import donem, veri
from kume_yardimcisi import kume_adi
from sinyal_yardimcisi import kontrol
from tarama_yardimcisi import KUME_NONE_DESENI
from uygunluk_yardimcisi import esikler, uygunluk

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H = lambda n: pd.Timedelta(hours=n)  # noqa: E731

DB, B = T("2025-01-01"), T("2025-06-30 20:00")
Z = pd.date_range(T("2025-03-01"), B, freq="4h")
MUM = pd.DataFrame({"open_time": Z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
TAM_FUND = pd.DataFrame({"odeme_zamani": pd.date_range(DB, B + H(4), freq="8h"), "aralik_saat": 8.0,
                         "oran": 0.0, "oran_8h": 0.0})
SINYAL_T = {"H1": T("2025-03-10 04:00"), "H2": T("2025-03-10 04:00"), "H3": T("2025-03-10")}


def _karar(hipotez, fr=TAM_FUND, rol="K1", **sinir):
    """Rev.11 madde 4/5: kapi sinyal degerlerini kendisi hesaplar; bu dosyanin saldirilari sinyal
    kurallarini degil karar noktasinin oteki adimlarini hedefler, bu yuzden rol K1'dir (kontrol
    barinda sinyal kosullari aranmaz; on-kayit §6 rev.11)."""
    tanim = pencere.hipotez_ufuklari(hipotez)
    s = {"kume": kume_adi(SINYAL_T[hipotez])}
    s.update(sinir)
    return pozisyon.olay_karari(SINYAL_T[hipotez], tanim.birincil, tanim.bar, hipotez=hipotez,
                                birincil_ufuk=tanim.birincil, **veri(MUM, fr, DB, B, uygun_bas=DB),
                                **kontrol(hipotez, rol), **s, **esikler(tanim.bar))


def _sinyal_degerleriyle(hipotez, degerler, fr=TAM_FUND, **sinir):
    """Eski (Rev.11 oncesi) cagri bicimi: sinyal degerlerini CAGIRANDAN vermek. Artik bir
    programlama hatasidir; asagidaki saldirilar bunu gosterir."""
    tanim = pencere.hipotez_ufuklari(hipotez)
    s = {"kume": kume_adi(SINYAL_T[hipotez])}
    s.update(sinir)
    return pozisyon.olay_karari(SINYAL_T[hipotez], tanim.birincil, tanim.bar, hipotez=hipotez,
                                birincil_ufuk=tanim.birincil, **veri(MUM, fr, DB, B, uygun_bas=DB),
                                **kontrol(hipotez), sinyal_degerleri=degerler, **s,
                                **esikler(tanim.bar))


# --- Saldiri 1: `__iter__` (ad tamligi) ile `.items()` (deger tamligi) ayrismasi -------------------


class _SahteEslem(Mapping):
    """`__iter__`/`__len__`/`__getitem__` GERCEK anahtarlari ve degerleri tasir (Mapping sozlesmesine
    uyar); ama `.items()` ELLE ezilmis ve GORUNEN (baska) degerleri doner.

    `data/pozisyon.py` `olay_karari`: ad tamligi `set(sinyal_degerleri)` (yani `__iter__`) ile,
    deger tamligi (`bool`/`enum`/NaN denetimi) `sinyal_degerleri.items()` ile yapilir. Bu iki erisim
    yolu farkli sonuc dondururse kapi ad kontrolunu GERCEK adlarla gecer, deger kontrolunu ise
    GORUNEN (sahte) degerlerle gecer."""

    def __init__(self, gercek: dict, gorunen: dict):
        self._gercek = gercek
        self._gorunen = gorunen

    def __iter__(self):
        return iter(self._gercek)

    def __len__(self):
        return len(self._gercek)

    def __getitem__(self, key):
        return self._gercek[key]

    def items(self):
        return self._gorunen.items()


# SALDIRI BULGUSU (F1 kapanis turu, xfail idi): olay_karari ad tamligini `set(sinyal_degerleri)`
# (__iter__) ile, deger tamligini `.items()` ile ayri ayri denetliyordu; Mapping alt sinifi NaN'i
# gizliyordu. F1 kapanis turu 2'de kapandi (kapi eslemi bir kez duz dict'e kopyaliyordu).
# REV.11 MADDE 4: bu saldiri ailesinin tamami KONUSUZ kaldi; kapi cagirandan hicbir sinyal degeri
# almaz (`sinyal_degerleri` anahtar sozcugu yok). Asagidaki test eski saldiri girdilerini
# koruyarak yeni iddiayi sinar: hangi esleme turu, hangi deger turu olursa olsun parametre
# REDDEDILIR. Boylece "sinyal degeri disaridan verilemez" kurali tek yerde sabitlenir.


class _Kosul(enum.IntEnum):
    EVET = 1


def _tam(hipotez, **degisen):
    """Eski `sinyal_yardimcisi.sinyal` yerine: hipotezin butun deger adlari 1.0."""
    degerler = {ad: 1.0 for ad in pozisyon.SINYAL_DEGERLERI[hipotez]}
    degerler.update(degisen)
    return degerler


def _sahte_esleme(hipotez):
    return _SahteEslem(_tam(hipotez, **{next(iter(_tam(hipotez))): float("nan")}), _tam(hipotez))


@pytest.mark.parametrize("yapici", [
    lambda h: _tam(h),                                             # duz dict, tam ve sayisal
    lambda h: _sahte_esleme(h),                                    # Mapping alt sinifi, .items() ezilmis
    lambda h: defaultdict(lambda: 1.0, _tam(h)),                   # defaultdict
    lambda h: _tam(h, **{next(iter(_tam(h))): float("nan")}),      # NaN deger
    lambda h: _tam(h, **{next(iter(_tam(h))): True}),              # bool
    lambda h: _tam(h, **{next(iter(_tam(h))): np.bool_(True)}),    # np.bool_
    lambda h: _tam(h, **{next(iter(_tam(h))): _Kosul.EVET}),       # enum uyesi
    lambda h: _tam(h, **{next(iter(_tam(h))): Decimal("1.5")}),    # Decimal
    lambda h: _tam(h, **{next(iter(_tam(h))): Fraction(3, 2)}),    # Fraction
    lambda h: {},                                                  # bos esleme
])
def test_sinyal_degerleri_hicbir_bicimde_verilemez(yapici):
    with pytest.raises(TypeError, match="sinyal_degerleri"):
        _sinyal_degerleriyle("H1", yapici("H1"))


def test_str_alt_sinifi_hipotez_normal_calisir():
    """Sade (adversarial olmayan) bir str alt sinifi hipotez adi olarak calismali; tur denetimi
    'isinstance' oldugu icin alt sinif engellenmemeli (savusturuldu, kirilma degil).

    Rev.11 notu: yapilandirma denetimi (`sinyal._hipotez_dogrula`) `type(hipotez) is not str`
    istedigi icin str ALT SINIFI artik reddedilir; bu, kapi sertlestirme turu 3'teki "hipotez adi
    yalnizca config.HIPOTEZLER'den" kuralinin yapilandirma tarafina genislemesidir. Iddia bu
    yuzden tersine cevrildi ve gerekcesi yazildi."""

    class HipotezStr(str):
        pass

    with pytest.raises(TypeError):
        _karar(HipotezStr("H1"))
    assert _karar("H1").hipotez == "H1"


# --- Saldiri 4: config.H2_FUNDING_PENCERESI_SAAT tur disiplini --------------------------------------


@pytest.mark.parametrize("saat", [np.int64(24), 24.0, True])
def test_h2_funding_penceresi_saat_baska_tur_kabul_etmez(saat):
    """H2 funding penceresi sabiti (`config.H2_FUNDING_PENCERESI_SAAT`) yalnizca duz `int` 24'u kabul
    eder; np.int64/float/bool (sayica 24'e esit olsa da) `sinyal_penceresi_ayrintisi` ve
    `funding_ortalamasi` tarafindan reddedilmeli (savusturuldu; data/funding.py:226-231)."""
    with pytest.raises((TypeError, ValueError)):
        funding.sinyal_penceresi_ayrintisi(TAM_FUND, [SINYAL_T["H2"]], config.BAR_4H, saat=saat,
                                           kume_baslangic=None, kume_bitis=None, donem_baslangic=DB)
    with pytest.raises((TypeError, ValueError)):
        funding.funding_ortalamasi(TAM_FUND, SINYAL_T["H2"], config.BAR_4H, saat=saat,
                                   kume_baslangic=None, kume_bitis=None, donem_baslangic=DB)


# --- Saldiri 5: OnaylanmisPozisyon imzasi (`_imza`) her alan icin korur -----------------------------


def test_onaylanmis_pozisyon_elle_degistirilince_mae_reddedilir():
    """`mae` de (`pozisyon_fiyatlari` gibi) `onay_dogrula` ile korunur: hipotez disinda herhangi bir
    alan (p1, funding_toplami) degistirilirse imza uyusmamali (savusturuldu; on-kayit §4 'MAE')."""
    p = _karar("H1")
    sahte_p1 = replace(p, p1=p.p1 * 1.5)
    with pytest.raises(ValueError):
        pozisyon.mae(sahte_p1)
    sahte_funding = replace(p, funding_toplami=p.funding_toplami + 1.0)
    with pytest.raises(ValueError):
        pozisyon.mae(sahte_funding)
    with pytest.raises(ValueError):
        pozisyon.pozisyon_fiyatlari(sahte_p1)


# --- Saldiri 6: kume sinirini (kume_bitis) sinyal barinin kapanisindan once koymak ------------------


def test_h2_kume_bitis_sinyal_barinin_kapanisindan_once_ise_olay_olusmaz():
    """Kume sonu, H2 sinyal barinin kapanisindan (= giris aninin kendisinden) once konursa; ister
    plan asamasinda ister funding penceresi asamasinda olsun, olay/kontrol HICBIR SEKILDE olusmamali
    (on-kayit §4 'Olayin kumede olusma olcutu'; savusturuldu, iki asamadan hangisi yakalarsa yakalasin)."""
    t = SINYAL_T["H2"]
    kume_son = t + H(4) - pd.Timedelta(minutes=1)
    # Kapi sertlestirme turu: kume siniri artik cagirandan alinmaz; serbest `kume_bitis` verilemez
    # (TypeError). Onceki beklenti OlayOlusmaz idi.
    with pytest.raises(TypeError):
        _karar("H2", kume_bitis=kume_son)
    # Kapi sertlestirme turu 2 (denetci KS D-C6): ayni iddia kapinin gercek davranisiyla. Sinyal KESIF'in
    # son bari (2025-08-31 20:00); kapanisi kume sonuyla tolerans icinde ayni an, giris bari (09-01 00:00)
    # C2'de. Fikstur serisi C2'ye uzansa da kapi veriyi kume sonuna keser: olay ya da kontrol olusmaz.
    # Gerekce `GirisBariYok`: kesme olmasaydi giris bari bulunur ve ret `KumeSiniriHatasi` olurdu.
    son = T("2025-08-31 20:00")
    db = T("2025-06-01")
    z = pd.date_range(db, T("2025-09-10 20:00"), freq="4h")
    mum = pd.DataFrame({"open_time": z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
    fr = pd.DataFrame({"odeme_zamani": pd.date_range(db, T("2025-09-11"), freq="8h"), "aralik_saat": 8.0,
                       "oran": 0.0, "oran_8h": 0.0})
    tanim = pencere.hipotez_ufuklari("H2")
    with pytest.raises(pencere.GirisBariYok):
        pozisyon.olay_karari(son, tanim.birincil, tanim.bar, hipotez="H2", birincil_ufuk=tanim.birincil,
                             kume="KESIF", **veri(mum, fr, db, T("2025-09-10 20:00"), uygun_bas=db),
                             **kontrol("H2"), **esikler(tanim.bar))


# --- Saldiri 7: kaynak taramasinin bilinen kor noktasi (D-C3) ---------------------------------------


@pytest.mark.xfail(strict=True, reason="SALDIRI BULGUSU (bilinen/belgelenmis sinir, D-C3): "
                    "KUME_NONE_DESENI (tests/tarama_yardimcisi.py:32) yalnizca LITERAL "
                    "'kume_baslangic=None' / 'kume_bitis=None' yakalar. Deger baska bir adla "
                    "(degiskenle) tasinip verilirse (ör. 'x = None; kume_baslangic=x') regex atlanir; "
                    "bilincli kume siniri kapatma kaynak taramasiyla yakalanamaz.")
def test_kume_none_deseni_degiskenle_tasinan_none_yakalar():
    kod = "x = None\nkume_baslangic=x\nkume_bitis=x\n"
    assert re.search(KUME_NONE_DESENI, kod) is not None
