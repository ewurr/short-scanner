"""Bu tur saldiri testleri (commit 5542748..d9e8266):

1. `data/donem.py` `ay_toplam_donemde`: sifir dolgusuz aylar, gecersiz ay
   ifadeleri, sinir aylari (on-kayit §2, D-B... "sizinti testcisi bulgusu"
   yorumu, donem.py docstring).
2. `analysis/00_veri_denetimi/calistir.py` `csv_yaz`: atomik yazma
   (denetci bulgusu D-C3).
3. `analysis/00_veri_denetimi/a1_olcumu.py`: `donem_sonu_cikisi`,
   `d_kurali_olc` sinir durumlari (D kurali olcumu, on-kayit revizyonu bekliyor).
4. `a1_olcumu.main([])` bos evrende cokmemeli.
5. `a1_olcumu` deger yolu: main([]) `oran`/`oran_8h` sutunu hic olmayan bir
   funding cercevesiyle de uctan uca calismali (D-B1).

Hicbir test aga cikmaz (tests/conftest.py `ag_kapali`). Mevcut test dosyalarina
dokunulmadi; bu tamamen yeni bir dosyadir.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import config
from data import donem as donem_modulu
from data import funding as funding_modulu
from data import pencere as pencere_modulu
from data import universe as universe_modulu
from data.donem import Donem

KOK = Path(__file__).resolve().parents[1]
_CALISTIR_YOLU = KOK / "analysis" / "00_veri_denetimi" / "calistir.py"
_A1_YOLU = KOK / "analysis" / "00_veri_denetimi" / "a1_olcumu.py"

pytestmark = pytest.mark.skipif(
    not (_CALISTIR_YOLU.exists() and _A1_YOLU.exists()),
    reason="analysis/00_veri_denetimi betikleri yok",
)


def _yukle(yol: Path, ad: str):
    spec = importlib.util.spec_from_file_location(ad, yol)
    modul = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modul
    spec.loader.exec_module(modul)
    return modul


if _CALISTIR_YOLU.exists():
    calistir = _yukle(_CALISTIR_YOLU, "_tur_c_calistir")
if _A1_YOLU.exists():
    a1 = _yukle(_A1_YOLU, "_tur_c_a1_olcumu")

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
DK = pd.Timedelta(minutes=1)
SN = pd.Timedelta(seconds=1)
TOL = funding_modulu.ODEME_TOLERANSI


def _fund(zamanlar, aralik=4):
    z = pd.DatetimeIndex(sorted(zamanlar))
    return pd.DataFrame({"odeme_zamani": z, "aralik_saat": aralik, "oran": 0.0, "oran_8h": 0.0})


# ---------------------------------------------------------------------------
# 1) data/donem.py: ay_toplam_donemde
# ---------------------------------------------------------------------------


def test_ay_toplam_donemde_sifir_dolgusuz_ay_dogru_kesisir():
    """'2026-8' metin siralamasinda '2026-08'den BUYUK sayilir ve donemin son
    ayini sessizce disarida birakirdi (metin karsilastirmasi). Deger uzerinden
    karsilastirma bunu yakalamali: on-kayit'in DONEM_SONU ayi (2026-08) ile
    kesismeli."""
    assert donem_modulu.ay_toplam_donemde("2026-8") is True
    assert donem_modulu.ay_toplam_donemde("2020-1") is True


@pytest.mark.parametrize("ay", ["2026-13", "abc", ""])
def test_ay_toplam_donemde_gecersiz_ay_hata_verir(ay):
    """Gecersiz ay ifadesi sessizce False donmemeli, ValueError firlatmali
    (docstring: 'Gecersiz ay ifadesi ValueError verir')."""
    with pytest.raises(ValueError):
        donem_modulu.ay_toplam_donemde(ay)


@pytest.mark.parametrize("ay,beklenen", [
    ("2019-12", False),   # DONEM_BASI'ndan bir ay once
    ("2020-01", True),    # DONEM_BASI'nin ayi
    ("2026-08", True),    # DONEM_SONU'nun ayi
    ("2026-09", False),   # DONEM_SONU'ndan bir ay sonra
])
def test_ay_toplam_donemde_sinir_aylari(ay, beklenen):
    """Toplam donem siniri AY duzeyinde tam sinirda dogru kesilmeli; bir ay
    disariya tasan istek kesismemeli."""
    assert donem_modulu.ay_toplam_donemde(ay) is beklenen


# ---------------------------------------------------------------------------
# 2) analysis/00_veri_denetimi/calistir.py: csv_yaz (atomik yazma)
# ---------------------------------------------------------------------------


def test_csv_yaz_basarili_kosudan_sonra_gecici_dosya_kalmaz(tmp_path):
    """Basarili bir yazmadan sonra `.tmp` dosyasi calisma dizininde kalmamali;
    `os.replace` hedefe tasimis olmali (denetci bulgusu D-C3)."""
    hedef = tmp_path / "cikti.csv"
    calistir.csv_yaz(pd.DataFrame({"a": [1, 2]}), hedef)
    assert hedef.exists()
    assert not (tmp_path / "cikti.csv.tmp").exists()


def test_csv_yaz_yazma_sirasinda_hata_eski_dosyayi_bozmaz(tmp_path, monkeypatch):
    """Var olan bir dosyanin uzerine yazarken `to_csv` patlarsa hedef ASLA
    yarim/bozuk kalmamali: eski icerik oldugu gibi durmali."""
    hedef = tmp_path / "cikti.csv"
    eski_icerik = "a\n1\n2\n"
    hedef.write_text(eski_icerik, encoding="utf-8")

    def patlayan_to_csv(self, yol, *a, **kw):
        # Yazma SIRASINDA (dosyayi actiktan/kismen yazdiktan sonra) patlar.
        Path(yol).write_text("YARIM-YAZILMIS-BOZUK-ICERIK", encoding="utf-8")
        raise RuntimeError("simule edilmis yazma hatasi")

    monkeypatch.setattr(pd.DataFrame, "to_csv", patlayan_to_csv)
    with pytest.raises(RuntimeError):
        calistir.csv_yaz(pd.DataFrame({"a": [9, 9, 9]}), hedef)

    # Hedef dosya ESKI icerigiyle degismeden durmali; ne bozuk ne yarim.
    assert hedef.read_text(encoding="utf-8") == eski_icerik


def test_csv_yaz_satir_sonu_crlf_sizdirmaz(tmp_path):
    """`lineterminator='\\n'` acikca verilmis; CRLF (\\r\\n) hicbir platformda
    sizmamali (rapor/tekrarlanabilirlik icin deterministik bayt duzeyi)."""
    hedef = tmp_path / "cikti.csv"
    calistir.csv_yaz(pd.DataFrame({"a": [1, 2, 3]}), hedef)
    ham = hedef.read_bytes()
    assert b"\r\n" not in ham
    assert b"\n" in ham


# ---------------------------------------------------------------------------
# 3) a1_olcumu.py: donem_sonu_cikisi sinir durumlari
# ---------------------------------------------------------------------------


def test_donem_sonu_cikisi_1d_tam_gun_basinda():
    """Donem bitisi tam gun basindaysa (00:00) taban 'floor' islemi barin
    acilisini DEGISTIRMEMELI; cikis ertesi gun 00:00 olmali."""
    donem = Donem(T("2025-04-01 00:00"), T("2025-04-14 00:00"), 80, 80)
    acilis, cikis = a1.donem_sonu_cikisi(donem, config.BAR_1D)
    assert acilis == T("2025-04-14 00:00")
    assert cikis == T("2025-04-15 00:00")


def test_donem_sonu_cikisi_1d_gun_sonunda():
    """Donem bitisi gun sonuna yakinsa (20:00) 1 gunluk izgarada barin acilisi
    yine o gunun 00:00'i olmali (gunun SONUNA degil)."""
    donem = Donem(T("2025-04-01 00:00"), T("2025-04-14 20:00"), 80, 80)
    acilis, cikis = a1.donem_sonu_cikisi(donem, config.BAR_1D)
    assert acilis == T("2025-04-14 00:00")
    assert cikis == T("2025-04-15 00:00")


def test_donem_sonu_cikisi_4h_izgarada_floor_uygulanmaz():
    """4 saatlik izgarada (H1/H2) cikis barin acilisi donem.bitis'in KENDISI
    olmali; 1 gunluk floor 4h barina sizmamali."""
    donem = Donem(T("2025-04-01 00:00"), T("2025-04-14 20:00"), 80, 80)
    acilis, cikis = a1.donem_sonu_cikisi(donem, config.BAR_4H)
    assert acilis == T("2025-04-14 20:00")
    assert cikis == T("2025-04-15 00:00")


# ---------------------------------------------------------------------------
# 3b) a1_olcumu.py: d_kurali_olc — 1 gunluk izgarada disarida_kalan siniri
# ---------------------------------------------------------------------------


DONEM_UZUN = Donem(T("2025-04-01 00:00"), T("2025-04-14 08:00"), 80, 80)


@pytest.mark.parametrize("kayma,beklenen", [
    (pd.Timedelta(0), 1),        # gun kapanisinda (cikis ani): dahil
    (59 * SN, 1),                 # 1 dk tolerans icinde: dahil
    (61 * SN, 0),                 # 1 dk tolerans disinda: harici
])
def test_1d_disarida_kalan_gun_kapanisi_siniri(kayma, beklenen):
    """1 gunluk cikis izgarasinda ust sinir tam gun kapanisi + 1 dk tolerans
    olmali; 61. saniyede kayit disariya (sinirin da disina) dusmeli.

    Kurgu degisikligi (Madde 1, denetci bulgusu D-A4): sayim artik veri
    katmaninin gordugu kayit tabanindan yapilir; bu taban son 4 saatlik barin
    kapanisindan + 1 dk sonrasini zaten atar. Bitisi 08:00 olan `DONEM_UZUN`da
    gun kapanisi (ertesi gun 00:00) o sinirin disinda kaldigi icin kayit her
    kaymada atilir ve test sinirin kendisini olcemezdi. Bitisi 20:00 olan donemde
    gun kapanisi son barin kapanisiyla ayni andir; testin olctugu tolerans siniri
    ve beklenen sayilar degismedi."""
    donem = Donem(T("2025-04-01 00:00"), T("2025-04-14 20:00"), 80, 80)
    _, cikis_ani = a1.donem_sonu_cikisi(donem, config.BAR_1D)
    fund = _fund([cikis_ani + kayma])
    satir = a1.d_kurali_olc("X", [donem], ["delist_SETTLING"], fund, config.BAR_1D)[0]
    assert satir["disarida_kalan"] == beklenen


# ---------------------------------------------------------------------------
# 3c) a1_olcumu.py: d_kurali_olc — kapanista_odeme tolerans siniri
# ---------------------------------------------------------------------------


DONEM_KISA = Donem(T("2025-04-14 04:00"), T("2025-04-14 08:00"), 2, 2)


def test_kapanista_odeme_59_saniye_icinde_true():
    """Cikis anindan 59 sn sonraki kayit hala 'kapanista odeme' sayilmali
    (1 dk toleransin ICINDE)."""
    _, cikis_ani = a1.donem_sonu_cikisi(DONEM_KISA, config.BAR_4H)
    fund = _fund([cikis_ani + 59 * SN])
    satir = a1.d_kurali_olc("X", [DONEM_KISA], ["delist_SETTLING"], fund, config.BAR_4H)[0]
    assert satir["kapanista_odeme"] is True


def test_kapanista_odeme_61_saniye_disinda_false():
    """Cikis anindan 61 sn sonraki kayit tolerans DISINA cikmali, 'kapanista
    odeme' False donmeli (sinirin siki uygulanmasi)."""
    _, cikis_ani = a1.donem_sonu_cikisi(DONEM_KISA, config.BAR_4H)
    fund = _fund([cikis_ani + 61 * SN])
    satir = a1.d_kurali_olc("X", [DONEM_KISA], ["delist_SETTLING"], fund, config.BAR_4H)[0]
    assert satir["kapanista_odeme"] is False


# ---------------------------------------------------------------------------
# 3d) a1_olcumu.py: d_kurali_olc — son_odeme_aralik_saat
# ---------------------------------------------------------------------------


def test_son_odeme_aralik_saat_kayit_yoksa_nan():
    """Hic funding kaydi yoksa 'son_odeme_aralik_saat' NaN olmali; sessizce 0
    ya da baska bir sayi UYDURULMAMALI."""
    satir = a1.d_kurali_olc("X", [DONEM_UZUN], ["delist_SETTLING"], _fund([]))[0]
    assert pd.isna(satir["son_odeme_aralik_saat"])


def test_son_odeme_aralik_saat_donem_sonrasi_kaydi_almaz():
    """Donem bitisinden SONRAKI (uzlasma sonrasi) bir kaydin araligi
    'son_odeme_aralik_saat'e sizmamali; sutun donem bitisine KADARKI son
    kaydin araligini yazmali.

    Kurgu duzeltmesi (testin olctugu sey degismedi): ilk surumde `date_range`e
    hem saat dilimli bir uc (`DONEM_UZUN.bitis`) hem `tz="UTC"` veriliyordu;
    pandas bunu TypeError ile reddettigi icin test koda hic ulasmadan
    kiriliyordu. Iki uc da saat dilimli verilir, `tz` argumani kaldirildi."""
    zamanlar = list(pd.date_range(T("2025-04-13 00:00"), DONEM_UZUN.bitis, freq="4h"))
    fund = _fund(zamanlar, aralik=4)
    # Donem sonrasi (uzlasma sonrasi) tek kayit, cok farkli bir aralikla.
    sonra = pd.DataFrame({"odeme_zamani": [DONEM_UZUN.bitis + pd.Timedelta(hours=4)],
                          "aralik_saat": [999], "oran": [0.0], "oran_8h": [0.0]})
    fund = pd.concat([fund, sonra], ignore_index=True)
    satir = a1.d_kurali_olc("X", [DONEM_UZUN], ["delist_SETTLING"], fund, config.BAR_4H)[0]
    assert satir["son_odeme_aralik_saat"] == 4.0


# ---------------------------------------------------------------------------
# 3e) a1_olcumu.py: d_kurali_olc — temsili giris donem basindan once kayamaz
# ---------------------------------------------------------------------------


def test_temsili_giris_donem_basindan_once_kayamaz():
    """TEMSILI_GIRIS_SURE (24 saat) donem sureden kisaysa temsili pozisyonun
    girisi `max(donem.baslangic, cikis_acilis - 24h)` ile donem basina
    SABITLENMELI. Donem basindan ONCEKI bir kayit (varsayimsal kirpilmamis
    giris penceresine duserdi) tamlik hesabini ETKILEMEMELI: kirpma dogru
    calisiyorsa bu kayit tamamen yok sayilir ve tamlik degismez."""
    donem = Donem(T("2025-04-13 20:00"), T("2025-04-14 00:00"), 2, 2)
    cikis_acilis, cikis_ani = a1.donem_sonu_cikisi(donem, config.BAR_4H)
    assert cikis_acilis == donem.bitis

    # Donem icini TAM kaplayan gecerli zincir (basi = donem.baslangic).
    taban_zincir = [donem.baslangic, donem.baslangic + pd.Timedelta(hours=4), cikis_ani]
    fund_taban = _fund(taban_zincir, aralik=4)
    satir_taban = a1.d_kurali_olc("X", [donem], ["delist_SETTLING"], fund_taban, config.BAR_4H)[0]
    assert satir_taban["tamlik_d"] is True

    # Ayni zincire, donem basindan 12 saat ONCE (ama kirpilmamis 24h'lik
    # pencerenin icinde kalacak sekilde), zincirle UYUMSUZ (kocaman aralikli)
    # bir "yem" kayit ekle. Giris dogru kirpilmissa bu kayit tamamen disarida
    # kalir ve sonucu DEGISTIRMEZ.
    yem = pd.DataFrame({"odeme_zamani": [donem.baslangic - pd.Timedelta(hours=12)],
                        "aralik_saat": [999], "oran": [0.0], "oran_8h": [0.0]})
    fund_yemli = pd.concat([yem, fund_taban], ignore_index=True).sort_values("odeme_zamani", ignore_index=True)
    satir_yemli = a1.d_kurali_olc("X", [donem], ["delist_SETTLING"], fund_yemli, config.BAR_4H)[0]
    assert satir_yemli["tamlik_d"] is True, (
        "donem basindan onceki bir kayit tamlik sonucunu degistirdi; "
        "temsili giris donem basina kirpilmiyor olabilir (sizinti)"
    )


# ---------------------------------------------------------------------------
# 4) a1_olcumu.main([]): bos evren coker mi?
# ---------------------------------------------------------------------------


def _bos_evren() -> pd.DataFrame:
    return pd.DataFrame({
        "sembol": pd.Series([], dtype=str),
        "haric": pd.Series([], dtype=bool),
        "donem_id": pd.Series([], dtype="int64"),
        "donem_baslangic": pd.Series([], dtype="datetime64[ns, UTC]"),
        "donem_bitis": pd.Series([], dtype="datetime64[ns, UTC]"),
        "donem_bar_sayisi": pd.Series([], dtype="int64"),
        "donem_gercek_bar_sayisi": pd.Series([], dtype="int64"),
        "donem_funding_yok": pd.Series([], dtype=bool),
        "settled_aylari": pd.Series([], dtype=str),
    })


def _bos_goruntu(yol):
    ham = json.dumps({"serverTime": 1, "symbols": []})
    yol.write_text(
        json.dumps(universe_modulu.exchange_info_anlik_goruntu(ham, pd.Timestamp("2026-09-18", tz="UTC"))),
        encoding="utf-8",
    )


def test_bos_evrende_main_cokmeden_biter_ve_veri_sonu_uretmez(tmp_path, monkeypatch):
    """Hic donemi olmayan (sentetik) bos evrende `main([])` cokmemeli ve hicbir
    donem sonu 'veri_sonu' turu ile ETIKETLENMEMELI (etiketlenecek donem yok)."""
    evren = _bos_evren()
    _bos_goruntu(tmp_path / "ei.json")
    monkeypatch.setattr(config, "EXCHANGE_INFO_ANLIK", tmp_path / "ei.json")
    monkeypatch.setattr(universe_modulu, "evren_yukle", lambda *a, **k: evren)

    def _patla(*a, **k):
        raise AssertionError("bos evrende funding/klines yuklenmemeli")

    from data import funding as f_mod
    from data import klines as k_mod
    monkeypatch.setattr(f_mod, "ham_funding_yukle", _patla)
    monkeypatch.setattr(k_mod, "ham_mumlari_yukle", _patla)
    for ad in ("CIKTI", "CIKTI_KONUM", "CIKTI_ONERI", "CIKTI_D", "CIKTI_ORTAM"):
        monkeypatch.setattr(a1, ad, tmp_path / getattr(a1, ad).name)

    a1.main([])  # cokerse test burada patlar

    d_tablo = pd.read_csv(tmp_path / a1.CIKTI_D.name)
    assert len(d_tablo) == 0
    assert "veri_sonu" not in set(d_tablo.get("tur", []))


# ---------------------------------------------------------------------------
# 5) a1_olcumu.main([]): oran/oran_8h sutunu HIC olmayan funding cercevesi
# ---------------------------------------------------------------------------


def test_oran_sutunu_olmayan_funding_ile_main_ucdan_uca_calisir(tmp_path, monkeypatch):
    """`oran`/`oran_8h` sutunlari funding cercevesinde HIC olmasa bile
    `main([])` calismali: betik bu sutunlara hicbir yolda erismemeli (D-B1).
    Erisen bir kod yolu varsa burada KeyError ile patlar."""
    sembol = "YUSDT"
    bitis = pd.Timestamp("2025-04-14 08:00", tz="UTC")
    evren = pd.DataFrame([{
        "sembol": sembol, "haric": False, "donem_id": 0,
        "donem_baslangic": pd.Timestamp("2025-04-01 00:00", tz="UTC"), "donem_bitis": bitis,
        "donem_bar_sayisi": 80, "donem_gercek_bar_sayisi": 80, "donem_funding_yok": False,
        "settled_aylari": "",
    }])
    zamanlar = pd.date_range("2025-04-12 00:00", "2025-04-14 12:00", freq="4h", tz="UTC")
    # BILEREK oran/oran_8h sutunu YOK.
    fund = pd.DataFrame({"odeme_zamani": zamanlar, "aralik_saat": 4})
    assert "oran" not in fund.columns and "oran_8h" not in fund.columns

    _bos_goruntu(tmp_path / "ei.json")
    ham_settling = json.dumps({"serverTime": 1, "symbols": [
        {"symbol": sembol, "contractType": "PERPETUAL", "underlyingType": "COIN",
         "status": "SETTLING", "deliveryDate": int(pd.Timestamp("2025-04-14 09:00", tz="UTC").timestamp() * 1000),
         "onboardDate": 1569398400000},
    ]})
    (tmp_path / "ei.json").write_text(
        json.dumps(universe_modulu.exchange_info_anlik_goruntu(ham_settling, pd.Timestamp("2026-09-18", tz="UTC"))),
        encoding="utf-8",
    )

    monkeypatch.setattr(config, "EXCHANGE_INFO_ANLIK", tmp_path / "ei.json")
    monkeypatch.setattr(universe_modulu, "evren_yukle", lambda *a, **k: evren)
    monkeypatch.setattr(universe_modulu, "dahil_semboller", lambda e: [sembol])

    from data import funding as f_mod
    from data import binance_vision as bv_mod
    monkeypatch.setattr(f_mod, "ham_funding_yukle", lambda s, yenile=False: fund.copy())
    monkeypatch.setattr(bv_mod, "tum_sembol_dizinleri", lambda: [sembol])
    for ad in ("CIKTI", "CIKTI_KONUM", "CIKTI_ONERI", "CIKTI_D", "CIKTI_ORTAM"):
        monkeypatch.setattr(a1, ad, tmp_path / getattr(a1, ad).name)

    a1.main([])  # oran sutunu olmadigi icin KeyError verirse test burada patlar

    assert (tmp_path / a1.CIKTI.name).exists()
