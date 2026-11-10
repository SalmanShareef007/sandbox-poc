
from pydantic import Field, field_validator

from app.schemas.sandbox_request import CamelModel, validate_budget_amount


class ApproveRequest(CamelModel):
    budget: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    comments: str | None = Field(default=None, max_length=1000)

    @field_validator("budget")
    @classmethod
    def budget_allowed(cls, value: float | None) -> float | None:
        return validate_budget_amount(value) if value is not None else None


class RejectRequest(CamelModel):
    reason: str = Field(min_length=10, max_length=1000)
