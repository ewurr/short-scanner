"""On-kayit §4 rev.9 "F2 sarti": kismi kuyruk, pencere sonu esitlik affi ve funding ritmi
bayraklarini gercek kod uretir (`funding.funding_tamlik_ayrintisi` -> `pozisyon.olay_karari`).

"F2 raporunda, kismi kuyruk ve pencere sonu esitligi nedeniyle net getirisi tam dogrulanamayan
olaylarin payi her hipotez icin funding ritmi basina (8, 4, 2, 1 saat) raporlanir ve ana
sonuclar bu olaylar dislanarak bir saglamlik kontrolu olarak yeniden hesaplanir." Aga cikmaz;
oranlar sifir, getiri hesaplanmaz.
"""

from __future__ import annotations

from dataclasses import replace

import pandas as pd
import pytest

import config
from data import funding, pozisyon
from sinyal_yardimcisi import sinyal
from uygunluk_yardimcisi import uygunluk

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
DB = T("2025-01-01 00:00")
B = T("2025-04-10 20:00")
Z = pd.date_range(T("2025-03-01"), B, freq="4h")
MUM = pd.DataFrame({"open_time": Z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})


def _fund(saat, bas=DB, son=B, disla=()):
    z = [x for x in pd.date_range(bas, son, freq=f"{saat}h") if x not in set(disla)]
    return pd.DataFrame({"odeme_zamani": pd.DatetimeIndex(z), "aralik_saat": float(saat), "oran": 0.0,
                         "oran_8h": 0.0})


def _karar(fr, t, ufuk=6):
    return pozisyon.olay_karari(MUM, fr, t, ufuk, config.BAR_4H, hipotez="H1", birincil_ufuk=18, kume_baslangic=None,
                                kume_bitis=None, donem_baslangic=DB, donem_bitis=B, sinyal_degerleri=sinyal("H1"),
                                **uygunluk(config.BAR_4H, DB, B))


def test_sekiz_saatlik_ritimde_kismi_kuyruk():
    """8 saatlik ritim, 6 barlik pozisyon: giris 03-05 12:00, cikis 03-06 12:00; son kayit 08:00,
    sonraki odeme 16:00 -> 08:00-12:00 dilimi bir tam araliktan kisa.

    Rev.10 (on-kayit §4 "Ufuk degerlerinin baglanmasi"): kapi serbest ufuk kabul etmez; senaryo
    onceki 1 barlik ufuk yerine on-kayittaki en kisa 4h ufkuyla (6 bar) ayni bicimde kuruldu."""
    p = _karar(_fund(8), T("2025-03-05 08:00"))
    assert p.kuyruk_kismi and not p.son_esitlik_affi
    assert p.capa_aralik_saat == 8.0 and p.son_aralik_saat == 8.0 and p.tek_ritim


def test_dort_saatlik_ritimde_kuyruk_yok():
    p = _karar(_fund(4), T("2025-03-05 04:00"))
    assert not p.kuyruk_kismi and not p.son_esitlik_affi and p.capa_aralik_saat == 4.0


def test_pencere_sonu_esitlik_affi():
    """4 saatlik ritim, cikis anindaki (03-06 08:00) kayit yok: son kayit 04:00 + 4h = 08:00.
    Rev.10: 6 barlik ufuk (onceki 1 bar); ayni senaryo."""
    fr = _fund(4, disla=[T("2025-03-06 08:00")])
    p = _karar(fr, T("2025-03-05 04:00"))
    assert p.son_esitlik_affi and not p.kuyruk_kismi


def test_karisik_ritim_etiketleri():
    """Ritim 8 saatten 4 saate geciyor: capa 8h, dizinin son kaydi 4h, tek ritim degil."""
    once = _fund(8, son=T("2025-03-05 08:00"))
    sonra = _fund(4, bas=T("2025-03-05 12:00"))
    p = _karar(pd.concat([once, sonra], ignore_index=True), T("2025-03-05 04:00"), ufuk=6)
    assert p.capa_aralik_saat == 8.0 and p.son_aralik_saat == 4.0 and not p.tek_ritim


def test_bayraklar_gercek_tamlik_satiriyla_ayni():
    fr = _fund(8)
    for t in pd.date_range(T("2025-03-05"), periods=12, freq="4h"):
        p = _karar(fr, t, ufuk=6)
        a = funding.pozisyon_funding_ayrintisi(fr, p.plan)
        assert (p.kuyruk_kismi, p.son_esitlik_affi, p.tek_ritim) == (
            bool(a["kuyruk_kismi"]), bool(a["son_esitlik_affi"]), bool(a["tek_ritim"]))
        assert (p.capa_aralik_saat, p.son_aralik_saat) == (a["capa_aralik_saat"], a["son_aralik_saat"])


@pytest.mark.parametrize("alan,deger", [("kuyruk_kismi", True), ("son_esitlik_affi", True),
                                        ("capa_aralik_saat", 1.0), ("tek_ritim", False)])
def test_bayraklar_imzaya_bagli(alan, deger):
    p = _karar(_fund(4), T("2025-03-05 04:00"))
    with pytest.raises(ValueError):
        pozisyon.pozisyon_fiyatlari(replace(p, **{alan: deger}))
