"""Tur E saldirilari: bu turda degisen kod uzerine (git 4eefa5b..HEAD).

Hedefler:
  - `analysis/00_veri_denetimi/calistir.py`: `kosu_kilidi` (esizamanli kosu kilidi).
  - `analysis/00_veri_denetimi/a1_olcumu.py`: `d_kurali_olc`'un yeni
    `funding_var_mevcut` / `funding_var_d` sutunlari (D-A2 penceresi).
  - `data/universe.py`: `delist_sinifi`'nin UTC zorlamasi.
  - `analysis/00_veri_denetimi/karsilastir.py`: `--ad` secenegi (kendini
    karsilastirmama korumasi).

Yalnizca `tests/` altina yazilir; aga cikmaz (tests/conftest.py `ag_kapali`).
Gercek `analysis/00_veri_denetimi/` dizinine kilit/CSV yazmaz, `tmp_path` kullanir.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

import config  # noqa: E402
from data import universe as universe_modulu  # noqa: E402
from data import funding as funding_modulu  # noqa: E402
from data import pencere as pencere_modulu  # noqa: E402
from data.donem import Donem  # noqa: E402

DIZIN = config.ANALIZ_DIZINI / "00_veri_denetimi"


def _yukle(dosya: str, ad: str):
    """analysis/00_veri_denetimi/<dosya>.py'yi paket olmadan, benzersiz bir modul
    adiyla yukler (diger test dosyalariyla ayni isim cakismasin diye)."""
    yol = DIZIN / dosya
    spec = importlib.util.spec_from_file_location(ad, yol)
    modul = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(DIZIN))
    spec.loader.exec_module(modul)
    return modul


cal = _yukle("calistir.py", "_turE_calistir")
a1 = _yukle("a1_olcumu.py", "_turE_a1_olcumu")
k = _yukle("karsilastir.py", "_turE_karsilastir")


# ==============================================================================
# kosu_kilidi (calistir.py) — esizamanli kosu kilidi
# ==============================================================================


def test_kilit_ikinci_kosu_reddedilir_ve_birincinin_kilidi_silinmez(tmp_path):
    """Ikinci kosu, calisan birinci kosunun kilit dosyasini SILMEDEN reddedilmeli.
    Aksi halde 'iki kosu ayni cikti dosyalarina yazar' korumasi delinir: reddedilen
    kosu, calisan kosunun kilidini kaldirip ucuncu bir kosunun da baslamasina izin
    verebilir (docstring'in vaat ettigi guvence budur)."""
    with cal.kosu_kilidi("paylasilan", tmp_path) as yol1:
        assert yol1.exists()
        with pytest.raises(cal.KosuKilidiHatasi):
            with cal.kosu_kilidi("paylasilan", tmp_path):
                pass  # buraya hic girilmemeli
        # Ikinci (reddedilen) kosunun finally'si BIRINCININ kilidini silmemis olmali.
        assert yol1.exists()
    assert not yol1.exists()


def test_kilit_govde_hata_firlatirsa_da_birakilir(tmp_path):
    """CLAUDE.md §5: kosu hata ile bitse de kilit dosyasi geride kalmamali,
    yoksa bir sonraki gercek kosu 'zaten calisiyor' sanip hicbir sey yazmadan durur."""
    yol = tmp_path / ".deneme.kilit"

    class OzelHata(Exception):
        pass

    with pytest.raises(OzelHata):
        with cal.kosu_kilidi("deneme", tmp_path):
            assert yol.exists()
            raise OzelHata("govde hatasi")
    assert not yol.exists()


def test_kilit_sistem_cikisinda_da_birakilir(tmp_path):
    """SystemExit (argparse hatasi, sys.exit) BaseException'dir; `except Exception`
    ile yakalanan bir finally degil, cikis GENEL finally blogundan gecmeli."""
    yol = tmp_path / ".cikis.kilit"
    with pytest.raises(SystemExit):
        with cal.kosu_kilidi("cikis", tmp_path):
            assert yol.exists()
            raise SystemExit(2)
    assert not yol.exists()


def test_kilit_serbest_kaldiktan_sonra_yeniden_alinabilir(tmp_path):
    """Normal bitince kilit kalkmali; ayni ad/dizin ile ikinci (ardisik, esizamanli
    olmayan) kosu patlamamali."""
    with cal.kosu_kilidi("tekrar", tmp_path):
        pass
    with cal.kosu_kilidi("tekrar", tmp_path):
        pass


def test_kilit_farkli_ad_ayni_dizinde_cakismaz(tmp_path):
    """Iki farkli betigin (`calistir`, `a1_olcumu`) kilitleri ayni cikti dizininde
    birbirini engellememeli: dosya adi `ad`ye gore ayrisir."""
    with cal.kosu_kilidi("calistir", tmp_path):
        with cal.kosu_kilidi("a1_olcumu", tmp_path):
            pass  # ikisi de acik olabilmeli


def test_kilit_sahibi_okunamazsa_okunamadi_yazilir(tmp_path, monkeypatch):
    """Kilit dosyasi varken icerigi okunamazsa (izin hatasi vb.) hata mesaji
    'okunamadi' demeli, coker ya da yanlis sahip bilgisi vermemeli."""
    yol = tmp_path / ".x.kilit"
    yol.write_text("pid=999 baslangic_utc=2020-01-01 00:00:00\n", encoding="utf-8")

    def patlar(self, *a, **k):
        raise OSError("erisim reddedildi")

    monkeypatch.setattr(Path, "read_text", patlar)
    with pytest.raises(cal.KosuKilidiHatasi, match="okunamadi"):
        with cal.kosu_kilidi("x", tmp_path):
            pass


def test_kilit_ikinci_kosu_hicbir_dosya_yazmadan_reddedilir(tmp_path):
    """`onay=True` olmadan C1/C2'ye erisim gibi: reddedilen kosu, kilitten baska
    HICBIR dosyaya dokunmamali. Burada 'dokunmama'yi, kilit disinda dizinde baska
    dosya olusmadigini dogrulayarak sinariz."""
    with cal.kosu_kilidi("saf", tmp_path):
        with pytest.raises(cal.KosuKilidiHatasi):
            with cal.kosu_kilidi("saf", tmp_path):
                pass
        dosyalar = sorted(p.name for p in tmp_path.iterdir())
        assert dosyalar == [".saf.kilit"]


# ==============================================================================
# delist_sinifi (data/universe.py) — UTC zorlamasi
# ==============================================================================


def _anlik_bos() -> pd.DataFrame:
    return pd.DataFrame(columns=["symbol", "status", "deliveryDate"])


def _evren_tek_sembol(donem_bitis) -> pd.DataFrame:
    return pd.DataFrame([
        {"sembol": "XUSDT", "haric": False, "donem_id": 0, "donem_bitis": donem_bitis},
    ])


def test_delist_sinifi_tum_nat_sutun_tz_aware_kalir_ve_karsilastirma_patlamaz():
    """Butun semboller exchangeInfo disi olursa (anlik bombos) deliveryDate sutunu
    tamami NaT olur. Bu sutun tz-naive/object'e duserse asagi akista
    (`deliveryDate <= son_donem_bitis` gibi) TypeError firlar; bu kural rev.7'de
    karantina/sinir hesaplarina SETTLED bilgisinin sizmasini engelleyen kontrolun
    ta kendisidir."""
    evren = _evren_tek_sembol(pd.Timestamp("2024-06-01", tz="UTC"))
    tablo = universe_modulu.delist_sinifi(evren, _anlik_bos())
    assert tablo.loc[0, "sinif"] == "exchangeInfo_disi"
    assert pd.isna(tablo.loc[0, "deliveryDate"])
    assert isinstance(tablo["deliveryDate"].dtype, pd.DatetimeTZDtype)
    # delist_tablosu'nun yaptigi karsilastirmayi aynen tekrarla: patlamamali.
    sinir = (tablo["son_donem_bitis"] <= tablo["deliveryDate"]) & (
        tablo["deliveryDate"] < tablo["son_donem_bitis"] + pd.Timedelta(hours=4)
    )
    assert bool(sinir.iloc[0]) is False


def test_delist_sinifi_naif_zaman_damgasi_sessizce_kaymaz():
    """`donem_bitis` yanlislikla saat dilimsiz (naive) gelirse, UTC'ye zorlama onu
    baska bir dilimmis gibi KAYDIRMAMALI; ayni duvar-saati UTC olarak damgalanmali
    (on-kayit'ta 'tum zaman damgalari UTC' varsayimi, CLAUDE.md §5)."""
    naif = pd.Timestamp("2024-06-01 12:00:00")  # tz yok
    assert naif.tzinfo is None
    evren = _evren_tek_sembol(naif)
    tablo = universe_modulu.delist_sinifi(evren, _anlik_bos())
    sonuc = tablo.loc[0, "son_donem_bitis"]
    assert sonuc == pd.Timestamp("2024-06-01 12:00:00", tz="UTC")
    assert sonuc.hour == 12  # kaymamis: saat degismeden UTC etiketlenmis


def test_delist_sinifi_deliverydate_ve_nat_karisimi_tz_tutarli():
    """Bir kismi SETTLING (deliveryDate dolu, tz-aware), bir kismi exchangeInfo_disi
    (deliveryDate NaT) olan karma bir tabloda sutun tek bir tz-aware tipte kalmali;
    aksi halde `groupby`/karsilastirma sessizce yanlis sonuc uretebilir."""
    evren = pd.DataFrame([
        {"sembol": "AUSDT", "haric": False, "donem_id": 0,
         "donem_bitis": pd.Timestamp("2024-01-01", tz="UTC")},
        {"sembol": "BUSDT", "haric": False, "donem_id": 0,
         "donem_bitis": pd.Timestamp("2024-02-01", tz="UTC")},
    ])
    anlik = pd.DataFrame([
        {"symbol": "AUSDT", "status": "SETTLING",
         "deliveryDate": pd.Timestamp("2024-01-01 04:00", tz="UTC")},
    ])
    tablo = universe_modulu.delist_sinifi(evren, anlik)
    assert isinstance(tablo["deliveryDate"].dtype, pd.DatetimeTZDtype)
    a = tablo.set_index("sembol")
    assert a.loc["AUSDT", "sinif"] == "SETTLING"
    assert a.loc["BUSDT", "sinif"] == "exchangeInfo_disi"
    assert pd.isna(a.loc["BUSDT", "deliveryDate"])


# ==============================================================================
# a1_olcumu.d_kurali_olc — funding_var_mevcut / funding_var_d (D-A2)
# ==============================================================================

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
TOL = funding_modulu.ODEME_TOLERANSI
ADIM = pencere_modulu.adim(config.BAR_4H)
DONEM_E = Donem(T("2025-04-01 00:00"), T("2025-04-14 08:00"), 80, 80)


def _tek_kayit(z, aralik=4):
    return pd.DataFrame({
        "odeme_zamani": pd.DatetimeIndex([z]),
        "aralik_saat": [aralik],
        "oran": [0.0],
        "oran_8h": [0.0],
    })


@pytest.mark.parametrize("z,beklenen", [
    # rev.8 §4 "Zaman toleransi": tam 1 dakika ayni an degildir; alt sinir artik HARIC
    # (rev.7'de dahildi; beklenti True -> False, RESULTS degisiklik kaydi).
    (DONEM_E.baslangic - TOL, False),
    (DONEM_E.baslangic - TOL - pd.Timedelta(seconds=1), False),  # alt sinirin disi
    (DONEM_E.bitis + TOL, False),                            # ust sinir HARIC
    (DONEM_E.bitis + TOL - pd.Timedelta(milliseconds=1), True),  # ust sinirdan hemen once
])
def test_funding_var_d_penceresi_uclari(z, beklenen):
    """`funding_var_d`: `[baslangic - 1 dk, bitis + 1 dk)`. Alt uc dahil, ust uc
    haric olmali (docstring'in ve D kuralinin tanimladigi gibi)."""
    fund = _tek_kayit(z)
    satir = a1.d_kurali_olc("XUSDT", [DONEM_E], ["delist_SETTLING"], fund, config.BAR_4H)[0]
    assert satir["funding_var_d"] is beklenen


def test_funding_var_mevcut_pencere_var_d_penceresinden_genistir():
    """`funding_var_mevcut` ust siniri `bitis + 4h + 1 dk`dir (mevcut kural),
    `funding_var_d` ust siniri `bitis + 1 dk`dir (D kurali). Son bar KAPANISINA
    yakin (ama acilisindan uzak) bir kayit mevcut kuralda donemi funding'li
    sayarken D kuralinda funding'siz saymali; ikisi ayni sonucu verirse D-A2
    ayrimi koda gecmemis demektir."""
    # Rev.8 §2 "Funding'i bulunmayan donemler": veri katmani (mevcut) da artik [bas, B]
    # penceresini kullanir; iki sutun ayni sonucu verir (RESULTS degisiklik kaydi).
    z = DONEM_E.bitis + pd.Timedelta(hours=2)  # [bitis+TOL, bitis+ADIM+TOL) icinde
    assert DONEM_E.bitis + TOL <= z < DONEM_E.bitis + ADIM + TOL
    fund = _tek_kayit(z)
    satir = a1.d_kurali_olc("XUSDT", [DONEM_E], ["delist_SETTLING"], fund, config.BAR_4H)[0]
    assert satir["funding_var_mevcut"] is False  # rev.7'de True
    assert satir["funding_var_d"] is False


def test_funding_var_d_ic_donemde_diger_donemin_kaydini_saymaz():
    """Iki donemli bir sembolde, ilk donemin sonu ile ikinci donemin basi arasindaki
    (dolgu/bosluk suresindeki) bir kayit HICBIR donemin `funding_var_d`sine
    girmemeli; ne oncekinin ne sonrakinin penceresine dahil edilmemeli."""
    d0 = Donem(T("2025-01-01 00:00"), T("2025-01-10 00:00"), 60, 60)
    d1 = Donem(T("2025-02-10 00:00"), T("2025-02-20 00:00"), 60, 60)
    ara_kayit = T("2025-01-20 00:00")  # iki donem arasinda, her ikisinden de uzak
    fund = _tek_kayit(ara_kayit)
    satirlar = a1.d_kurali_olc("XUSDT", [d0, d1], ["dolgu_kosusu", "delist_SETTLING"], fund, config.BAR_4H)
    assert satirlar[0]["funding_var_d"] is False
    assert satirlar[1]["funding_var_d"] is False


# ==============================================================================
# karsilastir.py — --ad secenegi (kendini karsilastirmama korumasi)
# ==============================================================================


def test_ad_karsilastirma_ile_baslamiyorsa_reddedilir():
    """--ad, 'karsilastirma' ile baslamiyorsa argparse hatasiyla (SystemExit)
    durmali; aksi halde rastgele adli bir CSV `karsilastirma*` korumasini atlatip
    sonraki bir kosuda kendi kendisiyle karsilastirilabilir."""
    with pytest.raises(SystemExit):
        k.main(["--onceki", "deadbeef", "--ad", "baska_ad"])


def test_ad_ile_uretilen_karsilastirma_dosyasi_kendini_karsilastirmaz(tmp_path, monkeypatch):
    """Onceki bir `--ad karsilastirma_X` kosusunun ciktisi diskte dururken yeni bir
    kosu calisirsa, o eski karsilastirma ciktisi yeni kosunun karsilastirdigi
    dosyalar listesine (`dosya` sutunu) GIRMEMELI (karsilastirma ciktilari
    karsilastirilmaz, docstring)."""
    monkeypatch.setattr(k, "KOK", tmp_path)
    monkeypatch.setattr(k, "BU_DIZIN", tmp_path)
    monkeypatch.setattr(k, "_git_listesi", lambda ref, dizin: ["karsilastirma_eski_tam.csv"])
    monkeypatch.setattr(k, "_git_dosyasi", lambda ref, yol: None)

    (tmp_path / "sembol_ozeti_tam.csv").write_text("a\n1\n", encoding="utf-8")
    (tmp_path / "karsilastirma_eski_tam.csv").write_text("dosya\nx\n", encoding="utf-8")

    k.main(["--onceki", "deadbeef", "--ad", "karsilastirma_yeni"])

    cikti = tmp_path / "karsilastirma_yeni_tam.csv"
    assert cikti.exists()
    sonuc = pd.read_csv(cikti, dtype=str, keep_default_na=False)
    assert "karsilastirma_eski_tam.csv" not in set(sonuc["dosya"])
    assert set(sonuc["dosya"]) == {"sembol_ozeti_tam.csv"}


def test_varsayilan_ad_ile_onceki_kosunun_karsilastirma_ciktisi_yeniden_islenmez(tmp_path, monkeypatch):
    """Varsayilan `--ad` (`karsilastirma`) ile onceki kosunun kendi ciktisi
    (`karsilastirma_tam.csv`) diskte kalmis olsa bile yeni kosunun girdi listesine
    dahil edilmemeli (kendi kendine referans dongusu olusmamali)."""
    monkeypatch.setattr(k, "KOK", tmp_path)
    monkeypatch.setattr(k, "BU_DIZIN", tmp_path)
    monkeypatch.setattr(k, "_git_listesi", lambda ref, dizin: [])
    monkeypatch.setattr(k, "_git_dosyasi", lambda ref, yol: None)

    (tmp_path / "karsilastirma_tam.csv").write_text("dosya\nonceki\n", encoding="utf-8")
    (tmp_path / "dolgu_kosulari_tam.csv").write_text("a\n1\n", encoding="utf-8")

    k.main(["--onceki", "deadbeef"])

    sonuc = pd.read_csv(tmp_path / "karsilastirma_tam.csv", dtype=str, keep_default_na=False)
    assert "karsilastirma_tam.csv" not in set(sonuc["dosya"])
    assert set(sonuc["dosya"]) == {"dolgu_kosulari_tam.csv"}
