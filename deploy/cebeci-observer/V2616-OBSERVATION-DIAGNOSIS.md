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

## İki çalışma ortamını karşılaştırma

Kullanıcının journal çıktısında onay, başlama ve kapanma görüldü.
Ayrıştırılmış taşıyıcı hatası mevcut değildi. Bu durumda aynı VDS'de, aynı
kimlik bilgileriyle birer yeni salt okunur teşhis örneği alınabilir.

[Teşhis betiğini](diagnose-observer.py) root'a ait
`/root/diagnose-observer.py` yoluna aktarın. **VDS terminalinde** bir kez
çalıştırın:

```bash
sudo /usr/bin/python3 -I -B /root/diagnose-observer.py --repo /home/mikadmin/v2616-diagnostic-source.git --material /MUTLAK/V2615/CHECKOUT/.local/cebeci-pilot/v2614-observer --venv /srv/mikrotik-v26-next/.venv
```

`--material` başarılı V2.6.15 gözlemcisinin CA/parola dizini,
`--venv` VDS'de doğrulanmış mevcut Python ortamıdır. Yer tutucu
malzeme yolunu VDS'deki gerçek mutlak yolla değiştirin. `--repo` iki sabit Git nesnesine yerelde erişebilmelidir.
Betiğin bağımlılık indirme veya Git fetch adımı yoktur.

İlk ölçüm V2.6.15 kaynağını doğrudan, ikincisi V2.6.16 kaynağını
geçici systemd biriminde çalıştırır. Karşılaştırma iki tarafta da önceki
gözlemcinin ayrıcalıksız hesabını ve aynı CA/parolayı kullanır. Böylece
ağ izolasyonu karşılaştırılır. Önceki yönetilen Linux hesabının UID/GID'si
ve canlı API okuyucusu bu denemenin kapsamı dışında kalır. Geçici birim
sürümdeki güvenlik özelliklerini taşır ve kendi runtime dizinini kullanır.
Eski izin dosyası korunur, deneme 10 dakikalık ayrı izin kopyası kullanır.

Sabit çıktılar `SOURCE_BIND`, `TCP`, `SOURCE_PEER`, `TLS`, `LOGIN`,
`IDENTITY` ve `SNAPSHOT` adımlarını ayırır. Kimlikte ad, model veya
sürüm sapması yalnız hata koduyla verilir. Snapshot satırlarının
içeriği, parola, sertifika ve cihaz yanıtı basılmaz. Kontrol sonrasında
yalnız geçici birim durdurulur ve geçici dosyalar kaldırılır.

### Python çalışma zamanı tanısı

Eski betik aynı `IMPORT_OR_EXEC_FAILURE` koduyla farklı import ve dosya
hatalarını birleştiriyordu. Bu çıktı tek başına geçmişteki hatayı belirlemez.
Güncel betik önceki `/run` alanının güncel `noexec` durumunu bildirir.
Kod ve kopya paketler geçici `/opt` alanına hazırlanır. Yönetilen snapshot
geçici `/run` çalışma dizininde kalır. Kaynak depo ve özgün venv yalnız
hazırlık sırasında okunur. Worker süreçleri `ProtectHome` altında
`/home` içindeki Git deposuna erişmez.

İki worker aynı biçimde `-I -S -B` ile başlatılır. Python standart
kütüphanesi, sabit kaynak ve kopyalanan paketler kullanılır. Çalışma
dizini, kaynak/paket erişimi ve modüllerin beklenen dizinlerden yüklenmesi
kontrol edilir. `IMPORT=PYDANTIC_CORE:NATIVE_MAP_DENIED`,
`IMPORT=FASTAPI:MODULE_MISSING:STARLETTE` gibi kodlar import kontrolünü
ve hata sınıfını ayırır. Ham hata, modül yolu veya kimlik bilgisi
yazılmaz. Makineye özel izin ve montaj ayarları değiştirilmez.

## VDS ağ bulgusu ve karar

Bağımsız akış 123/123, yönetilen akış kaynak bind PASS ve TCP timeout.
Önceki `/run` alanı NOEXEC. Bu ikinci olgu önceki import fazına ait.
Yeni ölçümde her iki runtime geçti ve yönetilen fark TCP aşamasında
görüldü. TLS, login, snapshot ve API tüketimi bu ölçümde yönetilen
bağlantı için erişilen aşamalar arasında değildi.

Systemd'nin adres kuralı port seçmez. Giden paketin hedefi ve gelen
paketin kaynağı eşleşir. Bu nedenle `10.250.0.1` bind adresini
allowlist'e eklemek bu sonuçtan türetilemez. Linux IPv4 bitiş yolunda
cgroup BPF egress kontrolü vardır. XFRM çıkışı da son dönüşümden sonra
bu IPv4 çıkış yoluna dönebilir. Dış IPsec başlığının gözlemciye ait filtre
tarafından değerlendirildiği, bu VDS'de kullanılmakta olan tünel yolu ve
paket düşüşü ölçülmeden doğrulanamaz.

Yetkili VDS terminalinde önce salt okunur yol ve devralınan politika
bilgisi alınabilir:

```bash
sudo systemctl show -p IPAddressAllow -p IPAddressDeny -p IPIngressFilterPath -p IPEgressFilterPath -p BPFProgram -- -.slice system.slice
ip -4 route get 10.250.0.19 from 10.250.0.1 ipproto tcp dport 8729
```

Etkin BPF kancaları için yönetilen geçici birim çalışırken
`systemctl show -p ControlGroup --value <geçici-birim>` ile gerçek cgroup
belirlenir ve `bpftool cgroup show /sys/fs/cgroup<ControlGroup> effective`
okunur. Ata kancalarının listesi, bir paketin düştüğünün kanıtı değildir.
Sonraki gerekli kanıt yalnız yönetilen bağlantının SYN/SYN-ACK yolu ve
varsa cgroup BPF veya XFRM düşüş nedeni. IPsec anahtarı içerebilen
`ip xfrm state` çıktısı paylaşılmaz.

Düzeltme kararı bu kanıta bağlıdır. İç bağlantı sınırı TCP
`10.250.0.1 → 10.250.0.19:8729` olarak kalmalıdır. Dış tünel uç noktasını
genel allowlist'e eklemek veya devralınan filtreyi sökmek bu sınırı
tek başına sağlamaz. Ürün ve birim değişikliği beklemede.

- [systemd cgroup kaynak ve adres filtresi](https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html)
- [Linux IPv4 egress kancası](https://github.com/torvalds/linux/blob/master/net/ipv4/ip_output.c)
- [Linux XFRM çıkış yolu](https://github.com/torvalds/linux/blob/master/net/xfrm/xfrm_output.c)
