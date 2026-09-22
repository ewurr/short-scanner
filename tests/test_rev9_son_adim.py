"""Rev.9 hazirligi, ucuncu tur: adim tanimi (rev9_hazirlik.son_adim_tamlik_ayrintisi). Aga cikmaz.

Beklenen anlarin capadan baslayip kayit dizisi boyunca uretildigini (bir beklenen anda kayit
varsa adim o kaydin araligi, yoksa son bilinen aralikla surdugunu), giris aninda ya da
oncesinde dusen kayitsiz beklenen anlarin tamligi bozmadigini, aralik gecislerinde yanlis
eksik uretilmedigini, zincirin kayit uzerinden atlayabildigini ve tolerans kuralini sabitler.
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
_spec = importlib.util.spec_from_file_location("_rev9_hazirlik_sa", DIZIN / "rev9_hazirlik.py")
r9 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r9)

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
BAS = T("2025-01-01 00:00")


def _seri(kayitlar):
    return pd.DataFrame({"odeme_zamani": pd.DatetimeIndex([T(z) for z, _ in kayitlar]),
                         "aralik_saat": [float(a) for _, a in kayitlar]})


def _sa(seri, giris, son, bas=BAS):
    return r9.son_adim_tamlik_ayrintisi(seri, [T(giris)], [T(son)], [bas]).iloc[0]


def _dort_saat(*eksik):
    z = pd.date_range("2025-01-01 00:00", "2025-01-03 00:00", freq="4h", tz="UTC")
    return _seri([(str(x.tz_localize(None)), 4) for x in z if str(x.tz_localize(None)) not in eksik])


def test_duzenli_seri_tam():
    assert _sa(_dort_saat(), "2025-01-01 04:00", "2025-01-02 04:00")["tam"]


def test_penceredeki_eksik_beklenen_an_eksik_yapar():
    seri = _dort_saat("2025-01-01 12:00:00")
    assert not _sa(seri, "2025-01-01 04:00", "2025-01-01 20:00")["tam"]


def test_giris_anindaki_eksik_beklenen_an_tamligi_bozmaz():
    seri = _dort_saat("2025-01-01 12:00:00")
    # Giris 08:00: beklenen an 12:00 giristen sonra ve kayitsiz -> eksik.
    assert not _sa(seri, "2025-01-01 08:00", "2025-01-01 20:00")["tam"]
    # Giris 12:00 (eksik anin kendisi): beklenen an giris aniyla ayni -> bozmaz. Zincir
    # ayni aralikla surer; 16:00 ve 20:00'da kayit var.
    assert _sa(seri, "2025-01-01 12:00", "2025-01-01 20:00")["tam"]


def test_giristen_onceki_eksik_beklenen_an_bozmaz_ama_zincir_surer():
    # 04:00 ve 08:00 eksik; giris 06:00. Beklenen anlar: 04:00 (giristen once, bozmaz),
    # 08:00 (giristen sonra, kayitsiz) -> eksik.
    seri = _dort_saat("2025-01-01 04:00:00", "2025-01-01 08:00:00")
    assert not _sa(seri, "2025-01-01 06:00", "2025-01-01 16:00")["tam"]
    # Pencere 08:00'dan once biterse tam.
    assert _sa(seri, "2025-01-01 06:00", "2025-01-01 07:00")["tam"]


def test_kisa_araliktan_uzuna_gecis_yanlis_eksik_uretmez():
    # 19:00 (1h) -> 20:00 (4h) -> 00:00. Onceki tanim 23:00'te beklenen an uretip eksik
    # diyordu; bu tanim 20:00 kaydinin araligiyla surer.
    seri = _seri([("2025-01-01 17:00", 1), ("2025-01-01 18:00", 1), ("2025-01-01 19:00", 1),
                  ("2025-01-01 20:00", 4), ("2025-01-02 00:00", 4), ("2025-01-02 04:00", 4)])
    assert _sa(seri, "2025-01-01 18:00", "2025-01-02 04:00")["tam"]
    assert not r9.son_hal_tamlik_ayrintisi(seri, [T("2025-01-01 18:00")], [T("2025-01-02 04:00")],
                                           [BAS])["tam"].iloc[0]


def test_uzun_araliktan_kisaya_gecis_tam():
    # 00:00 (8h) -> 08:00 (1h) -> saatlik. Beklenen an 08:00, orada kayit var; sonraki adim 1 saat.
    seri = _seri([("2025-01-01 00:00", 8), ("2025-01-01 08:00", 1), ("2025-01-01 09:00", 1),
                  ("2025-01-01 10:00", 1)])
    assert _sa(seri, "2025-01-01 00:00", "2025-01-01 10:00")["tam"]
    # 09:00 eksikse eksik.
    seri2 = seri.loc[seri["odeme_zamani"] != T("2025-01-01 09:00")].reset_index(drop=True)
    assert not _sa(seri2, "2025-01-01 00:00", "2025-01-01 10:00")["tam"]


def test_zincir_kayitlarin_uzerinden_atlayabilir():
    # 00:00 kaydi 8 saat diyor ama odemeler 4 saatlik ritimde. Zincir 08:00'a iner ve
    # 04:00 kaydini atlar; o kayit hic olmasaydi da tanim TAM derdi (bilinen sinir).
    seri = _seri([("2025-01-01 00:00", 8), ("2025-01-01 04:00", 4), ("2025-01-01 08:00", 4),
                  ("2025-01-01 12:00", 4)])
    assert _sa(seri, "2025-01-01 00:00", "2025-01-01 12:00")["tam"]
    eksikli = seri.loc[seri["odeme_zamani"] != T("2025-01-01 04:00")].reset_index(drop=True)
    assert _sa(eksikli, "2025-01-01 00:00", "2025-01-01 12:00")["tam"]


def test_pencere_sonundaki_beklenen_an_aranir():
    seri = _seri([("2025-01-01 00:00", 8), ("2025-01-01 08:00", 8), ("2025-01-01 16:00", 8)])
    s = _sa(seri, "2025-01-01 04:00", "2025-01-02 00:00")
    assert not s["tam"] and s["ihlal_pencere_sonunda"]
    seri2 = pd.concat([seri, _seri([("2025-01-02 00:00", 8)])], ignore_index=True)
    s2 = _sa(seri2, "2025-01-01 04:00", "2025-01-02 00:00")
    assert s2["tam"] and s2["kayit_pencere_sonunda"]


def test_capa_yoksa_eksik():
    seri = _seri([("2025-01-01 08:00", 8), ("2025-01-01 16:00", 8)])
    s = _sa(seri, "2025-01-01 04:00", "2025-01-01 20:00")
    assert not s["tam"] and not s["capa_var"]


def test_capa_donem_basindan_once_olamaz():
    seri = _seri([("2024-12-31 20:00", 4), ("2025-01-01 08:00", 4), ("2025-01-01 12:00", 4)])
    assert not _sa(seri, "2025-01-01 04:00", "2025-01-01 12:00")["capa_var"]


def test_capa_donem_ilk_kaydi_bayragi():
    seri = _dort_saat()
    assert _sa(seri, "2025-01-01 00:00", "2025-01-01 08:00")["capa_donem_ilk_kaydi"]
    assert not _sa(seri, "2025-01-01 08:00", "2025-01-01 16:00")["capa_donem_ilk_kaydi"]


def test_tolerans_kurali():
    ok = _seri([("2025-01-01 00:00", 4), ("2025-01-01 04:00:30", 4), ("2025-01-01 08:00:30", 4)])
    assert _sa(ok, "2025-01-01 00:00", "2025-01-01 08:00")["tam"]
    kotu = _seri([("2025-01-01 00:00", 4), ("2025-01-01 04:01", 4), ("2025-01-01 08:00", 4)])
    assert not _sa(kotu, "2025-01-01 00:00", "2025-01-01 08:00")["tam"]


def test_kayitsiz_kisa_pencere_tam():
    seri = _seri([("2025-01-01 00:00", 8), ("2025-01-01 08:00", 8), ("2025-01-01 16:00", 8)])
    assert _sa(seri, "2025-01-01 08:00", "2025-01-01 12:00")["tam"]


def test_serinin_sonundan_sonra_beklenen_an_eksiktir():
    seri = _seri([("2025-01-01 00:00", 4), ("2025-01-01 04:00", 4)])
    assert not _sa(seri, "2025-01-01 04:00", "2025-01-01 12:00")["tam"]
    assert _sa(seri, "2025-01-01 04:00", "2025-01-01 07:00")["tam"]


def test_gecersiz_aralik_tam_degil():
    seri = _seri([("2025-01-01 00:00", 8), ("2025-01-01 08:00", np.nan), ("2025-01-01 16:00", 8)])
    s = _sa(seri, "2025-01-01 04:00", "2025-01-01 20:00")
    assert not s["tam"] and not s["aralik_gecerli"]


def test_vektorel_tekil_ile_ayni():
    seri = _dort_saat("2025-01-01 12:00:00")
    girisler = [T("2025-01-01 00:00"), T("2025-01-01 12:00"), T("2025-01-01 16:00"), T("2025-01-01 04:00")]
    sonlar = [T("2025-01-01 08:00"), T("2025-01-02 00:00"), T("2025-01-02 04:00"), T("2025-01-01 12:00")]
    toplu = r9.son_adim_tamlik_ayrintisi(seri, girisler, sonlar, [BAS] * 4)
    for i in range(4):
        tek = r9.son_adim_tamlik_ayrintisi(seri, [girisler[i]], [sonlar[i]], [BAS]).iloc[0]
        assert toplu.iloc[i].equals(tek)
    assert list(toplu["tam"]) == [True, True, True, False]


def test_fark_turu_beklenen_an_eksik():
    seri = _dort_saat("2025-01-01 12:00:00")
    sa = _sa(seri, "2025-01-01 04:00", "2025-01-01 20:00")
    rev8 = r9.funding_modulu.funding_tamlik_ayrintisi(seri, [T("2025-01-01 04:00")],
                                                      [T("2025-01-01 20:00")]).iloc[0]
    assert not sa["tam"] and not rev8["tam"]
    assert r9.son_adim_fark_turu(rev8, sa, False) is None


def test_fark_turu_kayitsiz_kisa_pencere():
    seri = _seri([("2025-01-01 00:00", 8), ("2025-01-01 08:00", 8), ("2025-01-01 16:00", 8)])
    sa = _sa(seri, "2025-01-01 08:00", "2025-01-01 12:00")
    rev8 = r9.funding_modulu.funding_tamlik_ayrintisi(seri, [T("2025-01-01 08:00")],
                                                      [T("2025-01-01 12:00")]).iloc[0]
    assert r9.son_adim_fark_turu(rev8, sa, False) == "kayitsiz_kisa_pencere"


def test_uzunluk_uyusmazligi_hata():
    with pytest.raises(ValueError):
        r9.son_adim_tamlik_ayrintisi(_dort_saat(), [T("2025-01-01 04:00")], [], [BAS])
