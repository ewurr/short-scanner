"""F1 kapanis turu, madde 4: kume sonu kaydi. YALNIZCA SAYI; kural degistirilmez.

On-kayit §4 "Olcum raporlamasinin kume siniri" (rev.10): olcumler KESIF icindir. Getiri, fiyat farki,
funding orani ya da H2 ortalamasinin degeri HESAPLANMAZ: mumlardan acilis zamani, funding kayitlarindan
odeme zamani ve aralik okunur; oran sutunlari hicbir fonksiyona verilmez.

1. `rev10_kume_sonu_kesif_tam.csv` — KESIF, A grubu. Penceresi kume sonunu HAM karsilastirmayla asan
   4h barlar (kapanis > KESIF sonu 23:59:59; yani kumenin son bari 2025-08-31 20:00). Her bar icin:
   - karar noktasinin plan adimi (`pencere.pozisyon_plani`, gercek kod, kume sinirlari KESIF, seri
     `klines.mumlari_yukle(..., "KESIF")`) her 4h ufkunda (config.UFUKLAR, 6/18/42 bar) ret gerekcesi. Olaylar ve
     kontroller (K1, K2) ayni karar noktasina gider; bir barin olay olarak da kontrol olarak da
     gidecegi cagri aynidir.
   - H2 penceresinde bugun kac kayit oldugu (`funding.sinyal_penceresi_ayrintisi`, `funding_yukle`
     serisi) ve pencere sonundaki kaydin ritmi.
   - Diger pencere turleri ayni barda: 30 barlik (t dahil) ve 6 barlik (t haric) bar penceresi
     (`pencere.pencere_dilimi`), uygunluk hacim penceresi (`eligibility.medyan_hacim`, 1d seri).
   Ayrica KESIF'in 1d son gunu (2025-08-31; H3) icin plan adimi (7, 14, 30 gun).
2. `rev10_kume_sonu_sinir_tam.csv` — kumelerin son bari: C1 (B grubu, 2025-08-31 20:00) ve C2 (A+B,
   2026-08-31 20:00) icin YALNIZCA donem ici bar SAYISI (var/yok). Onay kumesi gerekcesi: F1 kapanis
   gorevi bu durumun onay kumelerinde de olup olmadigini soruyor; yalnizca zaman damgasi sayilir.
3. Ayni dosyada KESIF sonu ile C2 basi arasindaki bir saniyelik araliga (23:59:59 < z < 00:00:00) ve
   kume sinirindan bir dakika icine dusen funding kaydi SAYISI (denetci D-C1 supesi; yalnizca zaman).

Kullanim:
    python analysis/00_veri_denetimi/f1k_kume_sonu.py --is-parcaci 8
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

KOK = Path(__file__).resolve().parents[2]
BU_DIZIN = Path(__file__).resolve().parent
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(BU_DIZIN))

import config  # noqa: E402
from calistir import KosuKilidiHatasi, csv_yaz, git_durumu, kosu_kilidi, ortam_kaydi  # noqa: E402
from data import donem as donem_modulu  # noqa: E402
from data import eligibility as eligibility_modulu  # noqa: E402
from data import funding as funding_modulu  # noqa: E402
from data import klines as klines_modulu  # noqa: E402
from data import pencere as pencere_modulu  # noqa: E402
from data import split as split_modulu  # noqa: E402
from data import universe as universe_modulu  # noqa: E402

P = pencere_modulu
F = funding_modulu
H4 = P.ADIMLAR[config.BAR_4H]
CIKTI = {ad: BU_DIZIN / f"rev10_kume_sonu_{ad}_tam.csv" for ad in ("kesif", "sinir", "ortam")}


def _ret(fonk) -> str:
    try:
        fonk()
    except P.OlayOlusmaz as hata:
        return P.ret_gerekcesi(hata)
    return "olusur"


def _donem(donemler, t, bar):
    for d in donemler:
        if P.donem_ici_mi(t, bar, donem_baslangic=d.baslangic, donem_bitis=d.bitis):
            return d
    return None


def kesif_olc(sembol: str, donemler, k_bas, k_son) -> list[dict]:
    satirlar = []
    mumlar = klines_modulu.mumlari_yukle(sembol, config.BAR_4H, "KESIF")
    if mumlar.empty:
        return satirlar
    zamanlar = pd.DatetimeIndex(mumlar["open_time"])
    seri = F.funding_yukle(sembol, "KESIF").loc[:, ["odeme_zamani", "aralik_saat"]]  # oran okunmaz
    gunluk = klines_modulu.gunluge_cevir(mumlar, donemler=donemler)
    hacim = eligibility_modulu.gunluk_hacim_serisi(gunluk) if len(gunluk) else pd.Series(dtype=float)
    kapanis_sonrasi = zamanlar[np.asarray(zamanlar + H4 > k_son)]  # HAM karsilastirma (rev10_son ile ayni)
    for t in kapanis_sonrasi:
        d = _donem(donemler, t, config.BAR_4H)
        if d is None:
            continue
        zd = zamanlar[np.asarray(P.donem_ici_4h_maskesi(zamanlar, donem_baslangic=d.baslangic,
                                                        donem_bitis=d.bitis), dtype=bool)]
        satir = {"sembol": sembol, "izgara": config.BAR_4H, "t": t}
        for ufuk in config.UFUKLAR[config.BAR_4H]:
            satir[f"plan_{ufuk}"] = _ret(lambda u=ufuk: P.pozisyon_plani(
                zd, t, u, config.BAR_4H, birincil_ufuk=config.BIRINCIL_UFUK[config.BAR_4H], kume_baslangic=k_bas,
                kume_bitis=k_son, donem_baslangic=d.baslangic, donem_bitis=d.bitis))
        a = F.sinyal_penceresi_ayrintisi(seri, [t], config.BAR_4H, saat=config.H2_FUNDING_PENCERESI_SAAT,
                                         kume_baslangic=k_bas, kume_bitis=k_son,
                                         donem_baslangic=d.baslangic).iloc[0]
        satir["h2_hesaplanabilir"] = bool(a["hesaplanabilir"])
        satir["h2_kayit"] = max(int(a["son"]) - int(a["ilk"]) + 1, 0)
        satir["h2_son_aralik"] = float(seri["aralik_saat"].iloc[int(a["son"])]) if a["son"] >= 0 else np.nan
        seri_s = pd.Series(1.0, index=zamanlar)
        ortak = dict(kume_baslangic=k_bas, donem_baslangic=d.baslangic)
        satir["bar_30_t_dahil"] = P.pencere_dilimi(seri_s, t, 30, config.BAR_4H, t_dahil=True, **ortak) is not None
        satir["bar_6_t_haric"] = P.pencere_dilimi(seri_s, t, 6, config.BAR_4H, t_dahil=False, **ortak) is not None
        satir["uygunluk_hacim"] = bool(len(hacim)) and not np.isnan(eligibility_modulu.medyan_hacim(
            hacim, t, pencere_gun=config.HACIM_PENCERESI_GUN, **ortak))
        satirlar.append(satir)
    # H3: KESIF'in 1d son gunu.
    if len(gunluk):
        gunler = pd.DatetimeIndex(gunluk["open_time"])
        for t in gunler[np.asarray(gunler + P.ADIMLAR[config.BAR_1D] > k_son)]:
            d = _donem(donemler, t, config.BAR_1D)
            if d is None:
                continue
            zd = zamanlar[np.asarray(P.donem_ici_4h_maskesi(zamanlar, donem_baslangic=d.baslangic,
                                                            donem_bitis=d.bitis), dtype=bool)]
            satir = {"sembol": sembol, "izgara": config.BAR_1D, "t": t}
            for ufuk in config.UFUKLAR[config.BAR_1D]:
                satir[f"plan_{ufuk}"] = _ret(lambda u=ufuk: P.pozisyon_plani(
                    zd, t, u, config.BAR_1D, birincil_ufuk=config.BIRINCIL_UFUK[config.BAR_1D], kume_baslangic=k_bas,
                    kume_bitis=k_son, donem_baslangic=d.baslangic, donem_bitis=d.bitis))
            satirlar.append(satir)
    return satirlar


def sinir_olc(sembol: str, donemler, grup: str, kumeler) -> list[dict]:
    """Kumelerin son 4h bari donem ici mi (yalnizca zaman) ve sinir yakinindaki funding kaydi sayisi."""
    satirlar = []
    zamanlar = pd.DatetimeIndex(donem_modulu.toplam_doneme_kes(
        klines_modulu.ham_mumlari_yukle(sembol, config.BAR_4H), "open_time")["open_time"])
    for ad, (gruplar, _, son) in kumeler.items():
        if ad == "KESIF" or grup not in gruplar:
            continue
        son_bar = son.floor("4h")
        var = son_bar in zamanlar and _donem(donemler, son_bar, config.BAR_4H) is not None
        satirlar.append({"sembol": sembol, "kume": ad, "olcu": "son_bar_donem_ici", "adet": int(var)})
    fz = pd.DatetimeIndex(F.ham_funding_yukle(sembol)["odeme_zamani"])
    k_son, c2_bas = pd.Timestamp(config.KESIF_SONU), pd.Timestamp(config.C2_BASI)
    satirlar.append({"sembol": sembol, "kume": "KESIF|C2", "olcu": "bir_saniyelik_aralikta_kayit",
                     "adet": int(((fz > k_son) & (fz < c2_bas)).sum())})
    satirlar.append({"sembol": sembol, "kume": "KESIF|C2", "olcu": "sinirdan_bir_dakika_icinde_kayit",
                     "adet": int(((fz > k_son - pd.Timedelta(minutes=1)) & (fz < c2_bas + pd.Timedelta(minutes=1))).sum())})
    return satirlar


def main(argv: list[str] | None = None) -> None:
    ayristirici = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ayristirici.add_argument("--is-parcaci", type=int, default=4)
    ayristirici.add_argument("--semboller", nargs="*", default=None)
    ayristirici.add_argument("--cikti-dizini", type=Path, default=BU_DIZIN)
    argumanlar = ayristirici.parse_args(argv)
    cikti = argumanlar.cikti_dizini
    with kosu_kilidi("f1k_kume_sonu", cikti):
        baslangic_zamani = pd.Timestamp.now(tz="UTC")
        git = git_durumu()
        evren = universe_modulu.evren_yukle()
        grup = split_modulu.split_oku().set_index("sembol")["grup"].to_dict()
        kumeler = {k: (split_modulu.kume_tanimi(k)[0], *split_modulu.kume_araligi(k)) for k in config.KUMELER}
        semboller = [s for s in universe_modulu.dahil_semboller(evren) if s in grup]
        donemler = {s: universe_modulu.sembol_donemleri(evren, s) for s in semboller}
        secilen = [s for s in semboller if donemler[s] and (argumanlar.semboller is None or s in argumanlar.semboller)]
        _, k_bas, k_son = kumeler["KESIF"]
        kesif_s, sinir_s = [], []
        with ProcessPoolExecutor(max_workers=argumanlar.is_parcaci) as havuz:
            k_isler = [havuz.submit(kesif_olc, s, donemler[s], k_bas, k_son) for s in secilen
                       if grup[s] in kumeler["KESIF"][0]]
            s_isler = [havuz.submit(sinir_olc, s, donemler[s], grup[s], kumeler) for s in secilen]
            for is_ in k_isler:
                kesif_s += is_.result()
            for is_ in s_isler:
                sinir_s += is_.result()
        csv_yaz(pd.DataFrame(kesif_s), cikti / CIKTI["kesif"].name)
        sinir = pd.DataFrame(sinir_s).groupby(["kume", "olcu"], as_index=False)["adet"].sum() if sinir_s else \
            pd.DataFrame(columns=["kume", "olcu", "adet"])
        csv_yaz(sinir, cikti / CIKTI["sinir"].name)
        csv_yaz(ortam_kaydi(git, baslangic_zamani, pd.Timestamp.now(tz="UTC")), cikti / CIKTI["ortam"].name)
        print(f"KESIF satir {len(kesif_s)} | sinir satir {len(sinir)} -> {cikti}")


if __name__ == "__main__":
    try:
        main()
    except KosuKilidiHatasi as hata:
        print(f"HATA: {hata}", file=sys.stderr)
        sys.exit(2)
