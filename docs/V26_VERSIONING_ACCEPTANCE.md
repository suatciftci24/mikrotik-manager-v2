# V2.6 sürüm yönetimi kabulü — 2026-11-17

Yerel uygulama ve hedefli kontroller PASS. Başlangıç temiz cleanup dalı,
HEAD `892e87d578fa0801a397c0e7af9718849ab101a0`.

Ön inceleme: AGENTS, PROGRESS ve en son cleanup kabulü okundu. Paket ve
FastAPI sürümü 0.1.0 idi; V2.6 yalnız ürün adıydı. Ortak panel `/` ve
`/api/ready` HTTPS GET denemeleri curl exit 6 (DNS çözümlenemedi) verdi.
Canlı sürüm doğrulanamadı. Yeni 2.6.0 yalnız bu yerel değişikliğin atamasıdır.
Önceki canlı code drift/yedek/SSH engelleri bu görevle kapatılmadı.

Uygulama: release.json merkezi kaydı, paket/lock uyumu, derleme sürümünü
okuyan footer; backend başlangıcında sabitlenen sürüm, OpenAPI ve mevcut
salt okunur ready yanıtında app_version. Yeni endpoint veya yetki değişimi yok.
CHANGELOG, yerel SemVer artırma/check aracı, VERSIONING prosedürü ve AGENTS
kuralı eklendi. API sözleşmesi v1 olarak korunur.

Doğrulama:

- `python3 tools/release.py check`: 2.6.0.
- `python3 tools/test_release.py`: üç test PASS; geçici kopyalarda patch/minor/
  major artışı, paket tutarsızlığı/geçersiz SemVer reddi, backend sürümü ve
  gerçek ready fonksiyonu app_version yanıtı. Tam uygulama import edilmedi.
- `npm --prefix frontend run build`: TypeScript/Vite PASS (1715 modül).
- Üretilmiş ana JS bundle içinde footer running-version ve merkezi sürüm
  kaydı doğrulandı. Tarayıcı/görsel kabul veya canlı sürüm kabulü yapılmadı.
- `git diff --check`: PASS.

Baseline `v2.6-clean-baseline-20261117` hedefi
`a59728f1843a0ffa620c32270abb8295f73a0afb` değişmedi. Bu başlangıç görevinde
yeni SemVer etiketi oluşturulmadı; sonraki güncellemeler için açıklamalı
etiket prosedürü belgelendi. Yalnız yerel cleanup commit'i hedeflenir.
Push, VDS deploy, restart, DB/migration/router/RADIUS işlemi yok.
