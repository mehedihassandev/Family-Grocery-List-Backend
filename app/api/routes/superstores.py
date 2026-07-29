from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_current_user
from app.models.superstores import (
    BasketOptimizationRequest,
    BasketOptimizationResponse,
    PriceAlertCreateRequest,
    PriceAlertResponse,
    SplitBasketOptimizationResponse,
    SuperstoreSearchResponse,
    SuperstoreSyncResponse,
)
from app.services.scraper import sync_store_catalog_to_firestore
from app.services.superstores import (
    check_price_alerts,
    create_price_alert,
    delete_price_alert,
    list_price_alerts,
    optimize_basket_cost,
    optimize_split_basket_cost,
    search_superstore_prices,
)

router = APIRouter()


@router.get("/superstores/search", response_model=SuperstoreSearchResponse)
def search_superstores(
    q: Annotated[
        str, Query(..., description="Search term (e.g. Soyabean Oil, Mango)")
    ],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    unit: Annotated[
        str | None,
        Query(description="Optional unit quantity (e.g. 1kg, 2kg, 5L, 200g)"),
    ] = None,
) -> SuperstoreSearchResponse:
    """Superstore Price & Availability Search across Shwapno, Meena Bazar, and Agora."""
    if not q or not q.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query parameter 'q' is required.",
        )
    return search_superstore_prices(q.strip(), unit=unit.strip() if unit else None)


@router.post(
    "/superstores/basket-optimization", response_model=BasketOptimizationResponse
)
def basket_optimization(
    payload: BasketOptimizationRequest,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> BasketOptimizationResponse:
    """Single Superstore Basket Cost Optimizer."""
    if not payload.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Items list cannot be empty.",
        )
    return optimize_basket_cost(payload)


@router.post(
    "/superstores/basket-split-optimization",
    response_model=SplitBasketOptimizationResponse,
)
def basket_split_optimization(
    payload: BasketOptimizationRequest,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> SplitBasketOptimizationResponse:
    """Multi-Store Split Order Strategy Basket Cost Optimizer."""
    if not payload.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Items list cannot be empty.",
        )
    return optimize_split_basket_cost(payload)


@router.post("/superstores/price-alerts", response_model=PriceAlertResponse)
def create_alert(
    payload: PriceAlertCreateRequest,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> PriceAlertResponse:
    """Create a new price drop alert for a grocery item."""
    if not payload.query or not payload.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Field 'query' cannot be empty.",
        )
    if payload.targetPriceBDT <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Field 'targetPriceBDT' must be greater than 0.",
        )
    return create_price_alert(payload)


@router.get("/superstores/price-alerts", response_model=list[PriceAlertResponse])
def get_alerts(
    family_id: Annotated[
        str, Query(..., description="Target family ID to fetch alerts for")
    ],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> list[PriceAlertResponse]:
    """List active price drop alerts for a family."""
    if not family_id or not family_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query parameter 'family_id' is required.",
        )
    return list_price_alerts(family_id.strip())


@router.delete("/superstores/price-alerts/{alert_id}")
def remove_alert(
    alert_id: str,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    """Delete a price drop alert by ID."""
    success = delete_price_alert(alert_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Price alert with ID '{alert_id}' not found.",
        )
    return {"message": f"Price alert '{alert_id}' deleted successfully."}


@router.get("/superstores/price-alerts/check", response_model=list[PriceAlertResponse])
def trigger_alert_check(
    family_id: Annotated[
        str | None, Query(description="Optional family ID filter")
    ] = None,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)] = None,
) -> list[PriceAlertResponse]:
    """Check current market prices against active alerts and update triggered status."""
    return check_price_alerts(family_id.strip() if family_id else None)


@router.post("/superstores/sync-catalog", response_model=SuperstoreSyncResponse)
def trigger_catalog_sync(
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    queries: list[str] | None = None,
) -> SuperstoreSyncResponse:
    """Manually trigger background real catalog scraping and Firestore sync."""
    return sync_store_catalog_to_firestore(queries)

