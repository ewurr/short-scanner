"""Kosu duzeyinde kilit (calistir.py, a1_olcumu.py) ve delist tablosunda UTC tarih
sutunlari. Sizinti testcisi bulgulari (tests/test_tur_saldirilari_d.py). Aga cikmaz.

- Ayni betigin ikinci kosusu, acik bir hata mesajiyla ve hicbir sey yazmadan
  baslamayi reddeder.
- Kilit, kosu hata ile bitse de birakilir.
- `universe.delist_sinifi` ve `calistir.delist_tablosu`nun tarih sutunlari, tamami
  NaT olsa bile UTC saat dilimlidir.
"""

from __future__ import annotations

import importlib.util
import json
import sys

import pandas as pd
import pytest

import config
from data import universe as universe_modulu

DIZIN = config.ANALIZ_DIZINI / "00_veri_denetimi"
sys.path.insert(0, str(DIZIN))


def _yukle(ad: str, dosya: str):
    spec = importlib.util.spec_from_file_location(ad, DIZIN / dosya)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


calistir = _yukle("_kilit_calistir", "calistir.py")
a1 = _yukle("_kilit_a1", "a1_olcumu.py")


# --- kosu_kilidi --------------------------------------------------------------


def test_ikinci_kosu_acik_mesajla_reddedilir(tmp_path):
    with calistir.kosu_kilidi("x", tmp_path) as yol:
        assert yol.exists()
        with pytest.raises(calistir.KosuKilidiHatasi, match="zaten calisiyor"):
            with calistir.kosu_kilidi("x", tmp_path):
                pytest.fail("ikinci kosu baslamamaliydi")
        assert yol.exists(), "reddedilen kosu ilk kosunun kilidini silmemeli"
    assert not yol.exists()


def test_kilit_hata_durumunda_birakilir(tmp_path):
    with pytest.raises(RuntimeError, match="kosu hatasi"):
        with calistir.kosu_kilidi("x", tmp_path):
            raise RuntimeError("kosu hatasi")
    assert list(tmp_path.iterdir()) == []
    with calistir.kosu_kilidi("x", tmp_path):
        pass  # kilit birakildigi icin yeni kosu baslayabilir


def test_farkli_betiklerin_kilitleri_ayri(tmp_path):
    with calistir.kosu_kilidi("calistir", tmp_path), calistir.kosu_kilidi("a1_olcumu", tmp_path):
        assert sorted(p.name for p in tmp_path.iterdir()) == [".a1_olcumu.kilit", ".calistir.kilit"]


def _ciktilari_yonlendir(monkeypatch, tmp_path):
    for ad in ("CIKTI", "CIKTI_KONUM", "CIKTI_ONERI", "CIKTI_D", "CIKTI_ORTAM"):
        monkeypatch.setattr(a1, ad, tmp_path / getattr(a1, ad).name)


def test_a1_ikinci_kosu_hicbir_sey_yazmadan_reddedilir(tmp_path, monkeypatch):
    _ciktilari_yonlendir(monkeypatch, tmp_path)
    (tmp_path / ".a1_olcumu.kilit").write_text("pid=1", encoding="utf-8")

    def _yuklenmemeli(*a, **k):
        raise AssertionError("kilitliyken veri yuklenmemeli")

    monkeypatch.setattr(universe_modulu, "evren_yukle", _yuklenmemeli)
    # a1 sinifi `calistir` adli modulden alir; bu test dosyayi baska adla yukler.
    with pytest.raises(a1.KosuKilidiHatasi) as hata:
        a1.main([])
    assert "a1_olcumu" in str(hata.value) and "pid=1" in str(hata.value)
    assert sorted(p.name for p in tmp_path.iterdir()) == [".a1_olcumu.kilit"]


def test_a1_hata_ile_biten_kosu_kilidi_birakir(tmp_path, monkeypatch):
    _ciktilari_yonlendir(monkeypatch, tmp_path)

    def _patla(*a, **k):
        raise RuntimeError("evren okunamadi")

    monkeypatch.setattr(universe_modulu, "evren_yukle", _patla)
    with pytest.raises(RuntimeError, match="evren okunamadi"):
        a1.main([])
    assert not (tmp_path / ".a1_olcumu.kilit").exists()


def test_calistir_ikinci_kosu_reddedilir_ve_hata_ile_bitince_kilit_birakilir(tmp_path, monkeypatch):
    monkeypatch.setattr(calistir, "CIKTI_DIZINI", tmp_path)
    monkeypatch.setattr(sys, "argv", ["calistir.py"])
    (tmp_path / ".calistir.kilit").write_text("pid=1", encoding="utf-8")

    def _kosmamali(argumanlar):
        raise AssertionError("kilitliyken kosu baslamamali")

    monkeypatch.setattr(calistir, "_kos", _kosmamali)
    with pytest.raises(calistir.KosuKilidiHatasi, match="calistir zaten calisiyor"):
        calistir.main()
    assert (tmp_path / ".calistir.kilit").read_text(encoding="utf-8") == "pid=1"

    (tmp_path / ".calistir.kilit").unlink()

    def _patla(argumanlar):
        raise RuntimeError("kosu hatasi")

    monkeypatch.setattr(calistir, "_kos", _patla)
    with pytest.raises(RuntimeError, match="kosu hatasi"):
        calistir.main()
    assert not (tmp_path / ".calistir.kilit").exists()


def test_kilit_dosyasi_git_disinda():
    ignore = (config.KOK / ".gitignore").read_text(encoding="utf-8")
    assert "analysis/**/.*.kilit" in ignore


# --- UTC tarih sutunlari ---------------------------------------------------------


def _goruntu_yolu(tmp_path, semboller):
    ham = json.dumps({"serverTime": 1, "symbols": semboller})
    yol = tmp_path / "ei.json"
    yol.write_text(json.dumps(universe_modulu.exchange_info_anlik_goruntu(
        ham, pd.Timestamp("2026-09-18", tz="UTC"))), encoding="utf-8")
    return yol


def test_delist_sinifi_yalniz_exchangeinfo_disi_iken_utc(tmp_path):
    """Goruntude hic sembol yok: butun semboller exchangeInfo disi, deliveryDate
    tamamen NaT. Sutun yine de UTC saat dilimli olmali."""
    evren = pd.DataFrame([{"sembol": "AUSDT", "haric": False, "donem_id": 0,
                           "donem_bitis": pd.Timestamp("2025-04-14 08:00", tz="UTC")}])
    anlik = universe_modulu.exchange_info_anlik_yukle(_goruntu_yolu(tmp_path, []))
    tablo = universe_modulu.delist_sinifi(evren, anlik)
    assert str(tablo["deliveryDate"].dtype) == "datetime64[ns, UTC]"
    assert str(tablo["son_donem_bitis"].dtype).endswith("UTC]")
    assert tablo["deliveryDate"].isna().all()


def test_delist_tablosu_yalniz_exchangeinfo_disi_cokmez(tmp_path, monkeypatch):
    evren = pd.DataFrame([{"sembol": "AUSDT", "haric": False, "donem_id": 0,
                           "donem_bitis": pd.Timestamp("2025-04-14 08:00", tz="UTC")}])
    monkeypatch.setattr(config, "EXCHANGE_INFO_ANLIK", _goruntu_yolu(tmp_path, []))
    detay = {"sembol": "AUSDT", "son_bar": pd.Timestamp("2025-04-20 20:00", tz="UTC"), "dolgu_bar_son": 0,
             "_funding_zamanlari": pd.DatetimeIndex([pd.Timestamp("2025-04-14 12:00", tz="UTC")])}
    tablo = calistir.delist_tablosu(evren, [detay])
    assert str(tablo["deliveryDate"].dtype) == "datetime64[ns, UTC]"
    assert tablo["teslim_eksi_bitis_saat"].isna().all()
    assert tablo["teslimden_sonra_funding_kayit"].isna().all()
