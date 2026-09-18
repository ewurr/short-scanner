"""Denetci bulgusu A1 olcumu: uzlasma anindan sonra donem icinde kalan funding kayitlari.

`data.funding._donem_icinde` ust siniri son gercek barin KAPANISIDIR
(`donem_bitis + 4h + 1 dk`). Uzlasmis sozlesmelerde deliveryDate cogunlukla son
barin icine duser (RESULTS §2). Bu betik yalnizca KAYIT SAYAR ve ZAMAN KONUMU yazar:

1. deliveryDate'ten SONRA gelip donem icinde sayilan kayitlar ve bunlardan
   hangilerinin donem sonu cikis anina (`donem_bitis + 4h`, 1 dk tolerans) denk
   geldigi (`a1_uzlasma_sonrasi_funding_tam.csv`).
2. Her kaydin konumu (deliveryDate, son bar acilisi ve kapanisina gore) ve
   deliveryDate'i olmayan (exchangeInfo disi) sembollerde son barin acilisi ile
   kapanisi arasina dusen kayitlar (`a1_konumlar_tam.csv`).
3. Ust siniri son bar acilisina cekmenin etkisi, tum donemlerde kayit sayisi
   (`a1_oneri_etkisi_tam.csv`; 1093e69'daki 43 kayit dokumu).

DEGER RAPORLAMAZ (denetci bulgusu D-B1, CLAUDE.md §3.1). Uzlasma sonrasi
kayitlar donem sonunu asan pozisyonlarin net getirisine girebilecek turdendir.
1093e69'da oran degerleri ve isaretleri raporlandi; bu, veri denetimi sinirini
asti ve rapordan cikarildi. O kosunun ham ciktilari
(`a1_uzlasma_sonrasi_oranlar_tam.csv`, `a1_teslimsiz_son_bar_funding_tam.csv`)
iz icin depoda durur. Varsayilan kosu bu dosyalari URETMEZ ve oran degeri
yazdirmaz; yalnizca `--oran-degerleri` bayragiyla, o kosunun yeniden uretimi
icin yazilir. Bu bayrak yeni bir analiz icin kullanilmaz.

Getiri, pozisyon funding'i ya da olay hesaplamaz. Veri katmani kodunu
degistirmez.

Kullanim:
    python analysis/00_veri_denetimi/a1_olcumu.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

KOK = Path(__file__).resolve().parents[2]
BU_DIZIN = Path(__file__).resolve().parent
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(BU_DIZIN))

import config  # noqa: E402
from calistir import git_durumu, ortam_kaydi  # noqa: E402
from data import donem as donem_modulu  # noqa: E402
from data import funding as funding_modulu  # noqa: E402
from data import pencere as pencere_modulu  # noqa: E402
from data import universe as universe_modulu  # noqa: E402

CIKTI = BU_DIZIN / "a1_uzlasma_sonrasi_funding_tam.csv"
CIKTI_KONUM = BU_DIZIN / "a1_konumlar_tam.csv"
CIKTI_ONERI = BU_DIZIN / "a1_oneri_etkisi_tam.csv"
CIKTI_ORTAM = BU_DIZIN / "a1_ortam_tam.csv"
# Yalnizca --oran-degerleri ile (1093e69 kosusunun yeniden uretimi).
CIKTI_ORAN = BU_DIZIN / "a1_uzlasma_sonrasi_oranlar_tam.csv"
CIKTI_TESLIMSIZ = BU_DIZIN / "a1_teslimsiz_son_bar_funding_tam.csv"
REFERANS_KAYIT = 30

ADIM = pencere_modulu.adim(config.BAR_4H)
TOL = funding_modulu.ODEME_TOLERANSI


def funding_yukle(sembol: str) -> pd.DataFrame:
    """Sembolun ham funding kayitlari, toplam doneme IKI UCTAN kesilmis
    (denetci bulgusu D-B8; F1 denetimiyle ayni fonksiyon)."""
    return donem_modulu.toplam_doneme_kes(funding_modulu.ham_funding_yukle(sembol), "odeme_zamani")


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

    Yalnizca `--oran-degerleri` ile, 1093e69 kosusunun yeniden uretimi icin
    cagrilir (bkz. modul belgesi).

    `referans`: ayni sembolun incelenen kayitlardan onceki kayitlari. ON KOSUL:
    `referans` `odeme_zamani`na gore ARTAN sirada olmalidir. Fonksiyon siralamaz;
    `tail` ve `iloc[-1]` konuma gore calisir, sirasiz girdide "son 30 kayit" ve
    "referansin son orani" sessizce yanlis kayitlardan hesaplanir. Yalnizca son
    `REFERANS_KAYIT` tanesi kullanilir.
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


# --- Ana akis ----------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    ayristirici = argparse.ArgumentParser()
    ayristirici.add_argument(
        "--oran-degerleri", action="store_true",
        help="1093e69 kosusunun oran degeri CSV'lerini yeniden uretir. Yeni analiz icin KULLANILMAZ "
             "(denetci bulgusu D-B1).",
    )
    argumanlar = ayristirici.parse_args(argv)

    baslangic = pd.Timestamp.now(tz="UTC")
    git = git_durumu()

    evren = universe_modulu.evren_yukle()
    sinif = universe_modulu.delist_sinifi(evren, universe_modulu.exchange_info_anlik_yukle())
    sinif_haritasi = sinif.set_index("sembol")["sinif"].to_dict()
    settling = sinif.loc[sinif["sinif"] == universe_modulu.SETTLING_DURUMU].sort_values("sembol")

    satirlar, sayim, konumlar, oran_parcalari = [], [], [], []
    for r in settling.itertuples():
        donem = universe_modulu.sembol_donemleri(evren, r.sembol)[-1]
        fund = funding_yukle(r.sembol)
        s = sembol_olc(r.sembol, r.deliveryDate, donem, fund)
        satirlar += s
        sayim.append((r.sembol, len(s)))
        for x in s:
            konumlar.append({"sembol": r.sembol, "sinif": r.sinif, "deliveryDate": r.deliveryDate,
                             "son_bar_acilisi": donem.bitis, "son_bar_kapanisi": donem.bitis + ADIM,
                             "odeme_zamani": x["odeme_zamani"], "aralik_saat": x["aralik_saat"],
                             "konum": konum(x["odeme_zamani"], donem.bitis, donem.bitis + ADIM, r.deliveryDate)})
        if s and argumanlar.oran_degerleri:
            secilen = fund.loc[fund["odeme_zamani"].isin([x["odeme_zamani"] for x in s])]
            referans = fund.loc[fund["odeme_zamani"] <= r.deliveryDate + TOL]
            k = oran_karsilastir(secilen, referans)
            k.insert(0, "sembol", r.sembol)
            k.insert(1, "deliveryDate", r.deliveryDate)
            k.insert(2, "son_bar_acilisi", donem.bitis)
            k.insert(3, "son_bar_kapanisi", donem.bitis + ADIM)
            k["konum"] = [konum(z, donem.bitis, donem.bitis + ADIM, r.deliveryDate) for z in k["odeme_zamani"]]
            k["cikis_anina_denk"] = [abs(z - (donem.bitis + ADIM)) <= TOL for z in k["odeme_zamani"]]
            oran_parcalari.append(k)

    # deliveryDate'i olmayan semboller: son barin acilisi ile kapanisi arasi (uclar dahil).
    disi = sinif.loc[sinif["sinif"] == "exchangeInfo_disi"].sort_values("sembol")
    teslimsiz_parcalari, teslimsiz_sayim = [], []
    for r in disi.itertuples():
        donem = universe_modulu.sembol_donemleri(evren, r.sembol)[-1]
        acilis, kapanis = donem.bitis, donem.bitis + ADIM
        fund = funding_yukle(r.sembol)
        z = fund["odeme_zamani"]
        secim = (z >= acilis - TOL) & (z <= kapanis + TOL)
        teslimsiz_sayim.append((r.sembol, int(secim.sum()), len(fund) > 0))
        for _, x in fund.loc[secim].iterrows():
            konumlar.append({"sembol": r.sembol, "sinif": r.sinif, "deliveryDate": pd.NaT,
                             "son_bar_acilisi": acilis, "son_bar_kapanisi": kapanis,
                             "odeme_zamani": x["odeme_zamani"], "aralik_saat": x["aralik_saat"],
                             "konum": konum(x["odeme_zamani"], acilis, kapanis, None)})
        if secim.any() and argumanlar.oran_degerleri:
            k = oran_karsilastir(fund.loc[secim], fund.loc[z < acilis - TOL])
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

    konum_tablosu = pd.DataFrame(konumlar, columns=["sembol", "sinif", "deliveryDate", "son_bar_acilisi",
                                                    "son_bar_kapanisi", "odeme_zamani", "aralik_saat", "konum"])
    konum_tablosu.to_csv(CIKTI_KONUM, index=False, lineterminator="\n")
    print("\n--- Konumlar (yalnizca zaman; deger yok) ---")
    for s_, g in konum_tablosu.groupby("sinif"):
        print(f"{s_}: {len(g)} kayit, {g['sembol'].nunique()} sembol, {g['konum'].value_counts().to_dict()}")
    print(f"exchangeInfo disi: sembol {len(teslimsiz_sayim)}, funding kaydi olmayan "
          f"{sum(1 for _, _, v in teslimsiz_sayim if not v)}, son barda kaydi olmayan "
          f"{[s_ for s_, n, _ in teslimsiz_sayim if n == 0]}")

    if argumanlar.oran_degerleri:
        # 1093e69 kosusunun yeniden uretimi; degerler ekrana yazdirilmaz.
        pd.concat(oran_parcalari, ignore_index=True).to_csv(CIKTI_ORAN, index=False, lineterminator="\n")
        pd.concat(teslimsiz_parcalari, ignore_index=True).to_csv(CIKTI_TESLIMSIZ, index=False, lineterminator="\n")
        print(f"\n--oran-degerleri: {CIKTI_ORAN.name}, {CIKTI_TESLIMSIZ.name} yeniden yazildi (ekrana basilmadi)")

    # Oneri etkisi (1093e69'daki 43 kayit dokumu, ayni sinirlarla): ust sinir son
    # barin kapanisi yerine acilisi olsaydi kac kayit donem disina cikardi.
    # Alt uc `>` (1093e69 ile karsilastirilabilir).
    veri_sonu_bari = max(x.bitis for s_ in universe_modulu.dahil_semboller(evren)
                         for x in universe_modulu.sembol_donemleri(evren, s_))
    etki = []
    for sembol in universe_modulu.dahil_semboller(evren):
        fund = funding_yukle(sembol)
        zamanlar = pd.DatetimeIndex(fund["odeme_zamani"])
        donemler = universe_modulu.sembol_donemleri(evren, sembol)
        for i, d in enumerate(donemler):
            n = int(((zamanlar > d.bitis + TOL) & (zamanlar < d.bitis + ADIM + TOL)).sum())
            if n:
                etki.append((sembol, i, i == len(donemler) - 1, d.bitis, n))

    etki = pd.DataFrame(etki, columns=["sembol", "donem_sira", "son_donem", "donem_bitis", "kayit"])
    etki.to_csv(CIKTI_ONERI, index=False, lineterminator="\n")
    print("\n--- Oneri etkisi (1093e69 dokumu): (son bar acilisi + 1 dk, son bar kapanisi + 1 dk) ---")
    print(f"kayit: {int(etki['kayit'].sum())}, sembol: {etki['sembol'].nunique()}, "
          f"son donemde: {int(etki.loc[etki['son_donem'], 'kayit'].sum())}, "
          f"ara donemde: {int(etki.loc[~etki['son_donem'], 'kayit'].sum())}, "
          f"veri sonu donemi: {int(etki.loc[etki['donem_bitis'] == veri_sonu_bari, 'kayit'].sum())}")

    ortam_kaydi(git, baslangic, pd.Timestamp.now(tz="UTC")).to_csv(CIKTI_ORTAM, index=False, lineterminator="\n")
    print(f"\nCSV: {CIKTI.name}, {CIKTI_KONUM.name}, {CIKTI_ONERI.name}, {CIKTI_ORTAM.name}")


if __name__ == "__main__":
    main()
