
from pydantic import Field, field_validator

from app.core.config import settings
from app.schemas.sandbox_request import CamelModel


class ExtensionCreate(CamelModel):
    extra_days: int
    reason: str = Field(min_length=10, max_length=1000)

    @field_validator("extra_days")
    @classmethod
    def extra_days_allowed(cls, value: int) -> int:
        if value not in settings.ALLOWED_EXTENSION_DAYS:
            raise ValueError("Extension must be 30 or 60 days.")
        return value
