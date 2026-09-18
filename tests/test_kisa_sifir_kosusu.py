"""Serinin ortasindaki kisa sifir hacim kosulari icin denetim uyarisi (on-kayit §2 rev.7).

Rev.7: "6 veya daha fazla ardisik sifir hacimli bar (bir gun) donemi boler."
Karar rev.7'de verilmistir: bundan kisa (1-5 bar) bir sifir hacim kosusu donemi
bolmez ve donemin parcasidir. Bu test o karari degistirmez ve sorgulamaz.
F1 olcumu S2 evrende boyle bir kosu bulmamisti; rev.7 karari bu olcumle
verildi. Veri yenilenip boyle bir kosu ortaya cikarsa, kural geregi doneme giren
bu barlar `KisaSifirKosusuUyarisi` ile gorunur kilinir. Test basarisiz olmaz,
cunku kural ihlali yoktur; uyari yalnizca kararin dayandigi olcumun artik
gecerli olmadigini bildirir.

Gercek veri testi onbellekten okur, aga cikmaz; onbellek yoksa atlanir.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import config
from data import donem, universe

ONBELLEK = config.ONBELLEK_DIZINI / "klines"


class KisaSifirKosusuUyarisi(UserWarning):
    """Serinin ortasinda 1-5 barlik sifir hacim kosusu bulundu."""


def kisa_kosu_satirlari(sembol: str, zamanlar, hacim) -> list[str]:
    """Bir serideki kisa sifir kosularinin okunur satirlari (donem icinde mi bilgisiyle)."""
    kosular = donem.kisa_sifir_kosulari(zamanlar, hacim, config.BAR_4H)
    if not kosular:
        return []
    donemler = donem.listeleme_donemleri(zamanlar, hacim, config.BAR_4H)
    return [
        f"{sembol} {k.baslangic:%Y-%m-%d %H:%M} .. {k.bitis:%Y-%m-%d %H:%M} ({k.bar_sayisi} bar, "
        f"{'donem icinde' if donem.donem_bul(k.baslangic, donemler) is not None else 'donem disinda'})"
        for k in kosular
    ]


def uyar(satirlar: list[str]) -> None:
    if satirlar:
        warnings.warn(KisaSifirKosusuUyarisi(
            f"{len(satirlar)} kisa sifir hacim kosusu (1-{config.DOLGU_KOSU_ESIGI_BAR - 1} bar) "
            "donemi bolmeden doneme giriyor:\n" + "\n".join(satirlar)
        ), stacklevel=2)


def _seri(bar_sayisi: int):
    z = pd.date_range("2021-01-01", periods=bar_sayisi, freq="4h", tz="UTC")
    return z, np.full(bar_sayisi, 1_000_000.0)


# --- Uyari mekanizmasi (sentetik) ---------------------------------------------


@pytest.mark.parametrize("uzunluk", [1, 3, config.DOLGU_KOSU_ESIGI_BAR - 1])
def test_ortadaki_kisa_kosu_uyarir(uzunluk):
    z, h = _seri(60)
    h[30:30 + uzunluk] = 0
    with pytest.warns(KisaSifirKosusuUyarisi, match="donem icinde"):
        uyar(kisa_kosu_satirlari("XUSDT", z, h))


@pytest.mark.parametrize("dilim", [
    slice(30, 30 + config.DOLGU_KOSU_ESIGI_BAR),  # dolgu kosusu: donemi boler, uyari degil
    slice(0, 3),  # serinin basi
    slice(57, 60),  # serinin sonu
])
def test_dolgu_ve_uc_kosular_uyarmaz(dilim):
    z, h = _seri(60)
    h[dilim] = 0
    with warnings.catch_warnings():
        warnings.simplefilter("error", KisaSifirKosusuUyarisi)
        uyar(kisa_kosu_satirlari("XUSDT", z, h))


def test_eksik_bar_sifir_hacim_sayilmaz():
    """Eksik bar (kesinti) sifir hacimli bar degildir; kisa kosu uretmez."""
    z, h = _seri(60)
    tut = np.ones(60, dtype=bool)
    tut[30:33] = False
    assert kisa_kosu_satirlari("XUSDT", z[tut], h[tut]) == []


def test_uyari_bos_listede_hic_tetiklenmez():
    """`uyar([])` hicbir uyari birakmamali; testin kendisi de bunu SESSIZCE
    gecirmemeli -- kayitli uyari sayisini acikca sifir olarak dogrular."""
    with warnings.catch_warnings(record=True) as kayit:
        warnings.simplefilter("always")
        uyar([])
    assert len(kayit) == 0


def test_temiz_seride_gercek_veri_denetim_yolu_hicbir_uyari_uretmez():
    """`kisa_kosu_satirlari` bos donunce `uyar` cagrisi da sessiz kalmali; bu ikisi
    ayri test edilmezse bir tarafin hep 'gecen' gorunup digerinin hic calismadigi
    (ornegin `uyar` hep `if satirlar` False dalina dusup asla dogrulanmadigi) fark edilmez."""
    z, h = _seri(60)  # sifir kosu yok
    satirlar = kisa_kosu_satirlari("XUSDT", z, h)
    assert satirlar == []
    with warnings.catch_warnings():
        warnings.simplefilter("error", KisaSifirKosusuUyarisi)
        uyar(satirlar)  # hata firlatirsa test kirmizi olur


def test_iki_ayri_kisa_kosu_ikisi_de_raporlanir():
    """Ayni seride birbirinden bagimsiz iki kisa sifir kosusu varsa ikisi de
    satira donusmeli; biri sessizce kaybolmamali."""
    z, h = _seri(60)
    h[10:12] = 0  # 2 bar
    h[40:44] = 0  # 4 bar
    satirlar = kisa_kosu_satirlari("XUSDT", z, h)
    assert len(satirlar) == 2


# --- Gercek veri denetimi ------------------------------------------------------


def _hacim_serileri(semboller: list[str]) -> dict[str, pd.DataFrame]:
    """Onbellekteki 4h dosyalarini tek seferde okur (dosya basina okuma ~5 kat yavas).

    `cache/klines/<sembol>/4h/<ay>.parquet`; sembol dosya yolundan gelir. Ag kullanmaz.
    """
    import pyarrow.dataset as ds

    dosyalar = [str(d) for s in semboller for d in sorted((ONBELLEK / s / config.BAR_4H).glob("*.parquet"))]
    if not dosyalar:
        return {}
    tablo = ds.dataset(dosyalar, format="parquet").to_table(
        columns=["open_time", "quote_volume", "__filename"]).to_pandas()
    tablo["sembol"] = tablo["__filename"].map(lambda y: Path(y).parts[-3])
    return {
        s: g.drop_duplicates("open_time").sort_values("open_time", ignore_index=True)
        for s, g in tablo.groupby("sembol", sort=True)
    }


@pytest.mark.skipif(not (ONBELLEK.exists() and config.UNIVERSE_CSV.exists()),
                    reason="onbellekte mum verisi ya da universe.csv yok")
def test_evrende_ortada_kisa_sifir_kosusu_yok_uyarisi():
    """Evrenin dahil sembollerinde 1-5 barlik ara sifir kosusu varsa uyarir."""
    seriler = _hacim_serileri(universe.dahil_semboller(universe.evren_yukle()))
    if not seriler:
        pytest.skip("onbellekte dahil sembollerin mumu yok")
    satirlar = []
    for sembol, mumlar in seriler.items():
        satirlar += kisa_kosu_satirlari(sembol, pd.DatetimeIndex(mumlar["open_time"]), mumlar["quote_volume"])
    uyar(satirlar)
