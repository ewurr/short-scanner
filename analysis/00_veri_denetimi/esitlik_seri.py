"""Gercek veri deger esitligi: vektorel seri kuruculari ile skaler referans, her barda BIT DUZEYINDE (performans 2b-1).

Plan v3 G6 ve G14'un P2b-1 parcasi; RESULTS §14.48. Kapiya baglanmadan once seri kurucularinin (`data.seri_kurucu`)
gercek veride skaler referansla ayni degerleri verdigini gosterir. Kapi karari bu betigin konusu DEGILDIR (P2b-2).

Ornek: `esitlik_ornegi.csv` (8 sembol). Her sembolun KESIF araligindaki her gecerli donemi, her hipotezin ILK
yapilandirmasi, hipotez izgarasi yardimcisinin (`pozisyon.hipotez_izgarasi_barlari`, G20) BUTUN barlari. Veri kapinin
bugunku veri yolundan okunur (`pozisyon._karar_verisi`); seri kuruculari ve referans AYNI cerceveleri alir.

Karsilastirilan degerler (bar basina, bellekte; iki taraf da NaN ya da 64 bitlik temsiller ayni):
  - sinyal pencereleri: H1 `dip`, `hacim_6`, `hacim_medyani_180`, `kapanis`, `yuksek`, `tepe`; H2 `kirilim_dip`,
    `kapanis_30_once`, `funding_24s`, `kapanis`, `yuksek_30_max`; H3 `hacim_medyani_30g`, `hacim_medyani_120_31`,
    `sma50`, `kapanis_30_once`, `kapanis`, `yuksek_30_max`;
  - capasiz pencere hesaplanabilirligi (`capasiz_hesaplanabilir`, bool);
  - uygunluk: `uygunluk_medyan_hacim` (t'nin gunu), `uygunluk_listeleme_yasi`, `uygun` (bool).
H1'in tepesi capa ister: t barinin capasi `esitlik_kapi.py` ile ayni sabit kuraldir, `t - (1 + i mod 12) x 4 saat`
(i = barin izgaradaki sirasi; kosula bakilmaz). Bu karsilastirma ROL ICERMEZ; sinyal KOSULU karsilastirilmaz.

Hata yolu (G10): referansin bir barda yukselttigi `OlayOlusmaz` disi istisna `beklenmeyen_hata_referans`a sayilir. Seri
kurucusu yukseltirse bu BIRIM hatasidir (`hata` = sinif adi) ve referansta ayni birimde en az bir beklenmeyen hata
bulunmalidir; bulunmazsa birimin butun barlari uyusmayan sayilir.

Cikti (`esitlik_seri_<etiket>_tam.csv`): sembol, donem, hipotez, yapilandirma, deger adi, karsilastirilan bar sayisi,
uyusmayan bar sayisi, iki taraftaki beklenmeyen hata sayisi, birim hatasi sinif adi; `bar_kumesi` (`tum`), genel tohum,
numpy ve pandas surumleri. DEGER YAZILMAZ, uyusmayan barin zamani yazilmaz, sure yazilmaz; olay rolune ozgu hicbir sey
yoktur. Ayrica kesif kaydi (`esitlik_seri_<etiket>_kesif_kaydi_tam.csv`).

`split.kesif_kosusu` icinde, temiz agacta kosar (agac temizligi `KesifKaydi.agac_temiz`ten). Paralellik: surec havuzu
kesif kosusunun ICINDE kurulur. Uyusmazlik ya da hata varsa 1 ile cikar. Analiz kodu taramasinda bu dosya acik adiyla
istisnadir (`tests/tarama_yardimcisi.SERI_KURUCU_IZINLI_DOSYALAR`, `SKALER_REFERANS_IZINLI_DOSYALAR`).
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import multiprocessing
import sys
from pathlib import Path

import numpy as np
import pandas as pd

KOK = Path(__file__).resolve().parents[2]
BU_DIZIN = Path(__file__).resolve().parent
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(BU_DIZIN))

import config  # noqa: E402
from data import pencere as pencere_modulu  # noqa: E402
from data import pozisyon as pozisyon_modulu  # noqa: E402
from data import seri_kurucu as seri_modulu  # noqa: E402
from data import sinyal as sinyal_modulu  # noqa: E402
from data import split as split_modulu  # noqa: E402
from data import universe as universe_modulu  # noqa: E402

ORNEK = BU_DIZIN / "esitlik_ornegi.csv"
KUME = "KESIF"
H4 = pd.Timedelta(hours=4)
SUTUNLAR = ["sembol", "donem_no", "hipotez", "yapilandirma", "deger", "bar_kumesi", "genel_tohum", "numpy_surumu",
            "pandas_surumu", "karsilastirilan_bar", "uyusmayan_bar", "beklenmeyen_hata_referans", "hata"]
SAYI_ALANLARI = ("karsilastirilan_bar", "uyusmayan_bar", "beklenmeyen_hata_referans")

DEGERLER = {
    "H1": ("dip", "hacim_6", "hacim_medyani_180", "kapanis", "yuksek", "tepe"),
    "H2": ("kirilim_dip", "kapanis_30_once", "funding_24s", "kapanis", "yuksek_30_max"),
    "H3": ("hacim_medyani_30g", "hacim_medyani_120_31", "sma50", "kapanis_30_once", "kapanis", "yuksek_30_max"),
}
ORTAK = ("capasiz_hesaplanabilir", "uygunluk_medyan_hacim", "uygunluk_listeleme_yasi", "uygun")


# --- Karsilastirma -------------------------------------------------------------------------------------------

def ayni(a, b) -> bool:
    """Bit duzeyinde esitlik: ikisi de NaN ya da 64 bitlik temsiller ayni. Bool degerler `is`/`==` ile."""
    if isinstance(a, (bool, np.bool_)) or isinstance(b, (bool, np.bool_)):
        return isinstance(a, (bool, np.bool_)) and isinstance(b, (bool, np.bool_)) and bool(a) == bool(b)
    a, b = float(a), float(b)
    return (np.isnan(a) and np.isnan(b)) or np.float64(a).view(np.int64) == np.float64(b).view(np.int64)


def _beklenmeyen(hata) -> bool:
    return isinstance(hata, BaseException) and not isinstance(hata, pencere_modulu.OlayOlusmaz)


def _skaler(fonk):
    try:
        return fonk()
    except Exception as hata:  # noqa: BLE001 - yalnizca sinif sayilir; mesaj yazilmaz
        return hata


def h1_capalari(izgara: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """`esitlik_kapi.h1_capasi` ile ayni sabit kural (kosula bakilmaz)."""
    return pd.DatetimeIndex([t - (1 + i % config.H1_IZLEME_BAR) * H4 for i, t in enumerate(izgara)])


def _esikler(bar: str) -> dict:
    hacim = config.ASGARI_HACIM_4H if bar == config.BAR_4H else config.ASGARI_HACIM_1D
    return {"asgari_hacim": hacim, "asgari_listeleme_yasi_gun": config.ASGARI_LISTELEME_YASI_GUN}


def seri_degerleri(seri, hipotez: str, y, izgara, m4, fr, g, sinirlar) -> dict[str, np.ndarray]:
    """Seri kurucularinin bir birimdeki butun degerleri (ad -> dizi). Hata yukseltirse cagiran birim hatasi sayar."""
    kb, ks, bas, bitis = sinirlar
    s = {"kume_baslangic": kb, "donem_baslangic": bas}
    bar = pencere_modulu.hipotez_izgarasi(hipotez)
    k = y["k"] if hipotez == "H2" else None
    capasiz = seri.capasiz_pencereler(hipotez, k, izgara, mumlar_4h=m4, gunluk=g, funding=fr, kume_bitis=ks, **s)
    d = {}
    if hipotez == "H1":
        d.update(capasiz)
        d["kapanis"] = seri.kapanis(m4, izgara, bar)
        d["yuksek"] = seri.yuksek(m4, izgara, bar)
        d["tepe"] = seri.h1_tepe(m4, h1_capalari(izgara), izgara, **s)
    elif hipotez == "H2":
        d.update(capasiz)
        d["kapanis"] = seri.kapanis(m4, izgara, bar)
        d["yuksek_30_max"] = seri.yuksek_30_max(m4, izgara, bar, **s)
    else:
        d.update(capasiz)
        d["kapanis"] = seri.kapanis(g, izgara, bar)
        d["yuksek_30_max"] = seri.yuksek_30_max(g, izgara, bar, **s)
    d["capasiz_hesaplanabilir"] = seri.capasiz_hesaplanabilir(hipotez, capasiz)
    u = seri.uygunluk(g, izgara, bar, donem_baslangic=bas, donem_bitis=bitis, kume_baslangic=kb, **_esikler(bar))
    d["uygunluk_medyan_hacim"] = u["medyan_hacim"].to_numpy()
    d["uygunluk_listeleme_yasi"] = u["listeleme_yasi_gun"].to_numpy()
    d["uygun"] = u["uygun"].to_numpy()
    return d


def referans_degerleri(ref, hipotez: str, y, t, capa, m4, fr, g, gh, sinirlar) -> dict:
    """Referansin bir bardaki butun degerleri; her deger ayri cagrilir (hata yalnizca o degeri etkiler)."""
    kb, ks, bas, bitis = sinirlar
    s = {"kume_baslangic": kb, "donem_baslangic": bas}
    bar = pencere_modulu.hipotez_izgarasi(hipotez)
    capasiz = _skaler(lambda: ref.capasiz_pencere_degerleri(hipotez, y, t, mumlar_4h=m4, gunluk=g, funding=fr,
                                                            kume_bitis=ks, **s))
    d = {}
    for ad in seri_modulu.CAPASIZ_PENCERELER[hipotez]:
        d[ad] = capasiz if isinstance(capasiz, BaseException) else capasiz[ad]
    d["capasiz_hesaplanabilir"] = capasiz if isinstance(capasiz, BaseException) else \
        not ref.capasiz_hesaplanamayan(hipotez, capasiz)
    cerceve = g if hipotez == "H3" else m4
    d["kapanis"] = _skaler(lambda: ref.bar_degeri(cerceve, t, "close"))
    if hipotez == "H1":
        d["yuksek"] = _skaler(lambda: ref.bar_degeri(m4, t, "high"))
        d["tepe"] = _skaler(lambda: ref.h1_tepe(m4, capa, t, **s))
    else:
        d["yuksek_30_max"] = _skaler(lambda: ref.yuksek_30_max(cerceve, t, bar, **s))
    d["uygunluk_medyan_hacim"] = _skaler(lambda: ref.medyan_hacim(gh, t, donem_baslangic=bas, kume_baslangic=kb,
                                                                  pencere_gun=config.HACIM_PENCERESI_GUN))
    d["uygunluk_listeleme_yasi"] = _skaler(lambda: ref.listeleme_yasi_gun(bas, t))
    d["uygun"] = _skaler(lambda: ref.uygunluk_karari(gh, t, bar, donem_baslangic=bas, donem_bitis=bitis,
                                                     kume_baslangic=kb, **_esikler(bar)))
    return d


def birim_karsilastir(hipotez: str, y, izgara, m4, fr, g, sinirlar, *, seri=seri_modulu, ref=None) -> dict[str, dict]:
    """Bir (sembol, donem, hipotez, yapilandirma) biriminin deger adi basina sayilari. Deger DONDURMEZ.

    Doner: ad -> {karsilastirilan_bar, uyusmayan_bar, beklenmeyen_hata_referans, hata}."""
    if ref is None:
        from data import _skaler_referans as ref  # modul duzeyinde ad tutulmaz (esitlik_kapi S-17 ile ayni)
    adlar = DEGERLER[hipotez] + ORTAK
    try:
        vektor, birim_hatasi = seri_degerleri(seri, hipotez, y, izgara, m4, fr, g, sinirlar), ""
    except Exception as hata:  # noqa: BLE001 - G10: birim hatasi, yalnizca sinif adi
        vektor, birim_hatasi = None, type(hata).__name__
    gh = ref._gunluk_hacim(g)
    capalar = h1_capalari(izgara)
    sayi = {ad: {"karsilastirilan_bar": 0, "uyusmayan_bar": 0, "beklenmeyen_hata_referans": 0, "hata": birim_hatasi}
            for ad in adlar}
    for i, t in enumerate(izgara):
        r = referans_degerleri(ref, hipotez, y, t, capalar[i] if hipotez == "H1" else None, m4, fr, g, gh, sinirlar)
        for ad in adlar:
            sayi[ad]["karsilastirilan_bar"] += 1
            if _beklenmeyen(r[ad]):
                sayi[ad]["beklenmeyen_hata_referans"] += 1
                if vektor is not None:
                    sayi[ad]["uyusmayan_bar"] += 1      # referans hata verdi, seri deger verdi
            elif vektor is not None and not ayni(vektor[ad][i], r[ad]):
                sayi[ad]["uyusmayan_bar"] += 1
    if vektor is None:
        # G10: seri duzeyindeki hata, referansta ayni birimde en az bir beklenmeyen hata yoksa uyusmazliktir.
        if sum(v["beklenmeyen_hata_referans"] for v in sayi.values()) == 0:
            for v in sayi.values():
                v["uyusmayan_bar"] = v["karsilastirilan_bar"]
    return sayi


# --- Kosu ----------------------------------------------------------------------------------------------------

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


def _bos_satir(sembol, donem_no, hipotez, yk, deger) -> dict:
    return {"sembol": sembol, "donem_no": donem_no, "hipotez": hipotez, "yapilandirma": yk, "deger": deger,
            "bar_kumesi": "tum", "genel_tohum": config.TOHUM, "numpy_surumu": np.__version__,
            "pandas_surumu": pd.__version__, "karsilastirilan_bar": 0, "uyusmayan_bar": 0,
            "beklenmeyen_hata_referans": 0, "hata": ""}


def sembol_isi(sembol: str, hipotezler) -> list[dict]:
    satirlar = []
    kb, ks = pozisyon_modulu.kume_sinirlari(KUME)
    for donem_no in _donemler(sembol):
        kimlik = {"sembol": sembol, "donem_no": donem_no}
        bas, bitis, _ = pozisyon_modulu.donem_kaydi(sembol, donem_no)
        m4, fr, g = pozisyon_modulu._karar_verisi(sembol, KUME, kume_baslangic=kb, kume_bitis=ks,
                                                 donem_baslangic=bas, donem_bitis=bitis)
        for hipotez in hipotezler:
            y = sinyal_modulu.izgara(hipotez)[0]
            yk = sinyal_modulu.yapilandirma_kimligi(hipotez, y)
            try:
                izgara = pozisyon_modulu.hipotez_izgarasi_barlari(hipotez, kume=KUME, **kimlik)
                sayi = birim_karsilastir(hipotez, y, izgara, m4, fr, g, (kb, ks, bas, bitis))
            except Exception as hata:  # noqa: BLE001 - yalnizca sinif adi
                satirlar.append(_bos_satir(sembol, donem_no, hipotez, yk, "HATA") | {"hata": type(hata).__name__})
                continue
            for ad, v in sayi.items():
                satirlar.append(_bos_satir(sembol, donem_no, hipotez, yk, ad) | v)
    return satirlar


def _guvenli_sembol_isi(sembol: str, hipotezler) -> list[dict]:
    try:
        return sembol_isi(sembol, hipotezler)
    except Exception as hata:  # noqa: BLE001 - yalnizca sinif adi
        return [_bos_satir(sembol, -1, "", "", "HATA") | {"hata": type(hata).__name__}]


class AgacTemizDegil(SystemExit):
    """Kesif kaydi calisma agacini temiz bulmadi."""


def kos(semboller, hipotezler, isci: int):
    satirlar = []
    with split_modulu.kesif_kosusu() as kayit:
        if kayit.alanlar().get("agac_temiz") is not True:
            raise AgacTemizDegil("Kesif kaydi calisma agacini temiz bulmadi.")
        if isci <= 1:
            for s in semboller:
                satirlar += _guvenli_sembol_isi(s, hipotezler)
                print(f"bitti: {s}", file=sys.stderr, flush=True)
        else:
            baglam = multiprocessing.get_context("spawn")
            with concurrent.futures.ProcessPoolExecutor(max_workers=isci, mp_context=baglam,
                                                        max_tasks_per_child=1) as havuz:
                isler = {havuz.submit(_guvenli_sembol_isi, s, hipotezler): s for s in semboller}
                for is_ in concurrent.futures.as_completed(isler):
                    sembol = isler[is_]
                    try:
                        satirlar += is_.result()
                    except Exception as hata:  # noqa: BLE001 - yalnizca sinif adi
                        satirlar.append(_bos_satir(sembol, -1, "", "", "HATA") | {"hata": type(hata).__name__})
                    print(f"bitti: {sembol}", file=sys.stderr, flush=True)
    tablo = pd.DataFrame(satirlar).reindex(columns=SUTUNLAR)
    tablo = tablo.sort_values(["sembol", "donem_no", "hipotez", "deger"], kind="stable").reset_index(drop=True)
    return tablo, [kayit.alanlar()]


def ozet(tablo: pd.DataFrame) -> dict:
    sayilar = {a: int(pd.to_numeric(tablo[a], errors="coerce").fillna(0).sum()) for a in SAYI_ALANLARI}
    sayilar["hatali_birim"] = int((tablo["hata"].fillna("") != "").sum())
    return sayilar


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--hipotez", nargs="+", default=list(config.HIPOTEZLER), choices=list(config.HIPOTEZLER))
    ap.add_argument("--isci", type=int, default=max(1, (multiprocessing.cpu_count() or 2) - 1))
    ap.add_argument("--sembol", nargs="*", default=None, help="ornegin alt kumesi (varsayilan: butun ornek)")
    ap.add_argument("--etiket", default="p2b1")
    arg = ap.parse_args(argv)
    ornek = list(pd.read_csv(ORNEK, usecols=["sembol"])["sembol"])
    semboller = ornek if arg.sembol is None else [s for s in ornek if s in set(arg.sembol)]
    from calistir import csv_yaz, kosu_kilidi

    try:
        with kosu_kilidi(f"esitlik_seri_{arg.etiket}"):
            tablo, kayitlar = kos(semboller, arg.hipotez, arg.isci)
            csv_yaz(tablo, BU_DIZIN / f"esitlik_seri_{arg.etiket}_tam.csv")
            csv_yaz(pd.DataFrame(kayitlar), BU_DIZIN / f"esitlik_seri_{arg.etiket}_kesif_kaydi_tam.csv")
    except AgacTemizDegil:
        print("Calisma agaci temiz degil (kesif kaydi); esitlik kosusu commit edilmis agacta yapilir.", file=sys.stderr)
        return 2
    except Exception as hata:  # noqa: BLE001 - mesaj yazilmaz, yalnizca sinif adi
        print(f"kosu dustu: {type(hata).__name__}", file=sys.stderr)
        return 3
    sayilar = ozet(tablo)
    print(json.dumps(sayilar))
    print(f"karsilastirilan bar-deger: {sayilar['karsilastirilan_bar']}, uyusmayan: {sayilar['uyusmayan_bar']}, "
          f"beklenmeyen hata (referans): {sayilar['beklenmeyen_hata_referans']}, hatali birim: "
          f"{sayilar['hatali_birim']} (ayrintisi CSV'de)")
    temiz = sayilar["uyusmayan_bar"] == 0 and sayilar["beklenmeyen_hata_referans"] == 0 and sayilar["hatali_birim"] == 0
    return 0 if temiz else 1


if __name__ == "__main__":
    raise SystemExit(main())
