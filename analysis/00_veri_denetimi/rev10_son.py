"""Rev.10 hazirligi, son tur: YALNIZCA KESIF kumesi, YALNIZCA SAYI.

Getiri, fiyat farki, funding degeri ya da H2 ortalamasinin degeri HESAPLANMAZ. Mumlardan acilis
zamani, funding kayitlarindan odeme zamani ve aralik alani okunur; oran sutunu hicbir fonksiyona
verilmez. Yalnizca KESIF grubu (A) sembolleri ve KESIF tarih araligi okunur; C1/C2 hic hesaplanmaz.

1. H2 penceresinin kume icinde olmasi (`rev10_son_h2_tam.csv`). KESIF'teki her donem ici 4h bar t:
   pencere [kapanis - 24h, kapanis], kapanis = t + 4h. Sayilanlar: pencere basi kume basindan
   once (ham ve tolerans karsilastirmasiyla), kapanis kume sonundan sonra (ham ve tolerans), ve
   bu barlarin Rev.9 capa + zincir hesaplanabilirligi (gercek tamlik kodu; kume kesimli seri).
2. Dorduncu gevseklik, uc olcu ve iki seri (`rev10_son_gevseklik_tam.csv`, `rev10_son_tam_tam.csv`):
   rev10_hazirlik ile ayni pozisyon evreni ama yalnizca KESIF. Olculer:
     - `kendi`  : ilk supheli cift, m = z_i + a_i (rev10_hazirlik ile ayni),
     - `kucuk`  : m = z_i + min(a_i, a_{i+1}), ilk ciftte m girisin ardinda degilse atlanir
                  (rev10_hazirlik ile ayni),
     - `kucuk_giris`: aralik degisen her cift, taban ilk ciftte max(z_i, giris), sonrakilerde z_i;
                  sonraki kayit taban + min(a_i, a_{i+1}) + toleranstan SONRA ise supheli.
   Seri: `kesiksiz` (rev10_hazirlik ile ayni: toplam doneme kesilmis) ve `kesik` (ayrica
   `funding.funding_yukle` gibi KESIF araligina ham karsilastirmayla kesilmis).

Kullanim:
    python analysis/00_veri_denetimi/rev10_son.py --is-parcaci 8
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
from rev9_uygulama import _ayrinti, _bos_seri, _planlar  # noqa: E402
from rev10_hazirlik import _etiket  # noqa: E402

P = pencere_modulu
F = funding_modulu
KUME = "KESIF"
PENCERE = pd.Timedelta(hours=24)
CIKTI = {ad: BU_DIZIN / f"rev10_son_{ad}_tam.csv" for ad in ("h2", "gevseklik", "tam", "ortam")}
OLCULER = ("kendi", "kucuk", "kucuk_giris")


def kume_kes(seri: pd.DataFrame, bas, son) -> pd.DataFrame:
    """`funding.funding_yukle` ile ayni kesim (ham karsilastirma). Saf."""
    return seri.loc[(seri["odeme_zamani"] >= bas) & (seri["odeme_zamani"] <= son)].reset_index(drop=True)


# --- 1. H2 penceresi kume icinde mi ------------------------------------------------------------


def h2_kume_sayimi(t_ler, seri_kesik: pd.DataFrame, taban, k_bas, k_son) -> dict:
    t = pd.DatetimeIndex(t_ler)
    kapanis = t + P.ADIMLAR[config.BAR_4H]
    bas = kapanis - PENCERE
    n = len(t)
    bas_ham = np.asarray(bas < k_bas, dtype=bool)
    bas_tol = np.asarray(P.once(bas, k_bas), dtype=bool)
    son_ham = np.asarray(kapanis > k_son, dtype=bool)
    son_tol = np.asarray(P.sonra(kapanis, k_son), dtype=bool)
    if n and not seri_kesik.empty:
        hesap = F.funding_tamlik_ayrintisi(seri_kesik, bas, kapanis, donem_baslari=[taban] * n)["zincir_tam"].to_numpy()
    else:
        hesap = np.zeros(n, dtype=bool)
    return {"bar": n, "hesaplanabilir": int(hesap.sum()),
            "bas_kume_oncesi_ham": int(bas_ham.sum()), "bas_kume_oncesi_tol": int(bas_tol.sum()),
            "kapanis_kume_sonrasi_ham": int(son_ham.sum()), "kapanis_kume_sonrasi_tol": int(son_tol.sum()),
            "hesaplanabilir_ve_kapanis_sonrasi_ham": int((hesap & son_ham).sum()),
            "hesaplanabilir_ve_bas_oncesi_ham": int((hesap & bas_ham).sum())}


# --- 2. Gevseklik, uc olcu ----------------------------------------------------------------------


def gevseklik_uc_olcu(seri: pd.DataFrame, girisler, gercek: pd.DataFrame) -> pd.DataFrame:
    """Tam pozisyonlarda uc olcunun supheli cifti ve gecis turu. Saf; zaman ve aralik."""
    n = len(gercek)
    sonuc = pd.DataFrame({**{o: np.zeros(n, dtype=bool) for o in OLCULER},
                          **{f"gecis_{o}": [None] * n for o in OLCULER}})
    tam = gercek["tam"].to_numpy(dtype=bool)
    if n == 0 or seri.empty or not tam.any() or len(seri) < 2:
        return sonuc
    z = F._zaman_dizisi(seri, "gevseklik_uc_olcu")
    a = pd.to_numeric(seri["aralik_saat"], errors="coerce").to_numpy(dtype=float)
    girisler = pd.DatetimeIndex(girisler)
    gecis = a[1:] != a[:-1]
    kucuk = np.minimum(a[:-1], a[1:])
    ilk = z.get_indexer(pd.DatetimeIndex(gercek["capa_zamani"]))
    son = z.get_indexer(pd.DatetimeIndex(gercek["son_kayit_zamani"]))
    m_kendi = z[:-1] + pd.to_timedelta(a[:-1], unit="h")
    m_kucuk = z[:-1] + pd.to_timedelta(kucuk, unit="h")
    sup_kendi = gecis & np.asarray(P.sonra(z[1:], m_kendi), dtype=bool)
    sup_kucuk = gecis & np.asarray(P.sonra(z[1:], m_kucuk), dtype=bool)
    idx_kendi, idx_kucuk, idx_gecis = np.flatnonzero(sup_kendi), np.flatnonzero(sup_kucuk), np.flatnonzero(gecis)

    def _yaz(i, olcu, j):
        sonuc.at[i, olcu] = True
        sonuc.at[i, f"gecis_{olcu}"] = f"{_etiket(a[j])}->{_etiket(a[j + 1])}"

    for i in np.flatnonzero(tam):
        lo, hi = ilk[i], son[i]
        for olcu, idx, m in (("kendi", idx_kendi, m_kendi), ("kucuk", idx_kucuk, m_kucuk)):
            aday = idx[(idx >= lo) & (idx < hi)]
            if len(aday) and aday[0] == lo and not P.sonra(m[aday[0]], girisler[i]):
                aday = aday[1:]
            if len(aday):
                _yaz(i, olcu, int(aday[0]))
        # kucuk_giris: ilk ciftte taban max(capa, giris); sonrakiler z_i (girisin ardinda).
        aday = idx_gecis[(idx_gecis >= lo) & (idx_gecis < hi)]
        for j in aday:
            taban = max(z[j], girisler[i]) if j == lo else z[j]
            if P.sonra(z[j + 1], taban + pd.Timedelta(hours=float(kucuk[j]))):
                _yaz(i, "kucuk_giris", int(j))
                break
    return sonuc


def pozisyon_satirlari(sembol, grup, donemler, mumlar, seri, kumeler, seri_adi):
    gev, tam_s = [], []
    for bar in sorted(set(config.HIPOTEZ_IZGARASI.values())):
        planlar, plan_kumeleri = _planlar(donemler, mumlar, grup, kumeler, bar)
        planlar = [p for p, k in zip(planlar, plan_kumeleri) if k == KUME]
        if not planlar:
            continue
        g = _ayrinti(seri, planlar)
        s = gevseklik_uc_olcu(seri, [p.giris for p in planlar], g)
        tam_s.append({"sembol": sembol, "bar": bar, "seri": seri_adi, "plan": len(planlar), "tam": int(g["tam"].sum())})
        for olcu in OLCULER:
            for gec, adet in s.loc[s[olcu], f"gecis_{olcu}"].value_counts().items():
                gev.append({"sembol": sembol, "bar": bar, "seri": seri_adi, "olcu": olcu, "gecis": gec,
                            "pozisyon": int(adet)})
    return gev, tam_s


def sembol_olc(sembol: str, grup: str, donemler):
    kumeler = {KUME: kume_sinirlari()[KUME]}
    _, k_bas, k_son = kumeler[KUME]
    mumlar = donem_modulu.toplam_doneme_kes(klines_modulu.ham_mumlari_yukle(sembol, config.BAR_4H), "open_time")
    fund = donem_modulu.toplam_doneme_kes(funding_modulu.ham_funding_yukle(sembol), "odeme_zamani")
    seri = funding_modulu.donem_sonrasi_kayitlari_at(fund, donemler, config.BAR_4H) if len(fund) else fund
    if seri.empty:
        seri = _bos_seri()
    seri = seri.loc[:, ["odeme_zamani", "aralik_saat"]].reset_index(drop=True)  # oran okunmaz
    kesik = kume_kes(seri, k_bas, k_son)
    # 1. H2
    zamanlar = pd.DatetimeIndex(mumlar["open_time"])
    h2 = []
    for d in donemler:
        zd = zamanlar[np.asarray(P.donem_ici_4h_maskesi(zamanlar, donem_baslangic=d.baslangic,
                                                        donem_bitis=d.bitis), dtype=bool)]
        t_k = zd[np.array([sinyal_kumesi(t, grup, kumeler) == KUME for t in zd], dtype=bool)]
        if len(t_k):
            h2.append({"sembol": sembol, **h2_kume_sayimi(t_k, kesik, max(d.baslangic, pd.Timestamp(k_bas)), k_bas, k_son)})
    # 2. Gevseklik, iki seri
    gev, tam_s = [], []
    for ad, s in (("kesiksiz", seri), ("kesik", kesik)):
        g, t = pozisyon_satirlari(sembol, grup, donemler, mumlar, s, kumeler, ad)
        gev += g
        tam_s += t
    return h2, gev, tam_s


def main(argv: list[str] | None = None) -> None:
    ayristirici = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ayristirici.add_argument("--is-parcaci", type=int, default=4)
    ayristirici.add_argument("--semboller", nargs="*", default=None)
    ayristirici.add_argument("--cikti-dizini", type=Path, default=BU_DIZIN)
    argumanlar = ayristirici.parse_args(argv)
    with kosu_kilidi("rev10_son", CIKTI["ortam"].parent):
        baslangic_zamani = pd.Timestamp.now(tz="UTC")
        git = git_durumu()
        evren = universe_modulu.evren_yukle()
        grup = split_modulu.split_oku().set_index("sembol")["grup"].to_dict()
        gruplar = split_modulu.kume_tanimi(KUME)[0]
        semboller = [s for s in universe_modulu.dahil_semboller(evren) if grup.get(s) in gruplar]
        donemler = {s: universe_modulu.sembol_donemleri(evren, s) for s in semboller}
        secilen = [s for s in semboller if donemler[s] and (argumanlar.semboller is None or s in argumanlar.semboller)]
        h_s, g_s, t_s = [], [], []
        with ProcessPoolExecutor(max_workers=argumanlar.is_parcaci) as havuz:
            for is_ in [havuz.submit(sembol_olc, s, grup[s], donemler[s]) for s in secilen]:
                h, g, t = is_.result()
                h_s += h
                g_s += g
                t_s += t
        cikti = argumanlar.cikti_dizini
        csv_yaz(pd.DataFrame(h_s), cikti / CIKTI["h2"].name)
        csv_yaz(pd.DataFrame(g_s, columns=["sembol", "bar", "seri", "olcu", "gecis", "pozisyon"]),
                cikti / CIKTI["gevseklik"].name)
        csv_yaz(pd.DataFrame(t_s), cikti / CIKTI["tam"].name)
        csv_yaz(ortam_kaydi(git, baslangic_zamani, pd.Timestamp.now(tz="UTC")), cikti / CIKTI["ortam"].name)
        print(f"KESIF sembol {len(secilen)} | h2 {len(h_s)} | gevseklik {len(g_s)} | tam {len(t_s)} -> {cikti}")


if __name__ == "__main__":
    try:
        main()
    except KosuKilidiHatasi as hata:
        print(f"HATA: {hata}", file=sys.stderr)
        sys.exit(2)
