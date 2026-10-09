"""Tek karar noktasi: bir olay ya da kontrol olusur mu? (on-kayit §4 rev.8, rev.9)

On-kayit §4 "Olayin kumede olusma olcutu": "Bir olayin kumede olusup olusmadigina tek
bir karar noktasi hukmeder ... Ayni karar noktasinda pozisyonun funding tamligi da
saglanmalidir ... Uygunluk da bu karar noktasinin parcasidir (rev.9): hacim esigi ve
listeleme yasi dahil uygunluk filtresi, olaylar ve kontroller icin ayni karar noktasinda,
ayni cagriyla uygulanir. Uygunluk degerinin hesaplanabilmis olmasi yeterli degildir;
esigi de gecmelidir. ... Boylece brut ve net olay kumeleri her zaman aynidir."

`olay_karari` bu karar noktasidir; olaylar ve kontroller (K1, K2) ayni fonksiyonu cagirir,
ayri bir kontrol yolu yoktur. Sirasiyla:
  0. Hipotez -> izgara -> ufuk bagi (`pencere.hipotez_baglamini_dogrula`; F1 kapanis turu),
     yapilandirmanin izgarada olmasi (`sinyal.yapilandirma_dogrula`) ve ROL (on-kayit §6 rev.11).
  1. `pencere.pozisyon_plani`: sinyal kumede ve donem ici, giris bari, cikis (donem
     sonu / olagan / ileri kayma ve siniri), gercek cikis ani + tolerans <= kume sonu.
  2. Sinyal degerleri: kapi hipotezin butun sinyal degerlerini KENDISI hesaplar
     (`data.sinyal`; Rev.11 madde 4, F1 kapanis bulgusu D-B1). Cagiran deger vermez.
     Biri hesaplanamiyorsa `SinyalPenceresiTamDegil` (on-kayit §2 "Tamlik sarti"). Rol
     "olay" ise §5'teki kosullar saglanmali (`SinyalKosuluSaglanmadi`); rol "K2" ise
     saglanmamali (`OlayUretmis`). Rol "K1" ise sinyal HIC hesaplanmaz (on-kayit §6 rev.11).
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

**Rol (on-kayit §6 rev.11 "Kontrolun ne olctugu").** "Kontrol bari, olayin sinyal yapisini
taklit etmez: kontrolde hipotezin sinyal kosullari aranmaz. ... Kontrol bari icin gereken:
uygunluk filtresi, donem uyeligi, fiyat ve funding tamligi, ve §4'teki tek karar noktasinin
butun kosullari." Bu yuzden `rol`:
  - `"olay"`: sinyal degerleri hesaplanir ve §5'teki kosullar SAGLANMALI.
  - `"K2"`: sinyal degerleri yalnizca "o anda olay uretmemis" sartini dogrulamak icin hesaplanir;
    hesaplanamiyorsa bar kontrol OLAMAZ, hesaplanip kosulu saglamiyorsa kontrol adayidir.
    H1 bir istisnadir: "H1'in kontrol barinda pump bari, dip penceresi ve tepe aranmaz" (sinyali
    bir pump barina capalidir ve kontrol barinda pump yoktur), bu yuzden H1'in K2 barinda sinyal
    hic hesaplanmaz; "olay uretmemis" sarti o yapilandirmanin olay kumesine gore, ornekleme
    adiminda (`data.ornekleme`) uygulanir.
  - `"K1"`: sinyal hic hesaplanmaz. On-kayit §6 rev.11 kontrol tarafinda sinyal degerlerini
    "yalnizca tek bir amacla: K2'nin 'o anda olay uretmemis' sartini dogrulamak" icin hesaplar;
    K1'in olcutu zamansal uzakliktir, sinyal degil.

Getiri HESAPLAMAZ (F2 kodu degildir); fiyat ve funding degerlerini tasir ama raporlamaz.
"""

from __future__ import annotations

import functools
import math
from types import MappingProxyType
from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

import config
from data import eligibility as eligibility_modulu
from data import funding as funding_modulu
from data import klines as klines_modulu
from data import pencere as pencere_modulu
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


class OlayUretmis(pencere_modulu.OlayOlusmaz):
    """K2 adayi olmayan bar: o anda hipotezin kosullari saglaniyor, yani bar olay uretmis
    (on-kayit §6 K2: "o anda olay uretmemis diger coinlerden")."""

    gerekce = "olay_uretmis"


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
    hipotez: str | None = None
    # Yapilandirma kimligi ve rol (on-kayit §5, §6 rev.11): ornekleme ve dizi kurallari "ayni
    # yapilandirmanin olusmus olaylari"na gore isler, bu yuzden onayli pozisyon ikisini de tasir.
    yapilandirma: str | None = None
    rol: str | None = None
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
                 p.ritim_sinifi, p.hipotez, p.yapilandirma, p.rol, p.sembol, p.kume, p.donem_no))


def onay_dogrula(pozisyon) -> None:
    """`olay_karari`nin urettigi ve degistirilmemis bir pozisyon mu?"""
    if not isinstance(pozisyon, OnaylanmisPozisyon):
        raise TypeError(f"Onaylanmis pozisyon gerekir (pozisyon.olay_karari ciktisi); verilen: {type(pozisyon).__name__}")
    if pozisyon._imza != _imza(pozisyon):
        raise ValueError("OnaylanmisPozisyon elle kurulmus ya da degistirilmis; yalnizca olay_karari uretir.")


def _close_time_nat_yok(mumlar: pd.DataFrame, ad: str) -> None:
    """`close_time` sutunu varsa hicbir satiri NaT olamaz. NaT ile yapilan sure karsilastirmasi her
    zaman False doner; NaT'li bir 1d cercevesi 4h denetiminden (ya da tersi) sessizce gecerdi
    (sizinti testcisinin Rev.10 hazirlik bulgusu 2; on-kayit §4 "Fiyat okuma tabani")."""
    if bool(pd.isna(mumlar["close_time"]).any()):
        raise pencere_modulu.VeriHatasi(f"{ad}: close_time sutununda NaT var; bar suresi dogrulanamaz "
                         "(on-kayit §4 'Fiyat okuma tabani').")


def _gunluk_hacim(gunluk_mumlar: pd.DataFrame) -> pd.Series:
    """Uygunluk hacminin girdisi: sembolun 1d serisi (`klines.mumlari_yukle(s, "1d", ...)`,
    tek 1d yolu `klines.gunluge_cevir`). 1d olmayan cerceve (ör. 4h mumlari) acik hata verir:
    acilislar gun basi olmali ve `close_time` varsa bar suresi 4 saati asmali."""
    if not isinstance(gunluk_mumlar, pd.DataFrame) or "open_time" not in gunluk_mumlar:
        raise TypeError("gunluk_mumlar sembolun 1d mum cercevesi olmali (open_time, quote_volume).")
    acilis = pencere_modulu._zaman_dizisi_dogrula(pd.DatetimeIndex(gunluk_mumlar["open_time"]), "gunluk_mumlar")
    if len(acilis) and not bool((acilis == acilis.floor("D")).all()):
        raise pencere_modulu.VeriHatasi("gunluk_mumlar 1d serisi olmali: acilislar UTC gun basi degil (4h cercevesi verilmis olabilir).")
    if "close_time" in gunluk_mumlar and len(acilis):
        _close_time_nat_yok(gunluk_mumlar, "gunluk_mumlar")
        sure = pd.DatetimeIndex(gunluk_mumlar["close_time"]) - acilis
        if bool((sure <= pencere_modulu.ADIM_4H).any()):
            raise pencere_modulu.VeriHatasi("gunluk_mumlar 1d serisi olmali: bar suresi 4 saati asmiyor.")
    return eligibility_modulu.gunluk_hacim_serisi(gunluk_mumlar)


def _mum_zamanlari(mumlar: pd.DataFrame) -> pd.DatetimeIndex:
    """Fiyat okuma tabaninin 4h serisi oldugunu denetler (on-kayit §4 rev.8 "Fiyat okuma
    tabani": pozisyonun butun fiyat okumalari her hipotezde donem ici 4h barlardan; denetci
    bulgusu D-B3). 1d cercevesi (ör. `klines.mumlari_yukle(s, "1d", ...)`) ayni sutun adlarini
    tasidigi icin sessizce kabul edilirse her cikis ileri kaymaya duser; burada acik hata verir:
      - acilislar 4h izgarasinda (gun basindan 0, 4, ..., 20 saat) olmali,
      - `close_time` varsa hicbir barin suresi 4 saati asmamali; yoksa en az iki bar olmali,
      - en az iki bar varsa ardisik iki acilis arasindaki en kucuk fark 4 saat olmali.
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
    if len(zamanlar) > 1 and (zamanlar[1:] - zamanlar[:-1]).min() != adim:
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


def _kume_verisi(sembol: str, kume: str, kume_baslangic, kume_bitis) -> tuple[pd.DataFrame, pd.DataFrame]:
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
    if len(fr):
        zaman = pd.DatetimeIndex(fr["odeme_zamani"])
        fr = fr.loc[np.asarray((zaman >= kume_baslangic) & (zaman <= kume_bitis), dtype=bool)].reset_index(drop=True)
    return mumlar, fr


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


def _mae_tepesi(mumlar_4h: pd.DataFrame, zamanlar: pd.DatetimeIndex, plan, p1: float) -> float:
    """MAE'nin H'si (on-kayit §4 rev.8): giris anindan once acilmayan, cikis anindan sonra kapanmayan donem
    ici 4h barlarin en yuksek high'i ile P1'in buyugu. Secilen high'lar sonlu olmali (`_sonlu`)."""
    kapanislar = zamanlar + pencere_modulu.ADIM_4H
    secim = (np.asarray(pencere_modulu.ayni_ya_da_sonra(zamanlar, plan.giris), dtype=bool)
             & np.asarray(pencere_modulu.ayni_ya_da_once(kapanislar, plan.cikis_ani), dtype=bool)
             & np.asarray(pencere_modulu.donem_ici_4h_maskesi(
                 zamanlar, donem_baslangic=plan.donem_baslangic, donem_bitis=plan.donem_bitis), dtype=bool))
    tepe = p1
    if secim.any():
        yuksekler = mumlar_4h["high"].to_numpy(dtype=float)[secim]
        for deger in yuksekler:
            _sonlu(float(deger), "pozisyon penceresindeki high")
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


def _sinyal_gerekli(hipotez: str, rol: str) -> bool:
    """Bu hipotez ve rolde sinyal degerleri hesaplanir mi? (on-kayit §6 rev.11)

    - Olay rolu: her zaman (§5'teki kosullar saglanmali).
    - K2: "Sinyal degerleri kontrol tarafinda yalnizca tek bir amacla hesaplanir: K2'nin 'o anda
      olay uretmemis' sartini dogrulamak." H1 haric: "H1'in kontrol barinda pump bari, dip
      penceresi ve tepe aranmaz" (capali sinyal, kontrol barinda capa yok), bu yuzden H1'in K2
      sarti ornekleme adiminda o yapilandirmanin olay kumesine gore uygulanir.
    - K1: hic. K1'in olcutu "o hipotezin herhangi bir olayina birincil ufuk mesafesinden yakin
      olmamak"tir; sinyal degeri gerekmez.
    """
    if rol == "olay":
        return True
    if rol == "K2":
        return hipotez not in sinyal_modulu.CAPALI_HIPOTEZLER
    return False


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
    """TEK KARAR NOKTASI (on-kayit §4 rev.8, rev.9). Olay ya da kontrol olusursa
    `OnaylanmisPozisyon`, olusmazsa `OlayOlusmaz` alt sinifi (ret gerekcesi:
    `pencere.ret_gerekcesi`). Olaylar ve kontroller ayni cagriyi kullanir.

    Fiyat, funding ve 1d cerceveleri cagirandan alinmaz: kapi `sembol` ve `kume` ile yukler
    (`_kume_verisi`), 1d serisini 4h barlardan turetir (`klines.gunluge_cevir`). `sinyal_zamani` UTC
    olmali; sinyal bari hipotezin izgarasinda donem ici seride bulunmali (`SinyalBariYok`). Sonlu
    olmayan fiyat ya da funding toplami acik hatadir.

    SINYAL DEGERLERI CAGIRANDAN ALINMAZ (Rev.11 madde 4): kapi hipotezin butun sinyal degerlerini
    `data.sinyal`in pencere kuruculariyla kendisi hesaplar. `yapilandirma`: hipotezin izgarasindaki
    bir parametre demeti (on-kayit §5 rev.11; izgarada olmayan demet `sinyal.YapilandirmaHatasi`).
    `rol`: "olay", "K1" ya da "K2" (modul aciklamasindaki "Rol" basligi). `capa`: yalnizca H1'in
    olay rolunde pump bari, baska her durumda `None` (`_capa_dogrula`).
    `asgari_hacim`, `asgari_listeleme_yasi_gun`:
    uygunluk esikleri, on-kayit §2 degerleri olmalidir (`eligibility.esikleri_dogrula`).
    `hipotez` ("H1", "H2", "H3") zorunludur: `bar`, `ufuk` ve `birincil_ufuk` hipotezden tureyen on-kayit
    degerleriyle uyumlu olmalidir (`pencere.hipotez_baglamini_dogrula`; F2 kodu bunlari
    `pencere.hipotez_ufuklari`ndan okur). Onayli pozisyon hipotezi imzali tasir.
    Butun sinirlar ve esikler zorunlu anahtar sozcuktur; varsayilan yoktur. `kume`: kumenin ADI
    ("KESIF", "C1", "C2"); sinirlari kapi `split.kume_araligi`ndan kendisi okur (`kume_sinirlari`),
    cagiran sinir vermez. `sembol`, `donem_no`: evren tablosundaki listeleme donemi (`donem_id`);
    donem sinirlari kapida tablodan okunur (`donem_kaydi`), cagiran sinir vermez. Sembolun A/B grubu
    (bolme tablosu) kumenin gruplarindan biri olmalidir (`grup_dogrula`).
    """
    # Hipotez -> izgara -> ufuk bagi (on-kayit §4 "Ufuk degerlerinin baglanmasi", rev.10; F1 kapanis
    # turu, denetci D-B2): izgara ve ufuklar hipotezden turer; uyumsuz eslesme calisma aninda hata.
    pencere_modulu.hipotez_baglamini_dogrula(hipotez, bar, ufuk, birincil_ufuk)
    # Yapilandirma ve rol (on-kayit §5, §6 rev.11): "Olay ya da kontrol ureten her cagri, hipotezi
    # ve yapilandirmayi birlikte alir; izgarada bulunmayan bir parametre demeti hata verir."
    gecerli_yapilandirma = sinyal_modulu.yapilandirma_dogrula(hipotez, yapilandirma)
    yapilandirma_kimligi = sinyal_modulu.yapilandirma_kimligi(hipotez, gecerli_yapilandirma)
    rol = _rol_dogrula(rol)
    capa = _capa_dogrula(hipotez, rol, capa)
    # Olayin olusup olusmadigi BIRINCIL ufukta belirlenir (kapi sertlestirme turu 3, denetci KS2 D-B3; on-kayit
    # §4 "Ufuk degerlerinin baglanmasi": "Ikincil ufuklar yalnizca raporlanir; onay kararlari birincil ufka
    # gore verilir"). Ikincil ufuk istenirse ayni cagri once birincil ufukla degerlendirilir; orada olay
    # olusmazsa ayni ret gerekcesi yukari cikar ve hicbir ikincil ufukta onay verilmez. Birincil ufukta olusan
    # olayin ikincil cikisi ayrica kendi ufuk uzunluguyla kurallara tabidir (on-kayit §3 "Kume siniri ve ufuk").
    if ufuk != birincil_ufuk:
        olay_karari(sinyal_zamani, birincil_ufuk, bar, hipotez=hipotez, yapilandirma=gecerli_yapilandirma,
                    rol=rol, capa=capa, birincil_ufuk=birincil_ufuk, kume=kume, sembol=sembol,
                    donem_no=donem_no, asgari_hacim=asgari_hacim,
                    asgari_listeleme_yasi_gun=asgari_listeleme_yasi_gun)
    sinyal_zamani = _utc_sinyal_zamani(sinyal_zamani)
    # Kume sinirlari cagirandan alinmaz; kume adindan kapida okunur (kapi sertlestirme turu, denetci F1K2
    # D-B1; on-kayit §3 "Kume siniri ve geriye bakis": "kod duzeyinde ayrica dogrulanir"). Serbest sinir
    # cifti, karisik sinir (ör. KESIF basi + C2 sonu) ya da None verilemez.
    kume_baslangic, kume_bitis = kume_sinirlari(kume)
    # Onay baglami (kapi sertlestirme turu 3, denetci KS2 D-B1): C1/C2 pozisyonu yalnizca ayni (hipotez, kume)
    # ciftinin acik onay kosusunda; acik kosu varken baska pozisyon yok. Uyusmazlik `split.OnayUyusmazligi`.
    split_modulu.onay_baglami_dogrula(hipotez, kume)
    # Donem sinirlari da cagirandan alinmaz; commit edilmis evren tablosundan sembol ve donem numarasiyla
    # okunur (kapi sertlestirme turu, denetci F1K2 D-B2; on-kayit §2 "Listeleme donemi", "Evren tablosunun
    # sabitlenmesi": "analiz bu dosyadan okur"). Sembolun grubu kumeye ait olmali (on-kayit §3 "Coin bolmesi").
    donem_baslangic, donem_bitis, donem_funding_yok = donem_kaydi(sembol, donem_no)
    grup_dogrula(sembol, kume)
    # Uygunluk girdileri her cagrida denetlenir (programlama hatasi, ret gerekcesi degil).
    eligibility_modulu.esikleri_dogrula(bar, asgari_hacim=asgari_hacim,
                                        asgari_listeleme_yasi_gun=asgari_listeleme_yasi_gun)
    # Veri kapida yuklenir (kapi sertlestirme turu 2, denetci KS D-B1, KS D-B2): cagiran cerceve vermez.
    mumlar_4h, funding = _kume_verisi(sembol, kume, kume_baslangic, kume_bitis)
    zamanlar = _mum_zamanlari(mumlar_4h)
    # 1d serisi tektir ve donem ici 4h barlardan turetilir (on-kayit §2 rev.8 "1 gunluk barlar": "Bu seri
    # tektir: H3'un sinyal pencereleri, butun hipotezlerin uygunluk hacmi ve K1/K2 havuzlarinin 1d barlari
    # ayni seriden gelir"). Uygunluk ve sinyal bari bu donemin gunlerine bakar; gun donem donem kuruldugu
    # icin yalnizca bu donemi vermek sembolun butun donemleriyle kurulan seriyle bu donemde aynidir.
    gunluk_mumlar = klines_modulu.gunluge_cevir(mumlar_4h, donemler=[_DonemSiniri(donem_baslangic, donem_bitis)])
    gunluk_hacim = _gunluk_hacim(gunluk_mumlar)

    plan = pencere_modulu.pozisyon_plani(
        zamanlar, sinyal_zamani, ufuk, bar, birincil_ufuk=birincil_ufuk, kume_baslangic=kume_baslangic,
        kume_bitis=kume_bitis, donem_baslangic=donem_baslangic, donem_bitis=donem_bitis)
    # Sinyal bari t seride olmali (kapi sertlestirme turu 2, denetci KS D-B3): plan yalnizca t+1'i arar.
    # 4h: t acilisli donem ici bar; 1d: t gunu turetilmis 1d serisinde (alti 4h barin tamami donem ici).
    if bar == config.BAR_4H:
        t_bari = pencere_modulu.ayni_andaki_bar(zamanlar, plan.sinyal_zamani)
    else:
        t_bari = pencere_modulu.ayni_andaki_bar(pd.DatetimeIndex(gunluk_mumlar["open_time"]), plan.sinyal_zamani)
    if t_bari is None:
        raise SinyalBariYok(f"{sembol}: sinyal bari {plan.sinyal_zamani} ({bar}) donem ici seride yok; olay ya da "
                            "kontrol olusmaz.")
    # Sinyal degerleri KAPIDA hesaplanir (Rev.11 madde 4; on-kayit §5 "Pencere sinirlari"). Kume ve
    # donem sinirlari plandan okunur; pencerelerin tamlik, donem ve kume kurallari `data.sinyal`
    # uzerinden `data.pencere`nin tek kapisindan gecer. H2'nin funding penceresi de burada, gercek
    # funding serisinden kurulur (`funding.funding_ortalamasi`).
    if _sinyal_gerekli(hipotez, rol):
        degerler = sinyal_modulu.sinyal_degerleri(
            hipotez, gecerli_yapilandirma, plan.sinyal_zamani, mumlar_4h=mumlar_4h,
            gunluk=gunluk_mumlar, funding=funding, capa=capa, kume_baslangic=plan.kume_baslangic,
            kume_bitis=plan.kume_bitis, donem_baslangic=plan.donem_baslangic)
        hesaplanamayan = sinyal_modulu.hesaplanamayan(hipotez, degerler)
        if hesaplanamayan:
            raise SinyalPenceresiTamDegil(
                f"Sinyal penceresi tam degil: {hesaplanamayan} (on-kayit §2 'Tamlik sarti'); "
                f"{plan.sinyal_zamani} barinda olay ya da kontrol olusmaz.")
        saglandi = sinyal_modulu.kosullar_saglandi(hipotez, gecerli_yapilandirma, degerler)
        if rol == "olay" and not saglandi:
            raise SinyalKosuluSaglanmadi(
                f"{hipotez} kosullari {plan.sinyal_zamani} barinda saglanmadi (on-kayit §5); olay olusmaz.")
        if rol == "K2" and saglandi:
            raise OlayUretmis(
                f"{hipotez} kosullari {plan.sinyal_zamani} barinda saglaniyor: bar olay uretmis, K2 "
                "adayi degil (on-kayit §6 K2).")
    # Uygunluk (on-kayit §4 rev.9): esik gecilmeli, hesaplanabilmis olmasi yetmez.
    if not eligibility_modulu.uygunluk_karari(
            gunluk_hacim, plan.sinyal_zamani, bar, donem_baslangic=plan.donem_baslangic,
            donem_bitis=plan.donem_bitis, kume_baslangic=plan.kume_baslangic, asgari_hacim=asgari_hacim,
            asgari_listeleme_yasi_gun=asgari_listeleme_yasi_gun):
        raise UygunDegil(f"Sinyal bari {plan.sinyal_zamani} ({bar}) uygun degil: listeleme yasi ya da medyan "
                         "hacim esigi gecilmiyor (on-kayit §2 'Uygunluk').")
    # On-kayit §2 "Funding'i bulunmayan donemler": hic funding kaydi olmayan donem hicbir hipotezde olay ya da
    # kontrol uretmez. Cagiranin verdigi funding cercevesinden bagimsiz olarak tablodaki bayraktan uygulanir.
    if donem_funding_yok:
        raise FundingTamDegil(f"{sembol} donem {donem_no}: evren tablosunda funding kaydi yok (on-kayit §2 "
                              "'Funding'i bulunmayan donemler'); olay ya da kontrol olusmaz.")
    ayrinti = funding_modulu.pozisyon_funding_ayrintisi(funding, plan)
    if not bool(ayrinti["tam"]):
        raise FundingTamDegil(f"Pozisyonun funding'i tam degil: giris {plan.giris}, cikis {plan.cikis_ani} "
                              f"({plan.cikis_turu}); olay brut dahil hicbir hesapta olusmaz.")
    toplam = funding_modulu._plan_fundingi(funding, plan)
    if math.isnan(toplam):
        raise FundingTamDegil(f"Pozisyonun funding'i hesaplanamadi (oran NaN): giris {plan.giris}.")
    # Sonlu olmayan degerler (kapi sertlestirme turu 2): +-inf funding toplami, fiyat ve MAE penceresi.
    _sonlu(toplam, "funding toplami")
    p0 = _sonlu(_bar_degeri(mumlar_4h, zamanlar, plan.giris, "open"), "P0")
    p1 = _sonlu(_bar_degeri(mumlar_4h, zamanlar, plan.cikis.zaman, plan.cikis.fiyat_alani), "P1")
    _mae_tepesi(mumlar_4h, zamanlar, plan, p1)
    sonuc = OnaylanmisPozisyon(plan, p0, p1, toplam, kuyruk_kismi=bool(ayrinti["kuyruk_kismi"]),
                               son_esitlik_affi=bool(ayrinti["son_esitlik_affi"]),
                               capa_aralik_saat=float(ayrinti["capa_aralik_saat"]),
                               son_aralik_saat=float(ayrinti["son_aralik_saat"]), tek_ritim=bool(ayrinti["tek_ritim"]),
                               funding_ritmi_saat=float(ayrinti["funding_ritmi_saat"]),
                               karisik_ritim=bool(ayrinti["karisik_ritim"]),
                               ritim_sinifi=ayrinti["ritim_sinifi"], hipotez=hipotez,
                               yapilandirma=yapilandirma_kimligi, rol=rol, sembol=sembol, kume=kume,
                               donem_no=int(donem_no))
    return replace(sonuc, _imza=_imza(sonuc))


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
    split_modulu.onay_baglami_dogrula(pozisyon.hipotez, pozisyon.kume)  # kapi sertlestirme turu 3
    plan = pozisyon.plan
    mumlar_4h, _ = _kume_verisi(pozisyon.sembol, pozisyon.kume, plan.kume_baslangic, plan.kume_bitis)
    zamanlar = _mum_zamanlari(mumlar_4h)
    return _mae_tepesi(mumlar_4h, zamanlar, plan, pozisyon.p1) / pozisyon.p0 - 1
