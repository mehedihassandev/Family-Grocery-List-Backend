import urllib.parse
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.scraper import sync_store_catalog_to_firestore
from app.services.superstores import _SEARCH_CACHE

try:
    sync_store_catalog_to_firestore()
except Exception:
    pass

client = TestClient(app)


def test_superstores_search_api_success() -> None:
    _SEARCH_CACHE.clear()
    response = client.get("/api/v1/superstores/search?q=Soyabean%20Oil%205L")
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "Soyabean Oil 5L"
    assert data["bestPriceStore"] == "Meena Bazar"
    assert data["bestPriceBDT"] == 875.0
    assert data["savingsAmountBDT"] > 0
    assert len(data["storePrices"]) == 3
    
    store_names = [s["storeName"] for s in data["storePrices"]]
    assert "Shwapno" in store_names
    assert "Meena Bazar" in store_names
    assert "Agora" in store_names
    assert data["storePrices"][0]["unitQuantity"] == "5 Ltr"


def test_superstores_search_v1_alias() -> None:
    _SEARCH_CACHE.clear()
    response = client.get("/v1/superstores/search?q=Teer%20Atta%202kg")
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "Teer Atta 2kg"
    assert len(data["storePrices"]) == 3


def test_superstores_search_produce_unit_quantity() -> None:
    _SEARCH_CACHE.clear()
    response = client.get("/api/v1/superstores/search?q=mango")
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "mango"
    assert data["bestPriceStore"] == "Meena Bazar"
    assert data["bestPriceBDT"] == 250.0
    for item in data["storePrices"]:
        assert item["unitQuantity"] == "1 kg"


def test_superstores_search_with_explicit_unit_param() -> None:
    _SEARCH_CACHE.clear()
    response = client.get("/api/v1/superstores/search?q=Mango&unit=2kg")
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "Mango"
    assert data["unit"] == "2 kg"
    assert data["bestPriceStore"] == "Meena Bazar"
    assert data["bestPriceBDT"] == 500.0  # 250 * 2
    for item in data["storePrices"]:
        assert item["unitQuantity"] == "2 kg"


def test_superstores_search_grams_scaling() -> None:
    _SEARCH_CACHE.clear()
    response = client.get("/api/v1/superstores/search?q=Mango&unit=500gm")
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "Mango"
    assert data["unit"] == "500g"
    assert data["bestPriceStore"] == "Meena Bazar"
    assert data["bestPriceBDT"] == 125.0  # 250 * 0.5
    for item in data["storePrices"]:
        assert item["unitQuantity"] == "500g"


def test_superstores_search_500ml_oil() -> None:
    _SEARCH_CACHE.clear()
    response = client.get("/api/v1/superstores/search?q=500ml%20oil")
    assert response.status_code == 200
    data = response.json()
    assert data["unit"] == "500ml"
    assert data["bestPriceStore"] == "Meena Bazar"
    assert data["bestPriceBDT"] == 87.5  # 175 * 0.5
    for item in data["storePrices"]:
        assert item["unitQuantity"] == "500ml"


def test_superstores_search_incompatible_unit_message() -> None:
    _SEARCH_CACHE.clear()
    response = client.get("/api/v1/superstores/search?q=rice&unit=500ml")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] is not None
    assert "not available in requested unit" in data["message"]
    for item in data["storePrices"]:
        assert item["isAvailable"] is False
        assert item["stockStatus"] == "out_of_stock"


def test_superstores_search_various_item_categories() -> None:
    _SEARCH_CACHE.clear()
    # Test Beef 2kg
    res_beef = client.get("/api/v1/superstores/search?q=2kg%20beef")
    assert res_beef.status_code == 200
    data_beef = res_beef.json()
    assert data_beef["unit"] == "2 kg"
    assert data_beef["bestPriceBDT"] == 1560.0  # 780 * 2

    # Test Milk 500ml
    res_milk = client.get("/api/v1/superstores/search?q=500ml%20milk")
    assert res_milk.status_code == 200
    data_milk = res_milk.json()
    assert data_milk["unit"] == "500ml"
    assert data_milk["bestPriceBDT"] == 45.0  # 90 * 0.5


def test_superstores_search_bengali_and_fraction_corner_cases() -> None:
    _SEARCH_CACHE.clear()
    # Bengali search term: গরুর মাংস (Beef)
    query_bn = urllib.parse.quote("গরুর মাংস")
    res_bn = client.get(f"/api/v1/superstores/search?q={query_bn}")
    assert res_bn.status_code == 200
    data_bn = res_bn.json()
    assert data_bn["bestPriceBDT"] == 780.0
    assert data_bn["unit"] == "1 kg"

    # Fraction text: half kg chicken
    res_frac = client.get("/api/v1/superstores/search?q=half%20kg%20chicken")
    assert res_frac.status_code == 200
    data_frac = res_frac.json()
    assert data_frac["unit"] == "500g"
    assert data_frac["bestPriceBDT"] == 110.0  # 220 * 0.5

    # Zero quantity corner case: 0g rice
    res_zero = client.get("/api/v1/superstores/search?q=0g%20rice")
    assert res_zero.status_code == 200
    data_zero = res_zero.json()
    assert data_zero["message"] == "Requested quantity must be greater than 0."
    assert data_zero["storePrices"][0]["isAvailable"] is False


def test_superstores_search_missing_query() -> None:
    response = client.get("/api/v1/superstores/search")
    assert response.status_code == 422  # Unprocessable entity due to missing required query param


def test_superstores_search_caching() -> None:
    _SEARCH_CACHE.clear()
    res1 = client.get("/api/v1/superstores/search?q=Kataribhog%20Rice%205kg")
    assert res1.status_code == 200
    
    cache_key = "kataribhog rice 5kg"
    assert cache_key in _SEARCH_CACHE

    # Second call should return from cache
    res2 = client.get("/api/v1/superstores/search?q=Kataribhog%20Rice%205kg")
    assert res2.status_code == 200
    assert res2.json() == res1.json()


@patch("app.services.superstores.httpx.Client")
def test_superstores_search_timeout_fallback(mock_client_cls: MagicMock) -> None:
    import httpx
    _SEARCH_CACHE.clear()

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.get.side_effect = httpx.TimeoutException("Connection timed out")
    mock_client_cls.return_value = mock_client

    response = client.get("/api/v1/superstores/search?q=Unknown%20Product")
    assert response.status_code == 200
    data = response.json()
    assert len(data["storePrices"]) == 3


def test_basket_optimization_api_success() -> None:
    payload = {
        "familyId": "fam_12345",
        "items": [
            "Teer Soyabean Oil 5L",
            "Kataribhog Rice 5kg",
            "Eggs 12 pcs",
            "Aarong Butter 200g",
        ],
    }
    response = client.post("/api/v1/superstores/basket-optimization", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["familyId"] == "fam_12345"
    assert data["totalItemsCount"] == 4
    assert data["cheapestStoreName"] == "Meena Bazar"
    assert data["cheapestTotalBDT"] is not None
    assert data["potentialSavingsBDT"] is not None
    assert len(data["storeTotals"]) == 3


def test_basket_optimization_api_empty_items() -> None:
    payload = {
        "familyId": "fam_12345",
        "items": [],
    }
    response = client.post("/api/v1/superstores/basket-optimization", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "Items list cannot be empty."


def test_basket_split_optimization_api_success() -> None:
    payload = {
        "familyId": "fam_12345",
        "items": [
            "Teer Soyabean Oil 5L",
            "Kataribhog Rice 5kg",
            "Eggs 12 pcs",
            "Aarong Butter 200g",
        ],
    }
    response = client.post(
        "/api/v1/superstores/basket-split-optimization", json=payload
    )
    assert response.status_code == 200
    data = response.json()
    assert data["familyId"] == "fam_12345"
    assert data["totalItemsCount"] == 4
    assert data["singleStoreCheapestName"] == "Meena Bazar"
    assert data["splitStoreTotalBDT"] is not None
    assert len(data["splitStrategy"]) > 0


def test_price_alerts_crud_flow() -> None:
    # 1. Create price alert
    create_payload = {
        "familyId": "fam_12345",
        "query": "Soyabean Oil 5L",
        "targetPriceBDT": 900.0,
        "unit": "5L",
    }
    res_create = client.post("/api/v1/superstores/price-alerts", json=create_payload)
    assert res_create.status_code == 200
    data_create = res_create.json()
    alert_id = data_create["alertId"]
    assert data_create["familyId"] == "fam_12345"
    assert data_create["query"] == "Soyabean Oil 5L"
    assert data_create["isTriggered"] is True  # Best price is 875.0 <= 900.0

    # 2. List price alerts
    res_list = client.get("/api/v1/superstores/price-alerts?family_id=fam_12345")
    assert res_list.status_code == 200
    data_list = res_list.json()
    assert len(data_list) >= 1
    assert any(a["alertId"] == alert_id for a in data_list)

    # 3. Check price alerts
    res_check = client.get("/api/v1/superstores/price-alerts/check?family_id=fam_12345")
    assert res_check.status_code == 200
    data_check = res_check.json()
    assert len(data_check) >= 1

    # 4. Delete price alert
    res_del = client.delete(f"/api/v1/superstores/price-alerts/{alert_id}")
    assert res_del.status_code == 200
    assert "deleted successfully" in res_del.json()["message"]

    # 5. Delete non-existent alert
    res_del_404 = client.delete("/api/v1/superstores/price-alerts/non_existent_id")
    assert res_del_404.status_code == 404


def test_sync_catalog_api() -> None:
    with patch("app.api.routes.superstores.sync_store_catalog_to_firestore") as mock_sync:
        mock_sync.return_value = {
            "status": "success",
            "syncedItemsCount": 10,
            "syncedQueriesCount": 3,
            "lastSyncedAt": "2026-07-28T12:00:00Z",
            "message": "Successfully synced 10 real product items",
        }
        res = client.post("/api/v1/superstores/sync-catalog")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["syncedItemsCount"] == 10


