"""A1 olcum betiginde funding oran degerine giden kod yolu yoktur (denetci bulgusu D-B1).

1093e69'daki sinir asimindan sonra karar: `a1_olcumu.py` oran (`oran`, `oran_8h`)
sutunlarina hicbir yolda erismez ve hicbir bayrak bu yolu geri acmaz. Bu degerleri
yeniden uretmek bilincli bir kod degisikligi ister. Testler onu sabitler:
kaynak kodda oran sutunu adi gecmez, betigin secenegi yoktur, varsayilan kosu
yalnizca zaman ve aralik sutunlari yazar. Aga cikmaz.

Sinir (denetci bulgusu D-C1): bu testler bugunku durumu sabitler, butun yollari
kapatmaz. Kaynak taramasi yalnizca sutun ADINI arar: dizge sabiti olarak
"oran"/"oran_8h" ve `.oran`/`.oran_8h` ozniteligi. Sutun adini yazmadan degere
ulasan yollari yakalamaz: konumla erisim (`iloc[:, k]`, `itertuples()` demetinin
indeksi), butun cercevenin `to_numpy()`/`values` ile alinmasi, adin calisma
aninda kurulmasi (`"or" + "an"`, `getattr(r, ad)`) ya da veri katmanindaki bir
fonksiyonun degeri hesaplayip dondurmesi. Uctan uca kosu da yalnizca calisan
yollar icin gecerlidir ve yalnizca sutunun CIKTIYA yazilmadigini dogrular.
"""

from __future__ import annotations

import ast
import importlib.util
import json

import pandas as pd
import pytest

import config
from data import binance_vision as bv
from data import funding as funding_modulu
from data import universe as universe_modulu

A1_YOLU = config.ANALIZ_DIZINI / "00_veri_denetimi" / "a1_olcumu.py"
ORAN_SUTUNLARI = {"oran", "oran_8h"}


@pytest.fixture(scope="module")
def a1():
    spec = importlib.util.spec_from_file_location("a1_olcumu_deger", A1_YOLU)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _kod_agaci() -> ast.Module:
    return ast.parse(A1_YOLU.read_text(encoding="utf-8"))


def test_kodda_oran_sutunu_adi_gecmez():
    """Belge metni disinda hicbir dizge sabiti oran sutununu adlandirmamali."""
    agac = _kod_agaci()
    belgeler = {ast.get_docstring(d) for d in ast.walk(agac)
                if isinstance(d, (ast.Module, ast.FunctionDef, ast.ClassDef))}
    sabitler = [d.value for d in ast.walk(agac)
                if isinstance(d, ast.Constant) and isinstance(d.value, str) and d.value not in belgeler]
    kacaklar = [x for x in sabitler if x in ORAN_SUTUNLARI]
    assert not kacaklar, f"oran sutunu kodda geciyor: {kacaklar}"


def test_kodda_oran_ozniteligi_kullanilmaz():
    """`.oran` / `.oran_8h` oznitelik erisimi de olmamali (itertuples yolu)."""
    kacaklar = [d.attr for d in ast.walk(_kod_agaci())
                if isinstance(d, ast.Attribute) and d.attr in ORAN_SUTUNLARI]
    assert not kacaklar


def test_oran_karsilastirma_yolu_kaldirildi(a1):
    for ad in ("oran_karsilastir", "CIKTI_ORAN", "CIKTI_TESLIMSIZ", "REFERANS_KAYIT"):
        assert not hasattr(a1, ad), f"{ad} hala var"


def test_betigin_secenegi_yok(a1, capsys):
    """Hicbir bayrak oran degeri yolunu geri acamaz: yardim metninde secenek yok."""
    with pytest.raises(SystemExit):
        a1.main(["--help"])
    yardim = capsys.readouterr().out
    assert "oran" not in yardim.lower()
    with pytest.raises(SystemExit):
        a1.main(["--oran-degerleri"])


def test_iz_dosyalari_calisma_agacinda_yok():
    dizin = config.ANALIZ_DIZINI / "00_veri_denetimi"
    for ad in ("a1_uzlasma_sonrasi_oranlar_tam.csv", "a1_teslimsiz_son_bar_funding_tam.csv"):
        assert not (dizin / ad).exists(), f"{ad} calisma agacinda durmamali (1093e69'da var)"


# --- Varsayilan kosu: sentetik veri, tmp dizin, ag yok -------------------------


def _goruntu(yol, sembol, teslim_ms):
    ham = json.dumps({"serverTime": 1, "symbols": [
        {"symbol": sembol, "contractType": "PERPETUAL", "underlyingType": "COIN",
         "status": "SETTLING", "deliveryDate": teslim_ms, "onboardDate": 1569398400000},
    ]})
    yol.write_text(json.dumps(universe_modulu.exchange_info_anlik_goruntu(
        ham, pd.Timestamp("2026-09-18", tz="UTC"))), encoding="utf-8")


def test_varsayilan_kosu_yalnizca_zaman_ve_aralik_yazar(a1, tmp_path, monkeypatch):
    """Uctan uca varsayilan kosu: uretilen CSV'lerin hicbirinde oran sutunu olmamali
    ve iz dosyalari yazilmamali."""
    sembol = "XUSDT"
    bitis = pd.Timestamp("2025-04-14 08:00", tz="UTC")
    evren = pd.DataFrame([{
        "sembol": sembol, "haric": False, "donem_id": 0,
        "donem_baslangic": pd.Timestamp("2025-04-01 00:00", tz="UTC"), "donem_bitis": bitis,
        "donem_bar_sayisi": 80, "donem_gercek_bar_sayisi": 80, "donem_funding_yok": False,
        "settled_aylari": "",
    }])
    zamanlar = pd.date_range("2025-04-12 00:00", "2025-04-14 12:00", freq="4h", tz="UTC")
    fund = pd.DataFrame({"odeme_zamani": zamanlar, "aralik_saat": 4, "oran": 0.5, "oran_8h": 1.0})

    _goruntu(tmp_path / "ei.json", sembol, int(pd.Timestamp("2025-04-14 09:00", tz="UTC").timestamp() * 1000))
    monkeypatch.setattr(config, "EXCHANGE_INFO_ANLIK", tmp_path / "ei.json")
    monkeypatch.setattr(universe_modulu, "evren_yukle", lambda *a, **k: evren)
    monkeypatch.setattr(universe_modulu, "dahil_semboller", lambda e: [sembol])
    monkeypatch.setattr(funding_modulu, "ham_funding_yukle", lambda s, yenile=False: fund.copy())
    monkeypatch.setattr(bv, "tum_sembol_dizinleri", lambda: [sembol])
    for ad in ("CIKTI", "CIKTI_KONUM", "CIKTI_ONERI", "CIKTI_D", "CIKTI_ORTAM"):
        monkeypatch.setattr(a1, ad, tmp_path / getattr(a1, ad).name)

    a1.main([])

    uretilen = sorted(tmp_path.glob("*.csv"))
    assert uretilen, "varsayilan kosu hicbir CSV uretmedi"
    for yol in uretilen:
        sutunlar = set(pd.read_csv(yol, nrows=0).columns)
        assert not (sutunlar & ORAN_SUTUNLARI), f"{yol.name} oran sutunu yaziyor: {sutunlar}"
    for ad in ("a1_uzlasma_sonrasi_oranlar_tam.csv", "a1_teslimsiz_son_bar_funding_tam.csv"):
        assert not (tmp_path / ad).exists(), f"{ad} varsayilan kosuda yazilmamali"
    # Olcum gercekten calisti: uzlasma sonrasi 12:00 kaydi bulundu.
    assert len(pd.read_csv(tmp_path / a1.CIKTI.name)) == 1
