"""Onbellek manifesti: dondurulmus verinin iki katmanli kaydi (on-kayit §3 rev.13; RESULTS §14.41, denetci D-B2).

"Koşu dondurulmuş yerel önbellekten okur" hukmunun denetlenebilir hali. Depo herkese aciktir; onay dosyalarinin yolu
C1/C2 ay adlarini, boyu kaba bir etkinlik olcusunu verir. Bu yuzden iki katman vardir:

  - `data/onbellek_manifest.csv` (depoda): kesif dosyalari (A grubu, C2 oncesi) icin yol, boy, SHA256; `liste.json`
    icin yalnizca SHA256 (boyu bilerek yazilmaz, ay adi sayisini kabaca verir); onay dosyalari icin TEK SATIR: dosya
    sayisi ve birlesik SHA256.
  - `cache/manifest/onay_ayrintisi.tsv` (git'e girmez): onay dosyalari icin yol, boy, SHA256. Yalnizca onay verisi
    izniyle okunur. Metni kanoniktir (yola gore sirali `yol<TAB>boy<TAB>sha256` satirlari, UTF-8, LF) ve birlesik SHA256
    bu metnin ozetidir; depodaki tek satir boylece yerel listeye baglanir.

Dogrulama iki katmanlidir. `katman="kesif"` hicbir onay dosyasini acmaz ve boyuna bakmaz, yalnizca adina gore eler; F2
acilisinda bu cagrilir (`split.kesif_kosusu`). `katman="tam"` onay izni ister, onay kosusu acilisinda cagrilir ve
uyusmazlikta dosyayi adiyla soyler (`split.onay_kosusu`); hata mesajinda onay dosyasinin boyu ya da ozeti yazilmaz.

Baytlar `hashlib` ile ham okunur, parquet olarak acilmaz; bu modulun hicbir yolu cerceve ya da bayt dondurmez. Onay
katmani F1'de bir kez kurulur (on-kayit satir 123 "keşif sırasında" der, F1 kesif degildir; CLAUDE.md §3.1 kapsama
denetimini serbest birakir). Sonrasinda yalnizca acik bir onay kosusu icinde yeniden kurulabilir. `liste.json`'in ve
manifestin her degisikligi git gecmisinde gorunur.

Ad analiz kodunda taramayla yasaktir (`tests/tarama_yardimcisi.ONBELLEK_DESENI`).
"""

from __future__ import annotations

import csv
import hashlib
import io
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import config
from data import binance_vision as bv

MANIFEST_YOLU = Path(config.VERI_DIZINI) / "onbellek_manifest.csv"
_SUTUNLAR = ["katman", "yol", "boy", "sha256", "dosya_sayisi"]
_KATMANLAR = ("kesif", "tam")
_LISTE_GORELI = "/".join(bv._LISTE_ALT_YOLU)
_ISCI = 8


class ManifestHatasi(RuntimeError):
    """Manifest kaydi ile yerel onbellek birlikte kullanilamiyor."""


class ManifestYok(ManifestHatasi):
    """Manifest ya da onay ayrinti listesi yok. Sessizce atlanmaz, sessizce indirilmez."""


class ManifestUyusmazligi(ManifestHatasi):
    """Yerel dosya kayitla tutmuyor ya da okunmak istenen dosya kayitta yok."""


class OnayKatmaniKilitli(PermissionError):
    """Onay katmani F1'de kurulduktan sonra acik bir onay kosusu disinda yeniden kurulmak istendi."""


# --- Test ayari (yalnizca pytest) --------------------------------------------------------------------------------
#
# Takimin sentetik onbellek kullanan testleri manifest tasimaz. pytest icinde denetim yalnizca testin kendi manifestini
# kurdugu testte calisir; pytest disinda her zaman calisir ve yol `MANIFEST_YOLU`dur. `config.ONBELLEK_DIZINI` baska bir
# dizine yonlendirilirse denetim atlanmaz: goreli yollar yeni dizinde aranir ve tutmaz.
_TEST_AYARI: tuple[str, Path] | None = None


def _test_manifest_ayarla(yol) -> Path:
    """YALNIZCA TESTLER ICIN: bu pytest testi suresince manifest denetimi acilir ve `yol`a yonlenir."""
    global _TEST_AYARI
    from data import split

    test = split._pytest_testi()
    if test is None:
        raise bv.OnayVerisiKorumasi("Manifest test ayari yalnizca bir pytest testi icinde yapilabilir.")
    _TEST_AYARI = (test, Path(yol))
    return Path(yol)


def _etkin_yol() -> Path | None:
    from data import split

    test = split._pytest_testi()
    if test is None:
        return MANIFEST_YOLU
    return _TEST_AYARI[1] if _TEST_AYARI is not None and _TEST_AYARI[0] == test else None


def denetim_etkin() -> bool:
    return _etkin_yol() is not None


# --- Kanonik bicim ve dosya gezme ----------------------------------------------------------------------------------


def onay_ayrinti_yolu() -> Path:
    return Path(config.ONBELLEK_DIZINI) / "manifest" / "onay_ayrintisi.tsv"


def kanonik_metin(satirlar: dict[str, tuple[int, str]]) -> bytes:
    """Onay ayrinti listesinin kanonik metni: yola gore sirali, UTF-8, LF. Saf."""
    return "".join(f"{yol}\t{satirlar[yol][0]}\t{satirlar[yol][1]}\n" for yol in sorted(satirlar)).encode("utf-8")


def _onay_dosyasi_mi(goreli: str) -> bool:
    """`<tur>/<SEMBOL>/.../<YYYY-MM>.parquet` onay verisi mi. Bicime uymayan yol onay sayilir (kapali yon)."""
    parcalar = goreli.split("/")
    return len(parcalar) < 3 or bv.onay_verisi_mi(parcalar[1], Path(parcalar[-1]).stem)


def _dosyalari_gez():
    """(goreli yol, onay mi). Yalnizca dizin girdilerinin adlarina bakar: dosya acilmaz, boyu okunmaz."""
    kok = Path(config.ONBELLEK_DIZINI)
    for tur in bv._ONBELLEK_TURLERI:
        for dizin, _, adlar in os.walk(kok / tur):
            goreli_dizin = Path(dizin).relative_to(kok).as_posix()
            for ad in adlar:
                if ad.endswith(".parquet"):
                    goreli = f"{goreli_dizin}/{ad}"
                    yield goreli, _onay_dosyasi_mi(goreli)


def _sha256(yol: Path) -> str:
    ozet = hashlib.sha256()
    with open(yol, "rb") as dosya:
        for parca in iter(lambda: dosya.read(1 << 20), b""):
            ozet.update(parca)
    return ozet.hexdigest()


def _boy_ve_ozet(goreli: str) -> tuple[int, str]:
    yol = Path(config.ONBELLEK_DIZINI) / goreli
    return yol.stat().st_size, _sha256(yol)


def _kayitlar(gorelier: list[str]) -> dict[str, tuple[int, str]]:
    with ThreadPoolExecutor(max_workers=_ISCI) as havuz:
        return dict(zip(gorelier, havuz.map(_boy_ve_ozet, gorelier)))


# --- Manifest dosyasi ------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Manifest:
    kesif: dict[str, tuple[int, str]]
    liste_sha256: str
    onay_sayisi: int
    onay_sha256: str


_BELLEK: dict = {}


def bellek_temizle() -> None:
    """Manifest ve onay ayrinti listesinin bellek kopyalari duser (`bv.donuk_bellek_temizle` cagirir)."""
    _BELLEK.clear()


def _manifest_coz(metin: str) -> _Manifest:
    okuyucu = csv.DictReader(io.StringIO(metin))
    if okuyucu.fieldnames != _SUTUNLAR:
        raise ManifestUyusmazligi(f"Manifest sutunlari {_SUTUNLAR} olmali: {okuyucu.fieldnames}")
    kesif, listeler, ozetler = {}, [], []
    for satir in okuyucu:
        if satir["katman"] == "kesif":
            kesif[satir["yol"]] = (int(satir["boy"]), satir["sha256"])
        elif satir["katman"] == "liste":
            listeler.append(satir)
        elif satir["katman"] == "onay_ozeti":
            ozetler.append(satir)
        else:
            raise ManifestUyusmazligi(f"Manifestte bilinmeyen katman: {satir['katman']!r}")
    if len(listeler) != 1 or len(ozetler) != 1:
        raise ManifestUyusmazligi(f"Manifestte tek liste ve tek onay ozeti satiri olmali: {len(listeler)}, {len(ozetler)}.")
    return _Manifest(kesif, listeler[0]["sha256"], int(ozetler[0]["dosya_sayisi"]), ozetler[0]["sha256"])


def _manifest() -> _Manifest:
    yol = _etkin_yol()
    if yol is None:
        raise ManifestYok("pytest icinde manifest yalnizca `_test_manifest_ayarla` ile kullanilir.")
    try:
        bilgi = yol.stat()
    except FileNotFoundError:
        raise ManifestYok(f"Manifest yok: {yol}. Once `python -m data.onbellek_manifest manifest-kur` calistirilmali "
                          "(on-kayit §3 rev.13).") from None
    kimlik = (str(yol), bilgi.st_mtime_ns, bilgi.st_size)
    if _BELLEK.get("manifest_kimlik") != kimlik:
        _BELLEK.update(manifest_kimlik=kimlik, manifest=_manifest_coz(yol.read_text(encoding="utf-8")))
    return _BELLEK["manifest"]


def _onay_listesi(manifest: _Manifest) -> dict[str, tuple[int, str]]:
    """Onay ayrinti listesi. Her cagrida onay verisi izni aranir (on-kayit satir 123: bellekteki kopya dahil). Liste bu
    surecte ilk okundugunda ve dosya degistiginde metninin ozeti depodaki satirla karsilastirilir."""
    if not bv.onay_izni_var():
        raise bv.OnayVerisiKorumasi("Onay ayrinti listesi yalnizca onay verisi izniyle okunur (CLAUDE.md §3.3).")
    yol = onay_ayrinti_yolu()
    try:
        bilgi = yol.stat()
    except FileNotFoundError:
        raise ManifestYok(f"Onay ayrinti listesi yok: {yol}.") from None
    kimlik = (str(yol), bilgi.st_mtime_ns, bilgi.st_size, manifest.onay_sha256)
    if _BELLEK.get("onay_kimlik") != kimlik:
        govde = yol.read_bytes()
        if hashlib.sha256(govde).hexdigest() != manifest.onay_sha256:
            raise ManifestUyusmazligi("Onay ayrinti listesi depodaki birlesik SHA256 ile tutmuyor (ozet uyusmazligi).")
        satirlar = {}
        for satir in govde.decode("utf-8").splitlines():
            goreli, boy, sha = satir.split("\t")
            satirlar[goreli] = (int(boy), sha)
        if len(satirlar) != manifest.onay_sayisi:
            raise ManifestUyusmazligi("Onay ayrinti listesinin satir sayisi depodaki dosya sayisiyla tutmuyor.")
        _BELLEK.update(onay_kimlik=kimlik, onay=satirlar)
    return _BELLEK["onay"]


def _atomik_yaz(yol: Path, govde: bytes) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_suffix(f".{os.getpid()}.tmp")
    gecici.write_bytes(govde)
    gecici.replace(yol)


def _manifest_metni(kesif: dict[str, tuple[int, str]], liste_sha256: str, onay_sayisi: int, onay_sha256: str) -> bytes:
    cikti = io.StringIO(newline="")
    yazici = csv.writer(cikti, lineterminator="\n")
    yazici.writerow(_SUTUNLAR)
    satirlar = [("kesif", y, kesif[y][0], kesif[y][1], "") for y in kesif]
    satirlar.append(("liste", _LISTE_GORELI, "", liste_sha256, ""))
    yazici.writerows(sorted(satirlar, key=lambda s: s[1]))
    yazici.writerow(("onay_ozeti", "", "", onay_sha256, onay_sayisi))
    return cikti.getvalue().encode("utf-8")


# --- Kurulum ---------------------------------------------------------------------------------------------------------


def _gecmiste_var(yol: Path) -> bool:
    """Manifest git gecmisinde var mi. Git okunamazsa True (kapali yon): ilk kurulum sayilmaz."""
    from data import split

    try:
        goreli = yol.resolve().relative_to(split._depo().resolve()).as_posix()
    except ValueError:
        return False  # depo disi yol yalnizca testte olur (`_test_manifest_ayarla`)
    cikti = split._git("log", "--all", "--reflog", "--format=%H", "--", goreli)
    return cikti is None or bool(cikti.strip())


def manifest_kur(uzerine_yaz: bool = False, onay_katmani: bool = False) -> dict:
    """Manifesti kurar; yalnizca sayi ve ozet dondurur.

    - Ilk kurulum (manifest ve ayrinti listesi yok, manifest git gecmisinde de yok): iki katman kurulur. Onay baytlari
      izinle ve yalnizca `hashlib` ile okunur.
    - Var olan dosyanin uzerine yalnizca `uzerine_yaz=True` ile yazilir. Varsayilan yalnizca kesif katmanini ve
      `liste.json` ozetini yeniler; onay satiri oldugu gibi tasinir ve hicbir onay dosyasi acilmaz.
    - `onay_katmani=True` yalnizca acik bir onay kosusu icinde gecerlidir. Kosu acilisi `tam` dogrulamasindan gectigi
      icin bu yol bozulmus bir onay dosyasini aklayamaz.
    """
    from data import split

    bas = time.perf_counter()
    yol = _etkin_yol()
    if yol is None:
        raise ManifestYok("pytest icinde manifest yalnizca `_test_manifest_ayarla` ile kurulur.")
    ayrinti = onay_ayrinti_yolu()
    var = yol.exists() or ayrinti.exists()
    if var and not uzerine_yaz:
        raise FileExistsError(f"{yol.name} ya da onay ayrinti listesi zaten var; dondurma kaydi sessizce yenilenmez.")
    ilk = not var and not _gecmiste_var(yol)
    if not ilk and (onay_katmani or not yol.exists()) and split.aktif_onay_kosusu() is None:
        raise OnayKatmaniKilitli("Onay katmani F1'de kuruldu; yalnizca acik bir onay kosusu icinde yeniden kurulur "
                                 "(on-kayit §3, RESULTS §14.41).")
    dosyalar = sorted(_dosyalari_gez())
    kesif = _kayitlar([g for g, onay in dosyalar if not onay])
    liste_sha256 = _sha256(bv.donuk_liste_yolu()) if bv.donuk_liste_yolu().exists() else None
    if liste_sha256 is None:
        raise bv.DonukListeYok(f"Dondurulmus S3 listesi yok: {bv.donuk_liste_yolu()}.")
    if ilk or onay_katmani:
        with bv.onay_verisi_izni("onbellek_manifest.manifest_kur"):
            onay = _kayitlar([g for g, onay_mu in dosyalar if onay_mu])
        govde = kanonik_metin(onay)
        onay_sayisi, onay_sha256 = len(onay), hashlib.sha256(govde).hexdigest()
        _atomik_yaz(ayrinti, govde)
    else:
        onceki = _manifest()
        onay_sayisi, onay_sha256 = onceki.onay_sayisi, onceki.onay_sha256
    metin = _manifest_metni(kesif, liste_sha256, onay_sayisi, onay_sha256)
    _atomik_yaz(yol, metin)
    bellek_temizle()
    return {"kesif_satir": len(kesif), "kesif_bayt": sum(k[0] for k in kesif.values()), "onay_dosya": onay_sayisi,
            "birlesik_sha256": onay_sha256, "liste_sha256": liste_sha256,
            "manifest_sha256": hashlib.sha256(metin).hexdigest(), "sure_sn": round(time.perf_counter() - bas, 2)}


# --- Dogrulama -------------------------------------------------------------------------------------------------------


def _bildir(sorunlar: list[str], katman: str) -> None:
    if sorunlar:
        raise ManifestUyusmazligi(f"Manifest dogrulamasi ({katman}): {len(sorunlar)} sorun: "
                                  + "; ".join(sorted(sorunlar)[:5]))


def _kesif_sorunlari(manifest: _Manifest, disk: set[str]) -> list[str]:
    kok = Path(config.ONBELLEK_DIZINI)
    sorunlar = [f"{g} manifestte yok" for g in disk - manifest.kesif.keys()]
    sorunlar += [f"{g} diskte yok" for g in manifest.kesif.keys() - disk]

    def denetle(goreli: str) -> str | None:
        boy, sha = manifest.kesif[goreli]
        yol = kok / goreli
        bulunan = yol.stat().st_size
        if bulunan != boy:
            return f"{goreli} boyu tutmuyor ({bulunan} != {boy})"
        return None if _sha256(yol) == sha else f"{goreli} SHA256 tutmuyor"

    with ThreadPoolExecutor(max_workers=_ISCI) as havuz:
        sorunlar += [s for s in havuz.map(denetle, sorted(disk & manifest.kesif.keys())) if s]
    liste = bv.donuk_liste_yolu()
    if not liste.exists():
        sorunlar.append(f"{_LISTE_GORELI} diskte yok")
    elif _sha256(liste) != manifest.liste_sha256:
        sorunlar.append(f"{_LISTE_GORELI} SHA256 tutmuyor")
    return sorunlar


def _onay_sorunlari(manifest: _Manifest, disk: set[str]) -> list[str]:
    """Mesajlar dosyanin adini ve nedenini soyler; boyu ve ozeti yazmaz."""
    liste = _onay_listesi(manifest)
    kok = Path(config.ONBELLEK_DIZINI)
    sorunlar = [f"{g} ayrinti listesinde yok" for g in disk - liste.keys()]
    sorunlar += [f"{g} diskte yok" for g in liste.keys() - disk]

    def denetle(goreli: str) -> str | None:
        boy, sha = liste[goreli]
        yol = kok / goreli
        if yol.stat().st_size != boy:
            return f"{goreli} boyu tutmuyor"
        return None if _sha256(yol) == sha else f"{goreli} SHA256 tutmuyor"

    with ThreadPoolExecutor(max_workers=_ISCI) as havuz:
        sorunlar += [s for s in havuz.map(denetle, sorted(disk & liste.keys())) if s]
    return sorunlar


def manifest_dogrula(*, katman: str) -> dict:
    """`kesif`: kesif satirlari ve `liste.json`; onay dosyasi acilmaz. `tam`: ek olarak onay katmani; onay verisi izni
    ister (`OnayVerisiKorumasi`). Uyusmazlikta `ManifestUyusmazligi`. Yalnizca sayi dondurur."""
    if katman not in _KATMANLAR:
        raise ValueError(f"katman {_KATMANLAR} degerlerinden biri olmali: {katman!r}")
    if katman == "tam" and not bv.onay_izni_var():
        raise bv.OnayVerisiKorumasi("`tam` dogrulamasi yalnizca onay verisi izniyle calisir (CLAUDE.md §3.3).")
    bas = time.perf_counter()
    manifest = _manifest()
    dosyalar = list(_dosyalari_gez())
    _bildir(_kesif_sorunlari(manifest, {g for g, onay in dosyalar if not onay}), katman)
    if katman == "tam":
        _bildir(_onay_sorunlari(manifest, {g for g, onay in dosyalar if onay}), katman)
    return {"katman": katman, "kesif_satir": len(manifest.kesif), "kesif_bayt": sum(k[0] for k in manifest.kesif.values()),
            "onay_dosya": manifest.onay_sayisi, "sure_sn": round(time.perf_counter() - bas, 2)}


def okuma_denetle(yol: Path) -> None:
    """Agsiz yolda parquet okunmadan once: dosya kayitta olmali, boyu tutmali. Onay dosyasi icin mesaj adi yazmaz, cunku
    bu yol KESIF yuklemesinde de calisir (RESULTS §14.41); adi `tam` dogrulamasi soyler."""
    if not denetim_etkin():
        return
    try:
        parcalar = Path(yol).resolve().relative_to(Path(config.ONBELLEK_DIZINI).resolve()).parts
    except ValueError:
        return
    if not parcalar or parcalar[0] not in bv._ONBELLEK_TURLERI:
        return
    goreli = "/".join(parcalar)
    manifest = _manifest()
    onay = _onay_dosyasi_mi(goreli)
    satir = (_onay_listesi(manifest) if onay else manifest.kesif).get(goreli)
    try:
        boy = Path(yol).stat().st_size
    except FileNotFoundError:
        boy = None
    if satir is not None and boy == satir[0]:
        return
    if onay:
        raise ManifestUyusmazligi("Okunmak istenen bir onay dosyasi ayrinti listesinde yok ya da boyu tutmuyor; dosya "
                                  "okunmadi. Ad burada yazilmaz; `tam` dogrulamasi adiyla soyler.")
    raise ManifestUyusmazligi(f"{goreli} manifestte yok ya da boyu tutmuyor; dosya okunmadi, indirilmedi "
                              "(on-kayit §3 rev.13).")


def _ana(argumanlar: list[str]) -> int:
    if argumanlar[:1] == ["manifest-kur"] and not set(argumanlar[1:]) - {"--uzerine-yaz"}:
        sonuc = manifest_kur(uzerine_yaz="--uzerine-yaz" in argumanlar)
    elif argumanlar[:2] == ["manifest-dogrula", "--katman"] and argumanlar[2:] == ["kesif"]:
        sonuc = manifest_dogrula(katman="kesif")
    elif argumanlar[:2] == ["manifest-dogrula", "--katman"] and argumanlar[2:] == ["tam"]:
        # Faz kapisi (RESULTS §14.42, denetci D-C2): `tam` yalnizca acik bir onay kosusu icinde calisir. F1'deki kurulum
        # dogrulamasi yapildi (§14.41); komut satiri ayri bir surec oldugu icin pratikte her zaman reddedilir.
        from data import split

        if split.aktif_onay_kosusu() is None:
            raise OnayKatmaniKilitli("`manifest-dogrula --katman tam` yalnizca acik bir onay kosusu icinde calisir "
                                     "(RESULTS §14.42, denetci D-C2). Onay kosusu acilisi `tam`i kendisi cagirir.")
        with bv.onay_verisi_izni("onbellek_manifest komut satiri (acik onay kosusu)"):
            sonuc = manifest_dogrula(katman="tam")
    else:
        print("Kullanim: python -m data.onbellek_manifest manifest-kur [--uzerine-yaz] | "
              "manifest-dogrula --katman kesif|tam")
        return 2
    for ad, deger in sonuc.items():
        print(f"{ad}: {deger}")
    return 0


if __name__ == "__main__":
    # `-m` ile modul `__main__` adiyla yuklenir; veri katmani ayni modulu `data.onbellek_manifest` adiyla alir. Durum
    # tek kopyada kalsin diye is o kopyada yapilir.
    from data import onbellek_manifest as _modul

    sys.exit(_modul._ana(sys.argv[1:]))
