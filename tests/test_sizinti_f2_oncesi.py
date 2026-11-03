"""F2 oncesi bloklayicilar turunun sizinti testleri (RESULTS §14.42: D-B1, D-B2, D-C1, D-C2, D-C4, M-1, M-3, M-15, M-16).

Amac kodu KIRMAKTIR. Basarili bir saldiri `xfail(strict=True, raises=AssertionError)` ile isaretlidir: govde GUVENLI
davranisi iddia eder, bugunku kod o iddiayi bozar. Kurulum hatalari (RuntimeError, CalledProcessError, ...) xfail arkasina
saklanmaz; acik hata olarak gorunur. Gecici onbellek, gecici manifest ve gecici git deposu kullanilir; aga cikilmaz,
gercek `cache/` dosyalarina yazilmaz. Getiri, sinyal degeri ya da olay sayisi hesaplanmaz ya da yazdirilmaz.

Dayanaklar: CLAUDE.md §3.2-3.3 (veri bolmesi, onay kumesi tek atis), §5 (koruma katmani, onbellek kopyalari), on-kayit §3
rev.13 ("F2 ve F3 kosulari aga cikmaz", dondurulmus yerel onbellek).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pandas as pd
import pytest

import config
from conftest import sahte_4h
from data import binance_vision as bv
from data import funding as funding_modulu
from data import klines, kume_bellegi, onbellek_manifest as mf
from data import pozisyon, sinyal, split
from kapi_yardimcisi import veri
from onay_yardimcisi import gecici_depo, git

A_SEMBOL = "SOLUSDT"
AY = "2021-01"
AYLAR = ("2025-07", "2025-08", "2025-09", "2026-08", "2026-09")


# --- Ortak yardimcilar ---------------------------------------------------------------------------------------------


def _a_sembolu() -> str:
    tablo = split.split_oku()
    tek = tablo.loc[(tablo["grup"] == "A") & (tablo["sembol"] == tablo["varlik_anahtari"]), "sembol"]
    return str(tek.iloc[0])


def _b_sembolu() -> str:
    tablo = split.split_oku()
    return str(tablo.loc[tablo["grup"] == "B", "sembol"].iloc[0])


def _mum_anahtari(sembol: str, bar: str, ay: str) -> str:
    return f"{bv.MUM_ONEKI}/{sembol}/{bar}/{sembol}-{bar}-{ay}.zip"


def _funding_anahtari(sembol: str, ay: str) -> str:
    return f"{bv.FUNDING_ONEKI}/{sembol}/{sembol}-fundingRate-{ay}.zip"


def _liste_yaz(icerik: dict) -> None:
    yol = bv.donuk_liste_yolu()
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(icerik), encoding="utf-8")
    bv.donuk_bellek_temizle()


def _funding_cercevesi(ay: str) -> pd.DataFrame:
    return pd.DataFrame({"odeme_zamani": pd.date_range(f"{ay}-01", periods=3, freq="8h", tz="UTC"),
                         "aralik_saat": 8.0, "oran": 0.0001})


def _ayni_boyda_degistir(yol: Path) -> None:
    govde = bytearray(yol.read_bytes())
    govde[len(govde) // 2] ^= 0xFF
    yol.write_bytes(bytes(govde))


def _reddedildi(cagri) -> bool:
    """Cagri herhangi bir hatayla reddedildiyse True; sessizce deger dondurduyse False."""
    try:
        cagri()
    except Exception:  # noqa: BLE001  (hangi hata turu olursa olsun ret sayilir)
        return True
    return False


@pytest.fixture
def acilanlar(monkeypatch):
    """`bv.onbellekten_oku` cagrilarinin ay adlarini (dosya govdesi) kaydeder; cagriyi aynen gecirir."""
    liste: list[str] = []
    gercek = bv.onbellekten_oku

    def sarmal(yol):
        liste.append(Path(yol).stem)
        return gercek(yol)

    monkeypatch.setattr(bv, "onbellekten_oku", sarmal)
    return liste


# --- Hedef 1: ay elemesi -------------------------------------------------------------------------------------------


@pytest.fixture
def ay_onbellegi(monkeypatch, tmp_path):
    """A sembolu icin 4h, birincil 1d ve funding dosyalari; C2 aylari ve C2 sonrasi dahil. Manifest yok."""
    kok = tmp_path / "onbellek"
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", kok)
    bv.donuk_bellek_temizle()
    kume_bellegi.temizle()
    a = _a_sembolu()
    for ay in AYLAR:
        sahte_4h(f"{ay}-01 00:00", 12).to_parquet(bv.onbellek_yolu("klines", a, config.BAR_4H, f"{ay}.parquet"),
                                                  index=False)
        sahte_4h(f"{ay}-01 00:00", 6).to_parquet(bv.onbellek_yolu("klines_birincil_1d", a, f"{ay}.parquet"),
                                                 index=False)
        _funding_cercevesi(ay).to_parquet(bv.onbellek_yolu("funding", a, f"{ay}.parquet"), index=False)
    _liste_yaz({"mum": {a: {config.BAR_4H: [_mum_anahtari(a, config.BAR_4H, ay) for ay in AYLAR],
                            config.BAR_1D: [_mum_anahtari(a, config.BAR_1D, ay) for ay in AYLAR]}},
                "funding": {a: [_funding_anahtari(a, ay) for ay in AYLAR]}})
    yield a
    bv.donuk_bellek_temizle()
    kume_bellegi.temizle()


def test_kesif_birincil_gunluk_yolu_c2_ayini_acmaz(ay_onbellegi, acilanlar):
    """On-kayit §3 / D-B1: `birincil_gunluk_indir` KESIF yuklemesi yalnizca KESIF aylarinin dosyasini acar."""
    with bv.agsiz_okuma():
        klines.birincil_gunluk_indir(ay_onbellegi, "KESIF")
    assert set(acilanlar) == {"2025-07", "2025-08"}


def test_kesif_funding_yolu_c2_ayini_acmaz(ay_onbellegi, acilanlar):
    """On-kayit §3 / D-B1: funding KESIF yuklemesi (kume araligiyla) C2 aylarinin dosyasini acmaz."""
    with bv.agsiz_okuma():
        funding_modulu.ham_funding_yukle(ay_onbellegi, aralik=split.kume_araligi("KESIF"))
    assert set(acilanlar) == {"2025-07", "2025-08"}


def test_kesif_4h_yolu_c2_ayini_acmaz(ay_onbellegi, acilanlar):
    """On-kayit §3 / D-B1: 4h KESIF yuklemesi yalnizca KESIF aylarini acar (1d turetmesi dahil)."""
    bas, son = split.kume_araligi("KESIF")
    with bv.agsiz_okuma():
        klines.ham_mumlari_yukle(ay_onbellegi, config.BAR_4H, aralik=(bas, son))
        klines.ham_mumlari_yukle(ay_onbellegi, config.BAR_1D, aralik=(bas, son))
    assert set(acilanlar) == {"2025-07", "2025-08"}


@pytest.mark.parametrize("yukleyici", ["mum4h", "mum1d", "funding", "birincil1d"])
def test_aralik_verilmeyen_ham_yukleyici_kesif_sembolunde_bile_c2_ayini_izinsiz_acamaz(ay_onbellegi, yukleyici):
    """D-B1: `aralik=None` eski davranisi (butun gecmis) izin olmadan C2 aylarina ulasamaz."""
    a = ay_onbellegi
    cagri = {
        "mum4h": lambda: klines.ham_mumlari_yukle(a, config.BAR_4H),
        "mum1d": lambda: klines.ham_mumlari_yukle(a, config.BAR_1D),
        "funding": lambda: funding_modulu.ham_funding_yukle(a),
        "birincil1d": lambda: klines.ham_birincil_gunluk_indir(a),
    }[yukleyici]
    with bv.agsiz_okuma(), pytest.raises(bv.OnayVerisiKorumasi):
        cagri()


@pytest.mark.parametrize("yukleyici", ["mum4h", "funding", "birincil1d"])
def test_kesif_basi_c2_sonu_genis_aralik_izinsiz_c2_ayi_acamaz(ay_onbellegi, acilanlar, yukleyici):
    """D-B1: ay elemesi araligi genis verilirse C2 aylari listeye girer, ama izin denetimi onlari yine reddeder."""
    a = ay_onbellegi
    aralik = (split.kume_araligi("KESIF")[0], split.kume_araligi("C2")[1])
    cagri = {
        "mum4h": lambda: klines.ham_mumlari_yukle(a, config.BAR_4H, aralik=aralik),
        "funding": lambda: funding_modulu.ham_funding_yukle(a, aralik=aralik),
        "birincil1d": lambda: klines.ham_birincil_gunluk_indir(a, aralik=aralik),
    }[yukleyici]
    with bv.agsiz_okuma(), pytest.raises(bv.OnayVerisiKorumasi):
        cagri()
    assert not [m for m in acilanlar if m[:7] >= "2025-09"]


def test_b_sembolu_kesif_araligiyla_bile_izinsiz_yuklenemez(ay_onbellegi):
    """CLAUDE.md §3.2: B grubu sembolun hicbir ayi KESIF araligi verilerek izinsiz acilamaz."""
    b = _b_sembolu()
    _liste_yaz({"mum": {b: {config.BAR_4H: [_mum_anahtari(b, config.BAR_4H, "2025-07")]}}, "funding": {}})
    sahte_4h("2025-07-01 00:00", 12).to_parquet(bv.onbellek_yolu("klines", b, config.BAR_4H, "2025-07.parquet"),
                                                index=False)
    with bv.agsiz_okuma(), pytest.raises(bv.OnayVerisiKorumasi):
        klines.ham_mumlari_yukle(b, config.BAR_4H, aralik=split.kume_araligi("KESIF"))


@pytest.mark.parametrize("ad", [
    "{s}-4h-2025-09-2020-01.zip",       # ilk ay C2, son iki parca KESIF: filtre ve izin denetimi farkli ay okur
    "{s}-4h-2020-01-2025-09.zip",       # ters
    "{s}-4h-2025-9.zip",                # tek haneli ay
    "{s}-4h-2025-09.ZIP",               # buyuk harf uzanti
    "{s}-4h-2025-09.zip ",              # sonda bosluk
    "{s}-4h-2025-09.parquet.zip",       # cifte uzanti
    "{s}-4h-2025-09.zip.bak",           # zip degil
])
def test_tuhaf_dosya_adlari_kesif_yuklemesine_c2_ayi_actirmaz(ay_onbellegi, acilanlar, ad):
    """D-B1: dondurulmus listede tuhaf adli bir anahtar KESIF yuklemesinde C2 ayinin dosyasini actirmaz.

    Ya liste asamasinda `OnayVerisiKorumasi` (kapali yon) ya da yalnizca KESIF aylari acilir."""
    a = ay_onbellegi
    tuhaf = f"{bv.MUM_ONEKI}/{a}/{config.BAR_4H}/" + ad.format(s=a)
    _liste_yaz({"mum": {a: {config.BAR_4H: [_mum_anahtari(a, config.BAR_4H, "2025-08"), tuhaf]}}, "funding": {}})
    try:
        with bv.agsiz_okuma():
            klines.ham_mumlari_yukle(a, config.BAR_4H, aralik=split.kume_araligi("KESIF"))
    except (bv.OnayVerisiKorumasi, bv.AgsizOkumaIhlali, bv.DonukListeYok):
        pass
    assert not [m for m in acilanlar if m[:7] >= "2025-09"], acilanlar


def test_aylara_gore_ele_kenar_aylari_ve_yol_bicimleri():
    """D-B1: ilk/son ay dahil, bir oncesi/sonrasi haric; ters bolulu yol ve Path anahtari da elenir."""
    a = "SOLUSDT"
    anahtarlar = [f"d/{a}-4h-{ay}.zip" for ay in ("2019-12", "2020-01", "2025-08", "2025-09")]
    anahtarlar += [f"d\\{a}-4h-2025-09.zip", Path(f"d/{a}-4h-2025-09.zip"), "p\\2025-09.parquet", "p/2020-01.parquet"]
    kalan = [str(k).replace("\\", "/") for k in bv.aylara_gore_ele(anahtarlar, ("2020-01", "2025-08"))]
    assert kalan == [f"d/{a}-4h-2020-01.zip", f"d/{a}-4h-2025-08.zip", "p/2020-01.parquet"]


@pytest.mark.parametrize("bas, son", [
    (pd.NaT, pd.NaT),
    (None, None),
    (0, 1),
    ("", ""),
    ("2020-01-01", "2025-08-31 23:59:59"),                                   # saat dilimsiz metin
    ("2020-01-01T00:00:00+03:00", "2025-08-31T23:59:59+00:00"),              # kaymis baslangic
    (pd.Timestamp("2020-01-01", tz="UTC"), pd.NaT),
    (pd.Timestamp("2020-01-01", tz="UTC"), pd.Timestamp("2025-08-31 23:59:59.999999999", tz="UTC")),
])
def test_ay_siniri_bozuk_girdiler_ay_araligi_uretmez(bas, son):
    """D-B1: ay sinirina denk gelmeyen ya da bozuk aralik sessizce yuvarlanmaz, ay listesi uretmez."""
    assert _reddedildi(lambda: bv.ay_araligi_sinirlari(bas, son))


# --- Hedef 2: kesif kosusunun commit bagi ------------------------------------------------------------------------


@pytest.fixture
def depo(monkeypatch, tmp_path):
    """Gercek git test deposu: manifest, split.csv, universe.csv commit edilmis; onbellek depo disinda."""
    kok = tmp_path / "onbellek"
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", kok)
    bv.donuk_bellek_temizle()
    kume_bellegi.temizle()
    sahte_4h(f"{AY}-01 00:00", 12).to_parquet(bv.onbellek_yolu("klines", A_SEMBOL, config.BAR_4H, f"{AY}.parquet"),
                                              index=False)
    _liste_yaz({"mum": {A_SEMBOL: {config.BAR_4H: [_mum_anahtari(A_SEMBOL, config.BAR_4H, AY)]}}, "funding": {}})
    d = gecici_depo(tmp_path)
    (d / "data").mkdir()
    for ad, kaynak in (("SPLIT_CSV", config.SPLIT_CSV), ("UNIVERSE_CSV", config.UNIVERSE_CSV)):
        hedef = d / "data" / kaynak.name
        shutil.copyfile(kaynak, hedef)
        monkeypatch.setattr(config, ad, hedef)
    mf._test_manifest_ayarla(d / "data" / "onbellek_manifest.csv")
    mf.manifest_kur()
    git(d, "add", "data")
    git(d, "commit", "-q", "-m", "veri")
    yield d
    bv.donuk_bellek_temizle()
    kume_bellegi.temizle()


def _acilir_mi() -> bool:
    """Kesif kosusu acilip kapandi mi; commit bagi ya da manifest hatasiyla reddedildiyse False."""
    try:
        with split.kesif_kosusu():
            pass
    except (split.KesifBagiHatasi, mf.ManifestHatasi):
        return False
    return True


@pytest.mark.parametrize("bayrak", ["--assume-unchanged", "--skip-worktree"])
@pytest.mark.parametrize("dosya", ["onbellek_manifest.csv", "split.csv", "universe.csv"])
def test_git_dizininde_gizlenmis_kirli_bagli_dosya_kesif_kosusunu_acmamali(depo, bayrak, dosya):
    """D-B2: manifest, split.csv, universe.csv calisma agacinda HEAD'dekiyle AYNI olmali (RESULTS §14.42)."""
    yol = depo / "data" / dosya
    git(depo, "update-index", bayrak, f"data/{dosya}")
    yol.write_bytes(yol.read_bytes() + b"\n")
    assert not _acilir_mi(), f"{dosya} HEAD'den farkli ama git dizininde gizlendigi icin kosu acildi"


def test_autocrlf_ile_crlf_manifest_kayittaki_ozeti_head_baytlarina_baglamali(depo):
    """D-B2: kayittaki `manifest_sha256` HEAD'deki manifest baytlarinin ozeti olmali ya da kosu acilmamali."""
    git(depo, "config", "core.autocrlf", "true")
    yol = mf._etkin_yol()
    yol.write_bytes(yol.read_bytes().replace(b"\n", b"\r\n"))
    commitli = subprocess.run(["git", "cat-file", "blob", "HEAD:data/onbellek_manifest.csv"], cwd=depo, check=True,
                              capture_output=True).stdout
    beklenen = hashlib.sha256(commitli).hexdigest()
    try:
        with split.kesif_kosusu() as kayit:
            sabitlenen = kayit.manifest_sha256
    except (split.KesifBagiHatasi, mf.ManifestHatasi):
        return
    assert sabitlenen == beklenen, "kosu, commit edilmemis (CRLF) manifest baytlarina baglandi"


def test_git_kontrolunden_sonra_ozetlemeden_once_degisen_manifest_kosuyu_acmamali(depo, monkeypatch):
    """D-B2: acilis ile dogrulama arasinda manifest degisirse kosu acilmamali."""
    yol = mf._etkin_yol()
    durum = {"yapildi": False}
    gercek = subprocess.run

    def sarmal(*arguman, **anahtar):
        sonuc = gercek(*arguman, **anahtar)
        komut = arguman[0] if arguman else anahtar.get("args")
        # RESULTS §14.43: bag artik `git diff` degil `git cat-file blob HEAD:<yol>` ile kurulur; yaris noktasi o cagri.
        if (not durum["yapildi"] and isinstance(komut, list) and ("diff" in komut or "cat-file" in komut)
                and str(komut[-1]).endswith("onbellek_manifest.csv")):
            durum["yapildi"] = True
            yol.write_bytes(yol.read_bytes() + b"\n")  # git kontrolu gectikten HEMEN sonra
        return sonuc

    monkeypatch.setattr(subprocess, "run", sarmal)
    acildi = _acilir_mi()
    if not durum["yapildi"]:  # kurulum hatasi xfail arkasina saklanmaz (AssertionError degil)
        raise RuntimeError("kurulum: manifest icin `git diff` / `git cat-file` cagrisi yakalanamadi")
    assert not acildi, "manifest git kontrolunden sonra degisti ama kosu acildi"


def test_joker_karakterli_dosya_adi_git_kontrolunu_baska_dosyaya_yonlendiremez(depo, monkeypatch):
    """D-B2: bagli dosya GERCEKTEN git'te izlenmeli; adinin pathspec olarak baska dosyaya eslenmesi sayilmaz."""
    kaynak = config.SPLIT_CSV
    (depo / "data" / "split1.csv").write_bytes(kaynak.read_bytes())
    git(depo, "add", "data/split1.csv")
    git(depo, "commit", "-q", "-m", "tuzak")
    tuhaf = depo / "data" / "split[1].csv"
    tuhaf.write_bytes(kaynak.read_bytes() + b"\n")  # izlenmiyor ve kirli
    monkeypatch.setattr(config, "SPLIT_CSV", tuhaf)
    assert not _acilir_mi(), "izlenmeyen `split[1].csv` baska bir izlenen dosyanin adina eslenerek temiz sayildi"


def test_onbellek_dizini_degistirilmis_kopya_kesif_kosusunu_acmaz(depo, monkeypatch, tmp_path):
    """D-B2 / on-kayit §3: ONBELLEK_DIZINI baska bir kopyaya yonlendirilip dosya ayni boyda bozulursa kosu acilmaz."""
    kopya = tmp_path / "onbellek_kopya"
    shutil.copytree(config.ONBELLEK_DIZINI, kopya)
    _ayni_boyda_degistir(kopya / "klines" / A_SEMBOL / config.BAR_4H / f"{AY}.parquet")
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", kopya)
    assert not _acilir_mi()
    assert bv._KOSU_AGSIZ["sayac"] == 0


def test_onbellek_dizinine_manifestte_olmayan_dosya_eklenirse_kosu_acilmaz(depo):
    """D-B2: manifestte olmayan ek bir onbellek dosyasi (ornegin sert baglanti) acilista yakalanir."""
    ek = config.ONBELLEK_DIZINI / "klines" / A_SEMBOL / config.BAR_4H / "2021-02.parquet"
    shutil.copyfile(ek.parent / f"{AY}.parquet", ek)
    assert not _acilir_mi()


def test_kosu_icinde_ilk_okumadan_once_degisen_dosya_okunmaz(depo):
    """D-C4 / D-B2: acilistan sonra, ilk okumadan once ayni boyda bozulan dosya okunmaz; kapanis da hata verir."""
    hedef = config.ONBELLEK_DIZINI / "klines" / A_SEMBOL / config.BAR_4H / f"{AY}.parquet"
    sonuc = {}
    with pytest.raises(split.KesifBagiHatasi):
        with split.kesif_kosusu():
            _ayni_boyda_degistir(hedef)
            try:
                bv.onbellekten_oku(hedef)
                sonuc["okundu"] = True
            except mf.ManifestUyusmazligi:
                sonuc["okundu"] = False
    assert sonuc["okundu"] is False


def test_kosu_icinde_eklenen_yeni_dosya_okunmaz(depo):
    """D-C4: kosu sirasinda eklenen, manifestte olmayan dosya okunmaz; kapanista kesif katmani uyusmazligi yazilir."""
    yeni = config.ONBELLEK_DIZINI / "klines" / A_SEMBOL / config.BAR_4H / "2021-02.parquet"
    sonuc = {}
    with pytest.raises(split.KesifBagiHatasi):
        with split.kesif_kosusu():
            shutil.copyfile(yeni.parent / f"{AY}.parquet", yeni)
            try:
                bv.onbellekten_oku(yeni)
                sonuc["okundu"] = True
            except mf.ManifestUyusmazligi:
                sonuc["okundu"] = False
    assert sonuc["okundu"] is False


# --- Hedef 3: karar noktasi baglami ------------------------------------------------------------------------------

T = pd.Timestamp("2021-03-01 00:00", tz="UTC")


@pytest.fixture
def manifestli(monkeypatch, tmp_path):
    """Gecici onbellek + gecici manifest (denetim etkin). A ve B dosyalarinin icerigi farklidir."""
    kok = tmp_path / "onbellek"
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", kok)
    mf._test_manifest_ayarla(tmp_path / "onbellek_manifest.csv")
    bv.donuk_bellek_temizle()
    kume_bellegi.temizle()
    sahte_4h(f"{AY}-01 00:00", 12, hacim=1_000_000.0).to_parquet(
        bv.onbellek_yolu("klines", A_SEMBOL, config.BAR_4H, f"{AY}.parquet"), index=False)
    sahte_4h(f"{AY}-01 00:00", 12, hacim=7_777_777.0).to_parquet(
        bv.onbellek_yolu("klines", _b_sembolu(), config.BAR_4H, f"{AY}.parquet"), index=False)
    _liste_yaz({"mum": {}, "funding": {}})
    mf.manifest_kur()
    yield kok
    bv.donuk_bellek_temizle()
    kume_bellegi.temizle()


def _a(kok: Path) -> Path:
    return kok / "klines" / A_SEMBOL / config.BAR_4H / f"{AY}.parquet"


def _b(kok: Path) -> Path:
    return kok / "klines" / _b_sembolu() / config.BAR_4H / f"{AY}.parquet"


def _sentetik():
    zaman = pd.date_range("2021-01-01", periods=275, freq="8h", tz="UTC")
    fr = pd.DataFrame({"odeme_zamani": zaman, "aralik_saat": 8.0, "oran": 0.0001, "oran_8h": 0.0001})
    return veri(sahte_4h("2021-01-01", 540, hacim=1e10), fr, pd.Timestamp("2021-01-01 00:00", tz="UTC"),
                pd.Timestamp("2021-04-30 20:00", tz="UTC"))


def _karar(kimlik, ikincil: bool = False, hipotez: str = "H2"):
    bar = config.HIPOTEZ_IZGARASI[hipotez]
    birincil = config.BIRINCIL_UFUK[bar]
    ufuk = config.IKINCIL_UFUKLAR[bar][0] if ikincil else birincil
    hacim = config.ASGARI_HACIM_4H if bar == config.BAR_4H else config.ASGARI_HACIM_1D
    return pozisyon.olay_karari(T, ufuk, bar, hipotez=hipotez, yapilandirma=sinyal.izgara(hipotez)[0], rol="olay",
                                capa=None, birincil_ufuk=birincil, kume="KESIF", asgari_hacim=hacim,
                                asgari_listeleme_yasi_gun=config.ASGARI_LISTELEME_YASI_GUN, **kimlik)


def _kosul(kimlik, hipotez: str = "H2"):
    return pozisyon.sinyal_kosulu(T, hipotez=hipotez, yapilandirma=sinyal.izgara(hipotez)[0], capa=None,
                                  kume="KESIF", **kimlik)


def _sonuc(fn) -> str:
    try:
        fn()
    except split.KesifBaglamiYok:
        return "baglam yok"
    except Exception:  # noqa: BLE001  (olay olusmaz, veri hatasi: baglam denetimi gecilmis)
        return "gecti"
    return "gecti"


def test_ikincil_ufuk_ozyinelemesi_kesif_baglami_denetimini_atlatmaz(manifestli):
    """D-C1: ufuk != birincil ufuk oldugunda karar noktasi kendini cagirir; ic cagri da baglam ister."""
    assert _sonuc(lambda: _karar(_sentetik(), ikincil=True)) == "baglam yok"


def test_kapanan_baglamdan_sonra_calisan_is_parcacigi_karar_noktasini_acamaz(manifestli):
    """D-C1: kosu icinde baslatilip kosu kapandiktan sonra calisan is parcacigi bagliami devralmis olmaz."""
    kimlik = _sentetik()
    olay = threading.Event()
    sonuc: dict[str, str] = {}

    def is_parcacigi():
        olay.wait(10)
        sonuc["karar"] = _sonuc(lambda: _karar(kimlik))
        sonuc["kosul"] = _sonuc(lambda: _kosul(kimlik))

    parcacik = threading.Thread(target=is_parcacigi)
    with split.kesif_kosusu():
        parcacik.start()
    olay.set()
    parcacik.join(30)
    assert sonuc == {"karar": "baglam yok", "kosul": "baglam yok"}


def test_ic_ice_kesif_kosusunun_kapanisi_dis_kosunun_baglamini_ve_ag_yasagini_dusurmez(manifestli):
    """D-C1: sayac mantigi; ic kosu kapaninca dis kosu acik kalir, kapaninca ikisi de kapanir."""
    with split.kesif_kosusu():
        with split.kesif_kosusu():
            assert split.kesif_kosusu_acik()
        assert split.kesif_kosusu_acik() and bv._ag_yasak_mi()
        assert os.environ.get(split._KESIF_ORTAM_ADI) == str(os.getpid())
    assert not split.kesif_kosusu_acik() and not bv._ag_yasak_mi()
    assert os.environ.get(split._KESIF_ORTAM_ADI) is None


def test_hatayla_biten_ic_kosu_dis_kosunun_baglamini_dusurmez(manifestli):
    """D-C1: ic kosuda atilan hata sayaci bozmaz."""
    with split.kesif_kosusu():
        with pytest.raises(ValueError):
            with split.kesif_kosusu():
                raise ValueError("ic")
        assert split.kesif_kosusu_acik()
    assert split._KESIF_DURUMU["sayac"] == 0


_ALT_KESIF = ("import sys; sys.path.insert(0, sys.argv[1])\n"
              "from data import split\n"
              "print(split.kesif_kosusu_acik())\n")
_ALT_IZIN = ("import sys; sys.path.insert(0, sys.argv[1])\n"
             "from data import binance_vision as bv\n"
             "print(bv.onay_izni_var())\n")


def _alt_surec(kod: str, ortam: dict) -> str:
    return subprocess.run([sys.executable, "-B", "-c", kod, str(config.KOK)], capture_output=True, text=True,
                          check=True, env=ortam).stdout.strip()


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="F-5: ortam degiskenini KENDI pid'iyle ayarlayip alt surec baslatan herhangi bir betik, "
                          "kesif kosusu acmadan KESIF baglamini 'devralmis' olur (pid denetimi bunu elemez)")
def test_elle_kurulmus_ust_pid_degiskeni_alt_surece_kesif_baglami_vermemeli(manifestli):
    """D-C1: kosu acik degilken ortam degiskeniyle baglam sahtelenemez (belgelenmis sinir: kasitli atlatma)."""
    ortam = {**os.environ, split._KESIF_ORTAM_ADI: str(os.getpid())}
    assert _alt_surec(_ALT_KESIF, ortam) == "False"


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="F-6: `SHORT_LAB_ONAY_VERISI_IZNI` kendi pid'iyle ayarlanip alt surec baslatilirsa alt surec "
                          "onay verisi izni 'devralir' (onay kosusu olmadan)")
def test_elle_kurulmus_ust_pid_degiskeni_alt_surece_onay_verisi_izni_vermemeli(manifestli):
    """D-B1: onay verisi izni yalnizca izin baglamindan tasinir; elle kurulmus degisken izin acmamali."""
    ortam = {**os.environ, bv._IZIN_ORTAM_ADI: str(os.getpid())}
    assert _alt_surec(_ALT_IZIN, ortam) == "False"


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="F-7: `split._KESIF_DURUMU` sozlugu ad korumasina ragmen yerinde degistirilebilir; "
                          "kesif kosusu acmadan `kesif_kosusu_acik()` True olur")
def test_kesif_durum_sozlugu_yerinde_degistirilerek_baglam_acilamaz(monkeypatch):
    """D-C1: baglam yalnizca `kesif_kosusu` ile acilir (belgelenmis sinir: dict ici yazim ad korumasindan gecer)."""
    monkeypatch.setitem(split._KESIF_DURUMU, "sayac", 1)
    assert not split.kesif_kosusu_acik()


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="F-8: `bv._IZIN` sozlugu yerinde degistirilince `onay_izni_var()` True olur; izin baglami "
                          "acilmadan onay verisi izni elde edilir")
def test_izin_sayaci_yerinde_degistirilerek_onay_verisi_izni_acilamaz(monkeypatch):
    """D-B1: izin yalnizca `onay_verisi_izni` baglamiyla acilir (belgelenmis sinir: dict ici yazim)."""
    monkeypatch.setitem(bv._IZIN, "sayac", 1)
    assert not bv.onay_izni_var()


# --- Hedef 4: `manifest-dogrula --katman tam` kosu disinda -----------------------------------------------------------


@pytest.mark.parametrize("arguman", [
    ["manifest-dogrula", "--katman=tam"],
    ["manifest-dogrula", "--katman", "TAM"],
    ["manifest-dogrula", "--katman", "tam "],
    ["manifest-dogrula", "--katman", "kesif", "tam"],
    ["manifest-dogrula", "--katman", "tam", "--katman", "kesif"],
    ["manifest-dogrula", "tam"],
    [" manifest-dogrula", "--katman", "tam"],
])
def test_tam_komutunun_bicim_varyantlari_izin_acikken_bile_tam_dogrulamayi_calistirmaz(manifestli, monkeypatch, arguman):
    """D-C2: komut ayristirmasi kati; varyantlar ya reddedilir ya kullanim mesaji verir, `tam` calismaz."""
    cagrilar: list[str] = []
    gercek = mf.manifest_dogrula

    def izle(*, katman):
        cagrilar.append(katman)
        return gercek(katman=katman)

    monkeypatch.setattr(mf, "manifest_dogrula", izle)
    with bv.onay_verisi_izni("test"):
        try:
            mf._ana(arguman)
        except mf.OnayKatmaniKilitli:
            pass
    assert "tam" not in cagrilar


def test_tam_komutu_kesif_kosusu_icinde_de_reddedilir(manifestli):
    """D-C2: kesif kosusu onay kosusu degildir; `tam` komutu orada da reddedilir."""
    with split.kesif_kosusu():
        with pytest.raises(mf.OnayKatmaniKilitli):
            mf._ana(["manifest-dogrula", "--katman", "tam"])


def test_dogrudan_tam_dogrulama_izinsiz_calismaz_kesif_kosusunda_da(manifestli):
    """D-C2 / CLAUDE.md §3.3: `manifest_dogrula(katman="tam")` onay verisi izni olmadan, kesif kosusu icinde de reddedilir."""
    with pytest.raises(bv.OnayVerisiKorumasi):
        mf.manifest_dogrula(katman="tam")
    with split.kesif_kosusu():
        with pytest.raises(bv.OnayVerisiKorumasi):
            mf.manifest_dogrula(katman="tam")


def test_tam_komutu_sahte_pid_degiskenleriyle_alt_surecte_de_reddedilir():
    """D-C2: `-m` girisi; alt surec izni ve kesif baglamini 'devralmis' olsa bile `tam` yalnizca onay kosusunda."""
    ortam = {**os.environ, bv._IZIN_ORTAM_ADI: str(os.getpid()), split._KESIF_ORTAM_ADI: str(os.getpid())}
    cikti = subprocess.run([sys.executable, "-B", "-m", "data.onbellek_manifest", "manifest-dogrula", "--katman", "tam"],
                           cwd=config.KOK, capture_output=True, text=True, env=ortam)
    assert cikti.returncode != 0
    assert "OnayKatmaniKilitli" in cikti.stderr and "katman: tam" not in cikti.stdout


# --- Hedef 5: ilk okumadan sonra degisiklik ------------------------------------------------------------------------


def test_ilk_okumadan_sonra_ayni_boy_ayni_mtime_degisim_bellek_temizlenince_yakalanir(manifestli):
    """D-C4 / M-1: boy ve mtime korunarak yapilan degisiklik bellek bosaltilinca SHA256 ile yakalanir."""
    hedef = _a(manifestli)
    with bv.kosu_agsiz():
        bv.onbellekten_oku(hedef)
        bilgi = hedef.stat()
        _ayni_boyda_degistir(hedef)
        os.utime(hedef, ns=(bilgi.st_atime_ns, bilgi.st_mtime_ns))
        bv.dogrulanmis_bellek_temizle()
        with pytest.raises(mf.ManifestUyusmazligi):
            bv.onbellekten_oku(hedef)


def test_onbellek_koku_degisince_bellekteki_kopya_baska_koke_ait_dosyaya_cevap_vermez(manifestli, monkeypatch, tmp_path):
    """CLAUDE.md §5: bellek anahtari kok dizinini icerir; kok yonlendirilince bozuk kopya bellekten degil diskten dogrulanir."""
    kopya = tmp_path / "onbellek_ikinci"
    shutil.copytree(manifestli, kopya)
    kopya_dosya = kopya / "klines" / A_SEMBOL / config.BAR_4H / f"{AY}.parquet"
    _ayni_boyda_degistir(kopya_dosya)
    with bv.kosu_agsiz():
        bv.onbellekten_oku(_a(manifestli))  # belleği doldur
        monkeypatch.setattr(config, "ONBELLEK_DIZINI", kopya)
        with pytest.raises(mf.ManifestUyusmazligi):
            bv.onbellekten_oku(kopya_dosya)


def test_donen_cerceve_yerinde_bozulsa_da_sonraki_okuma_dogrulanmis_icerigi_verir(manifestli):
    """D-C4: sutun adi, satir silme ve attrs gibi yerinde degisiklikler bellekteki kopyaya gecmez."""
    hedef = _a(manifestli)
    with bv.kosu_agsiz():
        ilk = bv.onbellekten_oku(hedef)
        beklenen = ilk.copy()
        ilk.drop(index=ilk.index[:3], inplace=True)
        ilk.columns = [f"x{i}" for i in range(len(ilk.columns))]
        ilk.attrs["kirli"] = True
        ikinci = bv.onbellekten_oku(hedef)
    assert "kirli" not in ikinci.attrs
    pd.testing.assert_frame_equal(ikinci, beklenen)


def test_okuma_sirasinda_disk_degisse_cerceve_dogrulanan_baytlardan_kurulur(manifestli, monkeypatch):
    """M-1: SHA256 denetiminden sonra, cerceve kurulurken disk degisse bile cerceve dogrulanan baytlardandir."""
    hedef = _a(manifestli)
    beklenen = pd.read_parquet(hedef)
    gercek = pd.read_parquet

    def sarmal(*arguman, **anahtar):
        _ayni_boyda_degistir(hedef)
        return gercek(*arguman, **anahtar)

    monkeypatch.setattr(pd, "read_parquet", sarmal)
    with bv.kosu_agsiz():
        sonuc = bv.onbellekten_oku(hedef)
    pd.testing.assert_frame_equal(sonuc, beklenen)


def test_boy_denetimi_ile_okuma_arasinda_degisen_dosya_sha256ya_takilir(manifestli, monkeypatch):
    """M-1: `okuma_denetle` boyu gectikten SONRA dosya ayni boyda degisirse okuma reddedilir."""
    hedef = _a(manifestli)
    gercek = mf.okuma_denetle

    def sarmal(yol):
        satir = gercek(yol)
        _ayni_boyda_degistir(hedef)
        return satir

    monkeypatch.setattr(mf, "okuma_denetle", sarmal)
    with bv.kosu_agsiz(), pytest.raises(mf.ManifestUyusmazligi):
        bv.onbellekten_oku(hedef)


# --- Hedef 6: yol normallestirmesi ---------------------------------------------------------------------------------


def _okundu(yol) -> bool:
    """Izin olmadan okuma denendi; veri donduyse True, herhangi bir ret ya da bulunamama False."""
    try:
        sonuc = bv.onbellekten_oku(yol)
    except (OSError, ValueError, RuntimeError, TypeError, mf.ManifestHatasi):  # OnayVerisiKorumasi OSError alt sinifi
        return False
    return sonuc is not None


def test_noktali_ters_bolulu_ve_goreli_yollarla_b_dosyasi_izinsiz_acilamaz(manifestli, monkeypatch):
    """M-3: `..`, `.`, `/`, goreli yol gibi bicimler normallestirmeden sonra B dosyasi olarak taninir ve reddedilir."""
    kok, b = manifestli, _b_sembolu()
    adaylar = [
        os.path.join(str(kok / "klines" / A_SEMBOL), "..", b, config.BAR_4H, f"{AY}.parquet"),
        str(_b(kok)).replace("\\", "/"),
        str(kok / "klines" / b / config.BAR_4H / ".." / config.BAR_4H / f"{AY}.parquet"),
        str(kok) + os.sep + os.sep + "klines" + os.sep + b + os.sep + config.BAR_4H + os.sep + f"{AY}.parquet",
    ]
    for aday in adaylar:
        assert not _okundu(aday), aday
    monkeypatch.chdir(kok / "klines")
    assert not _okundu(os.path.join(b, config.BAR_4H, f"{AY}.parquet"))


def test_b_dosyasi_a_gibi_gorunen_sembolik_baglantiyla_izinsiz_acilamaz(manifestli):
    """M-3: onbellek ICINDEKI sembolik baglanti cozulur; hedef B dosyasiysa onay verisi sayilir."""
    baglanti = manifestli / "klines" / A_SEMBOL / config.BAR_4H / "2021-02.parquet"
    try:
        os.symlink(_b(manifestli), baglanti)
    except (OSError, NotImplementedError):
        pytest.skip("sembolik baglanti kurulamadi (yetki yok)")
    assert not _okundu(baglanti)


@pytest.mark.skipif(sys.platform != "win32", reason="junction yalnizca Windows")
def test_b_dizinine_giden_junction_uzerinden_b_dosyasi_izinsiz_acilamaz(manifestli):
    """M-3: onbellek icindeki junction cozulur; B sembol dizinine giden junction uzerinden okuma onay verisi sayilir."""
    baglanti = manifestli / "klines" / "ALIASUSDT"
    cikti = subprocess.run(["cmd", "/c", "mklink", "/J", str(baglanti), str(manifestli / "klines" / _b_sembolu())],
                           capture_output=True, text=True)
    if cikti.returncode != 0:
        pytest.skip(f"junction kurulamadi: {cikti.stderr.strip()}")
    try:
        assert not _okundu(baglanti / config.BAR_4H / f"{AY}.parquet")
    finally:
        os.rmdir(baglanti)  # yalnizca baglantiyi kaldirir


@pytest.mark.skipif(sys.platform != "win32", reason="junction yalnizca Windows")
def test_onbellek_disina_giden_junction_reddedilir(manifestli, tmp_path):
    """M-3: junction onbellek kokunun disina cozuluyorsa `OnbellekYoluHatasi`."""
    disarida = tmp_path / "disarida"
    (disarida / config.BAR_4H).mkdir(parents=True)
    sahte_4h(f"{AY}-01 00:00", 6).to_parquet(disarida / config.BAR_4H / f"{AY}.parquet", index=False)
    baglanti = manifestli / "klines" / "DISARIUSDT"
    cikti = subprocess.run(["cmd", "/c", "mklink", "/J", str(baglanti), str(disarida)], capture_output=True, text=True)
    if cikti.returncode != 0:
        pytest.skip(f"junction kurulamadi: {cikti.stderr.strip()}")
    try:
        with pytest.raises(bv.OnbellekYoluHatasi):
            bv.onbellekten_oku(baglanti / config.BAR_4H / f"{AY}.parquet")
    finally:
        os.rmdir(baglanti)


def _kisa_yol(yol: Path) -> str | None:
    import ctypes

    tampon = ctypes.create_unicode_buffer(1024)
    uzunluk = ctypes.windll.kernel32.GetShortPathNameW(str(yol), tampon, 1024)  # type: ignore[attr-defined]
    return tampon.value if 0 < uzunluk < 1024 else None


@pytest.mark.skipif(sys.platform != "win32", reason="8.3 adlari yalnizca Windows")
def test_8_3_kisa_adli_b_yolu_izinsiz_acilamaz(manifestli):
    """M-3: 8.3 kisa ad `resolve()` ile uzun ada acilir; B dosyasi olarak taninir."""
    uzun = _b(manifestli)
    kisa = _kisa_yol(uzun)
    if kisa is None or kisa.lower() == str(uzun).lower():
        pytest.skip("bu hacimde 8.3 kisa ad uretilmiyor")
    assert not _okundu(kisa)


@pytest.mark.skipif(sys.platform != "win32", reason="UNC yalnizca Windows")
def test_unc_yonetim_paylasimi_bicimindeki_b_yolu_izinsiz_acilamaz(manifestli):
    """M-15: `\\\\localhost\\C$\\...` bicimi ya kok disina cozulup reddedilir ya da B olarak taninir; veri donmez."""
    surucu, geri = os.path.splitdrive(str(Path(_b(manifestli)).resolve()))
    if len(surucu) != 2 or surucu[1] != ":":
        pytest.skip("surucu harfli yol yok")
    assert not _okundu("\\\\localhost\\" + surucu[0] + "$" + geri)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows ad bicimleri")
@pytest.mark.parametrize("ek", [".", " ", "::$DATA", ":akis", "\\", "/."])
def test_windows_ad_bicimi_hileleri_b_dosyasini_izinsiz_acamaz(manifestli, ek):
    """M-3 / M-16: sondaki nokta, bosluk, alternatif veri akisi ve ayirici ekleri B dosyasini onay disi gostermez."""
    assert not _okundu(str(_b(manifestli)) + ek)


@pytest.mark.skipif(sys.platform != "win32", reason="aygit onekleri Windows")
@pytest.mark.parametrize("onek", ["\\\\?/", "//?\\", "\\/?\\", "/\\?\\", "\\\\.\\", "//.\\", "\\\\?\\UNC\\localhost\\"])
def test_karisik_ayiricili_aygit_onekleri_b_dosyasini_izinsiz_acamaz(manifestli, onek):
    """M-15: `\\\\?\\` ve `\\\\.\\` onekinin karisik ayiricili varyantlari da B dosyasini acamaz."""
    assert not _okundu(onek + str(_b(manifestli)))


def test_bayt_yolu_ve_bayt_donduren_pathlike_onbellekten_okunmaz(manifestli):
    """M-16: metin olmayan yol `OnbellekYoluHatasi`."""
    yol = _a(manifestli)
    with pytest.raises(bv.OnbellekYoluHatasi):
        bv.onbellekten_oku(os.fsencode(str(yol)))

    class _Bayt:
        def __fspath__(self):
            return os.fsencode(str(yol))

    with pytest.raises(bv.OnbellekYoluHatasi):
        bv.onbellekten_oku(_Bayt())


def test_her_cagrida_farkli_yol_donduren_pathlike_denetlenenden_baska_dosyayi_okutmaz(manifestli):
    """M-3: `__fspath__` ikinci cagrida B yolu dondurse de okunan dosya denetlenen (ilk) yoldur."""
    a, b = _a(manifestli), _b(manifestli)

    class _Kayan:
        def __init__(self):
            self.sayac = 0

        def __fspath__(self):
            self.sayac += 1
            return str(a if self.sayac == 1 else b)

        def __str__(self):
            return "kayan"

    sonuc = None
    try:
        sonuc = bv.onbellekten_oku(_Kayan())
    except (OSError, ValueError, RuntimeError):
        return
    assert sonuc is None or float(sonuc["quote_volume"].iloc[0]) == 1_000_000.0


def test_kok_adiyla_baslayan_kardes_dizin_onbellek_sayilmaz(manifestli, tmp_path):
    """M-3: `onbellek_kardes` dizini `onbellek` kokunun altinda degildir (onek karsilastirmasi hatasi)."""
    hedef = tmp_path / "onbellek_kardes" / "klines" / A_SEMBOL / config.BAR_4H / f"{AY}.parquet"
    hedef.parent.mkdir(parents=True)
    sahte_4h(f"{AY}-01 00:00", 6).to_parquet(hedef, index=False)
    with pytest.raises(bv.OnbellekYoluHatasi):
        bv.onbellekten_oku(hedef)


def test_parquet_adli_dizin_icindeki_b_verisi_a_dosyasi_gibi_okunamaz(manifestli):
    """M-3: `<ay>.parquet` adli DIZIN reddedilir (pyarrow dizin veri kumesi okurdu)."""
    dizin = manifestli / "klines" / A_SEMBOL / config.BAR_4H / "2021-05.parquet"
    dizin.mkdir()
    sahte_4h(f"{AY}-01 00:00", 6, hacim=7_777_777.0).to_parquet(dizin / "part.parquet", index=False)
    with pytest.raises(bv.OnbellekYoluHatasi):
        bv.onbellekten_oku(dizin)


def test_onay_verisi_mi_bozuk_ay_bicimlerini_onay_sayar():
    """M-15 / RESULTS §14.42: ay metni bicime uymazsa (bos, bosluklu, bayt, None, tek haneli, Unicode rakam) onay sayilir."""
    for ay in ("", " 2021-01", "2021-01 ", "2021-1", "21-01", "2021/01", "٢٠٢١-٠١", "2021-00", "2021-13", None, b"2021-01", 202101):
        assert bv.onay_verisi_mi(A_SEMBOL, ay) is True, repr(ay)
