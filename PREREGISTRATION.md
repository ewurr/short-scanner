# PREREGISTRATION.md — Short Öngörü Hipotezleri

**Durum:** Sürüm 4 (2026-09-11). F2 keşif aşaması başlamadan önce, hiçbir getiri hesaplanmadan commit edildi.
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

**1 günlük barlar.** 1d barlar 4h barlardan türetilir: UTC günü; open ilk, high en yüksek,
low en düşük, close son değer; volume ve quote_volume toplam. 6 adet 4h barı tam olmayan gün
eksik (NaN) sayılır. Uygunluktaki günlük hacim bu seriden hesaplanır.

**Listeleme dönemi.** Her sembolün verisi bir veya daha fazla listeleme dönemine ayrılır.
- Bucket'ta `<SEMBOL>SETTLED` dizininde dosyası bulunan ve sembolün ilk ile son ayı arasında
  kalan her ay, o sembol için **karantina ayıdır**.
- Karantina ayındaki barlar olay veya kontrol barı olamaz; hiçbir geriye bakış penceresi ya da
  ufuk karantina ayına giremez.
- Karantina ayları dönemi böler. Önceki dönem, karantinadan önceki son barla biter. Yeni dönem,
  karantinadan sonraki ilk barla başlar.
- Aylık 4h dosyaları arasında 3 aydan uzun boşluk da dönemi böler.
- Yeniden adlandırma zincirindeki her sembol ayrı bir dönemdir; fiyat serileri birleştirilmez.
- Listeleme yaşı her dönem başında sıfırlanır.
- Tüm geriye bakış pencereleri (uygunluk hacmi, H1 hacim medyanı, H2 30 bar, H3 hacim pencereleri
  ve SMA50) dönem başlangıcını aşamaz. Aşıyorsa değer hesaplanmaz ve o barda olay oluşmaz.
- Ufuk dönem sonunu aşarsa çıkış fiyatı dönemin son barının kapanışıdır.
- Aynı kurallar K1 ve K2 kontrol barlarına da uygulanır.

**Veri boşlukları.** Bar dizisinde eksik bar bulunabilir (F1 denetimi: 105 kayıt, 10 olay;
en büyüğü 48 ve 49 sembolü aynı anda etkilemiştir). Aşağıdaki kurallar dönem kurallarına ek
olarak uygulanır ve dönem bölmezler.

- **Pencereler zamanla tanımlanır.** "Son N bar" ifadesi son N × 4 saatlik zaman aralığı
  demektir (1 günlük seride N × 24 saat). Bar sayısıyla değil, zaman damgasıyla hesaplanır.
- **Tamlık şartı.** Bir pencerede beklenen barlardan biri bile eksikse değer hesaplanmaz
  (NaN). O barda olay ya da kontrol oluşmaz. Bu, H1'in hacim ve yükseliş pencerelerini,
  H2'nin 30 barlık ve k barlık pencerelerini, H3'ün hacim pencerelerini ve SMA50'yi, ayrıca
  uygunluk hacmini kapsar.
- **Ufuk.** Ufuk zamanla ölçülür: h bar = h × 4 saat. Hedef çıkış barı eksikse çıkış, sonraki
  ilk mevcut barın **açılış** fiyatındandır. Dönem sonu ve delist kuralları önceliklidir.
- **Giriş.** t+1 barı eksikse olay oluşmaz.
- 1 günlük seride bir gün yalnızca 6 adet 4 saatlik barın tamamı varsa oluşur; eksik gün
  zaten NaN'dir ve pencerelerde eksik sayılır.
- Aynı kurallar K1 ve K2 kontrol barlarına da uygulanır.

**Gerekçe.** F1 denetiminde açıklanamayan iki bütünlük sıçraması (WAVESUSDT +%54,1 ve
KNCUSDT +%31,3, ikisi de 2022-03-01 00:00) 2022-02-26…28 arasındaki 18 barlık kesintinin
ardından gelen ilk bardır. Fiyat kesinti sırasında hareket etmiştir. Kesinti üzerinden
atlayan bir pencere sahte bir yükseliş, kesinti üzerinden geçen bir ufuk ise gerçekte
alınamayacak bir çıkış fiyatı üretir. Bu iki kayıt karantinaya alınmaz; bu kural onları
zaten dışarıda bırakır.

**Veri bütünlüğü kontrolü.** F1 denetim raporu, `|open[t] / close[t-1] - 1| > 0.30` olan tüm
barları sembol ve zamanla listeler. Karantina ile açıklanamayan kayıtlar, F2 başlamadan önce
ayrı bir revizyonla karantinaya alınır ya da gerekçesiyle bırakılır.

**Uygunluk (t anında, yalnızca t'ye kadarki veriyle):**
- Listeleme yaşı ≥ 30 gün.
- H1, H2: son 30 günün medyan günlük işlem hacmi ≥ 10 milyon USDT.
- H3: son 30 günün medyan günlük işlem hacmi ≥ 2 milyon USDT.

Delist edilen sözleşmelerin geçmişi elde edilemezse bu durum F1 denetim raporunda
sayısıyla yazılır ve sonuçlar "kötümser yanlılıklı" olarak etiketlenir.
F1 denetiminde 28 delist sembolün tümünün geçmişi eksiksiz indirilmiştir; bu veri
kümesinde hayatta kalma yanlılığı yoktur.

**Evren tablosunun sabitlenmesi.** Karantina ayları ve listeleme dönemi sınırları
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

## 4. Getiri tanımları

Olay t barının kapanışında tespit edilir. Giriş fiyatı `P0 = open[t+1]`.
Ufuk h bar sonra çıkış fiyatı `P1 = close[t+h]`.

- **Brüt short getirisi:** `-(P1 / P0 - 1)`
- **Funding katkısı:** giriş ile çıkış arasındaki her funding anında `+oran`
  (pozitif oran short'a ödeme demektir, negatif oran short'tan kesinti).
- **Maliyet:** gidiş-dönüş `0.20%`.
- **Net short getirisi:** `brüt + funding - 0.0020`
- **MAE (en kötü ara zarar):** `max(high[t+1..t+h]) / P0 - 1`. Raporlanır, eşik değildir.

Ufuk içinde sözleşme delist olursa çıkış, son mevcut barın kapanışıdır.

**Karantina ve çıkış.** Ufuk bir karantina ayına uzanırsa çıkış, karantinadan
önceki son barın kapanışıdır. Dönem sonu, delist ve karantina kuralları ileri
kayma kuralından önceliklidir.

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
- **K2 — aynı zaman, rastgele coin.** Aynı t barında uygun olan ve o anda olay
  üretmemiş diğer coinlerden 10 rastgele coin.

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
| 4 | 2026-09-11 | Küme sınırı ve ufuk kuralı; karantinanın çıkışa uygulanması; pencere sınırlarının açık belirtilmesi; evren tablosunun commit edilmesi | F2 öncesi metodoloji denetimi (B1, B2, B3, B10): ön-kayıtta tanımsız kalan ve ilk getiri hesabında devreye girecek noktalar. Hiçbir getiri hesaplanmadan yapıldı. | Yok (henüz sonuç yok) |
