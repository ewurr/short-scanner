"""Onay kosusu test yardimcilari (onay kaydi ve kosu butunlugu turu, denetci KS3 D-B1, D-B3).

Kayit yolu artik `config.ONAY_KAYDI` monkeypatch'iyle degistirilemez; testler `split._test_kaydi_ayarla` ile
kendi testleri suresince gecici bir kayda yonlenir (git ortami da orada sahte: temiz agac, sabit commit).

Onay kosusu blogu sonuc bildirilmeden biterse `OnaySonucuYok` verir. Kosuyu yalnizca erisim acmak icin kullanan
testler `kosu(...)` ile acar: blok hatasiz biterse sonuc "TEST" bildirilir; blok icindeki hata aynen yukari cikar.

Onay kaydi ikinci tur (denetci OK D-B1): `gecici_depo` gecici bir git deposu kurar ve kaydi oraya yonlendirir;
bu kipte git islemleri (temiz agac, HEAD, gecmis, commit) gercekten yapilir.
"""

from __future__ import annotations

import subprocess
from contextlib import contextmanager

from data import split

DEPO_KAYIT_BASLIGI = (
    "# ONAY_KAYDI.md (test)\n\n| Tarih (UTC) | Kume | Cagiran betik | Commit | Not |\n|---|---|---|---|---|\n\n"
    "Henuz onay kosusu yok.\n"
)
DEPO_BETIGI = "analysis/onay_betigi.py"


def gecici_kayit(yol, **ortam):
    """Bu test suresince onay kaydini `yol`a yonlendirir; `ortam` `split._test_kaydi_ayarla`ya gider."""
    return split._test_kaydi_ayarla(yol, **ortam)


def git(depo, *argumanlar) -> str:
    """Test deposunda git komutu; basarisizlikta CalledProcessError."""
    return subprocess.run(["git", *argumanlar], cwd=depo, check=True, capture_output=True, text=True,
                          encoding="utf-8").stdout


def gecici_depo(kok):
    """`kok/depo` altinda gercek bir git deposu kurar (kayit dosyasi ve izlenen bir betik commit edilmis) ve bu
    test suresince onay kaydini oraya yonlendirir. Doner: depo yolu. Kayit: `depo / "ONAY_KAYDI.md"`.

    Onay kaydi kapanis turu: `kok/uzak.git` ciplak bir depo `origin` olarak eklenir ve `main` oraya itilir (dosya
    yolu uzerinden; aga cikilmaz). Uzak depo: `uzak_depo(depo)`."""
    depo = kok / "depo"
    (depo / "analysis").mkdir(parents=True)
    git(depo, "init", "-q")
    git(depo, "checkout", "-q", "-b", "main")
    for anahtar, deger in [("user.name", "Test"), ("user.email", "test@example.invalid"),
                           ("core.autocrlf", "false"), ("commit.gpgsign", "false"), ("core.hooksPath", ".git/hooks")]:
        git(depo, "config", anahtar, deger)
    (depo / "ONAY_KAYDI.md").write_text(DEPO_KAYIT_BASLIGI, encoding="utf-8", newline="")
    (depo / DEPO_BETIGI).write_text("# onay betigi (test)\n", encoding="utf-8")
    git(depo, "add", ".")
    git(depo, "commit", "-q", "-m", "ilk")
    uzak = kok / "uzak.git"
    git(kok, "init", "-q", "--bare", str(uzak))
    git(depo, "remote", "add", "origin", str(uzak))
    git(depo, "push", "-q", "origin", "main")
    git(depo, "fetch", "-q", "origin")
    split._test_kaydi_ayarla(depo / "ONAY_KAYDI.md", depo=depo, betik=DEPO_BETIGI)
    return depo


def uzak_depo(depo):
    """`gecici_depo`nun ciplak uzak deposu."""
    return depo.parent / "uzak.git"


@contextmanager
def kosu(hipotez, kume, sonuc: str = "TEST"):
    """`split.onay_kosusu`; blok hatasiz biterse ve sonuc bildirilmediyse `sonuc` bildirilir."""
    with split.onay_kosusu(hipotez, kume) as tutamak:
        yield tutamak
        if tutamak.sonuc is None:
            tutamak.sonuc_bildir(sonuc)
