"""Tur I saldirilari: sizinti testcisi gorevi (Rev.10'un koda gecisi ustune ek saldirilar).

Hedefler (gorev tanimindan, onceki turlerde (H) test edilmemis kenarlar):
  1. H2 funding sinyal penceresi (`data/funding.py` `sinyal_penceresi_ayrintisi`,
     `funding_ortalamasi`): kume_bitis NaT/bool reddi, ters (mantiksiz) kume sinirlari,
     1d bar + kisa `saat` penceresi, dogrudan (vektorel) cagriya sizmayan temiz gelecek
     veri, kume_bitis=None'in belgelenen sinirsizligi.
  2. Tolerans zincirinin `pencere_dilimi` disindaki tasiyicilara (`ic_ice_pencere_degeri`,
     `ofsetli_pencere_degeri`, `eligibility.medyan_hacim`) da uygulandigi.
  3. Ritim sinifi (`funding.ritim_sinifi`, `ritim_sinifi_ozeti`) kesin esitlik siniri ve
     `OnaylanmisPozisyon.ritim_sinifi` / `funding_ritmi_saat` imza korumasi.
  4. Kume sinirlari on-kayidinin bilinen sinirlari: KESIF/C2 arasindaki 1 saniyelik
     bosluk (rev.7); kaynak taramasinin ".py metni" siniri (belgelenen atlatma).

Yalnizca `tests/` altina yazilir; aga cikmaz (tests/conftest.py `ag_kapali`). Mevcut
hicbir test dosyasina dokunulmadi (yalnizca okundu).
"""

from __future__ import annotations

import re
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
from conftest import sahte_4h  # noqa: E402
from data import eligibility  # noqa: E402
from data import funding  # noqa: E402
from data import pencere as pencere_modulu  # noqa: E402
from data import pozisyon as pozisyon_modulu  # noqa: E402
from tarama_yardimcisi import FUNDING_ORAN_DESENI  # noqa: E402
from uygunluk_yardimcisi import uygunluk  # noqa: E402

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H = lambda n: pd.Timedelta(hours=n)  # noqa: E731
DB = T("2032-01-01")  # donem basi (uzak, testlerin cogu icin kullanilir)
T0 = T("2032-06-10 20:00")  # t; kapanis 06-11 00:00, pencere basi 06-10 00:00 (24h)
KAPANIS = T0 + H(4)
BAS = KAPANIS - H(24)


def _seri(zamanlar, aralik=8.0, oran=None):
    zamanlar = pd.DatetimeIndex(zamanlar)
    oran = np.arange(1, len(zamanlar) + 1, dtype=float) * 1e-4 if oran is None else np.asarray(oran, dtype=float)
    a = np.full(len(zamanlar), float(aralik)) if np.ndim(aralik) == 0 else np.asarray(aralik, dtype=float)
    return pd.DataFrame({"odeme_zamani": zamanlar, "aralik_saat": a, "oran": oran, "oran_8h": oran})


def _sekiz_saatlik(bas=T("2032-06-01"), son=T("2032-06-20")):
    return _seri(pd.date_range(bas, son, freq="8h"))


def _ort(fund, t=T0, **sinirlar):
    s = dict(kume_baslangic=None, kume_bitis=None, donem_baslangic=DB)
    s.update(sinirlar)
    return funding.funding_ortalamasi(fund, t, config.BAR_4H, saat=24, **s)


# ==============================================================================
# 1. kume_bitis NaT / bool reddi — sinyal penceresi ve ortalamada ayni kapi
#    (on-kayit §5 rev.8 Zaman toleransi doku; §4 "Ufuk / sinir zorunlulugu").
# ==============================================================================


def test_kume_bitis_nat_sinyal_penceresinde_reddedilir():
    """`sinyal_penceresi_ayrintisi`nin kume_bitis argumani NaT'i KABUL ETMEMELI (
    `pencere.sinir_zamani` -> `utc_zamani` tz'siz/NaT degerleri TypeError ile reddeder)."""
    fund = _sekiz_saatlik()
    with pytest.raises(TypeError):
        funding.sinyal_penceresi_ayrintisi(
            fund, [T0], config.BAR_4H, saat=24, kume_baslangic=None, kume_bitis=pd.NaT, donem_baslangic=DB
        )


@pytest.mark.parametrize("deger", [True, False])
def test_kume_bitis_bool_funding_ortalamasinda_reddedilir(deger):
    """`funding_ortalamasi`nin kume_bitis'i bool KABUL ETMEMELI (bir zaman damgasi ya da
    acikca None olmali; `pencere.sinir_zamani`)."""
    fund = _sekiz_saatlik()
    with pytest.raises(TypeError):
        _ort(fund, kume_bitis=deger)


# ==============================================================================
# 2. Ters (mantiksiz) kume sinirlari savunmasi — kume_bitis < kume_baslangic
#    (on-kayit §4 "Funding sinyal penceresinin tamligi": kume karsilastirmalari
#    birbirinden bagimsiz, birbirini varsaymaz).
# ==============================================================================


def test_kume_sinirlari_ters_verilirse_pencere_guvenli_sekilde_disarida_kalir():
    """kume_bitis kume_baslangictan ONCE verilirse (saçma / bozuk sinir), sonuc sessizce
    'kume icinde' SAYILMAMALI: kapanis, kume_bitis'ten cok sonra oldugu icin `sonra(kapanis,
    kume_son)` kosulu tek basina reddi saglamali (leak yok)."""
    fund = _sekiz_saatlik()
    kume_bas = BAS - H(4)  # pencereyi kume disina itmeyen normal bir baslangic
    kume_son = BAS - H(20)  # ama bitis, baslangictan ONCE (mantiksiz sinir)
    assert kume_son < kume_bas
    assert np.isnan(_ort(fund, kume_baslangic=kume_bas, kume_bitis=kume_son))


# ==============================================================================
# 3. kume_bitis=None'in belgelenen sinirsizligi — leak DEGIL, ama kontrast net olmali
#    (on-kayit §4 "Funding sinyal penceresinin tamligi", rev.10: kume yoksa acikca None).
# ==============================================================================


def test_kume_bitis_none_ise_varsayimsal_kume_sonunu_asan_pencere_engellenmez():
    """kume_bitis=None ACIKCA 'sinir yok' der; pencere gercekte var olmayan bir kumenin
    sonunu 'asabilir'. Uretimde `split.kume_erisimi` HER ZAMAN gercek bas/son doner (bkz.
    `data/split.py`); bu test yalnizca dogrudan cagridaki belgelenen davranisi sabitler ve
    None ile GERCEK bir kume_bitis arasindaki farki gosterir (bu bir kume sizintisi degildir:
    cagiran taraf None'i acikca sececekti)."""
    fund = _sekiz_saatlik(bas=T("2032-06-01"), son=T("2032-08-01"))
    t = T("2032-07-25 20:00")
    varsayimsal_kume_son = T("2032-06-15")  # gercekte boyle bir kume olsaydi pencere onu cok asardi
    assert not np.isnan(_ort(fund, t=t, kume_baslangic=None, kume_bitis=None))
    assert np.isnan(_ort(fund, t=t, kume_baslangic=None, kume_bitis=varsayimsal_kume_son))


# ==============================================================================
# 4. 1d bar + kisa `saat` penceresi — `saat` bar tipinden bagimsiz olcum birimidir
#    (on-kayit §4 "Funding sinyal penceresinin tamligi"; genellik denetimi).
# ==============================================================================


def test_1d_barda_kisa_saat_penceresi_dogru_hesaplanir():
    """`saat` parametresi izgara adimindan (`adim(bar)`) BAGIMSIZ bir sure birimidir: 1d
    barda `saat=1` verilirse pencere kapanisin son 1 saatidir, gunun tamami degil. Capa,
    zincir ve kume/donem kontrolleri bu kisa pencerede de dogru calismali."""
    donem_bas = T("2020-01-01")
    t = T("2032-01-10")  # 1d bar acilisi
    kapanis = t + pencere_modulu.adim(config.BAR_1D)  # +1 gun
    bas = kapanis - H(1)
    fund = _seri([bas, kapanis], aralik=1.0)  # capa=bas, sonraki kayit=kapanis, 1 saatlik aralik
    a = funding.sinyal_penceresi_ayrintisi(
        fund, [t], config.BAR_1D, saat=1, kume_baslangic=None, kume_bitis=None, donem_baslangic=donem_bas
    ).iloc[0]
    assert bool(a["hesaplanabilir"])
    # Yari acik pencere: BAS'a (capa) denk gelen kayit ortalama araligina GIRMEZ; yalnizca
    # KAPANIS'a denk gelen kayit girer (tek kayit).
    assert int(a["son"]) - int(a["ilk"]) + 1 == 1

    # Karsi-kanit: ortadaki kaydi (capa) silersek capa yok, hesaplanamaz.
    fund_capasiz = _seri([kapanis], aralik=1.0)
    b = funding.sinyal_penceresi_ayrintisi(
        fund_capasiz, [t], config.BAR_1D, saat=1, kume_baslangic=None, kume_bitis=None, donem_baslangic=donem_bas
    ).iloc[0]
    assert not bool(b["hesaplanabilir"])


# ==============================================================================
# 5. Dogrudan (vektorel) cagriya temiz gelecek veri sizmaz — `funding_ortalamasi`nin
#    on-filtresi olmadan da (on-kayit §4 "t barinin kapanisindan sonraki hicbir kayit
#    okunmaz"), `sinyal_penceresi_ayrintisi`nin KENDISI de kapanistan sonraki temiz
#    (bozuk olmayan) kayitlardan etkilenmemeli.
# ==============================================================================


def test_dogrudan_cagrida_kapanistan_sonraki_temiz_veri_sonucu_degistirmez():
    """`funding_ortalamasi` kapanisa kadar on-filtreler; ama alttaki `sinyal_penceresi_ayrintisi`
    de AYNI sonucu (hesaplanabilir, ilk, son) uretmeli kapanistan sonra temiz (sirali, tekrarsiz)
    ek kayitlar eklenince -- cunku 'ilk'/'son' deger degil ZAMANLA araniyor, indeksle degil."""
    # fund_without KAPANIS'ta biter; "ek" KAPANIS'tan SONRAKI, seride hic olmayan yeni
    # zamanlardir (aksi halde `ek` var olan kayitlarla CAKISIR ve testin kendisi bozuk-veri
    # hatasi verirdi -- burada gercekten "gelecekteki ek/temiz veri" senaryosu kuruluyor).
    fund_without = _sekiz_saatlik(bas=T("2032-06-01"), son=KAPANIS)
    ek = _seri(pd.date_range(KAPANIS + H(8), KAPANIS + H(40), freq="8h"))
    fund_with = pd.concat([fund_without, ek], ignore_index=True)

    a = funding.sinyal_penceresi_ayrintisi(
        fund_without, [T0], config.BAR_4H, saat=24, kume_baslangic=None, kume_bitis=None, donem_baslangic=DB
    ).iloc[0]
    b = funding.sinyal_penceresi_ayrintisi(
        fund_with, [T0], config.BAR_4H, saat=24, kume_baslangic=None, kume_bitis=None, donem_baslangic=DB
    ).iloc[0]
    assert bool(a["hesaplanabilir"]) is True
    assert bool(b["hesaplanabilir"]) is True
    assert int(a["ilk"]) == int(b["ilk"])
    assert int(a["son"]) == int(b["son"])


# ==============================================================================
# 6. Tolerans zincirinin ic ice / ofsetli pencerelere ve medyan hacme de uygulandigi
#    (on-kayit §4 rev.10 "Zaman toleransi"; Rev.10 uygulamasi madde 2, `pencere_dilimi`
#    icindeki `once` kullanimi buradan cagiran her fonksiyona miras kalir).
# ==============================================================================


def test_ic_ice_pencere_degeri_donem_siniri_bir_ns_once_toleransla_kabul_edilir():
    t = T("2033-02-01 00:00")
    donem_bas = t + pd.Timedelta(1, "ns")  # 1 ns once; toleransa gore AYNI AN
    seri = pd.Series([3.0], index=pd.DatetimeIndex([t]))
    deger = pencere_modulu.ic_ice_pencere_degeri(
        seri, t, config.BAR_1D, dis_bar_sayisi=1, dis_t_dahil=True, dis_islev="mean", ic_bar_sayisi=1,
        ic_t_dahil=True, ic_islev="mean", kume_baslangic=None, donem_baslangic=donem_bas,
    )
    assert deger == pytest.approx(3.0)

    # Karsi-kanit: tam 1 dakika once ise toleranssiz ve reddedilir (NaN).
    donem_bas_uzak = t + pd.Timedelta(minutes=1)
    assert np.isnan(pencere_modulu.ic_ice_pencere_degeri(
        seri, t, config.BAR_1D, dis_bar_sayisi=1, dis_t_dahil=True, dis_islev="mean", ic_bar_sayisi=1,
        ic_t_dahil=True, ic_islev="mean", kume_baslangic=None, donem_baslangic=donem_bas_uzak,
    ))


def test_ofsetli_pencere_degeri_kume_siniri_bir_ns_once_toleransla_kabul_edilir():
    t = T("2033-03-01 00:00")
    kume_bas = t + pd.Timedelta(1, "ns")  # 1 ns once; toleransa gore AYNI AN
    seri = pd.Series([7.0], index=pd.DatetimeIndex([t]))
    deger = pencere_modulu.ofsetli_pencere_degeri(
        seri, t, 1, config.BAR_1D, bitis_ofseti=0, islev="mean", kume_baslangic=kume_bas, donem_baslangic=DB,
    )
    assert deger == pytest.approx(7.0)

    kume_bas_uzak = t + pd.Timedelta(minutes=1)
    assert np.isnan(pencere_modulu.ofsetli_pencere_degeri(
        seri, t, 1, config.BAR_1D, bitis_ofseti=0, islev="mean", kume_baslangic=kume_bas_uzak, donem_baslangic=DB,
    ))


def test_medyan_hacim_donem_siniri_bir_ns_once_toleransla_hesaplanir():
    t = T("2032-01-10")
    gun_once = t - pd.Timedelta(days=1)
    donem_bas = gun_once + pd.Timedelta(nanoseconds=1)  # pencere basindan 1 ns SONRA
    gunluk_hacim = pd.Series([5e7], index=pd.DatetimeIndex([gun_once]))
    deger = eligibility.medyan_hacim(gunluk_hacim, t, donem_baslangic=donem_bas, kume_baslangic=None, pencere_gun=1)
    assert not np.isnan(deger)
    assert deger == pytest.approx(5e7)

    donem_bas_uzak = gun_once + pd.Timedelta(minutes=1)  # tam 1 dk sonra: toleranssiz
    assert np.isnan(
        eligibility.medyan_hacim(gunluk_hacim, t, donem_baslangic=donem_bas_uzak, kume_baslangic=None, pencere_gun=1)
    )


# ==============================================================================
# 7. Ritim sinifi — kesin esitlik siniri ve bilinmeyen/None reddi
#    (on-kayit §4 "Pozisyonun funding ritmi", rev.10).
# ==============================================================================


@pytest.mark.parametrize("saat, beklenen", [
    (8.0, "8"), (8, "8"), (4.0, "4"), (2.0, "2"), (1.0, "1"),
    (8.0 + 1e-9, funding.RITIM_SINIFLANMAMIS),  # kesin esitlik: neredeyse-8 "8" SAYILMAZ
    (8.0 - 1e-9, funding.RITIM_SINIFLANMAMIS),
    (0.0, funding.RITIM_SINIFLANMAMIS),
    (16.0, funding.RITIM_SINIFLANMAMIS),
    (np.inf, funding.RITIM_SINIFLANMAMIS),
])
def test_ritim_sinifi_kesin_esitlik_siniri(saat, beklenen):
    assert funding.ritim_sinifi(saat) == beklenen


def test_ritim_sinifi_nan_capasiz_none_doner():
    assert funding.ritim_sinifi(float("nan")) is None


def test_ritim_sinifi_ozeti_none_capasiz_reddedilir():
    """Capasi olmayan (None sinifli) bir pozisyon `ritim_sinifi_ozeti`ye SIZMAMALI: fonksiyon
    None'i bilinmeyen sinif olarak ValueError ile reddeder (docstring: 'None (capasiz) ValueError')."""
    with pytest.raises(ValueError):
        funding.ritim_sinifi_ozeti(["8", None, "4"], [False, False, True])


def test_ritim_sinifi_ozeti_bilinmeyen_sinif_reddedilir():
    with pytest.raises(ValueError):
        funding.ritim_sinifi_ozeti(["8", "16"], [False, False])


# ==============================================================================
# 8. `OnaylanmisPozisyon` — ritim sinifi ve funding ritmi imzaya bagli, replace ile
#    sahtelenemez (on-kayit §4 "Pozisyonun funding ritmi", rev.10; imza denetimi
#    onceki turde capa_aralik_saat / son_aralik_saat icin yazilmisti, burada
#    ritim_sinifi / funding_ritmi_saat / karisik_ritim icin genisletiliyor).
# ==============================================================================


def _basit_plan_i(seri_bas_str: str):
    seri_bas = T(seri_bas_str)
    donem_bas = seri_bas - pd.Timedelta(days=60)
    donem_bitis = seri_bas + 200 * H(4)
    zamanlar = pd.date_range(seri_bas, donem_bitis, freq="4h", tz="UTC")
    sinyal = seri_bas + 10 * H(4)
    plan = pencere_modulu.pozisyon_plani(
        zamanlar, sinyal, 6, config.BAR_4H, birincil_ufuk=18,
        kume_baslangic=None, kume_bitis=None, donem_baslangic=donem_bas, donem_bitis=donem_bitis,
    )
    return plan, zamanlar, donem_bas, donem_bitis


def _tam_funding_icin_i(plan):
    giris = plan.giris
    kayitlar = [(giris, 4, 0.0001)]
    z = giris + H(4)
    while z <= funding.funding_penceresi_sonu(plan):
        kayitlar.append((z, 4, 0.0001))
        z += H(4)
    zamanlar = [k[0] for k in kayitlar]
    araliklar = [k[1] for k in kayitlar]
    oranlar = [k[2] for k in kayitlar]
    return pd.DataFrame({
        "odeme_zamani": pd.DatetimeIndex(zamanlar), "aralik_saat": araliklar, "oran": oranlar, "oran_8h": oranlar,
    })


def _onayli_pozisyon(bas_str: str):
    plan, zamanlar, donem_bas, donem_bitis = _basit_plan_i(bas_str)
    fund = _tam_funding_icin_i(plan)
    onayli = pozisyon_modulu.olay_karari(
        sahte_4h(bas_str, len(zamanlar)), fund, plan.sinyal_zamani, plan.ufuk, config.BAR_4H,
        birincil_ufuk=plan.birincil_ufuk, kume_baslangic=None, kume_bitis=None,
        donem_baslangic=donem_bas, donem_bitis=donem_bitis, sinyal_degerleri={"x": 1.0},
        **uygunluk(config.BAR_4H, donem_bas, donem_bitis),
    )
    return onayli, zamanlar, bas_str


def test_ritim_sinifi_replace_ile_sahtelenemez():
    onayli, zamanlar, bas_str = _onayli_pozisyon("2038-05-01 00:00")
    assert onayli.ritim_sinifi == "4"  # 4 saatlik funding
    sahte = replace(onayli, ritim_sinifi="8")
    with pytest.raises(ValueError):
        pozisyon_modulu.pozisyon_fiyatlari(sahte)
    with pytest.raises(ValueError):
        pozisyon_modulu.mae(sahte_4h(bas_str, len(zamanlar)), sahte)


def test_funding_ritmi_saat_ve_karisik_ritim_replace_ile_sahtelenemez():
    onayli, zamanlar, bas_str = _onayli_pozisyon("2038-06-01 00:00")
    sahte1 = replace(onayli, funding_ritmi_saat=onayli.funding_ritmi_saat + 1.0)
    with pytest.raises(ValueError):
        pozisyon_modulu.pozisyon_fiyatlari(sahte1)

    sahte2 = replace(onayli, karisik_ritim=not onayli.karisik_ritim)
    with pytest.raises(ValueError):
        pozisyon_modulu.mae(sahte_4h(bas_str, len(zamanlar)), sahte2)


# ==============================================================================
# 9. Kume sinirlari on-kayidinin bilinen sinirlari (topic 4): KESIF/C2 arasindaki
#    bosluk (rev.7 "ham kesim") ve kaynak taramasinin ".py metni" siniri.
# ==============================================================================


def test_kesif_sonu_ile_c2_basi_arasinda_tam_1_saniyelik_bosluk_var():
    """`funding_yukle`nin KUME kesimi TOLERANSSIZ (ham `>=`/`<=`) karsilastirmadir (on-kayit
    §2 rev.7 "ham kesim", bilinen ve bilerek birakilmis nokta). Bu, KESIF ile C2 arasinda
    ORTAK bir kayit (leak) OLUSTURMAZ cunku sinirlar arasinda ondalik saniyeden buyuk gercek
    bir bosluk vardir: bu bosluga denk gelen (pratikte gorulmeyen, cunku funding zamanlari
    saat sinirlarina hizalidir) bir kayit ISE HICBIR kumeye girmez -- sizinti degil, veri
    kaybi riski (bkz. `data/funding.py` `funding_yukle` docstring)."""
    bosluk = pd.Timestamp(config.C2_BASI) - pd.Timestamp(config.KESIF_SONU)
    assert bosluk == pd.Timedelta(seconds=1)
    # Boslugun ortasindaki bir an KESIF sonuna da C2 basina da HAM karsilastirmayla girmez.
    orta = pd.Timestamp(config.KESIF_SONU) + bosluk / 2
    assert not (orta <= pd.Timestamp(config.KESIF_SONU))
    assert not (orta >= pd.Timestamp(config.C2_BASI))


def test_kaynak_taramasi_string_bolme_ile_atlatilir_bilinen_sinir():
    """`tests/tarama_yardimcisi.py` docstring'inin belirttigi BILINEN SINIR: tarama yalnizca
    `.py` metnine regex uygular; ad parcalanip `getattr` ile erisim yakalanmaz. Bu bir saldiri
    BULGUSU degildir (dokumante edilmis bir sinirdir); bu test o siniri sabitler."""
    dogrudan = "cerceve.oran_8h.mean()"
    # Desen tam "oran_8h" ya da tirnak icinde YALNIZ "oran" arar; "or" + "an_8h" gibi bir
    # bolunme ne biri ne digeri gibi gorunur ve hicbir alternatifi tetiklemez.
    kacis = "getattr(cerceve, 'or' + 'an_8h').mean()"
    assert re.search(FUNDING_ORAN_DESENI, dogrudan)
    assert not re.search(FUNDING_ORAN_DESENI, kacis)
