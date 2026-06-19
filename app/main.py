import logging
import sys
import logging
import sys
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_resume import router as resume_router
from app.core.config import get_settings
from app.core.database import close_database, initialize_database

# Ensure logs are always emitted to stdout so they appear in deployment logs
# regardless of how the process is launched.
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
    force=True,
)

logger = logging.getLogger(__name__)

# Ensure logs are always emitted to stdout so they appear in deployment logs
# regardless of how the process is launched.
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
    force=True,
)

logger = logging.getLogger(__name__)

# Configure logging with explicit handler
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)
logger.info("Application starting up - logging configured")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("lifespan: startup sequence beginning")
    try:
        settings = get_settings()
        logger.info(
            "lifespan: settings loaded — app_name=%r llm_provider=%r "
            "mongodb_uri_set=%s",
            settings.app_name,
            settings.llm_provider,
            bool(settings.mongodb_uri),
        )

        await initialize_database()
        logger.info("lifespan: database initialisation complete")

        logger.info("lifespan: startup complete — yielding to application")
        yield
    except Exception:
        logger.critical(
            "lifespan: unhandled exception during startup:\n%s",
            traceback.format_exc(),
        )
        raise
    finally:
        logger.info("lifespan: shutdown sequence beginning")
        close_database()
        logger.info("lifespan: shutdown complete")


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resume_router)


@app.get("/", tags=["system"])
async def root() -> JSONResponse:
    """Minimal liveness check — confirms the app is running and reachable."""
    return JSONResponse({"status": "ok", "service": settings.app_name})


@app.get("/health", tags=["system"])
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "service": settings.app_name})
