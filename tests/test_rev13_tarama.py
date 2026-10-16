"""Olay uretimi `data.dizi`den gecmek zorunda: calisma ani + kaynak taramasi (on-kayit §4 rev.12).

On-kayit §4 "Olayin kumede olusma olcutu" (rev.12): "Tek karar noktasinin onayi, bir olayin
olusmasi icin gereklidir ama YETERLI DEGILDIR: §5'teki dizi kurallari (bekleme suresi, H1'de tek
izleme, H3'te ilk gun) da saglanmalidir. Olay kumesi yalnizca iki kosulun birlikte saglandigi
barlardan olusur; dizi kurallarindan gecmemis bir onay olay DEGILDIR ve hicbir hesaba, hicbir
kontrol olcutune girmez."

Iki savunma vardir ve bu dosya ikisini de sinar:

1. BIRINCIL, CALISMA ANINDA. "Olay" tipi (`dizi.Olay`) imzalidir ve yalnizca `dizi.olay_dizisi`
   uretir (`dizi.olay_dogrula`). Kapinin onayi tek basina bir olay nesnesi KURAMAZ, dolayisiyla
   F2'nin olay kumesine (ve "ayni yapilandirmanin olusmus olaylari" tanimina dayanan K1/K2
   olcutlerine) dizi kurallarindan gecmemis bir bar giremez. Ters yon `dizi._olay_dogrula`dadir
   (tests/test_rev13_dizi_kapisi.py): dizi de kapidan gecmemis bir onayi olay saymaz.

2. IKINCIL, KAYNAK TARAMASI. Analiz kodu (`events/`, `study/`, F1 disindaki `analysis/`) olay
   nesnesini elle kurmaz (`DIZI_ATLATMA_DESENI`) ve kapiya "olay" rolunu veren bir dosya ayni
   dosyada `olay_dizisi`ni de anmak zorundadir (`olay_rolu_ihlalleri`).

NEDEN IKI SAVUNMA, NEDEN BOYLE. On-kayit metnine en yakin ucuncu bir okuma, kapinin dizi
durumunu ZORUNLU GIRDI olarak almasiydi (`olay_karari(..., dizi_durumu=...)`). O okuma bu turda
uygulanmadi, cunku olay rolunde kapiyi dogrudan cagiran mevcut testlerin tamami -- bekleme, tek
izleme ya da ilk gun kurallariyla ilgisi OLMAYAN, kume siniri / ufuk bagi / funding tamligi /
uygunluk / MAE gibi adimlari sinayanlar dahil -- yalnizca yeni bir zorunlu argumani vermedikleri
icin dusecekti; bu turun kurali ise rev.12/rev.13'un acikca degistirmedigi bir davranis yuzunden
beklentisi degisen testi degistirmemektir. Secilen yol, aradaki garantiyi NESNE duzeyinde kurar:
olay tipi yalnizca diziden cikar, yani "kapinin onayi yeterli degildir" hukmu calisma aninda da
gecerlidir. Fark, kapinin TEK BASINA cagrilabilmesidir -- ama cagrinin ciktisi bir ONAYDIR, olay
degildir ve olay kumesine ancak diziden gecerek girer.

Aga cikmaz.
"""

from __future__ import annotations

import dataclasses

import pandas as pd
import pytest

import config
from data import dizi, pozisyon
from sinyal_yardimcisi import yapilandirma
from tarama_yardimcisi import (DIZI_ATLATMA_DESENI, IZINLI_ALTLAR, OLAY_ROLU_DESENI, ihlaller,
                               olay_rolu_ihlalleri)

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
BARLAR = pd.date_range(T("2025-03-01 00:00"), periods=10, freq="4h")
Y2 = yapilandirma("H2")


DIZI_KIMLIGI = dict(sembol="TESTONAYUSDT", kume="KESIF", donem_no=0)

def _dizi_sonucu():
    return dizi.olay_dizisi(
        "H2", Y2, BARLAR[:3], config.BAR_4H, birincil_ufuk=config.BIRINCIL_UFUK[config.BAR_4H],
        kosul=lambda t, capa: True,
        karar=lambda t, capa: pozisyon._test_onayi(hipotez="H2", yapilandirma=Y2, t=t, capa=capa), **DIZI_KIMLIGI)


# --- 1. Calisma ani: olay tipi yalnizca diziden cikar ----------------------------------------


def test_dizinin_urettigi_olay_dogrulanir_olumlu_kontrol():
    sonuc = _dizi_sonucu()
    assert len(sonuc.olaylar) == 1
    dizi.olay_dogrula(sonuc.olaylar[0])


def test_elle_kurulan_olay_reddedilir():
    """Kapinin onayi tek basina olay DEGILDIR: `Olay(...)` elle kurulamaz."""
    onay = pozisyon._test_onayi(hipotez="H2", yapilandirma=Y2, t=BARLAR[0])
    pozisyon.onay_dogrula(onay)                      # onay gecerli ...
    with pytest.raises(ValueError, match="elle kurulmus"):
        dizi.olay_dogrula(dizi.Olay(BARLAR[0], None, onay))   # ... ama olay degil


def test_degistirilmis_olay_reddedilir():
    olay = _dizi_sonucu().olaylar[0]
    for sahte in (dataclasses.replace(olay, zaman=BARLAR[5]),
                  dataclasses.replace(olay, capa=BARLAR[1]),
                  dataclasses.replace(olay, pozisyon="baska")):
        with pytest.raises(ValueError):
            dizi.olay_dogrula(sahte)


@pytest.mark.parametrize("nesne", [None, "olay", 1, ("olay", 1, 2)])
def test_olay_olmayan_nesne_reddedilir(nesne):
    with pytest.raises(TypeError, match="Olay gerekir"):
        dizi.olay_dogrula(nesne)


def test_kapinin_onayi_olay_tipinde_degildir():
    """Kapi tek basina cagrilabilir, ama ciktisi bir ONAYDIR: olay kumesine ancak diziden girer."""
    onay = pozisyon._test_onayi(hipotez="H2", yapilandirma=Y2, t=BARLAR[0])
    assert not isinstance(onay, dizi.Olay)
    with pytest.raises(TypeError):
        dizi.olay_dogrula(onay)


# --- 2. Kaynak taramasi (ikincil savunma) ----------------------------------------------------


def test_analiz_kodunda_olay_nesnesi_elle_kurulmuyor():
    assert ihlaller(DIZI_ATLATMA_DESENI) == []


def test_analiz_kodunda_olay_rolu_dizi_olmadan_kullanilmiyor():
    assert olay_rolu_ihlalleri() == []


def test_tarama_elle_kurulan_olayi_yakalar(tmp_path):
    """Tarama gercekten yakaliyor mu? Ekilmis ihlaller bulunmali, temiz dosya bulunmamali."""
    (tmp_path / "study").mkdir()
    (tmp_path / "study" / "kotu1.py").write_text("from data import dizi\nx = dizi.Olay(t, None, p)\n",
                                                 encoding="utf-8")
    (tmp_path / "study" / "kotu2.py").write_text("from data.dizi import Olay\ny = Olay(t, None, p)\n",
                                                 encoding="utf-8")
    (tmp_path / "study" / "kotu3.py").write_text("z = dizi._OLAY_GIZLI\n", encoding="utf-8")
    (tmp_path / "study" / "iyi.py").write_text("sonuc = dizi.olay_dizisi(..., **DIZI_KIMLIGI)\nolaylar = sonuc.olaylar\n",
                                               encoding="utf-8")
    bulunan = ihlaller(DIZI_ATLATMA_DESENI, kok=tmp_path, izinli_altlar=IZINLI_ALTLAR)
    assert bulunan == ["study/kotu1.py", "study/kotu2.py", "study/kotu3.py"]


def test_tarama_dizisiz_olay_rolunu_yakalar(tmp_path):
    (tmp_path / "study").mkdir()
    (tmp_path / "study" / "kotu.py").write_text('p = olay_karari(t, rol="olay", capa=None)\n',
                                                encoding="utf-8")
    (tmp_path / "study" / "iyi.py").write_text(
        'karar = lambda t, c: olay_karari(t, rol="olay", capa=c)\n'
        'sonuc = dizi.olay_dizisi(h, y, zamanlar, bar, karar=karar, **DIZI_KIMLIGI)\n', encoding="utf-8")
    assert olay_rolu_ihlalleri(kok=tmp_path) == ["study/kotu.py"]
    assert OLAY_ROLU_DESENI  # desen bos olmasin


def test_izinli_dizinler_muaf_bilinen_acik(tmp_path):
    """BILINEN ACIK: `data/`, `tests/`, `analysis/00_veri_denetimi/` ve `.claude/` muaftir
    (`IZINLI_ALTLAR`). F1 olcum betikleri olay uretmez, ama muafiyet desenleri orada da gormez;
    bu yuzden tarama tek savunma degildir (yukaridaki calisma ani denetimleri birincildir)."""
    for alt in ("data", "tests", "analysis/00_veri_denetimi", ".claude"):
        yol = tmp_path / alt
        yol.mkdir(parents=True)
        (yol / "x.py").write_text('dizi.Olay(t, None, p)\nrol="olay"\n', encoding="utf-8")
    assert ihlaller(DIZI_ATLATMA_DESENI, kok=tmp_path) == []
    assert olay_rolu_ihlalleri(kok=tmp_path) == []


def test_ipynb_bilinen_acik(tmp_path):
    """BILINEN ACIK: varsayilan uzanti yalnizca `.py`; bir `.ipynb` defteri taranmaz."""
    (tmp_path / "study").mkdir()
    (tmp_path / "study" / "defter.ipynb").write_text('"dizi.Olay(t, None, p)"', encoding="utf-8")
    assert ihlaller(DIZI_ATLATMA_DESENI, kok=tmp_path) == []
    # Acikca istenirse yakalanir (acigin kaynagi uzanti listesi, desen degil).
    assert ihlaller(DIZI_ATLATMA_DESENI, kok=tmp_path, uzantilar=(".ipynb",)) == ["study/defter.ipynb"]
