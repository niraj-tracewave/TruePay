from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel
from pydantic import constr, model_validator, EmailStr

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
    credit_score: Optional[str] = None
    pan_verified: Optional[bool] = False
    aadhaar_verified: Optional[bool] = False

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
    loan_type: str
    approved_loan: Optional[float]
    credit_score: Optional[str]
    credit_score_range_rate_id: Optional[int] = 0
    credit_score_range_rate_percentage: Optional[float] = 0.0
    custom_rate_percentage: Optional[float] = 0.0
    processing_fee_id: Optional[int] = 0
    processing_fee: Optional[float] = 0.0
    custom_processing_fee: Optional[float] = 0.0
    tenure_months: Optional[int] = 0

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
    credit_score_range_rate_id: Optional[int] = None
    custom_rate_percentage: Optional[float] = None
    credit_score_range_rate_percentage: Optional[float] = None
    processing_fee_id: Optional[int] = None
    processing_fee: Optional[float] = None
    custom_processing_fee: Optional[float] = None
    tenure_months: Optional[int] = None

    property_document_file: Optional[List[str]] = None

    @model_validator(mode="after")
    def check_approved_loan_required(cls, values):
        status = values.status
        approved_loan = values.approved_loan
        remarks = values.remarks
        credit_score_range_rate_id = values.credit_score_range_rate_id
        custom_rate_percentage = values.custom_rate_percentage
        credit_score_range_rate_percentage = values.credit_score_range_rate_percentage
        processing_fee_id = values.processing_fee_id
        processing_fee = values.processing_fee
        custom_processing_fee = values.custom_processing_fee
        tenure_months = values.tenure_months

        if status and not remarks:
            raise ValueError('Remarks is required when updating loan status')

        if status == LoanStatus.APPROVED:
            if approved_loan is None:
                raise ValueError("approved_loan is required when status is APPROVED")
            if (
                    credit_score_range_rate_id is None or credit_score_range_rate_percentage is None) and custom_rate_percentage is None:
                raise ValueError("Interest Rate is required when status is APPROVED")
            if (not processing_fee_id or not processing_fee) and not custom_processing_fee:
                raise ValueError("Processing Fee is required when status is APPROVED")
            if tenure_months is None:
                raise ValueError("Tenure Months is required when status is APPROVED")

        if values.loan_type == LoanType.LAP and not values.property_document_file:
            raise ValueError('Property Document File is required for LAP loan type')

        if values.custom_processing_fee == 0:
            values.custom_processing_fee = None

        if values.custom_rate_percentage == 0:
            values.custom_rate_percentage = None

        return values


class UserApprovedLoanForm(BaseModel):
    applicant_id: int
    approved_interest_rate: float
    final_interest_rate: float
    custom_interest_rate: Optional[float] = None
    approved_processing_fee: float
    processing_fee_amount: float
    custom_processing_fee: Optional[float] = None
    approved_tenure_months: int
    final_tenure_months: int
    user_accepted_amount: float
    approved_loan_amount: float

    @model_validator(mode="after")
    def validate_approved_fields(self) -> 'UserApprovedLoanForm':
        # ❗ Interest Rate check: All 3 are required
        if (
                (self.approved_interest_rate is None or self.final_interest_rate is None) and
                self.custom_interest_rate is None
        ):
            raise ValueError("All interest rate fields are required for Final Approval.")

        # ❗ Processing Fee check: All 3 are required
        if (
                (self.approved_processing_fee is None or self.processing_fee_amount is None) and
                self.custom_processing_fee is None
        ):
            raise ValueError("All processing fee fields are required for Final Approval.")

        # ❗ Tenure check
        if self.approved_tenure_months is None or self.final_tenure_months is None:
            raise ValueError("Tenure Months is required for Final Approval")

        if self.user_accepted_amount is None and self.approved_loan_amount is None:
            raise ValueError("User Accepted Amount and Approved Loan Amount is required for Final Approval")

        # if self.custom_processing_fee == 0:
        #     self.custom_processing_fee = None
        #
        # if self.custom_interest_rate == 0:
        #     self.custom_interest_rate = None

        return self

class InstantCashForm(BaseModel):
    applicant_id: int
    interest_rate: float
    processing_fee: float
    tenure_months: int
    accepted_amount: float