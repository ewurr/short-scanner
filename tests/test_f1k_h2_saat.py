"""H2'nin 24 saatlik funding penceresi on-kayit kaynakli config degeridir (F1 kapanis turu, denetci D-B3).

On-kayit §5 H2 madde 1: "t anina kadarki son 24 saatteki funding oranlarinin ortalamasi"; §4
"Funding sinyal penceresinin tamligi": "Pencere t barinin kapanisinda biter ve 24 saat geriye uzanir."
Tek kaynak `config.H2_FUNDING_PENCERESI_SAAT`, ufuklarla ayni on-kayit bolumunde. `funding_ortalamasi`
ve `sinyal_penceresi_ayrintisi` baska deger kabul etmez. Aga cikmaz.
"""

from __future__ import annotations

import re

import pandas as pd
import pytest

import config
from data import funding
from tarama_yardimcisi import KOK

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
DB = T("2030-01-01")
FUND = pd.DataFrame({"odeme_zamani": pd.date_range(T("2030-06-01"), T("2030-06-20"), freq="8h"), "aralik_saat": 8.0,
                     "oran": 1e-4, "oran_8h": 1e-4})
T0 = T("2030-06-10 20:00")


def test_deger_ve_bolum():
    assert config.H2_FUNDING_PENCERESI_SAAT == 24
    metin = (KOK / "config.py").read_text(encoding="utf-8")
    bolum = metin[metin.index("# --- Hipotez izgarasi ve ufuklar"):]
    bolum = bolum[:bolum.index("\n# --- ", 10)]
    assert re.search(r"^H2_FUNDING_PENCERESI_SAAT\s*=\s*24\s*$", bolum, re.M)
    assert "ON-KAYIT DEGILDIR" not in bolum


@pytest.mark.parametrize("saat", [1, 8, 23, 25, 48])
def test_serbest_saat_reddedilir(saat):
    with pytest.raises(ValueError, match="on-kayit"):
        funding.funding_ortalamasi(FUND, T0, config.BAR_4H, saat=saat, kume_baslangic=None, kume_bitis=None,
                                   donem_baslangic=DB)
    with pytest.raises(ValueError, match="on-kayit"):
        funding.sinyal_penceresi_ayrintisi(FUND, [T0], config.BAR_4H, saat=saat, kume_baslangic=None,
                                           kume_bitis=None, donem_baslangic=DB)


@pytest.mark.parametrize("saat", [24.0, True, "24", None])
def test_tamsayi_olmayan_saat_reddedilir(saat):
    with pytest.raises((TypeError, ValueError)):
        funding.funding_ortalamasi(FUND, T0, config.BAR_4H, saat=saat, kume_baslangic=None, kume_bitis=None,
                                   donem_baslangic=DB)


def test_on_kayit_degeri_kabul_edilir():
    assert funding.funding_ortalamasi(FUND, T0, config.BAR_4H, saat=config.H2_FUNDING_PENCERESI_SAAT,
                                      kume_baslangic=None, kume_bitis=None, donem_baslangic=DB) == pytest.approx(1e-4)


def test_olcum_betigi_config_degerini_okur():
    metin = (config.ANALIZ_DIZINI / "00_veri_denetimi" / "rev10_uygulama.py").read_text(encoding="utf-8")
    assert re.search(r"^SAAT\s*=\s*config\.H2_FUNDING_PENCERESI_SAAT\b", metin, re.M)


def test_kod_icinde_gomulu_24_saat_yok():
    """config.py ve testler disinda H2 penceresi icin gomulu `saat=24` ya da `SAAT = 24` yazilmaz."""
    desen = re.compile(r"\bsaat\s*=\s*24\b|^\s*SAAT\s*=\s*24\b", re.M | re.I)
    bulunan = []
    for yol in sorted(KOK.rglob("*.py")):
        goreli = yol.relative_to(KOK).as_posix()
        if goreli == "config.py" or goreli.startswith(("tests/", ".claude/")) or "cache" in yol.parts:
            continue
        if desen.search(yol.read_text(encoding="utf-8", errors="replace")):
            bulunan.append(goreli)
    assert bulunan == []
