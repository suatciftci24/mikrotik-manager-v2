"""Small V2-only settings surface; importing it performs no IO."""
from dataclasses import dataclass
import os
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Settings:
    app_name: str = 'MikroTik Manager V2'
    environment: str = 'local-demo'
    database_url: str = os.environ.get(
        'V2_DATABASE_URL',
        'postgresql+psycopg://v2_local:v2_local@127.0.0.1:55432/mikrotik_manager_v2',
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
