"""Opaque V2 sessions. Account origin and permissions are re-read from isolated PostgreSQL."""
import secrets
import time
from app.services.identity import find_user,verify_password,BOOTSTRAP_HASH,public_user
from fastapi import Depends, Header, Cookie, HTTPException, status

SESSION_TIMEOUT_SECONDS=8*60*60

_sessions: set[str] = set()
_session_users: dict[str,tuple[str,float]] = {}
_DEMO_USER = {'id': 'demo-user', 'name': 'Demo Operatör', 'email': 'demo@local.test',
              'role': 'Sistem Yöneticisi', 'is_demo': True}


def login_demo(username: str, password: str) -> str:
    identity=find_user(username,by_username=True)
    valid=verify_password(password,identity['password_hash'] if identity else BOOTSTRAP_HASH)
    if not identity or not identity['active'] or not valid:
        raise HTTPException(status_code=401,detail='Giriş bilgileri geçersiz')
    token=secrets.token_urlsafe(32)
    _sessions.add(token);_session_users[token]=(identity['id'],time.monotonic())
    return token


def logout_demo(token: str | None) -> None:
    if token:
        _sessions.discard(token)
        _session_users.pop(token,None)


def current_demo_user(v2_session: str | None = Cookie(default=None)) -> dict:
    if not v2_session or v2_session not in _sessions:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Oturum gerekli')
    session=_session_users.get(v2_session)
    if not session or time.monotonic()-session[1]>=SESSION_TIMEOUT_SECONDS:
        logout_demo(v2_session);raise HTTPException(401,'Oturum gerekli')
    identity=find_user(session[0])  # Fresh authoritative permissions on EVERY request.
    if not identity or not identity['active']:
        logout_demo(v2_session);raise HTTPException(401,'Oturum gerekli')
    return public_user(identity)


def current_demo_mutator(user: dict = Depends(current_demo_user),
                         x_v2_demo_action: str | None = Header(default=None)) -> dict:
    if x_v2_demo_action != 'expiry' or not user.get('is_demo') or user.get('role') != 'Sistem Yöneticisi':
        raise HTTPException(status_code=403, detail='Demo değişiklik yetkisi gerekli')
    return user


def current_demo_account_mutator(user: dict = Depends(current_demo_user),
                                 x_v2_demo_action: str | None = Header(default=None)) -> dict:
    if x_v2_demo_action != 'subscriber-management' or not user.get('is_demo') or user.get('role') != 'Sistem Yöneticisi':
        raise HTTPException(status_code=403, detail='Demo abone yönetim yetkisi gerekli')
    return user


def current_alarm_mutator(user: dict = Depends(current_demo_user),
                          x_v2_demo_action: str | None = Header(default=None)) -> dict:
    if x_v2_demo_action != 'alarm-ack' or not user.get('is_demo') or user.get('role') != 'Sistem Yöneticisi':
        raise HTTPException(403, 'Alarm onaylama yetkisi gerekli')
    return user


def current_admin(user:dict=Depends(current_demo_user)):
    if not user.get('is_demo') or (user.get('role_code')!='ADMIN' or user.get('can_manage_users') is not True):raise HTTPException(403,'Yönetici yetkisi gerekli')
    return user


def current_user_mutator(user:dict=Depends(current_admin),x_v2_demo_action:str|None=Header(default=None)):
    if x_v2_demo_action!='user-management':raise HTTPException(403,'Kullanıcı yönetim onayı gerekli')
    return user
