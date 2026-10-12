"""Sizinti testcisi saldirilari: F2 basalamadan once son kontrol.

Bu dosya mevcut testlerin (test_pencere.py, test_kume_siniri.py,
test_kume_korumasi.py, test_split.py, test_donem.py, test_onay_kaydi.py) UZERINE
eklenir, onlari tekrarlamaz. Odak: siralama varsayimlari, tekrarlanan zaman
damgasi, t anina kadarki veriyle sinirlanmis kararlarin gelecekten etkilenmemesi
ve gercek split.csv/ONAY_KAYDI.md dosyalarina karsi dogrudan denetim.

Hicbir test aga cikmaz (conftest.ag_kapali). Yalnizca tests/ altina yazildi.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import config
from donem_yardimcisi import TOPLAM_DONEM_B, TOPLAM_DONEM_BASI  # noqa: E402
from data import donem as donem_modulu
from data import eligibility, pencere, split
from onay_yardimcisi import gecici_kayit


def _seri(bas: str, adet: int, bar: str = config.BAR_4H, deger: float = 1.0) -> pd.Series:
    indeks = pd.date_range(bas, periods=adet, freq=pencere.adim(bar), tz="UTC")
    return pd.Series([deger] * adet, index=indeks)


# --- Siralama: cikis_bari sirasiz girdiyi baştan reddeder --------------------
#
# Yukleyiciler (klines.ham_mumlari_yukle, funding.ham_funding_yukle) daima
# sort_values ile sirali dondurur. data/pencere.py bu garantiye YASLANMAZ:
# sirasiz ya da tekrarli zaman dizisi bir veri bozuklugudur ve
# `ZamanDizisiHatasi` ile reddedilir. Onceki uygulama sessizce yanlis sonuc
# uretiyordu (ilk surumdeki bu iki test o acigi gostermisti).


def test_cikis_bari_tam_ters_sirali_seriyi_reddeder():
    """Seriyi ters sirada ver: yanlis cikis uretilmemeli, hata verilmeli.

    Duzeltme oncesinde `cikis_bari` "seri_sonu" sinirini POZISYONEL `indeks[-1]`
    olarak aliyordu; ters seride bu en eski bar oldugu icin cikis girisin bile
    ONCESINE dusuyordu. Artik sirasiz dizi baştan `ZamanDizisiHatasi` verir.
    """
    seri = _seri("2021-01-01", 20)
    giris = seri.index[2]
    ters = seri.index[::-1]

    with pytest.raises(pencere.ZamanDizisiHatasi):
        pencere.cikis_bari(ters, giris, 5, config.BAR_4H, donem_bitis=TOPLAM_DONEM_B, kume_bitis=None, birincil_ufuk=18)


def test_cikis_bari_karisik_sirali_seriyi_reddeder():
    """Karistirilmis sirada ver: yanlis "sonraki bar" secilmemeli, hata verilmeli.

    Duzeltme oncesinde hedef bar eksikken ileri kayma POZISYONEL `sonrakiler[0]`u
    kullaniyordu; sira bozulunca kronolojik olarak dogru bar yerine daha sonraki
    bir bardan cikiliyordu. Seri_sonu siniri bozulmasa bile sirasiz dizi artik
    baştan `ZamanDizisiHatasi` verir.
    """
    seri = _seri("2021-01-01", 60)
    giris = seri.index[5]
    hedef = seri.index[22]  # t+18

    dogru_sonraki = seri.index[23]  # hedef eksikse gercek sonraki ilk mevcut bar
    uzak = seri.index[40]

    # hedef'i cikar; geri kalan dizide dogru_sonraki ile uzaktaki bir bari yer
    # degistir. Seri_sonu siniri (indeks[-1] = idx59) etkilenmez, yalnizca
    # "sonraki ilk mevcut bar" adayinin POZISYONU bozulur.
    tum = [z for z in seri.index if z != hedef]
    i_dogru, i_uzak = tum.index(dogru_sonraki), tum.index(uzak)
    tum[i_dogru], tum[i_uzak] = tum[i_uzak], tum[i_dogru]
    bozuk = pd.DatetimeIndex(tum)
    assert bozuk[-1] == seri.index[-1]  # seri_sonu siniri degismedi

    with pytest.raises(pencere.ZamanDizisiHatasi):
        pencere.cikis_bari(bozuk, giris, 18, config.BAR_4H, donem_bitis=TOPLAM_DONEM_B, kume_bitis=None, birincil_ufuk=18)


# --- Tekrarlanan zaman damgasi: bozuk veri NaN'a cevrilmez, hata verir --------


def test_pencere_dilimi_tekrarlanan_zaman_damgasini_reddeder():
    """Tekrarlanan bar zaman damgasi acik bir hata vermeli; sessizce NaN olmamali.

    On-kayit rev.3'un "deger hesaplanmaz (NaN)" kurali EKSIK bar icindir. Bir
    zaman damgasinin TEKRARLANMASI (indirme/onbellek hatasi, drop_duplicates
    atlanmis olabilir) eksik veri degil bozuk veridir. Duzeltme oncesinde pandas
    `reindex` sirasinda anlasilmaz bir ValueError ile cokuyordu; artik
    `pencere_dilimi` (ve onun uzerinden `pencere_degeri`) tekrari baştan yakalayip
    Turkce `ZamanDizisiHatasi` verir.
    """
    seri = _seri("2021-01-01", 40)
    t = seri.index[39]
    dup_zaman = seri.index[35]
    bozuk = pd.concat([seri, pd.Series([999.0], index=[dup_zaman])])

    with pytest.raises(pencere.ZamanDizisiHatasi, match="tekrarlanan"):
        pencere.pencere_degeri(bozuk, t, 10, config.BAR_4H, t_dahil=True, kume_baslangic=None, donem_baslangic=TOPLAM_DONEM_BASI)


# --- Gelecege bakis: t'nin kendi gununun hacmini bozmak kararini degistirmemeli


def test_uygun_mu_t_gununun_kendi_hacmini_bozmak_karari_degistirmez():
    """On-kayit §2: uygunluk yalnizca t'ye kadarki (t haric gunu) veriyle hesaplanir.

    t'nin kendi gununun hacmi ASIRI sekilde degistirilse bile (o gun henuz
    kapanmadigi icin pencereye girmemesi gerekir) t anindaki uygunluk karari
    degismemelidir.
    """
    gunler = pd.date_range("2021-01-01", periods=40, freq="D", tz="UTC")
    hacim = pd.Series([20_000_000.0] * 40, index=gunler)
    donem_bas = gunler[0]
    t = gunler[35]  # listeleme yasi > 30 gun, hacim esigini gecer

    dogru = eligibility.uygun_mu(hacim, t, config.BAR_4H, donem_baslangic=donem_bas, kume_baslangic=None, donem_bitis=TOPLAM_DONEM_B)
    assert dogru is True

    bozuk = hacim.copy()
    bozuk.loc[t.floor("D")] = 0.0  # t'nin kendi gununu sifirla
    bozuk_sonuc = eligibility.uygun_mu(bozuk, t, config.BAR_4H, donem_baslangic=donem_bas, kume_baslangic=None, donem_bitis=TOPLAM_DONEM_B)

    assert bozuk_sonuc == dogru, (
        "t anindaki uygunluk karari, t'nin KENDI gununun hacmine gore "
        "degisti; bu gelecege bakistir (o gun t aninda henuz kapanmadi)."
    )

    # Ayni sekilde asiri YUKSEK bir deger de karari degistirmemeli.
    tersi = hacim.copy()
    tersi.loc[t.floor("D")] = 1e12
    assert eligibility.uygun_mu(tersi, t, config.BAR_4H, donem_baslangic=donem_bas, kume_baslangic=None, donem_bitis=TOPLAM_DONEM_B) == dogru


def test_medyan_hacim_serinin_sonuna_eklenen_gelecek_bar_gecmisi_degistirmez():
    """Serinin sonuna gelecek tarihli bar ekle: gecmisteki sonuc degismemeli."""
    gunler = pd.date_range("2021-01-01", periods=40, freq="D", tz="UTC")
    hacim = pd.Series(np.arange(1, 41, dtype=float) * 1_000_000, index=gunler)
    donem_bas = gunler[0]
    t = gunler[35]

    once = eligibility.medyan_hacim(hacim, t, donem_baslangic=donem_bas, kume_baslangic=None, pencere_gun=config.HACIM_PENCERESI_GUN)

    genisletilmis = pd.concat(
        [hacim, pd.Series([1e15], index=[gunler[-1] + pd.Timedelta(days=1)])]
    )
    sonra = eligibility.medyan_hacim(genisletilmis, t, donem_baslangic=donem_bas, kume_baslangic=None, pencere_gun=config.HACIM_PENCERESI_GUN)

    assert once == sonra, "gelecege eklenen bar gecmisteki medyan hacmi degistirdi (gelecege bakis)."


def test_pencere_degeri_serinin_sonuna_eklenen_gelecek_bar_gecmisi_degistirmez():
    """Ayni saldiri dogrudan pencere.pencere_degeri uzerinde (H1/H2 pencereleri icin)."""
    seri = _seri("2021-01-01", 40, deger=1.0)
    t = seri.index[30]

    once = pencere.pencere_degeri(seri, t, 10, config.BAR_4H, t_dahil=True, islev="mean", kume_baslangic=None, donem_baslangic=TOPLAM_DONEM_BASI)

    genisletilmis = pd.concat([seri, _seri("2030-01-01", 5, deger=9999.0)])
    sonra = pencere.pencere_degeri(genisletilmis, t, 10, config.BAR_4H, t_dahil=True, islev="mean", kume_baslangic=None, donem_baslangic=TOPLAM_DONEM_BASI)

    assert once == sonra


# --- Gercek split.csv: zincir sizintisi ve B grubu KESIF'e sizamaz ----------


def _gercek_split_var() -> bool:
    return config.SPLIT_CSV.exists()


@pytest.mark.skipif(not _gercek_split_var(), reason="data/split.csv yok")
def test_gercek_split_csvde_yeniden_adlandirma_zincirinin_iki_ucu_ayni_grupta():
    """On-kayit §3: zincirdeki tum semboller ayni gruba dusmeli.

    Gercek `data/split.csv` dosyasi uzerinde, kabul edilmis dokuz zincirin her
    ikisinin de (varsa) ayni grupta oldugunu dogrudan denetler. Bu bir mock
    degil; commit edilmis gercek dosyaya karsi calisir.
    """
    tablo = split.split_oku().set_index("sembol")["grup"]
    ihlaller = []
    for yeni, eski in config.YENIDEN_ADLANDIRMA.items():
        if yeni in tablo.index and eski in tablo.index:
            if tablo[yeni] != tablo[eski]:
                ihlaller.append((yeni, eski, tablo[yeni], tablo[eski]))
    assert ihlaller == [], f"zincirin iki ucu farkli grupta: {ihlaller}"


@pytest.mark.skipif(not _gercek_split_var(), reason="data/split.csv yok")
def test_gercek_split_csvde_b_grubu_kesife_sizamaz():
    """Gercek split.csv'den B grubu bir sembol secip KESIF kume kapisina sorar.

    `kume_erisimi` (split parametresi verilmeden) gercek split.csv'yi okur;
    B grubu sembol KESIF icin izinli=False donmeli.
    """
    tablo = split.split_oku()
    b_grubu = tablo.loc[tablo["grup"] == "B", "sembol"]
    assert not b_grubu.empty, "gercek split.csv'de B grubu sembol yok, saldiri kurulamadi"
    sembol = b_grubu.iloc[0]

    izinli, _, _ = split.kume_erisimi(sembol, "KESIF")
    assert izinli is False, f"{sembol} B grubunda oldugu halde KESIF'e izinli dondu"


# --- ONAY_KAYDI.md: gercek dosyaya onay=True olmadan asla yazilmamali -------


def test_gercek_onay_kaydina_onaysiz_erisim_dosyayi_degistirmez(tmp_path, monkeypatch):
    """CLAUDE.md §3.3: onay=True olmadan C1/C2'ye erisim reddedilmeli VE kayit
    dosyasina hicbir sey yazilmamali. Gercek ONAY_KAYDI.md'nin bir KOPYASI
    uzerinde calisir; gercek dosyaya asla dokunulmaz."""
    kopya = tmp_path / "ONAY_KAYDI.md"
    kopya.write_bytes(config.ONAY_KAYDI.read_bytes())
    once = kopya.read_bytes()
    gecici_kayit(kopya)

    for kume in ("C1", "C2"):
        with pytest.raises(PermissionError):
            split.kume_erisimi("XXUSDT", kume)
        with pytest.raises(PermissionError):  # onay=True da kosu olmadan yetmez
            split.kume_erisimi("XXUSDT", kume, onay=True)

    assert kopya.read_bytes() == once, "onaysiz cagri kopya kayit dosyasini degistirdi"


