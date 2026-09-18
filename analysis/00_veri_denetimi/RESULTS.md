# F1 Veri Denetimi — TAM EVREN (678 sembol), ön-kayıt rev.7

**Durum:** Tam koşu, 678/678 sembol, **hata yok**.
**Koşu:** 2026-09-18 14:42 → 15:01 UTC+3, 8 iş parçacığı, önbellekten.
**Kod:** `db5ba82` üzerine commit edilmemiş değişikliklerle koşuldu (`ortam_tam.csv`:
"çalışma ağacı kirli"). Değişiklikler: `calistir.py` rev.7 evren API'sine göre yeniden
yazıldı, `data/universe.py`'ye exchangeInfo görüntüsü eklendi. İndirme ve ayrıştırma
katmanına dokunulmadı.
**Evren:** commit edilmiş `data/universe.csv` (rev.7, bar düzeyinde dönemler).
**exchangeInfo:** depodaki görüntü `data/exchange_info_anlik.json`
(alınma 2026-09-18 11:31:55 UTC, ham yanıt SHA256 `41244d4d…58c6a`), canlı uç nokta değil.
**Toplam dönem kesimi:** tüm mum ve funding kayıtları 2020-01-01 → 2026-08-31 23:59:59
UTC aralığına kesildi (bucket'a sonradan eklenen aylar denetimi değiştirmesin diye).

**Kapsam:** Yalnızca kapsama ve bütünlük. Getiri, fiyat değişimi, volatilite,
funding ortalaması veya olay benzeri hiçbir istatistik hesaplanmamış ve
yazılmamıştır (CLAUDE.md §3.1). Tek istisna, ön-kayıt §2'nin istediği
`|open/close[t-1] − 1| > 0.30` bütünlük listesidir.

Ham çıktılar (`*_tam.csv`): `sembol_ozeti`, `delist_siniflandirmasi`, `dolgu_kosulari`,
`kisa_sifir_kosulari`, `funding_siz_donemler`, `donem_sonu_degisimleri`, `settled_aylari`,
`yillik_kapsama`, `butunluk_sicramalari`, `bosluklar`, `bosluk_olaylari`,
`funding_araliklari`, `cross_dogrulama`, `cross_yogun_tarihler`,
`fiyat_farki_listeleme_yasi`, `kisa_donemler`, `ortam`.
Rev.7 ile anlamını yitiren `karantina_kaybi_tam.csv` kaldırıldı.

---

## 1. Evren, bölme ve dönemler

| Kalem | Sayı |
|---|---|
| Bucket'taki USDT perpetual dizini | 864 |
| **Evrene dahil** | **678** |
| Hariç: `TRADIFI_PERPETUAL` / endeks / stablecoin | 179 / 6 / 1 |
| Listeleme dönemi (dahil) | **690** (666 sembol tek, 12 sembol iki dönem) |
| Commit edilmiş dönemler ham seriden yeniden türetilenle aynı | **678/678** |

İki dönemli 12 sembol: AERGOUSDT, AIAUSDT, BNXUSDT, CTKUSDT, CVCUSDT, CVXUSDT, ICPUSDT,
LITUSDT, MAVIAUSDT, PUMPUSDT, SLPUSDT, TLMUSDT. Bölen: 11'inde iç dolgu koşusu, BNXUSDT'de
7 günden uzun eksik bar boşluğu (bkz. §3, §6).

Bölme (`data/split.csv`) değişmedi: 678 sembol → 669 varlık anahtarı.

## 2. Delist sınıflandırması

exchangeInfo görüntüsüne göre dahil 678 sembol:

| Sınıf | Sembol | Dönem sonundan sonra dolgu barı olan | Bu dolgu barları |
|---|---|---|---|
| TRADING | 522 | 0 | 0 |
| **SETTLING** (uzlaşmış) | **128** | 128 | 268.383 |
| **exchangeInfo dışı** | **28** | 17 | 27.139 |
| **Toplam delist** | **156** | 145 | 295.522 |

Ön-kayıt §2 rev.7'deki "128 SETTLING + 28 exchangeInfo dışı ≈ 156" sayısı görüntüyle
**birebir** doğrulandı. Görüntüdeki sözleşme/dayanak tipleri `universe.csv` ile
çelişmiyor (678/678).

**deliveryDate ile dönem sonu.** 128 SETTLING sembolün **128'inde** deliveryDate son
gerçek barın içine düşüyor (`donem_bitis ≤ deliveryDate < donem_bitis + 4 saat`):

| deliveryDate − son gerçek bar açılışı | Sembol |
|---|---|
| 0 saat (FTTUSDT, RAYUSDT) | 2 |
| 1 saat (tipik 09:00 UTC teslimi, son bar 08:00) | 121 |
| 1,5 / 2 / 2,5 saat | 2 / 2 / 1 |

Yani bar düzeyindeki dönem sonu uzlaşma anını 4 saat çözünürlükte tam yakalıyor.
Görüntüde TRADING olan 522 sembolün hepsinin son dönemi verinin son barında
(2026-08-31 20:00) bitiyor. Bu üç kontrol `tests/test_exchange_info_anlik.py` ile
görüntüden okunarak sabitlendi.

**Delist dönem sonlarının yıllara dağılımı:**

| Yıl | SETTLING | exchangeInfo dışı |
|---|---|---|
| 2020 | — | 1 |
| 2021 | — | 2 |
| 2022 | 3 | 11 |
| 2023 | — | 3 |
| 2024 | 21 | 7 |
| 2025 | 44 | 2 |
| 2026 | 60 | 2 |

**exchangeInfo dışı 28 sembolde deliveryDate yok**; dönem sonu yalnızca hacimden
geliyor. 17'sinde dönem sonundan sonra dolgu var (en uzunu BTCSTUSDT: 11.621 bar).
Dolgusu olmayan 11'in 9'unda seri gerçek işlemle bitiyor (1000BTTCUSDT, AERGOUSDT,
ANCUSDT, BZRXUSDT, DODOUSDT, EOSUSDT, KEEPUSDT, NUUSDT, YFIIUSDT). Kalan ikisi,
AKROUSDT (1 bar) ve LUNAUSDT (4 bar), seriyi dolgu eşiğinin altında kalan **sondaki**
sıfır hacimli barlarla bitiriyor; dönem yine son gerçek barda bittiği için bu barlar
dönem dışında kalıyor.

## 3. Dolgu barları

| Konum | Koşu | Bar | Sembol | Medyan süre | En uzun |
|---|---|---|---|---|---|
| Baş (listeleme öncesi) | 0 | 0 | 0 | — | — |
| İç (iki dönem arası) | 11 | 18.104 | 11 | 264,5 gün | 898,5 gün (CVCUSDT) |
| Son (uzlaşma sonrası) | 145 | 295.522 | 145 | 264,5 gün | 1.936,8 gün (BTCSTUSDT) |
| **Toplam** | **156** | **313.626** | 156 | | |

Toplam 4h bar 3.692.573 = dönem içi 3.378.942 + dolgu 313.626 (**%8,5** dolgu).
Eski kural bu dolgu barlarını dönem içinde sayıyordu (§5).

**İç dolgu koşuları (tamamı):**

| Sembol | Başlangıç | Bitiş | Gün |
|---|---|---|---|
| CVCUSDT | 2022-11-29 12:00 | 2025-05-15 20:00 | 898,5 |
| CVXUSDT | 2024-05-14 12:00 | 2025-07-22 20:00 | 434,5 |
| SLPUSDT | 2024-05-15 12:00 | 2025-07-22 20:00 | 433,5 |
| CTKUSDT | 2024-04-01 12:00 | 2025-04-29 20:00 | 393,5 |
| LITUSDT | 2025-01-31 12:00 | 2025-12-22 20:00 | 325,5 |
| TLMUSDT | 2022-06-09 12:00 | 2023-02-28 20:00 | 264,5 |
| MAVIAUSDT | 2024-12-16 12:00 | 2025-03-25 20:00 | 99,5 |
| ICPUSDT | 2022-06-10 12:00 | 2022-08-31 20:00 | 82,5 |
| AIAUSDT | 2025-12-11 16:00 | 2026-01-19 20:00 | 39,3 |
| PUMPUSDT | 2025-06-13 12:00 | 2025-07-09 20:00 | 26,5 |
| AERGOUSDT | 2025-03-27 12:00 | 2025-04-15 20:00 | 19,5 |

**Serinin ortasındaki kısa (1–5 bar) sıfır hacim koşusu: 0.** F1 ölçümü S2 ile aynı.
`tests/test_kisa_sifir_kosusu.py` bunu önbellekteki tüm dahil sembollerde tarar ve
böyle bir koşu çıkarsa `KisaSifirKosusuUyarisi` verir.

## 4. Funding'siz dönemler

Ön-kayıt §2 rev.7: hiç funding kaydı olmayan dönem üç hipotezde de kullanılmaz.

| Sembol | Dönem | Başlangıç | Bitiş | Gerçek bar |
|---|---|---|---|---|
| ICPUSDT | 0 | 2021-05-11 00:00 | 2022-06-10 08:00 | 2.373 |
| TLMUSDT | 0 | 2021-07-16 00:00 | 2022-06-09 08:00 | 1.971 |

İkisi de iki dönemli sembollerin **ilk** dönemi; ikinci dönemlerinde funding var.
Bu iki dönem toplam 4.344 gerçek bar eder.

**Dönem sonrası funding kayıtları** (ön-kayıt §2 rev.7: yok sayılır):

| Kalem | Kayıt | Sembol |
|---|---|---|
| Toplam funding kaydı (toplam dönem içinde) | 2.562.456 | 678 |
| Atılan: son dönemden sonra | 63.718 | 57 (38 SETTLING + 19 exchangeInfo dışı) |
| Atılan: iki dönem arasındaki dolguya düşen | 8.881 | 12 |
| **Atılan toplam** | **72.599** | **68** |
| Korunan: ilk dönem başlangıcından önce | 936 | 150 |

Son dönemden sonraki kayıtlar 57 sembolün 54'ünde dönem kapanışından en geç 8 saat
sonra başlıyor; sembol başına 1–2 farklı oran değeri içeriyor (ön-kayıttaki "bir ya da
birkaç sabit oran" gözlemiyle uyumlu).

⚠️ **Ön-kayıt metniyle sayı farkı.** §2 rev.7 "38 sembolde uzlaşma sonrasında da funding
kaydı yayınlandığını" yazıyor. 38 yalnızca SETTLING sembollerin sayısıdır; exchangeInfo
dışı 19 sembolde de aynı durum var ve toplam **57**. Kural (kayıtları yok say) iki grup
için de aynı işliyor, hesap etkilenmiyor; yalnızca metindeki sayı eksik.
Ön-kayıt kilitli olduğu için dokunulmadı.

## 5. Dönem sonu değişimlerinin özeti (rev.7 öncesi → rev.7)

Karşılaştırma: `a66a5e0:data/universe.csv` (ay düzeyi, karantinalı) ile commit
edilmiş rev.7 tablosu. Eski son sınır = eski son dönemin son ayındaki son 4h bar,
serinin son barına kırpılmış.

| Kalem | Değer |
|---|---|
| Dönem sonu değişen sembol | **147 / 678** |
| Dönem sonu daha **erken** biten | 147 |
| Dönem sonu daha geç biten | 0 |
| Başlangıcı değişen | 2 (BNXUSDT −153 gün, MINAUSDT −21,7 gün: karantina ayları artık dönem içinde) |
| Dönem sayısı değişen | 1 (TLMUSDT 4 → 2) |
| Toplam dönem | 692 → 690 |

**Kısalma miktarı (147 sembol):**

| Kısalma | Sembol |
|---|---|
| ≤ 1 gün | 2 (AKROUSDT 4 saat, LUNAUSDT 16 saat) |
| 1–7 gün | 4 |
| 7–31 gün | 11 |
| 31–90 gün | 9 |
| 90–365 gün | 76 |
| 1–2 yıl | 30 |
| > 2 yıl | 15 |

Medyan kısalma 237,5 gün, en büyüğü 1.936,8 gün. En büyük beşi: BTCSTUSDT (1.936,8),
SCUSDT (1.536,5), FTTUSDT (1.386,7), RAYUSDT (1.385,7), STRAXUSDT (899,5). Eski
kuralda bu sembollerin dönemi uzlaşmadan sonra yıllarca sıfır hacimli sabit fiyatlı
dolgu barlarla devam ediyordu. Kısalan 147'nin 145'i §3'teki sondaki dolgu
koşularıdır; kalan ikisi (AKRO, LUNA) eşik altı sondaki sıfır barlardır.

Veri sonuna yakın uzlaşanlarda da fark var: ACXUSDT, HFTUSDT, VANRYUSDT, VICUSDT
(24,5 gün, deliveryDate 2026-08-07) ve ICXUSDT, SCRTUSDT, STORJUSDT (5,5 gün).

## 6. SETTLED ayları (yalnızca denetim)

34 SETTLED ayı, 13 sembol. Her ayda dolgu koşusu ya da dönem sınırı var mı:

| | Dönem sınırı var | Dönem sınırı yok |
|---|---|---|
| Dolgu koşusu var | 11 | 5 |
| Dolgu koşusu yok | 5 | **13** |

13 ayda ne dolgu ne dönem sınırı var: bu aylarda seri kesintisiz işlem görmüş.
Rev.7'deki "34 karantina ayının 14'ünde dolgu koşusu bulunmayan" ölçümüyle aynı
yönde (burada ölçüt dolgu **ve** dönem sınırı yokluğu olduğu için sayı 13).

## 7. Kapsama ve bar boşlukları

| Kalem | Değer |
|---|---|
| Toplam 4h bar | 3.692.573 |
| Eksik bar (kesintisiz ızgaraya göre) | 1.965 (%0,053) |
| Türetilmiş 1d gün | 615.043 |

3 bardan uzun 105 boşluk, zaman örtüşmesine göre **10 olay** (önceki raporla aynı).
Bunların **3'ü** 7 günden uzun olduğu için dönemi böler:

| Sembol | Başlangıç | Bitiş | Eksik bar | Etki |
|---|---|---|---|---|
| TLMUSDT | 2023-03-01 00:00 | 2023-03-30 08:00 | 177 | iç dolguya bitişik; sınır zaten dolguda |
| ICPUSDT | 2022-09-01 00:00 | 2022-09-26 20:00 | 156 | iç dolguya bitişik; sınır zaten dolguda |
| BNXUSDT | 2023-02-01 00:00 | 2023-02-22 08:00 | 129 | **dönemi tek başına böler** |

Kalan 7 olay 18 bar ve altındadır; rev.3 boşluk kurallarına tabidir. En büyük ikisi
2022-02-26…28 (48 sembol, 18 bar) ve 2022-04-01…02 (49 sembol, 12 bar).

## 8. Veri bütünlüğü (|open[t] / close[t−1] − 1| > 0.30) — tam liste

**10 kayıt: 8'i dönem başı (dönem bölme kuralıyla açıklanıyor), 2'si dönem içi kısa
boşluk sonrası.** Dönem içinde bitişik barlar arasında sıçrama: **0**.

| Sembol | Zaman | Önceki bar | Eksik süre | Bağıl fark | Sınıf | SETTLED ayı |
|---|---|---|---|---|---|---|
| LITUSDT | 2025-12-23 16:00 | 2025-12-22 20:00 | 16 s | %531 | dönem başı | evet |
| AERGOUSDT | 2025-04-16 08:00 | 2025-04-15 20:00 | 8 s | %392 | dönem başı | evet |
| CVXUSDT | 2025-07-23 08:00 | 2025-07-22 20:00 | 8 s | %115 | dönem başı | evet |
| BNXUSDT | 2023-02-22 12:00 | 2023-01-31 20:00 | 516 s | %98 | dönem başı | evet |
| PUMPUSDT | 2025-07-10 04:00 | 2025-07-09 20:00 | 4 s | %87 | dönem başı | evet |
| MAVIAUSDT | 2025-03-26 16:00 | 2025-03-25 20:00 | 16 s | %72 | dönem başı | evet |
| **WAVESUSDT** | 2022-03-01 00:00 | 2022-02-25 20:00 | 72 s | %54 | **dönem içi, boşluk sonrası** | hayır |
| CTKUSDT | 2025-04-30 08:00 | 2025-04-29 20:00 | 8 s | %49 | dönem başı | evet |
| TLMUSDT | 2023-03-30 12:00 | 2023-02-28 20:00 | 708 s | %40 | dönem başı | evet |
| **KNCUSDT** | 2022-03-01 00:00 | 2022-02-25 20:00 | 72 s | %31 | **dönem içi, boşluk sonrası** | hayır |

Dönem başı kayıtlarında önceki bar ya dolgu barı ya da uzun boşluğun öbür yanıdır;
sıçrama iki dönem arasındadır ve hiçbir pencere dönem başını aşamaz.
WAVESUSDT ve KNCUSDT önceki raporda da tespit edilmişti: 2022-02-26…28 kesintisinin
ardından ilk bar. Rev.3 tamlık şartı bunları zaten dışarıda bırakır
(`tests/test_pencere.py`). Ön-kayıt §2 "dönem bölme kurallarıyla açıklanamayan
kayıtlar F2'den önce ayrı revizyonla ele alınır" diyor; bu ikisi dönem kuralıyla
değil, rev.3 boşluk kuralıyla açıklanıyor. Ayrı bir revizyon gerekip gerekmediği
sizin kararınız.

## 9. 60 günden kısa listeleme dönemleri

| Sembol | Başlangıç | Bitiş | Gün |
|---|---|---|---|
| 牛来USDT | 2026-08-30 08:00 | 2026-08-31 20:00 | 1,7 |
| BTCSTUSDT | 2021-03-04 04:00 | 2021-03-12 00:00 | 8,0 |
| DOSUSDT | 2026-08-11 12:00 | 2026-08-31 20:00 | 20,5 |
| GRVTUSDT | 2026-07-31 12:00 | 2026-08-31 20:00 | 31,5 |
| DATAIPUSDT | 2026-07-03 04:00 | 2026-08-31 20:00 | 59,8 |

Önceki rapordaki üç kayıt (DOSUSDT, TLMUSDT dönem 1, 牛来USDT) ay düzeyinde "31 gün"
görünüyordu. Bar düzeyinde TLMUSDT'nin eski kısa dönemi yok, BTCSTUSDT (uzlaşma
sonrası dolgusu kesilince 8 gün kaldı), GRVTUSDT ve DATAIPUSDT eklendi. 30 günlük
listeleme yaşı şartı ilk üçünü tümüyle etkisiz bırakır.

## 10. Uygunluk eşiğini geçen sembol sayısı (yıllara göre)

Rev.7 dönemleriyle; funding'siz iki dönem sayılmadı; küme sınırı uygulanmadı
(denetim tüm geçmişi ölçer). "Geçen" = yıl içinde en az bir 4h barda uygun.

| Yıl | Verisi olan | ≥10M (H1, H2) | ≥2M (H3) | Önceki rapor (10M / 2M) |
|---|---|---|---|---|
| 2020 | 80 | 61 | 77 | 61 / 77 |
| 2021 | 136 | 130 | 130 | 132 / 132 |
| 2022 | 159 | 154 | 157 | 155 / 158 |
| 2023 | 248 | 229 | 234 | 229 / 234 |
| 2024 | 379 | 341 | 343 | 341 / 343 |
| 2025 | 607 | 538 | 569 | 539 / 572 |
| 2026 | 654 | 317 | 534 | 317 / 534 |

Farklar küçük (en çok 3 sembol) ve sembol düzeyinde ayrıştırılmadı. "Verisi olan"
2025'te 605 → 607: sayım artık türetilmiş günlük seriden değil 4h barlardan yapılıyor
(tam günü olmayan barlar da sayılıyor).

## 11. Funding aralıkları

Değişmedi: 8 saat 992.586 kayıt / 284 sembol · 4 saat 1.487.688 / 516 · 1 saat
78.690 / 162 · 2 saat 3.492 / 19. 678/678 sembolde funding verisi var.

## 12. 1d türetmesinin birincil 1d dosyalarıyla karşılaştırması

Değişmedi: 615.043 gün karşılaştırıldı; fiyat farkı 7 gün (%0,0011), hacim farkı 261
gün (%0,042). Fiyat farklı 7 günün 4'ü dönem başından sonraki ilk 30 gün içinde
(9,7–10,7. gün), 3'ü 2023-08-16'da (INJ, SFP, UNFI). 2023-08-16 hacim tarafında
192 sembolle baskın aykırı gün.

## 13. Ortam

Python 3.13.12 (Miniconda, `D:\Miniconda\python.exe`), Windows-10-10.0.19045-SP0,
pandas 2.3.3, numpy 2.4.4, pyarrow 21.0.0, requests 2.32.5.

---

## 14. Açık noktalar

1. **Ön-kayıt §2 rev.7 funding sayısı** (§4): "38 sembol" yalnızca SETTLING'i kapsıyor;
   doğrusu 57. Kural etkilenmiyor, metin eksik. Ön-kayıt kilitli; düzeltme revizyon
   ister.
2. **WAVESUSDT / KNCUSDT** (§8): dönem kuralıyla değil rev.3 boşluk kuralıyla
   açıklanıyor. Ön-kayıt §2'nin "ayrı revizyon" şartının bunlar için işletilip
   işletilmeyeceği sizin kararınız.
3. **exchangeInfo görüntüsü evrenden sonra alındı** (2026-09-18). Dahil sembollerin
   durumu `universe.csv` ile tutarlı (128 SETTLING, 28 dışarıda, tip uyuşmazlığı 0),
   ama `universe.csv` üretilirken kullanılan canlı yanıtın kendisi saklanmamıştı.
4. `data/exchange_info_anlik.json` kilitli dosya listesinde değil.

## 15. Tarihsel not: rev.3 boşluk kuralının etkisi

Önceki rapordaki "Revizyon 3 sonrası" tarama (birleşik eleme 19.763 bar-sembol,
%0,535) ay düzeyindeki eski dönemlerle yapılmıştı ve bu koşuda **yeniden
üretilmedi**. Rev.7 dönemleriyle sayılar farklı olabilir.
