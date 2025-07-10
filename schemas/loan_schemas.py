from typing import Optional, List

from pydantic import constr, model_validator, EmailStr, BaseModel

from common.enums import LoanType, IncomeProofType, DocumentType, LoanStatus


class LoanForm(BaseModel):
    name: str
    email: EmailStr
    phone_number: constr(min_length=10, max_length=15)
    annual_income: float
    desired_loan: float = 0.0
    date_of_birth: str
    gender: str
    address: str
    company_name: str
    company_address: str
    designation: str
    purpose_of_loan: str
    loan_type: LoanType
    pan_number: constr(min_length=10, max_length=10)
    aadhaar_number: constr(min_length=12, max_length=12)
    pan_file: Optional[str] = None
    aadhaar_file: Optional[str] = None

    proof_type: IncomeProofType
    document_type: DocumentType
    document_file: list

    property_document_file: Optional[List[str]] = None

    @model_validator(mode="after")
    def check_files_required_if_numbers_provided(cls, values):
        pan_number = values.pan_number
        pan_file = values.pan_file
        aadhaar_number = values.aadhaar_number
        aadhaar_file = values.aadhaar_file

        if pan_number and not pan_file:
            raise ValueError('Pan Card File is required when Pan Number is provided')

        if aadhaar_number and not aadhaar_file:
            raise ValueError('Aadhar Card File is required when Aadhar Number is provided')

        if values.loan_type == LoanType.LAP and not values.property_document_file:
            raise ValueError('Property Document File is required for LAP loan type')

        return values


from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class LoanDocumentSchema(BaseModel):
    id: int
    document_type: str
    document_number: Optional[str]
    document_file: str
    status: str
    remarks: Optional[str]

    model_config = {
        "from_attributes": True
    }


class LoanApplicantResponseSchema(BaseModel):
    id: int
    loan_uid: str
    name: str
    email: Optional[str]
    phone_number: str
    annual_income: int
    desired_loan: int
    date_of_birth: datetime
    gender: Optional[str]
    address: Optional[str]
    company_name: Optional[str]
    company_address: Optional[str]
    designation: Optional[str]
    purpose_of_loan: Optional[str]
    remarks: Optional[str]
    status: str
    created_at: datetime
    modified_at: datetime
    is_deleted: bool
    deleted_at: Optional[datetime]
    created_by: int
    modified_by: int
    documents: Optional[List[LoanDocumentSchema]] = []

    model_config = {
        "from_attributes": True
    }


class LoanApplicantResponseSchema(BaseModel):
    id: int
    loan_uid: str
    name: str
    phone_number: str
    annual_income: int
    desired_loan: int
    purpose_of_loan: Optional[str]
    status: str
    created_at: datetime

    model_config = {
        "from_attributes": True
    }


class UpdateLoanForm(LoanForm):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[constr(min_length=10, max_length=15)] = None
    annual_income: Optional[float] = None
    desired_loan: Optional[float] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    company_name: Optional[str] = None
    company_address: Optional[str] = None
    designation: Optional[str] = None
    purpose_of_loan: Optional[str] = None
    status: Optional[LoanStatus] = None
    loan_type: Optional[LoanType] = None
    approved_loan: Optional[float] = None
    remarks: Optional[str] = None
    is_deleted: Optional[bool] = False
    pan_number: Optional[constr(min_length=10, max_length=10)] = None
    aadhaar_number: Optional[constr(min_length=12, max_length=12)] = None
    pan_file: Optional[str] = None
    aadhaar_file: Optional[str] = None
    proof_type: Optional[IncomeProofType] = None
    document_type: Optional[DocumentType] = None
    document_file: Optional[List] = None

    property_document_file: Optional[List[str]] = None

    @model_validator(mode="after")
    def check_approved_loan_required(cls, values):
        status = values.status
        approved_loan = values.approved_loan
        remarks = values.remarks

        if status and not remarks:
            raise ValueError('Remarks is required when updating loan status')

        if status in [LoanStatus.APPROVED, LoanStatus.REJECTED, LoanStatus.ON_HOLD] and approved_loan is None:
            raise ValueError("approved_loan is required when status is APPROVED, REJECTED, or ON_HOLD.")

        if values.loan_type == LoanType.LAP and not values.property_document_file:
            raise ValueError('Property Document File is required for LAP loan type')

        return values
