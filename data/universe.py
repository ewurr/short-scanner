"""Tarihsel USDⓈ-M USDT perpetual evreni (on-kayit §2, revizyon 2).

Delist edilmis sozlesmeler dahildir; on-kayit §2 bunlari acikca evrene katar ve
disarida kalmalarinin sonuclari kotumser yonde saptiracagini soyler.

Kapsam (revizyon 2):
  - Yalnizca `contractType = PERPETUAL` olan USDT marjinli sozlesmeler.
  - `contractType = TRADIFI_PERPETUAL` (hisse senedi, emtia, premarket) kapsam disi.
  - `underlyingType = INDEX` ve on-kayit §2'deki kesin haric listesi disarida.
  - exchangeInfo'da bulunmayan (delist) semboller elle siniflandirilmistir; bunlar
    icin haric karari yalnizca kesin listeden gelir.

Bu modul bucket'taki dizin ve dosya ADLARINI ve herkese acik exchangeInfo uc
noktasini kullanir. API anahtari kullanilmaz.
"""

from __future__ import annotations

import pandas as pd
import requests

import config
from data import binance_vision as bv
from data import donem as donem_modulu

ONBELLEK_ADI = "universe.parquet"
EXCHANGE_INFO = "https://fapi.binance.com/fapi/v1/exchangeInfo"

# Vadeli (teslimatli) sozlesmeler sembolde alt cizgi tasir: BTCUSDT_210625.
VADELI_ISARETI = "_"


# --- Aday suzme (saf) --------------------------------------------------------


def usdt_perpetual_adaylari(sembol_dizinleri: list[str]) -> list[str]:
    """Bucket dizin adlarindan USDT marjinli perpetual adaylarini suzer.

    Elenenler: vadeli sozlesmeler (`_`), USDT disi teminat (USDC, BUSD, ...),
    `SETTLED` son ekli tekil kayitlar. Saf fonksiyon.
    """
    adaylar = []
    for sembol in sembol_dizinleri:
        if VADELI_ISARETI in sembol:
            continue
        if sembol.endswith(config.SETTLED_SONEKI):
            continue
        if not sembol.endswith(config.TEMINAT_SONEKI):
            continue
        adaylar.append(sembol)
    return sorted(set(adaylar))


def haric_mi(sembol: str, haric_liste: frozenset[str] | None = None) -> bool:
    """On-kayit §2'deki kesin haric tutma listesinde mi?

    Liste aciktir, duzenli ifade kullanilmaz: `BUSDT` (BU coini) ve `TUSDT`
    (Threshold) stablecoin degildir ve desen eslestirmesi bunlari yanlislikla
    eler.
    """
    liste = config.HARIC_SEMBOLLER if haric_liste is None else haric_liste
    return sembol in liste


def haric_gerekce(sembol: str, sozlesme_tipi: str | None, dayanak_tipi: str | None) -> str:
    """Sembol neden haric tutuldu? Bos dize = haric degil. Saf fonksiyon."""
    if sozlesme_tipi == config.TRADIFI_TIPI:
        return f"kapsam disi: contractType={config.TRADIFI_TIPI} (on-kayit rev.2)"
    if dayanak_tipi == config.ENDEKS_TIPI:
        return "endeks sozlesmesi: underlyingType=INDEX (on-kayit rev.2)"
    if sembol in config.HARIC_ENDEKSLER:
        return "endeks sozlesmesi: kesin liste (on-kayit rev.2)"
    if sembol in config.HARIC_STABLECOIN:
        return "stablecoin tabanli cift: kesin liste (on-kayit rev.2)"
    return ""


# --- exchangeInfo ------------------------------------------------------------


def exchange_info_siniflari() -> dict[str, tuple[str, str]]:
    """{sembol: (contractType, underlyingType)}. Herkese acik uc nokta."""
    cevap = requests.get(EXCHANGE_INFO, timeout=60)
    cevap.raise_for_status()
    return {
        s["symbol"]: (s.get("contractType"), s.get("underlyingType"))
        for s in cevap.json()["symbols"]
    }


# --- Karantina ---------------------------------------------------------------


def karantina_haritasi(sembol_dizinleri: list[str]) -> dict[str, list[str]]:
    """`<SEMBOL>SETTLED` dizinlerinden sembol basina karantina ayi adaylari.

    Ay listesi dosya adlarindan gelir. Sembolun ilk/son ayina gore kirpma
    `karantina_kirp` ile yapilir (on-kayit rev.2: yalnizca ilk ile son ay
    ARASINDA kalan aylar karantinadir).
    """
    harita: dict[str, list[str]] = {}
    for dizin in sembol_dizinleri:
        if not dizin.endswith(config.SETTLED_SONEKI):
            continue
        temel = dizin
        while temel.endswith(config.SETTLED_SONEKI):
            temel = temel[: -len(config.SETTLED_SONEKI)]
        temel = temel.rstrip("_")  # ICPUSDT_SETTLED gibi kayitlar icin
        aylar = [bv.dosya_ayi(a) for a in bv.mum_dosyalari(dizin, config.BAR_4H)]
        if aylar:
            harita.setdefault(temel, []).extend(aylar)
    return {k: sorted(set(v)) for k, v in harita.items()}


def karantina_kirp(karantina_aylari, ilk_ay: str, son_ay: str) -> list[str]:
    """Yalnizca sembolun ilk ile son ayi arasinda kalan karantina aylari. Saf."""
    bas, bit = pd.Period(ilk_ay, freq="M"), pd.Period(son_ay, freq="M")
    return sorted(
        str(p) for p in {pd.Period(a, freq="M") for a in karantina_aylari} if bas <= p <= bit
    )


# --- Evren kurma -------------------------------------------------------------


def evren_kur(haric_liste: frozenset[str] | None = None) -> pd.DataFrame:
    """Bucket ve exchangeInfo'dan evren tablosunu kurar (ag kullanir).

    Her satir bir (sembol, listeleme donemi) ciftidir. Sutunlar:
      sembol, ilk_ay, son_ay, dosya_sayisi_4h, funding_dosya_sayisi,
      sozlesme_tipi, dayanak_tipi, karantina_aylari, haric, haric_gerekce,
      donem_id, donem_bas_ay, donem_son_ay, donem_baslangic, donem_bitis
    """
    dizinler = bv.tum_sembol_dizinleri()
    adaylar = usdt_perpetual_adaylari(dizinler)
    siniflar = exchange_info_siniflari()
    karantina = karantina_haritasi(dizinler)

    satirlar = []
    for sembol in adaylar:
        dosyalar = bv.mum_dosyalari(sembol, config.BAR_4H)
        if not dosyalar:
            continue
        aylar = [bv.dosya_ayi(d) for d in dosyalar]
        sozlesme_tipi, dayanak_tipi = siniflar.get(sembol, (None, None))

        gerekce = haric_gerekce(sembol, sozlesme_tipi, dayanak_tipi)
        if not gerekce and haric_mi(sembol, haric_liste):
            gerekce = "kesin haric listesi (on-kayit rev.2)"
        dis = bool(gerekce)

        kar = karantina_kirp(karantina.get(sembol, []), aylar[0], aylar[-1])
        donemler = donem_modulu.listeleme_donemleri(aylar, kar)
        sinirlar = donem_modulu.donem_sinirlari(donemler)

        ortak = {
            "sembol": sembol,
            "ilk_ay": aylar[0],
            "son_ay": aylar[-1],
            "dosya_sayisi_4h": len(dosyalar),
            "funding_dosya_sayisi": len(bv.funding_dosyalari(sembol)),
            "sozlesme_tipi": sozlesme_tipi,
            "dayanak_tipi": dayanak_tipi,
            "karantina_aylari": ",".join(kar),
            "haric": dis,
            "haric_gerekce": gerekce,
        }
        if sinirlar.empty:  # tum aylari karantinaya dusen sembol
            satirlar.append(
                {
                    **ortak,
                    "donem_id": -1,
                    "donem_bas_ay": "",
                    "donem_son_ay": "",
                    "donem_baslangic": pd.NaT,
                    "donem_bitis": pd.NaT,
                }
            )
        else:
            for _, d in sinirlar.iterrows():
                satirlar.append({**ortak, **d.to_dict()})

    return pd.DataFrame(satirlar).sort_values(["sembol", "donem_id"], ignore_index=True)


def evren_turet(yenile: bool = False, haric_liste: frozenset[str] | None = None) -> pd.DataFrame:
    """Evreni onbellekten okur, yoksa (veya `yenile`) bucket ve exchangeInfo'dan kurar.

    YALNIZCA `data/universe.csv` dosyasini uretmek ve dogrulamak icindir.
    Analiz bu yolu kullanmaz: exchangeInfo zamanla degisir (delist olan sembol
    yanittan duser), yeniden turetilen evren commit edilmis tablodan sapabilir
    (on-kayit §2 rev.4).
    """
    yol = bv.onbellek_yolu(ONBELLEK_ADI)
    if not yenile:
        onbellek = bv.onbellekten_oku(yol)
        if onbellek is not None:
            return onbellek
    evren = evren_kur(haric_liste)
    bv.onbellege_yaz(evren, yol)
    return evren


# --- Sabit evren tablosu (on-kayit §2 rev.4) ---------------------------------

# CSV'ye zaman damgasi yazilmaz; donem sinirlari aylardan deterministik kurulur.
CSV_SUTUNLARI = [
    "sembol",
    "ilk_ay",
    "son_ay",
    "dosya_sayisi_4h",
    "funding_dosya_sayisi",
    "sozlesme_tipi",
    "dayanak_tipi",
    "karantina_aylari",
    "haric",
    "haric_gerekce",
    "donem_id",
    "donem_bas_ay",
    "donem_son_ay",
]
_METIN_SUTUNLARI = (
    "sembol",
    "ilk_ay",
    "son_ay",
    "sozlesme_tipi",
    "dayanak_tipi",
    "karantina_aylari",
    "haric_gerekce",
    "donem_bas_ay",
    "donem_son_ay",
)


class EvrenUyusmazligi(ValueError):
    """Commit edilmis evren tablosu onbellekteki turetilmis evrenle uyusmuyor."""


def _csv_bicimine(evren: pd.DataFrame) -> pd.DataFrame:
    """Evreni CSV'nin tuttugu sutun ve tiplere indirger; deterministik sira."""
    tablo = evren.loc[:, CSV_SUTUNLARI].copy()
    for sutun in _METIN_SUTUNLARI:
        tablo[sutun] = tablo[sutun].fillna("").astype(str)
    tablo["haric"] = tablo["haric"].astype(bool)
    for sutun in ("dosya_sayisi_4h", "funding_dosya_sayisi", "donem_id"):
        tablo[sutun] = tablo[sutun].astype("int64")
    return tablo.sort_values(["sembol", "donem_id"], ignore_index=True)


def _donem_zamanlarini_kur(tablo: pd.DataFrame) -> pd.DataFrame:
    """donem_bas_ay / donem_son_ay'dan UTC donem sinirlarini kurar (donem_sinirlari ile ayni)."""
    sonuc = tablo.copy()
    baslangic, bitis = [], []
    for bas_ay, son_ay, kimlik in zip(sonuc["donem_bas_ay"], sonuc["donem_son_ay"], sonuc["donem_id"]):
        if kimlik < 0 or not bas_ay:
            baslangic.append(pd.NaT)
            bitis.append(pd.NaT)
            continue
        baslangic.append(pd.Period(bas_ay, freq="M").to_timestamp(how="start").tz_localize("UTC"))
        bitis.append(pd.Period(son_ay, freq="M").to_timestamp(how="end").tz_localize("UTC"))
    sonuc["donem_baslangic"] = pd.to_datetime(pd.Series(baslangic, index=sonuc.index), utc=True)
    sonuc["donem_bitis"] = pd.to_datetime(pd.Series(bitis, index=sonuc.index), utc=True)
    return sonuc


def evren_csv_yaz(evren: pd.DataFrame, yol=None):
    """`data/universe.csv` dosyasini yazar. Dosya varsa uzerine yazmaz (split.csv gibi)."""
    from pathlib import Path

    hedef = config.UNIVERSE_CSV if yol is None else Path(yol)
    if hedef.exists():
        raise FileExistsError(
            f"{hedef} zaten var. Evren tablosu split.csv gibi sabittir (on-kayit §2 rev.4)."
        )
    hedef.parent.mkdir(parents=True, exist_ok=True)
    _csv_bicimine(evren).to_csv(hedef, index=False, lineterminator="\n", encoding="utf-8")
    return hedef


def evren_yukle(yol=None) -> pd.DataFrame:
    """Commit edilmis evren tablosunu okur (on-kayit §2 rev.4).

    Ag ve onbellek kullanmaz; canli exchangeInfo'dan yeniden turetmez. Donen
    cerceve `evren_kur` ile ayni sutunlara sahiptir (donem sinirlari dahil).
    """
    from pathlib import Path

    hedef = config.UNIVERSE_CSV if yol is None else Path(yol)
    if not hedef.exists():
        raise FileNotFoundError(f"{hedef} yok. Once evren tablosu uretilip commit edilmeli.")
    tablo = pd.read_csv(
        hedef,
        dtype={sutun: str for sutun in _METIN_SUTUNLARI},
        keep_default_na=False,
        encoding="utf-8",
    )
    haric = tablo["haric"].astype(str).map({"True": True, "False": False})
    if haric.isna().any():
        raise ValueError(f"{hedef}: 'haric' sutununda True/False disi deger var.")
    tablo["haric"] = haric.astype(bool)
    return _donem_zamanlarini_kur(_csv_bicimine(tablo))


def evren_onbellekle_dogrula(yol=None, onbellek=None) -> None:
    """Commit edilmis evren tablosu onbellekteki turetilmis evrenle birebir ayni mi?

    Uyusmazlikta `EvrenUyusmazligi` firlatir. `onbellek` verilmezse
    `cache/universe.parquet` okunur.
    """
    csv_evren = evren_yukle(yol)
    if onbellek is None:
        onbellek = bv.onbellekten_oku(bv.onbellek_yolu(ONBELLEK_ADI))
        if onbellek is None:
            raise FileNotFoundError("Onbellekte evren yok; karsilastirma yapilamaz.")
    beklenen = _donem_zamanlarini_kur(_csv_bicimine(onbellek))
    try:
        pd.testing.assert_frame_equal(
            csv_evren.reset_index(drop=True), beklenen.reset_index(drop=True), check_dtype=False
        )
    except AssertionError as hata:
        raise EvrenUyusmazligi(f"Evren tablosu onbellekle uyusmuyor: {hata}") from None
    # Donem sinirlari aylardan kuruldu; onbellekteki zaman damgalariyla da ayni olmali.
    onb = onbellek.sort_values(["sembol", "donem_id"], ignore_index=True)
    for sutun in ("donem_baslangic", "donem_bitis"):
        if not csv_evren[sutun].equals(pd.to_datetime(onb[sutun], utc=True)):
            raise EvrenUyusmazligi(f"'{sutun}' onbellekteki zaman damgalariyla uyusmuyor.")


def dahil_semboller(evren: pd.DataFrame) -> list[str]:
    """Haric tutulmayan semboller (calisma evreni), tekil ve sirali."""
    return sorted(evren.loc[~evren["haric"], "sembol"].unique().tolist())


def sembol_donemleri(evren: pd.DataFrame, sembol: str) -> list[tuple[pd.Period, pd.Period]]:
    """Bir sembolun listeleme donemleri, `donem` modulunun bekledigi bicimde."""
    satirlar = evren.loc[(evren["sembol"] == sembol) & (evren["donem_id"] >= 0)]
    return [
        (pd.Period(r["donem_bas_ay"], freq="M"), pd.Period(r["donem_son_ay"], freq="M"))
        for _, r in satirlar.sort_values("donem_id").iterrows()
    ]


def karantina_listesi(evren: pd.DataFrame, sembol: str) -> list[str]:
    """Bir sembolun karantina aylari."""
    satirlar = evren.loc[evren["sembol"] == sembol, "karantina_aylari"]
    if satirlar.empty:
        return []
    metin = satirlar.iloc[0]
    return [a for a in str(metin).split(",") if a]
