"""Rev.9 hazirligi, ikinci tur: tamlik kuralinin son hali (rev9_hazirlik.son_hal_tamlik_ayrintisi).
Aga cikmaz.

Beklenen odeme anlarinin capadan kayit dizisi boyunca uretildigini, giris anindan sonra
ve pencere sonuna kadar (dahil) her beklenen anda kayit arandigini, tolerans kuralini,
2026-06-24 turu bir boslugun yalnizca penceresi o ani iceren pozisyonlari eksik
yaptigini ve T >= K pozisyonlarda pencere sonunun B oldugunu sabitler.
"""

from __future__ import annotations

import importlib.util
import sys

import numpy as np
import pandas as pd
import pytest

import config

DIZIN = config.ANALIZ_DIZINI / "00_veri_denetimi"
sys.path.insert(0, str(DIZIN))
_spec = importlib.util.spec_from_file_location("_rev9_hazirlik_sh", DIZIN / "rev9_hazirlik.py")
r9 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r9)

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
BAS = T("2025-01-01 00:00")


def _seri(kayitlar):
    return pd.DataFrame({"odeme_zamani": pd.DatetimeIndex([T(z) for z, _ in kayitlar]),
                         "aralik_saat": [float(a) for _, a in kayitlar]})


def _sh(seri, giris, son, bas=BAS):
    return r9.son_hal_tamlik_ayrintisi(seri, [T(giris)], [T(son)], [bas]).iloc[0]


def _dort_saat(*eksik):
    z = pd.date_range("2025-01-01 00:00", "2025-01-02 12:00", freq="4h", tz="UTC")
    return _seri([(str(x.tz_localize(None)), 4) for x in z if str(x.tz_localize(None)) not in eksik])


def test_duzenli_seri_tam():
    assert _sh(_dort_saat(), "2025-01-01 04:00", "2025-01-02 04:00")["tam"]


def test_pencere_sonundaki_beklenen_odeme_eksikse_eksik():
    # Onceki onerinin "son esitlik" durumu: son kayit + aralik = pencere sonu, orada kayit yok.
    seri = _seri([("2025-01-01 00:00", 8), ("2025-01-01 08:00", 8), ("2025-01-01 16:00", 8)])
    assert not _sh(seri, "2025-01-01 04:00", "2025-01-02 00:00")["tam"]
    # Onceki oneri ayni pozisyonu tam sayiyordu.
    assert r9.oneri_tamlik_ayrintisi(seri, [T("2025-01-01 04:00")], [T("2025-01-02 00:00")], [BAS])["tam"].iloc[0]


def test_giris_anindaki_eksik_odeme_aranmaz():
    # 04:00 eksik; giris tam 04:00: beklenen an giris aniyla ayni, pencerede degil.
    seri = _dort_saat("2025-01-01 04:00:00")
    assert _sh(seri, "2025-01-01 04:00", "2025-01-01 16:00")["tam"]


def test_penceresi_eksik_ani_iceren_pozisyon_eksik():
    seri = _dort_saat("2025-01-01 04:00:00")
    assert not _sh(seri, "2025-01-01 00:00", "2025-01-01 16:00")["tam"]
    # Pencere eksik an bitince baslar: etkilenmez.
    assert _sh(seri, "2025-01-01 08:00", "2025-01-01 20:00")["tam"]
    # Pencere sonu tam eksik an (dahil): eksik.
    assert not _sh(seri, "2025-01-01 00:00", "2025-01-01 04:00")["tam"]


def test_ara_kayit_eksikse_eksik():
    seri = _dort_saat("2025-01-01 12:00:00")
    assert not _sh(seri, "2025-01-01 02:00", "2025-01-01 20:00")["tam"]


def test_kayitsiz_kisa_pencere_tam():
    seri = _seri([("2025-01-01 00:00", 8), ("2025-01-01 08:00", 8), ("2025-01-01 16:00", 8)])
    assert _sh(seri, "2025-01-01 08:00", "2025-01-01 12:00")["tam"]


def test_gec_baslayan_funding_eksik():
    seri = _seri([("2025-01-01 08:00", 8), ("2025-01-01 16:00", 8), ("2025-01-02 00:00", 8)])
    sonuc = _sh(seri, "2025-01-01 04:00", "2025-01-01 20:00")
    assert not sonuc["tam"] and not sonuc["onceki_var"]


def test_aralik_gecisinde_adim_buyuk_aralik():
    # 00:00 (8h) -> 07:00 (1h): beklenen an 00:00 + max(8, 1) = 08:00, orada kayit var.
    seri = _seri([("2025-01-01 00:00", 8), ("2025-01-01 07:00", 1), ("2025-01-01 08:00", 1),
                  ("2025-01-01 09:00", 1), ("2025-01-01 10:00", 1)])
    assert _sh(seri, "2025-01-01 00:00", "2025-01-01 10:00")["tam"]
    # 08:00 yoksa eksik.
    seri2 = seri.loc[seri["odeme_zamani"] != T("2025-01-01 08:00")].reset_index(drop=True)
    assert not _sh(seri2, "2025-01-01 00:00", "2025-01-01 10:00")["tam"]


def test_tolerans_kurali():
    ok = _seri([("2025-01-01 00:00", 4), ("2025-01-01 04:00:30", 4), ("2025-01-01 08:00", 4)])
    assert _sh(ok, "2025-01-01 02:00", "2025-01-01 08:00")["tam"]
    kotu = _seri([("2025-01-01 00:00", 4), ("2025-01-01 04:01", 4), ("2025-01-01 08:00", 4)])
    assert not _sh(kotu, "2025-01-01 02:00", "2025-01-01 08:00")["tam"]


def test_capa_girisle_ayni_an_capa_olur():
    seri = _seri([("2025-01-01 04:00", 4), ("2025-01-01 08:00", 4), ("2025-01-01 12:00", 4)])
    assert _sh(seri, "2025-01-01 04:00", "2025-01-01 12:00")["tam"]


def test_capa_donem_basindan_once_olamaz():
    # Giristen onceki son kayit donem basindan once: capa yok.
    seri = _seri([("2024-12-31 20:00", 4), ("2025-01-01 08:00", 4), ("2025-01-01 12:00", 4)])
    assert not _sh(seri, "2025-01-01 04:00", "2025-01-01 12:00")["onceki_var"]
    # Donem basiyla 30 sn fark ayni an: capa olur.
    assert _sh(seri, "2024-12-31 20:00", "2025-01-01 00:00", bas=T("2024-12-31 20:00:30"))["onceki_var"]


def test_kopuk_giris_oncesi_yalnizca_bilgi():
    # Capa girisin 20 saat oncesi (8h); beklenen an girisin 12 saat oncesi ve kayitsiz.
    seri = _seri([("2025-01-01 00:00", 8), ("2025-01-01 22:00", 8), ("2025-01-02 06:00", 8)])
    s = _sh(seri, "2025-01-01 20:00", "2025-01-02 06:00")
    assert s["kopuk_giris_oncesi"]


def test_son_kayittan_sonra_sonraki_kayit_okunmaz():
    # Son kayit 08:00 (4h), sonraki kayit pencereden sonra 20:00 (8h). Beklenen an 12:00 = pencere
    # sonu, kayit yok: eksik. Sonraki kaydin 8 saatlik araligi okunsaydi 16:00 olurdu ve tam derdi.
    seri = _seri([("2025-01-01 04:00", 4), ("2025-01-01 08:00", 4), ("2025-01-01 20:00", 8)])
    assert not _sh(seri, "2025-01-01 04:00", "2025-01-01 12:00")["tam"]


def test_vektorel_tekil_ile_ayni():
    seri = _dort_saat("2025-01-01 12:00:00")
    girisler = [T("2025-01-01 00:00"), T("2025-01-01 12:00"), T("2025-01-01 16:00"), T("2025-01-01 04:00")]
    sonlar = [T("2025-01-01 08:00"), T("2025-01-02 00:00"), T("2025-01-02 04:00"), T("2025-01-01 12:00")]
    toplu = r9.son_hal_tamlik_ayrintisi(seri, girisler, sonlar, [BAS] * 4)
    for i in range(4):
        tek = r9.son_hal_tamlik_ayrintisi(seri, [girisler[i]], [sonlar[i]], [BAS]).iloc[0]
        assert toplu.iloc[i].equals(tek)
    assert list(toplu["tam"]) == [True, True, True, False]  # 12:00 girisi: eksik an giris aniyla ayni


def test_t_k_pencere_sonu_b():
    K = T("2025-01-10 12:00")
    B = K - pd.Timedelta(hours=4)
    assert r9.son_hal_pencere_sonu(K, "olagan", B, K) == B
    assert r9.son_hal_pencere_sonu(T("2025-01-09 12:00"), "olagan", B, K) == T("2025-01-09 12:00")
    assert r9.son_hal_pencere_sonu(B, "donem_sonu", B, K) == B


def test_uzunluk_uyusmazligi_hata():
    with pytest.raises(ValueError):
        r9.son_hal_tamlik_ayrintisi(_dort_saat(), [T("2025-01-01 04:00")], [], [BAS])


def test_bir_saatten_dort_saate_geciste_beklenen_an_kayitlarin_arasina_duser():
    # 19:00 (1h) -> 20:00 (4h): adim max(1, 4) = 4, beklenen an 23:00; odemeler 20:00 ve 00:00'da.
    # Tanim geregi eksik; onceki oneri (bosluk <= iki araligin buyugu) tam der. Tur ayri sayilir.
    seri = _seri([("2025-01-01 17:00", 1), ("2025-01-01 18:00", 1), ("2025-01-01 19:00", 1),
                  ("2025-01-01 20:00", 4), ("2025-01-02 00:00", 4), ("2025-01-02 04:00", 4)])
    sh = _sh(seri, "2025-01-01 18:00", "2025-01-02 04:00")
    assert not sh["tam"]
    oneri = r9.oneri_tamlik_ayrintisi(seri, [T("2025-01-01 18:00")], [T("2025-01-02 04:00")], [BAS]).iloc[0]
    assert oneri["tam"]
    rev8 = r9.funding_modulu.funding_tamlik_ayrintisi(seri, [T("2025-01-01 18:00")], [T("2025-01-02 04:00")]).iloc[0]
    assert r9.son_hal_fark_turu(rev8, sh, False, bool(oneri["tam"])) == "beklenen_an_eksik_gecis"
