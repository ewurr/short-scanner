"""F1-K1 §2: §14.49'un kucuk duzeltmeleri (madde kodlari test adlarinda).

- D-C3: `k2_bitleri` grup kuralini kendisi yazmaz, `grup_dogrula`yi cagirir.
- D-C11: `split._adres_kimliksiz` sorgu dizgisindeki ve parcadaki belirteci de siler.
Aga cikmaz; sentetik dunya.
"""

from __future__ import annotations

import ast
import inspect
import textwrap

import pytest

from data import pozisyon, sinyal
from esitlik_yardimcisi import dunya

BAS, BITIS = "2021-01-01", "2021-08-31 20:00"


def _y():
    return dict(sinyal.izgara("H2")[0])


# --- D-C3 ------------------------------------------------------------------------------------------------------------

def test_D_C3_k2_bitleri_grup_kuralini_grup_dogrula_dan_alir(monkeypatch):
    kimlik, _ = dunya(641, BAS, BITIS)
    t = pozisyon.hipotez_izgarasi_barlari("H2", kume="KESIF", **kimlik)[500]
    cagri = []
    asil = pozisyon.grup_dogrula

    def casus(sembol, kume):
        cagri.append((sembol, kume))
        return asil(sembol, kume)

    monkeypatch.setattr(pozisyon, "grup_dogrula", casus)
    pozisyon.k2_bitleri("H2", _y(), kume="KESIF", **kimlik, zamanlar=[t])
    assert (kimlik["sembol"], "KESIF") in cagri

    # grup_dogrula reddederse (ValueError) bit acik denetimle 0; veri okunmaz.
    def ret(sembol, kume):
        raise ValueError("bilerek: kumeye ait degil")

    def yukleme_yasak(*a, **k):
        raise AssertionError("grup reddinde veri okunmamali")

    monkeypatch.setattr(pozisyon, "grup_dogrula", ret)
    monkeypatch.setattr(pozisyon, "_karar_girdisi", yukleme_yasak)
    assert pozisyon.k2_bitleri("H2", _y(), kume="KESIF", **kimlik, zamanlar=[t, t]).tolist() == [False, False]

    # Baska bir hata 0 bitine donusmez (G10).
    class Yasak(PermissionError):
        pass

    def yasak(sembol, kume):
        raise Yasak("bilerek")

    monkeypatch.setattr(pozisyon, "grup_dogrula", yasak)
    with pytest.raises(Yasak):
        pozisyon.k2_bitleri("H2", _y(), kume="KESIF", **kimlik, zamanlar=[t])


def test_D_C3_k2_bitleri_kaynaginda_ikinci_grup_kurali_yok():
    agac = ast.parse(textwrap.dedent(inspect.getsource(pozisyon.k2_bitleri)))
    adlar = {d.attr for d in ast.walk(agac) if isinstance(d, ast.Attribute)} | \
        {d.id for d in ast.walk(agac) if isinstance(d, ast.Name)}
    assert "grup_dogrula" in adlar
    assert "kume_tanimi" not in adlar and "_kayitlar" not in adlar


# --- D-C11 -----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("adres,beklenen", [
    ("https://github.com/x/y.git?access_token=gizli_belirtec", "https://github.com/x/y.git?***"),
    ("https://github.com/x/y.git?a=1&access_token=gizli_belirtec#parca", "https://github.com/x/y.git?***"),
    ("https://kullanici:gizli@github.com/x/y.git?access_token=gizli_belirtec", "https://***@github.com/x/y.git?***"),
    ("https://github.com/x/y.git#gizli_belirtec", "https://github.com/x/y.git#***"),
    ("https://gizli@github.com/x/y.git#access_token=gizli_belirtec", "https://***@github.com/x/y.git#***"),
    ("gizli_kullanici@ornek.org:x/y.git?access_token=gizli_belirtec", "***@ornek.org:x/y.git?***"),
    ("https://github.com/x/y.git", "https://github.com/x/y.git"),
])
def test_D_C11_adres_kimliksiz_sorgu_ve_parca_belirtecini_siler(adres, beklenen):
    from data import split

    sonuc = split._adres_kimliksiz(adres)
    assert sonuc == beklenen
    assert "gizli" not in sonuc and "access_token" not in sonuc
