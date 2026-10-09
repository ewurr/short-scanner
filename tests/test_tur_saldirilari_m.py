"""F1 kapanis turu saldiri testleri (M turu, "kapi sertlestirme turu 2" sonrasi).

Hedef, gorev tanimindaki degisiklik: `pozisyon.olay_karari` veriyi kendisi yukler
(`_veri_yukle`, `_kume_verisi`), 1d serisini `klines.gunluge_cevir` ile turetir, sinyal
barini denetler (`SinyalBariYok`), sonlu olmayan degerleri (`_sonlu`) ve UTC disi sinyal
zamanini (`_utc_sinyal_zamani`) reddeder.

Bu tur ozellikle KENDI yuklenen veri cercevesinin (mumlar_4h, funding) bicim ve bozukluk
denetimini, sonlu olmayan degerlerin pencere ici/disi ayrimini, UTC esdegerlerinin sinirini
ve onay kosusunun hipotez-kume eslesmesini hedefler.

Yaklasim kodu KIRMAYA calisir. Gecen (xfail olmayan) testler savusturulan saldirilardir;
`xfail(strict=True)` ile isaretli testler basarili saldirilardir (bulunan acik). Aga cikmaz.
Mevcut hicbir test dosyasi degistirilmedi; bu YENI bir dosyadir.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

import config
from data import funding, pencere, pozisyon, split
from kapi_yardimcisi import SENTETIK_VERI, veri
from sinyal_yardimcisi import kontrol
from uygunluk_yardimcisi import esikler
from onay_yardimcisi import kosu

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H = lambda n: pd.Timedelta(hours=n)  # noqa: E731

DB, B = T("2025-01-01"), T("2025-06-30 20:00")
Z = pd.date_range(T("2025-03-01"), B, freq="4h")
MUM = pd.DataFrame({"open_time": Z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
FUND = pd.DataFrame({"odeme_zamani": pd.date_range(DB, B + H(4), freq="8h"), "aralik_saat": 8.0,
                     "oran": 1e-4, "oran_8h": 1e-4})
SINYAL_T = {"H1": T("2025-03-10 04:00"), "H2": T("2025-03-10 04:00"), "H3": T("2025-03-10")}


def _karar(hipotez="H1", mum=MUM, fr=FUND, t=None, **ek):
    tanim = pencere.hipotez_ufuklari(hipotez)
    return pozisyon.olay_karari(SINYAL_T[hipotez] if t is None else t, tanim.birincil, tanim.bar, hipotez=hipotez,
                                birincil_ufuk=tanim.birincil, kume="KESIF",
                                **veri(mum, fr, DB, B, uygun_bas=DB, **ek), **kontrol(hipotez),
                                **esikler(tanim.bar))


def _hazirlanmis_mumlar() -> pd.DataFrame:
    """Hazirlanmis (sirali, quote_volume/close_time eklenmis) taban 4h cercevesi. Testler bunu bozup
    `ham=True` ile geri verir (`_hazirla` `sort_values` uyguladigi icin bozuk sirayi/tekrari kendisi
    duzeltirdi; ham yol bunu atlatir)."""
    taban = veri(MUM, FUND, DB, B, uygun_bas=DB)
    m, _ = SENTETIK_VERI[taban["sembol"]]
    return m.copy()


def _karar_ham(m: pd.DataFrame, fr: pd.DataFrame = FUND, hipotez: str = "H1"):
    tanim = pencere.hipotez_ufuklari(hipotez)
    kayit = veri(m, fr, DB, B, ham=True)
    return pozisyon.olay_karari(SINYAL_T[hipotez], tanim.birincil, tanim.bar, hipotez=hipotez,
                                birincil_ufuk=tanim.birincil, kume="KESIF", **kayit,
                                **kontrol(hipotez), **esikler(tanim.bar))


# --- 1. Yuklenen 4h mum cercevesinin bicim/bozukluk denetimi (kapi sertlestirme turu 2) --------------


def test_mumlarda_yinelenen_open_time_reddedilir():
    """Yukleyicinin dondurdugu 4h cercevesinde tekrarlanan `open_time`: bozuk veri, sessizce
    islenmemeli (`pencere._zaman_dizisi_dogrula`, `ZamanDizisiHatasi`)."""
    m = _hazirlanmis_mumlar()
    bozuk = pd.concat([m, m.iloc[[10]]], ignore_index=True)
    with pytest.raises(pencere.ZamanDizisiHatasi):
        _karar_ham(bozuk)


def test_mumlar_ters_sirada_verilirse_reddedilir():
    """Yukleyici barlari ters sirada dondurse (bozuk onbellek): kapi zaman siralamasini kendisi
    dogrular, geriye donuk (ters) diziyi ileri kayis gibi ISLEMEZ (`ZamanDizisiHatasi`)."""
    m = _hazirlanmis_mumlar()
    ters = m.iloc[::-1].reset_index(drop=True)
    with pytest.raises(pencere.ZamanDizisiHatasi):
        _karar_ham(ters)


def test_mumlarda_tz_naive_open_time_reddedilir():
    """`open_time` saat dilimsizse (tz-naive) tum zaman karsilastirmalari sessizce yanlis sonuc
    verirdi (CLAUDE.md §5); kapi acik hata vermeli."""
    m = _hazirlanmis_mumlar()
    m2 = m.copy()
    m2["open_time"] = pd.DatetimeIndex(m2["open_time"]).tz_localize(None)
    # Kapi sertlestirme turu 3: kapi zaman dizisini kesimden once dogruluyor; tz'siz veri ZamanDizisiHatasi
    # (VeriHatasi). Onceki turda genisletilen beklenti (ZamanDizisiHatasi, TypeError) testcinin ilk haline dondu.
    with pytest.raises(pencere.ZamanDizisiHatasi):
        _karar_ham(m2)


def test_mumlarda_close_time_nat_reddedilir():
    """`close_time` sutununda NaT: bar suresi dogrulanamaz (NaT ile yapilan sure karsilastirmasi
    her zaman False doner; sizinti testcisinin Rev.10 hazirlik bulgusu 2, `_close_time_nat_yok`)."""
    m = _hazirlanmis_mumlar()
    m2 = m.copy()
    m2.loc[m2.index[5], "close_time"] = pd.NaT
    with pytest.raises(ValueError, match="close_time"):
        _karar_ham(m2)


def test_fiyat_sutununda_string_deger_giris_barinda_reddedilir():
    """Giris barinin `open` degeri string ise (bozuk kayit) P0 sessizce hesaplanmamali."""
    m = _hazirlanmis_mumlar()
    giris_ani = SINYAL_T["H1"] + H(4)
    m2 = m.copy()
    m2.loc[m2["open_time"] == giris_ani, "open"] = "bozuk"
    assert (m2["open_time"] == giris_ani).any(), "test kurulumu: giris bari seride bulunamadi"
    with pytest.raises(ValueError):
        _karar_ham(m2)


def test_fiyat_sutununda_none_deger_giris_barinda_reddedilir():
    """`open` sutunu object turune donup (ör. bozuk parquet okuma) giris barinda None tasirsa
    P0 sessizce NaN'a degil, acik bir hataya dusmeli (nan atamasindan farkli olarak None gercek
    bir object degeridir; pandas float sutununa None atarsa NaN'a cevirir, bu yuzden sutun once
    object turune zorlanir)."""
    m = _hazirlanmis_mumlar()
    giris_ani = SINYAL_T["H1"] + H(4)
    m2 = m.copy()
    m2["open"] = m2["open"].astype(object)
    m2.loc[m2["open_time"] == giris_ani, "open"] = None
    with pytest.raises(TypeError):
        _karar_ham(m2)


# --- 2. Yuklenen funding cercevesinin bicim/bozukluk denetimi ----------------------------------------


def test_fundingde_yinelenen_kayit_reddedilir():
    """Funding kayitlarinda tekrarlanan `odeme_zamani`: ayni odeme iki kez yazilmis olabilir
    (bozuk veri); `funding._zaman_dizisi` acik hata vermeli, sessizce birlesmemeli."""
    fr = pd.concat([FUND, FUND.iloc[[3]]], ignore_index=True)
    with pytest.raises(pencere.ZamanDizisiHatasi):
        _karar(fr=fr)


def test_fundingde_sirasiz_kayit_reddedilir():
    """Funding kayitlari ters sirada verilirse (bozuk onbellek): kapi zaman siralamasini kendisi
    dogrulamali, sessizce yanlis capa/zincir hesabina dusmemeli."""
    fr = FUND.iloc[::-1].reset_index(drop=True)
    with pytest.raises(pencere.ZamanDizisiHatasi):
        _karar(fr=fr)


def test_fundingde_tz_naive_odeme_zamani_reddedilir():
    """`odeme_zamani` saat dilimsizse (tz-naive) tum pencere/tamlik karsilastirmalari sessizce
    yanlis sonuc verirdi; kapi acik hata vermeli."""
    fr = FUND.copy()
    fr["odeme_zamani"] = pd.DatetimeIndex(fr["odeme_zamani"]).tz_localize(None)
    # Kapi sertlestirme turu 3: kapi zaman dizisini kesimden once dogruluyor; tz'siz veri ZamanDizisiHatasi
    # (VeriHatasi). Onceki turda genisletilen beklenti (ZamanDizisiHatasi, TypeError) testcinin ilk haline dondu.
    with pytest.raises(pencere.ZamanDizisiHatasi):
        _karar(fr=fr)


# --- 3. Sonlu olmayan funding degerleri: pencere ici / disi ayrimi -----------------------------------


def test_funding_penceresi_icinde_zit_isaretli_iki_sonsuz_deger_toplami_bozuk_sayar():
    """Pozisyon penceresi icinde (giristen kesin sonra) biri +inf biri -inf oranli iki kayit:
    toplam NaN olur (`inf + -inf = nan`); `math.isnan(toplam)` bunu yakalar ve `FundingTamDegil`
    firlatir -- sessizce net getiriye sizmaz (savusturuldu)."""
    p = _karar()
    icerde = FUND.index[(FUND["odeme_zamani"] > p.plan.giris) & (FUND["odeme_zamani"] <= p.plan.cikis_ani)]
    assert len(icerde) >= 2, "test kurulumu: pozisyon penceresinde en az iki funding kaydi bekleniyordu"
    fr = FUND.copy()
    fr.loc[icerde[0], "oran"] = float("inf")
    fr.loc[icerde[1], "oran"] = float("-inf")
    with pytest.raises(pozisyon.FundingTamDegil):
        _karar(fr=fr)


def test_giris_anindaki_sonsuz_oran_pozisyon_disinda_kalir():
    """On-kayit §4: giris anindaki odeme pozisyon DISINDADIR. Tam giris aninda (capa kaydi) oran
    = inf olsa bile bu kayit toplama hic girmemeli; karar basariyla onaylanmali ve funding
    toplami sonlu kalmali (savusturuldu)."""
    p = _karar()
    tam_giriste = FUND.index[FUND["odeme_zamani"] == p.plan.giris]
    assert len(tam_giriste) == 1, "test kurulumu: giris aninda tam bir funding kaydi bekleniyordu"
    fr = FUND.copy()
    fr.loc[tam_giriste[0], "oran"] = float("inf")
    p2 = _karar(fr=fr)
    pozisyon.onay_dogrula(p2)
    assert math.isfinite(p2.funding_toplami)
    assert p2.funding_toplami == pytest.approx(p.funding_toplami)


def test_pencere_sonrasi_sonsuz_oran_toplami_etkilemez():
    """Pozisyon funding penceresinin (`funding.funding_penceresi_sonu`) KESIN otesindeki bir kayitta
    oran = inf: bu kayit toplam maskesine hic girmez (`sonra(...) & ayni_ya_da_once(...)`); toplam
    degismemeli (savusturuldu)."""
    p = _karar()
    pencere_sonu = funding.funding_penceresi_sonu(p.plan)
    sonrasi = FUND.index[FUND["odeme_zamani"] > pencere_sonu]
    assert len(sonrasi) > 0, "test kurulumu: pencere sonrasinda en az bir funding kaydi bekleniyordu"
    fr = FUND.copy()
    fr.loc[sonrasi[0], "oran"] = float("inf")
    p2 = _karar(fr=fr)
    assert p2.funding_toplami == pytest.approx(p.funding_toplami)


def test_funding_oran_sutunu_string_ise_hesaplanamaz_sayilir():
    """`oran` sutununda pozisyon penceresi icinde bir string kayit: `pd.to_numeric(errors='coerce')`
    NaN'a cevirir; toplam NaN olur ve `FundingTamDegil` firlatilir. Bozuk oran, tamlik denetimini
    (yalnizca zaman/aralik okur) atlatarak sessiz bir sayiya (0 ya da NaN gorunmeden) DONUSMEZ
    (savusturuldu)."""
    p = _karar()
    icerde = FUND.index[(FUND["odeme_zamani"] > p.plan.giris) & (FUND["odeme_zamani"] <= p.plan.cikis_ani)]
    assert len(icerde) > 0
    fr = FUND.copy()
    fr["oran"] = fr["oran"].astype(object)
    fr.loc[icerde[0], "oran"] = "bozuk"
    with pytest.raises(pozisyon.FundingTamDegil):
        _karar(fr=fr)


# --- 4. UTC esdegerleri ve sinirlari (KS D-B5'in genisletilmis sinirlari) ----------------------------


def test_pytz_utc_kabul_edilir():
    """`pytz.UTC` gercek UTC'dir (tzname 'UTC', offset 0); kapi reddetmemeli."""
    pytz = pytest.importorskip("pytz")
    t = SINYAL_T["H1"].tz_convert(pytz.UTC)
    pozisyon.onay_dogrula(_karar("H1", t=t))


def test_zoneinfo_utc_kabul_edilir():
    """`zoneinfo.ZoneInfo('UTC')` gercek UTC'dir; kapi reddetmemeli."""
    from zoneinfo import ZoneInfo

    t = SINYAL_T["H1"].tz_convert(ZoneInfo("UTC"))
    pozisyon.onay_dogrula(_karar("H1", t=t))


def test_dateutil_tzutc_kabul_edilir():
    """`dateutil.tz.tzutc()` gercek UTC'dir; kapi reddetmemeli."""
    dateutil_tz = pytest.importorskip("dateutil.tz")
    t = SINYAL_T["H1"].tz_convert(dateutil_tz.tzutc())
    pozisyon.onay_dogrula(_karar("H1", t=t))


def test_europe_london_kisin_offset_sifir_olsa_da_reddedilir():
    """Kisin (DST oncesi) Europe/London UTC ile AYNI offsete (0) sahiptir ama saat dilimi adi
    'UTC' degil 'GMT'dir. Kapi yalnizca offsete degil `tzname()`e de bakar (`_utc_sinyal_zamani`);
    sadece offsete bakan bir denetim bunu sessizce kabul ederdi (KS D-B5 mantiginin genisletilmis
    sinir sinamasi; savusturuldu)."""
    t = SINYAL_T["H1"].tz_convert("Europe/London")
    assert t.utcoffset() == pd.Timedelta(0), "test kurulumu: kisin Londra UTC ile ayni offsette olmali"
    assert t.tzname() != "UTC"
    with pytest.raises(ValueError, match="UTC olmali"):
        _karar("H1", t=t)


# --- 5. Donem disi sinyal, bar seride olsa bile reddedilir -------------------------------------------


def test_donem_disi_sinyal_seride_var_olsa_da_reddedilir():
    """Sinyal bari 4h serisinde fiziksel olarak mevcut olsa da donem baslangicindan ONCEYSE olay
    olusmamali (`pencere.DonemDisiSinyal`); uygunluk/`SinyalBariYok` denetiminden once, kapinin
    kendi donem sinir denetiminde yakalanmali (savusturuldu)."""
    donem_bas = T("2025-03-15")
    kayit = veri(MUM, FUND, donem_bas, B, uygun_bas=donem_bas)
    t_disi = T("2025-03-05 04:00")
    assert (MUM["open_time"] == t_disi).any(), "test kurulumu: bar seride olmali ama donem disinda kalmali"
    assert t_disi < donem_bas
    tanim = pencere.hipotez_ufuklari("H1")
    with pytest.raises(pencere.DonemDisiSinyal):
        pozisyon.olay_karari(t_disi, tanim.birincil, tanim.bar, hipotez="H1", birincil_ufuk=tanim.birincil,
                             kume="KESIF", **kayit, **kontrol("H1"), **esikler(tanim.bar))


# --- 6. Onay kosusu hipotez-kume eslesmesi (CLAUDE.md §3.3, on-kayit "tek atis") ---------------------


# SALDIRI BULGUSU (kapi sertlestirme turu 2, xfail idi): kapi ve `split.kume_erisimi` acik onay kosusunun
# yalnizca kumesini denetliyordu; `onay_kosusu("H2", "C1")` icinde H1'in C1 pozisyonu onaylaniyordu.
# Kapi sertlestirme turu 3'te kapandi (`split.onay_baglami_dogrula`: `OnayUyusmazligi`, `OnayGerekli` alt
# sinifi); xfail isareti kaldirildi, beklenti ayni.
def test_onay_kosusu_hipotez_uyusmazligi_engellenmez(tmp_path, monkeypatch):
    kayit = tmp_path / "onay_gecici.md"
    split._test_kaydi_ayarla(kayit)
    tanim = pencere.hipotez_ufuklari("H1")
    kayit_veri = veri(MUM, FUND, DB, B, uygun_bas=DB, grup="B")
    with kosu("H2", "C1"):  # onay kaydi turu (KS3 D-B1): `yol=` parametresi kaldirildi
        with pytest.raises((ValueError, split.OnayGerekli)):
            p = pozisyon.olay_karari(
                SINYAL_T["H1"], tanim.birincil, tanim.bar, hipotez="H1", birincil_ufuk=tanim.birincil,
                kume="C1", **kayit_veri, **kontrol("H1"), **esikler(tanim.bar))
            pozisyon.onay_dogrula(p)
