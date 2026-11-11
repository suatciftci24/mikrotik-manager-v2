# LOCAL / RADIUS merkezi görünürlük ve AAA kararları

2026-11-11 · Ofis `office-development` · yalnız mevcut sentetik V2 verileri.

RADIUS Merkezi daha önce hazırlık metniydi. Yeni ekran mevcut GET sözleşmelerini
okur; FreeRADIUS istemcisi, health/probe, sync, seed, scheduler veya migration
eklemez. `/modules` içindeki RADIUS SCAFFOLD durumu canlı entegrasyonun henüz
uygulanmadığını anlatmaya devam eder; yeni ekran entegrasyonun çalıştığı iddiası değildir.

## Mevcut sınırlar

- Legacy: `/api/v1/subscribers`, `current_demo_user` ve `items_for(can_view)`
  üzerinden yetkili router kapsamındaki hesaplar. Kaynak, tür, revizyon ve
  router ID aynı Abone Merkezi yanıtından gelir; ayrı kayıt deposu oluşturulmaz.
- Kalıcı çalışma alanı: mevcut `/api/v1/subscriber-workspace` ADMIN guard'ı;
  istemci de merkezi yönetici yoksa isteği reddeder. Tüm sayfalar okunmadan
  tam toplam yayımlanmaz. İki depo açık seçimlidir; kimlik veya audit birleşmez.
- LOCAL/RADIUS yetkili kaynaktır; PPPoE/Hotspot ayrı erişim türüdür. Bilinmeyen
  kaynak router adına, IP'ye veya türe göre atanmaz. Aktif hesap canlı oturum
  değildir. Paket adı FreeRADIUS profil eşlemesi değildir. Router referansı
  doğrulanmış NAS kimliği değildir. Eski/eksik veri sağlık kanıtı sayılmaz.
- Detay linkleri aynı kaynak ve sınırlı dönüş bağlamını taşır. Gerçek registered
  router hedeflerine geçiş üretilmez. Audit aynı depodaki mevcut Abone Detayı /
  Geçmiş yüzeyindedir; RADIUS accounting bilgisi oluşturulmaz.
- Okuma hatası, eksik/değişen toplam ve mükerrer ID sıfıra dönüştürülmez.
  Başarılı boş kaynak sıfırdır. Arayüz loglarına ham yanıt veya sır yazılmaz.

## Canlı AAA öncesi karar tablosu — uygulanmadı

| Konu | Mevcut yapı | Karar / eksik |
| --- | --- | --- |
| Kimlik ve tek otorite | `SubscriberAccount` LOCAL secret reference / RADIUS identity CHECK; demo ve workspace ayrı ID depoları | Merkezi immutable identity, realm ve username benzersizliği (NAS başına / realm genelinde) belirlenmeli; depolar kendiliğinden birleşmemeli. |
| Profil / paket | Plan FK modeli ve sentetik paket adları | Sürümlü AAA attribute/profil eşlemesi, desteklenen PPPoE/Hotspot politikaları, profil sahibinin kim olduğu belirlenmeli. |
| Abonelik süresi | Kayıtlı bitiş; Türkiye günü UI'da dahil | Gün sonunun UTC karşılığı, Expiration / Session-Timeout anlamı, pause/expire ayrımı ve mevcut oturuma etki kararı gerekiyor. Oturum kapatma bu görünümün kapsamı değil. |
| NAS / router | Yerel router ID, `RadiusIdentity.nas_identifier` protokol alanı | NAS-Identifier/NAS-IP ve RouterOS bağı, kapsam/tenant, adres değişimi, doğrulanmış uç ve secret reference politikası gerekiyor; yönetim IP'si otomatik NAS sayılmaz. |
| Yetki / sır | Ortak router read/write izinleri, ADMIN workspace, secret reference yaklaşımı | Ayrı AAA okuma/yazma yetkileri, tenant/NAS sınırı, minimum servis rolü, güvenli taşıma/topoloji ve merkezi secret yönetimi kararı gerekli. Üretim sırları demo ortamına taşınmaz. |
| Audit / tekrar / belirsizlik | Yerel transaction+audit ve UUID receipt; gerçek AAA adaptörü yalnız Protocol | Panel transaction'ı ile AAA yan etkisi tek DB transaction değildir. İdempotent iş kimliği, belirsiz sonuç uzlaştırma, ileri/geri plan ve gerekirse outbox tasarımı ayrıca incelenmeli; yeni şema burada yok. |
| Sağlık / accounting | Sentetik raporlar; canlı RADIUS okuması yok | Auth/accounting veri kaynakları, observation time/freshness, saklama ve kişisel veri sınırı tanımlanmalı. Sunucu erişilemiyor durumu hesap kapalı veya sıfır oturum değildir. |

Canlı uygulama öncesi hedef, yedek/geri dönüş, sürüm/uyumluluk, ağ ve secret
sınırları somutlaştırılıp ayrı açık onay gerekir. Mevcut `FreeRadiusAdapter`
protokolü yalnız health/create/disable taslağıdır; merkezi read/accounting
sözleşmesi tamamlanmış veya üretimde doğrulanmış değildir. `001` alan modelleri
ile 007/008 sentetik çalışma alanları aynı çalışan AAA şeması sayılmaz.

## Kabul sınırı

Mock GET/pagination ve statik React testleri ile izin/sözleşme kontrolü yapılır;
mevcut PostgreSQL'e test bağlantısı veya yazımı yoktur. Mobil 320/360/393/430 px
min-width/wrap/44px stilleri uygulanır. Gerçek tarayıcı geometrisi ve etkileşim
kabulü **PENDING**; bilinen socket EPERM tekrar denenmez.
