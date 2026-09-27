"""Karar noktasi kume sinirini `None` kabul etmez (F1 kapanis turu 2, Rev.10 denetci D-C3).

On-kayit §3 "Kume siniri ve geriye bakis": "kod duzeyinde ayrica dogrulanir — verinin kume sinirinda
kesilmis olmasina dayanilmaz". Her olay ve kontrol bir kumeye aittir; `pozisyon.olay_karari` iki kume
sinirindan biri `None` ise programlama hatasi (TypeError) verir. Kaynak taramasi
(`tarama_yardimcisi.KUME_NONE_DESENI`) ikincil savunma olarak kalir. Aga cikmaz.
"""

from __future__ import annotations

import pandas as pd
import pytest

from data import pencere, pozisyon
from kume_yardimcisi import C2, KESIF, kume_sinirlari
from sinyal_yardimcisi import sinyal
from uygunluk_yardimcisi import uygunluk

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H = lambda n: pd.Timedelta(hours=n)  # noqa: E731

DB, B = T("2025-01-01"), T("2025-06-30 20:00")
Z = pd.date_range(T("2025-03-01"), B, freq="4h")
MUM = pd.DataFrame({"open_time": Z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
FUND = pd.DataFrame({"odeme_zamani": pd.date_range(DB, B + H(4), freq="8h"), "aralik_saat": 8.0,
                     "oran": 0.0, "oran_8h": 0.0})
SINYAL_T = {"H1": T("2025-03-10 04:00"), "H2": T("2025-03-10 04:00"), "H3": T("2025-03-10")}


def _karar(hipotez, **kume):
    tanim = pencere.hipotez_ufuklari(hipotez)
    return pozisyon.olay_karari(MUM, FUND, SINYAL_T[hipotez], tanim.birincil, tanim.bar, hipotez=hipotez,
                                birincil_ufuk=tanim.birincil, donem_baslangic=DB, donem_bitis=B,
                                sinyal_degerleri=sinyal(hipotez), **kume, **uygunluk(tanim.bar, DB, B))


@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_gercek_kume_siniriyla_olusur(hipotez):
    assert pozisyon.onay_dogrula(_karar(hipotez, **KESIF)) is None


@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
@pytest.mark.parametrize("bos", [("kume_baslangic",), ("kume_bitis",), ("kume_baslangic", "kume_bitis")])
def test_none_kume_siniri_programlama_hatasi(hipotez, bos):
    kume = dict(KESIF)
    kume.update({ad: None for ad in bos})
    with pytest.raises(TypeError, match="None olamaz"):
        _karar(hipotez, **kume)


def test_none_reddi_diger_denetimlerden_once():
    """Sinyal degeri NaN olsa bile once kume siniri reddedilir: `None` hicbir ret gerekcesine
    (`OlayOlusmaz`) donusup sessizce sayilmaz."""
    tanim = pencere.hipotez_ufuklari("H1")
    with pytest.raises(TypeError, match="kume_bitis"):
        pozisyon.olay_karari(MUM, FUND, SINYAL_T["H1"], tanim.birincil, tanim.bar, hipotez="H1",
                             birincil_ufuk=tanim.birincil, kume_baslangic=KESIF["kume_baslangic"], kume_bitis=None,
                             donem_baslangic=DB, donem_bitis=B, sinyal_degerleri=sinyal("H1", pump_dip=float("nan")),
                             **uygunluk(tanim.bar, DB, B))


def test_none_degiskenle_tasinsa_da_reddedilir():
    """Tarama degiskenle tasinan None'u gormez (tur_saldirilari_j); kapi gorur."""
    x = None
    kume = {"kume_baslangic": KESIF["kume_baslangic"], "kume_bitis": x}
    with pytest.raises(TypeError, match="None olamaz"):
        _karar("H2", **kume)


def test_nat_kume_siniri_de_reddedilir():
    with pytest.raises(TypeError):
        _karar("H2", kume_baslangic=KESIF["kume_baslangic"], kume_bitis=pd.NaT)


def test_yardimci_gercek_kumeleri_verir():
    assert kume_sinirlari(T("2025-08-31 20:00")) == KESIF
    assert kume_sinirlari(T("2025-09-01 00:00")) == C2
    with pytest.raises(ValueError):
        kume_sinirlari(T("2033-01-01"))
