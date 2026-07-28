from fastapi import APIRouter

from app.api.routes import ai, family, grocery, health, notification, superstores, user

api_router = APIRouter()
api_router.include_router(health.router)

# Routes registered with /v1 prefix
api_router.include_router(user.router, prefix="/v1", tags=["user"])
api_router.include_router(family.router, prefix="/v1", tags=["family"])
api_router.include_router(grocery.router, prefix="/v1", tags=["grocery"])
api_router.include_router(notification.router, prefix="/v1", tags=["notifications"])
api_router.include_router(superstores.router, prefix="/v1", tags=["superstores"])
api_router.include_router(ai.router, prefix="/v1", tags=["ai"])

# Also support /api/v1 prefix mapping as specified in endpoint docs
api_router.include_router(superstores.router, prefix="/api/v1", tags=["superstores"])
api_router.include_router(ai.router, prefix="/api/v1", tags=["ai"])

