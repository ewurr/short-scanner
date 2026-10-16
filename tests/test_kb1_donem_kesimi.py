"""Bulgu K-B1, ikinci parca: `sinyal_kosulu` veriyi DONEME de keser (madde 3a).

On-kayit §2 "Listeleme donemi": "Donem dışındaki hiçbir bar ... hiçbir hesaba girmez."

Bulgu: `pozisyon.sinyal_kosulu` veriyi yalnizca KUME araligina kesiyordu (`_kume_verisi(sembol,
kume, kume_baslangic, kume_bitis)`). Dönem bitisinden SONRAKI bir t icin kosul hesaplanabiliyordu
ve penceresi dönemler arasi barlari (dolgu barlari, sonraki dönemin barlari) icerebiliyordu. Bu
yalnizca "bos bir hesap" degildi: kosulun sonucu DIZI DURUMUNU degistirir (H1'in izlemesi, H3'un
dizisi), cunku rev.13'ten beri dizi kosullarla tanimlidir, kapinin onayiyla degil. Yani dönem disi
bir bar, kendisi olay olmasa bile sonraki gecerli barin "ilk gun" ya da "yeni pump bari" sayilip
sayilmayacagini degistirebiliyordu.

Testler sentetik iki donemli bir sembol kurar: donem 0 ve donem 1 arasinda bir bosluk vardir ve
donem 1'in barlari donem 0'in penceresine girerse deger degisir.

Aga cikmaz; getiri hesaplanmaz.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import config
from data import pozisyon, sinyal
from kapi_yardimcisi import veri
from sinyal_yardimcisi import yapilandirma
from uygunluk_yardimcisi import esikler

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
HACIM = 5e7

# Donem 0: 2025-03-01 .. 2025-04-30 20:00. Sonrasindaki barlar BASKA bir donemdedir.
D0_BAS, D0_SON = T("2025-03-01"), T("2025-04-30 20:00")
SON_BAR = D0_SON
Y2 = yapilandirma("H2")


def _seri(bas, son, *, dip_kat: float = 1.0) -> pd.DataFrame:
    z = pd.date_range(bas, son, freq="4h")
    cerceve = pd.DataFrame({"open_time": z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
                            "quote_volume": HACIM / 6})
    return cerceve


def _funding(bas, son) -> pd.DataFrame:
    z = pd.date_range(bas, son, freq="8h")
    return pd.DataFrame({"odeme_zamani": z, "aralik_saat": 8.0, "oran": 1e-4, "oran_8h": 1e-4})


def _kayit(mumlar):
    """Donem 0 kaydi; seri donem BITISINDEN SONRA da barlar tasiyabilir (kume araligi daha genis)."""
    return veri(mumlar, _funding(D0_BAS, D0_SON + 30 * H4), D0_BAS, D0_SON, uygun_bas=D0_BAS,
                hacim=6 * HACIM)


def _kosul(t, kayit, capa=None):
    return pozisyon.sinyal_kosulu(t, hipotez="H2", yapilandirma=Y2, capa=capa, kume="KESIF", **kayit)


# --- 1. Donem bitisinden sonraki t: kosul hesaplanamaz ---------------------------------------


@pytest.mark.parametrize("kaydirma", [1, 2, 6, 30])
def test_donem_bitisinden_sonraki_bar_icin_kosul_hesaplanamaz(kaydirma):
    """Seride bar VAR (kume araligi devam ediyor) ama bar donem disi: deger hesaplanamaz -> None."""
    mumlar = _seri(D0_BAS, D0_SON + 40 * H4)
    kayit = _kayit(mumlar)
    t = SON_BAR + kaydirma * H4
    assert _kosul(t, kayit) is None, kaydirma


def test_donem_ici_son_bar_icin_kosul_hesaplanir():
    """Olumlu kontrol: donemin son bari icin kosul HESAPLANIR (True/False), None degil."""
    mumlar = _seri(D0_BAS, D0_SON + 40 * H4)
    kayit = _kayit(mumlar)
    assert _kosul(SON_BAR, kayit) in (True, False)


def test_donem_baslangicindan_onceki_bar_icin_kosul_hesaplanamaz():
    mumlar = _seri(D0_BAS - 40 * H4, D0_SON)
    kayit = _kayit(mumlar)
    assert _kosul(D0_BAS - 2 * H4, kayit) is None


# --- 2. Donem disi barlar PENCEREYE girmez ---------------------------------------------------


def test_donem_disi_barlar_pencere_degerini_degistirmez():
    """Ayni donem ici seri, donem sonrasi barlari FARKLI olan iki kayit: ayni sonuc.

    Donem disi barlar hesaba girseydi, dip/tepe pencereleri degisir ve kosul sonucu kayardi.
    """
    ici = _seri(D0_BAS, D0_SON)
    sade = ici.copy()
    sonrasi = _seri(D0_SON + H4, D0_SON + 40 * H4)
    sonrasi.loc[:, ["open", "high", "low", "close"]] = 99.0      # pencereyi bozacak kadar farkli
    bozuk = pd.concat([ici, sonrasi], ignore_index=True)

    t = SON_BAR
    a = _kosul(t, _kayit(sade))
    b = _kosul(t, _kayit(bozuk))
    assert a == b, (a, b)


def test_h2_funding_penceresi_donem_disi_odemeleri_gormez():
    """H2'nin funding penceresi (24 saat) donem bitisine dayanan bir t'de donem disina uzamaz."""
    mumlar = _seri(D0_BAS, D0_SON + 40 * H4)
    kayit = veri(mumlar, _funding(D0_BAS, D0_SON + 40 * H4), D0_BAS, D0_SON, uygun_bas=D0_BAS,
                 hacim=6 * HACIM)
    # Donem icindeki son bar: pencere tamamen donem icinde, deger hesaplanir.
    assert _kosul(SON_BAR, kayit) in (True, False)
    # Donem disindaki ilk bar: hic hesaplanmaz.
    assert _kosul(SON_BAR + H4, kayit) is None


# --- 3. Dizi durumu: donem disi bar diziyi etkilemez -----------------------------------------


def test_kosul_donem_disinda_hesaplanamaz_oldugu_icin_dizi_durumu_degismez():
    """K-B1'in zararli yolu: dönem disi bar kosulu "saglandi" verirse H1 izlemesi ya da H3 dizisi
    degisir. Artik `None` geldigi icin dizi o bari hesaplanamaz sayar (`sinyal_penceresi_tam_degil`)."""
    mumlar = _seri(D0_BAS, D0_SON + 40 * H4)
    kayit = _kayit(mumlar)
    sonuclar = [_kosul(SON_BAR + k * H4, kayit) for k in range(1, 11)]
    assert all(s is None for s in sonuclar), sonuclar
