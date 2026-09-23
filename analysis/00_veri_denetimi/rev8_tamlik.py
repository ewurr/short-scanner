"""TARIHSEL: Rev.8 pozisyon funding tamlik kurali, donmus kopya. YURURLUKTE DEGILDIR.

Kaynak: `data/funding.py` `funding_tamlik_ayrintisi`, commit 977acb6 (Rev.9 koda gecmeden
onceki son hal); ad disinda degistirilmedi. On-kayit Rev.9 bu kuralin yerine capa / zincir /
ilk cift / son maddelerini koydu (§4 "Funding tamligi"); yururlukteki TEK uygulama
`data.funding.funding_tamlik_ayrintisi`dir.

Bu modul yalnizca Rev.8 donemi olcum betiklerinin (`rev8_etki.py`, `rev9_hazirlik.py`)
`rev8_*` sutunlarini ayni tanimla yeniden uretebilmesi icindir. Hicbir karar yolunda
kullanilmaz; `data/` ve analiz kodu (events/, study/) bunu import etmez
(`tests/test_rev9_tek_tamlik.py`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import funding as funding_modulu
from data import pencere as pencere_modulu

REV8_TAMLIK_KOSULLARI = ("kayit_var", "aralik_gecerli", "baslangic_tam", "ic_tam", "son_tam")


def rev8_tamlik_ayrintisi(funding: pd.DataFrame, girisler, pencere_sonlari) -> pd.DataFrame:
    """Rev.8 pozisyon funding tamligi, kosul kosul (TARIHSEL; on-kayit §4 rev.8
    "Funding araligi gecisleri"). Vektorel; yalnizca odeme ZAMANI ve ARALIGI okunur.

    Pencere: giris anindan SONRA ve pencere sonu ile ayni an ya da once. Kosullar:
      - `kayit_var`: pencerede en az bir odeme.
      - `aralik_gecerli`: penceredeki kayitlarin araligi NaN degil ve > 0.
      - `baslangic_tam`: ilk odeme, giris ani + ilk kaydin araligindan SONRA degil.
      - `ic_tam`: ardisik her iki odemede sonraki, onceki + iki kaydin araliklarinin
        buyugunden SONRA degil.
      - `son_tam`: son odeme + araligi pencere sonundan SONRA.
    `tam` bes kosulun birlesimidir. Saf.
    """
    girisler = pd.DatetimeIndex(girisler)
    sonlar = pd.DatetimeIndex(pencere_sonlari)
    if len(girisler) != len(sonlar):
        raise ValueError("girisler ve pencere_sonlari ayni uzunlukta olmali.")
    n = len(girisler)
    sonuc = pd.DataFrame({k: np.zeros(n, dtype=bool) for k in (*REV8_TAMLIK_KOSULLARI, "tam")})
    if n == 0 or funding.empty:
        return sonuc
    zamanlar = funding_modulu._zaman_dizisi(funding, "rev8_tamlik_ayrintisi")
    aralik = pd.to_numeric(funding["aralik_saat"], errors="coerce").to_numpy(dtype=float)
    aralik_td = pd.to_timedelta(np.where(np.isfinite(aralik) & (aralik > 0), aralik, 0.0), unit="h")

    lo = zamanlar.searchsorted(pencere_modulu.ayni_an_sonu(girisler), side="left")
    hi = zamanlar.searchsorted(pencere_modulu.ayni_an_sonu(sonlar), side="left")
    kayit_var = hi > lo

    kotu_aralik = ~(np.isfinite(aralik) & (aralik > 0))
    p_aralik = np.r_[0, np.cumsum(kotu_aralik)]
    aralik_gecerli = kayit_var & ((p_aralik[hi] - p_aralik[lo]) == 0)

    if len(zamanlar) > 1:
        beklenen = zamanlar[:-1] + pd.to_timedelta(np.maximum(aralik_td[1:].to_numpy(), aralik_td[:-1].to_numpy()))
        kotu_bosluk = np.asarray(pencere_modulu.sonra(zamanlar[1:], beklenen), dtype=bool)
    else:
        kotu_bosluk = np.zeros(0, dtype=bool)
    p_bosluk = np.r_[0, np.cumsum(kotu_bosluk)]
    sinir = len(p_bosluk) - 1
    ust = np.minimum(np.maximum(hi - 1, lo), sinir)
    ic_tam = kayit_var & ((p_bosluk[ust] - p_bosluk[np.minimum(lo, sinir)]) == 0)

    ilk = np.where(kayit_var, lo, 0)
    son = np.where(kayit_var, hi - 1, 0)
    baslangic_tam = kayit_var & ~np.asarray(
        pencere_modulu.sonra(zamanlar[ilk], girisler + aralik_td[ilk]), dtype=bool)
    son_tam = kayit_var & np.asarray(pencere_modulu.sonra(zamanlar[son] + aralik_td[son], sonlar), dtype=bool)

    sonuc["kayit_var"] = kayit_var
    sonuc["aralik_gecerli"] = aralik_gecerli
    sonuc["baslangic_tam"] = baslangic_tam & aralik_gecerli
    sonuc["ic_tam"] = ic_tam & aralik_gecerli
    sonuc["son_tam"] = son_tam & aralik_gecerli
    sonuc["tam"] = kayit_var & aralik_gecerli & baslangic_tam & ic_tam & son_tam
    return sonuc


def rev8_pencere_sonu(plan) -> pd.Timestamp:
    """Rev.8'deki funding penceresi sonu (TARIHSEL): donem sonu cikisinda (Rev.8'de T > K) B,
    aksi halde cikis ani. Rev.9 ile T = K de donem sonu cikisidir; Rev.8'de olagan cikisti
    ve penceresi K'da kapaniyordu. Bu fonksiyon o durumda K doner."""
    pencere_modulu.plan_dogrula(plan)
    if plan.donem_sonu_mu and not pencere_modulu.sonra(plan.cikis.hedef_cikis_ani, plan.cikis_ani):
        return plan.cikis_ani  # T = K: Rev.8'de olagan cikis, pencere sonu K
    return funding_modulu.funding_penceresi_sonu(plan)
