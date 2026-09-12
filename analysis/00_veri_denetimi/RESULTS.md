# F1 Veri Denetimi — TAM EVREN (678 sembol)

**Durum:** Tam koşu. 678/678 sembol indirildi, **hata yok**.
**Koşu:** 2026-09-11 14:58 → 16:37 UTC+3, 12 iş parçacığı, checksum doğrulamalı.
**Veri katmanı kodu:** commit `e45eff6` ("Tam indirme icin eszamanlilik duzeltmesi
ve 2h funding testleri"). Bu rapordaki tablolar aynı commit'in veri katmanıyla
indirilmiş veriden üretilmiştir; rapor sonrası betik değişiklikleri yalnızca
özetleme/teşhis katmanına dokunur, indirme ve ayrıştırmaya dokunmaz.

**Kapsam:** Yalnızca kapsama ve bütünlük. Getiri, fiyat değişimi, volatilite,
funding ortalaması veya olay benzeri hiçbir istatistik hesaplanmamış ve
yazılmamıştır (CLAUDE.md §3.1).

Ham çıktılar: `sembol_ozeti_tam.csv`, `yillik_kapsama_tam.csv`,
`butunluk_sicramalari_tam.csv`, `bosluklar_tam.csv`, `bosluk_olaylari_tam.csv`,
`funding_araliklari_tam.csv`, `cross_dogrulama_tam.csv`,
`cross_yogun_tarihler_tam.csv`, `fiyat_farki_listeleme_yasi_tam.csv`,
`karantina_kaybi_tam.csv`, `kisa_donemler_tam.csv`, `ortam_tam.csv`.

---

## 1. Evren ve bölme

| Kalem | Sayı |
|---|---|
| Bucket'taki USDT perpetual dizini | 864 |
| **Evrene dahil** | **678** |
| Hariç: `contractType = TRADIFI_PERPETUAL` | 179 |
| Hariç: endeks sözleşmesi | 6 |
| Hariç: stablecoin tabanlı çift (USDCUSDT) | 1 |
| Dahil olanlardan delist edilmiş | 28 |

**Bölme (`data/split.csv`):** 678 sembol → 669 varlık anahtarı.
A: 333 varlık / 333 sembol · B: 336 varlık / 345 sembol.
Dokuz yeniden adlandırma zinciri tek varlık anahtarında birleşti.

**Delist sembollerin geçmişi: 28/28 eksiksiz indirildi** (toplam 127.834 bar).
Ön-kayıt §2'deki "kötümser yanlılık" etiketi **gerekmiyor**; hayatta kalma
yanlılığı bu veri kümesinde yok.

## 2. Kapsama

| Kalem | Değer |
|---|---|
| Toplam 4h bar | 3.692.573 |
| Beklenen (kesintisiz ızgara) | 3.694.538 |
| Eksik bar | 1.965 (**%0.053**) |
| Türetilmiş 1d gün | 615.043 |

### Eksik bar oranının sembol başına dağılımı

| Eksik oran | Sembol |
|---|---|
| 0 (tam) | 618 |
| %0–0.1 | 8 |
| %0.1–0.5 | 47 |
| %0.5–1 | 1 |
| >%1 | 4 |

En yüksek dördü: BNXUSDT %1.64 (159 bar), TLMUSDT %1.58 (177), ICPUSDT %1.34
(156), LUNAUSDT %1.06 (30). İlk üçü karantinalı sembollerdir; boşlukları
sözleşmenin yerinde kapatılıp yeniden açılmasıyla örtüşür.

## 3. Bar boşlukları (3 bardan uzun)

105 boşluk kaydı, **zaman örtüşmesine göre 10 olaya** toplandı. Örtüşen
boşluklar tek olay sayıldı; olayın başlangıcı en erken başlangıç, bitişi en geç
bitiştir.

### Borsa geneli / sembole özgü

Kural: olay, o zaman aralığında verisi bulunan sembollerin **en az yarısını**
etkiliyorsa borsa genelidir.

| Grup | Olay |
|---|---|
| Borsa geneli (≥%50) | **0** |
| Sembole özgü | 10 |

### En uzun 10 olay (tamamı)

| # | Başlangıç | Bitiş | Etkilenen | O aralıkta verisi olan | Oran | Azami eksik bar |
|---|---|---|---|---|---|---|
| 7 | 2023-03-01 00:00 | 2023-03-30 08:00 | 1 (TLMUSDT) | 174 | %0.6 | 177 |
| 5 | 2022-09-01 00:00 | 2022-09-26 20:00 | 1 (ICPUSDT) | 148 | %0.7 | 156 |
| 6 | 2023-02-01 00:00 | 2023-02-22 08:00 | 1 (BNXUSDT) | 165 | %0.6 | 129 |
| 0 | 2022-02-26 00:00 | 2022-02-28 20:00 | **48** | 137 | **%35** | 18 |
| 4 | 2022-08-10 00:00 | 2022-08-12 20:00 | 1 (BNXUSDT) | 141 | %0.7 | 18 |
| 1 | 2022-04-01 00:00 | 2022-04-02 20:00 | **49** | 141 | **%35** | 12 |
| 2 | 2022-04-17 00:00 | 2022-04-17 20:00 | 1 (BNXUSDT) | 141 | %0.7 | 6 |
| 3 | 2022-06-09 00:00 | 2022-06-09 20:00 | 1 (BNXUSDT) | 141 | %0.7 | 6 |
| 8 | 2025-03-26 00:00 | 2025-03-26 12:00 | 1 (MAVIAUSDT) | 413 | %0.2 | 4 |
| 9 | 2025-12-23 00:00 | 2025-12-23 12:00 | 1 (LITUSDT) | 603 | %0.2 | 4 |

⚠️ **Eşiğe dikkat edilmesi gereken nokta.** 0 ve 1 numaralı olaylar 48 ve 49
sembolü *aynı dakikada, aynı pencerede* etkiliyor. Bu açıkça sembole özgü bir
durum değil, ama etkilenen oran %35 olduğu için %50 eşiğini geçmiyor ve kural
gereği "sembole özgü" sayılıyor. Sayı sıfır diye borsa geneli boşluk yok
denemez; eşik bu iki olayı ıskalıyor. Revizyon 3 için eşiği düşürmek ya da
"aynı pencerede N'den çok sembol" gibi ikinci bir ölçüt eklemek düşünülebilir.

## 4. Veri bütünlüğü (|open[t] / close[t−1] − 1| > 0.30) — tam liste

**10 sıçrama bulundu: 8'i karantinayla açıklanıyor, 2'si açıklanmıyor.**

### 4a. Karantinayla açıklananlar (8)

| Sembol | Zaman | Önceki close | Open | Bağıl fark | Karantina ayı |
|---|---|---|---|---|---|
| LITUSDT | 2025-12-23 16:00 | 0.592 | 3.734 | +531% | 2025-12 |
| AERGOUSDT | 2025-04-16 08:00 | 0.0667 | 0.328 | +392% | 2025-04 |
| CVXUSDT | 2025-07-23 08:00 | 2.374 | 5.104 | +115% | 2025-07 |
| BNXUSDT | 2023-02-22 12:00 | 85.59 | 1.411 | −98% | 2023-02 |
| PUMPUSDT | 2025-07-10 04:00 | 0.0471 | 0.00595 | −87% | 2025-07 |
| MAVIAUSDT | 2025-03-26 16:00 | 1.4929 | 0.4179 | −72% | 2025-03 |
| CTKUSDT | 2025-04-30 08:00 | 1.0106 | 0.5149 | −49% | 2025-04 |
| TLMUSDT | 2023-03-30 12:00 | 0.0347 | 0.02073 | −40% | 2023-03 |

Hepsinde o ay için `SETTLED` kaydı var. Token yeniden fiyatlandırması.

### 4b. Karantinayla AÇIKLANAMAYANLAR (2)

| Sembol | Zaman | Önceki close | Open | Bağıl fark | O ay SETTLED kaydı |
|---|---|---|---|---|---|
| WAVESUSDT | 2022-03-01 00:00 | 10.544 | 16.246 | **+54.1%** | **yok** |
| KNCUSDT | 2022-03-01 00:00 | 1.862 | 2.444 | **+31.3%** | **yok** |

**İkisi de yeniden fiyatlandırma değil — veri boşluğu kaynaklı.** Her ikisi de
0 numaralı boşluk olayının (2022-02-26 00:00 → 2022-02-28 20:00, 18 bar)
hemen ardından gelen **ilk bar**. Fiyat boşluk süresince hareket etmiş; barlar
boşluğun iki yanında kesintisiz ve normal:

```
WAVESUSDT  2022-02-25 20:00  open 10.282  close 10.544   <- boslugun oncesi
           [2022-02-26 .. 2022-02-28 : 18 bar eksik]
           2022-03-01 00:00  open 16.246  close 17.555   <- boslugun sonrasi
```

Her iki sembol de 0 numaralı olayın etkilediği 48 sembolün içinde.

Ön-kayıt §2 rev.2, karantinayla açıklanamayan kayıtlar için F2'den önce ayrı bir
revizyon kararı istiyor. Bu ikisinin nedeni belirlenmiştir (veri boşluğu,
yeniden fiyatlandırma değil); karar sizindir (bkz. §9).

## 5. Karantina kaybı

Karantina yüzünden dışarıda kalan toplam: **34 sembol-ay**, 13 sembolde.

| Sembol | Karantina ayı | Aylar |
|---|---|---|
| ICPUSDT | 9 | 2022-01 … 2022-09 (kesintisiz) |
| TLMUSDT | 9 | 2022-01, 02, 04, 05, 06, 07, 08 · 2023-02, 03 |
| BNXUSDT | 6 | 2022-04 … 2022-08 · 2023-02 |
| AERGOUSDT, AIAUSDT, CVCUSDT, CTKUSDT, LITUSDT, CVXUSDT, MAVIAUSDT, MINAUSDT, PUMPUSDT, SLPUSDT | 1'er | — |

En çok kayıplı 5: ICPUSDT (9), TLMUSDT (9), BNXUSDT (6), ardından 1 aylık
10 sembol.

## 6. 60 günden kısa listeleme dönemleri

Yalnızca 3 tane; asgari dönem kuralı eklenmedi (30 günlük uygunluk penceresi
bunları zaten etkisiz bırakıyor).

| Sembol | Dönem | Gün |
|---|---|---|
| DOSUSDT | 2026-08 → 2026-08 | 31 |
| TLMUSDT | 2022-03 → 2022-03 (dönem 1) | 31 |
| 牛来USDT | 2026-08 → 2026-08 | 31 |

## 7. Uygunluk eşiğini geçen sembol sayısı (yıllara göre)

Uygunluk ön-kayıt rev.2 kurallarıyla: pencere dönem başlangıcını aşamaz,
karantina günleri uygun sayılmaz, listeleme yaşı dönem başında sıfırlanır.

| Yıl | Veri bulunan | ≥10M (H1, H2) | ≥2M (H3) |
|---|---|---|---|
| 2020 | 80 | 61 | 77 |
| 2021 | 136 | 132 | 132 |
| 2022 | 159 | 155 | 158 |
| 2023 | 248 | 229 | 234 |
| 2024 | 379 | 341 | 343 |
| 2025 | 605 | 539 | 572 |
| 2026 | 654 | 317 | 534 |

2026'daki düşüş listeleme yaşından: o yıl listelenen çok sayıda sembol 30 günlük
yaş ve hacim penceresini yıl içinde dolduramıyor.

## 8. Funding

**678/678 sembolde funding verisi var ve mum geçmişiyle örtüşüyor.** Kapsama
boşluğu veya örtüşmeyen sembol **yok**.

### Ödeme aralığı dağılımı

| Aralık | Kayıt | Sembol |
|---|---|---|
| 8 saat | 992.586 | 284 |
| 4 saat | 1.487.688 | 516 |
| 1 saat | 78.690 | 162 |
| **2 saat** | **3.492** | **19** |

8 saat dışına çıkan sembol: **520**. Artık çoğunluk 4 saatlik aralıkta.

⚠️ **Ön-kayıtla çelişki (Revizyon 3'te düzeltilecek):** §2 yalnızca "4 saatlik
veya 1 saatlik" diyor; veride **2 saatlik** aralık da var (19 sembol, 3.492
kayıt). Kod genel formüle (`oran × 8 / aralık`) dayandığı için doğru
normalleştiriyor; düzeltilmesi gereken metin. Bu davranış testle sabitlendi
(`test_genel_formul_her_araligi_kapsar`).

## 9. 1d türetmesinin birincil 1d dosyalarıyla karşılaştırması

Karşılaştırılan gün: **615.043** (678 sembol, hepsi karşılaştırıldı).

| Alan | Farklı gün | Oran |
|---|---|---|
| Fiyat (open, high, low, close) | **7** | %0.0011 |
| Hacim (volume, quote_volume) | 261 | %0.042 |

Türetme fiyat tarafında 615.036/615.043 birebir aynı.

### Fiyat farkı olan 7 günün tamamı ve listeleme yaşı

| Sembol | Gün | İlk bar | Listelemeden sonra | İlk 30 gün içinde |
|---|---|---|---|---|
| XRPUSDT | 2020-01-16 | 2020-01-06 | 9.7 gün | **evet** |
| TRUMPUSDT | 2025-01-29 | 2025-01-18 | 10.5 gün | **evet** |
| XRPUSDT | 2020-01-17 | 2020-01-06 | 10.7 gün | **evet** |
| EOSUSDT | 2020-01-19 | 2020-01-08 | 10.7 gün | **evet** |
| INJUSDT | 2023-08-16 | 2022-08-17 | 364 gün | hayır |
| SFPUSDT | 2023-08-16 | 2021-02-24 | 903 gün | hayır |
| UNFIUSDT | 2023-08-16 | 2021-02-19 | 908 gün | hayır |

**4/7'si sembolün listelenmesinden sonraki ilk 30 gün içinde** (hepsi 9–11.
günlerde). Kalan 3'ü tek bir tarihte toplanıyor: 2023-08-16.

### En yoğun 5 tarih

| Tarih | Tip | Sembol sayısı |
|---|---|---|
| 2023-08-16 | hacim | **192** |
| 2023-09-19 | hacim | 13 |
| 2023-09-20 | hacim | 13 |
| 2023-11-30 | hacim | 11 |
| 2023-09-21 | hacim | 9 |
| 2023-08-16 | fiyat | 3 |

**2023-08-16 baskın bir aykırı gün:** 192 sembolde hacim, 3 sembolde fiyat farkı.
Kaynak tarafında o güne özgü bir yayın tutarsızlığı; 4h dosyalarının toplamı ile
1d dosyası uyuşmuyor. Kararınız uyarınca uygunluk hacmi türetilmiş seriden
gelmeye devam ediyor; 30 günlük medyan kullanıldığı için tek günlük fark eşiği
taşımıyor.

## 10. Ortam

| Bileşen | Sürüm |
|---|---|
| Python | 3.13.12 (Miniconda, `D:\Miniconda\python.exe`, derleme 2026-02-24) |
| Platform | Windows-10-10.0.19045-SP0 |
| pandas | 2.3.3 |
| numpy | 2.4.4 |
| pyarrow | 21.0.0 |
| requests | 2.32.5 |

Koşu **Miniconda Python** ile yapılmıştır.

---

## 11. Karar gerektiren noktalar (Revizyon 3 için)

1. **İki açıklanamayan sıçrama** (WAVESUSDT, KNCUSDT, ikisi de 2022-03-01 00:00).
   Nedeni belirlendi: 18 barlık veri boşluğu, yeniden fiyatlandırma değil.
   Karantinaya alınsın mı, yoksa "boşluk sonrası ilk bar" olarak ayrı bir kuralla
   mı ele alınsın? Boşluk sonrası ilk barda giriş yapılması zaten sorunlu; genel
   bir "boşluğu aşan pencere geçersizdir" kuralı ikisini de kapsar.
2. **Borsa geneli boşluk eşiği.** %50 eşiği, 48–49 sembolü aynı pencerede
   etkileyen iki olayı (%35) ıskalıyor. Eşik düşürülsün mü, ikinci ölçüt
   eklensin mi?
3. **2 saatlik funding aralığı.** §2 metni düzeltilecek (19 sembol, 3.492 kayıt).
4. **Zamanla tanımlı ortak pencere yardımcısı.** Ayrı olarak raporlandı:
   mevcut dört pencere noktasından üçü bar sırasıyla sayıyor, biri (1d türetmesi)
   zaten zaman ve tamlık temelli.

## 12. Sonraki adım

Revizyon 3 metninden sonra F2 (keşif). Bu rapordaki hiçbir sayı getiri, olay ya
da fiyat davranışı içermez; keşif verisine bakılmamıştır.

---

## 13. Revizyon 3 sonrası: veri boşluğu kuralının etkisi

Ön-kayıt §2 rev.3'ün tamlık şartı (bir pencerede tek bar bile eksikse değer
hesaplanmaz), 4 saatlik seride aşağıdaki kadar bar-sembol kombinasyonunu olay
üretmekten çıkarır. Tarama tüm evren üzerinde yapılmıştır (3.692.251 bar,
boşluk içeren 60 sembol).

| Pencere | Uzunluk | Elenen bar-sembol |
|---|---|---|
| H1 hacim medyanı | 180 bar | 19.647 |
| H2 önceki yükseliş | 30 bar | 3.248 |
| H2 yapı kırılımı (k azami) | 12 bar | 1.232 |
| H1 yükseliş penceresi | 6 bar | 560 |
| **En az bir pencereden elenen (birleşik)** | — | **19.763** |

Birleşik eleme toplam barın **%0.535**'idir. Baskın katkı H1'in 180 barlık
hacim penceresinden gelir; uzun pencere, bir boşluğu daha uzun süre "taşır".

Bu sayım yalnızca kaç barın pencere kuralına takıldığını ölçer; hiçbir olay,
getiri veya fiyat davranışı hesaplanmamıştır.

Kuralın hedeflediği iki kayıt (WAVESUSDT ve KNCUSDT, 2022-03-01 00:00) bu
elemenin içindedir ve `tests/test_pencere.py` içinde gerçek veriyle
doğrulanmıştır.
