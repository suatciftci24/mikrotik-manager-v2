# AAA PostgreSQL izole kabul incelemesi — 2026-11-12

**Genel sonuç: BLOCKED — gerçek PostgreSQL kabulü çalıştırılmadı.**
Başlangıç `main-guncel` / `78c70dc`; temiz çalışma ağacı ve aynı GitHub SHA'sı
doğrulandı. Önceki 57 test tekrarlanmadı.

## İzolasyon kapısı

[Güvenlik incelemesindeki](AAA-POSTGRESQL-SECURITY-REVIEW.md) sabit disposable
kök `/tmp/mikrotik-v26-acceptance`, `os.path.lexists` ile yok olarak doğrulandı.
Owned PGDATA/cluster, marker, exact DB/rol ve hazır AAA şema kanıtı bulunmadığından
PostgreSQL bağlantısı kurulmadı. Başka DSN/env/credential veya mevcut local-demo
veritabanı alternatif hedef olarak aranmadı. Mevcut HTTP/WSL harness yeni cluster
hazırlar; `test_v26_identity_postgres.py` setup'ında `initdb` çağrısı vardır.
Bu görev yeni veritabanı oluşturmayı yasakladığı için harness çalıştırılmadı.
Kaynak kodundaki port/şema tanımları kurulu ve güvenli test ortamı kanıtı değildir.

## Kabul matrisi

| Kapsam | Sonuç | Kanıt / engel |
| --- | --- | --- |
| Gerçek PG claim TTL, prepared authorization, executor decision ve receipt | BLOCKED | Hazır doğrulanmış izole ortam yok; memory executor henüz PG UoW'ye bağlı değil |
| Membership resolver | BLOCKED | Kalıcı membership kaynağı, session-aware resolver ve actor/policy freshness entegrasyonu yok; sabit test grant'i gerçek üyelik değildir |
| Owner-writer PostgreSQL çalışma uyumu | BLOCKED | Additive tenant/fence/active-operation metadata ve bütün günlük writer'ların ortak protokole katılımı tamamlanmadı; katalog/MVCC/lock/rol/RLS doğrulanmadı |
| Owner CAS PostgreSQL SQL derlemesi | PASS, yalnız offline | AAA ve DAILY sorgularında tenant/subscriber/revision/fence/source/active-operation predicate ve UUID binding; DAILY için IS NULL |
| DI metadata TTL ve grant sınırları | PASS, yalnız fake session | 1–300 saniye, aware timestamp revalidation, değiştirilmiş grant reddi ve atomik metadata kontrolleri |
| Provider fixture | PASS, yalnız RAM | Replay tek etki/tek ACK; RADIUS enable için source fence; provider kanıtı owner commit sayılmaz |

## Kanıtlanan ve giderilen kod eksikleri

- `PostgresMetadataRepository.issue` 0.5 saniye TTL'yi kabul ediyordu. Alt sınır
  artık 1 saniye, üst sınır 300 saniye. Değiştirilmiş `ActionMetadata` JSON
  sözleşmesi yeniden doğrulanır; naive timestamp karşılaştırma TypeError'ı yerine
  sözleşme validation hatasıyla ret verilir. Mevcut DB clock kontrolü korunur.
- `require_ownership` değiştirilmiş grant içindeki truthy `actor_active='false'`
  veya `1` ve `membership_revision=True`/`1.5` değerlerini kabul ediyordu.
  Artık yalnız gerçek True ve pozitif int revision kabul edilir. Bu kontrol
  güvenilir resolver'ın yerini tutmaz; runtime'a yeni yetki yolu açılmaz.

Yeni testler düzeltme öncesinde bu sorunları gösterdi, sonrasında geçti.
`backend.tests.test_aaa_postgres_contract_boundaries` 4 yeni test;
doğrudan etkilenen metadata repository 8 ve owner contract 7 test;
`ProviderFencingTests` içinden replay ve source-fence için 2 test: **21 PASS**.
Fake-session testlerinde socket/psycopg/SQLite bağlantıları yasaktır. SQLAlchemy
PostgreSQL dialect derlemesi gerçek sunucu SQL yürütmesi veya transaction kanıtı
değildir. Yeni PostgreSQL driver/engine, resolver varsayımı veya schema DDL yok.

## Korunan sınırlar ve sonraki adım

HTTPS 200 ve kaynakta doğrulanmış `/api/ready` kimliği değişiklik öncesi/sonrası
başarılı. Yanıttaki `database_checked=false` nedeniyle DB sağlığı iddia edilmez;
DB sorgulayan `/api/health` çağrılmadı. Mevcut PG verileri/kullanıcılar okunmadı
ve değiştirilmedi. DB oluşturma/migration/DROP/TRUNCATE/DELETE/restore, servis
restartı, deployment, VDS veya gerçek router/RADIUS işlemi yapılmadı.

Sonraki gerekli girdi: önceden hazırlanmış, kimliği ve ownership'i kanıtlanmış
AAA şemalı izole kabul ortamı. Bunun yanında [resolver](AAA-MEMBERSHIP-RESOLVER-PLAN.md)
ve [writer](AAA-OWNER-WRITER-INTEGRATION-PLAN.md) ön koşulları tamamlanmalıdır.
Bu kayıttan yeni DB/migration veya mevcut veriye yazma izni türetilmez.
