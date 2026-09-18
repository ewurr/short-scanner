"""F1 veri denetimi betiginin saf fonksiyonlarina saldiri testleri (on-kayit §2 rev.7).

`analysis/00_veri_denetimi/calistir.py` getiri hesaplamaz ama donem sinirini,
dolgu kosularini ve delist siniflandirmasini OKUNUR tablolara doker. Bu
dosyada bir hata olursa F1 denetim raporu (RESULTS.md) rev.7 kurallarini
yanlis anlatir; sonraki fazlar bu yanlis okunan tabloya guvenir.

Bu dosya `analysis/`e yazmaz; betigi dosya yolundan `importlib` ile yukler ve
yalnizca sentetik detay sozlukleriyle saf fonksiyonlari cagirir.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import config
from data import donem as donem_modulu

KOK = Path(__file__).resolve().parents[1]
_CALISTIR_YOLU = KOK / "analysis" / "00_veri_denetimi" / "calistir.py"

pytestmark = pytest.mark.skipif(not _CALISTIR_YOLU.exists(), reason="calistir.py yok")


def _yukle_calistir():
    spec = importlib.util.spec_from_file_location("_denetim_calistir_saldiri", _CALISTIR_YOLU)
    modul = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modul
    spec.loader.exec_module(modul)
    return modul


if _CALISTIR_YOLU.exists():
    calistir = _yukle_calistir()

ADIM_4H = pd.Timedelta(hours=4)


# --- sicramalari_grupla: donem siniri siniflandirmasi -------------------------


def _mumlar(zamanlar, close=100.0):
    return pd.DataFrame({"open_time": zamanlar, "open": close, "close": close})


def _sicrama_satiri(zaman, onceki_close=100.0, acilis=140.0):
    return pd.DataFrame({
        "open_time": [zaman], "onceki_close": [onceki_close], "open": [acilis],
        "bagil_fark": [abs(acilis / onceki_close - 1.0)],
    })


def _detay(sembol, zamanlar, donemler, sicrama_zamani, settled_aylari=""):
    return {
        "sembol": sembol,
        "_mumlar": _mumlar(zamanlar),
        "_donemler": donemler,
        "_sicramalar": _sicrama_satiri(sicrama_zamani),
        "settled_aylari": settled_aylari,
    }


def test_donem_basi_sicramasi_dolgu_sonrasi_dogru_siniflanir():
    """Dolgu kosusu sonrasi ilk gercek bardaki sicrama 'donem_basi' olmali."""
    z, h = pd.date_range("2021-01-01", periods=40, freq="4h", tz="UTC"), np.full(40, 1e6)
    h[10:16] = 0  # 6 barlik dolgu -> iki donem
    donemler = donem_modulu.listeleme_donemleri(z, h, config.BAR_4H)
    assert len(donemler) == 2
    detay = _detay("XUSDT", z, donemler, z[16])
    sonuc = calistir.sicramalari_grupla([detay])
    assert sonuc.loc[0, "sinif"] == "donem_basi"


def test_dolgu_icindeki_sicrama_donem_disi_sayilir():
    """Dolgu barinin kendisinde olusan sicrama hicbir donemde degildir."""
    z, h = pd.date_range("2021-01-01", periods=40, freq="4h", tz="UTC"), np.full(40, 1e6)
    h[10:16] = 0
    donemler = donem_modulu.listeleme_donemleri(z, h, config.BAR_4H)
    detay = _detay("XUSDT", z, donemler, z[12])
    sonuc = calistir.sicramalari_grupla([detay])
    assert sonuc.loc[0, "sinif"] == "donem_disi"


def test_donem_ici_kisa_bosluk_sonrasi_ayri_siniflanir():
    """7 gunden kisa gercek bar boslugundan sonraki ilk bar 'donem_ici_bosluk_sonrasi'
    olmali, sessizce 'donem_ici' ile karistirilmamali (on-kayit §2 rev.3/rev.7)."""
    tam = pd.date_range("2021-01-01", periods=60, freq="4h", tz="UTC")
    h_tam = np.full(60, 1e6)
    bosluk = pd.date_range(tam[20], periods=3, freq="4h")  # 3 bar (12 saat) eksik, donemi bolmez
    maske = ~tam.isin(bosluk)
    z, h = tam[maske], h_tam[maske]
    donemler = donem_modulu.listeleme_donemleri(z, h, config.BAR_4H)
    assert len(donemler) == 1  # bosluk donemi bolmedi
    # bosluktan sonraki ilk mevcut bar tam[23]'tur.
    detay = _detay("XUSDT", z, donemler, tam[23])
    sonuc = calistir.sicramalari_grupla([detay])
    assert sonuc.loc[0, "sinif"] == "donem_ici_bosluk_sonrasi"


def test_donem_bolen_uzun_bosluktan_sonraki_bar_donem_basi_onceliklidir():
    """7 gunden UZUN bosluk donemi boler; sonraki bar 'donem_basi' olmali, 'donem_ici_bosluk_sonrasi' DEGIL.

    Siniflandirma once donem basi kontrolunu yapar; 'donem_ici_bosluk_sonrasi'
    yalnizca donemi bolMEyen kisa bosluklar icindir. Iki dal karisirsa denetim
    raporu bir donem sinirini borsa kesintisi gibi gosterir.
    """
    tam = pd.date_range("2021-01-01", periods=100, freq="4h", tz="UTC")
    h_tam = np.full(100, 1e6)
    bosluk = pd.date_range(tam[20], periods=43, freq="4h")  # 7 gun 4 saat eksik -> boler
    maske = ~tam.isin(bosluk)
    z, h = tam[maske], h_tam[maske]
    donemler = donem_modulu.listeleme_donemleri(z, h, config.BAR_4H)
    assert len(donemler) == 2
    sonraki_bar = tam[63]  # bosluktan sonraki ilk mevcut bar
    assert donemler[1].baslangic == sonraki_bar
    detay = _detay("XUSDT", z, donemler, sonraki_bar)
    sonuc = calistir.sicramalari_grupla([detay])
    assert sonuc.loc[0, "sinif"] == "donem_basi"


def test_normal_donem_ici_sicrama_onceki_bar_bitisikse():
    z, h = pd.date_range("2021-01-01", periods=40, freq="4h", tz="UTC"), np.full(40, 1e6)
    donemler = donem_modulu.listeleme_donemleri(z, h, config.BAR_4H)
    detay = _detay("XUSDT", z, donemler, z[20])
    sonuc = calistir.sicramalari_grupla([detay])
    assert sonuc.loc[0, "sinif"] == "donem_ici"


def test_settled_ayi_bayragi_ay_sinirinda_dogru():
    """settled_ayi yalnizca denetim bilgisidir; ay sinirindaki bar dogru isaretlenmeli."""
    z, h = pd.date_range("2021-01-31", periods=10, freq="4h", tz="UTC"), np.full(10, 1e6)
    donemler = donem_modulu.listeleme_donemleri(z, h, config.BAR_4H)
    subat_bari = [t for t in z if t.month == 2][0]
    detay = _detay("XUSDT", z, donemler, subat_bari, settled_aylari="2021-02")
    sonuc = calistir.sicramalari_grupla([detay])
    assert bool(sonuc.loc[0, "settled_ayi"]) is True
    # Ocak barinda ayni SETTLED etiketi yanlislikla True olmamali.
    detay2 = _detay("XUSDT", z, donemler, z[1], settled_aylari="2021-02")
    sonuc2 = calistir.sicramalari_grupla([detay2])
    assert bool(sonuc2.loc[0, "settled_ayi"]) is False


# --- kisa_donemler: esik siniri -----------------------------------------------


def _donem(baslangic, bar_araligi):
    """bar_araligi: bitis, baslangictan kac 4h bar sonra (0 => tek bar)."""
    bitis = baslangic + bar_araligi * ADIM_4H
    return donem_modulu.Donem(baslangic, bitis, bar_araligi + 1, bar_araligi + 1)


def test_tam_esik_gunluk_donem_kisa_sayilmaz():
    """DENETIM_KISA_DONEM_GUN tam sinirdaki donem raporlanmamali (< kullanilir, <= degil)."""
    t0 = pd.Timestamp("2021-01-01", tz="UTC")
    gun = config.DENETIM_KISA_DONEM_GUN
    # gun = (bitis + 4h - baslangic) / 1 gun = gun  =>  bitis - baslangic = gun gun - 4h
    bar_sayisi = int((gun * 24 - 4) / 4)
    d = _donem(t0, bar_sayisi)
    gun_hesap = (d.bitis + ADIM_4H - d.baslangic) / pd.Timedelta(days=1)
    assert gun_hesap == pytest.approx(gun)
    sonuc = calistir.kisa_donemler([{"sembol": "XUSDT", "_donemler": [d]}])
    assert sonuc.empty, f"tam {gun} gunluk donem kisa donemler tablosuna sizdi"


def test_esikten_bir_bar_kisa_donem_raporlanir():
    t0 = pd.Timestamp("2021-01-01", tz="UTC")
    gun = config.DENETIM_KISA_DONEM_GUN
    bar_sayisi = int((gun * 24 - 4) / 4) - 1  # bir bar daha kisa
    d = _donem(t0, bar_sayisi)
    sonuc = calistir.kisa_donemler([{"sembol": "XUSDT", "_donemler": [d]}])
    assert len(sonuc) == 1 and sonuc.loc[0, "sembol"] == "XUSDT"


# --- settled_karsilastirma: ay kesisim siniri ---------------------------------


def test_settled_karsilastirma_dolgu_ay_sinirinda_kesisir():
    """Dolgu kosusu ay sinirini tam kapsayan (bir ucu icinde biten) durumda kesisim True olmali."""
    dolgu_tam_icinde = donem_modulu.DolguKosusu(
        pd.Timestamp("2021-02-10", tz="UTC"), pd.Timestamp("2021-02-15", tz="UTC"), 30, "ic"
    )
    detay = {"sembol": "XUSDT", "settled_aylari": "2021-02", "_dolgu": [dolgu_tam_icinde], "_donemler": []}
    sonuc = calistir.settled_karsilastirma([detay])
    assert bool(sonuc.loc[0, "dolgu_kosusu_var"]) is True

    # Dolgu Ocak'ta bitiyor, Subat'a hic girmiyor -> kesisim olmamali.
    dolgu_disinda = donem_modulu.DolguKosusu(
        pd.Timestamp("2021-01-05", tz="UTC"), pd.Timestamp("2021-01-31 12:00", tz="UTC"), 30, "ic"
    )
    detay2 = {"sembol": "XUSDT", "settled_aylari": "2021-02", "_dolgu": [dolgu_disinda], "_donemler": []}
    sonuc2 = calistir.settled_karsilastirma([detay2])
    assert bool(sonuc2.loc[0, "dolgu_kosusu_var"]) is False


def test_settled_karsilastirma_donem_siniri_ay_icinde():
    d = donem_modulu.Donem(pd.Timestamp("2021-02-05", tz="UTC"), pd.Timestamp("2021-03-01", tz="UTC"), 10, 10)
    detay = {"sembol": "XUSDT", "settled_aylari": "2021-02", "_dolgu": [], "_donemler": [d]}
    sonuc = calistir.settled_karsilastirma([detay])
    assert bool(sonuc.loc[0, "donem_siniri_var"]) is True


# --- donem_sonu_degisimleri: eski (ay duzeyi) / yeni (bar duzeyi) karsilastirmasi --


def _eski_satir(sembol, bas_ay, son_ay, donem_id=0, haric="False"):
    return {"sembol": sembol, "haric": haric, "donem_id": donem_id,
            "donem_bas_ay": bas_ay, "donem_son_ay": son_ay, "karantina_aylari": "[]"}


def test_donem_sonu_degisimleri_v1_deseni_pozitif_kisalma_verir():
    """V1 deseni (on-kayit rev.7 gerekcesi): eski ay duzeyi donem uzlasma sonrasi
    dolguyu fark etmeden Aralik'a kadar surer; yeni bar duzeyi donem cok daha
    erken biter. `bitis_kisalma_gun` buyuk ve pozitif olmali."""
    eski = pd.DataFrame([_eski_satir("XUSDT", "2021-01", "2021-12")])
    yeni_bitis = pd.Timestamp("2021-03-01 00:00", tz="UTC")
    d = donem_modulu.Donem(pd.Timestamp("2021-01-05 08:00", tz="UTC"), yeni_bitis, 100, 100)
    detay = {
        "sembol": "XUSDT", "_donemler": [d],
        "ilk_bar": pd.Timestamp("2021-01-05 08:00", tz="UTC"),
        "son_bar": pd.Timestamp("2021-12-31 20:00", tz="UTC"),
    }
    sonuc = calistir.donem_sonu_degisimleri(eski, [detay]).set_index("sembol")
    assert sonuc.at["XUSDT", "eski_donem_sayisi"] == 1
    assert sonuc.at["XUSDT", "yeni_donem_sayisi"] == 1
    assert sonuc.at["XUSDT", "bitis_kisalma_gun"] > 250  # ~ Mart -> Aralik farkinin buyuk kismi


def test_donem_sonu_degisimleri_eski_veride_olmayan_sembol_cokmez():
    """Eski tabloda hic olmayan (yeni bulunmus) bir sembol icin karsilastirma
    alanlari NaN kalmali, fonksiyon hata vermemeli."""
    d = donem_modulu.Donem(pd.Timestamp("2022-01-01", tz="UTC"), pd.Timestamp("2022-02-01", tz="UTC"), 10, 10)
    detay = {"sembol": "YENIUSDT", "_donemler": [d],
             "ilk_bar": pd.Timestamp("2022-01-01", tz="UTC"), "son_bar": pd.Timestamp("2022-02-01", tz="UTC")}
    eski = pd.DataFrame([_eski_satir("BASKAUSDT", "2021-01", "2021-02")])
    sonuc = calistir.donem_sonu_degisimleri(eski, [detay]).set_index("sembol")
    assert sonuc.at["YENIUSDT", "eski_donem_sayisi"] == 0
    assert "bitis_kisalma_gun" not in sonuc.columns or pd.isna(sonuc.at["YENIUSDT", "bitis_kisalma_gun"])


def test_donem_sonu_degisimleri_haric_eski_satir_sayilmaz():
    """Eski tabloda haric=True olarak isaretli satirlar eski_donem_sayisi'na girmemeli."""
    eski = pd.DataFrame([
        _eski_satir("XUSDT", "2021-01", "2021-02", donem_id=0, haric="True"),
        _eski_satir("XUSDT", "2021-03", "2021-04", donem_id=1, haric="False"),
    ])
    d = donem_modulu.Donem(pd.Timestamp("2021-03-01", tz="UTC"), pd.Timestamp("2021-04-01", tz="UTC"), 10, 10)
    detay = {"sembol": "XUSDT", "_donemler": [d],
             "ilk_bar": pd.Timestamp("2021-03-01", tz="UTC"), "son_bar": pd.Timestamp("2021-04-01", tz="UTC")}
    sonuc = calistir.donem_sonu_degisimleri(eski, [detay]).set_index("sembol")
    assert sonuc.at["XUSDT", "eski_donem_sayisi"] == 1  # yalnizca haric=False satir sayilmali


def test_donem_sonu_degisimleri_son_bar_nat_ise_karsilastirma_atlanir():
    """Veri hic olmayan (son_bar NaT) sembolde karsilastirma alanlari hesaplanmamali."""
    eski = pd.DataFrame([_eski_satir("XUSDT", "2021-01", "2021-02")])
    detay = {"sembol": "XUSDT", "_donemler": [], "ilk_bar": pd.NaT, "son_bar": pd.NaT}
    sonuc = calistir.donem_sonu_degisimleri(eski, [detay]).set_index("sembol")
    assert sonuc.at["XUSDT", "yeni_donem_sayisi"] == 0
    assert "bitis_kisalma_gun" not in sonuc.columns or pd.isna(sonuc.at["XUSDT", "bitis_kisalma_gun"])


# --- delist_tablosu: teslim_son_bar_icinde tam sinir --------------------------


def _delist_ortami(monkeypatch, calistir_modulu, deliverydate, son_donem_bitis):
    evren = pd.DataFrame({
        "sembol": ["XUSDT"], "haric": [False], "donem_id": [0],
        "donem_bitis": pd.to_datetime([son_donem_bitis], utc=True),
    })
    anlik = pd.DataFrame({
        "symbol": ["XUSDT"], "status": ["SETTLING"],
        "deliveryDate": pd.to_datetime([deliverydate], utc=True),
        "pair": [""], "contractType": [""], "onboardDate": pd.to_datetime([deliverydate], utc=True),
        "underlyingType": [""], "underlyingSubType": [""], "baseAsset": [""], "quoteAsset": [""], "marginAsset": [""],
    })
    anlik.attrs["alinma_zamani_utc"] = "2026-01-01T00:00:00Z"
    monkeypatch.setattr(calistir_modulu.universe_modulu, "exchange_info_anlik_yukle", lambda: anlik)
    detaylar = [{"sembol": "XUSDT", "son_bar": pd.Timestamp(son_donem_bitis, tz="UTC"), "dolgu_bar_son": 0}]
    return evren, detaylar


@pytest.mark.parametrize(
    "deliverydate, beklenen",
    [
        ("2021-06-01 00:00", True),   # tam son_donem_bitis'e esit -> DAHIL
        ("2021-06-01 03:59:59.999", True),  # ust sinirin hemen altinda -> DAHIL
        ("2021-06-01 04:00", False),  # ust sinira esit -> HARIC (yari acik)
        ("2021-05-31 23:59:59.999", False),  # alt sinirin hemen altinda -> HARIC
    ],
)
def test_teslim_son_bar_icinde_tam_sinirlar(monkeypatch, deliverydate, beklenen):
    son_donem_bitis = "2021-06-01 00:00"
    evren, detaylar = _delist_ortami(monkeypatch, calistir, deliverydate, son_donem_bitis)
    tablo = calistir.delist_tablosu(evren, detaylar)
    assert bool(tablo.loc[0, "teslim_son_bar_icinde"]) is beklenen


def test_haric_sembol_delist_tablosuna_hic_girmez(monkeypatch):
    """haric=True bir sembol delist siniflandirmasinda -- SETTLING olsa bile -- hic gorunmemeli."""
    evren = pd.DataFrame({
        "sembol": ["HARICUSDT"], "haric": [True], "donem_id": [-1],
        "donem_bitis": pd.to_datetime([pd.NaT], utc=True),
    })
    anlik = pd.DataFrame({
        "symbol": ["HARICUSDT"], "status": ["SETTLING"],
        "deliveryDate": pd.to_datetime(["2021-06-01"], utc=True),
        "pair": [""], "contractType": [""], "onboardDate": pd.to_datetime(["2021-06-01"], utc=True),
        "underlyingType": [""], "underlyingSubType": [""], "baseAsset": [""], "quoteAsset": [""], "marginAsset": [""],
    })
    anlik.attrs["alinma_zamani_utc"] = "2026-01-01T00:00:00Z"
    monkeypatch.setattr(calistir.universe_modulu, "exchange_info_anlik_yukle", lambda: anlik)
    detaylar = [{"sembol": "HARICUSDT", "son_bar": pd.NaT, "dolgu_bar_son": 0}]
    tablo = calistir.delist_tablosu(evren, detaylar)
    assert tablo.empty, "haric sembol delist tablosuna sizdi"


def test_coklu_donemli_sembolde_en_son_donem_bitisi_secilir(monkeypatch):
    """delist_sinifi son_donem_bitis'i donem_id>=0 satirlarinin MAKSIMUMU olarak almali."""
    evren = pd.DataFrame({
        "sembol": ["XUSDT", "XUSDT"], "haric": [False, False], "donem_id": [0, 1],
        "donem_bitis": pd.to_datetime(["2021-01-01 00:00", "2021-06-01 00:00"], utc=True),
    })
    anlik = pd.DataFrame({
        "symbol": ["XUSDT"], "status": ["SETTLING"],
        "deliveryDate": pd.to_datetime(["2021-06-01 00:00"], utc=True),
        "pair": [""], "contractType": [""], "onboardDate": pd.to_datetime(["2021-06-01"], utc=True),
        "underlyingType": [""], "underlyingSubType": [""], "baseAsset": [""], "quoteAsset": [""], "marginAsset": [""],
    })
    anlik.attrs["alinma_zamani_utc"] = "2026-01-01T00:00:00Z"
    monkeypatch.setattr(calistir.universe_modulu, "exchange_info_anlik_yukle", lambda: anlik)
    detaylar = [{"sembol": "XUSDT", "son_bar": pd.Timestamp("2021-06-01", tz="UTC"), "dolgu_bar_son": 0}]
    tablo = calistir.delist_tablosu(evren, detaylar)
    assert tablo.loc[0, "son_donem_bitis"] == pd.Timestamp("2021-06-01 00:00", tz="UTC")
    assert bool(tablo.loc[0, "teslim_son_bar_icinde"]) is True
