from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from common.enums import InvoiceStatus


# Pydantic Schemas
class InvoiceCreateSchema(BaseModel):
    subscription_id: Optional[int] = None
    payment_detail_id: Optional[int] = None
    razorpay_invoice_id: str = Field(..., max_length=255)
    entity: Optional[str] = "invoice"
    amount: float
    currency: str = "INR"
    status: InvoiceStatus
    emi_number: int
    due_date: Optional[int] = None
    issued_at: Optional[int] = None
    paid_at: Optional[int] = None
    expired_at: Optional[int] = None
    short_url: Optional[str] = Field(None, max_length=255)
    customer_notify: bool = True
    notes: Optional[str] = None
    invoice_data: Optional[dict] = None
    invoice_type: str


class InvoiceUpdateSchema(BaseModel):
    subscription_id: Optional[int] = None
    payment_detail_id: Optional[int] = None
    razorpay_invoice_id: Optional[str] = Field(None, max_length=255)
    entity: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    status: Optional[InvoiceStatus] = None
    emi_number: Optional[int] = None
    due_date: Optional[int] = None
    issued_at: Optional[int] = None
    paid_at: Optional[int] = None
    expired_at: Optional[int] = None
    short_url: Optional[str] = Field(None, max_length=255)
    customer_notify: Optional[bool] = None
    notes: Optional[str] = None
    invoice_data: Optional[dict] = None
    invoice_type: str
    


class InvoiceResponseSchema(BaseModel):
    id: int
    subscription_id: Optional[int]
    payment_detail_id: Optional[int]
    razorpay_invoice_id: str
    entity: Optional[str]
    amount: float
    currency: str
    status: InvoiceStatus
    emi_number: int
    due_date: Optional[int]
    issued_at: Optional[int]
    paid_at: Optional[int]
    expired_at: Optional[int]
    short_url: Optional[str]
    customer_notify: bool
    notes: Optional[str]
    invoice_data: Optional[dict]
    created_at: datetime
    created_by: Optional[str]
    modified_at: Optional[datetime]
    modified_by: Optional[str]
    is_deleted: bool
    invoice_type: str
    

    class Config:
        from_attributes = True
