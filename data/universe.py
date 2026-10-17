"""Tarihsel USDⓈ-M USDT perpetual evreni (on-kayit §2, rev.2 ve rev.7).

Delist edilmis sozlesmeler dahildir; on-kayit §2 bunlari acikca evrene katar.

Kapsam (revizyon 2):
  - Yalnizca `contractType = PERPETUAL` olan USDT marjinli sozlesmeler.
  - `contractType = TRADIFI_PERPETUAL` (hisse senedi, emtia, premarket) kapsam disi.
  - `underlyingType = INDEX` ve on-kayit §2'deki kesin haric listesi disarida.
  - exchangeInfo'da bulunmayan (delist) semboller elle siniflandirilmistir; bunlar
    icin haric karari yalnizca kesin listeden gelir.

Listeleme donemleri (revizyon 7): bar duzeyinde, mum hacminden turetilir
(`data.donem.listeleme_donemleri`). Karantina kurali kaldirildi; bucket'taki
`<SEMBOL>SETTLED` aylari yalnizca denetim sutunu olarak tutulur (`settled_aylari`).
Donem icinde hic funding kaydi olmayan (uzlasma sonrasi kayitlar sayilmaz) donem
`donem_funding_yok = True` ile isaretlenir; bu donem uc hipotezde de kullanilmaz.

Bu modul bucket'taki dizin ve dosya ADLARINI, onbellekteki 4h mumlari ve herkese
acik exchangeInfo uc noktasini kullanir. API anahtari kullanilmaz.
"""

from __future__ import annotations

from pathlib import Path

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


def exchange_info_anlik_siniflari(yol=None) -> dict[str, tuple[str, str]]:
    """{sembol: (contractType, underlyingType)}, depodaki goruntuden. Ag kullanmaz.

    `evren_kur` sozlesme ve dayanak tipini buradan okur (denetci bulgusu D-B4):
    canli uc nokta zamanla degisir (delist olan sembol yanittan duser), goruntu
    ise sabittir. Goruntude olmayan sembolun tipi bilinmez (None).
    """
    anlik = exchange_info_anlik_yukle(yol)
    return {
        r.symbol: (r.contractType, r.underlyingType)
        for r in anlik.itertuples()
    }


# --- exchangeInfo anlik goruntusu ---------------------------------------------
#
# Canli exchangeInfo zamanla degisir; delist siniflandirmasi (SETTLING /
# exchangeInfo disi), deliveryDate denetimi ve evren kurulumundaki sozlesme/dayanak
# tipi depoya alinmis tek bir goruntuden okunur. Goruntu hicbir olay, uygunluk ya
# da getiri hesabina girmez. Evren tablosu (`universe.csv`) commit edilmistir ve
# sabittir; goruntu yalnizca onun depodaki veriden yeniden uretilebilmesini saglar.

# Goruntude tutulan sembol alanlari. Filtreler ve emir tipleri denetimle ilgisiz
# oldugu icin atilir; ham yanitin SHA256 ozeti kanit olarak saklanir.
ANLIK_ALANLAR = (
    "symbol", "pair", "contractType", "status", "deliveryDate", "onboardDate",
    "underlyingType", "underlyingSubType", "baseAsset", "quoteAsset", "marginAsset",
)
SETTLING_DURUMU = "SETTLING"


def exchange_info_anlik_goruntu(ham_yanit: str, alinma_zamani) -> dict:
    """Ham exchangeInfo yanitini depoya alinacak kirpilmis goruntuye cevirir. Saf."""
    import hashlib
    import json

    govde = json.loads(ham_yanit)
    semboller = [
        {alan: s.get(alan) for alan in ANLIK_ALANLAR}
        for s in sorted(govde["symbols"], key=lambda s: s["symbol"])
    ]
    return {
        "kaynak": EXCHANGE_INFO,
        "alinma_zamani_utc": pd.Timestamp(alinma_zamani).tz_convert("UTC").strftime(_ZAMAN_BICIMI),
        "server_time_ms": govde.get("serverTime"),
        "ham_yanit_sha256": hashlib.sha256(ham_yanit.encode("utf-8")).hexdigest(),
        "sembol_sayisi": len(semboller),
        "symbols": semboller,
    }


def exchange_info_anlik_kaydet(yol=None) -> Path:
    """Canli exchangeInfo'yu indirip goruntu dosyasina yazar (ag kullanir).

    Dosya varsa uzerine yazmaz: goruntu bir kez alinir ve commit edilir.
    """
    import json

    hedef = config.EXCHANGE_INFO_ANLIK if yol is None else Path(yol)
    if hedef.exists():
        raise FileExistsError(f"{hedef} zaten var. exchangeInfo goruntusu bir kez alinir.")
    cevap = requests.get(EXCHANGE_INFO, timeout=60)
    cevap.raise_for_status()
    goruntu = exchange_info_anlik_goruntu(cevap.text, pd.Timestamp.now(tz="UTC"))
    hedef.write_text(json.dumps(goruntu, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return hedef


def exchange_info_anlik_yukle(yol=None) -> pd.DataFrame:
    """Depodaki exchangeInfo goruntusu; sembol basina bir satir. Ag kullanmaz.

    `deliveryDate` ve `onboardDate` UTC zaman damgasidir. Goruntu zamani
    `attrs["alinma_zamani_utc"]` icindedir.
    """
    import json

    hedef = config.EXCHANGE_INFO_ANLIK if yol is None else Path(yol)
    if not hedef.exists():
        raise FileNotFoundError(f"{hedef} yok. Once exchange_info_anlik_kaydet ile alinip commit edilmeli.")
    goruntu = json.loads(hedef.read_text(encoding="utf-8"))
    tablo = pd.DataFrame(goruntu["symbols"], columns=list(ANLIK_ALANLAR))
    for alan in ("deliveryDate", "onboardDate"):
        tablo[alan] = pd.to_datetime(tablo[alan], unit="ms", utc=True)
    tablo.attrs["alinma_zamani_utc"] = goruntu["alinma_zamani_utc"]
    tablo.attrs["ham_yanit_sha256"] = goruntu["ham_yanit_sha256"]
    return tablo


def delist_sinifi(evren: pd.DataFrame, anlik: pd.DataFrame) -> pd.DataFrame:
    """Dahil sembollerin goruntudeki durumu. Saf.

    Sutunlar: sembol, sinif, durum, deliveryDate, son_donem_bitis.
    `sinif`: "SETTLING" (uzlasmis), "exchangeInfo_disi" (goruntude yok) ya da
    goruntudeki `status` (ornegin TRADING). Delist = ilk ikisi.
    """
    dahil = evren.loc[~evren["haric"]]
    son_bitis = dahil.loc[dahil["donem_id"] >= 0].groupby("sembol")["donem_bitis"].max()
    durumlar = anlik.set_index("symbol")
    satirlar = []
    for sembol in sorted(dahil["sembol"].unique()):
        if sembol in durumlar.index:
            durum = durumlar.at[sembol, "status"]
            teslim = durumlar.at[sembol, "deliveryDate"]
            sinif = durum
        else:
            durum, teslim, sinif = None, pd.NaT, "exchangeInfo_disi"
        satirlar.append({"sembol": sembol, "sinif": sinif, "durum": durum,
                         "deliveryDate": teslim, "son_donem_bitis": son_bitis.get(sembol, pd.NaT)})
    tablo = pd.DataFrame(satirlar, columns=["sembol", "sinif", "durum", "deliveryDate", "son_donem_bitis"])
    # Tarih sutunlari her durumda UTC saat dilimli: tamami NaT olan sutun (ör.
    # yalnizca exchangeInfo disi sembollerden olusan tablo) aksi halde saat
    # dilimsiz tipe duser ve UTC'li bir anla karsilastirilinca TypeError verir.
    for alan in ("deliveryDate", "son_donem_bitis"):
        tablo[alan] = pd.to_datetime(tablo[alan], utc=True)
    return tablo


# --- SETTLED aylari (yalnizca denetim, on-kayit §2 rev.7) ---------------------


def settled_aylari_haritasi(sembol_dizinleri: list[str]) -> dict[str, list[str]]:
    """`<SEMBOL>SETTLED` dizinlerindeki 4h dosya aylari, sembol basina.

    Rev.7: SETTLED bilgisi hicbir kurala girmez; evren tablosunda denetim
    sutunudur. F1 olcumu SETTLED aylarinin yeniden listeleme aylari oldugunu
    gostermistir.
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


def settled_kirp(settled_aylari, ilk_ay: str, son_ay: str) -> list[str]:
    """Yalnizca sembolun ilk ile son ayi arasinda kalan SETTLED aylari. Saf."""
    bas, bit = pd.Period(ilk_ay, freq="M"), pd.Period(son_ay, freq="M")
    return sorted(str(p) for p in {pd.Period(a, freq="M") for a in settled_aylari} if bas <= p <= bit)


# --- Evren kurma -------------------------------------------------------------


def sembol_satirlari(ortak: dict, zamanlar, hacim, funding: pd.DataFrame,
                    hucreler_tam=None) -> list[dict]:
    """Bir sembolun evren satirlari: her listeleme donemi icin bir satir. Saf.

    `ortak`: sembol duzeyindeki sutunlar (sembol, ilk_ay, son_ay, ...). Donemi
    olmayan sembol (tum barlari dolgu) `donem_id = -1` ile tek satirdir.
    `funding`: sembolun ham funding kayitlari (`odeme_zamani` sutunu yeterli).
    `donem_funding_yok`: donem icinde, uzlasma sonrasi kayitlar sayilmadan, hic
    funding kaydi yok (on-kayit §2 rev.7; `funding.donemde_funding_var`).
    """
    from data import funding as funding_modulu

    donemler = donem_modulu.listeleme_donemleri(zamanlar, hacim, config.BAR_4H,
                                               hucreler_tam=hucreler_tam)
    if not donemler:
        return [{**ortak, "donem_id": -1, "donem_baslangic": pd.NaT, "donem_bitis": pd.NaT,
                 "donem_bar_sayisi": 0, "donem_gercek_bar_sayisi": 0, "donem_funding_yok": True}]
    satirlar = donem_modulu.donem_sinirlari(donemler).to_dict("records")
    return [
        {**ortak, **d, "donem_funding_yok": not funding_modulu.donemde_funding_var(funding, donem, config.BAR_4H)}
        for d, donem in zip(satirlar, donemler)
    ]


def evren_kur(haric_liste: frozenset[str] | None = None) -> pd.DataFrame:
    """Bucket, onbellekteki 4h mumlar ve depodaki exchangeInfo goruntusunden evren
    tablosunu kurar (bucket listesi ve eksik aylar icin ag kullanir).

    Her satir bir (sembol, listeleme donemi) ciftidir. Sutunlar `CSV_SUTUNLARI`;
    donem sinirlari zaman damgasidir. Sozlesme/dayanak tipi canli uc noktadan
    degil `exchange_info_anlik_siniflari`ndan okunur (denetci bulgusu D-B4).
    """
    from data import funding, klines  # klines, split uzerinden bu modulu dolayli import edebilir

    dizinler = bv.tum_sembol_dizinleri()
    adaylar = usdt_perpetual_adaylari(dizinler)
    # Canli uc nokta degil, depodaki goruntu (D-B4).
    siniflar = exchange_info_anlik_siniflari()
    settled = settled_aylari_haritasi(dizinler)

    satirlar = []
    for sembol in adaylar:
        # Toplam donem kesimi (denetci bulgusu D-B3): F1 denetimiyle ayni sinir.
        # Bucket'a sonradan eklenen aylar dosya sayisini, ay sinirlarini ve
        # donemleri degistirmez.
        dosyalar = [d for d in bv.mum_dosyalari(sembol, config.BAR_4H)
                    if donem_modulu.ay_toplam_donemde(bv.dosya_ayi(d))]
        if not dosyalar:
            continue
        aylar = [bv.dosya_ayi(d) for d in dosyalar]
        sozlesme_tipi, dayanak_tipi = siniflar.get(sembol, (None, None))

        gerekce = haric_gerekce(sembol, sozlesme_tipi, dayanak_tipi)
        if not gerekce and haric_mi(sembol, haric_liste):
            gerekce = "kesin haric listesi (on-kayit rev.2)"

        # Evren kurulumu butun gecmisi (B grubu, C2 donemi dahil) olcer: onay verisi izniyle (CLAUDE.md §3.1).
        with bv.onay_verisi_izni(f"universe.evren_kur({sembol})"):
            mumlar = donem_modulu.toplam_doneme_kes(klines.ham_mumlari_yukle(sembol, config.BAR_4H), "open_time")
            fund = donem_modulu.toplam_doneme_kes(funding.ham_funding_yukle(sembol), "odeme_zamani")
        funding_dosyalari = [d for d in bv.funding_dosyalari(sembol)
                             if donem_modulu.ay_toplam_donemde(bv.dosya_ayi(d))]
        ortak = {
            "sembol": sembol,
            "ilk_ay": aylar[0],
            "son_ay": aylar[-1],
            "dosya_sayisi_4h": len(dosyalar),
            "funding_dosya_sayisi": len(funding_dosyalari),
            "sozlesme_tipi": sozlesme_tipi,
            "dayanak_tipi": dayanak_tipi,
            "settled_aylari": ",".join(settled_kirp(settled.get(sembol, []), aylar[0], aylar[-1])),
            "haric": bool(gerekce),
            "haric_gerekce": gerekce,
        }
        satirlar.extend(sembol_satirlari(
            ortak, pd.DatetimeIndex(mumlar["open_time"]), mumlar["quote_volume"], fund,
            # Bar duzeyli mevcutluk olcutu donem sinirlarinda da gecerlidir (bulgu K-C9,
            # on-kayit §2 rev.12 "her hesapta"): hucresi bozuk bar sinir tanimlayamaz.
            hucreler_tam=klines.hucreleri_tam_mi(mumlar),
        ))

    return pd.DataFrame(satirlar).sort_values(["sembol", "donem_id"], ignore_index=True)


def evren_turet(yenile: bool = False, haric_liste: frozenset[str] | None = None) -> pd.DataFrame:
    """Evreni onbellekten okur, yoksa (veya `yenile`) bucket ve exchangeInfo goruntusunden kurar.

    YALNIZCA `data/universe.csv` dosyasini uretmek ve dogrulamak icindir.
    Analiz bu yolu kullanmaz: bucket zamanla degisir, yeniden turetilen evren
    commit edilmis tablodan sapabilir (on-kayit §2 rev.4).
    """
    yol = bv.onbellek_yolu(ONBELLEK_ADI)
    if not yenile:
        onbellek = bv.onbellekten_oku(yol)
        if onbellek is not None:
            return onbellek
    evren = evren_kur(haric_liste)
    bv.onbellege_yaz(evren, yol)
    return evren


# --- Sabit evren tablosu (on-kayit §2 rev.4, rev.7) ---------------------------

# Rev.7: donem sinirlari bar duzeyindedir ve CSV'de ISO 8601 UTC zaman damgasi
# ("2021-01-05T08:00:00Z") olarak yazilir; deterministiktir.
CSV_SUTUNLARI = [
    "sembol",
    "ilk_ay",
    "son_ay",
    "dosya_sayisi_4h",
    "funding_dosya_sayisi",
    "sozlesme_tipi",
    "dayanak_tipi",
    "settled_aylari",
    "haric",
    "haric_gerekce",
    "donem_id",
    "donem_baslangic",
    "donem_bitis",
    "donem_bar_sayisi",
    "donem_gercek_bar_sayisi",
    "donem_funding_yok",
]
_METIN_SUTUNLARI = (
    "sembol",
    "ilk_ay",
    "son_ay",
    "sozlesme_tipi",
    "dayanak_tipi",
    "settled_aylari",
    "haric_gerekce",
)
_ZAMAN_SUTUNLARI = ("donem_baslangic", "donem_bitis")
_TAMSAYI_SUTUNLARI = ("dosya_sayisi_4h", "funding_dosya_sayisi", "donem_id", "donem_bar_sayisi", "donem_gercek_bar_sayisi")
_BOOL_SUTUNLARI = ("haric", "donem_funding_yok")
_ZAMAN_BICIMI = "%Y-%m-%dT%H:%M:%SZ"


class EvrenUyusmazligi(ValueError):
    """Commit edilmis evren tablosu onbellekteki turetilmis evrenle uyusmuyor."""


def _normallestir(evren: pd.DataFrame) -> pd.DataFrame:
    """Evreni CSV'nin tuttugu sutun ve tiplere indirger (zamanlar UTC); deterministik sira."""
    tablo = evren.loc[:, CSV_SUTUNLARI].copy()
    for sutun in _METIN_SUTUNLARI:
        tablo[sutun] = tablo[sutun].fillna("").astype(str)
    for sutun in _BOOL_SUTUNLARI:
        tablo[sutun] = tablo[sutun].astype(bool)
    for sutun in _TAMSAYI_SUTUNLARI:
        tablo[sutun] = tablo[sutun].astype("int64")
    for sutun in _ZAMAN_SUTUNLARI:
        tablo[sutun] = pd.to_datetime(tablo[sutun].replace("", pd.NaT), utc=True)
    return tablo.sort_values(["sembol", "donem_id"], ignore_index=True)


def _csv_bicimine(evren: pd.DataFrame) -> pd.DataFrame:
    tablo = _normallestir(evren)
    for sutun in _ZAMAN_SUTUNLARI:
        tablo[sutun] = tablo[sutun].dt.strftime(_ZAMAN_BICIMI).fillna("")
    return tablo


def evren_csv_yaz(evren: pd.DataFrame, yol=None):
    """`data/universe.csv` dosyasini yazar. Dosya varsa uzerine yazmaz (split.csv gibi)."""
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

    Ag ve onbellek kullanmaz; canli exchangeInfo'dan yeniden turetmez. Donem
    sinirlari UTC zaman damgasi olarak doner.
    """
    hedef = config.UNIVERSE_CSV if yol is None else Path(yol)
    if not hedef.exists():
        raise FileNotFoundError(f"{hedef} yok. Once evren tablosu uretilip commit edilmeli.")
    tablo = pd.read_csv(
        hedef,
        dtype={sutun: str for sutun in (*_METIN_SUTUNLARI, *_ZAMAN_SUTUNLARI)},
        keep_default_na=False,
        encoding="utf-8",
    )
    eksik = [s for s in CSV_SUTUNLARI if s not in tablo.columns]
    if eksik:
        raise ValueError(f"{hedef}: rev.7 evren tablosu bicimi degil; eksik sutunlar: {eksik}")
    for sutun in _BOOL_SUTUNLARI:
        deger = tablo[sutun].astype(str).map({"True": True, "False": False})
        if deger.isna().any():
            raise ValueError(f"{hedef}: {sutun!r} sutununda True/False disi deger var.")
        tablo[sutun] = deger.astype(bool)
    return _normallestir(tablo)


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
    try:
        beklenen = _normallestir(onbellek)
    except KeyError as hata:
        raise EvrenUyusmazligi(f"Onbellekteki evren rev.7 bicimi degil: {hata}") from None
    try:
        pd.testing.assert_frame_equal(
            csv_evren.reset_index(drop=True), beklenen.reset_index(drop=True), check_dtype=False
        )
    except AssertionError as hata:
        raise EvrenUyusmazligi(f"Evren tablosu onbellekle uyusmuyor: {hata}") from None


def dahil_semboller(evren: pd.DataFrame) -> list[str]:
    """Haric tutulmayan semboller (calisma evreni), tekil ve sirali."""
    return sorted(evren.loc[~evren["haric"], "sembol"].unique().tolist())


def sembol_donemleri(evren: pd.DataFrame, sembol: str) -> list[donem_modulu.Donem]:
    """Bir sembolun listeleme donemleri (bar duzeyinde, on-kayit §2 rev.7)."""
    satirlar = evren.loc[(evren["sembol"] == sembol) & (evren["donem_id"] >= 0)].sort_values("donem_id")
    return [
        donem_modulu.Donem(
            pd.Timestamp(r["donem_baslangic"]), pd.Timestamp(r["donem_bitis"]),
            int(r["donem_bar_sayisi"]), int(r["donem_gercek_bar_sayisi"]),
        )
        for _, r in satirlar.iterrows()
    ]


def settled_listesi(evren: pd.DataFrame, sembol: str) -> list[str]:
    """Bir sembolun SETTLED aylari (yalnizca denetim; hicbir kurala girmez)."""
    satirlar = evren.loc[evren["sembol"] == sembol, "settled_aylari"]
    if satirlar.empty:
        return []
    return [a for a in str(satirlar.iloc[0]).split(",") if a]
