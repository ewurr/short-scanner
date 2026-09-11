"""Tarihsel USDⓈ-M USDT perpetual evreni (on-kayit §2).

Delist edilmis sozlesmeler dahildir; on-kayit §2 bunlari acikca evrene katar ve
disarida kalmalarinin sonuclari kotumser yonde saptiracagini soyler.

Bu modul bucket'taki dizin ve dosya ADLARINI kullanir. Listeleme ve delist
tarihleri ilk/son aylik dosyanin icerigine bakilarak kesinlestirilebilir
(`tarihleri_kesinlestir`), ancak evrenin kendisi dosya adlarindan cikarilir.
"""

from __future__ import annotations

import pandas as pd

import config
from data import binance_vision as bv

ONBELLEK_ADI = "universe.parquet"

# Vadeli (teslimatli) sozlesmeler sembolde alt cizgi tasir: BTCUSDT_210625.
VADELI_ISARETI = "_"

# Delist sonrasi olusan tekil kayitlar: AERGOUSDTSETTLED gibi. Bunlar USDT ile
# bitmedigi icin USDT perpetual filtresinde zaten elenir; yine de acik tutulur.
SETTLED_ISARETI = "SETTLED"


def usdt_perpetual_adaylari(sembol_dizinleri: list[str]) -> list[str]:
    """Bucket dizin adlarindan USDT marjinli perpetual adaylarini suzer.

    Elenenler: vadeli sozlesmeler (`_`), USDT disi teminat (USDC, BUSD, ...),
    `SETTLED` son ekli tekil kayitlar.

    Bu fonksiyon ag kullanmaz; girdi -> cikti saftir.
    """
    adaylar = []
    for sembol in sembol_dizinleri:
        if VADELI_ISARETI in sembol:
            continue
        if sembol.endswith(SETTLED_ISARETI):
            continue
        if not sembol.endswith(config.TEMINAT_SONEKI):
            continue
        adaylar.append(sembol)
    return sorted(set(adaylar))


def haric_mi(sembol: str, haric_liste: frozenset[str] | None = None) -> bool:
    """On-kayit §2'deki hariç tutma listesinde mi?

    Liste aciktir, duzenli ifade kullanilmaz: `BUSDT` (BU coini) ve `TUSDT`
    (Threshold) stablecoin degildir ve desen eslestirmesi bunlari yanlislikla
    eler.
    """
    liste = config.HARIC_SEMBOLLER if haric_liste is None else haric_liste
    return sembol in liste


def evren_kur(haric_liste: frozenset[str] | None = None) -> pd.DataFrame:
    """Bucket'i listeleyip evren tablosunu kurar (ag kullanir).

    Sutunlar: sembol, ilk_ay, son_ay, dosya_sayisi_4h, funding_dosya_sayisi,
    haric, haric_gerekce.
    """
    dizinler = bv.tum_sembol_dizinleri()
    adaylar = usdt_perpetual_adaylari(dizinler)

    satirlar = []
    for sembol in adaylar:
        dosyalar = bv.mum_dosyalari(sembol, config.BAR_4H)
        if not dosyalar:
            continue
        aylar = [bv.dosya_ayi(d) for d in dosyalar]
        funding = bv.funding_dosyalari(sembol)
        dis = haric_mi(sembol, haric_liste)
        satirlar.append(
            {
                "sembol": sembol,
                "ilk_ay": aylar[0],
                "son_ay": aylar[-1],
                "dosya_sayisi_4h": len(dosyalar),
                "funding_dosya_sayisi": len(funding),
                "haric": dis,
                "haric_gerekce": "on-kayit §2" if dis else "",
            }
        )
    return pd.DataFrame(satirlar).sort_values("sembol", ignore_index=True)


def evren_yukle(yenile: bool = False, haric_liste: frozenset[str] | None = None) -> pd.DataFrame:
    """Evreni onbellekten okur, yoksa (veya `yenile`) kaynaktan kurar."""
    yol = bv.onbellek_yolu(ONBELLEK_ADI)
    if not yenile:
        onbellek = bv.onbellekten_oku(yol)
        if onbellek is not None:
            return onbellek
    evren = evren_kur(haric_liste)
    bv.onbellege_yaz(evren, yol)
    return evren


def dahil_semboller(evren: pd.DataFrame) -> list[str]:
    """Hariç tutulmayan semboller (calisma evreni)."""
    return sorted(evren.loc[~evren["haric"], "sembol"].tolist())
