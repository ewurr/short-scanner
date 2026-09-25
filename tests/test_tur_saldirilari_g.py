"""Tur G saldirilari: sizinti testcisi gorevi (on-kayit rev.9, CLAUDE.md §3.6).

Hedefler (gorev tanimindan):
  1. Uygunluk kapisinin atlanabildigi yollar (`data/pozisyon.py` `olay_karari`,
     `_gunluk_hacim`, `_mum_zamanlari`; `data/eligibility.py` `uygunluk_karari`,
     `esikleri_dogrula`).
  2. H2 penceresi (`data/funding.py` `funding_ortalamasi`) capasinin kume/donem
     sinirini asabildigi yollar (on-kayit §4 rev.9 "Funding sinyal penceresinin
     tamligi": ilk ciftte taban PENCERE BASI olmali; kod guncellenmedi).
  3. T = K siniri (`data/pencere.py` `cikis_bari` / `pozisyon_plani`): B bari
     eksik, ileri kaymanin B'yi asmasi, 1d izgarasi.
  4. Funding tamlik dort maddesi (`data/funding.py` `funding_tamlik_ayrintisi`):
     capa donem basi siniri, `OnaylanmisPozisyon` bayraklarinin `replace` ile
     sahtelenmesi, 4h girdi denetiminin 1d cerceveyi kacirdigi durumlar.

Yalnizca `tests/` altina yazilir; aga cikmaz (tests/conftest.py `ag_kapali`).
Mevcut hicbir test dosyasina dokunulmadi (yalnizca okundu).
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
from donem_yardimcisi import TOPLAM_DONEM_B, TOPLAM_DONEM_BASI  # noqa: E402
from conftest import sahte_4h  # noqa: E402
from data import eligibility as eligibility_modulu  # noqa: E402
from data import funding as funding_modulu  # noqa: E402
from data import pencere as pencere_modulu  # noqa: E402
from data import pozisyon as pozisyon_modulu  # noqa: E402
from tarama_yardimcisi import CIKIS_KAPI_DISI_DESENI, ihlaller  # noqa: E402
from uygunluk_yardimcisi import UYGUN_ONCELIK, uygunluk  # noqa: E402

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


# ==============================================================================
# 1. Uygunluk kapisinin atlanabildigi yollar
#    on-kayit §2 "Uygunluk", "Uygunluk penceresi ve t gunu"; §4 rev.9 "Olayin
#    kumede olusma olcutu" (uygunluk tek karar noktasinin parcasidir).
# ==============================================================================


def test_t_gununun_kendi_hacmi_uygunluga_sizmiyor():
    """t gununun KENDI hacmi devasa olsa bile, medyan penceresi t'yi HARIC tutar
    (on-kayit §2 'Uygunluk penceresi ve t gunu'); pencere oncesi 30 gun esik
    altindaysa uygun olmamali."""
    donem_bas = T("2031-01-01 00:00")
    gunler = pd.date_range(donem_bas, periods=40, freq="1D", tz="UTC")
    hacim = np.full(40, 1.0)  # esik cok altinda
    t_index = 35  # listeleme yasi 35 gun >= 30, esik saglaniyor
    hacim[t_index] = 1e12  # t gununun kendi hacmini sizdirma denemesi
    seri = eligibility_modulu.gunluk_hacim_serisi(
        pd.DataFrame({"open_time": gunler, "quote_volume": hacim}))
    t = gunler[t_index]
    sonuc = eligibility_modulu.uygunluk_karari(
        seri, t, config.BAR_4H, donem_baslangic=donem_bas, donem_bitis=TOPLAM_DONEM_B, kume_baslangic=None,
        asgari_hacim=config.ASGARI_HACIM_4H, asgari_listeleme_yasi_gun=config.ASGARI_LISTELEME_YASI_GUN)
    assert sonuc is False


def test_t_sonrasi_gunlerin_hacmi_uygunluga_sizmiyor():
    """t'DEN SONRAKI gunlerin hacmi (gelecege bakis denemesi) t anindaki uygunluk
    kararini ETKILEMEMELI (on-kayit §2 rev.6, CLAUDE.md §3.6)."""
    donem_bas = T("2031-02-01 00:00")
    gunler = pd.date_range(donem_bas, periods=45, freq="1D", tz="UTC")
    hacim = np.full(45, 1.0)  # esik altinda
    t_index = 35
    hacim[t_index + 1:] = 1e12  # t sonrasi gunlere devasa hacim (sizdirma denemesi)
    seri = eligibility_modulu.gunluk_hacim_serisi(
        pd.DataFrame({"open_time": gunler, "quote_volume": hacim}))
    t = gunler[t_index]
    sonuc = eligibility_modulu.uygunluk_karari(
        seri, t, config.BAR_4H, donem_baslangic=donem_bas, donem_bitis=TOPLAM_DONEM_B, kume_baslangic=None,
        asgari_hacim=config.ASGARI_HACIM_4H, asgari_listeleme_yasi_gun=config.ASGARI_LISTELEME_YASI_GUN)
    assert sonuc is False


def test_kume_basindan_onceki_gunlerin_hacmi_uygunluga_sizmiyor():
    """Kume basindan ONCEKI devasa hacim, penceresi kume basini asan bir barda
    uygunluk kararina SIZMAMALI (on-kayit §3 rev.5 'Kume siniri ve geriye bakis';
    §4 rev.9: uygunluk tek karar noktasinin parcasi)."""
    donem_bas = T("2031-03-01 00:00")
    kume_bas = donem_bas + pd.Timedelta(days=50)
    gunler = pd.date_range(donem_bas, periods=90, freq="1D", tz="UTC")
    hacim = np.full(90, 1.0)
    hacim[:50] = 1e12  # kume oncesi devasa hacim (sizdirma denemesi)
    seri = eligibility_modulu.gunluk_hacim_serisi(
        pd.DataFrame({"open_time": gunler, "quote_volume": hacim}))
    t = kume_bas + pd.Timedelta(days=5)  # pencere (t-30..t-1) kume basini asiyor
    sonuc = eligibility_modulu.uygunluk_karari(
        seri, t, config.BAR_4H, donem_baslangic=donem_bas, donem_bitis=TOPLAM_DONEM_B, kume_baslangic=kume_bas,
        asgari_hacim=config.ASGARI_HACIM_4H, asgari_listeleme_yasi_gun=config.ASGARI_LISTELEME_YASI_GUN)
    assert sonuc is False


def test_esikleri_dogrula_numpy_tamsayi_esigini_reddeder():
    """`esikleri_dogrula` numpy tamsayi (np.int64) esik degerini KABUL ETMEMELI;
    aksi halde on-kayit disindan farkli bir tur/deger sessizce gecebilir."""
    with pytest.raises(TypeError):
        eligibility_modulu.esikleri_dogrula(
            config.BAR_4H, asgari_hacim=config.ASGARI_HACIM_4H,
            asgari_listeleme_yasi_gun=np.int64(config.ASGARI_LISTELEME_YASI_GUN))


def test_esikleri_dogrula_string_hacim_esigini_reddeder():
    """`esikleri_dogrula` string bir hacim esigini (ör. "10000000") KABUL
    ETMEMELI."""
    with pytest.raises(TypeError):
        eligibility_modulu.esikleri_dogrula(
            config.BAR_4H, asgari_hacim="10000000",
            asgari_listeleme_yasi_gun=config.ASGARI_LISTELEME_YASI_GUN)


def test_tekrarlanan_gun_gunluk_mumlarda_sessizce_gecmez():
    """Iki farkli satirda AYNI gun (tekrar) `pozisyon._gunluk_hacim`'e verilirse
    bu bir VERI BOZUKLUGUDUR ve sessizce medyan hesaplanmamali; `ZamanDizisiHatasi`
    ile reddedilmeli (on-kayit §2 rev.3 tamlik sarti "veri bozuklugu, eksik veri
    degil")."""
    gunler = list(pd.date_range(T("2031-04-01 00:00"), periods=10, freq="1D", tz="UTC"))
    gunler[5] = gunler[4]  # tekrar
    df = pd.DataFrame({
        "open_time": gunler, "quote_volume": [1e8] * 10,
        "close_time": [g + pd.Timedelta(days=1) - pd.Timedelta(milliseconds=1) for g in gunler],
    })
    with pytest.raises(pencere_modulu.ZamanDizisiHatasi):
        pozisyon_modulu._gunluk_hacim(df)


def test_sirasiz_gunler_gunluk_mumlarda_sessizce_gecmez():
    """Sirasiz (kronolojik olmayan) gunler `pozisyon._gunluk_hacim`'e verilirse
    sessizce siralanip kabul EDILMEMELI; bu da bir veri bozuklugudur."""
    gunler = list(pd.date_range(T("2031-05-01 00:00"), periods=10, freq="1D", tz="UTC"))
    gunler[3], gunler[4] = gunler[4], gunler[3]  # sira bozuldu
    df = pd.DataFrame({
        "open_time": gunler, "quote_volume": [1e8] * 10,
        "close_time": [g + pd.Timedelta(days=1) - pd.Timedelta(milliseconds=1) for g in gunler],
    })
    with pytest.raises(pencere_modulu.ZamanDizisiHatasi):
        pozisyon_modulu._gunluk_hacim(df)


def test_4h_cerceve_gunluk_mumlar_olarak_verilirse_reddedilir():
    """Yanlislikla verilmis bir 4h cercevesi (`klines.mumlari_yukle(s, "4h", ...)`)
    `gunluk_mumlar` olarak kabul EDILMEMELI (on-kayit §2 '1 gunluk barlar': tek 1d
    kaynak `klines.gunluge_cevir`); `_gunluk_hacim` acikca hata vermeli."""
    zaman = pd.date_range(T("2031-06-01 00:00"), periods=50, freq="4h", tz="UTC")
    df = pd.DataFrame({
        "open_time": zaman, "quote_volume": 1e8,
        "close_time": zaman + H4 - pd.Timedelta(milliseconds=1),
    })
    with pytest.raises(ValueError):
        pozisyon_modulu._gunluk_hacim(df)


# ==============================================================================
# 2. H2 funding penceresinin capa/taban sinirlari
#    on-kayit §4 rev.9 "Funding sinyal penceresinin tamligi"
# ==============================================================================


# SALDIRI BULGUSU (Rev.9 turu, xfail idi): funding_ortalamasi ilk ciftte tabani capadan aliyordu.
# Rev.10 uygulamasi madde 1'de kapandi (funding.sinyal_penceresi_ayrintisi: taban pencere basi);
# xfail isareti kaldirildi, test ayni beklentiyle normal test olarak kaliyor. Cagriya Rev.10'un
# zorunlu kildigi `kume_bitis` eklendi.
def test_funding_ortalamasi_ilk_cift_tabani_capa_degil_pencere_basi_olmali():
    bas = T("2032-01-01 00:00")
    kapanis = bas + pd.Timedelta(hours=24)
    t = kapanis - H4  # bar=4h -> kapanis = t + 4h

    capa = bas - pd.Timedelta(hours=20)  # pencere basindan 20 saat ONCE (8h ritimde)
    r1 = bas + pd.Timedelta(hours=4)
    r2 = bas + pd.Timedelta(hours=12)
    r3 = bas + pd.Timedelta(hours=20)  # r3 + 8h = kapanis + 4h >= kapanis -> "son" tamam
    fund = _funding([(capa, 8, 0.0001), (r1, 8, 0.0001), (r2, 8, 0.0001), (r3, 8, 0.0001)])

    sonuc = funding_modulu.funding_ortalamasi(
        fund, t, config.BAR_4H, saat=24, kume_baslangic=None, kume_bitis=None,
        donem_baslangic=capa - pd.Timedelta(days=5))
    assert not pd.isna(sonuc)  # rev.9 beklentisi: pencere tam, ortalama hesaplanmali


# ==============================================================================
# 3. T = K siniri — on-kayit §4 rev.9 "Donem sonu ve cikis"
# ==============================================================================


def test_b_bari_seriden_silinmisse_donem_sonu_cikisi_sessizce_gecmez():
    """T = K (esitlik) durumunda B bari SERIDE YOKSA, cikis sessizce baska bir
    bardan (ör. yakinindaki bir bar) OKUNMAMALI; acikca hata vermeli (on-kayit §4
    rev.9: donem sonu cikisi B'nin kapanisidir, B eksikse veri bozuktur)."""
    g = T("2032-02-01 00:00")
    b = g + pd.Timedelta(hours=4)  # K = b + 4h = g + 8h = T (ufuk=2, bar=4h)
    zamanlar = pd.DatetimeIndex([g])  # B bari (g+4h) YOK
    with pytest.raises(ValueError):
        pencere_modulu.cikis_bari(zamanlar, g, 2, config.BAR_4H, birincil_ufuk=18,
                                   donem_bitis=b, kume_bitis=None)


def test_ileri_kaymada_yalnizca_b_sonrasi_bar_varsa_donem_disina_tasmaz():
    """Hedef bar eksik ve seride hedef ile B arasinda HICBIR bar yoksa, ileri
    kayma B'nin OTESINDEKI bir bari kullanarak donem disina TASMAMALI; acikca
    hata vermeli (on-kayit §4 rev.8 'Ileri kaymanin olcusu': sonraki mevcut bar
    B'den sonra olamaz)."""
    g = T("2032-03-01 00:00")  # giris bari
    b = g + pd.Timedelta(hours=40)  # donem T'den (g+8h, ufuk=2) cok sonra biter
    # Hedef bar (g+4h; T=g+8h'nin acilis bari) YOK; seride g'den sonraki tek bar
    # B'nin DE otesinde. (ufuk=1 kullanilamaz: o zaman hedef bar giris barinin
    # kendisi olurdu ve her zaman mevcut olurdu.)
    zamanlar = pd.DatetimeIndex([g, b + H4])
    with pytest.raises(ValueError):
        pencere_modulu.cikis_bari(zamanlar, g, 2, config.BAR_4H, birincil_ufuk=18,
                                   donem_bitis=b, kume_bitis=None)


def test_1d_izgarasinda_t_esit_k_donem_sonu_sayilir():
    """T = K esitligi yalnizca 4h sinyal izgarasinda degil, 1d sinyal izgarasinda
    da (adim 24 saat) donem sonu saymali (on-kayit §4 rev.9 'Donem sonu ve cikis'
    esitlik kurali; fiyat okumasi izgaradan bagimsiz 4h barlardandir)."""
    g = T("2032-04-01 00:00")
    b = g + pd.Timedelta(hours=20)  # K = b+4h = g+24h = T (ufuk=1, bar=1d -> adim 24h)
    zamanlar = pd.date_range(g, b, freq="4h", tz="UTC")  # g, g+4h, ..., b (=g+20h)
    sonuc = pencere_modulu.cikis_bari(zamanlar, g, 1, config.BAR_1D, birincil_ufuk=14,
                                       donem_bitis=b, kume_bitis=None)
    assert sonuc.tur == "donem_sonu"
    assert sonuc.cikis_ani == pencere_modulu.donem_kapanisi(b) == g + pd.Timedelta(hours=24)


# ==============================================================================
# 4. Funding tamlik dort maddesi — on-kayit §4 rev.9 "Funding tamligi"
# ==============================================================================


def test_capa_tam_donem_basinda_sayilir_bir_dakika_once_sayilmaz():
    """Capa TAM donem basinda ise sayilmali (§4 'Capa': 'donem basiyla ayni an ya
    da sonra'); donem basindan 1 dakika ONCE (ayni an degil) ise sayilMAMALI."""
    donem_bas = T("2032-05-01 00:00")
    giris = donem_bas + pd.Timedelta(hours=10)
    pencere_sonu = giris + H4

    fund_sinirda = _funding([(donem_bas, 4, 0.0)])
    ayrinti = funding_modulu.funding_tamlik_ayrintisi(
        fund_sinirda, [giris], [pencere_sonu], donem_baslari=[donem_bas])
    assert bool(ayrinti["capa_var"].iloc[0]) is True

    fund_disinda = _funding([(donem_bas - pd.Timedelta(minutes=1), 4, 0.0)])
    ayrinti2 = funding_modulu.funding_tamlik_ayrintisi(
        fund_disinda, [giris], [pencere_sonu], donem_baslari=[donem_bas])
    assert bool(ayrinti2["capa_var"].iloc[0]) is False


def _basit_plan():
    seri_bas = T("2033-01-01 00:00")
    donem_bas = seri_bas - UYGUN_ONCELIK
    donem_bitis = seri_bas + 200 * H4
    zamanlar = pd.date_range(seri_bas, donem_bitis, freq="4h", tz="UTC")
    sinyal = seri_bas + 10 * H4
    plan = pencere_modulu.pozisyon_plani(
        zamanlar, sinyal, 3, config.BAR_4H, birincil_ufuk=18,
        kume_baslangic=None, kume_bitis=None, donem_baslangic=donem_bas, donem_bitis=donem_bitis,
    )
    return plan, zamanlar, donem_bas, donem_bitis


def _tam_funding_icin(plan):
    giris = plan.giris
    kayitlar = [(giris, 4, 0.0001)]  # capa
    z = giris + H4
    while z <= funding_modulu.funding_penceresi_sonu(plan):
        kayitlar.append((z, 4, 0.0001))
        z += H4
    return _funding(kayitlar)


def test_onaylanmis_pozisyon_f2_bayraklari_replace_ile_sahtelenemez():
    """`OnaylanmisPozisyon`in F2 saglamlik bayraklarindan (`kuyruk_kismi`,
    `son_esitlik_affi`) biri `dataclasses.replace` ile degistirilirse imza
    tutarsizlasmali ve pozisyon REDDEDILMELI (on-kayit §4 rev.9: bu bayraklar
    'gercek tamlik kodundan ve imzaya bagli')."""
    plan, zamanlar, donem_bas, donem_bitis = _basit_plan()
    fund = _tam_funding_icin(plan)
    onayli = pozisyon_modulu.olay_karari(
        sahte_4h("2033-01-01 00:00", len(zamanlar)), fund, plan.sinyal_zamani, plan.ufuk, config.BAR_4H,
        birincil_ufuk=plan.birincil_ufuk, kume_baslangic=None, kume_bitis=None,
        donem_baslangic=donem_bas, donem_bitis=donem_bitis,
        sinyal_degerleri={"x": 1.0},
        **uygunluk(config.BAR_4H, donem_bas, donem_bitis),
    )
    sahte1 = replace(onayli, kuyruk_kismi=not onayli.kuyruk_kismi)
    with pytest.raises(ValueError):
        pozisyon_modulu.pozisyon_fiyatlari(sahte1)

    sahte2 = replace(onayli, son_esitlik_affi=not onayli.son_esitlik_affi)
    with pytest.raises(ValueError):
        pozisyon_modulu.mae(sahte_4h("2033-01-01 00:00", len(zamanlar)), sahte2)


# SALDIRI BULGUSU (Rev.9 turu, xfail idi): close_time'siz tek satirlik cerceve 4h denetiminden
# geciyordu. Rev.10 hazirliginda kapandi (pozisyon._mum_zamanlari); xfail isareti kaldirildi,
# test ayni beklentiyle normal test olarak kaliyor.
def test_tek_barlik_1d_cerceve_4h_izgara_denetimini_atlatir():
    tek_gun = pd.DataFrame({"open_time": [T("2032-06-01 00:00")]})
    with pytest.raises(ValueError):
        pozisyon_modulu._mum_zamanlari(tek_gun)


@pytest.mark.xfail(strict=True, reason=(
    "SALDIRI BULGUSU (dokumantasyonda bilinen sinir, CLAUDE.md §5 'Sinir': "
    "tarama yalnizca .py dosyalarinin metnine bakar): CIKIS_KAPI_DISI_DESENI "
    "literal fonksiyon/modul adlarini arar; ad importlib.import_module ve "
    "getattr ile parcalar halinde (string birlestirme) kurulursa desen bunu "
    "YAKALAMAZ. tests/tarama_yardimcisi.py:78-79 bu sinirin var oldugunu zaten "
    "yaziyor; bu test onu somut bir ornekle dogrular."
))
def test_tarama_deseni_parcalanmis_ad_ile_atlatilabilir(tmp_path):
    ornek = tmp_path / "sahte_analiz_kodu.py"
    ornek.write_text(
        "import importlib\n"
        "_ad = 'data.' + 'elig' + 'ibility'\n"
        "_mod = importlib.import_module(_ad)\n"
        "_fn = getattr(_mod, 'uygun' + '_mu')\n"
        "_fn(None, None, '4h', donem_baslangic=None, donem_bitis=None, kume_baslangic=None)\n",
        encoding="utf-8",
    )
    bulunan = ihlaller(CIKIS_KAPI_DISI_DESENI, kok=tmp_path, izinli_altlar=())
    assert bulunan  # beklenti: tarama bunu yakalamali (ama parcalanmis ad yuzunden yakalamiyor)
