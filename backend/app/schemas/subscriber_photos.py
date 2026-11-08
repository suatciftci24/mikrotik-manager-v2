from typing import Literal
from pydantic import BaseModel, Field


class SubscriberPhoto(BaseModel):
    id: str = Field(pattern=r"^[0-9a-f]{32}$")
    created_at: str
    size_bytes: int = Field(ge=1, le=8 * 1024 * 1024)
    media_type: Literal["image/jpeg"] = "image/jpeg"


class SubscriberPhotoCollection(BaseModel):
    subscriber_id: str
    source: Literal["LOCAL", "RADIUS"]
    access_type: Literal["PPPOE", "HOTSPOT"]
    items: list[SubscriberPhoto] = Field(max_length=20)
    is_demo: Literal[True] = True


class SubscriberPhotoCreated(BaseModel):
    item: SubscriberPhoto
    is_demo: Literal[True] = True


class SubscriberPhotoDeleted(BaseModel):
    id: str = Field(pattern=r"^[0-9a-f]{32}$")
    deleted: Literal[True] = True
    is_demo: Literal[True] = True
