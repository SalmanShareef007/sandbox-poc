
from pydantic import Field

from app.schemas.sandbox_request import CamelModel


class ApproveRequest(CamelModel):
    budget: float | None = Field(default=None, gt=0, le=100000)
    comments: str | None = Field(default=None, max_length=1000)


class RejectRequest(CamelModel):
    reason: str = Field(min_length=10, max_length=1000)
