"""Bu tur icin saldiri testleri (commit ea45007..e08ee31).

Hedefler: data/donem.py (toplam_doneme_kes, ay_toplam_donemde), data/universe.py
(evren_kur toplam donem kesimi), analysis/00_veri_denetimi/calistir.py
(donem_sonu_degisimleri ic sinir siniflandirmasi, rapor_sayilari, git_durumu/
ortam_kaydi) ve a1_olcumu.py (d_kurali_olc, donem_sonu_turleri, varsayilan
kosu CSV izleri).

Aga cikmaz (tests/conftest.py `ag_kapali`). Gercek onbellek/CSV gerektiren
testler skipif ile korunur.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import config
from data import binance_vision as bv
from data import donem as donem_modulu
from data import funding as funding_modulu
from data import klines as klines_modulu
from data import universe as universe_modulu
from data.donem import Donem

KOK = Path(__file__).resolve().parents[1]
T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
ADIM = pd.Timedelta(hours=4)


def _yukle(ad: str, goreli_yol: str):
    yol = KOK / goreli_yol
    spec = importlib.util.spec_from_file_location(ad, yol)
    modul = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modul
    spec.loader.exec_module(modul)
    return modul


calistir = _yukle("_tur_b_calistir", "analysis/00_veri_denetimi/calistir.py")
a1 = _yukle("_tur_b_a1_olcumu", "analysis/00_veri_denetimi/a1_olcumu.py")

UNIVERSE_CSV_VAR = config.UNIVERSE_CSV.exists()


# ============================================================================
# 1) data/donem.py: toplam_doneme_kes ve ay_toplam_donemde uc durumlari
# ============================================================================


def test_toplam_doneme_kes_donem_sonundan_1ns_sonra_disarida_kalir():
    """On-kayit §2: toplam donem uclar dahil [DONEM_BASI, DONEM_SONU]; DONEM_SONU'ndan
    1 nanosaniye bile sonra olan bir satir donem disinda kalmali (sizinti testi:
    saniye duzeyi degil nanosaniye duzeyi sinir kontrolu)."""
    tam_sinirda = pd.Timestamp(config.DONEM_SONU)
    bir_ns_sonra = tam_sinirda + pd.Timedelta(nanoseconds=1)
    cerceve = pd.DataFrame({"t": [tam_sinirda, bir_ns_sonra]})
    kesik = donem_modulu.toplam_doneme_kes(cerceve, "t")
    assert list(kesik["t"]) == [tam_sinirda]


def test_toplam_doneme_kes_donem_basi_eksi_1ns_disarida_kalir():
    """DONEM_BASI'ndan 1 nanosaniye once olan bir satir donem disinda kalmali."""
    tam_sinirda = pd.Timestamp(config.DONEM_BASI)
    bir_ns_once = tam_sinirda - pd.Timedelta(nanoseconds=1)
    cerceve = pd.DataFrame({"t": [bir_ns_once, tam_sinirda]})
    kesik = donem_modulu.toplam_doneme_kes(cerceve, "t")
    assert list(kesik["t"]) == [tam_sinirda]


def test_toplam_doneme_kes_tz_naive_sutunda_sessizce_yanlis_sonuc_uretmez():
    """CLAUDE.md §5: tum zaman damgalari UTC'dir. Saat dilimsiz bir sutun
    `config.DONEM_BASI/SONU` (UTC'li) ile karsilastirilinca ya acikca hata
    vermeli ya da hicbir satiri sessizce yanlis (hepsini disarida/icinde)
    birakmamali. Sessiz yanlis sonuc, F1 denetiminin ve evren kurulumunun
    "toplam donem" sinirini fark etmeden atlamasi demektir."""
    naive = pd.DataFrame({"t": pd.to_datetime(["2023-01-01", "2023-06-01"])})
    assert naive["t"].dt.tz is None
    try:
        kesik = donem_modulu.toplam_doneme_kes(naive, "t")
    except TypeError:
        # Beklenen: pandas tz-naive/tz-aware karsilastirmasini acikca reddeder.
        return
    # Hata firlatilmadiysa en azindan sessizce hepsini disarida birakmamali
    # (2023 toplam donem icindedir); bu durum sessiz veri kaybina isaret eder.
    assert len(kesik) == 2, (
        "tz-naive sutun sessizce (hata vermeden) yanlis sekilde filtrelendi; "
        "toplam donem icindeki 2023 tarihleri sessizce elendi."
    )


@pytest.mark.parametrize("ay,beklenen", [
    ("2020-01", True),   # DONEM_BASI ayi, tam sifir dolgulu bicim
    ("2026-08", True),   # DONEM_SONU ayi, tam sifir dolgulu bicim
])
def test_ay_toplam_donemde_dogru_bicimli_sinir_aylari(ay, beklenen):
    """Referans: dogru bicimli (sifir dolgulu 'YYYY-MM') sinir aylari True olmali."""
    assert donem_modulu.ay_toplam_donemde(ay) is beklenen


def test_ay_toplam_donemde_bicimsiz_tek_haneli_ay_donem_sonunda_yanlis_sonuc():
    """GERILEME TESTI: 'YYYY-M' (sifirsiz, tek haneli ay) toplam donemin son ayi
    olan 2026-08 ile ayni ay sayilmali.

    Eski kusur (ed354ce ile duzeltildi): fonksiyon ayi metin olarak
    karsilastiriyordu. '2026-8' sozluk sirasinda '2026-08'den BUYUK oldugu icin
    ('8' > '0') Agustos 2026 toplam donemin disinda sayiliyordu. Bugun
    karsilastirma `pd.Period` degeri uzerinden yapilir ve bu test yesildir;
    metin karsilastirmasina geri donulurse kirilir. Pratik etkisi yoktu:
    bv.dosya_ayi() hep sifir dolgulu bicim uretir (denetci bulgusu D-C2:
    aciklama eski hatali davranisi bugunku davranis gibi anlatiyordu).
    """
    assert donem_modulu.ay_toplam_donemde("2026-8") is True, (
        "ay_toplam_donemde('2026-8') False dondu: ay karsilastirmasi yeniden metin "
        "uzerinden yapiliyor olabilir ('2026-8' > '2026-08' sozluk sirasinda). "
        "Agustos 2026 toplam donemin (2020-01..2026-08) icindedir."
    )


# ============================================================================
# 2) data/universe.py: evren_kur toplam donem oncesi/sonrasi sizinti
# ============================================================================


def _anahtar(onek: str, sembol: str, ay: str) -> str:
    return f"{onek}/{sembol}/{sembol}-4h-{ay}.zip"


@pytest.fixture
def sahte_bucket_donem_oncesi(monkeypatch):
    """Tek sembol: 2019-12 (toplam donem ONCESI) ve 2020-01 (donem ICI) dosyalari."""
    sembol = "YUSDT"
    aylar = ["2019-12", "2020-01"]
    zamanlar = pd.date_range("2019-12-30 00:00", "2020-01-02 20:00", freq="4h", tz="UTC")
    mumlar = pd.DataFrame({"open_time": zamanlar, "quote_volume": 1.0})
    fund = pd.DataFrame({
        "odeme_zamani": pd.date_range("2019-12-30 00:00", "2020-01-02 16:00", freq="8h", tz="UTC"),
        "aralik_saat": 8, "oran": 0.0, "oran_8h": 0.0,
    })
    monkeypatch.setattr(bv, "tum_sembol_dizinleri", lambda: [sembol])
    monkeypatch.setattr(bv, "mum_dosyalari", lambda s, bar: [_anahtar(bv.MUM_ONEKI, s, a) for a in aylar])
    monkeypatch.setattr(bv, "funding_dosyalari", lambda s: [_anahtar(bv.FUNDING_ONEKI, s, a) for a in aylar])
    monkeypatch.setattr(klines_modulu, "ham_mumlari_yukle", lambda s, bar=config.BAR_4H, yenile=False: mumlar.copy())
    monkeypatch.setattr(funding_modulu, "ham_funding_yukle", lambda s, yenile=False: fund.copy())
    monkeypatch.setattr(universe_modulu, "exchange_info_anlik_siniflari",
                        lambda yol=None: {sembol: ("PERPETUAL", "COIN")})
    return sembol


def test_evren_kur_toplam_donem_oncesini_kesmeli(sahte_bucket_donem_oncesi):
    """SALDIRI: 2019-12 dosyasi/barlari toplam donem (2020-01-01 basliyor) ONCESI;
    ne dosya sayisina ne ilk_ay'a ne de donem baslangicina sizmali (D-B3 simetrisi:
    toplam donem kesimi yalnizca SONRASINI degil ONCESINI de kesmeli)."""
    evren = universe_modulu.evren_kur()
    satir = evren.loc[evren["sembol"] == sahte_bucket_donem_oncesi].iloc[0]
    assert satir["ilk_ay"] == "2020-01"
    assert satir["dosya_sayisi_4h"] == 1
    assert satir["funding_dosya_sayisi"] == 1
    assert satir["donem_baslangic"] == pd.Timestamp("2020-01-01 00:00", tz="UTC")
    # 2019-12-30/31 barlari donem disinda kaldigi icin donem bar sayisi yalnizca
    # 2020-01-01 00:00 .. 2020-01-02 20:00 arasindaki barlari icermeli (12 bar).
    assert satir["donem_bar_sayisi"] == 12


# ============================================================================
# 3) calistir.py: donem_sonu_degisimleri ic sinir / rapor_sayilari / git
# ============================================================================


def test_donem_sonu_degisimleri_ic_donem_cakismasinda_cift_sayim_yok():
    """SALDIRI (D-A2 benzeri): eski (ay duzeyi) donemler ICTE cakisip birden fazla
    ay araligini kapsadiginda `_eski_donem_ici` her bari YALNIZCA BIR KEZ True
    saymali (mantiksal OR, ic ice donemlerin sayisi kadar cogaltmamali).
    Cift sayim olursa `eski_ici_yeni_disi_bar` sismis (yanlis buyuk) cikar."""
    zamanlar = pd.date_range("2021-01-01", periods=20, freq="4h", tz="UTC")
    # Iki eski donem kaydi kasten AYNI ay araligini (Ocak 2021) kapsiyor.
    eski = pd.DataFrame([
        {"sembol": "XUSDT", "haric": "False", "donem_id": 0,
         "donem_bas_ay": "2021-01", "donem_son_ay": "2021-01", "karantina_aylari": "[]"},
        {"sembol": "XUSDT", "haric": "False", "donem_id": 1,
         "donem_bas_ay": "2021-01", "donem_son_ay": "2021-01", "karantina_aylari": "[]"},
    ])
    ici = calistir._eski_donem_ici(zamanlar, eski)
    # Sonuc bir bool Series olmali; cakisan iki donem OR'landigi icin degerler
    # yalnizca True/False olmali (2, 3 gibi "cift sayim" degeri sizmamali).
    assert ici.dtype == bool
    assert set(ici.unique()) <= {True, False}
    assert bool(ici.all())  # tum barlar Ocak 2021 icinde


def test_donem_sonu_degisimleri_v1_deseni_ic_sinir_bar_sayaclari_dogru():
    """`_eski_donem_ici` ile yeni donem maskesinin XOR'u (eksi/arti) donemin GERCEKTEN
    degisen bar sayisini vermeli; bas/bitis ayni kalirken YALNIZ ic sinir degisen
    (CVCUSDT benzeri) durumda yalniz_ic_sinir True, ama eski/yeni bar farki da
    sifirdan farkli olmali (hicbir sey degismis gibi gorunmemeli)."""
    zamanlar = pd.date_range("2021-03-01", periods=20, freq="4h", tz="UTC")
    eski = pd.DataFrame([{"sembol": "XUSDT", "haric": "False", "donem_id": 0,
                          "donem_bas_ay": "2021-03", "donem_son_ay": "2021-03", "karantina_aylari": "[]"}])
    # Yeni donem eski ile ayni ayda ama ORTADA (10..12. barlar) bir bosluk birakiyor.
    yeni_d0 = Donem(zamanlar[0], zamanlar[9], 10, 10)
    yeni_d1 = Donem(zamanlar[13], zamanlar[-1], 7, 7)
    detay = {
        "sembol": "XUSDT", "_donemler": [yeni_d0, yeni_d1],
        "ilk_bar": zamanlar[0], "son_bar": zamanlar[-1],
        "_mumlar": pd.DataFrame({"open_time": zamanlar}),
    }
    sonuc = calistir.donem_sonu_degisimleri(eski, [detay]).set_index("sembol")
    # Barlar 10,11,12 eskide donem ici (tek eski donem tum ayi kapsiyor) ama
    # yenide hicbir donemde degil -> eski_ici_yeni_disi_bar >= 3 olmali.
    assert sonuc.at["XUSDT", "eski_ici_yeni_disi_bar"] >= 3
    assert bool(sonuc.at["XUSDT", "degisti"]) is True


def test_rapor_sayilari_bos_ama_semali_tablolarla_cokmez():
    """Bos evren (hic sembol islenmemis) icin, dogru SEMALI (0 satirli) tablolar
    verildiginde rapor_sayilari cokmemeli (butun uretici fonksiyonlar dogru
    sema doner). Bu, 'bos tablo' saldirisinin YIKICI olmadigini gosterir."""
    detaylar: list[dict] = []
    evren0 = pd.DataFrame(columns=[
        "sembol", "ilk_ay", "son_ay", "dosya_sayisi_4h", "funding_dosya_sayisi",
        "sozlesme_tipi", "dayanak_tipi", "settled_aylari", "haric", "haric_gerekce",
        "donem_id", "donem_baslangic", "donem_bitis", "donem_bar_sayisi",
        "donem_gercek_bar_sayisi", "donem_funding_yok",
    ])
    evren0["haric"] = evren0["haric"].astype(bool)
    evren0["donem_id"] = evren0["donem_id"].astype("int64")
    evren0["donem_bitis"] = pd.to_datetime(evren0["donem_bitis"], utc=True)
    bolme0 = pd.DataFrame(columns=["sembol", "varlik_anahtari", "grup"])

    ozet0 = pd.DataFrame(columns=[
        "sembol", "bar_4h", "eksik_bar", "gun_1d", "donem_sayisi",
        "donemler_yeniden_turetimle_ayni", "donem_ici_bar", "ne_donem_ne_dolgu_bar",
        "funding_kayit", "funding_son_donem_sonrasi_atilan", "funding_donemler_arasi_atilan",
        "funding_son_donem_sonrasi_ilk_gecikme_saat",
        "funding_son_donem_sonrasi_ilk_gecikme_bitisten_saat", "funding_donem_sonrasi_atilan",
        "funding_ilk_donem_oncesi", "son_donem_bitis",
    ])

    tablolar = {
        "sembol_ozeti": ozet0,
        "delist_siniflandirmasi": calistir.delist_tablosu(evren0, detaylar) if UNIVERSE_CSV_VAR else
            pd.DataFrame(columns=["sembol", "sinif", "sonraki_dolgu_bar", "teslim_son_bar_icinde",
                                  "teslim_eksi_bitis_saat", "son_donem_bitis"]),
        "dolgu_kosulari": calistir.dolgu_tablosu(detaylar),
        "kisa_sifir_kosulari": calistir.kisa_sifir_tablosu(detaylar),
        "funding_siz_donemler": calistir.funding_siz_donemler(evren0),
        "settled_aylari": calistir.settled_karsilastirma(detaylar),
        "settled_icerik": calistir.settled_icerik(detaylar, [], calistir.settled_karsilastirma(detaylar)),
        "butunluk_sicramalari": calistir.sicramalari_grupla(detaylar),
        "kisa_donemler": calistir.kisa_donemler(detaylar),
        "donem_aralari": calistir.donem_aralari_tablosu(detaylar),
    }
    bosluklar, bosluk_olaylari = calistir.bosluklari_grupla(detaylar)
    tablolar["bosluklar"] = bosluklar
    tablolar["bosluk_olaylari"] = bosluk_olaylari
    capraz, _yogun = calistir.capraz_ozet(detaylar)
    tablolar["cross_dogrulama"] = capraz
    if not UNIVERSE_CSV_VAR:
        tablolar["delist_siniflandirmasi"].attrs["durum_sayimi"] = {}

    sonuc = calistir.rapor_sayilari(tablolar, evren0, bolme0)
    assert isinstance(sonuc, pd.DataFrame)
    assert set(sonuc.columns) == {"bolum", "kalem", "deger"}


def test_rapor_sayilari_eksik_sutunda_sessizce_yanlis_sayi_uretmez():
    """SALDIRI: sembol_ozeti tablosunda beklenen bir sutun (ornegin 'donem_sayisi')
    eksikse fonksiyon YUKSEK SESLE hata vermeli (KeyError), sessizce 0/NaN
    uretip rapor_sayilari'ni yanlis bir sayiyla doldurmamali."""
    ozet_eksik = pd.DataFrame({"sembol": ["XUSDT"]})  # donem_sayisi sutunu YOK
    tablolar = {"sembol_ozeti": ozet_eksik}
    evren0 = pd.DataFrame(columns=["sembol", "haric", "haric_gerekce", "donem_id"])
    bolme0 = pd.DataFrame(columns=["sembol", "varlik_anahtari", "grup"])
    with pytest.raises(KeyError):
        calistir.rapor_sayilari(tablolar, evren0, bolme0)


def test_git_durumu_git_calismiyorsa_sessizce_yanlis_commit_uydurmaz(monkeypatch):
    """git yoksa (FileNotFoundError) ya da calisma agaci komutu patlarsa
    git_durumu sessizce sahte/varsayilan bir commit hash'i UYDURMAMALI;
    acikca 'bilinmiyor' demeli (denetim raporunun hangi koddan uretildigi
    izlenebilir kalsin)."""
    def patlayan_run(*a, **k):
        raise FileNotFoundError("git bulunamadi (simule edildi)")

    monkeypatch.setattr(calistir.subprocess, "run", patlayan_run)
    sonuc = calistir.git_durumu()
    assert sonuc["bilinmiyor"] is True
    assert sonuc["commit"] == "bilinmiyor"
    assert sonuc["degisiklikler"] == []


def test_ortam_kaydi_git_bilinmiyorken_cokmez_ve_acikca_isaretler():
    """git_durumu 'bilinmiyor' dondurdugunde ortam_kaydi cokmemeli ve
    calisma_agaci satirini 'bilinmiyor (git yok)' olarak acikca isaretlemeli
    (sessizce 'temiz' UYDURMAMALI -- kirli bir agac 'temiz' gorunurse
    tekrarlanabilirlik iddiasi yanlis olur)."""
    git = {"commit": "bilinmiyor", "degisiklikler": [], "bilinmiyor": True}
    baslangic = pd.Timestamp("2026-01-01", tz="UTC")
    bitis = pd.Timestamp("2026-01-01 00:00:05", tz="UTC")
    tablo = calistir.ortam_kaydi(git, baslangic, bitis).set_index("bilesen")
    assert tablo.at["calisma_agaci", "surum"] == "bilinmiyor (git yok)"
    assert tablo.at["calisma_agaci", "surum"] != "temiz"


# ============================================================================
# 4) a1_olcumu.py: iki donem sizintisi, oran sutunu bagimsizligi, TLM/ICP deseni
# ============================================================================


def _fund(zamanlar, aralik=4.0, oran=None):
    z = pd.DatetimeIndex(sorted(zamanlar))
    if oran is None:
        oran = [0.0001] * len(z)
    return pd.DataFrame({"odeme_zamani": z, "aralik_saat": aralik, "oran": oran, "oran_8h": oran})


def _ritim(bas, son, saat):
    return list(pd.date_range(bas, son, freq=f"{saat}h", tz="UTC"))


def test_d_kurali_olc_ikinci_donem_kayitlari_birinci_donemin_hesabina_sizmaz():
    """SALDIRI: iki donemli bir sembolde, ikinci (cok sonraki) donemin funding
    kayitlari birinci donemin `disarida_kalan`/tamlik (rev.8: `tamlik` ve kosullari;
    rev.7'de `tamlik_mevcut`/`tamlik_d`) hesabini DEGISTIRMEMELI. Degistirirse `donem_sonrasi_kayitlari_at` sonrasi
    'seri' butun donemleri tek bir zaman dizisinde tuttugu icin ikinci donemin
    kayitlari birinci donemin tamlik zincirine sessizce eklenmis demektir."""
    bitis0 = T("2025-04-14 08:00")
    donem0 = Donem(T("2025-04-01 00:00"), bitis0, 80, 80)
    fund0 = _fund(_ritim("2025-04-12 00:00", "2025-04-14 12:00", 4))

    donem1 = Donem(T("2025-05-01 00:00"), T("2025-05-02 08:00"), 8, 8)
    fund1 = _fund(_ritim("2025-04-30 00:00", "2025-05-02 12:00", 4))

    fund_tek = fund0
    fund_iki = pd.concat([fund0, fund1], ignore_index=True).sort_values(
        "odeme_zamani", ignore_index=True
    )

    satir_tek = a1.d_kurali_olc("X", [donem0], ["delist_SETTLING"], fund_tek)[0]
    satir_iki = a1.d_kurali_olc("X", [donem0, donem1], ["uzun_bosluk", "delist_SETTLING"], fund_iki)[0]

    assert satir_tek["disarida_kalan"] == satir_iki["disarida_kalan"]
    # Rev.9 kosul adlari (capa_var, aralik_gecerli, zincir_tam, son_tam); rev.8'de kayit_var,
    # baslangic_tam, ic_tam vardi.
    for anahtar in ("tamlik", "capa_var", "aralik_gecerli", "zincir_tam", "son_tam"):
        assert satir_tek[anahtar] == satir_iki[anahtar], anahtar


def test_d_kurali_olc_oran_sutunu_olmadan_sayim_degismez():
    """SALDIRI: `d_kurali_olc` yalniz zaman damgasi ve aralik kullanmali; 'oran' sutunu hic
    yoksa ya da oranlarin DEGERI ne olursa olsun disarida_kalan/tamlik sayimlari DEGISMEMELI
    (bu bir olcum betigidir, deger hesaplamaz -- anayasa §3.1).

    REV.11 NOTU (madde 8): on-kayit §4 "Gecerli oran" tamlik kuralina kayit duzeyinde bir oran
    kosulu ekledi: "Pozisyonun funding penceresine giren her kaydin oran degeri sonlu bir sayi
    olmalidir." Bu yuzden NaN oranli seri artik tamligi DEGISTIRIR ve testin NaN kolu ayri bir
    teste tasindi (asagida). Oranin DEGERI hala okunmaz; okunan sey sonlu olup olmadigidir --
    bu bir tamlik bilgisidir, §3.1'in yasakladigi deger analizi degildir."""
    bitis0 = T("2025-04-14 08:00")
    donem0 = Donem(T("2025-04-01 00:00"), bitis0, 80, 80)
    zamanlar = _ritim("2025-04-12 00:00", "2025-04-14 12:00", 4)

    fund_normal = _fund(zamanlar, oran=[0.0002] * len(zamanlar))
    fund_buyuk = _fund(zamanlar, oran=[-5.0] * len(zamanlar))  # sonlu ama cok farkli DEGER
    fund_oransiz = pd.DataFrame({
        "odeme_zamani": pd.DatetimeIndex(sorted(zamanlar)), "aralik_saat": 4.0,
    })  # 'oran'/'oran_8h' sutunlari YOK

    satir_normal = a1.d_kurali_olc("X", [donem0], ["delist_SETTLING"], fund_normal)[0]
    satir_buyuk = a1.d_kurali_olc("X", [donem0], ["delist_SETTLING"], fund_buyuk)[0]
    satir_oransiz = a1.d_kurali_olc("X", [donem0], ["delist_SETTLING"], fund_oransiz)[0]

    for anahtar in ("disarida_kalan", "tamlik", "capa_var", "aralik_gecerli", "zincir_tam",
                    "son_tam"):  # Rev.9 kosul adlari
        assert satir_normal[anahtar] == satir_buyuk[anahtar] == satir_oransiz[anahtar], anahtar


def test_d_kurali_olc_nan_oran_rev11den_beri_tamligi_degistirir():
    """Rev.11 madde 8 ("Gecerli oran"): NaN oranli bir kayit pozisyonun funding'ini TAM OLMAYAN
    yapar. Olcum betigi gercek tamlik kodunu cagirdigi icin sayim da degisir. Bu, kuralin
    beklenen sonucudur; betik yine oranin DEGERINI okumaz."""
    bitis0 = T("2025-04-14 08:00")
    donem0 = Donem(T("2025-04-01 00:00"), bitis0, 80, 80)
    zamanlar = _ritim("2025-04-12 00:00", "2025-04-14 12:00", 4)
    normal = a1.d_kurali_olc("X", [donem0], ["delist_SETTLING"],
                             _fund(zamanlar, oran=[0.0002] * len(zamanlar)))[0]
    nan_satir = a1.d_kurali_olc("X", [donem0], ["delist_SETTLING"],
                                _fund(zamanlar, oran=[float("nan")] * len(zamanlar)))[0]
    assert nan_satir["tamlik"] != normal["tamlik"]
    # Rev.9 kosullari degismedi: dusuren kural yalnizca yeni oran kosuludur.
    for anahtar in ("capa_var", "aralik_gecerli", "zincir_tam", "son_tam"):
        assert nan_satir[anahtar] == normal[anahtar], anahtar


def test_donem_sonu_turleri_dolgu_ile_bitisik_uzun_boslukta_dolgu_onceliklidir():
    """TLM/ICP deseni: bir donem sonu HEM 6+ barlik dolgu kosusuyla HEM de o
    dolgunun hemen ardindan gelen >7 gunluk gercek eksik bar boslugu ile
    ayriliyorsa, `donem_sonu_turleri` bu ara donem sonunu 'dolgu_kosusu' olarak
    etiketlemeli (docstring: 'iki donem arasinda 6+ barlik sifir hacim kosusu
    varsa dolgu_kosusu' -- bosluk da ayrica varsa bile dolgu onceliklidir).
    Bu davranis DEGISMEDEN kalmali; degisirse D kuralinin 'tur' siniflandirmasi
    tutarsiz hale gelir ve RESULTS §14.5 sayimlari kayar."""
    adim = ADIM
    bas = T("2024-01-01 00:00")
    zam, hac = [], []
    for i in range(6):
        zam.append(bas + i * adim); hac.append(1.0)
    # 6 barlik dolgu kosusu (esigi tam karsilar).
    t = bas + 6 * adim
    for _ in range(6):
        zam.append(t); hac.append(0.0); t += adim
    # Dolgu kosusunun hemen ardindan >7 gunluk (43 bar) GERCEK eksik bar
    # (serede hic yok -- zam listesine hic eklenmiyor).
    t += 43 * adim
    for i in range(6):
        zam.append(t + i * adim); hac.append(1.0)
    zamanlar = pd.DatetimeIndex(zam)
    hacim = pd.Series(hac)

    donemler = donem_modulu.listeleme_donemleri(zamanlar, hacim, config.BAR_4H)
    assert len(donemler) == 2, "beklenen: dolgu + bosluk BIRLIKTE tek bir donem ayrimi olusturur"

    turler = a1.donem_sonu_turleri(donemler, "SETTLING", donemler[-1].bitis, zamanlar, hacim)
    assert turler == ["dolgu_kosusu", "delist_SETTLING"]


def test_donem_sonu_turleri_kisa_sifir_kosusu_dolgu_sayilmaz():
    """Esigin (6 bar) ALTINDA kalan bir sifir-hacim kosusu (5 bar) bir donemi
    BOLMEZ (donem.py esigi); ama eger baska bir sebeple (43 barlik gercek
    bosluk) donem bolunuyorsa, o kisa sifir kosusu 'dolgu_kosusu' sayilip
    yanlislikla siniflandirmayi degistirmemeli -- gercek ayirici uzun bosluktur."""
    adim = ADIM
    bas = T("2024-02-01 00:00")
    zam, hac = [], []
    for i in range(6):
        zam.append(bas + i * adim); hac.append(1.0)
    t = bas + 6 * adim
    for _ in range(5):  # esik ALTI: 5 < DOLGU_KOSU_ESIGI_BAR (6)
        zam.append(t); hac.append(0.0); t += adim
    t += 43 * adim  # 43 bar (>7 gun) gercek eksik
    for i in range(6):
        zam.append(t + i * adim); hac.append(1.0)
    zamanlar = pd.DatetimeIndex(zam)
    hacim = pd.Series(hac)

    donemler = donem_modulu.listeleme_donemleri(zamanlar, hacim, config.BAR_4H)
    assert len(donemler) == 2
    turler = a1.donem_sonu_turleri(donemler, "TRADING", donemler[-1].bitis, zamanlar, hacim)
    assert turler == ["uzun_bosluk", "veri_sonu"]


# ============================================================================
# 5) a1_olcumu.py: varsayilan kosu oran-degeri CSV'lerini URETMEMELI
# ============================================================================


def test_a1_olcumu_varsayilan_kosu_oran_csvlerini_uretmez(tmp_path, monkeypatch):
    """SALDIRI: `--oran-degerleri` bayragi verilmeden `main()` calistirildiginda
    `a1_uzlasma_sonrasi_oranlar_tam.csv` ve `a1_teslimsiz_son_bar_funding_tam.csv`
    URETILMEMELI (modul belgesi: 'Varsayilan kosu bu dosyalari URETMEZ'). Evren,
    exchangeInfo goruntusu ve funding TEK sentetik sembolle sahtelenir (tamamen
    bos evren `main()`in kendisini `max() of empty sequence` ile cokertir; bu
    testin amaci CSV URETIM KOSULUNU sinamaktir, o baska bir kirilganliktir).
    Ag ve onbellege erisim yoktur."""
    sembol = "ZUSDT"
    donem_bas = T("2025-01-01 00:00")
    donem_bit = T("2025-01-05 00:00")
    evren = pd.DataFrame([{
        "sembol": sembol, "ilk_ay": "2025-01", "son_ay": "2025-01",
        "dosya_sayisi_4h": 1, "funding_dosya_sayisi": 1,
        "sozlesme_tipi": "PERPETUAL", "dayanak_tipi": "COIN", "settled_aylari": "",
        "haric": False, "haric_gerekce": "", "donem_id": 0,
        "donem_baslangic": donem_bas, "donem_bitis": donem_bit,
        "donem_bar_sayisi": 25, "donem_gercek_bar_sayisi": 25, "donem_funding_yok": False,
    }])
    evren["donem_baslangic"] = pd.to_datetime(evren["donem_baslangic"], utc=True)
    evren["donem_bitis"] = pd.to_datetime(evren["donem_bitis"], utc=True)

    bos_anlik = pd.DataFrame(columns=[
        "symbol", "pair", "contractType", "status", "deliveryDate", "onboardDate",
        "underlyingType", "underlyingSubType", "baseAsset", "quoteAsset", "marginAsset",
    ])
    bos_anlik.attrs["alinma_zamani_utc"] = "2026-01-01T00:00:00Z"
    bos_anlik.attrs["ham_yanit_sha256"] = "x"

    fund_sahte = _fund(_ritim("2025-01-04 12:00", "2025-01-05 04:00", 4))

    monkeypatch.setattr(a1.universe_modulu, "evren_yukle", lambda: evren)
    monkeypatch.setattr(a1.universe_modulu, "exchange_info_anlik_yukle", lambda: bos_anlik)
    monkeypatch.setattr(funding_modulu, "ham_funding_yukle", lambda s, yenile=False: fund_sahte.copy())
    # git_durumu gercek git'i cagirabilir (ag degil, sorun yok); ortam_kaydi de oyle.

    # D-B1 karariyla oran degeri yolu ve onun cikti sabitleri koddan kaldirildi;
    # kontrol artik dosya ADIYLA ve sutun adiyla yapiliyor.
    for ad in ("CIKTI", "CIKTI_KONUM", "CIKTI_ONERI", "CIKTI_D", "CIKTI_ORTAM"):
        monkeypatch.setattr(a1, ad, tmp_path / f"{ad}.csv")

    a1.main([])

    assert (tmp_path / "CIKTI.csv").exists()
    assert (tmp_path / "CIKTI_D.csv").exists()
    for ad in ("a1_uzlasma_sonrasi_oranlar_tam.csv", "a1_teslimsiz_son_bar_funding_tam.csv"):
        assert not (tmp_path / ad).exists(), (
            f"kosu {ad} benzeri bir oran-degeri CSV'si URETTI; bu yol kaldirildi "
            "(veri denetimi sinirinda deger sizintisi)."
        )
    for yol in tmp_path.glob("*.csv"):
        assert not (set(pd.read_csv(yol, nrows=0).columns) & {"oran", "oran_8h"}), (
            f"{yol.name} oran sutunu yaziyor"
        )
