"""Rev.9 hazirligi, altinci tur: dogrulanamayan kuyruk payindaki kume farki ritimden mi?
YALNIZCA SAYI.

Getiri, fiyat farki ya da funding degeri HESAPLAMAZ ve raporlamaz. Mumlardan yalnizca
acilis zamani, funding kayitlarindan yalnizca odeme zamani ve aralik alani okunur
(CLAUDE.md §3.1, RESULTS §14.9). Veri katmani DEGISMEZ: plan gercek
`pencere.pozisyon_plani`, tamlik olcumu besinci turun olcum fonksiyonudur
(`rev9_hazirlik.capa_duzeltme_tamlik_ayrintisi`); hicbir karar yolunda kullanilmaz.

Soru: `capa_duzeltme_kuyruk_kismi` payi (tam sayilan pozisyonlarda son kayittan pencere
sonuna kalan dilim bir tam araliktan kisa) 4h izgarada kumeler arasinda ayrisiyor
(KESIF %35,8; C1 %36,8; C2 %12,0). Hipotez: fark funding ritminin dagilimindan gelir
(8 saatlikten 4 saatlige kayma), kumelerin kendisinden degil.

Ciktilar:
1. `rev9_ritim_kayit_tam.csv`: donem ici funding kayitlarinin odeme araligina gore
   dagilimi; sembol x kume x yil x aralik. Kume, kaydin odeme zamani ve sembolun
   grubuna gore (`rev8_etki.sinyal_kumesi`); kume araliginin disindaki kayitlar
   `kume = YOK` satirina duser.
2. `rev9_ritim_pozisyon_tam.csv`: rev9_hazirlik ile AYNI pozisyon evreni (butun donem
   ici barlar varsayimsal sinyal, birincil ufuk); sembol x izgara x kume x giris yili x
   ritim kirilimiyla plan, tam, kuyruk sayilari. Ritim sutunlari `pozisyon_ritmi`den.

Ritim tanimi (yalnizca zaman ve aralik alani): capa (giris aninda ya da oncesindeki son
donem ici kayit) ile pencere sonundaki son kayit arasindaki dizide
  - `capa_aralik`: capanin aralik alani,
  - `son_aralik`: dizideki son kaydin aralik alani (kuyrugun uzunlugunu belirleyen),
  - `tek_ritim`: dizideki butun araliklar ayni.
Ritim, tamlik hukmune girmez; yalnizca kirilim etiketidir.

Kullanim:
    python analysis/00_veri_denetimi/rev9_ritim.py --is-parcaci 8
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
from data import funding as funding_modulu  # noqa: E402
from data import klines as klines_modulu  # noqa: E402
from data import pencere as pencere_modulu  # noqa: E402
from data import split as split_modulu  # noqa: E402
from data import universe as universe_modulu  # noqa: E402
from rev8_etki import kume_sinirlari, sinyal_kumesi  # noqa: E402
from rev9_hazirlik import capa_duzeltme_tamlik_ayrintisi, son_hal_pencere_sonu  # noqa: E402

P = pencere_modulu
CIKTI_KAYIT = BU_DIZIN / "rev9_ritim_kayit_tam.csv"
CIKTI_POZISYON = BU_DIZIN / "rev9_ritim_pozisyon_tam.csv"
CIKTI_ORTAM = BU_DIZIN / "rev9_ritim_ortam_tam.csv"


def pozisyon_ritmi(funding: pd.DataFrame, girisler, pencere_sonlari, donem_baslari) -> pd.DataFrame:
    """Her pozisyon icin ritim etiketleri. Vektorel, saf; yalnizca odeme ZAMANI ve ARALIGI.

    Sutunlar: `capa_aralik` (capanin aralik alani), `son_aralik` (penceredeki son kaydin
    araligi), `tek_ritim` (capadan son kayda kadar butun araliklar ayni), `kayit_sayisi`
    (capa dahil, dizideki kayit sayisi). Capa yoksa araliklar NaN, `tek_ritim` False,
    `kayit_sayisi` 0. Tamlik hukmune girmez.
    """
    girisler = pd.DatetimeIndex(girisler)
    sonlar = pd.DatetimeIndex(pencere_sonlari)
    baslar = pd.DatetimeIndex(donem_baslari)
    if not (len(girisler) == len(sonlar) == len(baslar)):
        raise ValueError("girisler, pencere_sonlari ve donem_baslari ayni uzunlukta olmali.")
    n = len(girisler)
    sonuc = pd.DataFrame({"capa_aralik": np.full(n, np.nan), "son_aralik": np.full(n, np.nan),
                          "tek_ritim": np.zeros(n, dtype=bool), "kayit_sayisi": np.zeros(n, dtype="int64")})
    if n == 0 or funding.empty:
        return sonuc
    zamanlar = funding_modulu._zaman_dizisi(funding, "pozisyon_ritmi")
    aralik = pd.to_numeric(funding["aralik_saat"], errors="coerce").to_numpy(dtype=float)
    j = zamanlar.searchsorted(P.ayni_an_sonu(girisler), side="left") - 1  # capa
    jj = np.maximum(j, 0)
    son_i = np.maximum(zamanlar.searchsorted(P.ayni_an_sonu(sonlar), side="left") - 1, jj)
    capa_var = (j >= 0) & np.asarray(P.ayni_ya_da_sonra(zamanlar[jj], baslar), dtype=bool)
    degisim = (aralik[1:] != aralik[:-1]) if len(aralik) > 1 else np.zeros(0, dtype=bool)
    p_degisim = np.r_[0, np.cumsum(degisim)]
    sonuc["capa_aralik"] = np.where(capa_var, aralik[jj], np.nan)
    sonuc["son_aralik"] = np.where(capa_var, aralik[son_i], np.nan)
    sonuc["tek_ritim"] = capa_var & ((p_degisim[son_i] - p_degisim[jj]) == 0)
    sonuc["kayit_sayisi"] = np.where(capa_var, son_i - jj + 1, 0)
    return sonuc


def kayit_satirlari(sembol: str, grup: str, donemler, seri: pd.DataFrame, kumeler) -> list[dict]:
    """Donem ici funding kayitlarinin aralik dagilimi; sembol x kume x yil x aralik. Saf."""
    if seri.empty or not donemler:
        return []
    z = pd.DatetimeIndex(seri["odeme_zamani"])
    aralik = pd.to_numeric(seri["aralik_saat"], errors="coerce").to_numpy(dtype=float)
    ic = np.zeros(len(z), dtype=bool)
    for d in donemler:
        ic |= (np.asarray(P.ayni_ya_da_sonra(z, d.baslangic), dtype=bool)
               & np.asarray(P.ayni_ya_da_once(z, d.bitis), dtype=bool))
    tablo = pd.DataFrame({"odeme_zamani": z[ic], "aralik_saat": aralik[ic]})
    if tablo.empty:
        return []
    tablo["kume"] = [sinyal_kumesi(t, grup, kumeler) or "YOK" for t in tablo["odeme_zamani"]]
    tablo["yil"] = pd.DatetimeIndex(tablo["odeme_zamani"]).year
    sayim = tablo.groupby(["kume", "yil", "aralik_saat"], dropna=False).size().reset_index(name="kayit")
    sayim.insert(0, "sembol", sembol)
    return sayim.to_dict("records")


def pozisyon_satirlari(sembol: str, grup: str, donemler, mumlar: pd.DataFrame, seri: pd.DataFrame,
                       kumeler) -> list[dict]:
    """rev9_hazirlik.baslangic_ve_farklar ile AYNI pozisyon evreni; kuyruk sayilari ritim
    kirilimiyla. Saf."""
    zamanlar = pd.DatetimeIndex(mumlar["open_time"])
    satirlar = []
    for bar in sorted(set(config.HIPOTEZ_IZGARASI.values())):
        ufuk = config.BIRINCIL_UFUK[bar]
        girisler, sonlar, baslar, plan_kumeleri = [], [], [], []
        for d in donemler:
            maske = np.asarray(P.donem_ici_4h_maskesi(zamanlar, donem_baslangic=d.baslangic,
                                                      donem_bitis=d.bitis), dtype=bool)
            zd = zamanlar[maske]
            if bar == config.BAR_1D:
                sinyaller = pd.DatetimeIndex(klines_modulu.gunluge_cevir(mumlar, donemler=[d])["open_time"])
            else:
                sinyaller = zd
            for t in sinyaller:
                kume = sinyal_kumesi(t, grup, kumeler)
                if kume is None:
                    continue
                try:
                    plan = P.pozisyon_plani(zd, t, ufuk, bar, birincil_ufuk=ufuk,
                                            kume_baslangic=kumeler[kume][1], kume_bitis=kumeler[kume][2],
                                            donem_baslangic=d.baslangic, donem_bitis=d.bitis)
                except P.OlayOlusmaz:
                    continue
                girisler.append(plan.giris)
                sonlar.append(son_hal_pencere_sonu(plan.cikis_ani, plan.cikis_turu, d.bitis, d.kapanis))
                baslar.append(d.baslangic)
                plan_kumeleri.append(kume)
        if not girisler:
            continue
        cd = capa_duzeltme_tamlik_ayrintisi(seri, girisler, sonlar, baslar)
        rt = pozisyon_ritmi(seri, girisler, sonlar, baslar)
        tablo = pd.DataFrame({
            "kume": plan_kumeleri,
            "yil": pd.DatetimeIndex(girisler).year,
            "capa_aralik": rt["capa_aralik"].to_numpy(),
            "son_aralik": rt["son_aralik"].to_numpy(),
            "tek_ritim": rt["tek_ritim"].to_numpy(),
            "tam": cd["tam"].to_numpy(),
            "kuyruk_kismi": cd["kuyruk_kismi"].to_numpy(),
            "kuyruk_sifir": cd["kuyruk_sifir"].to_numpy(),
            "kuyruk_dogrulanmamis": cd["kuyruk_dogrulanmamis"].to_numpy(),
            "son_esitlik_affi": cd["son_esitlik_affi"].to_numpy(),
        })
        sayim = tablo.groupby(["kume", "yil", "capa_aralik", "son_aralik", "tek_ritim"], dropna=False).agg(
            plan=("tam", "size"), tam=("tam", "sum"), kuyruk_kismi=("kuyruk_kismi", "sum"),
            kuyruk_sifir=("kuyruk_sifir", "sum"), kuyruk_dogrulanmamis=("kuyruk_dogrulanmamis", "sum"),
            son_esitlik_affi=("son_esitlik_affi", "sum")).reset_index()
        sayim.insert(0, "bar", bar)
        sayim.insert(0, "sembol", sembol)
        satirlar += sayim.to_dict("records")
    return satirlar


def sembol_olc(sembol: str, grup: str, donemler):
    """Bir sembolun iki olcumu. Is parcacigi (ayri surec) icinde calisir."""
    mumlar = donem_modulu.toplam_doneme_kes(klines_modulu.ham_mumlari_yukle(sembol, config.BAR_4H), "open_time")
    fund = donem_modulu.toplam_doneme_kes(funding_modulu.ham_funding_yukle(sembol), "odeme_zamani")
    seri = funding_modulu.donem_sonrasi_kayitlari_at(fund, donemler, config.BAR_4H) if len(fund) else fund
    if seri.empty:
        seri = pd.DataFrame({"odeme_zamani": pd.DatetimeIndex([], tz="UTC"), "aralik_saat": np.empty(0)})
    # Oran sutunlari hicbir fonksiyona verilmez (yalnizca zaman ve aralik).
    seri = seri.loc[:, ["odeme_zamani", "aralik_saat"]].reset_index(drop=True)
    kumeler = kume_sinirlari()
    return (kayit_satirlari(sembol, grup, donemler, seri, kumeler),
            pozisyon_satirlari(sembol, grup, donemler, mumlar, seri, kumeler))


def main(argv: list[str] | None = None) -> None:
    ayristirici = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ayristirici.add_argument("--is-parcaci", type=int, default=4, help="es zamanli surec sayisi")
    ayristirici.add_argument("--semboller", nargs="*", default=None, help="yalnizca bu semboller (deneme)")
    ayristirici.add_argument("--cikti-dizini", type=Path, default=BU_DIZIN, help="CSV dizini (deneme icin)")
    argumanlar = ayristirici.parse_args(argv)
    with kosu_kilidi("rev9_ritim", CIKTI_ORTAM.parent):
        baslangic_zamani = pd.Timestamp.now(tz="UTC")
        git = git_durumu()
        evren = universe_modulu.evren_yukle()
        grup = split_modulu.split_oku().set_index("sembol")["grup"].to_dict()
        semboller = universe_modulu.dahil_semboller(evren)
        donemler = {s: universe_modulu.sembol_donemleri(evren, s) for s in semboller}
        secilen = [s for s in semboller if donemler[s] and (argumanlar.semboller is None or s in argumanlar.semboller)]
        k_s, p_s = [], []
        with ProcessPoolExecutor(max_workers=argumanlar.is_parcaci) as havuz:
            isler = [havuz.submit(sembol_olc, s, grup[s], donemler[s]) for s in secilen]
            for is_ in isler:
                a, b = is_.result()
                k_s += a
                p_s += b
        cikti = argumanlar.cikti_dizini
        csv_yaz(pd.DataFrame(k_s), cikti / CIKTI_KAYIT.name)
        csv_yaz(pd.DataFrame(p_s), cikti / CIKTI_POZISYON.name)
        csv_yaz(ortam_kaydi(git, baslangic_zamani, pd.Timestamp.now(tz="UTC")), cikti / CIKTI_ORTAM.name)
        print(f"sembol {len(secilen)} | kayit satiri {len(k_s)} | pozisyon satiri {len(p_s)} -> {cikti}")


if __name__ == "__main__":
    try:
        main()
    except KosuKilidiHatasi as hata:
        print(f"HATA: {hata}", file=sys.stderr)
        sys.exit(2)
