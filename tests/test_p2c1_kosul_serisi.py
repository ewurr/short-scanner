"""P2c-1: kosul serisi (`pozisyon.kosul_serisi`) -- dizi kurallarinin okudugu sinyal kosulu, kapinin olay rolundeki
kosulla ayni kaynaktan (tasarim notu `p2c1_tasarim.md` §5, kararlar `p2c1_kararlar.md` A3, A4).

Her deger dondurulmus skaler referansla (`data._skaler_referans.sinyal_kosulu`) karsilastirilir: deger ve TUR (`True` /
`False` / `None`), hata ise SINIF ve MESAJ. Deger, olay sayisi ve kosulun dogru oldugu bar sayisi yazilmaz; testler
yalnizca iki yolun ayni oldugunu ve korumalarin calistigini denetler. Sentetik dunya `esitlik_yardimcisi.dunya`dir
(eksik barlar, bozuk hucreli bar, enjekte pump ve kirilim kesitleri). Test adlari gereksinim koduyla baslar. Aga cikmaz.
"""

from __future__ import annotations

import ast
import copy
import pickle

import numpy as np
import pandas as pd
import pytest

import config
from data import _skaler_referans as ref
from data import kume_bellegi, pencere, pozisyon, sinyal
from esitlik_yardimcisi import H4, dunya, karar_cagrisi
from kapi_yardimcisi import SENTETIK_DONEMLER, SENTETIK_VERI, veri
from tarama_yardimcisi import KOK

BAS, BITIS = "2021-01-01", "2021-08-31 20:00"
U = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731


# --- Yardimcilar ---------------------------------------------------------------------------------------------------

def _cagir(f, *a, **k):
    try:
        return f(*a, **k)
    except Exception as hata:  # noqa: BLE001 - sinif ve mesaj karsilastirilir
        return hata


def ayni(a, b) -> bool:
    """Hata: ayni sinif VE ayni mesaj. Kosul: ayni deger ve ayni tur (True / False / None)."""
    if isinstance(a, BaseException) or isinstance(b, BaseException):
        return type(a) is type(b) and str(a) == str(b)
    return type(a) is type(b) and a == b


def _y(hipotez, i=0):
    return dict(sinyal.izgara(hipotez)[i])


def _izgara(hipotez, kimlik):
    return pozisyon.hipotez_izgarasi_barlari(hipotez, kume="KESIF", **kimlik)


def seri_degeri(hipotez, kimlik, t, y, capa=None):
    """Kosul serisinin t degeri (kurulum ya da okuma hatasi nesne olarak doner)."""
    return _cagir(lambda: pozisyon.kosul_serisi(hipotez, y, kume="KESIF", **kimlik, capa=capa).deger(t))


def ref_degeri(hipotez, kimlik, t, y, capa=None):
    return _cagir(ref.sinyal_kosulu, t, hipotez=hipotez, yapilandirma=y, capa=capa, kume="KESIF", **kimlik)


def _esit(hipotez, kimlik, t, y, capa=None):
    a, b = seri_degeri(hipotez, kimlik, t, y, capa), ref_degeri(hipotez, kimlik, t, y, capa)
    assert ayni(a, b), (hipotez, t, capa, repr(a)[:120], repr(b)[:120])
    return a


def _turetilmis(kimlik, *, bozan=None, dus=()):
    """Ayni donemle yeni bir sentetik sembol: 4h cercevesi `bozan(m)` ile degistirilir, `dus` barlari cikarilir."""
    m, f = SENTETIK_VERI[kimlik["sembol"]]
    b, s, fy = SENTETIK_DONEMLER[(kimlik["sembol"], 0)]
    m = m.copy()
    if bozan is not None:
        bozan(m)
    if dus:
        m = m.loc[~pd.DatetimeIndex(m["open_time"]).isin(pd.DatetimeIndex(dus))].reset_index(drop=True)
    return veri(m, f.copy(), b, s, ham=True, funding_yok=fy)


@pytest.fixture
def dunya_k():
    return dunya(621, BAS, BITIS)


# --- Sentetik esitlik: her bar, her hipotez -------------------------------------------------------------------------

@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_esitlik_izgaranin_butun_barlari_capasiz(dunya_k, hipotez):
    """Izgaranin BUTUN barlari, ilk yapilandirma, `capa=None` (H1'de pump kosulu). Kurulum: uc deger birlikte gorulur."""
    kimlik, _ = dunya_k
    y = _y(hipotez)
    gorulen = set()
    for t in _izgara(hipotez, kimlik):
        gorulen.add(repr(_esit(hipotez, kimlik, t, y)))
    assert {"True", "False", "None"} <= gorulen or (hipotez == "H3" and len(gorulen) >= 2 and "None" in gorulen), \
        gorulen


def test_esitlik_H1_teyit_capa_sinirlari(dunya_k):
    """H1 p capali teyit kosulu: pump barlari ve izgaradan secilen capalar, d in {1, 3, 5, 8, 12, 13} (13 tanimsiz:
    skalerde `TepePenceresiKurulamaz -> None`) ve 0 (pump barinin kendisi). Ilk ve son yapilandirma."""
    kimlik, ozel = dunya_k
    izgara = _izgara("H1", kimlik)
    capalar = list(ozel["pump"]) + [izgara[i] for i in range(200, len(izgara), 97)]
    gorulen = set()
    for y in (_y("H1", 0), _y("H1", -1)):
        for p in capalar:
            for d in (0, 1, 3, 5, 8, 12, 13):
                gorulen.add(repr(_esit("H1", kimlik, p + d * H4, y, capa=p)))
    assert {"True", "False", "None"} <= gorulen, gorulen


@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_esitlik_butun_yapilandirmalar_ornek_barlarda(dunya_k, hipotez):
    """Hipotezin BUTUN yapilandirmalari; tohumlu ornek barlar + enjekte kesitler (H1'de pump ve teyit)."""
    kimlik, ozel = dunya_k
    izgara = _izgara(hipotez, kimlik)
    rng = np.random.default_rng(6201)
    barlar = [izgara[i] for i in sorted(rng.choice(len(izgara), size=min(30, len(izgara)), replace=False))]
    if hipotez == "H2":
        barlar += list(ozel["h2"])
    for y in (dict(x) for x in sinyal.izgara(hipotez)):
        for t in barlar:
            _esit(hipotez, kimlik, t, y)
        if hipotez == "H1":
            for p in ozel["pump"][:3]:
                _esit("H1", kimlik, p, y)
                for d in (1, 4, 12):
                    _esit("H1", kimlik, p + d * H4, y, capa=p)


@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
@pytest.mark.parametrize("ad", ["kesif_sonu", "kesif_basi"])
def test_G13_kume_sinirinin_iki_yani(hipotez, ad):
    """Kume sinirini kesen donemler (G13): sinirin iki yanindaki barlar (kume disi barlar dahil)."""
    tohum, bas, bitis = {"kesif_sonu": (622, "2025-01-01", "2025-11-26 20:00"),
                         "kesif_basi": (623, "2019-06-01", "2020-04-26 20:00")}[ad]
    kimlik, ozel = dunya(tohum, bas, bitis)
    y = _y(hipotez)
    adim = pencere.adim(config.HIPOTEZ_IZGARASI[hipotez])
    sinir = pd.Timestamp(config.KESIF_SONU if ad == "kesif_sonu" else config.KESIF_BASI).floor("D")
    barlar = [sinir + i * adim for i in range(-25, 26)]
    for t in barlar:
        _esit(hipotez, kimlik, t, y)
    izgara = _izgara(hipotez, kimlik)
    assert len(izgara) and (izgara.min() >= pd.Timestamp(config.KESIF_BASI)) and (izgara.max() <= pd.Timestamp(config.KESIF_SONU))
    if hipotez == "H1":
        for p in izgara[-14:-1] if ad == "kesif_sonu" else izgara[:3]:
            for d in (1, 6, 12):
                _esit("H1", kimlik, p + d * H4, y, capa=p)


# --- Kararlar A4: serinin satiri olmayan t ---------------------------------------------------------------------------

@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_A4_satiri_olmayan_t_dort_durum_ve_tolerans(dunya_k, hipotez):
    """Kararlar A4: (1) izgarada olmayan hizali bar (donem ici bosluk), (2) hizasiz t (02:00), (3) saat dilimsiz t,
    (4) UTC olmayan t; ayrica tolerans payli t ve donem disi t. Seri ve skaler AYNI sonucu (deger ya da sinif + mesaj)
    verir. t'nin dogrulanmasi veriden ONCE gelir: (3) TypeError, (4) ValueError."""
    kimlik, _ = dunya_k
    y = _y(hipotez)
    bas, bitis, _ = pozisyon.donem_kaydi(kimlik["sembol"], 0)
    izgara = _izgara(hipotez, kimlik)
    adim = pencere.adim(config.HIPOTEZ_IZGARASI[hipotez])
    bosluk = bas + pd.Timedelta(days=61)                         # 60-63. gun bosluk (4h ve 1d)
    assert bosluk not in set(izgara)
    durumlar = {
        "bosluk": bosluk,
        "hizasiz": bas + pd.Timedelta(days=100, hours=2),
        "saat_dilimsiz": pd.Timestamp("2021-03-01 00:00"),
        "utc_degil": pd.Timestamp("2021-03-01 03:00", tz="Europe/Istanbul"),
        "tolerans": izgara[len(izgara) // 2] + pd.Timedelta(seconds=30),
        "donem_once": bas - 3 * adim,
        "donem_sonra": bitis + adim,
    }
    if hipotez == "H3":
        # Kararlar A4, skalerle TUTMAYAN tek durum: 1d'de tolerans payli t. Skaler `None`, seri kuruculari gun acilisi
        # olmayan zamani reddeder; kosul serisi bu durumu kapali yonde `KeyError` ile durdurur (rapora yazildi).
        t = durumlar.pop("tolerans")
        assert ref_degeri(hipotez, kimlik, t, y) is None
        assert type(seri_degeri(hipotez, kimlik, t, y)) is KeyError
    sonuc = {ad: _esit(hipotez, kimlik, t, y) for ad, t in durumlar.items()}
    assert type(sonuc["saat_dilimsiz"]) is TypeError
    assert type(sonuc["utc_degil"]) is ValueError
    assert sonuc["bosluk"] is None and sonuc["hizasiz"] is None
    if hipotez == "H1":
        p = izgara[400]
        for ad, t in {"bosluk_teyit": bosluk, "pencere_disi": p + 20 * H4, "tolerans_teyit": p + 3 * H4 +
                      pd.Timedelta(seconds=30)}.items():
            _esit("H1", kimlik, t, y, capa=p if ad != "bosluk_teyit" else bosluk - 2 * H4)


def test_A4_capa_dizisi_kipinde_satir_disi_t_kapali_yon(dunya_k):
    kimlik, _ = dunya_k
    izgara = _izgara("H1", kimlik)
    capa = pd.DatetimeIndex([t - H4 for t in izgara])
    seri = pozisyon.kosul_serisi("H1", _y("H1"), kume="KESIF", **kimlik, capa=capa)
    with pytest.raises(KeyError):
        seri.deger(izgara[10] + pd.Timedelta(seconds=30))


def test_capa_H2_H3_de_verilemez_skalerle_ayni_sinif(dunya_k):
    """Kararlar B 11: H2 ve H3'te capa skalerle ayni sinifla (`ValueError`) reddedilir."""
    kimlik, _ = dunya_k
    for h in ("H2", "H3"):
        t = _izgara(h, kimlik)[100]
        a = seri_degeri(h, kimlik, t, _y(h), capa=t - H4)
        b = ref_degeri(h, kimlik, t, _y(h), capa=t - H4)
        assert type(a) is type(b) is ValueError and str(a) == str(b)


# --- G10: hata seriyi durdurur ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_G10_bozuk_fiyat_seriyi_durdurur_skalerin_ilk_bozuk_bariyla_ayni_mesaj(hipotez):
    """Sifir kapanis (bozuk veri): kosul serisi kurulumu `VeriHatasi` ile durur; mesaj skalerin ILK bozuk barindaki
    mesajla aynidir. Hata seri bellegine yazilmaz; ayni anahtar ayni hatayi yeniden yukseltir (`_SERI_HATALARI`).
    Hedef bar dunyanin bosluk ve bozuk hucrelerinden uzaktir (pencereler tam; 330 gunluk donem)."""
    kimlik, _ = dunya(625, "2021-01-01", "2021-11-26 20:00")
    izgara = _izgara(hipotez, kimlik)
    hedef = izgara[int(len(izgara) * 0.85)]

    def bozan(m):
        z = pd.DatetimeIndex(m["open_time"])
        if hipotez == "H3":
            m.loc[(z >= hedef) & (z < hedef + pd.Timedelta(days=1)), "close"] = 0.0
        else:
            m.loc[z == hedef, "close"] = 0.0

    yeni = _turetilmis(kimlik, bozan=bozan)
    y = _y(hipotez)
    kume_bellegi.temizle()
    with pytest.raises(pencere.VeriHatasi) as hata:
        pozisyon.kosul_serisi(hipotez, y, kume="KESIF", **yeni)
    assert not [a for a in pozisyon._SERI_BELLEGI if a[0] == "kosul_serisi"]
    hatalar = [a for a in pozisyon._SERI_HATALARI if a[0] == "kosul_serisi"]
    assert len(hatalar) == 1
    with pytest.raises(pencere.VeriHatasi) as ikinci:
        pozisyon.kosul_serisi(hipotez, y, kume="KESIF", **yeni)
    assert ikinci.value is hata.value
    yeni_izgara = _izgara(hipotez, yeni)
    # G16: hedeften once hicbir barin degeri hedefin kapanisina bakmaz; arama hedefin bir adim oncesinden baslar.
    ilk = next(t for t in yeni_izgara if t >= hedef - pencere.adim(config.HIPOTEZ_IZGARASI[hipotez])
               and isinstance(ref_degeri(hipotez, yeni, t, y), pencere.VeriHatasi))
    assert str(ref_degeri(hipotez, yeni, ilk, y)) == str(hata.value)
    # Skaler bozuk olmayan barda karar verir; seri birimi durdurur (G10, bilinen kapsam farki; tasarim 5.6).
    assert not isinstance(ref_degeri(hipotez, yeni, yeni_izgara[10], y), BaseException)


def test_G10_OlayOlusmaz_disi_hata_None_a_donmez(dunya_k, monkeypatch):
    kimlik, _ = dunya_k

    def patla(*a, **k):
        raise ZeroDivisionError("bilerek")

    monkeypatch.setattr(pozisyon, "_h1_pump_kosul_dizisi", patla)
    with pytest.raises(ZeroDivisionError):
        pozisyon.kosul_serisi("H1", _y("H1"), kume="KESIF", **kimlik)


# --- G19: ret onceligi --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("hipotez", ["H1", "H2"])
def test_G19_eksik_deger_ve_bozuk_fiyat_ayni_barda_hesaplanamaz(dunya_k, hipotez):
    """Cok sebepli bar: eksik pencere degeri VE bozuk fiyat. Sira skalerle ayni: once tamlik (`None`), pozitiflik
    denetimi yalnizca tam barlarda. Kapinin ret sinifi degismez (`SinyalPenceresiTamDegil`)."""
    kimlik, _ = dunya_k
    izgara = _izgara(hipotez, kimlik)
    k = 500
    hedef = izgara[k]
    dus = [izgara[k - 1]] + ([hedef + 29 * H4] if hipotez == "H2" else [])

    def bozan(m):
        m.loc[pd.DatetimeIndex(m["open_time"]) == hedef, "close"] = 0.0

    yeni = _turetilmis(kimlik, bozan=bozan, dus=dus)
    y = _y(hipotez)
    assert _esit(hipotez, yeni, hedef, y) is None
    if hipotez == "H2":
        assert _esit(hipotez, yeni, hedef + 30 * H4, y) is None
    a = karar_cagrisi(pozisyon, hipotez, yeni, hedef, rol="olay", capa=hedef - H4 if hipotez == "H1" else None)
    b = karar_cagrisi(ref, hipotez, yeni, hedef, rol="olay", capa=hedef - H4 if hipotez == "H1" else None)
    assert type(a) is type(b) and str(a) == str(b)
    assert type(a) is pozisyon.SinyalPenceresiTamDegil


# --- G16: gelecege bakis --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_G16_t_den_sonraki_veri_degisince_t_satiri_degismez(dunya_k, hipotez):
    """t barinin kapanisindan SONRAKI fiyat, hacim, bar varligi ve funding degisince t'ye kadarki satirlar degismez.
    Degistirilen gelecek degerleri gecerli tutulur (G10 yolu G16'nin konusu degildir; tasarim 5.7). H1'de capasiz ve
    capali seri."""
    kimlik, _ = dunya_k
    izgara = _izgara(hipotez, kimlik)
    t = izgara[int(len(izgara) * 0.6)]
    kesim = t + pencere.adim(config.HIPOTEZ_IZGARASI[hipotez])
    m, f = SENTETIK_VERI[kimlik["sembol"]]
    b, s, fy = SENTETIK_DONEMLER[(kimlik["sembol"], 0)]
    m2, f2 = m.copy(), f.copy()
    z = pd.DatetimeIndex(m2["open_time"])
    gelecek = z >= kesim
    for alan in ("open", "high", "low", "close"):
        m2.loc[gelecek, alan] = m2.loc[gelecek, alan] * 1.9
    m2.loc[gelecek, "quote_volume"] = m2.loc[gelecek, "quote_volume"] * 13.0
    m2 = m2.loc[~(gelecek & (np.arange(len(m2)) % 7 == 0))].reset_index(drop=True)      # gelecekte bar varligi
    f2.loc[pd.DatetimeIndex(f2["odeme_zamani"]) > kesim, "oran"] = 0.05
    f2["oran_8h"] = f2["oran"] * 8.0 / f2["aralik_saat"]
    yeni = veri(m2, f2, b, s, ham=True, funding_yok=fy)
    y = _y(hipotez)
    gecmis = [x for x in izgara if x <= t]
    for capa in ([None] + ([t - 5 * H4, t - 12 * H4] if hipotez == "H1" else [])):
        sa = pozisyon.kosul_serisi(hipotez, y, kume="KESIF", **kimlik, capa=capa)
        sb = pozisyon.kosul_serisi(hipotez, y, kume="KESIF", **yeni, capa=capa)
        zamanlar = [x for x in sa.zamanlar() if x <= t]
        assert zamanlar and zamanlar == [x for x in sb.zamanlar() if x <= t]
        assert [sa.deger(x) for x in zamanlar] == [sb.deger(x) for x in zamanlar]
    assert any(seri_degeri(hipotez, kimlik, x, y) != seri_degeri(hipotez, yeni, x, y)
               for x in izgara if x > kesim + 40 * H4), "kurulum: gelecek degisimi gelecegin kosulunu degistirmeli"
    assert len(gecmis) > 100


# --- G11: seri nesnesi -------------------------------------------------------------------------------------------

def test_G11_kosul_serisi_elle_kurulamaz_degistirilemez_kopyalanamaz(dunya_k):
    kimlik, _ = dunya_k
    seri = pozisyon.kosul_serisi("H2", _y("H2"), kume="KESIF", **kimlik)
    with pytest.raises(TypeError):
        pozisyon.KosulSerisi(object(), None, ("kosul",), 0, pd.DatetimeIndex([], tz="UTC"), (), None)
    for ad in ("_KosulSerisi__degerler", "_KosulSerisi__sira", "baska"):
        with pytest.raises(AttributeError):
            setattr(seri, ad, ())
    with pytest.raises(AttributeError):
        del seri._KosulSerisi__degerler
    with pytest.raises(TypeError):
        pickle.dumps(seri)
    assert copy.copy(seri) is seri and copy.deepcopy(seri) is seri
    assert seri.kimlik[0] == "kosul"
    # Satir bellek duzeyinde degistirilirse (kararli atlatma) imza okumayi reddeder.
    t = seri.zamanlar()[150]
    degerler = list(seri._KosulSerisi__degerler)
    i = seri._KosulSerisi__sira[int(t.value)]
    degerler[i] = not degerler[i] if degerler[i] is not None else True
    object.__setattr__(seri, "_KosulSerisi__degerler", tuple(degerler))
    with pytest.raises(ValueError, match="imza"):
        seri.deger(t)


def test_G11_S_P2b2_1_karsiligi_sira_haritasi_baska_satiri_donduremez(dunya_k):
    """S-P2b2-1'in kosul serisindeki karsiligi (tasarim 5.4): sira haritasi baska bir satira yonlendirilirse okunan
    satirin KENDI zamani sorulan t ile tutmaz ve okuma reddedilir."""
    kimlik, _ = dunya_k
    seri = pozisyon.kosul_serisi("H2", _y("H2"), kume="KESIF", **kimlik)
    z = seri.zamanlar()
    sira = dict(seri._KosulSerisi__sira)
    sira[int(z[100].value)] = sira[int(z[101].value)]
    from types import MappingProxyType
    object.__setattr__(seri, "_KosulSerisi__sira", MappingProxyType(sira))
    with pytest.raises(ValueError, match="sira haritasi"):
        seri.deger(z[100])


def test_G11_kosu_acilisi_kapanisi_eski_seriyi_okutmaz(dunya_k):
    kimlik, _ = dunya_k
    seri = pozisyon.kosul_serisi("H1", _y("H1"), kume="KESIF", **kimlik)
    t = seri.zamanlar()[300]
    seri.deger(t)
    kume_bellegi.temizle()
    for okuma in (lambda: seri.deger(t), lambda: seri.icerir(t), lambda: seri.zamanlar(), lambda: len(seri)):
        with pytest.raises(pozisyon.SeriEskidi):
            okuma()
    assert pozisyon.kosul_serisi("H1", _y("H1"), kume="KESIF", **kimlik) is not seri


def test_G11_her_okumada_erisim_denetimi(dunya_k, monkeypatch):
    kimlik, _ = dunya_k
    seri = pozisyon.kosul_serisi("H2", _y("H2"), kume="KESIF", **kimlik)
    t = seri.zamanlar()[200]
    sayac = []
    asil = pozisyon._seri_erisimi_denetle
    monkeypatch.setattr(pozisyon, "_seri_erisimi_denetle", lambda *a: (sayac.append(1), asil(*a))[1])
    for n in range(1, 4):
        seri.deger(t)
        assert len(sayac) == n

    class Yasak(PermissionError):
        pass

    def yasak(*a):
        raise Yasak("baglam yok")

    monkeypatch.setattr(pozisyon, "_seri_erisimi_denetle", yasak)
    for okuma in (lambda: seri.deger(t), lambda: seri.icerir(t), lambda: seri.zamanlar(), lambda: len(seri)):
        with pytest.raises(Yasak):
            okuma()


def test_G11_anahtar_alanlari_ve_kapi_anahtarlarindan_ayrimi(dunya_k):
    """Anahtar `("kosul_serisi", kume, sembol, donem, hipotez, yapilandirma, capa, bar, isaret)`; her alan ayri girdi;
    kapi serisiyle ayni birim cakismaz; ayni istek ayni nesneyi doner. Ufuk alani yoktur (kararlar B 4)."""
    kimlik, _ = dunya_k
    kimlik2, _ = dunya(624, BAS, BITIS)
    kume_bellegi.temizle()
    p = _izgara("H1", kimlik)[300]
    seriler = {
        "temel": pozisyon.kosul_serisi("H2", _y("H2"), kume="KESIF", **kimlik),
        "sembol": pozisyon.kosul_serisi("H2", _y("H2"), kume="KESIF", **kimlik2),
        "hipotez": pozisyon.kosul_serisi("H3", _y("H3"), kume="KESIF", **kimlik),
        "yapilandirma": pozisyon.kosul_serisi("H2", _y("H2", 1), kume="KESIF", **kimlik),
        "pump": pozisyon.kosul_serisi("H1", _y("H1"), kume="KESIF", **kimlik),
        "capa": pozisyon.kosul_serisi("H1", _y("H1"), kume="KESIF", **kimlik, capa=p),
        "capa2": pozisyon.kosul_serisi("H1", _y("H1"), kume="KESIF", **kimlik, capa=p + H4),
    }
    kapi = pozisyon.kapi_serisi("H2", _y("H2"), "olay", kume="KESIF", **kimlik)
    anahtarlar = [a for a in pozisyon._SERI_BELLEGI if a[0] == "kosul_serisi"]
    assert len(anahtarlar) == len(set(anahtarlar)) == len(seriler)
    assert len({id(s) for s in seriler.values()} | {id(kapi)}) == len(seriler) + 1
    assert all(len(a) == 9 and a[-1] == kume_bellegi.donem_isareti() for a in anahtarlar)
    assert pozisyon.kosul_serisi("H2", _y("H2"), kume="KESIF", **kimlik) is seriler["temel"]
    # Tek capali seri: satirlar kapinin tek capa kurali (izleme penceresinin izgara barlari).
    assert list(seriler["capa"].zamanlar()) == list(pozisyon.kapi_serisi(
        "H1", _y("H1"), "olay", kume="KESIF", **kimlik, capa=p).zamanlar())


def test_G11_onbellekten_baska_tur_ya_da_kimlik_donerse_reddedilir(dunya_k):
    kimlik, _ = dunya_k
    seri = pozisyon.kosul_serisi("H2", _y("H2"), kume="KESIF", **kimlik)
    anahtar = next(a for a in pozisyon._SERI_BELLEGI if a[0] == "kosul_serisi")
    baska = pozisyon.kosul_serisi("H2", _y("H2", 1), kume="KESIF", **kimlik)
    pozisyon._SERI_BELLEGI[anahtar] = baska
    with pytest.raises(ValueError, match="tutarsiz"):
        pozisyon.kosul_serisi("H2", _y("H2"), kume="KESIF", **kimlik)
    pozisyon._SERI_BELLEGI[anahtar] = pozisyon.kapi_serisi("H2", _y("H2"), "olay", kume="KESIF", **kimlik)
    with pytest.raises(ValueError, match="tutarsiz"):
        pozisyon.kosul_serisi("H2", _y("H2"), kume="KESIF", **kimlik)
    assert seri.kimlik[0] == "kosul"


# --- Kapinin olay rolu tek kaynaktan: kapi ile kosul serisi ayni kosulu okur ---------------------------------------

@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_tek_kaynak_kapinin_kosul_reddi_kosul_serisiyle_tutarli(dunya_k, hipotez):
    """Kapinin olay rolunde `SinyalKosuluSaglanmadi` olan bar kosul serisinde `False`, `SinyalPenceresiTamDegil` olan
    bar `None` (sinyal bari ve plan gecildiyse); onayli bar `True`. Ayni dunya, ayni yapilandirma."""
    kimlik, _ = dunya_k
    izgara = _izgara(hipotez, kimlik)
    capa = pd.DatetimeIndex([t - (1 + i % 12) * H4 for i, t in enumerate(izgara)]) if hipotez == "H1" else None
    kapi = pozisyon.kapi_serisi(hipotez, _y(hipotez), "olay", kume="KESIF", **kimlik, capa=capa)
    kosul = pozisyon.kosul_serisi(hipotez, _y(hipotez), kume="KESIF", **kimlik, capa=capa)
    gorulen = set()
    for t in izgara:
        s = _cagir(kapi.sonuc, t)
        d = kosul.deger(t)
        if isinstance(s, pozisyon.SinyalKosuluSaglanmadi):
            assert d is False
            gorulen.add("False")
        elif isinstance(s, pozisyon.SinyalPenceresiTamDegil):
            assert d is None
            gorulen.add("None")
        elif isinstance(s, pozisyon.OnaylanmisPozisyon):
            assert d is True
    # Bu dunyada H3 kosulu hesaplanabildigi her barda saglaniyor (H3 kesiti); kurulum yalnizca `None`u ister.
    assert ({"False", "None"} if hipotez != "H3" else {"None"}) <= gorulen


# --- Tarama: tek kaynak (G1) ---------------------------------------------------------------------------------------

def _cagri_haritasi(yol) -> dict[str, set[str]]:
    """Fonksiyon adi -> govdesinde (ic ice tanimlar dahil) cagrilan adlar."""
    agac = ast.parse(yol.read_text(encoding="utf-8"))
    harita: dict[str, set[str]] = {}
    for fonk in [d for d in ast.walk(agac) if isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        adlar = harita.setdefault(fonk.name, set())
        for d in ast.walk(fonk):
            if isinstance(d, ast.Call):
                f = d.func
                adlar.add(f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None))
    return harita


def _cagiranlar(harita, ad) -> set[str]:
    return {f for f, adlar in harita.items() if ad in adlar and f != ad}


def test_G1_data_icinde_skaler_kosul_govdesi_kalmadi():
    """G1 (P2c-1 adim 4): `data/` icinde, dondurulmus referans disinda, skaler kosul govdesi TANIMI yok
    (`sinyal_kosulu`, `kosullar_saglandi`, `h1_pump_saglandi`, `h1_pump_degerleri`, `_fiyatlari_dogrula`) ve bu adlar
    hicbir yerden cagrilmaz. Referansin kendi kopyasi yerinde (G2: referans degismez)."""
    yasak = {"sinyal_kosulu", "kosullar_saglandi", "h1_pump_saglandi", "h1_pump_degerleri", "_fiyatlari_dogrula"}
    for yol in sorted((KOK / "data").glob("*.py")):
        if yol.name == "_skaler_referans.py":
            continue
        agac = ast.parse(yol.read_text(encoding="utf-8"))
        tanimlar = {d.name for d in ast.walk(agac) if isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef))}
        assert not tanimlar & yasak, (yol.name, tanimlar & yasak)
        adlar = set().union(*_cagri_haritasi(yol).values()) if _cagri_haritasi(yol) else set()
        assert not adlar & yasak, (yol.name, adlar & yasak)
    assert not hasattr(pozisyon, "sinyal_kosulu")
    for ad in ("kosullar_saglandi", "h1_pump_saglandi", "h1_pump_degerleri", "_fiyatlari_dogrula"):
        assert not hasattr(sinyal, ad), ad
    assert callable(ref.sinyal_kosulu) and callable(ref.kosullar_saglandi) and callable(ref.h1_pump_saglandi)


def test_G1_tek_kaynak_taramasi():
    """Olay rolunun kosulu ile dizi kurallarinin okudugu kosul ayni fonksiyonlardan gelir (tasarim 5.3 madde 5, kararlar
    A3). Tarama AST'ye dayanir, ada baglidir ve dardir (§14.49 D-C6 ile ayni sinir)."""
    harita = _cagri_haritasi(KOK / "data" / "pozisyon.py")
    beklenen = {
        "_kosul_dizisi": {"_olay_kosulu"},
        "_h1_pump_dizisi": {"_kosul_dizisi", "_h1_pump_kosul_dizisi"},
        "_h1_pump_kosul_dizisi": {"_kosul_satirlari"},
        "_fiyat_pozitifligi": {"_kosul_dizisi", "_h1_pump_kosul_dizisi"},
        "_h1_pump_degerleri": {"_olay_degerleri", "_kosul_satirlari"},
        "_olay_degerleri": {"_olay_kosulu"},
        "_olay_kosulu": {"_kapi_satirlari", "_kosul_satirlari"},
        # `kosul_serisi` kendi `kur` kapanisi uzerinden (ic ice tanim haritada iki kez gorunur).
        "_kosul_satirlari": {"_kosul_tek_bar", "kosul_serisi", "kur"},
        "_kosul_tek_bar": {"deger"},
    }
    for ad, cagiranlar in beklenen.items():
        assert _cagiranlar(harita, ad) == cagiranlar, (ad, _cagiranlar(harita, ad))
    # Pump esitsizligi ve olay kosulunun esitsizlikleri baska bir yerde yazilmaz: `>= teta` yalnizca `_h1_pump_dizisi`.
    kaynak = (KOK / "data" / "pozisyon.py").read_text(encoding="utf-8")
    assert kaynak.count("H1_HACIM_CARPANI") == 1
    # `data/` icinde (dondurulmus referans haric) sinyal kosulunu dogrudan cagiran baska bir modul yok.
    for yol in sorted((KOK / "data").glob("*.py")):
        if yol.name in ("_skaler_referans.py", "pozisyon.py", "sinyal.py"):
            continue
        adlar = set().union(*_cagri_haritasi(yol).values()) if _cagri_haritasi(yol) else set()
        assert not adlar & {"_olay_kosulu", "_kosul_satirlari", "_kosul_dizisi", "kosullar_saglandi",
                            "h1_pump_saglandi"}, yol.name
