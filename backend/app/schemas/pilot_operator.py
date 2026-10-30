from typing import Literal
from pydantic import BaseModel,ConfigDict,Field


class OperatorCandidate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id:str=Field(min_length=1,max_length=80)
    revision:int=Field(ge=0)
    source:Literal['V2_AUTHENTICATED_SESSION']


class PilotIdentity(BaseModel):
    model_config=ConfigDict(extra='forbid')
    state:Literal['ELIGIBLE','BOOTSTRAP_DEMO','INACTIVE','UNVERIFIED','NOT_ADMIN','INSUFFICIENT_SCOPE']
    candidate:OperatorCandidate|None=None
