"""Kume siniri ve geriye bakis testleri (on-kayit §3 rev.5).

"Geriye bakis pencereleri de kumenin tarih araligina sigmalidir. Penceresi kume
baslangicindan onceki veriye uzanan barda olay ya da kontrol olusmaz; pencere o
veriyi odunc almaz. Bu kural donem kurallarina ek olarak uygulanir
ve kod duzeyinde ayrica dogrulanir -- verinin kume sinirinda kesilmis olmasina
dayanilmaz."

Bu yuzden buradaki testlerin hepsi kume ONCESI verisi TAM olan serilerle kurulur:
NaN, eksik veriden degil kume sinirindan gelmelidir. Kume sinirlari elle
yazilmaz; `split.kume_araligi` uzerinden gelir.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from donem_yardimcisi import TOPLAM_DONEM_B, TOPLAM_DONEM_BASI  # noqa: E402
from data import eligibility, klines, pencere, split

DORT_SAAT = pd.Timedelta(hours=4)
C2_BAS = split.kume_araligi("C2")[0]


def _seri(bas, bitis, bar: str = config.BAR_4H, deger: float = 1.0) -> pd.Series:
    indeks = pd.date_range(bas, bitis, freq=pencere.adim(bar), tz="UTC")
    return pd.Series(deger, index=indeks)


# --- Parametre zorunludur ----------------------------------------------------


@pytest.mark.parametrize(
    "cagri",
    [
        lambda s, t: pencere.pencere_dilimi(s, t, 5, config.BAR_4H, t_dahil=True, donem_baslangic=TOPLAM_DONEM_BASI),
        lambda s, t: pencere.pencere_degeri(s, t, 5, config.BAR_4H, t_dahil=True, donem_baslangic=TOPLAM_DONEM_BASI),
    ],
)
def test_pencere_fonksiyonlarinda_kume_baslangici_verilmezse_hata(cagri):
    seri = _seri("2025-08-01", "2025-09-10")
    with pytest.raises(TypeError):
        cagri(seri, seri.index[-1])


@pytest.mark.parametrize(
    "cagri",
    [
        lambda h, t: eligibility.medyan_hacim(h, t, donem_baslangic=TOPLAM_DONEM_BASI, pencere_gun=config.HACIM_PENCERESI_GUN),
        lambda h, t: eligibility.uygun_mu(h, t, config.BAR_4H, donem_baslangic=pd.Timestamp("2020-01-01", tz="UTC"), donem_bitis=TOPLAM_DONEM_B),
        lambda h, t: eligibility.uygunluk_serisi(h, [t], config.BAR_4H, donem_baslangic=pd.Timestamp("2020-01-01", tz="UTC"), donem_bitis=TOPLAM_DONEM_B),
    ],
)
def test_uygunluk_fonksiyonlarinda_kume_baslangici_verilmezse_hata(cagri):
    hacim = _seri("2025-06-01", "2025-12-31", bar=config.BAR_1D, deger=50_000_000.0)
    with pytest.raises(TypeError):
        cagri(hacim, pd.Timestamp("2025-10-15", tz="UTC"))


@pytest.mark.parametrize("deger", [True, False])
def test_kume_baslangici_bool_olamaz(deger):
    seri = _seri("2025-08-01", "2025-09-10")
    with pytest.raises(TypeError):
        pencere.pencere_degeri(seri, seri.index[-1], 5, config.BAR_4H, t_dahil=True, kume_baslangic=deger, donem_baslangic=TOPLAM_DONEM_BASI)


# --- Kural: veri kesilmemis olsa bile sinir uygulanir ------------------------


def test_kume_oncesi_veri_mevcutken_siniri_asan_pencere_nan():
    """Seride kume oncesi veri eksiksiz; yine de pencere onu odunc alamaz."""
    seri = _seri("2025-07-01", "2025-09-30 20:00")
    t = C2_BAS + 10 * DORT_SAAT  # pencerenin 170 bari kume oncesinde

    assert not pd.isna(pencere.pencere_degeri(seri, t, 180, config.BAR_4H, t_dahil=True, kume_baslangic=None, donem_baslangic=TOPLAM_DONEM_BASI))
    assert pd.isna(pencere.pencere_degeri(seri, t, 180, config.BAR_4H, t_dahil=True, kume_baslangic=C2_BAS, donem_baslangic=TOPLAM_DONEM_BASI))
    assert pencere.pencere_dilimi(seri, t, 180, config.BAR_4H, t_dahil=True, kume_baslangic=C2_BAS, donem_baslangic=TOPLAM_DONEM_BASI) is None


@pytest.mark.parametrize(
    ("t_dahil", "ilk_gecerli"),
    [
        (True, C2_BAS + 179 * DORT_SAAT),   # [t-179, t] -> ilk bar = kume basi
        (False, C2_BAS + 180 * DORT_SAAT),  # [t-180, t-1] -> ilk bar = kume basi
    ],
)
def test_ilk_gecerli_bar_tam_kume_basinda_baslayan_penceredir(t_dahil, ilk_gecerli):
    seri = _seri("2025-06-01", "2025-11-30 20:00")

    assert not pd.isna(
        pencere.pencere_degeri(seri, ilk_gecerli, 180, config.BAR_4H, t_dahil=t_dahil, kume_baslangic=C2_BAS, donem_baslangic=TOPLAM_DONEM_BASI)
    )
    assert pd.isna(
        pencere.pencere_degeri(seri, ilk_gecerli - DORT_SAAT, 180, config.BAR_4H, t_dahil=t_dahil, kume_baslangic=C2_BAS, donem_baslangic=TOPLAM_DONEM_BASI)
    )


def test_kume_oncesi_veriyi_bozmak_kume_icindeki_hicbir_pencereyi_degistirmez():
    """Sizinti saldirisi: kume oncesi degerler degisse de kume ici sonuc ayni kalmali."""
    seri = _seri("2025-07-01", "2025-10-31 20:00")
    seri[:] = range(len(seri))
    bozuk = seri.copy()
    bozuk[bozuk.index < C2_BAS] = 1e12

    for t in seri.index[seri.index >= C2_BAS]:
        for t_dahil in (True, False):
            once = pencere.pencere_degeri(seri, t, 30, config.BAR_4H, t_dahil=t_dahil, kume_baslangic=C2_BAS, islev="mean", donem_baslangic=TOPLAM_DONEM_BASI)
            sonra = pencere.pencere_degeri(bozuk, t, 30, config.BAR_4H, t_dahil=t_dahil, kume_baslangic=C2_BAS, islev="mean", donem_baslangic=TOPLAM_DONEM_BASI)
            assert (pd.isna(once) and pd.isna(sonra)) or once == sonra, f"{t} t_dahil={t_dahil}"


@pytest.mark.parametrize(
    ("donem_bas", "kume_bas"),
    [
        ("2025-08-15", "2025-09-01"),  # kume daha gec: kume siniri belirler
        ("2025-09-01", "2025-08-15"),  # donem daha gec: donem siniri belirler
    ],
)
def test_donem_ve_kume_sinirindan_gec_olani_uygulanir(donem_bas, kume_bas):
    seri = _seri("2025-07-01", "2025-10-31 20:00")
    sinir = max(pd.Timestamp(donem_bas, tz="UTC"), pd.Timestamp(kume_bas, tz="UTC"))
    ilk_gecerli = sinir + 29 * DORT_SAAT

    def deger(t):
        return pencere.pencere_degeri(seri, t, 30, config.BAR_4H, t_dahil=True, donem_baslangic=pd.Timestamp(donem_bas, tz="UTC"), kume_baslangic=pd.Timestamp(kume_bas, tz="UTC"))

    assert not pd.isna(deger(ilk_gecerli))
    assert pd.isna(deger(ilk_gecerli - DORT_SAAT))


# --- Uygunluk: C2'nin ilk 30 gununde hacim penceresi yoktur -------------------


def test_c2_basinda_hacim_penceresi_kume_oncesine_uzanamaz():
    hacim = _seri("2025-06-01", "2025-12-31", bar=config.BAR_1D, deger=50_000_000.0)
    donem_bas = pd.Timestamp("2020-01-01", tz="UTC")

    # Kume oncesi hacim tam ve esigin cok ustunde; kume siniri olmasa uygun olurdu.
    erken = C2_BAS + pd.Timedelta(days=10)
    assert eligibility.uygun_mu(hacim, erken, config.BAR_4H, donem_baslangic=donem_bas, kume_baslangic=None, donem_bitis=TOPLAM_DONEM_B) is True
    assert eligibility.uygun_mu(hacim, erken, config.BAR_4H, donem_baslangic=donem_bas, kume_baslangic=C2_BAS, donem_bitis=TOPLAM_DONEM_B) is False

    # Pencere t'nin gununu icermez: 30 gunluk pencere ilk kez kume basindan 30 gun sonra dolar.
    ilk_gun = C2_BAS + pd.Timedelta(days=30)
    assert eligibility.uygun_mu(hacim, ilk_gun - pd.Timedelta(days=1), config.BAR_4H, donem_baslangic=donem_bas, kume_baslangic=C2_BAS, donem_bitis=TOPLAM_DONEM_B) is False
    assert eligibility.uygun_mu(hacim, ilk_gun, config.BAR_4H, donem_baslangic=donem_bas, kume_baslangic=C2_BAS, donem_bitis=TOPLAM_DONEM_B) is True


# --- Kume sinirini None ile kapatma yalnizca veri katmani ve F1 denetiminde ----


def test_kume_siniri_none_yalnizca_izinli_dizinlerde():
    """F1 kapanis bulgusu 4: `kume_baslangic` / `kume_bitis` bilincli `None`
    alabilir, ama `None` kural(lar)i kapatir. Bu yalnizca kumeye ait olmayan
    hesaplarda mesrudur: veri katmani, testler ve tum gecmisi olcen F1 denetimi.

    events/, study/ ve diger analizler (F2 ve sonrasi) kume sinirini `None` ile
    kapatirsa rev.4/rev.5 sessizce devre disi kalir; bu test onu yakalar.
    """
    from tarama_yardimcisi import KUME_NONE_DESENI, ihlaller

    assert ihlaller(KUME_NONE_DESENI) == []


# --- Gercek veri: C2'nin ilk bari, 180 barlik pencere -------------------------
#
# ONBELLEKTEN okunur, aga cikilmaz (CLAUDE.md §5). Yalnizca A grubu bir sembolun
# KESIF donemindeki (2025-07, 2025-08) dosyalari okunur. C2 donemi verisi
# OKUNMAZ: C2 bir onay kumesidir ve tek atistir (CLAUDE.md §3.3).
#
# Bu yuzden t, C2'nin ilk bari (2025-09-01 00:00) ve pencere t_dahil=False'tur:
# 180 barlik pencere [2025-08-02 00:00, 2025-08-31 20:00] tamamen kume oncesi
# veridedir ve bu veri eksiksizdir. Pencere NaN donuyorsa bunun tek nedeni
# kume siniridir. Daha sonraki bir C2 bari secilseydi pencere C2 barlarini da
# icerirdi; o barlar okunmadigi icin NaN tamlik kuralindan gelirdi ve test
# kume kuralini dogrulamazdi.

GERCEK_SEMBOL = "SOLUSDT"
GERCEK_AYLAR = ("2025-07", "2025-08")


def _gercek_dosyalar() -> list:
    dizin = config.ONBELLEK_DIZINI / "klines" / GERCEK_SEMBOL / config.BAR_4H
    return [dizin / f"{ay}.parquet" for ay in GERCEK_AYLAR]


def _gercek_veri_var() -> bool:
    return config.SPLIT_CSV.exists() and all(d.exists() for d in _gercek_dosyalar())


def _gercek_4h() -> pd.DataFrame:
    cerceve = pd.concat([pd.read_parquet(d) for d in _gercek_dosyalar()], ignore_index=True)
    return cerceve.drop_duplicates("open_time").sort_values("open_time", ignore_index=True)


gercek_veri = pytest.mark.skipif(
    not _gercek_veri_var(), reason=f"onbellekte {GERCEK_SEMBOL} {GERCEK_AYLAR} verisi ya da split.csv yok"
)


@gercek_veri
def test_gercek_sembol_a_grubunda_ve_c2_verisi_okunmuyor():
    tablo = split.split_oku().set_index("sembol")["grup"]
    assert tablo[GERCEK_SEMBOL] == "A"

    cerceve = _gercek_4h()
    assert cerceve["open_time"].max() < C2_BAS, "test C2 donemi verisi okumamali"


@gercek_veri
def test_gercek_veride_c2_ilk_barinda_180_barlik_pencere_nan():
    cerceve = _gercek_4h()
    hacim = pd.Series(cerceve["quote_volume"].values, index=pd.DatetimeIndex(cerceve["open_time"]))
    t = C2_BAS

    # Onkosul: pencerenin 180 bari seride eksiksiz mevcut (veri kesilmemis).
    beklenen = pencere.beklenen_zamanlar(t, 180, config.BAR_4H, t_dahil=False)
    assert beklenen[0] == pd.Timestamp("2025-08-02 00:00", tz="UTC")
    assert beklenen[-1] == pd.Timestamp("2025-08-31 20:00", tz="UTC")
    assert beklenen.isin(hacim.index).all()

    # Kume siniri olmadan pencere bir deger uretirdi...
    assert not pd.isna(
        pencere.pencere_degeri(hacim, t, 180, config.BAR_4H, t_dahil=False, kume_baslangic=None, donem_baslangic=TOPLAM_DONEM_BASI)
    )
    # ...C2 kume baslangiciyla NaN doner.
    assert pd.isna(
        pencere.pencere_degeri(hacim, t, 180, config.BAR_4H, t_dahil=False, kume_baslangic=C2_BAS, donem_baslangic=TOPLAM_DONEM_BASI)
    )


@gercek_veri
def test_gercek_veride_c2_ilk_gununde_medyan_hacim_nan():
    # rev.8 §2 "1 gunluk barlar": 1d serisi sembolun commit edilmis donemleriyle kurulur.
    from data import universe

    donemler = universe.sembol_donemleri(universe.evren_yukle(), GERCEK_SEMBOL)
    gunluk = klines.gunluge_cevir(_gercek_4h(), donemler=donemler)
    hacim = eligibility.gunluk_hacim_serisi(gunluk)

    assert not pd.isna(eligibility.medyan_hacim(hacim, C2_BAS, kume_baslangic=None, donem_baslangic=TOPLAM_DONEM_BASI, pencere_gun=config.HACIM_PENCERESI_GUN))
    assert pd.isna(eligibility.medyan_hacim(hacim, C2_BAS, kume_baslangic=C2_BAS, donem_baslangic=TOPLAM_DONEM_BASI, pencere_gun=config.HACIM_PENCERESI_GUN))
