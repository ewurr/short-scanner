"""Veri bolmesi testleri (on-kayit §3, CLAUDE.md §3.2-3.3)."""

from __future__ import annotations

import pandas as pd
import pytest

import config
from conftest import sahte_4h
from data import split


def test_bolme_deterministik():
    """Ayni sembol her zaman ayni gruba duser."""
    for _ in range(5):
        assert split.grup("BTCUSDT") == "B"
    ilk = split.split_uret(["AAAUSDT", "BBBUSDT", "CCCUSDT"])
    ikinci = split.split_uret(["CCCUSDT", "AAAUSDT", "BBBUSDT"])
    pd.testing.assert_frame_equal(ilk, ikinci)  # girdi sirasi sonucu degistirmez


def test_bilinen_sembollerin_gruplari_sabit():
    """On-kayit §3'teki SHA256 kuralinin donmus beklenen degerleri."""
    assert split.grup("BTCUSDT") == "B"
    assert split.grup("ETHUSDT") == "B"
    assert split.grup("SOLUSDT") == "A"


def test_yeniden_adlandirma_zinciri_ayni_gruba_duser():
    """Bir varligin tum adlari ayni gruba duser (on-kayit revizyonu, varlik anahtari).

    MATICUSDT tek basina B, POLUSDT tek basina A'dir; zincir tanimlandiginda
    ikisi de zincirin kokune (MATICUSDT) gore B olmalidir.
    """
    assert split.grup("MATICUSDT") != split.grup("POLUSDT")  # ham semboller ayrisiyor

    zincirler = {"POLUSDT": "MATICUSDT"}
    tablo = split.split_uret(["MATICUSDT", "POLUSDT"], zincirler)
    assert tablo["grup"].nunique() == 1
    assert set(tablo["varlik_anahtari"]) == {"MATICUSDT"}


def test_cok_adimli_zincir_kokunu_bulur():
    zincirler = {"CUSDT": "BUSDT_ESKI", "BUSDT_ESKI": "AUSDT_ESKI"}
    assert split.varlik_anahtari("CUSDT", zincirler) == "AUSDT_ESKI"
    tablo = split.split_uret(["AUSDT_ESKI", "BUSDT_ESKI", "CUSDT"], zincirler)
    assert tablo["grup"].nunique() == 1


def test_zincir_dongusu_sonsuz_donmez():
    zincirler = {"XUSDT": "YUSDT", "YUSDT": "XUSDT"}
    assert split.varlik_anahtari("XUSDT", zincirler) in {"XUSDT", "YUSDT"}


@pytest.fixture
def ornek_split():
    return pd.DataFrame(
        {
            "sembol": ["AAUSDT", "BBUSDT"],
            "varlik_anahtari": ["AAUSDT", "BBUSDT"],
            "grup": ["A", "B"],
        }
    )


def _yukleyici(sembol, bar):
    # 2020-01-01'den 2026 sonuna kadar uzanan duzenli 4h izgarasi
    return sahte_4h("2020-01-01", 15_000)


def test_kesif_yalnizca_A_grubunu_ve_kesif_donemini_dondurur(ornek_split):
    a = split.yukle("AAUSDT", config.BAR_4H, "KESIF", split=ornek_split, mum_yukleyici=_yukleyici)
    assert not a.empty
    assert a["open_time"].max() <= pd.Timestamp(config.KESIF_SONU)
    assert a["open_time"].max() < pd.Timestamp("2025-09-01", tz="UTC")

    b = split.yukle("BBUSDT", config.BAR_4H, "KESIF", split=ornek_split, mum_yukleyici=_yukleyici)
    assert b.empty  # B grubu coini kesifte hicbir bar dondurmez


def test_onay_kumesi_onaysiz_hata_verir_ve_kayit_yazmaz(ornek_split, tmp_path, monkeypatch):
    kayit = tmp_path / "ONAY_KAYDI.md"
    kayit.write_text("bas\n", encoding="utf-8")
    monkeypatch.setattr(config, "ONAY_KAYDI", kayit)

    for kume in ("C1", "C2"):
        with pytest.raises(PermissionError):
            split.yukle("AAUSDT", config.BAR_4H, kume, split=ornek_split, mum_yukleyici=_yukleyici)

    assert kayit.read_text(encoding="utf-8") == "bas\n"  # dosyaya hicbir sey eklenmedi


def test_onay_ile_cagri_kayit_dosyasina_satir_ekler(ornek_split, tmp_path, monkeypatch):
    kayit = tmp_path / "ONAY_KAYDI.md"
    kayit.write_text("bas\n", encoding="utf-8")
    monkeypatch.setattr(config, "ONAY_KAYDI", kayit)

    split.yukle(
        "BBUSDT", config.BAR_4H, "C1", onay=True, split=ornek_split, mum_yukleyici=_yukleyici
    )
    metin = kayit.read_text(encoding="utf-8")
    assert metin.startswith("bas\n")  # onceki icerik korunur, yalnizca eklenir
    assert "| C1 |" in metin and "BBUSDT" in metin


def test_c2_donemi_kesif_donemiyle_ortusmez(ornek_split, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ONAY_KAYDI", tmp_path / "k.md")
    c2 = split.yukle(
        "AAUSDT", config.BAR_4H, "C2", onay=True, split=ornek_split, mum_yukleyici=_yukleyici
    )
    assert c2["open_time"].min() >= pd.Timestamp(config.C2_BASI)
    assert c2["open_time"].max() <= pd.Timestamp(config.C2_SONU)


def test_bilinmeyen_kume_reddedilir(ornek_split):
    with pytest.raises(ValueError):
        split.yukle("AAUSDT", config.BAR_4H, "C3", split=ornek_split, mum_yukleyici=_yukleyici)


def test_split_csv_uzerine_yazilmaz(tmp_path):
    yol = tmp_path / "split.csv"
    tablo = split.split_uret(["AAUSDT"])
    split.split_yaz(tablo, yol)
    with pytest.raises(FileExistsError):
        split.split_yaz(tablo, yol)
