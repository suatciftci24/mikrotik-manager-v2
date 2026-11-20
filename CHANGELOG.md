# Değişiklik geçmişi

## [2.6.15] - 2026-11-20

- RouterOS gözlemlerinde alan bazlı metin işleme, güvenli abone eşleştirme ve tek WAN sorgusu.

## [2.6.14] - 2026-11-20

- RouterOS salt okunur gözlem aktarımı ve ayrı router, PPPoE ve Dashboard görünümleri.

## [2.6.13] - 2026-11-20

- Sentetik router kaydında envanter bilgileri, arama, yönetim ve simüle bağlantı filtreleri.
- Router detayında bağlı hesap sayıları ve paket dağılımı. Abone düzenlemede önizlemeli router değişikliği.
- Bağlı aboneli router için sunucu tarafında silme engeli. Audit önceki/yeni değerleri için 013 şema değişikliği.

## [2.6.12] - 2026-11-20

- Paket kataloğu araması, durum filtresi, para birimi, bağlı abone sayısı, korumalı silme ve abone düzenleme entegrasyonu.

## [2.6.11] - 2026-11-20

- Abone listesi ve işlem geçmişinde sunucu tarafı sayfalama, sıralama ve güvenli sayfa seçimi.

## [2.6.10] - 2026-11-19

- Geri alma kaynak grubu doğrulaması ve güvenlik kabulü.

## [2.6.9] - 2026-11-19

- Geri alma durum filtreleri, kaynak audit takibi ve eksiksiz grup doğrulaması.

## [2.6.8] - 2026-11-19

- İzole sentetik abonelikler için atomik ve denetlenebilir tekli/toplu geri alma.

## [2.6.7] - 2026-11-19

- Abone geçmişinde grup ayrıntıları, salt okunur geri alma önizlemesi ve üretim sürüm dosyası.

## [2.6.6] - 2026-11-19

- Abone işlemlerinde sabit önizleme, atlama açıklamaları ve tutarlı işlem geçmişi.

## [2.6.5] - 2026-11-19

- Toplu abone işlemlerinde aynı UUID'lerle güvenli tekrar ve grup sonuçlarının
  tek transaction’da kaydı. Önceki grup kimlikleri ve audit kayıtları okunabilir.
- Önizlemeden sonra revizyonu değişen aboneler için çakışma sonucu gösterilir.
  Hesabı hedef durumda ve revizyonu güncel olan aboneler atlanır.

## [2.6.4] - 2026-11-18

- PPPoE Abone Merkezi'nde bilgi düzenleme ile hesap, paket ve yenileme işlemlerini ayır.

## [2.6.3] - 2026-11-18

- Legacy PPPoE hızlı işlem penceresini geçersiz yetki veya kayıt doğrulandığında kapat.

## [2.6.2] - 2026-11-17

- PPPoE Abone Merkezi: birleşik kullanıcı/alan araması, kaynak filtreleri ve Türkiye gününe göre tekil bitiş grupları; liste/detay ve mobil görünüm iyileştirmeleri.

## [2.6.1] - 2026-11-17

- Dashboard, Router ve Abone Merkezi boşlukları, metin ve araç çubukları iyileştirildi; yinelenen Dashboard filtre bağlantıları kaldırıldı.

## [2.6.0] - 2026-11-17

- Kalıcı SemVer kaydı başlatıldı; frontend paketleri, arayüz alt bilgisi,
  FastAPI uygulama sürümü ve `/api/ready` app_version aynı kaynaktan beslenir.
- Yerel sürüm artırma aracı ve Git etiketi prosedürü eklendi.
- Bu numara yeni yerel sürüm atamasıdır; geçmiş cleanup veya canlı panelin
  doğrulanmış sürümü değildir. Önceki kodda paket/FastAPI sürümü 0.1.0 idi.
