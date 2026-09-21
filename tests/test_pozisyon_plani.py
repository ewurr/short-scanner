"""Pozisyon plani testleri: `pencere.pozisyon_plani` (on-kayit §4 rev.8).

"Bir olayin kumede olusup olusmadigina tek bir karar noktasi hukmeder ve olcut
cikis anina gore uygulanir: cikis ani ile funding tolerans payi birlikte kume
sonunu asmamalidir. Cikis ani, izgaranin adimindan turetilmez; ... olagan cikista
T, ileri kaymada sonraki barin acilisi, donem sonunda K."

Rev.8 guncellemesi (RESULTS degisiklik kaydi): plan her izgarada 4h barlarla
kurulur (§4 "Fiyat okuma tabani"); donem sinirlari zorunludur; T'ye dayali kume on
elemesi (`ufuk_kumeye_sigar_mi`) kaldirildi, ozellik testi artik kume kararinin
gercek cikis anina gore verildigini dogrular.

Korumalar:
  - Ozellik testi: kume sonuna yakin zaman izgarasinda (4h ve 1d, birincil ve
    ikincil ufuklar, eksik barlar, donem sonu) kumesiz planin cikis ani + tolerans
    kume icindeyse kumeli plan kabul eder, disindaysa `KumeSiniriHatasi`; kabul
    edilen planda funding hesabi kume hatasi vermez.
  - Kaynak taramasi: analiz kodu cikis_bari / cikis_ani'yi dogrudan cagirmaz,
    CikisSonucu ya da PozisyonPlani kurmaz.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import config
from data import funding, pencere, split
from tarama_yardimcisi import CIKIS_KAPI_DISI_DESENI, ihlaller

DORT_SAAT = pd.Timedelta(hours=4)
KESIF_BAS, KESIF_SON = split.kume_araligi("KESIF")
C2_BAS, C2_SON = split.kume_araligi("C2")


def _izgara(bas, adet, bar=config.BAR_4H):
    return pd.date_range(bas, periods=adet, freq=pencere.adim(bar), tz="UTC")


def _plan(zamanlar, t, ufuk=18, bar=config.BAR_4H, birincil=18, **sinirlar):
    """Varsayilan: kume sinirsiz, donem serinin ilk ve son bari (rev.8'de donem zorunlu)."""
    varsayilan = dict(kume_baslangic=None, kume_bitis=None, donem_baslangic=zamanlar[0], donem_bitis=zamanlar[-1])
    return pencere.pozisyon_plani(zamanlar, t, ufuk, bar, birincil_ufuk=birincil, **{**varsayilan, **sinirlar})


# --- Temel -------------------------------------------------------------------


def test_plan_alanlari():
    z = _izgara("2021-01-01", 60)
    plan = _plan(z, z[4])
    assert plan.sinyal_zamani == z[4] and plan.giris == z[5]
    assert plan.cikis.zaman == z[22] and plan.cikis.fiyat_alani == "close"
    assert plan.cikis_ani == z[23] and plan.ufuk == 18 and plan.birincil_ufuk == 18
    assert plan.cikis_turu == "olagan" and plan.cikis.hedef_cikis_ani == z[23]
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
    # rev.8: cikis_hedefi T'yi (hedef barin KAPANISI) verir; hedef barin acilisi T - 4h.
    hedef_acilis = pencere.cikis_hedefi(z[5], 18, config.BAR_4H) - DORT_SAAT
    eksik = z.drop(pd.date_range(hedef_acilis, periods=19, freq="4h"))
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
    """Son 4h barin kapanisi (09-01 00:00) C2'ye duser; bir adim once kabul.
    Rev.8: 1d izgarasinda da seri 4h'tir ve cikis bari 4h bardir (1d'de beklenen
    cikis bari 08-30 gun acilisi yerine 08-30 20:00 4h bari)."""
    a = pencere.adim(bar)
    son_4h = KESIF_SON.floor("4h")  # 2025-08-31 20:00
    z = pd.date_range(son_4h - 40 * pencere.adim(config.BAR_1D), son_4h + 10 * DORT_SAAT, freq="4h")
    t_son = (son_4h + DORT_SAAT) - (ufuk + 1) * a  # T = son 4h barin kapanisi
    with pytest.raises(pencere.KumeSiniriHatasi):
        _plan(z, t_son, ufuk=ufuk, bar=bar, kume_bitis=KESIF_SON)
    plan = _plan(z, t_son - a, ufuk=ufuk, bar=bar, kume_bitis=KESIF_SON)
    assert plan.cikis_ani == son_4h + DORT_SAAT - a
    assert plan.cikis.zaman == plan.cikis_ani - DORT_SAAT


# --- Zorunluluk ve tipler ----------------------------------------------------


@pytest.mark.parametrize("eksik", ["birincil_ufuk", "kume_baslangic", "kume_bitis", "donem_baslangic", "donem_bitis"])
def test_parametre_unutulursa_hata(eksik):
    z = _izgara("2021-01-01", 60)
    parametreler = dict(kume_baslangic=None, kume_bitis=None, donem_baslangic=z[0], donem_bitis=z[-1], birincil_ufuk=18)
    del parametreler[eksik]
    with pytest.raises(TypeError):
        pencere.pozisyon_plani(z, z[4], 18, config.BAR_4H, **parametreler)


@pytest.mark.parametrize("alan", ["donem_baslangic", "donem_bitis"])
def test_donem_siniri_none_olamaz(alan):
    """Rev.8: donem sonu kurali B'ye dayanir; donem sinirlari bilincli None da olamaz."""
    z = _izgara("2021-01-01", 60)
    with pytest.raises(TypeError):
        _plan(z, z[4], **{alan: None})


@pytest.mark.parametrize("alan", ["sinyal", "kume_bitis", "donem_baslangic"])
def test_saat_dilimsiz_zaman_reddedilir(alan):
    z = _izgara("2021-01-01", 60)
    t = z[4]
    parametreler = dict(kume_baslangic=None, kume_bitis=None, donem_baslangic=z[0], donem_bitis=z[-1])
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


# --- Ozellik testi: kume karari gercek cikis anina gore ------------------------


def _tam_funding(bas, son):
    zaman = pd.date_range(bas, son, freq="8h")
    fr = pd.DataFrame({"odeme_zamani": zaman, "aralik_saat": 8.0, "oran": 1e-4})
    fr["oran_8h"] = fr["oran"]
    return fr


@pytest.mark.parametrize("kume", ["KESIF", "C2"])
@pytest.mark.parametrize("bar,ufuklar,birincil", [(config.BAR_4H, (6, 18, 42), 18), (config.BAR_1D, (7, 14, 30), 14)])
@pytest.mark.parametrize("senaryo", ["tam", "eksik_barlar", "donem_sonu_icinde"])
def test_kume_karari_gercek_cikis_anina_gore(kume, bar, ufuklar, birincil, senaryo):
    kume_bas, kume_son = split.kume_araligi(kume)
    a = pencere.adim(bar)
    son_4h = kume_son.floor("4h")
    z = pd.date_range(son_4h - 60 * pencere.adim(config.BAR_1D), son_4h + 60 * DORT_SAAT, freq="4h")
    donem_bitis = z[-1]
    if senaryo == "eksik_barlar":
        rng = np.random.default_rng(config.TOHUM)
        sil = z[1:-1][rng.random(len(z) - 2) < 0.08]
        z = z.drop(sil)
    elif senaryo == "donem_sonu_icinde":
        donem_bitis = son_4h - 3 * a
        z = z[z <= donem_bitis]
    fund = _tam_funding(z[0] - pd.Timedelta(days=2), z[-1] + pd.Timedelta(days=2))
    donem = dict(donem_baslangic=z[0], donem_bitis=donem_bitis)

    kontrol = kabul = ret = t_disarida_k_icinde = 0
    for ufuk in ufuklar:
        for t in pd.date_range(son_4h.floor("D") - (ufuk + 30) * a, son_4h + 5 * DORT_SAAT, freq=a):
            if not pencere.donem_ici_mi(t, bar, **donem):
                continue
            kontrol += 1
            try:
                serbest = pencere.pozisyon_plani(z, t, ufuk, bar, birincil_ufuk=birincil, kume_baslangic=None,
                                                 kume_bitis=None, **donem)
            except (pencere.GirisBariYok, pencere.IleriKaymaSiniriHatasi):
                continue
            disarida = serbest.cikis_ani + funding.ODEME_TOLERANSI - pd.Timedelta(1, "ns") > kume_son
            if disarida or t < kume_bas:
                with pytest.raises(pencere.KumeSiniriHatasi):
                    pencere.pozisyon_plani(z, t, ufuk, bar, birincil_ufuk=birincil, kume_baslangic=kume_bas,
                                           kume_bitis=kume_son, **donem)
                ret += 1
                continue
            plan = pencere.pozisyon_plani(z, t, ufuk, bar, birincil_ufuk=birincil, kume_baslangic=kume_bas,
                                          kume_bitis=kume_son, **donem)
            kabul += 1
            if plan.cikis.hedef_cikis_ani > kume_son:
                t_disarida_k_icinde += 1  # rev.8 ornegi: T kume disinda, cikis K'da, olay olusur
                assert plan.cikis_turu == "donem_sonu"
            assert plan.cikis_ani == serbest.cikis_ani and plan.cikis == serbest.cikis
            assert plan.sinyal_zamani >= kume_bas
            deger = funding.pozisyon_fundingi(fund, plan)  # kume hatasi olamaz
            assert isinstance(deger, float)
    assert kontrol > 0 and kabul > 0
    if senaryo == "donem_sonu_icinde":
        # Donem kume sonundan once bitiyor: butun cikislar en gec K'da ve K kume icinde.
        assert ret == 0 and t_disarida_k_icinde > 0
    else:
        assert ret > 0


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
