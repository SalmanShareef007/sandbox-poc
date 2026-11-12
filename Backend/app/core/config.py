from functools import lru_cache
from pathlib import Path
from typing import Literal
 
from pydantic import EmailStr, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
 
BACKEND_DIR = Path(__file__).resolve().parents[2]
 
 
class Settings(BaseSettings):
    # Application settings
    APP_NAME: str = "Azure Sandbox Platform API"
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    APP_ENV: str = "development"
    RUNTIME_DIRECTORY: str = str(BACKEND_DIR / "data")
 
    # Frontend origins allowed to call the API from the browser
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
 
    # Microsoft Entra ID
    ENTRA_TENANT_ID: str | None = None
    ENTRA_CLIENT_ID: str | None = None
    ENTRA_API_AUDIENCE: str | None = None
    ENTRA_CLIENT_SECRET: SecretStr | None = None
    ENTRA_REQUIRED_SCOPE: str = "access_as_user"
    ENTRA_ALLOWED_CLIENT_IDS: list[str] = []
 
    # Microsoft Graph
    GRAPH_BASE_URL: str = "https://graph.microsoft.com/v1.0"
 
    # Azure Communication Services
    ACS_CONNECTION_STRING: SecretStr | None = None
    ACS_SENDER_ADDRESS: str | None = None
    ACS_ENDPOINT: str | None = None
    ADMIN_NOTIFICATION_EMAILS: list[EmailStr] = Field(default_factory=list, max_length=4)
    # Base URL of the web app, used for links in emails and chat alerts.
    FRONTEND_BASE_URL: str | None = None
    # Incoming webhook (Microsoft Teams Workflows or Slack) that receives admin notifications.
    ADMIN_WEBHOOK_URL: SecretStr | None = None
    BUDGET_ALERT_THRESHOLDS: list[float] = [75, 90, 100]
    COST_MANAGEMENT_ENABLED: bool = True
    BUDGET_CURRENCY: str = Field(default="USD", pattern="^[A-Z]{3}$")
    MAX_SANDBOX_BUDGET: float = Field(default=500, gt=0, allow_inf_nan=False)
    BUSINESS_UNIT_CATALOG_REQUIRED: bool = True
    COST_CENTER_MODE: Literal["business_unit", "shared", "free_text"] = "business_unit"
    SHARED_COST_CENTERS: list[str] = []
    EXPIRY_GRACE_DAYS: int = Field(default=7, ge=0, le=365)
    ALLOW_OWNER_ROLE_REQUESTS: bool = True
    COST_REFRESH_SECONDS: int = 3600
    COST_REFRESH_BATCH_SIZE: int = 5
    WORKER_POLL_SECONDS: int = 5
    LIFECYCLE_INTERVAL_SECONDS: int = 300
    WORKER_HEARTBEAT_MAX_SECONDS: int = 120
    APPLICATIONINSIGHTS_CONNECTION_STRING: SecretStr | None = None
 
    DATABASE_URL: SecretStr | None = None
    DB_POOL_SIZE: int = Field(default=5, ge=1, le=50)
    DB_MAX_OVERFLOW: int = Field(default=10, ge=0, le=100)
    DB_POOL_TIMEOUT_SECONDS: int = Field(default=30, ge=1)
    DB_POOL_RECYCLE_SECONDS: int = Field(default=1800, ge=60)
    DB_CONNECT_TIMEOUT_SECONDS: int = Field(default=10, ge=1)
 
    # Sandbox rules
    ADMIN_ROLE: str = "Sandboxadmin"
    ALLOWED_REGIONS: list[str] = ["East US", "West US 2", "West Europe", "Central India"]
    ALLOWED_SANDBOX_ROLES: list[str] = ["Owner", "Contributor"]
    LEGACY_BUDGET_START_DATE: str | None = None
    ALLOWED_DURATIONS_DAYS: list[int] = [30, 60, 90]
    ALLOWED_EXTENSION_DAYS: list[int] = [30, 60]
    MAX_EXTENSION_DAYS: int = Field(default=60, ge=1, le=365)
    EXPIRING_THRESHOLD_DAYS: int = 7
 
    # Terraform configuration
    TERRAFORM_ENABLED: bool = True
    TERRAFORM_ENVIRONMENT: str = "dev"
    TERRAFORM_WORKING_DIRECTORY: str = str(
        BACKEND_DIR.parent / "Terraform" / "environments" / "dev"
    )
    TERRAFORM_BINARY: str = "terraform"
    AZ_CLI_BINARY: str = "az"
    TERRAFORM_TIMEOUT_SECONDS: int = 1800
    AZURE_SUBSCRIPTION_ID: str = ""
    TERRAFORM_STATE_RESOURCE_GROUP: str | None = None
    TERRAFORM_STATE_STORAGE_ACCOUNT: str | None = None
    TERRAFORM_STATE_CONTAINER: str | None = None
    TERRAFORM_STATE_KEY: str | None = None
    TERRAFORM_STATE_SUBSCRIPTION_ID: str | None = None
 
    # Service principal used by Terraform and az. When unset, the machine's
    # own `az login` is used instead.
    ARM_CLIENT_ID: str | None = None
    ARM_CLIENT_SECRET: SecretStr | None = None
    ARM_TENANT_ID: str | None = None
    ARM_USE_MSI: bool = False
    AZURE_SP_CONFIG_DIRECTORY: str | None = None

    @field_validator("BUDGET_ALERT_THRESHOLDS")
    @classmethod
    def valid_thresholds(cls, values: list[float]) -> list[float]:
        values = sorted(set(values))
        if not values or len(values) > 5 or any(not 0 < value <= 100 for value in values):
            raise ValueError("Configure between one and five budget thresholds above zero and at most 100.")
        return values
 
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
 
 
@lru_cache
def get_settings() -> Settings:
    return Settings()
 
 
settings = get_settings()


def validate_hosting_configuration() -> None:
    from app.db.database import is_production

    if not is_production():
        return
    if not settings.ENTRA_TENANT_ID or not settings.ENTRA_API_AUDIENCE or not settings.AZURE_SUBSCRIPTION_ID:
        raise RuntimeError("Production requires Entra tenant, API audience, and subscription settings.")
    if not settings.ENTRA_ALLOWED_CLIENT_IDS:
        raise RuntimeError("Set ENTRA_ALLOWED_CLIENT_IDS to the trusted SPA application IDs.")
    if not settings.CORS_ORIGINS or any(not origin.startswith("https://") for origin in settings.CORS_ORIGINS):
        raise RuntimeError("Production CORS origins must explicitly allow only HTTPS frontend URLs.")
    if not settings.TERRAFORM_ENABLED:
        raise RuntimeError("Terraform simulation cannot be enabled in production.")
    if not set(settings.ALLOWED_SANDBOX_ROLES).issubset({"Sandbox Contributor", "Contributor", "Owner"}):
        raise RuntimeError("Unsupported sandbox access role.")
    if "Owner" in settings.ALLOWED_SANDBOX_ROLES and not settings.ALLOW_OWNER_ROLE_REQUESTS:
        raise RuntimeError("Owner access must be explicitly enabled with ALLOW_OWNER_ROLE_REQUESTS.")
