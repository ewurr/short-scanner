"""Performans 2a sizinti testcisi turu: kirmaya yonelik saldirilar (CLAUDE.md §3 ve §5).

Hedefler: (1) skaler referansin tarama disi kullanimi ve sabitlenmesinin sinirlari, (2) gercek veri esitlik betiginden
deger cikisi, (3) plan onbellegi (`pozisyon._PlanSerisi`) ve kume sinirlari, (4) S-11 ve S-5/S-6 yeni hallerinin ve
D-C2'nin atlatilmasi, (5) NFKC disi Unicode/kodlama hileleriyle ad taramasindan kacis, (6) toplu funding yolunun
(`_planlar_tamlik_satirlari` + `_satirdan_toplam`) n = 1 yoldan ve skaler referanstan ayrisan girdileri.

Kural: `@bulgu(...)` isaretli testler strict xfail'dir; saldiri BASARILI olursa (kodda acik varsa) test KIRMIZIDIR yerine
"xfail" olarak gorunur, savunma ONARILIRSA test XPASS(strict) ile kirmizi olur ve isaret kaldirilmalidir. Isaretsiz testler
savunmanin tuttugunu gosterir. Saldiri on kosulu kurulamazsa test atlanir (skip), sessizce xfail olmaz.
Deger raporlanmaz, getiri hesaplanmaz, aga cikilmaz, gercek `cache/` okunmaz. Alt surecler yalnizca yerel python ve git.
Sabit tohum kullanilir.
"""

from __future__ import annotations

import ast
import dataclasses
import importlib._bootstrap_external as _be
import importlib.util
import inspect
import json
import marshal
import os
import py_compile
import subprocess
import sys
import types
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import config
from data import _skaler_referans as ref
from data import funding, kume_bellegi, pencere, pozisyon, sinyal, split
import kapi_yardimcisi
from esitlik_yardimcisi import H4, dunya, karar_cagrisi, ornek_barlar, sonuc_esit
from onay_yardimcisi import DEPO_BETIGI, gecici_depo, gecici_kayit, git, kosu
from tarama_yardimcisi import KOK, skaler_referans_ihlalleri

sys.path.insert(0, str(KOK / "analysis" / "00_veri_denetimi"))
import esitlik_kapi as ek  # noqa: E402

BAS, BITIS = "2021-01-01", "2021-11-26 20:00"


def bulgu(kod: str, aciklama: str):
    """Saldiri basarili: kodda acik var. strict xfail; yalnizca `assert` basarisizligi xfail sayilir."""
    return pytest.mark.xfail(strict=True, raises=AssertionError, reason=f"{kod}: {aciklama}")


def _on_kosul(kosul: bool, mesaj: str) -> None:
    """Saldirinin on kosulu kurulamadiysa test atlanir (xfail'e donusup gercek bir sonucu gizlemesin)."""
    if not kosul:
        pytest.skip(f"saldiri on kosulu kurulamadi: {mesaj}")


# =====================================================================================================
# 1. Skaler referans: tarama atlatma ve sabitleme sinirlari
# =====================================================================================================

def _tara(kok: Path, goreli: str, icerik) -> list[str]:
    yol = kok / goreli
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_bytes(icerik if isinstance(icerik, bytes) else icerik.encode("utf-8"))
    return skaler_referans_ihlalleri(kok)


@pytest.mark.parametrize("goreli", ["analysis/h/kos.py", "events/h1.py", "study/k.pyw", "events/defter.ipynb",
                                    "tools/arac.py", "analysis/00_veri_denetimi/calistir.py",
                                    "analysis/00_veri_denetimi/alt/esitlik_x.py", "data/pozisyon.py"])
@pytest.mark.parametrize("icerik", ["from data import _skaler_referans as r\n", "import data._skaler_referans\n",
                                    "x = 'skaler_referans'\n", "# skaler_referans\n"])
def test_acik_referans_adi_her_uzantida_ve_dizinde_yakalanir(tmp_path, goreli, icerik):
    """Dayanak: tests/tarama_yardimcisi.SKALER_REFERANS_DESENI (plan v2 karar 3). Metin olarak yazilmis ad, istisna
    disindaki her dizinde ve uc uzantida (.py, .pyw, .ipynb) yakalanmali; IZINLI_ALTLAR muafiyeti buraya uygulanmaz."""
    assert _tara(tmp_path, goreli, icerik) == [goreli]


@bulgu("S-14", "skaler referans taramasi .ipynb dosyasini ham metin olarak tarar; JSON \\u0073 kacisi adi gizler")
def test_ipynb_json_unicode_kacisi_referans_adini_gizleyemez(tmp_path):
    """Dayanak: SKALER_REFERANS_UZANTILARI .ipynb'yi kapsar. Defter kaynagi JSON'dur; `\\u0073kaler_referans` JSON
    cozuldugunde `skaler_referans` olur ama ham metin taramasi (regex) bunu gormez. NFKC degil, JSON kacisi."""
    govde = '{"cells": [{"cell_type": "code", "source": ["from data import _\\u0073kaler_referans as r\\n"]}]}'
    cozulmus = json.loads(govde)["cells"][0]["source"][0]
    _on_kosul("skaler_referans" in cozulmus, "JSON cozulunce ad olusmadi")
    assert _tara(tmp_path, "events/defter.ipynb", govde) == ["events/defter.ipynb"]


@bulgu("S-15", "kaynak kodlama bildirimi (utf-7 / unicode_escape) ile ad ham baytlarda gorunmez, Python yine ice aktarir")
@pytest.mark.parametrize("govde", [
    pytest.param(b"# coding: utf-7\nfrom data import _+AHM-kaler_referans\n", id="utf-7"),
    pytest.param(b"# coding: unicode_escape\nfrom data import _\\u0073kaler_referans\n", id="unicode_escape"),
])
def test_kodlama_bildirimi_referans_adini_taramadan_gizleyemez(tmp_path, govde):
    """Dayanak: SKALER_REFERANS_DESENI. PEP 263 kodlama satiri dosyanin geri kalanini baska bir codec ile cozer; tarama
    yalnizca utf-8 metne bakar. NFKC disi bir hile: ad Python tarafindan cozulur, regex'e gorunmez."""
    try:
        agac = ast.parse(govde)
    except (SyntaxError, LookupError, ValueError) as hata:
        pytest.skip(f"bu Python kodlama bildirimini kabul etmedi: {type(hata).__name__}")
    adlar = {a.name for n in ast.walk(agac) if isinstance(n, ast.ImportFrom) for a in n.names}
    _on_kosul("_skaler_referans" in adlar, "cozulmus kaynakta ad yok")
    assert _tara(tmp_path, "analysis/h/kos.py", govde) == ["analysis/h/kos.py"]


@bulgu("S-16", "tarama yalnizca .py/.pyw/.ipynb; kaynaksiz .pyc ayni adi ice aktarabilir")
def test_kaynaksiz_pyc_referans_adini_taramadan_gizler(tmp_path):
    """Dayanak: SKALER_REFERANS_UZANTILARI. Python bir dizinde kaynaksiz `x.pyc` dosyasini ice aktarir; bayt kodunda
    `_skaler_referans` adi vardir (`co_names`) ama tarama bu uzantiya bakmaz."""
    kaynak = tmp_path / "kaynak" / "_k.py"
    kaynak.parent.mkdir()
    kaynak.write_text("from data import _skaler_referans\n", encoding="utf-8")
    kok = tmp_path / "depo"
    pyc = kok / "analysis" / "h" / "kos.pyc"
    pyc.parent.mkdir(parents=True)
    py_compile.compile(str(kaynak), cfile=str(pyc), doraise=True)
    kod = marshal.loads(pyc.read_bytes()[16:])
    _on_kosul("_skaler_referans" in kod.co_names, "bayt kodunda ad yok")
    assert skaler_referans_ihlalleri(kok) == ["analysis/h/kos.pyc"]


# S-17 kapandi (ana oturum, RESULTS §14.45): `esitlik_kapi` referansi modul duzeyinde bir adla tutmaz; referans yalnizca
# karsilastirma fonksiyonlarinin icinde ice aktarilir. Saldiri on kosulu (`ek.referans`) artik kurulamaz; test savunmanin
# tuttugunu gosterir.
def test_esitlik_betigi_uzerinden_referansa_adsiz_erisim_taranmaz(tmp_path):
    """Dayanak: SKALER_REFERANS_DESENI yalnizca `skaler_referans` metnini arar. Istisna dosyasini (`esitlik_kapi.py`) ice
    aktaran analiz kodu referansa ad anmadan erisememeli: modulun hicbir niteligi (ve varsayilan argumani) referans degil."""
    assert not hasattr(ek, "referans")
    for ad, deger in vars(ek).items():
        assert deger is not ref, ad
        assert all(x is not ref for x in (getattr(deger, "__defaults__", None) or ())), ad


def test_referans_onayi_getiri_giris_noktalarinda_reddedilir():
    """Dayanak: _skaler_referans aciklamasi degisiklik 3 ('ikinci bir onay kaynagi degildir'). Referansin urettigi onayli
    pozisyon, `replace` ile kopyalansa bile, getiri/fiyat/funding giris noktalarindan gecemez."""
    kimlik, _ = dunya(11, BAS, BITIS)
    for t in ornek_barlar(kimlik, 40, 1):
        sonuc = karar_cagrisi(ref, "H2", kimlik, t)
        if isinstance(sonuc, pozisyon.OnaylanmisPozisyon):
            for fonk in (pozisyon.onay_dogrula, pozisyon.pozisyon_fiyatlari, funding.pozisyon_fundingi):
                with pytest.raises((ValueError, TypeError)):
                    fonk(sonuc)
                with pytest.raises((ValueError, TypeError)):
                    fonk(dataclasses.replace(sonuc))
            return
    pytest.skip("ornekte onayli pozisyon yok")


def test_yuklu_referans_modulunun_bayt_kodu_sabitlenen_kaynakla_ayni():
    """Dayanak: SHA256 testi yalnizca KAYNAK baytlarini sabitler; `__pycache__` bayt kodu mtime+boyut basligiyla dogrulanir
    ve ayni basliga sahip bozuk bir .pyc kaynak degismeden yuklenir (S-30). Bu test o durumu OKUMA ANINDA yakalar: yuklu
    modulun her fonksiyonunun bayt kodu, kaynak dosyadan yeniden derlenenle ayni olmali."""
    yol = Path(ref.__file__)
    derlenen = compile(yol.read_bytes(), str(yol), "exec", dont_inherit=True)
    kodlar = {c.co_name: c for c in derlenen.co_consts if isinstance(c, types.CodeType)}
    sayi = 0
    for ad, nesne in vars(ref).items():
        if inspect.isfunction(nesne) and nesne.__module__ == ref.__name__ and ad in kodlar:
            assert nesne.__code__ == kodlar[ad], f"{ad}: yuklu bayt kodu kaynakla ayni degil"
            sayi += 1
    assert sayi > 30


@bulgu("S-30", "kaynak SHA256'si yurutulen bayt kodunu sabitlemez: ayni mtime/boyut basligiyla yazilmis .pyc kaynaga baskin")
def test_kaynak_baytlari_ayniyken_yurutulen_kod_degistirilebilir(tmp_path):
    """Dayanak: tests/test_skaler_referans.py SHA256 sabitlemesi. Kaynak dosya DEGISMEDEN, `__pycache__` altina kaynagin
    mtime ve boyutunu tasiyan baska bir kodun .pyc'si yazilirsa Python onu yukler. Kaynak SHA'si ayni kalir, calisan
    kod farklidir. (Onlem: hash-tabanli pyc ya da yukleme sonrasi bayt kodu karsilastirmasi; yukaridaki test sonuncusu.)"""
    paket = tmp_path / "paket"
    paket.mkdir()
    kaynak = paket / "_sk.py"
    kaynak.write_text("MARKER = 'orig'\n", encoding="utf-8", newline="\n")
    st = kaynak.stat()
    kod = compile("MARKER = 'evil'\n", str(kaynak), "exec")
    pyc = _be._code_to_timestamp_pyc(kod, int(st.st_mtime), st.st_size)
    onbellek = Path(importlib.util.cache_from_source(str(kaynak)))
    onbellek.parent.mkdir(exist_ok=True)
    onbellek.write_bytes(pyc)
    cikti = subprocess.run(
        [sys.executable, "-c", "import sys; sys.path.insert(0, sys.argv[1]); import _sk; print(_sk.MARKER)", str(paket)],
        capture_output=True, text=True, timeout=60)
    _on_kosul(cikti.returncode == 0, "alt surec calismadi")
    assert cikti.stdout.strip() == "orig"


# =====================================================================================================
# 2. Esitlik betigi: deger cikisi
# =====================================================================================================

def test_esitlik_betigi_print_cagrilari_yalnizca_sayi_ve_adlari_yazar():
    """Dayanak: esitlik_kapi.py aciklamasi ('Getiri, sinyal degeri ya da olay sayisi hesaplanmaz, yazilmaz'). `print`
    argumanlarinda gecen degiskenler izinli listeyle sinirli: yeni bir degisken yazdirilirsa kirmizi olur."""
    agac = ast.parse((KOK / "analysis" / "00_veri_denetimi" / "esitlik_kapi.py").read_text(encoding="utf-8"))
    izinli = {"s", "sembol", "karsi", "uyus", "hata", "sys"}
    bulunan = 0
    for dugum in ast.walk(agac):
        if isinstance(dugum, ast.Call) and isinstance(dugum.func, ast.Name) and dugum.func.id == "print":
            bulunan += 1
            adlar = {n.id for a in [*dugum.args, *[k.value for k in dugum.keywords]] for n in ast.walk(a)
                     if isinstance(n, ast.Name)}
            assert adlar <= izinli, f"print izinsiz degisken yazdiriyor: {sorted(adlar - izinli)}"
    assert bulunan >= 3


def test_kos_fazladan_alanlari_cikti_tablosuna_almaz(monkeypatch):
    """Dayanak: esitlik_kapi.SUTUNLAR. `sembol_isi` satirina sizan bir deger alani (getiri, olay sayisi) CSV'ye gitmez:
    cikti tablosu SUTUNLAR'a indirgenir."""
    class Kayit:
        def alanlar(self):
            return {"head_commit": "a" * 40, "agac_temiz": True}

    @contextmanager
    def kesif():
        yield Kayit()

    monkeypatch.setattr(ek, "split_modulu", types.SimpleNamespace(kesif_kosusu=kesif))

    def isi(s, ayar):
        return [{"sembol": s, "donem_no": 0, "hipotez": "H2", "yapilandirma": "y", "rol": "K1", "bar_kumesi": "tum",
                 "karsilastirilan_bar": 1, "uyusmayan_bar": 0, "ilk_20_uyusmayan": "", "sure_s": 0.1, "hata": "",
                 "getiri": 0.123456, "olay_sayisi": 777}]

    monkeypatch.setattr(ek, "sembol_isi", isi)
    tablo, _ = ek.kos(["X"], {"bar": "ornek"}, 1, None)
    metin = tablo.to_csv(index=False)
    assert list(tablo.columns) == ek.SUTUNLAR
    assert "0.123456" not in metin and "777" not in metin


def _sentinel_ayari(bar: str, roller) -> dict:
    return {"hipotezler": ["H2"], "yapilandirma": "ilk", "roller": list(roller), "funding_satiri": True, "bar": bar,
            "n": 5, "sure_siniri_dk": 15.0}


SENTINEL = "DEGER=0.987654321"


def test_ornek_kipinde_beklenmeyen_hata_yalnizca_sinif_adi_olarak_yazilir(monkeypatch):
    """Dayanak: esitlik_kapi aciklamasi: '`hata` yalnizca beklenmeyen bir hatanin SINIF adidir; mesaj yazilmaz (mesaj deger
    icerebilir)'. Referans funding adimi mesajinda deger tasiyan bir hata firlatirsa satira yalnizca sinif adi girer."""
    kimlik, _ = dunya(402, BAS, BITIS)
    monkeypatch.setattr(ek, "_donemler", lambda s: [0])
    for ad, deger in (("SINIR_DONEM", 3), ("SINIR_KUME", 3), ("SINIR_RITIM", 2)):
        monkeypatch.setattr(ek, ad, deger)

    def bozuk(fr, plan):
        raise RuntimeError(SENTINEL)

    monkeypatch.setattr(ref, "pozisyon_funding_ayrintisi", bozuk)
    satirlar = ek.sembol_isi(kimlik["sembol"], _sentinel_ayari("ornek", []))
    birim = [s for s in satirlar if s["rol"] == ek.FUNDING_SATIRI]
    # Performans 2b-0 (D-B2): beklenmeyen hata artik bar duzeyinde, taraf ve sinif adiyla sayilir (ana oturum guncelledi).
    assert len(birim) == 1 and birim[0]["beklenmeyen_hata_referans"] > 0
    assert birim[0]["ilk_20_beklenmeyen"].startswith("referans:RuntimeError@")
    assert SENTINEL not in repr(satirlar)


# S-18 kapandi (ana oturum, RESULTS §14.45): kalibrasyon dongusu ve `uyarlamali` kip kaldirildi; birim disi hatalar da
# `_guvenli_sembol_isi` ile sinif adina indirgenir. Test savunmanin tuttugunu gosterir.
def test_kalibrasyon_asamasi_hata_mesajini_disari_sizdirir(monkeypatch):
    """Dayanak: esitlik_kapi aciklamasi ('mesaj yazilmaz'). Kosucunun kullandigi `_guvenli_sembol_isi`, eski `uyarlamali`
    kipte de, ornek kipte deger tasiyan bir birim hatasinda da mesaji disari vermez."""
    kimlik, _ = dunya(402, BAS, BITIS)
    monkeypatch.setattr(ek, "_donemler", lambda s: [0])
    for ad, deger in (("SINIR_DONEM", 3), ("SINIR_KUME", 3), ("SINIR_RITIM", 2)):
        monkeypatch.setattr(ek, ad, deger)

    def bozuk(fr, plan):
        raise RuntimeError(SENTINEL)

    monkeypatch.setattr(ref, "pozisyon_funding_ayrintisi", bozuk)
    for kip in ("uyarlamali", "ornek"):
        satirlar = ek._guvenli_sembol_isi(kimlik["sembol"], _sentinel_ayari(kip, []))
        assert SENTINEL not in repr(satirlar)
    eski = ek._guvenli_sembol_isi(kimlik["sembol"], _sentinel_ayari("uyarlamali", []))
    assert [s["hata"] for s in eski] == ["ValueError"]


@pytest.mark.parametrize("hedef", [KOK / "tests" / ".." / "analysis" / "ara", KOK / "ara", KOK / "cache" / "ara",
                                   KOK / "analysis" / ".." / ".." / KOK.name / "ara"])
def test_ara_dizin_dolayli_yollarla_depoya_girilemez(monkeypatch, hedef):
    """Dayanak: esitlik_kapi._ara_dizin_dogrula ('ara kayit dizini depo DISINDA olmali'). `..` parcalari, depo koku ve
    `cache/` cozumlenip reddedilir. `mkdir` etkisiz kilinir: savunma delinirse bile diske yazilmaz."""
    monkeypatch.setattr(Path, "mkdir", lambda *a, **k: None)
    with pytest.raises(SystemExit):
        ek._ara_dizin_dogrula(hedef)
    with pytest.raises(SystemExit):
        ek._ara_dizin_dogrula(str(hedef))


# =====================================================================================================
# 3. Plan onbellegi (pozisyon._PlanSerisi) ve kume sinirlari
# =====================================================================================================

def _onayli_bar(kimlik, hipotez="H2", adet=60, tohum=5):
    for t in ornek_barlar(kimlik, adet, tohum):
        if isinstance(karar_cagrisi(pozisyon, hipotez, kimlik, t), pozisyon.OnaylanmisPozisyon):
            return t
    pytest.skip("ornekte onayli pozisyon yok")


def test_kesif_plan_serisi_c1_ve_c2_sorgusuna_donmez():
    """Dayanak: ön-kayıt §3 rev.13 / CLAUDE.md §5: anahtar kume adini tasir. KESIF icin isinmis plan ve veri, ayni sembol ve
    bar icin C1/C2 sorgusuna donmez; sorgu onay kosusu olmadan reddedilir ve bellek anahtarlari degismez."""
    kimlik, _ = dunya(403, BAS, BITIS)
    t = _onayli_bar(kimlik)
    onceki = sorted(kume_bellegi._BELLEK, key=repr)
    uzunluklar = {a: len(v[3]) for a, v in kume_bellegi._BELLEK.items() if a[0] == "karar"}
    assert uzunluklar and all(n >= 1 for n in uzunluklar.values())
    for kume in config.ONAY_KUMELERI:
        sonuc = karar_cagrisi(pozisyon, "H2", kimlik, t, kume=kume)
        assert isinstance(sonuc, split.OnayGerekli), (kume, type(sonuc).__name__)
    assert sorted(kume_bellegi._BELLEK, key=repr) == onceki
    assert {a: len(v[3]) for a, v in kume_bellegi._BELLEK.items() if a[0] == "karar"} == uzunluklar


def test_grup_denetimi_plan_isabetinde_de_calisir():
    """Dayanak: CLAUDE.md §3.2-3.3 (A/B grubu) ve ön-kayıt §3. KESIF karari bellekte isindiktan SONRA sembolun grubu B'ye
    cevrilirse (bolme tablosu degisti gibi) isabet grup denetimini atlamamali: ValueError, onayli pozisyon degil."""
    kimlik, _ = dunya(404, BAS, BITIS)
    t = _onayli_bar(kimlik)
    kapi_yardimcisi.SENTETIK_GRUPLAR[kimlik["sembol"]] = "B"
    sonuc = karar_cagrisi(pozisyon, "H2", kimlik, t)
    assert isinstance(sonuc, ValueError) and not isinstance(sonuc, pencere.OlayOlusmaz)


def test_onay_kosusu_bitince_plan_serisi_bellekten_dusmus_ve_yeniden_acilamaz(tmp_path):
    """Dayanak: CLAUDE.md §5 ('onay koşusunun açılışı ile kapanışı bu kopyaları geçersiz kılar'). C1 kosusunda isinan plan
    serisi, kosu kapaninca bellekte kalmaz; kosu disinda ayni C1 sorgusu OnayGerekli verir ve bellege C1 girdisi yazilmaz."""
    kimlik, _ = dunya(405, BAS, BITIS)
    kapi_yardimcisi.SENTETIK_GRUPLAR[kimlik["sembol"]] = "B"
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    y = next((dict(x) for x in sinyal.izgara("H2")
              if sinyal.yapilandirma_kimligi("H2", x) == "H2:phi=0.0003,k=3"), None)
    _on_kosul(y is not None, "kilitlenen yapilandirma izgarada yok")
    t = ornek_barlar(kimlik, 3, 1)[-5]
    with kosu("H2", "C1"):
        karar_cagrisi(pozisyon, "H2", kimlik, t, kume="C1", yapilandirma=y)
        icerde = [v for a, v in kume_bellegi._BELLEK.items() if a[0] == "karar" and a[2] == "C1"]
        _on_kosul(len(icerde) == 1 and len(icerde[0][3]) >= 1, "kosu icinde plan serisi olusmadi")
    assert kume_bellegi.girdi_sayisi() == 0
    sonuc = karar_cagrisi(pozisyon, "H2", kimlik, t, kume="C1", yapilandirma=y)
    assert isinstance(sonuc, split.OnayGerekli)
    assert not any(a[2] == "C1" for a in kume_bellegi._BELLEK)


@bulgu("S-19", "plan onbellegi anahtar-plan tutarliligini dogrulamaz: t1 anahtarina konan t2 plani t1 karari olarak doner")
def test_plan_onbellegi_anahtar_plan_tutarliligini_dogrulamaz():
    """Dayanak: CLAUDE.md §3.6 (sinyal t barinda, islem t+1) ve plan v2 karar 5. `_PlanSerisi.al` kayitli plani anahtarin
    zamaniyla karsilastirmaz; paylasilan seriye (kopyasi kendisi) konan baska bir imzali plan, sorulan t yerine o planin
    zamaniyla karar uretir. Seriye erisim tarama ile kapali (KAYIT_DESENI), ama kapi kendi icinde tutarlilik denetlemiyor."""
    kimlik, _ = dunya(406, BAS, BITIS)
    tanim = pencere.hipotez_ufuklari("H2")
    onayli = []
    for t in ornek_barlar(kimlik, 60, 5):
        if isinstance(karar_cagrisi(pozisyon, "H2", kimlik, t), pozisyon.OnaylanmisPozisyon):
            onayli.append(pd.Timestamp(t))
        if len(onayli) == 2:
            break
    _on_kosul(len(onayli) == 2, "iki onayli bar bulunamadi")
    t1, t2 = onayli
    bas, bitis, _ = pozisyon.donem_kaydi(kimlik["sembol"], kimlik["donem_no"])
    kb, ks = pozisyon.kume_sinirlari("KESIF")
    serisi = pozisyon._karar_girdisi(kimlik["sembol"], "KESIF", kume_baslangic=kb, kume_bitis=ks,
                                     donem_baslangic=bas, donem_bitis=bitis)[3]
    a1, a2 = ((tanim.bar, tanim.birincil, tanim.birincil, t) for t in (t1, t2))
    _on_kosul(a1 in serisi._harita and a2 in serisi._harita, "plan anahtari beklenen bicimde degil")
    serisi._harita[a1] = serisi._harita[a2]
    sonuc = karar_cagrisi(pozisyon, "H2", kimlik, t1)
    if isinstance(sonuc, pozisyon.OnaylanmisPozisyon):
        assert sonuc.plan.sinyal_zamani == t1


def test_onbellekteki_plan_zorla_bozulursa_imza_denetimi_reddeder():
    """Dayanak: pencere.plan_dogrula (on-kayit §4 rev.8). Paylasilan plan nesnesinin alani bellek duzeyinde (frozen'i
    `object.__setattr__` ile asarak) bozulursa, sonraki karar bozuk plani kabul etmemeli (ValueError)."""
    kimlik, _ = dunya(409, BAS, BITIS)
    t = _onayli_bar(kimlik)
    ilk = karar_cagrisi(pozisyon, "H2", kimlik, t)
    object.__setattr__(ilk.plan, "ufuk", 6)       # paylasilan ayni nesne
    sonuc = karar_cagrisi(pozisyon, "H2", kimlik, t)
    assert isinstance(sonuc, ValueError), type(sonuc).__name__


@pytest.mark.parametrize("sira", [(6, 42, 18), (42, 18, 6), (18, 6, 42)])
def test_ufuk_sorgu_sirasi_karari_degistirmez_plan_ufuklar_arasi_karismaz(sira):
    """Dayanak: ön-kayıt §4 'Ufuk değerlerinin bağlanması' (rev.10). Plan anahtari ufku tasir: ikincil ufuk once sorulsa
    da, ters sirayla sorulsa da kapi karari referansla ayni kalir."""
    kimlik, _ = dunya(407, BAS, BITIS)
    barlar = ornek_barlar(kimlik, 12, 8, sinir=3)
    kume_bellegi.temizle()
    for t in barlar:
        for ufuk in sira:
            a = karar_cagrisi(pozisyon, "H2", kimlik, t, ufuk=ufuk)
            assert sonuc_esit(a, karar_cagrisi(ref, "H2", kimlik, t, ufuk=ufuk)), (ufuk, t)


def test_karar_verisi_cerceveleri_bozulunca_sonraki_karar_degismez():
    """Dayanak: CLAUDE.md §5 ('bellekte tutulan her kopya ...'). `_karar_verisi`nin dondurdugu cerceveler kopyadir;
    fiyat, funding ve 1d hacim cercevesi bozulsa bile bellekteki girdi ve sonraki karar degismez."""
    kimlik, _ = dunya(408, BAS, BITIS)
    t = _onayli_bar(kimlik)
    onceki = karar_cagrisi(pozisyon, "H2", kimlik, t)
    bas, bitis, _ = pozisyon.donem_kaydi(kimlik["sembol"], kimlik["donem_no"])
    kb, ks = pozisyon.kume_sinirlari("KESIF")
    m, fr, g = pozisyon._karar_verisi(kimlik["sembol"], "KESIF", kume_baslangic=kb, kume_bitis=ks,
                                      donem_baslangic=bas, donem_bitis=bitis)
    m["open"] = -1.0
    m["high"] = 1e9
    fr["oran"] = 9.0
    fr.drop(fr.index[:50], inplace=True)
    g["quote_volume"] = 0.0
    assert sonuc_esit(onceki, karar_cagrisi(pozisyon, "H2", kimlik, t))


# =====================================================================================================
# 4. Toplu funding yolu: n = 1 ve skaler referansla uc yonlu esitlik
# =====================================================================================================

DB = pd.Timestamp("2021-01-01", tz="UTC")
DS = pd.Timestamp("2021-04-30 20:00", tz="UTC")


def _taban_funding(rng) -> pd.DataFrame:
    zaman, aralik = [], []
    t = DB
    while t <= DS + pd.Timedelta(hours=24):
        gun = (t - DB) / pd.Timedelta(days=1)
        a = 8.0 if gun < 40 else (4.0 if gun < 70 else (1.0 if gun < 85 else 8.0))
        zaman.append(t)
        aralik.append(a)
        t = t + pd.Timedelta(hours=a)
    fr = pd.DataFrame({"odeme_zamani": pd.DatetimeIndex(zaman), "aralik_saat": aralik})
    fr["oran"] = rng.normal(0.0002, 0.0003, len(fr))
    fr["oran_8h"] = fr["oran"] * 8.0 / fr["aralik_saat"]
    return fr


def _planlar_kur(rng, donem_bas=DB, adet=70) -> list:
    tam = pd.date_range(DB, DS, freq=H4)
    zamanlar = tam[rng.random(len(tam)) > 0.02]
    zamanlar = zamanlar[zamanlar >= donem_bas]
    # Duzeltme (ana oturum, RESULTS §14.44): donem bitis bari seride olmali; rastgele dusurulurse plan VeriHatasi verir
    # (dogru davranis, bulgu degil). Kurulus hatasi giderildi; saldirinin kendisi degismedi.
    if zamanlar[-1] != tam[-1]:
        zamanlar = zamanlar.append(tam[-1:])
    kb, ks = pozisyon.kume_sinirlari("KESIF")
    sec = set(rng.choice(len(tam), size=adet, replace=False).tolist()) | set(range(len(tam) - 25, len(tam)))
    sec |= set(range(0, 10))
    planlar = []
    for i in sorted(sec):
        if tam[i] < donem_bas:
            continue
        for ufuk in ((18, 6, 42) if i % 3 == 0 else (18,)):
            try:
                planlar.append(pencere.pozisyon_plani(
                    zamanlar, tam[i], ufuk, config.BAR_4H, birincil_ufuk=18, kume_baslangic=kb, kume_bitis=ks,
                    donem_baslangic=donem_bas, donem_bitis=DS))
            except pencere.OlayOlusmaz:
                continue
    return planlar


def _bozulmus(fr: pd.DataFrame, tur: str, rng) -> pd.DataFrame:
    fr = fr.copy()
    n = len(fr)
    if tur == "temiz":
        return fr
    if tur == "kayit_dusur":
        return fr.drop(index=fr.index[rng.random(n) < 0.03]).reset_index(drop=True)
    if tur == "jitter":
        ofset = np.array([-61.0, -60.0, -59.999, 0.0, 0.0, 59.999, 60.0, 61.0])
        fr["odeme_zamani"] = fr["odeme_zamani"] + pd.to_timedelta(rng.choice(ofset, n), unit="s")
        return fr
    if tur == "nan_aralik":
        fr.loc[rng.random(n) < 0.03, "aralik_saat"] = np.nan
        return fr
    if tur == "sifir_aralik":
        maske = rng.random(n) < 0.03
        fr.loc[maske, "aralik_saat"] = rng.choice([0.0, -8.0], int(maske.sum()))
        return fr
    if tur == "nan_oran":
        fr.loc[rng.random(n) < 0.03, "oran"] = np.nan
        return fr
    if tur == "inf_oran":
        maske = rng.random(n) < 0.02
        fr.loc[maske, "oran"] = rng.choice([np.inf, -np.inf], int(maske.sum()))
        return fr
    if tur == "oran_metin":
        fr["oran"] = fr["oran"].astype(str)
        return fr
    if tur == "tek_kayit":
        return fr.iloc[[n // 2]].reset_index(drop=True)
    if tur == "bos":
        return fr.iloc[0:0].reset_index(drop=True)
    if tur == "gec_baslangic":
        return fr.loc[fr["odeme_zamani"] >= DB + pd.Timedelta(days=45)].reset_index(drop=True)
    if tur == "sirasiz":
        return fr.sample(frac=1.0, random_state=3)
    if tur == "tekrarli":
        return pd.concat([fr, fr.iloc[5:9]]).sort_values("odeme_zamani", kind="stable").reset_index(drop=True)
    if tur == "yakin_cift":
        ek_satir = fr.iloc[[10]].copy()
        ek_satir["odeme_zamani"] = ek_satir["odeme_zamani"] + pd.Timedelta(seconds=30)
        return pd.concat([fr, ek_satir]).sort_values("odeme_zamani", kind="stable").reset_index(drop=True)
    if tur == "nat":
        fr.loc[20, "odeme_zamani"] = pd.NaT
        return fr
    if tur == "aralik_uyumsuz":
        fr["aralik_saat"] = 1.0
        return fr
    raise AssertionError(tur)


TURLER = ["temiz", "kayit_dusur", "jitter", "nan_aralik", "sifir_aralik", "nan_oran", "inf_oran", "oran_metin",
          "tek_kayit", "bos", "gec_baslangic", "sirasiz", "tekrarli", "yakin_cift", "nat", "aralik_uyumsuz"]


def _sonuc_n1(fr, plan):
    try:
        t = funding._pozisyon_tamlik_satiri(fr, plan)
        return ("ok", t.satir, funding._satirdan_toplam(fr, plan, t))
    except Exception as hata:  # noqa: BLE001 - sinif karsilastirilir
        return ("hata", type(hata).__name__)


def _sonuc_genel(fr, plan):
    try:
        return ("ok", funding.pozisyon_funding_ayrintisi(fr, plan), funding._plan_fundingi(fr, plan))
    except Exception as hata:  # noqa: BLE001
        return ("hata", type(hata).__name__)


def _sonuc_ref(fr, plan):
    try:
        return ("ok", ref.pozisyon_funding_ayrintisi(fr, plan), ref._plan_fundingi(fr, plan))
    except Exception as hata:  # noqa: BLE001
        return ("hata", type(hata).__name__)


def _sonuc_toplu(fr, planlar):
    try:
        satirlar = funding._planlar_tamlik_satirlari(fr, planlar)
    except Exception as hata:  # noqa: BLE001
        return [("hata", type(hata).__name__)] * len(planlar)
    cikti = []
    for plan, tamlik in zip(planlar, satirlar):
        try:
            cikti.append(("ok", tamlik.satir, funding._satirdan_toplam(fr, plan, tamlik)))
        except Exception as hata:  # noqa: BLE001
            cikti.append(("hata", type(hata).__name__))
    return cikti


def _esit(a, b) -> bool:
    if a[0] != b[0]:
        return False
    if a[0] == "hata":
        return a[1] == b[1]
    toplam_esit = (np.isnan(a[2]) and np.isnan(b[2])) or a[2] == b[2]
    return bool(list(a[1].index) == list(b[1].index) and a[1].equals(b[1]) and toplam_esit)


@pytest.mark.parametrize("seed", [0, 1])
@pytest.mark.parametrize("tur", TURLER)
def test_toplu_n1_genel_ve_referans_yollari_bozuk_funding_serilerinde_ayrismaz(tur, seed):
    """Dayanak: plan v2 karar 5 / D-C6 ve ön-kayıt §4 'Funding tamlığı' (rev.9-11). Sirasiz, tekrarli, yakin-cift, NaT, NaN/0/
    negatif aralik, NaN/inf/metin oran, bos/tek kayit, gec baslangic, tolerans kenarina jitter: toplu yol, n = 1 yol, genel
    yol ve skaler referans ayni sonucu (satirin butun sutunlari, toplam ya da ayni hata sinifi) vermeli."""
    rng = np.random.default_rng(1000 + seed)
    fr = _bozulmus(_taban_funding(rng), tur, rng)
    planlar = _planlar_kur(rng)
    assert len(planlar) > 40
    toplu = _sonuc_toplu(fr, planlar)
    for plan, t in zip(planlar, toplu):
        beklenen = _sonuc_ref(fr, plan)
        assert _esit(_sonuc_n1(fr, plan), beklenen), (tur, "n1", plan.sinyal_zamani)
        assert _esit(_sonuc_genel(fr, plan), beklenen), (tur, "genel", plan.sinyal_zamani)
        assert _esit(t, beklenen), (tur, "toplu", plan.sinyal_zamani)


def test_toplu_yol_siralama_tekrar_ve_donem_baslangicindan_bagimsiz():
    """Dayanak: plan v2 karar 5 (toplu cagri = n = 1 cagrinin vektorel hali). Plan listesi karistirilip tekrarlandiginda
    ve farkli donem baslangicli planlar tek cagrida verildiginde her plan kendi n = 1 sonucunu alir; `tamlik.plan` ayni nesne."""
    rng = np.random.default_rng(77)
    fr = _taban_funding(rng)
    planlar = _planlar_kur(rng) + _planlar_kur(rng, donem_bas=DB + pd.Timedelta(days=30), adet=40)
    assert len(planlar) > 60
    sirali = planlar + [planlar[i] for i in rng.integers(0, len(planlar), 15)]
    karisik = [sirali[i] for i in rng.permutation(len(sirali))]
    toplu = funding._planlar_tamlik_satirlari(fr, karisik)
    assert len(toplu) == len(karisik)
    sonuclar = _sonuc_toplu(fr, karisik)
    for plan, tamlik, sonuc in zip(karisik, toplu, sonuclar):
        assert tamlik.plan is plan
        assert _esit(sonuc, _sonuc_ref(fr, plan)), plan.sinyal_zamani
    # Bolunmus cagri da ayni sonucu verir.
    yarim = len(karisik) // 2
    assert all(_esit(a, b) for a, b in zip(_sonuc_toplu(fr, karisik[:yarim]) + _sonuc_toplu(fr, karisik[yarim:]),
                                           sonuclar))


def _tam_ve_dolu_pencereli_plan(rng):
    fr = _taban_funding(rng)
    planlar = _planlar_kur(rng)
    for plan, tamlik in zip(planlar, funding._planlar_tamlik_satirlari(fr, planlar)):
        if bool(tamlik.satir["tam"]) and tamlik.son_index > tamlik.capa_index + 1:
            return fr, plan, tamlik
    pytest.skip("tam ve dolu pencereli plan bulunamadi")


@bulgu("S-20", "`_satirdan_toplam` satiri yalnizca kayit SAYISIYLA bagliyor: ayni uzunlukta farkli funding serisiyle sayi doner")
@pytest.mark.parametrize("bozma", ["zaman_kaydirma", "sonsuz_oran"])
def test_satirdan_toplam_ayni_uzunlukta_farkli_seriyi_reddetmez(bozma):
    """Dayanak: funding._satirdan_toplam docstring ('Satir bu plan ve bu funding serisi icin kurulmus olmali (ValueError)');
    on-kayit §4 rev.9 (tamlik atlanmaz) ve rev.11 (gecerli oran). A serisinden kurulan satir, ayni uzunluktaki B serisiyle
    kullanilinca ValueError ya da (B icin dogru olan) NaN beklenir. Gozlenen: A'nin indeksleriyle B'den kesilen toplam."""
    rng = np.random.default_rng(5)
    fr, plan, tamlik = _tam_ve_dolu_pencereli_plan(rng)
    b = fr.copy()
    if bozma == "zaman_kaydirma":
        b["odeme_zamani"] = b["odeme_zamani"] + pd.Timedelta(days=1000)
    else:
        b.loc[tamlik.capa_index + 1, "oran"] = np.inf
    _on_kosul(np.isnan(ref._plan_fundingi(b, plan)), "B serisi icin dogru sonuc NaN degil")
    try:
        gozlenen = funding._satirdan_toplam(b, plan, tamlik)
    except ValueError:
        return    # beklenen savunma
    assert np.isnan(gozlenen), f"B icin NaN beklenirdi, gozlenen {gozlenen!r}"


@bulgu("S-21", "kolonsuz bos funding: `_satirdan_toplam` sessizce NaN doner, skaler `_plan_fundingi` KeyError verir")
def test_kolonsuz_bos_funding_toplu_yol_ve_skaler_referans_ayrisir():
    """Dayanak: plan v2 karar 6 (esitlik: ayni sonuc ya da ayni hata sinifi). `pd.DataFrame()` icin tamlik hesabi bos
    seri kisayoluna (`funding.empty`) girer ve `_satirdan_toplam` NaN doner; skaler yol `odeme_zamani` sutununu
    dogrularken KeyError verir. Kapi duzeyinde etkisi yok (ikisi de FundingTamDegil'e varir) ama iki yol ayrisiyor."""
    rng = np.random.default_rng(6)
    plan = _planlar_kur(rng)[0]
    bos = pd.DataFrame()
    yeni = _sonuc_n1(bos, plan)
    eski = _sonuc_ref(bos, plan)
    assert yeni[0] == eski[0], (yeni[0], eski)


@bulgu("S-22", "`_TamlikSatiri.satir` degistirilebilir Seri: tam=True yapilan tam olmayan satir icin `_satirdan_toplam` 0.0 doner")
def test_tamlik_satiri_degistirilince_toplam_tamligi_atlar():
    """Dayanak: funding._satirdan_toplam ('Tamlik atlanmaz ... tam degilse NaN doner'); on-kayit §4 rev.9. Satir bir pandas
    Serisidir ve frozen dataclass icinde degistirilebilir; capa yokken (`capa_index = son_index = -1`) tam=True yapilan satir
    bos dilimden finite 0.0 toplam uretir. Modul disina kapali ic adim; tarama ile analiz kodundan yasak."""
    rng = np.random.default_rng(8)
    fr = _bozulmus(_taban_funding(rng), "gec_baslangic", rng)
    for plan in _planlar_kur(rng):
        tamlik = funding._pozisyon_tamlik_satiri(fr, plan)
        if not bool(tamlik.satir["tam"]) and tamlik.capa_index == -1:
            tamlik.satir["tam"] = True
            toplam = funding._satirdan_toplam(fr, plan, tamlik)
            assert np.isnan(toplam), f"tam olmayan satir icin NaN beklenirdi, gozlenen {toplam!r}"
            return
    pytest.skip("capasiz plan bulunamadi")


# =====================================================================================================
# 5. S-11, S-5/S-6 ve D-C2: yeni hallerinin atlatilmasi
# =====================================================================================================

_S11_KOD = """
import sys
sys.path.insert(0, sys.argv[1])
from pathlib import Path
import config
from data import binance_vision as bv, onbellek_manifest as mf, split
yol = Path(config.ONBELLEK_DIZINI) / tuple(bv._ONBELLEK_TURLERI)[0] / "NOSUCHUSDT" / "2021-01.parquet"
degerler = {"none": None, "false": False, "sifir": 0, "float": 1.5, "bytes": b"x", "liste": ["a"], "bos_metin": "",
            "olmayan": "olmayan_dizin/manifest.csv", "nul": "nul"}
for ad, deger in degerler.items():
    mf.MANIFEST_YOLU = deger
    etkin = mf.denetim_etkin()
    try:
        mf.okuma_denetle(yol)
        okuma = "DONDU"
    except Exception as h:
        okuma = type(h).__name__
    try:
        with split.kesif_kosusu():
            kesif = "ACILDI"
    except Exception as h:
        kesif = type(h).__name__
    print(ad, etkin, okuma, kesif)
"""


def test_manifest_yolu_bozuk_degerleri_pytest_disinda_ne_okumayi_ne_kesif_kosusunu_acar():
    """Dayanak: S-11 (RESULTS §14.44), ön-kayıt §3 rev.13 ('koşu dondurulmuş yerel önbellekten okur'). pytest disinda
    `MANIFEST_YOLU` None/bool/sayi/bytes/liste/bos metin/olmayan yol yapilsa da denetim acik kalir; `okuma_denetle`
    sessizce None donmez, `kesif_kosusu` acilmaz."""
    env = {k: v for k, v in os.environ.items()
           if not k.upper().startswith("SHORT_LAB_") and k.upper() != "PYTEST_CURRENT_TEST"}
    cikti = subprocess.run([sys.executable, "-B", "-c", _S11_KOD, str(config.KOK)], capture_output=True, text=True,
                           timeout=180, env=env)
    _on_kosul(cikti.returncode == 0, f"alt surec basarisiz: {cikti.stderr[-300:]}")
    satirlar = [s.split() for s in cikti.stdout.strip().splitlines()]
    assert len(satirlar) == 9
    for ad, etkin, okuma, kesif in satirlar:
        assert etkin == "True", ad
        assert okuma != "DONDU", ad
        assert kesif != "ACILDI", ad


def _sahte_depo(kok: Path) -> Path:
    sahte = kok / "sahte"
    sahte.mkdir()
    git(sahte, "init", "-q")
    git(sahte, "checkout", "-q", "-b", "main")
    for anahtar, deger in [("user.name", "S"), ("user.email", "s@example.invalid"), ("commit.gpgsign", "false"),
                           ("core.autocrlf", "false")]:
        git(sahte, "config", anahtar, deger)
    (sahte / "baska.txt").write_text("sahte depo\n", encoding="utf-8")
    git(sahte, "add", ".")
    git(sahte, "commit", "-q", "-m", "sahte")
    return sahte


def _temiz_mi():
    return split._kesif_kaydi_kur(None).agac_temiz


def test_bag_ortami_dort_degiskeni_suzer_ve_replace_ile_pathspec_bayraklarini_zorlar(monkeypatch):
    """Dayanak: S-5/S-6 (RESULTS §14.44). GIT_DIR, GIT_INDEX_FILE, GIT_WORK_TREE, GIT_OBJECT_DIRECTORY ortamdan atilir;
    GIT_NO_REPLACE_OBJECTS ve GIT_LITERAL_PATHSPECS ortamda 0 verilse bile 1 olur."""
    for ad in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE", "GIT_OBJECT_DIRECTORY"):
        monkeypatch.setenv(ad, "x")
    monkeypatch.setenv("GIT_NO_REPLACE_OBJECTS", "0")
    monkeypatch.setenv("GIT_LITERAL_PATHSPECS", "0")
    ortam = split._bag_ortami()
    assert not {"GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE", "GIT_OBJECT_DIRECTORY"} & {k.upper() for k in ortam}
    assert ortam["GIT_NO_REPLACE_OBJECTS"] == "1" and ortam["GIT_LITERAL_PATHSPECS"] == "1"


# S-23 kapandi (RESULTS §14.45): git ortami beyaz listeyle kurulur; hicbir GIT_* degiskeni gecmez.
def test_bag_ortami_depo_ve_yapilandirma_yonlendiren_diger_degiskenleri_de_suzmeli(monkeypatch):
    """Dayanak: S-5 niyeti ('Depo, indeks, calisma agaci ve nesne dizini git'e ortam degiskeniyle baska bir yere
    cevrilemez'). Ayni sinifin diger degiskenleri: ortak dizin (refs ve nesneler), alternatif nesne dizinleri, ad alani,
    ve `status.showUntrackedFiles`, `core.*` gibi ayarlari enjekte eden GIT_CONFIG_* ailesi suzulmuyor."""
    adlar = ["GIT_COMMON_DIR", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE", "GIT_CONFIG_COUNT",
             "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM"]
    for ad in adlar:
        monkeypatch.setenv(ad, "x")
    # Performans 2b-0 (ana oturum): beyaz listeli ortam GIT_CONFIG_GLOBAL'i KENDISI os.devnull'a kurar; olcut ortamdaki
    # DEGERIN ("x") gecmemesidir, adin bulunmamasi degil.
    ortam = {k.upper(): v for k, v in split._bag_ortami().items()}
    gecen = sorted(a for a in adlar if ortam.get(a) == "x")
    assert gecen == [], f"suzulmeyen degiskenler: {gecen}"
    assert ortam["GIT_CONFIG_GLOBAL"] == os.devnull and ortam["GIT_CONFIG_NOSYSTEM"] == "1"


def test_depo_yonlendiren_dort_degisken_kesif_kaydini_ve_head_okumasini_saptiramaz(tmp_path, monkeypatch):
    """Dayanak: S-5 (RESULTS §14.44). GIT_DIR/GIT_WORK_TREE/GIT_INDEX_FILE/GIT_OBJECT_DIRECTORY temiz bir sahte depoya
    cevrilince kesif kaydinin HEAD'i ve HEAD'deki bayt okumasi yine gercek depodan gelir."""
    depo = gecici_depo(tmp_path)
    sahte = _sahte_depo(tmp_path)
    head = git(depo, "rev-parse", "HEAD").strip()
    _on_kosul(head != git(sahte, "rev-parse", "HEAD").strip(), "iki depo ayni commit")
    beklenen_bayt = (depo / DEPO_BETIGI).read_bytes()
    monkeypatch.setenv("GIT_DIR", str(sahte / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(sahte))
    monkeypatch.setenv("GIT_INDEX_FILE", str(sahte / ".git" / "index"))
    monkeypatch.setenv("GIT_OBJECT_DIRECTORY", str(sahte / ".git" / "objects"))
    assert split._kesif_kaydi_kur(None).head_commit == head
    assert split._git_bayt("cat-file", "blob", f"HEAD:{DEPO_BETIGI}") == beklenen_bayt


# S-24 savunma tuttu (ana oturum, RESULTS §14.44): ilk kosuda XPASS(strict); isaret kaldirildi, test savunmanin tuttugunu gosterir.
def test_git_common_dir_kesif_kaydinin_headini_saptirir(tmp_path, monkeypatch):
    """Dayanak: S-5 niyeti + ön-kayıt §3 (kosu commit'e baglanir). `GIT_COMMON_DIR` refs ve nesneleri baska bir ortak dizinden
    okutur; `_bag_ortami` bunu suzmuyor. Beklenen: kayit gercek deponun HEAD'ini tasir."""
    depo = gecici_depo(tmp_path)
    sahte = _sahte_depo(tmp_path)
    head = git(depo, "rev-parse", "HEAD").strip()
    sahte_head = git(sahte, "rev-parse", "HEAD").strip()
    _on_kosul(head != sahte_head, "iki depo ayni commit")
    monkeypatch.setenv("GIT_COMMON_DIR", str(sahte / ".git"))
    assert split._kesif_kaydi_kur(None).head_commit == head


def test_replace_referansi_head_icindeki_bayt_okumasini_saptiramaz(tmp_path):
    """Dayanak: S-6 (RESULTS §14.44). `git replace` ile HEAD commit'i baska bir commit'le degistirilse bile
    `HEAD:<yol>` bayt okumasi gercek HEAD'in baytlarini verir (--no-replace-objects)."""
    depo = gecici_depo(tmp_path)
    yol = depo / DEPO_BETIGI
    v1 = yol.read_bytes()
    yol.write_bytes(v1 + b"# v2\n")
    git(depo, "add", ".")
    git(depo, "commit", "-q", "-m", "v2")
    v2 = yol.read_bytes()
    git(depo, "replace", "HEAD", "HEAD~1")
    duz = subprocess.run(["git", "cat-file", "blob", f"HEAD:{DEPO_BETIGI}"], cwd=depo, capture_output=True)
    _on_kosul(duz.stdout == v1, "replace referansi etkili olmadi")
    assert split._git_bayt("cat-file", "blob", f"HEAD:{DEPO_BETIGI}") == v2


# S-25 kapandi (RESULTS §14.45): GIT_CONFIG_* git'e ulasmaz; status --untracked-files=all.
def test_git_yapilandirma_ortam_degiskeni_izlenmeyen_dosyayi_gizleyip_agaci_temiz_gosterir(tmp_path, monkeypatch):
    """Dayanak: CLAUDE.md §3.3 ('temiz çalışma ağacı'); S-5/S-6 niyeti. Ortam degiskeniyle enjekte edilen git ayari
    `git status --porcelain` ciktisini bosaltir; `_kesif_kaydi_kur` `--untracked-files` bayragi vermedigi icin kaydi
    'temiz' yazar."""
    depo = gecici_depo(tmp_path)
    (depo / "izlenmeyen.py").write_text("x = 1\n", encoding="utf-8")
    _on_kosul(_temiz_mi() is False, "taban: izlenmeyen dosya kirli sayilmali")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "status.showUntrackedFiles")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "no")
    gorunen = subprocess.run(["git", "status", "--porcelain"], cwd=depo, capture_output=True, text=True).stdout
    _on_kosul(gorunen.strip() == "", "bu git surumu GIT_CONFIG_COUNT'u desteklemiyor")
    assert _temiz_mi() is False


# S-26 kapandi (RESULTS §14.45): `-c status.showUntrackedFiles=all` depo ayarini ezer.
def test_yerel_git_ayari_izlenmeyen_dosyayi_gizleyip_agaci_temiz_gosterir(tmp_path):
    """Dayanak: CLAUDE.md §3.3. `esitlik_kapi.agac_temiz` acikca `--untracked-files=all` verir; `_kesif_kaydi_kur` vermez
    ve git ayarina (kullanicinin global ayari dahil) bagli kalir. Beklenen: izlenmeyen dosya her ayarda kirli sayilir."""
    depo = gecici_depo(tmp_path)
    git(depo, "config", "status.showUntrackedFiles", "no")
    (depo / "izlenmeyen.py").write_text("x = 1\n", encoding="utf-8")
    _on_kosul(git(depo, "status", "--porcelain").strip() == "", "ayar izlenmeyen dosyayi gizlemedi")
    assert _temiz_mi() is False


@pytest.mark.parametrize("bayraklar", [("--assume-unchanged",), ("--skip-worktree",),
                                       ("--assume-unchanged", "--skip-worktree")], ids=["assume", "skip", "ikisi"])
def test_gizlenen_degisiklik_kesif_kaydinda_kirli_sayilir(tmp_path, bayraklar):
    """Dayanak: D-C2 (RESULTS §14.44). `--assume-unchanged` / `--skip-worktree` ile `git status`tan gizlenen izlenen dosya
    degisikligi (tek bayrak ya da ikisi birden) `ls-files -v` etiketiyle bulunur ve agaci kirli yapar."""
    depo = gecici_depo(tmp_path)
    _on_kosul(_temiz_mi() is True, "baslangic agaci temiz degil")
    for bayrak in bayraklar:
        git(depo, "update-index", bayrak, DEPO_BETIGI)
    yol = depo / DEPO_BETIGI
    yol.write_bytes(yol.read_bytes() + b"# gizli degisiklik\n")
    _on_kosul(git(depo, "status", "--porcelain").strip() == "", "bayrak degisikligi gizlemedi")
    assert _temiz_mi() is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows'ta ctime olusturma zamanidir; baska platformda git degisikligi yakalar")
@bulgu("S-27", "ayni boyda icerik degisikligi + geri yuklenen mtime: git status temiz, agac_temiz True (izlenen dosya baytlari degisti)")
def test_ayni_boyda_icerik_degisikligi_ve_geri_yuklenen_mtime_agaci_temiz_gosterir(tmp_path):
    """Dayanak: CLAUDE.md §3.3 ('temiz çalışma ağacı'). git stat bilgisine (mtime, boyut) dayanir; icerik degisip boyut ve
    mtime geri yuklenirse (Windows'ta ctime degismez) hem `status` hem `ls-files -v` temiz gorunur. Bag dosyalari
    (manifest, split, universe) bayt duzeyinde ayrica denetlenir, diger kod dosyalari denetlenmez. KASITLI atlatma."""
    depo = gecici_depo(tmp_path)
    yol = depo / DEPO_BETIGI
    eski_ns = 1_000_000_000 * 10 ** 9
    os.utime(yol, ns=(eski_ns, eski_ns))
    git(depo, "update-index", "--refresh")
    orijinal = yol.read_bytes()
    degisen = orijinal.replace(b"test", b"tesx")
    _on_kosul(degisen != orijinal and len(degisen) == len(orijinal), "icerik degistirilemedi")
    yol.write_bytes(degisen)
    os.utime(yol, ns=(eski_ns, eski_ns))
    gercek = git(depo, "hash-object", DEPO_BETIGI).strip()
    _on_kosul(gercek != git(depo, "rev-parse", f"HEAD:{DEPO_BETIGI}").strip(), "icerik HEAD ile ayni")
    assert _temiz_mi() is False


class _KayitTemizlik:
    def __init__(self, temiz):
        self.temiz = temiz

    def alanlar(self):
        return {"head_commit": "a" * 40, "agac_temiz": self.temiz}


# S-28 kapandi (ana oturum, RESULTS §14.45): betigin ikinci `agac_temiz` uygulamasi kaldirildi; kosu `KesifKaydi.agac_temiz`
# degerine dayanir (D-C2 `ls-files -v` denetimi orada). Test savunmanin tuttugunu gosterir.
def test_esitlik_betigi_agac_temiz_gizlenen_degisikligi_gormez(tmp_path, monkeypatch):
    """Dayanak: esitlik_kapi aciklamasi ve D-C2. assume-unchanged ile gizlenen degisiklik kesif kaydinda kirli sayilir ve
    esitlik kosusu o kayitla BASLAMAZ."""
    assert not hasattr(ek, "agac_temiz")
    depo = gecici_depo(tmp_path)
    git(depo, "update-index", "--assume-unchanged", DEPO_BETIGI)
    yol = depo / DEPO_BETIGI
    yol.write_bytes(yol.read_bytes() + b"# gizli degisiklik\n")
    _on_kosul(git(depo, "status", "--porcelain").strip() == "", "bayrak degisikligi gizlemedi")
    temiz = _temiz_mi()
    assert temiz is False

    @contextmanager
    def kesif():
        yield _KayitTemizlik(temiz)

    monkeypatch.setattr(ek, "split_modulu", types.SimpleNamespace(kesif_kosusu=kesif))
    monkeypatch.setattr(ek, "sembol_isi", lambda s, a: pytest.fail("kirli agacta sembol kostu"))
    with pytest.raises(SystemExit):
        ek.kos(["X"], {"bar": "ornek"}, 1, None)


# S-29 kapandi (ana oturum, RESULTS §14.45): betik agaci kendisi denetlemez; kesif kaydi bag ortamiyla denetler. Test
# savunmanin tuttugunu gosterir.
def test_esitlik_betigi_agac_temiz_depo_yonlendirmesine_aldanir(tmp_path, monkeypatch):
    """Dayanak: S-5 niyeti. GIT_DIR/GIT_WORK_TREE temiz bir sahte depoya cevrilse de kesif kaydi kirli agaci kirli yazar."""
    assert not hasattr(ek, "agac_temiz")
    depo = gecici_depo(tmp_path)
    sahte = _sahte_depo(tmp_path)
    (depo / "izlenmeyen.py").write_text("x = 1\n", encoding="utf-8")
    _on_kosul(_temiz_mi() is False, "taban: kirli agac kirli gorunmeli")
    monkeypatch.setenv("GIT_DIR", str(sahte / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(sahte))
    assert _temiz_mi() is False
