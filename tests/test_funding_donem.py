"""Funding ve listeleme donemi (on-kayit §2 rev.7).

"Hicbir funding kaydi bulunmayan listeleme donemi uc hipotezin hicbirinde
kullanilmaz." ve "Donem sonundan sonra gelen funding kayitlari yok sayilir."
Evren tablosu funding'siz donemi `donem_funding_yok` ile isaretler;
`funding_yukle` donem sonrasi kayitlari atar.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import donem, funding, split, universe

BAR = config.BAR_4H
D0 = donem.Donem(pd.Timestamp("2021-01-01 00:00", tz="UTC"), pd.Timestamp("2021-01-10 20:00", tz="UTC"), 60, 60)
D1 = donem.Donem(pd.Timestamp("2021-02-01 00:00", tz="UTC"), pd.Timestamp("2021-02-10 20:00", tz="UTC"), 60, 60)


def _fund(*zamanlar):
    z = pd.DatetimeIndex([pd.Timestamp(t, tz="UTC") for t in zamanlar])
    return pd.DataFrame({"odeme_zamani": z, "aralik_saat": 8.0, "oran": 1e-4, "oran_8h": 1e-4})


def _kalan(cerceve):
    return [str(t) for t in cerceve["odeme_zamani"].dt.strftime("%Y-%m-%d %H:%M")]


# --- donem_sonrasi_kayitlari_at (saf) -----------------------------------------


def test_son_donemden_sonraki_kayitlar_atilir():
    f = _fund("2021-02-10 16:00", "2021-02-11 00:00", "2021-02-11 08:00", "2021-03-01 00:00")
    # D1'in son bari 20:00'de acilir, kapanisi 2021-02-11 00:00: o andaki odeme dahildir.
    assert _kalan(funding.donem_sonrasi_kayitlari_at(f, [D0, D1], BAR)) == ["2021-02-10 16:00", "2021-02-11 00:00"]


def test_donemler_arasindaki_kayitlar_atilir():
    f = _fund("2021-01-10 16:00", "2021-01-15 00:00", "2021-01-31 23:59:30", "2021-02-01 08:00")
    kalan = _kalan(funding.donem_sonrasi_kayitlari_at(f, [D0, D1], BAR))
    # 23:59:30 kaydi D1 baslangicina 1 dakikadan yakin: ayni an sayilir (ODEME_TOLERANSI).
    assert kalan == ["2021-01-10 16:00", "2021-01-31 23:59", "2021-02-01 08:00"]


def test_kapanistan_bir_dakika_sonraki_kayit_atilir():
    f = _fund("2021-02-11 00:00:59", "2021-02-11 00:01")
    assert _kalan(funding.donem_sonrasi_kayitlari_at(f, [D1], BAR)) == ["2021-02-11 00:00"]
    assert len(funding.donem_sonrasi_kayitlari_at(f, [D1], BAR)) == 1


def test_ilk_donemden_onceki_kayitlar_korunur():
    f = _fund("2020-12-31 16:00", "2021-01-01 08:00")
    assert len(funding.donem_sonrasi_kayitlari_at(f, [D0], BAR)) == 2


def test_donem_yoksa_kayit_kalmaz():
    assert funding.donem_sonrasi_kayitlari_at(_fund("2021-01-01 08:00"), [], BAR).empty


def test_girdi_degismez():
    f = _fund("2021-01-01 08:00", "2021-03-01 00:00")
    once = f.copy()
    funding.donem_sonrasi_kayitlari_at(f, [D0], BAR)
    pd.testing.assert_frame_equal(f, once)


# --- donemde_funding_var (saf) ------------------------------------------------


def test_yalnizca_uzlasma_sonrasi_kaydi_olan_donem_funding_siz():
    f = _fund("2021-01-11 08:00", "2021-01-12 00:00")
    assert not funding.donemde_funding_var(f, D0, BAR)
    assert funding.donemde_funding_var(_fund("2021-01-11 00:00"), D0, BAR)  # son barin kapanisi
    assert not funding.donemde_funding_var(_fund("2020-12-31 16:00"), D0, BAR)  # donem oncesi
    assert not funding.donemde_funding_var(_fund(), D0, BAR)


# --- funding_yukle ------------------------------------------------------------


@pytest.fixture
def ortam(tmp_path, monkeypatch):
    """AAUSDT (A grubu) iki donemli; ham funding donem arasi ve uzlasma sonrasi kayit icerir."""
    cerceve = split.split_uret(["AAUSDT", "BBUSDT"])
    split.split_yaz(cerceve, tmp_path / "split.csv")
    monkeypatch.setattr(config, "SPLIT_CSV", tmp_path / "split.csv")

    satirlar = []
    for d_id, d in enumerate((D0, D1)):
        satirlar.append({
            "sembol": "AAUSDT", "ilk_ay": "2021-01", "son_ay": "2021-03", "dosya_sayisi_4h": 3,
            "funding_dosya_sayisi": 3, "sozlesme_tipi": "", "dayanak_tipi": "", "settled_aylari": "",
            "haric": False, "haric_gerekce": "", "donem_id": d_id, "donem_baslangic": d.baslangic,
            "donem_bitis": d.bitis, "donem_bar_sayisi": d.bar_sayisi,
            "donem_gercek_bar_sayisi": d.gercek_bar_sayisi, "donem_funding_yok": False,
        })
    universe.evren_csv_yaz(pd.DataFrame(satirlar), tmp_path / "universe.csv")
    monkeypatch.setattr(config, "UNIVERSE_CSV", tmp_path / "universe.csv")

    ham = _fund("2021-01-05 00:00", "2021-01-20 00:00", "2021-02-05 00:00", "2021-02-20 00:00", "2021-03-01 00:00")
    monkeypatch.setattr(funding, "ham_funding_yukle", lambda sembol, yenile=False: ham.copy())
    # KESIF araligi 2021'i kapsar (config); kume kesimi ayrica test edilir.
    assert split.kume_araligi("KESIF")[0] <= D0.baslangic


def test_funding_yukle_donem_sonrasi_kayitlari_atar(ortam):
    sonuc = funding.funding_yukle("AAUSDT", "KESIF")
    assert _kalan(sonuc) == ["2021-01-05 00:00", "2021-02-05 00:00"]
    assert list(sonuc.columns) == funding.FUNDING_CIKTI_SUTUNLARI


def test_funding_yukle_evrende_olmayan_sembolu_reddeder(ortam):
    """split'te olup evren tablosunda olmayan sembol: donemleri bilinmez, KeyError."""
    evren = universe.evren_yukle().assign(sembol="CCUSDT")
    config.UNIVERSE_CSV.unlink()
    universe.evren_csv_yaz(evren, config.UNIVERSE_CSV)
    with pytest.raises(KeyError):
        funding.funding_yukle("AAUSDT", "KESIF")
