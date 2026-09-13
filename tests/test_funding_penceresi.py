"""Funding penceresi testleri (on-kayit §5 H2.1, F1 kapanis bulgusu 6).

H2'nin "t anina kadarki son 24 saatteki funding ortalamasi" kosulu, mum
pencereleriyle ayni korumalardan gecer: gelecege bakis yok, donem ve kume
baslangici asilmaz, karantina ayina girilmez, eksik odeme varsa deger yok.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import funding, pencere, split

C2_BAS = split.kume_araligi("C2")[0]
SINIRSIZ = dict(kume_baslangic=None, donem_baslangic=None, karantina_aylari=None)


def _funding(bas: str, bitis: str, aralik_saat: int = 8, oran: float = 1e-4) -> pd.DataFrame:
    zaman = pd.date_range(bas, bitis, freq=f"{aralik_saat}h", tz="UTC")
    cerceve = pd.DataFrame({"odeme_zamani": zaman, "aralik_saat": float(aralik_saat), "oran": oran})
    cerceve["oran_8h"] = funding.sekiz_saate_normallestir(cerceve["oran"], cerceve["aralik_saat"])
    return cerceve


def _ortalama(fund, t, **sinirlar):
    sinirlar = {**SINIRSIZ, **sinirlar}
    return funding.funding_ortalamasi(fund, t, config.BAR_4H, saat=24, **sinirlar)


# --- Temel hesap ve pencere sinirlari ----------------------------------------


def test_uc_odemenin_ortalamasi():
    fund = _funding("2021-01-01", "2021-01-10")
    fund.loc[fund["odeme_zamani"] == pd.Timestamp("2021-01-05 00:00", tz="UTC"), "oran_8h"] = 4e-4
    t = pd.Timestamp("2021-01-05 04:00", tz="UTC")  # kapanis 08:00 -> [04 08:00, 05 08:00)
    # Pencerede 04 08:00, 04 16:00, 05 00:00 odemeleri var.
    assert _ortalama(fund, t) == pytest.approx((1e-4 + 1e-4 + 4e-4) / 3)


def test_kapanis_anindaki_ve_sonraki_odeme_kullanilmaz():
    """Gelecege bakis saldirisi: kapanis anindaki ve sonrasindaki odemeyi bozmak sonucu degistirmez."""
    fund = _funding("2021-01-01", "2021-01-10")
    t = pd.Timestamp("2021-01-05 04:00", tz="UTC")
    once = _ortalama(fund, t)

    bozuk = fund.copy()
    bozuk.loc[bozuk["odeme_zamani"] >= t + pd.Timedelta(hours=4), "oran_8h"] = 1.0
    assert _ortalama(bozuk, t) == once


def test_kapanis_bar_turune_gore():
    """1d barda kapanis t + 1 gun."""
    fund = _funding("2021-01-01", "2021-01-10")
    t = pd.Timestamp("2021-01-05 00:00", tz="UTC")  # kapanis 01-06 00:00
    fund.loc[fund["odeme_zamani"] == pd.Timestamp("2021-01-05 16:00", tz="UTC"), "oran_8h"] = 7e-4
    deger = funding.funding_ortalamasi(fund, t, config.BAR_1D, saat=24, **SINIRSIZ)
    assert deger == pytest.approx((1e-4 + 1e-4 + 7e-4) / 3)


def test_dort_saatlik_aralikta_normallestirilmis_oran_kullanilir():
    fund = _funding("2021-01-01", "2021-01-10", aralik_saat=4, oran=1e-4)
    t = pd.Timestamp("2021-01-05 04:00", tz="UTC")
    assert _ortalama(fund, t) == pytest.approx(2e-4)  # 4 saatlik oran x2


def test_birer_ms_kayik_odemeler_tam_sayilir():
    fund = _funding("2021-01-01", "2021-01-10")
    fund["odeme_zamani"] = fund["odeme_zamani"] + pd.Timedelta(milliseconds=1)
    t = pd.Timestamp("2021-01-05 04:00", tz="UTC")
    assert _ortalama(fund, t) == pytest.approx(1e-4)


# --- Tamlik ------------------------------------------------------------------


@pytest.mark.parametrize(
    "eksik",
    ["2021-01-04 08:00", "2021-01-04 16:00", "2021-01-05 00:00"],
    ids=["bastaki", "ortadaki", "sondaki"],
)
def test_penceredeki_bir_odeme_eksikse_nan(eksik):
    fund = _funding("2021-01-01", "2021-01-10")
    fund = fund.loc[fund["odeme_zamani"] != pd.Timestamp(eksik, tz="UTC")].reset_index(drop=True)
    t = pd.Timestamp("2021-01-05 04:00", tz="UTC")
    assert pd.isna(_ortalama(fund, t))


def test_izgaraya_hizali_olmayan_pencerede_bastaki_eksik_odeme():
    """Kapanis 12:00: pencere [dun 12:00, bugun 12:00) -> 16:00, 00:00, 08:00."""
    fund = _funding("2021-01-01", "2021-01-10")
    t = pd.Timestamp("2021-01-05 08:00", tz="UTC")
    assert _ortalama(fund, t) == pytest.approx(1e-4)
    eksik = fund.loc[fund["odeme_zamani"] != pd.Timestamp("2021-01-04 16:00", tz="UTC")]
    assert pd.isna(_ortalama(eksik.reset_index(drop=True), t))


def test_nan_oran_nan_doner():
    fund = _funding("2021-01-01", "2021-01-10")
    fund.loc[fund["odeme_zamani"] == pd.Timestamp("2021-01-04 16:00", tz="UTC"), "oran_8h"] = float("nan")
    assert pd.isna(_ortalama(fund, pd.Timestamp("2021-01-05 04:00", tz="UTC")))


def test_penceresi_bos_nan_doner():
    fund = _funding("2021-01-01", "2021-01-02")
    assert pd.isna(_ortalama(fund, pd.Timestamp("2021-03-01 04:00", tz="UTC")))


def test_bir_dakikadan_yakin_iki_kayit_bozuk_veridir():
    fund = _funding("2021-01-01", "2021-01-10")
    kopya = fund.iloc[[10]].copy()
    kopya["odeme_zamani"] = kopya["odeme_zamani"] + pd.Timedelta(milliseconds=1)
    bozuk = pd.concat([fund, kopya]).sort_values("odeme_zamani", ignore_index=True)
    with pytest.raises(pencere.ZamanDizisiHatasi):
        _ortalama(bozuk, pd.Timestamp("2021-01-05 04:00", tz="UTC"))


# --- Donem, kume, karantina --------------------------------------------------


def test_kume_oncesi_odeme_mevcutken_kume_basini_asan_pencere_nan():
    fund = _funding("2025-08-01", "2025-09-30")
    t = C2_BAS + pd.Timedelta(hours=8)  # kapanis 12:00 -> pencere 08-31 12:00'den baslar
    assert not pd.isna(_ortalama(fund, t))
    assert pd.isna(_ortalama(fund, t, kume_baslangic=C2_BAS))

    ilk_gecerli = C2_BAS + pd.Timedelta(hours=20)  # kapanis 09-02 00:00 -> pencere tam C2 basinda
    assert not pd.isna(_ortalama(fund, ilk_gecerli, kume_baslangic=C2_BAS))
    assert pd.isna(_ortalama(fund, ilk_gecerli - pd.Timedelta(hours=4), kume_baslangic=C2_BAS))


def test_kume_oncesi_odemeleri_bozmak_kume_ici_sonucu_degistirmez():
    fund = _funding("2025-08-01", "2025-10-31")
    bozuk = fund.copy()
    bozuk.loc[bozuk["odeme_zamani"] < C2_BAS, "oran_8h"] = 1.0
    for t in pd.date_range(C2_BAS, C2_BAS + pd.Timedelta(days=3), freq="4h"):
        once = _ortalama(fund, t, kume_baslangic=C2_BAS)
        sonra = _ortalama(bozuk, t, kume_baslangic=C2_BAS)
        assert (pd.isna(once) and pd.isna(sonra)) or once == sonra, t


def test_donem_basini_asan_pencere_nan():
    fund = _funding("2021-01-01", "2021-03-01")
    donem_bas = pd.Timestamp("2021-02-01", tz="UTC")
    assert pd.isna(_ortalama(fund, pd.Timestamp("2021-02-01 12:00", tz="UTC"), donem_baslangic=donem_bas))
    assert not pd.isna(_ortalama(fund, pd.Timestamp("2021-02-02 20:00", tz="UTC"), donem_baslangic=donem_bas))


def test_karantina_ayina_dokunan_pencere_nan():
    fund = _funding("2021-05-01", "2021-07-31")
    t = pd.Timestamp("2021-07-01 04:00", tz="UTC")  # pencere 06-30 08:00 -> 07-01 08:00
    assert not pd.isna(_ortalama(fund, t))
    assert pd.isna(_ortalama(fund, t, karantina_aylari=["2021-06"]))
    assert pd.isna(_ortalama(fund, t, karantina_aylari=["2021-07"]))
    assert not pd.isna(_ortalama(fund, t, karantina_aylari=["2021-05"]))


# --- Zorunluluk --------------------------------------------------------------


@pytest.mark.parametrize("eksik", ["kume_baslangic", "donem_baslangic", "karantina_aylari", "saat"])
def test_sinir_ya_da_saat_unutulursa_hata(eksik):
    fund = _funding("2021-01-01", "2021-01-10")
    parametreler = {**SINIRSIZ, "saat": 24}
    del parametreler[eksik]
    with pytest.raises(TypeError):
        funding.funding_ortalamasi(fund, pd.Timestamp("2021-01-05 04:00", tz="UTC"), config.BAR_4H, **parametreler)


def test_saat_dilimsiz_t_reddedilir():
    fund = _funding("2021-01-01", "2021-01-10")
    with pytest.raises(TypeError):
        _ortalama(fund, pd.Timestamp("2021-01-05 04:00"))
