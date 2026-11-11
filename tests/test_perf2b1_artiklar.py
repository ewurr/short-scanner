"""Performans 2b-1, 0. asama: §14.46 artiklari (plan v3; RESULTS §14.48). Aga cikmaz.

- D-B2: `universe.evren_yukle`nin bool ayristirmasi ayri fonksiyonda (`bool_sutunlarini_ayristir`) ve SABIT'te.
- D-C2: `calistir.git_durumu` / `ortam_kaydi` agac temizligini tek kaynaktan (`split.agac_kirli_sayisi` ->
  `split._agac_kirlilikleri`) alir; dosya adi yazilmaz, yalnizca sayi.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

from data import split, universe
from onay_yardimcisi import DEPO_BETIGI, gecici_depo, git

import test_skaler_referans_dayanilan as dpd


# --- D-B2 ------------------------------------------------------------------------------------------------------

def _eski_govde(tablo: pd.DataFrame, hedef) -> pd.DataFrame:
    """`evren_yukle`nin 28f2c14'teki bool ayristirma govdesinin birebir kopyasi (karsilastirma tabani)."""
    tablo = tablo.copy()
    for sutun in universe._BOOL_SUTUNLARI:
        deger = tablo[sutun].astype(str).map({"True": True, "False": False})
        if deger.isna().any():
            raise ValueError(f"{hedef}: {sutun!r} sutununda True/False disi deger var.")
        tablo[sutun] = deger.astype(bool)
    return tablo


def _tablo(haric, funding_yok) -> pd.DataFrame:
    return pd.DataFrame({"sembol": [f"S{i}USDT" for i in range(len(haric))], "haric": haric,
                         "donem_funding_yok": funding_yok})


@pytest.mark.parametrize("haric,funding_yok", [
    (["True", "False"], ["False", "False"]),
    (["False"], ["True"]),
    (["True", "True", "False"], ["True", "False", "True"]),
])
def test_D_B2_true_false_metni_eski_govdeyle_ayni(haric, funding_yok):
    girdi = _tablo(haric, funding_yok)
    yeni = universe.bool_sutunlarini_ayristir(girdi, "evren.csv")
    pd.testing.assert_frame_equal(yeni, _eski_govde(girdi, "evren.csv"))
    assert yeni["haric"].dtype == bool and yeni["donem_funding_yok"].dtype == bool
    assert list(yeni["haric"]) == [h == "True" for h in haric]
    assert list(girdi["haric"]) == haric, "girdi degistirilmemeli"


@pytest.mark.parametrize("sutun", ["haric", "donem_funding_yok"])
@pytest.mark.parametrize("deger", ["", "true", "false", "1", "0", "Evet", " True", "True ", "nan", "None"])
def test_D_B2_bos_ve_gecersiz_metin_eski_govdeyle_ayni_hatayi_verir(sutun, deger):
    haric, funding_yok = ["False", "False"], ["False", "False"]
    (haric if sutun == "haric" else funding_yok)[1] = deger
    girdi = _tablo(haric, funding_yok)
    with pytest.raises(ValueError) as eski:
        _eski_govde(girdi, "evren.csv")
    with pytest.raises(ValueError) as yeni:
        universe.bool_sutunlarini_ayristir(girdi, "evren.csv")
    assert str(yeni.value) == str(eski.value) == f"evren.csv: {sutun!r} sutununda True/False disi deger var."


def test_D_B2_evren_yukle_gecersiz_metinde_ayni_mesajla_reddeder(tmp_path):
    """Yukleyici yolu: CSV'de bos `haric` hucresi (keep_default_na=False ile bos metin) reddedilir."""
    gercek = pd.read_csv(universe.config.UNIVERSE_CSV, dtype=str, keep_default_na=False, encoding="utf-8").head(3)
    gercek.loc[1, "haric"] = ""
    yol = tmp_path / "evren.csv"
    gercek.to_csv(yol, index=False, encoding="utf-8")
    with pytest.raises(ValueError, match=r"'haric' sutununda True/False disi deger var"):
        universe.evren_yukle(yol)


def test_D_B2_evren_yukle_gercek_tabloda_ayni_sonucu_verir():
    """Commit'li evren tablosu: yeni yol eski govdeyle ayni cerceveyi verir."""
    hedef = universe.config.UNIVERSE_CSV
    ham = pd.read_csv(hedef, dtype={s: str for s in (*universe._METIN_SUTUNLARI, *universe._ZAMAN_SUTUNLARI)},
                      keep_default_na=False, encoding="utf-8")
    pd.testing.assert_frame_equal(universe.evren_yukle(), universe._normallestir(_eski_govde(ham, hedef)))


def test_D_B2_ayristirma_SABIT_te_yukleyici_GUVENLIK_te():
    ad = "data.universe.bool_sutunlarini_ayristir"
    assert ad in dpd.SABIT and ad not in dpd.GUVENLIK
    assert ad in dpd._kapanis(), "evren_yukle ayristirmayi cagirmali (grafikte gorunmeli)"
    assert dpd.GUVENLIK["data.universe.evren_yukle"][1] == "yukleyici"
    assert dpd._sha(ad) == dpd.SABIT[ad]


# --- D-C2 ------------------------------------------------------------------------------------------------------

_KOK = Path(__file__).resolve().parents[1]


def _calistir():
    spec = importlib.util.spec_from_file_location("_perf2b1_calistir", _KOK / "analysis/00_veri_denetimi/calistir.py")
    modul = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modul
    spec.loader.exec_module(modul)
    return modul


calistir = _calistir()
_ZAMAN = pd.Timestamp("2026-01-01", tz="UTC")


def _ortam(git) -> pd.DataFrame:
    return calistir.ortam_kaydi(git, _ZAMAN, _ZAMAN).set_index("bilesen")


def test_D_C2_temiz_gecici_depoda_sifir(tmp_path):
    gecici_depo(tmp_path)
    git_durumu = calistir.git_durumu()
    assert git_durumu["bilinmiyor"] is False and git_durumu["kirli_sayisi"] == 0
    assert set(git_durumu) == {"commit", "kirli_sayisi", "bilinmiyor"}, "dosya listesi tasinmaz"
    tablo = _ortam(git_durumu)
    assert tablo.at["calisma_agaci", "surum"] == "temiz"
    assert tablo.at["calisma_agaci_kirli_sayisi", "surum"] == "0"
    assert "calisma_agaci_degisiklikleri" not in tablo.index


def test_D_C2_kirli_depoda_yalnizca_sayi_dosya_adi_yok(tmp_path):
    depo = gecici_depo(tmp_path)
    (depo / "gizli_ad.py").write_text("x = 1\n", encoding="utf-8")            # izlenmeyen
    (depo / DEPO_BETIGI).write_text("# degisti\n", encoding="utf-8")         # izlenen degisiklik
    git_durumu = calistir.git_durumu()
    assert git_durumu["kirli_sayisi"] == len(split._agac_kirlilikleri()) == 2
    tablo = _ortam(git_durumu)
    assert tablo.at["calisma_agaci", "surum"] == "kirli"
    assert tablo.at["calisma_agaci_kirli_sayisi", "surum"] == "2"
    metin = tablo.to_csv()
    assert "gizli_ad" not in metin and Path(DEPO_BETIGI).name not in metin, "kirli dosya adi ciktiya yazilmaz"


def test_D_C2_eski_hesabin_gormedigi_isaret_artik_kirli(tmp_path):
    """Eski `git status --porcelain` hesabi `--skip-worktree` isaretli dosyayi gormezdi; tek kaynak gorur. Ortam
    kaydi artik kesif kaydi ve onay kosusuyla ayni hukmu verir."""
    depo = gecici_depo(tmp_path)
    git(depo, "update-index", "--skip-worktree", DEPO_BETIGI)
    (depo / DEPO_BETIGI).write_text("# gizlice degisti\n", encoding="utf-8")
    assert git(depo, "status", "--porcelain").strip() == "", "kurulum: eski olcut temiz gorur"
    assert calistir.git_durumu()["kirli_sayisi"] == 1
    assert split._kesif_kaydi_kur(None).agac_kirli_sayisi == 1


def test_D_C2_tek_kaynak_okunamazsa_bilinmiyor(tmp_path):
    """Git deposu olmayan bir dizin: tek kaynak None verir, ortam kaydi 'bilinmiyor' der (temiz uydurmaz)."""
    depo = gecici_depo(tmp_path)
    (depo / ".git").rename(depo / "git_degil")
    assert split.agac_kirli_sayisi() is None
    git_durumu = calistir.git_durumu()
    assert git_durumu["bilinmiyor"] is True and git_durumu["kirli_sayisi"] is None
    assert _ortam(git_durumu).at["calisma_agaci", "surum"] == "bilinmiyor (git yok)"


def test_D_C2_calistir_kendi_agac_hesabini_yapmaz():
    metin = (_KOK / "analysis/00_veri_denetimi/calistir.py").read_text(encoding="utf-8")
    # Komut satiri olarak (tirnakli arguman) yok; aciklamadaki tarihsel anma serbest.
    assert '"--porcelain"' not in metin and '"ls-files"' not in metin and '"status"' not in metin
    assert "agac_kirli_sayisi" in metin
