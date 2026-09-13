"""Kume siniri ve ufuk testleri (on-kayit §3 rev.4, denetci bulgusu B1).

"Bir olayin birincil ufku, ait oldugu kumenin tarih araligina tam olarak
sigmalidir. Sigmayan olay o kumede hic olusmaz; kirpilmis getiri kullanilmaz.
Ikincil ufuklar raporlanirken ayni kural kendi ufuk uzunluklariyla uygulanir.
Kumeler arasi veri odunc alinmaz."

Kume sinirlari testlerde de elle yazilmaz; `split.kume_araligi` uzerinden gelir.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import pencere, split

DORT_SAAT = pd.Timedelta(hours=4)


def _izgara(bas: str, son: str) -> pd.DatetimeIndex:
    return pd.date_range(bas, son, freq="4h", tz="UTC")


# --- Kume araligi tek kaynaktan gelir ----------------------------------------


def test_kume_araligi_on_kayit_sinirlariyla_ayni():
    assert split.kume_araligi("KESIF") == (pd.Timestamp(config.KESIF_BASI), pd.Timestamp(config.KESIF_SONU))
    assert split.kume_araligi("C1") == (pd.Timestamp(config.KESIF_BASI), pd.Timestamp(config.KESIF_SONU))
    assert split.kume_araligi("C2") == (pd.Timestamp(config.C2_BASI), pd.Timestamp(config.C2_SONU))


def test_kume_araligi_kume_tanimindan_turetilir(monkeypatch):
    """Sinir kume_tanimi'ndan okunur; baska yerde elle yazilmis bir kopya yoktur."""
    sahte_bas = pd.Timestamp("2021-01-01", tz="UTC")
    sahte_son = pd.Timestamp("2021-06-30 23:59:59", tz="UTC")
    monkeypatch.setattr(split, "kume_tanimi", lambda kume: (("A",), sahte_bas, sahte_son))

    assert split.kume_araligi("KESIF") == (sahte_bas, sahte_son)
    t = pd.Timestamp("2021-06-30 20:00", tz="UTC") - 18 * DORT_SAAT
    assert split.ufuk_kumeye_sigar_mi(t, 18, config.BAR_4H, "KESIF") is True
    assert split.ufuk_kumeye_sigar_mi(t + DORT_SAAT, 18, config.BAR_4H, "KESIF") is False


def test_bilinmeyen_kume_reddedilir():
    with pytest.raises(ValueError):
        split.ufuk_kumeye_sigar_mi(pd.Timestamp("2021-01-01", tz="UTC"), 18, config.BAR_4H, "C3")


@pytest.mark.parametrize("ufuk", [0, -1])
def test_ufuk_birden_kucukse_hata(ufuk):
    with pytest.raises(ValueError):
        split.ufuk_kumeye_sigar_mi(pd.Timestamp("2021-01-01", tz="UTC"), ufuk, config.BAR_4H, "KESIF")


def test_hata_sinifi_tek():
    assert split.KumeSiniriHatasi is pencere.KumeSiniriHatasi
    assert issubclass(split.KumeSiniriHatasi, ValueError)


# --- Sigma kosulu ------------------------------------------------------------


def test_kesif_son_barina_tam_oturan_ufuk_sigar():
    _, son = split.kume_araligi("KESIF")
    son_bar = son.floor("4h")  # 2025-08-31 20:00, kumenin son 4h bari
    t = son_bar - 18 * DORT_SAAT
    assert split.ufuk_kumeye_sigar_mi(t, 18, config.BAR_4H, "KESIF") is True


def test_kesif_sinirini_bir_bar_asan_ufuk_sigmaz():
    _, son = split.kume_araligi("KESIF")
    t = son.floor("4h") - 18 * DORT_SAAT + DORT_SAAT
    assert split.ufuk_kumeye_sigar_mi(t, 18, config.BAR_4H, "KESIF") is False


def test_denetci_b1_ornegi_sigmaz():
    """2025-08-29 12:00'de olusan H1 olayi: 18 barlik ufuk 2025-09-01'e uzanir."""
    t = pd.Timestamp("2025-08-29 12:00", tz="UTC")
    assert split.ufuk_kumeye_sigar_mi(t, 18, config.BAR_4H, "KESIF") is False
    assert split.ufuk_kumeye_sigar_mi(t, 18, config.BAR_4H, "C1") is False


def test_ikincil_ufuklar_kendi_uzunluklariyla_degerlendirilir():
    """Ayni olay 6 barlik ikincil ufka sigar, 18 ve 42 barlik ufuklara sigmaz."""
    t = pd.Timestamp("2025-08-29 12:00", tz="UTC")
    assert split.ufuk_kumeye_sigar_mi(t, 6, config.BAR_4H, "KESIF") is True
    assert split.ufuk_kumeye_sigar_mi(t, 18, config.BAR_4H, "KESIF") is False
    assert split.ufuk_kumeye_sigar_mi(t, 42, config.BAR_4H, "KESIF") is False


def test_gunluk_seride_h3_ufku():
    """H3: 14 gunluk birincil ufuk."""
    _, son = split.kume_araligi("KESIF")
    son_gun = son.floor("D")  # 2025-08-31
    assert split.ufuk_kumeye_sigar_mi(son_gun - pd.Timedelta(days=14), 14, config.BAR_1D, "KESIF") is True
    assert split.ufuk_kumeye_sigar_mi(son_gun - pd.Timedelta(days=13), 14, config.BAR_1D, "KESIF") is False


def test_olayin_kumesi_sinyal_barinin_kumesidir():
    """C2 baslangicindan once tespit edilen olay C2'ye ait degildir."""
    c2_bas, _ = split.kume_araligi("C2")
    once = c2_bas - DORT_SAAT  # 2025-08-31 20:00
    assert split.ufuk_kumeye_sigar_mi(once, 6, config.BAR_4H, "C2") is False
    assert split.ufuk_kumeye_sigar_mi(c2_bas, 6, config.BAR_4H, "C2") is True


def test_c2_sonunu_asan_ufuk_sigmaz():
    _, son = split.kume_araligi("C2")
    t = son.floor("4h") - 18 * DORT_SAAT
    assert split.ufuk_kumeye_sigar_mi(t, 18, config.BAR_4H, "C2") is True
    assert split.ufuk_kumeye_sigar_mi(t + DORT_SAAT, 18, config.BAR_4H, "C2") is False


# --- cikis_bari kume korumasi ------------------------------------------------


def test_kume_disina_tasan_ufuk_kirpilmaz_hata_verir():
    """Kume sinirinda kesilmis seride (split.yukle ciktisi gibi) ufuk sinira
    ulasmadan biterse kirpilmis cikis DONMEZ, hata verir."""
    _, kume_son = split.kume_araligi("KESIF")
    kesik = _izgara("2025-08-20", "2025-08-31 20:00")  # kume sinirinda kesilmis
    t = pd.Timestamp("2025-08-29 12:00", tz="UTC")
    giris = t + DORT_SAAT

    # Kume bilgisi olmadan kod bunu delist sanip sessizce kirpardi (B1).
    korumasiz = pencere.cikis_bari(kesik, giris, 18, config.BAR_4H, donem_bitis=None, karantina_aylari=None, kume_bitis=None)
    assert korumasiz.kirpildi and korumasiz.kirpma_nedeni == "seri_sonu"

    with pytest.raises(split.KumeSiniriHatasi):
        pencere.cikis_bari(kesik, giris, 18, config.BAR_4H, kume_bitis=kume_son, donem_bitis=None, karantina_aylari=None)


def test_kume_disina_tasan_ufuk_sonraki_kumenin_verisini_okumaz():
    """Kesilmemis seride de ufuk C2 verisine uzanamaz."""
    _, kume_son = split.kume_araligi("KESIF")
    tam = _izgara("2025-08-20", "2025-09-10")
    giris = pd.Timestamp("2025-08-29 16:00", tz="UTC")

    with pytest.raises(split.KumeSiniriHatasi):
        pencere.cikis_bari(tam, giris, 18, config.BAR_4H, kume_bitis=kume_son, donem_bitis=None, karantina_aylari=None)


def test_ileri_kayma_kume_sinirini_asamaz():
    """Hedef kumenin son bari ama eksik; sonraki mevcut bar C2'de. Kayma yapilmaz."""
    _, kume_son = split.kume_araligi("KESIF")
    son_bar = kume_son.floor("4h")
    tam = _izgara("2025-08-20", "2025-09-10")
    eksik = tam.drop(son_bar)
    giris = son_bar - 17 * DORT_SAAT  # t+18 = son_bar

    with pytest.raises(split.KumeSiniriHatasi):
        pencere.cikis_bari(eksik, giris, 18, config.BAR_4H, kume_bitis=kume_son, donem_bitis=None, karantina_aylari=None)


def test_kumeye_sigan_ufuk_normal_cikar():
    _, kume_son = split.kume_araligi("KESIF")
    son_bar = kume_son.floor("4h")
    kesik = _izgara("2025-08-20", "2025-08-31 20:00")
    giris = son_bar - 17 * DORT_SAAT

    sonuc = pencere.cikis_bari(kesik, giris, 18, config.BAR_4H, kume_bitis=kume_son, donem_bitis=None, karantina_aylari=None)

    assert sonuc.zaman == son_bar
    assert sonuc.fiyat_alani == "close"
    assert sonuc.kirpildi is False


def test_kume_icinde_gercek_delist_kirpmasi_korunur():
    """Kume icinde veri gercekten biterse (delist) §4 kurali gecerli kalir."""
    _, kume_son = split.kume_araligi("KESIF")
    delist = _izgara("2023-05-01", "2023-05-10 12:00")
    giris = pd.Timestamp("2023-05-09 00:00", tz="UTC")

    sonuc = pencere.cikis_bari(delist, giris, 18, config.BAR_4H, kume_bitis=kume_son, donem_bitis=None, karantina_aylari=None)

    assert sonuc.kirpildi and sonuc.kirpma_nedeni == "seri_sonu"
    assert sonuc.zaman == delist[-1]
