from typing import Optional
from datetime import datetime

from pydantic import BaseModel

from common.enums import PaymentType


class LoanDisbursementForm(BaseModel):
    applicant_id: int
    payment_type: PaymentType
    payment_date: datetime
    transferred_amount: float
    remarks: Optional[str] = None
    bank_name: Optional[str] = None
    account_holder_name: Optional[str] = None
    account_number: Optional[str] = None
    ifsc_code: Optional[str] = None
    payment_file: Optional[str] = None
    cheque_number: Optional[str] = None
    upi_id: Optional[str] = None
    transaction_id: Optional[str] = None