# F1 Veri Denetimi — ÖRNEK KOŞU (30 sembol)

**Durum:** Örnek koşu. Tam evren (678 sembol) henüz indirilmedi.
**Tarih:** 2026-09-11 · **Commit:** `68e9e0e` · **Betik:** `calistir.py --ornek`
**Kapsam:** Yalnızca kapsama ve bütünlük. Getiri, fiyat değişimi, volatilite,
funding ortalaması veya olay benzeri hiçbir istatistik hesaplanmamış ve
yazılmamıştır (CLAUDE.md §3.1).

Ham çıktılar: `sembol_ozeti_ornek.csv`, `yillik_kapsama_ornek.csv`,
`butunluk_sicramalari_ornek.csv`, `uzun_bosluklar_ornek.csv`,
`cross_dogrulama_ornek.csv`.

---

## 1. Evren (tam bucket taraması, fiyat verisi indirilmeden)

| Kalem | Sayı |
|---|---|
| Bucket'taki USDT perpetual dizini | 864 |
| **Evrene dahil** | **678** |
| Hariç: `contractType = TRADIFI_PERPETUAL` | 179 |
| Hariç: endeks sözleşmesi | 6 |
| Hariç: stablecoin tabanlı çift (USDCUSDT) | 1 |
| Delist edilmiş (exchangeInfo'da yok) | 31 |

**Bölme (`data/split.csv`):** 678 sembol → 669 varlık anahtarı.
A: 333 varlık / 333 sembol · B: 336 varlık / 345 sembol.
Dokuz yeniden adlandırma zinciri tek varlık anahtarında birleşti.

**Listeleme dönemleri:** dahil 678 sembolün 666'sı tek dönem, 11'i iki dönem,
1'i (TLMUSDT) dört dönem. Karantina ayı olan 13 dahil sembol var.

Karantinalı semboller: AERGOUSDT, AIAUSDT, BNXUSDT, CTKUSDT, CVCUSDT, CVXUSDT,
ICPUSDT, LITUSDT, MAVIAUSDT, MINAUSDT, PUMPUSDT, SLPUSDT, TLMUSDT.

## 2. Örnek kümenin bileşimi

30 sembol, F1 planındaki kotalarla:

| Kota | Karşılandı | Semboller |
|---|---|---|
| ≥5 delist | 7 | SRMUSDT, HNTUSDT, MATICUSDT, EOSUSDT, GALUSDT, RNDRUSDT, BTSUSDT |
| ≥5 başlıksız 2020 dosyası | 8 | BTCUSDT, ETHUSDT, ADAUSDT, LINKUSDT, XRPUSDT, BCHUSDT, LTCUSDT, EOSUSDT |
| ≥5 4h funding | 16 | WIFUSDT, ORDIUSDT, MYXUSDT, AVNTUSDT, ASTERUSDT, POLUSDT, RENDERUSDT, GUSDT, AUSDT, CTKUSDT, LITUSDT, AERGOUSDT, BNXUSDT, TLMUSDT, HNTUSDT, SOLUSDT |
| ≥3 karantinalı (TLM + BNX dahil) | 6 | TLMUSDT, BNXUSDT, MINAUSDT, CTKUSDT, LITUSDT, AERGOUSDT |
| MATICUSDT + POLUSDT | var | ikisi de |

## 3. Kapsama

Toplam 4h bar: 258.457. Beklenen ızgaraya göre eksik: 464 bar (**%0.18**).

| Eksik oran | Sembol sayısı |
|---|---|
| 0 (tam) | 22 |
| %0–0.5 | 5 |
| %1.5–1.7 | 2 |
| diğer (%0.28) | 1 |

**Delist sembollerin geçmişi:** 7/7 sembolün tamamı eksiksiz indirildi.
Ön-kayıt §2'deki "kötümser yanlılık" notu bu örnek için **gerekmiyor**;
tam koşuda 31 delist sembolün tamamı için yeniden doğrulanacak.

### 3 bardan uzun boşluklar (14 adet)

| Sembol | Başlangıç | Bitiş | Eksik bar |
|---|---|---|---|
| TLMUSDT | 2023-03-01 00:00 | 2023-03-30 08:00 | 177 |
| BNXUSDT | 2023-02-01 00:00 | 2023-02-22 08:00 | 129 |
| XRPUSDT, LTCUSDT, LITUSDT, SOLUSDT | 2022-02-26 00:00 | 2022-02-28 20:00 | 18 (her biri) |
| BNXUSDT | 2022-08-10 00:00 | 2022-08-12 20:00 | 18 |
| XRPUSDT, LTCUSDT, LITUSDT, SOLUSDT | 2022-04-01 00:00 | 2022-04-02 20:00 | 12 (her biri) |
| BNXUSDT | 2022-04-17, 2022-06-09 | — | 6 (her biri) |
| LITUSDT | 2025-12-23 00:00 | 2025-12-23 12:00 | 4 |

İki gözlem:

1. **2022-02-26…28 ve 2022-04-01…02 boşlukları dört sembolde aynı anda** görülüyor.
   Sembole özgü değil, kaynak tarafında yayın boşluğu.
2. En uzun iki boşluk (TLMUSDT, BNXUSDT) karantina aylarının içinde; sözleşmenin
   yerinde kapatılıp yeniden açılmasıyla tutarlı.

**Not:** Aylık *dosya* düzeyinde 864 sembolün hiçbirinde boşluk yok (ayrıca
doğrulandı). Yukarıdaki boşlukların tamamı ay dosyalarının **içinde**; dosya adı
düzeyindeki kontrol bunları göremez.

## 4. Uygunluk eşiğini geçen sembol sayısı (yıllara göre)

Uygunluk ön-kayıt rev.2 kurallarıyla hesaplandı: pencere dönem başlangıcını
aşamaz, karantina günleri uygun sayılmaz, listeleme yaşı dönem başında sıfırlanır.

| Yıl | Veri bulunan | ≥10M (H1, H2) | ≥2M (H3) |
|---|---|---|---|
| 2020 | 13 | 10 | 13 |
| 2021 | 16 | 16 | 16 |
| 2022 | 18 | 18 | 18 |
| 2023 | 21 | 19 | 19 |
| 2024 | 26 | 23 | 23 |
| 2025 | 24 | 23 | 24 |
| 2026 | 23 | 17 | 21 |

## 5. Funding kapsaması

30/30 sembolde funding verisi var ve mum geçmişiyle zaman aralığı örtüşüyor.
Kapsama boşluğu veya örtüşmeyen sembol **yok**.

### Ödeme aralığı dağılımı

| Aralık | Kayıt | Sembol |
|---|---|---|
| 8 saat | 106.777 | 21 |
| 4 saat | 44.623 | 16 |
| 1 saat | 2.048 | 3 |
| **2 saat** | **205** | **2** |

8 saat dışına çıkan **19 sembol**. Kalıcı 4h'e geçenler (ORDIUSDT 2023-11'den,
WIFUSDT 2024-01'den, RENDERUSDT, POLUSDT, GUSDT, AUSDT, AVNTUSDT, ASTERUSDT,
MYXUSDT, CTKUSDT 2025-04'ten, LITUSDT 2025-12'den, TLMUSDT 2026-03'ten,
AERGOUSDT) dışında kısa süreli geçişler:

| Sembol | Aralık | Tarihler | Kayıt |
|---|---|---|---|
| SOLUSDT | 2 saat | 2022-11-10 → 2022-11-18 | 99 |
| AERGOUSDT | 2 saat | 2025-04-16 → 2025-04-25 | 106 |
| MYXUSDT | 1 saat | 2025-07-03 → 2025-10-12 | 1.955 |
| GUSDT | 1 saat | 2026-03-16 → 2026-03-19 | 66 |
| TLMUSDT | 1 saat | 2026-03-02 → 2026-03-03 | 27 |
| HNTUSDT | 4 saat | 2022-12-21 → 2022-12-26 | 27 |

⚠️ **Ön-kayıtla çelişki:** §2 yalnızca "4 saatlik veya 1 saatlik ödeme aralığına
geçmiş sözleşmeler"den söz ediyor. Veride ayrıca **2 saatlik** aralık var.
Kod bunu genel formülle (`oran × 8/aralık`) doğru normalleştiriyor, ancak
ön-kayıt metni bu durumu saymıyor. Karar gerekiyor (bkz. §8).

## 6. Veri bütünlüğü kontrolü (|open[t] / close[t−1] − 1| > 0.30)

**5 sıçrama bulundu; beşi de karantina ayında.** Karantinayla açıklanamayan
kayıt yok.

| Sembol | Zaman | Önceki close | Open | Bağıl fark | Karantina ayında |
|---|---|---|---|---|---|
| LITUSDT | 2025-12-23 16:00 | 0.592 | 3.734 | +531% | evet |
| AERGOUSDT | 2025-04-16 08:00 | 0.0667 | 0.328 | +392% | evet |
| BNXUSDT | 2023-02-22 12:00 | 85.59 | 1.411 | −98% | evet |
| CTKUSDT | 2025-04-30 08:00 | 1.0106 | 0.5149 | −49% | evet |
| TLMUSDT | 2023-03-30 12:00 | 0.0347 | 0.02073 | −40% | evet |

Bunların hepsi token yeniden fiyatlandırması kaynaklı yapay sıçramalardır.
Karantina kuralı olmasaydı LITUSDT ve AERGOUSDT kayıtları H1'in aradığı
"kısa sürede sert yükseliş" biçiminde sahte olay üretecekti.

## 7. 1d türetmesinin birincil 1d dosyalarıyla karşılaştırması

Karşılaştırılan gün: **43.116** (30 sembol).

| Alan | Farklı gün | Oran |
|---|---|---|
| Fiyat (open, high, low, close) | **3** | %0.007 |
| Hacim (volume, quote_volume) | 26 | %0.060 |

**Fiyat farkı olan üç gün** (hepsi veri dönemin en başında):

| Sembol | Gün | Azami bağıl fark |
|---|---|---|
| XRPUSDT | 2020-01-17 | %4.77 |
| XRPUSDT | 2020-01-16 | %3.04 |
| EOSUSDT | 2020-01-19 | %2.76 |

**Hacim farkı olan 26 günün 17'si tek bir tarihte: 2023-08-16.** Kaynak
tarafında o güne özgü bir yayın tutarsızlığı; 4h dosyalarının toplamı ile 1d
dosyası uyuşmuyor. Kalan 9 gün dağınık ve tekil.

Türetilmiş seride bulunup birincilde olmayan gün: 0. Birincilde olup
türetilmişte olmayan: sembol başına 0–2 gün (eksik 4h barı olan, bu yüzden
kuralca düşürülen günler).

**Değerlendirme:** türetme fiyat tarafında pratikte kusursuz (43.113/43.116).
Ön-kayıt rev.2 uygunluk hacmini türetilmiş seriden aldığı için, farkın hacimde
yoğunlaşması not edilmelidir; ancak uygunluk 30 günlük **medyan** kullandığından
tekil gün farkları eşiği taşıyacak boyutta değildir.

---

## 8. Karar gerektiren noktalar

1. **2 saatlik funding aralığı.** Ön-kayıt §2 yalnızca 4h ve 1h sayıyor.
   Kod genel formülle doğru çalışıyor. Metnin bir revizyonla düzeltilmesi mi,
   yoksa "sayılanlar örnektir" yorumu mu?
2. **2023-08-16 hacim tutarsızlığı.** Kaynak kaynaklı. Uygunluk hacmi için
   türetilmiş seri kullanılmaya devam mı edilsin?
3. **2020-01-16/17/19 fiyat farkları.** Üç gün, üç sembol. Ayrı bir işlem
   gerekiyor mu, yoksa kayda geçmesi yeterli mi?

## 9. Sonraki adım

Tam evren indirmesi (678 sembol) ve tam denetim raporu. Bu örnek koşu,
indirme zincirinin, karantina kuralının ve 1d türetmesinin uçtan uca
çalıştığını gösteriyor.
