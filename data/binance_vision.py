"""data.binance.vision ortak erisim katmani.

Yalnizca herkese acik uc noktalar kullanilir; API anahtari yoktur (CLAUDE.md §1).

Bu modul dort isi yapar:
  1. S3 bucket listeleme (sayfalamali),
  2. zip + .CHECKSUM indirme ve SHA256 dogrulama,
  3. zip icindeki CSV'yi DataFrame'e cevirme (basliksiz eski dosyalar dahil),
  4. parquet onbellek (cache/, git'e girmez).

Dogrulanmis varsayimlar (F1 §1 denemeleri, 2026-09-11):
  - Aylik mum yolu : data/futures/um/monthly/klines/<SEMBOL>/<BAR>/<SEMBOL>-<BAR>-<YYYY-MM>.zip
  - Aylik funding  : data/futures/um/monthly/fundingRate/<SEMBOL>/<SEMBOL>-fundingRate-<YYYY-MM>.zip
  - Her zip'in yaninda ayni adla .CHECKSUM (SHA256) dosyasi bulunur.
  - 2020 tarihli mum dosyalarinda basli satiri YOKTUR, yeni dosyalarda VARDIR.
  - Delist edilmis sozlesmelerin dosyalari bucket'ta durmaya devam eder.
"""

from __future__ import annotations

import hashlib
import io
import os
import re
import threading
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests

import config

# S3 listeleme ancak bolge uc noktasi uzerinden yapilabilir; indirme CDN'den.
LISTELEME_KOKU = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
INDIRME_KOKU = "https://data.binance.vision"
S3_NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"

MUM_ONEKI = "data/futures/um/monthly/klines"
FUNDING_ONEKI = "data/futures/um/monthly/fundingRate"

# Mum CSV sutunlari (basliksiz dosyalarda bu sira varsayilir).
MUM_SUTUNLARI = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "count",
    "taker_buy_volume",
    "taker_buy_quote_volume",
    "ignore",
]

FUNDING_SUTUNLARI = ["calc_time", "funding_interval_hours", "last_funding_rate"]

# Oturum is parcacigina ozeldir: tam indirmede sinirli eszamanlilik kullanilir
# ve requests.Session parcaciklar arasinda paylasilmaya uygun degildir.
_YEREL = threading.local()


class VeriYok(Exception):
    """Istenen dosya kaynakta bulunmuyor (404)."""


# --- 0) Onay verisi okuma izni (onay kaydi kapanisinin son turu) --------------
#
# Onbellek ve indirme yardimcilari kume kapisi tasimaz. Onay verisi (B grubu sembollerin her ayi ve butun
# sembollerin C2 donemindeki aylari; on-kayit §3) bu yardimcilarla YALNIZCA acik bir izin baglaminda okunur:
#   - kume kapisindan (`split.kume_erisimi`) gecmis yukleyiciler: `split.yukle`, `funding.funding_yukle`,
#     `klines.birincil_gunluk_indir` (veriyi ardindan kume araligina keserler);
#   - evren kurulumu (`universe`) ve F1 veri denetimi betikleri (`analysis/00_veri_denetimi`; CLAUDE.md §3.1:
#     kapsama ve butunluk denetimi serbesttir).
# Izin disinda onay verisi okuma denemesi `OnayVerisiKorumasi` verir; boylece analiz kodunda kolaylik icin yazilan
# `bv.onbellekten_oku(...)` ya da `klines.ham_mumlari_yukle(...)` kazayla onay verisi okuyamaz. `onay_verisi_izni`
# adi analiz kodunda taramayla yasaktir (`tests/tarama_yardimcisi.ONBELLEK_DESENI`). Izin surec genelidir (is
# parcaciklari gorur: F1 denetimi paralel indirir) ve baglam icinde baslatilan alt sureclere ortam degiskeniyle
# tasinir (asagidaki not; `ProcessPoolExecutor` kullanan F1 betikleri); kasitli bir atlatma (izni analiz kodunda
# acmak, `_IZIN`i ya da ortam degiskenini degistirmek) taramaya takilir ya da kodda gorunur.


class OnayVerisiKorumasi(PermissionError):
    """Onay verisi (B grubu ya da C2 donemi) izin baglami disinda onbellekten ya da kaynaktan okunmak istendi."""


_IZIN_KILIDI = threading.Lock()
_IZIN = {"sayac": 0}
_ONBELLEK_TURLERI = ("klines", "funding", "klines_birincil_1d")  # <tur>/<SEMBOL>/.../<YYYY-MM>.parquet

# Izin alt sureclere tasinir (denetci OK4 D-B1): F1 denetim betiklerinin yedisi `ProcessPoolExecutor` kullanir ve
# Windows'ta isci surecler `spawn` ile bastan baslar; surec icinde tutulan sayac onlara gecmez, isci icindeki ham
# yukleme `OnayVerisiKorumasi` ile duserdi. Izin bu yuzden ortam degiskeniyle de tasinir: baglam acilirken
# `SHORT_LAB_ONAY_VERISI_IZNI` acan surecin pid'ine ayarlanir, baglam kapanirken eski degerine doner. Yeni surec
# (spawn ortami devralir) import aninda degiskeni gorur ve DEGER KENDI UST SURECININ pid'i ise izni devralir;
# devralan surec degeri kendi pid'iyle gunceller, boylece torun surecler de devralir.
#
# Pid denetimi, kabukta elle ayarlanmis ya da bayat bir degiskenin korumayi tumden kapatmasini onler; kararli bir
# atlatmayi (degiskeni kendi kabuk pid'iyle ayarlayip betik calistirmak) onlemez. Degiskenin adi analiz kodunda
# taramayla yasaktir (`tests/tarama_yardimcisi.ONBELLEK_DESENI`).
_IZIN_ORTAM_ADI = "SHORT_LAB_ONAY_VERISI_IZNI"
_DEVRALINAN_IZIN = {"var": False}


def _izni_devral() -> None:
    """Import aninda bir kez: ust surec izin baglami icinde bu sureci baslattiysa izni devralir. Yan etkili."""
    deger = os.environ.get(_IZIN_ORTAM_ADI)
    if not deger:
        return
    try:
        acan = int(deger)
    except ValueError:
        return
    if acan != os.getppid():  # bayat ya da elle ayarlanmis degisken
        return
    _DEVRALINAN_IZIN["var"] = True
    os.environ[_IZIN_ORTAM_ADI] = str(os.getpid())  # torun surecler de devralsin


class onay_verisi_izni:  # noqa: N801  (baglam yoneticisi; `with bv.onay_verisi_izni("neden"):`)
    """Onay verisinin okunmasina izin veren baglam. YALNIZCA veri katmani (kapidan gecmis yukleyiciler, evren
    kurulumu) ve F1 veri denetimi icindir; analiz kodunda taramayla yasaktir. Baglam icinde baslatilan alt
    surecler izni devralir (yukaridaki not)."""

    def __init__(self, neden: str):
        if not isinstance(neden, str) or not neden.strip():
            raise ValueError("onay_verisi_izni bir neden ister.")
        self.neden = neden
        self._onceki_ortam = None

    def __enter__(self):
        with _IZIN_KILIDI:
            _IZIN["sayac"] += 1
            if _IZIN["sayac"] == 1:
                self._onceki_ortam = os.environ.get(_IZIN_ORTAM_ADI)
                os.environ[_IZIN_ORTAM_ADI] = str(os.getpid())
        return self

    def __exit__(self, *_):
        with _IZIN_KILIDI:
            _IZIN["sayac"] -= 1
            if _IZIN["sayac"] == 0:
                if self._onceki_ortam is None:
                    os.environ.pop(_IZIN_ORTAM_ADI, None)
                else:
                    os.environ[_IZIN_ORTAM_ADI] = self._onceki_ortam
        return False


_izni_devral()  # import aninda: bu surec bir izin baglami icinde baslatildiysa izin devralinir


def onay_verisi_mi(sembol: str, ay: str) -> bool:
    """(sembol, ay) onay verisi mi: ay C2 doneminde (`config.C2_BASI` ve sonrasi) ya da sembol B grubunda (on-kayit
    §3 bolme kurali, varlik anahtariyla). Ay ayristirilamazsa True (kapali yon). Saf."""
    from data import split  # split bu katmani dolayli import eder; dongu onlenir

    try:
        donem = pd.Period(ay, freq="M")
    except (ValueError, TypeError):
        return True
    if donem >= pd.Period(config.C2_BASI.strftime("%Y-%m"), freq="M"):
        return True
    return split.grup(split.varlik_anahtari(sembol)) == "B"


def _onay_verisi_denetle(sembol: str, ay: str, kaynak: str) -> None:
    if _IZIN["sayac"] > 0 or _DEVRALINAN_IZIN["var"] or not onay_verisi_mi(sembol, ay):
        return
    raise OnayVerisiKorumasi(
        f"{kaynak}: {sembol} {ay} onay verisidir (B grubu ya da C2 donemi); onbellek ve indirme yardimcilari onu "
        "yalnizca kume kapisindan gecen yukleyicilerle (`klines.mumlari_yukle`, `funding.funding_yukle`; C1/C2 icin "
        "acik bir `split.onay_kosusu` icinde) okur (CLAUDE.md §3.2-3.3).")


def _anahtar_denetle(anahtar: str) -> None:
    """Bucket anahtari `data/futures/um/<monthly|daily>/<tur>/<SEMBOL>/...<YYYY-MM>...zip` ise (sembol, ay) denetlenir;
    ay dosya adindaki ilk `YYYY-MM`dir (gunluk dosyalar dahil). `data/` ile baslayip bu bicime uymayan anahtar onay
    verisi sayilir (kapali yon). `data/` ile baslamayan anahtar bucket anahtari degildir; denetlenmez."""
    if not anahtar.startswith("data/"):
        return
    parcalar = anahtar.split("/")
    ay = re.search(r"\d{4}-\d{2}", parcalar[-1])
    if len(parcalar) < 7 or parcalar[:3] != ["data", "futures", "um"] or ay is None:
        _onay_verisi_denetle("", "", f"zip_indir({anahtar})")
        return
    _onay_verisi_denetle(parcalar[5], ay.group(0), f"zip_indir({anahtar})")


def _onbellek_yolu_denetle(yol: Path) -> None:
    """Onbellek yolundan (tur, sembol, ay) cikarir ve denetler. `klines_settled` her zaman onay verisi sayilir (yalnizca
    denetim). Onbellek disi ya da tanimsiz turdeki yollar (ör. evren onbellegi) denetlenmez."""
    try:
        parcalar = Path(yol).resolve().relative_to(Path(config.ONBELLEK_DIZINI).resolve()).parts
    except ValueError:
        return
    if not parcalar:
        return
    if parcalar[0] == "klines_settled":
        _onay_verisi_denetle("", "", f"onbellekten_oku({yol})")
    elif parcalar[0] in _ONBELLEK_TURLERI and len(parcalar) >= 3:
        _onay_verisi_denetle(parcalar[1], Path(parcalar[-1]).stem, f"onbellekten_oku({yol})")


def _oturum() -> requests.Session:
    oturum = getattr(_YEREL, "oturum", None)
    if oturum is None:
        oturum = requests.Session()
        oturum.headers["User-Agent"] = "short-lab/1.0 (arastirma; yalnizca okuma)"
        _YEREL.oturum = oturum
    return oturum


def _iste(url: str, deneme: int = 5, bekleme: float = 2.0) -> requests.Response:
    """Ustel geri cekilmeli GET.

    data.binance.vision yogun istekte baglantiyi kapatiyor (RemoteDisconnected),
    bu yuzden yeniden deneme zorunlu. 404 yeniden denenmez.
    """
    son_hata: Exception | None = None
    for i in range(deneme):
        try:
            cevap = _oturum().get(url, timeout=60)
            if cevap.status_code == 404:
                raise VeriYok(url)
            cevap.raise_for_status()
            return cevap
        except VeriYok:
            raise
        except Exception as hata:  # aglar gecici olarak kopabilir
            son_hata = hata
            if i < deneme - 1:
                time.sleep(bekleme * (2**i))
    raise RuntimeError(f"Indirme basarisiz: {url}") from son_hata


# --- 1) Listeleme ------------------------------------------------------------


def _listele(onek: str, ayirici: str) -> tuple[list[str], list[str]]:
    """Bir onek altindaki alt dizinleri ve dosya anahtarlarini sayfalamayla toplar."""
    jeton: str | None = None
    alt_dizinler: list[str] = []
    anahtarlar: list[str] = []
    while True:
        url = f"{LISTELEME_KOKU}?list-type=2&prefix={onek}&max-keys=1000"
        if ayirici:
            url += f"&delimiter={ayirici}"
        if jeton:
            url += "&continuation-token=" + requests.utils.quote(jeton, safe="")
        kok = ET.fromstring(_iste(url).text)
        alt_dizinler += [e.find(S3_NS + "Prefix").text for e in kok.findall(S3_NS + "CommonPrefixes")]
        anahtarlar += [e.find(S3_NS + "Key").text for e in kok.findall(S3_NS + "Contents")]
        if kok.find(S3_NS + "IsTruncated").text == "true":
            jeton = kok.find(S3_NS + "NextContinuationToken").text
        else:
            return alt_dizinler, anahtarlar


def tum_sembol_dizinleri() -> list[str]:
    """Bucket'ta mum dizini bulunan tum sembol adlari (delist olanlar dahil)."""
    alt_dizinler, _ = _listele(f"{MUM_ONEKI}/", ayirici="/")
    return sorted(p.rstrip("/").rsplit("/", 1)[-1] for p in alt_dizinler)


def mum_dosyalari(sembol: str, bar: str) -> list[str]:
    """Bir sembol/bar icin aylik zip anahtarlari, ay sirasinda."""
    _, anahtarlar = _listele(f"{MUM_ONEKI}/{sembol}/{bar}/", ayirici="")
    return sorted(a for a in anahtarlar if a.endswith(".zip"))


def funding_dosyalari(sembol: str) -> list[str]:
    """Bir sembol icin aylik funding zip anahtarlari, ay sirasinda."""
    _, anahtarlar = _listele(f"{FUNDING_ONEKI}/{sembol}/", ayirici="")
    return sorted(a for a in anahtarlar if a.endswith(".zip"))


def dosya_ayi(anahtar: str) -> str:
    """`.../SEMBOL-4h-2024-05.zip` -> `2024-05`."""
    ad = anahtar.rsplit("/", 1)[-1].removesuffix(".zip")
    return "-".join(ad.split("-")[-2:])


# --- 2) Indirme ve checksum --------------------------------------------------


def zip_indir(anahtar: str, checksum_dogrula: bool = True) -> bytes:
    """Zip'i indirir ve yanindaki .CHECKSUM ile SHA256 dogrulamasi yapar. Onay verisi izin disinda indirilemez
    (`OnayVerisiKorumasi`; anahtar `data/futures/um/monthly/<tur>/<SEMBOL>/...-<YYYY-MM>.zip`)."""
    _anahtar_denetle(anahtar)
    govde = _iste(f"{INDIRME_KOKU}/{anahtar}").content
    if checksum_dogrula:
        beklenen = _iste(f"{INDIRME_KOKU}/{anahtar}.CHECKSUM").text.split()[0].strip()
        bulunan = hashlib.sha256(govde).hexdigest()
        if bulunan != beklenen:
            raise ValueError(f"Checksum tutmadi: {anahtar} ({bulunan} != {beklenen})")
    return govde


# --- 3) Ayristirma -----------------------------------------------------------


def zip_csv_oku(govde: bytes, sutunlar: list[str]) -> pd.DataFrame:
    """Zip icindeki tek CSV'yi okur.

    Eski dosyalarda basli satiri yoktur, yenilerinde vardir; ilk hucre sayiya
    cevrilebiliyorsa basli yok kabul edilir.
    """
    with zipfile.ZipFile(io.BytesIO(govde)) as zf:
        ham = zf.read(zf.namelist()[0])
    ilk_satir = ham.split(b"\n", 1)[0].decode("utf-8", "replace")
    ilk_hucre = ilk_satir.split(",", 1)[0].strip()
    baslikli = not _sayi_mi(ilk_hucre)
    cerceve = pd.read_csv(
        io.BytesIO(ham),
        header=0 if baslikli else None,
        names=None if baslikli else sutunlar,
    )
    if baslikli:
        cerceve.columns = [str(c).strip() for c in cerceve.columns]
    return cerceve


def _sayi_mi(metin: str) -> bool:
    try:
        float(metin)
        return True
    except ValueError:
        return False


# --- 4) Parquet onbellek -----------------------------------------------------


def onbellek_yolu(*parcalar: str) -> Path:
    yol = config.ONBELLEK_DIZINI.joinpath(*parcalar)
    yol.parent.mkdir(parents=True, exist_ok=True)
    return yol


def onbellekten_oku(yol: Path) -> pd.DataFrame | None:
    """Onbellek dosyasini okur. Onay verisi izin disinda okunamaz (`OnayVerisiKorumasi`)."""
    _onbellek_yolu_denetle(yol)
    if yol.exists():
        return pd.read_parquet(yol)
    return None


def onbellege_yaz(cerceve: pd.DataFrame, yol: Path) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    # Gecici ad benzersizdir: sinirli eszamanlilikta ayni yolu iki parcacik
    # yazmaya kalkarsa birbirinin yarim dosyasini gormemeli.
    gecici = yol.with_suffix(f"{yol.suffix}.{os.getpid()}.{threading.get_ident()}.tmp")
    cerceve.to_parquet(gecici, index=False)
    gecici.replace(yol)  # yarim dosya birakmamak icin atomik degistirme


def ay_araligi(bas: str, son: str) -> Iterable[str]:
    """`2020-01`..`2020-04` gibi kapali ay araligi uretir."""
    baslangic = pd.Period(bas, freq="M")
    bitis = pd.Period(son, freq="M")
    su_an = baslangic
    while su_an <= bitis:
        yield str(su_an)
        su_an += 1
