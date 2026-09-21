"""Bu tur saldiri testleri.

Hedefler:
1. `analysis/00_veri_denetimi/calistir.py` `delist_tablosu`:
   `teslimden_sonra_funding_kayit` sutununun 1 dakikalik tolerans siniri ve
   `deliveryDate` NaT (exchangeInfo_disi) durumu.
2. `calistir.csv_yaz`: GERCEK es zamanli (thread) yazma; yarim/bozuk dosya
   kalmamali, gecici dosya sizmamali.
3. `analysis/00_veri_denetimi/karsilastir.py`: CRLF normallestirmesi uctan uca
   (`main`), coklu tekrarli satir sayimi.
4. `data/donem.py` `_gun_bar_sayilari` (calistir.py icinde): gun sinirinin
   nanosaniye duzeyinde tam kapanmasi.
5. `a1_olcumu.d_kurali_olc`: 1 gunluk izgarada `giris_aday`in donem basindan
   once kaymasi (kisa donem).
6. `calistir.gunluk_sinir_tablosu`: delist tablosunda olmayan (sinif bilinmeyen)
   sembol ve tek gunluk donem (bas_gunu == bitis_gunu) rapor_sayilari kalemi.

Aga cikmaz (tests/conftest.py `ag_kapali`). Mevcut test dosyalarina dokunulmadi;
bu tamamen yeni bir dosyadir.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import threading
from pathlib import Path

import pandas as pd
import pytest

import config
from data import universe as universe_modulu
from data.donem import Donem

DIZIN = config.ANALIZ_DIZINI / "00_veri_denetimi"
sys.path.insert(0, str(DIZIN))


def _yukle(ad: str, dosya: str):
    spec = importlib.util.spec_from_file_location(ad, DIZIN / dosya)
    modul = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modul
    spec.loader.exec_module(modul)
    return modul


calistir = _yukle("_tur_d_calistir", "calistir.py")
a1 = _yukle("_tur_d_a1", "a1_olcumu.py")
karsilastir = _yukle("_tur_d_karsilastir", "karsilastir.py")

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
DK = pd.Timedelta(minutes=1)
SN = pd.Timedelta(seconds=1)


# ============================================================================
# 1) delist_tablosu: teslimden_sonra_funding_kayit
# ============================================================================


def _sinif_df(satirlar):
    return pd.DataFrame(satirlar, columns=["sembol", "sinif", "deliveryDate", "son_donem_bitis"])


def _anlik_sahte():
    df = pd.DataFrame(columns=["symbol"])
    df.attrs["alinma_zamani_utc"] = "2026-01-01T00:00:00Z"
    return df


def test_teslimden_sonra_funding_kayit_1dk_tolerans_siniri(monkeypatch):
    """SALDIRI: deliveryDate + 1 dk TAM sinirindaki kayit sayilmamali (strict >),
    59. saniyede sayilmamali, 61. saniyede sayilmali. Sinir kaymasi delist
    sembolde 'uzlasma sonrasi funding' sayimini yanlislar (rev.8 kalemi)."""
    teslim = T("2025-04-14 09:00")
    bitis = T("2025-04-14 08:00")
    sinif = _sinif_df([{"sembol": "XUSDT", "sinif": universe_modulu.SETTLING_DURUMU,
                        "deliveryDate": teslim, "son_donem_bitis": bitis}])
    monkeypatch.setattr(universe_modulu, "exchange_info_anlik_yukle", lambda: _anlik_sahte())
    monkeypatch.setattr(universe_modulu, "delist_sinifi", lambda e, a: sinif)

    zamanlar = pd.DatetimeIndex([teslim + 59 * SN, teslim + DK, teslim + DK + 1 * SN])
    detaylar = [{"sembol": "XUSDT", "son_bar": bitis, "dolgu_bar_son": 0,
                "_funding_zamanlari": zamanlar}]
    tablo = calistir.delist_tablosu(pd.DataFrame(), detaylar)
    assert len(tablo) == 1
    # yalniz 61. saniyedeki kayit (teslim + DK + 1sn) sinirin gercekten disinda;
    # 59sn ve tam DK (60sn) sinirin ustunde/icinde sayilmamali.
    assert tablo.iloc[0]["teslimden_sonra_funding_kayit"] == 1


def test_teslimden_sonra_funding_kayit_deliverydate_nat_ise_nan(monkeypatch):
    """SALDIRI: exchangeInfo_disi (deliveryDate yok) sembolde bu sutun NaN
    olmali; sifir ya da baska bir sayi UYDURULMAMALI, funding kayitlari
    olsa bile sessizce 0'a dusmemeli."""
    bitis = T("2025-04-14 08:00")
    sinif = _sinif_df([{"sembol": "YUSDT", "sinif": "exchangeInfo_disi",
                        "deliveryDate": pd.NaT, "son_donem_bitis": bitis}])
    monkeypatch.setattr(universe_modulu, "exchange_info_anlik_yukle", lambda: _anlik_sahte())
    monkeypatch.setattr(universe_modulu, "delist_sinifi", lambda e, a: sinif)

    zamanlar = pd.DatetimeIndex([bitis + DK, bitis + pd.Timedelta(hours=4)])
    detaylar = [{"sembol": "YUSDT", "son_bar": bitis, "dolgu_bar_son": 0,
                "_funding_zamanlari": zamanlar}]
    tablo = calistir.delist_tablosu(pd.DataFrame(), detaylar)
    assert pd.isna(tablo.iloc[0]["teslimden_sonra_funding_kayit"])


def test_teslimden_sonra_funding_kayit_bos_zaman_dizisinde_sifir(monkeypatch):
    """Hic funding kaydi olmayan (bos DatetimeIndex) delist sembolde bu sutun 0
    olmali, hata firlatmamali ya da NaN gostermemeli (deliveryDate mevcutken)."""
    teslim = T("2025-04-14 09:00")
    bitis = T("2025-04-14 08:00")
    sinif = _sinif_df([{"sembol": "ZUSDT", "sinif": universe_modulu.SETTLING_DURUMU,
                        "deliveryDate": teslim, "son_donem_bitis": bitis}])
    monkeypatch.setattr(universe_modulu, "exchange_info_anlik_yukle", lambda: _anlik_sahte())
    monkeypatch.setattr(universe_modulu, "delist_sinifi", lambda e, a: sinif)

    detaylar = [{"sembol": "ZUSDT", "son_bar": bitis, "dolgu_bar_son": 0,
                "_funding_zamanlari": pd.DatetimeIndex([], tz="UTC")}]
    tablo = calistir.delist_tablosu(pd.DataFrame(), detaylar)
    assert tablo.iloc[0]["teslimden_sonra_funding_kayit"] == 0


# ============================================================================
# 2) csv_yaz: GERCEK es zamanli yazma
# ============================================================================


@pytest.mark.xfail(
    strict=False,
    reason="Eszamanli kosu desteklenmez: koruma csv_yaz'da degil, kosu kilidindedir "
           "(calistir.kosu_kilidi; tests/test_kosu_kilidi.py). Sonuc platforma bagli: "
           "Windows'ta ayni hedefe eszamanli os.replace PermissionError verir, POSIX'te "
           "os.replace atomiktir ve test gecebilir (denetci bulgusu D-B2).",
)
def test_csv_yaz_gercek_es_zamanli_yazmalar_dosyayi_bozmaz(tmp_path):
    """SALDIRI: iki thread ayni hedefe farkli icerik yazarsa dosya YARIM/BOZUK
    kalmamali (biri digerini tamamen degistirmeli, karisik bayt olmamali) ve
    hicbir gecici (.tmp) dosya geride kalmamali."""
    hedef = tmp_path / "es_zamanli.csv"
    hatalar = []

    def yaz(deger, tekrar):
        for _ in range(tekrar):
            try:
                calistir.csv_yaz(pd.DataFrame({"a": [deger] * 50}), hedef)
            except Exception as hata:  # pragma: no cover - saldiri teshisi
                hatalar.append(hata)

    iplikler = [threading.Thread(target=yaz, args=(i, 20)) for i in range(8)]
    for t in iplikler:
        t.start()
    for t in iplikler:
        t.join()

    assert not hatalar
    # Dosya HER ZAMAN gecerli, tek bir yazarin TAM ciktisi olmali: butun satirlar
    # ayni degeri tasimali (karisik/yarim yazma degerleri karistirmaz).
    okunan = pd.read_csv(hedef)
    assert okunan["a"].nunique() == 1
    assert len(okunan) == 50
    # Gecici dosya sizintisi yok.
    kalanlar = [p.name for p in tmp_path.iterdir() if p.name != hedef.name]
    assert kalanlar == [], f"gecici dosya(lar) kaldi: {kalanlar}"


# ============================================================================
# 3) karsilastir.py: CRLF uctan uca ve coklu tekrarli satir
# ============================================================================


def test_karsilastir_main_crlf_farkini_ayni_sayar(tmp_path, monkeypatch):
    """SALDIRI: onceki kosu (git'ten) CRLF satir sonuyla gelirse ve yerel dosya
    LF ise, icerik MANTIKEN ayniysa `durum` 'ayni' olmali (main() ikisini de
    normallestirir). Normallestirme main()'de degil de yalniz bir tarafta
    yapiliyorsa bu test 'farkli' donup saldiriyi yakalar."""
    monkeypatch.setattr(karsilastir, "BU_DIZIN", tmp_path)
    monkeypatch.setattr(karsilastir, "KOK", tmp_path.parent)
    monkeypatch.setattr(karsilastir, "CIKTI", tmp_path / "karsilastirma_tam.csv")

    (tmp_path / "ornek_tam.csv").write_text("a,b\n1,2\n3,4\n", encoding="utf-8")

    def sahte_run(cmd, cwd=None, capture_output=None, text=None, check=None):
        class R:
            pass
        r = R()
        if cmd[:2] == ["git", "ls-tree"]:
            r.returncode = 0
            r.stdout = "ornek_tam.csv\n"
        elif cmd[:2] == ["git", "show"]:
            r.returncode = 0
            r.stdout = b"a,b\r\n1,2\r\n3,4\r\n"
        else:  # pragma: no cover
            raise AssertionError(f"beklenmeyen komut: {cmd}")
        return r

    monkeypatch.setattr(karsilastir.subprocess, "run", sahte_run)
    karsilastir.main(["--onceki", "deadbeef"])

    sonuc = pd.read_csv(tmp_path / "karsilastirma_tam.csv")
    satir = sonuc.loc[sonuc["dosya"] == "ornek_tam.csv"].iloc[0]
    assert satir["durum"] == "ayni", (
        "CRLF/LF farki 'farkli' olarak raporlandi; icerik mantiken ayniydi "
        "(satir sonu normallestirmesi eksik olabilir)."
    )
    assert satir["yalniz_onceki_satir"] == 0 and satir["yalniz_yeni_satir"] == 0


def test_tablo_karsilastir_coklu_tekrarli_satirlar_dogru_sayilir():
    """SALDIRI: ayni satirin FARKLI tekrar sayilarda gectigi iki tabloda
    (3 kez -> 1 kez, ayrica yeni tabloda 2 kez gecen baska bir satir) coklukla
    sayim yapilmali; Counter kume farkina degil COKLUK farkina dayanmali."""
    onceki = "a\nX\nX\nX\nY\n"
    yeni = "a\nX\nZ\nZ\nY\n"
    s = karsilastir.tablo_karsilastir(onceki, yeni)
    # X: onceki 3, yeni 1 -> 2 fazla eski; Z: onceki 0, yeni 2 -> 2 fazla yeni.
    assert s["yalniz_onceki_satir"] == 2
    assert s["yalniz_yeni_satir"] == 2


# ============================================================================
# 4) _gun_bar_sayilari: gun sinirinin nanosaniye duzeyinde kapanmasi
# ============================================================================


def test_gun_bar_sayilari_gun_sinirinda_nanosaniye_duzeyinde_ayrilir():
    """SALDIRI: gunun son nanosaniyesindeki bar ONCEKI gune ait sayilmali,
    tam gun basindaki bar (00:00:00.000000000) SONRAKI gune ait sayilmali.
    Bir nanosaniyelik kayma bile barin yanlis gune sizmasina yol acmamali."""
    gun = T("2025-04-14 00:00")
    onceki_gun_son_an = gun - pd.Timedelta(nanoseconds=1)
    donem = Donem(T("2025-04-13 00:00"), T("2025-04-14 20:00"), 12, 12)
    zamanlar = pd.DatetimeIndex([onceki_gun_son_an, gun, gun + pd.Timedelta(hours=4)])

    ici_onceki, disi_onceki = calistir._gun_bar_sayilari(zamanlar, gun - pd.Timedelta(days=1), donem)
    ici_bugun, disi_bugun = calistir._gun_bar_sayilari(zamanlar, gun, donem)

    assert ici_onceki + disi_onceki == 1  # yalniz onceki_gun_son_an
    assert ici_bugun + disi_bugun == 2    # gun ve gun+4h


# ============================================================================
# 5) a1_olcumu.d_kurali_olc: 1 gunluk giris_aday donem basina kirpilir
# ============================================================================


def test_d_kurali_olc_1d_giris_aday_donem_basindan_once_kayamaz():
    """SALDIRI: cok kisa (tek barlik) bir donemde 1 gunluk aday kuralin girisi
    `cikis_ani_aday.floor('1D') - adim` hesabiyla donem basindan ONCEYE
    dusebilir; kod bunu `max(donem.baslangic, ...)` ile kirpmali. Kirpma
    calismazsa giris donem disina tasar ve temsili pozisyon donem oncesi
    funding'i sizdirabilir."""
    donem = Donem(T("2025-04-14 20:00"), T("2025-04-14 20:00"), 1, 1)
    fund = pd.DataFrame({"odeme_zamani": pd.DatetimeIndex([]), "aralik_saat": pd.Series([], dtype=float)})
    satir = a1.d_kurali_olc("X", [donem], ["delist_SETTLING"], fund, config.BAR_1D)[0]
    assert satir["giris_aday"] >= donem.baslangic
    assert satir["giris_aday"] == donem.baslangic


# ============================================================================
# 6) gunluk_sinir_tablosu: bilinmeyen sinif ve tek gunluk donem
# ============================================================================


def _mumlar(bas: str, son: str) -> pd.DataFrame:
    z = pd.date_range(T(bas), T(son), freq="4h")
    return pd.DataFrame({
        "open_time": z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
        "volume": 1.0, "close_time": z + pd.Timedelta(hours=4) - pd.Timedelta(milliseconds=1),
        "quote_volume": 1.0, "count": 1, "taker_buy_volume": 0.0, "taker_buy_quote_volume": 0.0,
    })


def test_gunluk_sinir_tablosu_delistte_olmayan_sembol_veri_sonu_sayilir():
    """SALDIRI: delist tablosunda hic gecmeyen (sinif.get None donen) bir sembol
    coktu ya da yanlislikla SETTLING/exchangeInfo_disi sayilmamali; veri sonu
    bariyla bitiyorsa 'veri_sonu' turune dusmeli."""
    from data import klines as klines_modulu

    m = _mumlar("2025-04-01 00:00", "2025-04-14 20:00")
    donem = Donem(T("2025-04-01 00:00"), T("2025-04-14 20:00"), 84, 84)
    detay = {"sembol": "BILINMEYENUSDT", "_donemler": [donem], "_mumlar": m,
             "_gunluk": klines_modulu.gunluge_cevir(m)}
    delist_bos = pd.DataFrame(columns=["sembol", "sinif"])
    tablo = calistir.gunluk_sinir_tablosu([detay], delist_bos)
    assert len(tablo) == 1
    assert tablo.iloc[0]["son_turu"] == "veri_sonu"


def test_gunluk_sinir_tablosu_tek_gunluk_donem_ayni_gunde_baslar_biter():
    """SALDIRI (uc durum): donemin basi ve sonu AYNI UTC gununde ise
    `bas_gunu == bitis_gunu` olmali ve fonksiyon cokmemeli (tek elemanli
    kesisen dizi, ilk_gun == son_gun)."""
    from data import klines as klines_modulu

    m = _mumlar("2025-04-01 00:00", "2025-04-01 20:00")
    donem = Donem(T("2025-04-01 00:00"), T("2025-04-01 20:00"), 6, 6)
    detay = {"sembol": "TEKGUNUSDT", "_donemler": [donem], "_mumlar": m,
             "_gunluk": klines_modulu.gunluge_cevir(m)}
    delist_bos = pd.DataFrame(columns=["sembol", "sinif"])
    tablo = calistir.gunluk_sinir_tablosu([detay], delist_bos)
    assert len(tablo) == 1
    satir = tablo.iloc[0]
    assert satir["bas_gunu"] == satir["bitis_gunu"] == T("2025-04-01 00:00")
    assert satir["ilk_gun"] == satir["son_gun"] == T("2025-04-01 00:00")


def _bos_evren_ve_bolme():
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
    return evren0, bolme0


def _bos_skelet_tablolar():
    """`test_rapor_sayilari_bos_ama_semali_tablolarla_cokmez` ile AYNI, kanitlanmis
    bos-ama-semali iskelet (calistir.py uretici fonksiyonlarindan, detaylar=[]);
    tekrar kullanilarak `gunluk_sinirlar` disindaki her sey guvenli tutulur."""
    detaylar: list[dict] = []
    evren0, _ = _bos_evren_ve_bolme()
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
        "delist_siniflandirmasi": pd.DataFrame(columns=["sembol", "sinif", "sonraki_dolgu_bar",
                                                         "teslim_son_bar_icinde", "teslim_eksi_bitis_saat",
                                                         "son_donem_bitis"]),
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
    tablolar["delist_siniflandirmasi"].attrs["durum_sayimi"] = {}
    return tablolar


_GS_SATIR_TABAN = {
    "sembol": "TEKGUNUSDT", "donem_sira": 0,
    "donem_baslangic": T("2025-04-01 00:00"), "donem_bitis": T("2025-04-01 20:00"),
    "bas_turu": "donem_basi", "son_turu": "veri_sonu",
    "bas_gunu": T("2025-04-01 00:00"), "bas_gunu_1d_serisinde": True,
    "bas_gunu_donem_ici_bar": 6, "bas_gunu_donem_disi_bar": 0,
    "bitis_gunu": T("2025-04-01 00:00"), "bitis_gunu_1d_serisinde": True,
    "bitis_gunu_donem_ici_bar": 6, "bitis_gunu_donem_disi_bar": 0,
    "ilk_gun": T("2025-04-01 00:00"), "ilk_gun_donem_disi_bar": 0,
    "son_gun": T("2025-04-01 00:00"), "son_gun_donem_disi_bar": 0,
}


def test_rapor_sayilari_tek_gunluk_donem_bir_kez_sayilir():
    """SALDIRI (uc durum): `bas_gunu == bitis_gunu` olan (tek gunluk) BIR donem
    satiri, rapor_sayilari'nin 'ayni_gunde_baslayan_ve_biten_donem' kaleminde
    TAM BIR kez sayilmali; cift sayilmamali ya da 0 kalmamali. Iki normal
    (farkli gunlerde baslayip biten) donem satiri bu kalemi ARTIRMAMALI."""
    tek_gunluk = dict(_GS_SATIR_TABAN)
    normal = dict(_GS_SATIR_TABAN, sembol="NORMALUSDT",
                  bitis_gunu=T("2025-04-05 00:00"), son_gun=T("2025-04-05 00:00"))
    gs = pd.DataFrame([tek_gunluk, normal], columns=calistir.GUNLUK_SINIR_SUTUNLARI)

    tablolar = _bos_skelet_tablolar()
    tablolar["gunluk_sinirlar"] = gs
    evren0, bolme0 = _bos_evren_ve_bolme()

    rapor = calistir.rapor_sayilari(tablolar, evren0, bolme0).set_index(["bolum", "kalem"])["deger"]
    assert rapor.loc[("14.8", "ayni_gunde_baslayan_ve_biten_donem")] == 1
