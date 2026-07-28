from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.models.ai import (
    MonthlyInsightsRequest,
    MonthlyInsightsResponse,
    RecipeToGroceryRequest,
    RecipeToGroceryResponse,
)
from app.services.ai import convert_recipe_to_grocery, generate_monthly_insights

router = APIRouter()


@router.post("/ai/recipe-to-grocery", response_model=RecipeToGroceryResponse)
def recipe_to_grocery(
    payload: RecipeToGroceryRequest,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> RecipeToGroceryResponse:
    """Recipe to Grocery List Converter powered by Gemini AI."""
    if not payload.recipePrompt or not payload.recipePrompt.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="recipePrompt is required.",
        )
    return convert_recipe_to_grocery(payload)


@router.post("/ai/monthly-insights", response_model=MonthlyInsightsResponse)
def monthly_insights(
    payload: MonthlyInsightsRequest,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> MonthlyInsightsResponse:
    """Monthly Natural-Language Family Grocery Insights powered by Gemini AI."""
    return generate_monthly_insights(payload)
