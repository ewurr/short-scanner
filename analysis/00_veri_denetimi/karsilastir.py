"""Bu kosunun `*_tam.csv` ciktilarini onceki bir kosunun commit'teki ciktilariyla karsilastirir.

RESULTS.md'deki "onceki kosuyla ayni / degismedi" cumlelerinin kaynagidir (denetci
bulgusu D-B1). Yalnizca dosya iceriklerini karsilastirir; hicbir deger hesaplamaz,
yorumlamaz. Calisma agacindaki dosya ile `<ref>:<yol>` arasinda:

- `durum`: `ayni` (bayt duzeyinde ayni), `farkli`, `yeni` (onceki ref'te yok) ya da
  `kaldirildi` (calisma agacinda yok).
- `eklenen_sutunlar`, `cikan_sutunlar`: baslik farki.
- `yalniz_onceki_satir`, `yalniz_yeni_satir`: ORTAK sutunlar uzerinden, satirlarin
  coklu kume farki. Sutun eklenmis ama ortak sutunlarda hicbir satir degismemisse
  ikisi de 0'dir.

Kullanim:
    python analysis/00_veri_denetimi/karsilastir.py --onceki 02effeb
"""

from __future__ import annotations

import argparse
import collections
import io
import subprocess
import sys
from pathlib import Path

import pandas as pd

KOK = Path(__file__).resolve().parents[2]
BU_DIZIN = Path(__file__).resolve().parent
sys.path.insert(0, str(BU_DIZIN))

from calistir import csv_yaz  # noqa: E402

CIKTI = BU_DIZIN / "karsilastirma_tam.csv"
SUTUNLAR = ["dosya", "onceki_ref", "durum", "onceki_satir", "yeni_satir", "eklenen_sutunlar",
            "cikan_sutunlar", "yalniz_onceki_satir", "yalniz_yeni_satir"]


def _oku(metin: str) -> pd.DataFrame:
    return pd.read_csv(io.StringIO(metin), dtype=str, keep_default_na=False)


def tablo_karsilastir(onceki: str | None, yeni: str | None) -> dict:
    """Iki CSV metnini karsilastirir. Saf. Taraflardan biri yoksa `None` verilir."""
    if onceki is None and yeni is None:
        raise ValueError("iki taraf da yok")
    if onceki is None:
        return {"durum": "yeni", "onceki_satir": None, "yeni_satir": len(_oku(yeni))}
    if yeni is None:
        return {"durum": "kaldirildi", "onceki_satir": len(_oku(onceki)), "yeni_satir": None}
    a, b = _oku(onceki), _oku(yeni)
    ortak = [s for s in a.columns if s in b.columns]
    satirlar_a = collections.Counter(map(tuple, a[ortak].itertuples(index=False, name=None)))
    satirlar_b = collections.Counter(map(tuple, b[ortak].itertuples(index=False, name=None)))
    return {
        "durum": "ayni" if onceki == yeni else "farkli",
        "onceki_satir": len(a), "yeni_satir": len(b),
        "eklenen_sutunlar": ",".join(s for s in b.columns if s not in a.columns),
        "cikan_sutunlar": ",".join(s for s in a.columns if s not in b.columns),
        "yalniz_onceki_satir": sum((satirlar_a - satirlar_b).values()),
        "yalniz_yeni_satir": sum((satirlar_b - satirlar_a).values()),
    }


def _git_dosyasi(ref: str, yol: str) -> str | None:
    sonuc = subprocess.run(["git", "show", f"{ref}:{yol}"], cwd=KOK, capture_output=True)
    if sonuc.returncode != 0:
        return None
    return sonuc.stdout.decode("utf-8").replace("\r\n", "\n")


def _git_listesi(ref: str, dizin: str) -> list[str]:
    cikti = subprocess.run(["git", "ls-tree", "--name-only", f"{ref}:{dizin}"], cwd=KOK,
                           capture_output=True, text=True, check=True).stdout
    return [s for s in cikti.splitlines() if s.endswith("_tam.csv")]


def main(argv: list[str] | None = None) -> None:
    ayristirici = argparse.ArgumentParser()
    ayristirici.add_argument("--onceki", required=True, help="onceki kosunun ciktilarini iceren commit")
    argumanlar = ayristirici.parse_args(argv)
    dizin = BU_DIZIN.relative_to(KOK).as_posix()
    adlar = sorted((set(_git_listesi(argumanlar.onceki, dizin)) | {p.name for p in BU_DIZIN.glob("*_tam.csv")})
                   - {CIKTI.name})
    satirlar = []
    for ad in adlar:
        yerel = BU_DIZIN / ad
        yeni = yerel.read_text(encoding="utf-8").replace("\r\n", "\n") if yerel.exists() else None
        onceki = _git_dosyasi(argumanlar.onceki, f"{dizin}/{ad}")
        satirlar.append({"dosya": ad, "onceki_ref": argumanlar.onceki, **tablo_karsilastir(onceki, yeni)})
    tablo = pd.DataFrame(satirlar, columns=SUTUNLAR)
    csv_yaz(tablo, CIKTI)
    print(tablo.to_string(index=False))


if __name__ == "__main__":
    main()
