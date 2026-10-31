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
