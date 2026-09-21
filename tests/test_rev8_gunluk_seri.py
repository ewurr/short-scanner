"""On-kayit §2 rev.8 "1 gunluk barlar" ve §2 Veri bosluklari: tek 1d serisi. Aga cikmaz.

"1d barlar yalnizca donem ici 4h barlardan turetilir ... Bir gun, yalnizca o gunun
00:00, 04:00, 08:00, 12:00, 16:00 ve 20:00 UTC acilisli alti 4h barinin tamami
mevcut ve ayni donemin icindeyse olusur ... Bu seri tektir."
"""

from __future__ import annotations

import importlib.util
import re
import sys

import pandas as pd
import pytest

import config
from data import klines
from data import universe as universe_modulu
from data.donem import Donem

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
DIZIN = config.ANALIZ_DIZINI / "00_veri_denetimi"


def _mum(zamanlar, hacim=1.0):
    z = pd.DatetimeIndex(zamanlar)
    return pd.DataFrame({
        "open_time": z, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": hacim,
        "close_time": z + pd.Timedelta(hours=4), "quote_volume": hacim, "count": 1,
        "taker_buy_volume": 0.0, "taker_buy_quote_volume": 0.0,
    })


def _gunler(m, donemler):
    return list(klines.gunluge_cevir(m, donemler=donemler)["open_time"])


def _seri(bas, son):
    return pd.date_range(T(bas), T(son), freq="4h")


def test_kismi_ilk_ve_son_gun_seride_yok():
    m = _mum(_seri("2025-01-01 00:00", "2025-01-06 20:00"))
    d = Donem(T("2025-01-01 08:00"), T("2025-01-05 08:00"), 20, 20)
    assert _gunler(m, [d]) == [T("2025-01-02"), T("2025-01-03"), T("2025-01-04")]


def test_donem_disi_dolgu_barlari_gun_olusturmaz():
    """6 bari mevcut olan ama bir kismi donem disi (dolgu) olan gun olusmaz;
    tamamen dolgudan olusan gun de olusmaz."""
    m = _mum(_seri("2025-01-01 00:00", "2025-01-08 20:00"))
    d = Donem(T("2025-01-01 00:00"), T("2025-01-04 20:00"), 24, 24)
    assert _gunler(m, [d]) == [T("2025-01-01"), T("2025-01-02"), T("2025-01-03"), T("2025-01-04")]


def test_donem_bitisi_20_de_ise_son_gun_tam():
    m = _mum(_seri("2025-01-01 00:00", "2025-01-03 20:00"))
    assert _gunler(m, [Donem(T("2025-01-01 00:00"), T("2025-01-03 20:00"), 18, 18)])[-1] == T("2025-01-03")
    assert _gunler(m, [Donem(T("2025-01-01 00:00"), T("2025-01-03 16:00"), 17, 17)])[-1] == T("2025-01-02")


def test_iki_donemin_ayni_gundeki_barlari_birlesmez():
    """Sentetik: donem A 04:00'te biter, donem B 08:00'de baslar; gunun alti bari
    mevcut ama ayni donemde degil -> gun olusmaz."""
    m = _mum(_seri("2025-01-01 00:00", "2025-01-03 20:00"))
    a = Donem(T("2025-01-01 00:00"), T("2025-01-02 04:00"), 8, 8)
    b = Donem(T("2025-01-02 08:00"), T("2025-01-03 20:00"), 10, 10)
    assert _gunler(m, [a, b]) == [T("2025-01-01"), T("2025-01-03")]


def test_hizasiz_bar_gun_olusturmaz_ama_hizali_alti_bar_yeter():
    z = list(_seri("2025-01-01 00:00", "2025-01-01 16:00")) + [T("2025-01-01 13:00")]  # 20:00 yok
    d = Donem(T("2025-01-01 00:00"), T("2025-01-01 20:00"), 6, 6)
    assert _gunler(_mum(sorted(z)), [d]) == []
    z = list(_seri("2025-01-01 00:00", "2025-01-01 20:00")) + [T("2025-01-01 13:00")]  # 6 hizali + 1 hizasiz
    gun = klines.gunluge_cevir(_mum(sorted(z)), donemler=[d])
    assert list(gun["open_time"]) == [T("2025-01-01")]
    assert gun["volume"].iloc[0] == 6.0  # hizasiz bar toplama girmez


def test_toplama_kurali():
    m = _mum(_seri("2025-01-01 00:00", "2025-01-01 20:00"))
    m["open"] = [1, 2, 3, 4, 5, 6]
    m["close"] = [6, 5, 4, 3, 2, 1]
    m["high"] = [1, 9, 1, 1, 1, 1]
    m["low"] = [3, 3, 3, 0.1, 3, 3]
    g = klines.gunluge_cevir(m, donemler=[Donem(T("2025-01-01 00:00"), T("2025-01-01 20:00"), 6, 6)]).iloc[0]
    assert (g["open"], g["close"], g["high"], g["low"], g["volume"]) == (1, 1, 9, 0.1, 6.0)


def test_donemler_zorunlu_ve_bos_liste_bos_seri():
    m = _mum(_seri("2025-01-01 00:00", "2025-01-01 20:00"))
    with pytest.raises(TypeError):
        klines.gunluge_cevir(m)
    with pytest.raises(TypeError):
        klines.gunluge_cevir(m, donemler=None)
    assert klines.gunluge_cevir(m, donemler=[]).empty


def test_1d_yukleyici_ayni_fonksiyonu_commit_edilmis_donemlerle_cagirir(monkeypatch):
    """Tek 1d yolu: `ham_mumlari_yukle(s, "1d")` = `gunluge_cevir(4h, donemler=universe)`."""
    m = _mum(_seri("2025-01-01 00:00", "2025-01-06 20:00"))
    d = Donem(T("2025-01-01 08:00"), T("2025-01-05 08:00"), 20, 20)
    gercek = klines.ham_mumlari_yukle

    def sahte(sembol, bar=config.BAR_4H, yenile=False):
        return m.copy() if bar == config.BAR_4H else gercek(sembol, bar, yenile)

    monkeypatch.setattr(klines, "ham_mumlari_yukle", sahte)
    monkeypatch.setattr(universe_modulu, "evren_yukle", lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr(universe_modulu, "sembol_donemleri", lambda e, s: [d])
    sonuc = gercek("XUSDT", config.BAR_1D)
    pd.testing.assert_frame_equal(sonuc, klines.gunluge_cevir(m, donemler=[d]))


def test_baska_1d_turetme_yolu_yok():
    """Fiyatlardan gun toplayan (open 'first') tek fonksiyon `klines.gunluge_cevir`dir.
    Karsilastirma sayimlari (calistir.eski_kural_gunleri, hiza_olcumu) yalnizca gun
    sayar, fiyat toplamaz."""
    desen = re.compile(r"""open\s*=\s*\(\s*["']open["']\s*,\s*["']first["']""")
    kaynaklar = list((config.KOK / "data").glob("*.py")) + list(DIZIN.glob("*.py"))
    kaynaklar += [p for p in (config.KOK / "events").rglob("*.py")] + [p for p in (config.KOK / "study").rglob("*.py")]
    bulunan = [p.name for p in kaynaklar if desen.search(p.read_text(encoding="utf-8"))]
    assert bulunan == ["klines.py"]


def test_eski_kural_karsilastirma_sayimi():
    sys.path.insert(0, str(DIZIN))
    spec = importlib.util.spec_from_file_location("_gs_cal", DIZIN / "calistir.py")
    c = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(c)
    z = _seri("2025-01-01 00:00", "2025-01-10 20:00")
    d0 = Donem(T("2025-01-01 08:00"), T("2025-01-04 08:00"), 16, 16)
    d1 = Donem(T("2025-01-06 08:00"), T("2025-01-09 08:00"), 16, 16)
    eski = c.eski_kural_gunleri(z)
    yeni = pd.DatetimeIndex(klines.gunluge_cevir(_mum(z), donemler=[d0, d1])["open_time"])
    sayim = c.cikan_gun_turleri(eski, yeni, [d0, d1])
    assert sayim == {"donem_basi": 1, "donem_sonu": 1, "ic_sinir": 2, "donem_disi": 2, "eklenen": 0}
