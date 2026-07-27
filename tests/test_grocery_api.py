from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@patch("app.api.routes.grocery.list_family_grocery_items")
def test_read_family_grocery_items_api(mock_list: MagicMock) -> None:
    mock_list.return_value = [
        {
            "id": "item-123",
            "familyId": "demo-family",
            "name": "Milk",
            "category": "Dairy",
            "priority": "Urgent",
            "status": "pending",
        }
    ]

    response = client.get("/v1/families/demo-family/items")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Milk"


@patch("app.api.routes.grocery.create_grocery_item")
def test_add_grocery_item_api(mock_create: MagicMock) -> None:
    mock_create.return_value = {
        "id": "item-456",
        "familyId": "demo-family",
        "name": "Organic Bananas",
        "category": "Produce",
        "priority": "Medium",
        "status": "pending",
    }

    payload = {
        "name": "Organic Bananas",
        "category": "Produce",
        "priority": "Medium",
        "quantity": "1 bunch",
    }

    response = client.post("/v1/families/demo-family/items", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == "item-456"
    assert data["name"] == "Organic Bananas"


@patch("app.api.routes.grocery.seed_family_grocery_items")
def test_seed_grocery_items_api(mock_seed: MagicMock) -> None:
    mock_seed.return_value = [
        {
            "id": f"item-{i}",
            "familyId": "demo-family",
            "name": f"Sample {i}",
            "category": "Produce",
            "priority": "Medium",
            "status": "pending",
        }
        for i in range(5)
    ]

    response = client.post("/v1/families/demo-family/seed")
    assert response.status_code == 201
    data = response.json()
    assert len(data) == 5

