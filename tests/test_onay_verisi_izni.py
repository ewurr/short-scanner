"""Onay kaydi kapanisinin son turu: onbellek ve indirme yardimcilari onay verisini izin disinda okuyamaz.

Onay verisi: B grubu sembollerin her ayi ve butun sembollerin C2 donemindeki aylari (on-kayit §3). Kume kapisindan
gecen yukleyiciler, evren kurulumu ve F1 denetimi `binance_vision.onay_verisi_izni` icinde okur; analiz kodunda
kolaylik icin yazilan `bv.onbellekten_oku(...)` ya da ham yukleyici cagrisi `OnayVerisiKorumasi` verir. Onbellek
gecici dizindedir; aga cikilmaz.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

import config
from conftest import sahte_4h
from data import binance_vision as bv
from data import funding, klines, split

B_SEMBOLU = "BTCUSDT"  # gercek split.csv'de B grubu


def _a_sembolu() -> str:
    tablo = split.split_oku()
    tek = tablo.loc[(tablo["grup"] == "A") & (tablo["sembol"] == tablo["varlik_anahtari"]), "sembol"]
    return str(tek.iloc[0])


@pytest.fixture
def onbellek(tmp_path, monkeypatch):
    kok = tmp_path / "cache"
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", kok)
    return kok


def _yaz(kok, *parcalar, cerceve=None):
    yol = kok.joinpath(*parcalar)
    yol.parent.mkdir(parents=True, exist_ok=True)
    (pd.DataFrame({"a": [1]}) if cerceve is None else cerceve).to_parquet(yol, index=False)
    return yol


def test_onay_verisi_mi_saftir():
    a = _a_sembolu()
    assert split.grup(split.varlik_anahtari(a)) == "A"
    assert bv.onay_verisi_mi(a, "2025-08") is False
    assert bv.onay_verisi_mi(a, "2025-09") is True  # C2 donemi
    assert bv.onay_verisi_mi(B_SEMBOLU, "2021-01") is True  # B grubu
    assert bv.onay_verisi_mi(a, "bozuk") is True  # kapali yon


@pytest.mark.parametrize("parcalar", [
    ("klines", "{B}", "4h", "2021-01.parquet"),
    ("klines", "{A}", "4h", "2025-09.parquet"),
    ("funding", "{B}", "2021-01.parquet"),
    ("klines_birincil_1d", "{A}", "2026-01.parquet"),
    ("klines_settled", "XUSDTSETTLED", "4h", "2021-01.parquet"),
])
def test_onbellekten_oku_onay_verisini_izin_disinda_okumaz(onbellek, parcalar):
    parcalar = tuple(p.format(A=_a_sembolu(), B=B_SEMBOLU) for p in parcalar)
    yol = _yaz(onbellek, *parcalar)
    with pytest.raises(bv.OnayVerisiKorumasi):
        bv.onbellekten_oku(yol)
    with bv.onay_verisi_izni("test"):
        assert bv.onbellekten_oku(yol) is not None
    with pytest.raises(bv.OnayVerisiKorumasi):  # izin baglamdan cikinca kapanir
        bv.onbellekten_oku(yol)


def test_onbellekten_oku_kesif_verisini_ve_onbellek_disini_okur(onbellek, tmp_path):
    assert bv.onbellekten_oku(_yaz(onbellek, "klines", _a_sembolu(), "4h", "2025-08.parquet")) is not None
    assert bv.onbellekten_oku(_yaz(onbellek, "evren.parquet")) is not None  # evren onbellegi: onay verisi degil
    assert bv.onbellekten_oku(_yaz(tmp_path, "baska", "x.parquet")) is not None


def test_ham_yukleyici_onay_verisini_izin_disinda_okumaz(onbellek, monkeypatch):
    monkeypatch.setattr(bv, "mum_dosyalari",
                        lambda s, b: [f"data/futures/um/monthly/klines/{s}/{b}/{s}-{b}-2021-01.zip"])
    monkeypatch.setattr(bv, "funding_dosyalari",
                        lambda s: [f"data/futures/um/monthly/fundingRate/{s}/{s}-fundingRate-2021-01.zip"])
    _yaz(onbellek, "klines", B_SEMBOLU, "4h", "2021-01.parquet")
    _yaz(onbellek, "funding", B_SEMBOLU, "2021-01.parquet")
    with pytest.raises(bv.OnayVerisiKorumasi):
        klines.ham_mumlari_yukle(B_SEMBOLU, config.BAR_4H)
    with pytest.raises(bv.OnayVerisiKorumasi):
        funding.ham_funding_yukle(B_SEMBOLU)


def test_zip_indir_onay_verisini_izin_disinda_indirmez(monkeypatch):
    # Denetim ag isteginden once gelir; ag istegi burada sahte ve hemen AssertionError verir.
    def istek(*_a, **_k):
        raise AssertionError("aga cikamaz")

    monkeypatch.setattr(bv, "_iste", istek)
    with pytest.raises(bv.OnayVerisiKorumasi):
        bv.zip_indir(f"data/futures/um/monthly/klines/{B_SEMBOLU}/4h/{B_SEMBOLU}-4h-2021-01.zip")
    with pytest.raises(bv.OnayVerisiKorumasi):
        bv.zip_indir(f"data/futures/um/monthly/fundingRate/{_a_sembolu()}/{_a_sembolu()}-fundingRate-2025-10.zip")
    with pytest.raises(AssertionError, match="aga cikamaz"):  # KESIF verisi: denetim gecer, ag yasagi yakalar
        bv.zip_indir(f"data/futures/um/monthly/klines/{_a_sembolu()}/4h/{_a_sembolu()}-4h-2021-01.zip")


def test_kapili_yukleyici_kesifte_c2_aylarini_izinle_okuyup_keser(onbellek, monkeypatch):
    """KESIF kumesinde A sembolunun ham okumasi C2 aylarini da okur (izinle) ve kume araligina keser."""
    a = _a_sembolu()
    aylar = ["2025-08", "2025-09"]
    monkeypatch.setattr(bv, "mum_dosyalari", lambda s, b: [f"data/futures/um/monthly/klines/{s}/{b}/{s}-{b}-{ay}.zip"
                                                         for ay in aylar])
    for ay in aylar:
        _yaz(onbellek, "klines", a, "4h", f"{ay}.parquet", cerceve=sahte_4h(f"{ay}-01", 6 * 28))
    mumlar = klines.mumlari_yukle(a, config.BAR_4H, "KESIF")
    assert len(mumlar) and mumlar["open_time"].max() <= pd.Timestamp(config.KESIF_SONU)
    assert bv._IZIN["sayac"] == 0


def test_kapili_yukleyici_b_sembolunu_kesifte_okumaz(onbellek, monkeypatch):
    monkeypatch.setattr(bv, "mum_dosyalari", lambda s, b: pytest.fail("B sembolu icin listeleme bile yapilmamali"))
    assert klines.mumlari_yukle(B_SEMBOLU, config.BAR_4H, "KESIF").empty


def test_izin_neden_ister():
    with pytest.raises(ValueError):
        bv.onay_verisi_izni("  ")


# --- Iznin alt sureclere tasinmasi (denetci OK4 D-B1) -------------------------

KOK = Path(__file__).resolve().parents[1]

# Alt surecte onay verisi denetimi: izin devralinmissa gecer, devralinmamissa `OnayVerisiKorumasi` verir.
ALT_SUREC_KODU = f"""
import sys
sys.path.insert(0, r"{KOK}")
from data import binance_vision as bv
bv._onay_verisi_denetle("{B_SEMBOLU}", "2021-01", "alt surec")
print("IZIN", bv._DEVRALINAN_IZIN["var"])
"""


def _alt_surec(ortam=None):
    return subprocess.run([sys.executable, "-c", ALT_SUREC_KODU], capture_output=True, text=True,
                          env=ortam if ortam is not None else os.environ.copy())


def test_izin_baglami_ortam_degiskenini_ayarlar_ve_geri_alir():
    assert bv._IZIN_ORTAM_ADI not in os.environ
    with bv.onay_verisi_izni("test"):
        assert os.environ[bv._IZIN_ORTAM_ADI] == str(os.getpid())
        with bv.onay_verisi_izni("ic icinde"):  # ic baglam degeri bozmaz
            assert os.environ[bv._IZIN_ORTAM_ADI] == str(os.getpid())
        assert os.environ[bv._IZIN_ORTAM_ADI] == str(os.getpid())
    assert bv._IZIN_ORTAM_ADI not in os.environ


def test_izin_baglaminda_baslatilan_alt_surec_izni_devralir():
    with bv.onay_verisi_izni("test"):
        sonuc = _alt_surec()
    assert sonuc.returncode == 0, sonuc.stderr
    assert sonuc.stdout.strip() == "IZIN True"


def test_izin_disinda_baslatilan_alt_surec_onay_verisini_okumaz():
    sonuc = _alt_surec()
    assert sonuc.returncode != 0
    assert "OnayVerisiKorumasi" in sonuc.stderr


def test_bayat_ya_da_elle_ayarlanmis_ortam_degiskeni_izin_vermez():
    """Deger ust surecin pid'i degilse devralinmaz (kabukta elle ayarlanmis ya da bayat degisken)."""
    ortam = os.environ.copy()
    ortam[bv._IZIN_ORTAM_ADI] = str(os.getpid() + 7919)
    sonuc = _alt_surec(ortam)
    assert sonuc.returncode != 0
    assert "OnayVerisiKorumasi" in sonuc.stderr
    ortam[bv._IZIN_ORTAM_ADI] = "izin"  # sayi olmayan deger
    assert "OnayVerisiKorumasi" in _alt_surec(ortam).stderr


HAVUZ_KODU = f"""
import sys
sys.path.insert(0, r"{KOK}")
from concurrent.futures import ProcessPoolExecutor
from data import binance_vision as bv


def isci(_):
    \"\"\"Isci surecte (Windows'ta spawn) onay verisi okunabiliyor mu.\"\"\"
    bv._onay_verisi_denetle("{B_SEMBOLU}", "2021-01", "isci")
    return bv._DEVRALINAN_IZIN["var"]


if __name__ == "__main__":
    with bv.onay_verisi_izni("F1 veri denetimi: havuz"):
        with ProcessPoolExecutor(max_workers=2) as havuz:
            print("ISCI", list(havuz.map(isci, range(2))))
"""


def test_process_havuzu_iscileri_izni_devralir(tmp_path):
    """F1 betiklerinin deseni: izin baglami icinde acilan `ProcessPoolExecutor`. Gercek surec baslatir."""
    betik = tmp_path / "havuz_betigi.py"
    betik.write_text(HAVUZ_KODU, encoding="utf-8")
    sonuc = subprocess.run([sys.executable, str(betik)], capture_output=True, text=True, env=os.environ.copy())
    assert sonuc.returncode == 0, sonuc.stderr
    assert sonuc.stdout.strip() == "ISCI [True, True]"
