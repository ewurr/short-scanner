"""Hook deseninin kapsami: yalnizca adi TAM `KILIT.md` olan yollar korunur.

`.claude/hooks/kilitli_dosya_korumasi.py` icindeki `analysis/*/KILIT.md` deseni iki yerde fazla
genis esliyordu:

  1. `fnmatch`te `*` `/` karakterini de karsilar; bu yuzden desenin ust dizini (`analysis/*`)
     `analysis/<dizin>/<baska dosya>` yollarini da "kapsanmis" sayiyordu. Sonuc: kosu kilidi
     artigi `analysis/00_veri_denetimi/.rev1213_capasiz.kilit` SILINEMIYORDU.
  2. Eslesme buyuk/kucuk harf duyarsizdi; `kilit` iceren her ad korumaya giriyordu.

Simdi desen yol parcasi duzeyinde ve dosya adi harf harf eslesiyor. Mevcut alti kilitli dosyanin
ve `analysis/<hipotez>/KILIT.md`nin korumasi aynen duruyor (tests/test_hook.py).

SINIR (bilincli, testte yazili): Windows'ta dosya adlari buyuk/kucuk harf ayrimi yapmaz, yani
`analysis/h1/kilit.md` ayni dosyayi gosterir ama desen onu eslestirmez. Koruma dikkatsiz bir
duzenlemeye karsidir, kararli bir atlatmaya karsi degil (CLAUDE.md "Koruma katmani").
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

KOK = pathlib.Path(__file__).resolve().parents[1]
_YOL = KOK / ".claude" / "hooks" / "kilitli_dosya_korumasi.py"
_SPEC = importlib.util.spec_from_file_location("kilit_hook_desen", _YOL)
hook = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = hook      # dataclass modulun kayitli olmasini bekler
_SPEC.loader.exec_module(hook)

DESEN = "analysis/*/KILIT.md"
KILIT = "analysis/h1/KILIT.md"
ARTIK = "analysis/00_veri_denetimi/.rev1213_capasiz.kilit"


# --- 1. Korunan yol: davranis degismedi -------------------------------------------------------


@pytest.mark.parametrize("yol", [KILIT, "analysis/H2/KILIT.md", "analysis\\h1\\KILIT.md",
                                 str(KOK / "analysis" / "h1" / "KILIT.md")])
def test_kilit_dosyasi_hala_korunur(yol):
    assert hook.kilitli_mi(yol) == DESEN
    assert hook.kapsar_mi(yol) == DESEN


@pytest.mark.parametrize("komut", [f"echo x >> {KILIT}", f"rm {KILIT}", f"sed -i 's/a/b/' {KILIT}",
                                   f"mv {KILIT} eski.md", "rm -rf analysis", "rm -rf analysis/h1"])
def test_kilit_dosyasina_yazma_hala_reddedilir(komut):
    karar = hook.bash_degerlendir(komut)
    assert not karar.izin and karar.kalip == DESEN, komut


# --- 2. `.kilit` uzantisi ve `kilit` iceren adlar korumaya GIRMEZ -----------------------------


@pytest.mark.parametrize("yol", [ARTIK, "analysis/h1/.rev_capasiz.kilit", "analysis/h1/kilitler.md",
                                 "analysis/h1/KILIT.md.bak", "analysis/h1/KILIT.markdown",
                                 "analysis/h1/onay_kilit.md", "cache/KILIT.md",
                                 "analysis/h1/alt/KILIT.md"])
def test_benzer_adlar_kilitli_degil(yol):
    """Desen `analysis/<tek dizin>/KILIT.md`dir: depo kokundeki ya da bir alt dizindeki ayni ad da
    korunmaz (bu, deseni yazarken verilmis bilincli karardir; bkz. hook aciklamasi)."""
    assert hook.kilitli_mi(yol) is None, yol
    assert hook.kapsar_mi(yol) is None, yol


def test_analysis_altindaki_tek_parcali_ad_temkinli_kapsanir():
    """`analysis/KILIT.md` kilitli dosyanin KENDISI degildir (desen bir hipotez dizini ister), ama
    DIZIN olabilecegi icin kapsama denetimi temkinli davranir. Yanlis engelleme zararsizdir,
    yanlis izin degil (hook aciklamasi)."""
    yol = "analysis/" + "KILIT" + ".md"
    assert hook.kilitli_mi(yol) is None
    assert hook.kapsar_mi(yol) == DESEN


@pytest.mark.parametrize("komut", [f"rm {ARTIK}", f"rm -f {ARTIK}",
                                   "rm analysis/00_veri_denetimi/.rev1213_capasiz.kilit",
                                   "echo x > analysis/h1/kilitler.md",
                                   "cp a.csv analysis/00_veri_denetimi/yeni.csv",
                                   "mv analysis/00_veri_denetimi/a.csv analysis/00_veri_denetimi/b.csv"])
def test_kilitli_olmayan_dosyalara_yazma_gecer(komut):
    karar = hook.bash_degerlendir(komut)
    assert karar.izin, f"{komut} -> {karar.neden}"


def test_kosu_kilidi_artigi_silinebilir():
    """Bulgunun kendisi: `.kilit` artigi silinebilmeli (etki olcumu yeniden kosulabilsin)."""
    assert hook.bash_degerlendir(f"rm {ARTIK}").izin


# --- 3. Buyuk/kucuk harf: ad harf harf eslesir -----------------------------------------------


@pytest.mark.parametrize("yol", ["analysis/h1/kilit.md", "analysis/h1/Kilit.Md",
                                 "analysis/h1/KILIT.MD"])
def test_harf_varyasyonlari_eslesmez(yol):
    """BILINCLI SINIR: Windows'ta bu yollar ayni dosyayi gosterir, ama desen yalnizca tam
    `KILIT.md` yazimini korur. Koruma dikkatsiz duzenlemeye karsidir; ad tam yazildiginda
    (ve araclar yolu dosya sisteminden aldiginda) koruma islerdir."""
    assert hook.kilitli_mi(yol) is None, yol


def test_tam_yol_girdileri_duyarsiz_kaldi():
    """Desen DISINDAKI kilitli dosyalarda (tam yol girdileri) buyuk/kucuk duyarsizlik korunur:
    bu dosyalarin adlari sabittir ve varyasyon yazmak kazayla olabilir."""
    for yol in ("preregistration.md", "PREREGISTRATION.MD", "data/Split.csv", "onay_kaydi.md"):
        assert hook.kilitli_mi(yol) is not None, yol


# --- 4. Desenin ust dizini yol parcasi duzeyinde kapsar --------------------------------------


@pytest.mark.parametrize("arg,beklenen", [("analysis", DESEN), ("analysis/", DESEN),
                                          ("analysis/h1", DESEN), ("./analysis", DESEN),
                                          ("analysis/h1/alt", None),
                                          ("analysis/00_veri_denetimi/x.csv", None)])
def test_dizin_kapsamasi_parca_parca(arg, beklenen):
    assert hook.kapsar_mi(arg) == beklenen, arg


def test_dizin_kapsar_yardimcisi():
    assert hook._dizin_kapsar("analysis", DESEN)
    assert hook._dizin_kapsar("analysis/h1", DESEN)
    assert not hook._dizin_kapsar("analysis/h1/KILIT.md", DESEN)
    assert not hook._dizin_kapsar("cache", DESEN)
