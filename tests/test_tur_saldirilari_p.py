"""Onay kaydi ikinci tur: sizinti testcisi P saldirilari (commit 73c80cd, `data/split.py`).

Amac kodu kirmaktir. Basarili bir saldiri `xfail(strict=True)` ile isaretlidir ve govde ISTENEN GUVENLI
davranisi iddia eder: saldiri gercekten basarili olursa govde kirmizi olur (xfail), kod duzeltilirse XPASS(strict)
testi kirar ve isaret kaldirilmalidir. Isaretsiz testler savusturulan saldirilardir (kod o noktada saglam).

Git testleri GERCEK gecici depoda kosar (`onay_yardimcisi.gecici_depo`); gercek `ONAY_KAYDI.md` ve gercek depo
hicbir testte kullanilmaz. Modul degisimi denemeleri `vars(...)` ile try/finally icinde geri alinir.
"""

from __future__ import annotations

import contextlib
import hashlib
import types
from contextlib import contextmanager

import pandas as pd
import pytest

import config
from data import split
from onay_yardimcisi import DEPO_BETIGI, gecici_depo, gecici_kayit, git, kosu

B_SEMBOLU = "BTCUSDT"  # gercek split.csv'de B grubu (test_onay_kaydi_git.py ile ayni varsayim)

# Basarili saldiri: govdedeki guvenli davranis iddiasi kirilir (ya da beklenen hata gelmez: "DID NOT RAISE").
_BASARILI = dict(strict=True, raises=(AssertionError, pytest.fail.Exception))


@pytest.fixture
def depo(tmp_path):
    return gecici_depo(tmp_path)


# --- yardimcilar --------------------------------------------------------------------------------------------


def _dal(depo) -> str:
    return git(depo, "rev-parse", "--abbrev-ref", "HEAD").strip()


def _kayit(depo) -> str:
    return (depo / "ONAY_KAYDI.md").read_text(encoding="utf-8")


def _tekrar_reddedilmeli(hipotez="H1", kume="C1"):
    """Cift harcanmis: kosu acilmamali (`OnayTekrari`)."""
    with pytest.raises(split.OnayTekrari):
        with kosu(hipotez, kume):
            pass


def _yeniden_yonlendir(depo):
    """Test ayarini yeniden `depo`ya cevirir (baska bir worktree'de kosu yapildiktan sonra)."""
    gecici_kayit(depo / "ONAY_KAYDI.md", depo=depo, betik=DEPO_BETIGI)


@contextmanager
def _ham_ata(modul, ad, deger):
    """SALDIRI ADIMI: `modul.ad = deger` duz atamasi. Koruma varsa buradan hata cikar. Cikista `vars` ile geri alinir."""
    once = vars(modul)[ad]
    try:
        setattr(modul, ad, deger)
        yield
    finally:
        vars(modul)[ad] = once


def _grup_hesapla(tuz: str, anahtar: str) -> str:
    ozet = hashlib.sha256((tuz + anahtar).encode("utf-8")).hexdigest()
    return "A" if int(ozet, 16) % 2 == 0 else "B"


def _sahte_tablo(yol, satirlar) -> None:
    pd.DataFrame(satirlar, columns=split.BOLME_SUTUNLARI).to_csv(yol, index=False, lineterminator="\n")


# --- Saldiri 1: bagimsiz (detached) HEAD + reflog suresi dolmasi --------------------------------------------


def test_bagimsiz_head_kosusu_reflog_varken_cift_harcanmis(depo):
    """Kural: tek atis git gecmisine bakar (`--all --reflog`). Saldiri: bagimsiz HEAD'de kosu, sonra dala donus;
    kayit commit'leri hicbir dalda degil, yalnizca HEAD reflog'unda. Guvenli davranis: cift hala harcanmis
    (on kosul; asil saldiri asagidaki xfail testtir)."""
    dal = _dal(depo)
    git(depo, "checkout", "-q", "--detach")
    with kosu("H1", "C1"):
        pass
    git(depo, "checkout", "-q", dal)
    assert split.kayit_satirlari(_kayit(depo)) == []  # calisma agacinda iz yok
    _tekrar_reddedilmeli("H1", "C1")


# Kapanis turu: kayit uzak depoya bagli; saldiri savusturuldu, xfail kaldirildi (RESULTS §14.26).
def test_bagimsiz_head_kosusu_reflog_suresi_dolunca_cift_yeniden_acilmamali(depo):
    """Kural: CLAUDE.md §3.3 tek atis. Saldiri: `checkout --detach` -> kosu -> `checkout <dal>` -> `reflog expire
    --expire-unreachable=now --all`. Kayit commit'leri yalnizca reflog'da tutuldugu icin (dal yok) reflog suresi
    dolunca (varsayilan gc.reflogExpireUnreachable = 30 gun; `git gc --auto` kendiliginden calistirir) gecmis
    denetimi cifti gormez. Guvenli davranis: `OnayTekrari`."""
    dal = _dal(depo)
    git(depo, "checkout", "-q", "--detach")
    with kosu("H1", "C1"):
        pass
    git(depo, "checkout", "-q", dal)
    git(depo, "reflog", "expire", "--expire-unreachable=now", "--all")
    _tekrar_reddedilmeli("H1", "C1")


# --- Saldiri 2: git worktree -------------------------------------------------------------------------------


# Kapanis turu: kayit uzak depoya bagli; saldiri savusturuldu, xfail kaldirildi (RESULTS §14.26).
def test_worktree_detached_kosusu_ana_depoda_cifti_harcamali(depo, tmp_path):
    """Kural: CLAUDE.md §3.3 tek atis. Saldiri: `git worktree add --detach`, kayit yolunu o worktree'ye
    yonlendirip kosu, `git worktree remove --force`. Commit'ler yalnizca worktree'nin kendi HEAD'indedir; ana
    depodaki `--all --reflog` bunlari gormez. Guvenli davranis: ana depoda ayni cift `OnayTekrari`."""
    wt = tmp_path / "wt"
    git(depo, "worktree", "add", "-q", "--detach", str(wt))
    gecici_kayit(wt / "ONAY_KAYDI.md", depo=wt, betik=DEPO_BETIGI)
    with kosu("H1", "C1"):
        pass
    git(depo, "worktree", "remove", "--force", str(wt))
    _yeniden_yonlendir(depo)
    _tekrar_reddedilmeli("H1", "C1")


def test_worktree_dal_kosusu_worktree_silinince_dal_uzerinden_gorunur(depo, tmp_path):
    """Kural: tek atis. Saldiri: `worktree add -b dal2`, orada kosu, worktree'yi sil. Dal kaldigi icin
    `--all` commit'leri gorur. Guvenli davranis: ana depoda `OnayTekrari` (bu saldiri savusturulur)."""
    wt = tmp_path / "wt"
    git(depo, "worktree", "add", "-q", "-b", "dal2", str(wt))
    gecici_kayit(wt / "ONAY_KAYDI.md", depo=wt, betik=DEPO_BETIGI)
    with kosu("H1", "C1"):
        pass
    git(depo, "worktree", "remove", "--force", str(wt))
    _yeniden_yonlendir(depo)
    _tekrar_reddedilmeli("H1", "C1")


# Kapanis turu: kayit uzak depoya bagli; saldiri savusturuldu, xfail kaldirildi (RESULTS §14.26).
def test_worktree_dal_kosusu_dal_silinince_cift_yeniden_acilmamali(depo, tmp_path):
    """Kural: tek atis. Saldiri: `worktree add -b dal2` -> kosu -> `worktree remove` -> `branch -D dal2`. Dalin
    reflog'u dalla, worktree'nin HEAD reflog'u worktree'yle silinir; ana depoda reflog girdisi da kalmaz.
    Guvenli davranis: `OnayTekrari`."""
    wt = tmp_path / "wt"
    git(depo, "worktree", "add", "-q", "-b", "dal2", str(wt))
    gecici_kayit(wt / "ONAY_KAYDI.md", depo=wt, betik=DEPO_BETIGI)
    with kosu("H1", "C1"):
        pass
    git(depo, "worktree", "remove", "--force", str(wt))
    git(depo, "branch", "-D", "dal2")
    _yeniden_yonlendir(depo)
    _tekrar_reddedilmeli("H1", "C1")


# --- Saldiri 3: dali birlestirmeden silmek ------------------------------------------------------------------


def test_dal_birlestirilmeden_silinince_reflog_cifti_hala_harcanmis_tutar(depo):
    """Kural: tek atis. Saldiri: yeni dalda kosu, `checkout <ana>`, `branch -D`. HEAD reflog'u commit'leri hala
    tutar. Guvenli davranis: `OnayTekrari` (savusturulur)."""
    ana = _dal(depo)
    git(depo, "checkout", "-q", "-b", "gecici")
    with kosu("H1", "C1"):
        pass
    git(depo, "checkout", "-q", ana)
    git(depo, "branch", "-D", "gecici")
    _tekrar_reddedilmeli("H1", "C1")


# Kapanis turu: kayit uzak depoya bagli; saldiri savusturuldu, xfail kaldirildi (RESULTS §14.26).
def test_dal_silinip_reflog_suresi_dolunca_cift_yeniden_acilmamali(depo):
    """Kural: tek atis. Saldiri: `checkout -b gecici` -> kosu -> `checkout <ana>` -> `branch -D gecici` ->
    `reflog expire --expire-unreachable=now --all` (30 gun sonra `gc --auto`'nun yapacagi sey). Guvenli
    davranis: `OnayTekrari`."""
    ana = _dal(depo)
    git(depo, "checkout", "-q", "-b", "gecici")
    with kosu("H1", "C1"):
        pass
    git(depo, "checkout", "-q", ana)
    git(depo, "branch", "-D", "gecici")
    git(depo, "reflog", "expire", "--expire-unreachable=now", "--all")
    _tekrar_reddedilmeli("H1", "C1")


# --- Saldiri 4: iki dal + birlestirme (tarih sadelestirmesi) -------------------------------------------------


def test_iki_dalda_ayni_cift_ikinci_dalda_reddedilir(depo):
    """Kural: tek atis. Saldiri: ayni cift iki ayri dalda (ikisi de ilk commit'ten). `--all` ilk dalin
    commit'lerini ikinci dalda gorur. Guvenli davranis: ikinci dalda `OnayTekrari` (savusturulur)."""
    ana = _dal(depo)
    git(depo, "checkout", "-q", "-b", "dalA")
    with kosu("H1", "C1"):
        pass
    git(depo, "checkout", "-q", ana)
    git(depo, "checkout", "-q", "-b", "dalB")
    _tekrar_reddedilmeli("H1", "C1")


def _iki_dal_kur_ve_birlestir(depo, strateji):
    """dalA: H1 C1, dalB: H2 C1 (ikisi de ilk commit'ten); dalB, dalA'ya `strateji` ile birlestirilir (dalA
    tarafi kazanir, dalB'nin kayit satirlari birlestirilmis dosyada YOK)."""
    ana = _dal(depo)
    git(depo, "checkout", "-q", "-b", "dalB")
    with kosu("H2", "C1"):
        pass
    git(depo, "checkout", "-q", ana)
    git(depo, "checkout", "-q", "-b", "dalA")
    # Kapanis turu: dalB'nin kosusu origin/main'e itildi; dalA origin/main'i icermedigi icin dalA'da kosu acilmaz.
    # Saldirinin on kosulu (iki dalda paralel kosu) artik kurulamiyor; birlestirme yine yapilir.
    with pytest.raises(split.OnayUzakHatasi):
        with kosu("H1", "C1"):
            pass
    git(depo, "merge", "-q", *strateji, "--no-ff", "--no-edit", "dalB")


@pytest.mark.parametrize("strateji", [["-X", "ours"], ["-s", "ours"]], ids=["X-ours", "s-ours"])
def test_ours_birlestirmesi_dal_silinse_de_reflog_varken_cift_harcanmis(depo, strateji):
    """Kural: tek atis. Saldiri: cakismayi tek tarafa cozen birlestirme, sonra ikinci dal silinir; reflog
    duruyor. HEAD reflog'u dalB commit'lerini tutar. Guvenli davranis: `OnayTekrari` (savusturulur)."""
    _iki_dal_kur_ve_birlestir(depo, strateji)
    git(depo, "branch", "-D", "dalB")
    _tekrar_reddedilmeli("H2", "C1")


# Kapanis turu: kayit uzak depoya bagli; saldiri savusturuldu, xfail kaldirildi (RESULTS §14.26).
@pytest.mark.parametrize("strateji", [["-X", "ours"], ["-s", "ours"]], ids=["X-ours", "s-ours"])
def test_ours_birlestirmesi_dal_ve_reflog_silinince_diger_dalin_cifti_harcanmali(depo, strateji):
    """Kural: tek atis; `_gecmis_kaydi` butun gecmisi taramali. Saldiri: dalA (H1) ve dalB (H2); dalB `ours`
    ile birlestirilir (dosya dalA'nin haliyle ayni kalir); `branch -D dalB` + `reflog expire --expire=now --all`.
    dalB commit'leri birlestirme commit'inin 2. ebeveyni olarak ulasilabilir durumdadir, ama dosya birlestirmede
    1. ebeveynle ayni oldugu icin `git log -- <dosya>` 2. ebeveyni sadelestirir ve o satirlari hic listelemez
    (`--full-history` yok). Guvenli davranis: ("H2","C1") harcanmis, `OnayTekrari`."""
    _iki_dal_kur_ve_birlestir(depo, strateji)
    git(depo, "branch", "-D", "dalB")
    git(depo, "reflog", "expire", "--expire=now", "--all")
    _tekrar_reddedilmeli("H2", "C1")


def test_revert_ile_geri_alinan_kayit_commitleri_cifti_harcanmis_birakir(depo):
    """Kural: tek atis. Saldiri: kosunun iki kayit commit'i `git revert` ile geri alinir (dosyadan satirlar
    gider, commit'ler dalda kalir). Guvenli davranis: `OnayTekrari` (savusturulur)."""
    ilk = git(depo, "rev-parse", "HEAD").strip()
    with kosu("H1", "C1"):
        pass
    git(depo, "revert", "--no-edit", f"{ilk}..HEAD")
    assert split.kayit_satirlari(_kayit(depo)) == []
    _tekrar_reddedilmeli("H1", "C1")


def test_kayit_dosyasi_silinip_commit_edilse_cift_harcanmis_kalir(depo):
    """Kural: tek atis; silinen dosya durumu (`gecmis_satirlari` yalnizca `-` satirlari gorur). Saldiri: kayit
    dosyasi `git rm` ile silinip commit edilir (calisma agaci ve HEAD'de dosya yok). Guvenli davranis: dosya
    yokken `_head_kaydi`/`_kaydi_oku` bos doner, ama gecmis cifti tutar: `OnayTekrari`."""
    with kosu("H1", "C1"):
        pass
    git(depo, "rm", "-q", "ONAY_KAYDI.md")
    git(depo, "commit", "-q", "-m", "kayit dosyasi silindi")
    assert not (depo / "ONAY_KAYDI.md").exists()
    _tekrar_reddedilmeli("H1", "C1")


# --- Saldiri 5: .git/info/attributes ile gecmis denetimini korlestirmek -------------------------------------


@pytest.mark.xfail(reason="P-6: `.git/info/attributes` icinde `ONAY_KAYDI.md binary`/`-diff` -> `git log -p` "
                          "'Binary files differ' yazar, hunk yok; gecmis denetimi kor (`--text` yok)", **_BASARILI)
@pytest.mark.parametrize("nitelik", ["binary", "-diff"])
def test_info_attributes_ile_kayit_ikili_isaretlenince_gecmis_denetimi_kor_olmamali(depo, nitelik):
    """Kural: tek atis gecmis denetimi. Saldiri: izlenmeyen, commit edilmeyen `.git/info/attributes` dosyasina
    `ONAY_KAYDI.md <nitelik>` yazilir (calisma agaci temiz kalir); kosu; `reset --hard <ilk>` (commit'ler yalniz
    reflog'da). `git log -p` artik metin farki yerine 'Binary files differ' basar; `gecmis_satirlari` hicbir
    satir bulamaz. Guvenli davranis: `OnayTekrari` (denetim `--text` ile zorlanmali ya da ikili farki hata sayip
    reddetmeli)."""
    ilk = git(depo, "rev-parse", "HEAD").strip()
    bilgi = depo / ".git" / "info"
    bilgi.mkdir(exist_ok=True)
    (bilgi / "attributes").write_text(f"ONAY_KAYDI.md {nitelik}\n", encoding="utf-8")
    with kosu("H1", "C1"):
        pass
    git(depo, "reset", "--hard", "-q", ilk)
    # Kapanis turu: HEAD origin/main'i icermeli; saldiri bir adim daha ister (kayitsiz birlestirme). Kosu
    # itildigi icin ikinci kosu uzak depoda iz birakir.
    git(depo, "merge", "-q", "-s", "ours", "--no-edit", "origin/main")
    assert split.kayit_satirlari(_kayit(depo)) == []
    _tekrar_reddedilmeli("H1", "C1")


# --- Saldiri 6: git replace --------------------------------------------------------------------------------


@pytest.mark.xfail(reason="P-7: `git replace <kayit-commit> <ilk>` nesne okumasini saptirir; `git log` "
                          "`--no-replace-objects` olmadan yerine konan commit'i gosterir, satirlar gorunmez", **_BASARILI)
def test_git_replace_ile_kayit_commitleri_gizlenince_cift_yeniden_acilmamali(depo):
    """Kural: tek atis gecmis denetimi. Saldiri: kosu; `reset --hard <ilk>`; kosunun iki commit'i
    (`git replace -f <c> <ilk>`) ilk commit'le degistirilir. `git log --all --reflog -p` degistirilmis nesneyi
    okur ve kayit satirlarini gormez. Guvenli davranis: `OnayTekrari` (denetim `--no-replace-objects` ile
    calismali)."""
    ilk = git(depo, "rev-parse", "HEAD").strip()
    with kosu("H1", "C1"):
        pass
    kayit_commitleri = git(depo, "rev-list", f"{ilk}..HEAD").split()
    assert len(kayit_commitleri) == 2
    git(depo, "reset", "--hard", "-q", ilk)
    # Kapanis turu: HEAD origin/main'i icermeli; saldiri bir adim daha ister (kayitsiz birlestirme). Kosu
    # itildigi icin ikinci kosu uzak depoda iz birakir.
    git(depo, "merge", "-q", "-s", "ours", "--no-edit", "origin/main")
    for sha in kayit_commitleri:
        git(depo, "replace", "-f", sha, ilk)
    _tekrar_reddedilmeli("H1", "C1")


# --- Saldiri 7: modul bagimliliklarini duz atamayla degistirmek ---------------------------------------------


def _git_log_bos_donen_subprocess():
    """`git log` cagrilarinda bos cikti donen, gerisini gercek `subprocess`e devreden sahte modul."""
    import subprocess as gercek

    class Sahte:
        CompletedProcess = gercek.CompletedProcess

        @staticmethod
        def run(komut, *argumanlar, **anahtarlar):
            if len(komut) > 1 and komut[1] == "log":
                return gercek.CompletedProcess(komut, 0, stdout="", stderr="")
            return gercek.run(komut, *argumanlar, **anahtarlar)

    return Sahte()


@pytest.mark.xfail(reason="P-8: `split.subprocess` korunan adlarda degil; sahte `run` ile `git log` bos "
                          "doner, gecmis denetimi kor", **_BASARILI)
def test_split_subprocess_atamasi_gecmis_denetimini_korlestirmemeli(depo):
    """Kural: koruma katmani (denetci OK D-B2); tek atis. Saldiri: `split.subprocess = sahte` (`git log`
    bos doner); once kosu, `reset --hard <ilk>` (commit'ler yalniz gecmiste), sonra ayni cift. Guvenli
    davranis: atama `OnayKorumasi` verir ya da denetim yine de `OnayTekrari` verir."""
    ilk = git(depo, "rev-parse", "HEAD").strip()
    with kosu("H1", "C1"):
        pass
    git(depo, "reset", "--hard", "-q", ilk)
    # Kapanis turu: HEAD origin/main'i icermeli; saldiri bir adim daha ister (kayitsiz birlestirme). Kosu
    # itildigi icin ikinci kosu uzak depoda iz birakir.
    git(depo, "merge", "-q", "-s", "ours", "--no-edit", "origin/main")
    with pytest.raises((split.OnayKorumasi, split.OnayTekrari)):
        with _ham_ata(split, "subprocess", _git_log_bos_donen_subprocess()):
            with kosu("H1", "C1"):
                pass


@pytest.mark.xfail(reason="P-9: `split.config` korunan adlarda degil; kopya config `ONAY_KUMELERI=()` ile "
                          "C1 kosusuz acilir", **_BASARILI)
def test_split_config_atamasi_c1i_kosusuz_acmamali():
    """Kural: CLAUDE.md §3.3 (`onay=True` bayragi + kosu olmadan C1/C2 reddedilir). Saldiri:
    `split.config = SimpleNamespace(**vars(config), ONAY_KUMELERI=())`; `config.ONAY_KUMELERI` kendisi korunur
    ama `split`in `config` adi korunmaz. Guvenli davranis: `OnayGerekli` (ya da atamada `OnayKorumasi`)."""
    if not config.SPLIT_CSV.exists():
        pytest.skip("split.csv yok")
    sahte = types.SimpleNamespace(**vars(config))
    sahte.ONAY_KUMELERI = ()
    with pytest.raises(split.OnayGerekli):
        with _ham_ata(split, "config", sahte):
            split.kume_erisimi(B_SEMBOLU, "C1", onay=True)


@pytest.mark.xfail(reason="P-10: `split.klines` korunan adlarda degil; sahte `donem_kes` kesmeden dondurur, "
                          "KESIF cagrisina 2025-09-01 sonrasi bar sizar", **_BASARILI)
def test_split_klines_atamasi_kesif_kumesine_c2_barlari_sizdirmamali():
    """Kural: CLAUDE.md §3.2-3.3; KESIF araligi 2025-08-31 sonunda biter. Saldiri: `split.klines =
    SimpleNamespace(donem_kes=lambda c, b, s: c)`; `yukle(A-sembolu, ..., "KESIF", mum_yukleyici=...)` kesmeden
    doner. Guvenli davranis: atama `OnayKorumasi` verir ya da cikti yine KESIF_SONU'nda kesilir."""
    if not config.SPLIT_CSV.exists():
        pytest.skip("split.csv yok")
    tablo = split.split_oku()
    a_sembol = tablo.loc[tablo["grup"] == "A", "sembol"].iloc[0]
    zamanlar = pd.to_datetime(["2025-08-30", "2025-08-31", "2025-09-01", "2025-09-02"], utc=True)
    ham = pd.DataFrame({"open_time": zamanlar, "close": [1.0, 1.0, 1.0, 1.0]})
    sahte = types.SimpleNamespace(donem_kes=lambda cerceve, bas, son: cerceve,
                                  ham_mumlari_yukle=lambda sembol, bar, yenile=False: ham)
    try:
        with _ham_ata(split, "klines", sahte):
            cerceve = split.yukle(a_sembol, "1d", "KESIF", mum_yukleyici=lambda s, b: ham)
    except split.OnayKorumasi:
        return
    assert cerceve["open_time"].max() <= pd.Timestamp(config.KESIF_SONU), "KESIF'e C2 donemi bari sizdi"


def _sahte_bolme_kur(ad, tmp_path, monkeypatch):
    """`ad` adli bagimliligi bolme dogrulamasini kandiracak sekilde hazirlar; doner: sahte deger.
    Sahte tablo: BTCUSDT (gercekte B) satiri A olarak, `SPLIT_CSV` o tabloya yonlendirilir."""
    yol = tmp_path / "sahte_split.csv"
    if ad == "varlik_anahtari":
        anahtar = next(k for k in (f"ANAHTAR{i}" for i in range(1000)) if split.grup(k) == "A")
        _sahte_tablo(yol, [(B_SEMBOLU, anahtar, "A")])
        sahte = lambda sembol, zincirler=None: anahtar  # noqa: E731
    else:
        _sahte_tablo(yol, [(B_SEMBOLU, B_SEMBOLU, "A")])
        if ad == "split_dogrula":
            sahte = lambda tablo: tablo  # noqa: E731
        elif ad == "grup":
            sahte = lambda anahtar: "A"  # noqa: E731
        else:  # hashlib: her ozet 0 -> cift -> A
            class _Ozet:
                def hexdigest(self):
                    return "0"

            sahte = types.SimpleNamespace(sha256=lambda veri: _Ozet())
    monkeypatch.setattr(config, "SPLIT_CSV", yol)
    return sahte


@pytest.mark.xfail(reason="P-11: `split_dogrula`, `grup`, `varlik_anahtari`, `hashlib` korunan adlarda degil; "
                          "sahte bagimlilik + sahte split.csv B grubundan bir coini KESIF'e sokar", **_BASARILI)
@pytest.mark.parametrize("ad", ["split_dogrula", "grup", "varlik_anahtari", "hashlib"])
def test_bolme_dogrulama_bagimliliklari_atanarak_b_coini_kesife_sokulamaz(ad, tmp_path, monkeypatch):
    """Kural: CLAUDE.md §3.2 (bolme dokunulmaz; disaridan tablo dayatilamaz), denetci OK D-B2 (`split_oku`
    korunur). Saldiri: `SPLIT_CSV` (korunmayan config adi) sahte bir tabloya (BTCUSDT = A) yonlendirilir ve
    `split_oku`nun dogrulamada kullandigi modul adlarindan biri (`split_dogrula`/`grup`/`varlik_anahtari`/
    `hashlib`) duz atamayla sahtelenir. Guvenli davranis: atama `OnayKorumasi` verir, dogrulama
    `BolmeTutarsizligi` verir ya da BTCUSDT KESIF icin izinsiz kalir."""
    if _grup_hesapla(config.BOLME_TUZU, B_SEMBOLU) != "B":
        pytest.skip("BTCUSDT bu bolmede B degil")
    sahte = _sahte_bolme_kur(ad, tmp_path, monkeypatch)
    try:
        with _ham_ata(split, ad, sahte):
            izinli = split.kume_erisimi(B_SEMBOLU, "KESIF")[0]
    except (split.OnayKorumasi, split.BolmeTutarsizligi):
        return
    assert izinli is False, "B grubundan BTCUSDT KESIF kumesine sizdi"


@pytest.mark.xfail(reason="P-12: `config.BOLME_TUZU` degistirilebilir; yeni tuzla uretilen tablo dogrulamadan "
                          "gecer ve B'den bir coin A olur", **_BASARILI)
def test_config_bolme_tuzu_degistirilerek_bolme_yeniden_dagitilamaz(tmp_path, monkeypatch):
    """Kural: CLAUDE.md §3.2 / on-kayit §3 (bolme tuzu `short-lab-v1:` sabit). Saldiri: `config.BOLME_TUZU`
    baska bir degere atanir (korunan adlarda yok), BTCUSDT'yi A yapan bir tuz aranir, sahte tablo o tuzla
    yazilir. `split_dogrula` grubu yeni tuzla yeniden hesaplayip onaylar. Guvenli davranis: atama
    `SabitDegistirilemez` verir, dogrulama `BolmeTutarsizligi` verir ya da BTCUSDT KESIF icin izinsiz kalir."""
    if _grup_hesapla(config.BOLME_TUZU, B_SEMBOLU) != "B":
        pytest.skip("BTCUSDT bu bolmede B degil")
    tuz = next(t for t in (f"saldiri{i}:" for i in range(1000)) if _grup_hesapla(t, B_SEMBOLU) == "A")
    yol = tmp_path / "sahte_split.csv"
    _sahte_tablo(yol, [(B_SEMBOLU, B_SEMBOLU, "A")])
    monkeypatch.setattr(config, "SPLIT_CSV", yol)
    try:
        with _ham_ata(config, "BOLME_TUZU", tuz):
            izinli = split.kume_erisimi(B_SEMBOLU, "KESIF")[0]
    except (config.SabitDegistirilemez, split.BolmeTutarsizligi):
        return
    assert izinli is False, "tuz degistirilerek B grubundan BTCUSDT KESIF kumesine sokuldu"


@pytest.mark.xfail(reason="P-13: `config.YENIDEN_ADLANDIRMA` sozlugu yerinde degistirilebilir; sahte zincir + "
                          "sahte tablo BTCUSDT'yi A grubuna tasir", **_BASARILI)
def test_config_yeniden_adlandirma_sozlugu_degistirilerek_bolme_kaydirilamaz(tmp_path, monkeypatch):
    """Kural: on-kayit §3 rev.2 (dokuz kabul edilmis zincir); CLAUDE.md §3.2. Saldiri:
    `config.YENIDEN_ADLANDIRMA["BTCUSDT"] = "ASSETX"` (A grubuna dusen bir anahtar), sahte tablo
    (BTCUSDT, ASSETX, A). Sozluk degistirilebilir bir `dict`. Guvenli davranis: degistirme `TypeError`/
    `SabitDegistirilemez` verir (salt okunur eslem), dogrulama `BolmeTutarsizligi` verir ya da BTCUSDT KESIF
    icin izinsiz kalir."""
    if _grup_hesapla(config.BOLME_TUZU, B_SEMBOLU) != "B":
        pytest.skip("BTCUSDT bu bolmede B degil")
    anahtar = next(k for k in (f"ASSETX{i}" for i in range(1000)) if _grup_hesapla(config.BOLME_TUZU, k) == "A")
    yol = tmp_path / "sahte_split.csv"
    _sahte_tablo(yol, [(B_SEMBOLU, anahtar, "A")])
    monkeypatch.setattr(config, "SPLIT_CSV", yol)
    zincir = config.YENIDEN_ADLANDIRMA
    try:
        try:
            zincir[B_SEMBOLU] = anahtar
            izinli = split.kume_erisimi(B_SEMBOLU, "KESIF")[0]
        except (TypeError, config.SabitDegistirilemez, split.BolmeTutarsizligi):
            return
    finally:
        zincir.pop(B_SEMBOLU, None)
    assert izinli is False, "yeniden adlandirma sozlugu degistirilerek BTCUSDT KESIF'e sokuldu"


@pytest.mark.xfail(reason="P-14: `config.HIPOTEZLER` degistirilebilir; yeni hipotez adi C1/C2 icin ek tek atis "
                          "hakki dogurur", **_BASARILI)
def test_config_hipotezleri_genisletilip_yeni_adla_onay_kosusu_acilamaz(depo):
    """Kural: CLAUDE.md §3.3 (her hipotez icin BIR kez), on-kayit §5 (H1, H2, H3). Saldiri:
    `config.HIPOTEZLER = (*HIPOTEZLER, "H4")` (korunan adlarda yok), `onay_kosusu("H4", "C1")`. Guvenli
    davranis: atama `SabitDegistirilemez` verir ya da kosu `ValueError` ile reddedilir."""
    yeni = (*config.HIPOTEZLER, "H4")
    with pytest.raises((config.SabitDegistirilemez, ValueError)):
        with _ham_ata(config, "HIPOTEZLER", yeni):
            with kosu("H4", "C1"):
                pass


# --- Saldiri 8: `gecmis_satirlari` ayristirici kenar durumlari ---------------------------------------------


def _blok(*eklenen: str, sondaki_yeni_satir_yok: bool = False) -> str:
    """Tek dosya icin `git log -p` bloku (hunk'li); eklenen satirlar `+` ile."""
    metin = "diff --git a/K b/K\nindex 1111111..2222222 100644\n--- a/K\n+++ b/K\n@@ -1 +1 @@\n x\n"
    metin += "".join(f"+{s}\n" for s in eklenen)
    if sondaki_yeni_satir_yok:
        metin += "\\ No newline at end of file\n"
    return metin


def test_gecmis_satirlari_cok_commitli_cikti_hepsini_toplar():
    """Kural: gecmis denetimi butun commit'lerin eklenmis satirlarini toplar. Saldiri: uc commit'lik cikti
    (`--format=` boslugu, arada `diff --git` basliklari, ikisinde 'No newline' isareti). Guvenli davranis:
    tum eklenen satirlar, sirayla."""
    cikti = _blok("a") + _blok("b", "c", sondaki_yeni_satir_yok=True) + _blok("d", sondaki_yeni_satir_yok=True)
    assert split.gecmis_satirlari(cikti) == "a\nb\nc\nd"


def test_gecmis_satirlari_no_newline_isareti_satir_sayilmaz_ve_sonrasini_yutmaz():
    """Kural: ayni. Saldiri: `\\ No newline at end of file` satiri silinen satirdan sonra gelir ve ardindan
    yeniden eklenen satir + yeni satir. Guvenli davranis: isaret yok sayilir; `-x` gitmis, `+x` ve `+| a |`
    kalir."""
    cikti = ("diff --git a/K b/K\n--- a/K\n+++ b/K\n@@ -1 +1,2 @@\n-x\n\\ No newline at end of file\n"
             "+x\n+| a |\n\\ No newline at end of file\n")
    assert split.gecmis_satirlari(cikti) == "x\n| a |"


def test_gecmis_satirlari_silinen_dosya_farki_satir_eklemez():
    """Kural: ayni. Saldiri: dosya silme farki (`+++ /dev/null`, yalnizca `-` satirlari). Guvenli davranis:
    bos sonuc; ardindan gelen yeni olusturma farki (`--- /dev/null`, `+++ b/K`) satirlarini normal toplar."""
    silme = "diff --git a/K b/K\ndeleted file mode 100644\nindex 111..000\n--- a/K\n+++ /dev/null\n@@ -1,2 +0,0 @@\n-a\n-b\n"
    olusturma = "diff --git a/K b/K\nnew file mode 100644\nindex 000..222\n--- /dev/null\n+++ b/K\n@@ -0,0 +1 @@\n+z\n"
    assert split.gecmis_satirlari(silme) == ""
    assert split.gecmis_satirlari(silme + olusturma) == "z"


def test_gecmis_satirlari_hunk_icindeki_baslik_taklidi_satirlari_yutulmaz():
    """Kural: ayni. Saldiri: eklenen satirlarin icerigi baslik gibi gorunur (`+++ b/x`, `+@@ -1 +1 @@`, `+diff
    --git a/x b/x`); bunlar hunk icinde `+` onekiyle gelir. Guvenli davranis: hepsi eklenmis satir sayilir."""
    cikti = _blok("++ b/x", "@@ -1 +1 @@", "diff --git a/x b/x", "| kayit |")
    assert split.gecmis_satirlari(cikti).splitlines() == ["++ b/x", "@@ -1 +1 @@", "diff --git a/x b/x", "| kayit |"]


def test_gecmis_satirlari_crlf_cikti_satirlari_tanir():
    """Kural: ayni. Saldiri: CRLF ile commit edilmis kayit (Windows): eklenen satirlar `\\r` ile biter.
    Guvenli davranis: `onay_satirlari` satiri temiz tanir, cift harcanir."""
    cikti = _blok("| t | C1 | b | c (temiz) | hipotez=H1 kosu=k surec=1 durum=BASLADI |\r").replace("\n", "\r\n")
    assert split.kayittaki_kosular(split.gecmis_satirlari(cikti)) == {("H1", "C1")}


@pytest.mark.xfail(reason="P-15: `gecmis_satirlari` ikili fark satirini ('Binary files ... differ' / 'GIT "
                          "binary patch') sessizce bos sayar; kor denetim hata vermez", **_BASARILI)
@pytest.mark.parametrize("satir", ["Binary files a/K and b/K differ", "GIT binary patch"])
def test_gecmis_satirlari_ikili_fark_sessizce_bos_sayilmamali(satir):
    """Kural: gecmis denetimi kor kalirsa tek atis islemez (bkz. P-6). Saldiri: `git log -p` ciktisinda kayit
    dosyasi ikili gorunur. Guvenli davranis: ayristirici bunu tanir ve hata verir (`OnayGerekli` ya da
    `ValueError`), sessizce bos donmez."""
    cikti = f"diff --git a/K b/K\nindex 111..222 100644\n{satir}\n"
    with pytest.raises((split.OnayGerekli, ValueError)):
        split.gecmis_satirlari(cikti)


def test_no_newline_ile_biten_kayit_commitlerinden_iki_satir_da_okunur(depo):
    """Kural: gecmis denetimi (gercek `git log -p`). Saldiri: kayit dosyasinin son satiri sonda yeni satir
    olmadan commit edilir; sonraki commit satirin ustune yeni satir ekler (`\\ No newline at end of file`
    isaretli fark). Guvenli davranis: iki satirdaki cift de gecmisten okunur."""
    baslik = "| Tarih (UTC) | Kume | Cagiran betik | Commit | Not |\n|---|---|---|---|---|\n"
    satir1 = "| 2026-01-01 00:00:00 | C1 | b | abc (temiz) | hipotez=H1 kosu=k1 surec=1 durum=BASLADI |"
    satir2 = "| 2026-01-01 00:00:01 | C2 | b | abc (temiz) | hipotez=H2 kosu=k2 surec=1 durum=BASLADI |"
    yol = depo / "ONAY_KAYDI.md"
    yol.write_bytes((baslik + satir1).encode("utf-8"))
    git(depo, "add", "-A")
    git(depo, "commit", "-q", "-m", "satir1 (sonda yeni satir yok)")
    yol.write_bytes((baslik + satir1 + "\n" + satir2).encode("utf-8"))
    git(depo, "add", "-A")
    git(depo, "commit", "-q", "-m", "satir2")
    assert {("H1", "C1"), ("H2", "C2")} <= split.kayittaki_kosular(split._gecmis_kaydi())


# --- Saldiri 9: kosu sirasinda kayittan eski satir silmek ---------------------------------------------------


def _eski_satiri_sil(depo, hipotez):
    yol = depo / "ONAY_KAYDI.md"
    metin = yol.read_bytes().decode("utf-8")
    yeni = "".join(s for s in metin.splitlines(keepends=True) if f"hipotez={hipotez} " not in s)
    assert yeni != metin
    yol.write_bytes(yeni.encode("utf-8"))


@pytest.mark.xfail(reason="P-16: kosu sirasinda eski satir silinirse bitis commit'i `git add` + `commit --only` "
                          "ile silmeyi de koşu mesajiyla commit eder; `_bitis_yaz` yalnizca kendi BASLADI "
                          "satirina bakar", **_BASARILI)
def test_kosu_sirasinda_eski_kayit_satirini_silmek_reddedilmeli(depo):
    """Kural: CLAUDE.md §3.3 (`ONAY_KAYDI.md` yalnizca ekleme, silme yok). Saldiri: H1 C1 tamamlanir; H2 C1
    kosusu sirasinda kodun kendisi H1'in iki satirini dosyadan siler. Bitis satiri eklenirken
    `_kayit_commitli_denetle` calisma agaci = HEAD kontrolunu commit'ten SONRA yapar (silme zaten commit
    edilmistir). Guvenli davranis: kosu kapanirken silme tespit edilir (`OnayKorumasi` ya da
    `OnayKaydiCommitsiz`) ve `HEAD:ONAY_KAYDI.md` H1 satirlarini korur."""
    with kosu("H1", "C1"):
        pass
    with pytest.raises((split.OnayKorumasi, split.OnayKaydiCommitsiz)):
        with kosu("H2", "C1"):
            _eski_satiri_sil(depo, "H1")


def test_kosu_sirasinda_silinen_eski_satirin_cifti_gecmisten_harcanmis_kalir(depo):
    """Kural: tek atis (gecmis). Saldiri: yukaridaki silme basarili olsa bile H1 C1 satirlari daha once commit
    edilmisti. Guvenli davranis: ("H1","C1") gecmisten harcanmis kalir ve yeniden acilamaz (savusturulur;
    silme hatasi verilirse o da kabul)."""
    with kosu("H1", "C1"):
        pass
    with contextlib.suppress(split.OnayGerekli):
        with kosu("H2", "C1"):
            _eski_satiri_sil(depo, "H1")
    assert ("H1", "C1") in split.harcanan_ciftler()
    with pytest.raises((split.OnayTekrari, split.OnayKaydiCommitsiz)):
        with kosu("H1", "C1"):
            pass


def test_kosu_sirasinda_kendi_basladi_satirini_silmek_reddedilir(depo):
    """Kural: CLAUDE.md §3.3 (silme yok). Saldiri: kosu kendi BASLADI satirini siler. Guvenli davranis:
    `_bitis_yaz` kayitta tek BASLADI bulamaz ve `OnayKorumasi` verir (savusturulur)."""
    with pytest.raises(split.OnayKorumasi):
        with kosu("H1", "C1"):
            _eski_satiri_sil(depo, "H1")
