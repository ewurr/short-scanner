"""Kesif kosusunun commit bagi ve kayit nesnesi (RESULTS §14.42, denetci D-B2).

Gercek git test deposu (`gecici_depo`) icinde manifest, split.csv ve universe.csv commit edilir; onbellek gecici
dizindedir. Aga cikilmaz; gercek `cache/` dosyalarina dokunulmaz.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess

import pytest

import config
from conftest import sahte_4h
from data import binance_vision as bv
from data import kume_bellegi, onbellek_manifest as mf
from data import split
from onay_yardimcisi import gecici_depo, git

A_SEMBOL = "SOLUSDT"
AY = "2021-01"


def _anahtar(sembol, ay):
    return f"{bv.MUM_ONEKI}/{sembol}/{config.BAR_4H}/{sembol}-{config.BAR_4H}-{ay}.zip"


@pytest.fixture
def depo(monkeypatch, tmp_path):
    """Gercek git deposu: manifest, split.csv ve universe.csv commit edilmis; onbellek depo disinda."""
    kok = tmp_path / "onbellek"
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", kok)
    bv.donuk_bellek_temizle()
    kume_bellegi.temizle()
    sahte_4h(f"{AY}-01 00:00", 12).to_parquet(bv.onbellek_yolu("klines", A_SEMBOL, config.BAR_4H, f"{AY}.parquet"),
                                              index=False)
    liste = bv.donuk_liste_yolu()
    liste.parent.mkdir(parents=True, exist_ok=True)
    liste.write_text(json.dumps({"mum": {A_SEMBOL: {config.BAR_4H: [_anahtar(A_SEMBOL, AY)]}}, "funding": {}}),
                     encoding="utf-8")
    d = gecici_depo(tmp_path)
    (d / "data").mkdir()
    for ad, kaynak in (("SPLIT_CSV", config.SPLIT_CSV), ("UNIVERSE_CSV", config.UNIVERSE_CSV)):
        hedef = d / "data" / kaynak.name
        shutil.copyfile(kaynak, hedef)
        monkeypatch.setattr(config, ad, hedef)
    mf._test_manifest_ayarla(d / "data" / "onbellek_manifest.csv")
    mf.manifest_kur()
    git(d, "add", "data")
    git(d, "commit", "-q", "-m", "veri")
    yield d
    bv.donuk_bellek_temizle()
    kume_bellegi.temizle()


def _ac():
    with split.kesif_kosusu() as kayit:
        return kayit


def test_temiz_depoda_acilir_ve_kayit_alanlari_dolu(depo):
    with split.kesif_kosusu() as kayit:
        assert kayit.kapanis_utc is None
        head = git(depo, "rev-parse", "HEAD").strip()
        assert kayit.head_commit == head
        assert kayit.manifest_sha256 == hashlib.sha256(mf._etkin_yol().read_bytes()).hexdigest()
        assert kayit.agac_temiz is True
        assert kayit.origin_main_esit is False  # "veri" commit'i itilmedi
        assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", kayit.acilis_utc)
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", kayit.kapanis_utc)
    assert set(kayit.alanlar()) == {"head_commit", "manifest_sha256", "agac_temiz", "origin_main_esit",
                                    "origin_main_ref_zamani", "acilis_utc",
                                    "kapanis_utc"}
    with pytest.raises(AttributeError):
        kayit.head_commit = "0" * 40


def test_itilmis_depoda_origin_esitligi_kayda_gecer(depo):
    git(depo, "push", "-q", "origin", "main")
    git(depo, "fetch", "-q", "origin")
    assert _ac().origin_main_esit is True


def test_kirli_agac_kosuyu_durdurmaz_ama_kayda_gecer(depo):
    (depo / "baska.txt").write_text("x", encoding="utf-8")
    assert _ac().agac_temiz is False


@pytest.mark.parametrize("hedef", ["manifest", "split", "universe"])
def test_bagli_dosya_head_ile_ayni_degilse_kosu_acilmaz(depo, hedef):
    yol = {"manifest": mf._etkin_yol(), "split": config.SPLIT_CSV, "universe": config.UNIVERSE_CSV}[hedef]
    yol.write_bytes(yol.read_bytes() + b"\n")
    with pytest.raises(split.KesifBagiHatasi, match=yol.name):
        with split.kesif_kosusu():
            pytest.fail("kosu acildi")
    assert bv._KOSU_AGSIZ["sayac"] == 0


def test_izlenmeyen_manifestle_kosu_acilmaz(depo):
    git(depo, "rm", "-q", "--cached", "data/onbellek_manifest.csv")
    git(depo, "commit", "-q", "-m", "manifest izlenmiyor")
    with pytest.raises(split.KesifBagiHatasi, match="izlenmiyor"):
        _ac()


def test_kosu_icinde_manifest_degisirse_kapanis_hata_verir(depo):
    with pytest.raises(split.KesifBagiHatasi, match="manifest dosyasi kosu sirasinda degisti"):
        with split.kesif_kosusu():
            yol = mf._etkin_yol()
            yol.write_bytes(yol.read_bytes() + b"\n")
    assert bv._KOSU_AGSIZ["sayac"] == 0


@pytest.mark.parametrize("hedef", ["split", "universe"])
def test_kosu_icinde_split_ya_da_evren_degisirse_kapanis_hata_verir(depo, hedef):
    """RESULTS §14.43 (denetci D-K3): bolme ve evren tablosu da kapanista yeniden ozetlenir."""
    yol = {"split": config.SPLIT_CSV, "universe": config.UNIVERSE_CSV}[hedef]
    with pytest.raises(split.KesifBagiHatasi, match=yol.name):
        with split.kesif_kosusu():
            yol.write_bytes(yol.read_bytes() + b"\n")


@pytest.mark.parametrize("bayrak", ["--assume-unchanged", "--skip-worktree"])
def test_git_bayragi_ile_gizlenen_degisiklik_bayt_bagina_takilir(depo, bayrak):
    """RESULTS §14.43 (sizinti F-1): bag `git diff`e degil baytlara dayanir."""
    git(depo, "update-index", bayrak, "data/split.csv")
    config.SPLIT_CSV.write_bytes(config.SPLIT_CSV.read_bytes() + b"\n")
    with pytest.raises(split.KesifBagiHatasi, match="baytlari"):
        _ac()


def test_kayit_manifest_ozeti_head_blobunun_ozetidir(depo):
    blob = subprocess.run(["git", "cat-file", "blob", "HEAD:data/onbellek_manifest.csv"], cwd=depo, check=True,
                          capture_output=True).stdout
    assert _ac().manifest_sha256 == hashlib.sha256(blob).hexdigest()


def test_origin_ref_zamani_kayda_gecer(depo):
    """RESULTS §14.43 (D-K4): yerel `origin/main` referansinin son guncellenme ani (reflog, UTC). Fetch yapilmaz."""
    kayit = _ac()
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", kayit.origin_main_ref_zamani)
    assert "origin_main_ref_zamani" in kayit.alanlar()


def test_kosu_icinde_onbellek_degisirse_kapanis_hata_verir(depo):
    hedef = config.ONBELLEK_DIZINI / "klines" / A_SEMBOL / config.BAR_4H / f"{AY}.parquet"
    with pytest.raises(split.KesifBagiHatasi, match="kesif katmani artik manifestle dogrulanmiyor"):
        with split.kesif_kosusu():
            hedef.write_bytes(hedef.read_bytes() + b"x")


def test_blok_hatasi_turunu_korur_kapanis_uyusmazligi_not_olarak_yazilir(depo):
    with pytest.raises(ValueError, match="blok") as hata:
        with split.kesif_kosusu():
            yol = mf._etkin_yol()
            yol.write_bytes(yol.read_bytes() + b"\n")
            raise ValueError("blok")
    assert any("manifest dosyasi kosu sirasinda degisti" in n for n in getattr(hata.value, "__notes__", []))
    assert bv._DONUK_BELLEK == {} and mf._BELLEK == {}


def test_blok_hatasi_kapanis_temizse_oldugu_gibi_cikar(depo):
    with pytest.raises(ValueError, match="blok"):
        with split.kesif_kosusu():
            raise ValueError("blok")


def test_test_deposu_yokken_bag_denetlenmez_kayit_yine_verilir():
    """pytest icinde gercek git deposu yoksa commit bagi atlanir (`_sahte_git` yaklasimi); kayit nesnesi verilir."""
    kayit = _ac()
    assert isinstance(kayit, split.KesifKaydi) and kayit.kapanis_utc is not None
    assert kayit.manifest_sha256 is None  # pytest'te manifest ayari yok: denetim kapali


def test_commit_bagi_adlari_modul_disindan_degistirilemez():
    for ad in ("kesif_bagi_denetle", "_kesif_git_denetimi", "_kesif_kapanisi_denetle", "KesifKaydi"):
        with pytest.raises(split.OnayKorumasi):
            setattr(split, ad, lambda *a, **k: None)
