
from datetime import date

from pydantic import Field, field_validator, model_validator

from app.core.config import settings
from app.schemas.sandbox_request import CamelModel


class ExtensionCreate(CamelModel):
    extra_days: int | None = None
    requested_expiry_date: date | None = None
    reason: str = Field(min_length=10, max_length=1000)

    @field_validator("extra_days")
    @classmethod
    def extra_days_allowed(cls, value: int | None) -> int | None:
        if value is not None and (value not in settings.ALLOWED_EXTENSION_DAYS or value > settings.MAX_EXTENSION_DAYS):
            raise ValueError("Select one of the configured extension durations.")
        return value

    @model_validator(mode="after")
    def extension_choice(self):
        if (self.extra_days is None) == (self.requested_expiry_date is None):
            raise ValueError("Provide either extra days or a requested expiry date.")
        return self
