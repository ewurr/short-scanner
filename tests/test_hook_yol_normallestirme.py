"""Hook'ta yol normallestirmesi (madde 1b).

Esleştirme oncesinde yol normalize edilir: ters egik cizgi, `./`, `../`, `//`, sondaki nokta ve
bosluk, NTFS veri akisi soneki (`::$DATA`) ve buyuk/kucuk harf. Gerekce: bu yazimlar Windows'ta
AYNI dosyayi gosterir; biri desene uymadiginda koruma delinir.

`Path.resolve()` yetmiyordu: Windows'ta sondaki noktayi temizlemedigi OLCULDU (sizinti turu),
yani delik Write/Edit yolunda da duruyordu. Normalleştirme artik tek bir saf fonksiyonda
(`yol_normalle`) ve hem yol eslestirmesinde (`kilitli_mi`, `kapsar_mi`, `_dizin_kapsar`) hem de
komut metninde anma aramasinda (`_ad_geciyor_mu` -> `_metin_normalle`) uygulanir.

Komutlar hicbir zaman CALISTIRILMAZ; yalnizca metin olarak degerlendirilir.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parents[1]
_YOL = KOK / ".claude" / "hooks" / "kilitli_dosya_korumasi.py"
_SPEC = importlib.util.spec_from_file_location("kilit_hook_normal", _YOL)
hook = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = hook
_SPEC.loader.exec_module(hook)

DESEN = "analysis/*/" + "KILIT" + ".md"
AD = "KILIT" + ".md"


# --- 1. `yol_normalle` saf davranisi --------------------------------------------------------


@pytest.mark.parametrize("girdi,beklenen", [
    ("analysis/h1/" + AD, "analysis/h1/" + AD),
    ("analysis\\h1\\" + AD, "analysis/h1/" + AD),
    ("./analysis/h1/" + AD, "analysis/h1/" + AD),
    ("analysis//h1///" + AD, "analysis/h1/" + AD),
    ("analysis/h1/./" + AD, "analysis/h1/" + AD),
    ("analysis/h1/../h1/" + AD, "analysis/h1/" + AD),
    ("analysis/h2/../h1/" + AD, "analysis/h1/" + AD),
    ("analysis/h1/" + AD + ".", "analysis/h1/" + AD),
    ("analysis/h1/" + AD + "...", "analysis/h1/" + AD),
    ("analysis/h1/" + AD + " ", "analysis/h1/" + AD),
    ("analysis/h1/" + AD + "::$DATA", "analysis/h1/" + AD),
    ('"analysis/h1/' + AD + '"', "analysis/h1/" + AD),
    ("/mutlak/yol/" + AD, "/mutlak/yol/" + AD),
    ("D:/Projeler/short_scanner/CLAUDE.md", "D:/Projeler/short_scanner/CLAUDE.md"),
    ("D:\\Projeler\\short_scanner\\CLAUDE.md", "D:/Projeler/short_scanner/CLAUDE.md"),
])
def test_yol_normalle(girdi, beklenen):
    assert hook.yol_normalle(girdi) == beklenen


def test_yol_normalle_saf():
    """Dosya sistemine dokunmaz: var olmayan yol da normalize edilir."""
    assert hook.yol_normalle("yok/olan//dizin/../dizin/a.md") == "yok/olan/dizin/a.md"


# --- 2. Esdeger yazimlar KILIT.md'yi korur --------------------------------------------------


ESDEGER_YOLLAR = [
    "analysis/h1/" + AD,
    "analysis\\h1\\" + AD,
    "./analysis/h1/" + AD,
    "analysis//h1/" + AD,
    "analysis/h1/./" + AD,
    "analysis/h1/../h1/" + AD,
    "analysis/h1/" + AD + ".",
    "analysis/h1/" + AD + "::$DATA",
    "analysis/h1/" + AD.lower(),
    "analysis/h1/Kilit.Md",
    "analysis/H1/" + AD,
]


@pytest.mark.parametrize("yol", ESDEGER_YOLLAR)
def test_esdeger_yazim_kilitli_sayilir(yol):
    assert hook.kilitli_mi(yol) == DESEN, yol


@pytest.mark.parametrize("yol", ESDEGER_YOLLAR)
def test_esdeger_yazim_write_yolunda_mutlak_olarak_da_korunur(yol):
    """Write/Edit yolu mutlak gelir; normalleştirme orada da uygulanir."""
    assert hook.kilitli_mi(str(KOK) + "/" + yol) == DESEN, yol


@pytest.mark.parametrize("yol", ESDEGER_YOLLAR)
def test_esdeger_yazima_yonlendirme_reddedilir(yol):
    karar = hook.bash_degerlendir(f"echo x > {yol}")
    assert not karar.izin and karar.kalip == DESEN, yol


@pytest.mark.parametrize("yol", ESDEGER_YOLLAR)
def test_esdeger_yazima_powershell_yazmasi_reddedilir(yol):
    karar = hook.powershell_degerlendir(f"Set-Content -Path {yol} -Value x")
    assert not karar.izin and karar.kalip == DESEN, yol


@pytest.mark.parametrize("yol", ESDEGER_YOLLAR)
def test_esdeger_yazimda_silme_reddedilir(yol):
    assert not hook.bash_degerlendir(f"rm -f {yol}").izin, yol


# --- 3. Tam yol girdileri: ayni esdegerlikler ----------------------------------------------


@pytest.mark.parametrize("yol", [
    "CLAUDE.md", ".\\CLAUDE.md", "./CLAUDE.md", "CLAUDE.md.", "CLAUDE.md::$DATA",
    "claude.md", "data//split.csv", "data\\split.csv", "data/../data/split.csv",
    "ONAY_KAYDI.md.", "data/universe.csv.", "PREREGISTRATION.md::$DATA",
])
def test_tam_yol_girdilerinin_esdegerleri_korunur(yol):
    assert hook.kilitli_mi(yol) is not None, yol
    assert not hook.bash_degerlendir(f"echo x > {yol}").izin, yol


# --- 4. Yanlis pozitif geri gelmedi --------------------------------------------------------


@pytest.mark.parametrize("yol", [
    "analysis/00_veri_denetimi/.rev1213_capasiz.kilit",
    "analysis/h1/.rev_capasiz.kilit",
    "analysis/h1/kilitler.md",
    "analysis/h1/" + AD + ".bak",
    "analysis/h1/KILIT.markdown",
    "analysis/h1/onay_kilit.md",
    "cache/" + AD,
    "analysis/h1/alt/" + AD,
    "analysis/h1/../" + AD,            # -> analysis/KILIT.md: desen bir hipotez dizini ister
])
def test_benzer_adlar_hala_kilitli_degil(yol):
    assert hook.kilitli_mi(yol) is None, yol


@pytest.mark.parametrize("komut", [
    "rm analysis/00_veri_denetimi/.rev1213_capasiz.kilit",
    "rm ./analysis/00_veri_denetimi/.rev1213_capasiz.kilit",
    "echo x > analysis/h1/kilitler.md",
    "Remove-Item analysis\\00_veri_denetimi\\.rev1213_capasiz.kilit",
    "cp a.csv analysis/00_veri_denetimi/yeni.csv",
])
def test_kilitli_olmayan_dosyalara_yazma_gecer(komut):
    for degerlendir in (hook.bash_degerlendir, hook.powershell_degerlendir):
        karar = degerlendir(komut)
        assert karar.izin, f"{degerlendir.__name__}: {komut} -> {karar.neden}"


def test_kosu_kilidi_artigi_silinebilir():
    assert hook.bash_degerlendir("rm analysis/00_veri_denetimi/.rev1213_capasiz.kilit").izin


# --- 5. Metin icinde anma: normallestirilmis kopyada da aranir -----------------------------


@pytest.mark.parametrize("metin", [
    "analysis/h1/../h1/" + AD,
    "analysis//h1/" + AD,
    "analysis\\h1\\" + AD,
    "analysis/h1/" + AD + ".",
    "analysis/h1/" + AD.lower(),
])
def test_anma_normallestirilmis_metinde_bulunur(metin):
    assert hook._ad_geciyor_mu(metin) == DESEN, metin


@pytest.mark.parametrize("metin", ["analysis/h1/kilitler.md", "analysis/h1/.x.kilit",
                                   "cache/" + AD, "bir metin"])
def test_anma_yanlis_pozitif_vermez(metin):
    assert hook._ad_geciyor_mu(metin) is None, metin
