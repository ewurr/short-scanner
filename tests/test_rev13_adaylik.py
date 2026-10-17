"""Adaylik ornekelemeden ONCE belirlenir (on-kayit §6, rev.13 (d)) + denetci bulgusu D-C5.

On-kayit §6 "Ornekleme kurallari" (rev.13): "Adaylik ornekelemeden once belirlenir: bir bar ya da
coin, §6'daki butun kontrol gereksinimlerini ve §4'teki tek karar noktasinin butun kosullarini
sagliyorsa adaydir; ornekleme yalnizca adaylar arasindan yapilir ve secilen bir aday sonradan
DUSMEZ. Gerekce: 'aday sayisi 10'dan azsa' kurali ancak adaylik ornekelemeden once tanimliysa
anlam tasir; once ornekleyip sonra elemek havuz boyutunu adaylarin varligina degil cekimin
sansina baglardi. Bunun sonucu olarak her olayin havuzu, aday sayisi yeterliyse tam 10 kontrol
icerir."

Kural rev.13'te SOZLESME duzeyine cikti: `ornekleme` ham bar damgasi ya da sembol adi kabul
etmez; adaylar tek karar noktasindan gecmis onaylardan `adaylari_kur` ile kurulur. D-C5: `ornekle`
tohumu cagirandan almaz (demetten turetir) ve `sayi` icin on-kayitin 10 degerinden baskasini
kabul etmez.

Aga cikmaz; getiri hesaplanmaz.
"""

from __future__ import annotations

import dataclasses

import pandas as pd
import pytest

import config
from data import ornekleme, pozisyon
from dizi_yardimcisi import olaylar_kur
from onay_yardimcisi import gecici_kayit, kosu
from ornekleme_yardimcisi import k1_adaylari_kur, k2_adaylari_kur, ornekle
from sinyal_yardimcisi import yapilandirma

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
UFUK = config.BIRINCIL_UFUK[config.BAR_4H]
BARLAR = [T("2025-03-01") + i * H4 for i in range(40)]
SEMBOLLER = [f"S{i:02d}USDT" for i in range(40)]
TB = T("2025-03-10 04:00")
Y2 = yapilandirma("H2")


def _onay(t=TB, rol="K1", **ek):
    return pozisyon._test_onayi(hipotez="H2", yapilandirma=Y2, t=t, rol=rol, **ek)


def _olay(sembol="AAAUSDT", t=TB, **ek):
    """Ornekelemenin olayi. Madde 3b'den beri `ornekle` olayin KENDISINI alir; sembol ve bar
    zamani ondan okunur ve adaylarla capraz dogrulanir."""
    return olaylar_kur([t], hipotez="H2", yapilandirma=Y2, kume="KESIF", sembol=sembol, **ek)[0]


# --- 1. Kapidan gecmemis aday kabul edilmez --------------------------------------------------


@pytest.mark.parametrize("ham", [BARLAR, SEMBOLLER, tuple(BARLAR), [], None, "AAAUSDT"])
def test_ham_liste_aday_degildir(ham):
    """"modul kapidan gecmemis bir adayi kabul etmesin": ham damga ya da sembol listesi reddedilir."""
    with pytest.raises(TypeError, match="adaylari_kur"):
        ornekleme.aday_dogrula(ham)
    with pytest.raises(TypeError):
        ornekleme.ornekle(ham, olay=_olay())
    with pytest.raises(TypeError):
        ornekleme.k1_adaylari(ham, [], UFUK, config.BAR_4H)
    with pytest.raises(TypeError):
        ornekleme.k2_adaylari(ham, [], olay_sembolu="AAAUSDT")


@pytest.mark.parametrize("nesne", ["onay_degil", 1.0, None, ("pozisyon", 1), object()])
def test_onayli_olmayan_nesne_aday_olamaz(nesne):
    with pytest.raises((TypeError, ValueError)):
        ornekleme.adaylari_kur([nesne], rol="K1")


def test_elle_degistirilmis_onay_aday_olamaz():
    gecerli = _onay()
    with pytest.raises(ValueError):
        ornekleme.adaylari_kur([dataclasses.replace(gecerli, p0=2.0)], rol="K1")


def test_elle_kurulmus_aday_kumesi_reddedilir():
    """`Adaylar` imzalidir: elle kurulan bir kume ornekelemeye giremez."""
    elle = ornekleme.Adaylar("K1", "H2", "H2:phi=0.0003,k=3", "KESIF", tuple(BARLAR))
    with pytest.raises(ValueError, match="elle kurulmus"):
        ornekleme.aday_dogrula(elle)
    with pytest.raises(ValueError):
        ornekleme.ornekle(elle, olay=_olay())


def test_olay_rolundeki_onay_aday_olamaz():
    """Kontrol ve olay roller ayridir (on-kayit §6 rev.11)."""
    with pytest.raises(ValueError, match="rol"):
        ornekleme.adaylari_kur([_onay(rol="olay")], rol="K1")
    with pytest.raises(ValueError, match="rol"):
        ornekleme.adaylari_kur([_onay(rol="K2")], rol="K1")
    with pytest.raises(ValueError, match="rol"):
        ornekleme.adaylari_kur([_onay(rol="K1")], rol="K2")


@pytest.mark.parametrize("rol", ["olay", "K3", "", None, 1])
def test_bilinmeyen_rol_reddedilir(rol):
    with pytest.raises(ValueError):
        ornekleme.adaylari_kur([], rol=rol)


# --- 2. Demet tutarliligi ---------------------------------------------------------------------


def test_karisik_yapilandirma_hipotez_ya_da_kume_reddedilir(tmp_path):
    """On-kayit §5, §6 rev.11: havuzlar yapilandirma basinadir.

    MADDE 1e ILE DEGISTI (denetci bulgusu D-C2): `_test_onayi` C1/C2 icin artik ACIK bir onay
    kosusu ister, bu yuzden C2 onayi bir `onay_kosusu` icinde kurulur. Iddia degismedi."""
    a = _onay()
    baskalar = [pozisyon._test_onayi(hipotez="H2", yapilandirma=yapilandirma("H2", k=12), t=TB, rol="K1"),
                pozisyon._test_onayi(hipotez="H1", yapilandirma=yapilandirma("H1"), t=TB, rol="K1")]
    yol = tmp_path / "onay_gecici.md"
    yol.write_text("bas\n", encoding="utf-8")
    gecici_kayit(yol)
    with kosu("H2", "C2"):
        baskalar.append(pozisyon._test_onayi(hipotez="H2", yapilandirma=Y2, t=T("2025-10-10 04:00"),
                                             rol="K1", kume="C2", sembol="TESTONAYUSDT"))
    for baska in baskalar:
        with pytest.raises(ValueError, match="ayni"):
            ornekleme.adaylari_kur([a, baska], rol="K1")


def test_k1_ayni_coin_k2_ayni_zaman():
    """K1 "ayni coin, rastgele zaman"; K2 "ayni zaman, rastgele coin" (on-kayit §6)."""
    with pytest.raises(ValueError, match="ayni coin"):
        ornekleme.adaylari_kur([_onay(sembol="AAAUSDT"), _onay(t=TB + H4, sembol="BBBUSDT")], rol="K1")
    with pytest.raises(ValueError, match="ayni t barindan"):
        ornekleme.adaylari_kur([_onay(rol="K2", sembol="AAAUSDT"),
                                _onay(t=TB + H4, rol="K2", sembol="BBBUSDT")], rol="K2")


def test_tekrarli_aday_reddedilir():
    with pytest.raises(ValueError, match="tekrarsiz"):
        k1_adaylari_kur([TB, TB])
    with pytest.raises(ValueError, match="tekrar"):
        k2_adaylari_kur(["AAAUSDT", "AAAUSDT"], t=TB)


# --- 3. Ayiklama ornekelemeden ONCE; secilen aday dusmez --------------------------------------


def test_ayiklayicilar_aday_kumesi_dondurur_ve_rolu_korur():
    k1 = ornekleme.k1_adaylari(k1_adaylari_kur(BARLAR), [], UFUK, config.BAR_4H)
    k2 = ornekleme.k2_adaylari(k2_adaylari_kur(SEMBOLLER, t=TB), [], olay_sembolu="ZZZUSDT")
    for kume, rol in ((k1, "K1"), (k2, "K2")):
        ornekleme.aday_dogrula(kume)
        assert kume.rol == rol and kume.hipotez == "H2"
    assert len(k1) == len(BARLAR) and len(k2) == len(SEMBOLLER)


def test_ayiklayicinin_ciktisi_dogrudan_ornekelemeye_girer():
    """Ayiklama -> ornekleme zinciri: ara adimda ham listeye dusulmez."""
    # Olay ve adaylar ayni coinden olmali (madde 3b): olay BARLAR[0] barinda, o bar ayiklama
    # sonrasi adaylar arasinda yok.
    ayiklanmis = ornekleme.k1_adaylari(k1_adaylari_kur(BARLAR),
                                       olaylar_kur([BARLAR[0]], sembol="AAVEUSDT"), UFUK,
                                       config.BAR_4H)
    havuz = ornekle(ayiklanmis, olay=olaylar_kur([BARLAR[0]], sembol="AAVEUSDT")[0])
    assert len(havuz) == config.KONTROL_SAYISI
    assert set(havuz.secilenler) <= set(ayiklanmis.ogeler)


@pytest.mark.parametrize("n", [0, 1, 5, 9, 10, 11, 25, 40])
def test_secilen_aday_sonradan_dusmez(n):
    """On-kayit §6 rev.13: "secilen bir aday sonradan dusmez" ve "her olayin havuzu, aday sayisi
    yeterliyse TAM 10 kontrol icerir"."""
    havuz = ornekle(k1_adaylari_kur(BARLAR[:n]))
    assert len(havuz) == min(config.KONTROL_SAYISI, n)
    assert havuz.aday_sayisi == n
    assert set(havuz.secilenler) <= set(BARLAR[:n])
    assert havuz.eksik is (n < config.KONTROL_SAYISI)


def test_bos_aday_kumesi_bos_havuz():
    havuz = ornekle(k2_adaylari_kur([], t=TB))
    assert havuz.secilenler == () and havuz.aday_sayisi == 0 and havuz.eksik


# --- 4. D-C5: tohum demetten turer, `sayi` on-kayit degeri -----------------------------------


@pytest.mark.parametrize("sayi", [1, 5, 9, 11, 40, 0, -1, True])
def test_on_kayit_disi_sayi_reddedilir(sayi):
    adaylar = k1_adaylari_kur(BARLAR, sembol="AAAUSDT")
    with pytest.raises(ValueError, match="on-kayit"):
        ornekleme.ornekle(adaylar, olay=_olay(), sayi=sayi)
    assert len(ornekleme.ornekle(adaylar, olay=_olay(),
                                 sayi=config.KONTROL_SAYISI)) == config.KONTROL_SAYISI


def test_tohum_cagirandan_alinmaz():
    """D-C5: serbest tohum verilemez; `ornekle` demetten turetir."""
    adaylar = k1_adaylari_kur(BARLAR, sembol="AAAUSDT")
    with pytest.raises(TypeError):
        ornekleme.ornekle(adaylar, tohum=1)
    with pytest.raises(TypeError):
        ornekleme.ornekle(adaylar, olay=_olay(), tohum=1)


def test_havuz_demetin_her_ogesine_duyarli():
    """Alt tohum (hipotez, yapilandirma, kume, sembol, olay zamani) demetinden turer."""
    temel = ornekle(k1_adaylari_kur(BARLAR, sembol="AAAUSDT"), olay_zamani=TB).secilenler
    assert ornekle(k1_adaylari_kur(BARLAR, sembol="BBBUSDT"), olay_zamani=TB).secilenler != temel
    assert ornekle(k1_adaylari_kur(BARLAR, sembol="AAAUSDT"), olay_zamani=TB + H4).secilenler != temel
    baska_y = ornekle(k1_adaylari_kur(BARLAR, sembol="AAAUSDT",
                                      yapilandirma=yapilandirma("H2", k=12)),
                      olay_zamani=TB).secilenler
    assert baska_y != temel
    # Ayni demet ayni havuz (tekrarlanabilirlik).
    assert ornekle(k1_adaylari_kur(BARLAR, sembol="AAAUSDT"), olay_zamani=TB).secilenler == temel


def test_alt_tohum_kimligi_de_kabul_eder():
    """`Adaylar` yapilandirma KIMLIGINI tasir; `alt_tohum` ikisini de ayni tohuma cevirir."""
    demet = ornekleme.alt_tohum("H2", Y2, "KESIF", "AAAUSDT", TB)
    kimlik = ornekleme.alt_tohum("H2", "H2:phi=0.0003,k=3", "KESIF", "AAAUSDT", TB)
    assert demet == kimlik
    with pytest.raises(ValueError):
        ornekleme.alt_tohum("H2", "H1:theta=0.2,delta=0.08", "KESIF", "AAAUSDT", TB)
