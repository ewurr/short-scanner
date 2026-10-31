"""Iki katmanli onbellek manifesti (on-kayit §3 rev.13; RESULTS §14.41, denetci D-B2).

Depodaki gercek manifest yalnizca metin olarak okunur; onbellek dosyasi acilmaz. Geri kalan testler gecici onbellek ve
gecici manifest kullanir; aga cikilmaz.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

import config
from conftest import sahte_4h
from data import binance_vision as bv
from data import funding as funding_modulu
from data import klines, onbellek_manifest as mf
from data import split
from onay_yardimcisi import gecici_depo, gecici_kayit, git, kosu

A_SEMBOL = "SOLUSDT"
AY_ONCESI = "2021-01"
C2_AYI = "2025-09"

_ACILAN: list | None = None


def _kanca(olay, argumanlar):
    if olay == "open" and _ACILAN is not None:
        _ACILAN.append(str(argumanlar[0]))


sys.addaudithook(_kanca)  # io.open, os.open, Path.open: yorumlayicida acilan her dosya


def _b_sembolu() -> str:
    tablo = split.split_oku()
    return str(tablo.loc[tablo["grup"] == "B", "sembol"].iloc[0])


def _anahtar(sembol, ay):
    return f"{bv.MUM_ONEKI}/{sembol}/{config.BAR_4H}/{sembol}-{config.BAR_4H}-{ay}.zip"


@pytest.fixture
def onbellek(monkeypatch, tmp_path):
    """Keşif: A, C2 oncesi (mum, funding, birincil). Onay: A, C2 ayi ve B, C2 oncesi. Gercek parquet, liste dahil."""
    kok = tmp_path / "onbellek"
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", kok)
    mf._test_manifest_ayarla(tmp_path / "onbellek_manifest.csv")
    bv.donuk_bellek_temizle()
    b = _b_sembolu()
    for sembol, ay, zaman in [(A_SEMBOL, AY_ONCESI, "2021-01-01 00:00"), (A_SEMBOL, C2_AYI, "2025-09-01 00:00"),
                              (b, AY_ONCESI, "2021-01-01 00:00")]:
        sahte_4h(zaman, 12).to_parquet(bv.onbellek_yolu("klines", sembol, config.BAR_4H, f"{ay}.parquet"), index=False)
    bv.onbellek_yolu("funding", A_SEMBOL, f"{AY_ONCESI}.parquet").write_bytes(b"funding kesif")
    bv.onbellek_yolu("klines_birincil_1d", A_SEMBOL, f"{AY_ONCESI}.parquet").write_bytes(b"birincil kesif")
    yol = bv.donuk_liste_yolu()
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps({"mum": {A_SEMBOL: {config.BAR_4H: [_anahtar(A_SEMBOL, AY_ONCESI), _anahtar(A_SEMBOL, C2_AYI)]},
                                       b: {config.BAR_4H: [_anahtar(b, AY_ONCESI)]}},
                               "funding": {}}), encoding="utf-8")
    yield kok
    bv.donuk_bellek_temizle()


def _kesif_yolu(kok):
    return kok / "klines" / A_SEMBOL / config.BAR_4H / f"{AY_ONCESI}.parquet"


def _onay_yolu(kok):
    return kok / "klines" / A_SEMBOL / config.BAR_4H / f"{C2_AYI}.parquet"


def _tam():
    with bv.onay_verisi_izni("test"):
        return mf.manifest_dogrula(katman="tam")


def _bayt_cevir(yol):
    govde = bytearray(yol.read_bytes())
    govde[len(govde) // 2] ^= 0xFF
    yol.write_bytes(bytes(govde))


# --- Depodaki gercek manifest --------------------------------------------------------------------------------------


def _depodaki_satirlar():
    metin = mf.MANIFEST_YOLU.read_text(encoding="utf-8")
    return metin, list(csv.DictReader(io.StringIO(metin)))


def test_depodaki_manifest_onay_dosyasi_yolu_ya_da_boyu_tasimaz():
    metin, satirlar = _depodaki_satirlar()
    assert [s["katman"] for s in satirlar].count("onay_ozeti") == 1
    assert [s["katman"] for s in satirlar].count("liste") == 1
    tablo = split.split_oku()
    b_grubu = set(tablo.loc[tablo["grup"] == "B", "sembol"])
    c2_basi = pd.Period(config.C2_BASI.strftime("%Y-%m"), freq="M")
    for satir in satirlar:
        if satir["katman"] == "kesif":
            parca = satir["yol"].split("/")
            assert parca[1] not in b_grubu and pd.Period(Path(parca[-1]).stem, freq="M") < c2_basi
            assert not bv.onay_verisi_mi(parca[1], Path(parca[-1]).stem)
        else:
            assert satir["boy"] == "", "boy yalnizca kesif satirinda"
    assert not any(pd.Period(a, freq="M") >= c2_basi for a in re.findall(r"\b20\d\d-\d\d\b", metin))
    ozet = next(s for s in satirlar if s["katman"] == "onay_ozeti")
    assert ozet["yol"] == "" and int(ozet["dosya_sayisi"]) > 0 and re.fullmatch(r"[0-9a-f]{64}", ozet["sha256"])


def test_depodaki_manifest_sirali_ve_lf():
    ham = mf.MANIFEST_YOLU.read_bytes()
    _, satirlar = _depodaki_satirlar()
    assert b"\r" not in ham
    yollar = [s["yol"] for s in satirlar if s["katman"] != "onay_ozeti"]
    assert yollar == sorted(yollar)
    assert satirlar[-1]["katman"] == "onay_ozeti"


def test_onay_ayrinti_listesi_git_disinda():
    assert subprocess.run(["git", "check-ignore", "-q", "cache/manifest/onay_ayrintisi.tsv"], cwd=config.KOK).returncode == 0


# --- Kurulum ---------------------------------------------------------------------------------------------------------


def test_kurulum_yalnizca_sayi_ve_ozet_dondurur_ve_parquet_acmaz(onbellek, monkeypatch):
    monkeypatch.setattr(pd, "read_parquet", lambda *_a, **_k: pytest.fail("parquet acildi"))
    sonuc = mf.manifest_kur()
    assert all(type(d) in (int, float, str) for d in sonuc.values())
    assert sonuc["kesif_satir"] == 3 and sonuc["onay_dosya"] == 2
    assert all(type(d) in (int, float, str) for d in mf.manifest_dogrula(katman="kesif").values())
    assert all(type(d) in (int, float, str) for d in _tam().values())


def test_manifest_metni_onay_dosyasi_tasimaz(onbellek):
    hedef = _onay_yolu(onbellek)
    hedef.write_bytes(hedef.read_bytes() + b"ayirt edici boy")  # sahte cerceveler ayni boyda; bu satir yalnizca ozetlenir
    sonuc = mf.manifest_kur()
    metin = mf._etkin_yol().read_text(encoding="utf-8")
    assert C2_AYI not in metin and _b_sembolu() not in metin
    assert sonuc["birlesik_sha256"] in metin
    assert str(hedef.stat().st_size) not in re.sub(r"[0-9a-f]{64}", "", metin)


def test_birlesik_ozet_kanonik_metnin_ozetidir(onbellek):
    import hashlib

    sonuc = mf.manifest_kur()
    govde = mf.onay_ayrinti_yolu().read_bytes()
    assert hashlib.sha256(govde).hexdigest() == sonuc["birlesik_sha256"]
    satirlar = govde.decode("utf-8").split("\n")
    assert satirlar[-1] == "" and all(len(s.split("\t")) == 3 for s in satirlar[:-1])
    assert [s.split("\t")[0] for s in satirlar[:-1]] == sorted(s.split("\t")[0] for s in satirlar[:-1])
    assert b"\r" not in govde


def test_uzerine_yaz_olmadan_manifest_ya_da_liste_degismez(onbellek):
    mf.manifest_kur()
    manifest_once = mf._etkin_yol().read_bytes()
    ayrinti_once = mf.onay_ayrinti_yolu().read_bytes()
    with pytest.raises(FileExistsError):
        mf.manifest_kur()
    assert mf._etkin_yol().read_bytes() == manifest_once and mf.onay_ayrinti_yolu().read_bytes() == ayrinti_once
    with pytest.raises(FileExistsError):
        bv.listeyi_dondur()


def test_ayrinti_listesi_varken_manifest_silinse_de_uzerine_yazilmaz(onbellek):
    mf.manifest_kur()
    mf._etkin_yol().unlink()
    with pytest.raises(FileExistsError):
        mf.manifest_kur()


def test_uzerine_yaz_kesif_katmanini_yeniler_onay_satirini_tasir_onay_dosyasi_acmaz(onbellek):
    global _ACILAN
    ilk = mf.manifest_kur()
    _bayt_cevir(_kesif_yolu(onbellek))
    _ACILAN = []
    try:
        sonuc = mf.manifest_kur(uzerine_yaz=True)
        acilan = list(_ACILAN)
    finally:
        _ACILAN = None
    assert sonuc["birlesik_sha256"] == ilk["birlesik_sha256"] and sonuc["onay_dosya"] == ilk["onay_dosya"]
    assert sonuc["manifest_sha256"] != ilk["manifest_sha256"]
    assert not [a for a in acilan if C2_AYI in a or _b_sembolu() in a or "onay_ayrintisi" in a]
    mf.manifest_dogrula(katman="kesif")


def test_onay_katmani_kosu_disinda_yeniden_kurulamaz(onbellek):
    mf.manifest_kur()
    with pytest.raises(mf.OnayKatmaniKilitli):
        mf.manifest_kur(uzerine_yaz=True, onay_katmani=True)
    with bv.onay_verisi_izni("test"), pytest.raises(mf.OnayKatmaniKilitli):
        mf.manifest_kur(uzerine_yaz=True, onay_katmani=True)


def test_onay_katmani_acik_kosuda_yeniden_kurulur(onbellek, tmp_path):
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    ilk = mf.manifest_kur()
    with kosu("H2", "C1"):
        sonuc = mf.manifest_kur(uzerine_yaz=True, onay_katmani=True)
    assert sonuc["birlesik_sha256"] == ilk["birlesik_sha256"]


def test_manifest_silinip_uzerine_yaz_ile_onay_katmani_kurulamaz(onbellek):
    mf.manifest_kur()
    mf._etkin_yol().unlink()
    with pytest.raises(mf.OnayKatmaniKilitli):
        mf.manifest_kur(uzerine_yaz=True)


def test_gecmisteki_manifest_silinip_ilk_kurulum_sayilmaz(onbellek, tmp_path):
    """Iki dosya da silinse bile manifest git gecmisindeyse ilk kurulum degildir."""
    depo = gecici_depo(tmp_path)
    yol = mf._test_manifest_ayarla(depo / "data" / "onbellek_manifest.csv")
    mf.manifest_kur()
    git(depo, "add", "data/onbellek_manifest.csv")
    git(depo, "commit", "-q", "-m", "manifest")
    yol.unlink()
    mf.onay_ayrinti_yolu().unlink()
    with pytest.raises(mf.OnayKatmaniKilitli):
        mf.manifest_kur()
    assert not yol.exists() and not mf.onay_ayrinti_yolu().exists()


def test_pytest_icinde_ayarsiz_gercek_manifest_yazilmaz(monkeypatch):
    monkeypatch.setattr(mf, "_TEST_AYARI", None)
    assert not mf.denetim_etkin()
    with pytest.raises(mf.ManifestYok):
        mf.manifest_kur()


def test_pytest_disinda_denetim_etkin_ve_test_ayari_reddedilir():
    betik = ("import sys; sys.path.insert(0, sys.argv[1])\n"
             "from data import onbellek_manifest as mf\n"
             "print(mf.denetim_etkin())\n"
             "try:\n    mf._test_manifest_ayarla('x')\n"
             "except PermissionError:\n    print('red')\n")
    cikti = subprocess.run([sys.executable, "-B", "-c", betik, str(config.KOK)], capture_output=True, text=True, check=True)
    assert cikti.stdout.split() == ["True", "red"]


# --- Kesif katmani ---------------------------------------------------------------------------------------------------


def test_kesif_katmani_onay_dosyasina_dokunmaz(onbellek, monkeypatch):
    """Acma denemeleri yorumlayici kancasiyla, boy okuma `os.stat` sarmaliyla sayilir. Yedek olarak onay dosyalari ve
    ayrinti listesi silinir: okunmaya calisilsa hata verirdi."""
    global _ACILAN
    mf.manifest_kur()
    gercek_stat = os.stat
    baktigi = []

    def sayan_stat(yol, *a, **k):
        baktigi.append(str(yol))
        return gercek_stat(yol, *a, **k)

    monkeypatch.setattr(os, "stat", sayan_stat)
    monkeypatch.setattr(mf, "_onay_listesi", lambda *_: pytest.fail("ayrinti listesi okundu"))
    _ACILAN = []
    try:
        mf.manifest_dogrula(katman="kesif")
        acilan = list(_ACILAN)
    finally:
        _ACILAN = None
    b = _b_sembolu()
    assert any(AY_ONCESI in a for a in acilan), "kanca calismiyor"
    assert not [a for a in acilan + baktigi if C2_AYI in a or b in a or "onay_ayrintisi" in a]


def test_kesif_katmani_onay_dosyasi_bozukken_de_gecer(onbellek):
    """Kanitin ikinci yolu: bozuk onay dosyasini kesif katmani fark edemez, cunku acmaz."""
    mf.manifest_kur()
    _bayt_cevir(_onay_yolu(onbellek))
    mf.manifest_dogrula(katman="kesif")


def test_kesif_katmani_izin_istemez_tam_ister(onbellek):
    mf.manifest_kur()
    mf.manifest_dogrula(katman="kesif")
    with pytest.raises(bv.OnayVerisiKorumasi):
        mf.manifest_dogrula(katman="tam")


def test_gecersiz_katman(onbellek):
    mf.manifest_kur()
    with pytest.raises(ValueError):
        mf.manifest_dogrula(katman="onay")


# --- Bozulmalar ------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("bozma", ["bayt", "boy", "sil"])
def test_kesif_dosyasi_bozulursa_iki_katman_da_adiyla_soyler(onbellek, bozma):
    mf.manifest_kur()
    hedef = _kesif_yolu(onbellek)
    if bozma == "bayt":
        _bayt_cevir(hedef)
    elif bozma == "boy":
        hedef.write_bytes(hedef.read_bytes() + b"x")
    else:
        hedef.unlink()
    for cagri in (lambda: mf.manifest_dogrula(katman="kesif"), _tam):
        with pytest.raises(mf.ManifestUyusmazligi, match=f"{A_SEMBOL}/{config.BAR_4H}/{AY_ONCESI}"):
            cagri()


def test_manifestte_olmayan_kesif_dosyasi_dogrulamada_yakalanir(onbellek):
    mf.manifest_kur()
    (_kesif_yolu(onbellek).parent / "2021-02.parquet").write_bytes(b"sonradan")
    with pytest.raises(mf.ManifestUyusmazligi, match="2021-02"):
        mf.manifest_dogrula(katman="kesif")


def test_liste_degisirse_iki_katman_da_hata_verir(onbellek):
    mf.manifest_kur()
    yol = bv.donuk_liste_yolu()
    yol.write_text(yol.read_text(encoding="utf-8") + " ", encoding="utf-8")
    for cagri in (lambda: mf.manifest_dogrula(katman="kesif"), _tam):
        with pytest.raises(mf.ManifestUyusmazligi, match="liste.json"):
            cagri()


@pytest.mark.parametrize("bozma", ["bayt", "boy", "sil"])
def test_onay_dosyasi_bozulursa_tam_adiyla_soyler_boy_ve_ozet_yazmaz(onbellek, bozma):
    mf.manifest_kur()
    hedef = _onay_yolu(onbellek)
    boy = hedef.stat().st_size
    ozet = mf._sha256(hedef)
    if bozma == "bayt":
        _bayt_cevir(hedef)
    elif bozma == "boy":
        hedef.write_bytes(hedef.read_bytes() + b"x")
    else:
        hedef.unlink()
    with pytest.raises(mf.ManifestUyusmazligi) as hata:
        _tam()
    assert C2_AYI in str(hata.value)
    assert str(boy) not in str(hata.value) and ozet not in str(hata.value)


def test_ayrinti_listesinde_satir_degisirse_ozet_uyusmazligi(onbellek):
    mf.manifest_kur()
    yol = mf.onay_ayrinti_yolu()
    metin = yol.read_text(encoding="utf-8")
    yol.write_text(metin.replace("\t", "\t1", 1), encoding="utf-8", newline="")
    with pytest.raises(mf.ManifestUyusmazligi, match="ozet uyusmazligi"):
        _tam()


def test_ayrinti_listesinin_satiri_silinip_dosyasi_silinse_de_ozet_tutmaz(onbellek):
    mf.manifest_kur()
    yol = mf.onay_ayrinti_yolu()
    satirlar = yol.read_bytes().splitlines(keepends=True)
    silinen = satirlar.pop(0).split(b"\t")[0].decode("utf-8")
    yol.write_bytes(b"".join(satirlar))
    (onbellek / silinen).unlink()
    with pytest.raises(mf.ManifestUyusmazligi, match="ozet uyusmazligi"):
        _tam()


def test_ayrinti_listesi_yoksa_tam_hata_verir(onbellek):
    mf.manifest_kur()
    mf.onay_ayrinti_yolu().unlink()
    with pytest.raises(mf.ManifestYok):
        _tam()


def test_ayrinti_listesi_izinsiz_okunamaz_bellekte_olsa_bile(onbellek):
    mf.manifest_kur()
    with bv.onay_verisi_izni("test"):
        mf._onay_listesi(mf._manifest())
    assert "onay" in mf._BELLEK  # kopya bellekte; denetim yine her okunusta
    with pytest.raises(bv.OnayVerisiKorumasi):
        mf._onay_listesi(mf._manifest())


def test_bellek_temizligi_kopyalari_dusurur(onbellek):
    mf.manifest_kur()
    with bv.onay_verisi_izni("test"):
        mf._onay_listesi(mf._manifest())
    bv.donuk_bellek_temizle()
    assert mf._BELLEK == {}


# --- Agsiz okuma -----------------------------------------------------------------------------------------------------


def test_kapi_yolu_tutarli_manifestle_okur(onbellek):
    mf.manifest_kur()
    assert len(klines.mumlari_yukle(A_SEMBOL, config.BAR_4H, "KESIF")) == 12


def test_kesif_yuklemesi_c2_ayi_dosyasini_da_ham_okur_ve_ayrinti_listesine_bakar(onbellek, monkeypatch):
    """RESULTS §14.41: kapi yolu butun aylari okuyup sonra keser; KESIF yuklemesi A grubunun C2 dosyasini da acar."""
    mf.manifest_kur()
    okunan = []
    gercek = pd.read_parquet
    monkeypatch.setattr(pd, "read_parquet", lambda yol, *a, **k: (okunan.append(str(yol)), gercek(yol, *a, **k))[1])
    bv.donuk_bellek_temizle()
    cerceve = klines.mumlari_yukle(A_SEMBOL, config.BAR_4H, "KESIF")
    assert any(C2_AYI in y for y in okunan) and "onay" in mf._BELLEK
    assert cerceve["open_time"].max() < pd.Timestamp(config.C2_BASI)


def test_agsiz_yolda_manifestte_olmayan_kesif_dosyasi_okunmaz(onbellek, monkeypatch):
    mf.manifest_kur()
    yeni = _kesif_yolu(onbellek).with_name("2021-02.parquet")
    sahte_4h("2021-02-01 00:00", 12).to_parquet(yeni, index=False)
    yol = bv.donuk_liste_yolu()
    icerik = json.loads(yol.read_text(encoding="utf-8"))
    icerik["mum"][A_SEMBOL][config.BAR_4H].insert(0, _anahtar(A_SEMBOL, "2021-02"))
    yol.write_text(json.dumps(icerik), encoding="utf-8")
    monkeypatch.setattr(bv, "_oturum", lambda: pytest.fail("aga cikildi"))
    monkeypatch.setattr(pd, "read_parquet", lambda *_a, **_k: pytest.fail("parquet acildi"))
    with pytest.raises(mf.ManifestUyusmazligi, match="2021-02"):
        klines.mumlari_yukle(A_SEMBOL, config.BAR_4H, "KESIF")


def test_agsiz_yolda_boyu_degismis_kesif_dosyasi_okunmaz(onbellek):
    mf.manifest_kur()
    hedef = _kesif_yolu(onbellek)
    hedef.write_bytes(hedef.read_bytes() + b"x")
    with pytest.raises(mf.ManifestUyusmazligi, match=AY_ONCESI):
        klines.mumlari_yukle(A_SEMBOL, config.BAR_4H, "KESIF")


def test_listede_olup_manifestte_olmayan_ay_ag_ya_da_sessiz_atlama_vermez(onbellek, monkeypatch):
    mf.manifest_kur()
    yol = bv.donuk_liste_yolu()
    icerik = json.loads(yol.read_text(encoding="utf-8"))
    icerik["mum"][A_SEMBOL][config.BAR_4H].insert(1, _anahtar(A_SEMBOL, "2021-03"))
    yol.write_text(json.dumps(icerik), encoding="utf-8")
    monkeypatch.setattr(bv, "_oturum", lambda: pytest.fail("aga cikildi"))
    with pytest.raises(mf.ManifestUyusmazligi, match="2021-03"):
        klines.mumlari_yukle(A_SEMBOL, config.BAR_4H, "KESIF")


def test_agsiz_yolda_boyu_degismis_onay_dosyasi_okunmaz_ve_ad_vermez(onbellek):
    mf.manifest_kur()
    hedef = _onay_yolu(onbellek)
    boy = hedef.stat().st_size
    hedef.write_bytes(hedef.read_bytes() + b"x")
    with pytest.raises(mf.ManifestUyusmazligi) as hata:
        klines.mumlari_yukle(A_SEMBOL, config.BAR_4H, "KESIF")
    assert C2_AYI not in str(hata.value) and str(boy) not in str(hata.value)


def test_agsiz_yolda_ayrinti_listesi_bozuksa_kesif_yuklemesi_durur(onbellek):
    """Ilk okumada depodaki ozetle karsilastirma."""
    mf.manifest_kur()
    yol = mf.onay_ayrinti_yolu()
    yol.write_bytes(yol.read_bytes() + b"x\t1\ty\n")
    bv.donuk_bellek_temizle()
    with pytest.raises(mf.ManifestUyusmazligi, match="ozet uyusmazligi"):
        klines.mumlari_yukle(A_SEMBOL, config.BAR_4H, "KESIF")


def test_manifest_yokken_agsiz_okuma_hata_verir(onbellek):
    with pytest.raises(mf.ManifestYok):
        klines.mumlari_yukle(A_SEMBOL, config.BAR_4H, "KESIF")


def test_funding_kapi_yolu_da_manifestten_gecer(onbellek, monkeypatch):
    """Funding kapisi evreni okur ve sonra ham yolu izler; ham yol `onbellekten_oku` uzerinden denetlenir."""
    monkeypatch.setattr(bv, "_donuk_anahtarlar", lambda *_a: [
        f"{bv.FUNDING_ONEKI}/{A_SEMBOL}/{A_SEMBOL}-fundingRate-2021-04.zip"])
    mf.manifest_kur()
    with pytest.raises(mf.ManifestUyusmazligi, match="2021-04"):
        funding_modulu.funding_yukle(A_SEMBOL, "KESIF")


# --- Izinsiz liste hatasi ad vermez ----------------------------------------------------------------------------------


def test_dondurulmus_liste_izinsiz_hatasi_ay_adi_vermez(onbellek):
    with pytest.raises(bv.OnayVerisiKorumasi) as hata:
        bv._donuk_liste()
    assert C2_AYI not in str(hata.value) and _b_sembolu() not in str(hata.value)
    with pytest.raises(bv.OnayVerisiKorumasi) as hata:
        bv._donuk_anahtarlar("mum", A_SEMBOL, config.BAR_4H)
    assert C2_AYI not in str(hata.value)


# --- Onay kosusu acilisi ---------------------------------------------------------------------------------------------


def test_tam_hata_verince_kosu_acilmaz_ve_cift_harcanmaz(onbellek, tmp_path):
    kayit = tmp_path / "ONAY_KAYDI.md"
    gecici_kayit(kayit)
    mf.manifest_kur()
    _bayt_cevir(_onay_yolu(onbellek))
    with pytest.raises(mf.ManifestUyusmazligi):
        with kosu("H2", "C1"):
            pytest.fail("kosu acildi")
    assert split.aktif_onay_kosusu() is None
    assert not kayit.exists() or "BASLADI" not in kayit.read_text(encoding="utf-8")
    assert ("H2", "C1") not in split.harcanan_ciftler()


def test_manifest_yoksa_kosu_acilmaz(onbellek, tmp_path):
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    with pytest.raises(mf.ManifestYok):
        with kosu("H2", "C1"):
            pytest.fail("kosu acildi")


def test_kosu_acilisi_tam_cagirir_ve_tutarli_manifestle_acilir(onbellek, tmp_path, monkeypatch):
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    mf.manifest_kur()
    katmanlar = []
    gercek = mf.manifest_dogrula
    monkeypatch.setattr(mf, "manifest_dogrula", lambda *, katman: (katmanlar.append(katman), gercek(katman=katman))[1])
    with kosu("H2", "C1"):
        assert split.aktif_onay_kosusu() == ("H2", "C1")
    assert katmanlar == ["tam"]


def test_kosu_icindeki_kapi_yolu_manifestle_okur(onbellek, tmp_path):
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    mf.manifest_kur()
    with kosu("H2", "C1"):
        assert len(klines.mumlari_yukle(_b_sembolu(), config.BAR_4H, "C1", onay=True)) == 12
