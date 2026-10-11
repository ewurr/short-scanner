# CLAUDE.md — short-lab Proje Anayasası

Bu dosya, bu depoda çalışan her yapay zekâ asistanının (Claude Code dahil) uyması
gereken kuralları tanımlar. Kurallar kod yazımından önce gelir. Bir kural ile bir
görev çelişirse görevi durdur ve kullanıcıya sor.

İletişim dili Türkçedir. Kod yorumları ve commit mesajları Türkçe yazılır.

---

## 1. Projenin amacı

Binance USDⓈ-M perpetual piyasasında, düşüşten kazanç sağlayan (short) bir taktiğin
**gerçek bir öngörü gücüne dayanıp dayanmadığını** dürüstçe ölçmek.

Bu bir sinyal üretme projesi değil, önce bir **ölçüm** projesidir. Hiçbir hipotez
onay aşamasını geçmeden taktik tasarlanmaz, hiçbir taktik ileri-zaman testini
geçmeden gerçek parayla kullanılmaz.

Projede hiçbir aşamada borsaya gerçek emir gönderilmez. API anahtarı istenmez,
saklanmaz, koda yazılmaz.

## 2. Short'a özgü gerçekler (tasarımın temeli)

1. **Asimetri.** Short'ta kazanç en fazla %100, kayıp sınırsızdır. Sağ kuyruk
   (sert yükseliş, squeeze) bu projede fırsat değil, **risktir**.
2. **Funding.** Perpetual pozisyon her funding anında ödeme yapar veya alır.
   Funding pozitifken short **alır**, negatifken **öder**. Her getiri hesabı
   funding'i gerçek geçmişiyle içerir; "sonra ekleriz" yoktur.
3. **Piyasa yönü tuzağı.** Düşen bir piyasada rastgele her short kazandırır.
   Bir hipotezin değeri, **aynı anda diğer coinleri short'lamaktan** daha iyi
   olmasıyla ölçülür (K2 kontrolü, bkz. PREREGISTRATION.md).
4. **Hayatta kalma yanlılığı ters çalışır.** Delist olmuş coinler en iyi short
   adaylarıdır. Delist edilmiş semboller veride mevcuttur, ancak uzlaşmış
   sözleşmeler sıfır hacimli dolgu barlarla devam ettiği için dönem sonu gerçek
   işlem bitişine (sıfır olmayan hacimli son bar) göre belirlenir. Dolgu barlar
   dönemin parçası sayılırsa delist coinler sessizce hesaptan düşer.
5. **Stop zorunludur.** Taktik aşamasında her short pozisyonun önceden tanımlı
   bir geçersizlik (stop) seviyesi olmalıdır. Stopsuz short tasarımı yapılmaz.
6. **Kâr al serbesttir.** Short'ta kazanç zaten sınırlı olduğu için önceden
   yazılmış bir kâr al kuralı meşrudur. Veriye bakıldıktan sonra eklenemez.
7. **Kaldıraç yoktur.** Paper testte pozisyonlar 1x nominal tutulur. Likidasyon
   değil, en kötü ara zarar (MAE) raporlanır.

## 3. Metodoloji kuralları (esnetilemez)

1. **Önce ön-kayıt, sonra veri.** PREREGISTRATION.md commit edilmeden hiçbir
   getiri hesaplanmaz. Veri denetimi (kapsama, eksik bar, delist sayısı) serbesttir;
   getiri, olay sayısı veya olay sonrası fiyat davranışı denetim değildir.
2. **Veri bölmesi dokunulmazdır.** `data/split.csv` bir kez üretilir ve commit
   edilir. Coin grubu (A/B) veya tarih sınırları sonradan değiştirilemez.
3. **Keşif serbest, onay tek atış.** Keşif yalnızca A grubu coinlerde ve keşif
   döneminde yapılır. Onay kümeleri (C1, C2) her hipotez için **bir kez** koşulur.
   Onay kümesi verisi yalnızca açık bir onay koşusu içinde okunabilir; koşu, veri
   katmanındaki `onay_kosusu` bağlam yöneticisiyle açılır ve hipotez ile küme adını
   alır. Koşu yalnızca temiz çalışma ağacında, git'te izlenen bir depo betiğinden ve
   yerel `main` `origin/main` ile eşitken açılabilir. Her koşu `ONAY_KAYDI.md`
   dosyasına iki satır yazar — açılışta BASLADI, kapanışta sonucuyla BITTI ya da hata
   sınıfıyla HATA — ve her satır yazıldığı anda commit edilip uzak depoya itilir.
   Tek atış denetimi `origin/main` geçmişine bakar: kaydı uzak depoda bulunan bir
   (hipotez, küme) çifti ikinci kez koşulamaz, yarıda kalmış koşu dahil. Kayıt
   satırları hiçbir zaman silinmez.
4. **Eşikler sonuçtan önce sabitlenir.** Başarı eşikleri, kontrol tanımları ve
   hipotez ızgaraları PREREGISTRATION.md'de yazılıdır. Sonuç görüldükten sonra
   değiştirilmez. Değişiklik gerekiyorsa gerekçesiyle **revizyon** olarak yazılır
   ve etkilenen sonuçlar geçersiz sayılır.
5. **Negatif sonuç sonuçtur.** Başarısız hipotez `analysis/<ad>/RESULTS.md` içinde
   aynı özenle yazılır. Başarısız bir fikre yama yapılıp yeniden denenmez; yeni
   fikir yeni hipotezdir ve yeni ön-kayıt ister.
6. **Geleceğe bakış yoktur.** Sinyal t barının kapanışında hesaplanır, işlem t+1
   barının açılışında açılır. Uygunluk filtreleri (hacim, listeleme yaşı) yalnızca
   t anına kadarki veriyi kullanır. Her yeni hesaplama için bunu doğrulayan test yazılır.
7. **Maliyet muhafazakârdır.** Tek yön %0.10 (ücret + kayma), gidiş-dönüş %0.20.
   Funding gerçek geçmişten alınır.

## 4. Aşamalar

| Faz | İçerik | Çıkış koşulu |
|---|---|---|
| F0 | Depo iskeleti, bu belge, ön-kayıt | PREREGISTRATION.md commit edildi |
| F1 | Veri katmanı, veri bölmesi, veri denetimi | `data/split.csv` commit edildi, denetim raporu yazıldı |
| F2 | Keşif: olay çalışması (yalnızca A grubu, keşif dönemi) | Her hipotez için yapılandırma kilitlendi ya da hipotez kapandı |
| F3 | Onay: C1 ve C2 tek atış | Her hipotez için GEÇTİ / KALDI hükmü |
| F4 | Taktik tasarımı (yalnızca geçen hipotezler, yalnızca keşif verisi) | Taktik ön-kaydı (revizyon) commit edildi |
| F5 | İleri-zaman paper testi (ayrı defter, ayrı servis) | Kendi ön-kaydındaki eşik |

Bir faz bitmeden sonrakine ait kod yazılmaz. F3'te hiçbir hipotez geçmezse proje
F4'e geçmez; bu geçerli ve değerli bir sonuçtur.

## 5. Kod kuralları

- Python 3.11+, bağımlılıklar `requirements.txt` içinde sürüm aralığıyla.
- Hesaplama fonksiyonları saftır (girdi → çıktı, yan etkisiz). Ağ ve disk erişimi
  yalnızca `data/` katmanında.
- Tüm zaman damgaları UTC. Bar zamanı = barın açılış zamanı.
- Önbellek parquet formatında, `cache/` altında, git'e girmez. Önbellek yalnızca ham ay
  verisini tutar; kümeye göre kesilmiş veri diske yazılmaz. Bellekte tutulan her kopya
  için küme erişim denetimi kopyanın her okunuşunda yeniden uygulanır, önbellek anahtarı
  küme adını içerir, ve onay koşusunun açılışı ile kapanışı bu kopyaları geçersiz kılar
  (ön-kayıt §3).
- F2 ve F3 koşuları ağa çıkmaz: veri koşudan önce indirilir, koşu dondurulmuş yerel
  önbellekten okur (ön-kayıt §3). Gerekçe tekrarlanabilirliktir; koşu sırasında yapılan
  bir ağ isteği sonucu borsanın o anki durumuna bağlar.
- Her modülün testi `tests/` altında. `pytest -q` ağa çıkmadan geçmelidir.
- Rastgelelik her zaman sabit tohumla (seed) ve tohum sonuç dosyasına yazılır.
- Her analiz `analysis/<ad>/` altında: çalıştırma betiği, `RESULTS.md`, ham çıktı CSV.

### Koruma katmanı

**Kilitli dosyalar.** `PREREGISTRATION.md`, `data/split.csv`, `data/universe.csv`,
`data/exchange_info_anlik.json`, `ONAY_KAYDI.md`, `analysis/<hipotez>/KILIT.md` (her
hipotez için, oluşturulduğu andan itibaren) ve bu dosya (`CLAUDE.md`) kilitlidir.
`.claude/hooks/kilitli_dosya_korumasi.py` adlı `PreToolUse` hook'u bu dosyalara
yapılan yazma ve düzenleme araç çağrılarını reddeder. Kilit yalnızca kullanıcının
açık izniyle, `SHORT_LAB_KILIT_ACIK=1` ortam değişkeni ayarlanarak açılır.

`ONAY_KAYDI.md` yalnızca ekleme kuralına tabidir; kayıt satırları hiçbir zaman
silinemez. Başlıktaki yer tutucu cümle Rev.11 kilit oturumunda kaldırılmıştır.

**F2'nin kilitlediği yapılandırma.** F2 sonunda her hipotez için seçilen
yapılandırma (ya da hipotezin kapandığı) `analysis/<hipotez>/KILIT.md` dosyasına
yazılır. Dosya oluşturulduğu andan itibaren kilitlidir ve hook tarafından korunur.
Dosyanın alanları, ekleme kuralı ve onay koşusunun bu dosyayı okuma yükümlülüğü
ön-kayıt §8'de yazılıdır; burada tekrarlanmaz. İki belgede aynı kuralı iki kez
yazmak ikisinin ayrışmasına yol açar, bu yüzden yetkili metin ön-kayıttır.

Hook araç çağrılarını yakalar; çalışan Python kodunu etkilemez.
`data/split.py` içindeki onay koşusu bu yüzden `ONAY_KAYDI.md` dosyasına
yazmaya devam eder. Hook `Bash` çağrılarını da denetler: kilitli bir dosyaya
yazma niyeti taşıyan komutları (yönlendirme, `sed -i`, `mv`, `rm`, çalışma
ağacını değiştiren git alt komutları vb.) reddeder, salt okuma komutları geçer.
Kilitli dosyayı adıyla anmadan yazan bir betik yakalanamaz: kilit, dikkatsiz bir
düzenlemeye karşı korur, kararlı bir atlatmaya karşı değil.

**Metodoloji denetçisi** (`.claude/agents/metodoloji-denetcisi.md`): her faz
sonunda ve her analiz kodu yazıldıktan sonra çalıştırılır. Geleceğe bakış,
pencere ve boşluk kuralı, dönem sınırları, dolgu koşuları ve uzun boşluklar,
veri bölmesi, ön-kayıttan sapma,
tohum ve tekrarlanabilirlik başlıklarında bulgu listesi döner. Kod düzeltmez.

**Sızıntı testçisi** (`.claude/agents/sizinti-testcisi.md`): yeni hesaplama kodu
yazıldıktan sonra çalıştırılır. Kodu kırmaya çalışan testler üretir; yalnızca
`tests/` altına yazar.

## 6. Eski projeyle ilişki

Bu proje `coin-scanner` deposundan **bağımsızdır**. Oradan kod import edilmez.
Uygun parçalar (önbellek deseni, permütasyon testi, rastgele kontrol portföyleri)
**kopyalanıp** bu projenin kurallarına uyarlanabilir; kopyalanan dosyanın başına
kaynağı yazılır. Eski projenin canlı servisine, defterine veya VPS dizinine hiçbir
şekilde dokunulmaz.

## 7. Dizin yapısı (hedef)

```
short-lab/
├── CLAUDE.md
├── PREREGISTRATION.md
├── ONAY_KAYDI.md            # onay koşularının değiştirilemez kaydı
├── README.md
├── requirements.txt
├── config.py                # tarih sınırları, maliyet, evren eşikleri (ön-kayıtla aynı)
├── .claude/
│   ├── settings.json        # hook kaydı ve araç izinleri
│   ├── hooks/
│   │   └── kilitli_dosya_korumasi.py   # kilitli dosyaları koruyan PreToolUse hook'u
│   └── agents/
│       ├── metodoloji-denetcisi.md     # faz sonu ve analiz kodu metodoloji denetimi
│       └── sizinti-testcisi.md         # kodu kırmaya çalışan test yazarı
├── data/
│   ├── __init__.py          # ağ ve disk erişimi yalnızca bu pakette
│   ├── binance_vision.py    # data.binance.vision ortak erişim katmanı
│   ├── universe.py          # tarihsel perpetual evreni (delist dahil)
│   ├── universe.csv         # commit edilir, bir daha değişmez
│   ├── exchange_info_anlik.json   # evren kurulumunun girdisi, bir kez üretilir
│   ├── klines.py            # 4h ve 1d mum indirme + önbellek
│   ├── funding.py           # funding geçmişi, 8 saate normalleştirme
│   ├── donem.py             # listeleme dönemi, dolgu koşusu ve uzun boşluk bölmesi
│   ├── pencere.py           # zamanla tanımlı pencere, tamlık kontrolü, ufuk
│   ├── eligibility.py       # t anındaki uygunluk filtresi
│   ├── sinyal.py            # hipotezlerin sinyal pencereleri, değerleri ve koşulları
│   ├── dizi.py              # olay dizisi kuralları: bekleme, tek izleme, ilk gün
│   ├── pozisyon.py          # tek karar noktası: olay ya da kontrol oluşur mu
│   ├── ornekleme.py         # K1 ve K2 kontrol havuzlarının örnekleme kuralları
│   ├── istatistik.py        # test istatistiği, `r` ve p-değeri
│   ├── split.py             # A/B coin bölmesi, dönem koruması, onay koşusu
│   └── split.csv            # commit edilir, bir daha değişmez
├── events/                  # F2: H1, H2, H3 olay tanımları
├── study/                   # F2-F3: olay çalışması, K1/K2 kontrolleri, permütasyon
├── analysis/
│   ├── 00_veri_denetimi/    # F1 veri denetimi: betikler, RESULTS.md, ham çıktı CSV
│   └── <hipotez>/           # F2: her hipotezin kendi dizini
│       └── KILIT.md         # F2'nin kilitlediği yapılandırma (ön-kayıt §8)
├── cache/                   # git'e girmez
└── tests/                   # her modülün testi ve ortak yardımcıları
```
