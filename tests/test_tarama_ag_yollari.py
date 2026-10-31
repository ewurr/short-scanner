"""Tarama ve dondurulmus liste kopyasi (RESULTS §14.41; sizinti S-6, S-7, S-13, denetci D-C1).

Yalnizca sentetik metin ve gecici onbellek kullanilir; aga cikilmaz.
"""

from __future__ import annotations

import json

import pytest

import config
from data import binance_vision as bv
from data import split
from onay_yardimcisi import gecici_kayit, kosu
from tarama_yardimcisi import ONBELLEK_DESENI, ONBELLEK_UZANTILARI, ihlaller

A_SEMBOL = "SOLUSDT"


def _anahtar(sembol, ay):
    return f"{bv.MUM_ONEKI}/{sembol}/{config.BAR_4H}/{sembol}-{config.BAR_4H}-{ay}.zip"


def _yakalar(tmp_path, metin) -> bool:
    (tmp_path / "study").mkdir()
    (tmp_path / "study" / "sahte.py").write_text(metin, encoding="utf-8")
    return bool(ihlaller(ONBELLEK_DESENI, kok=tmp_path, uzantilar=ONBELLEK_UZANTILARI))


@pytest.mark.parametrize("metin", [
    "klines.bv.mum_dosyalari(s, '4h')\n",
    "funding.bv.funding_dosyalari(s)\n",
    "from data.klines import bv\n",
    "from data import klines as k\nk.bv._iste(u)\n",
    "bv.tum_sembol_dizinleri()\n",
    "from data.binance_vision import _listele\n",
    "klines.mumlari_yukle(s, '4h', 'KESIF', yenile=True)\n",
    "funding.funding_yukle(s, 'KESIF', yenile = True)\n",
    "secenek = {'yenile': True}\n",
    "klines.mumlari_yukle(s, '4h', 'KESIF', yenile=bayrak)\n",
    "klines.birincil_gunluk_indir(s, 'KESIF')\n",
    "klines.ay_indir(s, '4h', '2021-01')\n",
    "listeyi_dondur()\n",
    "manifest_kur()\n",
    "_donuk_oku()\n",
    "_KOSU_AGSIZ['sayac'] = 0\n",
    "os.environ.pop('SHORT_LAB_KOSU_AGSIZ')\n",
])
def test_ag_yolu_analiz_kodunda_yakalanir(tmp_path, metin):
    assert _yakalar(tmp_path, metin)


@pytest.mark.parametrize("metin", [
    "klines.mumlari_yukle(s, '4h', 'KESIF')\n",
    "klines.mumlari_yukle(s, '4h', 'KESIF', yenile=False)\n",
    "funding.funding_yukle(s, 'KESIF')\n",
    "abv = 1\nbvx = 2\n",
    "yenilendi = True\n",
])
def test_kapili_yukleyici_yanlis_alarm_vermez(tmp_path, metin):
    assert not _yakalar(tmp_path, metin)


def test_mevcut_analiz_kodu_temiz():
    """`config.py` onbellek dizinini tanimlayan yerdir (`ONBELLEK_DIZINI`), analiz kodu degildir."""
    assert [y for y in ihlaller(ONBELLEK_DESENI, uzantilar=ONBELLEK_UZANTILARI) if y != "config.py"] == []


# --- Dondurulmus liste ----------------------------------------------------------------------------


@pytest.fixture
def liste(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", tmp_path / "onbellek")

    def yaz(mum: dict) -> None:
        yol = bv.donuk_liste_yolu()
        yol.parent.mkdir(parents=True, exist_ok=True)
        icerik = {"mum": {s: {config.BAR_4H: [_anahtar(s, a) for a in aylar]} for s, aylar in mum.items()},
                  "funding": {}}
        yol.write_text(json.dumps(icerik), encoding="utf-8")
        bv.donuk_bellek_temizle()

    return yaz


def test_donuk_liste_izinsiz_c2_ayi_varsa_reddedilir(liste):
    liste({A_SEMBOL: ["2021-01", "2025-09"]})
    with pytest.raises(bv.OnayVerisiKorumasi):
        bv._donuk_liste()


def test_donuk_liste_izinsiz_b_sembolu_varsa_reddedilir(liste):
    tablo = split.split_oku()
    liste({str(tablo.loc[tablo["grup"] == "B", "sembol"].iloc[0]): ["2021-01"]})
    with pytest.raises(bv.OnayVerisiKorumasi):
        bv._donuk_liste()


def test_donuk_liste_izinle_tam_ve_derin_kopya_doner(liste):
    liste({A_SEMBOL: ["2021-01", "2025-09"]})
    with bv.onay_verisi_izni("test"):
        ilk = bv._donuk_liste()
        assert ilk["mum"][A_SEMBOL][config.BAR_4H] == [_anahtar(A_SEMBOL, "2021-01"), _anahtar(A_SEMBOL, "2025-09")]
        ilk["mum"][A_SEMBOL][config.BAR_4H].clear()  # ic liste de kopya olmali
        assert len(bv._donuk_liste()["mum"][A_SEMBOL][config.BAR_4H]) == 2


def test_donuk_bellek_kosu_acilis_ve_kapanisinda_temizlenir(liste, tmp_path):
    """D-C1: kopya acilis ve kapanista duser."""
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    bv._DONUK_BELLEK.update(kimlik=("x",), veri={"mum": {}})
    with kosu("H2", "C1"):
        assert bv._DONUK_BELLEK == {}
        bv._DONUK_BELLEK.update(kimlik=("y",), veri={"mum": {}})
    assert bv._DONUK_BELLEK == {}


def test_donuk_bellek_kosu_hatayla_kapaninca_da_temizlenir(liste, tmp_path):
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    with pytest.raises(ZeroDivisionError):
        with kosu("H2", "C1"):
            bv._DONUK_BELLEK.update(kimlik=("y",), veri={"mum": {}})
            raise ZeroDivisionError
    assert bv._DONUK_BELLEK == {}
