"""Pozisyon funding'i testleri (on-kayit §4 rev.6-7).

Pozisyon giris anindan sonra ve cikis anina kadar gerceklesen odemeleri alir ya
da oder: giris anindaki haric, cikis anindaki dahil; 1 dakikadan kucuk kayma ayni
an sayilir. Rev.7: olayin kumede, donemde ve ufukta olusup olusmadigina tek kapi
`pencere.pozisyon_plani` karar verir; `pozisyon_fundingi` yalnizca plan alir ve
yalnizca veri tamligina bakar.
"""

from __future__ import annotations

import dataclasses

import pandas as pd
import pytest

import config
from data import funding, pencere, split

DORT_SAAT = pd.Timedelta(hours=4)
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


def _oran_ata(fund: pd.DataFrame, zaman: str, oran: float) -> None:
    fund.loc[fund["odeme_zamani"] == _ts(zaman), "oran"] = oran


def _plan(giris, cikis_bari, alan: str = "close", bar=config.BAR_4H, **sinirlar) -> pencere.PozisyonPlani:
    """Tek kapidan gecen plan: girisi `giris`, cikis bari `cikis_bari` olan pozisyon.

    Kapanistan cikista hedef bar `cikis_bari`dir. Acilistan (ileri kaymali) cikista
    hedef bar `cikis_bari - adim` seriden silinir ve sonraki mevcut bar
    `cikis_bari` olur.
    """
    g, c = _ts(giris), _ts(cikis_bari)
    a = pencere.adim(bar)
    zamanlar = pd.date_range(g - 5 * a, c + 40 * a, freq="4h")
    hedef = c if alan == "close" else c - a
    if alan == "open":
        assert hedef > g, "ileri kaymali cikis icin hedef bar giristen sonra olmali"
        zamanlar = zamanlar.drop(c - DORT_SAAT)  # kapanisi T = c olan hedef 4h bari
    ufuk = int((hedef - g) / a) + 1
    donem = dict(donem_baslangic=zamanlar[0], donem_bitis=zamanlar[-1])
    return pencere.pozisyon_plani(
        zamanlar, g - a, ufuk, bar, birincil_ufuk=max(ufuk, 18), **{**SINIRSIZ, **donem, **sinirlar}
    )


def _fon(fund, giris, cikis_bari, alan: str = "close", bar=config.BAR_4H, **sinirlar):
    return funding.pozisyon_fundingi(fund, _plan(giris, cikis_bari, alan, bar, **sinirlar))


# --- Cikis ani ---------------------------------------------------------------


def _cikis(zaman: str, fiyat_alani: str = "close") -> pencere.CikisSonucu:
    """Elle kurulan tutarli cikis (rev.8 alanlari): kapanista olagan (T = acilis + 4h),
    acilista 4 saatlik ileri kayma."""
    z = _ts(zaman)
    if fiyat_alani == "open":
        return pencere.CikisSonucu(0, z, "open", z, "ileri_kayma", z, DORT_SAAT)
    return pencere.CikisSonucu(0, z, "close", z + DORT_SAAT, "olagan", z + DORT_SAAT, pd.Timedelta(0))


def test_cikis_ani_kapanista_bar_sonu_acilista_bar_basi():
    """Rev.8 §4 "Fiyat okuma tabani": her izgarada cikis bari 4h bardir; kapanista
    cikis ani acilis + 4 saat, acilista (ileri kayma) acilis. Rev.7'de 1d izgarasinda
    gunluk barin kapanisi (acilis + 24 saat) bekleniyordu; `cikis_ani` artik izgara
    adimi almaz (§4 "Olayin kumede olusma olcutu": cikis ani izgaranin adimindan
    turetilmez)."""
    assert pencere.cikis_ani(_cikis("2021-01-05 20:00")) == _ts("2021-01-06 00:00")
    assert pencere.cikis_ani(_cikis("2021-01-05 20:00", "open")) == _ts("2021-01-05 20:00")
    assert pencere.cikis_ani(_cikis("2021-01-05 00:00")) == _ts("2021-01-05 04:00")


def test_cikis_ani_zaman_damgasi_kabul_etmez():
    with pytest.raises(TypeError):
        pencere.cikis_ani(_ts("2021-01-05 20:00"), config.BAR_4H)


def test_plan_cikis_ani_ile_ayni():
    plan = _plan("2021-01-05 00:00", "2021-01-05 20:00", "open")
    assert plan.cikis.fiyat_alani == "open" and plan.cikis_ani == _ts("2021-01-05 20:00")
    assert pencere.cikis_ani(plan.cikis) == plan.cikis_ani


# --- Temel hesap ve giris/cikis sinirlari ------------------------------------


def test_odemelerin_toplami_gercek_oranla():
    fund = _funding("2021-01-01", "2021-01-10")
    _oran_ata(fund, "2021-01-05 08:00", 2e-4)
    _oran_ata(fund, "2021-01-05 16:00", -5e-4)
    _oran_ata(fund, "2021-01-06 00:00", 3e-4)
    # giris 04:00, cikis bari 01-06 00:00, kapanis 01-06 04:00
    deger = _fon(fund, "2021-01-05 04:00", "2021-01-06 00:00")
    assert deger == pytest.approx(2e-4 - 5e-4 + 3e-4)


def test_dort_saatlik_aralikta_normallestirilmemis_oran_toplanir():
    fund = _funding("2021-01-01", "2021-01-10", aralik_saat=4, oran=1e-4)
    assert _fon(fund, "2021-01-05 00:00", "2021-01-05 20:00") == pytest.approx(6e-4)


def test_giris_anindaki_haric_cikis_anindaki_dahil():
    fund = _funding("2021-01-01", "2021-01-10")
    giris, cikis = "2021-01-05 00:00", "2021-01-05 20:00"  # an 01-06 00:00
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
    acilis = _fon(fund, giris, "2021-01-05 20:00", "open")  # 04..20 -> 5 odeme
    kapanis = _fon(fund, giris, "2021-01-05 20:00", "close")  # 04..00 -> 6 odeme
    assert acilis == pytest.approx(4e-4 + 9e-4)
    assert kapanis == pytest.approx(5e-4 + 9e-4)


def test_gunluk_barda_cikis_ani_ertesi_gun():
    fund = _funding("2021-01-01", "2021-03-20")
    deger = _fon(fund, "2021-01-05 00:00", "2021-01-06 00:00", bar=config.BAR_1D)  # an 01-07 00:00
    assert deger == pytest.approx(6e-4)


@pytest.mark.parametrize("kayma", ["59s", "-59s", "1ms", "-1ms"])
def test_bir_dakikadan_kucuk_kayma_ayni_an_sayilir(kayma):
    fund = _funding("2021-01-01", "2021-01-10")
    _oran_ata(fund, "2021-01-05 00:00", 1.0)  # giris ani: haric kalmali
    _oran_ata(fund, "2021-01-06 00:00", 5e-4)  # cikis ani: dahil olmali
    kayik = fund.copy()
    kayik["odeme_zamani"] = kayik["odeme_zamani"] + pd.Timedelta(kayma)
    assert _fon(kayik, "2021-01-05 00:00", "2021-01-05 20:00") == pytest.approx(1e-4 + 1e-4 + 5e-4)


def test_tam_bir_dakikalik_kayma_ayni_an_sayilmaz():
    fund = _funding("2021-01-01", "2021-01-10")
    _oran_ata(fund, "2021-01-05 00:00", 2e-3)
    _oran_ata(fund, "2021-01-06 00:00", 5e-4)
    kayik = fund.copy()
    kayik["odeme_zamani"] = kayik["odeme_zamani"] + pd.Timedelta(minutes=1)
    # Giris odemesi 00:01 -> giristen sonra, dahil; cikis odemesi 00:01 -> cikistan sonra, haric.
    assert _fon(kayik, "2021-01-05 00:00", "2021-01-05 20:00") == pytest.approx(2e-3 + 1e-4 + 1e-4)


# --- Tamlik ------------------------------------------------------------------


@pytest.mark.parametrize(
    "eksik",
    ["2021-01-05 08:00", "2021-01-05 16:00", "2021-01-06 00:00"],
    ids=["bastaki", "ortadaki", "cikis_anindaki"],
)
def test_araliktaki_bir_odeme_eksikse_nan(eksik):
    fund = _funding("2021-01-01", "2021-01-10")
    fund = fund.loc[fund["odeme_zamani"] != _ts(eksik)].reset_index(drop=True)
    assert pd.isna(_fon(fund, "2021-01-05 00:00", "2021-01-05 20:00"))


def test_nan_oran_nan_doner():
    fund = _funding("2021-01-01", "2021-01-10")
    _oran_ata(fund, "2021-01-05 16:00", float("nan"))
    assert pd.isna(_fon(fund, "2021-01-05 00:00", "2021-01-05 20:00"))


def test_odemesiz_kisa_pozisyon_sifir():
    """8 saatlik aralikta 00:00 -> 04:00 tutulan pozisyona odeme dusmez. Rev.8 §4
    "Funding araligi gecisleri": "Penceresinde hic funding kaydi bulunmayan pozisyonun
    funding'i tam degildir" (beklenti 0.0 -> NaN)."""
    fund = _funding("2021-01-01", "2021-01-10")
    assert pd.isna(_fon(fund, "2021-01-05 00:00", "2021-01-05 00:00"))


def test_odemesiz_aralikta_beklenen_odeme_eksikse_nan():
    fund = _funding("2021-01-01", "2021-01-10", aralik_saat=4)
    assert _fon(fund, "2021-01-05 00:00", "2021-01-05 00:00") == pytest.approx(1e-4)
    eksik = fund.loc[fund["odeme_zamani"] != _ts("2021-01-05 04:00")].reset_index(drop=True)
    assert pd.isna(_fon(eksik, "2021-01-05 00:00", "2021-01-05 00:00"))


def test_odemesiz_aralikta_onceki_kayit_yoksa_nan():
    fund = _funding("2021-01-05 08:00", "2021-01-10")
    assert pd.isna(_fon(fund, "2021-01-05 00:00", "2021-01-05 00:00"))


def test_bir_dakikadan_yakin_iki_kayit_bozuk_veridir():
    fund = _funding("2021-01-01", "2021-01-10")
    kopya = fund.iloc[[13]].copy()
    kopya["odeme_zamani"] = kopya["odeme_zamani"] + pd.Timedelta(milliseconds=1)
    bozuk = pd.concat([fund, kopya]).sort_values("odeme_zamani", ignore_index=True)
    with pytest.raises(pencere.ZamanDizisiHatasi):
        _fon(bozuk, "2021-01-05 00:00", "2021-01-05 20:00")


# --- Kume (on-kayit §3 rev.4-5, §4 rev.7): karar planda ----------------------


KESIF_BAS, KESIF_SON = split.kume_araligi("KESIF")
C2_BAS = split.kume_araligi("C2")[0]


@pytest.mark.parametrize("kesik", [False, True], ids=["tam_veri", "kume_sinirinda_kesik_veri"])
def test_cikis_anindaki_odeme_kume_disindaysa_olay_olusmaz(kesik):
    """Karar plan asamasinda ve ZAMANLA verilir; funding verisinin kume
    sinirinda kesilmis olup olmamasi hukmu degistirmez (rev.5)."""
    fund = _funding("2025-08-20", "2025-09-10")
    if kesik:  # funding_yukle ciktisi gibi
        fund = fund.loc[fund["odeme_zamani"] <= KESIF_SON].reset_index(drop=True)
    kume = dict(kume_baslangic=KESIF_BAS, kume_bitis=KESIF_SON)
    son_bar = KESIF_SON.floor("4h")  # 2025-08-31 20:00, kapanis 09-01 00:00
    giris = "2025-08-29 00:00"

    with pytest.raises(pencere.KumeSiniriHatasi):
        _fon(fund, giris, son_bar, **kume)

    deger = _fon(fund, giris, son_bar - DORT_SAAT, **kume)  # kapanis 08-31 20:00, kume icinde
    assert deger == pytest.approx(8e-4)  # 29 08:00 .. 31 16:00


def test_kume_sonrasi_odemeleri_bozmak_kume_ici_sonucu_degistirmez():
    fund = _funding("2025-08-20", "2025-09-10")
    bozuk = fund.copy()
    bozuk.loc[bozuk["odeme_zamani"] > KESIF_SON, "oran"] = 1.0
    kume = dict(kume_baslangic=KESIF_BAS, kume_bitis=KESIF_SON)
    giris = _ts("2025-08-28 00:00")
    for bar_zamani in pd.date_range("2025-08-28 00:00", "2025-09-02 00:00", freq="4h", tz="UTC"):
        for alan in ("close", "open"):
            if alan == "open" and bar_zamani - DORT_SAAT <= giris:
                continue
            sonuclar = []
            for veri in (fund, bozuk):
                try:
                    sonuclar.append(_fon(veri, giris, bar_zamani, alan, **kume))
                except pencere.KumeSiniriHatasi:
                    sonuclar.append("olusmaz")
            # NaN (rev.8: penceresinde kayit olmayan pozisyon) iki veride de NaN olmali.
            ayni = (sonuclar[0] == sonuclar[1]) or all(
                not isinstance(x, str) and pd.isna(x) for x in sonuclar)
            assert ayni, (bar_zamani, alan)
            if sonuclar[0] != "olusmaz":
                plan = _plan(giris, bar_zamani, alan, **kume)
                assert plan.cikis_ani + funding.ODEME_TOLERANSI <= KESIF_SON + pd.Timedelta(1, "ns")


def test_sinyal_kume_basindan_onceyse_olay_olusmaz():
    fund = _funding("2025-08-25", "2025-09-10")
    with pytest.raises(pencere.KumeSiniriHatasi):  # sinyal 08-31 20:00 < C2 basi
        _fon(fund, "2025-09-01 00:00", "2025-09-01 12:00", kume_baslangic=C2_BAS)
    assert not pd.isna(_fon(fund, "2025-09-01 04:00", "2025-09-01 12:00", kume_baslangic=C2_BAS))


def test_c2_basinda_kume_oncesi_kayit_okunmadan_tamlik():
    """Kume funding_yukle ile kesildiginde kume basindaki odeme bulunur, oncesi
    bulunmaz; tamlik kontrolu kume oncesi kayda ihtiyac duymamali."""
    fund = _funding("2025-09-01", "2025-09-10")
    deger = _fon(fund, "2025-09-01 04:00", "2025-09-01 20:00", kume_baslangic=C2_BAS)
    assert deger == pytest.approx(3e-4)  # 08:00, 16:00, 00:00


def test_kume_oncesi_kayit_tamlik_icin_okunmaz():
    """Araliktaki ilk odeme kume basinda degil ve onceki kayit kume oncesinde.
    Rev.8 §4 "Funding araligi gecisleri": baslangic tamligi onceki kaydi okumaz;
    giris ani ile ilk odeme (12:00) arasindaki bosluk (8 saat) ilk kaydin araligini
    asmaz, funding tamdir (rev.7'de onceki kayit kume oncesinde oldugu icin NaN
    bekleniyordu). Kume oncesi kayit hala okunmaz: bozulmasi sonucu degistirmez."""
    fund = pd.DataFrame({
        "odeme_zamani": pd.date_range(C2_BAS - pd.Timedelta(hours=4), C2_BAS + pd.Timedelta(days=3), freq="8h"),
        "aralik_saat": 8.0, "oran": 1e-4,
    })  # 08-31 20:00, 09-01 04:00, 12:00, ...
    fund["oran_8h"] = fund["oran"]
    ilk = fund.loc[fund["odeme_zamani"] >= C2_BAS].reset_index(drop=True)  # 09-01 04:00'ten itibaren
    ek = fund.iloc[[0]]  # kume oncesi 08-31 20:00
    veri = pd.concat([ek, ilk.iloc[1:]], ignore_index=True)  # 09-01 04:00 eksik -> onceki kayit kume oncesi
    giris, cikis = C2_BAS + DORT_SAAT, C2_BAS + 3 * DORT_SAAT
    assert _fon(veri, giris, cikis, kume_baslangic=C2_BAS) == pytest.approx(1e-4)
    bozuk = veri.copy()
    bozuk.loc[0, ["aralik_saat", "oran"]] = [1000.0, 9.0]  # kume oncesi kayit
    assert _fon(bozuk, giris, cikis, kume_baslangic=C2_BAS) == pytest.approx(1e-4)


# --- Donem -------------------------------------------------------------------


def test_donem_sonuna_kirpilmis_cikista_funding_hesaplanir():
    """Donem sonu olayi dusurmez: donemin son barinin kapanisindaki odeme dahildir."""
    fund = _funding("2021-05-01", "2021-06-30")
    _oran_ata(fund, "2021-06-01 00:00", 7e-4)
    donem_bitis = _ts("2021-05-31 23:59:59.999999999")
    giris = "2021-05-30 00:00"
    deger = _fon(fund, giris, "2021-05-31 20:00", donem_bitis=donem_bitis)  # an 06-01 00:00
    assert deger == pytest.approx(5e-4 + 7e-4)
    assert _fon(fund, giris, "2021-05-31 16:00", donem_bitis=donem_bitis) == pytest.approx(5e-4)


def test_donem_sonunu_asan_ufuk_planda_kirpilir():
    """Rev.7 tek kapi: kirpilmamis bir cikis artik uretilemez; plan donem sonunda kirpar.
    Rev.8: B donemin son mevcut baridir (rev.7 testi B'yi bar olmayan bir ana koyuyordu)."""
    donem_bitis = _ts("2021-05-31 20:00")
    plan = _plan("2021-05-30 00:00", "2021-06-01 00:00", donem_bitis=donem_bitis)
    assert plan.cikis.kirpildi and plan.cikis.kirpma_nedeni == "donem_sonu"
    assert plan.cikis.zaman == _ts("2021-05-31 20:00")
    fund = _funding("2021-05-01", "2021-06-30")
    # Rev.8 §4 "Donem sonu istisnasi": pencere B'de (dahil) kapanir; K'daki (06-01 00:00)
    # odeme hesaba girmez (rev.7'de 6 odeme, rev.8'de 5).
    assert funding.pozisyon_fundingi(fund, plan) == pytest.approx(5e-4)


def test_sinyal_donem_basindan_onceyse_hata():
    """Bulgu 11: donem oncesi sinyal veri eksikligi degil programlama hatasidir."""
    fund = _funding("2021-01-20", "2021-03-01")
    donem_bas = _ts("2021-02-01")
    with pytest.raises(ValueError) as hata:
        _fon(fund, "2021-01-31 20:00", "2021-02-01 12:00", donem_baslangic=donem_bas)
    assert not isinstance(hata.value, pencere.OlayOlusmaz)
    assert not pd.isna(_fon(fund, "2021-02-01 04:00", "2021-02-01 12:00", donem_baslangic=donem_bas))


def test_cikis_bari_kabul_etse_de_plan_kume_sonunda_reddeder():
    """Kumenin son barindan cikis: o barin kapanisindaki odeme C2'ye duser; olay
    olusmaz. Rev.8: kume olcutu gercek cikis anina `cikis_bari` ic adiminda da ayni
    fonksiyonla uygulanir (rev.7'de ic adim kabul ediyor, yalnizca plan
    reddediyordu). Kume sinirsiz ic adim son bari verir."""
    son_bar = KESIF_SON.floor("4h")
    zamanlar = pd.date_range(end=son_bar, periods=60, freq="4h")
    giris = son_bar - 17 * DORT_SAAT
    donem_bitis = _ts("2026-08-31 20:00")  # donem kumeden sonra suruyor
    cikis = pencere.cikis_bari(zamanlar, giris, 18, config.BAR_4H, birincil_ufuk=18, donem_bitis=donem_bitis, kume_bitis=None)
    assert cikis.zaman == son_bar and not cikis.kirpildi
    with pytest.raises(pencere.KumeSiniriHatasi):
        pencere.cikis_bari(zamanlar, giris, 18, config.BAR_4H, birincil_ufuk=18, donem_bitis=donem_bitis, kume_bitis=KESIF_SON)
    with pytest.raises(pencere.KumeSiniriHatasi):
        pencere.pozisyon_plani(zamanlar, giris - DORT_SAAT, 18, config.BAR_4H, birincil_ufuk=18,
                               kume_baslangic=KESIF_BAS, kume_bitis=KESIF_SON, donem_baslangic=zamanlar[0],
                               donem_bitis=donem_bitis)


# --- Yalnizca plan -----------------------------------------------------------


def test_plan_disinda_girdi_reddedilir():
    fund = _funding("2021-01-01", "2021-01-10")
    with pytest.raises(TypeError):
        funding.pozisyon_fundingi(fund, _cikis("2021-01-05 20:00"))
    with pytest.raises(TypeError):
        funding.pozisyon_fundingi(fund, _ts("2021-01-05 20:00"))


def test_eski_imza_reddedilir():
    """Rev.6 imzasi (giris, cikis, bar, sinirlar) artik yok."""
    fund = _funding("2021-01-01", "2021-01-10")
    with pytest.raises(TypeError):
        funding.pozisyon_fundingi(fund, _ts("2021-01-05 00:00"), _cikis("2021-01-05 20:00"), config.BAR_4H, **SINIRSIZ)


def test_elle_kurulmus_ya_da_degistirilmis_plan_reddedilir():
    fund = _funding("2021-01-01", "2021-01-10")
    plan = _plan("2021-01-05 00:00", "2021-01-05 20:00")
    assert not pd.isna(funding.pozisyon_fundingi(fund, plan))

    with pytest.raises(ValueError):  # cikis anini uzat: daha fazla odeme toplanirdi
        funding.pozisyon_fundingi(fund, dataclasses.replace(plan, cikis_ani=plan.cikis_ani + pd.Timedelta(hours=8)))
    with pytest.raises(ValueError):  # kume sinirini sonradan degistir
        funding.pozisyon_fundingi(fund, dataclasses.replace(plan, kume_bitis=_ts("2030-01-01")))
    elle = pencere.PozisyonPlani(**{f.name: getattr(plan, f.name) for f in dataclasses.fields(plan) if f.name != "_imza"})
    with pytest.raises(ValueError):
        funding.pozisyon_fundingi(fund, elle)
