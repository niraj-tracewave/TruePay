from datetime import datetime
from math import ceil
from typing import Optional, List, Dict, Any

from dateutil.relativedelta import relativedelta
from fastapi import UploadFile
from passlib.context import CryptContext
from starlette import status

from app_logging import app_logger
from common.cache_string import gettext
from models.user import User, UserDocument


def format_user_response(user: User, documents: Optional[list[UserDocument]] = None) -> dict:
    """
        Formats a User SQLAlchemy object along with related documents (PAN, Aadhaar).

        Args:
            user (User): User SQLAlchemy ORM object
            documents (List[UserDocument] | None): List of related document objects, or None

        Returns:
            dict: Formatted user data with document URLs and numbers
    """
    app_logger.info("Formatting user response with S3 URLs for profile image and documents.")

    pan_doc = aadhaar_doc = None

    if documents:
        pan_doc = next((doc for doc in documents if doc.document_type.value == "PAN"), None)
        aadhaar_doc = next((doc for doc in documents if doc.document_type.value == "AADHAR"), None)

    cibil_data = {}
    if user.cibil_reports:
        user_cibil_data = user.cibil_reports[-1]
        cibil_data = {
            "credit_score": user_cibil_data.credit_score,
            "refresh_date": user_cibil_data.report_refresh_date,
            "next_eligible_date": user_cibil_data.next_eligible_date,
        }

    return {
        "id": user.id,
        "name": user.name or "",
        "address": user.address or "",
        "phone_number": user.phone or "",
        "email": user.email or "",
        "role": user.role.value if user.role else "",
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else "",
        "profile_image": user.profile_image or "",

        "pan_number": pan_doc.document_number if pan_doc else "",
        "pan_document": pan_doc.document_file if pan_doc else "",

        "aadhaar_number": aadhaar_doc.document_number if aadhaar_doc else "",
        "aadhaar_document": aadhaar_doc.document_file if aadhaar_doc else "",
        "cibil_info": cibil_data
    }


def format_loan_documents(documents: list) -> list[dict]:
    formatted_docs = []
    for doc in documents:
        formatted_docs.append(
            {
                "id": doc.id,
                "document_type": doc.document_type.value.lower() if hasattr(doc.document_type, "value") else str(
                    doc.document_type
                ).lower(),
                "document_number": doc.document_number or "",
                "document_file": doc.document_file or "",
                "status": doc.status.value if hasattr(doc.status, "value") else str(doc.status),
                "remarks": doc.remarks or "",
            }
        )
    return formatted_docs


class PasswordHashing:
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    # Hash password
    def hash_password(self, password: str) -> str:
        return self.pwd_context.hash(password)

    # Verify password
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return self.pwd_context.verify(plain_password, hashed_password)


def validate_file_type(file: UploadFile):
    allowed_types = [
        "application/pdf",
        "image/jpeg",
        "image/jpg",
        "image/png",
    ]
    if file.content_type not in allowed_types:
        raise Exception(f"Invalid file type: {file.content_type}. Only PDF and images are allowed.")


def calculate_emi(
        loan_amount: float, tenure_months: int, annual_interest_rate: float, processing_fee: float = 0.0,
        is_fee_percentage: bool = False
) -> Dict[str, Any]:
    """
    Calculate EMI with an optional processing fee.

    Returns:
        dict: EMI breakdown or error message.
    """
    try:
        app_logger.info(
            f"Calculating EMI | Loan: {loan_amount}, Tenure: {tenure_months}, Rate: {annual_interest_rate}%, "
            f"Processing Fee: {processing_fee}, Is %: {is_fee_percentage}"
        )

        if loan_amount <= 0 or tenure_months <= 0:
            return {
                "success": False,
                "message": "Loan amount and tenure must be greater than zero.",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {},
            }

        fee_amount = (loan_amount * (processing_fee / 100)) if is_fee_percentage else processing_fee
        total_principal = loan_amount + fee_amount
        monthly_rate = annual_interest_rate / (12 * 100)

        if monthly_rate == 0:
            emi = total_principal / tenure_months
        else:
            emi = total_principal * monthly_rate * pow(1 + monthly_rate, tenure_months) / (
                    pow(1 + monthly_rate, tenure_months) - 1
            )

        total_payment = emi * tenure_months
        total_interest = total_payment - total_principal

        return {
            "success": True,
            "message": gettext("retrieved_successfully").format("EMI Calculation"),
            "status_code": status.HTTP_200_OK,
            "data": {
                "emi": round(float(ceil(emi)), 2),
                "total_payment": round(float(ceil(total_payment)), 2),
                "total_interest": round(float(ceil(total_interest)), 2),
                "loan_amount": round(float(ceil(loan_amount)), 2),
                "processing_fee": round(float(ceil(processing_fee)), 2),
                "total_principal": round(float(ceil(total_principal)), 2),
                "annual_interest_rate": annual_interest_rate,
                "tenure_months": tenure_months
            }
        }

    except Exception as e:
        app_logger.exception(f"Error in EMI calculation: {e}")
        return {
            "success": False,
            "message": gettext("something_went_wrong"),
            "status_code": status.HTTP_400_BAD_REQUEST,
            "data": {},
        }


def calculate_emi_schedule(
        loan_amount: float, annual_interest_rate: float, tenure_months: int, processing_fee: float = 0.0,
        is_fee_percentage: bool = False, start_date: datetime = datetime.today(),

) -> Dict[str, Any]:
    """
        Generate a month-wise EMI schedule with interest and principal breakdown.

        Returns:
            dict: EMI schedule or error message.
    """
    try:
        app_logger.info(
            f"Generating EMI schedule | Principal: {loan_amount}, Tenure: {tenure_months}, Rate: {annual_interest_rate}%, "
            f"Processing Fee: {processing_fee}, Is Fee %: {is_fee_percentage}"
        )

        if loan_amount <= 0 or tenure_months <= 0:
            return {
                "success": False,
                "message": "Principal and tenure must be greater than zero.",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {},
            }

        if start_date.day >= 25:
            current_month = (start_date.replace(day=1) + relativedelta(months=1))
        else:
            current_month = start_date.replace(day=1)

        fee_amount = (loan_amount * (processing_fee / 100)) if is_fee_percentage else processing_fee
        total_principal = loan_amount + fee_amount
        monthly_rate = annual_interest_rate / 12 / 100

        emi = (total_principal * monthly_rate * (1 + monthly_rate) ** tenure_months) / (
                (1 + monthly_rate) ** tenure_months - 1
        )

        balance = total_principal
        schedule = []

        for month in range(tenure_months):
            month_date = current_month + relativedelta(months=month)
            label = month_date.strftime("%b %Y")
            interest = balance * monthly_rate
            principal_paid = emi - interest
            balance -= principal_paid
            balance = max(balance, 0)

            schedule.append(
                {
                    "month": label,
                    "principal_paid": round(float(ceil(principal_paid)), 2),
                    "interest_paid": round(float(ceil(interest)), 2),
                    "emi": round(float(ceil(emi)), 2),
                    "balance": round(float(ceil(balance)), 2)
                }
            )

        return {
            "success": True,
            "message": gettext("retrieved_successfully").format("EMI Schedule"),
            "status_code": status.HTTP_200_OK,
            "data": {
                "loan_amount": round(float(ceil(loan_amount)), 2),
                "processing_fee": round(float(ceil(processing_fee)), 2),
                "total_principal": round(float(ceil(total_principal)), 2),
                "monthly_emi": round(float(ceil(emi)), 2),
                "schedule": schedule,
                "total_interest": round(float(ceil(sum(p['interest_paid'] for p in schedule))), 2),
                "total_payment": round(float(ceil(sum(p['emi'] for p in schedule))), 2)
            }
        }

    except Exception as e:
        app_logger.exception(f"Error generating EMI schedule: {e}")
        return {
            "success": False,
            "message": gettext("something_went_wrong"),
            "status_code": status.HTTP_400_BAD_REQUEST,
            "data": {},
        }
