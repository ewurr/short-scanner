# PREREGISTRATION.md — Short Öngörü Hipotezleri

**Durum:** Sürüm 13 (2026-10-10). F2 keşif aşaması başlamadan önce, hiçbir getiri hesaplanmadan commit edildi.
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

**1 günlük barlar.** 1d barlar yalnızca dönem içi 4h barlardan türetilir: UTC günü; open ilk, high en yüksek, low en düşük, close son değer; volume ve quote_volume toplam. Bir gün, yalnızca o günün 00:00, 04:00, 08:00, 12:00, 16:00 ve 20:00 UTC açılışlı altı 4h barının tamamı mevcut ve aynı dönemin içindeyse oluşur; aksi hâlde o gün eksik (NaN) sayılır. Bir barın mevcut sayılması için satırının bulunması yetmez (rev.11): fiyat ve hacim hücrelerinin tamamı sayı olmalıdır. Hücrelerinden biri NaN ya da sonlu değilse o bar eksiktir ve günü düşürür; eksik hücre sıfır sayılmaz. Bu, barın mevcutluğunun genel tanımıdır (rev.12): ölçüt alan düzeyinde değil bar düzeyindedir ve her ızgarada, her pencerede ve her hesapta geçerlidir — hücresi bozuk bir bar 4 saatlik sinyal pencerelerinde de mevcut sayılmaz, ilgili hücresi geçerli olsa bile. İşlem sayısı (`count`) bu kuralın kapsamı dışındadır: hiçbir olay, uygunluk ya da getiri hesabına girmediği için eksikliği barı düşürmez, yalnızca o günün `count` toplamını eksiltir. F1 ölçümünde dönem içi 4h barlarda böyle bir hücre bulunmamıştır, yani bu kural bugünkü veride hiçbir günü düşürmez. Bu yüzden dönemin kısmi ilk ve son günleri 1d serisinde yer almaz. Bu seri tektir: H3'ün sinyal pencereleri, bütün hipotezlerin uygunluk hacmi ve K1/K2 havuzlarının 1d barları aynı seriden gelir. (rev.8)

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
  (NaN). O barda olay ya da kontrol oluşmaz. Bu, H1'in hacim ve yükseliş pencerelerini, H1'in tepe penceresini, H2'nin 30 barlık ve k barlık pencerelerini, H3'ün hacim pencerelerini, H3'ün düşüş trendi oranını ve SMA50'yi, ayrıca uygunluk hacmini kapsar; pencerelerin sınırları §5 "Pencere sınırları"nda tanımlıdır. (rev.11) H2'nin 24 saatlik funding ortalaması penceresi bar değil kayıt
  tabanlı olduğu için ayrı tanımlanır: §4 "Funding sinyal penceresinin tamlığı". Sonucu
  aynıdır — değer hesaplanmazsa o barda olay ya da kontrol oluşmaz. (rev.9)
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

C1 ve C2 verisine keşif sırasında hiçbir biçimde bakılmaz. Olay sayıları dahil. Bu kural veriye erişimin her yolunu kapsar, önbellek dahil (rev.13): onay kümesi verisinin bellekte ya da diskte tutulan bir kopyası, açık bir onay koşusu olmadan okunabilir hâle gelirse kural delinmiş olur. Bu yüzden kümeye göre kesilmiş veri diske yazılmaz, bellekte tutulan her kopya için erişim denetimi kopyanın her okunuşunda yeniden uygulanır, ve onay koşusunun açılışı ile kapanışı bu kopyaları geçersiz kılar.

**Koşuların ağ erişimi (rev.13).** F2 ve F3 koşuları ağa çıkmaz: veri koşudan önce indirilir ve koşu dondurulmuş yerel önbellekten okur. Gerekçe tekrarlanabilirliktir — koşu sırasında yapılan bir ağ isteği sonucu borsanın o anki durumuna bağlar ve aynı koşunun sonradan yeniden üretilmesini garanti edilemez hâle getirir.

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

**Dönem sonu ve çıkış.** Hedef çıkış anı T, dönem kapanışına (K) eşit ya da ondan sonraysa pozisyon dönem sonuna ulaşmış sayılır; karşılaştırma kapanış anlarıyla yapılır. (rev.9: eşitlik dahil edildi; çıkış anı K olan pozisyonda da uzlaşmadan sonra pozisyon yoktur, dolayısıyla dönem sonu funding istisnası uygulanır.) Dönem sonuna ulaşan pozisyon, hangi ızgarada olursa olsun, dönemin son 4h barının kapanışından çıkar: `P1` o barın kapanışıdır, çıkış anı K'dır. Dönem sonu ve delist kuralları ileri kayma kuralından önceliklidir: önce T ≥ K denetlenir; ileri kayma kuralı yalnızca T < K ise uygulanır. (rev.9) T < K iken hedef bar eksikse, sonraki mevcut dönem içi 4h bar her zaman B'de ya da B'den önce açılır; ileri kayma dönem dışına taşmaz. (rev.9) Verinin sonu dönem sonu değildir ve bu kural o sınıra uygulanmaz. Son veri barı C2 kümesinin sonundan (2026-08-31 23:59:59 UTC) önce açılır ve 1 saniye sonra kapanır; bu yüzden verinin sonuna uzanan her ufuk C2 küme sonunu da aşar ve §4 "Olayın kümede oluşma ölçütü"yle oluşmaz. (rev.8)

**İleri kaymanın üst sınırı.** Hedef çıkış barı eksikse ileri kayma, olayın birincil
ufku kadar süre ile sınırlıdır (H1 ve H2 için 18 bar, H3 için 14 gün). Sonraki mevcut
bar bu sınırdan uzaksa olay oluşmaz; kırpılmış getiri kullanılmaz.

**Olayın kümede oluşma ölçütü.** Tek karar noktasının onayı, bir olayın oluşması için gereklidir ama yeterli değildir (rev.12): §5'teki dizi kuralları (bekleme süresi, H1'de tek izleme, H3'te ilk gün) da sağlanmalıdır. Olay kümesi yalnızca iki koşulun birlikte sağlandığı barlardan oluşur; dizi kurallarından geçmemiş bir onay olay değildir ve hiçbir hesaba, hiçbir kontrol ölçütüne girmez. Bir olayın kümede oluşup oluşmadığına tek bir karar noktası hükmeder ve ölçüt çıkış anına göre uygulanır: çıkış anı ile funding tolerans payı birlikte küme sonunu aşmamalıdır. Çıkış anı, ızgaranın adımından türetilmez; §4'teki tanımlarla belirlenen gerçek çıkış anıdır: olağan çıkışta T, ileri kaymada sonraki barın açılışı, dönem sonunda K. Aynı karar noktasında pozisyonun funding tamlığı da sağlanmalıdır (§4 "Funding tamlığı"): funding'i tam olmayan olay ya da kontrol, brüt getiri dahil hiçbir hesapta oluşmaz. Uygunluk da bu karar noktasının parçasıdır (rev.9): hacim eşiği ve listeleme yaşı dahil uygunluk filtresi, olaylar ve kontroller için aynı karar noktasında, aynı çağrıyla uygulanır. Uygunluk değerinin hesaplanabilmiş olması yeterli değildir; eşiği de geçmelidir. Uygunluğu karar noktasının dışında uygulayan bir kod yolu, §6'nın "Kontrol barları da aynı uygunluk filtresinden geçmek zorundadır." şartını sessizce delebileceği için kabul edilmez. Böylece brüt ve net olay kümeleri her zaman aynıdır. Fiyat ve funding için ayrı ölçüt kullanılmaz. Bu tanım olay kümesini değiştirebilir (örneğin keşif kümesinin sonuna yakın biten dönemlerde); değişiklik getiri görülmeden, tanım gereği yapılmıştır. (rev.8)

**Pozisyonun funding ritmi (rev.10).** Bir pozisyonun funding ritmi, §4 "Funding tamlığı"ndaki kayıt dizisinin (çapadan pencere sonundaki son kayda kadar) son kaydının aralık alanıdır, saat cinsinden; bu, kısmi kuyruğun uzunluğunu belirleyen aralıktır. Dizideki bütün kayıtların aralık alanı aynı değilse pozisyon ayrıca "karışık ritimli" işaretlenir ve yine son kaydın aralığına göre sınıflanır; karışık ritimlilerin payı her sınıfta ayrıca yazılır. Aralık alanı 8, 4, 2 ya da 1 saat dışında bir değerse pozisyon "sınıflanmamış" sınıfında raporlanır. Çapası olmayan pozisyon oluşmadığı için sınıflanmaz.

**Ufuk değerlerinin bağlanması (rev.10).** Birincil ufuk, ikincil ufuklar ve ileri kayma sınırı yalnızca bu ön-kayıtta tanımlıdır: H1 ve H2 için 4h ızgarada birincil 18 bar, ikincil 6 ve 42 bar, ileri kayma sınırı 18 bar; H3 için 1d ızgarada birincil 14 gün, ikincil 7 ve 30 gün, ileri kayma sınırı 14 gün. Kod bu değerleri tek bir yerden, ön-kayıt değeri olarak okur; getiri, olay ya da kontrol üreten hiçbir çağrı serbest bir ufuk değeri kabul etmez. Bekleme süresi de (§5) birincil ufka bağlıdır. İkincil ufuklar yalnızca raporlanır; onay kararları birincil ufka göre verilir. İkincil ufuklar yalnızca seçilen yapılandırma için hesaplanır (rev.13): §8'in ızgara raporu ve yapılandırma seçimi birincil ufka dayanır, ikincil ufuklar seçim yapıldıktan sonra, olaylar ve kontrolleri için birlikte hesaplanır. Gerekçe: ikincil ufuktaki fark kontroller olmadan anlamsızdır, ama dokuz yapılandırmanın tamamı için hesaplanması hiçbir hükmü değiştirmeden maliyeti üç katına çıkarırdı.

**Ölçüm raporlamasının küme sınırı (rev.10).** F1'in bütünlük ve tamlık ölçümleri varsayılan olarak yalnızca keşif kümesi için raporlanır. Onay kümelerine ait bir sayı raporlanacaksa gerekçesi ölçümle birlikte yazılır ve sayının hangi kümeye ait olduğu açıkça belirtilir. Bu kural §3'ün onay verisine bakmama şartının ölçüm tarafındaki karşılığıdır; zaten raporlanmış olan bütünlük sayıları (rev.8 ve rev.9 metinlerindeki evren toplamları) geriye dönük olarak kaldırılmaz, bundan sonrası için geçerlidir.

**Funding tamlığı (rev.9).** Funding kayıtlarındaki aralık alanı, kaydın alındığı anda bir sonraki ödemeye kalan süreyi gösterir. Aralık sonradan değişebildiği ve değişim anı kayıtlardan okunamadığı için bu alan, bir sonraki ödemenin zamanını kesin olarak vermez. Tamlık kontrolü bu yüzden ödeme anı tahmin etmez; yalnızca kayıtlar arasındaki boşlukları ölçer. Kural şu maddelerden oluşur:

- **Çapa.** Pozisyonun funding penceresinde çapa, giriş anında ya da öncesinde kalan son dönem içi kayıttır. Çapa yoksa funding tam değildir.
- **Zincir.** Çapadan pencere sonuna kadar art arda gelen iki kayıtta sonraki kayıt, öncekinin üstüne iki kaydın aralıklarından büyüğü ve tolerans payı eklenerek bulunan andan sonra olamaz; olursa arada en az bir ödeme eksiktir ve funding tam değildir.
- **İlk çift.** Çapa ile ondan sonraki ilk kayıt arasındaki boşluk ölçülürken taban çapa değil giriş anıdır: giriş anında ya da öncesinde kalan eksik ödemeler pozisyonu ilgilendirmez (§4 "Funding ödemesinin sınırları").
- **Son.** Penceredeki son kayıttan sonra, o kaydın aralığı ve tolerans payı pencere sonundan önce dolmamalıdır; tam pencere sonuna denk gelmesi yeterlidir.
- **Geçerli aralık (rev.10).** Dizideki her kaydın aralık alanı sonlu ve sıfırdan büyük olmalıdır; değilse funding tam değildir. Bu koşul kodda rev.9 döneminde de uygulanıyordu ama ön-kayıtta yazılı değildi; F1 ölçümünde veride geçersiz aralık alanlı kayıt bulunmamıştır, yani bugün hiçbir pozisyonu elemez.
- **Geçerli oran (rev.11).** Pozisyonun funding penceresine giren her kaydın oran değeri sonlu bir sayı olmalıdır; NaN, +sonsuz ya da −sonsuz oran taşıyan pozisyonun funding'i tam değildir ve pozisyon oluşmaz. Toplamın işaretine ya da büyüklüğüne bakılmaz; denetim kayıt düzeyindedir. Denetlenen kayıtlar ödeme penceresine girenlerdir (rev.12): giriş anından sonra, pencere sonuna kadar dahil. Çapanın oranı toplama girmediği için (§4 "Funding ödemesinin sınırları": giriş anındaki ödeme hariç) çapa bu denetimin dışındadır.

Beklenen ödeme anı yukarıdaki maddeler dışında hiçbir yerde üretilmez. (rev.10) Pencere sonu, dönem sonu çıkışlarında B'dir. Bu kural rev.8'in başlangıç boşluğu ve "penceresinde hiç funding kaydı bulunmayan pozisyon" cümlelerinin yerine geçer; rev.8'deki 4 saatten 1 saate geçişle ilgili bilinen sınır cümlesi, kural artık ödeme anı üretmediği için konusuz kalmış ve kaldırılmıştır. Kuralın gevşek kaldığı yerler §4 "Funding tamlığının bilinen sınırları"nda sayılmıştır.

**Funding sinyal penceresinin tamlığı (rev.9).** H2'nin funding ortalaması penceresi (§5 H2 madde 1) bar değil kayıt tabanlıdır; tamlığı yukarıdakiyle aynı yapıda kurulur. Pencere t barının kapanışında biter ve 24 saat geriye uzanır. Çapa, pencere başında ya da öncesinde kalan son kayıttır ve dönem başı ile küme başının geç olanından önce olamaz (§3 "Küme sınırı ve geriye bakış"); çapa yoksa değer hesaplanmaz ve o barda olay ya da kontrol oluşmaz. Zincir koşulu çapadan pencere sonuna kadar uygulanır; ilk çiftte taban pencere başıdır. Son koşulu sinyal penceresine uygulanmaz, çünkü pencere sonunda ödeme beklenip beklenmediğini söylemek aralık alanına güvenmeyi gerektirir. Pencere yarı açıktır (rev.10): pencere başına tam denk gelen kayıt ortalamaya **girmez**, pencere sonuna denk gelen kayıt **girer**; iki karşılaştırma da tolerans payıyla yapılır. Gerekçe, ön-kaydın başka yerlerdeki aynı yapısıdır: funding ödemesinde de giriş anındaki ödeme hariç, çıkış anındaki dahildir; pencere başındaki kaydı içeri almak 24 saatlik aralığı fiilen uzatır. t barının kapanışından sonraki hiçbir kayıt okunmaz. Pencerenin tamamı kümenin tarih aralığının içinde olmalıdır; değilse değer hesaplanmaz ve o barda olay ya da kontrol oluşmaz. Pencere sonuna denk gelen kayıt yalnızca aynı kümeye aitse ortalamaya girer (rev.11): sonraki kümenin ilk kaydı, tolerans payıyla pencere sonuna denk gelse bile okunmaz ve o barda değer hesaplanmaz, çünkü §3 gereği kümeler arası veri ödünç alınmaz. Bu, keşif kümesinin son barlarını düşürür; F1 ölçümünde bu barların tamamı (234 / 234) zaten giriş barı bulunmadığı için reddediliyordu, dolayısıyla olay kümesi değişmez. Penceredeki kayıtların oranlarından biri sayı değilse ya da sonlu değilse ortalama hesaplanmaz. Çapa ve zincir koşulları sağlansa bile pencerenin yarı açık aralığında hiç kayıt yoksa değer hesaplanmaz. Küme sınırı karşılaştırmaları da §4 "Zaman toleransı"na tabidir: kümenin son barının kapanışı ile küme sonu arasındaki bir saniyelik fark aynı an sayılır, dolayısıyla bu şart kümenin son barlarını düşürmez. Ortalama, penceredeki kayıtların 8 saate normalleştirilmiş oranlarından alınır (§2 "Funding").

**Funding tamlığının bilinen sınırları (rev.9).** Kural ödeme anı tahmin etmediği için yanlış eksik üretmez; F1 ölçümünde bütün evren iki katmanda tarandı ve pozisyon düzeyinde karşı örnek bulunamadı. Buna karşılık aşağıdaki yerlerde gevşektir. İlk üç maddedeki sayılar F1'in bütünlük sayımından gelir ve dönem içi bütün barların varsayımsal sinyal sayıldığı, süzülmemiş evrende, birincil ufukta ölçülmüştür (3.887.825 tam pozisyon); gerçek olay kümeleri süzüldükçe paylar değişir.

- **Kısmi kuyruk.** Penceredeki son kayıttan pencere sonuna kalan dilim bir tam aralıktan kısaysa, o dilimdeki eksik bir ödeme görülemez: 938.979 pozisyon (%24,15). Bu bir küme özelliği değil, ritim ile ızgaranın aritmetiğidir: 4 saatlik ızgarada 8 saatlik ritimde oran yapısal olarak ≈ %50, 4 saatlik ritimde 0'dır; 1 günlük ızgarada ≈ %0,02'dir. Kümeler arasındaki fark yalnızca ritimlerin takvime göre dağılımından gelir.
- **Pencere sonundaki eşitlik.** Son kayıt artı aralığı tam pencere sonuna denk geldiğinde, o anda gerçekten ödeme gerekip gerekmediği aralık alanına güvenmeden bilinemez. Pozisyon tam sayılır; o anda kayıt yoksa ödeme net getiriye girmez: 435 pozisyon.
- **Çapa yokluğu.** Girişten önce dönem içinde kayıt bulunmayan pozisyonlarda doğrulanacak hiçbir şey olmadığı için funding tam sayılmaz ve pozisyon oluşmaz: 7.248 pozisyon. Dönemlerin ilk girişleri ve funding'i bulunmayan dönemler buraya düşer.
- **Sinyal penceresinin tek kaydı (rev.11).** Funding sinyal penceresine son koşulu uygulanmadığı için, 24 saatlik pencerede yalnızca bir kayıt bulunsa bile ortalama o tek kayıttan hesaplanır. Bu, pencerede eksik bir ödeme olup olmadığının ayırt edilememesinden kaynaklanır ve pozisyon funding'indeki kısmi kuyruk sınırının sinyal tarafındaki karşılığıdır.
- **Aralık geçişine bitişik eksik ödeme (rev.10).** Ödeme aralığının değiştiği bir çiftte, aradaki tek bir eksik ödeme kuralın izin verdiği boşluğun içinde kalabilir ve görülmez. Ölçü: aralığı değişen her çiftte taban, ilk çiftte çapa ile girişin geç olanı, sonrakilerde önceki kayıt; eşik, iki kaydın aralık alanlarının küçüğü artı tolerans. Bu ölçü, **gerçek ödeme ritminin iki kaydın aralık alanlarının küçüğünden kısa olmadığı varsayımı altında** üst sınırdır; varsayım tutmazsa (alan gerçek ritimden gecikmeli değişmişse) daha fazlasını kaçırır. KEŞİF kümesinde en fazla 473 pozisyon (4h ızgarada, 1.103.215 tam pozisyon içinde, 23 sembol) ve 337 pozisyon (1d ızgarada, 180.928 içinde, 21 sembol). Bu madde yalnızca KEŞİF için sayılmıştır: onay kümelerinin sayılması §3 gereği keşif aşamasında gerekmeyen bir bakıştır. Kısmi kuyruk, pencere sonundaki eşitlik ve çapa yokluğu maddeleri ise bütün evren için sayılmıştır ve bu sayılar kümeye kesilmemiş seriden gelir; KEŞİF'te kesik ve kesiksiz seri aynı sonucu verir, C2'nin ilk pozisyonlarında çapa küme sınırının dışına düşerse küçük bir sapma kalabilir ve bu sapma ölçülmemiştir.

Ayrıca 2026-06-24 04:00'te, C2 kümesine düşen, borsa kaynaklı tek bir funding boşluğu vardır (aşağıdaki sayı da ilk üç maddeyle aynı sayımdan gelir): o an aktif 415 sembolün 398'inde kayıt yoktur (REST ucu ile vision dosyası birebir aynı). Penceresi bu anı içeren 12.298 pozisyon eksik sayılır ve oluşmaz; girişi tam bu ana denk gelen pozisyonlar etkilenmez. Boşluk olay ve kontrol taraflarına aynı anda uygulandığı için yön seçmez.

**F2 şartı (rev.9).** F2 raporunda, kısmi kuyruk ve pencere sonu eşitliği nedeniyle net getirisi tam doğrulanamayan olayların payı her hipotez için **funding ritmi başına** (8, 4, 2, 1 saat ve sınıflanmamış; §4 "Pozisyonun funding ritmi", rev.10) raporlanır ve ana sonuçlar bu olaylar dışlanarak bir sağlamlık kontrolü olarak yeniden hesaplanır. Dışlama kontrol tarafına da uygulanır (rev.13): sağlamlık kontrolünde kalan olayların havuzlarından, net getirisi aynı nedenlerle tam doğrulanamayan kontroller de çıkarılır ve havuzu boşalan olay analize girmez. Gerekçe: kontrol bir sağlamlık sorusudur ve "yalnızca doğrulanmış getirilerle sonuç ne olur" sorusuna girecek her sayının iki tarafta da doğrulanmış olması gerekir. Sağlamlık kontrolünde kalan olay ve kontrol sayıları raporlanır. Sağlamlık kontrolü ana testin yerini almaz, yanında raporlanır; onay kararları ana teste göre verilir. Bu şart sonuçlar görülmeden yazılmıştır.

| Hipotez | Birincil ufuk | İkincil ufuklar (yalnızca rapor) |
|---|---|---|
| H1, H2 | 18 bar (3 gün) | 6 bar, 42 bar |
| H3 | 14 gün | 7 gün, 30 gün |

## 5. Hipotezler

**Pencere sınırları.** Her koşulun geriye bakış penceresinin t barını içerip içermediği, §5'teki formülle belirlenir ve uygulamada açıkça belirtilir. H1'in 6 barlık dip penceresi ve H2'nin k barlık kırılım penceresi t'yi **içermez** (t-6..t-1, t-k..t-1). H2'nin 30 barlık yükseliş penceresi ve H1'in 180 barlık hacim penceresi t'yi **içerir**. Varsayılan davranış yoktur; belirtilmeyen çağrı hata verir.

**Pencere sınırlarının tamamı (rev.11).** Yukarıdakilere ek olarak:

- `close[t-30]` iki uçlu bir orandır: t'den 30 × adım önceki barın kapanışı (§2 "Pencereler zamanla tanımlanır"). Tamlık penceresi kapalı aralıktır: `[t-30 .. t]`, yani 31 bar; aralıktaki beklenen barlardan biri bile eksikse değer hesaplanmaz. Bu, H2'nin 30 barlık yükseliş penceresi ile H3'ün düşüş trendi oranı için aynıdır.
- **SMA50**, 1 günlük seride son 50 günün kapanışlarının basit ortalamasıdır ve t gününü **içerir** (`[t-49 .. t]`).
- **H3'ün hacim pencereleri:** "son 30 gün" t gününü **içerir** (`[t-29 .. t]`); "gün −120 ile −31 arası" t gününe göre sayılır (`[t-120 .. t-31]`, 90 gün). İki pencere arasındaki t-30 günü hiçbir pencereye girmez; bu, yazılı sayıların doğrudan sonucudur ve bilerek korunmuştur.
- **Tepe penceresi:** §5 H1'de tanımlıdır.

Bu pencerelerin hepsi §2 "Tamlık şartı" kapsamındadır.

Her hipotezin keşif ızgarası en fazla 9 yapılandırmadır. Izgara parametreleri (θ, δ, φ, k, ν, τ) yalnızca bu ön-kayıtta tanımlıdır ve kod bu değerleri tek bir yerden, ön-kayıt değeri olarak okur (rev.11). Olay ya da kontrol üreten her çağrı, hipotezi ve yapılandırmayı birlikte alır; ızgarada bulunmayan bir parametre demeti hata verir. Kontrol barının sinyal doğrulaması (§6) olayla aynı yapılandırmayı kullanır. Aynı coinde bir olaydan sonra, o hipotezin birincil ufku boyunca yeni olay sayılmaz (bekleme süresi). Süre olay barından (t) ölçülür ve t + birincil ufuk anını içerecek biçimde sürer (rev.12): açılışı tam o ana denk gelen bar hâlâ beklemededir, ilk serbest bar bir sonrakidir. Gerekçe, ön-kaydın başka yerlerindeki aynı yarı açık yapı (§4 "Funding ödemesinin sınırları" ve §4 funding sinyal penceresi, ikisinde de aralığın üst ucu dahildir) ve bu okumanın iki okumadan daha muhafazakâr olanı olmasıdır: ilk serbest barda açılan pozisyonun girişi, önceki olayın pozisyonunun çıkışından sonra gelir, aynı anda değil. Bekleme yalnızca oluşmuş olaylar için işler: §4'teki karar noktasından geçmemiş bir aday beklemeyi başlatmaz. Bekleme yapılandırma başına işler; her yapılandırma kendi olay dizisini üretir. Bekleme dönem sınırını aşmaz: yeni dönemde sıfırlanır.

### H1 — Başarısız pump

**Mekanizma.** Kısa sürede sert yükselen coinde geç gelen alıcılar tükenir. Yükseliş
başarısızlığı teyit edilince satış zincirleme hızlanır.
**Karşı taraf.** Tepeye yakın giren FOMO alıcıları.

1. **Pump barı:** `close[t] / min(low[t-6..t-1]) - 1 ≥ θ` ve son 6 barın toplam hacmi ≥ önceki 180 barın 6'lı toplam hacim medyanının 3 katı. Hacim, bu projedeki bütün hipotezlerde ve bütün pencerelerde USDT cinsinden işlem hacmidir (`quote_volume`); coin cinsinden hacim hiçbir hesaba girmez (rev.12). Gerekçe: uygunluk hacmi (§2) ve H3'ün hacim pencereleri de aynı seriyi kullanır, ve USDT hacmi katılımı coinin fiyat düzeyinden bağımsız ölçer.

   H1'in 6'lı toplam hacim medyanı kayan pencereyle hesaplanır: her bar için son 6 barın
   toplamı alınır ve bu toplamların 180 barlık medyanı kullanılır. Ardışık, çakışmayan
   bloklara bölünmez.

   H1'in 180 barlık hacim medyanı t barını içerir; 6 barlık toplam pencereleri t barını içerir. H1'in 6 barlık dip penceresi (`low[t-6..t-1]`) t barını içermez.

2. **Tepe:** pump barı dahil, teyit barından bir önceki bara kadar görülen en yüksek `high`; en fazla 12 bar izlenir. Teyit barının kendi `high` değeri tepeye girmez (rev.11): girseydi "aynı barda `high < tepe`" koşulu teyit barının yeni bir en yüksek değer kurmaması anlamına gelirdi ve koşulun amacı değişirdi. Tepe penceresi §2 "Tamlık şartı" kapsamındadır: pump barından teyit barının bir öncesine kadar beklenen barlardan biri bile eksikse tepe hesaplanmaz ve olay oluşmaz.
3. **Olay (başarısızlık teyidi):** pump barından sonraki 12 bar içinde ilk kez
   `close ≤ tepe × (1 - δ)` olan ve aynı barda `high < tepe` olan bar.
   12 bar içinde teyit gelmezse pump düşer, olay sayılmaz.
4. **Tek izleme (rev.11):** bir coinde aynı anda yalnızca bir izleme yürür. İzleme sürerken pump koşulunu sağlayan yeni bir bar gelirse yok sayılır: tepe ve 12 barlık sayaç ilk pump barından ölçülmeye devam eder. İzleme, teyit barıyla ya da 12 bar dolduğunda biter; yeni bir izleme ancak bundan sonra (ve olay oluştuysa bekleme süresi dolduktan sonra) başlayabilir. İzlemeyi bitiren bar o izlemenin parçasıdır ve yeni bir pump barı olarak değerlendirilmez (rev.12): en erken yeni pump barı, izlemenin bittiği bardan sonraki bardır. Bedeli, olay üretmeden biten bir izlemenin ardından en çok bir pump barının kaybolmasıdır; karşılığında bir bar aynı anda iki izlemeye ait olmaz. İzleme penceresi dönemin ve kümenin içinde kalmalıdır (rev.13): izleme yalnızca dönem içi ve küme içi barlar üzerinde yürür, bu barlar arasında teyit gelmezse izleme olay üretmeden kapanır. Dönemin ya da kümenin sonuna 12 bardan az kalmışken başlayan bir pump barı, bu yüzden hiç olay üretmeyebilir. Gerekçe: §2 dönem dışındaki hiçbir barın hesaba girmemesini, §3 kümeler arası veri ödünç alınmamasını şart koşuyor; keşif kümesindeki bir pump barının teyidini onay verisinde aramak bu iki kuralı birlikte delerdi. Aynı kural bir olayın dayandığı bütün barlar için geçerlidir: sinyal pencereleri, izleme penceresi ve pump barının kendisi aynı dönemin ve aynı kümenin içinde olmalıdır. Böylece bir teyit barı en çok bir olay sayar.
5. **Geçersizlik seviyesi (F4 için kayıt):** `tepe × 1.02`

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
3. **Olay:** iki koşulun birlikte sağlandığı ilk gün. "İlk gün", iki koşulun birlikte sağlandığı **kesintisiz dizinin** ilk günüdür (rev.11). Dizi, koşullardan biri sağlanmadığı ya da §2 "Tamlık şartı" gereği hesaplanamadığı günde kesilir; dizi kesildikten sonra koşullar yeniden birlikte sağlanırsa o gün yeni bir "ilk gün"dür ve bekleme süresi ayrıca uygulanır. Kesintisiz süren bir dizinin içinde, bekleme süresi dolsa bile yeni olay sayılmaz. Dizi koşullarla tanımlıdır, karar noktasının onayıyla değil (rev.13): bir gün iki koşulu birlikte sağlıyorsa diziye aittir, o günde olay oluşup oluşmadığına bakılmaz. Bunun sonucu olarak, dizinin ilk günü karar noktasından geçmezse (ör. funding tamlığı sağlanmadığı ya da giriş barı bulunmadığı için) o dizi hiç olay üretmez; dizinin ikinci günü "ilk gün" sayılmaz. Gerekçe: dizinin başlangıcı fiyat ve hacim verisinin özelliğidir, ret gerekçeleri ise getirinin yönünü seçmeyen veri koşullarıdır; bu okuma iki okumadan muhafazakâr olanıdır.
4. **Geçersizlik seviyesi (F4 için kayıt):** `max(high[t-30..t]) × 1.02` (rev.13). H3'ün çapası olmadığı için seviye H2 ile aynı biçimde, düşüş trendi koşulunun zaten kullandığı pencereden kurulur; pencere 1 günlük seridedir ve tamlık şartı §5 "Pencere sınırları"na göredir.

**Izgara:** `ν ∈ {0.50, 0.65, 0.80}` × `τ ∈ {0.15, 0.25, 0.35}`

## 6. Kontroller

Her olay için iki ayrı kontrol kümesi üretilir. Kontrol barları da aynı uygunluk filtresinden geçmek zorundadır.

**Kontrolün ne ölçtüğü (rev.11).** Kontrol barı, olayın sinyal yapısını taklit etmez: kontrolde hipotezin sinyal koşulları aranmaz. Kontrol, "aynı yönde pozisyon o barda açılsaydı getirisi ne olurdu" sorusunu ölçer. Bu yüzden H1'in kontrol barında pump barı, dip penceresi ve tepe aranmaz; H2'nin kontrol barında kırılım dibi, H3'ün kontrol barında koşul dizisi aranmaz. Kontrol barı için gereken: uygunluk filtresi, dönem üyeliği, fiyat ve funding tamlığı, hipotezin çapasız sinyal pencerelerinin hesaplanabilir olması, ve §4'teki tek karar noktasının bütün koşulları.

**Kontrol barında sinyal pencereleri (rev.12).** Kontrol barında hipotezin sinyal **koşulları** aranmaz, ancak çapasız sinyal pencerelerinin **hesaplanabilir** olması gerekir; hesaplanamıyorsa o bar kontrol olamaz. Bu, §2 "Tamlık şartı"nın açık hükmüdür ("o barda olay ya da kontrol oluşmaz") ve her iki kontrol kümesi için geçerlidir. Gerekçe: olay barlarında bütün pencereler tanımı gereği hesaplanmıştır; kontrol barlarında aranmazsa kontrol havuzuna bir olayın hiçbir zaman oluşamayacağı barlar (dönem başları, boşluk sonrası barlar) girer ve iki grup veri kalitesi bakımından sistematik olarak ayrışır. Çapasız pencere, tanımı yalnızca t'ye ve geçmişe dayanan penceredir: H1'in dip ve iki hacim penceresi, H2'nin kırılım, yükseliş ve funding pencereleri, H3'ün iki hacim penceresi, SMA50 ve düşüş trendi oranı. H1'in tepe penceresi bir pump barına çapalı olduğu için kontrol barında tanımsızdır ve aranmaz.

Kontrol barında sinyal koşulları hiçbir amaçla hesaplanmaz (rev.12). K2'nin "o anda olay üretmemiş" şartı, koşulların sağlanıp sağlanmadığına değil, o barın aynı yapılandırmanın oluşmuş olay kümesinde bulunup bulunmadığına göre uygulanır (§6 "Örnekleme kuralları"). Kontrol barında hesaplanan tek şey, çapasız pencerelerin hesaplanabilirliğidir.

- **K1 — aynı coin, rastgele zaman.** Aynı coinden, aynı küme ve dönem içinden, o hipotezin herhangi bir olayına birincil ufuk mesafesinden yakın olmayan 10 rastgele bar. Tam ufuk mesafesi yakın sayılmaz (rev.12): ölçüt "daha yakın"dır, iki yönde de. Gerekçe: tam ufuk mesafesindeki bir kontrol barının pozisyonu olayın pozisyonuyla çakışmaz, uç uca gelir — ileri yönde kontrolün girişi olayın çıkış anıdır, geri yönde kontrolün çıkışı olayın giriş anıdır.
- **K2 — aynı zaman, rastgele coin.** Aynı t barında uygun olan ve o anda olay üretmemiş diğer coinlerden 10 rastgele coin.
- **Örnekleme kuralları (rev.11).** K1'deki "o hipotezin herhangi bir olayı", **aynı yapılandırmanın** oluşmuş olaylarıdır: kapıdan geçmemiş (reddedilmiş) adaylar ve başka yapılandırmaların olayları sayılmaz. K2'deki "olay üretmemiş" de aynı yapılandırmanın oluşmuş olay kümesine göredir ve üç hipotezde aynıdır (rev.12): bir bar yalnızca o kümede yer alıyorsa K2 havuzundan çıkarılır. Sinyal koşullarını sağladığı hâlde olay oluşmamış barlar (bekleme süresi içindeki barlar, H1'de yürüyen bir izlemenin içindeki barlar, H3'te kesintisiz dizinin ilk gün dışındaki günleri, karar noktasının başka bir gerekçeyle reddettiği barlar) havuzda kalır. Gerekçe iki yönlüdür: ön-kayıt "olay üretmemiş" diyor, "koşulu sağlamamış" demiyor; ve bu okuma iki okumadan muhafazakâr olanıdır — koşulu sağlayan barları havuzdan çıkarmak kontrol havuzunu sinyale benzeyen barlardan arındırır ve ölçülen farkı hipotez lehine büyütür. İki havuzda da örnekleme iadesizdir. Adaylık örneklemeden önce belirlenir (rev.13): bir bar ya da coin, §6'daki bütün kontrol gereksinimlerini ve §4'teki tek karar noktasının bütün koşullarını sağlıyorsa adaydır; örnekleme yalnızca adaylar arasından yapılır ve seçilen bir aday sonradan düşmez. Gerekçe: aşağıdaki "aday sayısı 10'dan azsa" kuralı ancak adaylık örneklemeden önce tanımlıysa anlam taşır; önce örnekleyip sonra elemek havuz boyutunu adayların varlığına değil çekimin şansına bağlardı. Bunun sonucu olarak her olayın havuzu, aday sayısı yeterliyse tam 10 kontrol içerir. Aday sayısı 10'dan azsa adayların tamamı alınır ve sayı sonuç dosyasına yazılır. Bir olayın her iki havuzu da boşsa o olay analize girmez; en az bir kontrolü olan olay kalır. Örnekleme, §7'deki tohumdan (hipotez, yapılandırma, küme, sembol, olay zamanı) demetiyle türetilen alt tohumla yapılır; semboller alfabetik sırada işlenir, böylece sonuç koşu sırasından bağımsızdır.
- **Dönem üyeliği (rev.8).** Bir bar, onu oluşturan bütün 4h barlar aynı dönemin içindeyse dönem içidir: 4h barda açılış [dönem başı, B] aralığındadır; 1d barda §2 "1 günlük barlar"daki altı barın tamamı dönem içidir. Olay barı t, K1'in "aynı küme ve dönem içinden" koşulu ve K2'nin "aynı t barında uygun" koşulu bu ölçütü kullanır. Kontrol barları, olaylarla aynı fiyat okuma tabanına, dönem sonu kuralına ve tek karar noktasına tabidir.

K2 piyasa yönünü ayıklar ve bu projede **en önemli kontroldür**.

## 7. İstatistik

- **Test istatistiği:** `ortalama(olay net getirisi) - ortalama(kontrol net getirisi)`. Kontrol ortalaması olay başına ağırlıklandırılır (rev.13): önce her olayın kontrol havuzunun ortalaması alınır, sonra bu ortalamaların olaylar arasındaki ortalaması alınır; havuzlar tek bir kümede birleştirilmez. Gerekçe: aşağıdaki yeniden örnekleme her tekrarda olay başına bir kontrol çeker, dolayısıyla her olay dağılımda eşit ağırlık taşır. Havuzlar birleştirilirse gözlenen istatistik ile yeniden örnekleme dağılımı aynı ölçekte olmaz ve küçük havuzlu olaylar iki tarafta farklı ağırlıklanır. Bu tanım, §8 ve §9'da anılan "K2 farkı" için de geçerlidir; K1 farkı aynı biçimde hesaplanır.
- **p-değeri:** 10.000 tekrarlı eşleştirilmiş yeniden örnekleme. Her tekrarda her olayın kontrol havuzundan bir kontrol çekilir ve o tekrarın test istatistiği hesaplanır. `r`, test istatistiğinin sıfırı aşmadığı (`≤ 0`) tekrarların sayısıdır (rev.11). `p = (r + 1) / (10000 + 1)`, tek yönlü (olay short'u daha iyi). Çekim iadelidir ve §7'deki tohumdan, (hipotez, yapılandırma, küme, kontrol kümesi) demetiyle türetilen alt tohumla yapılır (rev.13). Gerekçe: tek bir global tohum, 9 yapılandırma ve iki kontrol kümesi için aynı rastgele diziyi kullanır ve p-değerlerini birbirine bağlar; alt tohum §6'daki örnekleme deseniyle aynıdır.
- **Bu yordamın sınırı (rev.11).** Bu bir bootstrap p-değeridir, permütasyon testi değildir: belirsizlik yalnızca kontrol seçiminden gelir, olay kümesi her tekrarda sabittir. Dolayısıyla p-değeri, olayların kendi örnekleme değişkenliğini hesaba katmaz ve bu yönüyle iyimser olabilir. Yordam ön-kayıtta yazıldığı biçimiyle korunmuştur; sınırı F2 ve F3 raporlarında bu cümleyle birlikte anılır.
- **Çoklu test:** üç hipotez için Bonferroni, `α = 0.05 / 3 = 0.0167`.
- **Tohum:** `20260911`, sonuç dosyalarına yazılır.

## 8. Keşif kuralları (F2)

1. Her hipotezin 9 yapılandırmasının hepsi KEŞİF kümesinde hesaplanır ve **hepsi raporlanır**. Her yapılandırma için raporlanması zorunlu kalemler (rev.13): yapılandırma kimliği ve parametre değerleri; oluşmuş olay sayısı; analize giren olay sayısı; ortalama net getiri; K1 farkı ve K2 farkı (§7 tanımıyla, birincil ufukta); iki kontrol kümesi için p-değerleri; havuzu 10'dan az olan olay sayısı; §4 "F2 şartı"ndaki ritim başına pay ve sağlamlık kontrolü sonucu; tohum ve alt tohum türetme demeti. Olay başına ham kayıtta ayrıca MAE ve geçersizlik seviyesi saklanır (F4 için; §10 ve §5). Analize giren olay sayısı sıfır olan bir yapılandırma da raporlanır: olay sayıları sıfır yazılır, ortalama getiri, farklar ve p-değerleri "hesaplanamaz" olarak işaretlenir ve sıfır sayılmaz.
2. Aday yapılandırmalar: olay sayısı ≥ 150 olanlar. Buradaki ve §9'daki olay sayısı, **analize giren** olayların sayısıdır (rev.13): her iki kontrol havuzu da boş olduğu için analize girmeyen olaylar (§6) sayılmaz. Gerekçe: eşikler istatistik gücünü güvenceye almak için vardır ve güç yalnızca teste giren olaylardan gelir; oluşmuş ama analize girmeyen olayı saymak gücü olduğundan fazla gösterirdi. Her iki sayı da raporlanır (§8 madde 1).
3. Adaylar arasından K2 farkı en yüksek olan seçilir (K2 farkı §7'deki tanımla, birincil ufukta). Berabere kalma mekanik olarak çözülür (rev.13): K2 farkı eşitse analize giren olay sayısı daha büyük olan, o da eşitse §5'teki ızgara sıralamasında daha önce gelen yapılandırma seçilir. Gerekçe: ölçüt mekanik olmalı ve başka bir sonuca bakmayı gerektirmemelidir; olay sayısının büyüğünü seçmek daha fazla güç demektir ve getirinin yönünü seçmez.
4. Hiçbir yapılandırma aday eşiğine ulaşmazsa hipotez **onaya gönderilmeden kapanır** (rev.13): seçilecek yapılandırma yoktur ve onay verisi harcanmaz. Dokuz yapılandırmanın tamamı madde 1'e göre raporlanır ve kapanma gerekçesi "aday yok" olarak yazılır. Bir yapılandırma seçilmişse, o yapılandırma için şu iki koşul keşifte sağlanmıyorsa hipotez **onaya
   gönderilmeden kapanır** (onay verisi harcanmaz):
   - K2 farkı > 0
   - ortalama net getiri > 0
5. Seçim, onay koşusundan önce `analysis/<hipotez>/KILIT.md` dosyasıyla commit edilir. Dosyanın yolu bu ön-kayıtta yazılı olandır ve oluşturulduğu andan itibaren kilitli dosyalar arasına girer (rev.13). Dosya şu alanları taşır: hipotez; hüküm (yapılandırma seçildi / hipotez kapandı) ve kapandıysa gerekçesi; seçildiyse yapılandırmanın kimliği ve bütün parametre değerleri; analize giren ve oluşmuş olay sayıları; K2 farkı; keşif koşusunun commit hash'i ve UTC zamanı; tohum. Onay koşusu, koştuğu hipotezin yapılandırmasını bu dosyadan okur; dosyada kaydı olmayan ya da hükmü "hipotez kapandı" olan bir hipotez için onay koşusu açılmaz. Dosya da yalnızca ekleme kuralına tabidir: bir hipotezin kaydı yazıldıktan sonra değiştirilmez.

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
| 9 | 2026-09-23 | T ≥ K, funding tamlık kuralının yeniden tanımı, bilinen sınırlar ve F2 sağlamlık şartı, H2 funding penceresinin tamlığı, uygunluğun tek karar noktasına alınması; ayrıntı tablonun altında | ayrıntı tablonun altında | Yok (henüz sonuç yok) |
| 10 | 2026-09-24 | H2 funding penceresinin yarı açık sınırları ve küme içinde olma şartı, dördüncü gevşeklik maddesi, geçerli aralık koşulu, ufuk değerlerinin bağlanması, pozisyonun funding ritmi, ölçüm raporlamasının küme sınırı; ayrıntı tablonun altında | ayrıntı tablonun altında | Yok (henüz sonuç yok) |
| 11 | 2026-10-09 | Pencere sınırları ve tamlık kapsamı, kontrolün tanımı ve örnekleme kuralları, ızgara parametrelerinin bağlanması, bekleme süresi, H1 tek izleme, H3 ilk gün, funding oranı ve küme sonu kaydı, sinyal penceresi sınırı, r tanımı; ayrıntı tablonun altında | ayrıntı tablonun altında | Yok (henüz sonuç yok) |
| 12 | 2026-10-10 | Bekleme süresinin üst ucu, H1'de izlemeyi bitiren bar, K1'in tam ufuk eşitliği, kontrol barında sinyal tamlığı, K2'nin ölçütü, hacim birimi, bar düzeyli hücre ölçütü, dizi kurallarının gerekliliği, geçerli oranın kapsamı; ayrıntı tablonun altında | ayrıntı tablonun altında | Yok (henüz sonuç yok) |
| 13 | 2026-10-10 | İzleme penceresinin dönem ve küme sınırı, H3 dizisinin koşulla tanımlı olması, H3 geçersizlik seviyesi, kontrol havuzlarında adaylığın örneklemeden önce belirlenmesi, K2 farkının olay başına ağırlıklandırılması, p-değerinin alt tohumu, raporlanacak kalemler ve sıfır olaylı yapılandırma, olay sayısının kapsamı, berabere kalma, aday bulunmaması, KILIT.md'nin alanları, ikincil ufukların kapsamı, sağlamlık kontrolünün kontrol tarafı, önbellek ve ağ; ayrıntı tablonun altında | ayrıntı tablonun altında | Yok (henüz sonuç yok) |

### Revizyon 8 — ayrıntı

**8.** Tarih: 2026-09-21. Değişiklikler: 4h fiyat okuma tabanı (giriş, çıkış, MAE ve çıkış anı her ızgarada dönem içi 4h barlardan); dönem bitişi (B) ve dönem kapanışı (K) tanımları; "ufuk dönem sonunu aşar" ölçütünün kapanış anlarına bağlanması ve ileri kaymayla sıralaması; delistin dönem sonu olarak tanımlanması; 1d barların yalnızca dönem içi, hizalı altı 4h bardan kurulması ve bu serinin sinyal, uygunluk ve kontrollerde tek olması; MAE'nin 4h barlardan ve çıkış fiyatını da içerecek şekilde tanımlanması; dönem sonu funding istisnası; tek zaman toleransı tanımı; funding tamlığının başlangıç boşluğunu da kapsaması ve tek karar noktasına eklenmesi; funding'siz dönem sayım penceresi; dönem üyeliği tanımı; SETTLED için tek kaynak kuralı; WAVESUSDT/KNCUSDT kararı; sayı düzeltmeleri.

**Gerekçe.** F1 denetiminin son turları, bugünkü kodun 1d ızgarasında dönem sonunda dolgu barlarından fiyat okuduğunu (rev.7'nin "dolgu barları hiçbir hesaba girmez" ve bar düzeyinde sınır kurallarının ihlali) ve dönem sonunu aşan pozisyonların 128 SETTLING sembolün 78'inde, 1d ızgarasında 168 dönem sonunun 167'sinde funding tamlığı bozulduğu için sessizce düştüğünü gösterdi (RESULTS §14.7, §14.8). Metodoloji denetçisi, aday kuralın sekiz tanımsız noktasını listeledi; bu revizyon hepsini tanımlar. 4h fiyat okuma tabanı ayrıca t+1 günü kısmi son gün olan H3 olaylarının kaybını önler; bu olaylar delistten hemen önceki dönemlere düşer ve düşürülmeleri hayatta kalma yanlılığı yaratırdı.

**Rev.7 düzeltme notu (errata).** Rev.7 gerekçesindeki "131 sembolde uzlaşma sonrası dolgu barların dönem sonunu yıllarca uzattığı" ifadesi düzeltilir: uzlaşma sonrası dolgusu olan sembol sayısı 145'tir; bunların 45'inde uzatma en az bir yıl, 15'inde en az iki yıldır. Rev.7 kaydının kendisi değiştirilmemiştir. §2'deki 14 → 18 ve 38 → 57 düzeltmeleri yürürlükteki metinde yapılmıştır. Üç sayı da `rapor_sayilari` betiğinden üretilmiştir (RESULTS §14.1).

**Denetim sınırı aşımı ve bu revizyonla ilişkisi.** A1 ölçümünde (commit 1093e69) uzlaşma sonrası 23 funding kaydının oran değerleri ve işaretleri raporlandı. Bu, §3.1'deki veri denetimi sınırını aştı. Kayıtların 5'i C1 grubundaki sembollere aittir; C2 dönemine ait kayıt içermez. Ayrıntılar RESULTS §14.5'tedir. Bu revizyondaki dönem sonu funding istisnası, bu bilgi görüldükten sonra ön-kayda yazılmıştır. Yön bilgisi açıkça beyan edilir: istisnanın dışarıda bıraktığı bu 23 kaydın 18'i pozitiftir, yani short lehine ödemedir; istisna, dönem sonuna ulaşan short pozisyonların net getirisini düşürür. İstisna görülen 23 kaydın tamamını hesaptan çıkarır; görülen hiçbir oran değeri getiri hesabına girmez. Aynı koşu, exchangeInfo'da bulunmayan sembollerin son barlarındaki 28 funding kaydının oran değerlerini de iz dosyasına yazmıştır; bunların bir kısmı C2 dönemine aittir. Bu 28 kaydın 23'ü dönem bitişindedir (B), istisnanın kapsamı dışında kalır ve getiri hesabına girer. İstisnanın dayandığı eğilim (funding penceresinin son barın açılışında bitmesi) araştırma tarafının çalışma notlarında oran değerleri ölçülmeden önce yazılmıştır, ancak bu depoda doğrulanabilir değildir. İstisnanın gerekçesi yöne değil ilkeye dayanır: uzlaşmadan sonra pozisyon yoktur. Bu revizyon hiçbir getiri hesaplanmadan yazılmıştır.

### Revizyon 9 — ayrıntı

**9.** Tarih: 2026-09-23.

**Değişiklikler.** (a) Dönem sonu eşiği T > K yerine T ≥ K. (b) Funding tamlık kuralı çapa, zincir, ilk çift ve son maddeleriyle yeniden tanımlandı; rev.8'in başlangıç boşluğu ve "hiç kayıt yok" cümleleri ile 4→1 saat geçişine ilişkin bilinen sınır cümlesi kaldırıldı. (c) Kuralın gevşek kaldığı üç yer ve 2026-06-24 boşluğu sayılarıyla yazıldı; F2 için ritim başına raporlama ve sağlamlık kontrolü şart koşuldu. (d) H2'nin 24 saatlik funding penceresinin tamlığı ilk kez tanımlandı. (e) Uygunluk tek karar noktasının parçası yapıldı.

**Gerekçe.** F1'in ölçüm turları, funding tamlığının bir sonraki ödemenin zamanını tahmin eden her tanımının yanlış eksik ürettiğini gösterdi. Aralık alanı, aralığın değiştiği anda eskimiş olur ve değişim anı kayıtlardan okunamaz. Rev.8'in tanımı pencere uçlarını kayıt dizisinden kopuk kurduğu için; "beklenen ödeme anı" üreten iki ara tanım ise aralık geçişlerinde ters yönlerde yanıldıkları için hatalıydı. Ölçülen etki: Rev.8'in, yürürlüğe giren kurala göre yanlış eksik saydığı 717 pozisyon; ikinci ara tanımın Rev.8'e göre 4.433 pozisyonluk farkının 4.412'si aralık geçişinden; üçüncü ara tanımın Rev.8'e göre 150 sembole yayılan 5.063 pozisyonu. Yalnızca kayıtlar arasındaki boşlukları ölçen tanım, bütün evren iki katmanda tarandığında pozisyon düzeyinde karşı örnek vermedi. Bunun bedeli pencere uçlarındaki gevşekliktir ve bilerek kabul edilmiştir: fazla sıkı bir kural pozisyonları düşürür, düşenler ağırlıkla delist coinlerdir ve bu hayatta kalma yanlılığı üretir (CLAUDE.md §2.4); fazla gevşek bir kural ise pozisyonu tutar. Kısmi kuyruk payındaki kümeler arası fark ölçüldü ve tamamen funding ritminin takvime göre dağılımından geldiği, ritim sabitlendiğinde üç kümenin 0,05 puan içinde birleştiği gösterildi; bu yüzden F2 raporlaması küme başına değil ritim başına istenir. T ≥ K eşiği, uzlaşma anında pozisyonun bulunmadığı ilkesinin K'ya tam denk gelen çıkışları da kapsaması içindir. H2 funding penceresi, §2 "Tamlık şartı" listesinde yer almadığı ve kod metinde tanımı olmayan bir kural uyguladığı için tanımlandı. Uygunluk kararı, olay ve kontrollerin farklı filtrelerden geçebildiği bir kod yolunu kapatmak için tek karar noktasına alındı.

**Bu revizyon hiçbir getiri hesaplanmadan yazılmıştır.** Kullanılan bütün sayılar funding kayıtlarının zaman damgaları ve ödeme aralıklarıyla sınırlı bütünlük sayımlarıdır (RESULTS §14.9); oran değeri okunmamıştır.

### Revizyon 10 — ayrıntı

**10.** Tarih: 2026-09-24.

**Değişiklikler.** (a) H2'nin funding penceresi yarı açık tanımlandı (başı hariç, sonu dahil) ve pencerenin tamamının kümenin içinde olması şart koşuldu; karşılaştırmalar tolerans tanımına bağlandı. (b) Bilinen sınırlara dördüncü madde eklendi: aralık geçişine bitişik tek eksik ödeme. (c) Funding tamlığına geçerli aralık koşulu beşinci madde olarak yazıldı. (d) Ufuk değerlerinin kodda ön-kayda bağlanması şart koşuldu. (e) Pozisyonun funding ritmi tanımlandı. (f) F1 ölçümlerinin varsayılan olarak yalnızca keşif kümesinde raporlanması kuralı yazıldı.

**Gerekçe.** Rev.9 uygulanırken H2 penceresinin başındaki kaydın ortalamaya girip girmediğinin ön-kayıtta yazılı olmadığı görüldü; bu, φ eşiğiyle karşılaştırılan sayıyı doğrudan değiştirir ve iki okuma keşif kümesinde 709.980 barda ayrışır. Seçim ölçümle yapılmadı: ortalamanın değerini ölçmek, kuralı sinyalin değerine bakarak seçmek olurdu. Karar, ön-kaydın başka yerlerde kurduğu yarı açık aralık yapısına dayanır. Küme içinde olma şartı, keşif kümesinin son barlarında pencere sonundaki kaydın bir sonraki kümeye düşmesiyle ortaya çıktı; tolerans tanımına bağlanınca şart kümenin son barlarını düşürmez ve bar tabanlı pencerelerle aynı davranır. Dördüncü gevşeklik maddesi, rev.9'un sınır listesinin eksiğiydi: aralığın değiştiği çiftlerde tek bir eksik ödeme kuralın izin verdiği boşluğun içinde kalabiliyor. Ölçüsünün üst sınır oluşu koşulludur ve koşul metinde yazılıdır. Geçerli aralık koşulu kodda vardı, ön-kayıtta yoktu; kodda olup metinde olmayan her kural ikisinin ayrıştığı yerdir, bugün hiçbir pozisyonu elemese de yazılmıştır. Ufuk değerleri ön-kayıtta zaten yazılıydı ama kod onlara bağlı değildi; birincil ufuk "ön-kayıt değildir" başlıklı bir kod bölümünde tutuluyordu. Ölçüm raporlamasının küme sınırı, F1 ölçümlerinin onay kümesi sayıları üretmesi üzerine yazıldı.

**Bu revizyon hiçbir getiri ve hiçbir sinyal değeri hesaplanmadan yazılmıştır.** Kullanılan sayılar funding kayıtlarının zaman damgaları ve ödeme aralıklarıyla sınırlı bütünlük sayımlarıdır (RESULTS §14.9); H2 ortalamasının değeri hesaplanmamıştır.

### Revizyon 11 — ayrıntı

**11.** Tarih: 2026-10-09.

**Değişiklikler.** (a) Tepe penceresinin sınırı ve tamlık kapsamı. (b) `close[t-30]`, SMA50 ve H3 hacim pencerelerinin sınırları; tamlık listesinin tamamlanması. (c) 4h barda eksik hücrenin barı düşürmesi. (d) Kontrolün ne ölçtüğü: kontrol barında sinyal koşulları aranmaz. (e) K1/K2 örnekleme kuralları. (f) Izgara parametrelerinin koda bağlanması. (g) Bekleme süresinin ölçüsü ve kapsamı. (h) H1'de tek izleme. (i) H3'te "ilk gün"ün dizi tanımı. (j) Funding sinyal penceresinde küme sonu kaydı ve eksik değerler. (k) Pozisyon funding'inde geçerli oran koşulu. (l) Sinyal penceresinin tek kayıttan hesaplanabilmesi, bilinen sınır olarak. (m) `r`'nin tanımı ve yordamın sınırı.

**Gerekçe.** F1 kapanışına doğru yapılan kapı çalışması, karar noktasının sinyal değerlerini çağırandan aldığını ve bu değerleri kendisi hesaplayabilmesi için ön-kayıtta tanımı olmayan on yedi noktanın kodda seçilmek zorunda kalacağını gösterdi. Bu revizyon o noktaların tamamını yazar; hiçbiri kodda seçilmemiştir.

İki karar ayrıca gerekçe ister. Birincisi kontrolün tanımı: H1'in sinyali bir pump barına çapalıdır ve kontrol barında pump yoktur, dolayısıyla kontrolde sinyal yapısını aramak kontrol barı için yapay bir çapa icat etmeyi gerektirirdi. Kontrolün ölçtüğü şey, aynı barda açılan bir pozisyonun getirisidir; sinyal koşulları yalnızca K2'nin "olay üretmemiş" şartını doğrulamak için hesaplanır. İkincisi `r`: yazılı yordam her tekrarda kontrol çeker, olay kümesini sabit tutar; bu bir bootstrap'tır ve `r`'nin tek tutarlı okuması, istatistiğin sıfırı aşmadığı tekrarların sayısıdır. Yordamı permütasyon testine çevirmek testi değiştirmek olurdu; bunun yerine yordam korunmuş ve sınırı metne yazılmıştır.

**Bu revizyon hiçbir getiri ve hiçbir sinyal değeri hesaplanmadan yazılmıştır.** Metindeki tek sayı (234 / 234) F1'in bütünlük sayımından gelir (RESULTS §14.19).

### Revizyon 12 — ayrıntı

**12.** Tarih: 2026-10-10.

**Değişiklikler.** (a) Bekleme süresinin üst ucu dahil. (b) H1'de izlemeyi bitiren bar yeni pump barı sayılmaz. (c) K1'de tam ufuk mesafesi yakın sayılmaz. (d) Kontrol barında çapasız sinyal pencerelerinin hesaplanabilir olması şartı. (e) K2'nin ölçütü üç hipotezde de gerçek olay kümesi; kontrol barında sinyal koşulları hiç hesaplanmaz. (f) Hacim birimi USDT (`quote_volume`). (g) Barın mevcutluğu bar düzeyinde tanımlı, her pencerede geçerli; `count` kapsam dışı. (h) Olayın oluşması için dizi kuralları da gerekli. (i) Geçerli oran koşulunun kapsamı ödeme penceresi.

**Gerekçe.** Rev.11 uygulanırken dokuz noktanın ön-kayıtta tanımsız olduğu ya da iki cümlenin çeliştiği görüldü; bu revizyon hepsini yazar. Dördünde kodun seçtiği okuma onaylanmış, beşinde değiştirilmiştir.

İki karar ayrıca gerekçe ister, çünkü ikisi de ölçülen farkın yönünü etkiler. Birincisi K2'nin ölçütü: koşulu sağladığı hâlde olay oluşmamış barları kontrol havuzundan çıkarmak, havuzu sinyale benzeyen barlardan arındırır ve ölçülen farkı hipotez lehine büyütür. Etki H3'te en belirgindir, çünkü kesintisiz dizinin ilk gün dışındaki bütün günleri havuzdan düşerdi ve bunlar hipotezin tam olarak tarif ettiği barlardır. Ön-kaydın harfi harfine okuması ("olay üretmemiş") aynı zamanda muhafazakâr olandır; seçilen okuma budur. İkincisi kontrol barında sinyal tamlığı: §2 "o barda olay ya da kontrol oluşmaz" diyor, §6 rev.11'in kontrol gereksinimleri listesi ise sinyal pencerelerini saymıyordu. §2 esas alınmıştır, çünkü olay barlarında bütün pencereler tanımı gereği hesaplanmıştır ve kontrolde aranmaması iki grubu veri kalitesi bakımından ayrıştırır. H1'in tepe penceresi bir pump barına çapalı olduğu için istisnadır; kural çapasız pencereler üzerinden yazılmıştır.

Bekleme süresinin üst ucu, izlemeyi bitiren bar ve K1'in tam eşitliği için kodun seçtiği okumalar onaylanmıştır; üçü de ön-kaydın başka yerlerindeki yapıyla tutarlı ve alternatiflerinden daha muhafazakârdır. Barın mevcutluğu bar düzeyinde tanımlanmıştır, çünkü alan düzeyli ölçüt aynı barı bir pencerede mevcut, başka bir pencerede eksik sayar; ölçülen etki her iki okumada da sıfırdır. Dizi kurallarının gerekliliği, kurallar yalnızca bir modülde yaşadığı ve karar noktası onları bilmediği için yazılmıştır: onay tek başına olay üretemez.

**Bu revizyon hiçbir getiri ve hiçbir sinyal değeri hesaplanmadan yazılmıştır.** Metinde ölçülmüş sayı yoktur.

### Revizyon 13 — ayrıntı

**13.** Tarih: 2026-10-10.

**Değişiklikler.** (a) İzleme penceresi dönem ve küme içinde kalır; bir olayın dayandığı bütün barlar aynı dönem ve kümede olmalıdır. (b) H3'ün dizisi koşullarla tanımlıdır; ilk günü karar noktasından geçmezse dizi olay üretmez. (c) H3'ün geçersizlik seviyesi tanımlandı. (d) Kontrol havuzlarında adaylık örneklemeden önce belirlenir. (e) Kontrol ortalaması olay başına ağırlıklandırılır; K2 farkının tanımı budur. (f) p-değeri alt tohumdan türetilir. (g) §8'in raporlanacak kalemleri ve sıfır olaylı yapılandırmanın raporlanması yazıldı. (h) 150 ve 100 eşikleri analize giren olay sayısına bakar. (i) Berabere kalma mekanik olarak çözülür. (j) Hiçbir yapılandırma aday eşiğine ulaşmazsa hipotez kapanır. (k) `KILIT.md`'nin yolu, alanları ve ekleme kuralı. (l) İkincil ufuklar yalnızca seçilen yapılandırma için. (m) Sağlamlık kontrolü kontrol tarafına da uygulanır. (n) Onay verisi kuralı önbelleği kapsar; F2 ve F3 koşuları ağa çıkmaz.

**Gerekçe.** F2'nin olay üretim yolu kod yazılmadan, şartname olarak baştan sona okundu ve kodun seçim yapmak zorunda kalacağı yirmi iki nokta tek listede toplandı. Bu revizyon o noktaların ön-kayıt kararı gerektirenlerini yazar; geri kalanı (rev.12'nin kodda henüz uygulanmamış maddeleri ve çıktı dosyalarının adlandırılması) kod ve belge işidir. Hiçbir karar bir sonuca bakılarak verilmemiştir; hiçbir olay kümesi, getiri ya da sinyal değeri hesaplanmamıştır.

Beş karar ayrıca gerekçe ister. **K2 farkının ağırlıklandırması**, §7'nin yeniden örneklemesi olay başına bir kontrol çektiği için olay başına olmak zorundadır; havuzların birleştirilmesi gözlenen istatistiği dağılımla aynı ölçekten çıkarırdı. **Olay sayısının kapsamı** analize giren olaylardır, çünkü eşikler istatistik gücünü güvenceye alır ve güç yalnızca teste giren olaylardan gelir. **H3'ün dizisi** koşullarla tanımlıdır; metin bunu söylüyor ve bu okuma, dizinin başlangıcını funding tamlığı gibi getirinin yönünü seçmeyen koşullardan bağımsız tutar. **Adaylığın örneklemeden önce belirlenmesi**, "aday sayısı 10'dan azsa hepsi alınır" kuralının anlamlı olması için zorunludur; bedeli kontrol havuzu için tam bir geçiştir. **İkincil ufukların yalnızca seçilen yapılandırma için hesaplanması**, hiçbir hükmü değiştirmeden maliyeti sınırlar; onay kararları zaten birincil ufka göre verilir.

**Ölçülmüş tek sayı.** Bu revizyonda ölçülmüş sayı yoktur. Kuru okumada ölçülen süreler (çağrı başına 1,55–1,61 saniye ve bunun yüzde doksan beşinin veri yüklemede geçmesi) yalnızca uygulama maliyetine ilişkindir ve hiçbir kuralı belirlemedi; önbellek ve ağ maddesinin gerekçesi tekrarlanabilirliktir, hız değil.
