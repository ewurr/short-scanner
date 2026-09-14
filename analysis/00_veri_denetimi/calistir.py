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
    # F1 kapsama denetimi TUM gecmisi (B grubu ve C2 dahil) olcer ve getiri
    # hesaplamaz (CLAUDE.md §3.1); bu yuzden kume korumasiz ham yukleyiciler
    # bilerek kullanilir. Analiz ve olay kodu bunlari cagirmaz.
    mumlar = klines_modulu.ham_mumlari_yukle(sembol, config.BAR_4H)
    gunluk = klines_modulu.gunluge_cevir(mumlar)
    fund = funding_modulu.ham_funding_yukle(sembol)

    karantina = universe_modulu.karantina_listesi(evren, sembol)
    donemler = universe_modulu.sembol_donemleri(evren, sembol)

    bosluklar = klines_modulu.eksik_barlar(mumlar, config.BAR_4H)
    uzun_bosluk = bosluklar.loc[bosluklar["eksik_bar"] > config.DENETIM_UZUN_BOSLUK_BAR] if not bosluklar.empty else bosluklar

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
        # Capraz dogrulama da tum gecmisi olcer; kume korumasiz ham yol bilerek.
        birincil = klines_modulu.ham_birincil_gunluk_indir(sembol)
        if not gunluk.empty and not birincil.empty:
            fark = klines_modulu.cross_dogrula(gunluk, birincil)
            fs = [f"{c}_bagil_fark" for c in FIYAT_SUTUNLARI]
            hs = [f"{c}_bagil_fark" for c in HACIM_SUTUNLARI]
            capraz = {
                "durum": "karsilastirildi",
                "ortak_gun": len(fark),
                "fiyat_farkli_gun": int((fark[fs] > config.DENETIM_CAPRAZ_TOLERANS).any(axis=1).sum()),
                "hacim_farkli_gun": int((fark[hs] > config.DENETIM_CAPRAZ_TOLERANS).any(axis=1).sum()),
                "yalniz_birincil": fark.attrs.get("yalniz_birincil"),
                "_fiyat_tarihleri": [
                    str(t.date()) for t in fark.loc[(fark[fs] > config.DENETIM_CAPRAZ_TOLERANS).any(axis=1), "open_time"]
                ],
                "_hacim_tarihleri": [
                    str(t.date()) for t in fark.loc[(fark[hs] > config.DENETIM_CAPRAZ_TOLERANS).any(axis=1), "open_time"]
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
    for yil in range(config.DONEM_BASI.year, config.DONEM_SONU.year + 1):
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
                # F1 denetimi tum gecmisi olcer, bir kumeye ait degildir: kume
                # baslangici bilincli olarak None (on-kayit §3 rev.5 kume hesaplari icindir).
                sinirlar = dict(donem_baslangic=d_bas, donem_bitis=d_son, kume_baslangic=None)
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

    Gruplama birebir ayni (bas, son) ciftine gore degil, ZAMAN ORTUSMESINE gore
    yapilir: birbiriyle ortusen bosluklar tek bir olaydir. Olayin baslangici en
    erken baslangic, bitisi en gec bitistir. O zaman araliginda verisi bulunan
    sembollerin en az yarisini etkileyen olay "borsa geneli" sayilir.

    Bu yalnizca bir TESHIS olcumudur; veri katmanini etkilemez.
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
    bos_sutun = ["sembol", "bas", "son", "eksik_bar", "olay_id"]
    if not satirlar:
        return (pd.DataFrame(columns=bos_sutun),
                pd.DataFrame(columns=["olay_id", "bas", "son", "etki_sembol",
                                      "o_aralikta_veri_olan", "borsa_geneli",
                                      "azami_eksik_bar", "semboller"]))

    tablo = pd.DataFrame(satirlar).sort_values("bas", ignore_index=True)

    # Ortusen araliklari tek olayda birlestir.
    olay_id = []
    su_an = 0
    olay_bas, olay_son = tablo.loc[0, "bas"], tablo.loc[0, "son"]
    sinirlar = []
    for i, r in tablo.iterrows():
        if r["bas"] <= olay_son:          # ortusuyor -> ayni olay
            olay_son = max(olay_son, r["son"])
        else:                              # yeni olay
            sinirlar.append((su_an, olay_bas, olay_son))
            su_an += 1
            olay_bas, olay_son = r["bas"], r["son"]
        olay_id.append(su_an)
    sinirlar.append((su_an, olay_bas, olay_son))
    tablo["olay_id"] = olay_id

    def veri_olan(bas, son) -> int:
        """O zaman araliginda verisi bulunan sembol sayisi."""
        n = 0
        for d in detaylar:
            mm = d["_mumlar"]
            if mm.empty:
                continue
            if mm["open_time"].iloc[0] <= son and bas <= mm["open_time"].iloc[-1]:
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
    return tablo, pd.DataFrame(olaylar).sort_values(
        "azami_eksik_bar", ascending=False, ignore_index=True
    )


def karantina_kaybi(evren: pd.DataFrame) -> tuple[int, pd.DataFrame]:
    """Karantina yuzunden disarida kalan sembol-ay sayisi ve en cok kayipli 5 sembol."""
    dahil = evren.loc[~evren["haric"]].drop_duplicates("sembol")
    satirlar = []
    for _, r in dahil.iterrows():
        aylar = [a for a in str(r["karantina_aylari"]).split(",") if a]
        if aylar:
            satirlar.append({"sembol": r["sembol"], "karantina_ay": len(aylar),
                             "aylar": ",".join(aylar)})
    if not satirlar:
        return 0, pd.DataFrame(columns=["sembol", "karantina_ay", "aylar"])
    tablo = pd.DataFrame(satirlar).sort_values("karantina_ay", ascending=False, ignore_index=True)
    return int(tablo["karantina_ay"].sum()), tablo


def kisa_donemler(evren: pd.DataFrame, asgari_gun: int = config.DENETIM_KISA_DONEM_GUN) -> pd.DataFrame:
    """60 gunden kisa listeleme donemleri (30 gunluk pencere bunlari etkisiz birakir)."""
    dahil = evren.loc[(~evren["haric"]) & (evren["donem_id"] >= 0)]
    satirlar = []
    for _, r in dahil.iterrows():
        bas, son = pd.Timestamp(r["donem_baslangic"]), pd.Timestamp(r["donem_bitis"])
        gun = (son - bas) / pd.Timedelta(days=1)
        if gun < asgari_gun:
            satirlar.append(
                {"sembol": r["sembol"], "donem_id": int(r["donem_id"]),
                 "donem": f"{r['donem_bas_ay']} -> {r['donem_son_ay']}", "gun": round(gun, 1)}
            )
    return pd.DataFrame(satirlar, columns=["sembol", "donem_id", "donem", "gun"]).sort_values(
        "gun", ignore_index=True
    )


def fiyat_farki_listeleme_yasi(detaylar: list[dict]) -> pd.DataFrame:
    """Fiyat farki cikan gunler, sembolun ILK barindan kac gun sonra?"""
    satirlar = []
    for d in detaylar:
        c = d["_capraz"]
        if c.get("durum") != "karsilastirildi":
            continue
        ilk = d["ilk_bar"]
        for tarih in c.get("_fiyat_tarihleri", []):
            gun = (pd.Timestamp(tarih, tz="UTC") - pd.Timestamp(ilk)) / pd.Timedelta(days=1)
            satirlar.append(
                {"sembol": d["sembol"], "tarih": tarih, "ilk_bar": str(pd.Timestamp(ilk).date()),
                 "listelemeden_sonra_gun": round(gun, 1), "ilk_30_gun_icinde": gun < 30}
            )
    return pd.DataFrame(
        satirlar, columns=["sembol", "tarih", "ilk_bar", "listelemeden_sonra_gun",
                           "ilk_30_gun_icinde"]
    ).sort_values("listelemeden_sonra_gun", ignore_index=True)


def ortam_kaydi() -> pd.DataFrame:
    """Kosuyu ureten ortam: Python ve paket surumleri."""
    import importlib.metadata as md
    import platform

    satirlar = [
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


def sicramalari_grupla(detaylar: list[dict], evren: pd.DataFrame) -> pd.DataFrame:
    """%30 acilis farkini karantinayla aciklanan / aciklanamayan diye ayirir."""
    parcalar = []
    for d in detaylar:
        s = d["_sicramalar"].copy()
        if s.empty:
            continue
        karantina = universe_modulu.karantina_listesi(evren, d["sembol"])
        s.insert(0, "sembol", d["sembol"])
        # Karantina kurali rev.7 ile kaldirildi; SETTLED ayi yalnizca denetim bilgisi.
        s["karantina_ayinda"] = [
            str(pd.Period(pd.Timestamp(t).tz_localize(None), freq="M")) in set(karantina) for t in s["open_time"]
        ]
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

    bosluklar, bosluk_olaylari = bosluklari_grupla(detaylar)
    bosluklar.to_csv(CIKTI_DIZINI / f"bosluklar_{etiket}.csv", index=False)
    bosluk_olaylari.to_csv(CIKTI_DIZINI / f"bosluk_olaylari_{etiket}.csv", index=False)

    funding_dagilimi(detaylar).to_csv(CIKTI_DIZINI / f"funding_araliklari_{etiket}.csv", index=False)

    capraz, yogun = capraz_ozet(detaylar)
    capraz.to_csv(CIKTI_DIZINI / f"cross_dogrulama_{etiket}.csv", index=False)
    yogun.to_csv(CIKTI_DIZINI / f"cross_yogun_tarihler_{etiket}.csv", index=False)

    fiyat_yasi = fiyat_farki_listeleme_yasi(detaylar)
    fiyat_yasi.to_csv(CIKTI_DIZINI / f"fiyat_farki_listeleme_yasi_{etiket}.csv", index=False)

    kayip_toplam, kayip_tablo = karantina_kaybi(evren)
    kayip_tablo.to_csv(CIKTI_DIZINI / f"karantina_kaybi_{etiket}.csv", index=False)

    kisa = kisa_donemler(evren)
    kisa.to_csv(CIKTI_DIZINI / f"kisa_donemler_{etiket}.csv", index=False)

    ortam = ortam_kaydi()
    ortam.to_csv(CIKTI_DIZINI / f"ortam_{etiket}.csv", index=False)

    if hatalar:
        pd.DataFrame(hatalar, columns=["sembol", "hata"]).to_csv(
            CIKTI_DIZINI / f"hatalar_{etiket}.csv", index=False
        )

    _gunluk.info("--- OZET ---")
    _gunluk.info(f"toplam 4h bar      : {int(ozet['bar_4h'].sum())}")
    _gunluk.info(f"toplam eksik bar   : {int(ozet['eksik_bar'].sum())}")
    _gunluk.info(f"sicrama            : {len(sicramalar)} "
                 f"(karantinali {int(sicramalar['karantina_ayinda'].sum()) if len(sicramalar) else 0})")
    _gunluk.info(f"bosluk             : {len(bosluklar)} adet, "
                 f"{len(bosluk_olaylari)} olay "
                 f"(borsa geneli {int(bosluk_olaylari['borsa_geneli'].sum()) if len(bosluk_olaylari) else 0})")
    _gunluk.info(f"karantina kaybi    : {kayip_toplam} sembol-ay, "
                 f"{len(kayip_tablo)} sembolde")
    _gunluk.info(f"60 gunden kisa donem: {len(kisa)}")
    _gunluk.info(f"fiyat farki gunleri : {len(fiyat_yasi)} "
                 f"(ilk 30 gun icinde {int(fiyat_yasi['ilk_30_gun_icinde'].sum()) if len(fiyat_yasi) else 0})")
    _gunluk.info(f"capraz gun         : {capraz.attrs['toplam_gun']}, "
                 f"fiyat farkli {capraz.attrs['fiyat_gun']}, hacim farkli {capraz.attrs['hacim_gun']}")
    _gunluk.info(f"CSV ciktilari: {CIKTI_DIZINI}")


if __name__ == "__main__":
    main()
