"""Denetci bulgusu D-B1: K1 adaylari ayni LISTELEME DONEMI icinden olmali (on-kayit §6 K1).

On-kayit §6 K1: "Ayni coinden, ayni kume ve donem icinden, o hipotezin herhangi bir olayina
birincil ufuk mesafesinden yakin olmayan ... 10 rastgele bar." §6 "Donem uyeligi" (rev.8) K1'in bu
olcutu kullandigini ayrica yazar.

Bulgu: `ornekleme.adaylari_kur` sembol birligini ve (hipotez, yapilandirma, kume) birligini
denetliyordu, `donem_no` birligini denetlemiyordu. Iki listeleme donemi olan bir coinde (delist
sonrasi yeniden listelenen) baska donemin bari K1 havuzuna girebiliyordu; bar kapidan gecmis
oldugu icin hicbir yerde dusmezdi.

Aga cikmaz; getiri hesaplanmaz.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import ornekleme, pozisyon
from ornekleme_yardimcisi import k1_adaylari_kur, k2_adaylari_kur, ornekle
from sinyal_yardimcisi import yapilandirma

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
Y2 = yapilandirma("H2")
BARLAR = [T("2025-03-01") + i * H4 for i in range(12)]


def _onay(t, *, donem_no=0, rol="K1", sembol="AAVEUSDT"):
    return pozisyon._test_onayi(hipotez="H2", yapilandirma=Y2, t=t, rol=rol, sembol=sembol,
                                kume="KESIF", donem_no=donem_no)


# --- 1. Karisik donem reddedilir ---------------------------------------------------------------


def test_karisik_donem_reddedilir():
    """Ayni sembolun iki listeleme donemi: adaylar tek bir donemden olmali."""
    with pytest.raises(ValueError, match="ayni donem"):
        ornekleme.adaylari_kur([_onay(BARLAR[0], donem_no=0), _onay(BARLAR[1], donem_no=1)], rol="K1")


@pytest.mark.parametrize("donemler", [(0, 1), (1, 0), (0, 0, 2), (3, 3, 3, 4)])
def test_her_karisim_reddedilir(donemler):
    onaylar = [_onay(BARLAR[i], donem_no=d) for i, d in enumerate(donemler)]
    with pytest.raises(ValueError, match="ayni donem"):
        ornekleme.adaylari_kur(onaylar, rol="K1")


def test_hata_mesaji_donem_numaralarini_yazar():
    with pytest.raises(ValueError) as hata:
        ornekleme.adaylari_kur([_onay(BARLAR[0], donem_no=0), _onay(BARLAR[1], donem_no=7)], rol="K1")
    assert "[0, 7]" in str(hata.value)


# --- 2. Tek donem gecer; donem numarasinin kendisi onemli degil --------------------------------


@pytest.mark.parametrize("donem_no", [0, 1, 5])
def test_tek_donem_gecer(donem_no):
    adaylar = ornekleme.adaylari_kur([_onay(t, donem_no=donem_no) for t in BARLAR[:4]], rol="K1")
    ornekleme.aday_dogrula(adaylar)
    assert len(adaylar) == 4


def test_bos_aday_kumesi_donem_denetiminden_etkilenmez():
    adaylar = ornekleme.adaylari_kur([], rol="K1")
    assert len(adaylar) == 0


# --- 3. Ayiklama ve ornekleme zinciri bozulmadi -----------------------------------------------


def test_zincir_tek_donemle_calisir():
    adaylar = ornekleme.adaylari_kur([_onay(t, donem_no=2) for t in BARLAR], rol="K1")
    ayiklanmis = ornekleme.k1_adaylari(adaylar, [BARLAR[0]], config.BIRINCIL_UFUK[config.BAR_4H],
                                       config.BAR_4H)
    havuz = ornekle(ayiklanmis)
    assert len(havuz) == min(config.KONTROL_SAYISI, len(ayiklanmis))
    assert set(havuz.secilenler) <= set(ayiklanmis.ogeler)


def test_sembol_birligi_denetimi_korundu():
    """Donem denetimi eklendi, sembol denetimi kaldirilmadi (on-kayit §6 K1 "ayni coin")."""
    with pytest.raises(ValueError, match="ayni coin"):
        ornekleme.adaylari_kur([_onay(BARLAR[0], sembol="AAAUSDT"),
                                _onay(BARLAR[1], sembol="BBBUSDT")], rol="K1")


# --- 4. K2: "ayni zaman, rastgele coin" -- donem birligi ARANMAZ -------------------------------


def test_k2_de_donem_birligi_aranmaz():
    """On-kayit §6 K2 "ayni barda, DIGER coinlerden": farkli coinlerin donem numaralari farkli
    olabilir, cunku donem numarasi sembole goredir. Denetim K1'e ozgudur."""
    t = T("2025-03-10 04:00")
    onaylar = [_onay(t, rol="K2", sembol="AAAUSDT", donem_no=0),
               _onay(t, rol="K2", sembol="BBBUSDT", donem_no=3)]
    adaylar = ornekleme.adaylari_kur(onaylar, rol="K2")
    assert adaylar.ogeler == ("AAAUSDT", "BBBUSDT")
    # Yardimcinin varsayilan yolu da bozulmadi.
    assert len(k2_adaylari_kur(["CUSDT", "DUSDT"], t=t)) == 2
    assert len(k1_adaylari_kur(BARLAR[:3])) == 3
