"""`KontrolHavuzu` imzalidir ve `olay_sayilari` ciftlerin kimligini dogrular (madde 3c; K-C6, sizinti 3).

Bulgu: havuz imzasiz bir `dataclass`ti. Elle kurulan havuz, `secilenler > aday_sayisi` olan havuz
ve `replace(havuz, tohum=...)` ile demetle tutarsiz hale getirilmis havuz `olay_sayilari`ndan
geciyordu. O sayi F2'nin aday esigi (150) ve F3'un guc esigi (100) demektir: sisirilmesi HUKMU
degistirir. Ayrica `olay_sayilari` ciftlerin HANGI OLAYA ait oldugunu denetlemiyordu, yani ayni
olayin iki kez sayilmasi ya da baska bir yapilandirmanin ciftinin karismasi esigi sessizce
gecirebiliyordu (K-C6).

Aga cikmaz; getiri hesaplanmaz.
"""

from __future__ import annotations

import dataclasses

import pandas as pd
import pytest

import config
from data import ornekleme
from dizi_yardimcisi import tek_olay
from ornekleme_yardimcisi import k1_adaylari_kur, k2_adaylari_kur
from sinyal_yardimcisi import yapilandirma

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
TB = T("2025-03-10 04:00")
BARLAR = [T("2025-03-01") + i * H4 for i in range(30)]


def _cift(i=0, *, k1_n=12, k2_n=12, hipotez="H2", yapilandirmasi=None, kume="KESIF"):
    y = yapilandirmasi if yapilandirmasi is not None else yapilandirma(hipotez)
    t = TB + i * H4
    olay = tek_olay(t, hipotez=hipotez, yapilandirma=y, kume=kume, sembol="AAVEUSDT")
    k1 = ornekleme.ornekle(k1_adaylari_kur(BARLAR[:k1_n], hipotez=hipotez, yapilandirma=y,
                                           kume=kume, sembol="AAVEUSDT"), olay=olay)
    k2 = ornekleme.ornekle(k2_adaylari_kur([f"S{j:02d}USDT" for j in range(k2_n)], t=t,
                                           hipotez=hipotez, yapilandirma=y, kume=kume), olay=olay)
    return k1, k2


# --- 1. Gercek havuz gecer (olumlu kontrol) --------------------------------------------------


def test_gercek_cift_gecer():
    k1, k2 = _cift()
    sayilar = ornekleme.olay_sayilari([(k1, k2)])
    assert (sayilar.olusmus, sayilar.analize_giren) == (1, 1)
    assert ornekleme.havuz_dogrula(k1) is k1 and ornekleme.havuz_dogrula(k2) is k2
    assert (k1.rol, k2.rol) == ("K1", "K2")


def test_cok_olayli_dizi_gecer():
    ciftler = [_cift(i) for i in range(5)]
    assert ornekleme.olay_sayilari(ciftler).olusmus == 5


# --- 2. Elle kurulmus ya da degistirilmis havuz reddedilir -----------------------------------


@pytest.mark.parametrize("sahte", [
    ornekleme.KontrolHavuzu(("SAHTE",), 1),
    ornekleme.KontrolHavuzu(tuple(f"S{i}" for i in range(12)), 3),        # secilen > aday sayisi
    ornekleme.KontrolHavuzu(("A",), 1, tohum=1, alt_tohum_demeti=("a", "b", "c", "d"),
                            genel_tohum=7, rol="K1"),
    ornekleme.KontrolHavuzu((), 0, rol="K1"),
])
def test_elle_kurulmus_havuz_reddedilir(sahte):
    with pytest.raises((TypeError, ValueError)):
        ornekleme.havuz_dogrula(sahte)


def test_elle_kurulmus_havuz_olay_sayisini_sisiremez():
    """Bulgunun kendisi: sahte havuz bir olayi 'analize girdi' yapabiliyordu."""
    _, k2 = _cift()
    sahte = ornekleme.KontrolHavuzu(("SAHTE",), 1, rol="K1")
    with pytest.raises((TypeError, ValueError)):
        ornekleme.olay_sayilari([(sahte, k2)])


@pytest.mark.parametrize("alan,deger", [("tohum", 1), ("aday_sayisi", 99), ("genel_tohum", 7),
                                        ("alt_tohum_demeti", ("a", "b", "c", "d")),
                                        ("secilenler", ("X",)), ("rol", "K2")])
def test_replace_ile_degistirilmis_havuz_reddedilir(alan, deger):
    k1, k2 = _cift()
    bozuk = dataclasses.replace(k1, **{alan: deger})
    with pytest.raises((TypeError, ValueError)):
        ornekleme.havuz_dogrula(bozuk)
    with pytest.raises((TypeError, ValueError)):
        ornekleme.olay_sayilari([(bozuk, k2)])


def test_imza_alani_elle_yazilamaz():
    """`_imza` alanini dogru degere getirmek, alanlardan yeniden hesaplanan imzayi atlatmaz."""
    k1, _ = _cift()
    bozuk = dataclasses.replace(k1, aday_sayisi=k1.aday_sayisi + 5)
    with pytest.raises(ValueError, match="elle kurulmus"):
        ornekleme.havuz_dogrula(bozuk)


# --- 3. Ciftin kimligi (K-C6) ----------------------------------------------------------------


def test_cift_ayni_olaya_ait_olmali():
    k1, _ = _cift(0)
    _, k2 = _cift(3)
    with pytest.raises(ValueError, match="ayni olayin havuzu"):
        ornekleme.olay_sayilari([(k1, k2)])


def test_ayni_olay_iki_kez_sayilamaz():
    """Bulgunun zararli yolu: tekrarlanan cift aday esigini (150) sessizce gecirirdi."""
    cift = _cift(0)
    with pytest.raises(ValueError, match="iki kez sayilamaz"):
        ornekleme.olay_sayilari([cift, cift])
    with pytest.raises(ValueError, match="iki kez sayilamaz"):
        ornekleme.olay_sayilari([_cift(1), _cift(2), _cift(1)])


def test_baska_yapilandirmanin_cifti_karisamaz():
    ciftler = [_cift(0), _cift(1, yapilandirmasi=yapilandirma("H2", k=12))]
    with pytest.raises(ValueError, match="ayni \\(yapilandirma, kume\\)"):
        ornekleme.olay_sayilari(ciftler)


def test_roller_k1_k2_sirasinda_olmali():
    k1, k2 = _cift()
    with pytest.raises(ValueError, match="sirasinda olmali"):
        ornekleme.olay_sayilari([(k2, k1)])


def test_bos_havuzlu_cift_de_dogrulanir():
    """Bos havuz da imzali ve kimlikli: 'analize girmeyen olay' yine sayilir (§8 madde 1)."""
    k1, k2 = _cift(k1_n=0, k2_n=0)
    sayilar = ornekleme.olay_sayilari([(k1, k2)])
    assert (sayilar.olusmus, sayilar.analize_giren) == (1, 0)
    assert k1.genel_tohum == config.TOHUM and k2.genel_tohum == config.TOHUM
