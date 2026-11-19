# Değişiklik geçmişi

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
