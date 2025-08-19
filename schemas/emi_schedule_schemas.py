from datetime import date
from typing import Optional

from pydantic import BaseModel

from common.enums import LoanType


class EmiScheduleCreate(BaseModel):
    emi_schedule_loan_type: LoanType
    emi_schedule_date: str


class EmiScheduleUpdate(BaseModel):
    emi_schedule_date: str
    is_deleted: Optional[bool] = None
