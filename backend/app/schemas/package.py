from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field,field_validator

class PackageFields(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    name:str=Field(min_length=1,max_length=120)
    download_mbps:int=Field(ge=1,le=1000000,strict=True)
    upload_mbps:int=Field(ge=1,le=1000000,strict=True)
    router_profile:str|None=Field(default=None,max_length=120)
    currency:Literal['TRY','USD','EUR','GBP']= 'TRY'
    radius_policy_ref:str|None=Field(default=None,max_length=120)
    monthly_price:Decimal|None=Field(default=None,ge=0,max_digits=12,decimal_places=2)
    duration_days:int=Field(ge=1,le=3660,strict=True)
    active:bool=Field(strict=True)
    @field_validator('name','router_profile','radius_policy_ref')
    @classmethod
    def printable(cls,value):
        if value is not None and (not value or not value.isprintable()):raise ValueError('Yazdırılabilir paket/profil adı gerekli.')
        return value

class PackageConfirmation(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id:UUID
    expected_revision:int=Field(ge=0)
    confirmed:Literal[True]
    @field_validator('confirmed',mode='before')
    @classmethod
    def explicit(cls,value):
        if value is not True:raise ValueError('Açık onay gerekli.')
        return value

class PackageCommand(PackageConfirmation):
    fields:PackageFields

class PackageDeletion(BaseModel):
    id:str
    request_id:UUID
    deleted:Literal[True]=True
    is_demo:Literal[True]=True

class PackageRecord(BaseModel):
    id:str
    revision:int
    fields:PackageFields
    subscriber_count:int|None=None
    is_demo:Literal[True]=True

class PackageList(BaseModel):
    items:list[PackageRecord]
    total:int
    page:int
    page_size:int
    is_demo:Literal[True]=True
