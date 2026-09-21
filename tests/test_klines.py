"""Mum ayristirma, 1d turetme ve butunluk testleri."""

from __future__ import annotations

import io
import zipfile

import pandas as pd

from tests.donem_yardimcisi import tum_seri_donemi

import config
from conftest import sahte_4h
from data import binance_vision as bv
from data import klines


def _mum_zip(satirlar: list[str]) -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as zf:
        zf.writestr("k.csv", "\n".join(satirlar))
    return tampon.getvalue()


SATIR_A = "1577836800000,7189.43,7239.74,7170.15,7221.65,12055.7,1577851199999,86901102.7,1,2,3,0"
SATIR_B = "1577851200000,7221.65,7300.00,7200.00,7280.00,11000.0,1577865599999,80000000.0,1,2,3,0"


def test_baslikli_ve_baslisiz_dosya_ayni_sonucu_verir():
    """2020 dosyalarinda basli yok, yenilerinde var; ikisi de ayni okunmali."""
    basliksiz = klines._ay_cercevesi(_mum_zip([SATIR_A, SATIR_B]))
    baslikli = klines._ay_cercevesi(_mum_zip([",".join(bv.MUM_SUTUNLARI), SATIR_A, SATIR_B]))
    pd.testing.assert_frame_equal(basliksiz, baslikli)
    assert len(basliksiz) == 2
    assert basliksiz["open"].iloc[0] == 7189.43


def test_zaman_damgasi_utc_ve_acilis_zamani():
    cerceve = klines._ay_cercevesi(_mum_zip([SATIR_A]))
    assert str(cerceve["open_time"].dt.tz) == "UTC"
    assert cerceve["open_time"].iloc[0] == pd.Timestamp("2020-01-01 00:00", tz="UTC")


def test_mikrosaniye_damgasi_da_dogru_cevrilir():
    mikro = SATIR_A.replace("1577836800000", "1577836800000000", 1).replace(
        "1577851199999", "1577851199999000", 1
    )
    cerceve = klines._ay_cercevesi(_mum_zip([mikro]))
    assert cerceve["open_time"].iloc[0] == pd.Timestamp("2020-01-01 00:00", tz="UTC")


def test_gunluge_cevirme_dogru_toplar():
    dort = sahte_4h("2021-05-01", 12, hacim=1000.0)
    # Ikinci gunun yuksek/dusuk degerlerini ayirt edilebilir yap
    dort.loc[7, "high"] = 150.0
    dort.loc[9, "low"] = 50.0
    dort.loc[6, "open"] = 111.0
    dort.loc[11, "close"] = 222.0

    gunluk = klines.gunluge_cevir(dort, donemler=tum_seri_donemi(dort))

    assert len(gunluk) == 2
    ikinci = gunluk.iloc[1]
    assert ikinci["open"] == 111.0
    assert ikinci["close"] == 222.0
    assert ikinci["high"] == 150.0
    assert ikinci["low"] == 50.0
    assert ikinci["quote_volume"] == 6000.0


def test_eksik_barli_gun_kismi_toplanmaz():
    """6 bari tam olmayan gun NaN sayilir, kismi toplanmaz."""
    dort = sahte_4h("2021-05-01", 12).drop(index=3).reset_index(drop=True)
    gunluk = klines.gunluge_cevir(dort, donemler=tum_seri_donemi(dort))

    assert len(gunluk) == 1  # eksik gun dusuruldu
    assert gunluk["open_time"].iloc[0] == pd.Timestamp("2021-05-02", tz="UTC")


def test_gunluk_open_time_utc_gun_basinda():
    gunluk = klines.gunluge_cevir(sahte_4h("2021-05-01", 18), donemler=tum_seri_donemi(sahte_4h("2021-05-01", 18)))
    assert (gunluk["open_time"].dt.hour == 0).all()
    assert (gunluk["open_time"].dt.tz is not None)


def test_donem_kes_kapali_aralik():
    dort = sahte_4h("2020-01-01", 100)
    kesik = klines.donem_kes(dort, config.KESIF_BASI, pd.Timestamp("2020-01-02", tz="UTC"))
    assert kesik["open_time"].min() == pd.Timestamp("2020-01-01", tz="UTC")
    assert kesik["open_time"].max() == pd.Timestamp("2020-01-02", tz="UTC")


def test_eksik_barlar_boslugu_bulur():
    dort = sahte_4h("2021-01-01", 20)
    eksikli = dort.drop(index=[5, 6, 7, 8]).reset_index(drop=True)

    bosluklar = klines.eksik_barlar(eksikli, config.BAR_4H)

    assert len(bosluklar) == 1
    assert bosluklar["eksik_bar"].iloc[0] == 4
    assert bosluklar["bas"].iloc[0] == pd.Timestamp("2021-01-01 20:00", tz="UTC")


def test_eksiksiz_seride_bosluk_yok():
    assert klines.eksik_barlar(sahte_4h("2021-01-01", 30), config.BAR_4H).empty


def test_cross_dogrulama_ayni_veride_sifir_fark():
    dort = sahte_4h("2021-05-01", 24)
    turetilmis = klines.gunluge_cevir(dort, donemler=tum_seri_donemi(dort))
    fark = klines.cross_dogrula(turetilmis, turetilmis)
    for sutun in fark.columns:
        if sutun.endswith("_bagil_fark"):
            assert fark[sutun].fillna(0).max() == 0


# --- 1d turetme kurali (on-kayit rev.2) --------------------------------------


def test_alti_bari_eksik_gun_nan_olur():
    """On-kayit rev.2: 6 adet 4h bari tam olmayan gun eksik sayilir, kismi
    toplanmaz."""
    dort = sahte_4h("2021-05-01", 18)          # 3 tam gun
    eksikli = dort.drop(index=8).reset_index(drop=True)  # 2. gunden bir bar eksik

    gunluk = klines.gunluge_cevir(eksikli, donemler=tum_seri_donemi(eksikli))
    gunler = list(gunluk["open_time"])

    assert pd.Timestamp("2021-05-02", tz="UTC") not in gunler   # eksik gun dusuruldu
    assert pd.Timestamp("2021-05-01", tz="UTC") in gunler       # tam gunler duruyor
    assert pd.Timestamp("2021-05-03", tz="UTC") in gunler
    assert len(gunluk) == 2


def test_kismi_gun_hacmi_toplanmaz():
    """Eksik gunun hacmi kismi olarak raporlanmamali."""
    dort = sahte_4h("2021-05-01", 12, hacim=1000.0)
    eksikli = dort.drop(index=[6, 7]).reset_index(drop=True)

    gunluk = klines.gunluge_cevir(eksikli, donemler=tum_seri_donemi(eksikli))

    assert len(gunluk) == 1
    assert gunluk["quote_volume"].iloc[0] == 6000.0  # yalnizca tam gun


# --- Veri butunlugu kontrolu (on-kayit rev.2) --------------------------------


def test_butunluk_sicramasi_yakalanir():
    """|open[t] / close[t-1] - 1| > 0.30 olan barlar listelenir."""
    dort = sahte_4h("2021-05-01", 10)
    dort.loc[5, "open"] = dort.loc[4, "close"] * 2.0   # %100 sicrama

    sicramalar = klines.butunluk_sicramalari(dort)

    assert len(sicramalar) == 1
    assert sicramalar["open_time"].iloc[0] == dort.loc[5, "open_time"]
    assert sicramalar["bagil_fark"].iloc[0] > 0.30


def test_butunluk_esik_altinda_bos_doner():
    dort = sahte_4h("2021-05-01", 10)
    dort.loc[5, "open"] = dort.loc[4, "close"] * 1.10  # %10, esik alti
    assert klines.butunluk_sicramalari(dort).empty


def test_butunluk_asagi_yonlu_sicramayi_da_yakalar():
    dort = sahte_4h("2021-05-01", 10)
    dort.loc[3, "open"] = dort.loc[2, "close"] * 0.5   # -%50
    assert len(klines.butunluk_sicramalari(dort)) == 1


def test_butunluk_esigi_config_ten_gelir():
    assert config.BUTUNLUK_ACILIS_ESIGI == 0.30
