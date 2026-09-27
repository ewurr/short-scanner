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

# Donem siniri de bilincli `None` ile kapatilamaz (denetci bulgusu D-C6; on-kayit §2 "Tum geriye
# bakis pencereleri donem baslangicini asamaz"). Esdegerler: anahtar sozcuk (`donem_baslangic=None`),
# eslem anahtari (`{"donem_baslangic": None}`, `**{...}`) ve ayni adli degiskene atama. Sinir:
# degerin baska bir adla tasinmasi (`d = None; donem_baslangic=d`) yakalanmaz.
DONEM_NONE_DESENI = r"\bdonem_(baslangic|bitis)\b[\"']?\s*[=:]\s*None\b"

# Funding'e kume kapisi (`funding.funding_yukle`) disindan erisim: kume korumasiz
# yukleyici, ic ay ayristiricisi, bucket listeleme/onek ve funding onbellek dizini
# (F1 kapanis denetimi bulgu 10).
FUNDING_KAPI_DISI_DESENI = (
    r"\bham_funding_yukle\b|\b_ay_cercevesi\b|\bfunding_dosyalari\b|\bFUNDING_ONEKI\b"
    r"|fundingRate|[\"']funding[\"']"
)

# Funding oranina dogrudan erisim (Rev.10 uygulamasi madde 5; denetci bulgusu D-A3): H2'nin funding
# ortalamasinin tek yolu `funding.funding_ortalamasi`dir (on-kayit §4 "Funding sinyal penceresinin
# tamligi"; yari acik pencere, capa, zincir, kume icinde olma). Analiz kodu oran sutunlarini okuyup
# ortalamayi kendisi kurarsa bu kurallarin hepsini atlar. Getiri tarafinda pozisyon funding'i
# `pozisyon.olay_karari` ciktisindan (`funding_toplami`) okunur; oran sutununa orada da gerek yoktur.
FUNDING_ORAN_DESENI = r"\boran_8h\b|\bsekiz_saate_normallestir\b|[\"']oran[\"']|\.oran\b"

# Kume korumasi olmayan ham yukleyiciler ve SETTLED verisi (denetci bulgusu D-C7). On-kayit §2
# rev.8: "SETTLED dosyalari hicbir hesaba girmez"; SETTLED yalnizca veri denetimi icindir.
# `tests/test_kume_korumasi.py`'deki eski desen (SETTLED'siz) degistirilmedi; bu desen onu kapsar.
HAM_ERISIM_DESENI = (
    r"\bham_(mumlari_yukle|funding_yukle|birincil_gunluk_indir|settled_mumlari_yukle)\b"
    r"|\bsettled_(dizinleri|ay_karsilastir)\b"
)
# `config.SETTLED_SONEKI` desene girmez: tanimi config.py'dedir (izinli dizin disi); SETTLED
# dizin adlari yalnizca `klines.settled_dizinleri` ile uretilir ve o ad desendedir.

# Bar sayisiyla calisan ve pencere kapisini (data.pencere) atlayan turetilmis seri
# islemleri. Bunlar seride bosluk, donem ya da kume sinirini bilmez.
# Uygunluk adlari (on-kayit §4 rev.9: uygunluk tek karar noktasinin parcasidir). `data/eligibility.py`
# icindeki butun fonksiyonlar ve modulun kendisi: modul adiyla erisim (`eligibility.x`, takma adli
# import) de yakalanir.
UYGUNLUK_ADLARI = ("uygun_mu", "uygunluk_serisi", "uygunluk_karari", "esikleri_dogrula", "medyan_hacim",
                   "hacim_esigi", "listeleme_yasi_gun", "gunluk_hacim_serisi")

CIKIS_KAPI_DISI_DESENI = (
    r"\b(cikis_bari|ufuk_kumeye_sigar_mi|cikis_ani|pozisyon_plani|pozisyon_fundingi|_plan_fundingi|pozisyon_funding_tam_mi"
    r"|pozisyon_funding_ayrintisi|funding_tamlik_ayrintisi"
    r"|" + "|".join(UYGUNLUK_ADLARI) + r")\s*\(|\b(CikisSonucu|PozisyonPlani|OnaylanmisPozisyon)\s*\("
    r"|_PLAN_GIZLI|_plan_imzasi|_ONAY_GIZLI|\beligibility\b"
)
"""Olayin ya da kontrolun olusup olusmadigina yalnizca `pozisyon.olay_karari` karar
verir (on-kayit §4 rev.8 "Olayin kumede olusma olcutu": tek karar noktasi, funding
tamligi dahil; rev.9: uygunluk da). Analiz kodu plan, cikis, funding tamligi ve uygunluk
adimlarini dogrudan cagirmaz; `eligibility` modulune hic erismez; plan, cikis ya da onayli
pozisyon nesnesini elle kurmaz. Rev.8 oncesi tek kapi `pencere.pozisyon_plani` idi.

Sinir: tarama yalnizca `.py` dosyalarinin metnine bakar; kasitli bir atlatma (ör. adi
parcalayip `importlib`/`getattr` ile cagirmak) yakalanmaz."""

TURETILMIS_SERI_DESENI = (
    r"\.(rolling|expanding|ewm|shift|diff|pct_change|cumsum|cumprod|cummax|cummin|resample)\s*\("
)

# Kapinin donem ve grup kayitlari (kapi sertlestirme turu, denetci F1K2 D-B2): analiz kodu kapinin kayit
# kaynagini degistiremez ya da test yardimcisinin sentetik donemlerini kullanamaz. Ikincil savunma;
# kararli bir atlatmayi (ör. `setattr` ile parcalanmis ad) yakalamaz.
# Kapi sertlestirme turu 2: kapinin veri yolu (`_veri_yukle`, `_kume_verisi`) ve sentetik veri kaydi da.
KAYIT_DESENI = (r"\b_kayitlar\b|\bkapi_yardimcisi\b|\bSENTETIK_(DONEMLER|GRUPLAR|VERI)\b"
                r"|\b_veri_yukle\b|\b_kume_verisi\b")
