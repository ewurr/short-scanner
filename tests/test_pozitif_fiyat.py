"""Kapinin okudugu fiyat POZITIF olmali (koruma turu madde 2b).

Sizinti bulgusu: `_sonlu` ve `klines.hucreleri_tam_mi` yalnizca `isfinite`e bakiyordu, bu yuzden
`open = 0.0` ya da `-1.0` ile onay olusuyor ve MAE (`max(H, P1) / P0 - 1`) sifira bolmeye
gidiyordu.

Olcum (madde 2a, `koruma_olcumu.py --olcum pozitif_fiyat`, butun evren, temiz agac): donem ici
3.378.942 4h barin HICBIRINDE open/high/low/close sifir ya da negatif degil. Madde 2b bu yuzden
"sifir" dalini uygular: sifir/negatif fiyat mesru bir piyasa durumu degil BOZUK VERIDIR, kapi onu
sessizce "olay olusmaz" diye gecmez, `pencere.VeriHatasi` verir. Bu bir KURAL degil HATA yoludur,
dolayisiyla on-kayit degisikligi gerektirmez (`sinyal._pozitif` ile ayni tutum).

Aga cikmaz; getiri hesaplanmaz.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import pencere, pozisyon
from kapi_yardimcisi import veri
from sinyal_yardimcisi import kontrol
from uygunluk_yardimcisi import esikler

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H = lambda n: pd.Timedelta(hours=n)  # noqa: E731

DB, B = T("2025-01-01"), T("2025-06-30 20:00")
Z = pd.date_range(T("2025-03-01"), B, freq="4h")
MUM = pd.DataFrame({"open_time": Z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
FUND = pd.DataFrame({"odeme_zamani": pd.date_range(DB, B + H(4), freq="8h"), "aralik_saat": 8.0,
                     "oran": 1e-4, "oran_8h": 1e-4})
T_SINYAL = T("2025-03-10 04:00")


def _karar(mum=MUM, hipotez="H1"):
    tanim = pencere.hipotez_ufuklari(hipotez)
    return pozisyon.olay_karari(T_SINYAL, tanim.birincil, tanim.bar, hipotez=hipotez,
                                birincil_ufuk=tanim.birincil, kume="KESIF",
                                **veri(mum, FUND, DB, B, uygun_bas=DB), **kontrol(hipotez),
                                **esikler(tanim.bar))


def _temiz_plan():
    """Saglam dunyada plan: giris ve cikis zamanlari."""
    return _karar().plan


# --- 1. Saf denetim ---------------------------------------------------------------------------


@pytest.mark.parametrize("deger", [0.0, -0.0, -1.0, -1e-9])
def test_pozitif_olmayan_fiyat_veri_hatasi(deger):
    with pytest.raises(pencere.VeriHatasi, match="pozitif bir fiyat"):
        pozisyon._pozitif_fiyat(deger, "P0")


@pytest.mark.parametrize("deger", [float("nan"), float("inf"), float("-inf")])
def test_sonlu_olmayan_fiyat_hala_veri_hatasi(deger):
    """Sonluluk denetimi kaldirilmadi."""
    with pytest.raises(pencere.VeriHatasi):
        pozisyon._pozitif_fiyat(deger, "P0")


@pytest.mark.parametrize("deger", [1e-12, 0.5, 1.0, 1e6])
def test_pozitif_fiyat_gecer(deger):
    assert pozisyon._pozitif_fiyat(deger, "P0") == deger


# --- 2. Kapi: P0, P1 ve MAE penceresi ---------------------------------------------------------


@pytest.mark.parametrize("deger", [0.0, -1.0])
def test_giris_barinda_pozitif_olmayan_acilis_onay_vermez(deger):
    """Bulgunun kendisi: P0 ≤ 0 ile onay olusuyor ve MAE sifira bolmeye gidiyordu."""
    plan = _temiz_plan()
    m = MUM.copy()
    m.loc[m["open_time"] == plan.giris, "open"] = deger
    with pytest.raises(pencere.VeriHatasi, match="P0"):
        _karar(m)


@pytest.mark.parametrize("deger", [0.0, -2.5])
def test_cikis_barinda_pozitif_olmayan_fiyat_onay_vermez(deger):
    plan = _temiz_plan()
    m = MUM.copy()
    m.loc[m["open_time"] == plan.cikis.zaman, plan.cikis.fiyat_alani] = deger
    with pytest.raises(pencere.VeriHatasi, match="P1"):
        _karar(m)


def test_mae_penceresindeki_pozitif_olmayan_high_onay_vermez():
    plan = _temiz_plan()
    m = MUM.copy()
    orta = (m["open_time"] > plan.giris) & (m["open_time"] < plan.cikis.zaman)
    hedef = m.loc[orta, "open_time"].iloc[3]
    m.loc[m["open_time"] == hedef, "high"] = 0.0
    with pytest.raises(pencere.VeriHatasi, match="high"):
        _karar(m)


def test_pencere_disindaki_pozitif_olmayan_high_onayi_etkilemez():
    """Yanlis pozitif denetimi: pozisyon penceresinin DISINDAKI bozuk high onayi dusurmemeli."""
    plan = _temiz_plan()
    m = MUM.copy()
    uzak = m["open_time"] > plan.cikis.zaman + H(40)
    m.loc[uzak, "high"] = 0.0
    assert _karar(m).p0 > 0


def test_saglam_dunyada_onay_ve_mae_hesaplanir():
    """Olumlu kontrol: degisiklik mesru yolu kapatmadi."""
    p = _karar()
    assert p.p0 > 0 and p.p1 > 0
    assert pozisyon.mae(p) == pytest.approx(0.0)


def test_mae_sifira_bolme_yoluna_hic_girmez():
    """P0 = 0 kapida reddedildigi icin `mae` artik sifira bolmez: onay nesnesi hic olusmaz."""
    plan = _temiz_plan()
    m = MUM.copy()
    m.loc[m["open_time"] == plan.giris, "open"] = 0.0
    with pytest.raises(pencere.VeriHatasi):
        pozisyon.mae(_karar(m))


# --- 3. Kontrol rolunde de ayni ---------------------------------------------------------------


@pytest.mark.parametrize("rol", ["K1", "K2"])
def test_kontrol_rolunde_de_pozitif_olmayan_fiyat_reddedilir(rol):
    plan = _temiz_plan()
    m = MUM.copy()
    m.loc[m["open_time"] == plan.giris, "open"] = 0.0
    tanim = pencere.hipotez_ufuklari("H1")
    with pytest.raises(pencere.VeriHatasi):
        pozisyon.olay_karari(T_SINYAL, tanim.birincil, tanim.bar, hipotez="H1",
                             birincil_ufuk=tanim.birincil, kume="KESIF",
                             **veri(m, FUND, DB, B, uygun_bas=DB), **kontrol("H1", rol=rol),
                             **esikler(tanim.bar))
