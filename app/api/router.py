from fastapi import APIRouter

from app.api.routes import grocery, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(grocery.router, prefix="/v1", tags=["grocery"])
