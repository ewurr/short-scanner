"""Performans 2b-1, 0. asama: §14.46 artiklari (plan v3; RESULTS §14.48). Aga cikmaz.

- D-B2: `universe.evren_yukle`nin bool ayristirmasi ayri fonksiyonda (`bool_sutunlarini_ayristir`) ve SABIT'te.
- D-C2: `calistir.git_durumu` / `ortam_kaydi` agac temizligini tek kaynaktan (`split.agac_kirli_sayisi` ->
  `split._agac_kirlilikleri`) alir; dosya adi yazilmaz, yalnizca sayi.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

from data import split, universe
from onay_yardimcisi import DEPO_BETIGI, gecici_depo, git

import test_skaler_referans_dayanilan as dpd


# --- D-B2 ------------------------------------------------------------------------------------------------------

def _eski_govde(tablo: pd.DataFrame, hedef) -> pd.DataFrame:
    """`evren_yukle`nin 28f2c14'teki bool ayristirma govdesinin birebir kopyasi (karsilastirma tabani)."""
    tablo = tablo.copy()
    for sutun in universe._BOOL_SUTUNLARI:
        deger = tablo[sutun].astype(str).map({"True": True, "False": False})
        if deger.isna().any():
            raise ValueError(f"{hedef}: {sutun!r} sutununda True/False disi deger var.")
        tablo[sutun] = deger.astype(bool)
    return tablo


def _tablo(haric, funding_yok) -> pd.DataFrame:
    return pd.DataFrame({"sembol": [f"S{i}USDT" for i in range(len(haric))], "haric": haric,
                         "donem_funding_yok": funding_yok})


@pytest.mark.parametrize("haric,funding_yok", [
    (["True", "False"], ["False", "False"]),
    (["False"], ["True"]),
    (["True", "True", "False"], ["True", "False", "True"]),
])
def test_D_B2_true_false_metni_eski_govdeyle_ayni(haric, funding_yok):
    girdi = _tablo(haric, funding_yok)
    yeni = universe.bool_sutunlarini_ayristir(girdi, "evren.csv")
    pd.testing.assert_frame_equal(yeni, _eski_govde(girdi, "evren.csv"))
    assert yeni["haric"].dtype == bool and yeni["donem_funding_yok"].dtype == bool
    assert list(yeni["haric"]) == [h == "True" for h in haric]
    assert list(girdi["haric"]) == haric, "girdi degistirilmemeli"


@pytest.mark.parametrize("sutun", ["haric", "donem_funding_yok"])
@pytest.mark.parametrize("deger", ["", "true", "false", "1", "0", "Evet", " True", "True ", "nan", "None"])
def test_D_B2_bos_ve_gecersiz_metin_eski_govdeyle_ayni_hatayi_verir(sutun, deger):
    haric, funding_yok = ["False", "False"], ["False", "False"]
    (haric if sutun == "haric" else funding_yok)[1] = deger
    girdi = _tablo(haric, funding_yok)
    with pytest.raises(ValueError) as eski:
        _eski_govde(girdi, "evren.csv")
    with pytest.raises(ValueError) as yeni:
        universe.bool_sutunlarini_ayristir(girdi, "evren.csv")
    assert str(yeni.value) == str(eski.value) == f"evren.csv: {sutun!r} sutununda True/False disi deger var."


def test_D_B2_evren_yukle_gecersiz_metinde_ayni_mesajla_reddeder(tmp_path):
    """Yukleyici yolu: CSV'de bos `haric` hucresi (keep_default_na=False ile bos metin) reddedilir."""
    gercek = pd.read_csv(universe.config.UNIVERSE_CSV, dtype=str, keep_default_na=False, encoding="utf-8").head(3)
    gercek.loc[1, "haric"] = ""
    yol = tmp_path / "evren.csv"
    gercek.to_csv(yol, index=False, encoding="utf-8")
    with pytest.raises(ValueError, match=r"'haric' sutununda True/False disi deger var"):
        universe.evren_yukle(yol)


def test_D_B2_evren_yukle_gercek_tabloda_ayni_sonucu_verir():
    """Commit'li evren tablosu: yeni yol eski govdeyle ayni cerceveyi verir."""
    hedef = universe.config.UNIVERSE_CSV
    ham = pd.read_csv(hedef, dtype={s: str for s in (*universe._METIN_SUTUNLARI, *universe._ZAMAN_SUTUNLARI)},
                      keep_default_na=False, encoding="utf-8")
    pd.testing.assert_frame_equal(universe.evren_yukle(), universe._normallestir(_eski_govde(ham, hedef)))


def test_D_B2_ayristirma_SABIT_te_yukleyici_GUVENLIK_te():
    ad = "data.universe.bool_sutunlarini_ayristir"
    assert ad in dpd.SABIT and ad not in dpd.GUVENLIK
    assert ad in dpd._kapanis(), "evren_yukle ayristirmayi cagirmali (grafikte gorunmeli)"
    assert dpd.GUVENLIK["data.universe.evren_yukle"][1] == "yukleyici"
    assert dpd._sha(ad) == dpd.SABIT[ad]


# --- D-C2 ------------------------------------------------------------------------------------------------------

_KOK = Path(__file__).resolve().parents[1]


def _calistir():
    spec = importlib.util.spec_from_file_location("_perf2b1_calistir", _KOK / "analysis/00_veri_denetimi/calistir.py")
    modul = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modul
    spec.loader.exec_module(modul)
    return modul


calistir = _calistir()
_ZAMAN = pd.Timestamp("2026-01-01", tz="UTC")


def _ortam(git) -> pd.DataFrame:
    return calistir.ortam_kaydi(git, _ZAMAN, _ZAMAN).set_index("bilesen")


def test_D_C2_temiz_gecici_depoda_sifir(tmp_path):
    gecici_depo(tmp_path)
    git_durumu = calistir.git_durumu()
    assert git_durumu["bilinmiyor"] is False and git_durumu["kirli_sayisi"] == 0
    assert set(git_durumu) == {"commit", "kirli_sayisi", "bilinmiyor"}, "dosya listesi tasinmaz"
    tablo = _ortam(git_durumu)
    assert tablo.at["calisma_agaci", "surum"] == "temiz"
    assert tablo.at["calisma_agaci_kirli_sayisi", "surum"] == "0"
    assert "calisma_agaci_degisiklikleri" not in tablo.index


def test_D_C2_kirli_depoda_yalnizca_sayi_dosya_adi_yok(tmp_path):
    depo = gecici_depo(tmp_path)
    (depo / "gizli_ad.py").write_text("x = 1\n", encoding="utf-8")            # izlenmeyen
    (depo / DEPO_BETIGI).write_text("# degisti\n", encoding="utf-8")         # izlenen degisiklik
    git_durumu = calistir.git_durumu()
    assert git_durumu["kirli_sayisi"] == len(split._agac_kirlilikleri()) == 2
    tablo = _ortam(git_durumu)
    assert tablo.at["calisma_agaci", "surum"] == "kirli"
    assert tablo.at["calisma_agaci_kirli_sayisi", "surum"] == "2"
    metin = tablo.to_csv()
    assert "gizli_ad" not in metin and Path(DEPO_BETIGI).name not in metin, "kirli dosya adi ciktiya yazilmaz"


def test_D_C2_eski_hesabin_gormedigi_isaret_artik_kirli(tmp_path):
    """Eski `git status --porcelain` hesabi `--skip-worktree` isaretli dosyayi gormezdi; tek kaynak gorur. Ortam
    kaydi artik kesif kaydi ve onay kosusuyla ayni hukmu verir."""
    depo = gecici_depo(tmp_path)
    git(depo, "update-index", "--skip-worktree", DEPO_BETIGI)
    (depo / DEPO_BETIGI).write_text("# gizlice degisti\n", encoding="utf-8")
    assert git(depo, "status", "--porcelain").strip() == "", "kurulum: eski olcut temiz gorur"
    assert calistir.git_durumu()["kirli_sayisi"] == 1
    assert split._kesif_kaydi_kur(None).agac_kirli_sayisi == 1


def test_D_C2_tek_kaynak_okunamazsa_bilinmiyor(tmp_path):
    """Git deposu olmayan bir dizin: tek kaynak None verir, ortam kaydi 'bilinmiyor' der (temiz uydurmaz)."""
    depo = gecici_depo(tmp_path)
    (depo / ".git").rename(depo / "git_degil")
    assert split.agac_kirli_sayisi() is None
    git_durumu = calistir.git_durumu()
    assert git_durumu["bilinmiyor"] is True and git_durumu["kirli_sayisi"] is None
    assert _ortam(git_durumu).at["calisma_agaci", "surum"] == "bilinmiyor (git yok)"


def test_D_C2_calistir_kendi_agac_hesabini_yapmaz():
    metin = (_KOK / "analysis/00_veri_denetimi/calistir.py").read_text(encoding="utf-8")
    # Komut satiri olarak (tirnakli arguman) yok; aciklamadaki tarihsel anma serbest.
    assert '"--porcelain"' not in metin and '"ls-files"' not in metin and '"status"' not in metin
    assert "agac_kirli_sayisi" in metin


# --- D-C3 ------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("dizin", [".pytest_cache", ".mypy_cache", "venv_yerel", "derin/alt"])
def test_D_C3_kendini_dislayan_izlenmeyen_gitignore_dizini_gizler_SINIR(tmp_path, dizin):
    """KAYITLI SINIR (RESULTS §14.48): `--exclude-per-directory=.gitignore` agactaki her `.gitignore`u uygular,
    izlenmeyenleri de. Izlenmeyen bir dizine `*` iceren `.gitignore` konursa (pytest, mypy ve venv onbellekleri boyle
    yapar) dizindeki betik kirli sayilmaz. Bu test sinirin VAR oldugunu belgeler; kapanirsa test kirmizi olur ve
    yorum ile kayit guncellenir."""
    depo = gecici_depo(tmp_path)
    hedef = depo / dizin
    hedef.mkdir(parents=True)
    (hedef / ".gitignore").write_text("*\n", encoding="utf-8")
    (hedef / "gizli_betik.py").write_text("x = 1\n", encoding="utf-8")
    assert split._agac_kirlilikleri() == []
    assert split._kesif_kaydi_kur(None).agac_temiz is True


def test_D_C3_kendini_dislamayan_izlenmeyen_gitignore_gizlemez(tmp_path):
    """Karsit vaka: izlenmeyen `.gitignore` kendini dislamiyorsa kendisi kirli sayilir."""
    depo = gecici_depo(tmp_path)
    (depo / "alt").mkdir()
    (depo / "alt" / ".gitignore").write_text("baska.txt\n", encoding="utf-8")
    (depo / "alt" / "betik.py").write_text("x = 1\n", encoding="utf-8")
    assert split._agac_kirlilikleri() == ["izlenmeyen:alt/.gitignore", "izlenmeyen:alt/betik.py"]


def test_D_C3_yorum_sinirin_adini_tasir():
    from inspect import getsource
    metin = (_KOK / "data" / "split.py").read_text(encoding="utf-8")
    assert "SINIR (RESULTS §14.48, D-C3)" in metin and ".pytest_cache/" in metin
    assert "YALNIZCA commit edilen" not in metin
    assert getsource(split._agac_kirlilikleri)  # tek kaynak yerinde


# --- D-C4 ------------------------------------------------------------------------------------------------------

def _head(depo) -> str:
    return git(depo, "rev-parse", "HEAD").strip()


def _kayda_satir(depo):
    with (depo / "ONAY_KAYDI.md").open("a", encoding="utf-8", newline="") as d:
        d.write("| deneme |\n")


@pytest.mark.parametrize("eksik", [("user.name",), ("user.email",), ("user.name", "user.email")])
def test_D_C4_kimlik_eksikse_kayit_commit_edilmez_ve_mesaj_hangisini_soyler(tmp_path, eksik):
    """`user.name` eksikken git 2.41 Windows'ta commit isletim sistemi adiyla YAPILIRDI; artik denenmez."""
    depo = gecici_depo(tmp_path)
    for a in eksik:
        git(depo, "config", "--unset", a)
    _kayda_satir(depo)
    head = _head(depo)
    with pytest.raises(split.OnayKaydiCommitsiz) as hata:
        split._kaydi_commit_et("deneme")
    mesaj = str(hata.value)
    assert f"Deponun yerel yapilandirmasinda {'/'.join(eksik)} yok" in mesaj
    if len(eksik) == 1:
        diger = ({"user.name", "user.email"} - set(eksik)).pop()
        assert f"{diger} yok" not in mesaj and f"/{diger}" not in mesaj
    assert _head(depo) == head, "commit yapilmamali"


def test_D_C4_kimlik_tamsa_kayit_commit_edilir(tmp_path):
    depo = gecici_depo(tmp_path)
    _kayda_satir(depo)
    head = _head(depo)
    split._kaydi_commit_et("deneme")
    assert _head(depo) != head
    assert git(depo, "log", "-1", "--format=%an <%ae>").strip() == "Test <test@example.invalid>"


@pytest.mark.parametrize("eksik", ["user.name", "user.email"])
def test_D_C4_kosu_acilisi_kimlik_eksikse_reddeder(tmp_path, eksik):
    depo = gecici_depo(tmp_path)
    git(depo, "config", "--unset", eksik)
    with pytest.raises(split.OnayOrtamiHatasi,
                       match=rf"Onay kosusu acilmadi: Deponun yerel yapilandirmasinda {eksik} yok"):
        split._kimlik_denetle()


def test_D_C4_kosu_acilisinda_kimlik_denetimi_itme_denemesinden_ve_kayittan_once():
    """Kimlik denetimi `onay_kosusu`nda yerel ortam denetiminden sonra, ag islemlerinden, itme denemesi commit'inden
    ve BASLADI satirindan ONCE cagrilir: eksik kimlikte kosu acilmaz, satir yazilmaz, cift harcanmaz."""
    import ast
    import inspect
    import textwrap
    agac = ast.parse(textwrap.dedent(inspect.getsource(split.onay_kosusu)))
    cagrilar = [d for d in ast.walk(agac) if isinstance(d, ast.Call) and isinstance(d.func, ast.Name)]
    satir = {}
    for d in cagrilar:
        satir[d.func.id] = min(satir.get(d.func.id, d.lineno), d.lineno)
    assert satir["_kosu_ortami"] < satir["_kimlik_denetle"] < satir["_uzak_adresi_denetle"]
    assert satir["_kimlik_denetle"] < satir["_itme_denemesi"] < satir["_onay_kaydet"]


def _hazir(tmp_path):
    depo = gecici_depo(tmp_path)
    git(depo, "config", "credential.helper", f"store --file={(tmp_path / 'kimlik').as_posix()}")
    return depo


def test_D_C4_git_hazirlik_uzak_adresi_denetler_tamam(tmp_path, capsys):
    _hazir(tmp_path)
    assert split.git_hazirlik() == 0
    assert "uzak adres: TAMAM" in capsys.readouterr().out


def test_D_C4_git_hazirlik_yanlis_uzak_adreste_basarisiz(tmp_path, capsys):
    depo = _hazir(tmp_path)
    baska = tmp_path / "baska.git"
    git(tmp_path, "init", "-q", "--bare", str(baska))
    git(depo, "remote", "set-url", "--push", "origin", str(baska))   # okuma dogru, itme baska depoya
    assert split.git_hazirlik() == 1
    cikti = capsys.readouterr().out
    assert "uzak adres: BASARISIZ" in cikti and "git-hazirlik: EKSIK" in cikti


@pytest.mark.parametrize("ad", ["agac_kirli_sayisi", "_KIMLIK_ANAHTARLARI", "_yerel_kimlik_eksikleri",
                                "_kimlik_mesaji", "_kimlik_denetle"])
def test_D_C4_yeni_adlar_korunur(ad):
    with pytest.raises(split.OnayKorumasi):
        setattr(split, ad, None)


@pytest.mark.parametrize("ad", ["_KIMLIK_ANAHTARLARI", "_yerel_kimlik_eksikleri", "_kimlik_mesaji", "_kimlik_denetle"])
def test_D_C4_kimlik_adlari_analiz_kodunda_taramaya_takilir(tmp_path, ad):
    from tarama_yardimcisi import ONAY_ATLATMA_DESENI, ihlaller
    (tmp_path / "study").mkdir()
    (tmp_path / "study" / "k.py").write_text(f"from data import split\nsplit.{ad}\n", encoding="utf-8")
    assert ihlaller(ONAY_ATLATMA_DESENI, kok=tmp_path) == ["study/k.py"]


# --- D-C6 ------------------------------------------------------------------------------------------------------

def test_D_C6_esitlik_betigi_her_satira_numpy_ve_pandas_surumunu_yazar():
    import numpy as np

    spec = importlib.util.spec_from_file_location("_perf2b1_esitlik", _KOK / "analysis/00_veri_denetimi/esitlik_kapi.py")
    ek = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = ek
    spec.loader.exec_module(ek)
    assert {"numpy_surumu", "pandas_surumu"} <= set(ek.SUTUNLAR)
    for rol in ("K1", "TOPLAM_SURE", "HATA"):
        satir = ek._bos_satir("XUSDT", 0, "H1", "y", rol)
        assert satir["numpy_surumu"] == np.__version__ and satir["pandas_surumu"] == pd.__version__
    assert set(ek._bos_satir("XUSDT", 0, "H1", "y", "K1")) <= set(ek.SUTUNLAR)
