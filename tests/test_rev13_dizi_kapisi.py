"""Olay uretimi `data.dizi`den gecer ve kapinin ciktisi dogrulanir (sizinti bulgusu S-B1).

On-kayit §4 "Olayin kumede olusma olcutu" (rev.12): "Tek karar noktasinin onayi, bir olayin
olusmasi icin GEREKLIDIR ama YETERLI DEGILDIR: §5'teki dizi kurallari (bekleme suresi, H1'de tek
izleme, H3'te ilk gun) da saglanmalidir. Olay kumesi yalnizca iki kosulun birlikte saglandigi
barlardan olusur; dizi kurallarindan gecmemis bir onay olay DEGILDIR ve hicbir hesaba, hicbir
kontrol olcutune girmez."

Iliski iki yonludur ve bu dosya ikisini birlikte sabitler:
  (1) Dizi -> kapi: `dizi.olay_dizisi` donen nesnenin gercekten kapidan gecmis, imzali, "olay"
      rolunde ve SORULAN (t, capa) ciftine ait bir onay oldugunu dogrular (`dizi._olay_dogrula`).
      Rev.13'ten once bu denetim yoktu; `karar`in dondurdugu her nesne olay sayiliyor ve kendi
      beklemesini baslatiyordu.
  (2) Kapi -> dizi: olay tipi (`dizi.Olay`) yalnizca `dizi.olay_dizisi`den cikar; analiz kodunun
      olay uretim yolunun `dizi`den gectigini bir KAYNAK TARAMASI da dogrular (ikincil savunma,
      asagida ve `tests/test_rev13_tarama.py`de).

Aga cikmaz; getiri hesaplanmaz.
"""

from __future__ import annotations

import dataclasses

import pandas as pd
import pytest

import config
from data import dizi, pencere, pozisyon
from sinyal_yardimcisi import yapilandirma

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
BARLAR = pd.date_range(T("2025-03-01 00:00"), periods=30, freq="4h")
Y2 = yapilandirma("H2")


def _calistir(karar, *, hipotez="H2", y=None, kosul=None, idxler=range(5)):
    bar = config.HIPOTEZ_IZGARASI[hipotez]
    izgara = BARLAR if bar == config.BAR_4H else pd.date_range(T("2025-03-01"), periods=30, freq="D")
    return dizi.olay_dizisi(hipotez, y if y is not None else yapilandirma(hipotez),
                            izgara[list(idxler)], bar, birincil_ufuk=config.BIRINCIL_UFUK[bar],
                            kosul=kosul if kosul is not None else (lambda t, capa: True), karar=karar)


def _onay(t, capa=None, **ek):
    return pozisyon._test_onayi(hipotez="H2", yapilandirma=Y2, t=t, capa=capa, **ek)


# --- 1. Olumlu kontrol -------------------------------------------------------------------------


def test_gecerli_onay_olay_sayilir_olumlu_kontrol():
    sonuc = _calistir(lambda t, capa: _onay(t, capa))
    assert len(sonuc.olaylar) == 1 and sonuc.olaylar[0].zaman == BARLAR[0]
    pozisyon.onay_dogrula(sonuc.olaylar[0].pozisyon)


# --- 2. Kapidan gecmemis / yanlis onaylar ------------------------------------------------------


@pytest.mark.parametrize("nesne", ["olay_degil", 1.0, None, object(), ("pozisyon", 1, 2)])
def test_onayli_pozisyon_olmayan_nesne_olay_sayilmaz(nesne):
    with pytest.raises((TypeError, ValueError)):
        _calistir(lambda t, capa: nesne)


def test_elle_degistirilmis_onay_reddedilir():
    """Imza denetimi: `dataclasses.replace` ile degistirilen onay dusmeli."""
    gecerli = _onay(BARLAR[0])
    with pytest.raises(ValueError):
        _calistir(lambda t, capa: dataclasses.replace(gecerli, p0=2.0))


@pytest.mark.parametrize("rol", ["K1", "K2"])
def test_kontrol_rolundeki_onay_olay_sayilmaz(rol):
    """On-kayit §6 rev.11: kontrol ve olay roller ayridir."""
    k = _onay(BARLAR[0], rol=rol)
    assert k.rol == rol
    with pytest.raises(ValueError, match="rol"):
        _calistir(lambda t, capa: k)


def test_baska_hipotezin_onayi_olay_sayilmaz():
    baska = pozisyon._test_onayi(hipotez="H1", yapilandirma=yapilandirma("H1"), t=BARLAR[0],
                                 capa=BARLAR[0])
    with pytest.raises(ValueError, match="demete ait"):
        _calistir(lambda t, capa: baska)


def test_baska_yapilandirmanin_onayi_olay_sayilmaz():
    """On-kayit §5 rev.11: "Bekleme yapilandirma basina isler; her yapilandirma kendi olay dizisini
    uretir." Iki yapilandirmanin olaylari karisamaz."""
    baska = pozisyon._test_onayi(hipotez="H2", yapilandirma=yapilandirma("H2", k=12), t=BARLAR[0])
    assert baska.yapilandirma != _onay(BARLAR[0]).yapilandirma
    with pytest.raises(ValueError, match="demete ait"):
        _calistir(lambda t, capa: baska, y=Y2)


def test_baska_barin_onayi_olay_sayilmaz():
    """Kapi hangi bari onayladiysa dizi onu olay sayar; baska bir barin onayi kabul edilmez."""
    yanlis = _onay(BARLAR[7])
    with pytest.raises(ValueError, match="sinyal zamani"):
        _calistir(lambda t, capa: yanlis, idxler=range(3))


# --- 3. H1: capa izlemenin ILK pump baridir ---------------------------------------------------


def test_h1_capasi_sorulan_pump_bari_olmali():
    """On-kayit §5 H1 madde 4: "bir teyit bari en cok bir olay sayar"; bu ancak capa denetlenirse
    garanti olur. Dizi 0 capali teyit sordu; kapi 1 capali onay dondururse dusmeli."""
    y1 = yapilandirma("H1")
    kosul = lambda t, capa: (capa is None and t == BARLAR[0]) or (capa is not None and t == BARLAR[3])  # noqa: E731
    with pytest.raises(ValueError, match="capa"):
        _calistir(lambda t, capa: pozisyon._test_onayi(hipotez="H1", yapilandirma=y1, t=t, capa=BARLAR[1]),
                  hipotez="H1", y=y1, kosul=kosul, idxler=range(6))
    # Olumlu kontrol: dogru capayla olay olusur ve capa izlemenin ilk pump baridir.
    sonuc = _calistir(lambda t, capa: pozisyon._test_onayi(hipotez="H1", yapilandirma=y1, t=t, capa=capa),
                      hipotez="H1", y=y1, kosul=kosul, idxler=range(6))
    assert [o.capa for o in sonuc.olaylar] == [BARLAR[0]]


def test_capasiz_hipotezde_capali_onay_reddedilir():
    with pytest.raises(ValueError, match="capa"):
        _calistir(lambda t, capa: _onay(t, capa=BARLAR[0]))


# --- 4. Reddedilen onay beklemeyi baslatmaz (degismedi) ---------------------------------------


def test_ret_gerekcesi_hala_ret_gerekcesidir():
    """Dogrulama yalnizca BASARILI donuse uygulanir: `OlayOlusmaz` alt siniflari hala ret
    gerekcesine cevrilir ve beklemeyi baslatmaz (on-kayit §5 rev.11)."""
    sonuc = _calistir(lambda t, capa: (_ for _ in ()).throw(pozisyon.UygunDegil("sahte")))
    assert sonuc.olaylar == ()
    assert [r.gerekce for r in sonuc.retler] == ["uygun_degil"] * 5


# --- 5. `_test_onayi` yalnizca pytest icinde ve analiz kodunda yasak -------------------------


def test_test_onayi_pytest_disinda_kullanilamaz(monkeypatch):
    """Test dikisi yalnizca pytest icinde acik (`split._pytest_testi`); gercek onay kapidan gelir."""
    from data import split

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    with pytest.raises(RuntimeError, match="pytest"):
        pozisyon._test_onayi(hipotez="H2", yapilandirma=Y2, t=BARLAR[0])
    assert split._pytest_testi() is None
