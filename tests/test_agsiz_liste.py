"""Dondurulmus S3 listesi ve agsiz kapi yolu (on-kayit §3 rev.13; RESULTS §14.40).

Sentetik parquet dosyalari gecici onbellekte kurulur; gercek onbellek ve ag kullanilmaz (`ag` isaretli
test haric). Karar sonuclari okunmaz: testler yalnizca agin kullanilip kullanilmadigina bakar.
"""

from __future__ import annotations

import json
import socket

import pandas as pd
import pytest

import config
from conftest import sahte_4h
from data import binance_vision as bv
from data import funding as funding_modulu
from data import klines, pencere, pozisyon, sinyal, split

A_SEMBOL = "SOLUSDT"
AYLAR = ("2021-01", "2021-02", "2021-03")


def _b_sembolu() -> str:
    tablo = split.split_oku()
    return str(tablo.loc[tablo["grup"] == "B", "sembol"].iloc[0])


def _mum_anahtari(s, ay):
    return f"{bv.MUM_ONEKI}/{s}/{config.BAR_4H}/{s}-{config.BAR_4H}-{ay}.zip"


def _funding_anahtari(s, ay):
    return f"{bv.FUNDING_ONEKI}/{s}/{s}-fundingRate-{ay}.zip"


def _liste_yaz(icerik) -> None:
    yol = bv.donuk_liste_yolu()
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(icerik), encoding="utf-8")


@pytest.fixture
def donuk_onbellek(monkeypatch, tmp_path):
    """Gecici onbellek: A sembolunun uc ayi ve dondurulmus liste."""
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", tmp_path)
    for ay in AYLAR:
        mum = sahte_4h(f"{ay}-01 00:00", 120)
        mum.to_parquet(bv.onbellek_yolu("klines", A_SEMBOL, config.BAR_4H, f"{ay}.parquet"), index=False)
        zaman = pd.date_range(f"{ay}-01 00:00", periods=60, freq="8h", tz="UTC")
        pd.DataFrame({"odeme_zamani": zaman, "aralik_saat": 8.0, "oran": 0.0001}).to_parquet(
            bv.onbellek_yolu("funding", A_SEMBOL, f"{ay}.parquet"), index=False)
    _liste_yaz({"mum": {A_SEMBOL: {config.BAR_4H: [_mum_anahtari(A_SEMBOL, a) for a in AYLAR]}},
                "funding": {A_SEMBOL: [_funding_anahtari(A_SEMBOL, a) for a in AYLAR]}})
    return tmp_path


@pytest.fixture
def soket_kapali(monkeypatch):
    def yasak(*_a, **_k):
        raise AssertionError("soket acilmamali")

    monkeypatch.setattr(socket.socket, "connect", yasak)
    monkeypatch.setattr(socket, "create_connection", yasak)


def _kapi(rol, hipotez="H2"):
    t = pd.Timestamp("2021-02-15 00:00", tz="UTC")
    bar = config.HIPOTEZ_IZGARASI[hipotez]
    ufuk = config.BIRINCIL_UFUK[bar]
    hacim = config.ASGARI_HACIM_4H if bar == config.BAR_4H else config.ASGARI_HACIM_1D
    try:
        pozisyon.olay_karari(t, ufuk, bar, hipotez=hipotez, yapilandirma=sinyal.izgara(hipotez)[0], rol=rol,
                             capa=None, birincil_ufuk=ufuk, kume="KESIF", sembol=A_SEMBOL, donem_no=0,
                             asgari_hacim=hacim, asgari_listeleme_yasi_gun=config.ASGARI_LISTELEME_YASI_GUN)
    except pencere.OlayOlusmaz:
        pass


@pytest.mark.parametrize(("rol", "hipotez"), [("olay", "H2"), ("K1", "H2"), ("K2", "H3")])
def test_soket_kapaliyken_kapi_calisir(donuk_onbellek, soket_kapali, rol, hipotez):
    _kapi(rol, hipotez)


@pytest.mark.parametrize("hipotez", ["H1", "H2", "H3"])
def test_soket_kapaliyken_kosul_calisir(donuk_onbellek, soket_kapali, hipotez):
    pozisyon.sinyal_kosulu(pd.Timestamp("2021-02-15 00:00", tz="UTC"), hipotez=hipotez,
                           yapilandirma=sinyal.izgara(hipotez)[0], capa=None, kume="KESIF", sembol=A_SEMBOL,
                           donem_no=0)


def test_liste_yokken_yukleme_hata_verir_aga_cikmaz(monkeypatch, tmp_path, soket_kapali):
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", tmp_path)
    monkeypatch.setattr(bv, "_listele", lambda *_a, **_k: pytest.fail("aga dusmemeli"))
    with pytest.raises(bv.DonukListeYok):
        klines.mumlari_yukle(A_SEMBOL, config.BAR_4H, "KESIF")
    with pytest.raises(bv.DonukListeYok):
        funding_modulu.funding_yukle(A_SEMBOL, "KESIF")


def test_sembol_listede_yoksa_hata_verir(donuk_onbellek):
    _liste_yaz({"mum": {}, "funding": {}})
    with pytest.raises(bv.DonukListeYok):
        klines.mumlari_yukle(A_SEMBOL, config.BAR_4H, "KESIF")


def test_eksik_ay_indirilmez_hata_verir(donuk_onbellek, soket_kapali):
    (donuk_onbellek / "klines" / A_SEMBOL / config.BAR_4H / "2021-02.parquet").unlink()
    with pytest.raises(bv.AgsizOkumaIhlali):
        klines.mumlari_yukle(A_SEMBOL, config.BAR_4H, "KESIF")


def test_agsiz_baglamda_http_yapilmaz():
    with bv.agsiz_okuma(), pytest.raises(bv.AgsizOkumaIhlali):
        bv._iste("https://ornek.invalid/x")


def test_baglam_is_parcacigina_ozeldir_ve_kapaninca_biter():
    with bv.agsiz_okuma():
        with bv.agsiz_okuma():
            assert bv._agsiz_mi()
        assert bv._agsiz_mi()
    assert not bv._agsiz_mi()


# --- Onay izni ----------------------------------------------------------------------------------


def test_bugunku_listeleme_izin_aramaz_referans(monkeypatch):
    """Referans olcum (RESULTS §14.40): baglam disindaki liste, izin olmadan da onay aylarini dondurur.
    Dondurulmus liste bundan daha sikidir (asagidaki testler)."""
    b = _b_sembolu()
    monkeypatch.setattr(bv, "_listele", lambda onek, ayirici: ([], [f"{onek}{b}-4h-2025-10.zip"]))
    assert bv.mum_dosyalari(b, config.BAR_4H) == [f"{bv.MUM_ONEKI}/{b}/{config.BAR_4H}/{b}-4h-2025-10.zip"]


def test_donuk_liste_izinsiz_b_grubu_ayini_dondurmez(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", tmp_path)
    b = _b_sembolu()
    anahtar = _mum_anahtari(b, "2021-01")
    _liste_yaz({"mum": {b: {config.BAR_4H: [anahtar]}}, "funding": {b: [_funding_anahtari(b, "2021-01")]}})
    with bv.agsiz_okuma():
        with pytest.raises(bv.OnayVerisiKorumasi):
            bv.mum_dosyalari(b, config.BAR_4H)
        with pytest.raises(bv.OnayVerisiKorumasi):
            bv.funding_dosyalari(b)
        with bv.onay_verisi_izni("test"):
            assert bv.mum_dosyalari(b, config.BAR_4H) == [anahtar]


def test_donuk_liste_izinsiz_c2_ayini_dondurmez_kesif_ayini_dondurur(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", tmp_path)
    kesif, c2 = _mum_anahtari(A_SEMBOL, "2021-01"), _mum_anahtari(A_SEMBOL, "2025-09")
    _liste_yaz({"mum": {A_SEMBOL: {config.BAR_4H: [kesif, c2]}, "AUSDT": {config.BAR_4H: [_mum_anahtari("AUSDT", "2021-01")]}},
                "funding": {}})
    with bv.agsiz_okuma():
        with pytest.raises(bv.OnayVerisiKorumasi):
            bv.mum_dosyalari(A_SEMBOL, config.BAR_4H)
        with bv.onay_verisi_izni("test"):
            assert bv.mum_dosyalari(A_SEMBOL, config.BAR_4H) == [kesif, c2]


def test_kapi_c1_listesini_kosu_olmadan_okutmaz(donuk_onbellek):
    with pytest.raises(split.OnayGerekli):
        klines.mumlari_yukle(_b_sembolu(), config.BAR_4H, "C1", onay=True)


# --- Dondurma -----------------------------------------------------------------------------------


@pytest.fixture
def sahte_kaynak(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", tmp_path)
    from data import universe

    evren = pd.DataFrame({"sembol": ["BUSDT", "AUSDT", "AUSDT"]})
    monkeypatch.setattr(universe, "evren_yukle", lambda: evren)

    def listele(onek, ayirici):
        return [], [f"{onek}x-2021-02.zip", f"{onek}x-2021-01.zip", f"{onek}x-2021-01.zip.CHECKSUM"]

    monkeypatch.setattr(bv, "_listele", listele)


def test_dondurma_yalnizca_dosya_adi_yazar_ve_deterministiktir(sahte_kaynak):
    birinci = bv.listeyi_dondur()
    icerik = json.loads(bv.donuk_liste_yolu().read_text(encoding="utf-8"))
    assert sorted(icerik) == ["funding", "mum"]
    assert sorted(icerik["mum"]) == ["AUSDT", "BUSDT"]
    assert icerik["mum"]["AUSDT"][config.BAR_4H] == [f"{bv.MUM_ONEKI}/AUSDT/{config.BAR_4H}/x-2021-01.zip",
                                                     f"{bv.MUM_ONEKI}/AUSDT/{config.BAR_4H}/x-2021-02.zip"]
    assert birinci["sembol_sayisi"] == 2 and birinci["dosya_sayisi"] == 8
    assert bv.listeyi_dondur(uzerine_yaz=True)["sha256"] == birinci["sha256"]


def test_dondurma_uzerine_sessizce_yazmaz(sahte_kaynak):
    bv.listeyi_dondur()
    with pytest.raises(FileExistsError):
        bv.listeyi_dondur()


def test_yerelde_eksik_dosyalar_sayilir(sahte_kaynak):
    assert bv.listeyi_dondur()["yerelde_eksik_dosya"] == 8


def test_onbellek_turleri_genislemedi():
    """Kumeye kesilmis veri diske yazilmaz (kuru okuma §6.5 risk 2)."""
    assert bv._ONBELLEK_TURLERI == ("klines", "funding", "klines_birincil_1d")


def test_guncelleme_araci_aga_cikmaya_devam_eder(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", tmp_path)
    cagri = []

    def listele(onek, ayirici):
        cagri.append(onek)
        return [], []

    monkeypatch.setattr(bv, "_listele", listele)
    klines.mumlari_yukle(A_SEMBOL, config.BAR_4H, "KESIF", yenile=True)
    assert cagri == [f"{bv.MUM_ONEKI}/{A_SEMBOL}/{config.BAR_4H}/"]


@pytest.mark.ag
def test_donuk_liste_agdaki_listeyle_ayni():
    """Aga cikar (`--ag`). Binance yeni ay ekleyince dogal olarak farklilasir: dondurmadan hemen sonra kosulur."""
    with bv.onay_verisi_izni("test: liste esitligi"):
        for sembol in ("SOLUSDT", "BTCUSDT", "A2ZUSDT"):
            with bv.agsiz_okuma():
                donuk_mum, donuk_funding = bv.mum_dosyalari(sembol, config.BAR_4H), bv.funding_dosyalari(sembol)
            assert donuk_mum == bv.mum_dosyalari(sembol, config.BAR_4H)
            assert donuk_funding == bv.funding_dosyalari(sembol)
