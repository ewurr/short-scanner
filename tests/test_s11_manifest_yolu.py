"""S-11 (RESULTS §14.44): pytest disinda manifest denetimi bir modul degiskeniyle kapatilamaz; eksik yol hata verir.

Alt surec temiz ortamla (SHORT_LAB_* ve PYTEST_CURRENT_TEST olmadan) yalnizca yerel python calistirir. Aga cikmaz.
"""

from __future__ import annotations

import os
import subprocess
import sys

import config

_KOD = ("import sys; sys.path.insert(0, sys.argv[1])\n"
        "from data import onbellek_manifest as mf\n"
        "{hazir}\n"
        "try:\n"
        "    print({cagri})\n"
        "except Exception as h:\n"
        "    print(type(h).__name__)\n")


def _alt(hazir: str, cagri: str) -> list[str]:
    env = {k: v for k, v in os.environ.items()
           if not k.upper().startswith("SHORT_LAB_") and k.upper() != "PYTEST_CURRENT_TEST"}
    cikti = subprocess.run([sys.executable, "-B", "-c", _KOD.format(hazir=hazir, cagri=cagri), str(config.KOK)],
                           capture_output=True, text=True, check=True, timeout=120, env=env)
    return cikti.stdout.split()


def test_uretimde_denetim_her_zaman_etkin():
    assert _alt("", "mf.denetim_etkin()") == ["True"]
    assert _alt("mf.MANIFEST_YOLU = None", "mf.denetim_etkin()") == ["True"]


def test_uretimde_eksik_manifest_yolu_hata_verir():
    assert _alt("mf.MANIFEST_YOLU = None", "mf._etkin_yol()") == ["ManifestYok"]
    assert _alt("mf.MANIFEST_YOLU = 0", "mf._etkin_yol()") == ["ManifestYok"]


def test_uretimde_gecerli_yol_oldugu_gibi_doner():
    assert _alt("", "mf._etkin_yol() == mf.MANIFEST_YOLU") == ["True"]
