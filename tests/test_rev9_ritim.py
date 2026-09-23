"""Rev.9 hazirligi, altinci tur: ritim kirilimi (rev9_ritim.pozisyon_ritmi ve
rev9_ritim.kayit_satirlari). Aga cikmaz.

Ritim etiketlerinin (capa araligi, penceredeki son kaydin araligi, tek ritim, kayit
sayisi) dogru dizi uzerinde hesaplandigini ve etiketin tamlik hukmunu DEGISTIRMEDIGINI
sabitler; kayit dagiliminin yalnizca donem ici kayitlari saydigini ve kume/yil
etiketlerini dogru verdigini sabitler.
"""

from __future__ import annotations

import importlib.util
import sys

import numpy as np
import pandas as pd
import pytest

import config

DIZIN = config.ANALIZ_DIZINI / "00_veri_denetimi"
sys.path.insert(0, str(DIZIN))


def _yukle(ad, dosya):
    spec = importlib.util.spec_from_file_location(ad, DIZIN / dosya)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


rt = _yukle("_rev9_ritim", "rev9_ritim.py")
r9 = _yukle("_rev9_hazirlik_rt", "rev9_hazirlik.py")

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
BAS = T("2025-01-01 00:00")


class _Donem:
    def __init__(self, baslangic, bitis):
        self.baslangic, self.bitis = T(baslangic), T(bitis)


def _seri(kayitlar):
    return pd.DataFrame({"odeme_zamani": pd.DatetimeIndex([T(z) for z, _ in kayitlar]),
                         "aralik_saat": [float(a) for _, a in kayitlar]})


def _r(seri, giris, son, bas=BAS):
    return rt.pozisyon_ritmi(seri, [T(giris)], [T(son)], [bas]).iloc[0]


# --- Ritim etiketleri ----------------------------------------------------------------


def test_tek_ritim_sekiz_saat():
    seri = _seri([("2025-01-01 00:00", 8), ("2025-01-01 08:00", 8), ("2025-01-01 16:00", 8)])
    s = _r(seri, "2025-01-01 04:00", "2025-01-01 20:00")
    assert s["capa_aralik"] == 8 and s["son_aralik"] == 8 and s["tek_ritim"] and s["kayit_sayisi"] == 3


def test_capa_giristen_onceki_son_kayit():
    seri = _seri([("2025-01-01 00:00", 4), ("2025-01-01 04:00", 8), ("2025-01-01 12:00", 8)])
    s = _r(seri, "2025-01-01 04:00", "2025-01-01 12:00")  # capa 04:00 (giris ile ayni an)
    assert s["capa_aralik"] == 8 and s["kayit_sayisi"] == 2 and s["tek_ritim"]


def test_aralik_degisimi_tek_ritmi_bozar():
    seri = _seri([("2025-01-01 00:00", 8), ("2025-01-01 08:00", 4), ("2025-01-01 12:00", 4)])
    s = _r(seri, "2025-01-01 00:00", "2025-01-01 12:00")
    assert s["capa_aralik"] == 8 and s["son_aralik"] == 4 and not s["tek_ritim"] and s["kayit_sayisi"] == 3


def test_pencere_sonundan_sonraki_kayit_diziye_girmez():
    seri = _seri([("2025-01-01 00:00", 4), ("2025-01-01 04:00", 4), ("2025-01-01 08:00", 1)])
    s = _r(seri, "2025-01-01 00:00", "2025-01-01 04:00")
    assert s["son_aralik"] == 4 and s["tek_ritim"] and s["kayit_sayisi"] == 2


def test_pencere_sonuyla_ayni_andaki_kayit_diziye_girer():
    seri = _seri([("2025-01-01 00:00", 4), ("2025-01-01 04:00", 8)])
    s = _r(seri, "2025-01-01 00:00", "2025-01-01 04:00")
    assert s["son_aralik"] == 8 and not s["tek_ritim"]


def test_capa_yoksa_etiket_bos():
    seri = _seri([("2025-01-01 08:00", 4)])
    s = _r(seri, "2025-01-01 04:00", "2025-01-01 12:00")
    assert np.isnan(s["capa_aralik"]) and np.isnan(s["son_aralik"])
    assert not s["tek_ritim"] and s["kayit_sayisi"] == 0


def test_capa_donem_basindan_onceyse_etiket_bos():
    seri = _seri([("2024-12-31 20:00", 4), ("2025-01-01 04:00", 4)])
    s = _r(seri, "2025-01-01 00:00", "2025-01-01 04:00", bas=BAS)
    assert np.isnan(s["capa_aralik"]) and s["kayit_sayisi"] == 0


def test_bos_seri_ve_bos_pozisyon():
    bos = pd.DataFrame({"odeme_zamani": pd.DatetimeIndex([], tz="UTC"), "aralik_saat": np.empty(0)})
    s = rt.pozisyon_ritmi(bos, [T("2025-01-01 04:00")], [T("2025-01-01 12:00")], [BAS]).iloc[0]
    assert np.isnan(s["capa_aralik"]) and s["kayit_sayisi"] == 0
    assert len(rt.pozisyon_ritmi(_seri([("2025-01-01 00:00", 8)]), [], [], [])) == 0


def test_uzunluk_uyusmazligi_hata():
    with pytest.raises(ValueError):
        rt.pozisyon_ritmi(_seri([("2025-01-01 00:00", 8)]), [T("2025-01-01 04:00")], [], [BAS])


def test_ritim_etiketi_tamligi_degistirmez():
    """Etiket yalnizca kirilim icindir: ayni seride tamlik hukmu besinci turla ayni."""
    seri = _seri([("2025-01-01 00:00", 8), ("2025-01-01 08:00", 4), ("2025-01-01 12:00", 4)])
    girisler, sonlar = [T("2025-01-01 00:00")], [T("2025-01-01 12:00")]
    cd = r9.capa_duzeltme_tamlik_ayrintisi(seri, girisler, sonlar, [BAS]).iloc[0]
    rr = rt.pozisyon_ritmi(seri, girisler, sonlar, [BAS]).iloc[0]
    assert set(rr.index) == {"capa_aralik", "son_aralik", "tek_ritim", "kayit_sayisi"}
    assert bool(cd["tam"])  # hukum besinci turun kuralindan gelir, etiketten degil


def test_vektorel_ve_tek_tek_ayni():
    seri = _seri([("2025-01-01 00:00", 8), ("2025-01-01 08:00", 8), ("2025-01-01 12:00", 4),
                  ("2025-01-01 16:00", 4)])
    girisler = [T("2025-01-01 00:00"), T("2025-01-01 08:00"), T("2025-01-01 12:00")]
    sonlar = [T("2025-01-01 12:00"), T("2025-01-01 16:00"), T("2025-01-01 16:00")]
    toplu = rt.pozisyon_ritmi(seri, girisler, sonlar, [BAS] * 3)
    for i, (g, s) in enumerate(zip(girisler, sonlar)):
        tek = rt.pozisyon_ritmi(seri, [g], [s], [BAS]).iloc[0]
        for sutun in toplu.columns:
            a, b = toplu.at[i, sutun], tek[sutun]
            assert (np.isnan(a) and np.isnan(b)) if isinstance(a, float) and np.isnan(a) else a == b


def test_oran_sutunu_okunmuyor():
    seri = _seri([("2025-01-01 00:00", 8), ("2025-01-01 08:00", 8)])
    kirli = seri.copy()
    kirli["funding_orani"] = [0.5, -0.5]
    a = rt.pozisyon_ritmi(seri, [T("2025-01-01 00:00")], [T("2025-01-01 08:00")], [BAS])
    b = rt.pozisyon_ritmi(kirli, [T("2025-01-01 00:00")], [T("2025-01-01 08:00")], [BAS])
    pd.testing.assert_frame_equal(a, b)


# --- Kayit dagilimi ------------------------------------------------------------------


def _kumeler():
    return {"KESIF": (("A",), T("2020-01-01"), T("2025-08-31 23:59:59")),
            "C1": (("B",), T("2020-01-01"), T("2025-08-31 23:59:59")),
            "C2": (("A", "B"), T("2025-09-01"), T("2026-08-31 23:59:59"))}


def test_kayit_dagilimi_kume_ve_yil():
    seri = _seri([("2025-08-31 16:00", 8), ("2025-09-01 00:00", 4), ("2025-09-01 04:00", 4)])
    donemler = [_Donem("2025-01-01 00:00", "2026-01-01 00:00")]
    satirlar = rt.kayit_satirlari("XUSDT", "A", donemler, seri, _kumeler())
    tablo = pd.DataFrame(satirlar).set_index(["kume", "yil", "aralik_saat"])["kayit"]
    assert tablo[("KESIF", 2025, 8.0)] == 1
    assert tablo[("C2", 2025, 4.0)] == 2
    assert tablo.sum() == 3


def test_kayit_dagilimi_b_grubu_c1():
    seri = _seri([("2025-08-31 16:00", 8)])
    donemler = [_Donem("2025-01-01 00:00", "2026-01-01 00:00")]
    satirlar = rt.kayit_satirlari("XUSDT", "B", donemler, seri, _kumeler())
    assert satirlar[0]["kume"] == "C1" and satirlar[0]["kayit"] == 1


def test_donem_disi_kayit_sayilmaz():
    seri = _seri([("2024-12-31 16:00", 8), ("2025-01-01 00:00", 8), ("2026-01-05 00:00", 8)])
    donemler = [_Donem("2025-01-01 00:00", "2026-01-01 00:00")]
    satirlar = rt.kayit_satirlari("XUSDT", "A", donemler, seri, _kumeler())
    assert sum(s["kayit"] for s in satirlar) == 1


def test_kume_araligi_disindaki_kayit_yok_satirina_duser():
    seri = _seri([("2026-09-05 00:00", 4)])
    donemler = [_Donem("2026-01-01 00:00", "2026-10-01 00:00")]
    satirlar = rt.kayit_satirlari("XUSDT", "A", donemler, seri, _kumeler())
    assert satirlar[0]["kume"] == "YOK"


def test_bos_seride_kayit_satiri_yok():
    bos = pd.DataFrame({"odeme_zamani": pd.DatetimeIndex([], tz="UTC"), "aralik_saat": np.empty(0)})
    assert rt.kayit_satirlari("XUSDT", "A", [_Donem("2025-01-01 00:00", "2026-01-01 00:00")], bos,
                              _kumeler()) == []
