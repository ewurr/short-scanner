"""Tekrarlanan bar damgasi yukleyicide hata verir (F1 kapanis bulgusu 14).

Eskiden `ham_mumlari_yukle` ve `ham_birincil_gunluk_indir` ayni `open_time`'a
sahip kayitlari `drop_duplicates(keep="last")` ile sessizce siliyordu; celisen iki
kayittan birini iz birakmadan seciyordu. `data.pencere` tekrari bozuk veri sayar;
yukleyici de artik ayni sekilde hata verir. Testler sahte onbellekle calisir,
aga cikmaz.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from conftest import sahte_4h
from data import binance_vision as bv
from data import klines, pencere


def _sahte_onbellek(monkeypatch, tmp_path, kategori, aylar_ve_cerceveler, bar=None):
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", tmp_path)
    sembol = "TESTUSDT"
    anahtarlar = []
    for ay, cerceve in aylar_ve_cerceveler:
        if kategori == "klines":
            anahtar = f"{bv.MUM_ONEKI}/{sembol}/{bar}/{sembol}-{bar}-{ay}.zip"
            yol = bv.onbellek_yolu("klines", sembol, bar, f"{ay}.parquet")
        else:
            anahtar = f"{bv.MUM_ONEKI}/{sembol}/1d/{sembol}-1d-{ay}.zip"
            yol = bv.onbellek_yolu("klines_birincil_1d", sembol, f"{ay}.parquet")
        cerceve.to_parquet(yol, index=False)
        anahtarlar.append(anahtar)
    monkeypatch.setattr(bv, "mum_dosyalari", lambda s, b: anahtarlar)

    def yasak(*_a, **_k):
        raise AssertionError("onbellek doluyken indirme yapilmamali")

    monkeypatch.setattr(bv, "zip_indir", yasak)
    return sembol


def test_ay_sinirinda_tekrarlanan_4h_bar_hata_verir(monkeypatch, tmp_path):
    ocak = sahte_4h("2021-01-31 00:00", 6)
    subat = sahte_4h("2021-01-31 20:00", 6)  # ilk bari ocak dosyasinin son bariyla ayni
    sembol = _sahte_onbellek(monkeypatch, tmp_path, "klines", [("2021-01", ocak), ("2021-02", subat)], bar=config.BAR_4H)

    with pytest.raises(pencere.ZamanDizisiHatasi):
        klines.ham_mumlari_yukle(sembol, config.BAR_4H)


def test_celisen_tekrar_da_sessizce_secilmez(monkeypatch, tmp_path):
    temel = sahte_4h("2021-01-01", 6)
    celisen = temel.iloc[[3]].copy()
    celisen["close"] = 999.0
    sembol = _sahte_onbellek(
        monkeypatch, tmp_path, "klines", [("2021-01", pd.concat([temel, celisen], ignore_index=True))], bar=config.BAR_4H
    )
    with pytest.raises(pencere.ZamanDizisiHatasi):
        klines.ham_mumlari_yukle(sembol, config.BAR_4H)


def test_tekrarsiz_parcalar_normal_birlesir(monkeypatch, tmp_path):
    ocak = sahte_4h("2021-01-31 00:00", 6)
    subat = sahte_4h("2021-02-01 00:00", 6)
    sembol = _sahte_onbellek(monkeypatch, tmp_path, "klines", [("2021-02", subat), ("2021-01", ocak)], bar=config.BAR_4H)

    tum = klines.ham_mumlari_yukle(sembol, config.BAR_4H)
    assert len(tum) == 12
    assert tum["open_time"].is_monotonic_increasing


def test_birincil_1d_tekrari_da_hata_verir(monkeypatch, tmp_path):
    gunluk = klines.gunluge_cevir(sahte_4h("2021-01-01", 18))
    sembol = _sahte_onbellek(
        monkeypatch, tmp_path, "birincil", [("2021-01", gunluk), ("2021-02", gunluk.iloc[[-1]])]
    )
    with pytest.raises(pencere.ZamanDizisiHatasi):
        klines.ham_birincil_gunluk_indir(sembol)
