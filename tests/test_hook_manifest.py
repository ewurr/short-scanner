"""Hook: `data/onbellek_manifest.csv` kilitli dosyalar listesinde (F1-K2, RESULTS §14.51).

Manifest, dondurulmus onbellegin kesif dosyalarini (yol, boy, SHA256) tutar ve kesif kosusu ona
baglanir. Kod onu `data/onbellek_manifest.py` ile uretir (calisan Python kodu hook'tan etkilenmez);
arac cagrisiyla elle degistirilmesi reddedilir, okunmasi serbesttir.

Sinanan: Edit / Write / NotebookEdit / Bash / PowerShell ile yazma reddedilir; Read / Grep / Glob ve salt
okuma komutlari gecer; kilit acikken her sey gecer. Komutlar hicbir zaman CALISTIRILMAZ; yalnizca metin
olarak degerlendirilir (son bolum hook surecini stdin JSON ile calistirir, komutu degil).
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
_SPEC = importlib.util.spec_from_file_location("kilit_hook_manifest", HOOK_YOLU)
hook = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = hook      # dataclass modulun kayitli olmasini bekler
_SPEC.loader.exec_module(hook)

MANIFEST = "data/onbellek_manifest.csv"


# --- Yol: kilitli_mi -------------------------------------------------------------------------------

@pytest.mark.parametrize("yol", [
    MANIFEST, "./" + MANIFEST, "data/../" + MANIFEST, str(KOK / MANIFEST), (KOK / MANIFEST).as_posix(),
    MANIFEST.upper(), "data\\onbellek_manifest.csv",
])
def test_manifest_yolu_kilitli(yol):
    assert hook.kilitli_mi(yol) == MANIFEST


@pytest.mark.parametrize("yol", ["data/onbellek_manifest.py", "data/onbellek_manifest.csv.bak",
                                 "cache/onbellek_manifest.csv", "onbellek_manifest.csv"])
def test_komsu_yollar_kilitli_degil(yol):
    """Kilit yalnizca bu tam yol icindir: modul, yedek ya da baska dizindeki ayni ad kilitli degil."""
    assert hook.kilitli_mi(yol) is None


# --- Bash -------------------------------------------------------------------------------------------

BASH_YAZMALARI = [
    f"echo x >> {MANIFEST}",
    f"echo x > {MANIFEST}",
    f"sed -i 's/a/b/' {MANIFEST}",
    f"mv {MANIFEST} eski.csv",
    f"cp yeni.csv {MANIFEST}",
    f"rm {MANIFEST}",
    f"truncate -s 0 {MANIFEST}",
    f"tee {MANIFEST}",
    f"git checkout -- {MANIFEST}",
    f"git restore {MANIFEST}",
    f"git rm {MANIFEST}",
    f"cd data && rm onbellek_manifest.csv",
    f"{{ echo x; }} > {MANIFEST}",
]

BASH_OKUMALARI = [
    f"cat {MANIFEST}",
    f"head -5 {MANIFEST}",
    f"wc -l {MANIFEST}",
    f"grep BTCUSDT {MANIFEST}",
    f"sha256sum {MANIFEST}",
    f"git log --oneline -- {MANIFEST}",
    f"git show HEAD:{MANIFEST}",
    f"git diff -- {MANIFEST}",
]


@pytest.mark.parametrize("komut", BASH_YAZMALARI)
def test_bash_manifest_yazmasi_reddedilir(komut):
    karar = hook.bash_degerlendir(komut)
    assert not karar.izin, komut


@pytest.mark.parametrize("komut", BASH_OKUMALARI)
def test_bash_manifest_okumasi_gecer(komut):
    assert hook.bash_degerlendir(komut).izin, komut


# --- PowerShell -------------------------------------------------------------------------------------

PS_YAZMALARI = [
    f"Set-Content {MANIFEST} x",
    f"Add-Content -Path {MANIFEST} -Value x",
    f"'x' | Out-File {MANIFEST}",
    f"Clear-Content {MANIFEST}",
    f"Remove-Item {MANIFEST}",
    f"Move-Item {MANIFEST} eski.csv",
    f"Copy-Item yeni.csv {MANIFEST}",
    f"New-Item {MANIFEST} -Force",
    f"echo x > {MANIFEST}",
    f"del {MANIFEST}",
    f"git checkout -- {MANIFEST}",
    f"if ($true) {{ Remove-Item {MANIFEST} }}",
]

PS_OKUMALARI = [
    f"Get-Content {MANIFEST}",
    f"Get-Content {MANIFEST} -TotalCount 5",
    f"Select-String -Path {MANIFEST} -Pattern BTCUSDT",
    f"Test-Path {MANIFEST}",
    f"Get-FileHash {MANIFEST}",
    f"git log --oneline -- {MANIFEST}",
]


@pytest.mark.parametrize("komut", PS_YAZMALARI)
def test_powershell_manifest_yazmasi_reddedilir(komut):
    assert not hook.powershell_degerlendir(komut).izin, komut


@pytest.mark.parametrize("komut", PS_OKUMALARI)
def test_powershell_manifest_okumasi_gecer(komut):
    assert hook.powershell_degerlendir(komut).izin, komut


# --- Surec: stdin JSON -> stdout (Edit / Write / okuma araclari / kilit acik) -----------------------

def _hook_calistir(girdi: dict, kilit_acik: bool = False) -> str:
    cevre = {k: v for k, v in os.environ.items() if k != hook.ACMA_DEGISKENI}
    if kilit_acik:
        cevre[hook.ACMA_DEGISKENI] = "1"
    sonuc = subprocess.run([sys.executable, str(HOOK_YOLU)], input=json.dumps(girdi), capture_output=True,
                           text=True, encoding="utf-8", env=cevre, timeout=30)
    assert sonuc.returncode == 0, sonuc.stderr
    return sonuc.stdout.strip()


def _reddedildi(cikti: str) -> bool:
    return bool(cikti) and json.loads(cikti)["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize("girdi", [
    {"tool_name": "Edit", "tool_input": {"file_path": str(KOK / MANIFEST), "old_string": "a", "new_string": "b"}},
    {"tool_name": "Write", "tool_input": {"file_path": str(KOK / MANIFEST), "content": "yol,boy,sha256\n"}},
    {"tool_name": "NotebookEdit", "tool_input": {"notebook_path": str(KOK / MANIFEST), "new_source": "x"}},
    {"tool_name": "Bash", "tool_input": {"command": f"echo x >> {MANIFEST}"}},
    {"tool_name": "PowerShell", "tool_input": {"command": f"Set-Content {MANIFEST} x"}},
], ids=["Edit", "Write", "NotebookEdit", "Bash", "PowerShell"])
def test_surec_manifest_yazmasini_reddeder(girdi):
    cikti = _hook_calistir(girdi)
    assert _reddedildi(cikti), cikti
    assert MANIFEST in json.loads(cikti)["hookSpecificOutput"]["permissionDecisionReason"]


@pytest.mark.parametrize("girdi", [
    {"tool_name": "Read", "tool_input": {"file_path": str(KOK / MANIFEST)}},
    {"tool_name": "Grep", "tool_input": {"pattern": "BTCUSDT", "path": str(KOK / MANIFEST)}},
    {"tool_name": "Glob", "tool_input": {"pattern": "data/*.csv", "path": str(KOK)}},
    {"tool_name": "Bash", "tool_input": {"command": f"cat {MANIFEST}"}},
    {"tool_name": "PowerShell", "tool_input": {"command": f"Get-Content {MANIFEST}"}},
], ids=["Read", "Grep", "Glob", "Bash", "PowerShell"])
def test_surec_manifest_okumasina_izin_verir(girdi):
    assert _hook_calistir(girdi) == ""


def test_surec_kilit_acikken_manifest_yazmasina_izin_verir():
    assert _hook_calistir({"tool_name": "Edit", "tool_input": {"file_path": str(KOK / MANIFEST)}},
                          kilit_acik=True) == ""
    assert _hook_calistir({"tool_name": "Bash", "tool_input": {"command": f"rm {MANIFEST}"}}, kilit_acik=True) == ""
