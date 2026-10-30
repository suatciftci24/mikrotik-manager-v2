"""Explicit local-owner TTY setup. No password arguments, environment inputs or web route."""
import getpass
import hmac
import sys
import warnings

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.services.demo_subscriptions import DemoStorageUnavailable
from app.services.first_admin import FirstAdminIdentity, FirstAdminInput, FirstAdminStore, SetupBlocked, local_owner, require


FIELD_POLICIES = {
    'username': ('Giriş adı', '3–64 karakter; yalnız harf, rakam, _, . ve - kullanın.'),
    'name': ('Ad soyad', '1–120 karakter içeren bir ad girin.'),
    'email': ('E-posta', 'En çok 180 karakter içeren geçerli bir e-posta adresi girin.'),
    'password': ('Parola', '14–128 karakter kullanın; yalnız boşluk, satır sonu ve NUL kabul edilmez.'),
}
SAFE_RULES = {
    'public_text_control': 'Kontrol karakteri kullanmayın.',
    'public_text_whitespace': 'Alan başındaki ve sonundaki boşlukları kaldırın.',
    'reserved_demo_identity': 'Demo kimliği yerine ayrı bir hesap bilgisi kullanın.',
    'password_too_short': 'En az 14 karakter kullanın.',
    'password_too_long': 'En çok 128 karakter / 1024 UTF-8 bayt kullanın.',
    'password_blank': 'Yalnız boşluklardan oluşan parola kullanmayın.',
    'password_control': 'Satır sonu veya NUL kullanmayın.',
    'password_encoding': 'Geçerli UTF-8 karakterler kullanın.',
}


def validation_message(failure):
    """Allowlisted field/rule only. Never interpolate inputs, ctx, raw messages or unknown field names."""
    details = []
    for issue in failure.errors(include_input=False, include_context=False, include_url=False):
        location = issue.get('loc', ())
        field = location[0] if location else None
        if field not in FIELD_POLICIES:
            detail = 'Kurulum alanları: beklenmeyen veya eksik alan; yalnız terminal istemlerini kullanın.'
        else:
            label, policy = FIELD_POLICIES[field]
            detail = label + ': ' + SAFE_RULES.get(issue.get('type'), policy)
        if detail not in details:
            details.append(detail)
    return 'ACCOUNT_INPUT_INVALID; ' + ' '.join(details or ['Kurulum alanları doğrulanamadı.'])


def require_tty():
    require(all(stream.isatty() for stream in (sys.stdin, sys.stdout, sys.stderr)), 'REAL_TTY_REQUIRED')


def collect_input():
    public = FirstAdminIdentity(username=input('Yeni V2 ADMIN giriş adı: '),
                                name=input('Ad soyad: '), email=input('E-posta: '))
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        password = getpass.getpass('Yeni parola (14–128 karakter, gizli): ')
        payload = FirstAdminInput(**public.model_dump(), password=password)
        repeated = getpass.getpass('Parola tekrar (gizli): ')
    try:
        repeated_bytes = repeated.encode('utf-8')
    except UnicodeError:
        raise SetupBlocked('PASSWORD_CONFIRMATION_INVALID; parola tekrarında geçerli UTF-8 karakterler kullanın; kayıt oluşturulmadı.') from None
    require(hmac.compare_digest(password.encode('utf-8'), repeated_bytes),
            'PASSWORD_CONFIRMATION_MISMATCH; parola tekrarı eşleşmiyor; kayıt oluşturulmadı.')
    return payload


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    # Do not echo unknown args: an operator may accidentally supply a secret.
    if argv not in (['--create'], ['--status']):
        print('BLOCKED: USE_FIRST_ADMIN_SH_WITHOUT_PASSWORD_ARGUMENTS', file=sys.stderr)
        return 1
    engine = None
    try:
        uid = local_owner()
        if argv == ['--create']:
            require_tty()  # Stop before DB IO/prompts if input/output is redirected.
        from app.core.database import engine
        store = FirstAdminStore(engine)
        state = store.status()
        if argv == ['--status']:
            print('FIRST_ADMIN_SETUP_CLOSED' if state.closed else 'FIRST_ADMIN_SETUP_NOT_COMPLETED')
            return 0
        require(not state.closed, 'FIRST_ADMIN_SETUP_CLOSED')
        payload = collect_input()
        print('Bu işlem ayrı LOCAL ADMIN oluşturur ve demo girişlerini kalıcı kapatır. Pilot kapısını açmaz.')
        require(input('Devam etmek için OLUSTUR yazın: ') == 'OLUSTUR', 'SETUP_CANCELLED')
        user = store.create(payload, uid)
        print('FIRST_ADMIN_CREATED_SETUP_CLOSED')
        print('V2 operatör ID: ' + user['id'])
        return 0
    except SetupBlocked as failure:
        print('BLOCKED: ' + str(failure), file=sys.stderr)
    except (DemoStorageUnavailable, SQLAlchemyError):
        print('BLOCKED: V2_POSTGRESQL_OR_IDENTITY_STATE_UNAVAILABLE; veri veya hesap sıfırlanmadı.', file=sys.stderr)
    except ValidationError as failure:
        print('BLOCKED: ' + validation_message(failure), file=sys.stderr)
    except getpass.GetPassWarning:
        print('BLOCKED: HIDDEN_TTY_REQUIRED; parola gizli okunamadı, düz metin girişine geçilmedi.', file=sys.stderr)
    except (OSError, ValueError, RuntimeError, EOFError, KeyboardInterrupt):
        print('BLOCKED: LOCAL_SETUP_NOT_COMPLETED; gizli TTY veya yerel V2 ön koşulları sağlanamadı.', file=sys.stderr)
    finally:
        if engine is not None:
            engine.dispose()
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
