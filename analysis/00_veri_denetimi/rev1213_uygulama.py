"""Rev.12-13 uygulamasinin etki olcumleri. YALNIZCA SAYI; kural burada degistirilmez.

On-kayit §4 "Olcum raporlamasinin kume siniri" (rev.10): yalnizca KESIF kumesi (A grubu, KESIF
tarih araligi) okunur; C1/C2 hic hesaplanmaz. Getiri, fiyat farki ya da sinyal DEGERI
raporlanmaz; yalnizca "hesaplandi / hesaplanamadi" ve bar/gun SAYILARI yazilir. Olcumlerin
tamami GERCEK kodu cagirir (`data.klines`, `data.eligibility`, `data.sinyal`); kuralin ikinci bir
kopyasi bu dosyada yoktur.

Olcumler (`--olcum`):

1. `bar_duzeyi` — madde 1c (on-kayit §2 rev.12: tamlik olcutu bar duzeyindedir).
   Her A grubu sembolun KESIF 4h barlarinda, `klines.hucreleri_tam_mi` (gercek kod) ile bar
   duzeyli olcutun MASKELEDIGI bar sayilir; sutun bazinda bozuk hucre sayilari da yazilir.
   Olcutun etkisi, "hucresi bozuk ama o pencerenin kullandigi alan saglam" barlarin
   sayisidir: bar duzeyli olcut bu barlari da dusurur, alan duzeyli olcut dusurmezdi.
   Ciktilar: `rev1213_bar_duzeyi_tam.csv`, `rev1213_bar_duzeyi_sutun_tam.csv`.

2. `capasiz` — madde 1b (on-kayit §6 rev.12: kontrol barinda CAPASIZ sinyal pencereleri
   hesaplanabilir olmali).
   Her hipotez icin, o hipotezin izgarasindaki donem ici KESIF barlarindan UYGUNLUK FILTRESINI
   GECENLER (gercek `eligibility.uygunluk_serisi`) sayilir -- rev.12'den once kontrol barinin
   gecmesi gereken bir sinyal sarti yoktu, dolayisiyla aday kumesi buydu. Sonra ayni barlarda
   `sinyal.capasiz_pencere_degerleri` + `capasiz_hesaplanamayan` (gercek kod) ile kuralin
   DUSURDUGU bar sayilir ve ilk hesaplanamayan pencerenin ADI yazilir (deger yazilmaz).
   Ciktilar: `rev1213_capasiz_tam.csv`, `rev1213_capasiz_pencere_tam.csv`.

3. `gecersizlik` — madde 2c (on-kayit §5 H2 madde 4, H3 madde 4 rev.13: `max(high[t-30..t]) x 1.02`).
   H2 ve H3 icin, uygunluk filtresini gecen ayni barlarda seviyenin hesaplanabilir olup olmadigi
   sayilir (`sinyal.gecersizlik_seviyesi`, gercek kod; donen DEGER yazilmaz, yalnizca sonlu olup
   olmadigi). H1'in seviyesi pump barina CAPALIDIR (tepe penceresi) ve yalnizca suren bir izleme
   icinde tanimlidir; izleme dizisi F2'nin isi oldugu icin H1 bu olcumde sayilmaz.
   Cikti: `rev1213_gecersizlik_tam.csv`.

Kullanim:
    python analysis/00_veri_denetimi/rev1213_uygulama.py --olcum capasiz --is-parcaci 8
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
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
from data import eligibility as uygunluk_modulu  # noqa: E402
from data import funding as funding_modulu  # noqa: E402
from data import klines as klines_modulu  # noqa: E402
from data import pencere as pencere_modulu  # noqa: E402
from data import sinyal as sinyal_modulu  # noqa: E402
from data import split as split_modulu  # noqa: E402
from data import universe as universe_modulu  # noqa: E402

P = pencere_modulu
KUME = "KESIF"
# Her hipotez icin tek bir yapilandirma yeter: capasiz pencerelerin HESAPLANABILIRLIGI yalnizca
# H2'nin k parametresine bagli degisir (kirilim dip penceresinin uzunlugu) ve en uzun pencere en
# cok bar duser. En muhafazakar olcum icin k'nin en buyugu alinir; H1 ve H3'un capasiz
# pencereleri yapilandirmadan bagimsizdir.
YAPILANDIRMALAR = {"H1": {"theta": 0.20, "delta": 0.08},
                   "H2": {"phi": 0.0003, "k": 12},
                   "H3": {"nu": 0.50, "tau": 0.15}}


def _donem_ici(zamanlar, d, bar: str):
    """Donem ici barlar. 4h'te gercek kod (`pencere.donem_ici_4h_maskesi`); gunluk seride
    `klines.gunluge_cevir` zaten donemlere gore kesilmis gunleri verdigi icin yalnizca gunun
    donem araligina dusup dusmedigine bakilir."""
    if bar == config.BAR_4H:
        return np.asarray(P.donem_ici_4h_maskesi(
            zamanlar, donem_baslangic=d.baslangic, donem_bitis=d.bitis), dtype=bool)
    return np.asarray((zamanlar >= pd.Timestamp(d.baslangic))
                      & (zamanlar <= pd.Timestamp(d.bitis)), dtype=bool)


# --- 1. Bar duzeyli tamlik olcutu (madde 1c) --------------------------------------------------


def bar_duzeyi_olc(sembol: str, donemler, k_bas, k_son):
    mumlar = klines_modulu.mumlari_yukle(sembol, config.BAR_4H, KUME)
    if mumlar.empty or not donemler:
        return [], []
    zamanlar = pd.DatetimeIndex(mumlar["open_time"])
    tam = np.asarray(klines_modulu.hucreleri_tam_mi(mumlar), dtype=bool)
    ici = np.zeros(len(mumlar), dtype=bool)
    for d in donemler:
        ici |= _donem_ici(zamanlar, d, config.BAR_4H)
    ici &= np.asarray((zamanlar >= k_bas) & (zamanlar <= k_son), dtype=bool)
    maskelenen = ici & ~tam

    sutunlar = []
    for sutun in klines_modulu.HUCRE_SUTUNLARI:
        if sutun not in mumlar:
            continue
        degerler = pd.to_numeric(mumlar[sutun], errors="coerce").to_numpy(dtype=float)
        bozuk = ici & ~np.isfinite(degerler)
        if bozuk.any():
            sutunlar.append({"sembol": sembol, "sutun": sutun, "bozuk_bar": int(bozuk.sum())})
    return [{"sembol": sembol, "donem_ici_kesif_bar": int(ici.sum()),
             "maskelenen_bar": int(maskelenen.sum())}], sutunlar


def bar_duzeyi_kosusu(secilen, donemler, is_parcaci: int, cikti: Path) -> str:
    k_bas, k_son = split_modulu.kume_araligi(KUME)
    ozetler, sutunlar = [], []
    with ProcessPoolExecutor(max_workers=is_parcaci) as havuz:
        for is_ in [havuz.submit(bar_duzeyi_olc, s, donemler[s], k_bas, k_son) for s in secilen]:
            o, c = is_.result()
            ozetler += o
            sutunlar += c
    cerceve = pd.DataFrame(ozetler, columns=["sembol", "donem_ici_kesif_bar", "maskelenen_bar"])
    csv_yaz(cerceve, cikti / "rev1213_bar_duzeyi_tam.csv")
    csv_yaz(pd.DataFrame(sutunlar, columns=["sembol", "sutun", "bozuk_bar"]),
            cikti / "rev1213_bar_duzeyi_sutun_tam.csv")
    if cerceve.empty:
        return "KESIF: sembol yok"
    return (f"KESIF sembol {len(cerceve)} | donem ici bar {int(cerceve['donem_ici_kesif_bar'].sum())} | "
            f"bar duzeyli olcutun maskeledigi bar {int(cerceve['maskelenen_bar'].sum())}")


# --- Uygunluk filtresini gecen barlar (iki olcumun ortak tabani) ------------------------------


def _uygun_barlar(d, bar: str, mumlar_4h, gunluk, k_bas, k_son):
    """Donem ici KESIF barlarindan uygunluk filtresini GECENLER (gercek `uygunluk_serisi`)."""
    seri = mumlar_4h if bar == config.BAR_4H else gunluk
    if seri.empty:
        return pd.DatetimeIndex([])
    zamanlar = pd.DatetimeIndex(seri["open_time"])
    maske = _donem_ici(zamanlar, d, bar)
    maske &= np.asarray((zamanlar >= k_bas) & (zamanlar <= k_son), dtype=bool)
    t_ler = zamanlar[maske]
    if not len(t_ler):
        return t_ler
    karar = uygunluk_modulu.uygunluk_serisi(
        uygunluk_modulu.gunluk_hacim_serisi(gunluk), t_ler, bar,
        donem_baslangic=d.baslangic, donem_bitis=d.bitis, kume_baslangic=k_bas)
    return t_ler[np.asarray(karar, dtype=bool)]


# --- 2. Capasiz pencereler (madde 1b) ---------------------------------------------------------


def capasiz_olc(sembol: str, donemler, k_bas, k_son):
    mumlar_4h = klines_modulu.mumlari_yukle(sembol, config.BAR_4H, KUME)
    fund = funding_modulu.funding_yukle(sembol, KUME)
    if mumlar_4h.empty or not donemler:
        return [], []
    gunluk = klines_modulu.gunluge_cevir(mumlar_4h, donemler=list(donemler))
    ozet, pencereler = [], []
    for hipotez, yapilandirma in YAPILANDIRMALAR.items():
        bar = pencere_modulu.hipotez_izgarasi(hipotez)
        for d in donemler:
            t_ler = _uygun_barlar(d, bar, mumlar_4h, gunluk, k_bas, k_son)
            dusen = 0
            sayac = Counter()
            for t in t_ler:
                degerler = sinyal_modulu.capasiz_pencere_degerleri(
                    hipotez, yapilandirma, t, mumlar_4h=mumlar_4h, gunluk=gunluk, funding=fund,
                    kume_baslangic=k_bas, kume_bitis=k_son, donem_baslangic=d.baslangic)
                eksik = sinyal_modulu.capasiz_hesaplanamayan(hipotez, degerler)
                if eksik:
                    dusen += 1
                    sayac[eksik[0]] += 1
            ozet.append({"sembol": sembol, "hipotez": hipotez, "donem_baslangic": d.baslangic,
                         "uygun_bar": int(len(t_ler)), "dusen_bar": int(dusen)})
            for ad, sayi in sorted(sayac.items()):
                pencereler.append({"sembol": sembol, "hipotez": hipotez, "pencere": ad,
                                   "dusen_bar": int(sayi)})
    return ozet, pencereler


def capasiz_kosusu(secilen, donemler, is_parcaci: int, cikti: Path) -> str:
    k_bas, k_son = split_modulu.kume_araligi(KUME)
    ozetler, pencereler = [], []
    with ProcessPoolExecutor(max_workers=is_parcaci) as havuz:
        for is_ in [havuz.submit(capasiz_olc, s, donemler[s], k_bas, k_son) for s in secilen]:
            o, p = is_.result()
            ozetler += o
            pencereler += p
    cerceve = pd.DataFrame(ozetler, columns=["sembol", "hipotez", "donem_baslangic", "uygun_bar",
                                             "dusen_bar"])
    csv_yaz(cerceve, cikti / "rev1213_capasiz_tam.csv")
    pencere_cercevesi = pd.DataFrame(pencereler, columns=["sembol", "hipotez", "pencere", "dusen_bar"])
    csv_yaz(pencere_cercevesi, cikti / "rev1213_capasiz_pencere_tam.csv")
    if cerceve.empty:
        return "KESIF: sembol yok"
    parcalar = []
    for hipotez, grup in cerceve.groupby("hipotez"):
        pay = 100.0 * int(grup["dusen_bar"].sum()) / max(int(grup["uygun_bar"].sum()), 1)
        parcalar.append(f"{hipotez}: uygun {int(grup['uygun_bar'].sum())} -> dusen "
                        f"{int(grup['dusen_bar'].sum())} (%{pay:.2f})")
    return f"KESIF sembol {cerceve['sembol'].nunique()} | " + " | ".join(parcalar)


# --- 3. Gecersizlik seviyesi (madde 2c) -------------------------------------------------------


def gecersizlik_olc(sembol: str, donemler, k_bas, k_son):
    mumlar_4h = klines_modulu.mumlari_yukle(sembol, config.BAR_4H, KUME)
    if mumlar_4h.empty or not donemler:
        return []
    gunluk = klines_modulu.gunluge_cevir(mumlar_4h, donemler=list(donemler))
    satirlar = []
    for hipotez in ("H2", "H3"):
        bar = pencere_modulu.hipotez_izgarasi(hipotez)
        for d in donemler:
            t_ler = _uygun_barlar(d, bar, mumlar_4h, gunluk, k_bas, k_son)
            hesaplanan = 0
            for t in t_ler:
                seviye = sinyal_modulu.gecersizlik_seviyesi(
                    hipotez, t, mumlar_4h=mumlar_4h, gunluk=gunluk, capa=None,
                    kume_baslangic=k_bas, donem_baslangic=d.baslangic)
                hesaplanan += int(np.isfinite(seviye))
            satirlar.append({"sembol": sembol, "hipotez": hipotez, "donem_baslangic": d.baslangic,
                             "uygun_bar": int(len(t_ler)), "hesaplanan": int(hesaplanan),
                             "hesaplanamayan": int(len(t_ler) - hesaplanan)})
    return satirlar


def gecersizlik_kosusu(secilen, donemler, is_parcaci: int, cikti: Path) -> str:
    k_bas, k_son = split_modulu.kume_araligi(KUME)
    satirlar = []
    with ProcessPoolExecutor(max_workers=is_parcaci) as havuz:
        for is_ in [havuz.submit(gecersizlik_olc, s, donemler[s], k_bas, k_son) for s in secilen]:
            satirlar += is_.result()
    cerceve = pd.DataFrame(satirlar, columns=["sembol", "hipotez", "donem_baslangic", "uygun_bar",
                                              "hesaplanan", "hesaplanamayan"])
    csv_yaz(cerceve, cikti / "rev1213_gecersizlik_tam.csv")
    if cerceve.empty:
        return "KESIF: sembol yok"
    parcalar = [f"{h}: uygun {int(g['uygun_bar'].sum())}, hesaplanan {int(g['hesaplanan'].sum())}, "
                f"hesaplanamayan {int(g['hesaplanamayan'].sum())}"
                for h, g in cerceve.groupby("hipotez")]
    return f"KESIF sembol {cerceve['sembol'].nunique()} | " + " | ".join(parcalar)


OLCUMLER = {"bar_duzeyi": ("rev1213_bar_duzeyi", bar_duzeyi_kosusu),
            "capasiz": ("rev1213_capasiz", capasiz_kosusu),
            "gecersizlik": ("rev1213_gecersizlik", gecersizlik_kosusu)}


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
        # F1 veri denetimi butun gecmisi olcer (anayasa §3.1): onay verisi izniyle. Bu betik
        # yalnizca KESIF kumesini okur (yukaridaki kume siniri), izin kapsami genis tutulmaz.
        from data import binance_vision as _bv

        with _bv.onay_verisi_izni("F1 veri denetimi: " + Path(__file__).name):
            main()
    except KosuKilidiHatasi as hata:
        print(f"HATA: {hata}", file=sys.stderr)
        sys.exit(2)
