"""F1 kapanis turu saldiri testleri (L turu, "kapi sertlestirme" sonrasi).

Hedef, gorev tanimindaki uc degisiklik:
  1. `funding.pozisyon_fundingi`: yalnizca onayli pozisyon; toplam `_plan_fundingi` ile
     yeniden hesaplanip `funding_toplami` ile ESITLIGE bakiliyor (`not toplam == ...`).
  2. `pozisyon.olay_karari`: kume siniri yerine kume ADI (`kume_sinirlari` -> `split.kume_araligi`).
  3. `pozisyon.olay_karari`: donem siniri yerine `sembol`, `donem_no` (`donem_kaydi` -> evren
     tablosu) ve `grup_dogrula` (sembolun bolme grubu kumeye ait mi).

Yaklasim kodu KIRMAYA calisir. Gecen (xfail olmayan) testler savusturulan saldirilardir;
`xfail(strict=True)` ile isaretli testler basarili saldirilardir (bulunan acik). Aga cikmaz.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

import config
from data import funding, pencere, pozisyon, split, universe
from kapi_yardimcisi import donem, veri
from sinyal_yardimcisi import sinyal
from uygunluk_yardimcisi import esikler, uygunluk

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H = lambda n: pd.Timedelta(hours=n)  # noqa: E731

DB, B = T("2025-01-01"), T("2025-06-30 20:00")
Z = pd.date_range(T("2025-03-01"), B, freq="4h")
MUM = pd.DataFrame({"open_time": Z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
TAM_FUND = pd.DataFrame({"odeme_zamani": pd.date_range(DB, B + H(4), freq="8h"), "aralik_saat": 8.0,
                         "oran": 0.0, "oran_8h": 0.0})
T_SINYAL_H1 = T("2025-03-10 04:00")


def _karar_h1(fr=TAM_FUND, mumlar=MUM, donem_bas=DB, donem_son=B, **sinir):
    tanim = pencere.hipotez_ufuklari("H1")
    s = {"kume": "KESIF"}
    s.update(sinir)
    return pozisyon.olay_karari(T_SINYAL_H1, tanim.birincil, tanim.bar, hipotez="H1",
                                birincil_ufuk=tanim.birincil, **veri(mumlar, fr, donem_bas, donem_son, uygun_bas=donem_bas),
                                sinyal_degerleri=sinyal("H1"), **s, **esikler(tanim.bar))


# --- Saldiri 1: oran = inf iceren bir funding kaydi sonsuz funding_toplami uretebilir -------------------


# SALDIRI BULGUSU (kapi sertlestirme turu, xfail idi): olay_karari funding toplamini yalnizca math.isnan
# ile denetliyordu; +-inf oranli bir kayit sonsuz toplamla onaylanabilirdi. Kapi sertlestirme turu 2'de
# kapandi (`pozisyon._sonlu`: sonlu olmayan toplam acik ValueError). Ana oturum duzeltmesi: xfail'in
# asil govdesi inf'i tam giris anindaki kayda (pencere_ici[0], 08:00) koyuyordu; on-kayit §4 giris
# anindaki odemeyi pozisyon disinda tutar, bu yuzden toplam sonluydu ve test yanlis nedenle xfail
# oluyordu. Kayit giris anindan KESIN SONRAKI kayda (pencere_ici[1]) alindi; beklenti ValueError.
def test_sonsuz_orani_olan_funding_kaydi_pozisyonu_sonsuz_toplamla_onaylatamaz():
    """`olay_karari`, `_plan_fundingi`nin dondurdugu toplami yalnizca `math.isnan` ile denetler
    (data/pozisyon.py, `if math.isnan(toplam): raise FundingTamDegil`). `math.isnan(float('inf'))`
    False'tur; `funding_tamlik_ayrintisi` de yalnizca odeme ZAMANI ve ARALIGINI okur, `oran`
    degerine bakmaz (docstring: 'Yalnizca odeme ZAMANI ve ARALIGI okunur; oran okunmaz'). Boylece
    bozuk/asiri bir `oran = inf` kaydi tamligi bozmadan `funding_toplami = inf` olan bir
    `OnaylanmisPozisyon` uretebilir; net getiri hesabi sonsuz/NaN'a doner (on-kayit §4: 'NaN
    yalnizca VERI EKSIKLIGIDIR' kurali sonsuz degeri kapsamiyor). Beklenen: reddedilmeli
    (`FundingTamDegil` ya da benzeri); GOZLENEN: `OnaylanmisPozisyon` sessizce olusuyor."""
    fr = TAM_FUND.copy()
    pencere_ici = fr.index[(fr["odeme_zamani"] > T_SINYAL_H1)
                           & (fr["odeme_zamani"] <= T_SINYAL_H1 + pd.Timedelta(days=3))]
    assert len(pencere_ici) > 0, "test kurulumu: pozisyon penceresinde funding kaydi bekleniyordu"
    assert fr.loc[pencere_ici[1], "odeme_zamani"] > T_SINYAL_H1 + pd.Timedelta(hours=4)  # giristen sonra
    fr.loc[pencere_ici[1], "oran"] = float("inf")

    with pytest.raises(ValueError, match="sonlu degil"):
        _karar_h1(fr=fr)


# --- Saldiri 2: gercek A/B grubu semboller yanlis kumede reddedilmeli (savusturuldu) ---------------------


def _gercek_sembol_donem(istenen_grup: str) -> tuple[str, int]:
    bolme = split.split_oku()
    semboller = set(bolme.loc[bolme["grup"] == istenen_grup, "sembol"])
    evren = universe.evren_yukle()
    aday = evren.loc[evren["sembol"].isin(semboller) & ~evren["haric"] & (evren["donem_id"] >= 0)]
    if aday.empty:
        pytest.skip(f"{istenen_grup} grubunda gercek donemli sembol bulunamadi.")
    r = aday.iloc[0]
    return str(r["sembol"]), int(r["donem_id"])


def test_gercek_a_grubu_sembol_c1_kumesinde_reddedilir(tmp_path, monkeypatch):
    """C1 yalnizca B grubudur (on-kayit §3 'Coin bolmesi'). Gercek bir A grubu sembolun gercek
    listeleme donemiyle C1'e sokulmaya calisilmasi `grup_dogrula` tarafindan reddedilmeli; kod bu
    noktaya kadar `sinyal_degerleri`, `mumlar_4h` gibi diger girdileri hic okumaz (savusturuldu)."""
    sembol, donem_no = _gercek_sembol_donem("A")
    tanim = pencere.hipotez_ufuklari("H1")
    # Kapi sertlestirme turu 3: C1 cagrisi once onay baglamindan gecer; grup denetimi acik kosu icinde sinanir.
    kayit = tmp_path / "onay_gecici.md"
    kayit.write_text("bas\n", encoding="utf-8")
    monkeypatch.setattr(config, "ONAY_KAYDI", kayit)
    with split.onay_kosusu("H1", "C1"), pytest.raises(ValueError, match="kumesine ait degil"):
        pozisyon.olay_karari(  # kapi sertlestirme turu 2: cerceve parametreleri kalkti
            T("2025-01-01"), tanim.birincil, tanim.bar, hipotez="H1",
            birincil_ufuk=tanim.birincil, kume="C1", sembol=sembol, donem_no=donem_no,
            sinyal_degerleri=sinyal("H1"), asgari_hacim=1.0, asgari_listeleme_yasi_gun=1)


def test_gercek_b_grubu_sembol_kesifte_reddedilir_uctan_uca():
    """KESIF yalnizca A grubudur. Gercek bir B grubu sembolun gercek donemiyle KESIF'e sokulmaya
    calisilmasi tam `olay_karari` cagrisi uzerinden (`test_ks_donem_kaydi.py`deki sentetik donem
    testinin gercek veriyle tekrari) reddedilmeli (savusturuldu)."""
    sembol, donem_no = _gercek_sembol_donem("B")
    tanim = pencere.hipotez_ufuklari("H1")
    with pytest.raises(ValueError, match="kumesine ait degil"):
        pozisyon.olay_karari(  # kapi sertlestirme turu 2: cerceve parametreleri kalkti
            T("2025-01-01"), tanim.birincil, tanim.bar, hipotez="H1",
            birincil_ufuk=tanim.birincil, kume="KESIF", sembol=sembol, donem_no=donem_no,
            sinyal_degerleri=sinyal("H1"), asgari_hacim=1.0, asgari_listeleme_yasi_gun=1)


# --- Saldiri 3: yeniden adlandirma zincirinin iki ucu farkli gruba dusurulemez (veri butunlugu) ----------


def test_yeniden_adlandirma_zincirinin_iki_ucu_ayni_grupta():
    """Bolme anahtari varlik anahtaridir (zincirin en eski uyesi); `POLUSDT`/`MATICUSDT` gibi
    ciftler her zaman ayni gruba dusmeli, aksi halde bolme sizintisi olusur (on-kayit §3;
    `split.split_dogrula` zaten bunu commit anında dogrular, burada tekrar dogrulanir).
    Savusturuldu: split.csv bu kurala uyuyor."""
    bolme = split.split_oku().set_index("sembol")["grup"]
    kontrol_edildi = 0
    for yeni, eski in config.YENIDEN_ADLANDIRMA.items():
        if yeni not in bolme.index or eski not in bolme.index:
            continue
        assert bolme[yeni] == bolme[eski], f"{yeni} ve {eski} farkli grupta: {bolme[yeni]!r} != {bolme[eski]!r}"
        kontrol_edildi += 1
    assert kontrol_edildi > 0, "test kurulumu: split.csv'de en az bir zincir cifti bekleniyordu"


# --- Saldiri 4: kapinin donduregi kayitlar (_kayitlar) disaridan degistirilemez -------------------------


def test_kayitlar_onbellegi_disaridan_degistirilemez():
    """`pozisyon._kayitlar()` `MappingProxyType` doner (kaynak: 'Commit edilmis evren ve bolme
    tablolarindan salt okunur kayitlar'). Baska bir testin ya da analiz kodunun donen eslemi
    yerinde degistirip sonraki tum karar noktasi cagrilarini zehirlemesi mumkun olmamali
    (savusturuldu)."""
    donemler, gruplar = pozisyon._kayitlar()
    with pytest.raises(TypeError):
        donemler["SAHTEUSDT", 0] = (T("2020-01-01"), T("2020-01-02"), False)
    with pytest.raises(TypeError):
        gruplar["SAHTEUSDT"] = "A"
    with pytest.raises(TypeError):
        del gruplar[next(iter(gruplar))]


# --- Saldiri 5: gercek funding'siz donem, uyumlu bir funding cercevesiyle bile atlatilamaz ---------------


def test_gercek_fundingsiz_donem_uygun_funding_cercevesiyle_bile_atlatilamaz(tmp_path, monkeypatch):
    """On-kayit §2 'Funding'i bulunmayan donemler': tablodaki bayrak, cagiranin verdigi funding
    cercevesinden BAGIMSIZ uygulanir. Gercek bir funding'siz donem icin, karar noktasina TAM
    (tamlik kosullarini gecen) bir funding cercevesi verilse bile olay olusmamali (savusturuldu;
    tabloya geri sizinti yok)."""
    evren = universe.evren_yukle()
    evren = evren.copy()
    evren["_uzunluk"] = pd.to_datetime(evren["donem_bitis"]) - pd.to_datetime(evren["donem_baslangic"])
    # En az 32 gunluk donem gerekir: sinyal, listeleme yasi esigini (30 gun) gecmek icin donem
    # basindan yeterince sonra, ama donem icinde olmali.
    aday = evren.loc[~evren["haric"] & (evren["donem_id"] >= 0) & evren["donem_funding_yok"]
                     & (evren["donem_bitis"] <= pd.Timestamp(config.KESIF_SONU))
                     & (evren["_uzunluk"] >= pd.Timedelta(days=32))]
    if aday.empty:
        pytest.skip("Evren tablosunda KESIF araligina dusen, 32+ gunluk funding'siz gercek donem yok.")
    r = aday.sort_values("_uzunluk").iloc[0]
    sembol, donem_no = str(r["sembol"]), int(r["donem_id"])
    bas, bit = pd.Timestamp(r["donem_baslangic"]), pd.Timestamp(r["donem_bitis"])
    t_sinyal = bas + pd.Timedelta(days=31)  # >= 30 gun listeleme yasi, hala donem icinde
    assert t_sinyal <= bit

    bolme = split.split_oku()
    grup = bolme.loc[bolme["sembol"] == sembol, "grup"]
    if grup.empty:
        pytest.skip(f"{sembol} split.csv icinde yok.")
    kume = "KESIF" if grup.iloc[0] == "A" else "C1"

    zaman = pd.date_range(bas, bit, freq="4h")
    mumlar = pd.DataFrame({"open_time": zaman, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
    # Tamamen uyumlu (dolu, tam) bir funding cercevesi -- gercek boslugu gizlemeye calisiyor.
    fr = pd.DataFrame({"odeme_zamani": pd.date_range(bas, bit + H(4), freq="8h"), "aralik_saat": 8.0,
                       "oran": 0.0, "oran_8h": 0.0})
    tanim = pencere.hipotez_ufuklari("H1")

    # Kapi sertlestirme turu 2: kapi veriyi kendisi yukler; gercek sembol icin tam bir funding cercevesi
    # yukleyici kaydina (sentetik yol, gercek sembol adi) konur; cerceve kapiya verilemez.
    from kapi_yardimcisi import SENTETIK_VERI, _hazirla

    monkeypatch.setitem(SENTETIK_VERI, sembol, (_hazirla(mumlar, uygun_bas=bas, hacim=5e7, eksik_gunler=()), fr))
    kayit = tmp_path / "onay_gecici.md"
    kayit.write_text("bas\n", encoding="utf-8")
    monkeypatch.setattr(config, "ONAY_KAYDI", kayit)
    import contextlib

    kosu = split.onay_kosusu("H1", kume) if kume in config.ONAY_KUMELERI else contextlib.nullcontext()
    with kosu, pytest.raises(pozisyon.FundingTamDegil, match="evren tablosunda funding kaydi yok"):
        pozisyon.olay_karari(
            t_sinyal, tanim.birincil, tanim.bar, hipotez="H1", birincil_ufuk=tanim.birincil,
            kume=kume, sembol=sembol, donem_no=donem_no, sinyal_degerleri=sinyal("H1"),
            **esikler(tanim.bar))


# --- Saldiri 6: donem/kume sinirini asan fazladan barlar cikis fiyatina sizamaz -------------------------


def test_donem_sonrasi_asiri_fiyatli_barlar_cikis_fiyatina_sizamaz():
    """`mumlar_4h` donem/kume sinirinin COK otesine (400 gun) uzanip sinir sonrasi barlari asiri
    bir fiyata (999999) cekerse, donem sonuna kirpilan bir cikisin fiyati (B'de acilan barin
    close'u) bundan etkilenmemeli: kapi, cagiranin verdigi fazladan veriyi kendi donem/kume
    sinirlarina gore yok saymali (savusturuldu; kapinin bilinen siniri BURADA degil -- veri
    cercevesinin ICERIGININ dogrulugu degil, sinir disina TASMASI sinanir)."""
    donem_bas, donem_son = T("2025-01-01"), T("2025-02-05 20:00")
    t_sinyal = T("2025-02-05 04:00")  # donem basindan 35 gun sonra (listeleme yasi >= 30 gun)

    zaman = pd.date_range(donem_bas, donem_bas + pd.Timedelta(days=400), freq="4h")
    mumlar = pd.DataFrame({"open_time": zaman, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
    sizinti_maskesi = mumlar["open_time"] > donem_son
    assert sizinti_maskesi.any()
    mumlar.loc[sizinti_maskesi, ["open", "high", "low", "close"]] = 999999.0

    fr = pd.DataFrame({"odeme_zamani": pd.date_range(donem_bas, donem_son + H(4), freq="8h"),
                       "aralik_saat": 8.0, "oran": 0.0, "oran_8h": 0.0})
    tanim = pencere.hipotez_ufuklari("H1")

    p = pozisyon.olay_karari(
        t_sinyal, tanim.birincil, tanim.bar, hipotez="H1", birincil_ufuk=tanim.birincil,
        kume="KESIF", **veri(mumlar, fr, donem_bas, donem_son, uygun_bas=donem_bas),
        sinyal_degerleri=sinyal("H1"), **esikler(tanim.bar))

    assert p.plan.donem_sonu_mu, "test kurulumu: ufuk (18 bar) donem sonunu asmali (kirpma bekleniyordu)"
    assert p.plan.cikis.zaman == donem_son
    # Gercek cikis ani K'dir (B'de acilan barin KAPANISI, on-kayit §4 rev.9); donem_son'un (B) en
    # fazla bir bar (4 saat) sonrasi olabilir, sizan barlara (>= donem_son + 2 bar) hicbir zaman ulasamaz.
    assert p.plan.cikis_ani <= donem_son + H(4)
    assert p.p1 == pytest.approx(1.0), f"cikis fiyati sizan asiri degeri tasidi: {p.p1!r}"


# --- Saldiri 7: pozisyon_fundingi NaN toplami sessizce esit sayamaz (esitlik kenari) ---------------------


def test_pozisyon_fundingi_nan_toplami_sessizce_kabul_etmez():
    """`pozisyon_fundingi` toplami `not toplam == pozisyon.funding_toplami` ile karsilastirir.
    NaN hicbir sayiya (kendisi dahil) esit olmadigi icin bu, gercek bir NaN/gercek deger
    uyusmazligini doğru sekilde YAKALAR (savusturuldu): degistirilmis bir funding cercevesi
    yeniden hesaplamada NaN'a donuyorsa (`_plan_fundingi`), `nan == finite_deger` False'tur ve
    `not False` True'dur; ValueError firlatilir, sessizce gecmez."""
    p = _karar_h1()
    assert math.isfinite(p.funding_toplami)
    # Pozisyonun GERCEKTEN kullandigi pencere icindeki (giris .. cikis) bir kaydi kaldirarak
    # zinciri kirip `_plan_fundingi`nin NaN donmesini zorluyoruz. Serinin baska bir yerinden
    # (ör. tam ortadan) kayit silmek bu pozisyonu ETKILEMEZ (pencere disi kalir); saldiri bu
    # yuzden ozellikle giris/cikis penceresi icindeki bir kaydi hedefler.
    pencere_ici = TAM_FUND.index[(TAM_FUND["odeme_zamani"] > T_SINYAL_H1)
                                 & (TAM_FUND["odeme_zamani"] <= T_SINYAL_H1 + pd.Timedelta(days=3))]
    assert len(pencere_ici) > 0, "test kurulumu: pozisyon penceresinde funding kaydi bekleniyordu"
    # Ana oturum duzeltmesi (kapi sertlestirme turu): ilk kayit (08:00) tam giris aninda; on-kayit §4
    # giris anindaki odemeyi pozisyon disinda tutar ve tamligin ilk cift tabani giris anidir, bu yuzden onu
    # silmek zinciri kirmaz. Giris anindan KESIN SONRAKI bir kayit silinir (pencere_ici[1]); iddia ayni.
    assert TAM_FUND.loc[pencere_ici[1], "odeme_zamani"] > p.plan.giris
    bozuk = TAM_FUND.drop(pencere_ici[1]).reset_index(drop=True)
    # Kapi sertlestirme turu 2: funding cercevesi verilemez; bozuk seri yukleyici kaydina konur.
    from kapi_yardimcisi import SENTETIK_VERI

    SENTETIK_VERI[p.sembol] = (SENTETIK_VERI[p.sembol][0], bozuk)
    with pytest.raises(ValueError, match="ayni degil"):
        funding.pozisyon_fundingi(p)
