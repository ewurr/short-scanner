"""A1 donem sonu funding tamligi olcumu (a1_olcumu.py: donem_sonu_turleri, d_kurali_olc).

Rev.8 ile D kurali veri katmanina gecti (on-kayit §4 "Donem sonu istisnasi");
betik kuralin kopyasini tasimaz, gercek `pencere.pozisyon_plani` ve
`funding.funding_tamlik_ayrintisi`yi cagirir (tests/test_a1_gercek_kod.py). Bu
testler sayimin sinirlarini sabitler: disarida kalan kayit B'den sonra ve K ile
ayni an ya da once; tamlik son odemeyi B'ye gore arar. Rev.8 oncesi `tamlik_mevcut`
(son bar kapanisina gore) ve `tamlik_d` sutunlari tek `tamlik` sutununa indi:
rev.8 "mevcut" kurali kaldirdi (RESULTS degisiklik kaydi, madde 8). Aga cikmaz.
"""

from __future__ import annotations

import importlib.util

import pandas as pd
import pytest

import config
from data.donem import Donem

_yol = config.ANALIZ_DIZINI / "00_veri_denetimi" / "a1_olcumu.py"
_spec = importlib.util.spec_from_file_location("a1_olcumu_d", _yol)
a1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(a1)

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
DK = pd.Timedelta(minutes=1)
SN = pd.Timedelta(seconds=1)
BITIS = T("2025-04-14 08:00")
DONEM = Donem(T("2025-04-01 00:00"), BITIS, 80, 80)


def _fund(zamanlar, aralik=4):
    z = pd.DatetimeIndex(sorted(zamanlar))
    return pd.DataFrame({"odeme_zamani": z, "aralik_saat": aralik, "oran": 0.0, "oran_8h": 0.0})


def _ritim(bas, son, saat):
    return list(pd.date_range(bas, son, freq=f"{saat}h", tz="UTC"))


# --- disarida kalan kayit sinirlari ------------------------------------------------


@pytest.mark.parametrize("kayma,beklenen", [
    (pd.Timedelta(0), 0),                          # son bar acilisi: D'de dahil
    (59 * SN, 0),                                  # tolerans ici: acilisla ayni an
    (DK, 1),                                       # tam 1 dk: disarida
    (pd.Timedelta(hours=1), 1),                    # son bar ici (teslimden sonra)
    (pd.Timedelta(hours=4), 1),                    # son bar kapanisi (cikis ani)
    (pd.Timedelta(hours=4) + 59 * SN, 1),          # kapanis toleransi ici
    (pd.Timedelta(hours=4) + DK, 0),               # zaten mevcut kuralda da donem disi
])
def test_disarida_kalan_sinirlari(kayma, beklenen):
    fund = _fund(_ritim("2025-04-13 00:00", "2025-04-14 04:00", 4) + [BITIS + kayma])
    satir = a1.d_kurali_olc("X", [DONEM], ["delist_SETTLING"], fund)[0]
    assert satir["disarida_kalan"] == beklenen


def test_veri_sonu_doneminde_kural_uygulanmaz():
    fund = _fund(_ritim("2025-04-13 00:00", "2025-04-14 12:00", 4))
    satir = a1.d_kurali_olc("X", [DONEM], ["veri_sonu"], fund)[0]
    assert satir["kural_uygulanir"] is False
    assert satir["disarida_kalan"] == 1  # 12:00 kaydi; sayi yine yazilir


# --- tamlik ------------------------------------------------------------------------


def test_duzenli_4h_ritimde_tam():
    # 08:00 (son bar acilisi) ve 12:00 (kapanis) kayitlari var.
    fund = _fund(_ritim("2025-04-12 00:00", "2025-04-14 12:00", 4))
    satir = a1.d_kurali_olc("X", [DONEM], ["delist_SETTLING"], fund)[0]
    assert satir["tamlik"] and satir["cikis_turu"] == "donem_sonu"


def test_kapanis_kaydi_yoksa_tam():
    # 08:00'dan sonra kayit yok. Rev.8 "Donem sonu istisnasi": son odeme B'ye gore
    # aranir; K'daki (12:00) odeme aranmaz. (Rev.7 kurali bozuk sayardi.)
    fund = _fund(_ritim("2025-04-12 00:00", "2025-04-14 08:00", 4))
    satir = a1.d_kurali_olc("X", [DONEM], ["delist_exchangeInfo_disi"], fund)[0]
    assert satir["tamlik"] and satir["son_tam"]


def test_8h_aralikta_son_odeme_acilistan_once_d_kurali_tam():
    # Son bar 04:00'te acilir; son odeme 00:00, sonraki 08:00 (= kapanis).
    donem = Donem(T("2022-11-01 00:00"), T("2022-11-14 04:00"), 80, 80)
    fund = _fund(_ritim("2022-11-12 00:00", "2022-11-14 08:00", 8), aralik=8)
    satir = a1.d_kurali_olc("X", [donem], ["delist_SETTLING"], fund)[0]
    assert satir["disarida_kalan"] == 1
    assert satir["tamlik"]


def test_odemeler_erken_biterse_bozuk():
    fund = _fund(_ritim("2025-04-10 00:00", "2025-04-12 00:00", 4))
    satir = a1.d_kurali_olc("X", [DONEM], ["delist_SETTLING"], fund)[0]
    # Rev.9 §4 "Funding tamligi": "kayit_var" kosulu kaldirildi; capa (04-12 00:00) var, son
    # kayit + 4 saat B'den once doluyor -> "Son" maddesi bozuk (rev.8'de kayit_var bozuktu).
    assert not satir["tamlik"] and satir["capa_var"] and not satir["son_tam"]


def test_donem_sonrasi_kayit_tamligi_d_kuralinda_kurtarmaz():
    # 04:00 ve 08:00 eksik; yalniz kapanistaki 12:00 var. Rev.8 donem sonu penceresi
    # B'de kapanir, 12:00'yi okumaz; 00:00 + 4h, B'den once: son odeme eksik.
    fund = _fund(_ritim("2025-04-12 00:00", "2025-04-14 00:00", 4) + [T("2025-04-14 12:00")])
    satir = a1.d_kurali_olc("X", [DONEM], ["delist_SETTLING"], fund)[0]
    assert not satir["tamlik"] and not satir["son_tam"]


def test_donem_basindan_onceki_kayit_okunmaz():
    # Donem son bardan 1 bar once basliyor; tek kayit donem basindan once.
    donem = Donem(T("2025-04-14 04:00"), BITIS, 2, 2)
    fund = _fund([T("2025-04-14 00:00")], aralik=8)
    satir = a1.d_kurali_olc("X", [donem], ["delist_SETTLING"], fund)[0]
    assert satir["giris"] >= donem.baslangic
    # Rev.9: donem basindan onceki kayit capa olamaz (rev.8'de kayit_var sutunuyla sabitleniyordu).
    assert not satir["tamlik"] and not satir["capa_var"]


def test_funding_yoksa_tamlik_bozuk():
    satir = a1.d_kurali_olc("X", [DONEM], ["delist_SETTLING"], _fund([]))[0]
    assert satir["disarida_kalan"] == 0
    # Rev.9: kayit yoksa capa yok (rev.8'de kayit_var sutunuyla sabitleniyordu).
    assert not satir["tamlik"] and not satir["capa_var"]


# --- donem sonu turleri -----------------------------------------------------------


VERI_SONU = T("2026-08-31 20:00")


@pytest.mark.parametrize("sinif,bitis,beklenen", [
    ("SETTLING", BITIS, "delist_SETTLING"),
    ("exchangeInfo_disi", BITIS, "delist_exchangeInfo_disi"),
    ("TRADING", VERI_SONU, "veri_sonu"),
    ("TRADING", BITIS, "diger_son_donem"),
    (None, VERI_SONU, "veri_sonu"),
])
def test_son_donem_turu(sinif, bitis, beklenen):
    donem = Donem(T("2025-01-01 00:00"), bitis, 10, 10)
    assert a1.donem_sonu_turleri([donem], sinif, VERI_SONU) == [beklenen]


def _iki_donem(ara_sifir_bar: int, ara_eksik_bar: int):
    """Donem 0 (6 gercek bar), arada `ara_sifir_bar` sifir hacimli bar ve
    `ara_eksik_bar` eksik bar, donem 1 (6 gercek bar)."""
    adim = pd.Timedelta(hours=4)
    bas = T("2024-01-01 00:00")
    zam, hac = [], []
    for i in range(6):
        zam.append(bas + i * adim); hac.append(1.0)
    t = bas + 6 * adim
    for _ in range(ara_sifir_bar):
        zam.append(t); hac.append(0.0); t += adim
    t += ara_eksik_bar * adim
    for i in range(6):
        zam.append(t + i * adim); hac.append(1.0)
    zamanlar = pd.DatetimeIndex(zam)
    hacim = pd.Series(hac)
    d0 = Donem(zamanlar[0], zamanlar[5], 6, 6)
    d1 = Donem(zamanlar[6 + ara_sifir_bar], zamanlar[-1], 6, 6)
    return [d0, d1], zamanlar, hacim


def test_ic_donem_sonu_dolgu_kosusu():
    donemler, z, h = _iki_donem(ara_sifir_bar=6, ara_eksik_bar=0)
    assert a1.donem_sonu_turleri(donemler, "SETTLING", VERI_SONU, z, h) == ["dolgu_kosusu", "delist_SETTLING"]


def test_ic_donem_sonu_uzun_bosluk():
    donemler, z, h = _iki_donem(ara_sifir_bar=0, ara_eksik_bar=43)  # > 7 gun
    assert a1.donem_sonu_turleri(donemler, "TRADING", donemler[1].bitis, z, h) == ["uzun_bosluk", "veri_sonu"]


# --- Cikis izgarasi (4h / 1d) ve yeni sutunlar ------------------------------------


def test_temsili_plan_4h_son_barin_kapanisi():
    plan = a1.temsili_plan(DONEM, config.BAR_4H)
    assert plan.cikis_turu == "donem_sonu"
    assert (plan.cikis.zaman, plan.cikis_ani) == (BITIS, T("2025-04-14 12:00"))


def test_temsili_plan_1d_kismi_son_gunde_k():
    """H3, rev.8 §4 "Donem sonu ve cikis": 1d izgarada da fiyat tabani 4h; cikis B
    barinin kapanisi, K = 12:00 (rev.7'de gunun kapanisi, ertesi gun 00:00 idi)."""
    plan = a1.temsili_plan(DONEM, config.BAR_1D)
    assert plan.cikis_turu == "donem_sonu"
    assert (plan.cikis.zaman, plan.cikis_ani) == (BITIS, T("2025-04-14 12:00"))


def test_1d_cikisinda_disarida_kalan_4h_ile_ayni_tabandan():
    """16:00 ve 20:00 kayitlarini veri katmani (`donem_sonrasi_kayitlari_at`) atar.
    Sayim ayni kayit tabanindan yapilir; donem sonu istisnasinin disarida biraktigi
    yalnizca 12:00'dir (denetci bulgusu D-A4). Rev.8: 1d cikisi da K'dadir (12:00);
    rev.7'de ertesi gun 00:00 idi ve kapanista odeme yoktu."""
    fund = _fund(_ritim("2025-04-13 00:00", "2025-04-14 20:00", 4))
    dort = a1.d_kurali_olc("X", [DONEM], ["delist_SETTLING"], fund, config.BAR_4H)[0]
    gun = a1.d_kurali_olc("X", [DONEM], ["delist_SETTLING"], fund, config.BAR_1D)[0]
    assert dort["disarida_kalan"] == 1        # yalnizca 12:00
    assert gun["disarida_kalan"] == 1         # ayni taban: 16:00 ve 20:00 zaten atilmis
    assert gun["cikis_ani"] == dort["cikis_ani"] == T("2025-04-14 12:00")
    assert gun["kapanista_odeme"] and dort["kapanista_odeme"]


def test_1d_cikisinda_kapanis_kaydi_yoksa_tam():
    """Uzlasmadan sonra odeme kesilince K'da kayit yoktur; rev.8 donem sonu istisnasi
    son odemeyi B'ye gore arar, 1d izgarada da."""
    fund = _fund(_ritim("2025-04-12 00:00", "2025-04-14 08:00", 4))
    gun = a1.d_kurali_olc("X", [DONEM], ["delist_SETTLING"], fund, config.BAR_1D)[0]
    assert gun["tamlik"] and gun["son_tam"]


def test_kapanista_odeme_sutunu():
    var = _fund(_ritim("2025-04-13 00:00", "2025-04-14 12:00", 4))
    yok = _fund(_ritim("2025-04-13 00:00", "2025-04-14 08:00", 4))
    assert a1.d_kurali_olc("X", [DONEM], ["delist_SETTLING"], var, config.BAR_4H)[0]["kapanista_odeme"]
    assert not a1.d_kurali_olc("X", [DONEM], ["delist_SETTLING"], yok, config.BAR_4H)[0]["kapanista_odeme"]


def test_son_odeme_aralik_saat_donem_bitisine_kadarki_son_kayittan():
    """Aralik degisirse (8h -> 2h) sutun donem bitisine kadarki SON kaydin
    araligini yazmali; uzlasma sonrasi kaydin araligini degil."""
    zamanlar = _ritim("2025-04-13 00:00", "2025-04-14 06:00", 2)
    fund = _fund(zamanlar + [T("2025-04-14 12:00")])
    fund.loc[fund["odeme_zamani"] == T("2025-04-14 12:00"), "aralik_saat"] = 8
    satir = a1.d_kurali_olc("X", [DONEM], ["delist_SETTLING"], fund, config.BAR_4H)[0]
    assert satir["son_odeme_aralik_saat"] == 4  # _fund varsayilani; 06:00 kaydi
