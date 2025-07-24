from pydantic import BaseModel

from common.enums import LoanType


class CombinedLoanConfigCreate(BaseModel):
    label: str = None
    min_score: int = None
    max_score: int = None
    rate_percentage: float
    loan_type: LoanType
