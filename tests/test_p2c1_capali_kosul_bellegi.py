"""P2c-1, kararlar A5: capali kosul serileri icin ayri bellek (`pozisyon._CAPALI_KOSUL_BELLEGI`,
`pozisyon._CAPALI_KOSUL_HATALARI`, sinir `pozisyon.CAPALI_KOSUL_AZAMI_GIRDI`).

G15 olcumu (`p2c1_kayit\\a2_50_olcum_g15_cikti.txt`): H1'in dizi yuruyusu pump basina bir tek capali kosul serisi kurar
(kararlar B 7); paylasilan LRU'ya yazildiklarinda ikinci yapilandirmada K1 serisi onbellekten gelmiyordu. Bu dosya:
  - capali kosul serileri paylasilan bellege yazilmaz; K1 ve capasiz kosul serisi, sinirdan fazla capali seriden sonra
    onbellekte kalir (ayni nesne);
  - ayri bellek sinirlidir (LRU, en eski duser);
  - HATA DAVRANISI DEGISMEDI (`_seri_bellekten` parametrelendi): hata veren kurulum seri bellegine yazilmaz, hata
    bellegine bir kez yazilir, ayni anahtar yeniden kurulmadan AYNI hata nesnesini yukseltir; donem isareti kurulum
    sirasinda degisirse ne seri ne hata yazilir; `MemoryError` tutulmaz; hata bellegi sinirlidir; kosu acilisi ve
    kapanisi (`kume_bellegi.temizle`) dort sozlugu de bosaltir. Capasiz kosul serisi ve kapi serisi paylasilan ciftte
    (`_SERI_BELLEGI`, `_SERI_HATALARI`) kalir; capali kosul serisi yalnizca ayri ciftte.
Sentetik dunya; deger, olay sayisi ve kosulun dogru oldugu bar sayisi yazilmaz. Aga cikmaz.
"""

from __future__ import annotations

import ast

import pandas as pd
import pytest

from data import kume_bellegi, pozisyon, sinyal
from esitlik_yardimcisi import H4, dunya
from tarama_yardimcisi import KOK

BAS, BITIS = "2021-01-01", "2021-08-31 20:00"


def _y(hipotez, i=0):
    return dict(sinyal.izgara(hipotez)[i])


@pytest.fixture
def dunya_c():
    kume_bellegi.temizle()
    kimlik, _ = dunya(631, BAS, BITIS)
    izgara = pozisyon.hipotez_izgarasi_barlari("H1", kume="KESIF", **kimlik)
    return kimlik, izgara


def _capali(kimlik, p, i=0):
    return pozisyon.kosul_serisi("H1", _y("H1", i), kume="KESIF", **kimlik, capa=p)


def _kosul_anahtarlari(sozluk):
    return [a for a in sozluk if a[0] == "kosul_serisi"]


# --- Ayri bellek: paylasilan LRU dolmaz ------------------------------------------------------------------------------

def test_A5_capali_kosul_serileri_paylasilan_bellege_yazilmaz_K1_ve_capasiz_seri_kalir(dunya_c):
    kimlik, izgara = dunya_c
    k1 = pozisyon.kapi_serisi("H1", _y("H1"), "K1", kume="KESIF", **kimlik)
    pump = pozisyon.kosul_serisi("H1", _y("H1"), kume="KESIF", **kimlik)
    paylasilan_once = list(pozisyon._SERI_BELLEGI)
    n = pozisyon.SERI_AZAMI_GIRDI + 8
    for p in izgara[300:300 + n]:
        _capali(kimlik, p)
    assert list(pozisyon._SERI_BELLEGI) == paylasilan_once, "capali kosul serisi paylasilan bellege yazildi"
    assert pozisyon.kapi_serisi("H1", _y("H1"), "K1", kume="KESIF", **kimlik) is k1
    assert pozisyon.kosul_serisi("H1", _y("H1"), kume="KESIF", **kimlik) is pump
    assert all(a[6] is not None for a in pozisyon._CAPALI_KOSUL_BELLEGI)
    assert len(pozisyon._CAPALI_KOSUL_BELLEGI) == pozisyon.CAPALI_KOSUL_AZAMI_GIRDI


def test_A5_capa_dizili_kosul_serisi_de_ayri_bellekte(dunya_c):
    """Izgara uzunlugunda capa dizisi (esitlik betiginin `kosul` birimi) da capali seridir: ayri bellekte."""
    kimlik, izgara = dunya_c
    capa = pd.DatetimeIndex([t - (1 + i % 12) * H4 for i, t in enumerate(izgara)])
    seri = pozisyon.kosul_serisi("H1", _y("H1"), kume="KESIF", **kimlik, capa=capa)
    assert not _kosul_anahtarlari(pozisyon._SERI_BELLEGI)
    assert len(pozisyon._CAPALI_KOSUL_BELLEGI) == 1
    assert pozisyon.kosul_serisi("H1", _y("H1"), kume="KESIF", **kimlik, capa=capa) is seri


def test_A5_ayri_bellek_sinirli_LRU_en_eskiyi_dusurur(dunya_c, monkeypatch):
    kimlik, izgara = dunya_c
    monkeypatch.setattr(pozisyon, "CAPALI_KOSUL_AZAMI_GIRDI", 3)
    capalar = list(izgara[300:306])
    seriler = [_capali(kimlik, p) for p in capalar]
    assert len(pozisyon._CAPALI_KOSUL_BELLEGI) == 3
    # Son uc capa bellekte (ayni nesne); en eski uc capa dustu (yeniden kurulur, yeni nesne).
    for p, s in zip(capalar[3:], seriler[3:]):
        assert _capali(kimlik, p) is s
    assert _capali(kimlik, capalar[0]) is not seriler[0]
    assert len(pozisyon._CAPALI_KOSUL_BELLEGI) == 3
    # Paylasilan sinir ayri bellegi etkilemez.
    monkeypatch.setattr(pozisyon, "SERI_AZAMI_GIRDI", 1)
    for p in izgara[400:405]:
        _capali(kimlik, p)
    assert len(pozisyon._CAPALI_KOSUL_BELLEGI) == 3


# --- Hata davranisi degismedi (iki cift icin ayni kurallar) ----------------------------------------------------------

def _kurulum_hatasi(monkeypatch, hata=None, oncesinde=None):
    """`kosul_serisi` kurulumunun cekirdegini bozar; her kurulum denemesi sayilir."""
    sayac = []

    def bozuk(*a, **k):
        sayac.append(1)
        if oncesinde is not None:
            oncesinde()
        raise (hata if hata is not None else ValueError("bilerek"))

    monkeypatch.setattr(pozisyon, "_kosul_satirlari", bozuk)
    return sayac


def _iste(kimlik, izgara, capali, i=0):
    if capali:
        return pozisyon.kosul_serisi("H1", _y("H1", i), kume="KESIF", **kimlik, capa=izgara[300])
    return pozisyon.kosul_serisi("H1", _y("H1", i), kume="KESIF", **kimlik)


def _ciftler(capali):
    """(hatanin yazilacagi cift, yazilmamasi gereken cift)."""
    kendi = (pozisyon._CAPALI_KOSUL_BELLEGI, pozisyon._CAPALI_KOSUL_HATALARI) if capali else \
        (pozisyon._SERI_BELLEGI, pozisyon._SERI_HATALARI)
    obur = (pozisyon._SERI_BELLEGI, pozisyon._SERI_HATALARI) if capali else \
        (pozisyon._CAPALI_KOSUL_BELLEGI, pozisyon._CAPALI_KOSUL_HATALARI)
    return kendi, obur


@pytest.mark.parametrize("capali", [False, True], ids=["capasiz", "capali"])
def test_A5_hata_seri_bellegine_yazilmaz_bir_kez_kurulur_ayni_hata_nesnesi_doner(dunya_c, monkeypatch, capali):
    kimlik, izgara = dunya_c
    sayac = _kurulum_hatasi(monkeypatch)
    with pytest.raises(ValueError, match="bilerek") as ilk:
        _iste(kimlik, izgara, capali)
    for _ in range(3):
        with pytest.raises(ValueError) as sonraki:
            _iste(kimlik, izgara, capali)
        assert sonraki.value is ilk.value
    assert len(sayac) == 1
    (kendi_bellek, kendi_hata), (obur_bellek, obur_hata) = _ciftler(capali)
    assert not _kosul_anahtarlari(kendi_bellek), "kismi seri yok: hata seri bellegine yazilmaz"
    assert len(_kosul_anahtarlari(kendi_hata)) == 1
    assert not _kosul_anahtarlari(obur_bellek) and not _kosul_anahtarlari(obur_hata)


@pytest.mark.parametrize("capali", [False, True], ids=["capasiz", "capali"])
def test_A5_kurulum_sirasinda_donem_isareti_degisirse_ne_seri_ne_hata_yazilir(dunya_c, monkeypatch, capali):
    kimlik, izgara = dunya_c
    asil = pozisyon._kosul_satirlari
    _kurulum_hatasi(monkeypatch, oncesinde=kume_bellegi.temizle)
    with pytest.raises(ValueError):
        _iste(kimlik, izgara, capali)
    for sozluk in (pozisyon._SERI_HATALARI, pozisyon._CAPALI_KOSUL_HATALARI, pozisyon._SERI_BELLEGI,
                   pozisyon._CAPALI_KOSUL_BELLEGI):
        assert not _kosul_anahtarlari(sozluk)

    def basarili(*a, **k):
        kume_bellegi.temizle()
        return asil(*a, **k)

    monkeypatch.setattr(pozisyon, "_kosul_satirlari", basarili)
    _iste(kimlik, izgara, capali)
    assert not _kosul_anahtarlari(pozisyon._SERI_BELLEGI) and not pozisyon._CAPALI_KOSUL_BELLEGI


@pytest.mark.parametrize("capali", [False, True], ids=["capasiz", "capali"])
def test_A5_memory_error_tutulmaz(dunya_c, monkeypatch, capali):
    kimlik, izgara = dunya_c
    sayac = _kurulum_hatasi(monkeypatch, hata=MemoryError("bilerek"))
    for n in (1, 2):
        with pytest.raises(MemoryError):
            _iste(kimlik, izgara, capali)
        assert len(sayac) == n
    assert not _kosul_anahtarlari(pozisyon._SERI_HATALARI) and not pozisyon._CAPALI_KOSUL_HATALARI


@pytest.mark.parametrize("capali", [False, True], ids=["capasiz", "capali"])
def test_A5_hata_bellegi_sinirli(dunya_c, monkeypatch, capali):
    kimlik, izgara = dunya_c
    monkeypatch.setattr(pozisyon, "CAPALI_KOSUL_AZAMI_GIRDI" if capali else "SERI_AZAMI_GIRDI", 2)
    _kurulum_hatasi(monkeypatch)
    _, kendi_hata = _ciftler(capali)[0]
    for i in range(4):
        with pytest.raises(ValueError):
            _iste(kimlik, izgara, capali, i)
        assert len(kendi_hata) <= 2


def test_A5_kosu_acilisi_ve_kapanisi_dort_sozlugu_de_bosaltir(dunya_c, monkeypatch):
    kimlik, izgara = dunya_c
    pozisyon.kapi_serisi("H1", _y("H1"), "K1", kume="KESIF", **kimlik)
    _capali(kimlik, izgara[300])
    _kurulum_hatasi(monkeypatch)
    for capali in (False, True):
        with pytest.raises(ValueError):
            _iste(kimlik, izgara, capali, 1)
    sozlukler = (pozisyon._SERI_BELLEGI, pozisyon._SERI_HATALARI, pozisyon._CAPALI_KOSUL_BELLEGI,
                 pozisyon._CAPALI_KOSUL_HATALARI)
    assert all(len(s) >= 1 for s in sozlukler)
    kume_bellegi.temizle()
    assert all(len(s) == 0 for s in sozlukler)


def test_A5_kapi_serisinin_hatasi_paylasilan_hata_belleginde_kalir(dunya_c, monkeypatch):
    """Kapi yolu degismedi: kapi serisinin kurulum hatasi `_SERI_HATALARI`na yazilir, ayri bellege yazilmaz (tek capali
    H1 olay serisi dahil)."""
    kimlik, izgara = dunya_c

    def bozuk(*a, **k):
        raise ValueError("bilerek")

    monkeypatch.setattr(pozisyon, "_kapi_satirlari", bozuk)
    for rol, capa in (("K1", None), ("olay", izgara[300])):
        with pytest.raises(ValueError):
            pozisyon.kapi_serisi("H1", _y("H1"), rol, kume="KESIF", **kimlik, capa=capa)
    assert len([a for a in pozisyon._SERI_HATALARI if a[0] == "kapi_serisi"]) == 2
    assert not pozisyon._CAPALI_KOSUL_HATALARI and not pozisyon._CAPALI_KOSUL_BELLEGI


def test_A5_ayri_bellegi_yalnizca_kosul_serisi_kullanir():
    """`_seri_bellekten(..., capali_kosul=...)` yalnizca `kosul_serisi`nde; iki sozluge `_seri_bellekten` ve temizleyici
    disinda erisen yok."""
    agac = ast.parse((KOK / "data" / "pozisyon.py").read_text(encoding="utf-8"))
    cagiranlar, erisenler = [], set()
    for f in [d for d in ast.walk(agac) if isinstance(d, ast.FunctionDef)]:
        for d in ast.walk(f):
            if isinstance(d, ast.Call) and getattr(d.func, "id", "") == "_seri_bellekten" \
                    and any(k.arg == "capali_kosul" for k in d.keywords):
                cagiranlar.append(f.name)
            if isinstance(d, ast.Name) and d.id in ("_CAPALI_KOSUL_BELLEGI", "_CAPALI_KOSUL_HATALARI"):
                erisenler.add(f.name)
    assert cagiranlar == ["kosul_serisi"]
    assert erisenler == {"_seri_bellekten", "_seri_bellegini_temizle"}
    for yol in [*(KOK / "data").glob("*.py"), *(KOK / "analysis").rglob("*.py")]:
        if yol.name != "pozisyon.py":
            metin = yol.read_text(encoding="utf-8")
            assert "_CAPALI_KOSUL_" not in metin and "capali_kosul" not in metin, yol
