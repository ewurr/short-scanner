"""Karar noktasi donem sinirlarini evren tablosundan okur (kapi sertlestirme turu, denetci F1K2 D-B2).

On-kayit §2 "Listeleme donemi" ve "Evren tablosunun sabitlenmesi" ("analiz bu dosyadan okur, canli
exchangeInfo'dan yeniden turetmez"). `pozisyon.olay_karari` `sembol` ve `donem_no` alir; sinirlar
`pozisyon.donem_kaydi` ile commit edilmis tablodan gelir. Tabloda olmayan donem, haric tutulan sembol ve
serbest sinir programlama hatasidir. Sembolun grubu kumeye ait olmalidir (on-kayit §3). Funding'i
bulunmayan donem olay ya da kontrol uretmez (on-kayit §2). Aga cikmaz.
"""

from __future__ import annotations

import pandas as pd
import pytest

from data import pencere, pozisyon, split, universe
from kapi_yardimcisi import veri
from sinyal_yardimcisi import sinyal
from uygunluk_yardimcisi import esikler

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H = lambda n: pd.Timedelta(hours=n)  # noqa: E731

DB, B = T("2025-01-01"), T("2025-06-30 20:00")
Z = pd.date_range(T("2025-03-01"), B, freq="4h")
MUM = pd.DataFrame({"open_time": Z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
FUND = pd.DataFrame({"odeme_zamani": pd.date_range(DB, B + H(4), freq="8h"), "aralik_saat": 8.0,
                     "oran": 0.0, "oran_8h": 0.0})
T_SINYAL = T("2025-03-10 04:00")


def _karar(kume="KESIF", **kayit):
    return pozisyon.olay_karari(T_SINYAL, 18, "4h", hipotez="H1", birincil_ufuk=18, kume=kume,
                                sinyal_degerleri=sinyal("H1"), **kayit, **esikler("4h"))


def _veri(**ek):
    """Kapi sertlestirme turu 2: kapi veriyi kendisi yukler; sentetik donem ve veri birlikte kaydedilir."""
    return veri(MUM, FUND, DB, B, uygun_bas=DB, **ek)


def _evren():
    return universe.evren_yukle()


def test_sinirlar_tablodan_gelir():
    p = _karar(**_veri())
    assert (p.plan.donem_baslangic, p.plan.donem_bitis) == (DB, B)


def test_gercek_tablo_okunur():
    """Test fiksturu gercek kayitlari korur: haric tutulmayan her donem tabloyla ayni."""
    evren = _evren()
    evren = evren.loc[~evren["haric"] & (evren["donem_id"] >= 0)]
    assert len(evren) > 0
    for r in evren.itertuples():
        assert pozisyon.donem_kaydi(r.sembol, int(r.donem_id)) == (
            pd.Timestamp(r.donem_baslangic), pd.Timestamp(r.donem_bitis), bool(r.donem_funding_yok))


def test_tabloda_olmayan_donem_reddedilir():
    evren = _evren()
    dahil = evren.loc[~evren["haric"] & (evren["donem_id"] >= 0)]
    sembol = str(dahil["sembol"].iloc[0])
    son_no = int(dahil.loc[dahil["sembol"] == sembol, "donem_id"].max())
    for kayit in ({"sembol": sembol, "donem_no": son_no + 1}, {"sembol": sembol, "donem_no": -1},
                  {"sembol": "YOKBOYLEUSDT", "donem_no": 0}):
        with pytest.raises(ValueError, match="evren tablosunda yok"):
            _karar(**kayit)


def test_haric_tutulan_sembolun_donemi_reddedilir():
    evren = _evren()
    haric = evren.loc[evren["haric"] & (evren["donem_id"] >= 0)]
    assert len(haric) > 0, "tabloda donemi olan haric sembol bekleniyordu"
    r = haric.iloc[0]
    with pytest.raises(ValueError, match="evren tablosunda yok"):
        pozisyon.donem_kaydi(str(r["sembol"]), int(r["donem_id"]))


@pytest.mark.parametrize("serbest", [{"donem_baslangic": DB, "donem_bitis": B},
                                     {"donem_baslangic": None, "donem_bitis": None}])
def test_serbest_donem_siniri_verilemez(serbest):
    with pytest.raises(TypeError):
        _karar(**serbest)
    with pytest.raises(TypeError):
        _karar(**_veri(), **serbest)


@pytest.mark.parametrize("kayit", [{"sembol": None, "donem_no": 0}, {"sembol": b"BTCUSDT", "donem_no": 0},
                                   {"sembol": "BTCUSDT", "donem_no": True}, {"sembol": "BTCUSDT", "donem_no": 0.0},
                                   {"sembol": "BTCUSDT", "donem_no": "0"}])
def test_sembol_ve_donem_no_turu(kayit):
    with pytest.raises(TypeError):
        _karar(**kayit)


def test_grup_kumeye_ait_olmali(tmp_path, monkeypatch):
    a = _veri(grup="A")
    b = _veri(grup="B")
    pozisyon.onay_dogrula(_karar(**a))
    with pytest.raises(ValueError, match="kumesine ait degil"):
        _karar(**b)  # KESIF yalnizca A
    # Kapi sertlestirme turu 2: kapi C1 verisini kume korumali yoldan yukler; onay kosusu olmadan
    # OnayGerekli (onceki beklenti: onaysiz onay; denetci KS D-B4). Kosu icinde onaylanir.
    with pytest.raises(split.OnayGerekli):
        _karar(kume="C1", **b)
    import config

    kayit = tmp_path / "onay_gecici.md"
    kayit.write_text("bas\n", encoding="utf-8")
    monkeypatch.setattr(config, "ONAY_KAYDI", kayit)
    with split.onay_kosusu("H1", "C1"):
        # Kapi sertlestirme turu 3: onay baglami grup denetiminden once gelir; C1 grup denetimi (A sembolu)
        # artik acik kosu icinde sinaniyor (onceki: kosu disinda ValueError).
        with pytest.raises(ValueError, match="kumesine ait degil"):
            _karar(kume="C1", **a)  # C1 yalnizca B
        pozisyon.onay_dogrula(_karar(kume="C1", **b))


def test_gercek_b_grubu_sembol_kesifte_reddedilir():
    bolme = split.split_oku()
    evren = _evren()
    b_semboller = set(bolme.loc[bolme["grup"] == "B", "sembol"])
    r = evren.loc[evren["sembol"].isin(b_semboller) & ~evren["haric"] & (evren["donem_id"] >= 0)].iloc[0]
    with pytest.raises(ValueError, match="kumesine ait degil"):
        pozisyon.grup_dogrula(str(r["sembol"]), "KESIF")


def test_fundingsiz_donem_olay_uretmez():
    """Funding cercevesi tam olsa bile tablodaki funding'siz donem bayragi olayi dusurur (on-kayit §2)."""
    with pytest.raises(pozisyon.FundingTamDegil) as hata:
        _karar(**_veri(funding_yok=True))
    assert pencere.ret_gerekcesi(hata.value) == "funding_tam_degil"


def test_analiz_kodu_kapi_kayitlarina_dokunamaz(tmp_path):
    from tarama_yardimcisi import KAYIT_DESENI, ihlaller

    ornekler = {"study/k1.py": "pozisyon._kayitlar = lambda: sahte\n",
                "events/h1.py": "from kapi_yardimcisi import donem\n",
                "study/temiz.py": "p = pozisyon.olay_karari(m, f, t, 18, bar, sembol=s, donem_no=0, kume='KESIF')\n"}
    for ad, metin in ornekler.items():
        (tmp_path / ad).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / ad).write_text(metin, encoding="utf-8")
    assert ihlaller(KAYIT_DESENI, kok=tmp_path) == ["events/h1.py", "study/k1.py"]
    assert ihlaller(KAYIT_DESENI) == []
