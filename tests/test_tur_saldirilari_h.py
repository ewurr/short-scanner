"""Tur H saldirilari: sizinti testcisi gorevi (bu turun degisiklikleri, commit e12f55c..53b2302).

Hedefler (gorev tanimindan):
  1. Donem siniri None olamaz (`data/pencere.py` `donem_siniri`, `pencere_dilimi`,
     `ic_ice_pencere_degeri`, `ofsetli_pencere_degeri`; `data/eligibility.py`;
     `data/funding.py` `funding_ortalamasi`): sahte sinirlar, kenarlar, kume None
     iken donem sinirinin tek basina korumasi.
  2. `data/pozisyon.py` `_mum_zamanlari`: tek satirlik close_time'siz cerceve reddi
     ve bunun etrafindan dolanan cerceveler.
  3. `olay_karari` sinyal_degerleri bool reddi: bool taklidi eden ama `isinstance`
     denetiminden kacan degerler.
  4. `OnaylanmisPozisyon` `funding_ritmi_saat` / `karisik_ritim` (rev.9 F2 ritim
     sinifi): capa yokken, tek kayitta, replace ile sahtelemede tutarlilik.
  5. `analysis/00_veri_denetimi/rev10_hazirlik.py` `h2_pencere_sayimi` ve
     `gevseklik_ayrintisi`: vektorel = tekil tutarliligi.

Yalnizca `tests/` altina yazilir; aga cikmaz (tests/conftest.py `ag_kapali`).
Mevcut hicbir test dosyasina dokunulmadi (yalnizca okundu).
"""

from __future__ import annotations

import enum
import importlib.util
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
from conftest import sahte_4h  # noqa: E402
from data import pencere as pencere_modulu  # noqa: E402
from data import pozisyon as pozisyon_modulu  # noqa: E402
from uygunluk_yardimcisi import uygunluk  # noqa: E402

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)


def _funding(kayitlar: list[tuple[pd.Timestamp, float, float]]) -> pd.DataFrame:
    """kayitlar: [(odeme_zamani, aralik_saat, oran), ...]."""
    z = [k[0] for k in kayitlar]
    a = [k[1] for k in kayitlar]
    o = [k[2] for k in kayitlar]
    return pd.DataFrame({
        "odeme_zamani": pd.DatetimeIndex(z),
        "aralik_saat": a,
        "oran": o,
        "oran_8h": o,
    })


def _basit_plan(seri_bas_str: str):
    seri_bas = T(seri_bas_str)
    donem_bas = seri_bas - pd.Timedelta(days=60)
    donem_bitis = seri_bas + 200 * H4
    zamanlar = pd.date_range(seri_bas, donem_bitis, freq="4h", tz="UTC")
    sinyal = seri_bas + 10 * H4
    # Rev.10: plan kapiya verildigi icin ufuk on-kayit degeri (onceki 3 bar yerine 6 bar).
    plan = pencere_modulu.pozisyon_plani(
        zamanlar, sinyal, 6, config.BAR_4H, birincil_ufuk=18,
        kume_baslangic=None, kume_bitis=None, donem_baslangic=donem_bas, donem_bitis=donem_bitis,
    )
    return plan, zamanlar, donem_bas, donem_bitis


def _tam_funding_icin(plan):
    from data import funding as funding_modulu

    giris = plan.giris
    kayitlar = [(giris, 4, 0.0001)]
    z = giris + H4
    while z <= funding_modulu.funding_penceresi_sonu(plan):
        kayitlar.append((z, 4, 0.0001))
        z += H4
    return _funding(kayitlar)


# ==============================================================================
# 1. Donem siniri None olamaz — sahte sinirlar, kenarlar (on-kayit §2 rev.7,
#    denetci bulgusu D-C6, §4 rev.8 "Zaman toleransi").
# ==============================================================================


@pytest.mark.parametrize("deger", [
    pd.NaT,
    np.datetime64("NaT"),
    True,
    False,
    "2025-01-01",
    pd.Timestamp("2025-01-01"),  # tz-naive
])
def test_donem_siniri_gecersiz_degerleri_reddeder(deger):
    """`donem_siniri` NaT (iki bicimde), bool ve saat dilimsiz degerleri KABUL
    ETMEMELI (on-kayit §5 rev.8 Zaman toleransi doku; F1 kapanis bulgusu 15)."""
    with pytest.raises(TypeError):
        pencere_modulu.donem_siniri(deger, "donem_baslangic")


def test_donem_basi_t_dan_sonra_ise_sinyal_donem_disi_sayilir():
    """Donem baslangici SINYAL ANINDAN sonra ise (bozuk/eksik sinir), sinyal donem
    ici SAYILMAMALI; sessizce kabul edilip olay olusMAMALI (on-kayit §6 rev.8
    'Donem uyeligi')."""
    t = T("2038-01-01 00:00")
    donem_bas = t + pd.Timedelta(days=1)  # donem, sinyalden SONRA basliyor
    donem_bitis = donem_bas + pd.Timedelta(hours=100)
    zamanlar = pd.date_range(t, donem_bitis, freq="4h", tz="UTC")
    with pytest.raises(pencere_modulu.DonemDisiSinyal):
        pencere_modulu.pozisyon_plani(zamanlar, t, 3, config.BAR_4H, birincil_ufuk=18,
                                       kume_baslangic=None, kume_bitis=None,
                                       donem_baslangic=donem_bas, donem_bitis=donem_bitis)


def test_kume_none_iken_donem_siniri_tek_basina_korur():
    """Kume siniri verilmedigi (None) durumda, donem baslangici TEK BASINA
    pencerenin gecmise tasmasini engellemeli (on-kayit §2 rev.7)."""
    donem_bas = T("2039-01-01 00:00")
    gunler = pd.date_range(donem_bas - pd.Timedelta(days=10), periods=40, freq="1D", tz="UTC")
    seri = pd.Series(1.0, index=gunler)
    t = donem_bas + pd.Timedelta(days=5)  # pencere (30 gun, t haric) donem basini asiyor
    deger = pencere_modulu.pencere_degeri(seri, t, 30, config.BAR_1D, t_dahil=False,
                                          kume_baslangic=None, donem_baslangic=donem_bas)
    assert np.isnan(deger)


def test_pencere_dilimi_donem_siniri_tam_1_dakika_once_dogru_reddedilir():
    """Karsi-kanit: donem basindan TAM 1 dakika once baslayan pencere gercekten
    oncedir (toleransa gore de ayni an DEGIL); bu kenarda savunma saglam."""
    t = T("2040-02-01 00:00")
    donem_bas = t + pd.Timedelta(minutes=1)
    seri = pd.Series([1.0], index=pd.DatetimeIndex([t]))
    sonuc = pencere_modulu.pencere_dilimi(
        seri, t, 1, config.BAR_1D, t_dahil=True, kume_baslangic=None, donem_baslangic=donem_bas)
    assert sonuc is None


# SALDIRI BULGUSU (Rev.10 hazirlik turu, xfail idi): pencere_dilimi donem/kume basini ham `<` ile
# karsilastiriyordu. Rev.10 uygulamasi madde 2'de kapandi (pencere.once); xfail isareti kaldirildi,
# test ayni beklentiyle normal test olarak kaliyor.
def test_pencere_dilimi_donem_siniri_bir_ns_once_toleransla_ayni_sayilmali():
    t = T("2040-01-01 00:00")
    donem_bas = t + pd.Timedelta(1, "ns")  # 1 ns once; toleransa gore AYNI AN
    seri = pd.Series([1.0], index=pd.DatetimeIndex([t]))
    sonuc = pencere_modulu.pencere_dilimi(
        seri, t, 1, config.BAR_1D, t_dahil=True, kume_baslangic=None, donem_baslangic=donem_bas)
    assert sonuc is not None


# ==============================================================================
# 2. `_mum_zamanlari`: tek satirlik close_time'siz cerceve reddi ve bunun
#    etrafindan dolanan cerceveler (on-kayit §4 rev.8 "Fiyat okuma tabani").
# ==============================================================================


def test_iki_satirlik_1d_cerceve_sahte_close_time_ile_kabul_edilir_mi():
    """Karsi-kanit: iki satirlik gercek 4h-acilisli cerceve (dogru close_time ile)
    savunmadan gecmeli; bu, asagidaki saldiri testinin karsilastirma noktasidir."""
    zamanlar = pd.DatetimeIndex([T("2025-07-01 00:00"), T("2025-07-01 04:00")])
    df = pd.DataFrame({"open_time": zamanlar,
                       "close_time": [zamanlar[0] + H4 - pd.Timedelta(milliseconds=1),
                                      zamanlar[1] + H4 - pd.Timedelta(milliseconds=1)]})
    sonuc = pozisyon_modulu._mum_zamanlari(df)
    assert len(sonuc) == 2


@pytest.mark.xfail(strict=True, reason=(
    "SALDIRI BULGUSU: on-kayit §4 rev.8 'Fiyat okuma tabani' pozisyonun butun "
    "fiyat okumalarinin HER IZGARADA 4h barlardan olmasini ister; _mum_zamanlari "
    "bunu ic denetimle saglar. Ancak close_time NaT oldugunda 'sure = close_time - "
    "acilis' NaT olur ve pandas'ta NaT karsilastirmasi (sure > adim) HER ZAMAN "
    "False doner (float NaN gibi); bu satir suresiz sayilir, hata vermez. Dort "
    "barlik bir cercevede uc bar gercekte 20h/24h araliklı (1d benzeri) olsa bile, "
    "close_time'lari NaT verilir ve yalnizca BIR bar (gercek 4h close_time'li) "
    "ardisik-fark denetimini (min == 4h) gecirmeye yeter; cerceve BUTUNUYLE kabul "
    "edilir. data/pozisyon.py _mum_zamanlari (satir ~153-160): NaT close_time icin "
    "'sure > adim' denetimi atlanabiliyor."
))
def test_close_time_nat_ile_disguised_1d_cercevesi_4h_denetimini_atlatir():
    opens = pd.DatetimeIndex([T("2025-01-01 00:00"), T("2025-01-01 04:00"),
                              T("2025-01-02 00:00"), T("2025-01-03 00:00")])
    close = [pd.NaT, opens[1] + H4 - pd.Timedelta(milliseconds=1), pd.NaT, pd.NaT]
    df = pd.DataFrame({"open_time": opens, "close_time": close})
    with pytest.raises(ValueError):
        pozisyon_modulu._mum_zamanlari(df)


# ==============================================================================
# 3. sinyal_degerleri bool reddi — bool taklidi eden ama isinstance'tan kacan
#    degerler (on-kayit §2 'Tamlik sarti', denetci bulgusu D-C1).
# ==============================================================================


class _Kosul(enum.IntEnum):
    """Test icin: bir kosul sonucunu tasiyan ama `bool` olmayan bir tur."""

    YANLIS = 0
    DOGRU = 1


@pytest.mark.xfail(strict=True, reason=(
    "SALDIRI BULGUSU: on-kayit §2 'Tamlik sarti' (denetci bulgusu D-C1) bool bir "
    "sinyal degerinin ('olumsuzlanmis bir kosul NaN pencereyi True ile gizleyebilir') "
    "TypeError ile reddedilmesini ister; data/pozisyon.py olay_karari bunu "
    "'isinstance(deger, (bool, np.bool_))' ile denetler. Ancak bir kosul sonucu "
    "'bool' YERINE bir IntEnum (ör. enum.IntEnum) uyesi olarak tasinirsa -- "
    "semantik olarak yine bir kosul sonucudur ve gercek bool ile ayni sekilde "
    "kullanilabilir -- isinstance(x, (bool, np.bool_)) FALSE doner (IntEnum bool "
    "ALT SINIFI degildir), sonraki 'eksik' denetimi de gecer (IntEnum bir int alt "
    "sinifidir, math.isfinite calisir). Boylece bool-koruma tasarim amacini "
    "atlatarak kosul-degeri sessizce numerik pencere degeri gibi kabul edilir."
))
def test_intenum_bool_benzeri_deger_bool_korumasini_atlatir():
    plan, zamanlar, donem_bas, donem_bitis = _basit_plan("2034-01-01 00:00")
    fund = _tam_funding_icin(plan)
    with pytest.raises(TypeError):
        pozisyon_modulu.olay_karari(
            sahte_4h("2034-01-01 00:00", len(zamanlar)), fund, plan.sinyal_zamani, plan.ufuk, config.BAR_4H,
            birincil_ufuk=plan.birincil_ufuk, kume_baslangic=None, kume_bitis=None,
            donem_baslangic=donem_bas, donem_bitis=donem_bitis,
            sinyal_degerleri={"kosul": _Kosul.YANLIS},
            **uygunluk(config.BAR_4H, donem_bas, donem_bitis),
        )


# ==============================================================================
# 4. `OnaylanmisPozisyon` funding_ritmi_saat / karisik_ritim — F2 ritim sinifi
#    (on-kayit §4 rev.9 "Funding tamligi", "F2 sarti").
# ==============================================================================


def test_tek_funding_kaydiyla_pozisyon_tam_ve_tek_ritim_sayilir():
    """Pencerede yalnizca CAPA'nin kendisi varsa (baska hicbir kayit yok, capa'nin
    araligi tum pencereyi kapsiyor), pozisyon yine TAM sayilmali (§4 rev.9 'Son':
    capa + araligi pencere sonunu kapsiyorsa yeterli) ve karisik_ritim YANLIS
    olmali (tek kayit = tanim geregi tek ritim)."""
    plan, zamanlar, donem_bas, donem_bitis = _basit_plan("2036-01-01 00:00")
    fund = _funding([(plan.giris, 2000.0, 0.0001)])  # tek kayit, cok genis aralik
    onayli = pozisyon_modulu.olay_karari(
        sahte_4h("2036-01-01 00:00", len(zamanlar)), fund, plan.sinyal_zamani, plan.ufuk, config.BAR_4H,
        birincil_ufuk=plan.birincil_ufuk, kume_baslangic=None, kume_bitis=None,
        donem_baslangic=donem_bas, donem_bitis=donem_bitis,
        sinyal_degerleri={"x": 1.0},
        **uygunluk(config.BAR_4H, donem_bas, donem_bitis),
    )
    assert onayli.tek_ritim is True
    assert onayli.karisik_ritim is False
    assert onayli.funding_ritmi_saat == pytest.approx(2000.0)
    assert onayli.capa_aralik_saat == onayli.son_aralik_saat == pytest.approx(2000.0)


def test_capa_ve_son_aralik_saat_replace_ile_sahtelenemez():
    """`OnaylanmisPozisyon.capa_aralik_saat` / `son_aralik_saat` `dataclasses.replace`
    ile degistirilirse imza tutarsizlasmali ve pozisyon REDDEDILMELI (on-kayit §4
    rev.9: bu alanlar 'gercek tamlik kodundan ve imzaya bagli')."""
    plan, zamanlar, donem_bas, donem_bitis = _basit_plan("2037-01-01 00:00")
    fund = _tam_funding_icin(plan)
    onayli = pozisyon_modulu.olay_karari(
        sahte_4h("2037-01-01 00:00", len(zamanlar)), fund, plan.sinyal_zamani, plan.ufuk, config.BAR_4H,
        birincil_ufuk=plan.birincil_ufuk, kume_baslangic=None, kume_bitis=None,
        donem_baslangic=donem_bas, donem_bitis=donem_bitis,
        sinyal_degerleri={"x": 1.0},
        **uygunluk(config.BAR_4H, donem_bas, donem_bitis),
    )
    sahte1 = replace(onayli, capa_aralik_saat=onayli.capa_aralik_saat + 1.0)
    with pytest.raises(ValueError):
        pozisyon_modulu.pozisyon_fiyatlari(sahte1)

    sahte2 = replace(onayli, son_aralik_saat=onayli.son_aralik_saat + 1.0)
    with pytest.raises(ValueError):
        pozisyon_modulu.mae(sahte_4h("2037-01-01 00:00", len(zamanlar)), sahte2)


# ==============================================================================
# 5. rev10_hazirlik.py — h2_pencere_sayimi / gevseklik_ayrintisi: vektorel = tekil
#    (RESULTS §14.16 "vektorel=tekil").
# ==============================================================================

_DIZIN = config.ANALIZ_DIZINI / "00_veri_denetimi"
sys.path.insert(0, str(_DIZIN))
_spec = importlib.util.spec_from_file_location("_r10_h_saldirisi", _DIZIN / "rev10_hazirlik.py")
_r10 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_r10)


def _seri_h(bas, son, saat, disla=()):
    z = [x for x in pd.date_range(T(bas), T(son), freq=f"{saat}h") if x not in set(disla)]
    return pd.DataFrame({"odeme_zamani": pd.DatetimeIndex(z), "aralik_saat": float(saat)})


def test_h2_pencere_sayimi_vektorel_tekille_ayni():
    """h2_pencere_sayimi birden fazla t ile CAGRILDIGINDA, her satir kendi TEK-t
    cagrisiyla AYNI sonucu vermeli (vektorel = tekil); bir vektorel hata t'ler
    arasinda sessizce karisirsa bu testte yakalanir."""
    seri = pd.concat([
        _seri_h("2025-01-01", "2025-01-04 00:00", 8, disla=[T("2025-01-02 16:00")]),
        _seri_h("2025-01-04 04:00", "2025-01-06", 4),
    ], ignore_index=True)
    taban = T("2025-01-01")
    t_ler = [T("2025-01-01 04:00"), T("2025-01-02 20:00"), T("2025-01-03 12:00"),
             T("2025-01-04 08:00"), T("2025-01-05 16:00")]
    coklu = _r10.h2_pencere_sayimi(t_ler, seri, taban)
    for i, t in enumerate(t_ler):
        tekil = _r10.h2_pencere_sayimi([t], seri, taban).iloc[0]
        satir = coklu.iloc[i]
        assert satir["kayit_A"] == tekil["kayit_A"]
        assert satir["kayit_B"] == tekil["kayit_B"]
        assert satir["ritim"] == tekil["ritim"]
        assert bool(satir["zincir_tam"]) == bool(tekil["zincir_tam"])
