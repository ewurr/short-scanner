"""Hook: PowerShell'de git komutlarinin siniflandirilmasi (RESULTS §14.38).

Bulgu: PowerShell yolunda git icin dal yoktu. Salt okuma komutu kilitli dosyayi aninca temkinli
reddediliyor, kilitli dosyayi anmayan yikici komut (`git reset --hard`) geciyordu. Ilke esdegerlik:
her git komutunda PowerShell karari Bash kararina esittir, Bash kararlari degismez.

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
_SPEC = importlib.util.spec_from_file_location("kilit_hook_ps_git", _YOL)
hook = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = hook      # dataclass modulun kayitli olmasini bekler
_SPEC.loader.exec_module(hook)

# Tek tablo: komut, sonra Bash'in degisiklikten ONCEKI (d239d27) tam karari:
# izin, kalip, neden, belirsiz. Satirlar o kodun olcumunden uretildi, elle yazilmadi.
TABLO = [
    ('git checkout .',
     False, 'PREREGISTRATION.md', '`git checkout` calisma agacini degistirir ve kilitli dosyalara dokunabilir', False),
    ('git checkout -- PREREGISTRATION.md',
     False, 'PREREGISTRATION.md', '`git checkout` calisma agacini degistirir ve kilitli dosyalara dokunabilir', False),
    ('git checkout -- analysis/H2/KILIT.md',
     False, 'analysis/*/KILIT.md', '`git checkout` calisma agacini degistirir ve kilitli dosyalara dokunabilir', False),
    ('git checkout HEAD~1 -- PREREGISTRATION.md',
     False, 'PREREGISTRATION.md', '`git checkout` calisma agacini degistirir ve kilitli dosyalara dokunabilir', False),
    ('git checkout HEAD~1 -- analysis/H2/KILIT.md',
     False, 'analysis/*/KILIT.md', '`git checkout` calisma agacini degistirir ve kilitli dosyalara dokunabilir', False),
    ('git restore .',
     False, 'PREREGISTRATION.md', '`git restore` calisma agacini degistirir ve kilitli dosyalara dokunabilir', False),
    ('git restore PREREGISTRATION.md',
     False, 'PREREGISTRATION.md', '`git restore` calisma agacini degistirir ve kilitli dosyalara dokunabilir', False),
    ('git restore analysis/H2/KILIT.md',
     False, 'analysis/*/KILIT.md', '`git restore` calisma agacini degistirir ve kilitli dosyalara dokunabilir', False),
    ('git restore --source=HEAD~1 PREREGISTRATION.md',
     False, 'PREREGISTRATION.md', '`git restore` calisma agacini degistirir ve kilitli dosyalara dokunabilir', False),
    ('git restore --source=HEAD~1 analysis/H2/KILIT.md',
     False, 'analysis/*/KILIT.md', '`git restore` calisma agacini degistirir ve kilitli dosyalara dokunabilir', False),
    ('git reset --hard',
     False, 'PREREGISTRATION.md', '`git reset --hard` calisma agacini degistirir', False),
    ('git reset --hard HEAD~1',
     False, 'PREREGISTRATION.md', '`git reset --hard HEAD~1` calisma agacini degistirir', False),
    ('git stash',
     False, 'PREREGISTRATION.md', '`git stash` calisma agacini degistirir ve kilitli dosyalara dokunabilir', False),
    ('git stash push',
     False, 'PREREGISTRATION.md', '`git stash` calisma agacini degistirir ve kilitli dosyalara dokunabilir', False),
    ('git stash pop',
     False, 'PREREGISTRATION.md', '`git stash` calisma agacini degistirir ve kilitli dosyalara dokunabilir', False),
    ('git stash drop',
     False, 'PREREGISTRATION.md', '`git stash` calisma agacini degistirir ve kilitli dosyalara dokunabilir', False),
    ('git clean -fd',
     False, 'PREREGISTRATION.md', '`git clean` calisma agacini degistirir ve kilitli dosyalara dokunabilir', False),
    ('git clean -fdx',
     False, 'PREREGISTRATION.md', '`git clean` calisma agacini degistirir ve kilitli dosyalara dokunabilir', False),
    ('git rm PREREGISTRATION.md',
     False, 'PREREGISTRATION.md', '`git rm` kilitli dosyayi tasiyor/siliyor', False),
    ('git rm analysis/H2/KILIT.md',
     False, 'analysis/*/KILIT.md', '`git rm` kilitli dosyayi tasiyor/siliyor', False),
    ('git mv PREREGISTRATION.md x.md',
     False, 'PREREGISTRATION.md', '`git mv` kilitli dosyayi tasiyor/siliyor', False),
    ('git mv analysis/H2/KILIT.md x.md',
     False, 'analysis/*/KILIT.md', '`git mv` kilitli dosyayi tasiyor/siliyor', False),
    ('git commit --amend',
     True, None, '', False),
    ('git push --force',
     True, None, '', False),
    ('git push -f',
     True, None, '', False),
    ('git rebase -i HEAD~3',
     False, 'PREREGISTRATION.md', '`git rebase` calisma agacini degistirir ve kilitli dosyalara dokunabilir', False),
    ('git status',
     True, None, '', False),
    ('git log --oneline -3',
     True, None, '', False),
    ('git log -- PREREGISTRATION.md',
     True, None, '', False),
    ('git log -- analysis/H2/KILIT.md',
     True, None, '', False),
    ('git log --format="%h %ad %s" --date=iso ec9b1a6..HEAD -- PREREGISTRATION.md',
     True, None, '', False),
    ('git log --format="%h %ad %s" --date=iso ec9b1a6..HEAD -- analysis/H2/KILIT.md',
     True, None, '', False),
    ('git show HEAD:PREREGISTRATION.md',
     True, None, '', False),
    ('git show HEAD:analysis/H2/KILIT.md',
     True, None, '', False),
    ('git diff -- PREREGISTRATION.md',
     True, None, '', False),
    ('git diff -- analysis/H2/KILIT.md',
     True, None, '', False),
    ('git blame PREREGISTRATION.md',
     True, None, '', False),
    ('git blame analysis/H2/KILIT.md',
     True, None, '', False),
    ('git ls-files',
     True, None, '', False),
    ('git fetch',
     True, None, '', False),
    ('git add README.md',
     True, None, '', False),
    ('git add PREREGISTRATION.md',
     True, None, '', False),
    ('git add analysis/H2/KILIT.md',
     True, None, '', False),
    ('git commit -m "x"',
     True, None, '', False),
    ('git push',
     True, None, '', False),
    ('git status; git reset --hard',
     False, 'PREREGISTRATION.md', '`git reset --hard` calisma agacini degistirir', False),
    ('git log -- PREREGISTRATION.md | Select-Object -First 3',
     True, None, '', False),
    ('git log -- analysis/H2/KILIT.md | Select-Object -First 3',
     True, None, '', False),
    ('cd D:\\Projeler\\short_scanner; git clean -fd',
     False, 'PREREGISTRATION.md', '`git clean` calisma agacini degistirir ve kilitli dosyalara dokunabilir', False),
    ('git status && git reset --hard',
     False, 'PREREGISTRATION.md', '`git reset --hard` calisma agacini degistirir', False),
    ('& git reset --hard',
     False, 'PREREGISTRATION.md', '`git reset --hard` calisma agacini degistirir', False),
    ('git.exe reset --hard',
     False, 'PREREGISTRATION.md', '`git reset --hard` calisma agacini degistirir', False),
    ('& "git" clean -fd',
     False, 'PREREGISTRATION.md', '`git clean` calisma agacini degistirir ve kilitli dosyalara dokunabilir', False),
]


@pytest.mark.parametrize("komut,izin,kalip,neden,belirsiz", TABLO, ids=[s[0] for s in TABLO])
def test_powershell_karari_bash_kararina_esit(komut, izin, kalip, neden, belirsiz):
    bash = hook.bash_degerlendir(komut)
    ps = hook.powershell_degerlendir(komut)
    assert bash.izin is izin, komut
    assert ps.izin is izin, f"{komut} -> {ps.neden}"
    assert ps.izin is bash.izin, komut


@pytest.mark.parametrize("komut,izin,kalip,neden,belirsiz", TABLO, ids=[s[0] for s in TABLO])
def test_bash_karari_degismedi(komut, izin, kalip, neden, belirsiz):
    """Regresyon: yalniz izin degil, gerekce dahil tam karar degisiklik oncesiyle ayni."""
    assert hook.bash_degerlendir(komut) == hook.Karar(izin=izin, kalip=kalip, neden=neden, belirsiz=belirsiz)


def test_tablo_beklenen_buyuklukte():
    """Tablodan sessizce satir dusmesin; RESULTS §14.38'in sayilari bu tabloya dayanir."""
    assert len(TABLO) == 53
    assert len({s[0] for s in TABLO}) == 53


def test_git_siniflari_tek_kaynakta():
    """Iki lehce ayni fonksiyonu kullanir: fonksiyon degisirse ikisinin karari birlikte degisir."""
    for argumanlar, izin in ((["git", "reset", "--hard"], False), (["git.exe", "log"], True)):
        assert hook._git_karari(argumanlar).izin is izin


@pytest.mark.parametrize("komut", [
    "git checkout -b yeni-dal", "git stash list", "git reset HEAD README.md",
])
def test_dar_istisnalar_powershellde_de_gecer(komut):
    assert hook.powershell_degerlendir(komut).izin, komut


# Kapsam disi (RESULTS §14.38): bu turda DEGISMEDI. Karar degisirse bu test fark eder; "dogru"
# davranis oldugunu soylemez, bazilari acik yoldur.
@pytest.mark.parametrize("komut,izin", [
    ("Start-Process git reset --hard", True),
    ("Start-Process git log -- PREREGISTRATION.md", False),
    ('Start-Process git -ArgumentList "reset --hard"', True),
    ('Invoke-Expression "git reset --hard"', True),
    ('iex "git reset --hard"', True),
    ("cmd /c git reset --hard", True),
    (". git reset --hard", True),
    ("sudo git reset --hard", True),
    ("g`it reset --hard", True),
    ('git log -- PREREGISTRATION.md "kapanmamis', False),
    ("git commit -m @'\nPREREGISTRATION.md revizyonu\n'@", False),
])
def test_kapsam_disi_powershell_yazimlari_degismedi(komut, izin):
    assert hook.powershell_degerlendir(komut).izin is izin, komut


@pytest.mark.parametrize("komut,red", [
    ("git reset --hard", True),
    ("git clean -fd", True),
    ("git log -- PREREGISTRATION.md", False),
    ("git log -- analysis/H2/KILIT.md", False),
])
def test_main_powershell_araci_uzerinden(monkeypatch, capsys, komut, red):
    monkeypatch.delenv(hook.ACMA_DEGISKENI, raising=False)
    girdi = {"tool_name": "PowerShell", "tool_input": {"command": komut}}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(girdi)))
    assert hook.main() == 0
    assert ('"deny"' in capsys.readouterr().out) is red, komut
