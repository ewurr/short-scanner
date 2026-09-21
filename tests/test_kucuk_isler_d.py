"""Denetci bulgulari D-C3, D-C4, D-C5 (kucuk isler). Aga cikmaz.

- D-C3: `a1_olcumu.main` icindeki exchangeInfo disi kolu uctan uca.
- D-C4: `calistir.csv_yaz` benzersiz gecici dosya adi kullanir ve hata
  durumunda gecici dosyayi siler.
- D-C5: temsili giris suresi `config.py`'de; betik kendi degerini tanimlamaz.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

import config
from data import binance_vision as bv
from data import funding as funding_modulu
from data import universe as universe_modulu

DIZIN = config.ANALIZ_DIZINI / "00_veri_denetimi"
sys.path.insert(0, str(DIZIN))


def _yukle(ad: str, dosya: str):
    spec = importlib.util.spec_from_file_location(ad, DIZIN / dosya)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


calistir = _yukle("_kucuk_d_calistir", "calistir.py")
a1 = _yukle("_kucuk_d_a1", "a1_olcumu.py")

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731


# --- D-C4: csv_yaz ---------------------------------------------------------------


def test_csv_yaz_gecici_dosya_adi_her_cagrida_farkli(tmp_path, monkeypatch):
    """Ayni hedefe iki yazma ayni gecici dosyayi kullanmamali; eszamanli iki
    kosu birbirinin yarim dosyasini yerine koyamaz. Gecici dosya hedefle ayni
    dizinde olmali (os.replace ayni dosya sisteminde atomiktir)."""
    kaynaklar = []
    gercek = os.replace

    def kaydeden(kaynak, hedef):
        kaynaklar.append(Path(kaynak))
        gercek(kaynak, hedef)

    monkeypatch.setattr(calistir.os, "replace", kaydeden)
    hedef = tmp_path / "cikti.csv"
    calistir.csv_yaz(pd.DataFrame({"a": [1]}), hedef)
    calistir.csv_yaz(pd.DataFrame({"a": [2]}), hedef)
    assert len(kaynaklar) == 2
    assert kaynaklar[0] != kaynaklar[1]
    assert all(k.parent == tmp_path for k in kaynaklar)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["cikti.csv"]


@pytest.mark.parametrize("asama", ["to_csv", "replace"])
def test_csv_yaz_hatada_gecici_dosya_silinir(tmp_path, monkeypatch, asama):
    """Yazma ya da yeniden adlandirma patlarsa dizinde gecici dosya kalmamali ve
    var olan hedef bozulmamali; hata yutulmamali."""
    hedef = tmp_path / "cikti.csv"
    hedef.write_text("a\n1\n", encoding="utf-8")

    if asama == "to_csv":
        def patlayan(self, yol, *a, **k):
            Path(yol).write_text("YARIM", encoding="utf-8")
            raise RuntimeError("yazma hatasi")
        monkeypatch.setattr(pd.DataFrame, "to_csv", patlayan)
    else:
        def patlayan(kaynak, hedef_):
            raise OSError("yeniden adlandirma hatasi")
        monkeypatch.setattr(calistir.os, "replace", patlayan)

    with pytest.raises((RuntimeError, OSError)):
        calistir.csv_yaz(pd.DataFrame({"a": [9]}), hedef)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["cikti.csv"]
    assert hedef.read_text(encoding="utf-8") == "a\n1\n"


# --- D-C5: temsili giris suresi config'te ---------------------------------------


def test_temsili_giris_suresi_configte():
    assert pd.Timedelta(config.DENETIM_TEMSILI_GIRIS_SURE) == pd.Timedelta(hours=24)
    assert a1.TEMSILI_GIRIS_SURE == pd.Timedelta(config.DENETIM_TEMSILI_GIRIS_SURE)


def test_a1_betigi_sureyi_kendisi_tanimlamaz():
    """Betikte Timedelta(hours=...) ile sabit bir giris suresi kurulmamali; deger
    yalnizca config'ten gelir."""
    agac = ast.parse((DIZIN / "a1_olcumu.py").read_text(encoding="utf-8"))
    for dugum in ast.walk(agac):
        if isinstance(dugum, ast.Assign) and any(
                isinstance(h, ast.Name) and h.id == "TEMSILI_GIRIS_SURE" for h in dugum.targets):
            kaynak = ast.unparse(dugum.value)
            assert "config.DENETIM_TEMSILI_GIRIS_SURE" in kaynak, kaynak
            assert "hours" not in kaynak, kaynak


# --- D-C3: exchangeInfo disi kolu uctan uca -------------------------------------


def _goruntu(yol, semboller):
    ham = json.dumps({"serverTime": 1, "symbols": semboller})
    yol.write_text(json.dumps(universe_modulu.exchange_info_anlik_goruntu(
        ham, pd.Timestamp("2026-09-18", tz="UTC"))), encoding="utf-8")


def _evren_satiri(sembol, bas, bitis):
    return {"sembol": sembol, "haric": False, "donem_id": 0, "donem_baslangic": bas, "donem_bitis": bitis,
            "donem_bar_sayisi": 80, "donem_gercek_bar_sayisi": 80, "donem_funding_yok": False,
            "settled_aylari": ""}


def test_exchangeinfo_disi_kolu_uctan_uca(tmp_path, monkeypatch):
    """Goruntude bulunmayan (deliveryDate'i olmayan) bir delist sembolde:
    - `a1_konumlar`: son barin acilisi ile kapanisi arasindaki kayitlar (uclar
      dahil) deliveryDate'siz konumla yazilir; son bardan onceki kayit yazilmaz;
    - `a1_uzlasma_sonrasi_funding`: deliveryDate'i olmadigi icin bu sembol yoktur;
    - `a1_d_kurali`: donem sonu turu `delist_exchangeInfo_disi`, kural uygulanir.
    Ikinci sembol (SETTLING) sinif ayriminin karismadigini gosterir."""
    disi, settling = "DISIUSDT", "SETUSDT"
    bitis = T("2025-04-14 08:00")
    evren = pd.DataFrame([_evren_satiri(disi, T("2025-04-01 00:00"), bitis),
                          _evren_satiri(settling, T("2025-04-01 00:00"), bitis)])
    _goruntu(tmp_path / "ei.json", [
        {"symbol": settling, "contractType": "PERPETUAL", "underlyingType": "COIN", "status": "SETTLING",
         "deliveryDate": int(T("2025-04-14 09:00").timestamp() * 1000), "onboardDate": 1569398400000},
    ])
    zamanlar = pd.date_range(T("2025-04-12 00:00"), T("2025-04-14 12:00"), freq="4h")
    fund = pd.DataFrame({"odeme_zamani": zamanlar, "aralik_saat": 4})

    monkeypatch.setattr(config, "EXCHANGE_INFO_ANLIK", tmp_path / "ei.json")
    monkeypatch.setattr(universe_modulu, "evren_yukle", lambda *a, **k: evren)
    monkeypatch.setattr(funding_modulu, "ham_funding_yukle", lambda s, yenile=False: fund.copy())
    monkeypatch.setattr(bv, "tum_sembol_dizinleri", lambda: [disi, settling])
    for ad in ("CIKTI", "CIKTI_KONUM", "CIKTI_ONERI", "CIKTI_D", "CIKTI_ORTAM"):
        monkeypatch.setattr(a1, ad, tmp_path / getattr(a1, ad).name)

    a1.main([])

    konum = pd.read_csv(tmp_path / a1.CIKTI_KONUM.name)
    k_disi = konum.loc[konum["sembol"] == disi]
    assert set(k_disi["sinif"]) == {"exchangeInfo_disi"}
    assert sorted(k_disi["konum"]) == ["son_bar_acilisi", "son_bar_kapanisi"]
    assert k_disi["deliveryDate"].isna().all()
    assert pd.to_datetime(k_disi["son_bar_acilisi"], utc=True).eq(bitis).all()

    uzlasma = pd.read_csv(tmp_path / a1.CIKTI.name)
    assert disi not in set(uzlasma["sembol"])
    assert set(uzlasma["sembol"]) == {settling}

    d = pd.read_csv(tmp_path / a1.CIKTI_D.name)
    d_disi = d.loc[d["sembol"] == disi]
    assert set(d_disi["tur"]) == {"delist_exchangeInfo_disi"}
    assert d_disi["kural_uygulanir"].all()
    assert set(d.loc[d["sembol"] == settling, "tur"]) == {"delist_SETTLING"}
