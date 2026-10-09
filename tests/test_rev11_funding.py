"""Rev.11 uygulamasi madde 8: funding sinyal penceresinde kume sonu kaydi ve sonlu olmayan oran;
pozisyon funding'inde gecerli oran kosulu (on-kayit §4, rev.11).

On-kayit §4 "Funding sinyal penceresinin tamligi" (rev.11): "Pencere sonuna denk gelen kayit
yalnizca ayni kumeye aitse ortalamaya girer: sonraki kumenin ilk kaydi, tolerans payiyla pencere
sonuna denk gelse bile okunmaz ve o barda deger hesaplanmaz. ... Penceredeki kayitlarin
oranlarindan biri sayi degilse ya da sonlu degilse ortalama hesaplanmaz. Capa ve zincir kosullari
saglansa bile pencerenin yari acik araliginda hic kayit yoksa deger hesaplanmaz."

On-kayit §4 "Funding tamligi" / "Gecerli oran" (rev.11): "Pozisyonun funding penceresine giren
her kaydin oran degeri sonlu bir sayi olmalidir; NaN, +sonsuz ya da -sonsuz oran tasiyan
pozisyonun funding'i tam degildir ve pozisyon olusmaz."

Oranlar sentetiktir ve hicbir deger raporlanmaz; testler yalnizca hesaplanabilirlik ve tamlik
okur. Aga cikmaz.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

import config
from data import funding, pencere

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H = lambda n: pd.Timedelta(hours=n)  # noqa: E731
SAAT = config.H2_FUNDING_PENCERESI_SAAT

KESIF_SON = pd.Timestamp(config.KESIF_SONU)   # 2025-08-31 23:59:59
SON_BAR = T("2025-08-31 20:00")               # KESIF'in son 4h bari; kapanisi 2025-09-01 00:00
C2_BAS = pd.Timestamp(config.C2_BASI)         # 2025-09-01 00:00


def _fund(zamanlar, aralik=8.0, oran=0.0005):
    z = pd.DatetimeIndex(zamanlar)
    return pd.DataFrame({"odeme_zamani": z, "aralik_saat": float(aralik),
                         "oran": float(oran), "oran_8h": float(oran)})


# --- 1. Kume sonundaki kayit (on-kayit §4 rev.11) ---------------------------------------------


def test_kesifin_son_bari_kume_sonu_kaydi_kuraliyla_duser():
    """KESIF'in son barinin (2025-08-31 20:00) penceresi 2025-09-01 00:00'da biter; o ana denk
    gelen kayit C2'nin ilk kaydidir. Rev.11: okunmaz, deger hesaplanmaz."""
    fr = _fund(pd.date_range(T("2025-08-25"), C2_BAS, freq="8h"))
    a = funding.sinyal_penceresi_ayrintisi(fr, [SON_BAR], config.BAR_4H, saat=SAAT,
                                           kume_baslangic=pd.Timestamp(config.KESIF_BASI),
                                           kume_bitis=KESIF_SON,
                                           donem_baslangic=T("2025-01-01")).iloc[0]
    assert not bool(a["kume_sonu_kaydi_disarida"])
    assert not bool(a["hesaplanabilir"])
    # Rev.10'un kosulu (toleransli) hala saglaniyor: dusuren kural yeni olandir.
    assert bool(a["kume_icinde"]), "kume_icinde toleransli kalir; son bari o dusurmez"


def test_kume_sonu_kurali_kayit_olmasa_da_uygulanir():
    """Kural kaydin VARLIGINA bakmaz: pencere sonu kume sonundan sonraysa, o ana denk gelecek
    kayit sonraki kumenin kaydi olurdu. Seri kumeye kesilmis (C2 kaydi yok) olsa bile bar duser;
    boylece kural verinin kesilmis olmasina dayanmaz (on-kayit §3)."""
    fr = _fund(pd.date_range(T("2025-08-25"), KESIF_SON, freq="8h"))
    assert fr["odeme_zamani"].max() < C2_BAS
    a = funding.sinyal_penceresi_ayrintisi(fr, [SON_BAR], config.BAR_4H, saat=SAAT,
                                           kume_baslangic=pd.Timestamp(config.KESIF_BASI),
                                           kume_bitis=KESIF_SON,
                                           donem_baslangic=T("2025-01-01")).iloc[0]
    assert not bool(a["kume_sonu_kaydi_disarida"]) and not bool(a["hesaplanabilir"])


def test_bir_onceki_bar_dusmez():
    """Sinir durumu: 2025-08-31 16:00 barinin penceresi 20:00'da biter; kume sonundan once."""
    fr = _fund(pd.date_range(T("2025-08-25"), C2_BAS, freq="8h"))
    a = funding.sinyal_penceresi_ayrintisi(fr, [SON_BAR - H(4)], config.BAR_4H, saat=SAAT,
                                           kume_baslangic=pd.Timestamp(config.KESIF_BASI),
                                           kume_bitis=KESIF_SON,
                                           donem_baslangic=T("2025-01-01")).iloc[0]
    assert bool(a["kume_sonu_kaydi_disarida"]) and bool(a["hesaplanabilir"])


def test_c2nin_son_bari_da_duser():
    """Kural kumeye ozgu degil: C2'nin son bari (2026-08-31 20:00) da ayni yoldan duser."""
    c2_son_bar = T("2026-08-31 20:00")
    fr = _fund(pd.date_range(T("2026-08-25"), T("2026-09-01"), freq="8h"))
    a = funding.sinyal_penceresi_ayrintisi(fr, [c2_son_bar], config.BAR_4H, saat=SAAT,
                                           kume_baslangic=pd.Timestamp(config.C2_BASI),
                                           kume_bitis=pd.Timestamp(config.C2_SONU),
                                           donem_baslangic=T("2026-01-01")).iloc[0]
    assert not bool(a["hesaplanabilir"])


def test_kume_sonu_verilmemisse_kural_uygulanmaz():
    """`kume_bitis=None` acikca "kume siniri yok" demektir; kural uygulanmaz."""
    fr = _fund(pd.date_range(T("2025-08-25"), C2_BAS, freq="8h"))
    a = funding.sinyal_penceresi_ayrintisi(fr, [SON_BAR], config.BAR_4H, saat=SAAT,
                                           kume_baslangic=None, kume_bitis=None,
                                           donem_baslangic=T("2025-01-01")).iloc[0]
    assert bool(a["kume_sonu_kaydi_disarida"]) and bool(a["hesaplanabilir"])


def test_funding_ortalamasi_son_barda_nan_doner():
    fr = _fund(pd.date_range(T("2025-08-25"), C2_BAS, freq="8h"))
    assert math.isnan(funding.funding_ortalamasi(
        fr, SON_BAR, config.BAR_4H, saat=SAAT, kume_baslangic=pd.Timestamp(config.KESIF_BASI),
        kume_bitis=KESIF_SON, donem_baslangic=T("2025-01-01")))
    assert not math.isnan(funding.funding_ortalamasi(
        fr, SON_BAR - H(4), config.BAR_4H, saat=SAAT, kume_baslangic=pd.Timestamp(config.KESIF_BASI),
        kume_bitis=KESIF_SON, donem_baslangic=T("2025-01-01")))


# --- 2. Sinyal penceresinde sonlu olmayan oran (on-kayit §4 rev.11) ---------------------------


@pytest.mark.parametrize("bozuk", [float("nan"), float("inf"), -float("inf")])
def test_penceredeki_sonlu_olmayan_oran_ortalamayi_dusurur(bozuk):
    t = T("2025-03-10 04:00")
    fr = _fund(pd.date_range(T("2025-03-01"), T("2025-03-11"), freq="8h"))
    pencere_ici = (fr["odeme_zamani"] > t + H(4) - H(SAAT)) & (fr["odeme_zamani"] <= t + H(4))
    assert int(pencere_ici.sum()) >= 1
    fr.loc[fr.index[pencere_ici][0], "oran_8h"] = bozuk
    assert math.isnan(funding.funding_ortalamasi(
        fr, t, config.BAR_4H, saat=SAAT, kume_baslangic=None, kume_bitis=None,
        donem_baslangic=T("2025-01-01")))


def test_pencere_disindaki_sonlu_olmayan_oran_etkilemez():
    """Sinir durumu: pencerenin DISINDAKI bozuk oran ortalamayi dusurmez."""
    t = T("2025-03-10 04:00")
    fr = _fund(pd.date_range(T("2025-03-01"), T("2025-03-11"), freq="8h"))
    disari = fr.index[fr["odeme_zamani"] < t + H(4) - H(SAAT)][-1]
    fr.loc[disari, "oran_8h"] = float("inf")
    assert not math.isnan(funding.funding_ortalamasi(
        fr, t, config.BAR_4H, saat=SAAT, kume_baslangic=None, kume_bitis=None,
        donem_baslangic=T("2025-01-01")))


def test_yari_acik_aralikta_hic_kayit_yoksa_hesaplanmaz():
    """On-kayit §4 rev.11: "Capa ve zincir kosullari saglansa bile pencerenin yari acik
    araliginda hic kayit yoksa deger hesaplanmaz." """
    t = T("2025-03-10 04:00")
    # 24 saatlik aralikli kayitlar: pencere basina tam denk gelen kayit (yari acik: girmez) ve
    # oncesi; (bas, kapanis] araliginda kayit yok.
    fr = _fund([T("2025-03-08 08:00"), T("2025-03-09 08:00")], aralik=24.0)
    a = funding.sinyal_penceresi_ayrintisi(fr, [t], config.BAR_4H, saat=SAAT, kume_baslangic=None,
                                           kume_bitis=None, donem_baslangic=T("2025-01-01")).iloc[0]
    assert not bool(a["kayit_var"]) and not bool(a["hesaplanabilir"])


# --- 3. Pozisyon funding'inde gecerli oran (on-kayit §4 rev.11) --------------------------------


def _plan(giris, cikis, donem_bas=T("2025-01-01"), donem_son=T("2025-06-30 20:00")):
    z = pd.date_range(T("2025-03-01"), T("2025-06-30 20:00"), freq="4h")
    ufuk = int((cikis - giris) / H(4))
    return pencere.pozisyon_plani(z, giris - H(4), config.BIRINCIL_UFUK[config.BAR_4H], config.BAR_4H,
                                  birincil_ufuk=config.BIRINCIL_UFUK[config.BAR_4H],
                                  kume_baslangic=pd.Timestamp(config.KESIF_BASI),
                                  kume_bitis=KESIF_SON, donem_baslangic=donem_bas, donem_bitis=donem_son)


@pytest.mark.parametrize("bozuk", [float("nan"), float("inf"), -float("inf")])
def test_odeme_penceresindeki_sonlu_olmayan_oran_tamligi_bozar(bozuk):
    plan = _plan(T("2025-03-10 08:00"), T("2025-03-13 08:00"))
    fr = _fund(pd.date_range(T("2025-03-01"), T("2025-03-20"), freq="8h"))
    pencere_sonu = funding.funding_penceresi_sonu(plan)
    odeme = fr.index[(fr["odeme_zamani"] > plan.giris) & (fr["odeme_zamani"] <= pencere_sonu)]
    assert len(odeme) >= 2
    assert bool(funding.pozisyon_funding_tam_mi(fr, plan)), "bozulmadan once tam olmali"
    fr.loc[odeme[1], "oran"] = bozuk
    ayrinti = funding.pozisyon_funding_ayrintisi(fr, plan)
    assert not bool(ayrinti["oran_gecerli"]) and not bool(ayrinti["tam"])
    # Diger tamlik kosullari bozulmadi: dusuren kural yalnizca gecerli orandir.
    assert bool(ayrinti["capa_var"]) and bool(ayrinti["zincir_tam"]) and bool(ayrinti["son_tam"])
    assert math.isnan(funding._plan_fundingi(fr, plan))


def test_capanin_orani_denetlenmez():
    """Belgeli sinir: capanin orani toplama girmez (giris anindaki odeme haric, on-kayit §4), bu
    yuzden "pencereye giren kayit" olcutu capayi kapsamaz. Rapora acik nokta olarak yazildi."""
    plan = _plan(T("2025-03-10 08:00"), T("2025-03-13 08:00"))
    fr = _fund(pd.date_range(T("2025-03-01"), T("2025-03-20"), freq="8h"))
    capa = fr.index[fr["odeme_zamani"] <= plan.giris][-1]
    fr.loc[capa, "oran"] = float("inf")
    ayrinti = funding.pozisyon_funding_ayrintisi(fr, plan)
    assert bool(ayrinti["oran_gecerli"]) and bool(ayrinti["tam"])
    assert math.isfinite(funding._plan_fundingi(fr, plan))


def test_pencere_sonundan_sonraki_bozuk_oran_etkilemez():
    plan = _plan(T("2025-03-10 08:00"), T("2025-03-13 08:00"))
    fr = _fund(pd.date_range(T("2025-03-01"), T("2025-03-20"), freq="8h"))
    pencere_sonu = funding.funding_penceresi_sonu(plan)
    sonra = fr.index[fr["odeme_zamani"] > pencere_sonu][0]
    fr.loc[sonra, "oran"] = float("nan")
    assert bool(funding.pozisyon_funding_tam_mi(fr, plan))


def test_oran_sutunu_olmayan_cerceve_kosuldan_gecer():
    """Olcum betikleri yalnizca zaman ve aralik tasiyan cerceve verebilir; denetlenecek oran
    yoktur ve kural o cerceveleri dusurmez."""
    plan = _plan(T("2025-03-10 08:00"), T("2025-03-13 08:00"))
    z = pd.date_range(T("2025-03-01"), T("2025-03-20"), freq="8h")
    fr = pd.DataFrame({"odeme_zamani": z, "aralik_saat": 8.0})
    assert bool(funding.pozisyon_funding_tam_mi(fr, plan))


def test_gecerli_oran_tamlik_kosullarinda():
    assert "oran_gecerli" in funding.TAMLIK_KOSULLARI


def test_sinyal_penceresi_sutunlarinda_kume_sonu_kaydi():
    assert "kume_sonu_kaydi_disarida" in funding.SINYAL_PENCERESI_SUTUNLARI
