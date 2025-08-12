from datetime import datetime
from http.client import CREATED
from typing import Optional
from pydantic import BaseModel, Field, validator
from enum import Enum


class ForeClosureStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CREATED = "created"


class PaymentDetailsBaseSchema(BaseModel):
    payment_id: str = Field(..., description="Unique payment identifier")
    amount: float = Field(..., gt=0, description="Payment amount in INR")
    currency: str = Field(default="INR", description="Currency code")
    status: PaymentStatus = Field(..., description="Payment status")
    payment_method: Optional[str] = Field(
        None, description="Payment method used")

    class Config:
        from_attributes = True
        use_enum_values = True


class PaymentDetailsResponseSchema(PaymentDetailsBaseSchema):
    id: int = Field(..., description="Payment details ID")
    foreclosure_id: int = Field(..., description="Associated foreclosure ID")
    created_at: datetime = Field(..., description="Payment creation timestamp")


class ForeClosureCreateSchema(BaseModel):
    subscription_id: int = Field(..., gt=0,
                                 description="ID of the associated subscription")
    amount: float = Field(..., gt=0, description="Foreclosure amount in INR")
    reason: Optional[str] = Field(None, description="Reason for foreclosure")
    status: ForeClosureStatus = Field(..., description="Foreclosure status")

    class Config:
        from_attributes = True
        use_enum_values = True


class ForeClosureUpdateSchema(BaseModel):
    amount: Optional[float] = Field(
        None, gt=0, description="Foreclosure amount in INR")
    reason: Optional[str] = Field(None, description="Reason for foreclosure")
    status: Optional[ForeClosureStatus] = Field(
        None, description="Foreclosure status")

    class Config:
        from_attributes = True
        use_enum_values = True


class ForeClosureResponseSchema(BaseModel):
    id: int = Field(..., description="Foreclosure ID")
    subscription_id: int = Field(...,
                                 description="ID of the associated subscription")
    amount: float = Field(..., description="Foreclosure amount in INR")
    reason: Optional[str] = Field(None, description="Reason for foreclosure")
    status: ForeClosureStatus = Field(..., description="Foreclosure status")
    # created_at: datetime = Field(..., description="Foreclosure creation timestamp")
    # payment_details: Optional[PaymentDetailsResponseSchema] = Field(None, description="Associated payment details")

    class Config:
        from_attributes = True
        use_enum_values = True

    # @validator('status', pre=True)
    # def validate_status(cls, value):
    #     if value not in [e.value for e in ForeClosureStatus]:
    #         raise ValueError(f"Invalid status. Must be one of {[e.value for e in ForeClosureStatus]}")
    #     return value
