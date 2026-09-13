"""Zamanla tanimli pencere, tamlik ve ufuk testleri (on-kayit §2, revizyon 3)."""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import pencere


def _seri(bas: str, adet: int, bar: str = config.BAR_4H, deger: float = 1.0) -> pd.Series:
    indeks = pd.date_range(bas, periods=adet, freq=pencere.adim(bar), tz="UTC")
    return pd.Series([deger] * adet, index=indeks)


# --- Tamlik sarti ------------------------------------------------------------


def test_pencerede_tek_bar_eksikse_nan_doner():
    """On-kayit rev.3: penceredeki barlardan biri bile eksikse deger hesaplanmaz."""
    tam = _seri("2021-01-01", 40)
    bitis = tam.index[-1]

    assert not pd.isna(pencere.pencere_degeri(tam, bitis, 10, config.BAR_4H, t_dahil=True, kume_baslangic=None, donem_baslangic=None, karantina_aylari=None))

    eksik = tam.drop(tam.index[-5])  # pencerenin ortasindan bir bar
    assert pd.isna(pencere.pencere_degeri(eksik, bitis, 10, config.BAR_4H, t_dahil=True, kume_baslangic=None, donem_baslangic=None, karantina_aylari=None))


def test_pencere_disindaki_eksik_bar_etkilemez():
    tam = _seri("2021-01-01", 40)
    bitis = tam.index[-1]
    eksik = tam.drop(tam.index[2])  # pencerenin cok oncesi

    assert not pd.isna(pencere.pencere_degeri(eksik, bitis, 10, config.BAR_4H, t_dahil=True, kume_baslangic=None, donem_baslangic=None, karantina_aylari=None))


def test_nan_degerli_bar_da_pencereyi_gecersiz_kilar():
    seri = _seri("2021-01-01", 40)
    seri.iloc[-3] = float("nan")
    assert pd.isna(pencere.pencere_degeri(seri, seri.index[-1], 10, config.BAR_4H, t_dahil=True, kume_baslangic=None, donem_baslangic=None, karantina_aylari=None))


def test_tamlik_kontrolu_pencere_dilimi_uzerinden():
    tam = _seri("2021-01-01", 20)
    assert pencere.pencere_dilimi(tam, tam.index[-1], 5, config.BAR_4H, t_dahil=True, kume_baslangic=None, donem_baslangic=None, karantina_aylari=None) is not None

    eksik = tam.drop(tam.index[-2])
    assert pencere.pencere_dilimi(eksik, tam.index[-1], 5, config.BAR_4H, t_dahil=True, kume_baslangic=None, donem_baslangic=None, karantina_aylari=None) is None


def test_tamlik_kontrolu_tek_basina_kapi_olarak_disari_acik_degil():
    """On-kayit §3 rev.5: sinirlari bilmeyen tamlik kontrolu kume kuralini atlatabilirdi.

    Herkese acik `pencere_tam_mi` kaldirildi; tek kapi pencere_dilimi/pencere_degeri.
    """
    assert not hasattr(pencere, "pencere_tam_mi")


# --- Zamanla olcum -----------------------------------------------------------


def test_pencere_zamanla_olculur_gecmise_uzamaz():
    """On-kayit rev.3: pencere bar SAYISIYLA degil zamanla tanimlanir.

    Eksik barli seride 10 barlik pencere, 10 MEVCUT bari toplayarak gecmise
    uzamamali; eksik varsa NaN donmeli.
    """
    tam = _seri("2021-01-01", 60)
    bitis = tam.index[40]
    beklenen = pencere.beklenen_zamanlar(bitis, 10, config.BAR_4H, t_dahil=True)

    # Pencere araligi tam olarak 10 x 4 saat
    assert beklenen[-1] == bitis
    assert beklenen[0] == bitis - 9 * pd.Timedelta(hours=4)
    assert len(beklenen) == 10

    # Pencerenin icinden bir bar silinince, bar sirasiyla sayan bir uygulama
    # gecmisten bir bar cekip 10'a tamamlardi; zamanla tanimli pencere NaN doner.
    eksik = tam.drop(beklenen[3])
    assert pd.isna(pencere.pencere_degeri(eksik, bitis, 10, config.BAR_4H, t_dahil=True, kume_baslangic=None, donem_baslangic=None, karantina_aylari=None))

    dilim = pencere.pencere_dilimi(tam, bitis, 10, config.BAR_4H, t_dahil=True, kume_baslangic=None, donem_baslangic=None, karantina_aylari=None)
    assert list(dilim.index) == list(beklenen)


def test_gunluk_seride_adim_24_saat():
    gunluk = _seri("2021-01-01", 40, config.BAR_1D)
    beklenen = pencere.beklenen_zamanlar(gunluk.index[-1], 30, config.BAR_1D, t_dahil=True)
    assert beklenen[0] == gunluk.index[-1] - pd.Timedelta(days=29)


def test_bilinmeyen_bar_reddedilir():
    with pytest.raises(ValueError):
        pencere.adim("7h")


# --- Donem ve karantina ------------------------------------------------------


def test_donem_baslangicini_asan_pencere_nan():
    seri = _seri("2021-01-01", 60)
    bitis = seri.index[10]
    donem_bas = seri.index[5]
    assert pd.isna(pencere.pencere_degeri(seri, bitis, 10, config.BAR_4H, t_dahil=True, donem_baslangic=donem_bas, kume_baslangic=None, karantina_aylari=None))
    assert not pd.isna(
        pencere.pencere_degeri(seri, bitis, 10, config.BAR_4H, t_dahil=True, donem_baslangic=seri.index[0], kume_baslangic=None, karantina_aylari=None)
    )


def test_karantinaya_giren_pencere_nan():
    seri = _seri("2021-05-25", 100)
    bitis = pd.Timestamp("2021-06-02 00:00", tz="UTC")
    assert not pd.isna(pencere.pencere_degeri(seri, bitis, 10, config.BAR_4H, t_dahil=True, kume_baslangic=None, donem_baslangic=None, karantina_aylari=None))
    assert pd.isna(
        pencere.pencere_degeri(seri, bitis, 10, config.BAR_4H, t_dahil=True, karantina_aylari=["2021-05"], kume_baslangic=None, donem_baslangic=None)
    )


# --- Giris -------------------------------------------------------------------


def test_t_arti_bir_eksikse_olay_olusmaz():
    """On-kayit rev.3: t+1 bari eksikse olay olusmaz."""
    seri = _seri("2021-01-01", 20)
    t = seri.index[5]

    assert pencere.giris_bari(seri.index, t, config.BAR_4H) == seri.index[6]

    eksik = seri.drop(seri.index[6])
    assert pencere.giris_bari(eksik.index, t, config.BAR_4H) is None


# --- Cikis -------------------------------------------------------------------


def test_normal_cikis_kapanistan():
    seri = _seri("2021-01-01", 60)
    sonuc = pencere.cikis_bari(seri.index, seri.index[5], 18, config.BAR_4H, donem_bitis=None, karantina_aylari=None, kume_bitis=None, birincil_ufuk=18)

    assert sonuc.zaman == seri.index[22]  # t=4, cikis t+18 (on-kayit §4)
    assert sonuc.fiyat_alani == "close"
    assert sonuc.kaydi is False
    assert sonuc.kirpildi is False


def test_cikis_bari_eksikse_sonraki_mevcut_barin_acilisi():
    """On-kayit rev.3: hedef cikis bari eksikse cikis sonraki ilk mevcut barin
    ACILIS fiyatindandir."""
    seri = _seri("2021-01-01", 60)
    giris = seri.index[5]
    hedef = seri.index[22]  # t+18

    eksik = seri.drop([hedef, seri.index[23]])
    sonuc = pencere.cikis_bari(eksik.index, giris, 18, config.BAR_4H, donem_bitis=None, karantina_aylari=None, kume_bitis=None, birincil_ufuk=18)

    assert sonuc.zaman == seri.index[24]  # sonraki ilk MEVCUT bar
    assert sonuc.fiyat_alani == "open"
    assert sonuc.kaydi is True


def test_donem_sonu_ileri_kaymaya_gore_onceliklidir():
    """Donem sonu ve delist kurallari ileri kaymadan onceliklidir."""
    seri = _seri("2021-01-01", 60)
    giris = seri.index[5]
    hedef = seri.index[22]  # t+18
    donem_bitis = seri.index[20]

    eksik = seri.drop(hedef)
    sonuc = pencere.cikis_bari(eksik.index, giris, 18, config.BAR_4H, donem_bitis=donem_bitis, karantina_aylari=None, kume_bitis=None, birincil_ufuk=18)

    assert sonuc.zaman == seri.index[20]
    assert sonuc.fiyat_alani == "close"  # kapanistan, acilistan degil
    assert sonuc.kaydi is False
    assert sonuc.kirpildi is True


def test_delist_serinin_sonuna_kirpar():
    """Ufuk serinin sonunu asarsa cikis son barin kapanisidir."""
    seri = _seri("2021-01-01", 20)
    sonuc = pencere.cikis_bari(seri.index, seri.index[10], 18, config.BAR_4H, donem_bitis=None, karantina_aylari=None, kume_bitis=None, birincil_ufuk=18)

    assert sonuc.zaman == seri.index[-1]
    assert sonuc.fiyat_alani == "close"
    assert sonuc.kirpildi is True


def test_giris_bari_seride_yoksa_hata():
    seri = _seri("2021-01-01", 20)
    with pytest.raises(KeyError):
        pencere.cikis_bari(seri.index, pd.Timestamp("2021-01-01 02:00", tz="UTC"), 5, config.BAR_4H, donem_bitis=None, karantina_aylari=None, kume_bitis=None, birincil_ufuk=18)


# --- Gercek veri: 2022-02-26..28 kesintisi -----------------------------------
#
# Bu testler ONBELLEKTEN okur, aga cikmaz (CLAUDE.md §5). Onbellek yoksa atlanir.

ONBELLEK = config.ONBELLEK_DIZINI / "klines"


def _onbellekten_oku(sembol: str) -> pd.Series | None:
    """cache/klines/<sembol>/4h/*.parquet dosyalarini birlestirir. Ag kullanmaz."""
    dizin = ONBELLEK / sembol / config.BAR_4H
    if not dizin.exists():
        return None
    dosyalar = sorted(dizin.glob("*.parquet"))
    if not dosyalar:
        return None
    parcalar = [pd.read_parquet(d) for d in dosyalar]
    tum = pd.concat(parcalar, ignore_index=True).drop_duplicates("open_time")
    return pd.Series(
        tum["close"].values, index=pd.DatetimeIndex(tum["open_time"])
    ).sort_index()


def _veri_var(sembol: str) -> bool:
    return (ONBELLEK / sembol / config.BAR_4H).exists()


@pytest.mark.skipif(
    not (_veri_var("WAVESUSDT") and _veri_var("KNCUSDT")),
    reason="onbellekte WAVESUSDT/KNCUSDT verisi yok",
)
@pytest.mark.parametrize("sembol", ["WAVESUSDT", "KNCUSDT"])
def test_kesinti_sonrasi_ilk_barda_pencere_nan(sembol):
    """F1 denetimindeki iki sahte sicrama, bosluk kuraliyla disarida kalmali.

    WAVESUSDT +%54,1 ve KNCUSDT +%31,3, ikisi de 2022-03-01 00:00 -- yani
    2022-02-26..28 arasindaki 18 barlik kesintinin ardindan gelen ilk bar.
    Kesintiyi asan her pencere NaN donmeli (on-kayit §2 rev.3).
    """
    seri = _onbellekten_oku(sembol)
    assert seri is not None

    sahte_bar = pd.Timestamp("2022-03-01 00:00", tz="UTC")
    assert sahte_bar in seri.index, "kesinti sonrasi ilk bar seride olmali"

    # Kesintiyi asan pencereler (H2'nin 30 barlik penceresi ve H1'in 6 barlik
    # yukselis penceresi dahil) NaN donmeli.
    for bar_sayisi in (6, 12, 30):
        assert pd.isna(
            pencere.pencere_degeri(seri, sahte_bar, bar_sayisi, config.BAR_4H, t_dahil=True, kume_baslangic=None, donem_baslangic=None, karantina_aylari=None)
        ), f"{sembol}: {bar_sayisi} barlik pencere kesintiyi asmasina ragmen deger dondu"

    # Kesintiden yeterince sonra pencere yeniden gecerli olmali.
    temiz = sahte_bar + pd.Timedelta(hours=4) * 30
    assert not pd.isna(pencere.pencere_degeri(seri, temiz, 30, config.BAR_4H, t_dahil=True, kume_baslangic=None, donem_baslangic=None, karantina_aylari=None))


@pytest.mark.skipif(not _veri_var("WAVESUSDT"), reason="onbellekte WAVESUSDT verisi yok")
def test_kesinti_gercekten_18_bar():
    """Kesintinin boyutu denetim raporundaki sayiyla ayni olmali."""
    seri = _onbellekten_oku("WAVESUSDT")
    zamanlar = seri.index
    beklenen = pd.date_range("2022-02-26 00:00", "2022-02-28 20:00", freq="4h", tz="UTC")

    assert len(beklenen) == 18
    assert not beklenen.isin(zamanlar).any()  # hicbiri yok
    assert pd.Timestamp("2022-02-25 20:00", tz="UTC") in zamanlar  # oncesi var
    assert pd.Timestamp("2022-03-01 00:00", tz="UTC") in zamanlar  # sonrasi var


@pytest.mark.skipif(not _veri_var("WAVESUSDT"), reason="onbellekte WAVESUSDT verisi yok")
def test_kesintiyi_asan_ufuk_ileri_kayar():
    """Kesinti uzerinden gecen ufuk, sonraki ilk mevcut barin acilisina kayar."""
    seri = _onbellekten_oku("WAVESUSDT")

    # Kesintiden hemen once giren bir pozisyonun 6 barlik ufku kesintiye duser.
    giris = pd.Timestamp("2022-02-25 20:00", tz="UTC")
    sonuc = pencere.cikis_bari(seri.index, giris, 6, config.BAR_4H, donem_bitis=None, karantina_aylari=None, kume_bitis=None, birincil_ufuk=18)

    assert sonuc.zaman == pd.Timestamp("2022-03-01 00:00", tz="UTC")
    assert sonuc.fiyat_alani == "open"
    assert sonuc.kaydi is True


# --- Pencere siniri: t_dahil (on-kayit §5 rev.4) -----------------------------


@pytest.mark.parametrize(
    "cagri",
    [
        lambda s: pencere.beklenen_zamanlar(s.index[-1], 5, config.BAR_4H),
        lambda s: pencere.pencere_dilimi(s, s.index[-1], 5, config.BAR_4H, kume_baslangic=None, donem_baslangic=None, karantina_aylari=None),
        lambda s: pencere.pencere_degeri(s, s.index[-1], 5, config.BAR_4H, kume_baslangic=None, donem_baslangic=None, karantina_aylari=None),
    ],
)
def test_t_dahil_belirtilmezse_hata_verir(cagri):
    """On-kayit §5 rev.4: varsayilan davranis yoktur, belirtilmeyen cagri hata verir."""
    with pytest.raises(TypeError):
        cagri(_seri("2021-01-01", 20))


@pytest.mark.parametrize("deger", [None, 0, 1, "True"])
def test_t_dahil_bool_olmayan_deger_reddedilir(deger):
    seri = _seri("2021-01-01", 20)
    with pytest.raises(TypeError):
        pencere.pencere_degeri(seri, seri.index[-1], 5, config.BAR_4H, t_dahil=deger, kume_baslangic=None, donem_baslangic=None, karantina_aylari=None)


def test_t_dahil_izgarayi_bir_bar_kaydirir():
    t = pd.Timestamp("2021-01-05 12:00", tz="UTC")
    adim = pd.Timedelta(hours=4)

    dahil = pencere.beklenen_zamanlar(t, 6, config.BAR_4H, t_dahil=True)
    haric = pencere.beklenen_zamanlar(t, 6, config.BAR_4H, t_dahil=False)

    assert len(dahil) == len(haric) == 6
    assert dahil[-1] == t and dahil[0] == t - 5 * adim
    assert haric[-1] == t - adim and haric[0] == t - 6 * adim  # t-6..t-1
    assert t not in haric


def test_h2_kirilim_penceresi_t_barinin_dibini_icermez():
    """On-kayit §5 H2: close[t] < min(low[t-k..t-1]).

    Pencere t'yi icerseydi min(low) en fazla low[t] <= close[t] olurdu ve kosul
    HICBIR ZAMAN saglanamazdi. t_dahil=False ile t'nin dibi pencereye girmez.
    """
    low = _seri("2021-01-01", 20, deger=100.0)
    t = low.index[-1]
    low.loc[t] = 50.0  # t barinda sert dusus
    close_t = 60.0     # close[t] >= low[t] her zaman

    haric = pencere.pencere_degeri(low, t, 6, config.BAR_4H, t_dahil=False, islev="min", kume_baslangic=None, donem_baslangic=None, karantina_aylari=None)
    dahil = pencere.pencere_degeri(low, t, 6, config.BAR_4H, t_dahil=True, islev="min", kume_baslangic=None, donem_baslangic=None, karantina_aylari=None)

    assert haric == 100.0 and close_t < haric    # kirilim tespit edilebilir
    assert dahil == 50.0 and not close_t < dahil  # t dahil edilseydi asla


def test_h1_dip_penceresi_t_barinin_dibini_icermez():
    """On-kayit §5 H1: close[t] / min(low[t-6..t-1]) - 1.

    t'nin kendi dibi paya girerse pump orani sistematik olarak sisirilir.
    """
    low = _seri("2021-01-01", 20, deger=100.0)
    t = low.index[-1]
    low.loc[t] = 70.0

    assert pencere.pencere_degeri(low, t, 6, config.BAR_4H, t_dahil=False, islev="min", kume_baslangic=None, donem_baslangic=None, karantina_aylari=None) == 100.0


# --- Karantina ve cikis (on-kayit §4 rev.4) ----------------------------------
#
# "Ufuk bir karantina ayina uzanirsa cikis, karantinadan onceki son barin
# kapanisidir. Donem sonu, delist ve karantina kurallari ileri kayma kuralindan
# onceliklidir."


def test_ufuk_karantinaya_uzanirsa_karantina_oncesi_son_kapanis():
    seri = _seri("2021-05-25", 100)
    giris = pd.Timestamp("2021-05-30 08:00", tz="UTC")  # ufuk 2021-06-02 08:00'e uzanir

    sonuc = pencere.cikis_bari(seri.index, giris, 18, config.BAR_4H, karantina_aylari=["2021-06"], donem_bitis=None, kume_bitis=None, birincil_ufuk=18)

    assert sonuc.zaman == pd.Timestamp("2021-05-31 20:00", tz="UTC")
    assert sonuc.fiyat_alani == "close"
    assert sonuc.kirpildi is True
    assert sonuc.kirpma_nedeni == "karantina"


def test_karantinaya_uzanmayan_ufuk_etkilenmez():
    seri = _seri("2021-05-25", 100)
    giris = pd.Timestamp("2021-05-26 00:00", tz="UTC")

    sonuc = pencere.cikis_bari(seri.index, giris, 6, config.BAR_4H, karantina_aylari=["2021-06"], donem_bitis=None, kume_bitis=None, birincil_ufuk=18)

    assert sonuc.zaman == giris + 5 * pd.Timedelta(hours=4)  # t+6
    assert sonuc.kirpildi is False
    assert sonuc.kirpma_nedeni is None


def test_giristen_onceki_karantina_ayi_cikisi_etkilemez():
    seri = _seri("2021-06-01", 100)
    giris = pd.Timestamp("2021-06-02 00:00", tz="UTC")

    sonuc = pencere.cikis_bari(seri.index, giris, 18, config.BAR_4H, karantina_aylari=["2021-05"], donem_bitis=None, kume_bitis=None, birincil_ufuk=18)

    assert sonuc.kirpildi is False
    assert sonuc.zaman == giris + 17 * pd.Timedelta(hours=4)  # t+18


def test_karantina_ileri_kaymaya_gore_onceliklidir():
    """Hedef bar eksik VE karantinada: karantinaya kayilmaz, oncesinde kapanis."""
    seri = _seri("2021-05-25", 100)
    giris = pd.Timestamp("2021-05-30 08:00", tz="UTC")
    eksik = seri.drop(pd.Timestamp("2021-06-02 08:00", tz="UTC"))

    sonuc = pencere.cikis_bari(eksik.index, giris, 18, config.BAR_4H, karantina_aylari=["2021-06"], donem_bitis=None, kume_bitis=None, birincil_ufuk=18)

    assert sonuc.zaman == pd.Timestamp("2021-05-31 20:00", tz="UTC")
    assert sonuc.fiyat_alani == "close"
    assert sonuc.kaydi is False


def test_eksik_hedefin_sonraki_bari_karantinadaysa_oraya_kayilmaz():
    """Hedef karantinadan ONCE ama eksik; sonraki mevcut bar karantina ayinda.

    Ileri kayma karantinaya girmemeli; cikis karantina oncesi son barin kapanisi.
    """
    seri = _seri("2021-05-25", 100)
    giris = pd.Timestamp("2021-05-30 20:00", tz="UTC")
    hedef = pd.Timestamp("2021-05-31 20:00", tz="UTC")  # t+7, ayin son bari, eksik
    eksik = seri.drop(hedef)

    sonuc = pencere.cikis_bari(eksik.index, giris, 7, config.BAR_4H, karantina_aylari=["2021-06"], donem_bitis=None, kume_bitis=None, birincil_ufuk=18)

    assert sonuc.zaman == pd.Timestamp("2021-05-31 16:00", tz="UTC")
    assert sonuc.fiyat_alani == "close"
    assert sonuc.kirpma_nedeni == "karantina"


def test_donem_sonu_karantinadan_onceyse_neden_donem_sonu():
    seri = _seri("2021-05-25", 100)
    giris = pd.Timestamp("2021-05-30 08:00", tz="UTC")
    donem_bitis = pd.Timestamp("2021-05-31 08:00", tz="UTC")

    sonuc = pencere.cikis_bari(seri.index, giris, 18, config.BAR_4H, donem_bitis=donem_bitis, karantina_aylari=["2021-06"], kume_bitis=None, birincil_ufuk=18)

    assert sonuc.zaman == donem_bitis
    assert sonuc.kirpma_nedeni == "donem_sonu"


def test_seri_sonu_kirpmasinin_nedeni_seri_sonu():
    seri = _seri("2021-01-01", 20)
    sonuc = pencere.cikis_bari(seri.index, seri.index[10], 18, config.BAR_4H, donem_bitis=None, karantina_aylari=None, kume_bitis=None, birincil_ufuk=18)
    assert sonuc.kirpma_nedeni == "seri_sonu"


def test_giris_karantina_ayindaysa_hata():
    """Karantina ayinda giris olamaz; uygunluk bunu zaten engeller, cikis da reddeder."""
    seri = _seri("2021-05-25", 100)
    with pytest.raises(ValueError):
        pencere.cikis_bari(seri.index, pd.Timestamp("2021-06-02 00:00", tz="UTC"), 6, config.BAR_4H, karantina_aylari=["2021-06"], donem_bitis=None, kume_bitis=None, birincil_ufuk=18)


@pytest.mark.parametrize("eksik", ["donem_bitis", "karantina_aylari", "kume_bitis", "birincil_ufuk"])
def test_cikis_bari_sinir_parametresi_unutulursa_hata(eksik):
    """F1 kapanis bulgulari 1 ve 2: sinirlar zorunludur; unutulan sinir sessizce
    atlanmaz. (Eski donem.cikis_bar_indeksi sarmalayicisi kaldirildi.)
    On-kayit §4 rev.6: ileri kayma siniri da zorunludur."""
    seri = _seri("2021-05-25", 100)
    sinirlar = {"donem_bitis": None, "karantina_aylari": ["2021-06"], "kume_bitis": None, "birincil_ufuk": 18}
    del sinirlar[eksik]
    with pytest.raises(TypeError):
        pencere.cikis_bari(seri.index, pd.Timestamp("2021-05-30 08:00", tz="UTC"), 18, config.BAR_4H, **sinirlar)


@pytest.mark.parametrize("eksik", ["donem_baslangic", "karantina_aylari", "kume_baslangic"])
def test_pencere_sinir_parametresi_unutulursa_hata(eksik):
    seri = _seri("2021-05-25", 100)
    sinirlar = {"donem_baslangic": None, "karantina_aylari": None, "kume_baslangic": None}
    del sinirlar[eksik]
    with pytest.raises(TypeError):
        pencere.pencere_degeri(seri, seri.index[-1], 6, config.BAR_4H, t_dahil=True, **sinirlar)


def test_karantina_tek_metin_olarak_verilemez():
    seri = _seri("2021-05-25", 100)
    with pytest.raises(TypeError):
        pencere.pencere_degeri(
            seri, seri.index[-1], 6, config.BAR_4H, t_dahil=True,
            kume_baslangic=None, donem_baslangic=None, karantina_aylari="2021-06",
        )


@pytest.mark.skipif(not _veri_var("LITUSDT"), reason="onbellekte LITUSDT verisi yok")
def test_litusdt_karantina_ayina_uzanan_ufuk_gercek_veri():
    """LITUSDT 2025-12 karantinasi: bu ayda +%531'lik yeniden fiyatlandirma var.

    Karantina oncesi giren bir pozisyonun ufku 2025-12'ye uzanirsa cikis,
    2025-11-30 20:00 barinin kapanisidir; yeniden fiyatlandirma sonrasi bir
    bardan okunmaz (on-kayit §4 rev.4).
    """
    seri = _onbellekten_oku("LITUSDT")
    karantina = ["2025-12"]
    sicrama = pd.Timestamp("2025-12-23 16:00", tz="UTC")
    assert pd.Period(sicrama, freq="M") == pd.Period("2025-12", freq="M")

    giris = pd.Timestamp("2025-11-29 20:00", tz="UTC")
    assert giris in seri.index

    sonuc = pencere.cikis_bari(seri.index, giris, 18, config.BAR_4H, karantina_aylari=karantina, donem_bitis=None, kume_bitis=None, birincil_ufuk=18)
    assert sonuc.zaman == pd.Timestamp("2025-11-30 20:00", tz="UTC")
    assert sonuc.fiyat_alani == "close"
    assert sonuc.kirpma_nedeni == "karantina"

    # Karantina verilmezse cikis karantina ayinin icine duserdi.
    korumasiz = pencere.cikis_bari(seri.index, giris, 18, config.BAR_4H, donem_bitis=None, karantina_aylari=None, kume_bitis=None, birincil_ufuk=18)
    assert pd.Period(korumasiz.zaman, freq="M") == pd.Period("2025-12", freq="M")


@pytest.mark.skipif(not _veri_var("LITUSDT"), reason="onbellekte LITUSDT verisi yok")
def test_litusdt_sicrama_barina_uzanan_ufuk_sicramadan_okunmaz():
    """Sicramadan hemen once (karantina ayinda) giris zaten gecersiz."""
    seri = _onbellekten_oku("LITUSDT")
    with pytest.raises(ValueError):
        pencere.cikis_bari(seri.index, pd.Timestamp("2025-12-22 16:00", tz="UTC"), 6, config.BAR_4H, karantina_aylari=["2025-12"], donem_bitis=None, kume_bitis=None, birincil_ufuk=18)


# --- Ufuk uzunlugu (on-kayit §4) ---------------------------------------------


def test_ufuk_h_bar_tutar_cikis_t_arti_h_kapanisi():
    """On-kayit §4: P0 = open[t+1], P1 = close[t+h]; pozisyon h bar tutulur.

    Onceki uygulama hedefi giris + h x adim hesapliyordu; giris zaten t+1
    oldugu icin cikis t+h+1'e dusuyor ve pozisyon h+1 bar tutuluyordu.
    """
    seri = _seri("2021-01-01", 60)
    t = seri.index[4]
    giris = pencere.giris_bari(seri.index, t, config.BAR_4H)
    assert giris == seri.index[5]

    for h in (1, 6, 18, 42):
        sonuc = pencere.cikis_bari(seri.index, giris, h, config.BAR_4H, donem_bitis=None, karantina_aylari=None, kume_bitis=None, birincil_ufuk=18)
        assert sonuc.zaman == t + h * pd.Timedelta(hours=4), h
        tutulan = seri.index[(seri.index >= giris) & (seri.index <= sonuc.zaman)]
        assert len(tutulan) == h, h


def test_ufuk_bir_ise_cikis_giris_barinin_kapanisi():
    seri = _seri("2021-01-01", 20)
    sonuc = pencere.cikis_bari(seri.index, seri.index[5], 1, config.BAR_4H, donem_bitis=None, karantina_aylari=None, kume_bitis=None, birincil_ufuk=18)
    assert sonuc.zaman == seri.index[5]
    assert sonuc.fiyat_alani == "close"


@pytest.mark.parametrize("ufuk", [0, -3])
def test_ufuk_birden_kucukse_hata(ufuk):
    seri = _seri("2021-01-01", 20)
    with pytest.raises(ValueError):
        pencere.cikis_bari(seri.index, seri.index[5], ufuk, config.BAR_4H, donem_bitis=None, karantina_aylari=None, kume_bitis=None, birincil_ufuk=18)

