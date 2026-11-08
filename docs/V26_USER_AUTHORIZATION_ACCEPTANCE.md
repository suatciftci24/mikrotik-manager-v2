# V2.6 kullanıcı ve rol yetkileri

## Rol sınırları

| Rol | Erişim |
| --- | --- |
| `ADMIN` | Router grant'leri kapsamındaki yönetim; tam `can_view` kapsamı varsa kullanıcı/audit, sistem ve global yönetim ekranları. ADMIN grant'leri belirli router'larda PPPoE, Hotspot ve alarm onayı verebilir. |
| `OPERATOR` | Yalnız `can_view` verilmiş router'larda ayrıca atanmış `can_manage_pppoe` / `can_manage_hotspot` işlemleri. Kullanıcı/sistem yönetimi, alarm onayı, router kaydı/onboarding ve diğer router'lara erişim yoktur. Mevcut Hotspot mutasyon servisi bulunmadığından grant tek başına işlem oluşturmaz. |
| `VIEWER` | Router başına `can_view`, rapor ve MikAjanı grant'leri kadar salt okunur erişim; yazma/ACK grant'i reddedilir. |

Her izin `can_view` ve ilgili router grant'iyle birlikte değerlendirilir. Backend, PPPoE create/update/quick, abone fotoğrafı ve ilgili router okuma yollarında scope'u her istekte kontrol eder. Kullanıcı yönetimi ve kritik sistem alanları `current_admin` ile ADMIN'e kapalıdır.

## Hesap, denetim ve oturum

- Kullanıcı rol/aktif/izin güncellemeleri mevcut `users` ve `user_audit` transaction/idempotency sözleşmesini kullanır. Audit aktör, hedef, zaman, önceki/yeni rol-durum-grant, sonuç ve request UUID içerir; parola/hash/token içermez.
- Kendini ADMIN/aktif/tam yönetim kapsamından düşürme ve son aktif ADMIN'i kaldırma reddedilir. Kullanıcı yazımı ile başarılı audit aynı transaction'dadır; audit yazımı başarısızsa kullanıcı değişikliği rollback olur.
- Oturum token'ı rol/grant taşımaz. Her istekte güncel kullanıcı tekrar okunur; rol değişikliği aynı cookie'de yeni sınırı uygular, pasif hesap 401 alıp session kaydından çıkar.
- `010_operator_role.sql` rol CHECK kısıtını yalnız `v2_demo` ve `v26_acceptance` kullanıcı tablolarına hazırlar. Bu görevde hiçbir veritabanına bağlanılmadı ve migration çalıştırılmadı.

## Doğrulama

Soketsiz hedef testler: kimlik/yetki 18, kullanıcı transaction 10, pilot kimliği 6 backend testi; `userManagement.test.mjs` 5 UI testi. Frontend typecheck ve production build PASS. PostgreSQL/HTTP/browser kabulü bu test sonucu olarak iddia edilmez.
