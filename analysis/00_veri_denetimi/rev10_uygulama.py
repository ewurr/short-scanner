"""Rev.10 uygulamasi: H2 funding sinyal penceresinin hesaplanabilirligi. YALNIZCA KESIF, YALNIZCA SAYI.

On-kayit §4 "Olcum raporlamasinin kume siniri" (rev.10): yalnizca KESIF kumesi (A grubu, KESIF tarih
araligi) okunur; C1/C2 hic hesaplanmaz.

Gercek kod yolu: funding `funding.funding_yukle(sembol, "KESIF")` ile yuklenir (kume kesimi dahil) ve her
donem ici 4h bar t icin `funding.funding_ortalamasi` cagrilir. Getiri, funding orani ya da H2
ortalamasinin degeri HESAPLANMAZ: fonksiyona verilmeden once `oran` ve `oran_8h` sutunlari, yalnizca
NaN olup olmadiklari korunarak sabit 0 ile degistirilir; donen degerin yalnizca NaN olup olmadigi okunur.

Betik, `funding_ortalamasi`nin iki surumunda da calisir (Rev.10 oncesi imzada `kume_bitis` yok; imza
`inspect` ile okunur). Boylece ayni betik degisiklikten once ve sonra temiz agacta kosulup iki sayim
karsilastirilir (`--etiket once|sonra`).

Ciktilar (`--etiket E`):
  - `rev10_uygulama_h2_E_tam.csv`: sembol basina donem ici KESIF 4h bar sayisi ve hesaplanabilen bar.
  - `rev10_uygulama_h2_nan_E_tam.csv`: hesaplanamayan her bar (sembol, t). Yalnizca zaman.
  - `rev10_uygulama_ortam_E_tam.csv`: ortam kaydi.

Kullanim:
    python analysis/00_veri_denetimi/rev10_uygulama.py --etiket once --is-parcaci 8
"""

from __future__ import annotations

import argparse
import inspect
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
F = funding_modulu
KUME = "KESIF"
SAAT = 24  # on-kayit §5 H2 madde 1: "son 24 saatteki funding oranlarinin ortalamasi"


def degersiz(fund: pd.DataFrame) -> pd.DataFrame:
    """Oran sutunlarini, yalnizca NaN olup olmadiklarini koruyarak 0 yapar. Saf."""
    kopya = fund.copy()
    for sutun in ("oran", "oran_8h"):
        if sutun in kopya:
            kopya[sutun] = np.where(pd.isna(kopya[sutun]), np.nan, 0.0)
    return kopya


def _kume_bitisli_mi() -> bool:
    return "kume_bitis" in inspect.signature(F.funding_ortalamasi).parameters


def hesaplanabilirlik(fund: pd.DataFrame, t_ler, *, kume_bas, kume_son, donem_bas) -> np.ndarray:
    """Her t icin `funding_ortalamasi` NaN degil mi (gercek kod). `fund` degersizlestirilmis olmali."""
    ek = {"kume_bitis": kume_son} if _kume_bitisli_mi() else {}
    sonuc = np.zeros(len(t_ler), dtype=bool)
    for i, t in enumerate(t_ler):
        deger = F.funding_ortalamasi(fund, t, config.BAR_4H, saat=SAAT, kume_baslangic=kume_bas,
                                     donem_baslangic=donem_bas, **ek)
        sonuc[i] = not np.isnan(deger)
    return sonuc


def sembol_olc(sembol: str, donemler, k_bas, k_son):
    mumlar = klines_modulu.mumlari_yukle(sembol, config.BAR_4H, KUME)
    fund = degersiz(F.funding_yukle(sembol, KUME))
    zamanlar = pd.DatetimeIndex(mumlar["open_time"]) if len(mumlar) else pd.DatetimeIndex([], tz="UTC")
    ozet, nan_s = [], []
    for d in donemler:
        maske = np.asarray(P.donem_ici_4h_maskesi(zamanlar, donem_baslangic=d.baslangic, donem_bitis=d.bitis),
                           dtype=bool) & (zamanlar >= k_bas) & (zamanlar <= k_son)
        t_ler = zamanlar[maske]
        if not len(t_ler):
            continue
        hesap = hesaplanabilirlik(fund, t_ler, kume_bas=k_bas, kume_son=k_son, donem_bas=d.baslangic) \
            if len(fund) else np.zeros(len(t_ler), dtype=bool)
        ozet.append({"sembol": sembol, "donem_baslangic": d.baslangic, "bar": len(t_ler),
                     "hesaplanabilir": int(hesap.sum())})
        nan_s += [{"sembol": sembol, "t": t} for t in t_ler[~hesap]]
    return ozet, nan_s


def main(argv: list[str] | None = None) -> None:
    ayristirici = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ayristirici.add_argument("--etiket", required=True, choices=("once", "sonra"))
    ayristirici.add_argument("--is-parcaci", type=int, default=4)
    ayristirici.add_argument("--semboller", nargs="*", default=None)
    ayristirici.add_argument("--cikti-dizini", type=Path, default=BU_DIZIN)
    argumanlar = ayristirici.parse_args(argv)
    e = argumanlar.etiket
    cikti = argumanlar.cikti_dizini
    with kosu_kilidi("rev10_uygulama", cikti):
        baslangic_zamani = pd.Timestamp.now(tz="UTC")
        git = git_durumu()
        evren = universe_modulu.evren_yukle()
        grup = split_modulu.split_oku().set_index("sembol")["grup"].to_dict()
        gruplar = split_modulu.kume_tanimi(KUME)[0]
        k_bas, k_son = split_modulu.kume_araligi(KUME)
        semboller = [s for s in universe_modulu.dahil_semboller(evren) if grup.get(s) in gruplar]
        donemler = {s: universe_modulu.sembol_donemleri(evren, s) for s in semboller}
        secilen = [s for s in semboller if donemler[s] and (argumanlar.semboller is None or s in argumanlar.semboller)]
        o_s, n_s = [], []
        with ProcessPoolExecutor(max_workers=argumanlar.is_parcaci) as havuz:
            for is_ in [havuz.submit(sembol_olc, s, donemler[s], k_bas, k_son) for s in secilen]:
                o, n = is_.result()
                o_s += o
                n_s += n
        csv_yaz(pd.DataFrame(o_s, columns=["sembol", "donem_baslangic", "bar", "hesaplanabilir"]),
                cikti / f"rev10_uygulama_h2_{e}_tam.csv")
        csv_yaz(pd.DataFrame(n_s, columns=["sembol", "t"]), cikti / f"rev10_uygulama_h2_nan_{e}_tam.csv")
        csv_yaz(ortam_kaydi(git, baslangic_zamani, pd.Timestamp.now(tz="UTC")),
                cikti / f"rev10_uygulama_ortam_{e}_tam.csv")
        o = pd.DataFrame(o_s)
        print(f"KESIF sembol {len(secilen)} | bar {int(o['bar'].sum()) if len(o) else 0} | "
              f"hesaplanabilir {int(o['hesaplanabilir'].sum()) if len(o) else 0} -> {cikti}")


if __name__ == "__main__":
    try:
        main()
    except KosuKilidiHatasi as hata:
        print(f"HATA: {hata}", file=sys.stderr)
        sys.exit(2)
