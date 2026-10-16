"""Koruma turu olcumleri. Yalnizca SAYAR; hicbir getiri, ortalama ya da fark hesaplamaz.

1. `pozitif_fiyat` (madde 2a): donem ici butun 4h barlarda `open`, `high`, `low`, `close`
   sutunlarindan herhangi birinin SIFIR ya da NEGATIF oldugu bar sayisi. Butun evren (A ve B
   gruplari), sembol ve kume kirilimi. Kume kirilimi barin tarihine gore yapilir (`split.kume_araligi`);
   hicbir kume araligina dusmeyen donem ici barlar `kume_disi` satirinda sayilir.

   Olcum KARARA baglidir (madde 2b): sayi sifirsa sifir/negatif fiyat mesru bir piyasa durumu
   degil bozuk veridir ve kapi bunu `VeriHatasi` ile reddeder; sayi sifirdan buyukse bu bir
   KURAL sorusudur ve on-kayit karari (Rev.14) gerekir.

   Deger okunmaz: cikti yalnizca bar SAYILARIDIR (CLAUDE.md §3.1 anlaminda denetim).

2. `donem_siniri` (madde 6): bar duzeyli mevcutluk olcutunun donem sinirlarina uygulanmasinin
   etkisi. `donem.gercek_bar_maskesi` yalnizca hacme bakiyordu; fiyat hucresi bozuk ama hacmi
   pozitif bir bar, seride bulunmadigi halde donem sinirini tanimlayabiliyordu. Olcum, iki
   maskenin farkli oldugu bar sayisini ve sinirin degistigi donem sayisini verir.

Veri tabani `klines.ham_mumlari_yukle`dir (F1 denetiminin tum gecmisi okuyan yolu); kume erisim
denetimi bu yolda uygulanmaz, bu yuzden betik yalnizca SAYI uretir ve hicbir sinyal/olay kurmaz.
Ag erisimi yok: onbellek koskudan once doldurulmus olmalidir.
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
from calistir import KosuKilidiHatasi, csv_yaz, git_durumu, kosu_kilidi, ortam_kaydi  # noqa: E402
from data import donem as donem_modulu  # noqa: E402
from data import klines as klines_modulu  # noqa: E402
from data import pencere as pencere_modulu  # noqa: E402
from data import split as split_modulu  # noqa: E402
from data import universe as universe_modulu  # noqa: E402

# Fiyat sutunlari: pozitiflik yalnizca FIYAT icin anlamlidir (hacim sifir olabilir).
FIYAT_SUTUNLARI = ("open", "high", "low", "close")


def _donem_ici_maske(zamanlar: pd.DatetimeIndex, donemler) -> np.ndarray:
    ici = np.zeros(len(zamanlar), dtype=bool)
    for d in donemler:
        ici |= np.asarray(pencere_modulu.donem_ici_4h_maskesi(
            zamanlar, donem_baslangic=d.baslangic, donem_bitis=d.bitis), dtype=bool)
    return ici


def _kume_maskeleri(zamanlar: pd.DatetimeIndex, grup: str) -> dict[str, np.ndarray]:
    """Kume maskeleri: kume = (gruplar, tarih araligi) (on-kayit §3).

    Sembolun grubu kumenin gruplarinda yoksa o kume icin maske bostur; yoksa KESIF ile C1 ayni
    tarih araligini paylastigi icin her bar iki kez sayilirdi.
    """
    maskeler = {}
    for kume in config.KUMELER:
        gruplar, bas, son = split_modulu.kume_tanimi(kume)
        if grup not in gruplar:
            maskeler[kume] = np.zeros(len(zamanlar), dtype=bool)
            continue
        maskeler[kume] = np.asarray(
            (zamanlar >= pd.Timestamp(bas)) & (zamanlar <= pd.Timestamp(son)), dtype=bool)
    return maskeler


# --- 1. Pozitif fiyat (madde 2a) --------------------------------------------------------------


def pozitif_fiyat_olc(sembol: str, donemler, grup: str) -> tuple[list[dict], list[dict]]:
    """Bir sembolun donem ici 4h barlarinda sifir/negatif fiyatli bar sayisi. Saf sayim."""
    mumlar = klines_modulu.ham_mumlari_yukle(sembol, config.BAR_4H)
    if mumlar.empty or not donemler:
        return [], []
    zamanlar = pd.DatetimeIndex(mumlar["open_time"])
    ici = _donem_ici_maske(zamanlar, donemler)
    if not ici.any():
        return [], []

    pozitif_olmayan = np.zeros(len(mumlar), dtype=bool)
    sutun_satirlari = []
    for sutun in FIYAT_SUTUNLARI:
        if sutun not in mumlar:
            continue
        degerler = pd.to_numeric(mumlar[sutun], errors="coerce").to_numpy(dtype=float)
        with np.errstate(invalid="ignore"):
            bozuk = ici & np.isfinite(degerler) & (degerler <= 0)
        pozitif_olmayan |= bozuk
        if bozuk.any():
            sutun_satirlari.append({"sembol": sembol, "sutun": sutun, "bar": int(bozuk.sum()),
                                    "en_erken": str(zamanlar[bozuk].min()),
                                    "en_gec": str(zamanlar[bozuk].max())})

    satir = {"sembol": sembol, "grup": grup, "donem_ici_bar": int(ici.sum()),
             "pozitif_olmayan_bar": int(pozitif_olmayan.sum())}
    maskeler = _kume_maskeleri(zamanlar, grup)
    for kume, maske in maskeler.items():
        satir[f"{kume}_bar"] = int((ici & maske).sum())
        satir[f"{kume}_pozitif_olmayan"] = int((pozitif_olmayan & maske).sum())
    kume_disi = ici & ~np.logical_or.reduce(list(maskeler.values()))
    satir["kume_disi_bar"] = int(kume_disi.sum())
    satir["kume_disi_pozitif_olmayan"] = int((pozitif_olmayan & kume_disi).sum())
    return [satir], sutun_satirlari


def pozitif_fiyat_kosusu(secilen, donemler, gruplar, cikti: Path) -> str:
    satirlar, sutunlar = [], []
    for sembol in secilen:
        s, c = pozitif_fiyat_olc(sembol, donemler[sembol], gruplar.get(sembol, ""))
        satirlar += s
        sutunlar += c
    cerceve = pd.DataFrame(satirlar)
    csv_yaz(cerceve, cikti / "koruma_pozitif_fiyat_tam.csv")
    csv_yaz(pd.DataFrame(sutunlar, columns=["sembol", "sutun", "bar", "en_erken", "en_gec"]),
            cikti / "koruma_pozitif_fiyat_sutun_tam.csv")
    if cerceve.empty:
        return "sembol yok"
    kume_satirlari = []
    for kume in list(config.KUMELER) + ["kume_disi"]:
        kume_satirlari.append({"kume": kume,
                               "donem_ici_bar": int(cerceve[f"{kume}_bar"].sum()),
                               "pozitif_olmayan_bar": int(cerceve[f"{kume}_pozitif_olmayan"].sum()),
                               "sembol": int((cerceve[f"{kume}_pozitif_olmayan"] > 0).sum())})
    csv_yaz(pd.DataFrame(kume_satirlari), cikti / "koruma_pozitif_fiyat_kume_tam.csv")
    ozet = " | ".join(f"{s['kume']}: bar {s['donem_ici_bar']}, pozitif olmayan {s['pozitif_olmayan_bar']}"
                      for s in kume_satirlari)
    return (f"sembol {len(cerceve)} | donem ici 4h bar {int(cerceve['donem_ici_bar'].sum())} | "
            f"sifir ya da negatif fiyatli bar {int(cerceve['pozitif_olmayan_bar'].sum())} "
            f"(sembol {int((cerceve['pozitif_olmayan_bar'] > 0).sum())}) || {ozet}")


# --- 2. Donem siniri (madde 6) ----------------------------------------------------------------


def donem_siniri_olc(sembol: str) -> list[dict]:
    """Bar duzeyli olcutun donem sinirlarina etkisi: iki maskenin farki ve sinir degisimi."""
    mumlar = klines_modulu.ham_mumlari_yukle(sembol, config.BAR_4H)
    if mumlar.empty:
        return []
    hacim_maskesi = np.asarray(donem_modulu.gercek_bar_maskesi(mumlar), dtype=bool)
    hucre_tam = np.asarray(klines_modulu.hucreleri_tam_mi(mumlar), dtype=bool)
    yeni_maske = hacim_maskesi & hucre_tam
    fark = int((hacim_maskesi != yeni_maske).sum())
    zamanlar = pd.DatetimeIndex(mumlar["open_time"])
    eski_ilk = str(zamanlar[hacim_maskesi].min()) if hacim_maskesi.any() else ""
    eski_son = str(zamanlar[hacim_maskesi].max()) if hacim_maskesi.any() else ""
    yeni_ilk = str(zamanlar[yeni_maske].min()) if yeni_maske.any() else ""
    yeni_son = str(zamanlar[yeni_maske].max()) if yeni_maske.any() else ""
    return [{"sembol": sembol, "bar": len(mumlar), "gercek_bar_eski": int(hacim_maskesi.sum()),
             "gercek_bar_yeni": int(yeni_maske.sum()), "fark_bar": fark,
             "ilk_bar_degisti": int(eski_ilk != yeni_ilk), "son_bar_degisti": int(eski_son != yeni_son),
             "eski_ilk": eski_ilk, "yeni_ilk": yeni_ilk, "eski_son": eski_son, "yeni_son": yeni_son}]


def donem_siniri_kosusu(secilen, donemler, gruplar, cikti: Path) -> str:
    satirlar = []
    for sembol in secilen:
        satirlar += donem_siniri_olc(sembol)
    cerceve = pd.DataFrame(satirlar)
    csv_yaz(cerceve, cikti / "koruma_donem_siniri_tam.csv")
    if cerceve.empty:
        return "sembol yok"
    return (f"sembol {len(cerceve)} | maskesi degisen bar {int(cerceve['fark_bar'].sum())} | "
            f"ilk bari degisen sembol {int(cerceve['ilk_bar_degisti'].sum())} | "
            f"son bari degisen sembol {int(cerceve['son_bar_degisti'].sum())}")


OLCUMLER = {
    "pozitif_fiyat": ("koruma_pozitif_fiyat", pozitif_fiyat_kosusu),
    "donem_siniri": ("koruma_donem_siniri", donem_siniri_kosusu),
}


def main(argv: list[str] | None = None) -> None:
    ayristirici = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ayristirici.add_argument("--olcum", required=True, choices=tuple(OLCUMLER))
    ayristirici.add_argument("--semboller", nargs="*", default=None)
    ayristirici.add_argument("--cikti-dizini", type=Path, default=BU_DIZIN)
    argumanlar = ayristirici.parse_args(argv)
    kilit_adi, kosu = OLCUMLER[argumanlar.olcum]
    cikti = argumanlar.cikti_dizini
    with kosu_kilidi(kilit_adi, cikti):
        baslangic_zamani = pd.Timestamp.now(tz="UTC")
        git = git_durumu()
        evren = universe_modulu.evren_yukle()
        gruplar = split_modulu.split_oku().set_index("sembol")["grup"].to_dict()
        semboller = list(universe_modulu.dahil_semboller(evren))   # butun evren: A ve B
        donemler = {s: universe_modulu.sembol_donemleri(evren, s) for s in semboller}
        secilen = [s for s in semboller
                   if argumanlar.semboller is None or s in argumanlar.semboller]
        ozet = kosu(secilen, donemler, gruplar, cikti)
        csv_yaz(ortam_kaydi(git, baslangic_zamani, pd.Timestamp.now(tz="UTC")),
                cikti / f"{kilit_adi}_ortam_tam.csv")
        print(f"{ozet} -> {cikti}")


if __name__ == "__main__":
    try:
        # F1 veri denetimi butun gecmisi olcer (anayasa §3.1): onay verisi izniyle. Betik
        # yalnizca SAYAR; hicbir fiyat degeri, getiri ya da olay uretmez.
        from data import binance_vision as _bv

        with _bv.onay_verisi_izni("F1 veri denetimi: " + Path(__file__).name):
            main()
    except KosuKilidiHatasi as hata:
        print(f"HATA: {hata}", file=sys.stderr)
        sys.exit(2)
