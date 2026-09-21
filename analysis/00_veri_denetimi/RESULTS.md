# F1 Veri Denetimi — TAM EVREN (678 sembol), ön-kayıt rev.7

**Durum:** Tam koşu, 678/678 sembol, **hata yok**.
**Koşu:** 2026-09-20 20:43:09 → 21:02:05 UTC, 8 iş parçacığı, önbellekten,
`--eski-evren` (rev.7 öncesi tabloyla karşılaştırma, §5) açık.
**Kod:** `6aa73a4`, çalışma ağacı **temiz** (`ortam_tam.csv`; durum koşunun başında,
hiçbir çıktı yazılmadan alındı). Bu commit'te tam test takımı geçiyor (betik dışı sayı:
`pytest -q` çıktısından). Bu commit'ten sonraki commit'ler yalnızca bu raporun metnini
değiştirir; hiçbir çıktıyı etkilemez.
**A1 ölçümü:** aynı commit, aynı temiz ağaç, 2026-09-20 20:43:11 → 20:51:22 UTC
(`a1_ortam_tam.csv`). A1'in referans koşusu budur; daha eski A1 çıktılarının zamanı
dosya tarihinden türetilmişti ve artık kullanılmıyor (denetçi bulgusu D-B2).
**Önceki temiz koşudan (`16b012c` / `209f115`) farklar:**
- `sembol_ozeti`: `funding_son_donem_sonrasi_ilk_gecikme_bitisten_saat` sütunu eklendi.
- `rapor_sayilari`: 8 saat sayımı iki referansa ayrıldı, `rev8` bölümü eklendi.
- `a1_d_kurali`: 1 günlük çıkış ızgarası (H3) satırları ve `cikis_ani`,
  `kapanista_odeme`, `son_odeme_aralik_saat` sütunları eklendi.
- `a1_uzlasma_sonrasi_oranlar` ve `a1_teslimsiz_son_bar_funding`: çalışma ağacından
  kaldırıldı (D-B1).
- Diğer tüm `*_tam.csv` dosyaları birebir aynı.
**Evren:** commit edilmiş `data/universe.csv` (rev.7, bar düzeyinde dönemler).
**exchangeInfo:** depodaki görüntü `data/exchange_info_anlik.json`
(alınma 2026-09-18 11:31:55 UTC, ham yanıt SHA256 `41244d4d…58c6a`), canlı uç nokta değil.
**Toplam dönem kesimi:** tüm mum ve funding kayıtları 2020-01-01 → 2026-08-31 23:59:59
UTC aralığına kesildi (bucket'a sonradan eklenen aylar denetimi değiştirmesin diye).

**Kapsam:** Yalnızca kapsama ve bütünlük. Getiri, fiyat değişimi, volatilite,
funding ortalaması veya olay benzeri hiçbir istatistik hesaplanmamış ve
yazılmamıştır (CLAUDE.md §3.1). Bilinçli istisna, ön-kayıt §2'nin istediği
`|open/close[t-1] − 1| > 0.30` bütünlük listesidir.

**Sınır aşımı (§14.5).** A1 ölçümünün ilk hâli (1093e69) uzlaşma sonrası funding
kayıtlarının oran değerlerini ve işaretlerini raporladı. Bu, yukarıdaki kapsamın
dışındaydı ve bir sınır aşımıdır. **Değer düzeyindeki analiz rapordan çıkarıldı; 18
pozitif / 5 negatif işaret sayımı bilerek bırakıldı** ve bu sayım da aşımın parçasıdır
(gerekçesi §14.5'teki notta).

Ham çıktılar (`*_tam.csv`), `calistir.py`: `sembol_ozeti`, `delist_siniflandirmasi`,
`dolgu_kosulari`, `kisa_sifir_kosulari`, `funding_siz_donemler`, `donem_sonu_degisimleri`,
`settled_aylari`, `yillik_kapsama`, `butunluk_sicramalari`, `bosluklar`, `bosluk_olaylari`,
`funding_araliklari`, `cross_dogrulama`, `cross_yogun_tarihler`,
`fiyat_farki_listeleme_yasi`, `kisa_donemler`, `settled_icerik`, `donem_aralari`, `ortam`.
`rapor_sayilari_tam.csv` bu rapordaki sayıların kaynağıdır (bölüm, kalem, değer).
Ölçüm sayılarının tamamı bu dosyadan ya da ham `*_tam.csv` çıktılarından gelir
(denetçi bulgusu D-A5). **Betikten türetilmeyen sayılar** üçtür ve bulundukları yerde
"betik dışı" diye işaretlidir: (a) başlıktaki test takımı sonucu, (b) §10'daki "önceki
koşu" ve "rev.7 öncesi rapor" karşılaştırma sütunları, (c) §15'teki tarihsel not.
Rev.7 ile anlamını yitiren `karantina_kaybi_tam.csv` kaldırıldı.

A1 ölçümü (`a1_olcumu.py`):
- Varsayılan koşunun çıktıları (değer içermez): `a1_uzlasma_sonrasi_funding_tam.csv`,
  `a1_konumlar_tam.csv`, `a1_oneri_etkisi_tam.csv`, `a1_d_kurali_tam.csv`,
  `a1_ortam_tam.csv` (koşunun commit'i, çalışma ağacı durumu ve UTC zamanı).
- **Sınır aşımının iz dosyaları (oran değeri içerir).** Çalışma ağacından kaldırıldı;
  `1093e69` commit'inin içinde duruyorlar. Yolları:
  - `analysis/00_veri_denetimi/a1_uzlasma_sonrasi_oranlar_tam.csv`
  - `analysis/00_veri_denetimi/a1_teslimsiz_son_bar_funding_tam.csv`

  Okumak için: `git show 1093e69:analysis/00_veri_denetimi/a1_uzlasma_sonrasi_oranlar_tam.csv`.
  Betik bu dosyaları üretmez; oran değeri üreten kod yolu ve onu açan bayrak kaldırıldı.
  Yeniden üretmek bilinçli bir kod değişikliği ister
  (`tests/test_a1_deger_yolu_yok.py`).

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

Bölme (`data/split.csv`) değişmedi: 678 sembol → 669 varlık anahtarı (A 333, B 345
sembol). Bu sayılar artık betik tarafından `split.csv`'den sayılıyor
(`rapor_sayilari_tam.csv`, D-A5). İki dönemi ayıran şeyin türü `donem_aralari_tam.csv`'de.

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

Toplam 4h bar 3.692.573 = dönem içi 3.378.942 + dolgu 313.626 + **ne dönem ne dolgu 5**
(**%8,5** dolgu). Eski kural dolgu barlarını dönem içinde sayıyordu (§5).

**5 barlık fark (denetçi bulgusu D-C2).** Önceki rapor eşitliği bu 5 bar olmadan
yazmıştı; toplam tutmuyordu (3.378.942 + 313.626 = 3.692.568). Bu 5 bar AKROUSDT'de 1,
LUNAUSDT'de 4 bardır (`sembol_ozeti`, `ne_donem_ne_dolgu_bar`). İkisi de seriyi dolgu
eşiğinin (6 bar) altında kalan sondaki sıfır hacimli barlarla bitiriyor (§2). Dönem son
gerçek barda bittiği için bu barlar dönem dışı; koşu 6 bardan kısa olduğu için dolgu
da sayılmıyor.

**§6a'daki "dönem dışındaki 5 ayda birer bar" ile aynı değil.** Oradaki 5 bar AERGOUSDT
2025-04, CTKUSDT 2025-04, CVCUSDT 2025-05, MAVIAUSDT 2025-03 ve PUMPUSDT 2025-07'deki
farklı barlardır. Hepsi yeniden listelenen bir dönemin **ilk gerçek barı**, yani dönem
içindedir. SETTLED dosyası aynı zaman damgasında eski sözleşmenin dolgu barını taşır.
Buradaki 5 bar ise başka iki sembolde, dönem dışında. Sayıların eşit olması rastlantı.

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
| Atılan: iki dönem arasında, ayırıcı dolgu koşusu | 8.817 | 11 |
| Atılan: iki dönem arasında, ayırıcı eksik bar boşluğu (BNXUSDT) | 64 | 1 |
| **Atılan toplam** | **72.599** | **68** |
| Korunan: ilk dönem başlangıcından önce | 936 | 150 |

İki dönem arasındaki 8.881 kaydın hepsi dolguya düşmüyor. BNXUSDT'nin iki dönemini
dolgu değil 129 barlık (21,5 gün) eksik bar boşluğu ayırıyor (`bosluklar_tam.csv`); onun 64 kaydı bu boşluğa düşüyor
(`donem_aralari_tam.csv`, D-A5).

**"57'nin 54'ü" tutarsızlığı (denetçi bulgusu D-A5) çözüldü.** İlk uzlaşma sonrası
kaydın gecikmesi iki farklı ana göre ölçülebilir; betik ikisini de yazıyor
(`sembol_ozeti`):

| Referans | En geç 8 saat sonra başlayan | Sütun |
|---|---|---|
| Dönem **kapanışı** (son barın kapanışı, çıkış anı) | **57 / 57** | `funding_son_donem_sonrasi_ilk_gecikme_saat` |
| Dönem **bitişi** (son barın açılışı) | 53 / 57 | `funding_son_donem_sonrasi_ilk_gecikme_bitisten_saat` |

Bitişe göre 8 saati aşan 4 sembol: FTTUSDT, LUNAUSDT, RAYUSDT, SRMUSDT.

Eski rapordaki **54 hiçbir tanımla üretilemiyor**; betik dışı bir sayımdı ve yanlıştı.
Cümlenin kendi ifadesi ("dönem kapanışından en geç 8 saat sonra") kapanış referansını
kullanıyor, dolayısıyla doğru sayı **57 / 57**'dir.

⚠️ **Ön-kayıt metniyle sayı farkı.** §2 rev.7 "38 sembolde uzlaşma sonrasında da funding
kaydı yayınlandığını" yazıyor. 38 yalnızca SETTLING sembollerin sayısıdır; exchangeInfo
dışı 19 sembolde de aynı durum var ve toplam **57**. Kural (kayıtları yok say) iki grup
için de aynı işliyor, hesap etkilenmiyor; yalnızca metindeki sayı eksik.
Ön-kayıt kilitli olduğu için dokunulmadı.

## 5. Dönem sonu değişimlerinin özeti (rev.7 öncesi → rev.7)

Karşılaştırma: `a66a5e0:data/universe.csv` (ay düzeyi, karantinalı) ile commit
edilmiş rev.7 tablosu; isteğe bağlı `--eski-evren` adımı (D-B1). Eski son sınır = eski
son dönemin son ayındaki son 4h bar, serinin son barına kırpılmış.

**İç sınırlar (denetçi bulgusu D-A2).** Önceki sürüm yalnızca ilk başlangıcı ve son
bitişi karşılaştırıyordu. İç dönem sınırı değişen semboller bu yüzden "değişmedi"
sayılıyordu. CVCUSDT örneğin: eski dönem 0 iç dolguyu içine alıyordu. Artık serinin
her barı eski ve yeni kurala göre ayrı ayrı sınıflanıyor (`eski_ici_yeni_disi_bar`,
`yeni_ici_eski_disi_bar`).

| Kalem | Değer |
|---|---|
| **Dönemi değişen sembol** (en az bir bar sınıf değiştirdi) | **159 / 678** |
| Son bitişi daha **erken** | 147 |
| Son bitişi daha geç | 0 |
| **Yalnızca iç sınırı değişen** (ilk başlangıç ve son bitiş aynı) | **11** |
| Yalnızca başlangıcı değişen | 1 (MINAUSDT) |
| Başlangıcı değişen | 2 (BNXUSDT −153 gün, MINAUSDT −21,7 gün: karantina ayları artık dönem içinde) |
| Dönem sayısı değişen | 1 (TLMUSDT 4 → 2) |
| Toplam dönem | 692 → 690 |
| Eskide dönem içi, yenide dışı | 311.399 bar |
| Eskide dönem dışı, yenide içi | 3.397 bar |

Yalnızca iç sınırı değişen 11 sembol (eski içi → yeni dışı / eski dışı → yeni içi, bar):

| Sembol | Eski içi → yeni dışı | Eski dışı → yeni içi |
|---|---|---|
| CVCUSDT | 5.301 | 94 |
| CVXUSDT | 2.475 | 52 |
| SLPUSDT | 2.469 | 52 |
| CTKUSDT | 2.187 | 4 |
| LITUSDT | 1.821 | 50 |
| TLMUSDT | 918 | 780 |
| MAVIAUSDT | 447 | 32 |
| AIAUSDT | 122 | 70 |
| PUMPUSDT | 105 | 131 |
| AERGOUSDT | 27 | 88 |
| ICPUSDT | 0 | 987 |

"Eski içi → yeni dışı" barlar eski kuralın dönem içinde saydığı iç dolgu barlarıdır.
"Eski dışı → yeni içi" barlar eski karantina aylarının artık dönem içinde kalan
gerçek barlarıdır.

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

### 6a. SETTLED dosyalarının içeriği ana seriyle (denetçi bulgusu C3)

Her SETTLED ayında bucket'taki `<SEMBOL>SETTLED` dizininin 4h mumları ana seriyle
aynı zaman damgasında bar bar karşılaştırıldı (OHLC ve hacim, bağıl tolerans 1e-6).
Çıktı: `settled_icerik_tam.csv`; kod: `data/klines.py` `settled_ay_karsilastir`.

**Rev.7 ile dönem içine giren 13 ay** (BNXUSDT 2022-05…08, ICPUSDT 2022-01…05,
TLMUSDT 2022-01, 02, 04, 05):

| Kalem | Değer |
|---|---|
| Ortak bar | 2.310 |
| Fiyatı farklı bar | **0** |
| Hacmi farklı bar | **0** |
| Yalnızca SETTLED'da olan bar | 24 (BNXUSDT 2022-06: 6, 2022-08: 18) |
| Yalnızca ana seride olan bar | 30 (TLMUSDT 2022-02: 18, 2022-04: 12) |

Ortak barların tamamı birebir aynı; dönem içine alınan 13 ayda SETTLED dosyası ana
seriden farklı bir fiyat taşımıyor. BNXUSDT'nin SETTLED dosyasındaki 24 fazla bar,
ana serideki 2022-06-09 (6 bar) ve 2022-08-10…12 (18 bar) boşluklarının tam yerine
düşüyor. Bu barlar ana seriye alınmıyor; SETTLED bilgisi hiçbir kurala girmez.

**Kalan 21 ay (dolgu ya da dönem sınırı olan):** 1.451 ortak bar, 5'inde fark var
(AERGOUSDT 2025-04, CTKUSDT 2025-04, CVCUSDT 2025-05, MAVIAUSDT 2025-03, PUMPUSDT
2025-07). Beşinde de farklı bar, yeniden listelenen dönemin **ilk barı**. Ana seride
yeni sözleşmenin gerçek (sıfır olmayan hacimli) barı var. SETTLED dosyasında ise aynı
zaman damgasında eski sözleşmenin sıfır hacimli, eski fiyatlı dolgu barı var.
BNXUSDT 2023-02, ICPUSDT 2022-09 ve TLMUSDT 2023-03'te SETTLED barları ana serinin
7 günden uzun boşluklarına düşüyor (128, 152, 177 bar); ortak bar yok.

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

**Payda (denetçi bulgusu D-C1).** "Verisi olan" artık yalnızca o yıl bir listeleme
dönemiyle kesişen, yani en az bir **gerçek** barı olan sembolleri sayar. Önceki sürüm
yalnızca dolgu barı olan (uzlaşmış, işlem görmeyen) sembolleri de sayıyordu. Bunlar
ayrı sütunda.

Son iki sütun **betik dışıdır**: biri bu turdan önceki koşunun çıktısından, diğeri
rev.7 öncesi rapordan alınmıştır; bu koşunun hiçbir CSV'sinden türetilemez.

| Yıl | Verisi olan (gerçek bar) | Yalnızca dolgu barı olan | ≥10M (H1, H2) | ≥2M (H3) | Önceki koşu: verisi olan (betik dışı) | Rev.7 öncesi rapor: 10M / 2M (betik dışı) |
|---|---|---|---|---|---|---|
| 2020 | 80 | 0 | 61 | 77 | 80 | 61 / 77 |
| 2021 | 136 | 0 | 130 | 130 | 136 | 132 / 132 |
| 2022 | 158 | 1 | 154 | 157 | 159 | 155 / 158 |
| 2023 | 241 | 7 | 229 | 234 | 248 | 229 / 234 |
| 2024 | 369 | 10 | 341 | 343 | 379 | 341 / 343 |
| 2025 | 582 | 25 | 538 | 569 | 607 | 539 / 572 |
| 2026 | 584 | 70 | 317 | 534 | 654 | 317 / 534 |

Eşik sayıları C1 düzeltmesinden etkilenmedi; dolgu barları uygunluk sayımına zaten
girmiyordu. "Rev.7 öncesi rapor" sütunundaki eşik farkları (en çok 3 sembol) rev.7 öncesi
dönemlerden geliyor ve sembol düzeyinde ayrıştırılmadı.

Aynı düzeltme bar boşluğu olaylarının paydasına da uygulandı (§7,
`bosluk_olaylari_tam.csv`, `o_aralikta_veri_olan`). Payda artık aralıkla kesişen bir
dönemi olan sembolleri sayıyor. Boşluğu dönemleri ayıran sembol (BNXUSDT) hiçbir dönemle
kesişmese de etkilendiği için paydaya giriyor. `borsa_geneli` sınıflaması değişmedi.
Eksik bar sayımı (§7) ise ilk ve son bar arasındaki ham ızgaraya göredir. Uzlaşma
sonrası dolgu aralığını da kapsar; bu bir ham seri kapsama ölçüsüdür, uygunluk paydası
değildir.

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

1. **Ön-kayıt §2 rev.7'de düzeltilecek üç sayı** (Rev.8 için). Üçü de
   `rapor_sayilari_tam.csv`'nin `rev8` bölümünden gelir; tanımları şöyledir:

   | Ön-kayıt | Doğrusu | Kalem ve tanım |
   |---|---|---|
   | 14 | **18** | `settled_ayinda_dolgu_kosusu_yok`: 34 SETTLED ayından, o ay içinde hiç dolgu koşusu (6+ ardışık sıfır hacimli bar) bulunmayanların sayısı. |
   | 131 | **145** | `uzlasma_sonrasi_dolgusu_olan_sembol`: delist edilen 156 sembolden, dönem sonundan sonra en az bir dolgu barı olanların sayısı. |
   | 38 | **57** | `uzlasma_sonrasi_funding_yayinlanan_sembol`: son döneminin bitişinden sonra en az bir funding kaydı atılan sembol sayısı (38 SETTLING + 19 exchangeInfo dışı). |

   Üçünde de kural aynı işliyor, etkilenen yalnızca ön-kayıt metnindeki sayılar.
   Ön-kayıt kilitli; düzeltme revizyon ister.
2. **WAVESUSDT / KNCUSDT** (§8): dönem kuralıyla değil rev.3 boşluk kuralıyla
   açıklanıyor. Ön-kayıt §2'nin "ayrı revizyon" şartının bunlar için işletilip
   işletilmeyeceği sizin kararınız.
3. **exchangeInfo görüntüsü evrenden sonra alındı** (2026-09-18). Dahil sembollerin
   durumu `universe.csv` ile tutarlı (128 SETTLING, 28 dışarıda, tip uyuşmazlığı 0),
   ama `universe.csv` üretilirken kullanılan canlı yanıtın kendisi saklanmamıştı.
4. **`data/exchange_info_anlik.json` kilitli dosya listesinde değil.** B4 ile
   `evren_kur` sözleşme ve dayanak tipini canlı uç noktadan değil bu görüntüden okuyor;
   evrenin depodaki veriden yeniden üretilebilmesi artık bu dosyaya bağlı. Delist
   sınıflandırması ve deliveryDate testi de buradan okuyor. `exchange_info_anlik_kaydet`
   var olan dosyanın üzerine yazmıyor, ama dosya silinip yeniden alınırsa yeni bir
   görüntü sessizce yerine geçer. Testlerdeki 128/28 sayımı bunu yakalar;
   deliveryDate değişikliklerini yakalamaz.
   **Öneri:** Görüntü `universe.csv` ve `split.csv` ile aynı statüde (bir kez üretilen,
   sonuçları belirleyen girdi) olduğu için kilitli dosya listesine eklensin. Kilit
   değiştirilmedi; karar sizin.
   deliveryDate testi artık toplam dönemden sonra teslim edilen SETTLING sembolleri
   sessizce atlamıyor, `AtlananTeslimUyarisi` ile listeliyor. Bugün atlanan sembol: 0.
5. **Uzlaşma sonrası funding kaydı dönem içinde kalıyor (denetçi bulgusu D-A1, ölçüldü).**
   `data/funding.py` `_donem_icinde` üst sınırı son barın kapanışı; deliveryDate çoğunlukla
   o barın içinde. 128 SETTLING sembolün **19'unda 23 kayıt** deliveryDate'ten sonra gelip
   dönem içinde sayılıyor. Aralık dağılımı: 4 saat 14, 2 saat 4, 1 saat 3, 8 saat 2
   (FTTUSDT, RAYUSDT). Kod düzeltilmedi. Betik `a1_olcumu.py`; çıktılar başlıktaki A1
   listesinde.

   **Konum.** 23 kaydın hepsi deliveryDate'ten sonra:
   - 19'u son barın kapanışında, yani dönem sonu çıkış anında. Ufku dönem sonunu aşan
     bir pozisyonun çıkış ödemesi olurlar.
   - 4'ü son barın içinde, deliveryDate'ten sonra ama kapanıştan önce: ALPACAUSDT
     10:00 ve 11:00 (1 saat aralık), TROYUSDT 10:00 ve VIDTUSDT 10:00 (2 saat aralık).
     Üçünde de son bar 08:00–12:00, deliveryDate 09:00. Bunlar pozisyonun tutulduğu
     sürede ödenir.

   **İşaret** (1093e69 koşusu, `a1_uzlasma_sonrasi_oranlar_tam.csv`): 23 kaydın 18'i
   pozitif, 5'i negatif.

   **deliveryDate'i olmayan 28 sembol.** Hepsinde funding kaydı var. 27'sinin son barında
   (açılış ve kapanış dahil) toplam 28 kayıt var, ANCUSDT'de yok. 23 kayıt son barın
   açılışında, 5 kayıt kapanışında (AKROUSDT, LENDUSDT, LUNAUSDT, MBLUSDT, SRMUSDT).
   deliveryDate olmadığı için bu kayıtların uzlaşmadan önce mi sonra mı geldiği
   bilinemiyor.

   **Öneri sınırının etkisi** (üst sınır son barın kapanışı yerine açılışı olsaydı, tüm
   dahil sembollerin tüm dönemleri; `a1_oneri_etkisi_tam.csv`): 43 kayıt, 31 sembol.
   - Son dönemlerde 38 kayıt: 24 SETTLING (yukarıdaki 23 artı ALPACAUSDT'nin teslim
     anındaki 09:00 kaydı), 5 exchangeInfo dışı, 9 veri sonu dönemi (ONGUSDT, SKRUSDT,
     ZKCUSDT: 2026-08-31 21:00–23:00, 1 saat aralık, gerçek işlem sürerken).
   - Ara dönem sonlarında 5 kayıt: AERGOUSDT, BNXUSDT, MAVIAUSDT, PUMPUSDT, SLPUSDT,
     her birinde 1 kayıt.

   D-B8 düzeltmesinden sonra (funding iki uçtan toplam döneme kesildi) yukarıdaki
   sayıların hiçbiri değişmedi: 23 / 19, konumlar, 28 kayıt ve 43 kayıt dökümü aynı.

   **D kuralının kapsamı ve delist çıkışlarındaki tamlık sorunu §14.7'de.** Oradaki
   ölçüm, bu bölümün A1 sayılarıyla aynı koşudan gelir (`a1_d_kurali_tam.csv`).

   > **Denetim sınırı aşımı.** A1 ölçümünde (1093e69) uzlaşma sonrası funding kayıtlarının oran değerleri ve işaretleri raporlandı. Bu kayıtlar dönem sonunu aşan pozisyonların net getirisine girebilecek türdendi ve bir kısmı C1 grubuna ve C2 dönemine ait. Bu, §3.1'deki veri denetimi sınırını aştı. Ölçümü bu kapsamda isteyen araştırma tarafıydı; aşımın sorumluluğu oradadır.
   >
   > Değer düzeyindeki analiz bu bölümden çıkarıldı. Geriye kalan 18 pozitif / 5 negatif işaret sayımı da aşımın bir parçasıdır: 23 kaydın 5'i C1 grubundaki sembollere aittir (AMB, NULS, SNT, TROY×2); C2 dönemine ait kayıt içermez. İki sayının (5 C1 kaydı, 5 negatif kayıt) birbirleriyle ilişkisi, C1'in işaret dağılımını açığa çıkaracağı için bilerek raporlanmaz. Sayım, funding üst sınırı kuralının etkisinin yönünü belgelemek için bırakıldı; bu nötr bir gerekçe değildir, yön bilgisidir ve öyle okunmalıdır.
   >
   > İz CSV'leri çalışma ağacından kaldırıldı; commit 1093e69 içinde durmaya devam ediyor. Bu aşımın funding üst sınırı kuralıyla ilişkisi ön-kayıtta yazılı hâle getirilecek; ön-kayıt henüz revize edilmedi.

6. **1 dakikalık toleransın kenarı (denetçi bulgusu D-B7, yalnızca not).**
   - Ön-kayıt §4: "1 dakikadan **küçük** zaman kayması aynı an sayılır."
   - `a1_olcumu.py` (`konum`, `sembol_olc`) tam 1 dakikalık kaymayı "aynı an" sayıyor
     (`<= tolerans`).
   - `data/funding.py` `_donem_icinde` üst uçta tam 1 dakikayı dışarıda bırakıyor
     (`< bitis + adım + 1 dk`).

   Kenar tanımı tutarsız. Gözlenen kaymalar en fazla 31 ms olduğu için bugünkü sayılar
   etkilenmiyor. Kod değiştirilmedi; tanım ön-kayıt revizyonunda çözülecek.

7. **F2'nin önünde duran açık nokta: delist çıkışlarında funding tamlığı
   (denetçi bulgusu D-A4).**

   **Bulgu.** Bugünkü kodla, ufku dönem sonunu aşan bir pozisyon 128 SETTLING sembolün
   **78'inde** NaN oluyor ve düşüyor. H3'ün 1 günlük çıkışlarında durum daha ağır:
   168 dönem sonunun **167'sinde** tamlık bozuluyor.

   **Sebep.** `pozisyon_fundingi` son ödemeyi çıkış anında (son barın kapanışı) arar.
   Uzlaşmış bir sözleşmede o anda ödeme kaydı yoktur, çünkü sözleşme son barın içinde
   uzlaşmıştır. 128 SETTLING sembolün yalnızca **19'unda** kapanış anında kayıt var
   (`a1_d_kurali_tam.csv`, `kapanista_odeme`). Kalan 109'un **31'i** yine de geçiyor:
   son ödemelerinin aralığı 8 saat olduğu için zincir çıkış anına yetişiyor
   (`son_odeme_aralik_saat`). Geçemeyen 78'in 72'sinde son ödeme aralığı 4 saat,
   6'sında 1 saat. 1 günlük ızgarada çıkış anı ertesi günün 00:00'ı olduğu için
   8 saatlik ritim de yetişmiyor; 167 dönem sonu bozuluyor.

   **Neden önemli.** Düşen pozisyonlar delist edilen coinlerdedir. CLAUDE.md §2.4:
   delist coinler en iyi short adaylarıdır ve sessizce hesaptan düşmemelidir. Bu hâliyle
   kod, tam da ölçülmek istenen olayların bir kısmını hayatta kalma yanlılığı yaratacak
   şekilde eliyor.

   **Ölçüm** (`a1_d_kurali_tam.csv`; yalnızca sayı, değer ve işaret yok). "Bozuk" =
   temsili pozisyonun funding'i NaN olur. Temsili pozisyon, çıkış barının açılışından
   24 saat önce (ya da dönem başında) girer ve dönem sonunda çıkar.

   Çıkış ızgarası **4 saat** (H1, H2):

   | Dönem sonu türü | Dönem sonu | Dışarıda kalacak kayıt (dönem sonu) | Kapanışta ödeme | Tamlık bozuk: mevcut | Tamlık bozuk: D |
   |---|---|---|---|---|---|
   | Delist, SETTLING | 128 | 24 (19) | 19 | **78** | 1 |
   | Delist, exchangeInfo dışı | 28 | 5 (5) | 5 | 3 | 0 |
   | Dolgu koşusu (iç) | 11 | 4 (4) | 4 | 3 | 2 |
   | Uzun boşluk (iç) | 1 | 1 (1) | 1 | 1 | 1 |
   | **Kural uygulanan toplam** | **168** | **34 (29)** | **29** | **85** | **4** |
   | Veri sonu (kural uygulanmaz) | 522 | 9 (3) | 0 | 522 | 0 |

   Çıkış ızgarası **1 gün** (H3):

   | Dönem sonu türü | Dönem sonu | Dışarıda kalacak kayıt (dönem sonu) | Kapanışta ödeme | Tamlık bozuk: mevcut | Tamlık bozuk: D |
   |---|---|---|---|---|---|
   | Delist, SETTLING | 128 | 132 (38) | 38 | **128** | 1 |
   | Delist, exchangeInfo dışı | 28 | 46 (21) | 20 | 27 | 0 |
   | Dolgu koşusu (iç) | 11 | 24 (8) | 8 | 11 | 2 |
   | Uzun boşluk (iç) | 1 | 1 (1) | 1 | 1 | 1 |
   | **Kural uygulanan toplam** | **168** | **203 (68)** | **67** | **167** | **4** |
   | Veri sonu (kural uygulanmaz) | 522 | 9 (3) | 0 | 522 | 1 |

   **D kuralı bunu 78'den (H3'te 167'den) 4'e indiriyor.** Kural henüz koda geçmedi;
   ön-kayıt revizyonu bekliyor. Her iki ızgarada da bozuk kalan aynı dört dönem sonu:
   - FTTUSDT (delist, SETTLING): son ödeme aralığı 2 saat ve uzlaşma anında kayıt yok
     (`son_odeme_aralik_saat = 2`).
   - ICPUSDT ve TLMUSDT'nin ilk dönemleri: funding'siz dönemler (§4); üç hipotezde de
     zaten kullanılmıyor.
   - BNXUSDT'nin boşluktan önceki dönemi.

   **Veri sonu satırı.** Oradaki 522 bozukluk ölçümün kendi sonucudur: çıkış anındaki
   kayıt (2026-09-01 00:00) toplam dönemin dışında kalıyor ve kesiliyor. Gerçek akışta
   bu çıkışlar zaten küme sınırında reddedilir (`pencere.ufuk_kumeye_sigar_mi`,
   ön-kayıt §3 rev.4), yani sayının pratik bir karşılığı yok; kural da bu dönemlere
   uygulanmıyor (denetçi bulgusu D-C2).

   **Ölçümün sınırı (denetçi bulgusu D-B4).** `a1_olcumu.py` veri katmanının
   `pozisyon_fundingi` hesabını **taklit eder**, onu çağırmaz: oran ve aralık için NaN
   kontrolü yapmaz (oran sütununa bakmamak için), tabanı yalnızca dönem başıdır (küme
   başı değil) ve bozuk zaman dizisi kontrolü yoktur. Temsili pozisyonun giriş süresi
   (24 saat) betikte sabittir. Bu yüzden sayılar tek yönlü okunmalıdır: "bozuk" gerçek
   kodun da NaN üreteceği anlamına gelir, "tam" ise başka bir nedenle NaN olmayacağını
   garanti etmez. D kuralı koda geçtiğinde bu sayılar gerçek kod yoluyla yeniden
   üretilip buradakilerle karşılaştırılacaktır.

   **F2'ye geçiş.** Bu açık nokta kapanmadan F2'ye geçilmez.

9. **Tamlık sayımlarının denetim sınırı (denetçi bulgusu D-B4).** D kuralı ve 1 günlük
   tamlık sayımları B grubunu ve C2 dönemini de kapsar. Bu sayımlar yalnızca funding
   kaydının varlığını ve zaman damgasını kullanır; fiyat, getiri ya da funding değeri
   içermez. Bu yüzden CLAUDE.md §3.1'deki veri bütünlüğü denetimi kapsamındadır.

   Tam liste: funding tarafında kaydın zaman damgasının yanında aralık alanı
   (`aralik_saat`, bir sonraki ödemeye kalan süre) da okunur; bu kaydın zamanlama
   bilgisidir, oran değeri değildir. Dönem sonu türünün ayrımı ve 1 günlük sınır günleri
   (§14.8) mumların zaman damgasını ve hacmin sıfır olup olmadığını kullanır; fiyat
   sütunlarına ve hacim miktarına bakılmaz.

   Kodda: `tests/test_tamlik_sayimi_deger_icermez.py`. `d_kurali_olc` oran sütunu hiç
   yokken de çalışır ve oran değerleri ne olursa olsun aynı satırları üretir;
   `gunluk_sinir_tablosu` fiyatlar NaN ya da sıfır olmayan hacimler rastgele olduğunda
   da aynı tabloyu üretir; bu fonksiyonların kaynağında fiyat ya da oran sütununun adı
   geçmez. Kaynak taramasının sınırı `tests/test_a1_deger_yolu_yok.py` açıklamasında
   (D-C1).

## 15. Tarihsel not: rev.3 boşluk kuralının etkisi (betik dışı)

Önceki rapordaki "Revizyon 3 sonrası" tarama (birleşik eleme 19.763 bar-sembol,
%0,535) ay düzeyindeki eski dönemlerle yapılmıştı ve bu koşuda **yeniden
üretilmedi**. Rev.7 dönemleriyle sayılar farklı olabilir.

## Değişiklik kaydı

- 2026-09-19: §14.5'teki **değer düzeyindeki analiz** çıkarıldı; **işaret sayımı (18/5)
  bilerek bırakıldı** ve aşımın parçası olarak işaretlendi (denetçi bulguları D-B1…D-B5).
  Çıkarılan içerik:
  - uzlaşma sonrası 23 kaydın ve deliveryDate'i olmayan sembollerdeki 5 kaydın oran
    değerleri;
  - taban / uç / olağan gruplaması ve "referans medyanın N katı" karşılaştırmaları;
  - sıfır / sabit / tekrar tespitleri;
  - ALPACAUSDT teslim anı değeri;
  - SRMUSDT/FTTUSDT cümlesi. Bu cümledeki tarih hatası da düzeltilmiş oldu: kayıtlar
    aynı gün değildi (FTTUSDT 2022-11-14, SRMUSDT 2022-11-15).

  İşaret sayımı (18/5) bilerek bırakıldı; içindeki 5 kayıt C1 grubundadır ve §14.5'teki
  not bunu açıkça yazar.
- 2026-09-19: §4'teki betik dışı sayılar betik çıktısından yeniden türetildi (D-A5).
  - "57 sembolün 54'ünde en geç 8 saat" yerine 57/57.
  - "İki dönem arasındaki dolguya düşen 8.881 / 12" ayrıldı: dolgu 8.817 / 11,
    BNXUSDT eksik bar boşluğu 64 / 1.
  - Oran değerine dayanan "sembol başına 1–2 farklı oran değeri" cümlesi çıkarıldı.
- 2026-09-21: Sınır aşımı notu yeniden yazıldı (D-A1, D-A2): Rev.8'e yapılan yanlış atıf
  kaldırıldı, işaret sayımının da aşımın parçası olduğu ve içindeki 5 kaydın C1 grubuna
  ait olduğu yazıldı. Oran değeri üreten kod yolu ve onu açan bayrak kaldırıldı, iz
  CSV'leri çalışma ağacından silindi (D-B1). A1 koşusunun dosya tarihinden türetilen
  zamanı kaldırıldı; referans koşu artık ortam kaydı olan temiz koşudur (D-B2). §14.7
  açıldı: delist çıkışlarında funding tamlığı, H3 ölçümüyle birlikte (D-A4, D-B3).
  Betik dışı kalan üç sayı işaretlendi (D-C1).
- 2026-09-21: §14.5 notunun ikinci paragrafı kullanıcının metniyle değiştirildi (D-A2,
  D-B4): korunan 18/5 sayımının 23 kaydının 5'i C1'dedir ve C2 dönemine ait kayıt
  içermez; "5 C1 kaydı" ile "5 negatif kayıt" arasındaki ilişki bilerek raporlanmaz;
  sayımı tutmanın gerekçesi nötr değil, yön bilgisidir. Birinci paragraftaki "bir kısmı
  C1 grubuna ve C2 dönemine ait" ifadesi bütün aşım için doğru olduğundan kaldı.
