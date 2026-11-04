"""Parcali tam takim: kayitli bolme yontemi (RESULTS §14.41).

Yontem: `tests/test_*.py` dosyalari ada gore siralanir, round-robin ile N gruba bolunur (varsayilan 4; i. dosya
i mod N grubuna), her grup sirayla ayri bir surecte `python -B -m pytest -q -rxXf -p no:cacheprovider` ile kosulur.
Grup basina ve toplamda gecen, xfail, basarisiz, XPASS, atlanan sayilari, sure ve grup surecinin tepe bellegi (MB)
tablo olarak yazilir. Herhangi bir
grupta basarisiz ya da XPASS varsa, ya da pytest bir ozet satiri uretemediyse cikis kodu sifirdan farklidir.

Strict xfail'in XPASS'i pytest ozetinde `failed` sayilir; bu sayilar ayrilir, XPASS `-rxXf` satirlarindan da okunur.

Tepe bellek: Windows'ta surec tanitici uzerinden `GetProcessMemoryInfo` ile `PeakWorkingSetSize` (surec bittikten
sonra okunur, kesindir); baska platformda psutil varsa yarim saniyelik orneklemeyle en buyuk RSS, yoksa
`resource.getrusage(RUSAGE_CHILDREN).ru_maxrss` (o ana kadarki cocuklarin en buyugu). Olculemezse "-" yazilir.
Toplam satirindaki bellek gruplarin en buyugudur, toplami degildir.

Kullanim: python tools/parcali_takim.py [--grup N] [--gunluk DIZIN]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
ALANLAR = ("gecen", "xfail", "basarisiz", "XPASS", "atlanan")
_OZET_ADLARI = {"passed": "gecen", "xfailed": "xfail", "failed": "basarisiz", "error": "basarisiz",
                "errors": "basarisiz", "xpassed": "XPASS", "skipped": "atlanan"}


def gruplara_bol(dosyalar, sayi: int) -> list[list[str]]:
    """Dosyalar ada gore siralanir ve round-robin bolunur. Saf."""
    if sayi < 1:
        raise ValueError(f"Grup sayisi en az 1 olmali: {sayi}")
    sirali = sorted(dosyalar)
    return [sirali[i::sayi] for i in range(sayi)]


def ozet_oku(cikti: str) -> dict | None:
    """pytest ciktisindan sayilar. Ozet satiri yoksa None (toplama hatasi, kesilmis surec). Saf.

    `[XPASS(strict)]` testleri pytest ozetinde `failed` sayilir; bu yuzden strict XPASS sayisi `basarisiz`dan dusulup
    `XPASS`e eklenir."""
    satirlar = [s for s in cikti.splitlines() if s.strip()]
    if not satirlar:
        return None
    son = satirlar[-1]
    if not re.search(r"\bin \d+(\.\d+)?s\b", son):
        return None
    sayilar = dict.fromkeys(ALANLAR, 0)
    for adet, ad in re.findall(r"(\d+) ([a-z]+)", son):
        if ad in _OZET_ADLARI:
            sayilar[_OZET_ADLARI[ad]] += int(adet)
    strict = len(re.findall(r"^\[XPASS\(strict\)\]", cikti, flags=re.M))
    sayilar["basarisiz"] -= strict
    sayilar["XPASS"] += strict
    return sayilar


def _windows_tepe_mb(surec: subprocess.Popen) -> float | None:
    """Bitmis surecin PeakWorkingSetSize degeri (MB). Popen taniticiyi wait'ten sonra da acik tutar."""
    import ctypes
    from ctypes import wintypes

    class _Sayaclar(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

    sayac = _Sayaclar()
    sayac.cb = ctypes.sizeof(sayac)
    psapi = ctypes.WinDLL("psapi")
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_Sayaclar), wintypes.DWORD]
    if not psapi.GetProcessMemoryInfo(int(surec._handle), ctypes.byref(sayac), sayac.cb):
        return None
    return sayac.PeakWorkingSetSize / 2**20


def _psutil_ornekleyici(pid: int):
    """psutil varsa arka planda en buyuk RSS'i ornekler; yoksa None."""
    try:
        import psutil
    except ImportError:
        return None
    durum = {"tepe": 0, "dur": threading.Event()}

    def dongu():
        try:
            p = psutil.Process(pid)
            while not durum["dur"].is_set():
                durum["tepe"] = max(durum["tepe"], p.memory_info().rss)
                durum["dur"].wait(0.5)
        except psutil.Error:
            pass

    threading.Thread(target=dongu, daemon=True).start()
    return durum


def grubu_kos(dosyalar: list[str], kok: Path = KOK) -> tuple[dict | None, float, str, float | None]:
    bas = time.perf_counter()
    surec = subprocess.Popen([sys.executable, "-B", "-m", "pytest", "-q", "-rxXf", "-p", "no:cacheprovider", *dosyalar],
                             cwd=kok, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                             errors="replace")
    ornekleyici = None if sys.platform == "win32" else _psutil_ornekleyici(surec.pid)
    stdout, stderr = surec.communicate()
    sure = time.perf_counter() - bas
    tepe_mb = None
    try:
        if sys.platform == "win32":
            tepe_mb = _windows_tepe_mb(surec)
        elif ornekleyici is not None:
            ornekleyici["dur"].set()
            tepe_mb = ornekleyici["tepe"] / 2**20 or None
        else:
            import resource
            tepe_mb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024  # Linux: KB
    except Exception:  # olcum basarisizsa takim sonucu etkilenmez
        tepe_mb = None
    # 0 yesil, 1 basarisiz test; baskasi (kesinti, kullanim, toplama yok) ozetten bagimsiz olarak sonuc sayilmaz.
    sayilar = ozet_oku(stdout) if surec.returncode in (0, 1) else None
    return sayilar, sure, stdout + stderr, tepe_mb


def _mb(deger: float | None) -> str:
    return "-" if deger is None else f"{deger:.0f}"


def tablo(satirlar: list[tuple]) -> str:
    """Satir: (ad, dosya sayisi, sayilar, sure) ya da sonuna tepe bellek (MB) eklenmis bes oge. Saf."""
    baslik = ["Grup", "Dosya", "Gecen", "xfail", "Basarisiz", "XPASS", "Atlanan", "Sure (s)", "Tepe bellek (MB)"]
    cikti = ["| " + " | ".join(baslik) + " |", "|" + "---|" * len(baslik)]
    toplam = dict.fromkeys(ALANLAR, 0)
    dosya_toplam, sure_toplam, tepe_en_buyuk = 0, 0.0, None
    for ad, dosya, sayilar, sure, *ek in satirlar:
        tepe = ek[0] if ek else None
        if tepe is not None:
            tepe_en_buyuk = tepe if tepe_en_buyuk is None else max(tepe_en_buyuk, tepe)
        dosya_toplam += dosya
        sure_toplam += sure
        if sayilar is None:
            degerler = ["OZET YOK"] * len(ALANLAR)
        else:
            degerler = [str(sayilar[a]) for a in ALANLAR]
            for a in ALANLAR:
                toplam[a] += sayilar[a]
        cikti.append(f"| {ad} | {dosya} | " + " | ".join(degerler) + f" | {sure:.2f} | {_mb(tepe)} |")
    cikti.append(f"| Toplam | {dosya_toplam} | " + " | ".join(str(toplam[a]) for a in ALANLAR)
                 + f" | {sure_toplam:.2f} | {_mb(tepe_en_buyuk)} |")
    return "\n".join(cikti)


def cikis_kodu(sonuclar: list[dict | None]) -> int:
    """Ozetsiz grup, basarisiz ya da XPASS varsa 1. Saf."""
    return int(any(s is None or s["basarisiz"] or s["XPASS"] for s in sonuclar))


def main(argumanlar=None) -> int:
    ayristirici = argparse.ArgumentParser(description="Parcali tam takim")
    ayristirici.add_argument("--grup", type=int, default=4)
    ayristirici.add_argument("--gunluk", type=Path, default=None, help="Grup ciktilarinin yazilacagi dizin")
    secenek = ayristirici.parse_args(argumanlar)

    dosyalar = [y.relative_to(KOK).as_posix() for y in (KOK / "tests").glob("test_*.py")]
    satirlar, sonuclar = [], []
    for i, grup in enumerate(gruplara_bol(dosyalar, secenek.grup)):
        sayilar, sure, cikti, tepe_mb = grubu_kos(grup)
        if secenek.gunluk is not None:
            secenek.gunluk.mkdir(parents=True, exist_ok=True)
            (secenek.gunluk / f"grup{i}.log").write_text(cikti, encoding="utf-8")
        satirlar.append((str(i), len(grup), sayilar, sure, tepe_mb))
        print(f"grup {i}: {len(grup)} dosya, {sure:.1f} s, tepe {_mb(tepe_mb)} MB", file=sys.stderr, flush=True)
        sonuclar.append(sayilar)
    print(tablo(satirlar))
    return cikis_kodu(sonuclar)


if __name__ == "__main__":
    sys.exit(main())
