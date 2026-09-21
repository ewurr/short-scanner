"""Tek karar noktasi: bir olay ya da kontrol olusur mu? (on-kayit §4 rev.8)

On-kayit §4 rev.8 "Olayin kumede olusma olcutu": "Bir olayin kumede olusup
olusmadigina tek bir karar noktasi hukmeder ... Ayni karar noktasinda pozisyonun
funding tamligi da saglanmalidir: funding'i tam olmayan olay ya da kontrol, brut
getiri dahil hicbir hesapta olusmaz. Boylece brut ve net olay kumeleri her zaman
aynidir. Fiyat ve funding icin ayri olcut kullanilmaz."

`olay_karari` bu karar noktasidir. Sirasiyla:
  1. Sinyal pencerelerinin tamligi: cagiranin hesapladigi pencere degerlerinden biri
     NaN ise `SinyalPenceresiTamDegil` (on-kayit §2 "Tamlik sarti").
  2. `pencere.pozisyon_plani`: sinyal kumede ve donem ici, giris bari, cikis (donem
     sonu / olagan / ileri kayma ve siniri), gercek cikis ani + tolerans <= kume sonu.
  3. Funding tamligi (`funding.pozisyon_funding_tam_mi`) -> `FundingTamDegil`.
Karar olumluysa `OnaylanmisPozisyon` doner: plan, P0, P1 ve funding toplami. Brut
getiri, net getiri, MAE ve K1/K2 kontrolleri YALNIZCA bu ciktiyi kullanir;
`pozisyon_fiyatlari` ve `mae` baska girdi kabul etmez. Ayri bir kapi yoktur.

Getiri HESAPLAMAZ (F2 kodu degildir); fiyat ve funding degerlerini tasir ama
raporlamaz. Saf fonksiyonlar.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

from data import funding as funding_modulu
from data import pencere as pencere_modulu


class SinyalPenceresiTamDegil(pencere_modulu.OlayOlusmaz):
    """Sinyal pencerelerinden biri tam degil (NaN) (on-kayit §2 "Tamlik sarti")."""

    gerekce = "sinyal_penceresi_tam_degil"


class FundingTamDegil(pencere_modulu.OlayOlusmaz):
    """Pozisyonun funding'i tam degil (on-kayit §4 rev.8 "Funding araligi gecisleri");
    olay ya da kontrol brut dahil hicbir hesapta olusmaz."""

    gerekce = "funding_tam_degil"


_ONAY_GIZLI = object()


@dataclass(frozen=True)
class OnaylanmisPozisyon:
    """Tek karar noktasindan gecmis pozisyon. Yalnizca `olay_karari` uretir.

    `p0`: giris barinin acilisi; `p1`: cikis barinin `plan.cikis.fiyat_alani`
    alani; `funding_toplami`: pozisyonun funding'i (on-kayit §4). Degerler raporlanmaz.
    """

    plan: pencere_modulu.PozisyonPlani
    p0: float
    p1: float
    funding_toplami: float
    _imza: int = field(default=0, repr=False, compare=False)

    @property
    def cikis_turu(self) -> str:
        return self.plan.cikis_turu


def _imza(p: OnaylanmisPozisyon) -> int:
    return hash((_ONAY_GIZLI, p.plan, p.p0, p.p1, p.funding_toplami))


def onay_dogrula(pozisyon) -> None:
    """`olay_karari`nin urettigi ve degistirilmemis bir pozisyon mu?"""
    if not isinstance(pozisyon, OnaylanmisPozisyon):
        raise TypeError(f"Onaylanmis pozisyon gerekir (pozisyon.olay_karari ciktisi); verilen: {type(pozisyon).__name__}")
    if pozisyon._imza != _imza(pozisyon):
        raise ValueError("OnaylanmisPozisyon elle kurulmus ya da degistirilmis; yalnizca olay_karari uretir.")


def _mum_zamanlari(mumlar: pd.DataFrame) -> pd.DatetimeIndex:
    return pencere_modulu._zaman_dizisi_dogrula(pd.DatetimeIndex(mumlar["open_time"]), "olay_karari")


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
    birincil_ufuk: int,
    kume_baslangic,
    kume_bitis,
    donem_baslangic,
    donem_bitis,
    sinyal_degerleri: Mapping[str, float],
) -> OnaylanmisPozisyon:
    """TEK KARAR NOKTASI (on-kayit §4 rev.8). Olay ya da kontrol olusursa
    `OnaylanmisPozisyon`, olusmazsa `OlayOlusmaz` alt sinifi (ret gerekcesi:
    `pencere.ret_gerekcesi`).

    `mumlar_4h`: sembolun donem ici 4h mumlari (her izgarada; `open_time`, `open`,
    `high`, `low`, `close`). `funding`: veri katmaninin funding cercevesi
    (`funding.funding_yukle`). `sinyal_degerleri`: sinyal barinda hesaplanan pencere
    degerleri (ad -> deger; kontrollerde uygunluk hacmi); bos olamaz. Butun sinirlar
    zorunlu anahtar sozcuktur.
    """
    if not isinstance(sinyal_degerleri, Mapping) or not sinyal_degerleri:
        raise TypeError("sinyal_degerleri bos olmayan bir eslem olmali (pencere degerleri; kontrollerde uygunluk).")
    eksik = [ad for ad, deger in sinyal_degerleri.items()
             if deger is None or not isinstance(deger, (int, float, np.integer, np.floating)) or not math.isfinite(deger)]
    if eksik:
        raise SinyalPenceresiTamDegil(f"Sinyal penceresi tam degil: {eksik} (on-kayit §2 'Tamlik sarti').")

    zamanlar = _mum_zamanlari(mumlar_4h)
    plan = pencere_modulu.pozisyon_plani(
        zamanlar, sinyal_zamani, ufuk, bar, birincil_ufuk=birincil_ufuk, kume_baslangic=kume_baslangic,
        kume_bitis=kume_bitis, donem_baslangic=donem_baslangic, donem_bitis=donem_bitis)
    if not funding_modulu.pozisyon_funding_tam_mi(funding, plan):
        raise FundingTamDegil(f"Pozisyonun funding'i tam degil: giris {plan.giris}, cikis {plan.cikis_ani} "
                              f"({plan.cikis_turu}); olay brut dahil hicbir hesapta olusmaz.")
    toplam = funding_modulu.pozisyon_fundingi(funding, plan)
    if math.isnan(toplam):
        raise FundingTamDegil(f"Pozisyonun funding'i hesaplanamadi (oran NaN): giris {plan.giris}.")
    p0 = _bar_degeri(mumlar_4h, zamanlar, plan.giris, "open")
    p1 = _bar_degeri(mumlar_4h, zamanlar, plan.cikis.zaman, plan.cikis.fiyat_alani)
    sonuc = OnaylanmisPozisyon(plan, p0, p1, toplam)
    return replace(sonuc, _imza=_imza(sonuc))


def pozisyon_fiyatlari(pozisyon) -> tuple[float, float]:
    """(P0, P1): brut getirinin tek girdisi. Yalnizca `olay_karari` ciktisini kabul eder."""
    onay_dogrula(pozisyon)
    return pozisyon.p0, pozisyon.p1
