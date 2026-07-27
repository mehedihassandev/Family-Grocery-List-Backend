from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator


def format_datetime(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.isoformat().replace("+00:00", "Z")
    return str(v)


class User(BaseModel):
    uid: str
    email: str
    displayName: str
    photoURL: str | None = None
    familyId: str | None = None
    role: Literal["owner", "member"] | None = None

    model_config = ConfigDict(extra="allow")


class Family(BaseModel):
    id: str
    name: str
    inviteCode: str
    ownerId: str
    createdAt: str

    @field_validator("createdAt", mode="before")
    @classmethod
    def parse_created_at(cls, v: Any) -> Any:
        return format_datetime(v)

    model_config = ConfigDict(extra="allow")


class CreateFamilyRequest(BaseModel):
    name: str


class JoinFamilyRequest(BaseModel):
    inviteCode: str


class MessageResponse(BaseModel):
    message: str
