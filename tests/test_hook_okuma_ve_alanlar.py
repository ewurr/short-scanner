"""Hook'un koruma turunda ortaya cikan uc gerilemesi: P-B1, P-C4, P-C5 (madde 8 denetimi).

- **P-B1 (agir).** Madde 1a eslestiriciyi `.*` yapti, yani artik OKUMA araclari da hook'a ugruyor;
  yol dali ise aracin yazip yazmadigina bakmadigi icin `Read`/`Grep` cagrilari da reddediliyordu.
  Sonucu agirdi: metodoloji denetcisi on-kayit metnini OKUYAMADI ve "on-kayittan sapma" basligini
  hic denetleyemedi (CLAUDE.md §5 o denetimi zorunlu kilar; ayni §5 hook'un gorevini "yazma ve
  duzenleme arac cagrilarini reddeder" diye tanimlar). F2'de ayni sorun `analysis/<hipotez>/KILIT.md`
  olusur olusmaz o dosyayi da denetciye okunamaz yapardi.
- **P-C4.** Yalnizca ILK bulunan komut alani denetleniyordu; iki komut alani tasiyan girdide ikinci
  alandaki yazma geciyordu. Liste biciminde komut (`argv`) hic denetlenmiyordu.
- **P-C5.** Yol dali ilk BULUNAN alanda duruyordu; zararsiz bir `path` degeri ayni girdideki kilitli
  `filePath`in denetlenmesini engelliyordu.

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
_SPEC = importlib.util.spec_from_file_location("kilit_hook_okuma", _YOL)
hook = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = hook
_SPEC.loader.exec_module(hook)

KILIT = "analysis/h1/" + "KILIT" + ".md"
ONAY = "ON" + "AY_KAYDI.md"
ANAYASA = "CLA" + "UDE" + ".md"
ONKAYIT = "PREREG" + "ISTRATION.md"
BOLME = "data/spl" + "it.csv"


def _calistir(monkeypatch, capsys, girdi: dict) -> str:
    monkeypatch.delenv(hook.ACMA_DEGISKENI, raising=False)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(girdi)))
    assert hook.main() == 0
    return capsys.readouterr().out


# --- 1. P-B1: salt okuma araclari kilitli dosyayi okuyabilir ---------------------------------


@pytest.mark.parametrize("girdi", [
    {"tool_name": "Read", "tool_input": {"file_path": ONKAYIT}},
    {"tool_name": "Read", "tool_input": {"file_path": ANAYASA}},
    {"tool_name": "Read", "tool_input": {"file_path": KILIT}},
    {"tool_name": "Grep", "tool_input": {"path": ONKAYIT, "pattern": "madde"}},
    {"tool_name": "Grep", "tool_input": {"path": ONAY, "pattern": "BITTI"}},
    {"tool_name": "Glob", "tool_input": {"path": "analysis", "pattern": "*/KILIT.md"}},
    {"tool_name": "LS", "tool_input": {"path": "data"}},
    {"tool_name": "NotebookRead", "tool_input": {"notebook_path": ANAYASA}},
    {"tool_name": "Read", "tool_input": {"file_path": BOLME}},
])
def test_salt_okuma_araci_reddedilmez(monkeypatch, capsys, girdi):
    assert _calistir(monkeypatch, capsys, girdi) == "", girdi


def test_okuma_araclari_listesi_testte_yazili():
    """Liste degisirse bu test fark etsin (madde 1a'nin "denetlenen araclar testte yazili" kurali)."""
    assert hook.OKUMA_ARACLARI == frozenset({"read", "grep", "glob", "ls", "notebookread",
                                             "readfile", "readmanyfiles"})


@pytest.mark.parametrize("arac", ["Write", "Edit", "NotebookEdit", "YeniEditor", "", None])
def test_yazma_ve_taninmayan_araclar_hala_reddedilir(monkeypatch, capsys, arac):
    """Muafiyet YALNIZCA salt okuma araclarina ait: taninmayan bir arac yol tasiyorsa denetlenir."""
    girdi = {"tool_name": arac, "tool_input": {"file_path": ONKAYIT}}
    assert '"deny"' in _calistir(monkeypatch, capsys, girdi), arac


def test_okuma_araci_komut_tasiyorsa_yine_denetlenir(monkeypatch, capsys):
    """Muafiyet yol dalina aittir; komut alani varsa arac adi ne olursa olsun denetlenir."""
    girdi = {"tool_name": "Read", "tool_input": {"command": f"echo x > {KILIT}"}}
    assert '"deny"' in _calistir(monkeypatch, capsys, girdi)


def test_write_edit_yolu_degismedi(monkeypatch, capsys):
    """Alti tam yol girdisinin Write korumasi aynen duruyor."""
    for yol in (ONKAYIT, BOLME, "data/universe.csv", "data/exchange_info_anlik.json", ONAY,
                ANAYASA, KILIT):
        girdi = {"tool_name": "Write", "tool_input": {"file_path": yol}}
        assert '"deny"' in _calistir(monkeypatch, capsys, girdi), yol


# --- 2. P-C4: butun komut alanlari ve liste komutlar -----------------------------------------


@pytest.mark.parametrize("girdi", [
    {"tool_name": "YeniKabuk", "tool_input": {"command": "echo ok", "script": f"rm {ANAYASA}"}},
    {"tool_name": "YeniKabuk", "tool_input": {"cmd": "ls", "komut": f"Set-Content {KILIT} x"}},
    {"tool_name": "YeniKabuk", "tool_input": {"command": "echo ok", "cmd": "echo ok",
                                              "script": f"sed -i s/a/b/ {BOLME}"}},
    {"tool_name": "PowerShell", "tool_input": {"command": "Get-ChildItem",
                                               "script": f"Remove-Item {ONAY}"}},
])
def test_butun_komut_alanlari_denetlenir(monkeypatch, capsys, girdi):
    assert '"deny"' in _calistir(monkeypatch, capsys, girdi), girdi


@pytest.mark.parametrize("girdi", [
    {"tool_name": "YeniKabuk", "tool_input": {"command": ["sed", "-i", "s/a/b/", ANAYASA]}},
    {"tool_name": "YeniKabuk", "tool_input": {"command": ("rm", "-f", ONAY)}},
    {"tool_name": "YeniKabuk", "tool_input": {"script": ["Remove-Item", KILIT]}},
    {"tool_name": "Bash", "tool_input": {"command": ["tee", "-a", ONKAYIT]}},
])
def test_liste_biciminde_komut_da_denetlenir(monkeypatch, capsys, girdi):
    assert '"deny"' in _calistir(monkeypatch, capsys, girdi), girdi


@pytest.mark.parametrize("girdi", [
    {"tool_name": "YeniKabuk", "tool_input": {"command": ["echo", "ok"]}},
    {"tool_name": "YeniKabuk", "tool_input": {"command": ["cat", ANAYASA]}},
    {"tool_name": "YeniKabuk", "tool_input": {"command": [], "script": ""}},
    {"tool_name": "YeniKabuk", "tool_input": {"command": "echo ok", "script": "ls analysis"}},
])
def test_zararsiz_komutlar_gecer(monkeypatch, capsys, girdi):
    assert _calistir(monkeypatch, capsys, girdi) == "", girdi


def test_liste_komutta_bosluklu_yol_bozulmaz(monkeypatch, capsys):
    """Liste parcalari tirnaklanarak birlestirilir; bosluk iceren yol tek token kalir."""
    girdi = {"tool_name": "YeniKabuk", "tool_input": {"command": ["rm", "bir dosya.md"]}}
    assert _calistir(monkeypatch, capsys, girdi) == ""


# --- 3. P-C5: yol dali ilk KILITLI alanda durur ----------------------------------------------


@pytest.mark.parametrize("girdi", [
    {"tool_name": "YeniEditor", "tool_input": {"path": ".", "filePath": ANAYASA}},
    {"tool_name": "YeniEditor", "tool_input": {"path": "README.md", "file_path": BOLME}},
    {"tool_name": "YeniEditor", "tool_input": {"notebook_path": "a.ipynb", "path": ONAY}},
    {"tool_name": "Write", "tool_input": {"path": "notlar.md", "file_path": KILIT}},
])
def test_yol_dali_ilk_kilitli_alanda_durur(monkeypatch, capsys, girdi):
    assert '"deny"' in _calistir(monkeypatch, capsys, girdi), girdi


def test_kilitli_olmayan_yol_alanlari_gecer(monkeypatch, capsys):
    girdi = {"tool_name": "Write", "tool_input": {"path": "analysis/h1/notlar.md",
                                                  "file_path": "analysis/h1/baska.md"}}
    assert _calistir(monkeypatch, capsys, girdi) == ""


def test_kilit_acikken_okuma_ve_yazma_gecer(monkeypatch, capsys):
    monkeypatch.setenv(hook.ACMA_DEGISKENI, "1")
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(
        {"tool_name": "Write", "tool_input": {"file_path": ONKAYIT}})))
    assert hook.main() == 0
    assert capsys.readouterr().out == ""
