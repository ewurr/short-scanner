"""Denetci bulgusu D-C2: `pozisyon.sinyal_kosulu`nun yakalamasi daraltildi.

Bulgu: `sinyal_kosulu`, H1'in tepe penceresi kurulamadiginda kosulu "hesaplanamaz" (`None`) sayar
ve bunu GENIS bir `except ValueError` ile yakaliyordu. `pencere.VeriHatasi` ve
`pencere.ZamanDizisiHatasi` da `ValueError` alt siniflari oldugu icin bir VERI HATASI da sessizce
ret gerekcesine ceviriliyordu. On-kayit §2 "Tamlik sarti" eksik veriyi "deger hesaplanamaz" sayar;
BOZUK veri (siralanmamis / tekrarli zaman dizisi, bicim hatasi) ise bir kurali degil kodun ya da
verinin hatasini gosterir ve yukari cikmalidir -- `pencere.VeriHatasi` aciklamasindaki tutum.

Cozum: tepe penceresinin TANIMSIZ oldugu durum kendi sinifini aldi
(`sinyal.TepePenceresiKurulamaz`) ve `sinyal_kosulu` yalnizca onu yakaliyor.

Aga cikmaz; getiri hesaplanmaz.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import pencere, pozisyon, sinyal
from kapi_yardimcisi import veri
from sinyal_yardimcisi import yapilandirma
from uygunluk_yardimcisi import esikler  # noqa: F401  (kapi yardimcilariyla ayni yol)

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
DB, B = T("2024-09-01"), T("2025-06-30 20:00")
T1 = T("2025-03-10 04:00")
HACIM = 1e7


def _duz(bas, son, hacim=6 * HACIM):
    z = pd.date_range(bas, son, freq="4h")
    return pd.DataFrame({"open_time": z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
                         "quote_volume": hacim / 6})


def _fund(bas, son):
    z = pd.date_range(bas, son, freq="8h")
    return pd.DataFrame({"odeme_zamani": z, "aralik_saat": 8.0, "oran": 0.0, "oran_8h": 0.0})


# --- 1. Tepe penceresi TANIMSIZ: kendi sinifi --------------------------------------------------


def test_tepe_penceresi_kurulamaz_kendi_sinifidir():
    """Sinif `ValueError` alt sinifidir (geriye donuk uyumluluk) ama `pencere.VeriHatasi`
    ailesinden AYRIDIR: ikisi ayni yoldan yakalanamaz."""
    assert issubclass(sinyal.TepePenceresiKurulamaz, ValueError)
    assert not issubclass(sinyal.TepePenceresiKurulamaz, pencere.VeriHatasi)
    assert not issubclass(pencere.VeriHatasi, sinyal.TepePenceresiKurulamaz)


@pytest.mark.parametrize("fark_bar", [0, -1, -12, config.H1_IZLEME_BAR + 1, config.H1_IZLEME_BAR + 5])
def test_izleme_penceresi_disindaki_teyit_bari_tepe_penceresi_kurulamaz(fark_bar):
    """On-kayit §5 H1 madde 2-3: teyit bari pump barindan SONRA ve en fazla 12 bar sonra olmali."""
    mumlar = _duz(DB, B)
    pump = T1
    teyit = pump + fark_bar * H4
    with pytest.raises(sinyal.TepePenceresiKurulamaz):
        sinyal.h1_tepe(mumlar, pump, teyit, kume_baslangic=None, donem_baslangic=DB)


@pytest.mark.parametrize("fark_bar", [1, 2, config.H1_IZLEME_BAR])
def test_izleme_penceresi_icindeki_teyit_bari_tepeyi_kurar(fark_bar):
    """Sinir: tam 12 bar sonrasi hala izleme icindedir (on-kayit §5 H1 madde 3)."""
    mumlar = _duz(DB, B)
    tepe = sinyal.h1_tepe(mumlar, T1, T1 + fark_bar * H4, kume_baslangic=None, donem_baslangic=DB)
    assert tepe == pytest.approx(1.0)


def test_izgara_disi_teyit_bari_da_tepe_penceresi_kurulamaz():
    with pytest.raises(sinyal.TepePenceresiKurulamaz):
        sinyal.h1_tepe(_duz(DB, B), T1, T1 + pd.Timedelta(hours=2), kume_baslangic=None,
                       donem_baslangic=DB)


# --- 2. `sinyal_kosulu` yalnizca bu sinifi yutar -----------------------------------------------


def _h1_ortak():
    kayit = veri(_duz(DB, B), _fund(DB, B + H4), DB, B, uygun_bas=DB, hacim=6 * HACIM)
    return dict(hipotez="H1", yapilandirma=yapilandirma("H1"), kume="KESIF", **kayit)


def test_izleme_disindaki_teyit_adayi_kosul_hesaplanamaz():
    """Davranis KORUNDU: tepe penceresi tanimsizken kosul `None` (hesaplanamaz)."""
    ortak = _h1_ortak()
    uzak_capa = T1 - (config.H1_IZLEME_BAR + 3) * H4
    assert pozisyon.sinyal_kosulu(T1, capa=uzak_capa, **ortak) is None
    # Izleme icindeki capa ile kosul HESAPLANIR (True/False, None degil).
    yakin_capa = T1 - 2 * H4
    assert pozisyon.sinyal_kosulu(T1, capa=yakin_capa, **ortak) in (True, False)


@pytest.mark.parametrize("hata", [pencere.VeriHatasi("bozuk veri"),
                                  pencere.ZamanDizisiHatasi("siralanmamis zaman dizisi"),
                                  ValueError("duz cagri hatasi"),
                                  TypeError("yanlis tur")])
def test_veri_hatasi_ret_gerekcesine_cevrilmez(monkeypatch, hata):
    """D-C2: `sinyal_degerleri`den gelen bir VERI HATASI yukari cikmali, `None` olmamali."""
    ortak = _h1_ortak()

    def patla(*a, **k):
        raise hata

    monkeypatch.setattr(sinyal, "sinyal_degerleri", patla)
    with pytest.raises(type(hata)):
        pozisyon.sinyal_kosulu(T1, capa=T1 - 2 * H4, **ortak)


def test_tepe_penceresi_hatasi_yine_yutulur(monkeypatch):
    """Daraltma, kuralin kendisini degistirmedi: `TepePenceresiKurulamaz` hala `None` olur."""
    ortak = _h1_ortak()

    def patla(*a, **k):
        raise sinyal.TepePenceresiKurulamaz("tepe penceresi tanimsiz")

    monkeypatch.setattr(sinyal, "sinyal_degerleri", patla)
    assert pozisyon.sinyal_kosulu(T1, capa=T1 - 2 * H4, **ortak) is None
