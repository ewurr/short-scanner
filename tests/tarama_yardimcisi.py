"""Kaynak tarama testlerinin ortak yardimcisi.

Bazi kurallar Python'da bir fonksiyon imzasiyla tamamen zorlanamaz (ör. kume
sinirini bilincli `None` ile kapatmak). Bu kurallar, analiz kodunun (events/,
study/, analysis/ altindaki F2 ve sonrasi) kaynagi taranarak korunur.
"""

from __future__ import annotations

import re
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]

# Kumeye ait olmayan hesaplarin yasal olarak yasadigi yerler.
IZINLI_ALTLAR = ("data", "tests", "analysis/00_veri_denetimi", ".claude")


def ihlaller(desen: str, kok: Path = KOK, izinli_altlar=IZINLI_ALTLAR) -> list[str]:
    """`kok` altindaki .py dosyalarindan, izinli dizinler DISINDA `desen` gecenleri doner."""
    derli = re.compile(desen)
    izinli = {kok / alt for alt in izinli_altlar}
    bulunan = []
    for yol in sorted(kok.rglob("*.py")):
        if any(p in izinli for p in yol.parents) or "cache" in yol.parts:
            continue
        if derli.search(yol.read_text(encoding="utf-8", errors="replace")):
            bulunan.append(yol.relative_to(kok).as_posix())
    return bulunan


KUME_NONE_DESENI = r"\bkume_(baslangic|bitis)\s*=\s*None\b"

# Funding'e kume kapisi (`funding.funding_yukle`) disindan erisim: kume korumasiz
# yukleyici, ic ay ayristiricisi, bucket listeleme/onek ve funding onbellek dizini
# (F1 kapanis denetimi bulgu 10).
FUNDING_KAPI_DISI_DESENI = (
    r"\bham_funding_yukle\b|\b_ay_cercevesi\b|\bfunding_dosyalari\b|\bFUNDING_ONEKI\b"
    r"|fundingRate|[\"']funding[\"']"
)

# Bar sayisiyla calisan ve pencere kapisini (data.pencere) atlayan turetilmis seri
# islemleri. Bunlar seride bosluk, donem ya da kume sinirini bilmez.
CIKIS_KAPI_DISI_DESENI = (
    r"\b(cikis_bari|ufuk_kumeye_sigar_mi|cikis_ani)\s*\(|\bCikisSonucu\s*\(|\bPozisyonPlani\s*\(|_PLAN_GIZLI"
    r"|_plan_imzasi"
)
"""Olayin kumede, donemde ve ufukta olusup olusmadigina yalnizca
`pencere.pozisyon_plani` karar verir (on-kayit §4 rev.7, D3). Analiz kodu cikis ve
kume on elemesini dogrudan cagirmaz, plan ya da cikis nesnesini elle kurmaz."""

TURETILMIS_SERI_DESENI = (
    r"\.(rolling|expanding|ewm|shift|diff|pct_change|cumsum|cumprod|cummax|cummin|resample)\s*\("
)
