"""Rev.11 uygulamasi madde 6: olay dizisi kurallari (on-kayit §5, rev.11).

Bekleme suresi, H1'de tek izleme ve H3'te "ilk gun". Her kuralin SINIR DURUMU ayri sinanir.
`data.dizi` saftir: kosul degerlendirmesi ve kapi iki cagrilabilirle verilir, bu yuzden dizi
kurallari veriden ve kapidan bagimsiz, tam deterministik sinanir. Getiri hesaplanmaz, sinyal
degeri raporlanmaz. Aga cikmaz.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import dizi, pencere, pozisyon, sinyal

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
G1 = pd.Timedelta(days=1)

H4_UFUK = config.BIRINCIL_UFUK[config.BAR_4H]   # 18
G1_UFUK = config.BIRINCIL_UFUK[config.BAR_1D]   # 14


DIZI_KIMLIGI = dict(sembol="TESTONAYUSDT", kume="KESIF", donem_no=0)

def _zamanlar(bas, adet, adim="4h"):
    return pd.date_range(bas, periods=adet, freq=adim)


def _kapi(hipotez, yapilandirma=None):
    """Her adayi onaylayan kapi: SORULAN (t, capa) ciftine ait IMZALI bir onay doner.

    Rev.13'ten once bu yardimci `("pozisyon", t, capa)` demeti donduruyordu; `dizi.olay_dizisi`
    donen her nesneyi olay sayiyordu (sizinti bulgusu S-B1). Artik dizi onayi dogruluyor (imza,
    rol, hipotez, yapilandirma, sorulan t ve capa), bu yuzden sahte kapi da gercek bir onay
    uretmek zorunda. `pozisyon._test_onayi` veri yuklemeden imzali bir onay kurar (yalnizca
    pytest icinde kullanilabilir); dizi KURALLARI yine kapidan ve veriden bagimsiz sinanir.
    """
    def karar(t, capa):
        return pozisyon._test_onayi(
            hipotez=hipotez, yapilandirma=dict(sinyal.izgara(hipotez)[0]) if yapilandirma is None
            else yapilandirma, t=t, capa=capa)

    return karar


def _kapi_hep_reddeder(t, capa):
    raise pencere.GirisBariYok("test: kapi reddetti")


def _h2_yap():
    return dict(sinyal.izgara("H2")[0])


def _h3_yap():
    return dict(sinyal.izgara("H3")[0])


def _h1_yap():
    return dict(sinyal.izgara("H1")[0])


# --- Bekleme suresi (on-kayit §5 rev.11) -------------------------------------------------------


def test_bekleme_araligi_ust_ucu_dahildir():
    """Uygulama karari (`dizi.BEKLEME_UST_UC_DAHIL`): bekleme `(t0, t0 + h × adim]`."""
    t0 = T("2025-03-01 00:00")
    assert dizi.bekleme_sonu(t0, H4_UFUK, config.BAR_4H) == t0 + H4_UFUK * H4
    assert not dizi.beklemede_mi(t0, t0, H4_UFUK, config.BAR_4H)              # olay barinin kendisi
    assert dizi.beklemede_mi(t0 + H4, t0, H4_UFUK, config.BAR_4H)             # hemen sonraki bar
    assert dizi.beklemede_mi(t0 + H4_UFUK * H4, t0, H4_UFUK, config.BAR_4H)   # tam ust uc: DAHIL
    assert not dizi.beklemede_mi(t0 + (H4_UFUK + 1) * H4, t0, H4_UFUK, config.BAR_4H)  # ilk serbest bar


def test_bekleme_h2de_ardisik_olaylari_ufuk_kadar_ayirir():
    """H2'de her bar kosulu sagliyorsa olaylar 19 bar arayla olusur (18 bar bekleme + 1)."""
    zamanlar = _zamanlar(T("2025-03-01"), 60)
    sonuc = dizi.olay_dizisi("H2", _h2_yap(), zamanlar, config.BAR_4H, birincil_ufuk=H4_UFUK,
                             kosul=lambda t, capa: True, karar=_kapi("H2", _h2_yap()), **DIZI_KIMLIGI)
    beklenen = [zamanlar[0], zamanlar[H4_UFUK + 1], zamanlar[2 * (H4_UFUK + 1)], zamanlar[3 * (H4_UFUK + 1)]]
    assert list(sonuc.olay_zamanlari) == beklenen
    assert {r.gerekce for r in sonuc.retler} == {"bekleme_suresi"}


def test_kapidan_gecmeyen_aday_beklemeyi_baslatmaz():
    """On-kayit §5 rev.11: "Bekleme yalnizca olusmus olaylar icin isler: §4'teki karar
    noktasindan gecmemis bir aday beklemeyi baslatmaz." """
    zamanlar = _zamanlar(T("2025-03-01"), 5)
    sonuc = dizi.olay_dizisi("H2", _h2_yap(), zamanlar, config.BAR_4H, birincil_ufuk=H4_UFUK,
                             kosul=lambda t, capa: True, karar=_kapi_hep_reddeder, **DIZI_KIMLIGI)
    assert sonuc.olaylar == ()
    # Bes barin BESI de kapiya gitti: ret beklemeyi baslatmadigi icin hicbiri atlanmadi.
    assert [r.zaman for r in sonuc.retler] == list(zamanlar)
    assert {r.gerekce for r in sonuc.retler} == {"giris_bari_yok"}


def test_bekleme_donem_sinirinda_sifirlanir():
    """On-kayit §5 rev.11: "Bekleme donem sinirini asmaz: yeni donemde sifirlanir." Dizi donem
    basina kosuldugu icin ikinci donemin ilk bari serbesttir."""
    d1 = _zamanlar(T("2025-03-01"), 3)
    d2 = _zamanlar(T("2025-03-01") + 2 * H4, 3)  # birinci donemin olayinin bekleme suresi icinde
    ilk = dizi.olay_dizisi("H2", _h2_yap(), d1, config.BAR_4H, birincil_ufuk=H4_UFUK,
                           kosul=lambda t, capa: True, karar=_kapi("H2", _h2_yap()), **DIZI_KIMLIGI)
    ikinci = dizi.olay_dizisi("H2", _h2_yap(), d2, config.BAR_4H, birincil_ufuk=H4_UFUK,
                              kosul=lambda t, capa: True, karar=_kapi("H2", _h2_yap()), **DIZI_KIMLIGI)
    assert ilk.olay_zamanlari == (d1[0],)
    assert ikinci.olay_zamanlari == (d2[0],), "yeni donemde bekleme sifirlanmali"


def test_bekleme_yapilandirma_basina_isler():
    """On-kayit §5 rev.11: "Bekleme yapilandirma basina isler; her yapilandirma kendi olay
    dizisini uretir." Iki yapilandirma ayri cagrilardir ve birbirini engellemez."""
    zamanlar = _zamanlar(T("2025-03-01"), 3)
    a, b = sinyal.izgara("H2")[0], sinyal.izgara("H2")[1]
    assert dict(a) != dict(b)
    for y in (a, b):
        sonuc = dizi.olay_dizisi("H2", y, zamanlar, config.BAR_4H, birincil_ufuk=H4_UFUK,
                                 kosul=lambda t, capa: True, karar=_kapi("H2", y), **DIZI_KIMLIGI)
        assert sonuc.olay_zamanlari == (zamanlar[0],)


def test_hesaplanamayan_kosul_olay_uretmez():
    zamanlar = _zamanlar(T("2025-03-01"), 3)
    sonuc = dizi.olay_dizisi("H2", _h2_yap(), zamanlar, config.BAR_4H, birincil_ufuk=H4_UFUK,
                             kosul=lambda t, capa: None, karar=_kapi("H2", _h2_yap()), **DIZI_KIMLIGI)
    assert sonuc.olaylar == ()
    assert {r.gerekce for r in sonuc.retler} == {"sinyal_penceresi_tam_degil"}


# --- H1 tek izleme (on-kayit §5 H1 madde 4, rev.11) --------------------------------------------


def _h1_kosul(pumplar, teyitler):
    """`capa is None` cagrisi pump sorar, `capa=p` cagrisi teyit sorar."""
    def kosul(t, capa):
        if capa is None:
            return t in pumplar
        return t in teyitler
    return kosul


def test_h1_teyit_bari_olay_uretir_ve_izlemeyi_bitirir():
    z = _zamanlar(T("2025-03-01"), 40)
    sonuc = dizi.olay_dizisi("H1", _h1_yap(), z, config.BAR_4H, birincil_ufuk=H4_UFUK,
                             kosul=_h1_kosul({z[0]}, {z[3]}), karar=_kapi("H1", _h1_yap()), **DIZI_KIMLIGI)
    assert [(o.zaman, o.capa) for o in sonuc.olaylar] == [(z[3], z[0])]


def test_h1_izleme_surerken_yeni_pump_yok_sayilir():
    """Rev.11: "Izleme surerken pump kosulunu saglayan yeni bir bar gelirse yok sayilir: tepe ve
    12 barlik sayac ilk pump barindan olculmeye devam eder." Teyit, ILK pump barina capalanir."""
    z = _zamanlar(T("2025-03-01"), 40)
    sonuc = dizi.olay_dizisi("H1", _h1_yap(), z, config.BAR_4H, birincil_ufuk=H4_UFUK,
                             kosul=_h1_kosul({z[0], z[2], z[5]}, {z[6]}), karar=_kapi("H1", _h1_yap()), **DIZI_KIMLIGI)
    assert [(o.zaman, o.capa) for o in sonuc.olaylar] == [(z[6], z[0])], "capa ilk pump bari olmali"


def test_h1_izleme_12_bar_sonra_biter_ve_12nci_bar_yeni_izleme_baslatmaz():
    """Sinir durumu: teyit en fazla 12 bar icinde gelir. 12. bar hala izlemenin icindedir; o barda
    gelen pump yok sayilir, yeni izleme ancak 13. bardan itibaren baslar."""
    z = _zamanlar(T("2025-03-01"), 60)
    n = config.H1_IZLEME_BAR  # 12
    # Teyit yok; 12. bar (z[n]) pump kosulunu sagliyor -> yok sayilmali. 13. bar (z[n+1]) pump.
    sonuc = dizi.olay_dizisi("H1", _h1_yap(), z, config.BAR_4H, birincil_ufuk=H4_UFUK,
                             kosul=_h1_kosul({z[0], z[n], z[n + 1]}, {z[n + 4]}), karar=_kapi("H1", _h1_yap()), **DIZI_KIMLIGI)
    assert [(o.zaman, o.capa) for o in sonuc.olaylar] == [(z[n + 4], z[n + 1])]


def test_h1_12nci_barda_gelen_teyit_hala_olay_uretir():
    """Sinir durumu: "pump barindan sonraki 12 bar icinde" -> 12. bar DAHIL."""
    z = _zamanlar(T("2025-03-01"), 40)
    n = config.H1_IZLEME_BAR
    sonuc = dizi.olay_dizisi("H1", _h1_yap(), z, config.BAR_4H, birincil_ufuk=H4_UFUK,
                             kosul=_h1_kosul({z[0]}, {z[n]}), karar=_kapi("H1", _h1_yap()), **DIZI_KIMLIGI)
    assert [(o.zaman, o.capa) for o in sonuc.olaylar] == [(z[n], z[0])]


def test_h1_13uncu_barda_gelen_teyit_olay_uretmez():
    z = _zamanlar(T("2025-03-01"), 40)
    n = config.H1_IZLEME_BAR
    sonuc = dizi.olay_dizisi("H1", _h1_yap(), z, config.BAR_4H, birincil_ufuk=H4_UFUK,
                             kosul=_h1_kosul({z[0]}, {z[n + 1]}), karar=_kapi("H1", _h1_yap()), **DIZI_KIMLIGI)
    assert sonuc.olaylar == ()


def test_h1_bir_teyit_bari_en_cok_bir_olay_sayar():
    """Rev.11: "Boylece bir teyit bari en cok bir olay sayar." Iki pump adayi ve ortak bir teyit
    barinda tek olay olusur."""
    z = _zamanlar(T("2025-03-01"), 40)
    sonuc = dizi.olay_dizisi("H1", _h1_yap(), z, config.BAR_4H, birincil_ufuk=H4_UFUK,
                             kosul=_h1_kosul({z[0], z[1]}, {z[4]}), karar=_kapi("H1", _h1_yap()), **DIZI_KIMLIGI)
    assert len(sonuc.olaylar) == 1


def test_h1_beklemeden_sonra_yeni_izleme_baslar():
    """Rev.11: "yeni bir izleme ancak bundan sonra (ve olay olustuysa bekleme suresi dolduktan
    sonra) baslayabilir." """
    z = _zamanlar(T("2025-03-01"), 80)
    teyit = z[2]
    serbest = z[2 + H4_UFUK + 1]
    sonuc = dizi.olay_dizisi("H1", _h1_yap(), z, config.BAR_4H, birincil_ufuk=H4_UFUK,
                             kosul=_h1_kosul({z[0], z[5], serbest}, {teyit, z[8], serbest + 2 * H4}),
                             karar=_kapi("H1", _h1_yap()), **DIZI_KIMLIGI)
    assert [o.zaman for o in sonuc.olaylar] == [teyit, serbest + 2 * H4]
    assert z[5] in [r.zaman for r in sonuc.retler]  # bekleme icindeki pump adayi


# --- H3 "ilk gun" (on-kayit §5 H3 madde 3, rev.11) ---------------------------------------------


def test_h3_kesintisiz_dizinin_yalnizca_ilk_gunu_olaydir():
    g = _zamanlar(T("2025-03-01"), 10, "D")
    saglanan = set(g[:5])
    sonuc = dizi.olay_dizisi("H3", _h3_yap(), g, config.BAR_1D, birincil_ufuk=G1_UFUK,
                             kosul=lambda t, capa: t in saglanan, karar=_kapi("H3", _h3_yap()), **DIZI_KIMLIGI)
    assert sonuc.olay_zamanlari == (g[0],)
    assert [r.gerekce for r in sonuc.retler] == ["dizi_ilk_gun_degil"] * 4


def test_h3_dizi_kesilince_yeni_ilk_gun_olusur():
    """"Dizi kesildikten sonra kosullar yeniden birlikte saglanirsa o gun yeni bir 'ilk gun'dur ve
    bekleme suresi ayrica uygulanir." Burada ikinci dizi beklemenin DISINDA baslar."""
    g = _zamanlar(T("2025-03-01"), 40, "D")
    saglanan = {g[0], g[1]} | {g[20], g[21]}
    sonuc = dizi.olay_dizisi("H3", _h3_yap(), g, config.BAR_1D, birincil_ufuk=G1_UFUK,
                             kosul=lambda t, capa: t in saglanan, karar=_kapi("H3", _h3_yap()), **DIZI_KIMLIGI)
    assert sonuc.olay_zamanlari == (g[0], g[20])


def test_h3_ikinci_dizi_beklemenin_icindeyse_olay_olusmaz():
    """Sinir durumu: dizi kesilip yeniden baslasa bile bekleme suresi ayrica uygulanir."""
    g = _zamanlar(T("2025-03-01"), 40, "D")
    saglanan = {g[0]} | {g[5], g[6]}  # ikinci dizi 14 gunluk beklemenin icinde
    sonuc = dizi.olay_dizisi("H3", _h3_yap(), g, config.BAR_1D, birincil_ufuk=G1_UFUK,
                             kosul=lambda t, capa: t in saglanan, karar=_kapi("H3", _h3_yap()), **DIZI_KIMLIGI)
    assert sonuc.olay_zamanlari == (g[0],)
    assert "bekleme_suresi" in {r.gerekce for r in sonuc.retler}


def test_h3_hesaplanamayan_gun_diziyi_keser():
    """"Dizi, kosullardan biri saglanmadigi ya da §2 'Tamlik sarti' geregi hesaplanamadigi gunde
    kesilir." Hesaplanamayan gun diziyi keser; sonraki gun yeni ilk gundur."""
    g = _zamanlar(T("2025-03-01"), 40, "D")

    def kosul(t, capa):
        if t == g[20]:
            return None
        return t in set(g[18:25])

    sonuc = dizi.olay_dizisi("H3", _h3_yap(), g, config.BAR_1D, birincil_ufuk=G1_UFUK,
                             kosul=kosul, karar=_kapi("H3", _h3_yap()), **DIZI_KIMLIGI)
    assert sonuc.olay_zamanlari == (g[18],)        # ilk dizi
    # g[21] yeni ilk gundur ama g[18] olayinin 14 gunluk beklemesi icinde: olay olusmaz.
    assert g[21] in [r.zaman for r in sonuc.retler if r.gerekce == "bekleme_suresi"]


def test_h3_kesintisiz_dizi_icinde_bekleme_dolsa_bile_yeni_olay_sayilmaz():
    """"Kesintisiz suren bir dizinin icinde, bekleme suresi dolsa bile yeni olay sayilmaz."""
    g = _zamanlar(T("2025-03-01"), 60, "D")
    saglanan = set(g[:40])  # 14 gunluk bekleme dizinin icinde doluyor
    sonuc = dizi.olay_dizisi("H3", _h3_yap(), g, config.BAR_1D, birincil_ufuk=G1_UFUK,
                             kosul=lambda t, capa: t in saglanan, karar=_kapi("H3", _h3_yap()), **DIZI_KIMLIGI)
    assert sonuc.olay_zamanlari == (g[0],)


def test_h3_ilk_gunu_kapi_reddederse_dizide_olay_olusmaz():
    """Olay "iki kosulun birlikte saglandigi kesintisiz dizinin ilk gunu"dur; o gun kapidan
    gecmezse dizinin sonraki gunleri olay olmaz."""
    g = _zamanlar(T("2025-03-01"), 10, "D")
    saglanan = set(g[:5])
    sonuc = dizi.olay_dizisi("H3", _h3_yap(), g, config.BAR_1D, birincil_ufuk=G1_UFUK,
                             kosul=lambda t, capa: t in saglanan, karar=_kapi_hep_reddeder, **DIZI_KIMLIGI)
    assert sonuc.olaylar == ()


def test_h2de_ilk_gun_kurali_yok():
    """H3'un dizi kurali H2'ye uygulanmaz: H2'de her bar kendi basina olay adayidir (yalnizca
    bekleme suresi sinirlar)."""
    assert "H2" not in dizi.DIZI_ILK_GUN_HIPOTEZLERI
    z = _zamanlar(T("2025-03-01"), 25)
    sonuc = dizi.olay_dizisi("H2", _h2_yap(), z, config.BAR_4H, birincil_ufuk=H4_UFUK,
                             kosul=lambda t, capa: True, karar=_kapi("H2", _h2_yap()), **DIZI_KIMLIGI)
    assert len(sonuc.olaylar) == 2


# --- Girdi denetimleri -------------------------------------------------------------------------


def test_izgara_disi_yapilandirma_hata_verir():
    z = _zamanlar(T("2025-03-01"), 3)
    with pytest.raises(sinyal.YapilandirmaHatasi):
        dizi.olay_dizisi("H2", {"phi": 0.0004, "k": 6}, z, config.BAR_4H, birincil_ufuk=H4_UFUK,
                         kosul=lambda t, capa: True, karar=_kapi("H2", {"phi": 0.0004, "k": 6}), **DIZI_KIMLIGI)


def test_hipotezin_izgarasi_disinda_bar_hata_verir():
    g = _zamanlar(T("2025-03-01"), 3, "D")
    with pytest.raises(ValueError, match="izgarasi"):
        dizi.olay_dizisi("H2", _h2_yap(), g, config.BAR_1D, birincil_ufuk=G1_UFUK,
                         kosul=lambda t, capa: True, karar=_kapi("H2", _h2_yap()), **DIZI_KIMLIGI)


def test_on_kayit_disi_birincil_ufuk_hata_verir():
    z = _zamanlar(T("2025-03-01"), 3)
    with pytest.raises(ValueError, match="birincil_ufuk"):
        dizi.olay_dizisi("H2", _h2_yap(), z, config.BAR_4H, birincil_ufuk=17,
                         kosul=lambda t, capa: True, karar=_kapi("H2", _h2_yap()), **DIZI_KIMLIGI)


def test_sirasiz_ya_da_tekrarli_zamanlar_reddedilir():
    z = _zamanlar(T("2025-03-01"), 3)
    with pytest.raises(ValueError, match="artan"):
        dizi.olay_dizisi("H2", _h2_yap(), z[::-1], config.BAR_4H, birincil_ufuk=H4_UFUK,
                         kosul=lambda t, capa: True, karar=_kapi("H2", _h2_yap()), **DIZI_KIMLIGI)
    with pytest.raises(ValueError, match="artan"):
        dizi.olay_dizisi("H2", _h2_yap(), z.append(z[:1]), config.BAR_4H, birincil_ufuk=H4_UFUK,
                         kosul=lambda t, capa: True, karar=_kapi("H2", _h2_yap()), **DIZI_KIMLIGI)


def test_kosul_yaniti_bool_olmali():
    z = _zamanlar(T("2025-03-01"), 3)
    with pytest.raises(TypeError, match="kosul yaniti"):
        dizi.olay_dizisi("H2", _h2_yap(), z, config.BAR_4H, birincil_ufuk=H4_UFUK,
                         kosul=lambda t, capa: 1.0, karar=_kapi("H2", _h2_yap()), **DIZI_KIMLIGI)


# --- Gercek kapiyla kopru: `pozisyon.sinyal_kosulu` (Rev.11 madde 6) --------------------------
#
# Dizi kurallari yukarida saf cagrilabilirlerle sinandi. Asagidaki testler ayni kurallarin
# GERCEK kapi ve gercek sinyal pencereleriyle de calistigini gosterir: `pozisyon.sinyal_kosulu`
# dizinin `kosul` argumani, `pozisyon.olay_karari` ise `karar` argumanidir.

import functools  # noqa: E402

import numpy as np  # noqa: E402

from data import pozisyon  # noqa: E402
from kapi_yardimcisi import veri  # noqa: E402
from kume_yardimcisi import kume_adi  # noqa: E402
from sinyal_yardimcisi import yapilandirma  # noqa: E402
from uygunluk_yardimcisi import esikler  # noqa: E402

HACIM = 1e7
DB2, B2 = T("2025-01-01"), T("2025-06-30 20:00")
T2 = T("2025-03-10 04:00")


def _duz(bas, son, fiyat=1.0, hacim=HACIM):
    z = pd.date_range(bas, son, freq="4h")
    return pd.DataFrame({"open_time": z, "open": fiyat, "high": fiyat, "low": fiyat, "close": fiyat,
                         "quote_volume": float(hacim)})


def _fund(bas, son, oran=0.0005):
    z = pd.date_range(bas, son, freq="8h")
    return pd.DataFrame({"odeme_zamani": z, "aralik_saat": 8.0, "oran": 0.0, "oran_8h": float(oran)})


def _h2_serisi(olay_zamanlari):
    """Verilen barlarda H2'nin uc kosulunu da saglayan seri."""
    m = _duz(DB2, B2)
    z = pd.DatetimeIndex(m["open_time"])
    for t in olay_zamanlari:
        dip = (z >= t - 3 * H4) & (z <= t - H4)
        m.loc[dip, ["low", "high", "close", "open"]] = 1.5
        m.loc[z == t, ["low", "high", "close", "open"]] = 1.2
    return m


def _gercek_dizi(olay_zamanlari, barlar):
    kayit = veri(_h2_serisi(olay_zamanlari), _fund(DB2, B2 + H4), DB2, B2, uygun_bas=DB2, hacim=6 * HACIM)
    y = yapilandirma("H2")
    ortak = dict(hipotez="H2", yapilandirma=y, kume=kume_adi(T2), **kayit)
    kosul = functools.partial(_kosul_koprusu, ortak)
    karar = functools.partial(_karar_koprusu, ortak)
    # Dizinin kimligi gercek kaydin kendisi (madde 3a): `kayit` sembol ve donem_no doner.
    return dizi.olay_dizisi("H2", y, barlar, config.BAR_4H,
                            birincil_ufuk=config.BIRINCIL_UFUK[config.BAR_4H], kosul=kosul, karar=karar,
                            sembol=kayit["sembol"], kume=ortak["kume"], donem_no=kayit["donem_no"])


def _kosul_koprusu(ortak, t, capa):
    return pozisyon.sinyal_kosulu(t, capa=capa, **ortak)


def _karar_koprusu(ortak, t, capa):
    tanim = pencere.hipotez_ufuklari("H2")
    return pozisyon.olay_karari(t, tanim.birincil, tanim.bar, birincil_ufuk=tanim.birincil,
                                rol="olay", capa=capa, **ortak, **esikler(tanim.bar))


def test_gercek_kapiyla_olay_dizisi_bekleme_suresini_uygular():
    """Ayni serideki iki H2 kosulu: ikincisi beklemenin icindeyse olay sayilmaz."""
    ikinci = T2 + 5 * H4  # 18 barlik beklemenin icinde
    barlar = pd.date_range(T2 - 2 * H4, T2 + 30 * H4, freq="4h")
    sonuc = _gercek_dizi([T2, ikinci], barlar)
    assert sonuc.olay_zamanlari == (T2,)
    assert any(r.zaman == ikinci and r.gerekce == "bekleme_suresi" for r in sonuc.retler)


def test_gercek_kapiyla_bekleme_dolduktan_sonra_ikinci_olay_olusur():
    ikinci = T2 + (config.BIRINCIL_UFUK[config.BAR_4H] + 1) * H4  # ilk serbest bar
    barlar = pd.date_range(T2 - 2 * H4, T2 + 40 * H4, freq="4h")
    sonuc = _gercek_dizi([T2, ikinci], barlar)
    assert sonuc.olay_zamanlari == (T2, ikinci)


def test_gercek_kosul_koprusu_uc_durumu_doner():
    """`sinyal_kosulu` True / False / None dondurur: kosul saglanir, saglanmaz, hesaplanamaz."""
    kayit = veri(_h2_serisi([T2]), _fund(DB2, B2 + H4), DB2, B2, uygun_bas=DB2, hacim=6 * HACIM)
    ortak = dict(hipotez="H2", yapilandirma=yapilandirma("H2"), kume=kume_adi(T2), **kayit)
    assert pozisyon.sinyal_kosulu(T2, capa=None, **ortak) is True
    assert pozisyon.sinyal_kosulu(T2 + 10 * H4, capa=None, **ortak) is False

    m = _h2_serisi([T2])
    eksik = m.loc[pd.DatetimeIndex(m["open_time"]) != T2 - H4].reset_index(drop=True)
    kayit2 = veri(eksik, _fund(DB2, B2 + H4), DB2, B2, uygun_bas=DB2, hacim=6 * HACIM)
    ortak2 = dict(hipotez="H2", yapilandirma=yapilandirma("H2"), kume=kume_adi(T2), **kayit2)
    assert pozisyon.sinyal_kosulu(T2, capa=None, **ortak2) is None


def test_gercek_kosul_koprusu_h1de_pump_ve_teyit_adimlarini_ayirir():
    """H1'de `capa=None` PUMP kosulunu, `capa=p` TEYIT kosulunu sorar (on-kayit §5 H1)."""
    p = T("2025-03-10 04:00")
    teyit = p + 3 * H4
    m = _duz(DB2, B2)
    z = pd.DatetimeIndex(m["open_time"])
    m.loc[(z >= p - 5 * H4) & (z <= p), "quote_volume"] = 3 * HACIM
    m.loc[z == p, ["close", "high"]] = [1.25, 1.30]
    kayit = veri(m, _fund(DB2, B2 + H4), DB2, B2, uygun_bas=DB2, hacim=6 * HACIM)
    ortak = dict(hipotez="H1", yapilandirma=yapilandirma("H1"), kume=kume_adi(p), **kayit)
    assert pozisyon.sinyal_kosulu(p, capa=None, **ortak) is True          # pump bari
    assert pozisyon.sinyal_kosulu(p - 10 * H4, capa=None, **ortak) is False
    assert pozisyon.sinyal_kosulu(teyit, capa=p, **ortak) is True          # teyit bari
    # 12 bardan uzak bir teyit adayi: tepe penceresi kurulamaz -> hesaplanamaz.
    assert pozisyon.sinyal_kosulu(p + 13 * H4, capa=p, **ortak) is None


def test_gercek_kapiyla_h1_tek_izleme():
    """Izleme surerken gelen ikinci pump bari yok sayilir; olay ILK pump barina capalanir.

    Kurgu: p ve p+2 pump kosulunu saglar. p+1 .. p+3 barlarinin kapanisi teyit esiginin
    (tepe x (1 - δ) = 1.30 x 0.92 = 1.196) USTUNDE, bu yuzden teyit gelmez; p+4'te kapanis
    duser ve teyit olusur. Capa p olmali: izleme p+2'de yeniden baslamadi."""
    p = T("2025-03-10 04:00")
    teyit = p + 4 * H4
    m = _duz(DB2, B2)
    z = pd.DatetimeIndex(m["open_time"])
    # Teyit esiginin ustunde kalan ara barlar (high < tepe olacak sekilde).
    m.loc[(z > p) & (z < teyit), ["close", "open"]] = 1.25
    m.loc[(z > p) & (z < teyit), "high"] = 1.26
    for pump in (p, p + 2 * H4):
        m.loc[(z >= pump - 5 * H4) & (z <= pump), "quote_volume"] = 3 * HACIM
        m.loc[z == pump, ["close", "high"]] = [1.25, 1.30]
    kayit = veri(m, _fund(DB2, B2 + H4), DB2, B2, uygun_bas=DB2, hacim=6 * HACIM)
    y = yapilandirma("H1")
    ortak = dict(hipotez="H1", yapilandirma=y, kume=kume_adi(p), **kayit)
    tanim = pencere.hipotez_ufuklari("H1")
    sonuc = dizi.olay_dizisi(
        "H1", y, pd.date_range(p - 2 * H4, p + 20 * H4, freq="4h"), config.BAR_4H,
        birincil_ufuk=tanim.birincil,
        kosul=lambda t, capa: pozisyon.sinyal_kosulu(t, capa=capa, **ortak),
        karar=lambda t, capa: pozisyon.olay_karari(t, tanim.birincil, tanim.bar,
                                                   birincil_ufuk=tanim.birincil, rol="olay",
                                                   capa=capa, **ortak, **esikler(tanim.bar)),
        sembol=kayit["sembol"], kume=ortak["kume"], donem_no=kayit["donem_no"])
    assert [(o.zaman, o.capa) for o in sonuc.olaylar] == [(teyit, p)]
