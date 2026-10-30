"""Explicit local-owner TTY setup. No password arguments, environment inputs or web route."""
import getpass
import hmac
import sys
import warnings

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.services.demo_subscriptions import DemoStorageUnavailable
from app.services.first_admin import FirstAdminInput, FirstAdminStore, SetupBlocked, local_owner, require


def require_tty():
    require(all(stream.isatty() for stream in (sys.stdin, sys.stdout, sys.stderr)), 'REAL_TTY_REQUIRED')


def collect_input():
    username = input('Yeni V2 ADMIN giriş adı: ')
    name = input('Ad soyad: ')
    email = input('E-posta: ')
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        password = getpass.getpass('Yeni parola (14–128 karakter, gizli): ')
        repeated = getpass.getpass('Parola tekrar (gizli): ')
    require(hmac.compare_digest(password.encode('utf-8'), repeated.encode('utf-8')), 'PASSWORD_CONFIRMATION_MISMATCH')
    return FirstAdminInput(username=username, name=name, email=email, password=password)


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
    except ValidationError:
        print('BLOCKED: ACCOUNT_INPUT_INVALID; giriş adı, e-posta ve 14–128 karakter parola gerekli.', file=sys.stderr)
    except (OSError, ValueError, RuntimeError, getpass.GetPassWarning, EOFError, KeyboardInterrupt):
        print('BLOCKED: LOCAL_SETUP_NOT_COMPLETED; gizli TTY veya yerel V2 ön koşulları sağlanamadı.', file=sys.stderr)
    finally:
        if engine is not None:
            engine.dispose()
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
