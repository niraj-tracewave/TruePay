from datetime import datetime
from math import ceil
from typing import Optional, List, Dict, Any

from dateutil.relativedelta import relativedelta
from fastapi import UploadFile
from passlib.context import CryptContext
from starlette import status

from config import app_config
from app_logging import app_logger
from common.cache_string import gettext
from models.user import User, UserDocument
from db_domains.db_interface import DBInterface
from models.loan import EmiScheduleDate, LoanApplicant


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
            "id": user_cibil_data.id,
            "name": user_cibil_data.name,
            "credit_score": user_cibil_data.credit_score,
            "pan_number": user_cibil_data.pan_number if user_cibil_data.pan_number else "",
            "refresh_date": user_cibil_data.report_refresh_date,
            "next_eligible_date": user_cibil_data.next_eligible_date,
            "client_id": user_cibil_data.client_id,
            "gender": user_cibil_data.gender.value,
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
        "gender": user.gender.value,

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
                "document_type": doc.document_type.value if hasattr(doc.document_type, "value") else str(
                    doc.document_type
                ),
                "document_number": doc.document_number or "",
                "document_file": doc.document_file or "",
                "status": doc.status.value if hasattr(doc.status, "value") else str(doc.status),
                "remarks": doc.remarks or "",
            }
        )
    return formatted_docs


def format_plan_and_subscriptions(plans: List[any]) -> List[dict]:
    formatted_data = []

    for plan in plans:
        subscriptions_data = []
        for sub in plan.subscriptions:
            foreclosure_data_list = []
            for foreclosure in sub.foreclosures:
                foreclosure_data = {
                    "id": foreclosure.id,
                    "subscription_id": foreclosure.subscription_id,
                    "amount": foreclosure.amount,
                    "status": foreclosure.status.value if hasattr(foreclosure.status, "value") else str(foreclosure.status),
                }
                if foreclosure.payment_details:
                    payment_details = {
                        "id": foreclosure.payment_details.id,
                        "payment_id": foreclosure.payment_details.payment_id,
                        "amount": foreclosure.payment_details.amount,
                        "status": foreclosure.payment_details.status.value if hasattr(foreclosure.payment_details.status, "value") else str(foreclosure.payment_details.status),
                        "created_at": foreclosure.payment_details.created_at.isoformat() if foreclosure.payment_details.created_at else None
                    }
                    foreclosure_data["payment_details"] = payment_details
                foreclosure_data_list.append(foreclosure_data)
            subscriptions_data.append({
                "subscription_id": sub.id,
                "razorpay_subscription_id": sub.razorpay_subscription_id,
                "status": sub.status.value if hasattr(sub.status, "value") else str(sub.status),
                "foreclosure_data": foreclosure_data_list
            })

        formatted_data.append({
            "plan_id": plan.id,
            "razorpay_plan_id": plan.razorpay_plan_id,
            "subscriptions": subscriptions_data,
        })

    return formatted_data

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
        loan_type: str = None, emi_start_day_atm: int = None

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

        # fee_amount = (loan_amount * (processing_fee / 100)) if is_fee_percentage else processing_fee
        total_principal = loan_amount
        monthly_rate = annual_interest_rate / 12 / 100

        emi = (total_principal * monthly_rate * (1 + monthly_rate) ** tenure_months) / (
                (1 + monthly_rate) ** tenure_months - 1
        )

        balance = total_principal
        schedule = []
        # Fetch Static Fixed Date 
        emi_schedule_date = 5
        try:
            if emi_start_day_atm:
                emi_schedule_date = emi_start_day_atm
            else:
                emi_schedule_db_interface = DBInterface(EmiScheduleDate)
                existing_entry = emi_schedule_db_interface.read_single_by_fields(
                        fields=[
                            EmiScheduleDate.emi_schedule_loan_type == loan_type,
                            EmiScheduleDate.is_deleted == False,
                        ]
                    )
                emi_schedule_date = existing_entry.emi_schedule_date if existing_entry else 5
        except Exception as e:
            print(f"Error fetching EMI schedule date: {e}")

        for month in range(1, tenure_months+1):
            month_date = current_month + relativedelta(months=month)
            label = f"{str(emi_schedule_date)} {month_date.strftime('%b %Y')}"
            interest = round(balance * monthly_rate, 2)
            principal_paid = round(emi - interest, 2)
            balance = round(balance - principal_paid, 2)
            balance = max(balance, 0)

            schedule.append(
                {
                    "month": label,
                    "principal_paid": principal_paid,
                    "interest_paid": interest,
                    "emi": round(emi, 2),
                    "balance": balance,
                    "show_balance": int(balance),
                    "show_principal_paid": int(principal_paid),
                    "show_interest_paid": int(interest),
                    "show_emi": round(emi, 0),
                }
            )

        return {
            "success": True,
            "message": gettext("retrieved_successfully").format("EMI Schedule"),
            "status_code": status.HTTP_200_OK,
            "data": {
                "loan_amount": round(float(ceil(loan_amount)), 2),
                "processing_fee": float(processing_fee),
                "total_principal": round(float(ceil(total_principal)), 2),
                # "monthly_emi": round(float(ceil(emi)), 0),
                "monthly_emi": round(emi, 0),
                "schedule": schedule,
                # "total_interest": round(float(ceil(sum(p['interest_paid'] for p in schedule))), 2),
                "total_interest": round(float(sum(p['interest_paid'] for p in schedule)), 0),
                # "total_payment": round(float(ceil(sum(p['emi'] for p in schedule))), 0),
                "total_payment": round(float(sum(p['interest_paid'] for p in schedule))) + loan_amount
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

def unix_to_yyyy_mm_dd(unix_timestamp: int) -> Optional[str]:
    try:
        dt = datetime.fromtimestamp(unix_timestamp)  # local timezone
        return dt.strftime("%Y-%m-%d")
    except Exception as e:
        # Optional: log the exception here if needed
        return None
    
def get_latest_paid_at(razorpay_sub_invoice_detail: dict) -> int | None:
    items = razorpay_sub_invoice_detail.get("items", [])
    # Filter invoices that have a non-null 'paid_at'
    paid_invoices = [inv for inv in items if inv.get("paid_at") is not None]
    
    if not paid_invoices:
        return None  # No invoices have been paid
    
    # Find the invoice with the max 'paid_at' timestamp
    latest_invoice = max(paid_invoices, key=lambda x: x["paid_at"])
    return latest_invoice["paid_at"]

def calculate_foreclosure_details(
    razorpay_plan_data: Dict[str, Any],
    razorpay_sub_data: Dict[str, Any],
    loan_details: LoanApplicant,
    effective_processing_fee: float
) -> Dict[str, float]:
    """Calculate foreclosure details based on Razorpay plan and subscription data."""
    loan_approval_detail = loan_details.approval_details[0]
    user_accepted_amount = loan_approval_detail.user_accepted_amount
    approved_interest_rate = loan_approval_detail.approved_interest_rate
    approved_tenure_months = loan_approval_detail.approved_tenure_months
    approved_processing_fee = loan_approval_detail.approved_processing_fee

    emi_result = calculate_emi_schedule(
                loan_amount=user_accepted_amount,
                tenure_months=approved_tenure_months,
                annual_interest_rate=approved_interest_rate,
                processing_fee=approved_processing_fee,
                is_fee_percentage=True,
                loan_type=loan_details.loan_type,
                emi_start_day_atm=loan_details.emi_start_day_atm
            )
    
    paid_principal_amt = 0.0
    interest_paid_amt = 0.0
    foreclosure_amt = 0.0
    paid_based_on_data = razorpay_sub_data['total_count'] - razorpay_sub_data['remaining_count']
    principal_amount = loan_details.approval_details[0].user_accepted_amount or 0.0
    if paid_based_on_data > 0:
        schedule = emi_result.get("data", {}).get("schedule", [])
        if len(schedule) < paid_based_on_data:
            raise IndexError(f"Schedule length ({len(schedule)}) is less than required ({paid_based_on_data})")

        for emi in schedule[:paid_based_on_data]:
            if not isinstance(emi, dict):
                raise TypeError("EMI entry must be a dictionary")

            paid_principal_amt += emi.get("principal_paid", 0.0)
            interest_paid_amt += emi.get("interest_paid", 0.0)
        # Set foreclosure_amt to the balance of the next EMI (if available)
        if paid_based_on_data < len(schedule):
            foreclosure_amt = schedule[paid_based_on_data].get("balance", 0.0)
        else:
            foreclosure_amt = 0.0  # No balance left if all EMIs are paid
    elif paid_based_on_data == 0:
        foreclosure_amt = principal_amount
    foreclosure_processing_amount = 0.0
    processing_fee = (effective_processing_fee * principal_amount) / 100
    other_charges = (processing_fee * int(app_config.GST_CHARGE)) / 100
    total_charges = processing_fee + other_charges

    return {
        "foreclosure_amount": foreclosure_amt,
        "principal_amount": principal_amount,
        "foreclosure_processing_amount": foreclosure_processing_amount,
        "processing_fee": processing_fee,
        "other_charges": other_charges,
        "total_charges": total_charges
    }
    
def map_razorpay_invoice_to_db(invoice_json, emi_number: int, payment_detail_id: int = None, subscription_id: int = None):
    return {
        "razorpay_invoice_id":invoice_json["id"],
        "subscription_id":subscription_id,  # map your internal subscription_id if you track it
        "payment_detail_id":payment_detail_id,
        "entity":invoice_json.get("entity", "invoice"),
        "amount":invoice_json.get("amount", 0) / 100 if invoice_json.get("amount") else 0,  # if Razorpay returns paise
        "currency":invoice_json.get("currency", "INR"),
        "status":invoice_json.get("status", "draft"),
        "emi_number":emi_number,
        "due_date":invoice_json.get("billing_end"),  # use Razorpay billing_end as due_date
        "billing_start":invoice_json.get("billing_start"),  # use Razorpay billing_end as due_date
        "issued_at":invoice_json.get("issued_at"),
        "paid_at":invoice_json.get("paid_at"),
        'expired_at':invoice_json.get("expired_at"),
        "short_url":invoice_json.get("short_url"),
        "customer_notify":True,  # set based on your flow
        "notes":str(invoice_json.get("notes", [])),
        "invoice_data":invoice_json,  # store full JSON for flexibility
        "invoice_type":"emi"
    }
    
def map_payment_link_to_invoice_obj(payment: dict, 
                                    invoice_type: str,
                                    emi_number: int = 1,
                                    payment_detail_id: int = None,
                                    subscription_id: int = None,
                                    ):
    if payment.get("status") != "paid":
        return None  

    payments = payment.get("payments", [])
    payment_obj = payments[0] if payments else {}
    return {
        "razorpay_invoice_id": payment_obj.get("payment_id"),
        "subscription_id": subscription_id,
        "payment_detail_id": payment_detail_id,
        "entity": "invoice",
        "amount": payment.get("amount_paid", 0) / 100 if payment.get("amount_paid") else 0,
        "currency": payment.get("currency", "INR"),
        "status": "paid",
        "emi_number": emi_number,
        "due_date": payment.get("expire_by") or payment.get("expired_at"),
        "issued_at": payment.get("created_at"),      # when link was created
        "paid_at": payment_obj.get("created_at"),    # when payment was captured
        "expired_at": payment.get("expired_at"),
        "short_url": payment.get("short_url"),
        "customer_notify": payment.get("notify", {}).get("email", True),
        "notes": str(payment.get("notes", {})),
        "invoice_data": payment,
        "invoice_type": invoice_type,
        "billing_start" :payment.get("notes", {}).get("billing_start")
    }