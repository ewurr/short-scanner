"""Funding gecmisi ve 8 saate normallestirme (on-kayit §2).

Kaynak dosyanin sutunlari: `calc_time, funding_interval_hours, last_funding_rate`.
Odeme araligi tahmin edilmez; dosyada acikca yazilidir (F1 §1 denemesiyle
dogrulandi: BTCUSDT ve 1000PEPEUSDT 8 saat, WIFUSDT/ORDIUSDT/MYXUSDT/AVNTUSDT
4 saat).

On-kayit §2: "4 saatlik veya 1 saatlik odeme araligina gecmis sozlesmelerde oran,
karsilastirma icin 8 saate normallestirilir; getiri hesabinda ise gercek odemeler
kullanilir." Bu yuzden `oran` (gercek odeme) ve `oran_8h` (karsilastirma) iki ayri
sutun olarak tutulur; gercek odeme sutunu hicbir zaman olceklenmez.
"""

from __future__ import annotations

import pandas as pd

import config
from data import binance_vision as bv


def _ay_cercevesi(govde: bytes) -> pd.DataFrame:
    ham = bv.zip_csv_oku(govde, bv.FUNDING_SUTUNLARI)
    ham = ham[bv.FUNDING_SUTUNLARI].copy()
    cerceve = pd.DataFrame(
        {
            # calc_time bazen 1 ms kayik yazilir (ornek: ...0001); odeme ani
            # icin saniyeye yuvarlamak yerine ham deger korunur, gruplama
            # yapilirken saate yuvarlanir.
            "odeme_zamani": pd.to_datetime(
                pd.to_numeric(ham["calc_time"], errors="coerce"), unit="ms", utc=True
            ),
            "aralik_saat": pd.to_numeric(ham["funding_interval_hours"], errors="coerce"),
            "oran": pd.to_numeric(ham["last_funding_rate"], errors="coerce"),
        }
    )
    return cerceve.sort_values("odeme_zamani", ignore_index=True)


def sekiz_saate_normallestir(oran: pd.Series, aralik_saat: pd.Series) -> pd.Series:
    """Gercek odeme oranini 8 saatlik esdegerine cevirir (on-kayit §2).

    4 saatlik aralikta oran x2, 1 saatlik aralikta x8, 8 saatlikte degismez.
    Saf fonksiyon.
    """
    carpan = config.NORMAL_FUNDING_ARALIGI_SAAT / pd.to_numeric(aralik_saat, errors="coerce")
    return pd.to_numeric(oran, errors="coerce") * carpan


FUNDING_CIKTI_SUTUNLARI = ["odeme_zamani", "aralik_saat", "oran", "oran_8h"]


def funding_yukle(
    sembol: str,
    kume: str,
    onay: bool = False,
    yenile: bool = False,
    split=None,
) -> pd.DataFrame:
    """Funding gecmisini KUME KORUMASIYLA yukler (CLAUDE.md §3.2-3.3).

    `split.yukle` ile ayni davranis: `kume` zorunludur ve varsayilani yoktur;
    C1/C2 icin `onay=True` sarttir, her onayli cagri onay kaydina eklenir,
    onaysiz cagri kayda hicbir sey yazmadan PermissionError verir; sembol
    kumenin grubunda degilse bos cerceve doner; kayitlar odeme zamanina gore
    kume tarih araligina kesilir. On-kayit §4 funding'i net getirinin parcasi
    yaptigi icin getiri kodu funding'e yalnizca bu yoldan erisir.
    """
    from data import split as split_modulu  # split, klines uzerinden bu katmani import eder

    izinli, bas, son = split_modulu.kume_erisimi(
        sembol, kume, onay=onay, split=split, not_metni="kaynak=funding"
    )
    if not izinli:
        return pd.DataFrame(columns=FUNDING_CIKTI_SUTUNLARI)
    tum = ham_funding_yukle(sembol, yenile=yenile)
    if tum.empty:
        return tum
    maske = (tum["odeme_zamani"] >= bas) & (tum["odeme_zamani"] <= son)
    return tum.loc[maske].reset_index(drop=True)


def ham_funding_yukle(sembol: str, yenile: bool = False) -> pd.DataFrame:
    """Bir sembolun TUM funding gecmisi, KUME KORUMASI OLMADAN; eksik aylar indirilir.

    B grubu ve C2 donemi dahil tum gecmisi dondurur. Yalnizca veri katmani ve
    tum gecmisi olcmesi gereken F1 kapsama denetimi icindir (CLAUDE.md §3.1).
    Analiz ve olay kodu bunu CAGIRMAZ.

    Sutunlar: odeme_zamani (UTC), aralik_saat, oran (gercek), oran_8h (normal).
    """
    anahtarlar = bv.funding_dosyalari(sembol)
    parcalar = []
    for anahtar in anahtarlar:
        ay = bv.dosya_ayi(anahtar)
        yol = bv.onbellek_yolu("funding", sembol, f"{ay}.parquet")
        cerceve = None if yenile else bv.onbellekten_oku(yol)
        if cerceve is None:
            cerceve = _ay_cercevesi(bv.zip_indir(anahtar))
            bv.onbellege_yaz(cerceve, yol)
        parcalar.append(cerceve)

    if not parcalar:
        return pd.DataFrame(columns=["odeme_zamani", "aralik_saat", "oran", "oran_8h"])

    tum = pd.concat(parcalar, ignore_index=True)
    tum = tum.drop_duplicates("odeme_zamani", keep="last")
    tum = tum.sort_values("odeme_zamani", ignore_index=True)
    tum["oran_8h"] = sekiz_saate_normallestir(tum["oran"], tum["aralik_saat"])
    return tum


# --- Denetim olcumleri -------------------------------------------------------


def aralik_ozeti(funding: pd.DataFrame) -> pd.DataFrame:
    """Odeme araligina gore kayit sayisi ve ilk/son tarih.

    Yalnizca kapsama olcer; oran ortalamasi veya benzeri bir istatistik
    hesaplamaz (gorev kisiti).
    """
    if funding.empty:
        return pd.DataFrame(columns=["aralik_saat", "kayit", "ilk", "son"])
    ozet = funding.groupby("aralik_saat").agg(
        kayit=("oran", "size"),
        ilk=("odeme_zamani", "min"),
        son=("odeme_zamani", "max"),
    )
    return ozet.reset_index()


def kapsama(funding: pd.DataFrame, mumlar: pd.DataFrame) -> dict:
    """Funding gecmisi ile mum gecmisinin zaman araligi ortusmesi."""
    if funding.empty or mumlar.empty:
        return {
            "funding_var": not funding.empty,
            "mum_var": not mumlar.empty,
            "ortusme_var": False,
            "funding_ilk": None,
            "funding_son": None,
            "mum_ilk": None,
            "mum_son": None,
        }
    f_ilk, f_son = funding["odeme_zamani"].iloc[0], funding["odeme_zamani"].iloc[-1]
    m_ilk, m_son = mumlar["open_time"].iloc[0], mumlar["open_time"].iloc[-1]
    return {
        "funding_var": True,
        "mum_var": True,
        "ortusme_var": bool(f_ilk <= m_son and m_ilk <= f_son),
        "funding_ilk": f_ilk,
        "funding_son": f_son,
        "mum_ilk": m_ilk,
        "mum_son": m_son,
    }
