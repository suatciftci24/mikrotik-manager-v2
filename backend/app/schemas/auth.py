from app.schemas.pilot_operator import PilotIdentity
from pydantic import BaseModel, Field
from typing import Literal


class DemoLogin(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128, repr=False, exclude=True)


class UserResponse(BaseModel):
    pilot_identity: PilotIdentity | None = None
    id: str
    name: str
    email: str
    role: str
    is_demo: bool
    account_origin: Literal['BOOTSTRAP_DEMO','DEMO','LOCAL'] = 'DEMO'
    bootstrap_closed: bool = False
    login_enabled: bool = False
    username: str = ''
    role_code: str = 'VIEWER'
    active: bool = True
    revision: int = 0
    permissions: dict[str,dict[str,bool]] = Field(default_factory=dict)
    can_manage_users: bool = False
