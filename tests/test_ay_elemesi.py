"""Ay elemesi: yukleyiciler kume araligi disindaki aylari dosya acmadan eler (RESULTS §14.42, denetci D-B1).

Sentetik testler gecici onbellek kullanir. Esitlik testi GERCEK onbellegi okur (aga cikmaz; liste dondurulmus dosyadan):
eski yol (butun aylar izinle, sonra kesim) ile yeni yol KESIF araliginda birebir ayni cerceveyi uretmeli. Degerler
yalnizca karsilastirilir, yazdirilmaz. Onbellek yoksa esitlik testi atlanir.
"""

from __future__ import annotations

import datetime as dt
import json
import sys

import pandas as pd
import pytest

import config
from conftest import sahte_4h
from data import binance_vision as bv
from data import funding as funding_modulu
from data import klines, kume_bellegi, split, universe
from onay_yardimcisi import gecici_kayit, kosu

_ACILAN: list | None = None


def _kanca(olay, argumanlar):
    if olay == "open" and _ACILAN is not None:
        _ACILAN.append(str(argumanlar[0]))


sys.addaudithook(_kanca)

UTC = dt.timezone.utc


# --- Sinirlar ------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("kume", config.KUMELER)
def test_kume_sinirlari_ay_sinirina_denk_gelir(kume):
    bas, son = split.kume_araligi(kume)
    ilk, sonuncu = bv.ay_araligi_sinirlari(bas, son)
    assert ilk == bas.strftime("%Y-%m") and sonuncu == son.strftime("%Y-%m")


@pytest.mark.parametrize("bas, son", [
    (dt.datetime(2020, 1, 2, tzinfo=UTC), dt.datetime(2025, 8, 31, 23, 59, 59, tzinfo=UTC)),   # gun 1 degil
    (dt.datetime(2020, 1, 1, 0, 0, 1, tzinfo=UTC), dt.datetime(2025, 8, 31, 23, 59, 59, tzinfo=UTC)),  # saat 0 degil
    (dt.datetime(2020, 1, 1, tzinfo=UTC), dt.datetime(2025, 8, 30, 23, 59, 59, tzinfo=UTC)),   # ay sonu degil
    (dt.datetime(2020, 1, 1, tzinfo=UTC), dt.datetime(2025, 8, 31, 23, 59, 58, tzinfo=UTC)),   # son saniye degil
    (dt.datetime(2020, 1, 1, tzinfo=UTC), dt.datetime(2025, 9, 1, tzinfo=UTC)),                # ay basi, son saniye degil
    (dt.datetime(2020, 1, 1), dt.datetime(2025, 8, 31, 23, 59, 59)),                            # saat dilimsiz
    (dt.datetime(2025, 9, 1, tzinfo=UTC), dt.datetime(2025, 8, 31, 23, 59, 59, tzinfo=UTC)),   # ters
])
def test_ay_siniri_olmayan_aralik_yuvarlanmaz_hata_verir(bas, son):
    with pytest.raises(bv.AySiniriHatasi):
        bv.ay_araligi_sinirlari(bas, son)


def test_aylara_gore_ele_adlara_bakar_ayristirilamayani_tutar():
    anahtarlar = [f"data/futures/um/monthly/klines/X/4h/X-4h-{ay}.zip" for ay in ("2019-12", "2020-01", "2025-08", "2025-09")]
    anahtarlar.append("data/futures/um/monthly/klines/X/4h/X-4h-bozuk.zip")
    kalan = bv.aylara_gore_ele(anahtarlar, ("2020-01", "2025-08"))
    assert [bv.dosya_ayi(a) for a in kalan] == ["2020-01", "2025-08", "4h-bozuk"]
    assert bv.aylara_gore_ele(["a/2025-09.parquet", "a/2025-08.parquet"], ("2020-01", "2025-08")) == ["a/2025-08.parquet"]
    with pytest.raises(bv.AySiniriHatasi):
        bv.aylara_gore_ele(anahtarlar, ("2020-1", "2025-08"))


def test_ham_yukleyiciler_ay_siniri_olmayan_araligi_reddeder():
    with pytest.raises(bv.AySiniriHatasi):
        klines.ham_mumlari_yukle("X", config.BAR_4H, aralik=(pd.Timestamp("2020-01-15", tz="UTC"),
                                                             pd.Timestamp(config.KESIF_SONU)))
    with pytest.raises(bv.AySiniriHatasi):
        funding_modulu.ham_funding_yukle("X", aralik=(pd.Timestamp(config.KESIF_BASI), pd.Timestamp("2025-08-15", tz="UTC")))


# --- Sentetik onbellek: hangi aylar acilir -------------------------------------------------------------------------


def _a_sembolu() -> str:
    tablo = split.split_oku()
    tek = tablo.loc[(tablo["grup"] == "A") & (tablo["sembol"] == tablo["varlik_anahtari"]), "sembol"]
    return str(tek.iloc[0])


def _b_sembolu() -> str:
    tablo = split.split_oku()
    return str(tablo.loc[tablo["grup"] == "B", "sembol"].iloc[0])


def _anahtar(sembol, ay):
    return f"{bv.MUM_ONEKI}/{sembol}/{config.BAR_4H}/{sembol}-{config.BAR_4H}-{ay}.zip"


AYLAR = ("2025-07", "2025-08", "2025-09", "2026-08", "2026-09")


@pytest.fixture
def onbellek(monkeypatch, tmp_path):
    kok = tmp_path / "onbellek"
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", kok)
    bv.donuk_bellek_temizle()
    kume_bellegi.temizle()
    semboller = (_a_sembolu(), _b_sembolu())
    for sembol in semboller:
        for ay in AYLAR:
            sahte_4h(f"{ay}-01 00:00", 12).to_parquet(bv.onbellek_yolu("klines", sembol, config.BAR_4H, f"{ay}.parquet"),
                                                      index=False)
    yol = bv.donuk_liste_yolu()
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps({"mum": {s: {config.BAR_4H: [_anahtar(s, ay) for ay in AYLAR]} for s in semboller},
                               "funding": {}}), encoding="utf-8")
    yield kok
    bv.donuk_bellek_temizle()
    kume_bellegi.temizle()


def _acilan_aylar(cagri) -> tuple[set, object]:
    global _ACILAN
    _ACILAN = []
    try:
        sonuc = cagri()
        acilan = list(_ACILAN)
    finally:
        _ACILAN = None
    return {a.replace("\\", "/").rsplit("/", 1)[-1].removesuffix(".parquet") for a in acilan if a.endswith(".parquet")}, sonuc


def test_kesif_yalnizca_kesif_aylarini_acar(onbellek):
    aylar, cerceve = _acilan_aylar(lambda: klines.mumlari_yukle(_a_sembolu(), config.BAR_4H, "KESIF"))
    assert aylar == {"2025-07", "2025-08"}
    assert len(cerceve) == 24


def test_kesif_1d_yalnizca_kesif_aylarini_acar(onbellek):
    aylar, _ = _acilan_aylar(lambda: klines.mumlari_yukle(_a_sembolu(), config.BAR_1D, "KESIF"))
    assert aylar <= {"2025-07", "2025-08"}


def test_c1_yalnizca_kesif_donemindeki_aylari_acar(onbellek, tmp_path):
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    with kosu("H2", "C1"):
        aylar, cerceve = _acilan_aylar(lambda: klines.mumlari_yukle(_b_sembolu(), config.BAR_4H, "C1", onay=True))
    assert aylar == {"2025-07", "2025-08"} and len(cerceve) == 24


def test_c2_yalnizca_c2_aylarini_acar_c2_sonu_sonrasini_acmaz(onbellek, tmp_path):
    gecici_kayit(tmp_path / "ONAY_KAYDI.md")
    with kosu("H2", "C2"):
        aylar, cerceve = _acilan_aylar(lambda: klines.mumlari_yukle(_a_sembolu(), config.BAR_4H, "C2", onay=True))
    assert aylar == {"2025-09", "2026-08"} and len(cerceve) == 24


def test_kesif_funding_yalnizca_kesif_aylarini_listeler(onbellek, monkeypatch):
    istenen = []
    monkeypatch.setattr(bv, "funding_dosyalari", lambda s, aylar=None: (istenen.append(aylar), [])[1])
    funding_modulu.funding_yukle(_a_sembolu(), "KESIF")
    assert istenen == [("2020-01", "2025-08")]


# --- Gercek onbellekte esitlik ---------------------------------------------------------------------------------------


def _gercek_onbellek_var() -> bool:
    return bv.donuk_liste_yolu().exists() and (config.ONBELLEK_DIZINI / "klines").exists()


def _esitlik_ornegi() -> list[str]:
    """En az 5 A sembolu, deterministik: donemi KESIF sinirini asan uc uzun sembol ve KESIF icinde biten iki sembol."""
    tablo = split.split_oku()
    evren = universe.evren_yukle()
    a = set(tablo.loc[tablo["grup"] == "A", "sembol"])
    evren = evren[evren["sembol"].isin(a) & ~evren["haric"].astype(str).str.lower().eq("true")]
    bas = pd.to_datetime(evren.groupby("sembol")["donem_baslangic"].min(), utc=True)
    son = pd.to_datetime(evren.groupby("sembol")["donem_bitis"].max(), utc=True)
    kesif_sonu, kesif_basi = pd.Timestamp(config.KESIF_SONU), pd.Timestamp(config.KESIF_BASI)
    asan = sorted(s for s in son.index if son[s] > kesif_sonu and bas[s] < kesif_basi + pd.Timedelta(days=400))
    icinde = sorted(s for s in son.index if son[s] < kesif_sonu - pd.Timedelta(days=60) and bas[s] < son[s] - pd.Timedelta(days=200))
    return asan[:3] + icinde[:2]


def _eski_yol(sembol):
    """§14.41'deki yol: butun aylar izinle okunur, sonra kesilir (yalnizca bu karsilastirma icin)."""
    bas, son = split.kume_araligi("KESIF")
    with bv.onay_verisi_izni("test: D-B1 esitligi"), bv.agsiz_okuma():
        mum = klines.donem_kes(klines.ham_mumlari_yukle(sembol, config.BAR_4H), bas, son)
        gunluk = klines.donem_kes(klines.ham_mumlari_yukle(sembol, config.BAR_1D), bas, son)
        tum = funding_modulu.ham_funding_yukle(sembol)
    evren = universe.evren_yukle()
    if not tum.empty:
        tum = funding_modulu.donem_sonrasi_kayitlari_at(tum, universe.sembol_donemleri(evren, sembol), config.BAR_4H)
        tum = tum.loc[(tum["odeme_zamani"] >= bas) & (tum["odeme_zamani"] <= son)].reset_index(drop=True)
    return mum, gunluk, tum


@pytest.mark.skipif(not _gercek_onbellek_var(), reason="gercek onbellek ya da dondurulmus liste yok")
def test_eski_ve_yeni_yol_kesif_araliginda_birebir_ayni():
    ornek = _esitlik_ornegi()
    assert len(ornek) >= 5
    son = pd.to_datetime(universe.evren_yukle().groupby("sembol")["donem_bitis"].max(), utc=True)
    assert any(son[s] > pd.Timestamp(config.KESIF_SONU) for s in ornek), "KESIF sinirini asan sembol ornekte olmali"
    for sembol in ornek:
        bv.donuk_bellek_temizle()
        mum, gunluk, fr = _eski_yol(sembol)
        assert len(mum) > 0
        pd.testing.assert_frame_equal(klines.mumlari_yukle(sembol, config.BAR_4H, "KESIF"), mum, obj=f"{sembol} 4h")
        pd.testing.assert_frame_equal(klines.mumlari_yukle(sembol, config.BAR_1D, "KESIF"), gunluk, obj=f"{sembol} 1d")
        pd.testing.assert_frame_equal(funding_modulu.funding_yukle(sembol, "KESIF"), fr, obj=f"{sembol} funding")
