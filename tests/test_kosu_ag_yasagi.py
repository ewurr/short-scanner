"""Kosu duzeyinde ag yasagi (on-kayit §3 rev.13; RESULTS §14.41, denetci D-B1).

Hicbir test aga cikmaz: `_oturum` ve `requests.get` tuzakla degistirilir. Tuzak `BaseException` alt sinifidir,
yeniden deneme dongusunde yutulmaz. Yalnizca sentetik veri ve gecici onbellek kullanilir.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import config
from conftest import sahte_4h
from data import binance_vision as bv
from data import funding as funding_modulu
from data import klines, split, universe
from onay_yardimcisi import gecici_depo, gecici_kayit, git, kosu, uzak_depo

A_SEMBOL = "SOLUSDT"
A_ANAHTARI = f"{bv.MUM_ONEKI}/{A_SEMBOL}/{config.BAR_4H}/{A_SEMBOL}-{config.BAR_4H}-2021-01.zip"


class _AgaCikti(BaseException):
    pass


@pytest.fixture
def ag_tuzagi(monkeypatch, tmp_path):
    """Gecici onbellek; aga gercekten cikmak `_AgaCikti` verir, yeniden deneme beklemesi olmaz."""
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", tmp_path / "onbellek")

    def tuzak(*_a, **_k):
        raise _AgaCikti()

    monkeypatch.setattr(bv, "_oturum", tuzak)
    monkeypatch.setattr(universe.requests, "get", tuzak)
    monkeypatch.setattr(bv.time, "sleep", lambda *_: None)


def _b_sembolu() -> str:
    tablo = split.split_oku()
    return str(tablo.loc[tablo["grup"] == "B", "sembol"].iloc[0])


def _ag_yollari(kume="C1", onay=True):
    """Aga cikan yollar; kume kapisi tasiyanlar acik kosu kumesiyle cagrilir."""
    b = _b_sembolu()
    return {
        "mumlari_yukle_yenile": lambda: klines.mumlari_yukle(b, config.BAR_4H, kume, onay=onay, yenile=True),
        "funding_yukle_yenile": lambda: funding_modulu.funding_yukle(b, kume, onay=onay, yenile=True),
        "birincil_gunluk_indir": lambda: klines.birincil_gunluk_indir(b, kume, onay=onay),
        "split_yukle": lambda: split.yukle(b, config.BAR_4H, kume, onay=onay),
        "ay_indir": lambda: klines.ay_indir(A_SEMBOL, config.BAR_4H, "2021-01"),
        "zip_indir": lambda: bv.zip_indir(A_ANAHTARI),
        "iste": lambda: bv._iste("https://ornek.invalid/x"),
        "listele": lambda: bv._listele("data/", ""),
        "mum_dosyalari": lambda: bv.mum_dosyalari(A_SEMBOL, config.BAR_4H),
        "funding_dosyalari": lambda: bv.funding_dosyalari(A_SEMBOL),
        "tum_sembol_dizinleri": bv.tum_sembol_dizinleri,
        "listeyi_dondur": lambda: bv.listeyi_dondur(uzerine_yaz=True),
        "exchange_info": lambda: universe.exchange_info_anlik_kaydet(config.ONBELLEK_DIZINI / "yok.json"),
    }


YOLLAR = ["mumlari_yukle_yenile", "funding_yukle_yenile", "birincil_gunluk_indir", "split_yukle", "ay_indir",
          "zip_indir", "iste", "listele", "mum_dosyalari", "funding_dosyalari", "tum_sembol_dizinleri",
          "listeyi_dondur", "exchange_info"]


@pytest.mark.parametrize("yol", YOLLAR)
def test_onay_kosusu_icinde_aga_cikan_yol_hata_verir(ag_tuzagi, tmp_path, yol):
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    with kosu("H2", "C1"):
        with pytest.raises(bv.KosuAgYasagi):
            _ag_yollari()[yol]()


@pytest.mark.parametrize("yol", YOLLAR)
def test_onay_kosusu_icinde_baska_is_parcacigindan_da_hata_verir(ag_tuzagi, tmp_path, yol):
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")

    def is_():
        try:
            _ag_yollari()[yol]()
        except bv.KosuAgYasagi:
            return "yasak"
        except BaseException as hata:
            return type(hata).__name__
        return "sessiz"

    with kosu("H2", "C1"):
        with ThreadPoolExecutor(max_workers=1) as havuz:
            assert havuz.submit(is_).result(timeout=60) == "yasak"


@pytest.mark.parametrize("yol", ["mum_dosyalari", "funding_dosyalari", "tum_sembol_dizinleri", "listele", "iste",
                                 "zip_indir", "ay_indir", "exchange_info"])
def test_kosu_kapaninca_indirme_araclari_yeniden_aga_cikar(ag_tuzagi, tmp_path, yol):
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    with kosu("H2", "C1"):
        pass
    assert not (bv._KOSU_AGSIZ["sayac"] or bv._KOSU_AGSIZ["devralinan"])
    with pytest.raises(_AgaCikti):
        _ag_yollari()[yol]()


def test_kosu_hatayla_kapaninca_da_yasak_kalkar(ag_tuzagi, tmp_path):
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    with pytest.raises(ZeroDivisionError):
        with kosu("H2", "C1"):
            raise ZeroDivisionError
    assert bv._KOSU_AGSIZ["sayac"] == 0
    assert os.environ.get(bv._AG_YASAGI_ORTAM_ADI) is None
    with pytest.raises(_AgaCikti):
        bv.tum_sembol_dizinleri()


def test_baglam_ic_ice_acilir_ve_son_kapanista_kalkar(ag_tuzagi):
    with bv.kosu_agsiz():
        with bv.kosu_agsiz():
            pass
        with pytest.raises(bv.KosuAgYasagi):
            bv.tum_sembol_dizinleri()
    with pytest.raises(_AgaCikti):
        bv.tum_sembol_dizinleri()


def test_yasak_agsiz_okuma_ihlali_siniftandir(ag_tuzagi):
    """Iki koruma ayni aileden: `AgsizOkumaIhlali` yakalayan kod yasagi da yakalar."""
    assert issubclass(bv.KosuAgYasagi, bv.AgsizOkumaIhlali)


def test_yasak_acikken_kapi_yolu_dondurulmus_listeden_okumaya_devam_eder(ag_tuzagi):
    """Iki koruma ust uste: `agsiz_okuma` icindeki kapi yolu yasaktan etkilenmez, ag da kullanmaz."""
    sahte_4h("2021-01-01 00:00", 12).to_parquet(
        bv.onbellek_yolu("klines", A_SEMBOL, config.BAR_4H, "2021-01.parquet"), index=False)
    yol = bv.donuk_liste_yolu()
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps({"mum": {A_SEMBOL: {config.BAR_4H: [A_ANAHTARI]}}, "funding": {}}), encoding="utf-8")
    with bv.kosu_agsiz():
        assert len(klines.mumlari_yukle(A_SEMBOL, config.BAR_4H, "KESIF")) == 12


def test_onay_kosusunun_git_adimlari_yasaktan_etkilenmez(ag_tuzagi, tmp_path):
    """Yasak veri kaynaklarini kapsar (RESULTS §14.40): gercek git deposunda kayit satirlari uzak depoya itilir ve
    yasak acikken `git fetch` calisir."""
    depo = gecici_depo(tmp_path)
    with kosu("H2", "C1"):
        with pytest.raises(bv.KosuAgYasagi):
            bv.tum_sembol_dizinleri()
        git(depo, "fetch", "-q", "origin")
    uzak_kayit = git(uzak_depo(depo), "show", "main:ONAY_KAYDI.md")
    assert "durum=BASLADI" in uzak_kayit and "durum=BITTI" in uzak_kayit
    assert split.aktif_onay_kosusu() is None


# --- Alt surec ------------------------------------------------------------------------------------

_ALT_SUREC = """
import sys
sys.path.insert(0, sys.argv[1])
from data import binance_vision as bv
try:
    bv.ag_yasagi_denetle("alt surec")
    print("serbest")
except bv.KosuAgYasagi:
    print("yasak")
"""


def _alt_surec(ortam=None) -> str:
    kok = str(Path(__file__).resolve().parents[1])
    cikti = subprocess.run([sys.executable, "-B", "-c", _ALT_SUREC, kok], capture_output=True, text=True, check=True,
                           env=None if ortam is None else {**os.environ, **ortam})
    return cikti.stdout.strip()


def test_baglam_icinde_baslatilan_alt_surec_yasagi_devralir():
    with bv.kosu_agsiz():
        assert _alt_surec() == "yasak"


def test_baglam_disinda_baslatilan_alt_surec_serbesttir():
    assert _alt_surec() == "serbest"


def test_bayat_ortam_degiskeni_yasagi_acmaz():
    assert _alt_surec({bv._AG_YASAGI_ORTAM_ADI: "1"}) == "serbest"
