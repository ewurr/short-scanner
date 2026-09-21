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
   kalacak kayit sayisi ve tamlik kontrolunun mevcut kural, D kurali ve aday
   kuralda (RESULTS §14.8) gecip gecmedigi (`a1_d_kurali_tam.csv`). Butun
   sutunlar veri katmaninin gordugu kayit tabanindan sayilir (D-A4).

DEGER OKUMAZ (denetci bulgusu D-B1, CLAUDE.md §3.1). Betik funding oran
sutunlarina (`oran`, `oran_8h`) hicbir yolda erismez; yalnizca odeme ZAMANI ve
odeme ARALIGI (saat) kullanilir. 1093e69'da oran degerleri ve isaretleri
raporlandi; bu, veri denetimi sinirini asti. O kosunun iz dosyalari calisma
agacindan kaldirildi ve 1093e69 commit'i icinde durur. Oran degeri ureten kod
yolu ve onu acan bayrak KALDIRILDI: bu degerleri yeniden uretmek bilincli bir
kod degisikligi ister (tests/test_a1_deger_yolu_yok.py bunu sabitler).

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
from calistir import (KosuKilidiHatasi, csv_yaz, donem_sonu_turleri, git_durumu,  # noqa: E402
                      kosu_kilidi, ortam_kaydi)
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

ADIM = pencere_modulu.adim(config.BAR_4H)
TOL = funding_modulu.ODEME_TOLERANSI
# D kurali tamlik olcumunde temsili pozisyon: cikis barinin acilisindan
# `config.DENETIM_TEMSILI_GIRIS_SURE` once girer (donem basindan once olamaz),
# donem sonunda cikar. Sure iki izgarada da aynidir; boylece olcum cikis anina
# odaklanir, giris penceresinin uzunluguna degil.
TEMSILI_GIRIS_SURE = pd.Timedelta(config.DENETIM_TEMSILI_GIRIS_SURE)

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


# --- D kurali olcumu (sayim; kod degismez) ------------------------------------


def donem_sonu_cikisi(donem, bar: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Donem sonunda cikilan barin acilisi ve cikis ani (= o barin kapanisi). Saf.

    `pencere.cikis_bari` donem sonunda cikisi "sinirdan onceki son barin KAPANISI"
    yapar. 4 saatlik izgarada bu bar `donem_bitis`te acilir. 1 gunluk izgarada
    (H3) `donem_bitis`i iceren gunun bari; acilisi o gunun 00:00'idir ve cikis
    ertesi gun 00:00 olur. Donem siniri her iki durumda da 4 saatlik bar
    duzeyindedir (on-kayit §2 rev.7).
    """
    adim_b = pencere_modulu.adim(bar)
    acilis = donem.bitis if bar == config.BAR_4H else donem.bitis.floor("1D")
    return acilis, acilis + adim_b


def d_kurali_olc(sembol: str, donemler, turler: list[str], fund: pd.DataFrame,
                 bar: str = config.BAR_4H) -> list[dict]:
    """Her donem sonunda D kuralinin disarida birakacagi kayit sayisi ve tamlik. Saf.

    Oran sutunlarina BAKMAZ; yalnizca odeme zamani ve araligi okunur.

    - Kayit tabani (denetci bulgusu D-A4): butun sutunlar veri katmaninin
      gordugu seriden (`donem_sonrasi_kayitlari_at`, ust sinir son 4 saatlik
      barin kapanisi + 1 dk) sayilir; 4 saatlik ve 1 gunluk satirlar ayni
      tabandandir. Mevcut kuralin zaten attigi kayitlar hicbir sutuna girmez.
    - `disarida_kalan`: `donem_bitis + 1 dk <= p < cikis_ani + 1 dk`. Mevcut ust
      sinir cikis ani + 1 dk; D kurali donem bitisini (son gercek 4 saatlik barin
      acilisi, dahil) ust sinir yapar. Veri sonu doneminde kural uygulanmaz (sayi
      yine yazilir, `kural_uygulanir=False`).
    - Tamlik: veri katmaninin gordugu seri (`donem_sonrasi_kayitlari_at`)
      uzerinde, cikis barinin acilisindan `TEMSILI_GIRIS_SURE` once (ya da
      donem basinda) giren ve donem sonunda cikan temsili pozisyon icin
      `_odemeler_tam_mi`. Mevcut kural: `[giris + 1 dk, cikis_ani + 1 dk)`.
      D kurali: `[giris + 1 dk, donem_bitis + 1 dk)`, son odeme buna gore aranir.
      False = pozisyon funding'i NaN olur (pozisyon duser).
    - `bar`: cikis izgarasi. 4h = H1/H2, 1d = H3.
    - `kapanista_odeme`: cikis aninda (1 dk tolerans) odeme kaydi var mi. Mevcut
      kuralin tamlik kontrolu bu kaydi arar.
    - Aday kural (RESULTS §14.8; on-kayit revizyonu bekliyor, KODA GECMEDI):
      1 gunluk bar yalnizca donem ici 4 saatlik barlardan kurulur; donem sonuna
      ulasan pozisyon her izgarada son donem ici 4 saatlik barin kapanisindan
      cikar (`cikis_ani_aday = donem_bitis + 4h`) ve funding penceresi D
      kuralidir. `tamlik_aday` bunun sonucudur. 4 saatlik izgarada aday kural D
      kuraliyla aynidir. 1 gunluk izgarada temsili pozisyon, donemin tamamen
      icinde kalan son UTC gununun acilisinda girer (`giris_aday`; donem
      basindan once olamaz).
    - `son_odeme_aralik_saat`: donem bitisine kadarki son odemenin aralik saati;
      tamligin neden gectigini ya da kaldigini bu sutun acikliyor (8 saatlik bir
      ritim cikis anina yetisir, 2 ya da 4 saatlik ritim yetismez).
    """
    adim_b = pencere_modulu.adim(bar)
    satirlar = []
    seri = funding_modulu.donem_sonrasi_kayitlari_at(fund, donemler, config.BAR_4H) if len(fund) else fund
    zam = pd.DatetimeIndex(seri["odeme_zamani"]) if len(seri) else pd.DatetimeIndex([], tz="UTC")
    araliklar = (pd.to_numeric(seri["aralik_saat"], errors="coerce").to_numpy(dtype=float)
                 if len(seri) else np.empty(0))
    for i, (d, tur) in enumerate(zip(donemler, turler)):
        cikis_acilis, cikis_ani = donem_sonu_cikisi(d, bar)
        disarida = int(((zam >= d.bitis + TOL) & (zam < cikis_ani + TOL)).sum())
        giris = max(d.baslangic, cikis_acilis - TEMSILI_GIRIS_SURE)
        alt = giris + TOL
        cikis_ani_aday = d.bitis + ADIM
        if bar == config.BAR_4H:
            giris_aday = giris
        else:
            giris_aday = max(d.baslangic, cikis_ani_aday.floor("1D") - adim_b)
        alt_aday = giris_aday + TOL
        son_aralik = float("nan")
        if len(seri):
            oncekiler = np.flatnonzero(np.asarray(zam <= d.bitis + TOL, dtype=bool))
            if len(oncekiler):
                son_aralik = float(araliklar[oncekiler[-1]])
            ust_m = cikis_ani + TOL
            ust_d = d.bitis + TOL
            maske_m = np.asarray((zam >= alt) & (zam < ust_m), dtype=bool)
            maske_d = np.asarray((zam >= alt) & (zam < ust_d), dtype=bool)
            tam_m = funding_modulu._odemeler_tam_mi(seri, zam, maske_m, alt, ust_m, d.baslangic)
            tam_d = funding_modulu._odemeler_tam_mi(seri, zam, maske_d, alt, ust_d, d.baslangic)
            maske_a = np.asarray((zam >= alt_aday) & (zam < ust_d), dtype=bool)
            tam_a = funding_modulu._odemeler_tam_mi(seri, zam, maske_a, alt_aday, ust_d, d.baslangic)
        else:
            tam_m = tam_d = tam_a = False
        satirlar.append({"sembol": sembol, "bar": bar, "donem_sira": i, "donem_bitis": d.bitis,
                         "cikis_ani": cikis_ani, "tur": tur,
                         "kural_uygulanir": tur != "veri_sonu", "disarida_kalan": disarida,
                         "kapanista_odeme": bool((abs(zam - cikis_ani) <= TOL).any()) if len(zam) else False,
                         "son_odeme_aralik_saat": son_aralik,
                         "tamlik_mevcut": bool(tam_m), "tamlik_d": bool(tam_d),
                         "giris_aday": giris_aday, "cikis_ani_aday": cikis_ani_aday,
                         "tamlik_aday": bool(tam_a)})
    return satirlar


# --- Ana akis ----------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    # Betigin secenegi yoktur: oran degeri ureten kod yolu kaldirildi (D-B1).
    argparse.ArgumentParser().parse_args(argv)
    # Kosu kilidi cikti dizininde (sizinti testcisi bulgusu): ikinci kosu hicbir
    # sey yazmadan reddedilir; kilit hata durumunda da birakilir.
    with kosu_kilidi("a1_olcumu", CIKTI_D.parent):
        _kos()


def _kos() -> None:
    baslangic = pd.Timestamp.now(tz="UTC")
    git = git_durumu()

    evren = universe_modulu.evren_yukle()
    sinif = universe_modulu.delist_sinifi(evren, universe_modulu.exchange_info_anlik_yukle())
    sinif_haritasi = sinif.set_index("sembol")["sinif"].to_dict()
    settling = sinif.loc[sinif["sinif"] == universe_modulu.SETTLING_DURUMU].sort_values("sembol")

    satirlar, sayim, konumlar = [], [], []
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
    # deliveryDate'i olmayan semboller: son barin acilisi ile kapanisi arasi (uclar dahil).
    disi = sinif.loc[sinif["sinif"] == "exchangeInfo_disi"].sort_values("sembol")
    teslimsiz_sayim = []
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
    tablo = pd.DataFrame(satirlar, columns=["sembol", "deliveryDate", "donem_bitis", "odeme_zamani",
                                            "teslimden_sonra_saat", "aralik_saat", "cikis_anina_denk"])
    csv_yaz(tablo, CIKTI)
    etkilenen = sum(1 for _, n in sayim if n)
    print(f"SETTLING sembol: {len(sayim)}")
    print(f"uzlasma sonrasi donem icinde kalan kayit: {len(tablo)} ({etkilenen} sembol)")
    print(f"  bunlardan cikis anina denk gelen: {int(tablo['cikis_anina_denk'].sum())} "
          f"({tablo.loc[tablo['cikis_anina_denk'], 'sembol'].nunique()} sembol)")
    if len(tablo):
        print(tablo.groupby("aralik_saat").size().rename("kayit").to_string())

    konum_tablosu = pd.DataFrame(konumlar, columns=["sembol", "sinif", "deliveryDate", "son_bar_acilisi",
                                                    "son_bar_kapanisi", "odeme_zamani", "aralik_saat", "konum"])
    csv_yaz(konum_tablosu, CIKTI_KONUM)
    print("\n--- Konumlar (yalnizca zaman; deger yok) ---")
    for s_, g in konum_tablosu.groupby("sinif"):
        print(f"{s_}: {len(g)} kayit, {g['sembol'].nunique()} sembol, {g['konum'].value_counts().to_dict()}")
    print(f"exchangeInfo disi: sembol {len(teslimsiz_sayim)}, funding kaydi olmayan "
          f"{sum(1 for _, _, v in teslimsiz_sayim if not v)}, son barda kaydi olmayan "
          f"{[s_ for s_, n, _ in teslimsiz_sayim if n == 0]}")

    # Oneri etkisi (1093e69'daki 43 kayit dokumu, ayni sinirlarla): ust sinir son
    # barin kapanisi yerine acilisi olsaydi kac kayit donem disina cikardi.
    # Alt uc `>` (1093e69 ile karsilastirilabilir); D kurali olcumu `>=` kullanir.
    donem_bitisleri = [x.bitis for s_ in universe_modulu.dahil_semboller(evren)
                       for x in universe_modulu.sembol_donemleri(evren, s_)]
    # Hic donemi olmayan evrende cokmek yerine bos olcum: veri sonu bari
    # tanimsizdir, hicbir donem sonu "veri_sonu" sayilmaz.
    veri_sonu_bari = max(donem_bitisleri) if donem_bitisleri else pd.Timestamp.min.tz_localize("UTC")
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
        for bar in (config.BAR_4H, config.BAR_1D):
            d_satirlari += d_kurali_olc(sembol, donemler, turler, fund, bar)

    etki = pd.DataFrame(etki, columns=["sembol", "donem_sira", "son_donem", "donem_bitis", "kayit"])
    csv_yaz(etki, CIKTI_ONERI)
    print("\n--- Oneri etkisi (1093e69 dokumu): (son bar acilisi + 1 dk, son bar kapanisi + 1 dk) ---")
    print(f"kayit: {int(etki['kayit'].sum())}, sembol: {etki['sembol'].nunique()}, "
          f"son donemde: {int(etki.loc[etki['son_donem'], 'kayit'].sum())}, "
          f"ara donemde: {int(etki.loc[~etki['son_donem'], 'kayit'].sum())}, "
          f"veri sonu donemi: {int(etki.loc[etki['donem_bitis'] == veri_sonu_bari, 'kayit'].sum())}")

    d_tablo = pd.DataFrame(d_satirlari, columns=["sembol", "bar", "donem_sira", "donem_bitis", "cikis_ani",
                                                 "tur", "kural_uygulanir", "disarida_kalan", "kapanista_odeme",
                                                 "son_odeme_aralik_saat", "tamlik_mevcut", "tamlik_d",
                                                 "giris_aday", "cikis_ani_aday", "tamlik_aday"])
    csv_yaz(d_tablo, CIKTI_D)
    for bar in (config.BAR_4H, config.BAR_1D):
        print(f"\n--- D kurali, cikis izgarasi {bar} (sayim; kod degismedi) ---")
        b = d_tablo.loc[d_tablo["bar"] == bar]
        for tur in SON_TURLERI:
            g = b.loc[b["tur"] == tur]
            if g.empty:
                continue
            print(f"{tur:26s} donem sonu {len(g):4d} | disarida kalan kayit {int(g['disarida_kalan'].sum()):4d} "
                  f"({int((g['disarida_kalan'] > 0).sum())} donem sonu) | kapanista odeme "
                  f"{int(g['kapanista_odeme'].sum()):4d} | tamlik bozuk: mevcut "
                  f"{int((~g['tamlik_mevcut']).sum())}, D {int((~g['tamlik_d']).sum())}, "
                  f"aday {int((~g['tamlik_aday']).sum())} | "
                  f"mevcutta tam D'de bozuk {int((g['tamlik_mevcut'] & ~g['tamlik_d']).sum())}, "
                  f"mevcutta bozuk D'de tam {int((~g['tamlik_mevcut'] & g['tamlik_d']).sum())}")
    # Kapanista odemesi olmayip mevcut kuralda yine de gecen donem sonlari: son
    # odemenin aralik saatine gore (8 saatlik ritim cikis anina yetisir).
    kap = d_tablo.loc[(d_tablo["bar"] == config.BAR_4H) & (d_tablo["tur"] == "delist_SETTLING")]
    print("\nSETTLING, kapanista odeme yok:",
          kap.loc[~kap["kapanista_odeme"]].groupby(["son_odeme_aralik_saat", "tamlik_mevcut"]).size().to_dict())
    print("FTTUSDT son odeme araligi:",
          d_tablo.loc[(d_tablo["sembol"] == "FTTUSDT") & (d_tablo["bar"] == config.BAR_4H),
                      "son_odeme_aralik_saat"].tolist())

    csv_yaz(ortam_kaydi(git, baslangic, pd.Timestamp.now(tz="UTC")), CIKTI_ORTAM)
    print(f"\nCSV: {CIKTI.name}, {CIKTI_KONUM.name}, {CIKTI_ONERI.name}, {CIKTI_D.name}, {CIKTI_ORTAM.name}")


if __name__ == "__main__":
    try:
        main()
    except KosuKilidiHatasi as hata:
        raise SystemExit(f"HATA: {hata}") from None
