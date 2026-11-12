"""Performans 2b-2: tek seri kapi (`pozisyon.kapi_serisi`) ve ince sarmalayici `olay_karari` (plan v3; RESULTS §14.49).

Sentetik dunya `tests/esitlik_yardimcisi.dunya`dir (eksik barlar, bozuk hucreli bar, gec baslayan ve ritmi degisen
funding, NaN oran, eksik kayit). Her karar dondurulmus skaler referansla (`data._skaler_referans.olay_karari`)
karsilastirilir: sonuc SINIFI, ret MESAJI ve onayli pozisyonun butun alanlari. Deger, olay sayisi ve getiri yazilmaz.
Test adlari gereksinim koduyla baslar. Aga cikmaz.
"""

from __future__ import annotations

import ast
import dataclasses
import math

import numpy as np
import pandas as pd
import pytest

import config
from data import _skaler_referans as ref
from data import kume_bellegi, pencere, pozisyon, sinyal, split
from esitlik_yardimcisi import H4, dunya, karar_cagrisi
from kapi_yardimcisi import SENTETIK_VERI, veri
from tarama_yardimcisi import KOK
from uygunluk_yardimcisi import esikler

BAS, BITIS = "2021-01-01", "2021-08-31 20:00"
U = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731


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


class _SplitVekili:
    """`split` modulu koruma altindadir (adlari disaridan atanamaz). Casuslar kapinin gordugu `split_modulu` adina bu
    vekille kurulur: verilen adlar degistirilir, gerisi gercek moduldendir."""

    def __init__(self, **degisen):
        self.__dict__.update(degisen)

    def __getattr__(self, ad):
        return getattr(split, ad)


def _split_vekili(monkeypatch, **degisen):
    monkeypatch.setattr(pozisyon, "split_modulu", _SplitVekili(**degisen))


@pytest.fixture
def dunya_g1():
    return dunya(611, BAS, BITIS)


# --- G1: olay_karari (yeni) == referans, her rolde, her barda --------------------------------------------------------

@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
@pytest.mark.parametrize("rol", ["olay", "K1", "K2"])
def test_G1_olay_karari_ve_kapi_serisi_her_rolde_her_barda_referansla_ayni(dunya_g1, hipotez, rol):
    """Izgaranin BUTUN barlari + izgara disi barlar (bosluk barlari, donem disi, tolerans payli t). Iki yeni yol: ince
    sarmalayici `olay_karari` ve seri satiri (`kapi_serisi(...).sonuc`; H1 olay rolunde teyit basina capa dizisi).
    Kurulum kaniti: hem onay hem en az iki farkli ret sinifi gorulur."""
    kimlik, _ = dunya_g1
    izgara = _izgara(hipotez, kimlik)
    capali = hipotez == "H1" and rol == "olay"
    seri = _seri(hipotez, kimlik, rol, capa=[_capa(t, i) for i, t in enumerate(izgara)] if capali else None)
    bas, bitis, _ = pozisyon.donem_kaydi(kimlik["sembol"], 0)
    adim = pencere.adim(config.HIPOTEZ_IZGARASI[hipotez])
    disari = [bas - 3 * adim, bas + pd.Timedelta(days=61), bas + pd.Timedelta(days=100, hours=12),
              izgara[50] + pd.Timedelta(seconds=30), bitis + adim]
    siniflar = set()
    for i, t in enumerate(list(izgara) + disari):
        capa = _capa(t, i) if capali else None
        r = karar_cagrisi(ref, hipotez, kimlik, t, rol=rol, capa=capa)
        a = karar_cagrisi(pozisyon, hipotez, kimlik, t, rol=rol, capa=capa)
        assert ayni(a, r), (i, t, type(a).__name__, type(r).__name__)
        if i < len(izgara):
            assert ayni(_seri_sonucu(seri, t), r), (i, t)
        siniflar.add(type(r).__name__)
    if capali:
        # Dunyanin enjekte ettigi pump barlari capa olarak: tek capali seri (izleme penceresi) ve bar basina okuyucu.
        _, ozel = dunya_g1
        for pump in ozel["pump"]:
            tek = _seri(hipotez, kimlik, rol, capa=pump)
            for n in range(1, config.H1_IZLEME_BAR + 1):
                t = pump + n * H4
                r = karar_cagrisi(ref, hipotez, kimlik, t, rol=rol, capa=pump)
                assert ayni(karar_cagrisi(pozisyon, hipotez, kimlik, t, rol=rol, capa=pump), r), (pump, n)
                if tek.icerir(t):
                    assert ayni(_seri_sonucu(tek, t), r), (pump, n)
                siniflar.add(type(r).__name__)
    if not (hipotez == "H3" and rol == "olay"):
        assert "OnaylanmisPozisyon" in siniflar, siniflar
    assert len(siniflar - {"OnaylanmisPozisyon"}) >= 2, siniflar


def test_G1_ikincil_ufuk_her_barda_referansla_ayni(dunya_g1):
    kimlik, _ = dunya_g1
    izgara = _izgara("H2", kimlik)
    for ufuk in (6, 42):
        seri = _seri("H2", kimlik, "K1", ufuk=ufuk)
        for t in izgara[::7]:
            r = karar_cagrisi(ref, "H2", kimlik, t, ufuk=ufuk)
            assert ayni(karar_cagrisi(pozisyon, "H2", kimlik, t, ufuk=ufuk), r)
            assert ayni(_seri_sonucu(seri, t), r)


# --- G8: kontrol maskesi kosuldan bagimsiz -------------------------------------------------------------------------

@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_G8_esik_tarafi_degisince_K1_K2_maskesi_degismez(dunya_g1, hipotez, monkeypatch):
    """SABITLEME: veri ayni dunya (uygunluk hacmi, funding tamligi ve capasiz pencerelerin girdileri ayni cerceveler);
    pencere UZUNLUGUNU belirleyen parametre sabit (H2'de `k` ayni tutulur; H1 ve H3'un esikleri pencere uzunlugu
    tasimaz). Degisen YALNIZCA esik tarafi: H1 `theta`/`delta`, H2 `phi`, H3 `nu`/`tau`. K1 ve K2 bit dizileri her
    yapilandirmada ayni olmali; olay rolunun vektorel kosulu ise en az bir yapilandirma ciftinde farkli (test bos
    degil). Kontrol rolunde kosul fonksiyonu hic cagrilmaz."""
    kimlik, _ = dunya_g1
    izgara = _izgara(hipotez, kimlik)
    yapilar = [dict(y) for y in sinyal.izgara(hipotez)]
    if hipotez == "H2":
        yapilar = [y for y in yapilar if y["k"] == yapilar[0]["k"]]
    assert len(yapilar) >= 2
    capalar = [_capa(t, i) for i, t in enumerate(izgara)] if hipotez == "H1" else None
    kosullar = [tuple(pozisyon._olay_kosulu_serisi(hipotez, y, kume="KESIF", **kimlik, capa=capalar)) for y in yapilar]
    assert len(set(kosullar)) >= 2, "kurulum: esik degisimi kosulu degistirmeli"

    def yasak(*a, **k):
        raise AssertionError("kontrol rolunde kosul hesaplanamaz (G8)")

    monkeypatch.setattr(pozisyon, "_kosul_dizisi", yasak)
    for rol in ("K1", "K2"):
        maskeler = {tuple(_seri(hipotez, kimlik, rol, y=y).onay_bitleri()) for y in yapilar}
        assert len(maskeler) == 1, rol
        assert any(next(iter(maskeler))), "kurulum: onayli kontrol bari olmali"


# --- G9: K2 bit dizisi ---------------------------------------------------------------------------------------------

def _k2_dunyasi():
    """H2 K2 rolunde onayli bir bar t ve onun dunyasinin cerceveleri."""
    kimlik, _ = dunya(612, BAS, BITIS)
    izgara = _izgara("H2", kimlik)
    seri = _seri("H2", kimlik, "K2")
    bit = seri.onay_bitleri()
    t = izgara[np.nonzero(bit)[0][len(np.nonzero(bit)[0]) // 2]]
    return kimlik, t, seri.sonuc(t)


def _boz(kimlik, t, poz, kosul):
    """Tek bir kosulu bozan yeni sentetik sembol (diger her sey ayni). Doner: yeni kimlik."""
    m, f = (x.copy() for x in SENTETIK_VERI[kimlik["sembol"]])
    bas, bitis, _ = pozisyon.donem_kaydi(kimlik["sembol"], 0)
    z = pd.DatetimeIndex(m["open_time"])
    ek = {}
    if kosul == "plan_giris_bari":
        m = m.loc[z != poz.plan.giris]
    elif kosul == "t_bari":
        m = m.loc[z != t]
    elif kosul == "capasiz_pencere":
        m = m.loc[z != t - 2 * H4]
    elif kosul == "uygunluk":
        gun = t.floor("D")
        m.loc[np.asarray((z >= gun - pd.Timedelta(days=30)) & (z < gun)), "quote_volume"] *= 1e-6
    elif kosul == "funding_li_donem":
        ek["funding_yok"] = True
    elif kosul == "funding_tamligi":
        fz = pd.DatetimeIndex(f["odeme_zamani"])
        f = f.loc[~np.asarray((fz > poz.plan.giris) & (fz < poz.plan.cikis_ani))]
    elif kosul == "funding_toplami_sonlu":
        fz = pd.DatetimeIndex(f["odeme_zamani"])
        f.loc[np.asarray((fz > poz.plan.giris) & (fz <= poz.plan.cikis_ani)), "oran"] = np.inf
    elif kosul == "p0_pozitif":
        m.loc[z == poz.plan.giris, "open"] = 0.0
    elif kosul == "p1_pozitif":
        m.loc[z == poz.plan.cikis.zaman, poz.plan.cikis.fiyat_alani] = -1.0
    elif kosul == "mae_penceresi":
        m.loc[z == poz.plan.giris + H4, "high"] = 0.0
    elif kosul == "grup":
        ek["grup"] = "B"
    else:
        raise ValueError(kosul)
    return veri(m.reset_index(drop=True), f.reset_index(drop=True), bas, bitis, ham=True, **ek)


K2_KOSULLARI = ["plan_giris_bari", "t_bari", "capasiz_pencere", "uygunluk", "funding_li_donem", "funding_tamligi",
                "funding_toplami_sonlu", "p0_pozitif", "p1_pozitif", "mae_penceresi", "grup"]


@pytest.fixture
def k2_dunyasi():
    return _k2_dunyasi()


@pytest.mark.parametrize("kosul", K2_KOSULLARI)
def test_G9_K2_biti_kapinin_her_kosulunu_kapsar(k2_dunyasi, kosul):
    """Her kosul tek tek bozulur. Referans t'de ret veriyorsa bit 0; referans `OlayOlusmaz` disi bir hata veriyorsa bit
    dizisi kurulamaz, ayni sinifla durur (G10: veri hatasi 0 bitine donusmez). Grup bozulursa bit acik grup
    denetimiyle 0."""
    kimlik, t, poz = k2_dunyasi
    assert pozisyon.k2_bitleri("H2", _y("H2"), kume="KESIF", **kimlik, zamanlar=[t]).tolist() == [True]
    yeni = _boz(kimlik, t, poz, kosul)
    if kosul == "grup":
        assert pozisyon.k2_bitleri("H2", _y("H2"), kume="KESIF", **yeni, zamanlar=[t]).tolist() == [False]
        return
    r = karar_cagrisi(ref, "H2", yeni, t, rol="K2")
    assert isinstance(r, BaseException), "kurulum: bozma referansta da karari dusurmeli"
    if isinstance(r, pencere.OlayOlusmaz):
        assert pozisyon.k2_bitleri("H2", _y("H2"), kume="KESIF", **yeni, zamanlar=[t]).tolist() == [False]
    else:
        with pytest.raises(type(r)):
            pozisyon.k2_bitleri("H2", _y("H2"), kume="KESIF", **yeni, zamanlar=[t])
    assert ayni(karar_cagrisi(pozisyon, "H2", yeni, t, rol="K2"), r)


def test_G9_K2_baglam_denetimi_bitte_ve_okumada_calisir(k2_dunyasi, monkeypatch):
    kimlik, t, _ = k2_dunyasi

    class Yasak(PermissionError):
        pass

    def yasak(kume):
        raise Yasak("baglam yok")

    seri = _seri("H2", kimlik, "K2")
    _split_vekili(monkeypatch, kesif_baglami_dogrula=yasak)
    with pytest.raises(Yasak):
        pozisyon.k2_bitleri("H2", _y("H2"), kume="KESIF", **kimlik, zamanlar=[t])
    with pytest.raises(Yasak):
        seri.onay_bitleri()


def test_G9_B_grubu_coinin_biti_acik_grup_denetimiyle_0_veri_okunmaz(k2_dunyasi, monkeypatch):
    kimlik, t, poz = k2_dunyasi
    yeni = _boz(kimlik, t, poz, "grup")

    def yukleme_yasak(*a, **k):
        raise AssertionError("B grubu coin icin KESIF verisi okunmamali (acik grup denetimi)")

    monkeypatch.setattr(pozisyon, "_veri_yukle", yukleme_yasak)
    monkeypatch.setattr(pozisyon, "_karar_girdisi", yukleme_yasak)
    bitler = pozisyon.k2_bitleri("H2", _y("H2"), kume="KESIF", **yeni, zamanlar=[t, t + H4, t + 2 * H4])
    assert bitler.tolist() == [False, False, False] and bitler.dtype == bool
    with pytest.raises(ValueError):
        pozisyon.kapi_serisi("H2", _y("H2"), "K2", kume="KESIF", **yeni)   # grup denetimi kapida da acik


def test_G9_orneklenen_adayin_sonradan_kurulumu_hata_verirse_sert_hata(k2_dunyasi, monkeypatch):
    """Biti 1 olan aday orneklendi; aday kurulurken hata cikarsa hata yukari cikar (yeniden cekim yok, None ya da 0
    donmez). Iki bicim: (a) veri yolu hata verir -> ayni hata; (b) aday artik onayli degil -> `KontrolAdayiHatasi`."""
    kimlik, t, _ = k2_dunyasi
    assert pozisyon.k2_aday_pozisyonu("H2", _y("H2"), kume="KESIF", **kimlik, t=t).plan.sinyal_zamani == t
    kume_bellegi.temizle()

    def bozuk(*a, **k):
        raise pencere.VeriHatasi("bilerek: kurulumda veri hatasi")

    with monkeypatch.context() as yama:
        yama.setattr(pozisyon, "_veri_yukle", bozuk)
        with pytest.raises(pencere.VeriHatasi):
            pozisyon.k2_aday_pozisyonu("H2", _y("H2"), kume="KESIF", **kimlik, t=t)
    seri = _seri("H2", kimlik, "K2")
    ret_t = next(x for x, b in zip(seri.zamanlar(), seri.onay_bitleri()) if not b)
    with pytest.raises(pozisyon.KontrolAdayiHatasi):
        pozisyon.k2_aday_pozisyonu("H2", _y("H2"), kume="KESIF", **kimlik, t=ret_t)
    with pytest.raises(pozisyon.KontrolAdayiHatasi):
        seri.pozisyon(t + pd.Timedelta(seconds=30))


# --- G10: veri hatasi ret degildir ----------------------------------------------------------------------------------

def test_G10_veri_hatasi_seriyi_durdurur_ret_koduna_donusmez(k2_dunyasi):
    kimlik, t, poz = k2_dunyasi
    yeni = _boz(kimlik, t, poz, "p0_pozitif")
    for rol in ("K1", "K2"):
        with pytest.raises(pencere.VeriHatasi):
            pozisyon.kapi_serisi("H2", _y("H2"), rol, kume="KESIF", **yeni)
    # Bar basina okuyucu: bozuk barda skalerle ayni hata; baska barda skalerle ayni karar (cekirdegin tek bar kosusu).
    assert ayni(karar_cagrisi(pozisyon, "H2", yeni, t), karar_cagrisi(ref, "H2", yeni, t))
    baska = _izgara("H2", yeni)[len(_izgara("H2", yeni)) // 3]
    assert ayni(karar_cagrisi(pozisyon, "H2", yeni, baska), karar_cagrisi(ref, "H2", yeni, baska))
    # Hicbir satir VeriHatasi'ni ret olarak tasimaz: saglam dunyanin serisinde ret siniflari yalnizca OlayOlusmaz.
    seri = _seri("H2", kimlik, "K1")
    for x in seri.zamanlar():
        s = _seri_sonucu(seri, x)
        assert isinstance(s, (pozisyon.OnaylanmisPozisyon, pencere.OlayOlusmaz)), type(s)


# --- G11: imza, onbellek, erisim, donem isareti ----------------------------------------------------------------------

def test_G11_kosu_kapandiktan_sonra_eski_seri_okunamaz(dunya_g1):
    kimlik, _ = dunya_g1
    seri = _seri("H2", kimlik, "K1")
    t = seri.zamanlar()[100]
    assert seri.icerir(t)
    kume_bellegi.temizle()            # kesif ve onay kosusunun acilisi ve kapanisi bunu cagirir
    for okuma in (lambda: seri.icerir(t), lambda: seri.sonuc(t), lambda: seri.zamanlar(), lambda: seri.onay_bitleri(),
                  lambda: seri.pozisyon(t), lambda: len(seri)):
        with pytest.raises(pozisyon.SeriEskidi):
            okuma()
    yeni = _seri("H2", kimlik, "K1")
    assert yeni is not seri and yeni.icerir(t)


def test_G11_kesif_ve_onay_kosusu_temizle_cagirir():
    import inspect

    for ad in ("kesif_kosusu", "onay_kosusu"):
        assert inspect.getsource(getattr(split, ad)).count("kume_bellegi.temizle()") >= 2, ad


def test_G11_anahtar_alanlarinin_her_biri_ayri_girdi_uretir(dunya_g1):
    kimlik, _ = dunya_g1
    kimlik2, _ = dunya(613, BAS, BITIS)
    kume_bellegi.temizle()
    t = _izgara("H1", kimlik)[300]
    seriler = {
        "temel": _seri("H2", kimlik, "K1"),
        "sembol": _seri("H2", kimlik2, "K1"),
        "hipotez_bar_birincil": _seri("H3", kimlik, "K1"),
        "hipotez": _seri("H1", kimlik, "K1"),
        "yapilandirma": _seri("H2", kimlik, "K1", y=_y("H2", 1)),
        "rol": _seri("H2", kimlik, "K2"),
        "capa": _seri("H1", kimlik, "olay", capa=t - H4),
        "capa2": _seri("H1", kimlik, "olay", capa=t - 2 * H4),
        "ufuk": _seri("H2", kimlik, "K1", ufuk=6),
    }
    anahtarlar = [a for a in pozisyon._SERI_BELLEGI]
    assert len(anahtarlar) == len(set(anahtarlar)) >= len(seriler)
    assert len({id(s) for s in seriler.values()}) == len(seriler)
    temel = seriler["temel"].kimlik
    assert temel[0] == "KESIF" and temel[1] == kimlik["sembol"] and temel[2] == 0      # kume, sembol, donem
    for ad, s in seriler.items():
        if ad != "temel":
            assert s.kimlik != temel, ad
    # Anahtar donem isaretini de tasir.
    assert all(a[-1] == kume_bellegi.donem_isareti() for a in anahtarlar)
    assert _seri("H2", kimlik, "K1") is seriler["temel"]


def test_G11_ikincil_ufuk_birincil_serinin_satirini_okumaz(dunya_g1):
    kimlik, _ = dunya_g1
    birincil = _seri("H2", kimlik, "K1")
    ikincil = _seri("H2", kimlik, "K1", ufuk=6)
    sinandi = 0
    for t in birincil.zamanlar()[::5]:
        a, b = _seri_sonucu(birincil, t), _seri_sonucu(ikincil, t)
        if isinstance(a, pozisyon.OnaylanmisPozisyon) and isinstance(b, pozisyon.OnaylanmisPozisyon):
            assert a.plan.ufuk == 18 and b.plan.ufuk == 6 and a is not b
            assert ayni(b, karar_cagrisi(ref, "H2", kimlik, t, ufuk=6))
            sinandi += 1
        elif isinstance(a, BaseException):
            assert ayni(a, b), "birincil ufukta reddedilen bar ikincilde ayni retle doner"
    assert sinandi > 10


def test_G11_her_okumada_erisim_denetimi_calisir(dunya_g1, monkeypatch):
    kimlik, _ = dunya_g1
    seri = _seri("H2", kimlik, "K1")
    t = seri.zamanlar()[200]
    sayac = {"kesif": 0, "onay": 0, "grup": 0, "erisim": 0}
    asil = (split.kesif_baglami_dogrula, split.onay_baglami_dogrula, pozisyon.grup_dogrula, split.onay_erisimi_denetle)

    def say(ad, f):
        def g(*a, **k):
            sayac[ad] += 1
            return f(*a, **k)
        return g

    _split_vekili(monkeypatch, kesif_baglami_dogrula=say("kesif", asil[0]), onay_baglami_dogrula=say("onay", asil[1]),
                  onay_erisimi_denetle=say("erisim", asil[3]))
    monkeypatch.setattr(pozisyon, "grup_dogrula", say("grup", asil[2]))
    for n in range(1, 4):
        _seri_sonucu(seri, t)
        assert all(v == n for v in sayac.values()), sayac

    class Yasak(PermissionError):
        pass

    def yasak(kume):
        raise Yasak("baglam yok")

    _split_vekili(monkeypatch, kesif_baglami_dogrula=yasak)
    for okuma in (lambda: seri.icerir(t), lambda: seri.sonuc(t), lambda: seri.zamanlar(), lambda: seri.onay_bitleri(),
                  lambda: seri.pozisyon(t)):
        with pytest.raises(Yasak):
            okuma()


def test_G11_seri_nesnesi_elle_kurulamaz_ve_degistirilemez(dunya_g1):
    import copy
    import pickle

    kimlik, _ = dunya_g1
    seri = _seri("H2", kimlik, "K1")
    with pytest.raises(TypeError):
        pozisyon.KapiSerisi(object(), None, (), 0, pd.DatetimeIndex([], tz="UTC"), ())
    with pytest.raises(AttributeError):
        seri._KapiSerisi__sonuclar = ()
    with pytest.raises(AttributeError):
        del seri._KapiSerisi__sonuclar
    with pytest.raises(TypeError):
        pickle.dumps(seri)
    assert copy.copy(seri) is seri and copy.deepcopy(seri) is seri
    # Satir bellek duzeyinde degistirilirse (kararli atlatma) imza okumayi reddeder.
    t = seri.zamanlar()[150]
    sonuclar = list(seri._KapiSerisi__sonuclar)
    i = seri._KapiSerisi__sira[int(t.value)]
    sonuclar[i] = ("ret", pozisyon.UygunDegil, ("sahte",))
    object.__setattr__(seri, "_KapiSerisi__sonuclar", tuple(sonuclar))
    with pytest.raises(ValueError, match="imza"):
        seri.sonuc(t)


# --- G13 vaka 2: birincil ufuk ve funding tolerans payi kume sonunu asar ------------------------------------------------

def test_G13_2_birincil_ufuk_ve_funding_tolerans_payi_kume_sonunu_asar():
    """KESIF sonu (2025-08-31 23:59:59) etrafinda veri ve funding kume sonundan SONRA da var. KESIF'in son barlari:
    birincil ufkun cikisi kume sonunu asan barlar `KumeSiniriHatasi`; funding pencere sonu kume sonuna tolerans
    payiyla denk gelir. Her rolde, son 60 barda kapi skalerle birebir ayni; kume siniri reddi gorulmeli."""
    kimlik, _ = dunya(614, "2025-03-01", "2025-10-31 20:00")
    m, f = SENTETIK_VERI[kimlik["sembol"]]
    kume_sonu = U("2025-08-31 23:59:59")
    assert (pd.DatetimeIndex(m["open_time"]) > kume_sonu).any() and (pd.DatetimeIndex(f["odeme_zamani"]) > kume_sonu).any()
    siniflar = set()
    for hipotez in ("H2", "H3"):
        izgara = _izgara(hipotez, kimlik)
        assert izgara[-1] <= kume_sonu
        for rol in ("olay", "K1", "K2"):
            seri = _seri(hipotez, kimlik, rol)
            for t in izgara[-60:]:
                r = karar_cagrisi(ref, hipotez, kimlik, t, rol=rol)
                assert ayni(_seri_sonucu(seri, t), r) and ayni(karar_cagrisi(pozisyon, hipotez, kimlik, t, rol=rol), r)
                siniflar.add(type(r).__name__)
    assert "KumeSiniriHatasi" in siniflar and "OnaylanmisPozisyon" in siniflar, siniflar


# --- G19: ret gerekcesinin onceligi --------------------------------------------------------------------------------

def test_G19_birden_cok_ret_sebebi_olan_barda_skalerin_ilk_sebebi():
    """Donem basinda uc sebep ayni barda birlikte: capasiz pencere eksik (ilk ~5 gun), listeleme yasi < 30 gun ve
    funding'siz donem (tablodaki bayrak; dunyanin funding kayitlari pencereleri yine besler). Kapi skalerin ILK
    sebebini, ayni mesajla verir: sinyal tamligi -> uygunluk -> funding. Kurulum sebeplerin birlikte oldugunu bagimsiz
    olarak sinar (yas ve bayrak). Olay rolunde ayni barlar: sinyal tamligi ve kosul uygunluktan once."""
    kimlik, _ = dunya(615, BAS, BITIS, funding_gec_gun=0, funding_yok=True)
    bas, _, funding_yok = pozisyon.donem_kaydi(kimlik["sembol"], 0)
    assert funding_yok is True
    gorulen = {}
    for rol in ("K1", "K2", "olay"):
        seri = _seri("H2", kimlik, rol)
        for t in seri.zamanlar():
            if (t - bas) / pd.Timedelta(days=1) >= 40:
                break
            r = karar_cagrisi(ref, "H2", kimlik, t, rol=rol)
            assert ayni(_seri_sonucu(seri, t), r) and ayni(karar_cagrisi(pozisyon, "H2", kimlik, t, rol=rol), r)
            assert not isinstance(r, pozisyon.OnaylanmisPozisyon)
            yas_kucuk = (t - bas) / pd.Timedelta(days=1) < config.ASGARI_LISTELEME_YASI_GUN
            gorulen.setdefault((rol, type(r).__name__), yas_kucuk)
    for rol in ("K1", "K2"):
        assert gorulen[(rol, "SinyalPenceresiTamDegil")] is True       # uc sebep birlikte, ilki tamlik
        assert gorulen[(rol, "UygunDegil")] is True                    # yas ve funding'siz donem birlikte, ilki uygunluk
        assert (rol, "FundingTamDegil") in gorulen                     # yas >= 30: yalnizca funding
    assert ("olay", "SinyalPenceresiTamDegil") in gorulen


# --- S-19: plan onbellegi tutarsizligi ------------------------------------------------------------------------------

def test_S19_plan_onbellegi_tutarsizligi_seriyi_durdurur(dunya_g1):
    kimlik, _ = dunya_g1
    seri = _seri("H2", kimlik, "K1")
    onayli = [t for t, b in zip(seri.zamanlar(), seri.onay_bitleri()) if b][:2]
    t1, t2 = onayli
    bas, bitis, _ = pozisyon.donem_kaydi(kimlik["sembol"], 0)
    kb, ks = pozisyon.kume_sinirlari("KESIF")
    plan_serisi = pozisyon._karar_girdisi(kimlik["sembol"], "KESIF", kume_baslangic=kb, kume_bitis=ks,
                                          donem_baslangic=bas, donem_bitis=bitis)[3]
    a1, a2 = ((config.BAR_4H, 18, 18, t) for t in (t1, t2))
    plan_serisi._harita[a1] = plan_serisi._harita[a2]
    pozisyon._seri_bellegini_temizle()          # yalnizca seri onbellegi; plan onbellegi bozuk kalir
    with pytest.raises(ValueError, match="Plan onbellegi tutarsiz"):
        _seri("H2", kimlik, "K1")
    assert isinstance(karar_cagrisi(pozisyon, "H2", kimlik, t1), ValueError)


# --- Taramalar -----------------------------------------------------------------------------------------------------

KARAR_ADIMLARI = {"pozisyon_plani", "uygunluk_karari", "uygunluk", "capasiz_pencere_degerleri", "capasiz_pencereler",
                  "sinyal_degerleri", "kosullar_saglandi", "_kosul_dizisi", "_olay_degerleri", "gecersizlik_seviyesi",
                  "_gecersizlik_tabani", "_pozisyon_tamlik_satiri", "_planlar_tamlik_satirlari", "_satirdan_toplam",
                  "pozisyon_funding_ayrintisi", "_mae_tepesi", "OnaylanmisPozisyon", "_kapi_satirlari"}

# (modul, fonksiyon) -> izin gerekcesi. Bunun disinda `data/` icinde (dondurulmus referans haric) kapinin ic adimini
# cagiran fonksiyon yoktur.
IZINLI_CAGIRANLAR = {
    ("pozisyon", "_kapi_satirlari"): "TEK karar cekirdegi",
    ("pozisyon", "olay_karari"): "ince sarmalayici: cekirdegin tek bar kosusu (G10, izgara disi t)",
    ("pozisyon", "kapi_serisi"): "seri kurulumu: cekirdegi cagirir",
    ("pozisyon", "kur"): "`kapi_serisi` icindeki kurulum kapanisi (ayni fonksiyonun parcasi)",
    ("pozisyon", "_olay_kosulu_serisi"): "esitlik betigi icin vektorel kosul (G1 istisnasi, karar vermez)",
    ("pozisyon", "sinyal_kosulu"): "G1 gecici istisnasi: skaler kosul (dizi kurallari, P2c'ye kadar)",
    ("pozisyon", "_test_onayi"): "test dikisi (yalnizca pytest icinde; ONAY_ATLATMA_DESENI)",
    ("pozisyon", "mae"): "getiri tarafi: onayli pozisyonun MAE'si (karar degil)",
    ("pozisyon", "_mae_tepesi"): "kendi tanimi",
    ("funding", "pozisyon_funding_tam_mi"): "funding ic adimi (skaler yardimci)",
    ("funding", "_plan_fundingi"): "funding ic adimi (getiri tarafinin yeniden hesabi)",
    ("funding", "_pozisyon_tamlik_satiri"): "toplu yolun n = 1 durumu (kendi modulu)",
    ("eligibility", "uygun_mu"): "eligibility ic sarmalayicisi (kendi modulu)",
}


def _cagiranlar() -> set[tuple[str, str]]:
    bulunan = set()
    for yol in sorted((KOK / "data").glob("*.py")):
        if yol.name == "_skaler_referans.py":
            continue
        agac = ast.parse(yol.read_text(encoding="utf-8"))
        for fonk in [d for d in ast.walk(agac) if isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            for d in ast.walk(fonk):
                if isinstance(d, ast.Call):
                    f = d.func
                    ad = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
                    if ad in KARAR_ADIMLARI and ad != fonk.name:
                        bulunan.add((yol.stem, fonk.name))
    return bulunan


def test_tarama_data_icinde_ikinci_karar_yolu_yok():
    """`data/` icinde kapinin ic adimlarini (plan, pencereler, kosul, uygunluk, funding tamligi ve toplami, fiyat ve
    MAE, onayli pozisyon kurulumu) cagiran her fonksiyon acik izin listesindedir; liste disi cagiran ikinci bir karar
    yoludur. Bar basina skaler karar govdesi yalnizca dondurulmus referansta yasar (G1)."""
    bulunan = _cagiranlar()
    assert bulunan - set(IZINLI_CAGIRANLAR) == set(), sorted(bulunan - set(IZINLI_CAGIRANLAR))
    assert ("pozisyon", "_kapi_satirlari") in bulunan
    # olay_karari bar basina adim CAGIRMAZ; yalnizca seriyi ve cekirdegi cagirir.
    kaynak = (KOK / "data" / "pozisyon.py").read_text(encoding="utf-8")
    tanim = next(d for d in ast.walk(ast.parse(kaynak)) if isinstance(d, ast.FunctionDef) and d.name == "olay_karari")
    cagrilan = {(d.func.attr if isinstance(d.func, ast.Attribute) else getattr(d.func, "id", None))
                for d in ast.walk(tanim) if isinstance(d, ast.Call)}
    assert cagrilan & KARAR_ADIMLARI == {"_kapi_satirlari"}, cagrilan & KARAR_ADIMLARI


def test_tarama_seri_kurucu_yalnizca_pozisyondan_ice_aktarilir():
    aktaranlar = set()
    for yol in sorted((KOK / "data").glob("*.py")):
        if yol.name == "seri_kurucu.py":
            continue
        for d in ast.walk(ast.parse(yol.read_text(encoding="utf-8"))):
            if isinstance(d, ast.ImportFrom) and (d.module == "data.seri_kurucu"
                                                  or (d.module == "data" and any(a.name == "seri_kurucu"
                                                                                 for a in d.names))):
                aktaranlar.add(yol.name)
            elif isinstance(d, ast.Import) and any(a.name == "data.seri_kurucu" for a in d.names):
                aktaranlar.add(yol.name)
    assert aktaranlar == {"pozisyon.py"}, aktaranlar


def test_tarama_analiz_kodunda_seri_kapi_ic_adlari_yasak(tmp_path):
    from tarama_yardimcisi import CIKIS_KAPI_DISI_DESENI, ihlaller

    (tmp_path / "study").mkdir()
    for ad, icerik in (("a.py", "pozisyon._kapi_satirlari(b, z)\n"), ("b.py", "x = pozisyon._olay_kosulu_serisi(h)\n"),
                       ("c.py", "pozisyon._kosul_dizisi(h, y, d)\n"), ("d.py", "pozisyon._SERI_GIZLI\n"),
                       ("e.py", "s._KapiSerisi__sonuclar\n")):
        (tmp_path / "study" / ad).write_text(icerik, encoding="utf-8")
    (tmp_path / "study" / "temiz.py").write_text("s = pozisyon.kapi_serisi(h, y, 'K1', kume=k, sembol=s, "
                                                 "donem_no=0)\n", encoding="utf-8")
    assert ihlaller(CIKIS_KAPI_DISI_DESENI, kok=tmp_path) == [f"study/{x}.py" for x in "abcde"]
