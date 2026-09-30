"""Rev.10 hazirligi: H2 pencere basi, dorduncu gevseklik maddesi, `aralik_gecerli`. YALNIZCA SAYI.

Getiri, fiyat farki ya da funding degeri HESAPLAMAZ ve raporlamaz. Mumlardan acilis zamani,
funding kayitlarindan odeme zamani ve aralik alani okunur; oran sutunu hicbir fonksiyona
verilmez (CLAUDE.md §3.1, RESULTS §14.9). Tamlik hukmu GERCEK koddan
(`funding.funding_tamlik_ayrintisi`); betikte kural kopyasi yoktur.

1. H2 funding sinyal penceresi (`rev10_h2_pencere_tam.csv`). Her donem ici 4h bar t (kumesi
   `rev8_etki.sinyal_kumesi`): pencere [bas, kapanis], kapanis = t + 4h, bas = kapanis - 24h.
   Funding serisi `funding.funding_yukle` gibi kume araligina kesilir. Iki okuma:
     - A (aday): pencere basina denk gelen kayit ortalamaya girmez, sonuna denk gelen girer:
       `sonra(z, bas)` ve `ayni_ya_da_once(z, kapanis)`.
     - B (alternatif): pencere basi da dahil: `ayni_ya_da_sonra(z, bas)`.
   Hesaplanabilirlik on-kayit §4 rev.9 "Funding sinyal penceresinin tamligi"nin capa ve zincir
   maddeleriyle, gercek pozisyon kuralinin ayni yapidaki parcasindan: giris yerine pencere basi,
   pencere sonu kapanis, capa tabani donem basi ile kume basinin gec olani, `zincir_tam`
   (son kosulu uygulanmaz). Okumanin ortalamasi, zincir tam ve kayit kumesi bos degilse
   hesaplanabilir. Oran NaN'i sayilmaz (oran okunmaz). Ritim: A kumesindeki kayitlarin araligi
   hepsi ayniysa o deger, degilse `karisik`, kume bossa `yok`.
2. Dorduncu gevseklik (`rev10_gevseklik_tam.csv`). rev9_uygulama ile ayni pozisyon evreni
   (butun donem ici barlar, birincil ufuk, gercek plan ve tamlik). Tam sayilan pozisyonda,
   capadan son kayda kadar bir cift (i, i+1) araligi degisen bir cift ise ve sonraki kayit
   "beklenen an" m'den SONRA geliyorsa (tolerans payiyla), m giristen sonra ve pencere sonunda
   ya da oncesindeyse, o ciftte kurala gorunmeyen tek eksik odeme olabilir. Iki olcu (ikisi de
   UST SINIR; aralik alani gecislerde eskimis olabildigi icin gercek eksigi ayirt etmez):
     - `kendi`: m = z_i + a_i (onceki kaydin kendi araligi),
     - `kucuk`: m = z_i + min(a_i, a_{i+1}).
   Kural (buyuk aralik) bu ciftleri eksik saymaz. Gecis turu ilk supheli ciftin a_i -> a_{i+1}'i.
3. `aralik_gecerli` (`rev10_aralik_tam.csv`): capa var ve aralik gecersiz pozisyon sayisi ve
   donem ici gecersiz aralikli kayit sayisi.

Kullanim:
    python analysis/00_veri_denetimi/rev10_hazirlik.py --is-parcaci 8
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

P = pencere_modulu
F = funding_modulu
TOL = P.ZAMAN_TOLERANSI
PENCERE = pd.Timedelta(hours=24)
CIKTI = {ad: BU_DIZIN / f"rev10_{ad}_tam.csv" for ad in ("h2_pencere", "gevseklik", "aralik", "ortam")}


def _etiket(a: float) -> str:
    return "yok" if not np.isfinite(a) else (str(int(a)) if float(a).is_integer() else str(a))


# --- 1. H2 pencere basi -----------------------------------------------------------------------


def h2_pencere_sayimi(t_ler, seri: pd.DataFrame, taban) -> pd.DataFrame:
    """Barlar icin iki okumanin kayit sayisi, ritim ve zincir tamligi. Saf; zaman ve aralik."""
    t = pd.DatetimeIndex(t_ler)
    kapanis = t + P.ADIMLAR[config.BAR_4H]
    bas = kapanis - PENCERE
    n = len(t)
    sonuc = pd.DataFrame({"kayit_A": np.zeros(n, dtype=int), "kayit_B": np.zeros(n, dtype=int),
                          "ritim": ["yok"] * n, "zincir_tam": np.zeros(n, dtype=bool)})
    if n == 0 or seri.empty:
        return sonuc
    z = F._zaman_dizisi(seri, "h2_pencere_sayimi")
    aralik = pd.to_numeric(seri["aralik_saat"], errors="coerce").to_numpy(dtype=float)
    hi = z.searchsorted(kapanis + TOL, side="left")             # ayni_ya_da_once(z, kapanis)
    lo_a = z.searchsorted(bas + TOL, side="left")                # sonra(z, bas)
    lo_b = z.searchsorted(bas - TOL, side="right")               # ayni_ya_da_sonra(z, bas)
    sonuc["kayit_A"] = hi - lo_a
    sonuc["kayit_B"] = hi - lo_b
    degisim = np.r_[0, np.cumsum(aralik[1:] != aralik[:-1])] if len(aralik) > 1 else np.zeros(1, dtype=int)
    bos = hi <= lo_a
    ilk = np.minimum(lo_a, len(z) - 1)
    son = np.maximum(hi - 1, 0)
    tek = ~bos & ((degisim[son] - degisim[ilk]) == 0)
    sonuc["ritim"] = np.where(bos, "yok", np.where(tek, [_etiket(aralik[i]) for i in ilk], "karisik"))
    gercek = F.funding_tamlik_ayrintisi(seri, bas, kapanis, donem_baslari=[taban] * n)
    sonuc["zincir_tam"] = gercek["zincir_tam"].to_numpy(dtype=bool)
    return sonuc


def h2_satirlari(sembol: str, grup: str, donemler, mumlar: pd.DataFrame, seri: pd.DataFrame, kumeler) -> list[dict]:
    zamanlar = pd.DatetimeIndex(mumlar["open_time"])
    satirlar = []
    for d in donemler:
        zd = zamanlar[np.asarray(P.donem_ici_4h_maskesi(zamanlar, donem_baslangic=d.baslangic,
                                                        donem_bitis=d.bitis), dtype=bool)]
        kume_dizi = np.array([sinyal_kumesi(t, grup, kumeler) for t in zd], dtype=object)
        for kume in sorted({k for k in kume_dizi if k is not None}):
            _, k_bas, k_son = kumeler[kume]
            t_k = zd[kume_dizi == kume]
            # funding_yukle ile ayni kume kesimi (funding.py: odeme_zamani >= bas ve <= son).
            s_k = seri.loc[(seri["odeme_zamani"] >= k_bas) & (seri["odeme_zamani"] <= k_son)].reset_index(drop=True)
            tablo = h2_pencere_sayimi(t_k, s_k, max(d.baslangic, pd.Timestamp(k_bas)))
            kapanis_disari = (t_k + P.ADIMLAR[config.BAR_4H]) > k_son
            tablo["kapanis_kume_disinda"] = np.asarray(kapanis_disari, dtype=bool)
            sayim = tablo.groupby(["ritim", "kayit_A", "kayit_B", "zincir_tam", "kapanis_kume_disinda"]).size()
            for (ritim, ka, kb, zt, kd), adet in sayim.items():
                satirlar.append({"sembol": sembol, "kume": kume, "ritim": ritim, "kayit_A": int(ka), "kayit_B": int(kb),
                                 "zincir_tam": bool(zt), "kapanis_kume_disinda": bool(kd), "bar": int(adet)})
    return satirlar


# --- 2. Dorduncu gevseklik ve 3. aralik_gecerli -----------------------------------------------------


def gevseklik_ayrintisi(seri: pd.DataFrame, planlar, gercek: pd.DataFrame) -> pd.DataFrame:
    """Tam pozisyonlarda, aralik gecisine bitisik ve kuralin gormedigi supheli cift (iki olcu).
    Saf; zaman ve aralik. Doner: `kendi`, `kucuk` (bool) ve ilk supheli ciftin gecis turu."""
    n = len(planlar)
    sonuc = pd.DataFrame({"kendi": np.zeros(n, dtype=bool), "kucuk": np.zeros(n, dtype=bool),
                          "gecis_kendi": [None] * n, "gecis_kucuk": [None] * n})
    tam = gercek["tam"].to_numpy(dtype=bool)
    if n == 0 or seri.empty or not tam.any():
        return sonuc
    z = F._zaman_dizisi(seri, "gevseklik_ayrintisi")
    a = pd.to_numeric(seri["aralik_saat"], errors="coerce").to_numpy(dtype=float)
    if len(z) < 2:
        return sonuc
    gecis = a[1:] != a[:-1]
    girisler = pd.DatetimeIndex([p.giris for p in planlar])
    ilk = z.get_indexer(pd.DatetimeIndex(gercek["capa_zamani"]))
    son = z.get_indexer(pd.DatetimeIndex(gercek["son_kayit_zamani"]))
    for olcu, adim in (("kendi", a[:-1]), ("kucuk", np.minimum(a[:-1], a[1:]))):
        m = z[:-1] + pd.to_timedelta(adim, unit="h")
        supheli = gecis & np.asarray(P.sonra(z[1:], m), dtype=bool)
        idx = np.flatnonzero(supheli)
        for i in np.flatnonzero(tam):
            aday = idx[(idx >= ilk[i]) & (idx < son[i])]
            if len(aday) and aday[0] == ilk[i] and not P.sonra(m[aday[0]], girisler[i]):
                aday = aday[1:]  # ilk ciftte beklenen an giriste ya da once: pozisyonu ilgilendirmez
            if len(aday):
                j = int(aday[0])
                sonuc.at[i, olcu] = True
                sonuc.at[i, f"gecis_{olcu}"] = f"{_etiket(a[j])}->{_etiket(a[j + 1])}"
    return sonuc


def pozisyon_satirlari(sembol: str, grup: str, donemler, mumlar: pd.DataFrame, seri: pd.DataFrame,
                       kumeler) -> tuple[list[dict], list[dict]]:
    gev, ara = [], []
    for bar in sorted(set(config.HIPOTEZ_IZGARASI.values())):
        planlar, plan_kumeleri = _planlar(donemler, mumlar, grup, kumeler, bar)
        if not planlar:
            continue
        g = _ayrinti(seri, planlar)
        s = gevseklik_ayrintisi(seri, planlar, g)
        tablo = pd.concat([g[["capa_var", "aralik_gecerli", "zincir_tam", "son_tam", "tam"]], s], axis=1)
        tablo["kume"] = plan_kumeleri
        for kume, t_ in tablo.groupby("kume", sort=True):
            ara.append({"sembol": sembol, "bar": bar, "kume": kume, "plan": len(t_), "tam": int(t_["tam"].sum()),
                        "capa_var": int(t_["capa_var"].sum()),
                        "aralik_gecersiz": int((t_["capa_var"] & ~t_["aralik_gecerli"]).sum())})
            for olcu in ("kendi", "kucuk"):
                for gec, adet in t_.loc[t_[olcu], f"gecis_{olcu}"].value_counts().items():
                    gev.append({"sembol": sembol, "bar": bar, "kume": kume, "olcu": olcu, "gecis": gec,
                                "pozisyon": int(adet)})
    return gev, ara


def sembol_olc(sembol: str, grup: str, donemler):
    mumlar = donem_modulu.toplam_doneme_kes(klines_modulu.ham_mumlari_yukle(sembol, config.BAR_4H), "open_time")
    fund = donem_modulu.toplam_doneme_kes(funding_modulu.ham_funding_yukle(sembol), "odeme_zamani")
    seri = funding_modulu.donem_sonrasi_kayitlari_at(fund, donemler, config.BAR_4H) if len(fund) else fund
    if seri.empty:
        seri = _bos_seri()
    seri = seri.loc[:, ["odeme_zamani", "aralik_saat"]].reset_index(drop=True)  # oran okunmaz
    kumeler = kume_sinirlari()
    a = pd.to_numeric(seri["aralik_saat"], errors="coerce").to_numpy(dtype=float)
    z = pd.DatetimeIndex(seri["odeme_zamani"])
    ici = np.zeros(len(z), dtype=bool)
    for d in donemler:
        ici |= (np.asarray(P.ayni_ya_da_sonra(z, d.baslangic), dtype=bool)
                & np.asarray(P.ayni_ya_da_once(z, d.bitis), dtype=bool))
    kayit = {"sembol": sembol, "donem_ici_kayit": int(ici.sum()),
             "donem_ici_gecersiz_aralik": int((ici & ~(np.isfinite(a) & (a > 0))).sum())}
    h2 = h2_satirlari(sembol, grup, donemler, mumlar, seri, kumeler)
    gev, ara = pozisyon_satirlari(sembol, grup, donemler, mumlar, seri, kumeler)
    for r in ara:
        r.update(kayit)
    return h2, gev, ara


def main(argv: list[str] | None = None) -> None:
    ayristirici = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ayristirici.add_argument("--is-parcaci", type=int, default=4)
    ayristirici.add_argument("--semboller", nargs="*", default=None)
    ayristirici.add_argument("--cikti-dizini", type=Path, default=BU_DIZIN)
    argumanlar = ayristirici.parse_args(argv)
    with kosu_kilidi("rev10_hazirlik", CIKTI["ortam"].parent):
        baslangic_zamani = pd.Timestamp.now(tz="UTC")
        git = git_durumu()
        evren = universe_modulu.evren_yukle()
        grup = split_modulu.split_oku().set_index("sembol")["grup"].to_dict()
        semboller = universe_modulu.dahil_semboller(evren)
        donemler = {s: universe_modulu.sembol_donemleri(evren, s) for s in semboller}
        secilen = [s for s in semboller if donemler[s] and (argumanlar.semboller is None or s in argumanlar.semboller)]
        h_s, g_s, a_s = [], [], []
        with ProcessPoolExecutor(max_workers=argumanlar.is_parcaci) as havuz:
            isler = [havuz.submit(sembol_olc, s, grup[s], donemler[s]) for s in secilen]
            for is_ in isler:
                h, g, a = is_.result()
                h_s += h
                g_s += g
                a_s += a
        cikti = argumanlar.cikti_dizini
        csv_yaz(pd.DataFrame(h_s), cikti / CIKTI["h2_pencere"].name)
        csv_yaz(pd.DataFrame(g_s, columns=["sembol", "bar", "kume", "olcu", "gecis", "pozisyon"]),
                cikti / CIKTI["gevseklik"].name)
        csv_yaz(pd.DataFrame(a_s), cikti / CIKTI["aralik"].name)
        csv_yaz(ortam_kaydi(git, baslangic_zamani, pd.Timestamp.now(tz="UTC")), cikti / CIKTI["ortam"].name)
        print(f"sembol {len(secilen)} | h2 {len(h_s)} | gevseklik {len(g_s)} | aralik {len(a_s)} -> {cikti}")


if __name__ == "__main__":
    try:
        # F1 veri denetimi butun gecmisi olcer (anayasa §3.1): onay verisi izniyle (kapanisin son turu).
        from data import binance_vision as _bv

        with _bv.onay_verisi_izni("F1 veri denetimi: " + Path(__file__).name):
            main()
    except KosuKilidiHatasi as hata:
        print(f"HATA: {hata}", file=sys.stderr)
        sys.exit(2)
