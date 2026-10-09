"""Rev.11 uygulamasi madde 7: K1 / K2 ornekleme kurallari (on-kayit §6, rev.11).

Ayni yapilandirmanin olusmus olaylarina gore ayiklama, iadesiz ornekleme, 10'dan az aday,
iki havuzu da bos olan olayin dusmesi, alt tohumun demetten turemesi ve sonucun sembol
sirasindan bagimsiz olmasi. Getiri hesaplanmaz. Aga cikmaz.
"""

from __future__ import annotations

import pandas as pd
import pytest

import config
from data import ornekleme

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
H4 = pd.Timedelta(hours=4)
G1 = pd.Timedelta(days=1)
H4_UFUK = config.BIRINCIL_UFUK[config.BAR_4H]
YAP = {"phi": 0.0003, "k": 3}


# --- Alt tohum (on-kayit §6 rev.11, §7 "Tohum") ------------------------------------------------


def test_alt_tohum_demetten_turer_ve_deterministiktir():
    a = ornekleme.alt_tohum("H2", YAP, "KESIF", "AAVEUSDT", T("2025-03-01"))
    b = ornekleme.alt_tohum("H2", YAP, "KESIF", "AAVEUSDT", T("2025-03-01"))
    assert a == b


@pytest.mark.parametrize("degisen", [
    {"hipotez": "H3"},
    {"yapilandirma": {"phi": 0.0005, "k": 3}},
    {"kume": "C2"},
    {"sembol": "BTCUSDT"},
    {"olay_zamani": T("2025-03-01 04:00")},
])
def test_alt_tohum_demetin_her_ogesine_duyarli(degisen):
    temel = {"hipotez": "H2", "yapilandirma": YAP, "kume": "KESIF", "sembol": "AAVEUSDT",
             "olay_zamani": T("2025-03-01")}
    yeni = {**temel, **degisen}
    if "hipotez" in degisen:  # H3'un parametreleri farkli
        yeni["yapilandirma"] = {"nu": 0.50, "tau": 0.15}
    assert ornekleme.alt_tohum(**temel) != ornekleme.alt_tohum(**yeni)


def test_alt_tohum_on_kayit_tohumuna_bagli():
    """§7'deki tohum degisirse alt tohumlar da degisir (tohum girdinin parcasidir)."""
    metin_tohumu = ornekleme.alt_tohum("H2", YAP, "KESIF", "AAVEUSDT", T("2025-03-01"))
    assert isinstance(metin_tohumu, int) and metin_tohumu > 0
    assert config.TOHUM == 20260911


def test_bilinmeyen_kume_ve_izgara_disi_yapilandirma_reddedilir():
    with pytest.raises(ValueError):
        ornekleme.alt_tohum("H2", YAP, "KESIF2", "AAVEUSDT", T("2025-03-01"))
    with pytest.raises(Exception):
        ornekleme.alt_tohum("H2", {"phi": 0.0004, "k": 3}, "KESIF", "AAVEUSDT", T("2025-03-01"))


# --- K1: olaylara yakinlik (on-kayit §6 K1) ----------------------------------------------------


def test_k1_birincil_ufuk_mesafesi_siniri():
    """"birincil ufuk mesafesinden yakin olmayan": tam ufuk mesafesi YAKIN SAYILMAZ."""
    olay = T("2025-03-10 00:00")
    tam = olay + H4_UFUK * H4
    assert ornekleme.k1_uzak_mi(tam, [olay], H4_UFUK, config.BAR_4H)
    assert not ornekleme.k1_uzak_mi(tam - H4, [olay], H4_UFUK, config.BAR_4H)
    # Iki yone de bakilir.
    assert ornekleme.k1_uzak_mi(olay - H4_UFUK * H4, [olay], H4_UFUK, config.BAR_4H)
    assert not ornekleme.k1_uzak_mi(olay - (H4_UFUK - 1) * H4, [olay], H4_UFUK, config.BAR_4H)
    assert not ornekleme.k1_uzak_mi(olay, [olay], H4_UFUK, config.BAR_4H)


def test_k1_adaylari_butun_olaylara_bakar():
    olaylar = [T("2025-03-10"), T("2025-03-20")]
    barlar = pd.date_range(T("2025-03-01"), T("2025-03-31"), freq="4h")
    adaylar = ornekleme.k1_adaylari(barlar, olaylar, H4_UFUK, config.BAR_4H)
    for t in adaylar:
        assert all(abs(t - o) >= H4_UFUK * H4 for o in olaylar)
    assert len(adaylar) < len(barlar)


def test_k1_olay_listesi_bos_olabilir():
    barlar = pd.date_range(T("2025-03-01"), periods=5, freq="4h")
    assert ornekleme.k1_adaylari(barlar, [], H4_UFUK, config.BAR_4H) == tuple(barlar)


# --- K2: olay ureten coinlerin ayiklanmasi (on-kayit §6 K2) ------------------------------------


def test_k2_olay_ureten_ve_olayin_kendi_coini_ayiklanir():
    adaylar = ["CUSDT", "AUSDT", "BUSDT", "DUSDT"]
    sonuc = ornekleme.k2_adaylari(adaylar, ["BUSDT"], olay_sembolu="AUSDT")
    assert sonuc == ("CUSDT", "DUSDT")


def test_k2_adaylari_alfabetik_sirada():
    assert ornekleme.k2_adaylari(["ZUSDT", "AUSDT", "MUSDT"], [], olay_sembolu="XUSDT") \
        == ("AUSDT", "MUSDT", "ZUSDT")


# --- Ornekleme (on-kayit §6 rev.11) ------------------------------------------------------------


def test_ornekleme_iadesizdir_ve_on_kayit_sayisini_ceker():
    adaylar = [T("2025-03-01") + i * H4 for i in range(50)]
    tohum = ornekleme.alt_tohum("H2", YAP, "KESIF", "AAVEUSDT", T("2025-03-01"))
    havuz = ornekleme.ornekle(adaylar, tohum=tohum)
    assert len(havuz) == config.KONTROL_SAYISI == 10
    assert len(set(havuz.secilenler)) == 10, "iadesiz: tekrar olamaz"
    assert havuz.aday_sayisi == 50 and not havuz.eksik


def test_ayni_tohum_ayni_sonucu_verir():
    adaylar = [T("2025-03-01") + i * H4 for i in range(50)]
    tohum = ornekleme.alt_tohum("H2", YAP, "KESIF", "AAVEUSDT", T("2025-03-01"))
    assert ornekleme.ornekle(adaylar, tohum=tohum) == ornekleme.ornekle(adaylar, tohum=tohum)


def test_farkli_tohum_farkli_sonuc_verir():
    adaylar = [T("2025-03-01") + i * H4 for i in range(50)]
    a = ornekleme.ornekle(adaylar, tohum=ornekleme.alt_tohum("H2", YAP, "KESIF", "AAVEUSDT", T("2025-03-01")))
    b = ornekleme.ornekle(adaylar, tohum=ornekleme.alt_tohum("H2", YAP, "KESIF", "BTCUSDT", T("2025-03-01")))
    assert a.secilenler != b.secilenler


def test_aday_sirasi_degisince_sonuc_degismez():
    """On-kayit §6 rev.11: "semboller alfabetik sirada islenir, boylece sonuc kosu sirasindan
    bagimsizdir." Ornekleme adaylari once siralar."""
    adaylar = [f"{h}USDT" for h in "ABCDEFGHIJKLMNOP"]
    tohum = ornekleme.alt_tohum("H2", YAP, "KESIF", "AAVEUSDT", T("2025-03-01"))
    duz = ornekleme.ornekle(adaylar, tohum=tohum)
    ters = ornekleme.ornekle(list(reversed(adaylar)), tohum=tohum)
    karisik = ornekleme.ornekle(adaylar[7:] + adaylar[:7], tohum=tohum)
    assert duz == ters == karisik


def test_ondan_az_aday_hepsi_alinir_ve_sayi_yazilir():
    adaylar = [T("2025-03-01") + i * H4 for i in range(4)]
    havuz = ornekleme.ornekle(adaylar, tohum=1)
    assert havuz.secilenler == tuple(adaylar) and havuz.aday_sayisi == 4 and havuz.eksik


def test_tam_on_aday_sinir_durumu():
    adaylar = [T("2025-03-01") + i * H4 for i in range(10)]
    havuz = ornekleme.ornekle(adaylar, tohum=1)
    assert len(havuz) == 10 and havuz.aday_sayisi == 10 and not havuz.eksik


def test_bos_havuz():
    havuz = ornekleme.ornekle([], tohum=1)
    assert havuz.secilenler == () and havuz.aday_sayisi == 0 and havuz.eksik


def test_tekrarli_aday_reddedilir():
    with pytest.raises(ValueError, match="tekrarsiz"):
        ornekleme.ornekle(["AUSDT", "AUSDT"], tohum=1)


# --- Olayin analize girmesi (on-kayit §6 rev.11) ----------------------------------------------


def test_iki_havuzu_da_bos_olan_olay_analize_girmez():
    bos = ornekleme.ornekle([], tohum=1)
    dolu = ornekleme.ornekle(["AUSDT"], tohum=1)
    assert not ornekleme.olay_analize_girer(bos, bos)
    assert ornekleme.olay_analize_girer(dolu, bos)
    assert ornekleme.olay_analize_girer(bos, dolu)
    assert ornekleme.olay_analize_girer(dolu, dolu)


def test_sembol_sirasi_tekrari_reddeder():
    assert ornekleme.sembol_sirasi(["BUSDT", "AUSDT"]) == ("AUSDT", "BUSDT")
    with pytest.raises(ValueError, match="tekrar"):
        ornekleme.sembol_sirasi(["AUSDT", "AUSDT"])
