"""Rev.10 uygulamasi madde 5: kalan sizinti bulgulari.

1. `close_time` sutunu NaT olan cerceve 4h (ve 1d) denetiminden gecmez (on-kayit §4 "Fiyat okuma
   tabani"; sizinti testcisinin Rev.10 hazirlik bulgusu 2).
2. Sinyal degeri artik CAGIRANDAN ALINMAZ (Rev.11 madde 4): `sinyal_degerleri` anahtar sozcugu
   kabul edilmez. Enum uyesinin (IntEnum, IntFlag, Enum) bir kosul sonucunu pencere degeri gibi
   gecirme yolu boylece kapandi (on-kayit §2 "Tamlik sarti", denetci bulgusu D-C1; sizinti
   bulgusu 3).
3. `funding_ortalamasi`nin korumasiz kullanimina karsi iki koruma:
   - Tarama: analiz kodu (events/, study/, F2 analizleri) funding oranina (`oran_8h`, `oran`
     sutunu, `sekiz_saate_normallestir`) dogrudan erismez; H2 ortalamasinin tek yolu
     `funding.funding_ortalamasi`dir (butun pencere kurallari orada).
   - Kapi: fonksiyonun uyguladigi kural surumu (`funding.SINYAL_PENCERESI_REVIZYONU`) on-kayittaki
     "Funding sinyal penceresinin tamligi" paragrafinin son revizyonuyla aynidir; on-kayit bu
     paragrafi yeniden degistirirse kod guncellenmeden bu test kirilir.
Aga cikmaz.
"""

from __future__ import annotations

import enum
import re

import numpy as np
import pandas as pd
import pytest

import config
from data import funding, pozisyon
from tarama_yardimcisi import FUNDING_ORAN_DESENI, KOK, ihlaller
from sinyal_yardimcisi import kontrol, olay, yapilandirma
from kapi_yardimcisi import donem, veri
from kume_yardimcisi import kume_adi
from uygunluk_yardimcisi import esikler, gunluk, uygunluk

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)


# --- 1. NaT close_time -------------------------------------------------------------------------


def _cerceve(acilislar, kapanislar):
    return pd.DataFrame({"open_time": pd.DatetimeIndex(acilislar), "close_time": pd.to_datetime(kapanislar, utc=True)})


def test_nat_close_time_ile_gizlenmis_1d_cerceve_reddedilir():
    """Sizinti testcisinin ornegi: uc bar 1d araliginda, close_time'lari NaT, bir bar gercek 4h."""
    acilis = pd.DatetimeIndex([T("2025-01-01 00:00"), T("2025-01-01 04:00"), T("2025-01-02 00:00"),
                               T("2025-01-03 00:00")])
    kapanis = [pd.NaT, acilis[1] + H4 - pd.Timedelta(milliseconds=1), pd.NaT, pd.NaT]
    with pytest.raises(ValueError, match="close_time"):
        pozisyon._mum_zamanlari(_cerceve(acilis, kapanis))


@pytest.mark.parametrize("nat_sira", [0, 3, 5])
def test_tek_nat_bile_reddedilir(nat_sira):
    acilis = pd.date_range(T("2025-01-01"), periods=6, freq="4h")
    kapanis = list(acilis + H4 - pd.Timedelta(milliseconds=1))
    kapanis[nat_sira] = pd.NaT
    with pytest.raises(ValueError, match="close_time"):
        pozisyon._mum_zamanlari(_cerceve(acilis, kapanis))


def test_gecerli_close_time_kabul_edilir():
    acilis = pd.date_range(T("2025-01-01"), periods=6, freq="4h")
    assert len(pozisyon._mum_zamanlari(_cerceve(acilis, acilis + H4 - pd.Timedelta(milliseconds=1)))) == 6


def test_gunluk_hacimde_nat_close_time_reddedilir():
    g = gunluk(T("2025-01-01"), T("2025-01-10"))
    g.loc[4, "close_time"] = pd.NaT
    with pytest.raises(ValueError, match="close_time"):
        pozisyon._gunluk_hacim(g)
    # Tamami NaT: 4h cercevesi 1d gibi gosterilemez.
    g4 = gunluk(T("2025-01-01"), T("2025-01-10"))
    g4["close_time"] = pd.NaT
    with pytest.raises(ValueError, match="close_time"):
        pozisyon._gunluk_hacim(g4)


# --- 2. Enum kosul degeri ------------------------------------------------------------------------


class _Kosul(enum.IntEnum):
    YANLIS = 0
    DOGRU = 1


class _Bayrak(enum.IntFlag):
    YOK = 0
    VAR = 1


class _FloatKosul(float, enum.Enum):
    SIFIR = 0.0


DB, B = T("2025-01-01"), T("2025-04-10 20:00")
Z = pd.date_range(T("2025-03-01"), B, freq="4h")
MUM = pd.DataFrame({"open_time": Z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
_FZ = pd.date_range(DB, B + H4, freq="8h")
FUND = pd.DataFrame({"odeme_zamani": _FZ, "aralik_saat": 8.0, "oran": 0.0, "oran_8h": 0.0})


def _karar(**ek):
    return pozisyon.olay_karari(T("2025-03-05 04:00"), 18, config.BAR_4H, hipotez="H1", birincil_ufuk=18,
                                kume=kume_adi(T('2025-03-05 04:00')), **veri(MUM, FUND, DB, B, uygun_bas=DB),
                                **ek, **esikler(config.BAR_4H))


# Rev.11 madde 4: sinyal degerleri cagirandan alinmaz. Enum (ve bool) bir kosul sonucunu pencere
# degeri gibi gecirme yolu oldugu icin reddediliyordu; yol artik yok. Iddia "parametre kabul
# edilmez"e tasindi, enum ornekleri korunarak.
@pytest.mark.parametrize("deger", [_Kosul.YANLIS, _Kosul.DOGRU, _Bayrak.YOK, _Bayrak.VAR, _FloatKosul.SIFIR])
def test_enum_uyesi_tasiyan_sinyal_degerleri_kabul_edilmez(deger):
    with pytest.raises(TypeError, match="sinyal_degerleri"):
        _karar(**kontrol("H1"), sinyal_degerleri={"x": 1.0, "kosul": deger})


def test_kontrol_rolu_kabul_edilir():
    assert _karar(**kontrol("H1")).plan.ufuk == 18


# --- 3. funding_ortalamasi korumasi -------------------------------------------------------------


def test_analiz_kodu_funding_oranina_dogrudan_erismez():
    assert ihlaller(FUNDING_ORAN_DESENI) == []


@pytest.mark.parametrize("satir", [
    'fund["oran_8h"].rolling(6).mean()',
    "f.oran_8h.mean()",
    "funding.sekiz_saate_normallestir(o, a)",
    "seri['oran'].mean()",
    'x.loc[m, "oran"]',
])
def test_tarama_deseni_dogrudan_oran_erisimini_yakalar(tmp_path, satir):
    (tmp_path / "events").mkdir()
    (tmp_path / "events" / "h2.py").write_text(f"def f(fund, o, a, seri, x, m):\n    return {satir}\n",
                                                 encoding="utf-8")
    assert ihlaller(FUNDING_ORAN_DESENI, kok=tmp_path, izinli_altlar=()) == ["events/h2.py"]


def test_tarama_deseni_funding_ortalamasi_cagrisini_yakalamaz(tmp_path):
    (tmp_path / "events").mkdir()
    (tmp_path / "events" / "h2.py").write_text(
        "from data import funding\n"
        "def f(fund, t, kb, ks, db):\n"
        "    return funding.funding_ortalamasi(fund, t, '4h', saat=24, kume_baslangic=kb, kume_bitis=ks,"
        " donem_baslangic=db)\n", encoding="utf-8")
    assert ihlaller(FUNDING_ORAN_DESENI, kok=tmp_path, izinli_altlar=()) == []


def _paragraf_isaretleri(baslik: str) -> list[int]:
    metin = (KOK / "PREREGISTRATION.md").read_text(encoding="utf-8")
    bas = metin.index(f"**{baslik}")
    son = metin.find("\n\n", bas)
    paragraf = metin[bas:son if son != -1 else None]
    return sorted(int(n) for n in re.findall(r"\(rev\.(\d+)\)", paragraf))


def _paragraf_revizyonu(baslik: str) -> int:
    return max(_paragraf_isaretleri(baslik))


def test_sinyal_penceresi_kurali_on_kayit_surumuyle_ayni():
    assert _paragraf_revizyonu("Funding sinyal penceresinin tamlığı") == funding.SINYAL_PENCERESI_REVIZYONU == 11


def test_paragraf_revizyonu_en_yuksek_isareti_okur():
    """Sinir durumu (Rev.11 uygulamasi madde 1): mekanizma paragraftaki EN YUKSEK "(rev.N)" isaretini
    okur, ilkini degil. On-kayit paragrafi "(rev.9)" basligiyla acilir ve icinde rev.10 ile rev.11
    isaretleri gecer; mekanizma ilk isareti okusaydi sabit 9'da kalir ve Rev.11'i kacirirdi."""
    isaretler = _paragraf_isaretleri("Funding sinyal penceresinin tamlığı")
    assert isaretler[0] == 9 and isaretler[-1] == 11, isaretler
    assert _paragraf_revizyonu("Funding sinyal penceresinin tamlığı") == isaretler[-1]
