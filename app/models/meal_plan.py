from typing import Literal, Optional
from pydantic import BaseModel, Field


class Macros(BaseModel):
    proteinGrams: int = 45
    carbsGrams: int = 180
    fatGrams: int = 40


class MealItem(BaseModel):
    id: str
    name: str
    category: Literal["breakfast", "lunch", "dinner", "snacks"]
    prepTimeMins: int = 15
    tags: str = "High Protein"
    status: Literal["in_kitchen", "syncing", "planned"] = "in_kitchen"
    thumbnailUrl: Optional[str] = None


class DailyMealPlan(BaseModel):
    date: str = "2026-10-14"
    dayName: str = "Tuesday"
    totalKcalPlanned: int = 1450
    kcalTarget: int = 2200
    mealsPlannedCount: int = 3
    macros: Macros = Field(default_factory=Macros)
    breakfast: list[MealItem] = Field(default_factory=list)
    lunch: list[MealItem] = Field(default_factory=list)
    dinner: list[MealItem] = Field(default_factory=list)
    snacks: list[MealItem] = Field(default_factory=list)


class AddMealItemRequest(BaseModel):
    date: str
    mealCategory: Literal["breakfast", "lunch", "dinner", "snacks"]
    name: str
    prepTimeMins: int = 15
    tags: str = "Quick & Healthy"
