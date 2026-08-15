<div align="center">

# Hushmark

**Yapay zekâ trafiği için Türkçe odaklı kişisel veri tespiti, geri döndürülebilir maskeleme ve kontrollü geri yükleme.**

[![CI](https://img.shields.io/github/actions/workflow/status/lokomotifai/hushmark/ci.yml?branch=main&label=CI)](https://github.com/lokomotifai/hushmark/actions/workflows/ci.yml)
[![Tedarik zinciri](https://img.shields.io/github/actions/workflow/status/lokomotifai/hushmark/supply-chain.yml?branch=main&label=tedarik%20zinciri)](https://github.com/lokomotifai/hushmark/actions/workflows/supply-chain.yml)
[![Sürüm](https://img.shields.io/github/v/release/lokomotifai/hushmark-open-core?label=sürüm)](https://github.com/lokomotifai/hushmark-open-core/releases/latest)
[![Lisans](https://img.shields.io/github/license/lokomotifai/hushmark)](LICENSE)

[English](README.md) · [Türkçe](README.tr.md) · [Dokümantasyon](docs/README-dev.md) · [Güvenlik](SECURITY.md) · [Katkı](CONTRIBUTING.md)

</div>

Hushmark, istekler bir yapay zekâ sağlayıcısına ulaşmadan önce hassas Türkçe verileri sizin kontrol
sınırınız içinde tutar. Deterministik tanıyıcıları Türkçe kişisel veri modeliyle birleştirir, açık
bir politika uygular, hassas alanları yer tutucularla değiştirir ve desteklenen yanıtlarda bu alanları
self-hosted ağ geçidi üzerinden kontrollü biçimde geri yükler.

> [!IMPORTANT]
> Geri döndürülebilir maskeleme teknik bir güvenlik tedbiridir; anonimleştirme, hukuki görüş veya
> mevzuata uyum garantisi değildir. Tespitler eksik ya da hatalı olabilir. Hushmark’ı temsilî
> verilerinizle doğrulayın; insan ve organizasyon kontrollerini koruyun.

## Neden Hushmark?

| Gizlilik ağ geçidi olmadan                          | Hushmark ile                                                                                     |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Ham kimlik verileri uygulama sınırından çıkabilir   | Politika, sağlayıcıya iletimden önce çalışır                                                     |
| Maskeleme davranışı uygulamalara dağılır            | Tespit, politika ve geri yükleme tek sınırda yürür                                               |
| Sağlayıcı kayıtları doğrudan tanımlayıcı içerebilir | Desteklenen tanımlayıcılar kapsamlı yer tutuculara çevrilir                                      |
| Olay kanıtı sonradan toplanır                       | Enterprise runtime, HMAC korumalı denetim zinciri ve Türkçe Madde 12 raporunu yerelde üretebilir |

## Depoda neler var?

- `core/`: FastAPI tabanlı tespit ve maskeleme otoritesi.
- `packages/gateway/`: Akış yanıtlarını geri yükleyebilen OpenAI ve Anthropic uyumlu vekil.
- `packages/gateway-enterprise/`: Kalıcı şifreli kasa, RBAC, denetim zinciri, çevrimdışı lisanslama
  ve Tedbir raporu. Paket adı tarihsel olarak korunur; kaynak kodu Apache-2.0 lisanslıdır.
- `apps/console/`: Türkçe/İngilizce operatör konsolu.
- `packages/sdk-ts/` ve `sdk-py/`: Tip güvenli TypeScript ve Python istemcileri.
- `bench/` ve `taxonomy/`: Tekrarlanabilir değerlendirme hattı ve kapalı v0.1 varlık taksonomisi.
- `deploy/`: Docker Compose, Helm, üretim ön kontrolü ve air-gap paketleme.

Daha küçük [hushmark-open-core](https://github.com/lokomotifai/hushmark-open-core) deposu; tespit
motoru, ağ geçidi, SDK’lar, benchmark ve taksonomi için yalnızca kaynak kodu içeren sürüm aynasıdır.
Bu tam depo kanonik geliştirme geçmişidir; iki depo da Apache-2.0 ile lisanslanır.

## Veri akışı

```text
Uygulama
    │ sağlayıcı uyumlu istek
    ▼
Hushmark Gateway ──► tespit + politika ──► maskeli istek ──► AI sağlayıcısı
    ▲                       │
    └──── geri yüklenen yanıt┴──── kapsamlı kasa / denetim kanıtı
```

Tespit sınırı kullanılamadığında Hushmark isteği kapalı tutar. Model çıktısı yalnızca bir sinyaldir;
politika ve maskeleme kararları modelin dışında kalır.

## Hızlı başlangıç

Gereksinimler: Node.js 22, pnpm 9, Python 3.12, uv, Docker ve seçilen model arka ucu için yeterli
yerel bellek.

```bash
./scripts/bootstrap.sh
./scripts/verify.sh
docker compose -f deploy/docker/compose.yaml -f deploy/docker/compose.dev.yaml up -d
```

Benimsenen `hushmark-tr` ağırlıkları bilinçli olarak Git’e konmaz. Model destekli başlangıçtan önce
ayrı dağıtılan ve sağlama toplamı doğrulanan modeli `models/hushmark-tr/` altına kurun. Bootstrap
üretim modelini kendiliğinden değiştirmez veya yeniden üretmez.

Tek sunuculu community pilotu için [üretim Compose](docs/install-compose-production.md) rehberini
kullanın; bu profil kalıcı değildir ve enterprise kanıt özelliklerini içermez. Kubernetes
için [Helm](docs/install-helm.md), bağlantısız ortamlar için [air-gap](docs/install-airgap.md)
rehberini kullanın.

## Yayımlanan çıktılar

| Çıktı          | Paket / imaj                                                                                  |
| -------------- | --------------------------------------------------------------------------------------------- |
| Core           | [`hushmark-core`](https://pypi.org/project/hushmark-core/) · `ghcr.io/lokomotifai/core:0.1.1` |
| Gateway        | `ghcr.io/lokomotifai/gateway:0.1.1`                                                           |
| Konsol         | `ghcr.io/lokomotifai/console:0.1.1`                                                           |
| Python SDK     | [`hushmark-sdk`](https://pypi.org/project/hushmark-sdk/)                                      |
| TypeScript SDK | [`@hushmark/ai-sdk`](https://www.npmjs.com/package/@hushmark/ai-sdk)                          |
| Ortak şemalar  | [`@hushmark/shared`](https://www.npmjs.com/package/@hushmark/shared)                          |

Sürüm iş akışları kaynak kanıtı ve SBOM üretir. İmaj imzalarını ve tasdiklerini
[güvenlik modelinde](docs/security.md) anlatıldığı gibi doğrulayın; hareketli etiketi sürüm kimliği
olarak kabul etmeyin.

## Proje durumu

Hushmark erken aşamadaki bir `0.1.x` sürümüdür. Depoda sentetik benchmark kanıtları ve dağıtım
testleri vardır; bu sonuçlar her kurumun trafiğinde aynı doğruluğu kanıtlamaz. Bilinen sınırlar ve
sonraki öncelikler [yol haritasında](ROADMAP.md) ve [model kartında](docs/model-card-hushmark-tr.md)
yer alır. Algılayıcı model seçilebilir; [model seçim rehberine](docs/models.md) bakın.

## Topluluk ve lisans

Hushmark [Apache License 2.0](LICENSE) altında açık biçimde geliştirilir. Katkılarda
[Developer Certificate of Origin](CONTRIBUTING.md#developer-certificate-of-origin) kullanılır; ayrı
bir CLA gerekmez. Katılmadan önce [Davranış Kuralları](CODE_OF_CONDUCT.md),
[yönetişim modeli](GOVERNANCE.md) ve [destek politikası](SUPPORT.md) belgelerini okuyun. Kaynak kodu
lisansı marka hakkı vermez; ayrıntılar [TRADEMARKS.md](TRADEMARKS.md) dosyasındadır.
