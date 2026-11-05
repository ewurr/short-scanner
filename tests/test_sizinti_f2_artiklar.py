"""F2 oncesi artiklar turu: sizinti testcisinin saldirilari (RESULTS §14.42-§14.43; commit araligi 497594d..f70d5e5).

Dort hedef:
  1. Bayt tabanli git bagi (`split.kesif_bagi_denetle`, `_git_bayt`): sembolik baglanti/kavsak, git replace, GIT_DIR
     ortami, autocrlf/filter, kapanis denetimini atlatma (D-K3).
  2. Kesif baglamini yasak adlar disinda bir yoldan acmak (analiz kodu taramasinin kacirdigi bicimler, ortam sahteciligi).
  3. `pozisyon.mae` ve `funding.pozisyon_fundingi` KESIF'te kesif_kosusu disinda.
  4. Yeni ag desenlerini (ftplib, smtplib, asyncio, curl/wget/iwr) takma adla atlatmak.

Kurallar: aga cikilmaz (alt surecler yalnizca yerel python/git calistirir); gercek `cache/` okunmaz; her `xfail(strict=True)`
bir bulgudur (S-n) ve reason'da bulgu kodu ile aciklama bulunur. xfail OLMAYAN testler savunmanin tuttugunu gosterir.
Tum dosya bu turun yeni dosyasidir; mevcut testlere dokunulmaz.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import threading
import time

import pandas as pd
import pytest

import config
from conftest import sahte_4h
from data import binance_vision as bv
from data import kume_bellegi, onbellek_manifest as mf
from data import pozisyon, sinyal, split
from kapi_yardimcisi import veri
from onay_yardimcisi import gecici_depo, git
from tarama_yardimcisi import ONAY_ATLATMA_DESENI, ONBELLEK_DESENI, ONBELLEK_UZANTILARI, ihlaller

A_SEMBOL = "SOLUSDT"
AY = "2021-01"
T = pd.Timestamp("2021-03-01 00:00", tz="UTC")


def _xf(kod: str, aciklama: str, **kw):
    """Bulgu isareti: strict xfail; reason bulgu kodunu ve kisa aciklamayi tasir."""
    return pytest.mark.xfail(strict=True, reason=f"{kod}: {aciklama}", **kw)


# --- Ortak fiksturlar --------------------------------------------------------------------------------------------------


def _anahtar(sembol, ay):
    return f"{bv.MUM_ONEKI}/{sembol}/{config.BAR_4H}/{sembol}-{config.BAR_4H}-{ay}.zip"


@pytest.fixture
def bagli_depo(monkeypatch, tmp_path):
    """Gercek git test deposu: manifest, split.csv ve universe.csv commit edilmis (test_kesif_bagi fiksturunun kopyasi)."""
    kok = tmp_path / "onbellek"
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", kok)
    bv.donuk_bellek_temizle()
    kume_bellegi.temizle()
    sahte_4h(f"{AY}-01 00:00", 12).to_parquet(bv.onbellek_yolu("klines", A_SEMBOL, config.BAR_4H, f"{AY}.parquet"),
                                              index=False)
    liste = bv.donuk_liste_yolu()
    liste.parent.mkdir(parents=True, exist_ok=True)
    liste.write_text(json.dumps({"mum": {A_SEMBOL: {config.BAR_4H: [_anahtar(A_SEMBOL, AY)]}}, "funding": {}}),
                     encoding="utf-8")
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


@pytest.fixture
def manifestli(monkeypatch, tmp_path):
    """Gecici onbellek + gecici manifest (denetim etkin); test_kesif_baglami fiksturunun kopyasi."""
    kok = tmp_path / "onbellek"
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", kok)
    mf._test_manifest_ayarla(tmp_path / "onbellek_manifest.csv")
    bv.donuk_bellek_temizle()
    kume_bellegi.temizle()
    sahte_4h("2021-01-01 00:00", 12).to_parquet(bv.onbellek_yolu("klines", A_SEMBOL, config.BAR_4H, "2021-01.parquet"),
                                                index=False)
    yol = bv.donuk_liste_yolu()
    yol.parent.mkdir(parents=True, exist_ok=True)
    anahtar = f"{bv.MUM_ONEKI}/{A_SEMBOL}/{config.BAR_4H}/{A_SEMBOL}-{config.BAR_4H}-2021-01.zip"
    yol.write_text(json.dumps({"mum": {A_SEMBOL: {config.BAR_4H: [anahtar]}}, "funding": {}}), encoding="utf-8")
    mf.manifest_kur()
    yield kok
    bv.donuk_bellek_temizle()
    kume_bellegi.temizle()


def _ac():
    with split.kesif_kosusu() as kayit:
        return kayit


def _bagli(hedef: str):
    return {"manifest": mf._etkin_yol(), "split": config.SPLIT_CSV, "universe": config.UNIVERSE_CSV}[hedef]


# =================================================================================================================
# HEDEF 1: bayt tabanli git bagi
# =================================================================================================================


def _oynat(ham: bytes, tur: str) -> bytes:
    if tur == "bom":
        return b"\xef\xbb\xbf" + ham
    if tur == "bosluk":
        return ham + b" "
    if tur == "nul":
        return ham + b"\x00"
    if tur == "kes":
        return ham[:-1]
    if tur == "satir_sonu":  # yalnizca satir sonu bicimi degisir (git autocrlf bunu "ayni" sayar)
        lf = ham.replace(b"\r\n", b"\n")
        crlf = lf.replace(b"\n", b"\r\n")
        return crlf if crlf != ham else lf
    raise AssertionError(tur)


@pytest.mark.parametrize("hedef", ["manifest", "split", "universe"])
@pytest.mark.parametrize("tur", ["bom", "bosluk", "nul", "kes", "satir_sonu"])
def test_bagli_dosyada_tek_baytlik_gorunmez_oynama_kosuyu_acmaz(bagli_depo, hedef, tur):
    """§14.43 F-1: bag baytlara dayanir; BOM, bosluk, NUL, kesik son bayt ve yalniz satir sonu farki da reddedilir."""
    yol = _bagli(hedef)
    yol.write_bytes(_oynat(yol.read_bytes(), tur))
    with pytest.raises(split.KesifBagiHatasi, match=yol.name):
        with split.kesif_kosusu():
            pytest.fail("kosu acildi")
    assert bv._KOSU_AGSIZ["sayac"] == 0 and not split.kesif_kosusu_acik()


@pytest.mark.parametrize("hedef", ["manifest", "split", "universe"])
def test_bagli_dosya_calisma_agacindan_silinirse_kosu_acilmaz(bagli_depo, hedef):
    """§14.43: okunamayan bagli dosya kapali yonde reddedilir (KesifBagiHatasi, ham OSError degil)."""
    _bagli(hedef).unlink()
    with pytest.raises(split.KesifBagiHatasi):
        _ac()
    assert not split.kesif_kosusu_acik()


def test_dizine_alinmis_ama_commit_edilmemis_degisiklik_kosuyu_acmaz(bagli_depo):
    """§14.43: `git add` HEAD'i degistirmez; calisma agaci = dizin != HEAD ise bag reddeder."""
    yol = config.UNIVERSE_CSV
    yol.write_bytes(yol.read_bytes() + b"# x\n")
    git(bagli_depo, "add", "data/universe.csv")
    with pytest.raises(split.KesifBagiHatasi, match="universe.csv"):
        _ac()


def test_dizinden_cikarilmis_ama_head_te_duran_dosya_izlenmiyor_sayilir(bagli_depo):
    """§14.43: `git rm --cached` (commit'siz) dosyayi izlenmez yapar; HEAD'de olmasi yetmez."""
    git(bagli_depo, "rm", "-q", "--cached", "data/split.csv")
    with pytest.raises(split.KesifBagiHatasi, match="izlenmiyor"):
        _ac()


def test_kose_parantezli_dosya_adi_pathspec_sihriyle_izlenen_dosyaya_cevrilemez(bagli_depo, monkeypatch):
    """§14.43 F-4: `data/spl[i]t.csv` glob'u izlenen `split.csv`e eslenir; literal pathspec ve cat-file bunu reddeder."""
    sahte = config.SPLIT_CSV.with_name("spl[i]t.csv")
    sahte.write_bytes(config.SPLIT_CSV.read_bytes() + b"\n")
    monkeypatch.setattr(config, "SPLIT_CSV", sahte)
    with pytest.raises(split.KesifBagiHatasi):
        _ac()


def test_buyuk_harfli_yolla_oynanmis_dosya_kosuyu_acmaz(bagli_depo, monkeypatch):
    """§14.43: Windows'ta DATA/SPLIT.CSV ayni dosyadir; yol yazimi bayt bagini gevsetemez (baska sistemde dosya yok)."""
    yol = config.SPLIT_CSV
    yol.write_bytes(yol.read_bytes() + b"\n")
    monkeypatch.setattr(config, "SPLIT_CSV", bagli_depo / "DATA" / "SPLIT.CSV")
    with pytest.raises(split.KesifBagiHatasi):
        _ac()


def test_autocrlf_acikken_yalniz_satir_sonu_degistirilmis_dosya_reddedilir(bagli_depo):
    """§14.43 F-1: `core.autocrlf=true` altinda git CRLF'li dosyayi 'temiz' sayar; bayt bagi saymaz."""
    git(bagli_depo, "config", "core.autocrlf", "true")
    yol = config.SPLIT_CSV
    yol.write_bytes(_oynat(yol.read_bytes(), "satir_sonu"))
    with pytest.raises(split.KesifBagiHatasi, match="baytlari"):
        _ac()


def test_gitattributes_temizleme_filtresiyle_gizlenen_oynama_reddedilir(bagli_depo):
    """§14.43 F-1: `.gitattributes` `filter` ile git'e 'temiz' gorunen ama baytlari farkli dosya bayt bagina takilir."""
    py = sys.executable.replace("\\", "/")
    git(bagli_depo, "config", "filter.lf.clean",
        f"'{py}' -c \"import sys; sys.stdout.buffer.write(sys.stdin.buffer.read().replace(b'\\r\\n', b'\\n'))\"")
    (bagli_depo / ".gitattributes").write_text("*.csv filter=lf\n", encoding="utf-8")
    yol = config.SPLIT_CSV
    ham = yol.read_bytes()
    lf = ham.replace(b"\r\n", b"\n")
    yol.write_bytes(lf.replace(b"\n", b"\r\n"))
    try:
        durum = git(bagli_depo, "status", "--porcelain", "--", "data/split.csv").strip()
    except subprocess.CalledProcessError:
        pytest.skip("filtre bu ortamda calismiyor")
    if durum or ham != lf:
        pytest.skip("on-kosul saglanmadi: git dosyayi 'temiz' saymiyor ya da HEAD'deki blob zaten CRLF")
    with pytest.raises(split.KesifBagiHatasi, match="baytlari"):
        _ac()


@_xf("S-1", "sembolik baglanti: `Path.resolve()` adli yolu degil hedef dosyayi baglar; universe.csv, HEAD'de baska "
            "baytli ama izlenen `universe_alt.csv`ye baglanti olunca kosu acilir (HEAD:data/universe.csv hic karsilastirilmaz)",
    raises=pytest.fail.Exception)
def test_universe_csv_izlenen_baska_dosyaya_sembolik_baglanti_olunca_kosu_acilmamali(bagli_depo):
    """§14.43 F-1..F-4, D-K3: bagli dosya ADIYLA HEAD'e baglanmali; sembolik baglanti hedefi sessizce yerine gecmemeli."""
    evren = config.UNIVERSE_CSV
    alt = evren.with_name("universe_alt.csv")
    alt.write_bytes(evren.read_bytes() + b"\n")
    git(bagli_depo, "add", "data/universe_alt.csv")
    git(bagli_depo, "commit", "-q", "-m", "alt")
    evren.unlink()
    try:
        os.symlink(alt.name, evren)
    except (OSError, NotImplementedError):
        pytest.skip("bu ortamda sembolik baglanti kurulamadi (yetki)")
    with pytest.raises(split.KesifBagiHatasi):
        with split.kesif_kosusu():
            pass


@_xf("S-1", "dizin kavsagi (Windows junction): `data/` izlenen `data2/`ye kavsak olunca resolve hedef yolu verir; "
            "HEAD:data/* hic karsilastirilmaz, kosu acilir", raises=pytest.fail.Exception)
@pytest.mark.skipif(sys.platform != "win32", reason="dizin kavsagi (mklink /J) yalnizca Windows'ta")
def test_data_dizini_izlenen_ikiz_dizine_kavsak_olunca_kosu_acilmamali(bagli_depo):
    """§14.43: aynisi dizin duzeyinde; yetki gerektirmeyen kavsakla (mklink /J) denenir."""
    veri_dizini, ikiz, eski = bagli_depo / "data", bagli_depo / "data2", bagli_depo / "data_eski"
    shutil.copytree(veri_dizini, ikiz)
    (ikiz / "universe.csv").write_bytes((ikiz / "universe.csv").read_bytes() + b"\n")
    git(bagli_depo, "add", "data2")
    git(bagli_depo, "commit", "-q", "-m", "ikiz")
    shutil.move(str(veri_dizini), str(eski))
    sonuc = subprocess.run(["cmd", "/c", "mklink", "/J", str(veri_dizini), str(ikiz)], capture_output=True)
    if sonuc.returncode != 0 or not veri_dizini.exists():
        shutil.move(str(eski), str(veri_dizini))
        pytest.skip("kavsak kurulamadi")
    try:
        with pytest.raises(split.KesifBagiHatasi):
            with split.kesif_kosusu():
                pass
    finally:
        os.rmdir(veri_dizini)  # yalnizca kavsagi kaldirir


# S-5 kapandi (RESULTS §14.44): bagin git cagrilari `split._bag_ortami` ile.
def test_git_replace_ile_head_blobu_degistirilerek_bayt_bagi_atlatilmamali(bagli_depo):
    """§14.43: 'HEAD'deki baytlar' commit'in gercek baytlari olmali; yerel replace referansi onlari degistirmemeli."""
    yol = config.SPLIT_CSV
    eski = git(bagli_depo, "rev-parse", "HEAD:data/split.csv").strip()
    yol.write_bytes(yol.read_bytes() + b"\n")
    yeni = git(bagli_depo, "hash-object", "-w", "data/split.csv").strip()
    git(bagli_depo, "replace", eski, yeni)
    blob = subprocess.run(["git", "cat-file", "blob", "HEAD:data/split.csv"], cwd=bagli_depo, capture_output=True,
                          check=True).stdout
    if blob != yol.read_bytes():
        pytest.skip("on-kosul: replace bu git surumunde cat-file'a yansimadi")
    with pytest.raises(split.KesifBagiHatasi):
        with split.kesif_kosusu():
            pass


# S-6 kapandi (RESULTS §14.44): bagin git cagrilari `split._bag_ortami` ile.
def test_git_dir_ortam_degiskeniyle_sahte_depodan_head_baytlari_okutulamamali(bagli_depo, monkeypatch, tmp_path):
    """§14.43: git ortam degiskenleri (GIT_DIR, GIT_INDEX_FILE, GIT_WORK_TREE...) bag denetimine tasinmamali."""
    dekoy = tmp_path / "dekoy"
    git(tmp_path, "-c", "core.autocrlf=false", "clone", "-q", str(bagli_depo), str(dekoy))
    git(dekoy, "config", "core.autocrlf", "false")
    yol = config.SPLIT_CSV
    yol.write_bytes(yol.read_bytes() + b"\n")                       # gercek depoda oynanmis
    (dekoy / "data" / "split.csv").write_bytes(yol.read_bytes())    # dekoyde ayni oynanmis baytlar commit'li
    git(dekoy, "-c", "user.name=T", "-c", "user.email=t@e.invalid", "-c", "commit.gpgsign=false",
        "commit", "-q", "-am", "dekoy")
    monkeypatch.setenv("GIT_DIR", str(dekoy / ".git"))
    with pytest.raises(split.KesifBagiHatasi):
        with split.kesif_kosusu():
            pass


# --- Acilis ile kapanis arasi ------------------------------------------------------------------------------------------


def _ekstra_satirli_split() -> bytes:
    tablo = split.split_oku()
    yeni = pd.concat([tablo, split.split_uret(["ZZZTESTUSDT"])], ignore_index=True)
    return yeni.to_csv(index=False, lineterminator="\n").encode("utf-8")


@_xf("S-3", "kosu icinde split.csv oynanip OKUNDUKTAN sonra eski baytlara geri yazilirsa kapanis ozeti ayni cikar; "
            "kosu oynanmis tabloyu okumus olsa da KesifBagiHatasi yok (okuma aninda denetim/mtime yok)",
    raises=pytest.fail.Exception)
def test_kosu_icinde_degistirip_geri_yazilan_split_csv_fark_edilmeli(bagli_depo):
    """D-K3: kapanis denetimi yalnizca son hali ozetler; ara okuma tablo degismisken yapildi."""
    orijinal = config.SPLIT_CSV.read_bytes()
    with pytest.raises(split.KesifBagiHatasi):
        with split.kesif_kosusu():
            config.SPLIT_CSV.write_bytes(_ekstra_satirli_split())
            okunan = split.split_oku()
            assert "ZZZTESTUSDT" in set(okunan["sembol"])           # kosu oynanmis tabloyu gordu
            config.SPLIT_CSV.write_bytes(orijinal)                  # iz birakmadan geri


@_xf("S-2", "`config.SPLIT_CSV` (`_DEGISMEZ_ADLAR`da degil) kosu icinde baska dosyaya cevrilince kapanis denetimi yalnizca "
            "ACILISTAKI yollari ozetler; yeni yoldaki tablo okunur, KesifBagiHatasi yok", raises=pytest.fail.Exception)
def test_kosu_icinde_config_split_csv_yeniden_baglanirsa_kapanista_fark_edilmeli(bagli_depo, monkeypatch):
    """D-K3: kapanis `_kesif_bagli_dosyalar()`i yeniden cozmeli ya da yol degisimini reddetmeli."""
    alt = bagli_depo / "data" / "split_alt.csv"
    with pytest.raises(split.KesifBagiHatasi):
        with split.kesif_kosusu():
            alt.write_bytes(_ekstra_satirli_split())
            monkeypatch.setattr(config, "SPLIT_CSV", alt)
            assert "ZZZTESTUSDT" in set(split.split_oku()["sembol"])


@_xf("S-4", "`kesif_kosusu()` `with` olmadan acilip generator.close() ya da GC ile kapaninca (GeneratorExit) kapanis "
            "uyusmazligi yalnizca `add_note` olur; hata firlatilmaz, oynanmis dosya sessiz gecer",
    raises=pytest.fail.Exception)
def test_with_olmadan_acilan_kosu_kapanirken_oynanmis_dosya_fark_edilmeli(bagli_depo):
    """D-K3: kapanis yolu ne olursa olsun uyusmazligi gorunur kilmali (kazayla `__enter__` cagirip birakma)."""
    cm = split.kesif_kosusu()
    cm.__enter__()
    yol = config.SPLIT_CSV
    yol.write_bytes(yol.read_bytes() + b"\n")
    try:
        with pytest.raises(split.KesifBagiHatasi):
            cm.gen.close()
    finally:
        try:
            cm.__exit__(None, None, None)
        except Exception:  # noqa: BLE001  (uretec zaten bitmis olabilir)
            pass
        assert not split.kesif_kosusu_acik()


def test_kosu_icinde_degisen_dosya_kapanista_yakalanir_manifest_degilse_de(bagli_depo):
    """D-K3 kontrol: kalici degisiklik (geri yazilmayan) kapanista yakalanir."""
    with pytest.raises(split.KesifBagiHatasi, match="universe.csv"):
        with split.kesif_kosusu():
            config.UNIVERSE_CSV.write_bytes(config.UNIVERSE_CSV.read_bytes() + b"\n")
    assert not split.kesif_kosusu_acik() and bv._KOSU_AGSIZ["sayac"] == 0


# =================================================================================================================
# HEDEF 3: mae ve pozisyon_fundingi (KESIF) kosu disinda
# =================================================================================================================


def _sentetik():
    zaman = pd.date_range("2021-01-01", periods=275, freq="8h", tz="UTC")
    fr = pd.DataFrame({"odeme_zamani": zaman, "aralik_saat": 8.0, "oran": 0.0001, "oran_8h": 0.0001})
    return veri(sahte_4h("2021-01-01", 540, hacim=1e10), fr, pd.Timestamp("2021-01-01 00:00", tz="UTC"),
                pd.Timestamp("2021-04-30 20:00", tz="UTC"))


def _onayli(kimlik):
    return pozisyon._test_onayi(hipotez="H2", yapilandirma=sinyal.izgara("H2")[0], t=T, rol="olay", **kimlik)


def _mae(p):
    return pozisyon.mae(p)


def _fund(p):
    from data import funding

    return funding.pozisyon_fundingi(p)


def _sonuc(fn) -> str:
    try:
        fn()
    except split.KesifBaglamiYok:
        return "baglam yok"
    except Exception:  # noqa: BLE001  (baglam denetimi gecildi; veri/olay hatasi)
        return "gecti"
    return "gecti"


@pytest.mark.parametrize("cagri", [_mae, _fund])
def test_kosu_icinde_kurulan_pozisyonla_kosu_kapandiktan_sonra_mae_ve_funding_cagrilamaz(manifestli, cagri):
    """§14.43 D-C1: pozisyon nesnesi kosudan sag cikar ama KESIF verisine erisim kosuyla birlikte kapanir."""
    with split.kesif_kosusu():
        p = _onayli(_sentetik())
        assert _sonuc(lambda: cagri(p)) == "gecti"
    with pytest.raises(split.KesifBaglamiYok):
        cagri(p)


@pytest.mark.parametrize("cagri", [_mae, _fund])
def test_kosu_kapaninca_baska_is_parcacigi_mae_ve_funding_cagiramaz(manifestli, cagri):
    """§14.43 D-C1: kosu icinde baslatilip kosudan sonra calisan is parcacigi baglami miras almaz."""
    p = _onayli(_sentetik())
    olay = threading.Event()
    sonuc: dict[str, str] = {}

    def is_parcacigi():
        olay.wait(10)
        sonuc["s"] = _sonuc(lambda: cagri(p))

    parcacik = threading.Thread(target=is_parcacigi)
    with split.kesif_kosusu():
        parcacik.start()
    olay.set()
    parcacik.join(30)
    assert sonuc == {"s": "baglam yok"}


@pytest.mark.parametrize("cagri", [_mae, _fund])
def test_ic_ice_kosunun_dis_kosusu_kapaninca_mae_ve_funding_yeniden_reddedilir(manifestli, cagri):
    """§14.43 D-C1: sayac mantigi; ic kosu dis kosuyu dusurmez, dis kosu kapaninca baglam kalkar."""
    p = _onayli(_sentetik())
    with split.kesif_kosusu():
        with split.kesif_kosusu():
            pass
        assert _sonuc(lambda: cagri(p)) == "gecti"
    assert _sonuc(lambda: cagri(p)) == "baglam yok"


@pytest.mark.parametrize("cagri", [_mae, _fund])
@pytest.mark.parametrize("hata", [ValueError, KeyboardInterrupt, SystemExit])
def test_kosu_her_turlu_hatayla_kapaninca_mae_ve_funding_reddedilir(manifestli, cagri, hata):
    """§14.43 D-C1: BaseException ile cikis (Ctrl-C, sys.exit dahil) baglami acik birakmaz."""
    p = _onayli(_sentetik())
    with pytest.raises(hata):
        with split.kesif_kosusu():
            raise hata("blok")
    assert not split.kesif_kosusu_acik() and os.environ.get(split._KESIF_ORTAM_ADI) is None
    assert _sonuc(lambda: cagri(p)) == "baglam yok"


@pytest.mark.parametrize("kume", ["kesif", "KESIF ", "Kesif"])
@_xf("S-12", "`kesif_baglami_dogrula` yalniz tam 'KESIF' degerinde denetler; bicimi bozuk kume adi sessizce gecer "
             "(acik-kapali/fail-open). Disaridan ulasilabilirligi kume dogrulamasina bagli, savunma derinligi eksik",
     raises=pytest.fail.Exception)
def test_bicimi_bozuk_kume_adi_kesif_baglami_denetimini_sessizce_gecmemeli(manifestli, kume):
    """§14.43 D-C1: bilinmeyen kume adi kapali yonde (hata) sonuclanmali."""
    with pytest.raises((split.KesifBaglamiYok, ValueError, TypeError)):
        split.kesif_baglami_dogrula(kume)


# =================================================================================================================
# HEDEF 2: kesif baglamini yasak adlar disinda acmak
# =================================================================================================================


def _alt(kod: str, *arg, ortam: dict | None = None) -> list[str]:
    """Temiz ortamla (SHORT_LAB_* ve PYTEST_CURRENT_TEST olmadan) alt surec; yalnizca yerel python."""
    env = {k: v for k, v in os.environ.items()
           if not k.upper().startswith("SHORT_LAB_") and k.upper() != "PYTEST_CURRENT_TEST"}
    env.update(ortam or {})
    cikti = subprocess.run([sys.executable, "-B", "-c", kod, str(config.KOK), *map(str, arg)], capture_output=True,
                           text=True, check=True, timeout=180, env=env)
    return cikti.stdout.split()


_SABLON = ("import sys, os; sys.path.insert(0, sys.argv[1])\n"
           "{hazir}\n"
           "from data import split\n"
           "try:\n"
           "    {cagri}\n"
           "except Exception as h:\n"
           "    print(type(h).__name__)\n"
           "else:\n"
           "    print('SESSIZ')\n")
_PYTEST_SAHTE = "import pytest\nos.environ['PYTEST_CURRENT_TEST'] = 'x.py::y (call)'"


def _sablon(hazir: str, cagri: str) -> str:
    return _SABLON.format(hazir=hazir, cagri=cagri)


def test_kontrol_pytest_disi_surecte_kesif_karar_noktasi_baglamsiz_reddedilir():
    """§14.42 D-C1 kontrol: uretim kipinde (pytest yok) kosu disinda `kesif_baglami_dogrula('KESIF')` reddeder."""
    assert _alt(_sablon("", "split.kesif_baglami_dogrula('KESIF')")) == ["KesifBaglamiYok"]


def test_kontrol_pytest_disi_surecte_test_kaydi_ayarlanamaz():
    """§14.42 kontrol: `_test_kaydi_ayarla` pytest disinda OnayKorumasi verir."""
    kod = _sablon("", "split._test_kaydi_ayarla(__import__('pathlib').Path(sys.argv[2]) / 'k.md')")
    assert _alt(kod, os.getcwd()) == ["OnayKorumasi"]


# S-10 kapandi (RESULTS §14.45): test istisnasi `pytest_configure` isaretine dayanir; xfail isareti kaldirildi.
def test_pytest_ortam_degiskeni_sahteciligi_kesif_baglami_denetimini_kapatmamali():
    """§14.42 D-C1: test istisnasi yalnizca gercek pytest oturumunda gecerli olmali."""
    assert _alt(_sablon(_PYTEST_SAHTE, "split.kesif_baglami_dogrula('KESIF')")) == ["KesifBaglamiYok"]


# S-10 kapandi (RESULTS §14.45).
def test_pytest_ortam_degiskeni_sahteciligi_test_kaydini_pytest_disinda_ayarlatmamali(tmp_path):
    """§3.3 / split.py `_test_kaydi_ayarla`: 'pytest disinda OnayKorumasi' vaadi."""
    kod = _sablon(_PYTEST_SAHTE, "split._test_kaydi_ayarla(__import__('pathlib').Path(sys.argv[2]) / 'k.md')")
    assert _alt(kod, tmp_path) == ["OnayKorumasi"]


# S-11 kapandi (RESULTS §14.44): pytest disinda `denetim_etkin()` her zaman True; yol eksikse `ManifestYok`.
def test_manifest_yolu_degiskeni_none_yapilarak_kesif_sozlesmesi_kapatilamamali():
    """§14.42 D-B2/D-C1: manifest denetiminin acik/kapali bayragi modul disindan degistirilememeli."""
    hazir = "from data import onbellek_manifest as mf\nmf.MANIFEST_YOLU = None"
    assert _alt(_sablon(hazir, "split.kesif_baglami_dogrula('KESIF')")) == ["KesifBaglamiYok"]


@_xf("S-9", "alt surecin devraldigi baglam (`devralinan`) hic dusmez: kosu icinde baslatilip kosudan sonra yasayan surec "
            "(is havuzu isci sureci), ust kosu kapandiktan sonra da `kesif_kosusu_acik()` True gorur",
     raises=AssertionError)
def test_kosudan_sonra_yasayan_alt_surec_kesif_baglamini_tutmamali(manifestli, tmp_path):
    """§14.42 D-C1: baglam kosuyla birlikte sona ermeli; devralan surecte kalici olmamali."""
    hazir, bitir = tmp_path / "hazir", tmp_path / "bitir"
    kod = ("import sys, time, pathlib; sys.path.insert(0, sys.argv[1])\n"
           "from data import split\n"
           "print(split.kesif_kosusu_acik(), flush=True)\n"
           "pathlib.Path(sys.argv[2]).write_text('1')\n"
           "t0 = time.time()\n"
           "while not pathlib.Path(sys.argv[3]).exists() and time.time() - t0 < 120:\n"
           "    time.sleep(0.05)\n"
           "print(split.kesif_kosusu_acik(), flush=True)\n")
    proc = None
    try:
        with split.kesif_kosusu():
            proc = subprocess.Popen([sys.executable, "-B", "-c", kod, str(config.KOK), str(hazir), str(bitir)],
                                    stdout=subprocess.PIPE, text=True)
            t0 = time.time()
            while not hazir.exists():
                if proc.poll() is not None or time.time() - t0 > 120:
                    pytest.fail("alt surec hazir olmadi")
                time.sleep(0.05)
        bitir.write_text("1")
        satirlar = proc.communicate(timeout=120)[0].split()
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill()
    if len(satirlar) < 2 or satirlar[0] != "True":
        pytest.skip("on-kosul: alt surec baglami devralmadi (ppid denetimi bu ortamda farkli)")
    assert satirlar[1] == "False"


@_xf("S-7", "`split._kesif_baglami` ozel sinifi okuma erisimiyle alinip `__enter__` edilince `kesif_kosusu` acilmadan "
            "baglam acik olur (commit bagi, ag yasagi, manifest dogrulamasi yok); ad korumasi yalniz ATAMAYI engeller, "
            "tarama ise adi parcalayan `getattr`i gormez", raises=AssertionError)
def test_ozel_baglam_sinifi_getattr_ile_kosusuz_acilamamali():
    """§14.42 D-C1: kesif baglami yalnizca `kesif_kosusu` ile (denetimlerle birlikte) acilmali."""
    sinif = getattr(split, "_kesif_" + "baglami")
    cm = sinif()
    cm.__enter__()
    try:
        assert not split.kesif_kosusu_acik()
    finally:
        cm.__exit__(None, None, None)
    assert not split.kesif_kosusu_acik() and split._KESIF_DURUMU["sayac"] == 0


def _tam(ad: str) -> str:
    """ASCII harfleri tam genislikli karsiliklarina cevirir (altcizgi/rakam ayni kalir)."""
    return "".join(chr(ord(c) + 0xFEE0) if c.isascii() and c.isalpha() else c for c in ad)


def test_tam_genislikli_kimlik_python_ayristiricisinda_ascii_ada_cevrilir():
    """Onkosul (S-13): PEP 3131 NFKC normallestirmesi; `split._ＫＥＳＩＦ_...` ayni oznitelik, `import ｆｔｐｌｉｂ` ayni modul."""
    assert ast.parse(f"split.{_tam('_KESIF_DURUMU')}").body[0].value.attr == "_KESIF_DURUMU"
    assert ast.parse(f"import {_tam('ftplib')}").body[0].names[0].name == "ftplib"


def _tara(tmp_path, metin, desen, uzantilar=(".py",)):
    (tmp_path / "study").mkdir(exist_ok=True)
    (tmp_path / "study" / "k.py").write_text(metin, encoding="utf-8")
    return ihlaller(desen, kok=tmp_path, uzantilar=uzantilar)


def _yakalanir(tmp_path, metin, tur="onay"):
    if tur == "onay":
        return _tara(tmp_path, metin, ONAY_ATLATMA_DESENI) == ["study/k.py"]
    return _tara(tmp_path, metin, ONBELLEK_DESENI, ONBELLEK_UZANTILARI) == ["study/k.py"]


@pytest.mark.parametrize("metin", [
    "from data import split\nsplit._KESIF_DURUMU['sayac'] += 1\n",
    "os.environ['SHORT_LAB_KESIF_KOSUSU'] = '1'\n",
    "from data import split\nsplit._kesif_baglami().__enter__()\n",
])
def test_kontrol_dogrudan_yazilmis_kesif_adlari_taramaya_takilir(tmp_path, metin):
    """§14.43 D-C1 kontrol: savunmanin tuttugu taban (bu dosyanin xfail'leri bu tabana gore olculur)."""
    assert _yakalanir(tmp_path, metin)


@pytest.mark.parametrize("metin", [
    pytest.param("from data import split\nd = getattr(split, '_KESIF_' 'DURUMU')\nd['sayac'] = 1\n",
                 marks=_xf("S-7", "bitisik dize birlestirme", raises=AssertionError)),
    pytest.param("from data import split\nd = getattr(split, '_KESIF_' + 'DURUMU')\nd['sayac'] = 1\n",
                 marks=_xf("S-7", "dize toplama", raises=AssertionError)),
    pytest.param("from data import split\ncm = getattr(split, '_kesif_' + 'baglami')()\ncm.__enter__()\n",
                 marks=_xf("S-7", "ozel sinif adi parcali", raises=AssertionError)),
    pytest.param("import os\nos.environ['SHORT_LAB_' + 'KESIF_KOSUSU'] = str(os.getppid())\n",
                 marks=_xf("S-7", "ortam adi parcali", raises=AssertionError)),
])
def test_parcalanmis_kesif_adlari_taramaya_takilmali(tmp_path, metin):
    """§14.43 D-C1: tarama 'adi parcalayan erisim yakalanmaz' sinirini belgeler; calisma aninda da savunma yok (S-7)."""
    assert _yakalanir(tmp_path, metin)


@pytest.mark.parametrize("metin", [
    pytest.param("import os\nos.environ['short_lab_kesif_kosusu'] = str(os.getppid())\n",
                 marks=_xf("S-8", "Windows'ta ortam adi buyuk/kucuk harf duyarsiz; kucuk harfli ad taramayi gecer ve "
                                  "calisma aninda ayni degiskendir", raises=AssertionError)),
    pytest.param("import os\nos.putenv('Short_Lab_Kesif_Kosusu', '1')\n",
                 marks=_xf("S-8", "putenv + karisik harf", raises=AssertionError)),
    pytest.param("import os\nos.environ['pytest_current_test'] = 'x (call)'\n",
                 marks=_xf("S-8", "PYTEST_CURRENT_TEST kucuk harfle (S-10 zincirinin baslangici)", raises=AssertionError)),
    pytest.param("import os\nos.environ['short_lab_onay_verisi_izni'] = str(os.getppid())\n",
                 marks=_xf("S-8", "onay verisi izni degiskeni kucuk harfle", raises=AssertionError)),
])
def test_kucuk_harfli_ortam_degiskeni_adlari_taramaya_takilmali(tmp_path, metin):
    """§14.42-§14.43: `SHORT_LAB_*` / `PYTEST_CURRENT_TEST` desenleri buyuk/kucuk harfe duyarli; Windows'ta etkisiz."""
    assert _yakalanir(tmp_path, metin, tur="onbellek" if "onay_verisi" in metin else "onay")


@pytest.mark.parametrize("tur,metin", [
    pytest.param("onay", f"from data import split\nsplit.{_tam('_KESIF_DURUMU')}['sayac'] += 1\n",
                 marks=_xf("S-13", "tam genislikli kimlik NFKC ile ASCII ada cevrilir; ad taramasi gormez",
                           raises=AssertionError)),
    pytest.param("onay", f"split.{_tam('_kesif_baglami')}().__enter__()\n",
                 marks=_xf("S-13", "ozel baglam sinifi tam genislikli", raises=AssertionError)),
    pytest.param("onay", f"split.{_tam('_test_kaydi_ayarla')}(yol)\n",
                 marks=_xf("S-13", "test kaydi ayarlayicisi tam genislikli", raises=AssertionError)),
    pytest.param("onbellek", f"import {_tam('ftplib')}\n",
                 marks=_xf("S-13", "ftplib ice aktarimi tam genislikli", raises=AssertionError)),
    pytest.param("onbellek", f"import {_tam('socket')}\n",
                 marks=_xf("S-13", "socket ice aktarimi tam genislikli", raises=AssertionError)),
    pytest.param("onbellek", f"import {_tam('requests')}\n",
                 marks=_xf("S-13", "requests ice aktarimi tam genislikli", raises=AssertionError)),
])
def test_tam_genislikli_kimlikler_ad_taramasini_atlatmamali(tmp_path, tur, metin):
    """Taramalar ham metne bakar; Python kimlikleri NFKC normallestirir. Cozum: `ast` ile ayristirip normallesmis adlara bakmak."""
    assert _yakalanir(tmp_path, metin, tur)


@pytest.mark.parametrize("metin", [
    pytest.param("g = split.kesif_kosusu_acik.__globals__\nfor v in g.values():\n    if isinstance(v, dict) and "
                 "'sayac' in v:\n        v['sayac'] = 1\n",
                 marks=_xf("S-14", "`fonksiyon.__globals__` modul sozlugunu verir; korunan ad yazilmadan durum sozlugu "
                                   "bulunur (F-7 ile birlesince kesif baglami sahte acilir)", raises=AssertionError)),
    pytest.param("import sys\ng = sys._getframe().f_globals\n",
                 marks=_xf("S-14", "`sys._getframe`", raises=AssertionError)),
    pytest.param("import inspect\nm = inspect.getmodule(split.kesif_kosusu_acik)\nm.__dict__.clear()\n",
                 marks=_xf("S-14", "`inspect.getmodule(...).__dict__` (desen yalniz `split.__dict__` adini arar)",
                           raises=AssertionError)),
])
def test_modul_sozlugune_adsiz_erisim_yollari_taramaya_takilmali(tmp_path, metin):
    """CLAUDE.md §5 koruma katmani: `_KorunanModul` ad atamasini engeller, sozluge dogrudan yazimi degil (belgelenmis sinir)."""
    assert _yakalanir(tmp_path, metin)


# =================================================================================================================
# HEDEF 4: ag desenleri
# =================================================================================================================


@pytest.mark.parametrize("metin", [
    "import ftplib as f\nf.FTP('h')\n",
    "import os, smtplib as s\n",
    "from ftplib import FTP_TLS as T\n",
    "x = 1; import smtplib\n",
    'exec("import ftplib")\n',
    "import asyncio as a\n\n\nasync def f():\n    return await a.open_connection('h', 443)\n",
    "import asyncio\n\nasync def f(loop):\n    return await loop.create_connection(\n        P, 'h', 443)\n",
    "import subprocess, shlex\nsubprocess.run(shlex.split('curl -s ' + u))\n",
    "from subprocess import run as r\nr(['C:/Windows/System32/curl.exe', u])\n",
    "import os\nos.system('WGET ' + u)\n",
])
def test_kontrol_takma_adli_ag_ice_aktarimlari_ve_cagrilari_yakalanir(tmp_path, metin):
    """§14.43 D-K6 kontrol: `import x as y`, `;` sonrasi import, exec dizesi, shlex listesi, curl.exe yakalanir."""
    assert _yakalanir(tmp_path, metin, tur="onbellek")


def _kacak(metin: str, kod: str, aciklama: str):
    return pytest.param(metin, marks=_xf(kod, aciklama, raises=AssertionError))


@pytest.mark.parametrize("metin", [
    _kacak("from asyncio import open_connection as oc\n\n\nasync def f():\n    return await oc('h', 443)\n",
           "S-15", "`from asyncio import open_connection as oc`: desen yalniz `open_connection(` cagri bicimini arar"),
    _kacak("import asyncio\nbaglan = asyncio.open_connection\n",
           "S-15", "fonksiyon nesnesine atama, parantezsiz"),
    _kacak("import asyncio, functools\nbaglan = functools.partial(asyncio.open_connection, 'h', 443)\n",
           "S-15", "functools.partial ile parantezsiz gecirme"),
    _kacak("import asyncio\nf = getattr(asyncio.get_event_loop(), 'create_connection')\n",
           "S-15", "getattr ile alinan create_connection"),
])
def test_asyncio_ag_acilislari_takma_adla_ya_da_parantezsiz_atlatilmamali(tmp_path, metin):
    """§14.43 D-K6: `open_connection`/`create_connection` yalnizca cagri bicimiyle taranir."""
    assert _yakalanir(tmp_path, metin, tur="onbellek")


@pytest.mark.parametrize("metin", [
    _kacak('__import__("ftplib").FTP("h")\n', "S-16", "`__import__` ile dinamik ice aktarim"),
    _kacak('import importlib\nm = importlib.import_module("smtplib")\n', "S-16", "importlib.import_module"),
    _kacak('s = __import__("socket")\n', "S-16", "`__import__('socket')`"),
])
def test_dinamik_ice_aktarimla_ag_modulu_taramayi_atlatmamali(tmp_path, metin):
    """§14.43 D-K6: tarama yalniz `import`/`from` ifadelerini arar (belgelenmis sinir)."""
    assert _yakalanir(tmp_path, metin, tur="onbellek")


@pytest.mark.parametrize("metin", [
    _kacak("if True: import socket\n", "S-17", "tek satirlik bilesik ifade: `:` sonrasi import"),
    _kacak("try: import requests\nexcept ImportError: pass\n", "S-17", "`try: import ...`"),
    _kacak("def f(): import ftplib\n", "S-17", "`def f(): import ...`"),
    _kacak("import os, \\\n    ftplib\n", "S-17", "ters bolulu satir devami"),
])
def test_bilesik_ya_da_bolunmus_ice_aktarim_satiri_taramayi_atlatmamali(tmp_path, metin):
    """§14.43 D-K6: desen import'un satir basinda ya da `;`/tirnaktan sonra olmasini ister."""
    assert _yakalanir(tmp_path, metin, tur="onbellek")


@pytest.mark.parametrize("metin", [
    _kacak("import telnetlib\n", "S-18", "telnetlib"),
    _kacak("import imaplib\n", "S-18", "imaplib"),
    _kacak("import poplib\n", "S-18", "poplib"),
    _kacak("import xmlrpc.client\n", "S-18", "xmlrpc.client (HTTP uzerinden)"),
    _kacak("import websockets\n", "S-18", "websockets"),
    _kacak("import ccxt\n", "S-18", "ccxt (borsa istemcisi)"),
    _kacak("from binance.client import Client\n", "S-18", "python-binance istemcisi"),
    _kacak("import pycurl\n", "S-18", "pycurl"),
    _kacak("import paramiko\n", "S-18", "paramiko (SSH)"),
])
def test_diger_ag_kutuphaneleri_ice_aktarim_taramasini_atlatmamali(tmp_path, metin):
    """§14.43 D-K6: ftplib/smtplib eklendi ama ayni sinifin geri kalani (ve ucuncu parti istemciler) listede yok."""
    assert _yakalanir(tmp_path, metin, tur="onbellek")


@pytest.mark.parametrize("metin", [
    _kacak("import asyncio\n\n\nasync def f(u):\n    return await asyncio.create_subprocess_exec('curl', u)\n",
           "S-19", "`create_subprocess_exec`: `subprocess` sozcugu `_` yuzunden \\b ile eslesmez"),
    _kacak("import asyncio\n\n\nasync def f(u):\n    return await asyncio.create_subprocess_shell('wget ' + u)\n",
           "S-19", "`create_subprocess_shell`"),
    _kacak("import os\nos.execvp('curl', ['curl', u])\n", "S-19", "os.exec*"),
    _kacak("import os\nos.spawnlp(os.P_WAIT, 'wget', 'wget', u)\n", "S-19", "os.spawn*"),
    _kacak("import pty\npty.spawn(['curl', u])\n", "S-19", "pty.spawn"),
])
def test_subprocess_disindaki_surec_baslaticilarla_curl_wget_atlatilmamali(tmp_path, metin):
    """§14.43 D-K6: kabuk deseni yalniz `subprocess`, `os.system`, `os.popen` sozcuklerine baglidir."""
    assert _yakalanir(tmp_path, metin, tur="onbellek")


@pytest.mark.parametrize("metin", [
    _kacak("import subprocess\nsubprocess.run(['powershell', '-c', 'irm ' + u])\n", "S-20", "`irm` (Invoke-RestMethod kisaltmasi)"),
    _kacak("import subprocess\nsubprocess.run(['powershell', '-c', 'Invoke-RestMethod ' + u])\n", "S-20", "Invoke-RestMethod"),
    _kacak("import subprocess\nsubprocess.run(['certutil', '-urlcache', '-f', u, 'x'])\n", "S-20", "certutil -urlcache"),
    _kacak("import subprocess\nsubprocess.run(['bitsadmin', '/transfer', 'j', u, 'x'])\n", "S-20", "bitsadmin"),
    _kacak("import subprocess\nsubprocess.run(['powershell', '-c', '(New-Object Net.WebClient).DownloadString(u)'])\n",
           "S-20", "Net.WebClient"),
])
def test_listede_olmayan_indirme_araclari_taramayi_atlatmamali(tmp_path, metin):
    """§14.43 D-K6: arac listesi (curl, wget, Invoke-WebRequest, iwr) kapali; esdegerleri acik."""
    assert _yakalanir(tmp_path, metin, tur="onbellek")


@pytest.mark.parametrize("metin", [
    _kacak("import subprocess\nsubprocess.run(['cu' 'rl', u])\n", "S-21",
           "arac adi bitisik dizeyle bolunur (belgelenmis sinir)"),
])
def test_bolunmus_arac_adi_taramayi_atlatmamali(tmp_path, metin):
    """§14.43 D-K6: tarama metne bakar; dize birlestirme gorunmez (belgelenmis sinir, AST ile kapanabilir)."""
    assert _yakalanir(tmp_path, metin, tur="onbellek")
