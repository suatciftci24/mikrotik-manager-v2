# PPPoE salt okunur gözlem API'si

`GET /api/v1/router-center/{id}/pppoe-observations` mevcut oturum doğrulamasını
ve Router Merkezi'nin kaynak bazlı erişim kurallarını kullanır.

Varsayılan yanıt kayıtlı router için `availability: UNAVAILABLE`, `error: DISABLED`,
`items: []`, `is_demo: false`, `read_only: true` içerir. Demo router için
`error: DEMO_ISOLATED`, `is_demo: true` döner. Endpoint router durumunu değiştirmez.

Başarılı gözlemler `account_id`, zorunlu `source: LOCAL | RADIUS`, nullable
`connected` ve nullable `ip_address` taşır. Oturumun yokluğu offline kanıtı değildir.
Mevcut abone ve ekran yanıtları bu gözlemlerle birleştirilmez.

`disabled_binding` üretimde varsayılan olarak None döndürür. Sentetik entegrasyon
ve ileride ayrı onaylı taşıyıcı için sunucu tarafı dependency enjeksiyonu
`PppoeReadBinding` sağlayabilir; HTTP girdisi hedef, credentials veya authority
seçemez. Binding router ID'si ve yetkili hesap envanteriyle sınırlıdır. Dönen her
hesap ID'si ve LOCAL/RADIUS kaynağı eşleşmelidir; uyuşmazlık bütün sonucu
`AUTHORITY_MISMATCH` ile reddeder. Boş/belirsiz envanter IO öncesinde reddedilir.

Adaptör hata kodları `TIMEOUT`, `INVALID_DATA`, `CONNECTION_FAILED` olarak
aktarılır; ham hata, sır, kısmi sonuç, retry veya demo fallback bulunmaz.
Bu entegrasyon canlı transport veya env ile etkinleştirme yolu kurmaz.

## Router kaynağı ve abone API'si

Router endpoint'i isteğe bağlı `source=LOCAL|RADIUS` seçimini kabul eder.
Seçim otoriteyi değiştirmez; yalnız doğrulanmış sonucu filtreler. Seçim yoksa
iki kaynak da kendi otoritesiyle döner. Önce bütün taşıyıcı sonucu envantere
karşı doğrulanır; filtre dışında kalan bozuk kayıtlar da tüm sonucu kapatır.

`GET /api/v1/subscriber-observations/{router_id}/{account_id}?source=LOCAL|RADIUS`
Abone Yönetimi için aynı salt okunur servisi kullanır. Router Merkezi'nin
kaynak bazlı yetkilendirmesi IO öncesinde uygulanır. Kaynak zorunludur;
hesap ID'si ve kaynak sunucu binding envanterinde eşleşmeden adaptör çağrılmaz.
Yanıtta yalnız seçilen hesabın gözlemi bulunur. Gerçek hesap için demo workspace'e
veya kullanıcı adı eşlemesine başvurulmaz. Mevcut sentetik abone liste/detay
sözleşmeleri korunur; bu endpoint gerçek abone envanteri oluşturmaz.

Yanıtın `selected_source` alanı seçimi açıklar.
`last_successful_observed_at`, başarılı ve bütünüyle doğrulanmış yanıtlardaki
seçili kapsamın en ileri gerçek ölçüm zamanıdır; router'ın tüm hesaplarının
ölçüldüğü anlamına gelmez. Kaynak/hesap kapsamları ayrıdır. HTTP zamanı,
boş sonuç, eksik timestamp veya hata bu zamanı ilerletmez. Eski bir ölçüm
zamanı geriye götürmez. Hata sırasında yalnız bu tarih korunur, oturum satırları
tekrar sunulmaz; hata kodu ve UNAVAILABLE korunur. Tarih UTC'dir, hiç ölçüm
yoksa null'dır. Her satırın mevcut FRESH/STALE/UNKNOWN durumu ve 5 dakika
eşiği korunur.

Bu metadata yalnız enjekte edilen binding ömründe, kilit altında tutulur;
yeniden başlatma/binding yenileme sonrası null olabilir. Kalıcı son-başarı
deposu veya DB migration'ı yoktur. Binding router, hedef ve otorite envanteri
değiştirildiğinde yeniden oluşturulmalıdır.

Timeout doğrudan oluşturulan ayarlarda da 0.1–10 saniye ve sonlu olmalıdır.
Taşıyıcı bağlantı ve okuma için bu toplam deadline'ı uygulamak zorundadır;
senkron adaptör takılmış taşıyıcıyı zorla durdurmaz. Adaptör süreyi aşarak
dönen sonucu TIMEOUT ile reddeder. TimeoutError ve diğer bağlantı hataları
sabit kodlarla maskelenir; retry ve demo fallback yoktur.
Varsayılan dependency hâlâ kapalıdır; canlı taşıyıcı kayıtlı değildir.
