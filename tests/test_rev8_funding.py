"""On-kayit §4 rev.8 "Funding odemesinin sinirlari", "Donem sonu istisnasi",
"Funding araligi gecisleri"; §2 "Funding'i bulunmayan donemler", "Gercek islem
sonrasi funding kayitlari". Aga cikmaz; getiri hesaplanmaz (sentetik oranlar).
"""

from __future__ import annotations

import ast
import inspect
import textwrap

import numpy as np
import pandas as pd
import pytest

import config
from data import funding, pencere
from data.donem import Donem

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
DK = pd.Timedelta(minutes=1)
NS = pd.Timedelta(1, "ns")


def _kayit(zamanlar, aralik=8.0, oran=1e-4):
    z = pd.DatetimeIndex(zamanlar)
    return pd.DataFrame({"odeme_zamani": z, "aralik_saat": aralik, "oran": oran, "oran_8h": oran})


def _plan(t, ufuk, bas, b, bar=config.BAR_4H, z=None):
    if z is None:
        z = pd.date_range(bas, b, freq="4h")
    return pencere.pozisyon_plani(z, t, ufuk, bar, birincil_ufuk=18, kume_baslangic=None, kume_bitis=None,
                                  donem_baslangic=bas, donem_bitis=b)


BAS, B = T("2025-01-01 00:00"), T("2025-01-20 08:00")


# --- Giris anindaki haric, cikis anindaki dahil (zaman toleransi kenarlari) ---------


@pytest.mark.parametrize("fark,dahil", [(DK - NS, False), (DK, True), (DK + NS, True)])
def test_giris_anindaki_odeme_haric(fark, dahil):
    """Girisle ayni an sayilan odeme haric; tam 1 dk sonrasi dahil."""
    plan = _plan(T("2025-01-05 04:00"), 6, BAS, B)  # giris 08:00, cikis ani 2025-01-06 08:00
    zam = [plan.giris - pd.Timedelta(hours=8)] + [plan.giris + fark + i * pd.Timedelta(hours=8) for i in range(4)]
    fr = _kayit(zam)
    fr.loc[1, "oran"] = 9e-4
    deger = funding.pozisyon_fundingi(fr, plan)
    if dahil:
        assert deger == pytest.approx(9e-4 + 2e-4)
    else:
        # pencerede 16:00, 00:00 ve cikis aniyla ayni an sayilan 08:00 kalir; ilk odeme
        # giristen 8 saat + fark sonra (fark < 1 dk): aralik asilmaz -> tam
        assert deger == pytest.approx(3e-4)


@pytest.mark.parametrize("fark,dahil", [(DK - NS, True), (DK, False)])
def test_cikis_anindaki_odeme_dahil(fark, dahil):
    plan = _plan(T("2025-01-05 04:00"), 6, BAS, B)  # cikis ani 2025-01-06 08:00
    an = plan.cikis_ani
    zam = [an - pd.Timedelta(hours=16), an - pd.Timedelta(hours=8), an + fark]
    fr = _kayit(zam)
    fr.loc[2, "oran"] = 9e-4
    deger = funding.pozisyon_fundingi(fr, plan)
    if dahil:
        assert deger == pytest.approx(2e-4 + 9e-4)
    else:
        # cikis anindan sonraki odeme alinmaz; son odeme (an - 8h) + 8h = an: siradaki
        # odeme cikis aniyla AYNI an, pencerede olmaliydi -> tam degil
        assert pd.isna(deger)


# --- Donem sonu istisnasi -------------------------------------------------------------


def test_donem_sonu_penceresi_b_de_kapanir_k_haric():
    plan = _plan(T("2025-01-18 08:00"), 18, BAS, B)
    assert plan.donem_sonu_mu and plan.cikis_ani == B + H4
    assert funding.funding_penceresi_sonu(plan) == B
    fr = _kayit(pd.date_range(T("2025-01-18 00:00"), B + H4, freq="4h"), aralik=4.0)
    fr.loc[fr["odeme_zamani"] == B + H4, "oran"] = 9.0  # K'daki odeme: hesaba girmez
    fr.loc[fr["odeme_zamani"] == B, "oran"] = 5e-4  # B'deki odeme: dahil
    beklenen = 5e-4 + 1e-4 * ((B - T("2025-01-18 12:00")) / H4 - 1)  # 16:00 .. B-4h (giris 12:00 haric)
    assert funding.pozisyon_fundingi(fr, plan) == pytest.approx(beklenen)


def test_donem_sonu_tamligi_son_odemeyi_b_ye_gore_arar():
    plan = _plan(T("2025-01-18 08:00"), 18, BAS, B)
    # 4 saatlik ritim B'de bitiyor: siradaki odeme B + 4h > B -> tam
    assert funding.pozisyon_funding_tam_mi(_kayit(pd.date_range(T("2025-01-18 00:00"), B, freq="4h"), 4.0), plan)
    # 4 saatlik ritim B - 4h'te bitiyor: B'deki odeme eksik -> tam degil
    assert not funding.pozisyon_funding_tam_mi(
        _kayit(pd.date_range(T("2025-01-18 00:00"), B - H4, freq="4h"), 4.0), plan)
    # 8 saatlik ritim B - 4h'te bitiyor: siradaki B + 4h -> tam
    assert funding.pozisyon_funding_tam_mi(
        _kayit(pd.date_range(T("2025-01-18 00:00") - H4, B - H4, freq="8h"), 8.0), plan)


# --- Baslangic boslugu ve kaydi olmayan pencere ---------------------------------------


@pytest.mark.parametrize("fazla,tam", [(pd.Timedelta(0), True), (DK - NS, True), (DK, False)])
def test_baslangic_boslugu(fazla, tam):
    """Giris ile penceredeki ilk odeme arasindaki bosluk ilk kaydin araligini ve
    toleransi asarsa eksik."""
    plan = _plan(T("2025-01-05 04:00"), 18, BAS, B)  # giris 08:00
    ilk = plan.giris + pd.Timedelta(hours=8) + fazla
    fr = _kayit([ilk + i * pd.Timedelta(hours=8) for i in range(12)])
    assert funding.pozisyon_funding_tam_mi(fr, plan) is tam


def test_baslangic_boslugu_ilk_kaydin_araligini_kullanir():
    """Gecis kaydi kisa araligi tasiyorsa (8 -> 2) kural tetiklenir (rev.8 metni)."""
    plan = _plan(T("2025-01-05 12:00"), 6, BAS, B)  # giris 16:00
    fr = _kayit([T("2025-01-05 16:00"), T("2025-01-05 20:00")] + list(
        pd.date_range(T("2025-01-05 22:00"), T("2025-01-07"), freq="2h")))
    fr["aralik_saat"] = [8.0] + [2.0] * (len(fr) - 1)
    ayrinti = funding.funding_tamlik_ayrintisi(fr, [plan.giris], [funding.funding_penceresi_sonu(plan)])
    assert not ayrinti["baslangic_tam"].iloc[0] and ayrinti["ic_tam"].iloc[0] and ayrinti["son_tam"].iloc[0]


def test_penceresinde_kayit_yoksa_tam_degil():
    plan = _plan(T("2025-01-05 04:00"), 1, BAS, B)  # 08:00 -> 12:00
    fr = _kayit([T("2025-01-05 00:00"), T("2025-01-05 16:00")])
    assert not funding.pozisyon_funding_tam_mi(fr, plan)
    assert pd.isna(funding.pozisyon_fundingi(fr, plan))


@pytest.mark.parametrize("kayitlar", [
    [T("2025-01-04 00:00")],                                     # tek kayit, giristen once
    [T("2025-01-04 00:00"), T("2025-01-05 00:00")],              # butun kayitlar giristen once
    [T("2025-01-04 00:00"), T("2025-01-05 08:00")],              # son kayit giris aninda (haric)
])
def test_giris_son_kayittan_sonraysa_tam_degil_cokmez(kayitlar):
    """Pencerede kayit yok ve giris butun kayitlardan sonra (lo = hi = kayit sayisi):
    tamlik False doner, indeks hatasi vermez. Vektorel yolda karisik girislerle de."""
    plan = _plan(T("2025-01-05 04:00"), 1, BAS, B)  # giris 08:00
    fr = _kayit(kayitlar)
    assert not funding.pozisyon_funding_tam_mi(fr, plan)
    assert pd.isna(funding.pozisyon_fundingi(fr, plan))
    erken = _plan(T("2025-01-03 20:00"), 1, BAS, B)  # giris 01-04 00:00, kayit anda: haric
    ayrinti = funding.funding_tamlik_ayrintisi(
        fr, [erken.giris, plan.giris], [funding.funding_penceresi_sonu(erken), funding.funding_penceresi_sonu(plan)])
    assert not ayrinti["kayit_var"].iloc[1] and not ayrinti["tam"].iloc[1]


# --- Donem pencereleri -------------------------------------------------------------------

D = Donem(BAS, B, 100, 100)


@pytest.mark.parametrize("an,beklenen", [
    (BAS, True), (BAS - DK + NS, True), (BAS - DK, False),
    (B, True), (B + DK - NS, True), (B + DK, False), (B + H4, False),
])
def test_donemde_funding_var_bas_ile_b_arasi(an, beklenen):
    assert funding.donemde_funding_var(_kayit([an]), D, config.BAR_4H) is beklenen


def test_donem_sonrasi_kayitlari_at_k_den_sonrasini_atar():
    zam = [B, B + 2 * pd.Timedelta(hours=1), B + H4, B + H4 + DK - NS, B + H4 + DK, B + pd.Timedelta(hours=12)]
    kalan = funding.donem_sonrasi_kayitlari_at(_kayit(zam), [D], config.BAR_4H)
    assert list(kalan["odeme_zamani"]) == zam[:4]


# --- Vektorel ve tekil yol ayni ------------------------------------------------------------


def test_vektorel_ayrinti_tekil_sonucla_ayni():
    rng = np.random.default_rng(config.TOHUM)
    z = pd.date_range(BAS, B, freq="4h")
    zamanlar = list(pd.date_range(BAS, B + H4, freq="4h"))
    silinecek = set(rng.choice(len(zamanlar), size=12, replace=False).tolist())
    fr = _kayit([x for i, x in enumerate(zamanlar) if i not in silinecek], 4.0)
    planlar = []
    for t in z[:-2][::3]:
        for ufuk in (1, 6, 18):
            try:
                planlar.append(_plan(t, ufuk, BAS, B, z=z))
            except pencere.OlayOlusmaz:
                pass
    ayrinti = funding.funding_tamlik_ayrintisi(
        fr, [p.giris for p in planlar], [funding.funding_penceresi_sonu(p) for p in planlar])
    tekil = [funding.pozisyon_funding_tam_mi(fr, p) for p in planlar]
    assert ayrinti["tam"].tolist() == tekil
    assert 0 < sum(tekil) < len(tekil)


def test_tamlik_kodu_oran_okumaz():
    """Oran sutununa yalnizca toplama icin (`pozisyon_fundingi`) erisilir; tamlik kodu okumaz."""
    for fonk in (funding.funding_tamlik_ayrintisi, funding.pozisyon_funding_tam_mi, funding.funding_penceresi_sonu,
                 funding.donemde_funding_var, funding.donem_sonrasi_kayitlari_at):
        agac = ast.parse(textwrap.dedent(inspect.getsource(fonk)))
        belge = ast.get_docstring(agac.body[0])
        sabitler = {d.value for d in ast.walk(agac) if isinstance(d, ast.Constant) and isinstance(d.value, str)
                    and d.value != belge}
        assert not (sabitler & {"oran", "oran_8h"}), fonk.__name__
