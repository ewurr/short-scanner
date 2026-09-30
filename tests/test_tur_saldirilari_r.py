"""Onay kaydi kapanisinin son turu: sizinti testcisi R saldirilari.

Basarili saldiri `xfail(strict=True)` ile isaretlidir; govde GUVENLI davranisi iddia eder. Gercek ONAY_KAYDI.md,
gercek depo, gercek `cache/` ve ag kullanilmaz.
"""

from __future__ import annotations

import threading

import pandas as pd
import pytest

import config
from conftest import sahte_4h
from data import binance_vision as bv
from data import split
from tarama_yardimcisi import HAM_ERISIM_DESENI, ONAY_ATLATMA_DESENI, ONBELLEK_DESENI, ihlaller

B_SEMBOLU = "BTCUSDT"
_BEKLENEN = (AssertionError, pytest.fail.Exception)


def _a_sembolu() -> str:
    tablo = split.split_oku()
    tek = tablo.loc[(tablo["grup"] == "A") & (tablo["sembol"] == tablo["varlik_anahtari"]), "sembol"]
    return str(tek.iloc[0])


@pytest.fixture
def onbellek(tmp_path, monkeypatch):
    kok = tmp_path / "cache"
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", kok)
    return kok


def _b_dosyasi(kok):
    yol = kok / "klines" / B_SEMBOLU / "4h" / "2021-01.parquet"
    yol.parent.mkdir(parents=True, exist_ok=True)
    sahte_4h("2021-01-01", 12).to_parquet(yol, index=False)
    return yol


@pytest.mark.xfail(strict=True, raises=_BEKLENEN,
                   reason="R1: izin surec geneli sayac; baska is parcacigindaki izin ana parcacigi da yetkilendirir")
def test_baska_is_parcacigindaki_izin_ana_parcacigin_onay_okumasini_acmaz(onbellek):
    """SALDIRI: T1 `onay_verisi_izni` icinde bekler; ana parcacik bu sirada B sembolunun onbellegini
    `bv.onbellekten_oku` ile okur. GUVENLI: `OnayVerisiKorumasi` (izin okuyan parcacikla sinirli olmali;
    CLAUDE.md §3.2-3.3)."""
    yol = _b_dosyasi(onbellek)
    girdi, cik = threading.Event(), threading.Event()

    def is_():
        with bv.onay_verisi_izni("t1"):
            girdi.set()
            cik.wait(timeout=10)

    t = threading.Thread(target=is_)
    t.start()
    try:
        assert girdi.wait(timeout=10)
        try:
            veri = bv.onbellekten_oku(yol)
        except bv.OnayVerisiKorumasi:
            return  # guvenli
        pytest.fail(f"ana parcacik baska parcacigin izniyle B verisi okudu: {len(veri)} satir")
    finally:
        cik.set()
        t.join(timeout=10)


@pytest.mark.xfail(strict=True, raises=_BEKLENEN,
                   reason="R2: <X>SETTLED anahtari A grubuna dusuyor; temel sembol B ise indirme denetimi gecer")
def test_b_grubu_temel_sembolun_settled_zipi_izin_disinda_indirilemez(monkeypatch):
    """SALDIRI: `varlik_anahtari("<X>SETTLED")` A grubunda, temel `<X>` B grubunda olan X icin
    `zip_indir(...<X>SETTLED...2021-01.zip)` cagrilir (`_iste` sahte). GUVENLI: `OnayVerisiKorumasi`
    (B grubu varligin SETTLED verisi de onay verisidir; on-kayit §2 rev.8, §3)."""
    tablo = split.split_oku()
    x = None
    for s in tablo["sembol"]:
        if split.grup(split.varlik_anahtari(s)) != "B":
            continue
        if split.grup(split.varlik_anahtari(f"{s}SETTLED")) == "A":
            x = s
            break
    if x is None:
        pytest.skip("uygun X bulunamadi (SETTLED anahtari B'de kaliyor)")

    class Sahte:
        content = b"PK"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(bv, "_iste", lambda *a, **k: Sahte())
    anahtar = f"data/futures/um/monthly/klines/{x}SETTLED/4h/{x}SETTLED-4h-2021-01.zip"
    try:
        bv.zip_indir(anahtar, checksum_dogrula=False)
    except bv.OnayVerisiKorumasi:
        return
    pytest.fail(f"{x}SETTLED (temel B grubu) izin disinda indirildi")


def _tara(tmp_path, metin, desen):
    (tmp_path / "study").mkdir()
    (tmp_path / "study" / "k.py").write_text(metin, encoding="utf-8")
    return ihlaller(desen, kok=tmp_path)


@pytest.mark.xfail(strict=True, raises=_BEKLENEN, reason="R3a: dogrudan requests.get(data.binance.vision) taranmiyor")
def test_analiz_kodunda_dogrudan_vision_istegi_taramaya_takilir(tmp_path):
    """SALDIRI: analiz kodu `requests.get("https://data.binance.vision/...")` ile kapiyi atlar. GUVENLI: ONBELLEK_DESENI
    ya da HAM_ERISIM_DESENI yakalar (CLAUDE.md §3.3)."""
    metin = 'import requests\nrequests.get("https://data.binance.vision/data/futures/um/monthly/klines/BTCUSDT/4h/x.zip")\n'
    assert _tara(tmp_path, metin, ONBELLEK_DESENI) or ihlaller(HAM_ERISIM_DESENI, kok=tmp_path)


@pytest.mark.xfail(strict=True, raises=_BEKLENEN, reason="R3b: `bv._iste(...)` taranmiyor (desende `_iste` yok)")
def test_analiz_kodunda_bv_iste_cagrisi_taramaya_takilir(tmp_path):
    """SALDIRI: analiz kodu `bv._iste(url)` ile agi dogrudan cagirir (`bv` takma adi `binance_` onekini tasimaz).
    GUVENLI: ONBELLEK_DESENI ya da HAM_ERISIM_DESENI yakalar."""
    metin = "bv._iste('https://x/y.zip')\n"
    assert _tara(tmp_path, metin, ONBELLEK_DESENI) or ihlaller(HAM_ERISIM_DESENI, kok=tmp_path)


@pytest.mark.xfail(strict=True, raises=_BEKLENEN, reason="R3c: fapi.binance.com metni taranmiyor")
def test_analiz_kodunda_fapi_adresi_taramaya_takilir(tmp_path):
    """SALDIRI: analiz kodu `fapi.binance.com` uzerinden canli/tarihsel veriyi kapi disi ceker. GUVENLI: desen yakalar."""
    metin = 'URL = "https://fapi.binance.com/fapi/v1/klines"\n'
    assert _tara(tmp_path, metin, ONBELLEK_DESENI) or ihlaller(HAM_ERISIM_DESENI, kok=tmp_path)


@pytest.mark.xfail(strict=True, raises=_BEKLENEN,
                   reason="R4: varsayilan uzanti yalnizca .py; .ipynb icindeki vars(split)/sys.modules taranmiyor")
def test_ipynb_icindeki_vars_split_varsayilan_taramayla_yakalanir(tmp_path):
    """SALDIRI: `vars(split)` ve `sys.modules` .ipynb defterine yazilir; testlerde kullanilan varsayilan uzantiyla
    (`ihlaller(desen, kok=...)`, yalnizca .py) taranir. GUVENLI: yakalanir (defter de analiz kodudur)."""
    (tmp_path / "study").mkdir()
    (tmp_path / "study" / "k.ipynb").write_text(
        '{"cells":[{"source":["vars(split)[\\"_AKTIF_KOSU\\"] = 1\\n","import sys; sys.modules"]}]}', encoding="utf-8")
    assert ihlaller(ONAY_ATLATMA_DESENI, kok=tmp_path)


# Ana oturum ekledi: testci bu saldiriyi savusturulur tahmin etmisti; kosuda basarili cikti (B verisi dondu). Govde
# degismedi; dosyadaki uzlasima gore basarili saldiri olarak isaretlendi (denetci OK4 D-C3 ile ayni bulgu).
@pytest.mark.xfail(strict=True, raises=(AssertionError, pytest.fail.Exception),
                   reason="R5: split.yukle(mum_yukleyici=...) verilen fonksiyonu izinle calistirir; B verisi doner")
def test_kume_kapisindan_gecen_yukle_b_onbellegini_mum_yukleyiciyle_okutamaz(onbellek):
    """SALDIRI: `split.yukle(A, "4h", "KESIF", mum_yukleyici=...)` ozel yukleyicisi izin icinde B sembolunun
    onbellegini `bv.onbellekten_oku` ile okur. GUVENLI: `OnayVerisiKorumasi` ya da bos cerceve (B verisi donmez)."""
    _b_dosyasi(onbellek)
    yol = onbellek / "klines" / B_SEMBOLU / "4h" / "2021-01.parquet"

    def yukleyici(_s, _b):
        return bv.onbellekten_oku(yol)

    try:
        sonuc = split.yukle(_a_sembolu(), "4h", "KESIF", mum_yukleyici=yukleyici)
    except bv.OnayVerisiKorumasi:
        return
    if isinstance(sonuc, pd.DataFrame):
        assert sonuc.empty, f"B grubu verisi KESIF cagrisindan dondu: {len(sonuc)} satir"


@pytest.mark.xfail(strict=True, raises=_BEKLENEN,
                   reason="R6: semasiz ve file:// adresleri beklenen adrese iner; yerel yol da kabul ediliyor")
@pytest.mark.parametrize("adres", ["github.com/ewurr/short-scanner", "file://github.com/ewurr/short-scanner"])
def test_semasiz_ve_file_adresi_beklenen_uzak_adrese_inmez(adres):
    """SALDIRI: `github.com/ewurr/short-scanner` (yerel goreli yol) ve `file://github.com/...` adresleri
    `uzak_adresi_normal` ile `config.UZAK_DEPO_ADRESI`ne indirgenir; `origin` yerel bir dizine isaret ederken
    `_uzak_adresi_denetle` gecer. GUVENLI: inmez (bunlar yerel yoldur, ag adresi degil)."""
    assert split.uzak_adresi_normal(adres) != config.UZAK_DEPO_ADRESI.lower()
