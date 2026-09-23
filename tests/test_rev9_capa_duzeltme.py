"""Rev.9 hazirligi, besinci tur: capa duzeltmesi (rev9_hazirlik.capa_duzeltme_tamlik_ayrintisi).
Aga cikmaz.

Sabitlenen: capa ile sonraki kayit arasindaki boslugun GIRISTEN olculmesi, bu duzeltmenin
yalnizca ilk cifti (capa -> sonraki kayit) etkilemesi, kuralin dorduncu tura gore yalnizca
gevsemesi (asla siki olmamasi), son kosulun ve capa kosulunun degismemesi, ve son ucundaki
karsi ornek adayinin (`son_ihlali_giris_oncesi`) isaretlenmesi.
"""

from __future__ import annotations

import importlib.util
import itertools
import sys

import numpy as np
import pandas as pd
import pytest

import config

DIZIN = config.ANALIZ_DIZINI / "00_veri_denetimi"
sys.path.insert(0, str(DIZIN))
_spec = importlib.util.spec_from_file_location("_rev9_hazirlik_cd", DIZIN / "rev9_hazirlik.py")
r9 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r9)

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
BAS = T("2025-01-01 00:00")


def _seri(kayitlar):
    return pd.DataFrame({"odeme_zamani": pd.DatetimeIndex([T(z) for z, _ in kayitlar]),
                         "aralik_saat": [float(a) for _, a in kayitlar]})


def _cd(seri, giris, son, bas=BAS):
    return r9.capa_duzeltme_tamlik_ayrintisi(seri, [T(giris)], [T(son)], [bas]).iloc[0]


def _ty(seri, giris, son, bas=BAS):
    return r9.tahmin_yok_tamlik_ayrintisi(seri, [T(giris)], [T(son)], [bas]).iloc[0]


def _dort_saat(*eksik):
    z = pd.date_range("2025-01-01 00:00", "2025-01-03 00:00", freq="4h", tz="UTC")
    return _seri([(str(x.tz_localize(None)), 4) for x in z if str(x.tz_localize(None)) not in eksik])


# --- Duzeltmenin kendisi -------------------------------------------------------------


def test_giris_anindaki_eksik_odeme_artik_dusurmuyor():
    # 2026-06-24 deseni: capa 00:00 (aralik 4), eksik odeme 04:00, giris tam 04:00.
    seri = _seri([("2025-01-01 00:00", 4), ("2025-01-01 08:00", 4), ("2025-01-01 12:00", 4)])
    assert not _ty(seri, "2025-01-01 04:00", "2025-01-01 12:00")["tam"]  # dorduncu tur: eksik
    s = _cd(seri, "2025-01-01 04:00", "2025-01-01 12:00")
    assert s["tam"] and s["zincir_tam"] and s["ilk_cift_affi"]


def test_giris_oncesindeki_eksik_odeme_de_dusurmuyor():
    # Capa 00:00, eksik odeme 04:00, giris 05:00 (eksik odeme giristen once).
    seri = _seri([("2025-01-01 00:00", 4), ("2025-01-01 08:00", 4), ("2025-01-01 12:00", 4)])
    assert _cd(seri, "2025-01-01 05:00", "2025-01-01 12:00")["tam"]


def test_giristen_sonra_dusen_eksik_odeme_hala_dusuruyor():
    # Capa 00:00, giris 00:00 (kayitla ayni an): bosluk giristen olculse de 8 > 4.
    seri = _seri([("2025-01-01 00:00", 4), ("2025-01-01 08:00", 4)])
    s = _cd(seri, "2025-01-01 00:00", "2025-01-01 08:00")
    assert not s["tam"] and not s["zincir_tam"] and not s["ilk_cift_affi"]


def test_ilk_ciftte_giristen_sonra_hala_eksik_varsa_dusuruyor():
    # Capa 00:00 (4), sonraki kayit 16:00: giris 04:00 olsa bile 16:00 > 04:00 + 4.
    seri = _seri([("2025-01-01 00:00", 4), ("2025-01-01 16:00", 4), ("2025-01-01 20:00", 4)])
    s = _cd(seri, "2025-01-01 04:00", "2025-01-01 20:00")
    assert not s["tam"] and not s["ilk_cift_affi"]


def test_duzeltme_yalnizca_ilk_cifti_etkiliyor():
    # Ikinci cift bozuk (12:00 eksik): duzeltme onu affetmez.
    seri = _dort_saat("2025-01-01 12:00:00")
    assert not _cd(seri, "2025-01-01 04:00", "2025-01-01 20:00")["tam"]
    # Ayni seride ilk cift bozuksa (04:00 eksik, giris 04:00) ve ikinci cift saglam: tam.
    seri2 = _seri([("2025-01-01 00:00", 4), ("2025-01-01 08:00", 4), ("2025-01-01 12:00", 4),
                   ("2025-01-01 16:00", 4)])
    assert _cd(seri2, "2025-01-01 04:00", "2025-01-01 16:00")["tam"]


def test_ilk_cift_affi_yalnizca_gercekten_affedilende():
    seri = _dort_saat()
    s = _cd(seri, "2025-01-01 04:00", "2025-01-01 16:00")
    assert s["tam"] and not s["ilk_cift_affi"]  # bozuk cift yok, af yok


def test_tolerans_giris_tabaninda_da_gecerli():
    # Sonraki kayit giris + aralik + 30 saniye: tolerans icinde, tam.
    seri = _seri([("2025-01-01 00:00", 4), ("2025-01-01 08:00:30", 4), ("2025-01-01 12:00", 4)])
    assert _cd(seri, "2025-01-01 04:00", "2025-01-01 12:00")["tam"]
    # 2 dakika sonra: tolerans disi, eksik.
    seri2 = _seri([("2025-01-01 00:00", 4), ("2025-01-01 08:02", 4), ("2025-01-01 12:02", 4)])
    assert not _cd(seri2, "2025-01-01 04:00", "2025-01-01 12:02")["tam"]


def test_ilk_ciftte_adim_iki_araligin_buyugu():
    # Capa araligi 1, sonraki kaydin araligi 8: adim 8, giris 04:00 -> 12:00 sinir.
    seri = _seri([("2025-01-01 00:00", 1), ("2025-01-01 12:00", 8), ("2025-01-01 20:00", 8)])
    assert _cd(seri, "2025-01-01 04:00", "2025-01-01 20:00")["tam"]
    seri2 = _seri([("2025-01-01 00:00", 1), ("2025-01-01 13:00", 8), ("2025-01-01 21:00", 8)])
    assert not _cd(seri2, "2025-01-01 04:00", "2025-01-01 21:00")["tam"]


# --- Degismeyen kosullar -------------------------------------------------------------


def test_capa_yoksa_eksik():
    seri = _seri([("2025-01-01 08:00", 4), ("2025-01-01 12:00", 4)])
    s = _cd(seri, "2025-01-01 04:00", "2025-01-01 12:00")
    assert not s["tam"] and not s["capa_var"]


def test_capa_donem_basindan_once_olamaz():
    seri = _seri([("2024-12-31 20:00", 4), ("2025-01-01 04:00", 4)])
    s = _cd(seri, "2025-01-01 00:00", "2025-01-01 04:00", bas=BAS)
    assert not s["capa_var"] and not s["tam"]


def test_son_kosulu_degismedi_esitlikte_affediyor():
    seri = _seri([("2025-01-01 00:00", 8), ("2025-01-01 08:00", 8), ("2025-01-01 16:00", 8)])
    s = _cd(seri, "2025-01-01 04:00", "2025-01-02 00:00")
    assert s["tam"] and s["son_esitlik_affi"] and not s["kuyruk_dogrulanmamis"]


def test_son_kayit_araligi_pencere_sonundan_once_dolarsa_eksik():
    seri = _seri([("2025-01-01 00:00", 4), ("2025-01-01 04:00", 4)])
    s = _cd(seri, "2025-01-01 04:00", "2025-01-01 12:00")
    assert not s["tam"] and not s["son_tam"]


def test_kuyruk_sutunlari_dorduncu_turla_ayni_anlamda():
    seri = _seri([("2025-01-01 00:00", 8), ("2025-01-01 08:00", 8), ("2025-01-01 16:00", 8)])
    s = _cd(seri, "2025-01-01 04:00", "2025-01-01 12:00")
    t = _ty(seri, "2025-01-01 04:00", "2025-01-01 12:00")
    assert s["tam"] and s["kuyruk_dogrulanmamis"] and s["kuyruk_kismi"] and not s["kuyruk_sifir"]
    assert bool(t["kuyruk_dogrulanmamis"]) == bool(s["kuyruk_dogrulanmamis"])


def test_kuyruk_sifir_son_kayit_pencere_sonunda():
    seri = _seri([("2025-01-01 00:00", 8), ("2025-01-01 08:00", 8)])
    s = _cd(seri, "2025-01-01 04:00", "2025-01-01 08:00")
    assert s["tam"] and s["kuyruk_sifir"] and not s["kuyruk_kismi"]


def test_aralik_gecersizse_eksik():
    seri = _seri([("2025-01-01 00:00", 4), ("2025-01-01 04:00", 0)])
    s = _cd(seri, "2025-01-01 04:00", "2025-01-01 08:00")
    assert not s["aralik_gecerli"] and not s["tam"]


# --- Son ucundaki karsi ornek adayi --------------------------------------------------


def test_son_ihlali_giris_oncesi_isaretleniyor():
    # Capa 00:00 (4), pencerede hic kayit yok, pencere sonu 06:00: beklenen an 04:00 = giris.
    seri = _seri([("2025-01-01 00:00", 4), ("2025-01-02 00:00", 4)])
    s = _cd(seri, "2025-01-01 04:00", "2025-01-01 06:00")
    assert not s["tam"] and s["son_ihlali_giris_oncesi"]


def test_son_ihlali_giris_sonrasinda_isaretlenmiyor():
    seri = _seri([("2025-01-01 00:00", 4), ("2025-01-01 04:00", 4), ("2025-01-02 00:00", 4)])
    s = _cd(seri, "2025-01-01 04:00", "2025-01-01 12:00")
    assert not s["tam"] and not s["son_ihlali_giris_oncesi"]  # beklenen an 08:00 > giris


# --- Dorduncu turla iliski ------------------------------------------------------------


def _izgara_serileri():
    """Elle kurulmus kucuk seriler: 4 ve 8 saatlik ritim, eksikler ve aralik degisimi."""
    yield _dort_saat()
    yield _dort_saat("2025-01-01 04:00:00")
    yield _dort_saat("2025-01-01 08:00:00")
    yield _dort_saat("2025-01-01 04:00:00", "2025-01-01 16:00:00")
    yield _seri([("2025-01-01 00:00", 8), ("2025-01-01 08:00", 8), ("2025-01-01 16:00", 8),
                 ("2025-01-02 00:00", 8)])
    yield _seri([("2025-01-01 00:00", 1), ("2025-01-01 01:00", 1), ("2025-01-01 05:00", 4),
                 ("2025-01-01 09:00", 4)])
    yield _seri([("2025-01-01 00:00", 4)])


def test_duzeltme_asla_sikilastirmaz():
    """Bu tanima gore eksik olan her pozisyon dorduncu turda da eksiktir (yalnizca gevsetme)."""
    girisler = ["2025-01-01 00:00", "2025-01-01 04:00", "2025-01-01 05:00", "2025-01-01 09:00"]
    sonlar = ["2025-01-01 12:00", "2025-01-01 16:00", "2025-01-02 00:00"]
    bakilan = 0
    for seri, giris, son in itertools.product(_izgara_serileri(), girisler, sonlar):
        if T(giris) >= T(son):
            continue
        t, c = _ty(seri, giris, son), _cd(seri, giris, son)
        bakilan += 1
        assert not (t["tam"] and not c["tam"]), (giris, son, seri.to_dict("list"))
        if bool(t["tam"]) != bool(c["tam"]):
            assert r9.capa_duzeltme_fark_turu(t, c) == "capa_boslugu_giris_oncesi"
    assert bakilan >= 60


def test_fark_turu_ayni_hukumde_none():
    seri = _dort_saat()
    t, c = _ty(seri, "2025-01-01 04:00", "2025-01-01 16:00"), _cd(seri, "2025-01-01 04:00", "2025-01-01 16:00")
    assert r9.capa_duzeltme_fark_turu(t, c) is None


# --- Bicim ve deger yolu -------------------------------------------------------------


def test_bos_seri_ve_bos_pozisyon():
    bos = r9._bos_seri()
    assert not r9.capa_duzeltme_tamlik_ayrintisi(bos, [T("2025-01-01 04:00")], [T("2025-01-01 12:00")],
                                                 [BAS])["tam"].iloc[0]
    assert len(r9.capa_duzeltme_tamlik_ayrintisi(_dort_saat(), [], [], [])) == 0


def test_uzunluk_uyusmazligi_hata():
    with pytest.raises(ValueError):
        r9.capa_duzeltme_tamlik_ayrintisi(_dort_saat(), [T("2025-01-01 04:00")], [], [BAS])


def test_oran_sutunu_okunmuyor():
    seri = _dort_saat()
    kirli = seri.copy()
    kirli["funding_orani"] = np.linspace(-1.0, 1.0, len(kirli))
    a = r9.capa_duzeltme_tamlik_ayrintisi(seri, [T("2025-01-01 04:00")], [T("2025-01-01 16:00")], [BAS])
    b = r9.capa_duzeltme_tamlik_ayrintisi(kirli, [T("2025-01-01 04:00")], [T("2025-01-01 16:00")], [BAS])
    pd.testing.assert_frame_equal(a, b)


def test_vektorel_ve_tek_tek_ayni():
    seri = _seri([("2025-01-01 00:00", 4), ("2025-01-01 08:00", 4), ("2025-01-01 12:00", 4),
                  ("2025-01-01 16:00", 4)])
    girisler = [T("2025-01-01 00:00"), T("2025-01-01 04:00"), T("2025-01-01 08:00")]
    sonlar = [T("2025-01-01 12:00"), T("2025-01-01 16:00"), T("2025-01-01 16:00")]
    toplu = r9.capa_duzeltme_tamlik_ayrintisi(seri, girisler, sonlar, [BAS] * 3)
    for i, (g, s) in enumerate(zip(girisler, sonlar)):
        tek = r9.capa_duzeltme_tamlik_ayrintisi(seri, [g], [s], [BAS]).iloc[0]
        for sutun in toplu.columns:
            assert bool(toplu.at[i, sutun]) == bool(tek[sutun]), (i, sutun)
