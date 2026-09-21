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
4. Donem sonu funding tamligi (on-kayit §4 rev.8, D kurali artik veri katmaninda):
   donem sonuna ulasan temsili pozisyonun gercek plani (`pencere.pozisyon_plani`) ve
   gercek tamlik kosullari (`funding.funding_tamlik_ayrintisi`), donem sonu turune
   gore; istisnanin disarida biraktigi kayitlar ve donemin funding sinifi
   (`a1_d_kurali_tam.csv`). Kayit tabani veri katmaninin gordugu seridir (D-A4).

DEGER OKUMAZ (denetci bulgusu D-B1, CLAUDE.md §3.1). Betik funding oran
sutunlarina (`oran`, `oran_8h`) hicbir yolda erismez; yalnizca odeme ZAMANI ve
odeme ARALIGI (saat) kullanilir. 1093e69'da oran degerleri ve isaretleri
raporlandi; bu, veri denetimi sinirini asti. O kosunun iz dosyalari calisma
agacindan kaldirildi ve 1093e69 commit'i icinde durur. Oran degeri ureten kod
yolu ve onu acan bayrak KALDIRILDI: bu degerleri yeniden uretmek bilincli bir
kod degisikligi ister (tests/test_a1_deger_yolu_yok.py bunu sabitler).

Getiri, pozisyon funding'i ya da olay hesaplamaz. Veri katmani kodunu degistirmez
ve kurallarin kopyasini tasimaz: cikis ve funding kurallari veri katmanindan
cagrilir (denetci bulgusu D-B3; tests/test_a1_gercek_kod.py).

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
# Zaman karsilastirmalari yalnizca on-kayit §4 rev.8 "Zaman toleransi" yardimcilariyla.
P = pencere_modulu
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
    sonra = icinde & P.sonra(zamanlar, teslim)
    cikis_ani = P.donem_kapanisi(donem.bitis)
    return [
        {"sembol": sembol, "deliveryDate": teslim, "donem_bitis": donem.bitis, "odeme_zamani": z,
         "teslimden_sonra_saat": (z - teslim) / pd.Timedelta(hours=1),
         "aralik_saat": a,
         "cikis_anina_denk": P.ayni_an(z, cikis_ani)}
        for z, a in zip(zamanlar[sonra], fund.loc[sonra, "aralik_saat"])
    ]


def konum(z: pd.Timestamp, acilis: pd.Timestamp, kapanis: pd.Timestamp,
          teslim: pd.Timestamp | None) -> str:
    """Kaydin son bara ve deliveryDate'e gore yeri (1 dk tolerans). Saf."""
    if P.ayni_an(z, acilis):
        yer = "son_bar_acilisi"
    elif P.ayni_an(z, kapanis):
        yer = "son_bar_kapanisi"
    elif P.sonra(z, acilis) and P.once(z, kapanis):
        yer = "son_bar_ici"
    elif P.once(z, acilis):
        yer = "son_bardan_once"
    else:
        yer = "son_bardan_sonra"
    if teslim is None or pd.isna(teslim):
        return yer
    if P.ayni_an(z, teslim):
        return f"{yer}|teslim_aninda"
    return f"{yer}|teslimden_{'sonra' if P.sonra(z, teslim) else 'once'}"


# --- Donem sonu funding tamligi: gercek kod yoluyla sayim (on-kayit §4 rev.8) ----------
#
# Rev.8 oncesi bu bolum D kuralini ve cikis kuralini betik icinde TAKLIT ediyordu
# (`donem_sonu_cikisi`, elle kurulan pencere maskeleri; denetci bulgusu D-B3). Rev.8
# ile kural veri katmanina gecti; kopya silindi. Temsili pozisyon gercek
# `pencere.pozisyon_plani` ile kurulur, tamlik gercek `funding.funding_tamlik_ayrintisi`
# ile olculur (tests/test_a1_gercek_kod.py).

SUTUNLAR_D = ["sembol", "bar", "donem_sira", "donem_bitis", "tur", "kural_uygulanir", "temsili_sinyal",
              "giris", "cikis_turu", "cikis_ani", "ret_gerekcesi", "disarida_kalan", "kapanista_odeme",
              "son_odeme_aralik_saat", *funding_modulu.TAMLIK_KOSULLARI, "tamlik", "funding_var"]


def temsili_plan(donem, bar: str):
    """Donem sonuna ulasan temsili pozisyon: gercek `pencere.pozisyon_plani` (on-kayit §4 rev.8).

    Giris bari (t kapanisi, on-kayit §4 rev.8): 4h izgarada son bardan
    `TEMSILI_GIRIS_SURE` once (donem basindan sonraki ilk bardan once olamaz); 1d
    izgarada B'yi iceren gunun 00:00 bari, sinyal bir onceki tam gun. Ufuk ve ileri
    kayma siniri hipotezin birincil ufkudur (`config.BIRINCIL_UFUK`), boylece cikis
    donem sonudur. Seri donemin 4h izgarasidir (mumlar okunmaz): olculen sey donem
    sonundaki funding tamligidir, giris barinin varligi degil. Kume toplam donemdir;
    "verinin sonu donem sonu degildir" (§4 "Donem sonu ve cikis") geregi veri sonu
    donemleri kume olcutuyle reddedilir. Olusmazsa `pencere.OlayOlusmaz` ya da
    `pencere.DonemDisiSinyal` firlatir (kisa donemde sinyal gunu donem disi).
    """
    birincil = config.BIRINCIL_UFUK[bar]
    adim_bar = pencere_modulu.adim(bar)
    if bar == config.BAR_1D:
        giris = donem.bitis.floor("D")
    else:
        giris = max(donem.bitis - TEMSILI_GIRIS_SURE, donem.baslangic + ADIM)
    t = giris - adim_bar
    zamanlar = pd.date_range(donem.baslangic, donem.bitis, freq=ADIM)
    return pencere_modulu.pozisyon_plani(
        zamanlar, t, birincil, bar, birincil_ufuk=birincil,
        kume_baslangic=pd.Timestamp(config.DONEM_BASI), kume_bitis=pd.Timestamp(config.DONEM_SONU),
        donem_baslangic=donem.baslangic, donem_bitis=donem.bitis)


def d_kurali_olc(sembol: str, donemler, turler: list[str], fund: pd.DataFrame,
                 bar: str = config.BAR_4H) -> list[dict]:
    """Her donem sonunda rev.8 funding kurallarinin sayimi, GERCEK kod yoluyla. Saf.

    Oran sutunlarina BAKMAZ; yalnizca odeme zamani ve araligi okunur. Kayit tabani
    veri katmaninin gordugu seridir (`funding.donem_sonrasi_kayitlari_at`, K'dan
    sonrasi atilir; D-A4).

    - `temsili_sinyal`, `giris`, `cikis_turu`, `cikis_ani`, `ret_gerekcesi`:
      `temsili_plan` (gercek plan). Olusmazsa ret gerekcesi yazilir, tamlik False.
    - `disarida_kalan`: B'den sonra ve K ile ayni an ya da once gelen kayit sayisi;
      "Donem sonu istisnasi"nin disarida biraktigi kayitlar.
    - `kapanista_odeme`: K ile ayni an bir kayit var mi.
    - `son_odeme_aralik_saat`: B ile ayni an ya da onceki son kaydin araligi.
    - `kayit_var` ... `son_tam`, `tamlik`: `funding.funding_tamlik_ayrintisi` (gercek).
      False = pozisyonun funding'i tam degil, olay tek karar noktasinda olusmaz.
    - `funding_var`: `funding.donemde_funding_var` (gercek; sayim penceresi [bas, B]).
    - `kural_uygulanir`: donem sonu turu veri sonu degil.
    """
    satirlar = []
    seri = funding_modulu.donem_sonrasi_kayitlari_at(fund, donemler, config.BAR_4H) if len(fund) else fund
    zam = pd.DatetimeIndex(seri["odeme_zamani"]) if len(seri) else pd.DatetimeIndex([], tz="UTC")
    araliklar = (pd.to_numeric(seri["aralik_saat"], errors="coerce").to_numpy(dtype=float)
                 if len(seri) else np.empty(0))
    for i, (d, tur) in enumerate(zip(donemler, turler)):
        satir = {"sembol": sembol, "bar": bar, "donem_sira": i, "donem_bitis": d.bitis, "tur": tur,
                 "kural_uygulanir": tur != "veri_sonu", "temsili_sinyal": pd.NaT, "giris": pd.NaT,
                 "cikis_turu": None, "cikis_ani": pd.NaT, "ret_gerekcesi": None,
                 **{k: False for k in funding_modulu.TAMLIK_KOSULLARI}, "tamlik": False}
        try:
            plan = temsili_plan(d, bar)
        except pencere_modulu.OlayOlusmaz as hata:
            plan, satir["ret_gerekcesi"] = None, pencere_modulu.ret_gerekcesi(hata)
        except pencere_modulu.DonemDisiSinyal:
            plan, satir["ret_gerekcesi"] = None, "donem_disi_sinyal"
        k = d.kapanis if hasattr(d, "kapanis") else pencere_modulu.donem_kapanisi(d.bitis)
        satir["disarida_kalan"] = int(np.sum(P.sonra(zam, d.bitis) & P.ayni_ya_da_once(zam, k))) if len(zam) else 0
        satir["kapanista_odeme"] = bool(np.any(P.ayni_an(zam, k))) if len(zam) else False
        oncekiler = np.flatnonzero(np.asarray(P.ayni_ya_da_once(zam, d.bitis), dtype=bool)) if len(zam) else []
        satir["son_odeme_aralik_saat"] = float(araliklar[oncekiler[-1]]) if len(oncekiler) else float("nan")
        if plan is not None:
            satir.update(temsili_sinyal=plan.sinyal_zamani, giris=plan.giris, cikis_turu=plan.cikis_turu,
                         cikis_ani=plan.cikis_ani)
            ayrinti = funding_modulu.funding_tamlik_ayrintisi(
                seri, [plan.giris], [funding_modulu.funding_penceresi_sonu(plan)]).iloc[0]
            satir.update({k_: bool(ayrinti[k_]) for k_ in (*funding_modulu.TAMLIK_KOSULLARI, "tam")})
            satir["tamlik"] = satir.pop("tam")
        satir["funding_var"] = funding_modulu.donemde_funding_var(fund, d, config.BAR_4H)
        satirlar.append(satir)
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
                             "son_bar_acilisi": donem.bitis, "son_bar_kapanisi": donem.kapanis,
                             "odeme_zamani": x["odeme_zamani"], "aralik_saat": x["aralik_saat"],
                             "konum": konum(x["odeme_zamani"], donem.bitis, donem.kapanis, r.deliveryDate)})
    # deliveryDate'i olmayan semboller: son barin acilisi ile kapanisi arasi (uclar dahil).
    disi = sinif.loc[sinif["sinif"] == "exchangeInfo_disi"].sort_values("sembol")
    teslimsiz_sayim = []
    for r in disi.itertuples():
        donem = universe_modulu.sembol_donemleri(evren, r.sembol)[-1]
        acilis, kapanis = donem.bitis, donem.kapanis
        fund = funding_yukle(r.sembol)
        z = fund["odeme_zamani"]
        secim = P.ayni_ya_da_sonra(z, acilis) & P.ayni_ya_da_once(z, kapanis)
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
    # Donem bitisinden SONRA (ayni an degil) ve son barin kapanisiyla ayni an ya da once.
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
            n = int((P.sonra(zamanlar, d.bitis) & P.ayni_ya_da_once(zamanlar, d.kapanis)).sum())
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

    d_tablo = pd.DataFrame(d_satirlari, columns=SUTUNLAR_D)
    # Evren tablosundaki (kilitli, rev.7 penceresiyle uretilmis) funding sinifi, karsilastirma icin.
    fy = evren.loc[evren["donem_id"] >= 0].set_index(["sembol", "donem_id"])["donem_funding_yok"]
    d_tablo["funding_yok_evren"] = [bool(fy.get((s_, i_), False)) for s_, i_ in
                                    zip(d_tablo["sembol"], d_tablo["donem_sira"])]
    csv_yaz(d_tablo, CIKTI_D)
    for bar in (config.BAR_4H, config.BAR_1D):
        print(f"\n--- Donem sonu funding tamligi, izgara {bar} (gercek kod; deger yok) ---")
        b_ = d_tablo.loc[d_tablo["bar"] == bar]
        for tur in SON_TURLERI:
            g = b_.loc[b_["tur"] == tur]
            if g.empty:
                continue
            olusan = g.loc[g["ret_gerekcesi"].isna()]
            print(f"{tur:26s} donem sonu {len(g):4d} | plan olustu {len(olusan):4d} "
                  f"(ret: {g['ret_gerekcesi'].value_counts().to_dict()}) | tamlik bozuk {int((~olusan['tamlik']).sum())} "
                  f"| yalniz baslangic {int((olusan['kayit_var'] & olusan['aralik_gecerli'] & ~olusan['baslangic_tam'] & olusan['ic_tam'] & olusan['son_tam']).sum())} "
                  f"| disarida kalan kayit {int(g['disarida_kalan'].sum())} ({int((g['disarida_kalan'] > 0).sum())}) "
                  f"| K'da odeme {int(g['kapanista_odeme'].sum())}")
    fs = d_tablo.loc[d_tablo["bar"] == config.BAR_4H]
    print("\n--- Funding sinifi: evren tablosu (rev.7 penceresi) -> gercek kod (rev.8, [bas, B]) ---")
    for tur in SON_TURLERI:
        g = fs.loc[fs["tur"] == tur]
        if g.empty:
            continue
        print(f"{tur:26s} donem {len(g):4d} | funding'siz: evren {int(g['funding_yok_evren'].sum())}, "
              f"rev.8 {int((~g['funding_var']).sum())} | funding'li -> funding'siz "
              f"{int((~g['funding_yok_evren'] & ~g['funding_var']).sum())}, funding'siz -> funding'li "
              f"{int((g['funding_yok_evren'] & g['funding_var']).sum())}")

    csv_yaz(ortam_kaydi(git, baslangic, pd.Timestamp.now(tz="UTC")), CIKTI_ORTAM)
    print(f"\nCSV: {CIKTI.name}, {CIKTI_KONUM.name}, {CIKTI_ONERI.name}, {CIKTI_D.name}, {CIKTI_ORTAM.name}")


if __name__ == "__main__":
    try:
        main()
    except KosuKilidiHatasi as hata:
        raise SystemExit(f"HATA: {hata}") from None
