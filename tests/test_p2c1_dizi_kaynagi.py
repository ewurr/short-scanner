"""P2c-1: dizi kurallari kosulu kosul serisinden okur (tasarim notu `p2c1_tasarim.md` §6, kararlar `p2c1_kararlar.md` A1,
A2 ve araştırma tarafinin 2026-11-25 A2 karari: `KararKaynagi`).

- `pozisyon.kosul_kaynagi` / `pozisyon.karar_kaynagi`: imzali, degistirilemez, kopyalanamaz nesneler; parametreleri
  yalnizca kimliktir (hipotez, yapilandirma, kume, sembol, donem_no).
- `dizi.olay_dizisi` girdi denetimi: kaynak ise kimligi dizinin argumanlariyla ayni olmali (degilse `ValueError`); kaynak
  degilse yalnizca pytest testinde kabul edilir, disarida `TypeError` -- onay kumesinde acik onay kosusu olsa bile (A1).
- Dizi esitligi: ayni dunyada dizi, kosul kaynagi ile ve referansin kosuluyla; karar kaynagi ile ve iki argumanli
  sarmalayiciyla ayni olay zamanlarini, capalari ve retleri verir. Yuruyus degismez.
- F2 gereksinimi 11 (kararlar B 1): donem ici boslugu olan sentetik izgarada, GERCEK kosul kaynagiyla, sureler izgara
  ZAMANIYLA olculur, listedeki sirayla uzamaz.
Deger, olay sayisi ve kosulun dogru oldugu bar sayisi yazilmaz. Aga cikmaz.
"""

from __future__ import annotations

import ast
import copy
import inspect
import pickle

import pandas as pd
import pytest

import config
from data import _skaler_referans as ref
from data import dizi, pencere, pozisyon, sinyal, split
from esitlik_yardimcisi import H4, dunya, karar_cagrisi
from kapi_yardimcisi import SENTETIK_DONEMLER, SENTETIK_VERI, veri
from onay_yardimcisi import gecici_kayit, kosu
from tarama_yardimcisi import KOK

BAS, BITIS = "2021-01-01", "2021-08-31 20:00"
KIMLIK_ADLARI = ("hipotez", "yapilandirma", "kume", "sembol", "donem_no")


def _y(hipotez, i=0):
    return dict(sinyal.izgara(hipotez)[i])


def _izgara(hipotez, kimlik):
    return pozisyon.hipotez_izgarasi_barlari(hipotez, kume="KESIF", **kimlik)


def _kaynaklar(hipotez, y, kimlik, kume="KESIF"):
    return (pozisyon.kosul_kaynagi(hipotez, y, kume=kume, **kimlik),
            pozisyon.karar_kaynagi(hipotez, y, kume=kume, **kimlik))


def _dizi(hipotez, y, kimlik, *, kosul=None, karar=None, zamanlar=None):
    bar = config.HIPOTEZ_IZGARASI[hipotez]
    bas, bitis, _ = pozisyon.donem_kaydi(kimlik["sembol"], kimlik["donem_no"])
    kk, kr = _kaynaklar(hipotez, y, kimlik)
    return dizi.olay_dizisi(hipotez, y, _izgara(hipotez, kimlik) if zamanlar is None else zamanlar, bar,
                            birincil_ufuk=config.BIRINCIL_UFUK[bar], kosul=kk if kosul is None else kosul,
                            karar=kr if karar is None else karar, sembol=kimlik["sembol"], kume="KESIF",
                            donem_no=kimlik["donem_no"], donem_baslangic=bas, donem_bitis=bitis)


def _ozet(sonuc):
    return (tuple((o.zaman, o.capa) for o in sonuc.olaylar), tuple((r.zaman, r.capa, r.gerekce) for r in sonuc.retler))


def _ref_kosulu(hipotez, y, kimlik):
    return lambda t, capa: ref.sinyal_kosulu(t, hipotez=hipotez, yapilandirma=y, capa=capa, kume="KESIF", **kimlik)


def _iki_argumanli_karar(hipotez, y, kimlik):
    """Testlerdeki iki argumanli sarmalayici: gercek `olay_karari`, birincil ufuk ve on-kayit esikleri."""
    tanim = pencere.hipotez_ufuklari(hipotez)

    def karar(t, capa):
        return pozisyon.olay_karari(t, tanim.birincil, tanim.bar, hipotez=hipotez, yapilandirma=y, rol="olay",
                                    capa=capa, birincil_ufuk=tanim.birincil, kume="KESIF", **kimlik,
                                    asgari_hacim=pozisyon.eligibility_modulu.hacim_esigi(tanim.bar),
                                    asgari_listeleme_yasi_gun=config.ASGARI_LISTELEME_YASI_GUN)

    return karar


def _test_karari(hipotez, y, kimlik):
    def karar(t, capa):
        return pozisyon._test_onayi(hipotez=hipotez, yapilandirma=y, t=t, rol="olay", capa=capa,
                                    sembol=kimlik["sembol"], kume="KESIF", donem_no=kimlik["donem_no"])

    return karar


class _SplitVekili:
    """`split` modulu koruma altindadir; dizinin gordugu `split_modulu` adina vekil kurulur."""

    def __init__(self, **degisen):
        self.__dict__.update(degisen)

    def __getattr__(self, ad):
        return getattr(split, ad)


@pytest.fixture
def dunya_d():
    return dunya(631, BAS, BITIS)


# --- Kaynak nesneleri ---------------------------------------------------------------------------------------------

def test_kaynak_parametreleri_yalnizca_kimlik():
    """A2 karari (a): ufuk, bar turu, rol ve esikler parametre olarak alinmaz."""
    for f in (pozisyon.kosul_kaynagi, pozisyon.karar_kaynagi):
        assert tuple(inspect.signature(f).parameters) == KIMLIK_ADLARI, f.__name__


def test_kaynaklar_imzali_degistirilemez_kopyalanamaz(dunya_d):
    kimlik, _ = dunya_d
    for k in _kaynaklar("H2", _y("H2"), kimlik):
        sinif = type(k)
        with pytest.raises(TypeError):
            sinif(object(), k.kimlik, _y("H2"))
        for ad in ("kimlik", "_Kaynak__kimlik", "baska"):
            with pytest.raises(AttributeError):
                setattr(k, ad, None)
        with pytest.raises(AttributeError):
            del k._Kaynak__kimlik
        with pytest.raises(TypeError):
            pickle.dumps(k)
        assert copy.copy(k) is k and copy.deepcopy(k) is k
        pozisyon.kaynak_dogrula(k)
        assert k.kimlik == ("H2", sinyal.yapilandirma_kimligi("H2", _y("H2")), "KESIF", kimlik["sembol"], 0)
        # Kimlik bellek duzeyinde degistirilirse (kararli atlatma) imza tutmaz; dizi de reddeder.
        object.__setattr__(k, "_Kaynak__kimlik", ("H2", k.kimlik[1], "KESIF", "BASKAUSDT", 0))
        with pytest.raises(ValueError, match="imza"):
            pozisyon.kaynak_dogrula(k)
    with pytest.raises(TypeError):
        pozisyon.kaynak_dogrula(lambda t, capa: True)


def test_karar_kaynagi_yalnizca_olay_karari_ile_ayni(dunya_d):
    """`KararKaynagi(t, capa)` = `olay_karari(t, birincil, bar, rol="olay", ...)` (ayni sinif ve mesaj ya da ayni pozisyon)."""
    kimlik, ozel = dunya_d
    for hipotez in ("H1", "H2", "H3"):
        _, kr = _kaynaklar(hipotez, _y(hipotez), kimlik)
        izgara = _izgara(hipotez, kimlik)
        barlar = list(izgara[::97]) + (list(ozel["h2"]) if hipotez == "H2" else [])
        for t in barlar:
            capa = t - 2 * H4 if hipotez == "H1" else None
            try:
                a = kr(t, capa)
            except Exception as hata:  # noqa: BLE001
                a = hata
            b = karar_cagrisi(pozisyon, hipotez, kimlik, t, rol="olay", capa=capa)
            if isinstance(a, BaseException) or isinstance(b, BaseException):
                assert type(a) is type(b) and str(a) == str(b)
            else:
                assert a == b


def test_kosul_kaynagi_capasiz_ve_capali_seriden_okur(dunya_d):
    kimlik, ozel = dunya_d
    kk, _ = _kaynaklar("H1", _y("H1"), kimlik)
    p = ozel["pump"][2]
    seri = pozisyon.kosul_serisi("H1", _y("H1"), kume="KESIF", **kimlik)
    for t in _izgara("H1", kimlik)[::50]:
        assert kk(t, None) is seri.deger(t)
    capali = pozisyon.kosul_serisi("H1", _y("H1"), kume="KESIF", **kimlik, capa=p)
    for d in range(1, 14):
        assert kk(p + d * H4, p) is (capali.deger(p + d * H4))
    with pytest.raises(TypeError):
        kk(pd.Timestamp("2021-03-01"), None)          # t veriden once dogrulanir (A4)


# --- Dizinin girdi denetimi -------------------------------------------------------------------------------------

@pytest.mark.parametrize("alan", ["sembol", "yapilandirma", "donem_no", "hipotez"])
def test_dizi_kaynak_kimligi_dizinin_argumanlariyla_ayni_olmali(dunya_d, alan):
    kimlik, _ = dunya_d
    kimlik2, _ = dunya(632, BAS, BITIS)
    h, y = "H2", _y("H2")
    kk, kr = _kaynaklar(h, y, kimlik)
    baska = {
        "sembol": _kaynaklar(h, y, kimlik2),
        "yapilandirma": _kaynaklar(h, _y("H2", 1), kimlik),
        "hipotez": _kaynaklar("H3", _y("H3"), kimlik),
    }
    if alan == "donem_no":
        SENTETIK_DONEMLER[(kimlik["sembol"], 1)] = SENTETIK_DONEMLER[(kimlik["sembol"], 0)]
        try:
            baska["donem_no"] = _kaynaklar(h, y, {"sembol": kimlik["sembol"], "donem_no": 1})
        finally:
            del SENTETIK_DONEMLER[(kimlik["sembol"], 1)]
    bk, br = baska[alan]
    with pytest.raises(ValueError, match="kimlig"):
        _dizi(h, y, kimlik, kosul=bk, karar=kr)
    with pytest.raises(ValueError, match="kimlig"):
        _dizi(h, y, kimlik, kosul=kk, karar=br)


def test_dizi_kosul_ve_karar_yer_degistiremez(dunya_d):
    kimlik, _ = dunya_d
    kk, kr = _kaynaklar("H2", _y("H2"), kimlik)
    with pytest.raises(TypeError):
        _dizi("H2", _y("H2"), kimlik, kosul=kr, karar=kr)
    with pytest.raises(TypeError):
        _dizi("H2", _y("H2"), kimlik, kosul=kk, karar=kk)


def test_A1_A2_pytest_disinda_kaynak_olmayan_kosul_ve_karar_TypeError(dunya_d, monkeypatch):
    """KESIF'te pytest disinda keyfi cagrilabilir `TypeError` alir; kosul ve karar ayri ayri denetlenir."""
    kimlik, _ = dunya_d
    h, y = "H2", _y("H2")
    kk, kr = _kaynaklar(h, y, kimlik)
    monkeypatch.setattr(dizi, "split_modulu", _SplitVekili(_pytest_testi=lambda: None))
    with pytest.raises(TypeError, match="kosul"):
        _dizi(h, y, kimlik, kosul=lambda t, capa: True, karar=kr)
    with pytest.raises(TypeError, match="karar"):
        _dizi(h, y, kimlik, kosul=kk, karar=_iki_argumanli_karar(h, y, kimlik))
    with pytest.raises(TypeError, match="karar"):
        _dizi(h, y, kimlik, kosul=kk, karar=pozisyon.olay_karari)
    # Gercek kaynaklarla dikis olmadan da kosar.
    assert isinstance(_dizi(h, y, kimlik, zamanlar=_izgara(h, kimlik)[:300]), dizi.DiziSonucu)


def test_A1_onay_kumesinde_acik_kosu_olsa_bile_keyfi_cagrilabilir_TypeError(tmp_path, monkeypatch):
    """Kararlar A1: 6.1'in (ii) dali yazilmadi. Acik onay kosusu icinde de, pytest disinda, kaynak olmayan kosul ya da
    karar `TypeError` alir. Sahte onay kosusu (gercek ONAY_KAYDI.md'ye yazilmaz)."""
    yol = tmp_path / "onay_gecici.md"
    yol.write_text("bas\n", encoding="utf-8")
    gecici_kayit(yol)
    kimlik, _ = dunya(633, "2025-03-01", "2026-01-31 20:00")
    h, y = "H2", _y("H2")
    with kosu(h, "C2"):
        bas, bitis, _ = pozisyon.donem_kaydi(kimlik["sembol"], 0)
        izgara = pozisyon.hipotez_izgarasi_barlari(h, kume="C2", **kimlik)
        kk = pozisyon.kosul_kaynagi(h, y, kume="C2", **kimlik)
        kr = pozisyon.karar_kaynagi(h, y, kume="C2", **kimlik)
        monkeypatch.setattr(dizi, "split_modulu", _SplitVekili(_pytest_testi=lambda: None))
        ortak = dict(birincil_ufuk=18, sembol=kimlik["sembol"], kume="C2", donem_no=0, donem_baslangic=bas,
                     donem_bitis=bitis)
        with pytest.raises(TypeError, match="kosul"):
            dizi.olay_dizisi(h, y, izgara, "4h", kosul=lambda t, capa: False, karar=kr, **ortak)
        with pytest.raises(TypeError, match="karar"):
            dizi.olay_dizisi(h, y, izgara, "4h", kosul=kk, karar=lambda t, capa: None, **ortak)
        sonuc = dizi.olay_dizisi(h, y, izgara[:200], "4h", kosul=kk, karar=kr, **ortak)
        assert isinstance(sonuc, dizi.DiziSonucu)


def test_pytest_icinde_kaynak_olmayan_kosul_kabul_edilir_dikis(dunya_d):
    """Pytest dikisi (kararlar B 2; `split._pytest_testi()`): dizi kurallarini lambda kosullarla sinayan testler."""
    kimlik, _ = dunya_d
    sonuc = _dizi("H2", _y("H2"), kimlik, kosul=lambda t, capa: False, karar=lambda t, capa: None)
    assert sonuc.olaylar == ()


# --- Dizi esitligi (sentetik) ------------------------------------------------------------------------------------

DIZI_DURUMLARI = [("H1", 0), ("H1", -1), ("H2", 0), ("H2", 1), ("H2", 2), ("H3", 0)]


@pytest.mark.parametrize("hipotez,i", DIZI_DURUMLARI)
def test_dizi_esitligi_kaynak_referans_ve_iki_argumanli_sarmalayici(dunya_d, hipotez, i):
    """Ayni dunyada dort cagri ayni olay zamanlarini, capalari ve retleri (zaman, capa, gerekce) verir:
      (a) kosul kaynagi + karar kaynagi (F2 yolu);
      (b) referansin kosulu (bu turdan onceki skaler kosulun dondurulmus kopyasi) + karar kaynagi;
      (c) kosul kaynagi + iki argumanli `olay_karari` sarmalayicisi (A2 karari (d));
      (d) referansin kosulu + iki argumanli sarmalayici (bu turdan onceki dizi davranisi).
    H2'de yapilandirmalar k'nin uc degerini kapsar (izgaranin ilk uc demeti)."""
    kimlik, _ = dunya_d
    y = _y(hipotez, i)
    if hipotez == "H2":
        y = next(dict(x) for x in sinyal.izgara("H2") if x["k"] == sorted({z["k"] for z in sinyal.izgara("H2")})[i])
    a = _ozet(_dizi(hipotez, y, kimlik))
    b = _ozet(_dizi(hipotez, y, kimlik, kosul=_ref_kosulu(hipotez, y, kimlik)))
    c = _ozet(_dizi(hipotez, y, kimlik, karar=_iki_argumanli_karar(hipotez, y, kimlik)))
    d = _ozet(_dizi(hipotez, y, kimlik, kosul=_ref_kosulu(hipotez, y, kimlik),
                    karar=_iki_argumanli_karar(hipotez, y, kimlik)))
    assert a == b == c == d
    gerekceler = {r[2] for r in a[1]}
    assert "sinyal_penceresi_tam_degil" in gerekceler, gerekceler


def test_dizi_esitligi_kurulumu_olay_ve_bekleme_gorulur(dunya_d):
    """Kurulum: dunyada H1 ve H2 dizileri gercek olay uretir ve bekleme retleri gorulur (esitlik bos degil)."""
    kimlik, _ = dunya_d
    for hipotez in ("H1", "H2"):
        sonuc = _dizi(hipotez, _y(hipotez), kimlik)
        assert sonuc.olaylar, hipotez
        assert any(r.gerekce == "bekleme_suresi" for r in sonuc.retler), hipotez


def test_dizi_esitligi_kume_siniri_G13():
    kimlik, _ = dunya(634, "2025-01-01", "2025-11-26 20:00")
    for hipotez in ("H1", "H2", "H3"):
        y = _y(hipotez)
        assert _ozet(_dizi(hipotez, y, kimlik)) == _ozet(_dizi(hipotez, y, kimlik,
                                                                 kosul=_ref_kosulu(hipotez, y, kimlik)))


# --- F2 gereksinimi 11: sureler izgara zamaniyla ------------------------------------------------------------------

def _dusurulmus(kimlik, dus):
    m, f = SENTETIK_VERI[kimlik["sembol"]]
    b, s, fy = SENTETIK_DONEMLER[(kimlik["sembol"], 0)]
    m = m.loc[~pd.DatetimeIndex(m["open_time"]).isin(pd.DatetimeIndex(dus))].reset_index(drop=True)
    return veri(m, f.copy(), b, s, ham=True, funding_yok=fy)


def _bosluksuz_olay(sonuc, izgara, *, sonra: int, adim=H4):
    """Ardindan `sonra` adim boyunca izgarada bosluk olmayan ilk olay."""
    kume = set(izgara)
    for o in sonuc.olaylar:
        if all(o.zaman + k * adim in kume for k in range(1, sonra + 1)):
            if o.capa is None or all(o.capa + k * adim in kume for k in range(0, sonra + 1)):
                return o
    pytest.fail("kurulum: bosluksuz olay bulunamadi")


def test_F2_11_a_bekleme_izgara_zamaniyla_olculur(dunya_d):
    """(a) Bekleme `(t0, t0 + h x 4h]` ZAMAN araligidir. Olaydan sonraki pencereye bosluk konunca bekleme retleri tam
    olarak o zaman araligindaki izgara barlaridir; listedeki h. eleman araligin disindadir ve bekleme reti tasimaz.
    Gercek kosul kaynagi; karar test onayi (olaylar kosulun belirledigi barlarda olusur)."""
    kimlik, _ = dunya_d
    h, y = "H1", _y("H1")
    izgara = _izgara(h, kimlik)
    once = _dizi(h, y, kimlik, karar=_test_karari(h, y, kimlik))
    e = _bosluksuz_olay(once, izgara, sonra=24).zaman
    yeni = _dusurulmus(kimlik, [e + k * H4 for k in (3, 4, 5)])
    izgara2 = _izgara(h, yeni)
    sonra = _dizi(h, y, yeni, karar=_test_karari(h, y, yeni))
    assert e in sonra.olay_zamanlari
    u = config.BIRINCIL_UFUK[config.BAR_4H]
    son = e + u * H4
    pencere_barlari = [t for t in izgara2 if e < t <= son]
    bekleme = [r.zaman for r in sonra.retler if r.gerekce == "bekleme_suresi" and e < r.zaman <= e + 40 * H4]
    assert bekleme == pencere_barlari
    # Kurulum: bosluk yuzunden araliktaki bar sayisi h'den az; listede h. eleman araligin disinda ve beklemede degil.
    sira = list(izgara2).index(e)
    assert len(pencere_barlari) == u - 3
    liste_h = izgara2[sira + u]
    assert liste_h > son and liste_h not in bekleme


def test_F2_11_b_H1_izleme_penceresi_izgara_zamaniyla_olculur(dunya_d):
    """(b) H1 izleme penceresi `(p, p + 12 x 4h]` ZAMAN araligidir. Pump barindan sonra bosluk konunca capa p ile sorulan
    barlar tam olarak o araliktaki izgara barlaridir; listedeki 12. eleman araligin disindadir ve p capasiyla
    sorulmaz. Gercek kosul kaynagi."""
    kimlik, _ = dunya_d
    h, y = "H1", _y("H1")
    izgara = _izgara(h, kimlik)
    once = _dizi(h, y, kimlik, karar=_test_karari(h, y, kimlik))
    p = _bosluksuz_olay(once, izgara, sonra=20).capa
    yeni = _dusurulmus(kimlik, [p + k * H4 for k in (1, 2, 3)])
    izgara2 = _izgara(h, yeni)
    sonra = _dizi(h, y, yeni, karar=_test_karari(h, y, yeni))
    son = p + config.H1_IZLEME_BAR * H4
    pencere_barlari = [t for t in izgara2 if p < t <= son]
    p_capali = sorted([r.zaman for r in sonra.retler if r.capa == p] + [o.zaman for o in sonra.olaylar if o.capa == p])
    # Bosluktan sonra tepe penceresi tam degil: pencerenin her bari "hesaplanamaz" (p capali ret), olay yok.
    assert p_capali == pencere_barlari and not [o for o in sonra.olaylar if o.capa == p]
    sira = list(izgara2).index(p)
    assert len(pencere_barlari) == config.H1_IZLEME_BAR - 3
    liste_12 = izgara2[sira + config.H1_IZLEME_BAR]
    assert liste_12 > son and liste_12 not in p_capali


def test_F2_11_c_H3_dizisi_bosluklu_gunde_kesilir():
    """(c) H3: izgarada olmayan gun diziyi keser (`ayni_an(t, onceki + 1 gun)`, takvim). Gercek kosul kaynagiyla:
    kosulun art arda saglandigi bir dizinin ortasindan bir gun dusurulunce o gun izgarada yoktur ve sonraki gunler
    'dizi_ilk_gun_degil' reti TASIMAZ (dizi oradan sonra kesintisiz suremez).

    SINIR (rapora yazildi): gercek kosulda bosluktan sonraki gunlerin pencereleri (SMA50, 30 gunluk medyan) bos gunu
    icerdigi icin kosul zaten hesaplanamaz (`None`) ve diziyi tamlik geregi de keser; takvim kuralinin TEK BASINA
    etkisi gercek kosulla gozlenemez. Takvim kuralinin kendisi lambda kosulla sinanir:
    `tests/test_rev13_h3_dizisi.py` (sizinti bulgusu S-B2)."""
    kimlik, _ = dunya(635, "2021-01-01", "2021-11-26 20:00")
    h, y = "H3", _y("H3")
    izgara = _izgara(h, kimlik)
    kk, _ = _kaynaklar(h, y, kimlik)
    degerler = [kk(t, None) for t in izgara]
    bas = next((i for i in range(len(izgara) - 3) if degerler[i] and degerler[i + 1] and degerler[i + 2]
                and izgara[i + 2] - izgara[i] == pd.Timedelta(days=2)), None)
    if bas is None:
        pytest.skip("kurulum: dunyada art arda uc gun saglanan H3 dizisi yok")
    gun = izgara[bas + 1]
    yeni = _dusurulmus(kimlik, [gun + k * H4 for k in range(6)])
    izgara2 = _izgara(h, yeni)
    assert gun not in set(izgara2)
    sonra = _dizi(h, y, yeni, karar=_test_karari(h, y, yeni))
    ilk_degil = [r.zaman for r in sonra.retler if r.gerekce == "dizi_ilk_gun_degil" and r.zaman > gun]
    kk2, _ = _kaynaklar(h, y, yeni)
    assert kk2(izgara[bas + 2], None) is None                  # tamlik da keser (yukaridaki sinir)
    assert not [t for t in ilk_degil if t <= gun + pd.Timedelta(days=50)]


def test_F2_11_d_ufuk_izgara_zamaniyla_olculur_aradaki_bosluk_cikisi_kaydirmaz():
    """(d) Ufuk (plan tarafi): pozisyon araligindaki bosluk cikis barini listedeki sirayla KAYDIRMAZ; cikis
    `giris + h x 4h` zamanindaki bardir. Mevcut testler: `tests/test_ileri_kayma_siniri.py` (hedef bar eksikse ileri
    kayma zamanla olculur), `tests/test_pencere.py::test_kesintiyi_asan_ufuk_ileri_kayar` (gercek veri, onbellek
    gerekir). Bu test aradaki bosluk durumunu sentetik olarak ekler."""
    zamanlar = pd.date_range("2021-01-01", periods=120, freq=H4, tz="UTC")
    giris = zamanlar[5]
    hedef = pencere.cikis_hedefi(giris, 18, config.BAR_4H) - H4
    eksik = zamanlar[(zamanlar <= giris + 2 * H4) | (zamanlar >= giris + 6 * H4)]
    sonuc = pencere.cikis_bari(eksik, giris, 18, config.BAR_4H, donem_bitis=eksik[-1], kume_bitis=None, birincil_ufuk=18)
    assert sonuc.zaman == hedef and sonuc.kaydi is False
    sira = list(eksik).index(giris)
    assert eksik[sira + 17] != hedef                           # listedeki sira baska bari verirdi


# --- Tarama: dizi ve kaynaklar ------------------------------------------------------------------------------------

def _cagrilanlar(yol, sinif: str | None, fonk: str) -> set[str]:
    agac = ast.parse(yol.read_text(encoding="utf-8"))
    kapsam = agac
    if sinif is not None:
        kapsam = next(d for d in ast.walk(agac) if isinstance(d, ast.ClassDef) and d.name == sinif)
    tanim = next(d for d in ast.walk(kapsam) if isinstance(d, ast.FunctionDef) and d.name == fonk)
    return {(d.func.attr if isinstance(d.func, ast.Attribute) else getattr(d.func, "id", None))
            for d in ast.walk(tanim) if isinstance(d, ast.Call)}


def test_tarama_karar_kaynagi_yalnizca_olay_karari_cagirir():
    """A2 karari (b): `KararKaynagi.__call__` kapinin ic adimlarini ya da ikinci bir karar yolunu cagirmaz."""
    yol = KOK / "data" / "pozisyon.py"
    cagrilan = _cagrilanlar(yol, "KararKaynagi", "__call__")
    yasak = {"_kapi_satirlari", "kapi_serisi", "_test_onayi", "_sonucu_ver", "_olay_kosulu", "_kosul_satirlari",
             "kosul_serisi", "sinyal_kosulu"}
    assert "olay_karari" in cagrilan and not cagrilan & yasak, cagrilan
    kosul = _cagrilanlar(yol, "KosulKaynagi", "__call__")
    assert not kosul & {"_kapi_satirlari", "kapi_serisi", "olay_karari", "_olay_kosulu", "_kosul_satirlari",
                        "_kosul_tek_bar", "sinyal_kosulu"}, kosul


def test_tarama_dizi_kosulu_ve_karari_yalnizca_argumandan_alir():
    """`dizi.py` kosulu ve karari yalnizca `kosul` ve `karar` argumanlarindan cagirir; kapinin ya da kosul serisinin
    adlarini cagirmaz (tasarim 5.3 madde 5)."""
    yol = KOK / "data" / "dizi.py"
    cagrilan = _cagrilanlar(yol, None, "olay_dizisi")
    assert {"kosul", "karar"} <= cagrilan
    assert not cagrilan & {"olay_karari", "kapi_serisi", "kosul_serisi", "sinyal_kosulu", "_kapi_satirlari",
                           "_kosul_satirlari", "_test_onayi"}, cagrilan
