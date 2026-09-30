"""F1 veri denetimi (on-kayit §2 rev.7, CLAUDE.md §3.1).

Yalnizca KAPSAMA ve BUTUNLUK olcer. Getiri, fiyat degisimi, volatilite, funding
ortalamasi veya olay benzeri hicbir istatistik hesaplamaz ya da yazdirmaz.
On-kayit §2'nin istedigi `|open[t] / close[t-1] - 1| > 0.30` butunluk listesi
tek istisnadir; o da on-kayitta tanimli bir denetim ciktisidir.

Rev.7 evren API'si: listeleme donemleri bar duzeyindedir ve commit edilmis
`data/universe.csv` dosyasindan (`universe.sembol_donemleri`) okunur. Karantina
kurali yoktur; SETTLED aylari yalnizca denetim bilgisidir. Delist
siniflandirmasi depodaki exchangeInfo goruntusunden (`data/exchange_info_anlik.json`)
okunur, canli uc noktadan degil.

Kullanim:
    python analysis/00_veri_denetimi/calistir.py --ornek       # 30 sembollu ornek
    python analysis/00_veri_denetimi/calistir.py --is-parcaci 6  # tam evren
    python analysis/00_veri_denetimi/calistir.py --eski-evren    # + rev.7 oncesiyle karsilastirma
"""

from __future__ import annotations

import argparse
import collections
import contextlib
import io
import logging
import os
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

KOK = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KOK))

import config  # noqa: E402
from data import binance_vision as bv  # noqa: E402
from data import donem as donem_modulu  # noqa: E402
from data import eligibility as uyg  # noqa: E402
from data import funding as funding_modulu  # noqa: E402
from data import klines as klines_modulu  # noqa: E402
from data import pencere as pencere_modulu  # noqa: E402
from data import universe as universe_modulu  # noqa: E402

CIKTI_DIZINI = Path(__file__).resolve().parent

# Rev.7 oncesi (ay duzeyi, karantinali) evren tablosunun son hali. Donem sonu
# degisimlerinin ozeti bununla karsilastirilir (istege bagli, `--eski-evren`).
# Tam hash: kisaltilmis hash ileride belirsizlesebilir (D-B1).
ESKI_EVREN_REF = "a66a5e0923d8fa4cc1d08329316a46f3b86a191b:data/universe.csv"

# Ornek kume: >=5 delist, >=5 SETTLED ayli (TLMUSDT ve BNXUSDT dahil), iki donemli
# (ICPUSDT, TLMUSDT), uzun dolgulu (FTTUSDT), MATICUSDT ve POLUSDT.
ORNEK_SEMBOLLER = [
    "SRMUSDT", "HNTUSDT", "MATICUSDT", "EOSUSDT", "GALUSDT", "RNDRUSDT", "BTSUSDT",
    "BTCUSDT", "ETHUSDT", "ADAUSDT", "LINKUSDT", "XRPUSDT", "BCHUSDT", "LTCUSDT",
    "WIFUSDT", "ORDIUSDT", "MYXUSDT", "AVNTUSDT", "ASTERUSDT",
    "TLMUSDT", "BNXUSDT", "ICPUSDT", "CTKUSDT", "LITUSDT", "AERGOUSDT",
    "POLUSDT", "RENDERUSDT", "AUSDT", "FTTUSDT", "SOLUSDT",
]

FIYAT_SUTUNLARI = ["open", "high", "low", "close"]
HACIM_SUTUNLARI = ["volume", "quote_volume"]
ADIM_4H = pd.Timedelta(hours=4)

_kilit = threading.Lock()
_gunluk = logging.getLogger("denetim")


def _kaydedici_kur(etiket: str) -> Path:
    log_yolu = CIKTI_DIZINI / f"indirme_{etiket}.log"
    _gunluk.setLevel(logging.INFO)
    _gunluk.handlers.clear()
    for islemci in (logging.FileHandler(log_yolu, encoding="utf-8"), logging.StreamHandler()):
        islemci.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        _gunluk.addHandler(islemci)
    return log_yolu


# Toplam donem kesimi veri katmanindadir; evren kurulumu da ayni fonksiyonu
# kullanir (denetci bulgusu D-B3).
_toplam_doneme_kes = donem_modulu.toplam_doneme_kes


def csv_yaz(tablo: pd.DataFrame, yol: Path) -> None:
    """CSV'yi ATOMIK yazar: once ayni dizinde gecici dosya, sonra yeniden adlandirma
    (denetci bulgusu D-C3).

    Yarida kesilen bir yazma onceki kosunun dosyasini yarim birakmaz: ya eski
    dosya oldugu gibi kalir ya da yeni dosya tam haliyle yerine gecer.

    Gecici dosyanin adi her cagrida benzersizdir (denetci bulgusu D-C4): ayni
    hedefe eszamanli iki yazma birbirinin gecici dosyasini ezmez. Hata olursa
    gecici dosya silinir; geride kalan bir `.tmp` sonraki kosunun ortam kaydini
    "kirli" gostermez.
    """
    tanitici, ad = tempfile.mkstemp(prefix=yol.name + ".", suffix=".tmp", dir=yol.parent)
    os.close(tanitici)
    gecici = Path(ad)
    try:
        tablo.to_csv(gecici, index=False, lineterminator="\n")
        os.replace(gecici, yol)
    except BaseException:
        gecici.unlink(missing_ok=True)
        raise


class KosuKilidiHatasi(RuntimeError):
    """Ayni betigin baska bir kosusu suruyor (ya da kilit birakilmadan sonlandi)."""


@contextlib.contextmanager
def kosu_kilidi(ad: str, dizin: Path | None = None):
    """Kosu duzeyinde kilit: ayni betigin iki kosusu ayni anda calisamaz.

    Eszamanli iki kosu ayni cikti dosyalarina yazar; Windows'ta ayni hedefe
    eszamanli `os.replace` PermissionError verir ve iki kosunun ciktilari
    karisabilir (sizinti testcisi bulgusu). Kilit `dizin/.<ad>.kilit` dosyasini
    atomik olarak (O_EXCL) olusturur; dosya varsa ikinci kosu hicbir sey
    yazmadan `KosuKilidiHatasi` ile baslamayi reddeder. Kosu hata ile bitse de
    kilit `finally` icinde birakilir. Kilit dosyasi git'e girmez (.gitignore).
    """
    yol = (CIKTI_DIZINI if dizin is None else Path(dizin)) / f".{ad}.kilit"
    try:
        tanitici = os.open(yol, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            sahibi = yol.read_text(encoding="utf-8").strip()
        except OSError:
            sahibi = "okunamadi"
        raise KosuKilidiHatasi(
            f"{ad} zaten calisiyor: kilit dosyasi {yol} var ({sahibi}). Eszamanli kosu "
            "desteklenmez; iki kosu ayni cikti dosyalarina yazar. Calisan bir kosu yoksa "
            "(onceki kosu zorla sonlandirildiysa) kilit dosyasini elle silin."
        ) from None
    with os.fdopen(tanitici, "w", encoding="utf-8") as dosya:
        dosya.write(f"pid={os.getpid()} baslangic_utc={pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M:%S}\n")
    try:
        yield yol
    finally:
        yol.unlink(missing_ok=True)


# --- Sembol basina olcum -----------------------------------------------------


def sembol_denetle(sembol: str, evren: pd.DataFrame) -> dict:
    """Tek sembolun kapsama, donem ve butunluk olcumleri. Getiri hesaplamaz."""
    # F1 kapsama denetimi TUM gecmisi (B grubu ve C2 dahil) olcer ve getiri
    # hesaplamaz (CLAUDE.md §3.1); bu yuzden kume korumasiz ham yukleyiciler
    # bilerek kullanilir. Analiz ve olay kodu bunlari cagirmaz.
    mumlar = _toplam_doneme_kes(klines_modulu.ham_mumlari_yukle(sembol, config.BAR_4H), "open_time")
    fund = _toplam_doneme_kes(funding_modulu.ham_funding_yukle(sembol), "odeme_zamani")

    donemler = universe_modulu.sembol_donemleri(evren, sembol)
    # Tek 1d yolu (on-kayit §2 rev.8): yalnizca donem ici hizali 4h barlardan.
    gunluk = klines_modulu.gunluge_cevir(mumlar, donemler=donemler)
    cikan_gunler = cikan_gun_turleri(eski_kural_gunleri(pd.DatetimeIndex(mumlar["open_time"])),
                                     pd.DatetimeIndex(gunluk["open_time"]), donemler)
    settled = universe_modulu.settled_listesi(evren, sembol)
    zamanlar = pd.DatetimeIndex(mumlar["open_time"])
    hacim = mumlar["quote_volume"]

    # Commit edilmis donemler ham seriden yeniden turetilenle ayni mi?
    yeniden = donem_modulu.listeleme_donemleri(zamanlar, hacim, config.BAR_4H) if len(mumlar) else []
    dolgu = donem_modulu.dolgu_kosulari(zamanlar, hacim, config.BAR_4H) if len(mumlar) else []
    kisa_sifir = donem_modulu.kisa_sifir_kosulari(zamanlar, hacim, config.BAR_4H) if len(mumlar) else []

    bosluklar = klines_modulu.eksik_barlar(mumlar, config.BAR_4H)
    uzun_bosluk = bosluklar.loc[bosluklar["eksik_bar"] > config.DENETIM_UZUN_BOSLUK_BAR] if not bosluklar.empty else bosluklar

    beklenen = 0
    if not mumlar.empty:
        beklenen = len(pd.date_range(mumlar["open_time"].iloc[0], mumlar["open_time"].iloc[-1], freq=ADIM_4H))

    donem_ici_bar = sum(d.bar_sayisi for d in donemler)
    dolgu_bar = sum(k.bar_sayisi for k in dolgu)

    # Funding: donem sonrasi kayitlar (on-kayit §2 rev.7) ve ilk donem oncesi kayitlar
    kalan = funding_modulu.donem_sonrasi_kayitlari_at(fund, donemler, config.BAR_4H)
    ilk_oncesi = 0
    son_sonrasi = arada = 0
    ilk_gecikme_saat = ilk_gecikme_bitisten_saat = float("nan")
    aralar = []
    if donemler and not fund.empty:
        P = pencere_modulu  # on-kayit §4 rev.8 "Zaman toleransi"
        ilk_oncesi = int(np.sum(P.once(pd.DatetimeIndex(fund["odeme_zamani"]), donemler[0].baslangic)))
        # Atilan kayitlarin ayrimi (denetci bulgusu D-A5): son donemden sonra ve
        # iki donem arasinda. Ust sinir `_donem_icinde` ile ayni: son bar kapanisi + 1 dk.
        atilan = fund.loc[~fund["odeme_zamani"].isin(kalan["odeme_zamani"]), "odeme_zamani"]
        son_kapanis = donemler[-1].kapanis
        son_sonra_maske = np.asarray(P.sonra(pd.DatetimeIndex(atilan), son_kapanis), dtype=bool)
        son_sonrasi = int(son_sonra_maske.sum())
        arada = len(atilan) - son_sonrasi
        if son_sonrasi:
            ilk = atilan.loc[son_sonra_maske].min()
            # Iki referans (denetci bulgusu D-A5 / "54 mu 57 mi"): donem KAPANISI
            # (son barin kapanisi, cikis ani) ve donem BITISI (son barin acilisi).
            ilk_gecikme_saat = (ilk - donemler[-1].kapanis) / pd.Timedelta(hours=1)
            ilk_gecikme_bitisten_saat = (ilk - donemler[-1].bitis) / pd.Timedelta(hours=1)
        for onceki, sonraki in zip(donemler[:-1], donemler[1:]):
            ic_dolgu = any(k.konum == "ic" and onceki.bitis < k.baslangic < sonraki.baslangic for k in dolgu)
            aralar.append({
                "sembol": sembol, "onceki_bitis": onceki.bitis, "sonraki_baslangic": sonraki.baslangic,
                "ayirici": "dolgu_kosusu" if ic_dolgu else "eksik_bar_boslugu",
                "atilan_funding": int(np.sum(P.sonra(pd.DatetimeIndex(atilan), onceki.kapanis)
                                             & P.once(pd.DatetimeIndex(atilan), sonraki.baslangic))),
            })
    elif donemler:
        for onceki, sonraki in zip(donemler[:-1], donemler[1:]):
            ic_dolgu = any(k.konum == "ic" and onceki.bitis < k.baslangic < sonraki.baslangic for k in dolgu)
            aralar.append({"sembol": sembol, "onceki_bitis": onceki.bitis, "sonraki_baslangic": sonraki.baslangic,
                           "ayirici": "dolgu_kosusu" if ic_dolgu else "eksik_bar_boslugu", "atilan_funding": 0})

    # Ne donem ici ne dolgu olan bar (C2): esik alti sondaki/bastaki sifir hacimli barlar.
    donem_ici_maske = pd.Series(False, index=zamanlar)
    for x in donemler:
        donem_ici_maske |= (zamanlar >= x.baslangic) & (zamanlar <= x.bitis)
    dolgu_maske = pd.Series(False, index=zamanlar)
    for k in dolgu:
        dolgu_maske |= (zamanlar >= k.baslangic) & (zamanlar <= k.bitis)
    ne_donem_ne_dolgu = int((~donem_ici_maske & ~dolgu_maske).sum())

    sicramalar = klines_modulu.butunluk_sicramalari(mumlar)
    aralik = funding_modulu.aralik_ozeti(fund)
    sekiz_disi = aralik.loc[aralik["aralik_saat"] != 8] if not aralik.empty else aralik

    # 1d capraz dogrulama
    capraz = {"durum": "yapilmadi"}
    try:
        # Capraz dogrulama da tum gecmisi olcer; kume korumasiz ham yol bilerek.
        birincil = _toplam_doneme_kes(klines_modulu.ham_birincil_gunluk_indir(sembol), "open_time")
        if not gunluk.empty and not birincil.empty:
            fark = klines_modulu.cross_dogrula(gunluk, birincil)
            fs = [f"{c}_bagil_fark" for c in FIYAT_SUTUNLARI]
            hs = [f"{c}_bagil_fark" for c in HACIM_SUTUNLARI]
            fiyat_maske = (fark[fs] > config.DENETIM_CAPRAZ_TOLERANS).any(axis=1)
            hacim_maske = (fark[hs] > config.DENETIM_CAPRAZ_TOLERANS).any(axis=1)
            capraz = {
                "durum": "karsilastirildi",
                "ortak_gun": len(fark),
                "fiyat_farkli_gun": int(fiyat_maske.sum()),
                "hacim_farkli_gun": int(hacim_maske.sum()),
                "yalniz_birincil": fark.attrs.get("yalniz_birincil"),
                "_fiyat_tarihleri": [str(t.date()) for t in fark.loc[fiyat_maske, "open_time"]],
                "_hacim_tarihleri": [str(t.date()) for t in fark.loc[hacim_maske, "open_time"]],
            }
        else:
            capraz = {"durum": "veri yok"}
    except Exception as hata:
        capraz = {"durum": f"hata: {type(hata).__name__}"}

    return {
        "sembol": sembol,
        "bar_4h": len(mumlar),
        "beklenen_4h": beklenen,
        "eksik_bar": max(beklenen - len(mumlar), 0),
        "eksik_oran": (beklenen - len(mumlar)) / beklenen if beklenen else float("nan"),
        "bosluk_3bardan_uzun": len(uzun_bosluk),
        "gun_1d": len(gunluk),
        **{f"gun_1d_cikan_{tur}": n for tur, n in cikan_gunler.items()},
        "ilk_bar": mumlar["open_time"].iloc[0] if not mumlar.empty else pd.NaT,
        "son_bar": mumlar["open_time"].iloc[-1] if not mumlar.empty else pd.NaT,
        "donem_sayisi": len(donemler),
        "donemler_yeniden_turetimle_ayni": yeniden == donemler,
        "ilk_donem_baslangic": donemler[0].baslangic if donemler else pd.NaT,
        "son_donem_bitis": donemler[-1].bitis if donemler else pd.NaT,
        "donem_ici_bar": donem_ici_bar,
        "dolgu_kosusu": len(dolgu),
        "dolgu_bar": dolgu_bar,
        "dolgu_bar_bas": sum(k.bar_sayisi for k in dolgu if k.konum == "bas"),
        "dolgu_bar_ic": sum(k.bar_sayisi for k in dolgu if k.konum == "ic"),
        "dolgu_bar_son": sum(k.bar_sayisi for k in dolgu if k.konum == "son"),
        "kisa_sifir_kosusu": len(kisa_sifir),
        "settled_aylari": ",".join(settled),
        "funding_kayit": len(fund),
        "funding_donem_sonrasi_atilan": len(fund) - len(kalan),
        "funding_son_donem_sonrasi_atilan": son_sonrasi,
        "funding_donemler_arasi_atilan": arada,
        "funding_son_donem_sonrasi_ilk_gecikme_saat": ilk_gecikme_saat,
        "funding_son_donem_sonrasi_ilk_gecikme_bitisten_saat": ilk_gecikme_bitisten_saat,
        "funding_ilk_donem_oncesi": ilk_oncesi,
        "ne_donem_ne_dolgu_bar": ne_donem_ne_dolgu,
        "funding_aralik_8h_disi_kayit": int(sekiz_disi["kayit"].sum()) if not sekiz_disi.empty else 0,
        "funding_aralik_degerleri": ",".join(
            str(int(a)) for a in sorted(aralik["aralik_saat"].dropna().unique())
        ) if not aralik.empty else "",
        "butunluk_sicrama_sayisi": len(sicramalar),
        "capraz_durum": capraz.get("durum"),
        "capraz_ortak_gun": capraz.get("ortak_gun"),
        "capraz_fiyat_farkli_gun": capraz.get("fiyat_farkli_gun"),
        "capraz_hacim_farkli_gun": capraz.get("hacim_farkli_gun"),
        "_mumlar": mumlar,
        "_gunluk": gunluk,
        "_funding_zamanlari": pd.DatetimeIndex(fund["odeme_zamani"]) if len(fund) else pd.DatetimeIndex([], tz="UTC"),
        "_donemler": donemler,
        "_aralar": aralar,
        "_dolgu": dolgu,
        "_kisa_sifir": kisa_sifir,
        "_sicramalar": sicramalar,
        "_uzun_bosluk": uzun_bosluk,
        "_aralik": aralik,
        "_capraz": capraz,
    }


# --- Donem, dolgu ve delist olcumleri (rev.7) ----------------------------------


def dolgu_tablosu(detaylar: list[dict]) -> pd.DataFrame:
    """Tum dolgu kosulari (6+ ardisik sifir hacimli bar), konumlariyla."""
    satirlar = [
        {"sembol": d["sembol"], "bas": k.baslangic, "bitis": k.bitis, "bar_sayisi": k.bar_sayisi,
         "gun": round(k.bar_sayisi * 4 / 24, 2), "konum": k.konum}
        for d in detaylar for k in d["_dolgu"]
    ]
    return pd.DataFrame(satirlar, columns=["sembol", "bas", "bitis", "bar_sayisi", "gun", "konum"])


def kisa_sifir_tablosu(detaylar: list[dict]) -> pd.DataFrame:
    """Serinin ortasindaki 1-5 barlik sifir hacim kosulari (F1 olcumu S2'de yoktu)."""
    satirlar = []
    for d in detaylar:
        for k in d["_kisa_sifir"]:
            satirlar.append({"sembol": d["sembol"], "bas": k.baslangic, "bitis": k.bitis,
                             "bar_sayisi": k.bar_sayisi,
                             "donem_icinde": donem_modulu.donem_bul(k.baslangic, d["_donemler"]) is not None})
    return pd.DataFrame(satirlar, columns=["sembol", "bas", "bitis", "bar_sayisi", "donem_icinde"])


def delist_tablosu(evren: pd.DataFrame, detaylar: list[dict]) -> pd.DataFrame:
    """Delist siniflandirmasi: SETTLING ve exchangeInfo disi, deliveryDate iliskisiyle.

    `teslim_son_bar_icinde`: `son_donem_bitis <= deliveryDate < son_donem_bitis + 4h`.
    `sonraki_dolgu_bar`: donem sonundan sonra seride kalan sifir hacimli bar sayisi.
    """
    anlik = universe_modulu.exchange_info_anlik_yukle()
    sinif = universe_modulu.delist_sinifi(evren, anlik)
    sinif = sinif.loc[sinif["sembol"].isin({d["sembol"] for d in detaylar})]
    son_bar = {d["sembol"]: d["son_bar"] for d in detaylar}
    son_dolgu = {d["sembol"]: d["dolgu_bar_son"] for d in detaylar}
    tablo = sinif.loc[sinif["sinif"].isin([universe_modulu.SETTLING_DURUMU, "exchangeInfo_disi"])].copy()
    # Tarih sutunlari her durumda UTC (tamami NaT olan sutun saat dilimsiz tipe duser).
    for alan in ("deliveryDate", "son_donem_bitis"):
        tablo[alan] = pd.to_datetime(tablo[alan], utc=True)
    tablo["seri_son_bar"] = tablo["sembol"].map(son_bar)
    tablo["sonraki_dolgu_bar"] = tablo["sembol"].map(son_dolgu)
    tablo["teslim_eksi_bitis_saat"] = (tablo["deliveryDate"] - tablo["son_donem_bitis"]) / pd.Timedelta(hours=1)
    # B ile ayni an ya da sonra, K'dan once (on-kayit §2 ve §4 rev.8). NaT satirlar False.
    teslim = pd.DatetimeIndex(pd.to_datetime(tablo["deliveryDate"], utc=True))
    bitis = pd.DatetimeIndex(pd.to_datetime(tablo["son_donem_bitis"], utc=True))
    kapanis = pd.DatetimeIndex(pd.to_datetime(
        [pencere_modulu.donem_kapanisi(b) if pd.notna(b) else pd.NaT for b in bitis], utc=True))
    tablo["teslim_son_bar_icinde"] = (np.asarray(pencere_modulu.ayni_ya_da_sonra(teslim, bitis), dtype=bool)
                                      & np.asarray(pencere_modulu.once(teslim, kapanis), dtype=bool))
    # deliveryDate'ten (+1 dk) sonra gelen funding kaydi sayisi; yalnizca kaydin
    # varligi ve zamani. deliveryDate'i olmayan sembolde tanimsiz (NaN).
    zamanlar = {d["sembol"]: d.get("_funding_zamanlari") for d in detaylar}

    def _teslimden_sonra(r) -> float:
        z = zamanlar.get(r.sembol)
        if z is None or pd.isna(r.deliveryDate):
            return float("nan")
        return float(np.sum(pencere_modulu.sonra(z, r.deliveryDate)))

    tablo["teslimden_sonra_funding_kayit"] = [_teslimden_sonra(r) for r in tablo.itertuples()]
    tablo.attrs["alinma_zamani_utc"] = anlik.attrs["alinma_zamani_utc"]
    tablo.attrs["durum_sayimi"] = sinif["sinif"].value_counts().to_dict()
    return tablo.reset_index(drop=True)


def donem_sonu_turleri(donemler, sinif: str | None, veri_sonu_bari: pd.Timestamp,
                       zamanlar: pd.DatetimeIndex | None = None, hacim=None) -> list[str]:
    """Her donemin sonu ne ile bitiyor. Saf.

    Son donem: delist sinifi (SETTLING / exchangeInfo disi), veri sonu
    (`bitis == veri_sonu_bari`) ya da diger. Ic donem sonu: iki donem arasinda
    6+ barlik sifir hacim kosusu varsa `dolgu_kosusu`, yoksa `uzun_bosluk`
    (on-kayit §2 rev.7: donemi bolen yalnizca bu ikisidir). Ic donem icin mumlar
    (`zamanlar`, `hacim`) gerekir. Hacimden yalnizca sifir olup olmadigi okunur.

    A1 olcumu (`a1_olcumu.py`) ayni fonksiyonu buradan alir; iki olcumun donem
    sonu turu ayni tanimdan gelir.
    """
    turler = []
    dolgular = []
    if len(donemler) > 1:
        dolgular = donem_modulu.dolgu_kosulari(zamanlar, hacim, config.BAR_4H)
    for i, d in enumerate(donemler):
        if i == len(donemler) - 1:
            if sinif == universe_modulu.SETTLING_DURUMU:
                turler.append("delist_SETTLING")
            elif sinif == "exchangeInfo_disi":
                turler.append("delist_exchangeInfo_disi")
            elif d.bitis == veri_sonu_bari:
                turler.append("veri_sonu")
            else:
                turler.append("diger_son_donem")
        else:
            sonraki = donemler[i + 1].baslangic
            dolgu = any(d.bitis < k.baslangic < sonraki for k in dolgular)
            turler.append("dolgu_kosusu" if dolgu else "uzun_bosluk")
    return turler


# --- 1 gunluk seri: rev.8 oncesiyle karsilastirma (yalnizca sayim) ---------------

CIKAN_GUN_TURLERI = ("donem_basi", "donem_sonu", "ic_sinir", "donem_disi", "eklenen")


def eski_kural_gunleri(zamanlar: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Rev.8 ONCESI kuralin 1d gunleri: bütün 4h seride 6 satiri olan UTC gunleri. Saf.

    Yalnizca karsilastirma sayimi icindir (RESULTS §14.8); fiyat ya da hacim
    toplamaz, 1d serisi URETMEZ. Tek 1d turetme yolu `klines.gunluge_cevir`dir.
    """
    gunler = pd.DatetimeIndex(zamanlar).floor("D")
    sayim = pd.Series(1, index=gunler).groupby(level=0).size()
    return pd.DatetimeIndex(sayim.index[sayim.to_numpy() == klines_modulu.GUNLUK_BAR_SAYISI])


def cikan_gun_turleri(eski: pd.DatetimeIndex, yeni: pd.DatetimeIndex, donemler) -> dict[str, int]:
    """Eski kuralin 1d serisinde olup rev.8 serisinde olmayan gunler, yere gore. Saf.

    `donem_basi`: ilk donemin baslangic gunu; `donem_sonu`: son donemin bitis (B) gunu;
    `ic_sinir`: diger donem baslangic ve bitis gunleri; `donem_disi`: hicbir donemin
    baslangic ya da bitis gununu icermeyen gun (ör. uzlasma sonrasi dolgu gunleri).
    `eklenen`: rev.8 serisinde olup eskide olmayan gun (beklenen 0).
    """
    sayim = dict.fromkeys(CIKAN_GUN_TURLERI, 0)
    son = len(donemler) - 1
    baslar = {d.baslangic.floor("D"): i for i, d in enumerate(donemler)}
    bitisler = {d.bitis.floor("D"): i for i, d in enumerate(donemler)}
    for gun in eski.difference(yeni):
        if baslar.get(gun) == 0:
            sayim["donem_basi"] += 1
        elif bitisler.get(gun) == son:
            sayim["donem_sonu"] += 1
        elif gun in baslar or gun in bitisler:
            sayim["ic_sinir"] += 1
        else:
            sayim["donem_disi"] += 1
    sayim["eklenen"] = len(yeni.difference(eski))
    return sayim


# --- 1 gunluk barlarin donem sinirlari (denetci bulgusu D-A1) ------------------

GUN = pd.Timedelta(days=1)


def _gun_bar_sayilari(zamanlar: pd.DatetimeIndex, gun: pd.Timestamp, donem) -> tuple[int, int]:
    """Bir UTC gunundeki 4 saatlik barlardan donem ici ve donem disi olanlarin sayisi. Saf."""
    gunde = zamanlar[(zamanlar >= gun) & (zamanlar < gun + GUN)]
    ici = int(((gunde >= donem.baslangic) & (gunde <= donem.bitis)).sum())
    return ici, len(gunde) - ici


def gunluk_sinir_satirlari(sembol: str, zamanlar: pd.DatetimeIndex, gun_acilislari: pd.DatetimeIndex,
                           donemler, turler: list[str]) -> list[dict]:
    """Her donemin basinda ve sonunda 1 gunluk seriye giren gunler. Saf.

    Yalnizca ZAMAN DAMGASI kullanir: 4 saatlik barlarin acilislari (`zamanlar`),
    bugunku 1 gunluk serinin gun acilislari (`gun_acilislari`,
    `klines.gunluge_cevir` ciktisi; 6 barin tamami olan gunler) ve donem
    sinirlari. Fiyat, hacim ya da funding okumaz.

    Bugunku kod 1 gunluk seriyi TUM 4 saatlik seriden kurar; donem sinirini
    bilmez. Bir satirda:
      - `bas_gunu` / `bitis_gunu`: donem baslangicini / bitisini iceren UTC gunu;
        `*_1d_serisinde` o gun bugunku 1 gunluk seride var mi (6 bar mevcut mu),
        `*_donem_ici_bar` / `*_donem_disi_bar` o gunun 4 saatlik barlarindan
        donem icinde / disinda kalanlar.
      - `ilk_gun`: donemle kesisen ilk 1 gunluk bar (acilisi `bas_gunu` ya da
        sonrasi, bitisten once).
      - `son_gun`: donem sonunda cikisin okundugu 1 gunluk bar. `pencere.cikis_bari`
        donem sonunda "sinirdan (donem bitisi) onceki son bar"i secer; 1 gunluk
        seride bu, acilisi donem bitisine esit ya da ondan once olan son gundur.
      - `*_donem_disi_bar`: o 1 gunluk bara giren donem disi 4 saatlik bar sayisi.
    Donem sinirlari bar duzeyindedir (on-kayit §2 rev.7). `bas_turu`: ilk donemin
    basi `donem_basi`, digerleri `ic_sinir`. `son_turu`: `donem_sonu_turleri`.
    """
    satirlar = []
    for i, (d, tur) in enumerate(zip(donemler, turler)):
        bas_gunu, bitis_gunu = d.baslangic.floor("D"), d.bitis.floor("D")
        kesisen = gun_acilislari[(gun_acilislari >= bas_gunu) & (gun_acilislari <= d.bitis)]
        ilk_gun = kesisen[0] if len(kesisen) else pd.NaT
        son_gun = kesisen[-1] if len(kesisen) else pd.NaT
        bas_ici, bas_disi = _gun_bar_sayilari(zamanlar, bas_gunu, d)
        bit_ici, bit_disi = _gun_bar_sayilari(zamanlar, bitis_gunu, d)
        satirlar.append({
            "sembol": sembol, "donem_sira": i, "donem_baslangic": d.baslangic, "donem_bitis": d.bitis,
            "bas_turu": "donem_basi" if i == 0 else "ic_sinir", "son_turu": tur,
            "bas_gunu": bas_gunu, "bas_gunu_1d_serisinde": bool(bas_gunu in gun_acilislari),
            "bas_gunu_donem_ici_bar": bas_ici, "bas_gunu_donem_disi_bar": bas_disi,
            "bitis_gunu": bitis_gunu, "bitis_gunu_1d_serisinde": bool(bitis_gunu in gun_acilislari),
            "bitis_gunu_donem_ici_bar": bit_ici, "bitis_gunu_donem_disi_bar": bit_disi,
            "ilk_gun": ilk_gun,
            "ilk_gun_donem_disi_bar": _gun_bar_sayilari(zamanlar, ilk_gun, d)[1] if len(kesisen) else 0,
            "son_gun": son_gun,
            "son_gun_donem_disi_bar": _gun_bar_sayilari(zamanlar, son_gun, d)[1] if len(kesisen) else 0,
        })
    return satirlar


GUNLUK_SINIR_SUTUNLARI = [
    "sembol", "donem_sira", "donem_baslangic", "donem_bitis", "bas_turu", "son_turu",
    "bas_gunu", "bas_gunu_1d_serisinde", "bas_gunu_donem_ici_bar", "bas_gunu_donem_disi_bar",
    "bitis_gunu", "bitis_gunu_1d_serisinde", "bitis_gunu_donem_ici_bar", "bitis_gunu_donem_disi_bar",
    "ilk_gun", "ilk_gun_donem_disi_bar", "son_gun", "son_gun_donem_disi_bar",
]


def gunluk_sinir_tablosu(detaylar: list[dict], delist: pd.DataFrame) -> pd.DataFrame:
    """Tum dahil sembollerde `gunluk_sinir_satirlari` (denetci bulgusu D-A1).

    Veri sonu bari tum donem bitislerinin en gecidir (A1 olcumuyle ayni tanim).
    """
    bitisler = [x.bitis for d in detaylar for x in d["_donemler"]]
    veri_sonu_bari = max(bitisler) if bitisler else pd.Timestamp.min.tz_localize("UTC")
    sinif = delist.set_index("sembol")["sinif"].to_dict()
    satirlar = []
    for d in detaylar:
        donemler = d["_donemler"]
        if not donemler:
            continue
        zamanlar = pd.DatetimeIndex(d["_mumlar"]["open_time"])
        turler = donem_sonu_turleri(donemler, sinif.get(d["sembol"]), veri_sonu_bari,
                                    zamanlar, d["_mumlar"]["quote_volume"])
        gunler = pd.DatetimeIndex(d["_gunluk"]["open_time"]) if len(d["_gunluk"]) else pd.DatetimeIndex([], tz="UTC")
        satirlar += gunluk_sinir_satirlari(d["sembol"], zamanlar, gunler, donemler, turler)
    return pd.DataFrame(satirlar, columns=GUNLUK_SINIR_SUTUNLARI)


def funding_siz_donemler(evren: pd.DataFrame) -> pd.DataFrame:
    """Hic funding kaydi olmayan listeleme donemleri (on-kayit §2 rev.7: hic kullanilmaz)."""
    d = evren.loc[(~evren["haric"]) & (evren["donem_id"] >= 0) & evren["donem_funding_yok"]]
    return d[["sembol", "donem_id", "donem_baslangic", "donem_bitis", "donem_bar_sayisi",
              "donem_gercek_bar_sayisi", "settled_aylari"]].reset_index(drop=True)


def eski_evreni_oku(ref: str = ESKI_EVREN_REF) -> pd.DataFrame:
    """Rev.7 oncesi ay duzeyindeki evren tablosunu git gecmisinden okur."""
    govde = subprocess.run(["git", "show", ref], cwd=KOK, check=True, capture_output=True).stdout
    return pd.read_csv(io.BytesIO(govde), keep_default_na=False, encoding="utf-8")


def _ay_sonu_bari(ay: str) -> pd.Timestamp:
    return pd.Period(ay, freq="M").end_time.floor("4h").tz_localize("UTC")


def _eski_donem_ici(zamanlar: pd.DatetimeIndex, eski_satirlar: pd.DataFrame) -> pd.Series:
    """Eski (ay duzeyi) donemlere gore her bar donem icinde mi. Saf."""
    ici = pd.Series(False, index=zamanlar)
    for r in eski_satirlar.itertuples():
        bas = pd.Period(r.donem_bas_ay, freq="M").start_time.tz_localize("UTC")
        son = pd.Period(r.donem_son_ay, freq="M").end_time.tz_localize("UTC")
        ici |= (zamanlar >= bas) & (zamanlar <= son)
    return ici


def donem_sonu_degisimleri(eski: pd.DataFrame, detaylar: list[dict]) -> pd.DataFrame:
    """Sembol basina eski (ay duzeyi, karantinali) ile yeni (bar duzeyi) donem sinirlari.

    Eski son sinir = eski son donemin son ayindaki son 4h bar, serinin son barina
    kirpilmis. Eski karantina aylari donemleri boldugu icin donem sayisi da
    karsilastirilir. Pozitif `bitis_kisalma_gun`, yeni donemin daha erken bittigidir.

    Ic sinirlar (denetci bulgusu D-A2): ilk baslangic ve son bitis ayni olsa bile
    ic donem sinirlari degismis olabilir (CVCUSDT: eski donem 0 ic dolguyu
    iceriyordu). Bu yuzden serinin her bari eski ve yeni kurala gore ayri ayri
    siniflanir: `eski_ici_yeni_disi_bar` (eskide donem ici, yenide degil) ve
    `yeni_ici_eski_disi_bar`. `degisti`: iki sayidan biri sifir degil.
    `yalniz_ic_sinir`: degisti ama ilk baslangic ve son bitis ayni.
    """
    eski = eski.loc[(eski["haric"].astype(str) == "False") & (eski["donem_id"].astype(int) >= 0)]
    eski_grup = {s: g.sort_values("donem_id") for s, g in eski.groupby("sembol")}
    satirlar = []
    for d in detaylar:
        g = eski_grup.get(d["sembol"])
        yeni = d["_donemler"]
        satir = {"sembol": d["sembol"], "eski_donem_sayisi": 0 if g is None else len(g),
                 "yeni_donem_sayisi": len(yeni)}
        if g is not None and yeni and pd.notna(d["son_bar"]):
            eski_bas = pd.Period(g["donem_bas_ay"].iloc[0], freq="M").start_time.tz_localize("UTC")
            eski_bas = max(eski_bas, pd.Timestamp(d["ilk_bar"]))
            eski_son = min(_ay_sonu_bari(g["donem_son_ay"].iloc[-1]), pd.Timestamp(d["son_bar"]))
            bas_gecikme = round((yeni[0].baslangic - eski_bas) / pd.Timedelta(days=1), 2)
            son_kisalma = round((eski_son - yeni[-1].bitis) / pd.Timedelta(days=1), 2)
            satir.update({
                "eski_ilk_baslangic": eski_bas, "yeni_ilk_baslangic": yeni[0].baslangic,
                "eski_son_bitis": eski_son, "yeni_son_bitis": yeni[-1].bitis,
                "baslangic_gecikme_gun": bas_gecikme,
                "bitis_kisalma_gun": son_kisalma,
            })
            # Bar duzeyi karsilastirma mumlari gerektirir; mum yoksa (yalnizca
            # sinir bilgisiyle cagrilirsa) alanlar bos kalir.
            mumlar = d.get("_mumlar")
            if mumlar is not None:
                zamanlar = pd.DatetimeIndex(mumlar["open_time"])
                eski_ici = _eski_donem_ici(zamanlar, g).to_numpy()
                yeni_ici = pd.Series(False, index=zamanlar)
                for x in yeni:
                    yeni_ici |= (zamanlar >= x.baslangic) & (zamanlar <= x.bitis)
                yeni_ici = yeni_ici.to_numpy()
                eksi, arti = int((eski_ici & ~yeni_ici).sum()), int((yeni_ici & ~eski_ici).sum())
                satir.update({
                    "eski_ici_yeni_disi_bar": eksi,
                    "yeni_ici_eski_disi_bar": arti,
                    "degisti": bool(eksi or arti),
                    "yalniz_ic_sinir": bool((eksi or arti) and bas_gecikme == 0 and son_kisalma == 0),
                })
            satir["eski_karantina_aylari"] = str(g["karantina_aylari"].iloc[0])
        satirlar.append(satir)
    return pd.DataFrame(satirlar)


def settled_karsilastirma(detaylar: list[dict]) -> pd.DataFrame:
    """Her SETTLED ayinda dolgu kosusu ya da donem siniri var mi? Yalnizca denetim."""
    satirlar = []
    for d in detaylar:
        for ay in [a for a in d["settled_aylari"].split(",") if a]:
            p = pd.Period(ay, freq="M")
            bas = p.start_time.tz_localize("UTC")
            son = p.end_time.tz_localize("UTC")
            dolgu = any(k.baslangic <= son and bas <= k.bitis for k in d["_dolgu"])
            sinir = any(bas <= t <= son for x in d["_donemler"] for t in (x.baslangic, x.bitis))
            satirlar.append({"sembol": d["sembol"], "ay": ay, "dolgu_kosusu_var": dolgu,
                             "donem_siniri_var": sinir})
    return pd.DataFrame(satirlar, columns=["sembol", "ay", "dolgu_kosusu_var", "donem_siniri_var"])


def settled_icerik(detaylar: list[dict], sembol_dizinleri: list[str], ozet: pd.DataFrame) -> pd.DataFrame:
    """Her SETTLED ayinin mumlarini ana seriyle bar bar karsilastirir (denetci bulgusu C3).

    `ozet`: `settled_karsilastirma` ciktisi; `donem_icinde` = o ayda ne dolgu kosusu
    ne donem siniri var, yani ay tumuyle bir donemin icinde (rev.7 ile doneme giren aylar).
    Yalnizca veri butunlugu: getiri veya fiyat davranisi hesaplanmaz.
    """
    satirlar = []
    for d in detaylar:
        aylar = [a for a in d["settled_aylari"].split(",") if a]
        if not aylar:
            continue
        dizinler = klines_modulu.settled_dizinleri(d["sembol"], sembol_dizinleri)
        parcalar = [klines_modulu.ham_settled_mumlari_yukle(x) for x in dizinler]
        settled = pd.concat(parcalar, ignore_index=True) if parcalar else pd.DataFrame(columns=["open_time"])
        for ay in aylar:
            satirlar.append({"sembol": d["sembol"], "settled_dizini": ",".join(dizinler),
                             **klines_modulu.settled_ay_karsilastir(d["_mumlar"], settled, ay)})
    tablo = pd.DataFrame(satirlar)
    if tablo.empty:
        return tablo
    tablo = tablo.merge(ozet, on=["sembol", "ay"], how="left")
    tablo["donem_icinde"] = ~tablo["dolgu_kosusu_var"] & ~tablo["donem_siniri_var"]
    return tablo.sort_values(["sembol", "ay"], ignore_index=True)


# --- Toplu olcumler ----------------------------------------------------------


def yillik_kapsama(detaylar: list[dict], evren: pd.DataFrame) -> pd.DataFrame:
    """Yillara gore: veri bulunan sembol, 10M ve 2M esigini en az bir barda gecen.

    Uygunluk rev.7 donemleriyle olculur; funding'siz donemler (hic kullanilmaz)
    sayilmaz.

    Payda (denetci bulgusu D-C1): `veri_bulunan_sembol` o yil en az bir GERCEK
    (donem ici) bari olan sembollerdir; dolgu barlari hicbir hesaba girmez
    (on-kayit §2 rev.7). Yalnizca dolgu bari olan semboller ayrica
    `yalniz_dolgu_bari_olan` sutununda sayilir.
    """
    funding_yok = {
        (r.sembol, int(r.donem_id))
        for r in evren.loc[evren["donem_funding_yok"] & (evren["donem_id"] >= 0)].itertuples()
    }
    satirlar = []
    for yil in range(config.DONEM_BASI.year, config.DONEM_SONU.year + 1):
        bas = pd.Timestamp(f"{yil}-01-01", tz="UTC")
        son = pd.Timestamp(f"{yil}-12-31 23:59:59", tz="UTC")
        veri_var = yalniz_dolgu = esik_10m = esik_2m = 0

        for d in detaylar:
            gunluk = d["_gunluk"]
            donemler = d["_donemler"]
            mm = d["_mumlar"]
            if mm.empty:
                continue
            yil_ici = mm.loc[(mm["open_time"] >= bas) & (mm["open_time"] <= son), "open_time"]
            if yil_ici.empty:
                continue
            gercek = any(x.baslangic <= son and bas <= x.bitis for x in donemler)
            if not gercek:
                yalniz_dolgu += 1
                continue
            veri_var += 1

            hacim = uyg.gunluk_hacim_serisi(gunluk)
            on_m = iki_m = False
            for t in yil_ici:
                kimlik = donem_modulu.donem_bul(t, donemler)
                if kimlik is None or (d["sembol"], kimlik) in funding_yok:
                    continue
                # F1 denetimi tum gecmisi olcer, bir kumeye ait degildir: kume
                # baslangici bilincli olarak None (on-kayit §3 rev.5 kume hesaplari icindir).
                sinirlar = dict(donem_baslangic=donemler[kimlik].baslangic,
                                donem_bitis=donemler[kimlik].bitis, kume_baslangic=None)
                if not on_m and uyg.uygun_mu(hacim, t, config.BAR_4H, **sinirlar):
                    on_m = True
                # 1d barin zamani UTC gun acilisidir (on-kayit §6 rev.8 "Donem uyeligi");
                # 1d uygunluk yalnizca gun acilisinda sorulur. Rev.8 oncesi her 4h anda
                # soruluyordu; `donem_ici_mi` gun ortasi 1d zamanini reddeder.
                if (not iki_m and t == t.floor("D")
                        and uyg.uygun_mu(hacim, t, config.BAR_1D, **sinirlar)):
                    iki_m = True
                if on_m and iki_m:
                    break
            esik_10m += int(on_m)
            esik_2m += int(iki_m)

        satirlar.append(
            {"yil": yil, "veri_bulunan_sembol": veri_var, "yalniz_dolgu_bari_olan": yalniz_dolgu,
             "esik_10M_gecen": esik_10m, "esik_2M_gecen": esik_2m}
        )
    return pd.DataFrame(satirlar)


def bosluklari_grupla(detaylar: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Bar bosluklarini OLAYLARA toplar ve borsa geneli / sembole ozgu ayirir.

    Gruplama ZAMAN ORTUSMESINE gore yapilir: birbiriyle ortusen bosluklar tek bir
    olaydir. O zaman araliginda verisi bulunan sembollerin en az yarisini
    etkileyen olay "borsa geneli" sayilir. Yalnizca bir TESHIS olcumudur.
    `donem_bolen`: 7 gunden uzun eksik sure (on-kayit §2 rev.7) donemi boler.
    """
    satirlar = []
    for d in detaylar:
        b = d["_uzun_bosluk"]
        for _, r in b.iterrows():
            satirlar.append({"sembol": d["sembol"], "bas": r["bas"], "son": r["son"],
                             "eksik_bar": int(r["eksik_bar"]),
                             "donem_bolen": int(r["eksik_bar"]) * ADIM_4H > pd.Timedelta(config.AZAMI_EKSIK_BAR_BOSLUGU)})
    olay_sutunlari = ["olay_id", "bas", "son", "etki_sembol", "o_aralikta_veri_olan", "borsa_geneli",
                      "azami_eksik_bar", "semboller"]
    if not satirlar:
        return (pd.DataFrame(columns=["sembol", "bas", "son", "eksik_bar", "donem_bolen", "olay_id"]),
                pd.DataFrame(columns=olay_sutunlari))

    tablo = pd.DataFrame(satirlar).sort_values(["bas", "sembol"], ignore_index=True)

    olay_id = []
    su_an = 0
    olay_bas, olay_son = tablo.loc[0, "bas"], tablo.loc[0, "son"]
    sinirlar = []
    for _, r in tablo.iterrows():
        if r["bas"] <= olay_son:
            olay_son = max(olay_son, r["son"])
        else:
            sinirlar.append((su_an, olay_bas, olay_son))
            su_an += 1
            olay_bas, olay_son = r["bas"], r["son"]
        olay_id.append(su_an)
    sinirlar.append((su_an, olay_bas, olay_son))
    tablo["olay_id"] = olay_id

    def veri_olan(bas, son, etkilenen: set[str]) -> int:
        # Payda: o aralikla kesisen bir listeleme donemi olan sembol. Yalnizca
        # dolgu bari olan (uzlasmis) semboller sayilmaz (denetci bulgusu D-C1).
        # Boslugu donemleri ayiran sembol (BNXUSDT) hicbir donemle kesismez ama
        # etkilenmistir; etkilenen her sembol paydaya girer.
        return sum(
            1 for d in detaylar
            if d["sembol"] in etkilenen
            or any(x.baslangic <= son and bas <= x.bitis for x in d["_donemler"])
        )

    olaylar = []
    for kimlik, bas, son in sinirlar:
        parca = tablo.loc[tablo["olay_id"] == kimlik]
        etki = parca["sembol"].nunique()
        kapsam = veri_olan(bas, son, set(parca["sembol"]))
        olaylar.append(
            {"olay_id": kimlik, "bas": bas, "son": son, "etki_sembol": etki,
             "o_aralikta_veri_olan": kapsam,
             "borsa_geneli": bool(kapsam and etki >= kapsam * config.DENETIM_BORSA_GENELI_ORANI),
             "azami_eksik_bar": int(parca["eksik_bar"].max()),
             "semboller": ",".join(sorted(parca["sembol"].unique())[:20])}
        )
    return tablo, pd.DataFrame(olaylar, columns=olay_sutunlari).sort_values(
        ["azami_eksik_bar", "bas"], ascending=[False, True], ignore_index=True
    )


def kisa_donemler(detaylar: list[dict], asgari_gun: int = config.DENETIM_KISA_DONEM_GUN) -> pd.DataFrame:
    """60 gunden kisa listeleme donemleri (30 gunluk pencere bunlari etkisiz birakir)."""
    satirlar = []
    for d in detaylar:
        for i, x in enumerate(d["_donemler"]):
            gun = (x.kapanis - x.baslangic) / pd.Timedelta(days=1)
            if gun < asgari_gun:
                satirlar.append({"sembol": d["sembol"], "donem_id": i, "baslangic": x.baslangic,
                                 "bitis": x.bitis, "gun": round(gun, 2)})
    return pd.DataFrame(satirlar, columns=["sembol", "donem_id", "baslangic", "bitis", "gun"]).sort_values(
        ["gun", "sembol"], ignore_index=True
    )


def fiyat_farki_listeleme_yasi(detaylar: list[dict]) -> pd.DataFrame:
    """Fiyat farki cikan gunler, ait oldugu donemin basindan kac gun sonra?"""
    satirlar = []
    for d in detaylar:
        c = d["_capraz"]
        if c.get("durum") != "karsilastirildi":
            continue
        for tarih in c.get("_fiyat_tarihleri", []):
            t = pd.Timestamp(tarih, tz="UTC")
            kimlik = donem_modulu.donem_bul(t, d["_donemler"])
            bas = d["_donemler"][kimlik].baslangic if kimlik is not None else pd.NaT
            gun = (t - bas) / pd.Timedelta(days=1) if kimlik is not None else float("nan")
            satirlar.append(
                {"sembol": d["sembol"], "tarih": tarih,
                 "donem_baslangic": bas, "donem_basindan_gun": round(gun, 1),
                 "ilk_30_gun_icinde": bool(gun < 30) if kimlik is not None else False}
            )
    return pd.DataFrame(
        satirlar, columns=["sembol", "tarih", "donem_baslangic", "donem_basindan_gun", "ilk_30_gun_icinde"]
    ).sort_values(["donem_basindan_gun", "sembol"], ignore_index=True)


def git_durumu() -> dict:
    """Commit ve calisma agaci durumu. Kosunun BASINDA, hicbir cikti yazilmadan
    cagrilir; boylece kosunun kendi ciktilari kirlilik sayilmaz (denetci bulgusu
    D-B2). git yoksa "bilinmiyor"."""
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=KOK, capture_output=True,
                                text=True, check=True).stdout.strip()
        durum = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=KOK,
                               capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return {"commit": "bilinmiyor", "degisiklikler": [], "bilinmiyor": True}
    return {"commit": commit, "degisiklikler": sorted(s for s in durum.splitlines() if s.strip()),
            "bilinmiyor": False}


def ortam_kaydi(git: dict, baslangic: pd.Timestamp, bitis: pd.Timestamp) -> pd.DataFrame:
    """Kosuyu ureten ortam: Python, paket surumleri, git commit'i ve kosu zamani (UTC).

    `git`: kosu basinda alinan `git_durumu()`. Calisma agaci kirliyse degisen
    dosyalar da yazilir; ciktilar hangi koddan uretildigi izlenebilsin.
    """
    import importlib.metadata as md
    import platform

    if git["bilinmiyor"]:
        agac = "bilinmiyor (git yok)"
    else:
        agac = "temiz" if not git["degisiklikler"] else "kirli"
    satirlar = [
        {"bilesen": "git_commit", "surum": git["commit"]},
        {"bilesen": "calisma_agaci", "surum": agac},
        {"bilesen": "calisma_agaci_degisiklikleri", "surum": " | ".join(git["degisiklikler"])},
        {"bilesen": "kosu_baslangic_utc", "surum": baslangic.strftime("%Y-%m-%d %H:%M:%S")},
        {"bilesen": "kosu_bitis_utc", "surum": bitis.strftime("%Y-%m-%d %H:%M:%S")},
        {"bilesen": "python", "surum": platform.python_version()},
        {"bilesen": "python_derleme", "surum": platform.python_build()[1]},
        {"bilesen": "python_yolu", "surum": sys.executable},
        {"bilesen": "platform", "surum": platform.platform()},
    ]
    for paket in ("pandas", "numpy", "pyarrow", "requests"):
        try:
            satirlar.append({"bilesen": paket, "surum": md.version(paket)})
        except Exception:
            satirlar.append({"bilesen": paket, "surum": "bulunamadi"})
    return pd.DataFrame(satirlar)


def sicramalari_grupla(detaylar: list[dict]) -> pd.DataFrame:
    """%30 acilis farklarini rev.7 donem kurallarina gore siniflar.

    `sinif`:
      - "donem_basi": sicrama barinin kendisi bir donemin ilk gercek bari; onceki
        bar baska bir donemde ya da dolguda. Donem bolme kuraliyla aciklanir.
      - "donem_disi": sicrama bari hicbir donemde degil (dolgu); hesaba girmez.
      - "donem_ici_bosluk_sonrasi": donem icinde, 7 gunden kisa bir eksik bar
        boslugunun ardindaki ilk bar; rev.3 bosluk kurallarina tabi.
      - "donem_ici": donem icinde, onceki bar bitisik. Donem kurallariyla aciklanamaz.
    `settled_ayi`: o ay icin SETTLED kaydi var mi (yalnizca denetim bilgisi).
    """
    sutunlar = ["sembol", "open_time", "onceki_close", "open", "bagil_fark", "sinif",
                "onceki_bar", "eksik_sure_saat", "settled_ayi"]
    parcalar = []
    for d in detaylar:
        s = d["_sicramalar"]
        if s.empty:
            continue
        zamanlar = pd.DatetimeIndex(d["_mumlar"]["open_time"])
        settled = set(a for a in d["settled_aylari"].split(",") if a)
        donemler = d["_donemler"]
        for _, r in s.iterrows():
            t = pd.Timestamp(r["open_time"])
            konum = zamanlar.get_loc(t)
            onceki = zamanlar[konum - 1]
            eksik = (t - onceki - ADIM_4H) / pd.Timedelta(hours=1)
            kimlik = donem_modulu.donem_bul(t, donemler)
            if kimlik is None:
                sinif = "donem_disi"
            elif t == donemler[kimlik].baslangic:
                sinif = "donem_basi"
            elif eksik > 0:
                sinif = "donem_ici_bosluk_sonrasi"
            else:
                sinif = "donem_ici"
            parcalar.append({"sembol": d["sembol"], "open_time": t, "onceki_close": r["onceki_close"],
                             "open": r["open"], "bagil_fark": r["bagil_fark"], "sinif": sinif,
                             "onceki_bar": onceki, "eksik_sure_saat": eksik,
                             "settled_ayi": str(pd.Period(t.tz_localize(None), freq="M")) in settled})
    return pd.DataFrame(parcalar, columns=sutunlar).sort_values(
        ["bagil_fark", "sembol"], ascending=[False, True], ignore_index=True
    )


def funding_dagilimi(detaylar: list[dict]) -> pd.DataFrame:
    """Odeme araligi dagilimi: kayit ve sembol sayisi."""
    kayit = collections.Counter()
    sembol = collections.defaultdict(set)
    for d in detaylar:
        a = d["_aralik"]
        for _, r in a.iterrows():
            saat = int(r["aralik_saat"])
            kayit[saat] += int(r["kayit"])
            sembol[saat].add(d["sembol"])
    return pd.DataFrame(
        [{"aralik_saat": s, "kayit": kayit[s], "sembol": len(sembol[s])} for s in sorted(kayit)],
        columns=["aralik_saat", "kayit", "sembol"],
    )


def capraz_ozet(detaylar: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """1d turetme karsilastirmasinin toplu ozeti ve en yogun tarihler."""
    fiyat = collections.Counter()
    hacim = collections.Counter()
    toplam_gun = fiyat_gun = hacim_gun = 0
    satirlar = []
    for d in detaylar:
        c = d["_capraz"]
        if c.get("durum") != "karsilastirildi":
            satirlar.append({"sembol": d["sembol"], "durum": c.get("durum")})
            continue
        toplam_gun += c["ortak_gun"]
        fiyat_gun += c["fiyat_farkli_gun"]
        hacim_gun += c["hacim_farkli_gun"]
        fiyat.update(c["_fiyat_tarihleri"])
        hacim.update(c["_hacim_tarihleri"])
        satirlar.append(
            {"sembol": d["sembol"], "durum": "karsilastirildi", "ortak_gun": c["ortak_gun"],
             "fiyat_farkli_gun": c["fiyat_farkli_gun"], "hacim_farkli_gun": c["hacim_farkli_gun"],
             "yalniz_birincil": c["yalniz_birincil"]}
        )
    # Esit sayida tarih varsa tarih sirasi belirleyicidir (tekrarlanabilirlik).
    def _en_yogun(sayac):
        return sorted(sayac.items(), key=lambda x: (-x[1], x[0]))[:5]
    yogun = pd.DataFrame(
        [{"tarih": t, "tip": "fiyat", "sembol_sayisi": n} for t, n in _en_yogun(fiyat)]
        + [{"tarih": t, "tip": "hacim", "sembol_sayisi": n} for t, n in _en_yogun(hacim)],
        columns=["tarih", "tip", "sembol_sayisi"],
    )
    ozet = pd.DataFrame(satirlar)
    ozet.attrs["toplam_gun"] = toplam_gun
    ozet.attrs["fiyat_gun"] = fiyat_gun
    ozet.attrs["hacim_gun"] = hacim_gun
    return ozet, yogun


def donem_aralari_tablosu(detaylar: list[dict]) -> pd.DataFrame:
    """Iki donemli sembollerde donemleri ayiran sey: dolgu kosusu ya da 7 gunden uzun
    eksik bar boslugu; aradaki atilan funding kaydi sayisiyla (denetci bulgusu D-A5)."""
    return pd.DataFrame(
        [a for d in detaylar for a in d["_aralar"]],
        columns=["sembol", "onceki_bitis", "sonraki_baslangic", "ayirici", "atilan_funding"],
    )


def _gecikme_esik_icinde(saat: pd.Series) -> np.ndarray:
    """Gecikme (saat), `config.DENETIM_ILK_GECIKME_SAAT` ile ayni an ya da ondan once mi
    (on-kayit §4 rev.8 "Zaman toleransi"). Saf."""
    gecikme = pd.to_timedelta(pd.to_numeric(saat, errors="coerce"), unit="h")
    return np.asarray(pencere_modulu.ayni_ya_da_once(gecikme, pd.Timedelta(hours=config.DENETIM_ILK_GECIKME_SAAT)),
                      dtype=bool)


def rapor_sayilari(t: dict[str, pd.DataFrame], evren: pd.DataFrame, bolme: pd.DataFrame) -> pd.DataFrame:
    """RESULTS.md'deki her sayinin betikten turetilmis kaynagi (denetci bulgusu D-A5).

    `t`: bu kosunun tablolari. Satir: bolum, kalem, deger. Rapor yalnizca bu
    tablodaki ve ham CSV'lerdeki sayilari kullanir.
    """
    s: list[tuple[str, str, object]] = []

    def ekle(bolum: str, kalem: str, deger) -> None:
        s.append((bolum, kalem, deger))

    ozet = t["sembol_ozeti"]
    semboller = set(ozet["sembol"])

    # §1 Evren, bolme ve donemler
    tekil = evren.drop_duplicates("sembol")
    ekle("1", "evren_tablosu_sembol (bucket USDT perpetual dizini)", tekil["sembol"].nunique())
    ekle("1", "dahil_sembol", len(semboller))
    gerekce = tekil.loc[tekil["haric"], "haric_gerekce"].astype(str)
    ekle("1", "haric_tradifi", int(gerekce.str.contains("TRADIFI").sum()))
    ekle("1", "haric_endeks", int(gerekce.str.contains("endeks").sum()))
    ekle("1", "haric_stablecoin", int(gerekce.str.contains("stablecoin").sum()))
    ekle("1", "donem_sayisi", int(ozet["donem_sayisi"].sum()))
    for n, g in ozet.groupby("donem_sayisi"):
        ekle("1", f"donem_sayisi_{n}_olan_sembol", len(g))
    ekle("1", "donemler_yeniden_turetimle_ayni", int(ozet["donemler_yeniden_turetimle_ayni"].sum()))
    aralar = t["donem_aralari"]
    for a, g in aralar.groupby("ayirici"):
        ekle("1", f"donem_ayirici_{a}", len(g))
    b = bolme.loc[bolme["sembol"].isin(semboller)]
    ekle("1", "bolme_sembol", len(b))
    ekle("1", "bolme_varlik_anahtari", b["varlik_anahtari"].nunique())
    for grup, g in b.groupby("grup"):
        ekle("1", f"bolme_grup_{grup}", len(g))

    # §2 Delist siniflandirmasi
    delist = t["delist_siniflandirmasi"]
    for sinif, n in sorted(delist.attrs.get("durum_sayimi", {}).items()):
        ekle("2", f"sinif_{sinif}", int(n))
    for sinif, g in delist.groupby("sinif"):
        ekle("2", f"{sinif}_sonraki_dolgu_olan", int((g["sonraki_dolgu_bar"] > 0).sum()))
        ekle("2", f"{sinif}_sonraki_dolgu_bar", int(g["sonraki_dolgu_bar"].sum()))
        ekle("2", f"{sinif}_teslim_son_bar_icinde", int(g["teslim_son_bar_icinde"].sum()))
        for saat, n in g["teslim_eksi_bitis_saat"].dropna().value_counts().sort_index().items():
            ekle("2", f"{sinif}_teslim_eksi_bitis_{saat:g}_saat", int(n))
        for yil, n in g["son_donem_bitis"].dt.year.value_counts().sort_index().items():
            ekle("2", f"{sinif}_donem_sonu_yili_{yil}", int(n))
        dolgusuz = g.loc[g["sonraki_dolgu_bar"] == 0, "sembol"]
        esik_alti = ozet.loc[ozet["sembol"].isin(dolgusuz) & (ozet["ne_donem_ne_dolgu_bar"] > 0), "sembol"]
        ekle("2", f"{sinif}_dolgusuz_gercek_islemle_biten", len(dolgusuz) - len(esik_alti))
        ekle("2", f"{sinif}_dolgusuz_esik_alti_sifirla_biten", ",".join(sorted(esik_alti)))
    trading = set(ozet["sembol"]) - set(delist["sembol"])
    son_bitis = ozet.set_index("sembol")["son_donem_bitis"]
    veri_sonu = son_bitis.max()
    ekle("2", "delist_olmayan_sembol", len(trading))
    ekle("2", "delist_olmayan_veri_sonunda_biten", int((son_bitis.loc[sorted(trading)] == veri_sonu).sum()))
    ekle("2", "veri_sonu_bari", str(veri_sonu))

    # §3 Dolgu barlari
    dolgu = t["dolgu_kosulari"]
    for konum in ("bas", "ic", "son"):
        g = dolgu.loc[dolgu["konum"] == konum]
        ekle("3", f"dolgu_{konum}_kosu", len(g))
        ekle("3", f"dolgu_{konum}_bar", int(g["bar_sayisi"].sum()))
        ekle("3", f"dolgu_{konum}_sembol", g["sembol"].nunique())
        ekle("3", f"dolgu_{konum}_medyan_gun", float(g["gun"].median()) if len(g) else float("nan"))
        ekle("3", f"dolgu_{konum}_en_uzun_gun", float(g["gun"].max()) if len(g) else float("nan"))
    ekle("3", "dolgu_toplam_kosu", len(dolgu))
    ekle("3", "dolgu_toplam_bar", int(dolgu["bar_sayisi"].sum()))
    ekle("3", "toplam_4h_bar", int(ozet["bar_4h"].sum()))
    ekle("3", "donem_ici_bar", int(ozet["donem_ici_bar"].sum()))
    ekle("3", "ne_donem_ne_dolgu_bar", int(ozet["ne_donem_ne_dolgu_bar"].sum()))
    ndd = ozet.loc[ozet["ne_donem_ne_dolgu_bar"] > 0]
    ekle("3", "ne_donem_ne_dolgu_semboller",
         ",".join(f"{r.sembol}:{r.ne_donem_ne_dolgu_bar}" for r in ndd.itertuples()))
    ekle("3", "kisa_sifir_kosusu", len(t["kisa_sifir_kosulari"]))

    # §4 Funding'siz donemler ve donem sonrasi funding
    fs = t["funding_siz_donemler"]
    ekle("4", "funding_siz_donem", len(fs))
    ekle("4", "funding_siz_donem_gercek_bar", int(fs["donem_gercek_bar_sayisi"].sum()) if len(fs) else 0)
    ekle("4", "funding_kayit_toplam", int(ozet["funding_kayit"].sum()))
    ekle("4", "funding_kayit_sembol", int((ozet["funding_kayit"] > 0).sum()))
    son_s = ozet.loc[ozet["funding_son_donem_sonrasi_atilan"] > 0]
    ekle("4", "atilan_son_donem_sonrasi_kayit", int(ozet["funding_son_donem_sonrasi_atilan"].sum()))
    ekle("4", "atilan_son_donem_sonrasi_sembol", len(son_s))
    sinif_haritasi = delist.set_index("sembol")["sinif"]
    for sinif, n in son_s["sembol"].map(sinif_haritasi).fillna("delist_degil").value_counts().sort_index().items():
        ekle("4", f"atilan_son_donem_sonrasi_sembol_{sinif}", int(n))
    ekle("4", "atilan_son_donem_sonrasi_8_saat_icinde_baslayan_kapanistan",
         int(np.sum(_gecikme_esik_icinde(son_s["funding_son_donem_sonrasi_ilk_gecikme_saat"]))))
    ekle("4", "atilan_son_donem_sonrasi_8_saat_icinde_baslayan_bitisten",
         int(np.sum(_gecikme_esik_icinde(son_s["funding_son_donem_sonrasi_ilk_gecikme_bitisten_saat"]))))
    ekle("4", "atilan_son_donem_sonrasi_bitisten_8_saati_asan_semboller",
         ",".join(sorted(son_s.loc[~_gecikme_esik_icinde(son_s["funding_son_donem_sonrasi_ilk_gecikme_bitisten_saat"]),
                                   "sembol"])))
    ekle("4", "atilan_donemler_arasi_kayit", int(ozet["funding_donemler_arasi_atilan"].sum()))
    ekle("4", "atilan_donemler_arasi_sembol", int((ozet["funding_donemler_arasi_atilan"] > 0).sum()))
    for a, g in aralar.groupby("ayirici"):
        ekle("4", f"atilan_donemler_arasi_kayit_{a}", int(g["atilan_funding"].sum()))
        ekle("4", f"atilan_donemler_arasi_sembol_{a}", int((g["atilan_funding"] > 0).sum()))
    ekle("4", "atilan_toplam_kayit", int(ozet["funding_donem_sonrasi_atilan"].sum()))
    ekle("4", "atilan_toplam_sembol", int((ozet["funding_donem_sonrasi_atilan"] > 0).sum()))
    ekle("4", "korunan_ilk_donem_oncesi_kayit", int(ozet["funding_ilk_donem_oncesi"].sum()))
    ekle("4", "korunan_ilk_donem_oncesi_sembol", int((ozet["funding_ilk_donem_oncesi"] > 0).sum()))

    # §5 Donem sonu degisimleri
    dg = t.get("donem_sonu_degisimleri")
    if dg is not None and "degisti" in dg:
        k = dg.dropna(subset=["bitis_kisalma_gun"])
        degisen = dg["degisti"].fillna(False).astype(bool)
        ekle("5", "karsilastirilan_sembol", len(k))
        ekle("5", "donemi_degisen_sembol", int(degisen.sum()))
        ekle("5", "yalniz_ic_siniri_degisen", int(dg["yalniz_ic_sinir"].fillna(False).astype(bool).sum()))
        ekle("5", "son_bitisi_erken", int((k["bitis_kisalma_gun"] > 0).sum()))
        ekle("5", "son_bitisi_gec", int((k["bitis_kisalma_gun"] < 0).sum()))
        ekle("5", "baslangici_degisen", int((k["baslangic_gecikme_gun"] != 0).sum()))
        ekle("5", "donem_sayisi_degisen", int((k["eski_donem_sayisi"] != k["yeni_donem_sayisi"]).sum()))
        ekle("5", "eski_toplam_donem", int(k["eski_donem_sayisi"].sum()))
        ekle("5", "yeni_toplam_donem", int(k["yeni_donem_sayisi"].sum()))
        ekle("5", "eski_ici_yeni_disi_bar", int(dg["eski_ici_yeni_disi_bar"].sum()))
        ekle("5", "yeni_ici_eski_disi_bar", int(dg["yeni_ici_eski_disi_bar"].sum()))
        kisalan = k.loc[k["bitis_kisalma_gun"] > 0, "bitis_kisalma_gun"]
        ekle("5", "kisalma_medyan_gun", float(kisalan.median()) if len(kisalan) else float("nan"))
        kovalar = [(0, 1), (1, 7), (7, 31), (31, 90), (90, 365), (365, 730), (730, float("inf"))]
        for alt, ust in kovalar:
            ekle("5", f"kisalma_{alt}_{ust}_gun", int(((kisalan > alt) & (kisalan <= ust)).sum()))

    # §6 SETTLED aylari
    st = t["settled_aylari"]
    ekle("6", "settled_ay", len(st))
    ekle("6", "settled_sembol", st["sembol"].nunique())
    for dv in (True, False):
        for sv in (True, False):
            ekle("6", f"settled_dolgu_{dv}_sinir_{sv}",
                 int(((st["dolgu_kosusu_var"] == dv) & (st["donem_siniri_var"] == sv)).sum()))
    si = t["settled_icerik"]
    if len(si):
        for etiket, g in (("donem_ici", si.loc[si["donem_icinde"]]), ("diger", si.loc[~si["donem_icinde"]])):
            ekle("6", f"settled_icerik_{etiket}_ay", len(g))
            for sutun in ("ortak_bar", "fiyat_farkli_bar", "hacim_farkli_bar", "yalniz_settled", "yalniz_ana"):
                ekle("6", f"settled_icerik_{etiket}_{sutun}", int(g[sutun].sum()))

    # §7 Kapsama ve bosluklar
    ekle("7", "eksik_bar", int(ozet["eksik_bar"].sum()))
    ekle("7", "gun_1d", int(ozet["gun_1d"].sum()))
    ekle("7", "bosluk_3bardan_uzun", len(t["bosluklar"]))
    ekle("7", "bosluk_olayi", len(t["bosluk_olaylari"]))
    ekle("7", "donem_bolen_bosluk", int(t["bosluklar"]["donem_bolen"].sum()) if len(t["bosluklar"]) else 0)

    # §8, §9
    sic = t["butunluk_sicramalari"]
    ekle("8", "sicrama", len(sic))
    for sinif, n in sic["sinif"].value_counts().sort_index().items():
        ekle("8", f"sicrama_{sinif}", int(n))
    ekle("9", "kisa_donem", len(t["kisa_donemler"]))

    # Rev.8'de duzeltilecek uc sayi. Her kalem on-kayittaki cumlenin harfiyen
    # tanimindan uretilir; cumleler RESULTS §14.1'de alintili (D-A3, D-B2).
    st_r = t["settled_aylari"]
    # "34 karantina ayinin 14'unde ... dolgu kosusu bulunmayan" (§2 rev.7)
    ekle("rev8", "settled_ay (on-kayit: 34)", len(st_r))
    ekle("rev8", "settled_ayinda_dolgu_kosusu_yok (on-kayit: 14)",
         int((~st_r["dolgu_kosusu_var"]).sum()))
    # §6'daki 13 dolgu VE donem siniri yoklugudur; aradaki fark bu aylardir.
    fark = st_r.loc[~st_r["dolgu_kosusu_var"] & st_r["donem_siniri_var"]]
    ekle("rev8", "settled_ayinda_dolgu_yok_donem_siniri_var", len(fark))
    ekle("rev8", "settled_ayinda_dolgu_yok_donem_siniri_var_aylar",
         ",".join(f"{r.sembol}:{r.ay}" for r in fark.sort_values(["sembol", "ay"]).itertuples()))
    # "131 sembolde uzlasma sonrasi dolgu barlarin donem sonunu yillarca
    # uzattigi" (Revizyon Gunlugu, rev.7). Cekirdek tanim: donem sonundan sonra
    # dolgu barlari olan delist sembol. "Yillarca" ayrica 1 ve 2 yil esigiyle.
    ekle("rev8", "uzlasma_sonrasi_dolgusu_olan_sembol (on-kayit: 131)",
         int((delist["sonraki_dolgu_bar"] > 0).sum()))
    son_dolgu = t["dolgu_kosulari"].loc[t["dolgu_kosulari"]["konum"] == "son"]
    for yil in (1, 2):
        ekle("rev8", f"uzlasma_sonrasi_dolgusu_en_az_{yil}_yil_olan_sembol",
             son_dolgu.loc[son_dolgu["gun"] >= 365 * yil, "sembol"].nunique())
    # "38 sembolde uzlasma sonrasinda da funding kaydi yayinlandigini" (§2 rev.7).
    # Tanim kapanis referanslidir: son donemin KAPANISINDAN (son barin kapanisi
    # + 1 dk) sonra en az bir kaydi olan sembol. exchangeInfo disi sembollerde
    # uzlasma ani (deliveryDate) yoktur; kapanis tum delist sembollerde tanimli
    # tek referanstir.
    ekle("rev8", "uzlasma_sonrasi_funding_yayinlanan_sembol_kapanistan_sonra (on-kayit: 38)",
         int((ozet["funding_son_donem_sonrasi_atilan"] > 0).sum()))
    for sinif, n in son_s["sembol"].map(sinif_haritasi).fillna("delist_degil").value_counts().sort_index().items():
        ekle("rev8", f"uzlasma_sonrasi_funding_yayinlanan_sembol_kapanistan_sonra_{sinif}", int(n))
    stl = delist.loc[delist["sinif"] == universe_modulu.SETTLING_DURUMU]
    if "teslimden_sonra_funding_kayit" in stl:
        ekle("rev8", "SETTLING_teslimden_sonra_funding_kaydi_olan_sembol",
             int((stl["teslimden_sonra_funding_kayit"] > 0).sum()))

    # §14.8 1 gunluk barlarin donem sinirlari (denetci bulgusu D-A1). Yalnizca
    # zaman damgasi sayimi; fiyat, hacim degeri ya da getiri yok.
    gs = t.get("gunluk_sinirlar")
    if gs is not None and len(gs):
        ic_turler = ("dolgu_kosusu", "uzun_bosluk")
        for tur, g in gs.groupby("son_turu"):
            ekle("14.8", f"donem_sonu_{tur}", len(g))
            ekle("14.8", f"son_gun_donem_disi_bar_iceren_{tur}", int((g["son_gun_donem_disi_bar"] > 0).sum()))
            ekle("14.8", f"son_gun_donem_disi_bar_toplam_{tur}", int(g["son_gun_donem_disi_bar"].sum()))
            ekle("14.8", f"bitis_gunu_1d_serisinde_yok_{tur}", int((~g["bitis_gunu_1d_serisinde"]).sum()))
        for tur, g in gs.groupby("bas_turu"):
            ekle("14.8", f"donem_basi_{tur}", len(g))
            ekle("14.8", f"ilk_gun_donem_disi_bar_iceren_{tur}", int((g["ilk_gun_donem_disi_bar"] > 0).sum()))
        # Bugunku 1 gunluk seride olup 6'dan az donem ici 4 saatlik bar iceren gunler.
        bas_kismi = gs["bas_gunu_1d_serisinde"] & (gs["bas_gunu_donem_ici_bar"] < 6)
        son_kismi = gs["bitis_gunu_1d_serisinde"] & (gs["bitis_gunu_donem_ici_bar"] < 6)
        ic_son = gs["son_turu"].isin(ic_turler)
        ekle("14.8", "kismi_gun_donem_basi", int((bas_kismi & (gs["bas_turu"] == "donem_basi")).sum()))
        ekle("14.8", "kismi_gun_ic_sinir_bas", int((bas_kismi & (gs["bas_turu"] == "ic_sinir")).sum()))
        ekle("14.8", "kismi_gun_ic_sinir_son", int((son_kismi & ic_son).sum()))
        ekle("14.8", "kismi_gun_donem_sonu", int((son_kismi & ~ic_son).sum()))
        # Rev.8 1d serisinden cikan gunler (eski kural: 6 satirli her gun), yere gore.
        for tur in CIKAN_GUN_TURLERI:
            sutun = f"gun_1d_cikan_{tur}"
            if sutun in ozet:
                ekle("14.8", f"rev8_1d_cikan_gun_{tur}", int(ozet[sutun].sum()))
        # Ayni gunde baslayip biten donem varsa o gun iki kez sayilmis olur.
        ekle("14.8", "ayni_gunde_baslayan_ve_biten_donem", int((gs["bas_gunu"] == gs["bitis_gunu"]).sum()))

    # §12 capraz
    cr = t["cross_dogrulama"]
    for anahtar in ("toplam_gun", "fiyat_gun", "hacim_gun"):
        ekle("12", f"capraz_{anahtar}", cr.attrs.get(anahtar))

    return pd.DataFrame(s, columns=["bolum", "kalem", "deger"])


# --- Ana akis ----------------------------------------------------------------


def main() -> None:
    ayristirici = argparse.ArgumentParser()
    ayristirici.add_argument("--ornek", action="store_true", help="30 sembollu ornek kume")
    ayristirici.add_argument("--is-parcaci", type=int, default=6,
                             help="es zamanli indirme parcacigi (sinirli tutulur)")
    ayristirici.add_argument(
        "--eski-evren", nargs="?", const=ESKI_EVREN_REF, default=None, metavar="GIT_REF:YOL",
        help="istege bagli: rev.7 oncesi evren tablosuyla donem sonu karsilastirmasi "
             f"(varsayilan ref {ESKI_EVREN_REF}); git gecmisi gerektirir",
    )
    argumanlar = ayristirici.parse_args()
    # Kosu kilidi (sizinti testcisi bulgusu): ikinci kosu hicbir sey yazmadan reddedilir.
    with kosu_kilidi("calistir"):
        _kos(argumanlar)


def _kos(argumanlar: argparse.Namespace) -> None:
    # Calisma agaci durumu ve baslangic zamani HER SEYDEN ONCE (D-B2).
    baslangic = pd.Timestamp.now(tz="UTC")
    git = git_durumu()

    etiket = "ornek" if argumanlar.ornek else "tam"
    log_yolu = _kaydedici_kur(etiket)
    _gunluk.info(f"git: {git['commit']}, calisma agaci "
                 f"{'temiz' if not git['degisiklikler'] else 'kirli: ' + ' | '.join(git['degisiklikler'])}")

    # Istege bagli eski tablo karsilastirmasi (denetci bulgusu D-B1): git gecmisi
    # gerektirdigi icin varsayilan kosunun parcasi degil. Istenirse YUKLEMEDEN ONCE
    # okunur; git yoksa ya da ref cozulemezse kosu hicbir sey yazmadan durur.
    eski_evren = None
    if argumanlar.eski_evren:
        try:
            eski_evren = eski_evreni_oku(argumanlar.eski_evren)
        except (OSError, subprocess.CalledProcessError) as hata:
            _gunluk.error(f"eski evren tablosu okunamadi ({argumanlar.eski_evren}): {hata}. "
                          f"Kosu durduruldu, hicbir cikti yazilmadi.")
            raise SystemExit(2) from hata
        _gunluk.info(f"eski evren tablosu: {argumanlar.eski_evren} ({len(eski_evren)} satir)")

    evren = universe_modulu.evren_yukle()
    semboller = (
        list(ORNEK_SEMBOLLER) if argumanlar.ornek else universe_modulu.dahil_semboller(evren)
    )

    _gunluk.info(f"[{etiket}] {len(semboller)} sembol, {argumanlar.is_parcaci} is parcacigi")
    _gunluk.info(f"log: {log_yolu}")

    detaylar: list[dict] = []
    hatalar: list[tuple[str, str]] = []
    tamam = 0

    with ThreadPoolExecutor(max_workers=argumanlar.is_parcaci) as havuz:
        isler = {havuz.submit(sembol_denetle, s, evren): s for s in semboller}
        for is_ in as_completed(isler):
            sembol = isler[is_]
            try:
                sonuc = is_.result()
            except Exception as hata:
                with _kilit:
                    hatalar.append((sembol, f"{type(hata).__name__}: {hata}"))
                    tamam += 1
                    _gunluk.error(f"  {tamam}/{len(semboller)} {sembol} HATA: {hata}")
                continue
            with _kilit:
                detaylar.append(sonuc)
                tamam += 1
                if tamam % 25 == 0 or tamam == len(semboller):
                    _gunluk.info(f"  {tamam}/{len(semboller)} tamam (son: {sembol})")

    # Tamamlanma sirasi is parcaciklarina baglidir; ciktilar sembole gore
    # siralanir (tekrarlanabilirlik, denetci bulgusu D-B5).
    detaylar.sort(key=lambda d: d["sembol"])
    hatalar.sort()
    _gunluk.info(f"yukleme bitti. basarili: {len(detaylar)}, hatali: {len(hatalar)}")

    # Tum tablolar once bellekte hesaplanir, en sonda birlikte yazilir: hesap
    # sirasinda hata cikarsa dizinde iki kosunun ciktilari karismaz (D-B1).
    ciktilar: dict[str, pd.DataFrame] = {}

    def yaz(tablo: pd.DataFrame, ad: str) -> None:
        ciktilar[ad] = tablo

    # --- Ciktilar
    ozet = pd.DataFrame([{k: v for k, v in d.items() if not k.startswith("_")} for d in detaylar])
    yaz(ozet, "sembol_ozeti")

    delist = delist_tablosu(evren, detaylar)
    yaz(delist, "delist_siniflandirmasi")
    gunluk_sinir = gunluk_sinir_tablosu(detaylar, delist)
    yaz(gunluk_sinir, "gunluk_sinirlar")
    dolgu = dolgu_tablosu(detaylar)
    yaz(dolgu, "dolgu_kosulari")
    kisa_sifir = kisa_sifir_tablosu(detaylar)
    yaz(kisa_sifir, "kisa_sifir_kosulari")
    fundingsiz = funding_siz_donemler(evren.loc[evren["sembol"].isin(semboller)])
    yaz(fundingsiz, "funding_siz_donemler")
    degisim = donem_sonu_degisimleri(eski_evren, detaylar) if eski_evren is not None else pd.DataFrame()
    if eski_evren is not None:
        yaz(degisim, "donem_sonu_degisimleri")
    settled = settled_karsilastirma(detaylar)
    yaz(settled, "settled_aylari")
    settled_ic = settled_icerik(detaylar, bv.tum_sembol_dizinleri(), settled)
    yaz(settled_ic, "settled_icerik")

    yaz(yillik_kapsama(detaylar, evren), "yillik_kapsama")
    sicramalar = sicramalari_grupla(detaylar)
    yaz(sicramalar, "butunluk_sicramalari")
    bosluklar, bosluk_olaylari = bosluklari_grupla(detaylar)
    yaz(bosluklar, "bosluklar")
    yaz(bosluk_olaylari, "bosluk_olaylari")
    yaz(funding_dagilimi(detaylar), "funding_araliklari")
    capraz, yogun = capraz_ozet(detaylar)
    yaz(capraz, "cross_dogrulama")
    yaz(yogun, "cross_yogun_tarihler")
    fiyat_yasi = fiyat_farki_listeleme_yasi(detaylar)
    yaz(fiyat_yasi, "fiyat_farki_listeleme_yasi")
    kisa = kisa_donemler(detaylar)
    yaz(kisa, "kisa_donemler")
    aralar = donem_aralari_tablosu(detaylar)
    yaz(aralar, "donem_aralari")
    from data import split as split_modulu

    tablolar = {
        "sembol_ozeti": ozet, "delist_siniflandirmasi": delist, "dolgu_kosulari": dolgu,
        "kisa_sifir_kosulari": kisa_sifir, "funding_siz_donemler": fundingsiz,
        "donem_sonu_degisimleri": degisim, "settled_aylari": settled, "settled_icerik": settled_ic,
        "butunluk_sicramalari": sicramalar, "bosluklar": bosluklar, "bosluk_olaylari": bosluk_olaylari,
        "cross_dogrulama": capraz, "kisa_donemler": kisa, "donem_aralari": aralar,
        "gunluk_sinirlar": gunluk_sinir,
    }
    yaz(rapor_sayilari(tablolar, evren, split_modulu.split_oku()), "rapor_sayilari")
    yaz(ortam_kaydi(git, baslangic, pd.Timestamp.now(tz="UTC")), "ortam")

    if hatalar:
        yaz(pd.DataFrame(hatalar, columns=["sembol", "hata"]), "hatalar")

    for ad, tablo in ciktilar.items():
        csv_yaz(tablo, CIKTI_DIZINI / f"{ad}_{etiket}.csv")
    # Bu kosuda uretilmeyen karsilastirma ciktisi onceki kosudan kalmasin.
    for ad in ("donem_sonu_degisimleri", "hatalar"):
        eski_dosya = CIKTI_DIZINI / f"{ad}_{etiket}.csv"
        if ad not in ciktilar and eski_dosya.exists():
            eski_dosya.unlink()
            _gunluk.info(f"onceki kosudan kalan {eski_dosya.name} silindi (bu kosuda uretilmedi)")

    _gunluk.info("--- OZET ---")
    _gunluk.info(f"toplam 4h bar       : {int(ozet['bar_4h'].sum())}")
    _gunluk.info(f"donem ici bar       : {int(ozet['donem_ici_bar'].sum())}")
    _gunluk.info(f"dolgu bar           : {int(ozet['dolgu_bar'].sum())} ({len(dolgu)} kosu)")
    _gunluk.info(f"kisa sifir kosusu   : {len(kisa_sifir)}")
    _gunluk.info(f"donem tutarsizligi  : {int((~ozet['donemler_yeniden_turetimle_ayni']).sum())}")
    _gunluk.info(f"delist siniflari    : {delist.attrs['durum_sayimi']}")
    _gunluk.info(f"teslim son barda    : {int(delist['teslim_son_bar_icinde'].sum())}")
    _gunluk.info(f"funding'siz donem   : {len(fundingsiz)}")
    if "degisti" in degisim:
        dg = degisim.loc[degisim["degisti"].fillna(False).astype(bool)]
        _gunluk.info(f"donem degisen sembol: {len(dg)} (yalniz ic sinir {int(dg['yalniz_ic_sinir'].sum())}), "
                     f"eski ici yeni disi bar {int(dg['eski_ici_yeni_disi_bar'].sum())}, "
                     f"yeni ici eski disi bar {int(dg['yeni_ici_eski_disi_bar'].sum())}")
    if len(settled_ic):
        ic = settled_ic.loc[settled_ic["donem_icinde"]]
        _gunluk.info(f"SETTLED donem ici ay: {len(ic)}, ortak bar {int(ic['ortak_bar'].sum())}, "
                     f"fiyat farkli {int(ic['fiyat_farkli_bar'].sum())}, hacim farkli {int(ic['hacim_farkli_bar'].sum())}, "
                     f"yalniz settled {int(ic['yalniz_settled'].sum())}, yalniz ana {int(ic['yalniz_ana'].sum())}")
    _gunluk.info(f"sicrama             : {len(sicramalar)} {sicramalar['sinif'].value_counts().to_dict()}")
    _gunluk.info(f"bosluk              : {len(bosluklar)} adet, {len(bosluk_olaylari)} olay")
    _gunluk.info(f"60 gunden kisa donem: {len(kisa)}")
    _gunluk.info(f"capraz gun          : {capraz.attrs['toplam_gun']}, "
                 f"fiyat farkli {capraz.attrs['fiyat_gun']}, hacim farkli {capraz.attrs['hacim_gun']}")
    _gunluk.info(f"CSV ciktilari: {CIKTI_DIZINI}")


if __name__ == "__main__":
    try:
        # F1 veri denetimi butun gecmisi olcer (anayasa §3.1): onay verisi izniyle (kapanisin son turu).
        from data import binance_vision as _bv

        with _bv.onay_verisi_izni("F1 veri denetimi: " + Path(__file__).name):
            main()
    except KosuKilidiHatasi as hata:
        raise SystemExit(f"HATA: {hata}") from None
