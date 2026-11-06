"""Agac temizliginin tek kaynagi (performans 2b-0 kapanisi, RESULTS §14.46; denetci D-B1, sizinti S-31, S-32, S-33).

`split._agac_kirlilikleri` uc denetimi birlestirir (status, `ls-files -v`, `.gitignore`'a gore izlenmeyenler); kesif
kaydi ve onay kosu ortami agac temizligini yalnizca ondan alir. Kayitta ve hata mesajinda dosya adi degil sayi vardir.
Butun git islemleri `gecici_depo` gecici depolarinda yapilir; onay kosusu acilmaz (yalnizca ortam karari sinanir).
"""

from __future__ import annotations

import ast
import inspect
import textwrap

import pytest

from data import split
from onay_yardimcisi import DEPO_BETIGI, gecici_depo, git

GIZLI = "gizli_kural.py"


def _kesif():
    return split._kesif_kaydi_kur(None)


def _onay_reddi() -> str | None:
    """Onay kosu ortami agaci reddederse mesaj; kabul ederse None."""
    try:
        split._kosu_ortami()
    except split.OnayOrtamiHatasi as hata:
        return str(hata)
    return None


def _cagrilan_adlar(fonk) -> set[str]:
    agac = ast.parse(textwrap.dedent(inspect.getsource(fonk)))
    return {d.func.id for d in ast.walk(agac) if isinstance(d, ast.Call) and isinstance(d.func, ast.Name)}


def test_kesif_kaydi_ve_onay_ortami_ayni_fonksiyonu_kullanir():
    for fonk in (split._kesif_kaydi_kur, split._kosu_ortami):
        adlar = _cagrilan_adlar(fonk)
        assert "_agac_kirlilikleri" in adlar, fonk.__name__
    # Durum komutu ve ls-files yalnizca tek kaynakta cagrilir.
    for fonk in (split._kesif_kaydi_kur, split._kosu_ortami):
        kaynak = inspect.getsource(fonk)
        assert "_DURUM_KOMUTU" not in kaynak and '"-v"' not in kaynak, fonk.__name__
    kaynak = inspect.getsource(split._agac_kirlilikleri)
    assert "_DURUM_KOMUTU" in kaynak and '"-v"' in kaynak and "_IZLENMEYEN_KOMUTU" in kaynak


def test_izlenmeyen_komutu_yalnizca_gitignore_dosyalarina_uyar():
    assert split._IZLENMEYEN_KOMUTU == ("ls-files", "--others", "--exclude-per-directory=.gitignore")
    assert "--exclude-standard" not in split._IZLENMEYEN_KOMUTU


def test_temiz_depo_iki_yolda_da_temiz(tmp_path):
    gecici_depo(tmp_path)
    assert split._agac_kirlilikleri() == []
    kayit = _kesif()
    assert kayit.agac_temiz is True and kayit.agac_kirli_sayisi == 0
    assert _onay_reddi() is None


def test_bu_git_surumunde_ls_files_yalnizca_gitignore_dosyalarina_uyar(tmp_path, monkeypatch):
    """`--exclude-per-directory=.gitignore` kok ve alt dizin `.gitignore`larini uygular; `.git/info/exclude`, yerel
    `core.excludesFile` ve `$HOME/.config/git/ignore` yok sayilir. Bag ortaminda (`split._git`) sinanir."""
    depo = gecici_depo(tmp_path)
    (depo / ".gitignore").write_text("kok_yok.py\n", encoding="utf-8")
    (depo / "alt").mkdir()
    (depo / "alt" / ".gitignore").write_text("alt_yok.py\n", encoding="utf-8")
    git(depo, "add", ".gitignore", "alt/.gitignore")
    git(depo, "commit", "-q", "-m", "gitignore")
    with (depo / ".git" / "info" / "exclude").open("a", encoding="utf-8") as d:
        d.write("info_exclude.py\n")
    liste = tmp_path / "dislama"
    liste.write_text("excludesfile.py\n", encoding="utf-8")
    git(depo, "config", "core.excludesFile", liste.as_posix())
    ev = tmp_path / "ev"
    (ev / ".config" / "git").mkdir(parents=True)
    (ev / ".config" / "git" / "ignore").write_text("xdg.py\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(ev))
    monkeypatch.setenv("USERPROFILE", str(ev))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    for ad in ("kok_yok.py", "alt/alt_yok.py", "info_exclude.py", "excludesfile.py", "xdg.py"):
        (depo / ad).write_text("x = 1\n", encoding="utf-8")
    cikti = split._git(*split._IZLENMEYEN_KOMUTU)
    assert cikti is not None
    assert sorted(cikti.split()) == ["excludesfile.py", "info_exclude.py", "xdg.py"]


def test_gitignoredaki_dosya_kirli_sayilmaz(tmp_path):
    depo = gecici_depo(tmp_path)
    (depo / ".gitignore").write_text("onbellek/\n", encoding="utf-8")
    git(depo, "add", ".gitignore")
    git(depo, "commit", "-q", "-m", "gitignore")
    (depo / "onbellek").mkdir()
    (depo / "onbellek" / "a.parquet").write_bytes(b"x")
    assert _kesif().agac_temiz is True
    assert _onay_reddi() is None


@pytest.mark.parametrize("gizleme", ["info_exclude", "excludesfile", "xdg"])
def test_yerel_dislama_ile_gizlenen_izlenmeyen_dosya_iki_yolda_da_kirli(tmp_path, monkeypatch, gizleme):
    depo = gecici_depo(tmp_path)
    if gizleme == "info_exclude":
        with (depo / ".git" / "info" / "exclude").open("a", encoding="utf-8") as d:
            d.write(f"{GIZLI}\n")
    elif gizleme == "excludesfile":
        liste = tmp_path / "dislama"
        liste.write_text(f"{GIZLI}\n", encoding="utf-8")
        git(depo, "config", "core.excludesFile", liste.as_posix())
    else:
        ev = tmp_path / "ev"
        (ev / ".config" / "git").mkdir(parents=True)
        (ev / ".config" / "git" / "ignore").write_text(f"{GIZLI}\n", encoding="utf-8")
        monkeypatch.setenv("HOME", str(ev))
        monkeypatch.setenv("USERPROFILE", str(ev))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    (depo / GIZLI).write_text("x = 1\n", encoding="utf-8")
    kayit = _kesif()
    assert kayit.agac_temiz is False and kayit.agac_kirli_sayisi == 1
    mesaj = _onay_reddi()
    assert mesaj is not None and "temiz calisma agacinda" in mesaj


@pytest.mark.parametrize("bayrak", ["--assume-unchanged", "--skip-worktree"])
def test_onay_yolu_isaretli_dosyayi_kirli_sayar(tmp_path, bayrak):
    """D-B1: onay kosu ortami da `ls-files -v` isaretlerini gorur (onceden yalnizca kesif kaydi goruyordu)."""
    depo = gecici_depo(tmp_path)
    git(depo, "update-index", bayrak, DEPO_BETIGI)
    (depo / DEPO_BETIGI).write_text("# degisti\n", encoding="utf-8")
    assert git(depo, "status", "--porcelain").strip() == ""
    mesaj = _onay_reddi()
    assert mesaj is not None and "temiz calisma agacinda" in mesaj
    assert _kesif().agac_temiz is False


def test_kayit_ve_mesaj_dosya_adi_tasimaz_yalnizca_sayi(tmp_path):
    depo = gecici_depo(tmp_path)
    adlar = ["birinci_gizli.py", "ikinci_gizli.py"]
    for ad in adlar:
        (depo / ad).write_text("x = 1\n", encoding="utf-8")
    (depo / DEPO_BETIGI).write_text("# degisti\n", encoding="utf-8")
    kayit = _kesif()
    assert kayit.agac_kirli_sayisi == 3
    metin = repr(kayit) + str(kayit.alanlar())
    mesaj = _onay_reddi()
    assert mesaj is not None and "3 kirli kayit" in mesaj
    for ad in [*adlar, DEPO_BETIGI]:
        assert ad not in metin and ad not in mesaj


def test_git_okunamazsa_kapali_yon(tmp_path, monkeypatch):
    """Depo olmayan bir dizinde tek kaynak None doner: kesif kaydi `agac_temiz=None`, onay ortami reddeder."""
    depo = gecici_depo(tmp_path)
    (depo / ".git").rename(depo / "git_degil")  # Windows'ta nesneler salt okunur; silmek yerine adlandirilir
    assert split._agac_kirlilikleri() is None
    kayit = _kesif()
    assert kayit.agac_temiz is None and kayit.agac_kirli_sayisi is None
    assert _onay_reddi() is not None
