"""Denetci bulgusu D-B2: havuz olcutlerinin girdisi DOGRULANMIS olay olmali (on-kayit §6 rev.11).

On-kayit §6 "Ornekleme kurallari" (rev.11): "K1'deki 'o hipotezin herhangi bir olayi', AYNI
YAPILANDIRMANIN olusmus olaylaridir: kapidan gecmemis (reddedilmis) adaylar ve baska
yapilandirmalarin olaylari sayilmaz. K2'deki 'olay uretmemis' de ayni yapilandirmanin olusmus olay
kumesine goredir."

Bulgu: iki olcut de ham `DatetimeIndex` / sembol kumesi aliyordu; listenin gercekten olusmus
olaylardan geldigi hicbir yerde dogrulanmiyordu. Eksik ya da yanlis liste sessizce yanlis havuz
uretir ve olculen farkin YONUNU degistirir.

BELIRSIZLIK (yorumlanmadi): on-kayit K1'de "o hipotezin herhangi bir olayi" diyor; bunun yalnizca
AYNI COININ olaylarini mi, yoksa butun coinlerin olaylarini mi kapsadigi yazili degil. Bu yuzden
dogrulama sembol kapsamini DARALTMAZ: yalnizca (hipotez, yapilandirma, kume) demeti eslestirilir.
K2'de olcut zaten "ayni t barinda ... diger coinlerden"dir, orada bar zamani da dogrulanir.

Aga cikmaz; getiri hesaplanmaz.
"""

from __future__ import annotations

import dataclasses

import pandas as pd
import pytest

import config
from data import dizi, ornekleme
from dizi_yardimcisi import olaylar_kur, olaylar_sembollerde, tek_olay
from ornekleme_yardimcisi import k1_adaylari_kur, k2_adaylari_kur, ornekle
from sinyal_yardimcisi import yapilandirma

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
UFUK = config.BIRINCIL_UFUK[config.BAR_4H]
TB = T("2025-03-10 04:00")
BARLAR = [T("2025-03-01") + i * H4 for i in range(60)]
SEMBOLLER = ["AAAUSDT", "BBBUSDT", "CCCUSDT", "DDDUSDT"]


# --- 1. Ham girdi reddedilir -------------------------------------------------------------------


@pytest.mark.parametrize("ham", [[TB], [T("2025-03-01")], pd.DatetimeIndex([TB]), ["AAAUSDT"],
                                 [1.0], [None], [object()]])
def test_k1_ham_olay_listesi_reddedilir(ham):
    adaylar = k1_adaylari_kur(BARLAR[:10])
    with pytest.raises(TypeError, match="Olay gerekir"):
        ornekleme.k1_adaylari(adaylar, ham, UFUK, config.BAR_4H)


@pytest.mark.parametrize("ham", [["AAAUSDT"], {"BBBUSDT"}, [TB], [1], [None]])
def test_k2_ham_sembol_listesi_reddedilir(ham):
    adaylar = k2_adaylari_kur(SEMBOLLER, t=TB)
    with pytest.raises(TypeError, match="Olay gerekir"):
        ornekleme.k2_adaylari(adaylar, ham, olay_sembolu="ZZZUSDT")


def test_elle_kurulmus_olay_reddedilir():
    """`Olay` imzalidir: elle kurulan nesne havuz olcutune giremez (on-kayit §4 rev.12)."""
    elle = dizi.Olay(TB, None, None)
    adaylar = k1_adaylari_kur(BARLAR[:10])
    with pytest.raises(ValueError, match="elle kurulmus"):
        ornekleme.k1_adaylari(adaylar, [elle], UFUK, config.BAR_4H)


def test_degistirilmis_olay_reddedilir():
    olay = tek_olay(TB)
    bozuk = dataclasses.replace(olay, zaman=TB + H4)
    adaylar = k1_adaylari_kur(BARLAR[:10])
    with pytest.raises(ValueError, match="elle kurulmus|degistirilmis"):
        ornekleme.k1_adaylari(adaylar, [bozuk], UFUK, config.BAR_4H)


# --- 2. Baska demetin olayi sayilmaz ----------------------------------------------------------


def test_baska_yapilandirmanin_olayi_reddedilir():
    """On-kayit §6 rev.11: "baska yapilandirmalarin olaylari sayilmaz"."""
    adaylar = k1_adaylari_kur(BARLAR[:10])                      # H2, ilk yapilandirma
    baska = olaylar_kur([TB], yapilandirma=yapilandirma("H2", k=12))
    with pytest.raises(ValueError, match="demetine ait"):
        ornekleme.k1_adaylari(adaylar, baska, UFUK, config.BAR_4H)


def test_baska_hipotezin_olayi_reddedilir():
    adaylar = k1_adaylari_kur(BARLAR[:10])
    baska = olaylar_kur([TB], hipotez="H1")
    with pytest.raises(ValueError, match="demetine ait"):
        ornekleme.k1_adaylari(adaylar, baska, UFUK, config.BAR_4H)


def test_baska_kumenin_olayi_reddedilir():
    """§3: kumeler arasi veri odunc alinmaz."""
    adaylar = k1_adaylari_kur(BARLAR[:10])
    baska = olaylar_kur([T("2025-10-10 04:00")], kume="C2")
    with pytest.raises(ValueError, match="demetine ait"):
        ornekleme.k1_adaylari(adaylar, baska, UFUK, config.BAR_4H)


def test_k2_de_demet_eslesmesi_aranir():
    adaylar = k2_adaylari_kur(SEMBOLLER, t=TB)
    baska = olaylar_kur([TB], yapilandirma=yapilandirma("H2", k=6))
    with pytest.raises(ValueError, match="demetine ait"):
        ornekleme.k2_adaylari(adaylar, baska, olay_sembolu="ZZZUSDT")


# --- 3. K2: olay bari adaylarin bariyla ayni olmali -------------------------------------------


@pytest.mark.parametrize("kaydirma", [1, -1, 6, -24])
def test_k2_baska_barin_olayi_reddedilir(kaydirma):
    """On-kayit §6 K2: olcut "o anda olay uretmemis", yani AYNI t bari."""
    adaylar = k2_adaylari_kur(SEMBOLLER, t=TB)
    baska_bar = olaylar_kur([TB + kaydirma * H4], sembol="AAAUSDT")
    with pytest.raises(ValueError, match="olay bari"):
        ornekleme.k2_adaylari(adaylar, baska_bar, olay_sembolu="ZZZUSDT")


def test_k2_ayni_barin_olayi_elenir():
    adaylar = k2_adaylari_kur(SEMBOLLER, t=TB)
    ureten = olaylar_sembollerde(["BBBUSDT"], t=TB)
    sonuc = ornekleme.k2_adaylari(adaylar, ureten, olay_sembolu="AAAUSDT")
    assert sonuc.ogeler == ("CCCUSDT", "DDDUSDT")


def test_k2_bos_olay_kumesi_hicbir_sembolu_elemez():
    adaylar = k2_adaylari_kur(SEMBOLLER, t=TB)
    assert ornekleme.k2_adaylari(adaylar, [], olay_sembolu="ZZZUSDT").ogeler == tuple(SEMBOLLER)


def test_k2_bar_zamani_imzaya_girer():
    """`Adaylar.bar_zamani` imzanin parcasi: elle degistirilen aday kumesi reddedilir."""
    adaylar = k2_adaylari_kur(SEMBOLLER, t=TB)
    assert adaylar.bar_zamani == TB
    bozuk = dataclasses.replace(adaylar, bar_zamani=TB + H4)
    with pytest.raises(ValueError, match="elle kurulmus|degistirilmis"):
        ornekleme.aday_dogrula(bozuk)


def test_k1_adaylarinin_bar_zamani_yok():
    """K1'in adaylari zaten farkli barlardir; ortak bar zamani tanimsizdir."""
    assert k1_adaylari_kur(BARLAR[:5]).bar_zamani is None


# --- 4. K1: gercek olaylarla ayiklama ---------------------------------------------------------


def test_k1_olaylara_yakin_barlar_elenir():
    olaylar = olaylar_kur([BARLAR[0], BARLAR[40]])
    assert len(olaylar) == 2, "iki olay birincil ufuktan uzak secildi"
    kalan = ornekleme.k1_adaylari(k1_adaylari_kur(BARLAR), olaylar, UFUK, config.BAR_4H)
    beklenen = tuple(t for t in BARLAR
                     if all(abs((t - o.zaman) / H4) >= UFUK for o in olaylar))
    assert kalan.ogeler == beklenen
    assert len(kalan) < len(BARLAR)


def test_k1_bos_olay_listesi_hepsini_birakir():
    kalan = ornekleme.k1_adaylari(k1_adaylari_kur(BARLAR[:5]), [], UFUK, config.BAR_4H)
    assert tuple(kalan.ogeler) == tuple(BARLAR[:5])


def test_ayiklanan_kume_dogrudan_ornekelemeye_girer():
    olaylar = olaylar_kur([BARLAR[0]])
    kalan = ornekleme.k1_adaylari(k1_adaylari_kur(BARLAR), olaylar, UFUK, config.BAR_4H)
    havuz = ornekle(kalan)
    assert len(havuz) == min(config.KONTROL_SAYISI, len(kalan))
    assert set(havuz.secilenler) <= set(kalan.ogeler)


def test_olayin_kendi_sembolu_daraltilmaz():
    """BELIRSIZLIK: on-kayit K1'de "o hipotezin herhangi bir olayi" diyor, sembol kapsamini
    yazmiyor. Dogrulama bu yuzden baska coinin olayini REDDETMEZ; karar cagirana (F2'ye) kalir."""
    olaylar = olaylar_kur([BARLAR[0]], sembol="ZZZUSDT")
    kalan = ornekleme.k1_adaylari(k1_adaylari_kur(BARLAR, sembol="AAVEUSDT"), olaylar, UFUK,
                                  config.BAR_4H)
    assert len(kalan) < len(BARLAR)
