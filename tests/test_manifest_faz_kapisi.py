"""`manifest-dogrula --katman tam` faz kapisi (RESULTS §14.42, denetci D-C2): yalnizca acik bir onay kosusu icinde calisir.

Gecici onbellek ve gecici manifest; komut satiri testi gercek depoda calisir ama reddedilen komut hicbir dosya okumaz.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

import config
from conftest import sahte_4h
from data import binance_vision as bv
from data import onbellek_manifest as mf
from onay_yardimcisi import gecici_kayit, kosu

A_SEMBOL = "SOLUSDT"


@pytest.fixture
def manifestli(monkeypatch, tmp_path):
    kok = tmp_path / "onbellek"
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", kok)
    mf._test_manifest_ayarla(tmp_path / "onbellek_manifest.csv")
    bv.donuk_bellek_temizle()
    sahte_4h("2021-01-01 00:00", 12).to_parquet(bv.onbellek_yolu("klines", A_SEMBOL, config.BAR_4H, "2021-01.parquet"),
                                                index=False)
    yol = bv.donuk_liste_yolu()
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps({"mum": {}, "funding": {}}), encoding="utf-8")
    mf.manifest_kur()
    yield kok
    bv.donuk_bellek_temizle()


def test_tam_komutu_kosu_disinda_reddedilir_ve_hicbir_sey_okumaz(manifestli, monkeypatch):
    monkeypatch.setattr(mf, "_onay_listesi", lambda *_: pytest.fail("ayrinti listesi okundu"))
    monkeypatch.setattr(mf, "manifest_dogrula", lambda **_: pytest.fail("dogrulama calisti"))
    with pytest.raises(mf.OnayKatmaniKilitli, match="acik bir onay kosusu"):
        mf._ana(["manifest-dogrula", "--katman", "tam"])


def test_tam_komutu_izin_acikken_de_kosu_ister(manifestli):
    with bv.onay_verisi_izni("test"), pytest.raises(mf.OnayKatmaniKilitli):
        mf._ana(["manifest-dogrula", "--katman", "tam"])


def test_tam_komutu_acik_onay_kosusunda_calisir(manifestli, tmp_path, capsys):
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    with kosu("H2", "C1"):
        assert mf._ana(["manifest-dogrula", "--katman", "tam"]) == 0
    assert "katman: tam" in capsys.readouterr().out


def test_kesif_komutu_kosu_istemez(manifestli):
    assert mf._ana(["manifest-dogrula", "--katman", "kesif"]) == 0


def test_komut_satirinda_tam_reddedilir():
    """Ayri surec: acik onay kosusu olamaz, komut her zaman reddedilir (gercek depoda; reddedilen komut okumaz)."""
    cikti = subprocess.run([sys.executable, "-B", "-m", "data.onbellek_manifest", "manifest-dogrula", "--katman", "tam"],
                           cwd=config.KOK, capture_output=True, text=True)
    assert cikti.returncode != 0
    assert "OnayKatmaniKilitli" in cikti.stderr and "katman: tam" not in cikti.stdout
