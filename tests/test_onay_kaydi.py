"""Onay kaydi yazimi (CLAUDE.md §3.3, denetci bulgusu B7).

Satir, kayit dosyasinin sonuna degil tablonun son satirinin altina eklenmeli;
mevcut hicbir satir silinmemeli ya da degistirilmemeli. Gercek kayit dosyasi
yalnizca OKUNUR; testler onun gecici kopyasi uzerinde calisir.
"""

from __future__ import annotations

import pytest

import config
from data import split


def _tablo_satirlari(metin: str) -> list[str]:
    """Baslik satirindan itibaren kesintisiz '|' ile baslayan satirlar."""
    satirlar = metin.splitlines()
    bas = next(i for i, s in enumerate(satirlar) if s.startswith(split.ONAY_TABLO_BASLIGI))
    tablo = []
    for s in satirlar[bas:]:
        if not s.startswith("|"):
            break
        tablo.append(s)
    return tablo


@pytest.fixture
def gercek_kopya(tmp_path):
    kaynak = config.ONAY_KAYDI
    hedef = tmp_path / "ONAY_KAYDI.md"
    hedef.write_bytes(kaynak.read_bytes())
    return hedef


def test_gercek_kayit_dosyasinda_satir_tablonun_icine_duser(gercek_kopya):
    once_bayt = gercek_kopya.read_bytes()
    once = once_bayt.decode("utf-8")
    # Tablodaki mevcut satir sayisi sabitlenmez: ilk F3 kosusundan sonra gercek
    # kayitta satir olacak. Test yalnizca EKLENEN satirlari sayar.
    onceki = len(_tablo_satirlari(once))
    assert onceki >= 2  # en az baslik + ayirici

    split.onay_kaydet("C1", "BBUSDT", "bar=4h", yol=gercek_kopya)
    split.onay_kaydet("C2", "AAUSDT", "kaynak=funding", yol=gercek_kopya)

    sonra = gercek_kopya.read_bytes().decode("utf-8")
    tablo = _tablo_satirlari(sonra)
    assert len(tablo) == onceki + 2, "iki onay satiri tablonun kesintisiz parcasi olmali"
    assert "| C1 |" in tablo[-2] and "BBUSDT" in tablo[-2]
    assert "| C2 |" in tablo[-1] and "kaynak=funding" in tablo[-1]

    # Tablonun disinda kalan aciklama cumlesi hala tablodan SONRA geliyor.
    son_tablo_satiri = sonra.splitlines().index(tablo[-1])
    assert any(s.strip() for s in sonra.splitlines()[son_tablo_satiri + 1 :])


def test_mevcut_satirlar_bayt_bayt_korunur(gercek_kopya):
    """Yalnizca ekleme: eklenen satirlar cikarilinca dosya eskisiyle bayt bayt ayni."""
    once = gercek_kopya.read_bytes().decode("utf-8")
    split.onay_kaydet("C1", "BBUSDT", "bar=4h", yol=gercek_kopya)
    sonra = gercek_kopya.read_bytes().decode("utf-8")

    once_satirlar = once.splitlines(keepends=True)
    sonra_satirlar = sonra.splitlines(keepends=True)
    eklenen = [s for s in sonra_satirlar if "BBUSDT" in s]
    assert len(eklenen) == 1
    sonra_satirlar.remove(eklenen[0])
    assert sonra_satirlar == once_satirlar


def test_crlf_dosyada_satir_sonu_stili_korunur(tmp_path):
    yol = tmp_path / "kayit.md"
    yol.write_bytes(b"# Kayit\r\n\r\n| Tarih (UTC) | Kume |\r\n|---|---|\r\n\r\nHenuz yok.\r\n")

    split.onay_kaydet("C1", "BBUSDT", yol=yol)

    ham = yol.read_bytes()
    assert b"\n" not in ham.replace(b"\r\n", b"")  # hicbir yalniz LF yok
    assert ham.startswith(b"# Kayit\r\n\r\n| Tarih (UTC) | Kume |\r\n|---|---|\r\n| ")


def test_tablo_dosyanin_son_satiriysa(tmp_path):
    yol = tmp_path / "kayit.md"
    yol.write_text("| Tarih (UTC) | Kume |\n|---|---|", encoding="utf-8")

    split.onay_kaydet("C2", "AAUSDT", yol=yol)

    metin = yol.read_text(encoding="utf-8")
    assert len(_tablo_satirlari(metin)) == 3
    assert metin.endswith(" |\n")


def test_tablosuz_dosyada_sona_eklenir(tmp_path):
    yol = tmp_path / "kayit.md"
    yol.write_text("bas", encoding="utf-8")
    split.onay_kaydet("C1", "BBUSDT", yol=yol)
    metin = yol.read_text(encoding="utf-8")
    assert metin.startswith("bas\n| ")


def test_kayda_satir_ekle_saftir():
    metin = "a\n| Tarih (UTC) | x |\n|---|---|\n\nson\n"
    sonuc = split.kayda_satir_ekle(metin, "| yeni | satir |")
    assert metin == "a\n| Tarih (UTC) | x |\n|---|---|\n\nson\n"
    assert sonuc == "a\n| Tarih (UTC) | x |\n|---|---|\n| yeni | satir |\n\nson\n"


def test_gecici_dosya_birakilmaz(gercek_kopya):
    split.onay_kaydet("C1", "BBUSDT", yol=gercek_kopya)
    assert not (gercek_kopya.parent / (gercek_kopya.name + ".tmp")).exists()
