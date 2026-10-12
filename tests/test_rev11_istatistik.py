"""Rev.11 uygulamasi madde 9: `r` ve p-degeri (on-kayit §7, rev.11).

Hicbir veriye uygulanmaz; girdiler sentetik sayilardir ve beklenen p-degerleri ELLE
hesaplanabilir. Getiri hesaplanmaz; fonksiyon getirileri sayi olarak alir. Aga cikmaz.
"""

from __future__ import annotations

import pytest

import config
from data import istatistik

N = config.PERMUTASYON_TEKRAR  # 10.000


# --- Test istatistigi (on-kayit §7) -----------------------------------------------------------


def _p(olay_getirileri, kontrol_havuzlari):
    """`yeniden_ornekle` cagrisinin tek yeri: imzasi rev.13'te degisecek (alt tohum demeti)."""
    return istatistik.yeniden_ornekle(olay_getirileri, kontrol_havuzlari)


def test_test_istatistigi_ortalama_farki():
    """REV.13 ILE DEGISTI (§7 madde (e)): fonksiyon duz bir kontrol getirisi listesi degil, OLAY
    BASINA kontrol havuzlari alir ve kontrol ortalamasini olay basina agirliklandirir."""
    assert istatistik.test_istatistigi([0.10, 0.20], [[0.05], [0.05]]) == pytest.approx(0.10)
    assert istatistik.test_istatistigi([0.0], [[0.0]]) == 0.0


def test_kontrol_ortalamasi_olay_basina_agirliklandirilir():
    """On-kayit §7 (rev.13): "once her olayin kontrol havuzunun ortalamasi alinir, sonra bu
    ortalamalarin olaylar arasindaki ortalamasi alinir; havuzlar tek bir kumede BIRLESTIRILMEZ."

    Havuz boyutlari 1 ile 10 arasinda degisen sentetik bir kume: iki tanim farkli deger verir ve
    rev.13'un tanimi ELLE hesaplanan degere esittir."""
    olaylar = [0.10, 0.10, 0.10]
    havuzlar = [[1.0], [0.0] * 10, [0.0, 0.0, 0.0]]
    # Rev.13: havuz ortalamalari 1.0, 0.0, 0.0 -> ortalama 1/3.
    elle = 0.10 - (1.0 + 0.0 + 0.0) / 3
    assert istatistik.test_istatistigi(olaylar, havuzlar) == pytest.approx(elle)
    # Birlestirilmis (rev.13 oncesi) tanim: 14 kontrolun ortalamasi 1/14 -> BASKA bir deger.
    birlesik = 0.10 - 1.0 / 14
    assert birlesik != pytest.approx(elle)


def test_havuz_boyutu_istatistigi_degistirmez_esit_ortalamalarda():
    """Agirliklandirmanin dogrudan sonucu: havuzun BOYUTU degil ORTALAMASI sayilir."""
    a = istatistik.test_istatistigi([0.2, 0.2], [[0.1], [0.1] * 7])
    b = istatistik.test_istatistigi([0.2, 0.2], [[0.1], [0.1]])
    assert a == pytest.approx(b) == pytest.approx(0.1)


def test_yeniden_ornekleme_dagiliminin_ortalamasi_gozlenen_istatistige_yakinsar():
    """On-kayit §7 gerekcesi: "Havuzlar birlestirilirse gozlenen istatistik ile yeniden ornekleme
    dagilimi ayni olcekte olmaz." Ayni olcekte olduklarinin olcusu: her olayin havuzundan BIR
    kontrol cekilerek hesaplanan istatistiklerin ortalamasi, gozlenen istatistige yakinsar.

    Burada dogrudan `r`yi kullaniriz: istatistik dagiliminin merkezi gozlenen istatistiktir, bu
    yuzden gozlenen istatistik tam sifirken `r` tekrarlarin yarisina yakin cikar; gozlenen
    istatistik acikca pozitifken r = 0. Havuz boyutlari KASITLI olarak esit degildir."""
    olaylar = [0.0, 0.0, 0.0]
    havuzlar = [[1.0, -1.0], [1.0, -1.0] * 5, [1.0, -1.0] * 3]
    assert istatistik.test_istatistigi(olaylar, havuzlar) == pytest.approx(0.0)
    sonuc = _p(olaylar, havuzlar)
    assert 0.40 * N < sonuc.r < 0.60 * N
    # Cekim OLAY BASINA oldugu icin dagilim elle sayilabilir: uc olaydan birer +-1 cekilir,
    # cekilenlerin ortalamasi {-1, -1/3, 1/3, 1} degerlerini 1/8, 3/8, 3/8, 1/8 olasiliklariyla
    # alir. Gozlenen istatistik 0.5 iken istatistik = 0.5 - ortalama <= 0 yalnizca ortalama 1
    # iken olur, yani r ~ N/8. Havuzlar BIRLESTIRILSE cekim 2+10+6 = 18 kontrolun ustunden
    # olurdu ve bu sayim gecerli olmazdi.
    pozitif = _p([0.5, 0.5, 0.5], havuzlar)
    assert pozitif.r == pytest.approx(N / 8, rel=0.15)
    # Gozlenen istatistik butun cekimlerin ustundeyse (1.5 - ortalama >= 0.5) r = 0.
    assert _p([1.5, 1.5, 1.5], havuzlar).r == 0


def test_bos_kume_tanimsiz():
    with pytest.raises(ValueError):
        istatistik.test_istatistigi([], [])
    with pytest.raises(ValueError):
        istatistik.test_istatistigi([0.1], [[]])


def test_havuz_sayisi_olay_sayisiyla_ayni_olmali_test_istatistiginde_de():
    with pytest.raises(ValueError, match="bir kontrol havuzu"):
        istatistik.test_istatistigi([0.10, 0.20], [[0.05]])


def test_sonlu_olmayan_getiri_reddedilir():
    with pytest.raises(ValueError, match="sonlu"):
        istatistik.test_istatistigi([float("nan")], [[0.1]])
    with pytest.raises(ValueError, match="sonlu"):
        istatistik.test_istatistigi([0.1], [[float("inf")]])


# --- r ve p (on-kayit §7 rev.11) --------------------------------------------------------------


def test_tek_kontrollu_havuzlarda_p_elle_hesaplanir_olay_lehine():
    """Her havuzda tek kontrol varsa cekim deterministiktir: istatistik her tekrarda aynidir.

    Olay ortalamasi 0.10, kontrol ortalamasi 0.00 -> istatistik +0.10 > 0, yani HICBIR tekrarda
    "sifiri asmadi" olmaz: r = 0 ve p = (0 + 1) / (10000 + 1) = 1 / 10001."""
    sonuc = _p([0.10, 0.10], [[0.0], [0.0]])
    assert sonuc.r == 0
    assert sonuc.p == pytest.approx(1 / (N + 1))
    assert sonuc.tekrar == N and sonuc.olay_sayisi == 2 and sonuc.tohum == config.TOHUM


def test_tek_kontrollu_havuzlarda_p_elle_hesaplanir_kontrol_lehine():
    """Istatistik -0.10 <= 0: butun tekrarlar sayilir, r = 10000 ve p = 10001 / 10001 = 1."""
    sonuc = _p([0.0, 0.0], [[0.10], [0.10]])
    assert sonuc.r == N
    assert sonuc.p == pytest.approx(1.0)


def test_tam_sifir_istatistigi_r_ye_sayilir():
    """On-kayit §7 rev.11: "`r`, test istatistiginin sifiri ASMADIGI (`<= 0`) tekrarlarin
    sayisidir." Tam sifir asmamaktir ve r'ye girer."""
    sonuc = _p([0.05], [[0.05]])
    assert sonuc.r == N and sonuc.p == pytest.approx(1.0)


def test_simetrik_havuzda_r_yarisina_yakin():
    """Her olayin havuzunda +1 ve -1 var; olay ortalamasi 0. Istatistik = -ortalama(cekilen).
    Tek olayda cekim iki esit olasilikli degerden biridir; r ~ N/2 (tohum sabit oldugu icin
    deger tam belirlidir ve tekrarlanabilir)."""
    a = _p([0.0], [[1.0, -1.0]])
    b = _p([0.0], [[1.0, -1.0]])
    assert a.r == b.r, "ayni tohum ayni r"
    assert 0.45 * N < a.r < 0.55 * N


def test_cekim_havuz_icinden_yapilir():
    """Havuzdaki butun kontroller ayni degerse istatistik deterministiktir; bu, cekimin gercekten
    havuzun icinden yapildigini gosterir (havuz dısından bir deger karismaz)."""
    sonuc = _p([0.20], [[0.05, 0.05, 0.05]])
    assert sonuc.r == 0 and sonuc.p == pytest.approx(1 / (N + 1))


def test_olaylar_kendi_havuzlarindan_cekilir():
    """Eslestirilmis ornekleme: iki olayin havuzlari karismaz. Birinci havuz sabit 0.0, ikinci
    sabit 1.0 -> cekilen ortalama her zaman 0.5, istatistik 0.6 - 0.5 = 0.1 > 0 -> r = 0."""
    sonuc = _p([0.6, 0.6], [[0.0, 0.0], [1.0, 1.0]])
    assert sonuc.r == 0


def test_bos_havuzlu_olay_reddedilir():
    with pytest.raises(ValueError, match="bos"):
        _p([0.1, 0.2], [[0.0], []])


def test_havuz_sayisi_olay_sayisiyla_ayni_olmali():
    with pytest.raises(ValueError, match="bir kontrol havuzu"):
        _p([0.1, 0.2], [[0.0]])


def test_olay_kumesi_bos_olamaz():
    with pytest.raises(ValueError):
        _p([], [])


@pytest.mark.parametrize("tekrar", [100, 9999, 10001])
def test_on_kayit_disi_tekrar_reddedilir(tekrar):
    with pytest.raises(ValueError, match="tekrar"):
        istatistik.yeniden_ornekle([0.1], [[0.0]], tekrar=tekrar)


def test_on_kayit_disi_tohum_reddedilir():
    with pytest.raises(ValueError, match="tohum"):
        istatistik.yeniden_ornekle([0.1], [[0.0]], tohum=1)


def test_yordamin_siniri_metni_tasinir():
    """On-kayit §7 rev.11 "Bu yordamin siniri": raporlarda p-degeriyle anilacak cumle kodda tek
    yerde durur."""
    assert "bootstrap" in istatistik.YORDAMIN_SINIRI
    assert "permutasyon testi degildir" in istatistik.YORDAMIN_SINIRI


def test_hicbir_veriye_uygulanmadi():
    """Madde 9: fonksiyon yazilir ve test edilir, hicbir veride kosulmaz. `data.istatistik`
    veri katmanindan hicbir yukleyici ya da cerceve almaz; yalnizca sayi listeleri alir."""
    import inspect

    kaynak = inspect.getsource(istatistik)
    for yasak in ("klines", "funding_yukle", "mumlari_yukle", "pozisyon", "read_parquet"):
        assert yasak not in kaynak, f"istatistik modulu veriye dokunmamali: {yasak}"
