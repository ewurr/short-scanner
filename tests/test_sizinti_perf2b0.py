"""Performans 2b-0 sizinti testcisi turu: kirmaya yonelik saldirilar (CLAUDE.md §3 ve §5).

Hedefler (turun commit'leri 33825ee..4503229):
  1. `test_skaler_referans_dayanilan.py` sabitlemesini, dayanilan kural fonksiyonlarinin DAVRANISI degisirken gecirmek
     (statik grafigin ve kaynak ozetinin goremedigi yollar). Gercek dosyalara dokunulmaz: saldiri `tmp_path` altindaki
     bir `data/*.py` kopyasina uygulanir ve sabitleme testinin KENDI yardimcilari (`_kapanis`, `_sha`, `_bilgi`) sahte
     kokle cagrilir.
  2. `esitlik_kapi.py` ciktisina (satir, `ilk_20_*`, `tohum`, `sure_s`, `kapsam_bar`, stderr, ara kayit JSON'u) olay
     rolunde deger ya da onay sayisi yazdirmak.
  3. Beyaz listeli git ortamini (`split._bag_ortami`) delmek: `.git/info/exclude`, yerel `core.excludesFile`,
     `include.path`, HOME altindaki XDG ignore dosyasi, `filter.*.clean`, gitlink + `diff.ignoreSubmodules`,
     `core.fsmonitor` ile delmek; `agac_temiz`i yanlis `True` yapmak.
  4. S-10'un pytest oturumu isaretini pytest disinda kurmak (`pytest.Config.__new__`, `Mock(spec=pytest.Config)`,
     `_PYTEST_OTURUMU` sozlugune dogrudan yazma) ve `denetim_etkin()` / `kesif_baglami_dogrula` istisnasini acmak.

Kural: `@bulgu(...)` isaretli testler strict xfail'dir; saldiri BASARILI olursa (kodda acik varsa) test "xfail" gorunur,
savunma ONARILIRSA XPASS(strict) ile kirmizi olur ve isaret kaldirilmalidir. Isaretsiz testler savunmanin tuttugunu
gosterir. Saldiri on kosulu kurulamazsa test atlanir (skip), sessizce xfail olmaz.
Deger raporlanmaz, getiri/sinyal degeri/olay sayisi hesaplanmaz, aga cikilmaz, gercek `cache/` okunmaz, onay kosusu
acilmaz. Git saldirilari yalnizca `tmp_path` gecici depolarinda yapilir. Sabit tohum kullanilir.
"""

from __future__ import annotations

import importlib.machinery
import json
import os
import subprocess
import sys
import types
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
import pytest

from data import pozisyon, split
from onay_yardimcisi import DEPO_BETIGI, gecici_depo, git
from tarama_yardimcisi import KOK as GERCEK_KOK
from tarama_yardimcisi import ONAY_ATLATMA_DESENI, ihlaller

import test_skaler_referans_dayanilan as dpd

sys.path.insert(0, str(GERCEK_KOK / "analysis" / "00_veri_denetimi"))
import esitlik_kapi as ek  # noqa: E402


def bulgu(kod: str, aciklama: str):
    """Saldiri basarili: kodda acik var. strict xfail; yalnizca `assert` basarisizligi xfail sayilir."""
    return pytest.mark.xfail(strict=True, raises=AssertionError, reason=f"{kod}: {aciklama}")


def _on_kosul(kosul: bool, mesaj: str) -> None:
    """Saldirinin on kosulu kurulamadiysa test atlanir (xfail'e donusup gercek bir sonucu gizlemesin)."""
    if not kosul:
        pytest.skip(f"saldiri on kosulu kurulamadi: {mesaj}")


# =====================================================================================================
# 1. Skaler referansin dayandigi kural fonksiyonlarinin sabitlenmesi: sahte kokle atlatma
# =====================================================================================================

def _kopya_kur(tmp_path, monkeypatch) -> Path:
    """`data/*.py` dosyalarini tmp_path altina kopyalar ve sabitleme testinin yardimcilarini oraya yonlendirir."""
    kok = tmp_path / "kok"
    (kok / "data").mkdir(parents=True)
    for yol in (GERCEK_KOK / "data").glob("*.py"):
        (kok / "data" / yol.name).write_text(yol.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    monkeypatch.setattr(dpd, "KOK", kok)
    monkeypatch.setattr(dpd, "_BILGI", {})
    return kok


def _denetim() -> tuple[list[str], list[str], list[str]]:
    """Sabitleme testinin uc kosulu: (ozeti degisenler, siniflandirilmamis adlar, grafikte artik kalmayanlar)."""
    degisen = sorted(ad for ad, sha in dpd.SABIT.items() if dpd._sha(ad) != sha)
    ulasilan = dpd._kapanis()
    return degisen, sorted(ulasilan - set(dpd.SABIT) - set(dpd.HARIC)), sorted(set(dpd.SABIT) - ulasilan)


def _temiz_kopya(tmp_path, monkeypatch) -> Path:
    kok = _kopya_kur(tmp_path, monkeypatch)
    _on_kosul(_denetim() == ([], [], []), "taban: sabitleme testi zaten kirmizi")
    return kok


def _ekle(monkeypatch, kok: Path, modul: str, metin: str) -> None:
    """Kopya modulun SONUNA metin ekler (var olan tanimlara dokunmaz) ve sabitleme testinin onbellegini atar."""
    yol = kok / "data" / f"{modul}.py"
    yol.write_text(yol.read_text(encoding="utf-8") + metin, encoding="utf-8", newline="\n")
    dpd._BILGI.clear()


def test_sabitleme_pinli_fonksiyonun_govde_degisikligini_yakalar(tmp_path, monkeypatch):
    """Dayanak: D-B1 (RESULTS §14.44), kontrol. Saldirilarin anlami icin: sabitleme duzeneginin kendisi, pinli bir
    fonksiyonun govdesine eklenen satiri yakalar (ozet degisir)."""
    kok = _temiz_kopya(tmp_path, monkeypatch)
    yol = kok / "data" / "pozisyon.py"
    kaynak = dpd._kaynak("data.pozisyon._tam_hucreli_barlar")
    metin = yol.read_text(encoding="utf-8")
    _on_kosul(kaynak in metin, "kaynak metin bulunamadi")
    yol.write_text(metin.replace(kaynak, kaynak.rstrip("\n") + "\n    pass\n", 1), encoding="utf-8", newline="\n")
    dpd._BILGI.clear()
    degisen, _, _ = _denetim()
    assert "data.pozisyon._tam_hucreli_barlar" in degisen


@bulgu("S-40", "kural, HARIC'teki bir adin (yukleyici / bellek onbellegi / tablo okuyucu) saricisina tasinir; grafik orada "
               "durur, yeni yardimci hicbir yerden ulasilmaz, sabitleme yesil kalir")
@pytest.mark.parametrize("modul,ad", [("pozisyon", "_veri_yukle"), ("kume_bellegi", "getir"),
                                      ("universe", "evren_yukle"), ("split", "split_oku")])
def test_haric_adin_icine_kural_tasimak_sabitlemeyi_gecirmemeli(tmp_path, monkeypatch, modul, ad):
    """Dayanak: D-B1 / `test_skaler_referans_dayanilan.HARIC` (grafik HARIC adlarda durur). Yukleyici ayni verilerle hem
    kapiyi hem referansi besledigi icin, orada yapilan bir degisiklik (satir dusurme, dolgu, donem siniri kaydirma) iki
    tarafi BIRLIKTE kaydirir ve esitlik testleri farki goremez. Beklenen: sabitleme bu degisikligi yakalar. Gozlenen:
    yeni sarmalayici ve `_gizli_kural` hicbir SABIT adi degistirmez ve grafikte gorunmez."""
    kok = _temiz_kopya(tmp_path, monkeypatch)
    _on_kosul(f"data.{modul}.{ad}" in dpd.HARIC, "ad HARIC'te degil")
    _ekle(monkeypatch, kok, modul,
          f"\n\n{ad}_orijinal = {ad}\n\n\ndef {ad}(*args, **kwargs):\n    veri = {ad}_orijinal(*args, **kwargs)\n"
          "    return _gizli_kural(veri)\n\n\ndef _gizli_kural(veri):\n    return veri  # kural govdesi burada yasar\n")
    assert any(_denetim()), "HARIC saricisi icine tasinan kural sabitlemeyi kirmadi"


@bulgu("S-41", "pinli fonksiyonun ust duzey olmayan (if icinde) yeniden tanimi grafikte gorunmez; calisma zamaninda son "
               "baglanan ad gecerlidir, ozet eski tanimi okur")
def test_if_blogu_icinde_yeniden_tanimlanan_pinli_fonksiyon_sabitlemeyi_gecirmemeli(tmp_path, monkeypatch):
    """Dayanak: D-B1; `_bilgi` yalnizca `agac.body` dogrudan cocuklarini tanim sayar. `if True:` altindaki `def`,
    Python'da modulun son baglamasidir (davranis degisir) ama `tanim` tablosuna girmez; ozet eski `def`i okur."""
    kok = _temiz_kopya(tmp_path, monkeypatch)
    _ekle(monkeypatch, kok, "pozisyon",
          "\n\nif True:\n    def _tam_hucreli_barlar(*args, **kwargs):\n        raise RuntimeError('kural degisti')\n")
    assert any(_denetim()), "if icindeki yeniden tanim sabitlemeyi kirmadi"


@bulgu("S-42", "`globals()[ad] = ...` ifadesi ust duzey Assign degildir; pinli adin calisma zamani baglamasi degisir, "
               "ozet degismez")
def test_globals_ile_pinli_adi_yeniden_baglamak_sabitlemeyi_gecirmemeli(tmp_path, monkeypatch):
    """Dayanak: D-B1; ozet yalnizca `Assign` / `AnnAssign` / `def` / `class` ust duzey ifadelerini tanim sayar. Bir
    `Expr` (globals()[...] = ...) pinli adi degistirir ama hicbir pinli metni degistirmez."""
    kok = _temiz_kopya(tmp_path, monkeypatch)
    _ekle(monkeypatch, kok, "pozisyon", "\n\nglobals()['_tam_hucreli_barlar'] = lambda *a, **k: None\n")
    assert any(_denetim()), "globals() ile yeniden baglama sabitlemeyi kirmadi"


@bulgu("S-43", "ust duzey AugAssign (`SABIT -= 1`) tanim sayilmaz; pinli sabitin DEGERI degisir, ozet degismez")
def test_artirmali_atama_ile_pinli_sabitin_degerini_degistirmek_sabitlemeyi_gecirmemeli(tmp_path, monkeypatch):
    """Dayanak: D-B1 ('sabitler ayni yolla sabitlenir: atama satiri'). `GUNLUK_BAR_SAYISI = config.GUNLUK_BAR_SAYISI`
    satiri ozetlenir, ama modulun sonundaki `GUNLUK_BAR_SAYISI -= 1` bir `AugAssign`dir ve tanim tablosuna girmez."""
    kok = _temiz_kopya(tmp_path, monkeypatch)
    _ekle(monkeypatch, kok, "klines", "\n\nGUNLUK_BAR_SAYISI -= 1\n")
    assert any(_denetim()), "AugAssign ile sabit degisikligi sabitlemeyi kirmadi"


@bulgu("S-44", "`fonksiyon.__code__ = ...` (Assign ama hedefi Attribute) tanim sayilmaz; pinli fonksiyonun govdesi "
               "calisma zamaninda degisir, ozet degismez")
def test_code_atamasi_ile_pinli_fonksiyonun_govdesini_degistirmek_sabitlemeyi_gecirmemeli(tmp_path, monkeypatch):
    """Dayanak: D-B1; `_bilgi` Assign hedeflerinden yalnizca `ast.Name` olanlari sayar. `f.__code__ = g.__code__`
    f'in kaynak metnini degistirmeden davranisini degistirir."""
    kok = _temiz_kopya(tmp_path, monkeypatch)
    _ekle(monkeypatch, kok, "pozisyon", "\n\n_tam_hucreli_barlar.__code__ = (lambda *a, **k: None).__code__\n")
    assert any(_denetim()), "__code__ atamasi sabitlemeyi kirmadi"


@bulgu("S-45", "sabitleme `data/<ad>.py` dosyasini okur; ayni adli bir paket dizini (ya da `data/__init__.py` "
               "yonlendirmesi) Python'un gercekte yukledigi modulu degistirir, hicbir ozet degismez")
@pytest.mark.parametrize("yol", ["paket_golgesi", "init_yonlendirmesi"])
def test_modul_golgeleme_ile_pinli_modulu_degistirmek_sabitlemeyi_gecirmemeli(tmp_path, monkeypatch, yol):
    """Dayanak: D-B1 ('baska module tasima'). `data/pencere/__init__.py` varsa Python `pencere.py` yerine PAKETI yukler
    (dizin once aranir); sabitleme `pencere.py`yi okumaya devam eder. `data/__init__.py` icinden `sys.modules` degisimi
    de ayni etkiyi verir. Beklenen: dayanilan modul kaynaginin gercek yuklenen kaynakla ayni oldugu denetlenir."""
    kok = _temiz_kopya(tmp_path, monkeypatch)
    if yol == "paket_golgesi":
        (kok / "data" / "pencere").mkdir()
        (kok / "data" / "pencere" / "__init__.py").write_text("# golge paket\n", encoding="utf-8")
        spec = importlib.machinery.PathFinder.find_spec("pencere", [str(kok / "data")])
        _on_kosul(spec is not None and str(spec.origin).endswith("__init__.py"), "paket modulun onune gecmedi")
    else:
        (kok / "data" / "klines_golge.py").write_text("GUNLUK_BAR_SAYISI = 5\n", encoding="utf-8")
        _ekle(monkeypatch, kok, "__init__",
              "\n\nimport sys as _sys\n\n\ndef _yonlendir():\n    from data import klines_golge\n"
              "    _sys.modules['data.klines'] = klines_golge\n\n\n_yonlendir()\n")
    assert any(_denetim()), "modul golgeleme sabitlemeyi kirmadi"


def test_conftest_pinli_kural_adlarini_monkeypatch_etmez():
    """Dayanak: D-B1 ('monkeypatch'). `tests/conftest.py` her teste otomatik uygulanir; orada pinli bir kural adinin
    degistirilmesi hem kapiyi hem referansi birlikte kaydirir. Bugun yalnizca belgelenmis `_kayitlar` ve (HARIC)
    `_veri_yukle` yamalanir; baska bir pinli ad yamalanirsa bu test kirilir."""
    import ast

    agac = ast.parse((GERCEK_KOK / "tests" / "conftest.py").read_text(encoding="utf-8"))
    yamalanan = set()
    for d in ast.walk(agac):
        if (isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr in ("setattr", "setitem")
                and len(d.args) >= 2 and isinstance(d.args[1], ast.Constant) and isinstance(d.args[1].value, str)):
            yamalanan.add(d.args[1].value)
    pinli_adlar = {ad.rpartition(".")[2] for ad in dpd.SABIT}
    assert (yamalanan & pinli_adlar) <= {"_kayitlar"}, sorted(yamalanan & pinli_adlar)


# =====================================================================================================
# 2. Esitlik betigi: olay rolunde deger / onay sayisi sizintisi
# =====================================================================================================

_ONAY = object()   # sahte "onay" sonucu; deger tasimaz
_AYAR = {"hipotezler": ["H1"], "yapilandirma": "ilk", "roller": ["olay"], "funding_satiri": False, "bar": "tum", "n": 10}
_BAR_SAYISI = 40


def _sahte_dunya(monkeypatch, maske, maliyet: bool = False) -> None:
    """`sembol_isi`yi veri olmadan kosturur: donem listesi, izgara ve karar sahtedir. `maske[i]` True ise i. bar
    'onaylanir' (iki tarafta). `maliyet=True` ise her onayli cagri sahte saati 1 sn ilerletir; aksi halde saat sabittir."""
    izgara = pd.date_range("2022-01-01", periods=len(maske), freq="4h", tz="UTC")
    saat = {"t": 0.0}
    monkeypatch.setattr(ek, "_donemler", lambda sembol: [0])
    monkeypatch.setattr(ek, "bar_izgarasi", lambda kimlik, hipotez: izgara)
    monkeypatch.setattr(ek, "sinir_siralari", lambda izgara_, kimlik: set())

    def karar(modul, hipotez, yapilandirma, rol, t, kimlik, sira):
        if maske[sira]:
            if maliyet:
                saat["t"] += 1.0
            return _ONAY
        return pozisyon.SinyalKosuluSaglanmadi("sahte")

    monkeypatch.setattr(ek, "karar", karar)
    monkeypatch.setattr(ek, "time", types.SimpleNamespace(perf_counter=lambda: saat["t"]))


@pytest.mark.parametrize("kip", ["tum", "ornek"])
def test_olay_rolu_satiri_onay_sayisindan_bagimsizdir(monkeypatch, kip):
    """Dayanak: esitlik_kapi aciklamasi ('OLAY ROLUNDE bos birakilir: olay rolunde onay sayisi olay sayisidir ve
    yazilmaz'). Ayni barlar uc maskeyle (hepsi onay, hic onay, karisik) kosulur; olay satirinin ve TOPLAM satirinin
    butun alanlari (`kapsam_bar`, `ilk_20_*`, `tohum`, sayilar) ayni olmali. Sabit saat: `sure_s` ayri testtedir."""
    karisik = [(i * 7) % 10 < 3 for i in range(_BAR_SAYISI)]
    sonuclar = []
    for maske in ([True] * _BAR_SAYISI, [False] * _BAR_SAYISI, karisik):
        _sahte_dunya(monkeypatch, maske)
        sonuclar.append(ek.sembol_isi("X", {**_AYAR, "bar": kip}))
    for satirlar in sonuclar:
        assert all(set(s) == set(ek.SUTUNLAR) for s in satirlar)
        olay = [s for s in satirlar if s["rol"] == "olay"]
        assert olay and all(s["kapsam_bar"] == "" for s in olay)
    assert sonuclar[0] == sonuclar[1] == sonuclar[2]


@bulgu("S-39", "olay rolu satirinin `sure_s` alani onayli ve reddedilen barlarin hesap suresi farkini tasir; 0.1 sn "
               "cozunurlukle olay sayisina dogru bir kanal acar")
def test_olay_rolu_sure_s_onay_sayisini_sizdirmaz(monkeypatch):
    """Dayanak: esitlik_kapi aciklamasi ('Getiri, sinyal degeri ya da olay sayisi hesaplanmaz, yazilmaz'). Onayli bar
    onaysiz bardan pahaliysa (pozisyon kurma, funding toplami) olay satirinin suresi onay sayisiyla artar. Sahte saatle
    kanal gosterilir: tum bar onayli ile hic bar onayli olmayan kosunun `sure_s` degeri ayni olmali. KURAMSAL kanal: gercek
    saat gurultulu ve sure 0.1 sn'ye yuvarlanir; yine de olay rolunde sure yazilmasi onay sayisini tasiyabilir."""
    sureler = []
    for maske in ([True] * _BAR_SAYISI, [False] * _BAR_SAYISI):
        _sahte_dunya(monkeypatch, maske, maliyet=True)
        sureler.append([s["sure_s"] for s in ek.sembol_isi("X", _AYAR) if s["rol"] == "olay"])
    assert sureler[0] == sureler[1]


class _KayitTemizlik:
    def __init__(self, temiz):
        self.temiz = temiz

    def alanlar(self):
        return {"head_commit": "a" * 40, "agac_temiz": self.temiz}


def test_ara_kayit_json_ve_stderr_olay_sayisi_tasimaz(tmp_path, monkeypatch, capsys):
    """Dayanak: esitlik_kapi `kos` ('ara_dizin ... <sembol>.json: satirlar, HEAD, ayar') ve S-18. Ara kayit JSON'u yalnizca
    `SUTUNLAR` alanlarini tasir, olay satirinda `kapsam_bar` bos kalir, onay sayisi (13) hicbir sayisal alanda gecmez ve
    stderr yalnizca 'bitti: <sembol>' satirini yazar."""
    maske = [i < 13 for i in range(_BAR_SAYISI)]
    _sahte_dunya(monkeypatch, maske)

    @contextmanager
    def kesif():
        yield _KayitTemizlik(True)

    monkeypatch.setattr(ek, "split_modulu", types.SimpleNamespace(kesif_kosusu=kesif))
    ara = tmp_path / "ara"
    ara.mkdir()
    ek.kos(["X"], _AYAR, 1, ara)
    veri = json.loads((ara / "X.json").read_text(encoding="utf-8"))
    assert set(veri) == {"head_commit", "ayar", "satirlar"}
    for satir in veri["satirlar"]:
        assert set(satir) == set(ek.SUTUNLAR)
        if satir["rol"] == "olay":
            assert satir["kapsam_bar"] == ""
        sayilar = [satir[a] for a in ek.SAYI_ALANLARI]
        assert 13 not in sayilar
        assert satir["ilk_20_uyusmayan"] == "" and satir["ilk_20_beklenmeyen"] == ""
    assert capsys.readouterr().err.strip() == "bitti: X"


def test_kapsam_bar_olay_rolunde_alanlar_kapsam_yazilmaz_bayragini_izler():
    """Dayanak: esitlik_kapi `Sayac.alanlar`. `kapsam_yazilir=False` iken Sayac'ta kapsam birikmis olsa bile alan bos
    doner; sayi hicbir diger alana kaymaz."""
    sayac = ek.Sayac()
    sayac.kapsam = 7
    alanlar = sayac.alanlar(kapsam_yazilir=False)
    assert alanlar["kapsam_bar"] == ""
    assert 7 not in [alanlar[a] for a in ("karsilastirilan_bar", "uyusmayan_bar", "beklenmeyen_hata_referans",
                                          "beklenmeyen_hata_yeni")]


# =====================================================================================================
# 3. Beyaz listeli git ortami: agac_temiz'i yanlis True yapmak
# =====================================================================================================

def _temiz_mi():
    return split._kesif_kaydi_kur(None).agac_temiz


def _duz_durum(depo) -> str:
    """Duz `git status --porcelain` (beyaz liste YOK, bu surecin ortamiyla): saldirinin gercekten gizledigini dogrular."""
    return git(depo, "status", "--porcelain").strip()


def _gizli_dosya(depo, ad="gizli_kural.py"):
    (depo / ad).write_text("x = 1\n", encoding="utf-8")
    return ad


# S-31 kapandi (RESULTS §14.46): izlenmeyenler yalnizca .gitignore'a gore (`split._agac_kirlilikleri`).
def test_info_exclude_ile_gizlenen_izlenmeyen_dosya_agaci_temiz_gostermemeli(tmp_path):
    """Dayanak: CLAUDE.md §3.3 ('temiz calisma agaci'); S-25/S-26 niyeti. `-c status.showUntrackedFiles=all` ayari ezer
    ama dislama kurallarini ezmez. `.git/info/exclude` commit edilmeyen, depo-yerel bir dislama listesidir: orada adi
    gecen izlenmeyen kod dosyasi kirli sayilmaz."""
    depo = gecici_depo(tmp_path)
    _on_kosul(_temiz_mi() is True, "taban: agac temiz degil")
    (depo / ".git" / "info").mkdir(exist_ok=True)
    with (depo / ".git" / "info" / "exclude").open("a", encoding="utf-8") as d:
        d.write("gizli_kural.py\n")
    _gizli_dosya(depo)
    _on_kosul(_duz_durum(depo) == "", "info/exclude dosyayi gizlemedi")
    assert _temiz_mi() is False


# S-32 kapandi (RESULTS §14.46): izlenmeyenler yalnizca .gitignore'a gore (`split._agac_kirlilikleri`).
@pytest.mark.parametrize("yol", ["dogrudan", "include"])
def test_yerel_core_excludesfile_ile_gizlenen_izlenmeyen_dosya_agaci_temiz_gostermemeli(tmp_path, yol):
    """Dayanak: CLAUDE.md §3.3; `split._GIT_SABIT_ORTAM` aciklamasi ('Yalnizca deponun kendi .git/config'u okunur').
    Depo-yerel ayar commit edilmez; `core.excludesFile` ya da onu iceren bir `include.path` dosyasi izlenmeyen kodu
    gizler."""
    depo = gecici_depo(tmp_path)
    _on_kosul(_temiz_mi() is True, "taban: agac temiz degil")
    liste = tmp_path / "dislama_listesi"
    liste.write_text("gizli_kural.py\n", encoding="utf-8")
    if yol == "dogrudan":
        git(depo, "config", "core.excludesFile", liste.as_posix())
    else:
        ek_ayar = tmp_path / "ek.config"
        ek_ayar.write_text(f"[core]\n\texcludesFile = {liste.as_posix()}\n", encoding="utf-8")
        git(depo, "config", "include.path", ek_ayar.as_posix())
    _gizli_dosya(depo)
    _on_kosul(_duz_durum(depo) == "", "ayar dosyayi gizlemedi")
    assert _temiz_mi() is False


# S-33 kapandi (RESULTS §14.46): izlenmeyenler yalnizca .gitignore'a gore (`split._agac_kirlilikleri`).
def test_home_altindaki_xdg_ignore_dosyasi_izlenmeyen_dosyayi_gizleyip_agaci_temiz_gostermemeli(tmp_path, monkeypatch):
    """Dayanak: CLAUDE.md §3.3; `split._GIT_ORTAM_BEYAZ_LISTESI` (HOME, USERPROFILE gecer). `core.excludesFile` ayarsizsa
    git `$XDG_CONFIG_HOME/git/ignore` ya da `$HOME/.config/git/ignore` dosyasini kullanir; bu ayar degil dosyadir, bu
    yuzden `GIT_CONFIG_GLOBAL=devnull` onu kesmez."""
    depo = gecici_depo(tmp_path)
    _on_kosul(_temiz_mi() is True, "taban: agac temiz degil")
    ev = tmp_path / "ev"
    (ev / ".config" / "git").mkdir(parents=True)
    (ev / ".config" / "git" / "ignore").write_text("gizli_kural.py\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(ev))
    monkeypatch.setenv("USERPROFILE", str(ev))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    _gizli_dosya(depo)
    _on_kosul(_duz_durum(depo) == "", "HOME altindaki ignore dosyayi gizlemedi")
    assert _temiz_mi() is False


def test_home_altindaki_global_gitconfig_agaci_temiz_gostermez(tmp_path, monkeypatch):
    """Dayanak: `split._GIT_SABIT_ORTAM` (`GIT_CONFIG_GLOBAL=os.devnull`). HOME altindaki `.gitconfig` icindeki
    `core.excludesFile` duz git'te izlenmeyen dosyayi gizler, ama bag ortaminda okunmaz: agac kirli sayilir."""
    depo = gecici_depo(tmp_path)
    _on_kosul(_temiz_mi() is True, "taban: agac temiz degil")
    ev = tmp_path / "ev"
    ev.mkdir()
    liste = tmp_path / "dislama_listesi"
    liste.write_text("gizli_kural.py\n", encoding="utf-8")
    (ev / ".gitconfig").write_text(f"[core]\n\texcludesFile = {liste.as_posix()}\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(ev))
    monkeypatch.setenv("USERPROFILE", str(ev))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    _gizli_dosya(depo)
    _on_kosul(_duz_durum(depo) == "", "global ayar dosyayi gizlemedi")
    assert _temiz_mi() is False


def test_ortamdaki_git_yapilandirma_degiskenleri_bag_ortamina_gecmez(tmp_path, monkeypatch):
    """Dayanak: S-23/S-25 (RESULTS §14.45). `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_SYSTEM`, `GIT_CONFIG_PARAMETERS`,
    `GIT_CONFIG_COUNT`, `GIT_ATTR_SOURCE`, `GIT_EXTERNAL_DIFF` ortamda verilse de bag ortaminda ya yoktur ya da
    sabitlenmistir."""
    ayar = tmp_path / "kotu.config"
    ayar.write_text("[status]\n\tshowUntrackedFiles = no\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(ayar))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(ayar))
    monkeypatch.setenv("GIT_CONFIG_PARAMETERS", "'status.showUntrackedFiles=no'")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_ATTR_SOURCE", "HEAD")
    monkeypatch.setenv("GIT_EXTERNAL_DIFF", "x")
    ortam = {k.upper(): v for k, v in split._bag_ortami().items()}
    assert ortam["GIT_CONFIG_GLOBAL"] == os.devnull
    assert ortam["GIT_CONFIG_NOSYSTEM"] == "1"
    for ad in ("GIT_CONFIG_SYSTEM", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT", "GIT_ATTR_SOURCE", "GIT_EXTERNAL_DIFF"):
        assert ad not in ortam, ad


@bulgu("S-34", "`.git/info/attributes` + yerel `filter.<ad>.clean` calistirilan dosyanin 'temiz' icerigini degistirir; "
               "izlenen dosyadaki degisiklik status ve ls-files -v'de gorunmez")
def test_yerel_temizleme_filtresi_izlenen_dosya_degisikligini_gizleyip_agaci_temiz_gostermemeli(tmp_path):
    """Dayanak: CLAUDE.md §3.3; D-C2 (gizlenen degisiklik). Git, stat'i degisen dosyayi indeksle karsilastirirken `clean`
    filtresinden gecirir. Filtre COMMIT EDILMIS icerigi dondururse degisen kod dosyasi 'degismemis' gorunur. Filtre ve
    attributes depo-yereldir (`.git/config`, `.git/info/attributes`), commit edilmez. Bag dosyalari (manifest, split,
    universe) ayrica bayt duzeyinde denetlenir; diger kod dosyalari (calistirilan betik dahil) denetlenmez."""
    depo = gecici_depo(tmp_path)
    _on_kosul(_temiz_mi() is True, "taban: agac temiz degil")
    yol = depo / DEPO_BETIGI
    orijinal = yol.read_bytes()
    betik = tmp_path / "temizle.py"
    betik.write_text(f"import sys\nsys.stdin.buffer.read()\nsys.stdout.buffer.write({orijinal!r})\n", encoding="utf-8")
    git(depo, "config", "filter.gizle.clean", f'"{Path(sys.executable).as_posix()}" "{betik.as_posix()}"')
    (depo / ".git" / "info").mkdir(exist_ok=True)
    with (depo / ".git" / "info" / "attributes").open("a", encoding="utf-8") as d:
        d.write(f"{DEPO_BETIGI} filter=gizle\n")
    yol.write_bytes(orijinal + b"# gizli degisiklik\n")
    _on_kosul(_duz_durum(depo) == "", "filtre degisikligi gizlemedi")
    assert _temiz_mi() is False


@bulgu("S-35", "`diff.ignoreSubmodules=all` (yerel ayar) gitlink'in yeni commit'lerini status'tan gizler; agac_temiz True")
def test_yerel_ignore_submodules_ayari_gitlink_degisikligini_gizleyip_agaci_temiz_gostermemeli(tmp_path):
    """Dayanak: CLAUDE.md §3.3. Depoya bir gitlink (ic ice git deposu) eklenir ve ic depoda yeni commit yapilir: duz
    `status` ` M alt` gosterir. Depo-yerel `diff.ignoreSubmodules=all` bunu gizler; `_DURUM_KOMUTU` bu ayari ezmez."""
    depo = gecici_depo(tmp_path)
    alt = depo / "alt"
    alt.mkdir()
    sahte_kimlik = ("-c", "user.name=a", "-c", "user.email=a@example.invalid", "-c", "commit.gpgsign=false")
    git(alt, "init", "-q")
    git(alt, *sahte_kimlik, "commit", "-q", "--allow-empty", "-m", "bir")
    git(depo, "add", "alt")
    git(depo, "commit", "-q", "-m", "gitlink")
    _on_kosul(_temiz_mi() is True, "taban: agac temiz degil")
    git(alt, *sahte_kimlik, "commit", "-q", "--allow-empty", "-m", "iki")
    _on_kosul(_duz_durum(depo) != "" and _temiz_mi() is False, "taban: gitlink degisikligi kirli gorunmuyor")
    git(depo, "config", "diff.ignoreSubmodules", "all")
    _on_kosul(_duz_durum(depo) == "", "ayar gitlink degisikligini gizlemedi")
    assert _temiz_mi() is False


@bulgu("S-36", "yerel `core.fsmonitor` komutu, kesif kaydinin `git status` cagrisinda calisir: depo-yerel yapilandirma "
               "bag ortaminda rastgele komut yurutur")
def test_yerel_fsmonitor_komutu_agac_denetimi_sirasinda_calismamali(tmp_path):
    """Dayanak: CLAUDE.md §3.3 ('temiz calisma agaci' denetimi okuma islemidir); `split._bag_git` aciklamasi. Beyaz liste
    ortami korur ama deponun kendi `.git/config`ini okur; `core.fsmonitor` bir kabuk komutudur ve `status` tarafindan
    cagrilir. Bir isaret dosyasi, komutun calistigini gosterir (komut ayrica 'degisiklik yok' diyerek status'u da
    kandirabilir)."""
    depo = gecici_depo(tmp_path)
    isaret = tmp_path / "fsmonitor_calisti.txt"
    betik = tmp_path / "izle.py"
    betik.write_text(f"open({isaret.as_posix()!r}, 'a').write('x')\n", encoding="utf-8")
    git(depo, "config", "core.fsmonitor", f'"{Path(sys.executable).as_posix()}" "{betik.as_posix()}"')
    _duz_durum(depo)
    _on_kosul(isaret.exists(), "duz git status fsmonitor komutunu calistirmadi")
    isaret.unlink()
    _temiz_mi()
    assert not isaret.exists(), "fsmonitor komutu kesif kaydi sirasinda calisti"


# =====================================================================================================
# 4. S-10: pytest oturumu isaretini pytest disinda kurmak
# =====================================================================================================

_COCUK = r"""
import os, sys
kok, varyant, tmp = sys.argv[1:4]
sys.path.insert(0, kok)
import pytest
from data import split
if varyant == "yeni":
    split._pytest_oturumu_kur(pytest.Config.__new__(pytest.Config))
elif varyant == "mock":
    from unittest import mock
    split._pytest_oturumu_kur(mock.MagicMock(spec=pytest.Config))
elif varyant == "sozluk":
    split._PYTEST_OTURUMU["config"] = object()


def ad(f):
    try:
        f()
    except Exception as hata:
        return type(hata).__name__
    return "ACIK"


print("kesif=" + ad(lambda: split.kesif_baglami_dogrula("KESIF")))
print("kayit=" + ad(lambda: split._test_kaydi_ayarla(os.path.join(tmp, "k.md"))))
"""


def _cocuk_calistir(tmp_path, varyant: str) -> dict[str, str]:
    """pytest OLMAYAN bir alt surec: `PYTEST_CURRENT_TEST` disaridan verilmis, `pytest` ice aktarilmis."""
    ortam = {k: v for k, v in os.environ.items() if not k.startswith("SHORT_LAB")}
    ortam["PYTEST_CURRENT_TEST"] = "tests/sahte.py::sahte (call)"
    cikti = subprocess.run([sys.executable, "-I", "-B", "-c", _COCUK, str(GERCEK_KOK), varyant, str(tmp_path)],
                           capture_output=True, text=True, env=ortam, timeout=180)
    _on_kosul(cikti.returncode == 0, f"alt surec dustu: {cikti.stderr[-300:]}")
    return dict(satir.split("=", 1) for satir in cikti.stdout.split() if "=" in satir)


_KORUMA = {"kesif": "KesifBaglamiYok", "kayit": "OnayKorumasi"}


def test_pytest_disinda_ortam_degiskeni_ve_pytest_importu_istisnayi_acmaz(tmp_path):
    """Dayanak: S-10 (RESULTS §14.44). Sahte `PYTEST_CURRENT_TEST` ve `import pytest` oturum isareti olmadan istisnayi
    acmaz: kesif karar noktasi kesif kosusu ister, test kaydi ayarlanamaz."""
    assert _cocuk_calistir(tmp_path, "yok") == _KORUMA


@pytest.mark.parametrize("varyant", [
    pytest.param("yeni", marks=bulgu("S-37", "`pytest.Config.__new__(pytest.Config)` isinstance denetimini gecer; "
                                              "oturum isareti kurulur, denetim_etkin() False olur")),
    pytest.param("mock", marks=bulgu("S-37", "`Mock(spec=pytest.Config)` isinstance denetimini gecer")),
    pytest.param("sozluk", marks=bulgu("S-37", "`_PYTEST_OTURUMU['config']` sozlugune dogrudan yazma denetlenmez")),
])
def test_pytest_oturum_isareti_pytest_disinda_sahte_nesneyle_kurulamaz(tmp_path, varyant):
    """Dayanak: S-10 / `split._pytest_oturumu_kur` ('YALNIZCA tests/conftest.py pytest_configure'). Beklenen: pytest
    disindaki bir surecte isaret kurulamaz; kesif karar noktasi `KesifBaglamiYok`, `_test_kaydi_ayarla` `OnayKorumasi`
    verir. Gozlenen (acik varsa): sahte nesne `isinstance` kontrolunu gecer, `_pytest_testi()` doludur, `denetim_etkin()`
    False olur, kesif baglami denetimi susar ve sahte git ortami (temiz agac, sabit HEAD) kurulabilir."""
    assert _cocuk_calistir(tmp_path, varyant) == _KORUMA


@pytest.mark.parametrize("sahte", [None, "config", object(), types.SimpleNamespace(), type("Config", (), {})()],
                         ids=["none", "metin", "object", "namespace", "ayni_adli_sinif"])
def test_pytest_oturumu_kurucusu_pytest_config_olmayan_nesneyi_reddeder(sahte):
    """Dayanak: S-10 (`isinstance(pytest_config, pytest.Config)`). Acik sahte nesneler reddedilir ve isaret degismez."""
    onceki = split._PYTEST_OTURUMU["config"]
    with pytest.raises(split.OnayKorumasi):
        split._pytest_oturumu_kur(sahte)
    assert split._PYTEST_OTURUMU["config"] is onceki


def test_bu_surecte_oturum_isareti_gercek_pytest_config_tasir():
    """Dayanak: S-10, `tests/conftest.py pytest_configure`. Test calisirken isaret gercek bir `pytest.Config`tir ve
    `_pytest_testi()` calisan testin kimligini verir."""
    assert isinstance(split._PYTEST_OTURUMU["config"], pytest.Config)
    assert split._pytest_testi() is not None


# S-38 kapandi (RESULTS §14.46): adlar `ONAY_ATLATMA_DESENI`nde ve `split._KORUNAN_ADLAR`da.
@pytest.mark.parametrize("icerik", [
    "from data import split\nsplit._pytest_oturumu_kur(None)\n",
    "from data import split\nsplit._PYTEST_OTURUMU['config'] = 1\n",
])
def test_analiz_kodu_pytest_oturum_isaretini_anarsa_tarama_yakalamali(tmp_path, icerik):
    """Dayanak: `split.py` `_PYTEST_OTURUMU` yorumu ('kurucuyu adiyla cagiran kararli bir atlatma yakalanmaz (ad taramasi
    ONAY_ATLATMA_DESENI'de)') ve CLAUDE.md §5 koruma katmani. Analiz kodu (`study/`) bu adlari anarsa tarama bunu
    ihlal saymali. Gozlenen: desen `_test_kaydi_ayarla` ve `PYTEST_CURRENT_TEST`i icerir, bu iki adi icermez."""
    (tmp_path / "study").mkdir()
    (tmp_path / "study" / "k.py").write_text(icerik, encoding="utf-8")
    assert ihlaller(ONAY_ATLATMA_DESENI, kok=tmp_path) == ["study/k.py"]
