from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_recipe_to_grocery_known_recipe() -> None:
    payload = {
        "recipePrompt": "Beef Tehari for 6 people",
        "servings": 6,
    }
    response = client.post("/api/v1/ai/recipe-to-grocery", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["recipeName"] == "Beef Tehari"
    assert data["servings"] == 6
    assert len(data["ingredients"]) == 4
    
    ingredient_names = [i["name"] for i in data["ingredients"]]
    assert "Kataribhog Rice" in ingredient_names
    assert "Beef" in ingredient_names


def test_recipe_to_grocery_custom_recipe() -> None:
    payload = {
        "recipePrompt": "Pasta Carbonara for 2 people",
        "servings": 2,
    }
    response = client.post("/api/v1/ai/recipe-to-grocery", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["servings"] == 2
    assert len(data["ingredients"]) > 0


def test_recipe_to_grocery_missing_prompt() -> None:
    payload = {"recipePrompt": "", "servings": 4}
    response = client.post("/api/v1/ai/recipe-to-grocery", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "recipePrompt is required."


def test_monthly_insights_api() -> None:
    payload = {
        "familyId": "fam_12345",
        "monthlyBreakdown": {
            "Staples": 3500,
            "Meat": 5200,
            "Dairy": 1200,
        },
    }
    response = client.post("/api/v1/ai/monthly-insights", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["familyId"] == "fam_12345"
    assert "insights" in data
    assert isinstance(data["keyRecommendations"], list)
    assert len(data["keyRecommendations"]) > 0
    assert data["potentialMonthlySavingsBDT"] is not None


@patch("app.services.ai.httpx.Client")
@patch("app.services.ai.get_settings")
def test_recipe_to_grocery_with_gemini_api(
    mock_get_settings: MagicMock, mock_client_cls: MagicMock
) -> None:
    mock_settings = MagicMock()
    mock_settings.gemini_api_key = "fake_gemini_key"
    mock_get_settings.return_value = mock_settings

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": (
                                '{"recipeName": "Gemini Tehari", "servings": 6, '
                                '"ingredients": [{"name": "Basmati", "category": "Staples", '
                                '"quantity": "1kg", "estimatedPriceBDT": 120}]}'
                            )
                        }
                    ]
                }
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.return_value = mock_resp
    mock_client_cls.return_value = mock_client

    payload = {"recipePrompt": "Beef Tehari", "servings": 6}
    response = client.post("/api/v1/ai/recipe-to-grocery", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["recipeName"] == "Gemini Tehari"
    assert data["ingredients"][0]["name"] == "Basmati"
