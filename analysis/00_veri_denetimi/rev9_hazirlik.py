"""Rev.9 hazirligi: onerilen funding tamlik kuralinin ve T = K durumunun etkisi. YALNIZCA SAYI.

Getiri, fiyat farki ya da funding degeri HESAPLAMAZ ve raporlamaz. Mumlardan acilis
zamani ve (donem sonu turu icin) hacmin sifir olup olmadigi, funding kayitlarindan
odeme zamani ve aralik alani okunur (CLAUDE.md §3.1, RESULTS §14.9). Veri katmani
DEGISMEZ: plan gercek `pencere.pozisyon_plani`, zaman karsilastirmalari gercek `pencere`
yardimcilaridir. Rev.8 tamligi Rev.9 koda gectikten sonra `rev8_tamlik.rev8_tamlik_ayrintisi`
(tarihsel donmus kopya, `rev8_*` sutunlari) ile olculur. Onerilen kural yalnizca bu betikteki `oneri_tamlik_ayrintisi`
olcum fonksiyonundadir; hicbir karar yolunda kullanilmaz.

Onerilen kural (rev.8 "baslangic boslugu" ve "penceresinde hic kayit yoksa tam degil"
cumlelerinin yerine):
  - Giristen onceki son donem ici kayittan pencere sonuna kadar olan kayit dizisi
    degerlendirilir.
  - Ardisik iki kayit arasindaki bosluk, iki kaydin araliklarindan buyugunu ve
    toleransi asarsa eksik.
  - Son kayittan sonra aralik + tolerans pencere sonundan once doluyorsa eksik.
  - Giristen once donem icinde kayit yoksa eksik.
Olcumdeki okuma: "giristen onceki" = giris ani ile ayni an ya da once (giris anindaki
odeme pozisyona girmez ama dizinin capasi olabilir); "donem ici" = donem basi ile
ayni an ya da sonra (kume basi taban degildir); son kosul `once(son + aralik,
pencere sonu)` ise eksik (esitlikte tam). Iki okuma ayrica sayilir: capa kesin
once (`kati`) ve son kosulu rev.8'deki gibi (`rev8_son`: esitlikte eksik).

Ciktilar:
1. `rev9_donem_sonu_tam.csv`: donem sonuna ulasan temsili pozisyon (A1 ile ayni
   `a1_olcumu.temsili_plan`), her donem sonu ve izgara; rev.8 ve oneri kosullari.
2. `rev9_baslangic_tam.csv`: butun donem ici barlar (1d'de gunler) varsayimsal
   sinyal, birincil ufuk (rev8_etki ile ayni evren); sembol x izgara x kume sayimi.
3. `rev9_farklar_tam.csv`: iki kuralin farkli hukum verdigi pozisyonlar (yalnizca
   zaman damgasi ve tur).
4. `rev9_tk_tam.csv`: T = K olan pozisyonlar (her donem, her izgara ve ufuk icin tek
   sinyal): donem sonu cikisi sayilsaydi funding penceresi (giris, K] -> (giris, B].

Besinci tur (capa duzeltmesi, `capa_duzeltme_tamlik_ayrintisi`): ayni ciktilara
`capa_duzeltme_*` sutunlari eklenir. Dorduncu turun tanimina tek cumle eklenir: "Capa ile
sonraki kayit arasindaki bosluk degerlendirilirken, giris aninda ya da oncesinde dusen
eksik odemeler dikkate alinmaz: bu boslugun olcumu giris anindan baslar." Yani dizideki
ilk ciftin (capa -> sonraki kayit) boslugu capadan degil giristen olculur; geri kalan
ciftler ve son kosul degismez. Onceki turlarin sutunlari korunur.

Dorduncu tur (tahmin etmeyen tanim, `tahmin_yok_tamlik_ayrintisi`): ayni ciktilara
`tahmin_yok_*` sutunlari eklenir. Tanim: capa (giris aninda ya da oncesinde, donem icindeki
son kayit); capadan pencere sonuna kadar ardisik iki kayit arasindaki bosluk ikisinin
araligindan buyugunu ve toleransi asarsa eksik; penceredeki son kayittan sonra o kaydin
araligi artı tolerans pencere sonundan ONCE doluyorsa eksik (tam pencere sonuna denk
gelirse eksik degil); baska hicbir yerde beklenen odeme ani uretilmez. Pencere sonu donem
sonu cikislarinda ve T >= K pozisyonlarda B.

Bu tanim, birinci turun onerisiyle (`oneri_tamlik_ayrintisi`, `kati_onceki=False`,
`son_kurali="oneri"`) AYNI kuraldir; tek fark pencere sonunun T >= K pozisyonlarda B'ye
cekilmesidir (`tests/test_rev9_tahmin_yok.py` bunu sabitler). Gevseklik olcusu sutunlari:
`kuyruk_dogrulanmamis` (son kayittan pencere sonuna kadar bir tam aralik dolmamis),
`son_esitlik_affi` (tam olarak dolmus ve orada kayit yok), `aralik_degisimi_var`.

Ucuncu tur (adim tanimi, `son_adim_tamlik_ayrintisi`): ayni ciktilara `son_adim_*`
sutunlari eklenir. Tanim:
  - Capa: giris aninda ya da oncesinde, donem icindeki son kayit. Yoksa eksik.
  - Beklenen anlar capadan baslar. Bir beklenen anda kayit varsa sonraki adim o kaydin
    araligidir; kayit yoksa adim son bilinen kaydin araligiyla surer.
  - Giris anindan sonra ve pencere sonunda ya da oncesinde dusen bir beklenen anda kayit
    yoksa eksik. Giris aninda ya da oncesinde dusen beklenen anlarda kayit yoklugu
    tamligi bozmaz.
  - Pencere sonu donem sonu cikislarinda B'dir; T >= K olan her pozisyon donem sonu
    cikisidir (`son_hal_pencere_sonu`).
`rev9_sinir_tam.csv`: tanimin sinir durumlarinin veri taramasi (aralik gecisleri, zincirin
atladigi kayitlar, tolerансla eslesen anlar, donem basindaki capa). Yalnizca sayi ve zaman.

Ikinci tur (son hal, `son_hal_tamlik_ayrintisi`): ayni ciktilara `son_hal_*` sutunlari
eklenir. Tanim:
  - Beklenen odeme anlari, giristen onceki (giris ani dahil) son donem ici kayittan
    baslayarak kayit dizisi boyunca uretilir; aralik gecislerinde adim iki kaydin
    araliklarindan buyugudur.
  - Giris anindan sonra ve pencere sonuna kadar (pencere sonu dahil) dusen her beklenen
    anda bir kayit bulunmali; yoksa eksik. Tolerans kurali gecerlidir.
  - Giristen once (giris ani dahil) donem icinde kayit yoksa eksik.
  - Donem sonu cikislarinda pencere sonu B'dir; T >= K olan her pozisyon donem sonu
    cikisi sayilir (`son_hal_pencere_sonu`).
2026-06-24 04:00 boslugunun etkisi karsi-olgusal seriyle sayilir: kaydi eksik olan
sembolde o ana, 00:00 kaydinin araligiyla tek bir yapay kayit (yalnizca zaman ve aralik)
eklenir ve tamlik yeniden olculur (`bosluk_seri`). Yapay kayit hicbir baska yere girmez.

Kullanim:
    python analysis/00_veri_denetimi/rev9_hazirlik.py --is-parcaci 8
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

KOK = Path(__file__).resolve().parents[2]
BU_DIZIN = Path(__file__).resolve().parent
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(BU_DIZIN))

import config  # noqa: E402
from a1_olcumu import temsili_plan  # noqa: E402
from calistir import (KosuKilidiHatasi, csv_yaz, donem_sonu_turleri, git_durumu,  # noqa: E402
                      kosu_kilidi, ortam_kaydi)
from data import donem as donem_modulu  # noqa: E402
from data import funding as funding_modulu  # noqa: E402
from data import klines as klines_modulu  # noqa: E402
from data import pencere as pencere_modulu  # noqa: E402
from data import split as split_modulu  # noqa: E402
from data import universe as universe_modulu  # noqa: E402
from rev8_etki import kume_sinirlari, sinyal_kumesi  # noqa: E402
from rev8_tamlik import REV8_TAMLIK_KOSULLARI, rev8_pencere_sonu, rev8_tamlik_ayrintisi  # noqa: E402

P = pencere_modulu
CIKTI_DONEM_SONU = BU_DIZIN / "rev9_donem_sonu_tam.csv"
CIKTI_BASLANGIC = BU_DIZIN / "rev9_baslangic_tam.csv"
CIKTI_FARKLAR = BU_DIZIN / "rev9_farklar_tam.csv"
CIKTI_TK = BU_DIZIN / "rev9_tk_tam.csv"
CIKTI_SINIR = BU_DIZIN / "rev9_sinir_tam.csv"
CIKTI_ORTAM = BU_DIZIN / "rev9_ortam_tam.csv"

ONERI_KOSULLARI = ("onceki_var", "aralik_gecerli", "zincir_tam", "son_tam")
# Raporlanan ufuklar (on-kayit §4 tablo: birincil ve ikincil).
UFUKLAR = {config.BAR_4H: (6, 18, 42), config.BAR_1D: (7, 14, 30)}


# --- Onerilen kural (yalnizca olcum) -------------------------------------------------


def oneri_tamlik_ayrintisi(funding: pd.DataFrame, girisler, pencere_sonlari, donem_baslari, *,
                           kati_onceki: bool = False, son_kurali: str = "oneri") -> pd.DataFrame:
    """Onerilen funding tamlik kurali, kosul kosul. Vektorel, saf; yalnizca odeme ZAMANI ve
    ARALIGI okunur. Zaman karsilastirmalari `pencere` yardimcilariyla.

    Dizi: capa (giristen onceki son donem ici kayit) ve pencere sonuyla ayni an ya da
    once olan butun kayitlar.
      - `onceki_var`: capa var ve donem basi ile ayni an ya da sonra. `kati_onceki`
        ise capa giristen kesin once (`once`), degilse ayni an ya da once.
      - `aralik_gecerli`: dizideki araliklar sonlu ve > 0.
      - `zincir_tam`: ardisik her iki kayitta sonraki, onceki + iki araligin buyugunden
        SONRA degil (capa -> ilk kayit cifti dahil).
      - `son_tam`: `son_kurali="oneri"`: son kayit + araligi pencere sonundan ONCE
        degil; `"rev8"`: pencere sonundan SONRA (rev.8 `son_tam` ile ayni).
      - `son_esit`: son kayit + araligi pencere sonuyla ayni an (iki son kuralinin
        ayrildigi yer).
    """
    if son_kurali not in ("oneri", "rev8"):
        raise ValueError(f"son_kurali: {son_kurali!r}")
    girisler = pd.DatetimeIndex(girisler)
    sonlar = pd.DatetimeIndex(pencere_sonlari)
    baslar = pd.DatetimeIndex(donem_baslari)
    if not (len(girisler) == len(sonlar) == len(baslar)):
        raise ValueError("girisler, pencere_sonlari ve donem_baslari ayni uzunlukta olmali.")
    n = len(girisler)
    sonuc = pd.DataFrame({k: np.zeros(n, dtype=bool) for k in (*ONERI_KOSULLARI, "son_esit", "tam")})
    if n == 0 or funding.empty:
        return sonuc
    zamanlar = funding_modulu._zaman_dizisi(funding, "oneri_tamlik_ayrintisi")
    aralik = pd.to_numeric(funding["aralik_saat"], errors="coerce").to_numpy(dtype=float)
    iyi = np.isfinite(aralik) & (aralik > 0)
    aralik_td = pd.to_timedelta(np.where(iyi, aralik, 0.0), unit="h")

    # Capa: kati ise z <= giris - 1 dk (`once`), degilse z < giris + 1 dk (ayni an ya da once).
    if kati_onceki:
        j = zamanlar.searchsorted(P.ayni_an_basi(girisler), side="right") - 1
    else:
        j = zamanlar.searchsorted(P.ayni_an_sonu(girisler), side="left") - 1
    hi = zamanlar.searchsorted(P.ayni_an_sonu(sonlar), side="left")  # pencere sonuyla ayni an ya da once
    jj = np.maximum(j, 0)
    onceki_var = (j >= 0) & np.asarray(P.ayni_ya_da_sonra(zamanlar[jj], baslar), dtype=bool)
    son_i = np.maximum(hi - 1, jj)  # capa varsa hi - 1 >= j (giris <= pencere sonu)

    p_aralik = np.r_[0, np.cumsum(~iyi)]
    aralik_gecerli = onceki_var & ((p_aralik[son_i + 1] - p_aralik[jj]) == 0)

    if len(zamanlar) > 1:
        beklenen = zamanlar[:-1] + pd.to_timedelta(np.maximum(aralik_td[1:].to_numpy(), aralik_td[:-1].to_numpy()))
        kotu_bosluk = np.asarray(P.sonra(zamanlar[1:], beklenen), dtype=bool)
    else:
        kotu_bosluk = np.zeros(0, dtype=bool)
    p_bosluk = np.r_[0, np.cumsum(kotu_bosluk)]  # ciftler [jj, son_i - 1] -> p[son_i] - p[jj]
    zincir_tam = onceki_var & ((p_bosluk[son_i] - p_bosluk[jj]) == 0)

    sonraki = zamanlar[son_i] + aralik_td[son_i]
    if son_kurali == "oneri":
        son_ok = ~np.asarray(P.once(sonraki, sonlar), dtype=bool)
    else:
        son_ok = np.asarray(P.sonra(sonraki, sonlar), dtype=bool)
    son_tam = onceki_var & son_ok & aralik_gecerli

    sonuc["onceki_var"] = onceki_var
    sonuc["aralik_gecerli"] = aralik_gecerli
    sonuc["zincir_tam"] = zincir_tam & aralik_gecerli
    sonuc["son_tam"] = son_tam
    sonuc["son_esit"] = onceki_var & np.asarray(P.ayni_an(sonraki, sonlar), dtype=bool)
    sonuc["tam"] = onceki_var & aralik_gecerli & zincir_tam & son_tam
    return sonuc


def fark_turu(rev8: pd.Series, oneri: pd.Series) -> str | None:
    """Iki kuralin hukmu farkliysa farkin turu; ayniysa None. Saf.

    Oneriye gore tam, rev.8'e gore degil:
      - `kayitsiz_kisa_pencere`: pencerede kayit yok (rev.8 `kayit_var` bozuk).
      - `diger_son_esitlik`: rev.8 yalnizca `son_tam`'da bozuk ve son + aralik = pencere sonu.
      - `diger_baslangic_araligi`: rev.8 `baslangic_tam` bozuk (ilk kaydin araligi kisa,
        capa + iki araligin buyugu yetiyor).
      - `diger`.
    Rev.8'e gore tam, oneriye gore degil:
      - `gec_baslayan_funding`: giristen once donem icinde kayit yok.
      - `diger_giris_oncesi_bosluk`: capa -> ilk kayit boslugu kurali asiyor.
      - `diger`.
    """
    if bool(rev8["tam"]) == bool(oneri["tam"]):
        return None
    if oneri["tam"]:
        if not rev8["kayit_var"]:
            return "kayitsiz_kisa_pencere"
        if (rev8["baslangic_tam"] and rev8["ic_tam"] and rev8["aralik_gecerli"] and not rev8["son_tam"]
                and oneri["son_esit"]):
            return "diger_son_esitlik"
        if not rev8["baslangic_tam"]:
            return "diger_baslangic_araligi"
        return "diger"
    if not oneri["onceki_var"]:
        return "gec_baslayan_funding"
    if not oneri["zincir_tam"]:
        return "diger_giris_oncesi_bosluk"
    return "diger"


FARK_TURLERI = ("kayitsiz_kisa_pencere", "diger_son_esitlik", "diger_baslangic_araligi", "gec_baslayan_funding",
                "diger_giris_oncesi_bosluk", "diger")



SON_HAL_KOSULLARI = ("onceki_var", "aralik_gecerli", "beklenen_tam")


def _eslesen_kayit_var(zamanlar: pd.DatetimeIndex, anlar) -> np.ndarray:
    """Her an icin onunla ayni an (`pencere.ayni_an`) bir kayit var mi. Saf, vektorel."""
    anlar = pd.DatetimeIndex(anlar)
    if len(zamanlar) == 0 or len(anlar) == 0:
        return np.zeros(len(anlar), dtype=bool)
    i = zamanlar.searchsorted(P.ayni_an_basi(anlar), side="right")
    ic = i < len(zamanlar)
    sonuc = np.zeros(len(anlar), dtype=bool)
    sonuc[ic] = np.asarray(zamanlar[i[ic]] < P.ayni_an_sonu(anlar[ic]), dtype=bool)
    return sonuc


def son_hal_tamlik_ayrintisi(funding: pd.DataFrame, girisler, pencere_sonlari, donem_baslari) -> pd.DataFrame:
    """Tamlik kuralinin son hali (Rev.9 hazirligi, ikinci tur), kosul kosul. Vektorel, saf;
    yalnizca odeme ZAMANI ve ARALIGI okunur. Pencere sonunu cagiran verir (donem sonu
    cikislarinda ve T >= K pozisyonlarda B).

    - Beklenen odeme anlari, capadan (giris ani dahil, giristen onceki son donem ici kayit)
      baslayarak kayit dizisi boyunca uretilir: dizideki her kayit i icin beklenen an
      `z_i + adim_i`; `adim_i`, dizide sonraki kayit varsa iki kaydin araliklarindan buyugu,
      yoksa (dizinin son kaydi) kendi araligi. Dizi: capa ve pencere sonuyla ayni an ya da
      once olan butun kayitlar. Dizinin son kaydinda sonraki kaydin araligi okunmaz
      (pencere sonundan sonrasi okunmaz).
    - `beklenen_tam`: giris anindan SONRA ve pencere sonuyla ayni an ya da ONCE olan her
      beklenen anda, onunla ayni an bir kayit var.
    - `onceki_var`: capa var ve donem basi ile ayni an ya da sonra.
    - `aralik_gecerli`: dizideki araliklar sonlu ve > 0.
    - `kopuk_giris_oncesi` (bilgi, `tam`a girmez): capanin beklenen ani giris ile ayni an
      ya da once ve orada kayit yok. Bu durumda metin pencere icin beklenen an uretmez;
      kosul yalnizca sayilir.
    """
    girisler = pd.DatetimeIndex(girisler)
    sonlar = pd.DatetimeIndex(pencere_sonlari)
    baslar = pd.DatetimeIndex(donem_baslari)
    if not (len(girisler) == len(sonlar) == len(baslar)):
        raise ValueError("girisler, pencere_sonlari ve donem_baslari ayni uzunlukta olmali.")
    n = len(girisler)
    sonuc = pd.DataFrame({k: np.zeros(n, dtype=bool) for k in (*SON_HAL_KOSULLARI, "kopuk_giris_oncesi", "tam")})
    if n == 0 or funding.empty:
        return sonuc
    zamanlar = funding_modulu._zaman_dizisi(funding, "son_hal_tamlik_ayrintisi")
    m = len(zamanlar)
    aralik = pd.to_numeric(funding["aralik_saat"], errors="coerce").to_numpy(dtype=float)
    iyi = np.isfinite(aralik) & (aralik > 0)
    a_saat = np.where(iyi, aralik, 0.0)
    # Kayit basina iki beklenen an: sonraki kayit dizideyse (ic) ve dizinin sonuysa (son).
    ic_adim = np.r_[np.maximum(a_saat[:-1], a_saat[1:]), a_saat[-1:]]
    beklenen_ic = zamanlar + pd.to_timedelta(ic_adim, unit="h")
    beklenen_son = zamanlar + pd.to_timedelta(a_saat, unit="h")
    esles_ic = _eslesen_kayit_var(zamanlar, beklenen_ic)
    esles_son = _eslesen_kayit_var(zamanlar, beklenen_son)

    j = zamanlar.searchsorted(P.ayni_an_sonu(girisler), side="left") - 1
    son_i = zamanlar.searchsorted(P.ayni_an_sonu(sonlar), side="left") - 1
    jj = np.maximum(j, 0)
    ll = np.maximum(son_i, jj)
    onceki_var = (j >= 0) & np.asarray(P.ayni_ya_da_sonra(zamanlar[jj], baslar), dtype=bool)
    p_aralik = np.r_[0, np.cumsum(~iyi)]
    aralik_gecerli = onceki_var & ((p_aralik[ll + 1] - p_aralik[jj]) == 0)

    def _ihlal(an, esles):
        gerekli = (np.asarray(P.sonra(an, girisler), dtype=bool)
                   & np.asarray(P.ayni_ya_da_once(an, sonlar), dtype=bool))
        return gerekli & ~esles, gerekli

    # Capa: dizide sonraki kayit varsa ic adim, yoksa son adim.
    capa_ic = ll > jj
    capa_an = pd.DatetimeIndex(np.where(capa_ic, beklenen_ic[jj].asi8, beklenen_son[jj].asi8)).tz_localize("UTC")
    capa_esles = np.where(capa_ic, esles_ic[jj], esles_son[jj])
    capa_ihlal, capa_gerekli = _ihlal(capa_an, capa_esles)
    kopuk = onceki_var & ~np.asarray(P.sonra(capa_an, girisler), dtype=bool) & ~capa_esles
    # Son kayit (capadan farkliysa): son adim.
    son_an = beklenen_son[ll]
    son_ihlal, _ = _ihlal(son_an, esles_son[ll])
    son_ihlal &= capa_ic
    # Ara kayitlar (jj, ll): giristen sonra; ic adim. Adaylar onek toplamiyla, kesin kontrol dongude.
    p_esles = np.r_[0, np.cumsum(~esles_ic)]
    aday = capa_ic & ((p_esles[ll] - p_esles[np.minimum(jj + 1, ll)]) > 0)
    ara_ihlal = np.zeros(n, dtype=bool)
    for k in np.flatnonzero(aday):
        i = np.arange(jj[k] + 1, ll[k])
        i = i[~esles_ic[i]]
        if len(i):
            ara_ihlal[k] = bool(np.any(np.asarray(P.ayni_ya_da_once(beklenen_ic[i], sonlar[k]), dtype=bool)))
    beklenen_tam = onceki_var & ~(capa_ihlal | son_ihlal | ara_ihlal)

    sonuc["onceki_var"] = onceki_var
    sonuc["aralik_gecerli"] = aralik_gecerli
    sonuc["beklenen_tam"] = beklenen_tam & aralik_gecerli
    sonuc["kopuk_giris_oncesi"] = kopuk
    sonuc["tam"] = onceki_var & aralik_gecerli & beklenen_tam
    return sonuc


def son_hal_pencere_sonu(cikis_ani, cikis_turu: str, donem_bitis, donem_kapanis) -> pd.Timestamp:
    """Son halde funding penceresinin sonu: donem sonu cikisinda ve T >= K olan pozisyonda
    (bugun olagan cikis sayilan T = K dahil) B, aksi halde gercek cikis ani. Saf."""
    if cikis_turu == "donem_sonu" or (cikis_turu == "olagan" and P.ayni_an(cikis_ani, donem_kapanis)):
        return pd.Timestamp(donem_bitis)
    return pd.Timestamp(cikis_ani)


def son_hal_fark_turu(rev8: pd.Series, son_hal: pd.Series, t_esit_k: bool, oneri_tam: bool = False) -> str | None:
    """Son hal ile rev.8'in hukmu farkliysa farkin turu; ayniysa None. Saf.

    Son hale gore tam, rev.8'e gore degil: `t_esit_k` (pencere sonu K -> B),
    `kayitsiz_kisa_pencere`, `baslangic_araligi` (rev.8 baslangic kosulu), `diger`.
    Rev.8'e gore tam, son hale gore degil: `t_esit_k`, `gec_baslayan_funding` (capa yok),
    `beklenen_an_eksik` (pencerede beklenen bir anda kayit yok),
    `beklenen_an_eksik_gecis` (ayni, ama onceki oneri tam: ardisik kayitlar arasindaki
    bosluk iki araligin buyugunu asmiyor; beklenen an iki kaydin arasina dusuyor, ornegin
    1 saatten 4 saate geciste), `diger`.
    """
    if bool(rev8["tam"]) == bool(son_hal["tam"]):
        return None
    if t_esit_k:
        return "t_esit_k"
    if son_hal["tam"]:
        if not rev8["kayit_var"]:
            return "kayitsiz_kisa_pencere"
        if not rev8["baslangic_tam"]:
            return "baslangic_araligi"
        return "diger"
    if not son_hal["onceki_var"]:
        return "gec_baslayan_funding"
    if not son_hal["beklenen_tam"]:
        return "beklenen_an_eksik_gecis" if oneri_tam else "beklenen_an_eksik"
    return "diger"


SON_HAL_FARK_TURLERI = ("t_esit_k", "kayitsiz_kisa_pencere", "baslangic_araligi", "gec_baslayan_funding",
                        "beklenen_an_eksik", "beklenen_an_eksik_gecis", "diger")
BOSLUK_ANI = pd.Timestamp("2026-06-24 04:00", tz="UTC")


def bosluk_seri(seri: pd.DataFrame, donemler) -> tuple[pd.DataFrame, bool]:
    """2026-06-24 04:00 kaydi eksikse (00:00 kaydi var, araligi <= 4 saat, 04:00 donem ici)
    o ana 00:00 kaydinin araligiyla tek yapay kayit eklenmis seri ve eklenip eklenmedigi.
    Yalnizca karsi-olgusal sayim icindir. Saf."""
    if seri.empty:
        return seri, False
    z = pd.DatetimeIndex(seri["odeme_zamani"])
    if np.any(np.asarray(P.ayni_an(z, BOSLUK_ANI), dtype=bool)):
        return seri, False
    onceki = np.flatnonzero(np.asarray(P.ayni_an(z, BOSLUK_ANI - pd.Timedelta(hours=4)), dtype=bool))
    if not len(onceki):
        return seri, False
    aralik = float(pd.to_numeric(seri["aralik_saat"], errors="coerce").iloc[onceki[-1]])
    if not (np.isfinite(aralik) and 0 < aralik <= 4):
        return seri, False
    if not any(P.donem_ici_mi(BOSLUK_ANI, config.BAR_4H, donem_baslangic=d.baslangic, donem_bitis=d.bitis)
               for d in donemler):
        return seri, False
    ek = pd.DataFrame({"odeme_zamani": pd.DatetimeIndex([BOSLUK_ANI]), "aralik_saat": [aralik]})
    return (pd.concat([seri, ek], ignore_index=True).sort_values("odeme_zamani", ignore_index=True), True)


# --- Adim tanimi (ucuncu tur; yalnizca olcum) ---------------------------------------

SON_ADIM_KOSULLARI = ("capa_var", "aralik_gecerli", "beklenen_tam")
TOL_NS = int(P.ZAMAN_TOLERANSI.value)  # 1 dakika, nanosaniye
IMAX = np.iinfo(np.int64).max


def _eslesme_indeksi(z: np.ndarray, anlar: np.ndarray) -> np.ndarray:
    """Her an icin onunla ayni an (`pencere.ayni_an`: fark 1 dk'dan kesin kucuk) olan kaydin
    indeksi; yoksa -1. Zamanlar int64 nanosaniye. Saf, vektorel."""
    sonuc = np.full(len(anlar), -1, dtype=np.int64)
    if len(z) == 0 or len(anlar) == 0:
        return sonuc
    i = np.searchsorted(z, anlar - TOL_NS, side="right")  # ilk z > an - tol
    ic = i < len(z)
    uygun = np.zeros(len(anlar), dtype=bool)
    uygun[ic] = z[i[ic]] < anlar[ic] + TOL_NS
    sonuc[uygun] = i[uygun]
    return sonuc


def zincir_yapisi(z: np.ndarray, a_ns: np.ndarray) -> dict:
    """Kayit dizisi uzerinde beklenen an zinciri. Saf; yalnizca zaman ve aralik.

    Her kayit i icin:
      - `ilk_beklenen`: z_i + araligi.
      - Zincir: beklenen anda kayit varsa oraya "iner" (`inis_kaydi`, `inis_ani`) ve
        sonraki adim o kaydin araligidir; kayit yoksa ayni aralikla adim adim surer.
      - `ilk_eksik`: i'den sonraki ilk KAYITSIZ beklenen an (yoksa IMAX).
      - `zincir_ilk_eksik`: i'den itibaren zincirin urettigi ilk kayitsiz beklenen an;
        i'de kayit varsa indigi kaydin degeri (geriye dogru tek gecis).
    """
    m = len(z)
    bos = np.zeros(m, dtype=np.int64)
    if m == 0:
        return {"ilk_beklenen": bos, "inis_kaydi": bos - 1, "inis_ani": bos + IMAX,
                "ilk_eksik": bos + IMAX, "zincir_ilk_eksik": bos + IMAX}
    ilk_beklenen = z + a_ns
    inis_kaydi = np.full(m, -1, dtype=np.int64)
    inis_ani = np.full(m, IMAX, dtype=np.int64)
    ilk_eksik = np.full(m, IMAX, dtype=np.int64)
    aday = ilk_beklenen.copy()
    kalan = np.arange(m)
    ust = z[-1] + TOL_NS  # bundan sonrasinda eslesebilecek kayit yok
    while len(kalan):
        idx = _eslesme_indeksi(z, aday[kalan])
        esti = idx >= 0
        inis_kaydi[kalan[esti]] = idx[esti]
        inis_ani[kalan[esti]] = aday[kalan[esti]]
        kalan = kalan[~esti]
        yeni = kalan[ilk_eksik[kalan] == IMAX]
        ilk_eksik[yeni] = aday[yeni]
        aday[kalan] += a_ns[kalan]
        kalan = kalan[aday[kalan] <= ust]
    zincir = np.full(m, IMAX, dtype=np.int64)
    for i in range(m - 1, -1, -1):
        if ilk_eksik[i] != IMAX:
            zincir[i] = ilk_eksik[i]
        elif inis_kaydi[i] >= 0:
            zincir[i] = zincir[inis_kaydi[i]]
    return {"ilk_beklenen": ilk_beklenen, "inis_kaydi": inis_kaydi, "inis_ani": inis_ani,
            "ilk_eksik": ilk_eksik, "zincir_ilk_eksik": zincir}


def son_adim_tamlik_ayrintisi(funding: pd.DataFrame, girisler, pencere_sonlari, donem_baslari) -> pd.DataFrame:
    """Adim tanimi (ucuncu tur), kosul kosul. Vektorel, saf; yalnizca odeme ZAMANI ve
    ARALIGI okunur. Pencere sonunu cagiran verir (donem sonu ve T >= K pozisyonlarda B).

      - `capa_var`: giris aninda ya da oncesinde, donem basiyla ayni an ya da sonra bir kayit.
      - `aralik_gecerli`: capadan pencere sonundaki son kayda kadar araliklar sonlu ve > 0.
      - `beklenen_tam`: giris anindan SONRA ve pencere sonuyla ayni an ya da ONCE dusen her
        beklenen anda kayit var. Giris aniyla ayni an ya da once dusen beklenen anlarda
        kayit yoklugu tamligi bozmaz; zincir ayni aralikla surer.
    Ek bilgi sutunlari (`tam`a girmez): `ihlal_pencere_sonunda` (ihlal eden beklenen an
    pencere sonuyla ayni an), `kayit_pencere_sonunda`, `capa_donem_ilk_kaydi`.
    """
    girisler = pd.DatetimeIndex(girisler)
    sonlar = pd.DatetimeIndex(pencere_sonlari)
    baslar = pd.DatetimeIndex(donem_baslari)
    if not (len(girisler) == len(sonlar) == len(baslar)):
        raise ValueError("girisler, pencere_sonlari ve donem_baslari ayni uzunlukta olmali.")
    n = len(girisler)
    ek = ("ihlal_pencere_sonunda", "kayit_pencere_sonunda", "capa_donem_ilk_kaydi")
    sonuc = pd.DataFrame({k: np.zeros(n, dtype=bool) for k in (*SON_ADIM_KOSULLARI, *ek, "tam")})
    if n == 0 or funding.empty:
        return sonuc
    zamanlar = funding_modulu._zaman_dizisi(funding, "son_adim_tamlik_ayrintisi")
    z = zamanlar.asi8
    aralik = pd.to_numeric(funding["aralik_saat"], errors="coerce").to_numpy(dtype=float)
    iyi = np.isfinite(aralik) & (aralik > 0)
    a_ns = np.where(iyi, aralik, 1.0) * 3_600_000_000_000
    a_ns = np.rint(a_ns).astype(np.int64)
    y = zincir_yapisi(z, a_ns)

    g, so, ba = girisler.asi8, sonlar.asi8, baslar.asi8
    j = np.searchsorted(z, g + TOL_NS, side="left") - 1  # giris ile ayni an ya da once son kayit
    jj = np.maximum(j, 0)
    capa_var = (j >= 0) & (z[jj] > ba - TOL_NS)  # donem basi ile ayni an ya da sonra
    ll = np.maximum(np.searchsorted(z, so + TOL_NS, side="left") - 1, jj)
    p_aralik = np.r_[0, np.cumsum(~iyi)]
    aralik_gecerli = capa_var & ((p_aralik[ll + 1] - p_aralik[jj]) == 0)

    a_j = a_ns[jj]
    ilk_eksik_j, inis_ani_j, inis_j = y["ilk_eksik"][jj], y["inis_ani"][jj], y["inis_kaydi"][jj]
    zincir = y["zincir_ilk_eksik"]
    capada_eksik_yok = ilk_eksik_j == IMAX
    # Capadan sonraki ilk KAYITSIZ beklenen an, giristen sonra olani (aritmetik izgara).
    # Tamsayi aritmetigi: ns degerleri float64'te tam temsil edilemez.
    t0 = np.where(capada_eksik_yok, 0, ilk_eksik_j)
    fark = (g + TOL_NS) - t0  # bundan buyuk esit ilk izgara noktasi aranir
    k = np.where(fark > 0, -(-fark // a_j), 0)
    aday = np.where(capada_eksik_yok, IMAX, t0 + k * a_j)
    aday_gecerli = ~capada_eksik_yok & (aday < inis_ani_j)  # inisten once: gercekten kayitsiz
    ihlal_a = aday_gecerli & (aday < so + TOL_NS)
    # Pencerede capadan gelen eksik yoksa zincir inise gecer.
    sonraki = np.where(inis_j >= 0, zincir[np.maximum(inis_j, 0)], IMAX)
    ihlal_b = ~ihlal_a & (inis_j >= 0) & (sonraki < so + TOL_NS)
    ihlal = capa_var & (ihlal_a | ihlal_b)
    ihlal_ani = np.where(ihlal, np.where(ihlal_a, aday, sonraki), 0)

    ilk_donem_kaydi = np.searchsorted(z, ba - TOL_NS, side="right")
    sonuc["capa_var"] = capa_var
    sonuc["aralik_gecerli"] = aralik_gecerli
    sonuc["beklenen_tam"] = capa_var & ~ihlal & aralik_gecerli
    sonuc["tam"] = capa_var & aralik_gecerli & ~ihlal
    sonuc["ihlal_pencere_sonunda"] = ihlal & (np.abs(ihlal_ani - np.where(ihlal, so, 0)) < TOL_NS)
    sonuc["kayit_pencere_sonunda"] = _eslesme_indeksi(z, so) >= 0
    sonuc["capa_donem_ilk_kaydi"] = capa_var & (jj == ilk_donem_kaydi)
    return sonuc


def son_adim_fark_turu(rev8: pd.Series, son_adim: pd.Series, t_esit_k: bool) -> str | None:
    """Adim tanimi ile rev.8'in hukmu farkliysa farkin turu; ayniysa None. Saf.

    Adim tanimina gore tam, rev.8'e gore degil: `t_esit_k`, `kayitsiz_kisa_pencere`,
    `baslangic_araligi`, `son_odeme` (rev.8'in son kosulu), `ic_bosluk`, `diger`.
    Rev.8'e gore tam, adim tanimina gore degil: `t_esit_k`, `capa_yok`,
    `beklenen_an_eksik`, `diger`.
    """
    if bool(rev8["tam"]) == bool(son_adim["tam"]):
        return None
    if t_esit_k:
        return "t_esit_k"
    if son_adim["tam"]:
        if not rev8["kayit_var"]:
            return "kayitsiz_kisa_pencere"
        if not rev8["baslangic_tam"]:
            return "baslangic_araligi"
        if not rev8["son_tam"]:
            return "son_odeme"
        if not rev8["ic_tam"]:
            return "ic_bosluk"
        return "diger"
    if not son_adim["capa_var"]:
        return "capa_yok"
    if not son_adim["beklenen_tam"]:
        return "beklenen_an_eksik"
    return "diger"


SON_ADIM_FARK_TURLERI = ("t_esit_k", "kayitsiz_kisa_pencere", "baslangic_araligi", "son_odeme", "ic_bosluk",
                         "capa_yok", "beklenen_an_eksik", "diger")


# --- Sinir durumu taramasi (tanimin kenarlari; yalnizca sayi ve zaman) ----------------


def sinir_taramasi(sembol: str, donemler, seri: pd.DataFrame) -> list[dict]:
    """Tanimin sinir durumlarini veride sayar. Saf; yalnizca odeme zamani ve araligi.

    Olculenler (`olcum` sutunu):
      - `ardisik_cift`: ardisik iki kayitta, sonraki kaydin beklenen ana gore yeri
        (`esit` / `once` / `sonra`) ve aralik cifti. `once`: zincir o kaydin uzerinden
        atlar; `sonra`: zincir kayitsiz beklenen an uretir.
      - `aralik_degisimi`: bir donemde aralik kac kez degisiyor (0, 1, 2, 3+).
      - `gecis_yonu`: uzun araliktan kisaya / kisadan uzuna gecis sayisi.
      - `tolerans_eslemesi`: beklenen an ile kaydin farki 0 degil ama 1 dk'dan kucuk.
      - `yakin_kayit`: ardisik iki kaydin farki 0 < fark < 1 dk (bozuk veri olurdu).
      - `zincirin_atladigi_kayit`: zincirin inis anina kadar atladigi kayit sayisi.
      - `zincir_eksik_uretiyor`: kendisinden sonra kayitsiz beklenen an ureten kayit.
    """
    satirlar = []

    def ekle(olcum, ayrinti, sayi, ornek=pd.NaT):
        satirlar.append({"sembol": sembol, "olcum": olcum, "ayrinti": str(ayrinti), "sayi": int(sayi),
                         "ornek_an": ornek})

    if seri.empty or not donemler:
        return satirlar
    zamanlar = pd.DatetimeIndex(seri["odeme_zamani"])
    z = zamanlar.asi8
    aralik = pd.to_numeric(seri["aralik_saat"], errors="coerce").to_numpy(dtype=float)
    iyi = np.isfinite(aralik) & (aralik > 0)
    a_ns = np.rint(np.where(iyi, aralik, 1.0) * 3_600_000_000_000).astype(np.int64)
    y = zincir_yapisi(z, a_ns)

    ic = np.zeros(len(z), dtype=bool)
    donem_no = np.full(len(z), -1)
    for i, d in enumerate(donemler):
        m = np.asarray(P.ayni_ya_da_sonra(zamanlar, d.baslangic), dtype=bool) & np.asarray(
            P.ayni_ya_da_once(zamanlar, d.bitis), dtype=bool)
        ic |= m
        donem_no[m] = i

    cift = np.flatnonzero(ic[:-1] & ic[1:] & (donem_no[:-1] == donem_no[1:]))
    if len(cift):
        fark = z[cift + 1] - y["ilk_beklenen"][cift]
        yer = np.where(np.abs(fark) < TOL_NS, "esit", np.where(fark < 0, "once", "sonra"))
        for durum in ("esit", "once", "sonra"):
            m = yer == durum
            for cift_aralik in sorted(set(zip(aralik[cift[m]], aralik[cift[m] + 1]))):
                mm = m & (aralik[cift] == cift_aralik[0]) & (aralik[cift + 1] == cift_aralik[1])
                ekle("ardisik_cift", f"{durum}|{cift_aralik[0]:g}->{cift_aralik[1]:g}", mm.sum(),
                     zamanlar[cift[mm][0]] if mm.any() else pd.NaT)
        deg = aralik[cift] != aralik[cift + 1]
        ekle("gecis_yonu", "kisadan_uzuna", (deg & (aralik[cift] < aralik[cift + 1])).sum(),
             zamanlar[cift[deg & (aralik[cift] < aralik[cift + 1])][0]]
             if (deg & (aralik[cift] < aralik[cift + 1])).any() else pd.NaT)
        ekle("gecis_yonu", "uzundan_kisaya", (deg & (aralik[cift] > aralik[cift + 1])).sum(),
             zamanlar[cift[deg & (aralik[cift] > aralik[cift + 1])][0]]
             if (deg & (aralik[cift] > aralik[cift + 1])).any() else pd.NaT)
        for i in range(len(donemler)):
            ekle("aralik_degisimi", f"donem_{i}", int((deg & (donem_no[cift] == i)).sum()),
                 donemler[i].baslangic)
        yakin = (z[cift + 1] - z[cift]) < TOL_NS
        ekle("yakin_kayit", "0<fark<1dk", yakin.sum(), zamanlar[cift[yakin][0]] if yakin.any() else pd.NaT)

    inen = y["inis_kaydi"] >= 0
    if inen.any():
        d = y["inis_ani"][inen] - z[np.maximum(y["inis_kaydi"], 0)[inen]]
        tol = (d != 0)
        ekle("tolerans_eslemesi", "beklenen_an_ile_kayit_farki_0_degil", tol.sum(),
             zamanlar[np.maximum(y["inis_kaydi"], 0)[inen][tol][0]] if tol.any() else pd.NaT)
        ekle("tolerans_eslemesi", "en_buyuk_fark_ms", int(np.abs(d).max() // 1_000_000) if len(d) else 0)
        atlanan = np.maximum(y["inis_kaydi"][inen] - np.flatnonzero(inen) - 1, 0)
        ekle("zincirin_atladigi_kayit", "toplam", atlanan.sum(),
             zamanlar[np.flatnonzero(inen)[atlanan > 0][0]] if (atlanan > 0).any() else pd.NaT)
        ekle("zincirin_atladigi_kayit", "kayit_sayisi", int((atlanan > 0).sum()))
    uretiyor = (y["ilk_eksik"] != IMAX) & ic
    ekle("zincir_eksik_uretiyor", "kayit_sayisi", uretiyor.sum(),
         zamanlar[np.flatnonzero(uretiyor)[0]] if uretiyor.any() else pd.NaT)
    return satirlar


# --- Tahmin etmeyen tanim (dorduncu tur; yalnizca olcum) -----------------------------

TAHMIN_YOK_KOSULLARI = ("capa_var", "aralik_gecerli", "zincir_tam", "son_tam")
TAHMIN_YOK_EK = ("kuyruk_dogrulanmamis", "kuyruk_sifir", "kuyruk_kismi", "son_esitlik_affi",
                 "aralik_degisimi_var")


def tahmin_yok_tamlik_ayrintisi(funding: pd.DataFrame, girisler, pencere_sonlari, donem_baslari) -> pd.DataFrame:
    """Tahmin etmeyen tamlik tanimi (dorduncu tur), kosul kosul. Vektorel, saf; yalnizca
    odeme ZAMANI ve ARALIGI okunur. Pencere sonunu cagiran verir (T >= K ve donem sonunda B).

      - `capa_var`: giris aninda ya da oncesinde, donem basiyla ayni an ya da sonra son kayit.
      - `zincir_tam`: capadan pencere sonuna kadar ardisik iki kayitta sonraki, onceki +
        iki araligin buyugunden SONRA degil.
      - `son_tam`: penceredeki son kayit + araligi pencere sonundan ONCE degil (tam pencere
        sonuna denk gelmek yeterlidir).
      - Beklenen odeme ani baska hicbir yerde uretilmez.
    Kural, birinci turun onerisiyle aynidir; bu fonksiyon onu cagirir ve gevseklik
    olcusunu ekler:
      - `kuyruk_dogrulanmamis`: son kayit + araligi pencere sonundan SONRA, yani son
        kayittan pencere sonuna kadar bir tam aralik dolmamis. Iki alt duruma ayrilir:
        `kuyruk_sifir` (son kayit pencere sonuyla ayni an; dogrulanamayan dilim YOK) ve
        `kuyruk_kismi` (0 < dilim < aralik; o dilimde eksik bir odeme gorulemez).
      - `son_esitlik_affi`: son kayit + araligi tam pencere sonu; kural bunu affeder.
      - `aralik_degisimi_var`: capadan pencere sonuna kadar en az bir ardisik aralik degisimi.
    """
    temel = oneri_tamlik_ayrintisi(funding, girisler, pencere_sonlari, donem_baslari,
                                   kati_onceki=False, son_kurali="oneri")
    sonuc = pd.DataFrame({
        "capa_var": temel["onceki_var"].to_numpy(), "aralik_gecerli": temel["aralik_gecerli"].to_numpy(),
        "zincir_tam": temel["zincir_tam"].to_numpy(), "son_tam": temel["son_tam"].to_numpy(),
        "kuyruk_dogrulanmamis": np.zeros(len(temel), dtype=bool),
        "kuyruk_sifir": np.zeros(len(temel), dtype=bool),
        "kuyruk_kismi": np.zeros(len(temel), dtype=bool),
        "son_esitlik_affi": temel["son_esit"].to_numpy() & temel["tam"].to_numpy(),
        "aralik_degisimi_var": np.zeros(len(temel), dtype=bool),
        "tam": temel["tam"].to_numpy(),
    })
    if len(temel) == 0 or funding.empty:
        return sonuc
    zamanlar = funding_modulu._zaman_dizisi(funding, "tahmin_yok_tamlik_ayrintisi")
    aralik = pd.to_numeric(funding["aralik_saat"], errors="coerce").to_numpy(dtype=float)
    iyi = np.isfinite(aralik) & (aralik > 0)
    aralik_td = pd.to_timedelta(np.where(iyi, aralik, 0.0), unit="h")
    girisler = pd.DatetimeIndex(girisler)
    sonlar = pd.DatetimeIndex(pencere_sonlari)
    j = zamanlar.searchsorted(P.ayni_an_sonu(girisler), side="left") - 1
    jj = np.maximum(j, 0)
    son_i = np.maximum(zamanlar.searchsorted(P.ayni_an_sonu(sonlar), side="left") - 1, jj)
    sonraki = zamanlar[son_i] + aralik_td[son_i]
    dolmamis = sonuc["tam"].to_numpy() & np.asarray(P.sonra(sonraki, sonlar), dtype=bool)
    sifir = np.asarray(P.ayni_an(zamanlar[son_i], sonlar), dtype=bool)
    sonuc["kuyruk_dogrulanmamis"] = dolmamis
    sonuc["kuyruk_sifir"] = dolmamis & sifir
    sonuc["kuyruk_kismi"] = dolmamis & ~sifir
    degisim = (aralik[1:] != aralik[:-1]) if len(aralik) > 1 else np.zeros(0, dtype=bool)
    p_degisim = np.r_[0, np.cumsum(degisim)]
    sonuc["aralik_degisimi_var"] = sonuc["capa_var"].to_numpy() & ((p_degisim[son_i] - p_degisim[jj]) > 0)
    return sonuc


# --- Capa duzeltmesi (besinci tur; yalnizca olcum) -----------------------------------

CAPA_DUZELTME_KOSULLARI = ("capa_var", "aralik_gecerli", "zincir_tam", "son_tam")
CAPA_DUZELTME_EK = ("ilk_cift_affi", "son_ihlali_giris_oncesi", "kuyruk_dogrulanmamis", "kuyruk_sifir",
                    "kuyruk_kismi", "son_esitlik_affi", "aralik_degisimi_var")


def capa_duzeltme_tamlik_ayrintisi(funding: pd.DataFrame, girisler, pencere_sonlari,
                                   donem_baslari) -> pd.DataFrame:
    """Dorduncu turun tanimi, capa boslugu giristen olculerek (besinci tur). Vektorel, saf;
    yalnizca odeme ZAMANI ve ARALIGI okunur. Pencere sonunu cagiran verir.

    Dorduncu tura eklenen tek cumle: "Capa ile sonraki kayit arasindaki bosluk
    degerlendirilirken, giris aninda ya da oncesinde dusen eksik odemeler dikkate alinmaz:
    bu boslugun olcumu giris anindan baslar." Yani dizideki ILK ciftin (capa -> sonraki
    kayit) boslugu capadan degil giristen olculur; capa giris aninda ya da oncesinde
    oldugu icin taban `giris`tir. Dizinin geri kalani ve son kosul dorduncu turla aynidir.

      - `capa_var`: giris aninda ya da oncesinde, donem basiyla ayni an ya da sonra son kayit.
      - `zincir_tam`: ilk cift icin sonraki kayit `giris + iki araligin buyugu`nden SONRA
        degil; sonraki ciftlerde `onceki kayit + iki araligin buyugu`nden SONRA degil.
      - `son_tam`: penceredeki son kayit + araligi pencere sonundan ONCE degil.
      - Beklenen odeme ani baska hicbir yerde uretilmez.
    Ek bilgi sutunlari (`tam`a girmez): `ilk_cift_affi` (ilk cift dorduncu turda eksikti,
    bu tanimda degil), `son_ihlali_giris_oncesi` (son kosul bozuk ve son kaydin beklenen
    odeme ani giris aninda ya da oncesinde: kuralin son ucundaki karsi ornek adayi),
    gevseklik olcusu sutunlari dorduncu turdaki anlamlariyla.
    """
    girisler = pd.DatetimeIndex(girisler)
    sonlar = pd.DatetimeIndex(pencere_sonlari)
    baslar = pd.DatetimeIndex(donem_baslari)
    if not (len(girisler) == len(sonlar) == len(baslar)):
        raise ValueError("girisler, pencere_sonlari ve donem_baslari ayni uzunlukta olmali.")
    n = len(girisler)
    sonuc = pd.DataFrame({k: np.zeros(n, dtype=bool)
                          for k in (*CAPA_DUZELTME_KOSULLARI, *CAPA_DUZELTME_EK, "tam")})
    if n == 0 or funding.empty:
        return sonuc
    zamanlar = funding_modulu._zaman_dizisi(funding, "capa_duzeltme_tamlik_ayrintisi")
    aralik = pd.to_numeric(funding["aralik_saat"], errors="coerce").to_numpy(dtype=float)
    iyi = np.isfinite(aralik) & (aralik > 0)
    a_saat = np.where(iyi, aralik, 0.0)
    aralik_td = pd.to_timedelta(a_saat, unit="h")

    j = zamanlar.searchsorted(P.ayni_an_sonu(girisler), side="left") - 1  # capa: ayni an ya da once
    jj = np.maximum(j, 0)
    son_i = np.maximum(zamanlar.searchsorted(P.ayni_an_sonu(sonlar), side="left") - 1, jj)
    capa_var = (j >= 0) & np.asarray(P.ayni_ya_da_sonra(zamanlar[jj], baslar), dtype=bool)
    p_aralik = np.r_[0, np.cumsum(~iyi)]
    aralik_gecerli = capa_var & ((p_aralik[son_i + 1] - p_aralik[jj]) == 0)

    # Dorduncu turun cift kurali (taban: onceki kayit); ilk cift ayrica giristen olculur.
    if len(zamanlar) > 1:
        adim = np.maximum(a_saat[1:], a_saat[:-1])
        beklenen = zamanlar[:-1] + pd.to_timedelta(adim, unit="h")
        kotu_bosluk = np.asarray(P.sonra(zamanlar[1:], beklenen), dtype=bool)
    else:
        adim = np.zeros(0)
        kotu_bosluk = np.zeros(0, dtype=bool)
    p_bosluk = np.r_[0, np.cumsum(kotu_bosluk)]
    ilk_cift_var = son_i > jj
    # Ilk ciftten sonraki ciftler: [jj + 1, son_i - 1] -> p[son_i] - p[min(jj + 1, son_i)].
    ic_kotu = (p_bosluk[son_i] - p_bosluk[np.minimum(jj + 1, son_i)]) > 0
    if len(adim):
        kk = np.minimum(jj, len(adim) - 1)  # ilk ciftin indeksi; ilk cift yoksa kullanilmaz
        ilk_adim = pd.to_timedelta(np.where(ilk_cift_var, adim[kk], 0.0), unit="h")
        sonraki_kayit = zamanlar[np.minimum(jj + 1, len(zamanlar) - 1)]
        ilk_cift_kotu = ilk_cift_var & np.asarray(P.sonra(sonraki_kayit, girisler + ilk_adim), dtype=bool)
        ilk_cift_eski_kotu = ilk_cift_var & kotu_bosluk[kk]
    else:  # tek kayitli seri: ilk cift yok
        ilk_cift_kotu = ilk_cift_eski_kotu = np.zeros(n, dtype=bool)
    zincir_tam = capa_var & ~ic_kotu & ~ilk_cift_kotu

    sonraki = zamanlar[son_i] + aralik_td[son_i]
    son_ok = ~np.asarray(P.once(sonraki, sonlar), dtype=bool)
    son_tam = capa_var & son_ok & aralik_gecerli
    tam = capa_var & aralik_gecerli & zincir_tam & son_tam

    sonuc["capa_var"] = capa_var
    sonuc["aralik_gecerli"] = aralik_gecerli
    sonuc["zincir_tam"] = zincir_tam & aralik_gecerli
    sonuc["son_tam"] = son_tam
    sonuc["tam"] = tam
    sonuc["ilk_cift_affi"] = capa_var & ilk_cift_eski_kotu & ~ilk_cift_kotu
    sonuc["son_ihlali_giris_oncesi"] = (capa_var & aralik_gecerli & ~son_ok
                                       & ~np.asarray(P.sonra(sonraki, girisler), dtype=bool))
    dolmamis = tam & np.asarray(P.sonra(sonraki, sonlar), dtype=bool)
    sifir = np.asarray(P.ayni_an(zamanlar[son_i], sonlar), dtype=bool)
    sonuc["kuyruk_dogrulanmamis"] = dolmamis
    sonuc["kuyruk_sifir"] = dolmamis & sifir
    sonuc["kuyruk_kismi"] = dolmamis & ~sifir
    sonuc["son_esitlik_affi"] = tam & np.asarray(P.ayni_an(sonraki, sonlar), dtype=bool)
    degisim = (aralik[1:] != aralik[:-1]) if len(aralik) > 1 else np.zeros(0, dtype=bool)
    p_degisim = np.r_[0, np.cumsum(degisim)]
    sonuc["aralik_degisimi_var"] = capa_var & ((p_degisim[son_i] - p_degisim[jj]) > 0)
    return sonuc


def capa_duzeltme_fark_turu(tahmin_yok: pd.Series, capa_duzeltme: pd.Series) -> str | None:
    """Capa duzeltmesi ile dorduncu turun hukmu farkliysa farkin turu; ayniysa None. Saf.

    Duzeltmeye gore tam, dorduncu tura gore degil: `capa_boslugu_giris_oncesi` (ilk cift
    affi), `diger`. Ters yon olamaz (duzeltme yalnizca gevsetir); olursa `beklenmeyen`.
    """
    if bool(tahmin_yok["tam"]) == bool(capa_duzeltme["tam"]):
        return None
    if not capa_duzeltme["tam"]:
        return "beklenmeyen"
    return "capa_boslugu_giris_oncesi" if capa_duzeltme["ilk_cift_affi"] else "diger"


CAPA_DUZELTME_FARK_TURLERI = ("capa_boslugu_giris_oncesi", "diger", "beklenmeyen")


def tahmin_yok_fark_turu(rev8: pd.Series, tahmin_yok: pd.Series, t_esit_k: bool) -> str | None:
    """Tahmin etmeyen tanim ile rev.8'in hukmu farkliysa farkin turu; ayniysa None. Saf.

    Tahmin etmeyen tanima gore tam, rev.8'e gore degil: `t_esit_k`, `kayitsiz_kisa_pencere`,
    `baslangic_araligi` (rev.8 ilk kaydin araligini kullaniyor), `son_odeme` (rev.8'in son
    kosulu; esitlikte rev.8 eksik der), `diger`.
    Rev.8'e gore tam, bu tanima gore degil: `t_esit_k`, `capa_yok`, `zincir_bosluk`, `diger`.
    """
    if bool(rev8["tam"]) == bool(tahmin_yok["tam"]):
        return None
    if t_esit_k:
        return "t_esit_k"
    if tahmin_yok["tam"]:
        if not rev8["kayit_var"]:
            return "kayitsiz_kisa_pencere"
        if not rev8["baslangic_tam"]:
            return "baslangic_araligi"
        if not rev8["son_tam"]:
            return "son_odeme"
        return "diger"
    if not tahmin_yok["capa_var"]:
        return "capa_yok"
    if not tahmin_yok["zincir_tam"]:
        return "zincir_bosluk"
    return "diger"


TAHMIN_YOK_FARK_TURLERI = ("t_esit_k", "kayitsiz_kisa_pencere", "baslangic_araligi", "son_odeme",
                           "capa_yok", "zincir_bosluk", "diger")


def _iki_kural(seri: pd.DataFrame, girisler, sonlar, baslar) -> pd.DataFrame:
    """Ayni pozisyonlarda rev.8 (gercek kod) ve oneri (uc okuma) kosullari, tek cerceve."""
    rev8 = rev8_tamlik_ayrintisi(seri, girisler, sonlar)
    oneri = oneri_tamlik_ayrintisi(seri, girisler, sonlar, baslar)
    kati = oneri_tamlik_ayrintisi(seri, girisler, sonlar, baslar, kati_onceki=True)
    r8son = oneri_tamlik_ayrintisi(seri, girisler, sonlar, baslar, son_kurali="rev8")
    tablo = pd.concat([rev8.add_prefix("rev8_"), oneri.add_prefix("oneri_")], axis=1)
    tablo["oneri_kati_tam"] = kati["tam"].to_numpy()
    tablo["oneri_rev8son_tam"] = r8son["tam"].to_numpy()
    tablo["fark_turu"] = [
        fark_turu(pd.Series({k: tablo.at[i, f"rev8_{k}"] for k in (*REV8_TAMLIK_KOSULLARI, "tam")}),
                  pd.Series({k: tablo.at[i, f"oneri_{k}"] for k in (*ONERI_KOSULLARI, "son_esit", "tam")}))
        if tablo.at[i, "rev8_tam"] != tablo.at[i, "oneri_tam"] else None
        for i in range(len(tablo))
    ]
    return tablo


def _bos_seri() -> pd.DataFrame:
    return pd.DataFrame({"odeme_zamani": pd.DatetimeIndex([], tz="UTC"), "aralik_saat": np.empty(0)})


# --- 1. Donem sonu (temsili pozisyon) ---------------------------------------------


def donem_sonu_satirlari(sembol: str, donemler, turler, seri: pd.DataFrame) -> list[dict]:
    """Her donem sonu ve izgara: temsili plan (A1 ile ayni), iki kural. Saf."""
    satirlar = []
    zam = pd.DatetimeIndex(seri["odeme_zamani"])
    aralik = pd.to_numeric(seri["aralik_saat"], errors="coerce").to_numpy(dtype=float)
    for bar in (config.BAR_4H, config.BAR_1D):
        for i, (d, tur) in enumerate(zip(donemler, turler)):
            satir = {"sembol": sembol, "bar": bar, "donem_sira": i, "tur": tur, "donem_baslangic": d.baslangic,
                     "donem_bitis": d.bitis, "giris": pd.NaT, "pencere_sonu": pd.NaT, "ret_gerekcesi": None}
            try:
                plan = temsili_plan(d, bar)
            except P.OlayOlusmaz as hata:
                satir["ret_gerekcesi"] = P.ret_gerekcesi(hata)
                satirlar.append(satir)
                continue
            except P.DonemDisiSinyal:
                satir["ret_gerekcesi"] = "donem_disi_sinyal"
                satirlar.append(satir)
                continue
            son = rev8_pencere_sonu(plan)
            satir.update(giris=plan.giris, pencere_sonu=son, cikis_turu=plan.cikis_turu)
            k = _iki_kural(seri, [plan.giris], [son], [d.baslangic]).iloc[0].to_dict()
            satir.update(k)
            sh = son_hal_tamlik_ayrintisi(
                seri, [plan.giris], [son_hal_pencere_sonu(plan.cikis_ani, plan.cikis_turu, d.bitis, d.kapanis)],
                [d.baslangic]).iloc[0]
            satir.update({f"son_hal_{k_}": bool(sh[k_]) for k_ in (*SON_HAL_KOSULLARI, "kopuk_giris_oncesi", "tam")})
            sa = son_adim_tamlik_ayrintisi(
                seri, [plan.giris], [son_hal_pencere_sonu(plan.cikis_ani, plan.cikis_turu, d.bitis, d.kapanis)],
                [d.baslangic]).iloc[0]
            satir.update({f"son_adim_{k_}": bool(sa[k_]) for k_ in
                          (*SON_ADIM_KOSULLARI, "ihlal_pencere_sonunda", "kayit_pencere_sonunda",
                           "capa_donem_ilk_kaydi", "tam")})
            ty = tahmin_yok_tamlik_ayrintisi(
                seri, [plan.giris], [son_hal_pencere_sonu(plan.cikis_ani, plan.cikis_turu, d.bitis, d.kapanis)],
                [d.baslangic]).iloc[0]
            satir.update({f"tahmin_yok_{k_}": bool(ty[k_]) for k_ in
                          (*TAHMIN_YOK_KOSULLARI, *TAHMIN_YOK_EK, "tam")})
            cd = capa_duzeltme_tamlik_ayrintisi(
                seri, [plan.giris], [son_hal_pencere_sonu(plan.cikis_ani, plan.cikis_turu, d.bitis, d.kapanis)],
                [d.baslangic]).iloc[0]
            satir.update({f"capa_duzeltme_{k_}": bool(cd[k_]) for k_ in
                          (*CAPA_DUZELTME_KOSULLARI, *CAPA_DUZELTME_EK, "tam")})
            # Capa ve pencere icindeki ilk kayit (yalnizca zaman ve aralik).
            capa = np.flatnonzero(np.asarray(P.ayni_ya_da_once(zam, plan.giris), dtype=bool)) if len(zam) else []
            ici = (np.flatnonzero(np.asarray(P.sonra(zam, plan.giris), dtype=bool)
                                  & np.asarray(P.ayni_ya_da_once(zam, son), dtype=bool)) if len(zam) else [])
            satir["capa_zamani"] = zam[capa[-1]] if len(capa) else pd.NaT
            satir["capa_aralik_saat"] = float(aralik[capa[-1]]) if len(capa) else float("nan")
            satir["pencerede_kayit"] = len(ici)
            satirlar.append(satir)
    return satirlar


# --- 2. Baslangic ve farklar (butun donem ici barlar, birincil ufuk) ------------------------


DELIST_TURLERI = ("delist_SETTLING", "delist_exchangeInfo_disi")


def baslangic_ve_farklar(sembol: str, grup: str, donemler, mumlar: pd.DataFrame, seri: pd.DataFrame,
                         kumeler, seri_cf: pd.DataFrame | None = None,
                         turler: list[str] | None = None) -> tuple[list[dict], list[dict]]:
    """rev8_etki.baslangic_etkisi ile ayni pozisyon evreni; iki kural. Saf."""
    zamanlar = pd.DatetimeIndex(mumlar["open_time"])
    satirlar, farklar = [], []
    for bar in sorted(set(config.HIPOTEZ_IZGARASI.values())):
        ufuk = config.BIRINCIL_UFUK[bar]
        girisler, sonlar, baslar, plan_kumeleri, sh_sonlar, tk, delist = [], [], [], [], [], [], []
        for d_sira, d in enumerate(donemler):
            maske = np.asarray(P.donem_ici_4h_maskesi(zamanlar, donem_baslangic=d.baslangic,
                                                      donem_bitis=d.bitis), dtype=bool)
            zd = zamanlar[maske]
            if bar == config.BAR_1D:
                sinyaller = pd.DatetimeIndex(klines_modulu.gunluge_cevir(mumlar, donemler=[d])["open_time"])
            else:
                sinyaller = zd
            for t in sinyaller:
                kume = sinyal_kumesi(t, grup, kumeler)
                if kume is None:
                    continue
                try:
                    plan = P.pozisyon_plani(zd, t, ufuk, bar, birincil_ufuk=ufuk,
                                            kume_baslangic=kumeler[kume][1], kume_bitis=kumeler[kume][2],
                                            donem_baslangic=d.baslangic, donem_bitis=d.bitis)
                except P.OlayOlusmaz:
                    continue
                girisler.append(plan.giris)
                sonlar.append(rev8_pencere_sonu(plan))
                baslar.append(d.baslangic)
                plan_kumeleri.append(kume)
                sh_sonlar.append(son_hal_pencere_sonu(plan.cikis_ani, plan.cikis_turu, d.bitis, d.kapanis))
                tk.append(bool(P.ayni_an(plan.cikis.hedef_cikis_ani, d.kapanis)))  # T = K
                delist.append(bool(turler is not None and turler[d_sira] in DELIST_TURLERI))
        if not girisler:
            continue
        rev8 = rev8_tamlik_ayrintisi(seri, girisler, sonlar)
        oneri = oneri_tamlik_ayrintisi(seri, girisler, sonlar, baslar)
        kati = oneri_tamlik_ayrintisi(seri, girisler, sonlar, baslar, kati_onceki=True)
        r8son = oneri_tamlik_ayrintisi(seri, girisler, sonlar, baslar, son_kurali="rev8")
        kume_dizi = np.array(plan_kumeleri)
        sh = son_hal_tamlik_ayrintisi(seri, girisler, sh_sonlar, baslar)
        sa = son_adim_tamlik_ayrintisi(seri, girisler, sh_sonlar, baslar)
        ty = tahmin_yok_tamlik_ayrintisi(seri, girisler, sh_sonlar, baslar)
        cd = capa_duzeltme_tamlik_ayrintisi(seri, girisler, sh_sonlar, baslar)
        tk_dizi = np.array(tk, dtype=bool)
        delist_dizi = np.array(delist, dtype=bool)
        if seri_cf is not None:
            sa_cf = son_adim_tamlik_ayrintisi(seri_cf, girisler, sh_sonlar, baslar)["tam"].to_numpy()
            ty_cf = tahmin_yok_tamlik_ayrintisi(seri_cf, girisler, sh_sonlar, baslar)["tam"].to_numpy()
            cd_cf = capa_duzeltme_tamlik_ayrintisi(seri_cf, girisler, sh_sonlar, baslar)["tam"].to_numpy()
            sh_cf = son_hal_tamlik_ayrintisi(seri_cf, girisler, sh_sonlar, baslar)["tam"].to_numpy()
            r8_cf = rev8_tamlik_ayrintisi(seri_cf, girisler, sonlar)["tam"].to_numpy()
            gi, sh_s, r8_s = pd.DatetimeIndex(girisler), pd.DatetimeIndex(sh_sonlar), pd.DatetimeIndex(sonlar)
            iceren_sh = (np.asarray(P.sonra(BOSLUK_ANI, gi), dtype=bool)
                         & np.asarray(P.ayni_ya_da_once(BOSLUK_ANI, sh_s), dtype=bool))
            iceren_r8 = (np.asarray(P.sonra(BOSLUK_ANI, gi), dtype=bool)
                         & np.asarray(P.ayni_ya_da_once(BOSLUK_ANI, r8_s), dtype=bool))
            giris_0400 = np.asarray(P.ayni_an(gi, BOSLUK_ANI), dtype=bool)
        else:
            ty_cf = ty["tam"].to_numpy()
            cd_cf = cd["tam"].to_numpy()
            sa_cf = sa["tam"].to_numpy()
            sh_cf, r8_cf = sh["tam"].to_numpy(), rev8["tam"].to_numpy()
            iceren_sh = iceren_r8 = giris_0400 = np.zeros(len(girisler), dtype=bool)
        sh_etki = sh_cf & ~sh["tam"].to_numpy()
        sa_etki = sa_cf & ~sa["tam"].to_numpy()
        ty_etki = ty_cf & ~ty["tam"].to_numpy()
        cd_etki = cd_cf & ~cd["tam"].to_numpy()
        r8_etki = r8_cf & ~rev8["tam"].to_numpy()
        farkli = np.flatnonzero((rev8["tam"].to_numpy() != oneri["tam"].to_numpy())
                                | (rev8["tam"].to_numpy() != sh["tam"].to_numpy())
                                | (rev8["tam"].to_numpy() != sa["tam"].to_numpy())
                                | (rev8["tam"].to_numpy() != ty["tam"].to_numpy())
                                | (rev8["tam"].to_numpy() != cd["tam"].to_numpy()))
        fark_turleri, sh_turler, sa_turler, ty_turler, cd_turler = {}, {}, {}, {}, {}
        for i in farkli:
            tur = fark_turu(rev8.iloc[i], oneri.iloc[i])
            fark_turleri[i] = tur
            ty_turler[i] = tahmin_yok_fark_turu(rev8.iloc[i], ty.iloc[i], bool(tk_dizi[i]))
            cd_turler[i] = capa_duzeltme_fark_turu(ty.iloc[i], cd.iloc[i])
            sh_tur = son_hal_fark_turu(rev8.iloc[i], sh.iloc[i], bool(tk_dizi[i]), bool(oneri.at[i, "tam"]))
            sh_turler[i] = sh_tur
            sa_tur = son_adim_fark_turu(rev8.iloc[i], sa.iloc[i], bool(tk_dizi[i]))
            sa_turler[i] = sa_tur
            farklar.append({"sembol": sembol, "bar": bar, "kume": kume_dizi[i], "giris": girisler[i],
                            "pencere_sonu": sonlar[i], "rev8_tam": bool(rev8.at[i, "tam"]),
                            "oneri_tam": bool(oneri.at[i, "tam"]), "fark_turu": tur,
                            "son_hal_pencere_sonu": sh_sonlar[i], "t_esit_k": bool(tk_dizi[i]),
                            "son_hal_tam": bool(sh.at[i, "tam"]), "son_hal_fark_turu": sh_tur,
                            "son_hal_kopuk_giris_oncesi": bool(sh.at[i, "kopuk_giris_oncesi"]),
                            "bosluk_etkisi_son_hal": bool(sh_etki[i]),
                            "son_adim_tam": bool(sa.at[i, "tam"]), "son_adim_fark_turu": sa_tur,
                            "bosluk_etkisi_son_adim": bool(sa_etki[i]),
                            "tahmin_yok_tam": bool(ty.at[i, "tam"]), "tahmin_yok_fark_turu": ty_turler[i],
                            "bosluk_etkisi_tahmin_yok": bool(ty_etki[i]),
                            "capa_duzeltme_tam": bool(cd.at[i, "tam"]),
                            "capa_duzeltme_fark_turu": cd_turler[i],
                            "capa_duzeltme_ilk_cift_affi": bool(cd.at[i, "ilk_cift_affi"]),
                            "bosluk_etkisi_capa_duzeltme": bool(cd_etki[i])})
        for kume in sorted(set(plan_kumeleri)):
            m = kume_dizi == kume
            r, o = rev8.loc[m], oneri.loc[m]
            digerleri = r["kayit_var"] & r["aralik_gecerli"] & r["ic_tam"] & r["son_tam"]
            satir = {"sembol": sembol, "bar": bar, "kume": kume, "plan": int(m.sum()),
                     "rev8_tam": int(r["tam"].sum()), "rev8_kayit_yok": int((~r["kayit_var"]).sum()),
                     "rev8_baslangic_bozuk": int((r["kayit_var"] & ~r["baslangic_tam"]).sum()),
                     "rev8_yalniz_baslangic": int((digerleri & ~r["baslangic_tam"]).sum()),
                     "oneri_tam": int(o["tam"].sum()), "oneri_onceki_yok": int((~o["onceki_var"]).sum()),
                     "oneri_zincir_bozuk": int((o["onceki_var"] & ~o["zincir_tam"]).sum()),
                     "oneri_kati_tam": int(kati.loc[m, "tam"].sum()),
                     "oneri_rev8son_tam": int(r8son.loc[m, "tam"].sum()),
                     "oneri_tam_rev8_degil": int((o["tam"] & ~r["tam"]).sum()),
                     "rev8_tam_oneri_degil": int((r["tam"] & ~o["tam"]).sum())}
            for tur in FARK_TURLERI:
                satir[f"fark_{tur}"] = sum(1 for i, t_ in fark_turleri.items() if t_ == tur and kume_dizi[i] == kume)
            h = sh.loc[m]
            satir.update({
                "son_hal_tam": int(h["tam"].sum()), "son_hal_onceki_yok": int((~h["onceki_var"]).sum()),
                "son_hal_beklenen_eksik": int((h["onceki_var"] & ~h["beklenen_tam"]).sum()),
                "son_hal_kopuk_giris_oncesi": int(h["kopuk_giris_oncesi"].sum()),
                "son_hal_kopuk_ve_tam": int((h["kopuk_giris_oncesi"] & h["tam"]).sum()),
                "t_esit_k": int(tk_dizi[m].sum()),
                "son_hal_tam_rev8_degil": int((h["tam"] & ~r["tam"]).sum()),
                "rev8_tam_son_hal_degil": int((r["tam"] & ~h["tam"]).sum()),
                "bosluk_etkisi_son_hal": int(sh_etki[m].sum()), "bosluk_etkisi_rev8": int(r8_etki[m].sum()),
                "bosluk_penceresi_iceren_son_hal": int(iceren_sh[m].sum()),
                "bosluk_etkisi_son_hal_pencere_disi": int((sh_etki & ~iceren_sh)[m].sum()),
                "bosluk_penceresi_iceren_rev8": int(iceren_r8[m].sum()),
                "bosluk_giris_0400": int(giris_0400[m].sum()),
                "bosluk_giris_0400_son_hal_tam": int((giris_0400 & sh["tam"].to_numpy())[m].sum()),
                "bosluk_giris_0400_rev8_tam": int((giris_0400 & rev8["tam"].to_numpy())[m].sum()),
            })
            for tur in SON_HAL_FARK_TURLERI:
                satir[f"son_hal_fark_{tur}"] = sum(1 for i, t_ in sh_turler.items() if t_ == tur and kume_dizi[i] == kume)
            d_ = sa.loc[m]
            satir.update({
                "son_adim_tam": int(d_["tam"].sum()), "son_adim_capa_yok": int((~d_["capa_var"]).sum()),
                "son_adim_beklenen_eksik": int((d_["capa_var"] & ~d_["beklenen_tam"]).sum()),
                "son_adim_ihlal_pencere_sonunda": int(d_["ihlal_pencere_sonunda"].sum()),
                "son_adim_kayit_pencere_sonunda": int(d_["kayit_pencere_sonunda"].sum()),
                "son_adim_kayit_pencere_sonunda_tam": int((d_["kayit_pencere_sonunda"] & d_["tam"]).sum()),
                "son_adim_capa_donem_ilk_kaydi": int(d_["capa_donem_ilk_kaydi"].sum()),
                "son_adim_capa_ilk_kayit_tam": int((d_["capa_donem_ilk_kaydi"] & d_["tam"]).sum()),
                "son_adim_tam_rev8_degil": int((d_["tam"] & ~r["tam"]).sum()),
                "rev8_tam_son_adim_degil": int((r["tam"] & ~d_["tam"]).sum()),
                "son_hal_gecis_son_adim_tam": int((~h["tam"] & r["tam"] & d_["tam"]).sum()),
                "son_hal_kopuk_son_adim_tam": int((h["kopuk_giris_oncesi"] & d_["tam"]).sum()),
                "son_hal_kopuk_son_adim_eksik": int((h["kopuk_giris_oncesi"] & ~d_["tam"]).sum()),
                "bosluk_etkisi_son_adim": int(sa_etki[m].sum()),
                "bosluk_etkisi_son_adim_pencere_disi": int((sa_etki & ~iceren_sh)[m].sum()),
                "bosluk_giris_0400_son_adim_tam": int((giris_0400 & sa["tam"].to_numpy())[m].sum()),
            })
            for tur in SON_ADIM_FARK_TURLERI:
                satir[f"son_adim_fark_{tur}"] = sum(1 for i, t_ in sa_turler.items()
                                                    if t_ == tur and kume_dizi[i] == kume)
            t_ = ty.loc[m]
            dl = delist_dizi[m]
            satir.update({
                "tahmin_yok_tam": int(t_["tam"].sum()), "tahmin_yok_capa_yok": int((~t_["capa_var"]).sum()),
                "tahmin_yok_zincir_bozuk": int((t_["capa_var"] & ~t_["zincir_tam"]).sum()),
                "tahmin_yok_son_bozuk": int((t_["capa_var"] & t_["zincir_tam"] & ~t_["son_tam"]).sum()),
                "tahmin_yok_tam_rev8_degil": int((t_["tam"] & ~r["tam"]).sum()),
                "rev8_tam_tahmin_yok_degil": int((r["tam"] & ~t_["tam"]).sum()),
                "tahmin_yok_oneri_ile_ayni": int((t_["tam"].to_numpy() == o["tam"].to_numpy()).sum()),
                # Gevseklik olcusu
                "tahmin_yok_aralik_degisimi_var": int(t_["aralik_degisimi_var"].sum()),
                "tahmin_yok_kuyruk_dogrulanmamis": int(t_["kuyruk_dogrulanmamis"].sum()),
                "tahmin_yok_kuyruk_sifir": int(t_["kuyruk_sifir"].sum()),
                "tahmin_yok_kuyruk_kismi": int(t_["kuyruk_kismi"].sum()),
                "tahmin_yok_kuyruk_kismi_delist": int((t_["kuyruk_kismi"].to_numpy() & dl).sum()),
                "tahmin_yok_kuyruk_kismi_delist_disi": int((t_["kuyruk_kismi"].to_numpy() & ~dl).sum()),
                "tahmin_yok_kuyruk_kismi_aralik_degisimli": int((t_["kuyruk_kismi"].to_numpy()
                                                                 & t_["aralik_degisimi_var"].to_numpy()).sum()),
                "tahmin_yok_son_esitlik_affi": int(t_["son_esitlik_affi"].sum()),
                "plan_delist": int(dl.sum()), "plan_delist_disi": int((~dl).sum()),
                "tahmin_yok_tam_delist": int((t_["tam"].to_numpy() & dl).sum()),
                "tahmin_yok_tam_delist_disi": int((t_["tam"].to_numpy() & ~dl).sum()),
                "tahmin_yok_kuyruk_delist": int((t_["kuyruk_dogrulanmamis"].to_numpy() & dl).sum()),
                "tahmin_yok_kuyruk_delist_disi": int((t_["kuyruk_dogrulanmamis"].to_numpy() & ~dl).sum()),
                "tahmin_yok_aralik_degisimi_delist": int((t_["aralik_degisimi_var"].to_numpy() & dl).sum()),
                "bosluk_etkisi_tahmin_yok": int(ty_etki[m].sum()),
                "bosluk_etkisi_tahmin_yok_pencere_disi": int((ty_etki & ~iceren_sh)[m].sum()),
                "bosluk_giris_0400_tahmin_yok_tam": int((giris_0400 & ty["tam"].to_numpy())[m].sum()),
            })
            for tur in TAHMIN_YOK_FARK_TURLERI:
                satir[f"tahmin_yok_fark_{tur}"] = sum(1 for i, t2 in ty_turler.items()
                                                      if t2 == tur and kume_dizi[i] == kume)
            c_ = cd.loc[m]
            satir.update({
                "capa_duzeltme_tam": int(c_["tam"].sum()), "capa_duzeltme_capa_yok": int((~c_["capa_var"]).sum()),
                "capa_duzeltme_zincir_bozuk": int((c_["capa_var"] & ~c_["zincir_tam"]).sum()),
                "capa_duzeltme_son_bozuk": int((c_["capa_var"] & c_["zincir_tam"] & ~c_["son_tam"]).sum()),
                "capa_duzeltme_tam_tahmin_yok_degil": int((c_["tam"] & ~t_["tam"]).sum()),
                "tahmin_yok_tam_capa_duzeltme_degil": int((t_["tam"] & ~c_["tam"]).sum()),
                "capa_duzeltme_tam_rev8_degil": int((c_["tam"] & ~r["tam"]).sum()),
                "rev8_tam_capa_duzeltme_degil": int((r["tam"] & ~c_["tam"]).sum()),
                "capa_duzeltme_ilk_cift_affi": int(c_["ilk_cift_affi"].sum()),
                "capa_duzeltme_ilk_cift_affi_tam": int((c_["ilk_cift_affi"] & c_["tam"]).sum()),
                # Karsi ornek aramasi: son kosul bozuk ve beklenen odeme ani giris aninda ya da oncesinde.
                "capa_duzeltme_son_ihlali_giris_oncesi": int(c_["son_ihlali_giris_oncesi"].sum()),
                # Gevseklik olcusu (F2 taban sayisi)
                "capa_duzeltme_kuyruk_dogrulanmamis": int(c_["kuyruk_dogrulanmamis"].sum()),
                "capa_duzeltme_kuyruk_sifir": int(c_["kuyruk_sifir"].sum()),
                "capa_duzeltme_kuyruk_kismi": int(c_["kuyruk_kismi"].sum()),
                "capa_duzeltme_kuyruk_kismi_delist": int((c_["kuyruk_kismi"].to_numpy() & dl).sum()),
                "capa_duzeltme_kuyruk_kismi_delist_disi": int((c_["kuyruk_kismi"].to_numpy() & ~dl).sum()),
                "capa_duzeltme_kuyruk_kismi_aralik_degisimli": int((c_["kuyruk_kismi"].to_numpy()
                                                                    & c_["aralik_degisimi_var"].to_numpy()).sum()),
                "capa_duzeltme_son_esitlik_affi": int(c_["son_esitlik_affi"].sum()),
                "capa_duzeltme_aralik_degisimi_var": int(c_["aralik_degisimi_var"].sum()),
                "capa_duzeltme_tam_delist": int((c_["tam"].to_numpy() & dl).sum()),
                "capa_duzeltme_tam_delist_disi": int((c_["tam"].to_numpy() & ~dl).sum()),
                "bosluk_etkisi_capa_duzeltme": int(cd_etki[m].sum()),
                "bosluk_etkisi_capa_duzeltme_pencere_disi": int((cd_etki & ~iceren_sh)[m].sum()),
                "bosluk_giris_0400_capa_duzeltme_tam": int((giris_0400 & cd["tam"].to_numpy())[m].sum()),
            })
            for tur in CAPA_DUZELTME_FARK_TURLERI:
                satir[f"capa_duzeltme_fark_{tur}"] = sum(1 for i, t3 in cd_turler.items()
                                                         if t3 == tur and kume_dizi[i] == kume)
            satirlar.append(satir)
    return satirlar, farklar


# --- 3. T = K ----------------------------------------------------------------------


def tk_satirlari(sembol: str, grup: str, donemler, turler, mumlar: pd.DataFrame, seri: pd.DataFrame,
                 kumeler) -> list[dict]:
    """Her donem, izgara ve ufuk icin T = K olan tek sinyal: gercek plan; funding penceresi
    sonu K (bugun) ile B (donem sonu cikisi sayilsaydi) karsilastirilir. Saf; zaman okur."""
    zamanlar = pd.DatetimeIndex(mumlar["open_time"])
    zam = pd.DatetimeIndex(seri["odeme_zamani"])
    satirlar = []
    for i, (d, tur) in enumerate(zip(donemler, turler)):
        maske = np.asarray(P.donem_ici_4h_maskesi(zamanlar, donem_baslangic=d.baslangic, donem_bitis=d.bitis),
                           dtype=bool)
        zd = zamanlar[maske]
        k = d.kapanis
        gunler = None
        for bar, ufuklar in UFUKLAR.items():
            adim = P.adim(bar)
            for ufuk in ufuklar:
                t = k - ufuk * adim - adim  # giris = t + adim, T = giris + ufuk x adim = K
                satir = {"sembol": sembol, "donem_sira": i, "tur": tur, "bar": bar, "ufuk": ufuk,
                         "donem_bitis": d.bitis, "sinyal": t, "kume": None, "durum": None}
                if bar == config.BAR_1D:
                    if t != t.floor("D"):
                        satir["durum"] = "1d_sinyal_gunu_yok"  # B 20:00 degilse T = K olamaz
                        satirlar.append(satir)
                        continue
                    if gunler is None:
                        gunler = pd.DatetimeIndex(klines_modulu.gunluge_cevir(mumlar, donemler=[d])["open_time"])
                    sinyal_var = P.ayni_andaki_bar(gunler, t) is not None
                else:
                    sinyal_var = P.ayni_andaki_bar(zd, t) is not None
                if not sinyal_var:
                    satir["durum"] = "sinyal_bari_yok"
                    satirlar.append(satir)
                    continue
                kume = sinyal_kumesi(t, grup, kumeler)
                satir["kume"] = kume
                if kume is None:
                    satir["durum"] = "kume_yok"
                    satirlar.append(satir)
                    continue
                try:
                    plan = P.pozisyon_plani(zd, t, ufuk, bar, birincil_ufuk=config.BIRINCIL_UFUK[bar],
                                            kume_baslangic=kumeler[kume][1], kume_bitis=kumeler[kume][2],
                                            donem_baslangic=d.baslangic, donem_bitis=d.bitis)
                except P.OlayOlusmaz as hata:
                    satir["durum"] = f"ret_{P.ret_gerekcesi(hata)}"
                    satirlar.append(satir)
                    continue
                # T = K: Rev.8'de olagan cikis, Rev.9'da donem sonu; ikisinde de cikis ani K.
                if not (P.ayni_an(plan.cikis.hedef_cikis_ani, k) and P.ayni_an(plan.cikis_ani, k)):
                    satir["durum"] = f"beklenmeyen_{plan.cikis_turu}"
                    satirlar.append(satir)
                    continue
                son_k = rev8_pencere_sonu(plan)  # Rev.8: K
                a = rev8_tamlik_ayrintisi(seri, [plan.giris, plan.giris], [son_k, d.bitis])
                bk = (np.asarray(P.sonra(zam, d.bitis), dtype=bool)
                      & np.asarray(P.ayni_ya_da_once(zam, k), dtype=bool)) if len(zam) else np.zeros(0, bool)
                sh = son_hal_tamlik_ayrintisi(seri, [plan.giris], [d.bitis], [d.baslangic]).iloc[0]
                sa = son_adim_tamlik_ayrintisi(seri, [plan.giris], [d.bitis], [d.baslangic]).iloc[0]
                ty = tahmin_yok_tamlik_ayrintisi(seri, [plan.giris], [d.bitis], [d.baslangic]).iloc[0]
                cd = capa_duzeltme_tamlik_ayrintisi(seri, [plan.giris], [d.bitis], [d.baslangic]).iloc[0]
                satir.update(son_hal_tam=bool(sh["tam"]), son_adim_tam=bool(sa["tam"]),
                             tahmin_yok_tam=bool(ty["tam"]), capa_duzeltme_tam=bool(cd["tam"]))
                satir.update(durum="t_esit_k", pencere_sonu_bugun=son_k,
                             bk_arasi_kayit=int(bk.sum()), k_da_kayit=bool(np.any(P.ayni_an(zam, k))) if len(zam) else False,
                             tam_bugun=bool(a.at[0, "tam"]), tam_b_ile=bool(a.at[1, "tam"]),
                             son_tam_bugun=bool(a.at[0, "son_tam"]), kayit_var_b_ile=bool(a.at[1, "kayit_var"]))
                satirlar.append(satir)
    return satirlar


# --- Ana akis ----------------------------------------------------------------------


def sembol_olc(sembol: str, grup: str, donemler, sinif: str | None, veri_sonu_bari: pd.Timestamp):
    """Bir sembolun uc olcumu. Is parcacigi (ayri surec) icinde calisir."""
    mumlar = donem_modulu.toplam_doneme_kes(klines_modulu.ham_mumlari_yukle(sembol, config.BAR_4H), "open_time")
    fund = donem_modulu.toplam_doneme_kes(funding_modulu.ham_funding_yukle(sembol), "odeme_zamani")
    seri = funding_modulu.donem_sonrasi_kayitlari_at(fund, donemler, config.BAR_4H) if len(fund) else fund
    if seri.empty:
        seri = _bos_seri()
    # Oran sutunlari hicbir fonksiyona verilmez (yalnizca zaman ve aralik).
    seri = seri.loc[:, ["odeme_zamani", "aralik_saat"]].reset_index(drop=True)
    mz = pd.DatetimeIndex(mumlar["open_time"])
    hacim = mumlar["quote_volume"] if len(donemler) > 1 else None
    turler = donem_sonu_turleri(donemler, sinif, veri_sonu_bari, mz if len(donemler) > 1 else None, hacim)
    kumeler = kume_sinirlari()
    ds = donem_sonu_satirlari(sembol, donemler, turler, seri)
    seri_cf, eklendi = bosluk_seri(seri, donemler)
    bs, fk = baslangic_ve_farklar(sembol, grup, donemler, mumlar, seri, kumeler,
                                  seri_cf if eklendi else None, turler)
    for satir in bs:
        satir["bosluk_sembolu"] = eklendi
    tk = tk_satirlari(sembol, grup, donemler, turler, mumlar, seri, kumeler)
    sn = sinir_taramasi(sembol, donemler, seri)
    return ds, bs, fk, tk, sn


def main(argv: list[str] | None = None) -> None:
    ayristirici = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ayristirici.add_argument("--is-parcaci", type=int, default=4, help="es zamanli surec sayisi")
    ayristirici.add_argument("--semboller", nargs="*", default=None, help="yalnizca bu semboller (deneme)")
    ayristirici.add_argument("--cikti-dizini", type=Path, default=BU_DIZIN, help="CSV dizini (deneme icin)")
    argumanlar = ayristirici.parse_args(argv)
    with kosu_kilidi("rev9_hazirlik", CIKTI_ORTAM.parent):
        baslangic_zamani = pd.Timestamp.now(tz="UTC")
        git = git_durumu()
        evren = universe_modulu.evren_yukle()
        sinif = universe_modulu.delist_sinifi(evren, universe_modulu.exchange_info_anlik_yukle())
        sinif_haritasi = sinif.set_index("sembol")["sinif"].to_dict()
        grup = split_modulu.split_oku().set_index("sembol")["grup"].to_dict()
        semboller = universe_modulu.dahil_semboller(evren)
        donemler = {s: universe_modulu.sembol_donemleri(evren, s) for s in semboller}
        bitisler = [d.bitis for ds in donemler.values() for d in ds]
        veri_sonu_bari = max(bitisler) if bitisler else pd.Timestamp.min.tz_localize("UTC")
        secilen = [s for s in semboller if donemler[s] and (argumanlar.semboller is None or s in argumanlar.semboller)]
        d_s, b_s, f_s, t_s, s_s = [], [], [], [], []
        with ProcessPoolExecutor(max_workers=argumanlar.is_parcaci) as havuz:
            isler = [havuz.submit(sembol_olc, s, grup[s], donemler[s], sinif_haritasi.get(s), veri_sonu_bari)
                     for s in secilen]
            for is_ in isler:
                a, b, c, d, e = is_.result()
                d_s += a
                b_s += b
                f_s += c
                t_s += d
                s_s += e
        cikti = argumanlar.cikti_dizini
        csv_yaz(pd.DataFrame(d_s), cikti / CIKTI_DONEM_SONU.name)
        csv_yaz(pd.DataFrame(b_s), cikti / CIKTI_BASLANGIC.name)
        csv_yaz(pd.DataFrame(f_s), cikti / CIKTI_FARKLAR.name)
        csv_yaz(pd.DataFrame(t_s), cikti / CIKTI_TK.name)
        csv_yaz(pd.DataFrame(s_s), cikti / CIKTI_SINIR.name)
        csv_yaz(ortam_kaydi(git, baslangic_zamani, pd.Timestamp.now(tz="UTC")), cikti / CIKTI_ORTAM.name)
        print(f"sembol {len(secilen)} | donem sonu satiri {len(d_s)} | baslangic satiri {len(b_s)} | "
              f"fark {len(f_s)} | T=K satiri {len(t_s)} | sinir satiri {len(s_s)} -> {cikti}")


if __name__ == "__main__":
    try:
        main()
    except KosuKilidiHatasi as hata:
        print(f"HATA: {hata}", file=sys.stderr)
        sys.exit(2)
