<div align="center">

# Hushmark Open Core

**Hushmark’ın yalnızca kaynak kodundan oluşan tespit motoru, ağ geçidi, SDK, benchmark ve taksonomi sürümü.**

[![CI](https://img.shields.io/github/actions/workflow/status/lokomotifai/hushmark-open-core/ci.yml?branch=main&label=CI)](https://github.com/lokomotifai/hushmark-open-core/actions/workflows/ci.yml)
[![Sürüm](https://img.shields.io/github/v/release/lokomotifai/hushmark-open-core?label=sürüm)](https://github.com/lokomotifai/hushmark-open-core/releases/latest)
[![Lisans](https://img.shields.io/github/license/lokomotifai/hushmark-open-core)](LICENSE)

[English](README.md) · [Türkçe](README.tr.md) · [Güvenlik](SECURITY.md) · [Katkı](CONTRIBUTING.md)

</div>

Hushmark, istekler bir yapay zekâ sağlayıcısına ulaşmadan önce hassas Türkçe verileri sizin kontrol
sınırınız içinde tutar. Deterministik tanımlayıcıları ve modelin bulduğu alanları tespit eder, açık
bir politika uygular, desteklenen değerleri kapsamlı yer tutucularla maskeler ve desteklenen
sağlayıcı yanıtlarında geri yükler.

> [!IMPORTANT]
> Geri döndürülebilir maskeleme teknik bir güvenlik tedbiridir; anonimleştirme, hukuki görüş veya
> mevzuata uyum garantisi değildir. Tespitler eksik ya da hatalı olabilir. Üretimden önce Hushmark’ı
> temsilî verilerinizle değerlendirin.

## Bu depo nedir?

Bu depo, kanonik geliştirme deposu olan
[`lokomotifai/hushmark`](https://github.com/lokomotifai/hushmark) içindeki herkese açık çalışma zamanı
kaynaklarının izin listesiyle üretilen sürüm aynasıdır. Benimsenen model ağırlıklarını, özel
değerlendirme veri kümelerini, konsolu, kalıcı kasayı, RBAC’i, denetim kanıtını, lisans üreticisini
ve dağıtım sırlarını içermez.

| Yol                     | Amaç                                                              |
| ----------------------- | ----------------------------------------------------------------- |
| `core/`                 | FastAPI tabanlı Türkçe kişisel veri tespit ve maskeleme otoritesi |
| `packages/gateway/`     | OpenAI ve Anthropic uyumlu ağ geçidi                              |
| `packages/sdk-ts/`      | TypeScript istemci yardımcıları                                   |
| `sdk-py/`               | Python istemcisi                                                  |
| `packages/shared/`      | Herkese açık şemalar ve taksonomi tipleri                         |
| `bench/` ve `taxonomy/` | Sentetik benchmark hattı ve kapalı v0.1 taksonomisi               |

## Kaynak ağacını doğrulama

Gereksinimler: Node.js 22, pnpm 9, Python 3.12 ve uv.

```bash
git clone https://github.com/lokomotifai/hushmark-open-core.git
cd hushmark-open-core
./scripts/bootstrap.sh
./scripts/verify.sh
```

Benimsenen `hushmark-tr` modeli ayrı dağıtılır ve sağlama toplamıyla doğrulanır. Kendiliğinden
indirilmez veya yeniden üretilmez. Üretim ağırlığı isteyen testler kaynak doğrulama yolunda açıkça
bildirilerek dışarıda bırakılır.

Yayımlanan istemci ve çalışma zamanı paketleri bağımsız kurulabilir:

```bash
pip install hushmark-core hushmark-sdk
npm install @hushmark/ai-sdk @hushmark/shared
```

Bileşen kullanımı için [`core/README.md`](core/README.md), [`sdk-py/README.md`](sdk-py/README.md) ve
[`packages/sdk-ts/README.md`](packages/sdk-ts/README.md) dosyalarına bakın. Tam Compose, üretim ve
konsol dağıtım kaynakları kanonik depodadır.

## Sürüm sınırı

Çıkarma testi sembolik bağlantıları, özel yol adlarını, model çıktılarını ve özel veri kümesi
kanaryasını reddeder. Kesin sürüm sınırı kanonik depodaki `tools/release` kodunda incelenir. Bu
aynayı özel veri veya model çıktısı için hedef olarak kullanmayın.

## Durum, topluluk ve lisans

Hushmark erken aşamadaki bir `0.1.x` sürümüdür. Sentetik benchmark kanıtı regresyon için yararlıdır;
her kurumun trafiğindeki doğruluğu kanıtlamaz. [Model kartını](docs/model-card-hushmark-tr.md),
[güvenlik modelini](docs/security.md) ve [yol haritasını](ROADMAP.md) okuyun.

Kaynak [Apache License 2.0](LICENSE) altındadır. Kod değişiklikleri sonraki çıkarmada korunması için
kanonik depoya gönderilmelidir; aynaya özgü dokümantasyon ve topluluk düzeltmeleri burada önerilebilir.
[Katkı rehberi](CONTRIBUTING.md), [Davranış Kuralları](CODE_OF_CONDUCT.md) ve
[Güvenlik Politikası](SECURITY.md) katılım koşullarını açıklar.
