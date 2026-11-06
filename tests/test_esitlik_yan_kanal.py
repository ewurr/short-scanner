"""Esitlik betiginde olay rolunun yan kanallari (performans 2b-0 kapanisi, RESULTS §14.46; denetci D-C2, D-C3, D-C4,
sizinti S-39).

Olay rolunde birim suresi (`sure_s`) ve uyusmayan / beklenmeyen barlarin zaman damgalari (`ilk_20_*`) yazilmaz;
yalnizca sayilar kalir. Uyusmazlik ya da beklenmeyen hata varsa betik 1 ile cikar. `config.TOHUM` her satira yazilir.
Sentetik girdiyle; aga cikmaz, gercek veri okunmaz, depoya dosya yazilmaz.
"""

from __future__ import annotations

import contextlib
import sys
import types

import pandas as pd
import pytest

from data import pozisyon
from tarama_yardimcisi import KOK

sys.path.insert(0, str(KOK / "analysis" / "00_veri_denetimi"))
import calistir  # noqa: E402
import esitlik_kapi as ek  # noqa: E402

_IZGARA = pd.date_range("2022-01-01", periods=30, freq="4h", tz="UTC")


def _sahte_dunya(monkeypatch, uyusmaz: set[int], beklenmeyen: set[int]) -> None:
    """`karsilastir`in kullandigi `karar`i sahteler: `uyusmaz` siralarda iki taraf farkli sinifla reddeder,
    `beklenmeyen` siralarda iki taraf ayni `TypeError` ile duser."""
    monkeypatch.setattr(ek, "_donemler", lambda sembol: [0])
    monkeypatch.setattr(ek, "bar_izgarasi", lambda kimlik, hipotez: _IZGARA)
    monkeypatch.setattr(ek, "sinir_siralari", lambda izgara, kimlik: set())

    def karar(modul, hipotez, yapilandirma, rol, t, kimlik, sira):
        if sira in beklenmeyen:
            return TypeError("x")
        if sira in uyusmaz and modul is not pozisyon:
            return pozisyon.UygunDegil("referans")
        return pozisyon.SinyalKosuluSaglanmadi("ayni")

    monkeypatch.setattr(ek, "karar", karar)


def _ayar(roller=("olay", "K1")):
    return {"hipotezler": ["H2"], "yapilandirma": "ilk", "roller": list(roller), "funding_satiri": False, "bar": "tum",
            "n": 5}


def test_olay_rolunde_sure_ve_zaman_damgasi_yazilmaz_sayilar_yazilir(monkeypatch):
    _sahte_dunya(monkeypatch, uyusmaz={3, 7}, beklenmeyen={11})
    satirlar = ek.sembol_isi("X", _ayar())
    olay = [s for s in satirlar if s["rol"] == "olay"]
    k1 = [s for s in satirlar if s["rol"] == "K1"]
    assert len(olay) == 1 and len(k1) == 1
    o = olay[0]
    assert o["sure_s"] == "" and o["ilk_20_uyusmayan"] == "" and o["ilk_20_beklenmeyen"] == ""
    assert o["kapsam_bar"] == ""
    assert (o["karsilastirilan_bar"], o["uyusmayan_bar"]) == (30, 2)
    assert o["beklenmeyen_hata_referans"] == o["beklenmeyen_hata_yeni"] == 1
    assert not any(z.isoformat() in repr(o) for z in _IZGARA)
    # Kontrol rolunde (olay bilgisi tasimaz) ayrinti korunur.
    assert k1[0]["ilk_20_uyusmayan"] != "" and k1[0]["ilk_20_beklenmeyen"].startswith("referans:TypeError@")
    assert isinstance(k1[0]["sure_s"], float)
    # Sure sembol duzeyinde toplam olarak yazilir.
    toplam = [s for s in satirlar if s["rol"] == "TOPLAM_SURE"]
    assert len(toplam) == 1 and isinstance(toplam[0]["sure_s"], float)


def test_genel_tohum_her_satira_yazilir(monkeypatch):
    _sahte_dunya(monkeypatch, set(), set())
    satirlar = ek.sembol_isi("X", _ayar())
    assert "genel_tohum" in ek.SUTUNLAR
    assert satirlar and all(s["genel_tohum"] == ek.config.TOHUM for s in satirlar)
    assert ek._guvenli_sembol_isi.__name__  # hata satiri da `_bos_satir`dan gelir
    hata = ek._bos_satir("X", -1, "", "", "HATA")
    assert hata["genel_tohum"] == ek.config.TOHUM


def test_sayac_olay_alanlari_zaman_tasimaz():
    sayac = ek.Sayac()
    t = pd.Timestamp("2022-03-04 08:00", tz="UTC")
    sayac.bar(t, False, (TypeError("x"),), ())
    alanlar = sayac.alanlar(kapsam_yazilir=False, zaman_yazilir=False)
    assert alanlar["ilk_20_uyusmayan"] == alanlar["ilk_20_beklenmeyen"] == alanlar["kapsam_bar"] == ""
    assert (alanlar["uyusmayan_bar"], alanlar["beklenmeyen_hata_referans"]) == (1, 1)
    assert t.isoformat() not in repr(alanlar)


@pytest.mark.parametrize("uyusmaz,beklenmeyen,kod", [(set(), set(), 0), ({2}, set(), 1), (set(), {4}, 1)])
def test_olay_rolunde_uyusmazlik_ya_da_beklenmeyen_hata_cikis_kodu_1(monkeypatch, tmp_path, capsys, uyusmaz,
                                                                     beklenmeyen, kod):
    _sahte_dunya(monkeypatch, uyusmaz, beklenmeyen)

    class Kayit:
        def alanlar(self):
            return {"head_commit": "a" * 40, "agac_temiz": True}

    @contextlib.contextmanager
    def kesif():
        yield Kayit()

    yazilan = []
    monkeypatch.setattr(ek, "split_modulu", types.SimpleNamespace(kesif_kosusu=kesif))
    monkeypatch.setattr(ek, "ORNEK", tmp_path / "ornek.csv")
    pd.DataFrame({"sembol": ["X"]}).to_csv(tmp_path / "ornek.csv", index=False)
    monkeypatch.setattr(calistir, "csv_yaz", lambda tablo, yol: yazilan.append(tablo))
    monkeypatch.setattr(calistir, "kosu_kilidi", lambda ad: contextlib.nullcontext())
    assert ek.main(["--bar", "tum", "--rol", "olay", "--hipotez", "H2", "--no-funding-satiri", "--isci", "1"]) == kod
    assert yazilan and list(yazilan[0].columns) == ek.SUTUNLAR
    for z in _IZGARA:
        assert z.isoformat() not in yazilan[0].to_csv(index=False)
    cikti = capsys.readouterr()
    assert all(z.isoformat() not in cikti.out + cikti.err for z in _IZGARA)
