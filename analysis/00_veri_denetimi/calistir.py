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
from data import donem as donem_modulu  # noqa: E402
from data import eligibility as uyg  # noqa: E402
from data import funding as funding_modulu  # noqa: E402
from data import klines as klines_modulu  # noqa: E402
from data import universe as universe_modulu  # noqa: E402

CIKTI_DIZINI = Path(__file__).resolve().parent

# Rev.7 oncesi (ay duzeyi, karantinali) evren tablosunun son hali. Donem sonu
# degisimlerinin ozeti bununla karsilastirilir; sabit commit, tekrarlanabilir.
ESKI_EVREN_REF = "a66a5e0:data/universe.csv"

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


def _toplam_doneme_kes(cerceve: pd.DataFrame, sutun: str) -> pd.DataFrame:
    """Toplam donem (on-kayit §2) disindaki kayitlari atar; bucket'a sonradan eklenen
    aylar denetimi degistirmesin."""
    if cerceve.empty:
        return cerceve
    maske = (cerceve[sutun] >= config.DONEM_BASI) & (cerceve[sutun] <= config.DONEM_SONU)
    return cerceve.loc[maske].reset_index(drop=True)


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
    if donemler and not fund.empty:
        ilk_oncesi = int((fund["odeme_zamani"] < donemler[0].baslangic - funding_modulu.ODEME_TOLERANSI).sum())

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
        "funding_ilk_donem_oncesi": ilk_oncesi,
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


def donem_sonu_degisimleri(eski: pd.DataFrame, detaylar: list[dict]) -> pd.DataFrame:
    """Sembol basina eski (ay duzeyi, karantinali) ile yeni (bar duzeyi) donem sinirlari.

    Eski son sinir = eski son donemin son ayindaki son 4h bar, serinin son barina
    kirpilmis. Eski karantina aylari donemleri boldugu icin donem sayisi da
    karsilastirilir. Pozitif `bitis_kisalma_gun`, yeni donemin daha erken bittigidir.
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
            satir.update({
                "eski_ilk_baslangic": eski_bas, "yeni_ilk_baslangic": yeni[0].baslangic,
                "eski_son_bitis": eski_son, "yeni_son_bitis": yeni[-1].bitis,
                "baslangic_gecikme_gun": round((yeni[0].baslangic - eski_bas) / pd.Timedelta(days=1), 2),
                "bitis_kisalma_gun": round((eski_son - yeni[-1].bitis) / pd.Timedelta(days=1), 2),
                "eski_karantina_aylari": str(g["karantina_aylari"].iloc[0]),
            })
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


# --- Toplu olcumler ----------------------------------------------------------


def yillik_kapsama(detaylar: list[dict], evren: pd.DataFrame) -> pd.DataFrame:
    """Yillara gore: veri bulunan sembol, 10M ve 2M esigini en az bir barda gecen.

    Uygunluk rev.7 donemleriyle olculur; funding'siz donemler (hic kullanilmaz)
    sayilmaz.
    """
    funding_yok = {
        (r.sembol, int(r.donem_id))
        for r in evren.loc[evren["donem_funding_yok"] & (evren["donem_id"] >= 0)].itertuples()
    }
    satirlar = []
    for yil in range(config.DONEM_BASI.year, config.DONEM_SONU.year + 1):
        bas = pd.Timestamp(f"{yil}-01-01", tz="UTC")
        son = pd.Timestamp(f"{yil}-12-31 23:59:59", tz="UTC")
        veri_var = esik_10m = esik_2m = 0

        for d in detaylar:
            gunluk = d["_gunluk"]
            donemler = d["_donemler"]
            mm = d["_mumlar"]
            if mm.empty or not donemler:
                continue
            yil_ici = mm.loc[(mm["open_time"] >= bas) & (mm["open_time"] <= son), "open_time"]
            if yil_ici.empty:
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
            {"yil": yil, "veri_bulunan_sembol": veri_var,
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

    def veri_olan(bas, son) -> int:
        n = 0
        for d in detaylar:
            mm = d["_mumlar"]
            if not mm.empty and mm["open_time"].iloc[0] <= son and bas <= mm["open_time"].iloc[-1]:
                n += 1
        return n

    olaylar = []
    for kimlik, bas, son in sinirlar:
        parca = tablo.loc[tablo["olay_id"] == kimlik]
        etki = parca["sembol"].nunique()
        kapsam = veri_olan(bas, son)
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


def ortam_kaydi() -> pd.DataFrame:
    """Kosuyu ureten ortam: Python, paket surumleri ve git commit'i."""
    import importlib.metadata as md
    import platform

    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=KOK, capture_output=True, text=True).stdout.strip()
    kirli = subprocess.run(["git", "status", "--porcelain"], cwd=KOK, capture_output=True, text=True).stdout.strip()
    satirlar = [
        {"bilesen": "git_commit", "surum": commit + (" (calisma agaci kirli)" if kirli else "")},
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


# --- Ana akis ----------------------------------------------------------------


def main() -> None:
    ayristirici = argparse.ArgumentParser()
    ayristirici.add_argument("--ornek", action="store_true", help="30 sembollu ornek kume")
    ayristirici.add_argument("--is-parcaci", type=int, default=6,
                             help="es zamanli indirme parcacigi (sinirli tutulur)")
    argumanlar = ayristirici.parse_args()

    etiket = "ornek" if argumanlar.ornek else "tam"
    log_yolu = _kaydedici_kur(etiket)

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

    detaylar.sort(key=lambda d: d["sembol"])
    _gunluk.info(f"yukleme bitti. basarili: {len(detaylar)}, hatali: {len(hatalar)}")

    def yaz(tablo: pd.DataFrame, ad: str) -> None:
        tablo.to_csv(CIKTI_DIZINI / f"{ad}_{etiket}.csv", index=False, lineterminator="\n")

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
    degisim = donem_sonu_degisimleri(eski_evreni_oku(), detaylar)
    yaz(degisim, "donem_sonu_degisimleri")
    settled = settled_karsilastirma(detaylar)
    yaz(settled, "settled_aylari")

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
    yaz(ortam_kaydi(), "ortam")

    if hatalar:
        yaz(pd.DataFrame(hatalar, columns=["sembol", "hata"]), "hatalar")

    _gunluk.info("--- OZET ---")
    _gunluk.info(f"toplam 4h bar       : {int(ozet['bar_4h'].sum())}")
    _gunluk.info(f"donem ici bar       : {int(ozet['donem_ici_bar'].sum())}")
    _gunluk.info(f"dolgu bar           : {int(ozet['dolgu_bar'].sum())} ({len(dolgu)} kosu)")
    _gunluk.info(f"kisa sifir kosusu   : {len(kisa_sifir)}")
    _gunluk.info(f"donem tutarsizligi  : {int((~ozet['donemler_yeniden_turetimle_ayni']).sum())}")
    _gunluk.info(f"delist siniflari    : {delist.attrs['durum_sayimi']}")
    _gunluk.info(f"teslim son barda    : {int(delist['teslim_son_bar_icinde'].sum())}")
    _gunluk.info(f"funding'siz donem   : {len(fundingsiz)}")
    _gunluk.info(f"sicrama             : {len(sicramalar)} {sicramalar['sinif'].value_counts().to_dict()}")
    _gunluk.info(f"bosluk              : {len(bosluklar)} adet, {len(bosluk_olaylari)} olay")
    _gunluk.info(f"60 gunden kisa donem: {len(kisa)}")
    _gunluk.info(f"capraz gun          : {capraz.attrs['toplam_gun']}, "
                 f"fiyat farkli {capraz.attrs['fiyat_gun']}, hacim farkli {capraz.attrs['hacim_gun']}")
    _gunluk.info(f"CSV ciktilari: {CIKTI_DIZINI}")


if __name__ == "__main__":
    main()
