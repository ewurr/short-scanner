"""Olay sayisinin kapsami: analize giren olaylar (on-kayit §8 madde 2, rev.13 (h)).

On-kayit §8 madde 2 (rev.13): "Aday yapilandirmalar: olay sayisi >= 150 olanlar. Buradaki ve
§9'daki olay sayisi, ANALIZE GIREN olaylarin sayisidir: her iki kontrol havuzu da bos oldugu icin
analize girmeyen olaylar (§6) sayilmaz. Gerekce: esikler istatistik gucunu guvenceye almak icin
vardir ve guc yalnizca teste giren olaylardan gelir; olusmus ama analize girmeyen olayi saymak
gucu oldugundan fazla gosterirdi. Her iki sayi da raporlanir (§8 madde 1)."

§6 rev.11: "Bir olayin her iki havuzu da bossa o olay analize girmez; en az bir kontrolu olan olay
kalir." Olcut TEK bir yuklemdir (`ornekleme.olay_analize_girer`) ve iki sayi yalnizca ondan
uretilir (`ornekleme.olay_sayilari`).

Esiklerin KARARA baglanmasi F2 (aday secimi) ve F3 (yeterli guc hukmu) isidir ve bu turda
yazilmadi (faz siniri; RESULTS'taki "F2'nin karsilamasi gereken on-kayit gereksinimleri"). Veri
katmani yuklemi, iki sayiyi ve esik dogrulamasini uretir.

Aga cikmaz; getiri hesaplanmaz.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import ornekleme
from ornekleme_yardimcisi import k1_adaylari_kur, k2_adaylari_kur, ornekle

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
TB = T("2025-03-10 04:00")


def _havuz(n):
    """n kontrollu bir havuz (n = 0 ise bos)."""
    return ornekle(k1_adaylari_kur([T("2025-03-01") + i * H4 for i in range(n)]))


# --- 1. Esikler on-kayit degeri --------------------------------------------------------------


def test_esikler_on_kayit_degeri_ve_degistirilemez():
    assert config.ADAY_OLAY_ESIGI == 150      # §8 madde 2
    assert config.ONAY_OLAY_ESIGI == 100      # §9 madde 6
    for ad in ("ADAY_OLAY_ESIGI", "ONAY_OLAY_ESIGI"):
        with pytest.raises(config.SabitDegistirilemez):
            setattr(config, ad, 1)


@pytest.mark.parametrize("asama,dogru", [("F2", 150), ("F3", 100)])
def test_olay_esigi_dogrula_serbest_deger_kabul_etmez(asama, dogru):
    assert ornekleme.olay_esigi_dogrula(dogru, asama=asama) == dogru
    for yanlis in (1, 99, 100 if asama == "F2" else 150, 149, 151, 0, 1000, True):
        if yanlis == dogru:
            continue
        with pytest.raises(ValueError, match="on-kayit"):
            ornekleme.olay_esigi_dogrula(yanlis, asama=asama)


@pytest.mark.parametrize("asama", ["F1", "F4", "", None, 2])
def test_bilinmeyen_asama_reddedilir(asama):
    with pytest.raises(ValueError, match="asama"):
        ornekleme.olay_esigi_dogrula(150, asama=asama)


# --- 2. Tek yuklem ---------------------------------------------------------------------------


def test_yuklem_en_az_bir_kontrolu_olan_olay():
    """§6 rev.11: iki havuzu da bos olan olay analize girmez."""
    bos, dolu = _havuz(0), _havuz(3)
    assert ornekleme.olay_analize_girer(bos, bos) is False
    assert ornekleme.olay_analize_girer(dolu, bos) is True
    assert ornekleme.olay_analize_girer(bos, dolu) is True
    assert ornekleme.olay_analize_girer(dolu, dolu) is True


def test_iki_sayi_yalnizca_yuklemden_uretilir():
    """Olusmus olay sayisi cift sayisi; analize giren sayi yuklemi saglayanlar."""
    bos, bir, on = _havuz(0), _havuz(1), _havuz(10)
    ciftler = [(bos, bos), (bir, bos), (bos, on), (on, on), (bos, bos), (bir, bir)]
    sayilar = ornekleme.olay_sayilari(ciftler)
    assert sayilar.olusmus == 6
    assert sayilar.analize_giren == 4
    assert sayilar.analize_giren == sum(1 for k1, k2 in ciftler if ornekleme.olay_analize_girer(k1, k2))


def test_bos_kume_sifir_sifir():
    sayilar = ornekleme.olay_sayilari([])
    assert (sayilar.olusmus, sayilar.analize_giren) == (0, 0)


def test_hepsi_bos_havuzlu_olaylar_olusmus_sayilir_analize_girmez():
    """On-kayit §8 madde 1 (rev.13): "Analize giren olay sayisi sifir olan bir yapilandirma da
    raporlanir: olay sayilari sifir yazilir ... ve sifir sayilmaz." Iki sayi AYRIDIR."""
    bos = _havuz(0)
    sayilar = ornekleme.olay_sayilari([(bos, bos)] * 7)
    assert sayilar.olusmus == 7 and sayilar.analize_giren == 0


# --- 3. Esik ANALIZE GIREN sayiya uygulanir --------------------------------------------------


def test_esik_analize_giren_sayiya_uygulanir():
    """Rev.13'un karari: olusmus olay sayisi esigi gecse bile analize giren sayi gecmiyorsa
    yapilandirma aday DEGILDIR."""
    bos, dolu = _havuz(0), _havuz(2)
    ciftler = [(dolu, bos)] * 149 + [(bos, bos)] * 10
    sayilar = ornekleme.olay_sayilari(ciftler)
    assert sayilar.olusmus == 159 and sayilar.analize_giren == 149
    assert not sayilar.esigi_gecer(config.ADAY_OLAY_ESIGI)       # 149 < 150
    assert sayilar.esigi_gecer(config.ONAY_OLAY_ESIGI)           # 149 >= 100
    # Sinir durumu: tam 150 analize giren olay esigi GECER (olcut ">=").
    tam = ornekleme.olay_sayilari([(dolu, bos)] * 150 + [(bos, bos)] * 10)
    assert tam.esigi_gecer(config.ADAY_OLAY_ESIGI) and tam.olusmus == 160


@pytest.mark.parametrize("n,esik,gecer", [(99, 100, False), (100, 100, True), (101, 100, True),
                                          (149, 150, False), (150, 150, True), (0, 100, False)])
def test_esik_kenarlari(n, esik, gecer):
    assert ornekleme.OlaySayilari(olusmus=n + 5, analize_giren=n).esigi_gecer(esik) is gecer


# --- 4. Girdi sozlesmesi ---------------------------------------------------------------------


@pytest.mark.parametrize("bozuk", [[(1, 2)], [None], [("a",)], [(None, None)], ["cift_degil"]])
def test_havuz_cifti_olmayan_girdi_reddedilir(bozuk):
    with pytest.raises(TypeError, match="KontrolHavuzu"):
        ornekleme.olay_sayilari(bozuk)


def test_uc_elemanli_cift_reddedilir():
    bos = _havuz(0)
    with pytest.raises(TypeError):
        ornekleme.olay_sayilari([(bos, bos, bos)])
