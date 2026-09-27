# F1 Veri Denetimi — TAM EVREN (678 sembol), ön-kayıt rev.7

**Durum:** Tam koşu, 678/678 sembol, **hata yok**.
**Koşu:** 2026-09-21 08:21:24 → 08:40:21 UTC, 8 iş parçacığı, önbellekten,
`--eski-evren` (rev.7 öncesi tabloyla karşılaştırma, §5) açık.
**Kod:** `2ce0bac`, çalışma ağacı **temiz** (`ortam_tam.csv`; durum koşunun başında,
hiçbir çıktı yazılmadan alındı). Bu commit'te tam test takımı geçiyor: 767 geçti, 2 xfail
(betik dışı sayı: `pytest -q` çıktısından). Bu koşunun çıktılarını commit eden
commit'ten sonrakiler yalnızca bu raporun metnini değiştirir.
**A1 ölçümü:** aynı commit, aynı temiz ağaç, 2026-09-21 08:21:31 → 08:28:37 UTC
(`a1_ortam_tam.csv`). A1'in referans koşusu budur. Koşu kilidi (`calistir.kosu_kilidi`)
iki betiğin kendi ikinci koşusunu reddeder; bu koşu sırasında ikinci bir denetim koşusu
denendi ve hiçbir şey yazmadan reddedildi (betik dışı: elle deneme).
**Önceki temiz koşudan (`d3a6fc4` kodu, çıktıları `4eefa5b`) farklar**
(`karsilastirma_tam.csv`, `karsilastir.py --onceki 4eefa5b`):
- `a1_d_kurali`: `funding_var_mevcut`, `funding_var_d` sütunları eklendi (§14.10); ortak
  sütunlarda satır farkı yok.
- `ortam`, `a1_ortam`: koşu kaydı (commit, zaman).
- Diğer 23 `*_tam.csv` dosyası aynı (satır sonları LF'ye çevrildikten sonra metin
  eşitliği).
- `karsilastirma_02effeb_tam.csv`: aynı çıktıların `02effeb` ile karşılaştırması
  (§14.7'deki D-B3 cümlesinin kaynağı).
- Bir önceki turun `2eaa5fc` ara koşusu ve bu turun `d506b6a` A1 ara koşusu metin için
  kullanıldı; son koşunun ilgili sayıları onlarla aynı (§14.10 tablosu A1 çıktısıyla
  birebir; betik dışı: elle karşılaştırma).
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
(gerekçesi §14.5'teki notta). 18/5 betik dışıdır: `1093e69` içindeki iz dosyasından
gelir, bu koşunun hiçbir çıktısından türetilemez.

Ham çıktılar (`*_tam.csv`), `calistir.py`: `sembol_ozeti`, `delist_siniflandirmasi`,
`dolgu_kosulari`, `kisa_sifir_kosulari`, `funding_siz_donemler`, `donem_sonu_degisimleri`,
`settled_aylari`, `yillik_kapsama`, `butunluk_sicramalari`, `bosluklar`, `bosluk_olaylari`,
`funding_araliklari`, `cross_dogrulama`, `cross_yogun_tarihler`,
`fiyat_farki_listeleme_yasi`, `kisa_donemler`, `settled_icerik`, `donem_aralari`,
`gunluk_sinirlar` (§14.8), `ortam`. `karsilastir.py`: `karsilastirma` (önceki koşuyla
fark), `karsilastirma_02effeb` (`02effeb` çıktılarıyla fark).
`rapor_sayilari_tam.csv` bu rapordaki sayıların kaynağıdır (bölüm, kalem, değer).
Ölçüm sayılarının tamamı bu dosyadan ya da ham `*_tam.csv` çıktılarından gelir
(denetçi bulgusu D-A5). Betikten türetilmeyen her sayı bulunduğu yerde **"betik dışı"**
diye işaretlidir (denetçi bulgusu D-B1). "Önceki koşuyla aynı / değişmedi" cümleleri
`karsilastir.py` çıktısına (`karsilastirma_tam.csv`) bağlıdır; bağlanamayanlar betik
dışı diye işaretlidir.
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

Bölme (`data/split.csv`) değişmedi (betik dışı: dosya kilitli; `git log` ile doğrulanır): 678 sembol → 669 varlık anahtarı (A 333, B 345
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

**Serinin ortasındaki kısa (1–5 bar) sıfır hacim koşusu: 0.** F1 ölçümü S2 ile aynı
(betik dışı: S2 eski bir ölçümdür).
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
Bu 13, ön-kayıttaki "34 karantina ayının 14'ünde dolgu koşusu bulunmayan" cümlesinin
tanımı **değildir**: cümle yalnızca dolgu yokluğunu anar ve harfiyen tanımla sayı
**18**'dir (13 + dolgusuz ama dönem sınırlı 5 ay). Rev.8'e girecek sayı 18'dir (§14.1).

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

3 bardan uzun 105 boşluk, zaman örtüşmesine göre **10 olay** (önceki koşuyla aynı:
`karsilastirma_tam.csv`, `bosluklar_tam.csv` ve `bosluk_olaylari_tam.csv` `ayni`).
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

Betik dışı: önceki rapordaki üç kayıt (DOSUSDT, TLMUSDT dönem 1, 牛来USDT) ay düzeyinde "31 gün"
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
kesişmese de etkilendiği için paydaya giriyor. `borsa_geneli` sınıflaması değişmedi
(betik dışı: D-C1 düzeltmesinden önceki koşuyla karşılaştırma).
Eksik bar sayımı (§7) ise ilk ve son bar arasındaki ham ızgaraya göredir. Uzlaşma
sonrası dolgu aralığını da kapsar; bu bir ham seri kapsama ölçüsüdür, uygunluk paydası
değildir.

## 11. Funding aralıkları

Önceki koşuyla aynı (`karsilastirma_tam.csv`, `funding_araliklari_tam.csv` `ayni`): 8 saat 992.586 kayıt / 284 sembol · 4 saat 1.487.688 / 516 · 1 saat
78.690 / 162 · 2 saat 3.492 / 19. 678/678 sembolde funding verisi var.

## 12. 1d türetmesinin birincil 1d dosyalarıyla karşılaştırması

Önceki koşuyla aynı (`karsilastirma_tam.csv`, `cross_dogrulama_tam.csv` ve
`cross_yogun_tarihler_tam.csv` `ayni`): 615.043 gün karşılaştırıldı; fiyat farkı 7 gün (%0,0011), hacim farkı 261
gün (%0,042). Fiyat farklı 7 günün 4'ü dönem başından sonraki ilk 30 gün içinde
(9,7–10,7. gün), 3'ü 2023-08-16'da (INJ, SFP, UNFI). 2023-08-16 hacim tarafında
192 sembolle baskın aykırı gün.

## 13. Ortam

Python 3.13.12 (Miniconda, `D:\Miniconda\python.exe`), Windows-10-10.0.19045-SP0,
pandas 2.3.3, numpy 2.4.4, pyarrow 21.0.0, requests 2.32.5.

---

## 14. Açık noktalar

1. **Ön-kayıtta düzeltilecek üç sayı** (Rev.8 için; denetçi bulguları D-A3, D-B2).
   Her sayı `rapor_sayilari_tam.csv`'nin `rev8` bölümünden, ön-kayıttaki cümlenin
   harfiyen tanımıyla üretilir. Cümleler aynen:

   - **14** — §2 "Karantina kuralının kaldırılması": "F1 ölçümü, SETTLED aylarının
     yeniden fiyatlandırma değil yeniden listeleme anlamına geldiğini; 34 karantina
     ayının 14'ünde ise dolgu koşusu bulunmayan, işlem gören verinin gereksiz yere
     dışarıda bırakıldığını; incelenen iki örnek ayda SETTLED dosyalarının ana seriyle
     birebir aynı olduğunu göstermiştir."
   - **131** — Revizyon Günlüğü, rev.7 gerekçesi: "F1 kapanış ölçümleri (D1, D2, D3, V1,
     V2, S1–S3): 131 sembolde uzlaşma sonrası dolgu barların dönem sonunu yıllarca
     uzattığı, SETTLED aylarının yeniden fiyatlandırma değil yeniden listeleme olduğu ve
     delist sayısının eksik saptandığı belirlendi."
   - **38** — §2 "Gerçek işlem sonrası funding kayıtları": "Dönem sonundan sonra gelen
     funding kayıtları yok sayılır. F1 ölçümü, 38 sembolde uzlaşma sonrasında da funding
     kaydı yayınlandığını ve bu kayıtların bir ya da birkaç sabit orandan oluştuğunu
     göstermiştir."

   | Ön-kayıt | Harfiyen tanımla | Kalem ve tanım |
   |---|---|---|
   | 14 (34'ten) | **18** (34'ten) | `settled_ayinda_dolgu_kosusu_yok`: 34 SETTLED ayından, o ay içinde hiç dolgu koşusu (6+ ardışık sıfır hacimli bar) bulunmayanlar. |
   | 131 | **145** | `uzlasma_sonrasi_dolgusu_olan_sembol`: delist edilen 156 sembolden, son dönem sonundan sonra en az bir dolgu barı olanlar. Cümledeki "yıllarca" harfiyen alınırsa: uzlaşma sonrası dolgusu en az 1 yıl olan **45**, en az 2 yıl olan **15** sembol (`…_en_az_1_yil_…`, `…_en_az_2_yil_…`). |
   | 38 | **57** | `uzlasma_sonrasi_funding_yayinlanan_sembol_kapanistan_sonra`: son döneminin **kapanışından** (son gerçek 4 saatlik barın kapanışı + 1 dk, yani dönem sonu çıkış anı) sonra en az bir funding kaydı olan sembol. 38 SETTLING + 19 exchangeInfo dışı. |

   **14: 13 mü 18 mi?** §6'daki 13, "ayda ne dolgu koşusu ne dönem sınırı var" sayımıdır.
   Alıntılanan cümle yalnızca "dolgu koşusu bulunmayan" der; dönem sınırını anmaz. Bu
   yüzden cümleye göre doğru sayı **18**'dir. Fark 5 ay: dolgu koşusu yok ama dönem
   sınırı var (BNXUSDT 2022-04, BNXUSDT 2023-02, ICPUSDT 2022-09, MINAUSDT 2023-02,
   TLMUSDT 2023-03; `settled_ayinda_dolgu_yok_donem_siniri_var_aylar`). §6'daki 13 başka
   bir ölçüdür ve Rev.8'e girmemelidir.

   **131: "yıllarca".** Çekirdek tanım (uzlaşma sonrası dolgusu olan) 145 verir; ama
   dolguların medyanı 264,5 gündür (§3), 145'in çoğu için "yıllarca" doğru değildir.
   Rev.8 metni ya sayıyı 145 yapıp "yıllarca"yı çıkarmalı ya da "yıllarca"yı tutup
   sayıyı eşikle (45 / 15) vermelidir. Hangisi sizin kararınız.

   **38: referans.** Önceki tanım "son döneminin bitişinden sonra" diyordu; betik ise
   kapanıştan sonrasını sayıyor (denetçi bulgusu D-B2). Tanım kapanış referansıyla
   düzeltildi. exchangeInfo dışı sembollerde uzlaşma anı (deliveryDate) yok; kapanış bütün
   delist sembollerde tanımlı tek referanstır. Karşılaştırma için: SETTLING sembollerde
   deliveryDate'ten sonra kaydı olan sembol de **38**'dir
   (`SETTLING_teslimden_sonra_funding_kaydi_olan_sembol`; son bar içindeki 19 sembolün
   hepsinin kapanıştan sonra da kaydı var). Ön-kayıttaki 38 yalnızca SETTLING
   sembolleri sayıyor.

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

   **İşaret** (betik dışı: 1093e69 koşusu, `a1_uzlasma_sonrasi_oranlar_tam.csv`; bu
   koşunun hiçbir çıktısından türetilemez): 23 kaydın 18'i pozitif, 5'i negatif.

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
   sayıların hiçbiri değişmedi (betik dışı: D-B8 öncesi koşuyla karşılaştırma): 23 / 19, konumlar, 28 kayıt ve 43 kayıt dökümü aynı.

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

   | Dönem sonu türü | Dönem sonu | Dışarıda kalacak kayıt (dönem sonu) | Kapanışta ödeme | Tamlık bozuk: mevcut | Tamlık bozuk: D | Tamlık bozuk: aday |
   |---|---|---|---|---|---|---|
   | Delist, SETTLING | 128 | 24 (19) | 19 | **78** | 1 | 1 |
   | Delist, exchangeInfo dışı | 28 | 5 (5) | 5 | 3 | 0 | 0 |
   | Dolgu koşusu (iç) | 11 | 4 (4) | 4 | 3 | 2 | 2 |
   | Uzun boşluk (iç) | 1 | 1 (1) | 1 | 1 | 1 | 1 |
   | **Kural uygulanan toplam** | **168** | **34 (29)** | **29** | **85** | **4** | **4** |
   | Veri sonu (kural uygulanmaz) | 522 | 9 (3) | 0 | 522 | 0 | 0 |

   Çıkış ızgarası **1 gün** (H3). Bu tablo 4 saatlik tabloyla **aynı kayıt tabanından**
   sayılır: veri katmanının gördüğü seri (`donem_sonrasi_kayitlari_at`, üst sınır son
   4 saatlik barın kapanışı + 1 dk). Önceki sürüm "dışarıda kalacak kayıt" ve "kapanışta
   ödeme" sütunlarını ham kayıtlardan, yani mevcut kuralın zaten attığı kayıtları da
   sayarak hesaplıyordu (denetçi bulgusu D-A4; eski değerler 203 (68) ve 67 idi). Tamlık
   sütunları zaten bu tabandan sayılıyordu ve değişmedi: `karsilastirma_02effeb_tam.csv`
   (`karsilastir.py --onceki 02effeb --ad karsilastirma_02effeb`) `a1_d_kurali_tam.csv` için `degisen_sutunlar` =
   `disarida_kalan:65;kapanista_odeme:65` (denetçi bulgusu D-B3). Bu 65 satırın hepsinin
   1 günlük satır olduğu betik dışıdır (iki dosyanın sembol, ızgara ve dönem sırasına göre
   elle birleştirilmesinden).
   "Aday" sütunu §14.8'deki aday kuraldır.

   | Dönem sonu türü | Dönem sonu | Dışarıda kalacak kayıt (dönem sonu) | Kapanışta ödeme | Tamlık bozuk: mevcut | Tamlık bozuk: D | Tamlık bozuk: aday |
   |---|---|---|---|---|---|---|
   | Delist, SETTLING | 128 | 24 (19) | 0 | **128** | 1 | 1 |
   | Delist, exchangeInfo dışı | 28 | 5 (5) | 1 | 27 | 0 | 0 |
   | Dolgu koşusu (iç) | 11 | 4 (4) | 0 | 11 | 2 | 2 |
   | Uzun boşluk (iç) | 1 | 1 (1) | 1 | 1 | 1 | 1 |
   | **Kural uygulanan toplam** | **168** | **34 (29)** | **2** | **167** | **4** | **4** |
   | Veri sonu (kural uygulanmaz) | 522 | 9 (3) | 0 | 522 | 1 | 0 |

   Aynı tabanla 1 günlük "dışarıda kalacak kayıt" 4 saatlikle birebir aynıdır: 1 günlük
   çıkış anına kadarki fazladan kayıtları veri katmanı zaten atıyor. "Kapanışta ödeme"
   yalnızca dönem bitişi 20:00 olan iki dönem sonunda var (1 günlük kapanış son 4 saatlik
   barın kapanışıyla aynı an). Veri sonu satırında D ile aday arasındaki tek fark
   牛来USDT'dir: dönemi 2026-08-30 08:00'de başlıyor ve D sütununun temsili girişi (dönem
   başı) ile aday sütununun girişi (2026-08-31 00:00) farklı; bu temsili girişin bir
   sonucudur, kural farkı değildir.

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

   **Çıkış kuralının betikteki kopyası (denetçi bulgusu D-B3).** `a1_olcumu.py` dönem
   sonu çıkışını ve funding penceresini kendi içinde yeniden kurar
   (`donem_sonu_cikisi`, `d_kurali_olc`); bu kopya `tests/tarama_yardimcisi.py`'deki
   tek kapı taramalarının dışındadır ve hiçbir otomatik kontrol onu
   `pencere.pozisyon_plani` / `funding.pozisyon_fundingi`'ye bağlamaz. Şimdilik kalıyor.
   D kuralı veri katmanına geçtiğinde A1 betiği gerçek kodu çağıracak, kopya silinecek
   ve betiğin sayılarının gerçek kod yoluyla aynı olduğunu doğrulayan bir test
   eklenecek.

   **F2'ye geçiş.** Bu açık nokta kapanmadan F2'ye geçilmez.

8. **1 günlük barlar ve dönem sınırları (denetçi bulgusu D-A1, ölçüldü, kod
   değişmedi).**

   **Ön-kayıttaki cümleler (aynen).**
   - §2 "1 günlük barlar": "1d barlar 4h barlardan türetilir: UTC günü; open ilk, high en
     yüksek, low en düşük, close son değer; volume ve quote_volume toplam. 6 adet 4h barı
     tam olmayan gün eksik (NaN) sayılır. Uygunluktaki günlük hacim bu seriden hesaplanır."
   - §2 "Listeleme dönemi" (rev.7): "Dönem, sıfır olmayan hacimli ilk barda başlar ve
     sıfır olmayan hacimli son barda biter. Sınır bar düzeyindedir, ay düzeyinde değil."
     · "6 veya daha fazla ardışık sıfır hacimli bar (bir gün) dönemi böler. Bu barlar
     delist edilmiş ya da henüz yeniden listelenmemiş bir sözleşmenin dolgu verisidir ve
     hiçbir hesaba girmez." · "7 günden uzun eksik bar boşluğu dönemi böler. …" ·
     "Tüm geriye bakış pencereleri dönem başlangıcını aşamaz; aşıyorsa değer hesaplanmaz
     ve o barda olay oluşmaz." · "Ufuk dönem sonunu aşarsa çıkış fiyatı dönemin son
     barının kapanışıdır."
   - §2 "Veri boşlukları": "Hedef çıkış barı eksikse çıkış, sonraki ilk mevcut barın
     **açılış** fiyatındandır. Dönem sonu ve delist kuralları önceliklidir." · "1 günlük
     seride bir gün yalnızca 6 adet 4 saatlik barın tamamı varsa oluşur; eksik gün zaten
     NaN'dir ve pencerelerde eksik sayılır."
   - §4: "Ufuk içinde sözleşme delist olursa çıkış, son mevcut barın kapanışıdır." ·
     "**Dönem sonu ve çıkış.** Ufuk dönem sonunu aşarsa çıkış, dönemin son barının
     kapanışıdır. Dönem sonu ve delist kuralları ileri kayma kuralından önceliklidir."
   - Revizyon Günlüğü, rev.7: "… dönem sınırları bar düzeyine indi …"

   **Bugünkü kod.** `klines.gunluge_cevir` 1 günlük seriyi sembolün **bütün** 4 saatlik
   serisinden kurar (`ham_mumlari_yukle(…, "1d")`, kümeye kesilmeden önce); dönem sınırını
   bilmez. Bir gün, 6 barın tamamı **mevcutsa** seriye girer; barların dönem içinde olup
   olmadığına bakılmaz.
   - *Dönem sonu.* `pencere.cikis_bari` dönem sonunda "sınırdan (dönem bitişi) önceki son
     barın kapanışı"nı seçer; 1 günlük seride bu, açılışı dönem bitişine eşit ya da ondan
     önce olan son gündür. Bitiş günü tamsa (sonrasında dolgu barları varsa) çıkış o
     günün barıdır: kapanışı günün son 4 saatlik barından, en yüksek değeri günün bütün
     barlarından gelir. Bitiş 08:00 ise 12:00, 16:00, 20:00 dönem dışı barlardır. Bitiş
     günü eksikse (seri gün ortasında bitiyorsa) çıkış bir önceki günün kapanışıdır, yani
     dönemin son barının kapanışından en az 4 saat önce (bu ölçümde 4–12 saat).
   - *Dönem başı ve iç sınır başı.* Başlangıç gününde dönem öncesi bar varsa gün 1 günlük
     seride durur, ama hiçbir hesaba girmez: pencere kapısı açılışı dönem başından önce
     olan günü reddeder (`pencere_dilimi`), sinyal dönem başından önce olamaz, listeleme
     yaşı 30 gündür. Bu ölçümde böyle bir gün **hiç yok** (aşağıda).
   - *Evet, dönem dışı bar giriyor:* dönem sonunda, 1 günlük çıkış barına.

   **Sayılar** (`gunluk_sinirlar_tam.csv`, `rapor_sayilari` §14.8; yalnızca zaman
   damgası, değer yok). "Son 1d bar" = bugünkü kodun dönem sonunda çıkışı okuduğu gün.

   | Dönem sonu türü | Dönem sonu | Son 1d barı dönem dışı bar içeren | Bu barların toplamı | Bitiş günü 1d serisinde yok (çıkış bir önceki gün) |
   |---|---|---|---|---|
   | Delist, SETTLING | 128 | **128** | 387 | 0 |
   | Delist, exchangeInfo dışı | 28 | **17** | 55 | 9 |
   | Dolgu koşusu (iç) | 11 | **11** | 32 | 0 |
   | Uzun boşluk (iç, BNXUSDT) | 1 | 0 | 0 | 0 |
   | Veri sonu | 522 | 0 | 0 | 0 |

   - İlk 1d barı dönem dışı 4 saatlik bar içeren dönem başı: **0** (678 ilk dönem başı
     ve 12 iç sınır başı). 12 iç sınır başının 11'inde başlangıç günü 1d serisinde
     yok (o günün dönem öncesi barlarından en az biri seride eksik); ICPUSDT'de dönem
     00:00'da başlıyor ve gün tamamen dönem içinde.
   - Altıdan az dönem içi 4 saatlik bar içeren ve bugünkü 1 günlük seride **bulunan**
     gün: dönem başı **0**, dönem sonu **145** (128 SETTLING + 17 exchangeInfo dışı), iç
     sınır **11** (11 iç dolgu koşusunun başladığı gün; iç sınır başlarında 0). Aynı günde
     başlayıp biten dönem yok, çift sayım yok.
   - exchangeInfo dışı 28'in dökümü: 17'sinde son 1d barı dönem dışı bar içeriyor (16'sı
     dolgu barı; LUNAUSDT'nin 2 barı dolgu eşiğinin altındaki sondaki sıfır barlar, §2);
     9'unda bitiş günü eksik (seri gün ortasında bitiyor: BZRX, KEEP, NU 00:00; AKRO, ANC
     04:00; 1000BTTC, DODO, EOS, YFII 08:00); 2'sinde (AERGO, LEND) bitiş 20:00, gün
     tamamen dönem içi. LENDUSDT'nin dolgusu ertesi gün başlıyor.

   **Aday kural (koda geçmedi, yalnızca sayım).** 1d barı yalnızca dönem içi 4 saatlik
   barlardan kurulur; altı barın tamamı dönem içinde değilse o gün 1d serisine girmez.
   Dönem sonuna ulaşan pozisyon her ızgarada son dönem içi 4 saatlik barın kapanışından
   çıkar; funding penceresi D kuralıyla, 4 saatlik zaman damgalarına göre uygulanır.
   - 1d serisinden çıkacak gün: **156** (145 dönem sonu + 11 iç sınır); dönem başında 0.
   - Çıkış anı değişecek dönem sonu: 168'in **165**'i (yukarıdaki 156 ve bitiş günü eksik
     9). Değişmeyen 3'ü bitişi 20:00 olan AERGOUSDT, LENDUSDT ve BNXUSDT'nin ilk dönemi.
   - 1 günlük tamlık (§14.7'deki tablo, aynı kayıt tabanı): mevcut kod **167** / D **4** /
     aday **4** bozuk dönem sonu (kural uygulanan 168'den). 4 saatlikte 85 / 4 / 4. Aday
     ile D arasında kural uygulanan dönem sonlarında fark yok; bozuk kalan dört dönem sonu
     §14.7'dekilerle aynı.

   **Ölçümün sınırı.** §14.7'deki 1 günlük "mevcut" sütunu çıkışın bitiş gününün barından
   (ertesi gün 00:00) olduğunu varsayar. Bitiş günü eksik 9 exchangeInfo dışı dönem
   sonunda gerçek kod bir önceki günün kapanışından (bitiş günü 00:00) çıkar; bu 9'un
   "mevcut" tamlığı o ana göre ölçülmedi (D-B3'teki kopya sorununun bir örneği).

   **Değerlendirme.** Rev.7'nin 1d türetme cümlesi kısmi gün konusunda sessiz: "6 adet 4h
   barı tam olmayan gün" bar sayısını anar, barların dönem içinde olmasını değil; bugünkü
   kod bu cümleyi harfiyen uygular. Ama sonuç rev.7'nin iki başka cümlesini deliyor:
   (1) dolgu barları "hiçbir hesaba girmez" — 128 SETTLING ve 11 iç dolgu dönem sonunda
   1d çıkış barının kapanışı ve en yüksek değeri dolgu barlarını içeriyor (exchangeInfo
   dışında 16 dönem sonunda dolgu, 1'inde eşik altı sıfır barlar); (2) "çıkış, dönemin son barının
   kapanışıdır" ve "sınır bar düzeyindedir" — 1d çıkışı 156 dönem sonunda dönemin son
   barından sonraki, 9 dönem sonunda ondan önceki bir anda. Yani türetme cümlesi sessiz,
   dönem ve çıkış cümleleri açık; bugünkü davranış dönem sonunda rev.7'yi deliyor. Dönem
   başında delme yok (0 gün; pencere kapısı zaten koruyor). Karar ve revizyon sizin;
   aday kural koda geçmedi.

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

10. **Funding'li / funding'siz dönem sınıflaması ve D penceresi (denetçi bulgusu D-A2,
    sayıldı, kod değişmedi).** Bugün bir dönem, `[dönem başı − 1 dk, son barın kapanışı
    + 1 dk)` içinde en az bir funding kaydı varsa funding'li sayılır
    (`funding.donemde_funding_var`). Üst uç D kuralındaki gibi dönem bitişi + 1 dk
    olsaydı (`a1_d_kurali_tam.csv`, `funding_var_mevcut` / `funding_var_d`; yalnızca kaydın
    varlığı ve zamanı):

    | Dönem sonu türü | Dönem | Funding'siz: bugün | Funding'siz: D penceresi | Funding'li → funding'siz | Funding'siz → funding'li |
    |---|---|---|---|---|---|
    | Delist, SETTLING | 128 | 0 | 0 | 0 | 0 |
    | Delist, exchangeInfo dışı | 28 | 0 | 0 | 0 | 0 |
    | Dolgu koşusu (iç) | 11 | 2 | 2 | 0 | 0 |
    | Uzun boşluk (iç) | 1 | 0 | 1 | **1** | 0 |
    | Veri sonu | 522 | 0 | 0 | 0 | 0 |

    Sınıfı değişen tek dönem BNXUSDT dönem 0: tek kaydı son barın kapanışında
    (2023-02-01 00:00). Bugünkü iki funding'siz dönem (ICPUSDT ve TLMUSDT'nin ilk dönemleri,
    §4) iki pencerede de funding'siz. Sayı iki ızgarada aynı (sınıf ızgaradan bağımsız).
    Dönem içinde funding'in dönem başından çok sonra başladığı başka dönem olup olmadığı
    ölçülmedi.

11. **`gunluge_cevir` hizalaması (denetçi bulgusu D-C5, ölçüldü, kod değişmedi).**
    `gunluge_cevir` bir günü satır sayısıyla (6) tam sayar, 4 saatlik ızgaraya hizaya
    bakmaz. `hiza_olcumu.py` (`hiza_tam.csv`, `hiza_ortam_tam.csv`: `a511cf1`, temiz ağaç,
    2026-09-21 20:11:18 → 20:18:18 UTC; yalnızca zaman damgası):
    - 678 sembol, 3.692.573 4 saatlik satır: ızgara dışında (00/04/08/12/16/20 UTC dışı)
      açılış **0**.
    - Altı satırlı 615.043 gün: açılışları altı ızgara anı olmayan gün **0** (0 sembol).

    Bugünkü veride hiza sorunu yok; kodda kontrol olmadığı bulgusu geçerli. Düzeltme
    Rev.8 uygulanırken yapılacak.

12. **Rev.8 uygulaması: açık noktaların durumu (2026-09-22).** Sayılar temiz ağaçtaki
    koşulardan: A1 `73ae679` (`a1_d_kurali_tam.csv`), tam denetim ve etki sayımları
    `09857aa` (`rev8_etki_*_tam.csv`); önceki koşuyla farklar
    `karsilastirma_ae8601f_tam.csv`. Yalnızca sayı; değer, işaret ya da getiri yok.
    Yukarıdaki 5–11. maddelerin metni tarihsel kayıttır; güncel durum burasıdır.

    - **§14.7, delist çıkışlarında funding tamlığı (D-A4): kapandı.** Temsili pozisyon
      artık gerçek `pozisyon_plani` ve gerçek `funding_tamlik_ayrintisi` ile ölçülür.
      Kural uygulanan 168 dönem sonunda bozuk: **4 saatlikte 4** (rev.7 kodunda 85; 128
      SETTLING'de 78 → 1), **1 günlükte 13** (rev.7 kodunda 167). 4 saatlikteki dört:
      FTTUSDT (son ödeme aralığı 2 saat, B'den önce bitiyor; `son_tam` bozuk), ICPUSDT ve
      TLMUSDT'nin ilk dönemleri ve BNXUSDT dönem 0 (penceresinde kayıt yok). 1 günlükteki
      fazladan 9 (AKRO, ANC, BTCST, BTT, BZRX, KEEP, NU, SRM exchangeInfo dışı; RAY
      SETTLING): temsili 1d girişi B'yi içeren günün 00:00'ı, B'ye 0–4 saat uzak ve
      8 saatlik ritimde (giriş, B] aralığına ödeme düşmüyor; "penceresinde hiç funding
      kaydı bulunmayan pozisyonun funding'i tam değildir". Bu, temsili girişin seçiminin
      ve rev.8'in harfiyen sonucudur: giriş bir gün önce olsa dokuzu da tam (betik dışı
      kontrol). Veri sonu 522 dönem sonu artık küme ölçütüyle reddediliyor (`kume_siniri`
      522; 1d'de 521 + 1 `donem_disi_sinyal`).
    - **§14.5, uzlaşma sonrası funding kaydı (D-A1): kapandı** (rev.8 §4 "Dönem sonu
      istisnası"). Dönem sonunda pencere B'de kapanır; B ile K arasındaki kayıtlar
      pozisyona girmez: kural uygulanan dönem sonlarında 34 kayıt, 29 dönem sonu;
      K'da ödeme 29. `donem_sonrasi_kayitlari_at` K'dan sonrasını atar.
    - **§14.8, 1 günlük barlar ve dönem sınırları (D-A1): kapandı.** 1d serisi dönem dönem,
      yalnızca dönem içi ve hizalı altı 4h bardan kurulur (tek yol `gunluge_cevir`).
      Seriden çıkan gün: dönem sonu **145**, iç sınır **11**, dönem başı 0 (önceki ölçüm
      156 = 145 + 11) ve 52.187 dönem dışı gün (uzlaşma sonrası dolgu günleri; rev.7'de de
      hiçbir hesaba girmiyordu); eklenen gün 0. 1d gün sayısı 615.043 → 562.700. 1d çıkış
      anı değişen dönem sonu **165 / 168** (önceki ölçümle aynı); rev.8 öncesi kuralda 1d
      günü bulunmayan dönem sonu 0. 4 saatlikte çıkış anı değişen 0.
    - **D-A2, funding sınıfı: kapandı, bir karar açık.** Rev.8 penceresi [dönem başı, B]:
      funding'siz dönem 2 → 3; sınıfı değişen yalnızca **BNXUSDT dönem 0** (tek kaydı
      K'da). Kilitli `data/universe.csv`'deki `donem_funding_yok` sütunu rev.7 penceresiyle
      üretildi ve BNXUSDT dönem 0 için eski değeri taşır; çalışan kod sınıfı kuraldan
      (`donemde_funding_var`) hesaplar. Tablonun yeniden üretilip üretilmeyeceği sizin
      kararınız (kilit). Funding'in dönem içinde geç başladığı dönemlerde ilk kayıttan
      önceki olaylar tek karar noktasında oluşmaz (`test_tek_karar_noktasi`).
    - **D-B3, A1'deki kural kopyası: kapandı.** Kopya silindi; `tests/test_a1_gercek_kod.py`.
    - **D-B4, sayımların tek yönlü okunması: kapandı.** Tamlık gerçek kod yolundan gelir;
      "bozuk" ve "tam" iki yönde de gerçek kodun kararıdır.
    - **§14.6 ve D-B7, zaman toleransı: kapandı.** Tek yardımcı (`pencere.ayni_an` ve
      türevleri), tam 1 dakika aynı an değildir. Funding kayıtlarının tam saatten en büyük
      sapması **47 ms** (2.562.456 kayıt; önceki not 31 ms'yi A1 alt kümesinden veriyordu),
      4h barlarda 0 ms. Sapması 29 saniyeyi aşan kayıt 0: iki kayıt arasındaki fark 58
      saniyeye ulaşamaz, eski uygulamalarla yenisinin ayrıldığı bölgeye hiçbir
      karşılaştırma düşmez; toleransın değiştirdiği kayıt **0**.
    - **Başlangıç boşluğu kuralının etkisi** (rev.8 §4 "Funding aralığı geçişleri";
      `rev8_etki_baslangic_tam.csv`). Bütün dönem içi barlar (1d'de günler) varsayımsal
      sinyal, birincil ufuk, gerçek plan ve tamlık; sinyal pencereleri ve uygunluk
      uygulanmaz (olası olayların üst kümesi). "Yalnız başlangıç" = diğer koşullar tam,
      yalnızca başlangıç koşulu bozuk (rev.7'de tam sayılırdı):

      | Hipotez (ızgara, ufuk) | Küme | Plan | Funding tam | Bozuk | Kayıt yok | Yalnız başlangıç |
      |---|---|---|---|---|---|---|
      | H1, H2 (4h, 18) | KEŞİF | 1.109.371 | 1.103.145 | 6.226 | 6.187 | 13 |
      | H1, H2 (4h, 18) | C1 | 1.107.539 | 1.107.436 | 103 | 74 | 25 |
      | H1, H2 (4h, 18) | C2 | 1.142.794 | 1.135.459 | 7.335 | 92 | 398 |
      | H3 (1d, 14) | KEŞİF | 181.948 | 180.907 | 1.041 | 1.024 | 3 |
      | H3 (1d, 14) | C1 | 181.570 | 181.558 | 12 | 4 | 8 |
      | H3 (1d, 14) | C2 | 184.186 | 178.623 | 5.563 | 0 | 398 |

      H1 ve H2 aynı ızgara ve ufku kullandığı için sayıları aynıdır. KEŞİF'teki "kayıt yok"
      sayısının çoğu ICPUSDT, TLMUSDT ve BNXUSDT'nin funding'siz dönemleridir.
    - **Yeni bulgu: 2026-06-24 04:00 funding kaydı piyasa genelinde eksik (C2 dönemi,
      yalnızca zaman damgası).** O an 4 saatlik ya da daha kısa ritimde aktif 415 sembolün
      **398'inde** önbellekte bu kayıt yok. C2'deki bozuk pozisyonların neredeyse tamamı
      bu tek boşluktan (sembol başına 4h'de ~18: ardışık kural ve son ödeme koşulu) ve
      C2'deki 398 "yalnız başlangıç" da aynı olaydır (06-24 00:00 girişinde ilk ödeme
      08:00, aralık 4). Boşluğun borsa verisinde mi yoksa indirmede mi olduğu ağa
      çıkmadan ayırt edilemedi. Kod davranışı rev.8'e uygundur; karar ve olası yeniden
      indirme sizin.
    - **Rev.8 uygulamasında bulunan iki hata (düzeltildi, testli).** (1) `funding_tamlik_ayrintisi`
      giriş son kayıttan sonraysa çöküyordu. (2) `yillik_kapsama` 1d uygunluğunu gün
      ortası anlarda sorduğu için tam denetim koşusu duruyordu; düzeltmeden sonra 2026'da
      2M eşiğini geçen sembol 534 → 533 (1d uygunluğu artık yalnızca gün açılışında).
    - **F1 kapanış ölçütü:** eklenmedi. İstekteki madde "[ONAYLADIYSAN KALSIN, YOKSA BU
      MADDEYİ SİL]" köşeli ayracıyla geldi; onay verilip verilmediği bu oturumda
      belirlenemedi.

13. **F1 kapanış ölçütü (araştırma tarafının kararı; 2026-09-27'de yeniden yazıldı).** §14.12'deki
    "eklenmedi" notunun yerine geçer. Tek ölçüt:

    "Bir bulgu getiriye dokunabiliyorsa F2 başlamadan kapanır; dokunmuyorsa §14'te açık nokta olarak kalır ve F2'yi engellemez. Ön-kayıt ile kodun ayrıştığı her yer getiriye dokunur sayılır, çünkü ayrışmanın sonucu tanımı gereği bilinmiyor. 'Ağır' ölçütü kaldırılmıştır. Karar: araştırma tarafı, 2026-09-27."

    2026-09-22 tarihli önceki metin ("ağır bulgular" ile "getiriyi etkileyebilecek bulgular" ayrımı)
    değişiklik kaydının 2026-09-27 (kapı sertleştirme turu) girdisinde aynen alıntılıdır. Sınıflama
    §14.21'de.

14. **Bilinen veri boşluğu: 2026-06-24 04:00 funding kaydı (C2 dönemi).** Yalnızca zaman
    damgası; değer yok.

    - **Kaynak borsa.** 8 sembol seçildi (`config.TOHUM` = 20260911 ile, kaydı eksik 5 ve
      kaydı olan 3 sembol). Bu sembollerde 2026-06-23 00:00 – 2026-06-25 00:00 aralığı iki
      kaynaktan geçici bir klasöre yeniden indirildi: `fapi/v1/fundingRate` REST ucu ve
      data.binance.vision 2026-06 aylık dosyası. İki kaynağın zaman damgaları önbellekle
      birebir aynı: kaydı eksik sembollerde iki kaynakta da 04:00 yok, olanlarda var.
      Boşluk indirmede değil, borsa verisinde. Önbelleğe yazılmadı. Seçilen semboller:
      IDOL, ACX, BEAT, POLYX, SAFE (eksik); ORDER, ON, UAI (var).
    - **Etkilenen sembol.** O an dönem içi olan ve 00:00 kaydının aralığı 4 saat ya da
      daha kısa olan 415 sembolün **398**'inde kayıt yok, **17**'sinde var. 8 saatlik
      ritimdeki 110 sembolde o an ödeme beklenmiyor. 17 sembolün ortak bir özelliği
      bulunamadı: indirme zamanı ve aralık geçmişi ayırt etmiyor, hepsi 2025-09'dan sonra
      listelenmiş ama aynı dönemde listelenmiş 104 sembolde de kayıt yok.
    - **Pozisyon funding'i (rev.8 kodu).** Penceresi (giriş, çıkış] 04:00'ı içeren
      pozisyonun tamlığı bozulur: ardışık kural (00:00 → 08:00 boşluğu 4 saati aşar),
      pencere sonu 04:00 ise son ödeme koşulu, giriş 00:00 ise başlangıç koşulu. Giriş anı
      tam 04:00 olan pozisyon etkilenmez; giriş anındaki ödeme pozisyona girmez. Bütün
      dönem içi barlar varsayımsal sinyal alındığında, birincil ufukla, boşluğun tek başına
      düşürdüğü pozisyon: H1/H2 (4h) C2 **7.146**, H3 (1d) C2 **5.548**. Sayım karşı-olgusal
      seriyle yapıldı: o ana yapay bir kayıt eklenip tamlık yeniden ölçüldü
      (`rev9_baslangic_tam.csv`, `bosluk_etkisi_rev8`). KEŞİF ve C1'de etki yok.
    - **H2 sinyal penceresi (`funding_ortalamasi`, 24 saat).** Penceresi 04:00'ı içeren
      sinyal barlarında (t = 06-24 04:00 … 06-25 00:00) değer hesaplanamaz: 00:00 kaydından
      08:00 kaydına boşluk iki aralığın büyüğünü aşar. Etkilenen sinyal barı **2.383**: 397
      sembolde 6, 1 sembolde 5. Betik dışı sayım: oran sütunu yerine sabit 0 verildi, yalnızca
      NaN olup olmadığı okundu, aynı karşı-olgusal kayıtla.
    - **Kural değişmedi.** Kod davranışı rev.8'e uygun. Kayıp C2'ye (onay kümesi) düşüyor;
      398 sembolde penceresi bu anı içeren pozisyonlar (4h'de girişi 06-21 04:00 … 06-24
      00:00, 1d'de 06-11 … 06-24 olanlar) oluşmaz; öteki 17 sembol etkilenmez. Rev.9 tartışmasındaki
      son hâl tanımıyla da aynı pozisyonlar düşer (4h 7.129, 1d 5.509), yalnızca penceresi
      04:00'ı içerenler; giriş anı 04:00 olan 398 pozisyon iki kuralda da tam.

15. **Rev.9 uygulaması: açık noktaların durumu (2026-09-23).** Kod `ce89096` (gerçek kod
    yolu), temiz ağaç koşuları: `rev9_uygulama.py` `cf71cf8` (`rev9_uygulama_*_tam.csv`), tam
    denetim `ce89096`, A1 `c342a69`; önceki koşuyla farklar
    `karsilastirma_rev9_uygulama_tam.csv` (`karsilastir.py --onceki ce89096`). Yalnızca sayı;
    değer, işaret ya da getiri yok. Yukarıdaki 1–14. maddelerin metni tarihsel kayıttır.

    **Doğrulama: Rev.9 metnindeki sayılar gerçek kod yoluyla** (`rev9_uygulama_karsilastirma_tam.csv`;
    plan `pencere.pozisyon_plani`, pencere sonu `funding.funding_penceresi_sonu`, tamlık
    `funding.funding_tamlik_ayrintisi`; ölçüm betiğiyle aynı süzülmemiş evren ve aynı ham funding
    serisi):

    | Kalem | Ölçüm betiği | Gerçek kod | Satır farkı |
    |---|---|---|---|
    | Tam pozisyon | 3.887.825 | 3.887.825 | 0 |
    | Kısmi kuyruk | 938.979 (%24,15) | 938.979 (%24,15) | 0 |
    | Pencere sonu eşitlik affı | 435 | 435 | 0 |
    | Çapa yok | 7.248 | 7.248 | 0 |
    | 2026-06-24 nedeniyle eksik | 12.298 | 12.298 | 0 |
    | Dönem sonu bozuk, 4h / 1d | 3 / 3 | 3 / 3 (BNXUSDT d0, ICPUSDT d0, TLMUSDT d0) | 0 |
    | T = K, birincil ufuk: tam / pozisyon | 165 / 170 | 165 / 170 (hepsi dönem sonu çıkışı) | 0 |
    | Kısmi kuyruk payı, 4h ızgara, tek ritim 8h / 4h | %49,94 / %0 | %49,94 / %0 | 0 |

    Fark çıkmadı. Sonra `rev9_hazirlik.py` ve `rev9_ritim.py` gerçek kodu çağıracak biçimde
    değiştirildi (`ce89096`) ve temiz ağaç zincirinde yeniden koşuldu: bütün veri CSV'leri önceki
    çıktılarla bayt düzeyinde aynı (yalnızca ortam kayıtları değişti; bu iki kayıt "kirli" der,
    çünkü ağaçtaki değişiklikler zincirdeki önceki koşunun çıktı CSV'leriydi, kod değil).
    Kopya kalmadığı `tests/test_rev9_tek_tamlik.py` ile sabit. Tarihsel tanımlar (`rev8_tamlik`
    donmuş Rev.8 kopyası; birinci–dördüncü tur önerileri) yürürlükte değildir ve öyle adlandırılır.

    **F2 sağlamlık kontrolünün bayrakları (Rev.9 madde 7).** Tek kaynak
    `funding.funding_tamlik_ayrintisi`: `kuyruk_kismi`, `son_esitlik_affi`, ritim etiketleri
    `capa_aralik_saat`, `son_aralik_saat`, `tek_ritim` (ayrıca `kuyruk_sifir`). Tek karar noktası
    `pozisyon.olay_karari` bunları `funding.pozisyon_funding_ayrintisi` ile aynı satırdan okur ve
    `OnaylanmisPozisyon` alanlarına yazar; alanlar imzaya bağlıdır. **F2 okuma yolu:** her olay ve
    kontrol `olay_karari` çıktısıdır; F2 raporu ritim başına payı ve dışlamalı sağlamlık
    kontrolünü bu alanlardan hesaplar, başka kod yolu kullanmaz. Karışık ritimli pozisyonun
    "funding ritmi" ön-kayıtta tanımlı değil (Rev.9 "F2 şartı": "funding ritmi başına (8, 4, 2, 1
    saat)"); bu yüzden tek bir ritim alanı üretilmedi, üç etiket ham verildi. Tek ritimli
    pozisyonlarda üçü aynı ritmi verir; karışık ritimlilerde (Rev.9 ölçümünde %0,33) hangi
    etiketin kullanılacağı F2'den önce karar ister.

    **Açık noktalar.**
    - **D-B1 (T = K): kapandı** — `760ecd7`; `tests/test_rev9_t_esit_k.py`; doğrulama tablosu.
    - **D-B2 (H2 funding sinyal penceresi): AÇIK, uygulanmadı.** Rev.9 §4 "Funding sinyal
      penceresinin tamlığı" pencerenin başlangıcındaki kaydın ortalamaya girip girmediğini
      söylemiyor: "Pencere t barının kapanışında biter ve 24 saat geriye uzanır. Çapa, pencere
      başında ya da öncesinde kalan son kayıttır … Pencere sonuna denk gelen kayıt (tolerans
      payıyla) pencereye dahildir … Ortalama, penceredeki kayıtların 8 saate normalleştirilmiş
      oranlarından alınır." Pencere başına denk gelen kayıt hem çapa hem "penceredeki kayıt"
      okunabilir; 8 saatlik ritimde ortalama 3 ya da 4 kayıttan alınır. Ön-kayda dokunulmadı;
      `funding_ortalamasi` rev.8 dönemi davranışında kaldı. **Getiriye dokunur (H2 olay kümesi).**
    - **D-B3 (karar noktası 4h girdisi): kapandı** — `3dbda4a`; `tests/test_rev9_fiyat_tabani_4h.py`.
    - **D-B4 (uygunluk tek karar noktasında): kapandı** — `642def8`;
      `tests/test_rev9_uygunluk_kapisi.py`. Tarama yalnızca `.py`; depoda başka uzantıda analiz
      kodu yok (testli).
    - **D-C6 (dönem sınırı `None`): kısmen.** Tarama ve karar noktasındaki ret `187bb52`
      (`tests/test_rev9_donem_none.py`). Pencere fonksiyonları (`pencere_dilimi`,
      `pencere_degeri`, iç içe/ofsetli, `medyan_hacim`, `uygun_mu` dönem bitişi,
      `funding_ortalamasi`) `None`'u hâlâ kabul ediyor: hataya çevirmek 11 test dosyasında 80
      çağrıyı bozar ve bu testler Rev.9 değişikliği sabitlemediği için güncellenmedi. Analiz kodu
      yolu tarama ile kapalı. **Getiriye dokunur sayılır (§14.13), karar bekliyor.**
    - **D-C7 (SETTLED taraması): kapandı** — `fc94497`, `45f2e1d`; `tests/test_rev9_settled_taramasi.py`.
    - **D-C3 (`universe.csv` BNXUSDT d0): kapandı** — `82a0465` (Rev.9 hazırlığında). Bu turun tam
      denetimi bu tablonun ilk koşusu: funding'siz dönem 2 → 3, 2022'de eşik geçen sembol bir az.
    - **D-C1, D-C2, D-C4, D-C5, D-C8: açık, getiriye dokunmaz** (Rev.9 hazırlık raporu 1. tur 5.2
      işaretlemesi değişmedi); F2'yi engellemez.
    - **§14.14, 2026-06-24 boşluğu: kapandı** — Rev.9 §4'te bilinen veri boşluğu olarak yazılı;
      12.298 pozisyon gerçek kodla da eksik.
    - **§14.10 D-A2 funding sınıfı kararı: kapandı** (D-C3 ile).
    - **§14.3 exchangeInfo görüntüsünün zamanı: açık not** (değişmedi). **§14.4: kapandı** (dosya
      kilitli listede).

    **Ağır bulgu (§14.13).** Getiriye dokunan ve kapanmamış iki nokta var: **D-B2** (uygulanmadı,
    ön-kayıt metninde belirsizlik) ve **D-C6'nın kalan kısmı** (test kuralı ile görev çelişiyor).
    §14.13'e göre ikisi de F2'den önce kapanmalı. F1 kapanmadı.

16. **Rev.10 hazırlığı: ölçümler ve küçük kapatmalar (2026-09-24).** Ölçüm `rev10_hazirlik.py`,
    `cab0176`, temiz ağaç (`rev10_*_tam.csv`). Yalnızca kayıt zamanı ve aralık alanı; oran okunmadı.

    **H2 pencere başı** (`rev10_h2_pencere_tam.csv`). Bütün dönem içi 4h barlar (3.378.942), funding
    `funding_yukle` gibi küme aralığına kesilmiş. A: pencere başındaki kayıt hariç, sondaki dahil;
    B: ikisi de dahil. Hesaplanabilirlik Rev.9 çapa + zincir (gerçek tamlık kodu, taban dönem ve küme
    başının geç olanı, son koşulu yok).
    - Hesaplanabilen bar A ve B'de aynı: KEŞİF 1.106.178, C1 1.110.591, C2 1.147.647; fark **0**.
    - İki okumanın kayıt sayısının ayrıştığı bar: KEŞİF 709.980, C1 701.892, C2 1.012.489.
    - Zinciri tam barlarda A'nın kayıt sayısı, ritim başına: 8h'de 3 kayıt 1.883.513, 2 kayıt 253;
      4h'de 6 kayıt 1.457.833, 5 kayıt 1.219; 2h'de 12 kayıt 842 (11: 10, 10: 6); 1h'de 24 kayıt
      18.227 (23: 9, 20: 6); karışık 2.498. B'de 8h'de 3 ya da 4 (941.975 / 941.791), 4h'de 7.
    - 8h'de her zaman 3 değil: 253 barın **252**'si küme sonundaki bar; pencere sonu kaydı bir
      sonraki kümeye düşüyor ve küme kesimiyle görünmüyor. 4h'deki 1.219'un 738'i de böyle.
      Son koşulu uygulanmadığı için pencere sonundaki eksik kayıt H2'de NaN üretmiyor.

    **Dördüncü gevşeklik: aralık geçişine bitişik tek eksik ödeme** (`rev10_gevseklik_tam.csv`;
    süzülmemiş evren, birincil ufuk). Kural tam saydığı hâlde, çapadan son kayda bir çiftte aralık
    değişiyor ve sonraki kayıt "beklenen an"dan sonra geliyor. **Düzeltme (2026-09-24, §14.17):**
    ilk sürümde "iki ölçü de üst sınırdır" yazıyordu; bu yanlıştı. İki ölçü de alt ya da üst sınır
    değil, yalnızca kendi tanımlarıyla sayılmış değerlerdir. Aralık alanı geçişte eskimiş olabildiği
    için gerçek eksiği ayırmazlar. Ayrıca şunları kaçırırlar:
    - `kendi`: aralığı küçülen geçişleri (8→4, 4→1 …).
    - `kendi` ve `kucuk`: ilk çiftte beklenen an girişte ya da önceyse girişten sonraki eksikleri.
    Tanımlar ve yeni `kucuk_giris` ölçüsü §14.17'de.

    | Izgara | Ölçü | KEŞİF | C1 | C2 | Toplam | Başlıca geçiş |
    |---|---|---|---|---|---|---|
    | 4h (H1, H2) | kendi (m = z + önceki kaydın aralığı) | 301 | 170 | 2.448 | 2.919 | 1→4: 2.666 |
    | 4h (H1, H2) | küçük (m = z + küçük aralık) | 470 | 275 | 2.448 | 3.193 | 1→4: 2.666 |
    | 1d (H3) | kendi | 227 | 106 | 1.791 | 2.124 | 1→4: 1.949 |
    | 1d (H3) | küçük | 337 | 179 | 1.791 | 2.307 | 1→4: 1.949 |

    Payda (tam pozisyon): 4h 1.103.215 / 1.107.470 / 1.136.027; 1d 180.928 / 181.562 / 178.623.

    **`aralik_gecerli`** (`data/funding.py`, `funding_tamlik_ayrintisi`): çapadan dizideki son kayda
    kadar her kaydın aralık alanı sonlu ve > 0. Bozuksa zincir ve son maddeleri ölçülemez ve
    pozisyon tam değildir. Veride dönem içi 2.488.869 kaydın hiçbirinde aralık geçersiz değil;
    koşul **0** pozisyon eliyor (her ızgara ve kümede). "Başka maddeyle de elenen" ayrımı bu yüzden
    boş.

    **Kapatmalar.**
    - D-C6'nın kalanı (`7279b93`): pencere, uygunluk ve funding ortalaması fonksiyonları dönem
      sınırını `None` ile kabul etmiyor. 12 test dosyasında 86 `None`, toplam dönem sınırlarıyla
      değiştirildi (`tests/donem_yardimcisi.py`); beklenen sonucu değişen test yok.
    - Tek satırlık, `close_time`'sız çerçeve 4h denetiminden geçmiyor; `sinyal_degerleri` bool kabul
      etmiyor (`2d9b8e6`).
    - F2 ritim sınıfı `funding_ritmi_saat` = son kaydın aralığı, `karisik_ritim` bayrağı (`602034a`).

    **Tarama sınırı (belgelenmiş).** Kaynak taraması `None`'u yalnızca dönem/küme sınırının yazıldığı
    yerde görür; değişkenle taşınan `None`'u (`d = None; donem_baslangic=d`) yakalayamaz.
    - Dönem sınırı için artık önemi yok: `None` çalışma anında TypeError veriyor.
    - Küme sınırı için sınır geçerli, çünkü `kume_baslangic=None` F1 denetiminde meşru.
    - Kapatma önerisi (uygulanmadı): küme sınırını da zorunlu yapmak ve "küme yok" durumunu
      `None` yerine yalnızca `data/` ile F1 dizininin import edebildiği bir işaret nesnesiyle
      (ör. `pencere.KUMESIZ`) söylemek. Böylece değişkenle taşınsa da analiz kodunda çalışma anında
      reddedilir; tarama da işaretin adını arar.

    **Ufuk değerleri bugün nerede tanımlı** (ön-kayda bağlanması Rev.10'a bırakıldı):
    - `config.BIRINCIL_UFUK = {4h: 18, 1d: 14}` (`config.py:138`). "ÖN-KAYIT DEĞİLDİR" başlıklı F1
      bölümünün içinde (D-C4).
    - İkincil ufuklar yalnızca ölçüm betiğinde: `rev9_hazirlik.UFUKLAR = {4h: (6, 18, 42), 1d: (7, 14,
      30)}`; `rev9_uygulama` onu import ediyor.
    - `pencere.cikis_bari`, `pencere.pozisyon_plani`, `pozisyon.olay_karari` `ufuk` ve
      `birincil_ufuk`'u serbest tamsayı olarak alıyor. Denetim yalnızca tamsayı ≥ 1 (denetçi D-B1).

17. **Rev.10 hazırlığı, son tur (2026-09-24; yalnızca KEŞİF).** Ölçüm `rev10_son.py`, `d2e068f`,
    temiz ağaç (`rev10_son_*_tam.csv`, çıktılar `3b305fe`). Yalnızca A grubu ve KEŞİF aralığı; C1/C2
    hesaplanmadı. Oran ve H2 ortalamasının değeri okunmadı.

    **H2 penceresinin küme içinde olması** (1.113.921 KEŞİF 4h barı).
    - Pencere başı küme başından önce: 5 bar. Hepsi bugün de hesaplanamıyor (çapa tabanı); fark 0.
    - Kapanış küme sonundan sonra:
      - Ham karşılaştırmada 234 bar; hepsi bugün (Rev.9 çapa + zincir) hesaplanabilir. Aday kural
        bu 234 barı düşürür.
      - Zaman toleransıyla 0 bar: son barın kapanışı 00:00, küme sonu 23:59:59. Fark 1 saniye,
        §4 "Zaman toleransı"na göre ikisi aynı an.
      - Bu 234 barın pencere sonu kaydı bugün `funding_yukle`'nin ham kesimiyle zaten düşüyor.
    - Bar tabanlı pencereler: `pencere.pencere_dilimi` yalnızca pencere başını küme başıyla (ve
      dönem başıyla) karşılaştırıyor, toleranssız (`beklenen[0] < kume_bas`). Sızıntı testçisinin
      Rev.10 hazırlık bulgusu; §4 "Zaman toleransı"na aykırı. Pencerenin sonu t barıdır ve t
      kümeye açılış anıyla atanır. §3 "Küme sınırı ve geriye bakış" yalnızca başlangıç tarafını
      yazar, son tarafı "Küme sınırı ve ufuk"a bırakır. Son bar (20:00) da 00:00'da kapanır; bar
      tabanında bu kapanış kümenin parçası sayılıyor.

    **Dördüncü gevşeklik, üç ölçü** (4h / 1d; tam pozisyon 1.103.215 / 180.928).
    - `kendi`: 301 / 227 pozisyon.
    - `kucuk`: 470 / 337 pozisyon.
    - `kucuk_giris`: 473 / 337 pozisyon. Aralığı değişen her çift; ilk çiftte taban max(çapa,
      giriş). Sonraki kayıt taban + iki aralığın küçüğü + toleranstan sonra ise şüpheli.
    - `kucuk_giris` şu varsayımla koşullu bir üst sınırdır: gerçek ritim iki kaydın aralık
      alanlarının küçüğünden kısa değil. Bu varsayım altında girişten sonra kurala görünmeyen her
      eksik ödeme bu ölçüde sayılır.
    - `kucuk_giris` şunları kaçırır:
      - aralık alanının iki kayıtta da gerçek ritimden uzun kaldığı durumlar (alan gecikmeli
        değişmiş);
      - son kayıttan pencere sonuna kalan dilim (ayrı madde: kısmi kuyruk).
    - Başlıca geçiş (4h, `kucuk_giris`): 1→4 164, 8→2 69, 4→8 68, 2→8 59, 4→2 55. Etkilenen
      sembol 23 (4h) / 21 (1d).

    **Küme kesimi.** `rev10_hazirlik.py`'nin gevşeklik ve `aralik_gecerli` bölümleri, ayrıca
    `rev9_hazirlik.py` ve `rev9_uygulama.py`'nin bütün pozisyon sayımları (Rev.9 metnindeki sayılar
    dahil) funding'i kümeye kesmeden okur. H2 bölümü keser.
    - KEŞİF'te kesik ve kesiksiz seri arasında fark **0**: tam pozisyon ve üç gevşeklik ölçüsü
      birebir aynı. Nedeni: KEŞİF başı toplam dönem başı, KEŞİF pozisyonlarının pencere sonu küme
      sonunun gerisinde.
    - C1 aynı tarih aralığında olduğu için aynı gerekçe geçerli; ölçülmedi.
    - C2'nin ilk pozisyonlarında çapa 2025-09-01'den önceki bir kayıt olabilir; kesimle çapa
      kaybolur. Etki ölçülmedi (C2 hesaplanmadı).

18. **Rev.10 uygulaması: açık noktaların durumu (2026-09-25).** Ön-kayıt Sürüm 10 (`d7b3629`,
    `52d0751`, `f7009e5`) koda geçirildi. Yalnızca sayı; getiri, funding oranı ya da H2 ortalamasının
    değeri hesaplanmadı. Ölçüm sonuçları yalnızca KEŞİF için (§4 "Ölçüm raporlamasının küme sınırı").

    **H2 hesaplanabilirliği, gerçek kod yolu** (`rev10_uygulama.py`, `72c034b`; `funding_yukle` +
    `funding_ortalamasi`, oran sütunları NaN'lığı korunarak 0 yapıldı, yalnızca NaN olup olmadığı
    okundu). KEŞİF, A grubu, 333 sembol, dönem içi 4h bar 1.113.921.

    | Kod | Koşu | Hesaplanabilen bar |
    |---|---|---|
    | Rev.10 öncesi (`funding_ortalamasi` rev.8 dönemi) | `72c034b`, temiz, çıktı `8477186` | 1.106.156 |
    | Rev.10 (`f9a144d`) | `f9a144d`, temiz, çıktı `26fd27a` | 1.106.178 |

    - Fark +22 bar (17 sembol); Rev.10 ile NaN olan bar **0**, hesaplanabilir olan 22. Sembollerin
      hepsi aralık geçişi olan semboller (BLZ, FLM, FTT, HYPER, BROCCOLIF3B, ERA …); tek tek neden
      sınıflanmadı. Liste: `rev10_uygulama_h2_nan_{once,sonra}_tam.csv` farkı.
    - 1.106.178, §14.16'da kural metniyle (A okuması, Rev.9 çapa + zincir) ölçülen KEŞİF sayısıyla
      aynı: gerçek kod metinle aynı barları hesaplıyor.

    **Doğrulama: Rev.9 ve Rev.10 metnindeki sayılar gerçek kod yoluyla.** Temiz ağaçta, son kodla
    (`26fd27a` sonrası) sırayla koşuldu; her koşunun `*_tam.csv` çıktıları bir önceki commit'tekilerle
    `karsilastir.py` ile karşılaştırıldı (`karsilastirma_rev10_uyg_<koşu>_tam.csv`):

    | Koşu | Commit (çıktı) | Veri CSV'leri |
    |---|---|---|
    | Tam denetim `calistir.py --eski-evren` | `9d1c243` | bayt düzeyinde aynı |
    | A1 `a1_olcumu.py` | `2eac2c8` | aynı |
    | `rev9_uygulama.py` (Rev.9 metnindeki sayılar: 3.887.825, 938.979, 435, 7.248, 12.298) | `26c5de8` | aynı |
    | `rev10_son.py` (Rev.10: 473 / 337, 1.103.215 / 180.928, 23 / 21, kesik = kesiksiz) | `c4e8c8e` | aynı |
    | `rev10_hazirlik.py` (Rev.10: 709.980; geçersiz aralık 0) | `8bf2878` | aynı |

    Her koşuda yalnızca kendi ortam kaydı değişti (commit ve zaman). **Onay kümesi gerekçesi:**
    `rev9_uygulama.py` ve `rev10_hazirlik.py` C1/C2'yi de hesaplar; Rev.9 metnindeki sayılar evren
    toplamı olduğu için doğrulama aynı evreni gerektirir. Yeni bir onay kümesi sayısı raporlanmadı;
    yalnızca önceki çıktılarla eşitlik okundu.

    **Rev.10 maddeleri.**
    - **H2 penceresi (§4 "Funding sinyal penceresinin tamlığı"): kapandı** — `f9a144d`;
      `funding.sinyal_penceresi_ayrintisi` (vektörel, oran okumaz) ve `funding_ortalamasi`
      (`kume_bitis` zorunlu; seri kapanışa kesilir). Testler `test_rev10_h2_penceresi` (31).
      Önceki D-B2 (Rev.9 turu) ve Rev.10 hazırlığındaki D-A3 bununla kapandı.
      - **Uygulanmayan parça (ön-kayıt belirsizliği):** veri katmanının küme kesimi
        (`funding_yukle`, ham `>=`/`<=`) değiştirilmedi. KEŞİF'in son barının (08-31 20:00)
        pencere sonu kaydı 2025-09-01 00:00; Rev.10 "pencere sonuna denk gelen kayıt **girer**" ve
        "Küme sınırı karşılaştırmaları da §4 'Zaman toleransı'na tabidir" diyor, §3 ise C2'yi
        2025-09-01 00:00'da başlatıyor. Bugün bu bar iki kayıttan hesaplanıyor. Denetçiye göre bu
        bardan olay ya da kontrol oluşamaz (çıkış küme sonunu aşar); etkisi sembol başına en fazla
        bir barın H2 değeri. Karar bekliyor.
    - **Bar tabanlı pencerelerde tolerans (kod hatası): kapandı** — `233db57`; `pencere_dilimi`
      dönem ve küme başını `pencere.once` ile karşılaştırıyor (bakışımsızlık kalktı). Bugünkü veride
      etki 0: 690 dönem başı ve küme başları 4h ızgarasında. Tam denetim ve A1 çıktıları aynı.
      Testler `test_rev10_pencere_toleransi`.
    - **Ufuk bağlama (§4 "Ufuk değerlerinin bağlanması"): kapandı (tek kapıda)** — `5c688fb`;
      `config` ön-kayıt bölümü (`BIRINCIL_UFUK`, `IKINCIL_UFUKLAR`, `ILERI_KAYMA_SINIRI`,
      `UFUKLAR`, `HIPOTEZ_IZGARASI`), `pencere.ufuk_dogrula`, `pencere.birincil_ufuk_dogrula`;
      `olay_karari` ön-kayıt dışı değeri reddeder. `rev9_hazirlik.UFUKLAR = config.UFUKLAR`. İç
      adımlar serbest tamsayı alıyor; analiz kodundan çağrılmaları tarama ile yasak (denetçi D-B2,
      aşağıda). Testler `test_rev10_ufuk_baglama`.
    - **Ritim sınıfı (§4 "Pozisyonun funding ritmi"): kapandı** — `9952421`; `funding.ritim_sinifi`,
      `RITIM_SINIFLARI`, `RITIM_SINIFLANMAMIS` ("siniflanmamis"), `ritim_sinifi_ozeti`;
      `OnaylanmisPozisyon.ritim_sinifi` imzalı. Testler `test_rev10_ritim_siniflari`.
    - **Geçerli aralık (§4 "Funding tamlığı" beşinci madde):** kodda Rev.9'dan beri var; H2
      penceresine de uygulanıyor. Kapandı.
    - **Dördüncü gevşeklik:** bilinen sınır; kod karşılığı gerekmiyor (denetçi).
    - **Ölçüm raporlamasının küme sınırı:** `rev10_uygulama.py` yalnızca KEŞİF okur.

    **Kalan sızıntı bulguları.** `739eb50`:
    - NaT `close_time` (4h ve 1d çerçeve): kapandı.
    - Enum koşul değeri: kapandı.
    - `funding_ortalamasi` koruması: iki parça.
      - Tarama `FUNDING_ORAN_DESENI`: analiz kodu oran sütunlarına doğrudan erişemez.
      - Kapı `funding.SINYAL_PENCERESI_REVIZYONU`: ön-kayıttaki paragrafın son revizyonuyla eşit
        olmalı.
    - Testler `test_rev10_kalan_bulgular`. Rev.10 hazırlığının üç xfail'i ve Rev.9 turunun ilk çift
      xfail'i kapandı; işaretleri kaldırıldı.

    **`None` yerine küme işaret nesnesi (`KUMESIZ`): uygulanmadı, belgelenmiş sınır.**
    - Neden: `None`'u `data/` fonksiyonlarında reddetmek gerekir. Testlerde 35 dosyada 165
      `kume_baslangic/kume_bitis=None` çağrısı var ve bunlar Rev.10'un değiştirdiği bir davranışı
      sabitlemiyor. Tur kuralı gereği güncellenemezler.
    - `None` ile işaretin birlikte kabul edilmesi açığı kapatmaz.
    - Sınır: tarama değişkenle taşınan `None`'u yakalamaz (`k = None; kume_baslangic=k`).
      `kume_bitis=None` verilirse H2 penceresinin küme sonu denetimi de atlanır.
    - Üretimde küme sınırları `split.kume_araligi`'ndan gelir.

    **Bu turun denetçi bulguları (düzeltilmedi).**
    - **D-B1:** tek kapı H2 funding değerinin `sinyal_degerleri`'nde bulunmasını şart koşmuyor. K1/K2
      çağrısı değeri hesaplamadan geçerse, penceresi hesaplanamayan barda kontrol oluşabilir.
    - **D-B2:** ufuk kuralı iç adımlarda yalnızca taramayla korunuyor.
      - `analysis/00_veri_denetimi` taramadan muaf.
      - `.ipynb` dosyaları taranmıyor.
      - Hipotez ile ızgara bağı kapıda zorlanmıyor.
    - **D-B3:** H2'nin 24 saatlik penceresi `config`'de değil; `saat` serbest.
    - **D-C1:** küme sonu kaydı (yukarıda). Pozisyon ve sinyal tarafı arasında asimetri var.
    - **D-C2:** `config.ILERI_KAYMA_SINIRI` üretim kodunda okunmuyor. Sınır birincil ufuktan türüyor;
      eşitlik testle korunuyor.
    - **D-C3:** yukarıdaki `KUMESIZ` sınırı.
    - **D-C4:** `rev10_uygulama.py`'nin testi yok.
    - **D-C5:** `kayit_var` ve penceredeki NaN oran şartları metinde yazılı değil.
    - **D-C7:** son koşulu olmadığı için ortalama tek kayıttan hesaplanabilir. Bu, bilinen sınırlar
      listesinde yok.

    **Sızıntı testçisi.** Yeni `test_tur_saldirilari_i` (`f0e0c0a`), 27 vaka, bulgu yok.

    **Rev.9'dan açık kalanlar.**
    - D-C1, D-C2, D-C4, D-C5, D-C8 (Rev.9 turu): açık, getiriye dokunmaz.
    - §14.3: açık not.

    **Ağır bulgu (§14.13).** Önceki turun iki ağır bulgusu kapandı: D-B2 (H2) ve D-C6. Bu turda
    getiriye dokunabilecek üç yeni kural açığı var: **D-B1, D-B2, D-B3**. Üçü de F2 kodu olay ya da
    kontrol ürettiğinde devreye girer. §14.13'e göre ("etkileyip etkilemediği belirsizse etkilediği
    varsayılır") F2'den önce kapanmalı. Küme sonu kaydı (D-C1) karar bekliyor ama denetçiye göre olay
    kümesini değiştirmez. **F1 kapanmadı.**

19. **F1 kapanış turu (2026-09-25).** Yalnızca sayı; getiri hesaplanmadı. Ölçümler KEŞİF için; C1/C2
    için yalnızca "var / yok" ve bar sayısı (görev bunu istedi).

    **Kapatılan kural açıkları** (Rev.10 uygulama turunun denetçi bulguları):
    - **D-B1: kapandı** — `a76f61c`. Karar noktası hipotezin bütün sinyal değerlerini ister
      (`pozisyon.SINYAL_DEGERLERI`); eksik ya da fazla ad TypeError, NaN SinyalPenceresiTamDegil.
      H2'nin funding penceresini kapı funding serisinden kendisi yeniden kurar; çağıranın verdiği sayı
      sonlu olsa bile pencere hesaplanamıyorsa ne olay ne kontrol oluşur. Test `test_f1k_sinyal_kapisi`.
    - **D-B2: kapandı (yapısal)** — `f6c2e1d`. `olay_karari` zorunlu `hipotez` alır; ızgara ve ufuklar
      hipotezden türer (`pencere.hipotez_ufuklari`), uyumsuz eşleşme çalışma anında ValueError;
      onaylı pozisyon hipotezi imzalı taşır. Test `test_f1k_hipotez_baglama`.
      - Tarama ikincil savunma olarak kaldı. Açıkları:
        - `analysis/00_veri_denetimi` bütünüyle muaf.
        - Yalnızca `.py` metni okunur: `.ipynb` ve parçalanmış ad (`importlib` + `getattr`) görünmez.
        - Değişkenle taşınan `None` görünmez.
      - Depoda `.ipynb` bulunmaması ayrıca testli.
      - İç adımlar (`pozisyon_plani`, `cikis_bari`, `cikis_hedefi`) serbest tamsayı almaya devam eder.
        Ürettikleri plan getiri fonksiyonlarına verilemez (`pozisyon_fiyatlari`, `mae` yalnızca imzalı
        onaylı pozisyon alır).
        **Düzeltme (kapı sertleştirme turu, denetçi F1K2 D-B3):** bu cümle yazıldığında
        `funding.pozisyon_fundingi` için yanlıştı; fonksiyon imzalı bir planı kabul ediyordu ve net
        getirinin funding girdisi kapıdan geçmeden üretilebiliyordu. `99238f4`'ten beri yalnızca onaylı
        pozisyon kabul eder; plan alan hesap `funding._plan_fundingi` adıyla yalnızca kapının iç adımıdır.
    - **D-B3: kapandı** — `78e51ba`. `config.H2_FUNDING_PENCERESI_SAAT = 24`, ufuklarla aynı ön-kayıt
      bölümünde; başka değer ValueError. Test `test_f1k_h2_saat`.

    **Küme sonu kaydı** (`f1k_kume_sonu.py`, `6c32ec4`, temiz ağaç, çıktılar `7bde546`; kural
    değiştirilmedi):
    - **KEŞİF'te penceresi küme sonunu aşan bar:** 234 (4h, hepsi 2025-08-31 20:00, 234 sembol).
      - Karar noktasının plan adımı, üç 4h ufkunda (6, 18, 42) **234 barın hepsini** reddediyor.
        Gerekçe `giris_bari_yok`: giriş anı 2025-09-01 00:00'dır ve o bar KEŞİF serisinde yok.
      - Olaylar ve kontroller (K1, K2) aynı karar noktasına gider; bir bar olay olarak da kontrol
        olarak da aynı çağrıyla reddedilir. Olay tarafı 234 / 234, kontrol tarafı 234 / 234.
      - Reddedilmeyen bar yok.
      - H3'ün son günü (2025-08-31, 1d, 234 bar) da üç ufukta (7, 14, 30) `giris_bari_yok`.
    - **Bu barlarda H2 ortalamasının kayıt sayısı** (234'ü de hesaplanabilir). Pencere sonu kaydı her
      durumda eksik:

      | Ritim | Bar | Kayıt (bugün) | Beklenen |
      |---|---|---|---|
      | 8h | 69 | 2 | 3 |
      | 4h | 162 | 5 | 6 |
      | 1h | 2 | 23 | 24 |
      | Karışık (son kayıt 4h) | 1 | 16 | — |
    - **Onay kümelerinde aynı durum:** C1 **var** (243 bar, 2025-08-31 20:00); C2 **var** (522 bar,
      2026-08-31 20:00). Başka sayı raporlanmadı.
    - **Başka pencere türlerinde aynı kesilme yok.**
      - Bar tabanlı geriye bakış pencereleri t barında biter; t barı KEŞİF serisinde. 234 barın
        234'ünde 6 barlık (t hariç), 233'ünde 30 barlık (t dahil) pencere hesaplanabilir.
      - Uygunluk penceresi t gününü dışlar; 225 barda hesaplanabilir.
      - Hesaplanamayan 1 + 9 barın hepsinde neden dönem başı: dönem 30 günden kısa (HEMIUSDT 2,7 gün;
        AIO, CARV, CUDIS, IN, SAPIEN, TOWNS, WLFI, XPL 8,5–26,3 gün). Küme sonu kesilmesi değil.
    - **Denetçi şüphesi (D-C1):** KEŞİF sonu ile C2 başı arasındaki bir saniyeye (23:59:59 < z <
      00:00:00) düşen funding kaydı **0**, bütün evrende. Sınırdan bir dakika içinde 481 kayıt var;
      hepsi C2 başında ya da sonrasında (ms kaymalı 00:00 kayıtları).

    **Doğrulama.** Tam denetim (`90260fc`) ve A1 (`907e73c`) temiz ağaçta; veri CSV'leri önceki
    çıktılarla bayt düzeyinde aynı, yalnızca ortam kayıtları farklı (`karsilastirma_f1k_{calistir,a1}_tam.csv`).

    **§14'ün bütün açık noktaları, son durum:**

    | Nokta | Durum | §14.13 |
    |---|---|---|
    | §14.1–14.2, 14.4–14.12, 14.14 | kapandı (§14.12, §14.15) | — |
    | §14.3 exchangeInfo görüntüsünün zamanı | açık not | dokunmaz |
    | Rev.9 D-B1…D-B4, D-C3, D-C6, D-C7 | kapandı (§14.15, §14.16) | — |
    | Rev.9 D-C1 (küme ölçütü / ileri kayma sırası) | açık | dokunmaz (ret etiketi değişir, olay kümesi aynı) |
    | Rev.9 D-C2 (bütün zaman karşılaştırmaları toleranslı değil: veri katmanı kesimleri) | açık | dokunmaz (bu turda ölçüldü: bir saniyelik aralığa düşen kayıt 0; küme sonu barları kapıda reddediliyor) |
    | Rev.9 D-C4 (ön-kayıt sabitlerinin yeri) | ufuklar ve H2 penceresi kapandı (`5c688fb`, `78e51ba`); zaman toleransı `pencere.py`'de | dokunmaz |
    | Rev.9 D-C5 (NaN / 0 P0, P1 reddedilmiyor) | açık | dokunmaz (veride 0) |
    | Rev.9 D-C8 (imza süreçler arası taşınamaz) | açık | dokunmaz (hata ile durur) |
    | Rev.10 H2 penceresi, tolerans, ufuk, ritim, sızıntı bulguları | kapandı (§14.18) | — |
    | Rev.10 D-B1, D-B2, D-B3 | kapandı (bu tur) | — |
    | Rev.10 D-C1 küme sonu kaydı (ön-kayıt belirsizliği) | açık, karar bekliyor | dokunmaz (234 / 234 bar kapıda reddediliyor; yalnızca H2 değeri etkilenir) |
    | Rev.10 D-C2 `ILERI_KAYMA_SINIRI` iç adımda okunmuyor | açık | dokunmaz (değerler eşit, testli; `hipotez_ufuklari` okuyor) |
    | Rev.10 D-C3 / `KUMESIZ`: küme sınırı `None`'u kapıda kabul ediliyor | açık | **dokunur sayıldı** (aşağıda) |
    | Rev.10 D-C4 `rev10_uygulama.py` testsiz | açık | dokunmaz (ölçüm betiği) |
    | Rev.10 D-C5, D-C7 (metinde yazılı olmayan `kayit_var`, NaN oran; tek kayıtla ortalama) | açık, ön-kayıt notu | dokunmaz (kod ön-kayda uygun) |
    | xfail: `gunluge_cevir` NaN hacim (A6), eşzamanlı `csv_yaz`, parçalanmış ad taraması | açık | dokunmaz (veride örnek yok; kilitle korunuyor; tarama ikincil) |

    **Ağır bulgu (§14.13).**
    - Bu turda getiriye dokunan üç açık kapandı.
    - Kalan tek aday **D-C3**: `olay_karari` küme sınırını `None` ile kabul ediyor; bu durumda küme
      kuralları atlanıyor. Koruma yalnızca kaynak taraması ve taramanın açığı biliniyor (değişkenle
      taşınan `None`).
    - Bu, D-B2'nin "yalnızca taramayla korunan kural" gerekçesiyle aynı yapıda. §14.13'ün "belirsizse
      etkilediği varsayılır" ölçütüyle **getiriye dokunur** sayıldı.
    - Önceki turlarda (§14.16, §14.18) belgelenmiş sınır olarak ağır sayılmamıştı; bu turda
      sınıflama tutarlılık için değiştirildi ve karar sizin.
    - **Bu sınıflamayla F1 kapanmadı.** Kapanması için kapının `None` küme sınırını reddetmesi yeterli.
      Testlerde kapıyı `None` küme sınırıyla çağıran yaklaşık 24 çağrı (17 dosya) gerçek sınırla değiştirilir; iç adımlar
      F1 ölçümleri için `None` kabul etmeye devam eder.

    **Tur sonu ajan bulguları (düzeltilmedi; yukarıdaki "kalan tek aday" cümlesinden sonra geldi).**
    Denetçi D-C3 sınıflamasına katılıyor ve F1'i engelleyen iki yeni bulgu ekliyor:
    - **D-B1 (yeni):** kapı H2 funding değerini doğrulamıyor, yalnızca hesaplanabilirliğine bakıyor.
      Yanlış t ile ya da kapalı pencereyle hesaplanan değer kabul edilir. Getiriye dokunur.
    - **D-B2 (yeni):** `SINYAL_DEGERLERI["H1"]` pump barına bağlı dört değeri K1/K2 kontrol barlarında
      da istiyor. Ön-kayıt kontrol barında pump çapasını tanımlamıyor; bu adlandırma kararı ön-kayıtta
      olmayan bir kural getiriyor. F2'den önce ön-kayıtta karar ister.

    Sızıntı testçisi (`test_tur_saldirilari_j`, `6fe3430`) üç bulguyu xfail(strict) olarak doğruladı:
    - İki bulgu aynı kökten: `__iter__` ile `.items()` arasında ayrışan bir `Mapping`, NaN ve bool
      sinyal değerini tamlık kapısından geçiriyor. Ad ve değer denetimi farklı erişim yolları kullanıyor.
    - Üçüncüsü: `KUME_NONE_DESENI` değişkenle taşınan `None`'u yakalamıyor (D-C3).

    Denetçinin hükmü: **F1 kapanamaz**; engelleyenler D-C3, yeni D-B1 ve yeni D-B2.

    **F1'in çıkış koşulu (not).** CLAUDE.md §4, F1'in çıkış koşulunu "split.csv commit edildi, denetim
    raporu yazıldı" diye tanımlıyor. Bu koşul erken sağlandı; F1 fiilen §14.13 ölçütüyle kapanıyor.
    Uzamanın nedeni, denetimin getiri hesabını etkileyen kural hataları bulması ve bunların on
    revizyonla kapatılmasıydı. İki ölçüt arasındaki fark bilinçlidir.

20. **F1 kapanış turu 2 (2026-09-27).** Getiri hesaplanmadı; F2'ye geçilmedi. Sayılar yalnızca
    KEŞİF'e ya da test girdilerine aittir.

    **Kapı değişiklikleri.**
    - `5b8f376`: `olay_karari` sinyal eşlemini bir kez düz `dict`'e kopyalar; ad ve değer denetimlerinin
      hepsi bu kopya üzerinden yapılır. Sızıntı testçisinin `Mapping.items()` bulgusu (§14.19) kapandı.
      İmza değişmedi.
    - `0e5dc1c`: `olay_karari` küme sınırını `None` olarak kabul etmez (TypeError). Rev.10 D-C3 kapandı.
      İç adımlar F1 ölçümleri için `None` kabul etmeye devam eder. `KUME_NONE_DESENI` taraması ikincil
      savunma olarak kalır.
    - **Kapının sinyal değerlerini kendisi hesaplaması (yeni D-B1): ertelendi.** Karar araştırma
      tarafının. Hipotez başına sinyal hesaplayan kod yok. Kapı değerleri kendisi hesaplayacaksa
      ön-kayıtta tanımsız üç okumayı seçmesi gerekir:
      - H1 pump çapası (olay tarafında θ ve olay tanımı gerekir; kontrol tarafında pump barı yok);
      - H2 kırılım dibinin k'sı;
      - `close[t-30]` tamlık penceresi ile H3 pencerelerinde t gününün dahil olup olmadığı.
      Değer doğrulaması Rev.11 sonrasına bırakıldı.

    **Kontrol barında sinyal (ölçüm, kural yazılmadı).**
    - Kontrol barı üreten ya da sinyal değeri hesaplayan kod yok: `events/` ve `study/` boş.
    - Kapı olay ile kontrolü ayırt etmez. Aldığı adların tam kümesini ve değerlerin sonlu sayı
      olmasını denetler. H2'de ayrıca funding penceresini kendisi yeniden kurar ve hesaplanabilir mi
      diye bakar.
    - Ölçüm, test takımı üzerinden: kapı çağrıları kaydedildi.
      - Kapı 74 H1 çağrısında pozisyon onayladı. Bunların 73'ünde sinyal anından önce 185'ten az 4h
        bar var; yani H1 pencereleri veride kurulamazken de sabit 1.0 değerleriyle pozisyon oluşuyor.
      - H3'te 12 onaylı çağrının 12'sinde 120 günden az 1d geçmişi var.
      - Kapı, değerlerin veriden gelip gelmediğini bilmiyor.
    - Ön-kayıtta karşılığı olmayan varsayımlar:
      - H1: dört adın kontrol barındaki çapası.
      - H1: `tepe` penceresinin t'yi (teyit barını) içerip içermediği; olay tarafında da geçerli.
      - H2: kontrol barında kırılım dibinin hangi k ile kurulacağı.
      - H2 ve H3: `close[t-30]`'un tamlık penceresi (30 ya da 31 bar).
      - H3: "son 30 gün" ve SMA50'de t gününün dahil olup olmadığı; −120…−31 penceresiyle bitişikliği.
      - Ayrıntı ve alıntılar tur raporunda.

    **Doğrulama.** Tam denetim (`bf19721`, `--eski-evren`) ve A1 (`f7d7120`) temiz ağaçta; veri
    CSV'leri önceki çıktılarla bayt düzeyinde aynı, yalnızca ortam kayıtları farklı
    (`karsilastirma_f1k2_{calistir,a1}_tam.csv`). Tam takım 1505 geçti, 4 xfail.

    **Açık noktaların yeniden sınıflanması.** Bu turda "ağır" ve "getiriye dokunur" iki ayrı sütundu.

    **Kapı sertleştirme turu notu.** Bu tablonun ikinci sütunu ("Ağır") ve "ağır" çalışma ölçütü, §14.13
    tek ölçütle yeniden yazıldığı için kaldırıldı. Güncel sınıflama §14.21'de.

    | Nokta | Durum | Getiriye dokunur |
    |---|---|---|
    | §14.3 exchangeInfo görüntüsünün zamanı | açık not | hayır |
    | Rev.9 D-C1 küme ölçütü / ileri kayma sırası | açık | hayır (ret etiketi değişir, olay kümesi aynı) |
    | Rev.9 D-C2 veri katmanı kesimlerinde tolerans yok | açık | hayır (bir saniyelik aralıkta kayıt 0; §14.19) |
    | Rev.9 D-C4 zaman toleransı `pencere.py`'de | açık | hayır |
    | Rev.9 D-C5 NaN / 0 P0, P1 reddedilmiyor | açık | hayır (veride 0) |
    | Rev.9 D-C8 imza süreçler arası taşınamaz | açık | hayır (hata ile durur) |
    | Rev.10 D-C1 küme sonu kaydı | açık, ön-kayıt kararı bekliyor | hayır (234 / 234 bar kapıda reddediliyor) |
    | Rev.10 D-C2 `ILERI_KAYMA_SINIRI` iç adımda okunmuyor | açık | hayır (değerler eşit, testli) |
    | Rev.10 D-C3 küme sınırı `None` | **kapandı** (`0e5dc1c`) | — |
    | Rev.10 D-C4 `rev10_uygulama.py` testsiz | açık | hayır (ölçüm betiği) |
    | Rev.10 D-C5, D-C7 metinde yazılı olmayan `kayit_var`, NaN oran, tek kayıtla ortalama | açık, ön-kayıt notu | hayır (kod ön-kayda uygun) |
    | Tarama açıkları: `analysis/00_veri_denetimi` muaf, `.ipynb`, parçalanmış ad, iç adımlar serbest tamsayı (§14.19) | açık, belgeli sınır | hayır (kapı ufku, hipotezi ve küme sınırını yapısal denetliyor). **Düzeltme (kapı sertleştirme turu):** buradaki "iç adım planı getiri fonksiyonuna verilemiyor" gerekçesi `pozisyon_fundingi` için yanlıştı (F1K2 D-B3; `99238f4` ile kapandı) |
    | xfail: `gunluge_cevir` NaN hacim (A6), eşzamanlı `csv_yaz`, parçalanmış ad taraması | açık | hayır (veride örnek yok; kilitle korunuyor; tarama ikincil) |
    | xfail: `KUME_NONE_DESENI` değişkenle taşınan `None` | açık, belgeli sınır | hayır (kapı artık `None`'u reddediyor) |
    | Sızıntı: `Mapping.items()` ile NaN / bool gizleme | **kapandı** (`5b8f376`) | — |
    | F1 kapanış D-B1: kapı sinyal değerlerini doğrulamıyor, değerler çağırandan geliyor | açık, ertelendi (Rev.11 sonrası) | **evet** (φ ile karşılaştırılan sayı; olay kümesi) |
    | F1 kapanış D-B2: `SINYAL_DEGERLERI["H1"]` kontrol barında pump çapası istiyor | açık, ön-kayıt kararı bekliyor | **evet** (kontrol havuzu) |
    | F1 kapanış D-C2: `close[t-30]` ile "30 barlık pencere t'yi içerir" arasında bir bar | açık, ön-kayıt kararı bekliyor | **evet** (tamlık penceresi olay ve kontrol kümesini değiştirir) |
    | F1 kapanış D-C3: `tepe` tamlık listesinde yok | açık, ön-kayıt notu | **evet** (belirsiz; §14.13) |
    | F1 kapanış D-C1, D-C4, D-C5 (yorum/sayı, NaN denetiminin sırası, RESULTS yapısal gerekçesi) | açık | hayır (olay kümesi değişmez) |
    | Bu tur: `tepe` penceresinin t'yi içerip içermediği | açık, ön-kayıt kararı bekliyor | **evet** |
    | Bu tur: H3 "son 30 gün" ve SMA50'de t günü; −120…−31 ile bitişiklik | açık, ön-kayıt kararı bekliyor | **evet** |
    | Bu tur: ızgara parametrelerinin (θ, δ, φ, k, ν, τ) kapıya ulaşması, ön-kayıtta metin yok | açık | **evet** (k kontrol barının kırılım dibini belirler) |

    **Sonuç.** (Kapı sertleştirme turunda yeniden yazıldı; "ağır" ölçütü kaldırıldı.) Getiriye dokunan açık
    bulgular F2'den önce kapanmalı; güncel liste §14.21'de.

    **Tur sonu ajan bulguları (düzeltilmedi; yukarıdaki tablodan sonra geldi).** Denetçinin bu tur
    bulguları "F1K2" önekiyle, önceki turunkilerden ayrı:
    - **F1K2 D-B1: küme sınırı kayıtlı bir kümeye bağlı değil.** Kapı yalnızca `None`'u reddediyor.
      `Timestamp.min`/`max` ya da karışık sınır (KEŞİF başı + C2 sonu) geçiyor. Sızıntı testçisi bunu
      xfail(strict) ile doğruladı (`test_tur_saldirilari_k`, `80cbad7`): ufku C2'ye taşan bir KEŞİF olayı
      gerçek sınırla reddediliyor, karışık sınırla onaylanıyor. `split.kume_araligi` tek kaynak olarak var,
      kapı onu çağırmıyor. Rev.10 D-C3'ün kapanışı bu yüzden biçimsel.
    - **F1K2 D-B2: dönem sınırları evren tablosuna bağlı değil.** `donem_baslangic`/`donem_bitis`
      serbest girdi. Yanlış sınırla dolgu barları, önceki dönemin funding çapası ve listeleme yaşı kapıdan
      geçebilir.
    - **F1K2 D-B3: net getirinin funding girdisi kapısız elde edilebiliyor.** `funding.pozisyon_fundingi`
      imzalı bir `PozisyonPlani` kabul ediyor, onaylı pozisyon istemiyor. Plan `pencere.pozisyon_plani`
      ile `None` küme ve serbest ufukla kurulabiliyor. P0 ve P1'in barları da plandan okunabiliyor. Tek
      koruma kaynak taraması. **Yukarıdaki tablonun "Tarama açıkları" satırındaki "iç adım planı getiri
      fonksiyonuna verilemiyor" gerekçesi (§14.19'dan taşındı) `pozisyon_fundingi` için yanlış.**
    - F1K2 D-C1: `pozisyon._imza` tarama deseninde yok. F1K2 D-C2: `mae` kararla aynı seriyi zorunlu
      tutmuyor. F1K2 D-C3: NaT küme sınırı sinyal ve uygunluk denetiminden sonra reddediliyor; NaN
      sinyalle birlikte verilirse ret gerekçesi gibi sayılır. F1K2 D-C4: §5–§9 sabitlerinin (ızgaralar,
      H1/H2 bar sayıları, K1/K2 10'ar, §8–§9 eşikleri) çoğu `config.py`'de yok; F2'nin ön koşulu.
    - **Sınıflama ölçütüne itirazlar.**
      - "Girdisi doğruyken" sinyal değerleri için bugün tanımlanamıyor.
      - Ölçüt geriye dönük tutarsız: bu ölçütle Rev.10 D-C3 de ağır olmazdı, F1K2 D-B1 de ağır olmaz.
      - Kapıyı atlayan ikinci kod yolu (F1K2 D-B3) sınıflanmıyor. Ön-kayıt §4 bu yolu "kabul edilmez"
        diye yazıyor. Denetçi ağır sayılmasından yana.
      - Önceki tur D-C3 (`tepe`) için "ağır" öneriyor; D-B2 ile aynı yapıda gördüğü için.
    - Denetçinin hükmü: **F1 kapanamaz.** Kapı ne tek (F1K2 D-B3) ne eksiksiz (F1K2 D-B1, D-B2).

    Sızıntı testçisi `test_tur_saldirilari_k` (`80cbad7`, yalnızca yeni dosya): 21 test, 20 savuşturuldu,
    1 xfail (yukarıdaki F1K2 D-B1). Sözlük kopyasına yönelik saldırıların hepsi savuşturuldu: `dict`
    alt sınıfı, `ChainMap`, `MappingProxyType`, `OrderedDict` alt sınıfı. Boş değerli küme sınırları
    da reddedildi: `0`, `""`, bool, `np.datetime64('NaT')`, ters sıra.

21. **Kapı sertleştirme turu (2026-09-27).** Ön-kayda dokunulmadı; getiri hesaplanmadı; F2'ye geçilmedi.
    Kapının sinyal değerlerini kendisi hesaplaması (F1 kapanış D-B1) Rev.11'i bekliyor, yapılmadı.

    **Kapı değişiklikleri.** Üçü de F1K2 turunun denetçi bulgularını kapatır.
    - `99238f4` (F1K2 D-B3): `funding.pozisyon_fundingi` yalnızca onaylı pozisyon kabul eder. Toplam iç
      adımla yeniden hesaplanır ve kararın `funding_toplami`'na eşit olmalıdır; başka bir funding serisi
      ValueError verir. Plan alan hesap `funding._plan_fundingi` adıyla kapının iç adımıdır; analiz kodunda
      `CIKIS_KAPI_DISI_DESENI` ile yasaklı. §14.19 ve §14.20'deki yanlış gerekçe yerinde düzeltildi.
    - `3f789ea` (F1K2 D-B1): kapı küme sınırı almaz, küme ADI alır (`kume`: KESIF / C1 / C2). Sınırları
      `split.kume_araligi`ndan kendisi okur. Serbest ya da karışık sınır çifti, `None`, NaT, bilinmeyen ad
      ve `str` alt sınıfı programlama hatasıdır. Sızıntı testçisinin karışım bulgusu (xfail) normal teste
      döndü. F1K2 D-C3 (NaT'nin geç reddi) de kapandı: küme adı her denetimden önce doğrulanıyor.
    - `10733c0` (F1K2 D-B2): kapı dönem sınırı almaz. `sembol` ve `donem_no` alır, sınırları commit'li
      evren tablosundan okur (hariç tutulmayan semboller, geçerli dönemler). Tabloda olmayan dönem
      ValueError verir. Aynı kayıttan iki ek denetim yapılıyor; görev metninin ötesindedir:
      - sembolün bölme grubu kümeye ait olmalı (on-kayıt §3; KEŞİF A, C1 B, C2 A + B);
      - tablodaki funding'siz dönem bayrağı olayı ve kontrolü düşürür (on-kayıt §2). Funding
        çerçevesinden bağımsızdır; önceden yalnızca çapa kuralı dolaylı olarak kapsıyordu.

    **Sınıflama (§14.13, tek ölçüt).**
    - Getiriye dokunabilen bulgu F2 başlamadan kapanır.
    - Ön-kayıt ile kodun ayrıştığı her yer dokunur sayılır. Buna ön-kayıtta tanımsız kalan ve kodun bir
      okuma seçtiği yerler de dahildir.
    - Dokunmayan bulgu açık nokta olarak kalır.
    - Önceki turlarda "dokunmaz" sayılan iki nokta bu ölçütle "dokunur"a geçti: Rev.9 D-C2 ve Rev.10
      D-C1 / D-C5.

    | Nokta | Durum | Getiriye dokunur |
    |---|---|---|
    | F1K2 D-B1 küme sınırı çağırandan | **kapandı** (`3f789ea`) | — |
    | F1K2 D-B2 dönem sınırı çağırandan | **kapandı** (`10733c0`) | — |
    | F1K2 D-B3 `pozisyon_fundingi` plan kabul ediyor | **kapandı** (`99238f4`) | — |
    | F1K2 D-C3 NaT küme sınırı sinyal denetiminden sonra | **kapandı** (`3f789ea`) | — |
    | §14.3 exchangeInfo görüntüsünün zamanı | açık not | hayır |
    | Rev.9 D-C1 küme ölçütü / ileri kayma sırası | açık | hayır (yalnızca ret etiketi; ön-kayıt etiket tanımlamıyor, olay kümesi aynı) |
    | Rev.9 D-C2 veri katmanı kesimlerinde zaman toleransı yok | açık, **kod düzeltmesi** | **evet**: ön-kayıt §4 "Zaman toleransı" bütün karşılaştırmaları kapsıyor, kod kesimlerde uygulamıyor. KEŞİF/C2 arasındaki bir saniyede ölçülen kayıt 0 (§14.19), ama ölçüt ayrışmayı dokunur sayar |
    | Rev.9 D-C4 zaman toleransı sabitinin `pencere.py`'de olması | açık | hayır (yer; değer ön-kayıtla aynı) |
    | Rev.9 D-C5 NaN / 0 P0, P1 reddedilmiyor | açık | **evet** (kapı sertleştirme turu 2'de yeniden sınıflandı: ön-kayıtta tanımsız, kod bir okuma seçmiş; önceki "veri sabit" gerekçesi yanlıştı, fiyat verisi `cache/` altında ve git dışında). NaN ve ±inf P0/P1 turu 2'de açık hata; 0 değeri hâlâ reddedilmiyor |
    | Rev.9 D-C8 imza süreçler arası taşınamaz | açık | hayır (hata ile durur) |
    | Rev.10 D-C1 H2 penceresinin küme sonundaki kaydı | açık, **Rev.11** | **evet** (ön-kayıtta tanımsız; bugün 234 / 234 bar pozisyon adımında reddediliyor) |
    | Rev.10 D-C2 `ILERI_KAYMA_SINIRI` iç adımda okunmuyor | açık | hayır (ön-kayıt sınırı birincil ufka eşitliyor; kod birincil ufku kullanıyor) |
    | Rev.10 D-C4 `rev10_uygulama.py` testsiz | açık | hayır (ölçüm betiği) |
    | Rev.10 D-C5 H2 penceresinde `kayit_var` ve NaN oran şartları | açık, **Rev.11** | **evet** (kodda var, metinde yok) |
    | Rev.10 D-C7 H2 ortalaması tek kayıttan hesaplanabilir | açık, Rev.11 notu | hayır (kod ön-kayıt metnine uygun; bilinen sınırlar listesinde yok) |
    | Tarama açıkları (analiz dizini muaf, `.ipynb`, parçalanmış ad, iç adımlar) | açık, belgeli sınır | hayır (P0, P1 ve funding onaylı pozisyondan; iç adımlarla kurulan yol kararlı atlatmadır ve F2 denetiminde aranır) |
    | xfail: `gunluge_cevir` NaN hacim (A6) | açık | **evet** (kapı sertleştirme turu 2'de yeniden sınıflandı: xfail olduğu için ayrışma biliniyor; ölçülen 0 muafiyet değildir, §14.13) |
    | xfail: eşzamanlı `csv_yaz`, parçalanmış ad taraması | açık | hayır (kilitle korunuyor; tarama ikincil) |
    | xfail: `KUME_NONE_DESENI` değişkenle taşınan `None` | konusuz | hayır (kapı küme sınırı almıyor) |
    | F1 kapanış D-B1 sinyal değerleri çağırandan, doğrulanmıyor | açık, **Rev.11 sonrası kod** | **evet** |
    | F1 kapanış D-B2 H1 kontrol çapası | açık, **Rev.11** | **evet** |
    | F1 kapanış D-C2 `close[t-30]` tamlık penceresi | açık, **Rev.11** | **evet** |
    | F1 kapanış D-C3 `tepe` tamlık listesinde yok | açık, **Rev.11** | **evet** |
    | F1 kapanış D-C1, D-C4, D-C5 | açık | hayır (yorum, ret etiketi sırası, belge) |
    | F1K2 turu: `tepe`'de t; H3'te t günü; SMA50; ızgara parametreleri; kontrol barındaki k | açık, **Rev.11** | **evet** |
    | F1K2 D-C1 `pozisyon._imza` tarama deseninde yok | açık | hayır (kararlı atlatma) |
    | F1K2 D-C2 `mae` kararla aynı seriyi zorunlu tutmuyor; onaylı pozisyon sembol ve küme taşımıyor | açık | hayır (MAE raporlanır, eşik değil) |
    | F1K2 D-C4 §5–§9 sabitleri `config.py`'de yok | açık, F2 ön koşulu | **evet** (kapı sertleştirme turu 2'de yeniden sınıflandı; Rev.11 listesinin 7. maddesi bunun alt kümesi) |

    **Getiriye dokunan açıklar.** F2 bunlar kapanmadan başlamaz.
    - Kod düzeltmesi: Rev.9 D-C2.
    - Rev.11 kararı: aşağıdaki liste.
    - Rev.11'den sonra kod: F1 kapanış D-B1, yani kapının sinyal değerlerini kendisi hesaplaması.

    **Rev.11'i bekleyenler.** Her birinin altında kodun bugünkü davranışı.
    1. **`tepe` penceresi ve tamlık listesi** (F1 kapanış D-C3; `tepe`'de t).
       - Kod tepeyi hesaplamıyor. Kapı `tepe` adını H1'in olay ve kontrol çağrısında çağırandan sonlu bir
         sayı olarak şart koşuyor. Pencerenin t'yi içerip içermediğini ve tamlığını bilmiyor.
    2. **`close[t-30]`'un tamlık penceresi** (F1 kapanış D-C2).
       - Kod hesaplamıyor. Kapı `kapanis_30_once`'ı (H2, H3) çağırandan istiyor.
       - `pencere.beklenen_zamanlar`ın yorumu H2'nin 30 barlık penceresini `[t-29..t]` olarak örnekliyor;
         bu aralık `close[t-30]`'u içermiyor.
    3. **H3'te t gününün dahil olması.**
       - Kod H3'ün "son 30 gün" ve −120…−31 hacim pencerelerini hesaplamıyor. Kapı
         `hacim_medyani_30g` ve `hacim_medyani_120_31`'i çağırandan istiyor.
       - Uygunluk hacmi (ayrı bir kural) t gününü dışlıyor.
    4. **SMA50.**
       - Kapı `sma50`'yi çağırandan istiyor. Uzunluğu ve kapsadığı günler kodda tanımlı değil.
    5. **Kontrol barındaki k.**
       - k kodda ve config'te yok. Kapı `kirilim_dip`'i k'yı bilmeden istiyor.
    6. **H1 kontrol çapası** (F1 kapanış D-B2).
       - Kapı dört pump adını (`pump_dip`, `pump_hacim_6`, `pump_hacim_medyani_180`, `tepe`) kontrol
         barında da şart koşuyor. Kontrol barındaki çapa kodda tanımlı değil.
    7. **Parametrelerin kapıya ulaşması.**
       - Kapı yapılandırma (θ, δ, φ, k, ν, τ) almıyor. Izgara değerleri config'te yok.

    Aynı ölçütle eklenenler (görev listesinde yoktu):
    8. **H2 penceresinin küme sonundaki kaydı** (Rev.10 D-C1).
       - KEŞİF'in son barlarında pencere hesaplanabilir sayılıyor, ama pencere sonundaki (C2
         başındaki) kayıt ortalamaya girmiyor.
       - Bu 234 bar pozisyon adımında reddedildiği için olay kümesi bugün değişmiyor.
    9. **H2 penceresinde `kayit_var` ve NaN oran** (Rev.10 D-C5).
       - `funding.sinyal_penceresi_ayrintisi` pencerede kayıt yoksa pencereyi hesaplanamaz sayıyor.
       - `funding_ortalamasi` penceredeki bir oran NaN ise NaN döndürüyor.
       - İki şart da ön-kayıtta yazılı değil.
    10. **Not (Rev.10 D-C7):** H2 ortalaması tek kayıttan hesaplanabiliyor. Kod metne uygun; bilinen
        sınırlar listesine eklenmesi bir ön-kayıt notu.

    Kapı sertleştirme turu 2'de eklenenler (denetçinin KS isteği, araştırma tarafının kararı):
    11. **Bekleme süresi** (§5).
        - Açık sorular: t'den mi, girişten mi ölçülür? Reddedilen olay beklemeyi başlatır mı? Dönemler
          arasında sürer mi? Yapılandırma başına mı işler?
        - Kod bugün: bekleme süresini uygulayan kod yok.
    12. **K1/K2 örneklemesi** (§6).
        - Açık sorular: "herhangi bir olayına" ve "o anda olay üretmemiş" hangi olaylara ve yapılandırmaya
          göre? 10'dan az aday varsa ne olur? İadeli mi, iadesiz mi? Tohum hangi sırayla kullanılır?
        - Kod bugün: kontrol barı seçen kod yok.
    13. **§7'deki `r` tanımı.**
        - `p = (r + 1) / (10000 + 1)` formülünde `r`'nin neyi saydığı yazılı değil.
        - Kod bugün: p-değeri ya da yeniden örnekleme kodu yok.

    Maddelerin ön-kayıt alıntıları depo dışındaki Rev.11 girdisindedir (`D:/Projeler/prompts/rev11_girdi.md`).

    **Bilinen sınır (düzeltilmedi, denetim sorusu).** Kapı `kume="C1"` ya da `"C2"` ile çağrıldığında aktif
    bir onay koşusu (`split.onay_kosusu`) aramıyor. Onay koruması yalnızca veri yükleyicisinde
    (`split.kume_erisimi`). Kapıya verilen fiyat, funding ve 1d çerçeveleri de hâlâ çağırandan geliyor;
    kapı bunların hangi sembolün ya da kümenin verisi olduğunu doğrulamıyor.

    **Tur sonu ajan bulguları (düzeltilmedi; yukarıdaki tablo ve listeden sonra geldi).** Denetçinin bu tur
    bulguları "KS" önekiyle. Aşağıdaki sınıflar denetçinin önerisidir; yukarıdaki tablo değiştirilmedi.
    - **KS D-B1: fiyat ve funding çerçeveleri çağırandan geliyor.**
      - Kapı yalnızca biçimi doğruluyor: `mumlar_4h` için 4h ızgarası ve `close_time`; funding için tamlık.
      - Hangi sembolün ya da kümenin verisi olduğuna, boşluğun doldurulup doldurulmadığına bakmıyor.
      - Örnekler:
        - (a) `reindex`/`asfreq` + `ffill` ile düzenli ızgaraya getirilmiş bir 4h serisi `GirisBariYok`
          ve ileri kaymayı hiç üretmez; boşluk üzerinden bayat fiyatla çıkış yapılır (on-kayıt §2 rev.3).
          Bu deyimler `TURETILMIS_SERI_DESENI`'nde yok.
        - (b) Sembol kaymasıyla başka bir sembolün fiyatları onaylanır.
        - (c) Doldurulmuş ya da değiştirilmiş bir `oran` sütunu tamlıktan geçer.
      - Kapı bu çerçeveleri `sembol` ve `kume` ile veri yükleyicisinden kendisi alabilir.
      - `pozisyon_fiyatlari`'nın P0 ve P1'i de bu çerçeveden gelir.
      - Denetçiye göre getiriye **dokunur**.
    - **KS D-B2: 1d serisi tek seri olarak bağlı değil.**
      - `gunluk_mumlar` yalnızca 1d biçimiyle doğrulanıyor.
      - `klines.birincil_gunluk_indir` (küme korumalı, `ham_` öneki yok) çerçevesi de denetimlerden geçer.
      - Borsanın 1d dosyasında 4h barı eksik günler de satırdır; örneğin 2022-02-26…28 kesintisi. Bu
        günlerde uygunluk penceresinin tamlığı yanlışlıkla sağlanır.
      - Ön-kayıt §2 rev.8 "Bu seri tektir" ile ayrışıyor.
      - Denetçiye göre **dokunur**.
    - **KS D-B3: sinyal barı (t) varlığı kapıda denetlenmiyor.**
      - Yalnızca t+1 barı aranıyor (`pencere.pozisyon_plani`).
      - t barı eksik, t+1 mevcutsa, ya da H3'te t günü 1d serisinde yoksa, pozisyon onaylanır.
      - Yapısaldır, Rev.11'deki okumalara bağlı değil.
      - Denetçiye göre **dokunur**.
    - **KS D-B4: onay koşusu kapıda yok; veri kapısı hipotezi denetlemiyor.**
      - Kapı `kume="C1"`/`"C2"` ile aktif onay koşusu olmadan çağrılabiliyor
        (`test_ks_donem_kaydi` bunu onaylıyor).
      - `split.kume_erisimi` onay koşusunun yalnızca kümesini karşılaştırıyor. `onay_kosusu("H2", "C1")`
        içinde H1 ve H3'ün C1 pozisyonları da onaylanır; onay kaydında tek satır (H2) oluşur.
      - `split._AKTIF_KOSU` ataması taramada yok.
      - İlgili kurallar: CLAUDE.md §3.3; ön-kayıt §3 ve §9.
      - Denetçiye göre **dokunur**; pratik etkisi F3'te.
    - **KS D-B5 (şüpheli, testle doğrulanmadı): UTC dışı saat dilimli `sinyal_zamani` olayları sessizce
      düşürüyor.**
      - `utc_zamani` saat dilimi var mı diye bakıyor, UTC mi diye bakmıyor.
      - `eligibility.medyan_hacim`'deki `floor("D")` yerel saatle yuvarlıyor. Uygunluk penceresi NaN oluyor
        ve H1/H2 olayları hata vermeden `UygunDegil` ile düşüyor.
      - CLAUDE.md §5 ile ayrışıyor.
    - **KS D-C1…D-C6:**
      - D-C1: `pozisyon_fundingi` taramada hâlâ yasak. Bu yüzden analiz kodunun yasal yolu
        `funding_toplami` özniteliği kalıyor ve öznitelik okuması imzadan geçmiyor.
      - D-C2: kayıt taraması `pozisyon.donem_kaydi`, `grup_dogrula`, `kume_sinirlari`, `config`
        sabitleri ve `split._AKTIF_KOSU` atamalarını kapsamıyor.
      - D-C3 (şüpheli): `_kayitlar` önbelleği süreç boyunca donuyor. Bugün tetikleyen çağrı yok.
      - D-C4: `pozisyon.py` modül açıklaması "saf fonksiyonlar" diyor, kapı artık disk okuyor.
      - D-C5: onaylı pozisyon sembol, küme ve dönem taşımıyor (K2 havuzu, §9.5).
      - D-C6: beklentisi TypeError'a dönen iki test (`tur_saldirilari_j` küme sonu,
        `tur_saldirilari_k` ters sıra) kapıyı değil Python'un imza denetimini sınıyor. Kapı düzeyinde
        küme sonu testi, gerçek KEŞİF son barıyla kurulmalı.
    - **Sızıntı testçisi bulgusu (`test_tur_saldirilari_l`, `d6cc482`, xfail(strict)).**
      - `olay_karari` funding toplamında yalnızca `math.isnan` denetliyor; tamlık kodu oranı okumuyor.
      - Pencere içindeki tek bir kayıtta `oran = inf` olduğunda `funding_toplami = inf` olan onaylı bir
        pozisyon üretiliyor.
      - Net getiriye doğrudan girer; **dokunur**.
      - Dosyanın öteki 7 testi savuşturuldu: gerçek A/B sembolleri yanlış kümede, yeniden adlandırma
        zinciri grupları, önbelleğin salt okunurluğu, gerçek funding'siz dönem, dönem sonrası aşırı
        fiyatlı barlar, NaN toplamın eşitlik kenarı.
      - O testlerden birinin kurgusu hatalıydı: giriş anındaki kaydı siliyordu. Ana oturum silinen kaydı
        giriş sonrasındaki kayıtla değiştirdi; iddia aynı.
    - **Denetçinin sınıflama itirazları.**
      - **Rev.9 D-C5** (NaN / 0 P0, P1) ve **A6 xfail'i** (`gunluge_cevir` NaN hacim) "dokunur" olmalı.
        İkisi de "ön-kayıtta tanımsız, kod bir okuma seçmiş, ölçülen 0" yapısında; aynı yapıdaki Rev.9
        D-C2 ile Rev.10 D-C1 "evet" sınıflandı.
      - Yukarıdaki "commit'li veride yok, veri sabit" gerekçesi yanlış: fiyat verisi `cache/` altında,
        git dışında. A6 bir xfail olduğu için ayrışma zaten biliniyor. Ya bu ikisi "evet" olmalı, ya da
        §14.13'e ölçülmüş sıfır etki için bir muafiyet eklenmeli.
      - **F1K2 D-C4** (§5–§9 sabitleri config'te yok) "evet" olmalı; Rev.11 listesinin 7. maddesi bunun
        alt kümesi ve "evet".
      - F1K2 D-C2'nin sembol/küme kısmı dokunabilir (KS D-C5).
      - "Bilinen sınır" paragrafının çerçeve kısmı "evet" olmalı (KS D-B1, D-B2).
    - **Denetçinin Rev.11 listesine eklenmesini istedikleri** (ön-kayıtta tanımsız, kod bir okuma
      seçmek zorunda kalır):
      - **Bekleme süresi (§5):**
        - t'den mi, girişten mi ölçülüyor?
        - Kapının reddettiği olay beklemeyi başlatır mı?
        - Dönemler arasında sürer mi?
        - Yapılandırma başına mı işler?
      - **K1 örneklemesi:**
        - "herhangi bir olayına" reddedilen ya da başka yapılandırmaya ait olayları kapsıyor mu?
        - 10'dan az aday varsa ne olur?
        - İadeli mi, iadesiz mi?
      - **K2 örneklemesi:**
        - "o anda olay üretmemiş" hangi yapılandırmaya göre?
        - 10'dan az uygun coin varsa ne olur?
      - **§7'deki `r` tanımı:** p-değerinde `r`'nin neyi saydığı yazılı değil. F3 kararını belirler;
        CLAUDE.md §3.4 gereği keşif çıktıları görülmeden yazılmalı.
      - Ayrıca: H1'de 12 barlık izleme sürerken yeni bir pump barı; H3'te "ilk gün"ün tanımı.
      - Tohum: F2'nin K1/K2 örneklemesi `config.TOHUM` ile ve belirlenmiş bir sembol sırasıyla yapılmalı.
    - Denetçinin hükmü: bu turun üç değişikliği amacına ulaşıyor. Kapı hâlâ şu olguları çağırandan kabul
      ediyor, oysa kendisi türetebilir:
      - fiyat, funding ve 1d çerçeveleri;
      - sinyal barının varlığı;
      - onay koşusu.

22. **Kapı sertleştirme turu 2 (2026-09-28).** Ön-kayda dokunulmadı; getiri hesaplanmadı; F2'ye geçilmedi.
    Kapının sinyal değerlerini kendisi hesaplaması (F1 kapanış D-B1) Rev.11'i bekliyor, yapılmadı.

    **Kapı değişikliği (`31da614`).**
    - **Veri kapıda yükleniyor** (KS D-B1, KS D-B2).
      - `olay_karari` 4h, funding ve 1d çerçevesi almaz.
      - 4h mumlarını ve funding kayıtlarını sembol ve küme adıyla küme korumalı yükleyicilerden alır
        (`pozisyon._veri_yukle`: `klines.mumlari_yukle`, `funding.funding_yukle`) ve küme aralığına yeniden
        keser.
      - 1d serisini 4h barlardan tek yol `klines.gunluge_cevir` ile türetir (ön-kayıt §2 rev.8 "Bu seri
        tektir").
      - C1/C2 için yükleyici açık bir onay koşusu istiyor; KS D-B4'ün onaysız C1/C2 kısmı bu yüzden kapandı.
        Onay koşusunun **hipotezi** kapıda hâlâ eşleştirilmiyor; KS D-B4 bu kısmıyla açık.
    - **Sinyal barı** (KS D-B3): t barı hipotezin ızgarasındaki dönem içi seride yoksa `SinyalBariYok`
      (olay ya da kontrol oluşmaz).
      - 4h'de t açılışlı bar gerekir.
      - 1d'de t günü türetilmiş seride olmalı, yani altı 4h barın tamamı.
    - **Sonlu olmayan değerler** (sızıntı testçisinin inf bulgusu): ±inf funding toplamı, sonlu olmayan
      P0, P1 ve MAE penceresindeki high açık `ValueError` veriyor. Sinyal değerleri zaten sonluluk
      denetiminden geçiyordu. NaN oran önceki gibi `FundingTamDegil` (Rev.10 D-C5, Rev.11'de).
    - **UTC** (KS D-B5): önce testle doğrulandı; ölçüm aşağıda. Kapı artık UTC dışı saat dilimli sinyal
      zamanını `ValueError` ile reddediyor. Saat dilimsiz zaman önceki gibi `TypeError`.
    - **Onaylı pozisyon kimlik taşıyor:** sembol, küme ve dönem numarası imzalı (KS D-C5). `mae(pozisyon)`
      ve `funding.pozisyon_fundingi(pozisyon)` veriyi bu kimlikle kendileri yüklüyor; çerçeve verilemez.
    - `pozisyon.py` modül açıklaması düzeltildi: kapı disk okur, "saf fonksiyonlar" değil (KS D-C4).

    **KS D-B5 doğrulaması** (kapı değiştirilmeden önce, scratchpad testi):
    - Aynı an (2025-03-10 04:00Z) üç saat dilimiyle verildi: UTC, `Europe/Istanbul`, `America/New_York`.
    - **UTC:** H1, H2 ve H3'ün üçü de onaylandı.
    - **UTC dışı iki saat dilimi:**
      - H1 ve H2 hata vermeden `UygunDegil` ile düştü;
      - H3 açık `ValueError` ("1d bar zamanı gün açılışı olmalı") verdi.
    - Mekanizma `test_ks2_kapi_veri::test_utc_disi_saat_dilimi_uygunlukta_gunu_kaydirir` ile kalıcı:
      `eligibility.medyan_hacim` UTC dışı t'de günü yerel saatle yuvarlıyor ve NaN veriyor. Bu alt katman
      değişmedi; koruma kapıda.

    **Kural 0 notları (ön-kayıtta tanımsız seçimler).**
    - Sonlu olmayan fiyat ve funding için ön-kayıtta metin yok. Kapı bir olay-oluşmaz kuralı icat etmiyor;
      açık hata veriyor, yani koşu durur ve veri incelenir. NaN oranın `FundingTamDegil` olması eski
      davranış ve Rev.11 listesinde (Rev.10 D-C5).
    - 1d serisi yalnızca pozisyonun döneminden türetiliyor. `gunluge_cevir` günleri dönem dönem kurduğu için
      bu dönemin günleri, sembolün bütün dönemleriyle kurulan seriyle aynı; bir seçim değil.

    **Test güncellemeleri.**
    - Kapı çağrıları yeni imzaya geçti. `tests/kapi_yardimcisi.veri` sentetik 4h ve funding kaydı yapıyor.
      Eski ayrı 1d uygunluk serisinin karşılığı, 4h serisinin öncesine eklenen hacimli düz barlar. Günlük
      hacim tam değer olarak 00:00 barına yazılıyor; kayan nokta bölmesi eşik testlerinde eşitliği bozuyordu.
    - `tests/conftest.py`: `_veri_yukle` yaması. Sentetik yolda da C1/C2 için onay koşusu şart
      (gerçek yükleyicinin aynası).
    - **Beklentisi değişen testler:**
      - `test_ks_donem_kaydi::test_grup_kumeye_ait_olmali`: onaysız C1 onayı → `OnayGerekli`; koşu
        içinde onaylanıyor.
      - `test_f1k2_kume_none::test_sinyal_kumede_degilse_olay_olusmaz`: C2 → önce `OnayGerekli`, koşu
        içinde `OlayOlusmaz`.
      - `test_tur_saldirilari_k::test_kesif_basi_ile_c2_sonu_karisimi_verilemez`: C2 aynı biçimde.
      - `test_rev9_uygunluk_kapisi::test_gunluk_yerine_4h_cerceve_hata_verir`: `ValueError` →
        `TypeError` (1d çerçevesi verilemez).
      - `test_rev9_fiyat_tabani_4h::test_mae_de_1d_cercevesini_reddeder`: `ValueError` → `TypeError`
        (`mae` çerçeve almaz).
      - `test_ks_funding_onayli::test_baska_funding_serisi_reddedilir` ve
        `test_tur_saldirilari_l::test_pozisyon_fundingi_nan_toplami_sessizce_kabul_etmez`: "başka seri"
        artık yükleyici kaydında değiştiriliyor.
    - **Fikstür değişiklikleri (beklenti aynı):**
      - `test_rev8_mae`: 4h fikstürünün `quote_volume=1.0` sütunu kaldırıldı; uygunluk artık bu seriden
        türüyor.
      - `test_rev9_uygunluk_kapisi`: `gun` girdisi `hacim` ve `eksik_gunler` ile.
    - **KS D-C6:**
      - `test_tur_saldirilari_j` küme sonu testi kapının gerçek davranışını sınıyor: KEŞİF'in son barı, veri
        C2'ye uzanıyor, ret `GirisBariYok`. Kesme olmasaydı ret `KumeSiniriHatasi` olurdu.
      - `test_tur_saldirilari_k` ters sıralı sınır testi gerçek davranışa çevrilemedi: ters sıralı bir küme
        `split.kume_araligi`nda yok, dolayısıyla kapıya verilebilecek bir girdi değil. İmza denetimi olarak
        kaldı.
    - **`test_tur_saldirilari_l` inf testi xfail'den çıktı.** Önceki gövde inf'i tam giriş anındaki
      kayda koyuyordu; ön-kayıt §4 bu ödemeyi pozisyon dışında tutar. Bu yüzden toplam sonluydu ve test
      yanlış nedenle xfail oluyordu. Giriş sonrası kayda alındı; beklenti `ValueError`.
    - `test_rev9_donem_none` kapı kısmı yeni imzayla yeniden yazıldı; eski hâli imza hatası yüzünden
      boş yere geçiyordu.
    - Yeni: `test_ks2_kapi_veri` (39); `tarama_yardimcisi.KAYIT_DESENI` `_veri_yukle`, `_kume_verisi`,
      `SENTETIK_VERI` ile genişletildi.

    **Bilinen sınırlar (düzeltilmedi).**
    - **Hız:** kapı her çağrıda diskten yüklüyor. Gerçek veriyle bir çağrı 1,3–3,6 sn sürdü (bir A grubu
      sembol, KEŞİF). F2'nin K1/K2 çağrıları için önbellek gerekecek. C1/C2'de önbellek onay denetimini
      atlamamalı.
    - Izgara dışı bir t (ör. 06:00), sinyal barı denetiminden önce plan adımında `GirisBariYok` ile
      reddediliyor. Olay oluşmuyor; yalnızca ret etiketi.
    - **KS D-C2:** tarama `donem_kaydi`, `grup_dogrula`, `kume_sinirlari`, `config` sabitleri ve
      `split._AKTIF_KOSU` atamalarını hâlâ kapsamıyor.

    **Sınıflama (§14.13, muafiyetsiz).** §14.21 tablosu güncellendi; Rev.11 listesine 11–13 eklendi.
    Bu turda "dokunur"a geçenler: Rev.9 D-C5, A6 xfail'i, F1K2 D-C4.

    **KS bulgularının durumu:**

    | Bulgu | Durum |
    |---|---|
    | KS D-B1 fiyat ve funding çerçeveleri çağırandan | **kapandı** (`31da614`) |
    | KS D-B2 1d serisi tek seri değil | **kapandı** (`31da614`) |
    | KS D-B3 sinyal barı varlığı | **kapandı** (`31da614`) |
    | KS D-B4 onay koşusu | kısmen: onaysız C1/C2 kapandı; hipotez eşleşmesi açık, **dokunur** |
    | KS D-B5 UTC dışı saat dilimi | doğrulandı, **kapandı** (`31da614`) |
    | Sızıntı: ±inf funding toplamı | **kapandı** (`31da614`) |
    | KS D-C1 `pozisyon_fundingi` taramada yasak | açık; hayır |
    | KS D-C2 kayıt taraması eksik | kısmen (veri yolu eklendi); hayır |
    | KS D-C3 `_kayitlar` önbelleği | açık, şüpheli; hayır |
    | KS D-C4 modül açıklaması | **kapandı** (`31da614`) |
    | KS D-C5 onaylı pozisyon kimliği | **kapandı** (`31da614`) |
    | KS D-C6 imza testleri | j kapandı; k kurulamıyor (yukarıda) |

    **Doğrulama.** Tam denetim (`3e83805`, `--eski-evren`) ve A1 (`480dc48`) temiz ağaçta. Veri CSV'leri önceki
    çıktılarla bayt düzeyinde aynı; yalnızca ortam kayıtları farklı (`karsilastirma_ks2_{calistir,a1}_tam.csv`).

    **Tur sonu ajan bulguları (düzeltilmedi; yukarıdakilerden sonra geldi).** Denetçinin bulguları "KS2"
    önekiyle. Denetçinin cevabı: getiri girdisi veren yollarda çağırandan gelen bir olgu kalmadı. Kalan
    açıklar sinyal değerleri ve t seçimi (bilinen, Rev.11), onay koşusunun hipotezi ve yapılandırması,
    ikincil ufuk.
    - **KS2 D-B1: onay koşusunun hipotezi eşleştirilmiyor** (KS D-B4'ün açık kısmı, genişletilmiş).
      - Kapı ve `split.kume_erisimi` yalnızca koşunun kümesine bakıyor. `onay_kosusu("H2", "C1")` içinde
        `hipotez="H1"` ile C1 pozisyonu onaylanıyor.
      - Koşunun hipotez adı yalnızca düzenli ifadeyle denetleniyor, `config` hipotezleriyle değil. "h2"
        ya da "H2_b" ile açılan koşu, tek atış anahtarını (`("H2", "C1")`) atlatıyor.
      - Sızıntı testçisi xfail(strict) ile doğruladı (`test_tur_saldirilari_m`, `5a6545f`).
      - **Dokunur** (F3).
    - **KS2 D-B2: onay koşusu seçilen yapılandırmaya bağlı değil.**
      - Tek bir `onay_kosusu` içinde 9 yapılandırmanın hepsi koşulabilir.
      - `KILIT.md` hiçbir kodda okunmuyor ve kilitli dosya listesinde değil (ön-kayıt §8.5, §9).
      - **Dokunur** (F3).
    - **KS2 D-B3: ikincil ufukta olay kimliği tanımsız.**
      - Kapı her ufku bağımsız karara bağlıyor. Birincil ufukta küme sınırı ya da funding tamlığı yüzünden
        oluşmayan bir olay ikincil ufukta onaylanıyor.
      - Ön-kayıt §3 "hiç oluşmaz" ile "İkincil ufuklar … kendi ufuk uzunluklarıyla" birlikte okununca
        tanımsız kalıyor.
      - **Dokunur**; Rev.11 listesinde yok.
    - **KS2 D-B4: pozisyon funding'inde NaN oran.**
      - NaN oran pozisyonu `FundingTamDegil` ile sessizce düşürüyor. Ön-kayıt §4'ün beş maddesi oranı
        okumuyor; bu bir ayrışma.
      - Bu kural hiçbir listede yok; Rev.10 D-C5 yalnızca H2 sinyal penceresi içindi. §14.22'deki "Rev.10
        D-C5, Rev.11'de" etiketi yanlış.
      - Sonlu olmayan değerlere beş farklı sonuç veriliyor. Aynı pencerede +inf ve −inf toplamı NaN yapıyor
        ve bu da `FundingTamDegil` ile sessizce düşüyor. Sızıntı testçisi bunu savuşturulmuş saydı.
      - **Dokunur.**
    - **KS2 D-B5: §14.21'in özeti ve Rev.11 listesi eksik; bazı satırlar bayat.**
      - Özet listesinde yok: Rev.9 D-C5 (0 fiyat), A6, F1K2 D-C4, KS D-B4.
      - Rev.11 listesinde yok: H1'de izleme sürerken yeni pump barı, H3 "ilk gün", KS2 D-B3, KS2 D-B4.
      - §14.21'deki F1K2 D-C2 satırı ve "Bilinen sınır" paragrafı turu 2'den sonra bayat.
    - **KS2 D-C1:** `OlayOlusmaz` bir `ValueError` alt sınıfı.
      - F2'de `except ValueError` yazılırsa `_sonlu`, dönem dışı ve grup hataları sessiz rede döner.
      - `DonemDisiSinyal` açıklaması kapıdaki sırayla çelişiyor.
      - K2 havuzu kurulurken dönem üyeliğinin kapı dışında süzülmesi gerekiyor; ön-kayıt §4 rev.9 ile
        gerilim var.
    - **KS2 D-C2:** gerçek `_veri_yukle` hiçbir testte kapı üzerinden çalışmıyor. `onay=` hesabı,
      `donem_sonrasi_kayitlari_at` ve boş çerçeve davranışı sınanmıyor.
    - **KS2 D-C3:** veri yolu yeniden atanabilir modül özniteliklerine bağlı (`klines.mumlari_yukle`,
      `funding.funding_yukle`, `config.KESIF_SONU`); taramada yok (kararlı atlatma).
    - **KS2 D-C4:** `mae` yeniden yüklenen seriyi karara karşı doğrulamıyor. `pozisyon_fundingi`
      karşılaştırıyor.
    - **KS2 D-C5 (şüpheli):** tolerans içindeki ızgara dışı t ham hâliyle saklanıyor.
    - **KS2 D-C6:** `test_tur_saldirilari_k` ters sıra testinin adı yanıltıcı. "Kurulamıyor" gerekçesi
      fazla kesin: `config` ya da `split.kume_tanimi` yamalanarak kurulabilir (KS2 D-C3).
    - **KS2 D-C7:** UTC denetimi `GMT`, `Africa/Abidjan` ve kışın `Europe/London`'ı da reddediyor. Açık
      hata veriyor; zararsız.
    - Denetçiye göre 1d serisinin yalnızca pozisyonun döneminden türetilmesi "Bu seri tektir" ile aynı
      sonucu veriyor. Bu eşitlik, küme sınırlarının UTC gün sınırına denk gelmesine dayanıyor.

    **Sızıntı testçisi** (`test_tur_saldirilari_m`, `5a6545f`, yalnızca yeni dosya): 19 test.
    - 18 geçti, 1 xfail(strict): yukarıdaki KS2 D-B1.
    - **Savuşturulanlar:**
      - yinelenen, sırasız ya da tz'siz 4h ve funding zamanları;
      - NaT `close_time`;
      - string ya da None fiyat;
      - pencere dışındaki inf (giriş anında ve pencere sonrasında);
      - string oran;
      - pytz, zoneinfo ve dateutil UTC eşdeğerleri;
      - kışın `Europe/London`'ın reddi;
      - seride olup dönem dışında kalan sinyal.
    - **Ana oturum düzeltmesi:** tz'siz veri testlerinde beklenen hata sınıfı `(ZamanDizisiHatasi,
      TypeError)` olarak genişletildi. Kapı kümeye kesimde `TypeError` veriyor; iddia (açık hata) aynı.

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
- 2026-09-21: §14.8 açıldı (D-A1): ön-kayıttaki 1d türetme, dönem ve dönem sonu çıkışı
  cümleleri, bugünkü kodun 1d barını dönem sınırlarında hangi 4 saatlik barlardan
  kurduğu, sayılar (`gunluk_sinirlar_tam.csv`) ve aday kuralın sayımı. §14.7'deki 1 günlük
  tablo 4 saatlik tabloyla aynı kayıt tabanından yeniden sayıldı (D-A4; "dışarıda kalacak
  kayıt" 203 (68) → 34 (29), "kapanışta ödeme" 67 → 2; tamlık sütunları değişmedi) ve iki
  tabloya aday kural sütunu eklendi.
- 2026-09-21: §14.1 yeniden yazıldı (D-A3, D-B2): ön-kayıttaki 14, 131 ve 38 cümleleri
  aynen alıntılandı; üç sayı harfiyen tanımla betikten (18, 145 ve "yıllarca" için 45 /
  15, 57); 13 ile 18 farkı cümleye göre çözüldü (18) ve §6 buna göre düzeltildi; 57'nin
  tanımı kapanış referansıyla yazıldı.
- 2026-09-21: Betik dışı sayı cümleleri (D-B1): "betik dışı sayılar üçtür" sayımı
  kaldırıldı; §7, §11, §12'deki "değişmedi / önceki raporla aynı" cümleleri
  `karsilastir.py` çıktısına bağlandı; §1, §3, §9, §10, §14.5'teki eski ölçümlerle
  karşılaştırmalar ve 18/5 işaret sayımı betik dışı diye işaretlendi. §14.7'ye A1
  betiğindeki çıkış kuralı kopyasının akıbeti yazıldı (D-B3).
- 2026-09-21: §14.7'deki "yalnızca bu iki sütun değişti" cümlesi `karsilastir.py`'nin yeni
  `degisen_sutunlar` sütununa (`karsilastirma_02effeb_tam.csv`) bağlandı; satırların 1 günlük
  olduğu kısmı betik dışı diye işaretlendi (D-B3).
- 2026-09-21: **Bilerek güncellenen mevcut testler** (bu ve önceki tur; yalnızca test
  ekleyen commit'ler listede yok):
  - `dd55012` — `tests/test_a1_d_kurali.py`: `test_1d_cikisinda_disarida_kalan_gun_sonuna_kadar_sayar`
    → `test_1d_cikisinda_disarida_kalan_4h_ile_ayni_tabandan`; 1 günlük `disarida_kalan`
    beklentisi **3 → 1**. Gerekçe: D-A4 kararıyla sayım veri katmanının kayıt tabanına
    geçti; 16:00 ve 20:00 kayıtlarını veri katmanı zaten atar. Eski test, bulgunun
    eleştirdiği davranışı sabitliyordu.
  - `dd55012` — `tests/test_tur_saldirilari_c.py` (sızıntı testçisi):
    `test_1d_disarida_kalan_gun_kapanisi_siniri` kurgusu değişti; dönem bitişi 08:00 yerine
    20:00. Gerekçe: aynı D-A4 değişikliğiyle 08:00 bitişli dönemde gün kapanışı veri
    katmanının sınırı dışında kalır ve test tolerans sınırını ölçemezdi. Beklenen sayılar
    (1, 1, 0) değişmedi.
  - `d19a013` — `tests/test_tur_saldirilari_c.py`: `test_son_odeme_aralik_saat_donem_sonrasi_kaydi_almaz`
    kurgu hatası (tz-aware uç ile `tz="UTC"` birlikte); ölçülen şey değişmedi. Kullanıcı
    talimatıyla.
  - `d6fad05` — yalnızca açıklama: `tests/test_tur_saldirilari_b.py` gerileme testinin
    açıklaması (D-C2) ve `tests/test_a1_deger_yolu_yok.py` modül açıklaması (D-C1).
  - `25d5bb5` — `tests/test_tur_saldirilari_d.py` (sızıntı testçisi):
    `test_csv_yaz_gercek_es_zamanli_yazmalar_dosyayi_bozmaz` `xfail(strict=True)` ile
    işaretlendi; test gövdesi değişmedi. Gerekçe: eşzamanlı koşu desteklenmez, koruma koşu
    kilidindedir (`calistir.kosu_kilidi`). Kullanıcı talimatıyla.
- 2026-09-21: §14.10 açıldı (D-A2): funding sınıflaması D penceresiyle belirlenseydi sınıfı
  değişecek dönem sayısı dönem sonu türüne göre; yalnızca BNXUSDT dönem 0 (uzun boşluk).
- 2026-09-21: `4110f43` — `tests/test_tur_saldirilari_d.py`: eşzamanlı `csv_yaz` testinin
  işareti `xfail(strict=True)` → `xfail(strict=False)`; test gövdesi değişmedi. Gerekçe:
  eşzamanlı koşu koşu kilidiyle desteklenmiyor ve sonuç platforma bağlı (Windows'ta
  PermissionError, POSIX'te `os.replace` atomik; strict POSIX'te XPASS ile takımı kırardı;
  denetçi bulgusu D-B2).
- 2026-09-22 (Rev.8 uygulaması, madde 1: rev.8 §4 "Zaman toleransı"). Tek tanım
  `pencere.ayni_an` (fark < 1 dk) ve türevleri; `funding`, `pencere`, `a1_olcumu`,
  `calistir` bunları kullanır. **Bilerek güncellenen mevcut testler:**
  - `tests/test_rev6_saldirilari.py::test_giris_tarafi_tam_60_saniyede_dahil_59_999_de_haric`:
    kurgudaki ilk kayıt 00:00 → 00:01. Gerekçe: 00:00 → 08:01 boşluğu aralıktan tam 1 dk
    uzun; rev.8'de tam 1 dk aynı an değildir ve bu boşluk eksik ödemedir, test pencere
    kenarını ölçemezdi. Ölçülen kenar ve beklenen değerler değişmedi.
  - `tests/test_tur_saldirilari_d.py::test_teslimden_sonra_funding_kayit_1dk_tolerans_siniri`:
    beklenti 1 → 2. Gerekçe: deliveryDate'ten tam 1 dk sonraki kayıt rev.8'de "sonra"dır.
  - `tests/test_tur_saldirilari_e.py::test_funding_var_d_penceresi_uclari[z0]`: dönem
    başından tam 1 dk önceki kayıt için beklenti True → False. Gerekçe: rev.8 §2
    "Funding'i bulunmayan dönemler" (toleranslar §4 "Zaman toleransı"na göre).
- 2026-09-22 (Rev.8 uygulaması, madde 2: rev.8 §2 "Listeleme dönemi" B/K, §6 "Dönem
  üyeliği"). K = B + 4 saat yalnızca `pencere.donem_kapanisi`'ndan (`Donem.kapanis`);
  tek yüklem `pencere.donem_ici_mi` (`eligibility.uygun_mu` ve `pozisyon_plani`).
  **Bilerek güncellenen mevcut test:** `tests/test_veri_denetimi_saldirilari.py::test_teslim_son_bar_icinde_tam_sinirlar`:
  K'dan 1 ms önceki teslim True → False, B'den 1 ms önceki teslim False → True
  (rev.8 §4 "Zaman toleransı": 1 dakikadan küçük fark aynı an); tam 1 dk kenarları için
  iki durum eklendi.
- 2026-09-22 (Rev.8 uygulaması, madde 3: rev.8 §2 "1 günlük barlar", §2 Veri
  boşlukları). `klines.gunluge_cevir(dort_saatlik, *, donemler)` tek 1d yolu: yalnızca
  dönem içi, 00/04/08/12/16/20 UTC hizalı altı 4h bardan, dönem dönem. `donemler`
  zorunlu. `ham_mumlari_yukle(s, "1d")` commit edilmiş dönemleri kullanır. Başka 1d
  kaynağı: `klines.birincil_gunluk_indir` (Binance'in kendi 1d dosyaları; yalnızca F1
  çapraz doğrulaması). Yalnızca gün sayan karşılaştırmalar: `calistir.eski_kural_gunleri`,
  `hiza_olcumu`. **Bilerek güncellenen mevcut testler:**
  - `gunluge_cevir(...)` çağrısı olan testlere `donemler=` eklendi (API değişikliği;
    beklenen değerler aynı): `test_klines.py` (6 çağrı), `test_klines_tekrar.py`,
    `test_kume_korumasi.py`, `test_f1_kapanis_saldirilari.py`,
    `test_tamlik_sayimi_deger_icermez.py`, `test_tur_saldirilari_d.py` (2),
    `test_kume_geriye_bakis.py` (gerçek sembolün commit edilmiş dönemleriyle).
  - `test_hiza_olcumu.py::test_alti_satirli_hizasiz_gun_sayilir_ve_gunluge_cevir_onu_tam_sayar`:
    beklenti 1 → 0 (hizasız bar içeren gün artık oluşmaz; D-C5'in eski davranışı).
  - `test_gunluk_sinirlar.py`: `test_uzlasma_gununun_dolgu_barlari_son_gune_girer` ve
    `test_ic_sinir_ikinci_donemin_ilk_gunu_dolgu_barlari_icerir` kısmi günlerin 1d
    serisinde olduğunu (D-A1) sabitliyordu; rev.8'de kısmi ilk ve son günler seride yok
    (son gün 04-14 → 04-13, dönem dışı bar 3 → 0; ilk gün 04-20 → 04-21, 2 → 0).
- 2026-09-22 (Rev.8 uygulaması, madde 4: rev.8 §4 "Fiyat okuma tabanı", "Dönem sonu ve
  çıkış", delist cümlesi, "Olayın kümede oluşma ölçütü"; §2 "Ufuk", "İleri kaymanın
  ölçüsü"). `pencere.cikis_bari` ve `pozisyon_plani` yeniden yazıldı: fiyat her ızgarada
  dönem içi 4h barlardan; giriş anı t'nin kapanışı; T = giriş + h × adım; önce T > K
  (dönem sonu, çıkış anı K), sonra kapanışı T olan bar (olağan), sonra açılışı T'ye eşit ya
  da sonra olan ilk bar (ileri kayma, sınır dahil). Her çıkış bir tür taşır
  (`CikisSonucu.tur`: olağan / ileri kayma / dönem sonu), reddedilen her olay bir gerekçe
  (`OlayOlusmaz.gerekce`). Dönem sınırları zorunlu; "seri sonu" kırpması kaldırıldı (delist
  bir dönem sonudur); T'ye dayalı küme ön elemesi (`pencere.ufuk_kumeye_sigar_mi`,
  `split.ufuk_kumeye_sigar_mi`) kaldırıldı, küme ölçütü gerçek çıkış anına uygulanır. Bar
  aramaları zaman toleransıyla (`pencere.ayni_andaki_bar`). Rev.8'in sessiz kaldığı bir sıra
  korundu: ileri kaymada küme ölçütü ileri kayma sınırından önce uygulanır (rev.4'ten beri
  mevcut test kararı). **Bilerek güncellenen mevcut testler** (davranışı rev.8 değiştirdi;
  senaryolar korundu):
  - `test_pozisyon_plani.py`: yardımcı dönemi serinin başı/sonu olarak verir (dönem
    zorunlu); ileri kayma testinde hedef bar T − 4 saat (`cikis_hedefi` artık T verir);
    küme son barı testinde 1d çıkış barı 4h bar; parametre testi dönem sınırlarını içerir;
    ön eleme özellik testi, küme kararının gerçek çıkış anına göre verildiğini doğrulayan
    özellik testiyle değiştirildi (dönem sonu senaryosunda T küme dışında, K küme içinde
    olan olay oluşur).
  - `test_pencere.py`: `cikis_bari` çağrılarına `donem_bitis` (serinin son barı);
    `seri_sonu` → `donem_sonu`.
  - `test_ileri_kayma_siniri.py`: hedef bar T − 4 saat; 1d testi 4h seriyle; boşluğun
    içindeki B (rev.8'de B her zaman mevcut bir bar) boşluktan önceki son bara alındı;
    delist `seri_sonu` → `donem_sonu`.
  - `test_kume_siniri.py`: `split.ufuk_kumeye_sigar_mi` soruları gerçek plana (`_sigar`);
    `cikis_bari` dönem bitişi zorunlu; bar olmayan B'ler gerçek bara; `seri_sonu` →
    `donem_sonu`; "kümeye sığan ufuk" testi bir bar erken (son barın kapanışı küme dışı).
  - `test_pozisyon_fundingi.py`, `test_rev6_saldirilari.py`, `test_funding_aralik_gecisi.py`:
    yardımcılar 4h seri ve dönem sınırlarıyla; elle kurulan `CikisSonucu` rev.8 alanlarıyla;
    `cikis_ani` ızgara adımı almaz (1d'de de 4h bar kapanışı); B gerçek bar; `cikis_bari`
    küme ölçütünü de uygular; hedef bar T − 4 saat; 1d ileri kayma 4h seriyle.
  - `test_f1_kapanis_saldirilari.py` (2 test): `donem_bitis=None` yerine kümeden sonra süren
    gerçek bir B.
  - `test_karantina_kaldirildi.py` (2 test): `KIRPMA_NEDENLERI` → `CIKIS_TURLERI`;
    `CikisSonucu` rev.8 alanları.
  - `test_gunluk_sinirlar.py::test_son_gun_gercek_cikis_bariyla_ayni`: 1d dönem sonu çıkışı
    artık B'deki 4h barın kapanışı (K); `son_gun` eşitliği yerine bu.
- 2026-09-22 (Rev.8 uygulaması, madde 6: rev.8 §4 "Funding ödemesinin sınırları",
  "Dönem sonu istisnası", "Funding aralığı geçişleri"; §2 "Funding'i bulunmayan
  dönemler", "Gerçek işlem sonrası funding kayıtları"). `funding.funding_tamlik_ayrintisi`
  pozisyon tamlığının tek (vektörel) uygulaması: kayıt var, aralık geçerli, başlangıç
  boşluğu (ilk kaydın aralığı + tolerans), ardışık boşluk, son ödeme (dönem sonunda B'ye
  göre). `pozisyon_fundingi` giriş anındaki ödemeyi hariç, çıkış anındakini dahil tutar;
  dönem sonunda pencere B'de (dahil) kapanır. `donemde_funding_var` [dönem başı, B];
  `donem_sonrasi_kayitlari_at` K'dan sonrasını atar. `funding_ortalamasi` (H2 sinyal
  penceresi) değişmedi: rev.8'in başlangıç boşluğu cümlesi "giriş anı"ndan söz eder; sinyal
  penceresine uygulanıp uygulanmayacağı rapora belirsizlik olarak yazıldı.
  **Bilerek güncellenen mevcut testler:**
  - `test_evren_tablosu.py::test_uzlasma_sonrasi_funding_donemi_funding_li_yapmaz` ve
    `test_funding_donem.py::test_yalnizca_uzlasma_sonrasi_kaydi_olan_donem_funding_siz`:
    yalnızca K'da kaydı olan dönem artık funding'siz (sayım penceresi B'de biter); B'deki
    kayıt için durum eklendi.
  - `test_pozisyon_fundingi.py`: kaydı olmayan kısa pozisyon 0.0 → NaN ("Penceresinde hiç
    funding kaydı bulunmayan pozisyonun funding'i tam değildir"); dönem sonu toplamı 6 → 5
    ödeme (K'daki ödeme istisnayla hariç); küme öncesi kayıt testinde funding artık tam
    (başlangıç kuralı önceki kaydı okumaz; küme öncesi kaydın okunmadığı bozma ile
    doğrulanır); küme sonrası bozma testinde NaN = NaN eşitliği.
  - `test_rev6_saldirilari.py` (giriş ve çıkış kenarı testleri): kenardaki ödeme hariç
    kalınca pencerede kayıt kalmıyor; 0.0 → NaN.
  - `test_funding_aralik_gecisi.py` (`test_eksiksiz_gecis_nan_uretmez`,
    `test_gercek_gecis_nan_uretmez`): rev.8 başlangıç kuralının tetiklendiği girişlerde
    (penceredeki ilk ödeme geçiş kaydı ve kısa aralığı taşıyor) NaN, diğer bütün girişlerde
    değer beklenir. Rev.7'de hepsi değer veriyordu; kural önceki kaydı okumadığı için bu
    pozisyonlar düşer (etki sayımı madde 9'da).
  - `test_gunluk_sinirlar.py` (2 test) ve `test_tur_saldirilari_e.py` (1 test): A1'in
    `funding_var_mevcut` sütunu gerçek kodu çağırır; gerçek kod artık B penceresini
    kullandığı için K'daki kayıt için False.
- 2026-09-22 (Rev.8 uygulaması, madde 7: rev.8 §4 "Olayın kümede oluşma ölçütü"). Tek
  karar noktası `data/pozisyon.py:olay_karari`: sinyal penceresi tamlığı, giriş barı,
  çıkış ve ileri kayma sınırı, gerçek çıkış anı + tolerans ≤ küme sonu, funding tamlığı.
  Çıktı imzalı `OnaylanmisPozisyon` (plan, P0, P1, funding toplamı); brüt ve net girdisi
  (`pozisyon_fiyatlari`) yalnızca onu kabul eder. **Bilerek güncellenen mevcut testler:**
  `tests/tarama_yardimcisi.py` kapı dışı deseni `pozisyon_plani`, `pozisyon_fundingi`,
  `pozisyon_funding_tam_mi`, `funding_tamlik_ayrintisi` ve `OnaylanmisPozisyon` kurulumunu
  da yakalar; `test_pozisyon_plani.py` tarama testinde "temiz" örnek `olay_karari` oldu
  (rev.7'de tek kapı `pozisyon_plani` idi) ve üç yeni ihlal örneği eklendi.
- 2026-09-22 (Rev.8 uygulaması, madde 5: rev.8 §4 "MAE"). `pozisyon.mae`: `max(H, P1) / P0 − 1`;
  H, açılışı giriş anından önce olmayan ve kapanışı çıkış anından sonra olmayan dönem içi 4h
  barların en yüksek high değeri. Yalnızca `OnaylanmisPozisyon` alır; hiçbir veride
  çalıştırılmadı, sonuç raporlanmadı. Mevcut test değişmedi.
- 2026-09-22 (Rev.8 uygulaması, madde 6 düzeltmesi: rev.8 §4 "Funding aralığı geçişleri").
  `funding_tamlik_ayrintisi`, giriş anı son funding kaydından sonra olduğunda (penceresinde
  kayıt yok) indeks taşmasıyla çöküyordu; rev.8 gereği "tam değil" döner. Madde 8 sırasında
  bulundu. Yeni test: `test_rev8_funding.py::test_giris_son_kayittan_sonraysa_tam_degil_cokmez`.
  Mevcut test değişmedi.
- 2026-09-22 (Rev.8 uygulaması, madde 8: denetçi bulguları D-B3, D-B4; rev.8 §4 "Dönem sonu
  istisnası", "Dönem sonu ve çıkış"). A1 ölçümündeki çıkış ve funding kuralı kopyası
  (`donem_sonu_cikisi`, elle kurulan tamlık pencereleri, `_odemeler_tam_mi` çağrıları)
  silindi. Temsili pozisyon gerçek `pencere.pozisyon_plani` ile kurulur (`temsili_plan`),
  tamlık gerçek `funding.funding_tamlik_ayrintisi` ile, funding sınıfı gerçek
  `funding.donemde_funding_var` ile ölçülür. Birincil ufuk `config.BIRINCIL_UFUK`'a taşındı
  (ön-kayıt §4 tablosu: 18 bar, 14 gün). Sütunlar: `tamlik_mevcut`, `tamlik_d`,
  `tamlik_aday`, `giris_aday`, `cikis_ani_aday`, `funding_var_mevcut`, `funding_var_d`
  yerine `temsili_sinyal`, `giris`, `cikis_turu`, `cikis_ani`, `ret_gerekcesi`, beş tamlık
  koşulu, `tamlik`, `funding_var` (ve `main`'de karşılaştırma için evren tablosundaki
  `funding_yok_evren`). Temsili giriş: 4h ızgarada B − 24 saat (dönem başından sonraki ilk
  bardan önce olamaz), 1d ızgarada B'yi içeren günün 00:00 barı. Küme toplam dönem;
  veri sonu dönemleri küme ölçütüyle reddedilir. Yeni test: `tests/test_a1_gercek_kod.py`
  (kaynak taraması, gerçek fonksiyonlara casus, config parametreleri).
  **Bilerek güncellenen mevcut testler** (hepsi rev.7'deki kopyayı ya da rev.8'in kaldırdığı
  "mevcut" kuralı sabitliyordu; kopya silindiği için aynı sınır gerçek kod yolunda sınanır):
  - `test_a1_d_kurali.py`: `tamlik_mevcut`/`tamlik_d` → `tamlik` ve koşul sütunları; iki
    kuralı karşılaştıran test adları tek kurala indi. `donem_sonu_cikisi` testleri
    `temsili_plan` testlerine çevrildi; 1d çıkış anı ertesi gün 00:00 → K (rev.8: 1d kısmi
    son günde de çıkış B barının kapanışı), bu yüzden 1d'de K'daki kayıt artık kapanışta
    ödeme sayılır.
  - `test_gunluk_sinirlar.py`: aday kural testleri gerçek plana çevrildi (1d temsili giriş
    rev.8 tanımıyla t kapanışı: 04-14 00:00; rev.7 sayımında `giris_aday` 04-13 00:00 idi).
    4h tamlık testi parametreli oldu, beklenen değer her son kayıt için açık yazıldı.
    Funding sınıfı testleri `funding_var` sütununa geçti.
  - `test_tamlik_sayimi_deger_icermez.py`: kaynak taraması `donem_sonu_cikisi` yerine
    `temsili_plan`'ı tarar.
  - `test_tur_saldirilari_b.py` (2 test): karşılaştırılan anahtarlar `tamlik` ve beş koşul.
  - `test_tur_saldirilari_c.py`: `donem_sonu_cikisi` testleri `temsili_plan` testleri oldu;
    1d beklentileri rev.8'e göre (çıkış barı B, çıkış anı K). Temsili girişin dönem başına
    sabitlenmesi testinde kurgu değişti: rev.8'de giriş t kapanışıdır ve dönem sonu penceresi
    (giriş, B] aralığıdır; iki barlık dönemde giriş B'ye düşer, pencere boş kalır ve test
    sızıntıyı ölçemezdi. Dört barlık dönem kullanıldı; ölçtüğü şey (dönem başından önceki
    kaydın sonucu değiştirmemesi) değişmedi.
  - `test_tur_saldirilari_d.py`: tek barlık dönemde temsili giriş rev.8'de oluşmaz (sinyal
    dönem dışı ya da giriş barı yok); test plan oluşmadığını ve dönem dışı girişin yazılmadığını
    sınar, 4h ızgara da eklendi.
  - `test_tur_saldirilari_e.py` (3 test): `funding_var_d`/`funding_var_mevcut` → `funding_var`.
- 2026-09-22 (Rev.8 uygulaması, süreç notu). Kilit listesi değişikliği
  (exchange_info_anlik.json), Rev.8'i uygulamaya çalışıp hiçbir şey yazmadan duran kilit
  oturumunun içinde yapıldı. Planda ayrı oturum öngörülmüştü. O oturumda fiilen tek yazma
  işi yapıldığı için bütünlük etkisi yoktur; sapma kayda geçirilmiştir.
- 2026-09-22 (Rev.8 uygulaması, madde 2 düzeltmesi: rev.8 §6 "Dönem üyeliği").
  `yillik_kapsama` 1d uygunluğunu her 4h anında soruyordu; madde 2'de `donem_ici_mi`
  gün ortası 1d zamanını reddettiği için temiz ağaçtaki tam denetim koşusu (73ae679) tablo
  aşamasında `ValueError` ile, hiçbir çıktı yazmadan durdu. Testler bu yolu kapsamıyordu.
  1d uygunluğu artık yalnızca gün açılışında sorulur (1d barın zamanı). Etkisi §10 tablosunun
  `esik_2M_gecen` sütununda karşılaştırmayla raporlanır. Yeni test:
  `tests/test_yillik_kapsama_1d.py` (eski sürümde hata veriyor). Mevcut test değişmedi.
- 2026-09-22 (Rev.9 hazırlığı). §14.13 eklendi: F1 kapanış ölçütü, araştırma tarafının
  metniyle aynen. Kod ve ön-kayıt değişmedi.
- 2026-09-22 (Rev.9 hazırlığı, ikinci tur). §14.14 eklendi: 2026-06-24 04:00 funding
  boşluğu bilinen veri boşluğu olarak (kaynak borsa, 398 sembol, kuralların işleyişi,
  yalnızca sayı). Kod ve ön-kayıt değişmedi.
- 2026-09-23 (Rev.9 uygulaması). §14.15 eklendi. Kod: §4 "Funding tamlığı" veri katmanında
  (`0ff7510`, çapa/zincir/ilk çift/son; bayraklar); T ≥ K (`760ecd7`); uygunluk tek karar
  noktasında (`642def8`); 4h girdi denetimi (`3dbda4a`); dönem `None` taraması (`187bb52`);
  SETTLED taraması (`fc94497`, düzeltme `45f2e1d`: o commit'te yeni tarama testi kırıktı, config
  sabiti desenden çıkarıldı); F2 bayrakları `OnaylanmisPozisyon`'da (`7bd1eff`); doğrulama betiği
  `rev9_uygulama.py` (`cf71cf8`, çıktılar `736846b`); ölçüm betikleri gerçek koda bağlandı
  (`ce89096`). H2 funding penceresi (Rev.9 madde d) belirsizlik nedeniyle uygulanmadı (§14.15).
  **Bilerek güncellenen mevcut testler** (hepsi Rev.9'un açıkça değiştirdiği davranışı
  sabitliyordu; ayrıntı commit mesajlarında):
  - Funding tamlığı (Rev.9 §4: çapa zorunlu; "hiç kayıt yok" ve başlangıç boşluğu cümleleri
    kaldırıldı; son maddesinde eşitlik yeterli; koşul adları `capa_var`/`zincir_tam`):
    `test_rev8_funding` (5 test), `test_pozisyon_fundingi` (3), `test_rev6_saldirilari` (2),
    `test_funding_aralik_gecisi` (2), `test_tur_saldirilari_f` (12), `test_tur_saldirilari_b`
    (2), `test_a1_d_kurali` (3), `test_a1_gercek_kod` (1 casus imzası). Test verisine çapa kaydı
    eklenen yerlerde ölçülen kenar değişmedi.
  - Rev.8 kehaneti donmuş kopyaya (`rev8_tamlik`) yönlendirildi: `test_rev8_etki`,
    `test_rev9_hazirlik`, `test_rev9_son_adim`, `test_rev9_son_hal`, `test_rev9_tahmin_yok`.
  - T ≥ K (Rev.9 §4 "Dönem sonu ve çıkış"): `test_rev8_cikis` (2), `test_tur_saldirilari_f` (4):
    T = K ve K ile aynı an sayılan T artık dönem sonu.
  - Uygunluk karar noktasında (Rev.9 §4 "Olayın kümede oluşma ölçütü"): `test_tek_karar_noktasi`,
    `test_rev8_mae`, `test_tur_saldirilari_f` (4 çağrı): uygun 1d seri ve ön-kayıt eşikleri
    verildi, dönem başı mum serisinden 60 gün önce.
  Silinen, gevşetilen ya da xfail'e alınan test yok. Yeni test dosyaları:
  `test_rev9_funding_tamligi`, `test_rev9_t_esit_k`, `test_rev9_uygunluk_kapisi`,
  `test_rev9_fiyat_tabani_4h`, `test_rev9_donem_none`, `test_rev9_settled_taramasi`,
  `test_rev9_f2_bayraklari`, `test_rev9_tek_tamlik`; yardımcı `uygunluk_yardimcisi`.
- 2026-09-24 (Rev.10 hazırlığı). §14.16 eklendi. Ölçüm `rev10_hazirlik.py` (`cab0176`, çıktılar
  `97c6070`). Kod: D-C6 kalan kısım (`7279b93`), tek satırlık çerçeve ve bool sinyal değeri
  (`2d9b8e6`), F2 ritim sınıfı (`602034a`).
  **Güncellenen mevcut testler:**
  - 12 dosyada 86 `donem_*=None` çağrısı → toplam dönem sınırları (`TOPLAM_DONEM_BASI`,
    `TOPLAM_DONEM_B`). Beklenen sonucu değişen test yok.
  - `test_tur_saldirilari_g.py::test_tek_barlik_1d_cerceve_4h_izgara_denetimini_atlatir`:
    `xfail(strict)` işareti kaldırıldı. Bulgu kapandı; aynı beklentiyle normal test oldu.
  Yeni test dosyaları: `test_rev10_hazirlik`, `test_rev10_donem_none`, `test_rev10_girdi_denetimleri`,
  `test_rev10_ritim_sinifi`.
- 2026-09-24 (Rev.10 hazırlığı, son tur). §14.17 eklendi.
  - Ölçüm `rev10_son.py` (`d2e068f`, çıktılar `3b305fe`), yalnızca KEŞİF. Yeni test
    `test_rev10_son`.
  - §14.16'daki "iki ölçü de üst sınırdır" cümlesi düzeltildi (denetçi bulguları D-A1, D-A2).
  - Kod ve mevcut testler değişmedi.
- 2026-09-25 (Rev.10 uygulaması). §14.18 eklendi. Kod: `233db57`, `f9a144d`, `5c688fb`,
  `9952421`, `739eb50`. Ölçüm `rev10_uygulama.py` (`72c034b`). Doğrulama koşuları `9d1c243`,
  `2eac2c8`, `26c5de8`, `c4e8c8e`, `8bf2878`.
  **Güncellenen mevcut testler.** Hepsi Rev.10'un açıkça değiştirdiği davranışlar içindir.
  - Zorunlu `kume_bitis` (§4 "Funding sinyal penceresinin tamlığı": pencere kümede olmalı):
    `funding_ortalamasi` çağrılarına `kume_bitis=None` eklendi. 7 dosya (`f9a144d` commit mesajındaki
    "8 dosya" yanlıştır):
    - `test_funding_aralik_gecisi`
    - `test_funding_penceresi`
    - `test_f1_kapanis_saldirilari`
    - `test_karantina_kaldirildi`
    - `test_rev10_donem_none`
    - `test_tur_saldirilari_g`
    - `test_zaman_toleransi`

    Beklentiler değişmedi. `test_funding_penceresi` zorunluluk testine `kume_bitis` eklendi
    (sıkılaştırma).
  - Yarı açık pencere, H2 zincirinde ilk çift tabanı ve son koşulunun olmaması:
    - `test_funding_penceresi::test_kapanistan_sonraki_odeme_kullanilmaz` (eski adı
      `test_kapanis_anindaki_ve_sonraki_odeme_kullanilmaz`):
      - Kapanış anındaki kayıt artık ortalamaya giriyor.
      - Kapanıştan sonraki bütün kayıtlar hâlâ bozuluyor.
      - Kapanış kaydını bozmanın sonucu değiştirdiği ayrıca doğrulanıyor.
    - `test_funding_penceresi::test_penceredeki_bir_odeme_eksikse_nan`:
      - Pencere başındaki kaydın (04 08:00) eksikliği artık NaN değil.
      - Pencere sonundaki kaydın eksikliği görülmez.
      - İçerideki ilk ve ortadaki eksiklik NaN. Önceki üç durum dört durumla yazıldı.
    - `test_zaman_toleransi::test_funding_ortalamasi_kapanis_kenari`: kenar kapanış + fark ile
      deneniyor; aynı an girer, 1 dk ve sonrası okunmaz.
    - `test_zaman_toleransi::test_bosluk_kurali_kenari`: aynı kenar, kaldırılan `_odemeler_tam_mi`
      yerine `sinyal_penceresi_ayrintisi` ile.
  - Ufuk bağlama (§4 "Ufuk değerlerinin bağlanması"): kapıyı serbest ufukla çağıran 20 test on-kayıt
    değerine geçti. 4h'de 1, 2, 3 → 6; 1d'de 3 → 7. Dosyalar:
    - `test_rev9_f2_bayraklari`
    - `test_tur_saldirilari_f`
    - `test_tur_saldirilari_g`
    - `test_tur_saldirilari_h`
    - `test_rev10_ritim_sinifi`
    - `test_rev9_uygunluk_kapisi`

    `test_rev9_f2_bayraklari`'nda kısmi kuyruk ve eşitlik affı senaryoları 6 barlık ufukla aynı
    biçimde yeniden kuruldu; beklentiler değişmedi.
  - `xfail(strict)` işareti kaldırılanlar (bulgu kapandı, XPASS; aynı beklentiyle normal test):
    - `test_tur_saldirilari_h`: dönem sınırı 1 ns, NaT `close_time`, IntEnum.
    - `test_tur_saldirilari_g`: H2 ilk çift tabanı.

  Silinen, gevşetilen ya da xfail'e alınan test yok. Yeni test dosyaları:
  - `test_rev10_pencere_toleransi`
  - `test_rev10_h2_penceresi`
  - `test_rev10_ufuk_baglama`
  - `test_rev10_ritim_siniflari`
  - `test_rev10_kalan_bulgular`
  - `test_tur_saldirilari_i` (sızıntı testçisi)

  Yardımcı `tarama_yardimcisi.FUNDING_ORAN_DESENI` eklendi.
- 2026-09-25 (F1 kapanış turu). §14.19 eklendi. Kod: `78e51ba` (D-B3), `f6c2e1d` (D-B2), `a76f61c`
  (D-B1). Ölçüm `f1k_kume_sonu.py` (`6c32ec4`, çıktılar `7bde546`). Tam denetim `90260fc`, A1
  `907e73c`.
  **Güncellenen mevcut testler:**
  - `olay_karari` zorunlu `hipotez` (D-B2): 15 dosyada 21 çağrıya `hipotez` eklendi (4h "H1", 1d
    "H3", değişken ızgarada koşullu); beklenti değişmedi.
  - Tam sinyal kümesi (D-B1): 12 dosyada 16 çağrıdaki sabit `{"x": 1.0}` → `sinyal(hipotez)`
    (`tests/sinyal_yardimcisi.py`).
  - Özel sözlüklü 4 test (NaN, sayısal kabul; `test_rev10_girdi_denetimleri`, `test_rev10_kalan_bulgular`,
    `test_tek_karar_noktasi`, `test_tur_saldirilari_f`) tam kümede tek değer bozularak aynı beklentiyle
    yazıldı. Bool ve enum reddi testleri değişmedi (tip denetimi ad denetiminden önce).
  - `test_tur_saldirilari_i::test_1d_barda_...`: `saat=1` yerine on-kayıt değeri 24 ile aynı yapı;
    `saat` 1, 23 ve 25 artık ValueError (D-B3).

  Silinen, gevşetilen ya da xfail'e alınan test yok. Yeni: `test_f1k_h2_saat`,
  `test_f1k_hipotez_baglama`, `test_f1k_sinyal_kapisi`; yardımcı `sinyal_yardimcisi`.
- 2026-09-27 (F1 kapanış turu 2). §14.20 eklendi. Kod: `5b8f376` (sinyal eşlemi düz dict'e
  kopyalanır; sızıntı bulgusu), `0e5dc1c` (kapı küme sınırını `None` kabul etmez; Rev.10 D-C3).
  Tam denetim `bf19721`, A1 `f7d7120`. Kapının sinyal değerlerini kendisi hesaplaması ertelendi
  (araştırma tarafının kararı).
  **Güncellenen mevcut testler:**
  - `test_tur_saldirilari_j`: düzelen iki `Mapping` saldırısının `xfail(strict)` işareti kaldırıldı
    (XPASS); beklenti aynı.
  - Küme sınırı `None` (D-C3): **18 dosyada** 25 kapı çağrısı gerçek küme sınırına geçti
    (`tests/kume_yardimcisi.py`; `0e5dc1c` commit mesajındaki "17 dosya" yanlıştır). Beklentiler
    değişmedi.
  - Sentetik tarihi hiçbir kümeye düşmeyen 6 saldırı testinde tarih KEŞİF içine (2024) alındı:
    `test_tur_saldirilari_g` (1; 2033), `test_tur_saldirilari_h` (3; 2034, 2036, 2037),
    `test_tur_saldirilari_i` (2; 2038). Beklentiler değişmedi.
  - `test_rev9_uygunluk_kapisi::test_karar_noktasi_uygunlugu_tek_uygulamadan_cagirir`: beklenen
    `kume_baslangic` `None`'dan kapıya verilen gerçek KEŞİF başına (girdinin yankısı; iddia aynı).

  Silinen, gevşetilen ya da xfail'e alınan test yok. Yeni: `test_f1k2_kume_none` (16); yardımcı
  `kume_yardimcisi`.
- 2026-09-27 (kapı sertleştirme turu). §14.21 eklendi; §14.13 tek ölçütle yeniden yazıldı; §14.20
  tablosunun "Ağır" sütunu kaldırıldı; §14.19 ve §14.20'deki `pozisyon_fundingi` gerekçesi düzeltildi.
  Kod: `99238f4` (F1K2 D-B3), `3f789ea` (F1K2 D-B1), `10733c0` (F1K2 D-B2).
  **§14.13'ün önceki metni (2026-09-22), aynen:** "F1, ağır bulguların tamamı kapandığında kapanır.
  Getiri hesabını etkileyebilecek bulgular önemlerinden bağımsız olarak F2'den önce kapanır. Etkilemeyen
  orta ve küçük bulgular §14'te açık nokta olarak kayda geçer ve F2'yi engellemez. Bir bulgunun getiriyi
  etkileyip etkilemediği belirsizse etkilediği varsayılır. Karar: araştırma tarafı, 2026-09-22."
  **Güncellenen mevcut testler:**
  - `pozisyon_fundingi` → `_plan_fundingi`: 8 dosyada plan ile yapılan çağrılar (beklenti aynı);
    `test_tek_karar_noktasi` onaylı pozisyonla çağırıyor.
  - Kapı imzası (`kume`, `sembol`, `donem_no`): kapıyı çağıran bütün testler
    (`kume_yardimcisi.kume_adi`, `kapi_yardimcisi.donem`). Beklentiler aynı.
  - Gerçek küme sınırına taşınan fikstürler (beklenti aynı):
    - `test_tek_karar_noktasi` küme sonu (2025-08-30 sinyali);
    - `test_f1k_sinyal_kapisi::test_h2_penceresi_kume_basini_asarsa_olusmaz` (2020-01-01 04:00 sinyali).
  - **Beklentisi değişenler.** Serbest sınır artık verilemiyor; bunlar önceden `OlayOlusmaz` bekliyordu:
    - `test_tur_saldirilari_j::test_h2_kume_bitis_sinyal_barinin_kapanisindan_once_ise_olay_olusmaz` →
      TypeError;
    - `test_tur_saldirilari_k::test_ters_sirali_kume_siniri_olay_olusturmaz` → TypeError.

    Boş, bool ve NaT sınır testleri aynı değerleri `kume=` ile veriyor.
  - `test_tur_saldirilari_k`: karışım xfail(strict) normal teste döndü, adı
    `test_kesif_basi_ile_c2_sonu_karisimi_verilemez`. C1 artık grup denetiminde ValueError.
  - `test_f1k2_kume_none` yeni arayüzle yeniden yazıldı. `test_rev9_donem_none` kapı kısmı:
    sembol / `donem_no` `None`.
  - `tests/conftest.py`: otomatik `sentetik_donem_kayitlari` fikstürü.

  Silinen ya da gevşetilen test yok. Yeni: `test_ks_funding_onayli` (5), `test_ks_donem_kaydi` (15);
  yardımcı `kapi_yardimcisi`; `tarama_yardimcisi.KAYIT_DESENI`.
- 2026-09-28 (kapı sertleştirme turu 2). §14.22 eklendi; §14.21 tablosunda Rev.9 D-C5, A6 xfail'i ve
  F1K2 D-C4 "dokunur"a geçti; Rev.11 listesine 11–13 eklendi. Kod: `31da614`.
  **§14.13'e muafiyet cümlesi eklenmedi** (araştırma tarafının kararı). Gerekçe:
  - Bugünkü veride sıfır olan etki, kod ya da veri değiştiğinde sıfır kalmaz.
  - Muafiyet kaydı, kimse yeniden ölçmeden geçerli sayılır.
  - Emsal: `aralik_gecerli` (funding tamlığının geçerli aralık koşulu) bugün hiçbir pozisyonu elemediği
    hâlde Rev.10'da ön-kayda yazıldı.

  Denetçinin itirazındaki alternatif (ölçülmüş sıfır etki muafiyeti) bu yüzden reddedildi; Rev.9 D-C2 ve
  Rev.10 D-C1 "dokunur" kaldı.
  **Güncellenen mevcut testler:** §14.22 "Test güncellemeleri". Silinen ya da gevşetilen test yok. xfail'den
  çıkan: `test_tur_saldirilari_l` inf testi. Yeni: `test_ks2_kapi_veri` (39).
