from fastapi import APIRouter

from app.api.routes import family, grocery, health, user

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(user.router, prefix="/v1", tags=["user"])
api_router.include_router(family.router, prefix="/v1", tags=["family"])
api_router.include_router(grocery.router, prefix="/v1", tags=["grocery"])
