"""Pozisyon funding'i testleri (on-kayit §4 rev.6).

Pozisyon giris anindan sonra ve cikis anina kadar gerceklesen odemeleri alir ya
da oder: giris anindaki haric, cikis anindaki dahil; 1 dakikadan kucuk kayma ayni
an sayilir; cikis anindaki odeme kume disina dusuyorsa olay olusmaz. Mum
pencereleri ve `funding_ortalamasi` ile ayni sinir korumalari gecerlidir.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import funding, pencere, split

DORT_SAAT = pd.Timedelta(hours=4)
SINIRSIZ = dict(kume_baslangic=None, kume_bitis=None, donem_baslangic=None, donem_bitis=None, karantina_aylari=None)


def _ts(metin: str) -> pd.Timestamp:
    return pd.Timestamp(metin, tz="UTC")


def _funding(bas: str, bitis: str, aralik_saat: int = 8, oran: float = 1e-4) -> pd.DataFrame:
    zaman = pd.date_range(bas, bitis, freq=f"{aralik_saat}h", tz="UTC")
    cerceve = pd.DataFrame({"odeme_zamani": zaman, "aralik_saat": float(aralik_saat), "oran": oran})
    cerceve["oran_8h"] = funding.sekiz_saate_normallestir(cerceve["oran"], cerceve["aralik_saat"])
    return cerceve


def _oran_ata(fund: pd.DataFrame, zaman: str, oran: float) -> None:
    fund.loc[fund["odeme_zamani"] == _ts(zaman), "oran"] = oran


def _cikis(zaman: str, fiyat_alani: str = "close") -> pencere.CikisSonucu:
    return pencere.CikisSonucu(
        indeks=0, zaman=_ts(zaman), fiyat_alani=fiyat_alani, kaydi=fiyat_alani == "open", kirpildi=False
    )


def _fon(fund, giris: str, cikis, bar=config.BAR_4H, **sinirlar):
    sinirlar = {**SINIRSIZ, **sinirlar}
    return funding.pozisyon_fundingi(fund, _ts(giris), cikis, bar, **sinirlar)


# --- Cikis ani ---------------------------------------------------------------


def test_cikis_ani_kapanista_bar_sonu_acilista_bar_basi():
    assert pencere.cikis_ani(_cikis("2021-01-05 20:00"), config.BAR_4H) == _ts("2021-01-06 00:00")
    assert pencere.cikis_ani(_cikis("2021-01-05 20:00", "open"), config.BAR_4H) == _ts("2021-01-05 20:00")
    assert pencere.cikis_ani(_cikis("2021-01-05 00:00"), config.BAR_1D) == _ts("2021-01-06 00:00")


def test_cikis_ani_zaman_damgasi_kabul_etmez():
    with pytest.raises(TypeError):
        pencere.cikis_ani(_ts("2021-01-05 20:00"), config.BAR_4H)


# --- Temel hesap ve giris/cikis sinirlari ------------------------------------


def test_odemelerin_toplami_gercek_oranla():
    fund = _funding("2021-01-01", "2021-01-10")
    _oran_ata(fund, "2021-01-05 08:00", 2e-4)
    _oran_ata(fund, "2021-01-05 16:00", -5e-4)
    _oran_ata(fund, "2021-01-06 00:00", 3e-4)
    # giris 04:00, 6 bar: cikis bari 01-05 00:00+20h, kapanis 01-06 04:00
    deger = _fon(fund, "2021-01-05 04:00", _cikis("2021-01-06 00:00"))
    assert deger == pytest.approx(2e-4 - 5e-4 + 3e-4)


def test_dort_saatlik_aralikta_normallestirilmemis_oran_toplanir():
    fund = _funding("2021-01-01", "2021-01-10", aralik_saat=4, oran=1e-4)
    deger = _fon(fund, "2021-01-05 00:00", _cikis("2021-01-05 20:00"))  # 04..00 -> 6 odeme
    assert deger == pytest.approx(6e-4)


def test_giris_anindaki_haric_cikis_anindaki_dahil():
    fund = _funding("2021-01-01", "2021-01-10")
    giris, cikis = "2021-01-05 00:00", _cikis("2021-01-05 20:00")  # an 01-06 00:00
    _oran_ata(fund, "2021-01-06 00:00", 7e-4)
    assert _fon(fund, giris, cikis) == pytest.approx(1e-4 + 1e-4 + 7e-4)

    bozuk = fund.copy()
    _oran_ata(bozuk, giris, 1.0)  # giris anindaki odeme
    _oran_ata(bozuk, "2021-01-06 08:00", 1.0)  # cikistan sonraki odeme
    _oran_ata(bozuk, "2021-01-04 16:00", 1.0)  # giristen onceki odeme
    assert _fon(bozuk, giris, cikis) == _fon(fund, giris, cikis)


def test_ileri_kaymali_cikista_an_barin_acilisidir():
    fund = _funding("2021-01-01", "2021-01-10", aralik_saat=4)
    _oran_ata(fund, "2021-01-05 20:00", 9e-4)
    giris = "2021-01-05 00:00"
    acilis = _fon(fund, giris, _cikis("2021-01-05 20:00", "open"))  # 04..20 -> 5 odeme
    kapanis = _fon(fund, giris, _cikis("2021-01-05 20:00", "close"))  # 04..00 -> 6 odeme
    assert acilis == pytest.approx(4e-4 + 9e-4)
    assert kapanis == pytest.approx(5e-4 + 9e-4)


def test_gunluk_barda_cikis_ani_ertesi_gun():
    fund = _funding("2021-01-01", "2021-01-20")
    deger = _fon(fund, "2021-01-05 00:00", _cikis("2021-01-06 00:00"), bar=config.BAR_1D)  # an 01-07 00:00
    assert deger == pytest.approx(6e-4)


@pytest.mark.parametrize("kayma", ["59s", "-59s", "1ms", "-1ms"])
def test_bir_dakikadan_kucuk_kayma_ayni_an_sayilir(kayma):
    fund = _funding("2021-01-01", "2021-01-10")
    _oran_ata(fund, "2021-01-05 00:00", 1.0)  # giris ani: haric kalmali
    _oran_ata(fund, "2021-01-06 00:00", 5e-4)  # cikis ani: dahil olmali
    kayik = fund.copy()
    kayik["odeme_zamani"] = kayik["odeme_zamani"] + pd.Timedelta(kayma)
    deger = _fon(kayik, "2021-01-05 00:00", _cikis("2021-01-05 20:00"))
    assert deger == pytest.approx(1e-4 + 1e-4 + 5e-4)


def test_tam_bir_dakikalik_kayma_ayni_an_sayilmaz():
    fund = _funding("2021-01-01", "2021-01-10")
    _oran_ata(fund, "2021-01-05 00:00", 2e-3)
    _oran_ata(fund, "2021-01-06 00:00", 5e-4)
    kayik = fund.copy()
    kayik["odeme_zamani"] = kayik["odeme_zamani"] + pd.Timedelta(minutes=1)
    # Giris odemesi 00:01 -> giristen sonra, dahil; cikis odemesi 00:01 -> cikistan sonra, haric.
    deger = _fon(kayik, "2021-01-05 00:00", _cikis("2021-01-05 20:00"))
    assert deger == pytest.approx(2e-3 + 1e-4 + 1e-4)


# --- Tamlik ------------------------------------------------------------------


@pytest.mark.parametrize(
    "eksik",
    ["2021-01-05 08:00", "2021-01-05 16:00", "2021-01-06 00:00"],
    ids=["bastaki", "ortadaki", "cikis_anindaki"],
)
def test_araliktaki_bir_odeme_eksikse_nan(eksik):
    fund = _funding("2021-01-01", "2021-01-10")
    fund = fund.loc[fund["odeme_zamani"] != _ts(eksik)].reset_index(drop=True)
    assert pd.isna(_fon(fund, "2021-01-05 00:00", _cikis("2021-01-05 20:00")))


def test_nan_oran_nan_doner():
    fund = _funding("2021-01-01", "2021-01-10")
    _oran_ata(fund, "2021-01-05 16:00", float("nan"))
    assert pd.isna(_fon(fund, "2021-01-05 00:00", _cikis("2021-01-05 20:00")))


def test_odemesiz_kisa_pozisyon_sifir():
    """8 saatlik aralikta 00:00 -> 04:00 tutulan pozisyona odeme dusmez."""
    fund = _funding("2021-01-01", "2021-01-10")
    assert _fon(fund, "2021-01-05 00:00", _cikis("2021-01-05 00:00")) == 0.0


def test_odemesiz_aralikta_beklenen_odeme_eksikse_nan():
    fund = _funding("2021-01-01", "2021-01-10", aralik_saat=4)
    assert _fon(fund, "2021-01-05 00:00", _cikis("2021-01-05 00:00")) == pytest.approx(1e-4)
    eksik = fund.loc[fund["odeme_zamani"] != _ts("2021-01-05 04:00")].reset_index(drop=True)
    assert pd.isna(_fon(eksik, "2021-01-05 00:00", _cikis("2021-01-05 00:00")))


def test_odemesiz_aralikta_onceki_kayit_yoksa_nan():
    fund = _funding("2021-01-05 08:00", "2021-01-10")
    assert pd.isna(_fon(fund, "2021-01-05 00:00", _cikis("2021-01-05 00:00")))


def test_bir_dakikadan_yakin_iki_kayit_bozuk_veridir():
    fund = _funding("2021-01-01", "2021-01-10")
    kopya = fund.iloc[[13]].copy()
    kopya["odeme_zamani"] = kopya["odeme_zamani"] + pd.Timedelta(milliseconds=1)
    bozuk = pd.concat([fund, kopya]).sort_values("odeme_zamani", ignore_index=True)
    with pytest.raises(pencere.ZamanDizisiHatasi):
        _fon(bozuk, "2021-01-05 00:00", _cikis("2021-01-05 20:00"))


# --- Kume (on-kayit §3 rev.4-5, §4 rev.6) ------------------------------------


KESIF_BAS, KESIF_SON = split.kume_araligi("KESIF")
C2_BAS = split.kume_araligi("C2")[0]


@pytest.mark.parametrize("kesik", [False, True], ids=["tam_veri", "kume_sinirinda_kesik_veri"])
def test_cikis_anindaki_odeme_kume_disindaysa_olay_olusmaz(kesik):
    fund = _funding("2025-08-20", "2025-09-10")
    if kesik:  # funding_yukle ciktisi gibi: kural veri kesimine dayanmaz
        fund = fund.loc[fund["odeme_zamani"] <= KESIF_SON].reset_index(drop=True)
    kume = dict(kume_baslangic=KESIF_BAS, kume_bitis=KESIF_SON)
    son_bar = KESIF_SON.floor("4h")  # 2025-08-31 20:00, kapanis 09-01 00:00
    giris = "2025-08-29 00:00"

    with pytest.raises(pencere.KumeSiniriHatasi):
        funding.pozisyon_fundingi(fund, _ts(giris), _cikis(str(son_bar)), config.BAR_4H, **{**SINIRSIZ, **kume})

    bir_once = _cikis(str(son_bar - DORT_SAAT))  # kapanis 08-31 20:00, kume icinde
    deger = funding.pozisyon_fundingi(fund, _ts(giris), bir_once, config.BAR_4H, **{**SINIRSIZ, **kume})
    assert deger == pytest.approx(8e-4)  # 29 08:00 .. 31 16:00


def test_kume_sonrasi_odemeleri_bozmak_kume_ici_sonucu_degistirmez():
    fund = _funding("2025-08-20", "2025-09-10")
    bozuk = fund.copy()
    bozuk.loc[bozuk["odeme_zamani"] > KESIF_SON, "oran"] = 1.0
    kume = dict(kume_baslangic=KESIF_BAS, kume_bitis=KESIF_SON)
    giris = _ts("2025-08-28 00:00")
    for bar_zamani in pd.date_range("2025-08-28 00:00", "2025-09-02 00:00", freq="4h", tz="UTC"):
        for alan in ("close", "open"):
            if alan == "open" and bar_zamani == giris:
                continue
            cikis = pencere.CikisSonucu(0, bar_zamani, alan, alan == "open", False)
            sonuclar = []
            for veri in (fund, bozuk):
                try:
                    sonuclar.append(funding.pozisyon_fundingi(veri, giris, cikis, config.BAR_4H, **{**SINIRSIZ, **kume}))
                except pencere.KumeSiniriHatasi:
                    sonuclar.append("olusmaz")
            assert sonuclar[0] == sonuclar[1], (bar_zamani, alan)
            if sonuclar[0] != "olusmaz":
                assert pencere.cikis_ani(cikis, config.BAR_4H) <= KESIF_SON


def test_giris_kume_basindan_onceyse_hata():
    fund = _funding("2025-08-25", "2025-09-10")
    with pytest.raises(pencere.KumeSiniriHatasi):
        _fon(fund, "2025-08-31 20:00", _cikis("2025-09-01 12:00"), kume_baslangic=C2_BAS)
    assert not pd.isna(_fon(fund, "2025-09-01 00:00", _cikis("2025-09-01 12:00"), kume_baslangic=C2_BAS))


def test_c2_basinda_giris_anindaki_odeme_kume_oncesi_kayit_okunmadan_haric():
    """Kume funding_yukle ile kesildiginde giris anindaki (kume basi) odeme bulunur,
    oncesi bulunmaz; tamlik kontrolu kume oncesi kayda ihtiyac duymamali."""
    fund = _funding("2025-09-01", "2025-09-10")
    deger = _fon(fund, "2025-09-01 00:00", _cikis("2025-09-01 20:00"), kume_baslangic=C2_BAS)
    assert deger == pytest.approx(3e-4)  # 08:00, 16:00, 00:00


# --- Donem ve karantina ------------------------------------------------------


def test_donem_sonuna_kirpilmis_cikista_funding_hesaplanir():
    """Donem sonu olayi dusurmez: donemin son barinin kapanisindaki odeme dahildir."""
    fund = _funding("2021-05-01", "2021-06-30")
    _oran_ata(fund, "2021-06-01 00:00", 7e-4)
    donem_bitis = _ts("2021-05-31 23:59:59.999999999")
    giris = "2021-05-30 00:00"
    deger = _fon(fund, giris, _cikis("2021-05-31 20:00"), donem_bitis=donem_bitis)  # an 06-01 00:00
    assert deger == pytest.approx(5e-4 + 7e-4)
    assert _fon(fund, giris, _cikis("2021-05-31 16:00"), donem_bitis=donem_bitis) == pytest.approx(5e-4)


def test_donem_sonuna_kirpilmamis_cikis_reddedilir():
    fund = _funding("2021-05-01", "2021-06-30")
    donem_bitis = _ts("2021-05-31 23:59:59.999999999")
    with pytest.raises(ValueError):
        _fon(fund, "2021-05-30 00:00", _cikis("2021-06-01 00:00"), donem_bitis=donem_bitis)


def test_giris_donem_basindan_onceyse_hata():
    """Bulgu 11: donem oncesi giris veri eksikligi degil programlama hatasidir;
    NaN donseydi olay dusme nedenlerinde "veri eksik" sayilirdi."""
    fund = _funding("2021-01-20", "2021-03-01")
    donem_bas = _ts("2021-02-01")
    with pytest.raises(ValueError) as hata:
        _fon(fund, "2021-01-31 20:00", _cikis("2021-02-01 12:00"), donem_baslangic=donem_bas)
    assert not isinstance(hata.value, pencere.KumeSiniriHatasi)
    assert not pd.isna(_fon(fund, "2021-02-01 00:00", _cikis("2021-02-01 12:00"), donem_baslangic=donem_bas))


def test_karantina_oncesi_son_kapanista_biten_cikista_funding_hesaplanir():
    """Karantina olayi dusurmez (kullanici karari, Revizyon 7'de yazilacak).

    cikis_bari ufku karantinaya uzanan pozisyonu 2021-05-31 20:00 barinin
    kapanisinda kirpar; cikis ani 06-01 00:00 karantina ayinin ilk anidir ve o
    andaki odeme dahil edilir. Olay olusur.
    """
    zamanlar = pd.date_range("2021-05-25", periods=100, freq="4h", tz="UTC")
    giris = _ts("2021-05-30 08:00")
    cikis = pencere.cikis_bari(
        zamanlar, giris, 18, config.BAR_4H,
        birincil_ufuk=18, donem_bitis=None, karantina_aylari=["2021-06"], kume_bitis=None,
    )
    assert cikis.kirpma_nedeni == "karantina" and cikis.zaman == _ts("2021-05-31 20:00")
    assert pencere.cikis_ani(cikis, config.BAR_4H) == _ts("2021-06-01 00:00")

    fund = _funding("2021-05-01", "2021-07-31")
    _oran_ata(fund, "2021-06-01 00:00", 7e-4)
    deger = funding.pozisyon_fundingi(
        fund, giris, cikis, config.BAR_4H, **{**SINIRSIZ, "karantina_aylari": ["2021-06"]}
    )
    # 05-30 16:00, 05-31 00:00, 08:00, 16:00 ve 06-01 00:00
    assert deger == pytest.approx(4e-4 + 7e-4)
    # Karantinaya gore kirpilmis cikis, karantina listesi verilmeden kullanilamaz (bulgu 5).
    with pytest.raises(ValueError):
        _fon(fund, "2021-05-30 08:00", cikis)


def test_karantina_ayina_kirpilmamis_cikis_ve_karantinada_giris_reddedilir():
    fund = _funding("2021-05-01", "2021-07-31")
    with pytest.raises(ValueError):
        _fon(fund, "2021-05-30 08:00", _cikis("2021-06-01 00:00"), karantina_aylari=["2021-06"])
    with pytest.raises(ValueError):
        _fon(fund, "2021-06-02 00:00", _cikis("2021-06-02 20:00"), karantina_aylari=["2021-06"])
    assert not pd.isna(_fon(fund, "2021-05-30 08:00", _cikis("2021-06-01 00:00"), karantina_aylari=["2021-04", "2021-07"]))


def test_cikis_bari_ile_kume_sonunda_biten_cikis_hata_verir():
    """Kume siniri davranisi degismedi: cikis_bari kume icinde son bari verir,
    ama o barin kapanisindaki odeme C2'ye duser -> olay olusmaz."""
    son_bar = KESIF_SON.floor("4h")
    zamanlar = pd.date_range(end=son_bar, periods=60, freq="4h")
    giris = son_bar - 17 * DORT_SAAT
    kume = dict(kume_baslangic=KESIF_BAS, kume_bitis=KESIF_SON)
    cikis = pencere.cikis_bari(
        zamanlar, giris, 18, config.BAR_4H, birincil_ufuk=18, donem_bitis=None, karantina_aylari=None, kume_bitis=KESIF_SON
    )
    assert cikis.zaman == son_bar and not cikis.kirpildi
    fund = _funding("2025-08-20", "2025-08-31 23:00")
    with pytest.raises(pencere.KumeSiniriHatasi):
        funding.pozisyon_fundingi(fund, giris, cikis, config.BAR_4H, **{**SINIRSIZ, **kume})


# --- Zorunluluk --------------------------------------------------------------


@pytest.mark.parametrize("eksik", list(SINIRSIZ))
def test_sinir_unutulursa_hata(eksik):
    fund = _funding("2021-01-01", "2021-01-10")
    parametreler = dict(SINIRSIZ)
    del parametreler[eksik]
    with pytest.raises(TypeError):
        funding.pozisyon_fundingi(fund, _ts("2021-01-05 00:00"), _cikis("2021-01-05 20:00"), config.BAR_4H, **parametreler)


@pytest.mark.parametrize("alan", ["giris", "kume_bitis", "donem_bitis"])
def test_saat_dilimsiz_zaman_reddedilir(alan):
    fund = _funding("2021-01-01", "2021-01-10")
    giris = _ts("2021-01-05 00:00")
    parametreler = dict(SINIRSIZ)
    if alan == "giris":
        giris = giris.tz_localize(None)
    else:
        parametreler[alan] = pd.Timestamp("2021-12-31")
    with pytest.raises(TypeError):
        funding.pozisyon_fundingi(fund, giris, _cikis("2021-01-05 20:00"), config.BAR_4H, **parametreler)


def test_cikis_zaman_damgasi_olarak_verilemez():
    """Bar zamani cikis ani sanilirsa cikis anindaki odeme kacardi."""
    fund = _funding("2021-01-01", "2021-01-10")
    with pytest.raises(TypeError):
        _fon(fund, "2021-01-05 00:00", _ts("2021-01-05 20:00"))


def _elle(zaman: str, fiyat_alani="close", kaydi=None, kirpildi=False, neden=None):
    kaydi = (fiyat_alani == "open") if kaydi is None else kaydi
    return pencere.CikisSonucu(0, _ts(zaman), fiyat_alani, kaydi, kirpildi, neden)


def test_karantina_ayindaki_barin_acilisindan_cikis_reddedilir():
    """F1 kapanis denetimi bulgu 5: cikis ANI sinira esit olsa da cikis BARI
    karantina ayinda; cikis_bari boyle bir cikis uretmez."""
    fund = _funding("2021-05-01", "2021-07-31")
    with pytest.raises(ValueError):
        _fon(fund, "2021-05-30 08:00", _elle("2021-06-01 00:00", "open"), karantina_aylari=["2021-06"])
    assert not pd.isna(_fon(fund, "2021-05-30 08:00", _elle("2021-05-31 20:00", "open"), karantina_aylari=["2021-06"]))


def test_donem_disindaki_barin_acilisindan_cikis_reddedilir():
    fund = _funding("2021-05-01", "2021-06-30")
    donem_bitis = _ts("2021-05-31 23:59:59.999999999")
    with pytest.raises(ValueError):
        _fon(fund, "2021-05-30 00:00", _elle("2021-06-01 00:00", "open"), donem_bitis=donem_bitis)


def test_gunluk_barda_karantina_ayindaki_gun_reddedilir():
    fund = _funding("2021-05-01", "2021-07-31")
    with pytest.raises(ValueError):
        _fon(fund, "2021-05-20 00:00", _elle("2021-06-01 00:00"), bar=config.BAR_1D, karantina_aylari=["2021-06"])
    son_gun = _elle("2021-05-31 00:00", kirpildi=True, neden="karantina")
    assert not pd.isna(_fon(fund, "2021-05-20 00:00", son_gun, bar=config.BAR_1D, karantina_aylari=["2021-06"]))


@pytest.mark.parametrize(
    "cikis",
    [
        pytest.param(lambda: _elle("2021-01-05 20:00", "open", kaydi=False), id="acilis_ama_kaymadi"),
        pytest.param(lambda: _elle("2021-01-05 20:00", "close", kaydi=True), id="kapanis_ama_kaydi"),
        pytest.param(lambda: _elle("2021-01-05 20:00", "open", kirpildi=True, neden="karantina"), id="kirpilmis_acilis"),
        pytest.param(lambda: _elle("2021-01-05 20:00", kirpildi=True, neden=None), id="kirpilmis_nedensiz"),
        pytest.param(lambda: _elle("2021-01-05 20:00", kirpildi=True, neden="kume_sonu"), id="bilinmeyen_neden"),
        pytest.param(lambda: _elle("2021-01-05 20:00", kirpildi=False, neden="donem_sonu"), id="kirpilmamis_nedenli"),
        pytest.param(lambda: _elle("2021-01-05 20:00", kirpildi=1), id="kirpildi_bool_degil"),
    ],
)
def test_tutarsiz_elle_kurulmus_cikis_reddedilir(cikis):
    fund = _funding("2021-01-01", "2021-01-10")
    with pytest.raises(ValueError):
        _fon(fund, "2021-01-05 00:00", cikis())


@pytest.mark.parametrize("neden", ["donem_sonu", "karantina"])
def test_kirpma_nedeninin_siniri_verilmemisse_reddedilir(neden):
    fund = _funding("2021-01-01", "2021-01-10")
    with pytest.raises(ValueError):
        _fon(fund, "2021-01-05 00:00", _elle("2021-01-05 20:00", kirpildi=True, neden=neden))


def test_cikis_giristen_once_olamaz():
    fund = _funding("2021-01-01", "2021-01-10")
    with pytest.raises(ValueError):
        _fon(fund, "2021-01-05 04:00", _cikis("2021-01-05 04:00", "open"))
