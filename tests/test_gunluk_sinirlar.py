"""1 gunluk barlarin donem sinirlari (denetci bulgusu D-A1) ve A1 sayiminin kayit
tabani (D-A4). Aga cikmaz.

`calistir.gunluk_sinir_satirlari` bugunku kodun 1 gunluk barini donem basinda ve
sonunda hangi 4 saatlik barlardan kurdugunu sayar. Testler bu sayimi gercek
kod yollarina baglar: 1 gunluk seri `klines.gunluge_cevir`den, donem sonu cikis
bari `pencere.cikis_bari`dan gelir; sayim ikisinin ikinci bir kopyasini yazmaz.
"""

from __future__ import annotations

import importlib.util
import sys

import pandas as pd
import pytest

import config
from data import klines
from data import pencere
from data.donem import Donem

DIZIN = config.ANALIZ_DIZINI / "00_veri_denetimi"
sys.path.insert(0, str(DIZIN))


def _yukle(ad: str, dosya: str):
    spec = importlib.util.spec_from_file_location(ad, DIZIN / dosya)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


calistir = _yukle("_gs_calistir", "calistir.py")
a1 = _yukle("_gs_a1", "a1_olcumu.py")

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
ADIM = pd.Timedelta(hours=4)


def _mumlar(bas: str, son: str, sifir_bas: str | None = None) -> pd.DataFrame:
    """4 saatlik sentetik seri; `sifir_bas`tan itibaren hacim sifir (dolgu)."""
    z = pd.date_range(T(bas), T(son), freq="4h")
    hacim = [0.0 if sifir_bas is not None and t >= T(sifir_bas) else 1.0 for t in z]
    return pd.DataFrame({
        "open_time": z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
        "volume": hacim, "close_time": z + ADIM - pd.Timedelta(milliseconds=1), "quote_volume": hacim,
        "count": 1, "taker_buy_volume": 0.0, "taker_buy_quote_volume": 0.0,
    })


def _satir(mumlar, donemler, turler):
    zamanlar = pd.DatetimeIndex(mumlar["open_time"])
    gunler = pd.DatetimeIndex(klines.gunluge_cevir(mumlar)["open_time"])
    return calistir.gunluk_sinir_satirlari("X", zamanlar, gunler, donemler, turler)


def test_uzlasma_gununun_dolgu_barlari_son_gune_girer():
    """SETTLING tipik durumu: son gercek bar 08:00, ayni gunun 12:00-20:00
    barlari dolgu. Bugunku 1 gunluk seri o gunu tam gun sayar (6 bar var) ve
    donem sonu cikisi o gunun barindan okunur: 3 donem disi bar."""
    m = _mumlar("2025-04-01 00:00", "2025-04-20 20:00", sifir_bas="2025-04-14 12:00")
    donem = Donem(T("2025-04-01 00:00"), T("2025-04-14 08:00"), 80, 80)
    s = _satir(m, [donem], ["delist_SETTLING"])[0]
    assert s["son_gun"] == T("2025-04-14 00:00")
    assert s["son_gun_donem_disi_bar"] == 3
    assert s["bitis_gunu_1d_serisinde"] and s["bitis_gunu_donem_ici_bar"] == 3
    assert s["ilk_gun"] == T("2025-04-01 00:00") and s["ilk_gun_donem_disi_bar"] == 0


def test_seri_gun_ortasinda_biterse_son_gun_bir_onceki_gundur():
    """Dolgusuz biten seri (exchangeInfo disi, gercek islemle biten): bitis gunu
    eksik oldugu icin 1 gunluk seride yok; cikis bir onceki tam gunden okunur ve
    o gunde donem disi bar yoktur."""
    m = _mumlar("2025-04-01 00:00", "2025-04-14 08:00")
    donem = Donem(T("2025-04-01 00:00"), T("2025-04-14 08:00"), 80, 80)
    s = _satir(m, [donem], ["delist_exchangeInfo_disi"])[0]
    assert not s["bitis_gunu_1d_serisinde"]
    assert s["son_gun"] == T("2025-04-13 00:00")
    assert s["son_gun_donem_disi_bar"] == 0


def test_bitis_gun_sonundaysa_donem_disi_bar_yok():
    m = _mumlar("2025-04-01 00:00", "2025-04-20 20:00", sifir_bas="2025-04-15 00:00")
    donem = Donem(T("2025-04-01 00:00"), T("2025-04-14 20:00"), 90, 90)
    s = _satir(m, [donem], ["delist_SETTLING"])[0]
    assert s["son_gun"] == T("2025-04-14 00:00") and s["son_gun_donem_disi_bar"] == 0
    assert s["bitis_gunu_donem_ici_bar"] == 6


def test_ic_sinir_ikinci_donemin_ilk_gunu_dolgu_barlari_icerir():
    """Ic dolgudan sonra 08:00'de baslayan donem: baslangic gununun 00:00 ve 04:00
    barlari dolgu. Ilk 1 gunluk bar o gundur ve 2 donem disi bar icerir."""
    m = _mumlar("2025-04-01 00:00", "2025-04-30 20:00", sifir_bas="2025-04-10 12:00")
    m.loc[m["open_time"] >= T("2025-04-20 08:00"), ["volume", "quote_volume"]] = 1.0
    d0 = Donem(T("2025-04-01 00:00"), T("2025-04-10 08:00"), 57, 57)
    d1 = Donem(T("2025-04-20 08:00"), T("2025-04-30 20:00"), 64, 64)
    s = _satir(m, [d0, d1], ["dolgu_kosusu", "veri_sonu"])
    assert s[0]["bas_turu"] == "donem_basi" and s[1]["bas_turu"] == "ic_sinir"
    assert s[0]["son_gun_donem_disi_bar"] == 3
    assert s[1]["ilk_gun"] == T("2025-04-20 00:00") and s[1]["ilk_gun_donem_disi_bar"] == 2
    assert s[1]["bas_gunu_donem_ici_bar"] == 4


@pytest.mark.parametrize("bitis,seri_son,sifir", [
    ("2025-04-14 08:00", "2025-04-20 20:00", "2025-04-14 12:00"),
    ("2025-04-14 08:00", "2025-04-14 08:00", None),
    ("2025-04-14 20:00", "2025-04-20 20:00", "2025-04-15 00:00"),
])
def test_son_gun_gercek_cikis_bariyla_ayni(bitis, seri_son, sifir):
    """`son_gun`, `pencere.cikis_bari`nin 1 gunluk seride donem sonunda sectigi
    bardir; sayim cikis kuralinin kopyasini yazmaz, gercek fonksiyonla ayni sonucu
    verir."""
    m = _mumlar("2025-04-01 00:00", seri_son, sifir_bas=sifir)
    donem = Donem(T("2025-04-01 00:00"), T(bitis), 80, 80)
    s = _satir(m, [donem], ["delist_SETTLING"])[0]
    gunler = pd.DatetimeIndex(klines.gunluge_cevir(m)["open_time"])
    cikis = pencere.cikis_bari(gunler, T("2025-04-05 00:00"), 30, config.BAR_1D, birincil_ufuk=30,
                               donem_bitis=donem.bitis, kume_bitis=None)
    assert cikis.kirpildi and cikis.zaman == s["son_gun"]


# --- D-A4: 1 gunluk satirlar 4 saatlik satirlarla ayni kayit tabanindan ----------


def _fund(zamanlar, aralik=4):
    return pd.DataFrame({"odeme_zamani": pd.DatetimeIndex(sorted(zamanlar)), "aralik_saat": aralik})


DONEM = Donem(T("2025-04-01 00:00"), T("2025-04-14 08:00"), 80, 80)


def test_1d_satiri_veri_katmaninin_attigi_kaydi_saymaz():
    """Son barin kapanisindan (12:00) sonraki kayitlari veri katmani atar. 1 gunluk
    cikis ani ertesi gun 00:00 olsa da o kayit ne disarida kalan ne de kapanista
    odeme sayilir."""
    z = list(pd.date_range(T("2025-04-12 00:00"), T("2025-04-15 00:00"), freq="4h"))
    gun = a1.d_kurali_olc("X", [DONEM], ["delist_SETTLING"], _fund(z), config.BAR_1D)[0]
    dort = a1.d_kurali_olc("X", [DONEM], ["delist_SETTLING"], _fund(z), config.BAR_4H)[0]
    assert gun["disarida_kalan"] == dort["disarida_kalan"] == 1
    assert dort["kapanista_odeme"] and not gun["kapanista_odeme"]


def test_aday_kural_1d_cikisi_son_4h_barin_kapanisi():
    """Aday kural: 1 gunluk izgarada da cikis ani son donem ici 4 saatlik barin
    kapanisi, funding penceresi D kurali. Temsili giris donemin tamamen icinde
    kalan son UTC gunu (bitis 08:00 -> onceki gun; bitis 20:00 -> ayni gun)."""
    z = list(pd.date_range(T("2025-04-12 00:00"), T("2025-04-14 08:00"), freq="4h"))
    gun = a1.d_kurali_olc("X", [DONEM], ["delist_SETTLING"], _fund(z), config.BAR_1D)[0]
    assert gun["cikis_ani_aday"] == T("2025-04-14 12:00")
    assert gun["giris_aday"] == T("2025-04-13 00:00")
    assert not gun["tamlik_mevcut"] and gun["tamlik_d"] and gun["tamlik_aday"]

    d20 = Donem(T("2025-04-01 00:00"), T("2025-04-14 20:00"), 80, 80)
    gun20 = a1.d_kurali_olc("X", [d20], ["delist_SETTLING"], _fund(z), config.BAR_1D)[0]
    assert gun20["giris_aday"] == T("2025-04-14 00:00")
    assert gun20["cikis_ani_aday"] == T("2025-04-15 00:00")


def test_aday_kural_4h_izgarada_d_kuraliyla_ayni():
    for son in ("2025-04-14 00:00", "2025-04-14 08:00", "2025-04-14 12:00"):
        z = list(pd.date_range(T("2025-04-12 00:00"), T(son), freq="4h"))
        s = a1.d_kurali_olc("X", [DONEM], ["delist_SETTLING"], _fund(z), config.BAR_4H)[0]
        assert s["tamlik_aday"] == s["tamlik_d"]
        assert s["giris_aday"] == T("2025-04-13 08:00")


def test_donem_sonu_turleri_tek_kaynak():
    """A1 olcumu donem sonu turunu F1 denetimiyle ayni fonksiyondan alir."""
    assert a1.donem_sonu_turleri.__module__ == "calistir"
    assert "def donem_sonu_turleri" not in (DIZIN / "a1_olcumu.py").read_text(encoding="utf-8")
