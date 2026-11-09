
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.services import sandbox_service
from app.services.sandbox_service import SandboxError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    imported = sandbox_service.import_existing_sandboxes()
    if imported:
        logger.info("Imported %s existing sandbox(es) from sandboxes.json", imported)

    sandbox_service.recover_jobs()
    yield


app = FastAPI(
    title="Azure Sandbox Platform API",
    description="Backend API for managing Azure sandbox provisioning, approvals, budgets, and lifecycle operations.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(api_router, prefix="/api/v1")


@app.exception_handler(SandboxError)
async def sandbox_error_handler(_: Request, exc: SandboxError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Azure Sandbox Platform API",
        "status": "running",
        "docs": "/docs",
    }
