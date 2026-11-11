"""Skaler referansin DAYANDIGI tanimlarin sabitlenmesi (performans 2b-0; denetci D-B1, RESULTS §14.44; kapanis D-B3,
RESULTS §14.46).

Neden: `data/_skaler_referans.py` karar yolunun kurallarini 4e63037'den kopyalar, ama veriyi ve bazi yardimcilari
kopyalamaz, `data/`daki asillarindan alir (`ref.DAYANILAN`). Bu asillardan biri degisirse kapi ile referans BIRLIKTE
kayar ve esitlik testleri farki goremez. Bu dosya, dayanilan adlardan ve `_karar_verisi`nin gecisli cagri grafiginden
ulasilan HER tanimi kaynak metniyle (SHA256) sabitler.

Yontem:
  - Grafik AST ile cikarilir (`_kapanis`): bir tanimin govdesinde yuklenen her ad, ayni modulun ust duzey bir tanimina
    ya da bir `data` modulu takma adi (`pencere_modulu.x`, `bv.x`, `from data.pencere import x`) uzerinden baska bir
    modulun ust duzey tanimina cozulurse kenardir. Fonksiyon govdesindeki yerel ice aktarmalar da sayilir.
  - Kokler: `ref.DAYANILAN`daki butun adlar (`config` haric: on-kayit sabitleri kendi degismezlik testleriyle korunur).
  - Grafik HICBIR adda durmaz (§14.46, D-B3): yukleyicilerin ve erisim denetimlerinin altindaki kurallar (donem sonrasi
    funding, `oran_8h`, tekrarli odeme secimi, ay elemesi, CSV ayristirma, evren donemleri, bolme kurali) da sabitlenir.
  - Ulasilan her ad iki listeden birindedir:
      * `SABIT`: kural tasiyan ya da kuralin parcasi olan tanimlar. P2b, P2c ve P2d'de DEGISMEZ. Degisirse once referans
        degisiklikten onceki halin kopyasiyla yeniden dondurulur (asagidaki hata mesaji).
      * `GUVENLIK`: yukleyiciler (disk, ag, kilitli tablo okuma), erisim denetimleri (onay/kesif baglami, ag yasagi, onay
        verisi izni, manifest), bellek onbellegi. SHA'lari YALNIZCA bir guvenlik duzeltmesinde guncellenebilir: degisen
        her GUVENLIK tanimi icin `analysis/00_veri_denetimi/RESULTS.md`de su bicimde bir satir bulunmalidir:
            GUVENLIK: <tam ad> <yeni sha256'nin ilk 12 hanesi> — <gerekce>
        (satir basinda istege bagli `- `; ayirac uzun tire "—"; gerekce en az 10 karakter). Satir yoksa test kirmizi.
  - Kaynak metni: tanimin AST araligi (dekoratorler dahil), dosya metninden, satir sonlari LF. `inspect.getsource` ile
    ayni metindir, ama monkeypatch'ten etkilenmez (`tests/conftest.py` `pozisyon._kayitlar`i ve `_veri_yukle`yi her
    testte sarar). Fonksiyonlar, siniflar VE sabitler ayni yolla sabitlenir: sabitin atama satiri (deger ifadesi dahil).
    Sabitin DEGERI sabitlenmez: degerler `config`ten gelir ya da surece ozgudur (`_PLAN_GIZLI = object()`).

Sinir (kayitta kalir, sizinti S-41..S-45): statik grafik dinamik cagrilari (`getattr`, nesne metotlari, `config`
uzerinden gelen degerler), ust duzey olmayan yeniden tanimlari, `globals()` / `__code__` / `AugAssign` ile yeniden
baglamayi ve modul golgelemeyi gormez; bunlar kasitli kod bicimi ister.
"""

from __future__ import annotations

import ast
import hashlib
import re

from data import _skaler_referans as ref
from tarama_yardimcisi import KOK

GUVENLIK_TURLERI = ("yukleyici", "erisim denetimi", "bellek onbellegi")
RESULTS_YOLU = ("analysis", "00_veri_denetimi", "RESULTS.md")
GUVENLIK_SATIRI = re.compile(r"^(?:- )?GUVENLIK: (?P<ad>\S+) (?P<sha>[0-9a-f]{12}) — (?P<gerekce>\S.{9,})$", re.M)

# Kural tanimlari (ad -> kaynak metninin SHA256'si, LF). Ilk degerler: performans 2b-0 kapanisi (RESULTS §14.46).
SABIT = {
    "data.binance_vision.AySiniriHatasi": "6af3e7495c76cf1817ff4c26f303088c13a8ffc1ab29a12546a37f5bfc3e1d2f",
    "data.binance_vision.FUNDING_SUTUNLARI": "2849d255ad114eafe03f149ff763895fca652e30e98bea86b1df85df596798ba",
    "data.binance_vision.MUM_SUTUNLARI": "75e9a583706cb059b86be269f769322db5f1f4b0cee2fb8b26db892eaf6986e7",
    "data.binance_vision._AY_DESENI": "e23171400b5daa3e8af4cbd3146649ab310b287b2ac13b9f1e37de51865721ce",
    "data.binance_vision._sayi_mi": "98369d30f295f8d59bc705eece0a07b7d2f05f1922c98cb3fcc47f7737c7e537",
    "data.binance_vision.ay_araligi_sinirlari": "0cfe1921c72674551326286690f238c7603ec4417a5783a6fb12fb81b3683725",
    "data.binance_vision.aylara_gore_ele": "1d1282f4c03a26be83c370f9177cd744c8bef8c0f3976fde666ba7e136907f5a",
    "data.binance_vision.dosya_ayi": "36c5a2d3dd930964afee4f734a6c4b389e8de289b3407401c1c03f947d3dc184",
    "data.binance_vision.zip_csv_oku": "8302acc8dd76247008ba44c6e6f07399a9996f3dae92c4d0e60a4f3136f3b7e2",
    "data.donem.Donem": "73f25b8bf03257dabe3e735eba92f37465a2d3778e53fcb2f5543f8a3aa74c5d",
    "data.funding.FUNDING_CIKTI_SUTUNLARI": "7fc3ffb2e49247ee106b79c60c24de8fc64a302efb4f20e6a329b8cad2a795ca",
    "data.funding._ay_cercevesi": "8d3559ecdd91b738ecc88459392851e98f6b537ada8b50c64d67197ed65a7938",
    "data.funding._donem_icinde": "19b6beca09e1ce2b05381239bca271a51ca66251be7a875c2d206d7aa17f04d4",
    "data.funding._zaman_dizisi": "836592289afc03734307183ba6d1b372565e0ca37d080a9e58b9306394a245fb",
    "data.funding.donem_sonrasi_kayitlari_at": "4736d1a93859c7440f9798bea365d18dc41da39f7f306a6ec7112b25bb73587c",
    "data.funding.funding_yukle": "bec67dc9b4945c921591331704ea8df05f7f68c24e128753738d613233d08608",
    "data.funding.ham_funding_yukle": "a117ede3bcf5c958d42c1ead88b9ecf61134c3912f37ed79ecbf571893984e93",
    "data.funding.sekiz_saate_normallestir": "5a071b437901f147629ded3b6aff4734a301c7d0e7b078dadad9a83294d30515",
    "data.klines.GUNLUK_BAR_SAYISI": "d9ef201dff2647d73222147b1d3aff50842b0f2deaafae50592823868a4cd184",
    "data.klines.GUNLUK_IZGARA_ADIMI": "9ec8aae90fd161eb5498ede661b241dddb4df9e8cf4a9ed4e88c30253162a79c",
    "data.klines.HUCRE_SUTUNLARI": "81799c9351b6e54ed994ffb2c230f8bb904109a17177842f69e4c6e0c7f0dd98",
    "data.klines.SAYISAL_SUTUNLAR": "557fb44cf92f8a828d0561d7f50c4cf803a274a54c7743e94cddf9482b361d26",
    "data.klines._ay_cercevesi": "799f213800830e5e48154d580f4b1699fd50198ba898f4b5bc8fbaeda75a3781",
    "data.klines._tekrarsiz_birlestir": "7d37506e8a8a4e618906bae17380ceb49f59720c366809111e1fcb77babc5905",
    "data.klines._zaman_cevir": "5187310b86298d06a4ff0809ad8617a89f8a2bba9628cabeb2458d58ebe51b0c",
    "data.klines.donem_kes": "bedad54d2e159d97e9c3c26837d0c54b36c1dc61eb394291121949eebc2757ed",
    "data.klines.gunluge_cevir": "788c4e34ae694476102e09361202f40f9b48fa57f4d5f485a6599162c5b3000b",
    "data.klines.ham_mumlari_yukle": "871ba649b6d588a84e20ccf53519fa8cb07942b2d52c301f67c65e595ea1d4ce",
    "data.klines.hucreleri_tam_mi": "466bb842beebd636be9e57088a81a37b43cee4af0ce0a0f4523996199c52bc5e",
    "data.pencere.ADIMLAR": "4af80d4d8def14587ed545a16bb0c2f002d4d3c79ab5f6bf45b2b0316cf25ce3",
    "data.pencere.ADIM_4H": "af5678e82356521f8c4f1751e4a85c7d02959b90aae424e9ad762823b1b15d11",
    "data.pencere.CikisSonucu": "ab4784806d80a62c669a62c1c225de9dcc5ec1a10cb13e9eae9a79045746e40a",
    "data.pencere.DonemDisiSinyal": "cc564872bddf74d66ebb55f1a5d65f91ba186ac73f3284d7c0c6ce1adeb96c95",
    "data.pencere.GUNUN_SON_4H_BARI": "59052065f88320b4d2c4abfa1bf4f129c0516f0c9a2ee0980806f33bd17bdb14",
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
    "data.pencere.donem_ici_mi": "211b1e45332fa5d4bb634e0db4aa08753f3c6db0e05f2b465f5112fdd3e6451d",
    "data.pencere.donem_kapanisi": "31943190a083ec39620748ab6f0f1691e4ba05cb6f7c7b4a63bcc19ed78fef37",
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
    "data.split.BOLME_SUTUNLARI": "932607135dddaee7200282a3afca23dd1df52623aa812770d58f31e162073f10",
    "data.split.BolmeTutarsizligi": "edaed74dbb1910715c96975fcc75304cff1baf96a375e9ee34ac7b0bcdf733c3",
    "data.split._bos_mum_cercevesi": "4a6627fe1551dc8660cd2f9cb1fccd25b15f90911d12cb675fe6411e76cb1b78",
    "data.split.grup": "8c428ab4c8f49cd24d59f66278a693ad36c5073ac7606408ecc04875393072a6",
    "data.split.kume_araligi": "dc42cf355bd2ac14556765e7da947d467edd333e90e79247fbfbfeea456960c6",
    "data.split.kume_erisimi": "c8276c1417093df268a2653e11d6c1aec9d3dac5ce01e5a0d921e9f0cb186b44",
    "data.split.kume_tanimi": "027a10ce011e5f443dc0048a7d1049d15b59516707eca1d82ceaaa42ae15584b",
    "data.split.split_dogrula": "fcac76619e1ab302ad5440b4e69db759618dddaf0a8795fa6b8f73c7efc139fe",
    "data.split.varlik_anahtari": "e68abb30a27c89f84d0755f66a78e78c8619a3464a13b6cbf509368eef02714c",
    "data.split.yukle": "83d9b9fe0749df5ee67b977f95e7d431b282a67ca91f3c52974de8b2ea803247",
    "data.universe.CSV_SUTUNLARI": "dea3afcebc2e1cfb20fa76609737f0782b17a97bd35a72ec9c2b3a2c7500df8d",
    "data.universe._BOOL_SUTUNLARI": "05ca4c3a163d79c8d82cf60e222e4484c6daadefd3c9309e3cd4f2aa2c16ff08",
    "data.universe._METIN_SUTUNLARI": "3db3f3dd63cd09826b3c54c3887d8945406d403f72b03d85ba9dca82be866531",
    "data.universe._TAMSAYI_SUTUNLARI": "769c27202b7bc96b5dd4ca4e2d5c76a0368361ef7b4fa1d2cacb797627383adc",
    "data.universe._ZAMAN_SUTUNLARI": "a769b569314fcb651b832cbf185c474472d29957287bf8a2ba8228260868e82a",
    "data.universe._normallestir": "568b99d1697a04efdee7e36dbae6cdeffa7cfd25674593136d623c0db7eca25d",
    # RESULTS §14.48 (D-B2): `evren_yukle`nin bool ayristirmasi kural tasir; yukleyiciden ayrilip SABIT'e alindi.
    "data.universe.bool_sutunlarini_ayristir": "05649ae9fb63cdfffafcbef429ed9c2962619933ad3a6ba62dfeffa0ecccfffa",
    "data.universe.sembol_donemleri": "f82f2eb2cd172cea05417593b8ce9a52d8c6c5aa89d44ac4594e4e8f6841d791",
}

# Yukleyiciler, erisim denetimleri, bellek onbellegi (ad -> (SHA256, tur)). Ilk degerler: §14.46. Degisiklik yalnizca
# RESULTS'taki gerekceli `GUVENLIK:` satiriyla (yukaridaki bicim).
GUVENLIK = {
    "data.binance_vision.AgsizOkumaIhlali": ("a4ae0ce2759e977a3436c7bed80e2263ecaf42a0661d15e57bcea7397dc43370", "erisim denetimi"),
    "data.binance_vision.DonukListeYok": ("456e77a084c59f069b0e0e85fe54c9579d06b53344dd8d3bcc66ce2e679778a2", "yukleyici"),
    "data.binance_vision.FUNDING_ONEKI": ("e611e9cc7d146b44dac6fde37df282b4ab5cfb8336551028dee0b8990188d601", "yukleyici"),
    "data.binance_vision.INDIRME_KOKU": ("87990555c317571cbb50b76c3478aff8c221fea559e6b1de10d8efa584b3d9b6", "yukleyici"),
    "data.binance_vision.KosuAgYasagi": ("b9490d4bbbb7e14720b8f195ca31b5736ed6debac022e7b29fa787b90ff9d027", "erisim denetimi"),
    "data.binance_vision.KosuYazmaYasagi": ("cfd9510c707eaf1d88ace163963659a763c46681c3d9c6a7fe39d9a0258ecba4", "erisim denetimi"),
    "data.binance_vision.LISTELEME_KOKU": ("eb34b7b6b8e31dea5612012f4544f6d9cf90f811edff19ed8c5f3546d860c0fd", "yukleyici"),
    "data.binance_vision.MUM_ONEKI": ("0a38fb620b64b7100e66b3235fc6638d79cd4fd76a444747e84d4c476c64ecb0", "yukleyici"),
    "data.binance_vision.OnayVerisiKorumasi": ("9ec36c0a971f53c98201fe451106066590b12934fd6236062d1ef47073cf1447", "erisim denetimi"),
    "data.binance_vision.OnbellekYoluHatasi": ("578ecaac9aaf211fe6e661f95a01464df3afe15af66b5eec7afa41f3ad1f5b8b", "yukleyici"),
    "data.binance_vision.S3_NS": ("753ae234bbef91c8403e64968a61ea71f04ed1e74c4446f401063430e6256c86", "yukleyici"),
    "data.binance_vision.VeriYok": ("188b484464e9d1eb6bf991bb5a7079ddcb1307e0db4cc90f9ea1b4daa23640d7", "yukleyici"),
    "data.binance_vision._AYGIT_ONEKLERI": ("90f7886f7e9c8c43d65358c408384d6b8788d8f71e2da7b1cf3c5a0b213ff9dc", "yukleyici"),
    "data.binance_vision._DEVRALINAN_IZIN": ("70839dc1b1ee841130baea47584594c57487a0ac64c60f78b718f40980ffa775", "erisim denetimi"),
    "data.binance_vision._DOGRULANMIS": ("355e0aa3dedbe9ca4307046bad5906ee4c04bd732f7ffc113156a77943f5449d", "erisim denetimi"),
    "data.binance_vision._DOGRULANMIS_KILIDI": ("9734b4f667dc96a68d1b147cb2444c6f38b2ca221cbd31112ef595e7728d1058", "erisim denetimi"),
    "data.binance_vision._DONUK_BELLEK": ("06ce72fbf2cf9df221e391076c03a380082edd131447acf4c9d01c214bb195ca", "yukleyici"),
    "data.binance_vision._IZIN": ("083700f34b6e502ebce8f70c8389679f4fdce8419600b9c1ef57d0531959bd8a", "erisim denetimi"),
    "data.binance_vision._IZIN_KILIDI": ("6af10fead60ebc2ab5333c682b0a6e9725cd7e1b578fbd3a0e862551f9ce616b", "erisim denetimi"),
    "data.binance_vision._IZIN_ORTAM_ADI": ("ca5912a6be0d84d744c11c7e48e0e3fc5930e555f76031b216772202cb65480d", "erisim denetimi"),
    "data.binance_vision._KOSU_AGSIZ": ("6738ec47ae0e1c47466c9d83617652fa13e403dafb8661ca639ab08a2db1c878", "erisim denetimi"),
    "data.binance_vision._LISTE_ALT_YOLU": ("c7a47423ad859de983812872992aa8568c13aae4b16e208f99b5e07f2353d62b", "yukleyici"),
    "data.binance_vision._ONBELLEK_TURLERI": ("3760b37447a95bf72dca5731959322fbb7e60ae8500d0f5705ce8dbe323e0036", "yukleyici"),
    "data.binance_vision._YEREL": ("d27f2382b2af72096ce9aa605a278e048f5ab9bbb0a70471f1fcf56ce8b8ce08", "yukleyici"),
    "data.binance_vision._ag_yasak_mi": ("b7e769a8fec132150e4321bb260f0df3b0a0e205f5e1985e0447b8d89b1b5039", "erisim denetimi"),
    "data.binance_vision._agsiz_mi": ("f2d62ab9dfefa6d88283b6d83a5689ed9a992daf5532ae162622cd301beaf166", "erisim denetimi"),
    "data.binance_vision._anahtar_denetle": ("6d755e3c32a1249509dc57eb1a06c8f9a46d8d53eb8a5577703da08f9c34d7d2", "yukleyici"),
    "data.binance_vision._donuk_anahtar_denetle": ("c01ceb26124eff789180d15c933d6a50d3ce6b5112cc6a135f71596eba8d9e14", "yukleyici"),
    "data.binance_vision._donuk_anahtarlar": ("0576f892f443722c345fdc94669d7f6d4236056b2196d96714357739355da71c", "yukleyici"),
    "data.binance_vision._donuk_oku": ("b9cf0b4b10637152f50ec80bb34cfeec3fcd646323cec3c9795e63543c35894c", "yukleyici"),
    "data.binance_vision._iste": ("c9b9e3a2996954b22b1477d1f2daab0ff68a5e751151278ca7232f0ff86fbbab", "yukleyici"),
    "data.binance_vision._listele": ("6584a185fb8e05e7de425b45b8a85aed8823a943fe16a10b6bcc290e9195468c", "yukleyici"),
    "data.binance_vision._onay_verisi_denetle": ("846b52d1fb4cdf63ef12f9f4d1a63982ce38df614d0616736878da1664b4b4af", "erisim denetimi"),
    "data.binance_vision._onbellek_yolu_denetle": ("95c3d6dd747d95356c3190ab354de86c58914bbd656ac843969981c14413a8e6", "yukleyici"),
    "data.binance_vision._onbellek_yolu_normallestir": ("ae0006562ac5199fc0cefac202e6f463eb7c3d23be04e5e6072f16a4fd7c5b58", "yukleyici"),
    "data.binance_vision._oturum": ("efbaada7fc23e66eb875d2aff09899e367023a3b19c49e5b85f28ebb05817d74", "yukleyici"),
    "data.binance_vision.ag_yasagi_denetle": ("4de9f970d9f6d12e8816ce11feb74994060e78f8feb86aa997c78adaca291e5b", "erisim denetimi"),
    "data.binance_vision.agsiz_okuma": ("e4801de56fd561aa06badcaf0ccaa517b2fe71fb8fb20be3d2148bcddd280c41", "erisim denetimi"),
    "data.binance_vision.donuk_liste_yolu": ("56d1adbdf8ba05cfa8eb605a9a6a7adb255b2c8d40b5246d92494fd289c90bbe", "yukleyici"),
    "data.binance_vision.funding_dosyalari": ("b4e3bd3665598d4f2866e7984b9c98c7981b6e0c25250edf6affde0fd39fa1fe", "yukleyici"),
    "data.binance_vision.mum_dosyalari": ("0a66b6c6f8b55ca16dcb4c76fd27b4fe1f662d20e4f07befeb4cdff19f8f75c9", "yukleyici"),
    "data.binance_vision.onay_izni_var": ("2ad1ccb6d3c0153ca1dd42ae4eb5b8723472e29aec54c6110059c6270e325427", "erisim denetimi"),
    "data.binance_vision.onay_verisi_izni": ("f5616665cba2b36028dd000d39f952cc59bbb9b825d97cb8f7c0d610ddadefa9", "erisim denetimi"),
    "data.binance_vision.onay_verisi_mi": ("2c72aa59655989fe11a5704b61574fcc9324fc8e19454876ed73262c63961de5", "erisim denetimi"),
    "data.binance_vision.onbellege_yaz": ("4082bb24194124518ab29741c5ea8f6fbdc02bfff6a31ff845d488693d662b5d", "yukleyici"),
    "data.binance_vision.onbellek_yolu": ("84787a06ddd9b03b89fab4c637cf0231dc336225bb627a6cf2a55988927b7b2d", "yukleyici"),
    "data.binance_vision.onbellekten_oku": ("3067ab08ee65d071f6e79441c7d28825981ee0859973e918069a61b46155fda5", "yukleyici"),
    "data.binance_vision.zip_indir": ("9a5f559357c9793851679ff55d1dd534d56a2fe0cfee1877084f9afa9d0eb3ff", "yukleyici"),
    "data.klines.mumlari_yukle": ("6b62a65c3212254cf28d4fe10a6a0d85c827dcbafddd573b757a9e241400c42c", "yukleyici"),
    "data.kume_bellegi.AZAMI_GIRDI": ("69c1a3c200b4a567c0fa2e63c344cdb94d05100e6d338d232dbb7d5b4e885be4", "bellek onbellegi"),
    "data.kume_bellegi._BELLEK": ("20acd8c082eaf1ef1e1b510c6bd8a38d655d37a43d994bdd4a398a7b952bf087", "bellek onbellegi"),
    "data.kume_bellegi._KILIT": ("8adedced65be0f6e2d75f553ad0665cc36f9586b5b4577c0116eb5407081a06b", "bellek onbellegi"),
    "data.kume_bellegi.getir": ("86c242664f116edd18938b37bc028037649635a963614a6dec3f1273d23dfbc2", "bellek onbellegi"),
    "data.onbellek_manifest.MANIFEST_YOLU": ("0f3727894d8bd3d350a1bcd7cc3ebc2e47f583de52cc29f49f638adea569dc2e", "erisim denetimi"),
    "data.onbellek_manifest.ManifestHatasi": ("2dc9b34b449303a67c98db31b3570a65d59322ecd5f1a485cfdb70728c606168", "erisim denetimi"),
    "data.onbellek_manifest.ManifestUyusmazligi": ("23676564a6beb922d2da1de52f22a282be91d595a5de70d89127965c82181efb", "erisim denetimi"),
    "data.onbellek_manifest.ManifestYok": ("e420a4eeba755744df6dfe159c8858eb49c07f8c8e451e1f56326c7255ba2960", "erisim denetimi"),
    "data.onbellek_manifest._BELLEK": ("d4790125db532ff7c7e2dfc440c2ee4eb42cc408acf4cae5a9c4e27cb95230a8", "erisim denetimi"),
    "data.onbellek_manifest._Manifest": ("e0291b500e7dad556aa66ac7c58747b1c13bdff3d700870ea7be29abbdec096c", "erisim denetimi"),
    "data.onbellek_manifest._SUTUNLAR": ("b8df0a88471259857ee4ff6a692f922119bd527624d393a0e6c2a56e85f63e8f", "erisim denetimi"),
    "data.onbellek_manifest._TEST_AYARI": ("76d1b7df9bc55ad9a034fdbb1b11236dd2f09b91e7fb2180d3dfb60737ec278b", "erisim denetimi"),
    "data.onbellek_manifest._etkin_yol": ("1cffa4e01bd9d69791f4f3fa91b57ad8ee3f24472236bb9e62dc5c08e53b559e", "erisim denetimi"),
    "data.onbellek_manifest._manifest": ("a525f8ee94c4f32c48d6ec15d6c7cde2113a7ed256e44fcffae3708b1334e69a", "erisim denetimi"),
    "data.onbellek_manifest._manifest_coz": ("3ca1c6a5ff00a0769aa1a17ae6d499df838b3f5084925a6db9772bc7ae19c936", "erisim denetimi"),
    "data.onbellek_manifest._onay_dosyasi_mi": ("e6ccc6556684d19f6c947e2a6c6eb3339ec6d59e1a5f48f52a0f43ad425fc3c4", "erisim denetimi"),
    "data.onbellek_manifest._onay_listesi": ("4614c1088eba973af00386e088a16fa6cd106c37f1f1f00f1461d7af3ed96af1", "erisim denetimi"),
    "data.onbellek_manifest.denetim_etkin": ("099c7cea0fcdffcef243990a333a92baeb9aa6c6e6482422e22c198eeeab52d4", "erisim denetimi"),
    "data.onbellek_manifest.okuma_denetle": ("2ac0c782e1c28f1a7d0472a0c3298c0bc5a2f243ff601499fe017d7758ed839e", "erisim denetimi"),
    "data.onbellek_manifest.onay_ayrinti_yolu": ("ddbc365dbed1d3216c3b80fe01257c5df33512718880940575d5baf1ccf7accb", "erisim denetimi"),
    "data.pozisyon._erisim_denetimi": ("456f25c630177c22452cded218627275a9967ee194317ab43f177d66e23c581b", "erisim denetimi"),
    "data.pozisyon._veri_yukle": ("dce15a76a2ad7b0c2299b9cefcc74314e889873866ba7397c9a8eb0ddaab342b", "yukleyici"),
    "data.split.KILIT_SECILDI": ("8873835f33bc526f2f4c7d211d727e20f9be687d26bdec58768d318f7f7656af", "erisim denetimi"),
    "data.split.KesifBaglamiYok": ("f8efa143f7a3e4d0b5eeb2522cd51b91f4ade23794a2cd50a218437b41c9e178", "erisim denetimi"),
    "data.split.KilitKaydi": ("a3a22c12186ea7cff3982c34dceaadf0bec35702ced7cc18ce797e85d1a3a98d", "erisim denetimi"),
    "data.split.ONAY_TABLO_BASLIGI": ("82337d703400b87fbfb73447c154edc94d4dca1e228a102d278a7732841a758f", "erisim denetimi"),
    "data.split.OnayGerekli": ("9a7e8a497dc2f6eb8e061323dc439331f4f8d752417e9c48926b15794fd707ed", "erisim denetimi"),
    "data.split.OnayKorumasi": ("e935492e7a8996dafca9c9c29c38318928c4eefcf6d194a65e3caef344bb1e18", "erisim denetimi"),
    "data.split.OnayUyusmazligi": ("12715da8d5e80be83baba619ff56ca4421d036051f7fa82724f5070b06e9d0f1", "erisim denetimi"),
    "data.split._AKTIF_KOSU": ("f9a366f8c2c877529e38c3863c08d5674f7f6a0f2978f420bae7f00dc1530ae1", "erisim denetimi"),
    "data.split._KAYIT_YOLU": ("272e799f90fa4a25d9897221c93039b9c10ef5f6cf86940cafb0b026aee1c767", "erisim denetimi"),
    "data.split._KESIF_DURUMU": ("54c803e6efa09fec54a5c802b6c7df85b711afd7553b1d1bf4304ed5efe62421", "erisim denetimi"),
    "data.split._Kosu": ("421e154927c062f771e77d6f1c7741389037659e7143d93c30e4a0edc6a7d23b", "erisim denetimi"),
    "data.split._PYTEST_OTURUMU": ("f4b1f1cb5fc5e244bace612cf0fed0fe5b6d39644d88de0bea5c208f9e76f252", "erisim denetimi"),
    "data.split._TEST_AYARI": ("abb2bfa94fb16f8159776880d146b24761c183e9ae510a2fb6d121da8228c040", "erisim denetimi"),
    "data.split._TestAyari": ("e3c926a7c6f38d42cb6a91c9aaba2b77b796966b34ea7a456c189d68c8a6f1cc", "erisim denetimi"),
    "data.split._acik_kosu": ("f472903ff9ad9ea0971388c08ef9bd568a915f8b789826fe6169406c005f2865", "erisim denetimi"),
    "data.split._kaydi_oku": ("653fffe9feb1050a68571d13c7b8a0dba5d6353f51ade2cfc9f5318bc5367b1e", "erisim denetimi"),
    "data.split._kayit_yolu": ("32791efd3e8a5a03a70bfdc2f68c35051d40963105f5d0443574dd6e40f1391c", "erisim denetimi"),
    "data.split._pytest_testi": ("c7211bb354177d89c434ac6238116e9fc3df87cea57a9f1a1a16fb6898e60db6", "erisim denetimi"),
    "data.split._tablo_zamani": ("cd2af7e76b9c1b6d3c74853d1e8b7f1094c8cef30856cb4d67ba897e44677ea5", "erisim denetimi"),
    "data.split._test_ayari": ("444047d7cdb89ebb0f08a463b6882d1de0e6ee54d286f34b3e2a134f409cdde4", "erisim denetimi"),
    "data.split.aktif_onay_kosusu": ("6a0bc884f54b9a3eb0c1b9d4c7cd7e9170bedda5cb2dec4f90e40c84a5104f16", "erisim denetimi"),
    "data.split.kayit_satirlari": ("937e6a934b73cba1c748878dbaf5e135d04fc69f15232e5f704001c0a5695493", "erisim denetimi"),
    "data.split.kesif_baglami_dogrula": ("96a930f422608ed2142b72633dedd1cac5a4b19f38d73ea348cb142f723d2baa", "erisim denetimi"),
    "data.split.kesif_kosusu_acik": ("6bc94b6f1d3a4a2d9956e486319954be166743269f5d3d665f9bfaf6c3e5d41f", "erisim denetimi"),
    "data.split.not_alanlari": ("4d5f5be119873dce2e2a94e792b086479fa87c290d735570d393009ffa280cd6", "erisim denetimi"),
    "data.split.onay_baglami_dogrula": ("3e2350633d3a1e2910ea1826005007377dbd712279a97b1722bb4e59f21d2eb2", "erisim denetimi"),
    "data.split.onay_erisimi_denetle": ("c2bc97b98183a77245d751d259b06f621ba785cc67c37188e6f135c218836b1e", "erisim denetimi"),
    "data.split.split_oku": ("b7181f134280462fe0777b60c8e492e292bc5de3a11f30afdc5a4d11348a232a", "yukleyici"),
    "data.universe.evren_yukle": ("68fce88a3f3cad902a1b968b7c8953f62c3d809419e760dcfc3bf57d8567a989", "yukleyici"),
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


def _guvenlik_satirlari() -> list[re.Match]:
    yol = KOK.joinpath(*RESULTS_YOLU)
    metin = yol.read_text(encoding="utf-8").replace("\r\n", "\n") if yol.exists() else ""
    return list(GUVENLIK_SATIRI.finditer(metin))


def _gerekcesiz_guvenlik_degisiklikleri() -> list[str]:
    """Ozeti kayitli degerden farkli olan ve RESULTS'ta (ad, yeni ozetin ilk 12 hanesi) satiri bulunmayan GUVENLIK
    adlari."""
    gerekceli = {(m["ad"], m["sha"]) for m in _guvenlik_satirlari()}
    return sorted(ad for ad, (sha, _) in GUVENLIK.items()
                  if (yeni := _sha(ad)) != sha and (ad, yeni[:12]) not in gerekceli)


def test_karar_verisi_gercek_kuralin_yasadigi_fonksiyonlara_ulasir():
    """`_karar_verisi` bugun bir sarmalayicidir (`_karar_girdisi(...)[:3]`); grafik gercek kurallara inmeli. §14.46:
    yukleyicilerin altindaki kurallara da."""
    ulasilan = _kapanis()
    for ad in ("data.pozisyon._karar_girdisi", "data.pozisyon._karar_verisi_kur", "data.pozisyon._kume_verisi_yukle",
               "data.pozisyon._tam_hucreli_barlar", "data.klines.donem_kes", "data.klines.gunluge_cevir",
               "data.klines.hucreleri_tam_mi", "data.pozisyon._kayitlar", "data.split.kume_tanimi",
               # D-B3 (§14.46): yukleyicilerin ve erisim denetimlerinin altindaki kurallar
               "data.funding.donem_sonrasi_kayitlari_at", "data.funding._donem_icinde",
               "data.funding.sekiz_saate_normallestir", "data.funding.ham_funding_yukle",
               "data.universe.sembol_donemleri", "data.split.yukle", "data.split.kume_erisimi",
               "data.klines._tekrarsiz_birlestir", "data.binance_vision.zip_csv_oku",
               "data.binance_vision.aylara_gore_ele"):
        assert ad in ulasilan and ad in SABIT, ad


def test_gecisli_grafikteki_her_ad_siniflandirilmistir():
    """Grafikte yeni bir ad belirirse (yeni bir yardimci, yeni bir kural) SABIT'e ya da (yukleyici, erisim denetimi,
    bellek onbellegi ise) GUVENLIK'e yazilmalidir; sessizce disarida kalamaz."""
    ulasilan = _kapanis()
    siniflandirilmamis = sorted(ulasilan - set(SABIT) - set(GUVENLIK))
    assert siniflandirilmamis == [], (
        f"skaler referansin dayandigi grafikte siniflandirilmamis adlar: {siniflandirilmamis}. Kural tasiyorsa SABIT'e, "
        "yukleyici / erisim denetimi / bellek onbellegiyse turuyle GUVENLIK'e eklenmeli (D-B1, D-B3).")
    artik = sorted((set(SABIT) | set(GUVENLIK)) - ulasilan)
    assert artik == [], f"SABIT/GUVENLIK'te grafikte artik bulunmayan adlar: {artik}"
    assert not set(SABIT) & set(GUVENLIK)


def test_dayanilan_kural_fonksiyonlarinin_kaynagi_sabit():
    degisen = [ad for ad, sha in SABIT.items() if _sha(ad) != sha]
    assert degisen == [], (
        f"skaler referansin dayandigi kural tanimlari degisti: {degisen}. Bu degisiklik `data/_skaler_referans.py`nin "
        "kararini da degistirir: kapi ile referans birlikte kayar ve esitlik testleri farki goremez (D-B1, RESULTS "
        "§14.44). SABIT P2b, P2c ve P2d'de degismez; once referans, degisiklikten onceki halin kopyasiyla yeniden "
        "dondurulmali, SABIT yalnizca bundan sonra guncellenir.")


def test_guvenlik_tanimlari_gerekcesiz_degisemez():
    degisen = _gerekcesiz_guvenlik_degisiklikleri()
    assert degisen == [], (
        f"GUVENLIK tanimlari degisti ve RESULTS'ta gerekcesi yok: {degisen}. Bu tanimlar kapiya ve referansa AYNI veriyi "
        "verir; degisiklik ikisini birlikte kaydirabilir. Yalnizca bir guvenlik duzeltmesi icin, her biri icin "
        "`analysis/00_veri_denetimi/RESULTS.md`ye `GUVENLIK: <ad> <yeni-sha-ilk-12> — <gerekce>` satiri yazilir "
        f"(yeni ozetler: {[(ad, _sha(ad)[:12]) for ad in degisen]}).")


def test_guvenlik_listesi_turleri_ve_results_satirlari_gecerli():
    assert all(tur in GUVENLIK_TURLERI for _, tur in GUVENLIK.values())
    assert all(re.fullmatch(r"[0-9a-f]{64}", sha) for sha, _ in GUVENLIK.values())
    assert all(re.fullmatch(r"[0-9a-f]{64}", sha) for sha in SABIT.values())
    # RESULTS'taki her GUVENLIK satiri listedeki bir ada isaret eder (yazim hatasi gerekceyi bosa cikarmasin).
    bilinmeyen = sorted({m["ad"] for m in _guvenlik_satirlari()} - set(GUVENLIK))
    assert bilinmeyen == [], bilinmeyen


def test_guvenlik_satiri_bicimi():
    """Bicimin kendisi: dogru satir eslesir, gerekcesiz / kisa ozetli / duz tireli satir eslesmez."""
    assert GUVENLIK_SATIRI.search("GUVENLIK: data.split.split_oku 0123456789ab — S-37 duzeltmesi icin denetim eklendi")
    assert GUVENLIK_SATIRI.search("- GUVENLIK: data.split.split_oku 0123456789ab — S-37 duzeltmesi icin denetim eklendi")
    for kotu in ("GUVENLIK: data.split.split_oku 0123456789ab —", "GUVENLIK: data.split.split_oku 0123456789ab — kisa",
                 "GUVENLIK: data.split.split_oku 0123456789a — yeterince uzun bir gerekce",
                 "GUVENLIK: data.split.split_oku 0123456789ab - yeterince uzun bir gerekce"):
        assert not GUVENLIK_SATIRI.search(kotu), kotu
