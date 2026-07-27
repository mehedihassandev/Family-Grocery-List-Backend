from app.services.grocery import summarize_grocery_items


def test_summarize_grocery_items_counts_status_priority_and_category() -> None:
    summary = summarize_grocery_items(
        "family-1",
        [
            {
                "id": "item-1",
                "familyId": "family-1",
                "name": "Milk",
                "category": "Dairy",
                "priority": "Urgent",
                "status": "pending",
            },
            {
                "id": "item-2",
                "familyId": "family-1",
                "name": "Bread",
                "category": "Snacks",
                "priority": "Medium",
                "status": "completed",
            },
            {
                "id": "item-3",
                "familyId": "family-1",
                "name": "Rice",
                "category": "",
                "priority": "Low",
                "status": "pending",
            },
        ],
    )

    assert summary.familyId == "family-1"
    assert summary.totalItems == 3
    assert summary.pendingItems == 2
    assert summary.completedItems == 1
    assert summary.urgentItems == 1
    assert summary.categoryTotals == {"Dairy": 1, "Snacks": 1, "Other": 1}
