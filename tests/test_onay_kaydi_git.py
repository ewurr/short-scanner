"""Onay kaydi ikinci tur: kayit git'e bagli, korunan adlar, sonuc ve hata (denetci OK D-B1, OK D-B2, OK D-C1;
sizinti testcisi O bulgulari).

OK D-B1 testleri gecici bir GERCEK git deposunda kosar (`onay_yardimcisi.gecici_depo`): temiz agac, HEAD,
`ls-files`, gecmis ve commit gercek git komutlariyla yapilir. Commit hatasi deponun `pre-commit` kancasiyla
uretilir (`.git/engel` dosyasi varken commit reddedilir). Gercek `ONAY_KAYDI.md` dosyasina yazilmaz.
"""

from __future__ import annotations

import types

import pandas as pd
import pytest

import config
from data import split
from onay_yardimcisi import gecici_depo, gecici_kayit, git, kosu, uzak_depo
from tarama_yardimcisi import ONAY_ATLATMA_DESENI, ihlaller

COMMIT = "0123456789abcdef" * 2 + "01234567"
B_SEMBOLU = "BTCUSDT"  # gercek split.csv'de B grubu


@pytest.fixture
def depo(tmp_path):
    return gecici_depo(tmp_path)


def _engelle(depo):
    """Deponun sonraki commit'lerini `pre-commit` kancasiyla reddettirir (`.git/engel` varken)."""
    kanca = depo / ".git" / "hooks" / "pre-commit"
    kanca.write_text("#!/bin/sh\nif [ -f .git/engel ]; then exit 1; fi\nexit 0\n", encoding="utf-8", newline="\n")
    kanca.chmod(0o755)
    (depo / ".git" / "engel").write_text("", encoding="utf-8")


def _engeli_kaldir(depo):
    (depo / ".git" / "engel").unlink()


def _kayit(depo) -> str:
    return (depo / "ONAY_KAYDI.md").read_text(encoding="utf-8")


def _head_kaydi(depo) -> str:
    return git(depo, "show", "HEAD:ONAY_KAYDI.md")


def _durumlar(metin) -> list[tuple[str, str, str]]:
    return [(s["hipotez"], s["kume"], s["durum"]) for s in split.kayit_satirlari(metin)]


# --- OK D-B1: kayit satirlari kosunun kendisi tarafindan commit edilir -------------------------------------


def test_kosu_iki_satiri_da_commit_eder_ve_agac_temiz_kalir(depo):
    ilk = git(depo, "rev-parse", "HEAD").strip()
    with kosu("H2", "C1") as k:
        # Blok icinde BASLADI satiri zaten commit edilmis: `git checkout .` onu silemez.
        assert _durumlar(_head_kaydi(depo)) == [("H2", "C1", "BASLADI")]
        assert git(depo, "status", "--porcelain") == ""
        assert split.kume_erisimi(B_SEMBOLU, "C1", onay=True)[0]
    assert _durumlar(_head_kaydi(depo)) == [("H2", "C1", "BASLADI"), ("H2", "C1", "BITTI")]
    assert git(depo, "status", "--porcelain") == ""
    mesajlar = git(depo, "log", "--format=%s", f"{ilk}..HEAD").splitlines()
    assert mesajlar == [f"ONAY_KAYDI: H2 C1 BITTI (kosu={k.kimlik})", f"ONAY_KAYDI: H2 C1 BASLADI (kosu={k.kimlik})"]
    # Kayda yazilan commit, kosuyu acan kodun commit'i (kayit commit'lerinden once).
    assert {s["commit"] for s in split.kayit_satirlari(_kayit(depo))} == {ilk}
    # Commit'ler yalnizca kayit dosyasini icerir.
    assert git(depo, "diff", "--name-only", ilk, "HEAD").split() == ["ONAY_KAYDI.md"]


def test_yalnizca_kayit_commit_edilir_kosunun_ciktilari_edilmez(depo):
    with kosu("H1", "C2"):
        (depo / "analysis" / "cikti.csv").write_text("a\n1\n", encoding="utf-8")
    assert git(depo, "status", "--porcelain").splitlines() == ["?? analysis/cikti.csv"]
    assert "cikti.csv" not in git(depo, "log", "--name-only", "--format=")


@pytest.mark.parametrize("silme", [["checkout", "HEAD", "--", "."], ["reset", "--hard", "-q"], ["stash", "-u", "-q"]],
                         ids=["checkout-head", "reset-hard", "stash"])
def test_commit_edilmeden_silinen_satirlar_cifti_harcanmis_birakir(depo, silme):
    """Bitis satiri commit edilemedi (kanca); satirlar calisma agacindan kazayla silindi. BASLADI satiri kosu
    acilirken commit edildigi icin cift hala harcanmis. (Commit edilemeyen satir `git add` ile index'te kalir;
    duz `git checkout -- .` onu silmez, bu yuzden HEAD'den geri alma denenir.)"""
    with pytest.raises(split.OnayKaydiCommitsiz):
        with split.onay_kosusu("H2", "C1") as k:
            k.sonuc_bildir("KALDI")
            _engelle(depo)
    assert _durumlar(_kayit(depo)) == [("H2", "C1", "BASLADI"), ("H2", "C1", "BITTI")]
    assert _durumlar(_head_kaydi(depo)) == [("H2", "C1", "BASLADI")]  # BITTI commit edilmedi

    git(depo, *silme)
    _engeli_kaldir(depo)
    assert "BITTI" not in _kayit(depo) and git(depo, "status", "--porcelain") == ""
    with pytest.raises(split.OnayTekrari):
        with split.onay_kosusu("H2", "C1"):
            pytest.fail("commit edilmis BASLADI cifti harcamis olmali")


def test_calisma_agacindan_silinen_commitli_satirlar_cifti_harcanmis_birakir(depo):
    """Kayit tamamen bos bir dosyayla degistirilip bu degisiklik commit edilse bile cift gecmisten harcanmis."""
    with kosu("H3", "C2"):
        pass
    (depo / "ONAY_KAYDI.md").write_text("bos\n", encoding="utf-8")
    git(depo, "commit", "-q", "-am", "kayit silindi")
    assert split.kayit_satirlari(_kayit(depo)) == [] and split.kayit_satirlari(_head_kaydi(depo)) == []
    with pytest.raises(split.OnayTekrari):
        with split.onay_kosusu("H3", "C2"):
            pytest.fail("gecmiste kayda eklenmis satir cifti harcamis olmali")


def test_reset_ile_geri_alinan_commitler_reflogdan_sayilir(depo):
    ilk = git(depo, "rev-parse", "HEAD").strip()
    with kosu("H1", "C1"):
        pass
    git(depo, "reset", "--hard", "-q", ilk)  # kayit commit'leri dalda artik yok
    assert split.kayit_satirlari(_kayit(depo)) == []
    with pytest.raises(split.OnayTekrari):
        with split.onay_kosusu("H1", "C1"):
            pytest.fail("reflog'daki commit cifti harcamis olmali")


def test_itilmis_cift_yerel_gecmis_silinse_de_harcanmis(depo):
    """Kapanis turu: itilmis bir cift, yerel gecmis (dal, reflog, nesneler ve uzak izleme referansi) silinse de
    harcanmis sayilir; kosu `origin/main`'i yeniden alir. (Ikinci tur surumu bu adimlarla cifti geri getiriyordu.)"""
    ilk = git(depo, "rev-parse", "HEAD").strip()
    with kosu("H1", "C1"):
        pass
    assert _durumlar(git(depo, "show", "origin/main:ONAY_KAYDI.md")) == [("H1", "C1", "BASLADI"), ("H1", "C1", "BITTI")]
    assert _durumlar(git(uzak_depo(depo), "show", "main:ONAY_KAYDI.md"))[-1] == ("H1", "C1", "BITTI")
    git(depo, "reset", "--hard", "-q", ilk)
    git(depo, "update-ref", "-d", "refs/remotes/origin/main")
    git(depo, "reflog", "expire", "--expire=now", "--all")
    git(depo, "gc", "-q", "--prune=now")
    assert "H1" not in git(depo, "log", "--all", "--reflog", "-p", "--format=", "--", "ONAY_KAYDI.md")
    with pytest.raises(split.OnayTekrari):
        with split.onay_kosusu("H1", "C1"):
            pytest.fail("itilmis cift yeniden acilmamali")


# --- Kapanis turu: kayit uzak depoya bagli --------------------------------------------------------------------


def _itmeyi_engelle(depo):
    """Uzak deponun `pre-receive` kancasi `engel` dosyasi varken itmeyi reddeder."""
    uzak = uzak_depo(depo)
    kanca = uzak / "hooks" / "pre-receive"
    kanca.write_text("#!/bin/sh\nif [ -f engel ]; then exit 1; fi\nexit 0\n", encoding="utf-8", newline="\n")
    kanca.chmod(0o755)
    (uzak / "engel").write_text("", encoding="utf-8")


def _itme_engelini_kaldir(depo):
    (uzak_depo(depo) / "engel").unlink()


def test_kosu_iki_satiri_da_iter(depo):
    with kosu("H2", "C2"):
        # BASLADI blok calismadan once itilmis.
        assert _durumlar(git(uzak_depo(depo), "show", "main:ONAY_KAYDI.md")) == [("H2", "C2", "BASLADI")]
    assert git(depo, "rev-parse", "HEAD") == git(uzak_depo(depo), "rev-parse", "main")
    assert git(depo, "status", "--porcelain") == ""


def test_itilmemis_kayit_varken_kosu_reddedilir(depo):
    """BASLADI itilemedi: kosu acilmaz, kayda ITILEMEDI yazilir (yerelde commit edilir). Itilmemis satirlar varken
    baska cift icin de kosu acilmaz; elle itilince acilir. Cift harcanmis kalir (veri okunmadi ama BASLADI
    commit edildi: muhafazakar yon)."""
    _itmeyi_engelle(depo)
    with pytest.raises(split.OnayUzakHatasi, match="itilemedi"):
        with split.onay_kosusu("H1", "C1"):
            pytest.fail("BASLADI itilemeyince kosu acilmamali")
    assert _durumlar(_head_kaydi(depo)) == [("H1", "C1", "BASLADI"), ("H1", "C1", "ITILEMEDI")]
    assert split.aktif_onay_kosusu() is None
    _itme_engelini_kaldir(depo)
    with pytest.raises(split.OnayUzakHatasi, match="itilmemis 2 satir"):
        with split.onay_kosusu("H2", "C1"):
            pytest.fail("itilmemis kayit varken kosu acilmamali")
    git(depo, "push", "-q", "origin", "main")
    with pytest.raises(split.OnayTekrari):
        with split.onay_kosusu("H1", "C1"):
            pytest.fail("cift harcanmis")
    with kosu("H2", "C1"):
        pass


def test_bitis_itilemezse_kayda_itilemedi_yazilir_ve_hata_verilir(depo):
    with pytest.raises(split.OnayUzakHatasi, match="BITTI kaydi"):
        with split.onay_kosusu("H3", "C2") as k:
            k.sonuc_bildir("KALDI")
            _itmeyi_engelle(depo)
    satirlar = split.kayit_satirlari(_head_kaydi(depo))
    assert [s["durum"] for s in satirlar] == ["BASLADI", "BITTI", "ITILEMEDI"]
    assert satirlar[-1]["asama"] == "BITTI" and satirlar[1]["sonuc"] == "KALDI"
    assert _durumlar(git(uzak_depo(depo), "show", "main:ONAY_KAYDI.md")) == [("H3", "C2", "BASLADI")]
    _itme_engelini_kaldir(depo)
    with pytest.raises(split.OnayUzakHatasi, match="itilmemis"):
        with split.onay_kosusu("H1", "C2"):
            pytest.fail("kosu acilmamali")


def test_ag_yoksa_kosu_acilmaz_ve_hicbir_sey_yazilmaz(depo):
    git(depo, "remote", "set-url", "origin", str(depo.parent / "olmayan.git"))
    once = _kayit(depo)
    with pytest.raises(split.OnayUzakHatasi, match="alinamadi"):
        with split.onay_kosusu("H1", "C1"):
            pytest.fail("ag yokken kosu acilmamali")
    assert _kayit(depo) == once and git(depo, "status", "--porcelain") == ""


def test_head_uzak_dali_icermiyorsa_kosu_acilmaz(depo):
    """Uzak depoya baska bir kopyadan kayit itilmis; yerel HEAD geride. Kosu, cift farkliysa bile acilmaz."""
    with kosu("H1", "C1"):
        pass
    git(depo, "reset", "--hard", "-q", "HEAD~2")
    with pytest.raises(split.OnayUzakHatasi, match="icermiyor"):
        with split.onay_kosusu("H2", "C2"):
            pytest.fail("kosu acilmamali")
    git(depo, "merge", "-q", "--ff-only", "origin/main")
    with kosu("H2", "C2"):
        pass


# --- OK D-B1: commit edilmemis kayit satiri varken yeni kosu acilmaz ------------------------------------------


def test_commit_edilmemis_bitis_satiri_varken_yeni_kosu_reddedilir(depo):
    with pytest.raises(split.OnayKaydiCommitsiz):
        with kosu("H2", "C2"):
            _engelle(depo)
    _engeli_kaldir(depo)
    once = _kayit(depo)
    with pytest.raises(split.OnayKaydiCommitsiz, match="1 commit edilmemis"):
        with split.onay_kosusu("H3", "C1"):  # baska cift
            pytest.fail("commit edilmemis kayit varken kosu acilmamali")
    assert _kayit(depo) == once
    git(depo, "commit", "-q", "-am", "bitis satiri elle commit edildi")
    git(depo, "push", "-q", "origin", "main")  # kapanis turu: itilmemis kayit varken de kosu acilmaz
    with kosu("H3", "C1"):
        pass
    assert ("H3", "C1", "BITTI") in _durumlar(_head_kaydi(depo))


def test_elle_eklenen_commitsiz_satir_ve_commitsiz_silme_kosuyu_acmaz(depo):
    with kosu("H1", "C2"):
        pass
    commitli = _kayit(depo)
    satir = [s for s in commitli.splitlines() if "durum=BITTI" in s][0]
    # Commit edilmemis satir.
    (depo / "ONAY_KAYDI.md").write_text(commitli + satir.replace("H1", "H2") + "\n", encoding="utf-8", newline="")
    with pytest.raises(split.OnayKaydiCommitsiz):
        with split.onay_kosusu("H3", "C2"):
            pytest.fail("kosu acilmamali")
    # Commit edilmemis silme.
    (depo / "ONAY_KAYDI.md").write_text(commitli.replace(satir + "\n", ""), encoding="utf-8", newline="")
    with pytest.raises(split.OnayKaydiCommitsiz, match="1 silinmis"):
        with split.onay_kosusu("H3", "C2"):
            pytest.fail("kosu acilmamali")


def test_basladi_commit_edilemezse_kosu_acilmaz(depo):
    """BASLADI satiri commit edilemezse kosu acilmaz (blok calismaz, veriye erisilmez). Satir calisma agacinda
    kalir ve commit edilene kadar yeni kosuyu engeller. BELGELEME: bu satir kazayla silinirse cift yeniden
    acilabilir; o cift icin hicbir veri okunmamistir."""
    _engelle(depo)
    with pytest.raises(split.OnayKaydiCommitsiz):
        with split.onay_kosusu("H1", "C1"):
            pytest.fail("kosu acilmamali")
    assert _durumlar(_kayit(depo)) == [("H1", "C1", "BASLADI")]
    assert split.aktif_onay_kosusu() is None
    _engeli_kaldir(depo)
    with pytest.raises(split.OnayKaydiCommitsiz):
        with split.onay_kosusu("H2", "C1"):
            pytest.fail("commit edilmemis BASLADI varken kosu acilmamali")
    git(depo, "checkout", "--", ".")
    assert "BASLADI" in _kayit(depo), "satir index'te (git add); duz checkout silmez"
    git(depo, "checkout", "HEAD", "--", ".")
    with kosu("H1", "C1"):
        pass


# --- Gercek ortamin olumlu ve olumsuz yolu (OK D-C7'ye kismi) ---------------------------------------------


def test_gercek_git_ortaminda_kirli_agac_ve_izlenmeyen_betik_reddedilir(tmp_path):
    depo = gecici_depo(tmp_path)
    (depo / "analysis" / "yeni.py").write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(split.OnayOrtamiHatasi, match="temiz"):
        with split.onay_kosusu("H1", "C1"):
            pytest.fail("kosu acilmamali")
    git(depo, "add", ".")
    git(depo, "commit", "-q", "-m", "yeni betik")
    gecici_kayit(depo / "ONAY_KAYDI.md", depo=depo, betik="analysis/izlenmeyen.py")
    with pytest.raises(split.OnayOrtamiHatasi, match="izlenen"):
        with split.onay_kosusu("H1", "C1"):
            pytest.fail("kosu acilmamali")
    assert split.kayit_satirlari(_kayit(depo)) == []


def test_gecmis_satirlari_saftir():
    cikti = "diff --git a/K b/K\n--- a/K\n+++ b/K\n@@ -1 +1,2 @@\n x\n+| a | C1 |\n-| b |\n+++bas\n"
    assert split.gecmis_satirlari(cikti) == "| a | C1 |\n++bas"
    assert split.onay_satirlari("x\n| 1 | C1 | b | c | hipotez=H1 kosu=k |\r\n| y |\n") == [
        "| 1 | C1 | b | c | hipotez=H1 kosu=k |"]


# --- OK D-C1: sonuc bildirildikten sonra gelen hata -------------------------------------------------------


def test_sonuc_bildirildikten_sonra_hata_kayda_ikisini_de_yazar(tmp_path):
    yol = gecici_kayit(tmp_path / "k.md", head=COMMIT)
    with pytest.raises(ZeroDivisionError):
        with split.onay_kosusu("H2", "C1") as k:
            k.sonuc_bildir("KALDI 3/6")
            1 / 0
    son = split.kayit_satirlari(yol.read_text(encoding="utf-8"))[-1]
    assert (son["durum"], son["hata"], son["sonuc"]) == ("HATA", "ZeroDivisionError", "KALDI 3/6")


def test_sonuc_bildirilmeden_hata_sonuc_alani_yazmaz(tmp_path):
    yol = gecici_kayit(tmp_path / "k.md", head=COMMIT)
    with pytest.raises(SystemExit):
        with split.onay_kosusu("H2", "C1"):
            raise SystemExit(1)
    son = split.kayit_satirlari(yol.read_text(encoding="utf-8"))[-1]
    assert (son["durum"], son["hata"], "sonuc" in son) == ("HATA", "SystemExit", False)


# --- OK D-B2 ve sizinti testcisi O: korunan adlar -----------------------------------------------------------


@pytest.mark.parametrize("ad", ["split_oku", "kume_araligi", "kume_tanimi", "_depo", "_gecmis_kaydi", "_head_kaydi",
                                "_kaydi_commit_et", "_kayit_commitli_denetle", "harcanan_ciftler"])
def test_bolme_kume_ve_git_adlari_disaridan_atanamaz(ad):
    once = getattr(split, ad)
    with pytest.raises(split.OnayKorumasi):
        setattr(split, ad, lambda *a, **k: None)
    with pytest.raises(split.OnayKorumasi):
        delattr(split, ad)
    assert getattr(split, ad) is once


def test_split_sinifi_degistirilemez():
    with pytest.raises(split.OnayKorumasi):
        split.__class__ = types.ModuleType
    with pytest.raises(split.OnayKorumasi):
        split._AKTIF_KOSU = ("H1", "C1")  # koruma yerinde


@pytest.mark.parametrize("ad", ["KESIF_BASI", "KESIF_SONU", "C2_BASI", "C2_SONU", "KUMELER", "ONAY_KUMELERI"])
def test_config_kume_sabitleri_degistirilemez(ad):
    once = getattr(config, ad)
    with pytest.raises(config.SabitDegistirilemez):
        setattr(config, ad, () if ad.endswith("KUMELERI") or ad == "KUMELER" else pd.Timestamp("2030-01-01"))
    with pytest.raises(config.SabitDegistirilemez):
        delattr(config, ad)
    assert getattr(config, ad) is once


def test_config_sinifi_degistirilemez():
    with pytest.raises(config.SabitDegistirilemez):
        config.__class__ = types.ModuleType
    with pytest.raises(config.SabitDegistirilemez):
        config.ONAY_KUMELERI = ()


def test_korunmayan_config_adlari_etkilenmez(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "SPLIT_CSV", tmp_path / "s.csv")
    assert config.SPLIT_CSV == tmp_path / "s.csv"


def test_sinir_modul_sozlugunden_fonksiyon_degistirmek_erisim_acar(tmp_path, monkeypatch):
    """BELGELEME (sinir, denetci OK D-B2 dogrulandi): ayni surec icinden mutlak koruma yok. `vars(split)` ile
    `aktif_onay_kosusu` degistirilirse C1 kayda satir yazilmadan acilir. Bu yol kasitlidir ve analiz kodunda
    taramayla yasaktir (asagidaki desen testi)."""
    yol = gecici_kayit(tmp_path / "k.md", head=COMMIT)
    yol.write_text("bas\n", encoding="utf-8")
    monkeypatch.setitem(vars(split), "aktif_onay_kosusu", lambda: ("H2", "C1"))
    assert split.kume_erisimi(B_SEMBOLU, "C1", onay=True)[0]
    assert yol.read_text(encoding="utf-8") == "bas\n"
    assert ihlaller(ONAY_ATLATMA_DESENI, kok=_tek_dosya(tmp_path, "vars(split_modulu)['aktif_onay_kosusu'] = f\n"))


def _tek_dosya(tmp_path, satir):
    kok = tmp_path / "tarama"
    (kok / "study").mkdir(parents=True)
    (kok / "study" / "k.py").write_text(satir, encoding="utf-8")
    return kok


# --- Tarama: split_modulu takma adi ve korumayi atlayan yollar ----------------------------------------------


@pytest.mark.parametrize("satir", [
    "vars(split_modulu)['kume_araligi'] = f\n",
    "split_modulu.__dict__['split_oku'] = f\n",
    "split_modulu.__class__ = types.ModuleType\n",
    "pozisyon.split_modulu = sahte\n",
    "object.__setattr__(split, 'split_oku', f)\n",
    "types.ModuleType.__setattr__(config, 'ONAY_KUMELERI', ())\n",
    "sys.modules['data.split'] = sahte\n",
    "split._kaydi_commit_et('x')\n",
])
def test_onay_atlatma_deseni_yeni_yollari_yakalar(tmp_path, satir):
    (tmp_path / "study").mkdir()
    (tmp_path / "study" / "k.py").write_text(satir, encoding="utf-8")
    assert ihlaller(ONAY_ATLATMA_DESENI, kok=tmp_path) == ["study/k.py"]


@pytest.mark.parametrize("satir", [
    "from data import split as split_modulu\ngrup = split_modulu.split_oku()\n",
    "if pozisyon.split_modulu == x:\n    pass\n",
])
def test_onay_atlatma_deseni_mesru_kullanimi_yakalamaz(tmp_path, satir):
    (tmp_path / "study").mkdir()
    (tmp_path / "study" / "k.py").write_text(satir, encoding="utf-8")
    assert ihlaller(ONAY_ATLATMA_DESENI, kok=tmp_path) == []
