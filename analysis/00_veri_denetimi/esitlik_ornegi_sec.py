"""Gercek veri esitlik orneginin secimi (performans 2a, plan v2 karar 6; denetci D-B5). Bir kez kosulur, ciktisi sabittir.

`esitlik_ornegi.csv` performans kodundan ONCE commit edilir ve bundan sonra degismez. Secim YALNIZCA F1 denetim
tablolarinin kapsama ve ritim sutunlarina bakar; hicbir fiyat, hacim, getiri ya da sinyal degeri okunmaz (her tablo
`usecols` ile yalnizca asagida adi gecen sutunlarla okunur). Kural mekaniktir: olcutler sirayla islenir ve her olcutte,
o olcutu saglayan, A grubunda, evrenden haric tutulmamis ve henuz secilmemis sembollerin ALFABETIK OLARAK ILKI secilir
(uzun bosluk olcutunde en uzun bosluk, esitlikte alfabetik ilk). Boylece secim sonuca bakilarak yonlendirilemez.

Olcutler (plan_performans_2 §7, prompt_perf2a adim 2):
  1. SOLUSDT                  -- sabit (RESULTS §14.40 esitlik kumesi)
  2. XRPUSDT                  -- sabit (RESULTS §14.40 esitlik kumesi)
  3. delist                   -- `delist_siniflandirmasi_tam.csv` `sinif == "SETTLING"`; en az bir donemi KESIF'le kesisir
                                 (evren `donem_baslangic` <= KESIF sonu)
  4. iki donemli              -- `sembol_ozeti_tam.csv` `donem_sayisi == 2`; iki donem de KESIF'le kesisir (evren)
  5. funding ritmi degisen    -- `rev9_ritim_kayit_tam.csv` `kume == "KESIF"` satirlarinda `aralik_saat` en az iki farkli
  6. funding'i gec baslayan   -- `rev9_uygulama_baslangic_tam.csv` `kume == "KESIF"`, `capa_yok > 0` (donem basindaki
                                 pozisyonlarin capasi yok: funding donem icinde sonra basliyor)
  7. uzun bosluklu            -- `bosluklar_tam.csv` `donem_bolen == False` satirlarinda en buyuk `eksik_bar` (donem ici,
                                 donemi bolmeyen en uzun bosluk; donemi bolen bosluk olcut 4'un konusudur)
  8. donemi KESIF sonunu asan -- `dk2_ay_elemesi_tam.csv` `donem_kesif_sonunu_icerir == True`
Ag ve onbellek okumasi yoktur; evren ve bolme tablolari `data/` katmaninin okuyuculariyla okunur.

Rastgele bar ornekleminin tohumu (esitlik betigi `esitlik_kapi.py`, `--bar ornek`). `config.TOHUM`'dan, kosu sirasindan
bagimsiz turetilir (`data.ornekleme.tohum_turet` ile ayni bicim, ayri bir onek):
    metin = "|".join((str(config.TOHUM), "esitlik", sembol, str(donem_no), hipotez, yapilandirma_kimligi, rol))
    tohum = int.from_bytes(hashlib.sha256(metin.encode("utf-8")).digest()[:8], "big")
    secim = numpy.random.default_rng(tohum).choice(<donem ici bar sayisi>, size=N, replace=False)
Sinir barlari (donemin ilk ve son 200 bari, kume sinirinin +-200 bari, funding ritim degisiminin +-20 bari) ornege
tohumdan bagimsiz eklenir.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

KOK = Path(__file__).resolve().parents[2]
BU_DIZIN = Path(__file__).resolve().parent
sys.path.insert(0, str(KOK))

import config  # noqa: E402
from data import split as split_modulu  # noqa: E402
from data import universe as universe_modulu  # noqa: E402

CIKTI = BU_DIZIN / "esitlik_ornegi.csv"
SUTUNLAR = ["sembol", "olcut", "kaynak_tablo", "kaynak_sutun", "kural"]


def _tablo(ad: str, sutunlar: list[str]) -> pd.DataFrame:
    return pd.read_csv(BU_DIZIN / ad, usecols=sutunlar)


def secim() -> pd.DataFrame:
    bolme = split_modulu.split_oku()
    a_grubu = set(bolme.loc[bolme["grup"] == "A", "sembol"])
    evren = universe_modulu.evren_yukle()[["sembol", "haric", "donem_id", "donem_baslangic"]]
    gecerli = evren.loc[~evren["haric"] & (evren["donem_id"] >= 0)]
    uygun = sorted(a_grubu & set(gecerli["sembol"]))
    kesif_sonu = pd.Timestamp(config.KESIF_SONU)
    kesif_donem_sayisi = (gecerli.loc[pd.to_datetime(gecerli["donem_baslangic"], utc=True) <= kesif_sonu]
                          .groupby("sembol").size())

    secilen: list[dict] = []

    def ekle(adaylar, olcut, tablo, sutun, kural):
        adaylar = [s for s in adaylar if s in uygun and s not in {x["sembol"] for x in secilen}]
        if not adaylar:
            raise RuntimeError(f"{olcut}: olcutu saglayan secilmemis A sembolu yok")
        secilen.append({"sembol": adaylar[0], "olcut": olcut, "kaynak_tablo": tablo, "kaynak_sutun": sutun,
                        "kural": kural})

    ekle(["SOLUSDT"], "sabit_SOLUSDT", "-", "-", "RESULTS §14.40 esitlik kumesi")
    ekle(["XRPUSDT"], "sabit_XRPUSDT", "-", "-", "RESULTS §14.40 esitlik kumesi")

    dl = _tablo("delist_siniflandirmasi_tam.csv", ["sembol", "sinif"])
    ekle(sorted(s for s in dl.loc[dl["sinif"] == "SETTLING", "sembol"] if kesif_donem_sayisi.get(s, 0) >= 1),
         "delist", "delist_siniflandirmasi_tam.csv", "sinif",
         "sinif == SETTLING; en az bir donem KESIF ile kesisir (evren donem_baslangic)")

    so = _tablo("sembol_ozeti_tam.csv", ["sembol", "donem_sayisi"])
    ekle(sorted(s for s in so.loc[so["donem_sayisi"] == 2, "sembol"] if kesif_donem_sayisi.get(s, 0) == 2),
         "iki_donemli", "sembol_ozeti_tam.csv", "donem_sayisi",
         "donem_sayisi == 2; iki donem de KESIF ile kesisir (evren donem_baslangic)")

    rt = _tablo("rev9_ritim_kayit_tam.csv", ["sembol", "kume", "aralik_saat"])
    farkli = rt.loc[rt["kume"] == "KESIF"].groupby("sembol")["aralik_saat"].nunique()
    ekle(sorted(farkli[farkli >= 2].index), "funding_ritmi_degisen", "rev9_ritim_kayit_tam.csv", "aralik_saat",
         "kume == KESIF satirlarinda aralik_saat en az iki farkli deger")

    bs = _tablo("rev9_uygulama_baslangic_tam.csv", ["sembol", "kume", "capa_yok"])
    ekle(sorted(set(bs.loc[(bs["kume"] == "KESIF") & (bs["capa_yok"] > 0), "sembol"])), "funding_gec_baslayan",
         "rev9_uygulama_baslangic_tam.csv", "capa_yok", "kume == KESIF, capa_yok > 0")

    bo = _tablo("bosluklar_tam.csv", ["sembol", "eksik_bar", "donem_bolen"])
    bo = bo.loc[~bo["donem_bolen"].astype(bool) & bo["sembol"].isin(uygun)
                & ~bo["sembol"].isin([x["sembol"] for x in secilen])]
    bo = bo.sort_values(["eksik_bar", "sembol"], ascending=[False, True])
    ekle(list(bo["sembol"]), "uzun_bosluklu", "bosluklar_tam.csv", "eksik_bar",
         "donem_bolen == False satirlarinda en buyuk eksik_bar (esitlikte alfabetik ilk)")

    dk = _tablo("dk2_ay_elemesi_tam.csv", ["sembol", "donem_kesif_sonunu_icerir"])
    ekle(sorted(dk.loc[dk["donem_kesif_sonunu_icerir"].astype(bool), "sembol"]), "donemi_kesif_sonunu_asan",
         "dk2_ay_elemesi_tam.csv", "donem_kesif_sonunu_icerir", "donem_kesif_sonunu_icerir == True")
    return pd.DataFrame(secilen, columns=SUTUNLAR)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--yaz", action="store_true", help="esitlik_ornegi.csv dosyasini yazar (yoksa yalnizca gosterir)")
    arg = ap.parse_args(argv)
    tablo = secim()
    print(tablo.to_string(index=False))
    if arg.yaz:
        if CIKTI.exists():
            raise SystemExit(f"{CIKTI.name} zaten var; ornek sabittir ve degismez.")
        tablo.to_csv(CIKTI, index=False, lineterminator="\n")


if __name__ == "__main__":
    main()
