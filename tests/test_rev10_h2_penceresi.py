"""H2 funding sinyal penceresi (on-kayit §4 "Funding sinyal penceresinin tamligi", rev.9 + rev.10).

Kural (ozet): pencere t barinin kapanisinda biter, 24 saat geriye uzanir ve YARI ACIKTIR: pencere
basina tam denk gelen kayit ortalamaya girmez, pencere sonuna denk gelen girer (ikisi de tolerans
payiyla). Capa pencere basinda ya da oncesinde kalan son kayittir ve donem basi ile kume basinin
gec olanindan once olamaz. Zincir capadan pencere sonuna kadar; ilk ciftte taban pencere basi. Son
kosulu uygulanmaz. Her kaydin araligi sonlu ve > 0. t'nin kapanisindan sonraki hicbir kayit
okunmaz. Pencerenin tamami kumenin icinde olmali; kume siniri karsilastirmalari toleransla.

Testlerdeki oranlar sentetiktir (gercek veri okunmaz). Aga cikmaz.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import config
from data import funding, pencere

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H = lambda n: pd.Timedelta(hours=n)  # noqa: E731
SN = lambda n: pd.Timedelta(seconds=n)  # noqa: E731
DB = T("2030-01-01")  # donem basi (uzak)
T0 = T("2030-06-10 20:00")  # t; kapanis 06-11 00:00, pencere basi 06-10 00:00
KAPANIS = T0 + H(4)
BAS = KAPANIS - H(24)


def _seri(zamanlar, aralik=8.0, oran=None):
    zamanlar = pd.DatetimeIndex(zamanlar)
    oran = np.arange(1, len(zamanlar) + 1, dtype=float) * 1e-4 if oran is None else np.asarray(oran, dtype=float)
    a = np.full(len(zamanlar), float(aralik)) if np.ndim(aralik) == 0 else np.asarray(aralik, dtype=float)
    return pd.DataFrame({"odeme_zamani": zamanlar, "aralik_saat": a, "oran": oran, "oran_8h": oran})


def _sekiz_saatlik(bas=T("2030-06-01"), son=T("2030-06-20")):
    return _seri(pd.date_range(bas, son, freq="8h"))


def _ort(fund, t=T0, **sinirlar):
    s = dict(kume_baslangic=None, kume_bitis=None, donem_baslangic=DB)
    s.update(sinirlar)
    return funding.funding_ortalamasi(fund, t, config.BAR_4H, saat=24, **s)


def _oran(fund, an):
    return float(fund.loc[fund["odeme_zamani"] == an, "oran_8h"].iloc[0])


# --- Yari acik pencere ----------------------------------------------------------------------------


def test_basa_denk_gelen_disarida_sona_denk_gelen_iceride():
    fund = _sekiz_saatlik()
    beklenen = np.mean([_oran(fund, BAS + H(8)), _oran(fund, BAS + H(16)), _oran(fund, KAPANIS)])
    assert _ort(fund) == pytest.approx(beklenen)
    # Bastaki kayit (BAS) ortalamaya girseydi sonuc farkli olurdu.
    assert _ort(fund) != pytest.approx(np.mean([_oran(fund, BAS), _oran(fund, BAS + H(8)), _oran(fund, BAS + H(16))]))


@pytest.mark.parametrize("kayma, bastaki_icerde", [
    (SN(0), False), (SN(30), False), (SN(59), False), (pd.Timedelta(minutes=1), True), (-SN(30), False)])
def test_pencere_basi_toleransi(kayma, bastaki_icerde):
    """Pencere basina tolerans payi icinde denk gelen kayit girmez; tam 1 dk sonraki girer."""
    zamanlar = [BAS - H(8), BAS + kayma, BAS + H(8), BAS + H(16), KAPANIS]
    fund = _seri(zamanlar, oran=[1e-4, 9e-4, 1e-4, 1e-4, 1e-4])
    beklenen = np.mean([9e-4, 1e-4, 1e-4, 1e-4]) if bastaki_icerde else 1e-4
    assert _ort(fund) == pytest.approx(beklenen)


@pytest.mark.parametrize("kayma, sondaki_icerde", [
    (SN(0), True), (SN(30), True), (SN(59), True), (-SN(30), True), (pd.Timedelta(minutes=1), False)])
def test_pencere_sonu_toleransi(kayma, sondaki_icerde):
    """Pencere sonuna tolerans payi icinde denk gelen kayit girer; tam 1 dk sonraki okunmaz."""
    zamanlar = [BAS, BAS + H(8), BAS + H(16), KAPANIS + kayma]
    fund = _seri(zamanlar, oran=[1e-4, 1e-4, 1e-4, 9e-4])
    beklenen = np.mean([1e-4, 1e-4, 9e-4]) if sondaki_icerde else 1e-4
    assert _ort(fund) == pytest.approx(beklenen)


# --- Gelecege bakis yok ------------------------------------------------------------------------


def test_kapanistan_sonraki_kayitlar_hic_okunmaz():
    """Kapanistan sonraki kayitlar (oran, aralik, hatta bozuk damga) sonucu etkilemez."""
    fund = _sekiz_saatlik()
    once = _ort(fund)
    bozuk = fund.copy()
    sonra = bozuk["odeme_zamani"] > KAPANIS + pd.Timedelta(minutes=1)
    bozuk.loc[sonra, "oran_8h"] = np.nan
    bozuk.loc[sonra, "aralik_saat"] = -1.0
    # Kapanistan sonra sirasiz ve tekrarli damgalar: seri yine de kapanisa kadar gecerli.
    ek = pd.DataFrame({"odeme_zamani": [KAPANIS + H(30), KAPANIS + H(30), KAPANIS + H(20)],
                       "aralik_saat": 8.0, "oran": 1.0, "oran_8h": 1.0})
    bozuk = pd.concat([bozuk, ek], ignore_index=True)
    assert _ort(bozuk) == once


# --- Capa, zincir, son kosulu yok -------------------------------------------------------------------


def test_ilk_cift_tabani_pencere_basi():
    """Capa pencere basindan cok once olabilir; capa ile ilk kayit arasindaki bosluk pencere disindadir.
    Ilk ciftte taban pencere basidir: ilk kayit BAS + 8h'den sonra olmadikca zincir tamdir."""
    fund = _seri([BAS - H(20), BAS + H(4), BAS + H(12), BAS + H(20)])
    assert not np.isnan(_ort(fund))
    # Ilk kayit taban + araliktan (8h) sonra: eksik odeme.
    fund2 = _seri([BAS - H(20), BAS + H(9), BAS + H(17)])
    assert np.isnan(_ort(fund2))


def test_capa_yoksa_nan():
    fund = _seri([BAS + H(8), BAS + H(16), KAPANIS])
    assert np.isnan(_ort(fund))


def test_capa_pencere_basinda_olabilir():
    fund = _seri([BAS, BAS + H(8), BAS + H(16), KAPANIS])
    assert not np.isnan(_ort(fund))


def test_son_kosulu_uygulanmaz():
    """Pencere sonundaki kayit eksik: son kayit + araligi pencere sonundan once. Rev.9: son kosulu
    sinyal penceresine uygulanmaz; deger hesaplanir."""
    fund = _seri([BAS, BAS + H(8), BAS + H(16)])
    assert _ort(fund) == pytest.approx(np.mean([2e-4, 3e-4]))


def test_ortadaki_eksik_odeme_nan():
    fund = _seri([BAS, BAS + H(8), KAPANIS])  # BAS + 16h eksik: 8 -> 24 boslugu 8h'yi asar
    assert np.isnan(_ort(fund))


@pytest.mark.parametrize("bozuk_aralik", [0.0, -8.0, np.inf, np.nan])
def test_gecersiz_aralik_nan(bozuk_aralik):
    """On-kayit §4 "Gecerli aralik" (rev.10): dizideki her kaydin araligi sonlu ve > 0."""
    fund = _seri([BAS, BAS + H(8), BAS + H(16), KAPANIS], aralik=[8.0, 8.0, bozuk_aralik, 8.0])
    assert np.isnan(_ort(fund))


def test_nan_oran_nan():
    fund = _seri([BAS, BAS + H(8), BAS + H(16), KAPANIS], oran=[1e-4, 1e-4, np.nan, 1e-4])
    assert np.isnan(_ort(fund))


def test_pencerede_kayit_yoksa_nan():
    """Capa var, uzun aralikli ve pencerede kayit yok: ortalama tanimsiz."""
    fund = _seri([BAS - H(1)], aralik=48.0)
    assert np.isnan(_ort(fund))


# --- Donem ve kume ---------------------------------------------------------------------------------


def test_pencere_basi_kume_basindan_onceyse_nan():
    fund = _sekiz_saatlik()
    assert not np.isnan(_ort(fund, kume_baslangic=BAS))  # capa BAS'ta, ayni an
    assert not np.isnan(_ort(fund, kume_baslangic=BAS + SN(59)))  # ayni an (tolerans)
    assert np.isnan(_ort(fund, kume_baslangic=BAS + pd.Timedelta(minutes=1)))
    assert np.isnan(_ort(fund, kume_baslangic=BAS + H(8)))  # kume oncesi kayitlar seride olsa bile


def test_pencere_basi_donem_basindan_onceyse_nan():
    fund = _sekiz_saatlik()
    assert not np.isnan(_ort(fund, donem_baslangic=BAS))
    assert np.isnan(_ort(fund, donem_baslangic=BAS + pd.Timedelta(minutes=1)))


def test_kumenin_son_bari_dusmez():
    """KESIF sonu 23:59:59; son barin (20:00) kapanisi 00:00. Fark 1 sn: ayni an; bar dusmez."""
    kume_son = T0.floor("D") + H(24) - SN(1)
    assert kume_son == T("2030-06-10 23:59:59")
    fund = _sekiz_saatlik()
    assert not np.isnan(_ort(fund, kume_bitis=kume_son))
    assert np.isnan(_ort(fund, kume_bitis=KAPANIS - pd.Timedelta(minutes=1)))
    assert np.isnan(_ort(fund, kume_bitis=KAPANIS - H(4)))


def test_gercek_kesif_siniri_ile_son_bar_kume_icinde():
    """KESIF'in son bari (08-31 20:00) gercek kume sinirlariyla kume icinde sayilir ve hesaplanir.

    Veri katmani (`funding_yukle`) funding'i kumeye HAM karsilastirmayla keser; 09-01 00:00 kaydi
    (C2'nin ilk kaydi) KESIF serisinde yoktur. Bu kaydin pencereye girip girmedigi on-kayitta iki
    bicimde okunabildigi icin veri katmani degistirilmedi (Rev.10 uygulama raporu, madde 1); bu test
    yalnizca pencerenin kume icinde sayildigini sabitler."""
    k_bas, k_son = config.KESIF_BASI, config.KESIF_SONU
    t = T("2025-08-31 20:00")
    fund = _seri(pd.date_range(T("2025-08-25"), T("2025-08-31 16:00"), freq="8h"))
    a = funding.sinyal_penceresi_ayrintisi(fund, [t], config.BAR_4H, saat=24, kume_baslangic=k_bas,
                                           kume_bitis=k_son, donem_baslangic=DB - pd.Timedelta(days=4000)).iloc[0]
    assert bool(a["kume_icinde"]) and bool(a["hesaplanabilir"])


# --- Zorunluluk ve tek uygulama ---------------------------------------------------------------------


def test_kume_bitis_zorunlu():
    with pytest.raises(TypeError):
        funding.funding_ortalamasi(_sekiz_saatlik(), T0, config.BAR_4H, saat=24, kume_baslangic=None,
                                   donem_baslangic=DB)


def test_vektorel_ve_tekil_ayni():
    fund = _sekiz_saatlik()
    fund = fund.loc[fund["odeme_zamani"] != T("2030-06-12 08:00")].reset_index(drop=True)  # bir eksik
    t_ler = pd.date_range(T("2030-06-02"), T("2030-06-15"), freq="4h")
    a = funding.sinyal_penceresi_ayrintisi(fund, t_ler, config.BAR_4H, saat=24, kume_baslangic=T("2030-06-03"),
                                           kume_bitis=T("2030-06-14 23:59:59"), donem_baslangic=DB)
    tekil = np.array([not np.isnan(_ort(fund, t, kume_baslangic=T("2030-06-03"), kume_bitis=T("2030-06-14 23:59:59")))
                      for t in t_ler])
    assert (a["hesaplanabilir"].to_numpy() == tekil).all()
    assert a["hesaplanabilir"].any() and not a["hesaplanabilir"].all()


def test_ayrinti_oran_okumaz():
    """Hesaplanabilirlik yalnizca zaman ve araliktan: oran sutunu olmayan seriyle de calisir."""
    fund = _sekiz_saatlik()[["odeme_zamani", "aralik_saat"]]
    a = funding.sinyal_penceresi_ayrintisi(fund, [T0], config.BAR_4H, saat=24, kume_baslangic=None, kume_bitis=None,
                                           donem_baslangic=DB)
    assert bool(a["hesaplanabilir"].iloc[0])
    assert int(a["son"].iloc[0]) - int(a["ilk"].iloc[0]) + 1 == 3


def test_bir_dakikadan_yakin_iki_kayit_bozuk_veridir():
    fund = _seri([BAS, BAS + H(8), BAS + H(8) + SN(20), BAS + H(16), KAPANIS])
    with pytest.raises(pencere.ZamanDizisiHatasi):
        _ort(fund)
