"""Rev.10 hazirligi, kapatmalar: tek karar noktasinin iki girdi denetimi. Aga cikmaz.

1. Fiyat okuma tabani (on-kayit §4 rev.8): close_time sutunu olmayan tek satirlik cerceve 4h serisi
   oldugu dogrulanamadigi icin reddedilir (sizinti testcisi Rev.9 bulgusu; D-B3'un kalan acigi).
2. Sinyal pencereleri (on-kayit §2 "Tamlik sarti"): Rev.11 madde 4'ten beri kapi sinyal
   degerini CAGIRANDAN ALMAZ; `sinyal_degerleri` anahtar sozcugu kabul edilmez. Denetci bulgusu
   D-C1'in (olumsuzlanmis bir kosulun NaN pencereyi True ile gizlemesi) konusu kalmadi ve iddia
   yapisal hale geldi.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import config
from data import pozisyon
from sinyal_yardimcisi import kontrol, olay, yapilandirma
from kapi_yardimcisi import donem, veri
from kume_yardimcisi import kume_adi
from uygunluk_yardimcisi import esikler, uygunluk

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)


@pytest.mark.parametrize("acilis", ["2025-03-01 00:00", "2025-03-01 04:00"])
def test_tek_satir_close_time_siz_reddedilir(acilis):
    with pytest.raises(ValueError, match="dogrulanamiyor"):
        pozisyon._mum_zamanlari(pd.DataFrame({"open_time": [T(acilis)]}))


def test_tek_satir_close_time_ile_sureye_gore_karar():
    dort = pd.DataFrame({"open_time": [T("2025-03-01 04:00")], "close_time": [T("2025-03-01 07:59:59.999")]})
    assert len(pozisyon._mum_zamanlari(dort)) == 1
    gun = pd.DataFrame({"open_time": [T("2025-03-01")], "close_time": [T("2025-03-01 23:59:59.999")]})
    with pytest.raises(ValueError, match="4 saati"):
        pozisyon._mum_zamanlari(gun)


def test_iki_satir_close_time_siz_ardisik_farkla_karar():
    assert len(pozisyon._mum_zamanlari(pd.DataFrame({"open_time": [T("2025-03-01"), T("2025-03-01 04:00")]}))) == 2
    with pytest.raises(ValueError):
        pozisyon._mum_zamanlari(pd.DataFrame({"open_time": [T("2025-03-01"), T("2025-03-02")]}))


def test_bos_cerceve_denetimden_hata_vermeden_doner():
    assert len(pozisyon._mum_zamanlari(pd.DataFrame({"open_time": pd.DatetimeIndex([], tz="UTC")}))) == 0


DB, B = T("2025-01-01"), T("2025-04-10 20:00")
Z = pd.date_range(T("2025-03-01"), B, freq="4h")
MUM = pd.DataFrame({"open_time": Z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
FUND = pd.DataFrame({"odeme_zamani": pd.date_range(DB, B, freq="8h"), "aralik_saat": 8.0, "oran": 0.0, "oran_8h": 0.0})


def _karar(**ek):
    return pozisyon.olay_karari(T("2025-03-05 04:00"), 6, config.BAR_4H, hipotez="H1", birincil_ufuk=18,
                                kume=kume_adi(T('2025-03-05 04:00')), **veri(MUM, FUND, DB, B, uygun_bas=DB),
                                **ek, **esikler(config.BAR_4H))


# Rev.11 madde 4: `sinyal_degerleri` anahtar sozcugu KALKTI; kapi degerleri kendisi hesaplar. Bu
# bolumun eski iddialari (bool ve olumsuzlanmis kosul bir pencere degeri gibi gecemez) artik
# yapisal olarak saglanir: kapi cagirandan hicbir sinyal degeri almaz. Iddia, "parametre
# yok"un kendisine tasindi; eski denetimlerin konusu kalmadi (denetci bulgusu D-C1 konusuz).
@pytest.mark.parametrize("degerler", [
    {"pencere": 1.0, "kosul": True},
    {"kosul": np.bool_(False)},
    {"pump_dip": 1.0, "pump_hacim_6": 1.0, "pump_hacim_medyani_180": 1.0, "tepe": 1.0},
])
def test_sinyal_degerleri_anahtar_sozcugu_kabul_edilmez(degerler):
    with pytest.raises(TypeError, match="sinyal_degerleri"):
        _karar(**kontrol("H1"), sinyal_degerleri=degerler)


def test_nan_pencere_olumsuz_kosulla_gizlenemez():
    """Eskiden `not (x < y)` gibi olumsuzlanmis bir kosul NaN pencereyi True ile gizleyebiliyordu.
    Rev.11'den beri bir pencere degeri KAPIYA VERILEMEZ: deger kapida hesaplanir ve NaN ise
    `SinyalPenceresiTamDegil` olur. Asagidaki eksik bar bunu veriyle gosterir."""
    # Eksik bar t'nin KENDI gunune konur (2025-03-05): o gun uygunluk penceresinin disindadir
    # (on-kayit §2 "Uygunluk penceresi ve t gunu"), bu yuzden yalnizca tepe penceresini dusurur.
    z = pd.DatetimeIndex(MUM["open_time"])
    mum = MUM.loc[z != T("2025-03-05 00:00")].reset_index(drop=True)
    with pytest.raises(pozisyon.SinyalPenceresiTamDegil):
        pozisyon.olay_karari(T("2025-03-05 04:00"), 6, config.BAR_4H, hipotez="H1", birincil_ufuk=18,
                             kume=kume_adi(T('2025-03-05 04:00')),
                             **veri(mum, FUND, DB, B, uygun_bas=DB),
                             **olay("H1", capa=T("2025-03-04 16:00")), **esikler(config.BAR_4H))


def test_kontrol_rolu_duz_seride_kabul_edilir():
    """Sinyal kurallarini sinamayan testlerin yolu: K1 rolu (on-kayit §6 rev.11)."""
    assert _karar(**kontrol("H1")).plan.sinyal_zamani == T("2025-03-05 04:00")
