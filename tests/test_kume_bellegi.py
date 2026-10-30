"""Bellek onbellegi: erisim denetimi, anahtar, LRU, onay kosusu ve esitlik (on-kayit §3 rev.13; RESULTS §14.40).

Esitlik testi gercek onbellekle calisir ve KESIF verisini yalnizca karsilastirir: deger yazdirilmaz, sayilmaz.
Onbellek ya da dondurulmus liste yoksa (temiz klon) atlanir. Aga cikmaz.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import binance_vision as bv
from data import funding as funding_modulu
from data import klines, kume_bellegi, pencere, pozisyon, sinyal, split
from kapi_yardimcisi import veri
from onay_yardimcisi import gecici_kayit
from conftest import sahte_4h
from tarama_yardimcisi import KAYIT_DESENI, ONBELLEK_DESENI, ONBELLEK_UZANTILARI, ihlaller


def _sayan_yukleyici(cerceve_sayisi=1):
    cagri = []

    def yukle():
        cagri.append(1)
        return tuple(pd.DataFrame({"a": [len(cagri)]}) for _ in range(cerceve_sayisi))

    return yukle, cagri


# --- Modulun kurallari --------------------------------------------------------------------------


def test_isabette_yeniden_yuklenmez_denetim_yine_calisir():
    yukle, cagri = _sayan_yukleyici()
    denetim = []
    for _ in range(3):
        kume_bellegi.getir(("x",), lambda: denetim.append(1), yukle)
    assert len(cagri) == 1 and len(denetim) == 3


def test_denetim_reddederse_isabet_donmez():
    yukle, _ = _sayan_yukleyici()
    kume_bellegi.getir(("x",), lambda: None, yukle)

    def red():
        raise split.OnayGerekli("izin yok")

    with pytest.raises(split.OnayGerekli):
        kume_bellegi.getir(("x",), red, yukle)


def test_donen_cerceve_kopyadir():
    yukle, _ = _sayan_yukleyici()
    ilk = kume_bellegi.getir(("x",), lambda: None, yukle)[0]
    ilk.loc[0, "a"] = 999
    assert kume_bellegi.getir(("x",), lambda: None, yukle)[0].loc[0, "a"] == 1


def test_yukleme_hatasi_bellege_yazilmaz():
    def bozuk():
        raise pencere.VeriHatasi("bozuk")

    with pytest.raises(pencere.VeriHatasi):
        kume_bellegi.getir(("x",), lambda: None, bozuk)
    assert kume_bellegi.girdi_sayisi() == 0


def test_lru_en_eskiyi_dusurur_ve_yeniden_yukler(monkeypatch):
    monkeypatch.setattr(kume_bellegi, "AZAMI_GIRDI", 2)
    yukleyiciler = {ad: _sayan_yukleyici() for ad in "abc"}
    for ad in "abc":
        kume_bellegi.getir((ad,), lambda: None, yukleyiciler[ad][0])
    assert kume_bellegi.girdi_sayisi() == 2
    kume_bellegi.getir(("b",), lambda: None, yukleyiciler["b"][0])
    assert len(yukleyiciler["b"][1]) == 1  # isabet
    kume_bellegi.getir(("a",), lambda: None, yukleyiciler["a"][0])
    assert len(yukleyiciler["a"][1]) == 2  # dusmustu, yeniden yuklendi


def test_kullanim_sirasi_lru_yi_gunceller(monkeypatch):
    monkeypatch.setattr(kume_bellegi, "AZAMI_GIRDI", 2)
    a, a_cagri = _sayan_yukleyici()
    b, _ = _sayan_yukleyici()
    c, _ = _sayan_yukleyici()
    kume_bellegi.getir(("a",), lambda: None, a)
    kume_bellegi.getir(("b",), lambda: None, b)
    kume_bellegi.getir(("a",), lambda: None, a)  # a tazelendi, b en eski
    kume_bellegi.getir(("c",), lambda: None, c)
    kume_bellegi.getir(("a",), lambda: None, a)
    assert len(a_cagri) == 1


def test_azami_girdi_kucuk_kalir():
    assert 1 <= kume_bellegi.AZAMI_GIRDI <= 16


# --- Kapi ile birlikte ---------------------------------------------------------------------------


def _sentetik(grup="A"):
    zaman = pd.date_range("2021-01-01", periods=180, freq="8h", tz="UTC")
    fr = pd.DataFrame({"odeme_zamani": zaman, "aralik_saat": 8.0, "oran": 0.0001, "oran_8h": 0.0001})
    return veri(sahte_4h("2021-01-01", 540), fr, pd.Timestamp("2021-01-01 00:00", tz="UTC"),
                pd.Timestamp("2021-04-30 20:00", tz="UTC"), grup=grup)


def _kume_verisi(kimlik, kume="KESIF"):
    bas, son = pozisyon.kume_sinirlari(kume)
    return pozisyon._kume_verisi(kimlik["sembol"], kume, bas, son)


def test_kapi_veriyi_bir_kez_yukler(monkeypatch):
    kimlik = _sentetik()
    gercek = pozisyon._veri_yukle
    cagri = []

    def sayan(sembol, kume):
        cagri.append((sembol, kume))
        return gercek(sembol, kume)

    monkeypatch.setattr(pozisyon, "_veri_yukle", sayan)
    for _ in range(5):
        _kume_verisi(kimlik)
    assert cagri == [(kimlik["sembol"], "KESIF")]


def test_anahtar_kumeyi_icerir_kesif_girdisi_c1e_donmez():
    kimlik = _sentetik()
    _kume_verisi(kimlik)
    assert kume_bellegi.girdi_sayisi() == 1
    with pytest.raises(split.OnayGerekli):
        _kume_verisi(kimlik, "C1")


def test_erisim_denetimi_kume_adiyla_calisir():
    with pytest.raises(ValueError):
        pozisyon._erisim_denetimi("YOK")()
    for kume in config.ONAY_KUMELERI:
        with pytest.raises(split.OnayGerekli):
            pozisyon._erisim_denetimi(kume)()
    pozisyon._erisim_denetimi("KESIF")()


def _onay_ortami(tmp_path):
    return gecici_kayit(tmp_path / "ONAY_KAYDI.md")


def test_kosu_kapaninca_c1_verisi_reddedilir(tmp_path):
    kimlik = _sentetik(grup="B")
    _onay_ortami(tmp_path)
    with split.onay_kosusu("H2", "C1") as kosu:
        _kume_verisi(kimlik, "C1")
        assert kume_bellegi.girdi_sayisi() == 1
        kosu.sonuc_bildir("test")
    assert kume_bellegi.girdi_sayisi() == 0
    with pytest.raises(split.OnayGerekli):
        _kume_verisi(kimlik, "C1")


def test_temizleme_bozuk_olsa_da_isabetteki_denetim_reddeder(tmp_path, monkeypatch):
    """Temizleme devre disiyken C1 girdisi bellekte kalir; denetim tek basina reddetmeli."""
    kimlik = _sentetik(grup="B")
    _onay_ortami(tmp_path)
    monkeypatch.setattr(kume_bellegi, "temizle", lambda: None)
    with split.onay_kosusu("H2", "C1") as kosu:
        _kume_verisi(kimlik, "C1")
        kosu.sonuc_bildir("test")
    assert kume_bellegi.girdi_sayisi() == 1
    with pytest.raises(split.OnayGerekli):
        _kume_verisi(kimlik, "C1")


def test_kosu_acilisi_bellegi_bosaltir(tmp_path):
    _kume_verisi(_sentetik())
    assert kume_bellegi.girdi_sayisi() == 1
    _onay_ortami(tmp_path)
    with split.onay_kosusu("H2", "C1") as kosu:
        assert kume_bellegi.girdi_sayisi() == 0
        kosu.sonuc_bildir("test")


def test_kosu_hatayla_bitse_de_bellek_bosalir(tmp_path):
    kimlik = _sentetik(grup="B")
    _onay_ortami(tmp_path)
    with pytest.raises(ZeroDivisionError):
        with split.onay_kosusu("H2", "C1"):
            _kume_verisi(kimlik, "C1")
            raise ZeroDivisionError
    assert kume_bellegi.girdi_sayisi() == 0


def test_bellek_dolarken_onbellek_dizininde_dosya_olusmaz(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", tmp_path)
    kimlik = _sentetik()
    onceki = sorted(tmp_path.rglob("*"))
    _kume_verisi(kimlik)
    bas, son = pozisyon.kume_sinirlari("KESIF")
    d = pozisyon.donem_kaydi(kimlik["sembol"], 0)
    pozisyon._karar_verisi(kimlik["sembol"], "KESIF", kume_baslangic=bas, kume_bitis=son,
                           donem_baslangic=d[0], donem_bitis=d[1])
    assert kume_bellegi.girdi_sayisi() == 2
    assert sorted(tmp_path.rglob("*")) == onceki


def test_cagiranin_cerceve_degisikligi_karari_etkilemez():
    kimlik = _sentetik()
    ilk, _ = _kume_verisi(kimlik)
    ilk["high"] = -1.0
    assert (_kume_verisi(kimlik)[0]["high"] > 0).all()


# --- Esitlik (gercek onbellek) -------------------------------------------------------------------

SEMBOLLER = ("SOLUSDT", "XRPUSDT")  # ikisi de A grubu


@pytest.fixture
def gercek_veri():
    for sembol in SEMBOLLER:
        if not (config.ONBELLEK_DIZINI / "klines" / sembol).exists():
            pytest.skip("gercek onbellek yok")
    if not bv.donuk_liste_yolu().exists():
        pytest.skip("dondurulmus liste yok")


def _sonuc(fn):
    """Karar, ret ya da hata: tur ve butun alanlar metin olarak; NaN alanlar `repr`da esittir."""
    try:
        return repr(fn())
    except Exception as hata:  # dönem disi sinyal gibi hatalar da iki yolda ayni olmali
        return f"{type(hata).__name__}: {hata}"


def _ornek_barlar(sembol, hipotez):
    """Donem basi ve sonu dahil bes bar; kesif araligina kirpilmis, hipotezin izgarasinda."""
    bas, son, _ = pozisyon.donem_kaydi(sembol, 0)
    kume_bas, kume_son = pozisyon.kume_sinirlari("KESIF")
    bas, son = max(bas, kume_bas), min(son, kume_son)
    adim = pd.Timedelta(hours=4)
    ham = [bas, bas + 200 * adim, (bas + (son - bas) / 2).floor("D"), son - 50 * adim, son]
    return [t.floor("D") for t in ham] if config.HIPOTEZ_IZGARASI[hipotez] == config.BAR_1D else ham


def _karar(sembol, t, hipotez, rol, capa):
    bar = config.HIPOTEZ_IZGARASI[hipotez]
    ufuk = config.BIRINCIL_UFUK[bar]
    hacim = config.ASGARI_HACIM_4H if bar == config.BAR_4H else config.ASGARI_HACIM_1D
    return pozisyon.olay_karari(t, ufuk, bar, hipotez=hipotez, yapilandirma=sinyal.izgara(hipotez)[0], rol=rol,
                                capa=capa, birincil_ufuk=ufuk, kume="KESIF", sembol=sembol, donem_no=0,
                                asgari_hacim=hacim, asgari_listeleme_yasi_gun=config.ASGARI_LISTELEME_YASI_GUN)


@pytest.mark.parametrize("sembol", SEMBOLLER)
@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_onbellekli_ve_onbelleksiz_ayni_karari_verir(gercek_veri, sembol, hipotez):
    """Her cagri once bellek bosken (onbelleksiz yol, tam yukleme), sonra bellekten; sonuclar birebir ayni."""
    for t in _ornek_barlar(sembol, hipotez):
        capa = t - pd.Timedelta(hours=24) if hipotez == "H1" else None
        cagrilar = [lambda r=rol, c=(capa if rol == "olay" else None): _karar(sembol, t, hipotez, r, c)
                    for rol in ("olay", "K1", "K2")]
        cagrilar.append(lambda: pozisyon.sinyal_kosulu(t, hipotez=hipotez, yapilandirma=sinyal.izgara(hipotez)[0],
                                                       capa=None, kume="KESIF", sembol=sembol, donem_no=0))
        for cagri in cagrilar:
            kume_bellegi.temizle()
            onbelleksiz = _sonuc(cagri)
            assert kume_bellegi.girdi_sayisi() > 0
            assert _sonuc(cagri) == onbelleksiz


def test_mae_ve_pozisyon_fundingi_bellekten_gecer(gercek_veri, monkeypatch):
    """Ayri bir yukleme yolu kalmaz: onayli pozisyon bulunursa yardimcilar yeniden yuklemez."""
    gercek = pozisyon._veri_yukle
    cagri = []

    def sayan(sembol, kume):
        cagri.append(sembol)
        return gercek(sembol, kume)

    monkeypatch.setattr(pozisyon, "_veri_yukle", sayan)
    for t in _ornek_barlar("SOLUSDT", "H2"):
        try:
            p = _karar("SOLUSDT", t, "H2", "K1", None)
        except (pencere.OlayOlusmaz, pencere.DonemDisiSinyal):
            continue
        kume_bellegi.temizle()
        cagri.clear()
        ilk_mae, ilk_fon = repr(pozisyon.mae(p)), repr(funding_modulu.pozisyon_fundingi(p))
        assert len(cagri) == 1
        assert repr(pozisyon.mae(p)) == ilk_mae and repr(funding_modulu.pozisyon_fundingi(p)) == ilk_fon
        assert len(cagri) == 1
        return
    pytest.skip("ornek barlarda onayli pozisyon yok")


# --- Tarama --------------------------------------------------------------------------------------


@pytest.mark.parametrize("metin", [
    "from data import kume_bellegi\n",
    "kume_bellegi.getir(('kume', s, 'C1'), lambda: None, y)\n",
    "veri = pozisyon.kume_bellegi._BELLEK\n",
    "pozisyon._erisim_denetimi('C1')()\n",
    "liste = json.load(open('x/s3_liste/liste.json'))\n",
    "bv._donuk_liste()\n",
    "bv._donuk_anahtarlar('mum', s, b)\n",
    "bv._DONUK_BELLEK\n",
    "yol = bv.donuk_liste_yolu()\n",
    "with bv.agsiz_okuma():\n    pass\n",
    "bv.listeyi_dondur(uzerine_yaz=True)\n",
])
def test_bellege_ve_listeye_disaridan_erisim_taramada_yakalanir(tmp_path, metin):
    (tmp_path / "study").mkdir()
    (tmp_path / "study" / "sahte.py").write_text(metin, encoding="utf-8")
    assert ihlaller(ONBELLEK_DESENI, kok=tmp_path, uzantilar=ONBELLEK_UZANTILARI) == ["study/sahte.py"]


@pytest.mark.parametrize("metin", ["pozisyon._karar_verisi(s, k)\n", "pozisyon._karar_verisi_kur(s)\n",
                                   "pozisyon._kume_verisi_yukle(s)\n"])
def test_kapinin_ic_veri_yollari_taramada_yakalanir(tmp_path, metin):
    (tmp_path / "study").mkdir()
    (tmp_path / "study" / "sahte.py").write_text(metin, encoding="utf-8")
    assert ihlaller(KAYIT_DESENI, kok=tmp_path) == ["study/sahte.py"]


def test_deponun_analiz_kodunda_ihlal_yok():
    assert [y for y in ihlaller(ONBELLEK_DESENI, uzantilar=ONBELLEK_UZANTILARI) if y != "config.py"] == []
    assert ihlaller(KAYIT_DESENI) == []
