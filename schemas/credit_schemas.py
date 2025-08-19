from typing import Optional

from pydantic import BaseModel

from common.enums import LoanType


class CombinedLoanConfigCreate(BaseModel):
    label: str = None
    min_score: int = None
    max_score: int = None
    rate_percentage: float
    loan_type: LoanType


class CombinedLoanConfigUpdate(BaseModel):
    label: Optional[str] = None
    min_score: Optional[int] = None
    max_score: Optional[int] = None
    rate_percentage: Optional[float] = None
    is_deleted: Optional[bool] = None


class ProcessingFeeCreate(BaseModel):
    label: str = None
    min_score: int = None
    max_score: int = None
    min_fee_percent: float
    max_fee_percent: Optional[float] = None

class ProcessingFeeUpdate(BaseModel):
    label: Optional[str] = None
    min_score: Optional[int] = None
    max_score: Optional[int] = None
    min_fee_percent: Optional[float] = None
    max_fee_percent: Optional[float] = None
    is_deleted: Optional[bool] = None

