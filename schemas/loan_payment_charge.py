from typing import Optional

from pydantic import BaseModel

from common.enums import ChargeStatus


class ChargeCreate(BaseModel):
    status: ChargeStatus
    amount: float


class ChargeUpdate(BaseModel):
    status: ChargeStatus
    amount: float
    is_deleted: Optional[bool] = None
