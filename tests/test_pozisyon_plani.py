"""Tek kapi testleri: `pencere.pozisyon_plani` (on-kayit §4 rev.7, D3 birinci yol).

"Bir olayin kumede olusup olusmadigina tek bir karar noktasi hukmeder ve olcut
cikis anina gore uygulanir: cikis ani ile funding tolerans payi birlikte kume
sonunu asmamalidir. Fiyat ve funding icin ayri olcut kullanilmaz."

Korumalar:
  - Ozellik testi: kume sonuna yakin zaman izgarasinda (4h ve 1d, birincil ve
    ikincil ufuklar, eksik barlar, donem sonu) on eleme reddettiyse plan da
    reddeder; plan kabul ettiyse on eleme de kabul etmistir, cikis ani + tolerans
    kume icindedir ve funding hesabi kume hatasi vermez.
  - Kaynak taramasi: analiz kodu cikis_bari / ufuk_kumeye_sigar_mi / cikis_ani'yi
    dogrudan cagirmaz, CikisSonucu ya da PozisyonPlani kurmaz.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import config
from data import funding, pencere, split
from tarama_yardimcisi import CIKIS_KAPI_DISI_DESENI, ihlaller

DORT_SAAT = pd.Timedelta(hours=4)
SINIRSIZ = dict(kume_baslangic=None, kume_bitis=None, donem_baslangic=None, donem_bitis=None)
KESIF_BAS, KESIF_SON = split.kume_araligi("KESIF")
C2_BAS, C2_SON = split.kume_araligi("C2")


def _izgara(bas, adet, bar=config.BAR_4H):
    return pd.date_range(bas, periods=adet, freq=pencere.adim(bar), tz="UTC")


def _plan(zamanlar, t, ufuk=18, bar=config.BAR_4H, birincil=18, **sinirlar):
    return pencere.pozisyon_plani(zamanlar, t, ufuk, bar, birincil_ufuk=birincil, **{**SINIRSIZ, **sinirlar})


# --- Temel -------------------------------------------------------------------


def test_plan_alanlari():
    z = _izgara("2021-01-01", 60)
    plan = _plan(z, z[4])
    assert plan.sinyal_zamani == z[4] and plan.giris == z[5]
    assert plan.cikis.zaman == z[22] and plan.cikis.fiyat_alani == "close"
    assert plan.cikis_ani == z[23] and plan.ufuk == 18 and plan.birincil_ufuk == 18
    pencere.plan_dogrula(plan)


def test_hata_siniflari_olay_olusmaz_altinda():
    for sinif in (pencere.KumeSiniriHatasi, pencere.IleriKaymaSiniriHatasi, pencere.GirisBariYok):
        assert issubclass(sinif, pencere.OlayOlusmaz) and issubclass(sinif, ValueError)
    assert not issubclass(pencere.ZamanDizisiHatasi, pencere.OlayOlusmaz)
    assert split.KumeSiniriHatasi is pencere.KumeSiniriHatasi


def test_giris_bari_eksikse_olay_olusmaz():
    z = _izgara("2021-01-01", 60)
    with pytest.raises(pencere.GirisBariYok):
        _plan(z.drop(z[5]), z[4])


def test_giris_bari_donem_disindaysa_olay_olusmaz():
    z = _izgara("2021-01-01", 60)
    with pytest.raises(pencere.GirisBariYok):
        _plan(z, z[4], donem_bitis=z[4])
    assert _plan(z, z[4], donem_bitis=z[5]).cikis.kirpma_nedeni == "donem_sonu"


def test_ileri_kayma_siniri_plandan_gecer():
    z = _izgara("2021-01-01", 120)
    hedef = pencere.cikis_hedefi(z[5], 18, config.BAR_4H)
    eksik = z.drop(pd.date_range(hedef, periods=19, freq="4h"))
    with pytest.raises(pencere.IleriKaymaSiniriHatasi):
        _plan(eksik, z[4])


def test_sinyal_donem_basindan_onceyse_programlama_hatasi():
    z = _izgara("2021-01-01", 60)
    with pytest.raises(ValueError) as hata:
        _plan(z, z[4], donem_baslangic=z[5])
    assert not isinstance(hata.value, pencere.OlayOlusmaz)


def test_sinyal_kume_basindan_onceyse_olay_olusmaz():
    z = pd.date_range(C2_BAS - 10 * DORT_SAAT, periods=60, freq="4h")
    with pytest.raises(pencere.KumeSiniriHatasi):
        _plan(z, C2_BAS - DORT_SAAT, kume_baslangic=C2_BAS)
    assert _plan(z, C2_BAS, kume_baslangic=C2_BAS).giris == C2_BAS + DORT_SAAT


@pytest.mark.parametrize("bar,ufuk", [(config.BAR_4H, 18), (config.BAR_4H, 6), (config.BAR_1D, 14)])
def test_kumenin_son_barinda_biten_ufuk_reddedilir(bar, ufuk):
    """Rev.7: son barin kapanisi (09-01 00:00) C2'ye duser; bir bar once kabul."""
    a = pencere.adim(bar)
    son_bar = KESIF_SON.floor("D") if bar == config.BAR_1D else KESIF_SON.floor("4h")
    z = pd.date_range(end=son_bar + 10 * a, periods=120, freq=a)
    t_son = son_bar - ufuk * a  # hedef cikis bari = son_bar
    with pytest.raises(pencere.KumeSiniriHatasi):
        _plan(z, t_son, ufuk=ufuk, bar=bar, kume_bitis=KESIF_SON)
    plan = _plan(z, t_son - a, ufuk=ufuk, bar=bar, kume_bitis=KESIF_SON)
    assert plan.cikis.zaman == son_bar - a


# --- Zorunluluk ve tipler ----------------------------------------------------


@pytest.mark.parametrize("eksik", ["birincil_ufuk", *SINIRSIZ])
def test_parametre_unutulursa_hata(eksik):
    z = _izgara("2021-01-01", 60)
    parametreler = {**SINIRSIZ, "birincil_ufuk": 18}
    del parametreler[eksik]
    with pytest.raises(TypeError):
        pencere.pozisyon_plani(z, z[4], 18, config.BAR_4H, **parametreler)


@pytest.mark.parametrize("alan", ["sinyal", "kume_bitis", "donem_baslangic"])
def test_saat_dilimsiz_zaman_reddedilir(alan):
    z = _izgara("2021-01-01", 60)
    t = z[4]
    parametreler = dict(SINIRSIZ)
    if alan == "sinyal":
        t = t.tz_localize(None)
    else:
        parametreler[alan] = pd.Timestamp("2021-12-31")
    with pytest.raises(TypeError):
        pencere.pozisyon_plani(z, t, 18, config.BAR_4H, birincil_ufuk=18, **parametreler)


@pytest.mark.parametrize("ufuk", [0, -1])
def test_ufuk_birden_kucukse_hata(ufuk):
    z = _izgara("2021-01-01", 60)
    with pytest.raises(ValueError):
        _plan(z, z[4], ufuk=ufuk)


def test_plan_disarida_kurulamaz():
    z = _izgara("2021-01-01", 60)
    plan = _plan(z, z[4])
    import dataclasses

    with pytest.raises(ValueError):
        pencere.plan_dogrula(dataclasses.replace(plan, ufuk=6))
    with pytest.raises(TypeError):
        pencere.plan_dogrula(plan.cikis)


# --- Ozellik testi: on eleme, plan ve funding ayni hukmu verir ---------------


def _tam_funding(bas, son):
    zaman = pd.date_range(bas, son, freq="8h")
    fr = pd.DataFrame({"odeme_zamani": zaman, "aralik_saat": 8.0, "oran": 1e-4})
    fr["oran_8h"] = fr["oran"]
    return fr


@pytest.mark.parametrize("kume", ["KESIF", "C2"])
@pytest.mark.parametrize("bar,ufuklar,birincil", [(config.BAR_4H, (6, 18, 42), 18), (config.BAR_1D, (7, 14, 30), 14)])
@pytest.mark.parametrize("senaryo", ["tam", "eksik_barlar", "donem_sonu_icinde"])
def test_on_eleme_plan_ve_funding_tutarli(kume, bar, ufuklar, birincil, senaryo):
    kume_bas, kume_son = split.kume_araligi(kume)
    a = pencere.adim(bar)
    son_bar = kume_son.floor("D") if bar == config.BAR_1D else kume_son.floor("4h")
    z = pd.date_range(end=son_bar + 60 * a, periods=260, freq=a)
    donem_bitis = None
    if senaryo == "eksik_barlar":
        rng = np.random.default_rng(config.TOHUM)
        sil = z[rng.random(len(z)) < 0.08]
        z = z.drop(sil)
    elif senaryo == "donem_sonu_icinde":
        donem_bitis = son_bar - 3 * a
    fund = _tam_funding(z[0] - pd.Timedelta(days=2), z[-1] + pd.Timedelta(days=2))
    sinirlar = dict(kume_baslangic=kume_bas, kume_bitis=kume_son, donem_baslangic=None, donem_bitis=donem_bitis)

    kontrol = 0
    for ufuk in ufuklar:
        for t in pd.date_range(son_bar - (ufuk + 30) * a, son_bar + 5 * a, freq=a):
            on = pencere.ufuk_kumeye_sigar_mi(t, ufuk, bar, kume_baslangic=kume_bas, kume_bitis=kume_son)
            try:
                plan = pencere.pozisyon_plani(z, t, ufuk, bar, birincil_ufuk=birincil, **sinirlar)
            except pencere.KumeSiniriHatasi:
                continue
            except (pencere.GirisBariYok, pencere.IleriKaymaSiniriHatasi):
                continue
            finally:
                kontrol += 1
            assert on, (t, ufuk, "plan kabul etti ama on eleme reddetmisti")
            assert plan.cikis_ani + funding.ODEME_TOLERANSI - pd.Timedelta(1, "ns") <= kume_son
            assert plan.sinyal_zamani >= kume_bas
            deger = funding.pozisyon_fundingi(fund, plan)  # kume hatasi olamaz
            assert isinstance(deger, float)
        # on eleme reddettiyse plan kesin reddeder
        for t in pd.date_range(son_bar - (ufuk + 30) * a, son_bar + 5 * a, freq=a):
            if not pencere.ufuk_kumeye_sigar_mi(t, ufuk, bar, kume_baslangic=kume_bas, kume_bitis=kume_son):
                with pytest.raises(pencere.KumeSiniriHatasi):
                    pencere.pozisyon_plani(z, t, ufuk, bar, birincil_ufuk=birincil, **sinirlar)
    assert kontrol > 0


# --- Kaynak taramasi -----------------------------------------------------------


def test_tarama_kapi_disi_cikis_erisimini_yakalar(tmp_path):
    ornekler = {
        "events/h1.py": "c = pencere.cikis_bari(z, g, 18, bar, birincil_ufuk=18, donem_bitis=d, kume_bitis=k)\n",
        "study/k1.py": "if pencere.ufuk_kumeye_sigar_mi(t, 18, bar, kume_baslangic=b, kume_bitis=s):\n    pass\n",
        "study/k2.py": "from data.split import ufuk_kumeye_sigar_mi\nufuk_kumeye_sigar_mi(t, 18, bar, 'KESIF')\n",
        "analysis/01_h1/calistir.py": "c = pencere.CikisSonucu(0, z, 'close', False, False)\n",
        "analysis/02_h2/calistir.py": "p = pencere.PozisyonPlani(*alanlar)\n",
        "events/h3.py": "an = pencere.cikis_ani(c, bar)\n",
    }
    for ad, metin in ornekler.items():
        yol = tmp_path / ad
        yol.parent.mkdir(parents=True, exist_ok=True)
        yol.write_text(metin, encoding="utf-8")
    temiz = tmp_path / "events" / "h2.py"
    temiz.write_text("plan = pencere.pozisyon_plani(z, t, 18, bar, birincil_ufuk=18, **sinirlar)\n", encoding="utf-8")
    izinli = tmp_path / "data" / "pencere.py"
    izinli.parent.mkdir()
    izinli.write_text("def cikis_bari(): ...\n", encoding="utf-8")

    assert ihlaller(CIKIS_KAPI_DISI_DESENI, kok=tmp_path) == sorted(ornekler)


def test_depoda_kapi_disi_cikis_erisimi_yok():
    assert ihlaller(CIKIS_KAPI_DISI_DESENI) == [], "analiz kodu tek kapiyi (pozisyon_plani) atliyor"
