from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, model_validator
from enum import Enum


class PaymentStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CREATED = "created"


class PaymentDetailsCreateSchema(BaseModel):
    foreclosure_id: Optional[int] = Field(
        None, gt=0, description="ID of the associated foreclosure"
    )
    prepayment_id: Optional[int] = Field(
        None, gt=0, description="ID of the associated prepayment"
    )
    payment_id: str = Field(..., description="Unique payment identifier")
    amount: float = Field(..., gt=0, description="Payment amount in INR")
    currency: str = Field(default="INR", description="Currency code")
    status: PaymentStatus = Field(..., description="Payment status")
    payment_method: Optional[str] = Field(
        None, description="Payment method used"
    )

    class Config:
        from_attributes = True
        use_enum_values = True

    @model_validator(mode="after")
    def check_foreclosure_or_prepayment(self):
        if not self.foreclosure_id and not self.prepayment_id:
            raise ValueError("Either foreclosure_id or prepayment_id must be provided.")
        return self


class PaymentDetailsUpdateSchema(BaseModel):
    amount: Optional[float] = Field(
        None, gt=0, description="Payment amount in INR"
    )
    currency: Optional[str] = Field(None, description="Currency code")
    status: Optional[PaymentStatus] = Field(None, description="Payment status")
    payment_method: Optional[str] = Field(
        None, description="Payment method used"
    )

    class Config:
        from_attributes = True
        use_enum_values = True


class PaymentDetailsResponseSchema(BaseModel):
    id: int = Field(..., description="Payment details ID")
    foreclosure_id: Optional[int] = Field(
        None, description="ID of the associated foreclosure"
    )
    prepayment_id: Optional[int] = Field(
        None, description="ID of the associated prepayment"
    )
    payment_id: str = Field(..., description="Unique payment identifier")
    amount: float = Field(..., description="Payment amount in INR")
    currency: str = Field(..., description="Currency code")
    status: PaymentStatus = Field(..., description="Payment status")
    payment_method: Optional[str] = Field(
        None, description="Payment method used"
    )
    created_at: datetime = Field(..., description="Payment creation timestamp")

    class Config:
        from_attributes = True
        use_enum_values = True
