"""F1 veri denetimi (on-kayit §2 ve rev.2, CLAUDE.md §3.1).

Yalnizca KAPSAMA ve BUTUNLUK olcer. Getiri, fiyat degisimi, volatilite, funding
ortalamasi veya olay benzeri hicbir istatistik hesaplamaz ya da yazdirmaz.

Kullanim:
    python analysis/00_veri_denetimi/calistir.py --ornek     # 30 sembollu ornek
    python analysis/00_veri_denetimi/calistir.py             # tam evren
"""

from __future__ import annotations

import argparse
import sys
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
from data import split as split_modulu  # noqa: E402
from data import universe as universe_modulu  # noqa: E402

CIKTI_DIZINI = Path(__file__).resolve().parent

# Ornek kume (F1 plani): >=5 delist, >=5 basliksiz 2020 dosyasi, >=5 4h funding,
# >=3 karantinali (TLMUSDT ve BNXUSDT dahil), MATICUSDT ve POLUSDT.
ORNEK_SEMBOLLER = [
    # delist edilmis (7)
    "SRMUSDT", "HNTUSDT", "MATICUSDT", "EOSUSDT", "GALUSDT", "RNDRUSDT", "BTSUSDT",
    # 2020'de listelenmis, basliksiz dosyalar (7)
    "BTCUSDT", "ETHUSDT", "ADAUSDT", "LINKUSDT", "XRPUSDT", "BCHUSDT", "LTCUSDT",
    # 4h funding araligi adaylari (5)
    "WIFUSDT", "ORDIUSDT", "MYXUSDT", "AVNTUSDT", "ASTERUSDT",
    # karantinali (6)
    "TLMUSDT", "BNXUSDT", "MINAUSDT", "CTKUSDT", "LITUSDT", "AERGOUSDT",
    # yeniden adlandirma zincirinin yeni ucu (3)
    "POLUSDT", "RENDERUSDT", "AUSDT",
    # karsilastirma icin (2)
    "SOLUSDT", "GUSDT",
]


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
        "_mumlar": mumlar,
        "_gunluk": gunluk,
        "_funding": fund,
        "_sicramalar": sicramalar,
        "_uzun_bosluk": uzun_bosluk,
        "_aralik": aralik,
    }


def yillik_kapsama(detaylar: list[dict], evren: pd.DataFrame) -> pd.DataFrame:
    """Yillara gore: veri bulunan sembol, 10M ve 2M esigini en az bir gun gecen.

    Uygunluk on-kayit rev.2 kurallariyla hesaplanir: pencere donem baslangicini
    asamaz, karantina gunleri uygun sayilmaz.
    """
    satirlar = []
    yillar = range(2020, 2027)
    for yil in yillar:
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


def cross_dogrulama_ozeti(detaylar: list[dict]) -> pd.DataFrame:
    """Turetilmis 1d ile kaynaktaki birincil 1d dosyalarini karsilastirir."""
    satirlar = []
    for d in detaylar:
        try:
            birincil = klines_modulu.birincil_gunluk_indir(d["sembol"])
        except Exception as hata:  # kaynakta 1d dosyasi olmayabilir
            satirlar.append({"sembol": d["sembol"], "durum": f"hata: {type(hata).__name__}"})
            continue
        turetilmis = d["_gunluk"]
        if turetilmis.empty or birincil.empty:
            satirlar.append({"sembol": d["sembol"], "durum": "veri yok"})
            continue
        fark = klines_modulu.cross_dogrula(turetilmis, birincil)
        sutunlar = [s for s in fark.columns if s.endswith("_bagil_fark")]
        satirlar.append(
            {
                "sembol": d["sembol"],
                "durum": "karsilastirildi",
                "ortak_gun": len(fark),
                "yalniz_turetilmis": fark.attrs.get("yalniz_turetilmis"),
                "yalniz_birincil": fark.attrs.get("yalniz_birincil"),
                "azami_bagil_fark": float(fark[sutunlar].max().max()),
                "fark_1e6_ustu_gun": int((fark[sutunlar] > 1e-6).any(axis=1).sum()),
            }
        )
    return pd.DataFrame(satirlar)


def main() -> None:
    ayristirici = argparse.ArgumentParser()
    ayristirici.add_argument("--ornek", action="store_true", help="30 sembollu ornek kume")
    argumanlar = ayristirici.parse_args()

    evren = universe_modulu.evren_yukle()
    split_tablosu = split_modulu.split_oku()

    if argumanlar.ornek:
        semboller = [s for s in ORNEK_SEMBOLLER]
        etiket = "ornek"
    else:
        semboller = universe_modulu.dahil_semboller(evren)
        etiket = "tam"

    print(f"[{etiket}] {len(semboller)} sembol denetlenecek", flush=True)
    detaylar = []
    for i, sembol in enumerate(semboller, 1):
        detaylar.append(sembol_denetle(sembol, evren))
        print(f"  {i}/{len(semboller)} {sembol}", flush=True)

    ozet = pd.DataFrame([{k: v for k, v in d.items() if not k.startswith("_")} for d in detaylar])
    ozet.to_csv(CIKTI_DIZINI / f"sembol_ozeti_{etiket}.csv", index=False)

    yillik = yillik_kapsama(detaylar, evren)
    yillik.to_csv(CIKTI_DIZINI / f"yillik_kapsama_{etiket}.csv", index=False)

    sicrama_tablo = []
    for d in detaylar:
        s = d["_sicramalar"].copy()
        if not s.empty:
            s.insert(0, "sembol", d["sembol"])
            karantina = universe_modulu.karantina_listesi(evren, d["sembol"])
            s["karantina_ayinda"] = [
                donem_modulu.karantinada_mi(t, karantina) for t in s["open_time"]
            ]
            sicrama_tablo.append(s)
    sicramalar = (
        pd.concat(sicrama_tablo, ignore_index=True) if sicrama_tablo
        else pd.DataFrame(columns=["sembol", "open_time", "onceki_close", "open",
                                   "bagil_fark", "karantina_ayinda"])
    )
    sicramalar.to_csv(CIKTI_DIZINI / f"butunluk_sicramalari_{etiket}.csv", index=False)

    capraz = cross_dogrulama_ozeti(detaylar)
    capraz.to_csv(CIKTI_DIZINI / f"cross_dogrulama_{etiket}.csv", index=False)

    bosluk_tablo = []
    for d in detaylar:
        b = d["_uzun_bosluk"].copy()
        if not b.empty:
            b.insert(0, "sembol", d["sembol"])
            bosluk_tablo.append(b)
    bosluklar = (
        pd.concat(bosluk_tablo, ignore_index=True) if bosluk_tablo
        else pd.DataFrame(columns=["sembol", "bas", "son", "eksik_bar"])
    )
    bosluklar.to_csv(CIKTI_DIZINI / f"uzun_bosluklar_{etiket}.csv", index=False)

    print("\nCSV ciktilari yazildi:", CIKTI_DIZINI)
    print(ozet.to_string(index=False))
    print("\nYillik kapsama:")
    print(yillik.to_string(index=False))
    print("\nButunluk sicramalari:", len(sicramalar))
    print("\n1d capraz dogrulama:")
    print(capraz.to_string(index=False))


if __name__ == "__main__":
    main()
