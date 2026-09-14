"""F1 kapanis saldirilari: `funding.pozisyon_fundingi`, `pencere.cikis_ani` ve
`pencere.cikis_bari` uzerine on-kayit revizyon 6 (ve kullanici karari
"Revizyon 7") kurallarini kirmaya calisan ek testler.

Bu dosya `tests/test_pozisyon_fundingi.py` ve `tests/test_ileri_kayma_siniri.py`
dosyalarindaki saldirilari TEKRARLAMAZ; yeni acilar dener:
  - kume sonuna ODEME_TOLERANSI kadar yakin cikislarda kume siniri kontrolu,
  - giris/cikis tolerans esiklerinin (59.999...s / 60s) tam sinirda davranisi,
  - bos, sirasiz ve saat dilimsiz funding cercevesi,
  - `cikis_ani`nin bilinmeyen `fiyat_alani` ile elle kurulmus CikisSonucu'nu reddetmesi,
  - kume siniri ile ileri kayma sinirinin AYNI ANDA asilmasinda hangi hatanin
    once geldigi,
  - `birincil_ufuk` olarak numpy tamsayisi,
  - gunluk barda funding ve ileri kaymali cikisin birlikte dogru calismasi.

Her testin docstring'i saldirinin ne oldugunu, beklenen dogru davranisi ve
dayandigi on-kayit/CLAUDE.md maddesini yazar. Basarisiz (kirmizi) bir test
KOD DUZELTILMEDEN birakilir; bu bir bulgudur.

Kume sonuna yakin cikisla ilgili iki test ilk kosuda basarisiz oldu. Kullanici
karari (rev.5 zamanla karar ilkesi) uzerine beklentileri tersine cevrildi;
gerekce testlerin docstring'indedir.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import config
from data import funding, pencere

DORT_SAAT = pd.Timedelta(hours=4)
BIR_DK = pd.Timedelta(minutes=1)
SINIRSIZ = dict(kume_baslangic=None, kume_bitis=None, donem_baslangic=None, donem_bitis=None)


def _ts(metin: str) -> pd.Timestamp:
    return pd.Timestamp(metin, tz="UTC")


def _funding(bas: str, bitis: str, aralik_saat: int = 8, oran: float = 1e-4) -> pd.DataFrame:
    zaman = pd.date_range(bas, bitis, freq=f"{aralik_saat}h", tz="UTC")
    cerceve = pd.DataFrame({"odeme_zamani": zaman, "aralik_saat": float(aralik_saat), "oran": oran})
    cerceve["oran_8h"] = funding.sekiz_saate_normallestir(cerceve["oran"], cerceve["aralik_saat"])
    return cerceve


def _oran_ata(fund: pd.DataFrame, zaman: pd.Timestamp, oran: float) -> None:
    fund.loc[fund["odeme_zamani"] == zaman, "oran"] = oran


def _cikis(zaman: pd.Timestamp, fiyat_alani: str = "close") -> pencere.CikisSonucu:
    return pencere.CikisSonucu(
        indeks=0, zaman=zaman, fiyat_alani=fiyat_alani, kaydi=fiyat_alani == "open", kirpildi=False
    )


def _fon(fund, giris, cikis, bar=config.BAR_4H, **sinirlar):
    sinirlar = {**SINIRSIZ, **sinirlar}
    return funding.pozisyon_fundingi(fund, giris, cikis, bar, **sinirlar)


# --- 1) Kume sonuna ODEME_TOLERANSI kadar yakin cikis --------------------------


@pytest.mark.parametrize("sinirdaki_odeme", ["yok", "kume_icinde", "kume_disinda"])
def test_kume_sonuna_bir_dakikadan_yakin_cikis_zamanla_reddedilir(sinirdaki_odeme):
    """Saldiri: cikis ani kume sonundan 30 saniye once; kume sonuna yakin
    gercek bir odeme olsa da olmasa da hukum ayni olmali.

    Ilk surumde bu test "reddedilmemeli" bekliyordu ve basarisiz oldu. Kullanici
    karariyla TERSINE CEVRILDI; dogru davranis mevcut davranistir:
      - Rev.6: 1 dakikadan kucuk kayma ayni an sayilir. Cikis anindan sonraki
        1 dakikaya dusen bir odeme CIKIS ANINDAKI odemedir. Burada o aralik kume
        sonunu asar; boyle bir odeme kume disina duser.
      - Rev.5 ilkesi (bilincli): kume sinirina ZAMANLA karar verilir, verideki
        durumla verilmez. `funding_yukle` veriyi kume sinirinda keser; kume
        disindaki odemenin veride gorunmemesi o odemenin olmadigini gostermez.
        Hukmu o anda bir odeme bulunup bulunmamasina baglamak, karari tam da
        gorulmemesi gereken veriye baglamak olurdu.
    Bu yuzden olay olusmaz (`KumeSiniriHatasi`). Gercek kume sonu 23:59:59 ve
    cikis anlari bar izgarasinda oldugu icin bu durum gercek veride dogmaz.
    Sinirdaki odemenin varligi, yoklugu ya da konumu hukmu degistirmez.
    """
    fund = _funding("2021-01-01", "2021-01-10")  # odemeler 00:00, 08:00, 16:00
    kume_son = _ts("2021-01-05 12:00:00")
    if sinirdaki_odeme != "yok":
        an = kume_son + pd.Timedelta(seconds=-10 if sinirdaki_odeme == "kume_icinde" else 20)
        ek = pd.DataFrame({"odeme_zamani": [an], "aralik_saat": [8.0], "oran": [1e-4]})
        fund = pd.concat([fund, ek]).sort_values("odeme_zamani", ignore_index=True)
    giris = _ts("2021-01-05 00:00")
    cikis = _cikis(kume_son - pd.Timedelta(seconds=30), "open")

    with pytest.raises(pencere.KumeSiniriHatasi):
        _fon(fund, giris, cikis, kume_bitis=kume_son)


def test_kume_sonuna_tam_esit_cikis_zamanla_reddedilir():
    """Saldiri: cikis ani kume sonuna TAM ESIT.

    Ilk surumde "reddedilmemeli" bekliyordu; kullanici karariyla tersine
    cevrildi (gerekce yukaridaki testte). Cikis anindaki odeme [son, son + 1 dk)
    araligindadir ve bu araligin kume sonundan sonraki kismi kume disidir; karar
    zamanla verilir, olay olusmaz. Kume sonundan tam 1 dakika onceki cikis ise
    kabul edilir: cikis anindaki odeme araligi tamamen kume icindedir.
    """
    fund = _funding("2021-01-01", "2021-01-10")
    giris = _ts("2021-01-05 00:00")
    kume_son = _ts("2021-01-05 12:00:00")

    with pytest.raises(pencere.KumeSiniriHatasi):
        _fon(fund, giris, _cikis(kume_son, "open"), kume_bitis=kume_son)

    sinirda = _cikis(kume_son - BIR_DK, "open")
    assert _fon(fund, giris, sinirda, kume_bitis=kume_son) == pytest.approx(1e-4)  # yalnizca 08:00


# --- 2) Giris/cikis tolerans esiklerinin tam siniri ----------------------------


def test_giris_tarafi_tam_60_saniyede_dahil_59_999_de_haric():
    """Saldiri: giris ile bir odeme arasindaki farki tam tolerans esiginde
    (60s) ve esigin hemen altinda (59.999999999s) test eder.

    On-kayit §4 rev.6: "1 dakikadan KUCUK kayma ayni an sayilir" ve giris
    anindaki odeme HARICTIR. Yani:
      - fark < 60s  -> giris ile "ayni an" -> HARIC (giris anindaki odeme).
      - fark >= 60s -> ayri an -> DAHIL (giristen sonraki odeme).
    Esigin kendisi (tam 60s) "kucuk" olmadigi icin dahil olmalidir.
    """
    T = _ts("2021-01-05 08:00:00")
    fund = _funding("2021-01-01", "2021-01-10")
    _oran_ata(fund, T, 9e-4)  # isaretli odeme
    cikis = _cikis(T + pd.Timedelta(hours=1), "open")  # dar pencere, sadece T etkilenir

    # Fark tam 60s: giris = T - 60s -> DAHIL
    giris_dahil = T - BIR_DK
    assert _fon(fund, giris_dahil, cikis) == pytest.approx(9e-4)

    # Fark 60s'nin az altinda: giris = T - (60s - 1ns) -> ayni an -> HARIC
    giris_haric = T - (BIR_DK - pd.Timedelta(nanoseconds=1))
    assert _fon(fund, giris_haric, cikis) == pytest.approx(0.0)


def test_cikis_tarafi_59_999_saniyede_dahil_tam_60_da_haric():
    """Saldiri: cikis ani ile bir odeme arasindaki farki tam tolerans esiginde
    (60s) ve esigin hemen altinda test eder.

    On-kayit §4 rev.6: cikis anindaki odeme DAHILDIR ve 60s'den kucuk kayma
    ayni an sayilir. Yani:
      - fark < 60s  -> cikisla "ayni an" -> DAHIL (cikis anindaki odeme).
      - fark >= 60s -> odeme cikistan SONRA -> HARIC (henuz gerceklesmemis).
    """
    T = _ts("2021-01-05 08:00:00")
    fund = _funding("2021-01-01", "2021-01-10")
    _oran_ata(fund, T, 9e-4)
    giris = T - pd.Timedelta(hours=2)  # dar pencere, sadece T etkilenir

    # Fark 60s'nin az altinda: son_an = T - (60s - 1ns) -> ayni an -> DAHIL
    son_an_dahil = T - (BIR_DK - pd.Timedelta(nanoseconds=1))
    assert _fon(fund, giris, _cikis(son_an_dahil, "open")) == pytest.approx(9e-4)

    # Fark tam 60s: son_an = T - 60s -> ayri an, odeme henuz gerceklesmemis -> HARIC
    son_an_haric = T - BIR_DK
    assert _fon(fund, giris, _cikis(son_an_haric, "open")) == pytest.approx(0.0)


# --- 3) Bos, sirasiz, saat dilimsiz funding cercevesi --------------------------


def test_bos_funding_cercevesinde_nan_doner_hata_firlatmaz():
    """Saldiri: tamamen bos funding cercevesi (sutunlar var, satir yok) verilir.

    Beklenen: hicbir odeme kaydi olmadigi icin tamlik kontrolu saglanamaz ve
    sonuc NaN olmalidir (on-kayit §2 rev.3 tamlik sarti); kod crash etmemeli.
    """
    bos = pd.DataFrame(columns=["odeme_zamani", "aralik_saat", "oran", "oran_8h"])
    bos["odeme_zamani"] = pd.to_datetime(bos["odeme_zamani"], utc=True)
    deger = _fon(bos, _ts("2021-01-05 00:00"), _cikis(_ts("2021-01-05 20:00")))
    assert pd.isna(deger)


def test_sirasiz_funding_cercevesi_hata_verir():
    """Saldiri: funding cercevesi zaman sirasina gore SIRALANMAMIS verilir
    (ör. ters sirali ya da karistirilmis).

    Beklenen (`pencere.ZamanDizisiHatasi` docstring'i, on-kayit §2 rev.3):
    sirasiz dizi bir VERI BOZUKLUGUDUR ve sessizce NaN'a cevrilmez; hata
    yuzeye cikmalidir. Sessizce yanlis (ya da sessizce tam) bir sonuc
    dondururse kural delinmis olur.
    """
    fund = _funding("2021-01-01", "2021-01-10")
    karisik = fund.sample(frac=1.0, random_state=20260911).reset_index(drop=True)
    with pytest.raises(pencere.ZamanDizisiHatasi):
        _fon(karisik, _ts("2021-01-05 00:00"), _cikis(_ts("2021-01-05 20:00")))

    ters = fund.iloc[::-1].reset_index(drop=True)
    with pytest.raises(pencere.ZamanDizisiHatasi):
        _fon(ters, _ts("2021-01-05 00:00"), _cikis(_ts("2021-01-05 20:00")))


def test_saat_dilimsiz_odeme_zamani_hata_verir():
    """Saldiri: `odeme_zamani` sutunu saat dilimsiz (tz-naive) verilir.

    Beklenen (CLAUDE.md §5, `pencere._zaman_dizisi_dogrula`): tum zaman
    damgalari UTC olmalidir; saat dilimsiz bir dizi UTC'li bir sinirla
    (giris/cikis) karsilastirilinca sessizce hep NaN/False dondurup calismayi
    yanlislikla "negatif sonuc" gibi gosterebilirdi. Bu yuzden acikca hata
    verilmelidir, NaN degil.
    """
    fund = _funding("2021-01-01", "2021-01-10")
    fund["odeme_zamani"] = fund["odeme_zamani"].dt.tz_localize(None)
    with pytest.raises(pencere.ZamanDizisiHatasi):
        _fon(fund, _ts("2021-01-05 00:00"), _cikis(_ts("2021-01-05 20:00")))


# --- 4) `cikis_ani` elle kurulmus tutarsiz CikisSonucu -------------------------


def test_cikis_ani_bilinmeyen_fiyat_alani_reddedilir():
    """Saldiri: analiz kodu `cikis_bari` disinda elle bir `CikisSonucu` kurup
    `fiyat_alani` alanina "close"/"open" disinda bir deger yazarsa ne olur?

    Beklenen: `cikis_ani` (ve onun uzerinden `pozisyon_fundingi`) bunu acikca
    reddetmeli (ValueError), sessizce "close" ya da "open" gibi davranmamali;
    aksi halde cikis ani yanlis hesaplanip bir funding odemesi kacirilir ya da
    fazladan sayilir (on-kayit §4 rev.6).
    """
    bozuk = pencere.CikisSonucu(
        indeks=0, zaman=_ts("2021-01-05 20:00"), fiyat_alani="vwap", kaydi=False, kirpildi=False
    )
    with pytest.raises(ValueError):
        pencere.cikis_ani(bozuk, config.BAR_4H)

    fund = _funding("2021-01-01", "2021-01-10")
    with pytest.raises(ValueError):
        _fon(fund, _ts("2021-01-05 00:00"), bozuk)


# --- 5) Kume siniri ile ileri kayma sinirinin ayni anda asilmasi ---------------


def test_kume_ve_ileri_kayma_siniri_ayni_anda_asilinca_kume_hatasi_once_gelir():
    """Saldiri: hedef cikis bari eksik VE sonraki mevcut bar hem ileri kayma
    sinirini (birincil_ufuk) HEM DE kume sonunu asiyor. Iki kural ayni anda
    ihlal ediliyor; hangisi once tetiklenmeli?

    Beklenen (on-kayit §3 rev.4): kume siniri kosulsuz onceliklidir --
    "kumeler arasi veri odunc alinmaz" kirala herhangi baska bir kirala
    (ileri kayma dahil) kiyaslanmadan uygulanir. Bu yuzden `KumeSiniriHatasi`
    beklenir, `IleriKaymaSiniriHatasi` degil.
    """
    zamanlar = pd.date_range("2021-01-01", periods=120, freq="4h", tz="UTC")
    giris = zamanlar[5]
    hedef = pencere.cikis_hedefi(giris, 18, config.BAR_4H)
    # Hedeften itibaren 25 bar sil: sonraki mevcut bar hem 18 barlik ileri kayma
    # sinirini (25 > 18) hem de -- kume sonu hedeften hemen sonraysa -- kume
    # sinirini asar.
    silinecek = pd.date_range(hedef, periods=25, freq="4h", tz="UTC")
    eksik = zamanlar.drop(silinecek)
    kume_son = hedef + 2 * DORT_SAAT  # sonraki mevcut bardan (hedef+25x4h) once

    with pytest.raises(pencere.KumeSiniriHatasi):
        pencere.cikis_bari(
            eksik, giris, 18, config.BAR_4H,
            birincil_ufuk=18, donem_bitis=None, kume_bitis=kume_son,
        )


# --- 6) `birincil_ufuk` numpy tamsayisi ----------------------------------------


def test_birincil_ufuk_numpy_tamsayi_kabul_edilir():
    """Saldiri: `birincil_ufuk` olarak Python `int` yerine `numpy.int64`
    verilir (pandas/numpy tabanli analiz kodunda sik rastlanan durum).

    Beklenen: kabul edilmeli ve normal `int` ile AYNI sonucu vermelidir;
    tip kontrolu `isinstance(..., (int, np.integer))` numpy tamsayilarini
    kapsadigi icin bu reddedilmemelidir (aksi halde F2/F3 kodu, ızgara
    parametreleri numpy dtype'indan geldiginde sebepsiz yere patlardi).
    """
    zamanlar = pd.date_range("2021-01-01", periods=60, freq="4h", tz="UTC")
    giris = zamanlar[5]
    sonuc_np = pencere.cikis_bari(
        zamanlar, giris, 18, config.BAR_4H,
        birincil_ufuk=np.int64(18), donem_bitis=None, kume_bitis=None,
    )
    sonuc_py = pencere.cikis_bari(
        zamanlar, giris, 18, config.BAR_4H,
        birincil_ufuk=18, donem_bitis=None, kume_bitis=None,
    )
    assert sonuc_np == sonuc_py


# --- 8) Gunluk barda funding ve ileri kaymali cikis birlikte -------------------


def test_gunluk_barda_ileri_kaymali_cikiste_funding_dogru_toplanir():
    """Saldiri: 1 gunluk bar izgarasinda hedef cikis bari EKSIK (ileri kayma
    devreye girer) ve funding 8 saatlik aralikla oduyor -- iki farkli zaman
    izgarasi (gunluk bar, 8 saatlik funding) ayni hesapta bir arada.

    Beklenen (on-kayit §4 rev.6): cikis ani ileri kaymali barin ACILISIDIR
    (`fiyat_alani="open"`); funding, giris anindan (haric) bu acilis anina
    (dahil) kadarki TUM gercek 8 saatlik odemeleri toplamalidir -- gunluk
    bar sayisiyla degil, gercek saatlerle.
    """
    zamanlar = pd.date_range("2021-05-01", periods=40, freq="1D", tz="UTC")
    giris = zamanlar[5]  # 2021-05-06
    hedef = pencere.cikis_hedefi(giris, 14, config.BAR_1D)  # giris + 13 gun = 2021-05-19
    # Hedef barin kendisini sil (tek gun eksik): sonraki mevcut bar hedef + 1 gun.
    eksik = zamanlar.drop([hedef])

    cikis = pencere.cikis_bari(
        eksik, giris, 14, config.BAR_1D,
        birincil_ufuk=14, donem_bitis=None, kume_bitis=None,
    )
    assert cikis.fiyat_alani == "open" and cikis.kaydi is True
    assert cikis.zaman == hedef + pd.Timedelta(days=1)  # 2021-05-20

    fund = _funding("2021-05-01", "2021-06-01", aralik_saat=8, oran=1e-4)
    deger = _fon(fund, giris, cikis, bar=config.BAR_1D)
    # Giris 05-06 00:00 (haric) -> cikis ani 05-20 00:00 (dahil, "open" oldugu
    # icin bar zamaninin kendisi):
    #   05-06 gunu   : yalnizca 08:00 ve 16:00 (00:00 giris ile ayni an, haric) -> 2
    #   05-07..05-19 : her gun 3 odeme (00:00, 08:00, 16:00), 13 gun          -> 39
    #   05-20 gunu   : yalnizca 00:00 (cikis anindaki odeme, dahil)           -> 1
    beklenen_adet = 2 + 13 * 3 + 1
    assert deger == pytest.approx(beklenen_adet * 1e-4)
