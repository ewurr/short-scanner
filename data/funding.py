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
    """
    from data import split as split_modulu  # split, klines uzerinden bu katmani import eder

    izinli, bas, son = split_modulu.kume_erisimi(sembol, kume, onay=onay)
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


# --- Funding penceresi (H2.1) ------------------------------------------------

# Ayni odeme anina ait kayitlarin kayabilecegi en buyuk fark. Iki odeme arasindaki
# en kisa gercek aralik 1 saattir; 1 dakikadan yakin iki kayit bozuk veridir.
ODEME_TOLERANSI = pd.Timedelta(minutes=1)


def funding_ortalamasi(
    funding: pd.DataFrame,
    t,
    bar: str,
    *,
    saat: int,
    kume_baslangic,
    donem_baslangic,
    karantina_aylari,
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
      - **Karantina.** Pencerenin dokundugu aylardan biri karantinadaysa NaN.
      - **Tamlik.** Penceredeki odemeler boslugsuz olmali; her kaydin
        `aralik_saat` degeri bir onceki odemeye kadar olan sureyi verir:
          * ilk odemeden onceki odeme (ilk - aralik) pencereden ONCE olmali,
          * ardisik iki odeme arasinda aralik + tolerans'tan uzun bosluk olmamali,
          * son odemeden sonraki odeme (son + aralik) kapanistan once olmamali.
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
    karantina = pencere_modulu.karantina_dogrula(karantina_aylari)

    kapanis = zaman + pencere_modulu.adim(bar)
    bas = kapanis - pd.Timedelta(hours=saat)
    nan = float("nan")

    if donem_bas is not None and bas < donem_bas:
        return nan
    if kume_bas is not None and bas < kume_bas:
        return nan
    if karantina:
        from data import donem as donem_modulu

        karantina_aylari_kumesi = {donem_modulu.ay_donemi(a) for a in karantina}
        aylar = pd.period_range(bas.tz_localize(None), (kapanis - pd.Timedelta(1, "ns")).tz_localize(None), freq="M")
        if any(ay in karantina_aylari_kumesi for ay in aylar):
            return nan

    zamanlar = pencere_modulu._zaman_dizisi_dogrula(funding["odeme_zamani"], "funding_ortalamasi")
    if len(zamanlar) > 1:
        farklar = zamanlar[1:] - zamanlar[:-1]
        if (farklar < ODEME_TOLERANSI).any():
            ilk = int((farklar < ODEME_TOLERANSI).argmax())
            raise pencere_modulu.ZamanDizisiHatasi(
                f"funding_ortalamasi: {zamanlar[ilk]} ve {zamanlar[ilk + 1]} birbirine "
                f"{ODEME_TOLERANSI}'dan yakin; ayni odeme iki kez yazilmis olabilir (bozuk veri)."
            )

    maske = (zamanlar >= bas) & (zamanlar < kapanis)
    if not maske.any():
        return nan
    secili = funding.loc[maske]
    oran = pd.to_numeric(secili["oran_8h"], errors="coerce")
    aralik = pd.to_numeric(secili["aralik_saat"], errors="coerce")
    if oran.isna().any() or aralik.isna().any() or (aralik <= 0).any():
        return nan

    odemeler = zamanlar[maske]
    araliklar = pd.to_timedelta(aralik.to_numpy(), unit="h")
    if not odemeler[0] - araliklar[0] < bas:
        return nan  # pencerenin basindaki odeme eksik
    if len(odemeler) > 1 and ((odemeler[1:] - araliklar[1:]) > odemeler[:-1] + ODEME_TOLERANSI).any():
        return nan  # ic bosluk
    if odemeler[-1] + araliklar[-1] < kapanis:
        return nan  # pencerenin sonundaki odeme eksik
    return float(oran.mean())


# --- Pozisyon funding'i (on-kayit §4 rev.6) ----------------------------------


def pozisyon_fundingi(
    funding: pd.DataFrame,
    giris_zamani,
    cikis,
    bar: str,
    *,
    kume_baslangic,
    kume_bitis,
    donem_baslangic,
    donem_bitis,
    karantina_aylari,
) -> float:
    """Short pozisyonun tuttugu sure boyunca aldigi (+) ya da odedigi (-) funding.

    On-kayit §4: her funding aninda `+oran` (GERCEK odeme orani, `oran`;
    8 saate normallestirilmis `oran_8h` kullanilmaz). Toplam doner.

    Sinirlar (on-kayit §4 rev.6):
      - Giris anindaki odeme HARIC, cikis anindaki DAHIL.
      - 1 dakikadan kucuk kayma ayni an sayilir. Odeme p dahildir ancak ve ancak
        `giris + 1 dk <= p < cikis_ani + 1 dk`.
      - Giris ani t+1 barinin acilisi (`giris_zamani`); cikis ani
        `pencere.cikis_ani(cikis, bar)`: kapanistan cikista barin kapanisi,
        ileri kaymali cikista barin acilisi.

    Korumalar (`funding_ortalamasi` ve `pencere.cikis_bari` ile ayni):
      - **Kume.** Odeme araligi kume baslangicindan once basliyor ya da kume
        sonunu asiyorsa `KumeSiniriHatasi` (rev.6: "cikis anindaki odeme kumenin
        tarih araligi disina dusuyorsa olay o kumede olusmaz"; `cikis_bari` ile
        ayni istisna). Kontrol ZAMANLA yapilir, verinin kume sinirinda kesilmis
        olmasina dayanilmaz (rev.5).
      - **Donem ve karantina.** Odeme araligi donem disina tasiyor ya da bir
        karantina ayina dokunuyorsa NaN (olay olusmaz). Sinir anlarla olculur:
        karantinadan onceki son barin kapanisi karantina ayinin ilk anidir ve o
        andaki odeme karantina ayina duser.
      - **Tamlik.** Aralikta beklenen odemelerin tamami bulunmali; her kaydin
        `aralik_saat` degeri bir onceki odemeye kadar olan sureyi verir:
          * ilk odemeden onceki odeme (ilk - aralik) araliktan ONCE olmali,
          * ardisik iki odeme arasinda aralik + tolerans'tan uzun bosluk olmamali,
          * son odemeden sonraki odeme (son + aralik) araliktan SONRA olmali.
        Aralikta hic odeme yoksa, araliktan onceki son odemenin bir sonrakinin
        araliktan sonra oldugu gosterilmeli. Eksik odeme, NaN oran ya da NaN
        aralik -> NaN. Bir dakikadan yakin iki kayit bozuk veridir ->
        ZamanDizisiHatasi.
      - Tum sinirlar zorunlu anahtar sozcuktur; sinir yoksa acikca None.
        Saat dilimsiz zaman TypeError.

    Saf fonksiyon.
    """
    from data import donem as donem_modulu
    from data import pencere as pencere_modulu

    giris = pencere_modulu.utc_zamani(giris_zamani, "giris_zamani")
    son_an = pencere_modulu.cikis_ani(cikis, bar)
    kume_bas = pencere_modulu.sinir_zamani(kume_baslangic, "kume_baslangic")
    kume_son = pencere_modulu.sinir_zamani(kume_bitis, "kume_bitis")
    donem_bas = pencere_modulu.sinir_zamani(donem_baslangic, "donem_baslangic")
    donem_son = pencere_modulu.sinir_zamani(donem_bitis, "donem_bitis")
    karantina = pencere_modulu.karantina_dogrula(karantina_aylari)
    if not son_an > giris:
        raise ValueError(f"Cikis ani giristen sonra olmali: giris {giris}, cikis {son_an}")

    alt = giris + ODEME_TOLERANSI  # dahil
    ust = son_an + ODEME_TOLERANSI  # haric
    son_dahil = ust - pd.Timedelta(1, "ns")
    nan = float("nan")

    if kume_bas is not None and giris < kume_bas:
        raise pencere_modulu.KumeSiniriHatasi(
            f"Giris {giris} kume baslangicindan ({kume_bas}) once (on-kayit §3 rev.4)."
        )
    if kume_son is not None and son_dahil > kume_son:
        raise pencere_modulu.KumeSiniriHatasi(
            f"Cikis anindaki funding odemesi ({son_an}) kume sonunu ({kume_son}) asiyor "
            "(on-kayit §4 rev.6: olay bu kumede olusmaz)."
        )
    if donem_bas is not None and giris < donem_bas:
        return nan
    if donem_son is not None and son_dahil > donem_son:
        return nan
    if karantina:
        karantina_kumesi = {donem_modulu.ay_donemi(a) for a in karantina}
        aylar = pd.period_range(giris.tz_localize(None), son_dahil.tz_localize(None), freq="M")
        if any(ay in karantina_kumesi for ay in aylar):
            return nan

    zamanlar = pencere_modulu._zaman_dizisi_dogrula(funding["odeme_zamani"], "pozisyon_fundingi")
    if len(zamanlar) > 1:
        farklar = zamanlar[1:] - zamanlar[:-1]
        if (farklar < ODEME_TOLERANSI).any():
            ilk = int((farklar < ODEME_TOLERANSI).argmax())
            raise pencere_modulu.ZamanDizisiHatasi(
                f"pozisyon_fundingi: {zamanlar[ilk]} ve {zamanlar[ilk + 1]} birbirine "
                f"{ODEME_TOLERANSI}'dan yakin; ayni odeme iki kez yazilmis olabilir (bozuk veri)."
            )

    maske = (zamanlar >= alt) & (zamanlar < ust)
    if not maske.any():
        # Aralikta odeme yok: bu ancak araliktan onceki son odemenin bir
        # sonrakinin araliktan sonra oldugu gosterilebilirse gecerlidir. Sonraki
        # odeme kume disinda olabilecegi icin okunmaz; onceki odemenin araliginin
        # degismedigi varsayilir (`funding_ortalamasi`nin son odeme kontroluyle
        # ayni varsayim). Kume ve donem oncesi kayitlar okunmaz.
        taban = max((s for s in (kume_bas, donem_bas) if s is not None), default=None)
        onceki = (zamanlar < alt) if taban is None else ((zamanlar < alt) & (zamanlar >= taban))
        if not onceki.any():
            return nan
        konum = int(np.flatnonzero(onceki)[-1])
        aralik = pd.to_numeric(pd.Series([funding["aralik_saat"].iloc[konum]]), errors="coerce").iloc[0]
        if pd.isna(aralik) or aralik <= 0:
            return nan
        if zamanlar[konum] + pd.Timedelta(hours=float(aralik)) < ust:
            return nan  # aralikta beklenen odeme eksik
        return 0.0

    secili = funding.loc[maske]
    oran = pd.to_numeric(secili["oran"], errors="coerce")
    aralik = pd.to_numeric(secili["aralik_saat"], errors="coerce")
    if oran.isna().any() or aralik.isna().any() or (aralik <= 0).any():
        return nan

    odemeler = zamanlar[maske]
    araliklar = pd.to_timedelta(aralik.to_numpy(), unit="h")
    if not odemeler[0] - araliklar[0] < alt:
        return nan  # araligin basindaki odeme eksik
    if len(odemeler) > 1 and ((odemeler[1:] - araliklar[1:]) > odemeler[:-1] + ODEME_TOLERANSI).any():
        return nan  # ic bosluk
    if odemeler[-1] + araliklar[-1] < ust:
        return nan  # araligin sonundaki odeme eksik
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
