"""Test istatistigi, `r` ve p-degeri (on-kayit §7, rev.11).

On-kayit §7:
  - "Test istatistigi: `ortalama(olay net getirisi) - ortalama(kontrol net getirisi)`. Kontrol
    ortalamasi OLAY BASINA agirliklandirilir (rev.13): once her olayin kontrol havuzunun
    ortalamasi alinir, sonra bu ortalamalarin olaylar arasindaki ortalamasi alinir; havuzlar tek
    bir kumede BIRLESTIRILMEZ. Gerekce: asagidaki yeniden ornekleme her tekrarda olay basina bir
    kontrol ceker, dolayisiyla her olay dagilimda esit agirlik tasir. Havuzlar birlestirilirse
    gozlenen istatistik ile yeniden ornekleme dagilimi ayni olcekte olmaz ve kucuk havuzlu
    olaylar iki tarafta farkli agirliklanir. Bu tanim, §8 ve §9'da anilan 'K2 farki' icin de
    gecerlidir; K1 farki ayni bicimde hesaplanir."
  - "p-degeri: 10.000 tekrarli eslestirilmis yeniden ornekleme. Her tekrarda her olayin kontrol
    havuzundan bir kontrol cekilir ve o tekrarin test istatistigi hesaplanir. `r`, test
    istatistiginin sifiri asmadigi (`<= 0`) tekrarlarin sayisidir (rev.11).
    `p = (r + 1) / (10000 + 1)`, tek yonlu (olay short'u daha iyi). Cekim iadelidir ve §7'deki
    tohumdan turetilir."
  - "Bu yordamin siniri (rev.11). Bu bir bootstrap p-degeridir, permutasyon testi degildir:
    belirsizlik yalnizca kontrol seciminden gelir, olay kumesi her tekrarda sabittir. Dolayisiyla
    p-degeri, olaylarin kendi ornekleme degiskenligini hesaba katmaz ve bu yoneyle iyimser
    olabilir. Yordam on-kayitta yazildigi bicimiyle korunmustur; siniri F2 ve F3 raporlarinda bu
    cumleyle birlikte anilir."

Bu modul SAFTIR ve getiri HESAPLAMAZ: net getirileri sayi olarak alir. Hicbir veriye
uygulanmamistir; F2'ye kadar yalnizca testlerde sentetik girdilerle kosulur (Rev.11 uygulamasi
madde 9).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

import config

# On-kayit §7 "Bu yordamin siniri" (rev.11): raporlarda p-degeriyle birlikte anilacak cumle.
# F2/F3 raporlari bu metni buradan okur, yeniden yazmaz.
YORDAMIN_SINIRI = (
    "Bu bir bootstrap p-degeridir, permutasyon testi degildir: belirsizlik yalnizca kontrol "
    "seciminden gelir, olay kumesi her tekrarda sabittir. Dolayisiyla p-degeri, olaylarin kendi "
    "ornekleme degiskenligini hesaba katmaz ve bu yoneyle iyimser olabilir."
)


@dataclass(frozen=True)
class PSonucu:
    """`r`, p ve yordamin girdileri. `r` on-kayit §7 rev.11 tanimidir."""

    r: int
    p: float
    tekrar: int
    olay_sayisi: int
    tohum: int


def test_istatistigi(olay_getirileri, kontrol_havuzlari) -> float:
    """`ortalama(olay net getirisi) - ortalama(kontrol net getirisi)`, kontrol tarafi OLAY BASINA
    agirliklandirilmis (on-kayit §7, rev.13). Saf.

    `kontrol_havuzlari`: her olay icin O OLAYIN havuzundaki kontrollerin net getirileri, olaylarla
    AYNI SIRADA. Havuzlar birlestirilmez: once her havuzun ortalamasi, sonra bu ortalamalarin
    olaylar arasindaki ortalamasi alinir. Rev.13'ten once fonksiyon duz bir kontrol getirisi
    listesi aliyordu ve havuzlari fiilen birlestiriyordu; o tanimda 1 kontrollu bir olay ile 10
    kontrollu bir olay kontrol tarafina farkli agirlik tasirdi, oysa `yeniden_ornekle` her olaydan
    BIR kontrol cektigi icin dagilimda ikisi de esit agirliktadir.

    Bos havuzlu olay buraya verilmez (on-kayit §6 rev.11: her iki havuzu da bos olan olay analize
    girmez; teste giren her havuzda en az bir kontrol vardir).
    """
    olay = _getiriler(olay_getirileri, "olay_getirileri")
    havuzlar = _havuzlar(kontrol_havuzlari, olay)
    kontrol_ortalamalari = np.array([float(h.mean()) for h in havuzlar], dtype=float)
    return float(olay.mean() - kontrol_ortalamalari.mean())


def _havuzlar(kontrol_havuzlari, olay) -> list:
    """Olay basina kontrol havuzlarini dogrular (on-kayit §7 rev.13). Tek yer: `test_istatistigi`
    ve `yeniden_ornekle` ayni denetimlerden gecer."""
    havuzlar = [_getiriler(h, f"kontrol_havuzlari[{i}]") for i, h in enumerate(kontrol_havuzlari)]
    if len(olay) == 0:
        raise ValueError("test istatistigi bos olay kumesinde tanimsiz (olay getirisi gerekli).")
    if len(havuzlar) != len(olay):
        raise ValueError(f"her olay icin bir kontrol havuzu gerekli: {len(olay)} olay, {len(havuzlar)} havuz.")
    bos = [i for i, h in enumerate(havuzlar) if h.size == 0]
    if bos:
        raise ValueError(f"kontrol havuzu bos olan olay teste giremez (on-kayit §6 rev.11): {bos}.")
    return havuzlar


def _getiriler(degerler, ad: str) -> np.ndarray:
    dizi = np.asarray(list(degerler), dtype=float)
    if dizi.ndim != 1:
        raise ValueError(f"{ad} tek boyutlu olmali.")
    if dizi.size and not np.isfinite(dizi).all():
        raise ValueError(f"{ad} sonlu olmayan deger tasiyor; net getiri sonlu bir sayi olmali.")
    return dizi


def yeniden_ornekle(olay_getirileri, kontrol_havuzlari, *, tekrar: int = None, tohum: int = None) -> PSonucu:
    """Eslestirilmis yeniden ornekleme ile `r` ve p-degeri (on-kayit §7, rev.11). Saf.

    `olay_getirileri`: olaylarin net getirileri. `kontrol_havuzlari`: her olay icin o olayin
    kontrol havuzundaki kontrollerin net getirileri (ayni sirada, bos olamaz; bos havuzlu olay
    on-kayit §6 rev.11 geregi analize girmez ve buraya verilmez).

    Her tekrarda her olay icin havuzundan BIR kontrol cekilir (cekim iadelidir: tekrarlar
    birbirinden bagimsizdir ve ayni kontrol birden fazla tekrarda secilebilir), o tekrarin test
    istatistigi hesaplanir. `r` = istatistigin sifiri asmadigi (`<= 0`) tekrar sayisi;
    `p = (r + 1) / (tekrar + 1)`, tek yonlu.

    `tekrar` ve `tohum` varsayilan olarak on-kayit degerleridir (`config.PERMUTASYON_TEKRAR`,
    `config.TOHUM`); baska deger verilemez.
    """
    n_tekrar = config.PERMUTASYON_TEKRAR if tekrar is None else int(tekrar)
    kullanilan_tohum = config.TOHUM if tohum is None else int(tohum)
    if n_tekrar != config.PERMUTASYON_TEKRAR:
        raise ValueError(f"tekrar on-kayit §7 degeri olmali ({config.PERMUTASYON_TEKRAR}); verilen {n_tekrar}.")
    if kullanilan_tohum != config.TOHUM:
        raise ValueError(f"tohum on-kayit §7 degeri olmali ({config.TOHUM}); verilen {kullanilan_tohum}.")

    olay = _getiriler(olay_getirileri, "olay_getirileri")
    havuzlar = _havuzlar(kontrol_havuzlari, olay)

    uretec = np.random.default_rng(kullanilan_tohum)
    olay_ortalamasi = float(olay.mean())
    boyutlar = np.array([h.size for h in havuzlar], dtype=np.int64)
    yigin = np.concatenate(havuzlar) if havuzlar else np.empty(0)
    baslangic = np.concatenate([[0], np.cumsum(boyutlar)[:-1]]).astype(np.int64)

    r = 0
    for _ in range(n_tekrar):
        # Her olaydan BIR kontrol cekilir; cekilenlerin ortalamasi olay basina esit agirliklidir,
        # yani `test_istatistigi`nin rev.13 tanimiyla ayni olcektedir (on-kayit §7 gerekcesi).
        secim = baslangic + uretec.integers(0, boyutlar)
        istatistik = olay_ortalamasi - float(yigin[secim].mean())
        if istatistik <= 0:
            r += 1
    p = (r + 1) / (n_tekrar + 1)
    return PSonucu(r=r, p=float(p), tekrar=n_tekrar, olay_sayisi=int(olay.size), tohum=kullanilan_tohum)
