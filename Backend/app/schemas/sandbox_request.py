
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from pydantic.alias_generators import to_camel

from app.core.config import settings


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


def validate_budget_amount(value: float) -> float:
    if value > settings.MAX_SANDBOX_BUDGET:
        raise ValueError(f"Budget must not exceed {settings.MAX_SANDBOX_BUDGET:g} {settings.BUDGET_CURRENCY}.")
    return value


class SandboxRequestCreate(CamelModel):
    business_unit: str = Field(min_length=1, max_length=120)
    cost_center: str = Field(min_length=1, max_length=80)
    manager_email: EmailStr
    workload: str = Field(min_length=1, max_length=80)
    region: str
    role: str = "Contributor"
    description: str = Field(min_length=1, max_length=300)
    justification: str = Field(min_length=20, max_length=2000)
    budget: float = Field(gt=0, allow_inf_nan=False)
    duration_days: int

    @field_validator("budget")
    @classmethod
    def budget_allowed(cls, value: float) -> float:
        return validate_budget_amount(value)

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
        if value == "Owner" and not settings.ALLOW_OWNER_ROLE_REQUESTS:
            raise ValueError("Owner access has not been enabled by the platform administrator.")
        return value

    @field_validator("duration_days")
    @classmethod
    def duration_allowed(cls, value: int) -> int:
        if value not in settings.ALLOWED_DURATIONS_DAYS:
            raise ValueError("Duration must be 30, 60 or 90 days.")
        return value
