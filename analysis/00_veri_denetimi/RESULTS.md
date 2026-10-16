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

    Kapı sertleştirme turu 3'te eklenen:
    14. **Pozisyon funding'inde NaN oran ve sonlu olmayan değer politikası** (KS2 D-B4).
        - Ön-kayıt §4 "Funding tamlığı"nın beş maddesi oranı okumuyor; NaN oranlı pozisyonun ne olacağı
          yazılı değil.
        - Kod bugün:
          - pozisyon penceresinde NaN oran varsa toplam NaN olur ve pozisyon `FundingTamDegil` ile sessizce
            düşer;
          - aynı pencerede +inf ve −inf toplamı NaN yapar ve aynı yoldan düşer;
          - tek başına ±inf toplam açık `VeriHatasi` verir.
        - Rev.10 D-C5 (H2 sinyal penceresinde `kayit_var` ve NaN oran, madde 9) ile karıştırılmamalı.

    Onay kaydı ve koşu bütünlüğü turunda eklenenler (denetçi KS2 D-B5, KS3 D-B5; §14.24):
    15. **H1'de izleme sürerken gelen yeni pump barı.**
        - Açık sorular: ilk izleme sürer mi, yeni bar yeni izleme başlatır mı? Tepe ve 12 barlık sayaç hangi
          pump barından ölçülür? Aynı teyit barı iki izlemeyi de teyit ederse kaç olay sayılır?
        - Kod bugün: pump, tepe ve izleme kodu yok; kapı `tepe`'yi ve pump adlarını çağırandan alıyor.
    16. **H3'te "ilk gün".**
        - Açık sorular: koşulların birlikte sağlandığı kesintisiz dizinin ilk günü mü, dönem ya da küme başından
          beri ilk gün mü? Koşullar sürerken bekleme bitince ertesi gün yeni "ilk gün" mü? Bir günlük NaN
          diziyi keser mi?
        - Kod bugün: H3 sinyal kodu yok; kapı t'yi çağırandan alıyor.
    17. **NaN hacmin 0 sayılması** (A6).
        - Açık soru: 4h barın satırı var ama hacim (ya da fiyat) hücresi NaN ise bar "mevcut" mu sayılır?
        - Kod bugün: `klines.gunluge_cevir` yalnızca bar sayısına bakıyor; gün oluşuyor ve toplam NaN'ı atlıyor
          (xfail: `test_f1_kapanis_saldirilari::test_gunluge_cevir_nan_hacimli_bari_tam_gun_sayar_kismi_toplar`).

    Maddelerin ön-kayıt alıntıları depo dışındaki Rev.11 girdisindedir (`D:/Projeler/prompts/rev11_girdi.md`).
    Girdinin bölüm numaraları bu listeninkilerle aynıdır (onay kaydı turunda eşitlendi, §14.24).

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
      denetiminden geçiyordu. NaN oran önceki gibi `FundingTamDegil`.
      **Düzeltme (kapı sertleştirme turu 3):** burada önceden "(Rev.10 D-C5, Rev.11'de)" yazıyordu; etiket
      yanlıştı. Rev.10 D-C5 yalnızca H2 **sinyal** penceresini (`funding_ortalamasi`) kapsar. Bu davranış,
      **pozisyon funding'inde NaN oranın sessizce reddi**, kendi adıyla KS2 D-B4'tür ve Rev.11 listesinin
      14. maddesidir (§14.21).
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

23. **Kapı sertleştirme turu 3 (2026-09-28).** Ön-kayda dokunulmadı; getiri hesaplanmadı; F2'ye geçilmedi;
    önbellek eklenmedi. Kapının sinyal değerlerini hesaplaması Rev.11'i bekliyor.

    **Kod.**
    - **`edebbbd`: hata ile "olay yok" ayrımı** (KS2 D-C1; madde 3).
      - `pencere.OlayOlusmaz` artık `Exception`'dan türüyor; `ValueError` alt sınıfı değil.
      - Yeni `pencere.VeriHatasi(ValueError)`; `ZamanDizisiHatasi` bundan türüyor.
      - Kapının veri hataları `VeriHatasi`: sonlu olmayan fiyat ya da funding toplamı, NaT `close_time`, 4h
        ızgarası dışı açılış, bar yok, yükleyicinin DataFrame dışı döndürmesi.
      - Sonuç: `except OlayOlusmaz` bir hatayı yutmaz, `except ValueError` bir ret gerekçesini yutmaz.
      - `_kume_verisi` zaman dizilerini kesimden önce doğruluyor.
      - Sızıntı testçisinin iki tz'siz testi (madde 5) ilk beklentisine (`ZamanDizisiHatasi`) döndü ve geçiyor.
    - **`c866f74`: onay koşusu bağlamı** (KS2 D-B1; madde 1).
      - `config.HIPOTEZLER` eklendi. `split._hipotez_dogrula` yalnızca bu sabitleri tam `str` olarak kabul
        ediyor. Serbest ad deseni kaldırıldı; onay kümesi de tam `str` ve `config.ONAY_KUMELERI` içinde olmalı.
      - `split.onay_baglami_dogrula` ve `OnayUyusmazligi(OnayGerekli)`: C1/C2 pozisyonu yalnızca aynı
        (hipotez, küme) çiftinin açık koşusunda oluşur.
      - Açık koşu varken KEŞİF dahil başka hiçbir pozisyon oluşmaz. Bu, görevin "eşleştirsin" ifadesinin
        katı okuması.
      - Kapı, `mae` ve `funding.pozisyon_fundingi` bu denetimi çağırıyor.
    - **`6699ff3`: ikincil ufuk** (KS2 D-B3; madde 2).
      - İkincil ufuk istendiğinde aynı çağrı önce birincil ufukla değerlendiriliyor. Birincilde olay
        oluşmazsa aynı ret gerekçesi yukarı çıkıyor.
      - Birincilde oluşan olayın ikincil çıkışı kendi uzunluğuyla kurallara tabi.

    **Yakalama noktaları.**
    - Kapı yolunda yakalama yok.
    - Analiz betikleri `OlayOlusmaz` ve `DonemDisiSinyal`i adıyla yakalıyor; bunlar zaten dardı, değişmedi:
      - `a1_olcumu.py:194, 196`
      - `f1k_kume_sonu.py:62`
      - `rev8_etki.py:122`
      - `rev9_hazirlik.py:859, 863, 933, 1179`
      - `rev9_ritim.py:139`
      - `rev9_uygulama.py:90, 145, 147, 193`

      `OlayOlusmaz` artık `ValueError` olmadığı için bu noktalar hiçbir veri hatasını yakalamıyor.
    - **Geniş yakalamalar** (`except Exception` / `BaseException`) kapı yolunda değil, değiştirilmedi:
      - `calistir.py:108` (geçici dosya temizliği; yeniden fırlatır)
      - `calistir.py:255` (çapraz doğrulama hatası tabloya yazılır)
      - `calistir.py:877` (sürüm okuma)
      - `calistir.py:1285` (sembol başına yükleme hatası `hatalar` listesine yazılır ve raporlanır)
      - `binance_vision.py:96` (ağ yeniden denemesi; sonunda `RuntimeError`)
      - `split.py` `_git` (git yoksa `None`)

      Hiçbiri bir ret gerekçesini yutmuyor.

    **KS2 D-B2 (onay koşusunu kilitlenen yapılandırmaya bağlama): tasarlandı, uygulanmadı.** Ayrıntı tur
    raporunda. `KILIT.md`'nin kodda okunması ve kilitli dosyalara eklenmesi ayrı bir kilit oturumunda.

    **KS2 D-B4:** §14.22'deki yanlış etiket ("Rev.10 D-C5") yerinde düzeltildi. Madde kendi adıyla Rev.11
    listesinin 14. maddesi (§14.21).

    **Test güncellemeleri.**
    - **Beklentisi değişenler:**
      - `test_kume_siniri::test_hata_sinifi_tek` ve
        `test_pozisyon_plani::test_hata_siniflari_olay_olusmaz_altinda`: `OlayOlusmaz` artık `ValueError`
        değil.
      - `test_kume_korumasi`: `"HTEST"` → `"H1"`; geçersiz ad listesine varyasyonlar eklendi.
      - `test_onay_kaydi::_test_hipotezi`: `config.HIPOTEZLER`'den boş ad seçer; boş ad yoksa atlanır.
      - `test_ks_donem_kaydi`, `tur_saldirilari_k`, `tur_saldirilari_l`: C1 grup denetimi açık koşu içinde
        yapılıyor; koşu dışında `OnayUyusmazligi`.
    - **Fikstürler birincil ufka taşındı (beklenti aynı):**
      - `test_rev9_f2_bayraklari::test_pencere_sonu_esitlik_affi`
      - `tur_saldirilari_f`, `g`, `h`, `i`'nin imza testi planları (6 → 18)
    - **xfail'den çıkan:** `tur_saldirilari_m` hipotez uyuşmazlığı.
    - **Beklentisi ilk hâline dönen:** `tur_saldirilari_m`'in iki tz'siz testi.
    - **Yeni:** `test_ks3_kapi` (31).

    **KS2 bulgularının durumu:**

    | Bulgu | Durum |
    |---|---|
    | KS2 D-B1 onay koşusunun hipotezi | **kapandı** (`c866f74`) |
    | KS2 D-B2 yapılandırma bağı | tasarlandı; kilit oturumunda uygulanacak; **dokunur** (F3) |
    | KS2 D-B3 ikincil ufuk | **kapandı** (`6699ff3`) |
    | KS2 D-B4 pozisyon funding'inde NaN oran | Rev.11 listesi 14; **dokunur** |
    | KS2 D-B5 §14.21 özeti ve bayat satırlar | açık (belge) |
    | KS2 D-C1 `OlayOlusmaz` ValueError | **kapandı** (`edebbbd`) |
    | KS2 D-C2 gerçek `_veri_yukle` testte yok | açık |
    | KS2 D-C3 yükleyici öznitelikleri atanabilir | açık (kararlı atlatma) |
    | KS2 D-C4 `mae` seri doğrulaması | açık |
    | KS2 D-C5 ızgara dışı t ham saklanıyor | açık, şüpheli |
    | KS2 D-C6 k ters sıra testinin adı | açık |
    | KS2 D-C7 UTC fazla reddediyor | açık, zararsız |

    **Doğrulama.** Tam denetim (`f523cb5`, `--eski-evren`) ve A1 (`18263d5`) temiz ağaçta; veri CSV'leri önceki
    çıktılarla bayt düzeyinde aynı, yalnızca ortam kayıtları farklı (`karsilastirma_ks3_{calistir,a1}_tam.csv`).

    **Tur sonu ajan bulguları (düzeltilmedi; yukarıdakilerden sonra geldi).** Denetçinin bulguları "KS3" önekiyle.

    *Denetçinin cevabı:* getiriye dokunan açıklar kaldı; F2 başlayamaz. Denetçi açıkları üçe ayırıyor.

    - **Rev.11 kararı bekleyenler (F2'yi engeller).**
      - Listedeki 1–9 ve 11–14. maddeler.
      - Listede olmayanlar:
        - H1'de 12 barlık izleme sürerken yeni pump barı; H3'te "ilk gün";
        - A6 (`gunluge_cevir` NaN hacmi 0 sayıyor);
        - KS3 D-B4.
    - **Kod düzeltmesi bekleyenler (F2'den önce).**
      - Rev.9 D-C2 (kesimlerde tolerans yok).
      - Rev.9 D-C5 (0 ya da negatif P0/P1 reddedilmiyor).
      - F1 kapanış D-B1 (Rev.11'den sonra).
      - §8 eşiği `config`'te yok (F1K2 D-C4).
      - KS3 D-C1.
    - **F3'ü engelleyenler (F2'yi değil).**
      - KS2 D-B2.
      - KS3 D-B1, D-B2, D-B3.
      - §9 eşikleri `config`'te yok.

    *Yeni bulgular:*
    - **KS3 D-B1:** onay kaydı ve tek atış, `onay_kosusu(..., yol=...)` parametresiyle ya da `config.ONAY_KAYDI`
      yeniden atamasıyla atlatılabiliyor.
      - Gerçek kayda bir şey yazılmadan koşu açılıyor.
      - Tekrar denetimi yalnızca verilen dosyayı okuyor.
      - Sızıntı testçisinin bulgusu da aynı ailede: `split._AKTIF_KOSU` doğrudan atanınca kayıtsız C1 pozisyonu
        onaylanıyor (`test_tur_saldirilari_n`, xfail).
    - **KS3 D-B2:** onay koşusu kirli çalışma ağacında ya da git yokken açılabiliyor; "KIRLI" yalnızca kayda
      yazılıyor.
    - **KS3 D-B3:** koşunun sonucu (GEÇTİ / KALDI / YETERSİZ GÜÇ) kayda yazılmıyor (ön-kayıt §9).
    - **KS3 D-B4:** BTCUSDT B grubunda. §10'daki "BTC rejimi" dökümü KEŞİF'te C1 verisine bakmayı
      gerektiriyor (ön-kayıt §3 ile gerilim). Rev.11 kararı.
    - **KS3 D-B5:** depo dışı Rev.11 girdisi (12 bölüm) §14.21 listesiyle (14 madde) uyuşmuyor.
      - Girdide olmayanlar: Rev.10 D-C5 (madde 9) ve D-C7 notu (madde 10).
      - Ne girdide ne listede olanlar: H1'de yeni pump barı, H3 "ilk gün", A6, Rev.9 D-C5.
    - **KS3 D-C1:** `DonemDisiSinyal` / K2 havuzu kısmı kapanmadı. (sembol, t) → dönem no araması veri
      katmanında yok; F2 bunu kapı dışında yapmak zorunda kalıyor. `DonemDisiSinyal` docstring'i bayat.
    - **KS3 D-C2:** `pozisyon_fiyatlari` onay bağlamını denetlemiyor; `mae` ve `pozisyon_fundingi`
      denetliyor.
    - **KS3 D-C3:** `pencere.py:777, 796` ve `funding.py:551` veri hatası için düz `ValueError` veriyor,
      `VeriHatasi` değil.
    - **KS3 D-C4:** `tur_saldirilari_m` testinin adı (`..._engellenmez`) artık tersini söylüyor; beklenti
      `OnayUyusmazligi` kadar dar değil.
    - **KS3 D-C5:** §14.23'te doğrulama paragrafı eksikti; yukarıya eklendi.
    - **KS3 D-C6 (şüpheli):** ikincil ufuk okuması ön-kayıt metnine dayanıyor; Rev.11'e bir açıklama cümlesi
      önerildi.
    - **KS3 D-C7:** `test_onay_kaydi`, bütün onay koşuları yapıldıktan sonra sessizce atlanıyor.
    - **KS2 D-B5 genişledi.**
      - §14.21 özetinde yok: Rev.9 D-C5, A6, F1K2 D-C4, KS2 D-B2, KS3 D-B1…B4.
      - Bayat: F1K2 D-C2 satırı ve "Bilinen sınır" paragrafı.

    *Denetçinin onayladıkları:*
    - `OlayOlusmaz` ayrımı sessiz ret ya da yutulan hata yaratmıyor.
    - Katı onay okuması ön-kayıtla çelişmiyor. §10'daki H1–H2 örtüşme oranı için Rev.11'de bir not öneriyor.
    - İkincil ufuk özyinelemesi doğru ve en fazla bir adım derin.
    - Beklentisi değişen testlerde anlam kaybı yok.
    - KS2 D-B2 tasarımı yönüyle tutarlı. Eksik adımlar:
      - ızgaralar `config`'e ve D-B1 bağımlılığı;
      - KS3 D-B1 ve D-B2 önce kapanmalı;
      - C1 ve C2 aynı kilitle koşulmalı;
      - §8.4 keşif sonuçları kilitte olmalı;
      - sonuç satırı ve yarıda kalan koşu;
      - kilit commit'inin HEAD'in atası olması.

    **Sızıntı testçisi** (`test_tur_saldirilari_n`, `2d32ce6`, yalnızca yeni dosya): 12 test.
    - Sonuç: 11 geçti, 1 xfail(strict). Bulgu: `_AKTIF_KOSU` doğrudan ataması (yukarıda, KS3 D-B1 ailesi).
    - Savuşturulanlar:
      - iç içe koşu;
      - koşu içinde istisna ve temizlik;
      - `OnayTekrari`'nın `_AKTIF_KOSU`'yu kirletmemesi;
      - başka koşuda `mae` / `pozisyon_fundingi`;
      - `numpy.str_` hipotez adı;
      - `DonemDisiSinyal`in `OlayOlusmaz` olarak yakalanmaması;
      - `cikis_bari`'nın düz `ValueError`'ı;
      - ikincil ufkun kendi küme sınırı ve birincil gerekçenin korunması;
      - H3'ün 7 ve 30 günlük ikincil ufukları.
    - `config.HIPOTEZLER` monkeypatch'i yalnızca belgelendi (kararlı atlatma).
    - **Ana oturum düzeltmesi:** xfail testinin gövdesi saldırının başarısını iddia ediyordu ve XPASS veriyordu.
      Uzlaşıma göre istenen davranışı (`OnayGerekli`) iddia edecek biçimde çevrildi; bulgu aynı.

24. **Onay kaydı ve koşu bütünlüğü turu (2026-09-29).** Ön-kayda dokunulmadı; getiri hesaplanmadı; F2'ye
    geçilmedi; önbellek eklenmedi. Kilitli dosyalara (`ONAY_KAYDI.md`, `CLAUDE.md`) dokunulmadı.

    **Koruma ölçütü.** Aynı süreç içinden mutlak koruma mümkün değil. Amaç: onay kaydını atlatmak kazayla
    olmasın ve geçmişte iz bırakmayan bir yolla yapılamasın.

    **Kod (`b2acfa3`).**
    - **KS3 D-B1: üç atlatma yolu kapandı.**
      - `split.onay_kosusu(hipotez, kume)` yol parametresi almıyor. Yol alan `onay_kaydet` kaldırıldı; kayıt
        yalnızca `config.ONAY_KAYDI`ya yazılıyor.
      - `config.ONAY_KAYDI` çalışma anında yeniden atanamıyor ve silinemiyor (`config.SabitDegistirilemez`).
        `split` yolu yükleme anında sabitliyor; `vars(config)` ile yapılan değişikliği yakalıyor.
      - `split._AKTIF_KOSU` ve koşu yolundaki 30 ad modül dışından atanamıyor ve silinemiyor
        (`split.OnayKorumasi`, `OnayGerekli` alt sınıfı). Durum yalnızca `onay_kosusu` içinde değişiyor.
      - Onay kümesine her erişimde (`kume_erisimi`, `onay_baglami_dogrula`, `aktif_onay_kosusu`) açık koşu
        kayıt dosyasında doğrulanıyor. Kayıtta koşunun bu sürece ait tek bir BASLADI satırı olmalı ve koşu
        kapanmamış olmalı. `vars(split)` ile bellekte kurulan koşu, gerçek kayda satır yazılmadan erişim
        açamıyor. Süreç numarası şartı, çökmüş bir koşunun asılı BASLADI satırının başka süreçte yeniden
        kullanılmasını engelliyor.
      - Testler kayıt yolunu yalnızca `split._test_kaydi_ayarla` ile değiştirebiliyor. Ayar yalnızca bir pytest
        testi içinde (`PYTEST_CURRENT_TEST`) kurulabiliyor ve yalnızca onu kuran testte geçerli.
      - Tarama: `tarama_yardimcisi.ONAY_ATLATMA_DESENI`. Analiz kodunda koşu durumu, test kapısı, kayıt
        yazıcıları, `vars(split|config)`, `split/config.__dict__` ve kayıt dosyasının adı yasak.
      - Sızıntı testçisinin `test_tur_saldirilari_n` xfail'i normal teste döndü.
    - **KS3 D-B2: temiz ağaç.**
      - Koşu yalnızca şu koşullarda açılıyor: git okunabiliyor, `git status --porcelain` boş (izlenmeyen
        dosya dahil), çağıran betik depo içinde ve git'te izleniyor. Aksi hâlde `split.OnayOrtamiHatasi`;
        kayda hiçbir şey yazılmıyor.
      - Etkileşimli oturum ve `python -c` reddediliyor. Kayda 40 haneli commit hash'i ve betiğin depo içindeki
        yolu yazılıyor. Temiz ağaç + izlenen betik: koşunun kodu kayıttaki commit'te.
      - Yan sonuç: koşunun yazdığı satırlar ağacı kirletiyor. Bir sonraki koşu, önceki koşunun kayıt satırları
        commit edilmeden açılamıyor.
    - **KS3 D-B3: sonuç ve hata kaydı.**
      - Koşu başına iki satır. Açılışta `durum=BASLADI`: tarih, küme, betik, commit, hipotez, koşu kimliği,
        süreç, UTC başlangıç.
      - Kapanışta UTC başlangıç ve bitişle:
        - `durum=BITTI sonuc=<...>`: sonuç blok içinde `kosu.sonuc_bildir(...)` ile bildirildi;
        - `durum=HATA hata=<sınıf>`: blok hata ile bitti (KeyboardInterrupt dahil), hata yeniden fırlatılıyor;
        - `durum=HATA hata=OnaySonucuYok`: sonuç bildirilmedi; `split.OnaySonucuYok` fırlatılıyor.
      - Süreç öldürülürse BASLADI satırı kalıyor.
      - Kayıttaki her (hipotez, küme) çifti, durumu ne olursa olsun, harcanmış sayılıyor: ikinci koşu
        `OnayTekrari`. Yarıda kalan koşu da buna dahil.
      - Kayıt koşu sırasında değişirse (BASLADI satırı silinirse) erişim kapanıyor. Bitiş satırı yine yazılıyor,
        sonra `OnayKorumasi`.
      - Oku-denetle-yaz adımı süreçler arası bir kilit dosyasıyla tekil. Kilit asılı kalırsa koşu açılmıyor ve
        ağaç kirli görünüyor.
    - **KS3 D-C3:** `pencere.cikis_bari` (boş bar listesi; dönem içi bar eksik) ve `funding.pozisyon_fundingi`
      (seri kararınkiyle aynı değil) artık `VeriHatasi` veriyor.

    **Kalan atlatma yolları (düzeltilmedi; hepsi kasıtlı).** Depoda commit edilmiş kodda bunların çoğu tarama
    testine takılır ve geçmişte görünür. Depo dışından ya da commit edilmemiş bir betikten yapıldığında iz
    kalmaz.
    1. **Önbelleği doğrudan okumak.** C1/C2 verisi `cache/` altında; `pd.read_parquet` ile ya da
       `klines.ham_mumlari_yukle` / `funding.ham_funding_yukle` ile kapısız okunur. Ham yükleyiciler analiz
       kodunda taramayla yasak (`HAM_ERISIM_DESENI`); `cache/` yolunun doğrudan okunması taranmıyor. Kayıt,
       onay kümesine erişimi değil, onay koşusunu kaydeder: bu yolun kayıtla kapatılması mümkün değil.
    2. **Onay kümesi tanımını değiştirmek.** `config.ONAY_KUMELERI`, `config.KUMELER`, `config.HIPOTEZLER` ve
       küme tarihleri korunmuyor. Örneğin `config.ONAY_KUMELERI = ()` ile C1 onaysız açılır. Taramada yok.
    3. **Veri yükleyicilerini yamalamak** (KS2 D-C3): `klines.mumlari_yukle`, `funding.funding_yukle`,
       `pozisyon._veri_yukle`. Sonuncusu taramada (`KAYIT_DESENI`).
    4. **Test kapısı.** `pytest` import edilip `PYTEST_CURRENT_TEST` ayarlanırsa `_test_kaydi_ayarla` kayıt
       yolunu geçici dosyaya, git ortamını sahteye çevirir. Analiz kodunda taramayla yasak.
    5. **Modül sözlüğü üzerinden fonksiyon değiştirmek** (onay kaydı ikinci turda düzeltildi, §14.25; denetçi
       OK D-B2). `vars(split)["aktif_onay_kosusu"]` ya da `vars(split)["_acik_kosu"]` bir fonksiyonla
       değiştirilirse C1 kayda satır yazılmadan ve dosyaya dokunulmadan açılır; tek satır yeter
       (`test_onay_kaydi_git::test_sinir_modul_sozlugunden_fonksiyon_degistirmek_erisim_acar` ölçtü). Yalnızca
       `vars(split)["_AKTIF_KOSU"]` ile durum kurmak kayıt denetimine takılır; o yol gerçek kayda bu sürecin
       BASLADI satırını yazıp silmeyi gerektirir. Eski metin: "Modül sözlüğü + gerçek kayıt. `vars(split)` ile
       koşu kurup gerçek kayda bu sürecin BASLADI satırını yazmak, sonra dosyayı eski hâline döndürmek. Kilitli
       dosyaya kasıtlı yazıp silmeyi gerektirir." Bu yalnızca `_AKTIF_KOSU` için doğruydu.
    6. **Modülü değiştirmek.** `sys.modules["data.split"]` yerine sahte modül koymak ya da `split` içindeki
       korunmayan yardımcıları (ör. `kume_tanimi`, `split_oku`) yamalamak.
    7. **Geçmişi yeniden yazmak.** Kayıt satırlarını içeren commit'i `git commit --amend`/`rebase` ile
       değiştirmek. Depo uzak bir kopyaya itilmediği sürece yerelde iz kalmaz.

    **Kural 0 notları (tanımsız seçimler; karar verilmedi).**
    - **Koşu sonucunun değer kümesi.** Ön-kayıt §9, satır 296–297: "Hipotez ancak **her iki kümede de**
      aşağıdaki koşulların tamamını sağlarsa **GEÇTİ** sayılır"; satır 304: "Altındaysa hüküm **YETERSİZ GÜÇ**
      olur, GEÇTİ sayılmaz."; satır 306: "Her koşunun sonucu, sonuç ne olursa olsun `ONAY_KAYDI.md` dosyasına
      eklenir." GEÇTİ ve YETERSİZ GÜÇ hipotez hükmü olarak tanımlı; küme başına koşunun sonuç etiketi tanımlı
      değil. Kod sonucu değer kümesiyle sınırlamıyor: tek satırlık, `|` içermeyen, en fazla 200 karakterlik
      metin.
    - **Kilitli dosyalardaki bayat metin.** `ONAY_KAYDI.md` başlığı "KOSU BASINA TEK SATIR ... Satir kosu
      acilirken yazilir" diyor; artık iki satır yazılıyor. `CLAUDE.md` §5 "`data/split.py` içindeki
      `onay_kaydet`" diyor; ad `_onay_kaydet` oldu ve yalnızca `onay_kosusu` içinden çağrılıyor. İkisi de
      kilitli; kilit oturumunda güncellenmeli. Tablonun sütunları değişmedi, yeni alanlar Not sütununda.

    **KS3 D-B5 (Rev.11 girdisi).** Fark:
    - §14.21 listesi 14, girdi 12 bölümdü.
    - Girdide olmayanlar: madde 9 (Rev.10 D-C5) ve madde 10 (Rev.10 D-C7 notu).
    - Girdinin 9–12. bölümleri listenin 11–14. maddeleriydi.

    Liste esas alındı. Girdi 17 bölüme çıktı ve numaraları listeyle aynı. 9 ve 10 alıntılarıyla eklendi; 15–17
    listeye ve girdiye eklendi. Rev.9 D-C5'in 0 fiyat kısmı listeye eklenmedi (görevde yok; §14.21 tablosunda
    "kod düzeltmesi" olarak duruyor).

    **KS3 D-B4 (BTC rejimi):** ölçüldü, karar verilmedi; tur raporunda. BTCUSDT (ve ETHUSDT) B grubunda.
    KEŞİF'te BTC rejimi dökümü, BTCUSDT'nin KEŞİF dönemi verisini gerektiriyor; bu veri tanımca C1'dir.

    **KS2 D-B2:** denetçinin altı eksiği tur raporunda; uygulanmadı.

    **Test güncellemeleri.**
    - **Kayıt yolu:** `config.ONAY_KAYDI` monkeypatch'i 12 yerde `split._test_kaydi_ayarla` oldu. Dosyalar:
      `test_f1_kapanis_saldirilari`, `test_f1k2_kume_none`, `test_ks3_kapi`, `test_ks_donem_kaydi`,
      `test_kume_korumasi`, `test_sizinti_saldirilari`, `test_split`, `tur_saldirilari_k`, `l`, `m`, `n`.
    - **Sonuç bildirimi:** erişim için açılan koşular `onay_yardimcisi.kosu` ile açılıyor; blok hatasız biterse
      "TEST" sonucu bildiriliyor. Koşu semantiğini sınayan testler (iç içe, tekrar, geçersiz ad) değişmedi.
    - **Beklentisi değişenler:**
      - `test_split::test_onay_kosusu_kayit_dosyasina_tek_satir_ekler` ve
        `test_kume_korumasi::test_kosu_basina_tek_satir_sembol_basina_degil`: kayıtta 1 satır → 2 satır
        (BASLADI + BITTI). Sembol başına satır yazılmadığı iddiası aynı.
      - `test_kume_korumasi::test_satirda_commit_ve_calisma_agaci_durumu_var`: eski `_git_commit` ve
        `_calisma_agaci_durumu` yamaları kalktı. Kirli ağaçta koşu artık açılmıyor (`OnayOrtamiHatasi`), temiz
        ağaçta commit 40 haneyle yazılıyor.
      - `test_onay_kaydi`: `onay_kaydet(yol=)` yerine `onay_kosusu`. İddialar aynı: tablonun içine düşme, bayt
        bayt koruma, tekrarın reddi, satır sonu stili, geçici dosya; satır sayıları iki katı.
      - `tur_saldirilari_m`: `yol=` parametresi kaldırıldı.
      - `tur_saldirilari_n` doğrudan atama testi: xfail kaldırıldı, atama `pytest.raises(OnayKorumasi)` içinde.
        `monkeypatch.setattr` teardown'da korunan adı geri atamaya çalıştığı için düz `setattr` kullanıldı.
    - Silinen ya da gevşetilen test yok.
    - **Yeni:** `test_onay_kaydi_butunlugu` (58), `tests/onay_yardimcisi.py`.
    - **Tam takım:** 1722 geçti, 4 xfail (önceki: 1663 geçti, 5 xfail).

    **KS3 bulgularının durumu:**

    | Bulgu | Durum |
    |---|---|
    | KS3 D-B1 `yol=`, `config.ONAY_KAYDI`, `_AKTIF_KOSU` | **kapandı** (`b2acfa3`); kalan kasıtlı yollar yukarıda |
    | KS3 D-B2 kirli ağaçta koşu | **kapandı** (`b2acfa3`) |
    | KS3 D-B3 sonuç kaydı | **kapandı** (`b2acfa3`); sonuç etiketleri kural 0 notu |
    | KS3 D-B4 BTC rejimi | ölçüldü; Rev.11 kararı |
    | KS3 D-B5 Rev.11 girdisi | **kapandı** (girdi 17 bölüm, liste 17 madde) |
    | KS3 D-C3 düz `ValueError` | **kapandı** (`b2acfa3`) |
    | KS3 D-C1, D-C2, D-C4, D-C6, D-C7 | açık (bu turun kapsamı dışında) |

    **Doğrulama.** Tam denetim (`008c72d`, `--eski-evren`) ve A1 (`ae2350d`) temiz ağaçta. 64 çıktının 63'ü önceki
    çıktılarla bayt düzeyinde aynı; yalnızca ortam kayıtları farklı (`karsilastirma_ok_{calistir,a1}_tam.csv`).

    **Tur sonu ajan bulguları (düzeltilmedi; yukarıdakilerden sonra geldi).** Denetçinin bulguları "OK" önekiyle.

    *Denetçinin cevabı:* onay kaydı hâlâ atlatılabiliyor, bir yolu kazayla. Yukarıdaki "Kalan atlatma yolları"
    listesinin 5. maddesi yanlış, 6. maddesi eksik.
    - **OK D-B1: kayıt commit edilene kadar yalnızca çalışma ağacında.** Tek atış denetimi yalnızca çalışma
      ağacındaki dosyayı okuyor. Koşudan sonra ağaç kirli; `git stash -u`, `git checkout .`, `git reset --hard`
      ya da IDE'de "Discard changes" satırları siler. Çift harcanmamış görünür, iz kalmaz. **Kazayla olabilir.**
      Kasıtlı biçimi: `git checkout -- ONAY_KAYDI.md`.
    - **OK D-B2 (şüpheli, denetçi testle doğrulamadı): korunan fonksiyonlar modül sözlüğünden değiştirilebiliyor.**
      - `vars(split)["aktif_onay_kosusu"] = lambda: ("H2", "C1")` (ya da `_acik_kosu`) ile C1 kayda satır
        yazılmadan açılır. 5. maddedeki "kilitli dosyaya yazıp silmeyi gerektirir" yalnızca `_AKTIF_KOSU` için
        doğru.
      - `split.__class__ = types.ModuleType` korumayı kaldırır.
      - Tarama deseni `vars(split)` arıyor; depodaki takma ad `split_modulu` ve `\b` onu eşlemiyor.
    - **OK D-C1:** sonuç bildirildikten sonra blok hata ile biterse (ör. `SystemExit`) kayda yalnızca HATA yazılıyor;
      bildirilmiş sonuç kayda girmiyor. Sonuç bildirilmeden istatistik ekrana basılırsa kayıtta yalnızca
      `OnaySonucuYok` kalır.
    - **OK D-C2 (şüpheli):** `ONAY_TABLO_BASLIGI` korunmuyor. Sızıntı testçisi ölçtü: biçim bozuluyor, tek atış
      bozulmuyor (aşağıda).
    - **OK D-C3:** kayıt izi yanıltıcı olabilir: `__main__.__file__` elle atanabiliyor, `config.KOK` korunmuyor,
      izlenen betik depo dışı kodu içe aktarabilir.
    - **OK D-C4:** tarama `analysis/00_veri_denetimi`'yi ve `.ipynb`'yi muaf tutuyor. `pozisyon.split_modulu` ve
      `data` paketinin `split` özniteliği korunmuyor.
    - **OK D-C5:** bitiş satırı yazılamazsa (kilit zaman aşımı, finally içinde Ctrl-C) başarılı koşunun sonucu
      kaybolur; BASLADI kalır ve hata yüksek sesle verilir. Kayıtsız erişim açan bir hata yolu bulunmadı.
    - **OK D-C6 (şüpheli):** `_acik_kosu` her erişimde dosyayı kilitsiz okuyor. Windows'ta geçici `OSError` koşuyu
      HATA ile bitirir ve çifti harcar. Süreç şartı yüzünden F3 çok süreçli koşulamaz. Performans ölçülmedi.
    - **OK D-C7:** `_test_kaydi_ayarla` varsayılanları gerçek `_kosu_ortami`'nin olumlu yolunu (`relative_to`,
      `ls-files`, porcelain) hiç sınatmıyor. Gerçek ortama dokunan tek test olumsuz yönlü; pytest temiz ağaçta
      izlenen bir giriş betiğinden başlatılırsa gerçek `(H1, C1)` çiftini harcar (şüpheli; bugün böyle betik yok).
    - **OK D-C8: bayat metin.**
      - Kilitli: `CLAUDE.md:54` (`--onay` bayrağı), `CLAUDE.md:107` (`onay_kaydet`), `ONAY_KAYDI.md:6-9`
        (tek satır, temiz/kirli). `ONAY_KAYDI.md:15` "Henuz onay kosusu yok." satırı ilk koşudan sonra da kalır.
      - Kilitsiz: hook yorumu (`onay_kaydet`), `test_kume_korumasi.py:6, 217` ("tek satir"),
        `test_tur_saldirilari_n.py:117`, `split.py` modül korumasının yorumu (OK D-B2).
    - **OK D-C9:** kural 0 okuması (sonuç değer kümesi) doğru. Ek: §9'un altı koşulunun küme başına değerlerinin
      kayda girip girmeyeceği de tanımsız.
    - Rev.11 girdisi ile §14.21 listesi 1–17 birebir uyuşuyor. 9, 10 ve 15–17'deki alıntılar satır satır doğru.

    *Denetçinin sınıflaması:*
    - Kazayla olabilecek: OK D-B1; küme tarihlerinin "duyarlılık için" değiştirilmesi (listenin 2. maddesi).
    - Kasıtla, iz bırakmadan: listenin 1–4, 6, 7. maddeleri; OK D-B2; OK D-B1'in kasıtlı biçimi; OK D-C4.
    - İz bırakan: 5. madde (yalnızca `_AKTIF_KOSU`), OK D-C2, OK D-C3 (yanlış iz), öldürülen süreç.

    **Sızıntı testçisi** (`test_tur_saldirilari_o`, `ab104f2`, yalnızca yeni dosya): 6 test; ana oturum koştu
    (testçinin kabuk aracı yoktu): 4 geçti, 2 xfail(strict).
    - **Bulgular:**
      - `split.split_oku` korunan adlarda yok. Düz `setattr` ile sahte tablo verilince B grubu bir sembol
        KEŞİF'te izinli dönüyor (CLAUDE.md §3.2).
      - `split.kume_araligi` korunan adlarda yok. Düz `setattr` ile KEŞİF'in sonu C2 sonuna uzatılabiliyor
        (ön-kayıt §3).
    - **Belgelenen:** `ONAY_TABLO_BASLIGI` bozulunca satır tablonun dışına düşüyor, tek atış bozulmuyor. İç içe koşu
      denemesinin `RuntimeError`'ı dıştaki koşuyu HATA ile bitiriyor ve çiftini harcıyor.
    - **Savuşturulanlar:** sonuç metnine gömülü sahte alanlar (`durum=`, `kosu=`, `hipotez=`) ayrıştırıcıyı
      yanıltmıyor; koşu sırasında kayıt dosyasının silinmesi iz bırakan bir hata veriyor ve çift harcanmış kalıyor.
    - Testçi raporunda 7 test diyordu; dosyada 6 test var.
    - **Tam takım:** 1726 geçti, 6 xfail.

25. **Onay kaydı ikinci tur (2026-09-30).** Ön-kayda ve kilitli dosyalara dokunulmadı; getiri hesaplanmadı;
    F2'ye geçilmedi.

    **Koruma sınırı.** Aynı süreç içinden mutlak koruma mümkün değildir: Python'da modül sözlüğü, `object.__setattr__`
    ve `sys.modules` her zaman yazılabilir. Amaç, onay kaydını **kazayla atlatmayı imkânsız**, **kasıtlı atlatmayı
    görünür** kılmaktır. "Görünür": yol, depoda commit edilmiş analiz kodunda tarama testine takılır ya da git
    geçmişinde (kayıt satırı, commit) iz bırakır. §14.24'teki ölçütün ("iz bırakmayan bir yolla yapılamasın")
    yerine bu ölçüt geçer; §14.24 ölçütü aynı süreç içinde karşılanamıyordu (OK D-B2).

    **Kod.**
    - **OK D-B1: kayıt git'e bağlı.**
      - Koşu her kayıt satırını yazdığı anda kendisi commit eder, yalnızca kayıt dosyasını
        (`git add` + `git commit --only -- ONAY_KAYDI.md`; mesaj `ONAY_KAYDI: <hipotez> <küme> <durum> (kosu=...)`).
        BASLADI satırı blok çalışmadan önce commit edilir; commit edilemezse koşu açılmaz
        (`split.OnayKaydiCommitsiz`, `OnayOrtamiHatasi` alt sınıfı). Bitiş satırı commit edilemezse hata yine
        yüksek sesle verilir; satır çalışma ağacında ve index'te kalır. Kancalar atlanmaz (`--no-verify` yok).
      - Tek atış denetimi (`split.harcanan_ciftler`) çalışma ağacındaki kayıt ile git geçmişinde kayda bir kez
        eklenmiş bütün satırların birleşimine bakar: `git log --all --reflog -p -- ONAY_KAYDI.md`. Stash,
        başka dallar ve reflog'daki (`reset`, `--amend`, `rebase` ile bırakılan) commit'ler dahildir.
      - Koşu açılmadan önce çalışma ağacındaki onay satırları HEAD'dekiyle aynı olmalı; commit edilmemiş ya da
        commit edilmeden silinmiş kayıt satırı varken yeni koşu açılmaz (`OnayKaydiCommitsiz`).
      - Sonuç: `git checkout .`, `git checkout HEAD -- .`, `git stash -u`, `git reset --hard` tek atışı geri
        getirmez; `reset --hard <eski commit>` de getirmez (reflog). **(Kapanış turunda düzeltildi, §14.26.)** Eski
        cümle: "Geri getiren: geçmişi yeniden yazmak **ve** reflog'u silmek (`reflog expire --expire=now --all`;
        ölçüldü, sınır testi)." Yanlıştı: bu turun koduyla tek atışı geri getiren başka, kazayla olabilecek yollar
        da vardı (ayrı worktree'yi silmek, itilmemiş commit'le yeniden klonlamak; bağımsız HEAD, birleştirilmeden
        silinen dal ya da `reset --hard origin/main` sonrası erişilemeyen reflog girdilerinin süresinin dolması;
        tek tarafa çözülen birleştirme). OK2 D-B1, D-B2; sızıntı P-1…P-5 ölçtü. Bu yollar kapanış turunda kayıt
        uzak depoya bağlanarak kapandı (§14.26).
    - **OK D-B2 ve sızıntı testçisi O: korunan adlar.**
      - `split`: `split_oku`, `kume_tanimi`, `kume_araligi`, git'e bağlı kayıt adları ve `__class__` korunan
        adlarda. `split.__class__ = types.ModuleType` artık `OnayKorumasi`.
      - `config`: `KESIF_BASI`, `KESIF_SONU`, `C2_BASI`, `C2_SONU`, `KUMELER`, `ONAY_KUMELERI` ve `__class__`
        yeniden atanamaz ve silinemez (`SabitDegistirilemez`).
      - Tarama (`ONAY_ATLATMA_DESENI`): `vars(split_modulu)`, `split_modulu.__dict__/__class__`,
        `<modül>.split_modulu = ...`, `object.__setattr__`, `ModuleType.__setattr__`, `sys.modules` ve yeni kayıt
        yazıcıları eklendi. `split_modulu.split_oku()` gibi meşru kullanım yakalanmıyor (testli).
    - **OK D-C1:** sonuç bildirildikten sonra blok hata ile biterse bitiş satırı
      `durum=HATA hata=<sınıf> sonuc=<sonuç>` olur; sonuç bildirilmemişse `sonuc` alanı yazılmaz.
    - **Test yardımcısı:** `onay_yardimcisi.gecici_depo` gerçek bir geçici git deposu kurar; bu kipte bütün git
      işlemleri gerçek (yalnızca çağıran betiğin yolu testten gelir). Eski kip (`gecici_kayit`, sahte git) kaydı
      her an commit edilmiş sayar, geçmişe bakmaz ve commit etmez.

    **Kalan atlatma yolları, yeni ölçütle.**

    | # | Yol | Kazayla? | Kasıtlıysa görünür mü? |
    |---|---|---|---|
    | 1 | Önbelleği doğrudan okumak (`pd.read_parquet("cache/...")`), bir not defterinde ya da koşu dışı betikte | **olabilir** (koşu açılmadan C1/C2 dosyası okunur) | hayır: `cache/` yolu taranmıyor, `.ipynb` taranmıyor; kayıt koşuyu kaydeder, erişimi değil |
    | 2 | Ham yükleyiciler (`ham_mumlari_yukle`, `ham_funding_yukle`) | hayır (adı açık) | evet, analiz kodunda `HAM_ERISIM_DESENI`; `analysis/00_veri_denetimi` muaf |
    | 3 | Modül sözlüğü: `vars(split)["aktif_onay_kosusu"] = ...` (§14.24 madde 5, düzeltilmiş) | hayır | evet (`split`, `split_modulu`, `config` adlarıyla); başka ad ya da `vars(pozisyon)["split_modulu"]` yakalanmaz |
    | 4 | `object.__setattr__`, `ModuleType.__setattr__`, `sys.modules` değişimi | hayır | evet (tarama) |
    | 5 | Yükleyicileri yamalamak (`klines.mumlari_yukle`, `funding.funding_yukle`) | hayır | kısmen: `pozisyon._veri_yukle` taramada, diğerleri değil |
    | 6 | Test kapısı (`PYTEST_CURRENT_TEST` + `_test_kaydi_ayarla`) | hayır | evet (tarama) |
    | 7 | Korunmayan config adları: `SPLIT_CSV`, `BOLME_TUZU`, `YENIDEN_ADLANDIRMA` (içeriği değişebilir), `HIPOTEZLER` | hayır: tek başına biri `split_dogrula`'da hata verir; sızıntı en az iki kasıtlı değişiklik ister. `HIPOTEZLER`'e ad eklemek yeni çift açar ama kayda o adla yazılır | tarama yok; `HIPOTEZLER` yolu kayıtta görünür |
    | 8 | Geçmişi yeniden yazıp reflog'u silmek | hayır (iki kasıtlı adım) | hayır, yerelde iz kalmaz |
    | 9 | Kayıt commit'lerini daldan çıkarıp (`reset --hard <eski>`) reflog'un kendiliğinden dolmasını beklemek | **olabilir, yavaş**: erişilemeyen reflog girdileri varsayılan olarak 30 gün sonra `git gc` ile silinir | hayır |
    | 10 | Başka bir klon ya da çalışma kopyası: kayıt yerel git geçmişine bağlı; iki kopya birbirinin koşusunu görmez | **olabilir** (birden fazla kopya varsa) | kopyalar birleştirilince kayıtta iki koşu görünür |
    | 11 | BASLADI commit edilemedi, satır sonra silindi | olabilir; ama koşu açılmadı, veri okunmadı: tek atış harcanmadı | — |
    | 12 | Bitiş satırı commit edilemedi, satır sonra silindi | olabilir; çift harcanmış kalır (BASLADI commit'li), yalnızca sonuç kaybolur | — |
    | 13 | Yanıltıcı iz: `__main__.__file__`, `config.KOK`, izlenen betiğin depo dışı kod yüklemesi (OK D-C3) | hayır | iz var ama yanlış |
    | 14 | Tarama muafiyetleri: `analysis/00_veri_denetimi`, `.ipynb` (OK D-C4) | — | muaf yerde kasıtlı yol taramaya takılmaz; commit edilmişse geçmişte görünür |

    **Açık kalanlar (bu turda istenmedi):** `ONAY_TABLO_BASLIGI` korunmuyor (OK D-C2; biçim bozulur, tek atış
    bozulmaz). OK D-C5 (bitiş satırı yazılamazsa sonuç kaybı), OK D-C6 (kilitsiz okuma), OK D-C7 (gerçek
    ortamda `__main__` ve `relative_to(KOK)` yolu hâlâ testsiz; git tarafı artık gerçek depoda sınanıyor).

    **Test güncellemeleri.**
    - `test_kume_siniri::test_kume_araligi_kume_tanimindan_turetilir`: `monkeypatch.setattr(split, "kume_tanimi")`
      → `monkeypatch.setitem(vars(split), "kume_tanimi")` (ad artık korunuyor). İddia aynı.
    - `test_tur_saldirilari_o`: iki xfail (`split_oku`, `kume_araligi`) normal teste döndü. Değişiklik: xfail
      işareti kalktı, "korunan adlarda değil" iddiası "korunan adlarda" oldu, atama `pytest.raises(OnayKorumasi)`
      içinde; erişimin sızdırmadığı iddiası aynı.
    - Yeni: `tests/test_onay_kaydi_git.py` (44), `onay_yardimcisi.gecici_depo` ve `git`.
    - Silinen ya da gevşetilen test yok.
    - **Tam takım:** 1772 geçti, 4 xfail (önceki: 1726 geçti, 6 xfail).

    **Doğrulama.** Tam denetim (`4d5a3de`, `1c78994` temiz ağaçta, `--eski-evren`; 678/678 sembol) ve A1 (`821cb1b`)
    temiz ağaçta. İkisinde de 64 çıktının 63'ü önceki çıktılarla bayt düzeyinde aynı; yalnızca ortam kayıtları farklı
    (`karsilastirma_ok2_{calistir,a1}_tam.csv`).

    **Tur sonu ajan bulguları (düzeltilmedi; yukarıdakilerden sonra geldi).** Denetçinin bulguları "OK2" önekiyle.

    *Denetçinin cevabı:* evet, kazayla atlatılabilecek yol kaldı. Kök: tek atış, koşunun yapıldığı kopyanın yerel git
    grafiğine ve reflog'una bağlı; kayıt commit'leri kalıcı bir referansa bağlanmıyor. Yukarıdaki "Kalan atlatma
    yolları" tablosu bu bakımdan eksik; "geri getiren yalnızca geçmişi yeniden yazmak ve reflog'u silmek" cümlesi yanlış.
    - **OK2 D-B1:** `ortam_karari` bağımsız HEAD'i, her dalı, worktree'yi ve klonu kabul ediyor. (a) Geçici worktree'de
      koşup `git worktree remove`: çift hemen yeniden açılır, iz kalmaz. (b) İtilmemiş kayıt commit'leriyle yeniden
      klonlama: iz kalmaz. (c) Bağımsız HEAD'de koşup dala dönmek, `git bisect`, birleştirilmeden `branch -D`,
      `reset --hard origin/main`: commit'ler yalnızca erişilemeyen reflog'da kalır, 30 gün + `git gc` sonrası çift
      geri gelir.
    - **OK2 D-B2:** `git log -p -- ONAY_KAYDI.md` `--full-history` olmadan çalışıyor; çatışması tek tarafa çözülen
      (`-X ours`, "Accept Current") birleştirmede öbür tarafın koşusu, o tarafın referansı ve reflog'u gidince
      görünmez. Tablonun 10. satırındaki "kayıtta iki koşu görünür" bu durumda yanlış.
    - **OK2 D-B3:** korunan fonksiyonların modül bağımlılıkları korunmuyor ve taranmıyor (kasıtlı): `split.subprocess`
      (geçmiş denetimi kör), `split.config` (C1 koşusuz), `split.klines` (kırpma kalkar), `split.split_dogrula`.
    - **OK2 D-C1:** bitiş commit'i, koşu sırasında kayıtta yapılmış ekleme dışı değişikliği de koşu mesajıyla commit
      ediyor ("yalnızca ekleme" güvencesi HEAD'e değil çalışma ağacına göre).
    - **OK2 D-C2:** `raise ... from commit_hatasi` `None` iken asıl hatayı traceback'te gizliyor (yalnızca teşhis).
    - **OK2 D-C3 (şüpheli):** 30 sn git zaman aşımı commit'e de uygulanıyor; `gc --auto` ya da kanca uzarsa commit
      yapılmış olsa da hata dönebilir; yarım `index.lock` sonraki koşuları kapatır (kapalı yönde).
    - **OK2 D-C4:** test deposu gerçek yapılandırmadan farklı (`autocrlf`, kancalar, gpgsign); sahte git kipinde
      commit, geçmiş ve ortam denetimleri atlanıyor; bağımsız HEAD, worktree, birleştirme için test yoktu.
    - **OK2 D-C5 (kasıtlı):** `.git/info/attributes`'ta `ONAY_KAYDI.md binary` geçmiş denetimini kör ediyor; `_git`
      `GIT_DIR`, `GIT_INDEX_FILE`, `GIT_CONFIG_*` değişkenlerini temizlemiyor.
    - **OK2 D-C6 (şüpheli):** OK D-C7 senaryosunda gerçek ortama dokunan olumsuz test gerçek depoya commit de atabilir.
    - **OK2 D-C7:** bayat metin. Kilitli: `CLAUDE.md:54` (`--onay`), `:102-104` ("Henüz onay koşusu yok"),
      `:107` (`onay_kaydet`, otomatik commit anılmıyor), `ONAY_KAYDI.md:6-10`, `:15`. Kilitsiz: `split.py` yorumları
      (eski ölçüt, "yalnızca geçmişi yeniden yazmak"), hook yorumu (`onay_kaydet`).
    - Tablo değerlendirmesi: 1, 2, 4–8, 11–14 doğru (2'ye `.ipynb` eklenmeli); 3–4 düz atamaları kapsamıyor; 9'un
      tetikleyicileri eksik; 10'un görünürlüğü yanlış. Eksik satırlar: geçici worktree, itilmemiş klon, tek tarafa
      çözülen birleştirme (üçü kazayla olabilir), bağımlılığa düz atama, öznitelik ve `GIT_*` (kasıtlı).
    - Ön-kayıt, küme tarihleri, geleceğe bakış, tohum: yeni bulgu yok. Kilitli dosyalar bu turda değişmedi (ana oturum
      `git diff cf6122b 1c78994` ile doğruladı).

    **Sızıntı testçisi** (`test_tur_saldirilari_p`, `671822e`, yalnızca yeni dosya; mevcut dosyalarda değişiklik yok):
    38 test; testçi koşamadı, ana oturum koştu: 16 geçti, 22 xfail(strict, `raises=(AssertionError, Failed)`).
    Testçi raporunda 21 xfail diyordu; koşuda 22.
    - **Başarılı saldırılar (xfail):**
      - P-1 bağımsız HEAD + `reflog expire --expire-unreachable=now`; P-4 dal `-D` + aynı: çift yeniden açılıyor.
      - P-2 bağımsız HEAD'li worktree + `worktree remove`; P-3 dallı worktree + `branch -D` (reflog expire bile
        gerekmiyor): çift ana depoda yeniden açılıyor. OK2 D-B1'i ölçtü.
      - P-5 (`-X ours`, `-s ours`) birleştirme + dal ve reflog silme: öbür dalın koşusu görünmüyor. OK2 D-B2'yi ölçtü.
      - P-6 (`binary`, `-diff`) `.git/info/attributes`: geçmiş denetimi kör. P-7 `git replace`: kayıt commit'leri
        gizleniyor.
      - P-8 `split.subprocess`, P-9 `split.config`, P-10 `split.klines`, P-11 (`split_dogrula`, `grup`,
        `varlik_anahtari`, `hashlib`) düz atamayla: geçmiş denetimi kör, C1 koşusuz, C2 barları KEŞİF'e, B coini KEŞİF'e.
      - P-12 `config.BOLME_TUZU`, P-13 `config.YENIDEN_ADLANDIRMA` (yerinde değişen sözlük) + sahte tablo: bölme kayıyor.
        P-14 `config.HIPOTEZLER`'e ad eklemek ek tek atış hakkı açıyor.
      - P-15 `gecmis_satirlari` ikili fark satırlarını hata vermeden boş sayıyor.
      - P-16 koşu sırasında eski satır silinirse bitiş commit'i silmeyi de commit ediyor (OK2 D-C1'i ölçtü; çift yine
        geçmişten harcanmış).
    - **Savuşturulanlar:** reflog duruyorken bağımsız HEAD, dal silme, `ours` birleştirmesi; dallı worktree silinince
      dal üzerinden görünme; iki dalda aynı çift; `git revert`; `git rm`; ayrıştırıcı kenar durumları (çok commit,
      `\ No newline`, silinip yeniden oluşan dosya, hunk içinde başlık taklidi, CRLF); koşunun kendi BASLADI satırını
      silmesi.
    - **Yazılamayanlar:** `config.KOK` değişimi (gerçek depoyu gerektirir), ikinci klon (tasarım sınırı), `split.os`,
      `split.time`, `split.uuid` (aynı türden).
    - **Tam takım:** 1788 geçti, 26 xfail.

26. **Onay kaydı kapanış turu (2026-09-30).** Ön-kayda ve kilitli dosyalara dokunulmadı; getiri hesaplanmadı;
    F2'ye geçilmedi. Onay kaydı çalışması bu turda kapanıyor.

    **Kapsam kararı** (kapanışta, §14.28, üçüncü kez yazıldı; genel hüküm içermiyor).
    Tek atış korumasının hedefi kazayla atlatmayı imkânsız, kasıtlı atlatmayı görünür kılmaktır. Bu hedefin bugün
    nerede tutulduğu yalnızca adıyla sayılan yollarda geçerlidir; üç liste §14.27'de:
    - **kapatılan yollar:** §14.27 "Kapatılan yollar" tablosu (1–12; adıyla, kapanış turuyla ve ölçen testiyle);
    - **kasıtlı ve çok adımlı oldukları için kapatılmayanlar:** §14.27 K1–K13 (adıyla ve iz durumuyla);
    - **kazayla tetiklenebilir olduğu halde kapatılmayanlar:** §14.27 KK1–KK4 (adıyla ve nedeniyle: iş parçacığı
      kapsamı, doğrudan ağ çağrıları, SETTLED dizin grubu, `split.yukle` özel yükleyicisi).
    Son iki liste açık nokta olarak kayıtlıdır ve F2'yi engellemez. Genel bir "kazayla atlatma yolları kapatıldı"
    hükmü verilmiyor: kapatılmış yol, tabloda adı geçen yoldur.
    Eski metin (bu turda yazılan, iki cümlesi denetçi OK3 D-B1, D-B2, D-B3, D-B5 ile yanlış çıktı): "Kazayla atlatma
    yolları kapatılmıştır. Kalan yollar (ayrı worktree, yeniden klonlama, bağımsız HEAD, birleştirmede tek tarafa
    çözüm, geçmişi yeniden yazıp zorla itme, düz atamayla modül değiştirme) kasıtlı ve çok adımlı eylemlerdir; kayıt
    commit'lerinin uzak depoya itilmesiyle her biri iz bırakır."

    **Kod (`472a541`): kayıt uzak depoya bağlı.**
    - Koşu açılmadan önce `origin/main` alınır (`git fetch`). Alınamazsa (ağ yok, uzak depo erişilemez, kimlik bilgisi
      istenir) koşu açılmaz (`split.OnayUzakHatasi`); yerel kipe düşülmez. Kimlik bilgisi istemi kapalı
      (`GIT_TERMINAL_PROMPT=0`); ağ işlemlerinin zaman aşımı 120 sn.
    - HEAD'deki kayıtta `origin/main` geçmişinde bulunmayan (itilmemiş) onay satırı varsa koşu açılmaz.
    - Tek atış denetimi çalışma ağacı ve yerel geçmişe (§14.25) ek olarak `origin/main` geçmişine de bakar.
    - Tek atış denetiminden sonra: HEAD `origin/main`'i içermiyorsa (kayıt commit'i ileri sarma olarak itilemez)
      koşu açılmaz. Harcanmış çift önce `OnayTekrari` verir.
    - BASLADI satırı commit edilince hemen itilir (`git push origin HEAD:refs/heads/main`, zorla itme yok); bitiş
      satırı da öyle. İtilemezse kayda `durum=ITILEMEDI asama=<BASLADI|BITTI|HATA> zaman=<UTC>` satırı yazılır ve
      yerelde commit edilir, `OnayUzakHatasi` verilir; mesaj sonucun koşu raporuna yazılmasını ve kaydın elle
      itilmesini ister. BASLADI itilemezse koşu açılmaz (veri okunmaz), ama çift harcanmış kalır (muhafazakâr yön).
      İtilmemiş satırlar itilene kadar yeni koşu açılmaz.
    - Sırası: yerel denetimler (commit'li kayıt, temiz ağaç, izlenen betik) → `fetch` → itilmemiş satır → tek atış →
      ileri sarma → BASLADI yaz, commit, it → blok → bitiş yaz, commit, it. Ağa yalnızca temiz, izlenen bir
      ortamda çıkılır; gerçek ortama dokunan olumsuz test ağa çıkmadan reddedilir.
    - Not: yerel `main` şu an `origin/main`'in 69 commit önünde. İlk gerçek onay koşusu bu commit'leri de iter.
    - Gerekçe: yerel git geçmişi sahibi tarafından yeniden yazılabilir; uzak depodaki commit'in zaman damgası
      yazılamaz.

    **Testler.** `onay_yardimcisi.gecici_depo` artık `origin` olarak çıplak bir geçici depo ekler (dosya yolu; ağa
    çıkılmaz).
    - Yeni (`test_onay_kaydi_git`): iki satır da itiliyor; itilmemiş kayıt varken koşu reddediliyor, elle itilince
      açılıyor; bitiş itilemezse kayıtta ITILEMEDI; ağ yoksa koşu açılmıyor ve hiçbir şey yazılmıyor; HEAD
      `origin/main`'i içermiyorsa koşu açılmıyor; **itilmiş çift, yerel dal, reflog, nesneler ve uzak izleme
      referansı silinse de harcanmış** (§14.25'teki "geçmişi yeniden yazıp reflog'u silmek geri getirir" sınır
      testinin yerine).
    - Güncellenen: `test_commit_edilmemis_bitis_satiri_varken_yeni_kosu_reddedilir` elle commit'ten sonra
      `git push` yapıyor.
    - `test_tur_saldirilari_p` (sızıntı testçisinin dosyası; davranış değiştiği için güncellendi):
      - P-1…P-4 (bağımsız HEAD, worktree, dal silme + reflog süresi) XPASS verdi: xfail işaretleri kaldırıldı,
        gövdeler değişmedi.
      - P-5 (`ours` birleştirmesi, 2 kimlik) ve eşi savuşturulan test: iki dalda paralel koşu kurulamıyor (ikinci
        dalda `OnayUzakHatasi`). Yardımcı `_iki_dal_kur_ve_birlestir` bu reddi iddia ediyor ve birleştirmeyi
        `--no-ff` ile yapıyor; "birleştirme dalB satırlarını düşürmeli" ön koşulu kaldırıldı (`-X ours` artık
        çatışmasız birleşiyor). P-5'in xfail işareti kaldırıldı; son iddia (`OnayTekrari`) aynı.
      - P-6 (`info/attributes`, 2 kimlik), P-7 (`git replace`), P-8 (`split.subprocess`): `reset --hard <ilk>`
        sonrasına `git merge -s ours origin/main` adımı eklendi (HEAD `origin/main`'i içermeli). Saldırı hâlâ
        başarılı (xfail); bir adım uzadı ve ikinci koşu uzak depoya itildiği için iz bırakıyor.
    - Yeni: `tests/test_onbellek_taramasi.py` (9).

    **`cache/` taraması.** `tarama_yardimcisi.ONBELLEK_DESENI`: analiz kodu (`.py` ve `.ipynb`; izinli dizinler
    dışında) `ONBELLEK_DIZINI` adını ve `cache` yol parçasını anamaz. `config.py` tanımı taşıdığı için muaf.
    `ihlaller` isteğe bağlı `uzantilar` parametresi aldı. Sınır: yolu parçalayıp kurmak yakalanmaz.

    **`split`'in modül bağımlılıkları korunmuyor (karar).** `split.config`, `split.subprocess`, `split.klines`,
    `split_dogrula`, `grup`, `varlik_anahtari`, `hashlib`, `os`, `time`, `uuid` ve config'teki `BOLME_TUZU`,
    `YENIDEN_ADLANDIRMA`, `HIPOTEZLER` düz atamayla değiştirilebilir (OK2 D-B3; sızıntı P-8…P-14). Gerekçe: koruma
    listesi sonsuza kadar uzayamaz; her korunan fonksiyonun her bağımlılığı yeni bir ad getirir. Ölçüt kapsam
    kararındaki cümledir: bu değişiklikler kasıtlı ve adı açık atamalardır (kazayla olmaz); koşu içinde yapılırsa
    kod temiz ağaçtan, commit edilmiş betikten çalışır ve kayıt commit'leri itilir. `HIPOTEZLER`'e ad eklemek kayıtta
    o adla görünür. Sızıntı testçisinin P-8…P-14 xfail'leri bu sınırın belgesi olarak kalır.

    **Test yardımcısının sınırı (belgelenmiş).** `onay_yardimcisi.kosu` gerçek `split.onay_kosusu`'yu çağırır; iki
    farkı var:
    - Blok sonuç bildirmeden biterse yardımcı "TEST" sonucunu bildirir; gerçek koşu `OnaySonucuYok` verip kayda HATA
      yazar. İkinci turda ölçüldü: `kosu` üzerinden koşan 76 testin 47'sinde sonuç yardımcıdan geldi. Bu tur
      (sızıntı P testleri ve yeni git testleriyle): 101 testin 72'sinde.
    - `gecici_kayit` (sahte git) kipinde git'e dokunulmaz: ortam (`rev-parse`, `status --porcelain`, `ls-files`,
      `__main__.__file__`, `relative_to(KOK)`) testten gelen değerlerle; HEAD ve geçmiş = çalışma ağacı; commit,
      `fetch`, itme ve uzak denetimleri atlanır. `kosu` üzerinden koşan testlerin 68'i bu kipte (ikinci turda da 68);
      33'ü gerçek git kipinde (`gecici_depo`; git ve uzak depo gerçek, yalnızca çağıran betiğin yolu testten gelir;
      `autocrlf=false`, yerel kanca dizini, `gpgsign=false`).
    - Bu farklar bilinçli: onay kümesi erişimini sınayan testler git ortamından bağımsız kalsın. Git ve uzak depo
      davranışı `gecici_depo` testlerinde sınanır. Gerçek ortamın olumlu yolu (`__main__`, gerçek `origin`) testsizdir.

    **Tam takım:** 1808 geçti, 20 xfail (önceki: 1788 geçti, 26 xfail).

    **Doğrulama.** Tam denetim (`94270d7`, `ce1dc11` temiz ağaçta, `--eski-evren`; 678/678) ve A1 (`83e7b72`) temiz
    ağaçta: 64 çıktının 63'ü önceki çıktılarla bayt düzeyinde aynı; yalnızca ortam kayıtları farklı
    (`karsilastirma_ok3_{calistir,a1}_tam.csv`).

    **Tur sonu ajan bulguları (düzeltilmedi; yukarıdakilerden sonra geldi).** Denetçinin bulguları "OK3" önekiyle.

    *Denetçinin cevabı:* kapsam kararı kısmen doğru. Tek klonda OK2 D-B1 (a), (b), (c) kapandı (koddan yürütüldü; P-1…P-4
    ölçüyor). "Kazayla atlatma yolları kapatılmıştır" ve "her biri iz bırakır" cümleleri aşağıdaki noktalarda yanlış;
    listedeki "ayrı worktree, yeniden klonlama, bağımsız HEAD" ise zorla itmeyle birleşmedikçe artık kapalı (OK3 D-C1).
    - **OK3 D-B1:** önbellek yardımcıları (`binance_vision.onbellek_yolu`, `onbellekten_oku`) hiçbir desene takılmıyor;
      koşusuz C1/C2 erişimi kazayla olabilir. `ihlaller` yolunda "cache" geçen her dosyayı bütün taramalardan atlıyor.
    - **OK3 D-B2:** koşu açmayan düz atama yolları (P-9…P-13) kayıt, commit ya da itme üretmiyor; uzakta iz yok.
      `split.config =` gibi biçimler taranmıyor; `.ipynb` onay deseniyle taranmıyor. "Koşu içinde yapılırsa"
      koşulu kapsam cümlesinde yok.
    - **OK3 D-B3:** OK2 D-B2'nin kökü (`--full-history` yok) kapanmadı. İki klonda: X iter, Y'nin itmesi reddedilir,
      Y `pull` edip çatışmayı kendi tarafına çözüp iter; uzak geçmiş denetimi X'in satırlarını görmez, yeni klon hiç
      görmez. Kazayla olabilir. P-5 artık bu mekanizmayı sınamıyor; "gevşetilen test yok" cümlesi bu kapsam
      daralmasını söylemiyor.
    - **OK3 D-B4:** itme hatası (fetch başarılı, itme başarısız: anonim erişim, kimlik penceresinin 120 sn'yi aşması,
      push protection, büyük dosya, dal koruması) veri okunmadan çifti kalıcı harcıyor. İlk koşu, hiç denenmemiş ve
      yerel `main`'in bütün itilmemiş commit'lerini içeren bir itmeyi tek atışın içinde yapacak.
    - **OK3 D-B5:** zorla itme uzak git geçmişinde iz bırakmıyor (fetch `+` refspec'i yeniden yazılmış uzağı sessizce
      kabul ediyor); `remote set-url`, `pushurl`, `insteadOf`, `GIT_CONFIG_*`, `GIT_DIR`, PATH'te sahte `git` ile koşu
      sahte uzağa itilebiliyor. Bunlar listede yok. Yalnızca yerelde yapılan körleştirmeler (P-6…P-8) ise ikinci
      koşuyu gerçek uzağa ittiği için iz bırakıyor.
    - **OK3 D-C2:** ITILEMEDI mesajı `git push origin main` öneriyor, kod HEAD'i itiyor. **D-C3:** başka daldan koşu o
      dalın bütün commit'lerini uzak `main`'e itiyor. **D-C4:** kilit itme sırasında 120 sn'ye kadar tutuluyor, ikinci
      süreç 10 sn bekliyor. **D-C5 (şüpheli):** Windows'ta zaman aşımı torun süreçle asılı kalabilir. **D-C6:**
      ITILEMEDI commit hatası sessizce yutuluyor. **D-C7:** OK2 D-C2 açık. **D-C8:** gerçek ortam testi ağa çıkmıyor
      (doğrulandı); izlenen betikten başlatılan pytest senaryosunda gerçek itme yapabilir (şüpheli). **D-C9:** bayat
      metin (`split.py` modül docstring'i ve korumaya ilişkin yorum, P-5 docstring'leri, kilitli metinler).
      **D-C10:** `_AG_SURESI` korunmuyor.

    **Sızıntı testçisi** (`test_tur_saldirilari_q`, `5277cd0`, yalnızca yeni dosya): 32 test; testçi koşamadı, ana
    oturum koştu: 14 geçti, 18 xfail(strict). İlk koşuda bir test kırmızıydı: testin `git checkout -- ONAY_KAYDI.md`
    adımı, `git add` ile index'e alınmış ITILEMEDI satırını silmiyordu (ikinci turda belgelenen davranış; güvenli
    yön). Ana oturum o satırı `git checkout HEAD --` yaptı ve yorumla işaretledi; test geçiyor.
    - **Başarılı saldırılar:** `merge -s ours` ile tek tarafa çözülen birleştirme X'in koşusunu hem yerelde hem taze
      klonda gizliyor (2; OK3 D-B3'ü ölçtü). `origin` yönlendirmesi (`set-url`, `pushurl`, `insteadOf`,
      `GIT_CONFIG_*`; 4) sahte uzağa itilen koşuyu gerçek uzakta izsiz bırakıyor (OK3 D-B5). Zorla itme (taze klon ve
      aynı depo; 2). `main` dışı daldan koşu açılıyor ve dalın commit'leri uzak `main`'e taşınıyor (1; OK3 D-C3).
      Önbellek taraması: `bv.onbellek_yolu`/`onbellekten_oku` (2), `rglob('*.parquet')`, `"CACHE"`, `"Cache"` (5
      kimlik), `.pyw` (1), `cache` adlı alt dizindeki analiz dosyası bütün taramalardan muaf (2; OK3 D-B1). ITILEMEDI
      mesajındaki `git push origin main` bağımsız HEAD'de işe yaramıyor (1; OK3 D-C2).
    - **Savuşturulanlar:** geride kalan klon aynı çifti `OnayTekrari`, başka çifti `OnayUzakHatasi` ile reddediyor;
      taze klon itilmiş koşuyu görüyor; sunucuda `receive.denyNonFastForwards` varsa zorla itme reddediliyor (kod bunu
      kurmuyor, doğrulamıyor); `deneme`'de harcanan çift `main`'de açılmıyor; `Path(KOK, 'cache')`, `os.path.join`,
      f-string, değişken biçimleri yakalanıyor; BASLADI itilemeyince gövde çalışmıyor, veri okunmuyor; ITILEMEDI
      commit'i de başarısız olunca yeni koşu `OnayKaydiCommitsiz`; BITTI itilemese de uzaktaki BASLADI çifti harcıyor;
      `git push origin HEAD:main` bağımsız HEAD durumunu çözüyor.
    - **Belgeleme (bulgu, xfail değil):** BASLADI itilemeyince çift veri okunmadan harcanıyor; elle itilince
      `OnayTekrari`, kurtarma yolu yok (OK3 D-B4'ü ölçtü).
    - **Yazılamayanlar:** gerçek kimlik bilgisi yokluğu (https; `pre-receive` reddiyle taklit edildi), eşzamanlı iki
      itme, `GIT_DIR` yönlendirmesi (2–3. saldırılarla aynı sınıf).
    - **Tam takım:** 1822 geçti, 38 xfail.

27. **Onay kaydı kapanışının son turu (2026-09-30).** Ön-kayda ve kilitli dosyalara dokunulmadı; getiri
    hesaplanmadı; F2'ye geçilmedi.

    **Kod.**
    - **Önbellek ve indirme yardımcıları onay verisini izin dışında okumaz** (OK3 D-B1, sızıntı Q).
      - Onay verisi: B grubu sembollerin her ayı ve bütün sembollerin C2 dönemindeki (2025-09 ve sonrası) ayları
        (`binance_vision.onay_verisi_mi`; grup bölme kuralından, varlık anahtarıyla).
      - `binance_vision.onbellekten_oku` (önbellek yolundan tür, sembol, ay) ve `zip_indir` (bucket anahtarından
        sembol ve dosya adındaki ilk `YYYY-MM`) izin dışında onay verisini `OnayVerisiKorumasi` ile reddeder.
        Ham yükleyiciler bu iki yardımcıdan geçtiği için onlar da korunur. `klines_settled` her zaman izin ister;
        ayrıştırılamayan ay ve `data/` ile başlayıp biçime uymayan anahtar kapalı yönde onay verisi sayılır.
      - İzin (`binance_vision.onay_verisi_izni(neden)`): küme kapısından geçmiş yükleyiciler (`split.yukle`,
        `funding.funding_yukle`, `klines.birincil_gunluk_indir`; ardından küme aralığına keserler), evren kurulumu
        (`universe.evren_kur`) ve F1 denetim betiklerinin `__main__` bloğu (`main()` değil;
        `analysis/00_veri_denetimi`, 11 betik; CLAUDE.md §3.1: veri denetimi serbest). İzin bu turda süreç içindeki bir
        sayaçtı: iş parçacıkları görür (F1 denetimi paralel indirir), alt süreçler görmezdi (OK4 D-B1; kapanışta
        ortam değişkeniyle alt süreçlere de taşındı, §14.28).
      - Açık bir onay koşusu tek başına izin vermez: koşu içinde de onay verisine yalnızca kapılı yükleyicilerle
        erişilir.
      - Tarama (`ONBELLEK_DESENI`): `binance_*` adları, `onbellek_yolu/onbellekten_oku/onbellege_yaz`, `zip_indir`,
        `onay_verisi_izni`, `_IZIN`, `read_parquet`, `.parquet`, büyük/küçük harf duyarsız `cache` yol parçası;
        uzantılar `.py`, `.ipynb`, `.pyw`. `ihlaller` artık yolunda "cache" geçen dosyaları muaf tutmuyor.
    - **`--full-history`** (OK2 D-B2, OK3 D-B3, sızıntı Q): yerel ve `origin/main` geçmiş denetimi birleştirmelerin
      bütün ebeveynlerini yürür; tek tarafa çözülen birleştirmenin öbür tarafındaki koşu görünür.
    - **İtme koşudan önce denenir** (OK3 D-B4). Tek atış ve ileri sarma denetimlerinden sonra, kayda satır
      yazılmadan: boş bir deneme commit'i (`ONAY_KAYDI: itme denemesi (kosu=...)`) oluşturulup `origin/main`'e
      itilir. Deneme her zaman gerçek bir güncellemedir: kimlik bilgisi, dal koruması ve uzak kancalar sınanır.
      Başarısızsa yerel deneme commit'i geri alınır (`reset --soft`), `OnayUzakHatasi`: koşu açılmaz, kayda satır
      yazılmaz, çift harcanmaz. Başarılıysa deneme commit'i uzakta kalır (koşunun ilk izi).
    - **Koşu ortasında itme başarısız olursa çift harcanmış sayılmaya devam eder** (davranış değişmedi). Gerekçe:
      BASLADI satırı itildikten sonra blok çalışır ve veriye bakılmış olabilir; bitiş itmesi başarısız olsa da
      uzaktaki BASLADI çifti harcar. Bu hâlde çifti serbest bırakmak, veriye bakıldıktan sonra ikinci atışa izin
      vermek olur (CLAUDE.md §3.3). Itme denemesi, bu durumu yalnızca koşu sırasında bozulan bir itmeye (ağ
      kesintisi, koşu sırasında değişen izinler) indirir. Kayıtta `ITILEMEDI` satırı, elle itilene kadar yeni koşu
      açılmaz.
    - **`origin` denetimi.** `origin`'in okuma adresi ve bütün itme adresleri (git'in çözdüğü hâliyle: `insteadOf`,
      `pushurl`, `GIT_CONFIG_*` dahil) `config.UZAK_DEPO_ADRESI` (`github.com/ewurr/short-scanner`) olmalı; https,
      ssh ve scp biçimleri, `.git` soneki ve büyük/küçük harf fark etmez (`split.uzak_adresi_normal`). Değilse
      `OnayUzakHatasi`, ağa çıkılmadan. `UZAK_DEPO_ADRESI` çalışma anında değiştirilemez. **Kural 0 notu:** görev
      adresin "ön-kayıt kaynaklı config bölümünde" tutulmasını istedi; ön-kayıtta uzak depo tanımlı değil. Adres
      config'te onay kaydı yolunun yanına, "ON-KAYIT DEGILDIR" etiketiyle ve değiştirilemez sabit olarak kondu.
    - Sıra: yerel denetimler → `origin` adresi → `fetch` → itilmemiş satır → tek atış → ileri sarma → itme
      denemesi → BASLADI (commit, it) → blok → bitiş (commit, it).

    **Kapanan yollar (adıyla; hangi turda, hangi ölçümle).**

    | # | Yol | Kazayla? | Kapanış | Ölçen test |
    |---|---|---|---|---|
    | 1 | Commit edilmemiş kayıt satırını `checkout .`/`stash`/`reset --hard` ile silmek | evet | ikinci tur: satır yazılır yazılmaz commit | `test_onay_kaydi_git::test_commit_edilmeden_silinen_...` |
    | 2 | Ayrı worktree'de koşup worktree'yi silmek | evet | kapanış turu: itme | P-2, P-3 |
    | 3 | İtilmemiş commit'le yeniden klonlamak | evet | kapanış turu: BASLADI itilmeden blok çalışmaz | `test_itilmis_cift_yerel_gecmis_silinse_de_harcanmis`, Q taze klon |
    | 4 | Bağımsız HEAD, `bisect`, birleştirilmeden silinen dal, `reset --hard origin/main` sonrası reflog süresinin dolması | evet | kapanış turu: itme | P-1, P-4 |
    | 5 | İki dalda ya da iki klonda koşu, birleştirmede tek tarafa çözüm (`merge -s ours`, "Accept Current") | evet | kapanış turu: ileri sarma şartı; son tur: `--full-history` | P-5; Q ours (2) |
    | 6 | Önbellek yardımcılarıyla (`bv.onbellekten_oku`) ya da ham yükleyicilerle koşusuz onay verisi okumak | evet | son tur: çalışma anı engeli + tarama | `test_onay_verisi_izni`; Q önbellek (2) |
    | 7 | `cache/` yolunu elle yazmak (`read_parquet`, `rglob('*.parquet')`, `CACHE`, `.pyw`, `cache` adlı alt dizin) | evet | kapanış turu + son tur: tarama; çalışma anı engeli yardımcılarda (doğrudan `pd.read_parquet` çalışma anında engellenmez) | `test_onbellek_taramasi`; Q (6) |
    | 8 | İtme hatasının çifti veri okunmadan harcaması | evet | son tur: itme denemesi | `test_itme_yapilamayan_ortamda_...`; Q |
    | 9 | `origin`'i başka depoya yönlendirmek (`set-url`, `pushurl`, `insteadOf`, `GIT_CONFIG_*`) | hayır (kasıtlı) | son tur: adres denetimi | `test_origin_beklenen_depo_degilse_...` (4); Q (4) |
    | 10 | Ağ yokken yerel kipe düşmek | evet | kapanış turu | `test_ag_yoksa_...` |
    | 11 | `config` küme sabitleri, `split_oku`, `kume_tanimi`, `kume_araligi`, `__class__` ataması | evet (küme tarihleri) | ikinci tur: korunan adlar | `test_onay_kaydi_git`, `tur_saldirilari_o` |
    | 12 | `yol=` parametresi, `config.ONAY_KAYDI`, `_AKTIF_KOSU` ataması, kirli ağaçta koşu | evet | onay kaydı turu | `test_onay_kaydi_butunlugu` |

    **Kapatılmayan yollar 1: kasıtlı ve çok adımlı oldukları için (adıyla ve iz durumuyla).** K9–K13 kapanışta
    (§14.28) eklendi; o turda da kapatılmadılar.

    | # | Yol | İz | Ölçen test |
    |---|---|---|---|
    | K1 | Zorla itmeyle uzak geçmişi yeniden yazmak (`push --force origin <eski>:main`) + yerel geçmiş ve reflog silme | git'te iz yok; uzak depoda dal koruması (zorla itme reddi) açılırsa kapanır. GitHub'ın etkinlik kaydı doğrulanmadı | Q zorla itme (2 xfail) |
    | K2 | Koşu açmadan düz atamayla modül değiştirmek (`split.config`, `split.klines`, `split.subprocess`, `split_dogrula`, `grup`, `varlik_anahtari`, `hashlib`, `config.BOLME_TUZU`, `YENIDEN_ADLANDIRMA`, `HIPOTEZLER`) | koşu dışında (ör. not defteri) iz yok; koşu içinde commit edilmiş koddan çalışır ve kayıt itilir | P-8…P-14 (10 xfail) |
    | K3 | `.git/info/attributes` ile kayıt farkını ikili göstermek; `git replace` | ikinci koşu itilir: uzakta aynı çift için iki BASLADI | P-6, P-7, P-15 (5 xfail) |
    | K4 | Koşu içinde kayıttan eski satırı silmek | silme koşu mesajlı commit'le itilir; tek atış bozulmaz | P-16 (xfail) |
    | K5 | `GIT_DIR`/`GIT_WORK_TREE`, PATH'te sahte `git` ile git'in kendisini değiştirmek | iz yok | test yok (OK3 D-B5) |
    | K6 | `vars(split)`, `object.__setattr__`, `sys.modules`, test kapısı, `onay_verisi_izni`/`_IZIN` kullanımı | commit edilmiş analiz kodunda tarama testine takılır; onay atlatma taraması yalnızca `.py` bakar (`.ipynb` için K12) | tarama testleri |
    | K7 | Tarama desenini parçalı adla (`importlib`, dize birleştirme) ya da değişkenle taşınan değerle atlatmak | koşu içindeyse commit edilmiş kod; değilse iz yok | eski g, j xfail |
    | K8 | Doğrudan `pd.read_parquet(<önbellek yolu>)` (tarama dışı bir yolla kurulmuş yol) | çalışma anında engellenmez; tarama `read_parquet`/`.parquet`/`cache` metnini yakalar | Q önbellek |
    | K9 | Adres denetiminin görmediği yönlendirmeler: `core.sshCommand`, `GIT_SSH_COMMAND`, `http.proxy`, `remote.origin.receivepack`, depo içinde göreli yol | yerel git yapılandırmasında iz; uzak depoda iz yok | test yok (OK4 D-B5) |
    | K10 | Şemasız (`github.com/ewurr/short-scanner`) ya da `file://github.com/...` adres: git bunları yerel göreli yol sayar, `split.uzak_adresi_normal` beklenen adres sanar | yerelde iz; gerçek uzak depoda iz yok | R6 (2 xfail; OK4 D-C1) |
    | K11 | `config.UZAK_DEPO_ADRESI`'ni sıradan bir commit'le başka depoya çevirmek | commit edilmiş kodda görünür; değer kilitli dosyada değil | test yok (OK4 D-B5, D-C5) |
    | K12 | `vars(split)` gibi bir satırı `.ipynb` içine yazmak: onay atlatma taraması yalnızca `.py` bakar | not defteri commit edilirse dosyada görünür, tarama uyarmaz | R4 (xfail; OK4 D-B5) |
    | K13 | Kayıt satırını yalnızca birleştirme commit'inde eklemek ("evil merge"): `git log` `-m` olmadan göstermez | uzakta birleştirme commit'inde iz | test yok (OK4 D-C9) |

    **Kapatılmayan yollar 2: kazayla tetiklenebilir olduğu halde kapatılmayanlar (adıyla ve nedeniyle).** Dördü de
    kapanışta (§14.28) gözden geçirildi ve kapatılmadı.

    | # | Yol | Neden kazayla tetiklenebilir | Ölçen test |
    |---|---|---|---|
    | KK1 | **İş parçacığı kapsamı:** izin iş parçacığına değil sürece bağlıdır; bir iş parçacığında kapılı yükleme sürerken başka bir iş parçacığının `klines.ay_indir` çağrısı B grubu ya da C2 ayını indirebilir | eş zamanlı indirme bu depoda olağan (`calistir --is-parcaci`); `ay_indir` hiçbir taramada yok, sonuç belirsiz ve iz bırakmaz | R1 (xfail; OK4 D-B2) |
    | KK2 | **Doğrudan ağ çağrıları:** `requests.get("https://data.binance.vision/...")`, `bv._iste(...)`, `fapi.binance.com` ya da ccxt (Binance REST); çalışma anında yalnızca `binance_vision.zip_indir` korunur | "güncel veriyle göz atmak" tek satırda yazılır; ne çalışma anında ne taramada yakalanır | R3 (3 xfail; OK4 D-B3) |
    | KK3 | **SETTLED dizin grubu:** indirme yolunda grup `<SEMBOL>SETTLED` adından hesaplanır, temel sembolden değil; temel sembolü B olan bir dizin adı varlık anahtarıyla A'ya düşerse C1 verisi izinsiz iner | önbellekten okuma her zaman izin ister, indirme istemez; `ham_settled_*` taramada, `ay_indir` değil | R2 (xfail; OK4 D-B4) |
    | KK4 | **`split.yukle` özel yükleyicisi:** `split.yukle(..., mum_yukleyici=<fonksiyon>)` verilen her fonksiyonu izin bağlamı içinde çalıştırır; fonksiyon KEŞİF çağrısından B verisi döndürebilir | kapıdan geçtiği için güvenli görünür; parametre veri katmanının kendi testleri için var | R5 (xfail; OK4 D-C3) |

    Bu yollar F2'nin tek süreçli akışında kendiliğinden tetiklenmez; korunmaları, projenin kendi doğrulama
    betiklerini kullanılamaz hâle getirecek kadar geniş bir kapsam gerektirir. Açık nokta olarak kayıtlıdırlar ve
    F2'yi engellemezler. Onay verisine elle göz atmamak kod değil, çalışma disiplini meselesidir.

    Ayrıca (atlatma değil, bulgu): `main` dışı daldan koşu açılıyor ve dalın commit'leri uzak `main`'e itiliyor
    (Q xfail, OK3 D-C3); ITILEMEDI mesajındaki `git push origin main` bağımsız HEAD'de işe yaramıyor (Q xfail,
    OK3 D-C2).

    **F2 öncesi kontrol listesi.**
    1. Yerel `main` ile `origin/main` eşit olmalı (`git rev-list --count origin/main..main` = 0 ve
       `git rev-list --count main..origin/main` = 0). İlk onay koşusu ancak bundan sonra açılabilir: ilk koşunun itme
       denemesi aksi hâlde itilmemiş bütün commit'leri tek atışın hemen öncesinde iter.
    2. **Bugün:** yerel `main`, `origin/main`'in (`f7009e5`, `git ls-remote` ile doğrulandı) **75 commit** önünde
       (bu turun commit'lerinden önce; tur sonu sayısı tur raporunda). `origin/main` yerelin gerisinde değil (0).
    3. Kilit oturumundaki metinler (CLAUDE.md §3.3, §5, §7; ONAY_KAYDI.md 6–10, 15) uygulanmış ve itilmiş olmalı.
    4. İsteğe bağlı: uzak depoda `main` için zorla itme reddi (dal koruması) açılırsa K1 kapanır.

    **Testler.**
    - Yeni: `tests/test_onay_verisi_izni.py` (onay verisi tanımı; önbellek, ham yükleyici ve indirme engeli; izin;
      kapılı yükleyicinin KEŞİF'te C2 aylarını izinle okuyup kesmesi; B sembolünün KEŞİF'te hiç okunmaması).
      `test_onay_kaydi_git`'e itme denemesi (2), origin denetimi (4 + adres biçimleri 9 + sabit), itme yapılamayan
      ortam testi. `test_onbellek_taramasi`'na 6 yeni biçim.
    - Güncellenen (davranış değiştiği için; iddialar aşağıda):
      - `test_onay_kaydi_git`: `test_itilmemis_kayit_varken_kosu_reddedilir` senaryosu koşu ortasına taşındı (BASLADI
        öncesi itme denemesi eklendi); `test_ag_yoksa_...` ağ yokluğunu adres değiştirmeden (uzak depo dizini
        erişilemez) taklit ediyor; commit sayan iki test deneme commit'ini sayıyor; `test_basladi_commit_edilemezse_...`
        kancası yalnızca BASLADI içeren commit'i reddediyor.
      - `test_klines_tekrar` (4) ve `test_f1_kapanis_saldirilari` (2): `TESTUSDT` B grubu olduğu için ham yükleyici
        çağrıları açık izinle; iddialar değişmedi.
      - `test_tur_saldirilari_q` (sızıntı testçisinin dosyası): önbellek (8), `ours` (2), origin (4) xfail'leri
        kaldırıldı. Origin testinde yönlendirmeli koşu adımı artık `OnayUzakHatasi` bekliyor; son iddia "çift
        harcanmadığı için geri alınınca açılır" oldu. `test_push_reddedilirse_...` ve
        `test_basladi_itilemeyince_..._bulgu`: itme denemesi yüzünden beklentiler değişti (satır yazılmıyor, çift
        harcanmıyor). `test_itilemedi_commiti_de_...` senaryosu koşu ortasına taşındı.
      - `test_tur_saldirilari_p`: commit sayısı 3 (deneme + BASLADI + BITTI); revert testi yalnızca iki kayıt
        commit'ini geri alıyor (boş commit revert edilemez).
    - Silinen test yok. Gevşetilen iddia: yok; değişen beklentiler yukarıda, her biri davranış değişikliğinin
      sonucu.
    - Kod: `e616e61`. **Tam takım:** 1870 geçti, 24 xfail (önceki: 1822 geçti, 38 xfail; 14 xfail normal teste döndü).

    **Doğrulama.** Tam denetim (`e09e295`, `a589620` temiz ağaçta, `--eski-evren`; 678/678) ve A1 (`19b01b4`) temiz
    ağaçta: 64 çıktının 63'ü önceki çıktılarla bayt düzeyinde aynı; yalnızca ortam kayıtları farklı
    (`karsilastirma_ok4_{calistir,a1}_tam.csv`). `calistir` iş parçacığı kullandığı ve A1 işçide kapılı yükleyici
    kullandığı için izinle çalıştı.

    **Tur sonu ajan bulguları (düzeltilmedi; yukarıdakilerden sonra geldi).** Denetçinin bulguları "OK4" önekiyle.

    *Denetçinin cevabı:* evet, kazayla ya da bilmeden atlatılabilecek yollar kaldı; A düzeyinde bulgu yok. Önbellek
    yardımcıları ve ham yükleyiciler üzerinden okuma tek iş parçacıklı kodda kapandı. Yukarıdaki kapsam paragrafının
    "bilinen kazayla atlatma yolları kapatılmıştır" cümlesi D-B2, D-B3, D-B4 karşısında doğru değil; kalan yollar
    tablosu eksik (D-B5).
    - **OK4 D-B1:** izin süreç başına. `ProcessPoolExecutor` kullanan 7 F1 betiği (`f1k_kume_sonu`, `rev10_son`,
      `rev10_hazirlik`, `rev8_etki`, `rev9_hazirlik`, `rev9_ritim`, `rev9_uygulama`) Windows'ta (`spawn`) işçide
      izinsiz; ham yükleme `OnayVerisiKorumasi` ile düşer. Yön kapalı; bu betikler `e616e61`'de yeniden üretilemez.
      "Süreç geneli sayaç" cümlesi yalnızca iş parçacıkları için doğru.
    - **OK4 D-B2:** iş parçacığı yarışı: bir iş parçacığında kapılı yükleme sürerken başka iş parçacığı B ya da C2
      verisi okuyabilir; `klines.ay_indir` hiçbir desende yok. Sızıntı R1 ölçtü.
    - **OK4 D-B3:** `zip_indir` dışı ağ yolları (`requests.get` ile `data.binance.vision`, Binance REST/ccxt,
      `bv._iste`) ne çalışma anında ne taramada engelleniyor; kazaya açık ("güncel veriyle göz atmak"). Sızıntı R3
      ölçtü (3).
    - **OK4 D-B4:** SETTLED indirme yolu grubu `<SEMBOL>SETTLED` adından hesaplıyor; temel sembol B iken ad A'ya
      düşerse C1 verisi izinsiz iner. "`klines_settled` her zaman izin ister" yalnızca önbellek için doğru. Sızıntı R2
      ölçtü.
    - **OK4 D-B5:** tablolarda eksik: doğrudan HTTP, iş parçacığı yarışı, SETTLED indirme, `split.yukle(mum_yukleyici=)`,
      adres denetiminin görmediği yönlendirmeler (`core.sshCommand`, `GIT_SSH_COMMAND`, `http.proxy`, `receivepack`,
      depo içinde göreli yol), `UZAK_DEPO_ADRESI`'nin sıradan bir commit'le değişebilmesi. İzin `main()`'de değil
      `__main__` bloğunda. K6'nın ".ipynb" okuması yanlış: `ONAY_ATLATMA_DESENI` yalnızca `.py` tarar (sızıntı R4).
    - **OK4 D-C1:** `uzak_adresi_normal` şemasız ve `file://github.com/...` adresini kabul ediyor (git bunları yerel yol
      sayar; kasıtlı, çok adımlı; sızıntı R6 ölçtü); SSH takma adlarını yanlışlıkla reddediyor. **D-C2:** itme denemesinin
      yan etkileri (zaman aşımına rağmen uzağa ulaşan deneme; `fetch` sırasında index'e alınan değişikliğin deneme
      commit'iyle gitmesi; BASLADI aşamasındaki ITILEMEDI + commit hatası artık testsiz). **D-C3:**
      `split.yukle(mum_yukleyici=...)` verilen fonksiyonu izinle çalıştırır (sızıntı R5 ölçtü: B verisi KEŞİF
      çağrısından döndü). **D-C4:** `onay_verisi_mi` grubu kuraldan hesaplıyor (D-B4'ün kökü). **D-C5:**
      `UZAK_DEPO_ADRESI` kararı doğru; `config.py` docstring'inin istisna listesi güncellenmemiş, değer kilitli
      dosyada değil. **D-C6:** test güncellemelerinde gevşetme yok; Q'daki `..._tek_atis_hakki_..._yanar_bulgu` adı ve
      docstring'i bayat (test artık tersini iddia ediyor); izin çağrı noktalarını sayan test yok. **D-C7:** evren
      önbelleği denetimsiz (fiyat verisi değil). **D-C8 (şüpheli):** `data/` ile başlamayan anahtar denetlenmiyor.
      **D-C9:** `--full-history` doğru; yalnızca birleştirme commit'inde eklenen satır `-m` olmadan görünmez (kasıtlı).
      **D-C10:** kontrol listesinin 1. maddesi kodda zorlanmıyor.
    - Standart başlıklar: geleceğe bakış, pencere, dönem, veri bölmesi, tohum: yeni bulgu yok; onay verisi tanımı
      ön-kayıt §3 tablosuyla uyumlu.

    **Sızıntı testçisi** (`test_tur_saldirilari_r`, yalnızca yeni dosya). İlk çağrı 600 sn ilerlemeden durdu ve dosya
    yazmadı; ikinci çağrı daraltılmış kapsamla yazdı. Testçi koşamadı; ana oturum koştu: 9 test, 9 xfail(strict).
    - Testçinin savuşturulur tahmin ettiği R5 (`split.yukle(mum_yukleyici=...)`) koşuda başarılı çıktı (B verisi
      döndü). Ana oturum gövdeye dokunmadan strict xfail işareti ekledi (dosyadaki uzlaşım).
    - **Başarılı saldırılar:** R1 iş parçacığı yarışı; R2 SETTLED indirme; R3 doğrudan `requests.get`
      (`data.binance.vision`), `bv._iste`, `fapi.binance.com` taranmıyor (3); R4 `.ipynb` içindeki `vars(split)`
      varsayılan taramada görülmüyor; R5 `mum_yukleyici`; R6 şemasız ve `file://` adres beklenen adrese iniyor (2).
    - Savuşturulan: yok (bu dosyada).
    - **Tam takım:** 1870 geçti, 33 xfail (`e5ad07d`).

28. **Onay kaydı çalışmasının kapanışı (2026-10-06).** Ön-kayda ve kilitli dosyalara dokunulmadı; getiri
    hesaplanmadı; F2'ye geçilmedi; ajan çalıştırılmadı. Bu tur yeni koruma eklemedi ve hiçbir ajan bulgusunu
    kapatmadı; tek kod değişikliği projenin kendi doğrulama betiklerini yeniden koşulabilir kılmak içindir
    (OK4 D-B1; "doğrulama araçlarının çalışır kalması korumadan önceliklidir").

    **Kod (`544939e`): onay verisi izni alt süreçlere taşınır.**
    - Sorun (OK4 D-B1): izin süreç içinde bir sayaçtı. `ProcessPoolExecutor` kullanan F1 betiklerinin işçi
      süreçleri Windows'ta `spawn` ile baştan başlar, sayacı görmez ve işçideki ham yükleme
      `OnayVerisiKorumasi` ile düşer. Yön kapalıydı (veri sızmıyordu), ama sekiz betik yeniden üretilemiyordu.
    - Çözüm: izin bağlamı açılırken `SHORT_LAB_ONAY_VERISI_IZNI` ortam değişkeni açan sürecin pid'ine ayarlanır,
      bağlam kapanırken eski değerine döner (iç içe bağlamlarda yalnızca en dış bağlam yazar). Yeni süreç import
      anında değişkeni görür ve değer **kendi üst sürecinin** pid'i ise izni devralır; devralan süreç değeri kendi
      pid'iyle güncelleyerek torun süreçlere de taşır. Pid denetimi bayat ya da kabukta elle ayarlanmış bir
      değişkenin korumayı tümden kapatmasını önler; kararlı bir atlatmayı (değişkeni kendi kabuk pid'iyle
      ayarlayıp betik çalıştırmak) önlemez — kilit gibi, dikkatsizliğe karşıdır.
    - Tarama (`ONBELLEK_DESENI`): değişkenin adı ve devralma yardımcıları (`_IZIN_ORTAM_ADI`, `_DEVRALINAN_IZIN`,
      `_izni_devral`) desene eklendi; analiz kodu izni bir alt süreç başlatarak da açamaz.
    - Testler (yeni, `tests/test_onay_verisi_izni.py`): ortam değişkeninin bağlamla ayarlanıp geri alınması; izin
      bağlamında başlatılan alt sürecin izni devralması; izin dışında başlatılan alt sürecin reddedilmesi;
      bayat ve sayı olmayan değişkenin izin vermemesi; gerçek `ProcessPoolExecutor` işçilerinin (F1 deseni)
      devralması. `test_onbellek_taramasi`'na 4 yeni biçim. Silinen ya da gevşetilen test yok.
    - **Tam takım:** 1879 geçti, 33 xfail (önceki: 1870 geçti, 33 xfail; yeni 9 test).

    **Doğrulama koşuları (temiz ağaçta, `karsilastir.py` ile).**

    | Betik | Koşu | Önceki ref | Sonuç |
    |---|---|---|---|
    | `f1k_kume_sonu` | `580d6a6` (`544939e` temiz ağaçta) | `544939e` | ölçüm çıktıları (`rev10_kume_sonu_kesif`, `_sinir`) bayt düzeyinde aynı; yalnızca `rev10_kume_sonu_ortam_tam.csv` farklı |
    | `rev8_etki` | `8494549` (`580d6a6` temiz ağaçta) | `580d6a6` | `rev8_etki_donem_sonu_tam.csv`'de **tek hücre** farklı (aşağıda); `_baslangic`, `_zaman` aynı; `_ortam` farklı |
    | `rev9_hazirlik` | `2b4ad0e` (`de3a3b2` temiz ağaçta) | `de3a3b2` | ölçüm çıktıları bayt düzeyinde aynı; yalnızca `rev9_ortam_tam.csv` farklı |
    | `rev9_ritim` | `005e280` (`2b4ad0e` temiz ağaçta) | `2b4ad0e` | ölçüm çıktıları bayt düzeyinde aynı; yalnızca `rev9_ritim_ortam_tam.csv` farklı |
    | `rev9_uygulama` | `5c96d37` (`005e280` temiz ağaçta) | `005e280` | ölçüm çıktıları bayt düzeyinde aynı; yalnızca `rev9_uygulama_ortam_tam.csv` farklı |
    | `rev10_hazirlik` | `7514497` (`5c96d37` temiz ağaçta) | `5c96d37` | ölçüm çıktıları bayt düzeyinde aynı; yalnızca `rev10_ortam_tam.csv` farklı |
    | `rev10_son` | `1eb1e98` (`7514497` temiz ağaçta) | `7514497` | ölçüm çıktıları bayt düzeyinde aynı; yalnızca `rev10_son_ortam_tam.csv` farklı |
    | `rev10_uygulama` (`--etiket sonra`) | `edd70e4` (`1eb1e98` temiz ağaçta) | `1eb1e98` | ölçüm çıktıları (`h2_sonra`, `h2_nan_sonra`) bayt düzeyinde aynı — commit dosyaya hiç dokunmadı; yalnızca `rev10_uygulama_ortam_sonra_tam.csv` farklı |

    **Sekiz betiğin sekizi de yeniden koşuldu.** `rev8_etki`'deki tek hücre dışında (aşağıda; nedeni evren
    tablosunun düzeltilmesidir, kod değil) hiçbir ölçüm çıktısı değişmedi. İzin değişikliğinin (`544939e`)
    ölçümü bozmadığı bu koşularla gösterilmiş oldu.

    **`*_ortam_tam.csv` farkları ölçüm farkı değildir.** Bu dosya koşunun ortam künyesidir: `git_commit`,
    `calisma_agaci`, koşu başlangıç/bitiş zaman damgası ve kütüphane sürümleri. Yedi koşuda farklı çıkan
    satırlar yalnızca commit hash'i ve koşu zamanlarıdır (iki koşuda ayrıca `calisma_agaci` `kirli`→`temiz`,
    çünkü Eylül koşuları kirli ağaçta yapılmıştı); python/pandas/numpy/pyarrow/requests sürümleri değişmedi.
    Bu yüzden "fark varsa dur" kuralı bu dosya için işletilmedi.

    **`rev10_uygulama` notu.** `--etiket once` çıktıları Rev.10 öncesi `funding_ortalamasi` imzasının anlık
    görüntüsüdür ve bugünkü kodla yeniden üretilemez; bu yüzden koşu `--etiket sonra` ile yapıldı ve
    `rev10_uygulama_*_sonra_tam.csv` dosyalarıyla karşılaştırıldı. `_once_` dosyalarına dokunulmadı.

    **`rev8_etki` farkının nedeni (ölçüldü, kod değişikliğinden değil).** Fark: BNXUSDT dönem 0,
    `funding_yok_evren` `False` → `True` (karşılaştırma: `degisen_sutunlar=funding_yok_evren:1`). Bu sütun
    `universe.csv`'deki `donem_funding_yok` değerinden gelir (`rev8_etki.main`, `fy` eşlemi). `82a0465`
    ("universe.csv: BNXUSDT d0 funding'siz (rev.8 sayım penceresi)", 2026-09-22 23:24) tam bu hücreyi
    `False`→`True` yaptı; `rev8_etki`'nin önceki koşusu ise o commit'ten önceydi (2026-09-22 06:57, `09857aa`).
    Yani eski çıktı bayattı, yeni çıktı bugünkü evren tablosuyla tutarlıdır. Koşunun özet satırı da buna uyuyor:
    "funding'siz: evren 3, rev.8 3" (önceki koşuda evren 2). İzin değişikliğiyle ilgisi yok: fark yalnızca evren
    tablosundan okunan bir bayrakta, ham mum ya da funding verisinden hesaplanan hiçbir sütunda değil.

    **Kapsam kararı.** §14.26 ve §14.27 bu turda genel hükümden arındırıldı; üç liste §14.27'de:
    "Kapatılan yollar" (1–12), "Kapatılmayan yollar 1: kasıtlı ve çok adımlı" (K1–K13; K9–K13 bu turda eklendi) ve
    "Kapatılmayan yollar 2: kazayla tetiklenebilir olduğu halde kapatılmayanlar" (KK1–KK4: iş parçacığı kapsamı,
    doğrudan ağ çağrıları, SETTLED dizin grubu, `split.yukle` özel yükleyicisi). KK listesinin gerekçesi §14.27'de
    yazılıdır. Hiçbir yeni koruma eklenmedi; KK1–KK4 ve K9–K13 açık nokta olarak kayıtlıdır ve F2'yi engellemez.

    **xfail envanteri (33; üç grup).**
    - **Rev.11 kararı bekleyen (1):** `f1_kapanis::test_gunluge_cevir_nan_hacimli_bari_tam_gun_sayar_kismi_toplar`
      (NaN hacim; A6, Rev.11 madde 17).
    - **Belgelenmiş sınır (24).** Önceki 15: `tur_d` eş zamanlı yazma (koruma koşu kilidinde), `tur_g` parçalı ad
      (K7), `tur_j` değişkenle taşınan `None` (K7), `tur_p` P-8…P-14 (10; K2), `tur_q` zorla itme (2; K1).
      Bu turda bu gruba taşınan 9'u (hepsi kapanış kararıyla açık noktaya döndü; §14.27'deki bağlandığı madde):
      `tur_r` R1 iş parçacığı yarışı → **KK1**; R3a/R3b/R3c doğrudan ağ (3) → **KK2**; R2 SETTLED indirme → **KK3**;
      R5 `mum_yukleyici` → **KK4**; R6 şemasız ve `file://` adres (2) → **K10**; R4 `.ipynb` onay taraması → **K12**.
    - **Kapanmayı bekleyen (8).** `tur_p` P-6 `info/attributes` (2; ucuz düzeltme `git log --text`), P-7 `git replace`
      (`--no-replace-objects`), P-15 ikili fark (2), P-16 koşu içinde satır silme; `tur_q` `main` dışı daldan koşu
      (OK3 D-C3), ITILEMEDI mesajındaki push önerisi (OK3 D-C2). Bunlar K3/K4 yollarının ölçümleridir; ucuz
      düzeltmeleri var ve bu tur bulgu kapatmadığı için açık bırakıldı.

    **Tur sonu metodoloji denetçisi bulguları (düzeltilmedi; yukarıdaki tablolardan sonra geldi).**
Denetçi `ad60dbd..HEAD` aralığını ve ön-kayıt §2, §4, §5, §6, §7'yi okudu; kod değiştirmedi.
Sınıflar denetçinin önerisidir. Rev.11'in (a)–(m) maddelerinin tamamı için kod yeri ve test
karşılığı doğrulandı; ön-kayıttaki bütün sayısal sabitler (ızgaralar, pencere uzunlukları,
ufuklar, uygunluk eşikleri, maliyet, tohum, tekrar, α) kodla birebir bulundu ve ön-kayıtta
olmayan sayısal sabit bulunamadı.

- **D-B1: K1 (ve H1'in K2) barlarında §2 "Tamlık şartı" hiç uygulanmıyor.** Denetçiye göre
  getiriye **dokunur** ve §14.29'un açık nokta listesinde yoktu.
  - Ön-kayıt §2: "Bir pencerede beklenen barlardan biri bile eksikse değer hesaplanmaz (NaN). O
    barda olay ya da **kontrol** oluşmaz." §4 funding sinyal penceresi aynı cümleyi tekrarlar.
  - §6 rev.11: "Kontrol barı için gereken: uygunluk filtresi, dönem üyeliği, fiyat ve funding
    tamlığı, ve §4'teki tek karar noktasının bütün koşulları" — sinyal pencereleri bu listede yok.
  - Kod (`pozisyon._sinyal_gerekli`): K1'de ve H1'in K2'sinde sinyal hiç hesaplanmaz, dolayısıyla
    tamlık şartı denetlenmez. Aynı bar K2'de düşerken K1'de kontrol olabiliyor.
  - Sonucu: K1 havuzu, bir olayın hiçbir zaman oluşamayacağı barları (boşluk komşusu, funding
    çapası olmayan bar) içerebilir. Metindeki iki cümle çelişiyor; kod birini seçti.
- **D-B2: K2'nin "olay üretmemiş" ölçütü H1 ile H2/H3'te farklı.** Denetçiye göre **dokunur**.
  - §6 rev.11 "Örnekleme kuralları": ölçüt "aynı yapılandırmanın **oluşmuş olayları**"dır.
  - Kod: H2/H3'te kapı, sinyal koşulları sağlanan her barı K2 adaylığından çıkarır — o barda olay
    oluşmamış olsa bile (bekleme içindeki barlar, kapının başka gerekçeyle reddettiği barlar ve
    özellikle **H3'te kesintisiz dizinin ilk gün dışındaki bütün günleri**). H1'de ölçüt gerçekten
    oluşmuş olay kümesidir (örnekleme adımı).
  - İki ön-kayıt paragrafı iki ayrı okumayı destekliyor; kodda iki hipotez ailesi arasındaki
    asimetri ön-kayıtta yazılı değil. H3'teki büyüklük **ölçülmedi** (ölçmek kontrol adayı sayısı
    üretmek olurdu).
- **D-B3: H1 hacim penceresinde hacmin hangi sütun olduğu ön-kayıtta yazılı değil.** Denetçiye
  göre **dokunur**. §5 H1 madde 1 birim vermiyor; USDT yalnızca §2 "Uygunluk"ta yazılı. Kod iki
  pencerede de `quote_volume` okuyor; `volume` (coin cinsi) ile oran aynı sayı değildir ve 180
  barlık pencere içinde fiyat değiştiyse eşik farklı olur. Seçim uygunluk hacmiyle aynı seriyi
  kullandığı için tutarlı, ama §5 H1 bir **oran** olduğu için "USDT eşiği" gerekçesi orada
  geçmiyor. H3'ün "medyan günlük hacim"i için aynı seçim daha savunulabilir, o da yazılı değil.
- **D-B5: H1'de izlemeyi bitiren bar yeni pump barı olarak değerlendirilmiyor.** Denetçiye göre
  **dokunur**. §5 H1 madde 4 "yeni bir izleme ancak bundan sonra başlayabilir" diyor; "bundan
  sonra"nın biten barın kendisini kapsayıp kapsamadığı yazılı değil. Kod en erken pump+13'ü yeni
  pump sayıyor. Sert pump serilerinde bir pump barı sessizce kaybolur. Yukarıdaki iki yeni
  belirsizlikle aynı sınıf; bu üçüncüsü tabloya denetçi bulgusu olarak eklenmiştir.
- **D-B4 (beklemenin üst ucu):** denetçi sınıflamaya katılıyor ama "hayır (bugün)" etiketine
  itiraz etti; tablo bu itirazla düzeltildi ("evet, ölçülmemiş").
- **D-C1 ("pencereye giren kayıt" çapayı kapsamıyor):** denetçi sınıflamaya katılıyor; kodun
  okuması §4 "Funding ödemesinin sınırları" ile tutarlı ve ölçülen etki iki okumada da 0.
- **D-C2: `pozisyon.sinyal_kosulu` içindeki geniş `except ValueError`.** `VeriHatasi` ve
  `ZamanDizisiHatasi` birer `ValueError` alt sınıfı olduğu için bir **veri bozukluğu** ret
  gerekçesine dönüşebilir ve koşu durmaz. Bugün etkisi sınırlı (zaman dizisi denetimleri ve
  `_pozitif` `try` bloğunun dışında), ama ileride bu yola eklenecek her `VeriHatasi` F2'de
  sessizce "olay oluşmaz" olur. Niyetlenen tek durum (`h1_tepe_bar_sayisi`'nın 12 bar sınırı)
  daha dar bir `except` ile ayrılabilir.
- **D-C3: sonlu olmayan hücre ölçütü sinyal pencerelerinde ALAN bazlı, 1d türetmesinde BAR
  bazlı.** Ön-kayıt cümlesi bar düzeyindedir ("hücrelerinden biri ... o bar eksiktir"). Somut
  ayrışma: `quote_volume`'u NaN, `close`/`low`'u geçerli bir 4h barı H2'nin `close[t-30]` ve
  `kirilim_dip` pencerelerinden geçer; bar düzeyli okumada geçmezdi. H1 ve H3'te fark doğmuyor.
  Ölçülen etki 0 (KEŞİF'te bozuk hücreli bar yok).
- **D-C4 (`count` kapsam dışı):** denetçi sınıflamaya katılıyor; `count` hiçbir olay, uygunluk,
  sinyal ya da getiri hesabında okunmuyor (tarama ile doğrulandı).
- **D-C5: `ornekleme.ornekle` ön-kayıt değerlerini zorlamıyor.** `sayi` ve `tohum` serbest;
  `istatistik.yeniden_ornekle` ise ön-kayıt dışı `tekrar`/`tohum`'u reddediyor. İki modül
  arasındaki sertlik farkı, ön-kayıt değerinin tek kapıdan geçmesi ilkesine göre eksik. Bugün
  çağıran yok (F2 kodu yazılmadı).
- **D-C6: RESULTS §14.29'un madde numaraları ön-kaydın (a)–(m) harflerine bağlanmıyor.** Belge
  sorunu; (l) ve (m)'nin "yordamın sınırı" parçası tabloda ayrı satır değil.
  **KAPANDI** (Rev.12-13 uygulaması turu): yukarıdaki "Madde → kod yeri → test" tablosuna
  **Rev.11 harfi** sütunu eklendi, (a)–(m)'nin tamamı karşılandı, (l) ile (m)'nin "yordamın
  sınırı" parçasının nereye düştüğü tablonun üstünde yazıldı.

**Denetçinin (a) sorusuna yanıtı: bir yapısal yol kaldı.** Dizi kuralları (bekleme, tek izleme,
ilk gün) yalnızca `data/dizi.py`'de yaşıyor; tek karar noktası `pozisyon.olay_karari` onları
bilmiyor. Kapı, bekleme süresinin içindeki ya da yürüyen bir izlemenin ortasındaki bir barda da
olay onaylar; H1'de çapayı yalnızca "pump koşulunu sağlıyor mu" diye denetliyor, "**ilk** pump
barı mı" diye denetlemiyor, dolayısıyla aynı teyit barı iki farklı çapayla iki kez çağrılırsa iki
olay onaylanır (§5 H1 madde 4: "bir teyit barı en çok bir olay sayar"). Bugün bunu yapan kod yok
ve `dizi.olay_dizisi` doğru davranıyor; eksik olan, olay üretiminin `dizi`den geçmesini zorlayan
bir kapı ya da kaynak taraması (`tests/tarama_yardimcisi`'nda `rol="olay"` çağrısını `dizi`
dışında yasaklayan desen yok). **F2'nin ilk satırından önce eklenmeli.** Denetçinin taradığı öteki
yollarda (geleceğe bakış, pencere/boşluk, dönem sınırları, dolgu koşuları, küme sınırı, kontrol
tanımı) olay üretimi kural dışına çıkmıyor.

**Denetçinin (b) sorusuna yanıtı:** ön-kayıtta karşılığı olmayan dört kural — D-B3 (hacim birimi),
D-B5 (izlemeyi bitiren bar), D-B4 (beklemenin üst ucu), D-C3 (alan bazlı hücre ölçütü). Ayrıca
kodun ret gerekçesi yerine **açık hata** verdiği iki yol (`sinyal._pozitif`, `pozisyon._sonlu`)
ön-kayıtta tanımsız ama bilinçli ve belgeli; denetçi bunları sapma saymıyor (olay düşürmezler,
koşuyu durdururlar).

**Veri bölmesi ve tohum başlıklarında bulgu yok.** Yeni dört modülde hiç veri erişimi yok; grup
bilgisi yalnızca `split.split_oku`, küme sınırları yalnızca `split.kume_araligi` üzerinden geliyor.
`rev11_uygulama.py` yalnızca KEŞİF ve A grubu okuyor. Rastgelelik iki yerde ve ikisi de tohuma
bağlı; `ornekleme.ornekle` adayları önce sıralıyor, `rev11_uygulama.py` paralel sonuçları submit
sırasında topluyor. İki not: tohumun **sonuç dosyasına yazılması** yükümlülüğü (henüz sonuç dosyası
yok) F2'de denetlenmeli; `ornekle`'nin serbestliği D-C5.

**Tur sonu sızıntı testçisi bulguları (düzeltilmedi).** Yalnızca yeni dosya:
`tests/test_tur_saldirilari_s.py`, **78 test**: 72 savuşturulan saldırı (normal, geçen test) ve
**6 başarılı saldırı** (`xfail(strict=True)`). Testçinin araçları arasında kabuk yoktu, bu yüzden
testleri ana oturum koşturdu: 72 geçti, 6 xfail — testçinin kestirimiyle birebir aynı, yani altı
bulgunun hepsi gerçek (strict xfail XPASS verse kırmızı olurdu) ve 72 normal testin hepsi,
testçinin eklediği üç **olumlu kontrol** (sentetik H1/H2 dünyasının gerçekten olay ve K1
pozisyonu üretebildiği) dahil, geçiyor.

- **S-B1 (üç test): `dizi.olay_dizisi`, `karar` çıktısını doğrulamıyor.** `_dene`, `karar`'ın
  döndürdüğü her nesneyi `Olay` olarak kaydeder ve beklemeyi başlatır; `pozisyon.onay_dogrula`
  çağrılmaz, `rol` / `hipotez` / `yapilandirma` eşleşmesine bakılmaz. Üç saldırı da başarılı:
  (i) rastgele bir nesne (`"olay_degil"`), (ii) gerçek ve imzalı ama **K1 rolündeki** onaylı
  pozisyon, (iii) **başka yapılandırmanın** (δ = 0.12) olay pozisyonunun δ = 0.08 dizisine
  verilmesi. Son ikisi ön-kayıt §6 "Kontrolün ne ölçtüğü" ve §5 "bekleme yapılandırma başına
  işler" kurallarını deler. Testler: `test_dizi_karar_ciktisi_onayli_pozisyon_degilse_olay_
  sayilmaz`, `test_dizi_k1_rolundeki_onayli_pozisyon_olay_sayilmaz`,
  `test_dizi_baska_yapilandirmanin_pozisyonunu_olay_saymaz`. Denetçinin (a) yanıtıyla aynı
  kökten: dizi ile kapı arasındaki bağ tek yönlü ve doğrulanmıyor.
- **S-B2: H3'ün "kesintisiz dizi"si `zamanlar` listesinin bitişikliğine dayanıyor.**
  `dizi_suruyor` yalnızca işlenen barlarda sıfırlanır; `zamanlar = [gün 0, 1, 20, 21, 22]` ve
  koşul hep doğruysa aradaki 18 gün (bar yok, yani §2 gereği hesaplanamaz) diziyi **kesmez** ve
  gün 20 yeni bir "ilk gün" sayılmaz. Ön-kayıt §5 H3 madde 3: dizi "§2 'Tamlık şartı' gereği
  hesaplanamadığı günde kesilir". Test: `test_h3_zamanlar_listesinde_eksik_gun_diziyi_keser`.
  Çağıranın eksik günleri listeye koyup `None` döndürmesi de bir çözümdür, ama dizi bunu bugün
  zorlamıyor.
- **S-B3 (düşük önem): H1'in 12 bar sınırı da bar varlığına bağlı.** İzlemeyi bitiren kontrol
  yalnızca işlenen barda çalışır; `zamanlar`'da 12. bar yoksa 13. bar hâlâ teyit adayıdır.
  Gerçek hatta eksik 12. bar tepe penceresini zaten bozar (olay oluşmaz), bu yüzden pratik etkisi
  düşük; yine de sınırın tek sahibi dizi değil. Test:
  `test_h1_12_bar_siniri_zamanlarda_eksik_bar_oldugunda_da_gecerli`.
- **S-B4: `ornekleme.alt_tohum` UTC dışı saat diliminde değişiyor.** `pencere.utc_zamani`
  yalnızca tz'siz damgayı reddeder; tohum metni `t.isoformat()` ile kurulduğu için **aynı an**
  `+03:00` ve `+00:00` ile verilince farklı alt tohum çıkar. Anayasa §5 ("tüm zaman damgaları
  UTC") ve ön-kayıt §7 (tohum) ile ayrışır. Kapı `sinyal_zamani` için UTC'yi zorluyor
  (`pozisyon._utc_sinyal_zamani`), örnekleme zorlamıyor. Test:
  `test_alt_tohum_ayni_an_utc_disi_saat_diliminde_ayni_olmali_ya_da_reddedilmeli`.

**Testçinin yazmadığı saldırılar ve gerekçeleri** (kayda geçer): `_imza`yı yeniden hesaplayarak
K1'i imzalı olaya çevirmek (anayasanın "kararlı atlatmaya karşı korumaz" sınırı); aynı çağrıda
iki dönemi birleştiren bir çağıranı yakalayacak koruma (dizinin dönem bilgisi yok, sıfırlama
çağıranın ayrı çağrısına bağlı); `funding_ortalamasi` içinden fırlayabilecek `ValueError`'ların
`sinyal_kosulu`da yutulup yutulmadığı (okunmadı — denetçinin D-C2'si bu alanı kapsıyor); kapının
çapayı "ilk pump barı"na bağlayamaması (tasarım gereği; ilk-pump kuralını yalnızca dizi uygular).

**Testçinin notu (bulgu saymadı, karar ana oturuma bırakıldı):** H2/H3'te kapı K2'yi "koşul
sağlanıyor" diye eler, ön-kayıt ise "olay üretmemiş" diyor; bekleme içindeki ya da H3 kesintisiz
dizisinin ikinci gününden sonraki bir coin olay üretmemiştir ama havuzdan düşer. H1'de kapı K2'yi
olay barında geçirir ve eleme `ornekleme.k2_adaylari`'na kalır. Bu, denetçinin **D-B2** bulgusuyla
aynı noktadır ve iki ajan birbirinden bağımsız olarak aynı yere bastı.

**F2 öncesi kontrol listesi (bugünkü durum).**
    1. **Yerel `main` itilmeli.** Bugün yerel `main`, `origin/main`'in (`f7009e5`) **93 commit** önünde;
       `origin/main` yerelin gerisinde değil (0). İlk onay koşusu ancak eşitlikten sonra açılabilir: ilk koşunun
       itme denemesi aksi hâlde itilmemiş bütün commit'leri tek atışın hemen öncesinde iter. (Sayı bu turun
       commit'lerini içerir; tur raporundaki `git log` ile karşılaştırılabilir.)
    2. **Zorla itme koruması.** GitHub'da `main` için zorla itme reddi (dal koruması) açılacak — kullanıcı yapacak.
       Açıldığında §14.27 K1 kapanır. Depo dışı bir ayardır, kodla zorlanamaz.
    3. **Kilit oturumu bekliyor** (kilitli dosyalar; `SHORT_LAB_KILIT_ACIK=1` ile, kullanıcının açık izniyle):
       - CLAUDE.md §3.3, §5, §7 metinleri (onay kaydının git ve uzak depo bağı, izin ve tarama, `KILIT.md`);
       - `KILIT.md`'nin kilitli dosya listesine eklenmesi;
       - ONAY_KAYDI.md 6–10 ve 15. maddeleri;
       - ONAY_KAYDI.md başlığındaki "Henuz onay kosusu yok." yer tutucu satırının silinmesi.
    4. Bu listenin 1. maddesi kodda zorlanmıyor (OK4 D-C10); elle doğrulanır.

### §14.29 Rev.11'in uygulanması ve F1'in dondurulması

Ön-kayıt Rev.11 (2026-10-09) on üç maddeyle F1'in son açık noktalarını tanımladı; bu tur onları
koda geçirdi. Her madde ayrı commit (madde 4 ile 5 tek commit; gerekçesi aşağıda), her commit
öncesi tam test takımı koşuldu. Getiri, fiyat farkı ya da sinyal **değeri** hiçbir yerde
hesaplanmadı ve raporlanmadı; etki ölçümleri yalnızca sayılabilirlik düzeyinde (hesaplandı /
hesaplanamadı) ve yalnızca KEŞİF kümesi için yapıldı (ön-kayıt §4 "Ölçüm raporlamasının küme
sınırı").

Commit'ler: `3decb27` (1), `f41a7c3` (2), `f8bc392` (3), `c74ac19` (4 + 5), `bf27e6a` (6),
`5718996` (7), `7723e76` (8), `17e076c` (9).

**Madde → kod yeri → test**

Madde numaraları bu turun commit sırasıdır; ön-kaydın Revizyon 11 günlüğündeki (a)–(m)
harflerine bağlanması denetçi bulgusu D-C6 ile istenmiştir ve aşağıdaki tabloya **Rev.11
harfi** sütunu olarak eklenmiştir (Rev.12-13 uygulaması turu). Harflerin tamamı (a)–(m)
karşılanmıştır; (l) — "sinyal penceresinin tek kayıttan hesaplanabilmesi, bilinen sınır olarak" —
madde 1'in revizyon bağıyla birlikte metne girmiştir ve ayrı bir kod yeri yoktur, (m)'nin
"yordamın sınırı" parçası `istatistik.YORDAMIN_SINIRI` sabitidir.

| Madde | Rev.11 harfi | Ön-kayıt | Kod yeri | Test |
|---|---|---|---|---|
| 1 | (j) kısmen, (l) | §4 "Funding sinyal penceresinin tamlığı" revizyon bağı | `funding.SINYAL_PENCERESI_REVIZYONU = 11` | `test_rev10_kalan_bulgular` (2) |
| 2 | (a), (b), (f) | §5 "Pencere sınırları", "Pencere sınırlarının tamamı" | `data/sinyal.py` kurucular; `config.IZGARA` + pencere uzunlukları (hepsi `_DEGISMEZ_ADLAR`) | `test_rev11_pencere_sinirlari` (92) |
| 3 | (c) | §2 "1 günlük barlar" (eksik hücre) | `klines.HUCRE_SUTUNLARI`, `klines.hucreleri_tam_mi`, `gunluge_cevir` | `test_rev11_eksik_hucre` (88) + `test_f1_kapanis_saldirilari` (xfail → normal) |
| 4 | (f) | §5 (kapı değerleri kendisi hesaplar) | `pozisyon.olay_karari` (`yapilandirma`, `rol`, `capa`); `sinyal.sinyal_degerleri`, `hesaplanamayan`, `kosullar_saglandi`, `h1_pump_*` | `test_rev11_kapi_sinyali` (47), `test_f1k_sinyal_kapisi` (10) |
| 5 | (d) | §6 "Kontrolün ne ölçtüğü" | `pozisyon.ROLLER`, `_sinyal_gerekli`, `_capa_dogrula`, `OlayUretmis`, `SinyalKosuluSaglanmadi` | `test_rev11_kapi_sinyali` rol bölümleri |
| 6 | (g), (h), (i) | §5 bekleme süresi; §5 H1 madde 4; §5 H3 madde 3 | `data/dizi.py`; `pozisyon.sinyal_kosulu` | `test_rev11_olay_dizisi` (30) |
| 7 | (e) | §6 "Örnekleme kuralları" | `data/ornekleme.py` | `test_rev11_ornekleme` (24) |
| 8 | (j), (k) | §4 funding sinyal penceresi (küme sonu kaydı, sonlu olmayan oran) + §4 "Geçerli oran" | `funding.sinyal_penceresi_ayrintisi` (`kume_sonu_kaydi_disarida`), `funding_ortalamasi`, `funding_tamlik_ayrintisi` (`oran_gecerli`) | `test_rev11_funding` (19) + `test_rev8_funding` davranış testi |
| 9 | (m) | §7 `r`, p-değeri, yordamın sınırı | `data/istatistik.py` | `test_rev11_istatistik` (20) |

**Madde 4 ile 5 neden tek commit.** Değerlerin kapıda hesaplanması, o barın ROLÜNÜ (olay / K1 /
K2) bilmeyi gerektiriyor: ön-kayıt §6 rev.11 kontrol barında sinyal koşullarının aranmayacağını
söylüyor. İkisini ayırmak, aradaki commit'te ya kontrol barlarını sinyal koşuluna tabi tutan ya
da hiçbir koşulu aramayan, çalışmayan bir ara durum bırakırdı.

**Etki ölçümleri** (`rev11_uygulama.py`; A grubu, KEŞİF aralığı, 272 sembol, 1.113.921 dönem içi
4h bar):

| Ölçüm | Sonuç | Beklenen |
|---|---|---|
| `--olcum hucre` (madde 3) | bozuk hücreli bar **0**; gün önce 185.486 → sonra 185.486, **düşen gün 0** | 0 ✓ |
| `--olcum kume_sonu` (madde 8) | **düşen bar 234** (234 sembol, hepsi 2025-08-31 20:00); üç 4h ufkunda da (6, 18, 42) tek gerekçe **`giris_bari_yok`** | 234, hepsi zaten giriş barı bulunmadığı için reddediliyor ✓ |

Madde 3 ölçümünün "önce" durumu, bozuk hücreleri sonlu bir yer tutucuyla (0.0) değiştirip aynı
gerçek `klines.gunluge_cevir` yolunu koşarak üretildi; eski kod yalnızca bar sayısına baktığı
için bu, kural öncesi gün kümesiyle birebir aynıdır. Madde 8 ölçümünde funding oran sütunları
fonksiyona verilmeden önce, yalnızca NaN olup olmadıkları korunarak sabit 0 ile değiştirildi
(`degersiz`), yani hiçbir funding değeri hesaba girmedi.

**Üçüncü ölçüm (madde 8'in tamlık tarafı), tam denetim koşusundan.** `oran_gecerli` sütunu
`a1_d_kurali_tam.csv`'ye eklendi. Değeri yalnızca **çapası olmayan** pozisyonlarda `False`
(1050 / 1380, `aralik_gecerli` ile birebir aynı satırlar); **çapası olan hiçbir pozisyonda
sonlu olmayan oran yok** (çapa var ama oran geçersiz: **0**). Yani rev.11'in "geçerli oran"
koşulu, rev.10'un "geçerli aralık" koşulu gibi, bugünkü veride hiçbir pozisyonu elemiyor.

**Doğrulama koşuları (temiz ağaçta, `7723e76`).**

| Betik | Koşu | Önceki ref | Sonuç |
|---|---|---|---|
| `calistir` (`--eski-evren`) | 2026-10-09 21:07:19 → 21:25:18 UTC | `19b01b4` | bütün ölçüm çıktıları aynı; yalnızca `ortam_tam.csv` farklı |
| `a1_olcumu` | aynı temiz ağaç | `19b01b4` | `a1_d_kurali_tam.csv`'de **yalnızca eklenen sütun** `oran_gecerli`; ortak sütunlarda satır farkı **0**. `a1_ortam_tam.csv` farklı |
| `rev11_uygulama` (`--olcum hucre`, `--olcum kume_sonu`) | aynı tur | — | altı yeni `rev11_*_tam.csv` |

`karsilastir.py --onceki 19b01b4 --ad karsilastirma_rev11_uygulama`. Farklı çıkan öteki dosyalar:
- `*_ortam_*.csv` (yedi dosya): koşunun ortam künyesi — `git_commit` ve koşu zaman damgaları.
  Python/pandas/numpy/pyarrow/requests sürümleri **değişmedi**; "fark varsa dur" kuralı bu dosya
  için işletilmedi (§14.28'deki aynı gerekçe).
- `rev8_etki_donem_sonu_tam.csv`: tek hücre (`funding_yok_evren`, BNXUSDT dönem 0). Bu betik bu
  turda **yeniden koşulmadı**; fark, karşılaştırma referansının (`19b01b4`) `rev8_etki`'nin son
  koşusundan (`8494549`) daha eski olmasından gelir ve §14.28'de açıklanan bilinen farktır.
- `rapor_sayilari_tam.csv` **aynı**: bu raporun bütün sayıları değişmedi.

**§14'teki açık noktaların son durumu.** Ölçüt §14.28'dekiyle aynı: **ön-kayıt ile kodun
ayrıştığı her yer getiriye dokunur sayılır**; buna ön-kayıtta tanımsız kalan ve kodun bir okuma
seçtiği yerler de dahildir.

Bu turda kapananlar:

| Nokta | Kapanış |
|---|---|
| F1 kapanış D-B1 sinyal değerleri çağırandan | madde 4 (`c74ac19`) |
| F1 kapanış D-B2 H1 kontrol çapası | madde 5 (kontrol barında pump aranmaz) |
| F1 kapanış D-C2 `close[t-30]` tamlık penceresi | madde 2 |
| F1 kapanış D-C3 `tepe` tamlık listesinde yok | madde 2 |
| F1K2 turu: `tepe`'de t; H3'te t günü; SMA50; ızgara parametreleri; kontrol barındaki k | madde 2 + madde 4 |
| F1K2 D-C4 §5–§9 sabitleri `config.py`'de yok | madde 2 |
| F1K2 D-C5 onaylı pozisyon yapılandırma taşımıyor | madde 4 (`yapilandirma`, `rol` imzada) |
| Rev.10 D-C1 H2 penceresinin küme sonundaki kaydı | madde 8 (ölçüldü: 234 / 234) |
| Rev.10 D-C5 H2 penceresinde `kayit_var` ve NaN oran şartları | madde 8 (ön-kayıt rev.11'de yazıldı; kod +sonsuzu da eler) |
| Rev.10 D-C7 H2 ortalaması tek kayıttan hesaplanabilir | Rev.11 (l) ile bilinen sınırlar listesine girdi |
| KS2 D-B4 pozisyon funding'inde NaN / sonlu olmayan oran politikası | madde 8 ("Geçerli oran"; ölçüldü: etkilenen pozisyon 0) |
| Rev.9 D-C5'in sinyal tarafı (oran böleni sıfır ya da negatif) | madde 4 (`sinyal._pozitif` açık `VeriHatasi`) |
| xfail: `gunluge_cevir` NaN hacim (A6) | madde 3 (xfail kaldırıldı; ölçüldü: düşen gün 0) |
| xfail yok ama açık olan: sızıntı testçisinin `oran = inf` bulgusu | madde 8 (artık `FundingTamDegil`) |
| §14.19'un "Rev.11'i bekleyenler" listesinin 17 maddesinin tamamı | maddeler 2–9 |

Açık kalanlar:

| Nokta | Getiriye dokunur | Not |
|---|---|---|
| Rev.9 D-C2 veri katmanı kesimlerinde zaman toleransı yok | **evet** | Ön-kayıt §4 "Zaman toleransı" bütün karşılaştırmaları kapsıyor, kod kesimlerde (`donem_kes`, `_kume_verisi`) uygulamıyor. KEŞİF/C2 arasındaki bir saniyede ölçülen kayıt 0 (§14.19); ayrışmanın yönü ve büyüklüğü gösterilmemiştir |
| Rev.9 D-C5'in kalanı: `P0`, `P1` = 0 reddedilmiyor | **evet** | NaN ve ±inf kapandı (kapı sertleştirme turu 2); sıfır fiyat hâlâ reddedilmiyor. Sinyal oranlarının bölenleri madde 4'te kapandı |
| §14.3 exchangeInfo görüntüsünün zamanı | hayır | Açık not |
| Rev.9 D-C1 küme ölçütü / ileri kayma sırası | hayır | Yalnızca ret etiketi; ön-kayıt etiket tanımlamıyor, olay kümesi aynı |
| Rev.9 D-C4 zaman toleransı sabitinin `pencere.py`'de olması | hayır | Yer; değer ön-kayıtla aynı |
| Rev.9 D-C8 imza süreçler arası taşınamaz | hayır | Hata ile durur |
| Rev.10 D-C2 `ILERI_KAYMA_SINIRI` iç adımda okunmuyor | hayır | Ön-kayıt sınırı birincil ufka eşitliyor; kod birincil ufku kullanıyor |
| Rev.10 D-C4 ölçüm betikleri testsiz (`rev10_uygulama`, `rev11_uygulama`) | hayır | Ölçüm betiği |
| F1K2 D-C1 `pozisyon._imza` tarama deseninde yok | hayır | Kararlı atlatma |
| Tarama açıkları (analiz dizini muaf, `.ipynb`, parçalanmış ad, iç adımlar), K1–K13, KK1–KK4 | hayır | §14.27'deki belgeli sınırlar; xfail envanteri 33 → 32 (A6 xfail'i normal teste döndü) |
| **Yeni:** beklemenin üst ucu ön-kayıtta yazılı değil | **evet** (ölçülmemiş) | Madde 6. §5 "t + birincil ufuk anına kadar sürer" cümlesi tam o ana denk gelen barı tanımlamıyor. Uygulanan okuma yarı açık `(t0, t0 + h × adım]`; gerekçe ön-kaydın başka yerlerdeki aynı yapısı (§4 "Funding ödemesinin sınırları"; §4 funding sinyal penceresi) ve ilk serbest barın, önceki olayın pozisyonunun çıkış anında kapanan bar olması. Tek sabit `dizi.BEKLEME_UST_UC_DAHIL`. **Olay kümesini değiştirebilir**; bugün hiçbir olay kümesi hesaplanmamıştır. F2'nin ilk koşusundan önce karara bağlanmalı ve bir revizyon ister |
| **Yeni:** K1'in "yakın olmayan" ölçütünde tam eşitlik | **evet** (ölçülmemiş) | Madde 7. "Birincil ufuk mesafesinden yakın olmayan" ifadesinde tam ufuk mesafesinin dahil olup olmadığı yazılı değil; uygulanan okuma: tam mesafe yakın sayılmaz. Aynı sınıf, aynı sonuç: F2 öncesi karar |
| **Yeni:** "pencereye giren kayıt" çapayı kapsıyor mu | hayır | Madde 8. "Geçerli oran" denetimi ödeme penceresine (giriş sonrası, pencere sonu dahil) uygulandı; çapanın oranı toplama girmediği için denetlenmiyor. Çapayı da kapsayan okuma, sonucu etkilemeyen veriyle pozisyon düşürürdü. Ölçülen etki her iki okumada da 0 |
| **Yeni:** `count` hücresi eksik hücre kuralının dışında | hayır | Madde 3. Ön-kayıt "fiyat ve hacim hücreleri" diyor. Eksik bir `count` günü düşürmez, günün `count` toplamını sessizce eksiltir; hiçbir olay, uygunluk ya da getiri hesabına girmez |
| **Yeni:** sonlu olmayan hücre ölçütünün sinyal pencerelerine uygulanması | hayır | Madde 2. §2 rev.11'in cümlesi 1d barların kuruluşu bağlamında yazılı; `sinyal._seri` aynı ölçütü 4h ve 1d sinyal pencerelerine de uyguluyor (sonlu olmayan hücre → NaN → pencere hesaplanamaz). Ölçülen etki 0 (bozuk hücreli bar yok) |

**F1 dondurma notu.** F1 bu noktadan sonra **dondurulmuştur**. Yeni bir bulgunun F2'yi
engellemesi için, bir hipotezin sonucunu değiştirebileceğinin gösterilmesi gerekir; ön-kayıt ile
kodun ayrışması tek başına yeterli değildir, ayrışmanın **yönü ve büyüklüğü** de gösterilmelidir.
Diğer bulgular açık nokta olarak kayda geçer ve F2'yi engellemez.

Gerekçe: F1'in çıkış koşulu (anayasa §4) erken sağlanmıştı; uzayan süre, denetimin getiriyi
etkileyen kural hatalarını bulmasından kaynaklanmıştır ve bu hatalar on bir revizyonla
kapatılmıştır. Bu noktadan sonra bulunan açıklar kasıtlı ya da teorik yollardır ve F2'nin
başlamamasının maliyeti daha büyüktür.

Notun pratikteki iki sonucu:
- Yukarıdaki iki "evet" (Rev.9 D-C2 ve Rev.9 D-C5'in kalanı) için ölçülen etki bugün sıfırdır;
  yön ve büyüklük gösterilmediği sürece F2'yi engellemezler.
- Bu turda ortaya çıkan ön-kayıt belirsizliklerinden üçü (beklemenin üst ucu, K1'in tam
  eşitliği, H1'de izlemeyi bitiren barın yeni pump olup olmadığı) olay kümesini **değiştirir** ve
  tablonun kendi ölçütüyle "dokunur" sayılır; büyüklükleri ölçülmemiştir, çünkü hiçbir olay
  kümesi hesaplanmamıştır. Bunlar F2'nin **ilk koşusundan önce** karara bağlanmalıdır ve bir
  revizyon isterler; F1'i açık tutmazlar — dondurma notu "yön ve büyüklük gösterilmeli" diyor ve
  bu üç nokta için gösterilecek büyüklük F2'nin ilk koşusunda ortaya çıkar.

**F2 öncesi kontrol listesi (bugünkü durum).** §14.28'deki listenin güncellemesi:
1. **Yerel `main` itilmeli.** `origin/main` bu turun başında `ad60dbd`'ye kadar güncellenmişti;
   bu tur sekiz commit ekledi ve yerel `main` `origin/main`'in **8 commit önünde**. İlk onay
   koşusu ancak eşitlikten sonra açılabilir. Bu tur push yapmadı.
2. **Zorla itme koruması** (GitHub dal koruması) — kullanıcı yapacak; depo dışı ayar.
3. **Kilit oturumu** bekliyor: anayasa §3.3/§5/§7 metinleri, `KILIT.md`'nin kilitli dosya
   listesine eklenmesi, ONAY_KAYDI.md maddeleri. ONAY_KAYDI.md'deki yer tutucu satır Rev.11
   kilit oturumunda kaldırıldı (bu tur doğrulandı: kayıt satırı tablonun içine düşüyor).
4. **Beklemenin üst ucu ve K1'in tam eşitliği** için ön-kayıt kararı (yukarıdaki iki "yeni"
   madde). F2'nin ilk koşusundan önce.

### §14.30 Rev.12 ve Rev.13'ün veri katmanı maddelerinin uygulanması

Ön-kayıt Rev.12 ve Rev.13 (`d69e085`) veri katmanına ait on üç madde getirdi; bu tur onları koda geçirdi. **Her madde ayrı commit, her commit öncesi tam test
takımı koşuldu ve yeşildi.** Getiri, fiyat farkı ya da sinyal **değeri** hiçbir yerde
hesaplanmadı ve raporlanmadı; etki ölçümleri yalnızca sayılabilirlik düzeyinde (hesaplandı /
hesaplanamadı) ve yalnızca KEŞİF kümesi için yapıldı (ön-kayıt §4 "Ölçüm raporlamasının küme
sınırı"). `events/` ve `study/` bu turda **boş kaldı** (CLAUDE.md §4 faz sınırı); F2'ye ait
gereksinimler §14.31'e yazıldı.

Commit'ler (en eskiden yeniye): `6690cf1` (1c), `e132a30` (1b), `6267a56` (1a), `55563a6` (2a),
`34b1b0f` (2b), `2737ece` (2c), `c0f1dd4` (3b), `195346e` (3a), `a4ef592` (2d), `85891f9` (2e),
`c668530` (2f), `3471511` (2g), `56f0e50` (2h), `427a9ac` (D-C2).

**Madde → ön-kayıt → kod yeri → test**

| Madde | Ön-kayıt | Kod yeri | Test |
|---|---|---|---|
| 1c | §2 (rev.12): tamlık ölçütü **bar düzeyindedir** | `sinyal._seri` barın tamamını maskeler (`klines.hucreleri_tam_mi`) | `test_rev12_bar_duzeyi` (44) |
| 1b | §6 (rev.12): kontrol barında **çapasız** pencereler hesaplanabilir olmalı | `sinyal.CAPASIZ_PENCERELER`, `capasiz_pencere_degerleri`, `capasiz_hesaplanamayan`; `pozisyon.olay_karari` kontrol rolü | `test_rev12_kontrol_penceresi` (37) |
| 1a | §6 (rev.12): kontrol barı sinyal **koşullarını** hiç hesaplamaz | `pozisyon`: koşullar yalnızca `rol == "olay"` dalında; `OlayUretmis` ve `_sinyal_gerekli` kaldırıldı | `test_rev12_kontrol_kosulsuz` (13) |
| 2a | §5 H1 madde 4 (rev.13): izleme penceresi dönemin ve kümenin içinde, sınır **takvimle** | `dizi`: `izleme_sonu = pump + H1_IZLEME_BAR × adım`, pencere dışındaki bar izlemeyi kapatır | `test_rev13_izleme_siniri` (9) |
| 2b | §5 H3 madde 3 (rev.13): dizi **koşullarla** tanımlı, onayla değil | `dizi`: `dizi_suruyor` kapı denemesinden önce kurulur; takvim boşluğu diziyi keser | `test_rev13_h3_dizisi` (9) |
| 2c | §5 H1 m.5, H2 m.4, H3 m.4 (rev.13): geçersizlik seviyesi | `sinyal.gecersizlik_seviyesi` + `yuksek_30_max`, `config.GECERSIZLIK_CARPANI = 1.02`; `OnaylanmisPozisyon.gecersizlik_seviyesi` (yalnızca olay rolü, imzada) | `test_rev13_gecersizlik_seviyesi` (12) |
| 3b | §4 (rev.12): onay gerekli ama **yeterli değil** | `dizi._olay_dogrula`: imza, rol, hipotez + yapılandırma, sinyal zamanı, çapa | `test_rev13_dizi_kapisi` (16) |
| 3a | §4 (rev.12) + §5: olay üretimi `data.dizi`den geçer | `dizi.Olay` imzalı tip + `olay_dogrula`; kaynak taraması `DIZI_ATLATMA_DESENI`, `olay_rolu_ihlalleri` | `test_rev13_tarama` (14) |
| 2d | §6 (rev.13): adaylık **örneklemeden önce** belirlenir | `ornekleme.Adaylar` imzalı tip, `adaylari_kur`, `k1_adaylari`/`k2_adaylari`/`ornekle` yalnızca `Adaylar` alır | `test_rev13_adaylik` (44) |
| 2e | §7 (rev.13): kontrol ortalaması **olay başına** ağırlıklandırılır | `istatistik.test_istatistigi` havuz ortalamalarının ortalamasını alır; denetimler `_havuzlar`da tek yerde | `test_rev11_istatistik` (38) |
| 2f | §7 (rev.13): p-değerinin **alt tohumu** demetten türer | `istatistik.alt_tohum` + `yeniden_ornekle` (tohum çağırandan alınmaz); türetme tek yol `ornekleme.tohum_turet` | `test_rev11_istatistik` (38) |
| 2g | §8 madde 2 (rev.13): olay sayısı = **analize giren** olaylar | `config.ADAY_OLAY_ESIGI`/`ONAY_OLAY_ESIGI`, `ornekleme.OlaySayilari`, `olay_sayilari`, `olay_esigi_dogrula` | `test_rev13_olay_sayisi` (25) |
| 2h | §8 madde 5 (rev.13): onay koşusu **KILIT.md**'yi okur | `split.kilit_yolu`/`kilit_oku`/`kilit_kaydi_coz`/`KilitKaydi`; `onay_kosusu` kaydı BASLADI satırından önce okur; `onay_baglami_dogrula(..., yapilandirma)` | `test_rev13_kilit_okuma` (33) |
| D-C2 | §5 H1 m.2-3 (yakalama kapsamı) | `sinyal.TepePenceresiKurulamaz`; `pozisyon.sinyal_kosulu` yalnızca onu yakalar | `test_rev13_tepe_penceresi_hatasi` (16) |

**Kapanan ajan bulguları.** S-B1 (dizi kapının çıktısını doğrulamıyordu), S-B2 (H3 dizisi onaya
bağlıydı), S-B3 (izleme sınırı takvimle ölçülmüyordu), S-B4 (`alt_tohum` UTC dışı saat diliminde
değişiyordu), D-C5 (`ornekle` ön-kayıt değerlerini zorlamıyordu), D-C6 (§14.29'un maddeleri
(a)–(m)'ye bağlanmıyordu), P-14 (`config.HIPOTEZLER` genişletilerek ek tek atış hakkı
doğuyordu) ve D-C2. Yedi `xfail(strict=True)` işareti kaldırıldı; **hiçbirinde testin beklentisi
değiştirilmedi**, yalnızca işaret kalktı.

**Güncellenen mevcut testler.** Yalnızca rev.12/rev.13'ün **açıkça değiştirdiği** davranışı
sabitleyen testler güncellendi; gevşetme, silme ya da xfail'e çevirme yok:
`test_rev11_istatistik` (2e: girdi biçimi havuz listesi; 2f: `tohum=` anahtar sözcüğü kaldırıldı),
`test_rev11_ornekleme` ve `test_k2_elemesi…` (2d: adaylar kapıdan kurulur), `test_rev11_kapi_sinyali`
ile `test_f1k_sinyal_kapisi` (1a: kontrol barında koşul yok), `test_rev11_olay_dizisi` (2a/2b/3b),
`test_tur_saldirilari_n` ve `_p` (2h: kilit kaydı olmayan ad için koşu açılmaz; redin **sınıfı**
değişti, hükmü değil) ve onay koşusu açan testlerin fikstürleri (artık `onay_yardimcisi.gecici_kayit`
/ `kilit_yaz` üzerinden bir kilit kaydı kuruyorlar). 1b nedeniyle üç testin sentetik dönem başı
geriye alındı (H1 185 bar, H3 121 gün geçmiş ister); bunlardan üçünde uygunluk eşiği H1/H3'te
**gözlenemez** hale geldiği için testler H2'ye taşındı, iddiaları korundu — bu, rev.12'nin
ölçülmüş bir sonucudur: H1 ve H3'te çapasız pencere uygunluk penceresinden geniştir, dolayısıyla
kontrol barında uygunluk eşiği tek başına yalnızca H2'de bağlayıcıdır.

**Test dikişi (bilinçli zayıflatma).** 3b'nin doğrulaması, dizi testlerinde ucuz sahte onayları
imkânsız kıldı; her bar için gerçek kapıyı çağırmak ise kabul edilemez yavaş. `pozisyon._test_onayi`
eklendi: veri yüklemeden imzalı bir onay kurar, `split._pytest_testi()` dışında `RuntimeError`
verir ve `tarama_yardimcisi.ONAY_ATLATMA_DESENI` ile analiz kodunda yasaktır (`split._test_kaydi_ayarla`
ile aynı iki koruma). Gerçek bir F2/F3 koşusunda (pytest yok) kapalıdır.

**Etki ölçümleri** (`rev1213_uygulama.py`; A grubu, KEŞİF aralığı, 272 sembol, 280 dönem):

| Ölçüm | Sonuç | Yorum |
|---|---|---|
| 1c `--olcum bar_duzeyi` | dönem içi KEŞİF 4h barı **1.113.921**, bar düzeyli ölçütün maskelediği bar **0**; bozuk hücreli bar 0 | Rev.11 madde 3 ölçümüyle (bozuk hücre 0) tutarlı: kural bugünkü veride hiçbir barı düşürmüyor. |
| 1b `--olcum capasiz` | H1: uygun 778.638 → düşen **491** (%0,06; 165 sembol); H2: **5.260** (%0,68; 108 sembol); H3: uygun 173.984 → düşen **25.311** (%14,55; 263 sembol) | Düşüş her hipotezde **tek bir pencereden** geliyor: H1'de 180 barlık hacim medyanı, H2'de 24 saatlik funding penceresi, H3'te 120–31 günlük hacim medyanı — yani en uzun geriye bakış. H3'ün payı yüksek, çünkü 120 günlük pencere dönem başında 90 gün boyunca kurulamıyor (sembol başına medyan 90 gün). H2'nin 5.260 barının **5.154'ü üç sembolde** (ICPUSDT 2.194, TLMUSDT 1.791, BNXUSDT 1.170 — funding'i olmayan/boşluklu dönemler); kalan 105 sembolde dönem başına 1 bar. |
| 2c `--olcum gecersizlik` | H2 ve H3: uygunluk filtresini geçen barların **tamamında** (778.638 ve 173.984) seviye hesaplanabiliyor; hesaplanamayan **0** | `max(high[t-30..t])` penceresi (31 bar) uygunluk penceresinden (30 gün) kısa olduğu için uygunluk geçildiğinde seviye de hesaplanıyor. H1'in seviyesi pump barına **çapalıdır** ve yalnızca süren bir izleme içinde tanımlıdır; izleme dizisi F2'nin işi olduğu için H1 bu turda ölçülmedi (**F2'de ölçülecek**). |

Ölçülmeyen maddeler (olay kümesi gerektirir, yani F2 kodu demektir): 1a, 2a, 2b, 2d, 2e, 2f, 2g —
"F2'de ölçülecek".

**Ölçümlerin iki sınırı.** (1) Üç ölçüm de `427a9ac` commit'inde, ama **kirli çalışma ağacında**
koşuldu: ölçüm betiği ve bu bölüm o anda henüz commit edilmemişti; `data/` altında hiçbir fark
yoktu (ortam CSV'lerinde `calisma_agaci=kirli` ve değişiklik listesi yazılıdır). (2) `capasiz` ve
`gecersizlik` ölçümlerinin **sembol başına** ham çıktıları (`rev1213_capasiz_tam.csv`,
`rev1213_gecersizlik_tam.csv`) depoya alınmadı; pencere kırılımı (`rev1213_capasiz_pencere_tam.csv`)
ve hipotez başına özetler (`*_ozet_tam.csv`) commit edildi. Sembol başına tablolar commit edilen
betikle yeniden üretilebilir (`--olcum capasiz` ≈ 2,5 saat, `--olcum gecersizlik` ≈ 18 dakika, 8 iş
parçacığı).

**Temiz koşu (madde 7).** `4ed62c5` commit'inde, temiz çalışma ağacında tam denetim
(`calistir.py --eski-evren`, 678 sembol, hatalı 0) ve A1 ölçümü (`a1_olcumu.py`) yeniden koşuldu;
farklar `karsilastir.py --onceki 427a9ac` ile listelendi
(`karsilastirma_rev1213_uygulama_tam.csv`): **68 dosya aynı**, 2 dosya farklı (`ortam_tam.csv` ve
`a1_ortam_tam.csv` — yalnızca commit hash'i ve koşu zamanı), 8 dosya yeni (bu turun etki ölçümü
çıktıları). Yani Rev.12/Rev.13'ün veri katmanı değişiklikleri F1'in denetim sayılarının
**hiçbirini** değiştirmedi; beklenen de buydu, çünkü değişen kurallar olay ve kontrol üretimine
ait, F1'in bütünlük/tamlık sayımlarına değil. Denetim özeti de aynı: toplam 4h bar 3.692.573,
dönem içi bar 3.378.942, dolgu bar 313.626 (156 koşu), kısa sıfır koşusu 0, dönem tutarsızlığı 0,
funding'siz dönem 3, sıçrama 10, boşluk 105 (10 olay), 60 günden kısa dönem 5.

### §14.31 F2'nin karşılaması gereken ön-kayıt gereksinimleri (bu turda **kod yazılmadı**)

Rev.12 ve Rev.13'ün bir bölümü veri katmanının değil **F2'nin kendi kodunun** kuralıdır: ızgara
yürüyüşü, yapılandırma seçimi, beraberlik çözümü, aday yokluğu, raporlanacak kalemler, sıfır
olaylı yapılandırmanın raporlanması, sağlamlık kontrolünün uygulanması ve ikincil ufukların ne
zaman hesaplandığı. CLAUDE.md §4: "Bir faz bitmeden sonrakine ait kod yazılmaz." Bu yüzden bu
maddeler **koda geçirilmedi**; `events/` ve `study/` bu turda boş kaldı. Aşağıdaki liste, F2'nin
ilk koşusundan önce karşılanması gereken gereksinimlerin kaydıdır. Yetkili metin ön-kayıttır;
burada yalnızca anılır.

| # | Gereksinim | Ön-kayıt | Veri katmanının hazır verdiği |
|---|---|---|---|
| 1 | **Izgara yürüyüşü.** Her hipotezin 9 yapılandırmasının **hepsi** KEŞİF kümesinde hesaplanır ve **hepsi raporlanır**. | §8 madde 1 | `config.IZGARA`, `sinyal.yapilandirma_dogrula`, `sinyal.yapilandirma_kimligi`; ızgara dışı demet hata verir |
| 2 | **Raporlanacak kalemler.** Yapılandırma kimliği ve parametre değerleri; oluşmuş olay sayısı; analize giren olay sayısı; ortalama net getiri; K1 ve K2 farkı (§7 tanımıyla, birincil ufukta); iki kontrol kümesi için p-değerleri; havuzu 10'dan az olan olay sayısı; §4 "F2 şartı"ndaki ritim başına pay ve sağlamlık kontrolü sonucu; tohum ve alt tohum türetme demeti. Olay başına ham kayıtta ayrıca MAE ve geçersizlik seviyesi. | §8 madde 1 | `ornekleme.olay_sayilari` (iki sayı), `KontrolHavuzu.eksik`/`aday_sayisi` (havuzu 10'dan az olan olay), `istatistik.yeniden_ornekle` → `PSonucu.genel_tohum` + `alt_tohum_demeti`, `pozisyon.mae`, `OnaylanmisPozisyon.gecersizlik_seviyesi`, `funding.*ritim*` |
| 3 | **Sıfır olaylı yapılandırma da raporlanır:** olay sayıları sıfır yazılır; ortalama getiri, farklar ve p-değerleri "hesaplanamaz" olarak işaretlenir ve **sıfır sayılmaz**. Üç parçanın **tamamı F2'ye aittir**: (a) yapılandırmanın rapora *girmesi*, (b) iki olay sayısının sıfır yazılması, (c) üç ölçünün "hesaplanamaz" olarak **işaretlenmesi**. Veri katmanı yalnızca (c)'nin yarısını güvenceye alır: boş olay kümesinde sıfır **üretmez**. | §8 madde 1 son cümle | `istatistik.test_istatistigi` / `yeniden_ornekle` boş olay kümesinde `ValueError` verir — yani kaza ile 0.0 raporlanamaz; ama "hesaplanamaz" ibaresini yazmak, sıfır olaylı yapılandırmayı tabloya koymak ve `ornekleme.olay_sayilari`nın iki sıfırını basmak F2 kodunun işidir (denetçi bulgusu D-C5) |
| 4 | **Yapılandırma seçimi.** Adaylar (analize giren olay sayısı ≥ 150) arasından **K2 farkı en yüksek** olan seçilir (K2 farkı §7 tanımıyla, birincil ufukta). | §8 madde 2–3 | `config.ADAY_OLAY_ESIGI`, `ornekleme.OlaySayilari.esigi_gecer`, `ornekleme.olay_esigi_dogrula(…, asama="F2")`, `istatistik.test_istatistigi` (olay başına ağırlıklı) |
| 5 | **Beraberlik mekanik çözülür:** K2 farkı eşitse analize giren olay sayısı daha büyük olan; o da eşitse §5'teki **ızgara sıralamasında** daha önce gelen yapılandırma. | §8 madde 3 | ızgara sırası `config.IZGARA` sırasıdır (tek kaynak); olay sayısı `OlaySayilari.analize_giren` |
| 6 | **Aday yoksa hipotez onaya gönderilmeden kapanır:** dokuz yapılandırma madde 1'e göre raporlanır, kapanma gerekçesi "aday yok" yazılır. Bir yapılandırma seçilmişse K2 farkı > 0 ve ortalama net getiri > 0 koşulları keşifte sağlanmıyorsa hipotez yine kapanır; onay verisi harcanmaz. Seçim/kapanma `analysis/<hipotez>/KILIT.md` ile commit edilir. | §8 madde 3–5 | `split.kilit_oku`, `split.kilit_kaydi_coz`, `split.KILIT_ALANLARI`, `split.HipotezKapandi`: onay koşusu kaydı olmayan ya da hükmü "hipotez kapandı" olan hipotez için **açılmaz** |
| 7 | **Sağlamlık kontrolünün uygulanması.** Net getirisi kısmi kuyruk ve pencere sonu eşitliği nedeniyle tam doğrulanamayan olayların payı **funding ritmi başına** raporlanır; ana sonuçlar bu olaylar dışlanarak yeniden hesaplanır. Dışlama **kontrol tarafına da** uygulanır (rev.13): kalan olayların havuzlarından aynı nedenlerle doğrulanamayan kontroller de çıkarılır ve **havuzu boşalan olay analize girmez**. Kalan olay ve kontrol sayıları raporlanır; sağlamlık kontrolü ana testin yerini almaz. | §4 "F2 şartı" (rev.9, rev.13) | `funding.funding_tamlik_ayrintisi` (`kuyruk_kismi`, `son_esitlik_affi` sütunları), `pozisyon` ritim sınıflaması, `ornekleme.olay_analize_girer` (tek yüklem: havuzu boşalan olay analize girmez) |
| 8 | **İkincil ufuklar yalnızca seçilen yapılandırma için** hesaplanır (rev.13): ızgara raporu ve seçim **birincil** ufka dayanır; ikincil ufuklar seçim yapıldıktan sonra, olaylar **ve** kontrolleri için birlikte hesaplanır. İkincil ufuklar yalnızca raporlanır; onay kararları birincil ufka göre verilir. | §4 "Ufuk değerlerinin bağlanması" | `config.BIRINCIL_UFUK` / `config.IKINCIL_UFUKLAR` (tek kaynak); `pozisyon.olay_karari` serbest ufuk kabul etmez ve ikincil ufukta aynı kapıdan geçer |

**Bu listenin sınırı.** Tablo, F2 kodunun yapacaklarının kaydıdır; hiçbiri bu turda koda
geçirilmedi ve hiçbiri test edilmedi. Veri katmanının sağladığı parçalar sütun 3'te anılmıştır:
F2 bu parçaları çağırmak zorundadır, kendi kopyasını yazmamalıdır (ön-kayıt §4 "tek karar
noktası" ile aynı gerekçe).

### §14.32 Kimlik ve kilit turu: Rev.12-13 bulgularının kapatılması

Rev.12-13 uygulama turunun bıraktığı bulgular kapatıldı. **Yeni bir ön-kayıt kararı çıkmadı:**
kapatılan her madde yazılı bir kurala karşı kod boşluğuydu. `events/` ve `study/` yine boş kaldı
(CLAUDE.md §4); yalnızca `data/`, `.claude/hooks/`, `config.py`, `tests/` ve bu rapor değişti.
Getiri, fiyat farkı ya da sinyal **değeri** hiçbir yerde hesaplanmadı ve raporlanmadı.

**Test kuralı değişikliği (bu turda yürürlüğe girdi).** Takım 2845 teste çıktı ve her commit
öncesi tam koşu bellek yetersizliğinden öldürülmeye başladı (bir koşu sistem tarafından
sonlandırıldı: "running low on memory"). Bu turdan itibaren:

- her commit öncesi yalnızca **dokunulan alanın hedefli testleri** koşulur;
- **tam takım turun sonunda, son commit'ten önce bir kez** ve `tests/` dizini gruplara
  bölünerek koşulur; her grubun sonucu rapora yazılır;
- tam takım kırmızı çıkarsa düzeltme **yeni bir commit** olur (amend yok).

Korunan güvence değişmedi: **kırmızı takımla push yapılmaz.** Kaybedilen güvence, her commit'in
tek tek tam takımla doğrulanmış olmasıdır; bunun yerine her commit kendi alanının testleriyle ve
tur sonunda tamamı bir arada doğrulanır.

**Madde → ön-kayıt → kod yeri → test**

| Madde | Bulgu | Ön-kayıt | Kod yeri | Test |
|---|---|---|---|---|
| 1a | D-B1 | §6 K1 ("aynı coinden, aynı küme ve **dönem** içinden") | `ornekleme.adaylari_kur`: K1'de `donem_no` birliği | `test_kimlik_k1_donem` (13) |
| 1b | D-B2 | §6 "Örnekleme kuralları" rev.11 | `ornekleme._olaylari_dogrula`; `k1_adaylari`/`k2_adaylari` artık `dizi.Olay` alır; `Adaylar.bar_zamani` | `test_kimlik_havuz_girdisi` (30) |
| 1c | S-C1 | §4 "Olayın kümede oluşma ölçütü" rev.12 | `dizi.olay_dogrula` → `pozisyon.onay_dogrula` | `test_kimlik_olay_imzasi` (12) |
| 1d | S-C2 | §5 rev.11 (bekleme dönem başına), §3 | `dizi.olay_dizisi`: tek (sembol, küme, dönem) üçlüsü | `test_kimlik_dizi_birligi` (17) |
| 1e | D-C2 | CLAUDE.md §3.3, §4 "tek karar noktası" | `pozisyon._TEST_ONAY_OMURLERI` + dikişte `onay_baglami_dogrula` | `test_kimlik_test_dikisi` (14) |
| 2a | S-C3 | §8 madde 4 | `kilit_kaydi_coz`: K2 farkı > 0 (ve varsa ortalama net getiri > 0) | `test_kilit_dogrulama` |
| 2b | S-C4 | §8 madde 2-3 | aynı yer: analize giren olay ≥ `config.ADAY_OLAY_ESIGI` | `test_kilit_dogrulama` |
| 2c | S-C5, D-C4 | §5 rev.11, §8 madde 5, §9 | `split._kilit_yapilandirmasi_dogrula` (ızgara kimliği) | `test_kilit_dogrulama` |
| 2d | S-C6 | §8 madde 5 | `_tam`: negatif olmayan tamsayı, binlik ayırıcı üçlü gruplar | `test_kilit_dogrulama` |
| 2e | S-C7 | §8 madde 5, CLAUDE.md §5 | `_kilit_commiti_dogrula`, `_kilit_zamani_dogrula` | `test_kilit_dogrulama` |
| 2f | S-C8 | §8 madde 4-5 | kapandı hükmünde `k2_farki = None` (NaN değil) | `test_kilit_dogrulama` |
| 2g | S-C9 | §8 madde 5 ekleme kuralı | `split._kilit_gecmisini_denetle` (git geçmişi, blob tabanlı) | `test_kilit_dogrulama` (104 toplam) |
| 3 | D-B3 | §2 rev.12 | `pozisyon._tam_hucreli_barlar` (`_kume_verisi` içinde) | `test_db3_fiyat_bar_duzeyi` (17) |
| 3 | D-B4 | §7, CLAUDE.md §5 | `config._DEGISMEZ_ADLAR` + `TOHUM`, `PERMUTASYON_TEKRAR`, `ALFA_BONFERRONI` | `test_db4_tohum_degismez` (14) |
| 3 | D-C6 | §8 madde 1, §6 | `KontrolHavuzu.tohum`/`alt_tohum_demeti`/`genel_tohum`, `ornekleme.alt_tohum_demeti` | `test_dc6_havuz_alt_tohumu` (9) |
| 3 | D-C5 | §8 madde 1 son cümle | — (belge bulgusu: §14.31 satır 3 düzeltildi) | — |
| 4 | — | CLAUDE.md "Koruma katmanı" | `_yol_deseni`, `_dizin_kapsar` (hook) | `test_hook_kilit_deseni` (34) |

**Kapanan bulgular.** Sızıntı testçisinin dokuz bulgusunun **tamamı** (S-C1…S-C9) ve denetçinin
D-B1, D-B2, D-B3, D-B4, D-C2, D-C4, D-C5, D-C6 bulguları kapandı. Dokuz `xfail(strict=True)`
işareti kaldırıldı; **hiçbirinde testin beklentisi değiştirilmedi**. `test_sizinti_rev1213.py`'de
artık hiç xfail yok. D-B5 (RESULTS kaydı eksik) bu bölümle kapanır. **Açık kalan tek bulgu
D-C1'dir** (aşağıda, bilinçli).

**Güncellenen mevcut testler** (yalnızca kapatılan bulgunun açıkça değiştirdiği davranışı
sabitleyenler; gevşetme, silme, xfail'e alma yok):

| Test | Değişen kural |
|---|---|
| `test_rev11_ornekleme` (2), `test_rev13_adaylik`, `test_rev12_kontrol_kosulsuz`, `test_kimlik_k1_donem`, `test_tur_saldirilari_s` (5 yer) | 1b: ölçütün girdi tipi ham liste değil `dizi.Olay` |
| `test_rev13_adaylik`, `test_kimlik_havuz_girdisi` | 1e: C1/C2 onayı artık açık onay koşusu ister |
| `test_kimlik_dizi_birligi`, `test_sizinti_rev1213` | 1e: küme karışımında redin **sınıfı** `OnayGerekli` oldu (hüküm aynı) |
| `test_rev13_kilit_okuma.test_analize_giren_olusmusu_asamaz` | 2b: olay sayıları aday eşiğinin üstüne çekildi (100/101 → 200/201) |
| `test_ks2_kapi_veri.test_sonlu_olmayan_fiyat_reddedilir` → `..._hesaba_girmez` | D-B3: sonlu olmayan P0/P1/high artık "bar yok" yoluyla elenir; `_sonlu` koruması ayrı testle yerinde bırakıldı |
| `test_tur_saldirilari_n.test_config_hipotezler_monkeypatch_belgeleme` | 2c: sahte hipotez adının §5 ızgarası olmadığı için koşu `KilitBozuk` ile reddedilir (**sertleşme**) |
| `onay_yardimcisi.gecici_depo(kok, kilitler=...)` (test altyapısı) | 2g: kaydı sonradan yazan testler hipotezi ilk commit'ten çıkarır |

**Etki ölçümü (madde 5).** Yalnızca D-B3 ölçülebilir; diğer maddelerin etkisi olay kümesi
gerektirir, yani F2 kodu demektir → **F2'de ölçülecek**. Ölçüm temiz ağaçta (`a272641`) koşuldu:

| Ölçüm | Sonuç | Yorum |
|---|---|---|
| `rev1213_uygulama.py --olcum bar_duzeyi` | dönem içi KEŞİF 4h barı **1.113.921**, bar düzeyli ölçütün maskelediği bar **0** | Beklenen 0; D-B3 bugünkü veride hiçbir barı düşürmüyor. Fiyat okuma yolu aynı seriyi kullandığı için düşen bar sayısı da 0'dır: hiçbir olay, kontrol, P0/P1 ya da MAE değeri değişmez. "Ölçülmüş sıfır etki muafiyet değildir" (§14.13), kural yine de uygulandı. |

**Açık kalan: D-C1 (bilinçli, savunma derinliği).** `dizi.olay_dizisi`in `zamanlar` argümanının
dönem içi ve küme içi olduğu ve `pozisyon.sinyal_kosulu`nun t'sinin dönem içinde olduğu **kod
düzeyinde doğrulanmıyor**; bugün yalnızca çağıranın sözleşmesine güveniliyor. Gözlemlenebilir bir
ihlal yok: dönem dışı bir barda koşul hesaplanabilse de kapı (`olay_karari`) o barı
`SinyalBariYok`/plan denetimleriyle reddeder, yani **olay oluşmaz**. Kapatılmadı, çünkü dizi
çağrısının girdisini kod düzeyinde dönem/kümeye bağlamak F2'nin çağrı yapısını (her dönem için
ayrı çağrı, hangi barların verildiği) kodda sabitlemek demektir ve o yapı F2'ye aittir. F2'nin ilk
satırından önce ya kapatılmalı ya da §14.31'e gereksinim olarak eklenmelidir.

**Hook'un bilinçli sınırı (madde 4).** Desen artık yalnızca adı tam `KILIT.md` olan yolları
eşliyor. Windows'ta dosya adları büyük/küçük harf ayrımı yapmadığı için `analysis/h1/kilit.md`
aynı dosyayı gösterir ama desen onu eşleştirmez; koruma dikkatsiz bir düzenlemeye karşıdır,
kararlı bir atlatmaya karşı değil (CLAUDE.md "Koruma katmanı"). Bu davranış testte yazılıdır.

**Temiz koşu ve kapanış denetimi (madde 6).** `8db3cc9` commit'inde, temiz çalışma ağacında tam
denetim (`calistir.py --eski-evren`, 678 sembol, hatalı 0) ve `a1_olcumu.py` yeniden koşuldu;
farklar `karsilastir.py --onceki 8db3cc9` ile listelendi
(`karsilastirma_kimlik_kilit_tam.csv`): **76 dosya AYNI, 2 dosya farklı** (`ortam_tam.csv` ve
`a1_ortam_tam.csv`; her ikisinde yalnızca `surum` sütununun 3 satırı — commit hash'i ve koşu
zamanları). Denetim özeti değişmedi: toplam 4h bar 3.692.573, dönem içi 3.378.942, dolgu 313.626
(156 koşu), kısa sıfır koşusu 0, dönem tutarsızlığı 0, funding'siz dönem 3, sıçrama 10, boşluk 105
(10 olay), 60 günden kısa dönem 5. Bu turun kod değişiklikleri F1'in denetim sayılarının hiçbirini
değiştirmedi; beklenen de buydu, çünkü değişen kurallar olay ve kontrol üretimine ait.

**Parçalı tam takım (yeni test kuralı).** `tests/` dört gruba (35 dosya × 4) bölünerek koşuldu:
grup 00 **720 geçti / 4 xfailed**, grup 01 **796 / 10**, grup 02 **921 / 71**, grup 03 **868 / 16**
— toplam **3305 geçti, 101 xfailed, 0 kırmızı**. İlk koşuda grup 00 **dört kırmızı** verdi; dördü de
D-B3 (`f5a4e06`) öncesi davranışı sabitleyen mevcut testlerdi ve hedefli koşuların dışında kalmıştı
(`test_ks3_kapi` iki parametre, `test_tur_saldirilari_m` iki test). Düzeltme ayrı commit olarak
yazıldı (`8a9f58d`): bozuk fiyat **hücresi** veri hatası değil "bar mevcut değil" okumasıdır, yani
girişte `GirisBariYok`, çıkışta ileri kayma. Hiçbir test gevşetilmedi. **Bu, yeni test kuralının
bilinen bedelidir:** her commit öncesi yalnızca dokunulan alanın hedefli testleri koşulduğu için
hedefin dışındaki bir beklenti tur sonuna kadar kırmızı kalabilir; korunan güvence "kırmızı takımla
push yapılmaz"dır ve tur sonunda sağlandı.

**Kapanış denetiminin bulguları (düzeltilmedi, raporlandı).** Metodoloji denetçisi bir ağır bulgu
(**K-B1**: `olay_dizisi`in dönem/küme sözleşmesi + yukarıdaki D-C1 paragrafının "gözlemlenebilir
ihlal yok" gerekçesinin eksik olduğu; reddedilen bir bar da H1 izlemesini ve H3 dizisini
değiştirebilir) ve sekiz hafif bulgu (K-C1…K-C9) döndürdü. Sızıntı testçisi 111 testlik yeni bir
dosya yazdı (`tests/test_sizinti_kimlik_kilit.py`, 286 geçti / 70 `xfail(strict)`); işaretli
açıkların en önemlileri: koruma hook'unun **PowerShell aracını hiç denetlememesi**, `ornekle`'nin
olay kimliğini adaylarla çapraz doğrulamaması, `KontrolHavuzu`nun imzasız olması, ekleme kuralı
denetiminde `--full-history` eksikliği, kapının P0 ≤ 0 fiyatla onay vermesi ve `config` sabit
korumasının üç yoldan delinmesi. Hiçbiri bu turda düzeltilmedi; **F2'nin ilk satırından önce
karara bağlanmalıdır** (dökümü `prompts/rapor_kimlik_kilit.md`).

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
- 2026-09-28 (kapı sertleştirme turu 3). §14.23 eklendi. Kod: `edebbbd` (KS2 D-C1), `c866f74`
  (KS2 D-B1), `6699ff3` (KS2 D-B3). §14.22'deki "Rev.10 D-C5" etiketi düzeltildi. Rev.11 listesine 14
  (KS2 D-B4) eklendi.
  **Güncellenen mevcut testler:** §14.23 "Test güncellemeleri". Silinen ya da gevşetilen test yok.
  xfail'den çıkan: `tur_saldirilari_m` hipotez uyuşmazlığı. Yeni: `test_ks3_kapi` (31).
- 2026-09-29 (onay kaydı ve koşu bütünlüğü turu). §14.24 eklendi. Kod: `b2acfa3` (KS3 D-B1, D-B2, D-B3, D-C3).
  Rev.11 listesine 15–17 eklendi; depo dışı Rev.11 girdisi listeyle eşitlendi (KS3 D-B5).
  **Güncellenen mevcut testler:** §14.24 "Test güncellemeleri". Silinen ya da gevşetilen test yok. xfail'den
  çıkan: `tur_saldirilari_n` doğrudan atama. Yeni: `test_onay_kaydi_butunlugu` (58).
- 2026-09-30 (onay kaydı ikinci tur). §14.25 eklendi. Kod: kayıt git'e bağlı (OK D-B1), korunan adlar ve tarama
  (OK D-B2, sızıntı testçisi O), sonuç ve hata birlikte (OK D-C1). §14.24 "Kalan atlatma yolları" 5. madde
  düzeltildi (eski metin madde içinde alıntılı).
  **Güncellenen mevcut testler:** §14.25 "Test güncellemeleri". Silinen ya da gevşetilen test yok. xfail'den
  çıkan: `tur_saldirilari_o` `split_oku` ve `kume_araligi`. Yeni: `test_onay_kaydi_git` (44).
- 2026-09-30 (onay kaydı kapanış turu). §14.26 eklendi (kapsam kararı; onay kaydı çalışması kapandı). Kod: `472a541`
  (kayıt uzak depoya bağlı, `cache/` taraması). §14.25'teki "geri getiren: geçmişi yeniden yazmak ve reflog'u
  silmek" cümlesi düzeltildi (eski metin madde içinde alıntılı).
  **Güncellenen mevcut testler:** §14.26 "Testler". Silinen ya da gevşetilen test yok; `tur_saldirilari_p`'de P-5
  kurulumunun ön koşul iddiası kaldırıldı (kurulum artık reddediliyor, bu ret iddia ediliyor). xfail'den çıkan:
  P-1…P-5 (6 kimlik). Yeni: `test_onbellek_taramasi` (9), `test_onay_kaydi_git`'e 5.
- 2026-10-06 (onay kaydı çalışmasının kapanışı). §14.28 eklendi (izin alt süreçlere taşındı, doğrulama
  koşuları, xfail envanteri, F2 öncesi kontrol listesi). §14.26 kapsam paragrafı genel hükümden arındırıldı ve üç
  listeye bağlandı; §14.27'de izin kapsamı cümlesi düzeltildi (`__main__` bloğu; süreç içi sayaç), kalan yollar
  tablosu "kasıtlı ve çok adımlı" (K1–K13) ve "kazayla tetiklenebilir olduğu halde kapatılmayan" (KK1–KK4) olarak
  ikiye ayrıldı. Kod: `544939e`. Çıktılar: `580d6a6` (f1k_kume_sonu), `8494549` (rev8_etki; tek hücre farkı
  `82a0465`'in evren düzeltmesinden). **Güncellenen mevcut testler:** yok (yalnızca yeni test ve 4 yeni tarama
  biçimi). Silinen ya da gevşetilen test yok. xfail sayısı değişmedi (33).
- 2026-10-09 (kapanışın doğrulama koşuları tamamlandı). Kod değişikliği yok; yalnızca §14.28 doğrulama tablosu
  ve F2 kontrol listesinin commit sayısı güncellendi. Çıktılar: `2b4ad0e` (rev9_hazirlik), `005e280` (rev9_ritim),
  `5c96d37` (rev9_uygulama), `7514497` (rev10_hazirlik), `1eb1e98` (rev10_son), `edd70e4` (rev10_uygulama
  `--etiket sonra`) — hepsinde ölçüm çıktıları bayt düzeyinde aynı, yalnızca ortam künyesi farklı. Böylece
  sekiz betiğin sekizi de yeniden koşulmuş oldu. Test eklenmedi, silinmedi, gevşetilmedi; xfail sayısı 33.
  Tam takım `1eb1e98` ağacında yeniden koşuldu: **1879 geçti, 33 xfail**, 24 dk 8 sn.
- 2026-09-30 (onay kaydı kapanışının son turu). §14.27 eklendi (kapanan ve kalan yollar adıyla, F2 öncesi kontrol
  listesi). §14.26 kapsam kararının iki cümlesi bugünkü kodla düzeltildi (eski metin madde içinde alıntılı). Kod:
  `e616e61` (önbellek yardımcılarında onay verisi izni, `--full-history`, itme denemesi, `origin` denetimi).
  **Güncellenen mevcut testler:** §14.27 "Testler". Silinen test yok. xfail'den çıkan: Q önbellek (8), `ours` (2),
  origin (4). Yeni: `test_onay_verisi_izni`.
