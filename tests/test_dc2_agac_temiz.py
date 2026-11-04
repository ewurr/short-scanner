"""D-C2 (RESULTS §14.44): kesif kaydinin `agac_temiz` alani `--assume-unchanged` ve `--skip-worktree` isaretli dosyalari
da kirli sayar (`git status --porcelain` bu dosyalari gostermez). Gercek gecici git deposu; aga cikmaz."""

from __future__ import annotations

import pytest

from data import split
from onay_yardimcisi import gecici_depo, git


def _izlenen(depo):
    return next(y for y in git(depo, "ls-files").splitlines() if y)


def test_temiz_depoda_agac_temiz(tmp_path):
    depo = gecici_depo(tmp_path)
    assert git(depo, "status", "--porcelain").strip() == ""
    assert split._kesif_kaydi_kur(None).agac_temiz is True


@pytest.mark.parametrize("bayrak", ["--assume-unchanged", "--skip-worktree"])
def test_isaretli_ve_degistirilmis_dosya_agaci_kirli_yapar(tmp_path, bayrak):
    depo = gecici_depo(tmp_path)
    yol = _izlenen(depo)
    git(depo, "update-index", bayrak, yol)
    (depo / yol).write_bytes((depo / yol).read_bytes() + b"\nek\n")
    assert git(depo, "status", "--porcelain").strip() == ""      # git status bunu gormez
    assert split._kesif_kaydi_kur(None).agac_temiz is False


def test_degisiklik_status_ile_de_kirli(tmp_path):
    depo = gecici_depo(tmp_path)
    yol = _izlenen(depo)
    (depo / yol).write_bytes((depo / yol).read_bytes() + b"\nek\n")
    assert split._kesif_kaydi_kur(None).agac_temiz is False
