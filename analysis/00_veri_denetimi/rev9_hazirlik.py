"""Rev.9 hazirligi: onerilen funding tamlik kuralinin ve T = K durumunun etkisi. YALNIZCA SAYI.

Getiri, fiyat farki ya da funding degeri HESAPLAMAZ ve raporlamaz. Mumlardan acilis
zamani ve (donem sonu turu icin) hacmin sifir olup olmadigi, funding kayitlarindan
odeme zamani ve aralik alani okunur (CLAUDE.md §3.1, RESULTS §14.9). Veri katmani
DEGISMEZ: plan gercek `pencere.pozisyon_plani`, rev.8 tamligi gercek
`funding.funding_tamlik_ayrintisi`, zaman karsilastirmalari gercek `pencere`
yardimcilaridir. Onerilen kural yalnizca bu betikteki `oneri_tamlik_ayrintisi`
olcum fonksiyonundadir; hicbir karar yolunda kullanilmaz.

Onerilen kural (rev.8 "baslangic boslugu" ve "penceresinde hic kayit yoksa tam degil"
cumlelerinin yerine):
  - Giristen onceki son donem ici kayittan pencere sonuna kadar olan kayit dizisi
    degerlendirilir.
  - Ardisik iki kayit arasindaki bosluk, iki kaydin araliklarindan buyugunu ve
    toleransi asarsa eksik.
  - Son kayittan sonra aralik + tolerans pencere sonundan once doluyorsa eksik.
  - Giristen once donem icinde kayit yoksa eksik.
Olcumdeki okuma: "giristen onceki" = giris ani ile ayni an ya da once (giris anindaki
odeme pozisyona girmez ama dizinin capasi olabilir); "donem ici" = donem basi ile
ayni an ya da sonra (kume basi taban degildir); son kosul `once(son + aralik,
pencere sonu)` ise eksik (esitlikte tam). Iki okuma ayrica sayilir: capa kesin
once (`kati`) ve son kosulu rev.8'deki gibi (`rev8_son`: esitlikte eksik).

Ciktilar:
1. `rev9_donem_sonu_tam.csv`: donem sonuna ulasan temsili pozisyon (A1 ile ayni
   `a1_olcumu.temsili_plan`), her donem sonu ve izgara; rev.8 ve oneri kosullari.
2. `rev9_baslangic_tam.csv`: butun donem ici barlar (1d'de gunler) varsayimsal
   sinyal, birincil ufuk (rev8_etki ile ayni evren); sembol x izgara x kume sayimi.
3. `rev9_farklar_tam.csv`: iki kuralin farkli hukum verdigi pozisyonlar (yalnizca
   zaman damgasi ve tur).
4. `rev9_tk_tam.csv`: T = K olan pozisyonlar (her donem, her izgara ve ufuk icin tek
   sinyal): donem sonu cikisi sayilsaydi funding penceresi (giris, K] -> (giris, B].

Kullanim:
    python analysis/00_veri_denetimi/rev9_hazirlik.py --is-parcaci 8
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
from calistir import (KosuKilidiHatasi, csv_yaz, donem_sonu_turleri, git_durumu,  # noqa: E402
                      kosu_kilidi, ortam_kaydi)
from data import donem as donem_modulu  # noqa: E402
from data import funding as funding_modulu  # noqa: E402
from data import klines as klines_modulu  # noqa: E402
from data import pencere as pencere_modulu  # noqa: E402
from data import split as split_modulu  # noqa: E402
from data import universe as universe_modulu  # noqa: E402
from rev8_etki import kume_sinirlari, sinyal_kumesi  # noqa: E402

P = pencere_modulu
CIKTI_DONEM_SONU = BU_DIZIN / "rev9_donem_sonu_tam.csv"
CIKTI_BASLANGIC = BU_DIZIN / "rev9_baslangic_tam.csv"
CIKTI_FARKLAR = BU_DIZIN / "rev9_farklar_tam.csv"
CIKTI_TK = BU_DIZIN / "rev9_tk_tam.csv"
CIKTI_ORTAM = BU_DIZIN / "rev9_ortam_tam.csv"

ONERI_KOSULLARI = ("onceki_var", "aralik_gecerli", "zincir_tam", "son_tam")
# Raporlanan ufuklar (on-kayit §4 tablo: birincil ve ikincil).
UFUKLAR = {config.BAR_4H: (6, 18, 42), config.BAR_1D: (7, 14, 30)}


# --- Onerilen kural (yalnizca olcum) -------------------------------------------------


def oneri_tamlik_ayrintisi(funding: pd.DataFrame, girisler, pencere_sonlari, donem_baslari, *,
                           kati_onceki: bool = False, son_kurali: str = "oneri") -> pd.DataFrame:
    """Onerilen funding tamlik kurali, kosul kosul. Vektorel, saf; yalnizca odeme ZAMANI ve
    ARALIGI okunur. Zaman karsilastirmalari `pencere` yardimcilariyla.

    Dizi: capa (giristen onceki son donem ici kayit) ve pencere sonuyla ayni an ya da
    once olan butun kayitlar.
      - `onceki_var`: capa var ve donem basi ile ayni an ya da sonra. `kati_onceki`
        ise capa giristen kesin once (`once`), degilse ayni an ya da once.
      - `aralik_gecerli`: dizideki araliklar sonlu ve > 0.
      - `zincir_tam`: ardisik her iki kayitta sonraki, onceki + iki araligin buyugunden
        SONRA degil (capa -> ilk kayit cifti dahil).
      - `son_tam`: `son_kurali="oneri"`: son kayit + araligi pencere sonundan ONCE
        degil; `"rev8"`: pencere sonundan SONRA (rev.8 `son_tam` ile ayni).
      - `son_esit`: son kayit + araligi pencere sonuyla ayni an (iki son kuralinin
        ayrildigi yer).
    """
    if son_kurali not in ("oneri", "rev8"):
        raise ValueError(f"son_kurali: {son_kurali!r}")
    girisler = pd.DatetimeIndex(girisler)
    sonlar = pd.DatetimeIndex(pencere_sonlari)
    baslar = pd.DatetimeIndex(donem_baslari)
    if not (len(girisler) == len(sonlar) == len(baslar)):
        raise ValueError("girisler, pencere_sonlari ve donem_baslari ayni uzunlukta olmali.")
    n = len(girisler)
    sonuc = pd.DataFrame({k: np.zeros(n, dtype=bool) for k in (*ONERI_KOSULLARI, "son_esit", "tam")})
    if n == 0 or funding.empty:
        return sonuc
    zamanlar = funding_modulu._zaman_dizisi(funding, "oneri_tamlik_ayrintisi")
    aralik = pd.to_numeric(funding["aralik_saat"], errors="coerce").to_numpy(dtype=float)
    iyi = np.isfinite(aralik) & (aralik > 0)
    aralik_td = pd.to_timedelta(np.where(iyi, aralik, 0.0), unit="h")

    # Capa: kati ise z <= giris - 1 dk (`once`), degilse z < giris + 1 dk (ayni an ya da once).
    if kati_onceki:
        j = zamanlar.searchsorted(P.ayni_an_basi(girisler), side="right") - 1
    else:
        j = zamanlar.searchsorted(P.ayni_an_sonu(girisler), side="left") - 1
    hi = zamanlar.searchsorted(P.ayni_an_sonu(sonlar), side="left")  # pencere sonuyla ayni an ya da once
    jj = np.maximum(j, 0)
    onceki_var = (j >= 0) & np.asarray(P.ayni_ya_da_sonra(zamanlar[jj], baslar), dtype=bool)
    son_i = np.maximum(hi - 1, jj)  # capa varsa hi - 1 >= j (giris <= pencere sonu)

    p_aralik = np.r_[0, np.cumsum(~iyi)]
    aralik_gecerli = onceki_var & ((p_aralik[son_i + 1] - p_aralik[jj]) == 0)

    if len(zamanlar) > 1:
        beklenen = zamanlar[:-1] + pd.to_timedelta(np.maximum(aralik_td[1:].to_numpy(), aralik_td[:-1].to_numpy()))
        kotu_bosluk = np.asarray(P.sonra(zamanlar[1:], beklenen), dtype=bool)
    else:
        kotu_bosluk = np.zeros(0, dtype=bool)
    p_bosluk = np.r_[0, np.cumsum(kotu_bosluk)]  # ciftler [jj, son_i - 1] -> p[son_i] - p[jj]
    zincir_tam = onceki_var & ((p_bosluk[son_i] - p_bosluk[jj]) == 0)

    sonraki = zamanlar[son_i] + aralik_td[son_i]
    if son_kurali == "oneri":
        son_ok = ~np.asarray(P.once(sonraki, sonlar), dtype=bool)
    else:
        son_ok = np.asarray(P.sonra(sonraki, sonlar), dtype=bool)
    son_tam = onceki_var & son_ok & aralik_gecerli

    sonuc["onceki_var"] = onceki_var
    sonuc["aralik_gecerli"] = aralik_gecerli
    sonuc["zincir_tam"] = zincir_tam & aralik_gecerli
    sonuc["son_tam"] = son_tam
    sonuc["son_esit"] = onceki_var & np.asarray(P.ayni_an(sonraki, sonlar), dtype=bool)
    sonuc["tam"] = onceki_var & aralik_gecerli & zincir_tam & son_tam
    return sonuc


def fark_turu(rev8: pd.Series, oneri: pd.Series) -> str | None:
    """Iki kuralin hukmu farkliysa farkin turu; ayniysa None. Saf.

    Oneriye gore tam, rev.8'e gore degil:
      - `kayitsiz_kisa_pencere`: pencerede kayit yok (rev.8 `kayit_var` bozuk).
      - `diger_son_esitlik`: rev.8 yalnizca `son_tam`'da bozuk ve son + aralik = pencere sonu.
      - `diger_baslangic_araligi`: rev.8 `baslangic_tam` bozuk (ilk kaydin araligi kisa,
        capa + iki araligin buyugu yetiyor).
      - `diger`.
    Rev.8'e gore tam, oneriye gore degil:
      - `gec_baslayan_funding`: giristen once donem icinde kayit yok.
      - `diger_giris_oncesi_bosluk`: capa -> ilk kayit boslugu kurali asiyor.
      - `diger`.
    """
    if bool(rev8["tam"]) == bool(oneri["tam"]):
        return None
    if oneri["tam"]:
        if not rev8["kayit_var"]:
            return "kayitsiz_kisa_pencere"
        if (rev8["baslangic_tam"] and rev8["ic_tam"] and rev8["aralik_gecerli"] and not rev8["son_tam"]
                and oneri["son_esit"]):
            return "diger_son_esitlik"
        if not rev8["baslangic_tam"]:
            return "diger_baslangic_araligi"
        return "diger"
    if not oneri["onceki_var"]:
        return "gec_baslayan_funding"
    if not oneri["zincir_tam"]:
        return "diger_giris_oncesi_bosluk"
    return "diger"


FARK_TURLERI = ("kayitsiz_kisa_pencere", "diger_son_esitlik", "diger_baslangic_araligi", "gec_baslayan_funding",
                "diger_giris_oncesi_bosluk", "diger")


def _iki_kural(seri: pd.DataFrame, girisler, sonlar, baslar) -> pd.DataFrame:
    """Ayni pozisyonlarda rev.8 (gercek kod) ve oneri (uc okuma) kosullari, tek cerceve."""
    rev8 = funding_modulu.funding_tamlik_ayrintisi(seri, girisler, sonlar)
    oneri = oneri_tamlik_ayrintisi(seri, girisler, sonlar, baslar)
    kati = oneri_tamlik_ayrintisi(seri, girisler, sonlar, baslar, kati_onceki=True)
    r8son = oneri_tamlik_ayrintisi(seri, girisler, sonlar, baslar, son_kurali="rev8")
    tablo = pd.concat([rev8.add_prefix("rev8_"), oneri.add_prefix("oneri_")], axis=1)
    tablo["oneri_kati_tam"] = kati["tam"].to_numpy()
    tablo["oneri_rev8son_tam"] = r8son["tam"].to_numpy()
    tablo["fark_turu"] = [
        fark_turu(pd.Series({k: tablo.at[i, f"rev8_{k}"] for k in (*funding_modulu.TAMLIK_KOSULLARI, "tam")}),
                  pd.Series({k: tablo.at[i, f"oneri_{k}"] for k in (*ONERI_KOSULLARI, "son_esit", "tam")}))
        if tablo.at[i, "rev8_tam"] != tablo.at[i, "oneri_tam"] else None
        for i in range(len(tablo))
    ]
    return tablo


def _bos_seri() -> pd.DataFrame:
    return pd.DataFrame({"odeme_zamani": pd.DatetimeIndex([], tz="UTC"), "aralik_saat": np.empty(0)})


# --- 1. Donem sonu (temsili pozisyon) ---------------------------------------------


def donem_sonu_satirlari(sembol: str, donemler, turler, seri: pd.DataFrame) -> list[dict]:
    """Her donem sonu ve izgara: temsili plan (A1 ile ayni), iki kural. Saf."""
    satirlar = []
    zam = pd.DatetimeIndex(seri["odeme_zamani"])
    aralik = pd.to_numeric(seri["aralik_saat"], errors="coerce").to_numpy(dtype=float)
    for bar in (config.BAR_4H, config.BAR_1D):
        for i, (d, tur) in enumerate(zip(donemler, turler)):
            satir = {"sembol": sembol, "bar": bar, "donem_sira": i, "tur": tur, "donem_baslangic": d.baslangic,
                     "donem_bitis": d.bitis, "giris": pd.NaT, "pencere_sonu": pd.NaT, "ret_gerekcesi": None}
            try:
                plan = temsili_plan(d, bar)
            except P.OlayOlusmaz as hata:
                satir["ret_gerekcesi"] = P.ret_gerekcesi(hata)
                satirlar.append(satir)
                continue
            except P.DonemDisiSinyal:
                satir["ret_gerekcesi"] = "donem_disi_sinyal"
                satirlar.append(satir)
                continue
            son = funding_modulu.funding_penceresi_sonu(plan)
            satir.update(giris=plan.giris, pencere_sonu=son, cikis_turu=plan.cikis_turu)
            k = _iki_kural(seri, [plan.giris], [son], [d.baslangic]).iloc[0].to_dict()
            satir.update(k)
            # Capa ve pencere icindeki ilk kayit (yalnizca zaman ve aralik).
            capa = np.flatnonzero(np.asarray(P.ayni_ya_da_once(zam, plan.giris), dtype=bool)) if len(zam) else []
            ici = (np.flatnonzero(np.asarray(P.sonra(zam, plan.giris), dtype=bool)
                                  & np.asarray(P.ayni_ya_da_once(zam, son), dtype=bool)) if len(zam) else [])
            satir["capa_zamani"] = zam[capa[-1]] if len(capa) else pd.NaT
            satir["capa_aralik_saat"] = float(aralik[capa[-1]]) if len(capa) else float("nan")
            satir["pencerede_kayit"] = len(ici)
            satirlar.append(satir)
    return satirlar


# --- 2. Baslangic ve farklar (butun donem ici barlar, birincil ufuk) ------------------------


def baslangic_ve_farklar(sembol: str, grup: str, donemler, mumlar: pd.DataFrame, seri: pd.DataFrame,
                         kumeler) -> tuple[list[dict], list[dict]]:
    """rev8_etki.baslangic_etkisi ile ayni pozisyon evreni; iki kural. Saf."""
    zamanlar = pd.DatetimeIndex(mumlar["open_time"])
    satirlar, farklar = [], []
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
                sonlar.append(funding_modulu.funding_penceresi_sonu(plan))
                baslar.append(d.baslangic)
                plan_kumeleri.append(kume)
        if not girisler:
            continue
        rev8 = funding_modulu.funding_tamlik_ayrintisi(seri, girisler, sonlar)
        oneri = oneri_tamlik_ayrintisi(seri, girisler, sonlar, baslar)
        kati = oneri_tamlik_ayrintisi(seri, girisler, sonlar, baslar, kati_onceki=True)
        r8son = oneri_tamlik_ayrintisi(seri, girisler, sonlar, baslar, son_kurali="rev8")
        kume_dizi = np.array(plan_kumeleri)
        farkli = np.flatnonzero(rev8["tam"].to_numpy() != oneri["tam"].to_numpy())
        turler = {}
        for i in farkli:
            tur = fark_turu(rev8.iloc[i], oneri.iloc[i])
            turler[i] = tur
            farklar.append({"sembol": sembol, "bar": bar, "kume": kume_dizi[i], "giris": girisler[i],
                            "pencere_sonu": sonlar[i], "rev8_tam": bool(rev8.at[i, "tam"]),
                            "oneri_tam": bool(oneri.at[i, "tam"]), "fark_turu": tur})
        for kume in sorted(set(plan_kumeleri)):
            m = kume_dizi == kume
            r, o = rev8.loc[m], oneri.loc[m]
            digerleri = r["kayit_var"] & r["aralik_gecerli"] & r["ic_tam"] & r["son_tam"]
            satir = {"sembol": sembol, "bar": bar, "kume": kume, "plan": int(m.sum()),
                     "rev8_tam": int(r["tam"].sum()), "rev8_kayit_yok": int((~r["kayit_var"]).sum()),
                     "rev8_baslangic_bozuk": int((r["kayit_var"] & ~r["baslangic_tam"]).sum()),
                     "rev8_yalniz_baslangic": int((digerleri & ~r["baslangic_tam"]).sum()),
                     "oneri_tam": int(o["tam"].sum()), "oneri_onceki_yok": int((~o["onceki_var"]).sum()),
                     "oneri_zincir_bozuk": int((o["onceki_var"] & ~o["zincir_tam"]).sum()),
                     "oneri_kati_tam": int(kati.loc[m, "tam"].sum()),
                     "oneri_rev8son_tam": int(r8son.loc[m, "tam"].sum()),
                     "oneri_tam_rev8_degil": int((o["tam"] & ~r["tam"]).sum()),
                     "rev8_tam_oneri_degil": int((r["tam"] & ~o["tam"]).sum())}
            for tur in FARK_TURLERI:
                satir[f"fark_{tur}"] = sum(1 for i, t_ in turler.items() if t_ == tur and kume_dizi[i] == kume)
            satirlar.append(satir)
    return satirlar, farklar


# --- 3. T = K ----------------------------------------------------------------------


def tk_satirlari(sembol: str, grup: str, donemler, turler, mumlar: pd.DataFrame, seri: pd.DataFrame,
                 kumeler) -> list[dict]:
    """Her donem, izgara ve ufuk icin T = K olan tek sinyal: gercek plan; funding penceresi
    sonu K (bugun) ile B (donem sonu cikisi sayilsaydi) karsilastirilir. Saf; zaman okur."""
    zamanlar = pd.DatetimeIndex(mumlar["open_time"])
    zam = pd.DatetimeIndex(seri["odeme_zamani"])
    satirlar = []
    for i, (d, tur) in enumerate(zip(donemler, turler)):
        maske = np.asarray(P.donem_ici_4h_maskesi(zamanlar, donem_baslangic=d.baslangic, donem_bitis=d.bitis),
                           dtype=bool)
        zd = zamanlar[maske]
        k = d.kapanis
        gunler = None
        for bar, ufuklar in UFUKLAR.items():
            adim = P.adim(bar)
            for ufuk in ufuklar:
                t = k - ufuk * adim - adim  # giris = t + adim, T = giris + ufuk x adim = K
                satir = {"sembol": sembol, "donem_sira": i, "tur": tur, "bar": bar, "ufuk": ufuk,
                         "donem_bitis": d.bitis, "sinyal": t, "kume": None, "durum": None}
                if bar == config.BAR_1D:
                    if t != t.floor("D"):
                        satir["durum"] = "1d_sinyal_gunu_yok"  # B 20:00 degilse T = K olamaz
                        satirlar.append(satir)
                        continue
                    if gunler is None:
                        gunler = pd.DatetimeIndex(klines_modulu.gunluge_cevir(mumlar, donemler=[d])["open_time"])
                    sinyal_var = P.ayni_andaki_bar(gunler, t) is not None
                else:
                    sinyal_var = P.ayni_andaki_bar(zd, t) is not None
                if not sinyal_var:
                    satir["durum"] = "sinyal_bari_yok"
                    satirlar.append(satir)
                    continue
                kume = sinyal_kumesi(t, grup, kumeler)
                satir["kume"] = kume
                if kume is None:
                    satir["durum"] = "kume_yok"
                    satirlar.append(satir)
                    continue
                try:
                    plan = P.pozisyon_plani(zd, t, ufuk, bar, birincil_ufuk=config.BIRINCIL_UFUK[bar],
                                            kume_baslangic=kumeler[kume][1], kume_bitis=kumeler[kume][2],
                                            donem_baslangic=d.baslangic, donem_bitis=d.bitis)
                except P.OlayOlusmaz as hata:
                    satir["durum"] = f"ret_{P.ret_gerekcesi(hata)}"
                    satirlar.append(satir)
                    continue
                if not (plan.cikis_turu == "olagan" and P.ayni_an(plan.cikis_ani, k)):
                    satir["durum"] = f"beklenmeyen_{plan.cikis_turu}"
                    satirlar.append(satir)
                    continue
                son_k = funding_modulu.funding_penceresi_sonu(plan)
                a = funding_modulu.funding_tamlik_ayrintisi(seri, [plan.giris, plan.giris], [son_k, d.bitis])
                bk = (np.asarray(P.sonra(zam, d.bitis), dtype=bool)
                      & np.asarray(P.ayni_ya_da_once(zam, k), dtype=bool)) if len(zam) else np.zeros(0, bool)
                satir.update(durum="t_esit_k", pencere_sonu_bugun=son_k,
                             bk_arasi_kayit=int(bk.sum()), k_da_kayit=bool(np.any(P.ayni_an(zam, k))) if len(zam) else False,
                             tam_bugun=bool(a.at[0, "tam"]), tam_b_ile=bool(a.at[1, "tam"]),
                             son_tam_bugun=bool(a.at[0, "son_tam"]), kayit_var_b_ile=bool(a.at[1, "kayit_var"]))
                satirlar.append(satir)
    return satirlar


# --- Ana akis ----------------------------------------------------------------------


def sembol_olc(sembol: str, grup: str, donemler, sinif: str | None, veri_sonu_bari: pd.Timestamp):
    """Bir sembolun uc olcumu. Is parcacigi (ayri surec) icinde calisir."""
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
    ds = donem_sonu_satirlari(sembol, donemler, turler, seri)
    bs, fk = baslangic_ve_farklar(sembol, grup, donemler, mumlar, seri, kumeler)
    tk = tk_satirlari(sembol, grup, donemler, turler, mumlar, seri, kumeler)
    return ds, bs, fk, tk


def main(argv: list[str] | None = None) -> None:
    ayristirici = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ayristirici.add_argument("--is-parcaci", type=int, default=4, help="es zamanli surec sayisi")
    ayristirici.add_argument("--semboller", nargs="*", default=None, help="yalnizca bu semboller (deneme)")
    ayristirici.add_argument("--cikti-dizini", type=Path, default=BU_DIZIN, help="CSV dizini (deneme icin)")
    argumanlar = ayristirici.parse_args(argv)
    with kosu_kilidi("rev9_hazirlik", CIKTI_ORTAM.parent):
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
        d_s, b_s, f_s, t_s = [], [], [], []
        with ProcessPoolExecutor(max_workers=argumanlar.is_parcaci) as havuz:
            isler = [havuz.submit(sembol_olc, s, grup[s], donemler[s], sinif_haritasi.get(s), veri_sonu_bari)
                     for s in secilen]
            for is_ in isler:
                a, b, c, d = is_.result()
                d_s += a
                b_s += b
                f_s += c
                t_s += d
        cikti = argumanlar.cikti_dizini
        csv_yaz(pd.DataFrame(d_s), cikti / CIKTI_DONEM_SONU.name)
        csv_yaz(pd.DataFrame(b_s), cikti / CIKTI_BASLANGIC.name)
        csv_yaz(pd.DataFrame(f_s), cikti / CIKTI_FARKLAR.name)
        csv_yaz(pd.DataFrame(t_s), cikti / CIKTI_TK.name)
        csv_yaz(ortam_kaydi(git, baslangic_zamani, pd.Timestamp.now(tz="UTC")), cikti / CIKTI_ORTAM.name)
        print(f"sembol {len(secilen)} | donem sonu satiri {len(d_s)} | baslangic satiri {len(b_s)} | "
              f"fark {len(f_s)} | T=K satiri {len(t_s)} -> {cikti}")


if __name__ == "__main__":
    try:
        main()
    except KosuKilidiHatasi as hata:
        print(f"HATA: {hata}", file=sys.stderr)
        sys.exit(2)
