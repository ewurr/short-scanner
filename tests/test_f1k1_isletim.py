"""F1-K1 §3 (RESULTS §14.49 kesintileri; §14.50): isletim engelleri.

1. Bayat kosu kilidi (`calistir.kosu_kilidi(..., bayat_alinir=True)`, esitlik betikleri): kilit sahibinin surec numarasini
   ve baslangic zamanini yazar. Sahibi yasamiyorsa (ya da pid yeniden kullanilmis: baslangic zamani farkli) kilit bayattir
   ve bir uyari yazilarak alinir; sahibi yasiyorsa `KosuKilidiHatasi`. Varsayilan (diger betikler) davranis degismez.
Aga cikmaz; sahte kesif kosusu (gercek kayit yazilmaz).
"""

from __future__ import annotations

import contextlib
import importlib.util
import os
import subprocess
import sys

import pandas as pd
import pytest

import config

DIZIN = config.ANALIZ_DIZINI / "00_veri_denetimi"
sys.path.insert(0, str(DIZIN))


def _yukle(ad: str, dosya: str):
    spec = importlib.util.spec_from_file_location(ad, DIZIN / dosya)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


calistir = _yukle("_f1k1_calistir", "calistir.py")
import esitlik_kapi as ek  # noqa: E402
import esitlik_seri as es  # noqa: E402


def _olmus_pid() -> int:
    """Bitmis bir alt surecin numarasi (sahibi yasamayan kilit icin)."""
    surec = subprocess.Popen([sys.executable, "-c", "pass"])
    surec.wait()
    return surec.pid


# --- 1. Bayat kilit --------------------------------------------------------------------------------------------------

def test_kilit_sahibinin_pid_ve_baslangic_zamanini_yazar(tmp_path):
    with calistir.kosu_kilidi("x", tmp_path) as yol:
        pid, baslangic = calistir._kilit_sahibi(yol.read_text(encoding="utf-8"))
    assert pid == os.getpid()
    assert baslangic == calistir.surec_baslangici(os.getpid()) and baslangic not in (None, "bilinmiyor")


def test_surec_baslangici_yasayan_ve_olmus_surec():
    assert calistir.surec_baslangici(os.getpid()) not in (None, "bilinmiyor")
    assert calistir.surec_baslangici(_olmus_pid()) is None
    assert calistir.surec_baslangici(0) is None and calistir.surec_baslangici(-5) is None


def test_sahibi_olmus_kilit_uyariyla_alinir(tmp_path, capsys):
    yol = tmp_path / ".x.kilit"
    yol.write_text(f"pid={_olmus_pid()} surec_baslangici=123 baslangic_utc=2026-11-01_00:00:00\n", encoding="utf-8")
    with calistir.kosu_kilidi("x", tmp_path, bayat_alinir=True) as alinan:
        assert calistir._kilit_sahibi(alinan.read_text(encoding="utf-8"))[0] == os.getpid()
    assert "bayat kosu kilidi alindi" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []                    # bayat kopya kalmaz, kilit birakildi


def test_eski_bicimli_sahibi_olmus_kilit_alinir(tmp_path):
    (tmp_path / ".x.kilit").write_text(f"pid={_olmus_pid()} baslangic_utc=2026-11-01 00:00:00\n", encoding="utf-8")
    with calistir.kosu_kilidi("x", tmp_path, bayat_alinir=True):
        pass


def test_yasayan_sahibin_kilidi_alinmaz(tmp_path):
    yol = tmp_path / ".x.kilit"
    metin = f"pid={os.getpid()} surec_baslangici={calistir.surec_baslangici(os.getpid())} baslangic_utc=x\n"
    yol.write_text(metin, encoding="utf-8")
    with pytest.raises(calistir.KosuKilidiHatasi, match="zaten calisiyor"):
        with calistir.kosu_kilidi("x", tmp_path, bayat_alinir=True):
            pytest.fail("yasayan sahibin kilidi alinmamali")
    assert yol.read_text(encoding="utf-8") == metin


def test_yasayan_sahip_baslangic_bilinmiyorsa_kilit_alinmaz(tmp_path):
    (tmp_path / ".x.kilit").write_text(f"pid={os.getpid()}\n", encoding="utf-8")
    with pytest.raises(calistir.KosuKilidiHatasi):
        with calistir.kosu_kilidi("x", tmp_path, bayat_alinir=True):
            pass


def test_pid_yeniden_kullanildiysa_baslangic_zamani_farkli_kilit_bayat(tmp_path, capsys):
    """Kilitteki pid yasayan bir surece (bu surec) ait, ama baslangic zamani farkli: pid yeniden kullanilmis."""
    (tmp_path / ".x.kilit").write_text(f"pid={os.getpid()} surec_baslangici=1 baslangic_utc=x\n", encoding="utf-8")
    with calistir.kosu_kilidi("x", tmp_path, bayat_alinir=True):
        pass
    assert "bayat kosu kilidi alindi" in capsys.readouterr().err


def test_okunamayan_sahip_bayat_sayilmaz(tmp_path):
    (tmp_path / ".x.kilit").write_text("bozuk icerik\n", encoding="utf-8")
    with pytest.raises(calistir.KosuKilidiHatasi):
        with calistir.kosu_kilidi("x", tmp_path, bayat_alinir=True):
            pass


def test_varsayilan_davranis_degismez_olmus_sahip_de_reddedilir(tmp_path):
    (tmp_path / ".x.kilit").write_text(f"pid={_olmus_pid()} surec_baslangici=1\n", encoding="utf-8")
    with pytest.raises(calistir.KosuKilidiHatasi):
        with calistir.kosu_kilidi("x", tmp_path):
            pass


def test_alma_sirasinda_kilit_yenilendiyse_geri_konur_ve_reddedilir(tmp_path, monkeypatch):
    """Bayat okunduktan sonra baska bir kosu kilidi yeniledi (tasinan dosyanin icerigi farkli): yeni kilit geri konur."""
    yol = tmp_path / ".x.kilit"
    yol.write_text(f"pid={_olmus_pid()} surec_baslangici=1\n", encoding="utf-8")
    yeni = f"pid={os.getpid()} surec_baslangici={calistir.surec_baslangici(os.getpid())}\n"
    asil = calistir.kilit_bayat_mi

    def araya_giren(metin):
        sonuc = asil(metin)
        yol.write_text(yeni, encoding="utf-8")            # baska kosu kilidi yeniledi
        return sonuc

    monkeypatch.setattr(calistir, "kilit_bayat_mi", araya_giren)
    with pytest.raises(calistir.KosuKilidiHatasi):
        with calistir.kosu_kilidi("x", tmp_path, bayat_alinir=True):
            pass
    assert yol.read_text(encoding="utf-8") == yeni
    assert [p.name for p in tmp_path.iterdir()] == [".x.kilit"]


@pytest.mark.parametrize("modul, argv", [
    (ek, ["--bar", "ornek", "--sembol", "YOK", "--etiket", "pytest_f1k1"]),
    (es, ["--sembol", "YOK", "--etiket", "pytest_f1k1"]),
])
def test_esitlik_betikleri_bayat_kilidi_alir(monkeypatch, modul, argv):
    gorulen = []

    @contextlib.contextmanager
    def kilit(ad, dizin=None, **k):
        gorulen.append(k)
        yield None

    monkeypatch.setattr(calistir_gercek(), "kosu_kilidi", kilit)
    monkeypatch.setattr(modul, "kos", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("dur")))
    modul.main(argv)
    assert gorulen == [{"bayat_alinir": True}]


def calistir_gercek():
    """Betiklerin `from calistir import ...` ile aldigi modul (sys.path'teki `calistir`)."""
    import calistir as c

    return c
