"""Denetci bulgusu D-C6: donem siniri `None` ile kapatilamaz; kaynak taramasi bunu yakalar.

On-kayit §2 "Listeleme donemi": "Tum geriye bakis pencereleri donem baslangicini asamaz;
asiyorsa deger hesaplanmaz ve o barda olay olusmaz." Tek karar noktasi (`olay_karari`,
`pencere.pozisyon_plani`) ve uygunluk donem sinirlarini None ile kabul etmez; analiz kodu
(events/, study/, analysis/ F2 ve sonrasi) pencere fonksiyonlarina `donem_*=None` veremez
(`tarama_yardimcisi.DONEM_NONE_DESENI`). Aga cikmaz.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import eligibility, pencere, pozisyon
from tarama_yardimcisi import DONEM_NONE_DESENI, ihlaller
from sinyal_yardimcisi import sinyal
from uygunluk_yardimcisi import uygunluk

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
BAS, B = T("2025-01-01 00:00"), T("2025-04-10 20:00")
Z = pd.date_range(BAS, B, freq="4h")
MUM = pd.DataFrame({"open_time": Z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
FUND = pd.DataFrame({"odeme_zamani": pd.date_range(BAS, B, freq="8h"), "aralik_saat": 8.0, "oran": 0.0,
                     "oran_8h": 0.0})


@pytest.mark.parametrize("sinir", ["donem_baslangic", "donem_bitis"])
def test_karar_noktasi_donem_sinirini_none_ile_kabul_etmez(sinir):
    sinirlar = {"donem_baslangic": BAS, "donem_bitis": B, sinir: None}
    with pytest.raises(TypeError):
        pozisyon.olay_karari(MUM, FUND, T("2025-03-05 04:00"), 6, config.BAR_4H, hipotez="H1", birincil_ufuk=18,
                             kume_baslangic=None, kume_bitis=None, sinyal_degerleri=sinyal("H1"),
                             **sinirlar, **uygunluk(config.BAR_4H, BAS, B))
    with pytest.raises(TypeError):
        pencere.pozisyon_plani(Z, T("2025-03-05 04:00"), 6, config.BAR_4H, birincil_ufuk=18,
                               kume_baslangic=None, kume_bitis=None, **sinirlar)


def test_uygunluk_donem_basini_none_ile_kabul_etmez():
    hacim = eligibility.gunluk_hacim_serisi(uygunluk(config.BAR_4H, BAS, B)["gunluk_mumlar"])
    with pytest.raises(TypeError):
        eligibility.uygunluk_karari(hacim, T("2025-03-05"), config.BAR_4H, donem_baslangic=None, donem_bitis=B,
                                    kume_baslangic=None, asgari_hacim=config.ASGARI_HACIM_4H,
                                    asgari_listeleme_yasi_gun=config.ASGARI_LISTELEME_YASI_GUN)


def test_tarama_donem_none_esdegerlerini_yakalar(tmp_path):
    ornekler = {
        "events/h1.py": "v = pencere.pencere_degeri(s, t, 30, bar, t_dahil=True, kume_baslangic=k, donem_baslangic=None)\n",
        "events/h2.py": "v = funding.funding_ortalamasi(fr, t, bar, saat=24, kume_baslangic=k, donem_baslangic = None)\n",
        "study/k1.py": "sinirlar = {\"donem_baslangic\": None, \"kume_baslangic\": k}\n",
        "study/k2.py": "sinirlar = dict(donem_bitis=None)\n",
        "study/k3.py": "v = f(**{'donem_bitis': None})\n",
        "analysis/02_h2/calistir.py": "donem_baslangic = None\n",
    }
    for ad, metin in ornekler.items():
        yol = tmp_path / ad
        yol.parent.mkdir(parents=True, exist_ok=True)
        yol.write_text(metin, encoding="utf-8")
    temiz = tmp_path / "events" / "h3.py"
    temiz.write_text("v = pencere.pencere_degeri(s, t, 30, bar, t_dahil=True, kume_baslangic=k,\n"
                     "                           donem_baslangic=d.baslangic)\nx = donem_bitis_None_degil\n",
                     encoding="utf-8")
    izinli = tmp_path / "tests" / "test_x.py"
    izinli.parent.mkdir()
    izinli.write_text("pencere_degeri(s, t, 5, bar, t_dahil=True, kume_baslangic=None, donem_baslangic=None)\n",
                      encoding="utf-8")
    assert ihlaller(DONEM_NONE_DESENI, kok=tmp_path) == sorted(ornekler)


def test_depoda_donem_none_yok():
    assert ihlaller(DONEM_NONE_DESENI) == [], "analiz kodu donem sinirini None ile kapatiyor"
