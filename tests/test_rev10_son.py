"""Rev.10 hazirligi son tur olcum betigi (analysis/00_veri_denetimi/rev10_son.py). Aga cikmaz; elle
kurulmus seriler, yalnizca zaman ve aralik."""

from __future__ import annotations

import importlib.util
import sys

import pandas as pd

import config
from data import funding

DIZIN = config.ANALIZ_DIZINI / "00_veri_denetimi"
sys.path.insert(0, str(DIZIN))
_spec = importlib.util.spec_from_file_location("_rev10_son", DIZIN / "rev10_son.py")
r = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r)

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
BAS = T("2025-01-01")


def _seri(*parcalar):
    z, a = [], []
    for bas, son, saat, disla in parcalar:
        for x in pd.date_range(T(bas), T(son), freq=f"{saat}h"):
            if x not in {T(d) for d in disla}:
                z.append(x)
                a.append(float(saat))
    return pd.DataFrame({"odeme_zamani": pd.DatetimeIndex(z), "aralik_saat": a})


def _olc(seri, giris, son):
    g = funding.funding_tamlik_ayrintisi(seri, [T(giris)], [T(son)], donem_baslari=[BAS])
    return g.iloc[0], r.gevseklik_uc_olcu(seri, [T(giris)], g).iloc[0]


def test_denetci_ornegi_yalniz_kucuk_giris_gorur():
    """D-A2: capa 19:00 (1h), 20:00 eksik, giris 20:00, sonraki 23:00 (4h). Kural tam der; 21:00 ve
    22:00 giristen sonra eksik. kendi/kucuk ilk cifti atlar, kucuk_giris gorur."""
    seri = _seri(("2025-01-02 16:00", "2025-01-02 19:00", 1, ()), ("2025-01-02 23:00", "2025-01-03 11:00", 4, ()))
    g, s = _olc(seri, "2025-01-02 20:00", "2025-01-03 08:00")
    assert g["tam"] and not s["kendi"] and not s["kucuk"] and s["kucuk_giris"] and s["gecis_kucuk_giris"] == "1->4"


def test_eksiksiz_gecis_hicbir_olcude_supheli_degil():
    seri = _seri(("2025-01-02 16:00", "2025-01-02 19:00", 1, ()), ("2025-01-02 20:00", "2025-01-03 08:00", 4, ()))
    _, s = _olc(seri, "2025-01-02 17:00", "2025-01-03 08:00")
    assert not (s["kendi"] or s["kucuk"] or s["kucuk_giris"])


def test_kuculen_geciste_kendi_kacirir():
    seri = _seri(("2025-01-02 00:00", "2025-01-02 08:00", 8, ()), ("2025-01-02 16:00", "2025-01-03 00:00", 4, ()))
    g, s = _olc(seri, "2025-01-02 04:00", "2025-01-03 00:00")
    assert g["tam"] and not s["kendi"] and s["kucuk"] and s["kucuk_giris"]


def test_giris_oncesi_eksik_sayilmaz():
    # 19:00 eksik ama giris 19:30'dan sonra ilk beklenen an 20:00 ve kayit var.
    seri = _seri(("2025-01-02 16:00", "2025-01-02 18:00", 1, ()), ("2025-01-02 20:00", "2025-01-03 08:00", 4, ()))
    _, s = _olc(seri, "2025-01-02 19:30", "2025-01-03 08:00")
    assert not s["kucuk_giris"]


def test_h2_kume_sayimi_kenarlar():
    k_bas, k_son = T("2025-01-01"), T("2025-01-10 23:59:59")
    t = [T("2025-01-01 00:00"), T("2025-01-05 00:00"), T("2025-01-10 16:00"), T("2025-01-10 20:00")]
    seri = _seri(("2025-01-01", "2025-01-10 16:00", 8, ()))
    s = r.h2_kume_sayimi(t, seri, k_bas, k_bas, k_son)
    assert s["bar"] == 4 and s["bas_kume_oncesi_ham"] == 1 and s["bas_kume_oncesi_tol"] == 1
    # 20:00 barinin kapanisi 00:00: ham karsilastirmada kume sonrasi, tolerans ile ayni an.
    assert s["kapanis_kume_sonrasi_ham"] == 1 and s["kapanis_kume_sonrasi_tol"] == 0


def test_kume_kesimi_ham_karsilastirma():
    seri = _seri(("2024-12-31 16:00", "2025-01-02", 8, ()))
    kesik = r.kume_kes(seri, T("2025-01-01"), T("2025-01-01 23:59:59"))
    assert list(kesik["odeme_zamani"]) == [T("2025-01-01 00:00"), T("2025-01-01 08:00"), T("2025-01-01 16:00")]
