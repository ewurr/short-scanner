"""F1-K1, D-B1 (RESULTS §14.49 denetci D-B1 ve D-C7; plan v3 G1, G10): `olay_karari`'nin geri dusus yolu kaldirildi.

- Yalnizca COK BARLI seri yolunda cikan bir hata (birimin baska bir barindaki bozuk veri) `olay_karari`'dan da ayni
  sinifla yukselir; skaler referans o barda karar verir (hata yalnizca seri yolunda vardir).
- Esitlik betigi (`esitlik_kapi.karsilastir`) bu durumu BIRIM hatasi olarak sayar: skalerde ayni birimde en az bir
  beklenmeyen hata varsa uyusan, yoksa birimin butun barlari uyusmayan.
- Hata veren kurulum ve onbellek: ayni anahtar icin hata bir kez kurulumdan cikar, sonraki cagrilar seriyi yeniden
  kurmadan AYNI hatayi verir; hata bellegi donem isareti kuralina uyar (kosu acilisi ve kapanisi onu dusurur).

Sentetik dunya; deger, getiri ve olay sayisi yazilmaz. Aga cikmaz.
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import pytest

from data import _skaler_referans as ref
from data import kume_bellegi, pencere, pozisyon, sinyal
from esitlik_yardimcisi import dunya, karar_cagrisi
from kapi_yardimcisi import SENTETIK_VERI, veri
from tarama_yardimcisi import KOK

sys.path.insert(0, str(KOK / "analysis" / "00_veri_denetimi"))
import esitlik_kapi as ek  # noqa: E402

BAS, BITIS = "2021-01-01", "2021-08-31 20:00"


def _y(hipotez="H2"):
    return dict(sinyal.izgara(hipotez)[0])


def _izgara(kimlik, hipotez="H2"):
    return pozisyon.hipotez_izgarasi_barlari(hipotez, kume="KESIF", **kimlik)


def _bozuk_dunya(tohum=621):
    """K2 rolunde onayli bir bar t'nin giris barinin `open`i sifir: yalnizca t'de skaler `VeriHatasi`, seri yolunda
    birimin hepsi. Doner: (saglam kimlik, bozuk kimlik, t, saglam izgara)."""
    kimlik, _ = dunya(tohum, BAS, BITIS)
    seri = pozisyon.kapi_serisi("H2", _y(), "K2", kume="KESIF", **kimlik)
    on = np.nonzero(seri.onay_bitleri())[0]
    assert len(on) >= 3, "kurulum: onayli K2 bari olmali"
    t = seri.zamanlar()[int(on[len(on) // 2])]
    poz = seri.sonuc(t)
    m, f = (x.copy() for x in SENTETIK_VERI[kimlik["sembol"]])
    bas, bitis, _ = pozisyon.donem_kaydi(kimlik["sembol"], 0)
    m.loc[pd.DatetimeIndex(m["open_time"]) == poz.plan.giris, "open"] = 0.0
    bozuk = veri(m.reset_index(drop=True), f.reset_index(drop=True), bas, bitis, ham=True)
    kume_bellegi.temizle()
    return kimlik, bozuk, t, _izgara(kimlik)


@pytest.fixture
def bozuk_dunya():
    return _bozuk_dunya()


# --- 1. Yalnizca cok barli seri yolunda cikan hata olay_karari'dan da ayni sinifla yukselir ---------------------------

@pytest.mark.parametrize("rol", ["K1", "K2"])
def test_yalnizca_seri_yolundaki_hata_olay_kararindan_ayni_sinifla_yukselir(bozuk_dunya, rol):
    _, bozuk, t, _ = bozuk_dunya
    izgara = _izgara(bozuk)
    with pytest.raises(pencere.VeriHatasi):
        pozisyon.kapi_serisi("H2", _y(), rol, kume="KESIF", **bozuk)
    # t'den uzak barlar: skaler karar verir (hata yalnizca seri yolunda), sarmalayici seri hatasini yukseltir.
    uzak = [x for x in izgara[:: max(1, len(izgara) // 15)] if abs(x - t) > pd.Timedelta(days=30)]
    assert len(uzak) >= 5
    for x in uzak:
        r = karar_cagrisi(ref, "H2", bozuk, x, rol=rol)
        assert not (isinstance(r, BaseException) and not isinstance(r, pencere.OlayOlusmaz)), \
            "kurulum: skaler bu barda beklenmeyen hata vermemeli"
        a = karar_cagrisi(pozisyon, "H2", bozuk, x, rol=rol)
        assert type(a) is pencere.VeriHatasi, (x, type(a).__name__)
    # Bozuk barin kendisi: iki taraf ayni sinif.
    assert type(karar_cagrisi(ref, "H2", bozuk, t, rol=rol)) is pencere.VeriHatasi
    assert type(karar_cagrisi(pozisyon, "H2", bozuk, t, rol=rol)) is pencere.VeriHatasi


def test_izgara_disi_t_de_seri_hatasini_yukseltir(bozuk_dunya):
    """Izgara disi t (tolerans payli) tek bar cekirdegine yalnizca seri BASARIYLA kurulduktan sonra gider; seri hatasi
    once yukselir."""
    _, bozuk, _, _ = bozuk_dunya
    x = _izgara(bozuk)[40] + pd.Timedelta(seconds=30)
    assert type(karar_cagrisi(pozisyon, "H2", bozuk, x, rol="K1")) is pencere.VeriHatasi


def test_seri_hatasi_olay_kararinda_tek_bar_cekirdegine_dusmez(bozuk_dunya, monkeypatch):
    """D-B1 / D-C7: seri kurulumu hata verdiginde `_kapi_satirlari` tek bar icin hic cagrilmaz."""
    _, bozuk, _, _ = bozuk_dunya
    x = _izgara(bozuk)[10]
    with pytest.raises(pencere.VeriHatasi):
        pozisyon.kapi_serisi("H2", _y(), "K1", kume="KESIF", **bozuk)

    def yasak(*a, **k):
        raise AssertionError("seri hatasindan sonra tek bar cekirdegi calismamali (D-B1)")

    monkeypatch.setattr(pozisyon, "_kapi_satirlari", yasak)
    assert type(karar_cagrisi(pozisyon, "H2", bozuk, x, rol="K1")) is pencere.VeriHatasi


def test_olay_kararinda_seri_hatasini_yutan_yol_yok():
    """Kaynak taramasi: `olay_karari` govdesinde `try` / `except` yok (geri dusus ve `except OlayOlusmaz: raise` kalkti)."""
    import ast
    import inspect
    import textwrap

    agac = ast.parse(textwrap.dedent(inspect.getsource(pozisyon.olay_karari)))
    assert not [d for d in ast.walk(agac) if isinstance(d, ast.Try)]


# --- 2. Esitlik betigi bunu birim hatasi olarak sayar -----------------------------------------------------------------

def test_esitlik_betigi_seri_hatasini_birim_hatasi_sayar_skalerde_karsiligi_varsa_uyusan(bozuk_dunya):
    _, bozuk, t, _ = bozuk_dunya
    izgara = _izgara(bozuk)
    siralar = sorted({int(izgara.get_loc(t))} | set(range(0, len(izgara), 97)))
    barlar = [izgara[i] for i in siralar]
    sayac = ek.karsilastir(barlar, siralar, "H2", _y(), "K2", bozuk)
    assert sayac.birim_hatasi == "seri:VeriHatasi"
    assert sayac.beklenmeyen_referans >= 1 and sayac.beklenmeyen_yeni == 0
    assert sayac.karsilastirilan == len(barlar) and sayac.uyusmayan == []


def test_esitlik_betigi_seri_hatasini_birim_hatasi_sayar_skalerde_karsiligi_yoksa_butun_barlar_uyusmaz(bozuk_dunya):
    _, bozuk, t, _ = bozuk_dunya
    izgara = _izgara(bozuk)
    siralar = [i for i in range(0, len(izgara), 97) if abs(izgara[i] - t) > pd.Timedelta(days=30)]
    barlar = [izgara[i] for i in siralar]
    sayac = ek.karsilastir(barlar, siralar, "H2", _y(), "K2", bozuk)
    assert sayac.birim_hatasi == "seri:VeriHatasi"
    assert (sayac.beklenmeyen_referans, sayac.beklenmeyen_yeni) == (0, 0)
    assert len(sayac.uyusmayan) == len(barlar) > 3


def test_sembol_isi_birim_hatasini_hata_sutununa_yazar(bozuk_dunya, monkeypatch):
    _, bozuk, _, _ = bozuk_dunya
    monkeypatch.setattr(ek, "_donemler", lambda sembol: [0])
    asil = ek.bar_izgarasi
    monkeypatch.setattr(ek, "bar_izgarasi", lambda k, h: asil(k, h)[:300])
    ayar = {"hipotezler": ["H2"], "yapilandirma": "ilk", "roller": ["K1"], "funding_satiri": False, "bar": "tum",
            "n": 5, "kosul_ve_onay_yolu": False}
    satir = [s for s in ek.sembol_isi(bozuk["sembol"], ayar) if s["rol"] == "K1"]
    assert len(satir) == 1 and satir[0]["hata"] == "seri:VeriHatasi"
    assert satir[0]["beklenmeyen_hata_yeni"] == 0


def test_bar_basina_beklenmeyen_hata_birim_hatasi_sayilmaz():
    """Yeni taraf bir barda beklenmeyen hata verir ama seri kurulumu saglamsa bar basina hatadir (G10'un ayrimi)."""
    kimlik, _ = dunya(622, BAS, BITIS)
    izgara = _izgara(kimlik)
    siralar = list(range(0, 400, 20))
    barlar = [izgara[i] for i in siralar]

    class Kapi:
        def olay_karari(self, t, *a, **k):
            if t == barlar[3]:
                raise KeyError("bilerek")
            return pozisyon.olay_karari(t, *a, **k)

        def __getattr__(self, ad):
            return getattr(pozisyon, ad)

    sayac = ek.karsilastir(barlar, siralar, "H2", _y(), "K1", kimlik, kapi=Kapi())
    assert sayac.birim_hatasi == "" and sayac.beklenmeyen_yeni == 1 and len(sayac.uyusmayan) == 1


# --- 3. Hata veren kurulum ve onbellek --------------------------------------------------------------------------------

def _kurulum_sayaci(monkeypatch):
    """Seri kurulumunun (`kur`) ilk adimi izgaradir: cagri sayisi kurulum sayisidir."""
    sayac = []
    asil = pozisyon.hipotez_izgarasi_barlari

    def say(*a, **k):
        sayac.append(1)
        return asil(*a, **k)

    monkeypatch.setattr(pozisyon, "hipotez_izgarasi_barlari", say)
    return sayac


def test_hata_bir_kez_kurulumdan_cikar_sonraki_cagrilar_yeniden_kurmadan_ayni_hatayi_verir(bozuk_dunya, monkeypatch):
    _, bozuk, _, _ = bozuk_dunya
    barlar = _izgara(bozuk)[::200]            # sayac kurulmadan once (izgara yardimcisi da sayilirdi)
    sayac = _kurulum_sayaci(monkeypatch)
    with pytest.raises(pencere.VeriHatasi) as ilk:
        pozisyon.kapi_serisi("H2", _y(), "K1", kume="KESIF", **bozuk)
    assert len(sayac) == 1
    for _ in range(3):
        with pytest.raises(pencere.VeriHatasi) as sonraki:
            pozisyon.kapi_serisi("H2", _y(), "K1", kume="KESIF", **bozuk)
        assert sonraki.value is ilk.value
    # Bar basina okuyucu: birimin bircok bari seriyi yeniden kurmaz.
    for x in barlar:
        assert type(karar_cagrisi(pozisyon, "H2", bozuk, x, rol="K1")) is pencere.VeriHatasi
    assert len(sayac) == 1
    # Kismi seri yoktur: hata seri bellegine yazilmaz.
    assert not any(a[2] == bozuk["sembol"] for a in pozisyon._SERI_BELLEGI)
    assert any(a[2] == bozuk["sembol"] for a in pozisyon._SERI_HATALARI)


def test_hata_bellegi_kosu_acilisinda_ve_kapanisinda_duser(bozuk_dunya, monkeypatch):
    """Donem isareti kurali: `kume_bellegi.temizle` (kesif ve onay kosusunun acilisi ve kapanisi) hata bellegini de
    dusurur; sonraki cagri seriyi yeniden kurar. Anahtar yeni isareti tasir."""
    _, bozuk, _, _ = bozuk_dunya
    sayac = _kurulum_sayaci(monkeypatch)
    for beklenen in (1, 2, 3):
        with pytest.raises(pencere.VeriHatasi):
            pozisyon.kapi_serisi("H2", _y(), "K1", kume="KESIF", **bozuk)
        with pytest.raises(pencere.VeriHatasi):
            pozisyon.kapi_serisi("H2", _y(), "K1", kume="KESIF", **bozuk)
        assert len(sayac) == beklenen
        assert all(a[-1] == kume_bellegi.donem_isareti() for a in pozisyon._SERI_HATALARI)
        kume_bellegi.temizle()
        assert len(pozisyon._SERI_HATALARI) == 0


def test_kurulum_sirasinda_donem_isareti_degisirse_hata_bellege_yazilmaz(bozuk_dunya, monkeypatch):
    _, bozuk, _, _ = bozuk_dunya
    asil = pozisyon.hipotez_izgarasi_barlari

    def kosu_acildi(*a, **k):
        kume_bellegi.temizle()            # kurulumun ortasinda bir kosu acildi ya da kapandi
        return asil(*a, **k)

    monkeypatch.setattr(pozisyon, "hipotez_izgarasi_barlari", kosu_acildi)
    with pytest.raises(pencere.VeriHatasi):
        pozisyon.kapi_serisi("H2", _y(), "K1", kume="KESIF", **bozuk)
    assert len(pozisyon._SERI_HATALARI) == 0


def test_hata_bellegi_azami_girdiyi_asmaz(bozuk_dunya, monkeypatch):
    _, bozuk, _, _ = bozuk_dunya
    monkeypatch.setattr(pozisyon, "SERI_AZAMI_GIRDI", 2)
    for i in range(4):
        with pytest.raises(pencere.VeriHatasi):
            pozisyon.kapi_serisi("H2", dict(sinyal.izgara("H2")[i]), "K1", kume="KESIF", **bozuk)
        assert len(pozisyon._SERI_HATALARI) <= 2


def test_memory_error_bellege_yazilmaz(bozuk_dunya, monkeypatch):
    _, bozuk, _, _ = bozuk_dunya

    def bellek_yok(*a, **k):
        raise MemoryError("bilerek")

    monkeypatch.setattr(pozisyon, "hipotez_izgarasi_barlari", bellek_yok)
    with pytest.raises(MemoryError):
        pozisyon.kapi_serisi("H2", _y(), "K1", kume="KESIF", **bozuk)
    assert len(pozisyon._SERI_HATALARI) == 0


def test_saglam_birimin_onbellegi_hata_belleginden_etkilenmez(bozuk_dunya):
    kimlik, bozuk, _, _ = bozuk_dunya
    with pytest.raises(pencere.VeriHatasi):
        pozisyon.kapi_serisi("H2", _y(), "K1", kume="KESIF", **bozuk)
    a = pozisyon.kapi_serisi("H2", _y(), "K1", kume="KESIF", **kimlik)
    assert pozisyon.kapi_serisi("H2", _y(), "K1", kume="KESIF", **kimlik) is a
