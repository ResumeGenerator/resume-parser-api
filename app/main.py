import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.routes_resume import router as resume_router
from app.core.config import get_settings
from app.core.database import close_database, initialize_database

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings()
    try:
        await initialize_database()
    except Exception as exc:
        logger.error("Unexpected error during database initialisation: %s", exc)
    try:
        yield
    finally:
        close_database()


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(resume_router)


@app.get("/health", tags=["system"])
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "service": settings.app_name})
