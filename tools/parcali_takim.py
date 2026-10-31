"""Parcali tam takim: kayitli bolme yontemi (RESULTS §14.41).

Yontem: `tests/test_*.py` dosyalari ada gore siralanir, round-robin ile N gruba bolunur (varsayilan 4; i. dosya
i mod N grubuna), her grup sirayla ayri bir surecte `python -B -m pytest -q -rxXf -p no:cacheprovider` ile kosulur.
Grup basina ve toplamda gecen, xfail, basarisiz, XPASS, atlanan sayilari ve sure tablo olarak yazilir. Herhangi bir
grupta basarisiz ya da XPASS varsa, ya da pytest bir ozet satiri uretemediyse cikis kodu sifirdan farklidir.

Strict xfail'in XPASS'i pytest ozetinde `failed` sayilir; bu sayilar ayrilir, XPASS `-rxXf` satirlarindan da okunur.

Kullanim: python tools/parcali_takim.py [--grup N] [--gunluk DIZIN]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
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


def grubu_kos(dosyalar: list[str], kok: Path = KOK) -> tuple[dict | None, float, str]:
    bas = time.perf_counter()
    surec = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-rxXf", "-p", "no:cacheprovider", *dosyalar],
                           cwd=kok, capture_output=True, text=True, encoding="utf-8", errors="replace")
    # 0 yesil, 1 basarisiz test; baskasi (kesinti, kullanim, toplama yok) ozetten bagimsiz olarak sonuc sayilmaz.
    sayilar = ozet_oku(surec.stdout) if surec.returncode in (0, 1) else None
    return sayilar, time.perf_counter() - bas, surec.stdout + surec.stderr


def tablo(satirlar: list[tuple[str, int, dict | None, float]]) -> str:
    baslik = ["Grup", "Dosya", "Gecen", "xfail", "Basarisiz", "XPASS", "Atlanan", "Sure (s)"]
    cikti = ["| " + " | ".join(baslik) + " |", "|" + "---|" * len(baslik)]
    toplam = dict.fromkeys(ALANLAR, 0)
    dosya_toplam, sure_toplam = 0, 0.0
    for ad, dosya, sayilar, sure in satirlar:
        dosya_toplam += dosya
        sure_toplam += sure
        if sayilar is None:
            degerler = ["OZET YOK"] * len(ALANLAR)
        else:
            degerler = [str(sayilar[a]) for a in ALANLAR]
            for a in ALANLAR:
                toplam[a] += sayilar[a]
        cikti.append(f"| {ad} | {dosya} | " + " | ".join(degerler) + f" | {sure:.2f} |")
    cikti.append(f"| Toplam | {dosya_toplam} | " + " | ".join(str(toplam[a]) for a in ALANLAR) + f" | {sure_toplam:.2f} |")
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
        sayilar, sure, cikti = grubu_kos(grup)
        if secenek.gunluk is not None:
            secenek.gunluk.mkdir(parents=True, exist_ok=True)
            (secenek.gunluk / f"grup{i}.log").write_text(cikti, encoding="utf-8")
        satirlar.append((str(i), len(grup), sayilar, sure))
        sonuclar.append(sayilar)
    print(tablo(satirlar))
    return cikis_kodu(sonuclar)


if __name__ == "__main__":
    sys.exit(main())
