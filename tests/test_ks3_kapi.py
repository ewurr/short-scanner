"""Kapi sertlestirme turu 3: hata ile "olay yok" ayrimi (denetci KS2 D-C1).

`pencere.OlayOlusmaz` artik `ValueError` alt sinifi degildir. Veri hatalari `pencere.VeriHatasi`
(`ValueError` alt sinifi; `ZamanDizisiHatasi` dahil), cagri hatalari `TypeError`/`ValueError`/`DonemDisiSinyal`
ve onay hatalari `split.OnayGerekli`dir. Olay dusmelerini sayan kod yalnizca `OlayOlusmaz`i yakalar; bir veri
hatasi ret gerekcesi olarak sayilamaz, bir ret gerekcesi de `except ValueError` ile yutulamaz. Aga cikmaz.
"""

from __future__ import annotations

import pandas as pd
import pytest

from data import pencere, pozisyon, split
from kapi_yardimcisi import veri
from sinyal_yardimcisi import sinyal
from uygunluk_yardimcisi import esikler

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H = lambda n: pd.Timedelta(hours=n)  # noqa: E731

DB, B = T("2025-01-01"), T("2025-06-30 20:00")
Z = pd.date_range(T("2025-03-01"), B, freq="4h")
MUM = pd.DataFrame({"open_time": Z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
FUND = pd.DataFrame({"odeme_zamani": pd.date_range(DB, B + H(4), freq="8h"), "aralik_saat": 8.0,
                     "oran": 1e-4, "oran_8h": 1e-4})
T_SINYAL = T("2025-03-10 04:00")


def _karar(t=T_SINYAL, mum=MUM, fr=FUND, hipotez="H1", ufuk=None, kume="KESIF", **ek):
    tanim = pencere.hipotez_ufuklari(hipotez)
    return pozisyon.olay_karari(t, tanim.birincil if ufuk is None else ufuk, tanim.bar, hipotez=hipotez,
                                birincil_ufuk=tanim.birincil, kume=kume,
                                **veri(mum, fr, DB, B, uygun_bas=DB, **ek), sinyal_degerleri=sinyal(hipotez),
                                **esikler(tanim.bar))


# --- 3. Hata ile "olay yok" ayrimi -------------------------------------------------------------------


def test_sinif_hiyerarsisi():
    for sinif in (pencere.KumeSiniriHatasi, pencere.IleriKaymaSiniriHatasi, pencere.GirisBariYok,
                  pozisyon.SinyalPenceresiTamDegil, pozisyon.UygunDegil, pozisyon.FundingTamDegil,
                  pozisyon.SinyalBariYok):
        assert issubclass(sinif, pencere.OlayOlusmaz)
        assert not issubclass(sinif, ValueError) and not issubclass(sinif, TypeError)
    for sinif in (pencere.VeriHatasi, pencere.ZamanDizisiHatasi, pencere.DonemDisiSinyal, split.OnayGerekli):
        assert not issubclass(sinif, pencere.OlayOlusmaz)
    assert issubclass(pencere.ZamanDizisiHatasi, pencere.VeriHatasi)


def _olay_olusmaz_yakalayan_dongu(cagri):
    """F2'deki olay dongusunun dar yakalama deseni: yalnizca OlayOlusmaz sayilir, gerisi yukari cikar."""
    try:
        cagri()
    except pencere.OlayOlusmaz as ret:
        return pencere.ret_gerekcesi(ret)
    return "onay"


@pytest.mark.parametrize("bozma", ["inf_p0", "nan_p1", "tz_naive", "tekrarli", "izgara_disi"])
def test_veri_hatasi_olay_olusmaz_olarak_yakalanmaz(bozma):
    p = _karar()
    m = MUM.copy()
    ham = False
    if bozma == "inf_p0":
        m.loc[m["open_time"] == p.plan.giris, "open"] = float("inf")
    elif bozma == "nan_p1":
        m.loc[m["open_time"] == p.plan.cikis.zaman, p.plan.cikis.fiyat_alani] = float("nan")
    elif bozma == "tz_naive":
        m["open_time"] = pd.DatetimeIndex(m["open_time"]).tz_localize(None)
        ham = True
    elif bozma == "tekrarli":
        m = pd.concat([m, m.iloc[[10]]]).sort_values("open_time", kind="stable").reset_index(drop=True)
    else:
        m["open_time"] = m["open_time"] + H(1)
    with pytest.raises(pencere.VeriHatasi):
        _olay_olusmaz_yakalayan_dongu(lambda: _karar(mum=m, ham=ham) if ham else _karar(mum=m))


def test_ret_gerekcesi_except_valueerror_ile_yutulmaz():
    """Bir ret gerekcesi (`GirisBariYok`) `except ValueError` blogundan gecer: hata sanilip yutulmaz."""
    eksik = MUM.loc[MUM["open_time"] != T_SINYAL + H(4)]
    with pytest.raises(pencere.GirisBariYok):
        try:
            _karar(mum=eksik)
        except ValueError:  # pragma: no cover - yakalanmamali
            pytest.fail("OlayOlusmaz ValueError olarak yakalandi")


def test_cagri_hatasi_olay_olusmaz_degil():
    with pytest.raises((TypeError, ValueError)) as hata:
        _olay_olusmaz_yakalayan_dongu(lambda: _karar(kume="kesif"))
    assert not isinstance(hata.value, pencere.OlayOlusmaz)
    with pytest.raises(TypeError):
        pencere.ret_gerekcesi(pencere.VeriHatasi("x"))
