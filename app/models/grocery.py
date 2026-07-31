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
    unit: str | None = "pcs"
    unitPrice: float | None = None
    actualPrice: float | None = None
    notes: str | None = None
    status: Literal["pending", "in_cart", "completed"] = "pending"
    addedBy: GroceryActor | None = None
    claimedBy: GroceryActor | None = None
    completedBy: GroceryActor | None = None
    createdAt: Any | None = None
    updatedAt: Any | None = None
    claimedAt: Any | None = None
    completedAt: Any | None = None

    # ── Extended fields for assignment, scheduling & tracking ──
    assignee: GroceryActor | None = None
    dueDate: Any | None = None
    reminderAt: Any | None = None
    recurrenceFrequency: str | None = "none"
    estimatedTotal: float | None = None

    # ── Meal & consumption tracking ──
    mealType: str | None = None
    servingsCount: int | None = None
    monthlyUsageFrequency: int | None = None

    # ── Superstore selection ──
    selectedSuperstore: str | None = None
    storeName: str | None = None
    unitPriceNormalized: float | None = None

    @field_validator(
        "createdAt", "updatedAt", "claimedAt", "completedAt",
        "dueDate", "reminderAt",
        mode="before",
    )
    @classmethod
    def parse_datetime_fields(cls, v: Any) -> Any:
        return format_datetime(v)

    model_config = ConfigDict(extra="allow")


class GrocerySummary(BaseModel):
    familyId: str
    totalItems: int
    pendingItems: int
    inCartItems: int = 0
    completedItems: int
    urgentItems: int
    assignedItems: int = 0
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
    unit: str | None = "pcs"
    unitPrice: float | None = None
    notes: str | None = None

    # ── Extended fields ──
    assignee: GroceryActor | None = None
    dueDate: str | None = None
    reminderAt: str | None = None
    recurrenceFrequency: str | None = "none"
    estimatedTotal: float | None = None
    mealType: str | None = None
    servingsCount: int | None = None
    monthlyUsageFrequency: int | None = None
    selectedSuperstore: str | None = None
    storeName: str | None = None


class UpdateGroceryItemRequest(BaseModel):
    name: str | None = None
    category: str | None = None
    priority: Literal["Urgent", "High", "Medium", "Low"] | None = None
    quantity: str | None = None
    unit: str | None = None
    unitPrice: float | None = None
    actualPrice: float | None = None
    notes: str | None = None
    status: Literal["pending", "in_cart", "completed"] | None = None

    # ── Extended fields ──
    assignee: GroceryActor | None = None
    claimedBy: GroceryActor | None = None
    completedBy: GroceryActor | None = None
    dueDate: str | None = None
    reminderAt: str | None = None
    recurrenceFrequency: str | None = None
    estimatedTotal: float | None = None
    mealType: str | None = None
    servingsCount: int | None = None
    monthlyUsageFrequency: int | None = None
    selectedSuperstore: str | None = None
    storeName: str | None = None
    unitPriceNormalized: float | None = None

    model_config = ConfigDict(extra="allow")
