import logging
import os
import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from google.api_core.exceptions import GoogleAPICallError
from google.auth.exceptions import DefaultCredentialsError

from app.api.router import api_router
from app.core.config import get_settings
from app.services.scraper import sync_store_catalog_to_firestore


class EndpointFilter(logging.Filter):
    def __init__(self, path: str):
        super().__init__()
        self.path = path

    def filter(self, record: logging.LogRecord) -> bool:
        return self.path not in record.getMessage()


# Filter out /health access logs from uvicorn
logging.getLogger("uvicorn.access").addFilter(EndpointFilter("/health"))

settings = get_settings()
scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if "pytest" not in sys.modules:
        try:
            # 1. Trigger immediate initial catalog pull on server startup
            scheduler.add_job(
                sync_store_catalog_to_firestore,
                id="initial_superstore_catalog_pull",
            )
            # 2. Schedule recurring catalog refresh every 6 hours
            scheduler.add_job(
                sync_store_catalog_to_firestore,
                "interval",
                hours=settings.superstore_cache_ttl_hours,
                id="superstore_catalog_sync",
                replace_existing=True,
            )
            scheduler.start()
        except Exception:
            pass
    yield
    if scheduler.running:
        scheduler.shutdown()


app = FastAPI(title=settings.data_api_title, lifespan=lifespan)

allowed_origins = settings.allowed_origin_list
if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router)


@app.exception_handler(DefaultCredentialsError)
def default_credentials_error_handler(
    request: Request, exc: DefaultCredentialsError
) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Firebase service account credentials are not configured on Render. "
            "Please set FIREBASE_SERVICE_ACCOUNT_JSON environment variable on Render."
        },
    )


@app.exception_handler(GoogleAPICallError)
def google_api_error_handler(
    request: Request, exc: GoogleAPICallError
) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": f"Firestore API Error: {exc.message}"},
    )


@app.exception_handler(ValueError)
def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    if "FIREBASE_SERVICE_ACCOUNT_JSON" in str(exc):
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc)},
        )
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )


@app.exception_handler(Exception)
def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": f"Backend Error ({type(exc).__name__}): {str(exc)}"},
    )



@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "service": settings.data_api_title}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "false").lower() == "true",
    )
