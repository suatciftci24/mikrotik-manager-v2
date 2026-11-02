# 7bb617c eski pilot yükseltme kararı — 2026-10-31

**BLOCKED: mevcut pilot yerinde yükseltilmeyecek.** Mevcut DB korunur.
Bu karar yalnız yerel kaynak incelemesidir; canlı şema/DB doğrulaması değildir.
Hedef: `7bb617c4838c1bd94b8cbe612981cabe5186b6b1`.

## Eksik tabloların anlamı

Hedefin ileri SQL dosyaları 28 tablo tanımlar; 002 down dosyası dahil değildir.

| Dosya | Tablo sayısı | Kapsam |
| --- | ---: | --- |
| 001 | 10 | roles, permissions, role_permissions, panel_users, routers, customers, subscription_plans, subscriber_accounts, subscriber_events, audit_logs |
| 002–005 | 10 | v2_demo sentetik depoları, kimlik ve ayarlar |
| 006 | 3 | public.v2_registered_routers, public.v2_router_verifications, public.v2_router_registry_audit |
| 007–008 | 4 | v2_router_workspace ve v2_subscriber_workspace |
| 009 | 1 | v2_demo.first_admin_setup; ayrıca mevcut kimlik tablolarında ALTER |

001 yeni modül yükseltmesi değil, ilk çekirdek şema tasarımıdır. Backend
models/access.py, identity.py, network.py, subscriptions.py ve operations.py
bu tabloları modeller. Çalışma alanı servisleri ayrı 007/008 modellerini;
router registry servisi 006 modellerini kullanır. Dolayısıyla eksik çekirdek
şema, mevcut demo/çalışma alanı verilerinin yokluğunu göstermez.

Bildirilen 18/28 ve 10 eksik public tablo sayıları, 001'in uygulanmamış olmasıyla
uyumludur. Ancak özet eksik adları içermediği için sayılardan kesin dosya eşlemesi
veya kalan 18 tablonun tam uyumluluğu çıkarılamaz. Mevcut teşhis çıktısındaki adlar
001 listesiyse eksikler tamamen ilk çekirdek tasarımdır; 006 adlarından biri varsa
registry kapsamı da eksiktir. Yeni teşhis döngüsü başlatılmadı.

## Veri etkisi ve en küçük olası değişiklik

001 yalnız 10 CREATE TABLE ve 5 CREATE INDEX içerir. Yabancı anahtarları kendi
10 tablosuna gider; v2_demo, registry veya workspace tablolarına ALTER/DML,
seed, kopyalama veya veri dönüşümü yapmaz. ON DELETE kuralları tablo tanımıdır,
çalıştırılan DELETE değildir. public adları dosyada şema nitelemesizdir;
uygulama search_path'e bağlıdır. Mevcut ADMIN v2_demo.users kaydı, bu dosya ile
panel_users'a aktarılmaz; yeni çekirdek tablolar boş kalır.

Yalnız 001 eksikliği kesin kanıtlansaydı en küçük aday, mevcut dosyaları yeniden
oynatmak yerine public şeması açıkça sabitlenmiş, transaction içindeki yalnız
bu eklemeler olurdu. Bu aday henüz uygulanabilir yükseltme değildir: nesne
çakışmaları, mevcut kolon/constraint/index ve izin uyumu, kurulu kaynak bağı,
korunacak veri invariantları ve geri dönüş henüz kanıtlanmamıştır.
002–009 topluca tekrar çalıştırılmaz: 004/005 schema_state günceller; 009 mevcut
users/schema_state/alarm_actions tanımlarını değiştirir ve tekrar oynatılabilir
değildir. IF NOT EXISTS mevcut tanımın eşitliğini kanıtlamaz.

Migration dosyası kopyalama, kontrol atlama, stamp veya 001–009 tamamlandı kaydı
oluşturma yapılmaz. schema_state.version=1 depo sürümüdür, migration head değildir.
Dosya hash eşitliği de DB uygulama geçmişini kanıtlamaz. Mevcut updater legacy
engeli korunur; yükseltmeyi açacak yerel kod değişikliği güvenle hazırlanamadı.

## Eski pilot ile temiz kurulum ayrımı

- Eski pilot: geçmiş UNKNOWN kalır; DB, kayıtlar, kimlikler ve yapılandırma
  değiştirilmez. Temiz-kurulum yolu mevcut cluster/DB'ye yöneltilemez.
- Yeni pilot adayı: farklı V2 cluster/data_directory, DB, rol, sırlar, port,
  yapılandırma ve servis kimliği gerekir. Mevcut sabit-hedef kurulum betikleri
  yeniden çalıştırılarak bu ayrım sağlanmış sayılmaz; ayrı profil hazırlanmalıdır.
- Yeni kurulum ancak boş hedef kimliği doğrulanınca açık forward manifestiyle
  hazırlanır. 009'un yetkili kimlik kurulum transaction'ı korunur. Yeni hedefte
  başarıyla uygulanan her dosyanın SHA256, sıra ve zamanı transaction ile kaydedilir;
  bu kayıt eski DB'nin geçmişine ilişkin iddia taşımaz. Startup migration yoktur.
- İlk aşamada eski DB'den toplu veri veya ADMIN/hash aktarımı yapılmaz. Eski pilot
  korunur; aktarım gerekiyorsa ayrıca alan bazlı eşleme, LOCAL/RADIUS otoritesi,
  audit/kimlik bütünlüğü ve yedekten geri dönüş planıyla ele alınır. Temiz kurulum,
  eski verinin taşınmış olması demek değildir.
- Geçiş kabul edilene kadar eski hedef değiştirilmez; geri dönüş eski hedefi
  koruyarak yapılır. DROP/reset/down migration kullanılmaz. Yeni profil ve yeni
  geçmiş kaydı bu görevde uygulanmadı; mevcut native installer bu iş için hazır
  kabul edilmez.

## Sonraki tek adım ve yerel kanıt

Ayrı temiz V2 pilot için mevcut sabit hedefleri kullanmayan, boş-hedef zorunlu
kurulum profilini **yerelde hazırlamak**. Canlı oluşturma/geçiş ayrıca açık kapsamlı
yetki ister. Mevcut DB'yi onarma veya yeniden teşhis görevi açılmaz.

Hedef Git SQL'lerinin statik incelemesi: 28 tablo ve 001 için yalnız 10 tablo +
5 indeks doğrulandı; yerel migration ağacı hedefle aynı. İlk yardımcı assertion,
FK içindeki ON DELETE'ı DML sanıyordu; statement başlangıcına göre düzeltildi ve
yalnız bu kontrol tekrar geçti. PostgreSQL execution/transaction/geri dönüş testi
çalıştırılmadı. Güvenli çalıştırılabilir kod değişikliği olmadığı için yeni genel
veya sentetik uygulama testi eklenmedi. SSH, DB bağlantısı, migration, dağıtım,
restart, router ve commit/push yapılmadı.
