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
from sinyal_yardimcisi import sinyal
from tarama_yardimcisi import KUME_NONE_DESENI
from uygunluk_yardimcisi import uygunluk

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H = lambda n: pd.Timedelta(hours=n)  # noqa: E731

DB, B = T("2025-01-01"), T("2025-06-30 20:00")
Z = pd.date_range(T("2025-03-01"), B, freq="4h")
MUM = pd.DataFrame({"open_time": Z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
TAM_FUND = pd.DataFrame({"odeme_zamani": pd.date_range(DB, B + H(4), freq="8h"), "aralik_saat": 8.0,
                         "oran": 0.0, "oran_8h": 0.0})
SINYAL_T = {"H1": T("2025-03-10 04:00"), "H2": T("2025-03-10 04:00"), "H3": T("2025-03-10")}


def _karar(hipotez, degerler, fr=TAM_FUND, **sinir):
    tanim = pencere.hipotez_ufuklari(hipotez)
    s = dict(kume_baslangic=None, kume_bitis=None)
    s.update(sinir)
    return pozisyon.olay_karari(MUM, fr, SINYAL_T[hipotez], tanim.birincil, tanim.bar, hipotez=hipotez,
                                birincil_ufuk=tanim.birincil, donem_baslangic=DB, donem_bitis=B,
                                sinyal_degerleri=degerler, **s, **uygunluk(tanim.bar, DB, B))


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
# (__iter__) ile, deger tamligini `.items()` ile ayri ayri denetliyordu; Mapping alt sinifi NaN'i gizliyordu.
# F1 kapanis turu 2'de kapandi (kapi eslemi bir kez duz dict'e kopyalar); xfail isareti kaldirildi,
# test ayni beklentiyle normal test olarak kaliyor.
def test_esleme_iterasyon_ile_items_ayrismasi_nan_degeri_sizdirir():
    gorunen = sinyal("H1")  # goze gorunen: hepsi 1.0, tam
    gercek = sinyal("H1", pump_dip=float("nan"))  # gercek deger NaN
    sahte = _SahteEslem(gercek, gorunen)
    with pytest.raises(pozisyon.SinyalPenceresiTamDegil):
        _karar("H1", sahte)


# SALDIRI BULGUSU (F1 kapanis turu, xfail idi): ayni ayrisma bool degerini de gizliyordu. F1 kapanis
# turu 2'de ayni duzeltmeyle kapandi; xfail isareti kaldirildi, beklenti ayni.
def test_esleme_iterasyon_ile_items_ayrismasi_bool_degerini_gizler():
    gorunen = sinyal("H3")
    gercek = sinyal("H3", sma50=True)  # bool: kosul sonucu, pencere degeri degil
    sahte = _SahteEslem(gercek, gorunen)
    with pytest.raises(TypeError, match="bool"):
        _karar("H3", sahte)


# --- Saldiri 2: defaultdict / bilinen (adversarial olmayan) Mapping turleri savusturulur -----------


def test_defaultdict_ile_eksik_ad_hala_programlama_hatasi():
    """defaultdict eksik anahtari otomatik doldurabilir umuduyla denenir: `set(sinyal_degerleri)`
    yalnizca ACIKCA konmus anahtarlari gorur, eksik ad hala TypeError'dur (savusturuldu)."""
    taban = sinyal("H1")
    ilk = next(iter(taban))
    eksik = defaultdict(lambda: 1.0, {k: v for k, v in taban.items() if k != ilk})
    with pytest.raises(TypeError, match="sinyal_degerleri"):
        _karar("H1", eksik)


def test_str_alt_sinifi_hipotez_normal_calisir():
    """Sade (adversarial olmayan) bir str alt sinifi hipotez adi olarak calismali; tur denetimi
    'isinstance' oldugu icin alt sinif engellenmemeli (savusturuldu, kirilma degil)."""

    class HipotezStr(str):
        pass

    p = _karar(HipotezStr("H1"), sinyal("H1"))
    assert p.hipotez == "H1"


# --- Saldiri 3: sinyal degeri turleri (Decimal/Fraction/np.bool_/Enum) ------------------------------


def test_decimal_ve_fraction_sinyal_degeri_tamlik_kapisini_gecmez():
    """Decimal/Fraction on-kayitin bekledigi (int/float/np sayisal) turlerden degildir; tamlik kapisi
    bunlari SESSIZCE kabul etmemeli, guvenli tarafta (eksik sayarak) reddetmeli (savusturuldu)."""
    for deger in (Decimal("1.5"), Fraction(3, 2)):
        with pytest.raises(pozisyon.SinyalPenceresiTamDegil):
            _karar("H1", sinyal("H1", pump_dip=deger))


def test_numpy_bool_sinyal_degeri_reddedilir():
    """np.bool_ da bool gibi kosul sonucu sayilmali, pencere degeri olarak kabul edilmemeli
    (savusturuldu)."""
    with pytest.raises(TypeError, match="bool"):
        _karar("H1", sinyal("H1", pump_dip=np.bool_(True)))


def test_enum_uyesi_sinyal_degeri_reddedilir():
    """IntEnum uyesi sayi gibi gecebilir ama bir kosul sonucu tasiyabilir; kapi acikca reddetmeli
    (savusturuldu)."""

    class Kosul(enum.IntEnum):
        EVET = 1

    with pytest.raises(TypeError, match="enum"):
        _karar("H1", sinyal("H1", pump_dip=Kosul.EVET))


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
    p = _karar("H1", sinyal("H1"))
    sahte_p1 = replace(p, p1=p.p1 * 1.5)
    with pytest.raises(ValueError):
        pozisyon.mae(MUM, sahte_p1)
    sahte_funding = replace(p, funding_toplami=p.funding_toplami + 1.0)
    with pytest.raises(ValueError):
        pozisyon.mae(MUM, sahte_funding)
    with pytest.raises(ValueError):
        pozisyon.pozisyon_fiyatlari(sahte_p1)


# --- Saldiri 6: kume sinirini (kume_bitis) sinyal barinin kapanisindan once koymak ------------------


def test_h2_kume_bitis_sinyal_barinin_kapanisindan_once_ise_olay_olusmaz():
    """Kume sonu, H2 sinyal barinin kapanisindan (= giris aninin kendisinden) once konursa; ister
    plan asamasinda ister funding penceresi asamasinda olsun, olay/kontrol HICBIR SEKILDE olusmamali
    (on-kayit §4 'Olayin kumede olusma olcutu'; savusturuldu, iki asamadan hangisi yakalarsa yakalasin)."""
    t = SINYAL_T["H2"]
    kume_son = t + H(4) - pd.Timedelta(minutes=1)
    with pytest.raises(pencere.OlayOlusmaz):
        _karar("H2", sinyal("H2"), kume_bitis=kume_son)


# --- Saldiri 7: kaynak taramasinin bilinen kor noktasi (D-C3) ---------------------------------------


@pytest.mark.xfail(strict=True, reason="SALDIRI BULGUSU (bilinen/belgelenmis sinir, D-C3): "
                    "KUME_NONE_DESENI (tests/tarama_yardimcisi.py:32) yalnizca LITERAL "
                    "'kume_baslangic=None' / 'kume_bitis=None' yakalar. Deger baska bir adla "
                    "(degiskenle) tasinip verilirse (ör. 'x = None; kume_baslangic=x') regex atlanir; "
                    "bilincli kume siniri kapatma kaynak taramasiyla yakalanamaz.")
def test_kume_none_deseni_degiskenle_tasinan_none_yakalar():
    kod = "x = None\nkume_baslangic=x\nkume_bitis=x\n"
    assert re.search(KUME_NONE_DESENI, kod) is not None
