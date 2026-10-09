"""Rev.11 uygulamasinin etki olcumleri. YALNIZCA SAYI; kural burada degistirilmez.

On-kayit §4 "Olcum raporlamasinin kume siniri" (rev.10): yalnizca KESIF kumesi (A grubu, KESIF
tarih araligi) okunur; C1/C2 hic hesaplanmaz. Getiri, fiyat farki, funding orani ya da herhangi
bir sinyal DEGERI hesaplanmaz; yalnizca "hesaplandi / hesaplanamadi" ve bar/gun SAYILARI
yazilir.

Olcumler (`--olcum`):

1. `hucre` — Rev.11 madde 3 (on-kayit §2 "1 gunluk barlar": eksik hucre gunu dusurur).
   Her A grubu sembolun KESIF 4h barlarinda, fiyat ve hacim hucrelerinden biri sonlu bir sayi
   olmayan bar sayilir (`klines.hucreleri_tam_mi`, gercek kod) ve kuralin DUSURDUGU gun sayisi
   olculur. "Once" durumu, bozuk hucreleri sonlu bir yer tutucuyla (0.0) degistirip ayni gercek
   `klines.gunluge_cevir` yolunu kosarak uretilir: eski kod yalnizca bar SAYISINA baktigi icin
   bu, kural oncesi gun kumesiyle birebir aynidir. Fark = kuralin dusurdugu gun.
   Ciktilar: `rev11_hucre_tam.csv` (sembol basina), `rev11_hucre_barlar_tam.csv` (bozuk hucreli
   her bar: sembol, t, sutun), `rev11_hucre_ortam_tam.csv`.

2. `kume_sonu` — Rev.11 madde 8 (on-kayit §4 "Funding sinyal penceresinin tamligi": pencere
   sonuna denk gelen kayit yalnizca ayni kumeye aitse ortalamaya girer).
   Her A grubu sembolun KESIF 4h barlarinda, H2 funding sinyal penceresi gercek kodla
   (`funding.sinyal_penceresi_ayrintisi`) kurulur ve YALNIZCA bayraklar okunur; oran sutunlari
   fonksiyona verilmeden once, NaN olup olmadiklari korunarak sabit 0 ile degistirilir
   (`degersiz`), yani hicbir funding DEGERI hesaba girmez. Kuralin DUSURDUGU bar: diger butun
   kosullar saglanirken (kume icinde, capa, aralik, zincir, kayit var) yalnizca yeni kosulun
   (`kume_sonu_kaydi_disarida`) dusurdugu bar. Her dusen bar icin karar noktasinin plan adimi
   (`pencere.pozisyon_plani`, gercek kod) uc 4h ufkunda (config.UFUKLAR) ret gerekcesini verir;
   boylece barlarin zaten giris bari bulunmadigi icin reddedildigi dogrulanir.
   Ciktilar: `rev11_kume_sonu_tam.csv` (sembol basina sayilar),
   `rev11_kume_sonu_barlar_tam.csv` (her dusen bar: sembol, t ve ufuk basina ret gerekcesi),
   `rev11_kume_sonu_ortam_tam.csv`.

Kullanim:
    python analysis/00_veri_denetimi/rev11_uygulama.py --olcum hucre --is-parcaci 8
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
from data import funding as funding_modulu  # noqa: E402
from data import klines as klines_modulu  # noqa: E402
from data import pencere as pencere_modulu  # noqa: E402
from data import split as split_modulu  # noqa: E402
from data import universe as universe_modulu  # noqa: E402

P = pencere_modulu
KUME = "KESIF"


# --- 1. Eksik hucre (Rev.11 madde 3) ----------------------------------------------------------


def _yer_tutuculu(mumlar: pd.DataFrame) -> pd.DataFrame:
    """Bozuk (sonlu olmayan ya da sayisal olmayan) hucreleri 0.0 ile degistirir: Rev.11 oncesi
    `gunluge_cevir` davranisinin (yalnizca bar sayisi) birebir karsiligi. Saf."""
    kopya = mumlar.copy()
    for sutun in klines_modulu.HUCRE_SUTUNLARI:
        if sutun not in kopya:
            continue
        degerler = pd.to_numeric(kopya[sutun], errors="coerce").to_numpy(dtype=float)
        kopya[sutun] = np.where(np.isfinite(degerler), degerler, 0.0)
    return kopya


def hucre_olc(sembol: str, donemler):
    """Sembolun KESIF 4h barlarinda bozuk hucreli bar ve kuralin dusurdugu gun sayisi."""
    mumlar = klines_modulu.mumlari_yukle(sembol, config.BAR_4H, KUME)
    if mumlar.empty or not donemler:
        return [], []
    zamanlar = pd.DatetimeIndex(mumlar["open_time"])
    tam = klines_modulu.hucreleri_tam_mi(mumlar)
    donem_ici = np.zeros(len(mumlar), dtype=bool)
    for d in donemler:
        donem_ici |= np.asarray(P.donem_ici_4h_maskesi(
            zamanlar, donem_baslangic=d.baslangic, donem_bitis=d.bitis), dtype=bool)

    bozuk = []
    for i in np.flatnonzero(donem_ici & ~tam):
        for sutun in klines_modulu.HUCRE_SUTUNLARI:
            if sutun not in mumlar:
                continue
            deger = pd.to_numeric(pd.Series([mumlar[sutun].iloc[i]]), errors="coerce").iloc[0]
            if not np.isfinite(deger):
                bozuk.append({"sembol": sembol, "t": zamanlar[i], "sutun": sutun})

    sonra = klines_modulu.gunluge_cevir(mumlar, donemler=list(donemler))
    once = klines_modulu.gunluge_cevir(_yer_tutuculu(mumlar), donemler=list(donemler))
    ozet = [{
        "sembol": sembol,
        "donem_ici_4h_bar": int(donem_ici.sum()),
        "bozuk_hucreli_bar": int((donem_ici & ~tam).sum()),
        "gun_once": int(len(once)),
        "gun_sonra": int(len(sonra)),
        "dusen_gun": int(len(once) - len(sonra)),
    }]
    return ozet, bozuk


def hucre_kosusu(secilen, donemler, is_parcaci: int, cikti: Path) -> str:
    ozetler, bozuklar = [], []
    with ProcessPoolExecutor(max_workers=is_parcaci) as havuz:
        for is_ in [havuz.submit(hucre_olc, s, donemler[s]) for s in secilen]:
            o, b = is_.result()
            ozetler += o
            bozuklar += b
    cerceve = pd.DataFrame(ozetler, columns=["sembol", "donem_ici_4h_bar", "bozuk_hucreli_bar",
                                             "gun_once", "gun_sonra", "dusen_gun"])
    csv_yaz(cerceve, cikti / "rev11_hucre_tam.csv")
    csv_yaz(pd.DataFrame(bozuklar, columns=["sembol", "t", "sutun"]), cikti / "rev11_hucre_barlar_tam.csv")
    if cerceve.empty:
        return "KESIF: sembol yok"
    return (f"KESIF sembol {len(cerceve)} | donem ici 4h bar {int(cerceve['donem_ici_4h_bar'].sum())} | "
            f"bozuk hucreli bar {int(cerceve['bozuk_hucreli_bar'].sum())} | "
            f"gun once {int(cerceve['gun_once'].sum())} -> sonra {int(cerceve['gun_sonra'].sum())} | "
            f"dusen gun {int(cerceve['dusen_gun'].sum())}")


# --- 2. Kume sonu kaydi (Rev.11 madde 8) ------------------------------------------------------


def degersiz(fund: pd.DataFrame) -> pd.DataFrame:
    """Oran sutunlarini, yalnizca NaN olup olmadiklarini koruyarak 0 yapar. Saf.
    (`rev10_uygulama.degersiz` ile ayni; olcum hicbir funding DEGERI okumaz.)"""
    kopya = fund.copy()
    for sutun in ("oran", "oran_8h"):
        if sutun in kopya:
            kopya[sutun] = np.where(pd.isna(kopya[sutun]), np.nan, 0.0)
    return kopya


def _ret(fonk) -> str:
    """Plan adiminin ret gerekcesi; olay olusursa "olustu"."""
    try:
        fonk()
    except P.OlayOlusmaz as hata:
        return P.ret_gerekcesi(hata)
    except P.DonemDisiSinyal:
        return "donem_disi_sinyal"
    return "olustu"


def kume_sonu_olc(sembol: str, donemler, k_bas, k_son):
    mumlar = klines_modulu.mumlari_yukle(sembol, config.BAR_4H, KUME)
    fund = degersiz(funding_modulu.funding_yukle(sembol, KUME))
    if mumlar.empty or not donemler:
        return [], []
    zamanlar = pd.DatetimeIndex(mumlar["open_time"])
    ozet, barlar = [], []
    for d in donemler:
        maske = np.asarray(P.donem_ici_4h_maskesi(
            zamanlar, donem_baslangic=d.baslangic, donem_bitis=d.bitis), dtype=bool)
        t_ler = zamanlar[maske & (zamanlar >= k_bas) & (zamanlar <= k_son)]
        if not len(t_ler):
            continue
        a = funding_modulu.sinyal_penceresi_ayrintisi(
            fund, t_ler, config.BAR_4H, saat=config.H2_FUNDING_PENCERESI_SAAT,
            kume_baslangic=k_bas, kume_bitis=k_son, donem_baslangic=d.baslangic)
        diger = (a["kume_icinde"] & a["capa_var"] & a["aralik_gecerli"] & a["zincir_tam"]
                 & a["kayit_var"]).to_numpy(dtype=bool)
        dusen = diger & ~a["kume_sonu_kaydi_disarida"].to_numpy(dtype=bool)
        ozet.append({"sembol": sembol, "donem_baslangic": d.baslangic, "bar": int(len(t_ler)),
                     "hesaplanabilir": int(a["hesaplanabilir"].sum()), "dusen_bar": int(dusen.sum())})
        for t in t_ler[dusen]:
            satir = {"sembol": sembol, "t": t}
            for ufuk in config.UFUKLAR[config.BAR_4H]:
                satir[f"ret_{ufuk}"] = _ret(lambda u=ufuk: P.pozisyon_plani(
                    zamanlar, t, u, config.BAR_4H, birincil_ufuk=config.BIRINCIL_UFUK[config.BAR_4H],
                    kume_baslangic=k_bas, kume_bitis=k_son, donem_baslangic=d.baslangic,
                    donem_bitis=d.bitis))
            barlar.append(satir)
    return ozet, barlar


def kume_sonu_kosusu(secilen, donemler, is_parcaci: int, cikti: Path) -> str:
    k_bas, k_son = split_modulu.kume_araligi(KUME)
    ozetler, barlar = [], []
    with ProcessPoolExecutor(max_workers=is_parcaci) as havuz:
        for is_ in [havuz.submit(kume_sonu_olc, s, donemler[s], k_bas, k_son) for s in secilen]:
            o, b = is_.result()
            ozetler += o
            barlar += b
    cerceve = pd.DataFrame(ozetler, columns=["sembol", "donem_baslangic", "bar", "hesaplanabilir",
                                             "dusen_bar"])
    ret_sutunlari = [f"ret_{u}" for u in config.UFUKLAR[config.BAR_4H]]
    bar_cercevesi = pd.DataFrame(barlar, columns=["sembol", "t", *ret_sutunlari])
    csv_yaz(cerceve, cikti / "rev11_kume_sonu_tam.csv")
    csv_yaz(bar_cercevesi, cikti / "rev11_kume_sonu_barlar_tam.csv")
    if cerceve.empty:
        return "KESIF: sembol yok"
    gerekceler = {s: sorted(bar_cercevesi[s].unique()) for s in ret_sutunlari} if len(bar_cercevesi) else {}
    return (f"KESIF sembol {cerceve['sembol'].nunique()} | donem ici bar {int(cerceve['bar'].sum())} | "
            f"dusen bar {int(cerceve['dusen_bar'].sum())} ({len(bar_cercevesi)} satir, "
            f"{bar_cercevesi['sembol'].nunique() if len(bar_cercevesi) else 0} sembol) | "
            f"plan ret gerekceleri {gerekceler}")


OLCUMLER = {"hucre": ("rev11_hucre", hucre_kosusu),
            "kume_sonu": ("rev11_kume_sonu", kume_sonu_kosusu)}


def main(argv: list[str] | None = None) -> None:
    ayristirici = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ayristirici.add_argument("--olcum", required=True, choices=tuple(OLCUMLER))
    ayristirici.add_argument("--is-parcaci", type=int, default=4)
    ayristirici.add_argument("--semboller", nargs="*", default=None)
    ayristirici.add_argument("--cikti-dizini", type=Path, default=BU_DIZIN)
    argumanlar = ayristirici.parse_args(argv)
    kilit_adi, kosu = OLCUMLER[argumanlar.olcum]
    cikti = argumanlar.cikti_dizini
    with kosu_kilidi(kilit_adi, cikti):
        baslangic_zamani = pd.Timestamp.now(tz="UTC")
        git = git_durumu()
        evren = universe_modulu.evren_yukle()
        grup = split_modulu.split_oku().set_index("sembol")["grup"].to_dict()
        gruplar = split_modulu.kume_tanimi(KUME)[0]
        semboller = [s for s in universe_modulu.dahil_semboller(evren) if grup.get(s) in gruplar]
        donemler = {s: universe_modulu.sembol_donemleri(evren, s) for s in semboller}
        secilen = [s for s in semboller
                   if donemler[s] and (argumanlar.semboller is None or s in argumanlar.semboller)]
        ozet = kosu(secilen, donemler, argumanlar.is_parcaci, cikti)
        csv_yaz(ortam_kaydi(git, baslangic_zamani, pd.Timestamp.now(tz="UTC")),
                cikti / f"{kilit_adi}_ortam_tam.csv")
        print(f"{ozet} -> {cikti}")


if __name__ == "__main__":
    try:
        # F1 veri denetimi butun gecmisi olcer (anayasa §3.1): onay verisi izniyle.
        from data import binance_vision as _bv

        with _bv.onay_verisi_izni("F1 veri denetimi: " + Path(__file__).name):
            main()
    except KosuKilidiHatasi as hata:
        print(f"HATA: {hata}", file=sys.stderr)
        sys.exit(2)
