"""Sizinti testcisi: olay/kontrol kimligi, KILIT.md dogrulamasi, bar duzeyli olcut, tohum, hook deseni.

BU DOSYA TEK YENI DOSYADIR; mevcut hicbir test ya da yardimci dosyaya dokunulmadi.

Amac KODU KIRMAKTIR. `acik(...)` ile isaretli testler basarili bir saldiridir: kodda gercek bir acik
vardir ve test `xfail(strict=True)` olarak beklenen basarisizliktir (`raises=AssertionError`: kurulum
hatasi ya da baska bir istisna xfail sayilmaz, gercek hata olarak gorunur). Acik KAPATILIRSA test
XPASS(strict) ile KIRMIZI olur; o zaman isaret kaldirilmalidir. Normal testler savusturulan saldirilardir.

BASLIK -> TESTLER
  1. Olay/kontrol kimligi
     1a adaylari_kur: test_k1_*, test_k2_*, test_rol_*, test_karisik_*, test_degistirilmis_onay_*,
        test_ham_*_adaylari_kurulamaz, test_k1_yakin_zamanli_tekrar_aday_xfail (acik)
     1b k1_adaylari / k2_adaylari / ornekle: test_k1_adaylari_*, test_k2_*, test_adaylar_*,
        test_ornekle_* (acik: olay kimligi adaylarla capraz dogrulanmiyor), test_elle_kurulmus_kontrol_havuzu_*
        (acik: KontrolHavuzu imzali degil)
     1c dizi.olay_dogrula: test_olay_*, test_tutarsiz_olay_* (acik)
     1d pozisyon._test_onayi omru ve onay kosusu: test_omur_*, test_onay_kumesi_dikisi_*
  2. KILIT.md: test_kilit_*, test_ekleme_kurali_* (git gecmisi; acik: --full-history yok, yerel yeniden yazim)
  3. Bar duzeyli olcut: test_bar_duzeyi_*
  4. Tohum degismezligi: test_sabit_*
  5. Havuz alt tohumu: test_havuz_tohumu_*, test_alt_tohum_*
  6. Hook deseni: test_hook_*

NOT: Bu dosya yazilirken testler KOSTURULAMADI (yazan ajanin calistirma araci yoktu). `xfail` isaretleri kod
okumasina dayanir; bir `XPASS(strict)` ya da beklenmedik `FAILED`, isaretin ya da testin yanlis oldugunu
gosterir ve ilk is olarak incelenmelidir.

Aga cikmaz; getiri hesaplanmaz; gercek depodaki kilitli dosyalara dokunulmaz (hook yalnizca METIN olarak
degerlendirilir, komutlar CALISTIRILMAZ; git testleri gecici depoda calisir).
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import io
import json
import pathlib
import sys
import types

import numpy as np
import pandas as pd
import pytest

import config
from data import dizi, klines, ornekleme, pencere, pozisyon, sinyal, split
from dizi_yardimcisi import olaylar_kur, olaylar_sembollerde, tek_olay
from kapi_yardimcisi import veri
from onay_yardimcisi import gecici_depo, gecici_kayit, git, kilit_metni, kilit_yaz, kosu
from sinyal_yardimcisi import kontrol
from sinyal_yardimcisi import yapilandirma as yap_ilk
from uygunluk_yardimcisi import UYGUN_ONCELIK, esikler

KOK = pathlib.Path(__file__).resolve().parents[1]
T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
UFUK = config.BIRINCIL_UFUK[config.BAR_4H]
BAS = T("2025-03-01")
TB = T("2025-03-10 04:00")
TC2 = T("2025-10-10 04:00")
Y2 = yap_ilk("H2")


def _elenmis(adaylar, olaylar=()):
    """`ornekle` yalnizca AYIKLANMIS kume kabul eder (bulgu P-B2): gercek ayiklayiciyi cagirir.

    Varsayilan olay kumesi bos: ayiklayici kosar ama hicbir aday dusmez, yani testin sinadigi sey
    (ornekleme kurallari, kimlik denetimi, imza) degismez. Ayiklamanin KENDISI ayri testlerde
    sinanir."""
    if not isinstance(adaylar, ornekleme.Adaylar) or adaylar.elendi:
        return adaylar          # ham girdi ve imza saldirilari DOGRUDAN `ornekle`ye gider
    bar = config.HIPOTEZ_IZGARASI[adaylar.hipotez]
    if adaylar.rol == "K1":
        return ornekleme.k1_adaylari(adaylar, olaylar, config.BIRINCIL_UFUK[bar], bar)
    sembol = olaylar[0].pozisyon.sembol if olaylar else "OLAYSEMBOLUYOK"
    return ornekleme.k2_adaylari(adaylar, olaylar, olay_sembolu=sembol)

def _bar(i: int) -> pd.Timestamp:
    return BAS + i * H4


def _acik(mesaj: str):
    """Saldiri basarili: AssertionError (xfail(raises=AssertionError) bunu bekler)."""
    raise AssertionError(f"SALDIRI BASARILI: {mesaj}")


def acik(neden: str):
    """Bulunan acigin isareti: strict xfail; yalnizca AssertionError beklenen basarisizliktir."""
    return pytest.mark.xfail(strict=True, raises=AssertionError, reason=neden)


def _onay(rol, t, *, hipotez="H2", sembol="AAVEUSDT", donem_no=0, kume="KESIF", y=None):
    """`pozisyon._test_onayi` ile imzali onay (veri yuklenmez; yalnizca pytest icinde)."""
    y = dict(sinyal.izgara(hipotez)[0]) if y is None else y
    return pozisyon._test_onayi(hipotez=hipotez, yapilandirma=y, t=t, rol=rol, sembol=sembol, kume=kume,
                                donem_no=donem_no)


def _k1_kur(barlar, **ek) -> ornekleme.Adaylar:
    hipotez = ek.get("hipotez", "H2")
    kimlik = dict(hipotez=hipotez, yapilandirma=ek.get("y") or dict(sinyal.izgara(hipotez)[0]),
                  kume=ek.get("kume", "KESIF"), sembol=ek.get("sembol", "AAVEUSDT"),
                  donem_no=ek.get("donem_no", 0))
    return ornekleme.adaylari_kur([_onay("K1", t, **ek) for t in barlar], rol="K1", **kimlik)


def _k2_kur(semboller, t, **ek) -> ornekleme.Adaylar:
    hipotez = ek.get("hipotez", "H2")
    kimlik = dict(hipotez=hipotez, yapilandirma=ek.get("y") or dict(sinyal.izgara(hipotez)[0]),
                  kume=ek.get("kume", "KESIF"), bar_zamani=t)
    return ornekleme.adaylari_kur([_onay("K2", t, sembol=s, **ek) for s in semboller], rol="K2",
                                  **kimlik)


def _olay(sembol="AAVEUSDT", t=None, **ek) -> dizi.Olay:
    """Ornekelemenin olayi (madde 3b: `ornekle` olayin KENDISINI alir).

    Varsayilan bar `_bar(100)`: aday barlarindan uzak, cunku olayin kendi bari K1 adayi olamaz.
    """
    return tek_olay(_bar(100) if t is None else t, hipotez=ek.pop("hipotez", "H2"),
                    yapilandirma=ek.pop("yapilandirma", Y2), kume=ek.pop("kume", "KESIF"),
                    sembol=sembol, **ek)


@pytest.fixture
def kayit(tmp_path):
    """Sahte git kipinde gecici onay kaydi + kilit kokleri (tests/test_kimlik_test_dikisi.py ile ayni desen)."""
    yol = tmp_path / "onay_gecici.md"
    yol.write_text("bas\n", encoding="utf-8")
    gecici_kayit(yol)
    return yol


# =================================================================================================
# 1a. adaylari_kur: K1 ayni sembol VE ayni donem; K2 ayni t; rol ve demet karisimi
# =================================================================================================


def test_k1_karisik_sembol_demeti_adaylari_kurulamaz():
    """On-kayit §6 K1: "ayni coinden". Iki sembolun K1 onayi tek aday kumesine girmez."""
    onaylar = [_onay("K1", _bar(0), sembol="AAAUSDT"), _onay("K1", _bar(1), sembol="BBBUSDT")]
    with pytest.raises(ValueError, match="ayni coinden"):
        ornekleme.adaylari_kur(onaylar, rol="K1")


def test_k1_karisik_donem_demeti_adaylari_kurulamaz():
    """On-kayit §6 K1: "ayni coinden, ayni kume ve donem icinden" (D-B1): ayni sembol, iki donem."""
    onaylar = [_onay("K1", _bar(0), donem_no=0), _onay("K1", _bar(1), donem_no=1)]
    with pytest.raises(ValueError, match="ayni donem"):
        ornekleme.adaylari_kur(onaylar, rol="K1")


def test_k1_donem_karisimi_siralamaya_bagli_degil():
    """Karisik donem, listenin neresine konursa konsun yakalanir (ilk/orta/son)."""
    for donemler in ((1, 0, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1), (2, 1, 0, 3)):
        onaylar = [_onay("K1", _bar(i), donem_no=d) for i, d in enumerate(donemler)]
        with pytest.raises(ValueError, match="ayni donem"):
            ornekleme.adaylari_kur(onaylar, rol="K1")


def test_k1_ayni_bar_iki_kez_aday_olamaz():
    """§6 rev.11: ornekleme IADESIZDIR; ayni bar iki kez aday olamaz."""
    onaylar = [_onay("K1", _bar(0)), _onay("K1", _bar(1)), _onay("K1", _bar(0))]
    with pytest.raises(ValueError, match="tekrarsiz"):
        ornekleme.adaylari_kur(onaylar, rol="K1")


def test_k1_yakin_zamanli_tekrar_aday_xfail():
    """On-kayit §4 'Zaman toleransi' + §6 iadesiz ornekleme. Kapi (`olay_karari`) t+30sn'yi AYNI bar sayip
    kabul eder (`ayni_andaki_bar`), ama `adaylari_kur` yalniz `has_duplicates` ile tekrar arar."""
    onaylar = [_onay("K1", _bar(0)), _onay("K1", _bar(0) + pd.Timedelta(seconds=30)), _onay("K1", _bar(1))]
    try:
        ornekleme.adaylari_kur(onaylar, rol="K1")
    except ValueError:
        return
    _acik("T ve T+30sn K1'de iki ayri aday sayildi (ayni bar).")


def test_k2_karisik_bar_demeti_adaylari_kurulamaz():
    """§6 K2: "ayni t barinda". Farkli barlarin K2 onaylari tek kumeye girmez."""
    onaylar = [_onay("K2", _bar(0), sembol="AAAUSDT"), _onay("K2", _bar(1), sembol="BBBUSDT")]
    with pytest.raises(ValueError, match="ayni t barindan"):
        ornekleme.adaylari_kur(onaylar, rol="K2")


def test_k2_tekrarli_sembol_aday_olamaz():
    """Iadesiz ornekleme: ayni coin ayni barda iki kez K2 adayi olamaz."""
    onaylar = [_onay("K2", _bar(0), sembol="AAAUSDT"), _onay("K2", _bar(0), sembol="AAAUSDT")]
    with pytest.raises(ValueError, match="tekrar"):
        ornekleme.adaylari_kur(onaylar, rol="K2")


@pytest.mark.parametrize("onay_rolu,istenen", [("K1", "K2"), ("K2", "K1"), ("olay", "K1"), ("olay", "K2")])
def test_rol_karisimi_adaylari_kurulamaz(onay_rolu, istenen):
    """§6 rev.11 'Kontrolun ne olctugu': olay ve kontrol rolleri ayridir; K1 onayi K2 havuzuna girmez."""
    with pytest.raises(ValueError, match="rolunde kapidan gecmis"):
        ornekleme.adaylari_kur([_onay(onay_rolu, _bar(0))], rol=istenen)


def test_rol_karisik_liste_adaylari_kurulamaz():
    """Listenin ortasindaki tek yanlis rol de yakalanir."""
    onaylar = [_onay("K1", _bar(0)), _onay("K1", _bar(1)), _onay("olay", _bar(2)), _onay("K1", _bar(3))]
    with pytest.raises(ValueError, match="rolunde kapidan gecmis"):
        ornekleme.adaylari_kur(onaylar, rol="K1")


@pytest.mark.parametrize("rol", ["olay", "K3", "k1", "", None, 1])
def test_adaylari_kur_gecersiz_rol_reddedilir(rol):
    with pytest.raises((ValueError, TypeError)):
        ornekleme.adaylari_kur([], rol=rol)


def test_karisik_hipotez_ve_yapilandirma_adaylari_kurulamaz():
    """§5/§6 rev.11: havuzlar yapilandirma basinadir; hipotez ya da yapilandirma karisimi reddedilir."""
    with pytest.raises(ValueError, match="butun adaylar ayni"):
        ornekleme.adaylari_kur([_onay("K1", _bar(0), hipotez="H2"), _onay("K1", _bar(1), hipotez="H1")], rol="K1")
    y1 = dict(sinyal.izgara("H2")[1])
    with pytest.raises(ValueError, match="butun adaylar ayni"):
        ornekleme.adaylari_kur([_onay("K1", _bar(0)), _onay("K1", _bar(1), y=y1)], rol="K1")
    with pytest.raises(ValueError, match="butun adaylar ayni"):
        ornekleme.adaylari_kur([_onay("K2", _bar(0), sembol="A", hipotez="H2"),
                                _onay("K2", _bar(0), sembol="B", hipotez="H1")], rol="K2")


@pytest.mark.parametrize("alan,deger", [("p0", 2.0), ("p1", 0.5), ("funding_toplami", 0.01), ("sembol", "ZZZUSDT"),
                                        ("donem_no", 7), ("rol", "K2"), ("hipotez", "H1"), ("kume", "C1"),
                                        ("gecersizlik_seviyesi", 1.0), ("ritim_sinifi", "4"),
                                        ("kuyruk_kismi", True), ("tek_ritim", True),
                                        ("yapilandirma", "H2:phi=0.0005,k=6")])
def test_degistirilmis_onay_adaylara_giremez(alan, deger):
    """`dataclasses.replace` `_imza` alanini oldugu gibi kopyalar; `onay_dogrula` imzayi ALANLARDAN yeniden
    hesaplar. Hicbir alan imza disinda kalmamali (§4 'tek karar noktasi')."""
    onay = _onay("K1", _bar(0))
    bozuk = dataclasses.replace(onay, **{alan: deger})
    with pytest.raises(ValueError, match="elle kurulmus|degistirilmis"):
        ornekleme.adaylari_kur([bozuk], rol="K1")


@pytest.mark.parametrize("ham", [_bar(0), "AAVEUSDT", 1.0, None, object(), pd.DatetimeIndex([_bar(0)])])
def test_ham_oge_adaylari_kurulamaz(ham):
    """§6 rev.13: ham bar damgasi / sembol adi aday DEGILDIR."""
    with pytest.raises((TypeError, ValueError)):
        ornekleme.adaylari_kur([ham], rol="K1")


# =================================================================================================
# 1b. k1_adaylari / k2_adaylari / ornekle
# =================================================================================================


def test_k1_adaylari_ufuk_siniri_tam_ufukta_yakin_sayilmaz():
    """§6 K1: "birincil ufuk mesafesinden yakin olmayan". Tam 18 bar uzaktaki bar KALIR; 17 bar uzaktaki ELENIR."""
    olay = tek_olay(_bar(30))
    adaylar = _k1_kur([_bar(i) for i in range(0, 61)])
    kalan = ornekleme.k1_adaylari(adaylar, [olay], UFUK, config.BAR_4H)
    kume = set(kalan.ogeler)
    assert _bar(12) in kume and _bar(48) in kume, "tam ufuk mesafesi yakin sayilmaz"
    assert _bar(13) not in kume and _bar(47) not in kume, "ufuktan bir bar yakin olan elenir"
    assert _bar(30) not in kume, "olayin kendi bari kontrol adayi olamaz"


def test_k1_adaylari_olay_listesi_sirasi_ve_cokluk_sonucu_degistirmez():
    """Olay sirasi ya da ayni olayin iki kez verilmesi sonucu degistirmez (kume semantigi)."""
    e1, e2 = tek_olay(_bar(10)), tek_olay(_bar(50))
    adaylar = _k1_kur([_bar(i) for i in range(0, 70)])
    a = ornekleme.k1_adaylari(adaylar, [e1, e2], UFUK, config.BAR_4H)
    b = ornekleme.k1_adaylari(adaylar, [e2, e1, e1], UFUK, config.BAR_4H)
    assert tuple(a.ogeler) == tuple(b.ogeler)


def test_k1_adaylari_k2_rolundeki_adayi_kabul_etmez():
    """k1_adaylari yalniz K1 rolunde aday bekler; K2 adaylari ile cagrilirsa reddedilir."""
    k2 = _k2_kur(["AAAUSDT", "BBBUSDT"], _bar(0))
    with pytest.raises(ValueError, match="K1 rolunde"):
        ornekleme.k1_adaylari(k2, [], UFUK, config.BAR_4H)
    k1 = _k1_kur([_bar(0), _bar(1)])
    with pytest.raises(ValueError, match="K2 rolunde"):
        ornekleme.k2_adaylari(k1, [], olay_sembolu="AAAUSDT")


@pytest.mark.parametrize("ham", [[_bar(0)], ["AAAUSDT"], pd.DatetimeIndex([_bar(0)]), [None], [1]])
def test_k1_k2_adaylari_ham_olay_listesi_reddedilir(ham):
    """§6 rev.11 (D-B2): olaylar `dizi.Olay` olmali; ham zaman/sembol listesi olay yerine gecmez."""
    with pytest.raises(TypeError):
        ornekleme.k1_adaylari(_k1_kur([_bar(0), _bar(1)]), ham, UFUK, config.BAR_4H)
    with pytest.raises(TypeError):
        ornekleme.k2_adaylari(_k2_kur(["AAAUSDT", "BBBUSDT"], _bar(0)), ham, olay_sembolu="ZZZUSDT")


def test_k1_adaylari_olay_yerine_kontrol_onayi_verilemez():
    """Bir `OnaylanmisPozisyon` (K1 rolunde bile) `dizi.Olay` degildir: kapinin onayi tek basina olay DEGILDIR."""
    onay = _onay("K1", _bar(30))
    with pytest.raises(TypeError):
        ornekleme.k1_adaylari(_k1_kur([_bar(0), _bar(1)]), [onay], UFUK, config.BAR_4H)


def test_k2_adaylari_olay_demeti_ve_bari_adaylarla_ayni_olmali():
    """§6 K2: 'o anda olay uretmemis' AYNI t barina ve AYNI yapilandirmaya gore."""
    adaylar = _k2_kur(["AAAUSDT", "BBBUSDT", "CCCUSDT"], _bar(5))
    with pytest.raises(ValueError, match="olay bari"):
        ornekleme.k2_adaylari(adaylar, olaylar_sembollerde(["BBBUSDT"], t=_bar(6)), olay_sembolu="ZZZUSDT")
    with pytest.raises(ValueError, match="demetine ait"):
        ornekleme.k2_adaylari(adaylar, olaylar_sembollerde(["BBBUSDT"], t=_bar(5), hipotez="H1"),
                              olay_sembolu="ZZZUSDT")
    sonuc = ornekleme.k2_adaylari(adaylar, olaylar_sembollerde(["BBBUSDT"], t=_bar(5)), olay_sembolu="AAAUSDT")
    assert sonuc.ogeler == ("CCCUSDT",)


@pytest.mark.parametrize("alan,deger", [("rol", "K2"), ("hipotez", "H1"), ("yapilandirma", "H2:phi=0.0005,k=6"),
                                        ("kume", "C1"), ("bar_zamani", _bar(3))])
def test_adaylar_alani_degistirilmis_hicbir_tuketiciden_gecmez(alan, deger):
    """`Adaylar` imzali: replace ile degistirilen kume ne filtreye ne ornekleyiciye girer (§6 rev.13)."""
    adaylar = _k1_kur([_bar(0), _bar(1), _bar(2)])
    bozuk = dataclasses.replace(adaylar, **{alan: deger})
    with pytest.raises(ValueError, match="elle kurulmus|degistirilmis"):
        ornekleme.k1_adaylari(bozuk, [], UFUK, config.BAR_4H)
    with pytest.raises(ValueError, match="elle kurulmus|degistirilmis"):
        ornekleme.ornekle(_elenmis(bozuk), olay=_olay())


def test_adaylar_ogeleri_degistirilmis_ya_da_elle_kurulmus_gecmez():
    adaylar = _k1_kur([_bar(0), _bar(1)])
    ekli = dataclasses.replace(adaylar, ogeler=adaylar.ogeler + (_bar(40),))
    with pytest.raises(ValueError, match="elle kurulmus|degistirilmis"):
        ornekleme.ornekle(_elenmis(ekli), olay=_olay())
    elle = ornekleme.Adaylar("K1", "H2", adaylar.yapilandirma, "KESIF", (_bar(0), _bar(1)))
    with pytest.raises(ValueError, match="elle kurulmus|degistirilmis"):
        ornekleme.ornekle(_elenmis(elle), olay=_olay())
    sifir = dataclasses.replace(elle, _imza=0)
    with pytest.raises(ValueError, match="elle kurulmus|degistirilmis"):
        ornekleme.ornekle(_elenmis(sifir), olay=_olay())


def test_ornekle_ham_liste_ve_serbest_sayi_reddedilir():
    """§6 rev.13: ham liste aday degildir; D-C5: sayi on-kayit degeri (10) olmali."""
    with pytest.raises(TypeError):
        ornekleme.ornekle(_elenmis([_bar(0), _bar(1)]), olay=_olay())
    adaylar = _k1_kur([_bar(i) for i in range(12)])
    for sayi in (0, 1, 9, 11, True):
        with pytest.raises(ValueError):
            ornekleme.ornekle(_elenmis(adaylar), olay=_olay(), sayi=sayi)


@pytest.mark.parametrize("n,beklenen,eksik", [(9, 9, True), (10, 10, False), (11, 10, False), (25, 10, False)])
def test_havuz_boyutu_aday_sayisina_gore_ve_aday_sayisi_yazilir(n, beklenen, eksik):
    """§6 rev.11: aday sayisi 10'dan azsa tamami alinir ve sayi yazilir; iadesiz."""
    adaylar = _k1_kur([_bar(i) for i in range(n)])
    h = ornekleme.ornekle(_elenmis(adaylar), olay=_olay())
    assert len(h) == beklenen and h.aday_sayisi == n and h.eksik is eksik
    assert len(set(h.secilenler)) == len(h.secilenler) and set(h.secilenler) <= set(adaylar.ogeler)


def test_ornekle_k1_olayin_kendi_bari_kontrol_adayi_olamaz():
    """§6 K1: 'o hipotezin herhangi bir olayina birincil ufuk mesafesinden yakin olmayan' bar; olayin kendi
    bari mesafe 0'dadir. `Adaylar` 'filtrelendi' bilgisini tasimadigi icin atlanan filtre fark edilmez."""
    barlar = [_bar(i) for i in range(8)]                   # 8 < 10: tamami cekilir
    adaylar = _k1_kur(barlar)                              # k1_adaylari UYGULANMADI
    try:
        h = ornekleme.ornekle(_elenmis(adaylar), olay=_olay(t=barlar[3]))
    except (ValueError, TypeError):
        return
    _acik(f"olay bari kontrol havuzunda: {barlar[3] in h.secilenler}")


def test_ornekle_k2_olayin_kendi_coini_kontrol_adayi_olamaz():
    """§6 K2: 'diger coinlerden' 10 rastgele coin; olayin kendi coini kendi kontrolu olamaz."""
    adaylar = _k2_kur(["AAVEUSDT", "BBBUSDT", "CCCUSDT"], _bar(5))
    try:
        h = ornekleme.ornekle(_elenmis(adaylar), olay=_olay(t=_bar(5)))
    except (ValueError, TypeError):
        return
    _acik(f"olayin kendi coini K2 havuzunda: {'AAVEUSDT' in h.secilenler}")


def test_ornekle_k2_olay_zamani_adaylarin_bariyla_ayni_olmali():
    """§6 K2: 'ayni t barinda'. Adaylar t=_bar(5) icin kuruldu, olay _bar(9)'da: havuz o olaya ait degil."""
    adaylar = _k2_kur(["BBBUSDT", "CCCUSDT"], _bar(5))
    try:
        ornekleme.ornekle(_elenmis(adaylar), olay=_olay(t=_bar(9)))
    except (ValueError, TypeError):
        return
    _acik("K2 havuzu baska bir barin olayi icin cekildi.")


def test_ornekle_k1_adaylar_olayin_coininden_olmali():
    """§6 K1: 'AYNI coinden' rastgele bar. Adaylar BBBUSDT'den, olay AAVEUSDT'den."""
    adaylar = _k1_kur([_bar(i) for i in range(12)], sembol="BBBUSDT")
    try:
        ornekleme.ornekle(_elenmis(adaylar), olay=_olay())
    except (ValueError, TypeError):
        return
    _acik("K1 kontrol havuzu baska bir coinin barlarindan cekildi.")


def test_kontrol_havuzu_olumlu_kontrol_gercek_havuz_olay_sayilarindan_gecer():
    """Kontrol: gercek havuz tutarlidir (sonraki xfail testlerin dayanagi)."""
    olay = _olay()
    k1 = ornekleme.ornekle(_elenmis(_k1_kur([_bar(i) for i in range(30)])), olay=olay)
    # Cift (K1, K2) olmali ve ayni olaya ait olmali (madde 3c): bos K2 havuzu da GERCEK havuzdur.
    k2 = ornekleme.ornekle(_elenmis(_k2_kur([], _bar(100))), olay=olay)
    ornekleme.olay_sayilari([(k1, k2)])


@pytest.mark.parametrize("sahte", [
    ornekleme.KontrolHavuzu(("SAHTE",), 1),
    ornekleme.KontrolHavuzu(tuple(f"S{i}" for i in range(12)), 3),     # secilen > aday sayisi
    ornekleme.KontrolHavuzu(("A",), 1, tohum=1, alt_tohum_demeti=("a", "b", "c", "d"), genel_tohum=7),
])
def test_elle_kurulmus_kontrol_havuzu_olay_sayisini_sisiremez(sahte):
    """§8 madde 2 (rev.13): olay sayisi ANALIZE GIREN olaylarin sayisidir; havuz kapidan gecmis adaylardan
    cekilmis olmali. Burada kapidan hic gecmemis bir havuz bir olayi 'analize girdi' yapar."""
    bos = ornekleme.ornekle(_elenmis(_k2_kur([], _bar(100))), olay=_olay())
    try:
        sayi = ornekleme.olay_sayilari([(sahte, bos)])
    except (TypeError, ValueError):
        return
    _acik(f"sahte havuz kabul edildi: analize_giren={sayi.analize_giren}")


def test_degistirilmis_kontrol_havuzu_tohumu_olay_sayilarindan_gecmemeli():
    """§8 madde 1: raporlanan tohum/demet cekimi yapan degerdir. `tohum` demetten turemiyorsa havuz sahtedir."""
    adaylar = _k1_kur([_bar(i) for i in range(30)])
    h = ornekleme.ornekle(_elenmis(adaylar), olay=_olay())
    bozuk = dataclasses.replace(h, tohum=h.tohum + 1)
    try:
        ornekleme.olay_sayilari([(bozuk, bozuk)])
    except (TypeError, ValueError):
        return
    _acik("tohumu demetle tutarsiz havuz kabul edildi.")


# =================================================================================================
# 1c. dizi.olay_dogrula
# =================================================================================================


@pytest.mark.parametrize("alan,deger", [
    ("p0", 2.0), ("p1", 0.5), ("funding_toplami", 0.5), ("gecersizlik_seviyesi", 5.0), ("ritim_sinifi", "4"),
    ("kuyruk_kismi", True), ("son_esitlik_affi", True), ("tek_ritim", True), ("karisik_ritim", True),
    ("funding_ritmi_saat", 4.0), ("son_aralik_saat", 4.0), ("capa_aralik_saat", 8.0), ("capa", T("2025-03-09")),
    ("sembol", "ZZZUSDT"), ("donem_no", 9), ("kume", "C1"), ("rol", "K1"), ("yapilandirma", "H2:phi=0.0005,k=6"),
])
def test_olay_icindeki_onay_bozulursa_olay_dogrulanamaz(alan, deger):
    """§4 rev.12 (S-C1): olayin tasidigi ONAY da dogrulanir. Pozisyonun HERHANGI bir alani bozulmus bir olay
    (replace ile, `_imza` kopyalanarak) reddedilir."""
    olay = tek_olay(TB)
    dizi.olay_dogrula(olay)
    bozuk = dataclasses.replace(olay, pozisyon=dataclasses.replace(olay.pozisyon, **{alan: deger}))
    with pytest.raises(ValueError):
        dizi.olay_dogrula(bozuk)


@pytest.mark.parametrize("alan,deger", [("zaman", TB + H4), ("capa", TB - H4), ("zaman", TB)])
def test_olayin_kendi_alanlari_imzada(alan, deger):
    """Olayin zaman ve capa alanlari imzaya girer (zaman=TB ayni deger: degisiklik yok -> gecer, kontrol)."""
    olay = tek_olay(TB)
    bozuk = dataclasses.replace(olay, **{alan: deger})
    if getattr(olay, alan) == deger:
        dizi.olay_dogrula(bozuk)
        return
    with pytest.raises(ValueError, match="elle kurulmus|degistirilmis"):
        dizi.olay_dogrula(bozuk)


@pytest.mark.parametrize("nesne", [None, 1, "olay", TB, object()])
def test_olay_olmayan_nesne_olay_dogrulamasindan_gecmez(nesne):
    with pytest.raises(TypeError):
        dizi.olay_dogrula(nesne)


def test_kapinin_onayi_tek_basina_olay_degildir():
    with pytest.raises(TypeError):
        dizi.olay_dogrula(_onay("olay", TB))


@pytest.mark.parametrize("zaman,capa", [(TB + 6 * H4, None), (TB, TB - 2 * H4)])
def test_tutarsiz_olay_zaman_capa_pozisyonla_celisirse_dogrulanamaz(zaman, capa):
    """§5 H1 madde 4 (S-B1): capa/t cifti pozisyonla ayni olmali. `dizi._olay_kur` ile imzali ama tutarsiz Olay."""
    gercek = tek_olay(TB)
    tutarsiz = dizi._olay_kur(zaman, capa, gercek.pozisyon)
    try:
        dizi.olay_dogrula(tutarsiz)
    except (ValueError, TypeError):
        return
    _acik(f"Olay(zaman={zaman}, capa={capa}) pozisyon sinyal zamani {gercek.pozisyon.plan.sinyal_zamani} iken kabul edildi.")


# =================================================================================================
# 1d. pozisyon._test_onayi omru ve onay kosusu
# =================================================================================================

_BASKA_TESTTE = {"olay": None, "adaylar": None, "onay": None}


def test_omur_a_kuran_test():
    """Bu test nesneleri kurar ve sonraki testlere tasir (dosya sirasi onemlidir)."""
    olay = tek_olay(TB)
    adaylar = _k1_kur([_bar(i) for i in range(12)])
    onay = _onay("K1", _bar(0))
    dizi.olay_dogrula(olay)
    pozisyon.onay_dogrula(onay)
    _BASKA_TESTTE.update(olay=olay, adaylar=adaylar, onay=onay)


def test_omur_b_baska_testte_kurulan_olay_dogrulanamaz():
    """D-C2: olay icindeki dikis onayi baska bir testte gecersizdir (`olay_dogrula` onayi yeniden dogrular)."""
    if _BASKA_TESTTE["olay"] is None:
        pytest.skip("kuran test kosmadi")
    with pytest.raises(ValueError, match="BASKA bir testte"):
        dizi.olay_dogrula(_BASKA_TESTTE["olay"])


def test_omur_b2_baska_testte_kurulan_onayin_kopyasi_da_gecersiz():
    """`dataclasses.replace(onay)` (alan degistirmeden) ayni `_imza`yi tasir; omur kaydi onu da yakalar."""
    if _BASKA_TESTTE["onay"] is None:
        pytest.skip("kuran test kosmadi")
    kopya = dataclasses.replace(_BASKA_TESTTE["onay"])
    with pytest.raises(ValueError, match="BASKA bir testte"):
        pozisyon.onay_dogrula(kopya)


@acik("Omur siniri yalniz `OnaylanmisPozisyon` nesnesine uygulanir; ondan turetilen `Adaylar` baska bir "
      "testte serbestce ornekleyiciye girer (D-C2 niyeti dikisin urunlerinin testle sinirli kalmasiydi). "
      "Koruma turunda KAPATILMADI: isaret bu turda yanlislikla kaldirilmis ve geri konmustur -- aciklik "
      "duruyor, yalnizca test baglaminda.")
def test_omur_c_baska_testte_kurulan_aday_kumesi_ornekleyiciye_girmemeli():
    if _BASKA_TESTTE["adaylar"] is None:
        pytest.skip("kuran test kosmadi")
    try:
        ornekleme.ornekle(_elenmis(_BASKA_TESTTE["adaylar"]), olay=_olay())
    except ValueError:
        return
    _acik("baska testte dikisle kurulan onaylardan turemis Adaylar ornekleyiciden gecti.")


def test_omur_ayni_testte_kimlik_degisirse_onay_reddedilir(monkeypatch):
    """Tek testte benzetim: test kimligi (PYTEST_CURRENT_TEST) degisince dikis onayi her tuketicide reddedilir."""
    onay = _onay("K1", _bar(0))
    pozisyon.onay_dogrula(onay)
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/baska_dosya.py::test_baska (call)")
    with pytest.raises(ValueError, match="BASKA bir testte"):
        pozisyon.onay_dogrula(onay)
    with pytest.raises(ValueError, match="BASKA bir testte"):
        ornekleme.adaylari_kur([onay], rol="K1")
    with pytest.raises(ValueError, match="BASKA bir testte"):
        pozisyon.pozisyon_fiyatlari(onay)


@pytest.mark.parametrize("kume,t", [("C1", TB), ("C2", TC2)])
def test_onay_kumesi_dikisi_acik_kosu_olmadan_kurulamaz_ve_kayit_kirlenmez(kume, t, kayit):
    """§3 madde 3: C1/C2 pozisyonu yalniz acik onay kosusunda; reddedilen cagri omur kaydina GIRMEZ."""
    once = dict(pozisyon._TEST_ONAY_OMURLERI)
    with pytest.raises(split.OnayGerekli):
        _onay("K1", t, kume=kume)
    with pytest.raises(split.OnayGerekli):
        _onay("olay", t, kume=kume)
    assert pozisyon._TEST_ONAY_OMURLERI == once


def test_onay_kumesi_dikisi_yalniz_eslesen_kosuda_ve_kilitli_yapilandirmayla_calisir(kayit):
    """Acik kosu (H2, C1) iken: eslesen cift ve KILIT.md yapilandirmasi calisir; baska hipotez, baska kume,
    KESIF ve baska yapilandirma OnayUyusmazligi; kosu bittikten sonra C1 yine OnayGerekli."""
    y_baska = dict(sinyal.izgara("H2")[1])
    with kosu("H2", "C1"):
        ok = _onay("K1", TB, kume="C1")
        assert ok.kume == "C1"
        with pytest.raises(split.OnayUyusmazligi):
            _onay("K1", TB, kume="C1", y=y_baska)
        with pytest.raises(split.OnayUyusmazligi):
            _onay("K1", TB, kume="C1", hipotez="H1")
        with pytest.raises(split.OnayUyusmazligi):
            _onay("K1", TC2, kume="C2")
        with pytest.raises(split.OnayUyusmazligi):
            _onay("K1", TB, kume="KESIF")
    with pytest.raises(split.OnayGerekli):
        _onay("K1", TB, kume="C1")


def test_pytest_disinda_dikis_calismaz(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    with pytest.raises(RuntimeError, match="yalnizca bir pytest testi"):
        _onay("K1", _bar(0))


# =================================================================================================
# 2. KILIT.md dogrulamasi
# =================================================================================================

KAPANDI = dict(hukum=split.KILIT_KAPANDI, gerekce="aday yok", yapilandirma="-", parametreler="-")


def _coz(**alanlar):
    return split.kilit_kaydi_coz(kilit_metni("H2", **alanlar), "H2")


@pytest.mark.parametrize("deger", ["inf", "+inf", "Infinity", "1e999"])
def test_kilit_k2_farki_sonsuz_olamaz(deger):
    """§8 madde 4: 'K2 farki > 0' sonlu bir olcumdur; sonsuz deger olculmus fark degildir."""
    try:
        _coz(k2_farki=deger)
    except split.KilitBozuk:
        return
    _acik(f"k2_farki={deger!r} kabul edildi")


def test_kilit_ortalama_net_getiri_sonsuz_olamaz():
    metin = kilit_metni("H2") + "| ortalama_net_getiri | inf |\n"
    try:
        split.kilit_kaydi_coz(metin, "H2")
    except split.KilitBozuk:
        return
    _acik("ortalama_net_getiri=inf kabul edildi")


@pytest.mark.parametrize("deger", ["nan", "NaN", "-inf", "abc", "", "0,0,1", "1.000.5"])
def test_kilit_k2_farki_sayi_olmayan_ya_da_pozitif_olmayan_reddedilir(deger):
    """NaN `> 0` degildir; sayi olmayan metin KilitBozuk."""
    with pytest.raises(split.KilitBozuk):
        _coz(k2_farki=deger)


@pytest.mark.parametrize("deger", ["1.50.000", "1..500", ".500", "1.5000", "1e3", "0x96", "1 500", "150,0",
                                   "--150", "+150", "-150", "150.0", "1.5"])
def test_kilit_olay_sayisi_bicim_saldirilari_reddedilir(deger):
    """§8 madde 5: negatif olmayan tamsayi; binlik ayirici nokta yalniz uclu gruplar halinde."""
    with pytest.raises(split.KilitBozuk):
        _coz(analize_giren=deger, olusmus="999999")


@pytest.mark.parametrize("deger", ["149", "0", "1.49"])
def test_kilit_aday_esiginin_altindaki_analize_giren_secilemez(deger):
    with pytest.raises(split.KilitBozuk):
        _coz(analize_giren=deger, olusmus="400")


def test_kilit_esik_analize_giren_olaya_uygulanir_olusmusa_degil():
    """§8 madde 2 (rev.13): olusmus 400 ama analize giren 149 -> aday degil."""
    with pytest.raises(split.KilitBozuk):
        _coz(olusmus=400, analize_giren=149)
    assert _coz(olusmus=400, analize_giren=config.ADAY_OLAY_ESIGI).analize_giren_olay == config.ADAY_OLAY_ESIGI


@pytest.mark.parametrize("alan,deger", [("analize_giren", "１５０"), ("tohum", "２０２６０９１１"),
                                        ("olusmus", "４００")])
def test_kilit_sayilar_yalniz_ascii_rakam_olmali(alan, deger):
    """§8 madde 5: olay sayilari/tohum 'negatif olmayan tamsayi'; kayit metni gozle denetlenir, ASCII olmayan
    rakam metin olarak bambaska bir sey gorunur."""
    try:
        _coz(**{alan: deger})
    except split.KilitBozuk:
        return
    _acik(f"{alan}={deger!r} kabul edildi")


@pytest.mark.parametrize("kimlik", ["h2:phi=0.0003,k=3", "H2:phi=0.00030,k=3", "H2:phi=3e-4,k=3",
                                    "H2:k=3,phi=0.0003", "H2:phi=0.0003, k=3", "H2:phi=0.0003,k=3,x=1",
                                    "H1:theta=0.2,delta=0.08", "", "-", "H2"])
def test_kilit_yapilandirma_kimligi_izgaradaki_bicimle_birebir_olmali(kimlik):
    """§5/§8 madde 5: kimlik izgaradaki demetin kimligidir; bicim/siralama farki ya da baska hipotez reddedilir."""
    with pytest.raises(split.KilitBozuk):
        _coz(yapilandirma=kimlik)


def test_kilit_butun_izgara_kimlikleri_gecer():
    for hipotez in config.HIPOTEZLER:
        for y in sinyal.izgara(hipotez):
            kimlik = sinyal.yapilandirma_kimligi(hipotez, y)
            # Madde 4b: `parametreler` kimlikle AYNI demeti gostermeli.
            parametreler = " ".join(p.strip() for p in kimlik.split(":", 1)[1].split(","))
            kayit = split.kilit_kaydi_coz(
                kilit_metni(hipotez, yapilandirma=kimlik, parametreler=parametreler), hipotez)
            assert kayit.yapilandirma == kimlik


def test_kilit_parametreler_kimlikle_tutarli_olmali():
    """§8 madde 5: 'yapilandirmanin kimligi ve BUTUN PARAMETRE DEGERLERI' ayni yapilandirmayi anlatmali."""
    try:
        _coz(parametreler="phi=0.0010 k=12")
    except split.KilitBozuk:
        return
    _acik("kimlik ile celisen parametreler kabul edildi")


@pytest.mark.parametrize("alan", list(split.KILIT_ALANLARI) + list(split.KILIT_ISTEGE_BAGLI_ALANLAR))
def test_kilit_her_alan_tam_bir_kez_buyuk_kucuk_harf_ve_bosluk_farki_ikinci_sayilir(alan):
    """§8 madde 5 ekleme kurali: ayni alanin 'ALAN' / bosluksuz / bicim farkli ikinci satiri da ikinci kayittir."""
    metin = kilit_metni("H2") + "| ortalama_net_getiri | 0.01 |\n"
    for ikinci in (f"| {alan.upper()} | x |\n", f"|{alan}|x|\n", f"|  {alan.title()}  |  x  |\n"):
        with pytest.raises(split.KilitBozuk, match="birden fazla"):
            split.kilit_kaydi_coz(metin + ikinci, "H2")


@pytest.mark.parametrize("hukum", ["Yapilandirma Secildi", "yapilandirma  secildi", "yapilandirma secildi.",
                                   "hipotez kapandi.", "kapandi", "secildi", "", "-"])
def test_kilit_hukum_yalniz_iki_sabit_metinden_biri_olabilir(hukum):
    with pytest.raises(split.KilitBozuk):
        _coz(hukum=hukum)


def test_kilit_kapandi_hukmunde_k2_farki_verilse_de_none():
    """§8 madde 4: kapanmis hipotezde secilecek yapilandirma/K2 farki yoktur -> None (NaN degil)."""
    kayit = _coz(**KAPANDI, k2_farki="0.5")
    assert kayit.secildi is False and kayit.k2_farki is None
    assert kayit == _coz(**KAPANDI, k2_farki="-")


@pytest.mark.parametrize("gerekce", ["", "-", "—"])
def test_kilit_kapandi_hukmunde_gerekce_zorunlu(gerekce):
    with pytest.raises(split.KilitBozuk):
        _coz(**{**KAPANDI, "gerekce": gerekce})


@acik("`pd.Timestamp(str)` dateutil'e dusup 'Oct 20 2026 12:00 UTC' gibi ISO olmayan, tz'li metni de kabul eder; "
      "kod yalniz tz ve ofseti denetler, bicimin ISO 8601 oldugunu denetlemez. (Kosturulamadi; pandas surumune bagli.)")
@pytest.mark.parametrize("zaman", ["Oct 20 2026 12:00 UTC", "10/20/2026 12:00:00 UTC"])
def test_kilit_kesif_zamani_iso_8601_olmali(zaman):
    """§8 madde 5: 'UTC zamani' (CLAUDE.md §5); kilit kaydi ISO 8601 yazim ister (`ISO + UTC`)."""
    try:
        _coz(zaman=zaman)
    except split.KilitBozuk:
        return
    _acik(f"kesif_zamani={zaman!r} kabul edildi")


@pytest.mark.parametrize("zaman", ["2026-10-20T12:00:00", "2026-10-20T12:00:00+03:00", "2026-10-20", "dun",
                                   "2026-13-45T00:00:00+00:00", "NaT", "", "2026-10-20T15:00:00+03:00"])
def test_kilit_kesif_zamani_utc_olmayan_ya_da_bozuk_reddedilir(zaman):
    with pytest.raises(split.KilitBozuk):
        _coz(zaman=zaman)


@pytest.mark.parametrize("commit", ["0" * 39, "0" * 41, "g" * 40, "0x" + "a" * 38, "", " ", "a" * 20 + " " + "a" * 19,
                                    "０" * 40])
def test_kilit_kesif_commit_40_hane_onaltilik_olmali(commit):
    with pytest.raises(split.KilitBozuk):
        _coz(commit=commit)


# ---- 2g. Ekleme kurali: git gecmisi (BLOB sayisi) ----------------------------------------------


def _h2_kilitli_depo(tmp_path):
    depo = gecici_depo(tmp_path, kilitler=("H1", "H3"))
    yol = kilit_yaz(depo, "H2")
    git(depo, "add", ".")
    git(depo, "commit", "-q", "-m", "H2 kaydi")
    git(depo, "push", "-q", "origin", "main")   # madde 4a: kayit itilmis olmali
    split.kilit_oku("H2")                       # kontrol: tek blob gecerli
    return depo, yol


def _blob_sayisi(depo, *bayrak) -> int:
    cikti = git(depo, "rev-list", "--all", *bayrak, "--objects", "--", "analysis/H2/KILIT.md")
    return len({s.split()[0] for s in cikti.splitlines() if s.strip().endswith("analysis/H2/KILIT.md")})


@pytest.mark.parametrize("varyasyon", ["crlf", "sondaki_bosluk", "bos_satir", "alan_sirasi"])
def test_ekleme_kurali_ayni_icerik_farkli_yazimla_ikinci_blob_olusturur_ve_reddedilir(tmp_path, varyasyon):
    """§8 madde 5: 'yazildiktan sonra degistirilmez'. Anlamca AYNI kaydin baska bayt dizisiyle yeniden
    commit'lenmesi ikinci bir BLOB'dur ve reddedilir (koruma yonunde yanlis pozitif: guvenli taraf)."""
    depo, yol = _h2_kilitli_depo(tmp_path)
    metin = yol.read_text(encoding="utf-8")
    if varyasyon == "crlf":
        yeni = metin.replace("\n", "\r\n")
    elif varyasyon == "sondaki_bosluk":
        yeni = metin.replace("\n", "  \n")
    elif varyasyon == "bos_satir":
        yeni = metin + "\n\n"
    else:
        satirlar = metin.splitlines()
        yeni = "\n".join(satirlar[:4] + satirlar[4:][::-1]) + "\n"
    assert yeni != metin
    yol.write_text(yeni, encoding="utf-8", newline="")
    git(depo, "add", "-A")
    git(depo, "commit", "-q", "-m", "ayni kayit baska yazimla")
    # Anlam ayni mi? (saldirinin on kosulu: ayristirilmis kayit esit)
    with open(yol, encoding="utf-8", newline="") as dosya:
        ham_yeni = dosya.read()
    assert split.kilit_kaydi_coz(ham_yeni, "H2") == split.kilit_kaydi_coz(metin, "H2")
    with pytest.raises(split.KilitBozuk, match="farkli icerikle"):
        split.kilit_oku("H2")


def test_ekleme_kurali_degistirip_geri_alma_iki_blob_sayilir(tmp_path):
    """A -> B -> A: son durum ilk durumla BAYT BAYT ayni olsa da gecmiste iki icerik vardir."""
    depo, yol = _h2_kilitli_depo(tmp_path)
    kilit_yaz(depo, "H2", k2_farki="0.9999")
    git(depo, "add", "-A")
    git(depo, "commit", "-q", "-m", "degisti")
    kilit_yaz(depo, "H2")
    git(depo, "add", "-A")
    git(depo, "commit", "-q", "-m", "geri alindi")
    with pytest.raises(split.KilitBozuk, match="farkli icerikle"):
        split.kilit_oku("H2")


def test_ekleme_kurali_silinip_baska_icerikle_geri_eklenen_kayit_reddedilir(tmp_path):
    depo, yol = _h2_kilitli_depo(tmp_path)
    yol.unlink()
    git(depo, "add", "-A")
    git(depo, "commit", "-q", "-m", "silindi")
    kilit_yaz(depo, "H2", k2_farki="0.5000")
    git(depo, "add", "-A")
    git(depo, "commit", "-q", "-m", "baska icerikle geri")
    with pytest.raises(split.KilitBozuk, match="farkli icerikle"):
        split.kilit_oku("H2")


def test_ekleme_kurali_silinmis_dalda_degistirilen_kayit_reflogdan_yakalanir(tmp_path):
    """Degisiklik yan dalda yapilip dal SILINIRSE: reflog hala tutar, `--reflog` taramasi yakalar."""
    depo, yol = _h2_kilitli_depo(tmp_path)
    git(depo, "checkout", "-q", "-b", "gecici")
    kilit_yaz(depo, "H2", k2_farki="0.9999")
    git(depo, "add", "-A")
    git(depo, "commit", "-q", "-m", "yan dalda degisti")
    git(depo, "checkout", "-q", "main")
    git(depo, "branch", "-q", "-D", "gecici")
    with pytest.raises(split.KilitBozuk, match="farkli icerikle"):
        split.kilit_oku("H2")


def test_ekleme_kurali_ours_birlesmesiyle_atilan_yan_dal_reflog_temizlenince_gorunmez(tmp_path):
    depo, yol = _h2_kilitli_depo(tmp_path)
    git(depo, "checkout", "-q", "-b", "gecici")
    kilit_yaz(depo, "H2", k2_farki="0.9999")
    git(depo, "add", "-A")
    git(depo, "commit", "-q", "-m", "yan dalda degisti")
    git(depo, "checkout", "-q", "main")
    git(depo, "merge", "-q", "--no-ff", "-s", "ours", "-m", "ours birlesmesi", "gecici")
    git(depo, "branch", "-q", "-D", "gecici")
    git(depo, "reflog", "expire", "--expire=now", "--all")
    if _blob_sayisi(depo, "--full-history") != 2:                     # saldirinin on kosulu
        raise RuntimeError("test onkosulu bozuk: --full-history ile iki blob gorunmeli")
    try:
        split.kilit_oku("H2")
    except split.KilitBozuk:
        return
    _acik("gecmiste degistirilmis kayit (yan dal) kilit_oku tarafindan fark edilmedi.")


@acik("Ekleme kurali YEREL git gecmisine dayanir: `reset --hard` + reflog temizligi ikinci blob'u siler ve denetim "
      "gecer (itilmis bir uzak ref yoksa). Tasarim siniri; CLAUDE.md 'kararli atlatmaya karsi degil'.")
def test_ekleme_kurali_yerel_gecmis_yeniden_yazilirsa_degisiklik_gorunmez(tmp_path):
    depo, yol = _h2_kilitli_depo(tmp_path)
    kilit_yaz(depo, "H2", k2_farki="0.9999")
    git(depo, "add", "-A")
    git(depo, "commit", "-q", "-m", "degisti")
    git(depo, "reset", "-q", "--hard", "HEAD~1")
    git(depo, "reflog", "expire", "--expire=now", "--all")
    try:
        split.kilit_oku("H2")
    except split.KilitBozuk:
        return
    _acik("yeniden yazilmis gecmiste degisiklik izi kalmadi; denetim gecti.")


# =================================================================================================
# 3. Bar duzeyli olcut ve fiyat okuma (D-B3, §2 rev.12)
# =================================================================================================

_B3_BAS = T("2025-01-01 00:00")
_B3_SON = T("2025-02-10 08:00")
_B3_DONEM_BAS = _B3_BAS - UYGUN_ONCELIK
_B3_T = T("2025-01-05 04:00")


def _b3_cerceve() -> pd.DataFrame:
    """Donem basindan sona tam, saglam 4h cerceve (tum hucre sutunlari float; `count` dahil)."""
    z = pd.date_range(_B3_DONEM_BAS, _B3_SON, freq="4h")
    acilis = 100.0 + 0.01 * np.arange(len(z))
    return pd.DataFrame({
        "open_time": z, "open": acilis, "high": acilis + 0.5, "low": acilis - 0.5, "close": acilis + 0.1,
        "volume": 1.0, "close_time": z + H4 - pd.Timedelta(milliseconds=1),
        "quote_volume": np.where(z.hour == 0, 5e7, 0.0), "count": 5.0, "taker_buy_volume": 0.5,
        "taker_buy_quote_volume": 0.0})


def _b3_funding() -> pd.DataFrame:
    z = pd.date_range(_B3_BAS, _B3_SON + H4, freq="8h")
    return pd.DataFrame({"odeme_zamani": z, "aralik_saat": 8.0, "oran": 1e-4, "oran_8h": 1e-4})


def _b3_karar(mumlar: pd.DataFrame, t=_B3_T):
    return pozisyon.olay_karari(
        t, 18, config.BAR_4H, hipotez="H1", birincil_ufuk=18, kume="KESIF",
        **veri(mumlar, _b3_funding(), _B3_DONEM_BAS, _B3_SON, ham=True),
        **kontrol("H1", "K1"), **esikler(config.BAR_4H))


def _satir(m: pd.DataFrame, zaman) -> int:
    return int(m.index[m["open_time"] == zaman][0])


def test_bar_duzeyi_kontrol_saglam_seri_olagan_karar_verir():
    """Kontrol: saldirilarin karsilastirma tabani."""
    p = _b3_karar(_b3_cerceve())
    assert p.plan.giris == T("2025-01-05 08:00") and p.cikis_turu == "olagan"


@pytest.mark.parametrize("sutun", klines.HUCRE_SUTUNLARI)
@pytest.mark.parametrize("deger", [np.nan, np.inf, -np.inf])
def test_bar_duzeyi_giris_bari_bozuksa_olay_olusmaz_ileri_kayma_girisde_yok(sutun, deger):
    """§2 rev.12 + §4 'Fiyat okuma tabani': bozuk hucreli bar MEVCUT DEGILDIR; giris barinda ileri kayma YOKTUR
    (yalniz cikista vardir), yani t+1 bari yoksa olay olusmaz. Giris sonraki bara KAYMAMALI."""
    m = _b3_cerceve()
    m.loc[_satir(m, T("2025-01-05 08:00")), sutun] = deger
    with pytest.raises(pencere.GirisBariYok):
        _b3_karar(m)


def test_bar_duzeyi_count_bozuksa_bar_dusmez():
    """§2 rev.12: islem sayisi (`count`) kapsam disidir; giris barinda NaN count olayi/kontrolu engellemez."""
    m = _b3_cerceve()
    m.loc[_satir(m, T("2025-01-05 08:00")), "count"] = np.nan
    assert _b3_karar(m).plan.giris == T("2025-01-05 08:00")


@pytest.mark.parametrize("sutun", ["volume", "open", "taker_buy_quote_volume"])
def test_bar_duzeyi_cikis_bari_bozuksa_ileri_kayma_sonraki_barin_acilisi(sutun):
    """§4 'Fiyat okuma tabani': hedef cikis bari mevcut degilse cikis sonraki ilk mevcut barin ACILISI."""
    temiz = _b3_cerceve()
    p0 = _b3_karar(temiz)
    hedef = p0.plan.cikis.zaman
    assert p0.cikis_turu == "olagan"
    m = _b3_cerceve()
    m.loc[_satir(m, hedef), sutun] = np.nan
    p = _b3_karar(m)
    assert p.cikis_turu == "ileri_kayma" and p.plan.cikis.zaman == hedef + H4
    assert p.plan.cikis.fiyat_alani == "open"
    assert p.p1 == float(temiz.loc[_satir(temiz, hedef + H4), "open"])


def test_bar_duzeyi_mae_penceresindeki_bozuk_bar_hesaba_girmez():
    """§4 MAE: H, DONEM ICI MEVCUT barlarin en yuksek high'idir. Bozuk hucreli barin (volume NaN) high'i 1e6 de
    olsa MAE'ye girmez; bar hic yokmus gibi (satir silinmis) ayni sonuc cikar. Kontrol: ayni high SAGLAM barda
    olsaydi MAE patlardi (testin duyarliligi)."""
    p0 = _b3_karar(_b3_cerceve())
    ic_bar = p0.plan.giris + 5 * H4

    bozuk = _b3_cerceve()
    i = _satir(bozuk, ic_bar)
    bozuk.loc[i, "high"] = 1e6
    bozuk.loc[i, "volume"] = np.nan

    silinmis = _b3_cerceve().drop(index=i).reset_index(drop=True)

    saglam = _b3_cerceve()
    saglam.loc[i, "high"] = 1e6

    m_bozuk = pozisyon.mae(_b3_karar(bozuk))
    m_silinmis = pozisyon.mae(_b3_karar(silinmis))
    m_saglam = pozisyon.mae(_b3_karar(saglam))
    assert m_saglam > 1e3, "duyarlilik: saglam barin high'i MAE'yi belirler"
    assert m_bozuk < 1.0, "bozuk barin high'i MAE'ye girdi"
    assert m_bozuk == pytest.approx(m_silinmis)


def test_bar_duzeyi_sinyal_penceresindeki_bozuk_bar_kontrolu_engeller_ayni_bar_icin_tutarlilik():
    """Tutarlilik: bir barin 'yok' sayilmasi sinyal penceresinde de gecerlidir. t-1 bari (H1 dip/hacim penceresinde)
    bozuksa K1 kontrol de olusmaz; ayni bar saglamken olusur. (Bir yerde 'var', baska yerde 'yok' olmamali.)"""
    assert _b3_karar(_b3_cerceve()).plan.giris == T("2025-01-05 08:00")
    m = _b3_cerceve()
    m.loc[_satir(m, _B3_T - H4), "volume"] = np.nan
    with pytest.raises(pencere.OlayOlusmaz):
        _b3_karar(m)


@pytest.mark.parametrize("fiyat", [0.0, -1.0])
def test_bar_duzeyi_giris_acilisi_pozitif_olmayan_fiyatla_onay_verilmemeli(fiyat):
    """§4 'Fiyat okuma tabani' + §2 rev.12 (sonlu hucre): fiyat sonlu ama 0/negatif olan bar gercek veri
    degildir (short getirisi 1 - P1/P0 tanimsiz). Kapi onay vermemeli."""
    m = _b3_cerceve()
    m.loc[_satir(m, T("2025-01-05 08:00")), "open"] = fiyat
    try:
        p = _b3_karar(m)
    except (pencere.OlayOlusmaz, ValueError):
        return
    _acik(f"P0={p.p0} ile onay verildi")


# =================================================================================================
# 4. Tohum degismezligi (D-B4)
# =================================================================================================

DEGISMEZLER = ("TOHUM", "PERMUTASYON_TEKRAR", "ALFA_BONFERRONI")


@pytest.mark.parametrize("ad", DEGISMEZLER)
def test_sabit_dogrudan_atama_ve_silme_reddedilir(ad):
    """§7 + CLAUDE.md §5: tohum/tekrar/alfa calisma aninda degistirilemez."""
    asil = getattr(config, ad)
    with pytest.raises(config.SabitDegistirilemez):
        setattr(config, ad, 1)
    with pytest.raises(config.SabitDegistirilemez):
        delattr(config, ad)
    assert getattr(config, ad) == asil


@pytest.mark.parametrize("ad", DEGISMEZLER)
def test_sabit_monkeypatch_setattr_reddedilir(ad):
    """`monkeypatch.setattr(config, ...)` atamada patlar. (Fikstur yerine ayri `MonkeyPatch`: pytest geri alma
    listesine atamadan ONCE yazar ve geri alma da `setattr` oldugu icin teardown'da patlardi; liste temizlenir.)"""
    asil = getattr(config, ad)
    yama = pytest.MonkeyPatch()
    try:
        with pytest.raises(config.SabitDegistirilemez):
            yama.setattr(config, ad, 1)
        with pytest.raises(config.SabitDegistirilemez):
            yama.delattr(config, ad)
    finally:
        yama._setattr.clear()
    assert getattr(config, ad) == asil


def test_sabit_sinifa_ayni_adli_deger_yazmak_modul_degerini_gizlemez():
    """`setattr(config.__class__, 'TOHUM', 1)`: deger degismez.

    Koruma turu madde 5'ten beri sinifin ozellikleri de yazilamaz (`_SabitModulTuru`), yani yazim
    DENEMESI reddedilir; hukum ayni: `config.TOHUM` ve ondan turetilen tohum degismez."""
    asil = config.TOHUM
    with pytest.raises(config.SabitDegistirilemez):
        type(config).TOHUM = 1
    assert config.TOHUM == asil
    assert ornekleme.tohum_turet("x") == int.from_bytes(
        hashlib.sha256(f"{asil}|x".encode("utf-8")).digest()[:8], "big")


def test_sabit_class_atamasi_reddedilir():
    with pytest.raises(config.SabitDegistirilemez):
        config.__class__ = types.ModuleType


def test_sabit_sinifin_setattr_degistirilerek_tohum_atlatilamaz():
    sinif = type(config)
    asil = config.TOHUM
    degisti = False
    try:
        try:
            sinif.__setattr__ = types.ModuleType.__setattr__
        except AttributeError:
            pass
        try:
            config.TOHUM = 1
        except AttributeError:
            pass
        degisti = config.TOHUM != asil
    finally:
        config.__dict__["TOHUM"] = asil
    assert not degisti, "config.TOHUM sinifin __setattr__i degistirilerek yeniden atandi"


def test_sabit_object_setattr_ile_tohum_atlatilamaz():
    asil = config.TOHUM
    degisti = False
    try:
        try:
            object.__setattr__(config, "TOHUM", 1)
        except (AttributeError, TypeError):
            pass
        degisti = config.TOHUM != asil
    finally:
        config.__dict__["TOHUM"] = asil
    assert not degisti, "config.TOHUM object.__setattr__ ile degistirildi"


@pytest.mark.parametrize("ad", DEGISMEZLER)
def test_sabit_modul_sozlugu_uzerinden_degistirilemez(ad, monkeypatch):
    asil = getattr(config, ad)
    monkeypatch.setitem(vars(config), ad, asil + 1)
    assert getattr(config, ad) == asil, f"config.{ad} vars(config) uzerinden degistirildi"


# =================================================================================================
# 5. Havuzun alt tohumu (D-C6)
# =================================================================================================


def _havuz(adaylar=None, *, sembol="AAVEUSDT", t=None):
    """Madde 3b: olay `ornekle`ye nesne olarak verilir ve adaylarla capraz dogrulanir.

    Olayin hipotezi ve yapilandirmasi ADAYLARDAN turetilir (kimlikten izgaradaki demete), coini ve
    donemi K1'de adaylarin kendisinden gelir.
    """
    adaylar = _k1_kur([_bar(i) for i in range(30)], sembol=sembol) if adaylar is None else adaylar
    hipotez = adaylar.hipotez
    y = next(dict(g) for g in sinyal.izgara(hipotez)
             if sinyal.yapilandirma_kimligi(hipotez, g) == adaylar.yapilandirma)
    olay = _olay(sembol=adaylar.sembol or sembol, t=t, hipotez=hipotez, yapilandirma=y,
                 kume=adaylar.kume, donem_no=adaylar.donem_no or 0)
    return ornekleme.ornekle(_elenmis(adaylar), olay=olay)


def test_havuz_tohumu_demetten_turer_ve_yeniden_uretilebilir():
    """§8 madde 1: tohum ve alt tohum turetme demeti. Demetten `tohum_turet` AYNI tohumu verir; SHA256 bagimsiz
    hesapla da ayni; ayni demetten cekim yeniden uretilince ayni barlar cikar."""
    adaylar = _k1_kur([_bar(i) for i in range(30)])
    olay = _olay()                     # madde 3b: demet OLAYDAN okunur
    h = ornekleme.ornekle(_elenmis(adaylar), olay=olay)
    kimlik, kume, sembol, zaman = h.alt_tohum_demeti
    assert (kimlik, kume, sembol, zaman) == (adaylar.yapilandirma, "KESIF", "AAVEUSDT",
                                             olay.zaman.isoformat())
    assert h.tohum == ornekleme.tohum_turet(*h.alt_tohum_demeti)
    beklenen = int.from_bytes(hashlib.sha256("|".join((str(config.TOHUM), *h.alt_tohum_demeti)).encode()).digest()[:8],
                              "big")
    assert h.tohum == beklenen and h.genel_tohum == config.TOHUM
    sirali = sorted(adaylar.ogeler)
    idx = sorted(int(i) for i in np.random.default_rng(h.tohum).choice(len(sirali), size=10, replace=False))
    assert h.secilenler == tuple(sirali[i] for i in idx)


def test_havuz_tohumu_ayni_demet_esit_havuz_aday_sirasi_ve_kurulus_sirasi_fark_etmez():
    barlar = [_bar(i) for i in range(30)]
    rng = np.random.default_rng(7)
    karisik = [barlar[i] for i in rng.permutation(len(barlar))]
    assert _havuz(_k1_kur(barlar)) == _havuz(_k1_kur(karisik)) == _havuz(_k1_kur(barlar))


def test_havuz_tohumu_demetin_her_ekseninde_degisir():
    """Farkli demet farkli tohum: sembol, olay zamani, yapilandirma, hipotez (kume: C1 acik kosu ister, kapsam disi)."""
    barlar = [_bar(i) for i in range(30)]
    y1 = dict(sinyal.izgara("H2")[1])
    tohumlar = {
        "temel": _havuz(_k1_kur(barlar)).tohum,
        # Madde 3b: K1 adaylari olayin KENDI coininden olmak zorunda, bu yuzden sembol ekseni iki
        # ayri aday kumesiyle sinanir.
        "sembol": _havuz(_k1_kur(barlar, sembol="BBBUSDT"), sembol="BBBUSDT").tohum,
        "zaman": _havuz(_k1_kur(barlar), t=_bar(101)).tohum,
        "yapilandirma": _havuz(_k1_kur(barlar, y=y1)).tohum,
        "hipotez": _havuz(_k1_kur(barlar, hipotez="H1")).tohum,
    }
    assert len(set(tohumlar.values())) == len(tohumlar), tohumlar


def test_havuz_tohumu_olay_zamani_saat_diliminden_bagimsiz_naive_reddedilir():
    """CLAUDE.md §5 (S-B4): ayni an +03:00 olarak verilse de ayni tohum/demet; saat dilimsiz damga reddedilir."""
    # Madde 3b'den beri olay zamani `ornekle`ye serbest damga olarak verilemez (olaydan okunur) ve
    # kapi UTC disi sinyal zamanini zaten reddeder; S-B4'un guvencesi bu yuzden TURETME
    # fonksiyonunda sinanir.
    utc = _bar(100)
    yerel = utc.tz_convert("Europe/Istanbul")
    assert ornekleme.alt_tohum("H2", Y2, "KESIF", "AAVEUSDT", utc) == ornekleme.alt_tohum(
        "H2", Y2, "KESIF", "AAVEUSDT", yerel)
    assert (ornekleme.alt_tohum_demeti("H2", Y2, "KESIF", "AAVEUSDT", utc)
            == ornekleme.alt_tohum_demeti("H2", Y2, "KESIF", "AAVEUSDT", yerel))
    with pytest.raises(TypeError):
        ornekleme.alt_tohum("H2", Y2, "KESIF", "AAVEUSDT", pd.Timestamp("2025-03-01"))


def test_havuz_tohumu_tohum_turet_ayirici_ve_bos_parcayi_reddeder_sinirda_carpismaz():
    for kotu in (("a|b",), ("",), ("a", ""), (1,), (None,), ()):
        with pytest.raises((ValueError, TypeError)):
            ornekleme.tohum_turet(*kotu)
    assert ornekleme.tohum_turet("ab", "c") != ornekleme.tohum_turet("a", "bc")
    assert ornekleme.tohum_turet("a", "b") != ornekleme.tohum_turet("b", "a")


def test_havuz_tohumu_genel_tohum_alani_turetmede_kullanilan_degerdir():
    """Genel tohum demetin disinda `genel_tohum` olarak yazilir; havuz onsuz yeniden uretilemez, bu yuzden alan
    dogru olmali (raporlanan genel tohum, turetmede kullanilan degerdir)."""
    h = _havuz()
    assert h.genel_tohum == config.TOHUM
    yeniden = int.from_bytes(hashlib.sha256(f"{h.genel_tohum}|{'|'.join(h.alt_tohum_demeti)}".encode()).digest()[:8], "big")
    assert yeniden == h.tohum


def test_havuz_tohumu_bos_havuzda_da_genel_tohum_raporlanir():
    """§8 madde 1 (rev.13) + CLAUDE.md §5: 'tohum sonuc dosyasina yazilir'."""
    h = ornekleme.ornekle(_elenmis(_k1_kur([])), olay=_olay())
    assert len(h) == 0 and h.aday_sayisi == 0
    assert h.genel_tohum == config.TOHUM


def test_alt_tohum_izgara_disi_kimlik_str_olarak_kabul_edilmemeli():
    try:
        ornekleme.alt_tohum("H2", "H2:phi=9,k=9", "KESIF", "AAVEUSDT", BAS)
    except (ValueError, TypeError):
        return
    _acik("izgara disi kimlikle alt tohum turetildi")


# =================================================================================================
# 6. Hook deseni (.claude/hooks/kilitli_dosya_korumasi.py) -- komutlar CALISTIRILMAZ, yalniz metin
# =================================================================================================

_HOOK_YOLU = KOK / ".claude" / "hooks" / "kilitli_dosya_korumasi.py"
_SPEC = importlib.util.spec_from_file_location("kilit_hook_sizinti_kimlik", _HOOK_YOLU)
hook = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = hook          # dataclass modulun kayitli olmasini bekler
_SPEC.loader.exec_module(hook)

ALTI = ("PREREGISTRATION.md", "data/split.csv", "data/universe.csv", "data/exchange_info_anlik.json",
        "ONAY_KAYDI.md", "CLAUDE.md")
DESEN = "analysis/*/KILIT.md"
KILIT = "analysis/h1/KILIT.md"
YAZMA_SABLONLARI = ("echo x > {}", "rm {}", "cp a {}", "mv a {}", "tee {}", "sed -i s/a/b/ {}")


def test_hook_kilitli_liste_alti_tam_yol_ve_bir_desen():
    assert tuple(hook.KILITLI) == (*ALTI, DESEN)


@pytest.mark.parametrize("yol", ALTI)
def test_hook_alti_tam_yol_girdisinin_korumasi_her_yazimda_durur(yol):
    """Altı tam yol girdisinin koruması aynen durmalı: yalın ad, ./, .. dolambaclari, mutlak yol, buyuk harf."""
    bicimler = [yol, "./" + yol, "alt/../" + yol, (KOK / yol).as_posix(), yol.upper(), "'" + yol + "'",
                '"' + yol + '"']
    kacan = []
    for bicim in bicimler:
        for sablon in YAZMA_SABLONLARI:
            if hook.bash_degerlendir(sablon.format(bicim)).izin:
                kacan.append(sablon.format(bicim))
    assert not kacan, kacan
    assert hook.kilitli_mi(str(KOK / yol)) == yol
    assert hook.kilitli_mi(yol) == yol


@pytest.mark.parametrize("yol", ["analysis/h1/KILIT.md", "analysis/H2/KILIT.md", "analysis\\h1\\KILIT.md",
                                 (KOK / "analysis" / "h1" / "KILIT.md").as_posix(),
                                 (KOK / "analysis" / "h1" / ".." / "h1" / "KILIT.md").as_posix(),
                                 KOK.as_posix() + "/analysis//h1/KILIT.md",
                                 KOK.as_posix() + "/analysis/h1/./KILIT.md"])
def test_hook_write_edit_yolu_normallestirilir_ve_desen_korunur(yol):
    """Write/Edit araclari mutlak yol verir; `Path.resolve()` '..', '.', '//' dolambaclarini temizler."""
    assert hook.kilitli_mi(yol) == DESEN, yol


@pytest.mark.parametrize("komut", [
    "echo x > 'analysis/h1/KILIT.md'", 'echo x > "analysis/h1/KILIT.md"', "echo x > analysis/h1/KIL\"\"IT.md",
    'echo x > analysis/h1/"KILIT".md', "echo x>analysis/h1/KILIT.md", "echo x >analysis/h1/KILIT.md",
    "cat > analysis/h1/KILIT.md <<EOF\nx\nEOF", "{ echo x; } > analysis/h1/KILIT.md",
    "(echo x) > analysis/h1/KILIT.md", ": > analysis/h1/KILIT.md", "echo x | dd of=analysis/h1/KILIT.md",
    "git mv yedek.md analysis/h1/KILIT.md", "git mv analysis/h1 analysis/z", "git rm analysis/h1/KILIT.md",
    "install -m 644 a analysis/h1/KILIT.md", "ln -sf a analysis/h1/KILIT.md", "truncate -s0 analysis/h1/KILIT.md",
    "sed -i.bak s/a/b/ analysis/h1/KILIT.md", "sed --in-place=.bak s/a/b/ analysis/h1/KILIT.md",
    "awk -i inplace '{print}' analysis/h1/KILIT.md", "perl -pi -e 's/a/b/' analysis/h1/KILIT.md",
    "env sed -i s/a/b/ analysis/h1/KILIT.md", "curl -o analysis/h1/KILIT.md http://x",
    "python -c \"open('analysis/h1/KILIT.md','w').write('x')\"",
    "python - <<EOF\nopen('analysis/h1/KILIT.md','w').write('x')\nEOF",
    "cp a analysis/h1/", "rm -rf analysis", "rm -rf analysis/h1", "rm -rf ./analysis/",
])
def test_hook_kilit_md_tirnak_kacis_ve_sarmalayici_dolambaclari_reddedilir(komut):
    assert not hook.bash_degerlendir(komut).izin, komut


@pytest.mark.parametrize("komut", [
    "echo x > analysis/h1/KILIT.md.bak", "touch analysis/h1/KILIT.mdx", "echo x > analysis/h1/XKILIT.md",
    "rm analysis/h1/baska.md", "cp a analysis/h1/notlar.md", "echo x > analysis/00_veri_denetimi/RESULTS.md",
    "rm analysis/00_veri_denetimi/.rev1213_capasiz.kilit", "echo x > KILIT.md", "rm data/KILIT.md",
])
def test_hook_desen_adi_tam_KILIT_md_olmayanlari_kapsamaz(komut):
    """Daraltma: yalniz adi TAM `KILIT.md` olan yollar korunur (kosu kilidi artigi vb. silinebilir)."""
    karar = hook.bash_degerlendir(komut)
    assert karar.izin, f"{komut} -> {karar.neden}"


@pytest.mark.parametrize("arg,beklenen", [("analysis", DESEN), ("analysis/", DESEN), ("./analysis", DESEN),
                                          ("analysis/h1", DESEN), ("analysis/ZZZ", DESEN),
                                          ("analysis/h1/baska.md", None), ("analysis/h1/alt", None),
                                          ("analysis2", None), ("xanalysis", None)])
def test_hook_dizin_kapsami_analysis_ve_hipotez_dizini_evet_icindeki_baska_dosya_hayir(arg, beklenen):
    assert hook.kapsar_mi(arg) == beklenen, arg


@pytest.mark.parametrize("yol", ["analysis/h1/../h1/KILIT.md", "analysis//h1/KILIT.md", "analysis/h1/./KILIT.md",
                                 "./analysis/h1/../h2/KILIT.md", "analysis/./h1/KILIT.md"])
def test_hook_bash_yol_dolambaclari_kilit_md_korumasini_delmemeli(yol):
    kacan = [s.format(yol) for s in YAZMA_SABLONLARI if hook.bash_degerlendir(s.format(yol)).izin]
    if kacan:
        _acik(f"izin verilen komutlar: {kacan}")


@pytest.mark.parametrize("komut", ["rm -rf analysis/h1/..", "rm -rf analysis/h1/../h1", "mv analysis/h1/.. /tmp/x"])
def test_hook_bash_dizin_dolambaclari_korumayi_delmemeli(komut):
    if hook.bash_degerlendir(komut).izin:
        _acik(f"izin verildi: {komut}")


@acik("Glob kapsamasi (`fnmatch(kalip, arguman)`) 'analysis/*/KILIT.md' kalibini desen olarak ALIR; "
      "'analysis/h1/*', 'analysis/h1/KIL*' gibi KILIT.md'ye genisleyen globlar eslesmez "
      "(tam yol girdilerinde 'data/spl*.csv' eslesir).")
@pytest.mark.parametrize("arguman", ["analysis/h1/*", "analysis/h1/KIL*", "analysis/h1/K?LIT.md",
                                     "analysis/h1/*.md"])
def test_hook_bash_glob_kilit_md_ye_genisleyen_yollari_kapsamali(arguman):
    kacan = [s.format(arguman) for s in ("rm {}", "rm -rf {}", "cp a {}") if hook.bash_degerlendir(s.format(arguman)).izin]
    if kacan:
        _acik(f"izin verilen komutlar: {kacan}")


def test_hook_bash_glob_tam_yol_girdileri_icin_hala_kapsar():
    """Kontrol: ayni glob teknigi eski girdilerde yakalaniyor (asimetrinin kaniti)."""
    for komut in ("rm data/spl*.csv", "rm PREREG*", "rm -rf data/*", "cp a data/spl?t.csv"):
        assert not hook.bash_degerlendir(komut).izin, komut


@acik("Desen girdisi icin yalin 'KILIT.md' eslesmez ve hook `cd`/`pushd` takip etmez: 'cd analysis/h1 && ... KILIT.md' "
      "gecer. Tam yol girdilerinde yalin ad yeterli oldugu icin ('cd /tmp && echo x > CLAUDE.md' reddedilir) "
      "yeni desen ESKI girdilerden zayif.")
@pytest.mark.parametrize("komut", ["cd analysis/h1 && echo x > KILIT.md", "cd analysis/h1; rm KILIT.md",
                                   "pushd analysis/h1 && sed -i s/a/b/ KILIT.md", "cd analysis/h1 && cp a KILIT.md",
                                   "cd analysis/h1 && python -c \"open('KILIT.md','w')\""])
def test_hook_bash_cd_ile_yalin_ad_kilit_md_yi_delmemeli(komut):
    if hook.bash_degerlendir(komut).izin:
        _acik(f"izin verildi: {komut}")


def test_hook_bash_cd_ile_yalin_ad_eski_girdilerde_reddedilir_kontrol():
    for komut in ("cd /tmp && echo x > CLAUDE.md", "cd data && rm split.csv", "cd sub && sed -i s/a/b/ ONAY_KAYDI.md"):
        assert not hook.bash_degerlendir(komut).izin, komut


@acik("`git -C <dizin> mv/rm <yalin ad>`: `_git_alt_komutu` -C argumanini atlar, konumsal arguman 'KILIT.md' "
      "yalin oldugu icin desenle eslesmez.")
@pytest.mark.parametrize("komut", ["git -C analysis/h1 rm KILIT.md", "git -C analysis/h1 mv yedek.md KILIT.md",
                                   "git -C analysis/h1 mv KILIT.md x.md"])
def test_hook_git_C_ile_yalin_ad_kilit_md_yi_delmemeli(komut):
    if hook.bash_degerlendir(komut).izin:
        _acik(f"izin verildi: {komut}")


@acik("`find ... -name KILIT.md -delete/-exec rm`, tam yol vermeden KILIT.md'yi siler; bilinmeyen komutta yalniz "
      "'analysis/<ad>/KILIT.md' bicimi aranir (tam yol girdilerinde dosya adi yeterliydi).")
@pytest.mark.parametrize("komut", ["find analysis -name KILIT.md -delete", "find analysis -name 'KILIT.md' -exec rm {} +",
                                   "find . -path '*/h1/*' -name KILIT.md -delete"])
def test_hook_find_ile_kilit_md_silme_yakalanmali(komut):
    if hook.bash_degerlendir(komut).izin:
        _acik(f"izin verildi: {komut}")


@acik("`python -c`/heredoc govdesinde yol parcali yazilirsa ('analysis','h1','KILIT.md' ya da d+'/KILIT.md') "
      "desen anma regexi ('analysis/<ad>/KILIT.md' bitisik) eslesmez; tam yol girdilerinde bos 'CLAUDE.md' adi "
      "anildigi icin yakalanirdi.")
@pytest.mark.parametrize("komut", [
    "python -c \"import pathlib; pathlib.Path('analysis','h1','KILIT.md').write_text('x')\"",
    "python -c \"d='analysis/h1'; open(d+'/KILIT.md','w').write('x')\"",
    "python - <<'EOF'\nfrom pathlib import Path\nPath('analysis/h1').joinpath('KILIT.md').write_text('x')\nEOF",
])
def test_hook_python_ile_parcali_yol_kilit_md_yazimi_yakalanmali(komut):
    if hook.bash_degerlendir(komut).izin:
        _acik(f"izin verildi: {komut[:60]!r}")


def test_hook_python_ile_parcali_yol_eski_girdilerde_yakalanir_kontrol():
    assert not hook.bash_degerlendir("python -c \"open('CLAUDE.md','w').write('x')\"").izin
    assert not hook.bash_degerlendir("python -c \"import os; open(os.path.join('data','split.csv'),'w')\"").izin


@acik("`sed` -i olmadan 'w dosya' komutu ve `awk` icinden yonlendirme dosyaya yazar; hook yalniz sed -i / awk -i "
      "inplace'i yazma sayar. (Yeni desene ozgu degil: CLAUDE.md icin de gecer.)")
@pytest.mark.parametrize("komut", ["sed -n 'w analysis/h1/KILIT.md' README.md",
                                   "awk 'BEGIN{print \"x\" > \"analysis/h1/KILIT.md\"}'",
                                   "sed -n 'w CLAUDE.md' README.md"])
def test_hook_sed_w_ve_awk_yonlendirmesi_yazma_sayilmali(komut):
    if hook.bash_degerlendir(komut).izin:
        _acik(f"izin verildi: {komut}")


def _hook_calistir(monkeypatch, capsys, girdi: dict) -> str:
    monkeypatch.delenv(hook.ACMA_DEGISKENI, raising=False)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(girdi)))
    assert hook.main() == 0
    return capsys.readouterr().out


def test_hook_main_bash_kontrolu_reddeder(monkeypatch, capsys):
    cikti = _hook_calistir(monkeypatch, capsys, {"tool_name": "Bash",
                                                 "tool_input": {"command": "echo x > analysis/h1/KILIT.md"}})
    assert '"deny"' in cikti


def test_hook_main_powershell_komutu_denetlenmeli(monkeypatch, capsys):
    girdi = {"tool_name": "PowerShell",
             "tool_input": {"command": "Set-Content -Path analysis/h1/KILIT.md -Value x"}}
    cikti = _hook_calistir(monkeypatch, capsys, girdi)
    assert '"deny"' in cikti, "PowerShell komutu kilitli dosyaya yazdi ve hook sessiz kaldi"


def test_hook_ayari_powershell_aracini_kapsamali():
    ayar = json.loads((KOK / ".claude" / "settings.json").read_text(encoding="utf-8"))
    eslestirici = ayar["hooks"]["PreToolUse"][0]["matcher"]
    assert "PowerShell" in eslestirici.split("|"), eslestirici


@pytest.mark.skipif(sys.platform != "win32", reason="NTFS ad esdegerlikleri yalniz Windows'ta")
@pytest.mark.parametrize("yol", ["analysis/h1/kilit.md", "analysis/h1/Kilit.Md"])
def test_hook_windows_buyuk_kucuk_harf_varyasyonu_ayni_dosyayi_gosterir(yol):
    if hook.bash_degerlendir(f"echo x > {yol}").izin:
        _acik(f"izin verildi: {yol}")


@pytest.mark.skipif(sys.platform != "win32", reason="NTFS ad esdegerlikleri yalniz Windows'ta")
@pytest.mark.parametrize("yol", ["analysis/h1/KILIT.md.", "analysis/h1/KILIT.md::$DATA"])
def test_hook_windows_sondaki_nokta_ve_veri_akisi_ayni_dosyayi_gosterir(yol):
    if hook.bash_degerlendir(f"echo x > {yol}").izin:
        _acik(f"izin verildi: {yol}")


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 GetFullPathName davranisi")
def test_hook_windows_write_yolunda_sondaki_nokta_resolve_ile_temizlenir():
    """Write/Edit tarafinda `Path.resolve()` sondaki noktayi temizler mi? (Bash tarafinin tersine.)"""
    if hook.kilitli_mi(str(KOK / "analysis" / "h1" / "KILIT.md.")) != DESEN:
        _acik("Write/Edit yolu: ad kismina eklenen sondaki nokta korunmuyor")
