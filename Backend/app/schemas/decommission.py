
from pydantic import Field

from app.schemas.sandbox_request import CamelModel


class DecommissionCreate(CamelModel):
    reason: str = Field(min_length=1, max_length=1000)
