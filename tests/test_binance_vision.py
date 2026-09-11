"""Ortak erisim katmani testleri. Ag kullanilmaz."""

from __future__ import annotations

import hashlib
import io
import zipfile

import pandas as pd
import pytest

from data import binance_vision as bv


def test_dosya_ayi_cozumleme():
    assert bv.dosya_ayi("a/b/SRMUSDT/4h/SRMUSDT-4h-2024-05.zip") == "2024-05"
    assert bv.dosya_ayi("x/BTCUSDT-fundingRate-2020-01.zip") == "2020-01"


def test_ay_araligi_kapali():
    assert list(bv.ay_araligi("2020-11", "2021-02")) == ["2020-11", "2020-12", "2021-01", "2021-02"]
    assert list(bv.ay_araligi("2021-03", "2021-03")) == ["2021-03"]


def test_sayi_mi_baslik_ayrimi():
    assert bv._sayi_mi("1577836800000") is True
    assert bv._sayi_mi("open_time") is False


def test_zip_csv_baslik_otomatik_algilanir():
    satir = "1577836800000,1,2,3,4,5,1577851199999,6,7,8,9,0"

    def paketle(icerik: str) -> bytes:
        tampon = io.BytesIO()
        with zipfile.ZipFile(tampon, "w") as zf:
            zf.writestr("k.csv", icerik)
        return tampon.getvalue()

    basliksiz = bv.zip_csv_oku(paketle(satir), bv.MUM_SUTUNLARI)
    baslikli = bv.zip_csv_oku(paketle(",".join(bv.MUM_SUTUNLARI) + "\n" + satir), bv.MUM_SUTUNLARI)

    assert len(basliksiz) == 1 and len(baslikli) == 1
    assert list(basliksiz.columns) == list(baslikli.columns) == bv.MUM_SUTUNLARI


def test_checksum_uyusmazligi_hata_verir(monkeypatch):
    govde = b"sahte-zip-icerigi"

    class SahteCevap:
        def __init__(self, icerik=b"", metin=""):
            self.content = icerik
            self.text = metin
            self.status_code = 200

        def raise_for_status(self):
            pass

    def sahte_iste(url, **_):
        if url.endswith(".CHECKSUM"):
            return SahteCevap(metin="0" * 64 + "  dosya.zip")
        return SahteCevap(icerik=govde)

    monkeypatch.setattr(bv, "_iste", sahte_iste)
    with pytest.raises(ValueError, match="Checksum"):
        bv.zip_indir("a/b.zip")

    # Dogru checksum ile sorunsuz gecmeli
    dogru = hashlib.sha256(govde).hexdigest()

    def sahte_iste_dogru(url, **_):
        if url.endswith(".CHECKSUM"):
            return SahteCevap(metin=f"{dogru}  dosya.zip")
        return SahteCevap(icerik=govde)

    monkeypatch.setattr(bv, "_iste", sahte_iste_dogru)
    assert bv.zip_indir("a/b.zip") == govde


def test_onbellek_yaz_oku_dongusu(tmp_path):
    yol = tmp_path / "alt" / "x.parquet"
    cerceve = pd.DataFrame({"a": [1, 2, 3]})

    assert bv.onbellekten_oku(yol) is None
    bv.onbellege_yaz(cerceve, yol)
    pd.testing.assert_frame_equal(bv.onbellekten_oku(yol), cerceve)
    assert not yol.with_suffix(yol.suffix + ".tmp").exists()  # gecici dosya birakilmaz
