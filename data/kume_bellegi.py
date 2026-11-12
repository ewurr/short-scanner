"""Kapinin bellek onbellegi: (sembol, kume, donem) basina bir kez yuklenen veri (on-kayit §3 rev.13).

On-kayit §3: "bellekte tutulan her kopya icin erisim denetimi kopyanin her okunusunda yeniden uygulanir, ve
onay kosusunun acilisi ile kapanisi bu kopyalari gecersiz kilar"; "kumeye gore kesilmis veri diske yazilmaz".
  - Tek okuma yolu `getir`dir ve erisim denetimi ISABET DAHIL her aramada, aramadan once calisir. Yalniz
    iskalamada calissaydi ilk cagridan sonra onay denetimi devre disi kalirdi (kuru okuma §6.5, risk 1).
  - Anahtar kume adini tasir: KESIF icin yuklenen veri C1 ya da C2 sorgusuna donmez, tersi de.
  - Yalniz bellektedir; bu modul diske yazmaz.
  - `split.onay_kosusu` acilis ve kapanista `temizle` cagirir.
  - Donen cerceveler kopyadir: cagiranin degisikligi bellekteki girdiye gecmez.

Sinir `AZAMI_GIRDI` (LRU, RESULTS §14.40). Modul analiz kodunda taramayla yasaktir
(`tests/tarama_yardimcisi.ONBELLEK_DESENI`). Saf hesap degildir; ag ve disk erisimi yapmaz.
"""

from __future__ import annotations

import threading
from collections import OrderedDict

AZAMI_GIRDI = 8

_BELLEK: OrderedDict = OrderedDict()
_KILIT = threading.Lock()


def getir(anahtar: tuple, denetim, yukle) -> tuple:
    """Erisim denetiminden gecer, sonra girdiyi bellekten ya da `yukle`den alir.

    `denetim`: argumansiz, izin yoksa hata firlatan fonksiyon; her cagrida calisir. `yukle`: argumansiz, cerceve
    demeti doner; yalnizca iskalamada calisir ve hata verirse bellege bir sey yazilmaz. Doner: kopyalar."""
    denetim()
    with _KILIT:
        deger = _BELLEK.get(anahtar)
        if deger is not None:
            _BELLEK.move_to_end(anahtar)
    if deger is None:
        deger = yukle()
        with _KILIT:
            _BELLEK[anahtar] = deger
            _BELLEK.move_to_end(anahtar)
            while len(_BELLEK) > AZAMI_GIRDI:
                _BELLEK.popitem(last=False)
    return tuple(cerceve.copy() for cerceve in deger)


# Donem isareti (performans 2b-2, plan v3 G11; RESULTS §14.49): kesif ve onay kosularinin acilisi ve kapanisi `temizle`
# cagirir ve her cagri sayaci artirir. Kapinin seri nesnesi (`pozisyon.KapiSerisi`) kuruldugu isareti tasir; isaret
# degismisse okuma reddedilir. Seri onbellegi de `temizle`de dusurulur (`_TEMIZLEYICILER`; kapi modulu kaydeder).
_DONEM_ISARETI = [0]
_TEMIZLEYICILER: list = []


def temizle() -> None:
    with _KILIT:
        _BELLEK.clear()
        _DONEM_ISARETI[0] += 1
    for temizleyici in tuple(_TEMIZLEYICILER):
        temizleyici()


def donem_isareti() -> int:
    """Donem isaretinin bugunku degeri: `temizle` her cagrildiginda artar (kosu acilisi ve kapanisi)."""
    with _KILIT:
        return _DONEM_ISARETI[0]


def temizleyici_ekle(temizleyici) -> None:
    """`temizle` ile birlikte cagrilacak argumansiz bir fonksiyon (ör. kapinin seri onbellegi). Ayni fonksiyon bir kez."""
    if temizleyici not in _TEMIZLEYICILER:
        _TEMIZLEYICILER.append(temizleyici)


def girdi_sayisi() -> int:
    with _KILIT:
        return len(_BELLEK)
