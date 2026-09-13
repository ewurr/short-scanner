"""Kilitli dosya hook'u testleri (CLAUDE.md §5 koruma katmani).

Hook iki yoldan korur:
  - Write / Edit / NotebookEdit: hedef yol kilitliyse red,
  - Bash: komut kilitli dosyaya YAZMA niyeti tasiyorsa red; salt okuma gecer;
    sinifi belirlenemeyen ve kilitli dosyayi anan komut temkinli red.

Komutlar hicbir zaman CALISTIRILMAZ; yalnizca metin olarak degerlendirilir.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parents[1]
HOOK_YOLU = KOK / ".claude" / "hooks" / "kilitli_dosya_korumasi.py"

_spec = importlib.util.spec_from_file_location("kilitli_dosya_korumasi", HOOK_YOLU)
hook = importlib.util.module_from_spec(_spec)
# dataclass, modulun sys.modules icinde kayitli olmasini bekler.
sys.modules[_spec.name] = hook
_spec.loader.exec_module(hook)


# --- Bash: yazma niyeti -> red -----------------------------------------------

YAZMA_KOMUTLARI = [
    "echo test >> PREREGISTRATION.md",
    "printf x > CLAUDE.md",
    "cat yama.txt > data/split.csv",
    "sed -i 's/a/b/' CLAUDE.md",
    "sed -ni.bak p ONAY_KAYDI.md",
    "mv data/split.csv eski.csv",
    "cp yedek.md PREREGISTRATION.md",
    "rm ONAY_KAYDI.md",
    "truncate -s 0 CLAUDE.md",
    "tee -a CLAUDE.md",
    "dd if=/dev/zero of=CLAUDE.md",
    "git checkout -- PREREGISTRATION.md",
    "git restore ONAY_KAYDI.md",
    "git rm data/split.csv",
    "cd /d/Projeler/short_scanner && echo x >> ONAY_KAYDI.md",
]


@pytest.mark.parametrize("komut", YAZMA_KOMUTLARI)
def test_yazma_niyeti_reddedilir(komut):
    karar = hook.bash_degerlendir(komut)
    assert not karar.izin, komut
    assert not karar.belirsiz, f"kesin yazma belirsiz sayildi: {komut}"


# --- Bash: agac degistiren git -> ad gecmese de red --------------------------

GIT_AGAC_KOMUTLARI = [
    "git checkout .",
    "git restore --source=HEAD~1 .",
    "git apply yama.patch",
    "git reset --hard HEAD",
    "git stash",
    "git pull",
]


@pytest.mark.parametrize("komut", GIT_AGAC_KOMUTLARI)
def test_agac_degistiren_git_ad_gecmese_de_reddedilir(komut):
    """Kilitli dosyayi adiyla anmadan da degistirebilirler."""
    assert not hook.bash_degerlendir(komut).izin, komut


# --- Bash: dizin ve glob kapsamasi -> red ------------------------------------

KAPSAYAN_KOMUTLAR = [
    "rm -rf data",
    "rm *.md",
    "mv data data_eski",
    "rm -rf .",
]


@pytest.mark.parametrize("komut", KAPSAYAN_KOMUTLAR)
def test_kilitli_dosyayi_kapsayan_dizin_ve_glob_reddedilir(komut):
    assert not hook.bash_degerlendir(komut).izin, komut


# --- Bash: salt okuma -> izin ------------------------------------------------

OKUMA_KOMUTLARI = [
    "cat PREREGISTRATION.md",
    "grep -n Revizyon PREREGISTRATION.md",
    "head -5 ONAY_KAYDI.md | tail -2",
    "sed -n '1,5p' CLAUDE.md",
    "cat data/split.csv 2>/dev/null | wc -l",
    "cp PREREGISTRATION.md /tmp/yedek.md",
    'echo "CLAUDE.md okundu"',
    "ls data",
    "git log --oneline -- PREREGISTRATION.md",
    "git show HEAD:CLAUDE.md",
    "git diff PREREGISTRATION.md",
    "git status --short",
    "git -C /d/Projeler/short_scanner status",
    'git add PREREGISTRATION.md && git commit -m "PREREGISTRATION.md revizyonu"',
    "git reset HEAD CLAUDE.md",
    "git stash list",
    "git checkout -b yeni-dal",
    "git switch -c yeni-dal",
]


@pytest.mark.parametrize("komut", OKUMA_KOMUTLARI)
def test_salt_okuma_gecer(komut):
    karar = hook.bash_degerlendir(komut)
    assert karar.izin, f"{komut} -> {karar.neden}"


def test_heredoc_commit_mesaji_kilitli_adi_ansa_da_gecer():
    komut = (
        "git commit -q -m \"$(cat <<'EOF'\n"
        "CLAUDE.md §5: koruma katmani maddesi\n"
        "PREREGISTRATION.md revizyonu\n"
        "EOF\n"
        ")\""
    )
    assert hook.bash_degerlendir(komut).izin


# --- Bash: kilitli dosyayla ilgisiz yazmalar -> izin -------------------------

ILGISIZ_YAZMALAR = [
    "python -m pytest -q",
    "rm -rf cache/klines",
    "rm tests/__pycache__/x.pyc",
    "echo x > /tmp/not.txt",
    "sed -i 's/a/b/' data/pencere.py",
    "cp config.py /tmp/config.py",
    "git add -A && git commit -m 'veri katmani'",
]


@pytest.mark.parametrize("komut", ILGISIZ_YAZMALAR)
def test_kilitli_dosyayla_ilgisiz_yazmalar_gecer(komut):
    karar = hook.bash_degerlendir(komut)
    assert karar.izin, f"{komut} -> {karar.neden}"


# --- Bash: sinifi belirsiz -> temkinli red -----------------------------------

BELIRSIZ_KOMUTLAR = [
    "python -c \"open('CLAUDE.md','a').write('x')\"",
    "python - <<'PYEOF'\nopen('PREREGISTRATION.md', 'a')\nPYEOF",
    "find . -name CLAUDE.md -delete",
    "for f in CLAUDE.md; do cat $f; done",
    "echo \"$(sed -i 's/x/y/' CLAUDE.md)\"",
    'cat "CLAUDE.md',
]


@pytest.mark.parametrize("komut", BELIRSIZ_KOMUTLAR)
def test_sinifi_belirsiz_komut_temkinli_reddedilir(komut):
    karar = hook.bash_degerlendir(komut)
    assert not karar.izin, komut
    assert karar.belirsiz, f"belirsiz olarak isaretlenmedi: {komut}"


# --- Yol eslestirme (Write/Edit) ---------------------------------------------


@pytest.mark.parametrize(
    "yol",
    [
        str(KOK / "PREREGISTRATION.md"),
        str(KOK / "data" / "split.csv"),
        "/d/Projeler/short_scanner/ONAY_KAYDI.md",
        "CLAUDE.md",
    ],
)
def test_kilitli_yol_taninir(yol):
    assert hook.kilitli_mi(yol) is not None


def test_kilitli_olmayan_yol_taninmaz():
    assert hook.kilitli_mi(str(KOK / "data" / "pencere.py")) is None


# --- Surecin kendisi (stdin JSON -> stdout) ----------------------------------


def _hook_calistir(girdi, kilit_acik: bool = False) -> str:
    cevre = {k: v for k, v in os.environ.items() if k != hook.ACMA_DEGISKENI}
    if kilit_acik:
        cevre[hook.ACMA_DEGISKENI] = "1"
    metin = girdi if isinstance(girdi, str) else json.dumps(girdi)
    sonuc = subprocess.run(
        [sys.executable, str(HOOK_YOLU)],
        input=metin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=cevre,
        timeout=30,
    )
    assert sonuc.returncode == 0, sonuc.stderr
    return sonuc.stdout.strip()


def test_surec_bash_yazmayi_reddeder():
    cikti = _hook_calistir({"tool_name": "Bash", "tool_input": {"command": "echo test >> PREREGISTRATION.md"}})
    cevap = json.loads(cikti)["hookSpecificOutput"]
    assert cevap["permissionDecision"] == "deny"
    assert "PREREGISTRATION.md" in cevap["permissionDecisionReason"]


def test_surec_bash_okumaya_izin_verir():
    assert _hook_calistir({"tool_name": "Bash", "tool_input": {"command": "cat PREREGISTRATION.md"}}) == ""


def test_surec_belirsiz_reddi_gerekcede_belirtir():
    cikti = _hook_calistir({"tool_name": "Bash", "tool_input": {"command": "python -c \"x='CLAUDE.md'\""}})
    assert "TEMKINLI" in json.loads(cikti)["hookSpecificOutput"]["permissionDecisionReason"]


def test_surec_edit_kilitli_dosyayi_reddeder():
    cikti = _hook_calistir({"tool_name": "Edit", "tool_input": {"file_path": str(KOK / "CLAUDE.md")}})
    assert json.loads(cikti)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_surec_kilit_acikken_her_seye_izin_verir():
    assert _hook_calistir(
        {"tool_name": "Bash", "tool_input": {"command": "echo x >> ONAY_KAYDI.md"}}, kilit_acik=True
    ) == ""
    assert _hook_calistir(
        {"tool_name": "Edit", "tool_input": {"file_path": str(KOK / "CLAUDE.md")}}, kilit_acik=True
    ) == ""


def test_surec_ayristirilamayan_girdide_sessizce_gecmez():
    cikti = _hook_calistir("bozuk-json ONAY_KAYDI.md")
    assert json.loads(cikti)["hookSpecificOutput"]["permissionDecision"] == "deny"
