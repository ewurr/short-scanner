"""Kapi sertlestirme turu 3 saldiri testleri (N turu).

Hedefler (gorev tanimi): onay bagami (`split._AKTIF_KOSU`, ic ice kosu, kosu icinde istisna,
`mae`/`pozisyon_fundingi`nin baska bir acik kosu icinde cagrilmasi, `OnayTekrari`de baglamin
kirlenmesi, `numpy.str_` hipotez adi), hata siniflari (`OlayOlusmaz` / `VeriHatasi` / duz
`ValueError` ayrimi, `DonemDisiSinyal`), ikincil ufuk (birincil basarili + ikincil kendi
nedeniyle reddedilen olay, ret gerekcesinin korunmasi, H3'un 7/30 gunluk ikincil ufuklari).

Yaklasim kodu KIRMAYA calisir. Gecen (xfail olmayan) testler savusturulan saldirilardir;
`xfail(strict=True)` ile isaretli testler basarili saldirilardir (bulunan acik). Aga cikmaz.
Mevcut hicbir test dosyasi degistirilmedi; bu YENI bir dosyadir.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import config
from data import funding, pencere, pozisyon, split
from kapi_yardimcisi import veri
from sinyal_yardimcisi import kontrol
from uygunluk_yardimcisi import esikler
from onay_yardimcisi import kosu

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H = lambda n: pd.Timedelta(hours=n)  # noqa: E731

# Rev.12 (§6 rev.12 "Kontrol barinda sinyal pencereleri"): kontrol bari capasiz
# pencerelerin hesaplanabilmesini gerektirir (H1: 185 bar, H3: 121 gun gecmis), bu yuzden
# donem basi sinyalden yeterince geriye alindi. Testlerin iddialari degismedi.
DB, B = T("2024-09-01"), T("2025-06-30 20:00")
Z = pd.date_range(T("2025-03-01"), B, freq="4h")
MUM = pd.DataFrame({"open_time": Z, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
FUND = pd.DataFrame({"odeme_zamani": pd.date_range(DB, B + H(4), freq="8h"), "aralik_saat": 8.0,
                     "oran": 1e-4, "oran_8h": 1e-4})
T_SINYAL = T("2025-03-10 04:00")


@pytest.fixture
def gecici_kayit(tmp_path, monkeypatch):
    yol = tmp_path / "onay_gecici.md"
    yol.write_text("bas\n", encoding="utf-8")
    split._test_kaydi_ayarla(yol)
    return yol


def _c1_ortak(hipotez="H1"):
    tanim = pencere.hipotez_ufuklari(hipotez)
    kayit = veri(MUM, FUND, DB, B, uygun_bas=DB, grup="B")
    return dict(hipotez=hipotez, birincil_ufuk=tanim.birincil, kume="C1", **kayit,
                **kontrol(hipotez), **esikler(tanim.bar)), tanim


# --- 1. `_AKTIF_KOSU` dogrudan atama -----------------------------------------------------------------


# SALDIRI BULGUSU (kapi sertlestirme turu 3, xfail idi): split._AKTIF_KOSU'yu context manager disinda dogrudan
# atamak, onay kaydina TEK SATIR bile yazilmadan C1 erisimini aciyordu. Onay kaydi ve kosu butunlugu turunda
# kapandi (denetci KS3 D-B1): `split` modulunun korunan adlari disaridan atanamaz (`OnayKorumasi`, `OnayGerekli`
# alt sinifi). xfail isareti kaldirildi; atama satiri `pytest.raises` icine alindi, geri kalan iddia ayni.
def test_aktif_kosu_dogrudan_atama_kayitsiz_onay_acar(gecici_kayit, monkeypatch):
    assert split.aktif_onay_kosusu() is None
    ortak, tanim = _c1_ortak("H1")
    # `monkeypatch.setattr` geri alma kaydini atamadan ONCE yazdigi icin teardown'da korunan adi geri atamaya
    # calisip hata verir; ayni atama duz `setattr` ile denenir.
    with pytest.raises(split.OnayKorumasi):
        setattr(split, "_AKTIF_KOSU", ("H1", "C1"))
    # Ana oturum duzeltmesi (tur 3): govde ISTENEN davranisi iddia eder: kayitsiz atanmis bir kosu C1 pozisyonu
    # acamamali.
    assert gecici_kayit.read_text(encoding="utf-8") == "bas\n"
    with pytest.raises(split.OnayGerekli):
        pozisyon.olay_karari(T_SINYAL, tanim.birincil, tanim.bar, **ortak)


# --- 2. Ic ice kosu, disaridaki kosuyu bozmaz ---------------------------------------------------------


def test_ic_ice_kosu_disaridaki_aktif_kosuyu_bozmaz(gecici_kayit):
    """Ic ice kosu RuntimeError verir; disaridaki kosunun baglami (`_AKTIF_KOSU`) bu basarisiz
    denemeden ETKILENMEMELI (on-kayit §3, CLAUDE.md §3.3: 'Ic ice kosu acilamaz')."""
    with kosu("H1", "C1"):
        assert split.aktif_onay_kosusu() == ("H1", "C1")
        with pytest.raises(RuntimeError):
            with kosu("H2", "C2"):
                pytest.fail("ic ice kosu acilmamali")
        assert split.aktif_onay_kosusu() == ("H1", "C1")
        ortak, tanim = _c1_ortak("H1")
        pozisyon.onay_dogrula(pozisyon.olay_karari(T_SINYAL, tanim.birincil, tanim.bar, **ortak))
    assert split.aktif_onay_kosusu() is None


# --- 3. Kosu icinde istisna baglami temizler ------------------------------------------------------


def test_kosu_icinde_istisna_baglami_temizler(gecici_kayit):
    """Blok icinde beklenmeyen bir istisna firlarsa `_AKTIF_KOSU` yine de temizlenmeli (contextmanager
    `finally`); aksi halde bir sonraki kosu kalici olarak kilitli kalirdi."""
    with pytest.raises(ValueError, match="kasitli"):
        with kosu("H1", "C1"):
            raise ValueError("kasitli hata")
    assert split.aktif_onay_kosusu() is None
    # Ayni cift tek atistir: kayit zaten yazildigi icin tekrar denemek OnayTekrari verir.
    with pytest.raises(split.OnayTekrari):
        with kosu("H1", "C1"):
            pytest.fail("tekrar acilmamali")
    assert split.aktif_onay_kosusu() is None
    # Ama FARKLI bir cift sorunsuz acilabilir: baglam gercekten temiz.
    with kosu("H2", "C1"):
        assert split.aktif_onay_kosusu() == ("H2", "C1")
    assert split.aktif_onay_kosusu() is None


# --- 4. `OnayTekrari`de `_AKTIF_KOSU` kirlenmesi --------------------------------------------------


def test_onay_tekrari_aktif_kosuyu_kirletmez(gecici_kayit):
    """Ayni (hipotez, kume) ciftinin ikinci kosusu `OnayTekrari` verir; bu reddedilen deneme
    `_AKTIF_KOSU`yu YANLIS bir degere sabitlememeli (kayit `onay_kaydet` icinde, `_AKTIF_KOSU`
    atamasindan ONCE basarisiz olmali)."""
    with kosu("H1", "C2"):
        pass
    assert split.aktif_onay_kosusu() is None
    with pytest.raises(split.OnayTekrari):
        with kosu("H1", "C2"):
            pytest.fail("tekrar acilmamali")
    assert split.aktif_onay_kosusu() is None
    # Baska bir hipotezle C2 hala acilabilir olmali (kilit kalici degil).
    with kosu("H2", "C2"):
        assert split.aktif_onay_kosusu() == ("H2", "C2")


# --- 5. `mae` / `pozisyon_fundingi`: baska bir ACIK kosu icinde cagri --------------------------------


def test_mae_baska_hipotezin_acik_kosusunda_reddedilir(gecici_kayit):
    """Pozisyon (H1, C1) icin onaylandi ve kosu kapandi. Sonra FARKLI bir cift ((H2, C1)) icin kosu
    acilirken eski pozisyonun `mae`/`pozisyon_fundingi`si cagrilirsa `OnayUyusmazligi` vermeli:
    aktif kosu VAR ama pozisyonunkiyle eslesmiyor (yalnizca 'kosu kapali' durumunun degil, 'yanlis
    kosu acik' durumunun da yakalandigini sinar; denetci KS2 D-B1)."""
    ortak, tanim = _c1_ortak("H1")
    with kosu("H1", "C1"):
        p = pozisyon.olay_karari(T_SINYAL, tanim.birincil, tanim.bar, **ortak)
        pozisyon.onay_dogrula(p)
    with kosu("H2", "C1"):
        with pytest.raises(split.OnayUyusmazligi):
            pozisyon.mae(p)
        with pytest.raises(split.OnayUyusmazligi):
            funding.pozisyon_fundingi(p)


# --- 6. `numpy.str_` hipotez adi ----------------------------------------------------------------------


def test_numpy_str_hipotez_adi_kosu_acamaz(gecici_kayit):
    """`numpy.str_` gercek `str`in bir alt sinifidir (`type(...) is not str` denetimini hedefler);
    `_hipotez_dogrula` `type(hipotez) is not str` kullandigi icin reddetmeli."""
    sahte = np.str_("H1")
    assert sahte == "H1" and isinstance(sahte, str) and type(sahte) is not str
    with pytest.raises(ValueError):
        with kosu(sahte, "C1"):
            pytest.fail("kosu acilmamali")
    assert split.aktif_onay_kosusu() is None


# --- 7. `config.HIPOTEZLER` monkeypatch (KARARLI atlatma, bulgu SAYILMAZ) ----------------------------


def test_config_hipotezler_monkeypatch_belgeleme(gecici_kayit, monkeypatch):
    """Gorev tanimi geregi bu bir bulgu SAYILMAZ: `config.HIPOTEZLER` on-kayit sabitidir ve tek guven
    kaynagidir (CLAUDE.md §5); onu calisma aninda degistirmek, kilitli dosyayi elle duzenlemeye
    esdeger kasitli bir mudahaledir. Burada yalnizca beklenen (kacinilmaz) davranis belgelenir."""
    monkeypatch.setattr(config, "HIPOTEZLER", config.HIPOTEZLER + ("SAHTE_HIPOTEZ",))
    with kosu("SAHTE_HIPOTEZ", "C1"):
        assert split.aktif_onay_kosusu() == ("SAHTE_HIPOTEZ", "C1")


# --- 8. Hata siniflari: `DonemDisiSinyal` `pencere` seviyesinde de `OlayOlusmaz` degil ----------------


def test_donem_disi_sinyal_pencere_seviyesinde_olay_olusmaz_yutulmaz():
    """`pencere.pozisyon_plani` dogrudan cagrildiginda (kapi `pozisyon.olay_karari` degil): donem disi
    sinyal `DonemDisiSinyal` (ValueError alt sinifi) verir; F2 tarzi 'yalnizca OlayOlusmaz yakala'
    dongusu bunu YUTMAMALI (on-kayit §6 rev.8, kapi sertlestirme turu 3, denetci KS2 D-C1)."""
    donem_bas = T("2025-03-15")
    t_disi = T("2025-03-05 04:00")
    assert t_disi < donem_bas
    assert (Z == t_disi).any(), "test kurulumu: bar seride fiziksel olarak var olmali"

    def cagri():
        return pencere.pozisyon_plani(Z, t_disi, 18, config.BAR_4H, birincil_ufuk=18, kume_baslangic=None,
                                      kume_bitis=None, donem_baslangic=donem_bas, donem_bitis=B)

    with pytest.raises(pencere.DonemDisiSinyal):
        try:
            cagri()
        except pencere.OlayOlusmaz:  # pragma: no cover - yakalanmamali
            pytest.fail("DonemDisiSinyal OlayOlusmaz olarak yutuldu")


def test_cikis_bari_kume_disi_olmayan_eksik_seri_duz_valueerror():
    """`cikis_bari`: hedef bar eksik, `kume_bitis=None` (kume siniri yok) ve B'ye kadar da bar yoksa
    bu bozuk/eksik bir seridir; `OlayOlusmaz` alt sinifi DEGIL, duz `ValueError` olmali (on-kayit bozuk
    veriyi bir 'olay olusmaz' kurali gibi tanimlamaz)."""
    giris = T_SINYAL + H(4)
    hedef_acilis = pencere.cikis_hedefi(giris, 18, config.BAR_4H) - H(4)
    z = Z[Z < hedef_acilis]
    assert (z == giris).any(), "test kurulumu: giris bari seride kalmali"
    with pytest.raises(ValueError) as hata:
        pencere.cikis_bari(z, giris, 18, config.BAR_4H, birincil_ufuk=18, donem_bitis=B, kume_bitis=None)
    assert not isinstance(hata.value, pencere.OlayOlusmaz)


# --- 9. Ikincil ufuk: birincil basarili, ikincil KENDI nedeniyle reddedilir --------------------------


def test_ikincil_ufuk_kume_sinirina_takilir_birincil_basaridir():
    """Sinyal, KESIF kume sonuna (`config.KESIF_SONU`) yakin: 18 barlik (72s) birincil cikis kume icinde
    kalir ve onaylanir; 42 barlik (168s) ikincil cikis kume sonunu asar ve KENDI `KumeSiniriHatasi`sini
    verir (on-kayit §3 'Kume siniri ve ufuk': ikincil ufuklar kendi kurallarina tabidir)."""
    db4 = T("2025-04-01")
    bitis4 = T("2025-09-10 20:00")  # kume (KESIF) sonunun otesinde: donem kume disina tasiyor
    z4 = pd.date_range(T("2025-06-01"), bitis4, freq="4h")
    mum4 = pd.DataFrame({"open_time": z4, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
    fr4 = pd.DataFrame({"odeme_zamani": pd.date_range(db4, bitis4 + H(4), freq="8h"), "aralik_saat": 8.0,
                       "oran": 0.0, "oran_8h": 0.0})
    t = T("2025-08-28 16:00")
    giris = t + H(4)
    assert giris + 18 * H(4) <= pd.Timestamp(config.KESIF_SONU)
    assert giris + 42 * H(4) > pd.Timestamp(config.KESIF_SONU)

    tanim = pencere.hipotez_ufuklari("H1")
    kayit = veri(mum4, fr4, db4, bitis4, uygun_bas=db4)
    ortak = dict(hipotez="H1", birincil_ufuk=tanim.birincil, kume="KESIF", **kayit,
                 **kontrol("H1"), **esikler(tanim.bar))
    p18 = pozisyon.olay_karari(t, 18, tanim.bar, **ortak)
    pozisyon.onay_dogrula(p18)
    with pytest.raises(pencere.KumeSiniriHatasi):
        pozisyon.olay_karari(t, 42, tanim.bar, **ortak)


def test_ikincil_cagrida_birincilin_ret_gerekcesi_korunur():
    """Birincil (18 bar) `GirisBariYok` ile reddedilirse, ikincil (6 bar) cagrisi ONCE ayni birincil
    cagriyi tekrar eder ve ayni ret gerekcesiyle durur: ikincilin KENDI hesaplamasina hic gecilmez ve
    gerekce degismez (on-kayit §4 'Ikincil ufuklar ... onay kararlari birincil ufka gore verilir')."""
    tanim = pencere.hipotez_ufuklari("H1")
    giris_ani = T_SINYAL + H(4)
    eksik = MUM.loc[MUM["open_time"] != giris_ani]
    kayit = veri(eksik, FUND, DB, B, uygun_bas=DB)
    ortak = dict(hipotez="H1", birincil_ufuk=tanim.birincil, kume="KESIF", **kayit,
                 **kontrol("H1"), **esikler(tanim.bar))
    with pytest.raises(pencere.GirisBariYok) as birincil_hata:
        pozisyon.olay_karari(T_SINYAL, 18, tanim.bar, **ortak)
    with pytest.raises(pencere.GirisBariYok) as ikincil_hata:
        pozisyon.olay_karari(T_SINYAL, 6, tanim.bar, **ortak)
    assert (pencere.ret_gerekcesi(birincil_hata.value) == pencere.ret_gerekcesi(ikincil_hata.value)
            == "giris_bari_yok")


def test_h3_ikincil_ufuklar_7_ve_30_kendi_kurallarina_tabidir():
    """H3'un (1d izgara) ikincil ufuklari 7 ve 30 gundur (`config.IKINCIL_UFUKLAR[BAR_1D]`). Birincil
    (14 gun) penceresinin DISINDA (14-30 gun arasi) eksik bir funding kaydi: 14 ve 7 gunluk pozisyonlar
    etkilenmez ve onaylanir, 30 gunluk pozisyon KENDI penceresinde `FundingTamDegil` ile reddedilir."""
    t3 = T("2025-03-10")
    tanim = pencere.hipotez_ufuklari("H3")
    assert tanim.ikincil == (7, 30)
    giris = pencere.giris_ani(t3, config.BAR_1D)
    eksik = giris + pd.Timedelta(days=20)  # 14 < 20 < 30
    assert (FUND["odeme_zamani"] == eksik).any(), "test kurulumu: eksik zaman 8s izgarasinda olmali"
    fr = FUND.loc[FUND["odeme_zamani"] != eksik].reset_index(drop=True)

    def _karar_h3(ufuk):
        kayit = veri(MUM, fr, DB, B, uygun_bas=DB)
        return pozisyon.olay_karari(t3, ufuk, config.BAR_1D, hipotez="H3", birincil_ufuk=tanim.birincil,
                                    kume="KESIF", **kayit, **kontrol("H3"),
                                    **esikler(config.BAR_1D))

    p14 = _karar_h3(14)
    pozisyon.onay_dogrula(p14)
    p7 = _karar_h3(7)
    pozisyon.onay_dogrula(p7)
    with pytest.raises(pozisyon.FundingTamDegil):
        _karar_h3(30)
