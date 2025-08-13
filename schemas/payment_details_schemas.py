from datetime import datetime
from http.client import CREATED
from typing import Optional
from pydantic import BaseModel, Field, validator
from enum import Enum


class PaymentStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CREATED = "created"


class PaymentDetailsCreateSchema(BaseModel):
    foreclosure_id: int = Field(..., gt=0,
                                description="ID of the associated foreclosure")
    payment_id: str = Field(..., description="Unique payment identifier")
    amount: float = Field(..., gt=0, description="Payment amount in INR")
    currency: str = Field(default="INR", description="Currency code")
    status: PaymentStatus = Field(..., description="Payment status")
    payment_method: Optional[str] = Field(
        None, description="Payment method used")

    class Config:
        from_attributes = True
        use_enum_values = True

    @validator('status')
    def validate_status(cls, value):
        if value not in [e.value for e in PaymentStatus]:
            raise ValueError(
                f"Invalid status. Must be one of {[e.value for e in PaymentStatus]}")
        return value


class PaymentDetailsUpdateSchema(BaseModel):
    amount: Optional[float] = Field(
        None, gt=0, description="Payment amount in INR")
    currency: Optional[str] = Field(None, description="Currency code")
    status: Optional[PaymentStatus] = Field(None, description="Payment status")
    payment_method: Optional[str] = Field(
        None, description="Payment method used")

    class Config:
        from_attributes = True
        use_enum_values = True

    @validator('status', pre=True, allow_reuse=True)
    def validate_status(cls, value):
        if value is not None and value not in [e.value for e in PaymentStatus]:
            raise ValueError(
                f"Invalid status. Must be one of {[e.value for e in PaymentStatus]}")
        return value


class PaymentDetailsResponseSchema(BaseModel):
    id: int = Field(..., description="Payment details ID")
    foreclosure_id: int = Field(...,
                                description="ID of the associated foreclosure")
    payment_id: str = Field(..., description="Unique payment identifier")
    amount: float = Field(..., description="Payment amount in INR")
    currency: str = Field(..., description="Currency code")
    status: PaymentStatus = Field(..., description="Payment status")
    payment_method: Optional[str] = Field(
        None, description="Payment method used")
    created_at: datetime = Field(..., description="Payment creation timestamp")

    class Config:
        from_attributes = True
        use_enum_values = True

    @validator('status', pre=True, allow_reuse=True)
    def validate_status(cls, value):
        if value not in [e.value for e in PaymentStatus]:
            raise ValueError(
                f"Invalid status. Must be one of {[e.value for e in PaymentStatus]}")
        return value
