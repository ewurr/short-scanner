"""F1 kapatma turu madde 1d / P-C3: `olay_dizisi`nin donem ve kume denetimi.

Bulgu neydi: `olay_dizisi` dizinin kimligini (sembol, kume, donem_no) argüman olarak aliyor ama
`zamanlar`in o donemin ve kumenin icinde oldugunu DOGRULAMIYORDU. Donem disi bir barda kosul
`False` dondugunde bar kapiya hic gitmez (yani `pozisyon`un donem denetimi devreye girmez), ama
bar dizi DURUMUNU degistirir: H1'de yuruyen izlemenin pump bari, H3'te kesintisiz dizi. Sonuc
olay kumesini kaydirir -- on-kayit §5 rev.12 madde (a): "Izleme penceresi donem ve kume icinde
kalir; bir olayin dayandigi butun barlar ayni donem ve kumede olmalidir."

Burada `dizi.olay_dizisi` DOGRUDAN cagrilir (sinirlari turetmeyen yol); dizi kurallarini sinayan
testler `tests/dizi_cagri.cagir` uzerinden gecer. Aga cikmaz.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import dizi, pencere, pozisyon, sinyal, split

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
UFUK4 = config.BIRINCIL_UFUK[config.BAR_4H]
UFUK1D = config.BIRINCIL_UFUK[config.BAR_1D]

KIMLIK = dict(sembol="TESTONAYUSDT", kume="KESIF", donem_no=0)


def _kapi(hipotez, yapilandirma=None):
    def karar(t, capa):
        return pozisyon._test_onayi(
            hipotez=hipotez,
            yapilandirma=dict(sinyal.izgara(hipotez)[0]) if yapilandirma is None else yapilandirma,
            t=t, capa=capa, **KIMLIK)

    return karar


def _cagir(zamanlar, *, bar=config.BAR_4H, hipotez="H2", donem_baslangic, donem_bitis, kume="KESIF"):
    y = dict(sinyal.izgara(hipotez)[0])
    kimlik = dict(KIMLIK, kume=kume)
    return dizi.olay_dizisi(hipotez, y, zamanlar, bar,
                            birincil_ufuk=config.BIRINCIL_UFUK[bar],
                            kosul=lambda t, capa: True, karar=_kapi(hipotez, y),
                            donem_baslangic=donem_baslangic, donem_bitis=donem_bitis, **kimlik)


# --- 1. Donem sinirlari zorunludur ------------------------------------------------------------


def test_donem_sinirlari_zorunlu_argümandir():
    """Dayanak: P-C3. Sinirsiz cagri `TypeError`; sessizce "butun barlar donem ici" varsayilmaz."""
    z = pd.date_range(T("2025-03-01"), periods=3, freq="4h")
    with pytest.raises(TypeError):
        dizi.olay_dizisi("H2", dict(sinyal.izgara("H2")[0]), z, config.BAR_4H,
                         birincil_ufuk=UFUK4, kosul=lambda t, c: True, karar=_kapi("H2"), **KIMLIK)


def test_ters_donem_sinirlari_reddedilir():
    z = pd.date_range(T("2025-03-01"), periods=3, freq="4h")
    with pytest.raises(ValueError):
        _cagir(z, donem_baslangic=z[-1], donem_bitis=z[0])


# --- 2. Donem disi bar ------------------------------------------------------------------------


def test_donem_bitisinden_sonraki_bar_reddedilir():
    """Dayanak: on-kayit §2 "Donem disindaki hicbir bar ... hicbir hesaba girmez"."""
    z = pd.date_range(T("2025-03-01"), periods=6, freq="4h")
    with pytest.raises(pencere.DonemDisiSinyal):
        _cagir(z, donem_baslangic=z[0], donem_bitis=z[-2])


def test_donem_basindan_onceki_bar_reddedilir():
    z = pd.date_range(T("2025-03-01"), periods=6, freq="4h")
    with pytest.raises(pencere.DonemDisiSinyal):
        _cagir(z, donem_baslangic=z[1], donem_bitis=z[-1])


def test_donem_ici_dizi_gecer():
    """Olumlu kontrol: sinirlar barlari kapsiyorsa dizi normal isler."""
    z = pd.date_range(T("2025-03-01"), periods=40, freq="4h")
    sonuc = _cagir(z, donem_baslangic=z[0], donem_bitis=z[-1])
    assert len(sonuc.olaylar) == 3          # 40 bar / 19 bar aralik (18 bekleme + 1)
    assert sonuc.olaylar[0].zaman == z[0]


def test_bos_dizi_sinirlarla_da_gecer():
    z = pd.DatetimeIndex([])
    assert _cagir(z, donem_baslangic=T("2025-03-01"), donem_bitis=T("2025-03-02")).olaylar == ()


# --- 3. 1d izgarasinda gunun tamami donem ici olmali -------------------------------------------


def test_gunluk_barda_gunun_son_4h_bari_donem_disiysa_reddedilir():
    """Dayanak: on-kayit §6 rev.8 "Donem uyeligi": 1d barda gunun ALTI 4h barinin tamami donem ici."""
    g = pd.date_range(T("2025-03-01"), periods=3, freq="1d")
    with pytest.raises(pencere.DonemDisiSinyal):
        _cagir(g, bar=config.BAR_1D, hipotez="H3", donem_baslangic=g[0], donem_bitis=g[-1])


def test_gunluk_barda_tam_gun_donem_icindeyse_gecer():
    g = pd.date_range(T("2025-03-01"), periods=3, freq="1d")
    sonuc = _cagir(g, bar=config.BAR_1D, hipotez="H3", donem_baslangic=g[0],
                   donem_bitis=g[-1] + pencere.GUNUN_SON_4H_BARI)
    assert len(sonuc.olaylar) == 1          # H3'te yalnizca kesintisiz dizinin ILK gunu


# --- 4. Kume araligi --------------------------------------------------------------------------


def test_kume_disindaki_bar_reddedilir():
    """Dayanak: on-kayit §3. KESIF 2025-08-31'de biter; C2 tarihli bar KESIF dizisine giremez."""
    z = pd.date_range(T("2025-08-31 12:00"), periods=6, freq="4h")   # 2025-09-01'e tasar
    with pytest.raises(pencere.DonemDisiSinyal):
        _cagir(z, donem_baslangic=z[0], donem_bitis=z[-1])


def test_kume_araligi_kume_adindan_okunur():
    """Dayanak: P-C3. Cagiran kume sinirini vermez; arlik kume ADINDAN gelir."""
    bas, son = pozisyon.kume_sinirlari("KESIF")
    assert (bas, son) == split.kume_araligi("KESIF")
    assert son < pd.Timestamp(config.C2_BASI)


# --- 5. Dizi durumu: reddedilen bar durumu kaydirmaz -------------------------------------------


def test_donem_disi_bar_h3_dizisini_kaydirmaz():
    """Dayanak: P-C3'un gerekcesi. Donem disi bir gun "ilk gun"u kaydirabiliyordu; artik cagri hata verir.

    Kurgu: 2 gunluk donem + oncesinde donem disi bir gun. Donem disi gun dizide olsaydi dizi onunla
    baslayip olayi bir gun KAYDIRIRDI; simdi cagri reddedilir, yani F2 donem disi bar veremez.
    """
    g = pd.date_range(T("2025-03-01"), periods=3, freq="1d")
    donem = dict(donem_baslangic=g[1], donem_bitis=g[-1] + pencere.GUNUN_SON_4H_BARI)
    with pytest.raises(pencere.DonemDisiSinyal):
        _cagir(g, bar=config.BAR_1D, hipotez="H3", **donem)
    # Yalnizca donem ici gunlerle cagri: ilk olay donemin ILK gunudur.
    sonuc = _cagir(g[1:], bar=config.BAR_1D, hipotez="H3", **donem)
    assert [o.zaman for o in sonuc.olaylar] == [g[1]]
