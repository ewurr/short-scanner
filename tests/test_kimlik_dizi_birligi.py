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
import dizi_cagri
from sinyal_yardimcisi import yapilandirma

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
IZGARA = pd.date_range(T("2025-03-01 00:00"), periods=90, freq="4h")
GUNLER = pd.date_range(T("2025-03-01"), periods=90, freq="D")
Y2, Y3 = yapilandirma("H2"), yapilandirma("H3")
UFUK4 = config.BIRINCIL_UFUK[config.BAR_4H]


def _dizi(karar, idxler, *, hipotez="H2", sembol="TESTONAYUSDT", kume="KESIF", donem_no=0):
    """Dizi cagrisi. Kimlik (sembol, kume, donem_no) madde 3a'dan beri CAGRIDAN gelir (bulgu K-B1);
    varsayilanlar `pozisyon._test_onayi`nin varsayilanlariyla ayni, boylece karismayan durumda
    cagri ile onaylar ayni ucluye aittir."""
    y = Y2 if hipotez == "H2" else Y3
    izgara = IZGARA if hipotez == "H2" else GUNLER
    bar = config.HIPOTEZ_IZGARASI[hipotez]
    return dizi_cagri.cagir(hipotez, y, izgara[list(idxler)], bar,
                            birincil_ufuk=config.BIRINCIL_UFUK[bar],
                            kosul=lambda t, capa: True, karar=karar,
                            sembol=sembol, kume=kume, donem_no=donem_no)


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

    # Cagrinin kimligi ILK olayin ucluusu: red IKINCI olayda, yani karisimin kendisinde olusur.
    with pytest.raises(ValueError, match="baska bir diziye ait"):
        _dizi(karar, idxler, **{alan: degerler[0]})


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
        _dizi(karar, [0, 20], kume=degerler[0])


def test_hata_mesaji_iki_ucluyu_de_yazar():
    def karar(t, capa):
        return _onay(t, capa, sembol="AAAUSDT" if t == IZGARA[0] else "BBBUSDT")

    with pytest.raises(ValueError) as hata:
        _dizi(karar, [0, 20], sembol="AAAUSDT")
    metin = str(hata.value)
    assert "AAAUSDT" in metin and "BBBUSDT" in metin


def test_h3_de_ayni_denetim_isler():
    def karar(t, capa):
        return _onay(t, capa, hipotez="H3", donem_no=0 if t == GUNLER[0] else 3)

    with pytest.raises(ValueError, match="baska bir diziye ait"):
        _dizi(karar, [0, 40], hipotez="H3", donem_no=0)


def test_kume_karismasi_ucuncu_olayda_da_yakalanir():
    """Uc olay: ilk ikisi KESIF, ucuncusu C1. Dizi ucuncude durur (red sinifi icin yukariya bak)."""
    secim = {IZGARA[0]: "KESIF", IZGARA[20]: "KESIF", IZGARA[40]: "C1"}

    def karar(t, capa):
        return _onay(t, capa, kume=secim[t])

    with pytest.raises((ValueError, PermissionError)):
        _dizi(karar, [0, 20, 40], kume="KESIF")


# --- 2. Tek uclu gecer; onceki denetimler korundu ---------------------------------------------


@pytest.mark.parametrize("uclu", [("AAAUSDT", "KESIF", 0), ("BBBUSDT", "KESIF", 3)])
def test_tek_uclu_gecer(uclu):
    sembol, kume, donem_no = uclu

    def karar(t, capa):
        return _onay(t, capa, sembol=sembol, kume=kume, donem_no=donem_no)

    sonuc = _dizi(karar, [0, 20, 40], sembol=sembol, kume=kume, donem_no=donem_no)
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


# --- 3. Kimlik CAGRIDAN gelir (madde 3a, bulgu K-B1) ------------------------------------------


@pytest.mark.parametrize("alan,deger", [("sembol", "BASKAUSDT"), ("donem_no", 7)])
def test_tek_olayli_cagri_da_dis_referansla_denetlenir(alan, deger):
    """Bulgunun kendisi: tek olay ureten cagri. Rev.13'te ilk olay ucluyu KURUYORDU, yani hicbir dis
    referansla karsilastirilmiyordu; `karar` yanlis sembolun ya da baska donemin onayini dondurse
    kabul ediliyordu. Artik uclu cagridan gelir."""
    with pytest.raises(ValueError, match="baska bir diziye ait"):
        _dizi(lambda t, capa: _onay(t, capa, **{alan: deger}), [5])


def test_sifir_olayli_cagri_kimligi_gerektirir():
    """Olay uretmeyen cagri da kimlik ister: eksik arguman programlama hatasidir."""
    bar = config.HIPOTEZ_IZGARASI["H2"]
    with pytest.raises(TypeError):
        dizi_cagri.cagir("H2", Y2, IZGARA[[0]], bar, birincil_ufuk=UFUK4,
                         kosul=lambda t, capa: False, karar=lambda t, capa: None)


def test_kume_karisimi_tek_olayda_da_yakalanir():
    """KESIF cagrisina C1 onayi: tek olayli cagrida da reddedilir (kume karisimi, on-kayit §3)."""
    with pytest.raises((ValueError, PermissionError)):
        _dizi(lambda t, capa: _onay(t, capa, kume="C1"), [0], kume="KESIF")


@pytest.mark.parametrize("kimlik", [
    {"sembol": ""}, {"sembol": None}, {"sembol": 3},
    {"kume": "kesif"}, {"kume": "C3"}, {"kume": None},
    {"donem_no": -1}, {"donem_no": 1.0}, {"donem_no": "0"}, {"donem_no": True},
])
def test_gecersiz_kimlik_argumani_reddedilir(kimlik):
    with pytest.raises((TypeError, ValueError)):
        _dizi(lambda t, capa: _onay(t, capa), [0], **kimlik)
