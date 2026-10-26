from pydantic import BaseModel, Field


class DemoLogin(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    is_demo: bool
