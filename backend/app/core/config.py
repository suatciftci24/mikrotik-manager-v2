"""Small V2-only settings surface; importing it performs no IO."""
from dataclasses import dataclass
import os
from urllib.parse import urlsplit


DEFAULT_DATABASE_URL = 'postgresql+psycopg://v2_local:v2_local@127.0.0.1:55432/mikrotik_manager_v2'


def local_demo_blocker(values=None):
    """Local tooling policy independent of the central application's runtime profile."""
    values = os.environ if values is None else values
    if (values.get('V2_DEPLOYMENT_PROFILE', 'local-demo') != 'local-demo'
            or values.get('V2_ENVIRONMENT', 'local-demo') != 'local-demo'):
        return 'LOCAL_DEMO_PROFILE_REQUIRED'
    if (any(values.get(key, 'false') != 'false' for key in (
            'V2_ROUTER_ONBOARDING_ENABLED', 'V2_CEBECI_API_SSL_ENABLED', 'V2_V26_CEBECI_READ_ENABLED'))
            or any(values.get(key) for key in (
                'V2_ROUTER_ONBOARDING_OPERATOR_IDS', 'V2_V26_CEBECI_OPERATOR_ID',
                'V2_V26_CEBECI_OPERATOR_REVISION'))):
        return 'LOCAL_DEMO_DEVICE_ACCESS_REJECTED'
    if any(values.get(key) for key in ('PGHOSTADDR', 'PGSERVICE', 'PGOPTIONS')):
        return 'LOCAL_DEMO_DATABASE_OVERRIDE_REJECTED'
    try:
        url = urlsplit(values.get('V2_DATABASE_URL') or DEFAULT_DATABASE_URL)
        if ((url.scheme, url.hostname, url.port, url.path, url.username) ==
                ('postgresql+psycopg', '127.0.0.1', 55432, '/mikrotik_manager_v2', 'v2_local')
                and not url.query and not url.fragment):
            return None
    except ValueError:
        pass
    return 'LOCAL_DEMO_DATABASE_TARGET_REJECTED'


@dataclass(frozen=True)
class Settings:
    app_name: str = 'MikroTik Manager V2'
    environment: str = os.environ.get('V2_ENVIRONMENT', 'local-demo')
    database_url: str = os.environ.get(
        'V2_DATABASE_URL',
        DEFAULT_DATABASE_URL,
    )
    session_secure: bool = os.environ.get('V2_SESSION_SECURE', 'false').lower() == 'true'

    def validate(self) -> None:
        parsed = urlsplit(self.database_url)
        if parsed.scheme not in {'postgresql', 'postgresql+psycopg', 'postgresql+psycopg2'}:
            raise RuntimeError('V2_DATABASE_URL must use PostgreSQL')
        if parsed.hostname not in {'127.0.0.1', 'localhost', '::1'}:
            raise RuntimeError('V2_DATABASE_URL must target loopback; external and V1 databases are forbidden')
        if not parsed.path or parsed.path == '/':
            raise RuntimeError('V2_DATABASE_URL must name a V2 database')
        if parsed.port == 5432:
            raise RuntimeError('V2_DATABASE_URL must use a separate local V2 port')


settings = Settings()

if __name__ == '__main__':
    import sys
    if blocker := local_demo_blocker():
        print(f'TERMINAL_TARGET_BLOCKED: {blocker}', file=sys.stderr)
        sys.exit(1)
