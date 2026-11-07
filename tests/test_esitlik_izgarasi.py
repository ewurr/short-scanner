"""Esitlik betiginin sinyal izgarasi ve takvim izgarasi taramasi (RESULTS §14.47; teshis §14.46).

`esitlik_kapi.bar_izgarasi` takvimden izgara kurmaz, `pozisyon.hipotez_izgarasi_barlari`ni kullanir. §14.46'da takvim
izgarasi yarim son gunu kapiya veriyordu ve iki taraf ayni `DonemDisiSinyal` ile dusuyordu. Sentetik dunya; aga
cikmaz, deger okunmaz.
"""

from __future__ import annotations

import sys

import pandas as pd
import pytest

from data import pencere, pozisyon, sinyal
from esitlik_yardimcisi import dunya
from tarama_yardimcisi import (KOK, TAKVIM_IZGARASI_IZINLI_DOSYALAR, takvim_izgarasi_ihlalleri)

sys.path.insert(0, str(KOK / "analysis" / "00_veri_denetimi"))
import esitlik_kapi as ek  # noqa: E402

BAS = "2021-01-01"
YARIM_SON = "2021-11-26 08:00"     # B 08:00: son gunun 3/6 bari donem ici
SON_GUN = pd.Timestamp("2021-11-26", tz="UTC")


@pytest.fixture(scope="module")
def yarim_dunya():
    return dunya(11, BAS, YARIM_SON)[0]


def test_betigin_1d_izgarasi_yarim_son_gunu_icermez(yarim_dunya):
    izgara = ek.bar_izgarasi(yarim_dunya, "H3")
    assert SON_GUN not in izgara and izgara[-1] == SON_GUN - pd.Timedelta(days=1)
    assert list(izgara) == list(pozisyon.hipotez_izgarasi_barlari("H3", kume=ek.KUME, **yarim_dunya))
    bas, bitis, _ = pozisyon.donem_kaydi(yarim_dunya["sembol"], yarim_dunya["donem_no"])
    assert all(pencere.donem_ici_mi(t, "1d", donem_baslangic=bas, donem_bitis=bitis) for t in izgara)


def test_takvim_izgarasi_o_gunu_kapiya_verirdi(yarim_dunya):
    """Karsi ornek: eski takvim izgarasinin son gunu kapida iki tarafta da `DonemDisiSinyal` (beklenmeyen hata)."""
    y = dict(sinyal.izgara("H3")[0])
    sonuc = ek.karar(pozisyon, "H3", y, "K1", SON_GUN, yarim_dunya, 0)
    assert isinstance(sonuc, pencere.DonemDisiSinyal) and ek.beklenmeyen(sonuc)


@pytest.mark.parametrize("rol", ["K1", "olay"])
def test_yarim_son_gunlu_donemde_tam_izgara_beklenmeyen_hata_vermez(yarim_dunya, rol):
    izgara = ek.bar_izgarasi(yarim_dunya, "H3")
    y = dict(sinyal.izgara("H3")[0])
    sayac = ek.karsilastir(list(izgara), list(range(len(izgara))), "H3", y, rol, yarim_dunya)
    assert sayac.karsilastirilan == len(izgara) > 100
    assert len(sayac.uyusmayan) == 0
    assert sayac.beklenmeyen_referans == sayac.beklenmeyen_yeni == 0


@pytest.mark.parametrize("hipotez", ["H1", "H2"])
def test_4h_izgarasi_dunyadaki_eksik_barlari_icermez(yarim_dunya, hipotez):
    """Sentetik dunyada 60. gunden 3 gun ve 100. gunde tek bar eksik, 120. gunde bozuk hucreli bar var: izgarada yoklar."""
    izgara = ek.bar_izgarasi(yarim_dunya, hipotez)
    bas, bitis, _ = pozisyon.donem_kaydi(yarim_dunya["sembol"], yarim_dunya["donem_no"])
    takvim = pd.date_range(bas, bitis, freq="4h")
    eksik = set(takvim) - set(izgara)
    assert izgara[0] == bas and izgara[-1] == bitis
    assert len(eksik) == 3 * 6 + 1 + 1


# --- Takvim izgarasi taramasi ---------------------------------------------------------------------------------

def test_depoda_takvim_izgarasi_yok():
    assert takvim_izgarasi_ihlalleri() == []


def test_muafiyet_listesi_bos_ve_acik_adli():
    assert TAKVIM_IZGARASI_IZINLI_DOSYALAR == frozenset()


@pytest.mark.parametrize("metin", [
    'pd.date_range(bas.ceil("D"), bitis, freq="1D")\n',
    "pd.date_range(a, b, freq='D')\n",
    'pd.date_range(start=a, end=b, freq="d")\n',
    'pd.date_range(a, b, freq="24h")\n',
    "pd.date_range(a, b, freq=pd.Timedelta(days=1))\n",
    'pd.date_range(a, b, freq=Timedelta("1D"))\n',
    'pd.date_range(\n    max(bas, kb).ceil("D"),\n    min(bitis, ks),\n    freq="1D",\n)\n',
])
@pytest.mark.parametrize("dizin", ["study", "events", "analysis/h3", "analysis/00_veri_denetimi"])
def test_takvim_izgarasi_analiz_kodunda_yakalanir(tmp_path, metin, dizin):
    hedef = tmp_path / dizin
    hedef.mkdir(parents=True)
    (hedef / "k.py").write_text("import pandas as pd\n" + metin, encoding="utf-8")
    assert takvim_izgarasi_ihlalleri(kok=tmp_path) == [f"{dizin}/k.py"]


@pytest.mark.parametrize("metin", [
    'pd.date_range(a, b, freq="4h")\n',
    "pd.date_range(a, b, freq=pd.Timedelta(hours=4))\n",
    "pozisyon.hipotez_izgarasi_barlari('H3', kume='KESIF', sembol=s, donem_no=0)\n",
    'pd.date_range(a, b, freq="8h")\n',
])
def test_4h_izgarasi_ve_yardimci_yakalanmaz(tmp_path, metin):
    (tmp_path / "study").mkdir()
    (tmp_path / "study" / "k.py").write_text(metin, encoding="utf-8")
    assert takvim_izgarasi_ihlalleri(kok=tmp_path) == []


@pytest.mark.parametrize("dizin", ["data", "tests"])
def test_veri_katmani_ve_testler_disarida(tmp_path, dizin):
    (tmp_path / dizin).mkdir()
    (tmp_path / dizin / "k.py").write_text('pd.date_range(a, b, freq="1D")\n', encoding="utf-8")
    assert takvim_izgarasi_ihlalleri(kok=tmp_path) == []
