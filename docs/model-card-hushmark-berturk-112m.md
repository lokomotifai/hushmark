# Hushmark BERTurk Span 112M

`hushmark-berturk-112m`, Hushmark'ın özel 12 etiketli Türkçe span-NER modelidir. Model
`dbmdz/bert-base-turkish-cased` encoder'ını tamamen fine-tune eder ve başlangıç, bitiş,
ortalama span temsili ile genişlik embedding'ini sınıflandıran özel bir head kullanır.

Bu sürüm bir **private challenger**'dır; varsayılan production modeli hâlâ `hushmark-tr`'dir.
Runtime entegrasyonunun repoda bulunması modelin otomatik olarak production'a terfi ettiği
anlamına gelmez.

## Değişmez kimlik

| Alan | Değer |
| --- | --- |
| Hugging Face | [`lokomotifai/hushmark-berturk-112m`](https://huggingface.co/lokomotifai/hushmark-berturk-112m) (private) |
| HF revision | `49ed7596936fd1ba28a26b788abcfb8c7b963a5c` |
| Parametre | `112.422.957` |
| Ana encoder dosyası | `encoder/model.safetensors` |
| Ana SHA-256 | `a2426b32e90cc97909bcdb1e8518d0bfd5fbf6e7d4e9401565a389fb23807d2f` |
| Span head SHA-256 | `49606104c71b9f10bac64086e43e6c528dd50566a18131bdd419ed7634e32af6` |
| Runtime artifact SHA-256 | `ce319a22f131fd62b49df85261fb33c1dff871c075f3bc37d2d3be0fb9db383a` |
| Maksimum giriş | 256 BERT subword token |
| Maksimum span | 24 kelime birimi |
| Önerilen eşik | `0.50` |

Altı gerekli runtime dosyasının boyut ve SHA-256 değerleri `core/models.yaml` içinde
sabitlenmiştir. Ağırlıklar ve eğitim verisi GitHub'a eklenmez.

## Private modeli kurma

Önce Hugging Face hesabının private modele erişebildiğinden emin olun ve standart HF kimlik
doğrulamasını yapın:

```bash
hf auth login
uv run python scripts/install-private-model.py
```

Installer yalnız registry'de listelenen dosyaları, tam HF commit'inden indirir; her dosyanın
boyutunu ve SHA-256 değerini doğrular ve ancak tüm doğrulamalar geçerse
`models/hushmark-berturk-112m` dizinine atomik olarak yerleştirir. Token komut satırına
yazdırılmaz ve repoya kaydedilmez. Mevcut kurulumu bilinçli olarak yenilemek için `--force`
kullanılabilir.

## Hushmark core ile çalıştırma

```bash
export HUSHMARK_CORE_NER_BACKEND=berturk
export HUSHMARK_CORE_MODEL_ID=hushmark-berturk-112m
export HUSHMARK_CORE_NER_THRESHOLD=0.50
```

`hushmark_core.ner.berturk_span.BerturkSpanModel` kanonik loader/model sınıfıdır. Eğitim
paketi `hushmark_bench.berturk_span` üzerinden aynı sınıfı yeniden export eder; böylece eğitim,
değerlendirme ve production runtime arasında kopyalanmış mimari kodu oluşmaz. Yükleme tamamen
lokaldir ve `safetensors` kullanır; uzaktan özel kod çalıştırılmaz.

## Eğitim özeti

- Temel encoder: `dbmdz/bert-base-turkish-cased`, revision
  `b6e1de16c983e0f2c70664591ea3f22810072608`.
- 200.592 eski sentetik kayıt ve 28.000 yeni sentetik kayıt; toplam 228.592 benzersiz kayıt.
- Epoch örneklemesi: %70 eski replay, %30 yeni veri.
- A100-SXM4-80GB, BF16, batch size 32.
- Seçilen checkpoint: 4.000. adım; erken durma: 8.000. adım.
- Eğitim süresi: 572,599 saniye.

RunPod yeniden üretim akışı `docs/train-berturk-runpod.md`, eğitim komutu
`bench/train/train_berturk.py`, kilitli karşılaştırma `bench/train/evaluate_berturk.py`
dosyalarındadır.

## Kilitli değerlendirme

| Set | BERTurk 112M | `hushmark-tr` 289M |
| --- | ---: | ---: |
| Eski 12-tip strict macro F1 | `1.000000` | `0.994124` |
| Yeni PERSON/ADDRESS/DOB strict macro F1 | `0.975286` | `0.536787` |
| Yeni micro F1 | `0.986301` | `0.617954` |
| Yeni boş belgelerde yanlış pozitif span | `37` | `545` |

Yeni sette aday `PERSON=1.0`, `ADDRESS=1.0`, `DOB=0.925859` üretti. Buna rağmen resmî
`adopt=false` kararı korunmuştur: önceden tanımlanmış legacy kuralı mutlak `+0.05` iyileşme
istiyordu; `0.994124` tabanından bu eşik pratikte erişilemez. Kilitli sonuçlara bakıldıktan
sonra eşik veya hiperparametre değiştirilmedi.

## Sınırlamalar ve terfi koşulu

- Eğitim ve değerlendirme sentetiktir; gerçek üretim dili için insan kontrollü yeni bir
  holdout ve shadow trafik değerlendirmesi gerekir.
- 256 subword token üzerindeki metinler çağıran tarafından güvenli biçimde parçalanmalıdır.
- Sınıf kümesi kapalıdır; yeni etiket yeniden eğitim gerektirir.
- Kimlik numarası, telefon, e-posta ve erişim anahtarı gibi deterministik sınıflar Hushmark
  doğrulayıcılarının sorumluluğundadır.
- Bu checkpoint için doğrulanmış ONNX export yoktur; yalnız `berturk` PyTorch backend'i
  desteklenir.
- Model anonimleştirme veya KVKK uyumluluğu garantisi değildir.

Production terfisi, kilitli sonuçlardan bağımsız tanımlanmış yeni bir kabul kuralı, gerçekçi
holdout, shadow test, gecikme/bellek ölçümü ve rollback planıyla ayrı bir karar olarak
yapılmalıdır.
