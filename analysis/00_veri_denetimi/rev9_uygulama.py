"""Rev.9 uygulamasi dogrulamasi: on-kayit Rev.9 metnindeki sayilar GERCEK kod yoluyla. YALNIZCA SAYI.

Rev.9'un "Funding tamliginin bilinen sinirlari" bolumu olcum betiginin (`rev9_hazirlik.py`
`capa_duzeltme_tamlik_ayrintisi`, `rev9_ritim.py`) sayilariyla yazildi. Bu betik ayni pozisyon
evrenini veri katmaninin kendisiyle yeniden uretir ve olcum betiginin ciktilariyla satir satir
karsilastirir:
  - plan: `pencere.pozisyon_plani` (Rev.9: T >= K donem sonu),
  - pencere sonu: `funding.funding_penceresi_sonu`,
  - tamlik ve bayraklar: `funding.funding_tamlik_ayrintisi` / `funding.pozisyon_funding_ayrintisi`.
Olcum betiginden yalnizca kural disi yardimcilar alinir: kume sinirlari (`rev8_etki`), donem sonu
turleri (`calistir`), temsili plan (`a1_olcumu`), 2026-06-24 karsi-olgusal serisi
(`rev9_hazirlik.bosluk_seri`).

Getiri, fiyat farki ya da funding degeri HESAPLAMAZ ve raporlamaz. Mumlardan acilis zamani ve
(donem sonu turu icin) hacmin sifir olup olmadigi, funding kayitlarindan odeme zamani ve aralik
alani okunur (CLAUDE.md §3.1, RESULTS §14.9). Funding serisi olcum betigiyle ayni tabandir:
toplam doneme kesilmis, donem kapanisindan sonrasi atilmis ham seri (kume kesimi yok).

Ciktilar (`rev9_uygulama_*_tam.csv`):
1. `baslangic`: butun donem ici barlar (1d'de gunler) varsayimsal sinyal, birincil ufuk; sembol x
   izgara x kume: plan, tam, capa yok, zincir bozuk, son bozuk, kismi kuyruk, esitlik affi,
   2026-06-24 boslugu nedeniyle eksik.
2. `ritim`: ayni evren; sembol x izgara x kume x giris yili x capa araligi x son aralik x tek ritim.
3. `donem_sonu`: temsili pozisyon (A1 ile ayni) her donem sonu ve izgarada.
4. `tk`: her donem, izgara ve ufukta T = K olan tek sinyal.
5. `karsilastirma`: olcum betiginin ciktilariyla yan yana toplamlar ve satir farklari.

Kullanim:
    python analysis/00_veri_denetimi/rev9_uygulama.py --is-parcaci 8
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
from a1_olcumu import temsili_plan  # noqa: E402
from calistir import KosuKilidiHatasi, csv_yaz, donem_sonu_turleri, git_durumu, kosu_kilidi, ortam_kaydi  # noqa: E402
from data import donem as donem_modulu  # noqa: E402
from data import funding as funding_modulu  # noqa: E402
from data import klines as klines_modulu  # noqa: E402
from data import pencere as pencere_modulu  # noqa: E402
from data import split as split_modulu  # noqa: E402
from data import universe as universe_modulu  # noqa: E402
from rev8_etki import kume_sinirlari, sinyal_kumesi  # noqa: E402
from rev9_hazirlik import UFUKLAR, bosluk_seri  # noqa: E402

P = pencere_modulu
F = funding_modulu
CIKTI = {ad: BU_DIZIN / f"rev9_uygulama_{ad}_tam.csv"
         for ad in ("baslangic", "ritim", "donem_sonu", "tk", "karsilastirma", "ortam")}


def _bos_seri() -> pd.DataFrame:
    return pd.DataFrame({"odeme_zamani": pd.DatetimeIndex([], tz="UTC"), "aralik_saat": np.empty(0)})


def _planlar(donemler, mumlar: pd.DataFrame, grup: str, kumeler, bar: str):
    """Butun donem ici barlar (1d'de donem ici tam gunler) varsayimsal sinyal, birincil ufuk;
    gercek plan. Doner: planlar ve kumeleri."""
    zamanlar = pd.DatetimeIndex(mumlar["open_time"])
    ufuk = config.BIRINCIL_UFUK[bar]
    planlar, plan_kumeleri = [], []
    for d in donemler:
        zd = zamanlar[np.asarray(P.donem_ici_4h_maskesi(zamanlar, donem_baslangic=d.baslangic,
                                                        donem_bitis=d.bitis), dtype=bool)]
        if bar == config.BAR_1D:
            sinyaller = pd.DatetimeIndex(klines_modulu.gunluge_cevir(mumlar, donemler=[d])["open_time"])
        else:
            sinyaller = zd
        for t in sinyaller:
            kume = sinyal_kumesi(t, grup, kumeler)
            if kume is None:
                continue
            try:
                plan = P.pozisyon_plani(zd, t, ufuk, bar, birincil_ufuk=ufuk, kume_baslangic=kumeler[kume][1],
                                        kume_bitis=kumeler[kume][2], donem_baslangic=d.baslangic,
                                        donem_bitis=d.bitis)
            except P.OlayOlusmaz:
                continue
            planlar.append(plan)
            plan_kumeleri.append(kume)
    return planlar, plan_kumeleri


def _ayrinti(seri: pd.DataFrame, planlar) -> pd.DataFrame:
    """Gercek tamlik, planlarin kendi pencere sonu ve donem basiyla (vektorel tek cagri)."""
    return F.funding_tamlik_ayrintisi(seri, [p.giris for p in planlar], [F.funding_penceresi_sonu(p) for p in planlar],
                                      donem_baslari=[p.donem_baslangic for p in planlar])


def baslangic_ve_ritim(sembol: str, grup: str, donemler, mumlar: pd.DataFrame, seri: pd.DataFrame,
                       seri_cf: pd.DataFrame | None, kumeler) -> tuple[list[dict], list[dict]]:
    satirlar, ritim = [], []
    for bar in sorted(set(config.HIPOTEZ_IZGARASI.values())):
        planlar, plan_kumeleri = _planlar(donemler, mumlar, grup, kumeler, bar)
        if not planlar:
            continue
        a = _ayrinti(seri, planlar)
        tam = a["tam"].to_numpy()
        cf_etki = (_ayrinti(seri_cf, planlar)["tam"].to_numpy() & ~tam) if seri_cf is not None \
            else np.zeros(len(planlar), dtype=bool)
        tablo = a.assign(kume=plan_kumeleri, yil=pd.DatetimeIndex([p.giris for p in planlar]).year,
                         bosluk_etkisi=cf_etki)
        for kume, g in tablo.groupby("kume", sort=True):
            satirlar.append({
                "sembol": sembol, "bar": bar, "kume": kume, "plan": len(g), "tam": int(g["tam"].sum()),
                "capa_yok": int((~g["capa_var"]).sum()),
                "zincir_bozuk": int((g["capa_var"] & ~g["zincir_tam"]).sum()),
                "son_bozuk": int((g["capa_var"] & g["zincir_tam"] & ~g["son_tam"]).sum()),
                "kuyruk_kismi": int(g["kuyruk_kismi"].sum()), "kuyruk_sifir": int(g["kuyruk_sifir"].sum()),
                "son_esitlik_affi": int(g["son_esitlik_affi"].sum()),
                "bosluk_etkisi": int(g["bosluk_etkisi"].sum()),
            })
        sayim = tablo.groupby(["kume", "yil", "capa_aralik_saat", "son_aralik_saat", "tek_ritim"], dropna=False).agg(
            plan=("tam", "size"), tam=("tam", "sum"), kuyruk_kismi=("kuyruk_kismi", "sum"),
            son_esitlik_affi=("son_esitlik_affi", "sum")).reset_index()
        sayim = sayim.rename(columns={"capa_aralik_saat": "capa_aralik", "son_aralik_saat": "son_aralik"})
        sayim.insert(0, "bar", bar)
        sayim.insert(0, "sembol", sembol)
        ritim += sayim.to_dict("records")
    return satirlar, ritim


def donem_sonu_satirlari(sembol: str, donemler, turler, seri: pd.DataFrame) -> list[dict]:
    """Temsili pozisyon (A1 ile ayni), gercek plan ve gercek tamlik."""
    satirlar = []
    for bar in (config.BAR_4H, config.BAR_1D):
        for i, (d, tur) in enumerate(zip(donemler, turler)):
            satir = {"sembol": sembol, "bar": bar, "donem_sira": i, "tur": tur, "ret_gerekcesi": None,
                     "cikis_turu": None, **{k: False for k in (*F.TAMLIK_KOSULLARI, "tam")}}
            try:
                plan = temsili_plan(d, bar)
            except P.OlayOlusmaz as hata:
                satir["ret_gerekcesi"] = P.ret_gerekcesi(hata)
            except P.DonemDisiSinyal:
                satir["ret_gerekcesi"] = "donem_disi_sinyal"
            else:
                a = F.pozisyon_funding_ayrintisi(seri, plan)
                satir.update(cikis_turu=plan.cikis_turu, **{k: bool(a[k]) for k in (*F.TAMLIK_KOSULLARI, "tam")})
            satirlar.append(satir)
    return satirlar


def tk_satirlari(sembol: str, grup: str, donemler, turler, mumlar: pd.DataFrame, seri: pd.DataFrame,
                 kumeler) -> list[dict]:
    """Her donem, izgara ve ufukta T = K olan tek sinyal; gercek plan (donem sonu olmali)."""
    zamanlar = pd.DatetimeIndex(mumlar["open_time"])
    satirlar = []
    for i, (d, tur) in enumerate(zip(donemler, turler)):
        zd = zamanlar[np.asarray(P.donem_ici_4h_maskesi(zamanlar, donem_baslangic=d.baslangic,
                                                        donem_bitis=d.bitis), dtype=bool)]
        k = d.kapanis
        gunler = None
        for bar, ufuklar in UFUKLAR.items():
            adim = P.adim(bar)
            for ufuk in ufuklar:
                t = k - ufuk * adim - adim
                satir = {"sembol": sembol, "donem_sira": i, "tur": tur, "bar": bar, "ufuk": ufuk, "kume": None,
                         "durum": None, "cikis_turu": None, "tam": False}
                if bar == config.BAR_1D:
                    if t != t.floor("D"):
                        satirlar.append({**satir, "durum": "1d_sinyal_gunu_yok"})
                        continue
                    if gunler is None:
                        gunler = pd.DatetimeIndex(klines_modulu.gunluge_cevir(mumlar, donemler=[d])["open_time"])
                    sinyal_var = P.ayni_andaki_bar(gunler, t) is not None
                else:
                    sinyal_var = P.ayni_andaki_bar(zd, t) is not None
                if not sinyal_var:
                    satirlar.append({**satir, "durum": "sinyal_bari_yok"})
                    continue
                kume = sinyal_kumesi(t, grup, kumeler)
                satir["kume"] = kume
                if kume is None:
                    satirlar.append({**satir, "durum": "kume_yok"})
                    continue
                try:
                    plan = P.pozisyon_plani(zd, t, ufuk, bar, birincil_ufuk=config.BIRINCIL_UFUK[bar],
                                            kume_baslangic=kumeler[kume][1], kume_bitis=kumeler[kume][2],
                                            donem_baslangic=d.baslangic, donem_bitis=d.bitis)
                except P.OlayOlusmaz as hata:
                    satirlar.append({**satir, "durum": f"ret_{P.ret_gerekcesi(hata)}"})
                    continue
                if not (P.ayni_an(plan.cikis.hedef_cikis_ani, k) and P.ayni_an(plan.cikis_ani, k)):
                    satirlar.append({**satir, "durum": f"beklenmeyen_{plan.cikis_turu}"})
                    continue
                a = F.pozisyon_funding_ayrintisi(seri, plan)
                satirlar.append({**satir, "durum": "t_esit_k", "cikis_turu": plan.cikis_turu, "tam": bool(a["tam"]),
                                 "pencere_sonu_b": F.funding_penceresi_sonu(plan) == d.bitis})
    return satirlar


def sembol_olc(sembol: str, grup: str, donemler, sinif: str | None, veri_sonu_bari: pd.Timestamp):
    """Bir sembolun olcumleri (rev9_hazirlik.sembol_olc ile ayni girdiler). Ayri surecte."""
    mumlar = donem_modulu.toplam_doneme_kes(klines_modulu.ham_mumlari_yukle(sembol, config.BAR_4H), "open_time")
    fund = donem_modulu.toplam_doneme_kes(funding_modulu.ham_funding_yukle(sembol), "odeme_zamani")
    seri = funding_modulu.donem_sonrasi_kayitlari_at(fund, donemler, config.BAR_4H) if len(fund) else fund
    if seri.empty:
        seri = _bos_seri()
    # Oran sutunlari hicbir fonksiyona verilmez (yalnizca zaman ve aralik).
    seri = seri.loc[:, ["odeme_zamani", "aralik_saat"]].reset_index(drop=True)
    mz = pd.DatetimeIndex(mumlar["open_time"])
    hacim = mumlar["quote_volume"] if len(donemler) > 1 else None
    turler = donem_sonu_turleri(donemler, sinif, veri_sonu_bari, mz if len(donemler) > 1 else None, hacim)
    kumeler = kume_sinirlari()
    seri_cf, eklendi = bosluk_seri(seri, donemler)
    bs, rt = baslangic_ve_ritim(sembol, grup, donemler, mumlar, seri, seri_cf if eklendi else None, kumeler)
    ds = donem_sonu_satirlari(sembol, donemler, turler, seri)
    tk = tk_satirlari(sembol, grup, donemler, turler, mumlar, seri, kumeler)
    return bs, rt, ds, tk


# --- Olcum betigiyle karsilastirma -------------------------------------------------------------


def _satir_farki(yeni: pd.DataFrame, eski: pd.DataFrame, anahtar: list[str], esler: dict[str, str]) -> int:
    """Anahtarla eslesen satirlarda sutun ciftlerinden en az biri farkli olan (ya da tek tarafta
    olan) satir sayisi."""
    sol = yeni[anahtar + list(esler)].copy()
    sag = eski[anahtar + list(esler.values())].rename(columns={v: k for k, v in esler.items()})
    for df in (sol, sag):
        for s in anahtar:
            df[s] = df[s].astype(str)
    birlesik = sol.merge(sag, on=anahtar, how="outer", suffixes=("_y", "_e"), indicator=True)
    fark = birlesik["_merge"] != "both"
    for k in esler:
        fark |= ~(birlesik[f"{k}_y"].astype(float).fillna(-1) == birlesik[f"{k}_e"].astype(float).fillna(-1))
    return int(fark.sum())


def karsilastir(dizin: Path) -> pd.DataFrame:
    """Rev.9 metnindeki sayilar: olcum betigi ciktilari ile bu betigin ciktilari yan yana."""
    eb = pd.read_csv(dizin / "rev9_baslangic_tam.csv")
    ed = pd.read_csv(dizin / "rev9_donem_sonu_tam.csv")
    et = pd.read_csv(dizin / "rev9_tk_tam.csv")
    er = pd.read_csv(dizin / "rev9_ritim_pozisyon_tam.csv")
    yb = pd.read_csv(dizin / CIKTI["baslangic"].name)
    yd = pd.read_csv(dizin / CIKTI["donem_sonu"].name)
    yt = pd.read_csv(dizin / CIKTI["tk"].name)
    yr = pd.read_csv(dizin / CIKTI["ritim"].name)
    satir = []

    def ekle(kalem, eski, yeni, satir_farki=None, not_=""):
        satir.append({"kalem": kalem, "olcum_betigi": eski, "gercek_kod": yeni, "fark": yeni - eski,
                      "satir_farki": satir_farki, "not": not_})

    esler = {"plan": "plan", "tam": "capa_duzeltme_tam", "capa_yok": "capa_duzeltme_capa_yok",
             "zincir_bozuk": "capa_duzeltme_zincir_bozuk", "son_bozuk": "capa_duzeltme_son_bozuk",
             "kuyruk_kismi": "capa_duzeltme_kuyruk_kismi", "son_esitlik_affi": "capa_duzeltme_son_esitlik_affi",
             "bosluk_etkisi": "bosluk_etkisi_capa_duzeltme"}
    fark_b = _satir_farki(yb, eb, ["sembol", "bar", "kume"], esler)
    for k, v in esler.items():
        ekle(f"baslangic.{k}", int(eb[v].sum()), int(yb[k].sum()), fark_b, "sembol x izgara x kume")
    kuyruk = int(yb["kuyruk_kismi"].sum()) / max(int(yb["tam"].sum()), 1)
    kuyruk_e = int(eb["capa_duzeltme_kuyruk_kismi"].sum()) / max(int(eb["capa_duzeltme_tam"].sum()), 1)
    ekle("baslangic.kuyruk_kismi_payi_yuzde", round(100 * kuyruk_e, 2), round(100 * kuyruk, 2), None)

    kural = ed["tur"] != "veri_sonu"
    for bar in (config.BAR_4H, config.BAR_1D):
        e_ = ed.loc[kural & (ed["bar"] == bar) & ed["ret_gerekcesi"].isna()]
        y_ = yd.loc[(yd["tur"] != "veri_sonu") & (yd["bar"] == bar) & yd["ret_gerekcesi"].isna()]
        ekle(f"donem_sonu.bozuk.{bar}", int((~e_["capa_duzeltme_tam"].astype(bool)).sum()),
             int((~y_["tam"].astype(bool)).sum()), None,
             "bozuk: " + ";".join(f"{r.sembol} d{r.donem_sira}" for r in y_.loc[~y_["tam"].astype(bool)].itertuples()))
    anahtar_d = ["sembol", "bar", "donem_sira", "ret_gerekcesi"]
    fark_d = (_satir_farki(yd, ed, anahtar_d, {})
              + _satir_farki(yd.loc[yd["ret_gerekcesi"].isna()], ed.loc[ed["ret_gerekcesi"].isna()], anahtar_d,
                             {"tam": "capa_duzeltme_tam"}))
    ekle("donem_sonu.satir_farki", 0, fark_d, fark_d, "sembol x izgara x donem: ret gerekcesi ve tam")

    for ad, filtre in (("birincil", lambda d: d["ufuk"] == d["bar"].map(config.BIRINCIL_UFUK)),
                       ("butun_ufuklar", lambda d: d["ufuk"].notna())):
        e_ = et.loc[(et["durum"] == "t_esit_k") & filtre(et)]
        y_ = yt.loc[(yt["durum"] == "t_esit_k") & filtre(yt)]
        ekle(f"tk.{ad}.pozisyon", len(e_), len(y_))
        ekle(f"tk.{ad}.tam", int(e_["capa_duzeltme_tam"].astype(bool).sum()), int(y_["tam"].astype(bool).sum()))
    anahtar_t = ["sembol", "donem_sira", "bar", "ufuk", "durum"]
    fark_t = (_satir_farki(yt, et, anahtar_t, {})
              + _satir_farki(yt.loc[yt["durum"] == "t_esit_k"], et.loc[et["durum"] == "t_esit_k"], anahtar_t,
                             {"tam": "capa_duzeltme_tam"}))
    ekle("tk.satir_farki", 0, fark_t, fark_t, "sembol x donem x izgara x ufuk: durum ve tam")
    ekle("tk.donem_sonu_cikisi", 0, int((yt.loc[yt["durum"] == "t_esit_k", "cikis_turu"] == "donem_sonu").sum()), None,
         "Rev.9: T = K olan pozisyonlarin donem sonu cikisi sayisi (olcum betiginde olagan)")

    anahtar_r = ["sembol", "bar", "kume", "yil", "capa_aralik", "son_aralik", "tek_ritim"]
    fark_r = _satir_farki(yr, er, anahtar_r, {"plan": "plan", "tam": "tam", "kuyruk_kismi": "kuyruk_kismi",
                                             "son_esitlik_affi": "son_esitlik_affi"})
    ekle("ritim.satir_farki", 0, fark_r, fark_r, "rev9_ritim_pozisyon ile ayni gruplama")
    for bar in (config.BAR_4H, config.BAR_1D):
        for aralik in (8.0, 4.0, 2.0, 1.0):
            e_ = er.loc[(er["bar"] == bar) & (er["son_aralik"] == aralik) & er["tek_ritim"].astype(bool)]
            y_ = yr.loc[(yr["bar"] == bar) & (yr["son_aralik"] == aralik) & yr["tek_ritim"].astype(bool)]
            if len(e_) or len(y_):
                pe = 100 * e_["kuyruk_kismi"].sum() / max(e_["tam"].sum(), 1)
                py = 100 * y_["kuyruk_kismi"].sum() / max(y_["tam"].sum(), 1)
                ekle(f"ritim.kuyruk_kismi_payi_yuzde.{bar}.tek_ritim_{int(aralik)}h", round(float(pe), 2),
                     round(float(py), 2), None, f"tam pozisyon {int(y_['tam'].sum())}")
    return pd.DataFrame(satir)


def main(argv: list[str] | None = None) -> None:
    ayristirici = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ayristirici.add_argument("--is-parcaci", type=int, default=4, help="es zamanli surec sayisi")
    ayristirici.add_argument("--semboller", nargs="*", default=None, help="yalnizca bu semboller (deneme)")
    ayristirici.add_argument("--cikti-dizini", type=Path, default=BU_DIZIN, help="CSV dizini (deneme icin)")
    argumanlar = ayristirici.parse_args(argv)
    with kosu_kilidi("rev9_uygulama", CIKTI["ortam"].parent):
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
        secilen = [s for s in semboller if donemler[s] and (argumanlar.semboller is None or s in argumanlar.semboller)]
        b_s, r_s, d_s, t_s = [], [], [], []
        with ProcessPoolExecutor(max_workers=argumanlar.is_parcaci) as havuz:
            isler = [havuz.submit(sembol_olc, s, grup[s], donemler[s], sinif_haritasi.get(s), veri_sonu_bari)
                     for s in secilen]
            for is_ in isler:
                a, b, c, d = is_.result()
                b_s += a
                r_s += b
                d_s += c
                t_s += d
        cikti = argumanlar.cikti_dizini
        csv_yaz(pd.DataFrame(b_s), cikti / CIKTI["baslangic"].name)
        csv_yaz(pd.DataFrame(r_s), cikti / CIKTI["ritim"].name)
        csv_yaz(pd.DataFrame(d_s), cikti / CIKTI["donem_sonu"].name)
        csv_yaz(pd.DataFrame(t_s), cikti / CIKTI["tk"].name)
        if argumanlar.semboller is None:
            tablo = karsilastir(cikti)
            csv_yaz(tablo, cikti / CIKTI["karsilastirma"].name)
            print(tablo.to_string(index=False))
        csv_yaz(ortam_kaydi(git, baslangic_zamani, pd.Timestamp.now(tz="UTC")), cikti / CIKTI["ortam"].name)
        print(f"sembol {len(secilen)} | baslangic {len(b_s)} | ritim {len(r_s)} | donem sonu {len(d_s)} | "
              f"T=K {len(t_s)} -> {cikti}")


if __name__ == "__main__":
    try:
        main()
    except KosuKilidiHatasi as hata:
        print(f"HATA: {hata}", file=sys.stderr)
        sys.exit(2)
