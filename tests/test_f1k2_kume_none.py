"""Karar noktasi kume sinirini cagirandan almaz (F1 kapanis turu 2: None reddi; kapi sertlestirme turu:
kume adi, denetci F1K2 D-B1).

On-kayit §3 "Kume siniri ve geriye bakis": "kod duzeyinde ayrica dogrulanir — verinin kume sinirinda
kesilmis olmasina dayanilmaz". `pozisyon.olay_karari` yalnizca kume ADINI ("KESIF", "C1", "C2") alir ve
sinirlari `split.kume_araligi`ndan kendisi okur. `None`, serbest sinir cifti, karisik sinir ya da
bilinmeyen ad programlama hatasidir. Kaynak taramasi (`tarama_yardimcisi.KUME_NONE_DESENI`) ikincil
savunma olarak kalir. Aga cikmaz.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import pencere, pozisyon, split
from kapi_yardimcisi import donem, veri
from kume_yardimcisi import C2, KESIF, kume_adi, kume_sinirlari
from sinyal_yardimcisi import sinyal
from uygunluk_yardimcisi import esikler, uygunluk

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H = lambda n: pd.Timedelta(hours=n)  # noqa: E731

DB, B = T("2025-01-01"), T("2025-06-30 20:00")
Z = pd.date_range(T("2025-03-01"), B, freq="4h")
MUM = pd.DataFrame({"open_time": Z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
FUND = pd.DataFrame({"odeme_zamani": pd.date_range(DB, B + H(4), freq="8h"), "aralik_saat": 8.0,
                     "oran": 0.0, "oran_8h": 0.0})
SINYAL_T = {"H1": T("2025-03-10 04:00"), "H2": T("2025-03-10 04:00"), "H3": T("2025-03-10")}


def _karar(hipotez, degerler=None, **kume):
    tanim = pencere.hipotez_ufuklari(hipotez)
    return pozisyon.olay_karari(SINYAL_T[hipotez], tanim.birincil, tanim.bar, hipotez=hipotez,
                                birincil_ufuk=tanim.birincil, **veri(MUM, FUND, DB, B, uygun_bas=DB),
                                sinyal_degerleri=sinyal(hipotez) if degerler is None else degerler, **kume,
                                **esikler(tanim.bar))


@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_gercek_kume_adiyla_olusur_ve_sinirlar_kapidan(hipotez):
    p = _karar(hipotez, kume="KESIF")
    pozisyon.onay_dogrula(p)
    assert (p.plan.kume_baslangic, p.plan.kume_bitis) == split.kume_araligi("KESIF")


@pytest.mark.parametrize("kume", [None, pd.NaT, 0, "", True, "kesif", "KESIF ", "C3"])
def test_gecersiz_kume_programlama_hatasi(kume):
    with pytest.raises((TypeError, ValueError)):
        _karar("H2", kume=kume)


def test_str_alt_sinifi_kume_adi_reddedilir():
    class _Ad(str):
        def __eq__(self, diger):
            return True

        __hash__ = str.__hash__

    with pytest.raises(TypeError):
        _karar("H1", kume=_Ad("KESIF"))


@pytest.mark.parametrize("sinirlar", [dict(KESIF), {"kume_baslangic": KESIF["kume_baslangic"],
                                                      "kume_bitis": C2["kume_bitis"]},
                                      {"kume_baslangic": None, "kume_bitis": None}])
def test_serbest_sinir_cifti_kabul_edilmez(sinirlar):
    """Gercek, karisik ya da None sinir cifti: hepsi TypeError (kapi sinir parametresi almaz)."""
    with pytest.raises(TypeError):
        _karar("H1", **sinirlar)
    with pytest.raises(TypeError):
        _karar("H1", kume="KESIF", **sinirlar)


def test_none_reddi_diger_denetimlerden_once():
    """Sinyal degeri NaN olsa bile once kume reddedilir: gecersiz kume hicbir ret gerekcesine (`OlayOlusmaz`)
    donusup sessizce sayilmaz. NaT icin de ayni (onceki turda NaT plan adiminda reddediliyordu)."""
    for kume in (None, pd.NaT):
        with pytest.raises(TypeError):
            _karar("H1", degerler=sinyal("H1", pump_dip=float("nan")), kume=kume)


def test_sinyal_kumede_degilse_olay_olusmaz(tmp_path, monkeypatch):
    """KESIF'teki bir sinyal C2 adiyla verilirse kapi C2 sinirlarini okur ve reddeder.

    Kapi sertlestirme turu 2: kapi C2 verisini kume korumali yoldan yukler; onay kosusu olmadan
    `OnayGerekli` (onceki beklenti dogrudan OlayOlusmaz idi). Kosu icinde kume siniri reddeder."""
    with pytest.raises(split.OnayGerekli):
        _karar("H2", kume="C2")
    kayit = tmp_path / "onay_gecici.md"
    kayit.write_text("bas\n", encoding="utf-8")
    monkeypatch.setattr(config, "ONAY_KAYDI", kayit)
    with split.onay_kosusu("H2", "C2"):
        with pytest.raises(pencere.OlayOlusmaz):
            _karar("H2", kume="C2")


def test_yardimci_gercek_kumeleri_verir():
    assert kume_sinirlari(T("2025-08-31 20:00")) == KESIF
    assert kume_sinirlari(T("2025-09-01 00:00")) == C2
    assert kume_adi(T("2025-08-31 20:00")) == "KESIF" and kume_adi(T("2025-09-01")) == "C2"
    assert (KESIF["kume_baslangic"], KESIF["kume_bitis"]) == split.kume_araligi("KESIF")
    assert (C2["kume_baslangic"], C2["kume_bitis"]) == split.kume_araligi("C2")
    assert set(config.KUMELER) == {"KESIF", "C1", "C2"}
    with pytest.raises(ValueError):
        kume_sinirlari(T("2033-01-01"))
