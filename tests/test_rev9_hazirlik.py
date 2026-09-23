"""Rev.9 hazirlik olcumu (analysis/00_veri_denetimi/rev9_hazirlik.py). Aga cikmaz.

Onerilen funding tamlik kuralinin olcum fonksiyonunu elle kurulmus serilerde sabitler:
capa (giristen onceki son donem ici kayit), zincir, son kosul ve iki alternatif okuma;
fark turlerinin siniflandirmasi; betigin oran sutununa bakmadigi.
"""

from __future__ import annotations

import importlib.util
import inspect
import sys

import numpy as np
import pandas as pd
import pytest

import config
from data import funding as funding_modulu

DIZIN = config.ANALIZ_DIZINI / "00_veri_denetimi"
sys.path.insert(0, str(DIZIN))
_spec = importlib.util.spec_from_file_location("_rev9_hazirlik", DIZIN / "rev9_hazirlik.py")
r9 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r9)

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
BAS = T("2025-01-01 00:00")


def _seri(kayitlar):
    """[(zaman, aralik_saat)] -> funding cercevesi (oran sutunu yok)."""
    return pd.DataFrame({"odeme_zamani": pd.DatetimeIndex([T(z) for z, _ in kayitlar]),
                         "aralik_saat": [float(a) for _, a in kayitlar]})


def _oneri(seri, giris, son, bas=BAS, **kw):
    return r9.oneri_tamlik_ayrintisi(seri, [T(giris)], [T(son)], [bas], **kw).iloc[0]


def _rev8(seri, giris, son):
    # Rev.9 veri katmanindaki kurali degistirdi; Rev.8 tanimi donmus kopyadan (rev8_tamlik).
    return r9.rev8_tamlik_ayrintisi(seri, [T(giris)], [T(son)]).iloc[0]


SEKIZ = _seri([("2025-01-01 00:00", 8), ("2025-01-01 08:00", 8), ("2025-01-01 16:00", 8),
               ("2025-01-02 00:00", 8), ("2025-01-02 08:00", 8)])


def test_duzenli_seri_iki_kuralda_tam():
    assert _oneri(SEKIZ, "2025-01-01 04:00", "2025-01-02 04:00")["tam"]
    assert _rev8(SEKIZ, "2025-01-01 04:00", "2025-01-02 04:00")["tam"]


def test_kayitsiz_kisa_pencere_oneride_tam_rev8de_degil():
    # (08:00, 12:00] araliginda kayit yok; capa 08:00 + 8h = 16:00 >= 12:00.
    o, r = _oneri(SEKIZ, "2025-01-01 08:00", "2025-01-01 12:00"), _rev8(SEKIZ, "2025-01-01 08:00", "2025-01-01 12:00")
    assert o["tam"] and not r["tam"] and not r["kayit_var"]
    assert r9.fark_turu(r, o) == "kayitsiz_kisa_pencere"


def test_gec_baslayan_funding_oneride_eksik():
    # Donem 00:00'da basliyor, ilk kayit 08:00; giris 04:00. Rev.8: ilk odeme 08:00 <= 04:00 + 8h, tam.
    seri = _seri([("2025-01-01 08:00", 8), ("2025-01-01 16:00", 8), ("2025-01-02 00:00", 8)])
    o, r = _oneri(seri, "2025-01-01 04:00", "2025-01-01 20:00"), _rev8(seri, "2025-01-01 04:00", "2025-01-01 20:00")
    assert r["tam"] and not o["tam"] and not o["onceki_var"]
    assert r9.fark_turu(r, o) == "gec_baslayan_funding"


def test_capa_donem_basindan_onceyse_yok_sayilir():
    seri = _seri([("2024-12-31 23:00", 8), ("2025-01-01 07:00", 8), ("2025-01-01 15:00", 8)])
    assert not _oneri(seri, "2025-01-01 04:00", "2025-01-01 12:00")["onceki_var"]
    assert _oneri(seri, "2025-01-01 04:00", "2025-01-01 12:00", bas=T("2024-12-31 00:00"))["tam"]


def test_giris_oncesi_bosluk_oneride_eksik_rev8de_tam():
    # 00:00'dan sonra 16:00'ya kadar kayit yok (08:00 eksik); giris 12:00. Rev.8 yalnizca
    # giris -> ilk odemeye bakar: 16:00 <= 12:00 + 8h, tam. Oneri capa 00:00 -> 16:00 > 8h.
    seri = _seri([("2025-01-01 00:00", 8), ("2025-01-01 16:00", 8), ("2025-01-02 00:00", 8)])
    o, r = _oneri(seri, "2025-01-01 12:00", "2025-01-01 20:00"), _rev8(seri, "2025-01-01 12:00", "2025-01-01 20:00")
    assert r["tam"] and not o["tam"] and o["onceki_var"] and not o["zincir_tam"]
    assert r9.fark_turu(r, o) == "diger_giris_oncesi_bosluk"


def test_son_esitlik_iki_okumada_ayrilir():
    # Son kayit 16:00, aralik 8 -> 24:00 = pencere sonu, orada kayit yok.
    seri = _seri([("2025-01-01 00:00", 8), ("2025-01-01 08:00", 8), ("2025-01-01 16:00", 8)])
    o = _oneri(seri, "2025-01-01 04:00", "2025-01-02 00:00")
    r = _rev8(seri, "2025-01-01 04:00", "2025-01-02 00:00")
    assert o["tam"] and o["son_esit"]
    assert not r["tam"] and not r["son_tam"]
    assert not _oneri(seri, "2025-01-01 04:00", "2025-01-02 00:00", son_kurali="rev8")["tam"]
    assert r9.fark_turu(r, o) == "diger_son_esitlik"


def test_son_kayit_pencere_sonundan_once_dolarsa_eksik():
    seri = _seri([("2025-01-01 00:00", 4), ("2025-01-01 04:00", 4)])
    assert not _oneri(seri, "2025-01-01 02:00", "2025-01-01 12:00")["tam"]


def test_ic_bosluk_iki_kuralda_eksik():
    seri = _seri([("2025-01-01 00:00", 4), ("2025-01-01 04:00", 4), ("2025-01-01 12:00", 4), ("2025-01-01 16:00", 4)])
    assert not _oneri(seri, "2025-01-01 02:00", "2025-01-01 16:00")["tam"]
    assert not _rev8(seri, "2025-01-01 02:00", "2025-01-01 16:00")["tam"]


def test_aralik_gecisi_capa_ile_tam_rev8_baslangic_bozuk():
    # Capa 00:00 (8h), ilk odeme 07:00 (1h): 07:00 <= 00:00 + max(8, 1). Rev.8: 07:00 > 01:00 + ... bozuk.
    seri = _seri([("2025-01-01 00:00", 8), ("2025-01-01 07:00", 1), ("2025-01-01 08:00", 1),
                  ("2025-01-01 09:00", 1)])
    o, r = _oneri(seri, "2025-01-01 00:00", "2025-01-01 09:00"), _rev8(seri, "2025-01-01 00:00", "2025-01-01 09:00")
    assert o["tam"] and not r["baslangic_tam"]
    assert r9.fark_turu(r, o) == "diger_baslangic_araligi"


def test_capa_giris_aninda_kati_okumada_bir_onceki_kayit():
    # Giris aninda kayit var ve donemin ilk kaydi; kati okumada capa yok.
    seri = _seri([("2025-01-01 04:00", 4), ("2025-01-01 08:00", 4), ("2025-01-01 12:00", 4)])
    assert _oneri(seri, "2025-01-01 04:00", "2025-01-01 12:00")["tam"]
    assert not _oneri(seri, "2025-01-01 04:00", "2025-01-01 12:00", kati_onceki=True)["tam"]


def test_tam_bir_dakika_ayni_an_degil():
    # Capa girisle tam 1 dk sonra: ayni an degil, capa olamaz.
    seri = _seri([("2025-01-01 04:01", 4), ("2025-01-01 08:01", 4)])
    assert not _oneri(seri, "2025-01-01 04:00", "2025-01-01 08:00")["onceki_var"]
    seri = _seri([("2025-01-01 03:59:30", 4), ("2025-01-01 08:00", 4)])
    assert _oneri(seri, "2025-01-01 04:00", "2025-01-01 08:00")["onceki_var"]


def test_gecersiz_aralik_tam_degil():
    seri = _seri([("2025-01-01 00:00", 8), ("2025-01-01 08:00", np.nan), ("2025-01-01 16:00", 8)])
    o = _oneri(seri, "2025-01-01 04:00", "2025-01-01 20:00")
    assert not o["tam"] and not o["aralik_gecerli"]


def test_vektorel_tekil_ile_ayni():
    girisler = [T("2025-01-01 04:00"), T("2025-01-01 08:00"), T("2025-01-01 12:00")]
    sonlar = [T("2025-01-02 04:00"), T("2025-01-01 12:00"), T("2025-01-02 08:00")]
    toplu = r9.oneri_tamlik_ayrintisi(SEKIZ, girisler, sonlar, [BAS] * 3)
    for i in range(3):
        tek = r9.oneri_tamlik_ayrintisi(SEKIZ, [girisler[i]], [sonlar[i]], [BAS]).iloc[0]
        assert toplu.iloc[i].equals(tek)


def test_oran_sutunu_okunmaz():
    kaynak = inspect.getsource(r9)
    assert '"oran"' not in kaynak and "'oran'" not in kaynak and "oran_8h" not in kaynak
    # Oran sutunu olmadan calisir (yukaridaki butun seriler zaten oransizdir).
    assert "oran" not in SEKIZ.columns


def test_uzunluk_uyusmazligi_hata():
    with pytest.raises(ValueError):
        r9.oneri_tamlik_ayrintisi(SEKIZ, [T("2025-01-01 04:00")], [], [BAS])
