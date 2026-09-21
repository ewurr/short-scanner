"""On-kayit §4 rev.8 "Fiyat okuma tabani", "Donem sonu ve cikis", delist cumlesi;
§2 "Ufuk", "Ileri kaymanin olcusu". Aga cikmaz.

- Giris ani = t barinin kapanisi; P0 = acilisi giris anina esit donem ici 4h bar.
- T = giris ani + h x adim. Once T > K: donem sonu, B'deki barin kapanisi, cikis ani K.
- T <= K: kapanisi T olan donem ici 4h bar; yoksa acilisi T'ye esit ya da sonra olan
  ilk donem ici 4h barin acilisi (ileri kayma, sinir dahil).
- Her plan bir cikis turu tasir; reddedilen her olay bir ret gerekcesi tasir.

Zaman karsilastirmalari §4 "Zaman toleransi"na gore: 1 dakikadan kucuk fark ayni an.
Bu yuzden "T = K + 1 ns" K ile ayni an (T > K degil) ve "kayma sinirinin 1 ns
otesi" sinirla ayni an (kabul); ret tam 1 dakikada baslar.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import klines, pencere
from data.donem import Donem

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
G = pd.Timedelta(days=1)
DK = pd.Timedelta(minutes=1)
NS = pd.Timedelta(1, "ns")


def _plan(z, t, ufuk, bar, birincil, bas, b, kume_bitis=None):
    return pencere.pozisyon_plani(z, t, ufuk, bar, birincil_ufuk=birincil, kume_baslangic=None,
                                  kume_bitis=kume_bitis, donem_baslangic=bas, donem_bitis=b)


# --- 1d: t+1 gunu kismi son gun ------------------------------------------------------


def test_1d_t_arti_bir_kismi_son_gun_olay_olusur():
    """B = 04-14 08:00: 04-14 kismi son gun, 1d serisinde yok. t = 04-13 (tam gun);
    giris 04-14 00:00 4h barinda (donem ici). Rev.7'de t+1 gunu seride olmadigi icin olay
    olusmuyordu; rev.8'de olusur ve donem sonunda cikar."""
    bas, b = T("2025-04-01 00:00"), T("2025-04-14 08:00")
    z = pd.date_range(bas, b, freq="4h")
    gunler = klines.gunluge_cevir(pd.DataFrame({
        "open_time": z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0,
        "close_time": z, "quote_volume": 1.0, "count": 1, "taker_buy_volume": 0.0, "taker_buy_quote_volume": 0.0,
    }), donemler=[Donem(bas, b, len(z), len(z))])["open_time"]
    assert T("2025-04-14") not in set(gunler)  # kismi son gun seride yok
    plan = _plan(z, T("2025-04-13"), 14, config.BAR_1D, 14, bas, b)
    assert plan.giris == T("2025-04-14 00:00")
    assert plan.cikis_turu == "donem_sonu" and plan.cikis.zaman == b and plan.cikis_ani == b + H4


# --- T ile K karsilastirmasi ---------------------------------------------------------


def test_t_tam_k_ise_donem_sonu_degil_olagan():
    z = pd.date_range(T("2025-01-01"), periods=40, freq="4h")
    b = z[20]
    giris = b + H4 - 6 * H4  # T = giris + 24h = K
    z = z[z <= b]
    c = pencere.cikis_bari(z, giris, 6, config.BAR_4H, birincil_ufuk=18, donem_bitis=b, kume_bitis=None)
    assert c.tur == "olagan" and c.zaman == b and c.cikis_ani == b + H4


def test_t_k_arti_1ns_k_ile_ayni_an_olagan():
    """T = K + 1 ns: fark 1 dakikadan kucuk, ayni an; T > K degil (olagan, hedef bar B)."""
    z = pd.date_range(T("2025-01-01"), periods=40, freq="4h")
    b = z[20]
    giris = b + H4 - 6 * H4 + NS  # T = giris + 24h = K + 1 ns; giris bari ayni an (1 ns)
    c = pencere.cikis_bari(z[z <= b], giris, 6, config.BAR_4H, birincil_ufuk=18, donem_bitis=b, kume_bitis=None)
    assert c.tur == "olagan" and c.zaman == b and c.cikis_ani == b + H4


def test_t_k_arti_1dk_donem_sonu():
    z = pd.date_range(T("2025-01-01"), periods=40, freq="4h")
    b = z[20]
    giris = b + H4 - 6 * H4 + DK  # T = K + 1 dk; giris bari 1 dk kaymis (ayni an degil)
    z_dk = pd.DatetimeIndex(sorted((set(z) - {giris - DK}) | {giris}))
    c = pencere.cikis_bari(z_dk[z_dk <= b], giris, 6, config.BAR_4H, birincil_ufuk=18, donem_bitis=b, kume_bitis=None)
    assert c.tur == "donem_sonu" and c.zaman == b and c.cikis_ani == b + H4


def test_t_k_den_bir_bar_sonra_donem_sonu_ileri_kaymadan_once():
    """Hedef bar eksik ve T > K: ileri kayma degil donem sonu (once T > K denetlenir)."""
    z = pd.date_range(T("2025-01-01"), periods=40, freq="4h")
    b = z[20]
    c = pencere.cikis_bari(z[z <= b], z[16], 6, config.BAR_4H, birincil_ufuk=18, donem_bitis=b, kume_bitis=None)
    assert c.hedef_cikis_ani == b + 2 * H4 and c.tur == "donem_sonu" and c.cikis_ani == b + H4


# --- Ileri kayma ------------------------------------------------------------------------


def test_hedef_eksik_sonraki_bar_b_de():
    z = pd.date_range(T("2025-01-01"), periods=40, freq="4h")
    b = z[20]
    giris = z[10]  # T = z[16]; hedef bar (kapanisi T) z[15]
    eksik = z[(z <= z[14]) | (z == b)]  # z[15..19] eksik, sonraki bar B
    c = pencere.cikis_bari(eksik, giris, 6, config.BAR_4H, birincil_ufuk=18, donem_bitis=b, kume_bitis=None)
    assert c.tur == "ileri_kayma" and c.zaman == b and c.cikis_ani == b and c.fiyat_alani == "open"
    assert c.ileri_kayma == b - z[15]


@pytest.mark.parametrize("fazla,kabul", [(pd.Timedelta(0), True), (NS, True), (DK - NS, True), (DK, False)])
def test_kayma_siniri(fazla, kabul):
    """Sinir dahil; sinirdan 1 dakikadan az otesi ayni an (kabul), tam 1 dk otesi ret."""
    z = pd.date_range(T("2025-01-01"), periods=200, freq="4h")
    giris = z[10]
    hedef_acilis = pencere.cikis_hedefi(giris, 6, config.BAR_4H) - H4
    sonraki = hedef_acilis + 18 * H4 + fazla
    seri = pd.DatetimeIndex(sorted([x for x in z if x < hedef_acilis] + [sonraki] + [x for x in z if x > sonraki]))
    ortak = dict(birincil_ufuk=18, donem_bitis=seri[-1], kume_bitis=None)
    if kabul:
        c = pencere.cikis_bari(seri, giris, 6, config.BAR_4H, **ortak)
        assert c.tur == "ileri_kayma" and c.zaman == sonraki
    else:
        with pytest.raises(pencere.IleriKaymaSiniriHatasi) as hata:
            pencere.cikis_bari(seri, giris, 6, config.BAR_4H, **ortak)
        assert pencere.ret_gerekcesi(hata.value) == "ileri_kayma_siniri"


# --- Delist ------------------------------------------------------------------------------


def test_delist_donem_sonudur():
    z = pd.date_range(T("2025-01-01"), periods=30, freq="4h")  # seri delistle biter
    plan = _plan(z, z[20], 18, config.BAR_4H, 18, z[0], z[-1])
    assert plan.donem_sonu_mu and plan.cikis.zaman == z[-1] and plan.cikis_ani == z[-1] + H4


# --- Tam gunlerde 1d sonucu open[t+1] / close[t+h] ile ayni ---------------------------


def test_tam_gunlerde_1d_fiyatlari_open_t1_close_th_ile_ayni():
    z = pd.date_range(T("2025-01-01"), T("2025-02-28 20:00"), freq="4h")
    fiyat = pd.Series(range(len(z)), index=z, dtype=float)
    m = pd.DataFrame({"open_time": z, "open": fiyat.values + 0.1, "high": fiyat.values + 0.9,
                      "low": fiyat.values, "close": fiyat.values + 0.5, "volume": 1.0, "close_time": z,
                      "quote_volume": 1.0, "count": 1, "taker_buy_volume": 0.0, "taker_buy_quote_volume": 0.0})
    gunluk = klines.gunluge_cevir(m, donemler=[Donem(z[0], z[-1], len(z), len(z))]).set_index("open_time")
    dort = m.set_index("open_time")
    for t, h in ((T("2025-01-05"), 14), (T("2025-01-20"), 7), (T("2025-01-10"), 30)):
        plan = _plan(z, t, h, config.BAR_1D, 14, z[0], z[-1])
        assert plan.cikis_turu == "olagan"
        p0 = dort.loc[plan.giris, "open"]
        p1 = dort.loc[plan.cikis.zaman, plan.cikis.fiyat_alani]
        assert p0 == gunluk.loc[t + G, "open"]
        assert p1 == gunluk.loc[t + h * G, "close"]


# --- Ret gerekceleri ve cikis turleri -------------------------------------------------------


def test_ret_gerekceleri():
    assert pencere.ret_gerekcesi(pencere.KumeSiniriHatasi("x")) == "kume_siniri"
    assert pencere.ret_gerekcesi(pencere.GirisBariYok("x")) == "giris_bari_yok"
    assert pencere.ret_gerekcesi(pencere.IleriKaymaSiniriHatasi("x")) == "ileri_kayma_siniri"
    with pytest.raises(TypeError):
        pencere.ret_gerekcesi(pencere.DonemDisiSinyal("x"))
    assert set(pencere.CIKIS_TURLERI) == {"olagan", "ileri_kayma", "donem_sonu"}


def test_verinin_sonu_donem_sonu_degil_c2_de_olusmaz():
    """Son veri bari (2026-08-31 20:00) C2 sonundan once acilir ve 1 sn sonra kapanir;
    verinin sonuna uzanan her ufuk C2 kume sonunu asar ve olusmaz (§4 "Donem sonu ve cikis")."""
    c2_bas, c2_son = pd.Timestamp(config.C2_BASI), pd.Timestamp(config.C2_SONU)
    z = pd.date_range(T("2026-07-01"), T("2026-08-31 20:00"), freq="4h")
    with pytest.raises(pencere.KumeSiniriHatasi):
        pencere.pozisyon_plani(z, T("2026-08-30 20:00"), 18, config.BAR_4H, birincil_ufuk=18, kume_baslangic=c2_bas,
                               kume_bitis=c2_son, donem_baslangic=z[0], donem_bitis=z[-1])
