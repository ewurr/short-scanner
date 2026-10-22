"""short-lab sabitleri.

Buradaki degerler PREREGISTRATION.md'den gelir ve yanina geldigi bolum yazilir.
Bu dosyadaki bir on-kayit sabitini degistirmek on-kaydi degistirmek demektir; once
revizyon yazilmadan burasi degistirilemez (CLAUDE.md §3.4).

Yorumlardaki `rev.N` atiflari kuralin BUGUNKU halini degil, onu getiren revizyonu adlandirir;
yetkili metin her zaman on-kaydin yururlukteki surumudur (bulgu S-C9).

Istisnalar "ON-KAYIT DEGILDIR" diye isaretlidir: dizin ve dosya yollari (ornegin
`EXCHANGE_INFO_ANLIK`) ve F1 denetim teshis esikleri (`DENETIM_*`). Bunlar hicbir
olay, uygunluk ya da getiri hesabinin esigi degildir.
"""

from __future__ import annotations

import datetime as dt
import types as _types
from pathlib import Path

# --- Dizinler (CLAUDE.md §7) -------------------------------------------------
#
# ON-KAYIT DEGILDIR: dosya ve dizin yollari.

KOK = Path(__file__).resolve().parent
VERI_DIZINI = KOK / "data"
ONBELLEK_DIZINI = KOK / "cache"
ANALIZ_DIZINI = KOK / "analysis"
SPLIT_CSV = VERI_DIZINI / "split.csv"
# Listeleme donemleri; split.csv gibi sabit (on-kayit §2 rev.4, rev.7).
UNIVERSE_CSV = VERI_DIZINI / "universe.csv"
ONAY_KAYDI = KOK / "ONAY_KAYDI.md"
# Onay kaydinin itildigi uzak depo (onay kaydi kapanisinin son turu). ON-KAYIT DEGILDIR: on-kayitta uzak depo
# tanimli degil; bu deger tek atis kaydinin butunlugu icindir. `split.onay_kosusu`, `origin`in okuma ve itme
# adreslerinin bu depo oldugunu denetler (https ya da ssh bicimi; `.git` soneki ve buyuk/kucuk harf fark etmez).
# Calisma aninda degistirilemez (`_DEGISMEZ_ADLAR`).
UZAK_DEPO_ADRESI = "github.com/ewurr/short-scanner"
# exchangeInfo anlik goruntusu. ON-KAYIT DEGILDIR (on-kayitta tanimli degil;
# 2026-09-18'de F1 denetimi icin alindi). Delist siniflandirmasi, deliveryDate
# denetimi ve evren kurulumundaki sozlesme/dayanak tipi canli uc noktadan degil bu
# dosyadan okunur.
EXCHANGE_INFO_ANLIK = VERI_DIZINI / "exchange_info_anlik.json"

# --- Piyasa ve evren (on-kayit §2) -------------------------------------------

# Binance USDⓈ-M, USDT marjinli, PERPETUAL sozlesmeler.
TEMINAT_SONEKI = "USDT"

# Toplam donem: 2020-01-01 00:00 UTC -> 2026-08-31 23:59 UTC (on-kayit §2)
DONEM_BASI = dt.datetime(2020, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
DONEM_SONU = dt.datetime(2026, 8, 31, 23, 59, 59, tzinfo=dt.timezone.utc)

# Bar tipleri: H1, H2 -> 4h · H3 -> 1d (on-kayit §2)
BAR_4H = "4h"
BAR_1D = "1d"

# Izgara adimlari, saat (on-kayit §2 "Bar tipleri" ve "1 gunluk barlar"). `pencere.ADIMLAR` tek
# `pd.Timedelta` tanimini buradan kurar; baska bir modul kendi adimini yazmaz (bulgu S-C3).
IZGARA_ADIMI_SAAT = _types.MappingProxyType({BAR_4H: 4, BAR_1D: 24})

# On-kayit §2 "1 gunluk barlar": "Bir gun, yalnizca o gunun 00:00, 04:00, 08:00, 12:00, 16:00 ve
# 20:00 UTC acilisli ALTI 4h barinin tamami mevcut ve ayni donemin icindeyse olusur." Gunun son
# 4h bari bu sayidan turer ((6-1) x 4 saat = 20:00); `klines` ve `pencere` ikisi de buradan okur
# (bulgu S-C3: sayi iki modulde ayri yaziliydi).
GUNLUK_BAR_SAYISI = 6

# --- Zaman toleransi (on-kayit §4 rev.8 "Zaman toleransi") -------------------
#
# "Projedeki butun zaman karsilastirmalarinda iki an arasindaki fark 1 dakikadan kesin olarak
# kucukse bu iki an ayni sayilir; tam 1 dakikalik fark ayni an degildir." Tek tanim burasidir;
# `pencere` butun zaman iliskilerini bu degerden kurar (bulgu S-C2: deger on-kayit sabiti oldugu
# halde `pencere.py`de, degismezlik korumasinin disinda yaziliydi).
ZAMAN_TOLERANSI = dt.timedelta(minutes=1)

# Kapsam netlestirmesi (on-kayit §2 "Kapsam", rev.2): evren yalnizca
# contractType = PERPETUAL olan USDT marjinli sozlesmelerden olusur.
# TRADIFI_PERPETUAL (hisse senedi, emtia, premarket) kapsam disidir.
PERPETUAL_TIPI = "PERPETUAL"
TRADIFI_TIPI = "TRADIFI_PERPETUAL"
ENDEKS_TIPI = "INDEX"

# Haric tutma listesi (on-kayit §2 "Haric tutma", rev.2). Kesin ve aciktir; duzenli ifade
# kullanilmaz, cunku BUSDT (BU) ve TUSDT (Threshold) stablecoin degildir.
HARIC_ENDEKSLER: frozenset[str] = frozenset(
    {"BTCDOMUSDT", "DEFIUSDT", "ALLUSDT", "BLUEBIRDUSDT", "DOTECOUSDT", "FOOTBALLUSDT"}
)
HARIC_STABLECOIN: frozenset[str] = frozenset({"USDCUSDT"})
HARIC_SEMBOLLER: frozenset[str] = HARIC_ENDEKSLER | HARIC_STABLECOIN

# On-kayit §2 (rev.2) stablecoin tanimi "bagini koruyan token" oldugu icin
# asagidakiler evrende KALIR. Liste yalnizca belge amaclidir.
EVRENDE_KALAN_STABLECOIN_BENZERI: frozenset[str] = frozenset(
    {"FRAXUSDT", "USTCUSDT", "STBLUSDT", "STABLEUSDT"}
)

# Kabul edilen yeniden adlandirma zincirleri (on-kayit §3 "Veri bolmesi", rev.2).
# {yeni_sembol: eski_sembol}; varlik anahtari zincirin en eski uyesidir.
# KEEPUSDT/NUUSDT -> TUSDT birlesme oldugu icin zincir SAYILMAZ.
# Dondurulmustur (F1 kapatma turu madde 1a): zincir bolmeyi belirler, yerinde bir yazim
# `varlik_anahtari`ni ve dolayisiyla A/B grubunu sessizce kaydirirdi.
YENIDEN_ADLANDIRMA = _types.MappingProxyType({
    "AAVEUSDT": "LENDUSDT",
    "1000BTTCUSDT": "BTTUSDT",
    "RENDERUSDT": "RNDRUSDT",
    "GUSDT": "GALUSDT",
    "POLUSDT": "MATICUSDT",
    "AUSDT": "EOSUSDT",
    "1000LUNCUSDT": "LUNAUSDT",
    "VICUSDT": "TOMOUSDT",
    "DODOXUSDT": "DODOUSDT",
})

# --- Listeleme donemi (on-kayit §2 "Listeleme donemi"; yurutlukteki metin rev.7) --------

# On-kayit §2 rev.7 "Listeleme donemi": bu kadar ya da daha fazla ardisik sifir
# hacimli bar (bir gun) dolgu kosusudur ve donemi boler.
DOLGU_KOSU_ESIGI_BAR = 6

# On-kayit §2 rev.7: bu sureden UZUN eksik bar boslugu donemi boler. Bosluk,
# ardisik iki mevcut bar arasindaki EKSIK sure olarak olculur
# (sonraki acilis - onceki acilis - bar adimi). Kisa bosluklar borsa kesintisidir.
AZAMI_EKSIK_BAR_BOSLUGU = dt.timedelta(days=7)

# Bucket'ta <SEMBOL>SETTLED dizini. On-kayit §2 rev.7: yalnizca denetim bilgisidir,
# hicbir kurala girmez (karantina kurali kaldirildi).
SETTLED_SONEKI = "SETTLED"

# --- Veri butunlugu kontrolu (on-kayit §2 "Veri butunlugu kontrolu", rev.2) --------------

# |open[t] / close[t-1] - 1| bu esigi asan barlar denetim raporunda listelenir.
BUTUNLUK_ACILIS_ESIGI = 0.30

# --- F1 denetim teshis esikleri ----------------------------------------------
#
# ON-KAYIT DEGILDIR. Yalnizca F1 kapsama ve butunluk raporunun sunumunu belirler;
# hicbir olay, uygunluk ya da getiri hesabina girmez. Degerler F1 gorevindeki
# kullanici talimatlarindan gelir. Denetci bulgusu B8: analysis betigine
# gomuluydu.

# "3 bardan uzun bosluklar" listesi
DENETIM_UZUN_BOSLUK_BAR = 3

# 1d turetmesi ile birincil 1d dosyalari arasinda "fark var" sayilan bagil esik
DENETIM_CAPRAZ_TOLERANS = 1e-6

# Bosluk olayi, o aralikta verisi olan sembollerin en az bu oranini etkiliyorsa
# "borsa geneli" sayilir
DENETIM_BORSA_GENELI_ORANI = 0.5

# Raporda listelenen kisa listeleme donemi esigi (gun)
DENETIM_KISA_DONEM_GUN = 60

# A1 olcumunde (D kurali, funding tamligi) temsili pozisyonun cikis barinin
# acilisindan ne kadar once girdigi (denetci bulgusu D-C5: betige gomuluydu).
# En uzun odeme araligindan (8 saat) uzundur; boylece son odemeler zincirin
# icinde kalir. Iki izgarada da aynidir (4 saatlikte 6 bar, 1 gunlukte 1 bar).
DENETIM_TEMSILI_GIRIS_SURE = dt.timedelta(hours=24)

# RESULTS §4: uzlasma sonrasi ilk funding kaydinin "en gec 8 saat sonra" basladigi
# sembol sayimi. Rev.7 metnindeki ifadeden gelir; esik ayni an ya da once
# (on-kayit §4 rev.8 "Zaman toleransi"). Betige gomuluydu (8 + 1/60).
DENETIM_ILK_GECIKME_SAAT = 8

# --- Hipotez izgarasi ve ufuklar (on-kayit §2, §4) ---------------------------
#
# On-kayit §4 "Ufuk degerlerinin baglanmasi" (rev.10): "Birincil ufuk, ikincil ufuklar ve
# ileri kayma siniri yalnizca bu on-kayitta tanimlidir ... Kod bu degerleri tek bir yerden,
# on-kayit degeri olarak okur; getiri, olay ya da kontrol ureten hicbir cagri serbest bir ufuk
# degeri kabul etmez." Tek yer burasidir; `data.pencere` (`ufuk_dogrula`, `birincil_ufuk_dogrula`)
# ve olcum betikleri buradan okur. Degerler izgara adimi cinsinden (4h: bar, 1d: gun).

# Hipotezlerin izgarasi (on-kayit §2 "Bar tipleri"; §4-§5: H1, H2 4 saatlik; H3 1 gunluk).
HIPOTEZ_IZGARASI = _types.MappingProxyType({"H1": BAR_4H, "H2": BAR_4H, "H3": BAR_1D})
# Hipotez adlari (on-kayit §5: H1, H2, H3). Onay kosusu ve karar noktasi yalnizca bu sabitleri kabul eder;
# "h2", "H2_b" gibi varyasyonlar reddedilir (kapi sertlestirme turu 3, denetci KS2 D-B1).
HIPOTEZLER = tuple(HIPOTEZ_IZGARASI)

# Birincil ufuk (on-kayit §4 tablo): H1, H2 18 bar (3 gun); H3 14 gun. Onay kararlari buna gore.
BIRINCIL_UFUK = _types.MappingProxyType({BAR_4H: 18, BAR_1D: 14})

# Ikincil ufuklar, yalnizca rapor (on-kayit §4 tablo): H1, H2 6 ve 42 bar; H3 7 ve 30 gun.
IKINCIL_UFUKLAR = _types.MappingProxyType({BAR_4H: (6, 42), BAR_1D: (7, 30)})

# Ileri kaymanin ust siniri (on-kayit §4 rev.6 "Ileri kaymanin ust siniri"; rev.10): H1, H2 18 bar,
# H3 14 gun. Degerce birincil ufka esittir ama on-kayitta ayri bir kural olarak yazilidir.
ILERI_KAYMA_SINIRI = _types.MappingProxyType({BAR_4H: 18, BAR_1D: 14})

# Izgara basina butun gecerli ufuklar (birincil + ikincil), artan sirada.
UFUKLAR = _types.MappingProxyType(
    {bar: tuple(sorted((BIRINCIL_UFUK[bar], *IKINCIL_UFUKLAR[bar]))) for bar in BIRINCIL_UFUK})

# H2'nin funding ortalamasi penceresi, saat (on-kayit §5 H2 madde 1: "t anina kadarki son 24 saatteki
# funding oranlarinin ortalamasi"; §4 "Funding sinyal penceresinin tamligi": "24 saat geriye uzanir").
# `funding.sinyal_penceresi_ayrintisi` ve `funding_ortalamasi` baska deger kabul etmez (denetci D-B3).
H2_FUNDING_PENCERESI_SAAT = 24

# --- Izgara parametreleri ve pencere sinirlari (on-kayit §5) -----------------
#
# On-kayit §5 (rev.11): "Izgara parametreleri (θ, δ, φ, k, ν, τ) yalnizca bu on-kayitta
# tanimlidir ve kod bu degerleri tek bir yerden, on-kayit degeri olarak okur. Olay ya da kontrol
# ureten her cagri, hipotezi ve yapilandirmayi birlikte alir; izgarada bulunmayan bir parametre
# demeti hata verir." Tek yer burasidir; `data.sinyal` butun pencere kurucularini, izgarayi ve
# kosul esiklerini buradan okur. Denetci bulgusu F1K2 D-C4 ("§5-§9 sabitleri config.py'de yok")
# bu bolumle kapanir.

# Izgaralar (on-kayit §5 H1, H2, H3 "Izgara" satirlari). Her hipotez icin 9 yapilandirma
# (3 x 3). φ oran olarak yazilidir: %0.03 = 0.0003 (funding oranlari da oran cinsindendir).
IZGARA = _types.MappingProxyType({
    "H1": _types.MappingProxyType({"theta": (0.20, 0.30, 0.40), "delta": (0.08, 0.12, 0.16)}),
    "H2": _types.MappingProxyType({"phi": (0.0003, 0.0005, 0.0010), "k": (3, 6, 12)}),
    "H3": _types.MappingProxyType({"nu": (0.50, 0.65, 0.80), "tau": (0.15, 0.25, 0.35)}),
})

# H1 (on-kayit §5 H1 madde 1-3 ve §5 "Pencere sinirlari"):
#   - dip penceresi `min(low[t-6..t-1])`: 6 bar, t HARIC
#   - "son 6 barin toplam hacmi": 6 bar, t DAHIL
#   - "onceki 180 barin 6'li toplam hacim medyani": 180 dis bar, t DAHIL (kayan 6'li toplamlar)
#   - hacim esigi: 6'li toplam >= 3 x medyan
#   - izleme: pump barindan sonraki en fazla 12 bar (madde 3, madde 4 "12 barlik sayac")
H1_DIP_BAR = 6
H1_HACIM_TOPLAM_BAR = 6
H1_HACIM_MEDYAN_BAR = 180
H1_HACIM_CARPANI = 3.0
H1_IZLEME_BAR = 12

# `close[t-30]` iki uclu orani (on-kayit §5 rev.11): t'den 30 ADIM onceki barin kapanisi; tamlik
# penceresi `[t-30 .. t]`, yani 31 bardir. H2'nin yukselis penceresi ile H3'un dusus trendi
# orani ayni sayiyi kullanir.
OTUZ_BAR_ONCE = 30

# H2 madde 2: "`close[t] / close[t-30] - 1 >= 0.10`".
H2_YUKSELIS_ESIGI = 0.10

# H3 (on-kayit §5 H3 madde 1-2 ve §5 rev.11 "Pencere sinirlarinin tamami"):
#   - "son 30 gun" t gununu DAHIL eder (`[t-29 .. t]`)
#   - "gun -120 ile -31 arasi" (`[t-120 .. t-31]`, 90 gun; bitis ofseti 31)
#   - SMA50 t gununu DAHIL eder (`[t-49 .. t]`)
# Iki hacim penceresi arasindaki t-30 gunu hicbir pencereye girmez; bu, yazili sayilarin
# dogrudan sonucudur ve bilerek korunmustur (on-kayit §5 rev.11).
H3_HACIM_YAKIN_GUN = 30
H3_HACIM_UZAK_GUN = 90
H3_HACIM_UZAK_OFSET = 31
H3_SMA_GUN = 50

# Gecersizlik (stop) seviyesinin carpani (on-kayit §5 H1 madde 5, H2 madde 4, H3 madde 4 rev.13):
# H1'de `tepe x 1.02`, H2 ve H3'te `max(high[t-30..t]) x 1.02`. Yalnizca F4 icin KAYITTIR; F2 ve
# F3'te hicbir karara girmez (CLAUDE.md §2 madde 5: "Taktik asamasinda her short pozisyonun
# onceden tanimli bir gecersizlik (stop) seviyesi olmalidir").
GECERSIZLIK_CARPANI = 1.02

# --- Kontroller (on-kayit §6) ------------------------------------------------

# K1 ve K2 havuzlarinin hedef buyuklugu: "10 rastgele bar", "10 rastgele coin". Aday sayisi
# bundan azsa adaylarin tamami alinir ve sayi sonuc dosyasina yazilir (§6 rev.11).
KONTROL_SAYISI = 10

# Olay sayisi esikleri (on-kayit §8 madde 2 ve §9 madde 6). Ikisi de ANALIZE GIREN olaylarin
# sayisina bakar (rev.13 madde (h)): "Buradaki ve §9'daki olay sayisi, analize giren olaylarin
# sayisidir: her iki kontrol havuzu da bos oldugu icin analize girmeyen olaylar (§6) sayilmaz.
# Gerekce: esikler istatistik gucunu guvenceye almak icin vardir ve guc yalnizca teste giren
# olaylardan gelir; olusmus ama analize girmeyen olayi saymak gucu oldugundan fazla gosterirdi."
# Esiklerin KARARA baglanmasi F2 (aday secimi) ve F3 (yeterli guc hukmu) isidir; veri katmani
# yalnizca yuklemi ve iki sayiyi uretir (`ornekleme.olay_sayilari`).
ADAY_OLAY_ESIGI = 150      # §8 madde 2: aday yapilandirma icin asgari analize giren olay sayisi
ONAY_OLAY_ESIGI = 100      # §9 madde 6: altinda hukum YETERSIZ GUC

# --- Uygunluk (on-kayit §2) --------------------------------------------------

# Listeleme yasi >= 30 gun
ASGARI_LISTELEME_YASI_GUN = 30

# Medyan gunluk hacim penceresi: son 30 gun
HACIM_PENCERESI_GUN = 30

# H1, H2: medyan gunluk hacim >= 10 milyon USDT
ASGARI_HACIM_4H = 10_000_000.0

# H3: medyan gunluk hacim >= 2 milyon USDT
ASGARI_HACIM_1D = 2_000_000.0

# --- Veri bolmesi (on-kayit §3) ----------------------------------------------

# SHA256("short-lab-v1:" + VARLIK ANAHTARI); ozetin tamsayi degeri cift ise A, tek ise B.
# Varlik anahtari, yeniden adlandirma zincirinin EN ESKI uyesidir (on-kayit §3 rev.2):
# `split.varlik_anahtari` once zinciri cozer, sonra ozeti alir. Yorum rev.2'den beri "SEMBOL"
# diyordu (bulgu S-C6); kod bastan beri varlik anahtarini kullaniyor.
BOLME_TUZU = "short-lab-v1:"

KESIF_BASI = dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc)
KESIF_SONU = dt.datetime(2025, 8, 31, 23, 59, 59, tzinfo=dt.timezone.utc)
C2_BASI = dt.datetime(2025, 9, 1, tzinfo=dt.timezone.utc)
C2_SONU = dt.datetime(2026, 8, 31, 23, 59, 59, tzinfo=dt.timezone.utc)

# KESIF: A grubu, kesif donemi · C1: B grubu, kesif donemi · C2: A+B, C2 donemi
KUMELER = ("KESIF", "C1", "C2")
ONAY_KUMELERI = ("C1", "C2")

# --- Funding (on-kayit §2) ---------------------------------------------------

# Karsilastirma icin oranlar 8 saate normallestirilir; getiri hesabinda gercek
# odemeler kullanilir.
NORMAL_FUNDING_ARALIGI_SAAT = 8

# --- Maliyet (on-kayit §4, CLAUDE.md §3.7) -----------------------------------

TEK_YON_MALIYET = 0.0010  # %0.10 ucret + kayma
GIDIS_DONUS_MALIYET = 0.0020  # %0.20

# --- Istatistik (on-kayit §7) ------------------------------------------------

TOHUM = 20260911
PERMUTASYON_TEKRAR = 10_000
# Uc hipotez icin Bonferroni duzeltmesi. On-kayit §7 esigi `0.05/3 = 0.0167` diye, §9 hukmu
# `p < 0.0167` diye yazar; kod BOLMEYI tasir (0.0166667) ve F3 karsilastirmasi bu degerden
# okunacaktir (bulgu S-C1). Iki yazim arasinda ulasilabilir p-degeri YOKTUR: p her zaman
# (r+1)/10001 bicimindedir ve (0.0166667, 0.0167] araligi icin r+1 tamsayisi yoktur
# (166.68 < r+1 <= 166.97). Yani yuvarlama hicbir hukmu degistiremez; esigin KARARA baglanmasi
# F3 isidir (RESULTS §14.31 madde 12).
ALFA_BONFERRONI = 0.05 / 3

# --- Calisma aninda degistirilemeyen adlar ------------------------------------
#
# ON-KAYIT DEGILDIR. Onay kaydi ve kosu butunlugu turu (denetci KS3 D-B1): onay kaydinin yolu calisma aninda
# yeniden atanamaz (`config.ONAY_KAYDI = ...`, `monkeypatch.setattr(config, "ONAY_KAYDI", ...)`). Testler kayit
# yolunu yalnizca `data.split._test_kaydi_ayarla` ile, kendi testleri suresince degistirir.
#
# SINIRLAR (bilincli, koruma turu madde 5; RESULTS §14.33'te acik nokta olarak yazili):
#   1. Modul sozlugune dogrudan yazim (`vars(config)[ad] = ...`) ENGELLENMEZ. Artik etkisi de
#      yoktur: degismez adlar veri tanimlayicisina baglandigi icin `config.<ad>` okumalari
#      sozluge bakmaz. Sozluk uzerinden OKUYAN kod analiz katmaninda taramayla yasaktir.
#   2. `object.__setattr__(config, "__class__", types.ModuleType)` ile modulun SINIFI
#      degistirilebilir; o anda tanimlayicilar da gider ve sozlukteki kopyalar gorunur. Bu
#      kararli bir atlatmadir (CLAUDE.md "Koruma katmani": kilit dikkatsiz bir degisiklige
#      karsidir). `config.__class__ = ...` ve `type(config).__setattr__ = ...` yollari kapalidir.

import sys as _sys  # noqa: E402


class SabitDegistirilemez(AttributeError):
    """Calisma aninda degistirilemeyen bir config adi yeniden atanmak ya da silinmek istendi."""


# Onay kaydi ikinci tur (denetci OK D-B2): kume sabitleri ve modul sinifi da. `config.ONAY_KUMELERI = ()` C1'i
# onaysiz acardi; kume tarihlerinin "duyarlilik icin" degistirilmesi kazayla da olabilirdi.
#
# F1 KAPATMA TURU MADDE 1a (bulgu 25). Kapsam artik "on-kayit kaynakli her sabit"tir: eskiden
# yalnizca §5, §7 ve kume sabitleri korunuyordu, bu yuzden maliyet (§4), uygunluk esikleri (§2),
# donem sinirlari (§2), bolme tuzu (§3), funding penceresi (§5) ve hipotez izgarasi (§2) calisma
# aninda yeniden atanabiliyordu; bir atama butun alt tohumlari, uygunluk suzgecini ve hukumleri
# sessizce kaydirirdi. Kapsamin TAM oldugu `tests/test_f1_config_kapsami.py` ile denetlenir: test
# adlari elle saymaz, `config.py`nin kaynagindan turetir ve her acik sabitin ya burada ya da
# `_ON_KAYIT_DISI`nda oldugunu arar. Sozluk sabitleri ayrica `MappingProxyType` ile dondurulmustur
# (ad korumasi yerinde yazimi engellemez).
_DEGISMEZ_ADLAR = frozenset({
    "ONAY_KAYDI", "_DEGISMEZ_ADLAR", "UZAK_DEPO_ADRESI",
    "KESIF_BASI", "KESIF_SONU", "C2_BASI", "C2_SONU", "KUMELER", "ONAY_KUMELERI",
    # On-kayit §2: piyasa, evren, bar tipleri, 1d turetmesi, listeleme donemi, veri butunlugu.
    "TEMINAT_SONEKI", "DONEM_BASI", "DONEM_SONU", "BAR_4H", "BAR_1D", "IZGARA_ADIMI_SAAT",
    "GUNLUK_BAR_SAYISI", "PERPETUAL_TIPI", "TRADIFI_TIPI", "ENDEKS_TIPI", "HARIC_ENDEKSLER",
    "HARIC_STABLECOIN", "HARIC_SEMBOLLER", "EVRENDE_KALAN_STABLECOIN_BENZERI", "YENIDEN_ADLANDIRMA",
    "DOLGU_KOSU_ESIGI_BAR", "AZAMI_EKSIK_BAR_BOSLUGU", "SETTLED_SONEKI", "BUTUNLUK_ACILIS_ESIGI",
    # On-kayit §2 uygunluk esikleri ve §3 bolme tuzu.
    "ASGARI_LISTELEME_YASI_GUN", "HACIM_PENCERESI_GUN", "ASGARI_HACIM_4H", "ASGARI_HACIM_1D",
    "BOLME_TUZU",
    # On-kayit §2, §4: hipotez izgarasi, ufuklar, ileri kayma siniri, funding penceresi, zaman
    # toleransi, maliyet.
    "HIPOTEZ_IZGARASI", "HIPOTEZLER", "BIRINCIL_UFUK", "IKINCIL_UFUKLAR", "ILERI_KAYMA_SINIRI",
    "UFUKLAR", "H2_FUNDING_PENCERESI_SAAT", "ZAMAN_TOLERANSI", "NORMAL_FUNDING_ARALIGI_SAAT",
    "TEK_YON_MALIYET", "GIDIS_DONUS_MALIYET",
    # Rev.11 madde 2: izgara parametreleri ve pencere sinirlari. θ, δ, φ, k, ν, τ ya da bir
    # pencere uzunlugunu calisma aninda degistirmek on-kaydi degistirmektir (on-kayit §5 rev.11).
    "IZGARA", "H1_DIP_BAR", "H1_HACIM_TOPLAM_BAR", "H1_HACIM_MEDYAN_BAR", "H1_HACIM_CARPANI",
    "H1_IZLEME_BAR", "OTUZ_BAR_ONCE", "H2_YUKSELIS_ESIGI", "H3_HACIM_YAKIN_GUN",
    "H3_HACIM_UZAK_GUN", "H3_HACIM_UZAK_OFSET", "H3_SMA_GUN",
    "GECERSIZLIK_CARPANI", "KONTROL_SAYISI", "ADAY_OLAY_ESIGI", "ONAY_OLAY_ESIGI",
    # Denetci bulgusu D-B4: §7'deki tohum ve tekrar sayisi. Tohum rev.13'ten beri IKI turetme
    # yolunun girdisidir (`ornekleme.alt_tohum` ile olay basina ornekleme ve `istatistik.alt_tohum`
    # ile p-degeri); calisma aninda degistirilirse butun alt tohumlar sessizce kayar ve sonuc
    # dosyasina yazilan `genel_tohum` da kaydigi icin fark raporda GORUNMEZ. `yeniden_ornekle`nin
    # `tekrar` denetimi de `config.PERMUTASYON_TEKRAR`a baktigi icin koruma saglamaz. CLAUDE.md §5:
    # "Rastgelelik her zaman sabit tohumla ve tohum sonuc dosyasina yazilir"; on-kayit §7: tohum
    # 20260911, tekrar 10.000.
    "TOHUM", "PERMUTASYON_TEKRAR", "ALFA_BONFERRONI",
    "__class__",
})

# ON-KAYIT DEGILDIR: yollar, uzak depo adresi, F1 denetim teshis esikleri ve korumanin kendi
# adlari. Bu kume `_DEGISMEZ_ADLAR` ile birlikte `config.py`deki butun acik sabitleri BOLER:
# ikisinde de olmayan ya da ikisinde de olan bir ad `tests/test_f1_config_kapsami.py`yi kirar,
# yani yeni bir sabit siniflandirilmadan eklenemez (madde 1a).
_ON_KAYIT_DISI = frozenset({
    "KOK", "VERI_DIZINI", "ONBELLEK_DIZINI", "ANALIZ_DIZINI", "SPLIT_CSV", "UNIVERSE_CSV",
    "EXCHANGE_INFO_ANLIK", "DENETIM_UZUN_BOSLUK_BAR", "DENETIM_CAPRAZ_TOLERANS",
    "DENETIM_BORSA_GENELI_ORANI", "DENETIM_KISA_DONEM_GUN", "DENETIM_TEMSILI_GIRIS_SURE",
    "DENETIM_ILK_GECIKME_SAAT",
})


class _SabitModulTuru(type):
    """Sinifin KENDISI de degistirilemez (koruma turu madde 5).

    Kapatilan yol: `type(config).__setattr__ = types.ModuleType.__setattr__`. Sinifin ozel
    yontemini degistirmek butun korumayi tek satirda kaldiriyordu.
    """

    def __setattr__(cls, ad, deger):
        raise SabitDegistirilemez(f"config modul sinifinin {ad!r} ozelligi degistirilemez "
                                  "(sabit koruma katmani).")

    def __delattr__(cls, ad):
        raise SabitDegistirilemez(f"config modul sinifinin {ad!r} ozelligi silinemez "
                                  "(sabit koruma katmani).")


def _sabit_atama(self, ad, deger):
    if ad in _DEGISMEZ_ADLAR:
        raise SabitDegistirilemez(f"config.{ad} calisma aninda yeniden atanamaz.")
    _types.ModuleType.__setattr__(self, ad, deger)


def _sabit_silme(self, ad):
    if ad in _DEGISMEZ_ADLAR:
        raise SabitDegistirilemez(f"config.{ad} silinemez.")
    _types.ModuleType.__delattr__(self, ad)


def _sabit_ozellik(ad: str, deger):
    """Degismez bir sabiti VERI TANIMLAYICISINA (data descriptor) baglar (madde 5).

    Kapatilan yol: `object.__setattr__(config, "TOHUM", 1)`. `object.__setattr__` modulun ornek
    sozlugune dogrudan yaziyordu, yani `_SabitModul.__setattr__` atlanabiliyordu. Veri
    tanimlayicisi ornek sozlugunden ONCE gelir: hem okuma degeri buradan gelir hem de
    `object.__setattr__` tanimlayicinin `__set__`ini cagirmak zorundadir, dolayisiyla red calisir.

    Degerin kendisi KAPANISTA tutulur; modul sozlugundeki kopya yalnizca geriye uyumluluk
    icindir ve okunmaz. Bu yuzden `vars(config)[ad] = ...` (asagidaki bilincli sinir) artik
    `config.<ad>` okumalarini da degistirmez.
    """

    def _al(self, _deger=deger):
        return _deger

    def _ata(self, yeni, _ad=ad):
        raise SabitDegistirilemez(f"config.{_ad} calisma aninda yeniden atanamaz "
                                  "(veri tanimlayicisi; `object.__setattr__` de gecemez).")

    def _sil(self, _ad=ad):
        raise SabitDegistirilemez(f"config.{_ad} silinemez (veri tanimlayicisi).")

    return property(_al, _ata, _sil)


# Sinif kurulurken tanimlayicilar yerlestirilir: `_SabitModulTuru.__setattr__` sinifi kilitledigi
# icin sonradan eklenemezler, bu yuzden `type()` ile yeni bir alt sinif uretilir.
_sabitler = {ad: _sabit_ozellik(ad, globals()[ad]) for ad in sorted(_DEGISMEZ_ADLAR)
             if ad in globals() and ad != "__class__"}
_SabitModul = _SabitModulTuru("_SabitModul", (_types.ModuleType,),
                              {**_sabitler,
                               "__setattr__": _sabit_atama,
                               "__delattr__": _sabit_silme,
                               "__doc__": "config modulunun sabit koruma sinifi (madde 5)."})

_sys.modules[__name__].__class__ = _SabitModul
