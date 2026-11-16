# V2.6 merkezi API / ev-ofis kullanımı — 2026-11-16

Başlangıç main-guncel/3ac1f2a, temiz çalışma ağacı, üç stash. Son PPPoE,
paket, abone oluşturma ve Dashboard kabul kayıtları esas alındı.

Ev ve ofis ortak kullanımında mevcut `https://v26.mikmanager.com.tr/`
origin'i tarayıcıda açılır. Ofis WSL repo kökünde `./dev.sh --central`
yalnız bu adresi ve mevcut hesapla giriş bilgisini gösterir; tarayıcı,
API, Vite veya PostgreSQL başlatmaz. Adres bu oturumda ağ üzerinden
teyit edilemedi; canlı kullanılabilirlik ve VDS sürüm eşitliği iddia edilmez.

Frontend `/api/v1` ve `credentials: include` kullanır; merkezi panelde
aynı origin üzerindeki API ve mevcut oturum geçerlidir. Yerel Vite proxy
loopback API'ye gider; yerel geliştirme ortak VDS veri oturumu değildir.
Merkezi oturum cookie'sini localhost'a taşımayın; DB URL'si veya yönetici
parolasını Git'e eklemeyin. Yeni hesap, parola sıfırlama veya veri aktarımı yok.
Git eşitliği DB eşitliği değildir; merkezi paneldeki sentetik workspace de
canlı RouterOS/RADIUS entegrasyon kanıtı değildir.

Tespit edilen yerel kalıntılar (yalnız dizin adı envanteri):
`.local/postgres-v2-demo`, `.local/postgres-v2-socket`, `.local/aaa-office-fixture`,
`.local/cebeci-pilot`, `.local/acceptance`, `.local/runtime` ve eski kabul/yayın
hazırlıkları. Bunlar abone/workspace satır sayısını veya çalışan DB kimliğini
kanıtlamaz. İçerikler ve mevcut yönetici hesabı korunur. Uygulamada LEGACY demo,
kalıcı subscriber/router workspace ve AAA fixture kaynakları hâlâ ayrıdır.
VDS'deki kalan demo workspace satırları bu oturumda doğrulanamadı; silinmedi.

Düzeltmeler: ortak panel erişimi yerel bootstrap'tan önce ayrıldı; geçersiz
başlatma argümanları bağımlılık/DB işlemlerinden önce reddedilir. Eksik abone
ve router API endpointleri 404 durumunu korur ve bağlı API adresi/sürümünün
kontrolünü ister; kullanıcıya koşulsuz servis yenileme yönlendirmesi vermez.

Hedefli doğrulama sonuçları PROGRESS.md görev kaydında. Üretim HTTP/PG veya
görsel kabul yok; deploy/restart/migration, veri silme veya cihaz işlemi yok.
