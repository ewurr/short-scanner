# PREREGISTRATION.md — Short Öngörü Hipotezleri

**Durum:** Sürüm 1. Veri indirilmeden ve hiçbir getiri hesaplanmadan önce commit edilir.
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
| Funding | Gerçek funding geçmişi. 4 saatlik veya 1 saatlik ödeme aralığına geçmiş sözleşmelerde oran, karşılaştırma için 8 saate normalleştirilir; getiri hesabında ise gerçek ödemeler kullanılır |

**Uygunluk (t anında, yalnızca t'ye kadarki veriyle):**
- Listeleme yaşı ≥ 30 gün.
- H1, H2: son 30 günün medyan günlük işlem hacmi ≥ 10 milyon USDT.
- H3: son 30 günün medyan günlük işlem hacmi ≥ 2 milyon USDT.

Delist edilen sözleşmelerin geçmişi elde edilemezse bu durum F1 denetim raporunda
sayısıyla yazılır ve sonuçlar "kötümser yanlılıklı" olarak etiketlenir.

## 3. Veri bölmesi

**Coin bölmesi.** Her sembol için `SHA256("short-lab-v1:" + SEMBOL)` hesaplanır.
Onaltılık özetin tamsayı değeri çift ise **A**, tek ise **B** grubudur. Sonuç
`data/split.csv` dosyasına yazılır ve commit edilir.

**Dönemler.**

| Küme | Coinler | Tarih aralığı | Kullanım |
|---|---|---|---|
| KEŞİF | A | 2020-01-01 → 2025-08-31 | Serbest keşif, ızgara seçimi |
| C1 | B | 2020-01-01 → 2025-08-31 | Onay (coin genellemesi), tek atış |
| C2 | A + B | 2025-09-01 → 2026-08-31 | Onay (zaman genellemesi), tek atış |

C1 ve C2 verisine keşif sırasında hiçbir biçimde bakılmaz. Olay sayıları dahil.

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

| Hipotez | Birincil ufuk | İkincil ufuklar (yalnızca rapor) |
|---|---|---|
| H1, H2 | 18 bar (3 gün) | 6 bar, 42 bar |
| H3 | 14 gün | 7 gün, 30 gün |

## 5. Hipotezler

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
