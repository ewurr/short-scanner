"""Vektorel seri kuruculari (`data.seri_kurucu`; performans 2b-1, plan v3; RESULTS §14.48). Sentetik dunya; aga cikmaz.

Her deger dondurulmus skaler referansla (`data._skaler_referans`) BIT DUZEYINDE karsilastirilir (G6): iki taraf da
NaN ya da iki float'in 64 bitlik temsili ayni. Degerler yazdirilmaz; testler yalnizca esitligi ve NaN konumunu sinar.
Test adlari gereksinim koduyla baslar (G3, G5, G6, G7, G13, G16, G17, G18, G20). Tohumlar `config.TOHUM`dan turetilir.
"""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import config
from data import _skaler_referans as ref
from data import klines, pencere, seri_kurucu as sk, sinyal
from data.donem import Donem

KOK = Path(__file__).resolve().parents[1]
H = lambda n: pd.Timedelta(hours=4 * n)  # noqa: E731
G = lambda n: pd.Timedelta(days=n)  # noqa: E731
U = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
BAS = U("2024-01-01 00:00")
SON = U("2024-07-31 20:00")         # ~213 gun: H3'un 120 gunluk penceresine yer var
TOHUMLAR = [config.TOHUM + i for i in range(3)]


# --- Sentetik dunya --------------------------------------------------------------------------------------------

def mumlar(bas=BAS, son=SON, *, tohum=config.TOHUM, eksik=(), bozuk=(), oncesi_gun=0) -> pd.DataFrame:
    """Rastgele yuruyus 4h mumlari [bas - oncesi_gun, son]; `eksik` satir silinir, `bozuk` barin open'i NaN."""
    rng = np.random.default_rng(tohum)
    z = pd.date_range(bas - G(oncesi_gun), son, freq="4h")
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, len(z))))
    acilis = np.concatenate(([close[0]], close[:-1]))
    yuksek = np.maximum(acilis, close) * np.exp(np.abs(rng.normal(0, 0.01, len(z))))
    dusuk = np.minimum(acilis, close) * np.exp(-np.abs(rng.normal(0, 0.01, len(z))))
    qv = rng.lognormal(16, 1.0, len(z))
    m = pd.DataFrame({"open_time": z, "open": acilis, "high": yuksek, "low": dusuk, "close": close,
                      "volume": qv / close, "close_time": z + pd.Timedelta(hours=4) - pd.Timedelta(milliseconds=1),
                      "quote_volume": qv, "count": 100, "taker_buy_volume": qv / close / 2,
                      "taker_buy_quote_volume": qv / 2})
    for t in bozuk:
        m.loc[m["open_time"] == t, "open"] = np.nan
    if len(eksik):
        m = m.loc[~m["open_time"].isin(list(eksik))]
    return m.reset_index(drop=True)


def gunluk(m, bas=BAS, son=SON) -> pd.DataFrame:
    return klines.gunluge_cevir(m, donemler=[Donem(bas, son, len(m), len(m))])


def fonlama(bas=BAS, son=SON, *, tohum=config.TOHUM, oranlar=None, aralik=8) -> pd.DataFrame:
    rng = np.random.default_rng(tohum + 1000)
    z = pd.date_range(bas.floor("D"), son + H(1), freq=f"{aralik}h")
    oran = rng.normal(1e-4, 3e-4, len(z)) if oranlar is None else oranlar
    return pd.DataFrame({"odeme_zamani": z, "aralik_saat": float(aralik), "oran": oran,
                         "oran_8h": oran * 8 / aralik})


def izgara_4h(m, bas=BAS, son=SON) -> pd.DatetimeIndex:
    """Hipotez izgarasi yardimcisinin 4h sozlesmesi: donem ici mevcut, hucresi tam barlar (G20; yardimcinin kendisi
    `tests/test_hipotez_izgarasi.py`de sinanir; burada saf kuruculara ayni bicimde izgara verilir)."""
    z = pd.DatetimeIndex(m["open_time"])
    tam = klines.hucreleri_tam_mi(m) & np.asarray((z >= bas) & (z <= son))
    return z[tam]


def izgara_1d(g) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(g["open_time"])


def ayni(a, b) -> bool:
    a, b = float(a), float(b)
    return (np.isnan(a) and np.isnan(b)) or np.float64(a).view(np.int64) == np.float64(b).view(np.int64)


def uyusmayan(vektor, skaler) -> int:
    assert len(vektor) == len(skaler)
    return sum(not ayni(v, s) for v, s in zip(vektor, skaler))


SINIR = {"kume_baslangic": None, "donem_baslangic": BAS}


def _skaler_4h(m, z, k=3, kume_bas=None, donem_bas=BAS):
    s = {"kume_baslangic": kume_bas, "donem_baslangic": donem_bas}
    return {
        "dip": [ref.h1_dip(m, t, **s) for t in z],
        "hacim_6": [ref.h1_hacim_6(m, t, **s) for t in z],
        "hacim_medyani_180": [ref.h1_hacim_medyani_180(m, t, **s) for t in z],
        "kirilim_dip": [ref.h2_kirilim_dip(m, t, k, **s) for t in z],
        "kapanis_30_once": [ref.kapanis_30_once(m, t, config.BAR_4H, **s) for t in z],
        "yuksek_30_max": [ref.yuksek_30_max(m, t, config.BAR_4H, **s) for t in z],
        "kapanis": [ref.bar_degeri(m, t, "close") for t in z],
        "yuksek": [ref.bar_degeri(m, t, "high") for t in z],
    }


def _vektor_4h(m, z, k=3, kume_bas=None, donem_bas=BAS):
    s = {"kume_baslangic": kume_bas, "donem_baslangic": donem_bas}
    return {
        "dip": sk.h1_dip(m, z, **s), "hacim_6": sk.h1_hacim_6(m, z, **s),
        "hacim_medyani_180": sk.h1_hacim_medyani_180(m, z, **s), "kirilim_dip": sk.h2_kirilim_dip(m, z, k, **s),
        "kapanis_30_once": sk.kapanis_30_once(m, z, config.BAR_4H, **s),
        "yuksek_30_max": sk.yuksek_30_max(m, z, config.BAR_4H, **s),
        "kapanis": sk.kapanis(m, z, config.BAR_4H), "yuksek": sk.yuksek(m, z, config.BAR_4H),
    }


def _skaler_1d(g, z, kume_bas=None, donem_bas=BAS):
    s = {"kume_baslangic": kume_bas, "donem_baslangic": donem_bas}
    return {
        "hacim_medyani_30g": [ref.h3_hacim_medyani_30g(g, t, **s) for t in z],
        "hacim_medyani_120_31": [ref.h3_hacim_medyani_120_31(g, t, **s) for t in z],
        "sma50": [ref.h3_sma50(g, t, **s) for t in z],
        "kapanis_30_once": [ref.kapanis_30_once(g, t, config.BAR_1D, **s) for t in z],
        "yuksek_30_max": [ref.yuksek_30_max(g, t, config.BAR_1D, **s) for t in z],
        "kapanis": [ref.bar_degeri(g, t, "close") for t in z],
    }


def _vektor_1d(g, z, kume_bas=None, donem_bas=BAS):
    s = {"kume_baslangic": kume_bas, "donem_baslangic": donem_bas}
    return {
        "hacim_medyani_30g": sk.h3_hacim_medyani_30g(g, z, **s),
        "hacim_medyani_120_31": sk.h3_hacim_medyani_120_31(g, z, **s), "sma50": sk.h3_sma50(g, z, **s),
        "kapanis_30_once": sk.kapanis_30_once(g, z, config.BAR_1D, **s),
        "yuksek_30_max": sk.yuksek_30_max(g, z, config.BAR_1D, **s), "kapanis": sk.kapanis(g, z, config.BAR_1D),
    }


def _hepsi_ayni(vektor, skaler):
    farklar = {ad: uyusmayan(vektor[ad], skaler[ad]) for ad in skaler}
    assert all(v == 0 for v in farklar.values()), farklar


def _sonlu_var(degerler):
    return any(np.isfinite(np.asarray(v, dtype=float)).any() for v in degerler.values())


# --- G6: bit duzeyinde esitlik ---------------------------------------------------------------------------------

@pytest.mark.parametrize("tohum", TOHUMLAR)
def test_G6_rastgele_4h_dunyada_her_pencere_bit_duzeyinde_ayni(tohum):
    rng = np.random.default_rng(tohum)
    tum = pd.date_range(BAS, SON, freq="4h")
    eksik = list(tum[rng.choice(len(tum), 6, replace=False)])
    bozuk = list(tum[rng.choice(len(tum), 4, replace=False)])
    m = mumlar(tohum=tohum, eksik=eksik, bozuk=bozuk)
    z = izgara_4h(m)
    k = int(rng.choice(config.IZGARA["H2"]["k"]))
    vektor, skaler = _vektor_4h(m, z, k), _skaler_4h(m, z, k)
    assert _sonlu_var(skaler), "kurulum: hesaplanabilir pencere olmali"
    _hepsi_ayni(vektor, skaler)


@pytest.mark.parametrize("tohum", TOHUMLAR)
def test_G6_rastgele_1d_dunyada_her_pencere_bit_duzeyinde_ayni(tohum):
    rng = np.random.default_rng(tohum)
    tum = pd.date_range(BAS, SON, freq="4h")
    m = mumlar(tohum=tohum, eksik=list(tum[rng.choice(len(tum), 3, replace=False)]))
    g = gunluk(m)
    z = izgara_1d(g)
    vektor, skaler = _vektor_1d(g, z), _skaler_1d(g, z)
    assert _sonlu_var(skaler)
    _hepsi_ayni(vektor, skaler)


@pytest.mark.parametrize("tohum", TOHUMLAR)
def test_G6_funding_24s_bit_duzeyinde_ayni(tohum):
    m = mumlar(tohum=tohum)
    z = izgara_4h(m)
    f = fonlama(tohum=tohum)
    s = {"kume_baslangic": None, "kume_bitis": None, "donem_baslangic": BAS}
    v = sk.h2_funding_24s(f, z, **s)
    r = [ref.h2_funding_24s(f, t, **s) for t in z]
    assert np.isfinite(r).sum() > 100
    assert uyusmayan(v, r) == 0


@pytest.mark.parametrize("aralik", [8, 4])
def test_G6_funding_ritmi_degisse_de_ayni(aralik):
    """4 saatlik ritimde pencerede 6 kayit, 8 saatlikte 3: degisken dilim uzunlugu."""
    m = mumlar()
    z = izgara_4h(m)
    f = fonlama(aralik=aralik)
    s = {"kume_baslangic": None, "kume_bitis": None, "donem_baslangic": BAS}
    assert uyusmayan(sk.h2_funding_24s(f, z, **s), [ref.h2_funding_24s(f, t, **s) for t in z]) == 0


@pytest.mark.parametrize("tohum", TOHUMLAR[:2])
def test_G6_uygunluk_bit_duzeyinde_ayni(tohum):
    bas = U("2024-01-01 12:00")
    m = mumlar(bas=bas, tohum=tohum)
    g = gunluk(m, bas=bas)
    gh = ref.gunluk_hacim_serisi(g)
    for bar, z, esik in ((config.BAR_4H, izgara_4h(m, bas=bas), config.ASGARI_HACIM_4H),
                         (config.BAR_1D, izgara_1d(g), config.ASGARI_HACIM_1D)):
        tablo = sk.uygunluk(g, z, bar, donem_baslangic=bas, donem_bitis=SON, kume_baslangic=None,
                            asgari_hacim=esik, asgari_listeleme_yasi_gun=config.ASGARI_LISTELEME_YASI_GUN)
        medyan = [ref.medyan_hacim(gh, t, donem_baslangic=bas, kume_baslangic=None,
                                   pencere_gun=config.HACIM_PENCERESI_GUN) for t in z]
        yas = [ref.listeleme_yasi_gun(bas, t) for t in z]
        uygun = [ref.uygunluk_karari(gh, t, bar, donem_baslangic=bas, donem_bitis=SON, kume_baslangic=None,
                                     asgari_hacim=esik, asgari_listeleme_yasi_gun=config.ASGARI_LISTELEME_YASI_GUN)
                 for t in z]
        assert uyusmayan(tablo["medyan_hacim"], medyan) == 0
        assert uyusmayan(tablo["listeleme_yasi_gun"], yas) == 0
        assert list(tablo["uygun"]) == uygun
        assert any(uygun) and not all(uygun), "kurulum: iki sonuc da gorulmeli"


def test_G6_capasiz_hesaplanabilirlik_referansla_ayni():
    m = mumlar(eksik=[U("2024-03-01 08:00")])
    g = gunluk(m)
    f = fonlama()
    s = {"kume_baslangic": None, "kume_bitis": None, "donem_baslangic": BAS}
    for hipotez, z in (("H1", izgara_4h(m)), ("H2", izgara_4h(m)), ("H3", izgara_1d(g))):
        y = ref.izgara(hipotez)[0]
        k = y["k"] if hipotez == "H2" else None
        p = sk.capasiz_pencereler(hipotez, k, z, mumlar_4h=m, gunluk=g, funding=f, **s)
        vektor = sk.capasiz_hesaplanabilir(hipotez, p)
        skaler = []
        for i, t in enumerate(z):
            d = ref.capasiz_pencere_degerleri(hipotez, y, t, mumlar_4h=m, gunluk=g, funding=f, **s)
            skaler.append(not ref.capasiz_hesaplanamayan(hipotez, d))
            for ad in d:
                assert ayni(p[ad][i], d[ad]), (hipotez, ad, i)
        assert list(vektor) == skaler and any(skaler) and not all(skaler)


# --- G3: tamlik, acik sayim, pencere uclari ---------------------------------------------------------------------

T4 = U("2024-06-01 12:00")          # her 4h penceresinin sigdigi bar
T1 = U("2024-07-01")                # her 1d penceresinin sigdigi gun

PENCERELER_4H = {                    # ad -> (pencere uzunlugu, t'den geriye son bar ofseti)
    "dip": (6, 1), "hacim_6": (6, 0), "kirilim_dip": (12, 1), "kapanis_30_once": (31, 0),
    "yuksek_30_max": (31, 0), "hacim_medyani_180": (185, 0),
}
PENCERELER_1D = {"hacim_medyani_30g": (30, 0), "hacim_medyani_120_31": (90, 31), "sma50": (50, 0),
                 "kapanis_30_once": (31, 0), "yuksek_30_max": (31, 0)}


def _tek_bar_4h(m, ad, t, k=12):
    v = _vektor_4h(m, pd.DatetimeIndex([t]), k)[ad][0]
    s = _skaler_4h(m, [t], k)[ad][0]
    return v, s


@pytest.mark.parametrize("ad", list(PENCERELER_4H))
@pytest.mark.parametrize("kip", ["eksik", "bozuk"])
def test_G3_4h_her_konumda_tek_eksik_bar_iki_tarafta_NaN(ad, kip):
    n, ofset = PENCERELER_4H[ad]
    konumlar = range(ofset, ofset + n)
    if ad == "hacim_medyani_180":
        konumlar = sorted({0, 1, 5, 6, 90, 178, 179, 180, 183, 184})   # 185 konumun temsilcileri ve iki uc
    for j in konumlar:
        hedef = T4 - H(j)
        m = mumlar(eksik=[hedef]) if kip == "eksik" else mumlar(bozuk=[hedef])
        v, s = _tek_bar_4h(m, ad, T4)
        assert np.isnan(s) and np.isnan(v), (ad, j)
    v, s = _tek_bar_4h(mumlar(), ad, T4)
    assert np.isfinite(s) and ayni(v, s)


@pytest.mark.parametrize("ad", list(PENCERELER_1D))
@pytest.mark.parametrize("kip", ["eksik", "bozuk"])
def test_G3_1d_her_konumda_tek_eksik_gun_iki_tarafta_NaN(ad, kip):
    n, ofset = PENCERELER_1D[ad]
    for j in range(ofset, ofset + n):
        hedef = T1 - G(j) + H(2)          # gunun 08:00 bari: gun 1d serisinden duser
        m = mumlar(eksik=[hedef]) if kip == "eksik" else mumlar(bozuk=[hedef])
        g = gunluk(m)
        v = _vektor_1d(g, pd.DatetimeIndex([T1]))[ad][0]
        s = _skaler_1d(g, [T1])[ad][0]
        assert np.isnan(s) and np.isnan(v), (ad, j)


@pytest.mark.parametrize("ad,dahil,haric", [
    ("kapanis_30_once", [0, 30], [31]),                    # [t-30 .. t] 31 bar
    ("hacim_medyani_180", [0, 184], [185]),                # H1 birlesim [t-184 .. t]
    ("dip", [1, 6], [0, 7]),                               # dip t'yi DISLAR
    ("hacim_6", [0, 5], [6]),
])
def test_G3_4h_pencere_uclari_adiyla(ad, dahil, haric):
    for j in dahil:
        v, s = _tek_bar_4h(mumlar(bozuk=[T4 - H(j)]), ad, T4)
        assert np.isnan(v) and np.isnan(s), (ad, "dahil", j)
    for j in haric:
        v, s = _tek_bar_4h(mumlar(bozuk=[T4 - H(j)]), ad, T4)
        assert np.isfinite(v) and ayni(v, s), (ad, "haric", j)


@pytest.mark.parametrize("ad,dahil,haric", [
    ("sma50", [0, 49], [50]),                              # [t-49 .. t]
    ("hacim_medyani_120_31", [31, 120], [30, 121]),        # [t-120 .. t-31]
    ("hacim_medyani_30g", [0, 29], [30]),                  # [t-29 .. t]
])
def test_G3_1d_pencere_uclari_adiyla(ad, dahil, haric):
    for j in dahil + haric:
        g = gunluk(mumlar(bozuk=[T1 - G(j) + H(2)]))
        v = _vektor_1d(g, pd.DatetimeIndex([T1]))[ad][0]
        s = _skaler_1d(g, [T1])[ad][0]
        assert ayni(v, s)
        assert np.isnan(v) == (j in dahil), (ad, j)


def test_G3_t_eksi_30_gunu_hicbir_hacim_penceresine_girmez():
    g = gunluk(mumlar(bozuk=[T1 - G(30) + H(2)]))
    z = pd.DatetimeIndex([T1])
    for ad in ("hacim_medyani_30g", "hacim_medyani_120_31"):
        assert np.isfinite(_vektor_1d(g, z)[ad][0]) and ayni(_vektor_1d(g, z)[ad][0], _skaler_1d(g, z)[ad][0])


@pytest.mark.parametrize("ad", ["hacim_medyani_180", "kapanis_30_once", "dip"])
def test_G3_donem_basi_ve_kume_basi_ayri_maskeler(ad):
    """Seride donem ve kume oncesi veri VAR (oncesi_gun=60); pencere basi sinirdan once ise NaN. Kume basi ve donem
    basi ayri ayri sinanir; sinirla ayni an olan pencere basi gecer."""
    m = mumlar(oncesi_gun=60)
    n, ofset = PENCERELER_4H[ad]
    t = BAS + H(n - 1 + ofset)                 # pencere basi = BAS
    z = pd.DatetimeIndex([t - H(1), t, t + H(1)])
    for sinir in ({"kume_bas": BAS, "donem_bas": BAS - G(60)}, {"kume_bas": None, "donem_bas": BAS}):
        v = _vektor_4h(m, z, 12, **sinir)[ad]
        s = _skaler_4h(m, z, 12, **sinir)[ad]
        assert uyusmayan(v, s) == 0
        assert np.isnan(v[0]) and np.isfinite(v[1]) and np.isfinite(v[2]), sinir


def test_G3_kaynak_rolling_shift_iloc_kullanmaz():
    metin = (KOK / "data" / "seri_kurucu.py").read_text(encoding="utf-8")
    agac = ast.parse(metin)
    adlar = {d.attr for d in ast.walk(agac) if isinstance(d, ast.Attribute)}
    for yasak in ("rolling", "expanding", "ewm", "shift", "iloc", "nanmedian", "nansum", "nanmean", "fillna"):
        assert yasak not in adlar, yasak


def test_G3_tekrarli_zaman_damgasi_iki_tarafta_ayni_hata():
    m = mumlar()
    m = pd.concat([m, m.iloc[[500]]], ignore_index=True)
    z = izgara_4h(mumlar())
    with pytest.raises(pencere.ZamanDizisiHatasi):
        ref.h1_dip(m, z[300], **SINIR)
    with pytest.raises(pencere.ZamanDizisiHatasi):
        sk.h1_dip(m, z, **SINIR)


# --- G5, G17: H2 funding penceresi ------------------------------------------------------------------------------

def _f24(f, z, kume_bas=None, kume_son=None):
    s = {"kume_baslangic": kume_bas, "kume_bitis": kume_son, "donem_baslangic": BAS}
    return sk.h2_funding_24s(f, z, **s), [ref.h2_funding_24s(f, t, **s) for t in z]


def _kayit_ekle(f, an, oran):
    yeni = pd.DataFrame({"odeme_zamani": [an], "aralik_saat": [8.0], "oran": [oran], "oran_8h": [oran]})
    return pd.concat([f, yeni], ignore_index=True).sort_values("odeme_zamani", kind="stable").reset_index(drop=True)


TF = U("2024-05-10 12:00")           # kapanis 16:00; 8 saatlik kayitlar 00/08/16


def test_G5_toleransin_hemen_disindaki_bozuk_oran_t_yi_etkilemez():
    f = fonlama()
    kapanis = TF + H(1)
    once_v, once_s = _f24(f, pd.DatetimeIndex([TF]))
    for fark in (pd.Timedelta(minutes=1), pd.Timedelta(minutes=1, seconds=1), pd.Timedelta(hours=1)):
        f2 = _kayit_ekle(f.loc[f["odeme_zamani"] != kapanis + pd.Timedelta(hours=8)], kapanis + fark, np.nan)
        v, s = _f24(f2, pd.DatetimeIndex([TF]))
        assert ayni(v[0], once_v[0]) and ayni(s[0], once_s[0]) and np.isfinite(v[0]), fark


def test_G5_tolerans_icindeki_kayit_dahil_edilir():
    """Kapanisa 30 sn sonra denk gelen kayit pencere sonuna denk gelir ve ortalamaya GIRER (on-kayit §4)."""
    kapanis = TF + H(1)
    f = fonlama()
    f = f.loc[f["odeme_zamani"] != kapanis].reset_index(drop=True)
    temel_v, temel_s = _f24(f, pd.DatetimeIndex([TF]))
    f2 = _kayit_ekle(f, kapanis + pd.Timedelta(seconds=30), 5e-3)
    v, s = _f24(f2, pd.DatetimeIndex([TF]))
    assert ayni(v[0], s[0]) and np.isfinite(v[0]) and not ayni(v[0], temel_v[0])
    f3 = _kayit_ekle(f, kapanis + pd.Timedelta(seconds=30), np.nan)
    v3, s3 = _f24(f3, pd.DatetimeIndex([TF]))
    assert np.isnan(v3[0]) and np.isnan(s3[0]), "tolerans icindeki bozuk oran pencereye girer"


def test_G5_sirasiz_zaman_damgasi_skalerle_ayni_hata():
    f = fonlama()
    f2 = f.copy()
    i = int(np.searchsorted(f["odeme_zamani"], TF))
    f2.loc[[i, i + 1], "odeme_zamani"] = f.loc[[i + 1, i], "odeme_zamani"].to_numpy()
    z = pd.DatetimeIndex([TF + H(3)])
    with pytest.raises(pencere.ZamanDizisiHatasi):
        ref.h2_funding_24s(f2, z[0], kume_baslangic=None, kume_bitis=None, donem_baslangic=BAS)
    with pytest.raises(pencere.ZamanDizisiHatasi):
        sk.h2_funding_24s(f2, z, kume_baslangic=None, kume_bitis=None, donem_baslangic=BAS)


def test_G5_saat_dilimsiz_odeme_zamani_iki_tarafta_ayni_hata():
    f = fonlama()
    f["odeme_zamani"] = f["odeme_zamani"].dt.tz_localize(None)
    with pytest.raises(pencere.ZamanDizisiHatasi):
        ref.h2_funding_24s(f, TF, kume_baslangic=None, kume_bitis=None, donem_baslangic=BAS)
    with pytest.raises(pencere.ZamanDizisiHatasi):
        sk.h2_funding_24s(f, pd.DatetimeIndex([TF]), kume_baslangic=None, kume_bitis=None, donem_baslangic=BAS)


@pytest.mark.parametrize("bozuk", [np.nan, np.inf, -np.inf, "metin"])
def test_G17_sonlu_olmayan_oran_ortalamayi_NaN_yapar(bozuk):
    f = fonlama()
    f["oran_8h"] = f["oran_8h"].astype(object)
    hedef = TF + H(1) - pd.Timedelta(hours=8)          # pencerenin icindeki kayit
    f.loc[f["odeme_zamani"] == hedef, "oran_8h"] = bozuk
    z = pd.DatetimeIndex([TF - H(2), TF, TF + H(6), TF + H(12)])
    v, s = _f24(f, z)
    assert uyusmayan(v, s) == 0
    assert np.isnan(v[1]) and np.isfinite(v[3]), "yalnizca kaydi iceren pencereler NaN"


# --- G7: uygunluk ------------------------------------------------------------------------------------------------

def _uygunluk(g, z, bar, bas):
    esik = config.ASGARI_HACIM_4H if bar == config.BAR_4H else config.ASGARI_HACIM_1D
    return sk.uygunluk(g, z, bar, donem_baslangic=bas, donem_bitis=SON, kume_baslangic=None, asgari_hacim=esik,
                       asgari_listeleme_yasi_gun=config.ASGARI_LISTELEME_YASI_GUN)


def test_G7_donem_12de_basladiginda_listeleme_yasi_bar_basina():
    bas = U("2024-01-01 12:00")
    m = mumlar(bas=bas)
    g = gunluk(m, bas=bas)
    z = pd.DatetimeIndex([bas + G(30) - H(1), bas + G(30), bas + G(30) + H(1)])
    tablo = _uygunluk(g, z, config.BAR_4H, bas)
    beklenen = [ref.listeleme_yasi_gun(bas, t) for t in z]
    assert uyusmayan(tablo["listeleme_yasi_gun"], beklenen) == 0
    assert list(tablo["listeleme_yasi_gun"] >= 30) == [False, True, True]
    # Gun basina medyan: ayni gunun barlari ayni medyani alir.
    gun = pd.DatetimeIndex([U("2024-03-05 00:00") + H(i) for i in range(6)])
    t2 = _uygunluk(g, gun, config.BAR_4H, bas)
    assert t2["medyan_hacim"].nunique() == 1


def test_G7_t_gunu_hacim_penceresinin_disinda():
    """t gununun hacmi degisirse medyan degismez; bir onceki gunun hacmi degisirse degisir."""
    m = mumlar()
    z = pd.DatetimeIndex([U("2024-04-10 12:00")])
    temel = _uygunluk(gunluk(m), z, config.BAR_4H, BAS)["medyan_hacim"].iloc[0]
    for gun, degismeli in ((U("2024-04-10"), False), (U("2024-04-09"), True)):
        m2 = m.copy()
        secim = (m2["open_time"] >= gun) & (m2["open_time"] < gun + G(1))
        m2.loc[secim, "quote_volume"] *= 1000
        yeni = _uygunluk(gunluk(m2), z, config.BAR_4H, BAS)["medyan_hacim"].iloc[0]
        skaler = ref.medyan_hacim(ref.gunluk_hacim_serisi(gunluk(m2)), z[0], donem_baslangic=BAS,
                                  kume_baslangic=None, pencere_gun=config.HACIM_PENCERESI_GUN)
        assert ayni(yeni, skaler)
        assert (not ayni(yeni, temel)) == degismeli, gun


def test_G7_esik_disi_deger_skalerle_ayni_hatayi_verir():
    g = gunluk(mumlar())
    with pytest.raises(ValueError):
        sk.uygunluk(g, izgara_1d(g), config.BAR_1D, donem_baslangic=BAS, donem_bitis=SON, kume_baslangic=None,
                    asgari_hacim=1.0, asgari_listeleme_yasi_gun=config.ASGARI_LISTELEME_YASI_GUN)


# --- G13: kume siniri (bes vaka; seride kume disi veri var) ------------------------------------------------------

KESIF_SONU = U("2025-08-31 23:59:59")
C2_BASI = U("2025-09-01 00:00")
C2_SONU = U("2026-08-31 23:59:59")


def _kume_dunyasi(bas, son):
    m = mumlar(bas=bas, son=son)
    return m, fonlama(bas=bas, son=son + G(2))


def test_G13_1_kesif_sonu_ve_c2_basi_iki_yuzu():
    bas, son = U("2025-06-01"), U("2025-10-31 20:00")
    m, f = _kume_dunyasi(bas, son)
    z = izgara_4h(m, bas=bas, son=son)
    kesif_yuzu = z[z <= KESIF_SONU]
    c2_yuzu = z[z >= C2_BASI]
    # KESIF yuzu: kume sonundan sonra veri var ama fiyat pencereleri geriye bakar.
    _hepsi_ayni(_vektor_4h(m, kesif_yuzu, donem_bas=bas), _skaler_4h(m, kesif_yuzu, donem_bas=bas))
    # C2 yuzu: kume basi C2 basi; seride C2 oncesi veri var, pencere onu odunc alamaz.
    v = _vektor_4h(m, c2_yuzu, kume_bas=C2_BASI, donem_bas=bas)
    _hepsi_ayni(v, _skaler_4h(m, c2_yuzu, kume_bas=C2_BASI, donem_bas=bas))
    assert np.isnan(v["hacim_medyani_180"][0]) and np.isfinite(v["hacim_medyani_180"][-1])


def test_G13_2_funding_tolerans_payi_kume_sonunu_asar():
    """KESIF'in son barlari: pencere sonu (kapanis) kume sonundan sonra -> rev.11 kume sonu kaydi kurali."""
    bas, son = U("2025-06-01"), U("2025-09-03 20:00")
    m, f = _kume_dunyasi(bas, son)
    z = izgara_4h(m, bas=bas, son=KESIF_SONU)
    v, s = _f24(f, z[-12:], kume_son=KESIF_SONU)
    assert uyusmayan(v, s) == 0 and np.isnan(v[-1]) and np.isfinite(v[0])


def test_G13_3_h2_funding_penceresi_kume_basini_asar():
    bas, son = U("2025-08-01"), U("2025-09-20 20:00")
    m, f = _kume_dunyasi(bas, son)
    z = izgara_4h(m, bas=C2_BASI, son=son)[:12]
    v, s = _f24(f, z, kume_bas=C2_BASI, kume_son=C2_SONU)
    assert uyusmayan(v, s) == 0 and np.isnan(v[0]) and np.isfinite(v[-1])


def test_G13_4_sonraki_kumenin_ilk_kaydi_tolerans_icinde_okunmaz():
    bas, son = U("2025-06-01"), U("2025-08-31 20:00")
    m = mumlar(bas=bas, son=son)
    f = fonlama(bas=bas, son=U("2025-08-31 12:00"))
    f = _kayit_ekle(f, C2_BASI + pd.Timedelta(seconds=20), 1e-4)
    z = izgara_4h(m, bas=bas, son=son)[-3:]
    v, s = _f24(f, z, kume_son=KESIF_SONU)
    assert uyusmayan(v, s) == 0 and np.isnan(v[-1])


def test_G13_5_c2_sonu_ve_son_barin_bir_saniye_sonraki_kapanisi():
    bas, son = U("2026-05-01"), U("2026-08-31 20:00")
    m = mumlar(bas=bas, son=son + G(3))
    f = fonlama(bas=bas, son=son + G(3))
    z = izgara_4h(m, bas=bas, son=son)[-8:]
    assert z[-1] + H(1) - C2_SONU == pd.Timedelta(seconds=1)
    v, s = _f24(f, z, kume_bas=C2_BASI, kume_son=C2_SONU)
    assert uyusmayan(v, s) == 0
    _hepsi_ayni(_vektor_4h(m, z, kume_bas=C2_BASI, donem_bas=bas), _skaler_4h(m, z, kume_bas=C2_BASI, donem_bas=bas))


# --- G16: gelecege bakis ----------------------------------------------------------------------------------------

def _satir(m, g, f, t4, t1):
    z4, z1 = pd.DatetimeIndex([t4]), pd.DatetimeIndex([t1])
    s = {"kume_baslangic": None, "donem_baslangic": BAS}
    degerler = {**{f"4h.{a}": v[0] for a, v in _vektor_4h(m, z4).items()},
                **{f"1d.{a}": v[0] for a, v in _vektor_1d(g, z1).items()},
                "funding_24s": sk.h2_funding_24s(f, z4, kume_bitis=None, **s)[0]}
    for bar, z in ((config.BAR_4H, z4), (config.BAR_1D, z1)):
        u = _uygunluk(g, z, bar, BAS).iloc[0]
        degerler[f"uygun.{bar}"], degerler[f"medyan.{bar}"] = float(u["uygun"]), u["medyan_hacim"]
    for hipotez, z in (("H1", z4), ("H2", z4), ("H3", z1)):
        p = sk.capasiz_pencereler(hipotez, 3 if hipotez == "H2" else None, z, mumlar_4h=m, gunluk=g, funding=f,
                                  kume_bitis=None, **s)
        degerler[f"capasiz.{hipotez}"] = float(sk.capasiz_hesaplanabilir(hipotez, p)[0])
    return degerler


@pytest.mark.parametrize("degisiklik", ["fiyat", "hacim", "yokluk", "bozuk_hucre", "funding_orani"])
def test_G16_t_den_sonraki_degisiklik_t_satirini_degistirmez(degisiklik):
    """Fiyat, hacim, bar varligi ve funding orani t'nin kapanisindan SONRA degisir; t satirinin sinyal pencereleri,
    uygunluk, capasiz hesaplanabilirlik ve funding penceresi degismez. (Plan, cikis ve funding toplami gelecegi
    MESRU olarak kullanir; onlar bu modulde degildir.) 1d'de t gunu kapanmadan sonraki gunler degisir."""
    t4, t1 = U("2024-05-20 08:00"), U("2024-05-20")
    m, f = mumlar(), fonlama()
    temel = _satir(m, gunluk(m), f, t4, t1)
    sinir4, sinir1 = t4 + H(1), t1 + G(1)
    m2, f2 = m.copy(), f.copy()
    gelecek = m2["open_time"] >= max(sinir4, sinir1)
    if degisiklik == "fiyat":
        m2.loc[gelecek, ["open", "high", "low", "close"]] *= 3.0
    elif degisiklik == "hacim":
        m2.loc[gelecek, ["volume", "quote_volume"]] *= 0.001
    elif degisiklik == "yokluk":
        m2 = m2.loc[~gelecek | (np.arange(len(m2)) % 3 != 0)].reset_index(drop=True)
    elif degisiklik == "bozuk_hucre":
        m2.loc[gelecek, "close"] = np.nan
    else:
        f2.loc[f2["odeme_zamani"] > sinir4 + pd.Timedelta(minutes=1), "oran_8h"] = np.inf
    assert _satir(m2, gunluk(m2), f2, t4, t1).keys() == temel.keys()
    yeni = _satir(m2, gunluk(m2), f2, t4, t1)
    farkli = [a for a in temel if not ayni(temel[a], yeni[a])]
    assert farkli == []


# --- G18: H1 tepe penceresi -------------------------------------------------------------------------------------

PUMP = U("2024-05-01 08:00")


def _tepe(m, teyitler, pump=PUMP, **sinir):
    s = {"kume_baslangic": None, "donem_baslangic": BAS} | sinir
    z = pd.DatetimeIndex(teyitler)
    return sk.h1_tepe(m, pump, z, **s), [ref.h1_tepe(m, pump, t, **s) for t in z]


def test_G18_tepe_bir_ile_on_iki_bar_arasi_skalerle_ayni():
    m = mumlar()
    v, s = _tepe(m, [PUMP + H(n) for n in range(1, 13)])
    assert uyusmayan(v, s) == 0 and np.isfinite(v).all()
    yuksek = m.set_index("open_time")["high"]
    assert v[0] == yuksek[PUMP], "tek barlik tepe = pump barinin high'i (pump dahil)"
    assert v[2] == yuksek[PUMP:PUMP + H(2)].max(), "teyit bari haric"


@pytest.mark.parametrize("n", [0, 13, -1])
def test_G18_tanimsiz_teyit_iki_tarafta_ayni_sinif(n):
    m = mumlar()
    with pytest.raises(sinyal.TepePenceresiKurulamaz):
        ref.h1_tepe(m, PUMP, PUMP + H(n), kume_baslangic=None, donem_baslangic=BAS)
    with pytest.raises(sinyal.TepePenceresiKurulamaz):
        sk.h1_tepe(m, PUMP, pd.DatetimeIndex([PUMP + H(n)]), kume_baslangic=None, donem_baslangic=BAS)


def test_G18_tepe_tamligi_ve_teyit_barinin_kendi_high_i():
    teyitler = [PUMP + H(n) for n in range(1, 13)]
    # Pump barinin kendisi eksik: her tepe NaN.
    v, s = _tepe(mumlar(bozuk=[PUMP]), teyitler)
    assert uyusmayan(v, s) == 0 and np.isnan(v).all()
    # Pencere ici bir bar (pump+3) eksik: n >= 4 olan tepeler NaN, n <= 3 olanlar degil.
    v, s = _tepe(mumlar(bozuk=[PUMP + H(3)]), teyitler)
    assert uyusmayan(v, s) == 0
    assert np.isfinite(v[:3]).all() and np.isnan(v[3:]).all()
    # Teyit barinin kendi hucresi bozuk: tepe degismez (teyit bari tepeye girmez).
    temel, _ = _tepe(mumlar(), [PUMP + H(5)])
    v, s = _tepe(mumlar(bozuk=[PUMP + H(5)]), [PUMP + H(5)])
    assert ayni(v[0], temel[0]) and ayni(v[0], s[0])


def test_G18_teyit_basina_capa_dizisi_skalerle_ayni():
    """Esitlik betiginin sabit capa kurali (t - (1 + i mod 12) x 4h): her teyidin kendi pump bari; pencere ici eksik
    bar bazi tepeleri NaN yapar."""
    m = mumlar(bozuk=[U("2024-05-03 04:00")])
    z = izgara_4h(m)
    z = z[(z > U("2024-05-01")) & (z < U("2024-05-06"))]
    capa = pd.DatetimeIndex([x - H(1 + i % 12) for i, x in enumerate(z)])
    s = {"kume_baslangic": None, "donem_baslangic": BAS}
    v = sk.h1_tepe(m, capa, z, **s)
    r = [ref.h1_tepe(m, c, x, **s) for c, x in zip(capa, z)]
    assert uyusmayan(v, r) == 0 and np.isnan(v).any() and np.isfinite(v).any()
    with pytest.raises(ValueError):
        sk.h1_tepe(m, capa[:-1], z, **s)


def test_G18_capa_donem_ve_kume_icinde_olmali():
    m = mumlar(oncesi_gun=10)
    pump = BAS - H(1)
    v, s = _tepe(m, [pump + H(n) for n in (1, 2, 6)], pump=pump)
    assert uyusmayan(v, s) == 0 and np.isnan(v).all(), "pump bari donem basindan once"
    v, s = _tepe(m, [BAS + H(n) for n in (1, 2)], pump=BAS, kume_baslangic=BAS + H(1))
    assert uyusmayan(v, s) == 0 and np.isnan(v).all(), "pump bari kume basindan once"


# --- G20 ve saflik -----------------------------------------------------------------------------------------------

def test_G20_izgara_bicimi_denetlenir():
    m = mumlar()
    with pytest.raises(TypeError):
        sk.h1_dip(m, pd.DatetimeIndex([pd.Timestamp("2024-05-01")]), **SINIR)
    with pytest.raises(pencere.ZamanDizisiHatasi):
        sk.h1_dip(m, pd.DatetimeIndex([U("2024-05-01 08:00"), U("2024-05-01 04:00")]), **SINIR)
    with pytest.raises(ValueError):
        sk.h3_sma50(gunluk(m), pd.DatetimeIndex([U("2024-05-01 08:00")]), **SINIR)


def test_G20_yardimcinin_izgarasi_kuruculara_verilir():
    """Sentetik kapi dunyasinda yardimcinin izgarasi ile kurulan seri, ayni izgarada skalerle bit duzeyinde ayni."""
    from data import pozisyon
    from kapi_yardimcisi import veri

    m = mumlar(bas=U("2024-01-01"), son=U("2024-03-31 20:00"))
    f = fonlama(bas=U("2024-01-01"), son=U("2024-03-31 20:00"))
    kimlik = veri(m, f, U("2024-01-01"), U("2024-03-31 20:00"))
    z = pozisyon.hipotez_izgarasi_barlari("H1", kume="KESIF", **kimlik)
    kb, ks = pozisyon.kume_sinirlari("KESIF")
    m4, _, _ = pozisyon._karar_verisi(kimlik["sembol"], "KESIF", kume_baslangic=kb, kume_bitis=ks,
                                     donem_baslangic=U("2024-01-01"), donem_bitis=U("2024-03-31 20:00"))
    v = sk.h1_hacim_medyani_180(m4, z, kume_baslangic=kb, donem_baslangic=U("2024-01-01"))
    s = [ref.h1_hacim_medyani_180(m4, t, kume_baslangic=kb, donem_baslangic=U("2024-01-01")) for t in z]
    assert uyusmayan(v, s) == 0 and np.isfinite(s).any()


_YASAK_ADLAR = {"_karar_verisi", "_karar_girdisi", "_kume_verisi", "_kume_verisi_yukle", "_veri_yukle", "kume_bellegi",
                "getir", "mumlari_yukle", "funding_yukle", "ham_funding_yukle", "ham_mumlari_yukle", "evren_yukle",
                "split_oku", "yukle", "onbellekten_oku", "zip_indir", "binance_vision", "bv", "split", "pozisyon",
                "universe", "onay_baglami_dogrula", "kesif_baglami_dogrula", "kesif_kosusu", "_erisim_denetimi",
                "read_parquet", "read_csv", "open", "subprocess", "requests", "urllib", "socket"}


def test_saflik_yukleyici_bellek_ve_erisim_denetimi_cagirmaz():
    import test_skaler_referans_dayanilan as dpd

    metin = (KOK / "data" / "seri_kurucu.py").read_text(encoding="utf-8")
    agac = ast.parse(metin)
    adlar = {d.id for d in ast.walk(agac) if isinstance(d, ast.Name)}
    adlar |= {d.attr for d in ast.walk(agac) if isinstance(d, ast.Attribute)}
    ice_aktarma = {a.name for d in ast.walk(agac) if isinstance(d, (ast.Import, ast.ImportFrom)) for a in d.names}
    ice_aktarma |= {d.module for d in ast.walk(agac) if isinstance(d, ast.ImportFrom) and d.module}
    assert not (adlar | ice_aktarma) & _YASAK_ADLAR, sorted((adlar | ice_aktarma) & _YASAK_ADLAR)
    guvenlik = {ad.rpartition(".")[2] for ad in dpd.GUVENLIK}
    assert not adlar & guvenlik - {"ZamanDizisiHatasi"}, sorted(adlar & guvenlik)
    assert set(ice_aktarma) <= {"annotations", "math", "MappingProxyType", "numpy", "pandas", "config", "eligibility",
                                "funding", "klines", "pencere", "sinyal", "__future__", "types", "data"}


def test_saflik_veri_cercevesi_girdisini_degistirmez():
    m, f = mumlar(), fonlama()
    g = gunluk(m)
    kopyalar = (m.copy(), f.copy(), g.copy())
    z4, z1 = izgara_4h(m), izgara_1d(g)
    s = {"kume_baslangic": None, "kume_bitis": None, "donem_baslangic": BAS}
    for h, z in (("H1", z4), ("H2", z4), ("H3", z1)):
        sk.capasiz_pencereler(h, 3 if h == "H2" else None, z, mumlar_4h=m, gunluk=g, funding=f, **s)
    sk.uygunluk(g, z1, config.BAR_1D, donem_baslangic=BAS, donem_bitis=SON, kume_baslangic=None,
                asgari_hacim=config.ASGARI_HACIM_1D, asgari_listeleme_yasi_gun=config.ASGARI_LISTELEME_YASI_GUN)
    for once_, sonra_ in zip(kopyalar, (m, f, g)):
        pd.testing.assert_frame_equal(once_, sonra_)


def test_tarama_analiz_kodunda_seri_kurucu_yasak(tmp_path):
    from tarama_yardimcisi import seri_kurucu_ihlalleri

    (tmp_path / "study").mkdir()
    for ad, icerik in (("a.py", "from data import seri_kurucu\n"), ("b.py", "import data.seri_kurucu as s\n"),
                       ("c.py", "from data.seri_kurucu import h1_dip\n"), ("d.py", "seri = 1  # seri metni serbest\n")):
        (tmp_path / "study" / ad).write_text(icerik, encoding="utf-8")
    (tmp_path / "analysis" / "00_veri_denetimi").mkdir(parents=True)
    (tmp_path / "analysis" / "00_veri_denetimi" / "baska.py").write_text("from data import seri_kurucu\n",
                                                                         encoding="utf-8")
    (tmp_path / "analysis" / "00_veri_denetimi" / "esitlik_seri.py").write_text("from data import seri_kurucu\n",
                                                                                encoding="utf-8")
    assert seri_kurucu_ihlalleri(kok=tmp_path) == ["analysis/00_veri_denetimi/baska.py", "study/a.py", "study/b.py",
                                                   "study/c.py"]


def test_tarama_depoda_seri_kurucu_ihlali_yok():
    from tarama_yardimcisi import seri_kurucu_ihlalleri

    assert seri_kurucu_ihlalleri() == []
