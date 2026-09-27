"""Tur F saldirilari: sizinti testcisi gorevi (on-kayit rev.8, CLAUDE.md §3.6).

Hedefler (gorev tanimindan):
  1. Kismi gunler (`klines.gunluge_cevir`)
  2. T = K siniri (`pencere.cikis_bari`)
  3. Tam 1 dakika toleransi (`pencere.ayni_an` ve turevleri, funding pencere kenarlari,
     `funding.donemde_funding_var`, `funding.donem_sonrasi_kayitlari_at`)
  4. Baslangic boslugu (`funding.funding_tamlik_ayrintisi`, `pozisyon_funding_tam_mi`)
  5. Donem sonu istisnasi (`funding.pozisyon_fundingi` B/K siniri)
  6. Tek karar noktasinin atlanmasi (`data.pozisyon`)

Yalnizca `tests/` altina yazilir; aga cikmaz (tests/conftest.py `ag_kapali`).
Mevcut hicbir test dosyasina dokunulmadi.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
from data import funding as funding_modulu  # noqa: E402
from data import klines as klines_modulu  # noqa: E402
from data import pencere as pencere_modulu  # noqa: E402
from data import pozisyon as pozisyon_modulu  # noqa: E402
from data.donem import Donem  # noqa: E402
from sinyal_yardimcisi import sinyal
from kume_yardimcisi import kume_sinirlari
from uygunluk_yardimcisi import UYGUN_ONCELIK, uygunluk  # noqa: E402

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
TOL = pencere_modulu.ZAMAN_TOLERANSI  # 1 dakika
H4 = pd.Timedelta(hours=4)


def _cerceve(zamanlar) -> pd.DataFrame:
    """`klines.gunluge_cevir` girdisiyle uyumlu sentetik 4h cercevesi."""
    idx = pd.DatetimeIndex(zamanlar)
    n = len(idx)
    return pd.DataFrame(
        {
            "open_time": idx,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 10.0,
            "close_time": idx + H4 - pd.Timedelta(milliseconds=1),
            "quote_volume": 1_000_000.0,
            "count": 5,
            "taker_buy_volume": 5.0,
            "taker_buy_quote_volume": 500_000.0,
        }
    )


def _funding(kayitlar: list[tuple[pd.Timestamp, float, float]]) -> pd.DataFrame:
    """kayitlar: [(odeme_zamani, aralik_saat, oran), ...]."""
    z = [k[0] for k in kayitlar]
    a = [k[1] for k in kayitlar]
    o = [k[2] for k in kayitlar]
    return pd.DataFrame({
        "odeme_zamani": pd.DatetimeIndex(z),
        "aralik_saat": a,
        "oran": o,
        "oran_8h": o,
    })


# ==============================================================================
# 1. Kismi gunler (klines.gunluge_cevir) — on-kayit §2 rev.8 "1 gunluk barlar"
# ==============================================================================


def test_donem_basinda_kismi_gun_1d_seride_yer_almaz():
    """Donem 08:00'de basliyorsa ilk gunun yalnizca 4 bari donem icindedir; bu gun
    1d seride hic OLUSMAMALI (on-kayit §2 rev.8: kismi ilk gun seride yoktur)."""
    bas = T("2024-01-10 08:00")
    bitis = T("2024-01-15 20:00")  # son gun tam (00:00..20:00 hepsi donem ici)
    zamanlar = pd.date_range(bas, bitis, freq="4h", tz="UTC")
    cerceve = _cerceve(zamanlar)
    donem = Donem(bas, bitis, len(zamanlar), len(zamanlar))
    gunluk = klines_modulu.gunluge_cevir(cerceve, donemler=[donem])
    gunler = set(pd.DatetimeIndex(gunluk["open_time"]).normalize())
    assert T("2024-01-10 00:00") not in gunler  # kismi ilk gun DISARIDA
    assert T("2024-01-11 00:00") in gunler  # ilk tam gun ICERIDE


def test_donem_sonunda_kismi_gun_1d_seride_yer_almaz():
    """Donem gun ortasinda bitiyorsa (12:00) o gunun yalnizca 4 bari donem icindedir;
    bu gun 1d seride OLUSMAMALI (on-kayit §2 rev.8)."""
    bas = T("2024-01-10 00:00")
    bitis = T("2024-01-15 12:00")  # son gun kismi (00:00, 04:00, 08:00, 12:00 -> 4 bar)
    zamanlar = pd.date_range(bas, bitis, freq="4h", tz="UTC")
    cerceve = _cerceve(zamanlar)
    donem = Donem(bas, bitis, len(zamanlar), len(zamanlar))
    gunluk = klines_modulu.gunluge_cevir(cerceve, donemler=[donem])
    gunler = set(pd.DatetimeIndex(gunluk["open_time"]).normalize())
    assert T("2024-01-15 00:00") not in gunler  # kismi son gun DISARIDA
    assert T("2024-01-14 00:00") in gunler  # onceki tam gun ICERIDE


def test_hizasiz_ekstra_bar_komsu_tam_gunleri_bozmaz():
    """02:00 acilisli hizasiz bir bar (gercekte olmamasi gereken veri) diger tam
    gunleri BOZMAMALI: hizali maskesi bu bari groupby'dan once eler."""
    bas = T("2024-02-01 00:00")
    bitis = T("2024-02-05 20:00")
    zamanlar = pd.date_range(bas, bitis, freq="4h", tz="UTC")
    cerceve = _cerceve(zamanlar)
    ekstra = _cerceve([T("2024-02-03 02:00")])  # hizasiz fazladan bar
    cerceve = pd.concat([cerceve, ekstra], ignore_index=True).sort_values("open_time", ignore_index=True)
    donem = Donem(bas, bitis, len(zamanlar) + 1, len(zamanlar) + 1)
    gunluk = klines_modulu.gunluge_cevir(cerceve, donemler=[donem])
    gunler = set(pd.DatetimeIndex(gunluk["open_time"]).normalize())
    # 02-03 gunu hala 6 hizali bara sahip (02:00 hizasiz bar bir slotun YERINE
    # gecmedi, fazladan geldi); dolayisiyla tam sayilmali.
    assert T("2024-02-03 00:00") in gunler


def test_hizasiz_bar_gerekli_slotun_yerine_gecerse_gun_eksik_sayilir():
    """04:00 bari SILINIP yerine 02:00'de hizasiz bir bar konursa, o gun artik
    yalnizca 5 hizali bara sahiptir ve NaN (eksik) sayilmalidir."""
    bas = T("2024-02-01 00:00")
    bitis = T("2024-02-05 20:00")
    zamanlar = list(pd.date_range(bas, bitis, freq="4h", tz="UTC"))
    zamanlar.remove(T("2024-02-03 04:00"))
    zamanlar.append(T("2024-02-03 02:00"))  # hizasiz yerine koyma
    cerceve = _cerceve(sorted(zamanlar))
    donem = Donem(bas, bitis, len(zamanlar), len(zamanlar))
    gunluk = klines_modulu.gunluge_cevir(cerceve, donemler=[donem])
    gunler = set(pd.DatetimeIndex(gunluk["open_time"]).normalize())
    assert T("2024-02-03 00:00") not in gunler  # eksik sayilmali


def test_ayni_gunde_iki_donem_birlesip_sahte_tam_gun_olusturmaz():
    """Ayni takvim gunu iki farkli donemin barlarini icerirse (donem0: 00-08,
    donem1: 12-20) bu gun HICBIR donemde 6 bar bulamamali; iki ayri donemin
    barlari birlesip sahte bir tam gun olusturmamali (on-kayit §2 rev.7 'Yeniden
    adlandirma zincirindeki her sembol ayri bir donemdir' ilkesinin genellemesi:
    donem sinirlari donem donem uygulanir)."""
    donem0 = Donem(T("2024-03-01 00:00"), T("2024-03-01 08:00"), 3, 3)
    donem1 = Donem(T("2024-03-01 12:00"), T("2024-03-05 00:00"), 25, 25)
    zamanlar = pd.date_range(T("2024-03-01 00:00"), T("2024-03-05 00:00"), freq="4h", tz="UTC")
    cerceve = _cerceve(zamanlar)
    gunluk = klines_modulu.gunluge_cevir(cerceve, donemler=[donem0, donem1])
    gunler = set(pd.DatetimeIndex(gunluk["open_time"]).normalize())
    assert T("2024-03-01 00:00") not in gunler  # ikiye bolunmus gun DISARIDA
    assert T("2024-03-02 00:00") in gunler  # donem1'in tam gunu ICERIDE


def test_h3_olayinin_giris_gunu_kismi_son_gun_olsa_da_giris_4h_bardan_yapilir():
    """On-kayit §4 rev.8 gerekce: '4h fiyat okuma tabani t+1 gunu kismi son gun
    olan H3 olaylarinin kaybini onler'. Sinyal gunu (t) tam olsa da, giris gunu
    (t+1) donemin kismi son gunu olabilir; giris yine de basarili olmali ve
    donem sonu (B, K) uygulanmalidir."""
    donem_bas = T("2024-04-01 00:00")
    donem_bitis = T("2024-04-22 12:00")  # t+1 gununun yalnizca ilk 4 bari donem ici
    zamanlar = pd.date_range(donem_bas, donem_bitis, freq="4h", tz="UTC")
    sinyal = T("2024-04-20 00:00")  # tam bir 1d gun (t)
    plan = pencere_modulu.pozisyon_plani(
        zamanlar, sinyal, 14, config.BAR_1D,
        birincil_ufuk=14, kume_baslangic=None, kume_bitis=None,
        donem_baslangic=donem_bas, donem_bitis=donem_bitis,
    )
    assert plan.giris == T("2024-04-21 00:00")  # t+1 gununun ilk 4h bari
    assert plan.donem_sonu_mu is True
    assert plan.cikis_ani == pencere_modulu.donem_kapanisi(donem_bitis)


# ==============================================================================
# 2. T = K siniri (pencere.cikis_bari) — on-kayit §4 rev.8 "Donem sonu ve cikis"
# ==============================================================================


def test_hedef_tam_k_ise_olagan_cikis_donem_sonu_degil():
    """Rev.9 §4 "Donem sonu ve cikis": T >= K, esitlik dahil; T = K TAM esitlikte donem
    sonu cikisidir (rev.8'de "once T > K denetlenir" geregi olagan idi)."""
    g = T("2024-05-10 00:00")
    b = g  # B = giris -> K = B + 4h = giris + 4h = T (ufuk=1)
    zamanlar = pd.DatetimeIndex([g])
    sonuc = pencere_modulu.cikis_bari(zamanlar, g, 1, config.BAR_4H, birincil_ufuk=18,
                                       donem_bitis=b, kume_bitis=None)
    assert sonuc.tur == "donem_sonu"
    assert sonuc.cikis_ani == pencere_modulu.donem_kapanisi(b)


def test_hedef_k_eksi_1ns_olagan_cikis():
    """T = K - 1ns: fark 1 dakikadan kesin kucuk, T ile K AYNI AN (§4 "Zaman toleransi").
    Rev.9: "T < K" yalnizca T, K'dan once (ayni an degil) ise; ayni an T >= K'dir -> donem
    sonu (rev.8'de olagan idi).

    T - K = g - b (ufuk=1, bar=4h); T=K-1ns istiyorsak b = g + 1ns olmali."""
    g = T("2024-05-10 00:00")
    b = g + pd.Timedelta(nanoseconds=1)
    zamanlar = pd.DatetimeIndex([g])
    sonuc = pencere_modulu.cikis_bari(zamanlar, g, 1, config.BAR_4H, birincil_ufuk=18,
                                       donem_bitis=b, kume_bitis=None)
    assert sonuc.tur == "donem_sonu"


def test_hedef_k_arti_1ns_tolerans_icinde_hala_olagan():
    """T = K + 1ns: fark toleranstan (1 dk) kucuk oldugu icin AYNI AN sayilir (on-kayit §4
    rev.8 'Zaman toleransi'). Rev.9: T >= K esitligi dahil eder -> donem sonu (rev.8'de
    "tolerans icinde, donem sonu DEGIL" idi). T-K = g-b; T=K+1ns -> b = g-1ns."""
    g = T("2024-05-10 00:00")
    b = g - pd.Timedelta(nanoseconds=1)
    zamanlar = pd.DatetimeIndex([g])
    sonuc = pencere_modulu.cikis_bari(zamanlar, g, 1, config.BAR_4H, birincil_ufuk=18,
                                       donem_bitis=b, kume_bitis=None)
    assert sonuc.tur == "donem_sonu"


def test_hedef_k_arti_1dk_donem_sonu_tetiklenir():
    """T = K + 1 dakika: fark tam tolerans esigine ULASIR (>= 1 dk), artik ayni an
    degildir; donem sonu tetiklenmeli (on-kayit §4 rev.8). T-K = g-b; T=K+1dk -> b = g-1dk."""
    g = T("2024-05-10 00:00")  # giris bari, T = g + 4h
    b = g - pd.Timedelta(minutes=1)  # K = b + 4h = g - 1dk + 4h -> T - K = 1 dk
    zamanlar = pd.DatetimeIndex([b, g])  # B bari da seride bulunmali
    sonuc = pencere_modulu.cikis_bari(zamanlar, g, 1, config.BAR_4H, birincil_ufuk=18,
                                       donem_bitis=b, kume_bitis=None)
    assert sonuc.tur == "donem_sonu"
    assert sonuc.cikis_ani == pencere_modulu.donem_kapanisi(b)
    assert sonuc.cikis_ani != T("2024-05-10 04:00")  # T degil, K'da cikilmali


def test_hedef_k_arti_1dk_eksi_1ns_hala_olagan():
    """T = K + 1 dk - 1ns: tam sinirin hemen altinda; hala AYNI AN. Rev.9: T >= K (esitlik
    dahil) -> donem sonu (rev.8'de "donem sonu OLMAMALI" idi). T-K = g-b;
    T=K+1dk-1ns -> b = g-1dk+1ns."""
    g = T("2024-05-10 00:00")
    b = g - pd.Timedelta(minutes=1) + pd.Timedelta(nanoseconds=1)
    zamanlar = pd.DatetimeIndex([g])
    sonuc = pencere_modulu.cikis_bari(zamanlar, g, 1, config.BAR_4H, birincil_ufuk=18,
                                       donem_bitis=b, kume_bitis=None)
    assert sonuc.tur == "donem_sonu"


# ==============================================================================
# 3. Tam 1 dakika toleransi — on-kayit §4 rev.8 "Zaman toleransi"
# ==============================================================================


@pytest.mark.parametrize("fark,beklenen", [
    (pd.Timedelta(minutes=1), False),  # tam 1 dk: AYNI AN DEGIL
    (pd.Timedelta(minutes=1) - pd.Timedelta(nanoseconds=1), True),  # hemen alti: ayni
    (pd.Timedelta(0), True),
])
def test_ayni_an_tam_1_dakika_siniri(fark, beklenen):
    """`pencere.ayni_an`: tam 1 dakikalik fark ayni an SAYILMAMALI (on-kayit §4 rev.8)."""
    a = T("2024-06-01 00:00")
    b = a + fark
    assert pencere_modulu.ayni_an(a, b) is beklenen
    assert pencere_modulu.ayni_an(b, a) is beklenen  # simetrik


def test_funding_giris_anindaki_odeme_haric_tutulur():
    """Giris anindaki funding odemesi pozisyona GIRMEMELI (on-kayit §4: 'giris
    anindaki odeme haric')."""
    donem_bas = T("2024-07-01 00:00")
    b = donem_bas + 40 * H4
    zamanlar = pd.date_range(donem_bas, b, freq="4h", tz="UTC")
    sinyal = b - 3 * H4
    plan = pencere_modulu.pozisyon_plani(
        zamanlar, sinyal, 1000, config.BAR_4H, birincil_ufuk=18,
        kume_baslangic=None, kume_bitis=None, donem_baslangic=donem_bas, donem_bitis=b,
    )
    assert plan.donem_sonu_mu is True
    giris = plan.giris
    # Tamlik icin devam eden bir zincir kur (B'ye kadar) ki tam=True olsun; ilk
    # kayit TAM giris aninda buyuk (5.0) bir sahte oran tasisin -- toplama
    # girerse test yakalar.
    kayitlar = [(giris, 4, 5.0)]
    z = giris + H4
    while z <= b:
        kayitlar.append((z, 4, 0.0001))
        z += H4
    fund3 = _funding(kayitlar)
    assert funding_modulu.pozisyon_funding_tam_mi(fund3, plan) is True
    toplam = funding_modulu.pozisyon_fundingi(fund3, plan)
    assert toplam == pytest.approx(0.0001 * (len(kayitlar) - 1))  # giris anindaki 5.0 DAHIL DEGIL


def test_funding_cikis_anindaki_odeme_dahil_edilir():
    """Cikis anindaki (T) funding odemesi pozisyona GIRMELI (on-kayit §4: 'cikis
    anindaki dahil'). Donem sonu OLMAYAN olagan cikis kullanilir."""
    donem_bas = T("2024-08-01 00:00")
    donem_bitis = donem_bas + 200 * H4
    zamanlar = pd.date_range(donem_bas, donem_bitis, freq="4h", tz="UTC")
    sinyal = donem_bas + 10 * H4
    plan = pencere_modulu.pozisyon_plani(
        zamanlar, sinyal, 3, config.BAR_4H, birincil_ufuk=18,
        kume_baslangic=None, kume_bitis=None, donem_baslangic=donem_bas, donem_bitis=donem_bitis,
    )
    assert plan.donem_sonu_mu is False
    giris = plan.giris
    cikis_ani = plan.cikis_ani
    # Rev.9 §4 "Funding tamligi": capa (giris aninda ya da oncesinde kayit) zorunlu; giris
    # anindaki capa pozisyona girmez (buyuk sahte oran).
    kayitlar = [(giris, 4, 5.0)]
    z = giris + H4
    while z <= cikis_ani:
        kayitlar.append((z, 4, 0.001))
        z += H4
    fund = _funding(kayitlar)
    assert funding_modulu.pozisyon_funding_tam_mi(fund, plan) is True
    toplam = funding_modulu.pozisyon_fundingi(fund, plan)
    assert toplam == pytest.approx(0.001 * (len(kayitlar) - 1))
    # cikis anindaki son kaydin (z == cikis_ani) toplama girdigini dogrula.
    assert kayitlar[-1][0] == cikis_ani


@pytest.mark.parametrize("fark,beklenen", [
    (pd.Timedelta(0), True),
    (pd.Timedelta(minutes=1) - pd.Timedelta(nanoseconds=1), True),
    (pd.Timedelta(minutes=1), False),
])
def test_donemde_funding_var_b_siniri_tam_1_dakika(fark, beklenen):
    """`funding.donemde_funding_var`: pencere [donem basi, B] dahildir; B'den 1 dk
    ya da daha fazla sonraki kayit sayilmamali (on-kayit §2 rev.8)."""
    donem = Donem(T("2024-09-01 00:00"), T("2024-09-05 00:00"), 25, 25)
    fund = _funding([(donem.bitis + fark, 4, 0.0)])
    assert funding_modulu.donemde_funding_var(fund, donem, config.BAR_4H) is beklenen


@pytest.mark.parametrize("fark,beklenen", [
    (pd.Timedelta(0), True),  # tam K -> KALIR
    (pd.Timedelta(minutes=1) - pd.Timedelta(nanoseconds=1), True),  # K'nin az ustu -> hala ayni an, KALIR
    (pd.Timedelta(minutes=1), False),  # tam 1 dk sonra -> ATILIR
])
def test_donem_sonrasi_kayitlari_at_kapanis_k_siniri_tam_1_dakika(fark, beklenen):
    """`funding.donem_sonrasi_kayitlari_at`: donem kapanisindan (K) SONRA gelen
    kayitlar atilir; sinir tam 1 dakikadir (on-kayit §4 rev.8 'Zaman toleransi')."""
    donem = Donem(T("2024-10-01 00:00"), T("2024-10-05 00:00"), 25, 25)
    k = pencere_modulu.donem_kapanisi(donem.bitis)
    fund = _funding([(k + fark, 4, 0.0)])
    kalan = funding_modulu.donem_sonrasi_kayitlari_at(fund, [donem], config.BAR_4H)
    assert (len(kalan) == 1) is beklenen


# ==============================================================================
# 4. Baslangic boslugu — funding_tamlik_ayrintisi / pozisyon_funding_tam_mi
# ==============================================================================


@pytest.mark.parametrize("aralik_once,aralik_sonra", [(8, 2), (2, 8), (8, 1), (1, 8)])
def test_aralik_gecisi_buyuk_araliga_gore_bosluk_denetlenir(aralik_once, aralik_sonra):
    """Aralik gecisinde (8h<->2h, 8h<->1h) bosluk, iki kaydin araliklarindan
    BUYUGUNE gore denetlenir (on-kayit §4 rev.9 "Funding tamligi", Zincir maddesi; rev.8'de
    'Funding araligi gecisleri'). Rev.9: capa zorunlu (giris aninda kayit eklendi) ve kosul
    adi `zincir_tam` (rev.8'de `ic_tam`)."""
    giris = T("2024-11-01 00:00")
    bas = [giris - pd.Timedelta(days=1)]
    ilk = giris + pd.Timedelta(hours=aralik_once)
    buyuk = max(aralik_once, aralik_sonra)
    # Ic gecis TAM buyugun sinirindaymis gibi (ayni an, tam degil): ikinci kayit
    # ilk + buyuk saat sonra -> zincir_tam TRUE (sinir dahil degil, "sonra" degil).
    ikinci_tam = ilk + pd.Timedelta(hours=buyuk)
    pencere_sonu = ikinci_tam + pd.Timedelta(hours=aralik_sonra)  # son_tam icin
    fund_tam = _funding([
        (giris, aralik_once, 0.0),
        (ilk, aralik_once, 0.0),
        (ikinci_tam, aralik_sonra, 0.0),
    ])
    ayrinti = funding_modulu.funding_tamlik_ayrintisi(fund_tam, [giris], [pencere_sonu], donem_baslari=bas)
    assert bool(ayrinti["zincir_tam"].iloc[0]) is True

    # Bosluk buyugu 1 saniye ASARSA (once() esigi tam 1 dk oldugu icin +1 dk ekle)
    ikinci_bozuk = ilk + pd.Timedelta(hours=buyuk) + pd.Timedelta(minutes=1)
    fund_bozuk = _funding([
        (giris, aralik_once, 0.0),
        (ilk, aralik_once, 0.0),
        (ikinci_bozuk, aralik_sonra, 0.0),
    ])
    ayrinti2 = funding_modulu.funding_tamlik_ayrintisi(
        fund_bozuk, [giris], [ikinci_bozuk + pd.Timedelta(hours=aralik_sonra)], donem_baslari=bas)
    assert bool(ayrinti2["zincir_tam"].iloc[0]) is False


def test_ilk_kayit_tam_giris_aninda_ise_pencerede_kayit_yok_sayilir():
    """Tek funding kaydi TAM giris aninda ise (giris haric kuralindan dolayi)
    pencerede HICBIR odeme yoktur. Rev.9 §4 "Funding tamligi": o kayit capadir; "hic kayit
    yok" cumlesi kaldirildi ve son kayit + aralik tam pencere sonuna denk geldigi icin ("tam
    pencere sonuna denk gelmesi yeterlidir") pozisyon TAM ve esitlik affi isaretli (rev.8'de
    `kayit_var` False, tamlik False idi)."""
    giris = T("2024-11-05 00:00")
    fund = _funding([(giris, 4, 0.0)])
    ayrinti = funding_modulu.funding_tamlik_ayrintisi(fund, [giris], [giris + H4], donem_baslari=[giris])
    assert bool(ayrinti["capa_var"].iloc[0]) is True
    assert bool(ayrinti["tam"].iloc[0]) is True
    assert bool(ayrinti["son_esitlik_affi"].iloc[0]) is True


@pytest.mark.parametrize("delta,beklenen_tam", [
    (pd.Timedelta(0), True),  # ilk odeme tam giris+aralikta -> "sonra" degil, TAM
    (pd.Timedelta(minutes=1) - pd.Timedelta(nanoseconds=1), True),  # tam sinirin altinda -> hala TAM
    (pd.Timedelta(minutes=1), False),  # tam 1dk gec -> kesinlikle sonra, eksik
])
def test_baslangic_tam_giris_arti_aralik_siniri(delta, beklenen_tam):
    """Rev.9 §4 "Funding tamligi", Ilk cift maddesi (rev.8'in `baslangic_tam` kosulunun
    yerine): capadan sonraki ilk odeme giris + iki araligin buyugunden SONRA olamaz; sinir tam
    1 dakikadir (§4 'Zaman toleransi'). Capa girisin bir aralik oncesinde."""
    giris = T("2024-11-06 00:00")
    aralik = 4
    ilk_odeme = giris + pd.Timedelta(hours=aralik) + delta
    pencere_sonu = ilk_odeme + pd.Timedelta(hours=aralik)
    fund = _funding([(giris - pd.Timedelta(hours=aralik), aralik, 0.0), (ilk_odeme, aralik, 0.0)])
    ayrinti = funding_modulu.funding_tamlik_ayrintisi(fund, [giris], [pencere_sonu],
                                                      donem_baslari=[giris - pd.Timedelta(days=1)])
    assert bool(ayrinti["zincir_tam"].iloc[0]) is beklenen_tam


def test_baslangic_tam_giris_arti_aralik_eksi_1ns_tamdir():
    """Ilk odeme giris+aralik'tan 1ns ONCE gelirse (tolerans disi degil) hala
    tam sayilmali; yalniz SINIRIN USTU (>=1dk) eksik sayilmali."""
    giris = T("2024-11-07 00:00")
    aralik = 4
    ilk_odeme = giris + pd.Timedelta(hours=aralik) - pd.Timedelta(nanoseconds=1)
    # Rev.9: capa girisin bir aralik oncesinde; kosul `zincir_tam` (Ilk cift, taban giris).
    fund = _funding([(giris - pd.Timedelta(hours=aralik), aralik, 0.0), (ilk_odeme, aralik, 0.0)])
    pencere_sonu = ilk_odeme + pd.Timedelta(hours=aralik)
    ayrinti = funding_modulu.funding_tamlik_ayrintisi(fund, [giris], [pencere_sonu],
                                                      donem_baslari=[giris - pd.Timedelta(days=1)])
    assert bool(ayrinti["zincir_tam"].iloc[0]) is True


def test_funding_tamlik_ayrintisi_vektorel_ve_tekil_yol_ayni_sonucu_verir():
    """Coklu pozisyonu tek cagrida (vektorel) hesaplamak, her birini AYRI AYRI
    (n=1) hesaplamakla AYNI sonucu vermeli. Farkliysa vektorlestirme sirasinda
    pozisyonlar arasi veri sizmasi (bir pozisyonun penceresi digerinin kaydini
    kullanmasi) vardir."""
    giris1 = T("2024-12-01 00:00")
    giris2 = T("2024-12-10 00:00")
    fund = _funding([
        (giris1, 4, 0.001),  # Rev.9: capa
        (giris1 + H4, 4, 0.001),
        (giris1 + 2 * H4, 4, 0.001),
        (giris2, 4, 0.002),  # Rev.9: capa
        (giris2 + H4, 4, 0.002),
        (giris2 + 2 * H4, 4, 0.002),
        (giris2 + 3 * H4, 4, 0.002),
    ])
    girisler = [giris1, giris2]
    sonlar = [giris1 + 2 * H4, giris2 + 3 * H4]
    baslar = [giris1 - pd.Timedelta(days=30)] * 2
    vektorel = funding_modulu.funding_tamlik_ayrintisi(fund, girisler, sonlar, donem_baslari=baslar)
    for i in range(2):
        tekil = funding_modulu.funding_tamlik_ayrintisi(fund, [girisler[i]], [sonlar[i]], donem_baslari=[baslar[i]])
        for kosul in (*funding_modulu.TAMLIK_KOSULLARI, "tam"):
            assert bool(vektorel[kosul].iloc[i]) == bool(tekil[kosul].iloc[0]), (
                f"kosul={kosul} pozisyon={i}: vektorel={vektorel[kosul].iloc[i]} "
                f"tekil={tekil[kosul].iloc[0]}"
            )


def test_kayitsiz_funding_cercevesinde_cokme_olmaz():
    """Bos funding cercevesi ya da hic kayit dusmeyen pencere COKMEMELI; tamlik
    False, funding NaN donmeli."""
    bos = pd.DataFrame(columns=["odeme_zamani", "aralik_saat", "oran", "oran_8h"])
    giris = T("2025-01-01 00:00")
    ayrinti = funding_modulu.funding_tamlik_ayrintisi(bos, [giris], [giris + H4], donem_baslari=[giris])
    assert bool(ayrinti["tam"].iloc[0]) is False
    assert len(ayrinti) == 1

    uzak = _funding([(T("2020-01-01 00:00"), 4, 0.0)])  # pencereden cok uzak tek kayit
    # Rev.9: donem basindan onceki kayit capa olamaz (rev.8'de `kayit_var` False).
    ayrinti2 = funding_modulu.funding_tamlik_ayrintisi(uzak, [giris], [giris + H4], donem_baslari=[giris])
    assert bool(ayrinti2["capa_var"].iloc[0]) is False
    assert bool(ayrinti2["tam"].iloc[0]) is False


# ==============================================================================
# 5. Donem sonu istisnasi — on-kayit §4 rev.8
# ==============================================================================


def _donem_sonu_plani(donem_bas, b, sinyal_ofset_bar=3, ufuk=1000):
    zamanlar = pd.date_range(donem_bas, b, freq="4h", tz="UTC")
    sinyal = b - sinyal_ofset_bar * H4
    return pencere_modulu.pozisyon_plani(
        zamanlar, sinyal, ufuk, config.BAR_4H, birincil_ufuk=18,
        kume_baslangic=None, kume_bitis=None, donem_baslangic=donem_bas, donem_bitis=b,
    )


def test_donem_sonu_pencere_b_dahil_b_ile_k_arasi_ve_k_haric():
    """Donem sonu cikisinda funding penceresi B'de (dahil) kapanmali. B ile K
    arasindaki (ornek B+2h) ve K'daki odeme HESABA GIRMEMELI (on-kayit §4 rev.8
    'Donem sonu istisnasi')."""
    donem_bas = T("2025-02-01 00:00")
    b = donem_bas + 30 * H4
    plan = _donem_sonu_plani(donem_bas, b)
    assert plan.donem_sonu_mu is True
    k = plan.cikis_ani
    assert k == b + H4

    giris = plan.giris
    kayitlar = [(giris, 4, 0.001)]  # Rev.9: capa (giris aninda; toplama girmez)
    z = giris + H4
    while z <= b:
        kayitlar.append((z, 4, 0.001))
        z += H4
    kayitlar.append((b + 2 * pd.Timedelta(hours=1), 4, 999.0))  # B ile K arasi -- DAHIL EDILMEMELI
    kayitlar.append((k, 4, 999.0))  # K'da -- DAHIL EDILMEMELI
    fund = _funding(kayitlar)
    assert funding_modulu.pozisyon_funding_tam_mi(fund, plan) is True
    toplam = funding_modulu.pozisyon_fundingi(fund, plan)
    beklenen = 0.001 * sum(1 for z, *_ in kayitlar if giris < z <= b)
    assert toplam == pytest.approx(beklenen)
    assert toplam < 500  # 999'lar HESABA GIRMEDI


def test_donem_sonu_son_odeme_b_ye_gore_aranir_k_ye_gore_degil():
    """`funding_penceresi_sonu` donem sonu pozisyonda B doner, K DEGIL; bu yuzden
    B'den sonraki (K dahil) hicbir kaydin tamlik kontrolune girmemesi gerekir."""
    donem_bas = T("2025-03-01 00:00")
    b = donem_bas + 20 * H4
    plan = _donem_sonu_plani(donem_bas, b)
    assert funding_modulu.funding_penceresi_sonu(plan) == b  # K DEGIL


def test_giris_tam_b_de_olan_donem_sonu_pozisyonunun_funding_penceresi_bostur():
    """Giris ani TAM B'ye denk gelirse (son bar hem giris hem donem bitisi),
    funding penceresi (giris haric, B dahil) BOS kumedir: giris==B oldugu icin
    (B, B] araligi bostur. Hicbir funding kaydi bu pozisyona giremez.

    Rev.9 §4 "Funding tamligi": "penceresinde hic kayit yok" kurali kaldirildi. Giris anindaki
    kayit (b) capadir; capa + 4 saat pencere sonundan (B) once dolmuyor, eksik odeme yok:
    pozisyon TAM ve funding'i 0 (rev.8'de her zaman False idi). Capa yoksa tam degil."""
    donem_bas = T("2025-04-01 00:00")
    b = donem_bas + 10 * H4
    # sinyal = b - 4h -> giris = sinyal + 4h = b (TAM B'de giris)
    plan = _donem_sonu_plani(donem_bas, b, sinyal_ofset_bar=1)
    assert plan.giris == b
    assert plan.donem_sonu_mu is True
    # Cok yogun bir funding serisi versek bile (giris=B oldugu icin) tam olamaz.
    kayitlar = [(b - pd.Timedelta(minutes=30), 4, 0.001), (b, 4, 0.001), (b + H4, 4, 0.001)]
    fund = _funding(kayitlar)
    assert funding_modulu.pozisyon_funding_tam_mi(fund, plan) is True
    assert funding_modulu.pozisyon_fundingi(fund, plan) == 0.0
    assert funding_modulu.pozisyon_funding_tam_mi(_funding([(b + H4, 4, 0.001)]), plan) is False


def test_donem_sonu_istisnasi_1d_izgarada_da_aynidir():
    """Sinyal 1d izgarasinda tespit edilse bile funding penceresi yine B'de
    (dahil) kapanmali; ızgara turu funding sinirini degistirmemeli (on-kayit §4
    rev.8: 'Izgaradan bagimsiz olarak 4h barlardan hesaplanir')."""
    donem_bas = T("2025-05-01 00:00")
    b = donem_bas + 60 * H4  # 10 gun
    zamanlar = pd.date_range(donem_bas, b, freq="4h", tz="UTC")
    sinyal = donem_bas + 4 * pd.Timedelta(days=1)  # tam bir gun acilisi (1d hizali)
    plan = pencere_modulu.pozisyon_plani(
        zamanlar, sinyal, 14, config.BAR_1D, birincil_ufuk=14,
        kume_baslangic=None, kume_bitis=None, donem_baslangic=donem_bas, donem_bitis=b,
    )
    assert plan.donem_sonu_mu is True
    assert funding_modulu.funding_penceresi_sonu(plan) == b

    giris = plan.giris
    kayitlar = [(giris, 4, 0.001)]  # Rev.9: capa
    z = giris + H4
    while z <= b:
        kayitlar.append((z, 4, 0.001))
        z += H4
    kayitlar.append((b + H4, 4, 777.0))  # K -- DAHIL EDILMEMELI
    fund = _funding(kayitlar)
    assert funding_modulu.pozisyon_funding_tam_mi(fund, plan) is True
    toplam = funding_modulu.pozisyon_fundingi(fund, plan)
    assert toplam < 100  # 777 disarida kaldi


# ==============================================================================
# 6. Tek karar noktasinin atlanmasi — on-kayit §4 rev.8, data/pozisyon.py
# ==============================================================================


def _basit_plan():
    seri_bas = T("2025-06-01 00:00")
    # Rev.9 §4: uygunluk tek karar noktasinda; donem seriden UYGUN_ONCELIK once baslar
    # (listeleme yasi >= 30 gun). Bar serisi degismedi.
    donem_bas = seri_bas - UYGUN_ONCELIK
    donem_bitis = seri_bas + 200 * H4
    zamanlar = pd.date_range(seri_bas, donem_bitis, freq="4h", tz="UTC")
    sinyal = seri_bas + 10 * H4
    # Rev.10 (on-kayit §4 "Ufuk degerlerinin baglanmasi"): plan kapiya (olay_karari) verildigi icin ufuk
    # on-kayit degeri (onceki 3 bar yerine en kisa 4h ufku, 6 bar).
    return pencere_modulu.pozisyon_plani(
        zamanlar, sinyal, 6, config.BAR_4H, birincil_ufuk=18,
        kume_baslangic=None, kume_bitis=None, donem_baslangic=donem_bas, donem_bitis=donem_bitis,
    ), zamanlar, donem_bas, donem_bitis


def _tam_funding_icin(plan):
    giris = plan.giris
    kayitlar = [(giris, 4, 0.0001)]  # Rev.9 §4 "Funding tamligi": capa
    z = giris + H4
    while z <= funding_modulu.funding_penceresi_sonu(plan):
        kayitlar.append((z, 4, 0.0001))
        z += H4
    return _funding(kayitlar)


def test_pozisyon_fiyatlari_elle_kurulmus_onaylanmis_pozisyonu_reddeder():
    """`pozisyon.pozisyon_fiyatlari` elle kurulmus bir OnaylanmisPozisyon'u
    (`_imza` sahte) KABUL ETMEMELI; aksi halde tek karar noktasi atlanabilir."""
    plan, zamanlar, _, _ = _basit_plan()
    sahte = pozisyon_modulu.OnaylanmisPozisyon(plan, 0.01, 100.0, 0.0)  # p0=0.01 -> devasa sahte kar
    with pytest.raises(ValueError):
        pozisyon_modulu.pozisyon_fiyatlari(sahte)


def test_mae_dataclasses_replace_ile_degistirilmis_pozisyonu_reddeder():
    """`pozisyon.mae`, gercek bir OnaylanmisPozisyon'un `dataclasses.replace` ile
    degistirilmis bir kopyasini (p0 sahtelenmis) KABUL ETMEMELI."""
    plan, zamanlar, _, _ = _basit_plan()
    fund = _tam_funding_icin(plan)
    onayli = pozisyon_modulu.olay_karari(
        _cerceve(zamanlar), fund, plan.sinyal_zamani, plan.ufuk, config.BAR_4H,
        hipotez="H1", birincil_ufuk=plan.birincil_ufuk, **kume_sinirlari(plan.sinyal_zamani),
        donem_baslangic=plan.donem_baslangic, donem_bitis=plan.donem_bitis,
        sinyal_degerleri=sinyal("H1"),
        **uygunluk(config.BAR_4H, plan.donem_baslangic, plan.donem_bitis),  # Rev.9 §4: uygunluk karar noktasinda
    )
    sahte = replace(onayli, p0=0.0001)  # imza artik tutarsiz
    with pytest.raises(ValueError):
        pozisyon_modulu.mae(_cerceve(zamanlar), sahte)
    with pytest.raises(ValueError):
        pozisyon_modulu.pozisyon_fiyatlari(sahte)


def test_pozisyon_fiyatlari_ham_pozisyonplani_ile_dogrudan_cagriyi_reddeder():
    """`pozisyon.pozisyon_fiyatlari`, `OnaylanmisPozisyon` yerine dogrudan bir
    `PozisyonPlani` (tek karar noktasindan gecmemis) verilirse TypeError vermeli."""
    plan, *_ = _basit_plan()
    with pytest.raises(TypeError):
        pozisyon_modulu.pozisyon_fiyatlari(plan)


def test_funding_tam_olmayan_olay_brut_dahil_hicbir_hesapta_olusmaz():
    """Funding'i tam olmayan bir sinyal `olay_karari`dan FundingTamDegil ile
    reddedilmeli; kismi/brut bir OnaylanmisPozisyon asla dogmamali (on-kayit §4
    rev.8: 'funding'i tam olmayan olay ... brut getiri dahil hicbir hesapta
    olusmaz')."""
    plan, zamanlar, donem_bas, donem_bitis = _basit_plan()
    bos_funding = pd.DataFrame(columns=["odeme_zamani", "aralik_saat", "oran", "oran_8h"])
    with pytest.raises(pozisyon_modulu.FundingTamDegil):
        pozisyon_modulu.olay_karari(
            _cerceve(zamanlar), bos_funding, plan.sinyal_zamani, plan.ufuk, config.BAR_4H,
            hipotez="H1", birincil_ufuk=plan.birincil_ufuk, **kume_sinirlari(plan.sinyal_zamani),
            donem_baslangic=donem_bas, donem_bitis=donem_bitis,
            sinyal_degerleri=sinyal("H1"),
            **uygunluk(config.BAR_4H, donem_bas, donem_bitis),  # Rev.9 §4: uygunluk karar noktasinda
        )


def test_nan_sinyal_degeri_pozisyon_planindan_once_reddedilir():
    """`sinyal_degerleri` icinde NaN varsa `SinyalPenceresiTamDegil` firlatilmali
    ve `pozisyon_plani`ya HIC ULASILMAMALI (bozuk/eksik zaman dizisiyle bile
    cagirsak once bu kontrolden donmeli; aksi halde alt katmanlarda coker ya da
    yanlislikla ilerler)."""
    bozuk_zamanlar = pd.DatetimeIndex([])  # boyle bir seriyle pozisyon_plani cokerdi
    with pytest.raises(pozisyon_modulu.SinyalPenceresiTamDegil):
        pozisyon_modulu.olay_karari(
            _cerceve(bozuk_zamanlar), _funding([]), T("2025-06-01 00:00"), 6, config.BAR_4H,  # Rev.10: on-kayit ufku
            hipotez="H1", birincil_ufuk=18, **kume_sinirlari(T('2025-06-01 00:00')),
            donem_baslangic=T("2025-06-01 00:00"), donem_bitis=T("2025-06-10 00:00"),
            sinyal_degerleri=sinyal("H1", pump_dip=float("nan")),  # F1 kapanis turu: tam sinyal kumesi
            **uygunluk(config.BAR_4H, T("2025-06-01 00:00"), T("2025-06-10 00:00")),  # Rev.9 §4
        )


def test_onaylanmis_pozisyon_replace_ile_funding_toplamini_sahteleyemez():
    """Gercek bir OnaylanmisPozisyon'un `funding_toplami` alani `dataclasses.replace`
    ile buyuk bir sahte degere cekilirse, `pozisyon_fiyatlari` ve `mae` YINE DE
    reddetmeli (imza tum alanlara bagli, yalniz p0/p1 degil)."""
    plan, zamanlar, _, _ = _basit_plan()
    fund = _tam_funding_icin(plan)
    onayli = pozisyon_modulu.olay_karari(
        _cerceve(zamanlar), fund, plan.sinyal_zamani, plan.ufuk, config.BAR_4H,
        hipotez="H1", birincil_ufuk=plan.birincil_ufuk, **kume_sinirlari(plan.sinyal_zamani),
        donem_baslangic=plan.donem_baslangic, donem_bitis=plan.donem_bitis,
        sinyal_degerleri=sinyal("H1"),
        **uygunluk(config.BAR_4H, plan.donem_baslangic, plan.donem_bitis),  # Rev.9 §4: uygunluk karar noktasinda
    )
    sahte = replace(onayli, funding_toplami=999.0)
    with pytest.raises(ValueError):
        pozisyon_modulu.pozisyon_fiyatlari(sahte)
    with pytest.raises(ValueError):
        pozisyon_modulu.mae(_cerceve(zamanlar), sahte)
