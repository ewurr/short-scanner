"""F1 KAPANIS sizinti saldirilari: data/ katmanini kirmaya calisir.

Bu dosya metodoloji denetcisinin F1 kapanis raporundaki bulgulari (1, 2, 4, 5,
7, 8, 9, 13, 14, 15 numarali maddeler) somut, calisan testlere cevirir. Amac
kodun DOGRU calistigini gostermek degil; on-kayit / CLAUDE.md kurallarindan
birinin fiilen delindigini kanitlamaktir.

Ilk surumde dokuz testin dokuzu da KIRMIZI kaldi (gercek pytest). Duzeltmelerden
sonra her test, kapatilan acigi dogrulayacak sekilde guncellendi; saldirinin
niyeti korundu, yalnizca kaldirilan ya da degisen API'ye uyarlandi. Hangi
duzeltmenin hangi testi kapattigi her docstring'in "Durum" satirinda yazilidir.

Hicbir test aga cikmaz (conftest.ag_kapali). Onbellek girdileri tmp_path uzerinde
sahte olarak kurulur; gercek cache/ ve ONAY_KAYDI.md dosyalarina dokunulmaz.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import binance_vision as bv
from data import donem as donem_modulu
from data import klines, pencere, split
from tarama_yardimcisi import KUME_NONE_DESENI, ihlaller


def _seri(bas: str, adet: int, bar: str = config.BAR_4H, deger: float = 1.0) -> pd.Series:
    indeks = pd.date_range(bas, periods=adet, freq=pencere.adim(bar), tz="UTC")
    return pd.Series([deger] * adet, index=indeks)


def _sahte_4h(bas: str, bar_sayisi: int, hacim: float = 1_000_000.0) -> pd.DataFrame:
    zaman = pd.date_range(bas, periods=bar_sayisi, freq="4h", tz="UTC")
    return pd.DataFrame(
        {
            "open_time": zaman,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 10.0,
            "close_time": zaman + pd.Timedelta(hours=4) - pd.Timedelta(milliseconds=1),
            "quote_volume": hacim,
            "count": 5,
            "taker_buy_volume": 5.0,
            "taker_buy_quote_volume": hacim / 2,
        }
    )


# --- 1) donem.cikis_bar_indeksi kume_bitis iletmiyor: kume siniri atlanir ----


def test_donem_cikis_bar_indeksi_kume_sinirini_kontrol_etmiyor():
    """Denetci bulgusu #1: `donem.cikis_bar_indeksi` `pencere.cikis_bari`ya
    `kume_bitis` iletmiyordu; ayni senaryoda kume disina tasan bir cikis sessizce
    uretilebiliyordu.

    On-kayit §3 rev.4: ufuk sonu kume sinirini asarsa `KumeSiniriHatasi`; olay o
    kumede olusmaz.

    Durum: A1 ile kapandi. Sarmalayici kaldirildi; `cikis_bari`de `kume_bitis`
    zorunludur, unutulursa TypeError verir.
    """
    seri = _seri("2021-01-01", 60)
    kume_son = seri.index[30]  # kume, index 30'da biter
    giris = seri.index[20]
    ufuk = 15  # hedef = giris + 14 adim = index 34 > kume_son(30): kume disina tasar

    with pytest.raises(pencere.KumeSiniriHatasi):
        pencere.cikis_bari(
            seri.index, giris, ufuk, config.BAR_4H, kume_bitis=kume_son, donem_bitis=None, karantina_aylari=None, birincil_ufuk=18
        )

    assert not hasattr(donem_modulu, "cikis_bar_indeksi"), "kume korumasiz sarmalayici hala duruyor"
    with pytest.raises(TypeError):  # kume_bitis unutulamaz
        pencere.cikis_bari(seri.index, giris, ufuk, config.BAR_4H, donem_bitis=None, karantina_aylari=None, birincil_ufuk=18)


# --- 2) onay parametresi bool dogrulanmiyor: "False" stringi kapiyi aciyor --


def test_kume_erisimi_onay_stringi_false_yetkisiz_erisimi_aciyor(tmp_path, monkeypatch):
    """Denetci bulgusu #8: `onay` parametresi bool olarak dogrulanmiyordu.

    CLAUDE.md §3.3: C1/C2 onay kumelerine yalnizca onayla erisilebilir; onaysiz
    erisim reddedilmeli ve HICBIR SEY kayda yazilmamali. Eski kontrol
    `not onay` idi; `not "False"` Python'da False oldugu icin `onay="False"`
    kapiyi aciyor ve kayda bir satir yaziyordu.

    Durum: A4 ile kapandi. `onay` yalnizca gercek bool olabilir; onay kumesine
    ayrica acik bir `onay_kosusu` gerekir. Kopya kayit uzerinde calisir.
    """
    kopya = tmp_path / "ONAY_KAYDI.md"
    kopya.write_bytes(config.ONAY_KAYDI.read_bytes())
    once = kopya.read_bytes()
    monkeypatch.setattr(config, "ONAY_KAYDI", kopya)

    with pytest.raises(PermissionError):
        split.kume_erisimi("ZZUSDT", "C1", onay="False")

    assert kopya.read_bytes() == once, (
        "onay='False' onay kumesine erisimi PermissionError vermeden acti ya da kopya "
        "onay kaydina satir yazdi; tek atis kurali bool olmayan bir degerle atlatildi."
    )


# --- 3) split= parametresi dogrulanmiyor: sahte tablo grubu degistirebiliyor -


def test_kume_erisimi_sahte_split_tablosu_dogrulanmadan_kabul_edilir(tmp_path, monkeypatch):
    """Denetci bulgusu #9: yukleyiciler disaridan bir `split` tablosu kabul ediyor
    ve bolme kuraliyla karsilastirmiyordu; B grubunda olmasi gereken bir sembol
    elle "A" isaretlenip KESIF'e sokulabiliyordu.

    On-kayit §3 / CLAUDE.md §3.2: coin grubu sonradan degistirilemez.

    Durum: A4 ile kapandi. `split=` parametresi kaldirildi (verilirse TypeError);
    betikle degistirilmis bir split.csv de `split_oku` dogrulamasinda reddedilir.
    """
    assert split.grup("SAHTEUSDT") == "B"
    sahte = pd.DataFrame({"sembol": ["SAHTEUSDT"], "varlik_anahtari": ["SAHTEUSDT"], "grup": ["A"]})

    with pytest.raises(TypeError):
        split.kume_erisimi("SAHTEUSDT", "KESIF", split=sahte)

    yol = tmp_path / "split.csv"
    sahte.to_csv(yol, index=False)
    monkeypatch.setattr(config, "SPLIT_CSV", yol)
    with pytest.raises(split.BolmeTutarsizligi):
        split.kume_erisimi("SAHTEUSDT", "KESIF")


# --- 4) kume_baslangic=None kume-oncesi veri sizintisini sessizce acar ------


def test_kume_baslangic_none_verilince_kume_oncesi_veri_sizar(tmp_path):
    """Denetci bulgusu #4: `kume_baslangic` serbest bir parametredir; `None`
    gecilirse rev.5 kurali devre disi kalir ve kume oncesi pencere deger uretir.

    `None` bilincli olarak kalir: kumeye ait olmayan hesaplar (F1 denetimi) icin
    gereklidir ve kume disi hesapta dogru sonuc budur. Kapatilmasi gereken yol,
    F2 ve sonrasi analiz kodunun kume sinirini `None` ile kapatmasidir.

    Durum: A1 ile kapandi. `kume_baslangic=None` / `kume_bitis=None` yalnizca
    data/, tests/ ve F1 denetim dizininde gecebilir; kaynak taramasi analiz
    kodundaki kullanimi yakalar. Bu test hem taramanin yakaladigini hem de gercek
    depoda ihlal olmadigini dogrular.
    """
    seri = _seri("2021-01-01", 40)
    kume_bas = seri.index[20]
    t = seri.index[25]  # pencere (10 bar, t dahil) index 16..25: kume oncesine tasar
    ortak = dict(donem_baslangic=None, karantina_aylari=None)
    assert pd.isna(pencere.pencere_degeri(seri, t, 10, config.BAR_4H, t_dahil=True, kume_baslangic=kume_bas, **ortak))

    (tmp_path / "events").mkdir()
    (tmp_path / "events" / "h1.py").write_text(
        "d = pencere.pencere_degeri(s, t, 10, bar, t_dahil=True, kume_baslangic=None, **o)\n", encoding="utf-8"
    )
    (tmp_path / "study").mkdir()
    (tmp_path / "study" / "k2.py").write_text("cikis_bari(z, g, 18, bar, kume_bitis = None)\n", encoding="utf-8")
    assert ihlaller(KUME_NONE_DESENI, kok=tmp_path) == ["events/h1.py", "study/k2.py"]

    assert ihlaller(KUME_NONE_DESENI) == [], "analiz kodu kume sinirini None ile kapatiyor"


# --- 5) saat dilimsiz (naive) t sessizce NaN uretiyor, hata vermiyor --------


def test_pencere_degeri_saat_dilimsiz_t_sessizce_nan_dondurur_hata_vermez():
    """Denetci bulgusu #15: saat dilimsiz `t`, UTC'li seriyle karsilastirilinca
    hicbir hata vermeden NaN uretiyordu; "kural geregi NaN" ile "yanlis tip
    yuzunden hep NaN" ayirt edilemiyordu.

    Durum: A5 ile kapandi. Saat dilimsiz zaman TypeError verir.
    """
    seri = _seri("2021-01-01", 40)  # tz-aware (UTC) seri
    t_aware = seri.index[30]
    t_naive = pd.Timestamp(t_aware.tz_localize(None))
    sinirlar = dict(kume_baslangic=None, donem_baslangic=None, karantina_aylari=None)

    dogru = pencere.pencere_degeri(seri, t_aware, 10, config.BAR_4H, t_dahil=True, **sinirlar)
    assert not pd.isna(dogru), "kurulum hatasi: tz-aware t ile bile deger NaN geldi"

    with pytest.raises((TypeError, ValueError)):
        pencere.pencere_degeri(seri, t_naive, 10, config.BAR_4H, t_dahil=True, **sinirlar)


# --- 6) klines onbellekte cakisan zaman damgasi sessizce "cozuluyor" --------


def test_ham_mumlari_yukle_cakisan_zaman_damgasini_sessizce_cozer(tmp_path, monkeypatch):
    """Denetci bulgusu #14: onbellekte ayni `open_time` iki farkli deger
    tasiyorsa `ham_mumlari_yukle` bunu `drop_duplicates(keep="last")` ile
    sessizce cozuyordu; `data/pencere.py` ise ayni durumu bozuk veri sayar.

    Durum: A5 ile kapandi. Tekrar ZamanDizisiHatasi verir. Sahte onbellek.
    """
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", tmp_path)
    sembol, bar = "TESTUSDT", config.BAR_4H
    anahtar = f"{bv.MUM_ONEKI}/{sembol}/{bar}/{sembol}-{bar}-2021-01.zip"
    monkeypatch.setattr(bv, "mum_dosyalari", lambda s, b: [anahtar])

    def _zip_indir_yasak(*_a, **_k):
        raise AssertionError("onbellek doluyken zip_indir cagrilmamali (ag kullanilmamali)")

    monkeypatch.setattr(bv, "zip_indir", _zip_indir_yasak)

    temel = _sahte_4h("2021-01-01", 6, hacim=1_000_000.0)
    celisen = temel.iloc[[3]].copy()
    celisen["close"] = 999.0
    celisen["quote_volume"] = 42.0
    bozuk_onbellek = pd.concat([temel, celisen], ignore_index=True)

    yol = bv.onbellek_yolu("klines", sembol, bar, "2021-01.parquet")
    bozuk_onbellek.to_parquet(yol, index=False)

    with pytest.raises(pencere.ZamanDizisiHatasi):
        klines.ham_mumlari_yukle(sembol, bar)


# --- 7) gunluge_cevir: NaN hacimli bar tam gun sayilip kismen toplaniyor ----


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Bilinen ve kapatilmamis davranis (A6 karari): F1 kapanis onbellek taramasi "
        "3.692.573 4h barda hic NaN hucre bulmadi; kullanici talimati geregi kod "
        "degistirilmedi. Test, gunluge_cevir'in NaN hacimli bari hala tam gun saydigini "
        "belgeler. strict=True: davranis duzeltilirse test XPASS verip kirmizi olur ve bu "
        "isaret kaldirilmalidir."
    ),
)
def test_gunluge_cevir_nan_hacimli_bari_tam_gun_sayar_kismi_toplar():
    """Denetci bulgusu #13: `gunluge_cevir`nin "tam gun" kontrolu yalnizca bar
    sayisini sayar; hacmi NaN olan bar da mevcut sayilir, gun "tam" kabul edilir ve
    toplam `sum(skipna=True)` ile sessizce eksik hesaplanir.

    Dogru davranis: NaN degerli bar tamlik acisindan mevcut sayilmamali, gun
    dusurulmelidir.

    Durum: ACIK, xfail. Onbellekte ornegi yok (A6); kod degismedi.
    """
    dortsaatlik = _sahte_4h("2021-01-01", 6, hacim=1_000_000.0)
    dortsaatlik.loc[3, "quote_volume"] = float("nan")

    gunluk = klines.gunluge_cevir(dortsaatlik)

    assert gunluk.empty, (
        "bir 4h barin quote_volume degeri NaN oldugu halde gun 'tam' sayildi "
        f"(uretilen satir sayisi={len(gunluk)})."
    )


# --- 8) funding: 1 ms kayik cift kayit iki odeme olarak sayilabiliyor --------


def test_ham_funding_yukle_yakin_ms_farkli_kayitlari_saate_yuvarlamaz(tmp_path, monkeypatch):
    """Denetci bulgusu #7: `data/funding.py` yorumu "gruplama yapilirken saate
    yuvarlanir" diyordu ama boyle bir kod yoktu; 1 ms farkli iki kayit (ayni
    odemenin kayik iki kopyasi) iki ayri odeme olarak kaliyor ve funding cift
    sayilabiliyordu.

    Durum: A6 + A3 ile kapandi. Onbellek taramasi 2.562.456 kayitta boyle bir cift
    bulmadi; yukleyici degistirilmedi ve yanlis yorum duzeltildi. Cift sayma riski,
    funding'i okuyan tek kapida kapatildi: `funding_ortalamasi` bir dakikadan yakin
    iki kaydi bozuk veri sayip ZamanDizisiHatasi verir. Yukleyicinin iki satiri
    korudugu da (sessizce birlestirmedigi) dogrulanir.
    """
    monkeypatch.setattr(config, "ONBELLEK_DIZINI", tmp_path)
    sembol = "TESTUSDT"
    anahtar = f"{bv.FUNDING_ONEKI}/{sembol}/{sembol}-fundingRate-2021-01.zip"
    monkeypatch.setattr(bv, "funding_dosyalari", lambda s: [anahtar])

    def _zip_indir_yasak(*_a, **_k):
        raise AssertionError("onbellek doluyken zip_indir cagrilmamali (ag kullanilmamali)")

    monkeypatch.setattr(bv, "zip_indir", _zip_indir_yasak)

    taban_zaman = pd.Timestamp("2021-01-01 00:00:00.000", tz="UTC")
    kayik_zaman = taban_zaman + pd.Timedelta(milliseconds=1)
    onbellek = pd.DataFrame(
        {
            "odeme_zamani": [taban_zaman - pd.Timedelta(hours=8), taban_zaman, kayik_zaman],
            "aralik_saat": [8.0, 8.0, 8.0],
            "oran": [0.0001, 0.0001, 0.0001],
        }
    )
    yol = bv.onbellek_yolu("funding", sembol, "2021-01.parquet")
    onbellek.to_parquet(yol, index=False)

    from data import funding as funding_modulu

    sonuc = funding_modulu.ham_funding_yukle(sembol)
    assert len(sonuc) == 3, "yukleyici kayik kaydi sessizce birlestirmemeli ya da silmemeli"

    with pytest.raises(pencere.ZamanDizisiHatasi):
        funding_modulu.funding_ortalamasi(
            sonuc,
            pd.Timestamp("2021-01-01 04:00", tz="UTC"),
            config.BAR_4H,
            saat=24,
            kume_baslangic=None,
            donem_baslangic=None,
            karantina_aylari=None,
        )


# --- 9) kume-kirpilmis seri: gercek delist ile kume-siniri kirpmasi ayirt ---
# --- edilemiyor; kume_bitis verilmezse sessizce 'seri_sonu' olarak kirpilir --


def test_kume_kirpilmis_seri_kume_bitis_verilmezse_delist_gibi_kirpilir():
    """Denetci bulgulari #1 ve #5: `split.yukle` mumlari kume araligina keser;
    `cikis_bari` kume bilgisi olmadan bu kesimi gercek delist ("seri_sonu") ile
    ayirt edemez ve kirpilmis bir cikis dondurur. On-kayit §3 rev.4: kirpilmis
    cikis kullanilmaz, olay o kumede olusmaz.

    Durum: A1 + A5 ile kapandi. `kume_bitis` artik unutulamaz (TypeError). Verilince
    hedef kume sonunu asiyorsa hata; hedef kume icinde ama kesilmis seri daha once
    bitiyorsa ve sembolun donemi kume icinde bitmiyorsa da hata (delist sayilmaz).
    """
    seri = _seri("2021-01-01", 30)
    kume_son = seri.index[24]
    kirpilmis = seri[seri.index <= kume_son]
    assert kirpilmis.index[-1] == kume_son
    assert len(kirpilmis) == 25

    giris = kirpilmis.index[10]
    ufuk = 20  # hedef = index[29] (asil izgarada), kume_son'u (index24) asar

    with pytest.raises(pencere.KumeSiniriHatasi):
        pencere.cikis_bari(kirpilmis.index, giris, ufuk, config.BAR_4H, kume_bitis=kume_son, donem_bitis=None, karantina_aylari=None, birincil_ufuk=18)

    with pytest.raises(TypeError):
        pencere.cikis_bari(kirpilmis.index, giris, ufuk, config.BAR_4H, donem_bitis=None, karantina_aylari=None, birincil_ufuk=18)

    # Hedef kume icinde (index 24) ama son iki bar eksik: seri index 22'de bitiyor.
    eksik_sonlu = kirpilmis.drop(kirpilmis.index[-2:])
    with pytest.raises(pencere.KumeSiniriHatasi):
        pencere.cikis_bari(eksik_sonlu.index, giris, 15, config.BAR_4H, kume_bitis=kume_son, donem_bitis=None, karantina_aylari=None, birincil_ufuk=18)
