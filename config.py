"""short-lab sabitleri.

Buradaki her deger PREREGISTRATION.md'den gelir ve yanina geldigi bolum yazilir.
Bu dosyadaki bir sabiti degistirmek on-kaydi degistirmek demektir; once revizyon
yazilmadan burasi degistirilemez (CLAUDE.md §3.4).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

# --- Dizinler (CLAUDE.md §7) -------------------------------------------------

KOK = Path(__file__).resolve().parent
VERI_DIZINI = KOK / "data"
ONBELLEK_DIZINI = KOK / "cache"
ANALIZ_DIZINI = KOK / "analysis"
SPLIT_CSV = VERI_DIZINI / "split.csv"
ONAY_KAYDI = KOK / "ONAY_KAYDI.md"

# --- Piyasa ve evren (on-kayit §2) -------------------------------------------

# Binance USDⓈ-M, USDT marjinli, PERPETUAL sozlesmeler.
TEMINAT_SONEKI = "USDT"

# Toplam donem: 2020-01-01 00:00 UTC -> 2026-08-31 23:59 UTC (on-kayit §2)
DONEM_BASI = dt.datetime(2020, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
DONEM_SONU = dt.datetime(2026, 8, 31, 23, 59, 59, tzinfo=dt.timezone.utc)

# Bar tipleri: H1, H2 -> 4h · H3 -> 1d (on-kayit §2)
BAR_4H = "4h"
BAR_1D = "1d"

# Haric tutulan semboller (on-kayit §2: stablecoin tabanli ciftler ve endeks
# sozlesmeleri). Kesin liste on-kayit revizyonuyla sabitlenir; revizyondan once
# bos birakilamaz diye varsayilan olarak on-kayitta acikca sayilanlar durur.
HARIC_SEMBOLLER: frozenset[str] = frozenset(
    {
        "USDCUSDT",  # stablecoin tabanli cift (on-kayit §2)
        "BTCDOMUSDT",  # endeks sozlesmesi (on-kayit §2)
        "DEFIUSDT",  # endeks sozlesmesi (on-kayit §2)
    }
)

# --- Uygunluk (on-kayit §2) --------------------------------------------------

# Listeleme yasi >= 30 gun
ASGARI_LISTELEME_YASI_GUN = 30

# Medyan gunluk hacim penceresi: son 30 gun
HACIM_PENCERESI_GUN = 30

# H1, H2: medyan gunluk hacim >= 10 milyon USDT
ASGARI_HACIM_4H = 10_000_000.0

# H3: medyan gunluk hacim >= 2 milyon USDT
ASGARI_HACIM_1D = 2_000_000.0

# --- Veri bolmesi (on-kayit §3) ----------------------------------------------

# SHA256("short-lab-v1:" + SEMBOL); ozetin tamsayi degeri cift ise A, tek ise B.
BOLME_TUZU = "short-lab-v1:"

KESIF_BASI = dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc)
KESIF_SONU = dt.datetime(2025, 8, 31, 23, 59, 59, tzinfo=dt.timezone.utc)
C2_BASI = dt.datetime(2025, 9, 1, tzinfo=dt.timezone.utc)
C2_SONU = dt.datetime(2026, 8, 31, 23, 59, 59, tzinfo=dt.timezone.utc)

# KESIF: A grubu, kesif donemi · C1: B grubu, kesif donemi · C2: A+B, C2 donemi
KUMELER = ("KESIF", "C1", "C2")
ONAY_KUMELERI = ("C1", "C2")

# --- Funding (on-kayit §2) ---------------------------------------------------

# Karsilastirma icin oranlar 8 saate normallestirilir; getiri hesabinda gercek
# odemeler kullanilir.
NORMAL_FUNDING_ARALIGI_SAAT = 8

# --- Maliyet (on-kayit §4, CLAUDE.md §3.7) -----------------------------------

TEK_YON_MALIYET = 0.0010  # %0.10 ucret + kayma
GIDIS_DONUS_MALIYET = 0.0020  # %0.20

# --- Istatistik (on-kayit §7) ------------------------------------------------

TOHUM = 20260911
PERMUTASYON_TEKRAR = 10_000
ALFA_BONFERRONI = 0.05 / 3  # uc hipotez icin Bonferroni = 0.0167
