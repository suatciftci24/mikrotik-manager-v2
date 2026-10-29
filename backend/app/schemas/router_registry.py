"""Onboarding commands are explicit; secret fields cannot enter repr/serialization."""
from ipaddress import IPv4Address
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class RouterCandidate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id: UUID
    name: str=Field(min_length=1,max_length=120)
    management_address: IPv4Address
    port: int=Field(default=8729,ge=1024,le=65535)
    expected_identity: str=Field(default='',max_length=120)
    expected_version: str=Field(default='',max_length=40)
    username: str=Field(default='',max_length=128,repr=False,exclude=True)
    password: SecretStr|None=Field(default=None,repr=False,exclude=True)
    ca_pem: str=Field(default='',max_length=262144,repr=False,exclude=True)
    leaf_sha256: str=Field(pattern=r'^[a-f0-9]{64}$')
    router_id: str|None=Field(default=None,pattern=r'^registered-[0-9a-f-]{36}$')
    expected_revision: int=Field(default=0,ge=0)
    confirmed_read_only: Literal[True]

    @field_validator('name','expected_identity','expected_version')
    @classmethod
    def text(cls,value):
        if any(ord(c)<32 for c in value):raise ValueError('INVALID_TEXT')
        return value.strip()

    @field_validator('name')
    @classmethod
    def nonempty(cls,value):
        if not value:raise ValueError('NAME_REQUIRED')
        return value

    @field_validator('confirmed_read_only',mode='before')
    @classmethod
    def explicit(cls,value):
        if value is not True:raise ValueError('EXPLICIT_CONFIRMATION_REQUIRED')
        return value


class RegisterVerified(BaseModel):
    model_config=ConfigDict(extra='forbid')
    verification_id: UUID
    confirmed: Literal[True]
    _explicit=field_validator('confirmed',mode='before')(RouterCandidate.explicit.__func__)


class RecheckRouter(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id: UUID
    expected_revision: int=Field(ge=0)
    confirmed_read_only: Literal[True]
    _explicit=field_validator('confirmed_read_only',mode='before')(RouterCandidate.explicit.__func__)
