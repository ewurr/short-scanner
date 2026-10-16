"""Onay kosusu test yardimcilari (onay kaydi ve kosu butunlugu turu, denetci KS3 D-B1, D-B3).

Kayit yolu artik `config.ONAY_KAYDI` monkeypatch'iyle degistirilemez; testler `split._test_kaydi_ayarla` ile
kendi testleri suresince gecici bir kayda yonlenir (git ortami da orada sahte: temiz agac, sabit commit).

Onay kosusu blogu sonuc bildirilmeden biterse `OnaySonucuYok` verir. Kosuyu yalnizca erisim acmak icin kullanan
testler `kosu(...)` ile acar: blok hatasiz biterse sonuc "TEST" bildirilir; blok icindeki hata aynen yukari cikar.

Onay kaydi ikinci tur (denetci OK D-B1): `gecici_depo` gecici bir git deposu kurar ve kaydi oraya yonlendirir;
bu kipte git islemleri (temiz agac, HEAD, gecmis, commit) gercekten yapilir.
"""

from __future__ import annotations

import pathlib
import subprocess
from contextlib import contextmanager

from data import split

DEPO_KAYIT_BASLIGI = (
    "# ONAY_KAYDI.md (test)\n\n| Tarih (UTC) | Kume | Cagiran betik | Commit | Not |\n|---|---|---|---|---|\n\n"
    "Henuz onay kosusu yok.\n"
)
DEPO_BETIGI = "analysis/onay_betigi.py"

# F2'nin kilitledigi yapilandirma (on-kayit §8 madde 5, rev.13). Onay kosusu bu dosyayi okur ve
# kaydi olmayan ya da hukmu "hipotez kapandi" olan hipotez icin acilmaz; bu yuzden onay kosusu
# kullanan her test, kostugu hipotez icin bir kilit kaydina ihtiyac duyar. Asagidaki yardimcilar
# uc hipotez icin "yapilandirma secildi" hukmunde deterministik bir kayit kurar; kilit kurallarini
# SINAYAN testler kaydi kendileri yazar.
KILIT_YAPILANDIRMASI = {
    "H1": ("H1:theta=0.2,delta=0.08", "theta=0.20 delta=0.08"),
    "H2": ("H2:phi=0.0003,k=3", "phi=0.0003 k=3"),
    "H3": ("H3:nu=0.5,tau=0.15", "nu=0.50 tau=0.15"),
}


def kilit_metni(hipotez: str, *, hukum: str = None, gerekce: str = "-", yapilandirma: str = None,
                parametreler: str = None, olusmus: int = 400, analize_giren: int = 380,
                k2_farki: str = "0.0210", commit: str = "0" * 40,
                zaman: str = "2026-10-20T12:00:00+00:00", tohum: int = None) -> str:
    """On-kayit §8 madde 5'teki alanlari tasiyan bir KILIT.md metni (test fiksturu)."""
    import config

    # On-kayit disi bir ad (yalnizca `config.HIPOTEZLER`i monkeypatch'leyen belgeleme testi) icin
    # yer tutucu: kilit kaydinin VARLIGI sinaniyor, icerigi degil.
    varsayilan_y, varsayilan_p = KILIT_YAPILANDIRMASI.get(hipotez, (f"{hipotez}:test", "test"))
    satirlar = [
        ("hipotez", hipotez),
        ("hukum", split.KILIT_SECILDI if hukum is None else hukum),
        ("gerekce", gerekce),
        ("yapilandirma", varsayilan_y if yapilandirma is None else yapilandirma),
        ("parametreler", varsayilan_p if parametreler is None else parametreler),
        ("olusmus_olay", str(olusmus)),
        ("analize_giren_olay", str(analize_giren)),
        ("k2_farki", k2_farki),
        ("kesif_commit", commit),
        ("kesif_zamani", zaman),
        ("tohum", str(config.TOHUM if tohum is None else tohum)),
    ]
    govde = "\n".join(f"| {ad} | {deger} |" for ad, deger in satirlar)
    return (f"# KILIT.md — {hipotez} (F2'nin kilitledigi yapilandirma; test)\n\n"
            f"| Alan | Deger |\n|---|---|\n{govde}\n")


def kilit_yaz(kok, hipotez: str, **alanlar) -> pathlib.Path:
    """`kok/analysis/<hipotez>/KILIT.md` dosyasini yazar ve yolunu doner."""
    yol = pathlib.Path(kok) / "analysis" / hipotez / "KILIT.md"
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(kilit_metni(hipotez, **alanlar), encoding="utf-8", newline="")
    return yol


def kilitleri_kur(kok, hipotezler=("H1", "H2", "H3")) -> pathlib.Path:
    """Verilen hipotezler icin varsayilan kilit kayitlarini `kok` altina yazar; `kok`u doner."""
    for hipotez in hipotezler:
        kilit_yaz(kok, hipotez)
    return pathlib.Path(kok)


def gecici_kayit(yol, *, kilit_koku=None, kilitler=("H1", "H2", "H3"), **ortam):
    """Bu test suresince onay kaydini `yol`a yonlendirir; `ortam` `split._test_kaydi_ayarla`ya gider.

    KILIT.md koku da bu testle sinirlidir: verilmezse `yol`un yanina `kilit_koku/` kurulur ve
    `kilitler`deki her hipotez icin varsayilan bir kayit yazilir (on-kayit §8 madde 5). Kilit
    kurallarini sinayan testler `kilit_koku` ya da `kilitler=()` vererek bunu devralir.

    GERCEK git kipinde (`depo=` verilmisse) kok DEPONUN kendisidir: kilit dosyasi commit edilmis
    olmali ("Secim, onay kosusundan once ... commit edilir"), bu yuzden `gecici_depo`nun ilk
    commit'ine giren kayit kullanilir ve yeni dosya yazilmaz.
    """
    if kilit_koku is None and ortam.get("depo") is not None:
        kilit_koku = ortam["depo"]
    elif kilit_koku is None:
        kilit_koku = pathlib.Path(yol).parent / "kilit_koku"
        pathlib.Path(kilit_koku).mkdir(parents=True, exist_ok=True)
        kilitleri_kur(kilit_koku, kilitler)
    return split._test_kaydi_ayarla(yol, kilit_koku=kilit_koku, **ortam)


def git(depo, *argumanlar) -> str:
    """Test deposunda git komutu; basarisizlikta CalledProcessError."""
    return subprocess.run(["git", *argumanlar], cwd=depo, check=True, capture_output=True, text=True,
                          encoding="utf-8").stdout


def gecici_depo(kok, kilitler=("H1", "H2", "H3")):
    """`kok/depo` altinda gercek bir git deposu kurar (kayit dosyasi ve izlenen bir betik commit edilmis) ve bu
    test suresince onay kaydini oraya yonlendirir. Doner: depo yolu. Kayit: `depo / "ONAY_KAYDI.md"`.

    Onay kaydi kapanis turu: `kok/uzak.git` ciplak bir depo `origin` olarak eklenir ve `main` oraya itilir (dosya
    yolu uzerinden; aga cikilmaz). Uzak depo: `uzak_depo(depo)`.

    `kilitler`: ilk commit'e girecek kilit kayitlarinin hipotezleri. Kaydi SONRADAN yazan testler
    ilgili hipotezi listeden cikarir, cunku kayit git gecmisinde TAM BIR KEZ eklenmis olmalidir
    (on-kayit §8 madde 5 ekleme kurali; madde 2g).
    """
    depo = kok / "depo"
    (depo / "analysis").mkdir(parents=True)
    git(depo, "init", "-q")
    git(depo, "checkout", "-q", "-b", "main")
    for anahtar, deger in [("user.name", "Test"), ("user.email", "test@example.invalid"),
                           ("core.autocrlf", "false"), ("commit.gpgsign", "false"), ("core.hooksPath", ".git/hooks")]:
        git(depo, "config", anahtar, deger)
    (depo / "ONAY_KAYDI.md").write_text(DEPO_KAYIT_BASLIGI, encoding="utf-8", newline="")
    (depo / DEPO_BETIGI).write_text("# onay betigi (test)\n", encoding="utf-8")
    # F2'nin kilitledigi yapilandirma, commit edilmis halde (on-kayit §8 madde 5: "Secim, onay
    # kosusundan once `analysis/<hipotez>/KILIT.md` dosyasiyla commit edilir").
    kilitleri_kur(depo, kilitler)
    git(depo, "add", ".")
    git(depo, "commit", "-q", "-m", "ilk")
    uzak = kok / "uzak.git"
    git(kok, "init", "-q", "--bare", str(uzak))
    git(depo, "remote", "add", "origin", str(uzak))
    git(depo, "push", "-q", "origin", "main")
    git(depo, "fetch", "-q", "origin")
    # Kapanisin son turu: beklenen uzak depo (`config.UZAK_DEPO_ADRESI` yerine) bu ciplak depodur.
    split._test_kaydi_ayarla(depo / "ONAY_KAYDI.md", depo=depo, betik=DEPO_BETIGI, uzak=uzak,
                             kilit_koku=depo)
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
