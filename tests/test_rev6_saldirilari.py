"""F1 kapanis saldirilari: `funding.pozisyon_fundingi`, `pencere.cikis_ani`,
`pencere.cikis_bari` ve (rev.7) tek kapi `pencere.pozisyon_plani` uzerine
on-kayit revizyon 6-7 kurallarini kirmaya calisan ek testler.

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
gerekce testlerin docstring'indedir. Rev.7 ile kume karari tek kapiya
(`pozisyon_plani`) tasindi ve bu testler plan uzerinden yazildi. Cikis anlari
artik bar izgarasinda oldugu icin tolerans esikleri, cikis ani yerine funding
kaydi kaydirilarak sinanir; olculen sinir aynidir.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import config
from data import funding, pencere

DORT_SAAT = pd.Timedelta(hours=4)
BIR_DK = pd.Timedelta(minutes=1)
# Rev.8 (RESULTS degisiklik kaydi): donem sinirlari zorunlu; varsayilan donem serinin
# ilk ve son bari. Seri her izgarada 4h (on-kayit §4 rev.8 "Fiyat okuma tabani").
SINIRSIZ = dict(kume_baslangic=None, kume_bitis=None)


def _ts(metin) -> pd.Timestamp:
    return metin if isinstance(metin, pd.Timestamp) else pd.Timestamp(metin, tz="UTC")


def _funding(bas: str, bitis: str, aralik_saat: int = 8, oran: float = 1e-4) -> pd.DataFrame:
    zaman = pd.date_range(bas, bitis, freq=f"{aralik_saat}h", tz="UTC")
    cerceve = pd.DataFrame({"odeme_zamani": zaman, "aralik_saat": float(aralik_saat), "oran": oran})
    cerceve["oran_8h"] = funding.sekiz_saate_normallestir(cerceve["oran"], cerceve["aralik_saat"])
    return cerceve


def _kayitlar(kayitlar: list[tuple[pd.Timestamp, float, float]]) -> pd.DataFrame:
    cerceve = pd.DataFrame(kayitlar, columns=["odeme_zamani", "aralik_saat", "oran"])
    cerceve["odeme_zamani"] = pd.DatetimeIndex(cerceve["odeme_zamani"])
    cerceve["oran_8h"] = funding.sekiz_saate_normallestir(cerceve["oran"], cerceve["aralik_saat"])
    return cerceve


def _plan(giris, cikis_bari, bar=config.BAR_4H, **sinirlar) -> pencere.PozisyonPlani:
    """Kapanistan cikisli plan: giris `giris`, cikis bari `cikis_bari`."""
    g, c = _ts(giris), _ts(cikis_bari)
    a = pencere.adim(bar)
    zamanlar = pd.date_range(g - 5 * a, c + 40 * a, freq="4h")
    ufuk = int((c - g) / a) + 1
    donem = dict(donem_baslangic=zamanlar[0], donem_bitis=zamanlar[-1])
    return pencere.pozisyon_plani(zamanlar, g - a, ufuk, bar, birincil_ufuk=max(ufuk, 18),
                                  **{**SINIRSIZ, **donem, **sinirlar})


def _fon(fund, giris, cikis_bari, bar=config.BAR_4H, **sinirlar):
    return funding._plan_fundingi(fund, _plan(giris, cikis_bari, bar, **sinirlar))


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
    Rev.7: karar tek kapida (`pozisyon_plani`) ve funding verisi GORULMEDEN
    verilir; asagida plan funding cercevesinden once kurulur. Olay olusmaz
    (`KumeSiniriHatasi`). Sinirdaki odemenin varligi, yoklugu ya da konumu hukmu
    degistirmez.
    """
    cikis_ani = _ts("2021-01-05 12:00")  # 08:00 barinin kapanisi
    kume_son = cikis_ani + pd.Timedelta(seconds=30)
    fund = _funding("2021-01-01", "2021-01-10")  # odemeler 00:00, 08:00, 16:00
    if sinirdaki_odeme != "yok":
        an = kume_son + pd.Timedelta(seconds=-10 if sinirdaki_odeme == "kume_icinde" else 20)
        ek = pd.DataFrame({"odeme_zamani": [an], "aralik_saat": [8.0], "oran": [1e-4]})
        fund = pd.concat([fund, ek]).sort_values("odeme_zamani", ignore_index=True)

    with pytest.raises(pencere.KumeSiniriHatasi):
        _fon(fund, "2021-01-05 00:00", "2021-01-05 08:00", kume_bitis=kume_son)


def test_kume_sonuna_tam_esit_cikis_zamanla_reddedilir():
    """Saldiri: cikis ani kume sonuna TAM ESIT.

    Ilk surumde "reddedilmemeli" bekliyordu; kullanici karariyla tersine
    cevrildi (gerekce yukaridaki testte). Cikis anindaki odeme [son, son + 1 dk)
    araligindadir ve bu araligin kume sonundan sonraki kismi kume disidir; karar
    zamanla verilir, olay olusmaz. Kume sonu cikis anindan tam 1 dakika sonraysa
    kabul edilir: cikis anindaki odeme araligi tamamen kume icindedir.
    """
    fund = _funding("2021-01-01", "2021-01-10")
    cikis_ani = _ts("2021-01-05 12:00")

    with pytest.raises(pencere.KumeSiniriHatasi):
        _fon(fund, "2021-01-05 00:00", "2021-01-05 08:00", kume_bitis=cikis_ani)

    deger = _fon(fund, "2021-01-05 00:00", "2021-01-05 08:00", kume_bitis=cikis_ani + BIR_DK)
    assert deger == pytest.approx(1e-4)  # yalnizca 08:00


# --- 2) Giris/cikis tolerans esiklerinin tam siniri ----------------------------


def test_giris_tarafi_tam_60_saniyede_dahil_59_999_de_haric():
    """Saldiri: giris ile bir odeme arasindaki farki tam tolerans esiginde
    (60s) ve esigin hemen altinda (59.999999999s) test eder.

    On-kayit §4 rev.6: "1 dakikadan KUCUK kayma ayni an sayilir" ve giris
    anindaki odeme HARICTIR. Yani:
      - fark < 60s  -> giris ile "ayni an" -> HARIC (giris anindaki odeme).
      - fark >= 60s -> ayri an -> DAHIL (giristen sonraki odeme).
    Giris ani izgarada (08:00); odeme kaydi giristen sonraya kaydirilir.

    Kurgu degisikligi (on-kayit §4 rev.8 "Zaman toleransi" ve "Funding araligi
    gecisleri"): ilk kayit 00:00'dan 00:01'e alindi. 00:00 -> 08:01 boslugu
    araliktan tam 1 dakika uzundur; rev.8'de tam 1 dakika ayni an degildir ve bu
    bosluk eksik odeme sayilir, test pencere kenarini olcemezdi. Olculen kenar ve
    beklenen degerler degismedi.
    """
    giris = _ts("2021-01-05 08:00")  # cikis bari 08:00 -> cikis ani 12:00

    def _cerceve(t):
        return _kayitlar([(_ts("2021-01-05 00:01"), 8.0, 1e-4), (t, 8.0, 9e-4), (_ts("2021-01-05 16:00"), 8.0, 1e-4)])

    assert _fon(_cerceve(giris + BIR_DK), giris, giris) == pytest.approx(9e-4)  # tam 60s -> DAHIL
    haric = giris + (BIR_DK - pd.Timedelta(nanoseconds=1))
    # 60s alti -> HARIC. Pencerede baska kayit kalmaz. Rev.9 §4 "Funding tamligi" rev.8'in
    # "penceresinde kayit olmayan pozisyon tam degildir" cumlesini kaldirdi: haric kayit
    # capadir, capa + 8h pencere sonundan sonra -> tam, 0.0 (rev.8'de NaN, rev.7'de 0.0).
    assert _fon(_cerceve(haric), giris, giris) == 0.0


def test_cikis_tarafi_59_999_saniyede_dahil_tam_60_da_haric():
    """Saldiri: cikis ani ile bir odeme arasindaki farki tam tolerans esiginde
    (60s) ve esigin hemen altinda test eder.

    On-kayit §4 rev.6: cikis anindaki odeme DAHILDIR ve 60s'den kucuk kayma
    ayni an sayilir. Yani:
      - fark < 60s  -> cikisla "ayni an" -> DAHIL (cikis anindaki odeme).
      - fark >= 60s -> odeme cikistan SONRA -> HARIC (henuz gerceklesmemis).
    Cikis ani izgarada (12:00); odeme kaydi cikistan sonraya kaydirilir. Onceki
    kaydin sonraki odemesi (04:01 + 8s) cikis araligindan sonra oldugu icin HARIC
    durumunda aralik odemesizdir ve sonuc 0'dir.
    """
    giris = _ts("2021-01-05 08:00")
    cikis_ani = _ts("2021-01-05 12:00")

    def _cerceve(t):
        return _kayitlar([(_ts("2021-01-05 04:01"), 8.0, 1e-4), (t, 8.0, 9e-4), (_ts("2021-01-05 20:01"), 8.0, 1e-4)])

    dahil = cikis_ani + (BIR_DK - pd.Timedelta(nanoseconds=1))
    assert _fon(_cerceve(dahil), giris, giris) == pytest.approx(9e-4)
    # Tam 60 s -> HARIC; pencerede kayit kalmaz. Rev.9 §4 "Funding tamligi": capa (04:01, 8h)
    # + 8h = 12:01 pencere sonundan once degil -> tam, 0.0 (rev.8'de NaN; rev.7'de 0.0).
    assert _fon(_cerceve(cikis_ani + BIR_DK), giris, giris) == 0.0


# --- 3) Bos, sirasiz, saat dilimsiz funding cercevesi --------------------------


def test_bos_funding_cercevesinde_nan_doner_hata_firlatmaz():
    """Saldiri: tamamen bos funding cercevesi (sutunlar var, satir yok) verilir.

    Beklenen: hicbir odeme kaydi olmadigi icin tamlik kontrolu saglanamaz ve
    sonuc NaN olmalidir (on-kayit §2 rev.3 tamlik sarti); kod crash etmemeli.
    """
    bos = pd.DataFrame(columns=["odeme_zamani", "aralik_saat", "oran", "oran_8h"])
    bos["odeme_zamani"] = pd.to_datetime(bos["odeme_zamani"], utc=True)
    assert pd.isna(_fon(bos, "2021-01-05 00:00", "2021-01-05 20:00"))


def test_sirasiz_funding_cercevesi_hata_verir():
    """Saldiri: funding cercevesi zaman sirasina gore SIRALANMAMIS verilir
    (ör. ters sirali ya da karistirilmis).

    Beklenen (`pencere.ZamanDizisiHatasi` docstring'i, on-kayit §2 rev.3):
    sirasiz dizi bir VERI BOZUKLUGUDUR ve sessizce NaN'a cevrilmez; hata
    yuzeye cikmalidir.
    """
    fund = _funding("2021-01-01", "2021-01-10")
    karisik = fund.sample(frac=1.0, random_state=config.TOHUM).reset_index(drop=True)
    with pytest.raises(pencere.ZamanDizisiHatasi):
        _fon(karisik, "2021-01-05 00:00", "2021-01-05 20:00")

    ters = fund.iloc[::-1].reset_index(drop=True)
    with pytest.raises(pencere.ZamanDizisiHatasi):
        _fon(ters, "2021-01-05 00:00", "2021-01-05 20:00")


def test_saat_dilimsiz_odeme_zamani_hata_verir():
    """Saldiri: `odeme_zamani` sutunu saat dilimsiz (tz-naive) verilir.

    Beklenen (CLAUDE.md §5, `pencere._zaman_dizisi_dogrula`): tum zaman
    damgalari UTC olmalidir; saat dilimsiz dizi sessizce hep NaN dondurup
    calismayi "negatif sonuc" gibi gosterebilirdi. Acikca hata verilmelidir.
    """
    fund = _funding("2021-01-01", "2021-01-10")
    fund["odeme_zamani"] = fund["odeme_zamani"].dt.tz_localize(None)
    with pytest.raises(pencere.ZamanDizisiHatasi):
        _fon(fund, "2021-01-05 00:00", "2021-01-05 20:00")


# --- 4) `cikis_ani` elle kurulmus tutarsiz CikisSonucu -------------------------


def test_cikis_ani_bilinmeyen_fiyat_alani_reddedilir():
    """Saldiri: analiz kodu `cikis_bari` disinda elle bir `CikisSonucu` kurup
    `fiyat_alani` alanina "close"/"open" disinda bir deger yazarsa ne olur?

    Beklenen: `cikis_ani` bunu acikca reddetmeli (ValueError). Rev.7:
    `pozisyon_fundingi` yalnizca plan alir; cikis nesnesi verilirse TypeError.
    """
    # Rev.8 alanlari (tur, hedef_cikis_ani, ileri_kayma); cikis_ani izgara adimi almaz.
    bozuk = pencere.CikisSonucu(
        indeks=0, zaman=_ts("2021-01-05 20:00"), fiyat_alani="vwap", cikis_ani=_ts("2021-01-06 00:00"),
        tur="olagan", hedef_cikis_ani=_ts("2021-01-06 00:00"), ileri_kayma=pd.Timedelta(0),
    )
    with pytest.raises(ValueError):
        pencere.cikis_ani(bozuk)

    fund = _funding("2021-01-01", "2021-01-10")
    with pytest.raises(TypeError):
        funding._plan_fundingi(fund, bozuk)


# --- 5) Kume siniri ile ileri kayma sinirinin ayni anda asilmasi ---------------


def test_kume_ve_ileri_kayma_siniri_ayni_anda_asilinca_kume_hatasi_once_gelir():
    """Saldiri: hedef cikis bari eksik VE sonraki mevcut bar hem ileri kayma
    sinirini (birincil_ufuk) HEM DE kume sonunu asiyor. Iki kural ayni anda
    ihlal ediliyor; hangisi once tetiklenmeli?

    Beklenen (on-kayit §3 rev.4): kume siniri kosulsuz onceliklidir. Bu yuzden
    `KumeSiniriHatasi` beklenir, `IleriKaymaSiniriHatasi` degil; ic adim
    `cikis_bari` ve tek kapi `pozisyon_plani` ayni hukmu verir.
    """
    zamanlar = pd.date_range("2021-01-01", periods=120, freq="4h", tz="UTC")
    giris = zamanlar[5]
    # Rev.8: cikis_hedefi T'yi verir; hedef barin acilisi T - 4 saat.
    hedef = pencere.cikis_hedefi(giris, 18, config.BAR_4H) - DORT_SAAT
    silinecek = pd.date_range(hedef, periods=25, freq="4h", tz="UTC")
    eksik = zamanlar.drop(silinecek)
    kume_son = hedef + 2 * DORT_SAAT  # sonraki mevcut bardan (hedef+25x4h) once
    donem = dict(donem_baslangic=eksik[0], donem_bitis=eksik[-1])

    with pytest.raises(pencere.KumeSiniriHatasi):
        pencere.cikis_bari(eksik, giris, 18, config.BAR_4H, birincil_ufuk=18, donem_bitis=eksik[-1], kume_bitis=kume_son)
    with pytest.raises(pencere.KumeSiniriHatasi):
        pencere.pozisyon_plani(eksik, giris - DORT_SAAT, 18, config.BAR_4H, birincil_ufuk=18,
                               **{**SINIRSIZ, **donem, "kume_bitis": kume_son})


# --- 6) `birincil_ufuk` numpy tamsayisi ----------------------------------------


def test_birincil_ufuk_numpy_tamsayi_kabul_edilir():
    """Saldiri: `birincil_ufuk` olarak Python `int` yerine `numpy.int64`
    verilir (pandas/numpy tabanli analiz kodunda sik rastlanan durum).

    Beklenen: kabul edilmeli ve normal `int` ile AYNI sonucu vermelidir.
    """
    zamanlar = pd.date_range("2021-01-01", periods=60, freq="4h", tz="UTC")
    giris = zamanlar[5]
    b = zamanlar[-1]  # rev.8: donem bitisi zorunlu
    sonuc_np = pencere.cikis_bari(zamanlar, giris, 18, config.BAR_4H, birincil_ufuk=np.int64(18), donem_bitis=b, kume_bitis=None)
    sonuc_py = pencere.cikis_bari(zamanlar, giris, 18, config.BAR_4H, birincil_ufuk=18, donem_bitis=b, kume_bitis=None)
    assert sonuc_np == sonuc_py
    plan_np = pencere.pozisyon_plani(zamanlar, zamanlar[4], 18, config.BAR_4H, birincil_ufuk=np.int64(18), **SINIRSIZ,
                                     donem_baslangic=zamanlar[0], donem_bitis=b)
    assert plan_np.cikis == sonuc_py


# --- 7) Gunluk barda funding ve ileri kaymali cikis birlikte -------------------


def test_gunluk_barda_ileri_kaymali_cikiste_funding_dogru_toplanir():
    """Saldiri: 1 gunluk bar izgarasinda hedef cikis bari EKSIK (ileri kayma
    devreye girer) ve funding 8 saatlik aralikla oduyor.

    Beklenen (on-kayit §4 rev.6): cikis ani ileri kaymali barin ACILISIDIR;
    funding, giris anindan (haric) bu acilis anina (dahil) kadarki TUM gercek
    8 saatlik odemeleri toplamalidir.
    """
    # Rev.8 §4 "Fiyat okuma tabani": 1d izgarasinda da seri 4h'tir; hedef bar kapanisi
    # T = giris + 14 gun olan 4h bardir (acilisi T - 4h). Onu silmek, rev.7'deki gunluk
    # hedef barin eksikligiyle ayni cikisi (05-20 00:00 acilisi) verir.
    zamanlar = pd.date_range("2021-05-01", periods=40 * 6, freq="4h", tz="UTC")
    giris = pd.Timestamp("2021-05-06", tz="UTC")
    hedef = pencere.cikis_hedefi(giris, 14, config.BAR_1D)  # T = 2021-05-20 00:00
    eksik = zamanlar.drop([hedef - DORT_SAAT])

    plan = pencere.pozisyon_plani(eksik, giris - pd.Timedelta(days=1), 14, config.BAR_1D, birincil_ufuk=14, **SINIRSIZ,
                                  donem_baslangic=eksik[0], donem_bitis=eksik[-1])
    assert plan.cikis.fiyat_alani == "open" and plan.cikis.kaydi is True
    assert plan.cikis.zaman == hedef  # 2021-05-20 00:00

    fund = _funding("2021-05-01", "2021-06-01", aralik_saat=8, oran=1e-4)
    deger = funding._plan_fundingi(fund, plan)
    #   05-06 gunu   : 08:00 ve 16:00 (00:00 giris ile ayni an, haric) -> 2
    #   05-07..05-19 : her gun 3 odeme, 13 gun                         -> 39
    #   05-20 gunu   : yalnizca 00:00 (cikis anindaki odeme, dahil)    -> 1
    assert deger == pytest.approx((2 + 13 * 3 + 1) * 1e-4)
