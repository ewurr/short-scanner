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
   adaylarıdır. Veride yoksa sonuçlar kötümser çıkar; varsa dahil edilmelidir.
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
   Onay koşusu, `--onay` bayrağı olmadan veri katmanı tarafından reddedilir ve her
   koşu `ONAY_KAYDI.md` dosyasına commit hash'iyle eklenir (yalnızca ekleme, silme yok).
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
- Önbellek parquet formatında, `cache/` altında, git'e girmez.
- Her modülün testi `tests/` altında. `pytest -q` ağa çıkmadan geçmelidir.
- Rastgelelik her zaman sabit tohumla (seed) ve tohum sonuç dosyasına yazılır.
- Her analiz `analysis/<ad>/` altında: çalıştırma betiği, `RESULTS.md`, ham çıktı CSV.

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
├── data/
│   ├── universe.py          # tarihsel perpetual evreni (delist dahil)
│   ├── klines.py            # 4h ve 1d mum indirme + önbellek
│   ├── funding.py           # funding geçmişi, 8 saate normalleştirme
│   ├── split.py             # A/B coin bölmesi ve dönem koruması
│   └── split.csv            # commit edilir, bir daha değişmez
├── events/                  # F2: H1, H2, H3 olay tanımları
├── study/                   # F2-F3: olay çalışması, K1/K2 kontrolleri, permütasyon
├── analysis/
│   └── 00_veri_denetimi/
├── cache/                   # git'e girmez
└── tests/
```
