from typing import Literal

from pydantic import BaseModel, ConfigDict


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

    model_config = ConfigDict(extra="allow")


class CreateFamilyRequest(BaseModel):
    name: str


class JoinFamilyRequest(BaseModel):
    inviteCode: str


class MessageResponse(BaseModel):
    message: str
