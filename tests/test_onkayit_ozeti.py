"""D-B2 (RESULTS §14.51, F2-0): kesif ve onay kosusu acilista manifest ozetini on-kayittaki degerle karsilastirir.

On-kayit §3 rev.14 "Kuruluş" iki degeri sabitler: manifest dosyasinin SHA256'si ve onay katmaninin birlesik SHA256'si.
Kodda tek yerleri `data/onbellek_manifest.py`'dir (`ONKAYIT_MANIFEST_SHA256`, `ONKAYIT_ONAY_SHA256`).

Testler gecici kok ve sahte manifest kullanir; gercek `cache/`a ve kilitli dosyalara dokunmaz, aga cikmaz. Sahte
manifest on-kayittaki baytlari tasimadigi icin beklenen degerler `_test_onkayit_ozeti_ayarla` ile bu teste ozgu verilir
(pytest disinda her zaman on-kayittaki sabitlerdir; bunu ayri surecteki test gosterir).
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

import config
from conftest import sahte_4h
from data import binance_vision as bv
from data import kume_bellegi, onbellek_manifest as mf
from data import split
from onay_yardimcisi import gecici_kayit, kosu

A_SEMBOL = "SOLUSDT"
AY_ONCESI = "2021-01"
C2_AYI = "2025-09"


def _b_sembolu() -> str:
    tablo = split.split_oku()
    return str(tablo.loc[tablo["grup"] == "B", "sembol"].iloc[0])


def _anahtar(sembol, ay):
    return f"{bv.MUM_ONEKI}/{sembol}/{config.BAR_4H}/{sembol}-{config.BAR_4H}-{ay}.zip"


def _sha(yol) -> str:
    return hashlib.sha256(Path(yol).read_bytes()).hexdigest()


@pytest.fixture
def onbellek(monkeypatch, tmp_path):
    """Kesif: A, C2 oncesi. Onay: A, C2 ayi ve B, C2 oncesi. Manifest kurulu; onay kaydi gecici (sahte git kipi)."""
    kok = tmp_path / "onbellek"
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", kok)
    mf._test_manifest_ayarla(tmp_path / "onbellek_manifest.csv")
    bv.donuk_bellek_temizle()
    kume_bellegi.temizle()
    b = _b_sembolu()
    for sembol, ay, zaman in [(A_SEMBOL, AY_ONCESI, "2021-01-01 00:00"), (A_SEMBOL, C2_AYI, "2025-09-01 00:00"),
                              (b, AY_ONCESI, "2021-01-01 00:00")]:
        sahte_4h(zaman, 12).to_parquet(bv.onbellek_yolu("klines", sembol, config.BAR_4H, f"{ay}.parquet"), index=False)
    yol = bv.donuk_liste_yolu()
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps({"mum": {A_SEMBOL: {config.BAR_4H: [_anahtar(A_SEMBOL, AY_ONCESI), _anahtar(A_SEMBOL, C2_AYI)]},
                                       b: {config.BAR_4H: [_anahtar(b, AY_ONCESI)]}},
                               "funding": {}}), encoding="utf-8")
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    mf.manifest_kur()
    yield kok
    bv.donuk_bellek_temizle()
    kume_bellegi.temizle()


def _gercek_ozetler() -> tuple[str, str]:
    """Bu testin sahte manifestinin (manifest SHA256, onay_ozeti satiri) degerleri."""
    return _sha(mf._etkin_yol()), mf._manifest().onay_sha256


def _dogru_ayarla() -> tuple[str, str]:
    ozetler = _gercek_ozetler()
    mf._test_onkayit_ozeti_ayarla(*ozetler)
    return ozetler


def _kayit_durumu(tmp_path):
    yol = tmp_path / "ONAY_KAYDI.md"
    return yol.read_bytes() if yol.exists() else None


def _kesif_acilmaz():
    with pytest.raises(mf.OnKayitOzetiUyusmazligi) as hata:
        with split.kesif_kosusu():
            pytest.fail("kesif kosusu acildi")
    assert bv._KOSU_AGSIZ["sayac"] == 0
    assert not split.kesif_kosusu_acik()
    return hata.value


def _onay_acilmaz(tmp_path, monkeypatch):
    """Onay kosusu acilmaz; kayda satir yazilmaz; `tam` dogrulamasina hic gelinmez (ozet denetimi ondan once)."""
    once = _kayit_durumu(tmp_path)
    dogrulanan: list = []
    asil = mf.manifest_dogrula
    monkeypatch.setattr(mf, "manifest_dogrula", lambda **k: (dogrulanan.append(k), asil(**k))[1])
    with pytest.raises(mf.OnKayitOzetiUyusmazligi) as hata:
        with kosu("H2", "C1"):
            pytest.fail("onay kosusu acildi")
    assert _kayit_durumu(tmp_path) == once, "ONAY_KAYDI'na satir yazildi"
    assert ("H2", "C1") not in split.harcanan_ciftler()
    assert split.aktif_onay_kosusu() is None
    assert bv._KOSU_AGSIZ["sayac"] == 0
    assert dogrulanan == [], "ozet denetimi `tam` dogrulamasindan once calismadi"
    return hata.value


# --- Sabitler ve on-kayit --------------------------------------------------------------------------------------------


def test_iki_deger_on_kayit_metninde_birebir_gecer():
    metin = (config.KOK / "PREREGISTRATION.md").read_text(encoding="utf-8")
    for deger in (mf.ONKAYIT_MANIFEST_SHA256, mf.ONKAYIT_ONAY_SHA256):
        assert re.fullmatch(r"[0-9a-f]{64}", deger)
        assert f"`{deger}`" in metin
    assert mf.ONKAYIT_MANIFEST_SHA256 == "8de2bb354e0b852856960b43463eaf24598b487fdec8a55d384ee9a307e15eec"
    assert mf.ONKAYIT_ONAY_SHA256 == "7611f6f2fe138a3f518ba7f879d697aef1eb6a8bcb6fbac1647125413f227f24"


def test_iki_deger_depo_kodunda_tek_yerde_yazili():
    """Testler disindaki bütün `.py` dosyalarinda iki deger yalnizca `data/onbellek_manifest.py`'de, birer kez."""
    bulunan: dict[str, list[str]] = {mf.ONKAYIT_MANIFEST_SHA256: [], mf.ONKAYIT_ONAY_SHA256: []}
    for yol in config.KOK.rglob("*.py"):
        goreli = yol.relative_to(config.KOK).as_posix()
        if goreli.split("/")[0] in {"tests", "cache", ".git", ".venv", "venv"}:
            continue
        metin = yol.read_text(encoding="utf-8", errors="replace")
        for deger in bulunan:
            bulunan[deger] += [goreli] * metin.count(deger)
    for deger, yerler in bulunan.items():
        assert yerler == ["data/onbellek_manifest.py"], (deger[:8], yerler)


def test_pytest_disinda_beklenen_degerler_on_kayittaki_sabitler_ve_test_ayari_reddedilir():
    betik = ("import sys; sys.path.insert(0, sys.argv[1])\n"
             "from data import onbellek_manifest as mf\n"
             "print(mf._beklenen_ozetler() == (mf.ONKAYIT_MANIFEST_SHA256, mf.ONKAYIT_ONAY_SHA256))\n"
             "try:\n    mf._test_onkayit_ozeti_ayarla('0' * 64, '0' * 64)\n"
             "except PermissionError:\n    print('red')\n"
             "print(mf._beklenen_ozetler() == (mf.ONKAYIT_MANIFEST_SHA256, mf.ONKAYIT_ONAY_SHA256))\n")
    cikti = subprocess.run([sys.executable, "-B", "-c", betik, str(config.KOK)], capture_output=True, text=True,
                           check=True, timeout=120)
    assert cikti.stdout.split() == ["True", "red", "True"]


def test_test_ayari_yalnizca_kendi_testinde_gecerli():
    """Bir testin ayari baska teste tasinmaz: bu testte ayar yok, beklenen deger yok (denetim calismaz)."""
    assert mf._beklenen_ozetler() is None


# --- Degistirilmis manifest ------------------------------------------------------------------------------------------


def test_degistirilmis_manifestle_kesif_kosusu_acilmaz(onbellek):
    _dogru_ayarla()
    yol = mf._etkin_yol()
    yol.write_bytes(yol.read_bytes() + b"\n")
    hata = _kesif_acilmaz()
    assert "on-kayit" in str(hata)


def test_degistirilmis_manifestle_onay_kosusu_acilmaz_ve_kayda_satir_yazilmaz(onbellek, tmp_path, monkeypatch):
    _dogru_ayarla()
    yol = mf._etkin_yol()
    yol.write_bytes(yol.read_bytes() + b"\n")
    _onay_acilmaz(tmp_path, monkeypatch)


def test_onay_ozeti_satiri_degistirilmis_manifestle_onay_kosusu_acilmaz(onbellek, tmp_path, monkeypatch):
    """Manifest dosyasinin ozeti beklenenle ayni (beklenen degistirilmis manifestin ozeti) ama `onay_ozeti` satiri
    on-kayittaki birlesik degerle ayni degil."""
    yol = mf._etkin_yol()
    _, onay_gercek = _gercek_ozetler()
    sahte_onay = hashlib.sha256(b"baska onay katmani").hexdigest()
    yol.write_bytes(yol.read_bytes().replace(onay_gercek.encode(), sahte_onay.encode()))
    mf.bellek_temizle()
    mf._test_onkayit_ozeti_ayarla(_sha(yol), onay_gercek)
    hata = _onay_acilmaz(tmp_path, monkeypatch)
    assert "onay_ozeti" in str(hata)
    assert onay_gercek not in str(hata) and sahte_onay not in str(hata)


def test_ayrinti_listesi_baytlari_on_kayittaki_degerle_tutmazsa_onay_kosusu_acilmaz(onbellek, tmp_path, monkeypatch):
    """Manifest ve `onay_ozeti` satiri beklenenle ayni; ayrinti listesinin baytlari degil."""
    _dogru_ayarla()
    ayrinti = mf.onay_ayrinti_yolu()
    ayrinti.write_bytes(ayrinti.read_bytes() + b"\n")
    hata = _onay_acilmaz(tmp_path, monkeypatch)
    assert "ayrinti" in str(hata)


def test_on_kayittaki_deger_farkliysa_dogru_manifestle_de_kosular_acilmaz(onbellek, tmp_path, monkeypatch):
    """Beklenen deger on-kayittaki sabitlerdir: sahte manifestin baytlari onlarla ayni olmadigi icin acilmaz."""
    mf._test_onkayit_ozeti_ayarla(mf.ONKAYIT_MANIFEST_SHA256, mf.ONKAYIT_ONAY_SHA256)
    assert _sha(mf._etkin_yol()) != mf.ONKAYIT_MANIFEST_SHA256
    _kesif_acilmaz()
    _onay_acilmaz(tmp_path, monkeypatch)


# --- Dogru manifest --------------------------------------------------------------------------------------------------


def test_dogru_manifestle_kesif_kosusu_acilir(onbellek):
    manifest_sha, _ = _dogru_ayarla()
    with split.kesif_kosusu() as kayit:
        assert split.kesif_kosusu_acik()
    assert kayit.manifest_sha256 in (None, manifest_sha)


def test_dogru_manifestle_onay_kosusu_acilir(onbellek, tmp_path):
    _dogru_ayarla()
    with kosu("H2", "C1"):
        assert split.aktif_onay_kosusu() is not None
    assert ("H2", "C1") in split.harcanan_ciftler()


# --- manifest-kur --uzerine-yaz --------------------------------------------------------------------------------------


def test_yeniden_kurulan_manifest_hicbir_kosuyu_acamaz(onbellek, tmp_path, monkeypatch):
    """`manifest-kur --uzerine-yaz` davranisi degismez (kurulum basarili, onay satiri tasinir); ama baska bir kesif
    verisini baglayan yeni manifest on-kayittaki ozetle tutmadigi icin ne kesif ne onay kosusu acilir."""
    ilk_manifest, ilk_onay = _dogru_ayarla()
    sahte_4h("2021-01-01 00:00", 13).to_parquet(bv.onbellek_yolu("klines", A_SEMBOL, config.BAR_4H,
                                                                 f"{AY_ONCESI}.parquet"), index=False)
    with pytest.raises(mf.ManifestUyusmazligi):  # kontrol: eski manifest yeni veriyi dogrulamaz
        mf.manifest_dogrula(katman="kesif")
    sonuc = mf.manifest_kur(uzerine_yaz=True)
    assert sonuc["manifest_sha256"] != ilk_manifest
    assert sonuc["birlesik_sha256"] == ilk_onay  # onay satiri oldugu gibi tasindi
    assert mf.manifest_dogrula(katman="kesif")["kesif_satir"] == 1  # yeni manifest kendi icinde tutarli
    hata = _kesif_acilmaz()
    assert sonuc["manifest_sha256"] in str(hata)
    _onay_acilmaz(tmp_path, monkeypatch)
