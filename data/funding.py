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


# --- Donem ve funding (on-kayit §2 rev.8) -------------------------------------
#
# Iki pencere (B, K: `pencere.donem_kapanisi`, 4h duzeyinde; `bar` yalnizca
# dogrulanir):
#   - Kayit donemde KALIR: [donem basi, K] (ayni an kurallariyla). "Donem
#     kapanisindan (K) sonra gelen funding kayitlari yok sayilir; B ile K arasindaki
#     kayitlar icin §4'teki donem sonu istisnasi gecerlidir."
#   - Donem funding'li SAYILIR: [donem basi, B]. "Bir funding kaydinin donemde
#     sayilma penceresi, donem basindan donem bitisine (B, dahil) kadardir ve getiri
#     hesabinin donem sonu penceresiyle aynidir."


def _donem_icinde(zamanlar: pd.DatetimeIndex, donem, bar: str) -> np.ndarray:
    """Kayit donemde kalir mi: donem basi ile ayni an ya da sonra, K ile ayni an ya
    da once (on-kayit §2 rev.8 "Gercek islem sonrasi funding kayitlari")."""
    from data import pencere as pencere_modulu

    pencere_modulu.adim(bar)
    return ayni_ya_da_sonra(zamanlar, donem.baslangic) & ayni_ya_da_once(zamanlar, donem_kapanisi(donem.bitis))


def _donemde_sayilir(zamanlar: pd.DatetimeIndex, donem) -> np.ndarray:
    """Kayit donemin funding'li sayilmasina katilir mi: [donem basi, B] (on-kayit §2
    rev.8 "Funding'i bulunmayan donemler"; §4 "Donem sonu istisnasi" ile ayni ust uc)."""
    return ayni_ya_da_sonra(zamanlar, donem.baslangic) & ayni_ya_da_once(zamanlar, donem.bitis)


def donem_sonrasi_kayitlari_at(funding: pd.DataFrame, donemler, bar: str) -> pd.DataFrame:
    """Donem kapanisindan (K) sonra gelen funding kayitlarini atar (on-kayit §2 rev.8). Saf.

    Bir kayit, bir donemin kapanisindan sonra gelip sonraki bir donemin icine
    dusmuyorsa atilir: son donemden sonrakiler ve iki donem arasindaki dolgu
    suresine dusenler. B ile K arasindaki kayitlar korunur; onlara pozisyon
    funding'inde donem sonu istisnasi uygulanir. Ilk donem baslangicindan onceki
    kayitlar korunur. Donem yoksa hicbir kayit kalmaz.
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
    """Donemde, donem basindan B'ye (dahil) kadar en az bir funding kaydi var mi? Saf.

    On-kayit §2 rev.8: hic funding kaydi bulunmayan donem uc hipotezde de
    kullanilmaz; sayim penceresi donem basindan donem bitisine (B, dahil) kadardir.
    `bar` yalnizca dogrulanir (B 4h duzeyindedir).
    """
    from data import pencere as pencere_modulu

    pencere_modulu.adim(bar)
    if funding.empty:
        return False
    return bool(np.any(_donemde_sayilir(pd.DatetimeIndex(funding["odeme_zamani"]), donem)))


# --- Funding sinyal penceresi (H2.1; on-kayit §4 "Funding sinyal penceresinin tamligi") ----------

# Bu bolumun uyguladigi on-kayit paragrafinin son revizyonu. `tests/test_rev10_kalan_bulgular.py`
# on-kayittaki paragrafin "(rev.N)" etiketleriyle karsilastirir: on-kayit kurali yeniden degistirirse
# kod guncellenmeden test kirilir (Rev.10 uygulamasi madde 5; denetci bulgusu D-A3).
SINYAL_PENCERESI_REVIZYONU = 10

SINYAL_PENCERESI_SUTUNLARI = ("hesaplanabilir", "kume_icinde", "capa_var", "aralik_gecerli", "zincir_tam",
                              "kayit_var", "ilk", "son")


def sinyal_penceresi_ayrintisi(funding: pd.DataFrame, t_ler, bar: str, *, saat: int, kume_baslangic,
                               kume_bitis, donem_baslangic) -> pd.DataFrame:
    """H2 funding sinyal penceresinin kurallari, t basina (vektorel). Yalnizca odeme ZAMANI ve ARALIGI
    okunur; oran okunmaz. `funding_ortalamasi` degeri bunun ustune kurar.

    On-kayit §4 "Funding sinyal penceresinin tamligi" (rev.9, rev.10):
      - Pencere t barinin kapanisinda biter ve `saat` saat geriye uzanir; YARI ACIKTIR: pencere
        basina tam denk gelen kayit ortalamaya girmez, pencere sonuna denk gelen girer (ikisi de
        tolerans payiyla, `pencere.sonra` / `pencere.ayni_ya_da_once`). `ilk`, `son`: penceredeki ilk
        ve son kaydin sirasi (kayit yoksa `son < ilk`).
      - `kume_icinde`: pencerenin tamami kumenin (ve donemin) icinde: pencere basi kume basindan ve
        donem basindan once degil, kapanis kume sonundan sonra degil; karsilastirmalar toleransla
        (kume sonu 23:59:59 ile son barin kapanisi 00:00 ayni an; son bar dusmez).
      - `capa_var`, `aralik_gecerli`, `zincir_tam`: tek tamlik kodu `funding_tamlik_ayrintisi`, giris =
        pencere basi, pencere sonu = kapanis, taban = donem basi ile kume basinin gec olani. Capa
        pencere basinda ya da oncesinde kalan son kayit; zincir capadan pencere sonuna; ilk ciftte
        taban pencere basi; dizideki her kaydin araligi sonlu ve > 0 ("Gecerli aralik", rev.10).
        **Son kosulu uygulanmaz** (`son_tam` okunmaz).
      - `kayit_var`: pencerede en az bir kayit (ortalama tanimli).
    `hesaplanabilir` = hepsi. Kapanistan sonraki kayitlar karara girmez (zincir ve aralik yalnizca
    capadan pencere sonuna); `funding_ortalamasi` seriyi ayrica kapanista keser. Sinirlar zorunlu
    anahtar sozcuktur; donem basi None olamaz, kume siniri yoksa acikca None. Saf.
    """
    from data import pencere as pencere_modulu

    if not isinstance(saat, int) or isinstance(saat, bool) or saat < 1:
        raise ValueError(f"saat pozitif bir tamsayi olmali: {saat!r}")
    if saat != config.H2_FUNDING_PENCERESI_SAAT:
        raise ValueError(f"saat {saat} on-kayit degeri degil; H2 funding penceresi "
                         f"{config.H2_FUNDING_PENCERESI_SAAT} saattir (on-kayit §5 H2 madde 1; "
                         "config.H2_FUNDING_PENCERESI_SAAT).")
    kume_bas = pencere_modulu.sinir_zamani(kume_baslangic, "kume_baslangic")
    kume_son = pencere_modulu.sinir_zamani(kume_bitis, "kume_bitis")
    donem_bas = pencere_modulu.donem_siniri(donem_baslangic, "donem_baslangic")
    t = pd.DatetimeIndex(t_ler)
    if t.tz is None:
        if len(t):
            raise TypeError("t_ler saat dilimsiz (tz-naive); tum zaman damgalari UTC olmali.")
        t = t.tz_localize("UTC")
    kapanis = t + pencere_modulu.adim(bar)
    bas = kapanis - pd.Timedelta(hours=saat)
    n = len(t)

    kume_icinde = ~np.asarray(once(bas, donem_bas), dtype=bool)
    if kume_bas is not None:
        kume_icinde &= ~np.asarray(once(bas, kume_bas), dtype=bool)
    if kume_son is not None:
        kume_icinde &= ~np.asarray(sonra(kapanis, kume_son), dtype=bool)

    taban = donem_bas if kume_bas is None else max(donem_bas, kume_bas)
    tamlik = funding_tamlik_ayrintisi(funding, bas, kapanis, donem_baslari=[taban] * n)
    if n and not funding.empty:
        zamanlar = _zaman_dizisi(funding, "sinyal_penceresi_ayrintisi")
        # Sirali dizide tek kenar tanimlari (`ayni_an_sonu`): sonra(z, bas) <=> z >= bas + tol;
        # ayni_ya_da_once(z, kapanis) <=> z < kapanis + tol.
        ilk = zamanlar.searchsorted(pencere_modulu.ayni_an_sonu(bas), side="left")
        son = zamanlar.searchsorted(pencere_modulu.ayni_an_sonu(kapanis), side="left") - 1
    else:
        ilk = np.zeros(n, dtype=int)
        son = np.full(n, -1, dtype=int)
    sonuc = pd.DataFrame({
        "kume_icinde": kume_icinde,
        "capa_var": tamlik["capa_var"].to_numpy(dtype=bool),
        "aralik_gecerli": tamlik["aralik_gecerli"].to_numpy(dtype=bool),
        "zincir_tam": tamlik["zincir_tam"].to_numpy(dtype=bool),
        "kayit_var": np.asarray(son >= ilk, dtype=bool),
        "ilk": np.asarray(ilk, dtype=int),
        "son": np.asarray(son, dtype=int),
    })
    sonuc.insert(0, "hesaplanabilir", sonuc["kume_icinde"] & sonuc["capa_var"] & sonuc["aralik_gecerli"]
                 & sonuc["zincir_tam"] & sonuc["kayit_var"])
    return sonuc


def funding_ortalamasi(
    funding: pd.DataFrame,
    t,
    bar: str,
    *,
    saat: int,
    kume_baslangic,
    kume_bitis,
    donem_baslangic,
) -> float:
    """t barinin kapanisina kadarki son `saat` saatteki 8 saate normallestirilmis funding oranlarinin
    ortalamasi (on-kayit §5 H2 madde 1); kural ihlalinde NaN.

    Pencere kurallari `sinyal_penceresi_ayrintisi`dir (on-kayit §4 "Funding sinyal penceresinin
    tamligi", rev.9 + rev.10): yari acik pencere (basa denk gelen kayit girmez, sona denk gelen girer),
    capa, zincir (ilk ciftte taban pencere basi), gecerli aralik, son kosulu yok, pencerenin tamami
    kumenin icinde. "t barinin kapanisindan sonraki hicbir kayit okunmaz": seri, hicbir denetimden
    once kapanisla ayni an ya da once olan kayitlara kesilir. Penceredeki bir oran NaN ise NaN.
    Bir dakikadan yakin iki kayit bozuk veridir -> `ZamanDizisiHatasi`.

    Tum sinirlar zorunlu anahtar sozcuktur (kume sonu Rev.10 ile eklendi). Donem basi None olamaz;
    kume siniri yoksa acikca None. Saf fonksiyon.
    """
    from data import pencere as pencere_modulu

    zaman = pencere_modulu.utc_zamani(t, "t")
    kapanis = zaman + pencere_modulu.adim(bar)
    ham = pd.DatetimeIndex(funding["odeme_zamani"])
    if len(ham) and ham.tz is None:
        raise pencere_modulu.ZamanDizisiHatasi(
            "funding_ortalamasi: odeme zamanlari saat dilimsiz (tz-naive); tum zaman damgalari UTC olmali.")
    gecmis = funding.loc[np.asarray(ayni_ya_da_once(ham, kapanis), dtype=bool)].reset_index(drop=True)
    a = sinyal_penceresi_ayrintisi(gecmis, [zaman], bar, saat=saat, kume_baslangic=kume_baslangic,
                                   kume_bitis=kume_bitis, donem_baslangic=donem_baslangic).iloc[0]
    if not bool(a["hesaplanabilir"]):
        return float("nan")
    oran = pd.to_numeric(gecmis["oran_8h"].iloc[int(a["ilk"]):int(a["son"]) + 1], errors="coerce")
    if oran.isna().any():
        return float("nan")
    return float(oran.mean())


# --- Pozisyon funding'i (on-kayit §4 rev.8, tamlik rev.9) ---------------------

TAMLIK_KOSULLARI = ("capa_var", "aralik_gecerli", "zincir_tam", "son_tam")
# Bilinen sinirlarin bayraklari ve ritim etiketleri (on-kayit §4 rev.9); `tam`a girmez.
TAMLIK_BAYRAKLARI = ("kuyruk_kismi", "kuyruk_sifir", "son_esitlik_affi", "capa_aralik_saat", "son_aralik_saat",
                     "tek_ritim", "funding_ritmi_saat", "karisik_ritim", "ritim_sinifi")

# Pozisyonun funding ritmi sinifi (on-kayit §4 "Pozisyonun funding ritmi", rev.10; "F2 sarti": "funding
# ritmi basina (8, 4, 2, 1 saat ve siniflanmamis)"). On-kayittaki ad "siniflanmamis"; kodda ASCII.
RITIM_SINIFLANMAMIS = "siniflanmamis"
RITIM_SINIFLARI = ("8", "4", "2", "1", RITIM_SINIFLANMAMIS)
_RITIM_SAATLERI = {8.0: "8", 4.0: "4", 2.0: "2", 1.0: "1"}


def ritim_sinifi(saat) -> str | None:
    """Funding ritmi (saat) -> sinif (on-kayit §4 "Pozisyonun funding ritmi", rev.10). "Aralik alani 8,
    4, 2 ya da 1 saat disinda bir degerse pozisyon 'siniflanmamis' sinifinda raporlanir. Capasi olmayan
    pozisyon olusmadigi icin siniflanmaz": NaN (capa yok) -> None. Saf."""
    deger = float(saat)
    if np.isnan(deger):
        return None
    return _RITIM_SAATLERI.get(deger, RITIM_SINIFLANMAMIS)


def ritim_sinifi_ozeti(siniflar, karisik) -> pd.DataFrame:
    """Ritim sinifi basina pozisyon sayisi, karisik ritimli sayisi ve payi (on-kayit §4 rev.10:
    "karisik ritimlilerin payi her sinifta ayrica yazilir"). Satirlar `RITIM_SINIFLARI` sirasinda, bos
    sinif da yazilir (pay NaN). Bilinmeyen sinif ya da None (capasiz) ValueError. Saf."""
    siniflar = list(siniflar)
    karisik = [bool(k) for k in karisik]
    if len(siniflar) != len(karisik):
        raise ValueError("siniflar ve karisik ayni uzunlukta olmali.")
    bilinmeyen = sorted({repr(s) for s in siniflar if s not in RITIM_SINIFLARI})
    if bilinmeyen:
        raise ValueError(f"Bilinmeyen ritim sinifi: {bilinmeyen} (gecerli: {RITIM_SINIFLARI}).")
    cerceve = pd.DataFrame({"sinif": siniflar, "karisik": karisik})
    ozet = pd.DataFrame(index=pd.Index(RITIM_SINIFLARI, name="sinif"))
    ozet["pozisyon"] = cerceve.groupby("sinif").size().reindex(ozet.index, fill_value=0).astype(int)
    ozet["karisik"] = cerceve.groupby("sinif")["karisik"].sum().reindex(ozet.index, fill_value=0).astype(int)
    ozet["karisik_payi"] = ozet["karisik"] / ozet["pozisyon"].where(ozet["pozisyon"] > 0)
    return ozet
# Dizinin iki ucu (yalnizca kayit zamanlari; hukme girmez): capa ve penceredeki son kayit.
TAMLIK_ZAMANLARI = ("capa_zamani", "son_kayit_zamani")


def funding_penceresi_sonu(plan) -> pd.Timestamp:
    """Pozisyonun funding penceresinin ust ucu (dahil). On-kayit §4 rev.8: olagan
    cikista ve ileri kaymada cikis ani ("cikis anindaki dahil"); donem sonuna ulasan
    pozisyonda donem bitisi B ("Donem sonu istisnasi": B'den sonraki odemeler, K
    dahil, hesaba girmez; tamlik son odemeyi B'ye gore arar)."""
    from data import pencere as pencere_modulu

    pencere_modulu.plan_dogrula(plan)
    return plan.donem_bitis if plan.donem_sonu_mu else plan.cikis_ani


def _zaman_dizisi(funding: pd.DataFrame, yer: str) -> pd.DatetimeIndex:
    """Sirali, tekrarsiz ve ardisik iki kaydi ayni an olmayan odeme zamanlari (bozuk veri ->
    ZamanDizisiHatasi)."""
    from data import pencere as pencere_modulu

    zamanlar = pencere_modulu._zaman_dizisi_dogrula(funding["odeme_zamani"], yer)
    if len(zamanlar) > 1:
        yakin = np.asarray(ayni_an(zamanlar[1:], zamanlar[:-1]), dtype=bool)
        if yakin.any():
            ilk = int(yakin.argmax())
            raise pencere_modulu.ZamanDizisiHatasi(
                f"{yer}: {zamanlar[ilk]} ve {zamanlar[ilk + 1]} ayni an ({ODEME_TOLERANSI}'dan yakin); "
                "ayni odeme iki kez yazilmis olabilir (bozuk veri)."
            )
    return zamanlar


def funding_tamlik_ayrintisi(funding: pd.DataFrame, girisler, pencere_sonlari, *, donem_baslari) -> pd.DataFrame:
    """Pozisyon funding tamliginin TEK uygulamasi, kosul kosul (on-kayit §4 rev.9
    "Funding tamligi"; pencere: §4 "Funding odemesinin sinirlari", "Donem sonu
    istisnasi"). Vektorel: `girisler[i]`, `pencere_sonlari[i]` ve `donem_baslari[i]`
    bir pozisyondur. Yalnizca odeme ZAMANI ve ARALIGI okunur; oran okunmaz.

    Kural odeme ani TAHMIN ETMEZ; yalnizca kayitlar arasindaki bosluklari olcer. Bes madde (rev.10):
      - `capa_var` (**Capa**): giris aninda ya da oncesinde kalan son donem ici kayit
        (donem basiyla ayni an ya da sonra). "Capa yoksa funding tam degildir."
      - `zincir_tam` (**Zincir**, **Ilk cift**): capadan pencere sonuna kadar art arda
        iki kayitta sonraki, oncekinin ustune iki kaydin araliklarindan buyugu eklenerek
        bulunan andan SONRA degil. Ilk ciftte (capa -> sonraki kayit) taban capa degil
        giris anidir.
      - `son_tam` (**Son**): penceredeki son kayit + araligi pencere sonundan ONCE degil;
        "tam pencere sonuna denk gelmesi yeterlidir". Pencerede capadan sonra kayit
        yoksa dizinin son kaydi capadir (rev.9 "hic kayit yok" cumlesini kaldirdi).
      - `aralik_gecerli` (**Gecerli aralik**, rev.10): capadan son kayda kadar her kaydin
        araligi sonlu ve > 0; aralik olmadan zincir ve son maddeleri olculemez.
    "Beklenen odeme ani yukaridaki maddeler disinda hicbir yerde uretilmez." Butun zaman
    karsilastirmalari §4 "Zaman toleransi"na gore (`pencere.ayni_an` ve turevleri):
    tolerans payi ayni an tanimidir, tam 1 dakikalik fark ayni an degildir.

    Bilinen sinirlarin bayraklari (on-kayit §4 rev.9 "Funding tamliginin bilinen
    sinirlari", "F2 sarti"; `tam`a GIRMEZ, yalnizca tam pozisyonlarda True olabilir):
      - `kuyruk_kismi`: son kayittan pencere sonuna kalan dilim bir tam araliktan kisa
        (0 < dilim; son kayit + araligi pencere sonundan SONRA ve son kayit pencere
        sonuyla ayni an degil). O dilimdeki eksik bir odeme gorulemez.
      - `kuyruk_sifir`: son kayit pencere sonuyla ayni an; dogrulanamayan dilim yok.
      - `son_esitlik_affi`: son kayit + araligi tam pencere sonuna denk geliyor; orada
        kayit yok ve pozisyon tam sayiliyor ("Pencere sonundaki esitlik").
    Ritim etiketleri (F2 sarti "funding ritmi basina"; hukme girmez): `capa_aralik_saat`
    (capanin araligi), `son_aralik_saat` (dizideki son kaydin araligi), `tek_ritim`
    (capadan son kayda kadar butun araliklar ayni). Capa yoksa araliklar NaN.
    Pozisyonun funding ritmi (on-kayit §4 "Pozisyonun funding ritmi", rev.10): `funding_ritmi_saat`
    = dizideki son kaydin araligi (kismi kuyrugun uzunlugunu belirleyen); `karisik_ritim` = capa var
    ve capadan son kayda araliklar ayni degil; `ritim_sinifi` = `ritim_sinifi(funding_ritmi_saat)`:
    "8", "4", "2", "1" ya da "siniflanmamis"; capa yoksa None.
    Dizinin uclari (`capa_zamani`, `son_kayit_zamani`; capa yoksa NaT) olcum betiklerinin tani
    sutunlari icindir; kural baska yerde yeniden kurulmasin diye buradan verilir.
    Saf.
    """
    from data import pencere as pencere_modulu

    girisler = pd.DatetimeIndex(girisler)
    sonlar = pd.DatetimeIndex(pencere_sonlari)
    baslar = pd.DatetimeIndex(donem_baslari)
    if not (len(girisler) == len(sonlar) == len(baslar)):
        raise ValueError("girisler, pencere_sonlari ve donem_baslari ayni uzunlukta olmali.")
    n = len(girisler)
    sonuc = pd.DataFrame({k: np.zeros(n, dtype=bool) for k in (*TAMLIK_KOSULLARI, "tam", *TAMLIK_BAYRAKLARI)})
    sonuc["capa_aralik_saat"] = np.full(n, np.nan)
    sonuc["son_aralik_saat"] = np.full(n, np.nan)
    sonuc["funding_ritmi_saat"] = np.full(n, np.nan)
    sonuc["ritim_sinifi"] = pd.Series([None] * n, index=sonuc.index, dtype=object)
    for k in TAMLIK_ZAMANLARI:
        sonuc[k] = pd.Series(pd.NaT, index=sonuc.index, dtype="datetime64[ns, UTC]")
    if n == 0 or funding.empty:
        return sonuc
    zamanlar = _zaman_dizisi(funding, "funding_tamlik_ayrintisi")
    aralik = pd.to_numeric(funding["aralik_saat"], errors="coerce").to_numpy(dtype=float)
    iyi = np.isfinite(aralik) & (aralik > 0)
    a_saat = np.where(iyi, aralik, 0.0)
    aralik_td = pd.to_timedelta(a_saat, unit="h")

    # Tek kenar tanimiyla (`ayni_an_sonu`): z < x + 1 dk <=> ayni_ya_da_once(z, x).
    j = zamanlar.searchsorted(pencere_modulu.ayni_an_sonu(girisler), side="left") - 1  # capa
    jj = np.maximum(j, 0)
    son_i = np.maximum(zamanlar.searchsorted(pencere_modulu.ayni_an_sonu(sonlar), side="left") - 1, jj)
    capa_var = (j >= 0) & np.asarray(pencere_modulu.ayni_ya_da_sonra(zamanlar[jj], baslar), dtype=bool)
    p_aralik = np.r_[0, np.cumsum(~iyi)]
    aralik_gecerli = capa_var & ((p_aralik[son_i + 1] - p_aralik[jj]) == 0)

    # Zincir: cift (i, i+1) icin sonraki kayit, onceki + iki araligin buyugunden SONRA olamaz.
    if len(zamanlar) > 1:
        adim = np.maximum(a_saat[1:], a_saat[:-1])
        kotu_cift = np.asarray(pencere_modulu.sonra(
            zamanlar[1:], zamanlar[:-1] + pd.to_timedelta(adim, unit="h")), dtype=bool)
    else:
        adim = np.zeros(0)
        kotu_cift = np.zeros(0, dtype=bool)
    p_cift = np.r_[0, np.cumsum(kotu_cift)]
    ilk_cift_var = son_i > jj
    # Ilk ciftten sonraki ciftler [jj + 1, son_i - 1]: p[son_i] - p[min(jj + 1, son_i)].
    sonraki_ciftler_kotu = (p_cift[son_i] - p_cift[np.minimum(jj + 1, son_i)]) > 0
    if len(adim):
        # Ilk cift (capa -> sonraki kayit): taban giris ani.
        k = np.minimum(jj, len(adim) - 1)
        ilk_adim = pd.to_timedelta(np.where(ilk_cift_var, adim[k], 0.0), unit="h")
        sonraki_kayit = zamanlar[np.minimum(jj + 1, len(zamanlar) - 1)]
        ilk_cift_kotu = ilk_cift_var & np.asarray(
            pencere_modulu.sonra(sonraki_kayit, girisler + ilk_adim), dtype=bool)
    else:
        ilk_cift_kotu = np.zeros(n, dtype=bool)
    zincir_tam = capa_var & aralik_gecerli & ~sonraki_ciftler_kotu & ~ilk_cift_kotu

    # Son: son kayit + araligi pencere sonundan ONCE olamaz (esitlik yeterli).
    sonraki = zamanlar[son_i] + aralik_td[son_i]
    son_tam = capa_var & aralik_gecerli & ~np.asarray(pencere_modulu.once(sonraki, sonlar), dtype=bool)
    tam = capa_var & aralik_gecerli & zincir_tam & son_tam

    sonuc["capa_var"] = capa_var
    sonuc["aralik_gecerli"] = aralik_gecerli
    sonuc["zincir_tam"] = zincir_tam
    sonuc["son_tam"] = son_tam
    sonuc["tam"] = tam
    dolmamis = tam & np.asarray(pencere_modulu.sonra(sonraki, sonlar), dtype=bool)
    son_kayit_sonda = np.asarray(pencere_modulu.ayni_an(zamanlar[son_i], sonlar), dtype=bool)
    sonuc["kuyruk_kismi"] = dolmamis & ~son_kayit_sonda
    sonuc["kuyruk_sifir"] = dolmamis & son_kayit_sonda
    sonuc["son_esitlik_affi"] = tam & np.asarray(pencere_modulu.ayni_an(sonraki, sonlar), dtype=bool)
    degisim = (aralik[1:] != aralik[:-1]) if len(aralik) > 1 else np.zeros(0, dtype=bool)
    p_degisim = np.r_[0, np.cumsum(degisim)]
    sonuc["capa_aralik_saat"] = np.where(capa_var, aralik[jj], np.nan)
    sonuc["son_aralik_saat"] = np.where(capa_var, aralik[son_i], np.nan)
    sonuc["tek_ritim"] = capa_var & ((p_degisim[son_i] - p_degisim[jj]) == 0)
    sonuc["funding_ritmi_saat"] = sonuc["son_aralik_saat"].to_numpy()
    sonuc["karisik_ritim"] = capa_var & ~sonuc["tek_ritim"].to_numpy(dtype=bool)
    sonuc["ritim_sinifi"] = pd.Series([ritim_sinifi(s) for s in sonuc["funding_ritmi_saat"].to_numpy()],
                                      index=sonuc.index, dtype=object)
    sonuc["capa_zamani"] = zamanlar[jj].where(capa_var)
    sonuc["son_kayit_zamani"] = zamanlar[son_i].where(capa_var)
    return sonuc


def pozisyon_funding_ayrintisi(funding: pd.DataFrame, plan) -> pd.Series:
    """Planin funding tamligi, kosullari ve bayraklariyla (on-kayit §4 rev.9): tek satir
    `funding_tamlik_ayrintisi`. Pencere `funding_penceresi_sonu`, capa tabani planin donem
    basi. Tek karar noktasi (`data.pozisyon.olay_karari`) bunu kullanir."""
    from data import pencere as pencere_modulu

    pencere_modulu.plan_dogrula(plan)
    return funding_tamlik_ayrintisi(funding, [plan.giris], [funding_penceresi_sonu(plan)],
                                    donem_baslari=[plan.donem_baslangic]).iloc[0]


def pozisyon_funding_tam_mi(funding: pd.DataFrame, plan) -> bool:
    """Planin funding'i tam mi (on-kayit §4 rev.9 "Funding tamligi")? Yalnizca odeme
    zamani ve araligi okunur."""
    return bool(pozisyon_funding_ayrintisi(funding, plan)["tam"])


def pozisyon_fundingi(funding: pd.DataFrame, pozisyon) -> float:
    """Onayli pozisyonun funding toplami (net getirinin funding girdisi; on-kayit §4).

    YALNIZCA `pozisyon.olay_karari`nin urettigi `OnaylanmisPozisyon`u kabul eder (kapi sertlestirme
    turu, denetci F1K2 D-B3): kapidan gecmemis bir plan (`pencere.pozisyon_plani` ciktisi) TypeError
    verir. Toplam `_plan_fundingi` ile yeniden hesaplanir ve kararin `funding_toplami` degeriyle ayni
    olmalidir; degilse `funding` karardakiyle ayni seri degildir (ValueError). Saf fonksiyon.
    """
    from data import pozisyon as pozisyon_modulu

    pozisyon_modulu.onay_dogrula(pozisyon)
    toplam = _plan_fundingi(funding, pozisyon.plan)
    if not toplam == pozisyon.funding_toplami:
        raise ValueError("funding serisi karar noktasindakiyle ayni degil: toplam "
                         f"{toplam!r} != onayli {pozisyon.funding_toplami!r}.")
    return toplam


def _plan_fundingi(funding: pd.DataFrame, plan) -> float:
    """Short pozisyonun tuttugu sure boyunca aldigi (+) ya da odedigi (-) funding.

    On-kayit §4: her funding aninda `+oran` (GERCEK odeme orani, `oran`;
    8 saate normallestirilmis `oran_8h` kullanilmaz). Toplam doner.

    MODUL DISINA KAPALI ic adim: yalnizca tek karar noktasi (`pozisyon.olay_karari`) cagirir;
    getiri tarafi funding'i onayli pozisyondan (`funding_toplami` ya da `pozisyon_fundingi`) okur.
    Testler dogrudan cagirabilir; analiz kodu icin kaynak taramasinda yasaklidir.

    Yalnizca `pencere.pozisyon_plani`nin urettigi PLANI alir. Sinirlar (on-kayit §4
    rev.8): giris anindaki odeme HARIC, cikis anindaki DAHIL; donem sonuna ulasan
    pozisyonda pencere B'de (dahil) kapanir. Tamlik `funding_tamlik_ayrintisi`dir (rev.9).

    NaN yalnizca VERI EKSIKLIGIDIR (tamlik saglanmadi ya da oran NaN). Plan olmayan
    girdi TypeError, degistirilmis plan ValueError, bozuk zaman dizisi
    `ZamanDizisiHatasi`. Saf fonksiyon.
    """
    from data import pencere as pencere_modulu

    pencere_modulu.plan_dogrula(plan)
    zamanlar = _zaman_dizisi(funding, "_plan_fundingi")
    if not pozisyon_funding_tam_mi(funding, plan):
        return float("nan")
    maske = (np.asarray(sonra(zamanlar, plan.giris), dtype=bool)
             & np.asarray(ayni_ya_da_once(zamanlar, funding_penceresi_sonu(plan)), dtype=bool))
    oran = pd.to_numeric(funding.loc[maske, "oran"], errors="coerce")
    if oran.isna().any():
        return float("nan")
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
