"""H1 izleme penceresinin donem ve kume siniri, takvimle (on-kayit §5 H1 madde 4, rev.13 (a)).

On-kayit §5 H1 madde 4 (rev.13): "Izleme penceresi donemin ve kumenin icinde kalmalidir: izleme
yalnizca donem ici ve kume ici barlar uzerinde yurur, bu barlar arasinda teyit gelmezse izleme
olay uretmeden kapanir. Donemin ya da kumenin sonuna 12 bardan az kalmisken baslayan bir pump
bari, bu yuzden hic olay uretmeyebilir. Gerekce: §2 donem disindaki hicbir barin hesaba
girmemesini, §3 kumeler arasi veri odunc alinmamasini sart kosuyor; kesif kumesindeki bir pump
barinin teyidini onay verisinde aramak bu iki kurali birlikte delerdi. Ayni kural bir olayin
dayandigi butun barlar icin gecerlidir."

Kural iki parcadan gelir:
  (1) `dizi.olay_dizisi`in `zamanlar` argumani SOZLESME geregi yalnizca DONEM ICI ve KUME ICI
      sinyal barlarini tasir; izleme bu barlarin disina cikamaz.
  (2) 12 barlik sinir TAKVIMLE olculur, barlarin varligiyla degil (sizinti bulgusu S-B3): teyit
      araligi `(pump, pump + 12 x adim]`dir. Rev.13'ten once sinir yalnizca islenen barlara
      bagliydi ve `zamanlar`da 12. bar yoksa 13. bar hala teyit adayi sayiliyordu.

Aga cikmaz; getiri ve sinyal degeri hesaplanmaz (kosul ve karar sahte cagrilabilirlerdir).
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import dizi, pozisyon

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
UFUK = config.BIRINCIL_UFUK[config.BAR_4H]
IZLEME = config.H1_IZLEME_BAR            # 12
# Her adayi onaylayan kapi: SORULAN (t, capa) ciftine ait IMZALI onay. `dizi.olay_dizisi`
# donen onayi dogruladigi icin (sizinti bulgusu S-B1) ham bir nesne olay sayilmaz;
# `pozisyon._test_onayi` veri yuklemeden imzali bir onay kurar (yalnizca pytest icinde).
DIZI_KIMLIGI = dict(sembol="TESTONAYUSDT", kume="KESIF", donem_no=0)

def _onay(t, capa=None):
    return pozisyon._test_onayi(hipotez="H1", yapilandirma=dict(theta=0.20, delta=0.08), t=t, capa=capa)

# Donem ici 4h izgarasi (yeterince uzun); testler bundan DILIM secerek donem/kume sonunu taklit eder.
IZGARA = pd.date_range(T("2025-03-01 00:00"), periods=120, freq="4h")


def _kosul(pumplar, teyitler):
    """Sahte H1 kosulu: `capa=None` pump, `capa=p` p capali teyit. Cagrilari kaydeder."""
    cagrilar = []

    def kosul(t, capa):
        i = int(IZGARA.get_loc(t))
        c = None if capa is None else int(IZGARA.get_loc(capa))
        cagrilar.append((i, c))
        return i in pumplar if c is None else i in teyitler.get(c, set())

    return kosul, cagrilar


def _calistir(idxler, kosul):
    return dizi.olay_dizisi("H1", dict(theta=0.20, delta=0.08), IZGARA[list(idxler)], config.BAR_4H,
                            birincil_ufuk=UFUK, kosul=kosul, karar=_onay, **DIZI_KIMLIGI)


def _idx(sonuc):
    return [int(IZGARA.get_loc(z)) for z in sonuc.olay_zamanlari]


def _capalar(sonuc):
    return [int(IZGARA.get_loc(o.capa)) for o in sonuc.olaylar]


# --- 1. Sinir takvimde: 12. bar yoksa 13. bar teyit adayi DEGILDIR ---------------------------


def test_eksik_12_bar_sonrasi_13_bar_teyit_adayi_degil():
    """Bitisik seride teyit araligi `(0, 12]`; 13 disindadir. 12. bar seride olmasa bile 13.
    bar araligin disinda kalir: izleme takvimde kapanmistir."""
    kosul, cagrilar = _kosul({0}, {0: {13}})
    sonuc = _calistir(list(range(12)) + [13, 14], kosul)
    assert sonuc.olaylar == ()
    assert (13, 0) not in cagrilar, "13. bar pump capali teyit olarak sorulmamali"


def test_uzun_bosluktan_sonraki_bar_izlemenin_parcasi_degil_yeni_pump_olabilir():
    """Izleme takvimde (0, 12]'de kapandi; 20. bar izlemenin parcasi DEGILDIR, bu yuzden yeni bir
    pump bari olarak degerlendirilir ve kendi teyidini (23) olay yapar."""
    kosul, cagrilar = _kosul({0, 20}, {0: set(), 20: {23}})
    sonuc = _calistir([0, 1, 20, 21, 22, 23], kosul)
    assert _idx(sonuc) == [23] and _capalar(sonuc) == [20]
    assert (20, None) in cagrilar, "20. bar pump kosuluna sorulmali"


# --- 2. Sinirin kenari: 12 dahil, 13 haric; sinira denk gelen bar izlemenin parcasi ----------


@pytest.mark.parametrize("teyit,olay_var", [(IZLEME, True), (IZLEME + 1, False)])
def test_teyit_araligi_ust_uc_dahil(teyit, olay_var):
    """`(pump, pump + 12 x adim]`: 12. bar teyit adayi, 13. bar degil (bitisik seride de)."""
    kosul, _ = _kosul({0}, {0: {teyit}})
    sonuc = _calistir(range(20), kosul)
    assert (_idx(sonuc) == [teyit]) is olay_var


def test_sinira_denk_gelen_bar_yeni_pump_sayilmaz():
    """Rev.12 (b): "Izlemeyi bitiren bar o izlemenin parcasidir ve yeni bir pump bari olarak
    degerlendirilmez; en erken yeni pump bari, izlemenin bittigi bardan sonraki bardir."
    12. bar pump kosulunu saglasa bile yeni izleme baslatmaz; 13. bar baslatir."""
    kosul, cagrilar = _kosul({0, IZLEME, IZLEME + 1}, {0: set(), IZLEME + 1: {IZLEME + 4}})
    sonuc = _calistir(range(25), kosul)
    assert _idx(sonuc) == [IZLEME + 4] and _capalar(sonuc) == [IZLEME + 1]
    assert (IZLEME, None) not in cagrilar, "12. bar izlemenin parcasi; pump kosuluna sorulmaz"


# --- 3. Donem ve kume sonu: 12 bardan az kalmissa olay olusmaz -------------------------------


def test_donem_sonuna_12_bardan_az_kalmissa_pump_olay_uretmez():
    """`zamanlar` yalnizca DONEM ICI barlari tasir (sozlesme). Pump barindan sonra donem icinde 11
    bar var ve teyit gelmiyor: izleme olay uretmeden kapanir. Teyidin donem DISINDA (12. barda)
    gelecek olmasi bir sey degistirmez -- o bar hicbir hesaba girmez (on-kayit §2)."""
    pump = 100
    donem_ici = list(range(pump, pump + 12))      # pump + 11 bara kadar; 12. bar donem disi
    kosul, cagrilar = _kosul({pump}, {pump: {pump + IZLEME}})
    assert _calistir(donem_ici, kosul).olaylar == ()
    # Teyit barinin kendisi hic sorulmadi: donem icinde yok.
    assert all(i != pump + IZLEME for i, _ in cagrilar)
    # Karsi-ornek: donem bir bar daha surerse (12. bar donem ici) ayni pump olay uretir.
    assert _idx(_calistir(donem_ici + [pump + IZLEME], kosul)) == [pump + IZLEME]


def test_kume_sonuna_12_bardan_az_kalmissa_pump_olay_uretmez():
    """Ayni kural kume sonu icin (on-kayit §3: "kumeler arasi veri odunc alinmaz"). Kesif
    kumesinin son barindan 11 bar once baslayan pump, teyidini onay verisinde ARAYAMAZ."""
    kume_sonu = 119                               # `zamanlar`in son bari = kumenin son bari
    pump = kume_sonu - 11
    kosul, cagrilar = _kosul({pump}, {pump: {pump + IZLEME}})
    assert _calistir(range(pump, kume_sonu + 1), kosul).olaylar == ()
    assert all(c != pump or i <= kume_sonu for i, c in cagrilar)


def test_donem_sonuna_tam_12_bar_kalmissa_olay_olusur_sinir_durumu():
    """Sinirin diger yani: donem icinde pumptan sonra TAM 12 bar varsa teyit gelebilir."""
    pump = 100
    kosul, _ = _kosul({pump}, {pump: {pump + IZLEME}})
    assert _idx(_calistir(range(pump, pump + IZLEME + 1), kosul)) == [pump + IZLEME]


def test_izleme_donem_sonunda_kapanir_sonraki_cagri_yeni_donemdir():
    """Donem basina ayri cagri yapilir (modul sozlesmesi): bir donemde yarim kalan izleme sonraki
    donemin cagrisina TASINMAZ. Iki cagri da olay uretmez; ikinci cagrinin ilk bari kendi pump
    kosuluna sorulur."""
    kosul1, _ = _kosul({0}, {0: {20}})
    assert _calistir(range(0, 6), kosul1).olaylar == ()
    kosul2, cagrilar2 = _kosul({0}, {0: {20}})
    assert _calistir(range(20, 26), kosul2).olaylar == ()
    assert (20, None) in cagrilar2 and all(c is None for _, c in cagrilar2)
