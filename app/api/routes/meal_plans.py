from typing import Annotated, Any
from fastapi import APIRouter, Depends
import uuid

from app.api.dependencies import ensure_family_access, get_current_user
from app.core.firebase import get_firestore_client
from app.models.meal_plan import AddMealItemRequest, DailyMealPlan, MealItem

router = APIRouter()


def _meal_plan_ref(family_id: str, date_str: str):
    """Return a Firestore document reference for a family's daily meal plan."""
    return (
        get_firestore_client()
        .collection("families")
        .document(family_id)
        .collection("meal_plans")
        .document(date_str)
    )


def _load_meal_plan(family_id: str, date_str: str) -> DailyMealPlan:
    """Load a meal plan from Firestore or return a fresh empty plan."""
    doc = _meal_plan_ref(family_id, date_str).get()
    if doc.exists:
        return DailyMealPlan.model_validate(doc.to_dict())
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


def _save_meal_plan(family_id: str, plan: DailyMealPlan) -> None:
    """Persist a meal plan document to Firestore."""
    _meal_plan_ref(family_id, plan.date).set(plan.model_dump())


@router.get("/families/{family_id}/meal-plans", response_model=DailyMealPlan)
def read_family_meal_plan(
    family_id: str,
    date: str = "2026-10-14",
    current_user: Annotated[dict[str, Any], Depends(get_current_user)] = None,
) -> DailyMealPlan:
    """Retrieve daily meal plan for selected family and date."""
    if current_user:
        ensure_family_access(family_id, current_user)
    return _load_meal_plan(family_id, date)


@router.post("/families/{family_id}/meal-plans/item", response_model=DailyMealPlan)
def add_meal_plan_item(
    family_id: str,
    payload: AddMealItemRequest,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)] = None,
) -> DailyMealPlan:
    """Add a planned meal item to the daily meal plan."""
    if current_user:
        ensure_family_access(family_id, current_user)

    plan = _load_meal_plan(family_id, payload.date)
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

    _save_meal_plan(family_id, plan)
    return plan

