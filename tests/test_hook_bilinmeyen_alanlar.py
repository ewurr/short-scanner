"""F1 kapatma turu madde 1e: hook'un kanal duzeyindeki boslugu.

Bulgu 18: `main()` komut ve yol alanlarini SABIT listelerden okuyordu, bu yuzden hicbir listede
bulunmayan bir alan (`destination`, `new_path`, `code`, `commands`, ic ice bir sozlukteki
`file_path`) FAIL-OPEN geciyordu. Denetlenmeyen bir GIRIS, denetlenmemis bir komut biciminden
farklidir: PowerShell boslugu gibi kanal duzeyinde bir acikliktir.

Kapanis: `tool_input` ic ice gezilir ve her alan uc daldan birine girer --
  1. adi `KOMUT_ALANLARI` icinde olan alan: tam komut degerlendirmesi (kod alanlarinda ayrica
     kilitli adin anilmasi temkinli reddir),
  2. adi `YOL_ALANLARI` icinde olan alan: yol denetimi (salt okuma araclarinda muaf),
  3. BILINMEYEN alan: degeri tek basina kilitli bir yolsa reddedilir; komut olarak KESIN red
     veriyorsa reddedilir; yalnizca temkinli red veren serbest metin (`description`) gecer.

Hangi alanlarin denetlendigi `tests/test_hook_kabuk_araclari.py::test_denetlenen_arac_listesi`
icinde yazilidir. Komutlar hicbir zaman CALISTIRILMAZ; yalnizca metin olarak degerlendirilir.
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
_SPEC = importlib.util.spec_from_file_location("kilit_hook_alanlar", _YOL)
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


# --- 1. Bilinmeyen YOL alanlari --------------------------------------------------------------


@pytest.mark.parametrize("alan", ["destination", "new_path", "target", "hedef", "output_path",
                                  "dest", "to", "yol2"])
@pytest.mark.parametrize("dosya", [ONKAYIT, ANAYASA, ONAY, BOLME, KILIT])
def test_bilinmeyen_yol_alani_reddedilir(monkeypatch, capsys, alan, dosya):
    """Dayanak: madde 1e (bulgu 18). Hicbir listede olmayan bir alanda gelen kilitli yol."""
    girdi = {"tool_name": "YeniArac", "tool_input": {alan: dosya}}
    assert '"deny"' in _calistir(monkeypatch, capsys, girdi), (alan, dosya)


def test_ic_ice_sozlukteki_yol_alani_reddedilir(monkeypatch, capsys):
    """Dayanak: madde 1e. Alan ic ice bir sozlukte ya da listede olabilir."""
    girdi = {"tool_name": "CokluDuzenleme",
             "tool_input": {"edits": [{"file_path": "README.md"}, {"file_path": ANAYASA}]}}
    assert '"deny"' in _calistir(monkeypatch, capsys, girdi)


def test_ic_ice_komut_alani_reddedilir(monkeypatch, capsys):
    """Dayanak: madde 1e. Ic ice yapidaki komut alani da denetlenir."""
    girdi = {"tool_name": "Toplu", "tool_input": {"adimlar": [{"command": "echo ok"},
                                                              {"command": f"rm {ONAY}"}]}}
    assert '"deny"' in _calistir(monkeypatch, capsys, girdi)


# --- 2. Bilinmeyen KOMUT alanlari ------------------------------------------------------------


@pytest.mark.parametrize("alan", ["commands", "shell", "run", "args", "argv", "arguments", "input"])
def test_bilinmeyen_komut_alani_denetlenir(monkeypatch, capsys, alan):
    """Dayanak: madde 1e. Komut tasiyan yeni bir alan adi sessizce gecmez."""
    girdi = {"tool_name": "Bash", "tool_input": {alan: f"echo x > {ONKAYIT}"}}
    assert '"deny"' in _calistir(monkeypatch, capsys, girdi), alan


def test_liste_bicimli_bilinmeyen_komut_alani_denetlenir(monkeypatch, capsys):
    """Dayanak: madde 1e. `argv` biciminde gelen komut parcalari birlestirilerek denetlenir."""
    girdi = {"tool_name": "Bash", "tool_input": {"argv": ["rm", "-f", ANAYASA]}}
    assert '"deny"' in _calistir(monkeypatch, capsys, girdi)


@pytest.mark.parametrize("alan", hook.KOD_ALANLARI)
def test_kod_alani_kilitli_adi_aniyorsa_temkinli_reddedilir(monkeypatch, capsys, alan):
    """Dayanak: madde 1e. Program metni kabuk kurallariyla siniflandirilamaz: anma yeter."""
    girdi = {"tool_name": "Python", "tool_input": {alan: f'open("{ONKAYIT}", "w").write("x")'}}
    cikti = _calistir(monkeypatch, capsys, girdi)
    assert '"deny"' in cikti and "TEMKINLI" in cikti, alan


# --- 3. Yanlis pozitif sinirlari -------------------------------------------------------------


def test_serbest_metin_alani_kilitli_adi_anabilir(monkeypatch, capsys):
    """Dayanak: madde 1e. `description` gibi serbest metin yazma niyeti tasimaz; komut ayrica denetlenir."""
    girdi = {"tool_name": "Bash", "tool_input": {"command": f"cat {ONKAYIT}",
                                                 "description": f"{ONKAYIT} dosyasini oku"}}
    assert _calistir(monkeypatch, capsys, girdi) == ""


def test_okuma_aracinda_bilinmeyen_yol_alani_gecer(monkeypatch, capsys):
    """Dayanak: madde 1e + bulgu P-B1. Kilit yazmaya karsidir: okuma araci muaf kalir."""
    girdi = {"tool_name": "Read", "tool_input": {"hedef": ONKAYIT, "offset": 1}}
    assert _calistir(monkeypatch, capsys, girdi) == ""


def test_okuma_aracinda_komut_alani_yine_denetlenir(monkeypatch, capsys):
    """Dayanak: madde 1e. Muafiyet YOL dalina aittir; komut alani arac adina bakilmadan denetlenir."""
    girdi = {"tool_name": "Read", "tool_input": {"run": f"rm {ANAYASA}"}}
    assert '"deny"' in _calistir(monkeypatch, capsys, girdi)


def test_kilitli_olmayan_yol_ve_sayi_alanlari_gecer(monkeypatch, capsys):
    """Olumlu kontrol: siradan bir girdi reddedilmez."""
    girdi = {"tool_name": "Write", "tool_input": {"file_path": "analysis/00_veri_denetimi/RESULTS.md",
                                                  "content": "x", "limit": 5, "flag": True,
                                                  "nested": {"a": [1, 2, "README.md"]}}}
    assert _calistir(monkeypatch, capsys, girdi) == ""


# --- 4. Gezicinin kendisi --------------------------------------------------------------------


def test_girdi_gezicisi_butun_alanlari_uretir():
    """Dayanak: madde 1e. `_girdi_alanlari` ic ice sozluk ve listeleri gezer, metin listesini birakir."""
    girdi = {"a": "1", "b": {"c": "2"}, "d": [{"e": "3"}], "f": ["sed", "-i", "x"]}
    bulunan = {(alan, tuple(deger) if isinstance(deger, list) else deger)
               for _, alan, deger in hook._girdi_alanlari(girdi)}
    assert ("a", "1") in bulunan and ("c", "2") in bulunan and ("e", "3") in bulunan
    assert ("f", ("sed", "-i", "x")) in bulunan

@pytest.mark.parametrize("alan", hook.ICERIK_ALANLARI)
def test_icerik_alani_komut_olarak_degerlendirilmez(monkeypatch, capsys, alan):
    """Dayanak: madde 1e. Dosya METNI komut degil veridir; hedef yol ayrica denetlenir.

    Gerekce: saldiri bicimlerini BELGELEYEN bir metin (RESULTS "acik noktalar" bolumu) komut gibi
    okunursa yazilamaz, yani kilit belgelemeye karsi calisirdi.
    """
    girdi = {"tool_name": "Write",
             "tool_input": {"file_path": "analysis/00_veri_denetimi/RESULTS.md",
                            alan: f"Ornek saldiri bicimi: `rm {ANAYASA}` ve `sed -i s/a/b/ {ONKAYIT}`."}}
    assert _calistir(monkeypatch, capsys, girdi) == "", alan


def test_icerik_alani_kilitli_hedefi_kurtarmaz(monkeypatch, capsys):
    """Dayanak: madde 1e. Icerik muafiyeti HEDEFI serbest birakmaz: kilitli yol yine reddedilir."""
    girdi = {"tool_name": "Write", "tool_input": {"file_path": ONKAYIT, "content": "zararsiz metin"}}
    assert '"deny"' in _calistir(monkeypatch, capsys, girdi)
