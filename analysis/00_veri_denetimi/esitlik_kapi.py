"""Gercek veri esitligi: skaler referans ile bugunku `data/` yolu ayni karari veriyor mu (performans 2a; plan v2 karar 6, D-B5).

Ornek: `esitlik_ornegi.csv` (performans kodundan once sabitlendi; `esitlik_ornegi_sec.py`). Her sembolun evrendeki her
gecerli donemi, KESIF araliginda, istenen hipotez, yapilandirma ve rol kumesinde iki yoldan karara sokulur:
  - kapi: `data.pozisyon.olay_karari` (bugunku yol; P2a ve sonrasinda degisen yol),
  - referans: `data._skaler_referans.olay_karari` (F2 oncesi skaler yolun dondurulmus kopyasi).
Karsilastirilan (bellekte; hicbir deger yazilmaz):
  - kapi karari ve ret gerekcesi sinifi (hata sinifi ayni olmali),
  - iki taraf da onaylarsa `OnaylanmisPozisyon`un butun alanlari (`==`; NaN konumlari dahil, NaN == NaN sayilir),
  - `funding_satiri` satirlari: barin plani (iki yoldan kurulur, ayni olmali) uzerinde funding tamlik satirinin butun
    sutunlari (`Series.equals`, NaN ve NaT konumlari dahil) ve funding toplami (`==`).
H1'in olay rolu capa ister: t barinin capasi, barin izgaradaki sirasi i ile `t - (1 + i mod 12) x 4 saat`tir (sabit, kosula
bakilmadan; boylece karsilastirilan bar sayisi sinyal kosulunun sonucuna bagli degildir ve olay sayisi sizmaz).

Bar kumesi (`--bar`):
  - `tum`: donem ∩ KESIF araligindaki butun izgara barlari (4h ya da 1d; seride olmayan bar da sorulur).
  - `ornek`: tohumlu `--n` bar + sinir barlari (donemin ilk ve son 200 bari, kume sinirinin +-200 bari, funding ritim
    degisiminin +-20 bari). Tohum kurali `esitlik_ornegi_sec.py` aciklamasindadir.
  - `uyarlamali`: once her hipotezde 30 tohumlu kalibrasyon bari olculur; sembolun `tum` kestirimi `--sure-siniri-dk`
    dakikayi asarsa sembolun butun hipotezleri `ornek` ile (kalibrasyon barlari dahil) kosar. Satirdaki `bar_kumesi`
    hangisinin kullanildigini yazar.

Cikti: `esitlik_kapi_<etiket>_tam.csv` (sembol, donem_no, hipotez, yapilandirma, rol, bar_kumesi, karsilastirilan_bar,
uyusmayan_bar, ilk_20_uyusmayan, sure_s, hata) ve `esitlik_kapi_<etiket>_kesif_kaydi_tam.csv` (`KesifKaydi.alanlar()`).
`hata` yalnizca beklenmeyen bir hatanin SINIF adidir; mesaj yazilmaz (mesaj deger icerebilir). Uyusmayan barlar yalnizca
zaman damgasiyla yazilir.

Temiz calisma agaci ister (`git status --porcelain` bos); `split.kesif_kosusu` icinde kosar, ag yasagi kosu boyuncadir.
Paralellik: surec havuzu kesif kosusunun ICINDE kurulur (plan_performans_2 §6: isciler kesif baglamini ve ag yasagini
devralir). Getiri, sinyal degeri ya da olay sayisi hesaplanmaz, yazilmaz.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import hashlib
import math
import multiprocessing
import subprocess
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
from data import _skaler_referans as referans  # noqa: E402
from data import funding as funding_modulu  # noqa: E402
from data import pencere as pencere_modulu  # noqa: E402
from data import pozisyon as pozisyon_modulu  # noqa: E402
from data import sinyal as sinyal_modulu  # noqa: E402
from data import split as split_modulu  # noqa: E402
from data import universe as universe_modulu  # noqa: E402

ORNEK = BU_DIZIN / "esitlik_ornegi.csv"
SUTUNLAR = ["sembol", "donem_no", "hipotez", "yapilandirma", "rol", "bar_kumesi", "karsilastirilan_bar", "uyusmayan_bar",
            "ilk_20_uyusmayan", "sure_s", "hata"]
ROLLER = ("olay", "K1", "K2")
FUNDING_SATIRI = "funding_satiri"
KUME = "KESIF"
H4 = pd.Timedelta(hours=4)
SINIR_DONEM = 200
SINIR_KUME = 200
SINIR_RITIM = 20
KALIBRASYON = 30


# --- Karsilastirma -------------------------------------------------------------------------------------

def _deger_esit(a, b) -> bool:
    if type(a) is not type(b):
        return False
    if dataclasses.is_dataclass(a):
        return all(_deger_esit(getattr(a, f.name), getattr(b, f.name)) for f in dataclasses.fields(a) if f.compare)
    if isinstance(a, float):
        return (math.isnan(a) and math.isnan(b)) or a == b
    return bool(a == b)


def sonuc_esit(a, b) -> bool:
    """Hata: ayni sinif. Onayli pozisyon (ya da plan): butun alanlar, NaN konumlari dahil."""
    if isinstance(a, BaseException) or isinstance(b, BaseException):
        return type(a) is type(b)
    return _deger_esit(a, b)


def _cagir(fonk, *args, **kwargs):
    try:
        return fonk(*args, **kwargs)
    except Exception as hata:  # noqa: BLE001 - yalnizca sinifi karsilastirilir
        return hata


def tohum(sembol: str, donem_no: int, hipotez: str, yapilandirma_kimligi: str, rol: str) -> int:
    """Kosu sirasindan bagimsiz tohum (`esitlik_ornegi_sec.py` aciklamasi)."""
    metin = "|".join((str(config.TOHUM), "esitlik", sembol, str(donem_no), hipotez, yapilandirma_kimligi, rol))
    return int.from_bytes(hashlib.sha256(metin.encode("utf-8")).digest()[:8], "big")


def h1_capasi(t: pd.Timestamp, sira: int) -> pd.Timestamp:
    return t - (1 + sira % config.H1_IZLEME_BAR) * H4


def _esikler(bar: str) -> dict:
    hacim = config.ASGARI_HACIM_4H if bar == config.BAR_4H else config.ASGARI_HACIM_1D
    return {"asgari_hacim": hacim, "asgari_listeleme_yasi_gun": config.ASGARI_LISTELEME_YASI_GUN}


def karar(modul, hipotez: str, yapilandirma, rol: str, t, kimlik: dict, sira: int):
    """`modul.olay_karari` (birincil ufuk); sonuc ya da hata nesnesi."""
    tanim = pencere_modulu.hipotez_ufuklari(hipotez)
    capa = h1_capasi(t, sira) if (hipotez in sinyal_modulu.CAPALI_HIPOTEZLER and rol == "olay") else None
    return _cagir(modul.olay_karari, t, tanim.birincil, tanim.bar, hipotez=hipotez, yapilandirma=dict(yapilandirma),
                  rol=rol, capa=capa, birincil_ufuk=tanim.birincil, kume=KUME, **kimlik, **_esikler(tanim.bar))


def karsilastir(barlar, siralar, hipotez: str, yapilandirma, rol: str, kimlik: dict, *, kapi=pozisyon_modulu,
                ref=referans) -> tuple[int, int, list[str]]:
    """(karsilastirilan, uyusmayan, ilk 20 uyusmayanin zaman damgasi). Deger dondurmez."""
    uyusmayan = []
    for t, sira in zip(barlar, siralar):
        a = karar(kapi, hipotez, yapilandirma, rol, t, kimlik, sira)
        b = karar(ref, hipotez, yapilandirma, rol, t, kimlik, sira)
        if not sonuc_esit(a, b):
            uyusmayan.append(t)
    return len(barlar), len(uyusmayan), [z.isoformat() for z in uyusmayan[:20]]


def _veri(kimlik: dict):
    bas, bitis, _ = pozisyon_modulu.donem_kaydi(kimlik["sembol"], kimlik["donem_no"])
    kb, ks = pozisyon_modulu.kume_sinirlari(KUME)
    m, fr, _ = pozisyon_modulu._karar_verisi(kimlik["sembol"], KUME, kume_baslangic=kb, kume_bitis=ks,
                                             donem_baslangic=bas, donem_bitis=bitis)
    return m, fr, (kb, ks, bas, bitis)


def _plan(modul, zamanlar, t, hipotez: str, sinirlar):
    tanim = pencere_modulu.hipotez_ufuklari(hipotez)
    kb, ks, bas, bitis = sinirlar
    return _cagir(modul.pozisyon_plani, zamanlar, t, tanim.birincil, tanim.bar, birincil_ufuk=tanim.birincil,
                  kume_baslangic=kb, kume_bitis=ks, donem_baslangic=bas, donem_bitis=bitis)


def _satir_esit(a: pd.Series, b: pd.Series) -> bool:
    return list(a.index) == list(b.index) and a.equals(b)


def _toplam_esit(a: float, b: float) -> bool:
    return (math.isnan(a) and math.isnan(b)) or a == b


def funding_karsilastir(barlar, hipotez: str, kimlik: dict, *, kapi_funding=funding_modulu,
                        ref=referans) -> tuple[int, int, list[str]]:
    """Barin plani iki yoldan kurulur ve ayni olmali; plan varsa funding tamlik satiri (butun sutunlar) ve toplam.

    Uc yol referansla karsilastirilir (P2a, D-C6): genel n = 1 yolu (`pozisyon_funding_ayrintisi`, `_plan_fundingi`),
    kapinin tek tamlik yolu (`_pozisyon_tamlik_satiri` + `_satirdan_toplam`) ve toplu yol (bar kumesindeki butun
    planlar TEK cagrida, `_planlar_tamlik_satirlari`). Bir barda uclerinden biri ayrisirsa bar uyusmayandir."""
    m, fr, sinirlar = _veri(kimlik)
    zamanlar = pd.DatetimeIndex(m["open_time"])
    uyusmayan = set()
    planli = []
    for t in barlar:
        pa, pb = _plan(pencere_modulu, zamanlar, t, hipotez, sinirlar), _plan(ref, zamanlar, t, hipotez, sinirlar)
        esit = sonuc_esit(pa, pb)
        if esit and not isinstance(pa, BaseException):
            ref_satir, ref_toplam = ref.pozisyon_funding_ayrintisi(fr, pa), ref._plan_fundingi(fr, pa)
            tek = kapi_funding._pozisyon_tamlik_satiri(fr, pa)
            esit = (_satir_esit(kapi_funding.pozisyon_funding_ayrintisi(fr, pa), ref_satir)
                    and _toplam_esit(kapi_funding._plan_fundingi(fr, pa), ref_toplam)
                    and _satir_esit(tek.satir, ref_satir)
                    and _toplam_esit(kapi_funding._satirdan_toplam(fr, pa, tek), ref_toplam))
            planli.append((t, pa, ref_satir, ref_toplam))
        if not esit:
            uyusmayan.add(t)
    if planli:
        toplu = kapi_funding._planlar_tamlik_satirlari(fr, [p for _, p, _, _ in planli])
        for (t, plan, ref_satir, ref_toplam), tamlik in zip(planli, toplu):
            if not (_satir_esit(tamlik.satir, ref_satir)
                    and _toplam_esit(kapi_funding._satirdan_toplam(fr, plan, tamlik), ref_toplam)):
                uyusmayan.add(t)
    sirali = sorted(uyusmayan)
    return len(barlar), len(sirali), [z.isoformat() for z in sirali[:20]]


# --- Bar kumeleri --------------------------------------------------------------------------------------

def bar_izgarasi(kimlik: dict, hipotez: str) -> pd.DatetimeIndex:
    """Donem ∩ KESIF araligindaki izgara barlari (hipotezin bar turu)."""
    bas, bitis, _ = pozisyon_modulu.donem_kaydi(kimlik["sembol"], kimlik["donem_no"])
    kb, ks = pozisyon_modulu.kume_sinirlari(KUME)
    bas, bitis = max(bas, kb), min(bitis, ks)
    if pencere_modulu.hipotez_izgarasi(hipotez) == config.BAR_4H:
        return pd.date_range(bas.ceil("4h"), bitis, freq=H4)
    return pd.date_range(bas.ceil("D"), bitis, freq="1D")


def sinir_siralari(izgara: pd.DatetimeIndex, kimlik: dict) -> set[int]:
    """Donemin ilk/son 200 bari, kume sinirinin +-200 bari, funding ritim degisiminin +-20 bari (izgara sira no)."""
    n = len(izgara)
    secim = set(range(min(SINIR_DONEM, n))) | set(range(max(0, n - SINIR_DONEM), n))
    for sinir in (pd.Timestamp(config.KESIF_BASI), pd.Timestamp(config.KESIF_SONU)):
        i = int(izgara.searchsorted(sinir))
        secim |= set(range(max(0, i - SINIR_KUME), min(n, i + SINIR_KUME)))
    _, fr, _ = _veri(kimlik)
    if len(fr) > 1:
        aralik = pd.to_numeric(fr["aralik_saat"], errors="coerce").to_numpy(dtype=float)
        degisim = pd.DatetimeIndex(fr["odeme_zamani"])[1:][aralik[1:] != aralik[:-1]]
        for z in degisim:
            i = int(izgara.searchsorted(z))
            secim |= set(range(max(0, i - SINIR_RITIM), min(n, i + SINIR_RITIM)))
    return {i for i in secim if 0 <= i < n}


def tohumlu_siralar(n: int, adet: int, tohum_degeri: int) -> set[int]:
    if n == 0:
        return set()
    return set(np.random.default_rng(tohum_degeri).choice(n, size=min(adet, n), replace=False).tolist())


# --- Sembol isi ------------------------------------------------------------------------------------------

def _donemler(sembol: str) -> list[int]:
    evren = universe_modulu.evren_yukle()
    satir = evren.loc[(evren["sembol"] == sembol) & ~evren["haric"] & (evren["donem_id"] >= 0)]
    kb, ks = pozisyon_modulu.kume_sinirlari(KUME)
    sonuc = []
    for no in sorted(int(x) for x in satir["donem_id"]):
        bas, bitis, _ = pozisyon_modulu.donem_kaydi(sembol, no)
        if bas <= ks and bitis >= kb:
            sonuc.append(no)
    return sonuc


def _birim_etiketleri(roller, funding_satiri: bool):
    return list(roller) + ([FUNDING_SATIRI] if funding_satiri else [])


def _kos(birim, izgara, siralar, hipotez, y, kimlik):
    barlar = [izgara[i] for i in siralar]
    if birim == FUNDING_SATIRI:
        return funding_karsilastir(barlar, hipotez, kimlik)
    return karsilastir(barlar, siralar, hipotez, y, birim, kimlik)


def sembol_isi(sembol: str, ayar: dict) -> list[dict]:
    """Bir sembolun butun donemleri, hipotezleri, yapilandirmalari ve rolleri. Yalnizca sayi ve zaman damgasi doner."""
    satirlar = []
    bas_sure = time.perf_counter()
    gorevler = []
    for donem_no in _donemler(sembol):
        kimlik = {"sembol": sembol, "donem_no": donem_no}
        for hipotez in ayar["hipotezler"]:
            izgara_y = list(sinyal_modulu.izgara(hipotez))
            yapilandirmalar = izgara_y[:1] if ayar["yapilandirma"] == "ilk" else izgara_y
            izgara = bar_izgarasi(kimlik, hipotez)
            for y in yapilandirmalar:
                gorevler.append((kimlik, hipotez, y, izgara))

    # Kalibrasyon (yalnizca `uyarlamali`): her gorevde 30 tohumlu bar, butun birimler.
    kip = ayar["bar"]
    kalibrasyon: dict[int, set[int]] = {}
    if kip == "uyarlamali":
        kestirim = 0.0
        for k, (kimlik, hipotez, y, izgara) in enumerate(gorevler):
            yk = sinyal_modulu.yapilandirma_kimligi(hipotez, y)
            sec = sorted(tohumlu_siralar(len(izgara), KALIBRASYON, tohum(sembol, kimlik["donem_no"], hipotez, yk,
                                                                         "kalibrasyon")))
            kalibrasyon[k] = set(sec)
            t0 = time.perf_counter()
            for birim in _birim_etiketleri(ayar["roller"], ayar["funding_satiri"]):
                _kos(birim, izgara, sec, hipotez, y, kimlik)
            if sec:
                kestirim += (time.perf_counter() - t0) / len(sec) * len(izgara)
        kip = "tum" if kestirim <= ayar["sure_siniri_dk"] * 60 else "ornek"

    for k, (kimlik, hipotez, y, izgara) in enumerate(gorevler):
        yk = sinyal_modulu.yapilandirma_kimligi(hipotez, y)
        for birim in _birim_etiketleri(ayar["roller"], ayar["funding_satiri"]):
            t0 = time.perf_counter()
            satir = {"sembol": sembol, "donem_no": kimlik["donem_no"], "hipotez": hipotez, "yapilandirma": yk,
                     "rol": birim, "bar_kumesi": "", "karsilastirilan_bar": 0, "uyusmayan_bar": 0,
                     "ilk_20_uyusmayan": "", "sure_s": 0.0, "hata": ""}
            try:
                if kip == "tum":
                    siralar = list(range(len(izgara)))
                    satir["bar_kumesi"] = "tum"
                else:
                    sec = tohumlu_siralar(len(izgara), ayar["n"], tohum(sembol, kimlik["donem_no"], hipotez, yk, birim))
                    sec |= sinir_siralari(izgara, kimlik) | kalibrasyon.get(k, set())
                    siralar = sorted(sec)
                    satir["bar_kumesi"] = f"ornek_{ayar['n']}+sinir" + ("+kalibrasyon" if k in kalibrasyon else "")
                n, u, ilk = _kos(birim, izgara, siralar, hipotez, y, kimlik)
                satir.update(karsilastirilan_bar=n, uyusmayan_bar=u, ilk_20_uyusmayan=";".join(ilk))
            except Exception as hata:  # noqa: BLE001 - yalnizca sinif adi yazilir
                satir["hata"] = type(hata).__name__
            satir["sure_s"] = round(time.perf_counter() - t0, 1)
            satirlar.append(satir)
    satirlar.append({"sembol": sembol, "donem_no": -1, "hipotez": "", "yapilandirma": "", "rol": "TOPLAM_SURE",
                     "bar_kumesi": kip, "karsilastirilan_bar": 0, "uyusmayan_bar": 0, "ilk_20_uyusmayan": "",
                     "sure_s": round(time.perf_counter() - bas_sure, 1), "hata": ""})
    return satirlar


def agac_temiz() -> bool:
    cikti = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=KOK, capture_output=True,
                           text=True, check=True).stdout
    return cikti.strip() == ""


def kos(semboller, ayar: dict, isci: int):
    """Kesif kosusu icinde, surec havuzuyla. (satirlar, kesif kaydi alanlari)."""
    satirlar = []
    with split_modulu.kesif_kosusu() as kayit:
        if isci <= 1:
            for s in semboller:
                satirlar += sembol_isi(s, ayar)
        else:
            baglam = multiprocessing.get_context("spawn")
            with concurrent.futures.ProcessPoolExecutor(max_workers=isci, mp_context=baglam,
                                                        max_tasks_per_child=1) as havuz:
                isler = {havuz.submit(sembol_isi, s, ayar): s for s in semboller}
                for is_ in concurrent.futures.as_completed(isler):
                    sembol = isler[is_]
                    try:
                        satirlar += is_.result()
                    except Exception as hata:  # noqa: BLE001
                        satirlar.append({"sembol": sembol, "donem_no": -1, "rol": "HATA", "hata": type(hata).__name__})
                    print(f"bitti: {sembol}", file=sys.stderr, flush=True)
    tablo = pd.DataFrame(satirlar).reindex(columns=SUTUNLAR)
    tablo = tablo.sort_values(["sembol", "donem_no", "hipotez", "yapilandirma", "rol"], kind="stable")
    return tablo.reset_index(drop=True), kayit.alanlar()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--hipotez", nargs="+", default=list(config.HIPOTEZLER), choices=list(config.HIPOTEZLER))
    ap.add_argument("--yapilandirma", choices=("ilk", "hepsi"), default="ilk")
    ap.add_argument("--rol", nargs="+", default=list(ROLLER), choices=list(ROLLER))
    ap.add_argument("--funding-satiri", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--bar", choices=("tum", "ornek", "uyarlamali"), default="uyarlamali")
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--sure-siniri-dk", type=float, default=15.0)
    ap.add_argument("--isci", type=int, default=max(1, (multiprocessing.cpu_count() or 2) - 1))
    ap.add_argument("--sembol", nargs="*", default=None, help="ornegin alt kumesi (varsayilan: butun ornek)")
    ap.add_argument("--etiket", default="p2a")
    arg = ap.parse_args(argv)
    if not agac_temiz():
        print("Calisma agaci temiz degil; esitlik kosusu commit edilmis agacta yapilir.", file=sys.stderr)
        return 2
    ornek = list(pd.read_csv(ORNEK, usecols=["sembol"])["sembol"])
    semboller = ornek if arg.sembol is None else [s for s in ornek if s in set(arg.sembol)]
    ayar = {"hipotezler": arg.hipotez, "yapilandirma": arg.yapilandirma, "roller": arg.rol,
            "funding_satiri": arg.funding_satiri, "bar": arg.bar, "n": arg.n, "sure_siniri_dk": arg.sure_siniri_dk}
    from calistir import csv_yaz, kosu_kilidi

    with kosu_kilidi(f"esitlik_kapi_{arg.etiket}"):
        tablo, kayit = kos(semboller, ayar, arg.isci)
        csv_yaz(tablo, BU_DIZIN / f"esitlik_kapi_{arg.etiket}_tam.csv")
        csv_yaz(pd.DataFrame([kayit]), BU_DIZIN / f"esitlik_kapi_{arg.etiket}_kesif_kaydi_tam.csv")
    karsi = int(tablo["karsilastirilan_bar"].fillna(0).sum())
    uyus = int(tablo["uyusmayan_bar"].fillna(0).sum())
    hata = int((tablo["hata"].fillna("") != "").sum())
    print(f"karsilastirilan bar: {karsi}, uyusmayan bar: {uyus}, hatali birim: {hata}")
    return 0 if (uyus == 0 and hata == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
