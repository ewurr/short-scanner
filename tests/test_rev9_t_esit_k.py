"""On-kayit §4 rev.9 "Donem sonu ve cikis": T >= K (esitlik dahil); ileri kayma yalnizca T < K.

"Hedef cikis ani T, donem kapanisina (K) esit ya da ondan sonraysa pozisyon donem sonuna
ulasmis sayilir; karsilastirma kapanis anlariyla yapilir." Karsilastirma §4 "Zaman
toleransi"na gore: T ile K'nin farki 1 dakikadan kesin kucukse ayni an, yani T >= K. Denetci
bulgusu D-B1'i kapatir. Aga cikmaz; getiri hesaplanmaz.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import funding, pencere

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
DK = pd.Timedelta(minutes=1)
NS = pd.Timedelta(1, "ns")
BAS = T("2025-01-01 00:00")
B = T("2025-01-10 20:00")
K = B + H4
Z = pd.date_range(BAS, B, freq="4h")


def _cikis(giris, ufuk=6, b=B, z=Z):
    return pencere.cikis_bari(z, giris, ufuk, config.BAR_4H, birincil_ufuk=18, donem_bitis=b, kume_bitis=None)


# --- T ile K: tam esitlik ve 1 ns ------------------------------------------------------


def test_t_tam_k_donem_sonu():
    giris = K - 6 * H4  # T = K
    c = _cikis(giris)
    assert c.tur == "donem_sonu" and c.zaman == B and c.fiyat_alani == "close"
    assert c.cikis_ani == K and c.hedef_cikis_ani == K


@pytest.mark.parametrize("b_kaymasi", [NS, -NS], ids=["T=K-1ns", "T=K+1ns"])
def test_t_k_1ns_farkla_ayni_an_donem_sonu(b_kaymasi):
    """B'yi 1 ns kaydirmak K'yi 1 ns kaydirir: T = K - 1 ns ya da K + 1 ns. Fark 1 dakikadan
    kesin kucuk, T ile K ayni an -> T >= K -> donem sonu."""
    giris = K - 6 * H4
    b = B + b_kaymasi
    c = _cikis(giris, b=b)
    assert c.tur == "donem_sonu" and c.zaman == B


@pytest.mark.parametrize("b_kaymasi,tur", [
    (DK - NS, "donem_sonu"),   # T = K - 59.999... s: ayni an
    (DK, "olagan"),            # T = K - 1 dk: T < K, hedef bar (acilisi T - 4h) mevcut
    (DK + NS, "olagan"),
])
def test_t_k_1dk_siniri(b_kaymasi, tur):
    """T < K yalnizca T, K'dan en az 1 dk once ise. B'yi ileri kaydirmak (K = B + 4h) T - K'yi
    kucultur; hedef bar (B barinin kendisi) seride kalir."""
    giris = K - 6 * H4
    b = B + b_kaymasi
    c = _cikis(giris, b=b)
    assert c.tur == tur
    if tur == "olagan":
        assert c.cikis_ani == giris + 6 * H4


def test_t_k_arti_1dk_donem_sonu():
    """T = K + 1 dk: giris bari 1 dk kaymis seri (B bari yerinde)."""
    giris = K - 6 * H4 + DK
    z = pd.DatetimeIndex(sorted((set(Z) - {giris - DK}) | {giris}))
    c = _cikis(giris, z=z)
    assert c.tur == "donem_sonu" and c.zaman == B and c.cikis_ani == K


# --- Ileri kayma yalnizca T < K --------------------------------------------------------


def test_t_esit_k_hedef_bar_seride_olsa_da_ileri_kayma_ya_da_olagan_degil():
    """T = K iken kapanisi T olan bar B barinin kendisidir; donem sonu kurali once uygulanir."""
    c = _cikis(K - 6 * H4)
    assert c.tur == "donem_sonu" and not c.kaydi and c.ileri_kayma == pd.Timedelta(0)


def test_t_kucuk_k_hedef_bar_eksikse_ileri_kayma_b_de_ya_da_once():
    """T < K ve hedef bar eksik: sonraki mevcut donem ici bar B'de ya da once acilir."""
    giris = K - 7 * H4  # T = K - 4h = B; hedef bar B - 4h
    z = Z.drop(B - H4)
    c = _cikis(giris, z=z)
    assert c.tur == "ileri_kayma" and c.zaman == B and c.cikis_ani == B
    assert c.cikis_ani <= B


def test_t_esit_k_b_bari_seride_yoksa_hata():
    """Donem sonu cikisi B barini okur; B bari seride yoksa (bozuk seri) sessiz ileri kayma yok."""
    with pytest.raises(ValueError):
        _cikis(K - 6 * H4, z=Z.drop(B))


def test_tutarlilik_dogrulamasi_t_esit_k_donem_sonunu_kabul_eder():
    c = _cikis(K - 6 * H4)
    pencere.cikis_tutarliligi_dogrula(c)  # hata yok
    bozuk = pencere.CikisSonucu(c.indeks, c.zaman, "close", c.cikis_ani, "donem_sonu", K - DK, pd.Timedelta(0))
    with pytest.raises(ValueError):
        pencere.cikis_tutarliligi_dogrula(bozuk)  # T = K - 1 dk: donem sonu olamaz


# --- Plan ve funding penceresi ------------------------------------------------------------


def _plan(t, ufuk, bar=config.BAR_4H):
    return pencere.pozisyon_plani(Z, t, ufuk, bar, birincil_ufuk=18, kume_baslangic=None, kume_bitis=None,
                                  donem_baslangic=BAS, donem_bitis=B)


def test_t_esit_k_planinda_funding_penceresi_b_de_kapanir():
    """T = K olan pozisyonda donem sonu funding istisnasi uygulanir: pencere B'de kapanir, K'daki
    odeme hesaba girmez (rev.8'de pencere K'da kapaniyordu)."""
    plan = _plan(K - 7 * H4, 6)  # sinyal t, giris t + 4h, T = K
    assert plan.donem_sonu_mu and plan.cikis_ani == K
    assert funding.funding_penceresi_sonu(plan) == B
    kayitlar = pd.date_range(plan.giris, K, freq="4h")
    fr = pd.DataFrame({"odeme_zamani": kayitlar, "aralik_saat": 4.0, "oran": 1e-4, "oran_8h": 1e-4})
    fr.loc[fr["odeme_zamani"] == K, "oran"] = 9.0  # K'daki odeme
    assert funding.pozisyon_fundingi(fr, plan) == pytest.approx(1e-4 * 5)  # giris haric, B dahil, K haric


def test_t_esit_k_1d_izgarasinda_da_donem_sonu():
    """1d izgarasi: B 20:00 ise K ertesi gunun 00:00'i; T = K olan 1d pozisyon donem sonudur."""
    ufuk = 3
    t = K - ufuk * pd.Timedelta(days=1) - pd.Timedelta(days=1)  # giris = t + 1 gun, T = giris + 3 gun
    plan = _plan(t, ufuk, bar=config.BAR_1D)
    assert plan.cikis.hedef_cikis_ani == K and plan.donem_sonu_mu and plan.cikis.zaman == B
