"""Kontrol barinda sinyal KOSULLARI hic hesaplanmaz (on-kayit §6, rev.12 (e)).

On-kayit §6 (rev.12): "Kontrol barinda sinyal kosullari hicbir amacla hesaplanmaz. K2'nin 'o anda
olay uretmemis' sarti, kosullarin saglanip saglanmadigina degil, o barin ayni yapilandirmanin
olusmus olay kumesinde bulunup bulunmadigina gore uygulanir (§6 'Ornekleme kurallari'). Kontrol
barinda hesaplanan tek sey, capasiz pencerelerin hesaplanabilirligidir."

Rev.11'de kapi K2 rolunde H2 ve H3'un kosullarini hesaplar ve saglaniyorsa `OlayUretmis`
firlatirdi; H1 bir istisnaydi (capali sinyal). Rev.12 ucunu ayni yola koydu, `OlayUretmis` ret
gerekcesini ve `_sinyal_gerekli` yardimcisini konusuz birakti. Gerekce (on-kayit §6 rev.12):
"on-kayit 'olay uretmemis' diyor, 'kosulu saglamamis' demiyor; ve bu okuma iki okumadan
muhafazakar olanidir -- kosulu saglayan barlari havuzdan cikarmak kontrol havuzunu sinyale
benzeyen barlardan arindirir ve olculen farki hipotez lehine buyutur."

Hicbir sinyal DEGERI ya da getiri raporlanmaz. Aga cikmaz.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import ornekleme, pencere, pozisyon, sinyal
from kapi_yardimcisi import veri
from kume_yardimcisi import kume_adi
from sinyal_yardimcisi import kontrol, olay, yapilandirma
from uygunluk_yardimcisi import esikler

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
HACIM = 1e7
KONTROL_ROLLERI = ("K1", "K2")


def _duz(bas, son, fiyat=1.0, hacim=HACIM) -> pd.DataFrame:
    z = pd.date_range(bas, son, freq="4h")
    return pd.DataFrame({"open_time": z, "open": fiyat, "high": fiyat, "low": fiyat, "close": fiyat,
                         "quote_volume": float(hacim)})


def _fund(bas, son, oran=0.0005) -> pd.DataFrame:
    z = pd.date_range(bas, son, freq="8h")
    return pd.DataFrame({"odeme_zamani": z, "aralik_saat": 8.0, "oran": 0.0, "oran_8h": float(oran)})


def _ayarla(mumlar, zaman, **alanlar):
    m = mumlar.copy()
    maske = pd.DatetimeIndex(m["open_time"]) == pd.Timestamp(zaman)
    assert bool(maske.any())
    for alan, deger in alanlar.items():
        m.loc[maske, alan] = deger
    return m


def _aralik_ayarla(mumlar, bas, son, **alanlar):
    m = mumlar.copy()
    z = pd.DatetimeIndex(m["open_time"])
    maske = (z >= pd.Timestamp(bas)) & (z <= pd.Timestamp(son))
    assert bool(maske.any())
    for alan, deger in alanlar.items():
        m.loc[maske, alan] = deger
    return m


def _karar(hipotez, mumlar, fund, db, b, t, **ek):
    tanim = pencere.hipotez_ufuklari(hipotez)
    return pozisyon.olay_karari(t, tanim.birincil, tanim.bar, hipotez=hipotez,
                                birincil_ufuk=tanim.birincil, kume=kume_adi(t),
                                **veri(mumlar, fund, db, b, uygun_bas=db, hacim=6 * HACIM),
                                **ek, **esikler(tanim.bar))


# --- Dunyalar: her hipotezin kosullarini SAGLAYAN bar ----------------------------------------

DB, B = T("2024-09-01"), T("2025-06-30 20:00")
FUND = _fund(DB, B + H4)

P1 = T("2025-03-10 04:00")            # H1 pump bari
T1 = P1 + 3 * H4                      # H1 teyit bari
T2 = T("2025-03-10 04:00")            # H2 kirilim bari
T3 = T("2025-03-10")                  # H3 olay gunu


def _h1_olay_serisi() -> pd.DataFrame:
    m = _aralik_ayarla(_duz(DB, B), P1 - 5 * H4, P1, quote_volume=3 * HACIM)
    return _ayarla(m, P1, close=1.25, high=1.30, low=1.0, open=1.0)


def _h2_olay_serisi() -> pd.DataFrame:
    m = _aralik_ayarla(_duz(DB, B), T2 - 3 * H4, T2 - H4, low=1.5, high=1.5, close=1.0, open=1.0)
    return _ayarla(m, T2, close=1.2, high=1.2, low=1.2, open=1.2)


def _h3_olay_serisi() -> pd.DataFrame:
    """H3'un iki kosulunu da saglayan 1d dunyasi: uzak hacim yuksek, yakin hacim cokmus; fiyat
    SMA50'nin altinda ve 30 gunde `-τ`dan fazla dusmus."""
    m = _duz(DB, B, fiyat=1.0, hacim=HACIM)
    # Yakin 30 gunde hacim coker (uzak pencere yuksek kalir). Gunluk hacim 6 x HACIM/6 = 1e7,
    # yani H3'un 2e6 uygunluk esiginin ustunde ama uzak medyanin (6e7) yarisinin altinda: ν = 0.50
    # kosulu saglanir ve uygunluk gerekcesi karismaz.
    m = _aralik_ayarla(m, T3 - pd.Timedelta(days=29), T3 + pd.Timedelta(hours=20), quote_volume=HACIM / 6)
    # Fiyat 30 gunde 1.0 -> 0.5 duser (τ = 0.15 ve SMA50 kosulu saglanir).
    m = _aralik_ayarla(m, T3 - pd.Timedelta(days=4), T3 + pd.Timedelta(hours=20),
                       open=0.5, high=0.5, low=0.5, close=0.5)
    return m


def test_h1_h2_h3_olay_barlari_gercekten_olay_uretiyor_on_kosul():
    """Olumlu kontrol: bu uc dunyada olay rolu GERCEKTEN olay uretiyor, yani asagidaki testler
    "kosulu saglayan bar" uzerinde kosuyor."""
    assert _karar("H1", _h1_olay_serisi(), FUND, DB, B, T1, **olay("H1", capa=P1)).rol == "olay"
    assert _karar("H2", _h2_olay_serisi(), FUND, DB, B, T2, **olay("H2")).rol == "olay"
    assert _karar("H3", _h3_olay_serisi(), FUND, DB, B, T3, **olay("H3")).rol == "olay"


# --- 1. Kosullari saglayan bar kontrol rollerinden gecer -------------------------------------


@pytest.mark.parametrize("rol", KONTROL_ROLLERI)
@pytest.mark.parametrize("hipotez,seri,t", [("H1", _h1_olay_serisi, T1), ("H2", _h2_olay_serisi, T2),
                                            ("H3", _h3_olay_serisi, T3)])
def test_kosullari_saglayan_bar_kontrol_rollerinde_kapidan_gecer(rol, hipotez, seri, t):
    """Uc hipotezde de: kosullar saglaniyor olsa bile kapi kontrolu elemez (rev.12)."""
    assert _karar(hipotez, seri(), FUND, DB, B, t, **kontrol(hipotez, rol)).rol == rol


def test_olay_uretmis_ret_gerekcesi_kalkti():
    """Kapi K2'de kosul hesaplamadigi icin `OlayUretmis` konusuz kalmistir ve kaldirilmistir."""
    assert not hasattr(pozisyon, "OlayUretmis")
    assert "olay_uretmis" not in {sinif.gerekce for sinif in vars(pozisyon).values()
                                  if isinstance(sinif, type) and issubclass(sinif, pencere.OlayOlusmaz)}


def test_sinyal_gerekli_yardimcisi_kalkti():
    """Rol basina sinyal hesaplama karari artik tek yerde (`olay_karari`): H1 istisnasi yok."""
    assert not hasattr(pozisyon, "_sinyal_gerekli")


# --- 2. Kosul gercekten hic hesaplanmiyor (yalnizca pencereler) -------------------------------


@pytest.mark.parametrize("rol", KONTROL_ROLLERI)
def test_kosul_degerlendirmesi_hata_verecek_veride_bile_kontrol_olusur(rol):
    """En keskin olcut: `sinyal.kosullar_saglandi` H2'nin `close[t-30]` bolenini POZITIF olmaya
    zorlar (`sinyal._pozitif` -> `pencere.VeriHatasi`). Sifir fiyatli bir seride kosul
    hesaplanirsa bu hata yukari cikar; rev.12'de kontrol rolunde kosul hic hesaplanmadigi icin
    pencere (sonlu bir sayi olan 0.0) hesaplanabilir sayilir ve kontrol olusur.

    Rev.11'de ayni bar K2 rolunde `VeriHatasi` verirdi -- yani bu test kosulun hesaplanmadigini
    dolayli degil DOGRUDAN gosterir."""
    # `close[t-30]` TAM t-30 barindadir (iki uclu oran); sifir fiyat oradadir.
    sifirli = _ayarla(_duz(DB, B), T2 - 30 * H4, close=0.0, open=0.0, high=0.0, low=0.0)
    degerler = sinyal.sinyal_degerleri("H2", yapilandirma("H2"), T2, mumlar_4h=sifirli,
                                       gunluk=None, funding=FUND, capa=None,
                                       kume_baslangic=T(config.KESIF_BASI.isoformat()),
                                       kume_bitis=T(config.KESIF_SONU.isoformat()),
                                       donem_baslangic=DB)
    with pytest.raises(pencere.VeriHatasi):
        sinyal.kosullar_saglandi("H2", yapilandirma("H2"), degerler)
    assert _karar("H2", sifirli, FUND, DB, B, T2, **kontrol("H2", rol)).rol == rol


# --- 3. Eleme ornekleme adiminda (uc hipotezde ayni) ------------------------------------------


def test_k2_elemesi_olay_kumesine_gore_ornekleme_adiminda():
    """On-kayit §6 "Ornekleme kurallari" (rev.12): "bir bar yalnizca o kumede yer aliyorsa K2
    havuzundan cikarilir". Kosulu saglayan ama olay olusmamis barlar HAVUZDA KALIR."""
    assert ornekleme.k2_adaylari(["AAAUSDT", "BBBUSDT"], ["AAAUSDT"], olay_sembolu="CCCUSDT") == ("BBBUSDT",)
    # Olay uretmemisse kalir; olayin kendi coini de ayiklanir ("diger coinlerden").
    assert ornekleme.k2_adaylari(["AAAUSDT", "CCCUSDT"], [], olay_sembolu="CCCUSDT") == ("AAAUSDT",)


def test_uc_hipotez_ayni_yolu_kullanir():
    """Rev.12 (e): H1'in K2 istisnasi konusuz kaldi; uc hipotezde kontrol rolu ayni adimlardan
    gecer (capasiz pencere + uygunluk + funding), kosul adimindan gecmez."""
    for hipotez, seri, t in (("H1", _h1_olay_serisi, T1), ("H2", _h2_olay_serisi, T2),
                             ("H3", _h3_olay_serisi, T3)):
        for rol in KONTROL_ROLLERI:
            p = _karar(hipotez, seri(), FUND, DB, B, t, **kontrol(hipotez, rol))
            assert (p.hipotez, p.rol) == (hipotez, rol)
