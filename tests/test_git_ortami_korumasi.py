"""Git ortami, durum komutu ve pytest oturumu isaretinin korunmasi (performans 2b-0 kapanisi, RESULTS §14.46).

Denetci D-B2 (gerileme) ve sizinti S-38: §14.45'te eklenen adlar `split._KORUNAN_ADLAR`da ve
`tarama_yardimcisi.ONAY_ATLATMA_DESENI`nde degildi; siradan bir atama (`split._DURUM_KOMUTU = ...`) agac temizligi
denetimini dusurebiliyordu. Bu testler siradan atamanin ve silmenin reddedildigini (`monkeypatch.setattr` ayni
`__setattr__` yolundan gecer; geri alma kaydi atamadan once tutuldugu icin burada ayrica sinanmaz) ve adlarin
analiz kodunda taramaya takildigini sinar. Kasitli yollar (`vars(split)`, sozluk ogesine yazma) kayitta kalir (S-37).
"""

from __future__ import annotations

import pytest

from data import split
from tarama_yardimcisi import ONAY_ATLATMA_DESENI, ihlaller

YENI_KORUNAN = ("_GIT_ORTAM_BEYAZ_LISTESI", "_GIT_SABIT_ORTAM", "_DURUM_KOMUTU", "_bag_ortami", "_bag_git",
                "_PYTEST_OTURUMU", "_pytest_oturumu_kur")


@pytest.mark.parametrize("ad", YENI_KORUNAN)
def test_yeni_adlar_korunan_adlarda(ad):
    assert ad in split._KORUNAN_ADLAR


@pytest.mark.parametrize("ad", YENI_KORUNAN)
def test_siradan_atama_reddedilir_ve_deger_degismez(ad):
    onceki = getattr(split, ad)
    with pytest.raises(split.OnayKorumasi):
        setattr(split, ad, None)
    assert getattr(split, ad) is onceki


@pytest.mark.parametrize("ad", YENI_KORUNAN)
def test_silme_reddedilir(ad):
    with pytest.raises(split.OnayKorumasi):
        delattr(split, ad)
    assert hasattr(split, ad)


def test_durum_komutunu_kapatan_atama_agac_denetimini_dusuremez():
    """Gerilemenin somut bicimi: izlenmeyen dosyalari gizleyen bir durum komutu atamasi reddedilir; kesif kaydi ve onay
    ortami ozgun komutu kullanmaya devam eder."""
    ozgun = split._DURUM_KOMUTU
    with pytest.raises(split.OnayKorumasi):
        split._DURUM_KOMUTU = ("status", "--porcelain", "--untracked-files=no")
    with pytest.raises(split.OnayKorumasi):
        split._bag_ortami = lambda: {}
    assert split._DURUM_KOMUTU is ozgun
    assert "--untracked-files=all" in split._DURUM_KOMUTU


@pytest.mark.parametrize("ad", YENI_KORUNAN)
def test_analiz_kodunda_ad_taramaya_takilir(tmp_path, ad):
    (tmp_path / "study").mkdir()
    (tmp_path / "study" / "k.py").write_text(f"from data import split\nx = split.{ad}\n", encoding="utf-8")
    assert ihlaller(ONAY_ATLATMA_DESENI, kok=tmp_path) == ["study/k.py"]


def test_depodaki_analiz_kodu_yeni_adlari_anmaz():
    assert [y for y in ihlaller(ONAY_ATLATMA_DESENI) if y != "config.py"] == []
