"""exchangeInfo anlik goruntusu ve deliveryDate denetimi (on-kayit §2 rev.7).

Rev.7: "Donem ... sifir olmayan hacimli son barda biter." ve "evrende 128
sembolun exchangeInfo durumunun SETTLING oldugu ... exchangeInfo'da hic
bulunmayan 28 sembolle birlikte" delist edilmistir.

Gercek veri testleri canli uc noktayi degil, depoya alinmis goruntuyu
(`data/exchange_info_anlik.json`) ve commit edilmis `universe.csv`'yi okur; aga
cikmaz. Uzlasmis bir sozlesmenin deliveryDate'i, donemin son gercek barinin
icine dusmelidir: `donem_bitis <= deliveryDate < donem_bitis + 4 saat`. Daha
gec bir deliveryDate donem sonunun erken kesildigini, daha erken bir deliveryDate
ise uzlasma sonrasi dolgu barlarin doneme sizdigini gosterir.
"""

from __future__ import annotations

import json
import warnings

import pandas as pd
import pytest

import config
from data import universe

ADIM = pd.Timedelta(hours=4)
VERI_SONU_BARI = pd.Timestamp("2026-08-31 20:00", tz="UTC")

gercek_veri = pytest.mark.skipif(
    not (config.EXCHANGE_INFO_ANLIK.exists() and config.UNIVERSE_CSV.exists()),
    reason="exchangeInfo goruntusu ya da universe.csv yok",
)


# --- Saf fonksiyonlar (sentetik) ---------------------------------------------


def _ham(semboller):
    return json.dumps({"serverTime": 1, "symbols": semboller})


def _sembol(ad, durum="TRADING", teslim=4133404800000, **ek):
    return {"symbol": ad, "contractType": "PERPETUAL", "status": durum, "deliveryDate": teslim,
            "onboardDate": 1569398400000, "filters": [{"x": 1}], **ek}


def test_goruntu_kirpilir_ve_siralanir():
    g = universe.exchange_info_anlik_goruntu(_ham([_sembol("ZUSDT"), _sembol("AUSDT")]),
                                             pd.Timestamp("2026-09-18 12:00", tz="UTC"))
    assert [s["symbol"] for s in g["symbols"]] == ["AUSDT", "ZUSDT"]
    assert set(g["symbols"][0]) == set(universe.ANLIK_ALANLAR)
    assert g["alinma_zamani_utc"] == "2026-09-18T12:00:00Z"
    assert len(g["ham_yanit_sha256"]) == 64


def test_goruntu_yuklenir_zamanlar_utc(tmp_path):
    yol = tmp_path / "ei.json"
    g = universe.exchange_info_anlik_goruntu(_ham([_sembol("AUSDT", "SETTLING", 1718096400000)]),
                                             pd.Timestamp("2026-09-18", tz="UTC"))
    yol.write_text(json.dumps(g), encoding="utf-8")
    t = universe.exchange_info_anlik_yukle(yol)
    assert t.loc[0, "deliveryDate"] == pd.Timestamp("2024-06-11 09:00", tz="UTC")
    assert str(t["deliveryDate"].dt.tz) == "UTC"


def test_goruntu_uzerine_yazilmaz(tmp_path):
    yol = tmp_path / "ei.json"
    yol.write_text("{}", encoding="utf-8")
    with pytest.raises(FileExistsError):
        universe.exchange_info_anlik_kaydet(yol)


def test_delist_sinifi_goruntude_olmayan_sembolu_ayirir():
    evren = pd.DataFrame({
        "sembol": ["AUSDT", "BUSDT", "CUSDT", "DUSDT"], "haric": [False, False, False, True],
        "donem_id": [0, 0, 0, 0],
        "donem_bitis": pd.to_datetime(["2024-06-11 08:00"] * 4, utc=True),
    })
    anlik = pd.DataFrame({
        "symbol": ["AUSDT", "BUSDT", "DUSDT"], "status": ["SETTLING", "TRADING", "SETTLING"],
        "deliveryDate": pd.to_datetime(["2024-06-11 09:00"] * 3, utc=True),
    })
    sinif = universe.delist_sinifi(evren, anlik).set_index("sembol")["sinif"].to_dict()
    assert sinif == {"AUSDT": "SETTLING", "BUSDT": "TRADING", "CUSDT": "exchangeInfo_disi"}


def test_delist_sinifi_haric_semboller_disarida_kalir():
    """Haric tutulan bir sembol goruntude delist gorunse bile calisma evrenine sizmamali
    (on-kayit §2: haric semboller hicbir denetim ciktisinda dahil sayilmaz)."""
    evren = pd.DataFrame({
        "sembol": ["HARICUSDT"], "haric": [True], "donem_id": [-1],
        "donem_bitis": pd.to_datetime([pd.NaT], utc=True),
    })
    anlik = pd.DataFrame({
        "symbol": ["HARICUSDT"], "status": ["SETTLING"],
        "deliveryDate": pd.to_datetime(["2024-06-11 09:00"], utc=True),
    })
    sonuc = universe.delist_sinifi(evren, anlik)
    assert sonuc.empty


def test_delist_sinifi_coklu_donem_max_bitis_alir():
    """Birden fazla donemi olan sembolde son_donem_bitis, donem_id>=0 satirlarinin
    MAKSIMUMU olmali; ilk donemin bitisiyle karistirilmamali."""
    evren = pd.DataFrame({
        "sembol": ["XUSDT", "XUSDT", "XUSDT"], "haric": [False, False, False],
        "donem_id": [0, 1, -1],
        "donem_bitis": pd.to_datetime(["2021-01-01 00:00", "2022-06-01 00:00", pd.NaT], utc=True),
    })
    anlik = pd.DataFrame({"symbol": ["XUSDT"], "status": ["TRADING"],
                          "deliveryDate": pd.to_datetime([pd.NaT], utc=True)})
    sonuc = universe.delist_sinifi(evren, anlik).set_index("sembol")
    assert sonuc.at["XUSDT", "son_donem_bitis"] == pd.Timestamp("2022-06-01 00:00", tz="UTC")


def test_anlik_kaydet_var_olmayan_dosyada_agi_dener(tmp_path):
    """Dosya yoksa fonksiyon gercekten ag cagirir (sessizce sahte veri uretmez);
    conftest'in ag engeli bunu yakalamali. Sessizce basarili donerse ag cagrisi
    hic yapilmamis, yani goruntu icerigi dogrulanmamis demektir."""
    hedef = tmp_path / "yeni.json"
    assert not hedef.exists()
    with pytest.raises(AssertionError, match="aga cikamaz"):
        universe.exchange_info_anlik_kaydet(hedef)
    assert not hedef.exists()


# --- Gercek veri denetimi ------------------------------------------------------


@pytest.fixture(scope="module")
def siniflar():
    return universe.delist_sinifi(universe.evren_yukle(), universe.exchange_info_anlik_yukle())


@gercek_veri
def test_delist_sayilari_on_kayitla_ayni(siniflar):
    """On-kayit §2 rev.7: 128 SETTLING + 28 exchangeInfo disi."""
    sayim = siniflar["sinif"].value_counts().to_dict()
    assert sayim.get(universe.SETTLING_DURUMU) == 128
    assert sayim.get("exchangeInfo_disi") == 28


class AtlananTeslimUyarisi(UserWarning):
    """deliveryDate'i toplam donemden sonra olan SETTLING sembol kontrolden atlandi."""


@gercek_veri
def test_uzlasmis_sozlesmenin_deliverydate_i_son_gercek_barin_icinde(siniflar):
    """`donem_bitis <= deliveryDate < donem_bitis + 4h` (veri sonundan onceki teslimler).

    deliveryDate'i toplam donemden sonra olan SETTLING semboller kontrol
    edilemez; bunlar 128 delist sayimina girer ama tum pencere boyunca islem
    gormustur. Sessizce atlanmazlar: listeleri `AtlananTeslimUyarisi` ile
    raporlanir (denetci bulgusu D-B4).
    """
    s = siniflar.loc[siniflar["sinif"] == universe.SETTLING_DURUMU]
    atlanan = s.loc[~(s["deliveryDate"] <= pd.Timestamp(config.DONEM_SONU))]
    if not atlanan.empty:
        warnings.warn(AtlananTeslimUyarisi(
            f"{len(atlanan)} SETTLING sembolun deliveryDate'i toplam donemden sonra, kontrol "
            f"edilmedi: {', '.join(f'{r.sembol} ({r.deliveryDate})' for r in atlanan.itertuples())}"
        ))
    s = s.loc[s["deliveryDate"] <= pd.Timestamp(config.DONEM_SONU)]
    assert not s.empty
    sapan = s.loc[~((s["son_donem_bitis"] <= s["deliveryDate"])
                    & (s["deliveryDate"] < s["son_donem_bitis"] + ADIM))]
    assert sapan.empty, f"deliveryDate son gercek barin disinda:\n{sapan.to_string()}"


@gercek_veri
def test_islem_goren_sozlesme_veri_sonuna_kadar_surer(siniflar):
    """Goruntude TRADING olan sembolun son donemi verinin son barinda biter."""
    t = siniflar.loc[siniflar["sinif"] == "TRADING"]
    sapan = t.loc[t["son_donem_bitis"] != VERI_SONU_BARI]
    assert sapan.empty, f"TRADING ama donem veri sonundan once bitiyor:\n{sapan.to_string()}"


@gercek_veri
def test_goruntudeki_sozlesme_tipleri_evren_tablosuyla_ayni():
    """Evren tablosunun sozlesme/dayanak tipi goruntuyle celismez; goruntude olmayan
    sembolde evren tablosunda da tip bos kalir."""
    evren = universe.evren_yukle().drop_duplicates("sembol").set_index("sembol")
    anlik = universe.exchange_info_anlik_yukle().set_index("symbol")
    for sembol, r in evren.iterrows():
        if sembol in anlik.index:
            assert r["sozlesme_tipi"] == anlik.at[sembol, "contractType"], sembol
            assert r["dayanak_tipi"] == anlik.at[sembol, "underlyingType"], sembol
        else:
            assert r["sozlesme_tipi"] == "" and r["dayanak_tipi"] == "", sembol
