from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class PrePaymentStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CREATED = "created"

class PrePaymentCreateSchema(BaseModel):
    subscription_id: int = Field(..., gt=0,
                                 description="ID of the associated subscription")
    amount: float = Field(..., gt=0, description="Foreclosure amount in INR")
    reason: Optional[str] = Field(None, description="Reason for foreclosure")
    status: PrePaymentStatus = Field(..., description="Foreclosure status")
    emi_stepper: int 

    class Config:
        from_attributes = True
        use_enum_values = True


class PrePaymentUpdateSchema(BaseModel):
    amount: Optional[float] = Field(
        None, gt=0, description="Foreclosure amount in INR")
    reason: Optional[str] = Field(None, description="Reason for foreclosure")
    status: Optional[PrePaymentStatus] = Field(
        None, description="Foreclosure status")

    class Config:
        from_attributes = True
        use_enum_values = True


class PrePaymentResponseSchema(BaseModel):
    id: int = Field(..., description="Foreclosure ID")
    subscription_id: int = Field(...,
                                 description="ID of the associated subscription")
    amount: float = Field(..., description="Foreclosure amount in INR")
    reason: Optional[str] = Field(None, description="Reason for foreclosure")
    status: PrePaymentStatus = Field(..., description="Foreclosure status")
    emi_stepper: int
    
    class Config:
        from_attributes = True
        use_enum_values = True

