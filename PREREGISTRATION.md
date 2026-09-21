# PREREGISTRATION.md — Short Öngörü Hipotezleri

**Durum:** Sürüm 8 (2026-09-21). F2 keşif aşaması başlamadan önce, hiçbir getiri hesaplanmadan commit edildi.
**Kapsam:** F2 (keşif) ve F3 (onay). Taktik (F4) ve ileri-zaman testi (F5) ayrı revizyonla eklenir.

Bu belge commit edildikten sonra aşağıdaki hiçbir tanım, eşik veya tarih sınırı
sessizce değiştirilemez. Değişiklikler en alttaki Revizyon Günlüğü'ne gerekçesiyle yazılır.

---

## 1. Soru

Binance USDⓈ-M USDT perpetual piyasasında, önceden tanımlanmış üç olay türünden
sonra short pozisyon, (a) aynı coini rastgele bir zamanda short'lamaktan ve
(b) aynı anda başka coinleri short'lamaktan, maliyet ve funding sonrası anlamlı
ölçüde daha fazla kazandırıyor mu?

## 2. Veri ve evren

| Kalem | Değer |
|---|---|
| Piyasa | Binance USDⓈ-M, USDT marjinli, PERPETUAL sözleşmeler |
| Dahil | Delist edilmiş sözleşmeler dahil tüm tarihsel semboller |
| Hariç | Stablecoin tabanlı çiftler (ör. USDCUSDT) ve endeks sözleşmeleri (ör. BTCDOMUSDT, DEFIUSDT) |
| Bar | H1, H2: 4 saat · H3: 1 gün |
| Toplam dönem | 2020-01-01 00:00 UTC → 2026-08-31 23:59 UTC |
| Funding | Gerçek funding geçmişi. 8 saat dışında bir ödeme aralığı (1, 2, 4 saat veya başka) kullanan sözleşmelerde oran, karşılaştırma için 8 saate normalleştirilir; getiri hesabında ise gerçek ödemeler kullanılır. Normalleştirme genel formülle tanımlanır: `oran × 8 / aralık`; yukarıda sayılan aralıklar örnektir, sınırlayıcı değildir |

**Kapsam netleştirmesi.** Evren, `fapi/v1/exchangeInfo` içinde `contractType = PERPETUAL`
olan USDT marjinli sözleşmelerden oluşur. `contractType = TRADIFI_PERPETUAL` olan sözleşmeler
(hisse senedi, emtia, premarket) kripto varlık olmadığı için kapsam dışıdır. exchangeInfo'da
bulunmayan (delist edilmiş) semboller elle sınıflandırılmıştır.

**Hariç tutma listesi (kesin).**
- Endeks sözleşmeleri: BTCDOMUSDT, DEFIUSDT, ALLUSDT, BLUEBIRDUSDT, DOTECOUSDT, FOOTBALLUSDT
- Stablecoin tabanlı: USDCUSDT
- Stablecoin tanımı: sabit bir fiyata bağlı kalacak şekilde tasarlanmış ve bağını koruyan token.
  Bu tanıma göre FRAXUSDT, USTCUSDT, STBLUSDT ve STABLEUSDT evrende kalır.

**1 günlük barlar.** 1d barlar yalnızca dönem içi 4h barlardan türetilir: UTC günü; open ilk, high en yüksek, low en düşük, close son değer; volume ve quote_volume toplam. Bir gün, yalnızca o günün 00:00, 04:00, 08:00, 12:00, 16:00 ve 20:00 UTC açılışlı altı 4h barının tamamı mevcut ve aynı dönemin içindeyse oluşur; aksi hâlde o gün eksik (NaN) sayılır. Bu yüzden dönemin kısmi ilk ve son günleri 1d serisinde yer almaz. Bu seri tektir: H3'ün sinyal pencereleri, bütün hipotezlerin uygunluk hacmi ve K1/K2 havuzlarının 1d barları aynı seriden gelir. (rev.8)

**Listeleme dönemi.** Her sembolün verisi bir veya daha fazla listeleme dönemine ayrılır.
- Dönem, sıfır olmayan hacimli ilk barda başlar ve sıfır olmayan hacimli son barda biter. Sınır bar düzeyindedir, ay düzeyinde değil. Dönemin son 4 saatlik barının açılış anına **dönem bitişi (B)**, kapanış anına **dönem kapanışı (K = B + 4 saat)** denir. Dönem dışındaki hiçbir bar (dolgu barı, boşluk sonrası veri, SETTLED verisi) hiçbir hesaba girmez. (rev.8)
- 6 veya daha fazla ardışık sıfır hacimli bar (bir gün) dönemi böler. Bu barlar delist edilmiş ya da henüz yeniden listelenmemiş bir sözleşmenin dolgu verisidir ve hiçbir hesaba girmez.
- 7 günden uzun eksik bar boşluğu dönemi böler. Bundan kısa boşluklar borsa kesintisi sayılır ve rev.3'ün veri boşluğu kurallarına tabidir.
- Yeniden adlandırma zincirindeki her sembol ayrı bir dönemdir; fiyat serileri birleştirilmez.
- Listeleme yaşı her dönem başında sıfırlanır.
- Tüm geriye bakış pencereleri dönem başlangıcını aşamaz; aşıyorsa değer hesaplanmaz ve o barda olay oluşmaz.
- Ufuk dönem sonunu aşarsa §4 "Dönem sonu ve çıkış" kuralı uygulanır. (rev.8)
- Aynı kurallar K1 ve K2 kontrol barlarına da uygulanır.

**Karantina kuralının kaldırılması.** Rev.2'de getirilen SETTLED tabanlı karantina kuralı yürürlükten kalkmıştır. F1 ölçümü, SETTLED aylarının yeniden fiyatlandırma değil yeniden listeleme anlamına geldiğini; 34 karantina ayının 18'inde ise dolgu koşusu bulunmayan, işlem gören verinin gereksiz yere dışarıda bırakıldığını; dönem içine alınan 13 SETTLED ayında ortak barların ana seriyle birebir aynı olduğunu göstermiştir; bu aylarda 24 bar yalnızca SETTLED dosyasında, 30 bar yalnızca ana seride bulunur (rev.8'de düzeltildi: önceki metinde 14 ay ve iki örnek ay yazıyordu). Yukarıdaki dönem bölme kuralları aynı riski daha doğru kapsar. SETTLED bilgisi yalnızca denetim amacıyla tutulur. Fiyat ve hacim için tek kaynak ana seridir: SETTLED dosyaları hiçbir hesaba girmez ve ana serideki boşluklar SETTLED verisiyle doldurulmaz. (rev.8)

**Funding'i bulunmayan dönemler.** Hiçbir funding kaydı bulunmayan listeleme dönemi, üç hipotezin hiçbirinde kullanılmaz; ne olay ne kontrol üretir. Gerekçe: net getiri funding içerir; funding'i olmayan dönem yalnızca H2'den çıkarılırsa brüt ve net olay kümeleri ayrışır ve K2 kontrol havuzu tutarsızlaşır. Funding sıfır varsayılmaz. Bir funding kaydının dönemde sayılma penceresi, dönem başından dönem bitişine (B, dahil) kadardır ve getiri hesabının dönem sonu penceresiyle aynıdır; toleranslar §4 "Zaman toleransı"na göredir. Funding'i dönemin içinde geç başlayan dönemlerde, ilk kayıttan önceki olay ve kontroller §4'teki tek karar noktasında funding tamlığını sağlamadıkları için oluşmaz. (rev.8)

**Gerçek işlem sonrası funding kayıtları.** Dönem kapanışından (K) sonra gelen funding kayıtları yok sayılır; B ile K arasındaki kayıtlar için §4'teki dönem sonu istisnası geçerlidir. F1 ölçümü, 57 sembolde (38 SETTLING, 19 exchangeInfo dışı) son dönemin kapanışından sonra da funding kaydı bulunduğunu göstermiştir. Rev.7'de bu kayıtların "bir ya da birkaç sabit orandan oluştuğu" yazılmıştı; A1 ölçümü bu ifadeyi desteklememiştir ve ifade geri alınmıştır. (rev.8)

**Veri boşlukları.** Bar dizisinde eksik bar bulunabilir (F1 denetimi: 105 kayıt, 10 olay;
en büyüğü 48 ve 49 sembolü aynı anda etkilemiştir). Aşağıdaki kurallar dönem kurallarına ek olarak uygulanır. 7 günden kısa boşluklar dönem bölmez; daha uzun boşluklar §2'deki listeleme dönemi kuralına göre dönemi böler.

- **Pencereler zamanla tanımlanır.** "Son N bar" ifadesi son N × 4 saatlik zaman aralığı
  demektir (1 günlük seride N × 24 saat). Bar sayısıyla değil, zaman damgasıyla hesaplanır.
- **Tamlık şartı.** Bir pencerede beklenen barlardan biri bile eksikse değer hesaplanmaz
  (NaN). O barda olay ya da kontrol oluşmaz. Bu, H1'in hacim ve yükseliş pencerelerini,
  H2'nin 30 barlık ve k barlık pencerelerini, H3'ün hacim pencerelerini ve SMA50'yi, ayrıca
  uygunluk hacmini kapsar.
- **Ufuk.** Ufuk zamanla ölçülür: h bar = h × adım; adım 4h ızgarasında 4 saat, 1d ızgarasında 24 saattir. Hedef çıkış barı, kapanışı hedef çıkış anına (T) eşit olan dönem içi 4h bardır (§4 "Fiyat okuma tabanı"). Bu bar eksikse çıkış, açılışı T'ye eşit ya da T'den sonra olan ilk dönem içi 4h barın **açılış** fiyatındandır ve çıkış anı o barın açılışıdır. Dönem sonu ve delist kuralları önceliklidir. (rev.8)
- **Giriş.** t+1 barı eksikse olay oluşmaz.
- 1 günlük seride bir gün yalnızca §2 "1 günlük barlar"da tanımlanan altı dönem içi 4 saatlik barın tamamı varsa oluşur; eksik gün zaten NaN'dir ve pencerelerde eksik sayılır. (rev.8)
- Aynı kurallar K1 ve K2 kontrol barlarına da uygulanır.

**Gerekçe.** F1 denetiminde açıklanamayan iki bütünlük sıçraması (WAVESUSDT +%54,1 ve
KNCUSDT +%31,3, ikisi de 2022-03-01 00:00) 2022-02-26…28 arasındaki 18 barlık kesintinin
ardından gelen ilk bardır. Fiyat kesinti sırasında hareket etmiştir. Kesinti üzerinden
atlayan bir pencere sahte bir yükseliş, kesinti üzerinden geçen bir ufuk ise gerçekte
alınamayacak bir çıkış fiyatı üretir. Bu kural o iki kaydı zaten dışarıda bırakır.

**Veri bütünlüğü kontrolü.** F1 denetim raporu, `|open[t] / close[t-1] - 1| > 0.30` olan tüm
barları sembol ve zamanla listeler. Dönem bölme kurallarıyla açıklanamayan kayıtlar, F2 başlamadan önce ayrı bir revizyonla ele alınır. WAVESUSDT ve KNCUSDT kayıtları için bu karar Rev.8'de verilmiştir: iki kayıt dönem bölme kurallarıyla değil §2 "Tamlık şartı"yla dışarıda kalır; boşluk üzerinden geçen her pencere hesaplanamaz olduğundan ek kural gerekmez.

**Uygunluk (t anında, yalnızca t'ye kadarki veriyle):**
- Listeleme yaşı ≥ 30 gün.
- H1, H2: son 30 günün medyan günlük işlem hacmi ≥ 10 milyon USDT.
- H3: son 30 günün medyan günlük işlem hacmi ≥ 2 milyon USDT.

**Uygunluk penceresi ve t günü.** Uygunluk hacmi, t barının ait olduğu UTC günü hariç,
ondan önceki 30 tam günün medyanıdır. Kural 4 saatlik ve 1 günlük barlarda aynıdır.

**İleri kaymanın ölçüsü.** İleri kayma, hedef bar ile sonraki mevcut barın açılış zamanları arasındaki fark olarak ölçülür ve sınır dahildir. Hedef bar ve sonraki mevcut bar her iki ızgarada da dönem içi 4h barlardır. (rev.8)

Delist edilen sözleşmelerin geçmişi elde edilemezse bu durum F1 denetim raporunda
sayısıyla yazılır ve sonuçlar "kötümser yanlılıklı" olarak etiketlenir.
F1 ölçümünde evrende 128 sembolün `exchangeInfo` durumunun SETTLING olduğu, yani uzlaşmış sözleşmeler olduğu belirlenmiştir. `exchangeInfo`'da hiç bulunmayan 28 sembolle birlikte toplam yaklaşık 156 sembol delist edilmiştir. Bu sembollerin geçmişi eksiksiz mevcuttur ve dönem sonları gerçek işlem bitişine göre belirlenir; ancak "hayatta kalma yanlılığı yoktur" hükmü geri alınmıştır, çünkü ilk denetimde delist sayısı 28 olarak eksik saptanmıştı.

**Evren tablosunun sabitlenmesi.** Listeleme dönemi sınırları
`data/universe.csv` dosyasına yazılır ve commit edilir. Bu dosya `split.csv` gibi
sabittir; analiz bu dosyadan okur, canlı exchangeInfo'dan yeniden türetmez.

## 3. Veri bölmesi

**Coin bölmesi.** Bölme sembol değil **varlık anahtarı** üzerinden yapılır. Varlık
anahtarı, yeniden adlandırma zincirindeki en eski semboldür; zincirde olmayan sembollerde
sembolün kendisidir. Her varlık anahtarı için `SHA256("short-lab-v1:" + VARLIK_ANAHTARI)`
hesaplanır. Onaltılık özetin tamsayı değeri çift ise **A**, tek ise **B** grubudur. Zincirdeki
tüm semboller aynı gruba düşer.

Kabul edilen yeniden adlandırma zincirleri (dokuz):
LENDUSDT→AAVEUSDT · BTTUSDT→1000BTTCUSDT · RNDRUSDT→RENDERUSDT · GALUSDT→GUSDT ·
MATICUSDT→POLUSDT · EOSUSDT→AUSDT · LUNAUSDT→1000LUNCUSDT · TOMOUSDT→VICUSDT ·
DODOUSDT→DODOXUSDT

KEEPUSDT, NUUSDT ve TUSDT birleşme olduğu için zincir sayılmaz. Sonuç `data/split.csv`
dosyasına sembol, varlık anahtarı ve grup sütunlarıyla yazılır ve commit edilir.

**Dönemler.**

| Küme | Coinler | Tarih aralığı | Kullanım |
|---|---|---|---|
| KEŞİF | A | 2020-01-01 → 2025-08-31 | Serbest keşif, ızgara seçimi |
| C1 | B | 2020-01-01 → 2025-08-31 | Onay (coin genellemesi), tek atış |
| C2 | A + B | 2025-09-01 → 2026-08-31 | Onay (zaman genellemesi), tek atış |

C1 ve C2 verisine keşif sırasında hiçbir biçimde bakılmaz. Olay sayıları dahil.

**Küme sınırı ve ufuk.** Bir olayın birincil ufku, ait olduğu kümenin tarih
aralığına tam olarak sığmalıdır. Sığmayan olay o kümede hiç oluşmaz; kırpılmış
getiri kullanılmaz. İkincil ufuklar raporlanırken aynı kural kendi ufuk
uzunluklarıyla uygulanır. Kümeler arası veri ödünç alınmaz: keşif kümesindeki bir
olayın ufku C2 verisine uzanamaz.

**Küme sınırı ve geriye bakış.** Geriye bakış pencereleri de kümenin tarih aralığına
sığmalıdır. Penceresi küme başlangıcından önceki veriye uzanan barda olay ya da kontrol
oluşmaz; pencere o veriyi ödünç almaz. Bu kural dönem kurallarına ek olarak
uygulanır ve kod düzeyinde ayrıca doğrulanır — verinin küme sınırında kesilmiş olmasına
dayanılmaz.

## 4. Getiri tanımları

Olay t barının kapanışında tespit edilir. Giriş fiyatı `P0 = open[t+1]`. Ufuk h bar sonra çıkış fiyatı `P1 = close[t+h]`.

**Fiyat okuma tabanı (rev.8).** Olay, sinyalin hesaplandığı ızgarada tespit edilir (H1, H2: 4h; H3: 1d). Pozisyonun bütün fiyat okumaları ise her hipotezde dönem içi 4h barlardan yapılır. Giriş anı, t barının kapanış anıdır. `P0`, açılışı giriş anına eşit olan dönem içi 4h barın açılışıdır; böyle bir bar yoksa olay oluşmaz. Hedef çıkış anı `T = giriş anı + h × adım`'dır. `P1`, kapanışı T'ye eşit olan dönem içi 4h barın kapanışıdır. Eksiksiz günlerde bu tanımlar `open[t+1]` ve `close[t+h]` ile aynı sonucu verir; fark yalnızca kısmi günlerde ve dönem sonlarında ortaya çıkar. Gerekçe: dönem sınırları 4h düzeyindedir; fiyat okumalarını da aynı düzeye bağlamak, 1d ızgarasının dönem sınırıyla her kesişiminde ayrı bir kural gerekmesini önler.

- **Brüt short getirisi:** `-(P1 / P0 - 1)`
- **Funding katkısı:** giriş ile çıkış arasındaki her funding anında `+oran`
  (pozitif oran short'a ödeme demektir, negatif oran short'tan kesinti).

  **Funding ödemesinin sınırları.** Pozisyon, giriş anından sonra ve çıkış anına kadar gerçekleşen funding ödemelerini alır ya da öder: giriş anındaki ödeme hariç, çıkış anındaki dahildir. Aynı an ölçütü §4 "Zaman toleransı"nda tanımlıdır. Çıkış anındaki ödeme kümenin tarih aralığı dışına düşüyorsa olay o kümede oluşmaz.
- **Dönem sonu istisnası (rev.8).** Dönem sonuna ulaşan pozisyonda funding penceresi dönem bitişinde (B, dahil) kapanır. B'den sonraki ödemeler, çıkış anındaki (K) ödeme dahil, hesaba girmez; tamlık kontrolü bu pozisyonlarda son ödemeyi B'ye göre arar. Gerekçe: dönem sonunda işlem durmuştur; uzlaşmadan sonra pozisyon, dolayısıyla funding yoktur. Çıkış fiyatı yine K'daki kapanıştır, çünkü o bar uzlaşma fiyatını taşır. Bu istisnanın bu revizyona hangi bilgiyle girdiği Revizyon Günlüğü 8'de yazılıdır.
- **Zaman toleransı (rev.8).** Projedeki bütün zaman karşılaştırmalarında iki an arasındaki fark 1 dakikadan kesin olarak küçükse bu iki an aynı sayılır; tam 1 dakikalık fark aynı an değildir. Ön-kayıttaki "tolerans payı" ve "funding tolerans payı" ifadeleri bu tanıma dayanır.
- **Maliyet:** gidiş-dönüş `0.20%`.
- **Net short getirisi:** `brüt + funding - 0.0020`
- **MAE (en kötü ara zarar):** `max(H, P1) / P0 - 1`. H, açılışı giriş anından önce olmayan ve kapanışı çıkış anından sonra olmayan bütün dönem içi 4h barların en yüksek high değeridir; böyle bar yoksa yalnızca P1 kullanılır. Izgaradan bağımsız olarak 4h barlardan hesaplanır; eksiksiz günlerde 1d tanımıyla aynı sonucu verir. P1'in dahil edilmesi, ileri kaymada boşluk üzerinden gelen çıkış fiyatının ara zarar olarak kaybolmasını önler. Eksik barlar MAE'yi hesaplanamaz yapmaz, ancak boşluk süresince ara zarar gözlenemez; bu sınırlama raporda yazılır. Raporlanır, eşik değildir. (rev.8)

Ufuk içinde sözleşme delist olursa bu bir dönem sonudur; çıkış §4 "Dönem sonu ve çıkış" kuralına göre dönemin son 4h barının kapanışıdır. (rev.8)

**Dönem sonu ve çıkış.** Hedef çıkış anı T, dönem kapanışından (K) sonraysa pozisyon dönem sonuna ulaşmış sayılır; karşılaştırma kapanış anlarıyla yapılır. Dönem sonuna ulaşan pozisyon, hangi ızgarada olursa olsun, dönemin son 4h barının kapanışından çıkar: `P1` o barın kapanışıdır, çıkış anı K'dır. Dönem sonu ve delist kuralları ileri kayma kuralından önceliklidir: önce T > K denetlenir; ileri kayma kuralı yalnızca T ≤ K ise uygulanır. T ≤ K iken hedef bar eksikse, sonraki mevcut dönem içi 4h bar her zaman B'de ya da B'den önce açılır; ileri kayma dönem dışına taşmaz. Verinin sonu dönem sonu değildir ve bu kural o sınıra uygulanmaz. Son veri barı C2 kümesinin sonundan (2026-08-31 23:59:59 UTC) önce açılır ve 1 saniye sonra kapanır; bu yüzden verinin sonuna uzanan her ufuk C2 küme sonunu da aşar ve §4 "Olayın kümede oluşma ölçütü"yle oluşmaz. (rev.8)

**İleri kaymanın üst sınırı.** Hedef çıkış barı eksikse ileri kayma, olayın birincil
ufku kadar süre ile sınırlıdır (H1 ve H2 için 18 bar, H3 için 14 gün). Sonraki mevcut
bar bu sınırdan uzaksa olay oluşmaz; kırpılmış getiri kullanılmaz.

**Olayın kümede oluşma ölçütü.** Bir olayın kümede oluşup oluşmadığına tek bir karar noktası hükmeder ve ölçüt çıkış anına göre uygulanır: çıkış anı ile funding tolerans payı birlikte küme sonunu aşmamalıdır. Çıkış anı, ızgaranın adımından türetilmez; §4'teki tanımlarla belirlenen gerçek çıkış anıdır: olağan çıkışta T, ileri kaymada sonraki barın açılışı, dönem sonunda K. Aynı karar noktasında pozisyonun funding tamlığı da sağlanmalıdır (§4 "Funding aralığı geçişleri"): funding'i tam olmayan olay ya da kontrol, brüt getiri dahil hiçbir hesapta oluşmaz. Böylece brüt ve net olay kümeleri her zaman aynıdır. Fiyat ve funding için ayrı ölçüt kullanılmaz. Bu tanım olay kümesini değiştirebilir (örneğin keşif kümesinin sonuna yakın biten dönemlerde); değişiklik getiri görülmeden, tanım gereği yapılmıştır. (rev.8)

**Funding aralığı geçişleri.** Funding kayıtlarındaki aralık alanı bir sonraki ödemeye kalan süreyi gösterir. Tamlık kontrolü buna göre yapılır: iki ödeme arasındaki boşluk, iki kaydın aralıklarından büyüğünü ve tolerans payını aşarsa ödeme eksik sayılır. Pencerenin başı için de aynı kural geçerlidir: giriş anı ile penceredeki ilk ödeme arasındaki boşluk, ilk kaydın aralığını ve tolerans payını aşarsa ödeme eksik sayılır. Penceresinde hiç funding kaydı bulunmayan pozisyonun funding'i tam değildir. (rev.8) Bilinen sınır: aralık 1 saate düşüp yeniden 4 saate hizalanırken pencere kapanışına denk gelen kayıt hesaba giremez ve değer hesaplanmaz; bunu ayırt etmek geleceğe bakış gerektirir. F1 ölçümünde bu durum, 4 saatten 1 saate geçişleri kapsayan 888 funding penceresinin 6'sında görülmüştür.

| Hipotez | Birincil ufuk | İkincil ufuklar (yalnızca rapor) |
|---|---|---|
| H1, H2 | 18 bar (3 gün) | 6 bar, 42 bar |
| H3 | 14 gün | 7 gün, 30 gün |

## 5. Hipotezler

**Pencere sınırları.** Her koşulun geriye bakış penceresinin t barını içerip
içermediği, §5'teki formülle belirlenir ve uygulamada açıkça belirtilir. H1'in
6 barlık dip penceresi ve H2'nin k barlık kırılım penceresi t'yi **içermez**
(t-6..t-1, t-k..t-1). H2'nin 30 barlık yükseliş penceresi ve H1'in 180 barlık
hacim penceresi t'yi **içerir**. Varsayılan davranış yoktur; belirtilmeyen çağrı
hata verir.

Her hipotezin keşif ızgarası en fazla 9 yapılandırmadır. Aynı coinde bir olaydan
sonra, o hipotezin birincil ufku boyunca yeni olay sayılmaz (bekleme süresi).

### H1 — Başarısız pump

**Mekanizma.** Kısa sürede sert yükselen coinde geç gelen alıcılar tükenir. Yükseliş
başarısızlığı teyit edilince satış zincirleme hızlanır.
**Karşı taraf.** Tepeye yakın giren FOMO alıcıları.

1. **Pump barı:** `close[t] / min(low[t-6..t-1]) - 1 ≥ θ`
   ve son 6 barın toplam hacmi ≥ önceki 180 barın 6'lı toplam hacim medyanının 3 katı.

   H1'in 6'lı toplam hacim medyanı kayan pencereyle hesaplanır: her bar için son 6 barın
   toplamı alınır ve bu toplamların 180 barlık medyanı kullanılır. Ardışık, çakışmayan
   bloklara bölünmez.

   H1'in 180 barlık hacim medyanı t barını içerir; 6 barlık toplam pencereleri t barını içerir. H1'in 6 barlık dip penceresi (`low[t-6..t-1]`) t barını içermez.

2. **Tepe:** pump barından itibaren görülen en yüksek `high`, en fazla 12 bar izlenir.
3. **Olay (başarısızlık teyidi):** pump barından sonraki 12 bar içinde ilk kez
   `close ≤ tepe × (1 - δ)` olan ve aynı barda `high < tepe` olan bar.
   12 bar içinde teyit gelmezse pump düşer, olay sayılmaz.
4. **Geçersizlik seviyesi (F4 için kayıt):** `tepe × 1.02`

**Izgara:** `θ ∈ {0.20, 0.30, 0.40}` × `δ ∈ {0.08, 0.12, 0.16}`

### H2 — Kalabalık long'ların çözülmesi (ana aday)

**Mekanizma.** Funding aşırı pozitifken piyasa kaldıraçlı long'larla doludur. Önce
yükselmiş fiyat yapısını aşağı kırınca long likidasyonları zincirleme satış yaratır.
**Karşı taraf.** Aşırı kaldıraçlı long pozisyonlar. Funding short'un lehinedir.

1. **Kalabalık:** t anına kadarki son 24 saatteki funding oranlarının ortalaması
   (8 saate normalleştirilmiş) ≥ φ.
2. **Önceki yükseliş:** `close[t] / close[t-30] - 1 ≥ 0.10` (son 5 gün).
3. **Olay (yapı kırılımı):** `close[t] < min(low[t-k..t-1])`.
4. **Geçersizlik seviyesi (F4 için kayıt):** `max(high[t-30..t]) × 1.02`

**Izgara:** `φ ∈ {0.03%, 0.05%, 0.10%}` × `k ∈ {3, 6, 12}`

### H3 — Ölmekte olan coin

**Mekanizma.** İlgisi biten coinde hacim erir, likidite çekilir, sahipler çıkış arar.
**Karşı taraf.** Çıkamayan sahipler ve zorunlu satıcılar.

1. **Hacim çöküşü:** son 30 günün medyan günlük hacmi ≤ (1 - ν) × gün −120 ile −31
   arasındaki medyan günlük hacim.
2. **Düşüş trendi:** `close[t] < SMA50[t]` ve `close[t] / close[t-30] - 1 ≤ -τ`.
3. **Olay:** iki koşulun birlikte sağlandığı ilk gün.

**Izgara:** `ν ∈ {0.50, 0.65, 0.80}` × `τ ∈ {0.15, 0.25, 0.35}`

## 6. Kontroller

Her olay için iki ayrı kontrol kümesi üretilir. Kontrol barları da aynı uygunluk
filtresinden geçmek zorundadır.

- **K1 — aynı coin, rastgele zaman.** Aynı coinden, aynı küme ve dönem içinden,
  o hipotezin herhangi bir olayına birincil ufuk mesafesinden yakın olmayan
  10 rastgele bar.
- **K2 — aynı zaman, rastgele coin.** Aynı t barında uygun olan ve o anda olay üretmemiş diğer coinlerden 10 rastgele coin.
- **Dönem üyeliği (rev.8).** Bir bar, onu oluşturan bütün 4h barlar aynı dönemin içindeyse dönem içidir: 4h barda açılış [dönem başı, B] aralığındadır; 1d barda §2 "1 günlük barlar"daki altı barın tamamı dönem içidir. Olay barı t, K1'in "aynı küme ve dönem içinden" koşulu ve K2'nin "aynı t barında uygun" koşulu bu ölçütü kullanır. Kontrol barları, olaylarla aynı fiyat okuma tabanına, dönem sonu kuralına ve tek karar noktasına tabidir.

K2 piyasa yönünü ayıklar ve bu projede **en önemli kontroldür**.

## 7. İstatistik

- **Test istatistiği:** `ortalama(olay net getirisi) - ortalama(kontrol net getirisi)`
- **p-değeri:** 10.000 tekrarlı eşleştirilmiş yeniden örnekleme. Her tekrarda her
  olayın kontrol havuzundan bir kontrol çekilir. `p = (r + 1) / (10000 + 1)`,
  tek yönlü (olay short'u daha iyi).
- **Çoklu test:** üç hipotez için Bonferroni, `α = 0.05 / 3 = 0.0167`.
- **Tohum:** `20260911`, sonuç dosyalarına yazılır.

## 8. Keşif kuralları (F2)

1. Her hipotezin 9 yapılandırmasının hepsi KEŞİF kümesinde hesaplanır ve **hepsi raporlanır**.
2. Aday yapılandırmalar: olay sayısı ≥ 150 olanlar.
3. Adaylar arasından K2 farkı en yüksek olan seçilir.
4. Seçilen yapılandırma için şu iki koşul keşifte sağlanmıyorsa hipotez **onaya
   gönderilmeden kapanır** (onay verisi harcanmaz):
   - K2 farkı > 0
   - ortalama net getiri > 0
5. Seçim, onay koşusundan önce `analysis/<hipotez>/KILIT.md` dosyasıyla commit edilir.

## 9. Onay kuralları (F3)

Seçilen yapılandırma C1 ve C2'de birer kez koşulur. Hipotez ancak **her iki kümede
de** aşağıdaki koşulların tamamını sağlarsa **GEÇTİ** sayılır:

1. K1'e karşı `p < 0.0167`
2. K2'ye karşı `p < 0.0167`
3. Ortalama net short getirisi > 0
4. K2 farkı ≥ +1.0 yüzde puan (birincil ufukta)
5. Net getiriye en çok katkı yapan 3 coin çıkarıldığında ortalama net getiri hâlâ > 0
6. Olay sayısı ≥ 100. Altındaysa hüküm **YETERSİZ GÜÇ** olur, GEÇTİ sayılmaz.

Her koşunun sonucu, sonuç ne olursa olsun `ONAY_KAYDI.md` dosyasına eklenir.
Başarısız bir hipotez için onay yeniden koşulamaz.

## 10. Raporlanacak ek bilgiler (eşik değil)

- MAE dağılımı (p50, p90, p95, p99), olay ile K1 karşılaştırmalı
- Yıllara göre olay sayısı ve ortalama net getiri
- Funding katkısının net getirideki payı
- H1 ile H2 olaylarının örtüşme oranı
- BTC rejimine göre ayrım (BTC kapanışı 100 günlük ortalamanın üstünde / altında)

---

## Revizyon Günlüğü

| Sürüm | Tarih | Değişiklik | Gerekçe | Etkilenen sonuçlar |
|---|---|---|---|---|
| 1 | — | İlk sürüm | — | — |
| 2 | 2026-09-11 | Kapsam netleştirmesi (TRADIFI_PERPETUAL dışı), kesin hariç tutma listesi, 1d türetme kuralı, listeleme dönemi ve karantina kuralı, veri bütünlüğü kontrolü, varlık anahtarıyla bölme | exchangeInfo sınıflandırması, yeniden adlandırma zincirlerinin bölmeyi sızdırması ve SETTLED kayıtlarının yeniden fiyatlandırma sıçraması riski. Hiçbir fiyat verisine bakılmadan yapıldı. | Yok (henüz sonuç yok) |
| 3 | 2026-09-11 | Funding aralığı metni genel formüle bağlandı; veri boşluğu kuralı (zamanla tanımlı pencere, tamlık şartı, ufukta ileri kayma); delist kapsamasının tam olduğu notu | F1 denetimi: 8 saat dışında dört farklı funding aralığı; 10 boşluk olayı ve bunların ardından oluşan iki sahte sıçrama. Hiçbir getiri hesaplanmadan yapıldı. | Yok (henüz sonuç yok) |
| 4 | 2026-09-13 | Küme sınırı ve ufuk kuralı; karantinanın çıkışa uygulanması; pencere sınırlarının açık belirtilmesi; evren tablosunun commit edilmesi | F2 öncesi metodoloji denetimi (B1, B2, B3, B10): ön-kayıtta tanımsız kalan ve ilk getiri hesabında devreye girecek noktalar. Hiçbir getiri hesaplanmadan yapıldı. | Yok (henüz sonuç yok) |
| 5 | 2026-09-13 | Geriye bakış pencerelerinin küme sınırını aşamayacağı açıkça yazıldı | F2 öncesi sızıntı testleri: kural yalnızca verinin kesilmiş olmasıyla sağlanıyordu, kod düzeyinde garanti edilmiyordu. Hiçbir getiri hesaplanmadan yapıldı. | Yok (henüz sonuç yok) |
| 6 | 2026-09-13 | Funding ödemesinin giriş/çıkış sınırları; ileri kaymanın üst sınırı; uygunluk penceresinin t gününü dışlaması; H1 hacim medyanının kayan pencere okuması; revizyon 4-5 tarih düzeltmesi | F1 kapanış denetimi: ön-kayıtta tanımsız kalan ve F2'de ilk getiri hesabında devreye girecek dört nokta. Hiçbir getiri hesaplanmadan yapıldı. | Yok (henüz sonuç yok) |
| 7 | 2026-09-13 | Karantina kuralı kaldırıldı, yerine dolgu koşusu ve uzun boşluk temelli dönem bölme geldi; dönem sınırları bar düzeyine indi; funding'siz dönemler tüm hipotezlerden çıkarıldı; uzlaşma sonrası funding kayıtları yok sayıldı; delist sayısı ve hayatta kalma yanlılığı hükmü düzeltildi; olayın kümede oluşma ölçütü tek kapıya bağlandı; funding aralığı geçişlerinde tamlık tanımı; ileri kaymanın ölçüsü; H1 pencere sınırları | F1 kapanış ölçümleri (D1, D2, D3, V1, V2, S1–S3): 131 sembolde uzlaşma sonrası dolgu barların dönem sonunu yıllarca uzattığı, SETTLED aylarının yeniden fiyatlandırma değil yeniden listeleme olduğu ve delist sayısının eksik saptandığı belirlendi. Hiçbir getiri hesaplanmadan yapıldı. | Yok (henüz sonuç yok) |
| 8 | 2026-09-21 | 4h fiyat okuma tabanı, dönem sonu funding istisnası, 1d kısmi gün kuralı, tek karar noktasında funding tamlığı, sayı düzeltmeleri, denetim sınırı aşımı kaydı | ayrıntı tablonun altında | Yok (henüz sonuç yok) |

### Revizyon 8 — ayrıntı

**8.** Tarih: 2026-09-21. Değişiklikler: 4h fiyat okuma tabanı (giriş, çıkış, MAE ve çıkış anı her ızgarada dönem içi 4h barlardan); dönem bitişi (B) ve dönem kapanışı (K) tanımları; "ufuk dönem sonunu aşar" ölçütünün kapanış anlarına bağlanması ve ileri kaymayla sıralaması; delistin dönem sonu olarak tanımlanması; 1d barların yalnızca dönem içi, hizalı altı 4h bardan kurulması ve bu serinin sinyal, uygunluk ve kontrollerde tek olması; MAE'nin 4h barlardan ve çıkış fiyatını da içerecek şekilde tanımlanması; dönem sonu funding istisnası; tek zaman toleransı tanımı; funding tamlığının başlangıç boşluğunu da kapsaması ve tek karar noktasına eklenmesi; funding'siz dönem sayım penceresi; dönem üyeliği tanımı; SETTLED için tek kaynak kuralı; WAVESUSDT/KNCUSDT kararı; sayı düzeltmeleri.

**Gerekçe.** F1 denetiminin son turları, bugünkü kodun 1d ızgarasında dönem sonunda dolgu barlarından fiyat okuduğunu (rev.7'nin "dolgu barları hiçbir hesaba girmez" ve bar düzeyinde sınır kurallarının ihlali) ve dönem sonunu aşan pozisyonların 128 SETTLING sembolün 78'inde, 1d ızgarasında 168 dönem sonunun 167'sinde funding tamlığı bozulduğu için sessizce düştüğünü gösterdi (RESULTS §14.7, §14.8). Metodoloji denetçisi, aday kuralın sekiz tanımsız noktasını listeledi; bu revizyon hepsini tanımlar. 4h fiyat okuma tabanı ayrıca t+1 günü kısmi son gün olan H3 olaylarının kaybını önler; bu olaylar delistten hemen önceki dönemlere düşer ve düşürülmeleri hayatta kalma yanlılığı yaratırdı.

**Rev.7 düzeltme notu (errata).** Rev.7 gerekçesindeki "131 sembolde uzlaşma sonrası dolgu barların dönem sonunu yıllarca uzattığı" ifadesi düzeltilir: uzlaşma sonrası dolgusu olan sembol sayısı 145'tir; bunların 45'inde uzatma en az bir yıl, 15'inde en az iki yıldır. Rev.7 kaydının kendisi değiştirilmemiştir. §2'deki 14 → 18 ve 38 → 57 düzeltmeleri yürürlükteki metinde yapılmıştır. Üç sayı da `rapor_sayilari` betiğinden üretilmiştir (RESULTS §14.1).

**Denetim sınırı aşımı ve bu revizyonla ilişkisi.** A1 ölçümünde (commit 1093e69) uzlaşma sonrası 23 funding kaydının oran değerleri ve işaretleri raporlandı. Bu, §3.1'deki veri denetimi sınırını aştı. Kayıtların 5'i C1 grubundaki sembollere aittir; C2 dönemine ait kayıt içermez. Ayrıntılar RESULTS §14.5'tedir. Bu revizyondaki dönem sonu funding istisnası, bu bilgi görüldükten sonra ön-kayda yazılmıştır. Yön bilgisi açıkça beyan edilir: istisnanın dışarıda bıraktığı bu 23 kaydın 18'i pozitiftir, yani short lehine ödemedir; istisna, dönem sonuna ulaşan short pozisyonların net getirisini düşürür. İstisna görülen 23 kaydın tamamını hesaptan çıkarır; görülen hiçbir oran değeri getiri hesabına girmez. Aynı koşu, exchangeInfo'da bulunmayan sembollerin son barlarındaki 28 funding kaydının oran değerlerini de iz dosyasına yazmıştır; bunların bir kısmı C2 dönemine aittir. Bu 28 kaydın 23'ü dönem bitişindedir (B), istisnanın kapsamı dışında kalır ve getiri hesabına girer. İstisnanın dayandığı eğilim (funding penceresinin son barın açılışında bitmesi) araştırma tarafının çalışma notlarında oran değerleri ölçülmeden önce yazılmıştır, ancak bu depoda doğrulanabilir değildir. İstisnanın gerekçesi yöne değil ilkeye dayanır: uzlaşmadan sonra pozisyon yoktur. Bu revizyon hiçbir getiri hesaplanmadan yazılmıştır.
