"""Tek karar noktasi: bir olay ya da kontrol olusur mu? (on-kayit §4 rev.8, rev.9)

On-kayit §4 "Olayin kumede olusma olcutu": "Bir olayin kumede olusup olusmadigina tek
bir karar noktasi hukmeder ... Ayni karar noktasinda pozisyonun funding tamligi da
saglanmalidir ... Uygunluk da bu karar noktasinin parcasidir (rev.9): hacim esigi ve
listeleme yasi dahil uygunluk filtresi, olaylar ve kontroller icin ayni karar noktasinda,
ayni cagriyla uygulanir. Uygunluk degerinin hesaplanabilmis olmasi yeterli degildir;
esigi de gecmelidir. ... Boylece brut ve net olay kumeleri her zaman aynidir."

P2b-2'den (RESULTS §14.49) beri karar noktasi TEK SERI KAPIDIR: `kapi_serisi` bir (sembol, donem, kume)
biriminin hipotez izgarasindaki butun barlarina ayni cekirdekle (`_kapi_satirlari`) karar verir; `olay_karari`
onun t satirini okuyan ince sarmalayicidir. Olaylar ve kontroller (K1, K2) ayni yoldan gecer, ayri bir kontrol
yolu yoktur. Bar basina skaler karar govdesi yalnizca dondurulmus skaler referansta yasar. Adimlar ve sirasi
(cekirdekte vektorel; ret gerekcesi ve mesaji skalerle birebir):
  0. Hipotez -> izgara -> ufuk bagi (`pencere.hipotez_baglamini_dogrula`; F1 kapanis turu),
     yapilandirmanin izgarada olmasi (`sinyal.yapilandirma_dogrula`) ve ROL (on-kayit §6 rev.11).
  1. `pencere.pozisyon_plani`: sinyal kumede ve donem ici, giris bari, cikis (donem
     sonu / olagan / ileri kayma ve siniri), gercek cikis ani + tolerans <= kume sonu.
  2. Sinyal degerleri: kapi hipotezin butun sinyal degerlerini KENDISI hesaplar
     (`data.sinyal`; Rev.11 madde 4, F1 kapanis bulgusu D-B1). Cagiran deger vermez.
     Rol "olay" ise butun degerler hesaplanmali (`SinyalPenceresiTamDegil`, on-kayit §2
     "Tamlik sarti") ve §5'teki kosullar saglanmali (`SinyalKosuluSaglanmadi`). Rol "K1" ya da
     "K2" ise sinyal KOSULLARI hic hesaplanmaz (on-kayit §6, rev.12); yalnizca CAPASIZ
     pencerelerin hesaplanabilirligi aranir (`SinyalPenceresiTamDegil`).
  3. Uygunluk (`eligibility.uygunluk_karari`, esikler zorunlu anahtar sozcuk) -> `UygunDegil`.
  4. Funding tamligi (`funding.pozisyon_funding_ayrintisi`) -> `FundingTamDegil`; ayni satirdan
     F2 saglamlik bayraklari (kismi kuyruk, esitlik affi, funding ritmi).

Adim sirasi Rev.11'de degisti: sinyal tamligi artik plandan SONRA denetlenir, cunku sinyal
pencereleri kume ve donem sinirlarini plandan okur (rev.11 oncesi cagiranin verdigi sayilar
sinirsiz denetlenebiliyordu). Iki adim da ayni `OlayOlusmaz` ailesindedir; degisen yalnizca
ikisi birlikte basarisiz oldugunda yukari cikan ret gerekcesidir.
Karar olumluysa `OnaylanmisPozisyon` doner: plan, P0, P1 ve funding toplami. Brut
getiri, net getiri, MAE ve K1/K2 kontrolleri YALNIZCA bu ciktiyi kullanir;
`pozisyon_fiyatlari` ve `mae` baska girdi kabul etmez. Ayri bir kapi yoktur.

Veri (kapi sertlestirme turu 2): karar noktasi fiyat, funding ve 1d cercevelerini cagirandan ALMAZ.
4h serisini ve funding kayitlarini sembol ve kume adiyla kume korumali yukleyicilerden
(`klines.mumlari_yukle`, `funding.funding_yukle`; C1/C2 icin acik onay kosusu sarttir) kendisi
yukler, kume araligina keser ve 1d serisini bu 4h barlardan tek yol `klines.gunluge_cevir` ile
turetir. Donem ve kume kayitlari commit edilmis tablolardan okunur. Bu yuzden fonksiyonlar saf
degildir: disk okurlar (CLAUDE.md §5: ag ve disk erisimi yalnizca `data/` katmaninda).

**Rol (on-kayit §6 "Kontrolun ne olctugu", rev.11; "Kontrol barinda sinyal pencereleri", rev.12).**
"Kontrol bari, olayin sinyal yapisini taklit etmez: kontrolde hipotezin sinyal kosullari aranmaz.
... Kontrol bari icin gereken: uygunluk filtresi, donem uyeligi, fiyat ve funding tamligi,
hipotezin capasiz sinyal pencerelerinin hesaplanabilir olmasi, ve §4'teki tek karar noktasinin
butun kosullari." Bu yuzden `rol`:
  - `"olay"`: hipotezin BUTUN sinyal degerleri hesaplanir ve §5'teki kosullar SAGLANMALI.
  - `"K1"` ve `"K2"`: sinyal KOSULLARI hicbir amacla hesaplanmaz (rev.12). Hesaplanan tek sey
    CAPASIZ pencerelerdir (`sinyal.capasiz_pencere_degerleri`) ve bunlarin hesaplanabilir olmasi
    sarttir; hesaplanamiyorsa bar kontrol olamaz. Iki kontrol kumesi ayni yoldan gecer.
    K2'nin "o anda olay uretmemis" sarti kapinin isi DEGILDIR (rev.12): ornekleme adimi
    (`data.ornekleme.k2_adaylari`) o barin ayni yapilandirmanin olusmus olay kumesinde bulunup
    bulunmadigina bakarak uygular. Rev.11'de bu sart H2 ve H3 icin kapida kosul hesaplanarak
    (`OlayUretmis`), H1'de ornekleme adiminda uygulaniyordu; rev.12 ucunu ayni yola koydu.
    K1'in olcutu zamansal uzakliktir, sinyal degil.

Getiri HESAPLAMAZ (F2 kodu degildir); fiyat ve funding degerlerini tasir ama raporlamaz.
"""

from __future__ import annotations

import functools
import hashlib
import math
import sys
import threading
from collections import OrderedDict
from types import MappingProxyType
from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

import config
from data import eligibility as eligibility_modulu
from data import funding as funding_modulu
from data import klines as klines_modulu
from data import kume_bellegi
from data import pencere as pencere_modulu
from data import seri_kurucu as seri_kurucu_modulu
from data import sinyal as sinyal_modulu
from data import split as split_modulu
from data import universe as universe_modulu


# Hipotez basina kapinin HESAPLADIGI sinyal degerleri (Rev.11 madde 4; F1 kapanis bulgusu D-B1).
# Rev.11'den once bu adlar cagirandan ISTENIYORDU; artik kapi degerleri `data.sinyal`in pencere
# kuruculariyla kendisi hesaplar ve `sinyal_degerleri` anahtar sozcugu KALKMISTIR. Adlarin ve
# pencere sinirlarinin tek kaynagi `sinyal.DEGER_ADLARI`dir (on-kayit §5 "Pencere sinirlari").
# On-kayit §2 "Tamlik sarti": "Pencerede beklenen barlardan biri bile eksikse deger hesaplanmaz ve o
# barda olay ya da kontrol olusmaz"; §4 "Funding sinyal penceresinin tamligi": "... o barda olay ya
# da kontrol olusmaz".
SINYAL_DEGERLERI = sinyal_modulu.DEGER_ADLARI
# H2'nin funding ortalamasi; penceresinin butun kurallari `funding.funding_ortalamasi`dedir.
FUNDING_SINYALI = "funding_24s"

# Barin rolu (on-kayit §6 rev.11 "Kontrolun ne olctugu"; modul aciklamasindaki "Rol" basligi).
ROLLER = ("olay", "K1", "K2")
KONTROL_ROLLERI = ("K1", "K2")


class SinyalPenceresiTamDegil(pencere_modulu.OlayOlusmaz):
    """Sinyal pencerelerinden biri tam degil (NaN) (on-kayit §2 "Tamlik sarti")."""

    gerekce = "sinyal_penceresi_tam_degil"


class UygunDegil(pencere_modulu.OlayOlusmaz):
    """Sinyal (ya da kontrol) barinda sembol uygun degil: listeleme yasi ya da medyan
    hacim esigi gecilmiyor, ya da hacim penceresi hesaplanamiyor (on-kayit §2 "Uygunluk";
    §4 rev.9: uygunluk tek karar noktasinin parcasidir)."""

    gerekce = "uygun_degil"


class FundingTamDegil(pencere_modulu.OlayOlusmaz):
    """Pozisyonun funding'i tam degil (on-kayit §4 rev.9 "Funding tamligi");
    olay ya da kontrol brut dahil hicbir hesapta olusmaz."""

    gerekce = "funding_tam_degil"


class SinyalKosuluSaglanmadi(pencere_modulu.OlayOlusmaz):
    """Sinyal degerleri hesaplandi ama hipotezin §5'teki kosullari bu barda saglanmadi; olay
    olusmaz. Kontrol barinda bu bir ret gerekcesi DEGILDIR (on-kayit §6 rev.11: "kontrolde
    hipotezin sinyal kosullari aranmaz")."""

    gerekce = "sinyal_kosulu_saglanmadi"


class SinyalBariYok(pencere_modulu.OlayOlusmaz):
    """Sinyal bari t, hipotezin izgarasindaki donem ici seride yok: 4h'de t acilisli bar, 1d'de t gunu
    (alti 4h barin tamami; on-kayit §2 "1 gunluk barlar"). Sinyal t barinin kapanisinda hesaplanir ve
    pencereler t'yi icerir (on-kayit §5 "Pencere sinirlari"); t yoksa olay ya da kontrol olusmaz
    (kapi sertlestirme turu 2, denetci KS D-B3)."""

    gerekce = "sinyal_bari_yok"


_ONAY_GIZLI = object()


@dataclass(frozen=True)
class OnaylanmisPozisyon:
    """Tek karar noktasindan gecmis pozisyon. Yalnizca `olay_karari` uretir.

    `p0`: giris barinin acilisi; `p1`: cikis barinin `plan.cikis.fiyat_alani`
    alani; `funding_toplami`: pozisyonun funding'i (on-kayit §4). Degerler raporlanmaz.

    F2 saglamlik kontrolunun bayraklari (on-kayit §4 rev.9 "Funding tamliginin bilinen
    sinirlari", "F2 sarti"); hepsi gercek tamlik kodundan (`funding.pozisyon_funding_ayrintisi`)
    ve imzaya bagli:
      - `kuyruk_kismi`: son kayittan pencere sonuna kalan dilim bir tam araliktan kisa
        (o dilimdeki eksik odeme gorulemez),
      - `son_esitlik_affi`: son kayit + araligi tam pencere sonuna denk geliyor, orada kayit
        yok; pozisyon tam sayildi,
      - `capa_aralik_saat`, `son_aralik_saat`, `tek_ritim`: pozisyonun funding ritmi
        etiketleri (capanin ve dizideki son kaydin araligi; capadan son kayda araliklar ayni mi),
      - `funding_ritmi_saat`: pozisyonun funding ritmi = son kaydin araligi; `karisik_ritim`: ritim
        pencere icinde degisti; `ritim_sinifi`: "8", "4", "2", "1" ya da "siniflanmamis" (on-kayit §4
        "Pozisyonun funding ritmi", rev.10; `funding.ritim_sinifi`).
    Bayraklarin varsayilanlari yalnizca elle kurulan (gecersiz) nesne icindir.
    """

    plan: pencere_modulu.PozisyonPlani
    p0: float
    p1: float
    funding_toplami: float
    kuyruk_kismi: bool = False
    son_esitlik_affi: bool = False
    capa_aralik_saat: float = float("nan")
    son_aralik_saat: float = float("nan")
    tek_ritim: bool = False
    funding_ritmi_saat: float = float("nan")
    karisik_ritim: bool = False
    ritim_sinifi: str | None = None
    # Gecersizlik (stop) seviyesi: YALNIZCA F4 icin kayit (on-kayit §5 H1 madde 5, H2 madde 4,
    # H3 madde 4 rev.13; §8 madde 1 "Olay basina ham kayitta ayrica MAE ve gecersizlik seviyesi
    # saklanir"). Yalnizca olay rolunde hesaplanir; kontrol barinda tanimsizdir (NaN) cunku
    # on-kayit seviyeyi olayin sinyal penceresinden kurar. Hicbir F2/F3 karari bu degere bakmaz.
    gecersizlik_seviyesi: float = float("nan")
    hipotez: str | None = None
    # Yapilandirma kimligi ve rol (on-kayit §5, §6 rev.11): ornekleme ve dizi kurallari "ayni
    # yapilandirmanin olusmus olaylari"na gore isler, bu yuzden onayli pozisyon ikisini de tasir.
    yapilandirma: str | None = None
    rol: str | None = None
    # Capa (H1'in pump bari; baska her durumda None). Imzaya dahildir, cunku olay dizisi kurallari
    # dondurulen pozisyonun SORULAN (t, capa) ciftine ait oldugunu dogrular (sizinti bulgusu S-B1):
    # "bir teyit bari en cok bir olay sayar" (on-kayit §5 H1 madde 4) ancak capa denetlenirse
    # garanti olur.
    capa: pd.Timestamp | None = None
    # Kimlik (kapi sertlestirme turu 2): `mae` ve `funding.pozisyon_fundingi` veriyi bu kimlikle kendileri
    # yukler; cagiran cerceve vermez.
    sembol: str | None = None
    kume: str | None = None
    donem_no: int | None = None
    _imza: int = field(default=0, repr=False, compare=False)

    @property
    def cikis_turu(self) -> str:
        return self.plan.cikis_turu


def _imza(p: OnaylanmisPozisyon) -> int:
    return hash((_ONAY_GIZLI, p.plan, p.p0, p.p1, p.funding_toplami, p.kuyruk_kismi, p.son_esitlik_affi,
                 p.capa_aralik_saat, p.son_aralik_saat, p.tek_ritim, p.funding_ritmi_saat, p.karisik_ritim,
                 p.ritim_sinifi, p.gecersizlik_seviyesi, p.hipotez, p.yapilandirma, p.rol, p.capa,
                 p.sembol, p.kume, p.donem_no))


# Test dikisinin (`_test_onayi`) urettigi onaylarin OMUR kaydi: imza -> onu kuran pytest testinin
# kimligi (denetci bulgusu D-C2). `split._test_kaydi_ayarla` kurdugu ayari testin kimligine baglar
# ve test bitince ayar kendiliginden gecersizlesir; dikisin urettigi nesne ise ayni oturumdaki
# BASKA bir testte de gecerliydi. Sozluk yalnizca pytest icinde dolar (dikis dislarda
# `RuntimeError` verir), bu yuzden gercek kosuda bostur ve denetim bedelsizdir.
_TEST_ONAY_OMURLERI: dict[int, str] = {}


def _test_onay_omru_dogrula(pozisyon) -> None:
    """Dikisin urettigi onay YALNIZCA kendi testinde gecerlidir (denetci bulgusu D-C2)."""
    if not _TEST_ONAY_OMURLERI:
        return
    kuran = _TEST_ONAY_OMURLERI.get(pozisyon._imza)
    if kuran is None:
        return
    simdi = split_modulu._pytest_testi()
    if simdi != kuran:
        raise ValueError(
            "Bu onay `pozisyon._test_onayi` ile BASKA bir testte kuruldu ve omru o testle sinirlidir "
            f"(kuran test: {kuran}; simdiki: {simdi}). Dikis gercek onayin yerine gecmez "
            "(on-kayit §4 'tek karar noktasi'; denetci bulgusu D-C2).")


def onay_dogrula(pozisyon) -> None:
    """`olay_karari`nin urettigi ve degistirilmemis bir pozisyon mu?"""
    if not isinstance(pozisyon, OnaylanmisPozisyon):
        raise TypeError(f"Onaylanmis pozisyon gerekir (pozisyon.olay_karari ciktisi); verilen: {type(pozisyon).__name__}")
    if pozisyon._imza != _imza(pozisyon):
        raise ValueError("OnaylanmisPozisyon elle kurulmus ya da degistirilmis; yalnizca olay_karari uretir.")
    _test_onay_omru_dogrula(pozisyon)


def _close_time_nat_yok(mumlar: pd.DataFrame, ad: str) -> None:
    """`close_time` sutununda NaT yok (tek uygulama `eligibility.close_time_nat_yok`; RESULTS §14.49, D-B3)."""
    eligibility_modulu.close_time_nat_yok(mumlar, ad)


def _gunluk_hacim(gunluk_mumlar: pd.DataFrame) -> pd.Series:
    """Uygunluk hacminin girdisi: sembolun 1d serisi (`klines.mumlari_yukle(s, "1d", ...)`,
    tek 1d yolu `klines.gunluge_cevir`). 1d olmayan cerceve (ör. 4h mumlari) acik hata verir:
    acilislar gun basi olmali ve `close_time` varsa bar suresi 4 saati asmali. Dogrulama
    `eligibility.gunluk_cercevesini_dogrula`dadir; seri kurucusu ayni fonksiyonu cagirir (D-B3)."""
    eligibility_modulu.gunluk_cercevesini_dogrula(gunluk_mumlar)
    return eligibility_modulu.gunluk_hacim_serisi(gunluk_mumlar)


def _mum_zamanlari(mumlar: pd.DataFrame) -> pd.DatetimeIndex:
    """Fiyat okuma tabaninin 4h serisi oldugunu denetler (on-kayit §4 rev.8 "Fiyat okuma
    tabani": pozisyonun butun fiyat okumalari her hipotezde donem ici 4h barlardan; denetci
    bulgusu D-B3). 1d cercevesi (ör. `klines.mumlari_yukle(s, "1d", ...)`) ayni sutun adlarini
    tasidigi icin sessizce kabul edilirse her cikis ileri kaymaya duser; burada acik hata verir:
      - acilislar 4h izgarasinda (gun basindan 0, 4, ..., 20 saat) olmali,
      - `close_time` varsa hicbir barin suresi 4 saati asmamali; yoksa en az iki bar olmali,
      - `close_time` YOKSA ardisik iki acilis arasindaki en kucuk fark 4 saat olmali.

    Ardisiklik sarti yalnizca `close_time` yoksa aranir (bulgu K-C8, koruma turu madde 7). Bar
    duzeyli mevcutluk olcutu (D-B3) bozuk hucreli barlari seriden DUSURUR; dar bir donemde geriye
    yalnizca komsu olmayan barlar kalirsa ardisiklik sarti `VeriHatasi` firlatiyordu -- yani bir
    ret gerekcesi yerine yukari cikan bir hata. Oysa eksik barin normal yolu rettir (`GirisBariYok`,
    tamlik). 4h serisi oldugunu dogrulayan asil olcutler IZGARA ve BAR SURESIDIR; ikisi de yerinde
    kalir, bu yuzden 1d cercevesinin 4h gibi verilmesi (D-B3'un amaci) yine yakalanir.
    """
    zamanlar = pencere_modulu._zaman_dizisi_dogrula(pd.DatetimeIndex(mumlar["open_time"]), "olay_karari")
    if len(zamanlar) == 0:
        return zamanlar
    adim = pencere_modulu.ADIM_4H
    if bool(((zamanlar - zamanlar.floor("D")) % adim != pd.Timedelta(0)).any()):
        raise pencere_modulu.VeriHatasi("mumlar_4h 4h izgarasinda degil (acilislar 00/04/08/12/16/20 UTC olmali).")
    if "close_time" not in mumlar and len(zamanlar) < 2:
        # Tek satirlik ve close_time'siz cerceve: gece yarisi acilisli bir 1d bari izgaraya uyar
        # ve ardisik fark olculemez; 4h serisi oldugu dogrulanamaz (sizinti testcisi bulgusu).
        raise pencere_modulu.VeriHatasi("mumlar_4h 4h serisi oldugu dogrulanamiyor: tek satir ve close_time yok "
                         "(on-kayit §4 'Fiyat okuma tabani').")
    if "close_time" in mumlar:
        _close_time_nat_yok(mumlar, "mumlar_4h")
        sure = pd.DatetimeIndex(mumlar["close_time"]) - zamanlar
        if bool((sure > adim).any()):
            raise pencere_modulu.VeriHatasi("mumlar_4h 4h serisi olmali: bar suresi 4 saati asiyor (1d cercevesi verilmis olabilir; "
                             "on-kayit §4 'Fiyat okuma tabani').")
    if "close_time" not in mumlar and len(zamanlar) > 1 and (zamanlar[1:] - zamanlar[:-1]).min() != adim:
        raise pencere_modulu.VeriHatasi("mumlar_4h 4h serisi olmali: ardisik acilislar arasinda 4 saatlik fark yok "
                         "(1d cercevesi verilmis olabilir; on-kayit §4 'Fiyat okuma tabani').")
    return zamanlar


def _bar_degeri(mumlar: pd.DataFrame, zamanlar: pd.DatetimeIndex, zaman: pd.Timestamp, alan: str) -> float:
    bar = pencere_modulu.ayni_andaki_bar(zamanlar, zaman)
    if bar is None:
        raise pencere_modulu.VeriHatasi(f"{zaman} bari mum cercevesinde yok (karar ile ayni seri verilmeli).")
    return float(mumlar[alan].to_numpy()[int(zamanlar.get_loc(bar))])


def kume_sinirlari(kume) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Kume adindan [baslangic, bitis] (on-kayit §3 "Donemler"); tek kaynak `split.kume_araligi`.

    Yalnizca `config.KUMELER`deki adlar, tam `str` turunde (alt sinif `__eq__` ile yalan
    soyleyebilir). Baska her deger programlama hatasidir: TypeError ya da ValueError."""
    if type(kume) is not str:
        raise TypeError(f"kume bir kume adi olmali ({config.KUMELER}); verilen: {kume!r}. Sinirlar "
                        "cagirandan alinmaz (on-kayit §3).")
    if kume not in config.KUMELER:
        raise ValueError(f"Bilinmeyen kume: {kume!r}. Gecerli: {config.KUMELER}")
    return split_modulu.kume_araligi(kume)


@functools.lru_cache(maxsize=1)
def _kayitlar():
    """Commit edilmis evren ve bolme tablolarindan salt okunur kayitlar (bir kez okunur; ag yok).

    Donemler: (sembol, donem_id) -> (donem_baslangic, donem_bitis, donem_funding_yok); yalnizca haric
    tutulmayan semboller ve gecerli donemler (`donem_id >= 0`). Gruplar: sembol -> "A" / "B"."""
    evren = universe_modulu.evren_yukle()
    evren = evren.loc[~evren["haric"] & (evren["donem_id"] >= 0)]
    donemler = {
        (str(sembol), int(no)): (pd.Timestamp(bas), pd.Timestamp(bitis), bool(yok))
        for sembol, no, bas, bitis, yok in zip(evren["sembol"], evren["donem_id"], evren["donem_baslangic"],
                                               evren["donem_bitis"], evren["donem_funding_yok"])
    }
    bolme = split_modulu.split_oku()
    gruplar = {str(s): str(g) for s, g in zip(bolme["sembol"], bolme["grup"])}
    return MappingProxyType(donemler), MappingProxyType(gruplar)


def donem_kaydi(sembol, donem_no) -> tuple[pd.Timestamp, pd.Timestamp, bool]:
    """(donem_baslangic, donem_bitis, donem_funding_yok): evren tablosundaki listeleme donemi (on-kayit §2
    "Listeleme donemi"). Tabloda olmayan (ya da haric tutulan sembolun) donem programlama hatasidir:
    ValueError. `sembol` tam `str`, `donem_no` tamsayi (bool degil) olmalidir: TypeError."""
    if type(sembol) is not str:
        raise TypeError(f"sembol str olmali; verilen: {sembol!r}")
    if isinstance(donem_no, bool) or not isinstance(donem_no, (int, np.integer)):
        raise TypeError(f"donem_no tamsayi olmali (evren tablosundaki donem_id); verilen: {donem_no!r}")
    kayit = _kayitlar()[0].get((sembol, int(donem_no)))
    if kayit is None:
        raise ValueError(f"{sembol} donem {donem_no} evren tablosunda yok (ya da sembol haric): donem sinirlari "
                         "yalnizca tablodan okunur (on-kayit §2 'Evren tablosunun sabitlenmesi').")
    return kayit


def grup_dogrula(sembol: str, kume: str) -> None:
    """Sembolun bolme grubu kumenin gruplarindan biri mi (on-kayit §3: KESIF A, C1 B, C2 A + B)? Degilse
    programlama hatasi: ValueError."""
    gruplar, _, _ = split_modulu.kume_tanimi(kume)
    grup = _kayitlar()[1].get(sembol)
    if grup is None or grup not in gruplar:
        raise ValueError(f"{sembol} (grup {grup}) {kume} kumesine ait degil; kume gruplari {gruplar} "
                         "(on-kayit §3 'Coin bolmesi').")


@dataclass(frozen=True)
class _DonemSiniri:
    """`klines.gunluge_cevir`in bir donemden okudugu iki alan (baslangic, bitis = B)."""

    baslangic: pd.Timestamp
    bitis: pd.Timestamp


def _veri_yukle(sembol: str, kume: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Kapinin TEK veri yolu: sembolun 4h mumlari ve funding kayitlari, kume korumali yukleyicilerden.

    C1/C2 icin `onay=True` verilir; yukleyiciler yine de acik bir `split.onay_kosusu` ister
    (`split.kume_erisimi`), yoksa `OnayGerekli`. Testler bu fonksiyonu sentetik veriyle degistirir
    (`tests/conftest.py`); analiz kodu icin kaynak taramasinda yasaklidir (`KAYIT_DESENI`)."""
    onay = kume in config.ONAY_KUMELERI
    mumlar = klines_modulu.mumlari_yukle(sembol, config.BAR_4H, kume, onay=onay)
    fr = funding_modulu.funding_yukle(sembol, kume, onay=onay)
    return mumlar, fr


def _erisim_denetimi(kume: str):
    """Bellek onbelleginin her okunusunda calisan denetim (on-kayit §3 rev.13; `data.kume_bellegi`)."""
    return lambda: split_modulu.onay_erisimi_denetle(kume, kume in config.ONAY_KUMELERI)


def _kume_verisi(sembol: str, kume: str, kume_baslangic, kume_bitis) -> tuple[pd.DataFrame, pd.DataFrame]:
    """`_veri_yukle` ciktisi, kume araligina kesilmis. Bellek onbelleginden gecer: `mae` ve
    `funding.pozisyon_fundingi` de ayni yolu kullanir, ayri bir yukleme yolu yoktur."""
    return kume_bellegi.getir(
        ("kume", sembol, kume, kume_baslangic, kume_bitis), _erisim_denetimi(kume),
        lambda: _kume_verisi_yukle(sembol, kume, kume_baslangic, kume_bitis))


def _kume_verisi_yukle(sembol: str, kume: str, kume_baslangic, kume_bitis) -> tuple[pd.DataFrame, pd.DataFrame]:
    """`_veri_yukle` ciktisi, kapida kume araligina yeniden kesilmis (ikinci savunma; yukleyici zaten keser)."""
    mumlar, fr = _veri_yukle(sembol, kume)
    if not isinstance(mumlar, pd.DataFrame) or not isinstance(fr, pd.DataFrame):
        raise pencere_modulu.VeriHatasi("veri yukleyicisi iki DataFrame dondurmeli (4h mumlari, funding).")
    # Zaman dizileri kesimden ONCE dogrulanir (kapi sertlestirme turu 3): tz'siz, sirasiz ya da tekrarli
    # damga `ZamanDizisiHatasi` (VeriHatasi) olur; kesimdeki naive/aware karsilastirmasina (TypeError) dusmez.
    if len(mumlar):
        pencere_modulu._zaman_dizisi_dogrula(pd.DatetimeIndex(mumlar["open_time"]), "_kume_verisi (4h)")
    if len(fr):
        funding_modulu._zaman_dizisi(fr, "_kume_verisi (funding)")
    mumlar = klines_modulu.donem_kes(mumlar, kume_baslangic, kume_bitis)
    mumlar = _tam_hucreli_barlar(mumlar)
    if len(fr):
        zaman = pd.DatetimeIndex(fr["odeme_zamani"])
        fr = fr.loc[np.asarray((zaman >= kume_baslangic) & (zaman <= kume_bitis), dtype=bool)].reset_index(drop=True)
    return mumlar, fr


def _karar_verisi(sembol: str, kume: str, *, kume_baslangic, kume_bitis, donem_baslangic,
                  donem_bitis) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(4h mumlari, funding, 1d mumlari): kararin ve kosulun verisi TEK yerden gelir (P-C1).

    Bulgu neydi: donem kurali IKI AYRI MEKANIZMADA duruyordu. `sinyal_kosulu` veriyi donem ∩ kume
    araligina KESIYOR, `olay_karari` ise kume araligini yukleyip donem uyeligini yalnizca pencere
    YUKLEMLERINE (plan, `donem_ici_*`, `gunluge_cevir`) birakiyordu. Denetci iki yolun bugun
    esdeger oldugunu dogruladi (tek davranis farki (B, K] araligindaki funding kayitlari, etkisi
    sifir). Risk sapma degil AYRISMA: biri gevserse DIZI DURUMU (kosulun sonucu) ile KAPININ
    onayi farkli veriden hesaplanir, oysa on-kayit §4 rev.12 dizi kurallarini ve kapiyi ayni olay
    kumesinin iki sarti sayar.

    Kesim kurali (on-kayit §2 "Listeleme donemi"): "Donem disindaki hicbir bar (dolgu bari,
    bosluk sonrasi veri, SETTLED verisi) hicbir hesaba girmez." 4h serisi bu yuzden
    [max(kume basi, donem basi), min(kume sonu, B)] araligina kesilir ve 1d serisi bu kesilmis
    seriden turetilir.

    FUNDING kume araligindan kesilir, donemden DEGIL: pozisyonun odemeleri donem bitisi B ile
    donem kapanisi K = B + 4 saat arasinda da olabilir (on-kayit §4 rev.8 "Funding tamligi"), yani
    B'de kesmek odemeleri dusururdu. Sinyal penceresi tarafinda bu bir fark yaratmaz: §5 H2'nin
    penceresi t'den GERIYE uzanir ve `funding.funding_ortalamasi` donem basi sinirini ayrica
    uygular. Asimetri bu yuzden bilincli ve tek yerde yazilidir.

    Pencere yuklemleri (plan, `donem_ici_4h_maskesi`, `gunluge_cevir`) kaldirilmadi: kesimden
    sonra ayni hukmu tekrar ederler, yani ikinci bir savunmadir -- ama kurali UYGULAYAN yer
    burasidir.

    Sonuc (sembol, kume, donem) basina bir kez hesaplanir (`data.kume_bellegi`); erisim denetimi
    her cagrida calisir.
    """
    return _karar_girdisi(sembol, kume, kume_baslangic=kume_baslangic, kume_bitis=kume_bitis,
                          donem_baslangic=donem_baslangic, donem_bitis=donem_bitis)[:3]


class _PlanSerisi:
    """Plan serisi (performans 2a, plan v2 karar 5): (sembol, kume, donem) verisi icin (bar, ufuk, birincil ufuk, t) ->
    `pencere.pozisyon_plani` sonucu (imzali plan ya da `OlayOlusmaz` reddi). Her anahtar EN COK BIR KEZ kurulur ve
    yapilandirmalar ile hipotezler arasinda paylasilir: plan hipotezin bar turune ve birincil ufkuna baglidir,
    yapilandirmaya bagli degildir; on-kayit §4 "Ufuk degerlerinin baglanmasi" (rev.10): "H1 ve H2 icin 4h izgarada
    birincil 18 bar ... H3 icin 1d izgarada birincil 14 gun". Plan VEKTORLESTIRILMEZ; yalnizca yeniden kullanilir.

    Seri `kume_bellegi`ndeki `_karar_girdisi` girdisinin parcasidir, ayri bir girdi degildir: anahtar kume adini
    tasir, her okumada erisim denetimi calisir (isabet dahil), onay kosusunun acilisi ve kapanisi (`temizle`) ve LRU
    dusurmesi seriyi veriyle birlikte dusurur (proje anayasasi §5, on-kayit §3). `copy()` kendisini doner: seri
    paylasim icindir ve yalnizca degismez nesneler (imzali plan, ret sinifi ve mesaji) tasir; veri cercevesi tasimaz.
    Ret yeniden firlatilirken ayni sinif ve ayni mesajla yeni bir nesne kurulur. `OlayOlusmaz` disindaki hatalar
    (programlama ya da veri hatasi) saklanmaz, her cagrida yeniden olusur."""

    __slots__ = ("_harita",)

    def __init__(self):
        self._harita: dict = {}

    def copy(self):
        return self

    def al(self, anahtar, kur):
        kayit = self._harita.get(anahtar)
        if kayit is None:
            try:
                kayit = ("plan", kur())
            except pencere_modulu.OlayOlusmaz as hata:
                kayit = ("ret", type(hata), hata.args)
            self._harita[anahtar] = kayit
        if kayit[0] == "ret":
            raise kayit[1](*kayit[2])
        return kayit[1]

    def __len__(self) -> int:
        return len(self._harita)


def _karar_girdisi(sembol: str, kume: str, *, kume_baslangic, kume_bitis, donem_baslangic, donem_bitis):
    """(4h mumlari, funding, 1d mumlari, plan serisi): `_karar_verisi`nin bellek girdisi ve plan serisi (tek girdi)."""
    return kume_bellegi.getir(
        ("karar", sembol, kume, kume_baslangic, kume_bitis, donem_baslangic, donem_bitis),
        _erisim_denetimi(kume),
        lambda: (*_karar_verisi_kur(sembol, kume, kume_baslangic, kume_bitis, donem_baslangic, donem_bitis),
                 _PlanSerisi()))


def _karar_verisi_kur(sembol: str, kume: str, kume_baslangic, kume_bitis, donem_baslangic,
                      donem_bitis) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    mumlar_4h, funding = _kume_verisi(sembol, kume, kume_baslangic, kume_bitis)
    veri_baslangic = max(pd.Timestamp(kume_baslangic), pd.Timestamp(donem_baslangic))
    veri_bitis = min(pd.Timestamp(kume_bitis), pd.Timestamp(donem_bitis))
    mumlar_4h = klines_modulu.donem_kes(mumlar_4h, veri_baslangic, veri_bitis)
    gunluk_mumlar = klines_modulu.gunluge_cevir(
        mumlar_4h, donemler=[_DonemSiniri(donem_baslangic, donem_bitis)])
    return mumlar_4h, funding, gunluk_mumlar


def _tam_hucreli_barlar(mumlar: pd.DataFrame) -> pd.DataFrame:
    """Hucresi bozuk barlari seriden DUSURUR: bar duzeyli mevcutluk olcutu (on-kayit §2, rev.12).

    On-kayit §2 (rev.12): "olcut alan duzeyinde degil BAR DUZEYINDEDIR ve her izgarada, her
    pencerede ve her HESAPTA gecerlidir." Denetci bulgusu D-B3: olcut `sinyal._seri` ve
    `klines.gunluge_cevir` icinde uygulaniyordu, ama pozisyonun FIYAT OKUMALARI (P0, P1, MAE'nin
    high'lari) ve plan adimi yalnizca damgaya bakiyordu. Hucresi bozuk (ör. `volume` NaN) ama
    `open`i gecerli bir 4h bar, on-kayit geregi "mevcut degil" olmasina ragmen giris bari olarak
    kabul ediliyordu; ileri kayma kurali hic devreye girmiyordu ve ayni bar sinyal penceresinde
    eksik sayildigi icin kod kendi icinde tutarsizdi.

    Olcutu TEK YERDE, verinin kapiya girdigi noktada uygulamak bu tutarsizligi kaldirir: bozuk
    bar seride yoktur, dolayisiyla plan onu giris/cikis bari saymaz (ileri kayma devreye girer),
    MAE penceresine girmez ve tamlik kontrolleri onu eksik bar olarak gorur. Olcut `data.klines`
    icindeki tek uygulamadan (`hucreleri_tam_mi`) gecer; ikinci bir kopya yoktur.

    Olculen etki bugun SIFIRDIR (dönem ici KESIF barlarinda bozuk hucre bulunmuyor); yine de
    uygulanir, cunku "olculmus sifir etki muafiyet degildir" (RESULTS §14.13).
    """
    if not len(mumlar):
        return mumlar
    tam = np.asarray(klines_modulu.hucreleri_tam_mi(mumlar), dtype=bool)
    if tam.all():
        return mumlar
    return mumlar.loc[tam].reset_index(drop=True)


def _utc_sinyal_zamani(sinyal_zamani) -> pd.Timestamp:
    """Sinyal zamani UTC olmali (CLAUDE.md §5 "Tum zaman damgalari UTC"). Saat dilimi olan ama UTC olmayan
    bir zaman, uygunluk penceresinin gun sinirini yerel saate kaydirir ve H1/H2 olaylarini sessizce
    `UygunDegil` ile dusururdu (kapi sertlestirme turu 2, denetci KS D-B5; testle dogrulandi). Acik hata."""
    zaman = pencere_modulu.utc_zamani(sinyal_zamani, "sinyal_zamani")
    if zaman.utcoffset() != pd.Timedelta(0) or zaman.tzname() != "UTC":
        raise ValueError(f"sinyal_zamani UTC olmali; verilen saat dilimi {zaman.tzinfo!r} ({zaman}). "
                         "UTC'ye cevrilerek verilmeli (CLAUDE.md §5).")
    return zaman


def _sonlu(deger: float, ad: str) -> float:
    """Sonlu olmayan (NaN, +-inf) fiyat ya da funding degeri acik hatadir (`VeriHatasi`): on-kayit bu durumu tanimlamaz;
    kapi bir olay-olusmaz kurali icat etmez (kapi sertlestirme turu 2, sizinti testcisi inf bulgusu)."""
    if not math.isfinite(deger):
        raise pencere_modulu.VeriHatasi(f"{ad} sonlu degil ({deger!r}); pozisyon onaylanmaz. On-kayit sonlu olmayan veriyi "
                         "tanimlamaz: veri denetlenmeli.")
    return deger


def _pozitif_fiyat(deger: float, ad: str) -> float:
    """Kapinin okudugu FIYAT sonlu VE POZITIF olmali; aksi halde `VeriHatasi` (koruma turu madde 2b).

    Gerekce: sifir ya da negatif bir perpetual fiyati mesru bir piyasa durumu degil, bozuk
    veridir. Olculdu (`koruma_olcumu.py --olcum pozitif_fiyat`, butun evren, temiz agac): donem
    ici 3.378.942 4h barin HICBIRINDE open/high/low/close sifir ya da negatif degil (sembol 0).
    Olcum sifir cikmasi muafiyet degildir (RESULTS §14.13): kapi bu durumu sessizce "olay olusmaz"
    diye gecmez, acik hata verir. Bu bir KURAL degil HATA yoludur, bu yuzden on-kayit degisikligi
    gerektirmez (`sinyal._pozitif` ile ayni tutum; Rev.9 D-C5).

    P0 ≤ 0 ayrica MAE'yi (`max(H, P1) / P0 - 1`) sifira bolmeye goturuyordu (sizinti bulgusu).

    ALTNORMAL deger de reddedilir (F1 kapatma turu madde 1b, bulgu 21): 1e-320 sonlu ve
    pozitiftir, ama `max(H, P1) / P0 - 1` orani onunla SONSUZA gider. Esik `sys.float_info.min`
    (yaklasik 2.2e-308); gercek bir perpetual fiyati bu buyuklugun yanina yaklasmaz (en kucuk
    tick 1e-8 duzeyindedir), bu yuzden esik hicbir mesru fiyati dislamaz. Bu da bir KURAL degil
    HATA yoludur.
    """
    _sonlu(deger, ad)
    if deger <= 0:
        raise pencere_modulu.VeriHatasi(
            f"{ad} pozitif bir fiyat olmali; verilen {deger!r}. Sifir ya da negatif fiyat bozuk veridir ve "
            "on-kayitta tanimlanmaz: kapi kural icat etmez, veri denetlenmeli (RESULTS §14.33).")
    if deger < sys.float_info.min:
        raise pencere_modulu.VeriHatasi(
            f"{ad} altnormal bir fiyat ({deger!r}); normal cift duyarlikli en kucuk degerin "
            f"({sys.float_info.min!r}) altinda. Boyle bir fiyat bozuk veridir ve oranlari sonsuza "
            "goturur (madde 1b, bulgu 21): veri denetlenmeli.")
    return deger


def _mae_tepesi(mumlar_4h: pd.DataFrame, zamanlar: pd.DatetimeIndex, plan, p1: float) -> float:
    """MAE'nin H'si (on-kayit §4 rev.8): giris anindan once acilmayan, cikis anindan sonra kapanmayan donem
    ici 4h barlarin en yuksek high'i ile P1'in buyugu. Secilen high'lar sonlu VE POZITIF olmali
    (`_pozitif_fiyat`; koruma turu madde 2b).

    Secim SIRALI dizide kenar aramasiyla yapilir (performans 2b-2, RESULTS §14.49; ayni kural, ayni toleransli
    yuklemler): `zamanlar` kesin artandir (`_mum_zamanlari`), bu yuzden dort kosulun her biri bir onek ya da sonek ve
    secim tek parcali bir araliktir. Kenarlar tamsayi nanosaniyede kesin esdegerdir:
      - `ayni_ya_da_sonra(z, g)` <=> `g - z < tol` <=> `z > g - tol` (`ayni_an_basi(g)`, sag kenar);
      - `ayni_ya_da_once(z + 4h, c)` <=> `z + 4h < c + tol` <=> `z < ayni_an_sonu(c) - 4h` (sol kenar);
      - donem uyeligi (`donem_ici_4h_maskesi`): `z > ayni_an_basi(donem basi)` ve `z < ayni_an_sonu(B)`.
    Onceki bicim her pozisyon icin butun seri uzerinde maske kuruyordu (bar basina O(n)); sonuc ve hata yolu ayni:
    secilen high'lar sirayla denetlenir, ilk bozuk degerde ayni mesajla `VeriHatasi`."""
    adim = pencere_modulu.ADIM_4H
    alt = max(int(zamanlar.searchsorted(pencere_modulu.ayni_an_basi(plan.giris), side="right")),
              int(zamanlar.searchsorted(pencere_modulu.ayni_an_basi(plan.donem_baslangic), side="right")))
    ust = min(int(zamanlar.searchsorted(pencere_modulu.ayni_an_sonu(plan.cikis_ani) - adim, side="left")),
              int(zamanlar.searchsorted(pencere_modulu.ayni_an_sonu(plan.donem_bitis), side="left")))
    tepe = p1
    if ust > alt:
        yuksekler = mumlar_4h["high"].to_numpy(dtype=float)[alt:ust]
        bozuk = ~np.isfinite(yuksekler) | (yuksekler <= 0) | (yuksekler < sys.float_info.min)
        if bozuk.any():
            _pozitif_fiyat(float(yuksekler[int(np.nonzero(bozuk)[0][0])]), "pozisyon penceresindeki high")
        tepe = max(float(np.max(yuksekler)), p1)
    return tepe


def _rol_dogrula(rol) -> str:
    """Bar hangi rolde karar noktasina geliyor (on-kayit §6 rev.11)? Bilinmeyen rol programlama
    hatasidir; `str` alt sinifi da reddedilir (`__eq__` ile yalan soyleyebilir)."""
    if type(rol) is not str:
        raise TypeError(f"rol bir rol adi olmali {ROLLER}; verilen: {rol!r}")
    if rol not in ROLLER:
        raise ValueError(f"Bilinmeyen rol {rol!r}; gecerli: {ROLLER} (on-kayit §6 rev.11 "
                         "'Kontrolun ne olctugu').")
    return rol


def _capa_dogrula(hipotez: str, rol: str, capa):
    """Capa (H1'in pump bari) bu hipotez ve rolde verilmeli mi? (on-kayit §5 H1, §6 rev.11)

    Capa YALNIZCA H1'in olay rolunde verilir: H1'in sinyali bir pump barina capalidir. Kontrol
    rollerinde capa verilemez, cunku "H1'in kontrol barinda pump bari, dip penceresi ve tepe
    aranmaz". H2 ve H3'un butun degerleri t barindan hesaplanir, onlarda capa hicbir rolde
    verilemez. Capa bir deger degil bir BAR ZAMANIDIR ve kapi onu ayrica dogrular: pump kosulu
    capada yeniden hesaplanir (`sinyal.kosullar_saglandi`), yani cagiran uydurma bir capayla
    olay uretemez.
    """
    capali = hipotez in sinyal_modulu.CAPALI_HIPOTEZLER and rol == "olay"
    if capali:
        if capa is None:
            raise TypeError(f"{hipotez} olay rolunde capa (pump bari) zorunludur (on-kayit §5 H1).")
        return pencere_modulu.utc_zamani(capa, "capa")
    if capa is not None:
        raise TypeError(f"{hipotez} / rol {rol} icin capa verilemez (on-kayit §6 rev.11: kontrol "
                        "barinda pump bari aranmaz; H2 ve H3 t barindan hesaplanir).")
    return None


def olay_karari(
    sinyal_zamani,
    ufuk: int,
    bar: str,
    *,
    hipotez: str,
    yapilandirma,
    rol: str,
    capa,
    birincil_ufuk: int,
    kume: str,
    sembol: str,
    donem_no: int,
    asgari_hacim,
    asgari_listeleme_yasi_gun,
) -> OnaylanmisPozisyon:
    """TEK KARAR NOKTASININ bar basina okuyucusu (on-kayit §4 rev.8, rev.9; performans 2b-2, plan v3 G1). Olay ya da
    kontrol olusursa `OnaylanmisPozisyon`, olusmazsa `OlayOlusmaz` alt sinifi (ret gerekcesi: `pencere.ret_gerekcesi`).
    Olaylar ve kontroller ayni cagriyi kullanir.

    INCE SARMALAYICI (P2b-2): karar `kapi_serisi`dedir; bu fonksiyon onun t SATIRINI okur. Bar basina skaler karar
    govdesi `data/`dan kalkti; yalnizca dondurulmus skaler referansta yasar. Imza, istisnalar ve
    donus degeri P2b-2 oncesiyle aynidir:
      - Girdi denetimleri (hipotez -> izgara -> ufuk bagi, yapilandirma, rol, capa, birincil ufuk once, UTC sinyal
        zamani, kume adi, onay ve kesif baglami, donem kaydi, grup, uygunluk esikleri) skalerdeki sirayla burada yapilir.
      - Once t'nin birimi icin seri kurulur (ya da onbellekten okunur). Seri kurulumu `OlayOlusmaz` disi bir hatayla
        durursa hata OLDUGU GIBI yukari cikar (G10: seri hatasi birimi durdurur; F1-K1, denetci D-B1 ve D-C7). Bar tek
        basina yeniden hesaplanmaz: bu, birimin butun barlarinda ayni hatayi verir ve gercek veri esitliginde birim
        hatasi olarak gorunur (`esitlik_kapi.karsilastir`).
      - t serinin bir satiriysa (hipotez izgarasinin bari; H1 olay rolunde capanin izleme penceresinde) satir
        ONBELLEKTEKI seriden okunur.
      - t serinin satiri degilse (izgarada degil, tolerans payiyla verilmis, ya da H1'de capanin izleme penceresi
        disinda) ayni karar cekirdegi (`_kapi_satirlari`) YALNIZCA t icin kosar; bu yol yalnizca seri BASARIYLA
        kurulduktan sonra calisir. Ikinci bir karar yolu yoktur: karar ayni fonksiyondan gelir; tek fark sorulan bar
        kumesidir.

    Fiyat, funding ve 1d cerceveleri cagirandan alinmaz: kapi `sembol` ve `kume` ile yukler. `yapilandirma`: hipotezin
    izgarasindaki bir parametre demeti. `rol`: "olay", "K1" ya da "K2". `capa`: yalnizca H1'in olay rolunde pump bari,
    baska her durumda `None` (`_capa_dogrula`). `asgari_hacim`, `asgari_listeleme_yasi_gun`: on-kayit §2 degerleri
    olmalidir (`eligibility.esikleri_dogrula`). `kume`: kumenin ADI; sinirlari kapi okur. `sembol`, `donem_no`: evren
    tablosundaki listeleme donemi; sembolun A/B grubu kumenin gruplarindan biri olmalidir (`grup_dogrula`).
    """
    # Hipotez -> izgara -> ufuk bagi (on-kayit §4 "Ufuk degerlerinin baglanmasi", rev.10; F1 kapanis turu, D-B2).
    pencere_modulu.hipotez_baglamini_dogrula(hipotez, bar, ufuk, birincil_ufuk)
    # Yapilandirma ve rol (on-kayit §5, §6 rev.11).
    gecerli_yapilandirma = sinyal_modulu.yapilandirma_dogrula(hipotez, yapilandirma)
    yapilandirma_kimligi = sinyal_modulu.yapilandirma_kimligi(hipotez, gecerli_yapilandirma)
    rol = _rol_dogrula(rol)
    capa = _capa_dogrula(hipotez, rol, capa)
    # Olayin olusup olusmadigi BIRINCIL ufukta belirlenir (kapi sertlestirme turu 3, KS2 D-B3): ikincil ufuk istenirse
    # once birincil ufuk sorulur; orada olay olusmazsa ayni ret gerekcesi yukari cikar.
    if ufuk != birincil_ufuk:
        olay_karari(sinyal_zamani, birincil_ufuk, bar, hipotez=hipotez, yapilandirma=gecerli_yapilandirma,
                    rol=rol, capa=capa, birincil_ufuk=birincil_ufuk, kume=kume, sembol=sembol,
                    donem_no=donem_no, asgari_hacim=asgari_hacim,
                    asgari_listeleme_yasi_gun=asgari_listeleme_yasi_gun)
    sinyal_zamani = _utc_sinyal_zamani(sinyal_zamani)
    # Kume ve donem sinirlari cagirandan alinmaz; baglam ve grup denetimleri skalerdeki sirayla (F1K2 D-B1, D-B2;
    # KS2 D-B1; RESULTS §14.42).
    kume_sinirlari(kume)
    split_modulu.onay_baglami_dogrula(hipotez, kume, yapilandirma_kimligi)
    split_modulu.kesif_baglami_dogrula(kume)
    donem_kaydi(sembol, donem_no)
    grup_dogrula(sembol, kume)
    # Uygunluk girdileri her cagrida denetlenir (programlama hatasi, ret gerekcesi degil). Esikler on-kayit degerleri
    # oldugu icin seri ayni esiklerle kurulur (`eligibility.hacim_esigi`, `config.ASGARI_LISTELEME_YASI_GUN`).
    eligibility_modulu.esikleri_dogrula(bar, asgari_hacim=asgari_hacim,
                                        asgari_listeleme_yasi_gun=asgari_listeleme_yasi_gun)
    ikincil = None if ufuk == birincil_ufuk else int(ufuk)
    # G10 (F1-K1, denetci D-B1): seri kurulumunun hatasi yakalanmaz; birimi durdurur ve oldugu gibi yukari cikar.
    seri = kapi_serisi(hipotez, gecerli_yapilandirma, rol, kume=kume, sembol=sembol, donem_no=donem_no,
                       capa=capa, ufuk=ikincil)
    if seri.icerir(sinyal_zamani):
        return seri.sonuc(sinyal_zamani)
    baglam = _kapi_baglami(hipotez, gecerli_yapilandirma, rol, kume=kume, sembol=sembol, donem_no=donem_no,
                           ufuk=ikincil)
    sonuc = _kapi_satirlari(baglam, pd.DatetimeIndex([sinyal_zamani]), None if capa is None else [capa])[0]
    return _sonucu_ver(sonuc)


def _test_onayi(*, hipotez: str, yapilandirma, t, rol: str = "olay", capa=None,
                sembol: str = "TESTONAYUSDT", kume: str = "KESIF", donem_no: int = 0) -> OnaylanmisPozisyon:
    """YALNIZCA TESTLER ICIN: veri yuklemeden imzali bir `OnaylanmisPozisyon` kurar.

    Neden var: `data.dizi` rev.13'ten beri `karar`in dondurdugu nesnenin gercekten kapidan gecmis,
    imzali, "olay" rolunde ve SORULAN (t, capa) ciftine ait bir onay oldugunu dogrular (sizinti
    bulgusu S-B1). Dizi KURALLARINI (bekleme, tek izleme, ilk gun) sinayan testler onlarca bar
    uzerinde kosar ve her bar icin gercek kapiyi cagirmak hem cok yavas olur hem de testin sinadigi
    seyi (dizi kurallarini) sentetik bir dunya kurmanin ayrintilarina gomer. Bu fonksiyon o testlere
    gecerli bir onay verir; plan `pencere.pozisyon_plani`nin kendisinden gecer, fiyat ve funding
    degerleri yer tutucudur (1.0, 1.0, 0.0) ve hicbir getiri hesabinda kullanilmaz.

    KORUMA (denetci bulgusu D-C2 ile tamamlandi). Dort katman:
      1. Yalnizca bir pytest testi icinde cagrilabilir (`split._pytest_testi`); dislarda
         `RuntimeError`.
      2. Urettigi nesnenin OMRU o testle sinirlidir: baska bir testte `onay_dogrula` reddeder
         (`_TEST_ONAY_OMURLERI`). Oncesinde nesne ayni oturumdaki her testte gecerliydi.
      3. C1/C2 icin acik bir ONAY KOSUSU sarttir (`split.onay_baglami_dogrula`): "C1/C2 pozisyonu
         yalnizca acik onay kosusu icinde olusur" degismezi pytest icinde de delinemez
         (CLAUDE.md §3.3, on-kayit §3). Gercek kosuda dikis zaten kapalidir; buradaki amac tek
         atis guvencesinin test baglaminda da gecerli kalmasidir.
      4. Adi analiz kodunda gecemez: `tests/tarama_yardimcisi.ONAY_ATLATMA_DESENI` tarafindan
         taranir.
    Kilit, dikkatsiz bir kullanima karsi korur, kararli bir atlatmaya karsi degil (CLAUDE.md
    "Koruma katmani" ile ayni tutum).
    """
    if split_modulu._pytest_testi() is None:
        raise RuntimeError("_test_onayi yalnizca bir pytest testi icinde kullanilabilir; gercek onay "
                           "`pozisyon.olay_karari`dan gelir (on-kayit §4 'tek karar noktasi').")
    tanim = pencere_modulu.hipotez_baglamini_dogrula(hipotez, config.HIPOTEZ_IZGARASI[hipotez],
                                                     config.BIRINCIL_UFUK[config.HIPOTEZ_IZGARASI[hipotez]],
                                                     config.BIRINCIL_UFUK[config.HIPOTEZ_IZGARASI[hipotez]])
    gecerli = sinyal_modulu.yapilandirma_dogrula(hipotez, yapilandirma)
    rol = _rol_dogrula(rol)
    zaman = _utc_sinyal_zamani(t)
    adim = pencere_modulu.adim(config.BAR_4H)
    kume_baslangic, kume_bitis = kume_sinirlari(kume)
    # Donem, t'nin etrafinda birincil ufku ve gunun tamamini kapsayacak kadar genis.
    bas = (zaman - pd.Timedelta(days=2)).floor("D")
    son = (zaman + pd.Timedelta(days=2) + tanim.birincil * pencere_modulu.adim(tanim.bar)).ceil("D") - adim
    zamanlar = pd.date_range(bas, son, freq=adim)
    plan = pencere_modulu.pozisyon_plani(
        zamanlar, zaman, tanim.birincil, tanim.bar, birincil_ufuk=tanim.birincil,
        kume_baslangic=kume_baslangic, kume_bitis=kume_bitis, donem_baslangic=bas, donem_bitis=son)
    yapilandirma_kimligi = sinyal_modulu.yapilandirma_kimligi(hipotez, gecerli)
    # Onay kumesi icin acik kosu sarti: gercek kapidaki denetimin aynisi (kapi sertlestirme turu 3).
    split_modulu.onay_baglami_dogrula(hipotez, kume, yapilandirma_kimligi)
    sonuc = OnaylanmisPozisyon(
        plan, 1.0, 1.0, 0.0, hipotez=hipotez,
        yapilandirma=yapilandirma_kimligi, rol=rol,
        capa=None if capa is None else _utc_sinyal_zamani(capa), sembol=sembol, kume=kume,
        donem_no=int(donem_no))
    imzali = replace(sonuc, _imza=_imza(sonuc))
    _TEST_ONAY_OMURLERI[imzali._imza] = split_modulu._pytest_testi()
    return imzali


def sinyal_kosulu(t, *, hipotez: str, yapilandirma, capa, kume: str, sembol: str, donem_no: int):
    """Hipotezin §5'teki sinyal kosullari t barinda saglandi mi? `True` / `False` / `None`.

    `None` = deger hesaplanamadi (on-kayit §2 "Tamlik sarti"). Bu fonksiyon `data.dizi`nin
    `kosul` argumanidir: olay dizisi kurallari (bekleme suresi, H1'de tek izleme, H3'te "ilk
    gun"; on-kayit §5 rev.11) bar bar bunu sorar, sonra kapiyi (`olay_karari`) cagirir.

    Veri kapiyla AYNI yoldan yuklenir (`_kume_verisi`, `klines.gunluge_cevir`); sinirlar kume
    adindan ve evren tablosundan okunur, cagiran sinir vermez. Degerler `data.sinyal`in pencere
    kuruculariyla hesaplanir.

    H1 iki adimlidir (on-kayit §5 H1): `capa=None` cagrisi madde 1'in PUMP kosulunu sorar
    (`sinyal.h1_pump_saglandi`), `capa=p` cagrisi p capali madde 3'un TEYIT kosulunu sorar.
    H2 ve H3'te `capa` her zaman `None`'dir.

    Bu fonksiyon KARAR VERMEZ: uygunluk, dönem üyeliği, plan ve funding tamligi yalnizca
    `olay_karari`dadir (on-kayit §4 "tek karar noktasi"). Getiri hesaplamaz, deger raporlamaz.
    """
    bar = pencere_modulu.hipotez_izgarasi(hipotez)
    gecerli = sinyal_modulu.yapilandirma_dogrula(hipotez, yapilandirma)
    zaman = _utc_sinyal_zamani(t)
    kume_baslangic, kume_bitis = kume_sinirlari(kume)
    split_modulu.onay_baglami_dogrula(hipotez, kume, sinyal_modulu.yapilandirma_kimligi(hipotez, gecerli))
    split_modulu.kesif_baglami_dogrula(kume)  # RESULTS §14.42, denetci D-C1
    donem_baslangic, donem_bitis, _ = donem_kaydi(sembol, donem_no)
    grup_dogrula(sembol, kume)
    # Veri kume araligina VE DONEME kesilir (bulgu K-B1; on-kayit §2 "Listeleme donemi": "Donem
    # disindaki hiçbir bar ... hicbir hesaba girmez"). Rev.13'te yalnizca kume araligina
    # kesiliyordu: donem bitisinden SONRAKI bir t icin kosul hesaplanabiliyor ve penceresi
    # donemler arasi barlari (dolgu barlari, sonraki donemin barlari) icerebiliyordu. Sonucu
    # olay kumesini de etkiler, cunku dizi durumu (H1 izlemesi, H3 dizisi) kosulun sonucuna
    # gore degisir -- kapinin onayina degil (rev.13: "dizi kosullarla tanimlidir").
    #
    # Kesim KAPIYLA AYNI fonksiyondan gelir (`_karar_verisi`; P-C1): kural iki ayri mekanizmada
    # degil tek yerde durur.
    mumlar_4h, funding, gunluk_mumlar = _karar_verisi(
        sembol, kume, kume_baslangic=kume_baslangic, kume_bitis=kume_bitis,
        donem_baslangic=donem_baslangic, donem_bitis=donem_bitis)
    _mum_zamanlari(mumlar_4h)
    sinir = {"kume_baslangic": kume_baslangic, "donem_baslangic": donem_baslangic}

    if hipotez in sinyal_modulu.CAPALI_HIPOTEZLER and capa is None:
        degerler = sinyal_modulu.h1_pump_degerleri(mumlar_4h, zaman, **sinir)
        return sinyal_modulu.h1_pump_saglandi(gecerli, degerler)

    try:
        degerler = sinyal_modulu.sinyal_degerleri(
            hipotez, gecerli, zaman, mumlar_4h=mumlar_4h, gunluk=gunluk_mumlar, funding=funding,
            capa=capa, kume_bitis=kume_bitis, **sinir)
    except sinyal_modulu.TepePenceresiKurulamaz:
        # Tepe penceresi bu (pump, teyit) cifti icin TANIMSIZ (ör. teyit bari pump barindan 12
        # bardan uzak): izleme kurallari bu bari teyit adayi saymaz; kosul hesaplanamaz.
        #
        # Yakalama rev.13'te daraltildi (denetci bulgusu D-C2): eskiden `except ValueError` idi ve
        # `pencere.VeriHatasi` ile `ZamanDizisiHatasi` da (ikisi de `ValueError` alt sinifi) bu
        # yoldan sessizce "kosul hesaplanamaz" oluyordu. Veri hatasi bir ret gerekcesi DEGILDIR:
        # `pencere.OlayOlusmaz` ailesinden ayridir ve yukari cikmalidir (`pencere.VeriHatasi`
        # aciklamasi; `sinyal._pozitif` ile ayni tutum).
        return None
    if sinyal_modulu.hesaplanamayan(hipotez, degerler):
        return None
    return sinyal_modulu.kosullar_saglandi(hipotez, gecerli, degerler)


def hipotez_izgarasi_barlari(hipotez: str, *, kume: str, sembol: str, donem_no: int) -> pd.DatetimeIndex:
    """Hipotezin sinyal izgarasi: (sembol, donem, kume) icin kapinin GORDUGU sinyal barlarinin acilislari (RESULTS
    §14.47). F2 kosucusu ve esitlik betigi sinyal izgarasini YALNIZCA buradan alir; takvimden izgara kurulmaz.

    Yeni kural YOKTUR: seri kapinin veri yolundan (`_karar_verisi`) okunur; erisim denetimi, kume ve donem kesimi,
    bar duzeyli mevcutluk ve 1d turetmesi `olay_karari` ile `sinyal_kosulu`nun kullandigi ayni yerden gelir.

    SOZLESME: izgara YALNIZCA MEVCUT barlari icerir -- satiri bulunan ve fiyat/hacim hucrelerinin tamami sayi olan bar
    (on-kayit §2 satir 40, rev.11/rev.12 bar duzeyli mevcutluk). Donem ici BOSLUKLAR (satiri olmayan ya da hucresi
    bozuk 4h barlar; 1d'de boyle bir bari iceren gunler) izgarada YER ALMAZ. Izgara bu yuzden esit aralikli degildir:
    ardisik iki elemanin farki 4 saatten (1d'de 1 gunden) buyuk olabilir. Sure olcen her kural (bekleme, H1 izleme
    penceresi, ufuklar) izgara ZAMANIYLA olcer, bu listedeki SIRA ile degil (RESULTS §14.47, P2c gereksinimi).
    Kapi seride olmayan bir bari olagan ret ile reddeder (`SinyalBariYok`, `OlayOlusmaz`); izgara onu hic sormaz.
      - 4h (H1, H2): donem ∩ kume icindeki mevcut, hucresi tam 4h barlarin acilislari (donem basi ile B arasinda,
        iki uc dahil).
      - 1d (H3): turetilmis 1d serisinin (`klines.gunluge_cevir`) acilislari. On-kayit §2 "1 gunluk barlar" (satir
        40): "dönemin kısmi ilk ve son günleri 1d serisinde yer almaz. Bu seri tektir". Yarim ilk ve son gunler ve
        alti barindan biri eksik gunler bu yuzden izgarada yoktur. Takvim izgarasi bu gunleri kapiya verir ve kapi
        onlari programlama hatasi (`pencere.DonemDisiSinyal`) ya da `SinyalBariYok` ile reddeder (§14.46, §14.47).
    Izgaradaki her bar `pencere.donem_ici_mi(t, bar, ...)` icin True'dur ve kapinin `SinyalBariYok` denetimini
    (sinyal bari donem ici seride) gecer. Izgara olay ya da kontrol ADAYIDIR, karar degildir: uygunluk, sinyal
    tamligi, plan, funding tamligi (funding'i bulunmayan donemler dahil) ve dizi kurallari karar noktasinda kalir.

    Baglam karar noktasiyla aynidir: kume sinirlari kume ADINDAN, donem sinirlari evren tablosundan okunur (cagiran
    sinir vermez); C1/C2 icin ayni (hipotez, kume) ciftinin acik onay kosusu, KESIF icin acik kesif kosusu gerekir;
    sembolun grubu kumeye ait olmalidir. Getiri hesaplamaz, deger dondurmez: yalnizca zaman damgasi.
    """
    bar = pencere_modulu.hipotez_izgarasi(hipotez)
    kume_baslangic, kume_bitis = kume_sinirlari(kume)
    split_modulu.onay_baglami_dogrula(hipotez, kume)
    split_modulu.kesif_baglami_dogrula(kume)
    donem_baslangic, donem_bitis, _ = donem_kaydi(sembol, donem_no)
    grup_dogrula(sembol, kume)
    mumlar_4h, _, gunluk_mumlar = _karar_verisi(
        sembol, kume, kume_baslangic=kume_baslangic, kume_bitis=kume_bitis,
        donem_baslangic=donem_baslangic, donem_bitis=donem_bitis)
    if bar == config.BAR_4H:
        zamanlar = _mum_zamanlari(mumlar_4h)
    else:
        zamanlar = pencere_modulu._zaman_dizisi_dogrula(pd.DatetimeIndex(gunluk_mumlar["open_time"]),
                                                       "hipotez_izgarasi_barlari (1d)")
    return pd.DatetimeIndex(zamanlar, name=None, copy=True)


# =====================================================================================================================
# TEK SERI KAPI (performans 2b-2; plan v3 G1, G8, G9, G10, G11, G13, G19, G20; RESULTS §14.49)
# =====================================================================================================================
#
# `kapi_serisi` olay, K1 ve K2 rollerine (H1'in capali olay rolu dahil) AYNI cekirdekle (`_kapi_satirlari`) karar verir.
# Bar basina skaler karar govdesi `data/`da yoktur; `olay_karari` bu serinin t satirini okuyan ince sarmalayicidir.
#
# Cekirdegin adimlari skalerin sirasiyla (G19): sinyal bari (plan + t barinin varligi) -> capasiz / sinyal tamligi ->
# kosul (yalnizca olay rolunde; G8) -> uygunluk -> funding'siz donem -> funding tamligi -> fiyat (P0, P1, MAE). Her bar
# ILK basarisiz adiminin ret sinifini ve mesajini (skalerle birebir) tasir; sonraki adimlar o bar icin hesaplanmaz.
#   - Pencereler, hesaplanabilirlik ve uygunluk `data.seri_kurucu`dan (G3, G6, G7; bit duzeyinde skalerle ayni).
#   - Plan skaler `pencere.pozisyon_plani` ile, bar basina, P2a'nin plan onbellegiyle (`_PlanSerisi`; vektorlestirilmez).
#   - Funding tamligi ve toplami P2a'nin TOPLU yolundan (`funding._planlar_tamlik_satirlari`, `_satirdan_toplam`).
#   - Kosul (olay rolu): seri degerleri ve yapilandirmanin esiklerinden vektorel (`_kosul_dizisi`). G1 gecici istisnasi:
#     skaler `sinyal_kosulu` dizi kurallari icin P2c'ye kadar kalir; ikisinin esitligi gercek veride ayrica sinanir (G14).
#   - G10: `OlayOlusmaz` disindaki her istisna (`VeriHatasi` dahil) seri kurulumunu DURDURUR; hicbir zaman ret koduna
#     ya da 0 bitine donusmez.
#
# Cikti `KapiSerisi`: imzali, degistirilemez; verisi yalnizca okuma yontemlerinden verilir ve her okuma erisim
# denetimini (onay ve kesif baglami, grup, kume erisimi, donem isareti, satir imzasi) yeniden calistirir (G11).

_SERI_GIZLI = object()
SERI_AZAMI_GIRDI = 32
_SERI_BELLEGI: OrderedDict = OrderedDict()
_SERI_HATALARI: OrderedDict = OrderedDict()     # hata veren kurulumlar (F1-K1, D-B1): ayni anahtar yeniden kurulmaz
_SERI_KILIDI = threading.Lock()


class SeriEskidi(RuntimeError):
    """Seri kuruldugu donem isaretinden SONRA okunmak istendi (kesif ya da onay kosusu acildi veya kapandi; G11).
    Programlama hatasidir: seri yeniden kurulmalidir."""


class KontrolAdayiHatasi(RuntimeError):
    """Ornekleme adayinin (biti 1 olan K2/K1 bari) onayli pozisyonu kurulamadi (G9): SERT hatadir, yeniden cekim
    yapilmaz."""


@dataclass(frozen=True)
class _KapiBaglami:
    """Bir seri biriminin kimligi ve kapinin kurulum denetimlerinden gecmis girdileri (cagiran sinir vermez)."""

    hipotez: str
    yapilandirma: MappingProxyType
    yapilandirma_kimligi: str
    rol: str
    bar: str
    ufuk: int
    birincil_ufuk: int
    kume: str
    kume_baslangic: pd.Timestamp
    kume_bitis: pd.Timestamp
    sembol: str
    donem_no: object
    donem_baslangic: pd.Timestamp
    donem_bitis: pd.Timestamp
    donem_funding_yok: bool

    @property
    def onay(self) -> bool:
        return self.kume in config.ONAY_KUMELERI


def _kapi_baglami(hipotez, yapilandirma, rol, *, kume, sembol, donem_no, ufuk=None) -> _KapiBaglami:
    """Kurulum denetimleri, skalerdeki sirayla: hipotez -> izgara -> ufuk bagi, yapilandirma, rol, kume adi, onay ve
    kesif baglami, donem kaydi, grup uyeligi (G9, G11). `ufuk` None ise birincil ufuk."""
    tanim = pencere_modulu.hipotez_ufuklari(hipotez)
    ufuk_degeri = tanim.birincil if ufuk is None else ufuk
    pencere_modulu.hipotez_baglamini_dogrula(hipotez, tanim.bar, ufuk_degeri, tanim.birincil)
    gecerli = sinyal_modulu.yapilandirma_dogrula(hipotez, yapilandirma)
    kimlik = sinyal_modulu.yapilandirma_kimligi(hipotez, gecerli)
    rol = _rol_dogrula(rol)
    kume_baslangic, kume_bitis = kume_sinirlari(kume)
    split_modulu.onay_baglami_dogrula(hipotez, kume, kimlik)
    split_modulu.kesif_baglami_dogrula(kume)
    donem_baslangic, donem_bitis, donem_funding_yok = donem_kaydi(sembol, donem_no)
    grup_dogrula(sembol, kume)
    return _KapiBaglami(hipotez, gecerli, kimlik, rol, tanim.bar, int(ufuk_degeri), int(tanim.birincil), kume,
                        kume_baslangic, kume_bitis, sembol, donem_no, donem_baslangic, donem_bitis,
                        bool(donem_funding_yok))


def _ret(hata: pencere_modulu.OlayOlusmaz) -> tuple:
    """Ret satiri: (isaret, sinif, argumanlar). Okumada AYNI sinif ve AYNI mesajla yeni bir nesne kurulur."""
    return ("ret", type(hata), hata.args)


def _sonucu_ver(sonuc):
    """Satirin sonucu: onayli pozisyon doner ya da ret yukseltilir (yeni nesne, ayni sinif ve mesaj)."""
    if isinstance(sonuc, OnaylanmisPozisyon):
        return sonuc
    _, sinif, argumanlar = sonuc
    raise sinif(*argumanlar)


def _sonlu_dizi(d) -> np.ndarray:
    return np.isfinite(np.asarray(d, dtype=float))


# --- Olay rolunun sinyal degerleri ve vektorel kosul -----------------------------------------------------------------

def _olay_degerleri(b: _KapiBaglami, z: pd.DatetimeIndex, capalar, m4, gunluk, funding) -> dict[str, np.ndarray]:
    """Olay rolunun `sinyal.DEGER_ADLARI` degerleri, `z`nin her bari icin (seri kuruculari; skalerle bit duzeyinde ayni).
    H1'de `capalar` bar basina pump bari (ayni uzunlukta); tepe penceresinin bar sayisi once skalerin TEK kuraliyla
    (`sinyal.h1_tepe_bar_sayisi`) denetlenir: tanimsiz teyit skalerle ayni sinif ve mesajla `TepePenceresiKurulamaz`."""
    sinir = {"kume_baslangic": b.kume_baslangic, "donem_baslangic": b.donem_baslangic}
    if b.hipotez == "H1":
        c = pd.DatetimeIndex(capalar)
        for pump, teyit in zip(c, z):
            sinyal_modulu.h1_tepe_bar_sayisi(pump, teyit)
        essiz = c.unique().sort_values()
        sira = essiz.get_indexer(c)
        return {
            "pump_dip": seri_kurucu_modulu.h1_dip(m4, essiz, **sinir)[sira],
            "pump_hacim_6": seri_kurucu_modulu.h1_hacim_6(m4, essiz, **sinir)[sira],
            "pump_hacim_medyani_180": seri_kurucu_modulu.h1_hacim_medyani_180(m4, essiz, **sinir)[sira],
            "tepe": seri_kurucu_modulu.h1_tepe(m4, c, z, **sinir),
            "pump_kapanis": seri_kurucu_modulu.kapanis(m4, essiz, config.BAR_4H)[sira],
            "kapanis": seri_kurucu_modulu.kapanis(m4, z, config.BAR_4H),
            "yuksek": seri_kurucu_modulu.yuksek(m4, z, config.BAR_4H),
        }
    if b.hipotez == "H2":
        return {
            "funding_24s": seri_kurucu_modulu.h2_funding_24s(funding, z, kume_baslangic=b.kume_baslangic,
                                                             kume_bitis=b.kume_bitis,
                                                             donem_baslangic=b.donem_baslangic),
            "kapanis_30_once": seri_kurucu_modulu.kapanis_30_once(m4, z, config.BAR_4H, **sinir),
            "kirilim_dip": seri_kurucu_modulu.h2_kirilim_dip(m4, z, b.yapilandirma["k"], **sinir),
            "kapanis": seri_kurucu_modulu.kapanis(m4, z, config.BAR_4H),
        }
    return {
        "hacim_medyani_30g": seri_kurucu_modulu.h3_hacim_medyani_30g(gunluk, z, **sinir),
        "hacim_medyani_120_31": seri_kurucu_modulu.h3_hacim_medyani_120_31(gunluk, z, **sinir),
        "sma50": seri_kurucu_modulu.h3_sma50(gunluk, z, **sinir),
        "kapanis_30_once": seri_kurucu_modulu.kapanis_30_once(gunluk, z, config.BAR_1D, **sinir),
        "kapanis": seri_kurucu_modulu.kapanis(gunluk, z, config.BAR_1D),
    }


def _kosul_dizisi(hipotez: str, yapilandirma, degerler: dict[str, np.ndarray]) -> np.ndarray:
    """Hipotezin §5 kosullari, her bar icin (VEKTOREL KOSUL; skaler `sinyal.kosullar_saglandi` ile ayni esitsizlikler,
    ayni esik yonleri, ayni sabitler). Degerlerin TAMAMI sonlu olmali (cagiran tam barlari verir). Once FIYAT degerleri
    sinanir: sifir, negatif ya da altnormal bir fiyat skalerin tek fonksiyonuyla (`sinyal._pozitif`, ayni ad ve mesaj)
    `VeriHatasi` verir (G10: seri durur). Elemanter islemler (bolme, carpma, karsilastirma) IEEE 754 cift duyarlikta
    Python float'iyla bit duzeyinde aynidir; skaler sabitler (`1 - δ` gibi) once Python float'i olarak kurulur."""
    d = {a: np.asarray(degerler[a], dtype=float) for a in sinyal_modulu.DEGER_ADLARI[hipotez]}
    n = len(next(iter(d.values()))) if d else 0
    if n:
        bozuk = np.zeros(n, dtype=bool)
        for a in sinyal_modulu.FIYAT_DEGERLERI[hipotez]:
            bozuk |= (d[a] <= 0) | (d[a] < sys.float_info.min)
        if bozuk.any():
            j = int(np.nonzero(bozuk)[0][0])
            for a in sinyal_modulu.FIYAT_DEGERLERI[hipotez]:
                sinyal_modulu._pozitif(float(d[a][j]), f"{hipotez} sinyal degeri {a}")
    y = yapilandirma
    if hipotez == "H1":
        teta = float(y["theta"])
        delta_carpani = 1 - float(y["delta"])
        pump = (d["pump_kapanis"] / d["pump_dip"] - 1 >= teta) \
            & (d["pump_hacim_6"] >= config.H1_HACIM_CARPANI * d["pump_hacim_medyani_180"])
        teyit = (d["kapanis"] <= d["tepe"] * delta_carpani) & (d["yuksek"] < d["tepe"])
        return np.asarray(pump & teyit, dtype=bool)
    if hipotez == "H2":
        return np.asarray((d["funding_24s"] >= float(y["phi"]))
                          & (d["kapanis"] / d["kapanis_30_once"] - 1 >= config.H2_YUKSELIS_ESIGI)
                          & (d["kapanis"] < d["kirilim_dip"]), dtype=bool)
    nu_carpani = 1 - float(y["nu"])
    eksi_tau = -float(y["tau"])
    return np.asarray((d["hacim_medyani_30g"] <= nu_carpani * d["hacim_medyani_120_31"])
                      & (d["kapanis"] < d["sma50"])
                      & (d["kapanis"] / d["kapanis_30_once"] - 1 <= eksi_tau), dtype=bool)


def _gecersizlik_tabani(b: _KapiBaglami, z: pd.DatetimeIndex, degerler: dict, secim: np.ndarray, m4, gunluk) -> np.ndarray:
    """Gecersizlik seviyesinin tabani (skaler `sinyal.gecersizlik_seviyesi`): H1'de tepe (ayni pencere), H2'de 4h,
    H3'te 1d `max(high[t-30..t])`."""
    if b.hipotez == "H1":
        return np.asarray(degerler["tepe"], dtype=float)[secim]
    sinir = {"kume_baslangic": b.kume_baslangic, "donem_baslangic": b.donem_baslangic}
    cerceve = m4 if b.hipotez == "H2" else gunluk
    return seri_kurucu_modulu.yuksek_30_max(cerceve, z[secim], b.bar, **sinir)


# --- Karar cekirdegi -----------------------------------------------------------------------------------------------

def _kapi_satirlari(b: _KapiBaglami, sorgu: pd.DatetimeIndex, capalar=None) -> list:
    """TEK KARAR CEKIRDEGI: `sorgu`nun her bari icin onayli pozisyon ya da ret satiri (`_ret`). `OlayOlusmaz` disindaki
    her istisna yukari cikar (G10). `sorgu` UTC, kesin artan; `capalar` yalnizca H1 olay rolunde, `sorgu` ile ayni
    uzunlukta pump barlari. Veri kapinin tek veri yolundan (`_karar_girdisi`); cagiran cerceve vermez."""
    mumlar_4h, funding, gunluk_mumlar, plan_serisi = _karar_girdisi(
        b.sembol, b.kume, kume_baslangic=b.kume_baslangic, kume_bitis=b.kume_bitis,
        donem_baslangic=b.donem_baslangic, donem_bitis=b.donem_bitis)
    zamanlar = _mum_zamanlari(mumlar_4h)
    _gunluk_hacim(gunluk_mumlar)
    gunluk_acilis = pd.DatetimeIndex(gunluk_mumlar["open_time"])
    sorgu = pd.DatetimeIndex(sorgu)
    n = len(sorgu)
    sonuc: list = [None] * n
    planlar: list = [None] * n
    capali = b.hipotez in sinyal_modulu.CAPALI_HIPOTEZLER and b.rol == "olay"
    if capali and (capalar is None or len(capalar) != n):
        raise TypeError(f"{b.hipotez} olay rolunde her sorgu bari icin bir capa (pump bari) zorunludur (on-kayit §5 H1).")

    # 1. Sinyal bari: plan (P2a plan onbellegi) ve t barinin donem ici seride varligi (KS D-B3).
    seri_t = zamanlar if b.bar == config.BAR_4H else gunluk_acilis
    for i, t in enumerate(sorgu):
        try:
            plan = plan_serisi.al(
                (b.bar, b.ufuk, b.birincil_ufuk, t),
                lambda: pencere_modulu.pozisyon_plani(
                    zamanlar, t, b.ufuk, b.bar, birincil_ufuk=b.birincil_ufuk, kume_baslangic=b.kume_baslangic,
                    kume_bitis=b.kume_bitis, donem_baslangic=b.donem_baslangic, donem_bitis=b.donem_bitis))
        except pencere_modulu.OlayOlusmaz as hata:
            sonuc[i] = _ret(hata)
            continue
        # Plan onbellegi anahtar-plan tutarliligi (sizinti S-19; RESULTS §14.49): onbellekten donen imzali plan SORULAN
        # anahtara ait olmali. Degilse programlama hatasidir (G10: seri durur); baska bir barin plani t'nin karari
        # olarak donemez.
        if (plan.sinyal_zamani != t or plan.bar != b.bar or plan.ufuk != b.ufuk or plan.birincil_ufuk != b.birincil_ufuk
                or plan.kume_baslangic != b.kume_baslangic or plan.kume_bitis != b.kume_bitis
                or plan.donem_baslangic != b.donem_baslangic or plan.donem_bitis != b.donem_bitis):
            raise ValueError(f"Plan onbellegi tutarsiz: {t} anahtarina baska bir plan ({plan.sinyal_zamani}, ufuk "
                             f"{plan.ufuk}) kayitli (sizinti S-19).")
        if pencere_modulu.ayni_andaki_bar(seri_t, plan.sinyal_zamani) is None:
            sonuc[i] = _ret(SinyalBariYok(f"{b.sembol}: sinyal bari {plan.sinyal_zamani} ({b.bar}) donem ici seride "
                                          "yok; olay ya da kontrol olusmaz."))
            continue
        planlar[i] = plan

    def kalan() -> np.ndarray:
        return np.asarray([i for i in range(n) if sonuc[i] is None], dtype=np.int64)

    gecersizlik = np.full(n, np.nan)
    # 2-3. Sinyal pencereleri. Kontrol rolu: yalnizca capasiz pencerelerin hesaplanabilirligi (on-kayit §6 rev.12);
    # KOSUL HESAPLANMAZ (G8). Olay rolu: butun degerlerin tamligi, kosul ve gecersizlik seviyesi.
    aktif = kalan()
    if len(aktif):
        z = sorgu[aktif]
        if b.rol in KONTROL_ROLLERI:
            k = b.yapilandirma["k"] if b.hipotez == "H2" else None
            pencereler = seri_kurucu_modulu.capasiz_pencereler(
                b.hipotez, k, z, mumlar_4h=mumlar_4h, gunluk=gunluk_mumlar, funding=funding,
                kume_baslangic=b.kume_baslangic, kume_bitis=b.kume_bitis, donem_baslangic=b.donem_baslangic)
            adlar = sinyal_modulu.CAPASIZ_PENCERELER[b.hipotez]
            sonlu = {a: _sonlu_dizi(pencereler[a]) for a in adlar}
            for j, i in enumerate(aktif):
                eksik = [a for a in adlar if not sonlu[a][j]]
                if eksik:
                    sonuc[i] = _ret(SinyalPenceresiTamDegil(
                        f"Kontrol barinda capasiz sinyal penceresi tam degil: {eksik} (on-kayit §6 "
                        f"rev.12); {planlar[i].sinyal_zamani} barinda kontrol olusmaz."))
        else:
            c = None if not capali else pd.DatetimeIndex([capalar[i] for i in aktif])
            degerler = _olay_degerleri(b, z, c, mumlar_4h, gunluk_mumlar, funding)
            adlar = sinyal_modulu.DEGER_ADLARI[b.hipotez]
            sonlu = {a: _sonlu_dizi(degerler[a]) for a in adlar}
            tam = np.ones(len(aktif), dtype=bool)
            for j, i in enumerate(aktif):
                eksik = [a for a in adlar if not sonlu[a][j]]
                if eksik:
                    tam[j] = False
                    sonuc[i] = _ret(SinyalPenceresiTamDegil(
                        f"Sinyal penceresi tam degil: {eksik} (on-kayit §2 'Tamlik sarti'); "
                        f"{planlar[i].sinyal_zamani} barinda olay olusmaz."))
            kosul = np.zeros(len(aktif), dtype=bool)
            if tam.any():
                kosul[tam] = _kosul_dizisi(b.hipotez, b.yapilandirma, {a: degerler[a][tam] for a in adlar})
            for j, i in enumerate(aktif):
                if tam[j] and not kosul[j]:
                    sonuc[i] = _ret(SinyalKosuluSaglanmadi(
                        f"{b.hipotez} kosullari {planlar[i].sinyal_zamani} barinda saglanmadi (on-kayit §5); olay "
                        "olusmaz."))
            # Gecersizlik seviyesi (on-kayit §5 rev.13; F4 kaydi): kosulu saglayan barlarda; hesaplanamazsa acik hata.
            if kosul.any():
                taban = _gecersizlik_tabani(b, z, degerler, kosul, mumlar_4h, gunluk_mumlar)
                for deger, i in zip(taban, aktif[kosul]):
                    if not math.isfinite(float(deger)):
                        _sonlu(float("nan"), "gecersizlik seviyesi")
                    sinyal_modulu._pozitif(float(deger), f"{b.hipotez} gecersizlik seviyesinin tabani")
                    gecersizlik[i] = _sonlu(float(deger) * config.GECERSIZLIK_CARPANI, "gecersizlik seviyesi")

    # 4. Uygunluk (on-kayit §4 rev.9): esik gecilmeli, hesaplanabilmis olmasi yetmez.
    aktif = kalan()
    if len(aktif):
        tablo = seri_kurucu_modulu.uygunluk(
            gunluk_mumlar, sorgu[aktif], b.bar, donem_baslangic=b.donem_baslangic, donem_bitis=b.donem_bitis,
            kume_baslangic=b.kume_baslangic, asgari_hacim=eligibility_modulu.hacim_esigi(b.bar),
            asgari_listeleme_yasi_gun=config.ASGARI_LISTELEME_YASI_GUN)
        for uygun, i in zip(tablo["uygun"].to_numpy(dtype=bool), aktif):
            if not uygun:
                sonuc[i] = _ret(UygunDegil(f"Sinyal bari {planlar[i].sinyal_zamani} ({b.bar}) uygun degil: listeleme "
                                           "yasi ya da medyan hacim esigi gecilmiyor (on-kayit §2 'Uygunluk')."))

    # 5. Funding'i bulunmayan donem (on-kayit §2): tablodaki bayraktan.
    aktif = kalan()
    if len(aktif) and b.donem_funding_yok:
        for i in aktif:
            sonuc[i] = _ret(FundingTamDegil(f"{b.sembol} donem {b.donem_no}: evren tablosunda funding kaydi yok "
                                            "(on-kayit §2 'Funding'i bulunmayan donemler'); olay ya da kontrol "
                                            "olusmaz."))

    # 6-7. Funding tamligi ve toplami (P2a toplu yolu), fiyatlar ve MAE penceresi.
    aktif = kalan()
    if len(aktif):
        tamliklar = funding_modulu._planlar_tamlik_satirlari(funding, [planlar[i] for i in aktif])
        for tamlik, i in zip(tamliklar, aktif):
            plan = planlar[i]
            ayrinti = tamlik.satir
            if not bool(ayrinti["tam"]):
                sonuc[i] = _ret(FundingTamDegil(f"Pozisyonun funding'i tam degil: giris {plan.giris}, cikis "
                                                f"{plan.cikis_ani} ({plan.cikis_turu}); olay brut dahil hicbir "
                                                "hesapta olusmaz."))
                continue
            toplam = funding_modulu._satirdan_toplam(funding, plan, tamlik)
            if math.isnan(toplam):
                sonuc[i] = _ret(FundingTamDegil(f"Pozisyonun funding'i hesaplanamadi (oran NaN): giris {plan.giris}."))
                continue
            _sonlu(toplam, "funding toplami")
            p0 = _pozitif_fiyat(_bar_degeri(mumlar_4h, zamanlar, plan.giris, "open"), "P0")
            p1 = _pozitif_fiyat(_bar_degeri(mumlar_4h, zamanlar, plan.cikis.zaman, plan.cikis.fiyat_alani), "P1")
            _mae_tepesi(mumlar_4h, zamanlar, plan, p1)
            poz = OnaylanmisPozisyon(plan, p0, p1, toplam, kuyruk_kismi=bool(ayrinti["kuyruk_kismi"]),
                                     son_esitlik_affi=bool(ayrinti["son_esitlik_affi"]),
                                     capa_aralik_saat=float(ayrinti["capa_aralik_saat"]),
                                     son_aralik_saat=float(ayrinti["son_aralik_saat"]),
                                     tek_ritim=bool(ayrinti["tek_ritim"]),
                                     funding_ritmi_saat=float(ayrinti["funding_ritmi_saat"]),
                                     karisik_ritim=bool(ayrinti["karisik_ritim"]),
                                     ritim_sinifi=ayrinti["ritim_sinifi"],
                                     gecersizlik_seviyesi=float(gecersizlik[i]), hipotez=b.hipotez,
                                     yapilandirma=b.yapilandirma_kimligi, rol=b.rol,
                                     capa=capalar[i] if capali else None, sembol=b.sembol,
                                     kume=b.kume, donem_no=int(b.donem_no))
            sonuc[i] = replace(poz, _imza=_imza(poz))
    return sonuc


# --- Seri nesnesi ve onbellek (G11) --------------------------------------------------------------------------------

def _satir_imzasi(kimlik: tuple, isaret: int, zaman_ns: int, sonuc) -> int:
    return hash((_SERI_GIZLI, kimlik, isaret, zaman_ns, sonuc))


class KapiSerisi:
    """`kapi_serisi`nin ciktisi: bir (kume, sembol, donem, hipotez, yapilandirma, rol, capa, bar turu, ufuk, birincil
    ufuk) biriminin satirlari. Satir = barin onayli pozisyonu ya da ret sinifi ve mesaji (skalerle birebir).

    IMZALI VE DEGISTIRILEMEZ (G11): yalnizca `kapi_serisi` kurar (gizli belirtec); her satirin imzasi kimlik, donem
    isareti, zaman ve sonucu baglar. Nitelik atamasi ve silme reddedilir. VERI YALNIZCA OKUMA YONTEMLERINDEN verilir
    (`icerir`, `sonuc`, `pozisyon`, `zamanlar`, `onay_bitleri`) ve her yontem HER CAGRIDA erisim denetimini calistirir:
    onay ve kesif baglami, grup uyeligi, kume erisimi (`split.onay_erisimi_denetle`), donem isareti (kosu acildi ya da
    kapandiysa `SeriEskidi`) ve okunan satirin imzasi. Kilit dikkatsiz bir kullanima karsi korur, kararli bir atlatmaya
    (ör. `object.__setattr__`, gizli belirtece erisim) karsi degil (CLAUDE.md "Koruma katmani" ile ayni tutum)."""

    __slots__ = ("_KapiSerisi__kimlik", "_KapiSerisi__isaret", "_KapiSerisi__zamanlar", "_KapiSerisi__sira",
                 "_KapiSerisi__sonuclar", "_KapiSerisi__imzalar", "_KapiSerisi__baglam")

    def __init__(self, gizli, baglam: _KapiBaglami, kimlik: tuple, isaret: int, zamanlar: pd.DatetimeIndex, sonuclar):
        if gizli is not _SERI_GIZLI:
            raise TypeError("KapiSerisi yalnizca `pozisyon.kapi_serisi` ile kurulur (imzali seri; G11).")
        ns = tuple(int(x) for x in pd.DatetimeIndex(zamanlar).asi8)
        sonuclar = tuple(sonuclar)
        if len(ns) != len(sonuclar):
            raise ValueError("KapiSerisi: zaman ve sonuc sayilari esit olmali.")
        sett = object.__setattr__
        sett(self, "_KapiSerisi__baglam", baglam)
        sett(self, "_KapiSerisi__kimlik", kimlik)
        sett(self, "_KapiSerisi__isaret", int(isaret))
        sett(self, "_KapiSerisi__zamanlar", ns)
        sett(self, "_KapiSerisi__sira", MappingProxyType({z: i for i, z in enumerate(ns)}))
        sett(self, "_KapiSerisi__sonuclar", sonuclar)
        sett(self, "_KapiSerisi__imzalar", tuple(_satir_imzasi(kimlik, int(isaret), z, s) for z, s in zip(ns, sonuclar)))

    def __setattr__(self, ad, deger):
        raise AttributeError("KapiSerisi degistirilemez (G11).")

    def __delattr__(self, ad):
        raise AttributeError("KapiSerisi degistirilemez (G11).")

    def __reduce__(self):
        raise TypeError("KapiSerisi kopyalanamaz ya da serilestirilemez (G11); alt surec kendi serisini kurar.")

    def __copy__(self):
        return self

    def __deepcopy__(self, bellek):
        return self

    def __len__(self) -> int:
        self._denetle()
        return len(self.__zamanlar)

    def __repr__(self) -> str:
        return f"KapiSerisi({self.__kimlik[:7]})"

    @property
    def kimlik(self) -> tuple:
        """(kume, sembol, donem, hipotez, yapilandirma kimligi, rol, capa anahtari, bar turu, ufuk, birincil ufuk)."""
        return self.__kimlik

    def _denetle(self) -> None:
        b = self.__baglam
        if kume_bellegi.donem_isareti() != self.__isaret:
            raise SeriEskidi(f"{self.__kimlik[:6]} serisi bir kosu acilisindan ya da kapanisindan once kuruldu; okuma "
                             "reddedildi (G11 donem isareti). Seri yeniden kurulmalidir.")
        split_modulu.onay_baglami_dogrula(b.hipotez, b.kume, b.yapilandirma_kimligi)
        split_modulu.kesif_baglami_dogrula(b.kume)
        grup_dogrula(b.sembol, b.kume)
        split_modulu.onay_erisimi_denetle(b.kume, b.onay)

    def _satir(self, i: int):
        z, s = self.__zamanlar[i], self.__sonuclar[i]
        if self.__imzalar[i] != _satir_imzasi(self.__kimlik, self.__isaret, z, s):
            raise ValueError("KapiSerisi satiri degistirilmis (imza tutmuyor; G11).")
        if isinstance(s, OnaylanmisPozisyon):
            onay_dogrula(s)
        return s

    def _sira_no(self, t) -> int | None:
        zaman = pencere_modulu.utc_zamani(t, "t")
        return self.__sira.get(int(zaman.value))

    def icerir(self, t) -> bool:
        """t (kesin zaman esitligiyle) serinin bir satiri mi?"""
        self._denetle()
        return self._sira_no(t) is not None

    def sonuc(self, t):
        """t satirinin sonucu: onayli pozisyon doner ya da ret (skalerle ayni sinif ve mesaj) yukseltilir. t seride
        yoksa KeyError."""
        self._denetle()
        i = self._sira_no(t)
        if i is None:
            raise KeyError(f"{t} bu serinin bir satiri degil.")
        return _sonucu_ver(self._satir(i))

    def pozisyon(self, t) -> OnaylanmisPozisyon:
        """Ornekleme adayinin (biti 1 olan bar) onayli pozisyonu. Satir yoksa ya da ret ise `KontrolAdayiHatasi`: SERT
        hata, yeniden cekim yapilmaz (G9)."""
        self._denetle()
        i = self._sira_no(t)
        if i is None:
            raise KontrolAdayiHatasi(f"{t} bu serinin bir satiri degil; aday kurulamadi (G9).")
        s = self._satir(i)
        if not isinstance(s, OnaylanmisPozisyon):
            raise KontrolAdayiHatasi(f"{t} adayi onayli degil ({s[1].__name__}); aday kurulamadi (G9).")
        return s

    def zamanlar(self) -> pd.DatetimeIndex:
        self._denetle()
        return pd.DatetimeIndex(np.asarray(self.__zamanlar, dtype="int64"), tz="UTC") if self.__zamanlar else \
            pd.DatetimeIndex([], tz="UTC")

    def onay_bitleri(self) -> np.ndarray:
        """Her satir icin 1 = onayli pozisyon, 0 = ret (kapinin BUTUN kosullari; G9). Her satirin imzasi denetlenir."""
        self._denetle()
        return np.asarray([isinstance(self._satir(i), OnaylanmisPozisyon) for i in range(len(self.__zamanlar))],
                          dtype=bool)

    def _ham_sonuclar(self) -> tuple:
        """Ic kullanim (ikincil ufuk serisinin birincil ret satirlari): denetimli, imzasi dogrulanmis satirlar."""
        self._denetle()
        return tuple(self._satir(i) for i in range(len(self.__zamanlar)))


def _seri_bellegini_temizle() -> None:
    with _SERI_KILIDI:
        _SERI_BELLEGI.clear()
        _SERI_HATALARI.clear()


kume_bellegi.temizleyici_ekle(_seri_bellegini_temizle)


def _seri_bellekten(anahtar: tuple, kur) -> KapiSerisi:
    """Seri onbellegi: SABIT tanimlara (`_karar_girdisi`, `_PlanSerisi`, `_karar_verisi`) DOKUNMADAN, ayri bir anahtar
    ve ayri bir LRU ile (G2, G11). Anahtar donem isaretini de tasir; kosu acilisi ve kapanisi (`kume_bellegi.temizle`)
    onbellegi dusurur.

    Hata veren kurulum (F1-K1, denetci D-B1; G10): hata seri bellegine YAZILMAZ (kismi seri yoktur), ayri bir LRU'da
    (`_SERI_HATALARI`, ayni anahtar ve ayni sinir) tutulur. Ayni anahtarla sonraki cagri seriyi yeniden kurmaz, AYNI hata
    nesnesini yeniden yukseltir; boylece birimin her bari seriyi yeniden kurmaya calismaz. Hata bellegi seri bellegiyle
    ayni donem isareti kuralina uyar: anahtar isareti tasir, yalnizca isaret degismemisse yazilir ve kosu acilisi /
    kapanisi (`_seri_bellegini_temizle`) onu da dusurur. `MemoryError` tutulmaz (ortamin durumudur, birimin degil)."""
    with _SERI_KILIDI:
        seri = _SERI_BELLEGI.get(anahtar)
        hata = None
        if seri is not None:
            _SERI_BELLEGI.move_to_end(anahtar)
        else:
            hata = _SERI_HATALARI.get(anahtar)
            if hata is not None:
                _SERI_HATALARI.move_to_end(anahtar)
    if hata is not None:
        raise hata.with_traceback(None)
    if seri is None:
        try:
            seri = kur()
        except MemoryError:
            raise
        except Exception as kurulum_hatasi:
            with _SERI_KILIDI:
                if kume_bellegi.donem_isareti() == anahtar[-1]:
                    _SERI_HATALARI[anahtar] = kurulum_hatasi
                    _SERI_HATALARI.move_to_end(anahtar)
                    while len(_SERI_HATALARI) > SERI_AZAMI_GIRDI:
                        _SERI_HATALARI.popitem(last=False)
            raise
        with _SERI_KILIDI:
            if kume_bellegi.donem_isareti() == anahtar[-1]:
                _SERI_BELLEGI[anahtar] = seri
                _SERI_BELLEGI.move_to_end(anahtar)
                while len(_SERI_BELLEGI) > SERI_AZAMI_GIRDI:
                    _SERI_BELLEGI.popitem(last=False)
    return seri


def _capa_anahtari(b: _KapiBaglami, capa):
    """(capa anahtari, bicimlenmis capa). Capa veri yuklenmeden once denetlenir (skalerdeki sira): kontrol rollerinde ve
    H2/H3'te verilemez; H1 olay rolunde zorunludur (`_capa_dogrula`). Dizi bicimi UTC olmali, NaT tasiyamaz. Anahtar
    izgarayi gerektirmez; onbellek isabetinde izgara ve veri yeniden kurulmaz."""
    capali = b.hipotez in sinyal_modulu.CAPALI_HIPOTEZLER and b.rol == "olay"
    if not capali or capa is None or not isinstance(capa, (pd.DatetimeIndex, np.ndarray, list, tuple, pd.Series)):
        tek = _capa_dogrula(b.hipotez, b.rol, capa)
        return (None if tek is None else ("tek", int(tek.value))), tek
    c = pd.DatetimeIndex(capa)
    if len(c) and (c.tz is None or bool(c.isna().any())):
        raise TypeError("capa dizisi UTC zaman damgalarindan olusmali (NaT ve saat dilimsiz zaman verilemez).")
    c = c.tz_convert("UTC") if len(c) else pd.DatetimeIndex([], tz="UTC")
    return ("dizi", len(c), hashlib.sha256(np.asarray(c.asi8, dtype="int64").tobytes()).hexdigest()), c


def _capa_satirlari(b: _KapiBaglami, capa, izgara: pd.DatetimeIndex):
    """(satir zamanlari, satir basina capalar). Capa YALNIZCA H1'in olay rolunde:
      - tek pump bari: satirlar izgaranin o capanin izleme penceresindeki barlaridir (`(capa, capa + 12 x 4h]`, 4h
        izgarasinda; on-kayit §5 H1 madde 3); pencere disindaki bar bu capanin teyit adayi degildir;
      - izgarayla ayni uzunlukta dizi: teyit basina pump bari; satirlar izgaranin butun barlari. Tanimsiz bir teyit
        (12 bardan uzak) skalerle ayni sinifla durur (G10)."""
    if capa is None:
        return izgara, None
    if isinstance(capa, pd.DatetimeIndex):
        if len(capa) != len(izgara):
            raise ValueError("capa dizisi hipotez izgarasiyla ayni uzunlukta olmali (teyit basina pump bari).")
        return izgara, list(capa)
    fark = izgara - capa
    adim = pencere_modulu.ADIM_4H
    pencerede = np.asarray((fark % adim == pd.Timedelta(0)) & (fark >= adim)
                           & (fark <= config.H1_IZLEME_BAR * adim), dtype=bool)
    satirlar = izgara[pencerede]
    return satirlar, [capa] * len(satirlar)


def kapi_serisi(hipotez, yapilandirma, rol, *, kume, sembol, donem_no, capa=None, ufuk=None) -> KapiSerisi:
    """TEK SERI KAPI (performans 2b-2; plan v3 G1). Bir (sembol, donem, kume) biriminin hipotez izgarasindaki BUTUN
    barlari icin karar: her satir onayli pozisyon (`OnaylanmisPozisyon`) ya da ret sinifi ve mesaji; ikisi de skalerle
    birebir ayni (dondurulmus skaler referansin `olay_karari`si). Olay, K1 ve K2 (H1'in capali olay rolu dahil)
    ayni cekirdekten (`_kapi_satirlari`) gecer.

    Imza (onerilen imza; `capa` H1 olay rolunde tek pump bari ya da izgarayla ayni uzunlukta dizi):
      - `hipotez`, `yapilandirma`, `rol`: olay_karari ile ayni anlam.
      - `kume`, `sembol`, `donem_no`: KIMLIK. Cagiran cerceve, sinir ya da izgara vermez; veriyi kapi `_karar_verisi` /
        `_karar_girdisi` ile kendisi yukler, izgarayi hipotez izgarasi yardimcisindan alir (G20).
      - `ufuk`: None = birincil ufuk; ikincil ufuk verilirse once BIRINCIL seri kurulur ve birincil ufukta reddedilen
        bar ayni retle doner (skalerle ayni); onaylanan barlar ikincil ufkun kendi plani, funding'i ve fiyatlariyla
        yeniden degerlendirilir. Ikincil seri birincil serinin POZISYONUNU okumaz (G11).
    Esikler on-kayit degerleridir (`eligibility.hacim_esigi`, `config.ASGARI_LISTELEME_YASI_GUN`).

    Kurulum ve HER okuma baglam ve grup denetiminden gecer (G9, G11). Onbellek anahtari: kume, sembol, donem, hipotez,
    yapilandirma kimligi, rol, capa anahtari, bar turu, ufuk, birincil ufuk ve donem isareti. `OlayOlusmaz` disindaki her
    istisna kurulumu durdurur ve yukari cikar (G10). Getiri hesaplamaz."""
    b = _kapi_baglami(hipotez, yapilandirma, rol, kume=kume, sembol=sembol, donem_no=donem_no, ufuk=ufuk)
    # Capa veri yuklenmeden once denetlenir (skalerdeki sira): kontrol rollerinde ve H2/H3'te verilemez; H1 olay rolunde
    # zorunludur. Dizi bicimi izgara uzunluguyla `_capa_satirlari`nda (kurulumda) denetlenir; onbellek isabetinde
    # izgara ve veri yeniden kurulmaz.
    capa_anahtari, capa_bicimli = _capa_anahtari(b, capa)
    isaret = kume_bellegi.donem_isareti()
    kimlik = (b.kume, b.sembol, int(b.donem_no), b.hipotez, b.yapilandirma_kimligi, b.rol, capa_anahtari, b.bar,
              b.ufuk, b.birincil_ufuk)
    anahtar = ("kapi_serisi", *kimlik, isaret)

    def kur() -> KapiSerisi:
        izgara = hipotez_izgarasi_barlari(b.hipotez, kume=b.kume, sembol=b.sembol, donem_no=b.donem_no)
        satirlar, capalar = _capa_satirlari(b, capa_bicimli, izgara)
        if b.ufuk == b.birincil_ufuk:
            return KapiSerisi(_SERI_GIZLI, b, kimlik, isaret, satirlar, _kapi_satirlari(b, satirlar, capalar))
        birincil = kapi_serisi(b.hipotez, b.yapilandirma, b.rol, kume=b.kume, sembol=b.sembol, donem_no=b.donem_no,
                               capa=capa, ufuk=None)
        once = birincil._ham_sonuclar()
        gecen = np.asarray([i for i, s in enumerate(once) if isinstance(s, OnaylanmisPozisyon)], dtype=np.int64)
        sonuclar = list(once)
        if len(gecen):
            alt = _kapi_satirlari(b, satirlar[gecen], None if capalar is None else [capalar[i] for i in gecen])
            for i, s in zip(gecen, alt):
                sonuclar[i] = s
        return KapiSerisi(_SERI_GIZLI, b, kimlik, isaret, satirlar, sonuclar)

    return _seri_bellekten(anahtar, kur)


# --- K2 bit dizisi ve ornekleme adayi (G9; bu turda yalnizca uretilir ve sinanir, kullanimi P2c) ----------------------

def k2_bitleri(hipotez, yapilandirma, *, kume, sembol, donem_no, zamanlar) -> np.ndarray:
    """K2 rolunun bit dizisi: istenen her bar zamani icin 1 = kapinin BUTUN kosullarindan gecen K2 bari (G9).

    Kapsam: baglam (onay, kesif), grup uyeligi (ACIK denetim), plan, t barinin varligi, capasiz pencereler, uygunluk,
    funding'li donem, funding tamligi ve toplamin sonlulugu, P0 ve P1'in pozitifligi, MAE penceresinin sonlulugu
    (`kapi_serisi(..., rol="K2")`). Hipotez izgarasinda olmayan zaman 0'dir (izgara karar adayidir; G20).

    Kumenin gruplarina ait olmayan sembolun biti (ör. KESIF'te B grubu) ACIK GRUP DENETIMIYLE 0'dir: veri hic
    yuklenmez; `split.yukle`nin bos cerceve dondurmesine dayanilmaz. Baglam denetimleri bu durumda da calisir."""
    gecerli = sinyal_modulu.yapilandirma_dogrula(hipotez, yapilandirma)
    kimlik = sinyal_modulu.yapilandirma_kimligi(hipotez, gecerli)
    kume_sinirlari(kume)
    split_modulu.onay_baglami_dogrula(hipotez, kume, kimlik)
    split_modulu.kesif_baglami_dogrula(kume)
    donem_kaydi(sembol, donem_no)
    istenen = pd.DatetimeIndex(zamanlar)
    if len(istenen) and istenen.tz is None:
        raise TypeError("zamanlar saat dilimsiz (tz-naive); tum zaman damgalari UTC olmali.")
    # Grup kurali tek kaynaktan (F1-K1, denetci D-C3): `grup_dogrula`nin YALNIZCA grup reddi (ValueError) 0 bitine
    # doner; baska her hata (G10) yukari cikar.
    try:
        grup_dogrula(sembol, kume)
    except ValueError:
        return np.zeros(len(istenen), dtype=bool)
    seri = kapi_serisi(hipotez, gecerli, "K2", kume=kume, sembol=sembol, donem_no=donem_no)
    bitler = seri.onay_bitleri()
    sira = seri.zamanlar().get_indexer(istenen.tz_convert("UTC") if len(istenen) else istenen)
    return np.asarray([bool(bitler[i]) if i >= 0 else False for i in sira], dtype=bool)


def k2_aday_pozisyonu(hipotez, yapilandirma, *, kume, sembol, donem_no, t) -> OnaylanmisPozisyon:
    """Ornekleme adayinin (biti 1) onayli pozisyonu. Kurulumda ya da okumada cikan HER hata yukari cikar (G9: sert
    hata, yeniden cekim yapilmaz); aday artik onayli degilse `KontrolAdayiHatasi`."""
    seri = kapi_serisi(hipotez, yapilandirma, "K2", kume=kume, sembol=sembol, donem_no=donem_no)
    return seri.pozisyon(t)


def _olay_kosulu_serisi(hipotez, yapilandirma, *, kume, sembol, donem_no, capa=None) -> np.ndarray:
    """Kapinin olay rolundeki VEKTOREL KOSULU, hipotez izgarasinin her barinda: True / False / None (None = degerlerden
    biri hesaplanamadi ya da H1 tepe penceresi o (pump, teyit) cifti icin tanimsiz; skaler `sinyal_kosulu` ile ayni
    sozlesme). YALNIZCA gercek veri esitlik betigi icindir (G1 gecici istisnasi, G14: vektorel kosul ile skaler
    `sinyal_kosulu` her barda karsilastirilir); karar vermez. Degerler ve kosul cekirdegin kullandigi AYNI
    fonksiyonlardan (`_olay_degerleri`, `_kosul_dizisi`). H1'de `capa`: izgarayla ayni uzunlukta pump barlari."""
    b = _kapi_baglami(hipotez, yapilandirma, "olay", kume=kume, sembol=sembol, donem_no=donem_no)
    izgara = hipotez_izgarasi_barlari(b.hipotez, kume=b.kume, sembol=b.sembol, donem_no=b.donem_no)
    mumlar_4h, funding, gunluk_mumlar, _ = _karar_girdisi(
        b.sembol, b.kume, kume_baslangic=b.kume_baslangic, kume_bitis=b.kume_bitis,
        donem_baslangic=b.donem_baslangic, donem_bitis=b.donem_bitis)
    _mum_zamanlari(mumlar_4h)
    sonuc = np.full(len(izgara), None, dtype=object)
    gecerli = np.ones(len(izgara), dtype=bool)
    c = None
    if b.hipotez in sinyal_modulu.CAPALI_HIPOTEZLER:
        c = pd.DatetimeIndex(capa)
        if len(c) != len(izgara):
            raise ValueError("capa dizisi hipotez izgarasiyla ayni uzunlukta olmali.")
        fark = izgara - c
        adim = pencere_modulu.ADIM_4H
        gecerli = np.asarray((fark % adim == pd.Timedelta(0)) & (fark >= adim)
                             & (fark <= config.H1_IZLEME_BAR * adim), dtype=bool)
    if not gecerli.any():
        return sonuc
    z = izgara[gecerli]
    degerler = _olay_degerleri(b, z, None if c is None else c[gecerli], mumlar_4h, gunluk_mumlar, funding)
    adlar = sinyal_modulu.DEGER_ADLARI[b.hipotez]
    tam = np.logical_and.reduce([_sonlu_dizi(degerler[a]) for a in adlar])
    kosul = np.zeros(len(z), dtype=bool)
    if tam.any():
        kosul[tam] = _kosul_dizisi(b.hipotez, b.yapilandirma, {a: degerler[a][tam] for a in adlar})
    yerel = np.full(len(z), None, dtype=object)
    yerel[tam] = [bool(x) for x in kosul[tam]]
    sonuc[gecerli] = yerel
    return sonuc


def pozisyon_fiyatlari(pozisyon) -> tuple[float, float]:
    """(P0, P1): brut getirinin tek girdisi. Yalnizca `olay_karari` ciktisini kabul eder."""
    onay_dogrula(pozisyon)
    return pozisyon.p0, pozisyon.p1


def mae(pozisyon) -> float:
    """En kotu ara zarar (on-kayit §4 rev.8 "MAE"): `max(H, P1) / P0 - 1`.

    "H, acilisi giris anindan once olmayan ve kapanisi cikis anindan sonra olmayan
    butun donem ici 4h barlarin en yuksek high degeridir; boyle bar yoksa yalnizca P1
    kullanilir. Izgaradan bagimsiz olarak 4h barlardan hesaplanir." Zaman
    karsilastirmalari "Zaman toleransi"na gore. Eksik barlar MAE'yi hesaplanamaz
    yapmaz (bosluk suresince ara zarar gozlenemez; rapor bu siniri yazar).
    Yalnizca `olay_karari` ciktisini kabul eder; 4h serisini onayli pozisyonun kimligiyle (sembol,
    kume) kararla ayni yoldan kendisi yukler (kapi sertlestirme turu 2): cagiran cerceve vermez.
    Raporlanir, esik degildir.
    """
    onay_dogrula(pozisyon)
    split_modulu.onay_baglami_dogrula(pozisyon.hipotez, pozisyon.kume,
                                      pozisyon.yapilandirma)  # kapi sertlestirme turu 3
    split_modulu.kesif_baglami_dogrula(pozisyon.kume)  # karar noktasiyla ayni veri (RESULTS §14.43, denetci D-C1)
    plan = pozisyon.plan
    mumlar_4h, _ = _kume_verisi(pozisyon.sembol, pozisyon.kume, plan.kume_baslangic, plan.kume_bitis)
    zamanlar = _mum_zamanlari(mumlar_4h)
    # Sonuc da sonlu olmali (F1 kapatma turu madde 1b, bulgu 21): girdilerin her biri sonlu ve
    # POZITIF oldugu halde ALTNORMAL bir P0 (ör. 1e-320) oranı sonsuza goturuyordu ve `mae` sessizce
    # `inf` donduruyordu. Oran seviyesinde denetlemek tek dogru yer: pozitiflik esigi altnormal
    # degerleri ayirt etmez.
    return _sonlu(_mae_tepesi(mumlar_4h, zamanlar, plan, pozisyon.p1) / pozisyon.p0 - 1, "MAE")
