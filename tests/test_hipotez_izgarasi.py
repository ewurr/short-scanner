"""Hipotez izgarasi yardimcisi `pozisyon.hipotez_izgarasi_barlari` (RESULTS §14.47; teshis §14.46).

Izgara kapinin veri yolundan (`pozisyon._karar_verisi`) gelir; yeni kural yoktur. 1d izgarasi turetilmis 1d serisidir
(on-kayit §2 "1 gunluk barlar", satir 40: "dönemin kısmi ilk ve son günleri 1d serisinde yer almaz"), 4h izgarasi donem
ici mevcut 4h barlardir. Sentetik dunya; aga cikmaz, deger okunmaz (yalnizca zaman damgasi).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import config
from data import pencere, pozisyon, split
from kapi_yardimcisi import SENTETIK_DONEMLER, veri

H4 = pd.Timedelta(hours=4)
GUN = pd.Timedelta(days=1)


def _utc(x) -> pd.Timestamp:
    z = pd.Timestamp(x)
    return z.tz_localize("UTC") if z.tzinfo is None else z.tz_convert("UTC")


def _mumlar(bas, son, *, sifir_hacim=(), eksik=(), bozuk=()) -> pd.DataFrame:
    """[bas, son] 4h barlari; `sifir_hacim` (aralik listesi) dolgu barlari, `eksik` cikarilan barlar, `bozuk` open'i NaN."""
    z = pd.date_range(_utc(bas), _utc(son), freq=H4)
    m = pd.DataFrame({"open_time": z, "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.0, "volume": 1.0,
                      "quote_volume": 1e7})
    for a, b in sifir_hacim:
        ic = (z >= _utc(a)) & (z <= _utc(b))
        m.loc[ic, ["volume", "quote_volume"]] = 0.0
    for t in bozuk:
        m.loc[z == _utc(t), "open"] = np.nan
    if eksik:
        m = m.loc[~z.isin([_utc(t) for t in eksik])].reset_index(drop=True)
    return m


def _funding(bas, son) -> pd.DataFrame:
    z = pd.date_range(_utc(bas), _utc(son), freq="8h")
    return pd.DataFrame({"odeme_zamani": z, "aralik_saat": 8.0, "oran": 1e-4, "oran_8h": 1e-4})


def _dunya(bas, bitis, **kw) -> dict:
    """Tek donemli sentetik sembol: veri donemin bir gun oncesinden bir gun sonrasina (donem disi barlar dahil)."""
    return veri(_mumlar(_utc(bas) - GUN, _utc(bitis) + GUN, **kw), _funding(bas, bitis), _utc(bas), _utc(bitis))


def _izgara(hipotez, kimlik, kume="KESIF"):
    return pozisyon.hipotez_izgarasi_barlari(hipotez, kume=kume, **kimlik)


def _hepsi_donem_ici(izgara, kimlik, bar):
    bas, bitis, _ = pozisyon.donem_kaydi(kimlik["sembol"], kimlik["donem_no"])
    return all(pencere.donem_ici_mi(t, bar, donem_baslangic=bas, donem_bitis=bitis) for t in izgara)


# --- 1d ---------------------------------------------------------------------------------------------------------

def test_yarim_son_gun_1d_izgarasinda_yok_onceki_gun_var():
    kimlik = _dunya("2024-01-01 00:00", "2024-03-10 08:00")      # B 08:00: son gunun 3/6 bari donem ici
    izgara = _izgara("H3", kimlik)
    assert _utc("2024-03-10") not in izgara
    assert izgara[-1] == _utc("2024-03-09")
    assert izgara[0] == _utc("2024-01-01")
    assert _hepsi_donem_ici(izgara, kimlik, config.BAR_1D)


def test_yarim_ilk_gun_1d_izgarasinda_yok_sonraki_gun_var():
    kimlik = _dunya("2024-01-01 12:00", "2024-03-10 20:00")
    izgara = _izgara("H3", kimlik)
    assert _utc("2024-01-01") not in izgara
    assert izgara[0] == _utc("2024-01-02")
    assert izgara[-1] == _utc("2024-03-10")                         # B 20:00: son gun tam
    assert _hepsi_donem_ici(izgara, kimlik, config.BAR_1D)


def test_1d_izgarasi_takvim_izgarasindan_yalniz_yarim_ve_eksik_gunlerle_ayrilir():
    """Eksik bar ya da bozuk hucreli bar gununu dusurur (on-kayit §2 satir 40); takvim izgarasi bu gunleri verirdi."""
    kimlik = _dunya("2024-01-01 08:00", "2024-03-10 08:00", eksik=["2024-02-01 04:00"], bozuk=["2024-02-15 12:00"])
    izgara = _izgara("H3", kimlik)
    takvim = pd.date_range(_utc("2024-01-01"), _utc("2024-03-10"), freq="1D")
    assert sorted(set(takvim) - set(izgara)) == [_utc(g) for g in ("2024-01-01", "2024-02-01", "2024-02-15",
                                                                    "2024-03-10")]
    assert set(izgara) <= set(takvim)
    assert _hepsi_donem_ici(izgara, kimlik, config.BAR_1D)


def test_1d_izgarasi_kapinin_turettigi_1d_serisinin_kendisi():
    kimlik = _dunya("2024-01-01 12:00", "2024-03-10 08:00", eksik=["2024-02-01 04:00"])
    bas, bitis, _ = pozisyon.donem_kaydi(kimlik["sembol"], kimlik["donem_no"])
    kb, ks = pozisyon.kume_sinirlari("KESIF")
    _, _, gunluk = pozisyon._karar_verisi(kimlik["sembol"], "KESIF", kume_baslangic=kb, kume_bitis=ks,
                                         donem_baslangic=bas, donem_bitis=bitis)
    assert list(_izgara("H3", kimlik)) == list(pd.DatetimeIndex(gunluk["open_time"]))


# --- 4h ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("hipotez", ["H1", "H2"])
def test_4h_izgarasi_donem_basi_ile_B_arasinda_iki_uc_dahil(hipotez):
    kimlik = _dunya("2024-01-01 12:00", "2024-03-10 08:00", eksik=["2024-02-01 04:00"], bozuk=["2024-02-15 12:00"])
    izgara = _izgara(hipotez, kimlik)
    assert izgara[0] == _utc("2024-01-01 12:00") and izgara[-1] == _utc("2024-03-10 08:00")
    takvim = pd.date_range(_utc("2024-01-01 12:00"), _utc("2024-03-10 08:00"), freq=H4)
    assert sorted(set(takvim) - set(izgara)) == [_utc("2024-02-01 04:00"), _utc("2024-02-15 12:00")]
    assert _hepsi_donem_ici(izgara, kimlik, config.BAR_4H)


# --- Iki donem, kume sonu ---------------------------------------------------------------------------------------

def _iki_donemli():
    """Donem 0: 2024-01-01 00:00 .. 2024-02-01 08:00; dolgu (sifir hacim) 2024-02-01 12:00 .. 2024-02-10 20:00;
    donem 1: 2024-02-11 12:00 .. 2024-03-31 20:00."""
    m = _mumlar("2023-12-31 00:00", "2024-04-01 20:00",
                sifir_hacim=[("2023-12-31 00:00", "2023-12-31 20:00"), ("2024-02-01 12:00", "2024-02-11 08:00"),
                             ("2024-04-01 00:00", "2024-04-01 20:00")])
    kimlik = veri(m, _funding("2024-01-01", "2024-03-31"), _utc("2024-01-01 00:00"),
                 _utc("2024-02-01 08:00"))
    SENTETIK_DONEMLER[(kimlik["sembol"], 1)] = (_utc("2024-02-11 12:00"), _utc("2024-03-31 20:00"), False)
    return kimlik, {**kimlik, "donem_no": 1}


@pytest.mark.parametrize("hipotez", ["H1", "H3"])
def test_iki_donemli_sembolde_donemler_arasi_dolgu_izgarada_yok(hipotez):
    d0, d1 = _iki_donemli()
    bar = pencere.hipotez_izgarasi(hipotez)
    i0, i1 = _izgara(hipotez, d0), _izgara(hipotez, d1)
    # Dolgu barlari (4h) ya da dolguya degen gunler (1d; 2024-02-01 ve 2024-02-11 yarim gunler) izgarada yok.
    dolgu_bas, dolgu_son = ((_utc("2024-02-01 12:00"), _utc("2024-02-11 08:00")) if bar == config.BAR_4H
                            else (_utc("2024-02-01"), _utc("2024-02-11")))
    for izgara in (i0, i1):
        assert not any(dolgu_bas <= t <= dolgu_son for t in izgara)
    if bar == config.BAR_1D:
        assert i0[-1] == _utc("2024-01-31") and i1[0] == _utc("2024-02-12")   # iki uctaki yarim gunler disarida
    else:
        assert i0[-1] == _utc("2024-02-01 08:00") and i1[0] == _utc("2024-02-11 12:00")
    assert _hepsi_donem_ici(i0, d0, bar) and _hepsi_donem_ici(i1, d1, bar)
    assert set(i0).isdisjoint(i1)


@pytest.mark.parametrize("hipotez,son", [("H2", "2025-08-31 20:00"), ("H3", "2025-08-31")])
def test_kesif_sonunu_asan_donemde_izgara_kume_sonunda_biter(hipotez, son):
    kimlik = _dunya("2025-06-01 00:00", "2025-09-20 20:00")
    izgara = _izgara(hipotez, kimlik)
    ks = pd.Timestamp(config.KESIF_SONU)
    assert izgara[-1] == _utc(son) and all(t <= ks for t in izgara)
    assert _hepsi_donem_ici(izgara, kimlik, pencere.hipotez_izgarasi(hipotez))


# --- Baglam: karar noktasiyla ayni ------------------------------------------------------------------------------

def test_onay_kumesi_acik_onay_kosusu_olmadan_reddedilir():
    kimlik = veri(_mumlar("2025-09-01", "2025-12-31 20:00"), _funding("2025-09-01", "2025-12-31"),
                  _utc("2025-09-01 00:00"), _utc("2025-12-31 20:00"), grup="B")
    with pytest.raises((split.OnayGerekli, split.OnayUyusmazligi)):
        _izgara("H2", kimlik, kume="C2")


def test_kumeye_ait_olmayan_grup_reddedilir():
    kimlik = veri(_mumlar("2024-01-01", "2024-03-10 20:00"), _funding("2024-01-01", "2024-03-10"),
                  _utc("2024-01-01 00:00"), _utc("2024-03-10 20:00"), grup="B")
    with pytest.raises(ValueError, match="kumesine ait degil"):
        _izgara("H2", kimlik, kume="KESIF")


def test_izgara_kopyadir_ve_degistirilmesi_kapiyi_etkilemez():
    kimlik = _dunya("2024-01-01 00:00", "2024-03-10 08:00")
    ilk = _izgara("H3", kimlik)
    assert isinstance(ilk, pd.DatetimeIndex) and str(ilk.tz) == "UTC"
    ikinci = _izgara("H3", kimlik)
    assert ilk is not ikinci and list(ilk) == list(ikinci)


def test_analiz_kodunda_yardimci_hicbir_taramaya_takilmaz(tmp_path):
    """F2 kosucusu ve esitlik betigi yardimciyi kullanir: analiz kodu taramalarinin hicbiri onu yakalamaz."""
    import tarama_yardimcisi as ty

    (tmp_path / "study").mkdir()
    (tmp_path / "study" / "kosucu.py").write_text(
        "from data import pozisyon\n"
        "izgara = pozisyon.hipotez_izgarasi_barlari('H3', kume='KESIF', sembol=s, donem_no=0)\n", encoding="utf-8")
    desenler = {ad: getattr(ty, ad) for ad in dir(ty) if ad.endswith("_DESENI") and isinstance(getattr(ty, ad), str)}
    assert desenler
    for ad, desen in desenler.items():
        assert ty.ihlaller(desen, kok=tmp_path) == [], ad
    assert ty.olay_rolu_ihlalleri(kok=tmp_path) == []
