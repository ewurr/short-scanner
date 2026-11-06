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
    # Denetci kapanis D-B1: birim suresi HICBIR rolde yazilmaz (toplamdan cikarma ile olay suresi elde edilemez).
    assert k1[0]["sure_s"] == ""
    # Olay rolu kosuldugu icin toplam sure de yazilmaz (denetci kapanis D-B1).
    toplam = [s for s in satirlar if s["rol"] == "TOPLAM_SURE"]
    assert len(toplam) == 1 and toplam[0]["sure_s"] == ""


@pytest.mark.parametrize("roller,funding", [(("olay",), False), (("olay", "K1"), False), (("olay", "K1", "K2"), True)])
def test_olay_rolu_kosulursa_hicbir_satirda_sure_yazilmaz(monkeypatch, roller, funding):
    """Denetci kapanis D-B1: tek rollu kosuda toplam olay biriminin suresi olurdu; cok rollu kosuda toplamdan diger
    birimlerin suresi cikarilirdi."""
    _sahte_dunya(monkeypatch, set(), set())
    if funding:
        monkeypatch.setattr(ek, "funding_karsilastir", lambda *a, **k: ek.Sayac())
    satirlar = ek.sembol_isi("X", {**_ayar(roller=roller), "funding_satiri": funding})
    assert all(s["sure_s"] == "" for s in satirlar)
    assert [s["rol"] for s in satirlar].count("TOPLAM_SURE") == 1


def _maliyetli_dunya(monkeypatch, onay_maskesi):
    """Onayli olay barinin sahte saati 1 sn ilerlettigi dunya (S-39 kanalinin kendisi); kontrol rolleri sabit maliyet."""
    saat = {"t": 0.0}
    monkeypatch.setattr(ek, "_donemler", lambda sembol: [0])
    monkeypatch.setattr(ek, "bar_izgarasi", lambda kimlik, hipotez: _IZGARA)
    monkeypatch.setattr(ek, "sinir_siralari", lambda izgara, kimlik: set())

    def karar(modul, hipotez, yapilandirma, rol, t, kimlik, sira):
        saat["t"] += 0.01
        if rol == "olay" and onay_maskesi[sira]:
            saat["t"] += 1.0
        return pozisyon.SinyalKosuluSaglanmadi("ayni")

    monkeypatch.setattr(ek, "karar", karar)
    monkeypatch.setattr(ek, "time", types.SimpleNamespace(perf_counter=lambda: saat["t"]))


def test_olay_suresi_toplamdan_cikarmayla_bulunamaz(monkeypatch):
    """Denetci kapanis D-B1: olay rolunun maliyeti onay sayisiyla buyurken (hepsi onay / hic onay) cikti satirlarinin
    HICBIR sayisal alani bunu tasimaz: (olay, K1) kosusunun butun satirlari iki maskede aynidir; olay rolu icermeyen
    (K1) kosusunun toplam suresi yazilir ama olay maskesinden bagimsizdir. Boylece ne ayni kosunun birim sureleri ne de
    iki kosunun toplamlari arasindaki fark olay suresini verir."""
    sonuc = {}
    for ad, maske in (("hepsi", [True] * len(_IZGARA)), ("hic", [False] * len(_IZGARA))):
        _maliyetli_dunya(monkeypatch, maske)
        sonuc[(ad, "olay+K1")] = ek.sembol_isi("X", _ayar(roller=("olay", "K1")))
        _maliyetli_dunya(monkeypatch, maske)
        sonuc[(ad, "K1")] = ek.sembol_isi("X", _ayar(roller=("K1",)))
    assert sonuc[("hepsi", "olay+K1")] == sonuc[("hic", "olay+K1")]
    assert all(s["sure_s"] == "" for s in sonuc[("hepsi", "olay+K1")])
    toplam_k1 = [s["sure_s"] for s in sonuc[("hepsi", "K1")] if s["rol"] == "TOPLAM_SURE"]
    assert len(toplam_k1) == 1 and isinstance(toplam_k1[0], float) and toplam_k1[0] > 0
    assert sonuc[("hepsi", "K1")] == sonuc[("hic", "K1")]


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
