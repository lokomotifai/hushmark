# Hushmark yönetim kılavuzu

## Günlük kontrol

1. `/readyz` durumunun hazır olduğunu ve core bağlantısının geçtiğini doğrulayın.
2. Dashboard'da maskeleme ve bloklama sayılarını beklenen trafikle karşılaştırın.
3. Denetim zinciri doğrulamasını çalıştırın; kırık zinciri olay müdahalesine aktarın.
4. Lisans durumunu, bitiş tarihini ve grace penceresini izleyin.

## Politika yönetimi

Politika matrisi kapalı 24 tip taksonomisini kullanır. Bilinmeyen tip, bilinmeyen eylem ve
multimodal içerik varsayılan olarak bloklanır. Değişiklikten önce mevcut politikayı dışa aktarın,
değişikliği dar kapsamda uygulayın ve sahte upstream ile hem maskelenen hem bloklanan bir örneği
doğrulayın. Streaming açıkken buffered response scan seçilemez.

## Rol ve de-mask

`admin` politika ve kimlik yönetir. `operator` yetkili placeholder çözümleme yapabilir. `auditor`
denetim olaylarını ve zincir sonucunu görür fakat değer çözümleyemez. De-mask işlemlerini gerekçe,
oturum ve olay kaydıyla sınırlayın.

## Lisans yaşam döngüsü

Geçerli ve grace durumlarında yetkili yönetim özellikleri çalışır. Grace sonrası konfigürasyon
salt-okunur/frozen olur; runtime trafiği bank-safe davranış gereği devam eder. Yeni lisans dosyasını
ve public key'i birlikte doğrulayın; issuer private key'i runtime sistemine koymayın.

## Olay müdahalesi

Core erişilemiyorsa gateway 503 ile fail-closed davranır. Audit zinciri kırılırsa ilgili NDJSON
dışa aktarımını değiştirilemez kanıt deposuna alın, son bilinen anchor'ı karşılaştırın ve yazma
erişimlerini inceleyin. Placeholder değeri veya müşteri metnini loglara kopyalamayın.
