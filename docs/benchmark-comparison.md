# Motor karşılaştırması: hushmark ve alternatifler

> Bu belge sentetik bir veri kümesi üzerinde yapılmış bir ölçümdür; bir uyumluluk,
> anonimleştirme veya kesin üstünlük iddiası değildir. Geri döndürülebilir maskeleme
> teknik bir güvenlik tedbiridir.

## Amaç

Türkçe metinde kişisel veri tespiti için hushmark ile yaygın alternatifleri aynı veri kümesi,
aynı eşleşme kuralları ve aynı donanım üzerinde ölçmek. Kıyas tek bir F1 sayısına indirgenmez:
maskeleme senaryosunda kaçan bir kimlik numarası, fazladan maskelenmiş bir kelimeden daha
pahalıdır. Bu yüzden tablo recall önceliklidir ve karar kriterleri ayrı ayrı raporlanır.

Karşılaştırma ayrıca bir ablasyon içerir: skorun ne kadarı fine-tune edilmiş modelden, ne kadarı
modelin çevresindeki deterministik doğrulayıcı katmandan geliyor?

## Ölçülen kriterler

| Kriter                         | Neden önemli                                                                                         |
| ------------------------------ | ---------------------------------------------------------------------------------------------------- |
| Strict recall / precision / F1 | Tip ve ofsetlerin birebir tutması; maskeleme motoru ofsetle çalışır                                  |
| Partial recall                 | Varlığın bulunup sınırının kayması ile hiç bulunmaması arasındaki farkı ayırır                       |
| TR kimlik recall               | TCKN, VKN, IBAN, SGK, plaka, telefon, e-posta, kart, sır tiplerinin toplamı                          |
| Özel nitelikli recall          | KVKK m.6: sağlık, din, etnik köken, siyasi görüş, cinsel hayat, ceza mahkûmiyeti, biyometri, sendika |
| Tip kapsamı                    | 24 tipin kaçında motor varlığı hiç görebiliyor (partial eşleşme üzerinden)                           |
| Morfoloji dayanıklılığı        | Ek almış isim, diakritiksiz yazım, küçük harfli bağlam dilimlerinde recall                           |
| Gecikme (p50/p95)              | Örnek başına, tek iş parçacıklı CPU üzerinde                                                         |
| Çalışma yeri                   | Yerel mi, yoksa metni üçüncü tarafa gönderiyor mu                                                    |

Son kriter bir performans ölçüsü değil ama gizlilik ürünü seçerken belirleyicidir: kişisel veriyi
bulmak için kişisel veriyi dışarı göndermek, çözülmek istenen sorunun kendisidir.

## Karşılaştırılan motorlar

Rakipleri zayıf hâlleriyle ölçmemek için her motor, o motoru kullanan yetkin bir ekibin
kuracağı makul yapılandırmayla çalıştırıldı.

| Motor                            | Ne çalışıyor                                                                                              |
| -------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `core-hushmark-tr-*`             | hushmark hattının tamamı + `lokomotifai/hushmark-tr-289m` fine-tune modeli, `torch` ve `onnx` arka uçları |
| `core-gliner-multi-pii-v1-torch` | Aynı hat, fine-tune yerine taban model `urchade/gliner_multi_pii-v1`                                      |
| `gliner-raw-hushmark-tr`         | Fine-tune model tek başına, hushmark hattı olmadan                                                        |
| `gliner-raw-gliner-multi-pii-v1` | Taban model tek başına                                                                                    |
| `presidio-tr`                    | Presidio yerleşikleri + `akdeniz27/bert-base-turkish-cased-ner`, telefon bölgesi `TR`                     |
| `presidio-default`               | Kutudan çıktığı hâliyle Presidio (yalnızca İngilizce yerleşikler)                                         |
| `openai-*`                       | OpenAI modeline JSON şema ile varlık çıkarttırma (LLM-redaktör yaklaşımı)                                 |

`presidio-tr` için Türkçeye özgü kimlik mantığı (TCKN, VKN, SGK, plaka) **eklenmedi**, çünkü
Presidio bunları içermiyor. Bu bir eksiklik tespitidir, harness'ın rakibe koyduğu bir engel
değil: Presidio özel tanıyıcılarla genişletilebilir.

Alt kelime birleştirme stratejisi `average`. `simple` stratejisi Türkçe isimleri parçalara
bölüyordu (`Şenkal` → `Şen` + `kal`); onunla ölçmek rakibi model kalitesi yüzünden değil,
entegrasyon hatası yüzünden düşük gösterirdi.

LLM'den karakter ofseti istenmez; model yüzey metnini ve kaçıncı geçtiğini döndürür, ofset
kaynak metinde eşleştirilerek bulunur. Yanıtlar diske önbelleklenir, böylece tekrar koşum
ücretsiz ve çıktı denetlenebilir olur.

## Sonuçlar

Veri kümesi: `hushmark-bench-v0.jsonl`, 2016 örnek,
SHA-256 `6170b620faa349dbcbf2f2a973d5de20e35c6594e5626a2a589d20df5f67d642`.
Tam tablolar: [`bench/reports/comparison-v2.md`](../bench/reports/comparison-v2.md).

| Motor                        | Çalışma |  Strict R | Strict P | Strict F1 | TR kimlik R | Özel nitelikli R | Kapsam |     p50 |
| ---------------------------- | ------- | --------: | -------: | --------: | ----------: | ---------------: | -----: | ------: |
| `core` + hushmark-tr (onnx)  | yerel   | **0.995** |    0.996 | **0.996** |       1.000 |            0.995 |  24/24 |   18 ms |
| `core` + hushmark-tr (torch) | yerel   | **0.995** |    0.997 | **0.996** |       1.000 |            0.995 |  24/24 |   42 ms |
| OpenAI `gpt-5.4-mini`        | API     |     0.865 |    0.851 |     0.858 |       0.971 |            0.691 |  24/24 | 1044 ms |
| `core` + taban model (torch) | yerel   |     0.858 |    0.858 |     0.858 |       1.000 |            0.640 |  24/24 |   44 ms |
| hushmark-tr tek başına       | yerel   |     0.617 |    0.931 |     0.742 |       0.322 |            0.989 |  19/24 |   49 ms |
| taban model tek başına       | yerel   |     0.537 |    0.661 |     0.593 |       0.457 |            0.583 |  22/24 |   49 ms |
| `presidio-tr`                | yerel   |     0.343 |    0.579 |     0.431 |       0.444 |            0.000 |   8/24 |   15 ms |
| `presidio-default`           | yerel   |     0.228 |    0.775 |     0.353 |       0.444 |            0.000 |   5/24 |  0.4 ms |

## Ablasyon: fine-tune ne katıyor, hat ne katıyor?

İki katkı birbirinden temiz biçimde ayrışıyor ve **hiçbiri tek başına yeterli değil**.

**Fine-tune modelin katkısı — anlamsal ve özel nitelikli tipler.** Aynı hat içinde taban model
yerine fine-tune konduğunda:

| Tip                     | Taban + hat | Fine-tune + hat |
| ----------------------- | ----------: | --------------: |
| BIOMETRIC_REF           |       0.042 |           1.000 |
| UNION                   |       0.219 |           1.000 |
| CRIMINAL                |       0.125 |           1.000 |
| POLITICAL               |       0.562 |           1.000 |
| ORG                     |       0.573 |           0.979 |
| PERSON                  |       0.642 |           0.985 |
| **Özel nitelikli grup** |   **0.640** |       **0.995** |

**Deterministik katmanın katkısı — checksum'lı kimlikler.** Fine-tune model tek başına ile hat
içindeki hâli:

| Tip                 | Model tek başına | Model + hat |
| ------------------- | ---------------: | ----------: |
| TR_TCKN             |            0.000 |       1.000 |
| TR_VKN              |            0.000 |       1.000 |
| TR_SGK              |            0.000 |       1.000 |
| IBAN_OTHER          |            0.000 |       1.000 |
| SECRET_JWT          |            0.000 |       1.000 |
| CREDIT_CARD         |            0.075 |       1.000 |
| **TR kimlik grubu** |        **0.322** |   **1.000** |

Okunuşu şu: checksum'lı kimlikler öğrenilen bir örüntü değil, doğrulanan bir kuraldır — model
onları ezberlemeye çalışmamalı. Buna karşılık "sendika üyeliği" veya "ceza kaydı" gibi tipler
regex'le yakalanamaz, dil modelinin işidir. hushmark'ın skoru bu iş bölümünden geliyor.

## ONNX arka ucu: önceki bulgunun düzeltmesi

Bu çalışmanın erken bir turunda, taban model `gliner_multi_pii-v1` için ONNX arka ucunun torch'a
göre çok düşük recall verdiği görülmüş ve ürünün varsayılan ONNX yolunun araştırılması
önerilmişti. **Fine-tune modelle ölçüm bu endişeyi doğrulamıyor:**

| Model / arka uç    | Strict R |     p50 |
| ------------------ | -------: | ------: |
| hushmark-tr, torch |    0.995 | 41.5 ms |
| hushmark-tr, onnx  |    0.995 | 18.3 ms |

`hushmark-tr` için ONNX ile torch aynı doğrulukta ve ONNX yaklaşık 2.3 kat daha hızlı. Önceki
düşüş, taban modelin **int8 nicemlenmiş** `model_quantized.onnx` export'una özgüydü;
`hushmark-tr` tam hassasiyetli `model.onnx` (1.16 GB) yayımlıyor. Yani varsayılan dağıtım
arka ucunda bir sorun yok; sorun yalnızca taban modelin nicemlenmiş export'undaydı.

## Presidio

Presidio Türkçeye ayarlanınca ciddi biçimde iyileşiyor (strict recall 0.228 → 0.343, PERSON
0.000 → 0.521). Kalan açık iki yerde: Türkçe kimlik tipleri için hazır tanıyıcı yok ve KVKK m.6
özel nitelikli grubunda her iki yapılandırma da 0.000 veriyor.

`presidio-tr` ADDRESS'te strict 0.000 alırken partial 0.896 alıyor: model ilçe/şehir buluyor,
gold ise tam adres. "Bulamadı" ile "buldu, sınırı kaydı" farklı şeylerdir; tablo ikisini ayırır.

## LLM-redaktör yaklaşımı

`gpt-5.4-mini` ciddi bir rakip: strict recall 0.865, partial recall 0.978, tip kapsamı 24/24.
Taksonomiyi hiç eğitim görmeden, yalnızca istemdeki tip listesinden yakalıyor. Ancak üç yapısal
fark var ve bunlar model kalitesiyle kapanmaz:

|                      | hushmark (onnx) |     gpt-5.4-mini |
| -------------------- | --------------: | ---------------: |
| Strict recall        |           0.995 |            0.865 |
| TR kimlik recall     |       **1.000** |            0.971 |
| p50 gecikme          |       **18 ms** |          1044 ms |
| Metin nereye gidiyor |   yerelde kalır | üçüncü taraf API |

1. **Gecikme ~57 kat.** Örnek başına 18 ms yerine 1044 ms; maskeleme, istek yolunda senkron
   çalışan bir adımdır.
2. **Kimlik garantisi olasılıksal.** LLM TCKN/IBAN'da 0.971 veriyor; deterministik katman
   checksum doğruladığı için 1.000 veriyor ve neden öyle olduğu denetlenebilir.
3. **Veri dışarı çıkıyor.** Kişisel veriyi bulmak için kişisel veriyi üçüncü tarafa göndermek,
   bir gizlilik ürününde çözülmek istenen sorunun kendisidir. (Bu ölçümde gönderilen metin
   sentetiktir; gerçek kişisel veri dışarı çıkmamıştır.)

## Nasıl koşulur

```bash
.venv/bin/python scripts/fetch-models.py

HUSHMARK_CORE_ALLOW_UNAUTHENTICATED=1 HUSHMARK_CORE_MODEL_ID=hushmark-tr \
  .venv/bin/python bench/run.py --engine core --backend onnx \
  --report bench/reports/compare-v2.md
```

Karşılaştırma tablosunu üretmek için:

```bash
.venv/bin/python bench/compare.py \
  --report bench/reports/compare-v2.md --output bench/reports/comparison-v2.md
```

LLM satırları için `OPENAI_API_KEY` ve `HUSHMARK_BENCH_OPENAI_MODEL` gerekir. Kendi motorunuzu
eklemek için `bench/src/hushmark_bench/adapters/` altına `predict(text)` döndüren bir sınıf yazıp
`build_adapter` içine bağlamak yeterlidir.

## Ölçülmeyenler

| Motor                                   | Neden                                                        |
| --------------------------------------- | ------------------------------------------------------------ |
| OpenAI `gpt-5.5`                        | Ölçüm sürüyor; tamamlanınca tabloya eklenecek                |
| Azure AI Language PII, Google Cloud DLP | Kimlik bilgisi yok; adapter yazılmadı                        |
| LFM2.5-Encoder-350M-PII                 | Ağırlıklar yerelde mevcut ama bu turda kapsam dışı bırakıldı |

## Geçerlilik sınırları

- **Veri sentetiktir.** `hushmark-bench-v0.jsonl` hushmark'ın kendi üreticisiyle üretildi.
  Şablonlar, üretici ve SHA-256 kilidi depoda açık olduğu için ölçüm tekrarlanabilir; ancak
  gerçek dünya metninin dağılımını temsil ettiği iddia edilemez. 0.99 üzeri skorlar bu
  sınırın içinde okunmalıdır: aynı şablon ailesinden üretilmiş metinlerde ölçülmüştür.
- **Fine-tune modelin eğitim verisi ile bu veri kümesi aynı üreticiden gelir.** Şablonlar ve
  değer üreticileri paylaşıldığı ölçüde, `hushmark-tr` satırı bir ev sahibi avantajı taşır.
  Bağımsız bir doğrulama için insan yazımı, dış kaynaklı bir test kümesi gerekir; bu, bu
  ölçümün kapatmadığı en önemli açıktır.
- **Ev sahibi taksonomisi.** 24 tipli taksonomi hushmark'ındır; rakipler kendi taksonomilerinden
  buraya eşlendi, eşleme tabloları adapter dosyalarında açıktır.
- **Strict eşleşme sınır farklarını cezalandırır.** Türkçe ek almış isimlerde modeller çoğunlukla
  eki dışarıda bırakır; bu yüzden partial recall da raporlanır.
- **Gecikme tek makinede, ardışık koşumlarla ölçüldü** (LLM satırları kendi aralarında eşzamanlı).
  Farklı CPU'da mutlak değerler değişir; motorlar arası oran daha anlamlıdır.
- **`core` ve çıplak model satırları birebir aynı koşulda değildir:** hat modele 12 NER
  etiketi verir, çıplak koşum 24 tipin tamamını; eşikler 0.55 ve 0.50'dir.
