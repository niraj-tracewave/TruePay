from common.enums import SubscriptionStatus
from sqlalchemy import Column, Integer, Enum, String, Float, ForeignKey, DateTime, Text, Boolean, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from db_domains import CreateUpdateTime, CreateByUpdateBy


class Customer(CreateUpdateTime, CreateByUpdateBy):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    razorpay_customer_id = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    contact = Column(String, nullable=False)
    gstin = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    subscriptions = relationship("Subscription", back_populates="customer")


class Plan(CreateUpdateTime, CreateByUpdateBy):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    applicant_id = Column(Integer, ForeignKey(
        "loan_applicants.id"), nullable=False, index=True)
    razorpay_plan_id = Column(String, unique=True, nullable=False)
    entity = Column(String, nullable=True)
    period = Column(String, nullable=False)
    interval = Column(Integer, nullable=False)
    item_id = Column(String, nullable=True)
    item_name = Column(String, nullable=False)
    item_amount = Column(Integer, nullable=False)  # stored in paise
    item_currency = Column(String, default="INR")
    item_description = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    plan_data = Column(JSON, nullable=True)
    

    subscriptions = relationship("Subscription", back_populates="plan")
    applicant = relationship("LoanApplicant", back_populates="plans")


class Subscription(CreateUpdateTime, CreateByUpdateBy):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(Enum(SubscriptionStatus), nullable=False)
    razorpay_subscription_id = Column(String, unique=True, nullable=False)
    entity = Column(String, nullable=True)
    # created, active, completed, cancelled
    plan_id = Column(Integer, ForeignKey("plans.id"))
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    quantity = Column(Integer, nullable=True)
    total_count = Column(Integer, nullable=True)
    paid_count = Column(Integer, nullable=True)
    remaining_count = Column(Integer, nullable=True)
    start_at = Column(DateTime, nullable=True)
    end_at = Column(DateTime, nullable=True)
    charge_at = Column(DateTime, nullable=True)
    expire_by = Column(DateTime, nullable=True)
    customer_notify = Column(Boolean, default=True)
    offer_id = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    short_url = Column(String, nullable=True)
    has_scheduled_changes = Column(Boolean, default=False)
    change_scheduled_at = Column(DateTime, nullable=True)
    upcoming_invoice_id = Column(String, nullable=True)
    addons = Column(JSON, nullable=True)  # JSON string
    auth_attempts = Column(Integer, nullable=True)
    subscription_data = Column(JSON, nullable=True)
    

    customer = relationship("Customer", back_populates="subscriptions")
    plan = relationship("Plan", back_populates="subscriptions")
