"""Tek karar noktasi: bir olay ya da kontrol olusur mu? (on-kayit §4 rev.8, rev.9)

On-kayit §4 "Olayin kumede olusma olcutu": "Bir olayin kumede olusup olusmadigina tek
bir karar noktasi hukmeder ... Ayni karar noktasinda pozisyonun funding tamligi da
saglanmalidir ... Uygunluk da bu karar noktasinin parcasidir (rev.9): hacim esigi ve
listeleme yasi dahil uygunluk filtresi, olaylar ve kontroller icin ayni karar noktasinda,
ayni cagriyla uygulanir. Uygunluk degerinin hesaplanabilmis olmasi yeterli degildir;
esigi de gecmelidir. ... Boylece brut ve net olay kumeleri her zaman aynidir."

`olay_karari` bu karar noktasidir; olaylar ve kontroller (K1, K2) ayni fonksiyonu cagirir,
ayri bir kontrol yolu yoktur. Sirasiyla:
  1. Sinyal pencerelerinin tamligi: cagiranin hesapladigi pencere degerlerinden biri
     NaN ise `SinyalPenceresiTamDegil` (on-kayit §2 "Tamlik sarti").
  2. `pencere.pozisyon_plani`: sinyal kumede ve donem ici, giris bari, cikis (donem
     sonu / olagan / ileri kayma ve siniri), gercek cikis ani + tolerans <= kume sonu.
  3. Uygunluk (`eligibility.uygunluk_karari`, esikler zorunlu anahtar sozcuk) -> `UygunDegil`.
  4. Funding tamligi (`funding.pozisyon_funding_ayrintisi`) -> `FundingTamDegil`; ayni satirdan
     F2 saglamlik bayraklari (kismi kuyruk, esitlik affi, funding ritmi).
Karar olumluysa `OnaylanmisPozisyon` doner: plan, P0, P1 ve funding toplami. Brut
getiri, net getiri, MAE ve K1/K2 kontrolleri YALNIZCA bu ciktiyi kullanir;
`pozisyon_fiyatlari` ve `mae` baska girdi kabul etmez. Ayri bir kapi yoktur.

Getiri HESAPLAMAZ (F2 kodu degildir); fiyat ve funding degerlerini tasir ama
raporlamaz. Saf fonksiyonlar.
"""

from __future__ import annotations

import enum
import math
from collections.abc import Mapping
from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

from data import eligibility as eligibility_modulu
from data import funding as funding_modulu
from data import pencere as pencere_modulu


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
    _imza: int = field(default=0, repr=False, compare=False)

    @property
    def cikis_turu(self) -> str:
        return self.plan.cikis_turu


def _imza(p: OnaylanmisPozisyon) -> int:
    return hash((_ONAY_GIZLI, p.plan, p.p0, p.p1, p.funding_toplami, p.kuyruk_kismi, p.son_esitlik_affi,
                 p.capa_aralik_saat, p.son_aralik_saat, p.tek_ritim, p.funding_ritmi_saat, p.karisik_ritim,
                 p.ritim_sinifi, p.hipotez))


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
        raise ValueError(f"{ad}: close_time sutununda NaT var; bar suresi dogrulanamaz "
                         "(on-kayit §4 'Fiyat okuma tabani').")


def _gunluk_hacim(gunluk_mumlar: pd.DataFrame) -> pd.Series:
    """Uygunluk hacminin girdisi: sembolun 1d serisi (`klines.mumlari_yukle(s, "1d", ...)`,
    tek 1d yolu `klines.gunluge_cevir`). 1d olmayan cerceve (ör. 4h mumlari) acik hata verir:
    acilislar gun basi olmali ve `close_time` varsa bar suresi 4 saati asmali."""
    if not isinstance(gunluk_mumlar, pd.DataFrame) or "open_time" not in gunluk_mumlar:
        raise TypeError("gunluk_mumlar sembolun 1d mum cercevesi olmali (open_time, quote_volume).")
    acilis = pencere_modulu._zaman_dizisi_dogrula(pd.DatetimeIndex(gunluk_mumlar["open_time"]), "gunluk_mumlar")
    if len(acilis) and not bool((acilis == acilis.floor("D")).all()):
        raise ValueError("gunluk_mumlar 1d serisi olmali: acilislar UTC gun basi degil (4h cercevesi verilmis olabilir).")
    if "close_time" in gunluk_mumlar and len(acilis):
        _close_time_nat_yok(gunluk_mumlar, "gunluk_mumlar")
        sure = pd.DatetimeIndex(gunluk_mumlar["close_time"]) - acilis
        if bool((sure <= pencere_modulu.ADIM_4H).any()):
            raise ValueError("gunluk_mumlar 1d serisi olmali: bar suresi 4 saati asmiyor.")
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
        raise ValueError("mumlar_4h 4h izgarasinda degil (acilislar 00/04/08/12/16/20 UTC olmali).")
    if "close_time" not in mumlar and len(zamanlar) < 2:
        # Tek satirlik ve close_time'siz cerceve: gece yarisi acilisli bir 1d bari izgaraya uyar
        # ve ardisik fark olculemez; 4h serisi oldugu dogrulanamaz (sizinti testcisi bulgusu).
        raise ValueError("mumlar_4h 4h serisi oldugu dogrulanamiyor: tek satir ve close_time yok "
                         "(on-kayit §4 'Fiyat okuma tabani').")
    if "close_time" in mumlar:
        _close_time_nat_yok(mumlar, "mumlar_4h")
        sure = pd.DatetimeIndex(mumlar["close_time"]) - zamanlar
        if bool((sure > adim).any()):
            raise ValueError("mumlar_4h 4h serisi olmali: bar suresi 4 saati asiyor (1d cercevesi verilmis olabilir; "
                             "on-kayit §4 'Fiyat okuma tabani').")
    if len(zamanlar) > 1 and (zamanlar[1:] - zamanlar[:-1]).min() != adim:
        raise ValueError("mumlar_4h 4h serisi olmali: ardisik acilislar arasinda 4 saatlik fark yok "
                         "(1d cercevesi verilmis olabilir; on-kayit §4 'Fiyat okuma tabani').")
    return zamanlar


def _bar_degeri(mumlar: pd.DataFrame, zamanlar: pd.DatetimeIndex, zaman: pd.Timestamp, alan: str) -> float:
    bar = pencere_modulu.ayni_andaki_bar(zamanlar, zaman)
    if bar is None:
        raise ValueError(f"{zaman} bari mum cercevesinde yok (karar ile ayni seri verilmeli).")
    return float(mumlar[alan].to_numpy()[int(zamanlar.get_loc(bar))])


def olay_karari(
    mumlar_4h: pd.DataFrame,
    funding: pd.DataFrame,
    sinyal_zamani,
    ufuk: int,
    bar: str,
    *,
    hipotez: str,
    birincil_ufuk: int,
    kume_baslangic,
    kume_bitis,
    donem_baslangic,
    donem_bitis,
    sinyal_degerleri: Mapping[str, float],
    gunluk_mumlar: pd.DataFrame,
    asgari_hacim,
    asgari_listeleme_yasi_gun,
) -> OnaylanmisPozisyon:
    """TEK KARAR NOKTASI (on-kayit §4 rev.8, rev.9). Olay ya da kontrol olusursa
    `OnaylanmisPozisyon`, olusmazsa `OlayOlusmaz` alt sinifi (ret gerekcesi:
    `pencere.ret_gerekcesi`). Olaylar ve kontroller ayni cagriyi kullanir.

    `mumlar_4h`: sembolun donem ici 4h mumlari (her izgarada; `open_time`, `open`,
    `high`, `low`, `close`). `funding`: veri katmaninin funding cercevesi
    (`funding.funding_yukle`). `sinyal_degerleri`: sinyal barinda hesaplanan pencere
    degerleri (ad -> deger); bos olamaz. `gunluk_mumlar`: sembolun 1d serisi (uygunluk
    hacmi; `klines.mumlari_yukle(s, "1d", ...)`). `asgari_hacim`, `asgari_listeleme_yasi_gun`:
    uygunluk esikleri, on-kayit §2 degerleri olmalidir (`eligibility.esikleri_dogrula`).
    `hipotez` ("H1", "H2", "H3") zorunludur: `bar`, `ufuk` ve `birincil_ufuk` hipotezden tureyen on-kayit
    degerleriyle uyumlu olmalidir (`pencere.hipotez_baglamini_dogrula`; F2 kodu bunlari
    `pencere.hipotez_ufuklari`ndan okur). Onayli pozisyon hipotezi imzali tasir.
    Butun sinirlar ve esikler zorunlu anahtar sozcuktur; varsayilan yoktur.
    """
    # Hipotez -> izgara -> ufuk bagi (on-kayit §4 "Ufuk degerlerinin baglanmasi", rev.10; F1 kapanis
    # turu, denetci D-B2): izgara ve ufuklar hipotezden turer; uyumsuz eslesme calisma aninda hata.
    pencere_modulu.hipotez_baglamini_dogrula(hipotez, bar, ufuk, birincil_ufuk)
    if not isinstance(sinyal_degerleri, Mapping) or not sinyal_degerleri:
        raise TypeError("sinyal_degerleri bos olmayan bir eslem olmali (sinyal barindaki pencere degerleri).")
    # Bool bir pencere degeri degil kosul sonucudur; `not (x < y)` gibi olumsuzlanmis bir kosul NaN
    # pencereyi True ile gizleyebilir (denetci bulgusu D-C1). Programlama hatasi: TypeError.
    mantiksal = [ad for ad, deger in sinyal_degerleri.items() if isinstance(deger, (bool, np.bool_))]
    if mantiksal:
        raise TypeError(f"sinyal_degerleri bool kabul etmez (pencere degeri verilmeli, kosul sonucu degil): {mantiksal}")
    # Enum uyesi (IntEnum, IntFlag, float karisimli Enum) de bir kosul sonucu tasiyabilir ve sayi gibi
    # gecer; bool ile ayni gerekceyle reddedilir (sizinti testcisinin Rev.10 hazirlik bulgusu 3).
    numaralandirma = [ad for ad, deger in sinyal_degerleri.items() if isinstance(deger, enum.Enum)]
    if numaralandirma:
        raise TypeError(f"sinyal_degerleri enum uyesi kabul etmez (pencere degeri verilmeli, kosul sonucu "
                        f"degil): {numaralandirma}")
    eksik = [ad for ad, deger in sinyal_degerleri.items()
             if deger is None or not isinstance(deger, (int, float, np.integer, np.floating)) or not math.isfinite(deger)]
    if eksik:
        raise SinyalPenceresiTamDegil(f"Sinyal penceresi tam degil: {eksik} (on-kayit §2 'Tamlik sarti').")
    # Uygunluk girdileri her cagrida denetlenir (programlama hatasi, ret gerekcesi degil).
    eligibility_modulu.esikleri_dogrula(bar, asgari_hacim=asgari_hacim,
                                        asgari_listeleme_yasi_gun=asgari_listeleme_yasi_gun)
    gunluk_hacim = _gunluk_hacim(gunluk_mumlar)

    zamanlar = _mum_zamanlari(mumlar_4h)
    plan = pencere_modulu.pozisyon_plani(
        zamanlar, sinyal_zamani, ufuk, bar, birincil_ufuk=birincil_ufuk, kume_baslangic=kume_baslangic,
        kume_bitis=kume_bitis, donem_baslangic=donem_baslangic, donem_bitis=donem_bitis)
    # Uygunluk (on-kayit §4 rev.9): esik gecilmeli, hesaplanabilmis olmasi yetmez.
    if not eligibility_modulu.uygunluk_karari(
            gunluk_hacim, plan.sinyal_zamani, bar, donem_baslangic=plan.donem_baslangic,
            donem_bitis=plan.donem_bitis, kume_baslangic=plan.kume_baslangic, asgari_hacim=asgari_hacim,
            asgari_listeleme_yasi_gun=asgari_listeleme_yasi_gun):
        raise UygunDegil(f"Sinyal bari {plan.sinyal_zamani} ({bar}) uygun degil: listeleme yasi ya da medyan "
                         "hacim esigi gecilmiyor (on-kayit §2 'Uygunluk').")
    ayrinti = funding_modulu.pozisyon_funding_ayrintisi(funding, plan)
    if not bool(ayrinti["tam"]):
        raise FundingTamDegil(f"Pozisyonun funding'i tam degil: giris {plan.giris}, cikis {plan.cikis_ani} "
                              f"({plan.cikis_turu}); olay brut dahil hicbir hesapta olusmaz.")
    toplam = funding_modulu.pozisyon_fundingi(funding, plan)
    if math.isnan(toplam):
        raise FundingTamDegil(f"Pozisyonun funding'i hesaplanamadi (oran NaN): giris {plan.giris}.")
    p0 = _bar_degeri(mumlar_4h, zamanlar, plan.giris, "open")
    p1 = _bar_degeri(mumlar_4h, zamanlar, plan.cikis.zaman, plan.cikis.fiyat_alani)
    sonuc = OnaylanmisPozisyon(plan, p0, p1, toplam, kuyruk_kismi=bool(ayrinti["kuyruk_kismi"]),
                               son_esitlik_affi=bool(ayrinti["son_esitlik_affi"]),
                               capa_aralik_saat=float(ayrinti["capa_aralik_saat"]),
                               son_aralik_saat=float(ayrinti["son_aralik_saat"]), tek_ritim=bool(ayrinti["tek_ritim"]),
                               funding_ritmi_saat=float(ayrinti["funding_ritmi_saat"]),
                               karisik_ritim=bool(ayrinti["karisik_ritim"]),
                               ritim_sinifi=ayrinti["ritim_sinifi"], hipotez=hipotez)
    return replace(sonuc, _imza=_imza(sonuc))


def pozisyon_fiyatlari(pozisyon) -> tuple[float, float]:
    """(P0, P1): brut getirinin tek girdisi. Yalnizca `olay_karari` ciktisini kabul eder."""
    onay_dogrula(pozisyon)
    return pozisyon.p0, pozisyon.p1


def mae(mumlar_4h: pd.DataFrame, pozisyon) -> float:
    """En kotu ara zarar (on-kayit §4 rev.8 "MAE"): `max(H, P1) / P0 - 1`.

    "H, acilisi giris anindan once olmayan ve kapanisi cikis anindan sonra olmayan
    butun donem ici 4h barlarin en yuksek high degeridir; boyle bar yoksa yalnizca P1
    kullanilir. Izgaradan bagimsiz olarak 4h barlardan hesaplanir." Zaman
    karsilastirmalari "Zaman toleransi"na gore. Eksik barlar MAE'yi hesaplanamaz
    yapmaz (bosluk suresince ara zarar gozlenemez; rapor bu siniri yazar).
    Yalnizca `olay_karari` ciktisini kabul eder; `mumlar_4h` kararla ayni seri
    olmalidir. Saf; raporlanir, esik degildir.
    """
    onay_dogrula(pozisyon)
    plan = pozisyon.plan
    zamanlar = _mum_zamanlari(mumlar_4h)
    kapanislar = zamanlar + pencere_modulu.ADIM_4H
    secim = (np.asarray(pencere_modulu.ayni_ya_da_sonra(zamanlar, plan.giris), dtype=bool)
             & np.asarray(pencere_modulu.ayni_ya_da_once(kapanislar, plan.cikis_ani), dtype=bool)
             & np.asarray(pencere_modulu.donem_ici_4h_maskesi(
                 zamanlar, donem_baslangic=plan.donem_baslangic, donem_bitis=plan.donem_bitis), dtype=bool))
    tepe = pozisyon.p1
    if secim.any():
        tepe = max(float(np.max(mumlar_4h["high"].to_numpy(dtype=float)[secim])), pozisyon.p1)
    return tepe / pozisyon.p0 - 1
