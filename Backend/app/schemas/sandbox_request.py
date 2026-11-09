
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from app.core.config import settings


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class SandboxRequestCreate(CamelModel):
    business_unit: str = Field(min_length=1, max_length=60)
    cost_center: str = Field(min_length=1, max_length=40)
    workload: str = Field(min_length=1, max_length=80)
    region: str
    role: str = "Contributor"
    description: str = Field(min_length=1, max_length=300)
    justification: str = Field(min_length=20, max_length=2000)
    budget: float = Field(gt=0, le=100000)
    duration_days: int

    @field_validator("region")
    @classmethod
    def region_allowed(cls, value: str) -> str:
        if value not in settings.ALLOWED_REGIONS:
            raise ValueError(f"Region must be one of: {', '.join(settings.ALLOWED_REGIONS)}")
        return value

    @field_validator("role")
    @classmethod
    def role_allowed(cls, value: str) -> str:
        if value not in settings.ALLOWED_SANDBOX_ROLES:
            raise ValueError(f"Role must be one of: {', '.join(settings.ALLOWED_SANDBOX_ROLES)}")
        return value

    @field_validator("duration_days")
    @classmethod
    def duration_allowed(cls, value: int) -> int:
        if value not in settings.ALLOWED_DURATIONS_DAYS:
            raise ValueError("Duration must be 30, 60 or 90 days.")
        return value
