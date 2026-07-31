from typing import Annotated, Any
from fastapi import APIRouter, Depends
import uuid

from app.api.dependencies import ensure_family_access, get_current_user
from app.models.meal_plan import AddMealItemRequest, DailyMealPlan, MealItem

router = APIRouter()

# In-memory mock store for meal plans
MEAL_PLANS_STORE: dict[str, DailyMealPlan] = {}


def _get_empty_meal_plan(date_str: str) -> DailyMealPlan:
    return DailyMealPlan(
        date=date_str,
        dayName="Active Day",
        totalKcalPlanned=0,
        kcalTarget=2200,
        mealsPlannedCount=0,
        breakfast=[],
        lunch=[],
        dinner=[],
        snacks=[],
    )



@router.get("/families/{family_id}/meal-plans", response_model=DailyMealPlan)
def read_family_meal_plan(
    family_id: str,
    date: str = "2026-10-14",
    current_user: Annotated[dict[str, Any], Depends(get_current_user)] = None,
) -> DailyMealPlan:
    """Retrieve daily meal plan for selected family and date."""
    if current_user:
        ensure_family_access(family_id, current_user)

    key = f"{family_id}:{date}"
    if key not in MEAL_PLANS_STORE:
        MEAL_PLANS_STORE[key] = _get_empty_meal_plan(date)

    return MEAL_PLANS_STORE[key]


@router.post("/families/{family_id}/meal-plans/item", response_model=DailyMealPlan)
def add_meal_plan_item(
    family_id: str,
    payload: AddMealItemRequest,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)] = None,
) -> DailyMealPlan:
    """Add a planned meal item to the daily meal plan."""
    if current_user:
        ensure_family_access(family_id, current_user)

    key = f"{family_id}:{payload.date}"
    if key not in MEAL_PLANS_STORE:
        MEAL_PLANS_STORE[key] = _get_empty_meal_plan(payload.date)

    plan = MEAL_PLANS_STORE[key]
    new_item = MealItem(
        id=str(uuid.uuid4())[:8],
        name=payload.name,
        category=payload.mealCategory,
        prepTimeMins=payload.prepTimeMins,
        tags=payload.tags,
        status="planned",
    )

    if payload.mealCategory == "breakfast":
        plan.breakfast.append(new_item)
    elif payload.mealCategory == "lunch":
        plan.lunch.append(new_item)
    elif payload.mealCategory == "dinner":
        plan.dinner.append(new_item)
    elif payload.mealCategory == "snacks":
        plan.snacks.append(new_item)

    plan.mealsPlannedCount = (
        len(plan.breakfast) + len(plan.lunch) + len(plan.dinner) + len(plan.snacks)
    )
    return plan
