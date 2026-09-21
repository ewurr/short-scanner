"""short-lab sabitleri.

Buradaki degerler PREREGISTRATION.md'den gelir ve yanina geldigi bolum yazilir.
Bu dosyadaki bir on-kayit sabitini degistirmek on-kaydi degistirmek demektir; once
revizyon yazilmadan burasi degistirilemez (CLAUDE.md §3.4).

Istisnalar "ON-KAYIT DEGILDIR" diye isaretlidir: dizin ve dosya yollari (ornegin
`EXCHANGE_INFO_ANLIK`) ve F1 denetim teshis esikleri (`DENETIM_*`). Bunlar hicbir
olay, uygunluk ya da getiri hesabinin esigi degildir.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

# --- Dizinler (CLAUDE.md §7) -------------------------------------------------
#
# ON-KAYIT DEGILDIR: dosya ve dizin yollari.

KOK = Path(__file__).resolve().parent
VERI_DIZINI = KOK / "data"
ONBELLEK_DIZINI = KOK / "cache"
ANALIZ_DIZINI = KOK / "analysis"
SPLIT_CSV = VERI_DIZINI / "split.csv"
# Listeleme donemleri; split.csv gibi sabit (on-kayit §2 rev.4, rev.7).
UNIVERSE_CSV = VERI_DIZINI / "universe.csv"
ONAY_KAYDI = KOK / "ONAY_KAYDI.md"
# exchangeInfo anlik goruntusu. ON-KAYIT DEGILDIR (on-kayitta tanimli degil;
# 2026-09-18'de F1 denetimi icin alindi). Delist siniflandirmasi, deliveryDate
# denetimi ve evren kurulumundaki sozlesme/dayanak tipi canli uc noktadan degil bu
# dosyadan okunur.
EXCHANGE_INFO_ANLIK = VERI_DIZINI / "exchange_info_anlik.json"

# --- Piyasa ve evren (on-kayit §2) -------------------------------------------

# Binance USDⓈ-M, USDT marjinli, PERPETUAL sozlesmeler.
TEMINAT_SONEKI = "USDT"

# Toplam donem: 2020-01-01 00:00 UTC -> 2026-08-31 23:59 UTC (on-kayit §2)
DONEM_BASI = dt.datetime(2020, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
DONEM_SONU = dt.datetime(2026, 8, 31, 23, 59, 59, tzinfo=dt.timezone.utc)

# Bar tipleri: H1, H2 -> 4h · H3 -> 1d (on-kayit §2)
BAR_4H = "4h"
BAR_1D = "1d"

# Kapsam netlestirmesi (on-kayit §2, revizyon 2): evren yalnizca
# contractType = PERPETUAL olan USDT marjinli sozlesmelerden olusur.
# TRADIFI_PERPETUAL (hisse senedi, emtia, premarket) kapsam disidir.
PERPETUAL_TIPI = "PERPETUAL"
TRADIFI_TIPI = "TRADIFI_PERPETUAL"
ENDEKS_TIPI = "INDEX"

# Haric tutma listesi (on-kayit §2, revizyon 2). Kesin ve aciktir; duzenli ifade
# kullanilmaz, cunku BUSDT (BU) ve TUSDT (Threshold) stablecoin degildir.
HARIC_ENDEKSLER: frozenset[str] = frozenset(
    {"BTCDOMUSDT", "DEFIUSDT", "ALLUSDT", "BLUEBIRDUSDT", "DOTECOUSDT", "FOOTBALLUSDT"}
)
HARIC_STABLECOIN: frozenset[str] = frozenset({"USDCUSDT"})
HARIC_SEMBOLLER: frozenset[str] = HARIC_ENDEKSLER | HARIC_STABLECOIN

# On-kayit §2 revizyon 2 stablecoin tanimi "bagini koruyan token" oldugu icin
# asagidakiler evrende KALIR. Liste yalnizca belge amaclidir.
EVRENDE_KALAN_STABLECOIN_BENZERI: frozenset[str] = frozenset(
    {"FRAXUSDT", "USTCUSDT", "STBLUSDT", "STABLEUSDT"}
)

# Kabul edilen yeniden adlandirma zincirleri (on-kayit §3, revizyon 2).
# {yeni_sembol: eski_sembol}; varlik anahtari zincirin en eski uyesidir.
# KEEPUSDT/NUUSDT -> TUSDT birlesme oldugu icin zincir SAYILMAZ.
YENIDEN_ADLANDIRMA: dict[str, str] = {
    "AAVEUSDT": "LENDUSDT",
    "1000BTTCUSDT": "BTTUSDT",
    "RENDERUSDT": "RNDRUSDT",
    "GUSDT": "GALUSDT",
    "POLUSDT": "MATICUSDT",
    "AUSDT": "EOSUSDT",
    "1000LUNCUSDT": "LUNAUSDT",
    "VICUSDT": "TOMOUSDT",
    "DODOXUSDT": "DODOUSDT",
}

# --- Listeleme donemi (on-kayit §2, revizyon 2) ------------------------------

# On-kayit §2 rev.7 "Listeleme donemi": bu kadar ya da daha fazla ardisik sifir
# hacimli bar (bir gun) dolgu kosusudur ve donemi boler.
DOLGU_KOSU_ESIGI_BAR = 6

# On-kayit §2 rev.7: bu sureden UZUN eksik bar boslugu donemi boler. Bosluk,
# ardisik iki mevcut bar arasindaki EKSIK sure olarak olculur
# (sonraki acilis - onceki acilis - bar adimi). Kisa bosluklar borsa kesintisidir.
AZAMI_EKSIK_BAR_BOSLUGU = dt.timedelta(days=7)

# Bucket'ta <SEMBOL>SETTLED dizini. On-kayit §2 rev.7: yalnizca denetim bilgisidir,
# hicbir kurala girmez (karantina kurali kaldirildi).
SETTLED_SONEKI = "SETTLED"

# --- Veri butunlugu kontrolu (on-kayit §2, revizyon 2) -----------------------

# |open[t] / close[t-1] - 1| bu esigi asan barlar denetim raporunda listelenir.
BUTUNLUK_ACILIS_ESIGI = 0.30

# --- F1 denetim teshis esikleri ----------------------------------------------
#
# ON-KAYIT DEGILDIR. Yalnizca F1 kapsama ve butunluk raporunun sunumunu belirler;
# hicbir olay, uygunluk ya da getiri hesabina girmez. Degerler F1 gorevindeki
# kullanici talimatlarindan gelir. Denetci bulgusu B8: analysis betigine
# gomuluydu.

# "3 bardan uzun bosluklar" listesi
DENETIM_UZUN_BOSLUK_BAR = 3

# 1d turetmesi ile birincil 1d dosyalari arasinda "fark var" sayilan bagil esik
DENETIM_CAPRAZ_TOLERANS = 1e-6

# Bosluk olayi, o aralikta verisi olan sembollerin en az bu oranini etkiliyorsa
# "borsa geneli" sayilir
DENETIM_BORSA_GENELI_ORANI = 0.5

# Raporda listelenen kisa listeleme donemi esigi (gun)
DENETIM_KISA_DONEM_GUN = 60

# A1 olcumunde (D kurali, funding tamligi) temsili pozisyonun cikis barinin
# acilisindan ne kadar once girdigi (denetci bulgusu D-C5: betige gomuluydu).
# En uzun odeme araligindan (8 saat) uzundur; boylece son odemeler zincirin
# icinde kalir. Iki izgarada da aynidir (4 saatlikte 6 bar, 1 gunlukte 1 bar).
DENETIM_TEMSILI_GIRIS_SURE = dt.timedelta(hours=24)

# RESULTS §4: uzlasma sonrasi ilk funding kaydinin "en gec 8 saat sonra" basladigi
# sembol sayimi. Rev.7 metnindeki ifadeden gelir; esik ayni an ya da once
# (on-kayit §4 rev.8 "Zaman toleransi"). Betige gomuluydu (8 + 1/60).
DENETIM_ILK_GECIKME_SAAT = 8

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
