"""Hipotez -> izgara -> ufuk bagi yapisaldir (F1 kapanis turu, denetci D-B2; on-kayit §4 "Ufuk degerlerinin
baglanmasi", rev.10; §2 "Bar tipleri").

Tek kapi `pozisyon.olay_karari` zorunlu `hipotez` anahtar sozcugu alir; izgara ve ufuklar hipotezden
`config`'in on-kayit bolumu uzerinden turer (`pencere.hipotez_ufuklari`) ve verilen `bar`, `ufuk`,
`birincil_ufuk` bunlarla uyumsuzsa calisma aninda ValueError. Onayli pozisyon hipotezi imzali tasir.
Kaynak taramasi ikincil savunmadir. Aga cikmaz.
"""

from __future__ import annotations

from dataclasses import replace

import pandas as pd
import pytest

import config
from data import pencere, pozisyon
from tarama_yardimcisi import KOK
from uygunluk_yardimcisi import uygunluk

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
DB, B = T("2025-01-01"), T("2025-06-30 20:00")
Z = pd.date_range(T("2025-03-01"), B, freq="4h")
MUM = pd.DataFrame({"open_time": Z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
_FZ = pd.date_range(DB, B + pd.Timedelta(hours=4), freq="8h")
FUND = pd.DataFrame({"odeme_zamani": _FZ, "aralik_saat": 8.0, "oran": 0.0, "oran_8h": 0.0})
SINYAL = {config.BAR_4H: T("2025-03-10 04:00"), config.BAR_1D: T("2025-03-10")}


def _karar(hipotez, bar, ufuk, birincil):
    return pozisyon.olay_karari(MUM, FUND, SINYAL[bar], ufuk, bar, hipotez=hipotez, birincil_ufuk=birincil,
                                kume_baslangic=None, kume_bitis=None, donem_baslangic=DB, donem_bitis=B,
                                sinyal_degerleri=_sinyal(hipotez), **uygunluk(bar, DB, B))


def _sinyal(hipotez):
    return {ad: 1.0 for ad in getattr(pozisyon, "SINYAL_DEGERLERI", {}).get(hipotez, ("x",))}


def test_hipotez_ufuklari_tek_kaynaktan():
    for h, bar in (("H1", config.BAR_4H), ("H2", config.BAR_4H), ("H3", config.BAR_1D)):
        t = pencere.hipotez_ufuklari(h)
        assert (t.hipotez, t.bar) == (h, bar)
        assert t.birincil == config.BIRINCIL_UFUK[bar]
        assert t.ikincil == config.IKINCIL_UFUKLAR[bar]
        assert t.ileri_kayma_siniri == config.ILERI_KAYMA_SINIRI[bar]
        assert t.ufuklar == config.UFUKLAR[bar]
    assert pencere.hipotez_ufuklari("H2").birincil == 18 and pencere.hipotez_ufuklari("H3").birincil == 14


@pytest.mark.parametrize("hipotez", ["H4", "h1", "", "H1 "])
def test_bilinmeyen_hipotez_reddedilir(hipotez):
    with pytest.raises(ValueError, match="hipotez"):
        pencere.hipotez_ufuklari(hipotez)


@pytest.mark.parametrize("hipotez", [None, 1, ("H1",)])
def test_metin_olmayan_hipotez_reddedilir(hipotez):
    with pytest.raises(TypeError):
        pencere.hipotez_ufuklari(hipotez)


@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_uyumlu_eslesme_kabul_edilir_ve_hipotez_imzali(hipotez):
    t = pencere.hipotez_ufuklari(hipotez)
    for ufuk in t.ufuklar:
        p = _karar(hipotez, t.bar, ufuk, t.birincil)
        assert p.hipotez == hipotez and p.plan.bar == t.bar and p.plan.ufuk == ufuk
    with pytest.raises(ValueError):
        pozisyon.pozisyon_fiyatlari(replace(p, hipotez="H2" if hipotez != "H2" else "H1"))


@pytest.mark.parametrize("hipotez, bar, ufuk, birincil", [
    ("H3", config.BAR_4H, 18, 18),   # H3 izgarasi 1d
    ("H1", config.BAR_1D, 14, 14),   # H1 izgarasi 4h
    ("H2", config.BAR_1D, 14, 14),
    ("H2", config.BAR_4H, 14, 18),   # 1d ufku 4h hipotezde
    ("H3", config.BAR_1D, 18, 14),   # 4h ufku 1d hipotezde
    ("H1", config.BAR_4H, 18, 14),   # birincil ufuk baska izgaranin
    ("H3", config.BAR_1D, 14, 18),
])
def test_uyumsuz_eslesme_calisma_aninda_hata(hipotez, bar, ufuk, birincil):
    with pytest.raises(ValueError):
        _karar(hipotez, bar, ufuk, birincil)


def test_hipotez_zorunlu():
    with pytest.raises(TypeError):
        pozisyon.olay_karari(MUM, FUND, SINYAL[config.BAR_4H], 18, config.BAR_4H, birincil_ufuk=18,
                             kume_baslangic=None, kume_bitis=None, donem_baslangic=DB, donem_bitis=B,
                             sinyal_degerleri=_sinyal("H1"), **uygunluk(config.BAR_4H, DB, B))


def test_depoda_notebook_yok():
    """Kaynak taramasi yalnizca .py dosyalarini okur (bilinen sinir). Taranmayan bicimde analiz kodu
    birikmesin diye depoda .ipynb bulunmamasi ayrica denetlenir."""
    bulunan = [p.relative_to(KOK).as_posix() for p in KOK.rglob("*.ipynb")
               if "cache" not in p.parts and ".ipynb_checkpoints" not in p.parts]
    assert bulunan == []
