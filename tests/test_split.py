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
def ornek_split(tmp_path, monkeypatch):
    """Gecici, kurala uygun split.csv (AAUSDT -> A, BBUSDT -> B); config ona yonlendirilir."""
    tablo = split.split_uret(["AAUSDT", "BBUSDT"])
    yol = tmp_path / "split.csv"
    split.split_yaz(tablo, yol)
    monkeypatch.setattr(config, "SPLIT_CSV", yol)
    return tablo


@pytest.fixture
def kayit(tmp_path, monkeypatch):
    yol = tmp_path / "ONAY_KAYDI.md"
    yol.write_text("bas\n", encoding="utf-8")
    monkeypatch.setattr(config, "ONAY_KAYDI", yol)
    return yol


def _yukleyici(sembol, bar):
    # 2020-01-01'den 2026 sonuna kadar uzanan duzenli 4h izgarasi
    return sahte_4h("2020-01-01", 15_000)


def test_kesif_yalnizca_A_grubunu_ve_kesif_donemini_dondurur(ornek_split):
    a = split.yukle("AAUSDT", config.BAR_4H, "KESIF", mum_yukleyici=_yukleyici)
    assert not a.empty
    assert a["open_time"].max() <= pd.Timestamp(config.KESIF_SONU)
    assert a["open_time"].max() < pd.Timestamp("2025-09-01", tz="UTC")

    b = split.yukle("BBUSDT", config.BAR_4H, "KESIF", mum_yukleyici=_yukleyici)
    assert b.empty  # B grubu coini kesifte hicbir bar dondurmez


def test_onay_kumesi_onaysiz_hata_verir_ve_kayit_yazmaz(ornek_split, kayit):
    for kume in ("C1", "C2"):
        with pytest.raises(PermissionError):
            split.yukle("AAUSDT", config.BAR_4H, kume, mum_yukleyici=_yukleyici)
        with pytest.raises(PermissionError):
            split.yukle("AAUSDT", config.BAR_4H, kume, onay=True, mum_yukleyici=_yukleyici)

    assert kayit.read_text(encoding="utf-8") == "bas\n"  # dosyaya hicbir sey eklenmedi


def test_onay_kosusu_kayit_dosyasina_tek_satir_ekler(ornek_split, kayit):
    with split.onay_kosusu("H1", "C1"):
        split.yukle("BBUSDT", config.BAR_4H, "C1", onay=True, mum_yukleyici=_yukleyici)
        split.yukle("AAUSDT", config.BAR_4H, "C1", onay=True, mum_yukleyici=_yukleyici)
    metin = kayit.read_text(encoding="utf-8")
    assert metin.startswith("bas\n")  # onceki icerik korunur, yalnizca eklenir
    satirlar = [s for s in metin.splitlines() if s.startswith("|")]
    assert len(satirlar) == 1 and "| C1 |" in satirlar[0] and "hipotez=H1" in satirlar[0]


def test_c2_donemi_kesif_donemiyle_ortusmez(ornek_split, kayit):
    with split.onay_kosusu("H1", "C2"):
        c2 = split.yukle("AAUSDT", config.BAR_4H, "C2", onay=True, mum_yukleyici=_yukleyici)
    assert c2["open_time"].min() >= pd.Timestamp(config.C2_BASI)
    assert c2["open_time"].max() <= pd.Timestamp(config.C2_SONU)


def test_bilinmeyen_kume_reddedilir(ornek_split):
    with pytest.raises(ValueError):
        split.yukle("AAUSDT", config.BAR_4H, "C3", mum_yukleyici=_yukleyici)


# --- Bolme tablosu dogrulamasi (F1 kapanis bulgusu 9) -------------------------


def test_gercek_split_csv_dogrulamadan_gecer():
    tablo = split.split_oku()
    assert len(tablo) > 0 and set(tablo["grup"]) == {"A", "B"}


def _csv(tmp_path, satirlar: list[str], baslik="sembol,varlik_anahtari,grup"):
    yol = tmp_path / "split.csv"
    yol.write_text("\n".join([baslik, *satirlar]) + "\n", encoding="utf-8")
    return yol


@pytest.mark.parametrize(
    "satirlar",
    [
        ["AAUSDT,AAUSDT,B"],                      # grup SHA256 kuraliyla uyusmuyor
        ["AAUSDT,AAUSDT,A", "AAUSDT,AAUSDT,A"],   # tekrarlanan sembol
        ["AAUSDT,AAUSDT,C"],                      # A/B disi grup
        ["AAUSDT,BBUSDT,B"],                      # varlik anahtari yanlis
        ["AAUSDT,,A"],                            # bos hucre
    ],
    ids=["grup_degistirilmis", "tekrar", "gecersiz_grup", "yanlis_anahtar", "bos_hucre"],
)
def test_bozuk_split_csv_reddedilir(tmp_path, satirlar):
    with pytest.raises(split.BolmeTutarsizligi):
        split.split_oku(_csv(tmp_path, satirlar))


def test_yanlis_sutunlu_split_csv_reddedilir(tmp_path):
    with pytest.raises(split.BolmeTutarsizligi):
        split.split_oku(_csv(tmp_path, ["AAUSDT,A"], baslik="sembol,grup"))


def test_zincir_uyesi_kendi_adiyla_anahtarlanamaz(tmp_path):
    """Yeniden adlandirilmis sembolun anahtari zincirin koku olmali (on-kayit §3)."""
    yeni, eski = next(iter(config.YENIDEN_ADLANDIRMA.items()))
    kok = split.varlik_anahtari(yeni)
    assert kok != yeni
    dogru = f"{yeni},{kok},{split.grup(kok)}"
    split.split_oku(_csv(tmp_path, [dogru]))  # gecer
    with pytest.raises(split.BolmeTutarsizligi):
        split.split_oku(_csv(tmp_path, [f"{yeni},{yeni},{split.grup(yeni)}"]))


def test_split_yaz_kurala_uymayan_tabloyu_yazmaz(tmp_path):
    bozuk = pd.DataFrame({"sembol": ["AAUSDT"], "varlik_anahtari": ["AAUSDT"], "grup": ["B"]})
    with pytest.raises(split.BolmeTutarsizligi):
        split.split_yaz(bozuk, tmp_path / "split.csv")
    assert not (tmp_path / "split.csv").exists()


def test_split_csv_uzerine_yazilmaz(tmp_path):
    yol = tmp_path / "split.csv"
    tablo = split.split_uret(["AAUSDT"])
    split.split_yaz(tablo, yol)
    with pytest.raises(FileExistsError):
        split.split_yaz(tablo, yol)
