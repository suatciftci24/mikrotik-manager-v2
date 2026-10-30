from app.schemas.pilot_operator import PilotIdentity
from pydantic import BaseModel, Field


class DemoLogin(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    pilot_identity: PilotIdentity | None = None
    id: str
    name: str
    email: str
    role: str
    is_demo: bool
    username: str = ''
    role_code: str = 'VIEWER'
    active: bool = True
    revision: int = 0
    permissions: dict[str,dict[str,bool]] = Field(default_factory=dict)
    can_manage_users: bool = False
