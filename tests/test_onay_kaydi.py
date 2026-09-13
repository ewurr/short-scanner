"""Onay kaydi yazimi (CLAUDE.md §3.3, denetci bulgulari B7 ve F1 kapanis 8).

Satir, kayit dosyasinin sonuna degil tablonun son satirinin altina eklenmeli;
mevcut hicbir satir silinmemeli ya da degistirilmemeli. Kayit kosu basina tek
satirdir ve ayni (hipotez, kume) ikinci kez yazilamaz. Gercek kayit dosyasi
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


def _test_hipotezi(metin: str, onek: str = "TESTH") -> str:
    """Gercek kayitta henuz bulunmayan bir hipotez adi (ilk F3 kosusundan sonra da calisir)."""
    mevcut = {h for h, _ in split.kayittaki_kosular(metin)}
    i = 0
    while f"{onek}{i}" in mevcut:
        i += 1
    return f"{onek}{i}"


def test_gercek_kayit_dosyasinda_satir_tablonun_icine_duser(gercek_kopya):
    once = gercek_kopya.read_bytes().decode("utf-8")
    # Tablodaki mevcut satir sayisi sabitlenmez: ilk F3 kosusundan sonra gercek
    # kayitta satir olacak. Test yalnizca EKLENEN satirlari sayar.
    onceki = len(_tablo_satirlari(once))
    assert onceki >= 2  # en az baslik + ayirici
    hipotez = _test_hipotezi(once)

    split.onay_kaydet(hipotez, "C1", yol=gercek_kopya)
    split.onay_kaydet(hipotez, "C2", yol=gercek_kopya)

    sonra = gercek_kopya.read_bytes().decode("utf-8")
    tablo = _tablo_satirlari(sonra)
    assert len(tablo) == onceki + 2, "iki onay satiri tablonun kesintisiz parcasi olmali"
    assert "| C1 |" in tablo[-2] and f"hipotez={hipotez}" in tablo[-2]
    assert "| C2 |" in tablo[-1] and f"hipotez={hipotez}" in tablo[-1]

    # Tablonun disinda kalan aciklama cumlesi hala tablodan SONRA geliyor.
    son_tablo_satiri = sonra.splitlines().index(tablo[-1])
    assert any(s.strip() for s in sonra.splitlines()[son_tablo_satiri + 1 :])


def test_mevcut_satirlar_bayt_bayt_korunur(gercek_kopya):
    """Yalnizca ekleme: eklenen satir cikarilinca dosya eskisiyle bayt bayt ayni."""
    once = gercek_kopya.read_bytes().decode("utf-8")
    hipotez = _test_hipotezi(once)
    split.onay_kaydet(hipotez, "C1", yol=gercek_kopya)
    sonra = gercek_kopya.read_bytes().decode("utf-8")

    once_satirlar = once.splitlines(keepends=True)
    sonra_satirlar = sonra.splitlines(keepends=True)
    eklenen = [s for s in sonra_satirlar if f"hipotez={hipotez}" in s]
    assert len(eklenen) == 1
    sonra_satirlar.remove(eklenen[0])
    assert sonra_satirlar == once_satirlar


def test_gercek_kayitta_tekrar_kosu_reddedilir_dosya_degismez(gercek_kopya):
    hipotez = _test_hipotezi(gercek_kopya.read_text(encoding="utf-8"))
    split.onay_kaydet(hipotez, "C1", yol=gercek_kopya)
    once = gercek_kopya.read_bytes()
    with pytest.raises(split.OnayTekrari):
        split.onay_kaydet(hipotez, "C1", yol=gercek_kopya)
    assert gercek_kopya.read_bytes() == once


def test_crlf_dosyada_satir_sonu_stili_korunur(tmp_path):
    yol = tmp_path / "kayit.md"
    yol.write_bytes(b"# Kayit\r\n\r\n| Tarih (UTC) | Kume |\r\n|---|---|\r\n\r\nHenuz yok.\r\n")

    split.onay_kaydet("H1", "C1", yol=yol)

    ham = yol.read_bytes()
    assert b"\n" not in ham.replace(b"\r\n", b"")  # hicbir yalniz LF yok
    assert ham.startswith(b"# Kayit\r\n\r\n| Tarih (UTC) | Kume |\r\n|---|---|\r\n| ")


def test_tablo_dosyanin_son_satiriysa(tmp_path):
    yol = tmp_path / "kayit.md"
    yol.write_text("| Tarih (UTC) | Kume |\n|---|---|", encoding="utf-8")

    split.onay_kaydet("H1", "C2", yol=yol)

    metin = yol.read_text(encoding="utf-8")
    assert len(_tablo_satirlari(metin)) == 3
    assert metin.endswith(" |\n")


def test_tablosuz_dosyada_sona_eklenir(tmp_path):
    yol = tmp_path / "kayit.md"
    yol.write_text("bas", encoding="utf-8")
    split.onay_kaydet("H1", "C1", yol=yol)
    metin = yol.read_text(encoding="utf-8")
    assert metin.startswith("bas\n| ")


def test_kayda_satir_ekle_saftir():
    metin = "a\n| Tarih (UTC) | x |\n|---|---|\n\nson\n"
    sonuc = split.kayda_satir_ekle(metin, "| yeni | satir |")
    assert metin == "a\n| Tarih (UTC) | x |\n|---|---|\n\nson\n"
    assert sonuc == "a\n| Tarih (UTC) | x |\n|---|---|\n| yeni | satir |\n\nson\n"


def test_kayittaki_kosular_ayristirilir():
    metin = (
        "| Tarih (UTC) | Kume | Cagiran betik | Commit | Not |\n|---|---|---|---|---|\n"
        "| 2026-10-01 10:00:00 | C1 | onay.py | abcdef012345 (temiz) | hipotez=H2 |\n"
        "| 2026-10-02 10:00:00 | C2 | onay.py | abcdef012345 (KIRLI) | hipotez=H2 |\n"
        "\nHenuz onay kosusu yok. hipotez=YANILTICI\n"
    )
    assert split.kayittaki_kosular(metin) == {("H2", "C1"), ("H2", "C2")}


def test_gecici_dosya_birakilmaz(gercek_kopya):
    split.onay_kaydet(_test_hipotezi(gercek_kopya.read_text(encoding="utf-8")), "C1", yol=gercek_kopya)
    assert not (gercek_kopya.parent / (gercek_kopya.name + ".tmp")).exists()
