"""Denetci bulgusu A1 olcumu: uzlasma anindan sonra donem icinde kalan funding kayitlari.

`data.funding._donem_icinde` ust siniri son gercek barin KAPANISIDIR
(`donem_bitis + 4h + 1 dk`). Uzlasmis sozlesmelerde deliveryDate cogunlukla son
barin icine duser (RESULTS §2). Bu betik, deliveryDate'ten SONRA gelip yine de
donem icinde sayilan funding kayitlarini sayar ve bunlardan hangilerinin donem
sonu cikis anina (`donem_bitis + 4h`, 1 dk tolerans) denk geldigini isaretler.

Tamamlayici olcum (ikinci tur):
- Uzlasma sonrasi her kaydin orani, ayni sembolun uzlasma oncesi son 30 kaydinin
  medyan |oran|'i ile yan yana; sifir, sembol icinde tekrar, uzlasma oncesi son
  kayitla ayni deger ve isaret. Amac kayitlarin gercek piyasa orani mi yoksa
  uzlasma sonrasi yapay deger mi oldugunu anlamak (veri butunlugu).
- Her kaydin konumu: deliveryDate, son bar acilisi ve kapanisina gore.
- deliveryDate'i olmayan (exchangeInfo disi) sembollerde son barin acilisi ile
  kapanisi arasina dusen kayitlar, ayni konum ve oran sutunlariyla.

Getiri, pozisyon funding'i ya da olay hesaplamaz; oranlar yalnizca uzlasma
anindaki tekil kayitlar ve sembolun kendi referans medyaniyla karsilastirilir.
Kod degistirmez.

Kullanim:
    python analysis/00_veri_denetimi/a1_olcumu.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

KOK = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KOK))

import config  # noqa: E402
from data import funding as funding_modulu  # noqa: E402
from data import pencere as pencere_modulu  # noqa: E402
from data import universe as universe_modulu  # noqa: E402

CIKTI = Path(__file__).resolve().parent / "a1_uzlasma_sonrasi_funding_tam.csv"
CIKTI_ORAN = Path(__file__).resolve().parent / "a1_uzlasma_sonrasi_oranlar_tam.csv"
CIKTI_TESLIMSIZ = Path(__file__).resolve().parent / "a1_teslimsiz_son_bar_funding_tam.csv"
REFERANS_KAYIT = 30


def sembol_olc(sembol: str, teslim: pd.Timestamp, donem, fund: pd.DataFrame) -> list[dict]:
    """Bir sembolde `teslim < odeme` olup donem icinde kalan kayitlar. Saf."""
    if fund.empty:
        return []
    zamanlar = pd.DatetimeIndex(fund["odeme_zamani"])
    icinde = funding_modulu._donem_icinde(zamanlar, donem, config.BAR_4H)
    sonra = icinde & (zamanlar > teslim + funding_modulu.ODEME_TOLERANSI)
    cikis_ani = donem.bitis + pencere_modulu.adim(config.BAR_4H)
    return [
        {"sembol": sembol, "deliveryDate": teslim, "donem_bitis": donem.bitis, "odeme_zamani": z,
         "teslimden_sonra_saat": (z - teslim) / pd.Timedelta(hours=1),
         "aralik_saat": a,
         "cikis_anina_denk": abs(z - cikis_ani) <= funding_modulu.ODEME_TOLERANSI}
        for z, a in zip(zamanlar[sonra], fund.loc[sonra, "aralik_saat"])
    ]


def konum(z: pd.Timestamp, acilis: pd.Timestamp, kapanis: pd.Timestamp,
          teslim: pd.Timestamp | None) -> str:
    """Kaydin son bara ve deliveryDate'e gore yeri (1 dk tolerans). Saf."""
    tol = funding_modulu.ODEME_TOLERANSI
    if abs(z - acilis) <= tol:
        yer = "son_bar_acilisi"
    elif abs(z - kapanis) <= tol:
        yer = "son_bar_kapanisi"
    elif acilis < z < kapanis:
        yer = "son_bar_ici"
    elif z < acilis:
        yer = "son_bardan_once"
    else:
        yer = "son_bardan_sonra"
    if teslim is None or pd.isna(teslim):
        return yer
    if abs(z - teslim) <= tol:
        return f"{yer}|teslim_aninda"
    return f"{yer}|teslimden_{'sonra' if z > teslim else 'once'}"


def oran_karsilastir(kayitlar: pd.DataFrame, referans: pd.DataFrame) -> pd.DataFrame:
    """Incelenen kayitlarin oranini referans kayitlarla yan yana koyar. Saf.

    `referans`: ayni sembolun incelenen kayitlardan onceki kayitlari (zaman
    sirali); yalnizca son `REFERANS_KAYIT` tanesi kullanilir.
    """
    ref = referans.tail(REFERANS_KAYIT)
    medyan = float(ref["oran"].abs().median()) if len(ref) else float("nan")
    medyan_8h = float(ref["oran_8h"].abs().median()) if len(ref) else float("nan")
    son_ref = ref["oran"].iloc[-1] if len(ref) else float("nan")
    son_ref_aralik = ref["aralik_saat"].iloc[-1] if len(ref) else float("nan")
    out = kayitlar[["odeme_zamani", "aralik_saat", "oran", "oran_8h"]].copy()
    out["isaret"] = ["sifir" if o == 0 else ("pozitif" if o > 0 else "negatif") for o in out["oran"]]
    out["referans_kayit"] = len(ref)
    out["referans_medyan_abs_oran"] = medyan
    out["referans_medyan_abs_oran_8h"] = medyan_8h
    out["abs_oran_8h_medyana_orani"] = out["oran_8h"].abs() / medyan_8h if medyan_8h else float("nan")
    out["referans_son_oran"] = son_ref
    out["referans_son_aralik"] = son_ref_aralik
    out["referans_son_oranla_ayni"] = out["oran"] == son_ref
    out["referans_30_kayit_sabit"] = bool(len(ref) and ref["oran"].nunique() == 1)
    out["incelenenler_icinde_tekrar"] = out["oran"].duplicated(keep=False)
    return out


def main() -> None:
    evren = universe_modulu.evren_yukle()
    sinif = universe_modulu.delist_sinifi(evren, universe_modulu.exchange_info_anlik_yukle())
    settling = sinif.loc[sinif["sinif"] == universe_modulu.SETTLING_DURUMU].sort_values("sembol")

    adim = pencere_modulu.adim(config.BAR_4H)
    tol = funding_modulu.ODEME_TOLERANSI
    satirlar, sayim, oran_parcalari = [], [], []
    for r in settling.itertuples():
        donem = universe_modulu.sembol_donemleri(evren, r.sembol)[-1]
        fund = funding_modulu.ham_funding_yukle(r.sembol)
        fund = fund.loc[fund["odeme_zamani"] <= config.DONEM_SONU].reset_index(drop=True)
        s = sembol_olc(r.sembol, r.deliveryDate, donem, fund)
        satirlar += s
        sayim.append((r.sembol, len(s)))
        if s:
            secilen = fund.loc[fund["odeme_zamani"].isin([x["odeme_zamani"] for x in s])]
            referans = fund.loc[fund["odeme_zamani"] <= r.deliveryDate + tol]
            k = oran_karsilastir(secilen, referans)
            k.insert(0, "sembol", r.sembol)
            k.insert(1, "deliveryDate", r.deliveryDate)
            k.insert(2, "son_bar_acilisi", donem.bitis)
            k.insert(3, "son_bar_kapanisi", donem.bitis + adim)
            k["konum"] = [konum(z, donem.bitis, donem.bitis + adim, r.deliveryDate)
                          for z in k["odeme_zamani"]]
            k["cikis_anina_denk"] = [abs(z - (donem.bitis + adim)) <= tol for z in k["odeme_zamani"]]
            oran_parcalari.append(k)

    # deliveryDate'i olmayan semboller: son barin acilisi ile kapanisi arasi (uclar dahil).
    disi = sinif.loc[sinif["sinif"] == "exchangeInfo_disi"].sort_values("sembol")
    teslimsiz_parcalari, teslimsiz_sayim = [], []
    for r in disi.itertuples():
        donem = universe_modulu.sembol_donemleri(evren, r.sembol)[-1]
        acilis, kapanis = donem.bitis, donem.bitis + adim
        fund = funding_modulu.ham_funding_yukle(r.sembol)
        fund = fund.loc[fund["odeme_zamani"] <= config.DONEM_SONU].reset_index(drop=True)
        z = fund["odeme_zamani"]
        secim = (z >= acilis - tol) & (z <= kapanis + tol)
        teslimsiz_sayim.append((r.sembol, int(secim.sum()), len(fund) > 0))
        if not secim.any():
            continue
        k = oran_karsilastir(fund.loc[secim], fund.loc[z < acilis - tol])
        k.insert(0, "sembol", r.sembol)
        k.insert(1, "son_bar_acilisi", acilis)
        k.insert(2, "son_bar_kapanisi", kapanis)
        k["konum"] = [konum(t, acilis, kapanis, None) for t in k["odeme_zamani"]]
        k["donem_icinde"] = funding_modulu._donem_icinde(pd.DatetimeIndex(k["odeme_zamani"]), donem,
                                                        config.BAR_4H)
        teslimsiz_parcalari.append(k)

    tablo = pd.DataFrame(satirlar, columns=["sembol", "deliveryDate", "donem_bitis", "odeme_zamani",
                                            "teslimden_sonra_saat", "aralik_saat", "cikis_anina_denk"])
    tablo.to_csv(CIKTI, index=False, lineterminator="\n")
    etkilenen = sum(1 for _, n in sayim if n)
    print(f"SETTLING sembol: {len(sayim)}")
    print(f"uzlasma sonrasi donem icinde kalan kayit: {len(tablo)} ({etkilenen} sembol)")
    print(f"  bunlardan cikis anina denk gelen: {int(tablo['cikis_anina_denk'].sum())} "
          f"({tablo.loc[tablo['cikis_anina_denk'], 'sembol'].nunique()} sembol)")
    if len(tablo):
        print(tablo.groupby("aralik_saat").size().rename("kayit").to_string())
    print(f"CSV: {CIKTI}")

    oranlar = pd.concat(oran_parcalari, ignore_index=True) if oran_parcalari else pd.DataFrame()
    oranlar.to_csv(CIKTI_ORAN, index=False, lineterminator="\n")
    print("\n--- Uzlasma sonrasi kayitlarin oranlari ---")
    if len(oranlar):
        with pd.option_context("display.width", 250, "display.max_columns", 30):
            print(oranlar[["sembol", "odeme_zamani", "aralik_saat", "oran", "oran_8h",
                           "referans_medyan_abs_oran_8h", "abs_oran_8h_medyana_orani",
                           "referans_son_oran", "referans_son_oranla_ayni",
                           "incelenenler_icinde_tekrar", "konum"]].to_string(index=False))
        print("isaret:", oranlar["isaret"].value_counts().to_dict())
        print("sifir oran:", int((oranlar["oran"] == 0).sum()))
        print("referansin son oraniyla ayni:", int(oranlar["referans_son_oranla_ayni"].sum()))
        print("referans 30 kaydi sabit olan sembol:",
              oranlar.loc[oranlar["referans_30_kayit_sabit"], "sembol"].unique().tolist())
        print("konum:", oranlar["konum"].value_counts().to_dict())
        print("birden fazla gecen oran degeri:",
              {k: v for k, v in oranlar["oran"].value_counts().items() if v > 1})
    print(f"CSV: {CIKTI_ORAN}")

    teslimsiz = pd.concat(teslimsiz_parcalari, ignore_index=True) if teslimsiz_parcalari else pd.DataFrame()
    teslimsiz.to_csv(CIKTI_TESLIMSIZ, index=False, lineterminator="\n")
    print("\n--- deliveryDate'i olmayan semboller: son bar icindeki kayitlar ---")
    print(f"sembol: {len(teslimsiz_sayim)}, funding kaydi olmayan: "
          f"{sum(1 for _, _, v in teslimsiz_sayim if not v)}, son barda kaydi olan: "
          f"{sum(1 for _, n, _ in teslimsiz_sayim if n)}, kayit: {len(teslimsiz)}")
    if len(teslimsiz):
        with pd.option_context("display.width", 250, "display.max_columns", 30):
            print(teslimsiz[["sembol", "son_bar_acilisi", "odeme_zamani", "aralik_saat", "oran",
                             "oran_8h", "referans_medyan_abs_oran_8h", "abs_oran_8h_medyana_orani",
                             "referans_son_oranla_ayni", "konum", "donem_icinde"]].to_string(index=False))
        print("konum:", teslimsiz["konum"].value_counts().to_dict())
        print("isaret:", teslimsiz["isaret"].value_counts().to_dict())
    print("son barda kaydi olmayan:", [s for s, n, _ in teslimsiz_sayim if n == 0])
    print(f"CSV: {CIKTI_TESLIMSIZ}")

    # Oneri etkisi: ust sinir son barin kapanisi yerine acilisi olsaydi, tum dahil
    # sembollerin tum donemlerinde kac kayit donem disina cikardi. Yalnizca sayim.
    print("\n--- Oneri etkisi: (son bar acilisi + 1 dk, son bar kapanisi + 1 dk) araligindaki kayitlar ---")
    etki = []
    for sembol in sorted(evren.loc[~evren["haric"], "sembol"].unique()):
        fund = funding_modulu.ham_funding_yukle(sembol)
        fund = fund.loc[fund["odeme_zamani"] <= config.DONEM_SONU]
        zamanlar = pd.DatetimeIndex(fund["odeme_zamani"])
        donemler = universe_modulu.sembol_donemleri(evren, sembol)
        for i, d in enumerate(donemler):
            n = int(((zamanlar > d.bitis + tol) & (zamanlar < d.bitis + adim + tol)).sum())
            if n:
                etki.append((sembol, i, i == len(donemler) - 1, d.bitis, n))
    etki = pd.DataFrame(etki, columns=["sembol", "donem_sira", "son_donem", "donem_bitis", "kayit"])
    print(f"kayit: {int(etki['kayit'].sum())}, sembol: {etki['sembol'].nunique()}, "
          f"son donemde: {int(etki.loc[etki['son_donem'], 'kayit'].sum())}, "
          f"ara donemde: {int(etki.loc[~etki['son_donem'], 'kayit'].sum())}, "
          f"veri sonu donemi (bitis {config.DONEM_SONU}): "
          f"{int(etki.loc[etki['donem_bitis'] >= config.DONEM_SONU - adim, 'kayit'].sum())}")
    if (~etki["son_donem"]).any():
        print(etki.loc[~etki["son_donem"]].to_string(index=False))


if __name__ == "__main__":
    main()
