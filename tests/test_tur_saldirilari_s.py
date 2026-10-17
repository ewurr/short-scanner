"""Rev.11 uygulamasinin tur sonu sizinti saldirilari (sizinti testcisi, tur S).

Saldirilan basliklar (hepsi bu turda yazilan kod; on-kayit §5 "Pencere sinirlari", "Pencere
sinirlarinin tamami", §6 "Kontrolun ne olctugu" ve "Ornekleme kurallari", §5 rev.11 olay dizisi):

  1. Pencere sinirlari (`data/sinyal.py`): her pencerenin bir bar kisa/uzun olmasi, t barinin
     yanlis icerilmesi, donem/kume asimi, tz'siz/tekrarli/sirasiz damga, sonsuz hucre, turetilmis
     seri islemleri (kaynak taramasi). `h1_hacim_medyani_180` ic pencere kapsami ([t-184 .. t]) ve
     `h1_tepe`nin pump -> teyit-1 araligi eksik-bar taramasiyla sinandi. SAVUSTURULDU.
  2. Kontrol tanimi (`pozisyon.olay_karari`, `rol` / `capa`): uydurma capa, rol/yapilandirma
     sahteciligi (imza), K2 adayinin olay uretmesi, K1'in uygunluk/donem/yapilandirma atlatmasi.
     Kapi tarafi SAVUSTURULDU. BULGU: olay dizisi (`dizi.olay_dizisi`) `karar` ciktisini
     dogrulamiyor (asagida B1).
  3. Bekleme suresi (`data/dizi.py`): ust uc kenarlari (+-1 dk, +-1 ns), ufuk degeri dogrulamasi,
     bekleme icindeki barin olay sayilmamasi, kapidan gecmeyen adayin beklemeyi baslatmamasi,
     donem sifirlama, yapilandirmalarin birbirinden bagimsizligi. SAVUSTURULDU (B1 haric).
  4. H1 tek izleme: teyit barinin tek olay saymasi, ikinci pump'in izlemeyi yeniden baslatmamasi,
     12 barlik sayacin ilk pump'tan olculmesi, izlemenin bitmesi. Dizi mantigi SAVUSTURULDU; BULGU
     B3: 12 bar siniri bar varligina bagli.
  5. H3 ilk gun: kesintisiz dizinin ikinci gunu, hesaplanamayan gunun diziyi kesmesi. SAVUSTURULDU;
     BULGU B2: dizi sureklilik denetimi `zamanlar` bitisikligine dayaniyor, takvime degil.
  6. Ornekleme (`data/ornekleme.py`): iadesizlik, aday/koşu sirasindan bagimsizlik, alt tohumun
     her demet ogesine duyarliligi, 10'dan az aday, K1 mesafe kenarlari, K2 havuzu. SAVUSTURULDU;
     BULGU B4: alt tohum UTC olmayan saat dilimli damgada degisiyor.

BULGULAR (xfail strict, 6 test):
  B1 (3 test) `dizi.olay_dizisi` `karar`dan donen nesneyi `pozisyon.onay_dogrula`dan gecirmez ve
     rol/hipotez/yapilandirma eslesmesine bakmaz: rastgele nesne, K1 rolunde onayli pozisyon ve
     baska yapilandirmanin pozisyonu OLAY sayilir ve beklemeyi baslatir.
  B2 (1 test) H3'te `zamanlar` listesinde eksik gun varsa dizi kesilmez.
  B3 (1 test) H1'de 12. barin zamanlar'da bulunmamasi izlemeyi 13. bara tasir.
  B4 (1 test) `ornekleme.alt_tohum` ayni anin UTC disi saat diliminde verilmesiyle degisir.

NOT: Bu dosya yazilirken calistirma araci yoktu; testler kod okunarak kuruldu. Bir "gecen" testin
kirmizi cikmasi dunya kurulumunun hatasi olabilir (olumlu-kontrol testleri bunu ayirt eder:
`test_*_olumlu_kontrol_*`). Getiri hesaplanmaz, sinyal degeri raporlanmaz; aga cikilmaz.
"""

from __future__ import annotations

import ast
import dataclasses
import datetime as dt
import math
import pathlib

import numpy as np
import pandas as pd
import pytest

import config
from data import dizi, ornekleme, pencere, pozisyon, sinyal
from kapi_yardimcisi import veri
from dizi_yardimcisi import olaylar_kur, olaylar_sembollerde, tek_olay
from ornekleme_yardimcisi import k1_adaylari_kur, k2_adaylari_kur
from ornekleme_yardimcisi import ornekle as yardimci_ornekle
from sinyal_yardimcisi import kontrol, olay, yapilandirma
from uygunluk_yardimcisi import UYGUN_ONCELIK, esikler


DIZI_KIMLIGI = dict(sembol="TESTONAYUSDT", kume="KESIF", donem_no=0)

def T(s):
    return pd.Timestamp(s, tz="UTC")


H4 = pd.Timedelta(hours=4)
D1 = pd.Timedelta(days=1)

# ======================================================================================
# 1. PENCERE SINIRLARI (data/sinyal.py)
# ======================================================================================

N4 = 400
Z4 = pd.date_range(T("2024-06-01 00:00"), periods=N4, freq="4h")
TI = 300                                   # t barinin indeksi
SINIR = {"kume_baslangic": None, "donem_baslangic": Z4[0]}

N1 = 300
Z1 = pd.date_range(T("2024-01-01"), periods=N1, freq="D")
T1 = 250


def _m4(**sutun) -> pd.DataFrame:
    d = {"open_time": Z4, "open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "quote_volume": 1.0}
    d.update(sutun)
    return pd.DataFrame(d)


def _g1(**sutun) -> pd.DataFrame:
    d = {"open_time": Z1, "open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "quote_volume": 1.0}
    d.update(sutun)
    return pd.DataFrame(d)


def _sil(m: pd.DataFrame, i: int) -> pd.DataFrame:
    return m.drop(index=i).reset_index(drop=True)


def _kenarlar(a: int, b: int):
    """[a, b] penceresinin iki kenarinin iki yani ve ortasi: eksik-bar taramasi icin."""
    return sorted({a - 2, a - 1, a, a + 1, (a + b) // 2, b - 1, b, b + 1, b + 2})


def _nan_olan(fonk, m, tarama) -> set:
    """Tarama kumesindeki her bari TEK TEK siler; degeri NaN olan indeks kumesini doner."""
    sonuc = set()
    for i in tarama:
        if math.isnan(fonk(_sil(m, i))):
            sonuc.add(i)
    return sonuc


def _degisen(fonk, m, sutun, deger, tarama) -> set:
    """Tarama kumesindeki her barin `sutun` hucresini TEK TEK `deger` yapar; sonucu degisenleri doner."""
    taban = fonk(m)
    sonuc = set()
    for i in tarama:
        mm = m.copy()
        mm.loc[i, sutun] = deger
        if fonk(mm) != taban:
            sonuc.add(i)
    return sonuc


def _aralik(tarama, a, b) -> set:
    return {i for i in tarama if a <= i <= b}


def test_h1_dip_penceresi_t_eksi_6_ile_t_eksi_1_arasidir_t_dahil_degildir():
    """On-kayit §5 "Pencere sinirlari": "H1'in 6 barlik dip penceresi ... t'yi icermez (t-6..t-1)".
    Saldiri: her bari tek tek silerek ve tek tek bozarak pencerenin tam kapsamini olc; bir bar kisa
    ya da uzun, ya da t dahil olursa kume farki cikar."""
    m = _m4(low=1000.0 + np.arange(N4))
    f = lambda mm: sinyal.h1_dip(mm, Z4[TI], **SINIR)  # noqa: E731
    tarama = _kenarlar(TI - 6, TI - 1)
    assert f(m) == 1000.0 + (TI - 6)
    assert _nan_olan(f, m, tarama) == _aralik(tarama, TI - 6, TI - 1)
    assert _degisen(f, m, "low", -1e9, tarama) == _aralik(tarama, TI - 6, TI - 1)


def test_h1_hacim_6_penceresi_t_eksi_5_ile_t_arasidir_t_dahildir():
    """On-kayit §5 "Pencere sinirlari": "6 barlik toplam pencereleri t barini icerir" ([t-5 .. t])."""
    v = 1.0 + np.arange(N4)
    m = _m4(quote_volume=v)
    f = lambda mm: sinyal.h1_hacim_6(mm, Z4[TI], **SINIR)  # noqa: E731
    tarama = _kenarlar(TI - 5, TI)
    assert f(m) == pytest.approx(float(v[TI - 5:TI + 1].sum()))
    assert _nan_olan(f, m, tarama) == _aralik(tarama, TI - 5, TI)
    assert _degisen(f, m, "quote_volume", 1e9, tarama) == _aralik(tarama, TI - 5, TI)


def test_h1_hacim_medyani_180_degeri_kayan_pencere_ve_kapsam_t_eksi_184_ile_t():
    """On-kayit §5 "Pencere sinirlari": 180 barlik dis pencere t'yi icerir; her dis barin ic penceresi
    o bari iceren 6 barlik toplam; ic pencerelerin birlesimi [t-184 .. t] (185 bar). Saldiri 1: deger
    cakismayan bloklarla ya da yanlis kaydirmayla hesaplanirsa beklenen medyandan sapar. Saldiri 2: her
    barin eksikligi tek tek sinanir; NaN kumesi tam [t-184 .. t] olmali (ilk ic pencere dahil)."""
    v = np.random.default_rng(7).uniform(1, 100, N4)
    m = _m4(quote_volume=v)
    f = lambda mm: sinyal.h1_hacim_medyani_180(mm, Z4[TI], **SINIR)  # noqa: E731
    beklenen = float(np.median([v[s - 5:s + 1].sum() for s in range(TI - 179, TI + 1)]))
    assert f(m) == pytest.approx(beklenen)
    tarama = _kenarlar(TI - 184, TI)
    assert _nan_olan(f, m, tarama) == _aralik(tarama, TI - 184, TI)


def test_h1_hacim_medyani_180_gelecek_barlar_degeri_degistirmez():
    """CLAUDE.md §3 madde 6 (geleceye bakis yok): t+1 ve sonrasi barlari bozmak t'deki degeri degistirmemeli;
    t barinin kendi hacmi ise (pencere t'yi icerir) degeri degistirir (yani pencere t'de bitiyor)."""
    v = np.random.default_rng(11).uniform(1, 100, N4)
    f = lambda mm: sinyal.h1_hacim_medyani_180(mm, Z4[TI], **SINIR)  # noqa: E731
    taban = f(_m4(quote_volume=v))
    gelecek = v.copy()
    gelecek[TI + 1:] = 1e12
    assert f(_m4(quote_volume=gelecek)) == taban
    yuksek, dusuk = v.copy(), v.copy()
    yuksek[TI], dusuk[TI] = 1e12, -1e12
    # t barinin hacmi pencerede (son ic toplamda): deger medyanin altindaysa yukari, ustundeyse asagi
    # cekmek medyani degistirir; ikisinden en az biri taban degerden farkli olmali.
    assert f(_m4(quote_volume=yuksek)) != taban or f(_m4(quote_volume=dusuk)) != taban


def test_h1_hacim_medyani_180_donem_ve_kume_sinirini_ic_pencereden_asamaz():
    """On-kayit §5 "Pencere sinirlari" + §3 "Kume siniri ve geriye bakis". Saldiri: turetilmis seri
    (rolling) kapiyi atlatir cunku yalnizca dis pencereyi denetler; ilk ic pencere donem/kume basindan
    oncesine uzanir. Donem/kume basi dis pencerenin basinda ([t-179]) iken deger NaN olmali; tam ic
    kapsamin basinda ([t-184]) sonlu olmali. Tolerans: +59 sn sonlu, +60 sn NaN, +1 ns sonlu."""
    m = _m4(quote_volume=np.random.default_rng(3).uniform(1, 100, N4))
    ilk = Z4[TI - 184]

    def f(donem=Z4[0], kume=None):
        return sinyal.h1_hacim_medyani_180(m, Z4[TI], kume_baslangic=kume, donem_baslangic=donem)

    assert not math.isnan(f(donem=ilk))
    assert math.isnan(f(donem=Z4[TI - 179]))                       # dis pencere basi: ic pencere tasar
    assert math.isnan(f(donem=Z4[TI - 183]))
    assert not math.isnan(f(donem=ilk + pd.Timedelta(seconds=59)))
    assert not math.isnan(f(donem=ilk + pd.Timedelta(1, "ns")))
    assert math.isnan(f(donem=ilk + pd.Timedelta(seconds=60)))
    # Ayni sinir kume basi olarak
    assert not math.isnan(f(kume=ilk))
    assert math.isnan(f(kume=Z4[TI - 179]))
    assert math.isnan(f(kume=ilk + pd.Timedelta(seconds=60)))


def test_h1_tepe_penceresi_pump_dahil_teyit_haric_ve_eksik_bar_nani():
    """On-kayit §5 H1 madde 2 (rev.11): "pump bari dahil, teyit barindan bir onceki bara kadar ... Teyit
    barinin kendi `high` degeri tepeye girmez"; "pump barindan teyit barinin bir oncesine kadar beklenen
    barlardan biri bile eksikse tepe hesaplanmaz". Saldiri: pump'tan onceki bar ve teyit barinin
    kendisi devasa high ile bozulur; tepe yalnizca [pump .. teyit-1] olmali; eksik bar taramasi."""
    p, te = 200, 203
    yuksek = np.full(N4, 100.0)
    yuksek[199] = 1000.0     # pump'tan bir onceki: tepeye girmemeli
    yuksek[200] = 500.0      # pump barinin kendisi: girmeli
    yuksek[201] = 300.0
    yuksek[203] = 900.0      # teyit barinin kendisi: girmemeli
    yuksek[204] = 2000.0     # gelecek
    m = _m4(high=yuksek)
    f = lambda mm: sinyal.h1_tepe(mm, Z4[p], Z4[te], **SINIR)  # noqa: E731
    assert f(m) == 500.0
    tarama = _kenarlar(p, te - 1)
    assert _nan_olan(f, m, tarama) == _aralik(tarama, p, te - 1)
    assert _degisen(f, m, "high", 1e9, tarama) == _aralik(tarama, p, te - 1)
    # Teyit barinin kendisi eksik olsa da tepe penceresi (teyit haric) tamdir.
    assert f(_sil(m, te)) == 500.0


def test_h1_tepe_12_bar_siniri_ve_gecersiz_teyit_konumlari():
    """On-kayit §5 H1 madde 3: teyit, pump barindan sonraki 12 bar icinde. Saldiri: tam 12 bar (kabul),
    13 bar (red), pump'in kendisi/oncesi (red), 4h izgarasinda olmayan teyit (red), tz'siz teyit (red)."""
    p = 200
    yuksek = np.full(N4, 100.0)
    yuksek[p] = 500.0
    m = _m4(high=yuksek)
    assert sinyal.h1_tepe(m, Z4[p], Z4[p + 12], **SINIR) == 500.0
    for gecersiz in (Z4[p + 13], Z4[p], Z4[p - 1], Z4[p + 3] + pd.Timedelta(hours=1)):
        with pytest.raises(ValueError):
            sinyal.h1_tepe(m, Z4[p], gecersiz, **SINIR)
    with pytest.raises(TypeError):
        sinyal.h1_tepe(m, Z4[p], Z4[p + 3].tz_localize(None), **SINIR)


def test_h1_tepe_kume_baslangicini_pump_barindan_once_acamaz():
    """On-kayit §3 "Kume siniri ve geriye bakis": tepe penceresi kume basindan once baslayamaz. Saldiri:
    kume basi pump'tan bir bar sonra (veri kume oncesinde de mevcut) -> NaN olmali."""
    m = _m4()
    assert math.isnan(sinyal.h1_tepe(m, Z4[200], Z4[203], kume_baslangic=Z4[201], donem_baslangic=Z4[0]))
    assert not math.isnan(sinyal.h1_tepe(m, Z4[200], Z4[203], kume_baslangic=Z4[200], donem_baslangic=Z4[0]))


def test_kapanis_30_once_tamlik_penceresi_31_bar_iki_ucu_degil_butun_aralik():
    """On-kayit §5 rev.11: "close[t-30] iki uclu bir orandir ... Tamlik penceresi kapali araliktir:
    [t-30 .. t], yani 31 bar; araliktaki beklenen barlardan biri bile eksikse deger hesaplanmaz".
    Saldiri: yalnizca iki ucu (t-30 ve t) denetleyen bir uygulama ortadaki eksigi gecirir."""
    m = _m4(close=1.0 + np.arange(N4))
    f = lambda mm: sinyal.kapanis_30_once(mm, Z4[TI], config.BAR_4H, **SINIR)  # noqa: E731
    assert f(m) == 1.0 + (TI - 30)
    tarama = _kenarlar(TI - 30, TI)
    assert _nan_olan(f, m, tarama) == _aralik(tarama, TI - 30, TI)
    # Donem basi t-30'dan sonra ise NaN (pencere donemi asar)
    assert math.isnan(sinyal.kapanis_30_once(m, Z4[TI], config.BAR_4H, kume_baslangic=None,
                                             donem_baslangic=Z4[TI - 29]))


def test_kapanis_30_once_hucre_nan_ve_sonsuz_ve_metin_pencerede_hesaplanamaz_yapar():
    """On-kayit §2 rev.11: "fiyat ve hacim hucrelerinin tamami sayi olmalidir"; NaN/sonsuz/metin hucre
    barin eksik sayilmasi demektir. Saldiri: pencere ortasina NaN, +inf, -inf ve metin koy."""
    for kotu in (np.nan, np.inf, -np.inf, "abc"):
        close = pd.Series(1.0 + np.arange(N4), dtype=object)
        close[TI - 15] = kotu
        m = _m4(close=close)
        assert math.isnan(sinyal.kapanis_30_once(m, Z4[TI], config.BAR_4H, **SINIR)), kotu


def test_sinyal_pencereleri_tzsiz_tekrarli_damgada_sessizce_nan_uretmez():
    """pencere.ZamanDizisiHatasi: tz'siz ya da tekrarli damga bir VERI BOZUKLUGUDUR, sessiz NaN degil.
    Sirasiz girdi ise sessizce siralanir ve sonuc degismez (seriyi karistirma saldirisi)."""
    m = _m4(low=1000.0 + np.arange(N4))
    taban = sinyal.h1_dip(m, Z4[TI], **SINIR)
    naif = m.copy()
    naif["open_time"] = pd.DatetimeIndex(naif["open_time"]).tz_localize(None)
    with pytest.raises(pencere.ZamanDizisiHatasi):
        sinyal.h1_dip(naif, Z4[TI], **SINIR)
    tekrar = pd.concat([m, m.iloc[[TI - 3]]], ignore_index=True)
    with pytest.raises(pencere.ZamanDizisiHatasi):
        sinyal.h1_dip(tekrar, Z4[TI], **SINIR)
    karisik = m.sample(frac=1.0, random_state=5).reset_index(drop=True)
    assert sinyal.h1_dip(karisik, Z4[TI], **SINIR) == taban
    ters = m.iloc[::-1].reset_index(drop=True)
    assert sinyal.h1_dip(ters, Z4[TI], **SINIR) == taban


def test_sinyal_t_tzsiz_ya_da_izgara_disi_olunca_tzsiz_hata_izgara_disi_nan():
    """CLAUDE.md §5 (UTC): tz'siz t TypeError. Izgara disi t (barlarla hizasiz) pencereyi bulamaz ve NaN
    doner (bar_degeri de NaN); sessizce yakin bara kaymaz."""
    m = _m4(low=1000.0 + np.arange(N4), close=1.0 + np.arange(N4))
    with pytest.raises(TypeError):
        sinyal.h1_dip(m, Z4[TI].tz_localize(None), **SINIR)
    with pytest.raises(TypeError):
        sinyal.bar_degeri(m, Z4[TI].tz_localize(None), "close")
    kayik = Z4[TI] + pd.Timedelta(hours=1)
    assert math.isnan(sinyal.h1_dip(m, kayik, **SINIR))
    assert math.isnan(sinyal.bar_degeri(m, kayik, "close"))
    assert sinyal.bar_degeri(m, Z4[TI] + pd.Timedelta(seconds=59), "close") == 1.0 + TI   # zaman toleransi


def test_h3_30_gun_hacim_penceresi_t_dahil_30_gun_degeri_ve_eksik_gun_taramasi():
    """On-kayit §5 rev.11: "'son 30 gun' t gununu icerir ([t-29 .. t])". Saldiri: 29/31 gunluk ya da t
    haric pencere medyani kaydirir (hacim artan seri); eksik-gun taramasi."""
    v = 1.0 + np.arange(N1)
    m = _g1(quote_volume=v)
    f = lambda mm: sinyal.h3_hacim_medyani_30g(mm, Z1[T1], **SINIR | {"donem_baslangic": Z1[0]})  # noqa: E731
    assert f(m) == pytest.approx(float(np.median(v[T1 - 29:T1 + 1])))
    tarama = _kenarlar(T1 - 29, T1)
    assert _nan_olan(f, m, tarama) == _aralik(tarama, T1 - 29, T1)


def test_h3_120_31_penceresi_90_gun_ve_t_eksi_30_gunu_hicbir_pencereye_girmez():
    """On-kayit §5 rev.11: "'gun -120 ile -31 arasi' t gunune gore sayilir ([t-120 .. t-31], 90 gun). Iki
    pencere arasindaki t-30 gunu hicbir pencereye girmez; bu bilerek korunmustur". Saldiri: t-30 gununu
    silmek 30 gunluk ve 120_31 pencerelerini ETKILEMEMELI, SMA50'yi NaN yapmali."""
    v = 1.0 + np.arange(N1)
    sinir = {"kume_baslangic": None, "donem_baslangic": Z1[0]}
    m = _g1(quote_volume=v, close=v)
    f = lambda mm: sinyal.h3_hacim_medyani_120_31(mm, Z1[T1], **sinir)  # noqa: E731
    assert f(m) == pytest.approx(float(np.median(v[T1 - 120:T1 - 30])))
    tarama = _kenarlar(T1 - 120, T1 - 31)
    assert _nan_olan(f, m, tarama) == _aralik(tarama, T1 - 120, T1 - 31)
    eksik30 = _sil(m, T1 - 30)
    assert f(eksik30) == f(m)
    assert sinyal.h3_hacim_medyani_30g(eksik30, Z1[T1], **sinir) == sinyal.h3_hacim_medyani_30g(m, Z1[T1], **sinir)
    assert math.isnan(sinyal.h3_sma50(eksik30, Z1[T1], **sinir))


def test_h3_sma50_penceresi_t_dahil_50_gun_ve_donem_basi_asimi():
    """On-kayit §5 rev.11: "SMA50 ... son 50 gunun kapanislarinin basit ortalamasidir ve t gununu icerir
    ([t-49 .. t])". Saldiri: 49/51 gunluk ya da t haric ortalama; donem basi t-49'dan sonraysa NaN."""
    c = 1.0 + np.arange(N1) ** 1.3
    m = _g1(close=c)
    sinir = {"kume_baslangic": None, "donem_baslangic": Z1[0]}
    f = lambda mm: sinyal.h3_sma50(mm, Z1[T1], **sinir)  # noqa: E731
    assert f(m) == pytest.approx(float(c[T1 - 49:T1 + 1].mean()))
    tarama = _kenarlar(T1 - 49, T1)
    assert _nan_olan(f, m, tarama) == _aralik(tarama, T1 - 49, T1)
    assert not math.isnan(sinyal.h3_sma50(m, Z1[T1], kume_baslangic=None, donem_baslangic=Z1[T1 - 49]))
    assert math.isnan(sinyal.h3_sma50(m, Z1[T1], kume_baslangic=None, donem_baslangic=Z1[T1 - 48]))
    assert math.isnan(sinyal.h3_sma50(m, Z1[T1], kume_baslangic=Z1[T1 - 48], donem_baslangic=Z1[0]))


def test_sinyal_ve_dizi_ve_ornekleme_kaynaginda_turetilmis_seri_islemi_yok():
    """On-kayit §5 "Pencere sinirlari" / pencere.py "Ic ice ve ofsetli pencereler": turetilmis seri
    (rolling, reindex, ffill, asfreq, ...) kapiyi atlatir. Saldiri: kaynak (AST) taramasi; sinyal.py, dizi.py
    ve ornekleme.py bu islemleri kullanmamali, pencereler yalnizca `pencere` kapisindan gecmeli."""
    yasak = {"rolling", "expanding", "ewm", "ffill", "bfill", "asfreq", "resample", "interpolate", "shift",
             "fillna", "reindex"}
    kok = pathlib.Path(__file__).resolve().parents[1] / "data"
    bulunan = []
    for dosya in ("sinyal.py", "dizi.py", "ornekleme.py"):
        agac = ast.parse((kok / dosya).read_text(encoding="utf-8"))
        for dugum in ast.walk(agac):
            if isinstance(dugum, ast.Attribute) and dugum.attr in yasak:
                bulunan.append((dosya, dugum.attr, dugum.lineno))
    assert bulunan == []


def test_sinyal_pencere_uzunluklari_on_kayit_sabitleriyle_ayni():
    """On-kayit §5 rev.11 pencere uzunluklari: dip 6, hacim toplami 6, medyan 180, izleme 12, 30 bar once 30,
    H3 30/90/31/50. Saldiri: sabitlerden biri sessizce degismis olursa test kirilir."""
    assert (config.H1_DIP_BAR, config.H1_HACIM_TOPLAM_BAR, config.H1_HACIM_MEDYAN_BAR, config.H1_IZLEME_BAR) \
        == (6, 6, 180, 12)
    assert config.OTUZ_BAR_ONCE == 30
    assert (config.H3_HACIM_YAKIN_GUN, config.H3_HACIM_UZAK_GUN, config.H3_HACIM_UZAK_OFSET, config.H3_SMA_GUN) \
        == (30, 90, 31, 50)


# ======================================================================================
# 2. KONTROL TANIMI (pozisyon.olay_karari: rol / capa / yapilandirma)
# ======================================================================================

BG = T("2025-02-10 08:00")
BAS_G = T("2025-01-01 00:00")
ZG = pd.date_range(BAS_G, BG, freq="4h")
DONEM_BAS_G = BAS_G - UYGUN_ONCELIK
PG = 30                  # H1 pump bari indeksi
TEYIT_G = PG + 3         # H1 teyit bari
TH = 40                  # H2 olay bari indeksi


def _fund(oran=1e-4):
    z = pd.date_range(BAS_G, BG + H4, freq="8h")
    return pd.DataFrame({"odeme_zamani": z, "aralik_saat": 8.0, "oran": oran, "oran_8h": oran})


def _bar_dizileri():
    n = len(ZG)
    a = np.full(n, 100.0)
    return a.copy(), a.copy(), a.copy(), a.copy()


def _h1_dunya() -> dict:
    """Pump (idx 30: +30%, hacim 6x) ve teyit (idx 33: close 110 <= 130*0.92, high 115 < tepe 130) kurulu H1
    sentetik sembolu. Tum yapilandirmalarin ilki (theta 0.2, delta 0.08) ve delta 0.12 olay uretir."""
    ac, yu, du, ka = _bar_dizileri()
    hacim = np.where(ZG.hour == 0, 5e7, 0.0)

    def bar(i, o, h, l, c):  # noqa: E741
        ac[i], yu[i], du[i], ka[i] = o, h, l, c

    bar(PG, 100, 130, 100, 130)
    hacim[PG] += 2.5e8
    bar(PG + 1, 126, 126, 120, 125)
    bar(PG + 2, 125, 126, 120, 125)
    bar(TEYIT_G, 112, 115, 108, 110)
    for i in range(PG + 4, len(ZG)):
        bar(i, 110, 110, 110, 110)
    mum = pd.DataFrame({"open_time": ZG, "open": ac, "high": yu, "low": du, "close": ka, "quote_volume": hacim})
    return veri(mum, _fund(), DONEM_BAS_G, BG, uygun_bas=DONEM_BAS_G)


def _h2_dunya() -> dict:
    """H2 olay bari idx 40: close 112 >= 1.10 x close[t-30] (100), close < min(low[t-3..t-1]) (118), funding
    oran 1e-3 >= phi. Idx 35'te yukselis var ama kirilim yok (olay degil)."""
    ac, yu, du, ka = _bar_dizileri()

    def bar(i, o, h, l, c):  # noqa: E741
        ac[i], yu[i], du[i], ka[i] = o, h, l, c

    for i in range(11, TH):
        bar(i, 120, 120, 118, 120)
    bar(TH, 119, 119, 111, 112)
    for i in range(TH + 1, len(ZG)):
        bar(i, 112, 112, 112, 112)
    mum = pd.DataFrame({"open_time": ZG, "open": ac, "high": yu, "low": du, "close": ka})
    return veri(mum, _fund(1e-3), DONEM_BAS_G, BG, uygun_bas=DONEM_BAS_G)


def _karar(dunya, hipotez, t, kw, *, ufuk=18):
    return pozisyon.olay_karari(t, ufuk, config.HIPOTEZ_IZGARASI[hipotez], hipotez=hipotez, birincil_ufuk=18,
                                kume="KESIF", **dunya, **kw, **esikler(config.BAR_4H))


def test_h1_olay_olumlu_kontrol_dunya_kurulumu_dogru():
    """Olumlu kontrol (saldirilarin yanlis nedenle gecmemesi icin): H1 dunyasinda pump bari capasiyla teyit
    barinda olay olusur ve onayli pozisyon rolunu ve yapilandirma kimligini tasir."""
    dunya = _h1_dunya()
    p = _karar(dunya, "H1", ZG[TEYIT_G], olay("H1", capa=ZG[PG]))
    pozisyon.onay_dogrula(p)
    assert p.rol == "olay" and p.hipotez == "H1" and p.yapilandirma == "H1:theta=0.2,delta=0.08"


def test_h2_olay_olumlu_kontrol_dunya_kurulumu_dogru():
    """Olumlu kontrol: H2 dunyasinda t=idx 40 olay uretir; idx 35'te olay olusmaz (kirilim yok)."""
    dunya = _h2_dunya()
    p = _karar(dunya, "H2", ZG[TH], olay("H2"))
    assert p.rol == "olay" and p.yapilandirma == "H2:phi=0.0003,k=3"
    with pytest.raises(pozisyon.SinyalKosuluSaglanmadi):
        _karar(dunya, "H2", ZG[35], olay("H2"))


def test_yapilandirma_gercekten_kapida_kullanilir_delta_016_ayni_teyitte_olay_uretmez():
    """On-kayit §5 rev.11: "Olay ya da kontrol ureten her cagri, hipotezi ve yapilandirmayi birlikte alir".
    Saldiri: yapilandirma yok sayilirsa delta 0.16 de (close 110 > 130 x 0.84 = 109.2) olay uretirdi.
    delta 0.12 olay uretir (110 <= 114.4), delta 0.16 uretmez."""
    dunya = _h1_dunya()
    t, capa = ZG[TEYIT_G], ZG[PG]
    assert _karar(dunya, "H1", t, olay("H1", capa=capa, delta=0.12)).yapilandirma == "H1:theta=0.2,delta=0.12"
    with pytest.raises(pozisyon.SinyalKosuluSaglanmadi):
        _karar(dunya, "H1", t, olay("H1", capa=capa, delta=0.16))


def test_uydurma_capa_non_pump_bari_olay_uretemez():
    """On-kayit §5 H1 + §6 rev.11: capa bir bar zamanidir ve kapi pump kosulunu capada yeniden hesaplar.
    Saldiri: pump olmayan bir bari (pump'tan onceki idx 29) capa olarak ver; teyit kosulu tepe uzerinden
    saglansa bile olay olusmamali."""
    dunya = _h1_dunya()
    with pytest.raises(pozisyon.SinyalKosuluSaglanmadi):
        _karar(dunya, "H1", ZG[TEYIT_G], olay("H1", capa=ZG[PG - 1]))


def test_uydurma_capa_konumlari_t_ile_ayni_gelecek_12_bardan_eski_izgara_disi_tzsiz():
    """On-kayit §5 H1 madde 3: teyit pump'tan sonraki 12 bar icinde. Saldiri: capa = t, capa > t, capa
    13 bar eski, 4h izgarasinda olmayan capa (hepsi hata; hicbiri pozisyon dondurmez), tz'siz capa (TypeError)."""
    dunya = _h1_dunya()
    t = ZG[TEYIT_G]
    for capa in (t, t + H4, ZG[TEYIT_G - 13], ZG[PG] + pd.Timedelta(hours=1)):
        with pytest.raises((ValueError, pencere.OlayOlusmaz)):
            _karar(dunya, "H1", t, olay("H1", capa=capa))
    with pytest.raises(TypeError):
        _karar(dunya, "H1", t, olay("H1", capa=ZG[PG].tz_localize(None)))


def test_capa_yalnizca_h1_olay_rolunde_verilir_baska_her_durumda_hata():
    """On-kayit §6 rev.11: "H1'in kontrol barinda pump bari, dip penceresi ve tepe aranmaz"; H2/H3 t barindan
    hesaplanir. Saldiri: K1/K2'ye capa vermek, H1 olay rolunde capayi atlamak, H2 olayina capa vermek."""
    d1, d2 = _h1_dunya(), _h2_dunya()
    capa = ZG[PG]
    for rol in ("K1", "K2"):
        kw = {"yapilandirma": yapilandirma("H1"), "rol": rol, "capa": capa}
        with pytest.raises(TypeError):
            _karar(d1, "H1", ZG[TEYIT_G], kw)
    with pytest.raises(TypeError):
        _karar(d1, "H1", ZG[TEYIT_G], olay("H1", capa=None))
    with pytest.raises(TypeError):
        _karar(d2, "H2", ZG[TH], {"yapilandirma": yapilandirma("H2"), "rol": "olay", "capa": ZG[TH - 3]})


def test_rol_degeri_uydurulamaz_bilinmeyen_buyuk_harf_str_alt_sinifi_none():
    """On-kayit §6 rev.11: roller "olay", "K1", "K2". Saldiri: "OLAY", "K3", `str` alt sinifi (eq ile yalan),
    None, bytes."""
    class Yalanci(str):
        def __eq__(self, diger):
            return True

        def __hash__(self):
            return hash("olay")

    dunya = _h2_dunya()
    y = yapilandirma("H2")
    for rol, hata in (("OLAY", ValueError), ("K3", ValueError), (Yalanci("olay"), TypeError), (None, TypeError),
                      (b"olay", TypeError)):
        with pytest.raises(hata):
            _karar(dunya, "H2", ZG[TH], {"yapilandirma": y, "rol": rol, "capa": None})


def test_izgara_disi_yapilandirma_uydurulamaz():
    """On-kayit §5 rev.11: "izgarada bulunmayan bir parametre demeti hata verir". Saldiri: theta 0.25,
    0.2000001, float32 yuvarlamasi, fazla/eksik anahtar, baska hipotezin demeti, bool, metin."""
    dunya = _h1_dunya()
    t, capa = ZG[TEYIT_G], ZG[PG]
    kotuler = [
        {"theta": 0.25, "delta": 0.08},
        {"theta": 0.2000001, "delta": 0.08},
        {"theta": np.float32(0.2), "delta": 0.08},
        {"theta": 0.2, "delta": 0.08, "fazla": 1},
        {"theta": 0.2},
        {"phi": 0.0003, "k": 3},
        {"theta": True, "delta": 0.08},
        {"theta": "0.2", "delta": 0.08},
    ]
    for y in kotuler:
        with pytest.raises((sinyal.YapilandirmaHatasi, TypeError)):
            _karar(dunya, "H1", t, {"yapilandirma": y, "rol": "olay", "capa": capa})


def test_onayli_pozisyonun_rolu_yapilandirmasi_hipotezi_imzaya_bagli():
    """On-kayit §6 rev.11 + `pozisyon.onay_dogrula`: rol ve yapilandirma imzaya dahil. Saldiri: K1 pozisyonunu
    `dataclasses.replace` ile olaya cevirmek, olay pozisyonunu K1'e cevirmek, yapilandirma kimligini ve
    hipotezi degistirmek; hepsi onay_dogrula'da ValueError."""
    dunya = _h1_dunya()
    k1 = _karar(dunya, "H1", ZG[TEYIT_G], kontrol("H1", "K1"))
    ev = _karar(dunya, "H1", ZG[TEYIT_G], olay("H1", capa=ZG[PG]))
    ev12 = _karar(dunya, "H1", ZG[TEYIT_G], olay("H1", capa=ZG[PG], delta=0.12))
    assert k1.rol == "K1" and ev.rol == "olay" and ev.yapilandirma != ev12.yapilandirma
    pozisyon.onay_dogrula(k1)
    sahteler = [
        dataclasses.replace(k1, rol="olay"),
        dataclasses.replace(ev, rol="K1"),
        dataclasses.replace(ev, rol="K2"),
        dataclasses.replace(ev, yapilandirma=ev12.yapilandirma),
        dataclasses.replace(ev, hipotez="H2"),
        dataclasses.replace(ev, kume="C2"),
    ]
    for sahte in sahteler:
        with pytest.raises(ValueError):
            pozisyon.onay_dogrula(sahte)


def test_k2_adayi_olay_ureten_barda_kapi_elemez_eleme_ornekleme_adiminda():
    """REV.12 ILE DEGISTI (§6, madde (e)). Rev.11'de H2'nin K2 barinda kapi kosullari hesaplar ve
    saglaniyorsa `OlayUretmis` firlatirdi. Rev.12: "Kontrol barinda sinyal kosullari hicbir amacla
    hesaplanmaz"; K2'nin "o anda olay uretmemis" sarti olay KUMESINE gore, ornekleme adiminda
    uygulanir. Saldiri simdi sunu sorar: kapi olay barini gecirdiginde eleme hala yapiliyor mu?
    Yanit `ornekleme.k2_adaylari`dir (asagidaki H1 testiyle ayni bagimlilik, artik uc hipotezde)."""
    dunya = _h2_dunya()
    assert not hasattr(pozisyon, "OlayUretmis")
    assert _karar(dunya, "H2", ZG[TH], kontrol("H2", "K2")).rol == "K2"
    assert _karar(dunya, "H2", ZG[TH], kontrol("H2", "K1")).rol == "K1"
    assert _karar(dunya, "H2", ZG[35], kontrol("H2", "K2")).rol == "K2"
    # Eleme ornekleme adimindadir: olay ureten sembol havuzdan cikar, verilmezse kalir.
    kur = lambda ss: k2_adaylari_kur(ss, t=ZG[TH], hipotez="H2")  # noqa: E731
    # REV.14 (denetci bulgusu D-B2): olcutun girdisi ham sembol adi degil, AYNI bardaki olay
    # nesneleridir. Iddialar degismedi.
    ureten = olaylar_sembollerde(["AAAUSDT"], t=ZG[TH], hipotez="H2")
    assert ornekleme.k2_adaylari(kur(["AAAUSDT"]), ureten, olay_sembolu="BBBUSDT").ogeler == ()
    assert ornekleme.k2_adaylari(kur(["AAAUSDT"]), [], olay_sembolu="BBBUSDT").ogeler == ("AAAUSDT",)


def test_h1_k2_kapisi_olay_barini_kendisi_elemez_havuz_k2_adaylari_ile_elenir():
    """On-kayit §6 rev.11: H1'in kontrol barinda pump bari/tepe aranmaz, bu yuzden K2'nin 'olay uretmemis'
    sarti H1'de ornekleme adiminda uygulanir. Kapi H1 K2'yi olay barinda GECIRIR (belgelenmis tasarim); olay
    ureten coin yalnizca `ornekleme.k2_adaylari` ile elenir. Bu test bagimliligi sabitler: cagiran
    `olay_ureten_semboller`i vermezse H1'de olay ureten coin havuza girer."""
    dunya = _h1_dunya()
    p = _karar(dunya, "H1", ZG[TEYIT_G], kontrol("H1", "K2"))
    assert p.rol == "K2"
    sembol = dunya["sembol"]
    aday = k2_adaylari_kur([sembol, "BBBUSDT"], t=ZG[PG], hipotez="H1")
    ureten = olaylar_sembollerde([sembol], t=ZG[PG], hipotez="H1", yapilandirma=Y_H1)
    assert ornekleme.k2_adaylari(aday, ureten, olay_sembolu="AAAUSDT").ogeler == ("BBBUSDT",)
    assert ornekleme.k2_adaylari(aday, [], olay_sembolu="AAAUSDT").ogeler == tuple(sorted([sembol, "BBBUSDT"]))


def test_k1_uygunluk_atlatilamaz_dusuk_hacim_ve_genc_listeleme():
    """On-kayit §6 rev.11 "Kontrolun ne olctugu" + §2 "Uygunluk": K1 de uygunluk kapisindan gecer. Saldiri 1:
    hacim 1.0 (esigin cok alti). Saldiri 2: listeleme yasi 30 gunden az (donem baslangici t'ye 4 gun kala)."""
    n = len(ZG)
    duz = pd.DataFrame({"open_time": ZG, "open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0})
    dusuk = veri(duz, _fund(), DONEM_BAS_G, BG, uygun_bas=DONEM_BAS_G, hacim=1.0)
    with pytest.raises(pozisyon.UygunDegil):
        _karar(dusuk, "H2", ZG[TH], kontrol("H2", "K1"))
    genc = veri(duz, _fund(), BAS_G, BG)
    with pytest.raises((pozisyon.UygunDegil, pencere.OlayOlusmaz)):
        _karar(genc, "H2", ZG[24], kontrol("H2", "K1"))
    assert n > TH


def test_k1_donem_disi_bar_kontrol_adayi_olamaz():
    """On-kayit §6 rev.8 "Donem uyeligi": K1 adayi donem ici olmali. Saldiri: donem bitisinden sonraki barda
    K1 iste (donem bitisi seri sonundan once)."""
    ac, yu, du, ka = _bar_dizileri()
    mum = pd.DataFrame({"open_time": ZG, "open": ac, "high": yu, "low": du, "close": ka})
    kisa_bitis = ZG[100]
    dunya = veri(mum, _fund(), DONEM_BAS_G, kisa_bitis, uygun_bas=DONEM_BAS_G)
    with pytest.raises((pencere.OlayOlusmaz, ValueError)):
        _karar(dunya, "H2", ZG[110], kontrol("H2", "K1"))


# ======================================================================================
# 3. BEKLEME SURESI (data/dizi.py)
# ======================================================================================

T0 = T("2025-03-01 00:00")


def test_bekleme_sonu_t_arti_birincil_ufuk_kere_adim():
    """On-kayit §5 rev.11: "Sure olay barindan (t) olculur ve t + birincil ufuk anina kadar surer"."""
    assert dizi.bekleme_sonu(T0, 18, config.BAR_4H) == T0 + 18 * H4
    assert dizi.bekleme_sonu(T0, 14, config.BAR_1D) == T0 + 14 * D1


def test_beklemede_mi_yari_acik_aralik_tum_barlar_icin_tam_sinir():
    """dizi.py uygulama karari: bekleme `(t0, t0 + h x adim]`. Saldiri: her 4h bar icin t0'dan -3 ile +25
    bar arasi; bekleme tam 1..18. barlardir (olay barinin kendisi ve 19. bar bekleme degildir)."""
    for k in range(-3, 26):
        t = T0 + k * H4
        assert dizi.beklemede_mi(t, T0, 18, config.BAR_4H) is (1 <= k <= 18), k
    for k in range(-2, 18):
        t = T0 + k * D1
        assert dizi.beklemede_mi(t, T0, 14, config.BAR_1D) is (1 <= k <= 14), k


def test_beklemede_mi_tolerans_kenarlari_arti_eksi_bir_dakika_ve_bir_nanosaniye():
    """On-kayit §4 "Zaman toleransi": 1 dakikadan kesin kucuk fark ayni an. Ust uc: son+59 sn / +1 ns hala
    bekleme (ayni an), son+60 sn bekleme degil. Alt uc: t0+59 sn / +1 ns olay anindan 'sonra' degil
    (bekleme degil), t0+60 sn bekleme."""
    son = T0 + 18 * H4
    sn = lambda x: pd.Timedelta(seconds=x)  # noqa: E731
    ns = pd.Timedelta(1, "ns")
    assert dizi.beklemede_mi(son + ns, T0, 18, config.BAR_4H) is True
    assert dizi.beklemede_mi(son + sn(59), T0, 18, config.BAR_4H) is True
    assert dizi.beklemede_mi(son + sn(60), T0, 18, config.BAR_4H) is False
    assert dizi.beklemede_mi(T0 + ns, T0, 18, config.BAR_4H) is False
    assert dizi.beklemede_mi(T0 + sn(59), T0, 18, config.BAR_4H) is False
    assert dizi.beklemede_mi(T0 + sn(60), T0, 18, config.BAR_4H) is True
    assert dizi.beklemede_mi(T0 - sn(30), T0, 18, config.BAR_4H) is False


def test_beklemede_mi_ust_uc_bayragi_false_iken_ust_ucta_serbest():
    """`BEKLEME_UST_UC_DAHIL=False` alternatifi: bekleme `(t0, t0 + h x adim)`; tam ust uc serbest, bir dakika
    oncesi bekleme. Saldiri: bayragin gercekten yonlendirdigini ve toleransin yon degistirmedigini sina."""
    eski = dizi.BEKLEME_UST_UC_DAHIL
    dizi.BEKLEME_UST_UC_DAHIL = False
    try:
        son = T0 + 18 * H4
        assert dizi.beklemede_mi(son, T0, 18, config.BAR_4H) is False
        assert dizi.beklemede_mi(son - pd.Timedelta(seconds=60), T0, 18, config.BAR_4H) is True
        assert dizi.beklemede_mi(son - pd.Timedelta(seconds=59), T0, 18, config.BAR_4H) is False
        assert dizi.beklemede_mi(son - H4, T0, 18, config.BAR_4H) is True
    finally:
        dizi.BEKLEME_UST_UC_DAHIL = eski
    assert dizi.BEKLEME_UST_UC_DAHIL is True


def test_beklemede_mi_ufuk_degeri_on_kayit_disi_verilemez():
    """On-kayit §4 "Ufuk degerlerinin baglanmasi": birincil ufuk izgaraya baglidir. Saldiri: ikincil ufuk
    (6, 42), baska izgaranin ufku (4h icin 14, 1d icin 18), float 18.0, bool, sifir, negatif, bilinmeyen bar."""
    for h, bar, hata in ((6, "4h", ValueError), (42, "4h", ValueError), (14, "4h", ValueError),
                         (18, "1d", ValueError), (7, "1d", ValueError), (18.0, "4h", TypeError),
                         (True, "4h", TypeError), (0, "4h", ValueError), (-18, "4h", ValueError),
                         (18, "2h", ValueError)):
        with pytest.raises(hata):
            dizi.beklemede_mi(T0 + H4, T0, h, bar)
        with pytest.raises(hata):
            dizi.bekleme_sonu(T0, h, bar)
    assert dizi.beklemede_mi(T0 + H4, T0, np.int64(18), "4h") is True


def test_beklemede_mi_tzsiz_zaman_reddedilir():
    """CLAUDE.md §5 (UTC): tz'siz t ya da olay zamani sessizce yanlis karsilastirilmaz, TypeError."""
    with pytest.raises(TypeError):
        dizi.beklemede_mi(T0.tz_localize(None) + H4, T0, 18, "4h")
    with pytest.raises(TypeError):
        dizi.beklemede_mi(T0 + H4, T0.tz_localize(None), 18, "4h")


# --- dizi: ortak yardimcilar -----------------------------------------------------------------------------

Z_H = pd.date_range(T("2025-03-01 00:00"), periods=120, freq="4h")
Z_D = pd.date_range(T("2025-03-01"), periods=80, freq="D")


def _sahte_kapi(hipotez, y=None):
    """Her adayi onaylayan kapi: SORULAN (t, capa) ciftine ait IMZALI onay (bulgu B1 kapandiktan
    sonra `dizi.olay_dizisi` onayi dogruluyor; ham bir nesne artik olay sayilmaz)."""
    def karar(t, capa):
        return pozisyon._test_onayi(hipotez=hipotez, yapilandirma=y if y is not None else yapilandirma(hipotez),
                                    t=t, capa=capa)

    return karar


def _calistir(hipotez, grid, idxler, kosul, karar=None, y=None):
    bar = config.HIPOTEZ_IZGARASI[hipotez]
    return dizi.olay_dizisi(hipotez, y if y is not None else yapilandirma(hipotez), grid[list(idxler)], bar,
                            birincil_ufuk=config.BIRINCIL_UFUK[bar], kosul=kosul,
                            karar=karar if karar is not None else _sahte_kapi(hipotez, y), **DIZI_KIMLIGI)


def _idx(sonuc, grid):
    return [int(grid.get_loc(z)) for z in sonuc.olay_zamanlari]


def test_bekleme_h2_her_olay_sonrasi_tam_on_sekiz_bar_ve_bekleme_icinde_karar_cagrilmaz():
    """On-kayit §5 rev.11 bekleme suresi. Saldiri: kosul her barda dogru; bekleme icindeki bar olay sayilir
    ya da kapiya (karar) gonderilirse olay dizisi bozulur. Beklenen: 0, 19, 38, ... ve karar yalnizca olay
    barlarinda cagrilir (19. bar ilk serbest bar)."""
    cagrilar = []

    def karar(t, capa):
        cagrilar.append(int(Z_H.get_loc(t)))
        return _sahte_kapi("H2")(t, capa)

    sonuc = _calistir("H2", Z_H, range(120), lambda t, capa: True, karar)
    beklenen = [0, 19, 38, 57, 76, 95, 114]
    assert _idx(sonuc, Z_H) == beklenen
    assert cagrilar == beklenen
    assert {r.gerekce for r in sonuc.retler} == {"bekleme_suresi"}


def test_bekleme_ust_uc_bayragi_false_iken_olay_on_sekizinci_barda():
    """Bayrak False iken tam ust uc serbest: olaylar 0, 18, 36, ... (bayragin dizi uzerindeki etkisi)."""
    eski = dizi.BEKLEME_UST_UC_DAHIL
    dizi.BEKLEME_UST_UC_DAHIL = False
    try:
        sonuc = _calistir("H2", Z_H, range(120), lambda t, capa: True)
        assert _idx(sonuc, Z_H) == [0, 18, 36, 54, 72, 90, 108]
    finally:
        dizi.BEKLEME_UST_UC_DAHIL = eski


def test_kapidan_gecmeyen_aday_beklemeyi_baslatmaz():
    """On-kayit §5 rev.11: "Bekleme yalnizca olusmus olaylar icin isler: §4'teki karar noktasindan gecmemis
    bir aday beklemeyi baslatmaz". Saldiri: ilk iki aday kapida reddedilir; sonraki bar (bekleme baslamamis
    olmali) hemen denenmeli ve olay olmali."""
    cagrilar = []

    def karar(t, capa):
        i = int(Z_H.get_loc(t))
        cagrilar.append(i)
        if i in (0, 1):
            raise pozisyon.UygunDegil("sahte ret")
        return _sahte_kapi("H2")(t, capa)

    sonuc = _calistir("H2", Z_H, range(120), lambda t, capa: True, karar)
    assert cagrilar[:3] == [0, 1, 2]
    assert _idx(sonuc, Z_H) == [2, 21, 40, 59, 78, 97, 116]
    assert [r.gerekce for r in sonuc.retler[:2]] == ["uygun_degil", "uygun_degil"]


def test_bekleme_donem_sinirini_asmaz_yeni_donemde_sifirlanir():
    """On-kayit §5 rev.11: "Bekleme donem sinirini asmaz: yeni donemde sifirlanir". Dizi donem basina ayri
    cagrilir; ikinci donemin ilk kosul-dogru bari, onceki donemin son olayindan 1 bar sonra olsa da olay olur."""
    ilk = _calistir("H2", Z_H, range(0, 10), lambda t, capa: True)
    ikinci = _calistir("H2", Z_H, range(10, 20), lambda t, capa: True)
    assert _idx(ilk, Z_H) == [0]
    assert _idx(ikinci, Z_H) == [10]      # tek cagrida olsaydi bekleme 10'u bastirirdi
    tek = _calistir("H2", Z_H, range(0, 20), lambda t, capa: True)
    assert _idx(tek, Z_H) == [0, 19]      # tek cagrida bekleme 1..18'i bastirir, 19 ilk serbest bar


def test_yapilandirmalar_birbirinin_beklemesini_tetiklemez():
    """On-kayit §5 rev.11: "Bekleme yapilandirma basina isler; her yapilandirma kendi olay dizisini uretir".
    Saldiri: iki yapilandirma ayni zamanlar ve ayni kosulla kosulur; her biri kendi 0, 19, 38... dizisini
    uretir (biri digerinin olayi yuzunden bastirilmaz). Kosul yapilandirmaya gore farkli bar kumeleri verir."""
    ya, yb = yapilandirma("H2", k=3), yapilandirma("H2", k=6)
    a = _calistir("H2", Z_H, range(60), lambda t, capa: int(Z_H.get_loc(t)) % 2 == 0, y=ya)
    b = _calistir("H2", Z_H, range(60), lambda t, capa: int(Z_H.get_loc(t)) in (1, 3, 25), y=yb)
    assert _idx(a, Z_H) == [0, 20, 40]
    assert _idx(b, Z_H) == [1, 25]       # 3 beklemede; 25 = 1 + 24 (serbest)


def test_dizi_girdi_dogrulamasi_tzsiz_sirasiz_tekrarli_bos_ve_yanlis_izgara():
    """CLAUDE.md §5 (UTC) + dizi.py girdileri: tz'siz damga TypeError, sirasiz/tekrarli ValueError, bos dizi
    bos sonuc, yanlis izgara/ufuk/yapilandirma/hipotez hata. kosul yaniti bool/None disinda ise TypeError."""
    y = yapilandirma("H2")
    kos = lambda t, capa: True  # noqa: E731
    kar = _sahte_kapi("H2")
    with pytest.raises(TypeError):
        dizi.olay_dizisi("H2", y, Z_H[:5].tz_localize(None), "4h", birincil_ufuk=18, kosul=kos, karar=kar, **DIZI_KIMLIGI)
    with pytest.raises(ValueError):
        dizi.olay_dizisi("H2", y, Z_H[[3, 1, 2]], "4h", birincil_ufuk=18, kosul=kos, karar=kar, **DIZI_KIMLIGI)
    with pytest.raises(ValueError):
        dizi.olay_dizisi("H2", y, Z_H[[1, 1, 2]], "4h", birincil_ufuk=18, kosul=kos, karar=kar, **DIZI_KIMLIGI)
    assert dizi.olay_dizisi("H2", y, Z_H[:0], "4h", birincil_ufuk=18, kosul=kos, karar=kar, **DIZI_KIMLIGI).olaylar == ()
    with pytest.raises(ValueError):
        dizi.olay_dizisi("H2", y, Z_H[:5], "1d", birincil_ufuk=14, kosul=kos, karar=kar, **DIZI_KIMLIGI)
    with pytest.raises(ValueError):
        dizi.olay_dizisi("H2", y, Z_H[:5], "4h", birincil_ufuk=42, kosul=kos, karar=kar, **DIZI_KIMLIGI)
    with pytest.raises(sinyal.YapilandirmaHatasi):
        dizi.olay_dizisi("H2", {"phi": 0.0004, "k": 3}, Z_H[:5], "4h", birincil_ufuk=18, kosul=kos, karar=kar, **DIZI_KIMLIGI)
    with pytest.raises(ValueError):
        dizi.olay_dizisi("h2", y, Z_H[:5], "4h", birincil_ufuk=18, kosul=kos, karar=kar, **DIZI_KIMLIGI)
    for kotu in (1, 0, "True", 1.0):
        with pytest.raises(TypeError):
            dizi.olay_dizisi("H2", y, Z_H[:5], "4h", birincil_ufuk=18, kosul=lambda t, c, k=kotu: k, karar=kar, **DIZI_KIMLIGI)
    assert dizi.olay_dizisi("H2", y, Z_H[:3], "4h", birincil_ufuk=18, kosul=lambda t, c: np.True_,
                            karar=kar, **DIZI_KIMLIGI).olaylar != ()


# --- B1 (bulgu): karar ciktisi dogrulanmiyor -------------------------------------------------------------


def _h1_sahte_kosul():
    pumplar, teyitler = {0}, {0: {1}}

    def kosul(t, capa):
        i = int(Z_H.get_loc(t))
        if capa is None:
            return i in pumplar
        return i in teyitler.get(int(Z_H.get_loc(capa)), set())

    return kosul


def test_k1_pozisyonu_h1_dunyasinda_uretilebilir_dizi_bulgu_testlerinin_on_kosulu():
    """B1 testlerinin on kosulu (olumlu kontrol): H1 dunyasinda gercek bir K1 pozisyonu uretilebiliyor."""
    k1 = _karar(_h1_dunya(), "H1", ZG[TEYIT_G], kontrol("H1", "K1"))
    assert k1.rol == "K1"


# SALDIRI BULGUSU B1 KAPANDI (Rev.12-13 uygulamasi madde 3b): `dizi._olay_dogrula` imzayi, rolu,
# hipotez ve yapilandirma kimligini ve sorulan (t, capa) ciftini denetliyor. xfail kaldirildi;
# beklenti degismedi.
def test_dizi_karar_ciktisi_onayli_pozisyon_degilse_olay_sayilmaz():
    """On-kayit §4 "tek karar noktasi" + §5 rev.11 ("Bekleme yalnizca olusmus olaylar icin isler").
    Bugunku davranis: `_dene`, `karar`in dondurdugu HER nesneyi `Olay(pozisyon=...)` olarak kaydeder ve
    beklemeyi baslatir; `pozisyon.onay_dogrula` cagrilmaz. Beklenen: onayli olmayan nesne TypeError/ValueError
    ile reddedilir. Neden acik: olay kumesine olay_karari'ndan gecmemis bir nesne girebilir (ve kendi
    beklemesini baslatir); dizi ile kapi arasindaki tek baglanti denetimsiz."""
    with pytest.raises((TypeError, ValueError)):
        _calistir("H1", Z_H, range(10), _h1_sahte_kosul(), lambda t, capa: "olay_degil")


# SALDIRI BULGUSU B1 KAPANDI (madde 3b): rol denetleniyor. xfail kaldirildi.
def test_dizi_k1_rolundeki_onayli_pozisyon_olay_sayilmaz():
    """On-kayit §6 rev.11 "Kontrolun ne olctugu": kontrol ve olay roller ayridir; K1'in 'o hipotezin olayi'
    sayilmamasi gerekir. Bugunku davranis: dizi `pozisyon.rol`e bakmaz; `karar` K1 rolunde gercek, imzali bir
    pozisyon dondururse bu OLAY olarak kaydedilir. Beklenen: TypeError/ValueError. Neden acik: bir kontrol
    barinin (K1) olay gibi onaylanmasi, olay kumesini ve K1/K2 havuzlarinin 'ayni yapilandirmanin olaylari'
    tanimini kirletir."""
    k1 = _karar(_h1_dunya(), "H1", ZG[TEYIT_G], kontrol("H1", "K1"))
    with pytest.raises((TypeError, ValueError)):
        _calistir("H1", Z_H, range(10), _h1_sahte_kosul(), lambda t, capa: k1)


# SALDIRI BULGUSU B1 KAPANDI (madde 3b): yapilandirma kimligi denetleniyor. xfail kaldirildi.
def test_dizi_baska_yapilandirmanin_pozisyonunu_olay_saymaz():
    """On-kayit §5 rev.11: "Bekleme yapilandirma basina isler; her yapilandirma kendi olay dizisini uretir".
    Bugunku davranis: delta=0.08 dizisi, `karar`dan delta=0.12 yapilandirmasinin onayli olay pozisyonunu
    alirsa bunu kendi olayi sayar. Beklenen: TypeError/ValueError. Neden acik: iki yapilandirmanin olaylari
    karisabilir; pozisyonun `yapilandirma` etiketi imzaliyken dizi onu hic karsilastirmaz."""
    dunya = _h1_dunya()
    baska = _karar(dunya, "H1", ZG[TEYIT_G], olay("H1", capa=ZG[PG], delta=0.12))
    assert baska.yapilandirma == "H1:theta=0.2,delta=0.12"
    with pytest.raises((TypeError, ValueError)):
        _calistir("H1", Z_H, range(10), _h1_sahte_kosul(), lambda t, capa: baska,
                  y=yapilandirma("H1", delta=0.08))


# ======================================================================================
# 4. H1 TEK IZLEME (dizi.olay_dizisi)
# ======================================================================================


def _h1_kosul(pumplar, teyitler):
    """Sahte H1 kosulu; (t, capa) sorgularini kaydeder. capa None = pump, capa=p = p capali teyit."""
    cagrilar = []

    def kosul(t, capa):
        i = int(Z_H.get_loc(t))
        c = None if capa is None else int(Z_H.get_loc(capa))
        cagrilar.append((i, c))
        if c is None:
            return i in pumplar
        return i in teyitler.get(c, set())

    return kosul, cagrilar


def _capalar(sonuc):
    return [None if o.capa is None else int(Z_H.get_loc(o.capa)) for o in sonuc.olaylar]


def test_h1_izleme_surerken_gelen_ikinci_pump_yok_sayilir_tek_olay_ilk_pumptan():
    """On-kayit §5 H1 madde 4: "Izleme surerken pump kosulunu saglayan yeni bir bar gelirse yok sayilir:
    tepe ve 12 barlik sayac ilk pump barindan olculmeye devam eder ... bir teyit bari en cok bir olay
    sayar". Saldiri: pump 0 ve 2; her ikisine de capali teyit 5'te dogru. Tek olay, capa=0; ikinci pump'a
    capali sorgu hic yapilmaz (izlemeyi yeniden baslatmaz)."""
    kosul, cagrilar = _h1_kosul({0, 2}, {0: {5}, 2: {5}})
    sonuc = _calistir("H1", Z_H, range(40), kosul)
    assert _idx(sonuc, Z_H) == [5]
    assert _capalar(sonuc) == [0]
    assert (2, None) not in cagrilar
    assert not any(c == 2 for _, c in cagrilar)


def test_h1_12_barlik_sayac_ikinci_pumptan_olculmez():
    """On-kayit §5 H1 madde 4: sayac ilk pump barindan. Saldiri: pump 0 ve 8; teyit yalnizca 14'te (ilk
    pump'tan 14 bar, ikinciden 6 bar sonra) dogru. Sayac 8'den yeniden olculseydi olay olurdu; olmamali ve
    (14, 8) sorgusu hic yapilmamali."""
    kosul, cagrilar = _h1_kosul({0, 8}, {8: {14}})
    sonuc = _calistir("H1", Z_H, range(40), kosul)
    assert sonuc.olaylar == ()
    assert (14, 8) not in cagrilar


def test_h1_teyit_tam_12_barda_kabul_13_barda_red():
    """On-kayit §5 H1 madde 3: "pump barindan sonraki 12 bar icinde". Saldiri: 12. bar teyidi olay olur
    (capa 0); yalnizca 13. barda dogru olan teyit olay olmaz (izleme 12'de bitti)."""
    kosul, _ = _h1_kosul({0}, {0: {12}})
    assert _idx(_calistir("H1", Z_H, range(40), kosul), Z_H) == [12]
    kosul, _ = _h1_kosul({0}, {0: {13}})
    assert _calistir("H1", Z_H, range(40), kosul).olaylar == ()


def test_h1_izleme_bitince_yeni_pump_yeni_izleme_baslatir():
    """On-kayit §5 H1 madde 4: "yeni bir izleme ancak bundan sonra baslayabilir". Saldiri: izleme hic bitmez
    ise 14'teki pump yok sayilir ve 16'daki teyit olay olmaz. Beklenen: izleme 12'de biter, 14'te yeni izleme,
    olay 16'da, capa 14."""
    kosul, _ = _h1_kosul({0, 14}, {14: {16}})
    sonuc = _calistir("H1", Z_H, range(40), kosul)
    assert _idx(sonuc, Z_H) == [16] and _capalar(sonuc) == [14]


def test_h1_teyit_bari_ayni_zamanda_pump_ise_iki_olay_saymaz():
    """On-kayit §5 H1 madde 4: "Boylece bir teyit bari en cok bir olay sayar". Saldiri: 3. bar hem 0 capali
    teyit hem pump kosulunu saglar; tek olay (capa 0), 3. bar yeni izleme baslatmaz, sonraki barlar bekleme."""
    kosul, cagrilar = _h1_kosul({0, 3, 4}, {0: {3}, 3: {5}, 4: {6}})
    sonuc = _calistir("H1", Z_H, range(40), kosul)
    assert _idx(sonuc, Z_H) == [3] and _capalar(sonuc) == [0]
    assert (3, None) not in cagrilar


def test_h1_kapidan_gecmeyen_teyit_izlemeyi_bitirir_ama_beklemeyi_baslatmaz():
    """On-kayit §5 H1 madde 4: "Izleme, teyit bariyla ... biter"; §5 rev.11: reddedilen aday beklemeyi
    baslatmaz. Saldiri: 3'teki teyit kapida reddedilir; izleme biter (0 capali 5 teyidi sorulmamali), 4'teki
    pump hemen yeni izleme baslatir (bekleme yok) ve 6'daki teyit olay olur (capa 4)."""
    kosul, cagrilar = _h1_kosul({0, 4}, {0: {3, 5}, 4: {6}})

    def karar(t, capa):
        if int(Z_H.get_loc(t)) == 3:
            raise pozisyon.SinyalKosuluSaglanmadi("sahte")
        return _sahte_kapi("H1")(t, capa)

    sonuc = _calistir("H1", Z_H, range(40), kosul, karar)
    assert _idx(sonuc, Z_H) == [6] and _capalar(sonuc) == [4]
    assert (5, 0) not in cagrilar


def test_h1_hesaplanamayan_teyit_izlemeyi_bitirmez_sonraki_dogru_teyit_olay_olur():
    """On-kayit §2 "Tamlik sarti" + §5 H1 madde 4: hesaplanamayan bar teyit sayilmaz ama izleme surer
    (12 bar dolmadan). Saldiri: 2'deki teyit sorgusu None doner; izleme kesilirse 4'teki teyit kacar."""
    cagrilar = []

    def kosul(t, capa):
        i = int(Z_H.get_loc(t))
        c = None if capa is None else int(Z_H.get_loc(capa))
        cagrilar.append((i, c))
        if c is None:
            return i == 0
        if i == 2:
            return None
        return i == 4

    sonuc = _calistir("H1", Z_H, range(30), kosul)
    assert _idx(sonuc, Z_H) == [4]
    assert any(r.gerekce == "sinyal_penceresi_tam_degil" for r in sonuc.retler)


def test_h1_bekleme_icinde_pump_yok_sayilir_ilk_serbest_barda_yeni_izleme():
    """On-kayit §5 H1 madde 4 + §5 rev.11 bekleme: olay 5'te (bekleme 6..23). 23'teki pump (bekleme icinde)
    izleme baslatmaz, 25'teki ona capali teyit sorulmaz; 24'teki pump (ilk serbest bar) izleme baslatir ve 26
    teyidi olay olur. Saldiri: bekleme ust ucu bir bar kisa/uzun olursa olaylar kayar."""
    kosul, cagrilar = _h1_kosul({0, 23, 24}, {0: {5}, 23: {25}, 24: {26}})
    sonuc = _calistir("H1", Z_H, range(40), kosul)
    assert _idx(sonuc, Z_H) == [5, 26] and _capalar(sonuc) == [0, 24]
    assert not any(c == 23 for _, c in cagrilar)
    assert (23, None) not in cagrilar


# SALDIRI BULGUSU B3 KAPANDI (Rev.12-13 uygulamasi madde 2a): izleme penceresi artik takvimle
# olculur (`(pump, pump + 12 x adim]`), islenen barlarin varligiyla degil. xfail isareti kaldirildi;
# beklenti degismedi.
def test_h1_12_bar_siniri_zamanlarda_eksik_bar_oldugunda_da_gecerli():
    """On-kayit §5 H1 madde 3-4: teyit pump'tan sonraki 12 bar icinde; 12 bar dolunca izleme biter. Bugunku
    davranis: izlemeyi bitiren `once(t, pump + 12 adim)` kontrolu yalnizca islenen bar icin calisir; zamanlar
    listesinde 12. bar yoksa 13. bar hala izleme icinde sayilir ve `kosul(13, pump)` dogruysa olay kaydedilir.
    Beklenen: teyit zamanini dizi kendisi sinirlar, olay olusmaz. Onem: DUSUK (gercek hatta eksik 12. bar
    tepe penceresini zaten eksik yapar ve `sinyal_kosulu` None doner); ama dizi tek basina sinirin sahibi
    degil."""
    kosul, _ = _h1_kosul({0}, {0: {13}})
    sonuc = _calistir("H1", Z_H, list(range(12)) + [13, 14], kosul)
    assert sonuc.olaylar == ()


def test_h1_entegrasyon_gercek_kapi_ve_kosulla_tek_olay_capa_ilk_pump_ve_yapilandirma_ayrimi():
    """Entegrasyon (gercek `sinyal_kosulu` + `olay_karari`): H1 dunyasinda idx 30 pump, idx 33 teyit. delta 0.08
    ve 0.12 icin tek olay (33, capa 30), bekleme sonraki barlari bastirir; delta 0.16 teyit gormez. Saldiri:
    pump'tan sonraki bar(lar) da pump kosulunu saglasa bile (idx 31, 32) ikinci izleme/olay olmamali."""
    dunya = _h1_dunya()
    zamanlar = ZG[24:41]

    def kos(y):
        return lambda t, capa: pozisyon.sinyal_kosulu(t, hipotez="H1", yapilandirma=y, capa=capa, kume="KESIF",
                                                      **dunya)

    def kar(y):
        return lambda t, capa: _karar(dunya, "H1", t, {"yapilandirma": y, "rol": "olay", "capa": capa})

    sonuclar = {}
    for delta in (0.08, 0.12, 0.16):
        y = yapilandirma("H1", delta=delta)
        sonuclar[delta] = dizi.olay_dizisi("H1", y, zamanlar, config.BAR_4H, birincil_ufuk=18, kosul=kos(y),
                                           karar=kar(y), kume="KESIF",
                                           sembol=dunya["sembol"], donem_no=dunya["donem_no"])
    for delta in (0.08, 0.12):
        s = sonuclar[delta]
        assert s.olay_zamanlari == (ZG[TEYIT_G],), delta
        assert s.olaylar[0].capa == ZG[PG]
        assert s.olaylar[0].pozisyon.rol == "olay"
        pozisyon.onay_dogrula(s.olaylar[0].pozisyon)
    assert sonuclar[0.16].olaylar == ()


# ======================================================================================
# 5. H3 ILK GUN (dizi.olay_dizisi)
# ======================================================================================


def _h3_kosul(dogru, none=()):
    def kosul(t, capa):
        assert capa is None
        i = int(Z_D.get_loc(t))
        if i in none:
            return None
        return i in dogru

    return kosul


def test_h3_kesintisiz_dizinin_yalnizca_ilk_gunu_olay_bekleme_dolsa_bile_ikinci_gun_olay_degil():
    """On-kayit §5 H3 madde 3: "Kesintisiz suren bir dizinin icinde, bekleme suresi dolsa bile yeni olay
    sayilmaz". Saldiri: 40 gun boyunca kosul dogru; bekleme 14. gunde biter (15. gun serbest) ama dizi suruyor:
    yalnizca gun 0 olay. 15. gunun ret gerekcesi `dizi_ilk_gun_degil` olmali (bekleme degil)."""
    sonuc = _calistir("H3", Z_D, range(40), _h3_kosul(set(range(40))))
    assert _idx(sonuc, Z_D) == [0]
    gerekce15 = [r.gerekce for r in sonuc.retler if r.zaman == Z_D[15]]
    gerekce1 = [r.gerekce for r in sonuc.retler if r.zaman == Z_D[1]]
    assert gerekce15 == ["dizi_ilk_gun_degil"] and gerekce1 == ["dizi_ilk_gun_degil"]


def test_h3_saglanmayan_gun_diziyi_keser_yeni_dizinin_ilk_gunu_bekleme_dolmussa_olay():
    """On-kayit §5 H3 madde 3: dizi kosullardan biri saglanmadigi gunde kesilir; yeni dizinin ilk gunu yeni
    'ilk gun'dur ve bekleme ayrica uygulanir. Gun 0-2 dogru, 3-15 yanlis, 16-18 dogru: olaylar 0 ve 16."""
    dogru = {0, 1, 2, 16, 17, 18}
    assert _idx(_calistir("H3", Z_D, range(30), _h3_kosul(dogru)), Z_D) == [0, 16]


def test_h3_hesaplanamayan_gun_diziyi_keser():
    """On-kayit §5 H3 madde 3 + §2 "Tamlik sarti": hesaplanamayan gun diziyi KESER. Saldiri: 0-14 dogru,
    15 hesaplanamaz (None), 16-20 dogru. Kesilmeseydi 16 ilk gun olmaz ve ikinci olay kacardi. Beklenen:
    olaylar 0 ve 16 (16: bekleme 14'te bitti)."""
    dogru = set(range(0, 15)) | set(range(16, 21))
    sonuc = _calistir("H3", Z_D, range(30), _h3_kosul(dogru, none={15}))
    assert _idx(sonuc, Z_D) == [0, 16]
    assert any(r.zaman == Z_D[15] and r.gerekce == "sinyal_penceresi_tam_degil" for r in sonuc.retler)


def test_h3_yeni_dizinin_ilk_gunu_bekleme_icindeyse_olay_degil_ve_dizinin_geri_kalani_da_olay_degil():
    """On-kayit §5 H3 madde 3: "bekleme suresi ayrica uygulanir". Saldiri: 0-1 dogru, 2-3 yanlis, 4'ten 30'a
    kadar dogru. 4. gun yeni dizinin ilk gunu ama bekleme icinde (olay yok); dizi kesintisiz surdugu icin
    bekleme bitince de olay yok. Sadece gun 0 olay."""
    dogru = {0, 1} | set(range(4, 31))
    sonuc = _calistir("H3", Z_D, range(40), _h3_kosul(dogru))
    assert _idx(sonuc, Z_D) == [0]
    assert [r.gerekce for r in sonuc.retler if r.zaman == Z_D[4]] == ["bekleme_suresi"]


def test_h3_bekleme_kenari_14_gun_bekleme_15_gun_serbest():
    """dizi.py yari acik bekleme `(t0, t0+14 gun]`: ikinci ilk-gun 14. gunde bekleme icinde (olay yok), 15.
    gunde serbest (olay). Saldiri: tam kenarda bir gunluk kayma."""
    assert _idx(_calistir("H3", Z_D, range(30), _h3_kosul({0, 14})), Z_D) == [0]
    assert _idx(_calistir("H3", Z_D, range(30), _h3_kosul({0, 15})), Z_D) == [0, 15]


# SALDIRI BULGUSU B2 KAPANDI (Rev.12-13 uygulamasi madde 2b): dizi artik TAKVIMLE kesilir; iki
# islenen gun arasinda bir adimdan fazla bosluk varsa dizi kesilir. xfail isareti kaldirildi;
# beklenti degismedi.
def test_h3_zamanlar_listesinde_eksik_gun_diziyi_keser():
    """On-kayit §5 H3 madde 3: dizi, kosullardan biri saglanmadigi "ya da §2 'Tamlik sarti' geregi
    hesaplanamadigi gunde kesilir". Bugunku davranis: `dizi_suruyor` yalniz ISLENEN barlarda sifirlanir;
    `zamanlar` 0,1 ve 20,21,22 gunlerini icerir (2..19 eksik gun, yani bar yok = hesaplanamaz), kosul her
    islenen gunde dogru. Dizi kesilmedigi icin 20. gun 'ilk gun' sayilmaz. Beklenen: olaylar 0 ve 20 (bekleme
    14'te bitti, 20 yeni dizinin ilk gunu). Neden acik: bar-eksik (silinmis) gunler listeden dusuyorsa,
    kesintisiz dizi denetimi bos gecer; kapi/sinyal tarafi bu gunleri hic gostermez."""
    sonuc = _calistir("H3", Z_D, [0, 1, 20, 21, 22], _h3_kosul(set(range(30))))
    assert _idx(sonuc, Z_D) == [0, 20]


# ======================================================================================
# 6. ORNEKLEME (data/ornekleme.py)
# ======================================================================================

Y_H1 = yapilandirma("H1")
OLAY_T = T("2025-03-01 04:00")
ADAYLAR = [T("2025-01-01") + i * H4 for i in range(40)]

# Rev.13 (madde (d)): adaylik ornekelemeden ONCE belirlenir; `ornekleme` ham damga/sembol kabul
# etmez. Asagidaki saldirilar adaylari kapidan gecirerek kurar (`ornekleme_yardimcisi`) ve tohum
# `ornekle`ye verilmez (D-C5): demetten turer, bu yuzden "farkli tohum" yerine farkli DEMET.
_SEMBOLLER = [f"S{i:03d}USDT" for i in range(40)]


def _k1(barlar, sembol="AAAUSDT"):
    return k1_adaylari_kur(barlar, hipotez="H1", yapilandirma=Y_H1, sembol=sembol)


def _ornekle(adaylar, sembol=None, olay_zamani=None, **ek):
    """Madde 3b: `ornekle` artik olayin KENDISINI alir ve olayi adaylarla capraz dogrular.

    Bu sarmalayici yardimci uzerinden adaylarin kimligine uyan bir olay kurar: K1'de adaylarin
    sembolu ve donemi, K2'de adaylarin bar zamani. Demeti degistirmek icin K1'de aday kumesinin
    sembolu, K2'de olayin sembolu degistirilir."""
    return yardimci_ornekle(adaylar, sembol=sembol, olay_zamani=olay_zamani, **ek)


def test_ornekle_iadesiz_ayni_kontrol_iki_kez_cekilmez_ve_aday_alt_kumesi():
    """On-kayit §6 rev.11: "Iki havuzda da ornekleme iadesizdir". Saldiri: 300 farkli DEMET (olay zamani);
    her cekilis 10 benzersiz, aday kumesinin alt kumesi, aday sirasinda (artan) olmali; aday_sayisi dogru."""
    adaylar = _k1(ADAYLAR)
    for i in range(300):
        h = _ornekle(adaylar, olay_zamani=OLAY_T + i * H4)
        assert len(h) == 10 and len(set(h.secilenler)) == 10
        assert set(h.secilenler) <= set(ADAYLAR)
        assert list(h.secilenler) == sorted(h.secilenler)
        assert h.aday_sayisi == 40 and not h.eksik


def test_ornekle_tekrarli_aday_reddedilir_dedup_ile_havuz_sisirilemez():
    """On-kayit §6: iadesizlik. Saldiri: ayni adayi iki kez vermek (havuz sisirmek) ValueError. Aday kurma
    adimi de tekrari reddeder (ayni bar iki kez aday olamaz)."""
    with pytest.raises(ValueError):
        _k1(ADAYLAR[:5] + ADAYLAR[:3])
    with pytest.raises(ValueError):
        k2_adaylari_kur(["AUSDT", "AUSDT", "BUSDT"], t=OLAY_T, hipotez="H1", yapilandirma=Y_H1)


def test_ornekle_ham_aday_listesi_kabul_edilmez():
    """On-kayit §6 rev.13: "kapidan gecmemis bir adayi kabul etmesin". Saldiri: ham bar damgasi listesi,
    ham sembol listesi, elle kurulmus `Adaylar`, olay rolundeki onay."""
    # Ham girdi `ornekleme.ornekle`ye DOGRUDAN verilir (yardimci sarmalayici adaylarin kimligini
    # okudugu icin ham listede kendisi patlar); olay gecerli bir `dizi.Olay`dir.
    olay = tek_olay(OLAY_T, hipotez="H1", yapilandirma=Y_H1, sembol="AAAUSDT")
    for ham in (ADAYLAR, _SEMBOLLER, tuple(ADAYLAR), []):
        with pytest.raises(TypeError):
            ornekleme.ornekle(ham, olay=olay)
    elle = ornekleme.Adaylar("K1", "H1", "H1:theta=0.2,delta=0.08", "KESIF", tuple(ADAYLAR))
    with pytest.raises(ValueError):
        ornekleme.ornekle(elle, olay=olay)
    with pytest.raises(ValueError, match="rol"):
        ornekleme.adaylari_kur([pozisyon._test_onayi(hipotez="H1", yapilandirma=Y_H1, t=ADAYLAR[0],
                                                     capa=ADAYLAR[0])], rol="K1")
    with pytest.raises((TypeError, ValueError)):
        ornekleme.adaylari_kur([("pozisyon", ADAYLAR[0])], rol="K1")


def test_ornekle_aday_sirasindan_ve_global_rastgelelikten_bagimsiz():
    """On-kayit §6 rev.11: "sonuc kosu sirasindan bagimsizdir". Saldiri: adaylari karistir/ters cevir ve
    numpy global tohumunu degistir; sonuc ayni olmali. Farkli DEMET en az bir kez farkli secim vermeli."""
    taban = _ornekle(_k1(ADAYLAR)).secilenler
    rng = np.random.default_rng(0)
    for _ in range(20):
        karisik = [ADAYLAR[i] for i in rng.permutation(len(ADAYLAR))]
        np.random.seed(int(rng.integers(0, 10_000)))
        assert _ornekle(_k1(karisik)).secilenler == taban
    assert _ornekle(_k1(ADAYLAR[::-1])).secilenler == taban
    assert _ornekle(_k1(iter(ADAYLAR))).secilenler == taban
    assert any(_ornekle(_k1(ADAYLAR, sembol=s), sembol=s).secilenler != taban
               for s in ("BBBUSDT", "CCCUSDT", "DDDUSDT", "EEEUSDT"))


def test_ornekle_on_adaydan_az_adayin_tamami_alinir_ve_sayi_kaybolmaz():
    """On-kayit §6 rev.11: "Aday sayisi 10'dan azsa adaylarin tamami alinir ve sayi sonuc dosyasina yazilir".
    Saldiri: 0, 1, 9, 10, 11 aday; aday_sayisi her zaman gercek sayi, `eksik` yalnizca <10."""
    for n, eksik, secilen in ((0, True, 0), (1, True, 1), (9, True, 9), (10, False, 10), (11, False, 10)):
        h = _ornekle(_k1(ADAYLAR[:n]))
        assert (h.aday_sayisi, h.eksik, len(h)) == (n, eksik, secilen), n
    assert _ornekle(_k1(ADAYLAR[:9])).secilenler == tuple(ADAYLAR[:9])
    assert set(_ornekle(_k1(ADAYLAR[:11])).secilenler) < set(ADAYLAR[:11])


def test_ornekle_on_kayit_disi_sayi_reddedilir():
    """Denetci bulgusu D-C5: `sayi` on-kayit degeri (10) olmali; serbest deger acik hata."""
    adaylar = _k1(ADAYLAR)
    for sayi in (1, 5, 9, 11, 40, 0, True):
        with pytest.raises(ValueError, match="on-kayit"):
            _ornekle(adaylar, sayi=sayi)
    assert len(_ornekle(adaylar)) == config.KONTROL_SAYISI


def test_olay_analize_girer_yalniz_iki_havuz_da_bossa_dusulur():
    """On-kayit §6 rev.11: "Bir olayin her iki havuzu da bossa o olay analize girmez; en az bir kontrolu olan
    olay kalir"."""
    bos = _ornekle(_k1([]))
    bir = _ornekle(_k1(ADAYLAR[:1]))
    assert ornekleme.olay_analize_girer(bos, bos) is False
    assert ornekleme.olay_analize_girer(bir, bos) is True
    assert ornekleme.olay_analize_girer(bos, bir) is True


def test_alt_tohum_deterministik_ve_ayni_yapilandirmanin_farkli_yazimlarinda_ayni():
    """On-kayit §6/§7: alt tohum (hipotez, yapilandirma, kume, sembol, olay zamani) demetinden turer ve
    kosu sirasindan bagimsizdir. Saldiri: ayni demet dict / demet / numpy degerleriyle yazilsa da ayni."""
    a = ornekleme.alt_tohum("H1", Y_H1, "KESIF", "AAAUSDT", OLAY_T)
    assert a == ornekleme.alt_tohum("H1", Y_H1, "KESIF", "AAAUSDT", OLAY_T)
    assert a == ornekleme.alt_tohum("H1", (0.2, 0.08), "KESIF", "AAAUSDT", OLAY_T)
    assert a == ornekleme.alt_tohum("H1", {"delta": np.float64(0.08), "theta": np.float64(0.2)}, "KESIF",
                                    "AAAUSDT", OLAY_T)
    assert isinstance(a, int) and a >= 0


def test_alt_tohum_demetin_her_ogesine_duyarli():
    """On-kayit §6 rev.11: alt tohum demetin HER ogesine baglidir. Saldiri: hipotez, yapilandirma (her iki
    parametre), kume, sembol, olay zamani (4 saat, 1 saniye, 1 nanosaniye) teker teker degistirilir; hicbiri
    ayni tohumu vermemeli (tohum cakismasi iki olayin ayni kontrolu secmesi demektir)."""
    a = ornekleme.alt_tohum("H1", Y_H1, "KESIF", "AAAUSDT", OLAY_T)
    farkli = [
        ornekleme.alt_tohum("H2", yapilandirma("H2"), "KESIF", "AAAUSDT", OLAY_T),
        ornekleme.alt_tohum("H1", yapilandirma("H1", delta=0.12), "KESIF", "AAAUSDT", OLAY_T),
        ornekleme.alt_tohum("H1", yapilandirma("H1", theta=0.3), "KESIF", "AAAUSDT", OLAY_T),
        ornekleme.alt_tohum("H1", Y_H1, "C2", "AAAUSDT", OLAY_T),
        ornekleme.alt_tohum("H1", Y_H1, "KESIF", "BBBUSDT", OLAY_T),
        ornekleme.alt_tohum("H1", Y_H1, "KESIF", "AAAUSDT", OLAY_T + H4),
        ornekleme.alt_tohum("H1", Y_H1, "KESIF", "AAAUSDT", OLAY_T + pd.Timedelta(seconds=1)),
        ornekleme.alt_tohum("H1", Y_H1, "KESIF", "AAAUSDT", OLAY_T + pd.Timedelta(1, "ns")),
    ]
    assert len(set(farkli + [a])) == len(farkli) + 1


def test_alt_tohum_girdi_dogrulamasi_tzsiz_bilinmeyen_kume_bos_sembol_izgara_disi():
    """On-kayit §6/§7 + CLAUDE.md §5: tz'siz olay zamani TypeError, bilinmeyen kume ValueError, bos/bytes
    sembol TypeError, izgara disi yapilandirma YapilandirmaHatasi."""
    with pytest.raises(TypeError):
        ornekleme.alt_tohum("H1", Y_H1, "KESIF", "AAAUSDT", OLAY_T.tz_localize(None))
    with pytest.raises(ValueError):
        ornekleme.alt_tohum("H1", Y_H1, "C3", "AAAUSDT", OLAY_T)
    for sembol in ("", b"AAAUSDT", None):
        with pytest.raises(TypeError):
            ornekleme.alt_tohum("H1", Y_H1, "KESIF", sembol, OLAY_T)
    with pytest.raises(sinyal.YapilandirmaHatasi):
        ornekleme.alt_tohum("H1", {"theta": 0.21, "delta": 0.08}, "KESIF", "AAAUSDT", OLAY_T)


def test_kosu_sirasi_bagimsizligi_semboller_alfabetik_islenir_sonuc_degismez():
    """On-kayit §6 rev.11: "semboller alfabetik sirada islenir, boylece sonuc kosu sirasindan bagimsizdir".
    Saldiri: sembol listesi karistirilir; `sembol_sirasi` ayni diziyi verir ve her sembol icin havuz (alt
    tohumdan) ayni cikar. Tekrarli sembol ValueError."""
    semboller = ["ZZZUSDT", "AAAUSDT", "MMMUSDT", "1000PEPEUSDT", "BTCUSDT"]
    beklenen = tuple(sorted(semboller))
    rng = np.random.default_rng(2)
    sonuc = None
    for _ in range(10):
        karisik = [semboller[i] for i in rng.permutation(len(semboller))]
        assert ornekleme.sembol_sirasi(karisik) == beklenen
        havuzlar = {s: _ornekle(_k1(ADAYLAR, sembol=s), sembol=s).secilenler
                    for s in ornekleme.sembol_sirasi(karisik)}
        sonuc = havuzlar if sonuc is None else sonuc
        assert havuzlar == sonuc
    with pytest.raises(ValueError):
        ornekleme.sembol_sirasi(["AAAUSDT", "AAAUSDT"])


# SALDIRI BULGUSU B4 KAPANDI (Rev.12-13 uygulamasi madde 2f): `alt_tohum` olay zamanini UTC'ye
# NORMALLESTIRIYOR (`tz_convert("UTC")`), bu yuzden ayni an hangi saat diliminde tasinirsa tasinsin
# ayni tohumu verir. xfail isareti kaldirildi; beklenti degismedi.
def test_alt_tohum_ayni_an_utc_disi_saat_diliminde_ayni_olmali_ya_da_reddedilmeli():
    """CLAUDE.md §5: "Tum zaman damgalari UTC"; on-kayit §7 tohum "olay zamani" demeti. Bugunku davranis:
    `pencere.utc_zamani` yalniz tz'siz damgayi reddeder; UTC disi saat dilimi kabul edilir ve tohum metni
    `t.isoformat()` ile kuruldugu icin ('...+03:00' ile '...+00:00') AYNI AN FARKLI TOHUM verir. Beklenen:
    ya ayni tohum (UTC'ye normallestirme) ya da UTC disi damgayi acik hata ile reddetme. Neden acik: ayni
    olayin kontrol havuzu, zaman damgasinin hangi saat diliminde tasindigina gore degisir; tekrarlanabilirlik
    zamanin gosterimine baglanir."""
    utc = T("2025-03-01 04:00")
    uc = utc.tz_convert(dt.timezone(dt.timedelta(hours=3)))
    assert utc == uc
    a = ornekleme.alt_tohum("H1", Y_H1, "KESIF", "AAAUSDT", utc)
    try:
        b = ornekleme.alt_tohum("H1", Y_H1, "KESIF", "AAAUSDT", uc)
    except (TypeError, ValueError):
        return
    assert a == b


def test_k1_ufuk_mesafesi_kenari_tam_ufuk_yakin_degil_bir_bar_eksik_yakin_4h_ve_1d():
    """On-kayit §6 K1: "birincil ufuk mesafesinden yakin olmayan" bar; tam ufuk mesafesi yakin sayilmaz.
    Saldiri: olayin her iki yaninda -30..+30 bar; |k| >= 18 uzak, |k| < 18 yakin (4h). 1d icin ufuk 14."""
    for k in range(-30, 31):
        assert ornekleme.k1_uzak_mi(OLAY_T + k * H4, [OLAY_T], 18, "4h") is (abs(k) >= 18), k
    for k in range(-20, 21):
        assert ornekleme.k1_uzak_mi(OLAY_T.floor("D") + k * D1, [OLAY_T.floor("D")], 14, "1d") is (abs(k) >= 14), k


def test_k1_mesafe_tolerans_kenarlari_arti_eksi_bir_dakika_bir_nanosaniye():
    """On-kayit §4 "Zaman toleransi": ufuk mesafesinden 1 dakikadan az eksik kalan fark ayni mesafe sayilir
    (uzak); tam 1 dakika eksik 'daha yakin' (yakin). Saldiri: -59 sn, -1 ns, -60 sn, +59 sn, ve iki yon."""
    mesafe = 18 * H4
    sn = lambda x: pd.Timedelta(seconds=x)  # noqa: E731
    ns = pd.Timedelta(1, "ns")
    for yon in (1, -1):
        assert ornekleme.k1_uzak_mi(OLAY_T + yon * (mesafe - ns), [OLAY_T], 18, "4h") is True
        assert ornekleme.k1_uzak_mi(OLAY_T + yon * (mesafe - sn(59)), [OLAY_T], 18, "4h") is True
        assert ornekleme.k1_uzak_mi(OLAY_T + yon * (mesafe - sn(60)), [OLAY_T], 18, "4h") is False
        assert ornekleme.k1_uzak_mi(OLAY_T + yon * (mesafe + sn(59)), [OLAY_T], 18, "4h") is True
    assert ornekleme.k1_uzak_mi(OLAY_T, [OLAY_T], 18, "4h") is False


def test_k1_birden_cok_olay_hicbirine_yakin_olmamali_bos_olay_listesi_hepsini_birakir():
    """On-kayit §6 K1: "o hipotezin herhangi bir olayina" yakin olmayan. Saldiri: iki olay; iki olay arasinda
    ikisinden de uzak ama birine yakin bar elenir. Olay yoksa tum adaylar kalir; sira korunur."""
    e1, e2 = OLAY_T, OLAY_T + 30 * H4
    aday = [e1 + k * H4 for k in range(-5, 40)]
    # REV.14 (D-B2): olaylar DOGRULANMIS nesnelerdir; iddialar degismedi.
    olaylar = olaylar_kur([e1], hipotez="H1", yapilandirma=Y_H1) +         olaylar_kur([e2], hipotez="H1", yapilandirma=Y_H1)
    kalan = ornekleme.k1_adaylari(_k1(aday), olaylar, 18, "4h")
    beklenen = tuple(t for t in aday if abs((t - e1) / H4) >= 18 and abs((t - e2) / H4) >= 18)
    assert kalan.ogeler == beklenen
    assert tuple(ornekleme.k1_adaylari(_k1(aday), [], 18, "4h").ogeler) == tuple(aday)
    assert all(ornekleme.k1_uzak_mi(t, [e1, e2], 18, "4h") for t in kalan.ogeler)
    with pytest.raises(ValueError):
        _k1(aday + aday[:2])
    # Ham aday listesi de kabul edilmez (rev.13): adaylik kapidan gecer.
    with pytest.raises(TypeError):
        ornekleme.k1_adaylari(aday, olaylar[:1], 18, "4h")
    # Ham OLAY listesi de kabul edilmez (rev.14).
    with pytest.raises(TypeError):
        ornekleme.k1_adaylari(_k1(aday), [e1], 18, "4h")


def test_k1_ufuk_degeri_on_kayit_disi_ve_tzsiz_zaman_reddedilir():
    """On-kayit §4 "Ufuk degerlerinin baglanmasi" + CLAUDE.md §5: K1 mesafesi birincil ufuktur (ikincil ufuk
    degil). Saldiri: 6, 42, 14 (4h icin), float, tz'siz bar/olay."""
    for h, bar in ((6, "4h"), (42, "4h"), (14, "4h"), (18, "1d")):
        with pytest.raises(ValueError):
            ornekleme.k1_uzak_mi(OLAY_T + 100 * H4, [OLAY_T], h, bar)
    with pytest.raises(TypeError):
        ornekleme.k1_uzak_mi(OLAY_T + 100 * H4, [OLAY_T], 18.0, "4h")
    with pytest.raises(TypeError):
        ornekleme.k1_uzak_mi((OLAY_T + 100 * H4).tz_localize(None), [OLAY_T], 18, "4h")
    with pytest.raises(TypeError):
        ornekleme.k1_uzak_mi(OLAY_T + 100 * H4, [OLAY_T.tz_localize(None)], 18, "4h")


def test_k2_havuzu_olay_ureten_coin_ve_olayin_kendi_coini_dusulur_sira_bagimsiz():
    """On-kayit §6 K2: "Ayni t barinda uygun olan ve o anda olay uretmemis DIGER coinlerden". Saldiri: olayin
    kendi sembolu aday listesinde, olay ureten semboller aday listesinde; ikisi de havuza girmemeli. Aday
    sirasi karistirilsa sonuc ayni ve alfabetik. Tekrarli aday ValueError."""
    adaylar = ["EEEUSDT", "AAAUSDT", "DDDUSDT", "BBBUSDT", "CCCUSDT"]
    kur = lambda ss: k2_adaylari_kur(ss, t=OLAY_T, hipotez="H1", yapilandirma=Y_H1)  # noqa: E731
    # REV.14 (D-B2): "olay ureten coinler" olay nesneleriyle verilir. Havuzda olmayan bir coinin
    # ("ZZZUSDT") olayi da verilebilir: eleme kume kesisimidir.
    olay = lambda ss: olaylar_sembollerde(ss, t=OLAY_T, hipotez="H1", yapilandirma=Y_H1)  # noqa: E731
    sonuc = ornekleme.k2_adaylari(kur(adaylar), olay(["CCCUSDT", "ZZZUSDT"]), olay_sembolu="AAAUSDT")
    assert sonuc.ogeler == ("BBBUSDT", "DDDUSDT", "EEEUSDT")
    assert ornekleme.k2_adaylari(kur(adaylar[::-1]), olay(["CCCUSDT"]),
                                 olay_sembolu="AAAUSDT").ogeler == sonuc.ogeler
    assert ornekleme.k2_adaylari(kur(adaylar), [], olay_sembolu="NNNUSDT").ogeler == tuple(sorted(adaylar))
    assert ornekleme.k2_adaylari(kur(adaylar), olay(adaylar), olay_sembolu="AAAUSDT").ogeler == ()
    with pytest.raises(ValueError):
        kur(adaylar + ["AAAUSDT"])
    with pytest.raises(TypeError):
        ornekleme.k2_adaylari(adaylar, [], olay_sembolu="ZZZUSDT")
    # Ham sembol listesi de kabul edilmez (rev.14).
    with pytest.raises(TypeError):
        ornekleme.k2_adaylari(kur(adaylar), ["CCCUSDT"], olay_sembolu="AAAUSDT")


def test_k2_ornekleme_olay_ureten_coini_asla_secmez_binlerce_tohumla():
    """On-kayit §6 K2 + iadesizlik: 40 aday, 5'i olay uretiyor, olayin kendi coini aday listesinde. 500 farkli
    tohumla ornekleme; secilenler arasinda olay ureten ya da olay coini hic cikmamali, 10 benzersiz olmali."""
    adaylar = [f"C{i:02d}USDT" for i in range(40)]
    ureten = {"C03USDT", "C11USDT", "C17USDT", "C25USDT", "C39USDT"}
    kur = k2_adaylari_kur(adaylar, t=OLAY_T, hipotez="H1", yapilandirma=Y_H1)
    ureten_olaylar = olaylar_sembollerde(sorted(ureten), t=OLAY_T, hipotez="H1", yapilandirma=Y_H1)
    havuz = ornekleme.k2_adaylari(kur, ureten_olaylar, olay_sembolu="C00USDT")
    assert len(havuz) == 40 - 5 - 1
    for i in range(500):
        # K2'de olayin bari adaylarin bariyla AYNI olmak zorunda (madde 3b); demet bu yuzden
        # olayin SEMBOLUYLE degistirilir.
        sec = _ornekle(havuz, sembol=f"X{i:03d}USDT").secilenler
        assert len(set(sec)) == 10
        assert not (set(sec) & (ureten | {"C00USDT"}))
