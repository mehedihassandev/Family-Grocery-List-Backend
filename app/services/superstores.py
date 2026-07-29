import re
import time
import urllib.parse
import uuid
from datetime import UTC, datetime

import httpx

from app.core.config import get_settings
from app.core.firebase import get_firestore_client
from app.services.scraper import register_frequent_search_query
from app.models.superstores import (
    BasketOptimizationRequest,
    BasketOptimizationResponse,
    PriceAlertCreateRequest,
    PriceAlertResponse,
    SplitBasketOptimizationResponse,
    SplitStoreGroup,
    StorePriceItem,
    StoreSplitItemAllocation,
    StoreTotalSummary,
    SuperstoreSearchResponse,
)

# Store Configuration with standard Bangladeshi retail e-commerce search query patterns
STORES = [
    {
        "name": "Shwapno",
        "url": "https://www.shwapno.com",
        "search_url_template": "https://www.shwapno.com/search?txtSearch={query}",
        "item_url_template": "https://www.shwapno.com/products/{slug}",
        "price_modifier": 1.016,  # Shwapno benchmark
        "orig_modifier": 1.036,
    },
    {
        "name": "Meena Bazar",
        "url": "https://meenabazaronline.com",
        "search_url_template": "https://meenabazaronline.com/search?q={query}",
        "item_url_template": "https://meenabazaronline.com/product/{slug}",
        "price_modifier": 1.000,  # Benchmark store for best pricing
        "orig_modifier": 1.018,
    },
    {
        "name": "Agora",
        "url": "https://agorasuperstores.com/home",
        "search_url_template": "https://agorasuperstores.com/search?q={query}",
        "item_url_template": "https://agorasuperstores.com/product/{slug}",
        "price_modifier": 1.024,  # Agora premium benchmark
        "orig_modifier": None,
    },
]

# Bengali Supermarket Search Term Synonyms Mapping
BENGALI_TERM_MAP: dict[str, str] = {
    "আম": "mango",
    "আপেল": "apple",
    "কলা": "banana",
    "কমলা": "orange",
    "পেঁয়াজ": "onion",
    "পেয়াজ": "onion",
    "আলু": "potato",
    "টমেটো": "tomato",
    "রসুন": "garlic",
    "আদা": "ginger",
    "গরু": "beef",
    "গরুর মাংস": "beef",
    "খাসি": "mutton",
    "খাসির মাংস": "mutton",
    "মুরগি": "chicken",
    "মুরগির মাংস": "chicken",
    "মাছ": "fish",
    "রুই মাছ": "ruhi fish",
    "ইলিশ": "hilsa",
    "তেল": "oil",
    "সয়াবিন তেল": "soybean oil",
    "সরষের তেল": "mustard oil",
    "দুধ": "milk",
    "মাখন": "butter",
    "ঘি": "ghee",
    "চাল": "rice",
    "আটা": "atta",
    "ময়দা": "maida",
    "ডিম": "egg",
    "চিনি": "sugar",
    "লবণ": "salt",
    "ডাল": "dal",
    "মসুর ডাল": "masoor dal",
}

# In-memory TTL Cache: { cache_key: (timestamp, SuperstoreSearchResponse) }
_SEARCH_CACHE: dict[str, tuple[float, SuperstoreSearchResponse]] = {}


def _get_cache_ttl_seconds() -> float:
    settings = get_settings()
    return float(settings.superstore_cache_ttl_hours * 3600)


def _translate_bengali_terms(text: str) -> str:
    """Translate Bengali supermarket terms into standard English product names."""
    res = text.strip()
    for bn_term, en_term in BENGALI_TERM_MAP.items():
        if bn_term in res:
            res = res.replace(bn_term, en_term)
    return res


def _normalize_fractional_words(text: str) -> str:
    """Convert verbal/text fractions like 'half kg', '1/2 kg' into standard unit strings."""
    t = text.lower()
    t = re.sub(
        r"\b(?:half\s*kg|হাফ\s*কেজি|1/2\s*kg|১/২\s*কেজি|half\s*kilo)\b", "500g", t
    )
    t = re.sub(
        r"\b(?:quarter\s*kg|১/৪\s*কেজি|1/4\s*kg|quarter\s*kilo)\b", "250g", t
    )
    t = re.sub(
        r"\b(?:half\s*(?:l|ltr|litre|liter)|হাফ\s*লিটার|1/2\s*(?:l|ltr))\b",
        "500ml",
        t,
    )
    return t


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    slug = re.sub(r"\s+", "-", cleaned)
    return urllib.parse.quote(slug.strip("-"))


def _extract_unit_quantity(query: str, title: str) -> str:
    """Extract standard unit quantity (e.g. '1 kg', '5 Ltr', '500ml') from text."""
    combined = _normalize_fractional_words(f"{query} {title}")

    # Explicit Liquid volume: 500ml, 5L, 5 Ltr, 5 Litre
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(l|ltr|litre|litres|ml)\b", combined, re.IGNORECASE
    )
    if match:
        val = match.group(1)
        unit_type = match.group(2).lower()
        if unit_type == "ml":
            return f"{val}ml"
        return f"{val} Ltr"

    # Explicit Weight: 5kg, 5 kg, 200g, 200 gm
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(kg|g|gm|gram|grams)\b", combined, re.IGNORECASE
    )
    if match:
        val = match.group(1)
        unit = match.group(2).lower()
        return f"{val} kg" if unit == "kg" else f"{val}g"

    # Explicit Count: 12 pcs, 12 pc, 12 count
    match = re.search(
        r"(\d+)\s*(?:pcs|pc|count|piece|pieces)\b", combined, re.IGNORECASE
    )
    if match:
        return f"{match.group(1)} Pcs"

    # Category-based default unit inference when no explicit digit is specified
    combined_lower = combined.lower()
    if any(
        k in combined_lower
        for k in [
            "oil",
            "milk",
            "juice",
            "water",
            "beverage",
            "liquid",
            "shampoo",
            "dishwash",
        ]
    ):
        return "1 Ltr" if "shampoo" not in combined_lower else "375ml"
    if any(k in combined_lower for k in ["egg", "eggs", "banana", "lemon"]):
        return "12 Pcs" if "lemon" not in combined_lower else "4 Pcs"
    if any(
        k in combined_lower
        for k in [
            "butter",
            "cheese",
            "ghee",
            "turmeric",
            "chili powder",
            "coriander",
            "cumin",
        ]
    ):
        return "200g"

    # Default for produce, fruit, vegetable, meat, fish, rice, dal, flour, sugar, etc.
    return "1 kg"


def _normalize_to_base_value(unit_str: str) -> tuple[float, str]:
    """Convert unit string into a normalized scalar value and dimension."""
    text = unit_str.strip().lower()

    # Liquid volume (base = ml)
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:l|ltr|litre|litres)\b", text)
    if match:
        return float(match.group(1)) * 1000.0, "volume"
    match = re.search(r"(\d+(?:\.\d+)?)\s*ml\b", text)
    if match:
        return float(match.group(1)), "volume"

    # Weight / Mass (base = grams)
    match = re.search(r"(\d+(?:\.\d+)?)\s*kg\b", text)
    if match:
        return float(match.group(1)) * 1000.0, "mass"
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:g|gm|gram|grams)\b", text)
    if match:
        return float(match.group(1)), "mass"

    # Count (base = pcs)
    if "dozen" in text:
        match = re.search(r"(\d+(?:\.\d+)?)", text)
        num = float(match.group(1)) if match else 1.0
        return num * 12.0, "count"
    match = re.search(r"(\d+)\s*(?:pcs|pc|count|piece|pieces)\b", text)
    if match:
        return float(match.group(1)), "count"

    # Fallback number parsing
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    num = float(match.group(1)) if match else 1.0
    return num, "unknown"


def _parse_quantity_ratio(target_unit: str, base_unit: str) -> float:
    """Calculate exact scaling ratio between requested target unit and baseline base unit."""
    val_target, dim_target = _normalize_to_base_value(target_unit)
    val_base, dim_base = _normalize_to_base_value(base_unit)

    if val_base > 0 and (
        dim_target == dim_base or dim_target == "unknown" or dim_base == "unknown"
    ):
        return val_target / val_base
    return 1.0


def _extract_clean_product_name(query: str) -> str:
    """Strip quantity/unit patterns and symbols from search query to leave clean product name."""
    translated = _translate_bengali_terms(query)
    fraction_normalized = _normalize_fractional_words(translated)
    cleaned = re.sub(
        r"(\d+(?:\.\d+)?)\s*(?:kg|g|gm|gram|grams|l|ltr|litre|litres|ml|pcs|pc|count|piece|pieces|dozen)\b",
        "",
        fraction_normalized,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"[^\w\s]", "", cleaned).strip()
    return cleaned if cleaned else translated.strip()




def _fetch_single_store_price(
    query: str, store_info: dict, timeout_ms: int = 3000
) -> StorePriceItem:
    """Return unavailable status when store product is absent from live database."""
    now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    slug = _slugify(_extract_clean_product_name(query))
    item_url = store_info["item_url_template"].format(slug=slug)

    return StorePriceItem(
        storeName=store_info["name"],
        storeUrl=store_info["url"],
        productTitle=f"{query.title()} (Unavailable)",
        priceBDT=0.0,
        originalPriceBDT=None,
        unitQuantity=_extract_unit_quantity(query, ""),
        isAvailable=False,
        stockStatus="out_of_stock",
        isBestPrice=False,
        itemUrl=item_url,
        lastUpdated=now_iso,
        message=f"Item '{query.title()}' is currently out of stock or unlisted at {store_info['name']}.",
    )



def _get_firestore_catalog_items(clean_query: str) -> list[StorePriceItem]:
    """Retrieve real scraped product prices from Firestore catalog if available."""
    try:
        db = get_firestore_client()
        clean_name = _extract_clean_product_name(clean_query).lower()
        candidate_terms = [clean_name, clean_query.lower()]
        for term in ["oil", "beef", "rice", "mango", "milk", "butter", "egg", "dal", "atta", "sugar", "salt", "mutton", "chicken", "fish"]:
            if term in clean_query.lower() and term not in candidate_terms:
                candidate_terms.append(term)

        items: list[StorePriceItem] = []
        seen_stores: set[str] = set()

        for term in candidate_terms:
            docs = (
                db.collection("superstore_catalog")
                .where("normalizedQuery", "==", term)
                .stream()
            )
            for doc in docs:
                data = doc.to_dict() or {}
                sname = data.get("storeName", "Superstore")
                if sname not in seen_stores:
                    seen_stores.add(sname)
                    items.append(
                        StorePriceItem(
                            storeName=sname,
                            storeUrl=data.get("storeUrl", ""),
                            productTitle=data.get("productTitle", clean_query.title()),
                            priceBDT=float(data.get("priceBDT", 0.0)),
                            originalPriceBDT=float(data["originalPriceBDT"])
                            if data.get("originalPriceBDT")
                            else None,
                            unitQuantity=data.get("unitQuantity", "1 kg"),
                            isAvailable=bool(data.get("isAvailable", True)),
                            stockStatus=data.get("stockStatus", "in_stock"),
                            isBestPrice=False,
                            itemUrl=data.get("itemUrl", ""),
                            lastUpdated=data.get(
                                "lastUpdated",
                                datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            ),
                        )
                    )
            if len(items) >= 3:
                break
        return items
    except Exception:
        return []



def search_superstore_prices(
    query: str, unit: str | None = None
) -> SuperstoreSearchResponse:
    """Search price and availability across Shwapno, Meena Bazar, Agora, and Chaldal."""
    raw_query = query.strip()
    clean_query = _translate_bengali_terms(raw_query)
    register_frequent_search_query(clean_query)
    clean_unit = unit.strip() if unit else None
    cache_key = (
        clean_query.lower()
        if not clean_unit
        else f"{clean_query.lower()}||{clean_unit.lower()}"
    )
    ttl = _get_cache_ttl_seconds()
    now_ts = time.time()

    if cache_key in _SEARCH_CACHE:
        cached_ts, cached_resp = _SEARCH_CACHE[cache_key]
        if now_ts - cached_ts < ttl:
            return cached_resp

    effective_query = clean_query
    if clean_unit and clean_unit.lower() not in clean_query.lower():
        effective_query = f"{clean_query} {clean_unit}"

    # First attempt: Check real scraped Firestore catalog
    store_prices: list[StorePriceItem] = _get_firestore_catalog_items(clean_query)

    # Fallback to estimated store prices if Firestore catalog has no data for query
    if not store_prices:
        for store_info in STORES:
            item = _fetch_single_store_price(effective_query, store_info)
            store_prices.append(item)


    # Determine requested target unit string
    target_unit_str = None
    if clean_unit:
        target_unit_str = _extract_unit_quantity("", clean_unit)
    elif re.search(
        r"(?:\d+\s*(?:kg|g|gm|l|ltr|ml|pcs|pc)|half\s*kg|half\s*ltr|1/2\s*kg|1/4\s*kg)\b",
        clean_query,
        re.IGNORECASE,
    ):
        target_unit_str = _extract_unit_quantity(clean_query, "")

    overall_message = None
    display_product_name = _extract_clean_product_name(clean_query).title()

    if target_unit_str:
        val_target, dim_target = _normalize_to_base_value(target_unit_str)

        # Check for zero or negative requested quantity corner case
        if val_target <= 0:
            for item in store_prices:
                item.isAvailable = False
                item.stockStatus = "out_of_stock"
                item.priceBDT = 0.0
                item.originalPriceBDT = None
                item.unitQuantity = target_unit_str
                item.message = "Requested quantity must be greater than 0."
            overall_message = "Requested quantity must be greater than 0."
        else:
            for item in store_prices:
                val_base, dim_base = _normalize_to_base_value(
                    item.unitQuantity or "1 kg"
                )

                # Check if requested unit dimension matches item dimension
                if (
                    dim_target != dim_base
                    and dim_target != "unknown"
                    and dim_base != "unknown"
                ):
                    item.isAvailable = False
                    item.stockStatus = "out_of_stock"
                    item.priceBDT = 0.0
                    item.originalPriceBDT = None
                    item.unitQuantity = target_unit_str
                    item.message = (
                        f"Item '{display_product_name}' is not available in "
                        f"requested unit ({target_unit_str})."
                    )
                else:
                    ratio = _parse_quantity_ratio(
                        target_unit_str, item.unitQuantity or "1 kg"
                    )
                    item.priceBDT = round(item.priceBDT * ratio, 2)
                    if item.originalPriceBDT:
                        item.originalPriceBDT = round(
                            item.originalPriceBDT * ratio, 2
                        )
                    item.unitQuantity = target_unit_str

    # Compute Best Price Store
    available_items = [item for item in store_prices if item.isAvailable]
    best_price_store = None
    best_price_bdt = None
    savings_amount_bdt = None

    if available_items:
        min_price = min(item.priceBDT for item in available_items)
        max_price = max(item.priceBDT for item in available_items)

        for item in store_prices:
            if item.isAvailable and item.priceBDT == min_price:
                item.isBestPrice = True
                if best_price_store is None:
                    best_price_store = item.storeName
                    best_price_bdt = item.priceBDT

        savings_amount_bdt = round(max_price - min_price, 2)
    else:
        if not overall_message:
            if target_unit_str:
                overall_message = (
                    f"Item '{display_product_name}' is not available in "
                    f"requested unit ({target_unit_str})."
                )
            else:
                overall_message = f"Item '{display_product_name}' is currently out of stock."

    response = SuperstoreSearchResponse(
        query=raw_query,
        unit=target_unit_str or (store_prices[0].unitQuantity if store_prices else None),
        bestPriceStore=best_price_store,
        bestPriceBDT=best_price_bdt,
        savingsAmountBDT=savings_amount_bdt,
        message=overall_message,
        storePrices=store_prices,
    )

    _SEARCH_CACHE[cache_key] = (now_ts, response)
    return response


def optimize_basket_cost(
    payload: BasketOptimizationRequest
) -> BasketOptimizationResponse:
    """Optimize overall grocery basket cost across targeted superstores."""
    items = payload.items
    total_items_count = len(items)

    store_map: dict[str, dict[str, float | int]] = {
        store["name"]: {"totalBDT": 0.0, "available": 0, "missing": 0}
        for store in STORES
    }

    for item_query in items:
        search_res = search_superstore_prices(item_query)
        for sp in search_res.storePrices:
            s_data = store_map[sp.storeName]
            if sp.isAvailable and sp.priceBDT > 0:
                s_data["totalBDT"] += sp.priceBDT
                s_data["available"] += 1
            else:
                s_data["missing"] += 1

    store_totals: list[StoreTotalSummary] = []
    for store_name, s_data in store_map.items():
        store_totals.append(
            StoreTotalSummary(
                storeName=store_name,
                totalBDT=round(s_data["totalBDT"], 2),
                availableItemsCount=int(s_data["available"]),
                missingItemsCount=int(s_data["missing"]),
            )
        )

    cheapest_store_name = None
    cheapest_total_bdt = None
    potential_savings_bdt = None

    valid_stores = [s for s in store_totals if s.availableItemsCount > 0]
    if valid_stores:
        max_available = max(s.availableItemsCount for s in valid_stores)
        fully_available_stores = [
            s for s in valid_stores if s.availableItemsCount == max_available
        ]

        cheapest_summary = min(fully_available_stores, key=lambda s: s.totalBDT)
        highest_summary = max(fully_available_stores, key=lambda s: s.totalBDT)

        cheapest_store_name = cheapest_summary.storeName
        cheapest_total_bdt = cheapest_summary.totalBDT
        potential_savings_bdt = round(
            highest_summary.totalBDT - cheapest_summary.totalBDT, 2
        )

    return BasketOptimizationResponse(
        familyId=payload.familyId,
        totalItemsCount=total_items_count,
        cheapestStoreName=cheapest_store_name,
        cheapestTotalBDT=cheapest_total_bdt,
        potentialSavingsBDT=potential_savings_bdt,
        storeTotals=store_totals,
    )


def optimize_split_basket_cost(
    payload: BasketOptimizationRequest,
) -> SplitBasketOptimizationResponse:
    """Calculate multi-store split allocation to maximize total savings across stores."""
    items = payload.items
    total_items_count = len(items)

    # First compute single-store cheapest benchmark
    single_res = optimize_basket_cost(payload)
    single_cheapest_name = single_res.cheapestStoreName
    single_cheapest_bdt = single_res.cheapestTotalBDT

    store_groups: dict[str, list[StorePriceItem]] = {
        store["name"]: [] for store in STORES
    }
    store_urls: dict[str, str] = {
        store["name"]: store["url"] for store in STORES
    }

    item_allocations: list[StoreSplitItemAllocation] = []
    store_breakdown: dict[str, int] = {store["name"]: 0 for store in STORES}

    for item_query in items:
        search_res = search_superstore_prices(item_query)
        available_items = [
            sp for sp in search_res.storePrices if sp.isAvailable and sp.priceBDT > 0
        ]
        if available_items:
            best_item = min(available_items, key=lambda x: x.priceBDT)
            store_groups[best_item.storeName].append(best_item)
            item_allocations.append(
                StoreSplitItemAllocation(
                    itemName=item_query,
                    bestStoreName=best_item.storeName,
                    priceBDT=best_item.priceBDT,
                )
            )
            store_breakdown[best_item.storeName] = (
                store_breakdown.get(best_item.storeName, 0) + 1
            )

    split_strategy: list[SplitStoreGroup] = []
    split_total = 0.0

    for store_name, group_items in store_groups.items():
        if group_items:
            subtotal = round(sum(i.priceBDT for i in group_items), 2)
            split_total += subtotal
            split_strategy.append(
                SplitStoreGroup(
                    storeName=store_name,
                    storeUrl=store_urls[store_name],
                    subtotalBDT=subtotal,
                    items=group_items,
                )
            )

    split_total = round(split_total, 2)
    additional_savings = None
    if single_cheapest_bdt is not None:
        additional_savings = max(
            0.0, round(single_cheapest_bdt - split_total, 2)
        )

    return SplitBasketOptimizationResponse(
        familyId=payload.familyId,
        totalItemsCount=total_items_count,
        singleStoreCheapestName=single_cheapest_name,
        singleStoreCheapestBDT=single_cheapest_bdt,
        splitStoreTotalBDT=split_total if split_strategy else None,
        splitTotalBDT=split_total if split_strategy else None,
        additionalSavingsBDT=additional_savings,
        extraSplitSavingsBDT=additional_savings,
        splitStrategy=split_strategy,
        itemAllocations=item_allocations,
        storeBreakdown=store_breakdown,
    )


# In-memory Price Alerts DB: { alert_id: alert_dict }
_PRICE_ALERTS: dict[str, dict] = {}


def create_price_alert(payload: PriceAlertCreateRequest) -> PriceAlertResponse:
    """Create a new price drop alert for a grocery item."""
    alert_id = f"alert_{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    search_res = search_superstore_prices(payload.query, payload.unit)
    best_price = search_res.bestPriceBDT
    best_store = search_res.bestPriceStore
    is_triggered = best_price is not None and best_price <= payload.targetPriceBDT

    alert_data = {
        "id": alert_id,
        "alertId": alert_id,
        "familyId": payload.familyId,
        "query": payload.query.strip(),
        "unit": payload.unit.strip() if payload.unit else None,
        "targetPriceBDT": float(payload.targetPriceBDT),
        "currentBestPriceBDT": best_price,
        "currentBestStore": best_store,
        "isTriggered": is_triggered,
        "createdAt": now_iso,
        "lastCheckedAt": now_iso,
        "message": (
            f"Price alert created. Target: {payload.targetPriceBDT} BDT. "
            f"Current best: {best_price} BDT at {best_store}."
        ),
    }

    _PRICE_ALERTS[alert_id] = alert_data
    return PriceAlertResponse(**alert_data)


def list_price_alerts(family_id: str) -> list[PriceAlertResponse]:
    """List active price drop alerts for a family."""
    alerts = [
        PriceAlertResponse(**data)
        for data in _PRICE_ALERTS.values()
        if data["familyId"] == family_id
    ]
    return alerts


def delete_price_alert(alert_id: str) -> bool:
    """Delete a price drop alert by ID."""
    if alert_id in _PRICE_ALERTS:
        del _PRICE_ALERTS[alert_id]
        return True
    return False


def check_price_alerts(family_id: str | None = None) -> list[PriceAlertResponse]:
    """Check current market prices against active alerts and update triggered status."""
    now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    updated_alerts: list[PriceAlertResponse] = []

    for _alert_id, alert_data in _PRICE_ALERTS.items():
        if family_id and alert_data["familyId"] != family_id:
            continue

        # Force fresh search by bypassing cache key check
        query = alert_data["query"]
        unit = alert_data["unit"]
        cache_key = query.lower() if not unit else f"{query.lower()}||{unit.lower()}"
        if cache_key in _SEARCH_CACHE:
            del _SEARCH_CACHE[cache_key]

        search_res = search_superstore_prices(query, unit)
        best_price = search_res.bestPriceBDT
        best_store = search_res.bestPriceStore

        is_triggered = (
            best_price is not None and best_price <= alert_data["targetPriceBDT"]
        )

        alert_data["currentBestPriceBDT"] = best_price
        alert_data["currentBestStore"] = best_store
        alert_data["isTriggered"] = is_triggered
        alert_data["lastCheckedAt"] = now_iso

        if is_triggered:
            alert_data["message"] = (
                f"ALERT TRIGGERED! {query.title()} is now available for "
                f"{best_price} BDT at {best_store} (Target: {alert_data['targetPriceBDT']} BDT)."
            )
        else:
            alert_data["message"] = (
                f"Current best: {best_price} BDT at {best_store}. "
                f"Target: {alert_data['targetPriceBDT']} BDT."
            )

        updated_alerts.append(PriceAlertResponse(**alert_data))

    return updated_alerts

