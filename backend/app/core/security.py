"""Local demo session. Phase 1 has no production identity provider or password store."""
import secrets
from fastapi import Cookie, HTTPException, status

_sessions: set[str] = set()
_DEMO_USER = {'id': 'demo-user', 'name': 'Demo Operatör', 'email': 'demo@local.test',
              'role': 'Sistem Yöneticisi', 'is_demo': True}


def login_demo(username: str, password: str) -> str:
    if username != 'demo' or password != 'demo-only':
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Demo bilgileri geçersiz')
    token = secrets.token_urlsafe(32)
    _sessions.add(token)
    return token


def logout_demo(token: str | None) -> None:
    if token:
        _sessions.discard(token)


def current_demo_user(v2_session: str | None = Cookie(default=None)) -> dict:
    if not v2_session or v2_session not in _sessions:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Oturum gerekli')
    return _DEMO_USER.copy()
