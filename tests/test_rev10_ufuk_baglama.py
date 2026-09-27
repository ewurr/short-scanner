"""Ufuk degerleri on-kayda baglidir (on-kayit §4 "Ufuk degerlerinin baglanmasi", rev.10).

"Birincil ufuk, ikincil ufuklar ve ileri kayma siniri yalnizca bu on-kayitta tanimlidir: H1 ve H2 icin
4h izgarada birincil 18 bar, ikincil 6 ve 42 bar, ileri kayma siniri 18 bar; H3 icin 1d izgarada
birincil 14 gun, ikincil 7 ve 30 gun, ileri kayma siniri 14 gun. Kod bu degerleri tek bir yerden,
on-kayit degeri olarak okur; getiri, olay ya da kontrol ureten hicbir cagri serbest bir ufuk degeri
kabul etmez."

Tek kaynak `config.py` (on-kayit bolumu). Olay ve kontrol ureten tek kapi `pozisyon.olay_karari`
on-kayit disindaki ufku ve birincil ufku reddeder; ic adimlar (`pencere.pozisyon_plani`,
`pencere.cikis_bari`, `pencere.cikis_hedefi`) analiz kodundan cagrilamaz (kaynak taramasi). Olcum
betikleri ayni kaynaktan okur. Aga cikmaz.
"""

from __future__ import annotations

import importlib.util
import re
import sys

import numpy as np
import pandas as pd
import pytest

import config
from data import pencere, pozisyon
from tarama_yardimcisi import CIKIS_KAPI_DISI_DESENI, KOK, ihlaller
from sinyal_yardimcisi import sinyal
from kume_yardimcisi import kume_sinirlari
from uygunluk_yardimcisi import uygunluk

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
DB, B = T("2025-01-01"), T("2025-06-30 20:00")
Z = pd.date_range(T("2025-03-01"), B, freq="4h")
MUM = pd.DataFrame({"open_time": Z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
_FZ = pd.date_range(DB, B + pd.Timedelta(hours=4), freq="8h")
FUND = pd.DataFrame({"odeme_zamani": _FZ, "aralik_saat": 8.0, "oran": 0.0, "oran_8h": 0.0})
SINYAL_4H = T("2025-03-10 04:00")
SINYAL_1D = T("2025-03-10")


# --- Tek kaynak ----------------------------------------------------------------------------------


def test_on_kayit_degerleri():
    assert config.BIRINCIL_UFUK == {config.BAR_4H: 18, config.BAR_1D: 14}
    assert config.IKINCIL_UFUKLAR == {config.BAR_4H: (6, 42), config.BAR_1D: (7, 30)}
    assert config.ILERI_KAYMA_SINIRI == {config.BAR_4H: 18, config.BAR_1D: 14}
    assert config.UFUKLAR == {config.BAR_4H: (6, 18, 42), config.BAR_1D: (7, 14, 30)}
    # Hipotez -> izgara: H1, H2 4h; H3 1d.
    assert config.HIPOTEZ_IZGARASI == {"H1": config.BAR_4H, "H2": config.BAR_4H, "H3": config.BAR_1D}


def test_ufuklar_on_kayit_disi_bolumde_degil():
    """`BIRINCIL_UFUK` "ON-KAYIT DEGILDIR" basligi altindan cikti: F1 teshis bolumunun basligi ile
    bir sonraki on-kayit bolumu arasinda ufuk tanimi yok."""
    metin = (KOK / "config.py").read_text(encoding="utf-8")
    bolumler = re.split(r"\n# --- ", metin)
    for bolum in bolumler:
        if "ON-KAYIT DEGILDIR" in bolum:
            assert not re.search(r"^(BIRINCIL_UFUK|IKINCIL_UFUKLAR|ILERI_KAYMA_SINIRI|UFUKLAR|HIPOTEZ_IZGARASI)\s*=",
                                 bolum, re.M), bolum[:60]


def test_ufuk_tanimi_yalnizca_configte():
    """config.py disinda (tests haric) ufuk degerleri tanimlanmaz: `UFUK...` adina sozluk/demet atamasi
    ya da `(6, 18, 42)`, `(7, 14, 30)` gibi degismez ufuk dizileri yok."""
    desen = re.compile(r"^\s*\w*UFUK\w*\s*=\s*[\{\(\[]|\(\s*6\s*,\s*18\s*,\s*42\s*\)|\(\s*7\s*,\s*14\s*,\s*30\s*\)"
                       r"|birincil_ufuk\s*=\s*\d", re.M)
    bulunan = []
    for yol in sorted(KOK.rglob("*.py")):
        goreli = yol.relative_to(KOK).as_posix()
        if goreli == "config.py" or goreli.startswith(("tests/", ".claude/")) or "cache" in yol.parts:
            continue
        if desen.search(yol.read_text(encoding="utf-8", errors="replace")):
            bulunan.append(goreli)
    assert bulunan == []


def test_olcum_betikleri_ayni_kaynaktan_okur():
    dizin = config.ANALIZ_DIZINI / "00_veri_denetimi"
    sys.path.insert(0, str(dizin))
    spec = importlib.util.spec_from_file_location("_rev9_hazirlik_ufuk", dizin / "rev9_hazirlik.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    assert modul.UFUKLAR is config.UFUKLAR


# --- Serbest deger reddi -------------------------------------------------------------------------


def _karar(ufuk, birincil, bar=config.BAR_4H):
    t = SINYAL_4H if bar == config.BAR_4H else SINYAL_1D
    return pozisyon.olay_karari(MUM, FUND, t, ufuk, bar, hipotez="H1" if bar == config.BAR_4H else "H3", birincil_ufuk=birincil, **kume_sinirlari(t), donem_baslangic=DB, donem_bitis=B, sinyal_degerleri=sinyal("H1" if bar == config.BAR_4H else "H3"),
                                **uygunluk(bar, DB, B))


@pytest.mark.parametrize("bar", [config.BAR_4H, config.BAR_1D])
def test_on_kayit_ufuklari_kabul_edilir(bar):
    for ufuk in config.UFUKLAR[bar]:
        p = _karar(ufuk, config.BIRINCIL_UFUK[bar], bar)
        assert p.plan.ufuk == ufuk and p.plan.birincil_ufuk == config.BIRINCIL_UFUK[bar]


@pytest.mark.parametrize("bar, ufuk", [
    (config.BAR_4H, 1), (config.BAR_4H, 3), (config.BAR_4H, 17), (config.BAR_4H, 19), (config.BAR_4H, 14),
    (config.BAR_4H, 7), (config.BAR_4H, 30), (config.BAR_1D, 18), (config.BAR_1D, 6), (config.BAR_1D, 42),
    (config.BAR_1D, 13), (config.BAR_1D, 1)])
def test_serbest_ufuk_reddedilir(bar, ufuk):
    with pytest.raises(ValueError, match="on-kayit"):
        _karar(ufuk, config.BIRINCIL_UFUK[bar], bar)


@pytest.mark.parametrize("bar, birincil", [
    (config.BAR_4H, 14), (config.BAR_4H, 6), (config.BAR_4H, 42), (config.BAR_4H, 19),
    (config.BAR_1D, 18), (config.BAR_1D, 7), (config.BAR_1D, 30)])
def test_serbest_birincil_ufuk_reddedilir(bar, birincil):
    with pytest.raises(ValueError, match="on-kayit"):
        _karar(config.BIRINCIL_UFUK[bar], birincil, bar)


@pytest.mark.parametrize("deger", [True, 18.0, "18", None, np.float64(18.0)])
def test_tamsayi_olmayan_ufuk_reddedilir(deger):
    with pytest.raises((TypeError, ValueError)):
        _karar(deger, 18)
    with pytest.raises((TypeError, ValueError)):
        _karar(18, deger)


def test_numpy_tamsayi_kabul_edilir():
    p = _karar(np.int64(18), np.int64(18))
    assert p.plan.ufuk == 18 and type(p.plan.ufuk) is int


def test_ic_adimlara_analiz_kodundan_erisilmez():
    """Ufuk dogrulamasi tek kapidadir (`pozisyon.olay_karari`): olay ve kontrol yalnizca oradan
    uretilir (on-kayit §4 rev.8 "Olayin kumede olusma olcutu"). Ic adimlar (`pozisyon_plani`,
    `cikis_bari`, `cikis_hedefi`) F1 olcumleri ve testler icin serbest tamsayi alir; analiz kodu
    (events/, study/, F2 analizleri) onlari cagiramaz (kaynak taramasi)."""
    assert ihlaller(CIKIS_KAPI_DISI_DESENI) == []
    assert ihlaller(r"\bcikis_hedefi\s*\(") == []
    assert re.search(CIKIS_KAPI_DISI_DESENI, "p = pencere.pozisyon_plani(z, t, 3, '4h', birincil_ufuk=3)")
    assert re.search(CIKIS_KAPI_DISI_DESENI, "c = cikis_bari(z, g, 3, '4h', birincil_ufuk=3)")


def test_kapi_gecerli_ufku_ic_adima_aynen_iletir():
    """Kapidan gecen plan on-kayit ufkunu tasir; ileri kayma siniri (ic adimda birincil ufuk) on-kayit
    ileri kayma siniriyla aynidir."""
    for bar in (config.BAR_4H, config.BAR_1D):
        assert config.ILERI_KAYMA_SINIRI[bar] == config.BIRINCIL_UFUK[bar]
        p = _karar(config.BIRINCIL_UFUK[bar], config.BIRINCIL_UFUK[bar], bar)
        assert p.plan.birincil_ufuk == config.ILERI_KAYMA_SINIRI[bar]


def test_ileri_kayma_siniri_on_kayittan():
    """Ileri kayma siniri `config.ILERI_KAYMA_SINIRI`: 4h'de 18 bar. Hedef bar eksik ve sonraki bar
    siniri tam asiyorsa olay olusmaz; sinirda ise olusur."""
    giris = SINYAL_4H + pd.Timedelta(hours=4)
    hedef_acilis = pencere.cikis_hedefi(giris, 18, config.BAR_4H) - pd.Timedelta(hours=4)
    sinir = hedef_acilis + config.ILERI_KAYMA_SINIRI[config.BAR_4H] * pd.Timedelta(hours=4)
    for son_bar, gecerli in ((sinir, True), (sinir + pd.Timedelta(hours=4), False)):
        z = Z[(Z < hedef_acilis) | (Z >= son_bar)]
        if gecerli:
            c = pencere.cikis_bari(z, giris, 18, config.BAR_4H, birincil_ufuk=18, donem_bitis=B, kume_bitis=None)
            assert c.tur == "ileri_kayma" and c.zaman == son_bar
        else:
            with pytest.raises(pencere.IleriKaymaSiniriHatasi):
                pencere.cikis_bari(z, giris, 18, config.BAR_4H, birincil_ufuk=18, donem_bitis=B, kume_bitis=None)
