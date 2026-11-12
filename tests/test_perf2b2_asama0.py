"""Performans 2b-2, 0. asama: kapiya baglanmadan once kapanan bulgular (RESULTS §14.48 kararlari, §14.49). Aga cikmaz.

Her madde kendi basligi altinda; test adlari madde koduyla baslar. Degerler yazdirilmaz; testler yalnizca esitligi,
NaN konumunu ve hata sinifini sinar. Sentetik dunya `tests/test_seri_kurucu.py`nin yardimcilaridir.
"""

from __future__ import annotations

import functools

import numpy as np
import pandas as pd
import pytest

import config
from data import _skaler_referans as ref
from data import pencere, seri_kurucu as sk

import test_seri_kurucu as tsk
from test_seri_kurucu import BAS, G, H, U, ayni, uyusmayan

S_FUNDING = {"kume_baslangic": None, "kume_bitis": None, "donem_baslangic": BAS}


# --- D-B1: cok barli izgarada funding gelecege bakis ve oran dilimi ------------------------------------------------

def _uzun_izgara(n=60, bas=U("2024-05-01 00:00")):
    m = tsk.mumlar()
    z = tsk.izgara_4h(m)
    z = z[z >= bas][:n]
    assert len(z) == n >= 50
    return z


def _sonrasini_boz(f: pd.DataFrame, kapanis: pd.Timestamp, kip: str) -> pd.DataFrame:
    """t'nin kapanisindan (tolerans payinin disinda) SONRAKI funding kayitlarini bozar, degistirir ya da ekler."""
    f = f.copy()
    f["oran_8h"] = f["oran_8h"].astype(float)
    sonra = f["odeme_zamani"] > kapanis + pd.Timedelta(minutes=1)
    if kip == "bozuk":
        f.loc[sonra, "oran_8h"] = np.nan
    elif kip == "degistirilmis":
        f.loc[sonra, "oran_8h"] = f.loc[sonra, "oran_8h"] * 1000 + 1e-3
    else:  # eklenmis: kapanistan sonra ızgara disi zamanlarda iki yeni kayit
        ek = pd.DataFrame({"odeme_zamani": [kapanis + pd.Timedelta(hours=2), kapanis + pd.Timedelta(hours=13)],
                           "aralik_saat": [8.0, 8.0], "oran": [5e-2, -5e-2], "oran_8h": [5e-2, -5e-2]})
        f = pd.concat([f, ek], ignore_index=True).sort_values("odeme_zamani", kind="stable").reset_index(drop=True)
    return f


@pytest.mark.parametrize("kip", ["bozuk", "degistirilmis", "eklenmis"])
@pytest.mark.parametrize("j", [3, 10])
def test_D_B1_cok_barli_izgarada_sonraki_funding_erken_t_yi_degistirmez(kip, j):
    """60 barlik izgara; erken bir t'nin kapanisindan sonraki funding kaydi bozulur / degisir / eklenir. Seri yolunda
    t ve ondan onceki her barin `funding_24s` degeri degismez ve skalerle bit duzeyinde aynidir. Bozmanin etkili oldugu
    da sinanir: sonraki barlardan en az biri degisir (yoksa test bir sey olcmezdi)."""
    z = _uzun_izgara()
    f = tsk.fonlama()
    temel = sk.h2_funding_24s(f, z, **S_FUNDING)
    t = z[j]
    f2 = _sonrasini_boz(f, t + H(1), kip)
    yeni = sk.h2_funding_24s(f2, z, **S_FUNDING)
    skaler = [ref.h2_funding_24s(f2, x, **S_FUNDING) for x in z[:j + 1]]
    assert np.isfinite(temel[:j + 1]).all(), "kurulum: erken barlarin degeri hesaplanabilir olmali"
    assert uyusmayan(yeni[:j + 1], temel[:j + 1]) == 0
    assert uyusmayan(yeni[:j + 1], skaler) == 0
    assert any(not ayni(yeni[i], temel[i]) for i in range(j + 1, len(z))), "kurulum: bozma sonraki barlari etkilemeli"


def _bagimsiz_dilim(f: pd.DataFrame, t: pd.Timestamp) -> tuple[int, int]:
    """t penceresinin kayitlari, `funding.sinyal_penceresi_ayrintisi`ndan BAGIMSIZ: (kapanis - 24 saat, kapanis],
    iki uc da tolerans payiyla (on-kayit §4 "Zaman toleransi": 1 dakikadan kucuk fark ayni an)."""
    zaman = pd.DatetimeIndex(f["odeme_zamani"])
    kapanis = t + H(1)
    bas = kapanis - pd.Timedelta(hours=config.H2_FUNDING_PENCERESI_SAAT)
    tol = pd.Timedelta(minutes=1)
    secim = np.nonzero(np.asarray((zaman >= bas + tol) & (zaman < kapanis + tol)))[0]
    return int(secim.min()), int(secim.max())


def _dilim_uyusmazligi(f, z) -> int:
    return uyusmayan(sk.h2_funding_24s(f, z, **S_FUNDING), [ref.h2_funding_24s(f, x, **S_FUNDING) for x in z])


def test_D_B1_dilim_uclari_bagimsiz_secimle_ayni():
    """Penceredeki ilk ve son kaydin sira numarasi, bagimsiz bir zaman secimiyle ayni (iki uc ayri ayri)."""
    from data import funding

    z = _uzun_izgara()
    f = tsk.fonlama()
    a = funding.sinyal_penceresi_ayrintisi(f, z, config.BAR_4H, saat=config.H2_FUNDING_PENCERESI_SAAT, **S_FUNDING)
    hesap = a["hesaplanabilir"].to_numpy(dtype=bool)
    assert hesap.all(), "kurulum"
    for j, t in enumerate(z):
        assert (int(a["ilk"].iloc[j]), int(a["son"].iloc[j])) == _bagimsiz_dilim(f, t), j


@pytest.mark.parametrize("kaydirma", [{"son_kaydirma": 1}, {"son_kaydirma": -1}, {"ilk_kaydirma": 1},
                                      {"ilk_kaydirma": -1}])
def test_D_B1_kaydirilmis_dilim_testi_kirmiziya_dondurur(monkeypatch, kaydirma):
    """Kaynak degistirilmeden: dilim fonksiyonu parametreyle bozulur (ör. `son+1`) ve ayni olcum uyusmazlik verir.
    Yani dilimin uclari gercekten sinaniyor; korunmayan bir uc olsaydi bozma fark edilmezdi."""
    z = _uzun_izgara()
    f = tsk.fonlama()
    assert _dilim_uyusmazligi(f, z) == 0
    monkeypatch.setattr(sk, "_funding_dilimi", functools.partial(sk._funding_dilimi, **kaydirma))
    assert _dilim_uyusmazligi(f, z) > 0, kaydirma


# --- D-B2: uygunluk ve 1d pencerelerinde G3 ------------------------------------------------------------------------

T_UYGUN_4H = U("2024-06-01 12:00")
T_UYGUN_1D = U("2024-06-01")


def _uygunluk_iki_taraf(g, z, bar, *, donem_bas=BAS, kume_bas=None):
    esik = config.ASGARI_HACIM_4H if bar == config.BAR_4H else config.ASGARI_HACIM_1D
    yas = config.ASGARI_LISTELEME_YASI_GUN
    tablo = sk.uygunluk(g, z, bar, donem_baslangic=donem_bas, donem_bitis=tsk.SON, kume_baslangic=kume_bas,
                        asgari_hacim=esik, asgari_listeleme_yasi_gun=yas)
    gh = ref.gunluk_hacim_serisi(g)
    medyan = [ref.medyan_hacim(gh, t, donem_baslangic=donem_bas, kume_baslangic=kume_bas,
                               pencere_gun=config.HACIM_PENCERESI_GUN) for t in z]
    uygun = [ref.uygunluk_karari(gh, t, bar, donem_baslangic=donem_bas, donem_bitis=tsk.SON, kume_baslangic=kume_bas,
                                 asgari_hacim=esik, asgari_listeleme_yasi_gun=yas) for t in z]
    return tablo, medyan, uygun


@pytest.mark.parametrize("bar,t", [(config.BAR_4H, T_UYGUN_4H), (config.BAR_1D, T_UYGUN_1D)])
def test_D_B2_uygunluk_hacim_penceresinin_her_konumunda_tek_eksik_gun(bar, t):
    """Hacim penceresi t'nin gunu HARIC onceki 30 tam gundur (on-kayit §2 "Uygunluk penceresi ve t günü"). 30 konumun
    her birinde tek gun eksikken (gunun 08:00 bari silinir; gun 1d serisinden duser) iki tarafta medyan NaN ve bar
    uygun degil. Pencerenin hemen disindaki iki gun (t'nin gunu ve t-31) medyani hesaplanamaz yapmaz."""
    gun = t.floor("D")
    for j in range(1, config.HACIM_PENCERESI_GUN + 1):
        g = tsk.gunluk(tsk.mumlar(eksik=[gun - G(j) + H(2)]))
        tablo, medyan, uygun = _uygunluk_iki_taraf(g, pd.DatetimeIndex([t]), bar)
        assert np.isnan(medyan[0]) and np.isnan(tablo["medyan_hacim"].iloc[0]), j
        assert uygun == [False] and list(tablo["uygun"]) == [False], j
    disarida = [config.HACIM_PENCERESI_GUN + 1] + ([0] if bar == config.BAR_4H else [])
    for j in disarida:
        g = tsk.gunluk(tsk.mumlar(eksik=[gun - G(j) + H(2)]))
        tablo, medyan, uygun = _uygunluk_iki_taraf(g, pd.DatetimeIndex([t]), bar)
        assert np.isfinite(medyan[0]) and ayni(tablo["medyan_hacim"].iloc[0], medyan[0]), j
        assert list(tablo["uygun"]) == uygun, j


@pytest.mark.parametrize("bar", [config.BAR_4H, config.BAR_1D])
def test_D_B2_uygunlukta_kume_basi_ve_donem_basi_maskesi_seride_oncesi_veri_varken(bar):
    """Seride kume ve donem oncesi 60 gunluk veri VAR (1d serisi de o gunleri tasir). Hacim penceresi kume basini
    ya da donem basini asarsa medyan NaN; sinirla ayni gun baslayan pencere gecer. Iki maske ayri ayri."""
    m = tsk.mumlar(oncesi_gun=60)
    g = tsk.gunluk(m, bas=BAS - G(60))
    ilk_tam = BAS + G(config.HACIM_PENCERESI_GUN)          # penceresi tam BAS'ta baslayan gun
    gunler = [ilk_tam - G(1), ilk_tam, ilk_tam + G(1)]
    z = pd.DatetimeIndex(gunler if bar == config.BAR_1D else [x + H(3) for x in gunler])
    for sinir in ({"donem_bas": BAS - G(60), "kume_bas": BAS}, {"donem_bas": BAS, "kume_bas": None}):
        tablo, medyan, uygun = _uygunluk_iki_taraf(g, z, bar, **sinir)
        assert uyusmayan(tablo["medyan_hacim"], medyan) == 0, sinir
        assert list(tablo["uygun"]) == uygun, sinir
        assert np.isnan(medyan[0]) and np.isfinite(medyan[1]) and np.isfinite(medyan[2]), sinir


@pytest.mark.parametrize("ad", list(tsk.PENCERELER_1D))
def test_D_B2_h3_1d_pencerelerinde_donem_basi_ve_kume_basi_maskesi(ad):
    """H3'un 1d pencereleri; seride donem ve kume oncesi veri VAR. Pencere basi sinirdan bir gun once ise NaN, sinirla
    ayni gun ise hesaplanir; donem basi ve kume basi ayri ayri sinanir."""
    m = tsk.mumlar(oncesi_gun=60)
    g = tsk.gunluk(m, bas=BAS - G(60))
    n, ofset = tsk.PENCERELER_1D[ad]
    t = BAS + G(n - 1 + ofset)                  # pencere basi = BAS
    z = pd.DatetimeIndex([t - G(1), t, t + G(1)])
    for sinir in ({"kume_bas": BAS, "donem_bas": BAS - G(60)}, {"kume_bas": None, "donem_bas": BAS}):
        v = tsk._vektor_1d(g, z, **sinir)[ad]
        s = tsk._skaler_1d(g, z, **sinir)[ad]
        assert uyusmayan(v, s) == 0, sinir
        assert np.isnan(v[0]) and np.isfinite(v[1]) and np.isfinite(v[2]), sinir


# --- D-B3: uygunluk girdisinin dogrulamasi (kapiyla ayni fonksiyon) ------------------------------------------------

def _uygunluk_cagir(g):
    z = tsk.izgara_1d(tsk.gunluk(tsk.mumlar()))[:3]
    return sk.uygunluk(g, z, config.BAR_1D, donem_baslangic=BAS, donem_bitis=tsk.SON, kume_baslangic=None,
                       asgari_hacim=config.ASGARI_HACIM_1D, asgari_listeleme_yasi_gun=config.ASGARI_LISTELEME_YASI_GUN)


def _bozuk_1d_cerceveleri():
    m = tsk.mumlar()
    g = tsk.gunluk(m)
    nat = g.copy()
    nat.loc[nat.index[5], "close_time"] = pd.NaT
    kisa = g.copy()
    kisa["close_time"] = pd.DatetimeIndex(kisa["open_time"]) + H(1) - pd.Timedelta(milliseconds=1)
    return {"4h_cercevesi": m, "close_time_NaT": nat, "bar_suresi_4_saat": kisa,
            "cerceve_degil": pd.Series([1.0]), "open_time_yok": g.drop(columns=["open_time"])}


@pytest.mark.parametrize("ad", list(_bozuk_1d_cerceveleri()))
def test_D_B3_uygunluk_girdisi_skalerle_ayni_sinif_ve_mesajla_reddedilir(ad):
    """4h cercevesi (ya da NaT'li / 4 saatlik 1d cercevesi) verilince seri kurucusu skalerle (`_gunluk_hacim`) ayni sinif
    ve AYNI mesajla duser. Oncesinde 4h cercevesi sessizce kabul ediliyordu (§14.48 D-B3)."""
    g = _bozuk_1d_cerceveleri()[ad]
    with pytest.raises(Exception) as skaler:
        ref._gunluk_hacim(g)
    with pytest.raises(Exception) as vektor:
        _uygunluk_cagir(g)
    assert type(vektor.value) is type(skaler.value) and str(vektor.value) == str(skaler.value), ad
    if ad == "4h_cercevesi":
        assert type(vektor.value) is pencere.VeriHatasi


def test_D_B3_kapi_ve_seri_kurucusu_ayni_dogrulama_fonksiyonunu_cagirir():
    """Dogrulama kopyalanmadi: `pozisyon._gunluk_hacim` ve `seri_kurucu.uygunluk` ayni fonksiyonu cagirir ve hata
    metinleri `data/` icinde yalnizca `eligibility.py`de (ve dondurulmus referansta) yazilidir."""
    import ast

    from data import pozisyon

    for modul, fonk in ((pozisyon, "_gunluk_hacim"), (sk, "uygunluk")):
        kaynak = (tsk.KOK / "data" / f"{modul.__name__.rpartition('.')[2]}.py").read_text(encoding="utf-8")
        tanim = next(d for d in ast.walk(ast.parse(kaynak)) if isinstance(d, ast.FunctionDef) and d.name == fonk)
        cagrilar = {d.func.attr for d in ast.walk(tanim) if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)}
        assert "gunluk_cercevesini_dogrula" in cagrilar, (modul.__name__, fonk)
    metin = "acilislar UTC gun basi degil"
    sahipler = sorted(y.name for y in (tsk.KOK / "data").glob("*.py") if metin in y.read_text(encoding="utf-8"))
    assert sahipler == ["_skaler_referans.py", "eligibility.py"], sahipler


# --- D-C3: G5'in hata yolu (arastirma tarafinin karari: sapma kabul edildi) -----------------------------------------

@pytest.mark.parametrize("bozma", ["sirasiz", "tekrarli"])
def test_D_C3_seri_birim_hatasi_skalerde_en_az_bir_barda_ayni_sinifla_karsilanir(bozma):
    """Izgaranin ortasinda funding zaman dizisi bozuk (sirasiz ya da tekrarli damga). Seri yolu birimi
    `ZamanDizisiHatasi` ile durdurur (G10: birim hatasi; deger uretmez). Kabul edilen sapmanin kosulu (RESULTS §14.49):
    ayni girdide skaler yol bozukluktan SONRAKI en az bir barda ayni sinifla duser, bozukluktan onceki barlarda deger
    verir. Boylece G10'un "birim hatasi = skalerde en az bir beklenmeyen hata" kurali saglanir."""
    z = _uzun_izgara()
    f = tsk.fonlama()
    orta = z[30] + H(1)
    i = int(np.searchsorted(pd.DatetimeIndex(f["odeme_zamani"]), orta))
    f2 = f.copy()
    if bozma == "sirasiz":
        f2.loc[[i, i + 1], "odeme_zamani"] = f.loc[[i + 1, i], "odeme_zamani"].to_numpy()
    else:
        f2.loc[i + 1, "odeme_zamani"] = f.loc[i, "odeme_zamani"]
    with pytest.raises(pencere.ZamanDizisiHatasi):
        sk.h2_funding_24s(f2, z, **S_FUNDING)
    sonuclar = []
    for t in z:
        try:
            sonuclar.append(ref.h2_funding_24s(f2, t, **S_FUNDING))
        except Exception as hata:  # noqa: BLE001 - yalnizca sinif sinanir
            sonuclar.append(hata)
    bozuk_an = pd.Timestamp(f2["odeme_zamani"].iloc[i])
    sonraki = [s for t, s in zip(z, sonuclar) if t + H(1) >= bozuk_an]
    onceki = [s for t, s in zip(z, sonuclar) if t + H(1) < bozuk_an - pd.Timedelta(hours=1)]
    assert any(type(s) is pencere.ZamanDizisiHatasi for s in sonraki), "skaler en az bir barda ayni sinifla dusmeli"
    assert all(not isinstance(s, BaseException) for s in onceki) and len(onceki) > 0
    assert all(isinstance(s, (float, pencere.ZamanDizisiHatasi)) for s in sonuclar)


# --- D-C8: seri_kurucu yalnizca kapi modulunden ---------------------------------------------------------------------

def test_D_C8_data_icinde_yalnizca_kapi_modulu_seri_kurucuyu_anabilir(tmp_path):
    from tarama_yardimcisi import seri_kurucu_ihlalleri

    (tmp_path / "data").mkdir()
    for ad, icerik in (("pozisyon.py", "from data import seri_kurucu\n"),
                       ("seri_kurucu.py", "# seri_kurucu modulunun kendisi\n"),
                       ("ornekleme.py", "from data import seri_kurucu as sk\n"),
                       ("dizi.py", "from data.seri_kurucu import h1_dip\n"),
                       ("sinyal.py", "x = 1  # seri metni serbest\n")):
        (tmp_path / "data" / ad).write_text(icerik, encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("from data import seri_kurucu\n", encoding="utf-8")
    assert seri_kurucu_ihlalleri(kok=tmp_path) == ["data/dizi.py", "data/ornekleme.py"]


def test_D_C8_depoda_mevcut_ihlal_yok():
    from tarama_yardimcisi import seri_kurucu_ihlalleri

    assert seri_kurucu_ihlalleri() == []


# --- D-C5: pencerelerin dis uclari ----------------------------------------------------------------------------------

@pytest.mark.parametrize("k", list(config.IZGARA["H2"]["k"]))
def test_D_C5_kirilim_dip_dis_uclari_her_k_icin(k):
    """`min(low[t-k..t-1])`: t HARIC, t-1 ve t-k DAHIL, t-(k+1) DISARIDA; her izgara k'si icin (3, 6, 12)."""
    t = tsk.T4
    def tek(j):
        m = tsk.mumlar(bozuk=[t - H(j)])
        z = pd.DatetimeIndex([t])
        return sk.h2_kirilim_dip(m, z, k, **tsk.SINIR)[0], ref.h2_kirilim_dip(m, t, k, **tsk.SINIR)
    for j, nan_beklenir in ((0, False), (1, True), (k, True), (k + 1, False)):
        v, s = tek(j)
        assert ayni(v, s), (k, j)
        assert bool(np.isnan(v)) == nan_beklenir, (k, j)


@pytest.mark.parametrize("ad", ["kapanis_30_once", "yuksek_30_max"])
def test_D_C5_1d_31_barlik_pencerelerde_t_eksi_31_disarida(ad):
    """1d `[t-30 .. t]`: t ve t-30 DAHIL (eksikse NaN), t-31 DISARIDA (eksikligi degeri degistirmez)."""
    t = tsk.T1
    temel = tsk._vektor_1d(tsk.gunluk(tsk.mumlar()), pd.DatetimeIndex([t]))[ad][0]
    for j, nan_beklenir in ((0, True), (30, True), (31, False)):
        g = tsk.gunluk(tsk.mumlar(bozuk=[t - G(j) + H(2)]))
        v = tsk._vektor_1d(g, pd.DatetimeIndex([t]))[ad][0]
        s = tsk._skaler_1d(g, [t])[ad][0]
        assert ayni(v, s) and bool(np.isnan(v)) == nan_beklenir, j
        if not nan_beklenir:
            assert ayni(v, temel), j


@pytest.mark.parametrize("ad", list(tsk.PENCERELER_1D))
def test_D_C5_1d_konum_testinde_tam_pencere_sonlu(ad):
    """`test_G3_1d_her_konumda_tek_eksik_gun_iki_tarafta_NaN` yalnizca NaN'i sinar; eksiksiz pencere iki tarafta da
    SONLU olmali (aksi halde her konumdaki NaN kurulumdan gelebilirdi)."""
    g = tsk.gunluk(tsk.mumlar())
    v = tsk._vektor_1d(g, pd.DatetimeIndex([tsk.T1]))[ad][0]
    s = tsk._skaler_1d(g, [tsk.T1])[ad][0]
    assert np.isfinite(v) and ayni(v, s)
