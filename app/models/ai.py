from typing import Any

from pydantic import BaseModel, ConfigDict


class RecipeIngredient(BaseModel):
    name: str
    category: str
    quantity: str
    estimatedPriceBDT: float

    model_config = ConfigDict(populate_by_name=True)


class RecipeToGroceryRequest(BaseModel):
    recipePrompt: str
    servings: int = 4

    model_config = ConfigDict(populate_by_name=True)


class GenerateAiRecipeRequest(BaseModel):
    recipePrompt: str
    servings: int = 4

    model_config = ConfigDict(populate_by_name=True)



class RecipeToGroceryResponse(BaseModel):
    recipeName: str
    servings: int
    ingredients: list[RecipeIngredient]

    model_config = ConfigDict(populate_by_name=True)


class MonthlyInsightsRequest(BaseModel):
    familyId: str | None = None
    monthlyBreakdown: dict[str, Any] | list[dict[str, Any]] | None = None
    items: list[dict[str, Any]] | list[str] | None = None

    model_config = ConfigDict(populate_by_name=True)


class MonthlyInsightsResponse(BaseModel):
    familyId: str | None = None
    insights: str
    keyRecommendations: list[str]
    potentialMonthlySavingsBDT: float | None = None

    model_config = ConfigDict(populate_by_name=True)
