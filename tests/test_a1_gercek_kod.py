"""A1 olcumu kuralin kopyasini tasimaz; sayimlar gercek kod yolundan gelir
(denetci bulgulari D-B3, D-B4; on-kayit §4 rev.8). Aga cikmaz.

1. Kaynak taramasi: a1_olcumu.py cikis ve funding tamlik kuralini yeniden yazan
   bir fonksiyon (rev.7'deki `donem_sonu_cikisi`) ya da ic yardimci
   (`_odemeler_tam_mi`) cagrisi icermez; D kurali bolumu veri katmaninin kural
   fonksiyonlarini cagirir.
2. Casus: `d_kurali_olc`in yazdigi plan ve tamlik sutunlari, veri katmanindaki
   fonksiyonlar degistirildiginde degisir (sonuc baska bir yoldan gelemez).
3. Parametreler config.py'den okunur (birincil ufuk, temsili giris suresi).
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import textwrap

import pandas as pd
import pytest

import config
from data import funding as funding_modulu
from data import pencere as pencere_modulu
from data.donem import Donem

_yol = config.ANALIZ_DIZINI / "00_veri_denetimi" / "a1_olcumu.py"
_spec = importlib.util.spec_from_file_location("a1_olcumu_gercek", _yol)
a1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(a1)

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
DONEM = Donem(T("2025-04-01 00:00"), T("2025-04-14 08:00"), 80, 80)
FUND = pd.DataFrame({"odeme_zamani": pd.date_range(T("2025-04-12 00:00"), T("2025-04-14 12:00"), freq="4h"),
                     "aralik_saat": 4.0})


def _agac():
    return ast.parse(_yol.read_text(encoding="utf-8"))


def _cagrilar(fonk) -> set[str]:
    agac = ast.parse(textwrap.dedent(inspect.getsource(fonk)))
    cagri = [d.func for d in ast.walk(agac) if isinstance(d, ast.Call)]
    return ({f.attr for f in cagri if isinstance(f, ast.Attribute)}
            | {f.id for f in cagri if isinstance(f, ast.Name)})


def test_kural_kopyasi_yok():
    agac = _agac()
    tanimlar = {d.name for d in ast.walk(agac) if isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert "donem_sonu_cikisi" not in tanimlar
    adlar = {d.attr for d in ast.walk(agac) if isinstance(d, ast.Attribute)}
    adlar |= {d.id for d in ast.walk(agac) if isinstance(d, ast.Name)}
    # Ic tamlik yardimcisi ve cikis/pencere yapi taslari betikte kullanilmaz.
    for yasak in ("_odemeler_tam_mi", "donem_sonu_cikisi", "cikis_hedefi", "giris_ani", "_donemde_sayilir"):
        assert yasak not in adlar, yasak


def test_d_kurali_gercek_fonksiyonlari_cagirir():
    assert {"pozisyon_plani"} <= _cagrilar(a1.temsili_plan)
    assert {"funding_tamlik_ayrintisi", "funding_penceresi_sonu", "donemde_funding_var",
            "donem_sonrasi_kayitlari_at", "temsili_plan", "ret_gerekcesi"} <= _cagrilar(a1.d_kurali_olc)
    # Modul nesneleri veri katmaninin kendisidir (kopya modul degil).
    assert a1.pencere_modulu is pencere_modulu and a1.funding_modulu is funding_modulu


def test_tamlik_sutunlari_gercek_fonksiyondan(monkeypatch):
    """Casus: gercek tamlik fonksiyonu tersine cevrilirse satir da tersine doner."""
    once = a1.d_kurali_olc("X", [DONEM], ["delist_SETTLING"], FUND)[0]
    gercek = funding_modulu.funding_tamlik_ayrintisi
    cagri = []

    def casus(funding, girisler, sonlar, **kw):
        # Rev.9: capa tabani icin donem_baslari zorunlu; yalnizca bool sutunlar tersine cevrilir.
        cagri.append((list(girisler), list(sonlar), list(kw["donem_baslari"])))
        sonuc = gercek(funding, girisler, sonlar, **kw)
        for k in (*funding_modulu.TAMLIK_KOSULLARI, "tam"):
            sonuc[k] = ~sonuc[k]
        return sonuc

    monkeypatch.setattr(funding_modulu, "funding_tamlik_ayrintisi", casus)
    sonra = a1.d_kurali_olc("X", [DONEM], ["delist_SETTLING"], FUND)[0]
    assert cagri == [([once["giris"]], [DONEM.bitis], [DONEM.baslangic])]  # donem sonu penceresi B'de biter
    for k in (*funding_modulu.TAMLIK_KOSULLARI, "tamlik"):
        assert sonra[k] is (not once[k]), k


def test_plan_sutunlari_gercek_plandan(monkeypatch):
    """Casus: gercek plan reddederse satir ret gerekcesini yazar ve tamlik False."""
    def ret(*a, **k):
        raise pencere_modulu.IleriKaymaSiniriHatasi("casus")

    monkeypatch.setattr(pencere_modulu, "pozisyon_plani", ret)
    satir = a1.d_kurali_olc("X", [DONEM], ["delist_SETTLING"], FUND)[0]
    assert satir["ret_gerekcesi"] == "ileri_kayma_siniri"
    assert satir["tamlik"] is False and pd.isna(satir["giris"])


def test_funding_sinifi_gercek_fonksiyondan(monkeypatch):
    monkeypatch.setattr(funding_modulu, "donemde_funding_var", lambda *a, **k: "casus")
    assert a1.d_kurali_olc("X", [DONEM], ["delist_SETTLING"], FUND)[0]["funding_var"] == "casus"


def test_veri_sonu_donemi_kume_olcutuyle_reddedilir():
    """Rev.8 §4 "verinin sonu donem sonu degildir": kume sonuna tasan temsili plan olusmaz."""
    son = Donem(T("2026-08-20 00:00"), T("2026-08-31 20:00"), 72, 72)
    satir = a1.d_kurali_olc("X", [son], ["veri_sonu"], FUND)[0]
    assert satir["ret_gerekcesi"] == "kume_siniri"


def test_birincil_ufuk_configden(monkeypatch):
    assert config.BIRINCIL_UFUK == {config.BAR_4H: 18, config.BAR_1D: 14}  # on-kayit §4 tablosu
    assert a1.temsili_plan(DONEM, config.BAR_4H).ufuk == 18
    monkeypatch.setitem(config.BIRINCIL_UFUK, config.BAR_4H, 1)
    plan = a1.temsili_plan(DONEM, config.BAR_4H)
    assert plan.ufuk == 1 and plan.birincil_ufuk == 1 and plan.cikis_turu == "olagan"


def test_temsili_giris_suresi_configden():
    assert a1.TEMSILI_GIRIS_SURE == pd.Timedelta(config.DENETIM_TEMSILI_GIRIS_SURE)
    assert a1.temsili_plan(DONEM, config.BAR_4H).giris == DONEM.bitis - a1.TEMSILI_GIRIS_SURE


@pytest.mark.parametrize("sayi", [18, 14, 24])
def test_betikte_gomulu_ufuk_ya_da_sure_yok(sayi):
    """Kod govdesinde (belge metni haric) birincil ufuk ya da temsili sure sayi olarak yazilmaz."""
    agac = _agac()
    sabitler = [d for d in ast.walk(agac) if isinstance(d, ast.Constant) and d.value == sayi
                and not isinstance(d.value, bool)]
    assert not sabitler, [d.lineno for d in sabitler]
