"""On-kayit §4 rev.9 "Funding tamligi": capa, zincir, ilk cift, son (`funding.funding_tamlik_ayrintisi`).

"Kural odeme ani tahmin etmez; yalnizca kayitlar arasindaki bosluklari olcer." Butun zaman
karsilastirmalari §4 "Zaman toleransi"na gore: fark 1 dakikadan kesin kucukse ayni an, tam
1 dakika ayni an degildir. Aga cikmaz; yalnizca odeme zamani ve araligi (oran sutunu yok).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import config
from data import funding, pencere

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
DK = pd.Timedelta(minutes=1)
NS = pd.Timedelta(1, "ns")
H = pd.Timedelta(hours=1)
BAS = T("2025-01-01 00:00")


def _seri(kayitlar):
    """[(zaman, aralik_saat)] -> funding cercevesi (oran sutunu yok)."""
    return pd.DataFrame({"odeme_zamani": pd.DatetimeIndex([T(z) if isinstance(z, str) else z for z, _ in kayitlar]),
                         "aralik_saat": [float(a) for _, a in kayitlar]})


def _a(seri, giris, son, bas=BAS):
    g = T(giris) if isinstance(giris, str) else giris
    s = T(son) if isinstance(son, str) else son
    return funding.funding_tamlik_ayrintisi(seri, [g], [s], donem_baslari=[bas]).iloc[0]


def _ritim(bas, son, saat):
    return [(z, saat) for z in pd.date_range(T(bas), T(son), freq=f"{saat}h")]


# --- Capa ----------------------------------------------------------------------------


def test_capa_yoksa_tam_degil():
    """Girisin ardindan baslayan eksiksiz seri: capa yok -> tam degil (rev.8'de tamdi)."""
    s = _a(_seri(_ritim("2025-01-02 08:00", "2025-01-03", 8)), "2025-01-02 04:00", "2025-01-02 16:00")
    assert not s["capa_var"] and not s["tam"]
    assert np.isnan(s["capa_aralik_saat"]) and not s["tek_ritim"]


def test_bos_seride_capa_yok():
    bos = pd.DataFrame({"odeme_zamani": pd.DatetimeIndex([], tz="UTC"), "aralik_saat": np.empty(0)})
    s = _a(bos, "2025-01-02 04:00", "2025-01-02 16:00")
    assert not s["capa_var"] and not s["tam"]


@pytest.mark.parametrize("kayma,capa", [(pd.Timedelta(0), True), (DK - NS, True), (DK, False), (DK + NS, False)])
def test_capa_giris_aninda_ya_da_oncesinde(kayma, capa):
    """Giris ani ile ayni an sayilan kayit capadir; tam 1 dakika sonrasi degildir."""
    seri = _seri([(T("2025-01-02 08:00") + kayma, 8)])
    s = _a(seri, "2025-01-02 08:00", "2025-01-02 12:00")
    assert bool(s["capa_var"]) is capa


@pytest.mark.parametrize("kayma,capa", [(pd.Timedelta(0), True), (-(DK - NS), True), (-DK, False), (-(DK + NS), False)])
def test_capa_donem_ici_olmali(kayma, capa):
    """Capa "donem ici" kayittir: donem basiyla ayni an ya da sonra; tam 1 dakika once degil."""
    seri = _seri([(BAS + kayma, 8)])
    s = _a(seri, BAS + 4 * H, BAS + 6 * H)
    assert bool(s["capa_var"]) is capa
    assert bool(s["tam"]) is capa  # capa + 8h pencere sonundan sonra


def test_capa_donem_basindan_onceki_kayit_olamaz_sonraki_kayit_da_capa_degil():
    """Donem basindan onceki kayit capa olamaz; girisin ardindaki kayit da capa olamaz."""
    seri = _seri([("2024-12-31 20:00", 8), ("2025-01-01 04:00", 8)])
    s = _a(seri, "2025-01-01 00:00", "2025-01-01 04:00")
    assert not s["capa_var"] and not s["tam"]


# --- Ilk cift: taban giris ani ----------------------------------------------------------


def test_ilk_ciftte_taban_giris():
    """2026-06-24 deseni: capa 00:00 (4h), 04:00 eksik, sonraki 08:00. Giris 04:00'te ise
    eksik odeme giris aninda kalir, pozisyonu ilgilendirmez -> tam."""
    seri = _seri([("2025-01-02 00:00", 4), ("2025-01-02 08:00", 4), ("2025-01-02 12:00", 4)])
    assert _a(seri, "2025-01-02 04:00", "2025-01-02 12:00")["tam"]
    # Giris 00:00'da ise ayni eksik odeme girisin ardindadir -> eksik.
    s = _a(seri, "2025-01-02 00:00", "2025-01-02 12:00")
    assert s["capa_var"] and not s["zincir_tam"] and not s["tam"]


@pytest.mark.parametrize("giris_kaymasi,tam", [
    (pd.Timedelta(0), True),             # giris 04:00: sonraki 08:00 = giris + 4h
    (-(DK - NS), True),                  # giris 03:59:00.000000001: fark 59.999... s -> ayni an
    (-DK, False),                        # giris 03:59: sonraki kayit giris + 4h'ten tam 1 dk sonra
    (-(DK + NS), False),
])
def test_ilk_cift_tolerans_siniri(giris_kaymasi, tam):
    seri = _seri([("2025-01-02 00:00", 4), ("2025-01-02 08:00", 4), ("2025-01-02 12:00", 4)])
    s = _a(seri, T("2025-01-02 04:00") + giris_kaymasi, "2025-01-02 12:00")
    assert bool(s["zincir_tam"]) is tam and bool(s["tam"]) is tam


def test_giris_tabani_yalnizca_ilk_ciftte():
    """Ikinci ciftte taban onceki kayittir: 04:00 -> 12:00 boslugu (08:00 eksik) giristen
    sonra oldugu icin yakalanir."""
    seri = _seri([("2025-01-02 00:00", 4), ("2025-01-02 04:00", 4), ("2025-01-02 12:00", 4)])
    s = _a(seri, "2025-01-02 06:00", "2025-01-02 12:00")
    assert s["capa_var"] and not s["zincir_tam"] and not s["tam"]


def test_ilk_ciftte_iki_araligin_buyugu():
    """Ilk ciftte de adim iki kaydin araliklarindan buyugudur (rev.8 ilk kaydin araligini
    kullaniyordu): capa 8h, sonraki 2h."""
    seri = _seri([("2025-01-02 00:00", 8), ("2025-01-02 08:00", 2), ("2025-01-02 10:00", 2)])
    assert _a(seri, "2025-01-02 02:00", "2025-01-02 10:00")["tam"]


# --- Zincir ve aralik gecisleri -----------------------------------------------------------


@pytest.mark.parametrize("fazla,tam", [(pd.Timedelta(0), True), (DK - NS, True), (DK, False), (DK + NS, False)])
def test_zincir_tolerans_siniri(fazla, tam):
    """Sonraki kayit onceki + iki araligin buyugu + tolerans payindan SONRA olamaz."""
    seri = _seri([("2025-01-02 00:00", 8), ("2025-01-02 08:00", 8),
                  (T("2025-01-02 16:00") + fazla, 8), (T("2025-01-03 00:00") + fazla, 8)])
    s = _a(seri, "2025-01-02 04:00", "2025-01-03 00:00")
    assert bool(s["zincir_tam"]) is tam


def test_bir_saatten_dort_saate_gecis():
    """1 -> 4 gecisi: gecis kaydi (20:00, 4h) onceki 1 saatlik kayittan 1 saat sonra gelir;
    sonraki bosluklar 4 saat. Eksiksiz -> tam. 4 saatlik ritimde bir odeme eksik -> eksik."""
    kayitlar = _ritim("2025-01-02 16:00", "2025-01-02 19:00", 1) + _ritim("2025-01-02 20:00", "2025-01-03 08:00", 4)
    s = _a(_seri(kayitlar), "2025-01-02 18:00", "2025-01-03 08:00")
    assert s["tam"] and not s["tek_ritim"]
    assert s["capa_aralik_saat"] == 1.0 and s["son_aralik_saat"] == 4.0
    eksik = [k for k in kayitlar if k[0] != T("2025-01-03 00:00")]
    assert not _a(_seri(eksik), "2025-01-02 18:00", "2025-01-03 08:00")["tam"]


def test_bir_saatten_dort_saate_geciste_gecisten_onceki_tek_eksik_gorulmez():
    """Kuralin yazili davranisi: 19:00 (1h) eksik; 18:00 (1h) -> 20:00 (4h) boslugu 2 saat,
    iki araligin buyugunu (4) asmiyor -> tam. Gecise bitisik tek eksik odeme zincir kuraliyla
    gorulemez (Rev.9 "bilinen sinirlar" listesinde sayilmayan gevseklik; rapor)."""
    kayitlar = [k for k in _ritim("2025-01-02 16:00", "2025-01-02 19:00", 1) if k[0] != T("2025-01-02 19:00")]
    kayitlar += _ritim("2025-01-02 20:00", "2025-01-03 08:00", 4)
    assert _a(_seri(kayitlar), "2025-01-02 16:00", "2025-01-03 08:00")["tam"]


def test_dort_saatten_sekiz_saate_gecis():
    kayitlar = _ritim("2025-01-02 00:00", "2025-01-02 08:00", 4) + _ritim("2025-01-02 16:00", "2025-01-03 16:00", 8)
    s = _a(_seri(kayitlar), "2025-01-02 02:00", "2025-01-03 16:00")
    assert s["tam"] and s["capa_aralik_saat"] == 4.0 and s["son_aralik_saat"] == 8.0
    # 8 saatlik ritimde bir odeme eksik: 16:00 -> 01-03 08:00 boslugu 16 saat > 8.
    eksik = [k for k in kayitlar if k[0] != T("2025-01-03 00:00")]
    assert not _a(_seri(eksik), "2025-01-02 02:00", "2025-01-03 16:00")["tam"]


def test_sekiz_saatten_dort_saate_gecis():
    kayitlar = _ritim("2025-01-02 00:00", "2025-01-02 08:00", 8) + _ritim("2025-01-02 12:00", "2025-01-03 00:00", 4)
    s = _a(_seri(kayitlar), "2025-01-02 04:00", "2025-01-03 00:00")
    assert s["tam"] and s["capa_aralik_saat"] == 8.0 and s["son_aralik_saat"] == 4.0
    # 4 saatlik ritimde iki ardisik odeme eksik (12:00, 16:00): 08:00 -> 20:00 = 12 saat > 8.
    eksik = [k for k in kayitlar if k[0] not in (T("2025-01-02 12:00"), T("2025-01-02 16:00"))]
    assert not _a(_seri(eksik), "2025-01-02 04:00", "2025-01-03 00:00")["tam"]
    # 4 saatlik ritimde tek eksik (16:00): 12:00 (4) -> 20:00 (4) = 8 saat > 4 -> eksik.
    tek = [k for k in kayitlar if k[0] != T("2025-01-02 16:00")]
    assert not _a(_seri(tek), "2025-01-02 04:00", "2025-01-03 00:00")["tam"]


def test_gecersiz_aralik_tam_degil():
    seri = _seri([("2025-01-02 00:00", 8), ("2025-01-02 08:00", float("nan")), ("2025-01-02 16:00", 8)])
    s = _a(seri, "2025-01-02 04:00", "2025-01-02 16:00")
    assert s["capa_var"] and not s["aralik_gecerli"] and not s["tam"]
    # Aralik gecersiz kayit capadan once ise dizinin disindadir.
    seri2 = _seri([("2025-01-01 16:00", 0), ("2025-01-02 00:00", 8), ("2025-01-02 08:00", 8)])
    assert _a(seri2, "2025-01-02 04:00", "2025-01-02 08:00")["tam"]


# --- Son ve pencere sonu --------------------------------------------------------------------


@pytest.mark.parametrize("son_kaymasi,tam", [
    (pd.Timedelta(0), True),           # son kayit + 4h = pencere sonu: esitlik yeterli
    (DK - NS, True),                   # pencere sonu 59.999... s sonra: hala ayni an
    (DK, False),                       # tam 1 dk: son kayit + aralik pencere sonundan ONCE
    (DK + NS, False),
])
def test_son_tolerans_siniri_ve_esitlik_affi(son_kaymasi, tam):
    seri = _seri(_ritim("2025-01-02 00:00", "2025-01-02 08:00", 4))
    s = _a(seri, "2025-01-02 00:00", T("2025-01-02 12:00") + son_kaymasi)
    assert bool(s["son_tam"]) is tam and bool(s["tam"]) is tam
    assert bool(s["son_esitlik_affi"]) is tam


def test_pencere_sonunda_kayit_var():
    """Pencere sonuyla ayni an kayit pencerededir ve son kayittir; dogrulanamayan dilim yok."""
    seri = _seri(_ritim("2025-01-02 00:00", "2025-01-03 00:00", 8))
    s = _a(seri, "2025-01-02 04:00", "2025-01-02 16:00")
    assert s["tam"] and s["kuyruk_sifir"] and not s["kuyruk_kismi"] and not s["son_esitlik_affi"]
    # Pencere sonundan 59.999... s sonraki kayit da ayni an: pencerede.
    kaymis = _seri([("2025-01-02 00:00", 8), ("2025-01-02 08:00", 8), (T("2025-01-02 16:00") + DK - NS, 8)])
    assert _a(kaymis, "2025-01-02 04:00", "2025-01-02 16:00")["kuyruk_sifir"]


def test_pencere_sonunda_kayit_yok():
    """Pencere sonundaki kayit tam 1 dk sonraya kayarsa pencerenin disindadir; son kayit
    08:00 + 8h tam pencere sonu -> esitlik affi. Kayit hic yoksa ve pencere sonu daha
    ilerideyse eksik."""
    kaymis = _seri([("2025-01-02 00:00", 8), ("2025-01-02 08:00", 8), (T("2025-01-02 16:00") + DK, 8)])
    s = _a(kaymis, "2025-01-02 04:00", "2025-01-02 16:00")
    assert s["tam"] and s["son_esitlik_affi"] and not s["kuyruk_sifir"]
    yok = _seri([("2025-01-02 00:00", 8), ("2025-01-02 08:00", 8)])
    assert not _a(yok, "2025-01-02 04:00", "2025-01-02 20:00")["tam"]


def test_pencerede_capadan_sonra_kayit_yoksa_son_kayit_capadir():
    """Rev.9 "hic kayit yok" cumlesini kaldirdi: capa + aralik pencere sonundan sonra ise tam."""
    seri = _seri([("2025-01-02 00:00", 8), ("2025-01-02 08:00", 8)])
    s = _a(seri, "2025-01-02 00:00", "2025-01-02 04:00")
    assert s["tam"] and s["kuyruk_kismi"]
    # Capa + aralik pencere sonundan once doluyorsa eksik (08:00 odemesi kayitta yok).
    assert not _a(_seri([("2025-01-02 00:00", 8)]), "2025-01-02 04:00", "2025-01-02 12:00")["tam"]


def test_ondan_sonraki_kayitlar_hukmu_degistirmez():
    """Pencere sonundan sonraki kayitlar okunmaz: sonrasini bozmak hukmu degistirmez."""
    seri = _seri(_ritim("2025-01-02 00:00", "2025-01-04 00:00", 8))
    once = funding.funding_tamlik_ayrintisi(seri, [T("2025-01-02 04:00")], [T("2025-01-02 20:00")],
                                            donem_baslari=[BAS])
    bozuk = seri.copy()
    bozuk.loc[bozuk["odeme_zamani"] > T("2025-01-02 20:00") + DK, "aralik_saat"] = 1000.0
    bozuk = bozuk.loc[bozuk["odeme_zamani"] != T("2025-01-03 08:00")]
    sonra = funding.funding_tamlik_ayrintisi(bozuk, [T("2025-01-02 04:00")], [T("2025-01-02 20:00")],
                                             donem_baslari=[BAS])
    pd.testing.assert_frame_equal(once, sonra)


# --- Plan uzerinden: pencere sonu ve capa tabani -----------------------------------------------


def _plan(t, ufuk, bas, b):
    z = pd.date_range(bas, b, freq="4h")
    return pencere.pozisyon_plani(z, t, ufuk, config.BAR_4H, birincil_ufuk=18, kume_baslangic=None,
                                  kume_bitis=None, donem_baslangic=bas, donem_bitis=b)


def test_plan_capa_tabani_donem_basi():
    """`pozisyon_funding_tam_mi` capa tabani olarak planin donem basini kullanir: donem
    basindan onceki kayit capa olamaz."""
    bas, b = T("2025-01-10 00:00"), T("2025-01-20 00:00")
    plan = _plan(bas, 3, bas, b)  # giris 04:00
    once_kayit = _seri([("2025-01-09 20:00", 8), ("2025-01-10 04:00", 8), ("2025-01-10 12:00", 8)])
    # 01-10 04:00 kaydi giris aninda: capa, donem ici -> tam
    assert funding.pozisyon_funding_tam_mi(once_kayit, plan)
    yalniz_once = _seri([("2025-01-09 20:00", 8), ("2025-01-10 12:00", 8)])
    assert not funding.pozisyon_funding_tam_mi(yalniz_once, plan)


def test_vektorel_ve_tekil_ayni():
    rng = np.random.default_rng(config.TOHUM)
    zam = list(pd.date_range(BAS, T("2025-01-10"), freq="4h"))
    sil = set(rng.choice(len(zam), size=8, replace=False).tolist())
    seri = _seri([(z, 4) for i, z in enumerate(zam) if i not in sil])
    girisler = list(pd.date_range(BAS, T("2025-01-09"), freq="12h"))
    sonlar = [g + pd.Timedelta(hours=int(h)) for g, h in zip(girisler, rng.integers(0, 40, len(girisler)))]
    toplu = funding.funding_tamlik_ayrintisi(seri, girisler, sonlar, donem_baslari=[BAS] * len(girisler))
    for i in range(len(girisler)):
        tek = funding.funding_tamlik_ayrintisi(seri, [girisler[i]], [sonlar[i]], donem_baslari=[BAS]).iloc[0]
        pd.testing.assert_series_equal(toplu.iloc[i], tek, check_names=False)
    assert 0 < toplu["tam"].sum() < len(girisler)


def test_uzunluk_uyusmazligi_ve_zorunlu_donem_baslari():
    seri = _seri([("2025-01-02 00:00", 8)])
    with pytest.raises(ValueError):
        funding.funding_tamlik_ayrintisi(seri, [T("2025-01-02 04:00")], [T("2025-01-02 08:00")], donem_baslari=[])
    with pytest.raises(TypeError):
        funding.funding_tamlik_ayrintisi(seri, [T("2025-01-02 04:00")], [T("2025-01-02 08:00")])  # noqa
