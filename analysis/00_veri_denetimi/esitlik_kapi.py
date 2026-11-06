"""Gercek veri esitligi: skaler referans ile bugunku `data/` yolu ayni karari veriyor mu (performans 2a; plan v2 karar 6, D-B5).

Ornek: `esitlik_ornegi.csv` (performans kodundan once sabitlendi; `esitlik_ornegi_sec.py`). Her sembolun evrendeki her
gecerli donemi, KESIF araliginda, istenen hipotez, yapilandirma ve rol kumesinde iki yoldan karara sokulur:
  - yeni: `data.pozisyon.olay_karari` (bugunku yol; P2a ve sonrasinda degisen yol),
  - referans: skaler referansin `olay_karari`si (F2 oncesi skaler yolun dondurulmus kopyasi). Referans modul duzeyinde
    bir adla TUTULMAZ (S-17, RESULTS §14.44): yalnizca karsilastirma fonksiyonlarinin icinde ice aktarilir; bu modulu
    ice aktaran kod referansa bu modul uzerinden adsiz ulasamaz.

Sozlesme (performans 2b-0; denetci D-B2, D-B3, D-C4, D-C7, sizinti S-17, S-18, S-28, S-29):
  - Karsilastirilan (bellekte; hicbir deger, hicbir hata mesaji yazilmaz): sonuc SINIFI, ret MESAJI (`str(hata)`) ve iki
    taraf da onaylarsa `OnaylanmisPozisyon`un butun alanlari (`==`; NaN konumlari dahil, NaN == NaN sayilir).
    `funding_satiri` biriminde: barin plani (iki yoldan kurulur, ayni olmali; ret sinifi ve mesaji dahil), plan varsa
    funding tamlik satirinin butun sutunlari (`Series.equals`) ve funding toplami, uc yeni yoldan (n = 1, tek tamlik,
    toplu cagri).
  - Her birim icin ayri sayilar: `karsilastirilan_bar`, `uyusmayan_bar`, `beklenmeyen_hata_referans`,
    `beklenmeyen_hata_yeni`. "Beklenmeyen hata" = `pencere.OlayOlusmaz` ailesi DISINDAKI her istisna. Iki taraf ayni
    sinifla (ve ayni mesajla) duserse bar uyusmayan sayilmaz, ama iki tarafta da beklenmeyen hata sayilir; "0 uyusmayan"
    tek basina esitlik kaniti degildir. Ilk 20 beklenmeyen hata yalnizca `taraf:Sinif@zaman` olarak yazilir.
  - OLAY ROLUNDE yan kanal yoktur (performans 2b-0 kapanisi, RESULTS §14.46; denetci D-C2, D-C3, sizinti S-39): `sure_s`,
    `ilk_20_uyusmayan` ve `ilk_20_beklenmeyen` bos yazilir (yalnizca sayilar kalir). Onayli bar onaysiz bardan pahali
    oldugu icin birim suresi onay sayisini, uyusmayan / beklenmeyen barin zaman damgasi da olay anini tasiyabilir. Sure
    yalnizca sembol duzeyinde toplam olarak (`TOPLAM_SURE` satiri) yazilir. Uyusmazlik ya da beklenmeyen hata varsa
    betik 1 ile cikar; olay rolunun hata ayiklamasi ayrica ve depo disinda yapilir.
  - `genel_tohum` (D-C4): `config.TOHUM` her satira yazilir (birim tohumu `tohum` ondan turetilir).
  - `kapsam_bar`: K1 ve K2 rollerinde iki tarafin AYNI onayli pozisyonu verdigi bar sayisi; `funding_satiri` biriminde
    planin kurulabildigi bar sayisi. Kontrol rolleri sinyal kosuluna bakmaz (on-kayit §6 rev.12), bu yuzden bu sayi olay
    bilgisi tasimaz. OLAY ROLUNDE bos birakilir: olay rolunde onay sayisi olay sayisidir ve yazilmaz.
  - Bar kipi (`--bar`, zorunlu) acik bir parametredir; sureye gore otomatik secilmez:
      `tum`: donem ∩ KESIF araligindaki butun izgara barlari (4h ya da 1d; seride olmayan bar da sorulur).
      `ornek`: tohumlu `--n` bar + sinir barlari (donemin ilk ve son 200 bari, kume sinirinin +-200 bari, funding ritim
      degisiminin +-20 bari). Tohum kurali `esitlik_ornegi_sec.py` aciklamasindadir.
    Kip (`bar_kumesi`) ve birimin tohumu (`tohum`; `tum` kipinde bos) her satira yazilir.
  - Agac temizligi bu betikte HESAPLANMAZ: `split.kesif_kosusu`nun `KesifKaydi.agac_temiz` degeri kullanilir (bag
    ortami, `ls-files -v` bayraklari ve izlenmeyen dosyalar orada denetlenir). Deger True degilse kosu baslamaz.

H1'in olay rolu capa ister: t barinin capasi, barin izgaradaki sirasi i ile `t - (1 + i mod 12) x 4 saat`tir (sabit, kosula
bakilmadan; boylece karsilastirilan bar sayisi sinyal kosulunun sonucuna bagli degildir ve olay sayisi sizmaz).

Cikti: `esitlik_kapi_<etiket>_tam.csv` (`SUTUNLAR`) ve `esitlik_kapi_<etiket>_kesif_kaydi_tam.csv` (`KesifKaydi.alanlar()`).
`hata` birimin kendisi kurulamadiginda (veri, izgara) yalnizca istisna SINIF adidir. Komut satirina da yalnizca sayilar
ve sinif adlari cikar.

`split.kesif_kosusu` icinde kosar, ag yasagi kosu boyuncadir. Paralellik: surec havuzu kesif kosusunun ICINDE kurulur
(plan_performans_2 §6: isciler kesif baglamini ve ag yasagini devralir). Getiri, sinyal degeri ya da olay sayisi
hesaplanmaz, yazilmaz.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import hashlib
import json
import math
import multiprocessing
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
from data import funding as funding_modulu  # noqa: E402
from data import pencere as pencere_modulu  # noqa: E402
from data import pozisyon as pozisyon_modulu  # noqa: E402
from data import sinyal as sinyal_modulu  # noqa: E402
from data import split as split_modulu  # noqa: E402
from data import universe as universe_modulu  # noqa: E402

ORNEK = BU_DIZIN / "esitlik_ornegi.csv"
SUTUNLAR = ["sembol", "donem_no", "hipotez", "yapilandirma", "rol", "bar_kumesi", "genel_tohum", "tohum",
            "karsilastirilan_bar",
            "uyusmayan_bar", "beklenmeyen_hata_referans", "beklenmeyen_hata_yeni", "kapsam_bar", "ilk_20_uyusmayan",
            "ilk_20_beklenmeyen", "sure_s", "hata"]
SAYI_ALANLARI = ("karsilastirilan_bar", "uyusmayan_bar", "beklenmeyen_hata_referans", "beklenmeyen_hata_yeni")
ROLLER = ("olay", "K1", "K2")
KONTROL_ROLLERI = ("K1", "K2")
FUNDING_SATIRI = "funding_satiri"
BAR_KIPLERI = ("tum", "ornek")
KUME = "KESIF"
H4 = pd.Timedelta(hours=4)
SINIR_DONEM = 200
SINIR_KUME = 200
SINIR_RITIM = 20


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
    """Hata: ayni sinif VE ayni mesaj (mesaj yalnizca bellekte karsilastirilir). Onayli pozisyon (ya da plan): butun
    alanlar, NaN konumlari dahil."""
    if isinstance(a, BaseException) or isinstance(b, BaseException):
        return type(a) is type(b) and str(a) == str(b)
    return _deger_esit(a, b)


def beklenmeyen(sonuc) -> bool:
    """`OlayOlusmaz` ailesi disindaki her istisna beklenmeyen hatadir (D-B2)."""
    return isinstance(sonuc, BaseException) and not isinstance(sonuc, pencere_modulu.OlayOlusmaz)


def _cagir(fonk, *args, **kwargs):
    try:
        return fonk(*args, **kwargs)
    except Exception as hata:  # noqa: BLE001 - sinif ve mesaj yalnizca bellekte karsilastirilir
        return hata


class Sayac:
    """Bir birimin sayilari. Yalnizca sayi, zaman damgasi ve istisna SINIF adi tutar; deger ve mesaj tutmaz."""

    def __init__(self):
        self.karsilastirilan = 0
        self.uyusmayan: list[pd.Timestamp] = []
        self.beklenmeyen_referans = 0
        self.beklenmeyen_yeni = 0
        self.beklenmeyen_ilk: list[str] = []
        self.kapsam = 0

    def bar(self, t, esit: bool, referans_sonuclari=(), yeni_sonuclari=(), kapsam: bool = False) -> None:
        self.karsilastirilan += 1
        if not esit:
            self.uyusmayan.append(t)
        for taraf, sonuclar in (("referans", referans_sonuclari), ("yeni", yeni_sonuclari)):
            hatalar = [s for s in sonuclar if beklenmeyen(s)]
            if hatalar:
                if taraf == "referans":
                    self.beklenmeyen_referans += 1
                else:
                    self.beklenmeyen_yeni += 1
                if len(self.beklenmeyen_ilk) < 20:
                    self.beklenmeyen_ilk.append(f"{taraf}:{type(hatalar[0]).__name__}@{pd.Timestamp(t).isoformat()}")
        if kapsam and esit:
            self.kapsam += 1

    def alanlar(self, kapsam_yazilir: bool, zaman_yazilir: bool = True) -> dict:
        """`kapsam_yazilir=False` ve `zaman_yazilir=False` olay rolu icindir: kapsam ve zaman damgalari bos (§14.46)."""
        return {"karsilastirilan_bar": self.karsilastirilan, "uyusmayan_bar": len(self.uyusmayan),
                "beklenmeyen_hata_referans": self.beklenmeyen_referans, "beklenmeyen_hata_yeni": self.beklenmeyen_yeni,
                "kapsam_bar": self.kapsam if kapsam_yazilir else "",
                "ilk_20_uyusmayan": (";".join(z.isoformat() for z in sorted(self.uyusmayan)[:20])
                                     if zaman_yazilir else ""),
                "ilk_20_beklenmeyen": ";".join(self.beklenmeyen_ilk) if zaman_yazilir else ""}


def _referans_modulu(ref):
    """Verilen referans ya da skaler referans modulu. Modul duzeyinde ad tutulmaz (S-17)."""
    if ref is not None:
        return ref
    from data import _skaler_referans

    return _skaler_referans


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
                ref=None) -> Sayac:
    """Kapi karari: sonuc sinifi, ret mesaji ve onayli pozisyonun butun alanlari. Deger dondurmez."""
    ref = _referans_modulu(ref)
    sayac = Sayac()
    for t, sira in zip(barlar, siralar):
        a = karar(kapi, hipotez, yapilandirma, rol, t, kimlik, sira)
        b = karar(ref, hipotez, yapilandirma, rol, t, kimlik, sira)
        sayac.bar(t, sonuc_esit(a, b), (b,), (a,),
                  kapsam=rol in KONTROL_ROLLERI and isinstance(a, pozisyon_modulu.OnaylanmisPozisyon))
    return sayac


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


def _esit(a, b) -> bool:
    """Funding biriminin parcalari: hata (sinif ve mesaj), satir (`Series.equals`, ayni indeks), toplam (NaN == NaN)."""
    if isinstance(a, BaseException) or isinstance(b, BaseException):
        return sonuc_esit(a, b)
    if isinstance(a, pd.Series) or isinstance(b, pd.Series):
        return (isinstance(a, pd.Series) and isinstance(b, pd.Series) and list(a.index) == list(b.index)
                and a.equals(b))
    return (isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b)) or bool(a == b)


def _satir(tamlik):
    return tamlik if isinstance(tamlik, BaseException) else tamlik.satir


def funding_karsilastir(barlar, hipotez: str, kimlik: dict, *, kapi_funding=funding_modulu, ref=None) -> Sayac:
    """Barin plani iki yoldan kurulur ve ayni olmali; plan varsa funding tamlik satiri (butun sutunlar) ve toplam.

    Uc yeni yol referansla karsilastirilir (P2a, D-C6): genel n = 1 yolu (`pozisyon_funding_ayrintisi`, `_plan_fundingi`),
    kapinin tek tamlik yolu (`_pozisyon_tamlik_satiri` + `_satirdan_toplam`) ve toplu yol (bar kumesindeki butun
    planlar TEK cagrida, `_planlar_tamlik_satirlari`). Bir barda uclerinden biri ayrisirsa bar uyusmayandir. Her cagri
    ayri yakalanir: bir tarafin beklenmeyen hatasi o barda o tarafa sayilir."""
    ref = _referans_modulu(ref)
    m, fr, sinirlar = _veri(kimlik)
    zamanlar = pd.DatetimeIndex(m["open_time"])
    bar_sonucu = {}   # t -> (esit, referans sonuclari, yeni sonuclari, plan kuruldu mu)
    planli = []
    for t in barlar:
        pa, pb = _plan(pencere_modulu, zamanlar, t, hipotez, sinirlar), _plan(ref, zamanlar, t, hipotez, sinirlar)
        esit, ref_sonuc, yeni_sonuc = sonuc_esit(pa, pb), [pb], [pa]
        kuruldu = not isinstance(pa, BaseException) and not isinstance(pb, BaseException)
        if esit and kuruldu:
            ref_satir = _cagir(ref.pozisyon_funding_ayrintisi, fr, pa)
            ref_toplam = _cagir(ref._plan_fundingi, fr, pa)
            tek = _cagir(kapi_funding._pozisyon_tamlik_satiri, fr, pa)
            tek_toplam = tek if isinstance(tek, BaseException) else _cagir(kapi_funding._satirdan_toplam, fr, pa, tek)
            genel_satir = _cagir(kapi_funding.pozisyon_funding_ayrintisi, fr, pa)
            genel_toplam = _cagir(kapi_funding._plan_fundingi, fr, pa)
            ref_sonuc += [ref_satir, ref_toplam]
            yeni_sonuc += [genel_satir, genel_toplam, _satir(tek), tek_toplam]
            esit = (_esit(genel_satir, ref_satir) and _esit(genel_toplam, ref_toplam)
                    and _esit(_satir(tek), ref_satir) and _esit(tek_toplam, ref_toplam))
            if not any(isinstance(x, BaseException) for x in (ref_satir, ref_toplam)):
                planli.append((t, pa, ref_satir, ref_toplam))
        bar_sonucu[t] = [esit, ref_sonuc, yeni_sonuc, kuruldu]
    if planli:
        toplu = _cagir(kapi_funding._planlar_tamlik_satirlari, fr, [p for _, p, _, _ in planli])
        for k, (t, plan, ref_satir, ref_toplam) in enumerate(planli):
            tamlik = toplu if isinstance(toplu, BaseException) else toplu[k]
            toplam = tamlik if isinstance(tamlik, BaseException) else _cagir(kapi_funding._satirdan_toplam, fr, plan,
                                                                              tamlik)
            bar_sonucu[t][2] += [_satir(tamlik), toplam]
            if not (_esit(_satir(tamlik), ref_satir) and _esit(toplam, ref_toplam)):
                bar_sonucu[t][0] = False
    sayac = Sayac()
    for t in barlar:
        esit, ref_sonuc, yeni_sonuc, kuruldu = bar_sonucu[t]
        sayac.bar(t, esit, ref_sonuc, yeni_sonuc, kapsam=kuruldu)
    return sayac


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


def _kos(birim, izgara, siralar, hipotez, y, kimlik) -> Sayac:
    barlar = [izgara[i] for i in siralar]
    if birim == FUNDING_SATIRI:
        return funding_karsilastir(barlar, hipotez, kimlik)
    return karsilastir(barlar, siralar, hipotez, y, birim, kimlik)


def _bos_satir(sembol, donem_no, hipotez, yk, rol) -> dict:
    return {"sembol": sembol, "donem_no": donem_no, "hipotez": hipotez, "yapilandirma": yk, "rol": rol,
            "bar_kumesi": "", "genel_tohum": config.TOHUM, "tohum": "", "karsilastirilan_bar": 0, "uyusmayan_bar": 0, "beklenmeyen_hata_referans": 0,
            "beklenmeyen_hata_yeni": 0, "kapsam_bar": "", "ilk_20_uyusmayan": "", "ilk_20_beklenmeyen": "",
            "sure_s": 0.0, "hata": ""}


def sembol_isi(sembol: str, ayar: dict) -> list[dict]:
    """Bir sembolun butun donemleri, hipotezleri, yapilandirmalari ve rolleri. Yalnizca sayi, zaman damgasi ve sinif adi
    doner. Bar kipi `ayar["bar"]` acik parametredir (`tum` ya da `ornek`); sureye gore secilmez."""
    kip = ayar["bar"]
    if kip not in BAR_KIPLERI:
        raise ValueError(f"bar kipi {BAR_KIPLERI} degerlerinden biri olmali.")
    satirlar = []
    bas_sure = time.perf_counter()
    for donem_no in _donemler(sembol):
        kimlik = {"sembol": sembol, "donem_no": donem_no}
        for hipotez in ayar["hipotezler"]:
            izgara_y = list(sinyal_modulu.izgara(hipotez))
            yapilandirmalar = izgara_y[:1] if ayar["yapilandirma"] == "ilk" else izgara_y
            for y in yapilandirmalar:
                yk = sinyal_modulu.yapilandirma_kimligi(hipotez, y)
                for birim in _birim_etiketleri(ayar["roller"], ayar["funding_satiri"]):
                    t0 = time.perf_counter()
                    satir = _bos_satir(sembol, donem_no, hipotez, yk, birim)
                    try:
                        izgara = bar_izgarasi(kimlik, hipotez)
                        if kip == "tum":
                            siralar = list(range(len(izgara)))
                            satir["bar_kumesi"] = "tum"
                        else:
                            birim_tohumu = tohum(sembol, donem_no, hipotez, yk, birim)
                            sec = tohumlu_siralar(len(izgara), ayar["n"], birim_tohumu)
                            siralar = sorted(sec | sinir_siralari(izgara, kimlik))
                            satir["bar_kumesi"] = f"ornek_{ayar['n']}+sinir"
                            satir["tohum"] = str(birim_tohumu)
                        sayac = _kos(birim, izgara, siralar, hipotez, y, kimlik)
                        satir.update(sayac.alanlar(kapsam_yazilir=birim != "olay", zaman_yazilir=birim != "olay"))
                    except Exception as hata:  # noqa: BLE001 - yalnizca sinif adi yazilir, mesaj yazilmaz
                        satir["hata"] = type(hata).__name__
                    # Olay rolunde birim suresi yazilmaz (S-39, D-C2): yalnizca sembol toplami (TOPLAM_SURE).
                    satir["sure_s"] = "" if birim == "olay" else round(time.perf_counter() - t0, 1)
                    satirlar.append(satir)
    toplam = _bos_satir(sembol, -1, "", "", "TOPLAM_SURE")
    toplam.update(bar_kumesi=kip, sure_s=round(time.perf_counter() - bas_sure, 1))
    satirlar.append(toplam)
    return satirlar


def _guvenli_sembol_isi(sembol: str, ayar: dict) -> list[dict]:
    """`sembol_isi`; birim disinda (donem listesi, ayar) dusen hata yalnizca sinif adiyla tek satir olur (S-18)."""
    try:
        return sembol_isi(sembol, ayar)
    except Exception as hata:  # noqa: BLE001 - yalnizca sinif adi
        satir = _bos_satir(sembol, -1, "", "", "HATA")
        satir["hata"] = type(hata).__name__
        return [satir]


def _ara_dizin_dogrula(ara_dizin) -> Path | None:
    """Ara kayit dizini depo DISINDA olmali (calisma agaci temiz kalir; kesilmis veri yazilmaz, yalnizca sayilar)."""
    if ara_dizin is None:
        return None
    yol = Path(ara_dizin).resolve()
    if yol == KOK or KOK in yol.parents:
        raise SystemExit("--ara-dizin depo disinda olmali (calisma agaci temiz kalir).")
    yol.mkdir(parents=True, exist_ok=True)
    return yol


class AgacTemizDegil(SystemExit):
    """Kesif kaydi calisma agacini temiz bulmadi; esitlik kosusu commit edilmis agacta yapilir."""


def kos(semboller, ayar: dict, isci: int, ara_dizin: Path | None = None):
    """Kesif kosusu icinde, surec havuzuyla. (satirlar, kesif kaydi alanlari listesi).

    Agac temizligi `KesifKaydi.agac_temiz`ten okunur (S-28, S-29, D-C7): betik ikinci bir uygulama tasimaz. Deger True
    degilse hicbir sembol kosmadan `AgacTemizDegil` (SystemExit) firlatilir.

    `ara_dizin` verilirse her biten sembolun satirlari oraya yazilir (`<sembol>.json`: satirlar, HEAD, ayar) ve sonraki
    kosu ayni HEAD ve ayni ayarla kaydi olan sembolleri atlar (kesilen kosunun kaldigi yerden devami). Farkli HEAD ya da
    ayarla yazilmis ara kayit hata verir; karisik sonuc birlestirilmez. Her kosunun kesif kaydi `kayitlar.jsonl`ye
    eklenir ve cikti kayit dosyasina hepsi yazilir."""
    satirlar = []
    with split_modulu.kesif_kosusu() as kayit:
        alanlar = kayit.alanlar()
        if alanlar.get("agac_temiz") is not True:
            raise AgacTemizDegil("Kesif kaydi calisma agacini temiz bulmadi; esitlik kosusu commit edilmis agacta "
                                 "yapilir.")
        head = alanlar["head_commit"]
        kalan = list(semboller)
        if ara_dizin is not None:
            kalan = []
            for s in semboller:
                yol = ara_dizin / f"{s}.json"
                if not yol.exists():
                    kalan.append(s)
                    continue
                onceki = json.loads(yol.read_text(encoding="utf-8"))
                if onceki["head_commit"] != head or onceki["ayar"] != ayar:
                    raise SystemExit(f"{yol.name}: ara kayit baska bir HEAD ya da ayarla yazilmis; birlestirilmez.")
                satirlar += onceki["satirlar"]

        def kaydet(s, sonuc):
            if ara_dizin is not None:
                (ara_dizin / f"{s}.json").write_text(
                    json.dumps({"head_commit": head, "ayar": ayar, "satirlar": sonuc}), encoding="utf-8")

        if isci <= 1:
            for s in kalan:
                sonuc = _guvenli_sembol_isi(s, ayar)
                kaydet(s, sonuc)
                satirlar += sonuc
                print(f"bitti: {s}", file=sys.stderr, flush=True)
        elif kalan:
            baglam = multiprocessing.get_context("spawn")
            with concurrent.futures.ProcessPoolExecutor(max_workers=isci, mp_context=baglam,
                                                        max_tasks_per_child=1) as havuz:
                isler = {havuz.submit(_guvenli_sembol_isi, s, ayar): s for s in kalan}
                for is_ in concurrent.futures.as_completed(isler):
                    sembol = isler[is_]
                    try:
                        sonuc = is_.result()
                        kaydet(sembol, sonuc)
                    except Exception as hata:  # noqa: BLE001 - yalnizca sinif adi
                        sonuc = [_bos_satir(sembol, -1, "", "", "HATA") | {"hata": type(hata).__name__}]
                    satirlar += sonuc
                    print(f"bitti: {sembol}", file=sys.stderr, flush=True)
    kayitlar = [kayit.alanlar()]
    if ara_dizin is not None:
        with (ara_dizin / "kayitlar.jsonl").open("a", encoding="utf-8") as d:
            d.write(json.dumps(kayit.alanlar(), default=str) + "\n")
        kayitlar = [json.loads(x) for x in (ara_dizin / "kayitlar.jsonl").read_text(encoding="utf-8").splitlines() if x]
    tablo = pd.DataFrame(satirlar).reindex(columns=SUTUNLAR)
    tablo = tablo.sort_values(["sembol", "donem_no", "hipotez", "yapilandirma", "rol"], kind="stable")
    return tablo.reset_index(drop=True), kayitlar


def ozet(tablo: pd.DataFrame) -> dict:
    """Komut satiri ozeti: yalnizca sayilar."""
    sayilar = {a: int(pd.to_numeric(tablo[a], errors="coerce").fillna(0).sum()) for a in SAYI_ALANLARI}
    sayilar["hatali_birim"] = int((tablo["hata"].fillna("") != "").sum())
    return sayilar


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bar", choices=BAR_KIPLERI, required=True, help="bar kipi; sureye gore secilmez (D-B3, D-C4)")
    ap.add_argument("--hipotez", nargs="+", default=list(config.HIPOTEZLER), choices=list(config.HIPOTEZLER))
    ap.add_argument("--yapilandirma", choices=("ilk", "hepsi"), default="ilk")
    ap.add_argument("--rol", nargs="+", default=list(ROLLER), choices=list(ROLLER))
    ap.add_argument("--funding-satiri", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--isci", type=int, default=max(1, (multiprocessing.cpu_count() or 2) - 1))
    ap.add_argument("--sembol", nargs="*", default=None, help="ornegin alt kumesi (varsayilan: butun ornek)")
    ap.add_argument("--etiket", default="p2a")
    ap.add_argument("--ara-dizin", default=None, help="depo disinda ara kayit dizini (kesilen kosunun devami)")
    arg = ap.parse_args(argv)
    ara_dizin = _ara_dizin_dogrula(arg.ara_dizin)
    ornek = list(pd.read_csv(ORNEK, usecols=["sembol"])["sembol"])
    semboller = ornek if arg.sembol is None else [s for s in ornek if s in set(arg.sembol)]
    ayar = {"hipotezler": arg.hipotez, "yapilandirma": arg.yapilandirma, "roller": arg.rol,
            "funding_satiri": arg.funding_satiri, "bar": arg.bar, "n": arg.n}
    from calistir import csv_yaz, kosu_kilidi

    try:
        with kosu_kilidi(f"esitlik_kapi_{arg.etiket}"):
            tablo, kayitlar = kos(semboller, ayar, arg.isci, ara_dizin)
            csv_yaz(tablo, BU_DIZIN / f"esitlik_kapi_{arg.etiket}_tam.csv")
            csv_yaz(pd.DataFrame(kayitlar), BU_DIZIN / f"esitlik_kapi_{arg.etiket}_kesif_kaydi_tam.csv")
    except AgacTemizDegil:
        print("Calisma agaci temiz degil (kesif kaydi); esitlik kosusu commit edilmis agacta yapilir.", file=sys.stderr)
        return 2
    except Exception as hata:  # noqa: BLE001 - S-18: mesaj yazilmaz, yalnizca sinif adi
        hata = type(hata).__name__
        print(f"kosu dustu: {hata}", file=sys.stderr)
        return 3
    sayilar = ozet(tablo)
    karsi, uyus = sayilar["karsilastirilan_bar"], sayilar["uyusmayan_bar"]
    hata = sayilar["beklenmeyen_hata_referans"] + sayilar["beklenmeyen_hata_yeni"] + sayilar["hatali_birim"]
    print(f"karsilastirilan bar: {karsi}, uyusmayan bar: {uyus}, beklenmeyen hata (iki taraf) + hatali birim: {hata} "
          "(ayrintisi CSV'de)")
    return 0 if (uyus == 0 and hata == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
