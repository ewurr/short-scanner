"""Denetci bulgusu D-C5 olcumu: `klines.gunluge_cevir` gunun "tam" oldugunu satir
sayisiyla (6) anlar, 4 saatlik izgaraya hizaya bakmaz.

Bu betik yalnizca ZAMAN DAMGASI okur ve sayar (fiyat, hacim, getiri yok):
- `hizasiz_satir`: acilis zamani 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC
  izgarasinda olmayan 4 saatlik satir sayisi,
- `alti_satirli_hizasiz_gun`: tam 6 satiri olan ama bu 6 satirin acilislari tam
  olarak o gunun alti izgara ani olmayan gun sayisi (`gunluge_cevir`in tam gun
  sayip izgara bari eksik oldugu halde 1d serisine aldigi gunler).
Kod degismez; duzeltme on-kayit Rev.8 uygulanirken yapilacak.

Kullanim:
    python analysis/00_veri_denetimi/hiza_olcumu.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

KOK = Path(__file__).resolve().parents[2]
BU_DIZIN = Path(__file__).resolve().parent
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(BU_DIZIN))

import config  # noqa: E402
from calistir import KosuKilidiHatasi, csv_yaz, git_durumu, kosu_kilidi, ortam_kaydi  # noqa: E402
from data import donem as donem_modulu  # noqa: E402
from data import klines as klines_modulu  # noqa: E402
from data import universe as universe_modulu  # noqa: E402

CIKTI = BU_DIZIN / "hiza_tam.csv"
CIKTI_ORTAM = BU_DIZIN / "hiza_ortam_tam.csv"
ADIM = pd.Timedelta(hours=4)
SUTUNLAR = ["sembol", "satir", "hizasiz_satir", "alti_satirli_gun", "alti_satirli_hizasiz_gun",
            "ilk_hizasiz_gun"]


def hiza_say(sembol: str, zamanlar: pd.DatetimeIndex) -> dict:
    """Bir sembolun 4 saatlik acilis zamanlarinda hiza sayimi. Saf."""
    z = pd.DatetimeIndex(zamanlar)
    gun = z.floor("D")
    hizali = (z - gun) % ADIM == pd.Timedelta(0)
    tablo = pd.DataFrame({"gun": gun, "hizali": hizali})
    gunluk = tablo.groupby("gun").agg(satir=("hizali", "size"), hizali=("hizali", "sum"))
    alti = gunluk.loc[gunluk["satir"] == 6]
    hizasiz_gunler = alti.index[alti["hizali"] < 6]
    # Alti satirin hepsi hizali olsa bile ayni acilis iki kez olabilir; tekrar
    # yukleyicide hata verir (`klines._tekrarsiz_birlestir`), burada ayrica sayilmaz.
    return {"sembol": sembol, "satir": len(z), "hizasiz_satir": int((~hizali).sum()),
            "alti_satirli_gun": len(alti), "alti_satirli_hizasiz_gun": len(hizasiz_gunler),
            "ilk_hizasiz_gun": hizasiz_gunler[0] if len(hizasiz_gunler) else pd.NaT}


def main() -> None:
    with kosu_kilidi("hiza_olcumu", CIKTI.parent):
        baslangic = pd.Timestamp.now(tz="UTC")
        git = git_durumu()
        evren = universe_modulu.evren_yukle()
        satirlar = []
        for sembol in universe_modulu.dahil_semboller(evren):
            mumlar = donem_modulu.toplam_doneme_kes(klines_modulu.ham_mumlari_yukle(sembol, config.BAR_4H),
                                                   "open_time")
            satirlar.append(hiza_say(sembol, pd.DatetimeIndex(mumlar["open_time"])))
        tablo = pd.DataFrame(satirlar, columns=SUTUNLAR)
        csv_yaz(tablo, CIKTI)
        csv_yaz(ortam_kaydi(git, baslangic, pd.Timestamp.now(tz="UTC")), CIKTI_ORTAM)
        print(f"sembol: {len(tablo)}, 4h satir: {int(tablo['satir'].sum())}")
        print(f"hizasiz satir: {int(tablo['hizasiz_satir'].sum())} "
              f"({int((tablo['hizasiz_satir'] > 0).sum())} sembol)")
        print(f"alti satirli gun: {int(tablo['alti_satirli_gun'].sum())}, bunlardan hizasiz: "
              f"{int(tablo['alti_satirli_hizasiz_gun'].sum())} "
              f"({int((tablo['alti_satirli_hizasiz_gun'] > 0).sum())} sembol)")


if __name__ == "__main__":
    try:
        # F1 veri denetimi butun gecmisi olcer (anayasa §3.1): onay verisi izniyle (kapanisin son turu).
        from data import binance_vision as _bv

        with _bv.onay_verisi_izni("F1 veri denetimi: " + Path(__file__).name):
            main()
    except KosuKilidiHatasi as hata:
        raise SystemExit(f"HATA: {hata}") from None
