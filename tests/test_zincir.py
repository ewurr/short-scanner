"""On-kayit §3 rev.2: dokuz yeniden adlandirma zinciri ve bolme butunlugu."""

from __future__ import annotations

import config
from data import split


ZINCIRLER = [
    ("LENDUSDT", "AAVEUSDT"),
    ("BTTUSDT", "1000BTTCUSDT"),
    ("RNDRUSDT", "RENDERUSDT"),
    ("GALUSDT", "GUSDT"),
    ("MATICUSDT", "POLUSDT"),
    ("EOSUSDT", "AUSDT"),
    ("LUNAUSDT", "1000LUNCUSDT"),
    ("TOMOUSDT", "VICUSDT"),
    ("DODOUSDT", "DODOXUSDT"),
]


def test_on_kayitta_dokuz_zincir_var():
    assert len(config.YENIDEN_ADLANDIRMA) == 9


def test_zincir_uyeleri_ayni_gruba_duser():
    """On-kayit §3 rev.2: zincirdeki tum semboller ayni gruba duser."""
    for eski, yeni in ZINCIRLER:
        assert split.varlik_anahtari(yeni) == eski, f"{yeni} -> {eski} beklendi"
        assert split.grup(split.varlik_anahtari(eski)) == split.grup(
            split.varlik_anahtari(yeni)
        ), f"{eski} ve {yeni} farkli gruplara dustu"


def test_zincir_tablosu_tek_grup_verir():
    for eski, yeni in ZINCIRLER:
        tablo = split.split_uret([eski, yeni])
        assert tablo["grup"].nunique() == 1
        assert set(tablo["varlik_anahtari"]) == {eski}


def test_matic_pol_sizintisi_kapandi():
    """Ham sembol bolmesinde ayrisiyorlardi; varlik anahtari bunu kapatir."""
    assert split.grup("MATICUSDT") != split.grup("POLUSDT")  # ham semboller
    tablo = split.split_uret(["MATICUSDT", "POLUSDT"])
    assert tablo["grup"].nunique() == 1


def test_birlesme_zincir_sayilmaz():
    """KEEP + NU -> T birlesmedir, ad degisikligi degil (on-kayit §3 rev.2)."""
    for sembol in ("KEEPUSDT", "NUUSDT", "TUSDT"):
        assert split.varlik_anahtari(sembol) == sembol
    assert "TUSDT" not in config.YENIDEN_ADLANDIRMA


def test_zincir_disi_sembol_kendi_anahtaridir():
    for sembol in ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BUSDT"):
        assert split.varlik_anahtari(sembol) == sembol


def test_bos_zincir_sozlugu_acikca_verilebilir():
    """Testlerde zincirsiz davranis icin bos sozluk gecilebilmeli."""
    assert split.varlik_anahtari("POLUSDT", {}) == "POLUSDT"
