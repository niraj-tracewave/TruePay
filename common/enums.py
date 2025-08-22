from enum import Enum


# User Enums
class UserRole(str, Enum):
    admin = "admin"
    user = "user"


# Loan Enums
class LoanStatus(str, Enum):
    APPLICATION_SUBMITTED = "APPLICATION_SUBMITTED"
    PENDING = "PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    ON_HOLD = "ON_HOLD"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    AADHAR_VERIFIED = "AADHAR_VERIFIED"
    BANK_VERIFIED = "BANK_VERIFIED"
    USER_ACCEPTED = "USER_ACCEPTED"
    E_MANDATE_GENERATED = "E_MANDATE_GENERATED"
    DISBURSED = "DISBURSED"
    COMPLETED = "COMPLETED"  # PAY VIA FORECLOSURE
    CANCELLED = "CANCELLED"
    CLOSED = "CLOSED"  # ALL EMI PAID
    DISBURSEMENT_APPROVAL_PENDING = "DISBURSEMENT_APPROVAL_PENDING"
    DISBURSEMENT_APPROVED = "DISBURSEMENT_APPROVED"


class DocumentStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    UNDER_REVIEW = "UNDER_REVIEW"
    ON_HOLD = "ON_HOLD"


class IncomeProofType(str, Enum):
    SALARIED = "salaried"
    SELF_EMPLOYED = "self_employed"


class LoanType(str, Enum):
    PERSONAL = "PERSONAL"
    LAP = "LAP"
    MSME = "MSME"
    MICRO = "MICRO"


class DocumentType(str, Enum):
    PAN = "PAN"
    AADHAR = "AADHAR"
    PASSPORT = "PASSPORT"
    VOTER_ID = "VOTER_ID"
    DRIVING_LICENSE = "DRIVING_LICENSE"
    ADDRESS_PROOF = "ADDRESS_PROOF"
    BANK_STATEMENT = "BANK_STATEMENT"
    SALARY_SLIP = "SALARY_SLIP"
    ITR = "ITR"
    FORM_16 = "FORM_16"
    PROPERTY_DOCUMENTS = "PROPERTY_DOCUMENTS"


class UploadFileType(str, Enum):
    salaried = "salaried"
    self_employed = "self_employed"
    aadhar_card = "aadhar_card"
    pan_card = "pan_card"
    profile_image = "profile_image"
    property_documents = "property_documents"
    income_proof = "income_proof"
    payment_proof_documents = "payment_proof_documents"
    loan_complete_document = "loan_complete_document"


class GenderEnum(str, Enum):
    male = "male"
    female = "female"
    other = "other"


class ConsentEnum(str, Enum):
    yes = "Y"
    no = "N"


class SubscriptionStatus(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    RESUMED = "resumed"
    AUTHENTICATED = "authenticated"

class PaymentType(str, Enum):
    BANK_TRANSFER = "BANK_TRANSFER"
    CASH = "CASH"
    CHEQUE = "CHEQUE"
    UPI = "UPI"
