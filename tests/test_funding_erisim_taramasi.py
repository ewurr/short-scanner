"""Funding'e yalnizca kume kapisindan erisim (F1 kapanis denetimi bulgu 10).

`funding.pozisyon_fundingi` ve `funding.funding_ortalamasi` kendilerine verilen
cercevenin nereden geldigini bilemez. `ham_funding_yukle` ciktisi verilirse
C2 ya da B grubu kayitlari KESIF hesabinda okunur (en azindan bozuk veri hatasi
olarak gorunur). Analiz kodu (events/, study/, analysis/ altindaki F2 ve
sonrasi) funding'e yalnizca `funding.funding_yukle` ile erisir; bu kural kaynak
taramasiyla korunur.
"""

from __future__ import annotations

from tarama_yardimcisi import FUNDING_KAPI_DISI_DESENI, ihlaller


def test_tarama_kapi_disi_erisimi_yakalar(tmp_path):
    ornekler = {
        "events/h2.py": "fr = funding.ham_funding_yukle(sembol)\n",
        "study/k2.py": "from data.funding import _ay_cercevesi\n",
        "study/liste.py": "anahtarlar = bv.funding_dosyalari(s)\n",
        "analysis/02_h2/calistir.py": "yol = config.ONBELLEK_DIZINI / 'funding' / sembol\n",
        "analysis/03_h2/oku.py": 'onek = "data/futures/um/monthly/fundingRate"\n',
    }
    for ad, metin in ornekler.items():
        yol = tmp_path / ad
        yol.parent.mkdir(parents=True, exist_ok=True)
        yol.write_text(metin, encoding="utf-8")
    temiz = tmp_path / "events" / "h1.py"
    temiz.write_text("fr = funding.funding_yukle(sembol, kume)\nh = funding.funding_ortalamasi(fr, t, bar, saat=24)\n", encoding="utf-8")
    izinli = tmp_path / "data" / "funding.py"
    izinli.parent.mkdir()
    izinli.write_text("def ham_funding_yukle(s): ...\n", encoding="utf-8")

    assert ihlaller(FUNDING_KAPI_DISI_DESENI, kok=tmp_path) == sorted(ornekler)


def test_depoda_funding_kapi_disi_erisim_yok():
    assert ihlaller(FUNDING_KAPI_DISI_DESENI) == [], "analiz kodu funding'e funding_yukle disindan erisiyor"
