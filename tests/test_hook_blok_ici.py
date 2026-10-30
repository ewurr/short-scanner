"""Hook: blok, alt ifade ve atama icindeki komutlar (RESULTS §14.39).

Ilke: bir komut bir blogun, alt ifadenin ya da atamanin sag tarafinin icinde yazildiginda, duz
yazilmis haliyle ayni karari alir. Beklenen karar elle yazilmaz, duz komutun olcumunden uretilir.

Komutlar hicbir zaman CALISTIRILMAZ; yalnizca metin olarak degerlendirilir.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parents[1]
_YOL = KOK / ".claude" / "hooks" / "kilitli_dosya_korumasi.py"
_SPEC = importlib.util.spec_from_file_location("kilit_hook_blok", _YOL)
hook = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = hook      # dataclass modulun kayitli olmasini bekler
_SPEC.loader.exec_module(hook)

KILITLILER = ("PREREGISTRATION.md", "analysis/H2/KILIT.md")
LEHCE = {"ps": hook.powershell_degerlendir, "bash": hook.bash_degerlendir}

# Tek tablo: kabuk, komut, icteki duz komutlar. `<K>` iki kilitli dosyayla acilir.
_SABLONLAR = [
    ("ps", "if ($?) { git reset --hard }", ["git reset --hard"]),
    ("ps", "if ($?) { git log -- <K> }", ["git log -- <K>"]),
    ("ps", "if ($?) { git clean -fd } else { git status }", ["git clean -fd", "git status"]),
    ("ps", "git status | ForEach-Object { git reset --hard }", ["git status", "git reset --hard"]),
    ("ps", "foreach ($i in 1) { git stash }", ["git stash"]),
    ("ps", "try { git restore . } catch { }", ["git restore ."]),
    ("ps", "& { git reset --hard }", ["git reset --hard"]),
    ("ps", "$x = git reset --hard", ["git reset --hard"]),
    ("ps", "$x = git log -- <K>", ["git log -- <K>"]),
    ("ps", "$x = git status", ["git status"]),
    ("ps", "$(git reset --hard)", ["git reset --hard"]),
    ("ps", '"$(git clean -fd)"', ["git clean -fd"]),
    ("ps", "if ($?) { Remove-Item <K> }", ["Remove-Item <K>"]),
    ("bash", "{ git reset --hard; }", ["git reset --hard"]),
    ("bash", "( git reset --hard )", ["git reset --hard"]),
    ("bash", "if true; then git reset --hard; fi", ["git reset --hard"]),
    ("bash", "if true; then git log -- <K>; fi", ["git log -- <K>"]),
    ("bash", "for i in 1; do git clean -fd; done", ["git clean -fd"]),
    ("bash", "while false; do git stash; done", ["git stash"]),
    ("bash", "x=$(git reset --hard)", ["git reset --hard"]),
    ("bash", "x=`git reset --hard`", ["git reset --hard"]),
    ("bash", "x=$(git log -- <K>)", ["git log -- <K>"]),
    ("bash", 'echo "$(git clean -fd)"', ["git clean -fd"]),
    ("bash", "if true; then rm <K>; fi", ["rm <K>"]),
]

# RED (bilincli siki, §14.39): gevseme siniri git disi RED->izin donusunu yasaklar, okuma `Read` ile yapilir.
_BILINCLI_SIKI = [
    ("ps", "if ($?) { Get-Content <K> }", ["Get-Content <K>"]),
    ("bash", "if true; then cat <K>; fi", ["cat <K>"]),
]


def _ac(sablonlar):
    satirlar = []
    for kabuk, komut, duzler in sablonlar:
        for kilitli in KILITLILER if "<K>" in komut else (None,):
            yaz = (lambda t, k=kilitli: t.replace("<K>", k)) if kilitli else (lambda t: t)
            satirlar.append((kabuk, yaz(komut), tuple(yaz(d) for d in duzler)))
    return satirlar


TABLO = _ac(_SABLONLAR)
SIKI = _ac(_BILINCLI_SIKI)


def test_tablo_beklenen_buyuklukte():
    """RESULTS §14.39'un sayilari bu tabloya dayanir: 34 satir, 4'u bilincli siki."""
    assert len(TABLO) + len(SIKI) == 34
    assert len(SIKI) == 4


@pytest.mark.parametrize("kabuk,komut,duzler", TABLO, ids=[f"{s[0]}:{s[1]}" for s in TABLO])
def test_blok_karari_duz_komutun_kararina_esit(kabuk, komut, duzler):
    degerlendir = LEHCE[kabuk]
    beklenen = all(degerlendir(d).izin for d in duzler)
    assert degerlendir(komut).izin is beklenen, komut


@pytest.mark.parametrize("kabuk,komut,duzler", SIKI, ids=[f"{s[0]}:{s[1]}" for s in SIKI])
def test_git_disi_okuma_blok_icinde_bilincli_olarak_red_kalir(kabuk, komut, duzler):
    degerlendir = LEHCE[kabuk]
    assert all(degerlendir(d).izin for d in duzler), "duz hali izinli olmali; istisnanin dayanagi bu"
    karar = degerlendir(komut)
    assert not karar.izin and karar.belirsiz, komut


# Gundelik is akisi: bu komutlar reddedilirse hook isi durdurur.
IS_AKISI = [
    'git add -A; if ($?) { git commit -m "x" }; if ($?) { git push }',
    "git add -A; if ($?) { git commit -m @'\ndocs(results): §14.39\n'@ }",
    "python -m pytest -q tests/test_hook.py",
    "foreach ($g in 0..3) { python -m pytest -q -rxXf tests/test_hook.py }",
    "$r = python -m pytest -q tests/test_hook.py; if (-not $?) { exit 1 }",
    "Get-ChildItem analysis | ForEach-Object { $_.Name }",
    "Select-String -Path analysis\\00_veri_denetimi\\RESULTS.md -Pattern '§14' | Select-Object -Last 3",
    "$x = git log --oneline -3",
    "if ($?) { git log --oneline origin/main..main | Measure-Object -Line }",
]


@pytest.mark.parametrize("kabuk", sorted(LEHCE))
@pytest.mark.parametrize("komut", IS_AKISI)
def test_is_akisi_komutlari_iki_kabukta_gecer(kabuk, komut):
    karar = LEHCE[kabuk](komut)
    assert karar.izin, f"{komut} -> {karar.neden}"


# --- Gevseme siniri ---------------------------------------------------------------------------


def test_git_kayit_tek_kaynaktan_turer():
    assert hook.GIT_KAYIT <= hook.GIT_OKUMA
    assert hook.GIT_SALT_OKUMA == hook.GIT_OKUMA - hook.GIT_KAYIT


@pytest.mark.parametrize("kabuk", sorted(LEHCE))
@pytest.mark.parametrize("komut", [
    "{ git diff --output=PREREGISTRATION.md }",
    "{ git diff --output=analysis/H2/KILIT.md }",
    "if ($?) { git log --output=PREREGISTRATION.md }",
    "if ($?) { git add PREREGISTRATION.md }",
    "if ($?) { git config --file PREREGISTRATION.md a.b c }",
    "{ PREREGISTRATION.md }",
    "rm { PREREGISTRATION.md }",
    "$x = PREREGISTRATION.md",
])
def test_gevseme_siniri_disinda_red_dusmez(kabuk, komut):
    assert not LEHCE[kabuk](komut).izin, komut


@pytest.mark.parametrize("kabuk", sorted(LEHCE))
@pytest.mark.parametrize("komut", [
    "if ($?) { git reset --hard",
    'echo "$(git clean -fd)',
])
def test_kapanmamis_blok_ve_ikamede_bugunku_davranis_korunur(kabuk, komut):
    assert LEHCE[kabuk](komut).izin, komut


@pytest.mark.parametrize("komut", ["git log HEAD@{1}", "git show stash@{0}", "find . -name x -exec cat {} +"])
def test_dengeli_kume_parantezi_blok_sayilmaz(komut):
    assert hook.bash_degerlendir(komut).izin and hook.powershell_degerlendir(komut).izin, komut


def test_tek_tirnak_ici_ikame_metindir():
    assert hook.bash_degerlendir("git commit -m 'bak: $(git reset --hard)'").izin
    assert hook.powershell_degerlendir("git commit -m @'\n$(git reset --hard)\n'@").izin
