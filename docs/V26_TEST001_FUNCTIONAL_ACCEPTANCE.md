# V2.6 v26-test-001 işlevsel kabulü — 2026-11-07

Başlangıç: main-guncel/e89f621. Yerel sentetik kapsam PASS; VDS yazma,
gerçek PostgreSQL/HTTP, gerçek login ve tarayıcı kabulü BLOCKED/çalıştırılmadı.
Ürün hatası saptanmadı; ürün kodu veya güvenlik kontrolleri değiştirilmedi.

Mevcut test_quick_actions.py, test_v26_subscriber_consistency.py ve
SubscriberTransactions SQLite fixture'ı incelendi. Önceki başarılı testler
tekrarlanmadı. Mevcut geçici DB fixture'ı ve ASGI istemcisi yeni tek-abone
kabulünde yeniden kullanıldı; sadece yeni üç senaryo çalıştırıldı.

## İzolasyon

Her fixture'da yalnız v26-test-001 adlı bir sentetik abone var. LEGACY kimliği
v26-test-001; workspace username v26-test-001, kimliği sözleşmenin zorunlu
kıldığı demo-managed-sub-UUID. Kimlik regex'i gevşetilmedi. Workspace için
fixture'ın sentetik router satırı kullanılır; dış cihaz adaptörü yoktur.
SQLite her testin private TemporaryDirectory alanında oluşturulur ve kapanışta
silinir. Yapılandırılmış PostgreSQL engine connect/begin çağrıları workspace
testlerinde hata verecek şekilde engellenir. LEGACY bellek testinde engine
connect engellenir. Mevcut DB/hesap/şema/sır kullanılmaz veya sorgulanmaz.

## PASS kanıtı

| Akış | API | Kayıt/detay | Audit ve tekrar |
| --- | --- | --- | --- |
| Workspace EXTEND +30 gün | ASGI POST 200, success/recorded | SQLite alanı, revision+1 ve GET detay eşit | Eski/yeni tarih, aktör, UTC zaman, operation, receipt; aynı UUID tekrarında snapshot aynı |
| Workspace PLAN | ASGI POST 200 | Paket değişir; tarih/durum korunur | DB event, detay ve merkezi geçmiş receipt'i eşit |
| Workspace STATUS PAUSED / ACTIVE | Her iki ASGI POST 200 | Durum değişir; paket/tarih korunur | Her adım tek event/revision; yeniden gönderme ek event üretmez |
| LEGACY QuickActions EXTEND / PLAN / PAUSED / ACTIVE | ASGI POST 200 | Bellek deposu, GET detay ve API sonucu eşit | Her adım tek aktör/action/event; aynı UUID ikinci kez uygulanmaz |

Workspace tüm başarılı adımlarda tabloyu yeni session ile doğrudan okur;
tek username ve event sayısını kontrol eder. Detay history sözleşmesi ID
sunmaz; revision+operation üzerinden bulunup DB event'in aktör/zaman/eski-yeni
alanlarıyla eşleştirilir. Merkezi history UUID üzerinden özgün receipt ile
eşleşir. Paket/durumda korunması gereken alanlar ayrıca karşılaştırılır.

Negatif kontroller: workspace VIEWER ve eksik onay header'ı 403; explicit
confirmed=false, geçersiz operation ve bilinmeyen source 422. Hesap ve event
snapshot'ı değişmez. Audit SQLAlchemyError enjeksiyonunda success=false,
recorded=false; hesap ve event tamamen eski halindedir. Stale revision
başarısızlığı hesabı değiştirmez, bir FAILED receipt/audit kaydeder; aynı UUID
tekrarında ek kayıt oluşmaz. LEGACY VIEWER ve router yazma yetkisi kaybı 403,
confirmed=false 422; bellek hesabı/audit/request snapshot'ı değişmez.

## Test aracı sınırı

İlk socket-free ASGI denemesi AnyIO worker dönüşünde timeout verdi. Üründen
bağımsız `anyio.to_thread.run_sync(lambda: 'WORKER_OK')` da timeout üretti.
Yalnız yeni test istemcisinde sync çağrılar inline çalıştırıldı; gerçek ASGI
middleware/router, Pydantic, response model, yetki ve transaction işlevleri
korundu. Eşzamanlılık/worker/network kabulü iddia edilmez. Süre sınırı veya
ürün assertion'ı gevşetilmedi. İlk yeni history assertion'ının ID beklentisi
mevcut revision tabanlı sözleşmeye uyarlandı; yalnız başarısız workspace
başarı senaryosu tekrarlandı. İki diğer senaryo PASS sonrası tekrarlanmadı.

Komut (yerel proje terminali, yalnız bu yeni dosya):

```bash
PYTHONPATH=backend:backend/tests .venv/bin/python -m unittest backend.tests.test_v26_test001_acceptance -v
```

Sonuç: üç yeni senaryo PASS (iki senaryo son ortak çalıştırmada; düzeltilen
workspace başarı senaryosu tekil son çalıştırmada). Ürün değişikliği yok;
önceki frontend/build/PG suite'leri tekrarlanmadı. Diff kontrolü PASS.

## BLOCKED ve sonraki adım

VDS'de yazma bu görevin açık yasağıdır; denenmedi. SSH/deploy/restart veya
V1/V2.5/router/RADIUS/IPsec erişimi yok. LEGACY PostgreSQL kalıcılığı bu bellek
testiyle PASS olmaz. SQLite, PostgreSQL uyumluluğu veya gerçek HTTP/browser
kabulü yerine geçmez. API detay yanıtı doğrulandı, tarayıcıda çizilmiş detay
ve audit görünümü doğrulanmadı. Kimlik fixture'ı gerçek login değildir.

Sonraki tek işlem: izinli, tamamen disposable yerel V2.6 PostgreSQL/HTTP
ortamında aynı v26-test-001 senaryosunun kalıcılık ve detay/audit kabulünü
çalıştırmak; VDS veritabanını kullanmamak.
