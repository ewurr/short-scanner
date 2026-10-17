"""Bulgu K-C8 (koruma turu madde 7): bar duzeyli olcut seriden bar dusurunce 4h seri denetimi
veri hatasina duser mi?

Denetci bunu SUPHELI olarak isaretledi: `pozisyon._tam_hucreli_barlar` (D-B3) bozuk hucreli
barlari seriden dusurur; `_mum_zamanlari` ise "ardisik acilislar arasinda 4 saatlik fark olmali"
diye bakiyordu. Dar bir donemde geriye yalnizca birbirine KOMSU OLMAYAN barlar kalirsa bu denetim
`VeriHatasi` firlatir -- yani bir RET GEREKCESI (olay olusmaz) degil, yukari cikan bir hata. Ayni
bar eksikliginin normal yolu ret gerekcesidir.

Bugunku veride bozuk hucre sayisi 0 (RESULTS §14.32), bu yuzden durum gozlenemez; test SENTETIK
seriyle sinar.

Sonuc: durum URETILEBILIYOR (asagidaki ilk test, duzeltme oncesi `VeriHatasi` veriyordu).
Duzeltme: 4h serisi oldugunu dogrulayan asil olcut IZGARA ve BAR SURESIDIR; ardisiklik yalnizca
`close_time` yoksa gereklidir (o zaman sureyi olcemeyiz). Boylece eksik barli seri "veri hatasi"
degil "bar yok" yoluna duser ve 1d cercevesinin 4h gibi verilmesi yine yakalanir.

Aga cikmaz; getiri hesaplanmaz.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import config
from data import pencere, pozisyon
from kapi_yardimcisi import veri
from sinyal_yardimcisi import kontrol
from uygunluk_yardimcisi import esikler

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H = lambda n: pd.Timedelta(hours=n)  # noqa: E731

DB, B = T("2025-01-01"), T("2025-06-30 20:00")
Z = pd.date_range(DB, B, freq="4h")   # 180 barlik hacim penceresi icin yeterli gecmis
FUND = pd.DataFrame({"odeme_zamani": pd.date_range(DB, B + H(4), freq="8h"), "aralik_saat": 8.0,
                     "oran": 1e-4, "oran_8h": 1e-4})
T_SINYAL = T("2025-03-10 04:00")


def _mum(bozuk_maske=None) -> pd.DataFrame:
    """4h seri; `bozuk_maske` True olan barlarin `volume` hucresi NaN (bar duzeyli olcut duser)."""
    cerceve = pd.DataFrame({"open_time": Z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
                            "close_time": Z + H(4) - pd.Timedelta(milliseconds=1),
                            "volume": 10.0, "quote_volume": 1e7, "count": 10,
                            "taker_buy_volume": 5.0, "taker_buy_quote_volume": 5e6})
    if bozuk_maske is not None:
        cerceve.loc[np.asarray(bozuk_maske), "volume"] = np.nan
    return cerceve


def _karar(mum, hipotez="H1"):
    tanim = pencere.hipotez_ufuklari(hipotez)
    return pozisyon.olay_karari(T_SINYAL, tanim.birincil, tanim.bar, hipotez=hipotez,
                                birincil_ufuk=tanim.birincil, kume="KESIF",
                                **veri(mum, FUND, DB, B, uygun_bas=DB, ham=True), **kontrol(hipotez),
                                **esikler(tanim.bar))


# --- 1. Durumun kendisi: her ikinci bar bozuk ------------------------------------------------


def test_her_ikinci_bar_bozukken_veri_hatasi_degil_olay_dusmesi():
    """K-C8'in sentetik uretimi: geriye yalnizca 8 saat arayla barlar kalir.

    `min(fark) == 8h` oldugu icin ardisiklik denetimi `VeriHatasi` veriyordu. Dogru sonuc bir RET
    GEREKCESIDIR: giris bari seride yok (`GirisBariYok`) ya da pencere tam degil."""
    bozuk = np.zeros(len(Z), dtype=bool)
    bozuk[1::2] = True
    with pytest.raises(pencere.OlayOlusmaz):
        _karar(_mum(bozuk))


def test_butun_barlar_bozukken_de_olay_dusmesi():
    with pytest.raises(pencere.OlayOlusmaz):
        _karar(_mum(np.ones(len(Z), dtype=bool)))


def test_yalniz_tek_bar_kalirsa_olay_dusmesi():
    bozuk = np.ones(len(Z), dtype=bool)
    bozuk[5] = False
    with pytest.raises(pencere.OlayOlusmaz):
        _karar(_mum(bozuk))


def test_saglam_seride_onay_olusur():
    """Olumlu kontrol: duzeltme mesru yolu kapatmadi."""
    p = _karar(_mum())
    assert p.p0 > 0 and p.p1 > 0


# --- 2. `_mum_zamanlari`in asil gorevi korundu: 1d cercevesi 4h gibi verilemez ---------------


def test_gunluk_cerceve_hala_reddedilir():
    """`_mum_zamanlari`in amaci 1d cercevesinin 4h gibi verilmesini yakalamakti (D-B3).

    Gunluk barlarin suresi 4 saati asar: olcut BAR SURESIDIR, ardisiklik degil."""
    gunler = pd.date_range(T("2025-03-01"), T("2025-04-30"), freq="D")
    gunluk = pd.DataFrame({"open_time": gunler, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
                           "close_time": gunler + pd.Timedelta(days=1) - pd.Timedelta(milliseconds=1),
                           "volume": 10.0, "quote_volume": 1e7, "count": 10,
                           "taker_buy_volume": 5.0, "taker_buy_quote_volume": 5e6})
    with pytest.raises(pencere.VeriHatasi, match="4h serisi"):
        pozisyon._mum_zamanlari(gunluk)


def test_izgara_disi_acilis_hala_reddedilir():
    bozuk = _mum()
    bozuk.loc[:, "open_time"] = bozuk["open_time"] + H(1)
    with pytest.raises(pencere.VeriHatasi, match="izgarasinda degil"):
        pozisyon._mum_zamanlari(bozuk)


def test_close_time_yoksa_ardisiklik_hala_aranir():
    """`close_time` yoksa bar suresi olculemez; o zaman ardisiklik TEK olcuttur ve korunur."""
    seyrek = _mum().iloc[::2].drop(columns=["close_time"]).reset_index(drop=True)
    with pytest.raises(pencere.VeriHatasi, match="4h serisi"):
        pozisyon._mum_zamanlari(seyrek)
    tek = _mum().iloc[[0]].drop(columns=["close_time"]).reset_index(drop=True)
    with pytest.raises(pencere.VeriHatasi, match="dogrulanamiyor"):
        pozisyon._mum_zamanlari(tek)


def test_eksik_barli_4h_serisi_kabul_edilir():
    """Bar duzeyli olcutun birakacagi seri: izgarada, suresi 4 saat, ama ardisik DEGIL."""
    seyrek = _mum().iloc[::3].reset_index(drop=True)
    zamanlar = pozisyon._mum_zamanlari(seyrek)
    assert len(zamanlar) == len(seyrek)


def test_bos_cerceve_bos_indeks_verir():
    assert len(pozisyon._mum_zamanlari(_mum().iloc[:0])) == 0
