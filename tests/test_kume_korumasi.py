"""Yukleyicilerde kume korumasi (CLAUDE.md §3.2-3.3, denetci bulgulari B5, 8, 9).

`klines.mumlari_yukle`, `klines.birincil_gunluk_indir` ve `funding.funding_yukle`,
`split.yukle` ile ayni kapidan gecer: kume zorunlu; C1/C2 icin onay=True VE acik
bir onay kosusu sart; onaysiz ya da kosusuz cagri kayda yazmadan reddedilir; kayit
kosu basina tek satirdir; yanlis grup bos doner; veri kume araligina kesilir;
bolme tablosu disaridan verilemez. Korumasiz `ham_*` yukleyiciler yalnizca veri
katmani ve F1 kapsama denetimi icindir.
"""

from __future__ import annotations

import inspect

import pandas as pd

from tests.donem_yardimcisi import tum_seri_donemi
import pytest

import config
from data import funding, klines, split, universe
from tarama_yardimcisi import ihlaller


@pytest.fixture
def tablo(tmp_path, monkeypatch):
    """Gecici, kurala uygun bir split.csv: AAUSDT -> A, BBUSDT -> B."""
    cerceve = split.split_uret(["AAUSDT", "BBUSDT"])
    assert dict(zip(cerceve["sembol"], cerceve["grup"])) == {"AAUSDT": "A", "BBUSDT": "B"}
    yol = tmp_path / "split.csv"
    split.split_yaz(cerceve, yol)
    monkeypatch.setattr(config, "SPLIT_CSV", yol)
    # funding_yukle donem sonrasi kayitlari commit edilmis evrene gore atar
    # (on-kayit §2 rev.7); sahte ham verinin tamamini kapsayan tek donemli evren.
    zaman = pd.date_range("2025-08-25", "2025-09-10", freq="4h", tz="UTC")
    satirlar = []
    for sembol in ("AAUSDT", "BBUSDT"):
        ortak = {
            "sembol": sembol, "ilk_ay": "2025-08", "son_ay": "2025-09", "dosya_sayisi_4h": 2,
            "funding_dosya_sayisi": 2, "sozlesme_tipi": "PERPETUAL", "dayanak_tipi": "COIN",
            "settled_aylari": "", "haric": False, "haric_gerekce": "",
        }
        satirlar += universe.sembol_satirlari(ortak, zaman, [1.0] * len(zaman), pd.DataFrame({"odeme_zamani": zaman}))
    evren_yolu = universe.evren_csv_yaz(pd.DataFrame(satirlar), tmp_path / "universe.csv")
    monkeypatch.setattr(config, "UNIVERSE_CSV", evren_yolu)
    return cerceve


@pytest.fixture
def kayit(tmp_path, monkeypatch):
    yol = tmp_path / "ONAY_KAYDI.md"
    yol.write_text("bas\n", encoding="utf-8")
    monkeypatch.setattr(config, "ONAY_KAYDI", yol)
    return yol


@pytest.fixture
def sahte_ham(monkeypatch):
    """KESIF/C2 sinirini kapsayan sahte ham veri; ag kullanilmaz."""

    def mumlar(sembol, bar=config.BAR_4H, yenile=False):
        zaman = pd.date_range("2025-08-25", "2025-09-10", freq="4h", tz="UTC")
        cerceve = pd.DataFrame(
            {
                "open_time": zaman, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
                "volume": 1.0, "close_time": zaman, "quote_volume": 1.0, "count": 1,
                "taker_buy_volume": 1.0, "taker_buy_quote_volume": 1.0,
            }
        )
        return klines.gunluge_cevir(cerceve, donemler=tum_seri_donemi(cerceve)) if bar == config.BAR_1D else cerceve

    def fund(sembol, yenile=False):
        zaman = pd.date_range("2025-08-25", "2025-09-10", freq="8h", tz="UTC")
        return pd.DataFrame({"odeme_zamani": zaman, "aralik_saat": 8, "oran": 1e-4, "oran_8h": 1e-4})

    monkeypatch.setattr(klines, "ham_mumlari_yukle", mumlar)
    monkeypatch.setattr(funding, "ham_funding_yukle", fund)

    def birincil(sembol, yenile=False):
        return mumlar(sembol, config.BAR_1D)

    monkeypatch.setattr(klines, "ham_birincil_gunluk_indir", birincil)


YUKLEYICILER = {
    "mum": lambda s, k, **o: klines.mumlari_yukle(s, config.BAR_4H, k, **o),
    "funding": lambda s, k, **o: funding.funding_yukle(s, k, **o),
    "birincil_1d": lambda s, k, **o: klines.birincil_gunluk_indir(s, k, **o),
}


# --- Kume zorunlu ------------------------------------------------------------


@pytest.mark.parametrize(
    "fonksiyon", [klines.mumlari_yukle, funding.funding_yukle, klines.birincil_gunluk_indir]
)
def test_kume_parametresinin_varsayilani_yok(fonksiyon):
    assert inspect.signature(fonksiyon).parameters["kume"].default is inspect.Parameter.empty


def test_kumesiz_cagri_hata_verir():
    with pytest.raises(TypeError):
        klines.mumlari_yukle("AAUSDT", config.BAR_4H)
    with pytest.raises(TypeError):
        funding.funding_yukle("AAUSDT")
    with pytest.raises(TypeError):
        klines.birincil_gunluk_indir("AAUSDT")


@pytest.mark.parametrize("yukleyici", YUKLEYICILER.values(), ids=YUKLEYICILER.keys())
def test_bilinmeyen_kume_reddedilir(yukleyici, tablo):
    with pytest.raises(ValueError):
        yukleyici("AAUSDT", "C3")


def test_split_disindaki_sembol_reddedilir(tablo, sahte_ham):
    with pytest.raises(KeyError):
        funding.funding_yukle("ZZUSDT", "KESIF")


# --- KESIF: grup ve aralik ---------------------------------------------------


def test_mum_kesif_a_grubu_kume_araligina_kesilir(tablo, sahte_ham):
    bas, son = split.kume_araligi("KESIF")
    mumlar = klines.mumlari_yukle("AAUSDT", config.BAR_4H, "KESIF")
    assert not mumlar.empty
    assert mumlar["open_time"].min() >= bas
    assert mumlar["open_time"].max() <= son
    assert (mumlar["open_time"] < pd.Timestamp("2025-09-01", tz="UTC")).all()


def test_gunluk_mum_da_kume_araligina_kesilir(tablo, sahte_ham):
    _, son = split.kume_araligi("KESIF")
    gunluk = klines.mumlari_yukle("AAUSDT", config.BAR_1D, "KESIF")
    assert not gunluk.empty
    assert gunluk["open_time"].max() <= son


def test_funding_kesif_a_grubu_kume_araligina_kesilir(tablo, sahte_ham):
    bas, son = split.kume_araligi("KESIF")
    fund = funding.funding_yukle("AAUSDT", "KESIF")
    assert not fund.empty
    assert fund["odeme_zamani"].min() >= bas
    assert fund["odeme_zamani"].max() <= son


def test_birincil_1d_kesif_a_grubu_kume_araligina_kesilir(tablo, sahte_ham):
    bas, son = split.kume_araligi("KESIF")
    gunluk = klines.birincil_gunluk_indir("AAUSDT", "KESIF")
    assert not gunluk.empty
    assert gunluk["open_time"].min() >= bas
    assert gunluk["open_time"].max() <= son


@pytest.mark.parametrize("yukleyici", YUKLEYICILER.values(), ids=YUKLEYICILER.keys())
def test_kesif_b_grubu_bos_doner(yukleyici, tablo, sahte_ham):
    assert yukleyici("BBUSDT", "KESIF").empty


def test_funding_bos_cerceve_sutunlari(tablo, sahte_ham):
    assert list(funding.funding_yukle("BBUSDT", "KESIF").columns) == funding.FUNDING_CIKTI_SUTUNLARI


# --- Onay kumeleri: kosu olmadan erisim yok ----------------------------------


@pytest.mark.parametrize("kume", ["C1", "C2"])
@pytest.mark.parametrize("yukleyici", YUKLEYICILER.values(), ids=YUKLEYICILER.keys())
def test_onaysiz_cagri_reddedilir_kayit_yazilmaz(yukleyici, kume, tablo, sahte_ham, kayit):
    with pytest.raises(PermissionError):
        yukleyici("BBUSDT", kume)
    assert kayit.read_text(encoding="utf-8") == "bas\n"


@pytest.mark.parametrize("kume", ["C1", "C2"])
@pytest.mark.parametrize("yukleyici", YUKLEYICILER.values(), ids=YUKLEYICILER.keys())
def test_onay_true_ama_kosu_yoksa_reddedilir_kayit_yazilmaz(yukleyici, kume, tablo, sahte_ham, kayit):
    with pytest.raises(PermissionError):
        yukleyici("BBUSDT", kume, onay=True)
    assert kayit.read_text(encoding="utf-8") == "bas\n"


@pytest.mark.parametrize("deger", ["False", "True", 1, 0, None, "evet"])
def test_onay_yalnizca_gercek_bool(deger, tablo, sahte_ham, kayit):
    """Bulgu 8: `onay="False"` gibi dogruluk degeri tasiyan her sey reddedilir."""
    with split.onay_kosusu("HTEST", "C1"):
        with pytest.raises(PermissionError):
            klines.mumlari_yukle("BBUSDT", config.BAR_4H, "C1", onay=deger)
    with pytest.raises(PermissionError):
        split.kume_erisimi("AAUSDT", "KESIF", onay=deger)


def test_baska_kumenin_kosusu_kapiyi_acmaz(tablo, sahte_ham, kayit):
    with split.onay_kosusu("HTEST", "C1"):
        with pytest.raises(PermissionError):
            klines.mumlari_yukle("AAUSDT", config.BAR_4H, "C2", onay=True)


def test_kosu_kapaninca_erisim_kapanir(tablo, sahte_ham, kayit):
    with split.onay_kosusu("HTEST", "C1"):
        assert not klines.mumlari_yukle("BBUSDT", config.BAR_4H, "C1", onay=True).empty
    assert split.aktif_onay_kosusu() is None
    with pytest.raises(PermissionError):
        klines.mumlari_yukle("BBUSDT", config.BAR_4H, "C1", onay=True)


def test_kosu_icinde_hata_olsa_da_kosu_kapanir(tablo, sahte_ham, kayit):
    with pytest.raises(RuntimeError, match="deneme"):
        with split.onay_kosusu("HTEST", "C1"):
            raise RuntimeError("deneme")
    assert split.aktif_onay_kosusu() is None


# --- Onay kumeleri: kosu basina tek satir, tek atis --------------------------


def test_kosu_basina_tek_satir_sembol_basina_degil(tablo, sahte_ham, kayit):
    with split.onay_kosusu("H2", "C1"):
        for yukleyici in YUKLEYICILER.values():
            for sembol in ("AAUSDT", "BBUSDT"):
                yukleyici(sembol, "C1", onay=True)

    metin = kayit.read_text(encoding="utf-8")
    satirlar = [s for s in metin.splitlines() if s.startswith("|")]
    assert len(satirlar) == 1
    assert "| C1 |" in satirlar[0] and "hipotez=H2" in satirlar[0]
    assert "AAUSDT" not in metin and "BBUSDT" not in metin
    assert split.kayittaki_kosular(metin) == {("H2", "C1")}


def test_satirda_commit_ve_calisma_agaci_durumu_var(tablo, kayit, monkeypatch):
    monkeypatch.setattr(split, "_git_commit", lambda: "0123456789abcdef")
    monkeypatch.setattr(split, "_calisma_agaci_durumu", lambda: "KIRLI")
    with split.onay_kosusu("H1", "C2"):
        pass
    satir = [s for s in kayit.read_text(encoding="utf-8").splitlines() if s.startswith("|")][0]
    hucreler = [h.strip() for h in satir.strip("|").split("|")]
    assert hucreler[1] == "C2"
    assert hucreler[3] == "0123456789ab (KIRLI)"
    assert hucreler[4] == "hipotez=H1"


def test_ayni_hipotez_ve_kume_ikinci_kez_kosulamaz(tablo, sahte_ham, kayit):
    with split.onay_kosusu("H2", "C1"):
        pass
    once = kayit.read_bytes()
    with pytest.raises(split.OnayTekrari):
        with split.onay_kosusu("H2", "C1"):
            pytest.fail("ikinci kosu blogu calismamali")
    assert kayit.read_bytes() == once
    assert split.aktif_onay_kosusu() is None

    # Ayni hipotezin diger kumesi ve baska hipotezin ayni kumesi kosulabilir.
    with split.onay_kosusu("H2", "C2"):
        pass
    with split.onay_kosusu("H3", "C1"):
        pass
    assert split.kayittaki_kosular(kayit.read_text(encoding="utf-8")) == {("H2", "C1"), ("H2", "C2"), ("H3", "C1")}


def test_ic_ice_kosu_acilamaz(tablo, kayit):
    with split.onay_kosusu("H1", "C1"):
        with pytest.raises(RuntimeError):
            with split.onay_kosusu("H1", "C2"):
                pass


@pytest.mark.parametrize(("hipotez", "kume"), [("H1", "KESIF"), ("", "C1"), ("H 1", "C1"), ("H1|x", "C1"), (None, "C1")])
def test_gecersiz_kosu_reddedilir(hipotez, kume, tablo, kayit):
    with pytest.raises(ValueError):
        with split.onay_kosusu(hipotez, kume):
            pass
    assert kayit.read_text(encoding="utf-8") == "bas\n"


def test_c2_donemi_c2_araligina_kesilir(tablo, sahte_ham, kayit):
    bas, _ = split.kume_araligi("C2")
    with split.onay_kosusu("HTEST", "C2"):
        mumlar = klines.mumlari_yukle("AAUSDT", config.BAR_4H, "C2", onay=True)
        fund = funding.funding_yukle("BBUSDT", "C2", onay=True)
    assert mumlar["open_time"].min() >= bas
    assert not fund.empty and fund["odeme_zamani"].min() >= bas


# --- Bolme tablosu disaridan verilemez ---------------------------------------


@pytest.mark.parametrize(
    "fonksiyon",
    [split.kume_erisimi, split.yukle, klines.mumlari_yukle, funding.funding_yukle, klines.birincil_gunluk_indir],
)
def test_yukleyicilere_split_tablosu_verilemez(fonksiyon):
    """Bulgu 9: `split=` parametresi kaldirildi; tablo yalnizca split_oku ile gelir."""
    assert "split" not in inspect.signature(fonksiyon).parameters


def test_kurala_uymayan_split_csv_kapida_reddedilir(tmp_path, monkeypatch, sahte_ham):
    """Betikle degistirilmis bir split.csv (B grubu sembol A isaretli) kullanilamaz."""
    yol = tmp_path / "split.csv"
    yol.write_text("sembol,varlik_anahtari,grup\nAAUSDT,AAUSDT,A\nBBUSDT,BBUSDT,A\n", encoding="utf-8")
    monkeypatch.setattr(config, "SPLIT_CSV", yol)
    with pytest.raises(split.BolmeTutarsizligi):
        klines.mumlari_yukle("BBUSDT", config.BAR_4H, "KESIF")


# --- Ham yukleyici disiplini -------------------------------------------------


def test_analiz_kodu_ham_yukleyici_cagirmaz():
    """Korumasiz ham yukleyiciler yalnizca data/ ve F1 kapsama denetiminde kullanilir.

    events/, study/ ve diger analizler (F2 ve sonrasi) bunlari cagirirsa kume
    korumasi sessizce atlanir; bu test onu yakalar.
    """
    assert ihlaller(r"\bham_(mumlari_yukle|funding_yukle|birincil_gunluk_indir)\b") == []
