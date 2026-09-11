"""Funding normallestirme ve ayristirma testleri (on-kayit §2)."""

from __future__ import annotations

import io
import zipfile

import pandas as pd

from data import binance_vision as bv
from data import funding


def test_normallestirme_carpanlari():
    """4h aralikta oran x2, 1h aralikta x8, 8h aralikta degismez."""
    oran = pd.Series([0.0001, 0.0001, 0.0001])
    aralik = pd.Series([8, 4, 1])
    sonuc = funding.sekiz_saate_normallestir(oran, aralik)

    assert sonuc.iloc[0] == 0.0001
    assert sonuc.iloc[1] == 0.0002
    assert sonuc.iloc[2] == 0.0008


def test_negatif_oran_isaretini_korur():
    sonuc = funding.sekiz_saate_normallestir(pd.Series([-0.0005]), pd.Series([4]))
    assert sonuc.iloc[0] == -0.0010


def _funding_zip(satirlar: list[str]) -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as zf:
        zf.writestr("f.csv", "\n".join(satirlar))
    return tampon.getvalue()


def test_funding_ayristirma_ve_gercek_oran_olceklenmez():
    govde = _funding_zip(
        [
            "calc_time,funding_interval_hours,last_funding_rate",
            "1719792000000,4,0.00010000",
            "1719806400000,4,-0.00020000",
        ]
    )
    cerceve = funding._ay_cercevesi(govde)
    cerceve["oran_8h"] = funding.sekiz_saate_normallestir(
        cerceve["oran"], cerceve["aralik_saat"]
    )

    assert list(cerceve["aralik_saat"]) == [4, 4]
    assert cerceve["oran"].iloc[0] == 0.0001  # gercek odeme olceklenmemis kalir
    assert cerceve["oran_8h"].iloc[0] == 0.0002
    assert str(cerceve["odeme_zamani"].dt.tz) == "UTC"


def test_aralik_ozeti_sadece_kapsama_olcer():
    cerceve = funding._ay_cercevesi(
        _funding_zip(
            [
                "calc_time,funding_interval_hours,last_funding_rate",
                "1719792000000,8,0.00010000",
                "1719820800000,4,0.00010000",
            ]
        )
    )
    ozet = funding.aralik_ozeti(cerceve)
    assert set(ozet.columns) == {"aralik_saat", "kayit", "ilk", "son"}
    assert sorted(ozet["aralik_saat"]) == [4, 8]


def test_kapsama_ortusmeyi_dogru_bulur():
    f = funding._ay_cercevesi(
        _funding_zip(
            [
                "calc_time,funding_interval_hours,last_funding_rate",
                "1600000000000,8,0.0001",
            ]
        )
    )
    # Funding ani mum araliginin icinde kalir -> ortusme var
    mum_ici = pd.DataFrame(
        {"open_time": pd.to_datetime([1599990000000, 1600100000000], unit="ms", utc=True)}
    )
    # Mum gecmisi funding baslamadan cok once biter -> ortusme yok
    mum_uzak = pd.DataFrame(
        {"open_time": pd.to_datetime([1500000000000, 1500100000000], unit="ms", utc=True)}
    )

    assert funding.kapsama(f, mum_ici)["ortusme_var"] is True
    assert funding.kapsama(f, mum_uzak)["ortusme_var"] is False


def test_basliksiz_funding_dosyasi_da_okunur():
    """Eski dosyalarda basli satiri yok; sutun adlari disaridan verilir."""
    govde = _funding_zip(["1719792000000,8,0.00010000", "1719820800000,8,0.00020000"])
    cerceve = bv.zip_csv_oku(govde, bv.FUNDING_SUTUNLARI)
    assert list(cerceve.columns) == bv.FUNDING_SUTUNLARI
    assert len(cerceve) == 2
