"""Sizinti testcisi, P2c-1 "kosul serisi": `pozisyon.kosul_serisi`, `KosulSerisi`, `KosulKaynagi`, `KararKaynagi`,
`kaynak_dogrula`, `dizi._kaynak_denetimi` ve capali kosul bellegi.

Amac kodu KIRMAKTIR: gecen test saldirinin yetmedigini, kalan test (ya da `xfail(strict=True)` isaretli test) kodda
gercek bir acik bulundugunu soyler. xfail gerekceleri `S-P2c1-N` numarasiyla baslar; acik kapatilinca test XPASS(strict)
verir ve isaret kaldirilmalidir. Her xfail gerekcesi bulgunun ulasim bicimini (sira disi / kasitli kod bicimi) yazar.

Sentetik dunya `tests/esitlik_yardimcisi.dunya`dir; gercek onbellek (`cache/`), C1/C2 verisi ve ag kullanilmaz. Onay
kumesi (C2/C1) testleri `tests/onay_yardimcisi.kosu` ile gecici kayda yonlenmis SAHTE bir onay kosusu acar (gercek
ONAY_KAYDI.md'ye yazilmaz). Deger, getiri, olay sayisi ve kosulun dogru oldugu bar sayisi yazdirilmaz: testler yalnizca
iki yolun ayni olup olmadigini ve korumalarin calisip calismadigini denetler.
"""

from __future__ import annotations

import datetime as dt
import functools
from types import MappingProxyType

import numpy as np
import pandas as pd
import pytest

import config
from data import _skaler_referans as ref
from data import dizi, kume_bellegi, pencere, pozisyon, sinyal, split
from esitlik_yardimcisi import H4, dunya
from kapi_yardimcisi import SENTETIK_DONEMLER, SENTETIK_GRUPLAR, SENTETIK_VERI, veri
from onay_yardimcisi import gecici_kayit, kosu

BAS, BITIS = "2021-01-01", "2021-08-31 20:00"
UC_SAAT = dt.timezone(dt.timedelta(hours=3))     # sabit ofset: tz veritabanina bagimli degil
OHLC = ("open", "high", "low", "close")


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


def _tur(x) -> str:
    """Rapor icin: deger icermez (yalnizca tur ya da hata sinifi)."""
    return type(x).__name__


def _y(hipotez, i=0):
    return dict(sinyal.izgara(hipotez)[i])


def _izgara(hipotez, kimlik, kume="KESIF"):
    return pozisyon.hipotez_izgarasi_barlari(hipotez, kume=kume, **kimlik)


def _seri(hipotez, kimlik, y=None, capa=None, kume="KESIF"):
    return pozisyon.kosul_serisi(hipotez, _y(hipotez) if y is None else y, kume=kume, **kimlik, capa=capa)


def _ref(hipotez, kimlik, t, y=None, capa=None, kume="KESIF"):
    return _cagir(ref.sinyal_kosulu, t, hipotez=hipotez, yapilandirma=_y(hipotez) if y is None else y, capa=capa,
                  kume=kume, **kimlik)


def _seri_degeri(hipotez, kimlik, t, y=None, capa=None, kume="KESIF"):
    return _cagir(lambda: _seri(hipotez, kimlik, y, capa, kume).deger(t))


def _kaynaklar(hipotez, kimlik, y=None, kume="KESIF"):
    y = _y(hipotez) if y is None else y
    return (pozisyon.kosul_kaynagi(hipotez, y, kume=kume, **kimlik),
            pozisyon.karar_kaynagi(hipotez, y, kume=kume, **kimlik))


def _satirlar(seri):
    z = list(seri.zamanlar())
    return z, [seri.deger(x) for x in z]


def _turetilmis(kimlik, bozan, *, grup="A"):
    """Ayni donemle yeni bir sentetik sembol: `bozan(m, f) -> (m2, f2)` ile cerceveler degistirilir."""
    m, f = SENTETIK_VERI[kimlik["sembol"]]
    b, s, fy = SENTETIK_DONEMLER[(kimlik["sembol"], 0)]
    m2, f2 = bozan(m.copy(), f.copy())
    return veri(m2.reset_index(drop=True), f2.reset_index(drop=True), b, s, ham=True, funding_yok=fy, grup=grup)


def _olcekle(m, maske, carpan):
    for alan in (*OHLC, "quote_volume", "volume"):
        m.loc[maske, alan] = m.loc[maske, alan] * carpan
    return m


def _funding_boz(f, maske):
    f.loc[maske, "oran"] = 0.05
    f["oran_8h"] = f["oran"] * 8.0 / f["aralik_saat"]
    return f


class _SplitVekili:
    """`split` modulu koruma altindadir; dizinin gordugu `split_modulu` adina vekil kurulur."""

    def __init__(self, **degisen):
        self.__dict__.update(degisen)

    def __getattr__(self, ad):
        return getattr(split, ad)


def _ozet(sonuc):
    return (tuple((o.zaman, o.capa) for o in sonuc.olaylar), tuple((r.zaman, r.capa, r.gerekce) for r in sonuc.retler))


def _dizi_cagir(hipotez, y, kimlik, kk, kr, zamanlar, **ust):
    bar = config.HIPOTEZ_IZGARASI[hipotez]
    bas, bitis, _ = pozisyon.donem_kaydi(kimlik["sembol"], kimlik["donem_no"])
    arg = dict(birincil_ufuk=config.BIRINCIL_UFUK[bar], kosul=kk, karar=kr, sembol=kimlik["sembol"], kume="KESIF",
               donem_no=kimlik["donem_no"], donem_baslangic=bas, donem_bitis=bitis)
    arg.update(ust)
    return dizi.olay_dizisi(hipotez, y, zamanlar, bar, **arg)


@pytest.fixture
def dunya_s():
    return dunya(641, BAS, BITIS)


# =====================================================================================================================
# HEDEF 1: seri ve kaynak taklidi / degistirilmesi
# =====================================================================================================================

def test_kosul_serisi_alt_sinifi_gizli_belirtecsiz_kurulamaz(dunya_s):
    """G11 (imzali seri): `KosulSerisi` alt sinifi, gizli belirtec olmadan (None, object(), 0, 'kosul', True) kurulamaz."""
    kimlik, _ = dunya_s
    baglam = _seri("H2", kimlik)._KosulSerisi__baglam

    class Taklit(pozisyon.KosulSerisi):
        pass

    bos = pd.DatetimeIndex([], tz="UTC")
    for gizli in (None, object(), 0, "kosul", True):
        with pytest.raises(TypeError):
            Taklit(gizli, baglam, ("kosul",), 0, bos, (), None)


def test_kosul_serisi_gizli_belirtecle_bile_etiketsiz_ya_da_sayisi_tutmayan_kurulum_reddedilir(dunya_s):
    """G11: kimligi 'kosul' etiketiyle baslamayan (ör. bir KapiSerisi kimligi) ya da zaman ve deger sayisi tutmayan
    kurulum, gizli belirtec bilinse bile reddedilir (kapi serisi kimligiyle kosul serisi taklit edilemez)."""
    kimlik, _ = dunya_s
    baglam = _seri("H2", kimlik)._KosulSerisi__baglam
    bos = pd.DatetimeIndex([], tz="UTC")
    for kimlik_taklidi in (("kapi_serisi", "x"), (), ("Kosul",), ("kapi",)):
        with pytest.raises(ValueError):
            pozisyon.KosulSerisi(pozisyon._SERI_GIZLI, baglam, kimlik_taklidi, 0, bos, (), None)
    iki = pd.DatetimeIndex(["2021-01-01", "2021-01-02"], tz="UTC")
    with pytest.raises(ValueError):
        pozisyon.KosulSerisi(pozisyon._SERI_GIZLI, baglam, ("kosul",), 0, iki, (True,), None)


def test_kosul_serisi_ic_depolari_degistirilemez_turlerde(dunya_s):
    """G11: satir degerleri, zamanlar ve imzalar demet, sira haritasi `MappingProxyType`; yerinde degistirilemez."""
    kimlik, _ = dunya_s
    seri = _seri("H2", kimlik)
    for ad in ("degerler", "zamanlar", "imzalar"):
        assert isinstance(getattr(seri, f"_KosulSerisi__{ad}"), tuple), ad
    sira = seri._KosulSerisi__sira
    assert isinstance(sira, MappingProxyType)
    with pytest.raises(TypeError):
        sira[0] = 1


def test_kosul_serisi_zamanlar_ciktisini_degistirmek_seriyi_etkilemez(dunya_s):
    """G11: `zamanlar()` her cagrida yeni bir indeks kurar; cikti uzerindeki yazma denemesi seriyi degistirmez."""
    kimlik, _ = dunya_s
    seri = _seri("H1", kimlik)
    once = list(seri.zamanlar())
    deger_once = seri.deger(once[300])
    z1 = seri.zamanlar()
    try:
        ham = z1.asi8
        ham[:] = 0
    except (ValueError, TypeError):
        pass                                           # salt okunur: daha da iyi
    assert list(seri.zamanlar()) == once
    assert seri.deger(once[300]) is deger_once


@pytest.mark.xfail(strict=True, reason=(
    "S-P2c1-1: KosulSerisi satir degeri VE satir imzasi birlikte degistirilirse (object.__setattr__ ile "
    "`_KosulSerisi__degerler` ve `_KosulSerisi__imzalar`; imza `pozisyon._satir_imzasi` ve modul seviyesi "
    "`_SERI_GIZLI` ile yeniden hesaplanir) `deger(t)` sahte degeri sessizce doner. Imza gizliligi yalnizca "
    "dikkatsiz degisiklige karsi korur. ULASIM: KASITLI kod bicimi (ozel ad + object.__setattr__); belgelenmis "
    "sinir (KosulSerisi docstring: 'kararli bir atlatmaya karsi degil'). Oneri: xfail olarak kayitta kalir."))
def test_kosul_serisi_satir_ve_imzasi_birlikte_degistirilirse_okuma_reddedilmeli(dunya_s):
    kimlik, _ = dunya_s
    seri = _seri("H2", kimlik)
    t = seri.zamanlar()[150]
    i = seri._KosulSerisi__sira[int(t.value)]
    onceki = seri.deger(t)
    degerler = list(seri._KosulSerisi__degerler)
    degerler[i] = (not onceki) if onceki is not None else True
    imzalar = list(seri._KosulSerisi__imzalar)
    imzalar[i] = pozisyon._satir_imzasi(seri.kimlik, seri._KosulSerisi__isaret, seri._KosulSerisi__zamanlar[i],
                                         degerler[i])
    object.__setattr__(seri, "_KosulSerisi__degerler", tuple(degerler))
    object.__setattr__(seri, "_KosulSerisi__imzalar", tuple(imzalar))
    with pytest.raises(Exception):
        seri.deger(t)


@pytest.mark.xfail(strict=True, reason=(
    "S-P2c1-2: `kaynak_dogrula` yapilandirma ile kimlik[1] (yapilandirma kimligi) arasindaki baglantiyi yeniden "
    "hesaplamaz; `_Kaynak__yapilandirma` baska bir izgara demetiyle degistirilip imza `pozisyon._kaynak_imzasi` ile "
    "yeniden hesaplanirsa kaynak dogrulamayi gecer: kimligi dizinin argumanlariyla ayni ama kosulu BASKA "
    "yapilandirmayla hesaplayan kaynak dizide kabul edilir. ULASIM: KASITLI kod bicimi (ozel adlar + "
    "object.__setattr__). Oneri: xfail olarak kayitta kalir; ucuz kapatma: `_imza_tutuyor`da "
    "`sinyal.yapilandirma_kimligi(hipotez, y) == kimlik[1]` denetimi."))
def test_kaynak_yapilandirmasi_kimlikle_tutarsiz_kilinirsa_dogrulama_reddetmeli(dunya_s):
    kimlik, _ = dunya_s
    kk, _ = _kaynaklar("H2", kimlik)
    baska = _y("H2", -1)
    assert sinyal.yapilandirma_kimligi("H2", baska) != kk.kimlik[1]
    object.__setattr__(kk, "_Kaynak__yapilandirma", MappingProxyType(dict(baska)))
    object.__setattr__(kk, "_Kaynak__imza", pozisyon._kaynak_imzasi(kk._TUR, kk.kimlik, kk._yapilandirma()))
    with pytest.raises(ValueError):
        pozisyon.kaynak_dogrula(kk)


@pytest.mark.xfail(strict=True, reason=(
    "S-P2c1-3: `_Kaynak._bellek()` kaynagin canli ic sozlugunu doner; `kk._bellek()['capasiz'] = baska_seri` ile "
    "BASKA yapilandirmanin (ya da hipotezin) serisi kaynaga yerlestirilebilir ve `KosulKaynagi.__call__` tutulan "
    "serinin kimligini kaynagin kimligiyle karsilastirmaz (imza `_bellek`i kapsamaz). ULASIM: KASITLI kod bicimi "
    "(alt cizgili ozel yontem). Oneri: xfail olarak kayitta kalir; ucuz kapatma: `_bellek` yerine kaynak icinde "
    "kimlik denetimli yazma ya da `MappingProxyType` + kimlik denetimi."))
def test_kaynagin_ic_bellegine_baska_seri_yerlestirilemez(dunya_s):
    kimlik, _ = dunya_s
    kk, _ = _kaynaklar("H2", kimlik)
    baska = _seri("H2", kimlik, _y("H2", -1))
    bellek = kk._bellek()
    with pytest.raises((TypeError, AttributeError)):
        bellek["capasiz"] = baska


def test_kaynak_yapilandirma_gorunumu_degistirilemez_ve_cagiranin_sozlugunu_baglamaz(dunya_s):
    """A2 karari (a): kaynak, cagiranin yapilandirma sozlugunun kopyasini tutar; sozluk sonradan degistirilse de
    kaynak, imzasi ve degerleri ayni kalir; kaynagin gorunumu salt okunurdur."""
    kimlik, _ = dunya_s
    y = _y("H2")
    kk, kr = _kaynaklar("H2", kimlik, y)
    izgara = _izgara("H2", kimlik)
    onceki = [kk(t, None) for t in izgara[100::37]]
    y["k"] = _y("H2", -1)["k"]
    y["phi"] = _y("H2", -1)["phi"]
    pozisyon.kaynak_dogrula(kk)
    pozisyon.kaynak_dogrula(kr)
    assert [kk(t, None) for t in izgara[100::37]] == onceki
    with pytest.raises(TypeError):
        kk._yapilandirma()["k"] = 99


def test_kaynak_sinifi_degistirilirse_imza_bozulur_ve_dizi_reddeder(dunya_s):
    """A2 karari: imza kaynak turunu (`_TUR`) baglar; `__class__` KosulKaynagi <-> KararKaynagi yer degistirirse
    (ayni slot yerlesimi) `kaynak_dogrula` ve dizi 'imza' hatasi verir."""
    kimlik, _ = dunya_s
    h, y = "H2", _y("H2")
    kk, kr = _kaynaklar(h, kimlik)
    kk_gercek, _ = _kaynaklar(h, kimlik)
    try:
        object.__setattr__(kk, "__class__", pozisyon.KararKaynagi)
    except TypeError:
        pytest.skip("kurulum: sinif degisimi bu yerlesimde mumkun degil")
    with pytest.raises(ValueError, match="imza"):
        pozisyon.kaynak_dogrula(kk)
    # Kosul kaynagi gercek, 'karar' yerine KosulKaynagi'ndan KararKaynagi'na cevrilmis nesne verilir.
    with pytest.raises(ValueError, match="imza"):
        _dizi_cagir(h, y, kimlik, kk_gercek, kk, _izgara(h, kimlik)[:60])


def test_kaynak_alt_sinifi_ve_taban_sinif_dogrudan_kurulamaz_ve_dizi_alt_sinifi_reddeder(dunya_s):
    """A1/A2: `type(x) is` denetimi: kaynak alt sinifi (gizli belirtecle bile) dizide TypeError; gizlisiz kurulamaz;
    `_Kaynak` tabani dogrudan kurulamaz. Pytest icinde de (kaynak olmayan kabul dikisi yalniz saf cagrilabilir icin)."""
    kimlik, _ = dunya_s
    h, y = "H2", _y("H2")
    kk, kr = _kaynaklar(h, kimlik)

    class SahteKosul(pozisyon.KosulKaynagi):
        def __call__(self, t, capa):
            return True

    class SahteKarar(pozisyon.KararKaynagi):
        def __call__(self, t, capa):
            raise pencere.OlayOlusmaz("sahte")

    for sinif in (SahteKosul, SahteKarar):
        with pytest.raises(TypeError):
            sinif(object(), kk.kimlik, kk._yapilandirma())
    with pytest.raises(TypeError):
        pozisyon._Kaynak(pozisyon._KAYNAK_GIZLI, kk.kimlik, kk._yapilandirma())
    sk = SahteKosul(pozisyon._KAYNAK_GIZLI, kk.kimlik, kk._yapilandirma())
    sr = SahteKarar(pozisyon._KAYNAK_GIZLI, kr.kimlik, kr._yapilandirma())
    for k in (sk, sr):
        with pytest.raises(TypeError):
            pozisyon.kaynak_dogrula(k)
    zamanlar = _izgara(h, kimlik)[:60]
    with pytest.raises(TypeError, match="kosul"):
        _dizi_cagir(h, y, kimlik, sk, kr, zamanlar)
    with pytest.raises(TypeError, match="karar"):
        _dizi_cagir(h, y, kimlik, kk, sr, zamanlar)


# =====================================================================================================================
# HEDEF 2: eski seri / eski kaynak
# =====================================================================================================================

@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_temizleme_sonrasi_eski_kaynak_icinde_tutulan_eski_seriyi_dondurmez(dunya_s, hipotez):
    """G11 donem isareti: `kume_bellegi.temizle()` (kosu acilisi/kapanisi) sonrasi kaynagin icinde tutulan capasiz ve
    capali seri okunamaz (SeriEskidi); satir olmayan t de ayni; yeni kaynak calisir ve ayni degeri verir."""
    kimlik, _ = dunya_s
    kk, _ = _kaynaklar(hipotez, kimlik)
    izgara = _izgara(hipotez, kimlik)
    t = izgara[len(izgara) // 2]
    eski_deger = kk(t, None)                     # seri kaynakta tutulur
    p = None
    if hipotez == "H1":
        p = t
        kk(p + 3 * H4, p)                        # capali seri de kaynakta tutulur
    kume_bellegi.temizle()
    with pytest.raises(pozisyon.SeriEskidi):
        kk(t, None)
    with pytest.raises(pozisyon.SeriEskidi):
        kk(izgara[len(izgara) // 2 + 1], None)
    with pytest.raises(pozisyon.SeriEskidi):
        kk(t + pd.Timedelta(hours=2), None)      # satir olmayan t de `_denetle`den once bir sey donmez
    if p is not None:
        with pytest.raises(pozisyon.SeriEskidi):
            kk(p + 3 * H4, p)
    kk2, _ = _kaynaklar(hipotez, kimlik)
    assert kk2(t, None) is eski_deger


def test_temizleme_sonrasi_eski_seri_her_okuma_yolunda_eskidi(dunya_s):
    """G11: `deger` (satir ve satir olmayan t), `icerir`, `zamanlar`, `len` temizlemeden sonra SeriEskidi; ayni istek
    yeni nesne doner; capali seri ayri bellekte de ayni."""
    kimlik, ozel = dunya_s
    p = ozel["pump"][2]
    seriler = [_seri("H1", kimlik), _seri("H1", kimlik, capa=p), _seri("H2", kimlik), _seri("H3", kimlik)]
    zamanlar = [s.zamanlar()[5] for s in seriler]
    kume_bellegi.temizle()
    for s, t in zip(seriler, zamanlar):
        for okuma in (lambda: s.deger(t), lambda: s.deger(t + pd.Timedelta(hours=2)), lambda: s.icerir(t),
                      lambda: s.zamanlar(), lambda: len(s)):
            with pytest.raises(pozisyon.SeriEskidi):
                okuma()
    assert _seri("H1", kimlik, capa=p) is not seriler[1]
    assert not [a for a in pozisyon._CAPALI_KOSUL_BELLEGI if a[-1] != kume_bellegi.donem_isareti()]


def test_eski_seri_yeni_isaretli_anahtara_yerlestirilse_de_okunamaz(dunya_s):
    """G11: eski isaretli seri, yeni isaretin onbellek anahtarina elle yazilirsa `kosul_serisi` onu dondurebilir
    (kimlik tutar) ama OKUMA her durumda SeriEskidi verir: eski seri sessizce deger vermez."""
    kimlik, _ = dunya_s
    eski = _seri("H2", kimlik)
    t = eski.zamanlar()[100]
    kume_bellegi.temizle()
    yeni = _seri("H2", kimlik)
    anahtar = next(a for a in pozisyon._SERI_BELLEGI if a[0] == "kosul_serisi")
    pozisyon._SERI_BELLEGI[anahtar] = eski
    donen = _seri("H2", kimlik)
    assert donen is eski
    with pytest.raises(pozisyon.SeriEskidi):
        donen.deger(t)
    yeni.deger(t)                                                  # yeni seri okunur (kurulum sagligi)


def test_onay_kosusu_kapaninca_icinde_olusan_kaynak_ve_seri_okunamaz(tmp_path):
    """On-kayit §3 / CLAUDE.md §5: onay kosusunun kapanisi bellek kopyalarini ve serileri gecersiz kilar. Kosu icinde
    kurulan seri ve kaynak (onbellege almis ve almamis) kosu bittikten sonra HICBIR yoldan deger vermez."""
    yol = tmp_path / "onay_gecici.md"
    yol.write_text("bas\n", encoding="utf-8")
    gecici_kayit(yol)
    kimlik, _ = dunya(644, "2025-03-01", "2026-01-31 20:00")
    h, y = "H2", _y("H2")
    with kosu(h, "C2"):
        izgara = pozisyon.hipotez_izgarasi_barlari(h, kume="C2", **kimlik)
        t = izgara[200]
        kk, _ = _kaynaklar(h, kimlik, y, kume="C2")
        kk_bos, _ = _kaynaklar(h, kimlik, y, kume="C2")
        seri = pozisyon.kosul_serisi(h, y, kume="C2", **kimlik)
        kk(t, None)
        seri.deger(t)
    with pytest.raises(pozisyon.SeriEskidi):
        kk(t, None)
    for okuma in (lambda: seri.deger(t), lambda: seri.icerir(t), lambda: seri.zamanlar(), lambda: len(seri)):
        with pytest.raises(pozisyon.SeriEskidi):
            okuma()
    with pytest.raises(Exception):               # hic okunmamis kaynak: seri kurulamaz (kosu kapali)
        kk_bos(t, None)
    with pytest.raises(Exception):
        pozisyon.kosul_serisi(h, y, kume="C2", **kimlik)


# =====================================================================================================================
# HEDEF 1/3: onay kumesi ve grup sizintisi
# =====================================================================================================================

def test_onay_kosusu_disinda_C2_kosul_serisi_ve_kaynaklari_kurulamaz_kayit_yazilmaz_bellege_girmez(tmp_path):
    """On-kayit §3: onay kumesine acik kosu disinda erisim yoktur. Seri, kosul kaynagi, karar kaynagi (capali ve
    capasiz) hata verir; kayit dosyasina HICBIR sey yazilmaz; paylasilan ve capali bellege C2 anahtari girmez."""
    yol = tmp_path / "onay_gecici.md"
    yol.write_text("bas\n", encoding="utf-8")
    gecici_kayit(yol)
    kimlik, _ = dunya(645, "2025-03-01", "2026-01-31 20:00")
    y = _y("H2")
    cagrilar = [
        lambda: pozisyon.kosul_serisi("H2", y, kume="C2", **kimlik),
        lambda: pozisyon.kosul_kaynagi("H2", y, kume="C2", **kimlik),
        lambda: pozisyon.karar_kaynagi("H2", y, kume="C2", **kimlik),
        lambda: pozisyon.kosul_serisi("H1", _y("H1"), kume="C2", **kimlik, capa=pd.Timestamp("2025-10-01", tz="UTC")),
        lambda: pozisyon.kosul_serisi("H1", _y("H1"), kume="C2", **kimlik,
                                       capa=pd.DatetimeIndex([pd.Timestamp("2025-10-01", tz="UTC")])),
    ]
    for f in cagrilar:
        with pytest.raises(Exception):
            f()
    assert yol.read_text(encoding="utf-8") == "bas\n"
    for sozluk in (pozisyon._SERI_BELLEGI, pozisyon._SERI_HATALARI, pozisyon._CAPALI_KOSUL_BELLEGI,
                   pozisyon._CAPALI_KOSUL_HATALARI):
        assert all(a[1] != "C2" for a in sozluk if a[0] == "kosul_serisi")


def test_onay_kosusunda_baska_hipotez_baska_yapilandirma_ve_KESIF_kurulamaz(tmp_path):
    """On-kayit §3, §8 madde 5: acik (H2, C2) kosusu icinde H3, F2'nin kilitlemedigi H2 yapilandirmasi ve KESIF
    kumesi icin seri / kaynak kurulamaz."""
    yol = tmp_path / "onay_gecici.md"
    yol.write_text("bas\n", encoding="utf-8")
    gecici_kayit(yol)
    kimlik, _ = dunya(646, "2025-03-01", "2026-01-31 20:00")
    yk, yb = _y("H2", 0), _y("H2", -1)
    with kosu("H2", "C2"):
        for f in (
            lambda: pozisyon.kosul_serisi("H2", yb, kume="C2", **kimlik),
            lambda: pozisyon.kosul_kaynagi("H2", yb, kume="C2", **kimlik),
            lambda: pozisyon.karar_kaynagi("H2", yb, kume="C2", **kimlik),
            lambda: pozisyon.kosul_serisi("H3", _y("H3"), kume="C2", **kimlik),
            lambda: pozisyon.kosul_kaynagi("H3", _y("H3"), kume="C2", **kimlik),
            lambda: pozisyon.kosul_serisi("H2", yk, kume="KESIF", **kimlik),
            lambda: pozisyon.kosul_kaynagi("H2", yk, kume="KESIF", **kimlik),
        ):
            with pytest.raises(Exception):
                f()
        assert isinstance(pozisyon.kosul_serisi("H2", yk, kume="C2", **kimlik), pozisyon.KosulSerisi)


def test_kesif_kumesine_B_grubu_sembol_seri_ve_kaynaklarla_sizdirilamaz(dunya_s):
    """On-kayit §3 / CLAUDE.md §3 madde 3: B grubu sembol KESIF icin seri, kaynak ya da izgara uretemez (ValueError)."""
    kimlik, _ = dunya_s
    b_kimlik = _turetilmis(kimlik, lambda m, f: (m, f), grup="B")
    y = _y("H2")
    for f in (
        lambda: pozisyon.kosul_serisi("H2", y, kume="KESIF", **b_kimlik),
        lambda: pozisyon.kosul_kaynagi("H2", y, kume="KESIF", **b_kimlik),
        lambda: pozisyon.karar_kaynagi("H2", y, kume="KESIF", **b_kimlik),
        lambda: pozisyon.hipotez_izgarasi_barlari("H2", kume="KESIF", **b_kimlik),
        lambda: pozisyon.kosul_serisi("H1", _y("H1"), kume="KESIF", **b_kimlik),
    ):
        with pytest.raises(ValueError):
            f()


def test_grup_sonradan_degisirse_mevcut_seri_ve_kaynak_okunamaz(dunya_s):
    """G11: erisim denetimi HER okumada grup uyeligini yeniden sorar. Evren/bolme tablosu (burada sentetik grup
    tablosu) kurulumdan sonra sembolu B'ye tasirsa onceden kurulmus seri ve kaynak KESIF icin okunamaz."""
    kimlik, _ = dunya_s
    kk, kr = _kaynaklar("H2", kimlik)
    seri = _seri("H2", kimlik)
    t = seri.zamanlar()[120]
    kk(t, None)
    eski = SENTETIK_GRUPLAR[kimlik["sembol"]]
    SENTETIK_GRUPLAR[kimlik["sembol"]] = "B"
    try:
        for okuma in (lambda: seri.deger(t), lambda: seri.icerir(t), lambda: seri.zamanlar(), lambda: len(seri),
                      lambda: kk(t, None)):
            with pytest.raises(ValueError):
                okuma()
        assert isinstance(_cagir(kr, t, None), BaseException)
    finally:
        SENTETIK_GRUPLAR[kimlik["sembol"]] = eski


def test_C1_kumesinde_A_grubu_sembol_kurulamaz_B_grubu_kurulur(tmp_path):
    """On-kayit §3: C1 yalnizca B grubudur. Acik (H2, C1) kosusunda A grubu sembol ValueError; B grubu sembol seri
    kurar ve satirlari kume sinirlari icindedir."""
    yol = tmp_path / "onay_gecici.md"
    yol.write_text("bas\n", encoding="utf-8")
    gecici_kayit(yol)
    a_kimlik, _ = dunya(647, BAS, BITIS)
    b_kimlik = _turetilmis(a_kimlik, lambda m, f: (m, f), grup="B")
    y = _y("H2")
    with kosu("H2", "C1"):
        for f in (lambda: pozisyon.kosul_serisi("H2", y, kume="C1", **a_kimlik),
                  lambda: pozisyon.kosul_kaynagi("H2", y, kume="C1", **a_kimlik),
                  lambda: pozisyon.karar_kaynagi("H2", y, kume="C1", **a_kimlik)):
            with pytest.raises(ValueError):
                f()
        seri = pozisyon.kosul_serisi("H2", y, kume="C1", **b_kimlik)
        z = seri.zamanlar()
        assert len(z) and z.min() >= pd.Timestamp(config.KESIF_BASI) and z.max() <= pd.Timestamp(config.KESIF_SONU)


def test_C2_serisi_yalnizca_C2_araligini_tasir_kume_disi_t_None_ve_referansla_ayni(tmp_path):
    """On-kayit §3 (kumeler arasi veri odunc alinmaz), G13: C2 serisinin satirlari C2 araligindadir; KESIF'e ait
    bir t (2025-08-31 20:00) icin deger `None` ve referansla aynidir."""
    yol = tmp_path / "onay_gecici.md"
    yol.write_text("bas\n", encoding="utf-8")
    gecici_kayit(yol)
    kimlik, _ = dunya(648, "2025-03-01", "2026-01-31 20:00")
    y = _y("H2")
    kesif_son = pd.Timestamp("2025-08-31 20:00", tz="UTC")
    with kosu("H2", "C2"):
        seri = pozisyon.kosul_serisi("H2", y, kume="C2", **kimlik)
        z = seri.zamanlar()
        assert len(z) and z.min() >= pd.Timestamp(config.C2_BASI) and z.max() <= pd.Timestamp(config.C2_SONU)
        assert seri.deger(kesif_son) is None
        assert ayni(_cagir(seri.deger, kesif_son), _ref("H2", kimlik, kesif_son, y, kume="C2"))


@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_kesif_sonrasi_veriyi_bozmak_kume_ici_satirlari_degistirmez(hipotez):
    """G13/G16: KESIF sonu (2025-08-31 23:59:59) SONRASI fiyat, hacim ve funding degisince kume ici satirlar ve (H1
    icin) son pump barlarinin capali serileri degismez; kume disi t `None` kalir; satirlar kume sonunu asmaz."""
    kimlik, _ = dunya(649, "2025-01-01", "2025-11-26 20:00")
    sinir = pd.Timestamp(config.KESIF_SONU)

    def boz(m, f):
        m = _olcekle(m, pd.DatetimeIndex(m["open_time"]) > sinir, 40.0)
        return m, _funding_boz(f, pd.DatetimeIndex(f["odeme_zamani"]) > sinir)

    yeni = _turetilmis(kimlik, boz)
    a, b = _seri(hipotez, kimlik), _seri(hipotez, yeni)
    za, va = _satirlar(a)
    zb, vb = _satirlar(b)
    assert za and za == zb and za[-1] <= sinir
    assert va == vb
    t_disi = pd.Timestamp("2025-09-02 00:00", tz="UTC")
    assert a.deger(t_disi) is None and b.deger(t_disi) is None
    if hipotez == "H1":
        p = za[-4]
        ca, cb = _seri("H1", kimlik, capa=p), _seri("H1", yeni, capa=p)
        assert _satirlar(ca) == _satirlar(cb)
        assert [ca.deger(p + d * H4) for d in range(0, 15)] == [cb.deger(p + d * H4) for d in range(0, 15)]


@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_kesif_basi_oncesi_veriyi_bozmak_kume_ici_satirlari_degistirmez(hipotez):
    """G13/G16: KESIF basi (2020-01-01) ONCESI veri degisince kume ici satirlar degismez (pencereler kumenin onune
    uzanamaz); kume oncesi bir pump capasi ve kume disi t degismez/`None`; satirlar kume basindan once baslamaz."""
    kimlik, _ = dunya(650, "2019-06-01", "2020-04-26 20:00")
    sinir = pd.Timestamp(config.KESIF_BASI)

    def boz(m, f):
        m = _olcekle(m, pd.DatetimeIndex(m["open_time"]) < sinir, 40.0)
        return m, _funding_boz(f, pd.DatetimeIndex(f["odeme_zamani"]) < sinir)

    yeni = _turetilmis(kimlik, boz)
    a, b = _seri(hipotez, kimlik), _seri(hipotez, yeni)
    za, va = _satirlar(a)
    zb, vb = _satirlar(b)
    assert za and za == zb and za[0] >= sinir
    assert va == vb
    t_disi = pd.Timestamp("2019-12-31 20:00", tz="UTC")
    assert a.deger(t_disi) is None and b.deger(t_disi) is None
    if hipotez == "H1":
        for p in (za[0], sinir - 2 * H4):
            ca, cb = _seri("H1", kimlik, capa=p), _seri("H1", yeni, capa=p)
            assert [ca.deger(p + d * H4) for d in range(0, 15)] == [cb.deger(p + d * H4) for d in range(0, 15)]
            assert ayni(_seri_degeri("H1", kimlik, p + 3 * H4, capa=p), _ref("H1", kimlik, p + 3 * H4, capa=p))


# =====================================================================================================================
# HEDEF 3: baska anahtarla okuma, capa bicimleri, bellek
# =====================================================================================================================

def test_capa_zaman_bicimleri_ayni_anahtar_ayni_seri_naif_bicimler_TypeError(dunya_s):
    """G11 anahtar kurali: UTC Timestamp, UTC'ye esit baska saat dilimli Timestamp, ISO dizgesi ve tz'li `datetime`
    ayni anahtara gider (ayni nesne). Saat dilimsiz biciminin hepsi (Timestamp, np.datetime64, dizge) ve NaT
    `TypeError` verir (sessiz yanlis capa yok)."""
    kimlik, ozel = dunya_s
    p = ozel["pump"][2]
    temel = _seri("H1", kimlik, capa=p)
    for v in (p.tz_convert(UC_SAAT), p.isoformat(), p.to_pydatetime(), p.tz_convert("UTC")):
        assert _seri("H1", kimlik, capa=v) is temel
    naif = p.tz_localize(None)
    for v in (naif, np.datetime64(naif), str(naif), pd.NaT):
        with pytest.raises(TypeError):
            _seri("H1", kimlik, capa=v)


def test_capa_farkli_saat_dilimiyle_ilk_kurulan_seri_UTC_capali_referansla_ayni(dunya_s):
    """G11/A4: seri capasi UTC+3'lu bir Timestamp ile ILK kez kurulursa (onbellekte o nesne kalir) satirlari ve
    satir disi zamanlari UTC capali referansla ayni degeri verir; kaynak yolu da ayni."""
    kimlik, ozel = dunya_s
    p = ozel["pump"][2]
    ist = p.tz_convert(UC_SAAT)
    seri = _seri("H1", kimlik, capa=ist)
    for d in (0, 1, 2, 5, 12, 13, 14):
        t = p + d * H4
        a, b = _cagir(seri.deger, t), _ref("H1", kimlik, t, capa=p)
        assert ayni(a, b), (d, _tur(a), _tur(b))
    kk, _ = _kaynaklar("H1", kimlik)
    for d in (1, 6, 12):
        t = p + d * H4
        a, b = _cagir(kk, t, ist), _ref("H1", kimlik, t, capa=p)
        assert ayni(a, b), (d, _tur(a), _tur(b))


def test_capa_dizisi_gecersiz_bicimler_reddedilir(dunya_s):
    """G11: izgara uzunlugunda dizi bicimleri: saat dilimsiz ve NaT'li dizi TypeError; H2/H3'te capa dizisi
    ValueError (skalerle ayni sinif); uzunluk tutmayan dizi ValueError."""
    kimlik, _ = dunya_s
    izgara = _izgara("H1", kimlik)
    naif = pd.DatetimeIndex([t.tz_localize(None) - H4 for t in izgara])
    with pytest.raises(TypeError):
        _seri("H1", kimlik, capa=naif)
    with pytest.raises(TypeError):
        _seri("H1", kimlik, capa=pd.DatetimeIndex([pd.NaT] * len(izgara), tz="UTC"))
    with pytest.raises(ValueError):
        _seri("H1", kimlik, capa=pd.DatetimeIndex(list(izgara[:-1] - H4)))
    for h in ("H2", "H3"):
        capa = pd.DatetimeIndex(list(_izgara(h, kimlik) - H4))
        with pytest.raises(ValueError):
            _seri(h, kimlik, capa=capa)


def test_capa_dizisi_ayni_pump_ile_tek_capali_seri_ayni_satir_degerlerini_verir(dunya_s):
    """G11 anahtar ayrimi: [p]*n capa dizisi ile tek capa p AYRI nesnelerdir, ama izgara barlarinda ikisi de
    referansin `capa=p` degerini verir (anahtar cakismasi ya da capa karismasi yok)."""
    kimlik, ozel = dunya_s
    p = ozel["pump"][1]
    izgara = _izgara("H1", kimlik)
    s_dizi = _seri("H1", kimlik, capa=pd.DatetimeIndex([p] * len(izgara)))
    s_tek = _seri("H1", kimlik, capa=p)
    assert s_dizi is not s_tek
    kume = set(izgara)
    ornek = sorted(set(izgara[::60]) | {p + d * H4 for d in range(0, 15) if p + d * H4 in kume})
    for t in ornek:
        b = _ref("H1", kimlik, t, capa=p)
        a1, a2 = _cagir(s_dizi.deger, t), _cagir(s_tek.deger, t)
        assert ayni(a1, b) and ayni(a2, b), (_tur(a1), _tur(a2), _tur(b))


def test_kosul_kaynagi_art_arda_farkli_capalarla_ve_capasizla_karismaz(dunya_s):
    """A2: kaynagin tuttugu 'son capali seri' capa degisince, capasiz cagri araya girince ve capa farkli bicimde
    (Timestamp, ISO dizgesi, UTC+3) verilince yanlis seri dondurmez: her cevap referansla ayni."""
    kimlik, ozel = dunya_s
    p1, p2 = ozel["pump"][0], ozel["pump"][1]
    kk, _ = _kaynaklar("H1", kimlik)
    istekler = []
    for p in (p1, p2, p1, p2):
        for d in (1, 4, 12):
            istekler.append((p + d * H4, p))
    istekler += [(p1 + 2 * H4, None), (p1 + 2 * H4, p1), (p1 + 2 * H4, p1.isoformat()), (p1 + 2 * H4, p1.tz_convert(UC_SAAT)),
                 (p2 + 2 * H4, p1), (p1 + 2 * H4, p2)]
    for t, c in istekler:
        cu = None if c is None else pd.Timestamp(c).tz_convert("UTC")
        a, b = _cagir(kk, t, c), _ref("H1", kimlik, t, capa=cu)
        assert ayni(a, b), (_tur(a), _tur(b))


def test_kosul_kaynagi_H2_H3_de_capa_verilince_referansla_ayni_sinif(dunya_s):
    """B 11: H2 ve H3 kaynaginda capa verilemez (ValueError, referansla ayni); naif capa TypeError."""
    kimlik, _ = dunya_s
    for h in ("H2", "H3"):
        kk, _ = _kaynaklar(h, kimlik)
        t = _izgara(h, kimlik)[60]
        a, b = _cagir(kk, t, t - H4), _ref(h, kimlik, t, capa=t - H4)
        assert type(a) is type(b) is ValueError, (h, _tur(a), _tur(b))
        with pytest.raises(TypeError):
            kk(t, (t - H4).tz_localize(None))


def test_H1_capa_hizasiz_ya_da_tolerans_payli_ise_referansla_ayni(dunya_s):
    """A4: izgaraya hizali olmayan capalar (+1 ns, +30 sn, +59 sn, +60 sn, +1 saat) ve bu capalarla sorulan t'ler
    (hizali / hizasiz) seri ve referansta ayni sonucu verir."""
    kimlik, ozel = dunya_s
    p = ozel["pump"][1]
    for kayma in (pd.Timedelta(nanoseconds=1), pd.Timedelta(seconds=30), pd.Timedelta(seconds=59),
                  pd.Timedelta(seconds=60), pd.Timedelta(hours=1)):
        c = p + kayma
        for t in (c + 3 * H4, p + 3 * H4, p + 3 * H4 + pd.Timedelta(seconds=30), p + 12 * H4):
            a, b = _seri_degeri("H1", kimlik, t, capa=c), _ref("H1", kimlik, t, capa=c)
            assert ayni(a, b), (str(kayma), _tur(a), _tur(b))


@pytest.mark.parametrize("y_i", [0, -1])
def test_H1_capa_zaman_haritasi_bosluk_donem_siniri_ve_bozuk_hucre_referansla_ayni(dunya_s, y_i):
    """Hedef 5 (H1 capa sinirlari): capa bosluktaki bar, tek bar bosluk, bozuk hucreli bar, donem basindan ONCE,
    donem basi, donem sonu, donem sonrasi ve enjekte pump barlari; her biri icin teyit uzakligi d = 0..13 (0 ve 13
    tanimsiz). Seri (capali) referansla ayni deger ya da ayni hata. Capa seride olmayan bir bar olabilir:
    kurulum hatasiz ve referansla ayni olmali."""
    kimlik, ozel = dunya_s
    y = _y("H1", y_i)
    bas, bitis, _ = pozisyon.donem_kaydi(kimlik["sembol"], 0)
    capalar = {
        "bosluk_uc_gun": bas + pd.Timedelta(days=61),
        "tek_bar_bosluk": bas + pd.Timedelta(days=100.5),
        "bozuk_hucre": bas + pd.Timedelta(days=120.5),
        "donem_oncesi": bas - 2 * H4,
        "donem_basi": bas,
        "donem_sonu": bitis,
        "donem_sonrasi": bitis + H4,
        "pump": ozel["pump"][0],
    }
    for ad, c in capalar.items():
        for d in range(0, 14):
            t = c + d * H4
            a, b = _seri_degeri("H1", kimlik, t, y, c), _ref("H1", kimlik, t, y, c)
            assert ayni(a, b), (ad, d, _tur(a), _tur(b))


@pytest.mark.parametrize("hipotez", ["H1", "H2"])
def test_tolerans_siniri_ve_hizasiz_t_referansla_ayni(dunya_s, hipotez):
    """A4 / on-kayit §4 'Zaman toleransi' (< 1 dk): t +- 59.999 sn icinde, +-60 ve +-61 sn disinda; capasiz seri ve
    (H1) capali seri referansla ayni. (H3'te tolerans payi bilinen, belgelenmis KeyError farkidir; atlanir.)"""
    kimlik, ozel = dunya_s
    y = _y(hipotez)
    izgara = _izgara(hipotez, kimlik)
    t0 = izgara[len(izgara) // 2]
    saniyeler = (-61, -60, -59.999, -30, 30, 59.999, 60, 61)
    for sn in saniyeler:
        t = t0 + pd.Timedelta(seconds=sn)
        a, b = _seri_degeri(hipotez, kimlik, t, y), _ref(hipotez, kimlik, t, y)
        assert ayni(a, b), (sn, _tur(a), _tur(b))
    if hipotez == "H1":
        p = ozel["pump"][1]
        for sn in saniyeler:
            t = p + 3 * H4 + pd.Timedelta(seconds=sn)
            a, b = _seri_degeri("H1", kimlik, t, y, p), _ref("H1", kimlik, t, y, p)
            assert ayni(a, b), (sn, _tur(a), _tur(b))


def test_capali_bellekte_baska_capa_baska_tur_ya_da_kapi_serisi_donerse_reddedilir(dunya_s):
    """S-P2b2-3'un capali bellekteki karsiligi: capali anahtara baska capanin serisi, capasiz seri ya da bir kapi
    serisi yazilirsa okuma 'tutarsiz' hatasi verir."""
    kimlik, ozel = dunya_s
    p1, p2 = ozel["pump"][2], ozel["pump"][3]
    y = _y("H1")
    _seri("H1", kimlik, capa=p1)
    s2 = _seri("H1", kimlik, capa=p2)
    anahtar = next(a for a in pozisyon._CAPALI_KOSUL_BELLEGI if a[6] == ("tek", int(p1.value)))
    for baska in (s2, _seri("H1", kimlik), pozisyon.kapi_serisi("H1", y, "olay", kume="KESIF", **kimlik, capa=p1)):
        pozisyon._CAPALI_KOSUL_BELLEGI[anahtar] = baska
        with pytest.raises(ValueError, match="tutarsiz"):
            _seri("H1", kimlik, capa=p1)


def test_esdeger_tipli_yapilandirmalar_ayni_anahtar_ayni_seri(dunya_s):
    """G11 anahtar: izgara demetine BIREBIR esit ama farkli tipli yapilandirmalar (float, np.float64, demet) ayni
    kimlige gider: ayni seri nesnesi; kaynak kimligi de ayni."""
    kimlik, _ = dunya_s
    y = _y("H2")
    temel = _seri("H2", kimlik, y)
    adlar = sinyal.PARAMETRELER["H2"]
    varyantlar = [{p: float(y[p]) for p in adlar}, {p: np.float64(y[p]) for p in adlar}, tuple(y[p] for p in adlar),
                  {p: np.int64(y[p]) if float(y[p]).is_integer() else y[p] for p in adlar}]
    for v in varyantlar:
        assert _seri("H2", kimlik, v) is temel
        assert pozisyon.kosul_kaynagi("H2", v, kume="KESIF", **kimlik).kimlik == \
            pozisyon.kosul_kaynagi("H2", y, kume="KESIF", **kimlik).kimlik


# =====================================================================================================================
# HEDEF 4: dizi ve kaynaklar
# =====================================================================================================================

class _Sarmal:
    def __init__(self, k):
        self._k = k

    def __call__(self, t, capa):
        return self._k(t, capa)


_SARMALAR = {
    "partial": lambda k: functools.partial(k),
    "bagli_yontem": lambda k: k.__call__,
    "lambda": lambda k: (lambda t, capa: k(t, capa)),
    "sinif_ornegi": _Sarmal,
}


@pytest.mark.parametrize("sarma", sorted(_SARMALAR))
@pytest.mark.parametrize("yer", ["kosul", "karar"])
def test_dizi_pytest_disinda_gercek_kaynagi_sarmalayan_cagrilabilir_reddedilir(dunya_s, monkeypatch, sarma, yer):
    """A1/A2: gercek kaynagi saran partial / bagli yontem / lambda / sinif ornegi kaynak DEGILDIR; pytest disinda
    (dikis kapali) dizi TypeError verir."""
    kimlik, _ = dunya_s
    h, y = "H2", _y("H2")
    kk, kr = _kaynaklar(h, kimlik)
    monkeypatch.setattr(dizi, "split_modulu", _SplitVekili(_pytest_testi=lambda: None))
    sarili = _SARMALAR[sarma](kk if yer == "kosul" else kr)
    kosul, karar = (sarili, kr) if yer == "kosul" else (kk, sarili)
    with pytest.raises(TypeError, match=yer):
        _dizi_cagir(h, y, kimlik, kosul, karar, _izgara(h, kimlik)[:50])


def test_dizi_kaynak_kumesi_dizinin_kumesiyle_ayni_olmali(dunya_s):
    """A2: KESIF kaynaklariyla `kume='C2'` ya da 'C1' ile kosan dizi kimlik uyusmazligi (ValueError) verir; bilinmeyen
    kume adi ValueError."""
    kimlik, _ = dunya_s
    h, y = "H2", _y("H2")
    kk, kr = _kaynaklar(h, kimlik)
    z = _izgara(h, kimlik)[:50]
    for kume in ("C1", "C2"):
        with pytest.raises(ValueError):
            _dizi_cagir(h, y, kimlik, kk, kr, z, kume=kume)
    with pytest.raises(ValueError):
        _dizi_cagir(h, y, kimlik, kk, kr, z, kume="CX")


@pytest.mark.parametrize("donem_no", [False, 0.0, np.int64(0)])
def test_dizi_donem_no_tamsayi_disi_turde_kimlik_esitligiyle_kabul_edilmez(dunya_s, donem_no):
    """On-kayit §2: `donem_no` negatif olmayan `int`; `False == 0` ya da `0.0 == 0` esitligi kimlik denetimini
    gecirmemeli (TypeError)."""
    kimlik, _ = dunya_s
    h, y = "H2", _y("H2")
    kk, kr = _kaynaklar(h, kimlik)
    with pytest.raises(TypeError):
        _dizi_cagir(h, y, kimlik, kk, kr, _izgara(h, kimlik)[:50], donem_no=donem_no)


@pytest.mark.xfail(strict=True, reason=(
    "S-P2c1-4: `olay_dizisi` `sembol` icin yalnizca `isinstance(str)` ister (kapi `type(sembol) is str` ister); "
    "`__eq__`i her zaman True donen bir `str` alt sinifi kaynak kimligi denetimini (`nesne.kimlik != beklenen`, "
    "demet esitligi) ve `uclu != dizi_kimligi` denetimini gecirir: dizi BASKA bir sembol adi bildirerek kosar. "
    "Gercek olaylar kaynaktan geldigi icin dogrudan hesap sizintisi yok; denetimin degeri dusuyor. ULASIM: KASITLI "
    "kod bicimi (ozel str alt sinifi). Oneri: xfail olarak kayitta kalir; ucuz kapatma: `type(sembol) is str`."))
def test_dizi_yalan_soyleyen_str_alt_sinifini_sembol_olarak_kabul_etmemeli(dunya_s):
    class YalanSembol(str):
        def __eq__(self, diger):
            return True

        def __ne__(self, diger):
            return False

        __hash__ = str.__hash__

    kimlik, _ = dunya_s
    h, y = "H2", _y("H2")
    kk, kr = _kaynaklar(h, kimlik)
    with pytest.raises((TypeError, ValueError)):
        _dizi_cagir(h, y, kimlik, kk, kr, _izgara(h, kimlik)[:120], sembol=YalanSembol("BASKAUSDT"))


@pytest.mark.parametrize("hipotez", ["H2", "H3"])
def test_dizi_esdeger_tipli_yapilandirma_ayni_sonucu_verir(dunya_s, hipotez):
    """A2: kaynaklar kanonik demetle, dizi esdeger tipli demetle (float, np.float64, demet) kosarsa kimlik tutar ve
    sonuc ayni olur (tip farki ayri bir dizi uretmez)."""
    kimlik, _ = dunya_s
    y = _y(hipotez)
    kk, kr = _kaynaklar(hipotez, kimlik, y)
    z = _izgara(hipotez, kimlik)[:200]
    adlar = sinyal.PARAMETRELER[hipotez]
    temel = _ozet(_dizi_cagir(hipotez, y, kimlik, kk, kr, z))
    for v in ({p: float(y[p]) for p in adlar}, {p: np.float64(y[p]) for p in adlar}, tuple(y[p] for p in adlar)):
        assert _ozet(_dizi_cagir(hipotez, v, kimlik, kk, kr, z)) == temel


@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_dizi_donem_disi_barlar_olay_uretmez_kaynagin_gercek_donemi_asilamaz(dunya_s, hipotez):
    """P-C3 / on-kayit §2: cagiran `donem_baslangic/bitis`i kaynagin gercek doneminden GENIS verip donem disi barlar
    sorsa bile (a) dizi hata verir ya da (b) hicbir olay gercek donemin disinda olusmaz."""
    kimlik, _ = dunya_s
    y = _y(hipotez)
    kk, kr = _kaynaklar(hipotez, kimlik, y)
    bas, bitis, _ = pozisyon.donem_kaydi(kimlik["sembol"], 0)
    adim = pencere.adim(config.HIPOTEZ_IZGARASI[hipotez])
    izgara = _izgara(hipotez, kimlik)
    z = pd.DatetimeIndex(sorted(set(izgara) | {bas - k * adim for k in range(1, 40)} | {bitis + k * adim for k in range(1, 40)}))
    sonuc = _cagir(_dizi_cagir, hipotez, y, kimlik, kk, kr, z, donem_baslangic=bas - 100 * adim,
                   donem_bitis=bitis + 100 * adim)
    if isinstance(sonuc, BaseException):
        return                                         # kapali yon: kabul
    assert all(bas <= o.zaman <= bitis for o in sonuc.olaylar)


@pytest.mark.parametrize("hipotez,i", [("H1", -1), ("H2", -2), ("H3", -1)])
def test_dizi_ikinci_dunya_kaynak_ile_referans_kosulu_ayni_dizi(hipotez, i):
    """Hedef 5: ikinci sentetik dunya ve baska yapilandirmalar; kosul kaynagi ile referansin kosulu ayni olay
    zamanlari, capalari ve retleri verir."""
    kimlik, _ = dunya(651, "2021-01-01", "2021-07-31 20:00")
    y = _y(hipotez, i)
    kk, kr = _kaynaklar(hipotez, kimlik, y)
    z = _izgara(hipotez, kimlik)
    a = _ozet(_dizi_cagir(hipotez, y, kimlik, kk, kr, z))
    b = _ozet(_dizi_cagir(hipotez, y, kimlik, lambda t, capa: ref.sinyal_kosulu(
        t, hipotez=hipotez, yapilandirma=y, capa=capa, kume="KESIF", **kimlik), kr, z))
    assert a == b


# =====================================================================================================================
# HEDEF 5 / geleceğe bakis: seri, kapi ve referans arasi tutarlilik
# =====================================================================================================================

@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_uc_yol_kapi_seri_referans_son_yapilandirma_ikinci_dunya(hipotez):
    """G19 / tek kaynak: ikinci dunya ve SON yapilandirma. Kapinin olay rolunde SinyalKosuluSaglanmadi -> False,
    SinyalPenceresiTamDegil -> None, kosuldan SONRAKI adimlarin retleri (UygunDegil, FundingTamDegil) ve onayli
    pozisyon -> True. Izgaranin her 11. bari referansla ayni."""
    kimlik, _ = dunya(652, "2021-02-01", "2021-09-30 20:00")
    y = _y(hipotez, -1)
    izgara = _izgara(hipotez, kimlik)
    capa = pd.DatetimeIndex([t - (1 + i % 12) * H4 for i, t in enumerate(izgara)]) if hipotez == "H1" else None
    kapi = pozisyon.kapi_serisi(hipotez, y, "olay", kume="KESIF", **kimlik, capa=capa)
    kosul = pozisyon.kosul_serisi(hipotez, y, kume="KESIF", **kimlik, capa=capa)
    for i, t in enumerate(izgara):
        s = _cagir(kapi.sonuc, t)
        d = kosul.deger(t)
        if isinstance(s, (pozisyon.UygunDegil, pozisyon.FundingTamDegil, pozisyon.OnaylanmisPozisyon)):
            assert d is True, (hipotez, _tur(s), _tur(d))
        elif isinstance(s, pozisyon.SinyalKosuluSaglanmadi):
            assert d is False, (hipotez, _tur(d))
        elif isinstance(s, pozisyon.SinyalPenceresiTamDegil):
            assert d is None, (hipotez, _tur(d))
    for i in range(0, len(izgara), 11):
        t = izgara[i]
        c = None if capa is None else capa[i]
        a, b = kosul.deger(t), _ref(hipotez, kimlik, t, y, c)
        assert ayni(a, b), (hipotez, _tur(a), _tur(b))


@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_bosluk_ve_bozuk_hucre_komsulugu_yapilandirmalar_referansla_ayni(dunya_s, hipotez):
    """Hedef 5: 3 gunluk bosluk (60-63. gun), tek bar bosluk (100.5), bozuk hucreli bar (120.5) ve donem basi
    komsuluklarinda, yapilandirmalarin ilk, orta ve sonu icin seri referansla ayni. H1'de capali (capa bosluk
    komsuluklarinda) kesitler de."""
    kimlik, _ = dunya_s
    izgara = _izgara(hipotez, kimlik)
    adim = pencere.adim(config.HIPOTEZ_IZGARASI[hipotez])
    bas, _, _ = pozisyon.donem_kaydi(kimlik["sembol"], 0)
    merkezler = [bas + pd.Timedelta(days=g) for g in (0, 60, 63, 100.5, 120.5)]
    kume = set(izgara)
    barlar = sorted({m + k * adim for m in merkezler for k in range(-6, 36, 3)} & kume)
    assert barlar
    n_y = len(sinyal.izgara(hipotez))
    for y in (_y(hipotez, 0), _y(hipotez, n_y // 2), _y(hipotez, -1)):
        seri = _seri(hipotez, kimlik, y)
        for t in barlar:
            a, b = seri.deger(t), _ref(hipotez, kimlik, t, y)
            assert ayni(a, b), (hipotez, _tur(a), _tur(b))
        if hipotez == "H1":
            for m in merkezler[1:]:
                for k in (-2, 0, 1):
                    c = m + k * H4
                    for d in (1, 6, 12):
                        t = c + d * H4
                        a, b = _seri_degeri("H1", kimlik, t, y, c), _ref("H1", kimlik, t, y, c)
                        assert ayni(a, b), (k, d, _tur(a), _tur(b))


@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_t_den_sonraki_barlari_silmek_t_ye_kadarki_satirlari_degistirmez(hipotez):
    """G16 (kesme): t'den SONRAKI butun barlar ve funding silinip donem t'de bitirilirse (delist benzeri) t'ye kadarki
    satirlar ve (H1) capali seri satirlari AYNI kalir."""
    kimlik, _ = dunya(653, BAS, BITIS)
    izgara = _izgara(hipotez, kimlik)
    adim = pencere.adim(config.HIPOTEZ_IZGARASI[hipotez])
    t = izgara[int(len(izgara) * 0.6)]
    kesim = t + adim
    m, f = SENTETIK_VERI[kimlik["sembol"]]
    b, s, fy = SENTETIK_DONEMLER[(kimlik["sembol"], 0)]
    m2 = m.loc[pd.DatetimeIndex(m["open_time"]) < kesim].reset_index(drop=True)
    f2 = f.loc[pd.DatetimeIndex(f["odeme_zamani"]) <= kesim].reset_index(drop=True)
    yeni = veri(m2, f2, b, m2["open_time"].iloc[-1], ham=True, funding_yok=fy)
    ra = [(x, v) for x, v in zip(*_satirlar(_seri(hipotez, kimlik))) if x <= t]
    rb = [(x, v) for x, v in zip(*_satirlar(_seri(hipotez, yeni))) if x <= t]
    assert ra and ra == rb
    if hipotez == "H1":
        p = t - 5 * H4
        ca = [(x, v) for x, v in zip(*_satirlar(_seri("H1", kimlik, capa=p))) if x <= t]
        cb = [(x, v) for x, v in zip(*_satirlar(_seri("H1", yeni, capa=p))) if x <= t]
        assert ca and ca == cb


@pytest.mark.parametrize("tur", ["absurd", "dolgu"])
@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_donem_sonuna_gelecek_tarihli_ya_da_dolgu_bar_eklemek_satirlari_degistirmez(hipotez, tur):
    """G16 / on-kayit §2 (dolgu barlar): donem bitisinden SONRA eklenen 60 bar (absurt fiyat ya da sifir hacimli
    dolgu) seri satirlarini ve donem disi t'nin `None` degerini degistirmez."""
    kimlik, _ = dunya(654, BAS, BITIS)

    def ekle(m, f):
        son = m["open_time"].iloc[-1]
        z = pd.date_range(son + H4, periods=60, freq=H4)
        ek = pd.concat([m.iloc[[-1]]] * 60, ignore_index=True)
        ek["open_time"] = z
        ek["close_time"] = z + H4 - pd.Timedelta(milliseconds=1)
        if tur == "absurd":
            ek = _olcekle(ek, np.ones(len(ek), dtype=bool), 40.0)
        else:
            sabit = float(m["close"].iloc[-1])
            for alan in OHLC:
                ek[alan] = sabit
            ek["volume"] = 0.0
            ek["quote_volume"] = 0.0
        return pd.concat([m, ek], ignore_index=True), f

    yeni = _turetilmis(kimlik, ekle)
    a, b = _seri(hipotez, kimlik), _seri(hipotez, yeni)
    assert _satirlar(a) == _satirlar(b) and a.zamanlar().size
    t_disi = pd.Timestamp("2021-09-02 00:00", tz="UTC")
    assert a.deger(t_disi) is None and b.deger(t_disi) is None
    if hipotez == "H1":
        p = a.zamanlar()[-3]
        assert _satirlar(_seri("H1", kimlik, capa=p)) == _satirlar(_seri("H1", yeni, capa=p))


@pytest.mark.parametrize("sira", ["ters", "karisik"])
@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_veri_sirasi_ters_ya_da_karisik_ise_ya_hata_ya_ayni_satirlar(hipotez, sira):
    """Hedef 'seriyi ters/karisik ver': kapi sirasiz mum cercevesini reddeder (veri/deger hatasi) ya da sirali
    veriyle AYNI satirlari verir; sessizce farkli deger vermez."""
    kimlik, _ = dunya(655, BAS, BITIS)

    def boz(m, f):
        if sira == "ters":
            return m.iloc[::-1], f.iloc[::-1]
        return m.sample(frac=1.0, random_state=11), f.sample(frac=1.0, random_state=12)

    yeni = _turetilmis(kimlik, boz)
    sonuc = _cagir(_seri, hipotez, yeni)
    if isinstance(sonuc, (ValueError, KeyError)):
        return                                         # kapali yon
    assert not isinstance(sonuc, BaseException), _tur(sonuc)
    assert _satirlar(sonuc) == _satirlar(_seri(hipotez, kimlik))


@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_karar_kaynagi_t_den_sonraki_veri_bozulunca_erken_retler_degismez(hipotez):
    """G16 (uygunluk dahil): t'den SONRAKI fiyat ve hacim x2.7 olunca, t'ye kadarki barlarin 'erken' retleri
    (SinyalBariYok, SinyalPenceresiTamDegil, SinyalKosuluSaglanmadi, UygunDegil) iki dunyada AYNI sinif ve mesajdir;
    bir dunyada erken ret, digerinde baska sonuc olamaz."""
    kimlik, _ = dunya(656, BAS, BITIS)
    izgara = _izgara(hipotez, kimlik)
    adim = pencere.adim(config.HIPOTEZ_IZGARASI[hipotez])
    t0 = izgara[int(len(izgara) * 0.5)]
    kesim = t0 + adim
    yeni = _turetilmis(kimlik, lambda m, f: (_olcekle(m, pd.DatetimeIndex(m["open_time"]) >= kesim, 2.7), f))
    _, kr_a = _kaynaklar(hipotez, kimlik)
    _, kr_b = _kaynaklar(hipotez, yeni)
    erken = (pozisyon.SinyalKosuluSaglanmadi, pozisyon.SinyalPenceresiTamDegil, pozisyon.UygunDegil,
             pozisyon.SinyalBariYok)
    for t in [x for x in izgara if x <= t0][::5]:
        capa = t - 3 * H4 if hipotez == "H1" else None
        a, b = _cagir(kr_a, t, capa), _cagir(kr_b, t, capa)
        if isinstance(a, erken) or isinstance(b, erken):
            assert ayni(a, b), (hipotez, _tur(a), _tur(b))


@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_gecersiz_t_degerleri_seri_ve_kaynakta_sessizce_None_donmez(dunya_s, hipotez):
    """A4: None, NaT, nan, 'NaT', saat dilimsiz Timestamp / np.datetime64 / dizge ve tamsayi t: `deger`, `icerir` ve
    kaynak cagrisi hata verir; 'hesaplanamaz' (`None`) ya da `False` DONMEZ."""
    kimlik, _ = dunya_s
    seri = _seri(hipotez, kimlik)
    kk, _ = _kaynaklar(hipotez, kimlik)
    kotu = [None, pd.NaT, float("nan"), "NaT", pd.Timestamp("2021-03-01"), np.datetime64("2021-03-01T00:00"),
            1614556800, "2021-03-01 00:00:00"]
    for t in kotu:
        for f in (lambda: seri.deger(t), lambda: seri.icerir(t), lambda: kk(t, None)):
            sonuc = _cagir(f)
            assert isinstance(sonuc, BaseException), (_tur(t), _tur(sonuc))
