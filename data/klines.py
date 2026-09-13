"""Mum verisi: 4h indirme + onbellek, 1d turetme.

Bar zamani = barin acilis zamani, hepsi UTC (CLAUDE.md §5).

1 gunluk mumlar birincil kaynaktan indirilmez, 4h barlardan turetilir
(kullanici karari, F1 plani):
  - UTC gunu; open = ilk, high = max, low = min, close = son,
    volume ve quote_volume = toplam,
  - 6 adet 4h bari tam olmayan gunler kismi toplanmaz, eksik sayilir.
Turetmenin dogrulugu birincil 1d dosyalariyla `cross_dogrula` ile karsilastirilir
ve fark denetim raporuna yazilir.
"""

from __future__ import annotations

import pandas as pd

import config
from data import binance_vision as bv

# Bir UTC gunu tam olmasi icin gereken 4h bar sayisi.
GUNLUK_BAR_SAYISI = 6

SAYISAL_SUTUNLAR = [
    "open",
    "high",
    "low",
    "close",
    "volume",
    "quote_volume",
    "count",
    "taker_buy_volume",
    "taker_buy_quote_volume",
]


def _ay_cercevesi(govde: bytes) -> pd.DataFrame:
    """Bir aylik mum zip'ini duzenli bir DataFrame'e cevirir."""
    ham = bv.zip_csv_oku(govde, bv.MUM_SUTUNLARI)
    ham = ham[bv.MUM_SUTUNLARI].copy()
    # Bazi aylik dosyalarda zaman damgasi mikrosaniye olarak yazilmis; buyukluge
    # bakip birimi secmek milisaniye varsayimindan daha guvenli.
    ham["open_time"] = _zaman_cevir(ham["open_time"])
    ham["close_time"] = _zaman_cevir(ham["close_time"])
    for sutun in SAYISAL_SUTUNLAR:
        ham[sutun] = pd.to_numeric(ham[sutun], errors="coerce")
    ham = ham.drop(columns=["ignore"])
    return ham.sort_values("open_time", ignore_index=True)


def _zaman_cevir(seri: pd.Series) -> pd.Series:
    """Milisaniye veya mikrosaniye epoch'unu UTC zaman damgasina cevirir."""
    sayi = pd.to_numeric(seri, errors="coerce")
    birim = "us" if sayi.dropna().gt(1e14).any() else "ms"
    return pd.to_datetime(sayi, unit=birim, utc=True)


def ay_indir(sembol: str, bar: str, ay: str) -> pd.DataFrame:
    """Tek bir ayin mumlarini indirir (onbelleksiz, checksum dogrulamali)."""
    anahtar = f"{bv.MUM_ONEKI}/{sembol}/{bar}/{sembol}-{bar}-{ay}.zip"
    return _ay_cercevesi(bv.zip_indir(anahtar))


def mumlari_yukle(
    sembol: str,
    bar: str,
    kume: str,
    onay: bool = False,
    yenile: bool = False,
) -> pd.DataFrame:
    """Bir sembolun mumlarini KUME KORUMASIYLA yukler (CLAUDE.md §3.2-3.3).

    `split.yukle` ile ayni davranis: `kume` zorunludur ve varsayilani yoktur;
    C1/C2 icin `onay=True` ve acik bir `split.onay_kosusu` sarttir, aksi halde
    kayda hicbir sey yazmadan PermissionError; sembol kumenin grubunda degilse
    bos cerceve doner; veri kume tarih araligina kesilir. Analiz ve olay kodu
    mumlara yalnizca bu yoldan erisir.
    """
    from data import split as split_modulu  # split bu modulu import eder; dongu onlenir

    return split_modulu.yukle(
        sembol,
        bar,
        kume,
        onay=onay,
        mum_yukleyici=lambda s, b: ham_mumlari_yukle(s, b, yenile=yenile),
    )


def ham_mumlari_yukle(sembol: str, bar: str = config.BAR_4H, yenile: bool = False) -> pd.DataFrame:
    """Bir sembolun TUM mumlari, KUME KORUMASI OLMADAN; yalnizca eksik aylari indirir.

    B grubu ve C2 donemi dahil tum gecmisi dondurur. Yalnizca veri katmani
    (`split.yukle`) ve tum gecmisi olcmesi gereken F1 kapsama denetimi icindir
    (CLAUDE.md §3.1). Analiz ve olay kodu bunu CAGIRMAZ.

    Onbellek ay basina tek parquet dosyasidir (`cache/klines/<sembol>/<bar>/<ay>.parquet`),
    bu sayede yeniden calistirma tamamlanmis aylari yeniden indirmez.
    """
    if bar == config.BAR_1D:
        return gunluge_cevir(ham_mumlari_yukle(sembol, config.BAR_4H, yenile))

    anahtarlar = bv.mum_dosyalari(sembol, bar)
    parcalar = []
    for anahtar in anahtarlar:
        ay = bv.dosya_ayi(anahtar)
        yol = bv.onbellek_yolu("klines", sembol, bar, f"{ay}.parquet")
        cerceve = None if yenile else bv.onbellekten_oku(yol)
        if cerceve is None:
            cerceve = _ay_cercevesi(bv.zip_indir(anahtar))
            bv.onbellege_yaz(cerceve, yol)
        parcalar.append(cerceve)

    if not parcalar:
        return pd.DataFrame(columns=[s for s in bv.MUM_SUTUNLARI if s != "ignore"])

    return _tekrarsiz_birlestir(parcalar, f"ham_mumlari_yukle({sembol}, {bar})")


def _tekrarsiz_birlestir(parcalar: list[pd.DataFrame], yer: str) -> pd.DataFrame:
    """Aylik parcalari birlestirir; tekrarlanan `open_time` varsa HATA verir.

    F1 kapanis bulgusu 14: eskiden `drop_duplicates(keep="last")` ile tekrarlar
    sessizce siliniyordu. Iki kayit celisiyorsa hangisinin dogru oldugu bilinemez
    ve secim iz birakmazdi. `data.pencere` tekrarlanan damgayi bozuk veri sayar;
    yukleyici de ayni tutumu izler. F1 kapanis taramasinda onbellekte hic tekrar
    bulunmadi (678 sembol, 3.692.573 4h bar, 615.689 birincil 1d bar).
    """
    from data.pencere import ZamanDizisiHatasi

    tum = pd.concat(parcalar, ignore_index=True)
    tekrar = tum["open_time"].duplicated(keep=False)
    if tekrar.any():
        ornek = ", ".join(str(z) for z in tum.loc[tekrar, "open_time"].unique()[:3])
        raise ZamanDizisiHatasi(
            f"{yer}: {int(tum['open_time'].duplicated().sum())} tekrarlanan bar damgasi "
            f"(ornek: {ornek}). Bozuk onbellek; sessizce silinmez, dosyalar yeniden "
            "indirilmeli (yenile=True) ve denetlenmeli."
        )
    return tum.sort_values("open_time", ignore_index=True)


def donem_kes(cerceve: pd.DataFrame, bas, son) -> pd.DataFrame:
    """Kapali [bas, son] araligina keser. Saf fonksiyon."""
    if cerceve.empty:
        return cerceve
    maske = (cerceve["open_time"] >= bas) & (cerceve["open_time"] <= son)
    return cerceve.loc[maske].reset_index(drop=True)


# --- 1d turetme --------------------------------------------------------------


def gunluge_cevir(dort_saatlik: pd.DataFrame) -> pd.DataFrame:
    """4h barlardan UTC gunluk barlar turetir.

    Tam olmayan gunler (6'dan az bar) dusurulur; kismi toplama yapilmaz.
    Saf fonksiyon: ag veya disk kullanmaz.
    """
    if dort_saatlik.empty:
        return dort_saatlik.copy()

    calisma = dort_saatlik.sort_values("open_time").copy()
    calisma["gun"] = calisma["open_time"].dt.floor("D")

    toplanan = calisma.groupby("gun", sort=True).agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        quote_volume=("quote_volume", "sum"),
        count=("count", "sum"),
        taker_buy_volume=("taker_buy_volume", "sum"),
        taker_buy_quote_volume=("taker_buy_quote_volume", "sum"),
        close_time=("close_time", "last"),
        bar_sayisi=("open", "size"),
    )
    tam = toplanan.loc[toplanan["bar_sayisi"] == GUNLUK_BAR_SAYISI].drop(columns=["bar_sayisi"])
    tam = tam.reset_index().rename(columns={"gun": "open_time"})
    return tam[[s for s in bv.MUM_SUTUNLARI if s != "ignore"]]


def cross_dogrula(turetilmis: pd.DataFrame, birincil: pd.DataFrame) -> pd.DataFrame:
    """Turetilmis 1d ile kaynaktaki birincil 1d dosyalarini karsilastirir.

    Her ortak gun icin OHLC ve hacim bagil farkini doner. Yalnizca veri
    butunlugu olcumudur; fiyat davranisi veya getiri hesaplamaz.
    """
    ortak = turetilmis.merge(birincil, on="open_time", suffixes=("_tur", "_bir"))
    sonuc = pd.DataFrame({"open_time": ortak["open_time"]})
    for sutun in ["open", "high", "low", "close", "volume", "quote_volume"]:
        a = ortak[f"{sutun}_tur"]
        b = ortak[f"{sutun}_bir"]
        sonuc[f"{sutun}_bagil_fark"] = (a - b).abs() / b.where(b != 0)
    sonuc.attrs["yalniz_turetilmis"] = int(
        (~turetilmis["open_time"].isin(birincil["open_time"])).sum()
    )
    sonuc.attrs["yalniz_birincil"] = int(
        (~birincil["open_time"].isin(turetilmis["open_time"])).sum()
    )
    return sonuc


def birincil_gunluk_indir(
    sembol: str,
    kume: str,
    onay: bool = False,
    yenile: bool = False,
) -> pd.DataFrame:
    """Kaynaktaki birincil 1d dosyalarini KUME KORUMASIYLA yukler (CLAUDE.md §3.2-3.3).

    `mumlari_yukle` ve `funding_yukle` ile ayni kapidan (`split.kume_erisimi`)
    gecer: `kume` zorunludur ve varsayilani yoktur; C1/C2 icin `onay=True` ve
    acik bir `split.onay_kosusu` sarttir; sembol kumenin grubunda degilse bos
    cerceve doner; veri kume araligina kesilir.
    """
    from data import split as split_modulu  # split bu modulu import eder; dongu onlenir

    izinli, bas, son = split_modulu.kume_erisimi(sembol, kume, onay=onay)
    if not izinli:
        return pd.DataFrame(columns=[s for s in bv.MUM_SUTUNLARI if s != "ignore"])
    return donem_kes(ham_birincil_gunluk_indir(sembol, yenile=yenile), bas, son)


def ham_birincil_gunluk_indir(sembol: str, yenile: bool = False) -> pd.DataFrame:
    """Kaynaktaki birincil 1d dosyalarini KUME KORUMASI OLMADAN indirir.

    B grubu ve C2 donemi dahil tum gecmisi dondurur. Yalnizca tum gecmisi olcmesi
    gereken F1 capraz dogrulamasi icindir (CLAUDE.md §3.1). Analiz ve olay kodu
    bunu CAGIRMAZ.
    """
    anahtarlar = bv.mum_dosyalari(sembol, config.BAR_1D)
    parcalar = []
    for anahtar in anahtarlar:
        ay = bv.dosya_ayi(anahtar)
        yol = bv.onbellek_yolu("klines_birincil_1d", sembol, f"{ay}.parquet")
        cerceve = None if yenile else bv.onbellekten_oku(yol)
        if cerceve is None:
            cerceve = _ay_cercevesi(bv.zip_indir(anahtar))
            bv.onbellege_yaz(cerceve, yol)
        parcalar.append(cerceve)
    if not parcalar:
        return pd.DataFrame(columns=[s for s in bv.MUM_SUTUNLARI if s != "ignore"])
    return _tekrarsiz_birlestir(parcalar, f"ham_birincil_gunluk_indir({sembol})")


# --- Butunluk olcumleri (denetim icin) ---------------------------------------


def eksik_barlar(cerceve: pd.DataFrame, bar: str) -> pd.DataFrame:
    """Beklenen bar izgarasina gore eksik barlari bulur.

    Yalnizca kapsama olcer; fiyat davranisina bakmaz (CLAUDE.md §3.1).
    """
    if cerceve.empty:
        return pd.DataFrame(columns=["bas", "son", "eksik_bar"])
    adim = pd.Timedelta(hours=4) if bar == config.BAR_4H else pd.Timedelta(days=1)
    izgara = pd.date_range(cerceve["open_time"].iloc[0], cerceve["open_time"].iloc[-1], freq=adim)
    eksik = izgara.difference(pd.DatetimeIndex(cerceve["open_time"]))
    if len(eksik) == 0:
        return pd.DataFrame(columns=["bas", "son", "eksik_bar"])

    # Ardisik eksikleri bosluk olarak grupla.
    seri = pd.Series(eksik)
    grup = (seri.diff() != adim).cumsum()
    bosluklar = seri.groupby(grup).agg(["first", "last", "size"])
    bosluklar.columns = ["bas", "son", "eksik_bar"]
    return bosluklar.reset_index(drop=True)


def butunluk_sicramalari(
    cerceve: pd.DataFrame, esik: float = config.BUTUNLUK_ACILIS_ESIGI
) -> pd.DataFrame:
    """`|open[t] / close[t-1] - 1| > esik` olan barlari listeler (on-kayit rev.2).

    Token yeniden fiyatlandirmasi fiyat serisinde yapay bir sicrama birakir; bu
    kontrol onlari denetim raporunda gorunur kilar. Yalnizca veri BUTUNLUGU
    olcumudur: getiri, volatilite veya olay hesaplamaz. Saf fonksiyon.
    """
    bos = pd.DataFrame(columns=["open_time", "onceki_close", "open", "bagil_fark"])
    if len(cerceve) < 2:
        return bos

    calisma = cerceve.sort_values("open_time")
    onceki_close = calisma["close"].shift(1)
    bagil = (calisma["open"] / onceki_close - 1.0).abs()
    secili = bagil > esik
    if not secili.any():
        return bos

    # .values kullanilmaz: zaman dilimi bilgisini dusurur.
    return pd.DataFrame(
        {
            "open_time": calisma.loc[secili, "open_time"],
            "onceki_close": onceki_close[secili],
            "open": calisma.loc[secili, "open"],
            "bagil_fark": bagil[secili],
        }
    ).reset_index(drop=True)
