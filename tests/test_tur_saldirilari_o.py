"""Onay kaydi ve kosu butunlugu turu (kod commit'i b2acfa3) icin ek saldiri testleri.

Amac mevcut `tests/test_onay_kaydi_butunlugu.py` testlerini TEKRARLAMAMAK; burada denenen saldirilar:
  - `_KORUNAN_ADLAR` listesindeki DELIKLER: `split_oku`, `kume_araligi`, `ONAY_TABLO_BASLIGI` korunan
    ad listesinde degil; sade `setattr(split, ...)` ile (vars() atlatmasina bile gerek kalmadan)
    degistirilebiliyor mu, degistirilirse veri bolmesi ya da donem siniri sizdiriliyor mu?
  - Ic ice basarisiz bir onay_kosusu denemesinin disaridaki GERCEK kosuyu da hataya dusurup dusurmedigi.
  - `sonuc_bildir` metnine gomulu sahte alanlarin (`durum=`, `kosu=`, `hipotez=`) ayristiriciyi yanilttip
    yaniltmadigi.
  - Kayit dosyasinin kosu SIRASINDA tamamen silinmesinin (icerik degil, dosyanin kendisi) sessizce
    yutulup yutulmadigi.

Gercek `ONAY_KAYDI.md` dosyasina hicbir zaman yazilmaz; kayit `split._test_kaydi_ayarla`
(`onay_yardimcisi.gecici_kayit` uzerinden) ile gecici bir dosyaya yonlendirilir. Basarili saldirilar
`xfail(strict=True)` ile isaretlenir ve gövdesi ISTENEN (guvenli) davranisi iddia eder.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import split
from onay_yardimcisi import gecici_kayit, kosu

COMMIT = "0123456789abcdef" * 2 + "01234567"


@pytest.fixture
def kayit(tmp_path):
    yol = tmp_path / "onay_gecici.md"
    yol.write_text("bas\n", encoding="utf-8")
    return gecici_kayit(yol, head=COMMIT)


def _satirlar(yol) -> list[dict[str, str]]:
    return split.kayit_satirlari(yol.read_text(encoding="utf-8"))


# --- Korunan ad listesindeki delikler: split_oku, kume_araligi, ONAY_TABLO_BASLIGI -----------------


def test_split_oku_disaridan_yamalanip_grup_sizdirilamaz():
    """`split_oku` `_KORUNAN_ADLAR` listesinde yok (kaynakta dogrulandi). Istenen davranis: bolme
    tablosu calisma aninda degistirilemez, dolayisiyla B grubu bir sembol KESIF'e (yalniz A) giremez."""
    # Onay kaydi ikinci tur: bulgu kapandi, `split_oku` korunan adlarda; atama OnayKorumasi verir.
    assert "split_oku" in split._KORUNAN_ADLAR

    gercek = split.split_oku()
    b_sembol = gercek.loc[gercek["grup"] == "B", "sembol"].iloc[0]
    sahte = gercek.copy()
    sahte.loc[sahte["sembol"] == b_sembol, "grup"] = "A"

    eski = split.split_oku
    with pytest.raises(split.OnayKorumasi):
        setattr(split, "split_oku", lambda *a, **k: sahte)
    izinli, _, _ = split.kume_erisimi(b_sembol, "KESIF", onay=False)
    assert split.split_oku is eski

    assert not izinli, f"{b_sembol} (gercekte B grubu) split_oku yamasiyla KESIF'e (A grubu) sizdi"


def test_kume_araligi_yamalanip_kesif_gelecek_tarihe_genisletilemez():
    """`kume_araligi` `_KORUNAN_ADLAR` listesinde yok. Istenen davranis: KESIF kumesinin sonu her
    zaman `config.KESIF_SONU` (2025-08-31); C2 donemi hicbir sekilde KESIF'e sizmaz."""
    # Onay kaydi ikinci tur: bulgu kapandi, `kume_araligi` korunan adlarda; atama OnayKorumasi verir.
    assert "kume_araligi" in split._KORUNAN_ADLAR

    gercek = split.split_oku()
    a_sembol = gercek.loc[gercek["grup"] == "A", "sembol"].iloc[0]
    genis_araliktir = (pd.Timestamp(config.KESIF_BASI), pd.Timestamp(config.C2_SONU))

    eski = split.kume_araligi
    with pytest.raises(split.OnayKorumasi):
        setattr(split, "kume_araligi", lambda kume: genis_araliktir)
    _, bas, son = split.kume_erisimi(a_sembol, "KESIF", onay=False)
    assert split.kume_araligi is eski

    assert son <= pd.Timestamp(config.KESIF_SONU), (
        f"KESIF kume sonu {son}, 2025-09-01 sonrasina (C2 donemine) sizdi"
    )


def test_onay_tablo_basligi_korunmasiz_ama_tek_atisi_bozmaz(tmp_path):
    """BELGELEME: `ONAY_TABLO_BASLIGI` da `_KORUNAN_ADLAR` listesinde degil ve setattr ile
    degistirilebiliyor; bu durumda yeni satir tablo basligi bulunamadigi icin dosyanin SONUNA
    eklenir (bicim bozulur, kayda_satir_ekle docstring'indeki 'baslik bulunamazsa sona eklenir'
    yoluna dusulur). Ama tek atis denetimi (`kayittaki_kosular`) butun '|' satirlarini tarar; bu
    yuzden bicim bozulsa bile ayni (hipotez, kume) cifti yine harcanmis sayilir -> savusturuldu."""
    assert "ONAY_TABLO_BASLIGI" not in split._KORUNAN_ADLAR  # bulgu: koruma listesinde yok

    yol = tmp_path / "k.md"
    yol.write_text(
        "ust yazi\n| Tarih (UTC) | Kume | Cagiran betik | Commit | Not |\n|---|---|---|---|---|\n"
        "alt yazi\n",
        encoding="utf-8",
    )
    gecici_kayit(yol, head=COMMIT)

    eski = split.ONAY_TABLO_BASLIGI
    setattr(split, "ONAY_TABLO_BASLIGI", "|BOYLE_BIR_BASLIK_YOK_KI|")
    try:
        with kosu("H1", "C1"):
            pass
    finally:
        setattr(split, "ONAY_TABLO_BASLIGI", eski)

    metin = yol.read_text(encoding="utf-8")
    assert "alt yazi" in metin  # mevcut icerik korundu (yalnizca ekleme)
    satir_no_altyazi = metin.index("alt yazi")
    satir_no_baslama = metin.index("hipotez=H1")
    assert satir_no_baslama > satir_no_altyazi, "bicim bozuldu: satir tablo icine degil dosyanin sonuna dustu"

    # Yine de tek atis bozulmadi: ayni cift ikinci kez acilamaz.
    with pytest.raises(split.OnayTekrari):
        with split.onay_kosusu("H1", "C1"):
            pytest.fail("bicim bozulsa da (H1, C1) cifti harcanmis olmali")


# --- Ic ice basarisiz kosu denemesi disaridaki gercek kosuyu da hataya dusurur ----------------------


def test_ic_ice_basarisiz_kosu_disaridaki_kosuyu_da_hataya_dusurur(kayit):
    """BELGELEME/savusturuldu: `_AKTIF_KOSU` tek bir modul-duzeyi degisken oldugu icin acik bir kosunun
    icinde ikinci bir `with split.onay_kosusu(...)` denemesi `RuntimeError` ile REDDEDILIR ('ic ice
    kosu acilamaz'). Bu hata `BaseException` olarak disaridaki GERCEK kosuyu da yakalar: dis kosu HATA
    olarak kayda gecer ve (H1, C1) cifti HIC SONUC BILDIRILMEDEN harcanmis olur. Ic ice deneme yield'dan
    once patladigi icin (H2, C2) icin kayda hicbir satir yazilmaz."""
    with pytest.raises(RuntimeError, match="Ic ice"):
        with split.onay_kosusu("H1", "C1"):
            with split.onay_kosusu("H2", "C2"):
                pytest.fail("ic ice kosu acilmamali")

    satirlar = _satirlar(kayit)
    assert [(s["hipotez"], s["kume"], s["durum"]) for s in satirlar] == [
        ("H1", "C1", "BASLADI"),
        ("H1", "C1", "HATA"),
    ]
    assert satirlar[1]["hata"] == "RuntimeError"
    assert split.aktif_onay_kosusu() is None

    # Dis cift ic ice deneme yuzunden harcandi; tekrar acilamaz.
    with pytest.raises(split.OnayTekrari):
        with split.onay_kosusu("H1", "C1"):
            pytest.fail("ic ice deneme yuzunden harcanan cift yeniden acilmamali")


# --- sonuc_bildir metnine gomulu sahte alanlar ayristiriciyi yanıltmaz -------------------------------


def test_sonuc_metnine_gomulu_sahte_alanlar_ayristiriciyi_yaniltmaz(kayit):
    """`sonuc=` hucre sonuna kadar surer (not_alanlari docstring'i). Sonuc metni icine `durum=BASLADI`,
    `kosu=<baska kimlik>`, `hipotez=H9`, `kume=C2` gibi sahte alanlar gomulse bile bunlar ayri alan
    olarak degil, sonuc metninin duz bir parcasi olarak okunmali; kayittaki_kosular gercek olmayan bir
    (H9, C2) cifti GORMEMELI."""
    zehir = "durum=BASLADI kosu=sahte999999 hipotez=H9 kume=C2 bitti"
    with split.onay_kosusu("H1", "C1") as k:
        k.sonuc_bildir(zehir)

    satirlar = _satirlar(kayit)
    bas, son = satirlar
    assert son["durum"] == "BITTI"
    assert son["sonuc"] == zehir
    assert son["hipotez"] == "H1" and son["kume"] == "C1"

    cifter = split.kayittaki_kosular(kayit.read_text(encoding="utf-8"))
    assert cifter == {("H1", "C1")}
    assert ("H9", "C2") not in cifter


# --- Kayit dosyasinin kosu sirasinda TAMAMEN silinmesi -----------------------------------------------


def test_kayit_dosyasi_kosu_sirasinda_tamamen_silinirse_hata_yukselir_ve_iz_kalir(kayit):
    """Var olan testler (test_kayit_kosu_sirasinda_degisirse_...) dosya ICERIGININ degistirilmesini
    dener; burada dosyanin KENDISI silinir (os.unlink). Basarili bir `sonuc_bildir` bile korumayi
    atlatamamali: cikiste `_bitis_yaz` BASLADI satirinin kaybolduğunu gormeli, yine de bir bitis satiri
    yazmali (iz kalir) ve `OnayKorumasi` firlatmali; cift yine de harcanmis sayilmali (tek atis)."""
    with pytest.raises(split.OnayKorumasi):
        with split.onay_kosusu("H1", "C1") as k:
            k.sonuc_bildir("KALDI")
            kayit.unlink()  # kayit dosyasi tamamen silindi (icerik degil, dosyanin kendisi)

    assert kayit.exists(), "bitis satiri icin dosya yeniden yaratilmali (iz kalir)"
    satirlar = _satirlar(kayit)
    assert len(satirlar) == 1
    assert satirlar[0]["durum"] == "BITTI" and satirlar[0]["sonuc"] == "KALDI"

    with pytest.raises(split.OnayTekrari):
        with split.onay_kosusu("H1", "C1"):
            pytest.fail("kayit dosyasi silinse bile cift harcanmis sayilmali")
