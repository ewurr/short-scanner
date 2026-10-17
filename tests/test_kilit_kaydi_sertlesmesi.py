"""Kilit kaydinin sertlesmesi: ekleme kurali, ayristirma ve zorunlu alanlar (madde 4a-4c).

Bulgular:
  - K-C3 / sizinti 4 (madde 4a): ekleme kurali denetimi yalnizca YEREL gecmise ve reflog'a
    bakiyordu ve `--full-history` BAYRAGI KOMUTTA YOKTU (docstring'de vardi). Iki sonucu:
    (i) yan dalda degistirilip `merge -s ours` ile birlestirilen icerik gorunmuyordu;
    (ii) `reset --hard` + `reflog expire` + `gc` ile yerel gecmis yeniden yazildiginda
    degistirilmis kayit yine "tek blob" gorunuyordu. `ONAY_KAYDI` ayni riski `origin/main`
    gecmisine bakarak kapatiyor; kilit kaydinda o simetri yoktu.
  - K-C7 (madde 4b): `float()` `inf`/`Infinity`/`1e999` kabul ediyordu (`inf` K2 farki > 0
    denetimini geciyordu); `\\d` Unicode rakamlari esliyordu (tam genislikli `１５０`);
    `parametreler` alani kimlikle karsilastirilmiyordu; `ortalama_net_getiri` istege bagliydi,
    yani §8 madde 4'un ikinci kosulu kod duzeyinde denetlenemiyordu.
  - K-C1 (madde 4c): `gerekce` "secildi" hukmunde de ZORUNLUYDU; on-kaydin harfine uyan bir kayit
    (gerekce yalnizca kapandiysa) kurtarilamaz duruma dusuyordu.

Testler gercek git depolarinda kosar (yerel ciplak uzak depo; aga cikilmaz).
"""

from __future__ import annotations

import pytest

from data import split
from onay_yardimcisi import gecici_depo, git, kilit_metni, kilit_yaz, uzak_depo


def _coz(**alanlar):
    return split.kilit_kaydi_coz(kilit_metni("H2", **alanlar), "H2")


# --- 1. Madde 4b: sayi ayristirmasi -----------------------------------------------------------


@pytest.mark.parametrize("deger", ["inf", "Inf", "INF", "-inf", "Infinity", "infinity", "nan",
                                   "NaN", "1e999", "1e5", "1E5", "0x10", "  inf  "])
def test_ondalik_alanlarda_inf_nan_ve_ustel_gosterim_reddedilir(deger):
    with pytest.raises(split.KilitBozuk, match="duz ondalik"):
        _coz(k2_farki=deger)
    with pytest.raises(split.KilitBozuk, match="duz ondalik"):
        _coz(ortalama_net_getiri=deger)


@pytest.mark.parametrize("deger", ["0.0210", "0,0210", "1", "+0.5", "-0.5", "0.00001"])
def test_duz_ondalik_sayilar_kabul_edilir(deger):
    kayit = _coz(k2_farki=deger) if not deger.startswith("-") else None
    if kayit is None:                      # negatif K2 farki madde 4'e gore reddedilir
        with pytest.raises(split.KilitBozuk, match="K2 farki > 0"):
            _coz(k2_farki=deger)
    else:
        assert kayit.k2_farki > 0


@pytest.mark.parametrize("alan,deger", [("analize_giren_olay", "１５０"), ("olusmus_olay", "４００"),
                                        ("tohum", "２０２６０９１１"),
                                        ("analize_giren_olay", "٣٠٠")])
def test_unicode_rakamlar_reddedilir(alan, deger):
    """`re.ASCII` olmadan `\\d` tam genislikli ve Arapca-Hintce rakamlari da esliyordu."""
    with pytest.raises(split.KilitBozuk, match="tamsayi"):
        _coz(**{alan.replace("analize_giren_olay", "analize_giren").replace("olusmus_olay", "olusmus"): deger}
             if alan in ("analize_giren_olay", "olusmus_olay") else {alan: deger})


@pytest.mark.parametrize("deger", ["１,５", "0.０1", "٠.٥"])
def test_unicode_rakamli_ondalik_reddedilir(deger):
    with pytest.raises(split.KilitBozuk, match="duz ondalik"):
        _coz(k2_farki=deger)


# --- 2. Madde 4b: `parametreler` kimlikle tutarli olmali -------------------------------------


@pytest.mark.parametrize("parametreler", ["phi=0.0010 k=12", "phi=0.0003", "phi=0.0003 k=3 x=1",
                                          "theta=0.20 delta=0.08", "k=3 phi=0.0010",
                                          "phi=0.0003 k=4"])
def test_parametreler_kimlikle_celisirse_reddedilir(parametreler):
    with pytest.raises(split.KilitBozuk, match="ayni demeti gostermiyor"):
        _coz(parametreler=parametreler)


@pytest.mark.parametrize("parametreler", ["phi=0.0003 k=3", "k=3 phi=0.0003", "phi=0.00030 k=3",
                                          "phi=0.0003, k=3", "phi=0.0003; k=3", "PHI=0.0003 K=3"])
def test_ayni_demeti_gosteren_yazimlar_kabul_edilir(parametreler):
    """Karsilastirma SAYISALDIR ve ad kumesi uzerinden yapilir; yazim serbesttir."""
    assert _coz(parametreler=parametreler).secildi


@pytest.mark.parametrize("parametreler", ["", "-", "phi", "phi=", "phi=abc", "phi=inf k=3",
                                          "phi=0.0003 phi=0.0003"])
def test_bozuk_parametre_alani_reddedilir(parametreler):
    with pytest.raises(split.KilitBozuk):
        _coz(parametreler=parametreler)


def test_kapandi_hukmunde_parametreler_aranmaz():
    kayit = split.kilit_kaydi_coz(
        kilit_metni("H2", hukum=split.KILIT_KAPANDI, gerekce="aday yok", yapilandirma="-",
                    parametreler="-", k2_farki="-"), "H2")
    assert kayit.secildi is False


# --- 3. Madde 4a: ekleme kurali -- `--full-history` ve uzak depo simetrisi -------------------


def _ilk_kayit(depo):
    """H2 kaydini yazar, commit'ler ve iter."""
    kilit_yaz(depo, "H2")
    git(depo, "add", ".")
    git(depo, "commit", "-q", "-m", "H2 kaydi")
    git(depo, "push", "-q", "origin", "main")


def test_itilmemis_kayit_reddedilir(tmp_path):
    """Madde 4a: kayit `origin/main` gecmisinde yoksa itilmemis demektir."""
    depo = gecici_depo(tmp_path, kilitler=("H1", "H3"))
    kilit_yaz(depo, "H2")
    git(depo, "add", ".")
    git(depo, "commit", "-q", "-m", "H2 kaydi")
    with pytest.raises(split.KilitYok, match="gecmisinde yok"):
        split.kilit_oku("H2")
    git(depo, "push", "-q", "origin", "main")
    assert split.kilit_oku("H2").secildi


def test_yan_dalda_degistirilip_ours_ile_birlestirilen_kayit_yakalanir(tmp_path):
    """Sizinti 4: `--full-history` olmadan `rev-list` birlestirmenin TEK ebeveynini izler ve yan
    dalda degistirilen icerik GORUNMEZ."""
    depo = gecici_depo(tmp_path, kilitler=("H1", "H3"))
    _ilk_kayit(depo)
    git(depo, "checkout", "-q", "-b", "yan")
    kilit_yaz(depo, "H2", k2_farki="0.9999")
    git(depo, "add", ".")
    git(depo, "commit", "-q", "-m", "yan dalda degistirildi")
    git(depo, "checkout", "-q", "main")
    git(depo, "merge", "-q", "--no-ff", "-s", "ours", "yan", "-m", "ours birlesmesi")
    git(depo, "branch", "-q", "-D", "yan")
    git(depo, "reflog", "expire", "--expire=now", "--all")
    git(depo, "push", "-q", "origin", "main")
    with pytest.raises(split.KilitBozuk, match="farkli icerikle"):
        split.kilit_oku("H2")


def test_yerel_gecmis_yeniden_yazilirsa_uzak_depo_yakalar(tmp_path):
    """K-C3: `reset --hard` + `reflog expire` + `gc` eski blob'u yok eder, yani YEREL gecmiste
    degistirilmis kayit yine "tek blob" gorunur; `origin/main` gecmisi farki gosterir."""
    depo = gecici_depo(tmp_path, kilitler=("H1", "H3"))
    _ilk_kayit(depo)
    ilk = git(depo, "rev-parse", "HEAD").strip()
    kilit_yaz(depo, "H2", k2_farki="0.9999")
    git(depo, "add", ".")
    git(depo, "commit", "-q", "-m", "kayit degistirildi")
    git(depo, "push", "-q", "origin", "main")
    # Yerel gecmisi temizle: eski icerik yerelde artik gorunmuyor.
    git(depo, "reset", "--hard", "-q", "HEAD")
    git(depo, "checkout", "-q", "-B", "main", ilk)
    kilit_yaz(depo, "H2", k2_farki="0.9999")
    git(depo, "add", ".")
    git(depo, "commit", "-q", "-m", "tek commit gibi")
    git(depo, "reflog", "expire", "--expire=now", "--all")
    git(depo, "gc", "-q", "--prune=now")
    with pytest.raises((split.KilitBozuk, split.KilitYok)):
        split.kilit_oku("H2")


def test_uzak_depoda_iki_icerik_varsa_reddedilir(tmp_path):
    depo = gecici_depo(tmp_path, kilitler=("H1", "H3"))
    _ilk_kayit(depo)
    kilit_yaz(depo, "H2", k2_farki="0.5000")
    git(depo, "add", ".")
    git(depo, "commit", "-q", "-m", "degistirildi")
    git(depo, "push", "-q", "origin", "main")
    with pytest.raises(split.KilitBozuk, match="farkli icerikle"):
        split.kilit_oku("H2")


def test_ilk_committe_gelen_kayit_itilmis_sayilir(tmp_path):
    """Olumlu kontrol: `gecici_depo` kilitleri ilk commit'te yazar ve iter."""
    gecici_depo(tmp_path, kilitler=("H1", "H2", "H3"))
    assert split.kilit_oku("H2").secildi
    assert split.kilit_oku("H1").secildi


def test_uzak_izleme_referansi_silinse_de_denetim_calisir(tmp_path):
    """Referans yoksa once alinir (`ONAY_KAYDI` ile ayni yol)."""
    depo = gecici_depo(tmp_path, kilitler=("H1", "H2", "H3"))
    git(depo, "update-ref", "-d", "refs/remotes/origin/main")
    assert split.kilit_oku("H2").secildi
    assert uzak_depo(depo).exists()
