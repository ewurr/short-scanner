"""Git hazirlik tanisi ve kimlik eksikligi mesaji (performans 2b-0 kapanisi, RESULTS §14.46; denetci D-B4).

Butun git islemleri `gecici_depo` gecici depolarinda (uzak depo yerel ciplak depodur; aga cikilmaz). Onay kosusu
acilmaz; tani kayda dokunmaz.
"""

from __future__ import annotations

import pytest

from data import split
from onay_yardimcisi import gecici_depo, git
from tarama_yardimcisi import ONAY_ATLATMA_DESENI, ihlaller


def _head(depo) -> str:
    return git(depo, "rev-parse", "HEAD").strip()


def _hazir_depo(tmp_path):
    """`gecici_depo` + yerel kimlik bilgisi yardimcisi (dosya uzaginda cagrilmaz; yalnizca varligi denetlenir)."""
    depo = gecici_depo(tmp_path)
    git(depo, "config", "credential.helper", f"store --file={(tmp_path / 'kimlik').as_posix()}")
    return depo


def test_hazir_depoda_tani_tamam_ve_kayda_dokunmaz(tmp_path, capsys):
    depo = _hazir_depo(tmp_path)
    kayit = (depo / "ONAY_KAYDI.md").read_bytes()
    head = _head(depo)
    assert split.git_hazirlik() == 0
    cikti = capsys.readouterr().out
    assert "user.name: Test" in cikti and "credential.helper: store" in cikti
    assert "fetch: TAMAM" in cikti and "push --dry-run: TAMAM" in cikti
    # E-posta maskelenir.
    assert "test@example.invalid" not in cikti and "t***@example.invalid" in cikti
    assert (depo / "ONAY_KAYDI.md").read_bytes() == kayit and _head(depo) == head
    assert git(depo, "status", "--porcelain").strip() == ""


def test_yerel_kimlik_yoksa_tani_eksik_der(tmp_path, capsys):
    depo = _hazir_depo(tmp_path)
    git(depo, "config", "--unset", "user.email")
    assert split.git_hazirlik() == 1
    cikti = capsys.readouterr().out
    assert "user.email: YOK" in cikti and "git-hazirlik: EKSIK" in cikti


def test_uzak_depo_yoksa_tani_basarisiz(tmp_path, capsys):
    depo = _hazir_depo(tmp_path)
    git(depo, "remote", "set-url", "origin", str(tmp_path / "olmayan.git"))
    assert split.git_hazirlik() == 1
    cikti = capsys.readouterr().out
    assert "fetch: BASARISIZ" in cikti and "push --dry-run: BASARISIZ" in cikti


# `user.name` eksikse git 2.41 Windows'ta isletim sistemi kullanici adina duser ve commit yine yapilir; commit'i dusuren
# eksik `user.email`dir (bu makinede sinandi, RESULTS §14.46). Tani (`git_hazirlik`) ikisini de ayrica denetler.
@pytest.mark.parametrize("eksik", ["user.email"])
def test_kimlik_eksikse_commit_hatasi_bunu_acikca_soyler(tmp_path, eksik):
    depo = gecici_depo(tmp_path)
    git(depo, "config", "--unset", eksik)
    with (depo / "ONAY_KAYDI.md").open("a", encoding="utf-8", newline="") as d:
        d.write("| deneme |\n")
    with pytest.raises(split.OnayKaydiCommitsiz) as hata:
        split._kaydi_commit_et("deneme")
    mesaj = str(hata.value)
    assert "Deponun yerel yapilandirmasinda" in mesaj and eksik in mesaj and "yok" in mesaj


def test_yardimci_yoksa_tani_eksik_der(tmp_path, capsys):
    gecici_depo(tmp_path)
    assert split.git_hazirlik() == 1
    assert "credential.helper: YOK" in capsys.readouterr().out


def test_eposta_maskesi():
    assert split._eposta_maskele("abc@ornek.org") == "a***@ornek.org"
    assert split._eposta_maskele("adres_degil") == "***"


@pytest.mark.parametrize("icerik", ["from data import split\nsplit.git_hazirlik()\n",
                                    "import subprocess\nsubprocess.run(['python', '-m', 'data.split', 'git-hazirlik'])\n",
                                    "from data import split\nsplit._git_tani('push')\n"])
def test_analiz_kodunda_tani_taramaya_takilir(tmp_path, icerik):
    (tmp_path / "study").mkdir()
    (tmp_path / "study" / "k.py").write_text(icerik, encoding="utf-8")
    assert ihlaller(ONAY_ATLATMA_DESENI, kok=tmp_path) == ["study/k.py"]


@pytest.mark.parametrize("ad", ["git_hazirlik", "_git_tani", "_eposta_maskele"])
def test_tani_adlari_korunur(ad):
    with pytest.raises(split.OnayKorumasi):
        setattr(split, ad, None)
