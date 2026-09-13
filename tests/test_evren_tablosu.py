"""Sabit evren tablosu testleri (on-kayit §2 rev.4, denetci bulgusu B10).

"Karantina aylari ve listeleme donemi sinirlari data/universe.csv dosyasina
yazilir ve commit edilir. Bu dosya split.csv gibi sabittir; analiz bu dosyadan
okur, canli exchangeInfo'dan yeniden turetmez."
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

import config
from data import donem, split, universe

KOK = Path(__file__).resolve().parents[1]
ONBELLEK = config.ONBELLEK_DIZINI / universe.ONBELLEK_ADI


def _sahte_evren() -> pd.DataFrame:
    donemler_a = donem.donem_sinirlari(
        donem.listeleme_donemleri(["2021-01", "2021-02", "2021-03", "2021-04"], ["2021-02"])
    )
    donemler_b = donem.donem_sinirlari(donem.listeleme_donemleri(["2022-05", "2022-06"]))
    satirlar = []
    for _, d in donemler_a.iterrows():
        satirlar.append(
            {
                "sembol": "AAUSDT", "ilk_ay": "2021-01", "son_ay": "2021-04",
                "dosya_sayisi_4h": 4, "funding_dosya_sayisi": 4,
                "sozlesme_tipi": None, "dayanak_tipi": None,  # delist: exchangeInfo'da yok
                "karantina_aylari": "2021-02", "haric": False, "haric_gerekce": "",
                **d.to_dict(),
            }
        )
    for _, d in donemler_b.iterrows():
        satirlar.append(
            {
                "sembol": "牛来USDT", "ilk_ay": "2022-05", "son_ay": "2022-06",
                "dosya_sayisi_4h": 2, "funding_dosya_sayisi": 2,
                "sozlesme_tipi": "PERPETUAL", "dayanak_tipi": "COIN",
                "karantina_aylari": "", "haric": True, "haric_gerekce": "test gerekcesi",
                **d.to_dict(),
            }
        )
    return pd.DataFrame(satirlar)


# --- Yazma ve okuma ----------------------------------------------------------


def test_yaz_oku_dongusu_ayni_evreni_verir(tmp_path):
    evren = _sahte_evren()
    yol = universe.evren_csv_yaz(evren, tmp_path / "universe.csv")

    okunan = universe.evren_yukle(yol)

    assert list(okunan["sembol"]) == ["AAUSDT", "AAUSDT", "牛来USDT"]
    assert okunan["haric"].dtype == bool
    assert okunan.loc[0, "sozlesme_tipi"] == ""
    pd.testing.assert_series_equal(
        okunan["donem_baslangic"].reset_index(drop=True),
        pd.to_datetime(evren["donem_baslangic"], utc=True).reset_index(drop=True),
        check_names=False,
    )
    pd.testing.assert_series_equal(
        okunan["donem_bitis"].reset_index(drop=True),
        pd.to_datetime(evren["donem_bitis"], utc=True).reset_index(drop=True),
        check_names=False,
    )


def test_csv_zaman_damgasi_icermez(tmp_path):
    yol = universe.evren_csv_yaz(_sahte_evren(), tmp_path / "universe.csv")
    baslik = yol.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert baslik == universe.CSV_SUTUNLARI
    assert "donem_baslangic" not in baslik and "donem_bitis" not in baslik


def test_uzerine_yazilmaz(tmp_path):
    yol = universe.evren_csv_yaz(_sahte_evren(), tmp_path / "universe.csv")
    with pytest.raises(FileExistsError):
        universe.evren_csv_yaz(_sahte_evren(), yol)


def test_dosya_yoksa_hata(tmp_path):
    with pytest.raises(FileNotFoundError):
        universe.evren_yukle(tmp_path / "yok.csv")


def test_yazim_deterministik(tmp_path):
    evren = _sahte_evren()
    a = universe.evren_csv_yaz(evren, tmp_path / "a.csv")
    b = universe.evren_csv_yaz(evren.iloc[::-1], tmp_path / "b.csv")  # ters sirada girdi
    assert a.read_bytes() == b.read_bytes()


def test_okunan_evren_donem_yardimcilariyla_uyumlu(tmp_path):
    yol = universe.evren_csv_yaz(_sahte_evren(), tmp_path / "universe.csv")
    okunan = universe.evren_yukle(yol)
    assert universe.karantina_listesi(okunan, "AAUSDT") == ["2021-02"]
    assert len(universe.sembol_donemleri(okunan, "AAUSDT")) == 2
    assert universe.dahil_semboller(okunan) == ["AAUSDT"]


# --- Onbellekle uyusmazlik ---------------------------------------------------


def test_onbellekle_ayniysa_hata_vermez(tmp_path):
    evren = _sahte_evren()
    yol = universe.evren_csv_yaz(evren, tmp_path / "universe.csv")
    universe.evren_onbellekle_dogrula(yol, onbellek=evren)


@pytest.mark.parametrize(
    "boz",
    [
        lambda e: e.assign(karantina_aylari=["2021-03", "2021-03", ""]),
        lambda e: e.assign(haric=[True, True, True]),
        lambda e: e.assign(donem_son_ay=["2021-01", "2021-05", "2022-06"]),
        lambda e: e.iloc[:-1],
        lambda e: e.assign(
            donem_bitis=pd.to_datetime(e["donem_bitis"], utc=True) + pd.Timedelta(days=1)
        ),
    ],
)
def test_onbellekle_uyusmazsa_hata_verir(tmp_path, boz):
    evren = _sahte_evren()
    yol = universe.evren_csv_yaz(evren, tmp_path / "universe.csv")
    with pytest.raises(universe.EvrenUyusmazligi):
        universe.evren_onbellekle_dogrula(yol, onbellek=boz(evren.copy()))


# --- Gercek dosya ------------------------------------------------------------

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
def test_evren_denetim_raporuyla_tutarli():
    evren = universe.evren_yukle()
    tekil = evren.drop_duplicates("sembol")
    assert len(evren) == 878
    assert len(tekil) == 864
    assert int((~tekil["haric"]).sum()) == 678
    assert universe.karantina_listesi(evren, "LITUSDT") == ["2025-12"]
    assert len(universe.sembol_donemleri(evren, "TLMUSDT")) == 4


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
