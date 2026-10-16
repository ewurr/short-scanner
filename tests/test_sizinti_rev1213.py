"""Sizinti testcisi: on-kayit Rev.12 ve Rev.13'un veri katmanina ait maddelerine saldiri.

Bu dosya YALNIZCA saldiri testidir; mevcut hicbir test, yardimci ya da `data/` dosyasina dokunmaz.
Aga cikmaz, getiri hesaplamaz. Kilitli dosyalara (PREREGISTRATION.md, data/split.csv, KILIT.md ...) yazmaz;
KILIT.md denemeleri gecici dizinlerde ve gecici git depolarinda yapilir.

Basarili saldirilar (kodda gercek acik) `xfail(strict=True)` ile isaretlidir: acik kapanirsa test XPASS olur
ve strict oldugu icin KIRMIZIYA doner; o zaman isaret kaldirilmalidir. Normal gecen testler savusturulan
saldirilardir.

Baslik -> test eslemesi
-----------------------
1. Dizi kapisi (on-kayit §4 rev.12 "Olayin kumede olusma olcutu", §5):
   test_elle_kurulan_olay_dogrulanamaz, test_olay_olmayan_nesne_olay_dogrulamasindan_gecemez,
   test_kapinin_onayi_tek_basina_olay_degildir, test_dizinin_urettigi_olay_dogrulanir_olumlu_kontrol, test_olay_alanlari_replace_ile_degistirilemez,
   test_olaya_baska_pozisyon_replace_ile_takilamaz, test_olayin_pozisyonu_bozulunca_getiri_girdisi_olamaz,
   test_olayin_icindeki_pozisyon_replace_ile_bozulunca_olay_dogrulanamaz (XFAIL),
   test_ayni_dizi_cagrisinda_ayni_sembol_donem_kume_onaylari_kabul_edilir_olumlu_kontrol,
   test_ayni_dizi_cagrisinda_farkli_sembol_donem_kume_onaylari_karisamaz (XFAIL),
   test_kapinin_olay_olusmaz_disindaki_hatalari_ret_sayilmaz, test_bool_olmayan_kosul_yaniti_reddedilir,
   test_hesaplanamaz_yanitlari_olay_uretmez_ret_olur.
2. Kontrol barindaki pencere sarti (on-kayit §6 rev.12):
   test_kontrol_barinda_kosul_ve_deger_kuruculari_cagrilmaz, test_kontrol_roluna_capa_verilemez,
   test_str_alt_sinifi_rol_reddedilir, test_capasiz_pencere_sonlu_olmayan_deger_hesaplanamaz_sayilir,
   test_olay_degeri_sonlu_olmayan_deger_hesaplanamaz_sayilir.
3. Izleme penceresinin sinirlari (on-kayit §5 H1 madde 4, rev.13):
   test_reddedilen_teyit_izlemeyi_bitirir_ikinci_teyit_olay_sayilmaz,
   test_izleme_surerken_gelen_ikinci_pump_sayaci_uzatmaz_ve_teyidi_capalamaz,
   test_eksik_barli_seride_12_bar_teyidi_dahil_13_bar_haric,
   test_gercek_kosul_t_den_sonraki_barlara_ve_fundinge_bakmaz (gelecege bakis, gercek `sinyal_kosulu`),
   test_kesif_kosulu_kume_sonundan_sonraki_barlari_hic_gormez (kume siniri, gercek `sinyal_kosulu`).
4. H3 dizisinin takvim tabani (on-kayit §5 H3 madde 3, rev.13):
   test_h3_hesaplanamayan_gunle_baslayan_dizinin_ilk_gunu_ikinci_gundur,
   ve butun hipotezler icin: test_dizi_gelecege_bakmaz_onek_ile_tam_kosu_ayni_olaylari_verir,
   test_dizi_tamsayi_modeliyle_ayni_olaylari_verir (rastgele bosluklu seriler, sabit tohum).
5. Olay basina agirliklandirma (on-kayit §7 rev.13):
   test_havuzlar_birlestirilmez_olay_basina_agirliklandirma, test_yeniden_ornekle_ayni_olcekte_yanit_verir,
   test_istatistik_sinir_esitligi_r_e_dahildir, test_istatistik_girdi_denetimleri,
   test_yeniden_ornekle_tohumu_cagirandan_almaz, test_alt_tohum_demetin_her_ekseninde_degisir,
   test_yeniden_ornekle_tekrar_ve_demet_denetimleri, test_yeniden_ornekle_deterministiktir.
6. KILIT.md okumasi (on-kayit §8 madde 5, rev.13):
   test_baska_hipotezin_kaydi_varken_kaydi_olmayan_hipotez_icin_kosu_acilmaz,
   test_ikinci_kayit_eklenen_kilit_bozuktur, test_gercek_git_*  (calisma agaci/HEAD/izlenmeyen/silinmis),
   (KAPANDI: test_secildi_hukmunde_k2_farki_pozitif_olmak_zorunda,
   test_k2_farki_pozitif_olmayan_kilitle_onay_kosusu_acilmaz -- madde 2a)
   (KAPANDI: butun kilit bulgulari -- maddeler 2a-2g)
   test_gercek_git_commitli_kapandi_kaydi_hipotez_kapandi_hatasi_verir,
"""

from __future__ import annotations

import dataclasses
import inspect
import math

import numpy as np
import pandas as pd
import pytest

import config
from data import dizi, istatistik, pencere, pozisyon, sinyal, split
from kapi_yardimcisi import veri
from kume_yardimcisi import kume_adi
from onay_yardimcisi import gecici_depo, gecici_kayit, git, kilit_metni, kilit_yaz, kilitleri_kur, kosu, uzak_depo
from sinyal_yardimcisi import kontrol, yapilandirma
from uygunluk_yardimcisi import esikler

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
UFUK4 = config.BIRINCIL_UFUK[config.BAR_4H]
UFUK1 = config.BIRINCIL_UFUK[config.BAR_1D]
IZ4 = pd.date_range(T("2025-03-01 00:00"), periods=90, freq="4h")
IZ1 = pd.date_range(T("2025-03-01"), periods=90, freq="D")
Y1, Y2, Y3 = yapilandirma("H1"), yapilandirma("H2"), yapilandirma("H3")


# =================================================================================================
# Ortak yardimcilar (dizi seviyesi)
# =================================================================================================


DIZI_KIMLIGI = dict(sembol="TESTONAYUSDT", kume="KESIF", donem_no=0)

def _h1_onay(t, capa=None, **ek):
    return pozisyon._test_onayi(hipotez="H1", yapilandirma=Y1, t=t, capa=capa, **ek)


def _h2_onay(t, capa=None, **ek):
    return pozisyon._test_onayi(hipotez="H2", yapilandirma=Y2, t=t, capa=capa, **ek)


def _h3_onay(t, capa=None, **ek):
    return pozisyon._test_onayi(hipotez="H3", yapilandirma=Y3, t=t, capa=capa, **ek)


def _h2_dizi(karar, idxler, kosul=None, **kimlik):
    """Kimlik madde 3a'dan beri cagridan gelir (bulgu K-B1); varsayilan `_test_onayi` ile ayni."""
    return dizi.olay_dizisi("H2", Y2, IZ4[list(idxler)], config.BAR_4H, birincil_ufuk=UFUK4,
                            kosul=kosul if kosul is not None else (lambda t, capa: True), karar=karar,
                            **{**DIZI_KIMLIGI, **kimlik})


def _h1_dizi(idxler, kosul, karar=_h1_onay):
    return dizi.olay_dizisi("H1", Y1, IZ4[list(idxler)], config.BAR_4H, birincil_ufuk=UFUK4,
                            kosul=kosul, karar=karar, **DIZI_KIMLIGI)


def _h3_dizi(idxler, kosul, karar=_h3_onay):
    return dizi.olay_dizisi("H3", Y3, IZ1[list(idxler)], config.BAR_1D, birincil_ufuk=UFUK1,
                            kosul=kosul, karar=karar, **DIZI_KIMLIGI)


def _h1_kosul(pumplar, teyitler):
    """Sahte H1 kosulu: `capa=None` pump, `capa=p` p capali teyit. Cagrilari kaydeder."""
    cagrilar = []

    def kosul(t, capa):
        i = int(IZ4.get_loc(t))
        c = None if capa is None else int(IZ4.get_loc(capa))
        cagrilar.append((i, c))
        return i in pumplar if c is None else i in teyitler.get(c, set())

    return kosul, cagrilar


def _idx4(sonuc):
    return [int(IZ4.get_loc(z)) for z in sonuc.olay_zamanlari]


def _capalar4(sonuc):
    return [int(IZ4.get_loc(o.capa)) for o in sonuc.olaylar]


# =================================================================================================
# 1. DIZI KAPISI
# =================================================================================================


def test_elle_kurulan_olay_dogrulanamaz():
    """On-kayit §4 rev.12 "Olayin kumede olusma olcutu": onay tek basina olay degildir; `Olay` tipi yalnizca
    `olay_dizisi`den cikar. Varsayilan imzayla elle kurulan nesne `olay_dogrula`dan gecmemeli."""
    sahte = dizi.Olay(IZ4[0], None, _h2_onay(IZ4[0]))
    with pytest.raises(ValueError, match="elle kurulmus"):
        dizi.olay_dogrula(sahte)


@pytest.mark.parametrize("nesne", ["olay", None, (1, 2), 3.0])
def test_olay_olmayan_nesne_olay_dogrulamasindan_gecemez(nesne):
    """On-kayit §4 rev.12: yalnizca `dizi.Olay` olay kumesine girer."""
    with pytest.raises(TypeError):
        dizi.olay_dogrula(nesne)


def test_kapinin_onayi_tek_basina_olay_degildir():
    """On-kayit §4 rev.12: "Tek karar noktasinin onayi, bir olayin olusmasi icin gereklidir ama YETERLI
    DEGILDIR". Imzali bir `OnaylanmisPozisyon` bile `olay_dogrula`dan gecemez."""
    with pytest.raises(TypeError):
        dizi.olay_dogrula(_h2_onay(IZ4[0]))


def test_dizinin_urettigi_olay_dogrulanir_olumlu_kontrol():
    """Olumlu kontrol: asagidaki saldirilarin bozdugu sey gercekten gecerli bir olaydir."""
    sonuc = _h2_dizi(lambda t, capa: _h2_onay(t, capa), [0])
    assert len(sonuc.olaylar) == 1
    dizi.olay_dogrula(sonuc.olaylar[0])


def test_olay_alanlari_replace_ile_degistirilemez():
    """Imza denetimi: `dataclasses.replace` ile zaman ya da capa degistirilen olay dusmeli (CLAUDE.md §3.6)."""
    olay = _h2_dizi(lambda t, capa: _h2_onay(t, capa), [0]).olaylar[0]
    with pytest.raises(ValueError):
        dizi.olay_dogrula(dataclasses.replace(olay, zaman=IZ4[5]))
    with pytest.raises(ValueError):
        dizi.olay_dogrula(dataclasses.replace(olay, capa=IZ4[0]))


@pytest.mark.parametrize("rol", ["olay", "K1", "K2"])
def test_olaya_baska_pozisyon_replace_ile_takilamaz(rol):
    """Baska bir t'nin (ya da kontrol rolundeki) imzali onayi mevcut bir olaya takilamaz: olayin imzasi
    pozisyonun imzasini, rolunu ve kimligini kapsar (on-kayit §6 rev.11: roller ayridir)."""
    olay = _h2_dizi(lambda t, capa: _h2_onay(t, capa), [0]).olaylar[0]
    baska = _h2_onay(IZ4[7], rol=rol)
    with pytest.raises(ValueError):
        dizi.olay_dogrula(dataclasses.replace(olay, pozisyon=baska))


def test_olayin_pozisyonu_bozulunca_getiri_girdisi_olamaz():
    """Savunma derinligi: `replace` ile fiyati degistirilen pozisyon, getirinin tek girdisi olan
    `pozisyon_fiyatlari`ndan gecemez (onay imzasi pozisyonun kendi alanlarini kapsar)."""
    olay = _h2_dizi(lambda t, capa: _h2_onay(t, capa), [0]).olaylar[0]
    bozuk = dataclasses.replace(olay.pozisyon, p1=olay.pozisyon.p1 * 0.5, funding_toplami=0.5)
    with pytest.raises(ValueError):
        pozisyon.pozisyon_fiyatlari(bozuk)


# SIZINTI BULGUSU S-C1 KAPANDI (madde 1c): `dizi.olay_dogrula` artik olayin tasidigi onayi da
# `pozisyon.onay_dogrula` ile dogruluyor; o imza ALANLARDAN yeniden hesaplandigi icin
# `dataclasses.replace` ile bozulmus bir pozisyon tasiyan olay reddediliyor. Isaret kaldirildi;
# testin beklentisi degismedi.
def test_olayin_icindeki_pozisyon_replace_ile_bozulunca_olay_dogrulanamaz():
    """On-kayit §4 rev.12 + `dizi.Olay` aciklamasi: "yalnizca `olay_dizisi` uretir", "degistirilmemis"."""
    olay = _h2_dizi(lambda t, capa: _h2_onay(t, capa), [0]).olaylar[0]
    bozuk = dataclasses.replace(olay.pozisyon, p1=olay.pozisyon.p1 * 0.5, funding_toplami=0.5)
    with pytest.raises((TypeError, ValueError)):
        pozisyon.onay_dogrula(bozuk)          # on kosul: pozisyonun kendi imzasi gercekten bozuldu
    with pytest.raises((TypeError, ValueError)):
        dizi.olay_dogrula(dataclasses.replace(olay, pozisyon=bozuk))


def test_ayni_dizi_cagrisinda_ayni_sembol_donem_kume_onaylari_kabul_edilir_olumlu_kontrol():
    """Olumlu kontrol (asagidaki XFAIL'in saglamligi icin): ayni (sembol, donem, kume) iki olay uretir."""
    sonuc = _h2_dizi(lambda t, capa: _h2_onay(t, capa, sembol="AAAUSDT"), [0, 20], sembol="AAAUSDT")
    assert _idx4(sonuc) == [0, 20]


# SIZINTI BULGUSU S-C2 KAPANDI (madde 1d): `dizi.olay_dizisi` artik bir cagrinin butun olaylarinin
# ayni (sembol, kume, donem_no) ucluusune ait oldugunu denetliyor. Isaret kaldirildi; testin
# beklentisi degismedi.
@pytest.mark.parametrize("alan,degerler", [("sembol", ("AAAUSDT", "BBBUSDT")), ("donem_no", (0, 1)),
                                           ("kume", ("KESIF", "C1"))])
def test_ayni_dizi_cagrisinda_farkli_sembol_donem_kume_onaylari_karisamaz(alan, degerler):
    """On-kayit §5 rev.11 ("Bekleme ... donem sinirini asmaz") + §3 (kumeler arasi veri odunc alinmaz).

    Kume karismasinda redin SINIFI madde 1e ile degisti: `_test_onayi` C1/C2 icin acik bir onay
    kosusu istedigi icin karisim daha ONCE, `split.OnayGerekli` ile reddediliyor. Hukum ayni: dizi
    iki kumeyi karistiramaz."""
    def karar(t, capa):
        deger = degerler[0] if t == IZ4[0] else degerler[1]
        return _h2_onay(t, capa, **{alan: deger})

    with pytest.raises((ValueError, PermissionError)):
        _h2_dizi(karar, [0, 20])


@pytest.mark.parametrize("hata", [pencere.VeriHatasi("bozuk"), pencere.ZamanDizisiHatasi("sirasiz"),
                                  KeyError("x"), RuntimeError("y"), ValueError("z")])
def test_kapinin_olay_olusmaz_disindaki_hatalari_ret_sayilmaz(hata):
    """`pencere.OlayOlusmaz` dizi icin ret gerekcesidir; veri bozuklugu ve programlama hatalari ret DEGILDIR,
    kosuyu durdurmalidir (pencere.VeriHatasi aciklamasi, denetci D-C2)."""
    def karar(t, capa):
        raise hata

    with pytest.raises(type(hata)):
        _h2_dizi(karar, [0, 1])


@pytest.mark.parametrize("yanit", [1, 0, 1.0, "True", np.float64(1.0), [True]])
def test_bool_olmayan_kosul_yaniti_reddedilir(yanit):
    """`kosul` yaniti True / False / hesaplanamaz'dan baska bir sey olamaz; 1 ya da "True" sessizce olay
    olusturamaz (on-kayit §2 "Tamlik sarti": uc durum)."""
    with pytest.raises(TypeError):
        _h2_dizi(lambda t, capa: _h2_onay(t, capa), [0], kosul=lambda t, capa: yanit)


def test_hesaplanamaz_yanitlari_olay_uretmez_ret_olur():
    """None, `KosulHesaplanamaz` sinifi ve ornegi ayni anlamdadir: olay yok, ret gerekcesi
    `sinyal_penceresi_tam_degil` (on-kayit §2 "Tamlik sarti"). np.bool_ ise gecerli bool'dur."""
    for yanit in (None, dizi.KosulHesaplanamaz, dizi.KosulHesaplanamaz()):
        sonuc = _h2_dizi(lambda t, capa: _h2_onay(t, capa), [0, 1], kosul=lambda t, capa, y=yanit: y)
        assert sonuc.olaylar == ()
        assert [r.gerekce for r in sonuc.retler] == ["sinyal_penceresi_tam_degil"] * 2
    sonuc = _h2_dizi(lambda t, capa: _h2_onay(t, capa), [0], kosul=lambda t, capa: np.True_)
    assert _idx4(sonuc) == [0]


# =================================================================================================
# 2. KONTROL BARINDAKI PENCERE SARTI
# =================================================================================================

DB, B = T("2024-09-01"), T("2025-06-30 20:00")
HACIM = 1e7
P1 = T("2025-03-10 04:00")          # H1 pump bari
T1 = P1 + 3 * H4                    # H1 teyit bari
T2 = T("2025-03-10 04:00")          # H2 kirilim bari
T3 = T("2025-03-10")                # H3 olay gunu


def _duz(bas, son, fiyat=1.0, hacim=HACIM) -> pd.DataFrame:
    z = pd.date_range(bas, son, freq="4h")
    return pd.DataFrame({"open_time": z, "open": fiyat, "high": fiyat, "low": fiyat, "close": fiyat,
                         "quote_volume": float(hacim)})


def _fund(bas, son, oran=0.0005) -> pd.DataFrame:
    z = pd.date_range(bas, son, freq="8h")
    return pd.DataFrame({"odeme_zamani": z, "aralik_saat": 8.0, "oran": 0.0, "oran_8h": float(oran)})


def _ayarla(mumlar, zaman, **alanlar):
    m = mumlar.copy()
    maske = np.asarray(pd.DatetimeIndex(m["open_time"]) == pd.Timestamp(zaman))
    assert bool(maske.any()), f"{zaman} seride yok"
    for alan, deger in alanlar.items():
        m.loc[maske, alan] = deger
    return m


def _aralik_ayarla(mumlar, bas, son, **alanlar):
    m = mumlar.copy()
    z = pd.DatetimeIndex(m["open_time"])
    maske = np.asarray((z >= pd.Timestamp(bas)) & (z <= pd.Timestamp(son)))
    assert bool(maske.any())
    for alan, deger in alanlar.items():
        m.loc[maske, alan] = deger
    return m


def _h1_serisi() -> pd.DataFrame:
    m = _aralik_ayarla(_duz(DB, B), P1 - 5 * H4, P1, quote_volume=3 * HACIM)
    return _ayarla(m, P1, close=1.25, high=1.30, low=1.0, open=1.0)


def _h2_dunyasi(t, bitis) -> pd.DataFrame:
    m = _aralik_ayarla(_duz(DB, bitis), t - 3 * H4, t - H4, low=1.5, high=1.5, close=1.0, open=1.0)
    return _ayarla(m, t, close=1.2, high=1.2, low=1.2, open=1.2)


def _h3_serisi() -> pd.DataFrame:
    m = _duz(DB, B)
    m = _aralik_ayarla(m, T3 - pd.Timedelta(days=29), T3 + pd.Timedelta(hours=20), quote_volume=HACIM / 6)
    return _aralik_ayarla(m, T3 - pd.Timedelta(days=4), T3 + pd.Timedelta(hours=20),
                          open=0.5, high=0.5, low=0.5, close=0.5)


FUND = _fund(DB, B + H4)


def _karar(hipotez, mumlar, fund, t, **ek):
    tanim = pencere.hipotez_ufuklari(hipotez)
    return pozisyon.olay_karari(t, tanim.birincil, tanim.bar, hipotez=hipotez,
                                birincil_ufuk=tanim.birincil, kume=kume_adi(t),
                                **veri(mumlar, fund, DB, B, uygun_bas=DB, hacim=6 * HACIM),
                                **ek, **esikler(tanim.bar))


@pytest.mark.parametrize("rol", ("K1", "K2"))
@pytest.mark.parametrize("hipotez,t", [("H1", T1), ("H2", T2), ("H3", T3)])
def test_kontrol_barinda_kosul_ve_deger_kuruculari_cagrilmaz(monkeypatch, hipotez, t, rol):
    """On-kayit §6 rev.12: "Kontrol barinda sinyal kosullari hicbir amacla hesaplanmaz. ... Kontrol barinda
    hesaplanan tek sey, capasiz pencerelerin hesaplanabilirligidir." Kosul, olay degeri ve gecersizlik
    kuruculari patlayici ile degistirilir; kontrol yine de olusmali, capasiz pencere kurucusu tam bir kez
    cagrilmali ve gecersizlik seviyesi tanimsiz (NaN) kalmali."""
    def yasak(ad):
        def f(*a, **k):
            raise AssertionError(f"sinyal.{ad} kontrol barinda cagrilamaz (on-kayit §6 rev.12)")
        return f

    for ad in ("sinyal_degerleri", "kosullar_saglandi", "h1_pump_saglandi", "h1_pump_degerleri",
               "gecersizlik_seviyesi"):
        monkeypatch.setattr(sinyal, ad, yasak(ad))
    gercek = sinyal.capasiz_pencere_degerleri
    cagrilar = []

    def izle(*a, **k):
        cagrilar.append(a[0])
        return gercek(*a, **k)

    monkeypatch.setattr(sinyal, "capasiz_pencere_degerleri", izle)
    p = _karar(hipotez, _duz(DB, B), FUND, t, **kontrol(hipotez, rol))
    assert p.rol == rol and cagrilar == [hipotez]
    assert math.isnan(p.gecersizlik_seviyesi)


@pytest.mark.parametrize("rol", ("K1", "K2"))
def test_kontrol_roluna_capa_verilemez(rol):
    """On-kayit §6 rev.11: "H1'in kontrol barinda pump bari, dip penceresi ve tepe aranmaz"; capa yalnizca
    H1'in olay rolunde verilir. Kontrol barini capali pencere hesaplatmaya zorlama girisimi."""
    with pytest.raises(TypeError):
        _karar("H1", _duz(DB, B), FUND, T1, yapilandirma=yapilandirma("H1"), rol=rol, capa=T1 - 3 * H4)


class _SahteRol(str):
    """`==` ile her seye esit gorunen str alt sinifi (rol dogrulamasini kandirma girisimi)."""

    def __eq__(self, diger):
        return True

    __hash__ = str.__hash__


def test_str_alt_sinifi_rol_reddedilir():
    """`pozisyon._rol_dogrula` tam `str` ister; `__eq__` ile yalan soyleyen rol kapiya giremez
    (kontrol/olay ayrimi rol alaninin guvenilirligine dayanir; on-kayit §6 rev.11)."""
    with pytest.raises(TypeError):
        _karar("H2", _duz(DB, B), FUND, T2, yapilandirma=yapilandirma("H2"), rol=_SahteRol("olay"), capa=None)


@pytest.mark.parametrize("hipotez", config.HIPOTEZLER)
@pytest.mark.parametrize("bozuk", [float("nan"), float("inf"), -float("inf"), None, True, "1.0", np.nan])
def test_capasiz_pencere_sonlu_olmayan_deger_hesaplanamaz_sayilir(hipotez, bozuk):
    """On-kayit §2 "Tamlik sarti" + §6 rev.12: sonlu bir sayi olmayan her deger (NaN, +-inf, None, bool, metin)
    hesaplanamamis demektir; kontrol barini sessizce gecirmemeli."""
    adlar = sinyal.capasiz_pencere_adlari(hipotez)
    for i in range(len(adlar)):
        degerler = {a: 1.0 for a in adlar}
        degerler[adlar[i]] = bozuk
        assert sinyal.capasiz_hesaplanamayan(hipotez, degerler) == [adlar[i]]


@pytest.mark.parametrize("hipotez", config.HIPOTEZLER)
@pytest.mark.parametrize("bozuk", [float("nan"), float("inf"), None, False, "x"])
def test_olay_degeri_sonlu_olmayan_deger_hesaplanamaz_sayilir(hipotez, bozuk):
    """Olay tarafinda ayni kural (on-kayit §2 "Tamlik sarti")."""
    adlar = sinyal.deger_adlari(hipotez)
    degerler = {a: 1.0 for a in adlar}
    degerler[adlar[-1]] = bozuk
    assert sinyal.hesaplanamayan(hipotez, degerler) == [adlar[-1]]


# =================================================================================================
# 3. IZLEME PENCERESININ SINIRLARI
# =================================================================================================


def test_reddedilen_teyit_izlemeyi_bitirir_ikinci_teyit_olay_sayilmaz():
    """On-kayit §5 H1 madde 3-4: olay "ilk kez" teyit koşulunu saglayan bardir ve izleme teyit bariyla
    biter. Kapi ilk teyit barini reddederse ikinci teyit barinin kapiya gonderilip olay yapilmasi
    "bir teyit bari en cok bir olay sayar" kuralini ve ilk-kez sartini deler."""
    kosul, _ = _h1_kosul({0}, {0: {3, 4}})
    sorulan = []

    def karar(t, capa):
        sorulan.append(int(IZ4.get_loc(t)))
        raise pozisyon.UygunDegil("sahte")

    sonuc = _h1_dizi(range(20), kosul, karar)
    assert sonuc.olaylar == () and sorulan == [3]
    assert [r.gerekce for r in sonuc.retler] == ["uygun_degil"]


def test_izleme_surerken_gelen_ikinci_pump_sayaci_uzatmaz_ve_teyidi_capalamaz():
    """On-kayit §5 H1 madde 4: izleme surerken gelen yeni pump YOK SAYILIR; sayac ve tepe ilk pump
    barindan olculur. Olay capasi ilk pump olmali, ikinci pump'in teyidi sorulmamali."""
    kosul, cagrilar = _h1_kosul({0, 5}, {0: {9}, 5: {9}})
    sonuc = _h1_dizi(range(20), kosul)
    assert _idx4(sonuc) == [9] and _capalar4(sonuc) == [0]
    assert (5, None) not in cagrilar, "izleme surerken ikinci pump kosula sorulmamali"
    assert (9, 5) not in cagrilar, "ikinci pump capali teyit sorulmamali"


@pytest.mark.parametrize("teyit,olay_var", [(12, True), (13, False)])
def test_eksik_barli_seride_12_bar_teyidi_dahil_13_bar_haric(teyit, olay_var):
    """On-kayit §5 H1 madde 3-4 (rev.13): teyit araligi takvimle `(pump, pump + 12 x adim]`. Arada 11 bar
    eksik olsa da (zamanlar [0, teyit]) 12. bar araligin icinde, 13. bar disindadir ve 13. bar icin
    capali teyit hic sorulmaz."""
    kosul, cagrilar = _h1_kosul({0}, {0: {teyit}})
    sonuc = _h1_dizi([0, teyit], kosul)
    assert (_idx4(sonuc) == [teyit]) is olay_var
    if not olay_var:
        assert (13, 0) not in cagrilar


# --- Gercek `sinyal_kosulu` ile geleceğe bakis ve kume siniri ----------------------------------------


def _gercek_kosul(hipotez, mumlar, fund, t, capa=None, bitis=B):
    v = veri(mumlar, fund, DB, bitis, uygun_bas=DB, hacim=6 * HACIM)
    return pozisyon.sinyal_kosulu(t, hipotez=hipotez, yapilandirma=yapilandirma(hipotez), capa=capa,
                                  kume="KESIF", **v)


def _gelecegi_zehirle(mumlar, kesim):
    m = mumlar.copy()
    sonra = np.asarray(pd.DatetimeIndex(m["open_time"]) > pd.Timestamp(kesim))
    assert bool(sonra.any())
    for alan in ("open", "high", "low", "close"):
        m.loc[sonra, alan] = 1e9
    m.loc[sonra, "quote_volume"] = 0.0
    return m


def _funding_zehirle(fund, kesim):
    f = fund.copy()
    sonra = np.asarray(pd.DatetimeIndex(f["odeme_zamani"]) > pd.Timestamp(kesim))
    f.loc[sonra, "oran_8h"] = 5.0
    f.loc[sonra, "oran"] = 5.0
    return f


@pytest.mark.parametrize("hipotez,seri,t,capa,mum_kesim,bozma", [
    ("H1", _h1_serisi, T1, P1, T1, dict(zaman=T1, high=2.0)),
    ("H2", lambda: _h2_dunyasi(T2, B), T2, None, T2, dict(zaman=T2, close=10.0)),
    ("H3", _h3_serisi, T3, None, T3 + pd.Timedelta(hours=20), dict(zaman=T3 + pd.Timedelta(hours=20), close=5.0)),
])
def test_gercek_kosul_t_den_sonraki_barlara_ve_fundinge_bakmaz(hipotez, seri, t, capa, mum_kesim, bozma):
    """CLAUDE.md §3.6 + on-kayit §5: sinyal t barinin kapanisinda hesaplanir. t'den SONRAKI butun barlar
    ve funding kayitlari absurt degerlere cevrilince gercek `sinyal_kosulu`nun karari DEGISMEMELI.
    Karsi-kontrol: t'nin kendi barini bozmak karari degistirir (test duyarli)."""
    m, f = seri(), FUND
    assert _gercek_kosul(hipotez, m, f, t, capa) is True, "olumlu kontrol: dunya kosulu sagliyor"
    zehirli_m = _gelecegi_zehirle(m, mum_kesim)
    zehirli_f = _funding_zehirle(f, t + H4)
    assert _gercek_kosul(hipotez, zehirli_m, zehirli_f, t, capa) is True
    bozma = dict(bozma)
    bozuk = _ayarla(m, bozma.pop("zaman"), **bozma)
    assert _gercek_kosul(hipotez, bozuk, f, t, capa) is False


def test_kesif_kosulu_kume_sonundan_sonraki_barlari_hic_gormez():
    """CLAUDE.md §3.3 + on-kayit §3 ("kumeler arasi veri odunc alinmaz"): `KESIF` kosulu icin 2025-09-01
    sonrasi (C2) barlar onbellekte dursa bile `sinyal_kosulu` onlari kullanmaz. Kosulu SAGLAYAN bir
    kirilim bari C2'ye dusuyorsa KESIF cagrisinda kosul hesaplanamaz (None) olmali."""
    bitis = T("2025-12-31 20:00")
    fon = _fund(DB, bitis + H4)
    t_ic, t_dis = T("2025-08-30 04:00"), T("2025-09-01 04:00")
    assert _gercek_kosul("H2", _h2_dunyasi(t_ic, bitis), fon, t_ic, bitis=bitis) is True
    assert _gercek_kosul("H2", _h2_dunyasi(t_dis, bitis), fon, t_dis, bitis=bitis) is None


# =================================================================================================
# 4. H3 DIZISININ TAKVIM TABANI + butun diziler icin gelecege bakis / model testleri
# =================================================================================================


def test_h3_hesaplanamayan_gunle_baslayan_dizinin_ilk_gunu_ikinci_gundur():
    """On-kayit §5 H3 madde 3: dizi "§2 'Tamlik sarti' geregi hesaplanamadigi gunde kesilir". Gun 0
    hesaplanamaz (diziye ait degil), gun 1'den itibaren kosullar saglaniyor: dizinin ILK gunu 1'dir ve
    olay gun 1'de olusur."""
    def kosul(t, capa):
        return None if t == IZ1[0] else True

    sonuc = _h3_dizi(range(6), kosul)
    assert [int(IZ1.get_loc(z)) for z in sonuc.olay_zamanlari] == [1]


def _durumlar(rng, n, p_dogru, p_yok):
    kod = rng.random(n)
    return [True if k < p_dogru else (None if k < p_dogru + p_yok else False) for k in kod]


def _dunya(hipotez, tohum):
    """Sabit tohumlu rastgele dizi dunyasi: tri-durumlu kosullar, kapinin rastgele reddi ve bosluklu zamanlar."""
    rng = np.random.default_rng(tohum)
    bar = config.HIPOTEZ_IZGARASI[hipotez]
    iz = IZ4 if bar == config.BAR_4H else IZ1
    n = len(iz)
    tek = _durumlar(rng, n, 0.25, 0.10)
    teyit = [_durumlar(rng, n, 0.20, 0.05) for _ in range(n)]
    ret = [bool(x) for x in (rng.random(n) < 0.15)]
    secim = np.sort(rng.choice(n, size=int(n * 0.8), replace=False))
    y = {"H1": Y1, "H2": Y2, "H3": Y3}[hipotez]

    def kosul(t, capa):
        i = int(iz.get_loc(t))
        if capa is None:
            return tek[i]
        return teyit[int(iz.get_loc(capa))][i]

    def karar(t, capa):
        if ret[int(iz.get_loc(t))]:
            raise pozisyon.UygunDegil("sahte")
        return pozisyon._test_onayi(hipotez=hipotez, yapilandirma=y, t=t, capa=capa)

    return dict(hipotez=hipotez, bar=bar, iz=iz, y=y, tek=tek, teyit=teyit, ret=ret, secim=secim,
                kosul=kosul, karar=karar)


def _kos(d, idx):
    return dizi.olay_dizisi(d["hipotez"], d["y"], d["iz"][np.asarray(idx, dtype=int)], d["bar"],
                            birincil_ufuk=config.BIRINCIL_UFUK[d["bar"]], kosul=d["kosul"], karar=d["karar"], **DIZI_KIMLIGI)


def _olay_ciftleri(d, sonuc):
    iz = d["iz"]
    return [(int(iz.get_loc(o.zaman)), None if o.capa is None else int(iz.get_loc(o.capa)))
            for o in sonuc.olaylar]


@pytest.mark.parametrize("tohum", [1, 2, 3, 4])
@pytest.mark.parametrize("hipotez", config.HIPOTEZLER)
def test_dizi_gelecege_bakmaz_onek_ile_tam_kosu_ayni_olaylari_verir(hipotez, tohum):
    """CLAUDE.md §3.6 + on-kayit §5: t'deki karar yalnizca t'ye kadarki girdiye baglidir. Serinin SONUNA bar
    eklemek (tam kosu) onek kosusunun olaylarini ve retlerini degistirmemeli. Bosluklu, rastgele
    tri-durumlu kosullarla ve rastgele kapi retleriyle sinanir (sabit tohum)."""
    d = _dunya(hipotez, 20260911 + tohum)
    secim = d["secim"]
    tam = _kos(d, secim)
    iz = d["iz"]
    for kesim in (15, 30, 45, 60, 75):
        onek = _kos(d, secim[secim <= kesim])
        sinir = iz[kesim]
        assert _olay_ciftleri(d, onek) == [c for c, o in zip(_olay_ciftleri(d, tam), tam.olaylar)
                                           if o.zaman <= sinir]
        assert [(r.zaman, r.capa, r.gerekce) for r in onek.retler] == [
            (r.zaman, r.capa, r.gerekce) for r in tam.retler if r.zaman <= sinir]


def _model(d):
    """Tamsayi indeksli referans model (on-kayit §5 metninden): takvim = indeks, kapi onaylari `ret`ten."""
    hipotez, tek, teyit, ret = d["hipotez"], d["tek"], d["teyit"], d["ret"]
    h = config.BIRINCIL_UFUK[d["bar"]]
    olaylar, son, izleme, suruyor, onceki = [], None, None, False, None

    def bekleme(i):
        return son is not None and 0 < i - son <= h

    for i in map(int, d["secim"]):
        if hipotez == "H1":
            if izleme is not None:
                if i - izleme <= config.H1_IZLEME_BAR:
                    if teyit[izleme][i] is True:
                        if not ret[i]:
                            olaylar.append((i, izleme))
                            son = i
                        izleme = None
                        continue
                    if i - izleme == config.H1_IZLEME_BAR:
                        izleme = None
                    continue
                izleme = None
            if bekleme(i):
                continue
            if tek[i] is True:
                izleme = i
            continue
        if hipotez == "H3":
            if onceki is not None and i != onceki + 1:
                suruyor = False
            onceki = i
            if tek[i] is not True:
                suruyor = False
                continue
            ilk = not suruyor
            suruyor = True
            if not ilk or bekleme(i):
                continue
        else:
            if tek[i] is not True or bekleme(i):
                continue
        if not ret[i]:
            olaylar.append((i, None))
            son = i
    return olaylar


@pytest.mark.parametrize("tohum", [11, 12, 13, 14, 15])
@pytest.mark.parametrize("hipotez", config.HIPOTEZLER)
def test_dizi_tamsayi_modeliyle_ayni_olaylari_verir(hipotez, tohum):
    """On-kayit §5 (bekleme yari acik, H1 tek izleme ve 12 bar takvimi, H3 kesintisiz dizi + takvim
    kesintisi): zaman damgali uygulama, tamsayi indeksli ayri bir modelle rastgele bosluklu serilerde
    ayni olaylari uretmeli (zaman toleransi / takvim farklarini yakalamak icin)."""
    d = _dunya(hipotez, 20261011 + tohum)
    assert _olay_ciftleri(d, _kos(d, d["secim"])) == _model(d)


# =================================================================================================
# 5. OLAY BASINA AGIRLIKLANDIRMA VE ALT TOHUM
# =================================================================================================


def test_havuzlar_birlestirilmez_olay_basina_agirliklandirma():
    """On-kayit §7 rev.13: "havuzlar tek bir kumede BIRLESTIRILMEZ". 1 kontrollu ve 9 kontrollu iki olay:
    olay basina ortalamalar 1.0 ve 3.0 -> kontrol ortalamasi 2.0 (birlestirilirse 2.8 olurdu)."""
    assert istatistik.test_istatistigi([2.5, 2.5], [[1.0], [3.0] * 9]) == pytest.approx(0.5)
    # Ters yonde: birlestirme 1.2 verirdi (istatistik +0.7), olay basina 2.0 verir (-0.1).
    assert istatistik.test_istatistigi([1.9, 1.9], [[3.0], [1.0] * 9]) == pytest.approx(-0.1)


def test_yeniden_ornekle_ayni_olcekte_yanit_verir():
    """On-kayit §7 rev.13 gerekcesi: gozlenen istatistik ile yeniden ornekleme dagilimi ayni olcekte olmali.
    Havuzlar sabit degerli oldugu icin her tekrar ayni istatistigi verir: `r`, gozlenen istatistigin
    isaretine (<= 0) esit olmali. Havuz boyutuyla kandirma: birlestirilmis ortalama isareti ters cevirirdi."""
    a = istatistik.yeniden_ornekle([2.5, 2.5], [[1.0], [3.0] * 9], hipotez="H2", yapilandirma=Y2,
                                   kume="KESIF", kontrol_kumesi="K2")
    assert a.r == 0 and a.p == pytest.approx(1 / 10001) and a.tekrar == 10000 and a.olay_sayisi == 2
    b = istatistik.yeniden_ornekle([1.9, 1.9], [[3.0], [1.0] * 9], hipotez="H2", yapilandirma=Y2,
                                   kume="KESIF", kontrol_kumesi="K2")
    assert b.r == 10000 and b.p == pytest.approx(1.0)


def test_istatistik_sinir_esitligi_r_e_dahildir():
    """On-kayit §7 rev.11: `r`, istatistigin sifiri ASMADIGI (`<= 0`) tekrarlarin sayisidir: tam sifir
    istatistik r'ye girer. Olay 2.0, kontrol ortalamasi (1.0 + 3.0) / 2 = 2.0 -> istatistik 0."""
    assert istatistik.test_istatistigi([2.0, 2.0], [[1.0], [3.0] * 9]) == 0.0
    s = istatistik.yeniden_ornekle([2.0, 2.0], [[1.0], [3.0] * 9], hipotez="H2", yapilandirma=Y2,
                                   kume="KESIF", kontrol_kumesi="K1")
    assert s.r == 10000 and s.p == pytest.approx(1.0)


def test_istatistik_girdi_denetimleri():
    """On-kayit §6 rev.11 / §7 rev.13: havuz sayisi olay sayisina esit, havuz bos degil, degerler sonlu.
    Rev.13 oncesi duz kontrol listesi API'si sessizce kabul edilmemeli."""
    with pytest.raises(ValueError):
        istatistik.test_istatistigi([1.0, 2.0], [[0.5]])                 # havuz sayisi != olay sayisi
    with pytest.raises(ValueError):
        istatistik.test_istatistigi([1.0, 2.0], [[0.5], []])             # bos havuz
    with pytest.raises(ValueError):
        istatistik.test_istatistigi([], [])                              # bos olay kumesi
    for bozuk in (float("nan"), float("inf"), -float("inf")):
        with pytest.raises(ValueError):
            istatistik.test_istatistigi([bozuk, 1.0], [[0.5], [0.5]])
        with pytest.raises(ValueError):
            istatistik.test_istatistigi([1.0, 1.0], [[0.5], [bozuk]])
    with pytest.raises((TypeError, ValueError)):
        istatistik.test_istatistigi([1.0, 2.0], [0.5, 0.5])             # eski duz-liste API'si
    with pytest.raises(ValueError):
        istatistik.test_istatistigi([[1.0, 2.0], [3.0, 4.0]], [[0.5], [0.5]])   # iki boyutlu olay getirisi


def test_yeniden_ornekle_tohumu_cagirandan_almaz():
    """On-kayit §7 rev.13: tohum (hipotez, yapilandirma, kume, kontrol kumesi) demetinden turetilir; cagiran
    tohum VEREMEZ ve dort alandan hicbiri atlanamaz."""
    parametreler = set(inspect.signature(istatistik.yeniden_ornekle).parameters)
    assert not ({"tohum", "seed", "rng", "uretec", "alt_tohum", "random_state"} & parametreler)
    temel = dict(hipotez="H2", yapilandirma=Y2, kume="KESIF", kontrol_kumesi="K2")
    with pytest.raises(TypeError):
        istatistik.yeniden_ornekle([1.0], [[0.0]], tohum=1, **temel)
    for eksik in temel:
        kw = dict(temel)
        del kw[eksik]
        with pytest.raises(TypeError):
            istatistik.yeniden_ornekle([1.0], [[0.0]], **kw)


def test_alt_tohum_demetin_her_ekseninde_degisir():
    """On-kayit §7 rev.13: "tek bir global tohum, 9 yapilandirma ve iki kontrol kumesi icin ayni rastgele
    diziyi kullanir ve p-degerlerini birbirine baglar". 3 hipotez x 9 yapilandirma x 3 kume x 2 kontrol
    kumesi = 162 demetin hepsi FARKLI alt tohum vermeli ve hicbiri genel tohum olmamali."""
    gorulen = {}
    for h in config.HIPOTEZLER:
        izgara = sinyal.izgara(h)
        assert len(izgara) == 9
        for y in izgara:
            for k in config.KUMELER:
                for kk in istatistik.KONTROL_KUMELERI:
                    tohum, demet = istatistik.alt_tohum(h, y, k, kk)
                    assert demet == (h, sinyal.yapilandirma_kimligi(h, y), k, kk)
                    gorulen[demet] = tohum
    assert len(gorulen) == 3 * 9 * 3 * 2
    assert len(set(gorulen.values())) == len(gorulen), "iki demet ayni alt tohumu kullaniyor"
    assert config.TOHUM not in gorulen.values()


def test_yeniden_ornekle_tekrar_ve_demet_denetimleri():
    """On-kayit §7: tekrar sayisi 10.000'dir (baska deger verilemez); kontrol kumesi K1/K2, kume KESIF/C1/C2,
    yapilandirma izgarada olmali."""
    temel = dict(hipotez="H2", yapilandirma=Y2, kume="KESIF", kontrol_kumesi="K2")
    for tekrar in (1, 100, 9999, 10001, True):
        with pytest.raises(ValueError):
            istatistik.yeniden_ornekle([1.0], [[0.0]], tekrar=tekrar, **temel)
    for ad, bozuk in (("kontrol_kumesi", "K3"), ("kontrol_kumesi", "k1"), ("kontrol_kumesi", None),
                      ("kontrol_kumesi", ""), ("kume", "C3"), ("kume", None), ("hipotez", "H4")):
        kw = dict(temel)
        kw[ad] = bozuk
        with pytest.raises(ValueError):
            istatistik.yeniden_ornekle([1.0], [[0.0]], **kw)
    kw = dict(temel)
    kw["yapilandirma"] = {"phi": 0.0004, "k": 3}
    with pytest.raises(ValueError):                     # izgarada olmayan demet (YapilandirmaHatasi)
        istatistik.yeniden_ornekle([1.0], [[0.0]], **kw)


def test_yeniden_ornekle_deterministiktir():
    """CLAUDE.md §5 (sabit tohum): ayni girdi ayni `r`'yi, ayni alt tohumu ve genel tohum kaydini verir."""
    rng = np.random.default_rng(20260911)
    olay = rng.normal(0.0, 1.0, size=12)
    havuzlar = [rng.normal(0.0, 1.0, size=int(rng.integers(1, 15))) for _ in range(12)]
    temel = dict(hipotez="H3", yapilandirma=Y3, kume="KESIF", kontrol_kumesi="K1")
    a = istatistik.yeniden_ornekle(olay, havuzlar, **temel)
    b = istatistik.yeniden_ornekle(olay, havuzlar, **temel)
    assert (a.r, a.p, a.tohum, a.alt_tohum_demeti) == (b.r, b.p, b.tohum, b.alt_tohum_demeti)
    assert a.genel_tohum == config.TOHUM
    assert (a.tohum, a.alt_tohum_demeti) == istatistik.alt_tohum("H3", Y3, "KESIF", "K1")


# =================================================================================================
# 6. KILIT.md OKUMASI
# =================================================================================================


def _kayit_dosyasi(tmp_path):
    yol = tmp_path / "onay_gecici.md"
    yol.write_text("bas\n", encoding="utf-8")
    return yol


def test_baska_hipotezin_kaydi_varken_kaydi_olmayan_hipotez_icin_kosu_acilmaz(tmp_path):
    """On-kayit §8 madde 5: "dosyada kaydi olmayan ... bir hipotez icin onay kosusu acilmaz". H1 ve H2'nin
    kaydi varken H3 kosusu acilamaz ve kayda hicbir sey yazilmaz."""
    yol = _kayit_dosyasi(tmp_path)
    gecici_kayit(yol, kilitler=("H1", "H2"))
    once = yol.read_bytes()
    with pytest.raises(split.KilitYok):
        with kosu("H3", "C1"):
            pytest.fail("kaydi olmayan hipotez icin kosu acilmamali")
    assert yol.read_bytes() == once and split.aktif_onay_kosusu() is None
    with pytest.raises(split.OnayGerekli):                 # onay verisine de erisim acilmadi
        split.kume_erisimi("BTCUSDT", "C1", onay=True)


@pytest.mark.parametrize("alan", split.KILIT_ALANLARI)
def test_ikinci_kayit_eklenen_kilit_bozuktur(alan):
    """On-kayit §8 madde 5 ekleme kurali: ayni hipotezin kaydi ikinci kez (farkli degerle, harf buyuklugu
    degistirilerek) eklenirse hangi alan olursa olsun KilitBozuk."""
    metin = kilit_metni("H2") + f"| {alan.upper()} | baska |\n"
    with pytest.raises(split.KilitBozuk, match="birden fazla"):
        split.kilit_kaydi_coz(metin, "H2")
    ikinci = kilit_metni("H2") + kilit_metni("H2", yapilandirma="H2:phi=0.0005,k=6")
    with pytest.raises(split.KilitBozuk, match="birden fazla"):
        split.kilit_kaydi_coz(ikinci, "H2")


# --- Gecerlilik: secildi hukmunun on-kayit §8 madde 2-4 sartlari (XFAIL) -----------------------------


# SIZINTI BULGUSU S-C3 KAPANDI (madde 2a): `kilit_kaydi_coz` secildi hukmunde K2 farkinin pozitif
# olmasini ariyor ve denetim kosu acilmadan ONCE calisiyor. Isaret kaldirildi; beklenti degismedi.
@pytest.mark.parametrize("k2", ["-0.0100", "0.0000", "nan"])
def test_secildi_hukmunde_k2_farki_pozitif_olmak_zorunda(k2):
    """On-kayit §8 madde 4."""
    with pytest.raises(split.KilitBozuk):
        split.kilit_kaydi_coz(kilit_metni("H2", k2_farki=k2), "H2")


# SIZINTI BULGUSU S-C3 (uc uca) KAPANDI (madde 2a): kosu acilmiyor ve kayit baytlari degismiyor.
def test_k2_farki_pozitif_olmayan_kilitle_onay_kosusu_acilmaz(tmp_path):
    """On-kayit §8 madde 4-5: secimin kosullari saglanmiyorsa onay verisi harcanmaz."""
    yol = _kayit_dosyasi(tmp_path)
    kok = kilitleri_kur(tmp_path / "kok", ("H1", "H3"))
    kilit_yaz(kok, "H2", k2_farki="-0.0100")
    gecici_kayit(yol, kilit_koku=kok)
    once = yol.read_bytes()
    with pytest.raises(split.OnayOrtamiHatasi):
        with kosu("H2", "C1"):
            pass
    assert yol.read_bytes() == once


# SIZINTI BULGUSU S-C4 KAPANDI (madde 2b): secildi hukmunde analize giren olay sayisi
# `config.ADAY_OLAY_ESIGI` ile karsilastiriliyor. Isaret kaldirildi; beklenti degismedi.
@pytest.mark.parametrize("analize", [149, 0])
def test_secildi_hukmunde_analize_giren_olay_aday_esiginin_altinda_olamaz(analize):
    """On-kayit §8 madde 2 (rev.13: eşik analize giren olay sayisina bakar)."""
    assert analize < config.ADAY_OLAY_ESIGI
    with pytest.raises(split.KilitBozuk):
        split.kilit_kaydi_coz(kilit_metni("H2", olusmus=200, analize_giren=analize), "H2")


# SIZINTI BULGUSU S-C5 ve DENETCI BULGUSU D-C4 KAPANDI (madde 2c): kayittaki yapilandirma kimligi
# hipotezin izgarasinda araniyor ve denetim kosu acilmadan ONCE calisiyor. Isaret kaldirildi;
# beklenti degismedi.
@pytest.mark.parametrize("kimlik", ["H2:phi=0.0003,k=4", "H1:theta=0.2,delta=0.08", "H2", "baska"])
def test_secildi_hukmunde_yapilandirma_izgarada_olmali(kimlik):
    """On-kayit §5 rev.11 (izgarada olmayan demet hata verir) + §8 madde 5 (yapilandirmanin kimligi)."""
    with pytest.raises(split.KilitBozuk):
        split.kilit_kaydi_coz(kilit_metni("H2", yapilandirma=kimlik), "H2")


# SIZINTI BULGUSU S-C6'nin ISARET parcasi KAPANDI (madde 2b): negatif olay sayisi aday esigi
# karsilastirmasina takiliyor. Ayristirmanin kendisi (ondalik ayiricinin sessizce silinmesi,
# "1.5" -> 15) madde 2d'de duzeltildi. Isaret kaldirildi; beklenti degismedi.
def test_olay_sayilari_negatif_olamaz():
    """On-kayit §8 madde 5: olay sayilari sayimdir."""
    with pytest.raises(split.KilitBozuk):
        split.kilit_kaydi_coz(kilit_metni("H2", olusmus=-5, analize_giren=-6), "H2")


# SIZINTI BULGUSU S-C7 KAPANDI (madde 2e): `kesif_commit` 40 haneli onaltilik, `kesif_zamani`
# ISO 8601 ve UTC olmak zorunda. Isaret kaldirildi; beklenti degismedi.
@pytest.mark.parametrize("alanlar", [dict(commit="yok"), dict(commit="0" * 39), dict(zaman="dun")])
def test_kesif_commit_ve_zamani_bicim_denetimi(alanlar):
    """On-kayit §8 madde 5: commit hash'i 40 hane, zaman UTC."""
    with pytest.raises(split.KilitBozuk):
        split.kilit_kaydi_coz(kilit_metni("H2", **alanlar), "H2")


# SIZINTI BULGUSU S-C8 KAPANDI (madde 2f): kapandi hukmunde `k2_farki` None (NaN degil), bu yuzden
# ayni metnin iki cozumu esit ve kapanmis hipotez gercek git kipinde de `HipotezKapandi` veriyor.
# Isaret kaldirildi; beklenti degismedi.
def test_ayni_kapandi_metninin_iki_cozumu_esit_olmali():
    """Saflik/tekrarlanabilirlik (CLAUDE.md §5): `kilit_kaydi_coz` saf bir fonksiyondur, ayni girdi esit cikti."""
    m = kilit_metni("H2", hukum=split.KILIT_KAPANDI, gerekce="aday yok", yapilandirma="-", parametreler="-",
                    k2_farki="-")
    assert split.kilit_kaydi_coz(m, "H2") == split.kilit_kaydi_coz(m, "H2")


# --- Gercek git kipi ----------------------------------------------------------------------------------


def _git_durumu(depo):
    """Kayit baytlari, HEAD, uzak `main` ve calisma agaci durumu: 'hicbir sey yazilmadi' olcutu."""
    return ((depo / "ONAY_KAYDI.md").read_bytes(), git(depo, "rev-parse", "HEAD"),
            git(uzak_depo(depo), "rev-parse", "main"), git(depo, "status", "--porcelain"))


def _kilit_commit(depo, mesaj, **alanlar):
    kilit_yaz(depo, "H2", **alanlar)
    git(depo, "add", ".")
    git(depo, "commit", "-q", "-m", mesaj)
    git(depo, "push", "-q", "origin", "main")


_KAPANDI = dict(hukum=split.KILIT_KAPANDI, gerekce="aday yok", yapilandirma="-", parametreler="-", k2_farki="-")


def test_gercek_git_calisma_agaci_kilidi_committen_farkliysa_kosu_acilmaz(tmp_path):
    """On-kayit §8 madde 5: secim "onay kosusundan once ... commit edilir". Calisma agacindaki KILIT.md
    HEAD'dekinden farkliysa (commit edilmemis degisiklik) kosu acilmaz, hicbir sey yazilmaz."""
    depo = gecici_depo(tmp_path)
    kilit_yaz(depo, "H2", k2_farki="0.9000")
    once = _git_durumu(depo)
    with pytest.raises(split.KilitYok):
        with kosu("H2", "C1"):
            pytest.fail("commit edilmemis kilitle kosu acilmamali")
    assert _git_durumu(depo) == once
    with pytest.raises(split.OnayGerekli):
        split.kume_erisimi("BTCUSDT", "C1", onay=True)


def test_gercek_git_hukmu_degistirilmis_calisma_agaci_kapanmis_hipotezi_acamaz(tmp_path):
    """Saldiri: HEAD'de 'hipotez kapandi', calisma agacinda 'yapilandirma secildi'. Kapanmis hipotezin
    onay verisi calisma agacindaki bir duzenlemeyle acilamaz (on-kayit §8 madde 4-5)."""
    # MADDE 2g: kayit git gecmisinde tam bir kez eklenmis olmali, bu yuzden H2'nin kaydi ilk
    # commit'e KONMAZ ve asagida tek commit'te yazilir (on-kayit §8 madde 5 ekleme kurali).
    depo = gecici_depo(tmp_path, kilitler=("H1", "H3"))
    _kilit_commit(depo, "kapandi", **_KAPANDI)
    kilit_yaz(depo, "H2")                                        # commit edilmemis 'secildi' kaydi
    once = _git_durumu(depo)
    with pytest.raises(split.OnayOrtamiHatasi):
        with kosu("H2", "C1"):
            pytest.fail("kapanmis hipotez icin kosu acilmamali")
    assert _git_durumu(depo) == once


def test_gercek_git_izlenmeyen_kilit_dosyasi_kabul_edilmez(tmp_path):
    """Dosya diskte var ama HEAD'de yok (git rm --cached): 'commit edilmis olmali' sarti."""
    depo = gecici_depo(tmp_path)
    git(depo, "rm", "-q", "--cached", "analysis/H2/KILIT.md")
    git(depo, "commit", "-q", "-m", "kilit izlenmiyor")
    assert (depo / "analysis" / "H2" / "KILIT.md").exists()
    once = _git_durumu(depo)
    with pytest.raises(split.KilitYok):
        with kosu("H2", "C1"):
            pytest.fail("izlenmeyen kilitle kosu acilmamali")
    assert _git_durumu(depo) == once


def test_gercek_git_silinmis_kilit_dosyasi_kosu_acmaz(tmp_path):
    """Kilit dosyasi commit'li silindi: 'kaydi olmayan hipotez' (on-kayit §8 madde 5)."""
    depo = gecici_depo(tmp_path)
    git(depo, "rm", "-q", "analysis/H2/KILIT.md")
    git(depo, "commit", "-q", "-m", "kilit silindi")
    once = _git_durumu(depo)
    with pytest.raises(split.KilitYok):
        with kosu("H2", "C1"):
            pytest.fail("silinmis kilitle kosu acilmamali")
    assert _git_durumu(depo) == once


def test_gercek_git_kilide_yoksayilan_satir_eklenince_kirli_agac_kosuyu_durdurur(tmp_path):
    """Savunma derinligi: `kilit_oku` cozumleri esit buldugu (yoksayilan bir satir) degisiklikte bile
    kosu, kirli calisma agaci nedeniyle acilmaz (CLAUDE.md §3.3 'temiz calisma agacinda')."""
    depo = gecici_depo(tmp_path)
    yol = depo / "analysis" / "H2" / "KILIT.md"
    with yol.open("a", encoding="utf-8", newline="") as dosya:
        dosya.write("| not | serbest metin |\n")
    once = _git_durumu(depo)
    with pytest.raises(split.OnayOrtamiHatasi):
        with kosu("H2", "C1"):
            pytest.fail("kirli agacta kosu acilmamali")
    assert _git_durumu(depo) == once


def test_gercek_git_kapandi_kaydi_icin_kosu_acilmaz_ve_hicbir_sey_yazilmaz(tmp_path):
    """On-kayit §8 madde 4-5: 'hipotez kapandi' kaydi icin kosu acilmaz, onay verisi harcanmaz. (Hata sinifi
    iki kod yolunda farklidir; bkz. asagidaki XFAIL. Burada yalnizca reddedilme ve 'hicbir sey yazilmadi'.)"""
    # MADDE 2g: kayit git gecmisinde tam bir kez eklenmis olmali, bu yuzden H2'nin kaydi ilk
    # commit'e KONMAZ ve asagida tek commit'te yazilir (on-kayit §8 madde 5 ekleme kurali).
    depo = gecici_depo(tmp_path, kilitler=("H1", "H3"))
    _kilit_commit(depo, "kapandi", **_KAPANDI)
    once = _git_durumu(depo)
    with pytest.raises(split.OnayOrtamiHatasi):
        with kosu("H2", "C1"):
            pytest.fail("kapanmis hipotez icin kosu acilmamali")
    assert _git_durumu(depo) == once
    assert split.aktif_onay_kosusu() is None


# SIZINTI BULGUSU S-C8 KAPANDI (madde 2f): kapandi hukmunde `k2_farki` None (NaN degil), bu yuzden
# ayni metnin iki cozumu esit ve kapanmis hipotez gercek git kipinde de `HipotezKapandi` veriyor.
# Isaret kaldirildi; beklenti degismedi.
def test_gercek_git_commitli_kapandi_kaydi_hipotez_kapandi_hatasi_verir(tmp_path):
    """On-kayit §8 madde 4-5 (rev.13): hukmu 'hipotez kapandi' olan hipotez icin kosu acilmaz; kayit
    okunabilir olmali ve hata `HipotezKapandi` olmali."""
    # MADDE 2g: kayit git gecmisinde tam bir kez eklenmis olmali, bu yuzden H2'nin kaydi ilk
    # commit'e KONMAZ ve asagida tek commit'te yazilir (on-kayit §8 madde 5 ekleme kurali).
    depo = gecici_depo(tmp_path, kilitler=("H1", "H3"))
    _kilit_commit(depo, "kapandi", **_KAPANDI)
    kayit = split.kilit_oku("H2")
    assert kayit.secildi is False and kayit.gerekce == "aday yok"
    with pytest.raises(split.HipotezKapandi):
        with kosu("H2", "C1"):
            pytest.fail("kapanmis hipotez icin kosu acilmamali")


# SIZINTI BULGUSU S-C9 KAPANDI (madde 2g): `kilit_oku` artik kaydin git GECMISINI de okuyor ve
# dosyanin gecmiste tek bir ICERIKLE bulunmasini istiyor. Isaret kaldirildi; testin hukmu
# degismedi (kosu acilmamali). On kosul artik `kilit_oku` ile degil dosya metniyle okunuyor,
# cunku degistirilmis kayit `kilit_oku`da zaten reddediliyor.
def test_gercek_git_kilit_commit_gecmisinde_degistirilmisse_kosu_acilmaz(tmp_path):
    """On-kayit §8 madde 5 ekleme kurali (git gecmisi uzerinden)."""
    depo = gecici_depo(tmp_path)
    yol = split.kilit_yolu("H2")
    ilk = yol.read_text(encoding="utf-8")
    _kilit_commit(depo, "kilit degistirildi", yapilandirma="H2:phi=0.0005,k=6", parametreler="phi=0.0005 k=6")
    assert yol.read_text(encoding="utf-8") != ilk             # degisiklik gercekten commit'li
    assert git(depo, "status", "--porcelain") == ""           # ve calisma agaci temiz
    with pytest.raises(split.OnayOrtamiHatasi):
        with kosu("H2", "C1"):
            pass
