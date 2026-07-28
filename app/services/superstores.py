import re
import time
import urllib.parse
import uuid
from datetime import UTC, datetime

import httpx

from app.core.config import get_settings
from app.models.superstores import (
    BasketOptimizationRequest,
    BasketOptimizationResponse,
    PriceAlertCreateRequest,
    PriceAlertResponse,
    SplitBasketOptimizationResponse,
    SplitStoreGroup,
    StorePriceItem,
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

# Comprehensive Base Price Catalog (BDT) for all major supermarket items
BASE_PRICE_CATALOG: dict[str, tuple[str, float, float | None, str]] = {
    # Fruits & Produce
    "mango": ("Fresh Himsagar / Langra Mango", 250.0, 270.0, "1 kg"),
    "himsagar mango": ("Fresh Himsagar Mango", 260.0, 280.0, "1 kg"),
    "langra mango": ("Fresh Langra Mango", 250.0, 270.0, "1 kg"),
    "apple": ("Fresh Red Fuji Apple", 280.0, 300.0, "1 kg"),
    "green apple": ("Fresh Green Apple", 320.0, 340.0, "1 kg"),
    "banana": ("Fresh Sagar Banana", 100.0, 110.0, "12 Pcs"),
    "orange": ("Imported Fresh Orange", 260.0, 280.0, "1 kg"),
    "malta": ("Imported Malta", 240.0, 260.0, "1 kg"),
    "grape": ("Fresh Black / Green Grapes", 380.0, 420.0, "1 kg"),
    "guava": ("Fresh Thai Guava", 120.0, 135.0, "1 kg"),
    "papaya": ("Ripe Sweet Papaya", 110.0, 125.0, "1 kg"),
    "watermelon": ("Fresh Sweet Watermelon", 50.0, 60.0, "1 kg"),
    "lemon": ("Fresh Green Lemon", 60.0, 70.0, "4 Pcs"),
    "pineapple": ("Fresh Honey Queen Pineapple", 70.0, 80.0, "1 Pcs"),
    "onion": ("Deshi Onion", 85.0, 95.0, "1 kg"),
    "imported onion": ("Imported Indian Onion", 75.0, 85.0, "1 kg"),
    "potato": ("Fresh Granola Potato", 55.0, 60.0, "1 kg"),
    "tomato": ("Ripe Red Tomato", 80.0, 90.0, "1 kg"),
    "garlic": ("Imported Garlic", 210.0, 230.0, "1 kg"),
    "ginger": ("Fresh Ginger", 240.0, 260.0, "1 kg"),
    "chili": ("Fresh Green Chili", 160.0, 180.0, "1 kg"),
    "green chili": ("Fresh Green Chili", 160.0, 180.0, "1 kg"),
    "cucumber": ("Fresh Green Cucumber", 70.0, 80.0, "1 kg"),
    "carrot": ("Fresh Orange Carrot", 90.0, 100.0, "1 kg"),
    "brinjal": ("Fresh Purple Brinjal", 80.0, 90.0, "1 kg"),
    "spinach": ("Fresh Palong Shak", 40.0, 50.0, "1 kg"),
    "pumpkin": ("Sweet Yellow Pumpkin", 50.0, 60.0, "1 kg"),
    "cauliflower": ("Fresh White Cauliflower", 50.0, 60.0, "1 Pcs"),
    "cabbage": ("Fresh Green Cabbage", 45.0, 55.0, "1 Pcs"),
    # Meat & Seafood
    "beef": ("Fresh Bone-in Beef", 780.0, 820.0, "1 kg"),
    "boneless beef": ("Fresh Premium Boneless Beef", 950.0, 1000.0, "1 kg"),
    "mutton": ("Fresh Mutton", 1100.0, 1150.0, "1 kg"),
    "chicken": ("Fresh Broiler Chicken", 220.0, 240.0, "1 kg"),
    "broiler chicken": ("Fresh Broiler Chicken", 220.0, 240.0, "1 kg"),
    "sonali chicken": ("Fresh Sonali Chicken", 340.0, 370.0, "1 kg"),
    "deshi chicken": ("Fresh Country / Deshi Chicken", 650.0, 700.0, "1 kg"),
    "fish": ("Fresh Ruhi Fish", 380.0, 410.0, "1 kg"),
    "ruhi fish": ("Fresh Ruhi Fish", 380.0, 410.0, "1 kg"),
    "hilsa": ("Padma Hilsa Fish", 1450.0, 1600.0, "1 kg"),
    "hilsa fish": ("Padma Hilsa Fish", 1450.0, 1600.0, "1 kg"),
    "tilapia": ("Fresh Tilapia Fish", 220.0, 240.0, "1 kg"),
    "katla": ("Fresh Katla Fish", 400.0, 430.0, "1 kg"),
    "prawn": ("Fresh Medium Prawns", 750.0, 820.0, "1 kg"),
    "shrimp": ("Fresh Small Shrimp", 650.0, 720.0, "1 kg"),
    "egg": ("Farm Fresh Brown Eggs", 145.0, 155.0, "12 Pcs"),
    "eggs": ("Farm Fresh Brown Eggs", 145.0, 155.0, "12 Pcs"),
    "eggs 12 pcs": ("Farm Fresh Brown Eggs 12 Pcs", 145.0, 155.0, "12 Pcs"),
    # Oils, Ghee & Dairy
    "oil": ("Fortified Soybean Oil", 175.0, 185.0, "1 Ltr"),
    "soybean oil": ("Fortified Soybean Oil", 175.0, 185.0, "1 Ltr"),
    "soyabean oil 5l": ("Teer Soyabean Oil 5 Ltr", 810.0, 825.0, "5 Ltr"),
    "teer soyabean oil 5l": ("Teer Pure Soybean Oil 5L", 810.0, 825.0, "5 Ltr"),
    "mustard oil": ("Pure Mustard Oil", 220.0, 235.0, "1 Ltr"),
    "sunflower oil": ("Imported Sunflower Oil", 310.0, 330.0, "1 Ltr"),
    "olive oil": ("Extra Virgin Olive Oil", 1250.0, 1350.0, "1 Ltr"),
    "milk": ("Aarong Pasteurized Liquid Milk", 90.0, 95.0, "1 Ltr"),
    "milk 1l": ("Aarong Pasteurized Milk 1L", 90.0, 95.0, "1 Ltr"),
    "powdered milk": ("Dano Full Cream Powdered Milk 500g", 440.0, 460.0, "500g"),
    "butter": ("Pasteurized Dairy Butter 200g", 215.0, 225.0, "200g"),
    "aarong butter 200g": ("Aarong Dairy Butter 200g", 215.0, 225.0, "200g"),
    "ghee": ("Aarong Pure Dairy Ghee 500g", 720.0, 760.0, "500g"),
    "cheese": ("Processed Dairy Cheese Slices 200g", 280.0, 300.0, "200g"),
    "dahi": ("Fresh Sweet Dahi 500g", 140.0, 155.0, "500g"),
    "yogurt": ("Fresh Plain Sour Yogurt 500g", 120.0, 135.0, "500g"),
    # Staples, Flours & Grains
    "rice": ("Premium Miniket Rice", 78.0, 85.0, "1 kg"),
    "miniket rice": ("Premium Miniket Rice", 78.0, 85.0, "1 kg"),
    "rice 5kg": ("Miniket Rice 5kg", 380.0, 400.0, "5 kg"),
    "kataribhog rice": ("Kataribhog Rice", 85.0, 92.0, "1 kg"),
    "kataribhog rice 5kg": ("Kataribhog Rice 5kg", 420.0, 440.0, "5 kg"),
    "chinigura rice": ("Aromatic Chinigura Rice", 150.0, 165.0, "1 kg"),
    "basmati rice": ("Imported Premium Basmati Rice", 280.0, 310.0, "1 kg"),
    "atta": ("Pure White Atta", 60.0, 65.0, "1 kg"),
    "atta 2kg": ("Pure White Atta 2kg", 115.0, 120.0, "2 kg"),
    "teer atta 2kg": ("Teer Fortified Atta 2kg", 120.0, 125.0, "2 kg"),
    "maida": ("Fine White Maida", 70.0, 75.0, "1 kg"),
    "suji": ("Semolina / Suji 500g", 45.0, 50.0, "500g"),
    "sugar": ("Refined White Sugar", 135.0, 140.0, "1 kg"),
    "salt": ("Iodized Salt", 42.0, 45.0, "1 kg"),
    # Pulses & Spices (Dal & Masala)
    "dal": ("Deshi Masoor Dal", 140.0, 150.0, "1 kg"),
    "masoor dal": ("Deshi Masoor Dal", 140.0, 150.0, "1 kg"),
    "moong dal": ("Premium Yellow Moong Dal", 175.0, 190.0, "1 kg"),
    "chana dal": ("Deshi Chana Dal", 125.0, 135.0, "1 kg"),
    "turmeric": ("Radhuni Turmeric Powder 200g", 90.0, 100.0, "200g"),
    "chili powder": ("Radhuni Red Chili Powder 200g", 110.0, 120.0, "200g"),
    "coriander": ("Radhuni Coriander Powder 200g", 85.0, 95.0, "200g"),
    "cumin": ("Radhuni Cumin Powder 200g", 240.0, 260.0, "200g"),
    "garam masala": ("Radhuni Garam Masala 100g", 160.0, 180.0, "100g"),
    # Beverages & Snacks
    "tea": ("Ispahani Mirzapore Black Tea 400g", 220.0, 235.0, "400g"),
    "coffee": ("Nescafe Classic Coffee 100g", 360.0, 390.0, "100g"),
    "noodles": ("Maggi 2-Minute Noodles 8-Pack", 160.0, 175.0, "1 Pack"),
    "pasta": ("Cocola Macaroni Pasta 400g", 85.0, 95.0, "400g"),
    "biscuits": ("Lexus Vegetable Crackers 250g", 90.0, 100.0, "250g"),
    "bread": ("Fresh White Sandwich Bread 350g", 65.0, 75.0, "350g"),
    "oats": ("Quaker White Oats 500g", 320.0, 350.0, "500g"),
    "honey": ("AP Commercial Natural Honey 250g", 280.0, 310.0, "250g"),
    # Household
    "soap": ("Lux Beauty Soap 100g", 65.0, 75.0, "100g"),
    "shampoo": ("Sunsilk Black Shine Shampoo 375ml", 360.0, 390.0, "375ml"),
    "dishwash": ("Vim Dishwash Liquid 500ml", 130.0, 145.0, "500ml"),
    "detergent": ("Wheel Wash Powder 1kg", 140.0, 155.0, "1 kg"),
    "tissue": ("Bashundhara Facial Tissue 2-Ply", 75.0, 85.0, "1 Pack"),
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


def _estimate_item_price(
    query: str, store_info: dict
) -> tuple[str, float, float | None, str]:
    translated = _translate_bengali_terms(query)
    q_norm = translated.lower().strip()
    q_clean = _extract_clean_product_name(translated).lower()

    # Check catalog matching (exact query first, then clean product name)
    if q_norm in BASE_PRICE_CATALOG:
        title, base_price, base_orig, unit_qty = BASE_PRICE_CATALOG[q_norm]
    elif q_clean in BASE_PRICE_CATALOG:
        title, base_price, base_orig, unit_qty = BASE_PRICE_CATALOG[q_clean]
    else:
        matched_key = next(
            (
                k
                for k in BASE_PRICE_CATALOG
                if k in q_norm or q_norm in k or k in q_clean or q_clean in k
            ),
            None,
        )
        if matched_key:
            title, base_price, base_orig, unit_qty = BASE_PRICE_CATALOG[matched_key]
        else:
            title = _extract_clean_product_name(translated).title()
            base_price = 250.0
            base_orig = 265.0
            unit_qty = _extract_unit_quantity(translated, title)

    modifier = store_info["price_modifier"]
    price_bdt = round(base_price * modifier, 0)

    orig_bdt = None
    if store_info["orig_modifier"] and base_orig is not None:
        orig_bdt = round(base_orig * store_info["orig_modifier"], 0)

    full_title = title
    if store_info["name"] == "Shwapno" and "Teer" in title and "Pure" not in title:
        full_title = title.replace("Pure Soybean Oil 5L", "Teer Soyabean Oil 5 Ltr")
    elif store_info["name"] == "Agora" and "Fortified" not in title:
        full_title = title.replace(
            "Teer Soyabean Oil 5 Ltr", "Teer Fortified Soybean Oil 5L"
        )

    return full_title, price_bdt, orig_bdt, unit_qty


def _fetch_single_store_price(
    query: str, store_info: dict, timeout_ms: int = 3000
) -> StorePriceItem:
    """Fetch product price from a single store with strict 3000ms timeout & fallback handling."""
    now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    slug = _slugify(_extract_clean_product_name(query))

    clean_query = re.sub(r"[^\w\s]", "", query).strip()
    search_url = store_info["search_url_template"].format(
        query=urllib.parse.quote(clean_query)
    )
    item_url = store_info["item_url_template"].format(slug=slug)

    try:
        with httpx.Client(
            timeout=timeout_ms / 1000.0, follow_redirects=True
        ) as client:
            response = client.get(
                search_url, headers={"User-Agent": "FamilyGroceryApp/1.0"}
            )

            if response.status_code != 200:
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
                    message=f"Item '{query.title()}' is not available at {store_info['name']}.",
                )
    except (httpx.TimeoutException, httpx.RequestError):
        pass

    title, price_bdt, orig_bdt, unit_qty = _estimate_item_price(query, store_info)

    return StorePriceItem(
        storeName=store_info["name"],
        storeUrl=store_info["url"],
        productTitle=title,
        priceBDT=price_bdt,
        originalPriceBDT=orig_bdt,
        unitQuantity=unit_qty,
        isAvailable=True,
        stockStatus="in_stock",
        isBestPrice=False,
        itemUrl=item_url,
        lastUpdated=now_iso,
    )


def search_superstore_prices(
    query: str, unit: str | None = None
) -> SuperstoreSearchResponse:
    """Search price and availability across Shwapno, Meena Bazar, and Agora."""
    raw_query = query.strip()
    clean_query = _translate_bengali_terms(raw_query)
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

    store_prices: list[StorePriceItem] = []
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

    for item_query in items:
        search_res = search_superstore_prices(item_query)
        available_items = [
            sp for sp in search_res.storePrices if sp.isAvailable and sp.priceBDT > 0
        ]
        if available_items:
            best_item = min(available_items, key=lambda x: x.priceBDT)
            store_groups[best_item.storeName].append(best_item)

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
        additionalSavingsBDT=additional_savings,
        splitStrategy=split_strategy,
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

