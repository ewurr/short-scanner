"""Sabit evren tablosu testleri (on-kayit §2 rev.4 ve rev.7, denetci bulgusu B10).

"Listeleme donemi sinirlari data/universe.csv dosyasina yazilir ve commit edilir.
Bu dosya split.csv gibi sabittir; analiz bu dosyadan okur, canli exchangeInfo'dan
yeniden turetmez." Rev.7: donem sinirlari bar duzeyindedir; karantina yoktur,
SETTLED aylari yalnizca denetim sutunudur.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import config
from data import split, universe

KOK = Path(__file__).resolve().parents[1]
ONBELLEK = config.ONBELLEK_DIZINI / universe.ONBELLEK_ADI


def _ortak(sembol, **alanlar):
    return {
        "sembol": sembol, "ilk_ay": "2021-01", "son_ay": "2021-04",
        "dosya_sayisi_4h": 4, "funding_dosya_sayisi": 4,
        "sozlesme_tipi": None, "dayanak_tipi": None,  # delist: exchangeInfo'da yok
        "settled_aylari": "", "haric": False, "haric_gerekce": "", **alanlar,
    }


def _sahte_evren() -> pd.DataFrame:
    z = pd.date_range("2021-01-05 08:00", periods=120, freq="4h", tz="UTC")
    h = np.full(len(z), 1e6)
    h[40:60] = 0  # ic dolgu -> iki donem
    h[-10:] = 0  # sondaki dolgu
    satirlar = universe.sembol_satirlari(_ortak("AAUSDT", settled_aylari="2021-02"), z, h)
    z2 = pd.date_range("2022-05-01", periods=30, freq="4h", tz="UTC")
    satirlar += universe.sembol_satirlari(
        _ortak("牛来USDT", ilk_ay="2022-05", son_ay="2022-05", sozlesme_tipi="PERPETUAL", dayanak_tipi="COIN",
               haric=True, haric_gerekce="test gerekcesi"),
        z2, np.full(len(z2), 1e6),
    )
    satirlar += universe.sembol_satirlari(_ortak("DOLGUUSDT"), z2, np.zeros(len(z2)))
    return pd.DataFrame(satirlar)


# --- Satir uretimi (saf) -----------------------------------------------------


def test_sembol_satirlari_bar_duzeyinde_donemler():
    evren = _sahte_evren()
    aa = evren[evren["sembol"] == "AAUSDT"]
    z = pd.date_range("2021-01-05 08:00", periods=120, freq="4h", tz="UTC")
    assert list(aa["donem_id"]) == [0, 1]
    assert list(aa["donem_baslangic"]) == [z[0], z[60]]
    assert list(aa["donem_bitis"]) == [z[39], z[109]]
    dolgu = evren[evren["sembol"] == "DOLGUUSDT"]
    assert list(dolgu["donem_id"]) == [-1] and pd.isna(dolgu["donem_baslangic"].iloc[0])


# --- Yazma ve okuma ----------------------------------------------------------


def test_yaz_oku_dongusu_ayni_evreni_verir(tmp_path):
    evren = _sahte_evren()
    yol = universe.evren_csv_yaz(evren, tmp_path / "universe.csv")
    okunan = universe.evren_yukle(yol)

    assert list(okunan["sembol"]) == ["AAUSDT", "AAUSDT", "DOLGUUSDT", "牛来USDT"]
    assert okunan["haric"].dtype == bool
    assert okunan.loc[0, "sozlesme_tipi"] == ""
    beklenen = evren.sort_values(["sembol", "donem_id"], ignore_index=True)
    for sutun in ("donem_baslangic", "donem_bitis"):
        pd.testing.assert_series_equal(
            okunan[sutun].reset_index(drop=True), pd.to_datetime(beklenen[sutun], utc=True).reset_index(drop=True),
            check_names=False,
        )


def test_csv_donem_sinirlarini_iso_zaman_damgasi_olarak_yazar(tmp_path):
    yol = universe.evren_csv_yaz(_sahte_evren(), tmp_path / "universe.csv")
    satirlar = yol.read_text(encoding="utf-8").splitlines()
    assert satirlar[0].split(",") == universe.CSV_SUTUNLARI
    assert "karantina_aylari" not in satirlar[0] and "donem_bas_ay" not in satirlar[0]
    assert "2021-01-05T08:00:00Z" in satirlar[1]


def test_uzerine_yazilmaz(tmp_path):
    yol = universe.evren_csv_yaz(_sahte_evren(), tmp_path / "universe.csv")
    with pytest.raises(FileExistsError):
        universe.evren_csv_yaz(_sahte_evren(), yol)


def test_dosya_yoksa_hata(tmp_path):
    with pytest.raises(FileNotFoundError):
        universe.evren_yukle(tmp_path / "yok.csv")


def test_eski_bicimli_tablo_reddedilir(tmp_path):
    """Rev.7 oncesi (ay duzeyi, karantina sutunlu) tablo sessizce okunmaz."""
    eski = tmp_path / "universe.csv"
    eski.write_text(
        "sembol,ilk_ay,son_ay,dosya_sayisi_4h,funding_dosya_sayisi,sozlesme_tipi,dayanak_tipi,karantina_aylari,"
        "haric,haric_gerekce,donem_id,donem_bas_ay,donem_son_ay\nAAUSDT,2021-01,2021-04,4,4,,,,False,,0,2021-01,2021-04\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        universe.evren_yukle(eski)


def test_yazim_deterministik(tmp_path):
    evren = _sahte_evren()
    a = universe.evren_csv_yaz(evren, tmp_path / "a.csv")
    b = universe.evren_csv_yaz(evren.iloc[::-1], tmp_path / "b.csv")  # ters sirada girdi
    assert a.read_bytes() == b.read_bytes()


def test_okunan_evren_donem_yardimcilariyla_uyumlu(tmp_path):
    yol = universe.evren_csv_yaz(_sahte_evren(), tmp_path / "universe.csv")
    okunan = universe.evren_yukle(yol)
    assert universe.settled_listesi(okunan, "AAUSDT") == ["2021-02"]
    donemler = universe.sembol_donemleri(okunan, "AAUSDT")
    assert len(donemler) == 2 and donemler[1].bitis == pd.Timestamp("2021-01-23 12:00", tz="UTC")
    assert universe.sembol_donemleri(okunan, "DOLGUUSDT") == []
    assert universe.dahil_semboller(okunan) == ["AAUSDT", "DOLGUUSDT"]


def test_karantina_yardimcilari_kaldirildi():
    for ad in ("karantina_listesi", "karantina_kirp", "karantina_haritasi"):
        assert not hasattr(universe, ad), ad


# --- Onbellekle uyusmazlik ---------------------------------------------------


def test_onbellekle_ayniysa_hata_vermez(tmp_path):
    evren = _sahte_evren()
    yol = universe.evren_csv_yaz(evren, tmp_path / "universe.csv")
    universe.evren_onbellekle_dogrula(yol, onbellek=evren)


@pytest.mark.parametrize(
    "boz",
    [
        lambda e: e.assign(settled_aylari=["2021-03"] * len(e)),
        lambda e: e.assign(haric=[True] * len(e)),
        lambda e: e.iloc[:-1],
        lambda e: e.assign(donem_bitis=pd.to_datetime(e["donem_bitis"], utc=True) + pd.Timedelta(hours=4)),
        lambda e: e.assign(donem_gercek_bar_sayisi=e["donem_gercek_bar_sayisi"] + 1),
    ],
)
def test_onbellekle_uyusmazsa_hata_verir(tmp_path, boz):
    evren = _sahte_evren()
    yol = universe.evren_csv_yaz(evren, tmp_path / "universe.csv")
    with pytest.raises(universe.EvrenUyusmazligi):
        universe.evren_onbellekle_dogrula(yol, onbellek=boz(evren.copy()))


# --- Gercek dosya ------------------------------------------------------------
#
# Asagidaki uc test commit edilmis data/universe.csv'yi okur (rev.7 bicimi).

gercek_csv_var = pytest.mark.skipif(not config.UNIVERSE_CSV.exists(), reason="universe.csv yok")


@gercek_csv_var
@pytest.mark.skipif(not ONBELLEK.exists(), reason="onbellekte evren yok")
def test_commit_edilmis_evren_onbellekle_uyusur():
    """Dosya onbellekteki turetilmis evrenle birebir ayni olmali; sapma hata verir."""
    universe.evren_onbellekle_dogrula()


@gercek_csv_var
def test_evren_dahil_sembolleri_split_ile_ayni():
    """split.csv bu evrenden uretildi; dahil semboller birebir ayni olmali."""
    evren = universe.evren_yukle()
    assert universe.dahil_semboller(evren) == sorted(split.split_oku()["sembol"].tolist())


@gercek_csv_var
def test_evren_denetim_olcumleriyle_tutarli():
    """F1 kapanis olcumleriyle (V1, S3) tutarlilik: dahil 678 sembol; CVCUSDT'nin
    ilk donemi 2022-11-29 12:00'de baslayan dolgu kosusundan once biter; TLMUSDT
    iki donemdir; LITUSDT'nin SETTLED ayi denetim sutununda kalir."""
    evren = universe.evren_yukle()
    tekil = evren.drop_duplicates("sembol")
    assert len(tekil) == 864
    assert int((~tekil["haric"]).sum()) == 678
    assert universe.settled_listesi(evren, "LITUSDT") == ["2025-12"]
    assert len(universe.sembol_donemleri(evren, "TLMUSDT")) == 2
    assert universe.sembol_donemleri(evren, "CVCUSDT")[0].bitis == pd.Timestamp("2022-11-29 08:00", tz="UTC")


# --- Turetme yolu analizde kullanilmaz ---------------------------------------


def test_analiz_kodu_evreni_yeniden_turetmez():
    """evren_turet / evren_kur yalnizca data/ ve testlerde kullanilir."""
    izinli = {KOK / "data", KOK / "tests", KOK / ".claude"}
    desen = re.compile(r"\bevren_(turet|kur)\b")
    ihlaller = []
    for yol in KOK.rglob("*.py"):
        if any(p in izinli for p in yol.parents) or "cache" in yol.parts:
            continue
        if desen.search(yol.read_text(encoding="utf-8", errors="replace")):
            ihlaller.append(str(yol.relative_to(KOK)))
    assert ihlaller == []
