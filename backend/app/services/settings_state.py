"""Public, fixed error codes. No payload, SQL or connection details escape."""
from app.services.demo_subscriptions import DemoStorageUnavailable


class SettingsStateError(DemoStorageUnavailable):
    MESSAGES = {
        'SETTINGS_SCHEMA_MISSING': 'Ayar deposu şeması eksik; açık bakım gerekli.',
        'DEFAULT_SETTINGS_MISSING': 'Varsayılan ayar kaydı eksik; açık onarım gerekli.',
        'SETTINGS_RECORD_INVALID': 'Kayıtlı ayarlar geçersiz; kayıt değiştirilmedi.',
    }

    def __init__(self, code):
        self.code = code if code in self.MESSAGES else 'SETTINGS_RECORD_INVALID'
        super().__init__(self.code)

    @property
    def detail(self):
        return self.MESSAGES[self.code]
