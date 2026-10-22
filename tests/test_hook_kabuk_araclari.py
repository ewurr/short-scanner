"""Hook'un denetledigi KABUK ARACLARI: PowerShell ve taninmayan araclar (madde 1a).

Bulgu (sizinti turu): `main()` yalnizca `tool_name == "Bash"` komutuna bakiyordu ve
`.claude/settings.json` eslestiricisi `Write|Edit|NotebookEdit|Bash` idi. Bu ortamin birincil
kabugu PowerShell oldugu icin butun kilitli dosyalarin korumasi o kanaldan delikti.

Simdi: `tool_input` icinde komut alani tasiyan HER arac denetlenir. Arac adi yalnizca lehce
secer (bash / powershell); taninmayan arac adinda iki lehce de denetlenir ve biri reddediyorsa
komut reddedilir -- yani beyaz liste degil, kara liste mantigi.

Komutlar hicbir zaman CALISTIRILMAZ; yalnizca metin olarak degerlendirilir.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parents[1]
_YOL = KOK / ".claude" / "hooks" / "kilitli_dosya_korumasi.py"
_SPEC = importlib.util.spec_from_file_location("kilit_hook_kabuk", _YOL)
hook = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = hook      # dataclass modulun kayitli olmasini bekler
_SPEC.loader.exec_module(hook)

KILIT = "analysis/h1/" + "KILIT" + ".md"


def _calistir(monkeypatch, capsys, girdi: dict) -> str:
    monkeypatch.delenv(hook.ACMA_DEGISKENI, raising=False)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(girdi)))
    assert hook.main() == 0
    return capsys.readouterr().out


# --- 1. Denetlenen araclarin listesi testte yazili -------------------------------------------


def test_denetlenen_arac_listesi():
    """Yeni bir kabuk araci eklendiginde bu testin fark etmesi gerekir (madde 1a)."""
    assert hook.KABUK_ARACLARI == {
        "bash": "bash", "shell": "bash", "sh": "bash", "zsh": "bash",
        "powershell": "powershell", "pwsh": "powershell", "powershellcore": "powershell",
    }
    # F1 kapatma turu madde 1e: liste genisletildi ve BILINMEYEN alanlar da denetlenir
    # (`tests/test_hook_bilinmeyen_alanlar.py`). Hangi alanlarin hangi dalda denetlendigi burada
    # yazilidir; liste degisirse bu test fark eder.
    assert hook.KOMUT_ALANLARI == ("command", "cmd", "commands", "script", "scripts", "komut",
                                   "shell", "run", "code", "snippet", "program", "args", "argv",
                                   "arguments", "input")
    assert hook.KOD_ALANLARI == ("code", "snippet", "program", "script", "scripts")
    assert hook.YOL_ALANLARI == ("file_path", "notebook_path", "path", "filePath")


def test_ayar_dosyasi_kabuk_araclarini_kapsar():
    """Eslestirici PowerShell'i ADIYLA anar ve ayrica her araci kapsayan bir desen tasir."""
    ayar = json.loads((KOK / ".claude" / "settings.json").read_text(encoding="utf-8"))
    eslestirici = ayar["hooks"]["PreToolUse"][0]["matcher"]
    parcalar = eslestirici.split("|")
    assert "PowerShell" in parcalar, eslestirici
    assert "Bash" in parcalar and "Write" in parcalar and "Edit" in parcalar
    assert ".*" in parcalar, f"taninmayan araclari kapsayan desen yok: {eslestirici}"


# --- 2. PowerShell: yazan cmdlet'ler reddedilir ----------------------------------------------


PS_YAZMA_KOMUTLARI = [
    f"Set-Content -Path {KILIT} -Value x",
    f"Set-Content {KILIT} x",
    f"Add-Content -Path {KILIT} -Value x",
    f"Out-File -FilePath {KILIT}",
    f"'x' | Out-File {KILIT}",
    f"Clear-Content {KILIT}",
    f"Remove-Item {KILIT}",
    f"Remove-Item -Recurse -Force analysis/h1",
    f"Move-Item {KILIT} eski.md",
    f"Rename-Item {KILIT} eski.md",
    f"New-Item -ItemType File -Force {KILIT}",
    f"Copy-Item yedek.md {KILIT}",
    f"Copy-Item -Path yedek.md -Destination {KILIT}",
    f"Tee-Object -FilePath {KILIT}",
    f"Export-Csv -Path {KILIT}",
    f"echo x > {KILIT}",
    f"'x' >> {KILIT}",
    "Set-Content -Path PREREGISTRATION.md -Value x",
    "Remove-Item data/split.csv",
    "Set-Content CLAUDE.md x",
    "Remove-Item ONAY_KAYDI.md",
    "Set-Content data/universe.csv x",
    "Set-Content data/exchange_info_anlik.json x",
    # Takma adlar
    f"sc {KILIT} x",
    f"ri {KILIT}",
    f"del {KILIT}",
    f"mv {KILIT} x.md",
    f"cp yedek.md {KILIT}",
    f"ac {KILIT} x",
    f"clc {KILIT}",
]


@pytest.mark.parametrize("komut", PS_YAZMA_KOMUTLARI)
def test_powershell_yazma_reddedilir(komut):
    karar = hook.powershell_degerlendir(komut)
    assert not karar.izin, komut


PS_OKUMA_KOMUTLARI = [
    f"Get-Content {KILIT}",
    f"Get-Content -Path {KILIT} -TotalCount 5",
    f"Select-String -Path {KILIT} -Pattern yapilandirma",
    "Get-ChildItem analysis",
    f"Test-Path {KILIT}",
    f"Get-Content {KILIT} | Measure-Object -Line",
    "Get-Content CLAUDE.md",
    "Select-String -Path PREREGISTRATION.md -Pattern '§8'",
    f"cat {KILIT}",
    f"gc {KILIT}",
    f"sls -Path {KILIT} -Pattern x",
]


@pytest.mark.parametrize("komut", PS_OKUMA_KOMUTLARI)
def test_powershell_okuma_gecer(komut):
    karar = hook.powershell_degerlendir(komut)
    assert karar.izin, f"{komut} -> {karar.neden}"


@pytest.mark.parametrize("komut", [
    f"Set-Content analysis/h1/kilitler.md x",
    "Set-Content analysis/00_veri_denetimi/.rev1213_capasiz.kilit x",
    "Remove-Item analysis/00_veri_denetimi/.rev1213_capasiz.kilit",
    "Set-Content cache/veri.parquet x",
    "Remove-Item analysis/00_veri_denetimi/yeni.csv",
])
def test_powershell_kilitli_olmayan_dosyaya_yazma_gecer(komut):
    """Yanlis pozitif denetimi: kilitli olmayan dosyalar PowerShell yolundan da yazilabilir."""
    karar = hook.powershell_degerlendir(komut)
    assert karar.izin, f"{komut} -> {karar.neden}"


def test_powershell_taninmayan_cmdlet_temkinli_reddedilir():
    karar = hook.powershell_degerlendir(f"Invoke-Yama -Hedef {KILIT}")
    assert not karar.izin and karar.belirsiz


def test_powershell_here_string_govdesi_temkinli_reddedilir():
    komut = "python - @'\nopen('" + KILIT + "','w').write('x')\n'@"
    karar = hook.powershell_degerlendir(komut)
    assert not karar.izin and karar.belirsiz


def test_powershell_ayirici_sonrasi_komut_da_denetlenir():
    karar = hook.powershell_degerlendir(f"Get-ChildItem analysis; Set-Content {KILIT} x")
    assert not karar.izin


# --- 3. main(): arac adindan bagimsiz denetim ------------------------------------------------


@pytest.mark.parametrize("arac", ["PowerShell", "powershell", "pwsh", "Bash", "bash",
                                  "YeniKabuk", "Terminal", None])
def test_main_komut_tasiyan_her_araci_denetler(monkeypatch, capsys, arac):
    """Arac adi ne olursa olsun (bilinmeyen ad dahil) kilitli dosyaya yazan komut reddedilir."""
    girdi = {"tool_name": arac, "tool_input": {"command": f"Set-Content -Path {KILIT} -Value x"}}
    assert '"deny"' in _calistir(monkeypatch, capsys, girdi), arac


@pytest.mark.parametrize("arac", ["PowerShell", "YeniKabuk"])
def test_main_bash_yazimi_da_yeni_araclarda_denetlenir(monkeypatch, capsys, arac):
    girdi = {"tool_name": arac, "tool_input": {"command": "echo x >> CLAUDE.md"}}
    assert '"deny"' in _calistir(monkeypatch, capsys, girdi), arac


@pytest.mark.parametrize("alan", ["command", "cmd", "script", "komut"])
def test_main_komut_alanlarinin_hepsi_denetlenir(monkeypatch, capsys, alan):
    girdi = {"tool_name": "YeniKabuk", "tool_input": {alan: f"Remove-Item {KILIT}"}}
    assert '"deny"' in _calistir(monkeypatch, capsys, girdi), alan


def test_main_okuma_komutu_gecer(monkeypatch, capsys):
    girdi = {"tool_name": "PowerShell", "tool_input": {"command": f"Get-Content {KILIT}"}}
    assert _calistir(monkeypatch, capsys, girdi) == ""


def test_main_kilit_acikken_gecer(monkeypatch, capsys):
    monkeypatch.setenv(hook.ACMA_DEGISKENI, "1")
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(
        {"tool_name": "PowerShell", "tool_input": {"command": f"Set-Content {KILIT} x"}})))
    assert hook.main() == 0
    assert capsys.readouterr().out == ""


def test_main_yol_alani_filepath_de_denetlenir(monkeypatch, capsys):
    girdi = {"tool_name": "YeniDuzenleyici", "tool_input": {"filePath": str(KOK / "CLAUDE.md")}}
    assert '"deny"' in _calistir(monkeypatch, capsys, girdi)


def test_komut_degerlendir_taninmayan_aracta_iki_lehce_de_denetlenir():
    """Taninmayan arac: bash yazimi da PowerShell yazimi da reddedilir."""
    assert not hook.komut_degerlendir("YeniKabuk", f"sed -i 's/a/b/' {KILIT}").izin
    assert not hook.komut_degerlendir("YeniKabuk", f"Set-Content {KILIT} x").izin
    assert hook.komut_degerlendir("YeniKabuk", f"Get-Content {KILIT}").izin
    assert hook.komut_degerlendir("YeniKabuk", f"cat {KILIT}").izin
