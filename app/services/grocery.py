from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

from app.core.firebase import get_firestore_client
from app.models.grocery import (
    CreateGroceryItemRequest,
    GroceryActor,
    GroceryItem,
    GrocerySummary,
    UpdateGroceryItemRequest,
)

GROCERY_ITEMS_COLLECTION = "grocery_items"


def _snapshot_to_dict(snapshot: Any) -> dict[str, Any]:
    data = snapshot.to_dict() or {}
    data.setdefault("id", snapshot.id)
    return data


def list_family_grocery_items(family_id: str) -> list[GroceryItem]:
    snapshots = (
        get_firestore_client()
        .collection(GROCERY_ITEMS_COLLECTION)
        .where("familyId", "==", family_id)
        .stream()
    )
    return [GroceryItem.model_validate(_snapshot_to_dict(snapshot)) for snapshot in snapshots]


def get_grocery_item(item_id: str) -> GroceryItem | None:
    snapshot = get_firestore_client().collection(GROCERY_ITEMS_COLLECTION).document(item_id).get()
    if not snapshot.exists:
        return None
    return GroceryItem.model_validate(_snapshot_to_dict(snapshot))


def _actor_dump(actor: GroceryActor | None) -> dict[str, Any] | None:
    """Safely serialise a GroceryActor for Firestore storage."""
    return actor.model_dump() if actor else None


def create_grocery_item(
    family_id: str,
    payload: CreateGroceryItemRequest,
    added_by: GroceryActor | None = None,
) -> GroceryItem:
    doc_ref = get_firestore_client().collection(GROCERY_ITEMS_COLLECTION).document()
    now = datetime.now(UTC).isoformat()
    data: dict[str, Any] = {
        "id": doc_ref.id,
        "familyId": family_id,
        "name": payload.name,
        "category": payload.category,
        "priority": payload.priority,
        "quantity": payload.quantity,
        "unit": getattr(payload, "unit", "pcs"),
        "unitPrice": payload.unitPrice,
        "notes": payload.notes,
        "status": "pending",
        "addedBy": _actor_dump(added_by),
        "claimedBy": None,
        "completedBy": None,
        "createdAt": now,
        "updatedAt": now,
        "claimedAt": None,
        "completedAt": None,
        # ── Extended fields ──
        "assignee": _actor_dump(payload.assignee),
        "dueDate": payload.dueDate,
        "reminderAt": payload.reminderAt,
        "recurrenceFrequency": payload.recurrenceFrequency or "none",
        "estimatedTotal": payload.estimatedTotal,
        "mealType": payload.mealType,
        "servingsCount": payload.servingsCount,
        "monthlyUsageFrequency": payload.monthlyUsageFrequency,
        "selectedSuperstore": payload.selectedSuperstore,
        "storeName": payload.storeName,
    }
    doc_ref.set(data)
    item = GroceryItem.model_validate(data)

    # ── Notify family: item added ──
    if added_by and added_by.uid:
        try:
            from app.services.notification import create_and_send_family_notification
            actor_name = added_by.name or "A family member"
            create_and_send_family_notification(
                family_id=family_id,
                actor_uid=added_by.uid,
                actor_name=actor_name,
                title="New Grocery Item Added",
                body=f"{actor_name} added '{payload.name}' to the grocery list.",
                event_type="ITEM_ADDED",
                data={"familyId": family_id, "itemId": item.id, "action": "ITEM_ADDED"},
            )
        except Exception as err:
            import logging
            logging.getLogger(__name__).warning("Failed to send notification: %s", err)

    # ── Notify assignee if item was assigned at creation ──
    if payload.assignee and payload.assignee.uid and added_by and added_by.uid:
        _send_assignment_notification(family_id, added_by, payload.assignee, item)

    return item


def _send_assignment_notification(
    family_id: str,
    actor: GroceryActor,
    assignee: GroceryActor,
    item: GroceryItem,
) -> None:
    """Fire an ITEM_ASSIGNED push notification to the family."""
    if not actor.uid or actor.uid == (assignee.uid or ""):
        return
    try:
        from app.services.notification import create_and_send_family_notification
        actor_name = actor.name or "A family member"
        assignee_name = assignee.name or "someone"
        create_and_send_family_notification(
            family_id=family_id,
            actor_uid=actor.uid,
            actor_name=actor_name,
            title="Item Assigned",
            body=f"{actor_name} assigned '{item.name}' to {assignee_name}.",
            event_type="ITEM_ASSIGNED",
            data={
                "familyId": family_id,
                "itemId": item.id,
                "action": "ITEM_ASSIGNED",
                "assigneeUid": assignee.uid or "",
            },
        )
    except Exception as err:
        import logging
        logging.getLogger(__name__).warning("Failed to send assignment notification: %s", err)


# ── Mapping of UpdateGroceryItemRequest field names to their Firestore keys ──
_EXTENDED_UPDATE_FIELDS = (
    "assignee", "dueDate", "reminderAt", "recurrenceFrequency",
    "estimatedTotal", "mealType", "servingsCount", "monthlyUsageFrequency",
    "selectedSuperstore", "storeName", "unitPriceNormalized",
)


def update_grocery_item(
    item_id: str,
    payload: UpdateGroceryItemRequest,
    completed_by: GroceryActor | None = None,
    claimed_by: GroceryActor | None = None,
) -> GroceryItem | None:
    doc_ref = get_firestore_client().collection(GROCERY_ITEMS_COLLECTION).document(item_id)
    snapshot = doc_ref.get()
    if not snapshot.exists:
        return None

    existing = snapshot.to_dict() or {}
    now = datetime.now(UTC).isoformat()
    updates: dict[str, Any] = {"updatedAt": now}

    # ── Core scalar fields ──
    if payload.name is not None:
        updates["name"] = payload.name
    if payload.category is not None:
        updates["category"] = payload.category
    if payload.priority is not None:
        updates["priority"] = payload.priority
    if payload.quantity is not None:
        updates["quantity"] = payload.quantity
    if payload.unit is not None:
        updates["unit"] = payload.unit
    if payload.unitPrice is not None:
        updates["unitPrice"] = payload.unitPrice
    if payload.actualPrice is not None:
        updates["actualPrice"] = payload.actualPrice
    if payload.notes is not None:
        updates["notes"] = payload.notes

    # ── Status transitions ──
    if payload.status is not None:
        updates["status"] = payload.status
        if payload.status == "completed":
            updates["completedAt"] = now
            if completed_by:
                updates["completedBy"] = completed_by.model_dump()
        elif payload.status == "in_cart":
            updates["claimedAt"] = now
            if claimed_by:
                updates["claimedBy"] = claimed_by.model_dump()
            # Clear completion fields when moving back to in_cart
            updates["completedAt"] = None
            updates["completedBy"] = None
        elif payload.status == "pending":
            # Reset all transition fields
            updates["claimedAt"] = None
            updates["claimedBy"] = None
            updates["completedAt"] = None
            updates["completedBy"] = None

    # ── Explicit claimedBy / completedBy from payload (frontend-driven) ──
    if payload.claimedBy is not None:
        updates["claimedBy"] = _actor_dump(payload.claimedBy)
    if payload.completedBy is not None:
        updates["completedBy"] = _actor_dump(payload.completedBy)

    # ── Extended fields ──
    for field_name in _EXTENDED_UPDATE_FIELDS:
        value = getattr(payload, field_name, None)
        if value is not None:
            if field_name == "assignee":
                updates["assignee"] = _actor_dump(value) if isinstance(value, GroceryActor) else value
            else:
                updates[field_name] = value

    doc_ref.update(updates)
    existing.update(updates)
    existing.setdefault("id", item_id)
    updated_item = GroceryItem.model_validate(existing)

    # ── Notify on completion ──
    if payload.status == "completed" and completed_by and completed_by.uid:
        try:
            from app.services.notification import create_and_send_family_notification
            actor_name = completed_by.name or "A family member"
            create_and_send_family_notification(
                family_id=updated_item.familyId,
                actor_uid=completed_by.uid,
                actor_name=actor_name,
                title="Grocery Item Completed",
                body=f"{actor_name} marked '{updated_item.name}' as completed.",
                event_type="ITEM_COMPLETED",
                data={
                    "familyId": updated_item.familyId,
                    "itemId": item_id,
                    "action": "ITEM_COMPLETED",
                },
            )
        except Exception as err:
            import logging
            logging.getLogger(__name__).warning("Failed to send completion notification: %s", err)

    # ── Notify on assignment change ──
    if payload.assignee and payload.assignee.uid:
        old_assignee_uid = ""
        old_assignee = existing.get("assignee")
        if isinstance(old_assignee, dict):
            old_assignee_uid = old_assignee.get("uid", "")
        if payload.assignee.uid != old_assignee_uid:
            actor = completed_by or claimed_by or GroceryActor(uid="system", name="System")
            _send_assignment_notification(
                updated_item.familyId, actor, payload.assignee, updated_item
            )

    return updated_item


def delete_grocery_item(item_id: str) -> bool:
    doc_ref = get_firestore_client().collection(GROCERY_ITEMS_COLLECTION).document(item_id)
    snapshot = doc_ref.get()
    if not snapshot.exists:
        return False
    doc_ref.delete()
    return True


def seed_family_grocery_items(family_id: str) -> list[GroceryItem]:
    sample_items = [
        CreateGroceryItemRequest(
            name="Organic Whole Milk",
            category="Dairy",
            priority="Urgent",
            quantity="2 gallons",
            notes="Prefer organic brand",
        ),
        CreateGroceryItemRequest(
            name="Organic Bananas",
            category="Produce",
            priority="Medium",
            quantity="1 bunch",
            notes="Slightly green",
        ),
        CreateGroceryItemRequest(
            name="Organic Eggs (Large)",
            category="Dairy",
            priority="Urgent",
            quantity="1 dozen",
            notes="Check expiration date",
        ),
        CreateGroceryItemRequest(
            name="Whole Wheat Bread",
            category="Bakery",
            priority="Medium",
            quantity="1 loaf",
            notes="Sliced bread preferred",
        ),
        CreateGroceryItemRequest(
            name="Whole Bean Coffee",
            category="Pantry",
            priority="Low",
            quantity="1 bag (12 oz)",
            notes="Medium dark roast",
        ),
    ]

    created: list[GroceryItem] = []
    actor = GroceryActor(uid="system-seed", name="Demo Seed Script")
    for sample in sample_items:
        created.append(create_grocery_item(family_id, sample, added_by=actor))
    return created


def summarize_grocery_items(
    family_id: str,
    items: Iterable[Mapping[str, Any] | GroceryItem],
) -> GrocerySummary:
    total_items = 0
    pending_items = 0
    in_cart_items = 0
    completed_items = 0
    urgent_items = 0
    assigned_items = 0
    category_totals: dict[str, int] = {}

    for item in items:
        data = item.model_dump() if isinstance(item, GroceryItem) else dict(item)
        total_items += 1

        status = data.get("status")
        if status == "completed":
            completed_items += 1
        elif status == "in_cart":
            in_cart_items += 1
        else:
            pending_items += 1

        if data.get("priority") == "Urgent":
            urgent_items += 1

        # Count assigned items
        assignee = data.get("assignee")
        if assignee and isinstance(assignee, dict) and assignee.get("uid"):
            assigned_items += 1
        elif isinstance(assignee, GroceryActor) and assignee.uid:
            assigned_items += 1

        category = data.get("category")
        category_name = (
            category.strip() if isinstance(category, str) and category.strip() else "Other"
        )
        category_totals[category_name] = category_totals.get(category_name, 0) + 1

    return GrocerySummary(
        familyId=family_id,
        totalItems=total_items,
        pendingItems=pending_items,
        inCartItems=in_cart_items,
        completedItems=completed_items,
        urgentItems=urgent_items,
        assignedItems=assigned_items,
        categoryTotals=category_totals,
        updatedAt=datetime.now(UTC),
    )


def build_grocery_summary(family_id: str) -> GrocerySummary:
    return summarize_grocery_items(family_id, list_family_grocery_items(family_id))

