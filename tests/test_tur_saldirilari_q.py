"""Onay kaydi kapanis turu: sizinti testcisi Q saldirilari (commit 472a541, `data/split.py`: kayit uzak depoya bagli).

Amac kodu kirmaktir. Basarili bir saldiri `xfail(strict=True)` ile isaretlidir ve govde ISTENEN GUVENLI davranisi
iddia eder: saldiri gercekten basarili olursa govde kirmizi olur (xfail); kod duzeltilirse XPASS(strict) testi kirar
ve isaret kaldirilmalidir. Isaretsiz testler savusturulan saldirilardir ya da bulgu olarak belgelenen mevcut
davranistir (docstring'inde yazar).

Butun git testleri GERCEK gecici depolarda kosar (`onay_yardimcisi.gecici_depo`; `origin` = tmp altindaki ciplak
depo, dosya yolu uzerinden). Gercek `ONAY_KAYDI.md`, gercek depo ve gercek uzak depo (GitHub) hicbir testte
kullanilmaz; aga cikilmaz. Ikinci klon ve sahte uzak depolar da tmp altindadir.

Not: `pre-receive` hook'u kullanan testler git'in `sh` ile hook calistirabildigi bir ortam ister; hook calismiyorsa
test atlanir (`_hook_kur`).
"""

from __future__ import annotations

import re
import subprocess

import pytest

from data import split
from onay_yardimcisi import DEPO_BETIGI, gecici_depo, gecici_kayit, git, kosu, uzak_depo
from tarama_yardimcisi import (ONAY_ATLATMA_DESENI, ONBELLEK_DESENI, ONBELLEK_UZANTILARI, ihlaller)

B_SEMBOLU = "BTCUSDT"  # gercek split.csv'de B grubu

# Basarili saldiri: govdedeki guvenli davranis iddiasi kirilir (ya da beklenen hata gelmez).
_BASARILI = dict(strict=True, raises=(AssertionError, pytest.fail.Exception))


@pytest.fixture
def depo(tmp_path):
    return gecici_depo(tmp_path)


# --- yardimcilar --------------------------------------------------------------------------------------------


def _kayit(d) -> str:
    with (d / "ONAY_KAYDI.md").open("r", encoding="utf-8", newline="") as f:
        return f.read()


def _yonlendir(d):
    """Test ayarini `d` deposuna (ana depo ya da klon) cevirir."""
    gecici_kayit(d / "ONAY_KAYDI.md", depo=d, betik=DEPO_BETIGI)


def _klonla(tmp_path, ad, uzak):
    """`uzak`in yeni bir klonu (`tmp/ad`); kimlik ve satir sonu ayarlari gecici_depo ile ayni."""
    hedef = tmp_path / ad
    git(tmp_path, "clone", "-q", "-c", "core.autocrlf=false", "-b", "main", str(uzak), str(hedef))
    for anahtar, deger in [("user.name", "Test"), ("user.email", "test@example.invalid"),
                           ("core.autocrlf", "false"), ("commit.gpgsign", "false"), ("core.hooksPath", ".git/hooks")]:
        git(hedef, "config", anahtar, deger)
    return hedef


def _reddedilmeli(hipotez, kume, *beklenen):
    """Kosu `beklenen` hatalardan biriyle reddedilmeli. Baska bir onay hatasi ya da acilan kosu `pytest.fail`."""
    try:
        with kosu(hipotez, kume):
            pass
    except beklenen:
        return
    except (split.OnayGerekli, split.OnayTekrari) as hata:
        pytest.fail(f"({hipotez}, {kume}) icin beklenen {[b.__name__ for b in beklenen]}, gelen "
                    f"{type(hata).__name__}: {hata}")
    else:
        pytest.fail(f"({hipotez}, {kume}) kosusu ACILDI; beklenen {[b.__name__ for b in beklenen]}.")


def _acilmali(hipotez, kume):
    """Kosu acilabilmeli; onay hatasi `pytest.fail`."""
    try:
        with kosu(hipotez, kume):
            pass
    except (split.OnayGerekli, split.OnayTekrari) as hata:
        pytest.fail(f"({hipotez}, {kume}) kosusu acilabilmeliydi; gelen {type(hata).__name__}: {hata}")


def _uzak_mesajlari(uzak) -> str:
    return git(uzak, "log", "main", "--format=%s")


def _hook_kur(uzak, depo):
    """Uzak depoya `pre-receive` hook'u kurar: `uzak/reddet` dosyasi varken her itme reddedilir (fetch etkilenmez).
    Hook calismiyorsa (ortam sh'i yok) test atlanir."""
    isaret = (uzak / "reddet").as_posix()
    hook = uzak / "hooks" / "pre-receive"
    hook.parent.mkdir(exist_ok=True)
    hook.write_text(f'#!/bin/sh\n[ -e "./reddet" ] && exit 1\n[ -e "{isaret}" ] && exit 1\nexit 0\n',
                    encoding="utf-8", newline="\n")
    hook.chmod(0o755)
    _reddi_ac(uzak)
    sonuc = subprocess.run(["git", "push", "-q", "origin", "HEAD:refs/heads/hook-denemesi"], cwd=depo,
                           capture_output=True, text=True)
    _reddi_kapat(uzak)
    if sonuc.returncode == 0:
        pytest.skip("pre-receive hook'u bu ortamda calismiyor.")


def _reddi_ac(uzak):
    (uzak / "reddet").write_text("x", encoding="utf-8")


def _reddi_kapat(uzak):
    (uzak / "reddet").unlink(missing_ok=True)


def _hepsini_unut(depo, ilk):
    """SALDIRI ADIMI: yerel gecmisi `ilk`e sarar, uzak izleme dalini alir, reflog'u siler. Yerelde iz kalmaz."""
    git(depo, "reset", "-q", "--hard", ilk)
    git(depo, "fetch", "-q", "origin")
    git(depo, "reflog", "expire", "--expire=now", "--all")


# --- Saldiri 1: iki klon ------------------------------------------------------------------------------------


def test_geride_kalan_klon_ayni_cifti_uzak_gecmisten_gorur(depo, tmp_path):
    """Kural: CLAUDE.md §3.3 tek atis; kapanis turu: tek atis `origin/main` gecmisine de bakar. Saldiri: Y klonu X'in
    kosusundan ONCE kuruldu (geride, kendi kaydinda satir yok); X kosuyu iter; Y ayni cifti kosmak ister.
    Guvenli davranis: Y kosu acilirken `origin/main`'i alir ve `OnayTekrari` verir."""
    uzak = uzak_depo(depo)
    y = _klonla(tmp_path, "y", uzak)
    with kosu("H1", "C1"):
        pass
    assert "H1 C1 BITTI" in _uzak_mesajlari(uzak)
    _yonlendir(y)
    assert split.kayit_satirlari(_kayit(y)) == []  # Y'nin kendi kaydinda iz yok
    _reddedilmeli("H1", "C1", split.OnayTekrari)


def test_geride_kalan_klon_baska_cifti_ileri_sarma_yapamaz_ve_kayit_degismez(depo, tmp_path):
    """Kural: kapanis turu `_ileri_sarma_denetle`. Saldiri: geride kalan Y klonu (X'in kosusunu birlestirmeden) BASKA
    bir cifti acmak ister; BASLADI commit'i `origin/main` ustune ileri sarma olarak itilemez. Guvenli davranis:
    `OnayUzakHatasi`, Y'nin kaydina ve git gecmisine hicbir sey yazilmaz."""
    uzak = uzak_depo(depo)
    y = _klonla(tmp_path, "y", uzak)
    with kosu("H1", "C1"):
        pass
    _yonlendir(y)
    once_kayit, once_head = _kayit(y), git(y, "rev-parse", "HEAD")
    _reddedilmeli("H2", "C1", split.OnayUzakHatasi)
    assert _kayit(y) == once_kayit
    assert git(y, "rev-parse", "HEAD") == once_head
    assert git(y, "status", "--porcelain").strip() == ""


def test_yeni_klon_x_in_itilmis_kosusunu_gorur(depo, tmp_path):
    """Kural: tek atis; uzak depo tek gercek kaynak. Saldiri: X kosuyu iter, sonra TAZE bir klon (Z) ayni cifti
    kosmak ister. Guvenli davranis: Z'nin calisma agacinda satir olmasa da `origin/main` gecmisi cifti harcar."""
    with kosu("H1", "C1"):
        pass
    z = _klonla(tmp_path, "z", uzak_depo(depo))
    _yonlendir(z)
    _reddedilmeli("H1", "C1", split.OnayTekrari)


def _ours_ile_gizle(depo, tmp_path):
    """SALDIRI ADIMLARI. Y klonu (geride) yerel bir commit yapar (kayit dosyasinin ONAY SATIRI OLMAYAN aciklama
    cumlesi), X'in itilmis kosusunu `merge -s ours` ile "kendi tarafi" diyerek birlestirir ve iter. Birlestirme
    commit'inin agaci ilk ebeveyniyle (Y) ayni oldugu icin `git log -- dosya` (`--full-history` yok) ikinci ebeveyni
    (X'in kosu commit'leri) sadelestirmeyle GIZLER. Doner: Y klonu."""
    uzak = uzak_depo(depo)
    y = _klonla(tmp_path, "y", uzak)
    with kosu("H1", "C1"):
        pass
    assert "H1 C1 BITTI" in _uzak_mesajlari(uzak)
    kayit = y / "ONAY_KAYDI.md"
    with kayit.open("r", encoding="utf-8", newline="") as f:
        metin = f.read()
    assert "Henuz onay kosusu yok." in metin
    with kayit.open("w", encoding="utf-8", newline="") as f:
        f.write(metin.replace("Henuz onay kosusu yok.", "Y notu."))
    git(y, "commit", "-q", "-am", "Y notu")
    git(y, "fetch", "-q", "origin")
    git(y, "merge", "-q", "-s", "ours", "origin/main", "-m", "Y kendi tarafini secti")
    git(y, "push", "-q", "origin", "HEAD:refs/heads/main")
    return y


@pytest.mark.xfail(reason="`merge -s ours` birlestirmesi git log sadelestirmesiyle X'in kosu commit'lerini gizler; "
                          "`--full-history`/`-m` yok", **_BASARILI)
def test_ours_birlestirmesiyle_x_in_kosusu_yerel_gecmisten_silinemez(depo, tmp_path):
    """Kural: CLAUDE.md §3.3 tek atis; git gecmisindeki her satir cifti harcar. Saldiri: Y, X'in itilmis kosusunu
    `merge -s ours` ile "cozer" (X'in satirlari agactan cikar, commit'ler ise birlestirmenin ikinci ebeveyninde
    kalir), birlestirmeyi iter, reflog'u siler. Sonra Y ayni cifti kosmak ister. `git log --all --reflog -p -- dosya`
    varsayilan gecmis sadelestirmesiyle (birlestirme ilk ebeveyne TREESAME) ikinci ebeveyne inmez. Guvenli davranis:
    cift hala harcanmis (`OnayTekrari`). Gozlenen (saldiri basarili): kosu acilir. Kasitli-cok-adimli yol olarak
    belgelendi (split.py 'birlestirmede tek tarafa cozum'); yine de iz `--full-history` ile bulunabilirdi."""
    y = _ours_ile_gizle(depo, tmp_path)
    git(y, "reflog", "expire", "--expire=now", "--all")  # X'in ucu Y'nin fetch reflog'unda da duruyordu
    _yonlendir(y)
    _reddedilmeli("H1", "C1", split.OnayTekrari)


@pytest.mark.xfail(reason="`merge -s ours` birlestirmesi itildikten sonra TAZE klon X'in kosusunu gormez", **_BASARILI)
def test_ours_birlestirmesi_sonrasi_yeni_klon_cifti_gorur(depo, tmp_path):
    """Kural: CLAUDE.md §3.3 tek atis, uzak depo tek gercek kaynak. Saldiri: Y `merge -s ours` ile X'in kosusunu
    kendi agacindan cikarip uzak `main`'e iter; sonra TAZE bir klon (Z; reflog'u yalniz klonlama girdisi) ayni cifti
    kosmak ister. `origin/main` gecmisi X'in commit'lerini sadelestirme yuzunden listelemez. Guvenli davranis:
    `OnayTekrari`. Gozlenen (saldiri basarili): kosu acilir ve uzak `main` ikinci bir H1/C1 kosusu kaydeder."""
    _ours_ile_gizle(depo, tmp_path)
    z = _klonla(tmp_path, "z", uzak_depo(depo))
    _yonlendir(z)
    _reddedilmeli("H1", "C1", split.OnayTekrari)


# --- Saldiri 2 ve 3: origin'i sahte uzaga yonlendirmek -------------------------------------------------------


@pytest.mark.parametrize("yol", ["set-url", "pushurl", "insteadOf", "ortam"])
@pytest.mark.xfail(reason="origin'in kimligi dogrulanmaz; sahte uzaga itilen kosu gercek uzakta iz birakmaz", **_BASARILI)
def test_origin_sahte_uzaga_yonlendirilip_geri_alininca_cift_yeniden_acilmamali(depo, tmp_path, monkeypatch, yol):
    """Kural: kapanis turu 'itme sayesinde her yol uzak depoda iz birakir'; CLAUDE.md §3.3 tek atis. Saldiri
    (yol=set-url: `git remote set-url`; pushurl: `remote.origin.pushurl`; insteadOf: `url.<sahte>.insteadOf`;
    ortam: `GIT_CONFIG_COUNT/KEY_0/VALUE_0` ortam degiskenleri): origin baska bir yerel ciplak depoya cevrilir,
    kosu orada itilir (gercek uzak hicbir sey gormez), yonlendirme geri alinir, yerel gecmis `ilk`e sarilir ve
    reflog silinir. Sonra ayni cift kosulmak istenir. Guvenli davranis: `OnayTekrari` (uzakta cift kayitli
    olmali). Gozlenen (saldiri basarili): gercek uzakta iz olmadigi icin kosu acilir ve gercek uzak ilk kez orada
    H1/C1 gorur."""
    uzak = uzak_depo(depo)
    sahte = tmp_path / "sahte.git"
    git(tmp_path, "init", "-q", "--bare", str(sahte))
    git(depo, "push", "-q", str(sahte), "main:refs/heads/main")
    ilk = git(depo, "rev-parse", "HEAD").strip()
    ayar = depo / ".git" / "config"
    with ayar.open("r", encoding="utf-8", newline="") as f:
        yedek = f.read()

    if yol == "set-url":
        git(depo, "remote", "set-url", "origin", str(sahte))
    elif yol == "pushurl":
        git(depo, "config", "remote.origin.pushurl", str(sahte))
    elif yol == "insteadOf":
        git(depo, "config", f"url.{sahte}.insteadOf", str(uzak))
    else:
        monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
        monkeypatch.setenv("GIT_CONFIG_KEY_0", "remote.origin.url")
        monkeypatch.setenv("GIT_CONFIG_VALUE_0", str(sahte))

    with kosu("H1", "C1"):
        pass
    # Saldirinin on kosulu: kosu sahtede kayitli, gercek uzak degismemis (hala `ilk`).
    assert "H1 C1 BITTI" in _uzak_mesajlari(sahte)
    assert git(uzak, "rev-parse", "main").strip() == ilk

    if yol == "ortam":
        for ad in ("GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0"):
            monkeypatch.delenv(ad)
    else:
        with ayar.open("w", encoding="utf-8", newline="") as f:
            f.write(yedek)
    _hepsini_unut(depo, ilk)
    _reddedilmeli("H1", "C1", split.OnayTekrari)


# --- Saldiri 4: zorla itme ile uzak gecmisi yeniden yazmak ---------------------------------------------------


@pytest.mark.xfail(reason="uzak gecmis zorla itmeyle yeniden yazilabilir; kod sunucu tarafi korumasina dayanir", **_BASARILI)
def test_zorla_itmeyle_uzak_gecmis_yeniden_yazilinca_ayni_ciftle_yeni_klon_reddedilmeli(depo, tmp_path):
    """Kural: CLAUDE.md §3.3 tek atis; kapanis turu 'uzak depodaki commit yazilamaz'. Saldiri: kosu itilir, sonra
    `git push --force origin <ilk>:main` ile uzak gecmis kosudan ONCEKI commit'e geri alinir; TAZE bir klon ayni
    cifti kosmak ister. Guvenli davranis: `OnayTekrari`. Gozlenen (saldiri basarili): uzak gecmiste iz kalmadigi
    icin kosu acilir. Kod yalniz `push` (zorlamasiz) yapar; zorla itmeyi reddetmek uzak sunucunun isidir
    (`receive.denyNonFastForwards`; bkz. sonraki test). Belgelenmis kasitli yol; bulgu olarak raporlanir."""
    ilk = git(depo, "rev-parse", "HEAD").strip()
    with kosu("H1", "C1"):
        pass
    git(depo, "push", "-q", "--force", "origin", f"{ilk}:refs/heads/main")
    assert git(uzak_depo(depo), "rev-parse", "main").strip() == ilk
    z = _klonla(tmp_path, "z", uzak_depo(depo))
    _yonlendir(z)
    _reddedilmeli("H1", "C1", split.OnayTekrari)


@pytest.mark.xfail(reason="yerel gecmis + zorla itilmis uzak gecmis birlikte silinince iz kalmaz", **_BASARILI)
def test_zorla_itme_ve_yerel_reflog_silme_ayni_depoda_cifti_geri_getirmemeli(depo):
    """Kural: CLAUDE.md §3.3 tek atis. Saldiri: ayni depoda kosu itilir, `push --force origin <ilk>:main`, yerel
    `reset --hard <ilk>` + `fetch` + `reflog expire --expire=now --all`. Yerel `--all --reflog` ve `origin/main`
    ikisi de temiz. Guvenli davranis: `OnayTekrari`. Gozlenen (saldiri basarili): kosu acilir."""
    ilk = git(depo, "rev-parse", "HEAD").strip()
    with kosu("H1", "C1"):
        pass
    git(depo, "push", "-q", "--force", "origin", f"{ilk}:refs/heads/main")
    _hepsini_unut(depo, ilk)
    _reddedilmeli("H1", "C1", split.OnayTekrari)


def test_sunucu_zorla_itmeyi_reddederse_zorla_itme_saldirisi_savusturulur(depo):
    """Kural: kapanis turu 'uzak depodaki commit yazilamaz'. Saldiri: zorla itme. Onlem (kod disi, sunucu tarafi):
    `receive.denyNonFastForwards=true`. Guvenli davranis: zorla itme reddedilir, uzak gecmis ve `OnayTekrari`
    korunur. Bu test onlemin bilesenini belgeler: kod bu ayari KENDISI kurmaz ve dogrulamaz."""
    uzak = uzak_depo(depo)
    git(uzak, "config", "receive.denyNonFastForwards", "true")
    ilk = git(depo, "rev-parse", "HEAD").strip()
    with kosu("H1", "C1"):
        pass
    sonuc = subprocess.run(["git", "push", "--force", "origin", f"{ilk}:refs/heads/main"], cwd=depo,
                           capture_output=True, text=True)
    assert sonuc.returncode != 0
    _hepsini_unut(depo, ilk)
    _reddedilmeli("H1", "C1", split.OnayTekrari)


# --- Saldiri 5: baska dalda kosu -----------------------------------------------------------------------------


@pytest.mark.xfail(reason="kosu main disi bir daldan acilabiliyor ve HEAD:main ile dalin commit'lerini uzak main'e tasiyor",
                   **_BASARILI)
def test_main_disi_daldan_kosu_acilmamali(depo):
    """Kural: kapanis turu 'BASLADI ve bitis commit'leri `git push origin HEAD:refs/heads/main` ile itilir';
    CLAUDE.md §3.3 (onay kosusu denetlenebilir koddan). Saldiri: `checkout -b deneme`, dalda (gozden gecirilmemis)
    commit'ler, oradan onay kosusu. Itme dalin BUTUN commit'lerini uzak `main`'e tasir, yerel `main` geride kalir.
    Guvenli davranis: kosu yalniz `main` dalindan acilir (`OnayOrtamiHatasi`); ya da en azindan dalin commit'leri
    uzak main'e karismaz. Gozlenen (saldiri basarili): kosu acilir. Tartismali: tasarim belki bunu kabul eder;
    bulgu olarak raporlanir."""
    git(depo, "checkout", "-q", "-b", "deneme")
    _reddedilmeli("H1", "C1", split.OnayOrtamiHatasi)


def test_main_disi_dalda_harcanan_cift_main_de_yeniden_acilamaz_ve_main_geride_kalir(depo):
    """Kural: tek atis; kapanis turu `_ileri_sarma_denetle`. Saldiri: `deneme` dalinda kosu (itme uzak `main`'i
    dalin ucuna gotururr), sonra `checkout main` (yerel main geride) ve ayni cifti ya da baska bir cifti kosmak.
    Guvenli davranis (savusturulur): ayni cift `OnayTekrari` (uzak gecmisten), baska cift `OnayUzakHatasi` (yerel
    main uzak main'i icermez). Ayrica: uzak main == deneme ucu, yerel main == ilk (dal commit'leri uzaga sizdi)."""
    uzak = uzak_depo(depo)
    ilk = git(depo, "rev-parse", "HEAD").strip()
    git(depo, "checkout", "-q", "-b", "deneme")
    with kosu("H1", "C1"):
        pass
    assert git(uzak, "rev-parse", "main").strip() == git(depo, "rev-parse", "deneme").strip()
    git(depo, "checkout", "-q", "main")
    assert git(depo, "rev-parse", "HEAD").strip() == ilk
    _reddedilmeli("H1", "C1", split.OnayTekrari)
    _reddedilmeli("H2", "C1", split.OnayUzakHatasi)


# --- Saldiri 6: onbellek taramasini atlatmak -----------------------------------------------------------------


def _tara(tmp_path, dosya, metin, desen=ONBELLEK_DESENI, uzantilar=ONBELLEK_UZANTILARI):
    yol = tmp_path / dosya
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(metin, encoding="utf-8")
    return ihlaller(desen, kok=tmp_path, uzantilar=uzantilar)


_XF = pytest.mark.xfail(reason="ONBELLEK_DESENI bu biciminde onbellege erisimi yakalamiyor", **_BASARILI)


@pytest.mark.parametrize("metin", [
    pytest.param("import pathlib\nyol = pathlib.Path(config.KOK, 'cache')\n", id="Path_KOK_cache_tirnakli"),
    pytest.param("import os\nyol = os.path.join(config.KOK, \"cache\", \"klines\")\n", id="os_path_join"),
    pytest.param("yol = f'{config.KOK}/cache/klines'\n", id="f_string_egik_cizgi"),
    pytest.param("ad = 'cache'\nyol = config.KOK / ad\n", id="degiskene_atama"),
])
def test_onbellek_deseni_kazayla_kurulan_cache_yolunu_yakalar(tmp_path, metin):
    """Kural: kapanis turu onbellek taramasi (RESULTS §14.26). Saldiri: `cache` yolunu kaza sonucu kurulabilecek
    bicimlerde yazmak (tirnakli parca, `os.path.join`, f-string, degiskene atama). Guvenli davranis: hepsi
    yakalanir (bu saldirilar savusturulur)."""
    assert _tara(tmp_path, "study/k.py", metin) == ["study/k.py"]


@pytest.mark.parametrize("metin", [
    pytest.param("from data import binance_vision as bv\nyol = bv.onbellek_yolu('klines', '4h', 'BTCUSDT.parquet')\n"
                 "df = bv.onbellekten_oku(yol)\n", marks=_XF, id="binance_vision_onbellek_yolu_ve_oku"),
    pytest.param("from data.binance_vision import onbellekten_oku\ndf = onbellekten_oku(p)\n", marks=_XF,
                 id="onbellekten_oku_dogrudan"),
    pytest.param("import pandas as pd\nfor p in config.KOK.rglob('*.parquet'):\n    df = pd.read_parquet(p)\n",
                 marks=_XF, id="rglob_parquet_cache_anilmadan"),
    pytest.param("import pandas as pd\ndf = pd.read_parquet(config.KOK / 'CACHE' / 'klines' / 'x.parquet')\n",
                 marks=_XF, id="buyuk_harf_CACHE_windows_buyuk_kucuk_harf_duyarsiz"),
    pytest.param("import pandas as pd\ndf = pd.read_parquet(config.KOK / 'Cache' / 'klines' / 'x.parquet')\n",
                 marks=_XF, id="Cache_baslik_harfi"),
])
def test_onbellek_deseni_dolayli_onbellek_erisimini_yakalamali(tmp_path, metin):
    """Kural: kapanis turu onbellek taramasi; CLAUDE.md §3.3 (C1/C2 verisi yalniz kapili yukleyicilerle). Saldiri:
    `cache` yol parcasini anmadan onbellege ulasmak: `data.binance_vision.onbellek_yolu`/`onbellekten_oku` (kume
    kapisi yok), `rglob('*.parquet')` ile depoyu taramak, Windows'ta buyuk/kucuk harf duyarsiz `CACHE`/`Cache`.
    Guvenli davranis: tarama bunlari yakalar. Gozlenen (saldiri basarili): desen yalniz kucuk harfli, sinirlayicili
    `cache` metnini ve `ONBELLEK_DIZINI` adini arar."""
    assert _tara(tmp_path, "study/k.py", metin) == ["study/k.py"]


@_XF
def test_onbellek_taramasi_pyw_uzantisini_kapsar(tmp_path):
    """Kural: kapanis turu onbellek taramasi. Saldiri: analiz betigini `.pyw` uzantisiyla yazmak (python calistirir;
    `ONBELLEK_UZANTILARI` yalniz `.py` ve `.ipynb`). Guvenli davranis: dogrudan onbellek okuyan `.pyw` yakalanir.
    Gozlenen (saldiri basarili): uzanti taranmaz."""
    assert _tara(tmp_path, "study/k.pyw", "pd.read_parquet('cache/klines/x.parquet')\n") == ["study/k.pyw"]


@pytest.mark.xfail(reason="`ihlaller` yol parcalarinda 'cache' gecen her dosyayi tum taramalardan muaf tutar", **_BASARILI)
def test_cache_adli_alt_dizindeki_analiz_dosyasi_taramadan_muaf_olmamali(tmp_path):
    """Kural: kapanis turu onbellek taramasi (`ihlaller` `"cache" in yol.parts` dosyalari atlar). Saldiri: analiz
    kodunu `study/cache/k.py` (ya da `analysis/h2/cache/k.py`) altina koymak; dosyanin kendisi `cache/` yolunu
    okuyor. Guvenli davranis: yakalanir (yalniz depo kokundeki `cache/` verisi muaf olmali, `cache` adli her alt
    dizin degil). Gozlenen (saldiri basarili): dosya hicbir tarama tarafindan gorulmez."""
    assert _tara(tmp_path, "study/cache/k.py", "pd.read_parquet('cache/klines/x.parquet')\n") == ["study/cache/k.py"]


@pytest.mark.xfail(reason="`ihlaller` cache/ altindaki .py dosyalarini tum taramalardan (onay atlatma dahil) muaf tutar",
                   **_BASARILI)
def test_cache_dizinindeki_py_dosyasi_onay_atlatma_taramasindan_muaf_olmamali(tmp_path):
    """Kural: onay kaydi ve kosu butunlugu turu `ONAY_ATLATMA_DESENI`. Saldiri: onay kosusu durumunu bozan kodu
    (`split._AKTIF_KOSU = ...`) `cache/k.py` icine koymak (cache/ git'e girmez ama kod calisir). Guvenli davranis:
    kok dizindeki `cache/` altinda bile calistirilabilir `.py` dosyasi taranir. Gozlenen (saldiri basarili):
    `ihlaller` `cache` yol parcali dosyayi ilk satirda atlar."""
    assert _tara(tmp_path, "cache/k.py", "split._AKTIF_KOSU = None\n", desen=ONAY_ATLATMA_DESENI,
                 uzantilar=(".py",)) == ["cache/k.py"]


# --- Saldiri 7 ve 8: itilemeyen kayit ------------------------------------------------------------------------


def test_push_reddedilirse_kosu_acilmaz_kayda_itilemedi_yazilir_ve_veri_kapali_kalir(depo):
    """Kural: kapanis turu `_it_ya_da_kaydet` (kimlik bilgisi yok / uzak `pre-receive` reddi; fetch calisir).
    Saldiri: itme reddedilir. Guvenli davranis (savusturulur): govde HIC calismaz, kayitta [BASLADI, ITILEMEDI
    (asama=BASLADI)], onay kumesi verisi kapali (`OnayGerekli`), calisma agaci temiz, uzak degismemis."""
    uzak = uzak_depo(depo)
    ilk = git(uzak, "rev-parse", "main").strip()
    _hook_kur(uzak, depo)
    _reddi_ac(uzak)
    girildi = False
    with pytest.raises(split.OnayUzakHatasi, match="ITILEMEDI"):
        with kosu("H1", "C1"):
            girildi = True
    assert not girildi
    satirlar = split.kayit_satirlari(_kayit(depo))
    assert [s["durum"] for s in satirlar] == ["BASLADI", "ITILEMEDI"]
    assert satirlar[1]["asama"] == "BASLADI"
    with pytest.raises(split.OnayGerekli):
        split.kume_erisimi(B_SEMBOLU, "C1", onay=True)
    assert git(depo, "status", "--porcelain").strip() == ""
    assert git(uzak, "rev-parse", "main").strip() == ilk


def test_basladi_itilemeyince_tek_atis_hakki_veri_okunmadan_yanar_bulgu(depo):
    """BULGU (belgeleme; guvenli davranis tartismali): BASLADI itilemediginde govde hic calismaz (veri okunmaz), ama
    BASLADI ve ITILEMEDI satirlari yerelde commit edilmistir. Itme sorunu giderilip kayit elle itilince cift
    `OnayTekrari` ile HARCANMIS olur: kullanici veriye hic bakmadan tek atis hakkini kaybeder. Bu test mevcut
    davranisi sabitler (isaretsiz): itilmeden yeni kosu `OnayUzakHatasi`; elle itildikten sonra ayni cift
    `OnayTekrari`, baska cift acilir. Kural (CLAUDE.md §3.3) muhafazakar tarafta hata verir; kurtarma yolu yok."""
    uzak = uzak_depo(depo)
    _hook_kur(uzak, depo)
    _reddi_ac(uzak)
    with pytest.raises(split.OnayUzakHatasi):
        with kosu("H1", "C1"):
            pass
    _reddi_kapat(uzak)
    _reddedilmeli("H1", "C1", split.OnayUzakHatasi)  # itilmemis satirlar: once itilmeli
    git(depo, "push", "-q", "origin", "HEAD:refs/heads/main")
    _reddedilmeli("H1", "C1", split.OnayTekrari)  # veri okunmadan harcanmis
    _acilmali("H2", "C1")


def test_itilemedi_commiti_de_basarisiz_olursa_kayit_commitsiz_kalir_ve_yeni_kosu_acilmaz(depo):
    """Kural: kapanis turu `_it_ya_da_kaydet` (`OnayKaydiCommitsiz` yutulur). Saldiri: itme reddedilir VE ITILEMEDI
    satirinin commit'i de basarisiz olur (yerel `pre-commit` hook'u ITILEMEDI iceren diff'i reddeder). Guvenli
    davranis (savusturulur): kosu yine `OnayUzakHatasi` ile acilmaz, ITILEMEDI satiri calisma agacinda commitsiz
    kalir; yeni kosu `OnayKaydiCommitsiz`; satiri `checkout` ile atmak BASLADI'yi itilmemis birakir ve yeni kosu
    `OnayUzakHatasi`; cift her durumda harcanmis kalir."""
    uzak = uzak_depo(depo)
    _hook_kur(uzak, depo)
    _reddi_ac(uzak)
    hook = depo / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(exist_ok=True)
    hook.write_text('#!/bin/sh\nif git diff --cached | grep -q "durum=ITILEMEDI"; then exit 1; fi\nexit 0\n',
                    encoding="utf-8", newline="\n")
    hook.chmod(0o755)
    girildi = False
    with pytest.raises(split.OnayUzakHatasi):
        with kosu("H1", "C1"):
            girildi = True
    assert not girildi
    assert [s["durum"] for s in split.kayit_satirlari(_kayit(depo))] == ["BASLADI", "ITILEMEDI"]
    assert git(depo, "status", "--porcelain").strip() != ""  # ITILEMEDI satiri commitsiz
    hook.unlink()
    _reddi_kapat(uzak)
    _reddedilmeli("H2", "C1", split.OnayKaydiCommitsiz)
    # SALDIRI ADIMI: ITILEMEDI satirini at. (Ana oturum: satir `git add` ile index'te oldugu icin duz
    # `checkout -- <dosya>` onu silmez; niyet HEAD'e donmek oldugundan `checkout HEAD --` kullanildi.)
    git(depo, "checkout", "HEAD", "--", "ONAY_KAYDI.md")
    _reddedilmeli("H2", "C1", split.OnayUzakHatasi)  # HEAD'deki BASLADI hala itilmemis
    _reddedilmeli("H1", "C1", split.OnayUzakHatasi, split.OnayTekrari)


def test_bitti_itilemese_de_uzaktaki_basladi_cifti_yerel_gecmis_silinince_de_harcar(depo):
    """Kural: kapanis turu `_bitis_yaz`; CLAUDE.md §3.3 tek atis. Saldiri: BASLADI itilir, govde calisir (veriye
    bakilir), BITTI itmesi reddedilir (`OnayUzakHatasi`, kayitta ITILEMEDI asama=BITTI); saldirgan yerel gecmisi
    `ilk`e sarip reflog'u siler, reddi kaldirir ve ayni cifti yeniden kosmak ister. Guvenli davranis (savusturulur):
    uzaktaki BASLADI satiri cifti harcar (`OnayTekrari`); sonuc yerelde silinse de veriye bakma hakki geri gelmez."""
    uzak = uzak_depo(depo)
    _hook_kur(uzak, depo)
    ilk = git(depo, "rev-parse", "HEAD").strip()
    girildi = False
    with pytest.raises(split.OnayUzakHatasi, match="BITTI"):
        with kosu("H1", "C1") as tutamak:
            girildi = True
            _reddi_ac(uzak)  # BASLADI itildi; bundan sonrakiler reddedilir
            tutamak.sonuc_bildir("TEST")
    assert girildi
    assert "H1 C1 BASLADI" in _uzak_mesajlari(uzak)
    assert "BITTI" not in _uzak_mesajlari(uzak)
    _reddi_kapat(uzak)
    _hepsini_unut(depo, ilk)
    assert split.kayit_satirlari(_kayit(depo)) == []
    _reddedilmeli("H1", "C1", split.OnayTekrari)


def _bagimsiz_head_bitti_itilemez(depo):
    """SALDIRI ADIMLARI: bagimsiz HEAD'de kosu; BITTI itmesi reddedilir. Doner: hata mesaji."""
    uzak = uzak_depo(depo)
    _hook_kur(uzak, depo)
    git(depo, "checkout", "-q", "--detach")
    with pytest.raises(split.OnayUzakHatasi) as bilgi:
        with kosu("H1", "C1") as tutamak:
            _reddi_ac(uzak)
            tutamak.sonuc_bildir("TEST")
    _reddi_kapat(uzak)
    return str(bilgi.value)


@pytest.mark.xfail(reason="hata mesajindaki `git push origin main` bagimsiz HEAD'in itilmemis satirlarini itmez",
                   **_BASARILI)
def test_hata_mesajindaki_push_onerisi_bagimsiz_headde_itilmemis_kaydi_iter(depo):
    """Kural: kapanis turu `_it_ya_da_kaydet` hata mesaji ('kaydi elle itin (`git push origin main`)'). Saldiri
    (kaza): kosu bagimsiz HEAD'de acildi; BITTI itilemedi; operator mesajdaki komutu AYNEN calistirir. Komut
    yerel `main` DALINI iter, bagimsiz HEAD'in commit'lerini degil. Guvenli davranis: onerilen komut sorunu
    cozer, yani sonraki kosu (H2, C1) `OnayUzakHatasi` vermeden acilir. Gozlenen (saldiri basarili): komut
    `Everything up-to-date` ya da reddedilir, HEAD'in satirlari itilmemis kalir, yeni kosu `OnayUzakHatasi`."""
    mesaj = _bagimsiz_head_bitti_itilemez(depo)
    eslesme = re.search(r"`(git push [^`]+)`", mesaj)
    assert eslesme, f"mesajda push onerisi yok: {mesaj}"
    subprocess.run(["git", *eslesme.group(1).split()[1:]], cwd=depo, capture_output=True, text=True)
    _acilmali("H2", "C1")


def test_head_main_itmesi_bagimsiz_head_durumunu_cozer(depo):
    """Kural: kapanis turu `_kaydi_it` (`HEAD:refs/heads/main`). Karsilastirma: ayni durumda operator
    `git push origin HEAD:main` calistirirsa itilmemis satirlar uzaga gider. Guvenli davranis (savusturulur): sonraki
    kosu (H2, C1) acilir; ayni cift `OnayTekrari`."""
    _bagimsiz_head_bitti_itilemez(depo)
    git(depo, "push", "-q", "origin", "HEAD:refs/heads/main")
    _reddedilmeli("H1", "C1", split.OnayTekrari)
    _acilmali("H2", "C1")
