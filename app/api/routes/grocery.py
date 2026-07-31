from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import ensure_family_access, get_current_user
from app.models.grocery import (
    CreateGroceryItemRequest,
    GroceryActor,
    GroceryItem,
    GrocerySummary,
    UpdateGroceryItemRequest,
)
from app.services.grocery import (
    build_grocery_summary,
    create_grocery_item,
    delete_grocery_item,
    get_grocery_item,
    list_family_grocery_items,
    seed_family_grocery_items,
    update_grocery_item,
)

router = APIRouter()


@router.get("/families/{family_id}/items", response_model=list[GroceryItem])
def read_family_grocery_items(
    family_id: str,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> list[GroceryItem]:
    """List all grocery items belonging to a specific family."""
    ensure_family_access(family_id, current_user)
    return list_family_grocery_items(family_id)


@router.post(
    "/families/{family_id}/items",
    response_model=GroceryItem,
    status_code=status.HTTP_201_CREATED,
)
def add_grocery_item(
    family_id: str,
    payload: CreateGroceryItemRequest,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> GroceryItem:
    """Add a new grocery item to Firestore for the given family."""
    ensure_family_access(family_id, current_user)
    actor = GroceryActor(
        uid=current_user.get("uid", ""),
        name=current_user.get("name", "Unknown User"),
        photoURL=current_user.get("picture"),
    )
    return create_grocery_item(family_id, payload, added_by=actor)


@router.get("/families/{family_id}/items/{item_id}", response_model=GroceryItem)
def read_grocery_item_detail(
    family_id: str,
    item_id: str,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> GroceryItem:
    """Get details of a specific grocery item."""
    ensure_family_access(family_id, current_user)
    item = get_grocery_item(item_id)
    if not item or item.familyId != family_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grocery item not found for this family.",
        )
    return item


@router.patch("/families/{family_id}/items/{item_id}", response_model=GroceryItem)
def modify_grocery_item(
    family_id: str,
    item_id: str,
    payload: UpdateGroceryItemRequest,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> GroceryItem:
    """Update details or status (e.g. pending/in_cart/completed) of a grocery item."""
    ensure_family_access(family_id, current_user)
    existing = get_grocery_item(item_id)
    if not existing or existing.familyId != family_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grocery item not found for this family.",
        )

    user_actor = GroceryActor(
        uid=current_user.get("uid", ""),
        name=current_user.get("name", "Unknown User"),
        photoURL=current_user.get("picture"),
    )

    completed_actor = user_actor if payload.status == "completed" else None
    claimed_actor = user_actor if payload.status == "in_cart" else None

    updated = update_grocery_item(
        item_id, payload, completed_by=completed_actor, claimed_by=claimed_actor,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Failed to update grocery item.",
        )
    return updated



@router.delete("/families/{family_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_grocery_item(
    family_id: str,
    item_id: str,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> None:
    """Delete a grocery item from Firestore."""
    ensure_family_access(family_id, current_user)
    existing = get_grocery_item(item_id)
    if not existing or existing.familyId != family_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grocery item not found for this family.",
        )
    delete_grocery_item(item_id)


@router.post(
    "/families/{family_id}/seed",
    response_model=list[GroceryItem],
    status_code=status.HTTP_201_CREATED,
)
def seed_grocery_items(
    family_id: str,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> list[GroceryItem]:
    """Seed 5 sample grocery items into Firestore for testing and learning python."""
    ensure_family_access(family_id, current_user)
    return seed_family_grocery_items(family_id)


@router.get("/families/{family_id}/grocery-summary", response_model=GrocerySummary)
def read_grocery_summary(
    family_id: str,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> GrocerySummary:
    """Get aggregated grocery stats (total, pending, completed, urgent items)."""
    ensure_family_access(family_id, current_user)
    return build_grocery_summary(family_id)

