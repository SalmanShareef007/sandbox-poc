from pydantic import Field, field_validator
from uuid import UUID

from app.schemas.sandbox_request import CamelModel


class SubscriptionUpdate(CamelModel):
    subscription_id: UUID


class BusinessUnitUpdate(CamelModel):
    name: str = Field(min_length=1, max_length=120)
    short_code: str = Field(min_length=1, max_length=12, pattern=r"^[a-z][a-z0-9]{0,11}$")
    cost_centers: list[str] = Field(default_factory=list, max_length=2000)
    active: bool = True

    @field_validator("short_code", mode="before")
    @classmethod
    def normalize_short_code(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("cost_centers")
    @classmethod
    def normalize_centers(cls, values: list[str]) -> list[str]:
        result = sorted({value.strip() for value in values if value.strip()})
        if any(len(value) > 80 for value in result):
            raise ValueError("Cost centres must not exceed 80 characters.")
        return result