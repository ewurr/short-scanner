"""Performans 2b-1, 0. asama: §14.46 artiklari (plan v3; RESULTS §14.48). Aga cikmaz.

- D-B2: `universe.evren_yukle`nin bool ayristirmasi ayri fonksiyonda (`bool_sutunlarini_ayristir`) ve SABIT'te.
"""

from __future__ import annotations

import pandas as pd
import pytest

from data import universe

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
