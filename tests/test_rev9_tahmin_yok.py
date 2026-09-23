"""Rev.9 hazirligi, dorduncu tur: tahmin etmeyen tanim (rev9_hazirlik.tahmin_yok_tamlik_ayrintisi).
Aga cikmaz.

Kuralin yalnizca ardisik kayitlara ve son kayda baktigini (hicbir yerde beklenen odeme ani
uretmedigini), son kosulun esitlikte affettigini, kuralin birinci turun onerisiyle AYNI
oldugunu ve gevseklik olcusu sutunlarini sabitler.
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
_spec = importlib.util.spec_from_file_location("_rev9_hazirlik_ty", DIZIN / "rev9_hazirlik.py")
r9 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r9)

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
BAS = T("2025-01-01 00:00")


def _seri(kayitlar):
    return pd.DataFrame({"odeme_zamani": pd.DatetimeIndex([T(z) for z, _ in kayitlar]),
                         "aralik_saat": [float(a) for _, a in kayitlar]})


def _ty(seri, giris, son, bas=BAS):
    return r9.tahmin_yok_tamlik_ayrintisi(seri, [T(giris)], [T(son)], [bas]).iloc[0]


def _dort_saat(*eksik):
    z = pd.date_range("2025-01-01 00:00", "2025-01-03 00:00", freq="4h", tz="UTC")
    return _seri([(str(x.tz_localize(None)), 4) for x in z if str(x.tz_localize(None)) not in eksik])


def test_duzenli_seri_tam():
    assert _ty(_dort_saat(), "2025-01-01 04:00", "2025-01-02 04:00")["tam"]


def test_ardisik_bosluk_iki_araligin_buyugunu_asarsa_eksik():
    seri = _dort_saat("2025-01-01 12:00:00")
    assert not _ty(seri, "2025-01-01 04:00", "2025-01-01 20:00")["tam"]


def test_aralik_gecisi_yanlis_eksik_uretmez():
    # 1 saatten 4 saate gecis: bosluk 4 saat, iki araligin buyugu 4 -> tam.
    seri = _seri([("2025-01-01 17:00", 1), ("2025-01-01 18:00", 1), ("2025-01-01 19:00", 1),
                  ("2025-01-01 23:00", 4), ("2025-01-02 03:00", 4)])
    assert _ty(seri, "2025-01-01 18:00", "2025-01-02 03:00")["tam"]
    # Ucuncu turun adim tanimi ayni seride eksik diyordu (19:00 + 1 saat = 20:00'de kayit yok).
    assert not r9.son_adim_tamlik_ayrintisi(seri, [T("2025-01-01 18:00")], [T("2025-01-02 03:00")],
                                            [BAS])["tam"].iloc[0]


def test_son_kosulu_esitlikte_affeder():
    # Son kayit 16:00 (8 saat) -> 24:00 = pencere sonu, orada kayit yok: kural tam der.
    seri = _seri([("2025-01-01 00:00", 8), ("2025-01-01 08:00", 8), ("2025-01-01 16:00", 8)])
    s = _ty(seri, "2025-01-01 04:00", "2025-01-02 00:00")
    assert s["tam"] and s["son_esitlik_affi"] and not s["kuyruk_dogrulanmamis"]


def test_son_kayit_araligi_pencere_sonundan_once_dolarsa_eksik():
    seri = _seri([("2025-01-01 00:00", 4), ("2025-01-01 04:00", 4)])
    assert not _ty(seri, "2025-01-01 04:00", "2025-01-01 12:00")["tam"]


def test_kuyruk_dogrulanmamis_bayragi():
    # Son kayit 08:00 (8 saat) -> 16:00 > pencere sonu 12:00: tam ama kuyruk dogrulanmamis.
    seri = _seri([("2025-01-01 00:00", 8), ("2025-01-01 08:00", 8), ("2025-01-01 16:00", 8)])
    s = _ty(seri, "2025-01-01 04:00", "2025-01-01 12:00")
    assert s["tam"] and s["kuyruk_dogrulanmamis"] and not s["son_esitlik_affi"]


def test_kayitsiz_kisa_pencere_tam():
    seri = _seri([("2025-01-01 00:00", 8), ("2025-01-01 08:00", 8), ("2025-01-01 16:00", 8)])
    s = _ty(seri, "2025-01-01 08:00", "2025-01-01 12:00")
    assert s["tam"] and s["kuyruk_dogrulanmamis"]


def test_capa_yoksa_eksik():
    seri = _seri([("2025-01-01 08:00", 8), ("2025-01-01 16:00", 8)])
    s = _ty(seri, "2025-01-01 04:00", "2025-01-01 20:00")
    assert not s["tam"] and not s["capa_var"]


def test_capa_donem_basindan_once_olamaz():
    seri = _seri([("2024-12-31 20:00", 4), ("2025-01-01 08:00", 4), ("2025-01-01 12:00", 4)])
    assert not _ty(seri, "2025-01-01 04:00", "2025-01-01 12:00")["capa_var"]


def test_aralik_degisimi_bayragi():
    seri = _seri([("2025-01-01 00:00", 4), ("2025-01-01 04:00", 4), ("2025-01-01 08:00", 1),
                  ("2025-01-01 09:00", 1)])
    assert not _ty(seri, "2025-01-01 00:00", "2025-01-01 04:00")["aralik_degisimi_var"]
    assert _ty(seri, "2025-01-01 00:00", "2025-01-01 09:00")["aralik_degisimi_var"]


def test_tolerans_kurali():
    ok = _seri([("2025-01-01 00:00", 4), ("2025-01-01 04:00:30", 4), ("2025-01-01 08:00", 4)])
    assert _ty(ok, "2025-01-01 00:00", "2025-01-01 08:00")["tam"]
    # Tam bir aralik + 1 dakika: bosluk toleransi asar.
    kotu = _seri([("2025-01-01 00:00", 4), ("2025-01-01 04:01", 4), ("2025-01-01 08:01", 4)])
    assert not _ty(kotu, "2025-01-01 00:00", "2025-01-01 08:01")["tam"]


def test_birinci_turun_onerisiyle_ayni_kural():
    """Kural, birinci turun onerisiyle aynidir; fark yalnizca pencere sonunun secimindedir."""
    seri = _dort_saat("2025-01-01 12:00:00")
    girisler = [T("2025-01-01 00:00"), T("2025-01-01 08:00"), T("2025-01-01 12:00"), T("2025-01-01 16:00")]
    sonlar = [T("2025-01-01 08:00"), T("2025-01-02 00:00"), T("2025-01-01 20:00"), T("2025-01-02 04:00")]
    ty = r9.tahmin_yok_tamlik_ayrintisi(seri, girisler, sonlar, [BAS] * 4)
    oneri = r9.oneri_tamlik_ayrintisi(seri, girisler, sonlar, [BAS] * 4)
    assert list(ty["tam"]) == list(oneri["tam"])


def test_t_k_pencere_sonu_b():
    K = T("2025-01-10 12:00")
    B = K - pd.Timedelta(hours=4)
    assert r9.son_hal_pencere_sonu(K, "olagan", B, K) == B


def test_gecersiz_aralik_tam_degil():
    seri = _seri([("2025-01-01 00:00", 8), ("2025-01-01 08:00", np.nan), ("2025-01-01 16:00", 8)])
    s = _ty(seri, "2025-01-01 04:00", "2025-01-01 20:00")
    assert not s["tam"] and not s["aralik_gecerli"]


def test_vektorel_tekil_ile_ayni():
    seri = _dort_saat("2025-01-01 12:00:00")
    girisler = [T("2025-01-01 00:00"), T("2025-01-01 12:00"), T("2025-01-01 16:00"), T("2025-01-01 04:00")]
    sonlar = [T("2025-01-01 08:00"), T("2025-01-02 00:00"), T("2025-01-02 04:00"), T("2025-01-01 12:00")]
    toplu = r9.tahmin_yok_tamlik_ayrintisi(seri, girisler, sonlar, [BAS] * 4)
    for i in range(4):
        tek = r9.tahmin_yok_tamlik_ayrintisi(seri, [girisler[i]], [sonlar[i]], [BAS]).iloc[0]
        assert toplu.iloc[i].equals(tek)


def test_fark_turu():
    seri = _seri([("2025-01-01 00:00", 8), ("2025-01-01 08:00", 8), ("2025-01-01 16:00", 8)])
    ty = _ty(seri, "2025-01-01 08:00", "2025-01-01 12:00")
    rev8 = r9.rev8_tamlik_ayrintisi(seri, [T("2025-01-01 08:00")],
                                                      [T("2025-01-01 12:00")]).iloc[0]
    assert r9.tahmin_yok_fark_turu(rev8, ty, False) == "kayitsiz_kisa_pencere"


def test_uzunluk_uyusmazligi_hata():
    with pytest.raises(ValueError):
        r9.tahmin_yok_tamlik_ayrintisi(_dort_saat(), [T("2025-01-01 04:00")], [], [BAS])


def test_kuyruk_sifir_ve_kismi_ayrilir():
    seri = _seri([("2025-01-01 00:00", 4), ("2025-01-01 04:00", 4), ("2025-01-01 08:00", 4)])
    # Son kayit tam pencere sonunda: dogrulanamayan dilim yok.
    s = _ty(seri, "2025-01-01 00:00", "2025-01-01 08:00")
    assert s["tam"] and s["kuyruk_dogrulanmamis"] and s["kuyruk_sifir"] and not s["kuyruk_kismi"]
    # Pencere sonu son kayittan 2 saat sonra (aralik 4): 0 < dilim < aralik.
    s2 = _ty(seri, "2025-01-01 00:00", "2025-01-01 10:00")
    assert s2["tam"] and s2["kuyruk_kismi"] and not s2["kuyruk_sifir"]
