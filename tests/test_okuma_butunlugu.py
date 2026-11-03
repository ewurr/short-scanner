"""Okuma butunlugu, yazma yasagi ve yol normallestirmesi (RESULTS §14.42; denetci D-C4, sizinti M-1, M-3, M-15, M-16).

Gecici onbellek ve gecici manifest; aga cikilmaz, gercek `cache/` dosyalarina dokunulmaz.
"""

from __future__ import annotations

import json
import sys

import pandas as pd
import pytest

import config
from conftest import sahte_4h
from data import binance_vision as bv
from data import kume_bellegi, onbellek_manifest as mf
from data import split
from onay_yardimcisi import gecici_kayit, kosu

A_SEMBOL = "SOLUSDT"
AY = "2021-01"


def _b_sembolu() -> str:
    tablo = split.split_oku()
    return str(tablo.loc[tablo["grup"] == "B", "sembol"].iloc[0])


@pytest.fixture
def onbellek(monkeypatch, tmp_path):
    kok = tmp_path / "onbellek"
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", kok)
    mf._test_manifest_ayarla(tmp_path / "onbellek_manifest.csv")
    bv.donuk_bellek_temizle()
    kume_bellegi.temizle()
    for sembol in (A_SEMBOL, _b_sembolu()):
        sahte_4h(f"{AY}-01 00:00", 12).to_parquet(bv.onbellek_yolu("klines", sembol, config.BAR_4H, f"{AY}.parquet"),
                                                  index=False)
    yol = bv.donuk_liste_yolu()
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps({"mum": {}, "funding": {}}), encoding="utf-8")
    mf.manifest_kur()
    yield kok
    bv.donuk_bellek_temizle()
    kume_bellegi.temizle()


def _kesif(kok):
    return kok / "klines" / A_SEMBOL / config.BAR_4H / f"{AY}.parquet"


def _b(kok):
    return kok / "klines" / _b_sembolu() / config.BAR_4H / f"{AY}.parquet"


def _ayni_boyda_degistir(yol):
    govde = bytearray(yol.read_bytes())
    govde[len(govde) // 2] ^= 0xFF
    yol.write_bytes(bytes(govde))


# --- Ilk okumada SHA256, sonra bellek ------------------------------------------------------------------------------


def test_ilk_okumadan_sonra_diskteki_ayni_boy_degisiklik_sonuca_girmez(onbellek):
    with bv.kosu_agsiz():
        once = bv.onbellekten_oku(_kesif(onbellek))
        _ayni_boyda_degistir(_kesif(onbellek))
        sonra = bv.onbellekten_oku(_kesif(onbellek))
    pd.testing.assert_frame_equal(once, sonra)


def test_ilk_okumadan_sonra_boyu_degisen_dosya_reddedilir(onbellek):
    with bv.kosu_agsiz():
        bv.onbellekten_oku(_kesif(onbellek))
        _kesif(onbellek).write_bytes(_kesif(onbellek).read_bytes() + b"x")
        with pytest.raises(mf.ManifestUyusmazligi):
            bv.onbellekten_oku(_kesif(onbellek))


def test_ilk_okumada_ayni_boyda_bozuk_dosya_parquet_olarak_acilmaz(onbellek, monkeypatch):
    _ayni_boyda_degistir(_kesif(onbellek))
    monkeypatch.setattr(pd, "read_parquet", lambda *_a, **_k: pytest.fail("parquet acildi"))
    with bv.kosu_agsiz(), pytest.raises(mf.ManifestUyusmazligi, match="SHA256"):
        bv.onbellekten_oku(_kesif(onbellek))


def test_bellekteki_kopya_cagiranin_degisikliginden_etkilenmez(onbellek):
    with bv.kosu_agsiz():
        ilk = bv.onbellekten_oku(_kesif(onbellek))
        ilk.loc[:, "close"] = -1.0
        assert (bv.onbellekten_oku(_kesif(onbellek))["close"] > 0).all()


def test_kosu_acilisi_ve_kapanisi_dogrulanmis_bellegi_temizler(onbellek):
    with bv.kosu_agsiz():
        bv.onbellekten_oku(_kesif(onbellek))
    assert bv._DOGRULANMIS
    with split.kesif_kosusu():
        assert not bv._DOGRULANMIS
        bv.onbellekten_oku(_kesif(onbellek))
        assert bv._DOGRULANMIS
    assert not bv._DOGRULANMIS


def test_bellekteki_onay_kopyasi_izinsiz_okunamaz(onbellek, tmp_path):
    """Erisim denetimi bellege bakmadan once her okunusta calisir (CLAUDE.md §5)."""
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    with kosu("H2", "C1"):
        with bv.onay_verisi_izni("test"):
            assert bv.onbellekten_oku(_b(onbellek)) is not None
        assert bv._DOGRULANMIS
        with pytest.raises(bv.OnayVerisiKorumasi):
            bv.onbellekten_oku(_b(onbellek))


def test_onay_dosyasi_ilk_okumada_bozuksa_ad_yazilmaz(onbellek, tmp_path):
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    with kosu("H2", "C1"):
        _ayni_boyda_degistir(_b(onbellek))
        with bv.onay_verisi_izni("test"), pytest.raises(mf.ManifestUyusmazligi) as hata:
            bv.onbellekten_oku(_b(onbellek))
    assert _b_sembolu() not in str(hata.value) and AY not in str(hata.value)


def test_denetim_kapaliyken_dogrudan_okunur_bellege_alinmaz(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", tmp_path)
    bv.donuk_bellek_temizle()
    yol = tmp_path / "klines" / A_SEMBOL / config.BAR_4H / f"{AY}.parquet"
    yol.parent.mkdir(parents=True)
    sahte_4h(f"{AY}-01 00:00", 6).to_parquet(yol, index=False)
    with bv.kosu_agsiz():
        assert len(bv.onbellekten_oku(yol)) == 6
    assert not bv._DOGRULANMIS


# --- Yazma yasagi ----------------------------------------------------------------------------------------------------


def test_ag_yasakli_kosuda_onbellege_yazilamaz(onbellek):
    hedef = onbellek / "klines" / A_SEMBOL / config.BAR_4H / "2021-02.parquet"
    with bv.kosu_agsiz(), pytest.raises(bv.KosuYazmaYasagi):
        bv.onbellege_yaz(sahte_4h("2021-02-01 00:00", 6), hedef)
    assert not hedef.exists()
    with split.kesif_kosusu(), pytest.raises(bv.KosuYazmaYasagi):
        bv.onbellege_yaz(sahte_4h("2021-02-01 00:00", 6), hedef)
    bv.onbellege_yaz(sahte_4h("2021-02-01 00:00", 6), hedef)  # kosu disinda serbest
    assert hedef.exists()


# --- Yol normallestirmesi --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("bicim", ["kok", "tur_dizini", "sembol_dizini", "bar_dizini", "kok_disi", "kok_disi_nokta_nokta",
                                   "aygit_soru", "aygit_nokta"])
def test_yol_normallestirmesi_reddeder(onbellek, tmp_path, monkeypatch, bicim):
    disarida = tmp_path / "disarida.parquet"
    sahte_4h(f"{AY}-01 00:00", 6).to_parquet(disarida, index=False)
    yollar = {
        "kok": onbellek,
        "tur_dizini": onbellek / "klines",
        "sembol_dizini": onbellek / "klines" / A_SEMBOL,
        "bar_dizini": onbellek / "klines" / A_SEMBOL / config.BAR_4H,
        "kok_disi": disarida,
        "kok_disi_nokta_nokta": onbellek / "klines" / ".." / ".." / "disarida.parquet",
        "aygit_soru": "\\\\?\\" + str(_kesif(onbellek)),
        "aygit_nokta": "\\\\.\\" + str(_kesif(onbellek)),
    }
    monkeypatch.setattr(pd, "read_parquet", lambda *_a, **_k: pytest.fail("parquet acildi"))
    with bv.onay_verisi_izni("test"), pytest.raises(bv.OnbellekYoluHatasi):
        bv.onbellekten_oku(yollar[bicim])


def test_normallestirilen_yol_tanimli_turde_bicim_disiysa_onay_sayilir(onbellek):
    tuhaf = onbellek / "klines" / f"{A_SEMBOL}.parquet"  # <tur>/<ad>.parquet: sembol/ay ayristirilamaz
    sahte_4h(f"{AY}-01 00:00", 6).to_parquet(tuhaf, index=False)
    with pytest.raises(bv.OnayVerisiKorumasi):
        bv.onbellekten_oku(tuhaf)


def test_bos_ay_onay_verisi_sayilir():
    """`pd.Period("")` NaT verir; bos ay eskiden A sembolunde onay disi sayiliyordu (RESULTS §14.42)."""
    assert bv.onay_verisi_mi(A_SEMBOL, "") is True
    assert bv.onay_verisi_mi(A_SEMBOL, "2021-13") is True
    assert bv.onay_verisi_mi(A_SEMBOL, AY) is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows yol bicimleri")
def test_buyuk_kucuk_harf_ve_goreli_yol_kokun_icinde_kalir(onbellek):
    yol = onbellek.joinpath(*[p.swapcase() for p in _kesif(onbellek).relative_to(onbellek).parts])
    assert len(bv.onbellekten_oku(yol)) == 12
