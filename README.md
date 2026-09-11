# short-lab

Binance USDⓈ-M perpetual piyasasinda **short** taktiklerinin gercek bir ongoru
gucune dayanip dayanmadigini olcen arastirma deposu.

Bu bir sinyal uretme projesi degil, once bir **olcum** projesidir. Borsaya hicbir
asamada gercek emir gonderilmez; API anahtari istenmez, saklanmaz, koda yazilmaz.

Kurallarin tamami [CLAUDE.md](CLAUDE.md), hipotezler ve esikler
[PREREGISTRATION.md](PREREGISTRATION.md) icindedir. Ikisi de kod yaziminin
onunde gelir.

## Fazlar

Ayrintili tablo: [CLAUDE.md §4](CLAUDE.md#4-aşamalar).

| Faz | Icerik | Durum |
|---|---|---|
| F0 | Depo iskeleti, anayasa, on-kayit | tamam |
| F1 | Veri katmani, veri bolmesi, veri denetimi | surmekte |
| F2 | Kesif: olay calismasi (yalnizca A grubu, kesif donemi) | baslamadi |
| F3 | Onay: C1 ve C2 tek atis | baslamadi |
| F4 | Taktik tasarimi | baslamadi |
| F5 | Ileri-zaman paper testi | baslamadi |

Bir faz bitmeden sonrakine ait kod yazilmaz.

## Kurulum

```bash
pip install -r requirements.txt
pytest -q          # aga cikmadan gecer
```

## Dizinler

| Yol | Icerik |
|---|---|
| `config.py` | On-kayittaki sabitler (tarih sinirlari, maliyet, esikler, tohum) |
| `data/` | Veri katmani: evren, mumlar, funding, bolme, uygunluk |
| `data/split.csv` | A/B bolmesi — bir kez uretilir, bir daha degismez |
| `ONAY_KAYDI.md` | Onay kosularinin degistirilemez kaydi |
| `analysis/` | Her analiz kendi dizininde: betik, `RESULTS.md`, ham CSV |
| `cache/` | Parquet onbellek, git'e girmez |
| `tests/` | `pytest` testleri |
