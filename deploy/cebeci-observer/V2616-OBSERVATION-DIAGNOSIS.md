# CEBECI_TOWERS V2.6.16 kabul tanısı

Kullanıcı V2.6.15 bağımsız gözlemcide 123 hesabı, V2.6.16 denemesinde
`TIMEOUT_OBSERVATION_DEVICE_IDENTITY` ve V2.6.13 geri dönüşünden sonra
HTTPS/API sağlığını doğruladı. V2.6.16 ürün pini
`433e2ba99a7f4a24ba904b14db98b57f30709f9e`, kurulum kaynağı
`d8ac82cf57f01f7ffabf4b9609d1bb80baaa478d`.

## Kod karşılaştırması

| Katman | V2.6.15 bağımsız | V2.6.16 systemd |
| --- | --- | --- |
| Ağ | Öndeki süreç host ağını kullanır. | Birim host ağını kullanır. Soket ailesi AF_INET ile sınırlıdır ve birim gelen/giden paketleri cihaz adresine göre filtreler. |
| Kaynak ve TLS | `10.250.0.1` adresine bind, `10.250.0.19:8729` hedefi, CA/TLS 1.2+, IP SAN, leaf pin, ardından login. | Aynı bağlama, doğrulama, giriş ve salt okunur toplayıcı kodu. CA ve parola yeni özel çalışma alanından okunur. |
| Snapshot | Özel dizin 0700, çıktı 0600. | `/run` dizini 0750, çıktı 0640, gözlemci UID ve okuyucu grup. Atomik değiştirme korunur. Onay bitişi çıktıya eklenir, WAN sorgulanmaz. Birim durunca geçici dizin kaldırılır. |
| Okuyucu | Yerel dosya. | API ayrı kullanıcı ve ek grup ile sabit dosyayı okur. Sahip/grup/mod, bağlantı sayısı, DTO, onay süresi ve güncellik doğrulanır. Okunamayan veya geçersiz dosya 503, eksik veya süresi dolmuş çıktı boş liste üretir. |
| Kimlik | Cihazın adı, modeli ve sürümü PPP tablolarından önce doğrulanır. | Aynı cihaz doğrulaması. API yalnız ONLINE satırda kimlik üçlüsünü zorunlu tutar. Kurulum kabulü ise ONLINE kontrolünden önce kimlik üçlüsünü değerlendirir. |

Systemd adres filtresi giden pakette hedefi, gelen pakette kaynağı ölçer.
Bu yüzden birim allowlist'inde yerel bind adresi yerine cihaz adresi vardır.
Bu statik karşılaştırma, VDS'de cgroup filtresinin veya IPsec yolunun o anda
çalıştığını kanıtlamaz.
[systemd IP paket filtresi](https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html#IPAddressAllow=ADDRESS[/PREFIXLENGTH]%E2%80%A6)

## Kabul kodunun gösterdiği durum

`wait_for` son başarısız kontrolün kodunu `TIMEOUT_` ile bildirir. Son
deneme kimlik kapısına gelmeden önce HTTP 200, kaynak sözleşmesi ve tam bir
satır kontrolünü geçti. Bu nedenle izin reddiyle dönen 503 veya eksik
snapshot'tan dönen boş liste son hatayı açıklamıyor.

İlk başarısız cihaz çevrimi de sabit router ID ile tek satır yayımlar.
Önceki başarı yoksa bu satırın kimlik, model ve sürüm alanları boştur.
Ağ, TLS, login, protokol veya veri doğrulaması hataları bu görünümü
üretebilir. Dolayısıyla kabul kodundan router adının değiştiği çıkarılamaz.
`sample_device` taşıyıcı hatasını DTO kategorisine indirger ve journal'a
yazmaz. Journal'da varsa birim başlatma/izin hataları, onay ve yerel I/O
kodları ile `INVALID_TEXT` konumu ayrıştırılabilir. Yalnız başlama ve
durdurma görülürse kayıtlardan kesin kök neden çıkarmak mümkün değildir.

## VDS terminalinde salt okunur tanı

Aşağıdaki tek komut, rollback ile birim dosyası silinmiş olsa da önceki
birim kayıtlarını arar. Çıktıya yalnız zaman ve tanı kodları geçer.
Router, API veya servis çağrısı yapmaz.

```bash
(
  set -o pipefail
  sudo journalctl --no-pager -q -u mikrotik-v2-cebeci-observer.service -n 200 -o short-iso |
  awk '
    function emit(code) { print $1, code; found=1 }
    /^[0-9][0-9][0-9][0-9]-/ {
      if (match($0,/V2614_CEBECI_OBSERVER_(APPROVAL_OK|NOT_AUTHORIZED|MATERIAL_REJECTED|CREDENTIAL_REJECTED|SCOPE_REJECTED|LOCAL_IO_REJECTED)/)) emit(substr($0,RSTART,RLENGTH))
      if (match($0,/INVALID_TEXT:\/(system\/(identity|resource)|interface|ppp\/(secret|active))\/print:(name|board-name|version|cpu-load|total-memory|free-memory|uptime|running|disabled|rx-byte|tx-byte|profile|service|comment|address)/)) emit(substr($0,RSTART,RLENGTH))
      if ($0 ~ /systemd\[1\]:/) {
        if (match($0,/status=[0-9]+\/[A-Z_]+/)) emit(substr($0,RSTART,RLENGTH))
        if ($0 ~ /BPF|IP firewall/) emit("SYSTEMD_IP_FILTER_NOTICE")
        if ($0 ~ /: (Starting|Started) /) emit("SYSTEMD_START")
        if ($0 ~ /: (Stopping|Stopped) |Deactivated successfully/) emit("SYSTEMD_STOP")
        if ($0 ~ /Failed with result|Failed to start/) emit("SYSTEMD_UNIT_FAILURE")
      }
    }
    END { if (!found) print "JOURNAL_NO_DIAGNOSTIC_MATCH" }
  '
)
```

Başlangıç ve rollback saatine karşılık gelen satırları değerlendirin.
`APPROVAL_OK` sadece yerel onayı gösterir. `SYSTEMD_IP_FILTER_NOTICE`
birim filtresiyle ilgili mesaj bulunduğunu gösterir ve trafik reddini
tek başına kanıtlamaz.
