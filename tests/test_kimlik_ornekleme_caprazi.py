"""Ornekelemenin olayla CAPRAZ dogrulamasi (madde 3b-3e; bulgular K-C4, K-C5, K-C6 ve sizinti 2-3).

Bulgular:
  - K-C4 / sizinti 2: olayin kimligi `ornekle`ye SERBEST METIN olarak giriyordu (`sembol`,
    `olay_zamani`) ve adaylarla hicbir yerde karsilastirilmiyordu. Sonuclari: K1 adaylari baska
    coinden olabiliyor; olayin KENDI bari K1 kontrolu, KENDI coini K2 kontrolu olabiliyor; kaymis
    bir `olay_zamani` sessizce baska bir alt tohum uretiyor ve fark RAPORDA GORUNMUYOR.
  - K-C5: bos aday kumesi kimligini `(None, None, None)`a dusuruyordu; mesru bir "aday yok"
    durumu sonradan `ValueError` veriyor ve bos havuzda `genel_tohum = 0` yaziliyordu.
  - K-C6 / sizinti 3: `olay_sayilari` havuz ciftlerinin HANGI OLAYA ait oldugunu dogrulamiyordu
    (bkz. tests/test_havuz_imzasi.py).
  - Madde 3e: K1 tekrar denetimi TAM ESITLIGE bakiyordu; t ile t+30sn iki ayri aday sayiliyordu,
    oysa §4 "Zaman toleransi" onlari ayni an sayar.
  - Madde 3b (son): `alt_tohum` izgara disi bir yapilandirma kimligini kabul ediyordu.

Aga cikmaz; getiri hesaplanmaz.
"""

from __future__ import annotations

import dataclasses

import pandas as pd
import pytest

import config
from data import ornekleme, pozisyon
from dizi_yardimcisi import olaylar_sembollerde, tek_olay
from ornekleme_yardimcisi import k1_adaylari_kur, k2_adaylari_kur
from sinyal_yardimcisi import yapilandirma

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
BARLAR = [T("2025-03-01") + i * H4 for i in range(40)]
TB = T("2025-03-10 04:00")
Y2 = yapilandirma("H2")
UFUK = config.BIRINCIL_UFUK[config.BAR_4H]


def _elenmis(adaylar, olaylar=()):
    """`ornekle` yalnizca AYIKLANMIS kume kabul eder (bulgu P-B2): gercek ayiklayiciyi cagirir.

    Varsayilan olay kumesi bos: ayiklayici kosar ama hicbir aday dusmez, yani testin sinadigi sey
    (ornekleme kurallari, kimlik denetimi, imza) degismez. Ayiklamanin KENDISI ayri testlerde
    sinanir."""
    if not isinstance(adaylar, ornekleme.Adaylar) or adaylar.elendi:
        return adaylar          # ham girdi ve imza saldirilari DOGRUDAN `ornekle`ye gider
    bar = config.HIPOTEZ_IZGARASI[adaylar.hipotez]
    if adaylar.rol == "K1":
        return ornekleme.k1_adaylari(adaylar, olaylar, config.BIRINCIL_UFUK[bar], bar)
    sembol = olaylar[0].pozisyon.sembol if olaylar else "OLAYSEMBOLUYOK"
    return ornekleme.k2_adaylari(adaylar, olaylar, olay_sembolu=sembol)

def _olay(sembol="AAVEUSDT", t=TB, donem_no=0, **ek):
    return tek_olay(t, hipotez="H2", yapilandirma=Y2, kume="KESIF", sembol=sembol,
                    donem_no=donem_no, **ek)


# --- 1. K1: olayin sembolu ve donemi adaylarla ayni olmali -----------------------------------


def test_k1_adaylari_olayin_coininden_olmali():
    """Bulgunun kendisi (sizinti 2): K1 adaylari BBBUSDT'den, olay AAVEUSDT'den -- kabul ediliyordu."""
    adaylar = k1_adaylari_kur(BARLAR, sembol="BBBUSDT")
    with pytest.raises(ValueError, match="K1 ayni coinden"):
        ornekleme.ornekle(_elenmis(adaylar), olay=_olay(sembol="AAVEUSDT"))


def test_k1_adaylari_olayla_ayni_donemden_olmali():
    adaylar = k1_adaylari_kur(BARLAR, sembol="AAVEUSDT", donem_no=1)
    with pytest.raises(ValueError, match="donem"):
        ornekleme.ornekle(_elenmis(adaylar), olay=_olay(sembol="AAVEUSDT", donem_no=0))


def test_k1_ayni_coin_ve_donem_gecer():
    adaylar = k1_adaylari_kur(BARLAR, sembol="AAVEUSDT", donem_no=2)
    havuz = ornekleme.ornekle(_elenmis(adaylar), olay=_olay(sembol="AAVEUSDT", donem_no=2))
    assert len(havuz) == config.KONTROL_SAYISI


def test_olayin_kendi_bari_k1_kontrolu_olamaz():
    """Sizinti 2: `adaylari_kur` ciktisi dogrudan `ornekle`ye verilince (ayiklama atlanarak) olayin
    kendi bari K1 kontrolu olabiliyordu."""
    adaylar = k1_adaylari_kur(BARLAR, sembol="AAVEUSDT")
    with pytest.raises(ValueError, match="kendi bari"):
        ornekleme.ornekle(_elenmis(adaylar), olay=_olay(t=BARLAR[7]))


def test_olayin_kendi_bari_tolerans_icinde_de_reddedilir():
    adaylar = k1_adaylari_kur(BARLAR, sembol="AAVEUSDT")
    with pytest.raises(ValueError, match="kendi bari"):
        ornekleme.ornekle(_elenmis(adaylar), olay=_olay(t=BARLAR[7] + pd.Timedelta(seconds=30)))


# --- 2. K2: olayin bari ve coini ---------------------------------------------------------------


def test_k2_olayin_bari_adaylarin_bariyla_ayni_olmali():
    adaylar = k2_adaylari_kur([f"S{i:02d}USDT" for i in range(20)], t=TB)
    with pytest.raises(ValueError, match="ayni t barindan"):
        ornekleme.ornekle(_elenmis(adaylar), olay=_olay(sembol="AAAUSDT", t=TB + 4 * H4))


def test_olayin_kendi_coini_k2_kontrolu_olamaz():
    semboller = [f"S{i:02d}USDT" for i in range(20)]
    adaylar = k2_adaylari_kur(semboller, t=TB)
    with pytest.raises(ValueError, match="kendi coini"):
        ornekleme.ornekle(_elenmis(adaylar), olay=_olay(sembol=semboller[3], t=TB))


def test_k2_ayiklanmis_havuz_gecer():
    semboller = [f"S{i:02d}USDT" for i in range(20)]
    kur = k2_adaylari_kur(semboller, t=TB)
    ayiklanmis = ornekleme.k2_adaylari(kur, olaylar_sembollerde(["S03USDT"], t=TB), olay_sembolu="S00USDT")
    havuz = ornekleme.ornekle(_elenmis(ayiklanmis), olay=_olay(sembol="S00USDT", t=TB))
    assert "S00USDT" not in havuz.secilenler and "S03USDT" not in havuz.secilenler


# --- 3. Olay nesnesi ZORUNLU; ham kimlik verilemez -------------------------------------------


def test_serbest_sembol_ve_zaman_verilemez():
    """Eski cagri bicimi (serbest metin) artik kabul edilmez."""
    adaylar = k1_adaylari_kur(BARLAR, sembol="AAVEUSDT")
    with pytest.raises(TypeError):
        ornekleme.ornekle(_elenmis(adaylar), sembol="AAVEUSDT", olay_zamani=TB)
    with pytest.raises(TypeError):
        ornekleme.ornekle(_elenmis(adaylar))


@pytest.mark.parametrize("sahte", [TB, "AAVEUSDT", None, 3, ("olay", TB)])
def test_olay_gercek_olay_nesnesi_olmali(sahte):
    adaylar = k1_adaylari_kur(BARLAR, sembol="AAVEUSDT")
    with pytest.raises((TypeError, ValueError)):
        ornekleme.ornekle(_elenmis(adaylar), olay=sahte)


def test_kontrol_onayi_olay_yerine_gecmez():
    adaylar = k1_adaylari_kur(BARLAR, sembol="AAVEUSDT")
    onay = pozisyon._test_onayi(hipotez="H2", yapilandirma=Y2, t=TB, rol="K1", sembol="AAVEUSDT")
    with pytest.raises((TypeError, ValueError)):
        ornekleme.ornekle(_elenmis(adaylar), olay=onay)


def test_baska_yapilandirmanin_olayi_reddedilir():
    adaylar = k1_adaylari_kur(BARLAR, sembol="AAVEUSDT")
    baska = tek_olay(TB, hipotez="H2", yapilandirma=yapilandirma("H2", k=12), kume="KESIF",
                     sembol="AAVEUSDT")
    with pytest.raises(ValueError, match="demetine ait"):
        ornekleme.ornekle(_elenmis(adaylar), olay=baska)


# --- 4. K-C5: bos aday kumesi kimligini korur ------------------------------------------------


def test_bos_k1_kumesi_kimligini_korur():
    adaylar = ornekleme.adaylari_kur([], rol="K1", hipotez="H2", yapilandirma=Y2, kume="KESIF",
                                     sembol="AAVEUSDT", donem_no=0)
    assert (adaylar.hipotez, adaylar.yapilandirma, adaylar.kume) == (
        "H2", "H2:phi=0.0003,k=3", "KESIF")
    assert (adaylar.sembol, adaylar.donem_no) == ("AAVEUSDT", 0)


def test_bos_k2_kumesi_kimligini_korur():
    adaylar = ornekleme.adaylari_kur([], rol="K2", hipotez="H2", yapilandirma=Y2, kume="KESIF",
                                     bar_zamani=TB)
    assert adaylar.bar_zamani == TB and adaylar.kume == "KESIF"


def test_bos_kumede_kimlik_zorunlu():
    with pytest.raises(ValueError, match="kimlik argumanlari zorunlu"):
        ornekleme.adaylari_kur([], rol="K1")
    with pytest.raises(ValueError, match="kimlik argumanlari zorunlu"):
        ornekleme.adaylari_kur([], rol="K1", hipotez="H2", yapilandirma=Y2, kume="KESIF")
    with pytest.raises(ValueError, match="kimlik argumanlari zorunlu"):
        ornekleme.adaylari_kur([], rol="K2", hipotez="H2", yapilandirma=Y2, kume="KESIF")


def test_bos_kume_olay_kumesiyle_calisir_ve_hata_vermez():
    """Bulgunun zararli yolu: mesru "aday yok" durumu `k1_adaylari`da `ValueError` veriyordu."""
    adaylar = ornekleme.adaylari_kur([], rol="K1", hipotez="H2", yapilandirma=Y2, kume="KESIF",
                                     sembol="AAVEUSDT", donem_no=0)
    ayiklanmis = ornekleme.k1_adaylari(adaylar, [_olay()], UFUK, config.BAR_4H)
    assert len(ayiklanmis) == 0 and ayiklanmis.sembol == "AAVEUSDT"
    havuz = ornekleme.ornekle(_elenmis(ayiklanmis), olay=_olay())
    assert len(havuz) == 0 and havuz.aday_sayisi == 0


def test_bos_havuzun_tohumu_on_kayit_tohumundan_turer():
    """Bos havuzda `genel_tohum = 0` olmamali (madde 3d): §8 madde 1 geregi raporlanir."""
    adaylar = ornekleme.adaylari_kur([], rol="K1", hipotez="H2", yapilandirma=Y2, kume="KESIF",
                                     sembol="AAVEUSDT", donem_no=0)
    havuz = ornekleme.ornekle(_elenmis(adaylar), olay=_olay())
    assert havuz.genel_tohum == config.TOHUM
    assert havuz.tohum == ornekleme.tohum_turet(*havuz.alt_tohum_demeti)
    assert havuz.alt_tohum_demeti[1:3] == ("KESIF", "AAVEUSDT")


def test_kimlik_argumanlari_onaylarla_ayni_olmali():
    onaylar = [pozisyon._test_onayi(hipotez="H2", yapilandirma=Y2, t=t, rol="K1",
                                    sembol="AAVEUSDT", kume="KESIF") for t in BARLAR[:3]]
    with pytest.raises(ValueError, match="kimlik argumanlari"):
        ornekleme.adaylari_kur(onaylar, rol="K1", sembol="BBBUSDT")
    with pytest.raises(ValueError, match="kimlik argumanlari"):
        ornekleme.adaylari_kur(onaylar, rol="K1", donem_no=5)
    with pytest.raises(ValueError, match="kimlik argumanlari"):
        ornekleme.adaylari_kur(onaylar, rol="K1", kume="C2")
    # Uyusan kimlik gecer.
    assert len(ornekleme.adaylari_kur(onaylar, rol="K1", sembol="AAVEUSDT", donem_no=0,
                                      kume="KESIF", hipotez="H2", yapilandirma=Y2)) == 3


def test_k1_de_bar_zamani_k2_de_sembol_verilemez():
    onaylar = [pozisyon._test_onayi(hipotez="H2", yapilandirma=Y2, t=t, rol="K1",
                                    sembol="AAVEUSDT", kume="KESIF") for t in BARLAR[:3]]
    with pytest.raises(ValueError, match="bar_zamani"):
        ornekleme.adaylari_kur(onaylar, rol="K1", bar_zamani=TB)
    k2 = [pozisyon._test_onayi(hipotez="H2", yapilandirma=Y2, t=TB, rol="K2", sembol=s,
                              kume="KESIF") for s in ("AUSDT", "BUSDT")]
    with pytest.raises(ValueError, match="sembol"):
        ornekleme.adaylari_kur(k2, rol="K2", sembol="AUSDT")


# --- 5. Madde 3e: K1 tekrar denetiminde zaman toleransi --------------------------------------


@pytest.mark.parametrize("fark", [pd.Timedelta(seconds=0), pd.Timedelta(seconds=30),
                                  pd.Timedelta(seconds=59)])
def test_k1_tolerans_icindeki_tekrar_reddedilir(fark):
    """§4 "Zaman toleransi": bir dakikadan kisa fark AYNI andir, yani ayni bar iki kez adaydir."""
    onaylar = [pozisyon._test_onayi(hipotez="H2", yapilandirma=Y2, t=t, rol="K1",
                                    sembol="AAVEUSDT", kume="KESIF")
               for t in (BARLAR[0], BARLAR[0] + fark, BARLAR[5])]
    with pytest.raises(ValueError, match="tekrarsiz"):
        ornekleme.adaylari_kur(onaylar, rol="K1")


def test_k1_tolerans_siniri_saf_fonksiyonda():
    """Tolerans sinirinin iki yani (saf `_k1_tekrarsiz`; kapi izgara disi bari onaylamadigi icin
    sinir burada sinanir): 59 saniye AYNI an, 1 dakika AYRI."""
    with pytest.raises(ValueError, match="tekrarsiz"):
        ornekleme._k1_tekrarsiz(pd.DatetimeIndex([BARLAR[0], BARLAR[0] + pd.Timedelta(seconds=59)]))
    ornekleme._k1_tekrarsiz(pd.DatetimeIndex([BARLAR[0], BARLAR[0] + pd.Timedelta(minutes=1)]))
    ornekleme._k1_tekrarsiz(pd.DatetimeIndex(BARLAR))
    ornekleme._k1_tekrarsiz(pd.DatetimeIndex([]))


def test_k1_tekrar_denetimi_sirasiz_girdide_de_isler():
    """Tekrar, sirali olmayan listede de yakalanir (denetim siralayarak bakar)."""
    with pytest.raises(ValueError, match="tekrarsiz"):
        ornekleme._k1_tekrarsiz(pd.DatetimeIndex(
            [BARLAR[5], BARLAR[0], BARLAR[5] + pd.Timedelta(seconds=10)]))


# --- 6. Madde 3b (son): alt tohum izgara disi kimligi kabul etmez ----------------------------


@pytest.mark.parametrize("kimlik", ["H2:phi=9,k=9", "H2:phi=0.0003,k=4", "H2:", "H2:k=3,phi=0.0003",
                                    "H2:phi=0.0003,k=3,x=1"])
def test_alt_tohum_izgara_disi_kimligi_reddeder(kimlik):
    with pytest.raises(ValueError, match="izgarasinda bulunmali"):
        ornekleme.alt_tohum("H2", kimlik, "KESIF", "AAVEUSDT", TB)


def test_alt_tohum_izgaradaki_kimligi_kabul_eder():
    for y in ornekleme.sinyal_modulu.izgara("H2"):
        kimlik = ornekleme.sinyal_modulu.yapilandirma_kimligi("H2", y)
        assert ornekleme.alt_tohum("H2", kimlik, "KESIF", "AAVEUSDT", TB) > 0


# --- 7. P-B2: ornekleme yalnizca AYIKLANMIS kumeden yapilir ----------------------------------


def test_ayiklanmamis_kume_ornekelemeye_giremez():
    """Bulgunun kendisi: `adaylari_kur` ciktisi DOGRUDAN `ornekle`ye verilebiliyordu, yani
    `k1_adaylari`/`k2_adaylari` cagrisi atlanabiliyordu. O durumda K1'de olayin 1..17 bar
    yakinindaki butun kapidan gecmis barlar, K2'de o barda olay ureten coinler havuza giriyordu ve
    veri katmani HICBIR hata vermiyordu."""
    k1 = k1_adaylari_kur(BARLAR, sembol="AAVEUSDT")
    assert k1.elendi is False
    with pytest.raises(ValueError, match="AYIKLANMIS"):
        ornekleme.ornekle(k1, olay=_olay())
    k2 = k2_adaylari_kur([f"S{i:02d}USDT" for i in range(12)], t=TB)
    assert k2.elendi is False
    with pytest.raises(ValueError, match="AYIKLANMIS"):
        ornekleme.ornekle(k2, olay=_olay(sembol="AAAUSDT", t=TB))


def test_ayiklanmis_kume_gecer():
    """Olumlu kontrol: ayiklayicidan gecen kume ornekelemeye girer ve `elendi` bayragini tasir."""
    k1 = ornekleme.k1_adaylari(k1_adaylari_kur(BARLAR, sembol="AAVEUSDT"), [_olay()], UFUK,
                               config.BAR_4H)
    assert k1.elendi is True
    assert len(ornekleme.ornekle(k1, olay=_olay())) == config.KONTROL_SAYISI

    semboller = [f"S{i:02d}USDT" for i in range(12)]
    k2 = ornekleme.k2_adaylari(k2_adaylari_kur(semboller, t=TB), [], olay_sembolu="AAAUSDT")
    assert k2.elendi is True
    assert len(ornekleme.ornekle(k2, olay=_olay(sembol="AAAUSDT", t=TB))) == config.KONTROL_SAYISI


def test_elendi_bayragi_elle_cevrilemez():
    """Bayrak imzaya girer: `dataclasses.replace` ile `True` yapmak imza denetiminde duser."""
    k1 = k1_adaylari_kur(BARLAR, sembol="AAVEUSDT")
    sahte = dataclasses.replace(k1, elendi=True)
    with pytest.raises(ValueError, match="elle kurulmus|degistirilmis"):
        ornekleme.aday_dogrula(sahte)
    with pytest.raises(ValueError, match="elle kurulmus|degistirilmis"):
        ornekleme.ornekle(sahte, olay=_olay())


def test_elle_kurulmus_elenmis_kume_de_gecmez():
    """Havuz kurucularini ATLAYAN bir cagri, `ornekle`ye verebilecegi gecerli bir nesne uretemez:
    elle kurulan `Adaylar(..., elendi=True)` imzasizdir."""
    elle = ornekleme.Adaylar("K1", "H2", "H2:phi=0.0003,k=3", "KESIF", tuple(BARLAR),
                             None, "AAVEUSDT", 0, True)
    with pytest.raises(ValueError, match="elle kurulmus|degistirilmis"):
        ornekleme.ornekle(elle, olay=_olay())
    # Imzayi "dogru" degere getirmek de ise yaramaz: imza GIZLI anahtarla alanlardan hesaplanir.
    with pytest.raises(ValueError, match="elle kurulmus|degistirilmis"):
        ornekleme.ornekle(dataclasses.replace(elle, _imza=hash(("x",))), olay=_olay())


def test_ayiklayici_ciktisi_ikinci_kez_ayiklanabilir():
    """Ayiklama yinelenebilir (iki olay kumesi ayri ayri uygulanabilir) ve bayrak kaybolmaz."""
    k1 = ornekleme.k1_adaylari(k1_adaylari_kur(BARLAR, sembol="AAVEUSDT"), [], UFUK, config.BAR_4H)
    ikinci = ornekleme.k1_adaylari(k1, [_olay(t=BARLAR[20])], UFUK, config.BAR_4H)
    assert ikinci.elendi is True and len(ikinci) < len(k1)


def test_bos_ayiklanmis_kume_de_gecer():
    """"Aday yok" mesru durumdur: ayiklamadan gecmis BOS kume de ornekelemeye girer (K-C5)."""
    bos = ornekleme.adaylari_kur([], rol="K1", hipotez="H2", yapilandirma=Y2, kume="KESIF",
                                 sembol="AAVEUSDT", donem_no=0)
    elenmis = ornekleme.k1_adaylari(bos, [_olay()], UFUK, config.BAR_4H)
    havuz = ornekleme.ornekle(elenmis, olay=_olay())
    assert len(havuz) == 0 and havuz.genel_tohum == config.TOHUM
