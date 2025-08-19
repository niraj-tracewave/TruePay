from pydantic import BaseModel
from typing import Optional, List

class PlanItem(BaseModel):
    name: str
    amount: int  # in paise
    currency: str = "INR"
    description: Optional[str] = None  # Optional


class PlanNotes(BaseModel):
    notes_key_1: Optional[str] = None
    notes_key_2: Optional[str] = None


class CreatePlanSchema(BaseModel):
    period: str  # e.g., "weekly" or "monthly"
    interval: int
    item: PlanItem
    notes: Optional[PlanNotes] = None


class AddonItem(BaseModel):
    name: str
    amount: int
    currency: str = "INR"


class Addon(BaseModel):
    item: AddonItem


class Notes(BaseModel):
    notes_key_1: Optional[str] = None
    notes_key_2: Optional[str] = None


class CreateSubscriptionSchema(BaseModel):
    plan_id: str
    total_count: int
    quantity: Optional[int] = 1
    start_at: Optional[int] = None  # Unix timestamp
    expire_by: Optional[int] = None  # Unix timestamp
    customer_notify: Optional[int] = 1
    addons: Optional[List[Addon]] = None
    offer_id: Optional[str] = None
    notes: Optional[Notes] = None
