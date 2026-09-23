"""Rev.8 uygulamasinin etki sayimlari (on-kayit §4 rev.8; RESULTS §14). YALNIZCA SAYI.

Getiri, fiyat farki ya da funding degeri HESAPLAMAZ ve raporlamaz. Mumlardan
acilis zamani ve (donem sonu turu icin) hacmin sifir olup olmadigi, funding
kayitlarindan odeme zamani ve aralik alani okunur (denetim siniri: CLAUDE.md §3.1,
RESULTS §14.9). 1d sinyal gunleri gercek `klines.gunluge_cevir`den gelir; o fonksiyon
fiyat sutunlarini gunluge toplar, betik ciktisindan yalnizca `open_time`i okur. Kurallar veri katmanindan
cagrilir; betik kopyasini tasimaz.

1. Baslangic boslugu etkisi (`rev8_etki_baslangic_tam.csv`): butun donem ici
   barlar (1d'de butun donem ici gunler) varsayimsal sinyal; her hipotezin
   izgarasi ve birincil ufku (`config.HIPOTEZ_IZGARASI`, `config.BIRINCIL_UFUK`),
   kume kirilimi (KESIF / C1 / C2; sembolun grubu ve sinyal zamani). Plan gercek
   `pencere.pozisyon_plani`, tamlik Rev.8 kurali (`rev8_tamlik.rev8_tamlik_ayrintisi`, tarihsel donmus
   kopya; Rev.9 ile veri katmanindaki kural degisti).
   Sinyal pencereleri ve uygunluk filtreleri UYGULANMAZ: sayim olasi olaylarin
   ust kumesidir. "Yalniz baslangic": diger dort kosul tam, baslangic kosulu
   bozuk (rev.7'de funding'i tam sayilan, rev.8'de dusen pozisyon).
2. Donem sonlari (`rev8_etki_donem_sonu_tam.csv`): 1d cikis aninin rev.8 oncesi
   kuralla (butun 4h seriden 6 satirli gunler, `calistir.eski_kural_gunleri`;
   donem bitisinden once acilan son gunun kapanisi) ve rev.8 ile (K) karsilastirmasi;
   donemin funding sinifi: evren tablosu (kilitli, rev.7 penceresi) ve gercek
   `funding.donemde_funding_var` (rev.8, [bas, B]).
3. Zaman toleransi (`rev8_etki_zaman_tam.csv`): funding kayitlarinin ve 4h
   barlarin tam saatten en buyuk sapmasi. Toleransin (1 dk, kesin) eski
   uygulamalarla (<= 1 dk, 59 sn) ayrildigi bolgeye dusen kayit sayisi.

Kullanim:
    python analysis/00_veri_denetimi/rev8_etki.py --is-parcaci 8
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
from calistir import (KosuKilidiHatasi, csv_yaz, donem_sonu_turleri, eski_kural_gunleri,  # noqa: E402
                      git_durumu, kosu_kilidi, ortam_kaydi)
from data import donem as donem_modulu  # noqa: E402
from data import funding as funding_modulu  # noqa: E402
from data import klines as klines_modulu  # noqa: E402
from data import pencere as pencere_modulu  # noqa: E402
from data import split as split_modulu  # noqa: E402
from data import universe as universe_modulu  # noqa: E402
from rev8_tamlik import rev8_pencere_sonu, rev8_tamlik_ayrintisi  # noqa: E402

P = pencere_modulu
CIKTI_BASLANGIC = BU_DIZIN / "rev8_etki_baslangic_tam.csv"
CIKTI_DONEM_SONU = BU_DIZIN / "rev8_etki_donem_sonu_tam.csv"
CIKTI_ZAMAN = BU_DIZIN / "rev8_etki_zaman_tam.csv"
CIKTI_ORTAM = BU_DIZIN / "rev8_etki_ortam_tam.csv"

RET_GEREKCELERI = ("olay_olusmaz", "kume_siniri", "ileri_kayma_siniri", "giris_bari_yok")
SUTUNLAR_BASLANGIC = ["sembol", "bar", "kume", "sinyal", "plan", *[f"ret_{g}" for g in RET_GEREKCELERI],
                      "tam", "bozuk", "kayit_yok", "baslangic_bozuk", "yalniz_baslangic"]
SUTUNLAR_DONEM_SONU = ["sembol", "donem_sira", "donem_bitis", "tur", "cikis_1d_eski", "cikis_1d_rev8",
                       "cikis_4h_rev8", "funding_yok_evren", "funding_var_rev8"]
SUTUNLAR_ZAMAN = ["sembol", "funding_kaydi", "funding_en_buyuk_sapma_ms", "funding_29sn_ustu",
                  "bar_4h", "bar_en_buyuk_sapma_ms", "bar_29sn_ustu"]
# Iki kaydin tam saatten sapmalari 29 saniyenin altindaysa aralarindaki fark 58 sn'yi
# asamaz; eski uygulamalarin (59 sn, <= 1 dk) ve rev.8'in (< 1 dk) ayrildigi bolgeye
# (59 sn - 1 dk) hicbir karsilastirma dusemez. Esik sayim icindir, kural degildir.
SAPMA_ESIGI = pd.Timedelta(seconds=29)


def kume_sinirlari() -> dict[str, tuple[tuple[str, ...], pd.Timestamp, pd.Timestamp]]:
    return {k: (split_modulu.kume_tanimi(k)[0], *split_modulu.kume_araligi(k)) for k in config.KUMELER}


def sinyal_kumesi(t: pd.Timestamp, grup: str, kumeler) -> str | None:
    """Sinyalin kumesi: sembolun grubu kumede ve t kume araliginda. Saf."""
    for ad, (gruplar, bas, son) in kumeler.items():
        if grup in gruplar and bas <= t <= son:
            return ad
    return None


def _saat_sapmasi(zamanlar: pd.DatetimeIndex) -> np.ndarray:
    """Tam saate en yakin uzaklik (mutlak). Saf."""
    z = pd.DatetimeIndex(zamanlar)
    return np.abs((z - z.round("h")).to_numpy())


def baslangic_etkisi(sembol: str, grup: str, donemler, mumlar: pd.DataFrame, seri: pd.DataFrame,
                     kumeler) -> list[dict]:
    """Bir sembolde her izgara ve kume icin plan ve tamlik sayimi. Saf; yalnizca zaman okur."""
    zamanlar = pd.DatetimeIndex(mumlar["open_time"])
    satirlar = []
    for bar in sorted(set(config.HIPOTEZ_IZGARASI.values())):
        ufuk = config.BIRINCIL_UFUK[bar]
        sayim: dict[str, dict] = {}
        girisler, sonlar, plan_kumeleri = [], [], []
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
                s = sayim.setdefault(kume, {"sinyal": 0, "plan": 0, **{g: 0 for g in RET_GEREKCELERI}})
                s["sinyal"] += 1
                try:
                    plan = P.pozisyon_plani(zd, t, ufuk, bar, birincil_ufuk=ufuk,
                                            kume_baslangic=kumeler[kume][1], kume_bitis=kumeler[kume][2],
                                            donem_baslangic=d.baslangic, donem_bitis=d.bitis)
                except P.OlayOlusmaz as hata:
                    s[P.ret_gerekcesi(hata)] += 1
                    continue
                s["plan"] += 1
                girisler.append(plan.giris)
                sonlar.append(rev8_pencere_sonu(plan))
                plan_kumeleri.append(kume)
        ayrinti = rev8_tamlik_ayrintisi(seri, girisler, sonlar)
        ayrinti["kume"] = plan_kumeleri
        for kume, s in sorted(sayim.items()):
            a = ayrinti.loc[ayrinti["kume"] == kume]
            digerleri = a["kayit_var"] & a["aralik_gecerli"] & a["ic_tam"] & a["son_tam"]
            satirlar.append({"sembol": sembol, "bar": bar, "kume": kume, "sinyal": s["sinyal"], "plan": s["plan"],
                             **{f"ret_{g}": s[g] for g in RET_GEREKCELERI},
                             "tam": int(a["tam"].sum()), "bozuk": int((~a["tam"]).sum()),
                             "kayit_yok": int((~a["kayit_var"]).sum()),
                             "baslangic_bozuk": int((a["kayit_var"] & ~a["baslangic_tam"]).sum()),
                             "yalniz_baslangic": int((digerleri & ~a["baslangic_tam"]).sum())})
    return satirlar


def donem_sonu_satirlari(sembol: str, donemler, turler, mumlar: pd.DataFrame, fund: pd.DataFrame,
                         funding_yok_evren: dict) -> list[dict]:
    """1d cikis anlari (rev.8 oncesi / rev.8) ve funding sinifi, her donem sonu. Saf."""
    eski_gunler = eski_kural_gunleri(pd.DatetimeIndex(mumlar["open_time"]))
    satirlar = []
    for i, (d, tur) in enumerate(zip(donemler, turler)):
        oncekiler = eski_gunler[eski_gunler <= d.bitis]
        eski = oncekiler[-1] + pd.Timedelta(days=1) if len(oncekiler) else pd.NaT
        satirlar.append({"sembol": sembol, "donem_sira": i, "donem_bitis": d.bitis, "tur": tur,
                         "cikis_1d_eski": eski, "cikis_1d_rev8": d.kapanis, "cikis_4h_rev8": d.kapanis,
                         "funding_yok_evren": bool(funding_yok_evren.get(i, False)),
                         "funding_var_rev8": funding_modulu.donemde_funding_var(fund, d, config.BAR_4H)})
    return satirlar


def sembol_etki(sembol: str, grup: str, donemler, sinif: str | None, veri_sonu_bari: pd.Timestamp,
                funding_yok_evren: dict) -> tuple[list[dict], list[dict], dict]:
    """Bir sembolun uc sayimi. Is parcacigi (ayri surec) icinde calisir."""
    mumlar = donem_modulu.toplam_doneme_kes(klines_modulu.ham_mumlari_yukle(sembol, config.BAR_4H), "open_time")
    fund = donem_modulu.toplam_doneme_kes(funding_modulu.ham_funding_yukle(sembol), "odeme_zamani")
    seri = funding_modulu.donem_sonrasi_kayitlari_at(fund, donemler, config.BAR_4H) if len(fund) else fund
    mz = pd.DatetimeIndex(mumlar["open_time"])
    hacim = mumlar["quote_volume"] if len(donemler) > 1 else None
    turler = donem_sonu_turleri(donemler, sinif, veri_sonu_bari, mz if len(donemler) > 1 else None, hacim)
    baslangic = baslangic_etkisi(sembol, grup, donemler, mumlar, seri, kume_sinirlari())
    donem_sonu = donem_sonu_satirlari(sembol, donemler, turler, mumlar, fund, funding_yok_evren)
    fs = _saat_sapmasi(pd.DatetimeIndex(fund["odeme_zamani"])) if len(fund) else np.zeros(0, "m8[ns]")
    bs = _saat_sapmasi(mz)
    zaman = {"sembol": sembol, "funding_kaydi": len(fs),
             "funding_en_buyuk_sapma_ms": float(fs.max() / np.timedelta64(1, "ms")) if len(fs) else 0.0,
             "funding_29sn_ustu": int((fs >= SAPMA_ESIGI.to_timedelta64()).sum()),
             "bar_4h": len(bs), "bar_en_buyuk_sapma_ms": float(bs.max() / np.timedelta64(1, "ms")) if len(bs) else 0.0,
             "bar_29sn_ustu": int((bs >= SAPMA_ESIGI.to_timedelta64()).sum())}
    return baslangic, donem_sonu, zaman


def _yazdir(baslangic: pd.DataFrame, donem_sonu: pd.DataFrame, zaman: pd.DataFrame) -> None:
    print("--- Baslangic boslugu etkisi (butun donem ici barlar varsayimsal sinyal; yalnizca sayi) ---")
    toplam = baslangic.groupby(["bar", "kume"])[SUTUNLAR_BASLANGIC[3:]].sum()
    for hipotez, bar in config.HIPOTEZ_IZGARASI.items():
        print(f"{hipotez} ({bar}, birincil ufuk {config.BIRINCIL_UFUK[bar]}):")
        for kume in config.KUMELER:
            if (bar, kume) not in toplam.index:
                continue
            r = toplam.loc[(bar, kume)]
            print(f"  {kume:5s} sinyal {int(r['sinyal']):8d} | plan {int(r['plan']):8d} "
                  f"(ret: kume {int(r['ret_kume_siniri'])}, kayma {int(r['ret_ileri_kayma_siniri'])}, "
                  f"giris yok {int(r['ret_giris_bari_yok'])}) | funding tam {int(r['tam']):8d}, bozuk "
                  f"{int(r['bozuk']):6d} (kayit yok {int(r['kayit_yok'])}) | baslangic bozuk "
                  f"{int(r['baslangic_bozuk']):5d} | yalniz baslangic {int(r['yalniz_baslangic']):5d}")
    uyg = donem_sonu.loc[donem_sonu["tur"] != "veri_sonu"]
    degisen = uyg["cikis_1d_eski"] != uyg["cikis_1d_rev8"]
    print("\n--- 1d cikis ani, donem sonu (kural uygulanan) ---")
    print(f"donem sonu {len(uyg)} | cikis ani degisen {int(degisen.sum())} | eski kuralda 1d gunu yok "
          f"{int(uyg['cikis_1d_eski'].isna().sum())} | 4h cikis ani degisen 0 (iki kuralda da K)")
    print("\n--- Funding sinifi: evren tablosu (rev.7) -> rev.8 [bas, B] ---")
    gecen = donem_sonu.loc[~donem_sonu["funding_yok_evren"] & ~donem_sonu["funding_var_rev8"]]
    donen = donem_sonu.loc[donem_sonu["funding_yok_evren"] & donem_sonu["funding_var_rev8"]]
    print(f"donem {len(donem_sonu)} | funding'siz: evren {int(donem_sonu['funding_yok_evren'].sum())}, rev.8 "
          f"{int((~donem_sonu['funding_var_rev8']).sum())} | funding'li -> funding'siz {len(gecen)} "
          f"{list(zip(gecen['sembol'], gecen['donem_sira']))} | funding'siz -> funding'li {len(donen)}")
    print("\n--- Zaman toleransi ---")
    print(f"funding kaydi {int(zaman['funding_kaydi'].sum())}, tam saatten en buyuk sapma "
          f"{zaman['funding_en_buyuk_sapma_ms'].max():.0f} ms, 29 sn ustu {int(zaman['funding_29sn_ustu'].sum())} | "
          f"4h bar {int(zaman['bar_4h'].sum())}, en buyuk sapma {zaman['bar_en_buyuk_sapma_ms'].max():.0f} ms, "
          f"29 sn ustu {int(zaman['bar_29sn_ustu'].sum())}")


def main(argv: list[str] | None = None) -> None:
    ayristirici = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ayristirici.add_argument("--is-parcaci", type=int, default=4, help="es zamanli surec sayisi")
    argumanlar = ayristirici.parse_args(argv)
    with kosu_kilidi("rev8_etki", CIKTI_ORTAM.parent):
        baslangic_zamani = pd.Timestamp.now(tz="UTC")
        git = git_durumu()
        evren = universe_modulu.evren_yukle()
        sinif = universe_modulu.delist_sinifi(evren, universe_modulu.exchange_info_anlik_yukle())
        sinif_haritasi = sinif.set_index("sembol")["sinif"].to_dict()
        grup = split_modulu.split_oku().set_index("sembol")["grup"].to_dict()
        semboller = universe_modulu.dahil_semboller(evren)
        donemler = {s: universe_modulu.sembol_donemleri(evren, s) for s in semboller}
        bitisler = [d.bitis for ds in donemler.values() for d in ds]
        veri_sonu_bari = max(bitisler) if bitisler else pd.Timestamp.min.tz_localize("UTC")
        fy = evren.loc[evren["donem_id"] >= 0]
        fy = {s: dict(zip(g["donem_id"], g["donem_funding_yok"])) for s, g in fy.groupby("sembol")}
        b_satir, d_satir, z_satir = [], [], []
        with ProcessPoolExecutor(max_workers=argumanlar.is_parcaci) as havuz:
            isler = [havuz.submit(sembol_etki, s, grup[s], donemler[s], sinif_haritasi.get(s), veri_sonu_bari,
                                  fy.get(s, {})) for s in semboller if donemler[s]]
            for is_ in isler:
                b, d, z = is_.result()
                b_satir += b
                d_satir += d
                z_satir.append(z)
        baslangic = pd.DataFrame(b_satir, columns=SUTUNLAR_BASLANGIC)
        donem_sonu = pd.DataFrame(d_satir, columns=SUTUNLAR_DONEM_SONU)
        zaman = pd.DataFrame(z_satir, columns=SUTUNLAR_ZAMAN)
        csv_yaz(baslangic, CIKTI_BASLANGIC)
        csv_yaz(donem_sonu, CIKTI_DONEM_SONU)
        csv_yaz(zaman, CIKTI_ZAMAN)
        csv_yaz(ortam_kaydi(git, baslangic_zamani, pd.Timestamp.now(tz="UTC")), CIKTI_ORTAM)
        _yazdir(baslangic, donem_sonu, zaman)


if __name__ == "__main__":
    try:
        main()
    except KosuKilidiHatasi as hata:
        print(f"HATA: {hata}", file=sys.stderr)
        sys.exit(2)
