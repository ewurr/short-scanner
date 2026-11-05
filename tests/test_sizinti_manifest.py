"""Sizinti testcisi: onbellek manifesti, agsiz okuma ve kesif kosusu (on-kayit §3 rev.13; RESULTS §14.41).

Her test GUVENLI davranisi iddia eder. Saldiri basariliysa test `AssertionError` ile kirilir; bilinen acik olarak
isaretlenenler `xfail(strict=True, raises=AssertionError, reason="M-n: ...")` tasir. Hicbir test aga cikmaz, gercek
`cache/` dosyalarina dokunmaz; gecici onbellek ve gecici manifest kullanilir (`test_onbellek_manifest.py` duzeni).
Gercek veriye yalnizca `data/split.csv` ve `config` (zaten depoda acik) bakilir.

Bulgu kodlari (xfail nedenlerinde):
  M-1  `okuma_denetle` yalnizca boya bakar: ayni boyda bayt degisikligi okumada yakalanmaz (kesif ve onay).
  M-2  `liste.json` yalnizca kosu acilisinda ozetlenir; kosu icinde degisirse ay sessizce dusurulur.
  M-3  `onbellekten_oku` dizin yoluyla (`klines`, `klines/<SEMBOL>`) izinsiz butun onay verisini okur.
  M-4  Onay kosusu icinde onay katmani, degistirilmis onay dosyasiyla "yeniden kurularak" aklanir.
  M-5  Tarama: NFKC ile esdeger tam genislikli kimlikler (`ｂｖ`) taramadan kacar.
  M-6  Tarama: `.ipynb` JSON parcalama / `\\uXXXX` kacisi taramadan kacar.
  M-7  Tarama: `# coding: utf-7` bildirimli kaynak taramadan kacar.
  M-8  Tarama: `yenile=False or True` gibi ifadeler taramadan kacar.
  M-9  Tarama: `yenile` konumsal gecirilirse taramadan kacar (imza anahtar-sozcuk-yalniz degil).
  M-10 Ag yasagi yalnizca ortam degiskeniyle tasinir: ara surec zinciri ya da silinen degisken yasagi dusurur.
  M-11 `PYTEST_CURRENT_TEST` taklidiyle manifest denetimi kapatilabilir.
  M-12 Eslesmemis `kosu_agsiz().__exit__` calisan kosunun yasagini kaldirir ve sayaci bozar.
  M-13 Onay verisi izni surec geneli: baska is parcaciginin izni bu parcaciga onay verisi okutur.
  M-14 Sabit baglanti (hardlink) ile onay dosyasi "kesif" satirina girer: boy ve ozet depodaki manifeste yazilir.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import os
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import pytest

import config
from conftest import sahte_4h
from data import binance_vision as bv
from data import funding as funding_modulu
from data import klines, kume_bellegi, onbellek_manifest as mf
from data import split
from onay_yardimcisi import gecici_depo, gecici_kayit, git, kosu
from tarama_yardimcisi import ONBELLEK_DESENI, ONBELLEK_UZANTILARI, ihlaller

A_SEMBOL = "SOLUSDT"
AY_ONCESI = "2021-01"
C2_AYI = "2025-09"

_ACILAN: list | None = None


def _kanca(olay, argumanlar):
    if olay == "open" and _ACILAN is not None:
        _ACILAN.append(str(argumanlar[0]))


sys.addaudithook(_kanca)  # yorumlayicida acilan her dosya (io.open, os.open, Path.open)


def _b_sembolu() -> str:
    tablo = split.split_oku()
    return str(tablo.loc[tablo["grup"] == "B", "sembol"].iloc[0])


def _anahtar(sembol, ay):
    return f"{bv.MUM_ONEKI}/{sembol}/{config.BAR_4H}/{sembol}-{config.BAR_4H}-{ay}.zip"


@pytest.fixture
def onbellek(monkeypatch, tmp_path):
    """Kesif: A, C2 oncesi (mum, funding, birincil). Onay: A, C2 ayi ve B, C2 oncesi. Gercek parquet, liste dahil."""
    kok = tmp_path / "onbellek"
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", kok)
    mf._test_manifest_ayarla(tmp_path / "onbellek_manifest.csv")
    bv.donuk_bellek_temizle()
    kume_bellegi.temizle()
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
    kume_bellegi.temizle()


def _kesif_yolu(kok):
    return kok / "klines" / A_SEMBOL / config.BAR_4H / f"{AY_ONCESI}.parquet"


def _onay_yolu(kok):
    return kok / "klines" / A_SEMBOL / config.BAR_4H / f"{C2_AYI}.parquet"


def _b_yolu(kok):
    return kok / "klines" / _b_sembolu() / config.BAR_4H / f"{AY_ONCESI}.parquet"


def _tam():
    with bv.onay_verisi_izni("test"):
        return mf.manifest_dogrula(katman="tam")


def _bayt_cevir(yol):
    """Boyu degistirmeden tek baytin bitlerini cevirir."""
    boy = yol.stat().st_size
    govde = bytearray(yol.read_bytes())
    govde[len(govde) // 2] ^= 0xFF
    yol.write_bytes(bytes(govde))
    assert yol.stat().st_size == boy


def _okuma_kaydi(monkeypatch) -> list:
    """`pd.read_parquet` cagrilarini sayar (bos cerceve doner). Okuma denendiyse manifest/izin kapisi gecilmistir."""
    okunan: list = []

    def sahte(yol, *_a, **_k):
        okunan.append(str(yol))
        return pd.DataFrame()

    monkeypatch.setattr(pd, "read_parquet", sahte)
    return okunan


def _okumayi_dene(yol) -> str:
    """`bv.onbellekten_oku` cagirir; kapilarin reddi 'reddedildi' doner. Okuma `_okuma_kaydi` ile ayrica olculur."""
    try:
        bv.onbellekten_oku(Path(yol))
    except (bv.OnayVerisiKorumasi, mf.ManifestHatasi, OSError, ValueError):
        return "reddedildi"
    return "gecti"


# --- M-1: ayni boyda bayt degisikligi ----------------------------------------------------------------------------


def test_kosu_icinde_ayni_boyda_bayt_degisikligi_kesif_dosyasinda_yakalanir(onbellek, monkeypatch):
    """On-kayit §3 rev.13: "koşu dondurulmuş yerel önbellekten okur". Dondurma SHA256 ile kanitlanir; kosu acildiktan
    sonra ayni boyda degistirilen kesif dosyasi okuma aninda reddedilmelidir."""
    mf.manifest_kur()
    hedef = _kesif_yolu(onbellek)
    # Kapanis kesif katmanini yeniden dogrular ve bozulmayi ayrica yakalar (RESULTS §14.42, D-B2).
    with pytest.raises(split.KesifBagiHatasi):
        with split.kesif_kosusu():
            _bayt_cevir(hedef)
            okunan = _okuma_kaydi(monkeypatch)
            _okumayi_dene(hedef)
            assert not okunan, "ayni boyda bozulmus kesif dosyasi kosu icinde parquet olarak acildi"


def test_onay_kosusu_icinde_ayni_boyda_bayt_degisikligi_onay_dosyasinda_yakalanir(onbellek, monkeypatch, tmp_path):
    """On-kayit §3 rev.13 ve CLAUDE.md §3.3: onay kosusunun baktigi veri, acilista dogrulanan veridir. Kosu icinde ayni
    boyda degistirilen C2 dosyasi okuma aninda reddedilmelidir."""
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    mf.manifest_kur()
    hedef = _onay_yolu(onbellek)
    with kosu("H2", "C1"):
        _bayt_cevir(hedef)
        okunan = _okuma_kaydi(monkeypatch)
        with bv.onay_verisi_izni("test"):
            _okumayi_dene(hedef)
        assert not okunan, "ayni boyda bozulmus onay dosyasi onay kosusu icinde parquet olarak acildi"


# --- M-2: liste.json kosu icinde ----------------------------------------------------------------------------------


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="M-2: liste.json'in SHA256'si yalnizca kosu acilisinda denetlenir; kosu icinde bir ay "
                          "listeden silinirse veri sessizce eksik yuklenir")
def test_kosu_acildiktan_sonra_liste_json_degisirse_ay_sessizce_dusmez(onbellek):
    """On-kayit §3 rev.13: dondurulmus liste degismezdir (SHA256 manifestte). Liste kosu icinde degistirilirse ya hata
    verilmeli ya da sonuc ayni kalmali; bir ay sessizce dusmemelidir."""
    ikinci = _kesif_yolu(onbellek).with_name("2021-02.parquet")
    sahte_4h("2021-02-01 00:00", 12).to_parquet(ikinci, index=False)
    liste = bv.donuk_liste_yolu()
    icerik = json.loads(liste.read_text(encoding="utf-8"))
    icerik["mum"][A_SEMBOL][config.BAR_4H].insert(1, _anahtar(A_SEMBOL, "2021-02"))
    liste.write_text(json.dumps(icerik), encoding="utf-8")
    mf.manifest_kur()
    with split.kesif_kosusu():
        once = len(klines.mumlari_yukle(A_SEMBOL, config.BAR_4H, "KESIF"))
        icerik["mum"][A_SEMBOL][config.BAR_4H].pop(1)
        liste.write_text(json.dumps(icerik), encoding="utf-8")
        kume_bellegi.temizle()
        try:
            sonra = len(klines.mumlari_yukle(A_SEMBOL, config.BAR_4H, "KESIF"))
        except mf.ManifestHatasi:
            return  # reddedildi: guvenli
        assert sonra == once, f"liste degisti, yukleme sessizce {once} satirdan {sonra} satira dustu"


# --- Yonlendirme ve yol hileleri ---------------------------------------------------------------------------------


def test_onbellek_dizini_yonlendirilip_ayni_boyda_bozulursa_kesif_acilisi_yakalar(onbellek, monkeypatch, tmp_path):
    """On-kayit §3 rev.13 (`config.ONBELLEK_DIZINI` yonlendirmesi denetimi atlatmaz): baska dizindeki kopyada ayni
    boyda degisen kesif dosyasi, kosu acilisinda SHA256 ile yakalanir."""
    mf.manifest_kur()
    kopya = tmp_path / "kopya"
    shutil.copytree(onbellek, kopya)
    _bayt_cevir(kopya / "klines" / A_SEMBOL / config.BAR_4H / f"{AY_ONCESI}.parquet")
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", kopya)
    with pytest.raises(mf.ManifestUyusmazligi):
        with split.kesif_kosusu():
            pytest.fail("yonlendirilmis dizinle kosu acildi")
    assert bv._KOSU_AGSIZ["sayac"] == 0


def test_kosu_icinde_yonlendirilen_dizindeki_manifestsiz_dosya_okunamaz(onbellek, monkeypatch, tmp_path):
    """On-kayit §3 rev.13: manifestte olmayan dosya agsiz yolda okunmaz; kok yonlendirilse bile goreli yol manifestte
    aranir."""
    mf.manifest_kur()
    kopya = tmp_path / "kopya"
    shutil.copytree(onbellek, kopya)
    ekstra = kopya / "klines" / A_SEMBOL / config.BAR_4H / "2021-02.parquet"
    sahte_4h("2021-02-01 00:00", 12).to_parquet(ekstra, index=False)
    with split.kesif_kosusu():
        monkeypatch.setattr(config, "ONBELLEK_DIZINI", kopya)
        okunan = _okuma_kaydi(monkeypatch)
        assert _okumayi_dene(ekstra) == "reddedildi"
        assert not okunan
        # Kapanis kesif katmanini yeniden dogrular (RESULTS §14.42, D-B2); kok kapanistan once eski haline doner.
        monkeypatch.setattr(config, "ONBELLEK_DIZINI", onbellek)


def _yol_bicimleri(kok: Path, hedef: Path) -> dict:
    govde = hedef.relative_to(kok)
    bicimler = {
        "nokta_nokta": kok / "klines" / ".." / govde,
        "tek_nokta": kok / "." / govde,
        "buyuk_kucuk_harf": kok.joinpath(*[p.swapcase() for p in govde.parts]),
        "sonda_nokta": Path(str(hedef) + "."),
    }
    try:
        bicimler["gorece"] = Path(os.path.relpath(hedef))
    except ValueError:  # Windows: farkli surucu
        pass
    if sys.platform == "win32":
        bicimler["uzun_yol_oneki"] = Path("\\\\?\\" + str(hedef))
        bicimler["ntfs_akisi"] = Path(str(hedef) + "::$DATA")
    return bicimler


BICIMLER = ["nokta_nokta", "tek_nokta", "buyuk_kucuk_harf", "sonda_nokta", "gorece", "uzun_yol_oneki", "ntfs_akisi"]


@pytest.mark.parametrize("hedef_adi", ["a_c2_ayi", "b_grubu"])
@pytest.mark.parametrize("bicim", BICIMLER)
def test_yol_hileleriyle_onay_verisi_izinsiz_okunamaz(onbellek, monkeypatch, bicim, hedef_adi):
    """CLAUDE.md §3.3 ve `bv.onbellekten_oku`: onay verisi (B grubu, C2 ayi) izin disinda okunamaz. `..`, tek nokta,
    harf buyuklugu, sondaki nokta, goreli yol, `\\\\?\\` oneki ve NTFS akisi yolun siniflandirmasini sasirtmamali."""
    hedef = _onay_yolu(onbellek) if hedef_adi == "a_c2_ayi" else _b_yolu(onbellek)
    bicimler = _yol_bicimleri(onbellek, hedef)
    if bicim not in bicimler:
        pytest.skip(f"{bicim} bu platformda yok")
    okunan = _okuma_kaydi(monkeypatch)
    _okumayi_dene(bicimler[bicim])
    assert not okunan, f"{bicim} bicimiyle onay dosyasi izinsiz parquet olarak acildi"


@pytest.mark.parametrize("dizin", ["tur_dizini", "b_sembol_dizini", "a_sembol_dizini"])
def test_dizin_yoluyla_onay_verisi_izinsiz_okunamaz(onbellek, monkeypatch, dizin):
    """CLAUDE.md §3.3: onay verisi izin disinda okunamaz. Dosya yerine dizin verilirse `pd.read_parquet` dizindeki
    butun parquet dosyalarini (B grubu ve C2 ayi dahil) okuyabilir; kapi bunu da reddetmelidir."""
    yollar = {"tur_dizini": onbellek / "klines", "b_sembol_dizini": onbellek / "klines" / _b_sembolu(),
              "a_sembol_dizini": onbellek / "klines" / A_SEMBOL}
    okunan = _okuma_kaydi(monkeypatch)
    _okumayi_dene(yollar[dizin])
    assert not okunan, "dizin yolu denetimsiz parquet okumasina gitti"


def test_sembol_ve_bar_dizini_izinsiz_okunamaz(onbellek, monkeypatch):
    """CLAUDE.md §3.3: `klines/<SEMBOL>/<bar>` dizin yolu da onay verisi izni ister (ay yerine `4h` ayristirilamaz,
    kapali yon)."""
    okunan = _okuma_kaydi(monkeypatch)
    _okumayi_dene(onbellek / "klines" / _b_sembolu() / config.BAR_4H)
    _okumayi_dene(onbellek / "klines" / A_SEMBOL / config.BAR_4H)
    assert not okunan


def test_agsiz_yolda_dizin_yolu_manifest_ya_da_izin_kapisindan_gecemez(onbellek, monkeypatch):
    """On-kayit §3 rev.13: agsiz yolda manifestte olmayan (dizin dahil) yol okunmaz."""
    mf.manifest_kur()
    with split.kesif_kosusu():
        okunan = _okuma_kaydi(monkeypatch)
        with bv.onay_verisi_izni("test"):  # kapi yukleyicilerinin tuttugu izin: dizin yine de reddedilmeli
            assert _okumayi_dene(onbellek / "klines" / A_SEMBOL) == "reddedildi"
            assert _okumayi_dene(onbellek / "klines") == "reddedildi"
        assert not okunan


# --- Siniflandirma ve kesif katmani ------------------------------------------------------------------------------


def test_siniflandirma_split_csv_ile_birebir_uyumlu():
    """On-kayit §3: B grubu her ay, A grubu yalnizca C2 ayindan itibaren onay verisidir. Gercek `split.csv` ile
    `onbellek_manifest._onay_dosyasi_mi` her sembol ve sinir ayi icin ayni karari vermeli."""
    tablo = split.split_oku()
    for sembol, grup in zip(tablo["sembol"], tablo["grup"]):
        onay = grup == "B"
        assert mf._onay_dosyasi_mi(f"klines/{sembol}/{config.BAR_4H}/2021-01.parquet") is onay, sembol
        assert mf._onay_dosyasi_mi(f"klines/{sembol}/{config.BAR_4H}/2025-08.parquet") is onay, sembol
        assert mf._onay_dosyasi_mi(f"klines/{sembol}/{config.BAR_4H}/2025-09.parquet") is True, sembol
        assert mf._onay_dosyasi_mi(f"funding/{sembol}/2026-01.parquet") is True, sembol


def test_yeniden_adlandirma_zincirinin_iki_ucu_ayni_siniflanir():
    """On-kayit §3 rev.2 (dokuz zincir): zincirin iki ucu ayni gruba duser; siniflandirma da ikisi icin ayni olmali.
    Aksi halde B coininin eski adi 'kesif' sayilip manifeste ve depoya girer."""
    tablo = split.split_oku()
    grup = dict(zip(tablo["sembol"], tablo["grup"]))
    for yeni, eski in config.YENIDEN_ADLANDIRMA.items():
        yeni_onay = mf._onay_dosyasi_mi(f"klines/{yeni}/{config.BAR_4H}/2021-01.parquet")
        eski_onay = mf._onay_dosyasi_mi(f"klines/{eski}/{config.BAR_4H}/2021-01.parquet")
        assert yeni_onay == eski_onay, (yeni, eski)
        for ad in (yeni, eski):
            if ad in grup:
                assert (grup[ad] == "B") == yeni_onay, ad


@pytest.mark.parametrize("goreli", [
    "klines/SOLUSDT.parquet",                       # bicimi bozuk: kisa yol
    "klines/SOLUSDT/4h/2025-9.parquet",             # sifirsiz ay
    "klines/SOLUSDT/4h/20250915.parquet",           # gun bicimi
    "klines/SOLUSDT/4h/2025-09-15.parquet",         # gunluk dosya adi
    "klines/SOLUSDT/4h/09-2025.parquet",            # ters sira
    "klines/SOLUSDT/4h/bozuk.parquet",              # ayristirilamaz
    "klines/SOLUSDT/4h/2025-13.parquet",            # gecersiz ay
    "klines/SOLUSDT/4h/2025-00.parquet",
    "klines/SOLUSDT/4h/alt/2026-01.parquet",        # ic ice dizin
    "funding/SOLUSDT/2025-10.parquet",              # baska tur
    "klines_birincil_1d/SOLUSDT/2025-09.parquet",   # birincil gunluk
    "klines/{B}/4h/2021-01.parquet",                # B grubu, eski ay
    "funding/{B}/2021-01.parquet",
])
def test_kesif_dogrulamasi_onay_gorunumlu_ya_da_bicimi_bozuk_dosyayi_acmaz(onbellek, goreli):
    """CLAUDE.md §3.3 ve ozet: `katman="kesif"` hicbir onay dosyasini acmaz. Adi bicimi bozuk, ay yazimi sasirtici ya da
    B grubuna ait dosyalar onay sayilmali (kapali yon): ne acilmali ne de 'kesif manifestte yok' diye sinif degistirmeli."""
    global _ACILAN
    mf.manifest_kur()
    hedef = onbellek / goreli.format(B=_b_sembolu())
    hedef.parent.mkdir(parents=True, exist_ok=True)
    hedef.write_bytes(b"onay baytlari")
    _ACILAN = []
    try:
        try:
            mf.manifest_dogrula(katman="kesif")
            kesif_sayildi = None
        except mf.ManifestUyusmazligi as hata:
            kesif_sayildi = str(hata)
        acilan = list(_ACILAN)
    finally:
        _ACILAN = None
    hedef_yolu = os.path.normcase(os.path.abspath(hedef))
    assert not [a for a in acilan if os.path.normcase(os.path.abspath(a)) == hedef_yolu], \
        "kesif dogrulamasi dosyayi acti"
    assert kesif_sayildi is None, f"onay gorunumlu ad kesif katmaninda ele alindi: {kesif_sayildi}"


def test_kesif_katmani_onay_dosyasi_eklenip_silinse_sessiz_kalir_ve_ad_vermez(onbellek):
    """Ozet: `katman="kesif"` onay dosyasinin varligina bile bakmaz; eklenen/silinen onay dosyasi kesif hatasinda
    ad olarak gecmez (ad yalnizca `tam` dogrulamasinda)."""
    mf.manifest_kur()
    _onay_yolu(onbellek).unlink()
    _onay_yolu(onbellek).with_name("2025-10.parquet").write_bytes(b"eklenen")
    sonuc = mf.manifest_dogrula(katman="kesif")
    assert set(sonuc) == {"katman", "kesif_satir", "kesif_bayt", "onay_dosya", "sure_sn"}
    with pytest.raises(mf.ManifestUyusmazligi) as hata:
        _tam()
    assert "2025-10" in str(hata.value) or C2_AYI in str(hata.value)  # `tam` adiyla soyler


def test_hostile_katman_nesnesi_izin_kapisini_atlatamaz(onbellek):
    """Ozet: `tam` onay izni ister. `==` karsilastirmasi ardisik cagrilarda farkli sonuc veren bir `str` alt sinifi,
    uye denetimini ve izin denetimini gecip sonra 'tam' gibi davranirsa bile ayrinti listesi izinsiz okunamaz."""

    class _Degisken(str):
        def __new__(cls, deger):
            nesne = super().__new__(cls, deger)
            nesne.cagri = 0
            return nesne

        def __eq__(self, diger):
            self.cagri += 1
            if self.cagri == 1:
                return True
            if self.cagri == 2:
                return False
            return str.__eq__(self, diger)

        __hash__ = str.__hash__

    mf.manifest_kur()
    try:
        mf.manifest_dogrula(katman=_Degisken("tam"))
    except (bv.OnayVerisiKorumasi, ValueError):
        return
    raise AssertionError("sahte katman nesnesi izinsiz 'tam' dogrulamasini calistirdi")


def test_komut_satiri_ciktisi_onay_ay_adi_ve_b_sembolu_sizdirmaz(onbellek, capsys, tmp_path):
    """Ozet: manifest araclari yalnizca sayi ve ozet dondurur/yazar; C2 ayi adi ve B sembolu ciktida gecmez. `tam`
    yalnizca acik onay kosusunda calisir (RESULTS §14.42, D-C2); bu yuzden kosu icinde cagrilir."""
    mf.manifest_kur()
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    for argumanlar in (["manifest-dogrula", "--katman", "kesif"], ["manifest-dogrula", "--katman", "tam"]):
        if argumanlar[-1] == "tam":
            with kosu("H2", "C1"):
                capsys.readouterr()
                assert mf._ana(argumanlar) == 0
                cikti = capsys.readouterr().out
        else:
            assert mf._ana(argumanlar) == 0
            cikti = capsys.readouterr().out
        assert C2_AYI not in cikti and _b_sembolu() not in cikti
        assert {satir.split(":")[0] for satir in cikti.splitlines()} <= {"katman", "kesif_satir", "kesif_bayt",
                                                                        "onay_dosya", "sure_sn"}


def test_ayrinti_listesi_yokken_kesif_yuklemesi_ona_bakmaz(onbellek):
    """RESULTS §14.42 (D-B1; §14.41'de bu test KESIF yuklemesinin ayrinti listesi yokken ad sizdirmadan durdugunu
    sinardi): KESIF yuklemesi ayrinti listesini hic okumaz; liste yokken de sonuc ayni."""
    mf.manifest_kur()
    once = klines.mumlari_yukle(A_SEMBOL, config.BAR_4H, "KESIF")
    mf.onay_ayrinti_yolu().unlink()
    bv.donuk_bellek_temizle()
    kume_bellegi.temizle()
    sonra = klines.mumlari_yukle(A_SEMBOL, config.BAR_4H, "KESIF")
    pd.testing.assert_frame_equal(once, sonra)


# --- M-14: sabit baglanti -----------------------------------------------------------------------------------------


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="M-14: manifest_kur dosyalari adina gore siniflar; onay dosyasina sabit baglanti (hardlink) "
                          "kesif adiyla yerlestirilirse boyu ve SHA256'si depodaki 'kesif' satirina yazilir")
def test_onay_dosyasina_sabit_baglanti_kesif_satirina_girmez(onbellek):
    """Ozet ve CLAUDE.md §3.3: depodaki manifest onay dosyasinin boyunu ve ozetini tasimaz. Onay dosyasinin bir
    baglantisi kesif adi altinda durursa kurulum onu kesif satirina yazmamali (sabit baglanti/sembolik baglanti reddi)."""
    hedef = _onay_yolu(onbellek)
    kesif_adi = _kesif_yolu(onbellek).with_name("2021-02.parquet")
    try:
        os.link(hedef, kesif_adi)
    except (OSError, NotImplementedError):
        pytest.skip("sabit baglanti kurulamadi")
    mf.manifest_kur()
    onay_ozeti = mf._sha256(hedef)
    satirlar = mf._manifest().kesif
    assert not [y for y, (_, sha) in satirlar.items() if sha == onay_ozeti], "onay dosyasinin ozeti kesif satirinda"


# --- M-4: onay katmanini aklama ---------------------------------------------------------------------------------


def test_kesif_kosusu_icinde_onay_katmani_kurulamaz(onbellek):
    """Ozet: onay katmani yalnizca ACIK BIR ONAY KOSUSU icinde yeniden kurulur; kesif kosusu onay kosusu degildir."""
    mf.manifest_kur()
    onceki = mf.onay_ayrinti_yolu().read_bytes()
    with split.kesif_kosusu():
        with pytest.raises(mf.OnayKatmaniKilitli):
            mf.manifest_kur(uzerine_yaz=True, onay_katmani=True)
    assert mf.onay_ayrinti_yolu().read_bytes() == onceki


def test_ayrinti_silinip_uzerine_yaz_ile_onay_katmani_yeniden_olusmaz(onbellek):
    """Ozet: varsayilan `uzerine_yaz` yalnizca kesif katmanini yeniler; silinen ayrinti listesi sessizce yeniden
    uretilmez (yeni liste degistirilmis onay verisini aklardi)."""
    mf.manifest_kur()
    mf.onay_ayrinti_yolu().unlink()
    try:
        mf.manifest_kur(uzerine_yaz=True)
    except (mf.ManifestHatasi, PermissionError, FileExistsError):
        pass
    assert not mf.onay_ayrinti_yolu().exists()


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="M-4: onay_katmani=True kosu icinde onay dosyalarini yeniden ozetler ve ayrinti listesi ile "
                          "manifesti yazar; acilistan sonra degistirilmis dosya 'dondurulmus' hale getirilir")
def test_kosu_icinde_degistirilmis_onay_dosyasiyla_onay_katmani_aklanamaz(onbellek, tmp_path):
    """Ozet ("bu yol bozulmus bir onay dosyasini aklayamaz") ve CLAUDE.md §3.3: kosu acildiktan sonra degisen onay
    dosyasi ile onay katmani yeniden kurulursa yeni ozet eskisiyle ayni olmali; degilse kurulum reddedilmeli."""
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    ilk = mf.manifest_kur()
    with kosu("H2", "C1"):
        _bayt_cevir(_onay_yolu(onbellek))
        reddedildi = False
        try:
            sonuc = mf.manifest_kur(uzerine_yaz=True, onay_katmani=True)
        except (mf.ManifestHatasi, PermissionError):
            reddedildi = True
        assert reddedildi or sonuc["birlesik_sha256"] == ilk["birlesik_sha256"], \
            "degistirilmis onay dosyasi yeni birlesik ozet olarak kabul edildi"


def test_ayrinti_ve_ozet_birlikte_yeniden_yazilsa_da_kirli_agac_onay_kosusunu_durdurur(onbellek, tmp_path):
    """Ozet ("depodaki satir yerel listeye baglanir") ve CLAUDE.md §3.3 (temiz calisma agaci): onay dosyasi degistirilip
    ayrinti listesi ve depodaki ozet satiri birlikte yeniden yazilsa bile, commit edilmemis manifest onay kosusunu
    acamaz."""
    depo = gecici_depo(tmp_path)
    yol = mf._test_manifest_ayarla(depo / "data" / "onbellek_manifest.csv")
    mf.manifest_kur()
    git(depo, "add", "data/onbellek_manifest.csv")
    git(depo, "commit", "-q", "-m", "manifest")
    git(depo, "push", "-q", "origin", "main")
    with kosu("H1", "C1"):  # kontrol: temiz agacta kosu acilir
        pass
    _bayt_cevir(_onay_yolu(onbellek))
    dosyalar = sorted(mf._dosyalari_gez())
    with bv.onay_verisi_izni("test"):
        onay = mf._kayitlar([g for g, onay_mu in dosyalar if onay_mu])
    govde = mf.kanonik_metin(onay)
    mf.onay_ayrinti_yolu().write_bytes(govde)
    eski = mf._manifest()
    yol.write_bytes(mf._manifest_metni(eski.kesif, eski.liste_sha256, len(onay), hashlib.sha256(govde).hexdigest()))
    acildi = False
    try:
        with kosu("H2", "C1"):
            acildi = True
    except Exception:  # noqa: BLE001 (hangi hata olursa olsun kosu acilmamali)
        pass
    assert not acildi, "kirli calisma agacinda (degistirilmis manifest) onay kosusu acildi"


# --- Bellek bayatligi ----------------------------------------------------------------------------------------------


def test_onay_kosusu_acilis_ve_kapanisinda_manifest_ve_donuk_bellek_dusurulur(onbellek, tmp_path):
    """On-kayit §3 rev.13 ve CLAUDE.md §5: onay kosusunun acilisi ve kapanisi bellek kopyalarini gecersiz kilar (manifest,
    ayrinti listesi, donuk liste)."""
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    mf.manifest_kur()
    with bv.onay_verisi_izni("test"):
        mf._onay_listesi(mf._manifest())
        bv._donuk_anahtarlar("mum", A_SEMBOL, config.BAR_4H)
    assert "onay" in mf._BELLEK and bv._DONUK_BELLEK
    with kosu("H2", "C1"):
        assert mf._BELLEK == {} and bv._DONUK_BELLEK == {}, "acilista bayat kopya kaldi"
        klines.mumlari_yukle(_b_sembolu(), config.BAR_4H, "C1", onay=True)
        assert "onay" in mf._BELLEK
    assert mf._BELLEK == {} and bv._DONUK_BELLEK == {}, "kapanista kopya kaldi"


def test_onay_kosusu_hatayla_kapanirsa_da_bellek_kopyalari_dusurulur(onbellek, tmp_path):
    """CLAUDE.md §5: kapanista kopyalar duser; kosu hatayla bitse de."""
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    mf.manifest_kur()
    with pytest.raises(ZeroDivisionError):
        with kosu("H2", "C1"):
            klines.mumlari_yukle(_b_sembolu(), config.BAR_4H, "C1", onay=True)
            assert "onay" in mf._BELLEK
            raise ZeroDivisionError
    assert mf._BELLEK == {} and bv._DONUK_BELLEK == {}


def test_kesif_kosusu_gercek_yuklemeden_sonra_kapanista_onay_listesi_bellekte_kalmaz(onbellek):
    """CLAUDE.md §5 ve RESULTS §14.42 (D-B1): KESIF yuklemesi ayrinti listesini bellege almaz (§14.41'de alirdi); kosu
    kapanisinda kopyalar duser (kosu disina onay dosyasi adi/boyu tasinmaz)."""
    mf.manifest_kur()
    with split.kesif_kosusu():
        klines.mumlari_yukle(A_SEMBOL, config.BAR_4H, "KESIF")
        assert "onay" not in mf._BELLEK
    assert mf._BELLEK == {} and bv._DONUK_BELLEK == {}
    with pytest.raises(bv.OnayVerisiKorumasi):
        mf._onay_listesi(mf._manifest())


# --- Izin: is parcacigi (M-13) -----------------------------------------------------------------------------------


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="M-13: onay verisi izni surec geneli sayactir; baska bir is parcaciginin tuttugu izin "
                          "izinsiz parcaciga onay dosyasi okutur")
def test_baska_is_parcacigindaki_izin_bu_parcaciga_onay_verisi_okutmaz(onbellek, monkeypatch):
    """CLAUDE.md §3.3: onay verisi yalnizca izin baglaminda okunur. Izin baska bir is parcaciginda (ornegin paralel bir
    yukleyici) tutuluyorken, izni olmayan bir parcacik onay dosyasini okuyamamali."""
    mf.manifest_kur()
    hazir, birak = threading.Event(), threading.Event()

    def tut():
        with bv.onay_verisi_izni("baska parcacik"):
            hazir.set()
            birak.wait(30)

    parcacik = threading.Thread(target=tut)
    parcacik.start()
    try:
        if not hazir.wait(30):
            pytest.fail("izin parcacigi hazirlanmadi")
        okunan = _okuma_kaydi(monkeypatch)
        _okumayi_dene(_onay_yolu(onbellek))
        assert not okunan, "baska parcacigin izniyle onay dosyasi okundu"
    finally:
        birak.set()
        parcacik.join(30)


# --- Ag yasagi: is parcacigi, alt surec, ortam -----------------------------------------------------------------

_ALT_SUREC = """
import sys
sys.path.insert(0, sys.argv[1])
from data import binance_vision as bv
try:
    bv.ag_yasagi_denetle("alt surec")
    print("serbest")
except bv.KosuAgYasagi:
    print("yasak")
"""

_ARA_SUREC = """
import subprocess, sys
sonuc = subprocess.run([sys.executable, "-B", "-c", sys.argv[2], sys.argv[1]], capture_output=True, text=True)
print(sonuc.stdout.strip())
sys.stderr.write(sonuc.stderr)
"""


def _calistir(*argumanlar) -> str:
    cikti = subprocess.run([sys.executable, "-B", "-c", *argumanlar], capture_output=True, text=True, timeout=120)
    if cikti.returncode != 0:
        pytest.fail(f"alt surec coktu: {cikti.stderr[-500:]}")
    return cikti.stdout.strip()


def test_kosu_oncesi_baslamis_is_parcacigi_havuzu_da_yasaga_tabidir(onbellek):
    """On-kayit §3 rev.13: yasak surec geneldir; koşudan ONCE baslatilmis bir is parcacigi da aga cikamaz."""
    mf.manifest_kur()
    havuz = ThreadPoolExecutor(max_workers=1)
    havuz.submit(lambda: None).result(timeout=30)  # is parcacigi simdiden calisiyor

    def is_():
        try:
            bv.tum_sembol_dizinleri()
        except bv.KosuAgYasagi:
            return "yasak"
        except BaseException as hata:  # noqa: BLE001
            return type(hata).__name__
        return "sessiz"

    try:
        with split.kesif_kosusu():
            assert havuz.submit(is_).result(timeout=60) == "yasak"
    finally:
        havuz.shutdown()


def test_ic_ice_kesif_kosusunda_ic_kapanis_yasagi_kaldirmaz(onbellek):
    """On-kayit §3 rev.13: ic ice kosularda yasak en dis kosu bitene kadar surer."""
    mf.manifest_kur()
    with split.kesif_kosusu():
        with split.kesif_kosusu():
            pass
        assert bv._ag_yasak_mi()
        with pytest.raises(bv.KosuAgYasagi):
            bv.tum_sembol_dizinleri()
    assert not bv._ag_yasak_mi()


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="M-10: yasak yalnizca ust surec pid'iyle tasinir; veri katmanini ice aktarmayan bir ara surec "
                          "zinciri (ornegin kabuk ya da baska bir python) torun surecte yasagi dusurur")
def test_kosu_icinde_ara_surec_zinciri_ag_yasagini_dusurmez(onbellek):
    """On-kayit §3 rev.13 ("F2 ve F3 koşuları ağa çıkmaz"): koşu içinde başlatılan sürecin torunu da aga cikamaz. Ara
    surec `data`yi ice aktarmazsa pid zinciri kopar (`_ag_yasagini_devral` yalnizca dogrudan ebeveyni tanir)."""
    mf.manifest_kur()
    with split.kesif_kosusu():
        cikti = _calistir(_ARA_SUREC, str(config.KOK), _ALT_SUREC)
    assert cikti == "yasak", f"torun surec yasagi devralmadi: {cikti!r}"


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="M-10: yasagin tek tasiyicisi ortam degiskenidir; kosu icinde silinirse (os.environ.pop/clear "
                          "ya da temiz ortamli subprocess) sonradan baslatilan surec yasagi almaz")
def test_kosu_icinde_ortam_degiskeni_silinse_de_alt_surec_yasagi_devralir(onbellek):
    """On-kayit §3 rev.13: ag yasagi ortam temizlemeyle delinmemeli. Surecin kendi durumu (`_KOSU_AGSIZ`) hala yasakli
    oldugundan alt surec de yasakli olmali; ortam degiskeni tek kaynak olmamali."""
    mf.manifest_kur()
    with split.kesif_kosusu():
        os.environ.pop(bv._AG_YASAGI_ORTAM_ADI, None)
        assert bv._ag_yasak_mi()  # ust surecte yasak surer
        cikti = _calistir(_ALT_SUREC, str(config.KOK))
    assert cikti == "yasak", f"ortam temizlendikten sonra baslayan surec yasagi almadi: {cikti!r}"


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="M-12: kosu_agsiz.__exit__ eslesmemis cagrida sayaci dusurur; calisan kosunun yasagi kalkar "
                          "ve sayac negatif kalip sonraki kosularin yasagini da bozar")
def test_eslesmemis_kosu_agsiz_cikisi_calisan_kosunun_yasagini_kaldirmaz(onbellek):
    """On-kayit §3 rev.13: acik kosu boyunca yasak surer. Hic girilmemis bir `kosu_agsiz` nesnesinin `__exit__`i
    sayaci dusurmemeli (reddedilmeli ya da yok sayilmali)."""
    mf.manifest_kur()
    yasakli = None
    try:
        with split.kesif_kosusu():
            try:
                bv.kosu_agsiz().__exit__(None, None, None)
            except Exception:  # noqa: BLE001 (reddedilmesi guvenli)
                pass
            yasakli = bv._ag_yasak_mi()
    finally:
        bv._KOSU_AGSIZ["sayac"] = 0  # testin kirletecegi surec durumunu onar
        bv._KOSU_AGSIZ["devralinan"] = False
        os.environ.pop(bv._AG_YASAGI_ORTAM_ADI, None)
    assert yasakli, "eslesmemis cikis calisan kosunun ag yasagini kaldirdi"


# M-11 kapandi (RESULTS §14.45; S-10 ile ayni acik): `_pytest_testi` `pytest_configure` isaretine dayanir.
def test_pytest_adi_ortam_degiskeni_taklit_edilerek_manifest_denetimi_kapatilamaz():
    """On-kayit §3 rev.13: manifest denetimi pytest disinda her zaman calisir. `PYTEST_CURRENT_TEST` ayarlayip `pytest`i
    ice aktaran bir surec, denetimi kapatamamali (ayrica `_test_manifest_ayarla` ile sahte manifest dayatamamali)."""
    betik = ("import sys; sys.path.insert(0, sys.argv[1])\nimport pytest\n"
             "from data import onbellek_manifest as mf\nprint(mf.denetim_etkin())\n")
    ortam = {**os.environ, "PYTEST_CURRENT_TEST": "sahte.py::sahte_test (call)"}
    cikti = subprocess.run([sys.executable, "-B", "-c", betik, str(config.KOK)], capture_output=True, text=True,
                           env=ortam, timeout=120)
    if cikti.returncode != 0:
        pytest.fail(f"alt surec coktu: {cikti.stderr[-500:]}")
    assert cikti.stdout.split() == ["True"], f"denetim ortam taklidiyle kapandi: {cikti.stdout!r}"


# --- Tarama: takma ad ve gizleme -----------------------------------------------------------------------------------


def _tara(tmp_path, metin: str, uzanti: str = ".py", ad: str = "sahte") -> bool:
    """Her cagri kendi kokunde calisir; onceki cagrinin dosyasi sonucu etkilemez."""
    kok = tmp_path / f"kok_{ad}"
    (kok / "study").mkdir(parents=True, exist_ok=True)
    (kok / "study" / f"{ad}{uzanti}").write_text(metin, encoding="utf-8")
    return bool(ihlaller(ONBELLEK_DESENI, kok=kok, uzantilar=ONBELLEK_UZANTILARI))


_TAM = "ｂｖ"  # "ｂｖ": NFKC ile "bv"


# M-5 kapandi (RESULTS §14.45; S-13 ile ayni acik): tarama NFKC ile normallesmis metne bakar.
@pytest.mark.parametrize("duz, gizli, kontrol", [
    ("from data import klines\nx = klines.bv\n", f"from data import klines\nx = klines.{_TAM}\n",
     lambda ns: ns["x"] is bv),
    ("from data import onbellek_manifest as m\n", "from data import ｏnbellek_manifest as m\n",
     lambda ns: ns["m"] is mf),
    ("import config\nx = config.ONBELLEK_DIZINI\n", "import config\nx = config.ＯNBELLEK_DIZINI\n",
     lambda ns: ns["x"] == config.ONBELLEK_DIZINI),
])
def test_tam_genislikli_kimlik_onbellek_taramasindan_kacamaz(tmp_path, duz, gizli, kontrol):
    """CLAUDE.md §3.3 ve `ONBELLEK_DESENI`: analiz kodu onbellek/ag katmanina ulasamaz. NFKC-esdeger yazim ayni nesneye
    ulastigi icin ayni sekilde yakalanmali."""
    if not _tara(tmp_path, duz, ad="duz"):
        pytest.fail("on kosul: duz yazim taramada yakalanmali")
    ns: dict = {}
    exec(compile(gizli, "<sahte>", "exec"), ns)  # noqa: S102 (yalnizca ad cozumleme)
    assert kontrol(ns), "tam genislikli ad ayni nesneye cozumlenmedi (test varsayimi)"
    assert _tara(tmp_path, gizli, ad="gizli"), "tam genislikli kimlik taramadan kacti"


def _defter(kaynak_json: str) -> str:
    return ('{"cells": [{"cell_type": "code", "execution_count": null, "metadata": {}, "outputs": [], "source": '
            + kaynak_json + '}], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}')


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="M-6: .ipynb kaynak satirlari birlestirilir ve JSON \\uXXXX kacislari cozulur; desen ham metne "
                          "bakar")
@pytest.mark.parametrize("kaynak_json", [
    '["from data import klines\\n", "klines.b", "v.kosu_agsiz()\\n"]',
    '["from data import klines\\n", "klines.\\u0062v.kosu_agsiz()\\n"]',
], ids=["satir_parcalama", "unicode_kacisi"])
def test_ipynb_json_gizlemesi_onbellek_taramasindan_kacamaz(tmp_path, kaynak_json):
    """`ONBELLEK_DESENI` `.ipynb` dosyalarini da tarar. Hucre kaynagi satir listesinden birlestirildigi ve JSON kacislari
    cozuldugu icin ham metinde gorunmeyen `bv` yine de calisir; tarama bunu yakalamali."""
    cozulen = "".join(json.loads(kaynak_json))
    assert "klines.bv.kosu_agsiz" in cozulen
    assert _tara(tmp_path, _defter('["from data import klines\\n", "klines.bv.kosu_agsiz()\\n"]'), ".ipynb", "duz"), \
        "on kosul: duz defter yakalanmali"
    assert _tara(tmp_path, _defter(kaynak_json), ".ipynb", "gizli"), "gizlenmis defter taramadan kacti"


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="M-7: kaynak kodlama bildirimi (# coding: utf-7) ile 'bv' ham baytlarda base64 olarak durur; "
                          "tarama UTF-8 okur")
def test_utf7_kodlama_bildirimi_onbellek_taramasindan_kacamaz(tmp_path):
    """`ONBELLEK_DESENI`: analiz kodu `bv`ye ulasamaz. Python PEP 263 ile kaynagi baska kodlamada okur; tarama yalniz
    UTF-8 gordugu icin `+AGIAdg-` ("bv") yakalanmaz."""
    govde = b"# -*- coding: utf-7 -*-\nfrom data import klines\nklines.+AGIAdg-.kosu_agsiz()\n"
    try:
        agac = ast.parse(govde)
    except (SyntaxError, LookupError, ValueError):
        pytest.skip("Python bu kaynak kodlamasini kabul etmiyor")
    if "bv" not in [dugum.attr for dugum in ast.walk(agac) if isinstance(dugum, ast.Attribute)]:
        pytest.skip("kodlama beklenen adi uretmedi")
    (tmp_path / "study").mkdir()
    (tmp_path / "study" / "sahte.py").write_bytes(govde)
    assert ihlaller(ONBELLEK_DESENI, kok=tmp_path, uzantilar=ONBELLEK_UZANTILARI), "utf-7 kaynak taramadan kacti"


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="M-8: desendeki (?!False\\b) onbakisi 'False or True' gibi ifadeleri 'False' ile basladigi icin "
                          "gecirir; deger yine de True'dur")
@pytest.mark.parametrize("ifade", ["False or True", "False|True", "False if x else True", "False or flag",
                                   "False!=flag", "False and False or True"])
def test_yenile_ifadesi_false_ile_baslayip_true_olunca_taramadan_kacamaz(tmp_path, ifade):
    """RESULTS §14.41: `yenile` degeri `False` disinda her sey yakalanir. `False`la baslayan ama True degerlenen bir
    ifade (aga cikan guncelleme yolu) da yakalanmali."""
    assert eval(ifade, {"x": False, "flag": True}), "on kosul: ifade True degerlenmeli"  # noqa: S307
    assert _tara(tmp_path, "klines.mumlari_yukle(s, '4h', 'KESIF', yenile=True)\n", ad="duz"), "on kosul"
    assert _tara(tmp_path, f"klines.mumlari_yukle(s, '4h', 'KESIF', yenile={ifade})\n", ad="gizli"), \
        f"yenile={ifade} taramadan kacti"


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="M-8: eslem anahtari biciminde de 'False or True' kacar")
def test_yenile_eslem_anahtari_ifadesi_taramadan_kacamaz(tmp_path):
    """RESULTS §14.41: `{"yenile": ...}` bicimi de `False`tan baska her degeri yakalamali."""
    assert _tara(tmp_path, "klines.mumlari_yukle(s, '4h', 'KESIF', **{'yenile':False or True})\n"), \
        "eslem anahtari ifadesi taramadan kacti"


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="M-9: yenile konumsal gecirilebilir (5. konumsal arguman); desen yalnizca anahtar sozcuge "
                          "bakar ve imza anahtar-sozcuk-yalniz degildir")
def test_yenile_konumsal_gecirilemez_ya_da_taramada_yakalanir(tmp_path):
    """RESULTS §14.41: aga cikan guncelleme bayragi taramadan kacmamali. Ya `yenile` anahtar-sozcuk-yalniz olmali ya da
    konumsal kullanim taranmali."""
    kaynaklar = {
        klines.mumlari_yukle: "klines.mumlari_yukle(s, '4h', 'KESIF', False, True)\n",
        funding_modulu.funding_yukle: "funding.funding_yukle(s, 'KESIF', False, True)\n",
    }
    for sira, (islev, kaynak) in enumerate(kaynaklar.items()):
        tur = inspect.signature(islev).parameters["yenile"].kind
        korumali = tur is inspect.Parameter.KEYWORD_ONLY or _tara(tmp_path, kaynak, ad=f"k{sira}")
        assert korumali, f"{islev.__name__}: yenile konumsal gecirilebilir ve tarama yakalamiyor"


def test_kapili_yukleyici_cagrisi_yeni_tarama_desenlerinde_yanlis_alarm_vermez(tmp_path):
    """RESULTS §14.41: desen sinirlari asiri genisletilmemeli; kapili yukleyici ve `kesif_kosusu` temiz kalir."""
    assert not _tara(tmp_path, "with split.kesif_kosusu():\n    klines.mumlari_yukle(s, '4h', 'KESIF')\n"
                               "    funding.funding_yukle(s, 'KESIF', yenile=False)\n")
