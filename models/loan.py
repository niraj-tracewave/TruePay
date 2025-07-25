import random
import re
import string

from sqlalchemy import (Column, Integer, String, Float, Date, Enum, ForeignKey, UniqueConstraint, Index)
from sqlalchemy.orm import relationship

from common.enums import IncomeProofType, DocumentType, DocumentStatus, LoanType, LoanStatus, GenderEnum
from db_domains import CreateUpdateTime, CreateByUpdateBy


class LoanApplicant(CreateUpdateTime, CreateByUpdateBy):
    __tablename__ = "loan_applicants"

    id = Column(Integer, primary_key=True, index=True)
    loan_uid = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    email = Column(String(100), nullable=False, index=True)
    phone_number = Column(String(15), nullable=False, index=True)
    annual_income = Column(Float, nullable=False)
    desired_loan = Column(Float, default=0.0)
    date_of_birth = Column(Date, nullable=False)
    gender = Column(Enum(GenderEnum), nullable=False)
    address = Column(String(500), nullable=False)
    company_name = Column(String(255), nullable=True)
    company_address = Column(String(500), nullable=True)
    designation = Column(String(255), nullable=True)
    purpose_of_loan = Column(String(500), nullable=False)
    remarks = Column(String(500), nullable=True)
    loan_type = Column(
        Enum(LoanType), default=LoanType.PERSONAL, server_default=LoanType.PERSONAL.value, nullable=False
    )
    status = Column(
        Enum(LoanStatus), default=LoanStatus.PENDING, server_default=LoanStatus.PENDING.value, nullable=False
    )
    approved_loan = Column(Float, nullable=True)
    credit_score_range_rate_id = Column(
        Integer, ForeignKey("credit_score_range_rate.id", ondelete="SET NULL"), nullable=True
    )
    custom_rate_percentage = Column(Float, nullable=True)

    credit_score_range_rate = relationship("CreditScoreRangeRate")
    documents = relationship("LoanDocument", back_populates="applicant", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<LoanApplicant id={self.id} uid={self.loan_uid} name={self.name} status={self.status}>"

    @classmethod
    def is_valid_phone(cls, phone: str) -> bool:
        return bool(re.fullmatch(r"[\d\s\-]+", phone)) and (10 <= sum(c.isdigit() for c in phone) <= 15)

    @classmethod
    def is_valid_email(cls, email: str) -> bool:
        return bool(re.fullmatch(r"[^@]+@[^@]+\.[^@]+", email)) if email else True

    @staticmethod
    def generate_loan_uid() -> str:
        """
        Generate a unique loan UID like TPARDTR2783Q
        """
        letters_part = ''.join(random.choices(string.ascii_uppercase, k=5))
        digits_part = ''.join(random.choices(string.digits, k=4))
        last_letter = random.choice(string.ascii_uppercase)
        return f"TP{letters_part}{digits_part}{last_letter}"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Perform validations during initialization
        if not self.is_valid_phone(self.phone_number):
            raise ValueError(f"Invalid phone number: {self.phone_number}")

        if not self.is_valid_email(self.email):
            raise ValueError(f"Invalid email address: {self.email}")

        if not self.loan_uid:
            self.loan_uid = self.generate_loan_uid()


class LoanDocument(CreateUpdateTime, CreateByUpdateBy):
    __tablename__ = "loan_documents"

    id = Column(Integer, primary_key=True, index=True)
    applicant_id = Column(Integer, ForeignKey("loan_applicants.id"), nullable=False, index=True)

    proof_type = Column(Enum(IncomeProofType), nullable=True, index=True)
    document_type = Column(Enum(DocumentType), nullable=False, index=True)
    document_number = Column(String(100), nullable=True, index=True)
    document_file = Column(String(255), nullable=True)
    remarks = Column(String(500), nullable=True)
    status = Column(
        Enum(DocumentStatus), default=DocumentStatus.PENDING, server_default=DocumentStatus.PENDING.value,
        nullable=False
    )

    applicant = relationship("LoanApplicant", back_populates="documents")

    def __repr__(self):
        return f"<LoanDocument id={self.id} applicant_id={self.applicant_id} type={self.document_type}>"


class LoanApprovalDetail(CreateUpdateTime, CreateByUpdateBy):
    __tablename__ = "loan_approval_details"

    id = Column(Integer, primary_key=True, index=True)

    applicant_id = Column(Integer, ForeignKey("loan_applicants.id"), unique=True, nullable=False, index=True)

    interest_rate_id = Column(Integer, ForeignKey("credit_score_range_rate.id"), nullable=True)
    final_interest_rate = Column(Float, nullable=False)
    custom_interest_rate = Column(Float, nullable=True)
    processing_fee_id = Column(Integer, ForeignKey("processing_fees.id"), nullable=False)
    processing_fee_amount = Column(Float, nullable=False)  # E.g., ₹10,000.0

    approved_loan_amount = Column(Float, nullable=False)
    user_accepted_amount = Column(Float, nullable=True)
    disbursed_amount = Column(Float, nullable=True)

    remarks = Column(String(500), nullable=True)

    # Relationships
    applicant = relationship("LoanApplicant", backref="approval_detail", uselist=False)
    interest_rate = relationship("CreditScoreRangeRate")
    processing_fee = relationship("ProcessingFee")

    __table_args__ = (
        UniqueConstraint('applicant_id', name='uq_approval_applicant'),  # redundant due to unique=True, but explicit
        Index('ix_approval_interest_rate_id', 'interest_rate_id'),
        Index('ix_approval_processing_fee_id', 'processing_fee_id'),
    )

    def __repr__(self):
        return (
            f"<LoanApprovalDetail applicant_id={self.applicant_id} "
            f"approved={self.approved_loan_amount} interest={self.interest_rate_id}% "
            f"fee={self.processing_fee_amount}>"
        )
