"""Denetci bulgusu D-C6: ornekleme alt tohumu ve demeti havuzla birlikte tasinir.

On-kayit §8 madde 1 (rev.13), raporlanacak kalemler: "... havuzu 10'dan az olan olay sayisi; ...
tohum ve alt tohum TURETME DEMETI." §6: "Ornekleme, §7'deki tohumdan (hipotez, yapilandirma, kume,
sembol, olay zamani) demetiyle turetilen alt tohumla yapilir."

Bulgu: p-degeri tarafinda iki alan `istatistik.PSonucu`da tasiniyordu (`tohum`,
`alt_tohum_demeti`, `genel_tohum`), ornekleme tarafinda hicbir yerde tasinmiyordu ve F2'nin
yeniden turetmesi gerekiyordu. Asimetri kapandi.

Aga cikmaz; getiri hesaplanmaz.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import istatistik, ornekleme
from ornekleme_yardimcisi import k1_adaylari_kur, k2_adaylari_kur, ornekle

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
BARLAR = [T("2025-03-01") + i * H4 for i in range(25)]
TB = T("2025-03-10 04:00")


def test_havuz_alt_tohumu_ve_demeti_tasir():
    havuz = ornekle(k1_adaylari_kur(BARLAR), sembol="AAVEUSDT", olay_zamani=TB)
    assert havuz.tohum == ornekleme.alt_tohum("H2", "H2:phi=0.0003,k=3", "KESIF", "AAVEUSDT", TB)
    assert havuz.alt_tohum_demeti == ("H2:phi=0.0003,k=3", "KESIF", "AAVEUSDT", TB.isoformat())
    assert havuz.genel_tohum == config.TOHUM


def test_demet_tohumu_yeniden_uretir():
    """Rapordaki demetten tohum yeniden turetilebilir: tek turetme yolu `tohum_turet`."""
    havuz = ornekle(k1_adaylari_kur(BARLAR), sembol="BTCUSDT", olay_zamani=TB)
    assert havuz.tohum == ornekleme.tohum_turet(*havuz.alt_tohum_demeti)


@pytest.mark.parametrize("degisen", [{"sembol": "ZZZUSDT"}, {"olay_zamani": TB + H4}])
def test_demetin_her_ogesi_tohumu_degistirir(degisen):
    temel = ornekle(k1_adaylari_kur(BARLAR), sembol="AAVEUSDT", olay_zamani=TB)
    baska = ornekle(k1_adaylari_kur(BARLAR), **{"sembol": "AAVEUSDT", "olay_zamani": TB, **degisen})
    assert baska.tohum != temel.tohum and baska.alt_tohum_demeti != temel.alt_tohum_demeti


def test_on_kayit_sayisindan_az_adayda_da_tasinir():
    """Cekim yapilmasa bile (aday <= 10) tohum ve demet raporlanir."""
    havuz = ornekle(k1_adaylari_kur(BARLAR[:4]), sembol="AAVEUSDT", olay_zamani=TB)
    assert len(havuz) == 4 and havuz.eksik
    assert havuz.tohum and havuz.alt_tohum_demeti and havuz.genel_tohum == config.TOHUM


def test_bos_havuzda_cekim_yok():
    havuz = ornekle(k1_adaylari_kur([]), sembol="AAVEUSDT", olay_zamani=TB)
    assert havuz.secilenler == () and havuz.tohum == 0 and havuz.alt_tohum_demeti == ()


def test_k2_havuzu_da_tasir():
    havuz = ornekle(k2_adaylari_kur([f"S{i:02d}USDT" for i in range(20)], t=TB), sembol="AAAUSDT",
                    olay_zamani=TB)
    assert havuz.tohum and havuz.alt_tohum_demeti[2] == "AAAUSDT"


def test_p_degeri_tarafiyla_simetrik():
    """Iki taraf ayni alan adlarini kullanir (`tohum`, `alt_tohum_demeti`, `genel_tohum`)."""
    havuz = ornekle(k1_adaylari_kur(BARLAR), sembol="AAVEUSDT", olay_zamani=TB)
    sonuc = istatistik.yeniden_ornekle([0.1], [[0.0]], hipotez="H2",
                                       yapilandirma={"phi": 0.0003, "k": 3}, kume="KESIF",
                                       kontrol_kumesi="K1")
    for ad in ("tohum", "alt_tohum_demeti", "genel_tohum"):
        assert hasattr(havuz, ad) and hasattr(sonuc, ad)
    assert havuz.genel_tohum == sonuc.genel_tohum == config.TOHUM
    assert havuz.tohum != sonuc.tohum, "iki demet farkli, tohumlar da farkli"


def test_esitlik_ve_tekrarlanabilirlik_bozulmadi():
    """`KontrolHavuzu` esitligi: ayni demet ayni havuzu verir (yeni alanlar dahil)."""
    a = ornekle(k1_adaylari_kur(BARLAR), sembol="AAVEUSDT", olay_zamani=TB)
    b = ornekle(k1_adaylari_kur(BARLAR), sembol="AAVEUSDT", olay_zamani=TB)
    assert a == b
    assert ornekleme.olay_analize_girer(a, b) is True
