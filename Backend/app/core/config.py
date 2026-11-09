from functools import lru_cache
from pathlib import Path
 
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
 
BACKEND_DIR = Path(__file__).resolve().parents[2]
 
 
class Settings(BaseSettings):
    # Application settings
    APP_NAME: str = "Azure Sandbox Platform API"
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True
 
    # Frontend origins allowed to call the API from the browser
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
 
    # Microsoft Entra ID
    ENTRA_TENANT_ID: str | None = None
    ENTRA_CLIENT_ID: str | None = None
    ENTRA_API_AUDIENCE: str | None = None
    ENTRA_CLIENT_SECRET: SecretStr | None = None
 
    # Microsoft Graph
    GRAPH_BASE_URL: str = "https://graph.microsoft.com/v1.0"
 
    # Azure Communication Services
    ACS_CONNECTION_STRING: SecretStr | None = None
    ACS_SENDER_ADDRESS: str | None = None
 
    # Database configuration (integration comes later)
    DATABASE_URL: SecretStr | None = None
 
    # Sandbox rules
    ADMIN_ROLE: str = "Sandboxadmin"
    ALLOWED_REGIONS: list[str] = ["East US", "West US 2", "West Europe", "Central India"]
    ALLOWED_SANDBOX_ROLES: list[str] = ["Contributor", "Owner"]
    ALLOWED_DURATIONS_DAYS: list[int] = [30, 60, 90]
    ALLOWED_EXTENSION_DAYS: list[int] = [30, 60]
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
    AZURE_SUBSCRIPTION_ID: str = "9dd38a25-a50b-4f30-be0c-ea1ac7b44bdb"
 
    # Service principal used by Terraform and az. When unset, the machine's
    # own `az login` is used instead.
    ARM_CLIENT_ID: str | None = None
    ARM_CLIENT_SECRET: SecretStr | None = None
    ARM_TENANT_ID: str | None = None
    AZURE_SP_CONFIG_DIRECTORY: str = str(BACKEND_DIR / ".azure-sp")
 
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