"""KESIF karar noktasi acik bir kesif kosusu ister (RESULTS §14.42, denetci D-C1).

Kural pytest icinde yalnizca testin kendi manifestini kurdugu testte uygulanir (`onbellek_manifest.denetim_etkin`); bu
dosyanin `manifestli` fiksturu bunu yapar. Sentetik veri, gecici onbellek; aga cikilmaz.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pandas as pd
import pytest

import config
from conftest import sahte_4h
from data import binance_vision as bv
from data import kume_bellegi, onbellek_manifest as mf
from data import pozisyon, sinyal, split
from kapi_yardimcisi import veri

A_SEMBOL = "SOLUSDT"
T = pd.Timestamp("2021-03-01 00:00", tz="UTC")


@pytest.fixture
def manifestli(monkeypatch, tmp_path):
    kok = tmp_path / "onbellek"
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", kok)
    mf._test_manifest_ayarla(tmp_path / "onbellek_manifest.csv")
    bv.donuk_bellek_temizle()
    kume_bellegi.temizle()
    sahte_4h("2021-01-01 00:00", 12).to_parquet(bv.onbellek_yolu("klines", A_SEMBOL, config.BAR_4H, "2021-01.parquet"),
                                                index=False)
    yol = bv.donuk_liste_yolu()
    yol.parent.mkdir(parents=True, exist_ok=True)
    anahtar = f"{bv.MUM_ONEKI}/{A_SEMBOL}/{config.BAR_4H}/{A_SEMBOL}-{config.BAR_4H}-2021-01.zip"
    yol.write_text(json.dumps({"mum": {A_SEMBOL: {config.BAR_4H: [anahtar]}}, "funding": {}}), encoding="utf-8")
    mf.manifest_kur()
    yield kok
    bv.donuk_bellek_temizle()
    kume_bellegi.temizle()


def _sentetik():
    zaman = pd.date_range("2021-01-01", periods=275, freq="8h", tz="UTC")
    fr = pd.DataFrame({"odeme_zamani": zaman, "aralik_saat": 8.0, "oran": 0.0001, "oran_8h": 0.0001})
    return veri(sahte_4h("2021-01-01", 540, hacim=1e10), fr, pd.Timestamp("2021-01-01 00:00", tz="UTC"),
                pd.Timestamp("2021-04-30 20:00", tz="UTC"))


def _karar(kimlik, kume="KESIF", hipotez="H2"):
    bar = config.HIPOTEZ_IZGARASI[hipotez]
    ufuk = config.BIRINCIL_UFUK[bar]
    hacim = config.ASGARI_HACIM_4H if bar == config.BAR_4H else config.ASGARI_HACIM_1D
    return pozisyon.olay_karari(T, ufuk, bar, hipotez=hipotez, yapilandirma=sinyal.izgara(hipotez)[0], rol="olay",
                                capa=None, birincil_ufuk=ufuk, kume=kume, asgari_hacim=hacim,
                                asgari_listeleme_yasi_gun=config.ASGARI_LISTELEME_YASI_GUN, **kimlik)


def _kosul(kimlik, kume="KESIF", hipotez="H2"):
    return pozisyon.sinyal_kosulu(T, hipotez=hipotez, yapilandirma=sinyal.izgara(hipotez)[0], capa=None, kume=kume,
                                  **kimlik)


def _sonuc(fn):
    """Karar noktasinin sonucu; kesif baglami hatasi disindaki her sey (olay olusmaz dahil) 'gecti' sayilir."""
    try:
        fn()
    except split.KesifBaglamiYok:
        return "baglam yok"
    except Exception:  # noqa: BLE001  (olay olusmaz, veri hatasi: baglam denetimi gecilmis)
        return "gecti"
    return "gecti"


@pytest.mark.parametrize("cagri", [_karar, _kosul])
def test_kesif_karar_noktasi_kosu_disinda_reddedilir(manifestli, cagri):
    kimlik = _sentetik()
    with pytest.raises(split.KesifBaglamiYok):
        cagri(kimlik)


@pytest.mark.parametrize("cagri", [_karar, _kosul])
def test_kesif_karar_noktasi_kosu_icinde_calisir(manifestli, cagri):
    kimlik = _sentetik()
    with split.kesif_kosusu():
        assert split.kesif_kosusu_acik()
        assert _sonuc(lambda: cagri(kimlik)) == "gecti"
    assert not split.kesif_kosusu_acik()
    assert os.environ.get(split._KESIF_ORTAM_ADI) is None


@pytest.mark.parametrize("cagri", [_karar, _kosul])
def test_pytest_istisnasi_manifestsiz_testte_kural_uygulanmaz(cagri):
    """Bugunku test istisnasi (manifest denetimiyle ayni; RESULTS §14.41, M-11): manifest ayari olmayan testte kural
    uygulanmaz."""
    assert not mf.denetim_etkin()
    assert _sonuc(lambda: cagri(_sentetik())) == "gecti"


def test_onay_kumesinde_kural_onay_baglamidir(manifestli):
    """C1/C2 icin kural degismedi: acik onay kosusu ister (`OnayUyusmazligi`), kesif kosusu yetmez."""
    kimlik = _sentetik()
    with split.kesif_kosusu():
        with pytest.raises(split.OnayUyusmazligi):
            _karar(kimlik, kume="C2")


def test_yukleyicilere_kesif_baglami_kurali_uygulanmaz(manifestli):
    from data import klines

    assert len(klines.mumlari_yukle(A_SEMBOL, config.BAR_4H, "KESIF")) == 12


def test_kesif_kosusu_hatayla_kapaninca_baglam_kalkar(manifestli):
    with pytest.raises(ValueError):
        with split.kesif_kosusu():
            raise ValueError("blok")
    assert not split.kesif_kosusu_acik() and split._KESIF_DURUMU["sayac"] == 0


_ALT = ("import sys; sys.path.insert(0, sys.argv[1])\n"
        "from data import split\n"
        "print(split.kesif_kosusu_acik())\n")


def _alt_surec(ortam=None) -> str:
    return subprocess.run([sys.executable, "-B", "-c", _ALT, str(config.KOK)], capture_output=True, text=True,
                          check=True, env=ortam).stdout.strip()


def test_alt_surec_kesif_baglamini_devralir(manifestli):
    with split.kesif_kosusu():
        assert _alt_surec() == "True"
    assert _alt_surec() == "False"


def test_elle_ayarlanmis_degisken_baglam_acmaz():
    ortam = {**os.environ, split._KESIF_ORTAM_ADI: str(os.getpid() + 999_999)}
    assert _alt_surec(ortam) == "False"


@pytest.mark.parametrize("ad", ["_KESIF_DURUMU", "kesif_kosusu_acik", "kesif_baglami_dogrula", "_kesif_baglami"])
def test_kesif_baglami_adlari_modul_disindan_degistirilemez(ad):
    with pytest.raises(split.OnayKorumasi):
        setattr(split, ad, lambda *a, **k: True)


# --- RESULTS §14.43 (D-C1): mae ve pozisyon_fundingi -----------------------------------------------------------------


def _onayli(kimlik):
    return pozisyon._test_onayi(hipotez="H2", yapilandirma=sinyal.izgara("H2")[0], t=T, rol="olay", **kimlik)


def _mae(p):
    return pozisyon.mae(p)


def _fund(p):
    from data import funding

    return funding.pozisyon_fundingi(p)


@pytest.mark.parametrize("cagri", [_mae, _fund])
def test_mae_ve_pozisyon_fundingi_kosu_disinda_reddedilir(manifestli, cagri):
    p = _onayli(_sentetik())
    with pytest.raises(split.KesifBaglamiYok):
        cagri(p)


@pytest.mark.parametrize("cagri", [_mae, _fund])
def test_mae_ve_pozisyon_fundingi_kosu_icinde_baglam_denetiminden_gecer(manifestli, cagri):
    p = _onayli(_sentetik())
    with split.kesif_kosusu():
        assert _sonuc(lambda: cagri(p)) == "gecti"


# --- RESULTS §14.43 (D-C1): yasak adlar --------------------------------------------------------------------------------


@pytest.mark.parametrize("metin", [
    "from data import split\nsplit._KESIF_DURUMU['sayac'] += 1\n",
    "split._kesif_baglami().__enter__()\n",
    "os.environ['SHORT_LAB_KESIF_KOSUSU'] = str(os.getpid())\n",
    "os.environ[split._KESIF_ORTAM_ADI] = '1'\n",
    "split._kesif_baglamini_devral()\n",
])
def test_kesif_baglami_yasak_adlari_taramaya_takilir(tmp_path, metin):
    from tarama_yardimcisi import ONAY_ATLATMA_DESENI, ihlaller

    (tmp_path / "study").mkdir()
    (tmp_path / "study" / "k.py").write_text(metin, encoding="utf-8")
    assert ihlaller(ONAY_ATLATMA_DESENI, kok=tmp_path) == ["study/k.py"]


def test_kesif_kosusu_ve_dogrulama_adlari_taramada_izinli(tmp_path):
    from tarama_yardimcisi import ONAY_ATLATMA_DESENI, ihlaller

    (tmp_path / "study").mkdir()
    (tmp_path / "study" / "k.py").write_text(
        "with split.kesif_kosusu() as kayit:\n    assert split.kesif_kosusu_acik()\n", encoding="utf-8")
    assert ihlaller(ONAY_ATLATMA_DESENI, kok=tmp_path) == []
