from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app
from app.models.grocery import GroceryItem, GrocerySummary

client = TestClient(app)


def test_health_check_api() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@patch("app.api.routes.grocery.list_family_grocery_items")
def test_read_family_grocery_items_api(mock_list: MagicMock) -> None:
    mock_list.return_value = [
        GroceryItem(
            id="item-123",
            familyId="demo-family",
            name="Organic Whole Milk",
            category="Dairy",
            priority="Urgent",
            quantity="2 gallons",
            notes="Prefer organic brand",
            status="pending",
        )
    ]

    response = client.get("/v1/families/demo-family/items")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Organic Whole Milk"
    assert data[0]["category"] == "Dairy"
    assert data[0]["priority"] == "Urgent"


@patch("app.api.routes.grocery.create_grocery_item")
def test_add_grocery_item_api(mock_create: MagicMock) -> None:
    mock_create.return_value = GroceryItem(
        id="item-456",
        familyId="demo-family",
        name="Organic Bananas",
        category="Produce",
        priority="Medium",
        quantity="1 bunch",
        notes="Slightly green",
        status="pending",
    )

    payload = {
        "name": "Organic Bananas",
        "category": "Produce",
        "priority": "Medium",
        "quantity": "1 bunch",
        "notes": "Slightly green",
    }

    response = client.post("/v1/families/demo-family/items", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == "item-456"
    assert data["name"] == "Organic Bananas"
    assert data["quantity"] == "1 bunch"


@patch("app.api.routes.grocery.get_grocery_item")
def test_read_grocery_item_detail_api_success(mock_get: MagicMock) -> None:
    mock_get.return_value = GroceryItem(
        id="item-abc-123",
        familyId="family-xyz-789",
        name="Organic Whole Milk",
        category="Dairy",
        priority="Urgent",
        quantity="2 gallons",
        notes="Prefer organic brand",
        status="pending",
    )

    response = client.get("/v1/families/family-xyz-789/items/item-abc-123")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "item-abc-123"
    assert data["name"] == "Organic Whole Milk"


@patch("app.api.routes.grocery.get_grocery_item")
def test_read_grocery_item_detail_api_not_found(mock_get: MagicMock) -> None:
    mock_get.return_value = None

    response = client.get("/v1/families/family-xyz-789/items/nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Grocery item not found for this family."


@patch("app.api.routes.grocery.update_grocery_item")
@patch("app.api.routes.grocery.get_grocery_item")
def test_modify_grocery_item_api_success(
    mock_get: MagicMock, mock_update: MagicMock
) -> None:
    item = GroceryItem(
        id="item-abc-123",
        familyId="family-xyz-789",
        name="Organic Whole Milk",
        status="pending",
    )
    mock_get.return_value = item
    mock_update.return_value = GroceryItem(
        id="item-abc-123",
        familyId="family-xyz-789",
        name="Organic Whole Milk",
        status="completed",
        notes="Purchased from Whole Foods",
    )

    payload = {"status": "completed", "notes": "Purchased from Whole Foods"}
    response = client.patch(
        "/v1/families/family-xyz-789/items/item-abc-123", json=payload
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["notes"] == "Purchased from Whole Foods"


@patch("app.api.routes.grocery.get_grocery_item")
def test_modify_grocery_item_api_not_found(mock_get: MagicMock) -> None:
    mock_get.return_value = None

    response = client.patch(
        "/v1/families/family-xyz-789/items/nonexistent", json={"status": "completed"}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Grocery item not found for this family."


@patch("app.api.routes.grocery.delete_grocery_item")
@patch("app.api.routes.grocery.get_grocery_item")
def test_remove_grocery_item_api_success(
    mock_get: MagicMock, mock_delete: MagicMock
) -> None:
    mock_get.return_value = GroceryItem(
        id="item-abc-123",
        familyId="family-xyz-789",
        name="Organic Whole Milk",
    )
    mock_delete.return_value = True

    response = client.delete("/v1/families/family-xyz-789/items/item-abc-123")
    assert response.status_code == 204
    assert response.content == b""


@patch("app.api.routes.grocery.get_grocery_item")
def test_remove_grocery_item_api_not_found(mock_get: MagicMock) -> None:
    mock_get.return_value = None

    response = client.delete("/v1/families/family-xyz-789/items/nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Grocery item not found for this family."


@patch("app.api.routes.grocery.seed_family_grocery_items")
def test_seed_grocery_items_api(mock_seed: MagicMock) -> None:
    mock_seed.return_value = [
        GroceryItem(
            id=f"item-{i}",
            familyId="demo-family",
            name=f"Sample {i}",
            category="Produce",
            priority="Medium",
            status="pending",
        )
        for i in range(5)
    ]

    response = client.post("/v1/families/demo-family/seed")
    assert response.status_code == 201
    data = response.json()
    assert len(data) == 5


@patch("app.api.routes.grocery.build_grocery_summary")
def test_read_grocery_summary_api(mock_summary: MagicMock) -> None:
    mock_summary.return_value = GrocerySummary(
        familyId="family-xyz-789",
        totalItems=12,
        pendingItems=8,
        completedItems=4,
        urgentItems=3,
        categoryTotals={"Produce": 4, "Dairy": 3, "Bakery": 2, "Other": 3},
    )

    response = client.get("/v1/families/family-xyz-789/grocery-summary")
    assert response.status_code == 200
    data = response.json()
    assert data["familyId"] == "family-xyz-789"
    assert data["totalItems"] == 12
    assert data["pendingItems"] == 8
    assert data["completedItems"] == 4
    assert data["urgentItems"] == 3
    assert data["categoryTotals"] == {
        "Produce": 4,
        "Dairy": 3,
        "Bakery": 2,
        "Other": 3,
    }


@patch("app.api.dependencies.get_settings")
@patch("app.api.dependencies.get_firestore_client")
def test_ensure_family_access_forbidden(
    mock_fs: MagicMock, mock_settings: MagicMock
) -> None:
    mock_settings.return_value = Settings(allow_dev_bypass=False)
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {"familyId": "other-family"}
    mock_fs.return_value.collection.return_value.document.return_value.get.return_value = mock_doc

    import pytest
    from fastapi import HTTPException

    from app.api.dependencies import ensure_family_access

    with pytest.raises(HTTPException) as exc_info:
        ensure_family_access("target-family", {"uid": "user-123"})
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "User does not belong to this family."
