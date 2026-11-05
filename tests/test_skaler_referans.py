"""Skaler referans (`data/_skaler_referans.py`): sabitleme, birebir kopya, dayanilan adlar, esitlik (performans 2a).

Plan v2 karar 3: F2 oncesi skaler karar yolu `data/_skaler_referans.py` modulune OLDUGU GIBI kopyalanir ve
dondurulur. Bu dosya dort seyi denetler:
  1. Sabitleme: dosyanin SHA256'si asagidaki sabittir; tek bir bayt degisirse kirmizi.
  2. Birebir kopya: referansin govdesi, `TABAN` commit'indeki `data/` dosyalarindan kopyalanan fonksiyon ve
     sabitlerin metnidir; modul aciklamasindaki uc mekanik degisiklik disinda fark yoktur.
  3. Dayanilan adlar: referans `data/`dan yalnizca `DAYANILAN` listesindeki adlari kullanir.
  4. Esitlik: sentetik dunyalarda referans ile bugunku `data/` yolu (kapi `olay_karari`, kosul `sinyal_kosulu`,
     funding tamlik satiri ve toplami) ayni sonucu verir. Bu, kopyanin dogru oldugunun kanitidir; P2a ve sonrasinda
     ayni test vektorel yolun skalerle ayni kaldiginin da kanitidir.
Deger raporlanmaz. Aga cikmaz.
"""

from __future__ import annotations

import ast
import collections
import hashlib
import re
import subprocess

import pandas as pd
import pytest

import config
from data import _skaler_referans as ref
from data import funding, pencere, pozisyon, sinyal
from esitlik_yardimcisi import H4, dunya, karar_cagrisi, kosul_cagrisi, ornek_barlar, sinif, sonuc_esit
from tarama_yardimcisi import KOK

YOL = KOK / "data" / "_skaler_referans.py"
TABAN = "4e63037"
SHA256 = "933983b51bd74ef23fb843bc6d1f5e5d9509240b47cdfc1b9bed3de202f7e1a9"


# --- 1. Sabitleme ------------------------------------------------------------------------------------

def test_referans_dosyasinin_sha256_si_sabit():
    """Dosya degisirse bu test kirmizi olur. Referans degistirilmez (modul aciklamasi)."""
    assert hashlib.sha256(YOL.read_bytes()).hexdigest() == SHA256


def test_referans_satir_sonlari_lf_olarak_sabit():
    """SHA her checkout'ta ayni olmali: `.gitattributes` dosyayi `eol=lf` tutar (core.autocrlf CRLF'e cevirmez)."""
    assert b"\r\n" not in YOL.read_bytes()
    nitelik = subprocess.run(["git", "check-attr", "eol", "--", "data/_skaler_referans.py"], cwd=KOK,
                             capture_output=True, text=True, check=True).stdout
    assert nitelik.strip().endswith("eol: lf")


# --- 2. Birebir kopya --------------------------------------------------------------------------------

def _kopyalanan_adlar() -> dict[str, list[str]]:
    """Referans dosyasindaki bolum basliklarindan (modul) ve tanimlardan kopyalanan adlar, kaynak sirasiyla."""
    metin = YOL.read_text(encoding="utf-8")
    bolumler = re.split(r"\n# =+\n# data/(\w+)\.py \(\w+\) kopyasi\n# =+\n", metin)
    adlar = {}
    for modul, govde in zip(bolumler[1::2], bolumler[2::2]):
        agac = ast.parse(govde)
        adlar[modul] = [d.name if isinstance(d, (ast.FunctionDef, ast.ClassDef)) else d.targets[0].id
                        for d in agac.body]
    return adlar


def _kaynak(modul: str) -> str:
    return subprocess.run(["git", "show", f"{TABAN}:data/{modul}.py"], cwd=KOK, capture_output=True,
                          check=True).stdout.decode("utf-8")


def _parca(modul: str, ad: str) -> str:
    if modul == "sinyal" and ad == "_sinyal_sonlu":   # degisiklik 2: kaynaktaki ad `_sonlu`
        ad = "_sonlu"
    kaynak = _kaynak(modul)
    satirlar = kaynak.splitlines(keepends=True)
    for d in ast.parse(kaynak).body:
        isim = d.name if isinstance(d, (ast.FunctionDef, ast.ClassDef)) else (
            d.targets[0].id if isinstance(d, ast.Assign) and isinstance(d.targets[0], ast.Name) else None)
        if isim == ad:
            bas = min([d.lineno] + [x.lineno for x in getattr(d, "decorator_list", [])])
            return "".join(satirlar[bas - 1:d.end_lineno])
    raise AssertionError(f"{modul}.{ad} {TABAN} commit'inde yok")


_YEREL_IMPORT = "    from data import pencere as pencere_modulu\n"


def _belgeli_degisiklikler(modul: str, ad: str, metin: str) -> str:
    """Modul aciklamasindaki uc mekanik degisiklik; baska degisiklik yoktur."""
    if modul == "funding":
        metin = metin.replace(_YEREL_IMPORT + "\n", "").replace(_YEREL_IMPORT, "")
    if modul == "sinyal":
        metin = re.sub(r"(?<![\w.])_sonlu\b", "_sinyal_sonlu", metin)
    if modul == "pozisyon" and ad == "olay_karari":
        metin = metin.replace("    return replace(sonuc, _imza=_imza(sonuc))\n",
                              "    return sonuc  # REFERANS: imzalanmaz (modul aciklamasi, degisiklik 3)\n")
    return metin


def test_referans_govdesi_taban_commitinden_birebir_kopya():
    """Referansin bes bolumu, `TABAN` commit'indeki kaynaklardan ayni sirayla kopyalanan metindir."""
    metin = YOL.read_text(encoding="utf-8")
    ilk = metin.index("\n\n\n# " + "=" * 100 + "\n# data/pencere.py") + 1   # baslik: aciklama ve importlar
    beklenen = [metin[:ilk]]
    adlar = _kopyalanan_adlar()
    assert list(adlar) == ["pencere", "funding", "eligibility", "sinyal", "pozisyon"]
    for modul, isimler in adlar.items():
        beklenen.append(f"\n\n# {'=' * 100}\n# data/{modul}.py ({TABAN}) kopyasi\n# {'=' * 100}\n")
        for ad in isimler:
            beklenen.append("\n\n" + _belgeli_degisiklikler(modul, ad, _parca(modul, ad)))
    assert "".join(beklenen).rstrip("\n") + "\n" == metin


def test_kopya_olay_karari_ve_sinyal_kosulunun_cagri_grafini_kapsar():
    """Kapinin ve kosulun bugunku cagri grafigindeki her kural fonksiyonu kopyalanmis ya da acikca dayanilandir:
    referansin modul ad alaninda her ad cozulur (eksik ad yok) ve bes takma ad referansin kendisidir."""
    for takma in ("pencere_modulu", "sinyal_modulu", "funding_modulu", "eligibility_modulu"):
        assert getattr(ref, takma) is ref
    agac = ast.parse(YOL.read_text(encoding="utf-8"))
    eksik = sorted({x.attr for x in ast.walk(agac)
                    if isinstance(x, ast.Attribute) and isinstance(x.value, ast.Name)
                    and x.value.id in ("pencere_modulu", "sinyal_modulu", "funding_modulu", "eligibility_modulu")
                    and not hasattr(ref, x.attr)})
    assert eksik == []
    # Fonksiyon govdelerinde ice aktarma yok (degisiklik 1): kopya `data/`ya yalnizca modul basindan ulasir.
    assert [n.lineno for n in ast.walk(agac) if isinstance(n, (ast.Import, ast.ImportFrom)) and n.col_offset] == []


# --- 2b. D-C1 (RESULTS §14.44): ad tekilligi, baslik importlari, statik ad cozumu ---------------------------

# Modul basligindaki ice aktarmalar (`ast.unparse`, kaynak sirasiyla). Dosya SHA'si bunlari zaten kapsar; bu liste
# degisikligin NEREDE oldugunu soyler: yeni bir `data` ice aktarmasi referansa kopyalanmamis bir yol acar.
BASLIK_IMPORTLARI = (
    "from __future__ import annotations",
    "import functools",
    "import functools as _functools",
    "import itertools",
    "import math",
    "import sys",
    "import types as _types",
    "from dataclasses import dataclass, field, replace",
    "from types import MappingProxyType",
    "import numpy as np",
    "import pandas as pd",
    "import config",
    "from data import klines as klines_modulu",
    "from data import pozisyon as _pozisyon_asli",
    "from data import split as split_modulu",
    "from data.pencere import ADIM_4H, ADIMLAR, ODEME_TOLERANSI, _plan_imzasi, _zaman_dizisi_dogrula, adim, ayni_an, "
    "ayni_an_basi, ayni_an_sonu, ayni_ya_da_once, ayni_ya_da_sonra, once, plan_dogrula, sonra, utc_zamani",
    "from data.pencere import CikisSonucu, DonemDisiSinyal, GirisBariYok, HipotezUfuklari, IleriKaymaSiniriHatasi, "
    "KumeSiniriHatasi, OlayOlusmaz, PozisyonPlani, VeriHatasi, ZamanDizisiHatasi",
    "from data.pozisyon import FundingTamDegil, OnaylanmisPozisyon, SinyalBariYok, SinyalKosuluSaglanmadi, "
    "SinyalPenceresiTamDegil, UygunDegil",
    "from data.sinyal import TepePenceresiKurulamaz, YapilandirmaHatasi",
)


def _ust_duzey_adlar(agac: ast.Module) -> list[str]:
    """Modul ad alanina ust duzeyde baglanan her ad (tanim, atama hedefi, ice aktarma), tekrarlariyla."""
    adlar = []
    for d in agac.body:
        if isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            adlar.append(d.name)
        elif isinstance(d, ast.Assign):
            adlar += [n.id for h in d.targets for n in ast.walk(h) if isinstance(n, ast.Name)]
        elif isinstance(d, ast.AnnAssign):
            adlar.append(d.target.id)
        elif isinstance(d, (ast.Import, ast.ImportFrom)):
            adlar += [a.asname or a.name.split(".")[0] for a in d.names if a.name != "annotations"]
    return adlar


def test_referanstaki_ust_duzey_adlar_tekildir():
    """Kopyalanan iki tanim ayni adi tasirsa sonraki oncekini sessizce ezer (`_sonlu` carpismasi, degisiklik 2)."""
    sayac = collections.Counter(_ust_duzey_adlar(ast.parse(YOL.read_text(encoding="utf-8"))))
    assert sorted(a for a, n in sayac.items() if n > 1) == []


def test_referansin_baslik_importlari_sabit():
    agac = ast.parse(YOL.read_text(encoding="utf-8"))
    ust = [ast.unparse(d) for d in agac.body if isinstance(d, (ast.Import, ast.ImportFrom))]
    assert tuple(ust) == BASLIK_IMPORTLARI
    # Ice aktarmalarin hepsi kopyalanan bolumlerden ONCE, baslikta.
    ilk_tanim = next(d.lineno for d in agac.body if isinstance(d, (ast.FunctionDef, ast.ClassDef)))
    assert all(d.lineno < ilk_tanim for d in agac.body if isinstance(d, (ast.Import, ast.ImportFrom)))


def _yerel_adlar(dugum) -> set[str]:
    """Bir tanimin govdesinde baglanan adlar: parametreler, atama/dongu/with/except hedefleri, ic tanimlar."""
    adlar = set()
    for x in ast.walk(dugum):
        if isinstance(x, ast.arg):
            adlar.add(x.arg)
        elif isinstance(x, ast.Name) and isinstance(x.ctx, (ast.Store, ast.Del)):
            adlar.add(x.id)
        elif isinstance(x, ast.ExceptHandler) and x.name:
            adlar.add(x.name)
        elif isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and x is not dugum:
            adlar.add(x.name)
    return adlar


def test_gecisli_cagri_grafiginde_referansta_karsiligi_olmayan_ad_yok():
    """`olay_karari` ve `sinyal_kosulu`ndan referansin icinde ulasilan her tanimda yuklenen her ad cozulur: yerel ad,
    referansin ust duzey adi (kopya, dayanilan ice aktarma, takma ad) ya da yerlesik ad. Takma adlar uzerinden
    (`pencere_modulu.x`) ulasilan ad referansta tanimlidir; `klines_modulu`, `split_modulu`, `_pozisyon_asli`
    uzerinden ulasilan ad DAYANILAN'dadir. Calisma anina birakilan (NameError ile ortaya cikacak) ad kalmaz."""
    import builtins

    agac = ast.parse(YOL.read_text(encoding="utf-8"))
    tanim = {d.name: d for d in agac.body if isinstance(d, (ast.FunctionDef, ast.ClassDef))}
    ust = set(_ust_duzey_adlar(agac))
    oz = {"pencere_modulu", "sinyal_modulu", "funding_modulu", "eligibility_modulu"}
    dis = {"klines_modulu": "data.klines", "split_modulu": "data.split", "_pozisyon_asli": "data.pozisyon"}
    eksik, gorulen, yigin = [], set(), ["olay_karari", "sinyal_kosulu"]
    while yigin:
        ad = yigin.pop()
        if ad in gorulen:
            continue
        gorulen.add(ad)
        yerel = _yerel_adlar(tanim[ad])
        for x in ast.walk(tanim[ad]):
            if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load):
                if x.id in tanim:
                    yigin.append(x.id)
                elif x.id not in yerel and x.id not in ust and not hasattr(builtins, x.id):
                    eksik.append(f"{ad}: {x.id}")
            elif isinstance(x, ast.Attribute) and isinstance(x.value, ast.Name):
                if x.value.id in oz:
                    if x.attr in tanim:
                        yigin.append(x.attr)
                    elif x.attr not in ust:
                        eksik.append(f"{ad}: {x.value.id}.{x.attr}")
                elif x.value.id in dis and x.attr not in ref.DAYANILAN[dis[x.value.id]]:
                    eksik.append(f"{ad}: {x.value.id}.{x.attr}")
    assert eksik == []
    # Grafik kopyanin buyuk bolumunu kapsamali (yanlislikla bos bir yurume testi gecirmesin).
    assert {"olay_karari", "sinyal_kosulu", "funding_tamlik_ayrintisi", "pozisyon_plani"} <= gorulen


# --- 3. Dayanilan adlar ------------------------------------------------------------------------------

def test_referans_data_dan_yalnizca_dayanilan_listesindeki_adlari_kullanir():
    agac = ast.parse(YOL.read_text(encoding="utf-8"))
    kullanilan = collections.defaultdict(set)
    takma = {}
    for d in agac.body:
        if isinstance(d, ast.ImportFrom) and d.module and d.module.startswith("data."):
            for a in d.names:
                kullanilan[d.module].add(a.name)
        if isinstance(d, ast.ImportFrom) and d.module == "data":
            for a in d.names:
                takma[a.asname or a.name] = f"data.{a.name}"
        if isinstance(d, ast.Import):
            for a in d.names:
                if a.name.startswith("data"):
                    takma[a.asname or a.name] = a.name
    for x in ast.walk(agac):
        if isinstance(x, ast.Attribute) and isinstance(x.value, ast.Name) and x.value.id in takma:
            kullanilan[takma[x.value.id]].add(x.attr)
    beklenen = {m: set(a) for m, a in ref.DAYANILAN.items() if m != "config"}
    assert dict(kullanilan) == beklenen


def test_referans_onayi_imzasizdir_getiri_tarafina_giremez():
    """Degisiklik 3: referans ikinci bir onay kaynagi degildir."""
    kimlik, _ = dunya(11, "2021-01-01", "2021-11-26 20:00")
    for t in ornek_barlar(kimlik, 40, 1):
        sonuc = karar_cagrisi(ref, "H2", kimlik, t)
        if isinstance(sonuc, pozisyon.OnaylanmisPozisyon):
            with pytest.raises(ValueError):
                pozisyon.onay_dogrula(sonuc)
            with pytest.raises(ValueError):
                pozisyon.pozisyon_fiyatlari(sonuc)
            return
    pytest.fail("ornekte onayli pozisyon yok (dunya kurulusu)")


# --- 4. Esitlik --------------------------------------------------------------------------------------

DUNYALAR = {
    # 330 gun, KESIF icinde: bosluklar, bozuk hucre, gec funding, ritim 8 -> 4 -> 1, eksik ve NaN funding.
    "ic": (101, "2021-01-01", "2021-11-26 20:00", 30),
    # KESIF sonunu (2025-08-31) asan donem: kume sonu, ufuk, funding kesimi.
    "kesif_sonu": (102, "2025-01-01", "2025-11-26 20:00", 12),
    # KESIF basindan (2020-01-01) once baslayan donem: kume basi geriye bakis siniri.
    "kesif_basi": (103, "2019-06-01", "2020-04-26 20:00", 12),
}


def _sinir_barlari(kimlik, bar: str) -> list[pd.Timestamp]:
    """Kume sinirinin iki yanindaki barlar (dunya kume sinirini kesiyorsa)."""
    bas, bitis, _ = pozisyon.donem_kaydi(kimlik["sembol"], kimlik["donem_no"])
    adim = H4 if bar == config.BAR_4H else pd.Timedelta(days=1)
    barlar = []
    for sinir in (pd.Timestamp(config.KESIF_BASI), pd.Timestamp(config.KESIF_SONU).floor("D")):
        if bas < sinir < bitis:
            barlar += [sinir.floor("D") + i * adim for i in range(-25, 26)]
    return barlar


def _funding_satiri_esit(kimlik, poz) -> None:
    """Onayli pozisyonun funding tamlik satiri (butun sutunlar, NaN/NaT konumlari dahil) ve toplami (`==`)."""
    plan = poz.plan
    _, fr, _ = pozisyon._karar_verisi(kimlik["sembol"], poz.kume, kume_baslangic=plan.kume_baslangic,
                                      kume_bitis=plan.kume_bitis, donem_baslangic=plan.donem_baslangic,
                                      donem_bitis=plan.donem_bitis)
    assert ref.pozisyon_funding_ayrintisi(fr, plan).equals(funding.pozisyon_funding_ayrintisi(fr, plan))
    assert ref._plan_fundingi(fr, plan) == funding._plan_fundingi(fr, plan) == poz.funding_toplami


def _karsilastir(sayac, etiket, a, b, t):
    assert sonuc_esit(a, b), f"{etiket} {t}: kapi {sinif(a)}, referans {sinif(b)}"
    sayac[(etiket, sinif(a))] += 1


@pytest.mark.parametrize("hipotez", config.HIPOTEZLER)
@pytest.mark.parametrize("ad", list(DUNYALAR))
def test_referans_bugunku_yolla_ayni_sonucu_verir(ad, hipotez):
    tohum, bas, bitis, adet = DUNYALAR[ad]
    kimlik, ozel = dunya(tohum, bas, bitis)
    tanim = pencere.hipotez_ufuklari(hipotez)
    izgara = [dict(y) for y in sinyal.izgara(hipotez)]
    barlar = ornek_barlar(kimlik, adet, tohum, tanim.bar) + _sinir_barlari(kimlik, tanim.bar)
    if ad == "ic" and tanim.bar == config.BAR_4H:
        # Funding kirilmalari: gec baslangic (45. gun), eksik kayit (100. gun), NaN oran (130. gun). Pozisyon penceresi
        # kirilmayi kapsayip sinyal penceresi kapsamayan barlar `FundingTamDegil` yolunu sinar.
        bas_z = pozisyon.donem_kaydi(kimlik["sembol"], kimlik["donem_no"])[0]
        barlar += [bas_z + pd.Timedelta(hours=h) for g in (40, 98, 128) for h in range(g * 24, g * 24 + 48, 12)]
    sayac = collections.Counter()

    # Kosul (dizi kurallarinin girdisi) ve iki kontrol rolu, ilk yapilandirmada.
    for i, t in enumerate(barlar):
        _karsilastir(sayac, "kosul", kosul_cagrisi(pozisyon, hipotez, kimlik, t),
                     kosul_cagrisi(ref, hipotez, kimlik, t), t)
        for rol in ("K1", "K2"):
            a = karar_cagrisi(pozisyon, hipotez, kimlik, t, rol=rol)
            _karsilastir(sayac, rol, a, karar_cagrisi(ref, hipotez, kimlik, t, rol=rol), t)
            if isinstance(a, pozisyon.OnaylanmisPozisyon):
                _funding_satiri_esit(kimlik, a)
        if i % 5 == 0:   # ikincil ufuklar (birincil ufuk once degerlendirilir)
            for ufuk in config.IKINCIL_UFUKLAR[tanim.bar]:
                _karsilastir(sayac, "K1_ikincil", karar_cagrisi(pozisyon, hipotez, kimlik, t, ufuk=ufuk),
                             karar_cagrisi(ref, hipotez, kimlik, t, ufuk=ufuk), t)

    # Olay rolu: enjekte edilen kesitler, ilk ve son yapilandirma.
    for y in (izgara[0], izgara[-1]):
        if hipotez == "H1":
            for p in ozel["pump"] if ad == "ic" else ozel["pump"][:2]:
                _karsilastir(sayac, "pump", kosul_cagrisi(pozisyon, hipotez, kimlik, p, yapilandirma=y),
                             kosul_cagrisi(ref, hipotez, kimlik, p, yapilandirma=y), p)
                for d in (1, 3, 5, 8, 12, 13):
                    t = p + d * H4
                    _karsilastir(sayac, "teyit", kosul_cagrisi(pozisyon, hipotez, kimlik, t, yapilandirma=y, capa=p),
                                 kosul_cagrisi(ref, hipotez, kimlik, t, yapilandirma=y, capa=p), t)
                    a = karar_cagrisi(pozisyon, hipotez, kimlik, t, yapilandirma=y, rol="olay", capa=p)
                    _karsilastir(sayac, "olay", a, karar_cagrisi(ref, hipotez, kimlik, t, yapilandirma=y,
                                                               rol="olay", capa=p), t)
            continue
        if hipotez == "H2":
            olay_barlari = ozel["h2"] + barlar[::4]
        else:
            _, son, _ = pozisyon.donem_kaydi(kimlik["sembol"], kimlik["donem_no"])
            olay_barlari = list(pd.date_range(son.floor("D") - pd.Timedelta(days=50),
                                              son.floor("D") - pd.Timedelta(days=15), freq="1D")) + barlar[::4]
        for t in olay_barlari:
            a = karar_cagrisi(pozisyon, hipotez, kimlik, t, yapilandirma=y, rol="olay")
            _karsilastir(sayac, "olay", a, karar_cagrisi(ref, hipotez, kimlik, t, yapilandirma=y, rol="olay"), t)
            if isinstance(a, pozisyon.OnaylanmisPozisyon):
                _funding_satiri_esit(kimlik, a)

    # Kapsam: ic dunyada her rolde onayli pozisyon ve funding tamligi reddi gorulmeli (esitlik bos gecmesin).
    if ad == "ic":
        for rol in ("K1", "K2", "olay"):
            assert sayac[(rol, "OnaylanmisPozisyon")] > 0, (rol, dict(sayac))
        assert any(s == "SinyalPenceresiTamDegil" for _, s in sayac), dict(sayac)
        if hipotez != "H3":
            assert sayac[("K1", "FundingTamDegil")] > 0, dict(sayac)


def test_funding_kaydi_olmayan_donemde_iki_yol_ayni_reddi_verir():
    kimlik, _ = dunya(104, "2021-01-01", "2021-11-26 20:00", funding_yok=True)
    for t in ornek_barlar(kimlik, 15, 104):
        a = karar_cagrisi(pozisyon, "H2", kimlik, t)
        assert sonuc_esit(a, karar_cagrisi(ref, "H2", kimlik, t))


# --- 5. Analiz kodu taramasi -------------------------------------------------------------------------

def test_analiz_kodu_skaler_referansi_anmaz():
    from tarama_yardimcisi import skaler_referans_ihlalleri

    assert skaler_referans_ihlalleri() == []


def test_tarama_istisnalari_yalnizca_tests_ve_esitlik_betikleri(tmp_path):
    from tarama_yardimcisi import skaler_referans_ihlalleri

    dosyalar = {
        "tests/test_x.py": True, "data/_skaler_referans.py": True,
        "analysis/00_veri_denetimi/esitlik_kapi.py": True,
        "analysis/00_veri_denetimi/calistir.py": False, "analysis/00_veri_denetimi/alt/esitlik_x.py": False,
        "data/pozisyon.py": False, "study/kos.py": False, "events/h1.ipynb": False, "tools/arac.pyw": False,
    }
    for goreli in dosyalar:
        yol = tmp_path / goreli
        yol.parent.mkdir(parents=True, exist_ok=True)
        yol.write_text("from data import _skaler_referans\n", encoding="utf-8")
    assert skaler_referans_ihlalleri(tmp_path) == sorted(g for g, izinli in dosyalar.items() if not izinli)
