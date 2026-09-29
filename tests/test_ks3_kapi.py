"""Kapi sertlestirme turu 3: hata ile "olay yok" ayrimi (denetci KS2 D-C1).

`pencere.OlayOlusmaz` artik `ValueError` alt sinifi degildir. Veri hatalari `pencere.VeriHatasi`
(`ValueError` alt sinifi; `ZamanDizisiHatasi` dahil), cagri hatalari `TypeError`/`ValueError`/`DonemDisiSinyal`
ve onay hatalari `split.OnayGerekli`dir. Olay dusmelerini sayan kod yalnizca `OlayOlusmaz`i yakalar; bir veri
hatasi ret gerekcesi olarak sayilamaz, bir ret gerekcesi de `except ValueError` ile yutulamaz. Aga cikmaz.
"""

from __future__ import annotations

import pandas as pd
import pytest

from data import pencere, pozisyon, split
from kapi_yardimcisi import veri
from sinyal_yardimcisi import sinyal
from uygunluk_yardimcisi import esikler
from onay_yardimcisi import kosu

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H = lambda n: pd.Timedelta(hours=n)  # noqa: E731

DB, B = T("2025-01-01"), T("2025-06-30 20:00")
Z = pd.date_range(T("2025-03-01"), B, freq="4h")
MUM = pd.DataFrame({"open_time": Z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
FUND = pd.DataFrame({"odeme_zamani": pd.date_range(DB, B + H(4), freq="8h"), "aralik_saat": 8.0,
                     "oran": 1e-4, "oran_8h": 1e-4})
T_SINYAL = T("2025-03-10 04:00")


def _karar(t=T_SINYAL, mum=MUM, fr=FUND, hipotez="H1", ufuk=None, kume="KESIF", **ek):
    tanim = pencere.hipotez_ufuklari(hipotez)
    return pozisyon.olay_karari(t, tanim.birincil if ufuk is None else ufuk, tanim.bar, hipotez=hipotez,
                                birincil_ufuk=tanim.birincil, kume=kume,
                                **veri(mum, fr, DB, B, uygun_bas=DB, **ek), sinyal_degerleri=sinyal(hipotez),
                                **esikler(tanim.bar))


# --- 3. Hata ile "olay yok" ayrimi -------------------------------------------------------------------


def test_sinif_hiyerarsisi():
    for sinif in (pencere.KumeSiniriHatasi, pencere.IleriKaymaSiniriHatasi, pencere.GirisBariYok,
                  pozisyon.SinyalPenceresiTamDegil, pozisyon.UygunDegil, pozisyon.FundingTamDegil,
                  pozisyon.SinyalBariYok):
        assert issubclass(sinif, pencere.OlayOlusmaz)
        assert not issubclass(sinif, ValueError) and not issubclass(sinif, TypeError)
    for sinif in (pencere.VeriHatasi, pencere.ZamanDizisiHatasi, pencere.DonemDisiSinyal, split.OnayGerekli):
        assert not issubclass(sinif, pencere.OlayOlusmaz)
    assert issubclass(pencere.ZamanDizisiHatasi, pencere.VeriHatasi)


def _olay_olusmaz_yakalayan_dongu(cagri):
    """F2'deki olay dongusunun dar yakalama deseni: yalnizca OlayOlusmaz sayilir, gerisi yukari cikar."""
    try:
        cagri()
    except pencere.OlayOlusmaz as ret:
        return pencere.ret_gerekcesi(ret)
    return "onay"


@pytest.mark.parametrize("bozma", ["inf_p0", "nan_p1", "tz_naive", "tekrarli", "izgara_disi"])
def test_veri_hatasi_olay_olusmaz_olarak_yakalanmaz(bozma):
    p = _karar()
    m = MUM.copy()
    ham = False
    if bozma == "inf_p0":
        m.loc[m["open_time"] == p.plan.giris, "open"] = float("inf")
    elif bozma == "nan_p1":
        m.loc[m["open_time"] == p.plan.cikis.zaman, p.plan.cikis.fiyat_alani] = float("nan")
    elif bozma == "tz_naive":
        m["open_time"] = pd.DatetimeIndex(m["open_time"]).tz_localize(None)
        ham = True
    elif bozma == "tekrarli":
        m = pd.concat([m, m.iloc[[10]]]).sort_values("open_time", kind="stable").reset_index(drop=True)
    else:
        m["open_time"] = m["open_time"] + H(1)
    with pytest.raises(pencere.VeriHatasi):
        _olay_olusmaz_yakalayan_dongu(lambda: _karar(mum=m, ham=ham) if ham else _karar(mum=m))


def test_ret_gerekcesi_except_valueerror_ile_yutulmaz():
    """Bir ret gerekcesi (`GirisBariYok`) `except ValueError` blogundan gecer: hata sanilip yutulmaz."""
    eksik = MUM.loc[MUM["open_time"] != T_SINYAL + H(4)]
    with pytest.raises(pencere.GirisBariYok):
        try:
            _karar(mum=eksik)
        except ValueError:  # pragma: no cover - yakalanmamali
            pytest.fail("OlayOlusmaz ValueError olarak yakalandi")


def test_cagri_hatasi_olay_olusmaz_degil():
    with pytest.raises((TypeError, ValueError)) as hata:
        _olay_olusmaz_yakalayan_dongu(lambda: _karar(kume="kesif"))
    assert not isinstance(hata.value, pencere.OlayOlusmaz)
    with pytest.raises(TypeError):
        pencere.ret_gerekcesi(pencere.VeriHatasi("x"))


# --- 1. Onay kosusu baglami (denetci KS2 D-B1) -----------------------------------------------------


@pytest.fixture
def gecici_kayit(tmp_path, monkeypatch):
    import config

    yol = tmp_path / "onay_gecici.md"
    yol.write_text("bas\n", encoding="utf-8")
    split._test_kaydi_ayarla(yol)
    return yol


def _c1(hipotez="H1", **ek):
    return _karar(hipotez=hipotez, kume="C1", grup="B", **ek)


def test_uyusmayan_hipotez_reddedilir_eslesen_onaylanir(gecici_kayit):
    with kosu("H2", "C1"):
        with pytest.raises(split.OnayUyusmazligi):
            _c1("H1")
        pozisyon.onay_dogrula(_c1("H2"))


def test_onay_kumesi_kosu_disinda_ve_baska_kumenin_kosusunda_reddedilir(gecici_kayit):
    with pytest.raises(split.OnayUyusmazligi):
        _c1("H1")
    with kosu("H1", "C2"):
        with pytest.raises(split.OnayUyusmazligi):
            _c1("H1")


def test_acik_kosu_icinde_kesif_pozisyonu_reddedilir(gecici_kayit):
    pozisyon.onay_dogrula(_karar())
    with kosu("H1", "C1"):
        with pytest.raises(split.OnayUyusmazligi):
            _karar()


@pytest.mark.parametrize("hipotez", ["h2", "H2_b", " H2", "H2 ", "H4", "HTEST", "", None, b"H2"])
def test_hipotez_adi_varyasyonlari_kosu_acamaz(gecici_kayit, hipotez):
    with pytest.raises(ValueError):
        with kosu(hipotez, "C1"):
            pytest.fail("kosu acilmamali")
    assert gecici_kayit.read_text(encoding="utf-8") == "bas\n"
    assert split.aktif_onay_kosusu() is None


@pytest.mark.parametrize("kume", ["c1", "C1 ", "KESIF", "C3", None])
def test_onay_kumesi_varyasyonlari_kosu_acamaz(gecici_kayit, kume):
    with pytest.raises(ValueError):
        with kosu("H2", kume):
            pytest.fail("kosu acilmamali")


def test_str_alt_sinifi_hipotez_adi_kosu_acamaz(gecici_kayit):
    class _Ad(str):
        pass

    with pytest.raises(ValueError):
        with kosu(_Ad("H2"), "C1"):
            pytest.fail("kosu acilmamali")


def test_kapi_hipotezi_de_sabitlerden(gecici_kayit):
    with pytest.raises((ValueError, KeyError)):
        _karar(hipotez="h1")


def test_mae_ve_funding_onay_baglamini_ister(gecici_kayit):
    from data import funding

    with kosu("H1", "C1"):
        p = _c1("H1")
        assert pozisyon.mae(p) == pozisyon.mae(p)
        funding.pozisyon_fundingi(p)
    with pytest.raises(split.OnayUyusmazligi):
        pozisyon.mae(p)
    with pytest.raises(split.OnayUyusmazligi):
        funding.pozisyon_fundingi(p)


# --- 2. Ikincil ufuk: olay birincil ufukta belirlenir (denetci KS2 D-B3) -------------------------------


def test_birincilde_kume_sinirina_takilan_olay_ikincilde_de_olusmaz():
    """KESIF sonuna yakin t: birincil (18 bar) cikis C2'ye tasar, 6 barlik cikis sigar. Olay birincilde
    olusmadigi icin 6 barda da onaylanmaz; ret gerekcesi birincilinkidir."""
    db = T("2025-06-01")
    z = pd.date_range(db, T("2025-08-31 20:00"), freq="4h")
    mum = pd.DataFrame({"open_time": z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
    fr = pd.DataFrame({"odeme_zamani": pd.date_range(db, T("2025-09-01"), freq="8h"), "aralik_saat": 8.0,
                       "oran": 0.0, "oran_8h": 0.0})
    tanim = pencere.hipotez_ufuklari("H1")
    t = T("2025-08-29 04:00")
    kayit = veri(mum, fr, db, T("2025-08-31 20:00"), uygun_bas=db)
    ortak = dict(hipotez="H1", birincil_ufuk=tanim.birincil, kume="KESIF", **kayit, sinyal_degerleri=sinyal("H1"),
                 **esikler(tanim.bar))
    with pytest.raises(pencere.KumeSiniriHatasi):
        pozisyon.olay_karari(t, tanim.birincil, tanim.bar, **ortak)
    for ufuk in tanim.ikincil:
        with pytest.raises(pencere.KumeSiniriHatasi):
            pozisyon.olay_karari(t, ufuk, tanim.bar, **ortak)


def test_birincilde_funding_eksik_olay_ikincilde_de_olusmaz():
    """Birincil pencerenin 6 barlik ufuktan SONRAKI kisminda bir funding kaydi eksik: 6 barlik pozisyonun
    funding'i tamdir ama olay birincilde olusmaz."""
    p6_giris = T_SINYAL + H(4)
    eksik = p6_giris + H(6 * 4 + 16)  # 6 barlik cikistan sonra, birincil cikistan once
    fr = FUND.loc[FUND["odeme_zamani"] != eksik].reset_index(drop=True)
    assert (FUND["odeme_zamani"] == eksik).any()
    with pytest.raises(pozisyon.FundingTamDegil):
        _karar(fr=fr)
    with pytest.raises(pozisyon.FundingTamDegil):
        _karar(fr=fr, ufuk=6)


def test_birincilde_olusan_olayin_ikincil_cikisi_kendi_kurallarina_tabidir():
    """Birincil onayli olay 6 barda da onaylanir; 42 barlik cikis donem/kume/funding kurallarini kendi
    uzunluguyla gecmelidir (on-kayit §3 'Ikincil ufuklar ... kendi ufuk uzunluklariyla')."""
    p18 = _karar()
    p6 = _karar(ufuk=6)
    assert p18.plan.ufuk == 18 and p6.plan.ufuk == 6 and p6.plan.giris == p18.plan.giris
    fr = FUND.loc[FUND["odeme_zamani"] != p18.plan.cikis_ani + H(16)].reset_index(drop=True)
    pozisyon.onay_dogrula(_karar(fr=fr))
    with pytest.raises(pozisyon.FundingTamDegil):
        _karar(fr=fr, ufuk=42)
