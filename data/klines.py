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

import numpy as np
import pandas as pd

import config
from data import binance_vision as bv
from data import pencere as pencere_modulu

# Bir UTC gunu tam olmasi icin gereken 4h bar sayisi ve o gunun izgara adimi (00:00, 04:00, ...,
# 20:00 UTC). Ikisi de on-kayit sabitidir ve `config`ten TURETILIR (F1 kapatma turu madde 1a,
# bulgu S-C3: ayni sayilar burada ve `pencere`de ayri yaziliydi, ikisi de korumanin disindaydi).
GUNLUK_BAR_SAYISI = config.GUNLUK_BAR_SAYISI
GUNLUK_IZGARA_ADIMI = pencere_modulu.adim(config.BAR_4H)

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

    Aga cikmaz (on-kayit §3 rev.13): liste dondurulmus dosyadan okunur, eksik ay indirilmez
    (`bv.agsiz_okuma`). Istisna `yenile=True`: guncelleme aracidir ve aga cikar.
    """
    from data import split as split_modulu  # split bu modulu import eder; dongu onlenir

    def yukle() -> pd.DataFrame:
        return split_modulu.yukle(
            sembol,
            bar,
            kume,
            onay=onay,
            mum_yukleyici=lambda s, b: ham_mumlari_yukle(s, b, yenile=yenile),
        )

    if yenile:
        return yukle()
    with bv.agsiz_okuma():
        return yukle()


def ham_mumlari_yukle(sembol: str, bar: str = config.BAR_4H, yenile: bool = False) -> pd.DataFrame:
    """Bir sembolun TUM mumlari, KUME KORUMASI OLMADAN; yalnizca eksik aylari indirir.

    B grubu ve C2 donemi dahil tum gecmisi dondurur. Yalnizca veri katmani
    (`split.yukle`) ve tum gecmisi olcmesi gereken F1 kapsama denetimi icindir
    (CLAUDE.md §3.1). Analiz ve olay kodu bunu CAGIRMAZ.

    Onbellek ay basina tek parquet dosyasidir (`cache/klines/<sembol>/<bar>/<ay>.parquet`),
    bu sayede yeniden calistirma tamamlanmis aylari yeniden indirmez.
    """
    if bar == config.BAR_1D:
        # Tek 1d yolu (on-kayit §2 rev.8): sembolun commit edilmis listeleme
        # donemleriyle, yalnizca donem ici hizali 4h barlardan.
        from data import universe as universe_modulu

        donemler = universe_modulu.sembol_donemleri(universe_modulu.evren_yukle(), sembol)
        return gunluge_cevir(ham_mumlari_yukle(sembol, config.BAR_4H, yenile), donemler=donemler)

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

# Bir 4h barin "mevcut" sayilmasi icin sonlu bir sayi tasimasi gereken hucreler (on-kayit §2
# "1 gunluk barlar", rev.11: "fiyat ve hacim hucrelerinin tamami sayi olmalidir"). `count` islem
# sayisidir; fiyat ya da hacim hucresi olmadigi icin listede yoktur (gunluge_cevir docstring'i).
HUCRE_SUTUNLARI = ("open", "high", "low", "close", "volume", "quote_volume",
                   "taker_buy_volume", "taker_buy_quote_volume")


def hucreleri_tam_mi(mumlar: pd.DataFrame) -> np.ndarray:
    """Her barin fiyat ve hacim hucreleri sonlu bir sayi mi? (on-kayit §2 rev.11) Saf.

    Sayisal olmayan deger (metin, nesne) ve +-sonsuz da eksik sayilir; eksik hucre sifir
    sayilmaz. Cercevede bulunmayan bir `HUCRE_SUTUNLARI` sutunu denetlenmez (sentetik ve kismi
    cerceveler icin): var olan hucreler denetlenir.
    """
    tam = np.ones(len(mumlar), dtype=bool)
    for sutun in HUCRE_SUTUNLARI:
        if sutun not in mumlar:
            continue
        degerler = pd.to_numeric(mumlar[sutun], errors="coerce").to_numpy(dtype=float)
        tam &= np.isfinite(degerler)
    return tam


def gunluge_cevir(dort_saatlik: pd.DataFrame, *, donemler) -> pd.DataFrame:
    """4h barlardan UTC gunluk barlar turetir; TEK 1d turetme yolu (on-kayit §2 rev.8
    "1 gunluk barlar").

    "1d barlar yalnizca donem ici 4h barlardan turetilir ... Bir gun, yalnizca o
    gunun 00:00, 04:00, 08:00, 12:00, 16:00 ve 20:00 UTC acilisli alti 4h barinin
    tamami mevcut ve ayni donemin icindeyse olusur; aksi halde o gun eksik (NaN)
    sayilir." Seri donem donem kurulur: her 4h bar yalnizca iceren donemin
    (`pencere.donem_ici_4h_maskesi`) gunune sayilir; izgara disindaki (hizasiz)
    bar hicbir gune girmez. Donemin kismi ilk ve son gunleri seride yoktur.

    **Eksik hucre (rev.11).** "Bir barin mevcut sayilmasi icin satirinin bulunmasi yetmez
    (rev.11): fiyat ve hacim hucrelerinin tamami sayi olmalidir. Hucrelerinden biri NaN ya da
    sonlu degilse o bar eksiktir ve gununu dusurur; eksik hucre sifir sayilmaz." Denetlenen
    hucreler `HUCRE_SUTUNLARI`dir: fiyat (open, high, low, close) ve hacim (volume,
    quote_volume, taker_buy_volume, taker_buy_quote_volume). Boyle bir bar, gunun alti barindan
    biri olarak SAYILMAZ; gun alti tam bara ulasmadigi icin dusup NaN olur ve eksik hucre
    toplamlara 0 gibi girmez. Rev.11'den once yalnizca bar SAYISI sayiliyordu: hacmi NaN olan
    bar mevcut sayiliyor, gun "tam" kabul ediliyor ve toplam `sum(skipna=True)` ile sessizce
    eksik hesaplaniyordu (denetci bulgusu #13, A6 xfail'i).

    `count` sutunu islem SAYISIDIR, fiyat ya da hacim hucresi degildir; on-kayit cumlesi onu
    kapsamadigi icin denetime girmez. Eksik bir `count` hucresi gunun `count` toplamini sessizce
    eksiltir; bu bir acik noktadir ve hicbir olay, uygunluk ya da getiri hesabina girmez.

    `donemler` zorunludur (varsayilan yok): sembolun listeleme donemleri
    (`universe.sembol_donemleri`). Bos liste bos seri verir. Saf fonksiyon.
    """
    from data import pencere as pencere_modulu

    if not isinstance(donemler, (list, tuple)):
        raise TypeError(f"donemler bir Donem listesi olmali: {type(donemler).__name__}")
    sutunlar = [s for s in bv.MUM_SUTUNLARI if s != "ignore"]
    if dort_saatlik.empty or not donemler:
        return pd.DataFrame(columns=sutunlar)

    calisma = dort_saatlik.sort_values("open_time").reset_index(drop=True)
    zamanlar = pd.DatetimeIndex(calisma["open_time"])
    gun = zamanlar.floor("D")
    ofset = zamanlar - gun
    # Izgara hizasi acikca: acilis gun basindan tam 0, 4, ..., 20 saat sonra.
    hizali = np.asarray((ofset % GUNLUK_IZGARA_ADIMI) == pd.Timedelta(0), dtype=bool)
    # Eksik hucre (on-kayit §2 rev.11): fiyat ve hacim hucrelerinin tamami sonlu bir sayi olmali.
    hucreler_tam = hucreleri_tam_mi(calisma)

    donem_no = np.full(len(calisma), -1)
    for i, donem in enumerate(donemler):
        ici = np.asarray(pencere_modulu.donem_ici_4h_maskesi(
            zamanlar, donem_baslangic=donem.baslangic, donem_bitis=donem.bitis), dtype=bool)
        donem_no[ici] = i
    calisma["gun"] = gun
    calisma["_donem"] = donem_no
    calisma["_ofset"] = ofset
    calisma = calisma.loc[(donem_no >= 0) & hizali & hucreler_tam]
    if calisma.empty:
        return pd.DataFrame(columns=sutunlar)

    toplanan = calisma.groupby(["_donem", "gun"], sort=True).agg(
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
        farkli_acilis=("_ofset", "nunique"),
    )
    tam = toplanan.loc[(toplanan["bar_sayisi"] == GUNLUK_BAR_SAYISI)
                       & (toplanan["farkli_acilis"] == GUNLUK_BAR_SAYISI)]
    tam = tam.reset_index().drop(columns=["_donem", "bar_sayisi", "farkli_acilis"])
    tam = tam.rename(columns={"gun": "open_time"}).sort_values("open_time", ignore_index=True)
    return tam[sutunlar]


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
    # Kapidan gecildi; ham okuma onay verisi izniyle, ardindan kume araligina kesilir.
    with bv.onay_verisi_izni(f"klines.birincil_gunluk_indir({sembol}, {kume})"):
        ham = ham_birincil_gunluk_indir(sembol, yenile=yenile)
    return donem_kes(ham, bas, son)


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


# --- SETTLED dizinleri (yalnizca denetim, on-kayit §2 rev.7) ------------------


def settled_dizinleri(sembol: str, sembol_dizinleri: list[str]) -> list[str]:
    """Bucket'ta bir sembole ait `<SEMBOL>SETTLED...` / `<SEMBOL>_SETTLED` dizinleri. Saf.

    Esleme `universe.settled_aylari_haritasi` ile aynidir: SETTLED son ekleri ve
    ardindaki alt cizgi atildiginda kalan ad sembole esit olmalidir.
    """
    sonuc = []
    for dizin in sembol_dizinleri:
        if not dizin.endswith(config.SETTLED_SONEKI):
            continue
        temel = dizin
        while temel.endswith(config.SETTLED_SONEKI):
            temel = temel[: -len(config.SETTLED_SONEKI)]
        if temel.rstrip("_") == sembol:
            sonuc.append(dizin)
    return sorted(sonuc)


def ham_settled_mumlari_yukle(dizin: str, bar: str = config.BAR_4H, yenile: bool = False) -> pd.DataFrame:
    """Bir SETTLED dizininin tum mumlari, KUME KORUMASI OLMADAN (ag kullanir).

    Yalnizca F1 denetiminin SETTLED icerik karsilastirmasi icindir; SETTLED
    bilgisi hicbir kurala girmez (on-kayit §2 rev.7). Analiz ve olay kodu bunu
    CAGIRMAZ. Onbellek: `cache/klines_settled/<dizin>/<bar>/<ay>.parquet`.
    """
    parcalar = []
    for anahtar in bv.mum_dosyalari(dizin, bar):
        yol = bv.onbellek_yolu("klines_settled", dizin, bar, f"{bv.dosya_ayi(anahtar)}.parquet")
        cerceve = None if yenile else bv.onbellekten_oku(yol)
        if cerceve is None:
            cerceve = _ay_cercevesi(bv.zip_indir(anahtar))
            bv.onbellege_yaz(cerceve, yol)
        parcalar.append(cerceve)
    if not parcalar:
        return pd.DataFrame(columns=[s for s in bv.MUM_SUTUNLARI if s != "ignore"])
    return _tekrarsiz_birlestir(parcalar, f"ham_settled_mumlari_yukle({dizin}, {bar})")


def _bagil_fark(a: pd.Series, b: pd.Series) -> pd.Series:
    """|a - b| / max(|a|, |b|); ikisi de sifirsa 0."""
    payda = pd.concat([a.abs(), b.abs()], axis=1).max(axis=1)
    return ((a - b).abs() / payda.where(payda != 0)).fillna(0.0)


def settled_ay_karsilastir(ana: pd.DataFrame, settled: pd.DataFrame, ay: str,
                           tolerans: float = config.DENETIM_CAPRAZ_TOLERANS) -> dict:
    """Bir takvim ayinda SETTLED mumlarini ana seriyle bar bar karsilastirir. Saf.

    Yalnizca veri butunlugu olcumudur: iki kaynakta ayni zaman damgali barlarin
    OHLC ve hacim alanlari ayni mi? Getiri veya fiyat davranisi hesaplamaz.
    """
    p = pd.Period(ay, freq="M")
    bas, son = p.start_time.tz_localize("UTC"), p.end_time.tz_localize("UTC")

    def kes(c):
        return c.loc[(c["open_time"] >= bas) & (c["open_time"] <= son)] if not c.empty else c

    a, s = kes(ana), kes(settled)
    ortak = a.merge(s, on="open_time", suffixes=("_ana", "_set"))
    fiyat = pd.concat([_bagil_fark(ortak[f"{c}_ana"], ortak[f"{c}_set"]) for c in ("open", "high", "low", "close")],
                      axis=1).max(axis=1) if len(ortak) else pd.Series(dtype=float)
    hacim = pd.concat([_bagil_fark(ortak[f"{c}_ana"], ortak[f"{c}_set"]) for c in ("volume", "quote_volume")],
                      axis=1).max(axis=1) if len(ortak) else pd.Series(dtype=float)
    return {
        "ay": ay,
        "ana_bar": len(a),
        "settled_bar": len(s),
        "ortak_bar": len(ortak),
        "yalniz_ana": int((~a["open_time"].isin(s["open_time"])).sum()) if len(a) else 0,
        "yalniz_settled": int((~s["open_time"].isin(a["open_time"])).sum()) if len(s) else 0,
        "fiyat_farkli_bar": int((fiyat > tolerans).sum()),
        "hacim_farkli_bar": int((hacim > tolerans).sum()),
        "azami_fiyat_bagil_fark": float(fiyat.max()) if len(fiyat) else float("nan"),
        "azami_hacim_bagil_fark": float(hacim.max()) if len(hacim) else float("nan"),
    }
