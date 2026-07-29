from pydantic import BaseModel, ConfigDict


class StorePriceItem(BaseModel):
    storeName: str
    storeUrl: str
    productTitle: str
    priceBDT: float
    originalPriceBDT: float | None = None
    unitQuantity: str | None = None
    isAvailable: bool
    stockStatus: str  # "in_stock" | "out_of_stock"
    isBestPrice: bool
    itemUrl: str
    lastUpdated: str
    message: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class SuperstoreSearchResponse(BaseModel):
    query: str
    unit: str | None = None
    bestPriceStore: str | None = None
    bestPriceBDT: float | None = None
    savingsAmountBDT: float | None = None
    message: str | None = None
    storePrices: list[StorePriceItem]

    model_config = ConfigDict(populate_by_name=True)


class BasketOptimizationRequest(BaseModel):
    familyId: str
    items: list[str]

    model_config = ConfigDict(populate_by_name=True)


class StoreTotalSummary(BaseModel):
    storeName: str
    totalBDT: float
    availableItemsCount: int
    missingItemsCount: int

    model_config = ConfigDict(populate_by_name=True)


class BasketOptimizationResponse(BaseModel):
    familyId: str
    totalItemsCount: int
    cheapestStoreName: str | None = None
    cheapestTotalBDT: float | None = None
    potentialSavingsBDT: float | None = None
    storeTotals: list[StoreTotalSummary]

    model_config = ConfigDict(populate_by_name=True)


class SplitStoreGroup(BaseModel):
    storeName: str
    storeUrl: str
    subtotalBDT: float
    items: list[StorePriceItem]

    model_config = ConfigDict(populate_by_name=True)


class StoreSplitItemAllocation(BaseModel):
    itemName: str
    bestStoreName: str
    priceBDT: float

    model_config = ConfigDict(populate_by_name=True)


class SplitBasketOptimizationResponse(BaseModel):
    familyId: str
    totalItemsCount: int
    singleStoreCheapestName: str | None = None
    singleStoreCheapestBDT: float | None = None
    splitStoreTotalBDT: float | None = None
    splitTotalBDT: float | None = None
    additionalSavingsBDT: float | None = None
    extraSplitSavingsBDT: float | None = None
    splitStrategy: list[SplitStoreGroup] = []
    itemAllocations: list[StoreSplitItemAllocation] = []
    storeBreakdown: dict[str, int] = {}

    model_config = ConfigDict(populate_by_name=True)


class PriceAlertCreateRequest(BaseModel):
    familyId: str
    query: str
    targetPriceBDT: float
    unit: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class PriceAlertResponse(BaseModel):
    id: str | None = None
    alertId: str
    familyId: str
    query: str
    unit: str | None = None
    targetPriceBDT: float
    currentBestPriceBDT: float | None = None
    currentBestStore: str | None = None
    isTriggered: bool
    createdAt: str
    lastCheckedAt: str
    message: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class SuperstoreCatalogDocument(BaseModel):
    id: str
    storeName: str
    storeUrl: str
    productTitle: str
    normalizedQuery: str
    priceBDT: float
    originalPriceBDT: float | None = None
    unitQuantity: str | None = None
    isAvailable: bool = True
    stockStatus: str = "in_stock"
    itemUrl: str
    lastUpdated: str

    model_config = ConfigDict(populate_by_name=True)


class SuperstoreSyncResponse(BaseModel):
    status: str
    syncedItemsCount: int
    syncedQueriesCount: int
    lastSyncedAt: str
    message: str

    model_config = ConfigDict(populate_by_name=True)

