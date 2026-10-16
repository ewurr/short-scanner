"""Denetci bulgusu D-C2: test dikisinin omru testle sinirli, onay kumesi acik kosu ister.

`pozisyon._test_onayi` dizi kurallarini sinayan testlere veri yuklemeden imzali bir onay verir
(rev.13 madde 3b'nin bedeli). Denetci iki noktada `split._test_kaydi_ayarla` deseninden
ayristigini saptadi:

  (i) `_test_kaydi_ayarla` kurdugu ayari TESTIN KIMLIGINE baglar ve test bitince ayar
      kendiliginden gecersizlesir; dikisin urettigi nesnenin boyle bir omur siniri yoktu, ayni
      oturumdaki baska bir testte de gecerliydi.
  (ii) Dikis `kume="C1"/"C2"` kabul ediyordu, yani pytest icinde ACIK bir onay kosusu olmadan
      imzali bir C1/C2 "olayi" kurulabiliyordu. Veri okunmadigi icin §3'un veri yasagi
      delinmiyordu, ama "C1/C2 pozisyonu yalnizca acik onay kosusunda olusur" degismezi
      (CLAUDE.md §3.3; kapi sertlestirme turu 3) test baglaminda deliniyordu.

Ikisi de kapatildi. Gercek bir F2/F3 kosusunda dikis zaten kapalidir (`split._pytest_testi`).

Aga cikmaz; getiri hesaplanmaz.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import dizi, pozisyon, split
from onay_yardimcisi import gecici_kayit, kosu
from sinyal_yardimcisi import yapilandirma

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
Y2 = yapilandirma("H2")
TB = T("2025-03-10 04:00")
TC2 = T("2025-10-10 04:00")          # C2 tarih araligi
UFUK = config.BIRINCIL_UFUK[config.BAR_4H]

# Omur testinin iki testi arasinda tasinan nesne (dosya sirasi: once kuran test kosar).
_BASKA_TESTTE_KURULAN: list = []


@pytest.fixture
def kayit(tmp_path):
    yol = tmp_path / "onay_gecici.md"
    yol.write_text("bas\n", encoding="utf-8")
    gecici_kayit(yol)
    return yol


def _onay(**ek):
    return pozisyon._test_onayi(hipotez="H2", yapilandirma=Y2, t=TB, **ek)


# --- 1. Onay kumesi: acik kosu sart -----------------------------------------------------------


@pytest.mark.parametrize("kume", ["C1", "C2"])
def test_acik_kosu_olmadan_onay_kumesi_dikisi_reddedilir(kume, kayit):
    t = TB if kume == "C1" else TC2
    with pytest.raises(split.OnayGerekli):
        pozisyon._test_onayi(hipotez="H2", yapilandirma=Y2, t=t, kume=kume)


@pytest.mark.parametrize("kume", ["C1", "C2"])
def test_acik_kosu_icinde_dikis_calisir(kume, kayit):
    t = TB if kume == "C1" else TC2
    with kosu("H2", kume):
        onay = pozisyon._test_onayi(hipotez="H2", yapilandirma=Y2, t=t, kume=kume)
    pozisyon.onay_dogrula(onay)
    assert onay.kume == kume


def test_baska_kumenin_kosusu_dikisi_acmaz(kayit):
    """Acik kosu (H2, C1) iken C2 ve KESIF pozisyonu kurulamaz (kapi sertlestirme turu 3)."""
    with kosu("H2", "C1"):
        with pytest.raises(split.OnayUyusmazligi):
            pozisyon._test_onayi(hipotez="H2", yapilandirma=Y2, t=TC2, kume="C2")
        with pytest.raises(split.OnayUyusmazligi):
            _onay(kume="KESIF")


def test_baska_hipotezin_kosusu_dikisi_acmaz(kayit):
    with kosu("H1", "C1"):
        with pytest.raises(split.OnayUyusmazligi):
            pozisyon._test_onayi(hipotez="H2", yapilandirma=Y2, t=TB, kume="C1")


def test_kesif_dikisi_kosu_istemez(kayit):
    """KESIF serbesttir (on-kayit §3): dikis acik kosu olmadan da KESIF onayi kurar."""
    onay = _onay(kume="KESIF")
    pozisyon.onay_dogrula(onay)
    assert onay.kume == "KESIF"


# --- 2. Omur: nesne yalnizca kendi testinde gecerli -------------------------------------------


def test_a_omur_kuran_test():
    """Bu test bir onay kurar ve sonraki teste tasir (dosya sirasi onemlidir)."""
    onay = _onay()
    pozisyon.onay_dogrula(onay)                    # kendi testinde gecerli
    _BASKA_TESTTE_KURULAN.append(onay)


def test_b_baska_testte_kurulan_onay_reddedilir():
    """Dikisin urettigi nesnenin omru onu kuran testle sinirlidir (denetci bulgusu D-C2)."""
    assert _BASKA_TESTTE_KURULAN, "kurulum testi once kosmali"
    onay = _BASKA_TESTTE_KURULAN[0]
    with pytest.raises(ValueError, match="BASKA bir testte"):
        pozisyon.onay_dogrula(onay)


def test_c_baska_testte_kurulan_onay_dizi_ve_havuza_da_giremez():
    from data import ornekleme

    onay = _BASKA_TESTTE_KURULAN[0]
    with pytest.raises(ValueError, match="BASKA bir testte"):
        ornekleme.adaylari_kur([onay], rol="K1")
    # Ayni nesneyi tasiyan bir olay da gecersizdir: `olay_dogrula` onayi yeniden dogrular (1c).
    def karar(t, capa):
        return onay

    with pytest.raises(ValueError, match="BASKA bir testte"):
        dizi.olay_dizisi("H2", Y2, pd.DatetimeIndex([TB]), config.BAR_4H, birincil_ufuk=UFUK,
                         kosul=lambda t, capa: True, karar=karar,
                         sembol=onay.sembol, kume=onay.kume, donem_no=onay.donem_no)


def test_ayni_test_icinde_yeniden_dogrulama_calisir():
    """Omur siniri testin ICINDE hicbir seyi kisitlamaz: nesne istenildigi kadar dogrulanir."""
    onay = _onay()
    for _ in range(3):
        pozisyon.onay_dogrula(onay)


def test_gercek_kapinin_onayi_omur_kaydina_girmez():
    """Kayit yalnizca dikisin urettigi nesneler icindir; gercek onaylar etkilenmez.

    Dikis kaydi `pozisyon._TEST_ONAY_OMURLERI` sozlugudur ve yalnizca `_test_onayi` doldurur."""
    onay = _onay()
    assert onay._imza in pozisyon._TEST_ONAY_OMURLERI
    assert pozisyon._TEST_ONAY_OMURLERI[onay._imza] == split._pytest_testi()


# --- 3. Onceki korumalar korundu --------------------------------------------------------------


def test_dikis_adi_taramada_yasakli():
    """`tarama_yardimcisi.ONAY_ATLATMA_DESENI` dikisi analiz kodunda yasaklar."""
    import tarama_yardimcisi

    assert "_test_onayi" in tarama_yardimcisi.ONAY_ATLATMA_DESENI


def test_pytest_disinda_dikis_calismaz():
    """Birinci koruma (rev.13) korundu: PYTEST_CURRENT_TEST yoksa dikis calismaz."""
    with pytest.MonkeyPatch.context() as yama:
        yama.delenv("PYTEST_CURRENT_TEST", raising=False)
        with pytest.raises(RuntimeError, match="yalnizca bir pytest testi"):
            _onay()
