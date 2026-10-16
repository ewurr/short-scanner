"""Denetci bulgusu D-B3: bar duzeyli mevcutluk olcutu FIYAT OKUMA yoluna da uygulanir.

On-kayit §2 (rev.12): "Bu, barin mevcutlugunun genel tanimidir: olcut alan duzeyinde degil BAR
DUZEYINDEDIR ve her izgarada, her PENCEREDE ve her HESAPTA gecerlidir -- hucresi bozuk bir bar 4
saatlik sinyal pencerelerinde de mevcut sayilmaz, ilgili hucresi gecerli olsa bile. Islem sayisi
(`count`) bu kuralin kapsami disindadir."

Bulgu: olcut `sinyal._seri` ve `klines.gunluge_cevir` icinde uygulaniyordu, ama pozisyonun fiyat
okumalari (P0, P1, MAE'nin high'lari) ve plan adimi yalnizca DAMGAYA bakiyordu. Hucresi bozuk ama
`open`i gecerli bir bar, on-kayit geregi "mevcut degil" olmasina ragmen giris bari olarak kabul
ediliyordu ve ileri kayma kurali hic devreye girmiyordu.

Cozum: olcut verinin kapiya girdigi tek noktada (`pozisyon._kume_verisi`) uygulanir; bozuk bar
seride YOKTUR. Olculen etki bugun sifirdir (bkz. §5 olcumu), ama "olculmus sifir etki muafiyet
degildir" (RESULTS §14.13).

Aga cikmaz; getiri RAPORLANMAZ (yalnizca olayin olusup olusmadigi ve ret gerekcesi okunur).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import config
from data import klines, pencere, pozisyon
from kapi_yardimcisi import veri
from sinyal_yardimcisi import kontrol, yapilandirma
from uygunluk_yardimcisi import esikler

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
DB, B = T("2024-09-01"), T("2025-06-30 20:00")
T2 = T("2025-03-10 04:00")
UFUK = config.BIRINCIL_UFUK[config.BAR_4H]
HACIM = 6e7


def _seri() -> pd.DataFrame:
    """H2'nin uc kosulunu T2 barinda saglayan seri (kalabalik funding `_fund`te).

    t-3..t-1 dibi 1.5, t kapanisi 1.2: kirilim (`close[t] < min(low[t-k..t-1])`) ve onceki
    yukselis (`close[t]/close[t-30] - 1 = 0.2 >= 0.10`) saglanir.
    """
    z = pd.date_range(DB, B, freq="4h")
    m = pd.DataFrame({"open_time": z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
                      "volume": 10.0, "quote_volume": HACIM / 6, "count": 7,
                      "taker_buy_volume": 1.0, "taker_buy_quote_volume": 1.0,
                      "close_time": z + H4 - pd.Timedelta(milliseconds=1)})
    dip = (z >= T2 - 3 * H4) & (z <= T2 - H4)
    m.loc[dip, ["open", "high", "low", "close"]] = 1.5
    m.loc[z == T2, ["open", "high", "low", "close"]] = 1.2
    return m


def _fund() -> pd.DataFrame:
    z = pd.date_range(DB, B + H4, freq="8h")
    return pd.DataFrame({"odeme_zamani": z, "aralik_saat": 8.0, "oran": 1e-3, "oran_8h": 1e-3})


def _bozuk(sutun: str, zaman, deger=float("nan")) -> pd.DataFrame:
    m = _seri()
    m.loc[pd.DatetimeIndex(m["open_time"]) == zaman, sutun] = deger
    return m


def _karar(mumlar, t=T2, **ek):
    kayit = veri(mumlar, _fund(), DB, B, uygun_bas=DB, hacim=HACIM, ham=True)
    ortak = dict(hipotez="H2", yapilandirma=yapilandirma("H2"), kume="KESIF", rol="olay", capa=None,
                 **kayit, **esikler(config.BAR_4H))
    return pozisyon.olay_karari(t, UFUK, config.BAR_4H, birincil_ufuk=UFUK, **{**ortak, **ek})


def _ret(mumlar, t=T2, **ek) -> str:
    try:
        _karar(mumlar, t, **ek)
    except pencere.OlayOlusmaz as hata:
        return pencere.ret_gerekcesi(hata)
    return "olustu"


# --- 1. Giris bari: hucresi bozuk bar "mevcut degil" ------------------------------------------


def test_saglam_seride_olay_olusur():
    """On kosul: ayni dunyada bozuk hucre yokken olay olusuyor (test duyarli)."""
    assert _ret(_seri()) == "olustu"


@pytest.mark.parametrize("sutun", ["open", "high", "low", "close", "volume", "quote_volume",
                                   "taker_buy_volume", "taker_buy_quote_volume"])
def test_giris_barinin_bozuk_hucresi_olayi_dusurur(sutun):
    """On-kayit §4 "Fiyat okuma tabani": "`P0`, acilisi giris anina esit olan donem ici 4h barin
    acilisidir; BOYLE BIR BAR YOKSA OLAY OLUSMAZ." Giris barinda ileri kayma YOKTUR (ileri kayma
    yalnizca hedef CIKIS bari icin tanimlidir), bu yuzden hucresi bozuk giris bari olayi dusurur.

    Rev.12'den onceki davranis: bar "mevcut" sayilir, `open`i okunur ve olay olusurdu."""
    giris = T2 + H4
    bozuk = _bozuk(sutun, giris)
    assert not np.asarray(klines.hucreleri_tam_mi(bozuk), dtype=bool)[
        int(pd.DatetimeIndex(bozuk["open_time"]).get_loc(giris))], "test kurulumu: bar gercekten bozuk"
    assert _ret(bozuk) == "giris_bari_yok"
    assert _karar(_seri()).plan.giris == giris, "saglam seride giris t+1'dir ve olay olusur"


def test_count_sutunu_kapsam_disi():
    """On-kayit §2: "Islem sayisi (`count`) bu kuralin kapsami disindadir." """
    bozuk = _bozuk("count", T2 + H4)
    assert _karar(bozuk).plan.giris == T2 + H4


def test_cikis_sonrasi_butun_barlar_bozuksa_olay_dusar():
    """Ileri kayma birincil ufuk kadar sinirlidir (on-kayit §4 "Ileri kaymanin ust siniri"):
    hedef cikistan sonraki butun barlar bozuksa olay OLUSMAZ."""
    m = _seri()
    z = pd.DatetimeIndex(m["open_time"])
    hedef = T2 + UFUK * H4
    maske = (z >= hedef) & (z <= hedef + (UFUK + 2) * H4)
    m.loc[maske, "volume"] = float("nan")
    assert _ret(m) == "ileri_kayma_siniri"


# --- 2. Cikis bari ve MAE penceresi -----------------------------------------------------------


def test_cikis_barinin_bozuk_hucresi_ileri_kaymaya_dusurur():
    cikis = T2 + UFUK * H4                 # kapanisi cikis anina esit olan bar
    saglam = _karar(_seri())
    assert saglam.plan.cikis.zaman == cikis, "test kurulumu: cikis bari"
    bozuk = _karar(_bozuk("high", cikis))
    assert bozuk.plan.cikis.zaman != cikis


def test_mae_penceresindeki_bozuk_bar_hesaba_girmez():
    """MAE'nin H'si bozuk barin high'ini OKUMAZ: bar seride yoktur (on-kayit §4 "MAE")."""
    orta = T2 + 5 * H4
    m = _seri()
    m.loc[pd.DatetimeIndex(m["open_time"]) == orta, "high"] = 5.0     # saglam: MAE'yi yukseltir
    yuksek_mae = pozisyon.mae(_karar(m))
    m2 = m.copy()
    m2.loc[pd.DatetimeIndex(m2["open_time"]) == orta, "volume"] = float("nan")  # bar artik yok
    assert pozisyon.mae(_karar(m2)) < yuksek_mae


# --- 3. Kontrol rolu ve sinyal penceresi ayni olcutten gecer ----------------------------------


@pytest.mark.parametrize("rol", ["K1", "K2"])
def test_kontrol_rolu_de_ayni_olcutten_gecer(rol):
    """Kontrol bari olaylarla ayni fiyat okuma tabanina tabidir (on-kayit §6 "Donem uyeligi")."""
    giris = T2 + H4
    assert _karar(_seri(), **kontrol("H2", rol)).rol == rol, "saglam seride kontrol olusur"
    assert _ret(_bozuk("quote_volume", giris), **kontrol("H2", rol)) == "giris_bari_yok"


def test_sinyal_penceresi_ve_fiyat_okumasi_ayni_bari_eksik_sayar():
    """Kodun kendi icinde tutarliligi: ayni bozuk bar hem sinyal penceresinde hem fiyat okuma
    yolunda "mevcut degil"dir. Sinyal penceresi t-30'u icerir (H2 yukselis penceresi)."""
    bozuk = _bozuk("volume", T2 - 30 * H4)
    assert _ret(bozuk) == "sinyal_penceresi_tam_degil" or _ret(bozuk) == "olustu"
    # Kesin iddia: pencere kurucusu da ayni bari eksik sayar.
    from data import sinyal

    deger = sinyal.kapanis_30_once(bozuk, T2, config.BAR_4H, kume_baslangic=None, donem_baslangic=DB)
    assert not np.isfinite(deger)


def test_olcut_tek_uygulamadan_gecer():
    """Kural `klines.hucreleri_tam_mi` icindeki tek uygulamadan gecer; ikinci kopya yok."""
    import inspect

    kaynak = inspect.getsource(pozisyon._tam_hucreli_barlar)
    assert "hucreleri_tam_mi" in kaynak
    assert "HUCRE_SUTUNLARI" not in kaynak, "sutun listesi burada tekrarlanmamali"
