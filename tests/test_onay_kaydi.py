"""Onay kaydi yazimi (CLAUDE.md §3.3, denetci bulgulari B7 ve F1 kapanis 8).

Satir, kayit dosyasinin sonuna degil tablonun son satirinin altina eklenmeli;
mevcut hicbir satir silinmemeli ya da degistirilmemeli. Ayni (hipotez, kume)
ikinci kez yazilamaz. Gercek kayit dosyasi yalnizca OKUNUR; testler onun gecici
kopyasi uzerinde calisir.

Onay kaydi ve kosu butunlugu turu (denetci KS3 D-B1, D-B3): `onay_kaydet(hipotez, kume, yol=...)` kalkti; kayit
yalnizca `onay_kosusu` ile ve yalnizca `config.ONAY_KAYDI`ya yazilir. Testler kayit yolunu
`split._test_kaydi_ayarla` ile yonlendirir. Kosu basina iki satir yazilir (BASLADI + BITTI/HATA); asagidaki
beklentiler buna gore guncellendi, iddialar (tablonun icine dusme, bayt bayt koruma, tekrarin reddi, satir sonu
stili, gecici dosya) ayni.
"""

from __future__ import annotations

import pytest

import config
from data import split
from onay_yardimcisi import gecici_kayit, kosu


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
    return gecici_kayit(hedef)


def _test_hipotezi(metin: str) -> str:
    """Gercek kayitta C1 ve C2 icin henuz bulunmayan bir hipotez adi (ilk F3 kosusundan sonra da calisir).

    Kapi sertlestirme turu 3 (denetci KS2 D-B1): hipotez adi yalnizca `config.HIPOTEZLER`den olabilir;
    onceki serbest test adlari ("TESTH0") artik reddedilir. Butun hipotezler kayitta ise test atlanir."""
    mevcut = split.kayittaki_kosular(metin)
    for hipotez in config.HIPOTEZLER:
        if (hipotez, "C1") not in mevcut and (hipotez, "C2") not in mevcut:
            return hipotez
    pytest.skip("Gercek kayitta her hipotez icin onay kosusu var; bos hipotez adi kalmadi.")


def test_gercek_kayit_dosyasinda_satir_tablonun_icine_duser(gercek_kopya):
    once = gercek_kopya.read_bytes().decode("utf-8")
    # Tablodaki mevcut satir sayisi sabitlenmez: ilk F3 kosusundan sonra gercek
    # kayitta satir olacak. Test yalnizca EKLENEN satirlari sayar.
    onceki = len(_tablo_satirlari(once))
    assert onceki >= 2  # en az baslik + ayirici
    hipotez = _test_hipotezi(once)

    with kosu(hipotez, "C1"):
        pass
    with kosu(hipotez, "C2"):
        pass

    sonra = gercek_kopya.read_bytes().decode("utf-8")
    tablo = _tablo_satirlari(sonra)
    assert len(tablo) == onceki + 4, "iki kosunun dort satiri tablonun kesintisiz parcasi olmali"
    assert all("| C1 |" in s and f"hipotez={hipotez}" in s for s in tablo[-4:-2])
    assert all("| C2 |" in s and f"hipotez={hipotez}" in s for s in tablo[-2:])

    # Tablonun disinda kalan aciklama cumlesi hala tablodan SONRA geliyor.
    son_tablo_satiri = sonra.splitlines().index(tablo[-1])
    assert any(s.strip() for s in sonra.splitlines()[son_tablo_satiri + 1 :])


def test_mevcut_satirlar_bayt_bayt_korunur(gercek_kopya):
    """Yalnizca ekleme: eklenen satirlar cikarilinca dosya eskisiyle bayt bayt ayni."""
    once = gercek_kopya.read_bytes().decode("utf-8")
    hipotez = _test_hipotezi(once)
    with kosu(hipotez, "C1"):
        pass
    sonra = gercek_kopya.read_bytes().decode("utf-8")

    once_satirlar = once.splitlines(keepends=True)
    sonra_satirlar = sonra.splitlines(keepends=True)
    eklenen = [s for s in sonra_satirlar if f"hipotez={hipotez}" in s]
    assert len(eklenen) == 2
    for s in eklenen:
        sonra_satirlar.remove(s)
    assert sonra_satirlar == once_satirlar


def test_gercek_kayitta_tekrar_kosu_reddedilir_dosya_degismez(gercek_kopya):
    hipotez = _test_hipotezi(gercek_kopya.read_text(encoding="utf-8"))
    with kosu(hipotez, "C1"):
        pass
    once = gercek_kopya.read_bytes()
    with pytest.raises(split.OnayTekrari):
        with kosu(hipotez, "C1"):
            pytest.fail("ikinci kosu acilmamali")
    assert gercek_kopya.read_bytes() == once


def test_crlf_dosyada_satir_sonu_stili_korunur(tmp_path):
    yol = gecici_kayit(tmp_path / "kayit.md")
    yol.write_bytes(b"# Kayit\r\n\r\n| Tarih (UTC) | Kume |\r\n|---|---|\r\n\r\nHenuz yok.\r\n")

    with kosu("H1", "C1"):
        pass

    ham = yol.read_bytes()
    assert b"\n" not in ham.replace(b"\r\n", b"")  # hicbir yalniz LF yok
    assert ham.startswith(b"# Kayit\r\n\r\n| Tarih (UTC) | Kume |\r\n|---|---|\r\n| ")


def test_tablo_dosyanin_son_satiriysa(tmp_path):
    yol = gecici_kayit(tmp_path / "kayit.md")
    yol.write_text("| Tarih (UTC) | Kume |\n|---|---|", encoding="utf-8")

    with kosu("H1", "C2"):
        pass

    metin = yol.read_text(encoding="utf-8")
    assert len(_tablo_satirlari(metin)) == 4
    assert metin.endswith(" |\n")


def test_tablosuz_dosyada_sona_eklenir(tmp_path):
    yol = gecici_kayit(tmp_path / "kayit.md")
    yol.write_text("bas", encoding="utf-8")
    with kosu("H1", "C1"):
        pass
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
        "| 2026-10-03 10:00:00 | C1 | a/b.py | " + "0" * 40 + " (temiz) | hipotez=H3 kosu=abc durum=BASLADI "
        "baslangic=2026-10-03T10:00:00Z |\n"
        "| 2026-10-03 11:00:00 | C1 | a/b.py | " + "0" * 40 + " (temiz) | hipotez=H3 kosu=abc durum=BITTI "
        "baslangic=2026-10-03T10:00:00Z bitis=2026-10-03T11:00:00Z sonuc=YETERSIZ GUC |\n"
        "\nHenuz onay kosusu yok. hipotez=YANILTICI\n"
    )
    assert split.kayittaki_kosular(metin) == {("H2", "C1"), ("H2", "C2"), ("H3", "C1")}
    son = split.kayit_satirlari(metin)[-1]
    assert son["durum"] == "BITTI" and son["sonuc"] == "YETERSIZ GUC" and son["kosu"] == "abc"
    assert son["commit"] == "0" * 40 and son["betik"] == "a/b.py"


def test_gecici_dosya_birakilmaz(gercek_kopya):
    with kosu(_test_hipotezi(gercek_kopya.read_text(encoding="utf-8")), "C1"):
        pass
    assert not (gercek_kopya.parent / (gercek_kopya.name + ".tmp")).exists()
    assert not (gercek_kopya.parent / ("." + gercek_kopya.name + ".kilit")).exists()
