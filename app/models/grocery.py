from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.family import format_datetime


class GroceryActor(BaseModel):
    uid: str = ""
    name: str = ""
    photoURL: str | None = None


class GroceryItem(BaseModel):
    id: str
    familyId: str
    name: str = ""
    category: str = "Other"
    priority: Literal["Urgent", "High", "Medium", "Low"] = "Medium"
    quantity: str | None = None
    notes: str | None = None
    status: Literal["pending", "completed"] = "pending"
    addedBy: GroceryActor | None = None
    completedBy: GroceryActor | None = None
    createdAt: Any | None = None
    updatedAt: Any | None = None
    completedAt: Any | None = None

    @field_validator("createdAt", "updatedAt", "completedAt", mode="before")
    @classmethod
    def parse_datetime_fields(cls, v: Any) -> Any:
        return format_datetime(v)

    model_config = ConfigDict(extra="allow")


class GrocerySummary(BaseModel):
    familyId: str
    totalItems: int
    pendingItems: int
    completedItems: int
    urgentItems: int
    categoryTotals: dict[str, int]
    updatedAt: datetime | str | None = None

    @field_validator("updatedAt", mode="before")
    @classmethod
    def parse_updated_at(cls, v: Any) -> Any:
        return format_datetime(v)


class CreateGroceryItemRequest(BaseModel):
    name: str
    category: str = "Other"
    priority: Literal["Urgent", "High", "Medium", "Low"] = "Medium"
    quantity: str | None = None
    notes: str | None = None


class UpdateGroceryItemRequest(BaseModel):
    name: str | None = None
    category: str | None = None
    priority: Literal["Urgent", "High", "Medium", "Low"] | None = None
    quantity: str | None = None
    notes: str | None = None
    status: Literal["pending", "completed"] | None = None


