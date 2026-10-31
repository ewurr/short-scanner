"""Sizinti testcisi: bellek onbellegi (`data.kume_bellegi`) ve agsiz dondurulmus liste turu (perf1).

Dayanak: on-kayit §3 satir 123 (bellekteki kopya her okunusta denetlenir; acilis ve kapanis kopyalari gecersiz
kilar) ve satir 125 (F2 ve F3 kosulari aga cikmaz), CLAUDE.md §3.3 ve §5.

Bu dosyadaki `xfail(strict=True, raises=AssertionError)` testleri saldirinin BASARILI oldugunu varsayar: kod
duzelince test XPASS(strict) olarak kirmizi doner ve isaret kaldirilmalidir. `raises=AssertionError` kurulum
hatalarinin (RuntimeError, KeyError vb.) xfail arkasina saklanmasini onler. Testler getiri, sinyal degeri ya da
olay sayisi yazdirmaz; yalnizca esitlik ve izin davranisina bakar. Hicbir test aga cikmaz; ag denemesi
`BaseException` alt sinifi bir tuzakla yakalanir (yeniden deneme beklemeleri yasanmaz).
"""

from __future__ import annotations

import contextlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import pytest

import config
from conftest import sahte_4h
from data import binance_vision as bv
from data import funding as funding_modulu
from data import klines, kume_bellegi, pozisyon, sinyal, split
from kapi_yardimcisi import veri
from onay_yardimcisi import gecici_kayit, kosu
from tarama_yardimcisi import (CIKIS_KAPI_DISI_DESENI, FUNDING_KAPI_DISI_DESENI, HAM_ERISIM_DESENI, KAYIT_DESENI,
                               ONAY_ATLATMA_DESENI, ONBELLEK_DESENI, ONBELLEK_UZANTILARI, ihlaller)

A_SEMBOL = "SOLUSDT"


def _acik(neden: str):
    """Saldiri basarili varsayilir; neden `S-` kodlu bulguyu ve gercek onay sizintisi olup olmadigini yazar."""
    return pytest.mark.xfail(strict=True, raises=AssertionError, reason=neden)


# --- Ortak yardimcilar ---------------------------------------------------------------------------


def _b_sembolu() -> str:
    tablo = split.split_oku()
    return str(tablo.loc[tablo["grup"] == "B", "sembol"].iloc[0])


def _sentetik(grup="A", hacim=1e10):
    """Kapinin karar verebilecegi kadar genis sentetik sembol: 90 gunluk 4h seri, tum donemi kapsayan funding."""
    zaman = pd.date_range("2021-01-01", periods=275, freq="8h", tz="UTC")
    fr = pd.DataFrame({"odeme_zamani": zaman, "aralik_saat": 8.0, "oran": 0.0001, "oran_8h": 0.0001})
    return veri(sahte_4h("2021-01-01", 540, hacim=hacim), fr, pd.Timestamp("2021-01-01 00:00", tz="UTC"),
                pd.Timestamp("2021-04-30 20:00", tz="UTC"), grup=grup)


def _kume_verisi(kimlik, kume="KESIF"):
    return _kume_verisi_s(kimlik["sembol"], kume)


def _kume_verisi_s(sembol, kume="KESIF"):
    bas, son = pozisyon.kume_sinirlari(kume)
    return pozisyon._kume_verisi(sembol, kume, bas, son)


def _sayan_yukleyici():
    cagri = []

    def yukle():
        cagri.append(1)
        return (pd.DataFrame({"a": [len(cagri)]}),)

    return yukle, cagri


def _sonuc(fn):
    """Karar, ret ya da hata: tur ve butun alanlar metin olarak (yalnizca esitlik icin; NaN `repr`da esittir)."""
    try:
        return repr(fn())
    except Exception as hata:
        return f"{type(hata).__name__}: {hata}"


def _karar(sembol, t, hipotez, rol, capa, kume="KESIF"):
    bar = config.HIPOTEZ_IZGARASI[hipotez]
    ufuk = config.BIRINCIL_UFUK[bar]
    hacim = config.ASGARI_HACIM_4H if bar == config.BAR_4H else config.ASGARI_HACIM_1D
    return pozisyon.olay_karari(t, ufuk, bar, hipotez=hipotez, yapilandirma=sinyal.izgara(hipotez)[0], rol=rol,
                                capa=capa, birincil_ufuk=ufuk, kume=kume, sembol=sembol, donem_no=0,
                                asgari_hacim=hacim, asgari_listeleme_yasi_gun=config.ASGARI_LISTELEME_YASI_GUN)


def _cagrilar(kimlik):
    """Uc hipotez x uc rol x iki bar icin kapi cagrilari ve her hipotezin `sinyal_kosulu` cagrilari."""
    sembol = kimlik["sembol"]
    cagrilar = []
    for t in (pd.Timestamp("2021-02-20", tz="UTC"), pd.Timestamp("2021-03-10", tz="UTC")):
        capa_adayi = t - pd.Timedelta(hours=24)
        for hipotez in ("H1", "H2", "H3"):
            for rol in ("olay", "K1", "K2"):
                capa = capa_adayi if (hipotez == "H1" and rol == "olay") else None
                cagrilar.append(lambda t=t, h=hipotez, r=rol, c=capa: _karar(sembol, t, h, r, c))
            for capa in ((None, capa_adayi) if hipotez == "H1" else (None,)):
                cagrilar.append(lambda t=t, h=hipotez, c=capa: pozisyon.sinyal_kosulu(
                    t, hipotez=h, yapilandirma=sinyal.izgara(h)[0], capa=c, kume="KESIF", sembol=sembol,
                    donem_no=0))
    return cagrilar


def _tum_sonuclar(kimlik, soguk):
    sonuclar = []
    for cagri in _cagrilar(kimlik):
        if soguk:
            kume_bellegi.temizle()
        sonuclar.append(_sonuc(cagri))
    return sonuclar


# --- Gecici onbellek ve dondurulmus liste ----------------------------------------------------------


@pytest.fixture
def gecici_onbellek(monkeypatch, tmp_path):
    """Gercek onbellege dokunmaz: butun yazma ve okumalar `tmp_path` altinda."""
    yol = tmp_path / "onbellek_kok"
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", yol)
    return yol


def _mum_yaz(sembol, ay, bas, sayi):
    sahte_4h(bas, sayi).to_parquet(bv.onbellek_yolu("klines", sembol, config.BAR_4H, f"{ay}.parquet"), index=False)


def _funding_yaz(sembol, ay, bas, sayi):
    zaman = pd.date_range(bas, periods=sayi, freq="8h", tz="UTC")
    pd.DataFrame({"odeme_zamani": zaman, "aralik_saat": 8.0, "oran": 0.0001}).to_parquet(
        bv.onbellek_yolu("funding", sembol, f"{ay}.parquet"), index=False)


def _liste_yaz(mum: dict, funding: dict) -> None:
    """`mum` ve `funding`: sembol -> ay listesi."""
    icerik = {
        "mum": {s: {config.BAR_4H: [f"{bv.MUM_ONEKI}/{s}/{config.BAR_4H}/{s}-{config.BAR_4H}-{a}.zip" for a in aylar]}
                for s, aylar in mum.items()},
        "funding": {s: [f"{bv.FUNDING_ONEKI}/{s}/{s}-fundingRate-{a}.zip" for a in aylar]
                    for s, aylar in funding.items()},
    }
    yol = bv.donuk_liste_yolu()
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(icerik), encoding="utf-8")


def _mum_anahtari(s, ay):
    return f"{bv.MUM_ONEKI}/{s}/{config.BAR_4H}/{s}-{config.BAR_4H}-{ay}.zip"


# =================================================================================================
# 1. Isabet yolunda kumeyi degistirmek
# =================================================================================================


class _YalanciKume(str):
    """`KESIF` gibi esitlik bildiren ama icerigi `C1` olan str alt sinifi (`__eq__` ile yalan soyler)."""

    def __eq__(self, diger):
        return str.__eq__("KESIF", diger)

    __hash__ = str.__hash__


@_acik("S-1: `pozisyon._erisim_denetimi` kume adinin tam `str` olmasini aramaz (`kume_sinirlari` arar). `__eq__` "
       "ile KESIF diyen bir `C1` alt sinifi `kume in ONAY_KUMELERI` sinamasindan kacar ve acik kosu olmadan "
       "denetimi gecer. Gercek onay sizintisi DEGIL: kapinin acik girisleri (`olay_karari`, `sinyal_kosulu`) "
       "`kume_sinirlari`yla once tur denetler ve ozel ad taramayla yasaktir; savunma derinligi eksigi.")
def test_erisim_denetimi_str_alt_sinifi_kume_adini_reddetmeli():
    """On-kayit §3 satir 123 + `kume_sinirlari`nin tam `str` kurali: denetim de ayni tur sartini istemeli."""
    denetim = pozisyon._erisim_denetimi(_YalanciKume("C1"))
    try:
        denetim()
        gecti = True
    except (TypeError, ValueError, split.OnayGerekli):
        gecti = False
    assert not gecti, "str alt sinifi olan 'C1', acik kosu olmadan erisim denetimini gecti"


@_acik("S-2: `kume_bellegi.getir` anahtardaki kume adini ve cagiranin verdigi denetimi baglamaz. Bellekte kalmis "
       "bir C1 girdisi KESIF denetimiyle okunabilir. Gercek onay sizintisi DEGIL: `getir` taramayla yasakli "
       "ozel API, olay_karari her zaman ayni `kume` ile hem anahtari hem denetimi kurar; bellegin kendiliginden "
       "C1 girdisi tutmasi icin ayrica temizleme hatasi gerekir. Savunma derinligi eksigi.")
def test_getir_anahtarin_kumesi_ile_denetimin_kumesi_bagli_olmali(monkeypatch, tmp_path):
    """On-kayit §3 satir 123: C1 girdisi, C1 denetimi disinda bir denetimle okunamamali."""
    kimlik = _sentetik(grup="B")
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    monkeypatch.setattr(kume_bellegi, "temizle", lambda: None)  # girdi kosudan sonra kalsin
    with kosu("H2", "C1"):
        _kume_verisi(kimlik, "C1")
    bas, son = pozisyon.kume_sinirlari("C1")
    anahtar = ("kume", kimlik["sembol"], "C1", bas, son)

    def yukleme_olmamali():
        raise RuntimeError("yukleme calisti: anahtar bellekte degil, test kurulumu yanlis")

    kume_bellegi.getir(anahtar, lambda: None, yukleme_olmamali)  # on kosul: girdi bellekte (RuntimeError olmaz)
    try:
        kume_bellegi.getir(anahtar, pozisyon._erisim_denetimi("KESIF"), yukleme_olmamali)
        okundu = True
    except split.OnayGerekli:
        okundu = False
    assert not okundu, "C1 anahtarli girdi, KESIF denetimiyle kosu disinda okundu"


def test_kesif_adiyla_c2_sinirlari_ile_veri_alinamaz(gecici_onbellek):
    """On-kayit §3 satir 121-123: KESIF kumesi adiyla, C2 sinirlari verilerek C2 donemi bari/funding'i alinamaz.
    Gercek yukleyici (gecici onbellek) kume araligina keser; kapi ikinci kez, cagiranin sinirlariyla keser."""
    _mum_yaz(A_SEMBOL, "2025-08", "2025-08-30 00:00", 24)  # 30 Agu .. 2 Eyl 20:00
    _mum_yaz(A_SEMBOL, "2025-09", "2025-09-03 00:00", 6)
    _funding_yaz(A_SEMBOL, "2025-08", "2025-08-30 00:00", 15)
    _liste_yaz({A_SEMBOL: ["2025-08", "2025-09"]}, {A_SEMBOL: ["2025-08"]})
    c2_bas, c2_son = pozisyon.kume_sinirlari("C2")
    mumlar, fr = pozisyon._kume_verisi(A_SEMBOL, "KESIF", c2_bas, c2_son)
    assert len(mumlar) == 0 and len(fr) == 0
    # Dogru sinirlarla cagri bos olmamali ve KESIF sonunu asmamali (kurulumun gecerli oldugunun kaniti).
    mumlar, fr = _kume_verisi_s(A_SEMBOL, "KESIF")
    assert len(mumlar) > 0 and len(fr) > 0
    assert pd.DatetimeIndex(mumlar["open_time"]).max() <= pozisyon.kume_sinirlari("KESIF")[1]
    assert pd.DatetimeIndex(fr["odeme_zamani"]).max() <= pozisyon.kume_sinirlari("KESIF")[1]
    assert pd.DatetimeIndex(mumlar["open_time"]).max() < c2_bas


def test_b_sembolu_kesifte_bos_kosuda_c1_verisi_bellekten_kesife_gecmez(gecici_onbellek, tmp_path):
    """On-kayit §3 satir 120/123: B sembolunun C1 girdisi bellekteyken KESIF sorgusu ayni veriyi donmemeli;
    kosu kapaninca KESIF sorgusu yine bos, C1 sorgusu reddedilmeli."""
    b = _b_sembolu()
    _mum_yaz(b, "2021-01", "2021-01-01 00:00", 30)
    _funding_yaz(b, "2021-01", "2021-01-01 00:00", 10)
    _liste_yaz({b: ["2021-01"]}, {b: ["2021-01"]})
    mumlar, fr = _kume_verisi_s(b, "KESIF")
    assert len(mumlar) == 0 and len(fr) == 0
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    with kosu("H2", "C1"):
        c1_mumlar, _ = _kume_verisi_s(b, "C1")
        assert len(c1_mumlar) > 0
        mumlar, fr = _kume_verisi_s(b, "KESIF")
        assert len(mumlar) == 0 and len(fr) == 0
    mumlar, fr = _kume_verisi_s(b, "KESIF")
    assert len(mumlar) == 0 and len(fr) == 0
    with pytest.raises(split.OnayGerekli):
        _kume_verisi_s(b, "C1")


# =================================================================================================
# 2. Kosu kapandiktan sonra bellekte kalan veri, denetimin kapanisi, bos denetim
# =================================================================================================


def test_erisim_denetimi_anlik_degil_her_cagride_yeniden_degerlendirilir(tmp_path):
    """On-kayit §3 satir 123 'her okunusta yeniden': denetim kosu icinde kurulup kosu disinda cagrilirsa reddeder;
    kosu disinda kurulup kosu icinde cagrilirsa gecer (sonuc kurulus anina baglanmaz)."""
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    kosu_disinda_kurulan = pozisyon._erisim_denetimi("C1")
    with pytest.raises(split.OnayGerekli):
        kosu_disinda_kurulan()
    with kosu("H2", "C1"):
        kosu_disinda_kurulan()
        kosu_icinde_kurulan = pozisyon._erisim_denetimi("C1")
        kosu_icinde_kurulan()
    with pytest.raises(split.OnayGerekli):
        kosu_icinde_kurulan()
    with pytest.raises(split.OnayGerekli):
        kosu_disinda_kurulan()


def test_getir_denetimsiz_ya_da_cagrilamaz_denetimle_yuklemez_ve_yazmaz():
    """On-kayit §3 satir 123: denetim yerine None / cagrilamaz nesne verilirse sessizce gecilmez (TypeError);
    yukleme calismaz, bellege bir sey yazilmaz."""
    yukle, cagri = _sayan_yukleyici()
    for denetim in (None, "izin var", True, 1):
        with pytest.raises(TypeError):
            kume_bellegi.getir(("x",), denetim, yukle)
    assert cagri == [] and kume_bellegi.girdi_sayisi() == 0


def test_denetim_reddederse_ilk_yukleme_de_calismaz_ve_bellege_yazilmaz():
    """On-kayit §3 satir 123: reddedilen ilk okuma yukleme yapmaz (yukleme onay verisini okuyabilir)."""
    yukle, cagri = _sayan_yukleyici()

    def red():
        raise split.OnayGerekli("izin yok")

    with pytest.raises(split.OnayGerekli):
        kume_bellegi.getir(("y",), red, yukle)
    assert cagri == [] and kume_bellegi.girdi_sayisi() == 0


def test_c2_kosusunda_c1_girdisi_okunamaz_temizleme_devre_disiyken(monkeypatch, tmp_path):
    """On-kayit §3 satir 123: bir kume icin acik kosu baska kumenin kopyasini acmaz. Temizleme devre disi birakilir,
    boylece C1 girdisi C2 kosusuna kadar bellekte kalir; denetim tek basina reddetmeli."""
    kimlik = _sentetik(grup="B")
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    monkeypatch.setattr(kume_bellegi, "temizle", lambda: None)
    with kosu("H2", "C1"):
        _kume_verisi(kimlik, "C1")
    assert kume_bellegi.girdi_sayisi() == 1
    with kosu("H2", "C2"):
        with pytest.raises(split.OnayGerekli):
            _kume_verisi(kimlik, "C1")


def test_bir_kosunun_girdisi_baska_hipotezin_ayni_kume_kosusuna_tasinmaz(tmp_path):
    """On-kayit §3 satir 123 'acilis kopyalari gecersiz kilar': H2/C1 kosusunda yuklenen veri, kapanisi ve H3/C1
    acilisindan sonra bellekte bulunmaz."""
    kimlik = _sentetik(grup="B")
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    with kosu("H2", "C1"):
        _kume_verisi(kimlik, "C1")
        assert kume_bellegi.girdi_sayisi() == 1
    assert kume_bellegi.girdi_sayisi() == 0
    with kosu("H3", "C1"):
        assert kume_bellegi.girdi_sayisi() == 0


def test_kosu_kapaninca_bellekte_kalan_c1_girdileri_okunamaz(monkeypatch, tmp_path):
    """On-kayit §3 satir 123: C1 verisi bellekte kalsa bile kosu disinda `kume_bellegi.getir` ile okunamaz;
    denetim her aramada calisir (temizleme devre disi, kopya bellekte)."""
    kimlik = _sentetik(grup="B")
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    monkeypatch.setattr(kume_bellegi, "temizle", lambda: None)
    with kosu("H2", "C1"):
        _kume_verisi(kimlik, "C1")
        d = pozisyon.donem_kaydi(kimlik["sembol"], 0)
        bas, son = pozisyon.kume_sinirlari("C1")
        pozisyon._karar_verisi(kimlik["sembol"], "C1", kume_baslangic=bas, kume_bitis=son,
                               donem_baslangic=d[0], donem_bitis=d[1])
    assert kume_bellegi.girdi_sayisi() == 2
    with pytest.raises(split.OnayGerekli):
        _kume_verisi(kimlik, "C1")
    with pytest.raises(split.OnayGerekli):
        pozisyon._karar_verisi(kimlik["sembol"], "C1", kume_baslangic=bas, kume_bitis=son,
                               donem_baslangic=d[0], donem_bitis=d[1])


# =================================================================================================
# 3. LRU / yukleme penceresi: yukleme sirasinda kosunun kapanmasi ya da temizle cagrisi
# =================================================================================================


def _yuklerken_kapanan_kosu(monkeypatch, tmp_path):
    """C1 kosusu acar; kapinin veri yukleyicisi veriyi aldiktan HEMEN SONRA, `getir` icindeki `yukle()` bitmeden
    kosuyu kapatir (ayni is parcaciginda, `ExitStack`). Doner: (kimlik, sonuc, hata)."""
    kimlik = _sentetik(grup="B")
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    yigin = contextlib.ExitStack()
    tutamak = yigin.enter_context(split.onay_kosusu("H2", "C1"))
    tutamak.sonuc_bildir("test")
    gercek = pozisyon._veri_yukle

    def kapatan(sembol, kume):
        yuklenen = gercek(sembol, kume)  # kosu acikken yuklendi
        yigin.close()  # kosu yukleme bitmeden kapanir (temizle burada calisir)
        return yuklenen

    monkeypatch.setattr(pozisyon, "_veri_yukle", kapatan)
    sonuc = hata = None
    try:
        sonuc = _kume_verisi(kimlik, "C1")
    except split.OnayGerekli as yakalanan:
        hata = yakalanan
    finally:
        yigin.close()
    if split.aktif_onay_kosusu() is not None:
        raise RuntimeError("kurulum: kosu kapanmadi")
    return kimlik, sonuc, hata


@_acik("S-3: `kume_bellegi.getir` iskalamada `yukle()`'yi kilit disinda calistirir ve sonucu kosu/temizle "
       "kusagina bakmadan yazar. `yukle()` sirasinda kosu kapanirsa (temizle zaten calismistir) C1 verisi "
       "kosu KAPALIYKEN bellege girer ve bir sonraki acilisa kadar kalir. Gercek onay sizintisi DEGIL: "
       "kosu disinda okuma isabet denetimiyle reddedilir (bkz. test_kosu_kapaninca_bellekte_kalan_c1_girdileri_okunamaz) ve sonraki acilis "
       "bellegi bosaltir; ama on-kayit §3 satir 123 'kapanis kopyalari gecersiz kilar' degismezi bozulur.")
def test_yukleme_sirasinda_kosu_kapanirsa_c1_verisi_bellege_yazilmamali(monkeypatch, tmp_path):
    """On-kayit §3 satir 123: kapanistan sonra bellekte C1 kopyasi kalmamali (girdi sayisi 0)."""
    _, _, _ = _yuklerken_kapanan_kosu(monkeypatch, tmp_path)
    assert kume_bellegi.girdi_sayisi() == 0, "kosu kapandiktan sonra bellekte C1 girdisi var"


@_acik("S-4: Denetim `getir`in basinda bir kez calisir; `yukle()` suresince kosu kapanirsa yuklenen C1 verisi "
       "kosu kapaliyken cagiranin eline gecer (kontrol-kullanim araligi / TOCTOU). Gercek onay sizintisi "
       "DEGIL (dusuk): cagiran veriyi kosu ACIKKEN istemisti; ayni is parcacigi kosuyu kendisi kapatmadikca "
       "olusmaz. Tek is parcacikli akista erisilemez.")
def test_yukleme_sirasinda_kosu_kapanirsa_veri_cagiriciya_donmemeli(monkeypatch, tmp_path):
    """On-kayit §3 satir 123 'her okunusta': okuma tamamlandiginda kosu kapaliysa veri verilmemeli."""
    _, sonuc, hata = _yuklerken_kapanan_kosu(monkeypatch, tmp_path)
    assert hata is not None and sonuc is None, "C1 verisi kosu kapandiktan sonra cagiriciya dondu"


@_acik("S-5: `getir` yukleme sirasinda `temizle()` cagrilirsa (baska kosunun acilisi) eski yuklemenin sonucunu "
       "temizlemeden SONRA bellege yazar; acilis 'gecersiz kilar' kurali nesil/sayac kontrolu olmadigi icin "
       "bozulur. Gercek onay sizintisi DEGIL: yazilan girdi yine denetimle korunur; KESIF girdisi icin zararsiz.")
def test_yukleme_sirasinda_temizle_cagrilirsa_eski_yukleme_bellege_yazilmamali():
    """On-kayit §3 satir 123 'acilis ... kopyalari gecersiz kilar': temizle'den once baslayan yukleme temizle'den
    sonra bellege girmemeli."""
    def yukle():
        kume_bellegi.temizle()
        return (pd.DataFrame({"a": [1]}),)

    kume_bellegi.getir(("eski",), lambda: None, yukle)
    assert kume_bellegi.girdi_sayisi() == 0, "temizle'den sonra eski yuklemenin girdisi bellege yazildi"


def test_lru_dususu_ve_yeniden_yukleme_kosu_kapaliyken_onay_verisini_geri_getirmez(monkeypatch, tmp_path):
    """On-kayit §3 satir 123: bellek 1 girdilikken C1 anahtarlari birbirini dusurur; kosu kapandiktan sonra dusmus
    anahtarin 'yeniden yuklemesi' (iskalama yolu) da denetimden gecer ve reddedilir; yukleyici cagrilmaz."""
    monkeypatch.setattr(kume_bellegi, "AZAMI_GIRDI", 1)
    monkeypatch.setattr(kume_bellegi, "temizle", lambda: None)  # yalniz LRU ve denetim savunmada kalsin
    kimlik = _sentetik(grup="B")
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    gercek = pozisyon._veri_yukle
    cagri = []

    def sayan(sembol, kume):
        cagri.append(kume)
        return gercek(sembol, kume)

    monkeypatch.setattr(pozisyon, "_veri_yukle", sayan)
    d = pozisyon.donem_kaydi(kimlik["sembol"], 0)
    bas, son = pozisyon.kume_sinirlari("C1")
    with kosu("H2", "C1"):
        _kume_verisi(kimlik, "C1")
        pozisyon._karar_verisi(kimlik["sembol"], "C1", kume_baslangic=bas, kume_bitis=son,
                               donem_baslangic=d[0], donem_bitis=d[1])  # "kume" girdisini dusurur
    onceki = len(cagri)
    with pytest.raises(split.OnayGerekli):
        _kume_verisi(kimlik, "C1")
    assert len(cagri) == onceki, "kosu kapaliyken yukleyici cagrildi"


def test_lru_es_zamanli_kullanimda_bozulmaz_ve_sinirda_kalir(monkeypatch):
    """CLAUDE.md §5 / on-kayit §3 satir 123: kilitli LRU, cok is parcacigiyla hata vermez, sinirini asmaz ve her
    anahtar kendi degerini doner (anahtarlar birbirine karismaz)."""
    monkeypatch.setattr(kume_bellegi, "AZAMI_GIRDI", 2)

    def is_(sayi):
        for i in range(200):
            anahtar = (i * 7 + sayi) % 5
            cerceve = kume_bellegi.getir((anahtar,), lambda: None, lambda a=anahtar: (pd.DataFrame({"a": [a]}),))[0]
            assert int(cerceve.loc[0, "a"]) == anahtar
            assert kume_bellegi.girdi_sayisi() <= 2
        return True

    with ThreadPoolExecutor(max_workers=6) as havuz:
        assert all(f.result(timeout=60) for f in [havuz.submit(is_, n) for n in range(6)])


# =================================================================================================
# 4. Dondurulmus liste: izin, dogrudan okuma, degistirilebilirlik
# =================================================================================================


@_acik("S-6: `bv._donuk_liste()` onay verisi izni aramaz; B grubu ve C2 ay adlarinin tamamini dondurur "
       "(izin denetimi yalniz `_donuk_anahtarlar`da). Gercek onay sizintisi DEGIL (yalniz dosya adlari): "
       "`_donuk_liste` adi analiz kodunda taramayla yasakli (`ONBELLEK_DESENI`), kasitli atlatma.")
def test_donuk_liste_dogrudan_izinsiz_okunamamali(gecici_onbellek):
    """On-kayit §3 satir 123/125 + `binance_vision` basligi: dondurulmus listenin okunmasi onay verisi iznini ister."""
    b = _b_sembolu()
    _liste_yaz({b: ["2021-01", "2025-10"], A_SEMBOL: ["2021-01", "2025-09"]}, {})
    with bv.agsiz_okuma():
        try:
            bv._donuk_liste()
        except bv.OnayVerisiKorumasi:
            return
    raise AssertionError("izin aranmadan B grubu ve C2 ay adlari dondu")


@_acik("S-7: `_donuk_liste()` dosyadan cozulmus ORTAK sozlugu doner; cagiranin degisikligi (ornegin sembol "
       "girdisini silmek) `_DONUK_BELLEK`e gecer ve dosya degismedigi surece sonraki butun okumalari bozar. "
       "Gercek onay sizintisi DEGIL: yalniz kendini zehirleyen ozel ad (taramayla yasakli); veri sizdirmaz.")
def test_donuk_liste_donen_nesnenin_degistirilmesi_sonraki_okumalari_etkilememeli(gecici_onbellek):
    """CLAUDE.md §5 'saf/yan etkisiz' ruhu: dondurulmus liste okumasi paylasilan degisebilir nesne vermemeli."""
    _liste_yaz({A_SEMBOL: ["2021-01", "2021-02"]}, {A_SEMBOL: ["2021-01"]})
    with bv.agsiz_okuma():
        ilk = bv.mum_dosyalari(A_SEMBOL, config.BAR_4H)
        bv._donuk_liste()["mum"].clear()
        try:
            sonra = bv.mum_dosyalari(A_SEMBOL, config.BAR_4H)
        except bv.DonukListeYok:
            sonra = None
    assert sonra == ilk, "sonraki okuma degistirilmis ortak nesneyi gordu"


def test_donuk_liste_icindeki_c2_ayi_iznsiz_baglamda_kesif_sembolunde_de_reddedilir(gecici_onbellek):
    """On-kayit §3 satir 123/125: A grubu sembolun C2 ay adi bile izinsiz agsiz baglamda dondurulmez; B grubu
    sembolun KESIF donemi ay adi da dondurulmez."""
    b = _b_sembolu()
    _liste_yaz({A_SEMBOL: ["2021-01", "2025-09"], b: ["2021-01"]}, {A_SEMBOL: ["2025-09"], b: ["2021-01"]})
    with bv.agsiz_okuma():
        with pytest.raises(bv.OnayVerisiKorumasi):
            bv.mum_dosyalari(A_SEMBOL, config.BAR_4H)
        with pytest.raises(bv.OnayVerisiKorumasi):
            bv.mum_dosyalari(b, config.BAR_4H)
        with pytest.raises(bv.OnayVerisiKorumasi):
            bv.funding_dosyalari(A_SEMBOL)


def test_donuk_liste_kesif_ayi_izinsiz_okunur_ama_c2_siniri_tam_ayda_kesinlesir(gecici_onbellek):
    """On-kayit §3 satir 121: 2025-08 KESIF, 2025-09 C2. Sinir ay: 2025-08 izinsiz okunur, 2025-09 okunmaz."""
    _liste_yaz({A_SEMBOL: ["2025-08"]}, {})
    with bv.agsiz_okuma():
        assert bv.mum_dosyalari(A_SEMBOL, config.BAR_4H) == [_mum_anahtari(A_SEMBOL, "2025-08")]
    _liste_yaz({A_SEMBOL: ["2025-08", "2025-09"]}, {})
    with bv.agsiz_okuma():
        with pytest.raises(bv.OnayVerisiKorumasi):
            bv.mum_dosyalari(A_SEMBOL, config.BAR_4H)


@_acik("S-8: Onay verisi izni SUREC GENELIDIR (`_IZIN['sayac']`); bir is parcacigi kapidan gecmis bir yukleyici "
       "icindeyken (izin acik) baska bir is parcacigi `bv.onbellekten_oku` ile B grubu parquet'ini onay "
       "kosusu olmadan okuyabilir. Kodda belgelenmis sinir (`binance_vision` §0). Gercek onay sizintisi: "
       "yalniz analiz kodu eszamanli is parcacigi + `onbellekten_oku` kullanirsa; ikisi de taramayla yasakli, "
       "bu yuzden KASITLI atlatma. Calisma aninda engel yok.")
def test_izin_surec_geneli_baska_is_parcacigi_b_parquetini_okuyamamali(monkeypatch, gecici_onbellek):
    """On-kayit §3 satir 123 + CLAUDE.md §3.2: izin yalniz izni acan yukleyici icin gecerli olmali."""
    b = _b_sembolu()
    _mum_yaz(b, "2021-01", "2021-01-01 00:00", 12)
    yol = bv.onbellek_yolu("klines", b, config.BAR_4H, "2021-01.parquet")
    with pytest.raises(bv.OnayVerisiKorumasi):  # on kosul: izinsiz okuma reddedilir
        bv.onbellekten_oku(yol)
    izinde, devam = threading.Event(), threading.Event()

    def bloke(sembol, bar, yenile=False):
        izinde.set()
        devam.wait(20)
        return sahte_4h("2021-01-01 00:00", 6)

    monkeypatch.setattr(klines, "ham_mumlari_yukle", bloke)
    isci = threading.Thread(target=lambda: klines.mumlari_yukle(A_SEMBOL, config.BAR_4H, "KESIF"), daemon=True)
    isci.start()
    okudu = None
    try:
        if not izinde.wait(20):
            raise RuntimeError("kurulum: isci is parcacigi izin baglamina girmedi")
        try:
            bv.onbellekten_oku(yol)
            okudu = True
        except bv.OnayVerisiKorumasi:
            okudu = False
    finally:
        devam.set()
        isci.join(20)
    assert okudu is False, "baska is parcacigi, izin baglami disinda B grubu parquet'ini okudu"


@pytest.mark.parametrize("hata_yolu", ["liste_yok", "eksik_ay"])
def test_yukleyici_hata_verince_onay_izni_ve_agsiz_sayaci_sizmaz(gecici_onbellek, hata_yolu):
    """On-kayit §3 satir 123/125: yukleyici hata verirse izin sayaci ve agsiz sayaci eski haline doner; aksi halde
    sonraki cagri B grubu verisini izinsiz okurdu ya da agsiz kurali kalici kapanirdi."""
    if hata_yolu == "eksik_ay":
        _mum_yaz(A_SEMBOL, "2021-01", "2021-01-01 00:00", 6)
        _liste_yaz({A_SEMBOL: ["2021-01", "2021-02"]}, {A_SEMBOL: ["2021-01", "2021-02"]})
        beklenen = bv.AgsizOkumaIhlali
    else:
        beklenen = bv.DonukListeYok
    for yukle in (lambda: klines.mumlari_yukle(A_SEMBOL, config.BAR_4H, "KESIF"),
                  lambda: funding_modulu.funding_yukle(A_SEMBOL, "KESIF")):
        with pytest.raises(beklenen):
            yukle()
        assert bv._IZIN["sayac"] == 0
        assert not bv._agsiz_mi()
    b = _b_sembolu()
    _mum_yaz(b, "2021-01", "2021-01-01 00:00", 6)
    with pytest.raises(bv.OnayVerisiKorumasi):
        bv.onbellekten_oku(bv.onbellek_yolu("klines", b, config.BAR_4H, "2021-01.parquet"))


# =================================================================================================
# 5. Agsiz okuma: is parcacigi, yenile, birincil 1d
# =================================================================================================


class _AgaCikti(BaseException):
    """`_oturum()` tuzagi: `except Exception` ile yutulmaz, yeniden deneme beklemesi olusmaz."""


@pytest.mark.parametrize("yukleyici", ["mum", "funding"])
def test_isci_is_parcaciginda_eksik_ay_aga_dusmez_agsiz_ihlali_verir(monkeypatch, gecici_onbellek, yukleyici):
    """On-kayit §3 satir 125: `agsiz_okuma` is parcacigina ozeldir; ama yukleyiciler baglami KENDI is parcaciginda
    acar, bu yuzden bir havuz iscisinde de eksik ay indirilmez."""
    _mum_yaz(A_SEMBOL, "2021-01", "2021-01-01 00:00", 6)
    _funding_yaz(A_SEMBOL, "2021-01", "2021-01-01 00:00", 6)
    _liste_yaz({A_SEMBOL: ["2021-01", "2021-02"]}, {A_SEMBOL: ["2021-01", "2021-02"]})

    def tuzak():
        raise _AgaCikti()

    monkeypatch.setattr(bv, "_oturum", tuzak)
    monkeypatch.setattr(bv.time, "sleep", lambda *_: None)

    def is_():
        try:
            if yukleyici == "mum":
                klines.mumlari_yukle(A_SEMBOL, config.BAR_4H, "KESIF")
            else:
                funding_modulu.funding_yukle(A_SEMBOL, "KESIF")
        except bv.AgsizOkumaIhlali:
            return "ihlal"
        except _AgaCikti:
            return "aga_cikti"
        except BaseException as hata:
            return type(hata).__name__
        return "sessiz"

    with ThreadPoolExecutor(max_workers=1) as havuz:
        assert havuz.submit(is_).result(timeout=60) == "ihlal"


def _yenile_ortami(monkeypatch, gecici_onbellek, tmp_path):
    cagri = []

    def listele(onek, ayirici):
        cagri.append(onek)
        return [], []

    monkeypatch.setattr(bv, "_listele", listele)
    monkeypatch.setattr(bv.time, "sleep", lambda *_: None)
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    return cagri


@_acik("S-9: `klines.mumlari_yukle(..., yenile=True)` acik bir onay kosusu ICINDE de bucket listesini canli "
       "ceker (`bv._listele`, ag). `yenile` kamuya acik parametredir ve taramada yasakli degildir. On-kayit §3 "
       "satir 125 'F3 kosulari aga cikmaz' ihlali. Onay VERISI sizdirmaz (sonuc yine kume araligina kesilir); "
       "canli listeyle C1/C2 ay adlari ve borsanin anlik durumu kosuya girer. Gercek onay sizintisi: ay "
       "adlari acisindan dusuk; AG kurali acisindan evet.")
def test_onay_kosusu_icinde_mumlari_yukle_yenile_aga_cikmamali(monkeypatch, gecici_onbellek, tmp_path):
    """On-kayit §3 satir 125: onay kosusu icinde `yenile=True` reddedilmeli ya da yok sayilmali."""
    cagri = _yenile_ortami(monkeypatch, gecici_onbellek, tmp_path)
    b = _b_sembolu()
    with kosu("H2", "C1"):
        with contextlib.suppress(Exception):
            klines.mumlari_yukle(b, config.BAR_4H, "C1", onay=True, yenile=True)
    assert cagri == [], f"onay kosusu icinde ag listesi cagrildi: {cagri}"


@_acik("S-10: `funding.funding_yukle(..., yenile=True)` onay kosusu icinde `ham_funding_yukle(yenile=True)` "
       "yolunu acar ve `bv._listele` ile aga cikar (S-9 ile ayni neden). Gercek onay sizintisi: ag kurali "
       "acisindan evet, veri acisindan hayir.")
def test_onay_kosusu_icinde_funding_yukle_yenile_aga_cikmamali(monkeypatch, gecici_onbellek, tmp_path):
    """On-kayit §3 satir 125: onay kosusu icinde funding `yenile=True` aga cikmamali."""
    cagri = _yenile_ortami(monkeypatch, gecici_onbellek, tmp_path)
    b = _b_sembolu()
    with kosu("H2", "C1"):
        with contextlib.suppress(Exception):
            funding_modulu.funding_yukle(b, "C1", onay=True, yenile=True)
    assert cagri == [], f"onay kosusu icinde ag listesi cagrildi: {cagri}"


@_acik("S-11: `klines.birincil_gunluk_indir` `agsiz_okuma` icinde calismaz (`mumlari_yukle`/`funding_yukle`'den "
       "farkli); onay kosusu icinde canli bucket listesini cagirir. Taramada yalniz `ham_birincil_gunluk_indir` "
       "yasakli, kapili `birincil_gunluk_indir` serbest. On-kayit §3 satir 125 ihlali; veri kume araligina "
       "kesilir. Gercek onay sizintisi: ag kurali acisindan evet, veri acisindan hayir.")
def test_onay_kosusu_icinde_birincil_gunluk_indir_aga_cikmamali(monkeypatch, gecici_onbellek, tmp_path):
    """On-kayit §3 satir 125: kapili 1d indirici de onay kosusunda aga cikmamali."""
    cagri = _yenile_ortami(monkeypatch, gecici_onbellek, tmp_path)
    b = _b_sembolu()
    with kosu("H2", "C1"):
        with contextlib.suppress(Exception):
            klines.birincil_gunluk_indir(b, "C1", onay=True)
    assert cagri == [], f"onay kosusu icinde ag listesi cagrildi: {cagri}"


@_acik("S-12: `klines.birincil_gunluk_indir(sembol, 'KESIF')` kosu disinda da (F2) `agsiz_okuma` kullanmaz ve "
       "canli listeyi ceker; F2 'ag yok' kurali (on-kayit §3 satir 125) ayni kapili yoldan delinir. Gercek "
       "onay sizintisi DEGIL (KESIF verisi).")
def test_kesif_icin_birincil_gunluk_indir_aga_cikmamali(monkeypatch, gecici_onbellek, tmp_path):
    """On-kayit §3 satir 125: F2 kosusu kapili yukleyicilerle ag kullanmaz."""
    cagri = _yenile_ortami(monkeypatch, gecici_onbellek, tmp_path)
    with contextlib.suppress(Exception):
        klines.birincil_gunluk_indir(A_SEMBOL, "KESIF")
    assert cagri == [], f"KESIF 1d indirici aga cikti: {cagri}"


# =================================================================================================
# 6. Tarama desenlerinin yakalamadigi yollar
# =================================================================================================

_TARAMA_DESENLERI = (ONBELLEK_DESENI, HAM_ERISIM_DESENI, FUNDING_KAPI_DISI_DESENI, KAYIT_DESENI, ONAY_ATLATMA_DESENI,
                     CIKIS_KAPI_DISI_DESENI)


def _bilinen_desenler_yakalar_mi(tmp_path, metin):
    (tmp_path / "study").mkdir()
    (tmp_path / "study" / "sahte.py").write_text(metin, encoding="utf-8")
    return any(ihlaller(desen, kok=tmp_path, uzantilar=ONBELLEK_UZANTILARI) for desen in _TARAMA_DESENLERI)


_ACIK_TARAMA = [
    "from data import klines\nliste = klines.bv.mum_dosyalari(s, '4h')\n",
    "from data import klines\nliste = klines.bv._listele('x', '')\n",
    "from data import klines\nad = klines.bv.tum_sembol_dizinleri()\n",
    "from data import klines\nklines.mumlari_yukle(s, '4h', 'KESIF', yenile=True)\n",
    "from data import funding\nfunding.funding_yukle(s, 'KESIF', yenile=True)\n",
    "from data import klines\nklines.birincil_gunluk_indir(s, 'KESIF')\n",
]


@pytest.mark.parametrize("metin", [
    pytest.param(m, marks=_acik(
        "S-13: Analiz kodunun ag/liste yollari tarama desenleriyle yakalanmiyor: `klines.bv.mum_dosyalari` "
        "(`binance_vision` adi gecmeden `klines.bv` takma adiyla, canli listeleme izin aramaz; "
        "`mum_dosyalari`/`_listele`/`tum_sembol_dizinleri` hicbir desende yok), `yenile=True` ve kapili "
        "`birincil_gunluk_indir`. On-kayit §3 satir 125 icin tarama savunmasi eksik. Gercek onay sizintisi: "
        "canli liste C1/C2 ay adlarini izinsiz verir (yalniz adlar); veri sizmaz."))
    for m in _ACIK_TARAMA])
def test_aga_cikan_yollar_analiz_kodunda_taramayla_yakalanmali(tmp_path, metin):
    """On-kayit §3 satir 125 + CLAUDE.md §5: F2/F3 analiz kodu aga cikan bir yola erisirse tarama bunu yakalamali."""
    assert _bilinen_desenler_yakalar_mi(tmp_path, metin), "hicbir bilinen tarama deseni bu yolu yakalamadi"


@pytest.mark.parametrize("metin", [
    "from data import kume_bellegi as kb\nkb.getir(k, d, y)\n",
    "from data.kume_bellegi import getir\n",
    "import data.kume_bellegi\n",
    "from data import pozisyon\nx = pozisyon.kume_bellegi\n",
    "bv = klines.bv\nbv.agsiz_okuma()\n",
])
def test_kume_bellegine_ad_ile_erisim_taramada_yakalanir(tmp_path, metin):
    """On-kayit §3 satir 123: bellek modulune ad (takma ad, alt modul, dolayli ozellik) ile erisim yakalanir."""
    assert _bilinen_desenler_yakalar_mi(tmp_path, metin)


# =================================================================================================
# 7. Bellekten donen cerceveyi degistirmek
# =================================================================================================


def test_karar_verisinin_uc_cercevesi_de_kopyadir_ilk_ve_sonraki_donusler():
    """CLAUDE.md §5 / on-kayit §3 satir 123: `_karar_verisi`nin (4h, funding, 1d) ucu de her donuste kopyadir;
    ilk (yukleme) donusunde de, hit donusunde de degistirmek belleği bozmaz."""
    kimlik = _sentetik()
    bas, son = pozisyon.kume_sinirlari("KESIF")
    d = pozisyon.donem_kaydi(kimlik["sembol"], 0)
    argumanlar = dict(kume_baslangic=bas, kume_bitis=son, donem_baslangic=d[0], donem_bitis=d[1])
    ilk = pozisyon._karar_verisi(kimlik["sembol"], "KESIF", **argumanlar)
    referans = tuple(c.copy() for c in ilk)
    for c in ilk:
        c.drop(c.index, inplace=True)
    ikinci = pozisyon._karar_verisi(kimlik["sembol"], "KESIF", **argumanlar)
    for a, b in zip(ikinci, referans):
        pd.testing.assert_frame_equal(a, b)
    for c in ikinci:
        for sutun in c.columns:
            if pd.api.types.is_numeric_dtype(c[sutun]):
                c[sutun] = -1.0
    ucuncu = pozisyon._karar_verisi(kimlik["sembol"], "KESIF", **argumanlar)
    for a, b in zip(ucuncu, referans):
        pd.testing.assert_frame_equal(a, b)


@_acik("S-14: `getir` yukle()'nin dondurdugu nesneleri KOPYALAMADAN saklar, yalniz donusu kopyalar. Yukleyici "
       "kendi nesnesini sonradan degistirirse bellekteki girdi de degisir. Gercek onay sizintisi DEGIL: "
       "kapinin yukleyicileri her cagrida taze cerceve kurar ve elinde tutmaz; ozel API icin savunma derinligi.")
def test_getir_yukleyicinin_sakladigi_cerceveyi_sonradan_degistirmek_bellegi_bozmamali():
    """On-kayit §3 satir 123 'bellekteki kopya': depolanan kopya yukleyiciyle paylasilmamali."""
    paylasilan = pd.DataFrame({"a": [1]})
    kume_bellegi.getir(("p",), lambda: None, lambda: (paylasilan,))
    paylasilan.loc[0, "a"] = 999
    assert int(kume_bellegi.getir(("p",), lambda: None, lambda: (paylasilan,))[0].loc[0, "a"]) == 1


# =================================================================================================
# 8. Esitlik: onbellekli yol ile temizlenmis yol
# =================================================================================================


def test_sentetik_veride_soguk_sicak_dar_bellek_ayni_sonucu_verir(monkeypatch):
    """On-kayit §3 satir 123 / RESULTS §14.40 esitlik: her cagri (a) bellek bosken, (b) bellekten, (c) bellek 1 ve 0
    girdilikken (surekli dusme) AYNI sonucu (karar, ret ya da hata) vermeli. Uc hipotez x uc rol x `sinyal_kosulu`."""
    kimlik = _sentetik()
    soguk = _tum_sonuclar(kimlik, soguk=True)
    sicak = _tum_sonuclar(kimlik, soguk=False)
    sicak_ikinci = _tum_sonuclar(kimlik, soguk=False)
    assert soguk == sicak == sicak_ikinci
    for sinir in (1, 0):
        monkeypatch.setattr(kume_bellegi, "AZAMI_GIRDI", sinir)
        kume_bellegi.temizle()
        assert _tum_sonuclar(kimlik, soguk=False) == soguk, f"AZAMI_GIRDI={sinir} farkli sonuc verdi"
        assert kume_bellegi.girdi_sayisi() <= sinir


def test_onay_kosusundan_once_ve_sonra_kesif_karari_ayni(tmp_path):
    """On-kayit §3 satir 123: onay kosusunun acilisi/kapanisi bellegi bosaltir; temizlenmis yol KESIF kararini
    degistirmemeli."""
    kimlik = _sentetik()
    once = _tum_sonuclar(kimlik, soguk=False)
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    with kosu("H2", "C1"):
        pass
    assert kume_bellegi.girdi_sayisi() == 0
    assert _tum_sonuclar(kimlik, soguk=False) == once


def test_ayni_sembol_farkli_donem_sinirinda_ayri_girdi_ve_ayni_sonuc():
    """On-kayit §2 'donem disindaki bar hicbir hesaba girmez': ayni sembolun donem sinirlari degisince `_karar_verisi`
    anahtari degisir; iki sinirla alinan veri birbirine karismaz ve soguk yolla ayni olur."""
    kimlik = _sentetik()
    bas, son = pozisyon.kume_sinirlari("KESIF")
    gunler = [(pd.Timestamp("2021-01-01", tz="UTC"), pd.Timestamp("2021-02-14 20:00", tz="UTC")),
              (pd.Timestamp("2021-01-01", tz="UTC"), pd.Timestamp("2021-03-31 20:00", tz="UTC"))]
    sicak = []
    for db, de in gunler * 2:  # her sinir iki kez: ikincisi isabet
        sicak.append(pozisyon._karar_verisi(kimlik["sembol"], "KESIF", kume_baslangic=bas, kume_bitis=son,
                                            donem_baslangic=db, donem_bitis=de))
    assert len(sicak[0][0]) < len(sicak[1][0])
    for ilk, ikinci in ((0, 2), (1, 3)):
        for a, b in zip(sicak[ilk], sicak[ikinci]):
            pd.testing.assert_frame_equal(a, b)
    for i, (db, de) in enumerate(gunler):
        kume_bellegi.temizle()
        soguk = pozisyon._karar_verisi(kimlik["sembol"], "KESIF", kume_baslangic=bas, kume_bitis=son,
                                       donem_baslangic=db, donem_bitis=de)
        for a, b in zip(sicak[i], soguk):
            pd.testing.assert_frame_equal(a, b)
