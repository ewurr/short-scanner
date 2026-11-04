"""Performans 2a: funding tamligi tek hesaplanir, toplu cagri yolu, plan yeniden kullanimi (plan v2 karar 5, D-C6, D-C8).

  1. Tek tamlik (1a): kapi tamlik satirini bir kez hesaplar; toplam satirin `capa_index` / `son_index` diliminden,
     skaler `_plan_fundingi` ile AYNI kayitlar ve ayni indirgemeyle (`==`). Toplam tamligi atlamaz.
  2. Toplu cagri (1b): bir funding serisi icin butun planlarla tek cagri; her satir n = 1 satiriyla butun sutunlarda
     `equals` (NaN/NaT konumlari dahil), toplam `==`.
  3. Plan yeniden kullanimi: plan (sembol, kume, donem) verisi icin (bar, ufuk, birincil ufuk, t) basina bir kez kurulur;
     paylasim karari degistirmez; onbellek `kume_bellegi` kurallarina tabidir.
Deger raporlanmaz. Aga cikmaz.
"""

from __future__ import annotations

import inspect

import numpy as np
import pandas as pd
import pytest

import config
from data import _skaler_referans as ref
from data import funding, kume_bellegi, pencere, pozisyon, sinyal
from esitlik_yardimcisi import H4, dunya, karar_cagrisi, ornek_barlar, sonuc_esit

BAS, BITIS = "2021-01-01", "2021-11-26 20:00"


def _planlar(kimlik, hipotez="H2", adet=120, tohum=7):
    """Dunyanin orneklenen barlarindan kurulabilen planlar ve funding serisi."""
    tanim = pencere.hipotez_ufuklari(hipotez)
    bas, bitis, _ = pozisyon.donem_kaydi(kimlik["sembol"], kimlik["donem_no"])
    kb, ks = pozisyon.kume_sinirlari("KESIF")
    m, fr, _ = pozisyon._karar_verisi(kimlik["sembol"], "KESIF", kume_baslangic=kb, kume_bitis=ks,
                                      donem_baslangic=bas, donem_bitis=bitis)
    zamanlar = pd.DatetimeIndex(m["open_time"])
    planlar = []
    for t in ornek_barlar(kimlik, adet, tohum, tanim.bar):
        try:
            planlar.append(pencere.pozisyon_plani(zamanlar, t, tanim.birincil, tanim.bar, birincil_ufuk=tanim.birincil,
                                                  kume_baslangic=kb, kume_bitis=ks, donem_baslangic=bas,
                                                  donem_bitis=bitis))
        except pencere.OlayOlusmaz:
            pass
    return planlar, fr


@pytest.fixture
def dunya_ic():
    return dunya(301, BAS, BITIS)


@pytest.mark.parametrize("hipotez", ("H2", "H3"))
def test_toplu_cagri_n1_ile_her_satirda_butun_sutunlarda_ayni_ve_toplam_esit(dunya_ic, hipotez):
    kimlik, _ = dunya_ic
    planlar, fr = _planlar(kimlik, hipotez)
    toplu = funding._planlar_tamlik_satirlari(fr, planlar)
    assert len(toplu) == len(planlar) > 50
    gorulen = set()
    for plan, tamlik in zip(planlar, toplu):
        n1 = funding.pozisyon_funding_ayrintisi(fr, plan)
        assert list(tamlik.satir.index) == list(n1.index) and tamlik.satir.equals(n1)
        assert tamlik.satir.equals(ref.pozisyon_funding_ayrintisi(fr, plan))     # skaler referans
        t1 = funding._satirdan_toplam(fr, plan, tamlik)
        t0 = funding._plan_fundingi(fr, plan)
        assert (np.isnan(t1) and np.isnan(t0)) or t1 == t0 == ref._plan_fundingi(fr, plan)
        gorulen.add(bool(n1["tam"]))
    assert gorulen == {True, False}     # tam ve tam olmayan planlar birlikte sinandi


def test_satirin_kesimi_skaler_maskeyle_ayni_kayitlari_secer(dunya_ic):
    kimlik, _ = dunya_ic
    planlar, fr = _planlar(kimlik)
    zamanlar = pd.DatetimeIndex(fr["odeme_zamani"])
    sinandi = 0
    for tamlik in funding._planlar_tamlik_satirlari(fr, planlar):
        if tamlik.capa_index < 0:
            assert not bool(tamlik.satir["capa_var"])
            continue
        plan = tamlik.plan
        maske = (np.asarray(pencere.sonra(zamanlar, plan.giris), dtype=bool)
                 & np.asarray(pencere.ayni_ya_da_once(zamanlar, funding.funding_penceresi_sonu(plan)), dtype=bool))
        assert np.array_equal(np.arange(tamlik.capa_index + 1, tamlik.son_index + 1), np.flatnonzero(maske))
        sinandi += 1
    assert sinandi > 50


def test_toplam_tamligi_atlamaz_ve_hesaplandi_bayragi_almaz(dunya_ic):
    kimlik, _ = dunya_ic
    planlar, fr = _planlar(kimlik)
    assert list(inspect.signature(funding._satirdan_toplam).parameters) == ["funding", "plan", "tamlik"]
    eksik = [t for t in funding._planlar_tamlik_satirlari(fr, planlar) if not bool(t.satir["tam"])]
    assert eksik
    for tamlik in eksik:
        assert np.isnan(funding._satirdan_toplam(fr, tamlik.plan, tamlik))


def test_toplam_baska_planin_ya_da_baska_serinin_satirini_kabul_etmez(dunya_ic):
    kimlik, _ = dunya_ic
    planlar, fr = _planlar(kimlik)
    a, b = funding._planlar_tamlik_satirlari(fr, planlar[:2])
    with pytest.raises(ValueError):
        funding._satirdan_toplam(fr, planlar[1], a)
    with pytest.raises(ValueError):
        funding._satirdan_toplam(fr.iloc[:-1], planlar[0], a)
    with pytest.raises(ValueError):
        funding._satirdan_toplam(fr, planlar[0], funding.pozisyon_funding_ayrintisi(fr, planlar[0]))
    with pytest.raises(TypeError):
        funding._planlar_tamlik_satirlari(fr, [object()])


def test_genel_api_degismedi_ic_sutunlar_yalnizca_istenirse(dunya_ic):
    kimlik, _ = dunya_ic
    planlar, fr = _planlar(kimlik)
    p = planlar[0]
    genel = funding.funding_tamlik_ayrintisi(fr, [p.giris], [funding.funding_penceresi_sonu(p)],
                                             donem_baslari=[p.donem_baslangic])
    assert "capa_index" not in genel and "son_index" not in genel
    assert list(genel.columns) == list(ref.funding_tamlik_ayrintisi(fr, [p.giris], [funding.funding_penceresi_sonu(p)],
                                                                   donem_baslari=[p.donem_baslangic]).columns)


def test_kapi_pozisyon_tamligini_bir_kez_hesaplar(dunya_ic, monkeypatch):
    """Pozisyonun penceresi (giris, funding penceresi sonu) icin tamlik kurali kapida BIR KEZ uygulanir (rev.9 - P2a: iki
    kez; toplamin icinde yeniden). H2'nin funding SINYAL penceresi ayri bir penceredir ve sayilmaz."""
    kimlik, _ = dunya_ic
    cagrilar = []
    asil = funding.funding_tamlik_ayrintisi

    def kaydet(fr, girisler, sonlar, **k):
        cagrilar.append((list(pd.DatetimeIndex(girisler)), list(pd.DatetimeIndex(sonlar))))
        return asil(fr, girisler, sonlar, **k)

    monkeypatch.setattr(funding, "funding_tamlik_ayrintisi", kaydet)
    for hipotez in ("H2", "H3"):
        tanim = pencere.hipotez_ufuklari(hipotez)
        for t in ornek_barlar(kimlik, 40, 3, tanim.bar):
            cagrilar.clear()
            sonuc = karar_cagrisi(pozisyon, hipotez, kimlik, t)
            if isinstance(sonuc, pozisyon.OnaylanmisPozisyon):
                pencere_ = ([sonuc.plan.giris], [funding.funding_penceresi_sonu(sonuc.plan)])
                assert sum(c == pencere_ for c in cagrilar) == 1
                break
        else:
            pytest.fail(f"{hipotez}: ornekte onayli pozisyon yok")


# --- Plan yeniden kullanimi --------------------------------------------------------------------------------

def _plan_sayaci(monkeypatch):
    sayac = {"n": 0}
    asil = pencere.pozisyon_plani

    def say(*a, **k):
        sayac["n"] += 1
        return asil(*a, **k)

    monkeypatch.setattr(pencere, "pozisyon_plani", say)
    return sayac


def test_plan_yapilandirmalar_ve_h1_h2_arasinda_paylasilir_karar_degismez(dunya_ic, monkeypatch):
    kimlik, ozel = dunya_ic
    sayac = _plan_sayaci(monkeypatch)
    barlar = ornek_barlar(kimlik, 25, 9) + ozel["h2"]
    for t in barlar:
        karar_cagrisi(pozisyon, "H2", kimlik, t)
    ilk = sayac["n"]
    assert ilk > 0
    # Ayni barlar baska yapilandirmalarda, K2 rolunde ve H1'de: plan yeniden kurulmaz; karar referansla ayni.
    for y in [dict(x) for x in sinyal.izgara("H2")][1:4]:
        for t in barlar:
            for rol in ("K1", "K2", "olay"):
                a = karar_cagrisi(pozisyon, "H2", kimlik, t, yapilandirma=y, rol=rol)
                assert sonuc_esit(a, karar_cagrisi(ref, "H2", kimlik, t, yapilandirma=y, rol=rol))
    for t in barlar:
        a = karar_cagrisi(pozisyon, "H1", kimlik, t)
        assert sonuc_esit(a, karar_cagrisi(ref, "H1", kimlik, t))
    assert sayac["n"] == ilk
    # H3 (1d) ayri bar turu: ayri anahtar.
    karar_cagrisi(pozisyon, "H3", kimlik, barlar[-1].floor("D"))
    assert sayac["n"] == ilk + 1


def test_plan_reddi_ayni_sinif_ve_mesajla_yeniden_firlatilir(dunya_ic, monkeypatch):
    """Ret (`OlayOlusmaz`) saklanir ve her isabette ayni sinif ve ayni mesajla YENI bir nesne olarak firlatilir."""
    kimlik, _ = dunya_ic
    sayac = _plan_sayaci(monkeypatch)
    bas, _, _ = pozisyon.donem_kaydi(kimlik["sembol"], 0)
    t = bas + pd.Timedelta(days=60) - H4          # giris bari 60. gunun ilk bari: dunyada eksik (3 gunluk bosluk)
    hatalar = [karar_cagrisi(pozisyon, "H2", kimlik, t) for _ in range(2)]
    assert all(isinstance(h, pencere.GirisBariYok) for h in hatalar)
    assert hatalar[0].args == hatalar[1].args and hatalar[0] is not hatalar[1]
    assert sayac["n"] == 1
    assert sonuc_esit(hatalar[1], karar_cagrisi(ref, "H2", kimlik, t))


def test_donem_disi_sinyal_programlama_hatasi_saklanmaz(dunya_ic, monkeypatch):
    """`DonemDisiSinyal` bir ret degil programlama hatasidir (`ValueError`): saklanmaz, her cagrida plan yeniden denenir."""
    kimlik, _ = dunya_ic
    sayac = _plan_sayaci(monkeypatch)
    bas, _, _ = pozisyon.donem_kaydi(kimlik["sembol"], 0)
    for _ in range(2):
        assert isinstance(karar_cagrisi(pozisyon, "H2", kimlik, bas - 10 * H4), pencere.DonemDisiSinyal)
    assert sayac["n"] == 2


def test_plan_serisi_karar_girdisinin_parcasi_anahtar_kume_adini_tasir(dunya_ic):
    kimlik, _ = dunya_ic
    kume_bellegi.temizle()
    karar_cagrisi(pozisyon, "H2", kimlik, ornek_barlar(kimlik, 3, 1)[-5])
    anahtarlar = list(kume_bellegi._BELLEK)
    assert all("KESIF" in a for a in anahtarlar)
    karar = [a for a in anahtarlar if a[0] == "karar"]
    assert len(karar) == 1
    deger = kume_bellegi._BELLEK[karar[0]]
    assert isinstance(deger[3], pozisyon._PlanSerisi) and len(deger[3]) >= 1
    assert len(anahtarlar) == 2       # "kume" ve "karar": plan ayri bir LRU yuvasi kullanmaz


def test_erisim_denetimi_plan_isabetinde_de_calisir(dunya_ic, monkeypatch):
    kimlik, _ = dunya_ic
    t = ornek_barlar(kimlik, 3, 1)[-5]
    karar_cagrisi(pozisyon, "H2", kimlik, t)

    class Yasak(PermissionError):
        pass

    def denetim(kume):
        def f():
            raise Yasak("erisim yok")
        return f

    monkeypatch.setattr(pozisyon, "_erisim_denetimi", denetim)
    assert isinstance(karar_cagrisi(pozisyon, "H2", kimlik, t), Yasak)


def test_temizle_plan_serisini_dusurur(dunya_ic, monkeypatch):
    kimlik, _ = dunya_ic
    sayac = _plan_sayaci(monkeypatch)
    t = ornek_barlar(kimlik, 3, 1)[-5]
    karar_cagrisi(pozisyon, "H2", kimlik, t)
    karar_cagrisi(pozisyon, "H2", kimlik, t)
    assert sayac["n"] == 1
    kume_bellegi.temizle()        # onay kosusunun acilisi ve kapanisi bunu cagirir (split.onay_kosusu)
    karar_cagrisi(pozisyon, "H2", kimlik, t)
    assert sayac["n"] == 2


def test_onay_kosusu_acilis_ve_kapanista_kume_bellegini_temizler():
    """Plan serisi `kume_bellegi` girdisinin parcasi oldugu icin onay kosusu kurali onu da kapsar."""
    from data import split

    kaynak = inspect.getsource(split)
    assert kaynak.count("kume_bellegi.temizle()") >= 2


def test_olay_olusmaz_disindaki_hata_saklanmaz(dunya_ic, monkeypatch):
    kimlik, _ = dunya_ic
    t = ornek_barlar(kimlik, 3, 1)[-5]
    asil = pencere.pozisyon_plani
    durum = {"bozuk": True}

    def bazen_hata(*a, **k):
        if durum["bozuk"]:
            raise RuntimeError("gecici")
        return asil(*a, **k)

    monkeypatch.setattr(pencere, "pozisyon_plani", bazen_hata)
    assert isinstance(karar_cagrisi(pozisyon, "H2", kimlik, t), RuntimeError)
    durum["bozuk"] = False
    assert sonuc_esit(karar_cagrisi(pozisyon, "H2", kimlik, t), karar_cagrisi(ref, "H2", kimlik, t))
