from fastapi import APIRouter, Depends, Response
from fastapi import Cookie

from app.core.config import settings
from app.core.security import current_demo_user, login_demo, logout_demo
from app.schemas.auth import DemoLogin, UserResponse

router = APIRouter(prefix='/auth', tags=['system-users'])


@router.post('/login', response_model=UserResponse)
def demo_login(payload: DemoLogin, response: Response):
    token = login_demo(payload.username, payload.password)
    response.set_cookie('v2_session', token, httponly=True, secure=settings.session_secure,
                        samesite='strict', max_age=8 * 60 * 60, path='/api')
    from app.core.security import _DEMO_USER
    return _DEMO_USER


@router.get('/me', response_model=UserResponse)
def me(user: dict = Depends(current_demo_user)):
    return user


@router.post('/logout')
def logout(response: Response, v2_session: str | None = Cookie(default=None)):
    logout_demo(v2_session)
    response.delete_cookie('v2_session', path='/api', httponly=True,
                           secure=settings.session_secure, samesite='strict')
    return {'ok': True}
