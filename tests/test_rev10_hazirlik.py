"""Rev.10 hazirligi olcum betigi (analysis/00_veri_denetimi/rev10_hazirlik.py). Aga cikmaz; yalnizca
elle kurulmus seriler, zaman ve aralik (oran sutunu yok)."""

from __future__ import annotations

import ast
import importlib.util
import inspect
import sys
import textwrap

import pandas as pd

import config

DIZIN = config.ANALIZ_DIZINI / "00_veri_denetimi"
sys.path.insert(0, str(DIZIN))
_spec = importlib.util.spec_from_file_location("_rev10_hazirlik", DIZIN / "rev10_hazirlik.py")
r10 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r10)

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
DK = pd.Timedelta(minutes=1)
BAS = T("2025-01-01")


def _seri(bas, son, saat, disla=()):
    z = [x for x in pd.date_range(T(bas), T(son), freq=f"{saat}h") if x not in set(disla)]
    return pd.DataFrame({"odeme_zamani": pd.DatetimeIndex(z), "aralik_saat": float(saat)})


def _h2(seri, t):
    return r10.h2_pencere_sayimi([T(t)], seri, BAS).iloc[0]


def test_sekiz_saatlik_ritimde_a_okumasi_uc_kayit():
    seri = _seri("2025-01-01", "2025-01-05", 8)
    # t 20:00 -> kapanis 00:00, bas onceki gun 00:00: iki uc da kayitli.
    s = _h2(seri, "2025-01-03 20:00")
    assert (s["kayit_A"], s["kayit_B"], s["ritim"], s["zincir_tam"]) == (3, 4, "8", True)
    # t 00:00 -> kapanis 04:00: iki ucta kayit yok.
    s = _h2(seri, "2025-01-03 00:00")
    assert (s["kayit_A"], s["kayit_B"]) == (3, 3)


def test_pencere_ucu_tolerans_kenari():
    """Pencere basindan 59.999 s sonraki kayit bas ile ayni an (A disarida); tam 1 dk sonraki icerde."""
    z = [T("2025-01-02 00:00") + DK - pd.Timedelta(1, "ns"), T("2025-01-02 08:00"), T("2025-01-02 16:00"),
         T("2025-01-03 00:00")]
    seri = pd.DataFrame({"odeme_zamani": pd.DatetimeIndex([T("2025-01-01 16:00")] + z), "aralik_saat": 8.0})
    s = _h2(seri, "2025-01-02 20:00")
    assert (s["kayit_A"], s["kayit_B"]) == (3, 4)
    z[0] = T("2025-01-02 00:00") + DK
    seri2 = pd.DataFrame({"odeme_zamani": pd.DatetimeIndex([T("2025-01-01 16:00")] + z), "aralik_saat": 8.0})
    assert _h2(seri2, "2025-01-02 20:00")["kayit_A"] == 4


def test_kapanistan_sonraki_kayit_sayilmaz():
    seri = _seri("2025-01-01", "2025-01-05", 8)
    kayik = seri.copy()
    kayik.loc[kayik["odeme_zamani"] == T("2025-01-04 00:00"), "odeme_zamani"] = T("2025-01-04 00:01")
    assert _h2(kayik, "2025-01-03 20:00")["kayit_A"] == 2


def test_zincir_eksik_odemede_tam_degil_ve_taban():
    seri = _seri("2025-01-01", "2025-01-05", 8, disla=[T("2025-01-03 08:00")])
    assert not _h2(seri, "2025-01-03 20:00")["zincir_tam"]
    # Capa taban oncesinde: taban pencere basindan sonra ise capa yok.
    s = r10.h2_pencere_sayimi([T("2025-01-03 20:00")], _seri("2025-01-01", "2025-01-05", 8), T("2025-01-03 00:01"))
    assert not s["zincir_tam"].iloc[0]


def test_karisik_ritim_etiketi():
    seri = pd.concat([_seri("2025-01-01", "2025-01-03 08:00", 8), _seri("2025-01-03 12:00", "2025-01-05", 4)],
                     ignore_index=True)
    assert _h2(seri, "2025-01-03 12:00")["ritim"] == "karisik"


class _Plan:
    def __init__(self, giris):
        self.giris = T(giris)


def _gev(seri, giris, son):
    from data import funding
    g = funding.funding_tamlik_ayrintisi(seri, [T(giris)], [T(son)], donem_baslari=[BAS])
    return g, r10.gevseklik_ayrintisi(seri, [_Plan(giris)], g).iloc[0]


def test_gecise_bitisik_eksik_odeme_supheli_sayilir():
    # 1h ritim 16..18 (19:00 eksik), 20:00'de 4h ritme gecis: kural tam der.
    seri = pd.concat([_seri("2025-01-02 16:00", "2025-01-02 18:00", 1), _seri("2025-01-02 20:00", "2025-01-03 08:00", 4)],
                     ignore_index=True)
    g, s = _gev(seri, "2025-01-02 16:00", "2025-01-03 08:00")
    assert g["tam"].iloc[0] and s["kendi"] and s["gecis_kendi"] == "1->4" and s["kucuk"]


def test_eksiksiz_gecis_kendi_olcusunde_supheli_degil():
    seri = pd.concat([_seri("2025-01-02 16:00", "2025-01-02 19:00", 1), _seri("2025-01-02 20:00", "2025-01-03 08:00", 4)],
                     ignore_index=True)
    _, s = _gev(seri, "2025-01-02 16:00", "2025-01-03 08:00")
    assert not s["kendi"] and not s["kucuk"]


def test_beklenen_an_giristen_once_ise_sayilmaz():
    seri = pd.concat([_seri("2025-01-02 16:00", "2025-01-02 18:00", 1), _seri("2025-01-02 20:00", "2025-01-03 08:00", 4)],
                     ignore_index=True)
    _, s = _gev(seri, "2025-01-02 19:30", "2025-01-03 08:00")  # capa 18:00, beklenen 19:00 < giris
    assert not s["kendi"]


def test_sekizden_dorde_geciste_kucuk_olcu():
    # 08:00 (8) -> 12:00 eksik -> 16:00 (4): kendi olcu gormez (8 = 8), kucuk olcu gorur.
    seri = pd.concat([_seri("2025-01-02 00:00", "2025-01-02 08:00", 8), _seri("2025-01-02 16:00", "2025-01-03 00:00", 4)],
                     ignore_index=True)
    g, s = _gev(seri, "2025-01-02 04:00", "2025-01-03 00:00")
    assert g["tam"].iloc[0] and not s["kendi"] and s["kucuk"] and s["gecis_kucuk"] == "8->4"


def test_oran_okunmaz_ve_kural_kopyasi_yok():
    for fonk in (r10.h2_pencere_sayimi, r10.gevseklik_ayrintisi, r10.sembol_olc):
        kaynak = inspect.getsource(fonk)
        belge = ast.get_docstring(ast.parse(textwrap.dedent(kaynak)).body[0]) or ""
        assert "oran_8h" not in kaynak.replace(belge, "") and '"oran"' not in kaynak
    assert "funding_tamlik_ayrintisi" in inspect.getsource(r10.h2_pencere_sayimi)
