"""Sizinti testcisi, performans 2b-2: tek seri kapi (`pozisyon.kapi_serisi`, `KapiSerisi`, `_seri_bellekten`,
`k2_bitleri`, `k2_aday_pozisyonu`, ince sarmalayici `olay_karari`) ve `kume_bellegi` donem isareti.

Amac kodu KIRMAKTIR: gecen test saldirinin yetmedigini, kalan test (ya da `xfail(strict=True)` isaretli test) kodda
gercek bir acik bulundugunu soyler. xfail testlerinin gerekcesi `S-P2b2-N` numarasiyla baslar; acik kapatilinca test
XPASS(strict) verir ve isaret kaldirilmalidir.

Sentetik dunya `tests/esitlik_yardimcisi.dunya`dir; gercek onbellek (`cache/`) okunmaz, aga cikilmaz. Deger, getiri ve
olay sayisi yazdirilmaz: asagidaki dogrulamalar yalnizca sinif, mesaj, bayrak ve kimlik karsilastirir.
Onay kumesi (C1/C2) testleri `tests/onay_yardimcisi.kosu` ile gecici kayda yonlenmis SAHTE bir onay kosusu acar
(gercek ONAY_KAYDI.md'ye yazilmaz).
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import datetime as dt
import math
import pickle
from types import MappingProxyType

import numpy as np
import pandas as pd
import pytest

import config
from data import _skaler_referans as ref
from data import kume_bellegi, pencere, pozisyon, sinyal, split
from esitlik_yardimcisi import H4, dunya, karar_cagrisi
from kapi_yardimcisi import SENTETIK_DONEMLER, SENTETIK_GRUPLAR, SENTETIK_VERI, veri
from onay_yardimcisi import gecici_kayit as kayit_ayarla, kosu
from tarama_yardimcisi import KOK
from uygunluk_yardimcisi import esikler

BAS, BITIS = "2021-01-01", "2021-08-31 20:00"
U = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
UC_SAAT = dt.timezone(dt.timedelta(hours=3))     # sabit ofset: tz veritabanina bagimli degil


# --- Yardimcilar ---------------------------------------------------------------------------------------------------

def _deger_esit(a, b) -> bool:
    if type(a) is not type(b):
        return False
    if dataclasses.is_dataclass(a):
        return all(_deger_esit(getattr(a, f.name), getattr(b, f.name)) for f in dataclasses.fields(a) if f.compare)
    if isinstance(a, float):
        return (math.isnan(a) and math.isnan(b)) or a == b
    return bool(a == b)


def ayni(a, b) -> bool:
    """Hata: ayni sinif VE ayni mesaj. Onayli pozisyon: butun alanlar (NaN == NaN)."""
    if isinstance(a, BaseException) or isinstance(b, BaseException):
        return type(a) is type(b) and str(a) == str(b)
    return _deger_esit(a, b)


def _ozet(x) -> str:
    """Rapor icin: deger icermez (pozisyon alanlari yazdirilmaz)."""
    if isinstance(x, BaseException):
        return f"{type(x).__name__}: {str(x)[:90]}"
    return type(x).__name__


def _cagir(f, *a, **k):
    try:
        return f(*a, **k)
    except Exception as hata:  # noqa: BLE001 - sinif ve mesaj karsilastirilir
        return hata


def _y(hipotez, i=0):
    return dict(sinyal.izgara(hipotez)[i])


def _izgara(hipotez, kimlik):
    return pozisyon.hipotez_izgarasi_barlari(hipotez, kume="KESIF", **kimlik)


def _capa(t, i):
    """Esitlik betiginin sabit capa kurali: t - (1 + i mod 12) x 4h (kosula bakilmaz)."""
    return t - (1 + i % config.H1_IZLEME_BAR) * H4


def _seri(hipotez, kimlik, rol, y=None, **k):
    return pozisyon.kapi_serisi(hipotez, _y(hipotez) if y is None else y, rol, kume="KESIF", **kimlik, **k)


def _seri_sonucu(seri, t):
    return _cagir(seri.sonuc, t)


def _ornek(izgara, adet=40):
    adim = max(1, len(izgara) // adet)
    secim = list(izgara[::adim]) + list(izgara[-5:]) + list(izgara[:3])
    return sorted(set(secim))


def _ilk_onayli(seri, sira=0):
    bit = seri.onay_bitleri()
    on = np.nonzero(bit)[0]
    assert len(on) > sira, "kurulum: onayli bar bulunamadi"
    return seri.zamanlar()[int(on[sira])]


def _okumalar(seri, t) -> dict:
    """Seri nesnesinin BUTUN okuma yollari (kimlik ve repr veri tasimaz, dahil degil)."""
    return {
        "icerir": lambda: seri.icerir(t), "sonuc": lambda: seri.sonuc(t), "pozisyon": lambda: seri.pozisyon(t),
        "zamanlar": lambda: seri.zamanlar(), "onay_bitleri": lambda: seri.onay_bitleri(),
        "len": lambda: len(seri), "ham_sonuclar": lambda: seri._ham_sonuclar(),
    }


class _SplitVekili:
    """`split` modulu koruma altindadir (adlari disaridan atanamaz). Casuslar kapinin gordugu `split_modulu` adina bu
    vekille kurulur: verilen adlar degistirilir, gerisi gercek moduldendir."""

    def __init__(self, **degisen):
        self.__dict__.update(degisen)

    def __getattr__(self, ad):
        return getattr(split, ad)


def _split_vekili(monkeypatch, **degisen):
    monkeypatch.setattr(pozisyon, "split_modulu", _SplitVekili(**degisen))


def _p0_boz(kimlik, poz):
    """Verilen onayli pozisyonun giris barinin `open`i sifir olan yeni sentetik sembol (diger her sey ayni)."""
    m, f = (x.copy() for x in SENTETIK_VERI[kimlik["sembol"]])
    bas, bitis, _ = pozisyon.donem_kaydi(kimlik["sembol"], 0)
    z = pd.DatetimeIndex(m["open_time"])
    m.loc[z == poz.plan.giris, "open"] = 0.0
    return veri(m.reset_index(drop=True), f.reset_index(drop=True), bas, bitis, ham=True)


@pytest.fixture(scope="module")
def dunya_a():
    """A grubu sentetik dunya (KESIF); modul boyunca bir kez kurulur (veri global kayda yazilir, degismez)."""
    return dunya(611, BAS, BITIS)


@pytest.fixture(scope="module")
def dunya_k2():
    """H2 K2 rolunde onayli barlari olan dunya (mevcut G9 dunyasinin aynisi: tohum 612)."""
    return dunya(612, BAS, BITIS)


@pytest.fixture
def gecici_kayit(tmp_path):
    yol = tmp_path / "onay_gecici.md"
    yol.write_text("bas\n", encoding="utf-8")
    kayit_ayarla(yol)
    return yol


# =====================================================================================================================
# HEDEF 1: kosu kapandiktan (ya da acildiktan) sonra eski seri okuma
# =====================================================================================================================

def test_temizle_sonrasi_eski_seri_hicbir_okuma_yolundan_veri_vermez(dunya_a):
    """Dayanak: ön-kayıt §3 rev.13 ('koşunun açılışı ile kapanışı bellekteki kopyaları geçersiz kılar'), CLAUDE.md §5,
    plan v3 G11. Saldiri: `temizle()` sonrasi AYNI nesneden yedi okuma yolunun hepsi (icerir, sonuc, pozisyon, zamanlar,
    onay_bitleri, len, _ham_sonuclar) `SeriEskidi` vermeli. Sonra yeni seri kurulup tekrar temizlenirse de eski nesne
    reddedilmeli (isaret kalici)."""
    kimlik, _ = dunya_a
    seri = _seri("H2", kimlik, "K2")
    t = _ilk_onayli(seri)
    seri.sonuc(t)                                  # kurulum: temizlenmeden once okunabilir
    kume_bellegi.temizle()
    for ad, okuma in _okumalar(seri, t).items():
        with pytest.raises(pozisyon.SeriEskidi):
            okuma()
    yeni = _seri("H2", kimlik, "K2")
    assert yeni is not seri
    yeni.sonuc(t)
    for ad, okuma in _okumalar(seri, t).items():   # yeni seri kurulmasi eskiyi diriltmez
        with pytest.raises(pozisyon.SeriEskidi):
            okuma()
    kume_bellegi.temizle()
    kume_bellegi.temizle()                         # art arda temizleme isareti geri sarmaz
    for ad, okuma in _okumalar(yeni, t).items():
        with pytest.raises(pozisyon.SeriEskidi):
            okuma()


def test_temizle_sonrasi_seri_onbellegi_eski_nesneyi_dondurmez(dunya_a):
    """Dayanak: ön-kayıt §3 rev.13; CLAUDE.md §5 ('anahtar küme adını içerir, açılış ve kapanış kopyaları geçersiz
    kılar'). Saldiri: isaretin degistigi bir turdan sonra `kapi_serisi` ayni anahtarla eski nesneyi dondurmemeli;
    onbellekte yalnizca guncel isaretli anahtarlar kalmali."""
    kimlik, _ = dunya_a
    seri = _seri("H2", kimlik, "K1")
    assert _seri("H2", kimlik, "K1") is seri       # kurulum: ayni isarette onbellek isabeti
    kume_bellegi.temizle()
    assert len(pozisyon._SERI_BELLEGI) == 0
    yeni = _seri("H2", kimlik, "K1")
    assert yeni is not seri
    assert all(a[-1] == kume_bellegi.donem_isareti() for a in pozisyon._SERI_BELLEGI)


def test_bozuk_temizleyici_donem_isaretini_geri_birakmaz(dunya_a, monkeypatch):
    """Dayanak: plan v3 G11 ('kosu acilisi ve kapanisi seriyi gecersiz kilar'). Saldiri: `temizle()` icinde kayitli bir
    temizleyici HATA verir ve seri onbellegi temizleyicisi calismaz: isaret yine de ilerlemis olmali; eski nesne
    okunamamali, yeni cagri eski nesneyi dondurmemeli."""
    kimlik, _ = dunya_a
    seri = _seri("H2", kimlik, "K1")
    onceki = kume_bellegi.donem_isareti()

    def bozuk():
        raise RuntimeError("bilerek bozuk temizleyici")

    monkeypatch.setattr(kume_bellegi, "_TEMIZLEYICILER", [bozuk, pozisyon._seri_bellegini_temizle])
    with pytest.raises(RuntimeError):
        kume_bellegi.temizle()
    assert kume_bellegi.donem_isareti() == onceki + 1
    with pytest.raises(pozisyon.SeriEskidi):
        seri.zamanlar()
    yeni = _seri("H2", kimlik, "K1")
    assert yeni is not seri
    yeni.zamanlar()


def test_seri_onbellegi_temizleyicisi_tek_kez_kayitlidir(dunya_a):
    """Dayanak: plan v3 G11. Saldiri: `temizleyici_ekle` ayni fonksiyonu iki kez ekleyemez; kapinin temizleyicisi gercekten
    kayitli (kayit dusmusse seri onbellegi `temizle`de dusmez)."""
    sayi = kume_bellegi._TEMIZLEYICILER.count(pozisyon._seri_bellegini_temizle)
    assert sayi == 1
    kume_bellegi.temizleyici_ekle(pozisyon._seri_bellegini_temizle)
    assert kume_bellegi._TEMIZLEYICILER.count(pozisyon._seri_bellegini_temizle) == 1


def test_temizle_isareti_yalnizca_artar_ve_okuma_isareti_degistirmez(dunya_a):
    """Dayanak: plan v3 G11. Saldiri: okumalar (icerir, onay_bitleri...) isareti oynatmaz; `temizle` her cagrida +1."""
    kimlik, _ = dunya_a
    seri = _seri("H2", kimlik, "K1")
    isaret = kume_bellegi.donem_isareti()
    seri.onay_bitleri()
    seri.zamanlar()
    _seri("H2", kimlik, "K1")
    assert kume_bellegi.donem_isareti() == isaret
    for n in range(1, 4):
        kume_bellegi.temizle()
        assert kume_bellegi.donem_isareti() == isaret + n


def test_seri_kurulumu_sirasinda_temizle_cagrilirsa_seri_onbellege_girmez_ve_okunamaz(dunya_a, monkeypatch):
    """Dayanak: plan v3 G11; ön-kayıt §3 rev.13. Saldiri (yaris, deterministik): seri kurulurken (izgara adiminda) bir
    kosu acilisi/kapanisi `temizle()` cagirir. Kurulan nesne eski isaretle dogar: onbellege YAZILMAMALI ve okunamamali."""
    kimlik, _ = dunya_a
    asil = pozisyon.hipotez_izgarasi_barlari

    def girisli(*a, **k):
        kume_bellegi.temizle()
        return asil(*a, **k)

    with monkeypatch.context() as yama:
        yama.setattr(pozisyon, "hipotez_izgarasi_barlari", girisli)
        seri = _seri("H2", kimlik, "K1")
    assert len(pozisyon._SERI_BELLEGI) == 0
    with pytest.raises(pozisyon.SeriEskidi):
        seri.zamanlar()
    yeni = _seri("H2", kimlik, "K1")
    assert yeni is not seri
    yeni.zamanlar()


def test_onbellege_sokulan_eski_nesne_yine_de_okunamaz(dunya_a):
    """Dayanak: plan v3 G11 ('okuma yontemleri isareti her cagrida denetler'). Saldiri: eski bir nesne, guncel isaretli
    anahtar altinda onbellege yerlestirilir; `kapi_serisi` onu dondururse bile okuma `SeriEskidi` vermeli (ya da kapi
    onu hic dondurmemeli)."""
    kimlik, _ = dunya_a
    eski = _seri("H2", kimlik, "K1")
    kume_bellegi.temizle()
    anahtar = ("kapi_serisi", *eski.kimlik, kume_bellegi.donem_isareti())
    pozisyon._SERI_BELLEGI[anahtar] = eski
    donen = _seri("H2", kimlik, "K1")
    if donen is eski:
        with pytest.raises(pozisyon.SeriEskidi):
            donen.zamanlar()
    else:
        donen.zamanlar()


def test_isareti_sahtelenen_eski_seri_satir_ve_bit_veremez(dunya_a):
    """Dayanak: plan v3 G11 ('her satirin imzasi kimlik, donem isareti, zaman ve sonucu baglar'). Saldiri: eski seride
    `__isaret` guncel isarete cevrilir (kararli atlatma; yalnizca gizli belirtecsiz imza uretilemedigini sinar): satir
    okuyan hicbir yol (sonuc, pozisyon, onay_bitleri, _ham_sonuclar) veri vermemeli (imza ValueError)."""
    kimlik, _ = dunya_a
    seri = _seri("H2", kimlik, "K2")
    t = _ilk_onayli(seri)
    kume_bellegi.temizle()
    object.__setattr__(seri, "_KapiSerisi__isaret", kume_bellegi.donem_isareti())
    for ad in ("sonuc", "pozisyon", "onay_bitleri", "ham_sonuclar"):
        with pytest.raises(ValueError):
            _okumalar(seri, t)[ad]()


def test_seri_eskidi_ret_ya_da_veri_hatasi_sinifi_degildir(dunya_a):
    """Dayanak: plan v3 G10 (hata ret koduna ya da 0 bitine donusmez). Saldiri: `SeriEskidi` ve `KontrolAdayiHatasi`
    `OlayOlusmaz` ya da `VeriHatasi` ailesinden olsaydi `except OlayOlusmaz` bir eski okumayi 'olay olusmadi' diye yutardi."""
    for sinif in (pozisyon.SeriEskidi, pozisyon.KontrolAdayiHatasi):
        assert not issubclass(sinif, pencere.OlayOlusmaz)
        assert not issubclass(sinif, pencere.VeriHatasi)
        assert issubclass(sinif, RuntimeError)


def test_olay_karari_eski_seriyle_karar_vermez(dunya_a, monkeypatch):
    """Dayanak: ön-kayıt §3 rev.13; plan v3 G11. Saldiri: `kapi_serisi` (yarisla) eski bir nesne dondurur. `olay_karari`
    o nesnenin satirindan karar vermemeli: ya `SeriEskidi` yukselir ya da karar tazeden kurulur (skalerle ayni)."""
    kimlik, _ = dunya_a
    eski = _seri("H2", kimlik, "K1")
    t = _ilk_onayli(eski)
    beklenen = karar_cagrisi(ref, "H2", kimlik, t, rol="K1")
    kume_bellegi.temizle()
    monkeypatch.setattr(pozisyon, "kapi_serisi", lambda *a, **k: eski)
    sonuc = karar_cagrisi(pozisyon, "H2", kimlik, t, rol="K1")
    assert isinstance(sonuc, pozisyon.SeriEskidi) or ayni(sonuc, beklenen), _ozet(sonuc)


# =====================================================================================================================
# HEDEF 2: imzali seriyi taklit etme / degistirme
# =====================================================================================================================

def test_seri_gizli_belirtec_olmadan_kurulamaz_ve_bos_nesne_veri_vermez(dunya_a):
    """Dayanak: plan v3 G11 ('yalnizca kapi_serisi kurar'). Saldiri: yanlis/bos/taklit belirtec, alt sinif, ve
    `object.__new__` ile ilklendirilmemis nesne. Hicbiri veri vermemeli."""
    kimlik, _ = dunya_a
    gercek = _seri("H2", kimlik, "K1")
    z = gercek.zamanlar()
    for belirtec in (None, object(), 0, "gizli", pozisyon._ONAY_GIZLI):
        with pytest.raises(TypeError):
            pozisyon.KapiSerisi(belirtec, None, gercek.kimlik, 0, z, [None] * len(z))

    class Sahte(pozisyon.KapiSerisi):
        pass

    with pytest.raises(TypeError):
        Sahte(object(), None, gercek.kimlik, 0, z, [None] * len(z))
    bos = object.__new__(pozisyon.KapiSerisi)
    for ad, okuma in _okumalar(bos, z[0]).items():
        with pytest.raises(Exception) as hata:
            okuma()
        assert not isinstance(hata.value, pozisyon.SeriEskidi), ad      # ilklendirilmemis: eskime degil, kurulus hatasi


def test_seri_nitelik_atama_silme_ve_dict_yollari_kapali(dunya_a):
    """Dayanak: plan v3 G11 ('nitelik atamasi ve silme reddedilir'). Saldiri: yeni nitelik, var olan alan, mangled ad,
    `__class__` degistirme, `__dict__`/`vars` ile ic duruma erisim."""
    kimlik, _ = dunya_a
    seri = _seri("H2", kimlik, "K1")
    for ad in ("yeni_alan", "kimlik", "_KapiSerisi__isaret", "_KapiSerisi__baglam", "_KapiSerisi__imzalar", "__class__"):
        with pytest.raises(AttributeError):
            setattr(seri, ad, 1)
    for ad in ("kimlik", "_KapiSerisi__zamanlar", "_KapiSerisi__imzalar"):
        with pytest.raises(AttributeError):
            delattr(seri, ad)
    with pytest.raises(AttributeError):
        seri.__dict__
    with pytest.raises(TypeError):
        vars(seri)


@pytest.mark.parametrize("protokol", [0, 1, 2, 3, 4, 5])
def test_seri_pickle_her_protokolde_reddedilir_ve_kopya_ayni_nesnedir(dunya_a, protokol):
    """Dayanak: plan v3 G11 ('kopyalanamaz ya da serilestirilemez; alt surec kendi serisini kurar'). Saldiri: bir surecte
    serilestirilen imzali nesne baska yerde yeniden kurulamaz; `copy`/`deepcopy` yeni (kurcalanabilir) nesne uretmez."""
    kimlik, _ = dunya_a
    seri = _seri("H2", kimlik, "K1")
    with pytest.raises(TypeError):
        pickle.dumps(seri, protocol=protokol)
    assert copy.copy(seri) is seri
    assert copy.deepcopy(seri) is seri


def test_seri_satirlari_degistirilirse_okuma_reddedilir(dunya_a):
    """Dayanak: plan v3 G11 ('her satirin imzasi'). Saldiri (kararli atlatma, imza gizlisi OLMADAN): (a) iki satirin
    sonuclari yer degistirir, (b) zaman dizisi bir bar kaydirilir, (c) imza tuple'i silinip baska bir uzunluk konur.
    Satir okuyan yollar ValueError vermeli."""
    kimlik, _ = dunya_a
    for deney in ("sonuclar_takas", "zamanlar_kaydir", "imzalar_kisalt"):
        kume_bellegi.temizle()
        seri = _seri("H2", kimlik, "K1")
        t = seri.zamanlar()[120]
        if deney == "sonuclar_takas":
            s = list(seri._KapiSerisi__sonuclar)
            s[120], s[121] = s[121], s[120]
            object.__setattr__(seri, "_KapiSerisi__sonuclar", tuple(s))
        elif deney == "zamanlar_kaydir":
            z = list(seri._KapiSerisi__zamanlar)
            z[120] = z[120] + 1                       # sira haritasi eski kalir: sorulan t yine 120. satira gider
            object.__setattr__(seri, "_KapiSerisi__zamanlar", tuple(z))
        else:
            object.__setattr__(seri, "_KapiSerisi__imzalar", seri._KapiSerisi__imzalar[:-1])
        with pytest.raises((ValueError, IndexError)):
            seri.onay_bitleri()
        if deney != "imzalar_kisalt":
            with pytest.raises(ValueError):
                seri.sonuc(t)


def test_satirdan_donen_pozisyon_degistirilirse_seri_ve_fiyat_yollari_reddeder(dunya_a):
    """Dayanak: ön-kayıt §4 'tek karar noktası' ve plan v3 G11 (onayli pozisyon imzali). Saldiri: serinin dondurdugu
    `OnaylanmisPozisyon` uzerinde `object.__setattr__` ile p1 degistirilir; ayrica `dataclasses.replace` ile eski imzayla
    sahte pozisyon kurulur. `pozisyon_fiyatlari` ve serinin sonraki okumasi ValueError vermeli."""
    kimlik, _ = dunya_a
    seri = _seri("H2", kimlik, "K1")
    t = _ilk_onayli(seri)
    poz = seri.sonuc(t)
    sahte = dataclasses.replace(poz, p1=poz.p1 * 0.5)          # eski `_imza` tasinir
    with pytest.raises(ValueError):
        pozisyon.pozisyon_fiyatlari(sahte)
    object.__setattr__(poz, "p1", poz.p1 * 0.5)
    with pytest.raises(ValueError):
        pozisyon.pozisyon_fiyatlari(poz)
    with pytest.raises(ValueError):
        seri.sonuc(t)
    with pytest.raises(ValueError):
        seri.onay_bitleri()


@pytest.mark.xfail(strict=True, reason=(
    "S-P2b2-1: KapiSerisi satir imzasi (kimlik, isaret, satirin KENDI zamani, sonuc) baglar ama `sonuc(t)`/`pozisyon(t)` "
    "sorulan t ile satirin zamaninin esitligini dogrulamaz. `__sira` haritasi degistirilirse (kararli atlatma: "
    "object.__setattr__) t1 sorusuna t2 satirinin onayli pozisyonu doner, hata yok. Dusuk onem: ozel alana yazma gerektirir "
    "(tarama `_KapiSerisi__` adini yasaklar); yine de duzeltme tek satir (`self.__zamanlar[i] == zaman.value`)."))
def test_seri_sira_haritasi_kurcalanirsa_sorulan_zamanin_satiri_baska_zamaninkiyle_degismez(dunya_a):
    """Dayanak: plan v3 G11 (satir imzasi zamani baglar). Saldiri: `__sira` icinde t1 -> baska satirin indeksi. Beklenen:
    ValueError (ya da en azindan donen pozisyonun sinyal zamani t1). Gozlenen: t2 satiri sessizce doner."""
    kimlik, _ = dunya_a
    seri = _seri("H2", kimlik, "K1")
    bit = seri.onay_bitleri()
    on = np.nonzero(bit)[0]
    assert len(on) >= 2, "kurulum"
    i1, i2 = int(on[0]), int(on[len(on) // 2])
    z = seri.zamanlar()
    t1 = z[i1]
    sira = dict(seri._KapiSerisi__sira)
    sira[int(t1.value)] = i2
    object.__setattr__(seri, "_KapiSerisi__sira", MappingProxyType(sira))
    try:
        sonuc = seri.sonuc(t1)
    except Exception:  # noqa: BLE001 - reddedildi: savunma saglam
        return
    assert sonuc.plan.sinyal_zamani == t1


@pytest.mark.xfail(strict=True, reason=(
    "S-P2b2-3: `_seri_bellekten` onbellek isabetinde donen serinin `kimlik`ini istenen anahtarla karsilastirmaz. K1 serisi "
    "K2 anahtari altina yazilirsa `kapi_serisi(..., 'K2')` K1 serisini doner (k2_bitleri/k2_aday_pozisyonu yanlis rolun "
    "bitlerini kullanir). Dusuk onem: ozel sozluge (`_SERI_BELLEGI`) yazma gerektirir; tarama bu adi yasaklar."))
def test_onbellek_isabetinde_donen_serinin_kimligi_istenen_kimlikle_ayni_olmali(dunya_a):
    """Dayanak: plan v3 G11 ('onbellek anahtari rol dahil kimligi tasir'). Saldiri: K1 serisi K2 anahtari altina konur."""
    kimlik, _ = dunya_a
    k1 = _seri("H2", kimlik, "K1")
    k1_kimlik = k1.kimlik
    k2_anahtar = ("kapi_serisi", *k1_kimlik[:5], "K2", *k1_kimlik[6:], kume_bellegi.donem_isareti())
    assert k2_anahtar not in pozisyon._SERI_BELLEGI, "kurulum"
    pozisyon._SERI_BELLEGI[k2_anahtar] = k1
    donen = _seri("H2", kimlik, "K2")
    assert donen.kimlik[5] == "K2"


# =====================================================================================================================
# HEDEF 3: onbellek anahtari / kume / koşu baglami
# =====================================================================================================================

@pytest.mark.parametrize("kume", ["kesif", "KESIF ", "C3", "", None, 1, ("KESIF",)])
def test_bilinmeyen_kume_adi_seri_kurmaz_ve_onbellege_girmez(dunya_a, kume):
    """Dayanak: ön-kayıt §3 ('küme adı sabit'); `pozisyon.kume_sinirlari`. Saldiri: yazim varyasyonlari ve tur karisikligi."""
    kimlik, _ = dunya_a
    onceki = len(pozisyon._SERI_BELLEGI)
    with pytest.raises((TypeError, ValueError)):
        pozisyon.kapi_serisi("H2", _y("H2"), "K1", kume=kume, **kimlik)
    assert len(pozisyon._SERI_BELLEGI) == onceki


def test_str_alt_sinifi_kume_ve_rol_adi_seri_kurmaz(dunya_a):
    """Dayanak: `pozisyon.kume_sinirlari`/`_rol_dogrula` ('alt sinif `__eq__` ile yalan soyleyebilir'). Saldiri: `str`
    alt sinifi, her zaman `==` True doner."""
    kimlik, _ = dunya_a

    class Yalanci(str):
        def __eq__(self, diger):
            return True

        __hash__ = str.__hash__

    onceki = len(pozisyon._SERI_BELLEGI)
    with pytest.raises((TypeError, ValueError)):
        pozisyon.kapi_serisi("H2", _y("H2"), "K1", kume=Yalanci("KESIF"), **kimlik)
    with pytest.raises((TypeError, ValueError)):
        pozisyon.kapi_serisi("H2", _y("H2"), Yalanci("K1"), kume="KESIF", **kimlik)
    assert len(pozisyon._SERI_BELLEGI) == onceki


@pytest.mark.parametrize("kume", ["C1", "C2"])
def test_kesif_serisi_onbellekteyken_onay_kumesi_serisi_kosusuz_kurulamaz(dunya_a, kume):
    """Dayanak: CLAUDE.md §3.3, ön-kayıt §3 ('onay kümesi verisi yalnızca açık onay koşusunda okunur'). Saldiri: KESIF
    icin sicak seri varken ayni sembol/hipotez icin C1/C2 istenir (C2 A grubunu da kapsar). Acik kosu olmadan `OnayGerekli`;
    onbellege onay kumesi anahtari girmez."""
    kimlik, _ = dunya_a
    kesif = _seri("H2", kimlik, "K1")
    onceki = dict(pozisyon._SERI_BELLEGI)
    with pytest.raises(split.OnayGerekli):
        pozisyon.kapi_serisi("H2", _y("H2"), "K1", kume=kume, **kimlik)
    with pytest.raises(split.OnayGerekli):
        pozisyon.k2_bitleri("H2", _y("H2"), kume=kume, **kimlik, zamanlar=kesif.zamanlar()[:5])
    with pytest.raises(split.OnayGerekli):
        pozisyon.k2_aday_pozisyonu("H2", _y("H2"), kume=kume, **kimlik, t=kesif.zamanlar()[100])
    assert dict(pozisyon._SERI_BELLEGI) == onceki
    assert all(a[1] == "KESIF" for a in pozisyon._SERI_BELLEGI)


def test_donem_anahtari_ayni_sembolun_baska_donemi_icin_seri_dondurmez(dunya_a, monkeypatch):
    """Dayanak: ön-kayıt §2 'Listeleme dönemi' ve plan v3 G11 (anahtar donem numarasini tasir). Saldiri: ayni sembolun
    ikinci, DAR bir donemi kaydedilir; donem 1 serisi donem 0 serisinin ayni nesnesi olamaz, donem 1 sinirlari disinda bar
    icermemeli."""
    kimlik, _ = dunya_a
    sembol = kimlik["sembol"]
    bas0, bitis0, _ = pozisyon.donem_kaydi(sembol, 0)
    bas1, bitis1 = U("2021-03-01"), U("2021-06-30 20:00")
    monkeypatch.setitem(SENTETIK_DONEMLER, (sembol, 1), (bas1, bitis1, False))
    s0 = _seri("H2", kimlik, "K1")
    s1 = pozisyon.kapi_serisi("H2", _y("H2"), "K1", kume="KESIF", sembol=sembol, donem_no=1)
    assert s1 is not s0
    assert s0.kimlik[2] == 0 and s1.kimlik[2] == 1
    z1 = s1.zamanlar()
    assert len(z1) < len(s0.zamanlar())
    assert z1.min() >= bas1 and z1.max() <= bitis1
    dis = s0.zamanlar()[5]
    assert dis < bas1 and not s1.icerir(dis)
    assert _seri("H2", kimlik, "K1") is s0                    # donem 1 sorgusu donem 0 girdisini bozmaz
    assert bas0 <= z1.min()


def test_ufuk_anahtari_gecersiz_ufuklar_seri_kurmaz_ve_birincil_ufuk_tek_seridir(dunya_a):
    """Dayanak: ön-kayıt §4 'Ufuk değerlerinin bağlanması' (rev.10); plan v3 G11. Saldiri: H2 icin gecersiz ufuklar
    (bool, 1, 0, negatif, ara degerler, str); `ufuk=18` (birincil) ile `ufuk=None` AYNI seridir (cift kurulum yok)."""
    kimlik, _ = dunya_a
    ana = _seri("H2", kimlik, "K1")
    assert _seri("H2", kimlik, "K1", ufuk=18) is ana
    onceki = dict(pozisyon._SERI_BELLEGI)
    for ufuk in (True, 1, 0, -6, 7, 19, 43, "18", 18.5):
        with pytest.raises(Exception) as hata:
            _seri("H2", kimlik, "K1", ufuk=ufuk)
        assert not isinstance(hata.value, pencere.OlayOlusmaz), ufuk       # programlama hatasi, ret degil
    assert dict(pozisyon._SERI_BELLEGI) == onceki


def test_capa_yalnizca_H1_olay_rolunde_verilebilir_ve_reddedilen_cagri_onbellege_girmez(dunya_a):
    """Dayanak: ön-kayıt §5 H1 ve §6 rev.11 ('kontrolde pump bari aranmaz'); `_capa_dogrula`. Saldiri: capa K1/K2'ye, H2'ye,
    H3'e verilir; H1 olay rolunde capa verilmez."""
    kimlik, _ = dunya_a
    capa = U("2021-03-01")
    onceki = dict(pozisyon._SERI_BELLEGI)
    for hipotez, rol, c in (("H1", "K1", capa), ("H1", "K2", capa), ("H2", "olay", capa), ("H2", "K1", capa),
                            ("H3", "K1", capa), ("H1", "olay", None)):
        with pytest.raises(TypeError):
            _seri(hipotez, kimlik, rol, capa=c)
    assert dict(pozisyon._SERI_BELLEGI) == onceki


def test_capa_dizisi_saldirilari_seriyi_kurmaz_onbellege_girmez_ve_gelecek_capa_reddedilir(dunya_a):
    """Dayanak: ön-kayıt §5 H1 madde 2-3 (tepe penceresi pump'tan teyide, en fazla 12 bar), CLAUDE.md §3.6 (geleceğe
    bakış yok). Saldiri: capa dizisi (a) tz'siz, (b) NaT iceren, (c) kisa, (d) teyitten SONRA (gelecek), (e) teyitle
    ayni bar, (f) 12 bardan uzak. Hicbiri seri vermemeli ve onbellegi kirletmemeli."""
    kimlik, _ = dunya_a
    izgara = _izgara("H1", kimlik)
    temel = izgara - H4
    nat = list(temel)
    nat[7] = pd.NaT
    vakalar = {
        "tz_siz": (pd.DatetimeIndex(temel.tz_localize(None)), TypeError),
        "nat": (pd.DatetimeIndex(nat), TypeError),
        "kisa": (temel[:-1], ValueError),
        "gelecek": (izgara + H4, sinyal.TepePenceresiKurulamaz),
        "ayni_bar": (izgara, sinyal.TepePenceresiKurulamaz),
        "uzak": (izgara - (config.H1_IZLEME_BAR + 8) * H4, sinyal.TepePenceresiKurulamaz),
    }
    onceki = dict(pozisyon._SERI_BELLEGI)
    for ad, (capa, hata) in vakalar.items():
        with pytest.raises(hata):
            _seri("H1", kimlik, "olay", capa=capa)
    assert dict(pozisyon._SERI_BELLEGI) == onceki


def test_veri_hatasiyla_biten_seri_kurulumu_onbellege_girmez_ve_her_cagrida_yeniden_olusur(dunya_a):
    """Dayanak: plan v3 G10 ('veri hatasi seriyi durdurur, ret koduna donusmez') ve `_seri_bellekten` ('hata veren
    kurulum bellege yazilmaz'). Saldiri: bir onayli barin P0'i sifir. Iki ardisik cagri da `VeriHatasi` vermeli; kismi
    seri onbellege girmemeli."""
    kimlik, _ = dunya_a
    ana = _seri("H2", kimlik, "K1")
    t = _ilk_onayli(ana)
    bozuk = _p0_boz(kimlik, ana.sonuc(t))
    kume_bellegi.temizle()
    for _ in range(2):
        with pytest.raises(pencere.VeriHatasi):
            _seri("H2", bozuk, "K1")
    assert not any(a[2] == bozuk["sembol"] for a in pozisyon._SERI_BELLEGI)


def test_seri_onbellegi_azami_girdiyi_asmaz_ve_en_eskiyi_dusurur(dunya_a, monkeypatch):
    """Dayanak: CLAUDE.md §5 / RESULTS §14.40 (bellek siniri); `_seri_bellekten` LRU. Saldiri: sinir 2'ye indirilir, uc ayri
    seri kurulur; onbellek 2'yi asmamali, en eski seri onbellekten dusmus (yeniden kurulunca yeni nesne)."""
    kimlik, _ = dunya_a
    monkeypatch.setattr(pozisyon, "SERI_AZAMI_GIRDI", 2)
    a = _seri("H2", kimlik, "K1")
    _seri("H2", kimlik, "K2")
    _seri("H3", kimlik, "K1")
    assert len(pozisyon._SERI_BELLEGI) == 2
    assert _seri("H2", kimlik, "K1") is not a
    assert len(pozisyon._SERI_BELLEGI) == 2


@pytest.mark.parametrize("denetim", ["onay_baglami_dogrula", "kesif_baglami_dogrula", "onay_erisimi_denetle",
                                     "grup_dogrula"])
def test_seri_okuma_yontemlerinin_her_biri_dort_denetimin_her_birini_calistirir(dunya_a, monkeypatch, denetim):
    """Dayanak: ön-kayıt §3 rev.13 ('erişim denetimi kopyanın her okunuşunda yeniden uygulanır'), CLAUDE.md §5. Saldiri:
    seri sicakken dort denetimden biri hata vermeye baslar (izin geri alinmis gibi); yedi okuma yolunun HEPSI o hatayi
    vermeli; denetimi atlayan hicbir okuma yolu olmamali. Kapi seviyesindeki onbellek isabeti de (erisim denetimi disindaki
    uc denetimle) hata vermeli."""
    kimlik, _ = dunya_a
    seri = _seri("H2", kimlik, "K2")
    t = _ilk_onayli(seri)

    class Yasak(PermissionError):
        pass

    def yasak(*a, **k):
        raise Yasak(denetim)

    if denetim == "grup_dogrula":
        monkeypatch.setattr(pozisyon, "grup_dogrula", yasak)
    else:
        _split_vekili(monkeypatch, **{denetim: yasak})
    for ad, okuma in _okumalar(seri, t).items():
        with pytest.raises(Yasak):
            okuma()
    if denetim != "onay_erisimi_denetle":
        with pytest.raises(Yasak):
            _seri("H2", kimlik, "K2")
        with pytest.raises(Yasak):
            pozisyon.k2_aday_pozisyonu("H2", _y("H2"), kume="KESIF", **kimlik, t=t)


def test_olay_karari_ve_izgara_da_kesif_baglamini_sicak_onbellekte_denetler(dunya_a, monkeypatch):
    """Dayanak: RESULTS §14.42 ('KESIF karar noktasi yalnizca kesif kosusu icinde'); ön-kayıt §3 rev.13. Saldiri: sicak
    onbellek varken kesif baglami kapanir; `olay_karari` (sarmalayici) ve `hipotez_izgarasi_barlari` hata vermeli,
    onbellekten karar dondurmemeli."""
    kimlik, _ = dunya_a
    seri = _seri("H2", kimlik, "K1")
    t = _ilk_onayli(seri)

    class Yasak(PermissionError):
        pass

    def yasak(kume):
        raise Yasak("baglam yok")

    _split_vekili(monkeypatch, kesif_baglami_dogrula=yasak)
    assert isinstance(karar_cagrisi(pozisyon, "H2", kimlik, t, rol="K1"), Yasak)
    with pytest.raises(Yasak):
        _izgara("H2", kimlik)


def test_onay_kosusu_acilis_ve_kapanisi_seriyi_eskitir_ve_C1_serisi_kosu_disinda_kurulamaz(gecici_kayit, dunya_a,
                                                                                         monkeypatch):
    """Dayanak: CLAUDE.md §3.3 ('onay kümesi verisi yalnızca açık bir onay koşusu içinde okunabilir'), ön-kayıt §3 rev.13
    ('koşunun açılışı ile kapanışı kopyaları geçersiz kılar'). SAHTE koşu (gecici kayit). Saldiri: (1) KESIF serisi koşu
    ACILMADAN once kurulur: kosu icinde okunamaz (acilis eskitir); (2) acik C1 kosusu varken KESIF, baska hipotez, baska
    kume, baska yapilandirma serisi kurulamaz; (3) A grubu coin C1'de kurulamaz; (4) C1 serisi kosu KAPANINCA okunamaz,
    kosu disinda yeniden kurulamaz ve onbellekte onay kumesi anahtari kalmaz."""
    kesif_kimlik, _ = dunya_a
    b_kimlik, _ = dunya(621, BAS, BITIS)
    monkeypatch.setitem(SENTETIK_GRUPLAR, b_kimlik["sembol"], "B")
    y = _y("H2")
    kesif_seri = _seri("H2", kesif_kimlik, "K1")
    t_kesif = kesif_seri.zamanlar()[100]
    with kosu("H2", "C1"):
        with pytest.raises(pozisyon.SeriEskidi):
            kesif_seri.icerir(t_kesif)                       # acilis KESIF serisini eskitti
        with pytest.raises(split.OnayUyusmazligi):
            _seri("H2", kesif_kimlik, "K1")                   # acik kosu varken KESIF yok
        with pytest.raises(split.OnayUyusmazligi):
            pozisyon.kapi_serisi("H3", _y("H3"), "K1", kume="C1", **b_kimlik)      # baska hipotez
        with pytest.raises(split.OnayUyusmazligi):
            pozisyon.kapi_serisi("H2", y, "K1", kume="C2", **b_kimlik)             # baska kume
        with pytest.raises(split.OnayUyusmazligi):
            pozisyon.kapi_serisi("H2", _y("H2", 1), "K1", kume="C1", **b_kimlik)   # kilitli olmayan yapilandirma
        with pytest.raises(ValueError):
            pozisyon.kapi_serisi("H2", y, "K1", kume="C1", **kesif_kimlik)         # A grubu C1'de yok
        bitler_a = pozisyon.k2_bitleri("H2", y, kume="C1", **kesif_kimlik,
                                       zamanlar=pd.date_range(U("2021-05-01"), periods=20, freq=H4))
        assert not bitler_a.any()                                                  # A grubu coin: hic 1 yok
        c1 = pozisyon.kapi_serisi("H2", y, "K1", kume="C1", **b_kimlik)
        assert c1.kimlik[0] == "C1"
        t = c1.zamanlar()[100]
        assert c1.icerir(t)
        assert pozisyon.kapi_serisi("H2", y, "K1", kume="C1", **b_kimlik) is c1
        assert all(a[1] == "C1" for a in pozisyon._SERI_BELLEGI)
    for ad, okuma in _okumalar(c1, t).items():
        with pytest.raises(pozisyon.SeriEskidi):
            okuma()                                          # kapanis C1 serisini eskitti
    with pytest.raises(split.OnayGerekli):
        pozisyon.kapi_serisi("H2", y, "K1", kume="C1", **b_kimlik)
    assert not any(a[1] in config.ONAY_KUMELERI for a in pozisyon._SERI_BELLEGI)


def test_C2_kosusunda_k2_bitleri_ve_aday_kume_kosuyla_sinirlidir(gecici_kayit):
    """Dayanak: CLAUDE.md §3.3, ön-kayıt §3 (C2 = A + B, 2025-09-01 sonrasi). SAHTE koşu. Saldiri: C2 kosusunda uretilen K2
    bitleri ve aday pozisyonu (a) yalnizca C2 icin gecerlidir (KESIF/C1 istegi `OnayUyusmazligi`), (b) kosu kapaninca
    `k2_bitleri`/`k2_aday_pozisyonu` `OnayGerekli` verir, seri `SeriEskidi` verir."""
    kimlik, _ = dunya(623, "2025-09-01", "2026-04-30 20:00")
    y = _y("H2")
    with kosu("H2", "C2"):
        seri = pozisyon.kapi_serisi("H2", y, "K2", kume="C2", **kimlik)
        bit = seri.onay_bitleri()
        assert bit.any(), "kurulum"
        z = seri.zamanlar()
        bitler = pozisyon.k2_bitleri("H2", y, kume="C2", **kimlik, zamanlar=z)
        assert bitler.tolist() == bit.tolist()
        t = z[int(np.nonzero(bit)[0][0])]
        poz = pozisyon.k2_aday_pozisyonu("H2", y, kume="C2", **kimlik, t=t)
        assert poz.kume == "C2" and poz.rol == "K2" and poz.sembol == kimlik["sembol"]
        for baska in ("KESIF", "C1"):
            with pytest.raises(split.OnayUyusmazligi):
                pozisyon.k2_bitleri("H2", y, kume=baska, **kimlik, zamanlar=z[:5])
            with pytest.raises(split.OnayUyusmazligi):
                pozisyon.k2_aday_pozisyonu("H2", y, kume=baska, **kimlik, t=t)
    with pytest.raises(pozisyon.SeriEskidi):
        seri.onay_bitleri()
    with pytest.raises(split.OnayGerekli):
        pozisyon.k2_bitleri("H2", y, kume="C2", **kimlik, zamanlar=z[:5])
    with pytest.raises(split.OnayGerekli):
        pozisyon.k2_aday_pozisyonu("H2", y, kume="C2", **kimlik, t=t)
    assert not any(a[1] in config.ONAY_KUMELERI for a in pozisyon._SERI_BELLEGI)


# =====================================================================================================================
# HEDEF 4: K2 bit dizisi ve aday pozisyonunda B grubu
# =====================================================================================================================

def _b_kopyasi(monkeypatch, tohum=612):
    """G9 dunyasinin birebir kopyasi (ayni veri, yeni sembol) B grubuna koyulur (KESIF'te yasak)."""
    kimlik, _ = dunya(tohum, BAS, BITIS)
    monkeypatch.setitem(SENTETIK_GRUPLAR, kimlik["sembol"], "B")
    return kimlik


@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_k2_bitleri_B_grubu_coinine_hic_1_uretmez_ve_hicbir_yolda_veri_okunmaz(dunya_k2, monkeypatch, hipotez):
    """Dayanak: ön-kayıt §3 ('keşif yalnızca A grubu'), CLAUDE.md §3.3. Saldiri: aynisi bir A coininde onayli barlari olan
    veri B grubuna konur. `k2_bitleri` her hipotezde SIFIR 1 dondurmeli (veri okumadan); kapi, aday, izgara ve
    `olay_karari` ValueError vermeli (grup denetimi). Kontrol: ayni veri A grubunda en az bir onayli bit uretir (H2)."""
    ctrl, _ = dunya_k2
    b = _b_kopyasi(monkeypatch)
    bas, bitis, _ = pozisyon.donem_kaydi(b["sembol"], 0)
    zamanlar = pd.date_range(bas, bitis, freq=H4)
    if hipotez == "H2":
        assert _seri("H2", ctrl, "K2").onay_bitleri().any(), "kurulum: kontrol dunyasinda onayli K2 bari olmali"
    cagri = []

    def yasak(*a, **k):
        cagri.append(1)
        raise AssertionError("B grubu coin icin KESIF verisi okunmamali")

    monkeypatch.setattr(pozisyon, "_veri_yukle", yasak)
    kume_bellegi.temizle()
    bitler = pozisyon.k2_bitleri(hipotez, _y(hipotez), kume="KESIF", **b, zamanlar=zamanlar)
    assert bitler.dtype == bool and len(bitler) == len(zamanlar) and not bitler.any()
    for rol in ("K1", "K2"):
        with pytest.raises(ValueError):
            pozisyon.kapi_serisi(hipotez, _y(hipotez), rol, kume="KESIF", **b)
    with pytest.raises(ValueError):
        pozisyon.k2_aday_pozisyonu(hipotez, _y(hipotez), kume="KESIF", **b, t=zamanlar[500])
    with pytest.raises(ValueError):
        pozisyon.hipotez_izgarasi_barlari(hipotez, kume="KESIF", **b)
    karar = karar_cagrisi(pozisyon, hipotez, b, zamanlar[500], rol="K2")
    assert isinstance(karar, ValueError) and not isinstance(karar, pencere.OlayOlusmaz), _ozet(karar)
    assert not cagri


def test_onbellekteki_A_serisi_coin_B_grubuna_gecince_okunamaz_ve_bit_vermez(dunya_k2, monkeypatch):
    """Dayanak: ön-kayıt §3, plan v3 G11 ('grup denetimi her okumada'). Saldiri: A grubunda sicak seri varken sembolun
    bolme grubu B'ye cevrilir (tablo degisti/yanlis okundu). Eski seri nesnesinin her okumasi, `kapi_serisi`,
    `k2_aday_pozisyonu` ValueError; `k2_bitleri` onbellekteki 1'leri DONDURMEMELI (sifir)."""
    kimlik, _ = dunya_k2
    seri = _seri("H2", kimlik, "K2")
    t = _ilk_onayli(seri)
    zamanlar = seri.zamanlar()
    assert seri.onay_bitleri().any()
    monkeypatch.setitem(SENTETIK_GRUPLAR, kimlik["sembol"], "B")
    for ad, okuma in _okumalar(seri, t).items():
        with pytest.raises(ValueError):
            okuma()
    with pytest.raises(ValueError):
        _seri("H2", kimlik, "K2")
    with pytest.raises(ValueError):
        pozisyon.k2_aday_pozisyonu("H2", _y("H2"), kume="KESIF", **kimlik, t=t)
    bitler = pozisyon.k2_bitleri("H2", _y("H2"), kume="KESIF", **kimlik, zamanlar=zamanlar)
    assert not bitler.any()


def test_grubu_olmayan_sembol_k2_bitine_1_katmaz(monkeypatch, dunya_k2):
    """Dayanak: ön-kayıt §3 (coin A ya da B'dir). Saldiri: evren tablosunda olan ama bolme tablosunda grubu olmayan
    sembol. `k2_bitleri` 1 uretmemeli; kapi ValueError vermeli."""
    b = _b_kopyasi(monkeypatch)
    monkeypatch.delitem(SENTETIK_GRUPLAR, b["sembol"])
    bas, bitis, _ = pozisyon.donem_kaydi(b["sembol"], 0)
    zamanlar = pd.date_range(bas, bitis, freq=H4)
    bitler = pozisyon.k2_bitleri("H2", _y("H2"), kume="KESIF", **b, zamanlar=zamanlar)
    assert not bitler.any()
    with pytest.raises(ValueError):
        pozisyon.kapi_serisi("H2", _y("H2"), "K2", kume="KESIF", **b)


def test_k2_bitleri_zaman_girdisi_saldirilari_dogru_hizalanir(dunya_k2):
    """Dayanak: plan v3 G9/G20 ('izgarada olmayan zaman 0', bit dizisi istenen zamana hizali). Saldiri: tekrarli,
    siralanmamis, izgara disi (+30 sn), farkli saat dilimli ayni an, NaT, tz'siz ve bos zaman listesi. Bit, sorulan
    zamanin satirina ait olmali, siraya degil."""
    kimlik, _ = dunya_k2
    y = _y("H2")
    seri = _seri("H2", kimlik, "K2")
    bit = seri.onay_bitleri()
    z = seri.zamanlar()
    on, red = np.nonzero(bit)[0], np.nonzero(~bit)[0]
    assert len(on) and len(red), "kurulum"
    t_on, t_red = z[int(on[len(on) // 2])], z[int(red[len(red) // 2])]
    istek = pd.DatetimeIndex([t_red, t_on, t_on, t_on + pd.Timedelta(seconds=30), t_on - H4 / 2])
    bitler = pozisyon.k2_bitleri("H2", y, kume="KESIF", **kimlik, zamanlar=istek)
    assert bitler.tolist() == [False, True, True, False, False]
    assert pozisyon.k2_bitleri("H2", y, kume="KESIF", **kimlik, zamanlar=z).tolist() == bit.tolist()
    ters = z[::-1]
    assert pozisyon.k2_bitleri("H2", y, kume="KESIF", **kimlik, zamanlar=ters).tolist() == bit[::-1].tolist()
    ofsetli = pd.DatetimeIndex([t_on]).tz_convert(UC_SAAT)
    assert pozisyon.k2_bitleri("H2", y, kume="KESIF", **kimlik, zamanlar=ofsetli).tolist() == [True]
    nat = pd.DatetimeIndex([pd.NaT, t_on])
    assert pozisyon.k2_bitleri("H2", y, kume="KESIF", **kimlik, zamanlar=nat).tolist() == [False, True]
    with pytest.raises(TypeError):
        pozisyon.k2_bitleri("H2", y, kume="KESIF", **kimlik, zamanlar=pd.DatetimeIndex([t_on]).tz_localize(None))


def test_k2_bitleri_bos_zaman_listesi_bos_bit_dizisi_doner(dunya_k2):
    """Dayanak: plan v3 G9. Saldiri: bos zaman listesi (tz'siz bos DatetimeIndex, tz'li seriye karsi `get_indexer`). Beklenen:
    bos bool dizisi; hata ya da yanlis uzunluk donmemeli. (Bu test calistirilmadan yazildi: pandas bos tz'siz hedefi tz'li
    indekse karsi kabul etmezse TypeError cikar ve bu gercek bir kucuk kusurdur.)"""
    kimlik, _ = dunya_k2
    bitler = pozisyon.k2_bitleri("H2", _y("H2"), kume="KESIF", **kimlik, zamanlar=[])
    assert len(bitler) == 0 and bitler.dtype == bool


def test_k2_aday_pozisyonu_K2_rolundeki_skaler_karari_dondurur(dunya_k2):
    """Dayanak: plan v3 G9 ('K2 bit = kapinin butun kosullari'); ön-kayıt §4 tek karar noktası. Saldiri: aday pozisyonu
    baska rol/kume/sembol tasimamali ve dondurulmus skaler referansin K2 kararina esit olmali; bit 1 olan her bar icin."""
    kimlik, _ = dunya_k2
    seri = _seri("H2", kimlik, "K2")
    on = np.nonzero(seri.onay_bitleri())[0]
    for i in (on[0], on[len(on) // 2], on[-1]):
        t = seri.zamanlar()[int(i)]
        poz = pozisyon.k2_aday_pozisyonu("H2", _y("H2"), kume="KESIF", **kimlik, t=t)
        assert poz.rol == "K2" and poz.kume == "KESIF" and poz.sembol == kimlik["sembol"]
        assert poz.plan.sinyal_zamani == t
        assert ayni(poz, karar_cagrisi(ref, "H2", kimlik, t, rol="K2"))


def test_k2_biti_olay_karari_K2_kararina_esittir_ornek_barlarda(dunya_k2):
    """Dayanak: plan v3 G9 ve ön-kayıt §4 (tek karar noktası). Saldiri: K2 bit dizisi ile her barda skaler referansin K2
    karari (onayli mi) ayni olmali; bit 1 iken sarmalayici da onayli pozisyon vermeli."""
    kimlik, _ = dunya_k2
    izgara = _izgara("H2", kimlik)
    ornek = _ornek(izgara, 50)
    bitler = pozisyon.k2_bitleri("H2", _y("H2"), kume="KESIF", **kimlik, zamanlar=pd.DatetimeIndex(ornek))
    for t, bit in zip(ornek, bitler):
        r = karar_cagrisi(ref, "H2", kimlik, t, rol="K2")
        a = karar_cagrisi(pozisyon, "H2", kimlik, t, rol="K2")
        assert bool(bit) == (not isinstance(r, BaseException)), (t, _ozet(r))
        assert ayni(a, r), (t, _ozet(a), _ozet(r))


# =====================================================================================================================
# HEDEF 5: seri_kurucu'yu kapi disindan cagirma
# =====================================================================================================================

def test_gercek_agacta_seri_kurucu_yalnizca_izinli_dosyalarda_anilir():
    """Dayanak: RESULTS §14.49 D-C8, plan 'yalnizca kapi kullanir'. Saldiri: depo taramasi (analysis/, study/, events/,
    kok betikleri, .ipynb/.pyw dahil) `seri_kurucu` adini izinli dosyalarin disinda gormemeli."""
    from tarama_yardimcisi import seri_kurucu_ihlalleri

    assert seri_kurucu_ihlalleri() == []


def test_seri_kurucu_tarayicisi_dogrudan_ice_aktarma_bicimlerini_yakalar(tmp_path):
    """Dayanak: RESULTS §14.49 D-C8. Saldiri (pozitif kontrol): analiz dizininde uc ice aktarma bicimi taranmali."""
    from tarama_yardimcisi import seri_kurucu_ihlalleri

    (tmp_path / "analysis" / "h2").mkdir(parents=True)
    govdeler = {"a.py": "from data import seri_kurucu\n", "b.py": "import data.seri_kurucu as s\n",
                "c.py": "from data.seri_kurucu import kapanis\n", "temiz.py": "from data import pozisyon\n"}
    for ad, govde in govdeler.items():
        (tmp_path / "analysis" / "h2" / ad).write_text(govde, encoding="utf-8")
    assert seri_kurucu_ihlalleri(tmp_path) == [f"analysis/h2/{x}.py" for x in "abc"]


def _tum_taramalar(kok):
    import tarama_yardimcisi as ty

    bulunan = {}
    for ad in dir(ty):
        deger = getattr(ty, ad)
        if ad.endswith("_DESENI") and isinstance(deger, str):
            bulunan[ad] = ty.ihlaller(deger, kok=kok)
    bulunan["seri_kurucu_ihlalleri"] = ty.seri_kurucu_ihlalleri(kok)
    return bulunan


@pytest.mark.parametrize("govde", [
    "from data import pozisyon\nx = pozisyon.seri_kurucu_modulu.kapanis(m, z, '4h')\n",
    "from data.pozisyon import seri_kurucu_modulu as sk\nsk.h2_funding_24s(f, z, kume_baslangic=a, kume_bitis=b, "
    "donem_baslangic=c)\n",
])
def test_seri_kurucuya_kapinin_takma_adi_uzerinden_erisim_taramada_yakalanmali(tmp_path, govde):
    """Dayanak: RESULTS §14.49 D-C8 ('seri kuruculari analiz kodunda yasaktir'). Saldiri: adi `seri_kurucu_modulu` olarak
    anarak yasagi dolanmak. Beklenen: en az bir tarama dosyayi isaretler. Gozlenen: hicbiri.

    F1-K1: kapandi (takma ad `pozisyon._seri_kurucu`, desen sozcuk sinirina dayanmiyor); strict xfail isareti kaldirildi."""
    (tmp_path / "analysis" / "h2").mkdir(parents=True)
    (tmp_path / "analysis" / "h2" / "x.py").write_text(govde, encoding="utf-8")
    sonuc = _tum_taramalar(tmp_path)
    assert any(sonuc.values()), "hicbir tarama deseni dosyayi isaretlemedi"


def test_seri_kurucu_modulu_diskten_agdan_ya_da_kume_kapisindan_veri_okumaz():
    """Dayanak: CLAUDE.md §5 ('ag ve disk erisimi yalnizca data/ katmaninda', kapi disi kullanimda veri kapisi atlanamaz).
    Saldiri: `data/seri_kurucu.py` kaynagi (AST) yukleyici, onbellek, bolme/evren tablosu ya da dosya acan hicbir ad
    kullanmamali: yalniz cerceve alan saf bir moduldur, bu yuzden kapi disindan cagrilsa bile B grubu ya da onay verisini
    kendisi OKUYAMAZ (veriyi cagiranin kapili yukleyicilerden almasi gerekir)."""
    agac = ast.parse((KOK / "data" / "seri_kurucu.py").read_text(encoding="utf-8"))
    ice = set()
    for d in ast.walk(agac):
        if isinstance(d, ast.ImportFrom):
            ice.add(d.module or "")
            ice.update(f"{d.module or ''}.{a.name}" for a in d.names)
        elif isinstance(d, ast.Import):
            ice.update(a.name for a in d.names)
    yasak_parca = ("split", "universe", "kume_bellegi", "binance_vision", "onbellek", "requests", "os", "pathlib", "subprocess")
    kotu_ice = sorted(m for m in ice if any(p == m.split(".")[-1] or p in m.split(".") for p in yasak_parca))
    assert kotu_ice == [], kotu_ice
    kullanilan = ({d.attr for d in ast.walk(agac) if isinstance(d, ast.Attribute)}
                  | {d.id for d in ast.walk(agac) if isinstance(d, ast.Name)})
    yasak_ad = {"mumlari_yukle", "funding_yukle", "kume_erisimi", "split_oku", "evren_yukle", "read_parquet",
                "to_parquet", "open", "onbellekten_oku", "ham_mumlari_yukle", "ham_funding_yukle", "kesif_kosusu",
                "onay_kosusu", "yukle", "getir"}
    assert not (kullanilan & yasak_ad), sorted(kullanilan & yasak_ad)


def test_seri_kurucu_ve_kapi_ic_adlari_gercek_analiz_agacinda_gecmez():
    """Dayanak: RESULTS §14.49 (kapi ic adlari analiz kodunda yasak). Saldiri: `_kapi_satirlari`, `_SERI_BELLEGI`,
    `_SERI_GIZLI`, `_KapiSerisi__` ve `kume_bellegi` adlarinin gercek agacta (tests/, data/, .claude/ disinda; F1 denetim
    dizini dahil degil) gecmedigini sinar."""
    import tarama_yardimcisi as ty

    for desen in (ty.CIKIS_KAPI_DISI_DESENI, ty.KAYIT_DESENI):
        assert ty.ihlaller(desen) == [], desen[:40]


# =====================================================================================================================
# HEDEF 6: olay_karari ile kapi_serisi / skaler referans esitligi
# =====================================================================================================================

@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
@pytest.mark.parametrize("rol", ["olay", "K1", "K2"])
def test_olay_karari_seri_satiri_ve_referans_sicak_ve_soguk_onbellekte_ayni(dunya_a, hipotez, rol):
    """Dayanak: plan v3 G1 / ön-kayıt §4 (tek karar noktası). Saldiri: izgaranin ornek barlarinda (rastgele 40 + ilk/son
    barlar) ORTA yapilandirmada (izgara[4]) uc yol (sarmalayici, seri satiri, dondurulmus skaler referans) AYNI sinif,
    ayni mesaj, ayni pozisyon alanlari. Sonra onbellek bosaltilir (soguk) ve sarmalayici ayni karari vermeli."""
    kimlik, _ = dunya_a
    y = _y(hipotez, 4)
    izgara = _izgara(hipotez, kimlik)
    sira = {t: i for i, t in enumerate(izgara)}
    capali = hipotez == "H1" and rol == "olay"
    seri = _seri(hipotez, kimlik, rol, y=y, capa=[_capa(t, i) for i, t in enumerate(izgara)] if capali else None)

    def capasi(t):
        return _capa(t, sira[t]) if capali else None

    ornek = _ornek(izgara)
    sicak = {}
    for t in ornek:
        a = karar_cagrisi(pozisyon, hipotez, kimlik, t, rol=rol, capa=capasi(t), yapilandirma=y)
        r = karar_cagrisi(ref, hipotez, kimlik, t, rol=rol, capa=capasi(t), yapilandirma=y)
        s = _seri_sonucu(seri, t)
        assert ayni(a, r), (t, _ozet(a), _ozet(r))
        assert ayni(a, s), (t, _ozet(a), _ozet(s))
        sicak[t] = a
    kume_bellegi.temizle()
    for t in ornek[:4] + ornek[-2:]:
        soguk = karar_cagrisi(pozisyon, hipotez, kimlik, t, rol=rol, capa=capasi(t), yapilandirma=y)
        assert ayni(soguk, sicak[t]), (t, _ozet(soguk), _ozet(sicak[t]))


@pytest.mark.parametrize("ufuk", [6, 42])
@pytest.mark.parametrize("rol", ["olay", "K1", "K2"])
def test_ikincil_ufukta_sarmalayici_seri_ve_referans_ayni_birincil_ret_ikincilde_korunur(dunya_a, ufuk, rol):
    """Dayanak: ön-kayıt §4 'Ufuk değerlerinin bağlanması' rev.10 ('olay birincil ufukta belirlenir'), plan v3 G1/G11.
    Saldiri: ikincil ufukta (6 ve 42 bar; 42 donem sonuna tasar) ornek barlar + SON barlarda sarmalayici = seri satiri =
    referans; birincil ufukta reddedilen barda ikincil de AYNI retle donmeli."""
    kimlik, _ = dunya_a
    y = _y("H2", 4)
    izgara = _izgara("H2", kimlik)
    birincil = _seri("H2", kimlik, rol, y=y)
    ikincil = _seri("H2", kimlik, rol, y=y, ufuk=ufuk)
    for t in _ornek(izgara, 30) + list(izgara[-12:]):
        a = karar_cagrisi(pozisyon, "H2", kimlik, t, rol=rol, yapilandirma=y, ufuk=ufuk)
        r = karar_cagrisi(ref, "H2", kimlik, t, rol=rol, yapilandirma=y, ufuk=ufuk)
        assert ayni(a, r), (t, _ozet(a), _ozet(r))
        if ikincil.icerir(t):
            assert ayni(_seri_sonucu(ikincil, t), r), (t, _ozet(r))
        if birincil.icerir(t):
            p = _seri_sonucu(birincil, t)
            if isinstance(p, BaseException):
                assert ayni(a, p), (t, _ozet(a), _ozet(p))


def test_H1_capa_penceresi_siniri_ve_capa_varyantlarinda_sarmalayici_referans_ve_seri_ayni(dunya_a):
    """Dayanak: ön-kayıt §5 H1 madde 2-3 (teyit pump'tan sonra, en fazla 12 bar), CLAUDE.md §3.6. Saldiri: gercek pump
    barlarinda capa-teyit mesafesi -2..20 bar (pencere dışı ve capadan ONCEKI bar dahil): pencere disinda hicbir yolda
    onayli pozisyon olmamali; sarmalayici = referans her mesafede; pencere ici barlarda seri satiri da ayni. Ek: capa
    farkli saat diliminde (ayni an) ve capa 30 sn kaymis."""
    kimlik, ozel = dunya_a
    for pump in ozel["pump"][:4]:
        tek = _seri("H1", kimlik, "olay", capa=pump)
        for n in (-2, -1, 0, 1, 2, 6, 11, 12, 13, 20):
            t = pump + n * H4
            a = karar_cagrisi(pozisyon, "H1", kimlik, t, rol="olay", capa=pump)
            r = karar_cagrisi(ref, "H1", kimlik, t, rol="olay", capa=pump)
            assert ayni(a, r), (n, _ozet(a), _ozet(r))
            if not (1 <= n <= config.H1_IZLEME_BAR):
                assert not tek.icerir(t), n
                assert not isinstance(a, pozisyon.OnaylanmisPozisyon), n
            elif tek.icerir(t):
                assert ayni(_seri_sonucu(tek, t), r), (n, _ozet(r))
        t = pump + 3 * H4
        ofsetli = pump.tz_convert(UC_SAAT)
        assert ayni(karar_cagrisi(pozisyon, "H1", kimlik, t, rol="olay", capa=ofsetli),
                    karar_cagrisi(ref, "H1", kimlik, t, rol="olay", capa=ofsetli))
        kayik = pump + pd.Timedelta(seconds=30)
        a = karar_cagrisi(pozisyon, "H1", kimlik, t, rol="olay", capa=kayik)
        assert ayni(a, karar_cagrisi(ref, "H1", kimlik, t, rol="olay", capa=kayik))
        assert not isinstance(a, pozisyon.OnaylanmisPozisyon)
        assert len(_seri("H1", kimlik, "olay", capa=kayik)) == 0


def test_H1_capa_dizisi_ve_tek_capa_serileri_ayni_satiri_verir(dunya_a):
    """Dayanak: plan v3 G1 (H1 capa skaler/dizi varyantlari). Saldiri: ayni (t, capa) cifti icin 'teyit basina capa dizisi'
    serisi ile 'tek pump capasi' serisi AYNI satiri vermeli (iki seri bicimi farkli karar uretemez)."""
    kimlik, ozel = dunya_a
    izgara = _izgara("H1", kimlik)
    capa = {t: t - H4 for t in izgara}             # varsayilan: teyitten bir bar once (gecerli, tanimli pencere)
    esler = []
    for pump in ozel["pump"][:4]:
        for n in range(1, config.H1_IZLEME_BAR + 1):
            t = pump + n * H4
            if t in capa:
                capa[t] = pump                    # bu barlarin capasi gercek pump (tek capa serisiyle ortak cift)
                esler.append((t, pump))
    dizi = _seri("H1", kimlik, "olay", capa=[capa[t] for t in izgara])
    karsilastirilan = 0
    for pump in ozel["pump"][:4]:
        tek = _seri("H1", kimlik, "olay", capa=pump)
        for t, p in esler:
            if p == pump and tek.icerir(t) and dizi.icerir(t):
                assert ayni(_seri_sonucu(dizi, t), _seri_sonucu(tek, t)), (t - pump,)
                karsilastirilan += 1
    assert karsilastirilan >= 1, "kurulum: capa dizisi ile tek capa serisi kesisen bar yok"


@pytest.mark.parametrize(("hipotez", "rol"), [("H1", "olay"), ("H1", "K2"), ("H2", "olay"), ("H2", "K1"), ("H2", "K2"),
                                              ("H3", "olay"), ("H3", "K2")])
def test_seri_kurulumu_hata_verince_geri_dusus_yolu_ayni_karari_uretir(dunya_a, monkeypatch, hipotez, rol):
    """Dayanak: plan v3 G10/G1 ('ikinci bir karar yolu yoktur'); `olay_karari` geri dusus yolu. Saldiri: `kapi_serisi`
    `OlayOlusmaz` disi bir hatayla durur; tek bar cekirdegi (`_kapi_satirlari([t])`) seri yolundan FARKLI karar uretmemeli:
    ayni sinif, ayni mesaj, ayni pozisyon alanlari (ornek barlar + son barlar).

    F1-K1 (D-B1) ile bilerek guncellendi: geri dusus yolu KALKTI. Seri kurulumunun hatasi `olay_karari`'dan oldugu gibi
    (ayni sinif, ayni mesaj) yukselir ve tek bar cekirdegi hic calismaz; boylece seri yolundan farkli bir karar uretecek
    ikinci yol da yoktur. Saldirinin amaci (seri hatasinda farkli karar yok) korunur."""
    kimlik, _ = dunya_a
    y = _y(hipotez, 4)
    izgara = _izgara(hipotez, kimlik)
    sira = {t: i for i, t in enumerate(izgara)}
    capali = hipotez == "H1" and rol == "olay"
    ornek = _ornek(izgara, 25)

    def capasi(t):
        return _capa(t, sira[t]) if capali else None

    cagri = []

    def bozuk(*a, **k):
        cagri.append(1)
        raise RuntimeError("bilerek: seri kurulumu durdu")

    def cekirdek_yasak(*a, **k):
        raise AssertionError("seri hatasindan sonra tek bar cekirdegi calismamali (D-B1)")

    kume_bellegi.temizle()
    monkeypatch.setattr(pozisyon, "kapi_serisi", bozuk)
    monkeypatch.setattr(pozisyon, "_kapi_satirlari", cekirdek_yasak)
    for t in ornek:
        geri = karar_cagrisi(pozisyon, hipotez, kimlik, t, rol=rol, capa=capasi(t), yapilandirma=y)
        assert ayni(geri, RuntimeError("bilerek: seri kurulumu durdu")), (t, _ozet(geri))
    assert len(cagri) == len(ornek), "kurulum: her cagri seri kurulumuna gitmeli"


@pytest.mark.parametrize("rol", ["K1", "olay"])
@pytest.mark.parametrize("fark", [pd.Timedelta(nanoseconds=1), pd.Timedelta(seconds=30),
                                  pd.Timedelta(seconds=59, milliseconds=999), pd.Timedelta(minutes=1),
                                  -pd.Timedelta(seconds=59), -pd.Timedelta(minutes=1), pd.Timedelta(hours=1),
                                  pd.Timedelta(hours=4)])
def test_izgara_disi_ve_tolerans_sinirindaki_t_icin_sarmalayici_referansla_ayni(dunya_a, rol, fark):
    """Dayanak: ön-kayıt §4 rev.8 'Zaman toleransı' ('1 dakikadan kesin kucuk fark ayni an; tam 1 dakika degil'), plan v3
    G1. Saldiri: izgara barindan 1 ns, 30 sn, 59.999 sn, tam 1 dk, -59 sn, -1 dk, +1 saat, +4 saat sapmis t. Bu t seri
    satiri degildir; geri dusus tek bar cekirdegi referansla ayni karari vermeli."""
    kimlik, _ = dunya_a
    izgara = _izgara("H2", kimlik)
    for taban in (izgara[50], izgara[700], izgara[-1]):
        t = taban + fark
        a = karar_cagrisi(pozisyon, "H2", kimlik, t, rol=rol)
        r = karar_cagrisi(ref, "H2", kimlik, t, rol=rol)
        assert ayni(a, r), (fark, _ozet(a), _ozet(r))


def _dogrudan(modul, kimlik, t, **ek):
    tanim = pencere.hipotez_ufuklari("H2")
    k = {"ufuk": tanim.birincil, "bar": tanim.bar, "hipotez": "H2", "yapilandirma": _y("H2"), "rol": "K1",
         "capa": None, "birincil_ufuk": tanim.birincil, "kume": "KESIF", **kimlik, **esikler(tanim.bar)}
    k.update(ek)
    ufuk, bar = k.pop("ufuk"), k.pop("bar")
    return _cagir(modul.olay_karari, t, ufuk, bar, **k)


def _hata_vakalari(t):
    class YalanciStr(str):
        def __eq__(self, diger):
            return True

        __hash__ = str.__hash__

    return {
        "hipotez_kucuk": {"hipotez": "h2"}, "hipotez_none": {"hipotez": None},
        "yapilandirma_izgara_disi": {"yapilandirma": {"phi": 0.0003, "k": 4}},
        "yapilandirma_eksik": {"yapilandirma": {"phi": 0.0003}},
        "yapilandirma_demet": {"yapilandirma": (0.0003,)},
        "rol_bilinmeyen": {"rol": "K3"}, "rol_kucuk": {"rol": "k1"}, "rol_none": {"rol": None},
        "rol_yalanci": {"rol": YalanciStr("K9")},
        "capa_H2": {"capa": t - H4},
        "kume_bilinmeyen": {"kume": "C3"}, "kume_kucuk": {"kume": "kesif"}, "kume_none": {"kume": None},
        "kume_yalanci": {"kume": YalanciStr("C3")},
        "kume_C1_kosusuz": {"kume": "C1"}, "kume_C2_kosusuz": {"kume": "C2"},
        "sembol_bilinmeyen": {"sembol": "YOKUSDT"}, "sembol_sayi": {"sembol": 5},
        "donem_bool": {"donem_no": True}, "donem_yok": {"donem_no": 9}, "donem_str": {"donem_no": "0"},
        "hacim_yanlis": {"asgari_hacim": 1.0}, "hacim_bool": {"asgari_hacim": True},
        "hacim_str": {"asgari_hacim": "1e7"}, "hacim_yarim": {"asgari_hacim": config.ASGARI_HACIM_4H * 0.5},
        "yas_yanlis": {"asgari_listeleme_yasi_gun": 29}, "yas_bool": {"asgari_listeleme_yasi_gun": True},
        "birincil_yanlis": {"birincil_ufuk": 17}, "ufuk_yanlis": {"ufuk": 7}, "bar_yanlis": {"bar": "1d"},
        "ikincil_kume_bilinmeyen": {"ufuk": 6, "kume": "C3"},
        "ikincil_sembol_bilinmeyen": {"ufuk": 6, "sembol": "YOKUSDT"},
        "ikincil_capa": {"ufuk": 6, "capa": t - H4}, "ikincil_C1": {"ufuk": 6, "kume": "C1"},
        "ikincil_t_naive": {"ufuk": 6, "t": t.tz_localize(None)},
        "rol_ve_kume_bozuk": {"rol": "K3", "kume": "C3"},
        "capa_ve_sembol_bozuk": {"capa": t - H4, "sembol": "YOKUSDT"},
        "yapilandirma_ve_rol_bozuk": {"yapilandirma": {"phi": 1.0, "k": 3}, "rol": "K3"},
        "C1_ve_sembol_bilinmeyen": {"kume": "C1", "sembol": "YOKUSDT"},
        "hacim_ve_kume_bozuk": {"asgari_hacim": 1.0, "kume": "C3"},
        "t_naive": {"t": t.tz_localize(None)}, "t_sabit_ofset": {"t": t.tz_convert(UC_SAAT)},
        "t_str": {"t": str(t)}, "t_none": {"t": None},
        "t_naive_ve_rol_bozuk": {"t": t.tz_localize(None), "rol": "K3"},
    }


@pytest.mark.parametrize("sicak", [True, False])
def test_hata_vakalarinda_sarmalayici_ve_referans_ayni_sinif_ve_mesajla_hata_verir(dunya_a, sicak):
    """Dayanak: plan v3 G1 ('imza, istisnalar ve donus degeri P2b-2 oncesiyle aynidir'); ön-kayıt §4 tek karar noktası.
    Saldiri: gecersiz girdi matrisi (hipotez, yapilandirma, rol, capa, kume, sembol, donem, esik, ufuk, t; ikili bozuk
    girdilerle oncelik siralamasi dahil) hem sicak hem soguk onbellekte: yeni yol ile dondurulmus skaler referans AYNI
    hata sinifini ve mesajini vermeli. Sicak onbellek hicbir denetimi atlatmamali."""
    kimlik, _ = dunya_a
    seri = _seri("H2", kimlik, "K1")
    t = _ilk_onayli(seri)
    if sicak:
        assert seri.sonuc(t) is not None
    else:
        kume_bellegi.temizle()
    vakalar = _hata_vakalari(t)
    sapma = []
    hata_sayisi = 0
    for ad, ek in vakalar.items():
        ek = dict(ek)
        zaman = ek.pop("t", t) if "t" in ek else t
        yeni = _dogrudan(pozisyon, kimlik, zaman, **ek)
        eski = _dogrudan(ref, kimlik, zaman, **ek)
        hata_sayisi += isinstance(eski, BaseException)
        if not ayni(yeni, eski):
            sapma.append((ad, _ozet(yeni), _ozet(eski)))
    assert not sapma, sapma
    assert hata_sayisi >= len(vakalar) // 2, "kurulum: vakalarin cogu hata uretmeli"


def test_gecerli_cagri_sicak_onbellekte_bile_esik_ve_baglam_denetimini_atlamaz(dunya_a):
    """Dayanak: `eligibility.esikleri_dogrula` ('esikler on-kayit degeri olmali, baska deger verilemez'). Saldiri: seri
    sicakken uygunluk esikleri oynatilir (yarisi, bir kusur, bool, str): sarmalayici onbellekteki satiri DONDURMEMELI,
    ValueError/TypeError vermeli."""
    kimlik, _ = dunya_a
    seri = _seri("H2", kimlik, "K1")
    t = _ilk_onayli(seri)
    dogru = _dogrudan(pozisyon, kimlik, t)
    assert isinstance(dogru, pozisyon.OnaylanmisPozisyon), "kurulum"
    for hacim in (config.ASGARI_HACIM_4H * 0.5, config.ASGARI_HACIM_4H * 1.0000001, config.ASGARI_HACIM_4H - 1, True,
                  "1e7", None):
        sonuc = _dogrudan(pozisyon, kimlik, t, asgari_hacim=hacim)
        assert isinstance(sonuc, (ValueError, TypeError)), (hacim, _ozet(sonuc))
    for yas in (29, 29.999, 31, False, None):
        sonuc = _dogrudan(pozisyon, kimlik, t, asgari_listeleme_yasi_gun=yas)
        assert isinstance(sonuc, (ValueError, TypeError)), (yas, _ozet(sonuc))
