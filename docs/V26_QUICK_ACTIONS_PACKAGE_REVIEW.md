# QuickActions seçici paket incelemesi — 2026-11-07

Sonuç: yerel inceleme PASS, dağıtıma hazır paket BLOCKED.
Kaynak: main-guncel / 07b13b13cf6c4b1b3f3dd36e0665749290880fed.

## Korunan ofis değişiklikleri

stash@{0}: 66eda91d7033db67d35ce40d6662f432585bc694.
Yalnız docs/PROGRESS.md içinde 88 ek satır; index değişikliği ve untracked
stash dosyası yok. Salt okunur incelendi; apply/pop/drop yapılmadı.
Başlangıç çalışma ağacı temizdi. İnceleme sonunda stash kimliği aynı.

## Eksik girdiler ve hazırlık malzemesi

Önceki kabulün kaydettiği .local/v26-legacy-review,
.local/v26-legacy-actions, .local/v26-legacy-update-final ve
v26-vds-reference bu ofis kopyasında bulunmuyor. Kaynak commit'i VDS'nin
mevcut config/public/dist içeriklerinin kanıtı değildir. Tam yerel frontend
build'i veya Git'ten üretilen varsayımsal eski dist uyumluluk kanıtı sayılamaz.
Bu yüzden deploy manifesti veya dağıtıma hazır dist üretilmedi.

Git dışı hazırlık arşivi:
.local/v26-quickactions-07b13b1-preparation-NOT-DEPLOYABLE.tar.gz
SHA256: 23c931dee172e56c31563042c3b9f52898595165e6a6033f27c8f2b6b4cf2230

Arşiv yalnız QuickActions.tsx, tek kaynak dosyalık patch, mevcut update.py,
aracın işletim belgesi, hash/kontrol kaydı ve NOT_DEPLOYABLE uyarısını içerir.
Bu arşiv update.py bundle'ı değildir ve VDS'ye uygulanmamalıdır.

## Tek güvenli yöntem

Mevcut deploy/v26-frontend/update.py dışında yayın yöntemi kullanılmaz:

1. Önce önceki test edilmiş v26-legacy-update-final paketini bulunduğu
   bilgisayardan kayıpsız aktarın. Yoksa tam eski kaynak/config/public/dist
   baseline'ı ve test edilmiş adayı alın; yeni isimde `pack` üretin. Yalnız
   QuickActions farkı, payload'ın 07b13b1 ile eşitliği, manifest/dist SHA'ları
   doğrulanmadan sonraki aşamaya geçilmez. Önceki dosyalar ezilmez.
2. Ayrı yetkili VDS adımında salt okunur `check`: sabit V2.6 frontend hedefinin
   bütün source/config/public ve mevcut dist hash'leri baseline ile eşleşmeli.
   Driftte durulur. Bu görevde VDS kontrolü yapılmadı.
3. Ancak yeni açık yayın onayından sonra `apply`: yeni private yedek, eski
   kaynak ve tam dist için hash doğrulaması, hedef filesystem üzerinde staging,
   flock ve renameat2 atomik dist exchange. Başka yayın aracı eşzamanlı çalışmaz.
   Kaynak/dist tek transaction değildir; hata otomatik geri dönüşle ele alınır,
   süreç kesintisi için kalıcı yedek korunur. Servis restartı yok.
4. `verify` ile tam yerel hash kontrolü; doğrulanmış mevcut loopback statik
   listener'da aynı araçla yalnız index/JS/CSS GET kontrolü; mevcut oturumda
   üç pencere/açıklama salt okunur kontrol edilir. Gerçek abone yazımı yok.
   HTTP verify yalnız index'in doğrudan referanslarını karşılaştırır; lazy
   chunk sunumu ayrıca ilgili görünüm açılarak doğrulanmalıdır.
5. Gerekirse ayrıca yetkili `rollback`, yedek/receipt hash'lerini ve hedefin
   izinli before/after durumunu kontrol ederek önceki kaynak/dist'i geri alır;
   sonradan oluşan drift ezilmez. Sonuç tekrar doğrulanır. Yedek silinmez.

Komut sözleşmesi ve sabit hedef: deploy/v26-frontend/README.md.
Manifest yalnız hash bütünlüğü sağlar; güvenilen aktarım ve paket SHA kontrolü
zorunludur, kriptografik imza olduğu varsayılmaz.

## Bu görevdeki hedefli kontroller

PASS: 07b13b1 ile kaynak byte eşitliği; tek dosyalık patch; geçici dizinde
patch öncesi/sonrası byte doğrulaması; update.py AST syntax kontrolü;
oluşturulan arşiv üyelerinin byte eşitliği; stash kimliğinin korunması.
Önceki 16/15 frontend, 9 backend, 9 updater ve build PASS tekrar edilmedi.
VDS uyumluluğu/yayın/HTTP/rollback canlı doğrulaması için PASS iddiası yok.
VDS/SSH/V1/V2.5/backend/DB/router/RADIUS/IPsec/deploy/restart işlemi yok.

Sonraki tek işlem: önceki test edilmiş v26-legacy-update-final paketini bu
ofis reposunun .local dizinine mevcut dosyaları ezmeden güvenli aktarmak.
