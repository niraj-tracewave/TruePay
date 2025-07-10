from enum import Enum


# User Enums
class UserRole(str, Enum):
    admin = "admin"
    user = "user"


class DocumentType(str, Enum):
    aadhar = "aadhar"
    pan = "pan"
    passport = "passport"
    voter_id = "voter_id"
    driving_license = "driving_license"
    address_proof = "address_proof"
    bank_statement = "bank_statement"
    salary_slip = "salary_slip"
    itr = "itr"
    form_16 = "form_16"
    business_registration = "business_registration"
    license = "license"
    property_document = "property_document"


class GenderEnum(str, Enum):
    male = "Male"
    female = "Female"
    other = "Other"


# Loan Enums
class LoanStatus(str, Enum):
    PENDING = "PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    ON_HOLD = "ON_HOLD"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DISBURSED = "DISBURSED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


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
