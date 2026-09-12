#!/usr/bin/env python3
"""Kilitli dosyalara yazmayi engelleyen PreToolUse hook'u.

Amac: F2'de ilk kez getiri hesaplanacak. Metodolojinin sessizce delinmemesi icin
on-kayit, veri bolmesi, onay kaydi ve proje anayasasi dosyalari yalnizca
kullanicinin acik izniyle degistirilebilir (CLAUDE.md §3.2-3.4).

Calisma bicimi:
  - Yalnizca Claude'un Write / Edit arac cagrilarini yakalar.
  - Calisan Python kodunu ETKILEMEZ. `data/split.py` icindeki `onay_kaydet`
    fonksiyonu ONAY_KAYDI.md'ye yazmaya devam eder; o bir arac cagrisi degil,
    surecin kendi dosya yazimidir.
  - `SHORT_LAB_KILIT_ACIK=1` ayarliysa izin verir (bilerek yapilan revizyon).

Girdi : stdin uzerinden JSON (tool_name, tool_input.file_path)
Cikti : izin veriyorsa sessiz cikis; engelliyorsa PreToolUse deny JSON'u.

Ek bagimlilik kullanmaz; yalnizca standart kutuphane.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Proje koku: bu betik .claude/hooks/ altinda durur.
KOK = Path(__file__).resolve().parents[2]

# Gerekce metni Turkce; konsol kodlamasi bozmasin diye cikti UTF-8'e sabitlenir.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Kilitli dosyalar, proje kokune gore.
KILITLI = (
    "PREREGISTRATION.md",
    "data/split.csv",
    "ONAY_KAYDI.md",
    "CLAUDE.md",
)

ACMA_DEGISKENI = "SHORT_LAB_KILIT_ACIK"


def hedef_yol(girdi: dict) -> str | None:
    """Arac girdisinden dosya yolunu cikarir."""
    arac_girdi = girdi.get("tool_input") or {}
    for alan in ("file_path", "notebook_path", "path"):
        deger = arac_girdi.get(alan)
        if isinstance(deger, str) and deger:
            return deger
    return None


def kilitli_mi(yol: str) -> str | None:
    """Yol kilitli dosyalardan birine mi isaret ediyor? Eslesen kalibi doner.

    Iki asamali eslestirme yapilir, cunku yol farkli bicimlerde gelebilir
    (Windows mutlak yolu, POSIX bicimi `/d/...`, ya da goreli yol):
      1. Mutlak yol karsilastirmasi (normal durum),
      2. Normallestirilmis son-ek karsilastirmasi (yedek).
    Yedek asama bir koruma katmani icin bilerek genistir: baska bir dizindeki
    ayni adli dosya da engellenir. Yanlis engelleme zararsizdir (kullanici kilidi
    acabilir); yanlis izin vermek degildir.
    """
    # 1) Mutlak yol karsilastirmasi
    try:
        mutlak = Path(yol).resolve()
        for kalip in KILITLI:
            if mutlak == (KOK / kalip).resolve():
                return kalip
    except Exception:
        pass

    # 2) Son-ek karsilastirmasi (bicimden bagimsiz)
    duz = yol.replace("\\", "/").lower().rstrip("/")
    for kalip in KILITLI:
        hedef = kalip.lower()
        if duz == hedef or duz.endswith("/" + hedef):
            return kalip
    return None


def reddet(kalip: str) -> None:
    """PreToolUse deny cevabini yazar."""
    gerekce = (
        f"{kalip} kilitli bir dosyadir ve dogrudan duzenlenemez. "
        f"Bu dosya proje metodolojisinin cekirdegidir (CLAUDE.md §3.2-3.4): "
        f"on-kayit, veri bolmesi ve onay kaydi sonradan degistirilemez. "
        f"Degisiklik ancak kullanicinin acik izniyle yapilir; izin verildiginde "
        f"{ACMA_DEGISKENI}=1 ortam degiskeni ayarlanarak kilit acilir. "
        f"Kullaniciya sormadan bu dosyayi degistirme."
    )
    cevap = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": gerekce,
        }
    }
    print(json.dumps(cevap, ensure_ascii=False))


def main() -> int:
    try:
        ham = sys.stdin.read()
    except Exception:
        return 0

    # Kilit bilerek acilmissa hicbir sey yapma.
    if os.environ.get(ACMA_DEGISKENI) == "1":
        return 0

    try:
        girdi = json.loads(ham) if ham.strip() else {}
    except Exception:
        # Girdi ayristirilamadi. Bir koruma katmani burada SESSIZCE GECMEMELI:
        # ham metinde kilitli bir dosya adi geciyorsa yine de reddedilir.
        for kalip in KILITLI:
            if kalip.rsplit("/", 1)[-1] in ham:
                reddet(kalip)
                return 0
        return 0

    yol = hedef_yol(girdi)
    if not yol:
        return 0

    kalip = kilitli_mi(yol)
    if kalip:
        reddet(kalip)
    return 0


if __name__ == "__main__":
    sys.exit(main())
