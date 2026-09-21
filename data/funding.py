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

import numpy as np
import pandas as pd

import config
from data import binance_vision as bv
from data.pencere import (  # tek tanim: data/pencere.py (on-kayit §4 rev.8 "Zaman toleransi")
    ODEME_TOLERANSI, ayni_an, ayni_an_basi, ayni_an_sonu, ayni_ya_da_once, ayni_ya_da_sonra, donem_kapanisi,
    once, sonra,
)


def _ay_cercevesi(govde: bytes) -> pd.DataFrame:
    ham = bv.zip_csv_oku(govde, bv.FUNDING_SUTUNLARI)
    ham = ham[bv.FUNDING_SUTUNLARI].copy()
    cerceve = pd.DataFrame(
        {
            # calc_time bazen 1 ms kayik yazilir (ornek: ...0001). Ham deger
            # korunur; hicbir yerde saate YUVARLANMAZ. Ayni odemenin kayik iki
            # kaydi `drop_duplicates` ile birlesmez; bu durum
            # `funding_ortalamasi` icinde bozuk veri olarak hata verir. F1
            # kapanis taramasinda onbellekte 1 dakikadan yakin iki kayit
            # bulunmadi (678 sembol, 2.562.456 kayit).
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
) -> pd.DataFrame:
    """Funding gecmisini KUME KORUMASIYLA yukler (CLAUDE.md §3.2-3.3).

    `split.yukle` ile ayni kapi (`split.kume_erisimi`): `kume` zorunludur ve
    varsayilani yoktur; C1/C2 icin `onay=True` ve acik bir `split.onay_kosusu`
    sarttir, aksi halde kayda hicbir sey yazmadan PermissionError; sembol
    kumenin grubunda degilse bos cerceve doner; kayitlar odeme zamanina gore
    kume tarih araligina kesilir. On-kayit §4 funding'i net getirinin parcasi
    yaptigi icin getiri kodu funding'e yalnizca bu yoldan erisir.

    On-kayit §2 rev.7: donem sonundan sonra gelen (uzlasma sonrasi) kayitlar
    commit edilmis evren tablosunun donemlerine gore atilir
    (`donem_sonrasi_kayitlari_at`). Sembol evren tablosunda yoksa KeyError.
    """
    from data import split as split_modulu  # split, klines uzerinden bu katmani import eder

    from data import universe  # universe, klines uzerinden bu katmani dolayli import edebilir

    izinli, bas, son = split_modulu.kume_erisimi(sembol, kume, onay=onay)
    if not izinli:
        return pd.DataFrame(columns=FUNDING_CIKTI_SUTUNLARI)
    evren = universe.evren_yukle()
    if not (evren["sembol"] == sembol).any():
        raise KeyError(f"{sembol} universe.csv icinde yok.")
    tum = ham_funding_yukle(sembol, yenile=yenile)
    if tum.empty:
        return tum
    tum = donem_sonrasi_kayitlari_at(tum, universe.sembol_donemleri(evren, sembol), config.BAR_4H)
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


# --- Donem ve funding (on-kayit §2 rev.7) -------------------------------------


def _donem_icinde(zamanlar: pd.DatetimeIndex, donem, bar: str) -> np.ndarray:
    """Odeme donem icinde mi: donem basi ile ayni an ya da sonra, son barin
    kapanisi ile ayni an ya da once (on-kayit §4 rev.8 "Zaman toleransi").

    Ust sinir donemin son gercek barinin KAPANISIDIR ve o andaki odeme dahildir;
    ufuk donem sonunu asan pozisyon o anda kapanir ve `pozisyon_fundingi` cikis
    anindaki odemeyi sayar.
    """
    return ayni_ya_da_sonra(zamanlar, donem.baslangic) & ayni_ya_da_once(zamanlar, donem_kapanisi(donem.bitis))


def donem_sonrasi_kayitlari_at(funding: pd.DataFrame, donemler, bar: str) -> pd.DataFrame:
    """Donem sonundan sonra gelen funding kayitlarini atar (on-kayit §2 rev.7). Saf.

    Bir kayit, bir donemin sonundan sonra gelip sonraki bir donemin icine
    dusmuyorsa atilir: son donemden sonrakiler (uzlasma sonrasi sabit oranlar)
    ve iki donem arasindaki dolgu suresine dusenler. Ilk donem baslangicindan
    onceki kayitlar kurala girmez ve korunur (tamlik kurali donem basindan
    onceki kaydi zaten okumaz). Donem yoksa hicbir kayit kalmaz.
    """
    if funding.empty:
        return funding.reset_index(drop=True)
    if not donemler:
        return funding.iloc[0:0].reset_index(drop=True)
    zamanlar = pd.DatetimeIndex(funding["odeme_zamani"])
    tut = once(zamanlar, donemler[0].baslangic)
    for donem in donemler:
        tut |= _donem_icinde(zamanlar, donem, bar)
    return funding.loc[tut].reset_index(drop=True)


def donemde_funding_var(funding: pd.DataFrame, donem, bar: str) -> bool:
    """Donemin icinde (uzlasma sonrasi kayitlar haric) en az bir funding kaydi var mi? Saf.

    On-kayit §2 rev.7: hic funding kaydi bulunmayan donem uc hipotezde de
    kullanilmaz. Evren tablosundaki `donem_funding_yok` sutunu bununla uretilir.
    """
    if funding.empty:
        return False
    return bool(_donem_icinde(pd.DatetimeIndex(funding["odeme_zamani"]), donem, bar).any())


# --- Funding penceresi (H2.1) ------------------------------------------------

# `ODEME_TOLERANSI` (1 dakika) data/pencere.py'de tanimlidir. Iki odeme arasindaki
# en kisa gercek aralik 1 saattir; 1 dakikadan yakin iki kayit bozuk veridir.


def _odemeler_tam_mi(funding: pd.DataFrame, zamanlar: pd.DatetimeIndex, maske, taban, *,
                     bas, bas_dahil: bool, son, son_dahil: bool) -> bool:
    """Penceredeki beklenen odemelerin tamami var mi? (on-kayit §2 rev.3 tamlik
    sarti; `funding_ortalamasi` kurali.) Butun zaman karsilastirmalari on-kayit §4
    rev.8 "Zaman toleransi"na gore (`data.pencere.ayni_an` ve turevleri).

    `aralik_saat` (Binance `funding_interval_hours`) bir kayittan SONRAKI odemeye
    kadar olan sureyi gosterir. F1 kapanis olcumu D1: 559 aralik gecisinin
    556'sinda kayittan sonraki bosluk yeni araliga esit; onceki bosluk ise 365'inde
    yeni, 96'sinda eski araliga esit, 98'inde hicbirine esit degil. Gecis kaydi
    bazen eski, bazen yeni ritimde gelir. Bu yuzden bir sonraki odeme, onceki
    odeme + iki kaydin araliklarindan BUYUGUnden sonra (ayni an degil) geliyorsa
    eksik odeme vardir.

      - **Baslangic.** Pencere `bas` ile ayni an odemeyi iceriyorsa (`bas_dahil`)
        ve penceredeki ilk odeme `bas` ile ayni an ise baslangic tamdir. Degilse
        pencereden onceki son kayit (`bas_dahil` ise `bas`tan once, degilse `bas`
        ile ayni an ya da once) bulunmali ve onunla ilk odeme arasindaki bosluk
        kurala uymalidir; `taban`dan (kume ya da donem basi) onceki kayitlar
        OKUNMAZ. Onceki kayit yoksa tamlik gosterilemez: False.
      - **Ic.** Ardisik her iki odeme arasinda ayni kural.
      - **Son.** Son odeme + kendi araligi, pencere `son` ile ayni an odemeyi
        iceriyorsa (`son_dahil`) `son`dan sonra, icermiyorsa `son` ile ayni an ya
        da sonra olmali. Sonraki kayit okunmaz.
      - **Odemesiz pencere.** Onceki son kayit (taban sonrasi) + araligi ayni
        kurala uymali; onceki kayit yoksa False.
      - Ilgili kayitlardan birinin araligi NaN ya da <= 0 ise False.

    Bilinen sinir: tam bir aralik gecisine denk gelen ve boslugu iki araligin
    buyugunu asmayan tek bir eksik odeme yakalanamaz.
    """
    aralik_tum = pd.to_numeric(funding["aralik_saat"], errors="coerce").to_numpy(dtype=float)
    maske = np.asarray(maske, dtype=bool)
    onceki_maske = np.asarray(once(zamanlar, bas) if bas_dahil else ayni_ya_da_once(zamanlar, bas), dtype=bool)
    if taban is not None:
        onceki_maske &= np.asarray(ayni_ya_da_sonra(zamanlar, taban), dtype=bool)
    onceki = np.flatnonzero(onceki_maske)
    ici = np.flatnonzero(maske)

    def _son_tam(z_son, a_son) -> bool:
        sonraki = z_son + pd.Timedelta(hours=float(a_son))
        return sonra(sonraki, son) if son_dahil else ayni_ya_da_sonra(sonraki, son)

    if len(ici) == 0:
        if len(onceki) == 0:
            return False
        k = int(onceki[-1])
        a = aralik_tum[k]
        return bool(a > 0) and _son_tam(zamanlar[k], a)

    if bas_dahil and ayni_an(zamanlar[ici[0]], bas):
        zincir = ici
    elif len(onceki):
        zincir = np.r_[onceki[-1], ici]
    else:
        return False
    a = aralik_tum[zincir]
    if np.isnan(a).any() or (a <= 0).any():
        return False
    z = zamanlar[zincir]
    if len(zincir) > 1:
        beklenen = z[:-1] + pd.to_timedelta(np.maximum(a[1:], a[:-1]), unit="h")
        if np.asarray(sonra(z[1:], beklenen)).any():
            return False
    return _son_tam(z[-1], a[-1])


def funding_ortalamasi(
    funding: pd.DataFrame,
    t,
    bar: str,
    *,
    saat: int,
    kume_baslangic,
    donem_baslangic,
) -> float:
    """t barinin kapanisina kadarki son `saat` saatteki 8 saate normallestirilmis
    funding oranlarinin ortalamasi (on-kayit §5 H2.1); kural ihlalinde NaN.

    Mum pencereleriyle (`data.pencere.pencere_dilimi`) ayni korumalar:
      - **Gelecege bakis yok.** Sinyal t barinin KAPANISINDA hesaplanir
        (CLAUDE.md §3.6). Pencere yari acik `[kapanis - saat, kapanis)`:
        tam kapanis anindaki odeme ALINMAZ. Bir odeme o anda gerceklesir; ms
        duzeyindeki kayit farklari yuzunden kapanisla ayni ana dusen odemenin
        sinyalden once bilindigi varsayilmaz (ihtiyatli secim).
      - **Donem ve kume.** Pencere donem ya da kume baslangicini asarsa NaN
        (on-kayit §2 rev.2, §3 rev.5); kume oncesi odeme seride bulunsa bile.
      - **Tamlik.** Penceredeki odemeler boslugsuz olmali (`_odemeler_tam_mi`:
        `aralik_saat` SONRAKI odemeye kalan suredir; ardisik iki odeme arasindaki
        bosluk iki kaydin araliklarindan buyugunu asamaz; pencere oncesindeki
        kayit kume/donem basindan once olamaz; kapanistan sonraki kayit okunmaz).
        Eksik odeme, NaN oran ya da NaN aralik -> NaN. Bir dakikadan yakin iki
        kayit bozuk veridir -> ZamanDizisiHatasi.

    Tum sinirlar zorunlu anahtar sozcuktur; sinir yoksa acikca None.
    Saf fonksiyon.
    """
    from data import pencere as pencere_modulu

    if not isinstance(saat, int) or isinstance(saat, bool) or saat < 1:
        raise ValueError(f"saat pozitif bir tamsayi olmali: {saat!r}")
    zaman = pencere_modulu.utc_zamani(t, "t")
    kume_bas = pencere_modulu.sinir_zamani(kume_baslangic, "kume_baslangic")
    donem_bas = pencere_modulu.sinir_zamani(donem_baslangic, "donem_baslangic")

    kapanis = zaman + pencere_modulu.adim(bar)
    bas = kapanis - pd.Timedelta(hours=saat)
    nan = float("nan")

    if donem_bas is not None and once(bas, donem_bas):
        return nan
    if kume_bas is not None and once(bas, kume_bas):
        return nan
    zamanlar = pencere_modulu._zaman_dizisi_dogrula(funding["odeme_zamani"], "funding_ortalamasi")
    if len(zamanlar) > 1:
        yakin = np.asarray(ayni_an(zamanlar[1:], zamanlar[:-1]), dtype=bool)
        if yakin.any():
            ilk = int(yakin.argmax())
            raise pencere_modulu.ZamanDizisiHatasi(
                f"funding_ortalamasi: {zamanlar[ilk]} ve {zamanlar[ilk + 1]} birbirine "
                f"{ODEME_TOLERANSI}'dan yakin; ayni odeme iki kez yazilmis olabilir (bozuk veri)."
            )

    # Pencere `[kapanis - saat, kapanis)`: baslangic ile ayni an ya da sonra, kapanistan
    # ONCE (kapanis ile ayni an sayilan odeme alinmaz; on-kayit §4 rev.8 "Zaman toleransi").
    maske = ayni_ya_da_sonra(zamanlar, bas) & once(zamanlar, kapanis)
    if not maske.any():
        return nan
    secili = funding.loc[maske]
    oran = pd.to_numeric(secili["oran_8h"], errors="coerce")
    aralik = pd.to_numeric(secili["aralik_saat"], errors="coerce")
    if oran.isna().any() or aralik.isna().any() or (aralik <= 0).any():
        return nan

    taban = max((s for s in (kume_bas, donem_bas) if s is not None), default=None)
    if not _odemeler_tam_mi(funding, zamanlar, maske, taban, bas=bas, bas_dahil=True,
                            son=kapanis, son_dahil=False):
        return nan  # eksik odeme
    return float(oran.mean())


# --- Pozisyon funding'i (on-kayit §4 rev.6) ----------------------------------


def pozisyon_fundingi(funding: pd.DataFrame, plan) -> float:
    """Short pozisyonun tuttugu sure boyunca aldigi (+) ya da odedigi (-) funding.

    On-kayit §4: her funding aninda `+oran` (GERCEK odeme orani, `oran`;
    8 saate normallestirilmis `oran_8h` kullanilmaz). Toplam doner.

    Yalnizca `pencere.pozisyon_plani`nin urettigi PLANI alir (on-kayit §4 rev.7
    "Olayin kumede olusma olcutu", tek kapi). Olayin kumede, donemde ve ufukta
    olusup olusmadigina plan karar vermistir; bu fonksiyon kume ya da donem
    karari VERMEZ, yalnizca veri tamligina bakar. Elle kurulmus ya da sonradan
    degistirilmis plan reddedilir.

    Sinirlar (on-kayit §4 rev.6):
      - Giris anindaki odeme HARIC, cikis anindaki DAHIL.
      - 1 dakikadan kucuk kayma ayni an sayilir. Odeme p dahildir ancak ve ancak
        `giris + 1 dk <= p < cikis_ani + 1 dk`.
      - Tamlik `_odemeler_tam_mi` ile; kume ya da donem basindan onceki kayit okunmaz.

    NaN ile hata ayrimi (F1 kapanis denetimi bulgu 11):
      - **NaN yalnizca VERI EKSIKLIGIDIR**: aralikta beklenen bir odeme eksik,
        oran ya da aralik NaN, aralik <= 0, odemesiz aralikta onceki kayit yok.
      - **TypeError**: `plan` bir `PozisyonPlani` degil.
      - **ValueError**: plan elle kurulmus ya da degistirilmis (programlama hatasi).
      - **ZamanDizisiHatasi** (ValueError alt sinifi): bozuk veri (sirasiz,
        tekrarli, saat dilimsiz ya da 1 dakikadan yakin kayit).
    Kume, donem, giris ve ileri kayma kurallari `pencere.OlayOlusmaz` alt
    siniflariyla PLAN asamasinda yuzeye cikar.

    Saf fonksiyon.
    """
    from data import pencere as pencere_modulu

    pencere_modulu.plan_dogrula(plan)
    ust = plan.cikis_ani
    nan = float("nan")

    zamanlar = pencere_modulu._zaman_dizisi_dogrula(funding["odeme_zamani"], "pozisyon_fundingi")
    if len(zamanlar) > 1:
        yakin = np.asarray(ayni_an(zamanlar[1:], zamanlar[:-1]), dtype=bool)
        if yakin.any():
            ilk = int(yakin.argmax())
            raise pencere_modulu.ZamanDizisiHatasi(
                f"pozisyon_fundingi: {zamanlar[ilk]} ve {zamanlar[ilk + 1]} birbirine "
                f"{ODEME_TOLERANSI}'dan yakin; ayni odeme iki kez yazilmis olabilir (bozuk veri)."
            )

    maske = sonra(zamanlar, plan.giris) & ayni_ya_da_once(zamanlar, ust)
    taban = max((s for s in (plan.kume_baslangic, plan.donem_baslangic) if s is not None), default=None)
    if not maske.any():
        # Aralikta odeme yok: onceki son kaydin (kume/donem basi sonrasi) sonraki
        # odemesi araliktan sonra olmali (`_odemeler_tam_mi`).
        tam = _odemeler_tam_mi(funding, zamanlar, maske, taban, bas=plan.giris, bas_dahil=False,
                               son=ust, son_dahil=True)
        return 0.0 if tam else nan

    secili = funding.loc[maske]
    oran = pd.to_numeric(secili["oran"], errors="coerce")
    aralik = pd.to_numeric(secili["aralik_saat"], errors="coerce")
    if oran.isna().any() or aralik.isna().any() or (aralik <= 0).any():
        return nan

    if not _odemeler_tam_mi(funding, zamanlar, maske, taban, bas=plan.giris, bas_dahil=False,
                            son=ust, son_dahil=True):
        return nan  # eksik odeme
    return float(oran.sum())


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
