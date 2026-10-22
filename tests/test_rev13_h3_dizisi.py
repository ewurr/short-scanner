"""H3'un dizisi: kosullarla tanimli ve TAKVIME bagli (on-kayit §5 H3 madde 3, rev.13 (b)).

On-kayit §5 H3 madde 3 (rev.13): "Dizi kosullarla tanimlidir, karar noktasinin onayiyla degil: bir
gun iki kosulu birlikte sagliyorsa diziye aittir, o gunde olay olusup olusmadigina bakilmaz. Bunun
sonucu olarak, dizinin ilk gunu karar noktasindan gecmezse (or. funding tamligi saglanmadigi ya da
giris bari bulunmadigi icin) o dizi hic olay uretmez; dizinin ikinci gunu 'ilk gun' sayilmaz.
Gerekce: dizinin baslangici fiyat ve hacim verisinin ozelligidir, ret gerekceleri ise getirinin
yonunu secmeyen veri kosullaridir; bu okuma iki okumadan muhafazakar olanidir."

Ayrica dizi TAKVIMLE kesilir (sizinti bulgusu S-B2): seride bulunmayan (bar olmayan, §2 "Tamlik
sarti" geregi hesaplanamaz) bir gun diziyi keser; `zamanlar` listesinin bitisikligine bakilmaz.

Aga cikmaz; getiri ve sinyal degeri hesaplanmaz.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import dizi, pencere, pozisyon
import dizi_cagri

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
UFUK = config.BIRINCIL_UFUK[config.BAR_1D]       # 14 gun
# Her adayi onaylayan kapi: SORULAN (t, capa) ciftine ait IMZALI onay. `dizi.olay_dizisi`
# donen onayi dogruladigi icin (sizinti bulgusu S-B1) ham bir nesne olay sayilmaz;
# `pozisyon._test_onayi` veri yuklemeden imzali bir onay kurar (yalnizca pytest icinde).
DIZI_KIMLIGI = dict(sembol="TESTONAYUSDT", kume="KESIF", donem_no=0)

def _onay(t, capa=None):
    return pozisyon._test_onayi(hipotez="H3", yapilandirma=dict(nu=0.50, tau=0.15), t=t, capa=capa)
GUNLER = pd.date_range(T("2025-03-01"), periods=80, freq="D")


def _kosul(saglanan, hesaplanamaz=()):
    """Sahte H3 kosulu: verilen gun indekslerinde True, `hesaplanamaz`da None, digerlerinde False."""
    cagrilar = []

    def kosul(t, capa):
        assert capa is None, "H3'te capa verilmez"
        i = int(GUNLER.get_loc(t))
        cagrilar.append(i)
        if i in hesaplanamaz:
            return None
        return i in saglanan

    return kosul, cagrilar


def _calistir(idxler, kosul, karar=None):
    return dizi_cagri.cagir("H3", dict(nu=0.50, tau=0.15), GUNLER[list(idxler)], config.BAR_1D,
                            birincil_ufuk=UFUK, kosul=kosul,
                            karar=karar if karar is not None else _onay, **DIZI_KIMLIGI)


def _idx(sonuc):
    return [int(GUNLER.get_loc(z)) for z in sonuc.olay_zamanlari]


def _gerekceler(sonuc):
    return [r.gerekce for r in sonuc.retler]


# --- 1. Dizi takvimle kesilir (S-B2) ---------------------------------------------------------


def test_seride_bulunmayan_gun_diziyi_keser():
    """`zamanlar` 0, 1 ve 20, 21, 22 gunlerini tasir; 2..19 gunleri seride YOK (bar yok = §2 geregi
    hesaplanamaz). Dizi 20. gunde kesilmis sayilir, bu yuzden 20 yeni bir "ilk gun"dur."""
    kosul, _ = _kosul(set(range(30)))
    assert _idx(_calistir([0, 1, 20, 21, 22], kosul)) == [0, 20]


def test_bitisik_seride_dizi_kesilmez_ilk_gun_tek_kalir():
    """Karsi-ornek: ayni kosulla bitisik seride dizi hic kesilmez; bekleme dolsa bile (14 gun)
    kesintisiz dizinin icinde yeni olay sayilmaz."""
    kosul, _ = _kosul(set(range(30)))
    sonuc = _calistir(range(30), kosul)
    assert _idx(sonuc) == [0]
    assert _gerekceler(sonuc) == ["dizi_ilk_gun_degil"] * 29


def test_tek_gunluk_bosluk_da_diziyi_keser_sinir_durumu():
    """Sinir durumu: tek bir eksik gun yeter. 0..4 ve 6..10 (5 eksik): 0 ve 6 ilk gundur; 6
    beklemenin icinde oldugu icin (bekleme 1..14) olay DEGIL ama dizinin ilk gunudur ve
    beklemenin ret gerekcesini alir."""
    kosul, _ = _kosul(set(range(30)))
    sonuc = _calistir(list(range(5)) + list(range(6, 11)), kosul)
    assert _idx(sonuc) == [0]
    assert _gerekceler(sonuc) == ["dizi_ilk_gun_degil"] * 4 + ["bekleme_suresi"] + ["dizi_ilk_gun_degil"] * 4


def test_bosluk_sonrasi_bekleme_dolmussa_yeni_olay_olusur():
    """0'da olay (bekleme 1..14); 2..19 eksik; 20'de yeni dizi ve bekleme dolmus -> olay."""
    kosul, _ = _kosul(set(range(30)))
    assert _idx(_calistir([0, 1, 20], kosul)) == [0, 20]


def test_hesaplanamayan_gun_de_diziyi_keser():
    """On-kayit §5 H3 madde 3: dizi "§2 'Tamlik sarti' geregi hesaplanamadigi gunde kesilir".
    Bar seride var ama deger hesaplanamiyorsa (kosul None) sonuc aynidir."""
    kosul, _ = _kosul(set(range(30)) - {15}, hesaplanamaz={15})
    sonuc = _calistir(range(30), kosul)
    assert _idx(sonuc) == [0, 16]
    assert "sinyal_penceresi_tam_degil" in _gerekceler(sonuc)


# --- 2. Dizi kosullarla tanimli: kapidan gecmeyen ilk gun diziyi BASLATIR ---------------------


def test_ilk_gunu_kapidan_gecmeyen_dizi_hic_olay_uretmez():
    """Rev.13 (b): dizinin ilk gunu karar noktasindan gecmezse o dizi HIC olay uretmez; ikinci gun
    "ilk gun" sayilmaz. Kapi yalnizca ilk gunu funding tamligi gerekcesiyle reddeder; sonraki
    gunlerin kapiya hic gonderilmemesi gerekir."""
    kosul, _ = _kosul(set(range(30)))
    gonderilen = []

    def karar(t, capa):
        gonderilen.append(int(GUNLER.get_loc(t)))
        raise FundingTamDegil("funding tam degil (sahte)")

    sonuc = _calistir(range(10), kosul, karar)
    assert sonuc.olaylar == ()
    assert gonderilen == [0], "yalnizca dizinin ilk gunu kapiya gider"
    assert _gerekceler(sonuc) == ["funding_tam_degil"] + ["dizi_ilk_gun_degil"] * 9


def test_reddedilen_ilk_gun_beklemeyi_baslatmaz_ama_diziyi_baslatir():
    """Iki kural birlikte: "Bekleme yalnizca olusmus olaylar icin isler" (§5 rev.11) -- reddedilen
    ilk gun beklemeyi BASLATMAZ; ama dizi kosullarla tanimli oldugu icin dizi BASLAR. Dizi
    kesildikten sonra gelen yeni ilk gun (burada 20) kapidan gecerse olay olur."""
    kosul, _ = _kosul(set(range(30)))
    red_gunleri = {0}

    def karar(t, capa):
        if int(GUNLER.get_loc(t)) in red_gunleri:
            raise FundingTamDegil("funding tam degil (sahte)")
        return _onay(t, capa)

    sonuc = _calistir([0, 1, 2, 20, 21], kosul, karar)
    assert _idx(sonuc) == [20], "0 reddedildi, 1-2 ilk gun degil, 20 yeni dizinin ilk gunu"


def test_dizinin_ikinci_gunu_hicbir_zaman_ilk_gun_degil():
    """Rev.13 (b)'nin en keskin sonucu: ilk gun reddedilse bile ikinci gun kapiya gitmez."""
    kosul, _ = _kosul({5, 6, 7})
    gonderilen = []

    def karar(t, capa):
        gonderilen.append(int(GUNLER.get_loc(t)))
        raise FundingTamDegil("funding tam degil (sahte)")

    _calistir(range(12), kosul, karar)
    assert gonderilen == [5]


# --- 3. Kural H1 ve H2'yi degistirmez --------------------------------------------------------


def test_h2_bosluktan_etkilenmez_dizi_kurali_yalnizca_h3te():
    """H2'de "ilk gun" kurali yoktur (`dizi.DIZI_ILK_GUN_HIPOTEZLERI`): her bar kendi basina
    adaydir ve yalnizca bekleme suresi sinirlar. Takvim boslugu H2'nin olaylarini degistirmez."""
    assert dizi.DIZI_ILK_GUN_HIPOTEZLERI == ("H3",)
    barlar = pd.date_range(T("2025-03-01 00:00"), periods=60, freq="4h")
    secilen = list(range(0, 10)) + list(range(30, 40))

    def kosul(t, capa):
        return True

    def _h2_onay(t, capa=None):
        return pozisyon._test_onayi(hipotez="H2", yapilandirma=dict(phi=0.0003, k=3), t=t, capa=capa)

    sonuc = dizi_cagri.cagir("H2", dict(phi=0.0003, k=3), barlar[secilen], config.BAR_4H,
                             birincil_ufuk=config.BIRINCIL_UFUK[config.BAR_4H], kosul=kosul,
                             karar=_h2_onay, **DIZI_KIMLIGI)
    # Bekleme 18 bar: 0'da olay, 19..29 seride yok, 30'da bekleme dolmus -> olay; sonra 49 yok.
    assert [int(barlar.get_loc(z)) for z in sonuc.olay_zamanlari] == [0, 30]


class FundingTamDegil(pencere.OlayOlusmaz):
    """Kapinin `funding_tam_degil` ret gerekcesinin sahtesi (gercek sinif `data.pozisyon`da;
    bu dosya kapiyi cagirmaz, dizi kurallarini yalitik sinar)."""

    gerekce = "funding_tam_degil"
