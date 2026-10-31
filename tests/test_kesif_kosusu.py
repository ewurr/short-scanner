"""F2 giris noktasi: `split.kesif_kosusu` (on-kayit §3 rev.13; RESULTS §14.41).

Hicbir test aga cikmaz; aga cikmak tuzak verir. Gecici onbellek ve gecici manifest kullanilir.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

import config
from conftest import sahte_4h
from data import binance_vision as bv
from data import funding as funding_modulu
from data import klines, kume_bellegi, onbellek_manifest as mf
from data import split, universe
from onay_yardimcisi import gecici_kayit, kosu

A_SEMBOL = "SOLUSDT"
AY = "2021-01"
ANAHTAR = f"{bv.MUM_ONEKI}/{A_SEMBOL}/{config.BAR_4H}/{A_SEMBOL}-{config.BAR_4H}-{AY}.zip"


class _AgaCikti(BaseException):
    pass


@pytest.fixture
def ortam(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", tmp_path / "onbellek")
    mf._test_manifest_ayarla(tmp_path / "onbellek_manifest.csv")

    def tuzak(*_a, **_k):
        raise _AgaCikti()

    monkeypatch.setattr(bv, "_oturum", tuzak)
    monkeypatch.setattr(universe.requests, "get", tuzak)
    monkeypatch.setattr(bv.time, "sleep", lambda *_: None)
    bv.donuk_bellek_temizle()
    kume_bellegi.temizle()
    sahte_4h("2021-01-01 00:00", 12).to_parquet(bv.onbellek_yolu("klines", A_SEMBOL, config.BAR_4H, f"{AY}.parquet"),
                                                index=False)
    yol = bv.donuk_liste_yolu()
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps({"mum": {A_SEMBOL: {config.BAR_4H: [ANAHTAR]}}, "funding": {}}), encoding="utf-8")
    mf.manifest_kur()
    yield
    bv.donuk_bellek_temizle()
    kume_bellegi.temizle()


def _ag_yollari():
    return {
        "mumlari_yukle_yenile": lambda: klines.mumlari_yukle(A_SEMBOL, config.BAR_4H, "KESIF", yenile=True),
        "funding_yukle_yenile": lambda: funding_modulu.funding_yukle(A_SEMBOL, "KESIF", yenile=True),
        "birincil_gunluk_indir": lambda: klines.birincil_gunluk_indir(A_SEMBOL, "KESIF"),
        "ay_indir": lambda: klines.ay_indir(A_SEMBOL, config.BAR_4H, AY),
        "zip_indir": lambda: bv.zip_indir(ANAHTAR),
        "iste": lambda: bv._iste("https://ornek.invalid/x"),
        "mum_dosyalari": lambda: bv.mum_dosyalari(A_SEMBOL, config.BAR_4H),
        "tum_sembol_dizinleri": bv.tum_sembol_dizinleri,
        "listeyi_dondur": lambda: bv.listeyi_dondur(uzerine_yaz=True),
        "exchange_info": lambda: universe.exchange_info_anlik_kaydet(config.ONBELLEK_DIZINI / "yok.json"),
    }


YOLLAR = ["mumlari_yukle_yenile", "funding_yukle_yenile", "birincil_gunluk_indir", "ay_indir", "zip_indir", "iste",
          "mum_dosyalari", "tum_sembol_dizinleri", "listeyi_dondur", "exchange_info"]


@pytest.mark.parametrize("yol", YOLLAR)
def test_kosu_icinde_aga_cikan_yol_hata_verir(ortam, yol):
    with split.kesif_kosusu():
        with pytest.raises(bv.KosuAgYasagi):
            _ag_yollari()[yol]()


@pytest.mark.parametrize("yol", YOLLAR)
def test_kosu_icinde_baska_is_parcacigindan_da_hata_verir(ortam, yol):
    def is_():
        try:
            _ag_yollari()[yol]()
        except bv.KosuAgYasagi:
            return "yasak"
        except BaseException as hata:
            return type(hata).__name__
        return "sessiz"

    with split.kesif_kosusu():
        with ThreadPoolExecutor(max_workers=1) as havuz:
            assert havuz.submit(is_).result(timeout=60) == "yasak"


_ALT_SUREC = """
import sys
sys.path.insert(0, sys.argv[1])
from data import binance_vision as bv
from data import klines
sonuc = []
for cagri in (bv.tum_sembol_dizinleri, lambda: klines.ay_indir("SOLUSDT", "4h", "2021-01")):
    try:
        cagri()
        sonuc.append("sessiz")
    except bv.KosuAgYasagi:
        sonuc.append("yasak")
print(" ".join(sonuc))
"""


def _alt_surec() -> list[str]:
    cikti = subprocess.run([sys.executable, "-B", "-c", _ALT_SUREC, str(config.KOK)], capture_output=True, text=True,
                           check=True)
    return cikti.stdout.split()


def test_kosu_icinde_baslatilan_dogrudan_alt_surec_yasagi_devralir(ortam):
    with split.kesif_kosusu():
        assert _alt_surec() == ["yasak", "yasak"]


def test_kapi_yolu_kosu_icinde_okur(ortam):
    with split.kesif_kosusu():
        assert len(klines.mumlari_yukle(A_SEMBOL, config.BAR_4H, "KESIF")) == 12


def test_acilista_kesif_dogrulanir_tam_cagrilmaz(ortam, monkeypatch):
    katmanlar = []
    gercek = mf.manifest_dogrula
    monkeypatch.setattr(mf, "manifest_dogrula", lambda *, katman: (katmanlar.append(katman), gercek(katman=katman))[1])
    monkeypatch.setattr(mf, "_onay_sorunlari", lambda *_: pytest.fail("onay katmani denetlendi"))
    with split.kesif_kosusu():
        assert katmanlar == ["kesif"]
    assert katmanlar == ["kesif"]


def test_kesif_hata_verince_kosu_acilmaz(ortam):
    hedef = config.ONBELLEK_DIZINI / "klines" / A_SEMBOL / config.BAR_4H / f"{AY}.parquet"
    hedef.write_bytes(hedef.read_bytes() + b"x")
    with pytest.raises(mf.ManifestUyusmazligi, match=AY):
        with split.kesif_kosusu():
            pytest.fail("kosu acildi")
    assert bv._KOSU_AGSIZ["sayac"] == 0


def test_manifest_yoksa_kosu_acilmaz(ortam):
    mf._etkin_yol().unlink()
    with pytest.raises(mf.ManifestYok):
        with split.kesif_kosusu():
            pytest.fail("kosu acildi")


def test_onbellekler_acilis_ve_kapanista_temizlenir(ortam):
    kume_bellegi._BELLEK["sahte"] = 1
    bv._DONUK_BELLEK.update(kimlik=("x",), veri={"mum": {}})
    mf._BELLEK["sahte"] = 1
    with split.kesif_kosusu():
        assert "sahte" not in kume_bellegi._BELLEK
        assert bv._DONUK_BELLEK == {} and "sahte" not in mf._BELLEK
        kume_bellegi._BELLEK["sahte"] = 1
        bv._DONUK_BELLEK.update(kimlik=("y",), veri={"mum": {}})
        mf._BELLEK["sahte"] = 1
    assert "sahte" not in kume_bellegi._BELLEK
    assert bv._DONUK_BELLEK == {} and "sahte" not in mf._BELLEK


def test_kapanista_yasak_kalkar_hata_olsa_da(ortam):
    with pytest.raises(ZeroDivisionError):
        with split.kesif_kosusu():
            raise ZeroDivisionError
    assert bv._KOSU_AGSIZ["sayac"] == 0
    assert os.environ.get(bv._AG_YASAGI_ORTAM_ADI) is None
    assert bv._DONUK_BELLEK == {}
    with pytest.raises(_AgaCikti):
        bv.tum_sembol_dizinleri()


def test_acik_onay_kosusunda_kesif_kosusu_acilmaz(ortam, tmp_path):
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    with kosu("H2", "C1"):
        with pytest.raises(RuntimeError):
            with split.kesif_kosusu():
                pytest.fail("kosu acildi")
