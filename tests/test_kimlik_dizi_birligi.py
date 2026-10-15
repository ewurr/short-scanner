"""Sizinti bulgusu S-C2: bir dizi cagrisi tek bir (sembol, kume, donem) dizisidir.

`dizi.olay_dizisi` aciklamasi: "Bir (sembol, donem, kume, yapilandirma) dizisinde olaylari sirayla
bulur." On-kayit §5 (rev.11): "Bekleme donem sinirini asmaz: yeni donemde sifirlanir", bu yuzden
her donem icin ayri cagri yapilir. On-kayit §3: kumeler arasi veri odunc alinmaz.

Bulgu: `_olay_dogrula` onayin (hipotez, yapilandirma, rol, t, capa) alanlarini denetliyordu;
sembol, kume ve donem_no'yu denetlemiyordu. `karar` ayni cagri icinde baska sembolun, baska donemin
ya da baska kumenin onayini dondururse dizi kabul ediyordu -- ornegin KESIF cagrisina C1 pozisyonu
girebiliyordu (C1, KESIF ile ayni tarih araligini paylasir; ayiran sey coin grubudur).

Aga cikmaz; getiri hesaplanmaz.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import dizi, pozisyon
from sinyal_yardimcisi import yapilandirma

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
IZGARA = pd.date_range(T("2025-03-01 00:00"), periods=90, freq="4h")
GUNLER = pd.date_range(T("2025-03-01"), periods=90, freq="D")
Y2, Y3 = yapilandirma("H2"), yapilandirma("H3")
UFUK4 = config.BIRINCIL_UFUK[config.BAR_4H]


def _dizi(karar, idxler, *, hipotez="H2"):
    y = Y2 if hipotez == "H2" else Y3
    izgara = IZGARA if hipotez == "H2" else GUNLER
    bar = config.HIPOTEZ_IZGARASI[hipotez]
    return dizi.olay_dizisi(hipotez, y, izgara[list(idxler)], bar,
                            birincil_ufuk=config.BIRINCIL_UFUK[bar],
                            kosul=lambda t, capa: True, karar=karar)


def _onay(t, capa=None, *, hipotez="H2", **ek):
    y = Y2 if hipotez == "H2" else Y3
    return pozisyon._test_onayi(hipotez=hipotez, yapilandirma=y, t=t, capa=capa, **ek)


# --- 1. Karisik ucluler reddedilir -------------------------------------------------------------


@pytest.mark.parametrize("alan,degerler", [("sembol", ("AAAUSDT", "BBBUSDT")),
                                           ("donem_no", (0, 1)),
                                           ("donem_no", (2, 0))])
def test_karisik_sembol_ve_donem_reddedilir(alan, degerler):
    idxler = [0, 20]          # ikisi de beklemenin disinda (18 bar)

    def karar(t, capa):
        deger = degerler[0] if t == IZGARA[idxler[0]] else degerler[1]
        return _onay(t, capa, **{alan: deger})

    with pytest.raises(ValueError, match="ayni \\(sembol, kume, donem"):
        _dizi(karar, idxler)


@pytest.mark.parametrize("degerler", [("KESIF", "C1"), ("C1", "KESIF")])
def test_karisik_kume_reddedilir(degerler):
    """Kume karisimi madde 1e'den sonra daha ONCE, `split.OnayGerekli` ile reddedilir: `_test_onayi`
    C1/C2 icin acik bir onay kosusu ister. Acik bir C1 kosusu varken de karisim kalir: o kosu
    icinde KESIF pozisyonu olusturulamaz (kapi sertlestirme turu 3). Iki yol da "dizi iki kumeyi
    karistiramaz" hukmunu verir."""
    def karar(t, capa):
        deger = degerler[0] if t == IZGARA[0] else degerler[1]
        return _onay(t, capa, kume=deger)

    with pytest.raises((ValueError, PermissionError)):
        _dizi(karar, [0, 20])


def test_hata_mesaji_iki_ucluyu_de_yazar():
    def karar(t, capa):
        return _onay(t, capa, sembol="AAAUSDT" if t == IZGARA[0] else "BBBUSDT")

    with pytest.raises(ValueError) as hata:
        _dizi(karar, [0, 20])
    metin = str(hata.value)
    assert "AAAUSDT" in metin and "BBBUSDT" in metin


def test_h3_de_ayni_denetim_isler():
    def karar(t, capa):
        return _onay(t, capa, hipotez="H3", donem_no=0 if t == GUNLER[0] else 3)

    with pytest.raises(ValueError, match="ayni \\(sembol, kume, donem"):
        _dizi(karar, [0, 40], hipotez="H3")


def test_kume_karismasi_ucuncu_olayda_da_yakalanir():
    """Uc olay: ilk ikisi KESIF, ucuncusu C1. Dizi ucuncude durur (red sinifi icin yukariya bak)."""
    secim = {IZGARA[0]: "KESIF", IZGARA[20]: "KESIF", IZGARA[40]: "C1"}

    def karar(t, capa):
        return _onay(t, capa, kume=secim[t])

    with pytest.raises((ValueError, PermissionError)):
        _dizi(karar, [0, 20, 40])


# --- 2. Tek uclu gecer; onceki denetimler korundu ---------------------------------------------


@pytest.mark.parametrize("uclu", [("AAAUSDT", "KESIF", 0), ("BBBUSDT", "KESIF", 3)])
def test_tek_uclu_gecer(uclu):
    sembol, kume, donem_no = uclu

    def karar(t, capa):
        return _onay(t, capa, sembol=sembol, kume=kume, donem_no=donem_no)

    sonuc = _dizi(karar, [0, 20, 40])
    assert len(sonuc.olaylar) == 3
    for olay in sonuc.olaylar:
        dizi.olay_dogrula(olay)
        assert (olay.pozisyon.sembol, olay.pozisyon.kume, olay.pozisyon.donem_no) == uclu


def test_tek_olayli_dizi_de_gecer():
    sonuc = _dizi(lambda t, capa: _onay(t, capa), [5])
    assert len(sonuc.olaylar) == 1


def test_rev13_denetimleri_korundu():
    """Yapilandirma, rol ve t denetimleri (rev.13 madde 3b) kaldirilmadi."""
    with pytest.raises(ValueError, match="demete ait"):
        _dizi(lambda t, capa: _onay(t, capa, hipotez="H2") if False else pozisyon._test_onayi(
            hipotez="H2", yapilandirma=yapilandirma("H2", k=12), t=t, capa=capa), [0])
    with pytest.raises(ValueError, match="rol"):
        _dizi(lambda t, capa: _onay(t, capa, rol="K1"), [0])
    with pytest.raises(ValueError, match="sinyal zamani"):
        _dizi(lambda t, capa: _onay(IZGARA[1], capa), [0])
