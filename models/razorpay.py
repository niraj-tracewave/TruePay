from common.enums import SubscriptionStatus, InvoiceStatus
from sqlalchemy import Column, Integer, Enum, String, Float, ForeignKey, DateTime, Text, Boolean, JSON, BigInteger, CheckConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from db_domains import CreateUpdateTime, CreateByUpdateBy

from enum import Enum as PyEnum   # <-- Python Enum
from sqlalchemy import Enum       # <-- SQLAlchemy Enum

class InvoiceType(str, PyEnum):   # <-- Use PyEnum here
    FORECLOSURE = "foreclosure"
    PRE_PAYMENT = "pre_payment"
    EMI = "emi"

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
    start_at = Column(BigInteger, nullable=True)  # Store Unix timestamp
    end_at = Column(BigInteger, nullable=True)    # Store Unix timestamp
    charge_at = Column(BigInteger, nullable=True)  # Store Unix timestamp
    expire_by = Column(BigInteger, nullable=True)  # Store Unix timestamp
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
    foreclosures = relationship("ForeClosure", back_populates="subscription")
    prepayment = relationship("PrePayment", back_populates="subscription")
    invoices = relationship("Invoice", back_populates="subscription")
    
    

class ForeClosure(CreateUpdateTime, CreateByUpdateBy):
    __tablename__ = "foreclosures"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    amount = Column(Float, nullable=False)  # Amount in INR
    reason = Column(Text, nullable=True)
    status = Column(Enum("pending", "approved", "rejected", name="foreclosure_status"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    subscription = relationship("Subscription", back_populates="foreclosures")
    payment_details = relationship("PaymentDetails", back_populates="foreclosure", uselist=False)

class PrePayment(CreateUpdateTime, CreateByUpdateBy):
    __tablename__ = "prepayment"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    amount = Column(Float, nullable=False)  # Amount in INR
    reason = Column(Text, nullable=True)
    emi_stepper = Column(Integer)
    status = Column(Enum("pending", "approved", "rejected", name="prepayment_status"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_due_payment = Column(Boolean, default=False)

    subscription = relationship("Subscription", back_populates="prepayment")
    payment_details = relationship("PaymentDetails", back_populates="prepayment", uselist=False)
    
class PaymentDetails(CreateUpdateTime, CreateByUpdateBy):
    __tablename__ = "payment_details"

    id = Column(Integer, primary_key=True, index=True)
    foreclosure_id = Column(Integer, ForeignKey("foreclosures.id"), nullable=True)
    prepayment_id = Column(Integer, ForeignKey("prepayment.id"), nullable=True)
    payment_id = Column(String, unique=True, nullable=False)
    amount = Column(Float, nullable=False)  # Amount in INR
    currency = Column(String, default="INR")
    status = Column(Enum("created", "partially_paid", "paid", "expired", "cancelled", name="payment_status"), nullable=False)
    payment_method = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    foreclosure = relationship("ForeClosure", back_populates="payment_details")
    prepayment = relationship("PrePayment", back_populates="payment_details")
    invoices = relationship("Invoice", back_populates="payment_details")
    
    
    __table_args__ = (
        CheckConstraint(
            "(foreclosure_id IS NOT NULL) OR (prepayment_id IS NOT NULL)",
            name="check_foreclosure_or_prepayment_not_null"
        ),
        CheckConstraint(
            "NOT (foreclosure_id IS NOT NULL AND prepayment_id IS NOT NULL)",
            name="check_only_one_of_foreclosure_or_prepayment"
        ),
    )
    

class Invoice(CreateUpdateTime, CreateByUpdateBy):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True, index=True)
    payment_detail_id = Column(Integer, ForeignKey("payment_details.id"), nullable=True, index=True)
    razorpay_invoice_id = Column(String, unique=True, nullable=False)
    entity = Column(String, nullable=True, default="invoice")
    amount = Column(Float, nullable=False)  # Amount in INR
    currency = Column(String, default="INR")
    status = Column(Enum(InvoiceStatus), nullable=False)  # e.g., draft, issued, paid, partially_paid, cancelled, expired
    emi_number = Column(Integer, nullable=False)  # Tracks EMI sequence (e.g., 1 for first EMI, 2 for second)
    due_date = Column(BigInteger, nullable=True)  # Unix timestamp for due date
    issued_at = Column(BigInteger, nullable=True)  # Unix timestamp when invoice was issued
    paid_at = Column(BigInteger, nullable=True)  # Unix timestamp when invoice was paid
    expired_at = Column(BigInteger, nullable=True)  # Unix timestamp when invoice expired
    short_url = Column(String, nullable=True)  # Payment link for the invoice
    customer_notify = Column(Boolean, default=True)  # Whether customer was notified
    notes = Column(Text, nullable=True)  # Additional notes or metadata
    invoice_data = Column(JSON, nullable=True)  # Full Razorpay invoice payload for flexibility
    created_at = Column(DateTime, default=datetime.utcnow)
    invoice_type =  Column(Enum(InvoiceType), nullable=True, default="emi")

    subscription = relationship("Subscription", back_populates="invoices")
    payment_details = relationship("PaymentDetails", back_populates="invoices")