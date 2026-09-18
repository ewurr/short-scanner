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
import io
import logging
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

KOK = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KOK))

import config  # noqa: E402
from data import binance_vision as bv  # noqa: E402
from data import donem as donem_modulu  # noqa: E402
from data import eligibility as uyg  # noqa: E402
from data import funding as funding_modulu  # noqa: E402
from data import klines as klines_modulu  # noqa: E402
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


# --- Sembol basina olcum -----------------------------------------------------


def sembol_denetle(sembol: str, evren: pd.DataFrame) -> dict:
    """Tek sembolun kapsama, donem ve butunluk olcumleri. Getiri hesaplamaz."""
    # F1 kapsama denetimi TUM gecmisi (B grubu ve C2 dahil) olcer ve getiri
    # hesaplamaz (CLAUDE.md §3.1); bu yuzden kume korumasiz ham yukleyiciler
    # bilerek kullanilir. Analiz ve olay kodu bunlari cagirmaz.
    mumlar = _toplam_doneme_kes(klines_modulu.ham_mumlari_yukle(sembol, config.BAR_4H), "open_time")
    gunluk = klines_modulu.gunluge_cevir(mumlar)
    fund = _toplam_doneme_kes(funding_modulu.ham_funding_yukle(sembol), "odeme_zamani")

    donemler = universe_modulu.sembol_donemleri(evren, sembol)
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
    ilk_gecikme_saat = float("nan")
    aralar = []
    if donemler and not fund.empty:
        tol = funding_modulu.ODEME_TOLERANSI
        ilk_oncesi = int((fund["odeme_zamani"] < donemler[0].baslangic - tol).sum())
        # Atilan kayitlarin ayrimi (denetci bulgusu D-A5): son donemden sonra ve
        # iki donem arasinda. Ust sinir `_donem_icinde` ile ayni: son bar kapanisi + 1 dk.
        atilan = fund.loc[~fund["odeme_zamani"].isin(kalan["odeme_zamani"]), "odeme_zamani"]
        son_ust = donemler[-1].bitis + ADIM_4H + tol
        son_sonrasi = int((atilan >= son_ust).sum())
        arada = len(atilan) - son_sonrasi
        if son_sonrasi:
            ilk_gecikme_saat = (atilan.loc[atilan >= son_ust].min() - (donemler[-1].bitis + ADIM_4H)) / pd.Timedelta(hours=1)
        for onceki, sonraki in zip(donemler[:-1], donemler[1:]):
            ic_dolgu = any(k.konum == "ic" and onceki.bitis < k.baslangic < sonraki.baslangic for k in dolgu)
            aralar.append({
                "sembol": sembol, "onceki_bitis": onceki.bitis, "sonraki_baslangic": sonraki.baslangic,
                "ayirici": "dolgu_kosusu" if ic_dolgu else "eksik_bar_boslugu",
                "atilan_funding": int(((atilan >= onceki.bitis + ADIM_4H + tol) & (atilan < sonraki.baslangic - tol)).sum()),
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
    tablo["seri_son_bar"] = tablo["sembol"].map(son_bar)
    tablo["sonraki_dolgu_bar"] = tablo["sembol"].map(son_dolgu)
    tablo["teslim_eksi_bitis_saat"] = (tablo["deliveryDate"] - tablo["son_donem_bitis"]) / pd.Timedelta(hours=1)
    tablo["teslim_son_bar_icinde"] = (
        (tablo["son_donem_bitis"] <= tablo["deliveryDate"])
        & (tablo["deliveryDate"] < tablo["son_donem_bitis"] + ADIM_4H)
    )
    tablo.attrs["alinma_zamani_utc"] = anlik.attrs["alinma_zamani_utc"]
    tablo.attrs["durum_sayimi"] = sinif["sinif"].value_counts().to_dict()
    return tablo.reset_index(drop=True)


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
                if not iki_m and uyg.uygun_mu(hacim, t, config.BAR_1D, **sinirlar):
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
            gun = (x.bitis + ADIM_4H - x.baslangic) / pd.Timedelta(days=1)
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
    ekle("4", "atilan_son_donem_sonrasi_8_saat_icinde_baslayan",
         int((son_s["funding_son_donem_sonrasi_ilk_gecikme_saat"] <= 8 + 1 / 60).sum()))
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
    }
    yaz(rapor_sayilari(tablolar, evren, split_modulu.split_oku()), "rapor_sayilari")
    yaz(ortam_kaydi(git, baslangic, pd.Timestamp.now(tz="UTC")), "ortam")

    if hatalar:
        yaz(pd.DataFrame(hatalar, columns=["sembol", "hata"]), "hatalar")

    for ad, tablo in ciktilar.items():
        tablo.to_csv(CIKTI_DIZINI / f"{ad}_{etiket}.csv", index=False, lineterminator="\n")
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
    main()
