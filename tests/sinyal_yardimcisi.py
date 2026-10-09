"""Tek karar noktasi testlerinin ortak yapilandirma ve rol girdisi (Rev.11 uygulamasi madde 4, 5).

Rev.11'den once `pozisyon.olay_karari` sinyal DEGERLERINI cagirandan aliyordu ve bu modul
hipotezin butun degerlerini 1.0 veren bir sozluk uretiyordu. Rev.11 ile kapi degerleri kendisi
hesaplar (on-kayit §5 "Pencere sinirlari", rev.11) ve `sinyal_degerleri` anahtar sozcugu
KALKMISTIR; yerine hipotezin YAPILANDIRMASI (izgaradan) ve BARIN ROLU gelir (on-kayit §5 rev.11
"Olay ya da kontrol ureten her cagri, hipotezi ve yapilandirmayi birlikte alir"; §6 rev.11
"Kontrolun ne olctugu").

Sinyal kurallarini sinamayan testler `**kontrol(hipotez)` ile cagirir: K1 rolunde kontrol
barinda hipotezin sinyal kosullari ARANMAZ (on-kayit §6 rev.11), bu yuzden duz sentetik seriler
(sabit fiyat, sabit hacim) kapidan gecmeye devam eder ve testin asil sinadigi adim (plan, cikis,
uygunluk, funding tamligi) degismez. Olay yolunu sinayan testler `**olay(hipotez, capa=...)`
kullanir ve seriyi §5'teki kosullari saglayacak sekilde kurar. Aga cikmaz.
"""

from __future__ import annotations

from data import sinyal as sinyal_modulu


def yapilandirma(hipotez: str, **degisen) -> dict:
    """Hipotezin izgarasindaki ILK yapilandirma (deterministik), `degisen` ile degistirilmis.

    Degisen deger de izgarada olmali; aksi halde `sinyal.YapilandirmaHatasi` (testin kurulus
    hatasi). Sinyal kurallarini sinamayan testler icin hangi yapilandirmanin secildigi onemsizdir.
    """
    temel = dict(sinyal_modulu.izgara(hipotez)[0])
    bilinmeyen = sorted(set(degisen) - set(temel))
    if bilinmeyen:
        raise KeyError(f"{hipotez} izgara parametresi degil: {bilinmeyen}")
    temel.update(degisen)
    return dict(sinyal_modulu.yapilandirma_dogrula(hipotez, temel))


def kontrol(hipotez: str, rol: str = "K1", **degisen) -> dict:
    """`olay_karari`nin yapilandirma, rol ve capa anahtar sozcukleri; kontrol (K1) rolu.

    Kontrol rolunde capa her zaman `None`'dir: H1'in kontrol barinda pump bari aranmaz
    (on-kayit §6 rev.11).
    """
    if rol not in ("K1", "K2"):
        raise ValueError(f"kontrol rolu K1 ya da K2 olmali: {rol!r}")
    return {"yapilandirma": yapilandirma(hipotez, **degisen), "rol": rol, "capa": None}


def olay(hipotez: str, capa=None, **degisen) -> dict:
    """`olay_karari`nin olay rolu anahtar sozcukleri. H1'de `capa` (pump bari) zorunludur."""
    return {"yapilandirma": yapilandirma(hipotez, **degisen), "rol": "olay", "capa": capa}


def ilk_ad(hipotez: str) -> str:
    """Hipotezin ilk sinyal deger adi (geriye donuk uyumluluk icin korundu)."""
    return sinyal_modulu.deger_adlari(hipotez)[0]
