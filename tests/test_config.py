"""config.py sabitlerinin on-kayitla birebir ayni oldugunu dogrular.

Bu test bir "sessiz degisiklik" alarmidir: bir sabit on-kayit revizyonu
yazilmadan degistirilirse test kirilir (CLAUDE.md §3.4).
"""

from __future__ import annotations

import datetime as dt

import config


def test_donem_sinirlari():
    assert config.DONEM_BASI == dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc)
    assert config.DONEM_SONU.date() == dt.date(2026, 8, 31)


def test_kume_donemleri_ortusmez():
    assert config.KESIF_SONU < config.C2_BASI
    assert config.KESIF_BASI == config.DONEM_BASI
    assert config.C2_SONU == config.DONEM_SONU
    assert config.KESIF_SONU.date() == dt.date(2025, 8, 31)
    assert config.C2_BASI.date() == dt.date(2025, 9, 1)


def test_maliyet_muhafazakar():
    assert config.TEK_YON_MALIYET == 0.0010
    assert config.GIDIS_DONUS_MALIYET == 0.0020
    assert config.GIDIS_DONUS_MALIYET == 2 * config.TEK_YON_MALIYET


def test_istatistik_sabitleri():
    assert config.TOHUM == 20260911
    assert config.PERMUTASYON_TEKRAR == 10_000
    assert abs(config.ALFA_BONFERRONI - 0.0167) < 0.0001


def test_bolme_tuzu():
    assert config.BOLME_TUZU == "short-lab-v1:"


def test_kume_adlari():
    assert config.KUMELER == ("KESIF", "C1", "C2")
    assert config.ONAY_KUMELERI == ("C1", "C2")
