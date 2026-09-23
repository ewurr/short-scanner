"""Denetci bulgusu D-C7: `ham_settled_mumlari_yukle` erisim taramasinda.

On-kayit §2 "Karantina kuralinin kaldirilmasi" (rev.8): "SETTLED bilgisi yalnizca denetim
amaciyla tutulur. Fiyat ve hacim icin tek kaynak ana seridir: SETTLED dosyalari hicbir hesaba
girmez." Analiz kodu (IZINLI_ALTLAR disi) SETTLED yukleyicisine ve kume korumasiz ham
yukleyicilere erisemez. Aga cikmaz.
"""

from __future__ import annotations

from tarama_yardimcisi import HAM_ERISIM_DESENI, ihlaller


def test_desen_settled_yukleyicisini_yakalar(tmp_path):
    ornekler = {
        "events/h1.py": "m = klines.ham_settled_mumlari_yukle(dizin, '4h')\n",
        "study/k1.py": "from data.klines import ham_settled_mumlari_yukle as oku\n",
        "study/k2.py": "d = klines.settled_dizinleri(s, dizinler)\n",
        "study/k3.py": "ek = s + config.SETTLED_SONEKI\n",
        "analysis/02_h2/calistir.py": "m = klines.ham_mumlari_yukle(s, bar)\n",
        "analysis/03_h3/calistir.py": "f = funding.ham_funding_yukle(s)\n",
    }
    for ad, metin in ornekler.items():
        yol = tmp_path / ad
        yol.parent.mkdir(parents=True, exist_ok=True)
        yol.write_text(metin, encoding="utf-8")
    temiz = tmp_path / "events" / "h2.py"
    temiz.write_text("m = klines.mumlari_yukle(s, bar, 'KESIF')\n", encoding="utf-8")
    izinli = tmp_path / "analysis" / "00_veri_denetimi" / "calistir.py"
    izinli.parent.mkdir(parents=True)
    izinli.write_text("m = klines.ham_settled_mumlari_yukle(dizin, '4h')\n", encoding="utf-8")
    assert ihlaller(HAM_ERISIM_DESENI, kok=tmp_path) == sorted(ornekler)


def test_depoda_settled_ve_ham_erisim_yok():
    assert ihlaller(HAM_ERISIM_DESENI) == [], "analiz kodu SETTLED ya da kume korumasiz yukleyiciye erisiyor"
