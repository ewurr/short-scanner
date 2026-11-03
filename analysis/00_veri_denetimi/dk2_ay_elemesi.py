"""D-K2 olcumu: ay elemesi (D-B1) hicbir KESIF kaydini dusurmuyor mu? Yalnizca SAYAR (RESULTS §14.43).

Varsayim: bir ay dosyasindaki kayitlarin hepsi o aya aittir. Dogru degilse, ornegin bir 2025-09 dosyasinda 2025-08'e ait
bir kayit varsa, D-B1'den sonra o kayit KESIF'ten sessizce duser. Olcum C2 dosyalarina DOKUNMADAN yapilir:

1. `kesif`: `split.kesif_kosusu` icinde, butun A sembollerinde yeni kapili yukleyiciyle (`klines.mumlari_yukle`,
   `funding.funding_yukle`, KESIF) donem ici 4h bar sayisi ve donem ici funding kayit sayisi sayilir; F1'de ESKI
   yolla (butun aylar acilarak) uretilmis referanslarla karsilastirilir:
     - 4h: `koruma_pozitif_fiyat_tam.csv`, sutun `KESIF_bar` (`koruma_olcumu.py`; `klines.ham_mumlari_yukle`, butun
       aylar; donem ici = `pencere.donem_ici_4h_maskesi`, KESIF = acilis zamani kume araliginda).
     - funding: `rev9_ritim_kayit_tam.csv`, `kume == "KESIF"` satirlarinin `kayit` toplami (`rev9_ritim.py`;
       `funding.ham_funding_yukle`, butun aylar; donem ici = [donem basi, B] toleransla; kume = odeme zamani).
   Ikinci funding kaniti: donemi KESIF sonunu asan sembolde son KESIF funding kaydi + araligi = C2 basi olmali.
2. `dosya_ayi`: KESIF dosyalarinin (manifestin `kesif` satirlari: A grubu, C2 oncesi) her kaydi dosyanin ayinda mi?
   Ters yon. Onay dosyasi listede yoktur, acilmaz.

Deger okunmaz: cikti yalnizca sayilar ve KESIF tarafindaki zaman damgasi sinirlaridir. Ag yok (kesif kosusu ag yasagi
acar). `_DOGRULANMIS` bellegi sembol basina bosaltilir (yalnizca bellek; olcumu degistirmez).
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

KOK = Path(__file__).resolve().parents[2]
BU_DIZIN = Path(__file__).resolve().parent
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(BU_DIZIN))

import config  # noqa: E402
from calistir import csv_yaz, kosu_kilidi  # noqa: E402
from data import binance_vision as bv  # noqa: E402
from data import funding as funding_modulu  # noqa: E402
from data import klines as klines_modulu  # noqa: E402
from data import pencere as P  # noqa: E402
from data import split as split_modulu  # noqa: E402
from data import universe as universe_modulu  # noqa: E402

CIKTI_SEMBOL = BU_DIZIN / "dk2_ay_elemesi_tam.csv"
CIKTI_DOSYA = BU_DIZIN / "dk2_dosya_ayi_tam.csv"
CIKTI_KAYIT = BU_DIZIN / "dk2_kesif_kaydi_tam.csv"
REF_4H = BU_DIZIN / "koruma_pozitif_fiyat_tam.csv"
REF_FUNDING = BU_DIZIN / "rev9_ritim_kayit_tam.csv"
MANIFEST = KOK / "data" / "onbellek_manifest.csv"


def _donem_ici_4h(zamanlar: pd.DatetimeIndex, donemler) -> np.ndarray:
    ic = np.zeros(len(zamanlar), dtype=bool)
    for d in donemler:
        ic |= np.asarray(P.donem_ici_4h_maskesi(zamanlar, donem_baslangic=d.baslangic, donem_bitis=d.bitis), dtype=bool)
    return ic


def _donem_ici_funding(zamanlar: pd.DatetimeIndex, donemler) -> np.ndarray:
    ic = np.zeros(len(zamanlar), dtype=bool)
    for d in donemler:
        ic |= (np.asarray(P.ayni_ya_da_sonra(zamanlar, d.baslangic), dtype=bool)
               & np.asarray(P.ayni_ya_da_once(zamanlar, d.bitis), dtype=bool))
    return ic


def sembol_say(sembol: str, donemler) -> dict:
    mum = klines_modulu.mumlari_yukle(sembol, config.BAR_4H, "KESIF")
    fr = funding_modulu.funding_yukle(sembol, "KESIF")
    z = pd.DatetimeIndex(mum["open_time"]) if len(mum) else pd.DatetimeIndex([], tz="UTC")
    ic = _donem_ici_4h(z, donemler) if len(z) else np.zeros(0, dtype=bool)
    fz = pd.DatetimeIndex(fr["odeme_zamani"]) if len(fr) else pd.DatetimeIndex([], tz="UTC")
    fic = _donem_ici_funding(fz, donemler) if len(fz) else np.zeros(0, dtype=bool)
    satir = {"sembol": sembol, "yeni_4h": int(ic.sum()), "yeni_funding": int(fic.sum()),
             "ilk_bar": str(z[ic].min()) if ic.any() else "", "son_bar": str(z[ic].max()) if ic.any() else "",
             "son_funding": str(fz[fic].max()) if fic.any() else "",
             "son_funding_aralik_saat": float(fr.loc[fic, "aralik_saat"].iloc[-1]) if fic.any() else np.nan}
    bv.dogrulanmis_bellek_temizle()
    return satir


def kesif_olcumu() -> tuple[pd.DataFrame, dict]:
    tablo = split_modulu.split_oku()
    evren = universe_modulu.evren_yukle()
    a = sorted(set(tablo.loc[tablo["grup"] == "A", "sembol"]) & set(evren["sembol"]))
    donemler = {s: universe_modulu.sembol_donemleri(evren, s) for s in a}
    a = [s for s in a if donemler[s]]
    ref4 = pd.read_csv(REF_4H).set_index("sembol")["KESIF_bar"]
    rf = pd.read_csv(REF_FUNDING)
    reff = rf.loc[rf["kume"] == "KESIF"].groupby("sembol")["kayit"].sum()
    kesif_sonu, c2_basi = pd.Timestamp(config.KESIF_SONU), pd.Timestamp(config.C2_BASI)
    satirlar = []
    with split_modulu.kesif_kosusu() as kayit:
        for s in a:
            satir = sembol_say(s, donemler[s])
            satir["ref_4h"] = int(ref4.get(s, 0))
            satir["ref_funding"] = int(reff.get(s, 0))
            asan = max(d.bitis for d in donemler[s]) > kesif_sonu
            satir["donem_kesif_sonunu_asar"] = bool(asan)
            if asan and satir["son_funding"]:
                sonraki = pd.Timestamp(satir["son_funding"]) + pd.Timedelta(hours=satir["son_funding_aralik_saat"])
                satir["son_funding_sonraki_c2_basi"] = bool(abs(sonraki - c2_basi) <= P.ODEME_TOLERANSI)
            else:
                satir["son_funding_sonraki_c2_basi"] = ""
            satirlar.append(satir)
    cerceve = pd.DataFrame(satirlar)
    cerceve["fark_4h"] = cerceve["yeni_4h"] - cerceve["ref_4h"]
    cerceve["fark_funding"] = cerceve["yeni_funding"] - cerceve["ref_funding"]
    sutunlar = ["sembol", "ref_4h", "yeni_4h", "fark_4h", "ref_funding", "yeni_funding", "fark_funding", "ilk_bar",
                "son_bar", "son_funding", "son_funding_aralik_saat", "donem_kesif_sonunu_asar",
                "son_funding_sonraki_c2_basi"]
    return cerceve[sutunlar], kayit.alanlar()


def dosya_ayi_olcumu() -> pd.DataFrame:
    """Manifestin kesif satirlari: her dosyanin kayitlari dosyanin ayinda mi (ters yon)."""
    with open(MANIFEST, encoding="utf-8", newline="") as dosya:
        yollar = [s["yol"] for s in csv.DictReader(dosya) if s["katman"] == "kesif"]
    kok = Path(config.ONBELLEK_DIZINI)
    ozet: dict[str, dict] = {}
    aykirilar = []
    for goreli in yollar:
        tur = goreli.split("/")[0]
        ay = pd.Period(Path(goreli).stem, freq="M")
        sutun = "odeme_zamani" if tur == "funding" else "open_time"
        z = pd.DatetimeIndex(pd.read_parquet(kok / goreli, columns=[sutun])[sutun])
        disari = int((z.tz_convert("UTC").to_period("M") != ay).sum()) if len(z) else 0
        o = ozet.setdefault(tur, {"tur": tur, "dosya": 0, "kayit": 0, "ay_disi_kayit": 0, "ay_disi_dosya": 0})
        o["dosya"] += 1
        o["kayit"] += len(z)
        o["ay_disi_kayit"] += disari
        o["ay_disi_dosya"] += int(disari > 0)
        if disari:
            aykirilar.append(goreli)
    tablo = pd.DataFrame(list(ozet.values()))
    tablo.attrs["aykirilar"] = aykirilar
    return tablo


def main(argv: list[str] | None = None) -> None:
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args(argv)
    with kosu_kilidi("dk2_ay_elemesi"):
        bas = time.perf_counter()
        sembol, kayit = kesif_olcumu()
        csv_yaz(sembol, CIKTI_SEMBOL)
        dosya = dosya_ayi_olcumu()
        csv_yaz(dosya, CIKTI_DOSYA)
        csv_yaz(pd.DataFrame([kayit]), CIKTI_KAYIT)
        asan = sembol[sembol["donem_kesif_sonunu_asar"]]
        print(f"A sembolu {len(sembol)} | 4h fark!=0 {int((sembol['fark_4h'] != 0).sum())} | funding fark!=0 "
              f"{int((sembol['fark_funding'] != 0).sum())} | ref 4h {int(sembol['ref_4h'].sum())} yeni 4h "
              f"{int(sembol['yeni_4h'].sum())} | ref funding {int(sembol['ref_funding'].sum())} yeni funding "
              f"{int(sembol['yeni_funding'].sum())}")
        print(f"donemi KESIF sonunu asan {len(asan)} | son funding + aralik = C2 basi: "
              f"{int((asan['son_funding_sonraki_c2_basi'] == True).sum())}")  # noqa: E712
        print(dosya.to_string(index=False))
        print(f"ay disi kayitli dosya: {dosya.attrs['aykirilar'][:10]} | sure {time.perf_counter() - bas:.1f} s")


if __name__ == "__main__":
    main()
