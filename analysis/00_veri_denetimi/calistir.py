"""F1 veri denetimi (on-kayit §2 ve rev.2, CLAUDE.md §3.1).

Yalnizca KAPSAMA ve BUTUNLUK olcer. Getiri, fiyat degisimi, volatilite, funding
ortalamasi veya olay benzeri hicbir istatistik hesaplamaz ya da yazdirmaz.

Kullanim:
    python analysis/00_veri_denetimi/calistir.py --ornek       # 30 sembollu ornek
    python analysis/00_veri_denetimi/calistir.py --is-parcaci 6  # tam evren
"""

from __future__ import annotations

import argparse
import collections
import logging
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

# Ornek kume (F1 plani): >=5 delist, >=5 basliksiz 2020 dosyasi, >=5 4h funding,
# >=3 karantinali (TLMUSDT ve BNXUSDT dahil), MATICUSDT ve POLUSDT.
ORNEK_SEMBOLLER = [
    "SRMUSDT", "HNTUSDT", "MATICUSDT", "EOSUSDT", "GALUSDT", "RNDRUSDT", "BTSUSDT",
    "BTCUSDT", "ETHUSDT", "ADAUSDT", "LINKUSDT", "XRPUSDT", "BCHUSDT", "LTCUSDT",
    "WIFUSDT", "ORDIUSDT", "MYXUSDT", "AVNTUSDT", "ASTERUSDT",
    "TLMUSDT", "BNXUSDT", "MINAUSDT", "CTKUSDT", "LITUSDT", "AERGOUSDT",
    "POLUSDT", "RENDERUSDT", "AUSDT",
    "SOLUSDT", "GUSDT",
]

FIYAT_SUTUNLARI = ["open", "high", "low", "close"]
HACIM_SUTUNLARI = ["volume", "quote_volume"]

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


# --- Sembol basina olcum -----------------------------------------------------


def sembol_denetle(sembol: str, evren: pd.DataFrame) -> dict:
    """Tek sembolun kapsama ve butunluk olcumleri. Getiri hesaplamaz."""
    mumlar = klines_modulu.mumlari_yukle(sembol, config.BAR_4H)
    gunluk = klines_modulu.gunluge_cevir(mumlar)
    fund = funding_modulu.funding_yukle(sembol)

    karantina = universe_modulu.karantina_listesi(evren, sembol)
    donemler = universe_modulu.sembol_donemleri(evren, sembol)

    bosluklar = klines_modulu.eksik_barlar(mumlar, config.BAR_4H)
    uzun_bosluk = bosluklar.loc[bosluklar["eksik_bar"] > 3] if not bosluklar.empty else bosluklar

    beklenen = 0
    if not mumlar.empty:
        izgara = pd.date_range(
            mumlar["open_time"].iloc[0], mumlar["open_time"].iloc[-1], freq=pd.Timedelta(hours=4)
        )
        beklenen = len(izgara)

    sicramalar = klines_modulu.butunluk_sicramalari(mumlar)
    kapsama = funding_modulu.kapsama(fund, mumlar)
    aralik = funding_modulu.aralik_ozeti(fund)
    sekiz_disi = aralik.loc[aralik["aralik_saat"] != 8] if not aralik.empty else aralik

    # 1d capraz dogrulama
    capraz = {"durum": "yapilmadi"}
    try:
        birincil = klines_modulu.birincil_gunluk_indir(sembol)
        if not gunluk.empty and not birincil.empty:
            fark = klines_modulu.cross_dogrula(gunluk, birincil)
            fs = [f"{c}_bagil_fark" for c in FIYAT_SUTUNLARI]
            hs = [f"{c}_bagil_fark" for c in HACIM_SUTUNLARI]
            capraz = {
                "durum": "karsilastirildi",
                "ortak_gun": len(fark),
                "fiyat_farkli_gun": int((fark[fs] > 1e-6).any(axis=1).sum()),
                "hacim_farkli_gun": int((fark[hs] > 1e-6).any(axis=1).sum()),
                "yalniz_birincil": fark.attrs.get("yalniz_birincil"),
                "_fiyat_tarihleri": [
                    str(t.date()) for t in fark.loc[(fark[fs] > 1e-6).any(axis=1), "open_time"]
                ],
                "_hacim_tarihleri": [
                    str(t.date()) for t in fark.loc[(fark[hs] > 1e-6).any(axis=1), "open_time"]
                ],
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
        "karantina_ay_sayisi": len(karantina),
        "karantina_aylari": ",".join(karantina),
        "donem_sayisi": len(donemler),
        "funding_kayit": len(fund),
        "funding_var": kapsama["funding_var"],
        "funding_ortusme": kapsama["ortusme_var"],
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
        "_sicramalar": sicramalar,
        "_uzun_bosluk": uzun_bosluk,
        "_aralik": aralik,
        "_capraz": capraz,
    }


# --- Toplu olcumler ----------------------------------------------------------


def yillik_kapsama(detaylar: list[dict], evren: pd.DataFrame) -> pd.DataFrame:
    """Yillara gore: veri bulunan sembol, 10M ve 2M esigini en az bir gun gecen."""
    satirlar = []
    for yil in range(2020, 2027):
        bas = pd.Timestamp(f"{yil}-01-01", tz="UTC")
        son = pd.Timestamp(f"{yil}-12-31 23:59:59", tz="UTC")
        veri_var = esik_10m = esik_2m = 0

        for d in detaylar:
            gunluk = d["_gunluk"]
            if gunluk.empty:
                continue
            yil_ici = gunluk.loc[(gunluk["open_time"] >= bas) & (gunluk["open_time"] <= son)]
            if yil_ici.empty:
                continue
            veri_var += 1

            hacim = uyg.gunluk_hacim_serisi(gunluk)
            karantina = universe_modulu.karantina_listesi(evren, d["sembol"])
            donemler = universe_modulu.sembol_donemleri(evren, d["sembol"])
            if not donemler:
                continue

            on_m = iki_m = False
            for t in yil_ici["open_time"]:
                kimlik = donem_modulu.donem_bul(t, donemler)
                if kimlik is None:
                    continue
                d_bas = donemler[kimlik][0].to_timestamp(how="start").tz_localize("UTC")
                d_son = donemler[kimlik][1].to_timestamp(how="end").tz_localize("UTC")
                if not on_m and uyg.uygun_mu(hacim, d_bas, t, config.BAR_4H, karantina, d_son):
                    on_m = True
                if not iki_m and uyg.uygun_mu(hacim, d_bas, t, config.BAR_1D, karantina, d_son):
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


def bosluklari_grupla(detaylar: list[dict]) -> pd.DataFrame:
    """Bar bosluklarini borsa geneli / sembole ozgu diye ayirir.

    Borsa geneli: ayni baslangic-bitis araligi, o tarihte verisi olan sembollerin
    en az YARISINI etkiliyorsa.
    """
    satirlar = []
    for d in detaylar:
        b = d["_uzun_bosluk"]
        if b.empty:
            continue
        for _, r in b.iterrows():
            satirlar.append(
                {"sembol": d["sembol"], "bas": r["bas"], "son": r["son"],
                 "eksik_bar": int(r["eksik_bar"])}
            )
    if not satirlar:
        return pd.DataFrame(columns=["sembol", "bas", "son", "eksik_bar", "etki_sembol",
                                     "o_tarihte_veri_olan", "borsa_geneli"])
    tablo = pd.DataFrame(satirlar)

    # Ayni (bas, son) ciftini kac sembol yasadi?
    etki = tablo.groupby(["bas", "son"]).size().rename("etki_sembol")
    tablo = tablo.merge(etki, on=["bas", "son"])

    # O tarihte verisi olan sembol sayisi
    def veri_olan(t) -> int:
        n = 0
        for d in detaylar:
            m = d["_mumlar"]
            if m.empty:
                continue
            if m["open_time"].iloc[0] <= t <= m["open_time"].iloc[-1]:
                n += 1
        return n

    tablo["o_tarihte_veri_olan"] = [veri_olan(t) for t in tablo["bas"]]
    tablo["borsa_geneli"] = tablo["etki_sembol"] >= (tablo["o_tarihte_veri_olan"] / 2.0)
    return tablo.sort_values("eksik_bar", ascending=False, ignore_index=True)


def sicramalari_grupla(detaylar: list[dict], evren: pd.DataFrame) -> pd.DataFrame:
    """%30 acilis farkini karantinayla aciklanan / aciklanamayan diye ayirir."""
    parcalar = []
    for d in detaylar:
        s = d["_sicramalar"].copy()
        if s.empty:
            continue
        karantina = universe_modulu.karantina_listesi(evren, d["sembol"])
        s.insert(0, "sembol", d["sembol"])
        s["karantina_ayinda"] = [donem_modulu.karantinada_mi(t, karantina) for t in s["open_time"]]
        s["o_ay_settled_kaydi"] = [
            str(pd.Period(pd.Timestamp(t), freq="M")) in set(karantina) for t in s["open_time"]
        ]
        s["sembolun_karantina_aylari"] = ",".join(karantina)
        parcalar.append(s)
    if not parcalar:
        return pd.DataFrame(
            columns=["sembol", "open_time", "onceki_close", "open", "bagil_fark",
                     "karantina_ayinda", "o_ay_settled_kaydi", "sembolun_karantina_aylari"]
        )
    return pd.concat(parcalar, ignore_index=True).sort_values(
        "bagil_fark", ascending=False, ignore_index=True
    )


def funding_dagilimi(detaylar: list[dict]) -> pd.DataFrame:
    """Odeme araligi dagilimi: kayit ve sembol sayisi."""
    kayit = collections.Counter()
    sembol = collections.defaultdict(set)
    for d in detaylar:
        a = d["_aralik"]
        if a.empty:
            continue
        for _, r in a.iterrows():
            saat = int(r["aralik_saat"])
            kayit[saat] += int(r["kayit"])
            sembol[saat].add(d["sembol"])
    return pd.DataFrame(
        [{"aralik_saat": s, "kayit": kayit[s], "sembol": len(sembol[s])} for s in sorted(kayit)]
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
        for t in c["_fiyat_tarihleri"]:
            fiyat[t] += 1
        for t in c["_hacim_tarihleri"]:
            hacim[t] += 1
        satirlar.append(
            {"sembol": d["sembol"], "durum": "karsilastirildi", "ortak_gun": c["ortak_gun"],
             "fiyat_farkli_gun": c["fiyat_farkli_gun"], "hacim_farkli_gun": c["hacim_farkli_gun"],
             "yalniz_birincil": c["yalniz_birincil"]}
        )
    yogun = pd.DataFrame(
        [{"tarih": t, "tip": "fiyat", "sembol_sayisi": n} for t, n in fiyat.most_common(5)]
        + [{"tarih": t, "tip": "hacim", "sembol_sayisi": n} for t, n in hacim.most_common(5)]
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
                if tamam % 10 == 0 or tamam == len(semboller):
                    _gunluk.info(f"  {tamam}/{len(semboller)} tamam (son: {sembol})")

    detaylar.sort(key=lambda d: d["sembol"])
    _gunluk.info(f"indirme bitti. basarili: {len(detaylar)}, hatali: {len(hatalar)}")

    # --- Ciktilar
    ozet = pd.DataFrame([{k: v for k, v in d.items() if not k.startswith("_")} for d in detaylar])
    ozet.to_csv(CIKTI_DIZINI / f"sembol_ozeti_{etiket}.csv", index=False)

    yillik_kapsama(detaylar, evren).to_csv(
        CIKTI_DIZINI / f"yillik_kapsama_{etiket}.csv", index=False
    )
    sicramalar = sicramalari_grupla(detaylar, evren)
    sicramalar.to_csv(CIKTI_DIZINI / f"butunluk_sicramalari_{etiket}.csv", index=False)

    bosluklar = bosluklari_grupla(detaylar)
    bosluklar.to_csv(CIKTI_DIZINI / f"bosluklar_{etiket}.csv", index=False)

    funding_dagilimi(detaylar).to_csv(CIKTI_DIZINI / f"funding_araliklari_{etiket}.csv", index=False)

    capraz, yogun = capraz_ozet(detaylar)
    capraz.to_csv(CIKTI_DIZINI / f"cross_dogrulama_{etiket}.csv", index=False)
    yogun.to_csv(CIKTI_DIZINI / f"cross_yogun_tarihler_{etiket}.csv", index=False)

    if hatalar:
        pd.DataFrame(hatalar, columns=["sembol", "hata"]).to_csv(
            CIKTI_DIZINI / f"hatalar_{etiket}.csv", index=False
        )

    _gunluk.info("--- OZET ---")
    _gunluk.info(f"toplam 4h bar      : {int(ozet['bar_4h'].sum())}")
    _gunluk.info(f"toplam eksik bar   : {int(ozet['eksik_bar'].sum())}")
    _gunluk.info(f"sicrama            : {len(sicramalar)} "
                 f"(karantinali {int(sicramalar['karantina_ayinda'].sum()) if len(sicramalar) else 0})")
    _gunluk.info(f"bosluk             : {len(bosluklar)} "
                 f"(borsa geneli {int(bosluklar['borsa_geneli'].sum()) if len(bosluklar) else 0})")
    _gunluk.info(f"capraz gun         : {capraz.attrs['toplam_gun']}, "
                 f"fiyat farkli {capraz.attrs['fiyat_gun']}, hacim farkli {capraz.attrs['hacim_gun']}")
    _gunluk.info(f"CSV ciktilari: {CIKTI_DIZINI}")


if __name__ == "__main__":
    main()
