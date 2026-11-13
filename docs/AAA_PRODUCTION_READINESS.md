# AAA Production Readiness

Tarih: 2026-11-13
Durum: PREPARATION / PRODUCTION BLOCKED

## 1. Remote Observer
- Kimliği doğrulanmış, şifreli uzak bağlantı.
- Tenant, actor, router ve operation kapsam doğrulaması.
- Replay, timeout, eksik veya çelişkili kanıtta fail-closed.
- UNKNOWN durumunda otomatik retry veya writer işlemi yok.
- Kabul: izole ortamda olumlu/olumsuz senaryolar PASS.

## 2. Signing Key Lifecycle
- Anahtarlar kodda, Git'te veya loglarda tutulmaz.
- Güvenilir secret store ve erişim yetkileri tanımlanır.
- Key ID, rotasyon, iptal ve eski anahtar geçerlilik politikası.
- Yanlış/iptal edilmiş anahtarla gelen kanıt reddedilir.
- Kabul: izole rotasyon ve iptal testleri PASS.

## 3. PostgreSQL Runtime Principal
- Ayrı, minimum yetkili LOGIN rolü.
- SUPERUSER ve BYPASSRLS yasak.
- Bağlantı havuzunda tenant/actor bağlamı sızıntısı engellenir.
- Her işlemde yetki ve üyelik yeniden doğrulanır.
- Kabul: izole rol, pool reuse ve cross-tenant testleri PASS.

## 4. Production RLS
- Tenant izolasyonu ve owner kapsamı zorunlu.
- Eksik veya yanlış runtime context erişimi reddeder.
- Migration, rollback ve kurtarma prosedürü hazırlanır.
- Gerçek üretim kurulumu ayrı açık onay gerektirir.
- Kabul: hedef ortamda yetkili ve yetkisiz erişim testleri PASS.

## Güvenlik Sınırları
- V1, V2.5 pilotu ve canlı router sistemleri korunur.
- Gerçek AAA writer ve LOCAL expire worker kapalı kalır.
- Gerçek RADIUS, secret store ve üretim DB bağlantısı açılmaz.
- Canlı deploy, migration, restart ve veri değişikliği için
  kullanıcıdan yeni açık onay alınır.

## Kabul Durumu
| Alan | Durum |
|---|---|
| Sentetik Remote Observer | PASS (önceki izole kabul) |
| Gerçek Remote Observer | BLOCKED |
| Gerçek signing key lifecycle | BLOCKED |
| Üretim runtime principal/pool | BLOCKED |
| Üretim RLS rollout | BLOCKED |
| Gerçek AAA writer | DISABLED |

Bu belge hazırlık kontrol listesidir; üretim kabul belgesi değildir.
