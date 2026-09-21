"""On-kayit §2 rev.8 "Listeleme donemi" (B, K) ve §6 rev.8 "Donem uyeligi". Aga cikmaz.

- K = B + 4 saat tek yerde (`pencere.donem_kapanisi`); baska modul B + 4 saati
  yeniden hesaplamaz.
- Tek "donem ici bar" yuklemi (`pencere.donem_ici_mi`): 4h barda acilis
  [donem basi, B]; 1d barda gunun alti 4h barinin tamami donem ici.
- `eligibility.uygun_mu` ve `pencere.pozisyon_plani` bu yuklemi kullanir.
"""

from __future__ import annotations

import re

import pandas as pd
import pytest

import config
from data import eligibility, pencere
from data.donem import Donem

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
DK = pd.Timedelta(minutes=1)
NS = pd.Timedelta(1, "ns")
BAS, B = T("2025-01-01 08:00"), T("2025-03-10 08:00")
D = Donem(BAS, B, 100, 100)


def test_k_b_arti_dort_saat_tek_tanim():
    assert pencere.donem_kapanisi(B) == T("2025-03-10 12:00")
    assert D.kapanis == pencere.donem_kapanisi(D.bitis)


def test_baska_modul_b_arti_dort_saati_hesaplamaz():
    """`data/` ve `analysis/00_veri_denetimi/` kaynaklarinda donem bitisine 4 saat
    ya da bar adimi eklenmez; K yalnizca `donem_kapanisi`ndan gelir."""
    desen = re.compile(r"bitis\s*\+\s*(ADIM|adim|pd\.Timedelta\(hours=4\)|pencere_modulu\.adim)")
    kaynaklar = list((config.KOK / "data").glob("*.py")) + list((config.ANALIZ_DIZINI / "00_veri_denetimi").glob("*.py"))
    ihlal = [p.name for p in kaynaklar if p.name != "pencere.py" and desen.search(p.read_text(encoding="utf-8"))]
    assert ihlal == []


@pytest.mark.parametrize("t,beklenen", [
    (BAS, True), (B, True), (BAS - pd.Timedelta(hours=4), False), (B + pd.Timedelta(hours=4), False),
    (BAS - DK + NS, True), (BAS - DK, False),  # zaman toleransi (rev.8 §4)
    (B + DK - NS, True), (B + DK, False),
])
def test_4h_uyelik(t, beklenen):
    assert pencere.donem_ici_mi(t, config.BAR_4H, donem_baslangic=BAS, donem_bitis=B) is beklenen
    assert D.ici_mi(t, config.BAR_4H) is beklenen


@pytest.mark.parametrize("gun,beklenen", [
    ("2025-01-01", False),  # donem 08:00'de basliyor: 00:00 ve 04:00 barlari donem disi
    ("2025-01-02", True),
    ("2025-03-09", True),
    ("2025-03-10", False),  # B 08:00: 12:00-20:00 barlari donem disi (kismi son gun)
])
def test_1d_uyelik_alti_barin_tamami(gun, beklenen):
    assert pencere.donem_ici_mi(T(gun), config.BAR_1D, donem_baslangic=BAS, donem_bitis=B) is beklenen


def test_1d_uyelik_son_bar_20_de_bitiyorsa_tam_gun():
    b20 = T("2025-03-10 20:00")
    assert pencere.donem_ici_mi(T("2025-03-10"), config.BAR_1D, donem_baslangic=BAS, donem_bitis=b20)
    b16 = T("2025-03-10 16:00")
    assert not pencere.donem_ici_mi(T("2025-03-10"), config.BAR_1D, donem_baslangic=BAS, donem_bitis=b16)


def test_1d_uyelik_gun_acilisi_olmayan_zaman_hata():
    with pytest.raises(ValueError):
        pencere.donem_ici_mi(T("2025-01-05 04:00"), config.BAR_1D, donem_baslangic=BAS, donem_bitis=B)


def _hacim():
    gunler = pd.date_range(T("2024-11-01"), T("2025-03-10"), freq="1D")
    return pd.Series(50_000_000.0, index=gunler)


def test_uygunluk_kismi_son_gunu_reddeder():
    """1d t = kismi son gun: rev.7'de gun acilisi <= B oldugu icin donem ici sayiliyordu."""
    ortak = dict(donem_baslangic=T("2024-11-01"), donem_bitis=B, kume_baslangic=None)
    assert eligibility.uygun_mu(_hacim(), T("2025-03-09"), config.BAR_1D, **ortak)
    assert not eligibility.uygun_mu(_hacim(), T("2025-03-10"), config.BAR_1D, **ortak)
    # 4h ızgarasında ayni gunun B'deki bari donem ici
    assert eligibility.uygun_mu(_hacim(), B, config.BAR_4H, **ortak)


def test_plan_donem_disi_sinyali_programlama_hatasi_sayar():
    gunler = pd.date_range(T("2025-02-01"), T("2025-03-10"), freq="1D")
    with pytest.raises(pencere.DonemDisiSinyal):
        pencere.pozisyon_plani(gunler, T("2025-03-10"), 1, config.BAR_1D, birincil_ufuk=14,
                               kume_baslangic=None, kume_bitis=None, donem_baslangic=BAS, donem_bitis=B)
    assert not issubclass(pencere.DonemDisiSinyal, pencere.OlayOlusmaz)
