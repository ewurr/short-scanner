"""Skaler referansin DAYANDIGI kural fonksiyonlarinin sabitlenmesi (performans 2b-0; denetci D-B1, RESULTS §14.44).

Neden: `data/_skaler_referans.py` karar yolunun kurallarini 4e63037'den kopyalar, ama veriyi ve bazi yardimcilari
kopyalamaz, `data/`daki asillarindan alir (`ref.DAYANILAN`). Bu asillardan biri degisirse kapi ile referans BIRLIKTE
kayar ve esitlik testleri farki goremez. Bu dosya, dayanilan adlardan ve `_karar_verisi`nin gecisli cagri grafiginden
ulasilan her kural tanimini kaynak metniyle (SHA256) sabitler.

Yontem:
  - Grafik AST ile cikarilir (`_kapanis`): bir tanimin govdesinde yuklenen her ad, ayni modulun ust duzey bir tanimina
    ya da bir `data` modulu takma adi (`pencere_modulu.x`, `bv.x`, `from data.pencere import x`) uzerinden baska bir
    modulun ust duzey tanimina cozulurse kenardir. Fonksiyon govdesindeki yerel ice aktarmalar da sayilir.
  - Kokler: `ref.DAYANILAN`daki butun adlar (`config` haric: on-kayit sabitleri kendi degismezlik testleriyle korunur).
  - `HARIC` adlarda grafik DURUR: veri yukleyicileri, erisim denetimleri, bellek onbellegi. Guvenlik duzeltmeleri
    bunlari degistirebilmeli; kural degil, erisim yoludurlar. Her birinin gerekcesi yanindadir.
  - Ulasilan her ad ya `SABIT`te (sabitli) ya `HARIC`te olmali; siniflandirilmamis yeni bir ad testi kirar.
  - Kaynak metni: tanimin AST araligi (dekoratorler dahil), dosya metninden, satir sonlari LF. `inspect.getsource` ile
    ayni metindir, ama monkeypatch'ten etkilenmez (`tests/conftest.py` `pozisyon._kayitlar`i ve `_veri_yukle`yi her
    testte sarar). Fonksiyonlar, siniflar VE sabitler ayni yolla sabitlenir: sabitin atama satiri (deger ifadesi dahil).
    Sabitin DEGERI sabitlenmez: degerler `config`ten gelir ya da surece ozgudur (`_PLAN_GIZLI = object()`).

Sinir: statik grafik dinamik cagrilari (`getattr`, nesne metotlari, `config` uzerinden gelen degerler) gormez.
Kod yazilmaz; SABIT guncellenmeden once referans yeni bir kopyayla dondurulmalidir (asagidaki hata mesaji).
"""

from __future__ import annotations

import ast
import hashlib

from data import _skaler_referans as ref
from tarama_yardimcisi import KOK

# Grafigin durdugu adlar: kural degil, erisim yolu. (ad -> gerekce)
HARIC = {
    "data.pozisyon._veri_yukle": "veri yukleyicisi (kume korumali `mumlari_yukle` / `funding_yukle`)",
    "data.pozisyon._erisim_denetimi": "erisim denetimi (`split.onay_erisimi_denetle`)",
    "data.kume_bellegi.getir": "bellek onbellegi; her okumada erisim denetimi calistirir",
    "data.universe.evren_yukle": "tablo yukleyicisi (kilitli `universe.csv`)",
    "data.split.split_oku": "tablo yukleyicisi (kilitli `split.csv`)",
    "data.split.onay_baglami_dogrula": "erisim denetimi (onay kosusu baglami)",
    "data.split.kesif_baglami_dogrula": "erisim denetimi (kesif kosusu baglami)",
}

# Sabitlenen kural tanimlari (ad -> kaynak metninin SHA256'si, LF). Kaynak commit: performans 2b-0 tabani (33825ee).
SABIT = {
    "data.binance_vision.MUM_SUTUNLARI": "75e9a583706cb059b86be269f769322db5f1f4b0cee2fb8b26db892eaf6986e7",
    "data.funding._zaman_dizisi": "836592289afc03734307183ba6d1b372565e0ca37d080a9e58b9306394a245fb",
    "data.klines.GUNLUK_BAR_SAYISI": "d9ef201dff2647d73222147b1d3aff50842b0f2deaafae50592823868a4cd184",
    "data.klines.GUNLUK_IZGARA_ADIMI": "9ec8aae90fd161eb5498ede661b241dddb4df9e8cf4a9ed4e88c30253162a79c",
    "data.klines.HUCRE_SUTUNLARI": "81799c9351b6e54ed994ffb2c230f8bb904109a17177842f69e4c6e0c7f0dd98",
    "data.klines.donem_kes": "bedad54d2e159d97e9c3c26837d0c54b36c1dc61eb394291121949eebc2757ed",
    "data.klines.gunluge_cevir": "788c4e34ae694476102e09361202f40f9b48fa57f4d5f485a6599162c5b3000b",
    "data.klines.hucreleri_tam_mi": "466bb842beebd636be9e57088a81a37b43cee4af0ce0a0f4523996199c52bc5e",
    "data.pencere.ADIMLAR": "4af80d4d8def14587ed545a16bb0c2f002d4d3c79ab5f6bf45b2b0316cf25ce3",
    "data.pencere.ADIM_4H": "af5678e82356521f8c4f1751e4a85c7d02959b90aae424e9ad762823b1b15d11",
    "data.pencere.CikisSonucu": "ab4784806d80a62c669a62c1c225de9dcc5ec1a10cb13e9eae9a79045746e40a",
    "data.pencere.DonemDisiSinyal": "cc564872bddf74d66ebb55f1a5d65f91ba186ac73f3284d7c0c6ce1adeb96c95",
    "data.pencere.GirisBariYok": "c605d654eb52c70e99c667d778c2ba9f546dcd5e04824b46656fc1abaae22db8",
    "data.pencere.HipotezUfuklari": "1e72e3d49a20ac5d9b98c190d4015a5e3ef317e948c928aee35914cb729d767c",
    "data.pencere.IleriKaymaSiniriHatasi": "f7dc0487c734281f55edc3808b6deb3f8bfd894ea77a808f0adae5f6768a6b38",
    "data.pencere.KumeSiniriHatasi": "8244cd175f58fa06c3defbaadbaddcd57fbf03b474c9da96dc191d7a048bb462",
    "data.pencere.ODEME_TOLERANSI": "a9363369ae7593ed6600e7c9c7e060722e65412074359d0a1b069222b5132f62",
    "data.pencere.OlayOlusmaz": "7f659e4a0b40e5eb38e9eccb5a514ca8d0567ea9c2916b1eb6203305e8b9e20c",
    "data.pencere.PozisyonPlani": "e480f5ecbe974189da39cf2412d94edc51f4943e41ac199e19ab08fea3f1af65",
    "data.pencere.VeriHatasi": "564dc5b5caceb483bbe0146ed24e998aff3d64d81b5441175bd2570b8202b344",
    "data.pencere.ZAMAN_TOLERANSI": "0b663ba3de56314b6ab1bd6b894ceea4a98d69f22c97bc5b70dd9217b6353366",
    "data.pencere.ZamanDizisiHatasi": "787e383b69bd023c247fc29d74c258fa7348df890abce84296e4b04f0ac45caa",
    "data.pencere._PLAN_GIZLI": "0d3a7a336c447b2aa314114b811b10414087daec29b0a99f43905cec96bd85b1",
    "data.pencere._plan_imzasi": "c6c80116bdaa618ab505fe71ba9d56210bf193ebc8c107b9f471f4cb9179e031",
    "data.pencere._sonuc": "67e64e7625509f519a4c23dc7fab6fffa17ec382693b82f2d2c912a82c85bab4",
    "data.pencere._tolerans_pd": "4530bb245bc48b30c698ad680e591a8c6b738d33fe9b260f1dd3adead3db360c",
    "data.pencere._zaman_dizisi_dogrula": "b0c3e6882431e8f58a8f7d98c450b796889749886bca748b6d6f7be979bdb7d0",
    "data.pencere.adim": "54e1ab7b0e217eeb576dbd15d7f5bd9b3f0d4ac6d71f92102f5eed02249c6b54",
    "data.pencere.ayni_an": "f607803d598d10898c4573871f21eb8ce2b65c387a27d4c63beccd13ab697a38",
    "data.pencere.ayni_an_basi": "de4687ff743fd5d6962c5dc4873f714e29498fee5a5aee77cb95e23c4c0ba248",
    "data.pencere.ayni_an_sonu": "101d7aae68f8137f1b21914dacf5c198e656d73ff48006954e9b96bf1d262d05",
    "data.pencere.ayni_ya_da_once": "584cee254bd9e7a0757e219173ed39e6a3b59eda5681bdb1354d7f585d1f3815",
    "data.pencere.ayni_ya_da_sonra": "847b0c438465a9292732c7785164663513d1206d886fd583553add4147769d55",
    "data.pencere.donem_ici_4h_maskesi": "02827d67874fda99be8abe5b5950ffb3665b89995534c32cfbc702f643c80be1",
    "data.pencere.once": "60c193d4c9cffd1a844bdf9ff695082ad7a9ef84fe586035197c74ff6e0cba5c",
    "data.pencere.plan_dogrula": "869006707457bbc4bcc88ee0f140632d074e77589bd02beac9ba829833378dae",
    "data.pencere.sonra": "45e485d19327846a9b696d91121df9a722086d118a820bf1662d7625c5bb3547",
    "data.pencere.tolerans": "650d4a3bb88c0c6ba39c2da0e3aed556e30b15b73db98898f6f253cabe80a709",
    "data.pencere.utc_zamani": "78fd50693c2e4db2aa8794e2342f4a83b9caec5b7e1839091ac7f71375a1ae03",
    "data.pozisyon.FundingTamDegil": "a9a880520fd052e436e372d94471ce584b905d5b3a1faa96b14bcb3cf615d6ec",
    "data.pozisyon.OnaylanmisPozisyon": "7f81f29da96048c96eb11ca53ca4a3e05d03b6ddea3665e6a6c40272c2526f19",
    "data.pozisyon.SinyalBariYok": "344aa69c72fd5eb9c5af8a0e0ca75dd61824c84395e99e41167ffb8aea6b9053",
    "data.pozisyon.SinyalKosuluSaglanmadi": "8cf7357aef411e9cb95c0eb94626cbcd63746086ab4ff8e24356cf0ef9c825c3",
    "data.pozisyon.SinyalPenceresiTamDegil": "9cf9887bf3460800b41a3e2a9fc4d2f6fbfebeb39b8f078615548f56a6a4e825",
    "data.pozisyon.UygunDegil": "fe600ff2ec1973555491c04e62b55a8136cc0ae41416e3a1d3f9e923c470f973",
    "data.pozisyon._DonemSiniri": "82b0e83449555e9ec34266f74e788ee209fd9da3de6ffe1b268fcaaa4b2e919c",
    "data.pozisyon._PlanSerisi": "c41843c998b6cb973164c675f21b420d62b6348744495acebd982f66b301673e",
    "data.pozisyon._karar_girdisi": "b0b226e0cebb2aa78cca7ef89b4a1da79f62d534b1f60c58594c0dc858c19470",
    "data.pozisyon._karar_verisi": "7a60dc36412103345b60fbbea9d4e3b5017d372b425400a272d673f267b7b419",
    "data.pozisyon._karar_verisi_kur": "a944ebfe77c5d5836f594392d890ad5add44ad61d1d4b1121980377df90bf8a5",
    "data.pozisyon._kayitlar": "32f58a97cd3370332c71390c83d41f58837c8026a27f7544ad2bc279fad5e2e5",
    "data.pozisyon._kume_verisi": "db5a2fdf63c7515bea1b3b25c9f37cc546e9ebbd592f1a19dabf6fce8d9612e3",
    "data.pozisyon._kume_verisi_yukle": "e5fae218146d3d9d7fe0696e22385aba1ec8682c52bd8c53828ca071b74839e1",
    "data.pozisyon._tam_hucreli_barlar": "ea5921f95f01168100a6b8f208bdeecd061dd73a00e8e73990f2bc8533b9c69d",
    "data.pozisyon.donem_kaydi": "670179f48045894e0c0d1fc8e2e871a046c0b1f1c365ff213e564919fdbf78a9",
    "data.pozisyon.grup_dogrula": "32010689969f491ea027a25f4ffb6c0d97e9fd938c20141c3d13ee1f7d1a6280",
    "data.pozisyon.kume_sinirlari": "72a55ca8150c8d061bd5f1f7332943f441e855acaca213d11188345ea67d2590",
    "data.sinyal.TepePenceresiKurulamaz": "d5a6a4a5f007141164a9822eeb4d996ab9a5a64568735ae19a4c22d70baa2124",
    "data.sinyal.YapilandirmaHatasi": "343efa79f835daf46d03e05f85463145e0fcfd013e613899ffdb4684177ddfe4",
    "data.split.kume_araligi": "dc42cf355bd2ac14556765e7da947d467edd333e90e79247fbfbfeea456960c6",
    "data.split.kume_tanimi": "027a10ce011e5f443dc0048a7d1049d15b59516707eca1d82ceaaa42ae15584b",
}


def _modul_yolu(modul: str):
    return KOK / (modul.replace(".", "/") + ".py")


_BILGI: dict = {}


def _bilgi(modul: str):
    """(ust duzey tanimlar: ad -> dugum, takma adlar: ad -> modul, dogrudan adlar: ad -> (modul, ad), metin)."""
    if modul not in _BILGI:
        metin = _modul_yolu(modul).read_text(encoding="utf-8").replace("\r\n", "\n")
        agac = ast.parse(metin)
        tanim, takma, adlar = {}, {}, {}
        for d in agac.body:
            if isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                tanim[d.name] = d
            elif isinstance(d, (ast.Assign, ast.AnnAssign)):
                for h in (d.targets if isinstance(d, ast.Assign) else [d.target]):
                    if isinstance(h, ast.Name):
                        tanim[h.id] = d
        for x in ast.walk(agac):
            if isinstance(x, ast.ImportFrom) and x.module == "data":
                for a in x.names:
                    takma[a.asname or a.name] = f"data.{a.name}"
            elif isinstance(x, ast.ImportFrom) and x.module and x.module.startswith("data."):
                for a in x.names:
                    adlar[a.asname or a.name] = (x.module, a.name)
        _BILGI[modul] = (tanim, takma, adlar, metin)
    return _BILGI[modul]


def _komsular(modul: str, ad: str) -> set[str]:
    tanim, takma, adlar, _ = _bilgi(modul)
    cikti = set()
    for x in ast.walk(tanim[ad]):
        if isinstance(x, ast.Attribute) and isinstance(x.value, ast.Name) and x.value.id in takma:
            hedef = takma[x.value.id]
            if x.attr in _bilgi(hedef)[0]:
                cikti.add(f"{hedef}.{x.attr}")
        elif isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load):
            if x.id in tanim and x.id != ad:
                cikti.add(f"{modul}.{x.id}")
            elif x.id in adlar and adlar[x.id][1] in _bilgi(adlar[x.id][0])[0]:
                cikti.add(".".join(adlar[x.id]))
    return cikti


def _ayir(tam_ad: str) -> tuple[str, str]:
    modul, _, ad = tam_ad.rpartition(".")
    return modul, ad


def _kokler() -> list[str]:
    return [f"{m}.{a}" for m, adlar in ref.DAYANILAN.items() if m != "config" for a in adlar]


def _kapanis() -> set[str]:
    gorulen, yigin = set(), _kokler()
    while yigin:
        ad = yigin.pop()
        if ad in gorulen:
            continue
        gorulen.add(ad)
        if ad not in HARIC:
            yigin.extend(_komsular(*_ayir(ad)))
    return gorulen


def _kaynak(tam_ad: str) -> str:
    modul, ad = _ayir(tam_ad)
    tanim, _, _, metin = _bilgi(modul)
    d = tanim[ad]
    satirlar = metin.splitlines(keepends=True)
    bas = min([d.lineno] + [x.lineno for x in getattr(d, "decorator_list", [])])
    return "".join(satirlar[bas - 1:d.end_lineno])


def _sha(tam_ad: str) -> str:
    return hashlib.sha256(_kaynak(tam_ad).encode("utf-8")).hexdigest()


def test_karar_verisi_gercek_kuralin_yasadigi_fonksiyonlara_ulasir():
    """`_karar_verisi` bugun bir sarmalayicidir (`_karar_girdisi(...)[:3]`); grafik gercek kurallara inmeli."""
    ulasilan = _kapanis()
    for ad in ("data.pozisyon._karar_girdisi", "data.pozisyon._karar_verisi_kur", "data.pozisyon._kume_verisi_yukle",
               "data.pozisyon._tam_hucreli_barlar", "data.klines.donem_kes", "data.klines.gunluge_cevir",
               "data.klines.hucreleri_tam_mi", "data.pozisyon._kayitlar", "data.split.kume_tanimi"):
        assert ad in ulasilan and ad in SABIT, ad


def test_gecisli_grafikteki_her_ad_siniflandirilmistir():
    """Grafikte yeni bir ad belirirse (yeni bir yardimci, yeni bir kural) sabitlenmeli ya da gerekcesiyle HARIC'e
    yazilmalidir; sessizce disarida kalamaz."""
    ulasilan = _kapanis()
    siniflandirilmamis = sorted(ulasilan - set(SABIT) - set(HARIC))
    assert siniflandirilmamis == [], (
        f"skaler referansin dayandigi grafikte siniflandirilmamis adlar: {siniflandirilmamis}. Kural tasiyorsa SABIT'e, "
        "veri yukleyicisi ya da erisim denetimiyse gerekcesiyle HARIC'e eklenmeli (D-B1).")
    artik = sorted(set(SABIT) - ulasilan)
    assert artik == [], f"SABIT'te grafikte artik bulunmayan adlar: {artik}"
    assert set(HARIC) <= ulasilan, sorted(set(HARIC) - ulasilan)


def test_dayanilan_kural_fonksiyonlarinin_kaynagi_sabit():
    degisen = [ad for ad, sha in SABIT.items() if _sha(ad) != sha]
    assert degisen == [], (
        f"skaler referansin dayandigi kural tanimlari degisti: {degisen}. Bu degisiklik `data/_skaler_referans.py`nin "
        "kararini da degistirir: kapi ile referans birlikte kayar ve esitlik testleri farki goremez (D-B1, RESULTS "
        "§14.44). Once referans, degisiklikten onceki halin kopyasiyla yeniden dondurulmali; SABIT yalnizca bundan "
        "sonra guncellenir.")


def test_haric_tutulanlar_kural_degil_erisim_yoludur():
    """HARIC listesi yalnizca yukleyici, erisim denetimi ve bellek onbellegi tasir; her girdinin gerekcesi yazilidir."""
    assert all(g.strip() for g in HARIC.values())
    assert not set(HARIC) & set(SABIT)
