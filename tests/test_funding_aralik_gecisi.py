"""Funding araligi gecislerinde tamlik (F1 kapanis olcumu D1).

`aralik_saat` (Binance `funding_interval_hours`) bir kayittan SONRAKI odemeye
kalan sureyi gosterir: 559 gecisin 556'sinda kayittan sonraki bosluk yeni
araliga esit. Eski kod degeri "onceki odemeye gecen sure" okuyordu; gecis
kaydi eski ritimde geldiginde eksik odeme olmadan NaN uretiyordu (ör. FLMUSDT
8->2: 16:00 (8) -> 20:00 (2), 20:00 - 2s = 18:00 > 16:00 + 1 dk). Yeni kural
(`funding._odemeler_tam_mi`): ardisik iki odeme arasindaki bosluk iki kaydin
araliklarindan buyugunu + 1 dk'yi asarsa eksik odeme vardir.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import funding, pencere, split

DORT_SAAT = pd.Timedelta(hours=4)
SINIRSIZ_ORT = dict(kume_baslangic=None, donem_baslangic=None)
SINIRSIZ_POZ = dict(kume_baslangic=None, kume_bitis=None, donem_baslangic=None, donem_bitis=None)


def _ts(metin: str) -> pd.Timestamp:
    return pd.Timestamp(metin, tz="UTC")


def _cerceve(kayitlar: list[tuple[str, float]], oran: float = 1e-4) -> pd.DataFrame:
    cerceve = pd.DataFrame(
        {"odeme_zamani": [_ts(z) for z, _ in kayitlar], "aralik_saat": [float(a) for _, a in kayitlar], "oran": oran}
    )
    cerceve["oran_8h"] = funding.sekiz_saate_normallestir(cerceve["oran"], cerceve["aralik_saat"])
    return cerceve


def _ritim(bas: str, bitis: str, saat: int) -> list[tuple[str, float]]:
    return [(str(z), saat) for z in pd.date_range(bas, bitis, freq=f"{saat}h", tz="UTC")]


def _ortalama(fr, t, **sinirlar):
    return funding.funding_ortalamasi(fr, t, config.BAR_4H, saat=24, **{**SINIRSIZ_ORT, **sinirlar})


def _poz(fr, giris, **sinirlar):
    """18 barlik pozisyon; plan tek kapidan (pencere.pozisyon_plani) gecer."""
    zamanlar = pd.date_range(giris - 5 * DORT_SAAT, giris + 40 * DORT_SAAT, freq="4h")
    # Rev.8: donem sinirlari zorunlu; varsayilan donem serinin ilk ve son bari.
    donem = dict(donem_baslangic=zamanlar[0], donem_bitis=zamanlar[-1])
    plan = pencere.pozisyon_plani(
        zamanlar, giris - DORT_SAAT, 18, config.BAR_4H, birincil_ufuk=18, **{**SINIRSIZ_POZ, **donem, **sinirlar}
    )
    return funding.pozisyon_fundingi(fr, plan)


def _gecisi_kapsayan_ortalama_zamanlari(gecis: pd.Timestamp):
    for k in range(-12, 13):
        kapanis = gecis.floor("4h") + DORT_SAAT + k * DORT_SAAT
        if kapanis - pd.Timedelta(hours=24) <= gecis < kapanis:
            yield kapanis - DORT_SAAT


def _gecisi_kapsayan_girisler(gecis: pd.Timestamp):
    for k in range(-30, 13):
        giris = gecis.floor("4h") + k * DORT_SAAT
        if giris + funding.ODEME_TOLERANSI <= gecis < giris + 18 * DORT_SAAT + funding.ODEME_TOLERANSI:
            yield giris


# --- Sentetik gecis desenleri (D1'deki gercek orneklerin bicimi) --------------


DESENLER = {
    # FLMUSDT 2023-09-05: 16:00 (8) -> 20:00 (2), gecis kaydi ne eski ne yeni ritimde
    "8->2_flm": _ritim("2021-01-01", "2021-01-05 16:00", 8) + _ritim("2021-01-05 20:00", "2021-01-09", 2),
    # AMBUSDT 2023-10-12: 08:00 (8) -> 12:00 (4)
    "8->4_amb": _ritim("2021-01-01", "2021-01-05 08:00", 8) + _ritim("2021-01-05 12:00", "2021-01-09", 4),
    # AERGOUSDT 2025-04-25: 10:00 (2) -> 12:00 (4)
    "2->4_aergo": _ritim("2021-01-01", "2021-01-05 10:00", 2) + _ritim("2021-01-05 12:00", "2021-01-09", 4),
    # 0GUSDT 2026-02-15: 02:00 (1) -> 04:00 (4), iki saatlik bosluk
    "1->4_0g": _ritim("2021-01-01", "2021-01-05 02:00", 1) + _ritim("2021-01-05 04:00", "2021-01-09", 4),
    # 4->1 ve 4->8
    "4->1": _ritim("2021-01-01", "2021-01-05 08:00", 4) + _ritim("2021-01-05 09:00", "2021-01-09", 1),
    "4->8": _ritim("2021-01-01", "2021-01-05 08:00", 4) + _ritim("2021-01-05 16:00", "2021-01-09", 8),
}
GECIS = {
    "8->2_flm": "2021-01-05 20:00", "8->4_amb": "2021-01-05 12:00", "2->4_aergo": "2021-01-05 12:00",
    "1->4_0g": "2021-01-05 04:00", "4->1": "2021-01-05 09:00", "4->8": "2021-01-05 16:00",
}


@pytest.mark.parametrize("ad", list(DESENLER))
def test_eksiksiz_gecis_nan_uretmez(ad):
    fr = _cerceve(DESENLER[ad])
    gecis = _ts(GECIS[ad])
    for t in _gecisi_kapsayan_ortalama_zamanlari(gecis):
        assert not pd.isna(_ortalama(fr, t)), (ad, t)
    for giris in _gecisi_kapsayan_girisler(gecis):
        assert not pd.isna(_poz(fr, giris)), (ad, giris)


@pytest.mark.parametrize("ad", list(DESENLER))
def test_gecisten_sonraki_ritimde_eksik_odeme_yakalanir(ad):
    """Gecisten sonraki ikinci odeme silinirse (bosluk iki araligin buyugunu asar)."""
    kayitlar = DESENLER[ad]
    i = [z for z, _ in kayitlar].index(str(_ts(GECIS[ad])))
    silinen = _ts(kayitlar[i + 2][0])
    fr = _cerceve(kayitlar[: i + 2] + kayitlar[i + 3 :])
    kapanis = silinen.floor("4h") + DORT_SAAT * (1 if silinen != silinen.floor("4h") else 1) + DORT_SAAT
    assert pd.isna(_ortalama(fr, kapanis - DORT_SAAT)), (ad, silinen)
    assert pd.isna(_poz(fr, silinen.floor("4h") - 8 * DORT_SAAT)), (ad, silinen)


def test_sabit_ritimde_eksik_odeme_hala_yakalanir():
    kayitlar = _ritim("2021-01-01", "2021-01-09", 8)
    fr = _cerceve([k for k in kayitlar if k[0] != str(_ts("2021-01-05 08:00"))])
    assert pd.isna(_ortalama(fr, _ts("2021-01-05 12:00")))
    assert pd.isna(_poz(fr, _ts("2021-01-04 20:00")))


def test_pencere_basindaki_eksik_odeme_onceki_kayitla_yakalanir():
    """Pencere 12:00'de basliyor; 16:00 odemesi eksik. Onceki kayit (08:00, 8s)
    ile ilk odeme (00:00) arasi 16 saat > 8 saat."""
    kayitlar = _ritim("2021-01-01", "2021-01-09", 8)
    fr = _cerceve([k for k in kayitlar if k[0] != str(_ts("2021-01-04 16:00"))])
    assert pd.isna(_ortalama(fr, _ts("2021-01-05 08:00")))  # pencere [04 12:00, 05 12:00)


def test_onceki_kayit_kume_basindan_onceyse_okunmaz():
    """Ilk odeme pencere basinda degil ve onceki kayit kume oncesinde: tamlik
    gosterilemez, NaN. Kume siniri olmadan onceki kayit okunur ve deger doner."""
    c2 = split.kume_araligi("C2")[0]
    kayitlar = [(str(z), 8) for z in pd.date_range(c2 - pd.Timedelta(hours=28), c2 + pd.Timedelta(days=3), freq="8h")]
    fr = _cerceve(kayitlar)  # odemeler 04:00, 12:00, 20:00
    t = c2 + pd.Timedelta(hours=20)  # kapanis 09-02 00:00, pencere [09-01 00:00, 09-02 00:00)
    assert not pd.isna(_ortalama(fr, t))
    assert pd.isna(_ortalama(fr, t, kume_baslangic=c2))
    # Pozisyon funding'inde kume basinda giris artik olusmaz: sinyal kume icinde
    # olmalidir (pencere.pozisyon_plani); kume oncesi kaydin okunmamasi
    # test_pozisyon_fundingi.py'de plan uzerinden ayrica dogrulanir.


def test_kapanistan_sonraki_kayit_okunmaz():
    """Gelecege bakis saldirisi: kapanistan sonraki kayitlarin araligini ve
    zamanini bozmak funding_ortalamasi sonucunu degistirmez."""
    fr = _cerceve(DESENLER["8->2_flm"])
    t = _ts("2021-01-05 16:00")  # kapanis 20:00
    once = _ortalama(fr, t)
    bozuk = fr.copy()
    sonra = bozuk["odeme_zamani"] >= t + DORT_SAAT
    bozuk.loc[sonra, "aralik_saat"] = 1000.0
    assert _ortalama(bozuk, t) == once


# --- Gercek veri: D1 orneklerindeki gecisler ----------------------------------
#
# Onbellekten okur, aga cikmaz; onbellek yoksa atlanir.


def _onbellek_funding(sembol: str, aylar: list[str]) -> pd.DataFrame | None:
    dizin = config.ONBELLEK_DIZINI / "funding" / sembol
    dosyalar = [dizin / f"{ay}.parquet" for ay in aylar]
    if not all(d.exists() for d in dosyalar):
        return None
    fr = pd.concat([pd.read_parquet(d) for d in dosyalar], ignore_index=True)
    fr = fr.drop_duplicates("odeme_zamani", keep="last").sort_values("odeme_zamani", ignore_index=True)
    fr["oran_8h"] = funding.sekiz_saate_normallestir(fr["oran"], fr["aralik_saat"])
    return fr


GERCEK = [
    ("FLMUSDT", ["2023-08", "2023-09", "2023-10"], "2023-09-05 20:00", 8.0, 2.0),
    ("AMBUSDT", ["2023-09", "2023-10", "2023-11"], "2023-10-12 12:00", 8.0, 4.0),
    ("AERGOUSDT", ["2025-03", "2025-04", "2025-05"], "2025-04-25 12:00", 2.0, 4.0),
]


@pytest.mark.parametrize("sembol,aylar,gecis,eski,yeni", GERCEK, ids=[g[0] for g in GERCEK])
def test_gercek_gecis_nan_uretmez(sembol, aylar, gecis, eski, yeni):
    fr = _onbellek_funding(sembol, aylar)
    if fr is None:
        pytest.skip(f"onbellekte {sembol} funding verisi yok")
    z = pd.DatetimeIndex(fr["odeme_zamani"])
    i = int(((z - _ts(gecis)).to_series().abs() < funding.ODEME_TOLERANSI).to_numpy().argmax())
    assert fr["aralik_saat"].iloc[i - 1] == eski and fr["aralik_saat"].iloc[i] == yeni, "ornek gecis veride degil"

    gecis_ani = z[i]
    for t in _gecisi_kapsayan_ortalama_zamanlari(gecis_ani):
        assert not pd.isna(_ortalama(fr, t)), t
    for giris in _gecisi_kapsayan_girisler(gecis_ani):
        assert not pd.isna(_poz(fr, giris)), giris


@pytest.mark.parametrize("sembol,aylar,gecis,eski,yeni", GERCEK, ids=[g[0] for g in GERCEK])
def test_gercek_gecisten_sonraki_odeme_silinirse_nan(sembol, aylar, gecis, eski, yeni):
    fr = _onbellek_funding(sembol, aylar)
    if fr is None:
        pytest.skip(f"onbellekte {sembol} funding verisi yok")
    z = pd.DatetimeIndex(fr["odeme_zamani"])
    i = int(((z - _ts(gecis)).to_series().abs() < funding.ODEME_TOLERANSI).to_numpy().argmax())
    silinen = z[i + 1]
    eksik = fr.drop(index=i + 1).reset_index(drop=True)
    giris = silinen.floor("4h") - 8 * DORT_SAAT
    assert not pd.isna(_poz(fr, giris))
    assert pd.isna(_poz(eksik, giris))
