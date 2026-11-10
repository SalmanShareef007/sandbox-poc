import logging
from contextlib import asynccontextmanager
 
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
 
from app.api.router import api_router
from app.core.config import settings, validate_hosting_configuration
from app.db.database import check_database, initialize_database, is_production
from app.services.sandbox_service import SandboxError
 
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)
 
 
@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_hosting_configuration()
    if not is_production():
        initialize_database()
    check_database()
    if settings.APPLICATIONINSIGHTS_CONNECTION_STRING:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(connection_string=settings.APPLICATIONINSIGHTS_CONNECTION_STRING.get_secret_value())
    yield
 
 
app = FastAPI(
    title="Azure Sandbox Platform API",
    description="Backend API for managing Azure sandbox provisioning, approvals, budgets, and lifecycle operations.",
    version="1.0.0",
    docs_url="/docs" if not is_production() else None,
    redoc_url="/redoc" if not is_production() else None,
    openapi_url="/openapi.json" if not is_production() else None,
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
 