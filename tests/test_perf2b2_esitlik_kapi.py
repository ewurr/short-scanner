"""Gercek veri esitlik betiginin P2b-2 ekleri (`esitlik_kapi.py`; plan v3 G1 gecici istisnasi, G14; RESULTS §14.49).

- `kosul` birimi: kapinin vektorel kosulu ile skaler `sinyal_kosulu` her barda; bozulan tek bar tek uyusmazlik;
  vektorel kosulun seri duzeyindeki hatasi skalerde karsiligi yoksa butun barlari uyusmayan yapar (G10).
- `ONAY_YOLU` satiri: (sembol, hipotez) basina evet / hayir; sayi, zaman damgasi ve sure tasimaz.
Sentetik girdi; aga cikmaz.
"""

from __future__ import annotations

import sys

import pandas as pd
import pytest

from data import pozisyon, sinyal
from esitlik_yardimcisi import dunya
from tarama_yardimcisi import KOK

sys.path.insert(0, str(KOK / "analysis" / "00_veri_denetimi"))
import esitlik_kapi as ek  # noqa: E402

BAS, BITIS = "2021-01-01", "2021-08-31 20:00"


def _kur(tohum, hipotez):
    kimlik, ozel = dunya(tohum, BAS, BITIS)
    izgara = ek.bar_izgarasi(kimlik, hipotez)
    return kimlik, izgara, dict(sinyal.izgara(hipotez)[0])


@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_kosul_birimi_vektorel_ve_skaler_kosul_her_barda_ayni(hipotez):
    kimlik, izgara, y = _kur(701, hipotez)
    siralar = list(range(len(izgara)))
    sayac = ek.kosul_karsilastir([izgara[i] for i in siralar], siralar, hipotez, y, kimlik, izgara)
    assert sayac.karsilastirilan == len(izgara) > 100
    assert (len(sayac.uyusmayan), sayac.beklenmeyen_referans, sayac.birim_hatasi) == (0, 0, "")
    # P2c-1: vektorel taraf kosul serisidir (`_olay_kosulu_serisi` kalkti; ayni kaynak `_olay_kosulu`).
    capa = pd.DatetimeIndex([ek.h1_capasi(t, i) for i, t in enumerate(izgara)]) if hipotez == "H1" else None
    seri = pozisyon.kosul_serisi(hipotez, y, kume="KESIF", **kimlik, capa=capa)
    v = [seri.deger(t) for t in izgara]
    assert None in set(v) and False in set(v), "kurulum: hesaplanamayan ve saglanmayan barlar birlikte"


class _BozukKapi:
    def __init__(self, hedef=None, vektor_hatasi=None):
        self.hedef, self.vektor_hatasi = hedef, vektor_hatasi

    def sinyal_kosulu(self, t, **k):
        s = pozisyon.sinyal_kosulu(t, **k)
        return (not s if s is not None else True) if t == self.hedef else s

    def kosul_serisi(self, *a, **k):
        if self.vektor_hatasi is not None:
            raise self.vektor_hatasi
        return pozisyon.kosul_serisi(*a, **k)


def test_kosul_birimi_bozulan_tek_bar_tek_uyusmazlik():
    kimlik, izgara, y = _kur(702, "H2")
    siralar = list(range(0, len(izgara), 9))
    hedef = izgara[siralar[len(siralar) // 2]]
    sayac = ek.kosul_karsilastir([izgara[i] for i in siralar], siralar, "H2", y, kimlik, izgara,
                                 kapi=_BozukKapi(hedef=hedef))
    assert sayac.uyusmayan == [hedef]


def test_kosul_birimi_seri_hatasi_skalerde_karsiligi_yoksa_butun_barlar_uyusmaz():
    kimlik, izgara, y = _kur(703, "H2")
    siralar = list(range(0, 200, 5))
    sayac = ek.kosul_karsilastir([izgara[i] for i in siralar], siralar, "H2", y, kimlik, izgara,
                                 kapi=_BozukKapi(vektor_hatasi=ValueError("bilerek")))
    assert sayac.birim_hatasi == "seri:ValueError" and len(sayac.uyusmayan) == len(siralar)


def test_sembol_isi_kosul_ve_onay_yolu_satirlari_yalnizca_sayi_ve_evet_hayir_tasir(monkeypatch):
    kimlik, _, _ = _kur(704, "H2")
    monkeypatch.setattr(ek, "_donemler", lambda sembol: [0])
    asil = ek.bar_izgarasi
    monkeypatch.setattr(ek, "bar_izgarasi", lambda k, h: asil(k, h)[:400])
    ayar = {"hipotezler": ["H2", "H3"], "yapilandirma": "ilk", "roller": ["olay", "K1"], "funding_satiri": False,
            "bar": "tum", "n": 5, "kosul_ve_onay_yolu": True}
    satirlar = ek.sembol_isi(kimlik["sembol"], ayar)
    assert all(set(s) == set(ek.SUTUNLAR) for s in satirlar)
    kosul = [s for s in satirlar if s["rol"] == ek.KOSUL]
    assert [s["hipotez"] for s in kosul] == ["H2", "H3"]
    for s in kosul:
        assert s["hata"] == "" and s["uyusmayan_bar"] == 0 and s["karsilastirilan_bar"] > 0
        assert s["kapsam_bar"] == "" and s["sure_s"] == "" and s["ilk_20_uyusmayan"] == s["ilk_20_beklenmeyen"] == ""
    onay = [s for s in satirlar if s["rol"] == ek.ONAY_YOLU]
    assert [s["hipotez"] for s in onay] == ["H2", "H3"]
    for s in onay:
        assert s["onay_yolu"] in ("evet", "hayir") and s["sure_s"] == "" and s["karsilastirilan_bar"] == 0
    assert all(s["onay_yolu"] == "" for s in satirlar if s["rol"] != ek.ONAY_YOLU)
    assert all(s["sure_s"] == "" for s in satirlar)       # olay rolu kosuldu: hicbir satirda sure yok


def test_ekler_komut_satirinda_varsayilan_acik_ve_kapatilabilir(monkeypatch):
    gorulen = []

    def kos(semboller, ayar, isci, ara_dizin=None):
        gorulen.append(ayar["kosul_ve_onay_yolu"])
        raise RuntimeError("dur")

    monkeypatch.setattr(ek, "kos", kos)
    ek.main(["--bar", "ornek", "--sembol", "YOK", "--etiket", "pytest_p2b2"])
    ek.main(["--bar", "ornek", "--sembol", "YOK", "--etiket", "pytest_p2b2", "--no-kosul-ve-onay-yolu"])
    assert gorulen == [True, False]


def test_onay_yolu_satiri_sayi_tasimaz_ve_ozet_hayirlari_sayar():
    tablo = pd.DataFrame([ek._bos_satir("A", -1, "H2", "", ek.ONAY_YOLU) | {"onay_yolu": "hayir"},
                          ek._bos_satir("A", -1, "H3", "", ek.ONAY_YOLU) | {"onay_yolu": "evet"},
                          ek._bos_satir("A", 0, "H2", "y", ek.KOSUL) | {"uyusmayan_bar": 2, "karsilastirilan_bar": 9}])
    o = ek.ozet(tablo.reindex(columns=ek.SUTUNLAR))
    assert o["onay_yolu_hayir"] == 1 and o["kosul_uyusmayan"] == 2 and o["uyusmayan_bar"] == 2
