# Merkezi senkronizasyon simülatörü — sözleşme v1

Varsayılan kapalıdır. Import, API GET veya UI ekranı simülasyon başlatmaz.
RouterOS API/SSH/SNMP/RADIUS client'ı, scheduler veya dış yazma yoktur.
Bu bir canlı entegrasyon ya da business PostgreSQL ingest servisi değildir.

## Açık çalışma ve izolasyon

Normal V2 kökünde `PYTHONPATH=backend .venv/bin/python -m app.sync_simulator --run`
yeni bir koşum üretir. Argümansız komut yalnız yardım gösterir. Kaynak saati sabit
2026-10-28T12:00:00Z ve deterministik adımlardır; gerçek rapor üretim saati ayrıca
kaydedilir. Kaynak gözlemleri canlı/bugüne ait ölçüm gibi gösterilmez.

Beş bağımsız sanal router sim-router-001..005, mevcut demo envanterine eklenmez.
Mevcut dört routerdan sunucu tarafında belirlenen bir owner izin kapsamına bağlanır;
001 ve 005 aynı owner'ın iznini paylaşır ama state/cursor/abone/oturumları bağımsızdır.
Owner eşlemesi kullanıcı girdisinden alınmaz. Mevcut 14 demo abonesi veya audit,
ayar, alarm ve kullanıcı kayıtları okunup yeniden seed edilmez/değiştirilmez.
Yeni aboneler yalnız sanal router namespace'inde motor state'inde bulunur.

Her yeni koşum UUID ile ayrı `.local/sync-simulator/<run_id>.json` dosyasında
saklanır. Önceki koşumlar korunur; doğrulanmış bütün özet `latest.json` üzerine
atomik os.replace ile yayımlanır. Dosyalar 0600, yol sahipliği/symlink guard'lıdır.
Yayın kısmen başarısızsa eski latest korunur; yeni tamamlanmış arşiv dosyası
kalabilir. Bu yerel atomiklik power-loss/fsync veya dağıtık durability garantisi
değildir. Business DB şeması/migration/seed yoktur.

## Veri ve işlem sınırı

`scenarios -> SimulatorEngine -> Batch/Observation + reconcile -> candidate
Replica + subscribers + sessions + alarms + isolated audit -> tek state commit ->
Report whitelist doğrulaması -> yeni koşum arşivi -> atomik latest`.

Aşama 16/17 source_id, cursor, base_cursor, snapshot sequence, revision/gözlem
watermark, UTC ve deterministik record sıralaması yeniden kullanılır. İşlem lock
altında beklenen cursor ile CAS yapar. Candidate içinde tüm projection/audit
hazırlanır; hata/bozuk veri/partial fault commit öncesi atılır ve son başarılı durum
bozulmaz. Aynı batch aynı effect/audit/session üretmez; yalnız atlanan gözlem sayısı
artar. Cursor aynı ama içerik farklıysa reddedilir. Audit kimliği koşum namespace'i
altında `(run_id, virtual_router_id, record_id, revision)` kapsamındadır; yeni UUID
koşumu önceki koşumun replay'i veya business işlemidir diye yorumlanmaz.

PPPoE kaynak otoritesi LOCAL/RADIUS zorunlu ve değiştirilemez. Yabancı subject/kayıt
namespace'i reddedilir. CREATE, PROFILE_CHANGE, DISABLE, ENABLE, EXPIRE ve session
OPEN/CLOSE audit'i sadece koşum içindedir; eski/yeni değerler aynı candidate'ta tutulur.
Yeni bağlantı yeni session source ID ister. İlk oturum 20 sn, yeniden açılan ayrı
oturum 10 sn sonra kapanır; ACTIVE oturumun bitiş süresi bilinmiyorsa null'dır.

WAN/IPsec gözlemleri UP/DOWN/UNKNOWN'dır; freshness AVAILABLE değilse DOWN alarmı
üretilmez. Aynı açık problem aynı alarm kimliğini korur. ACK ACKNOWLEDGED yapar,
RESOLVED yapmaz. Kaynak UP geldiğinde RESOLVED olur; ACK bilgisi ayrı korunur.
Bu simulator projection'ı mevcut gerçek demo Alarm Merkezi action/audit deposuna
bağlanmaz ve mevcut ACK/read state'ini değiştirmez.

## Beş senaryo

1. ONLINE, profil değişikliği, WAN/IPsec DOWN, offline test ACK, UP/RESOLVED,
   disable/session close, enable/yeni session, EXPIRE/session close.
2. OFFLINE kaydı ve bağımsız TIMEOUT; son başarılı snapshot kalır.
3. UNKNOWN başlangıcı, timeout ve belirlenmiş retry zamanında ONLINE toparlanma.
4. WAN/IPsec DOWN açık alarmı; bozuk router payload'ı rollback olur ve ERROR kaydı
   son başarılı snapshot/alarmları bozmaz.
5. Eski WAN DOWN gözlemi STALE olduğundan DOWN alarmı olmaz; IPsec UNKNOWN'dır.
   Kısmi commit hatası replica/projection/audit'i birlikte geri alır.

Geç delta, eski cursor/sequence ve sıra dışı zamanlar kontrollü reddedilir. Retry
gecikmesi mevcut recovery.retry_delay ile 1,2,4,8,16,32,60,... saniyedir; gerçek sleep,
polling veya otomatik tekrar yoktur. Bir routerın hata kaydı diğer state'i etkilemez.

## Salt okunur API ve ekran

GET /api/v1/system/simulator yalnız tam kapsamlı ADMIN'e açıktır. Alt servis owner
router can_view_reports kapsamını satır ve toplam/sayfalama öncesi filtreler; owner
izni olmayan kullanıcıya dosya metadata'sı bile okunmaz. VIEWER mutasyonları motor
sınırında da reddedilir. HTTP üzerinden ingest/fault/ACK/start endpoint'i yoktur.

Rapor yoksa DISABLED, son sync UNKNOWN; bozuk/aşırı büyük/symlink rapor UNKNOWN'dır.
RECORDED yalnız geçmiş koşum raporu demektir: running=false, enabled=false,
external_connections=false ve automatic_polling=false kalır. Sanal kaynak başına
source status, WAN/IPsec, son başarılı sync, cursor, işlenen/atlanan sayısı, izole audit,
hata/retry zamanı ve abone/oturum/alarm detayı gösterilir. Sayfa en fazla 5 sanal router;
alt record listeleri de şema sınırlarıyla bounded'dır. Kimlik/sır/bağlantı değeri alanı
yoktur; hatalar yalnız TIMEOUT/ERROR enum'u veya sabit sanitizasyon mesajıdır.

## Kabul ve sınırlar

`./browser-accept-demo.sh --simulator-acceptance` mevcut ManagedAPI/UI yaşam döngüsü
ve read-only DB geçidini kullanır. Sonra açık --run yalnız yeni izole dosya koşumu
hazırlar; browser Aşama 18 ekranını salt okunur doğrular. Mevcut kullanıcı/ayar/
tercih ve eski abone/audit baseline eşitliği korunur; önceki kabul aşamaları çalışmaz.
320/390/1440px, sayfalama, reload, yeni oturumlar, fault isolation ve yazma isteği
olmaması kontrol edilir. Gerçek browser çalışmazsa PASS değildir.

Motor/ledger süreç içidir; restart sonrası devam eden kaynak ingest'i, çok süreçli
CAS ve PostgreSQL transaction garantisi bu aşamada uygulanmış değildir. Kalıcı
entegrasyon için ayrı test hedefi, secret resolver, TLS/client timeout, yetki/audit ve
transaction sınırlarıyla açık onay gerekir. V1 geçişi başlatılmaz.
