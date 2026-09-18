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
4. D kurali (on-kayit revizyonu bekliyor, KODA GECMEDI): donem sonu cikislarinda
   funding penceresi son barin acilisinda (dahil) biter, veri sonu donemi haric;
   tamlik kontrolu son odemeyi buna gore arar. Donem sonu turune gore disarida
   kalacak kayit sayisi ve tamlik kontrolunun mevcut kural ile D kuralinda
   gecip gecmedigi (`a1_d_kurali_tam.csv`).

DEGER RAPORLAMAZ (denetci bulgusu D-B1, CLAUDE.md §3.1). Uzlasma sonrasi
kayitlar donem sonunu asan pozisyonlarin net getirisine girebilecek turdendir.
1093e69'da oran degerleri ve isaretleri raporlandi; bu, veri denetimi sinirini
asti ve rapordan cikarildi. O kosunun ham ciktilari
(`a1_uzlasma_sonrasi_oranlar_tam.csv`, `a1_teslimsiz_son_bar_funding_tam.csv`)
iz icin depoda durur. Varsayilan kosu bu dosyalari URETMEZ ve oran degeri
yazdirmaz; yalnizca `--oran-degerleri` bayragiyla, o kosunun yeniden uretimi
icin yazilir. Bu bayrak yeni bir analiz icin kullanilmaz.

Getiri, pozisyon funding'i ya da olay hesaplamaz. Veri katmani kodunu
degistirmez; D kurali yalnizca bu betikte, sayim icin taklit edilir.

Kullanim:
    python analysis/00_veri_denetimi/a1_olcumu.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

KOK = Path(__file__).resolve().parents[2]
BU_DIZIN = Path(__file__).resolve().parent
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(BU_DIZIN))

import config  # noqa: E402
from calistir import git_durumu, ortam_kaydi  # noqa: E402
from data import donem as donem_modulu  # noqa: E402
from data import funding as funding_modulu  # noqa: E402
from data import klines as klines_modulu  # noqa: E402
from data import pencere as pencere_modulu  # noqa: E402
from data import universe as universe_modulu  # noqa: E402

CIKTI = BU_DIZIN / "a1_uzlasma_sonrasi_funding_tam.csv"
CIKTI_KONUM = BU_DIZIN / "a1_konumlar_tam.csv"
CIKTI_ONERI = BU_DIZIN / "a1_oneri_etkisi_tam.csv"
CIKTI_D = BU_DIZIN / "a1_d_kurali_tam.csv"
CIKTI_ORTAM = BU_DIZIN / "a1_ortam_tam.csv"
# Yalnizca --oran-degerleri ile (1093e69 kosusunun yeniden uretimi).
CIKTI_ORAN = BU_DIZIN / "a1_uzlasma_sonrasi_oranlar_tam.csv"
CIKTI_TESLIMSIZ = BU_DIZIN / "a1_teslimsiz_son_bar_funding_tam.csv"
REFERANS_KAYIT = 30

ADIM = pencere_modulu.adim(config.BAR_4H)
TOL = funding_modulu.ODEME_TOLERANSI
# D kurali tamlik olcumunde temsili pozisyon: son bar acilisindan 6 bar (24 saat)
# once girer, donem sonunda cikar. 24 saat en uzun odeme araligindan (8 saat)
# uzundur; boylece son odemeler zincirin icindedir.
TEMSILI_GIRIS_BAR = 6

SON_TURLERI = ("delist_SETTLING", "delist_exchangeInfo_disi", "dolgu_kosusu", "uzun_bosluk",
               "diger_son_donem", "veri_sonu")


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


# --- D kurali olcumu (sayim; kod degismez) ------------------------------------


def donem_sonu_turleri(donemler, sinif: str | None, veri_sonu_bari: pd.Timestamp,
                       zamanlar: pd.DatetimeIndex | None = None, hacim=None) -> list[str]:
    """Her donemin sonu ne ile bitiyor. Saf.

    Son donem: delist sinifi (SETTLING / exchangeInfo disi), veri sonu
    (`bitis == veri_sonu_bari`) ya da diger. Ic donem sonu: iki donem arasinda
    6+ barlik sifir hacim kosusu varsa `dolgu_kosusu`, yoksa `uzun_bosluk`
    (on-kayit §2 rev.7: donemi bolen yalnizca bu ikisidir). Ic donem icin mumlar
    (`zamanlar`, `hacim`) gerekir.
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


def d_kurali_olc(sembol: str, donemler, turler: list[str], fund: pd.DataFrame) -> list[dict]:
    """Her donem sonunda D kuralinin disarida birakacagi kayit sayisi ve tamlik. Saf.

    - `disarida_kalan`: `bitis + 1 dk <= p < bitis + 4h + 1 dk`. Mevcut ust sinir
      `_donem_icinde`'deki son bar kapanisi + 1 dk; D kurali son bar acilisini
      (dahil) ust sinir yapar. Veri sonu doneminde kural uygulanmaz (sayi yine
      yazilir, `kural_uygulanir=False`).
    - Tamlik: veri katmaninin gordugu seri (`donem_sonrasi_kayitlari_at`)
      uzerinde, son bar acilisindan `TEMSILI_GIRIS_BAR` bar once (ya da donem
      basinda) giren ve donem sonunda cikan temsili pozisyon icin
      `_odemeler_tam_mi`. Mevcut kural: `[giris + 1 dk, bitis + 4h + 1 dk)`.
      D kurali: `[giris + 1 dk, bitis + 1 dk)`, son odeme buna gore aranir.
      False = pozisyon funding'i NaN olur (pozisyon duser).
    """
    satirlar = []
    zam_ham = pd.DatetimeIndex(fund["odeme_zamani"]) if len(fund) else pd.DatetimeIndex([], tz="UTC")
    seri = funding_modulu.donem_sonrasi_kayitlari_at(fund, donemler, config.BAR_4H) if len(fund) else fund
    zam = pd.DatetimeIndex(seri["odeme_zamani"]) if len(seri) else pd.DatetimeIndex([], tz="UTC")
    for i, (d, tur) in enumerate(zip(donemler, turler)):
        disarida = int(((zam_ham >= d.bitis + TOL) & (zam_ham < d.bitis + ADIM + TOL)).sum())
        giris = max(d.baslangic, d.bitis - TEMSILI_GIRIS_BAR * ADIM)
        alt = giris + TOL
        if len(seri):
            ust_m = d.bitis + ADIM + TOL
            ust_d = d.bitis + TOL
            maske_m = np.asarray((zam >= alt) & (zam < ust_m), dtype=bool)
            maske_d = np.asarray((zam >= alt) & (zam < ust_d), dtype=bool)
            tam_m = funding_modulu._odemeler_tam_mi(seri, zam, maske_m, alt, ust_m, d.baslangic)
            tam_d = funding_modulu._odemeler_tam_mi(seri, zam, maske_d, alt, ust_d, d.baslangic)
        else:
            tam_m = tam_d = False
        satirlar.append({"sembol": sembol, "donem_sira": i, "donem_bitis": d.bitis, "tur": tur,
                         "kural_uygulanir": tur != "veri_sonu", "disarida_kalan": disarida,
                         "tamlik_mevcut": bool(tam_m), "tamlik_d": bool(tam_d)})
    return satirlar


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
    # Alt uc `>` (1093e69 ile karsilastirilabilir); D kurali olcumu `>=` kullanir.
    veri_sonu_bari = max(x.bitis for s_ in universe_modulu.dahil_semboller(evren)
                         for x in universe_modulu.sembol_donemleri(evren, s_))
    etki, d_satirlari = [], []
    for sembol in universe_modulu.dahil_semboller(evren):
        fund = funding_yukle(sembol)
        zamanlar = pd.DatetimeIndex(fund["odeme_zamani"])
        donemler = universe_modulu.sembol_donemleri(evren, sembol)
        for i, d in enumerate(donemler):
            n = int(((zamanlar > d.bitis + TOL) & (zamanlar < d.bitis + ADIM + TOL)).sum())
            if n:
                etki.append((sembol, i, i == len(donemler) - 1, d.bitis, n))
        if not donemler:
            continue
        mz = hacim = None
        if len(donemler) > 1:
            mumlar = donem_modulu.toplam_doneme_kes(klines_modulu.ham_mumlari_yukle(sembol, config.BAR_4H),
                                                     "open_time")
            mz, hacim = pd.DatetimeIndex(mumlar["open_time"]), mumlar["quote_volume"]
        turler = donem_sonu_turleri(donemler, sinif_haritasi.get(sembol), veri_sonu_bari, mz, hacim)
        d_satirlari += d_kurali_olc(sembol, donemler, turler, fund)

    etki = pd.DataFrame(etki, columns=["sembol", "donem_sira", "son_donem", "donem_bitis", "kayit"])
    etki.to_csv(CIKTI_ONERI, index=False, lineterminator="\n")
    print("\n--- Oneri etkisi (1093e69 dokumu): (son bar acilisi + 1 dk, son bar kapanisi + 1 dk) ---")
    print(f"kayit: {int(etki['kayit'].sum())}, sembol: {etki['sembol'].nunique()}, "
          f"son donemde: {int(etki.loc[etki['son_donem'], 'kayit'].sum())}, "
          f"ara donemde: {int(etki.loc[~etki['son_donem'], 'kayit'].sum())}, "
          f"veri sonu donemi: {int(etki.loc[etki['donem_bitis'] == veri_sonu_bari, 'kayit'].sum())}")

    d_tablo = pd.DataFrame(d_satirlari, columns=["sembol", "donem_sira", "donem_bitis", "tur", "kural_uygulanir",
                                                 "disarida_kalan", "tamlik_mevcut", "tamlik_d"])
    d_tablo.to_csv(CIKTI_D, index=False, lineterminator="\n")
    print("\n--- D kurali (sayim; kod degismedi) ---")
    for tur in SON_TURLERI:
        g = d_tablo.loc[d_tablo["tur"] == tur]
        if g.empty:
            continue
        print(f"{tur:26s} donem sonu {len(g):4d} | disarida kalan kayit {int(g['disarida_kalan'].sum()):4d} "
              f"({int((g['disarida_kalan'] > 0).sum())} donem sonu) | tamlik bozuk: mevcut "
              f"{int((~g['tamlik_mevcut']).sum())}, D {int((~g['tamlik_d']).sum())} | "
              f"mevcutta tam D'de bozuk {int((g['tamlik_mevcut'] & ~g['tamlik_d']).sum())}, "
              f"mevcutta bozuk D'de tam {int((~g['tamlik_mevcut'] & g['tamlik_d']).sum())}")

    ortam_kaydi(git, baslangic, pd.Timestamp.now(tz="UTC")).to_csv(CIKTI_ORTAM, index=False, lineterminator="\n")
    print(f"\nCSV: {CIKTI.name}, {CIKTI_KONUM.name}, {CIKTI_ONERI.name}, {CIKTI_D.name}, {CIKTI_ORTAM.name}")


if __name__ == "__main__":
    main()
