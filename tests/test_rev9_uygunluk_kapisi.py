"""On-kayit §4 rev.9 "Olayin kumede olusma olcutu": uygunluk tek karar noktasinin parcasidir.

"Uygunluk da bu karar noktasinin parcasidir (rev.9): hacim esigi ve listeleme yasi dahil
uygunluk filtresi, olaylar ve kontroller icin ayni karar noktasinda, ayni cagriyla uygulanir.
Uygunluk degerinin hesaplanabilmis olmasi yeterli degildir; esigi de gecmelidir."
Denetci bulgusu D-B4'u kapatir. Aga cikmaz; getiri hesaplanmaz.
"""

from __future__ import annotations

import ast
import inspect
import textwrap

import numpy as np
import pandas as pd
import pytest

import config
from data import eligibility, pencere, pozisyon
from tarama_yardimcisi import CIKIS_KAPI_DISI_DESENI, KOK, UYGUNLUK_ADLARI, ihlaller
from sinyal_yardimcisi import sinyal
from kapi_yardimcisi import veri
from kume_yardimcisi import kume_adi, kume_sinirlari
from uygunluk_yardimcisi import esikler

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
DB = T("2025-01-01 00:00")          # donem basi
SERI_BAS = T("2025-03-01 00:00")   # mum ve funding serisinin basi (donem basindan 59 gun sonra)
B = T("2025-04-10 20:00")
Z = pd.date_range(SERI_BAS, B, freq="4h")
MUM = pd.DataFrame({"open_time": Z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
                    "close_time": Z + H4 - pd.Timedelta(milliseconds=1)})
FUND = pd.DataFrame({"odeme_zamani": pd.date_range(DB, B, freq="8h"), "aralik_saat": 8.0, "oran": 0.0,
                     "oran_8h": 0.0})
T_SINYAL = T("2025-03-05 04:00")


def _karar(t=T_SINYAL, bar=config.BAR_4H, db=DB, mum=MUM, hacim=5e7, eksik_gunler=(), **ek):
    """Kapi sertlestirme turu 2: kapi 1d serisini 4h barlardan kendisi turetir; eski `gun` (1d cercevesi)
    girdisinin karsiligi 4h serisinin hacmi (`hacim`) ve eksik gunleridir (`eksik_gunler`)."""
    esik = {**esikler(bar), **{k: ek.pop(k) for k in list(ek) if k.startswith("asgari_")}}
    return pozisyon.olay_karari(
        t, 6 if bar == config.BAR_4H else 7, bar,  # Rev.10: on-kayit ufku (1d'de onceki 3)
        hipotez="H1" if bar == config.BAR_4H else "H3", birincil_ufuk=18 if bar == config.BAR_4H else 14,
        kume=kume_adi(t), **veri(mum, FUND, db, B, uygun_bas=db, hacim=hacim, eksik_gunler=eksik_gunler),
        sinyal_degerleri=sinyal("H1" if bar == config.BAR_4H else "H3"), **esik, **ek)


# --- Uygunluk karar noktasinin icinde ------------------------------------------------------


def test_uygun_bar_onaylanir():
    assert _karar().plan.sinyal_zamani == T_SINYAL


def test_uygunluk_girdisi_olmadan_onayli_pozisyon_uretilemez():
    with pytest.raises(TypeError):
        pozisyon.olay_karari(T_SINYAL, 6, config.BAR_4H, hipotez="H1", birincil_ufuk=18, kume=kume_adi(T_SINYAL),
                             **veri(MUM, FUND, DB, B, uygun_bas=DB), sinyal_degerleri=sinyal("H1"))
    with pytest.raises(ValueError):  # elle kurulan onay reddedilir (karar noktasi atlanamaz)
        pozisyon.pozisyon_fiyatlari(pozisyon.OnaylanmisPozisyon(_karar().plan, 1.0, 1.0, 0.0))


@pytest.mark.parametrize("bar,esik", [(config.BAR_4H, config.ASGARI_HACIM_4H), (config.BAR_1D, config.ASGARI_HACIM_1D)])
def test_esigi_gecmeyen_bar_olay_uretmez(bar, esik):
    """Medyan hacim esigin hemen altinda: deger hesaplanabiliyor ama esik gecilmiyor."""
    t = T("2025-03-05 00:00")
    with pytest.raises(pozisyon.UygunDegil) as hata:
        _karar(t=t, bar=bar, hacim=esik - 1.0)
    assert pencere.ret_gerekcesi(hata.value) == "uygun_degil"
    assert _karar(t=t, bar=bar, hacim=esik).plan.sinyal_zamani == t  # esik dahil (>=)


def test_hacim_penceresi_hesaplanamazsa_olay_uretmez():
    """Uygunluk penceresinde bir gun eksik: deger NaN -> uygun degil."""
    with pytest.raises(pozisyon.UygunDegil):
        _karar(eksik_gunler=[T("2025-02-20")])


@pytest.mark.parametrize("yas_gun,uygun", [(30, True), (29.9, False)])
def test_listeleme_yasi_esigi(yas_gun, uygun):
    db = T_SINYAL - pd.Timedelta(days=yas_gun)
    # Hacim penceresi (t gunu haric onceki 30 gun) donem basini asmasin diye bu testte donemin
    # ilk gunleri de gunluk seride; yas 30 gunun altindaysa pencere zaten donem basini asar.
    if uygun:
        assert _karar(db=db.floor("D")).plan.donem_baslangic == db.floor("D")
    else:
        with pytest.raises(pozisyon.UygunDegil):
            _karar(db=db)


def test_uygunluk_t_gunu_haric_gecmis_hacme_bakar():
    """t gununun (ve sonrasinin) hacmi kararini degistirmez; gelecege bakis yok."""
    zaman = pd.DatetimeIndex(MUM["open_time"])
    hacim = np.where(zaman.hour == 0, 5e7, 0.0)
    hacim[np.asarray(zaman >= T_SINYAL.floor("D"))] = 0.0
    assert _karar(mum=MUM.assign(quote_volume=hacim)).plan.sinyal_zamani == T_SINYAL


@pytest.mark.parametrize("ad,deger", [("asgari_hacim", config.ASGARI_HACIM_1D), ("asgari_hacim", 9_999_999.0),
                                      ("asgari_listeleme_yasi_gun", 29), ("asgari_hacim", True)])
def test_on_kayit_disi_esik_reddedilir(ad, deger):
    with pytest.raises((ValueError, TypeError)):
        _karar(**{ad: deger})


def test_gunluk_yerine_4h_cerceve_hata_verir():
    # Kapi sertlestirme turu 2: 1d serisi kapida 4h barlardan turetilir; cagiran 1d (ya da yerine 4h)
    # cercevesi veremez: TypeError (onceki beklenti: verilen 4h cercevesi icin ValueError).
    with pytest.raises(TypeError):
        _karar(gunluk_mumlar=MUM.assign(quote_volume=5e7))


# --- Olaylar ve kontroller ayni kapidan ------------------------------------------------------


def test_karar_noktasi_uygunlugu_tek_uygulamadan_cagirir(monkeypatch):
    """Casus: `eligibility.uygunluk_karari` False donerse karar reddeder; cagri sinyal zamani,
    izgara ve on-kayit esikleriyle yapilir."""
    cagri = []

    def casus(hacim, t, bar, **kw):
        cagri.append((t, bar, kw["asgari_hacim"], kw["asgari_listeleme_yasi_gun"], kw["kume_baslangic"]))
        return False

    monkeypatch.setattr(eligibility, "uygunluk_karari", casus)
    with pytest.raises(pozisyon.UygunDegil):
        _karar()
    # F1 kapanis turu 2: kapi kume sinirini None kabul etmez; beklenen deger, kapiya verilen gercek kume
    # basinin (KESIF) uygunluga aynen iletilmesidir (onceden verilen None'in yankisiydi).
    assert cagri == [(T_SINYAL, config.BAR_4H, config.ASGARI_HACIM_4H, config.ASGARI_LISTELEME_YASI_GUN,
                      kume_sinirlari(T_SINYAL)["kume_baslangic"])]


def test_kontrol_bari_ayni_kapidan_gecer():
    """K2 kontrolu: ayni t'de baska bir coin. Ayri bir kontrol yolu yoktur; kontrol barinin
    uygunlugu da `olay_karari` icinde ayni esikle denetlenir."""
    uygun_kontrol = _karar(hacim=2e7)
    assert uygun_kontrol.plan.sinyal_zamani == T_SINYAL
    with pytest.raises(pozisyon.UygunDegil):
        _karar(hacim=1e6)
    # Karar noktasi olay/kontrol ayrimi yapan bir parametre almaz.
    parametreler = set(inspect.signature(pozisyon.olay_karari).parameters)
    assert not {p for p in parametreler if "kontrol" in p or "tur" == p}


def _cagrilar(modul, ad):
    agac = ast.parse(textwrap.dedent(inspect.getsource(modul)))
    sonuc = []
    for fonk in ast.walk(agac):
        if isinstance(fonk, ast.FunctionDef):
            for d in ast.walk(fonk):
                if isinstance(d, ast.Call):
                    f = d.func
                    isim = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
                    if isim == ad:
                        sonuc.append(fonk.name)
    return sonuc


def test_veri_katmaninda_uygunluk_karari_yalnizca_karar_noktasinda_ve_uygun_muda():
    from data import funding, klines, pencere as pencere_modulu, split, universe

    assert _cagrilar(pozisyon, "uygunluk_karari") == ["olay_karari"]
    assert _cagrilar(eligibility, "uygunluk_karari") == ["uygun_mu"]
    for modul in (funding, klines, pencere_modulu, split, universe):
        assert not _cagrilar(modul, "uygunluk_karari") and not _cagrilar(modul, "uygun_mu"), modul.__name__
    # OnaylanmisPozisyon yalnizca olay_karari'nda kurulur.
    assert _cagrilar(pozisyon, "OnaylanmisPozisyon") == ["olay_karari"]


# --- Kaynak taramasi -----------------------------------------------------------------------------


def test_tarama_uygunluk_adlarini_yakalar(tmp_path):
    ornekler = {f"events/u_{ad}.py": f"x = {ad}(h, t, bar)\n" for ad in UYGUNLUK_ADLARI}
    ornekler.update({
        "study/k1.py": "from data import eligibility\n",
        "study/k2.py": "from data.eligibility import uygun_mu as u\nu(h, t, bar)\n",
        "study/k3.py": "import data.eligibility as e\n",
        "analysis/02_h2/calistir.py": "ok = eligibility.uygun_mu(h, t, b, donem_baslangic=d, donem_bitis=e, kume_baslangic=k)\n",
    })
    for ad, metin in ornekler.items():
        yol = tmp_path / ad
        yol.parent.mkdir(parents=True, exist_ok=True)
        yol.write_text(metin, encoding="utf-8")
    temiz = tmp_path / "events" / "h2.py"
    temiz.write_text("p = pozisyon.olay_karari(m, fr, t, 18, bar, birincil_ufuk=18, **sinirlar,\n"
                     "    gunluk_mumlar=g, asgari_hacim=config.ASGARI_HACIM_4H,\n"
                     "    asgari_listeleme_yasi_gun=config.ASGARI_LISTELEME_YASI_GUN)\n", encoding="utf-8")
    izinli = tmp_path / "data" / "pozisyon.py"
    izinli.parent.mkdir()
    izinli.write_text("from data import eligibility\neligibility.uygunluk_karari(h, t, b)\n", encoding="utf-8")
    assert ihlaller(CIKIS_KAPI_DISI_DESENI, kok=tmp_path) == sorted(ornekler)


def test_depoda_uygunluk_kapi_disi_erisim_yok():
    assert ihlaller(CIKIS_KAPI_DISI_DESENI) == []


def test_uygunluk_adlari_eligibility_modulunun_butun_fonksiyonlari():
    """Taramadaki ad listesi `data/eligibility.py`deki butun ust duzey fonksiyonlari kapsar;
    module yeni fonksiyon eklenirse bu test hatirlatir."""
    agac = ast.parse(inspect.getsource(eligibility))
    fonksiyonlar = {d.name for d in agac.body if isinstance(d, ast.FunctionDef)}
    assert fonksiyonlar == set(UYGUNLUK_ADLARI)


def test_depoda_py_disi_analiz_kodu_yok():
    """Kaynak taramalari yalnizca .py dosyalarina bakar. Depoda analiz kodu tasiyabilecek baska
    uzanti (not defteri, betik) yoktur; eklenirse taramalar onu gormez ve bu test uyarir."""
    import os

    uzantilar = {".ipynb", ".pyw", ".pyx", ".pyi", ".sh", ".ps1", ".bat", ".r", ".jl", ".sql"}
    atla = {"cache", ".git", ".venv", "venv", "__pycache__", ".pytest_cache"}
    bulunan = []
    for dizin, altlar, dosyalar in os.walk(KOK):
        altlar[:] = [a for a in altlar if a not in atla]
        bulunan += [os.path.relpath(os.path.join(dizin, d), KOK) for d in dosyalar
                    if os.path.splitext(d)[1].lower() in uzantilar]
    assert sorted(bulunan) == []


def test_gunluk_hacim_numpy_turleri_ile_de():
    """Esik degerleri numpy sayisi olsa da kabul edilir (deger ayni)."""
    esik = {"asgari_hacim": np.float64(config.ASGARI_HACIM_4H),
            "asgari_listeleme_yasi_gun": config.ASGARI_LISTELEME_YASI_GUN}
    assert _karar(**esik).plan.sinyal_zamani == T_SINYAL
