import os
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from zoneinfo import ZoneInfo

from fastapi import UploadFile, BackgroundTasks
from sqlalchemy import asc, desc
from sqlalchemy.orm import selectinload, with_loader_criteria
from starlette import status

from app_logging import app_logger
from config import app_settings
from common.cache_string import gettext
from common.common_services.aws_services import AWSClient
from common.common_services.email_service import EmailService
from common.email_html_utils import build_loan_email_bodies
from common.enums import DocumentType, IncomeProofType, LoanType, UploadFileType, LoanStatus
from common.utils import (calculate_emi_schedule, format_loan_documents,
    format_plan_and_subscriptions, unix_to_yyyy_mm_dd, validate_file_type, get_latest_paid_at, calculate_foreclosure_details)
from config import app_config
from db_domains import Base
from db_domains.db import DBSession
from db_domains.db_interface import DBInterface
from models.loan import LoanDocument, LoanApplicant, LoanApprovalDetail
from models.razorpay import Plan, Subscription, ForeClosure, PaymentDetails
from schemas.loan_schemas import LoanForm, LoanApplicantResponseSchema, UserApprovedLoanForm, InstantCashForm, \
    LoanConsentForm, LoanDisbursementForm, LoanAadharVerifiedStatusForm
from services.razorpay_service import RazorpayService
razorpay_service_obj = RazorpayService(
                app_config.RAZORPAY_KEY_ID, app_config.RAZORPAY_SECRET)

class UserLoanService:
    def __init__(self, db_model: type[Base]) -> None:
        self.db_class: type[Base] = db_model
        self.db_interface = DBInterface(self.db_class)

    def get_effective_rate(self, loan: LoanApplicant) -> float:
        if loan.custom_rate_percentage is not None:
            return loan.custom_rate_percentage
        if loan.credit_score_range_rate:
            return loan.credit_score_range_rate.rate_percentage
        return 0.0

    def get_effective_processing_fee(self, loan: LoanApplicant) -> float:
        if loan.custom_processing_fee is not None:
            return loan.custom_processing_fee
        if loan.processing_fee_id:
            return loan.processing_fee
        return 0.0

    def add_loan_application(
            self, user_id: str, loan_application_form: LoanForm, background_tasks: BackgroundTasks,
            is_created_by_admin: bool
    ):
        try:
            app_logger.info(f"User {user_id} initiated loan application.")

            # Prepare applicant details
            applicant_details_data = {
                "name": loan_application_form.name,
                "email": loan_application_form.email,
                "phone_number": loan_application_form.phone_number,
                "annual_income": loan_application_form.annual_income,
                "desired_loan": loan_application_form.desired_loan,
                "date_of_birth": loan_application_form.date_of_birth,
                "gender": loan_application_form.gender,
                "address": loan_application_form.address,
                "company_name": loan_application_form.company_name,
                "company_address": loan_application_form.company_address,
                "designation": loan_application_form.designation,
                "purpose_of_loan": loan_application_form.purpose_of_loan,
                "loan_type": loan_application_form.loan_type,
                "credit_score": loan_application_form.credit_score if loan_application_form.credit_score else 0,
                "created_by": user_id,
                "modified_by": user_id,
                "pan_verified": loan_application_form.pan_verified,
                "aadhaar_verified": loan_application_form.aadhaar_verified,
            }

            # Save loan applicant to DB
            applicant_obj = self.db_interface.create(applicant_details_data)
            applicant_id = applicant_obj.id
            app_logger.info(f"Loan applicant created with ID: {applicant_id}")

            # Prepare all documents
            all_documents = []
            doc_creator = lambda doc_type, number, file, proof_type=None, is_verified=False: {
                "applicant_id": applicant_id,
                "document_type": doc_type,
                "document_number": number or "",
                "document_file": file,
                "proof_type": proof_type,
                "created_by": user_id,
                "modified_by": user_id
            }

            # PAN document
            if loan_application_form.pan_number and loan_application_form.pan_file:
                all_documents.append(
                    doc_creator(
                        DocumentType.PAN.value,
                        loan_application_form.pan_number,
                        loan_application_form.pan_file,
                        is_verified=loan_application_form.pan_verified
                    )
                )
                app_logger.info("PAN document prepared for upload.")

            # Aadhaar document
            if loan_application_form.aadhaar_number and loan_application_form.aadhaar_file:
                all_documents.append(
                    doc_creator(
                        DocumentType.AADHAR.value,
                        loan_application_form.aadhaar_number,
                        loan_application_form.aadhaar_file,
                        is_verified=loan_application_form.aadhaar_verified
                    )
                )
                app_logger.info("Aadhaar document prepared for upload.")

            # Income proof documents
            if loan_application_form.proof_type in IncomeProofType.__members__.values():
                for doc_file in loan_application_form.document_file or []:
                    all_documents.append(
                        doc_creator(
                            loan_application_form.document_type.value,
                            "",  # No document_number
                            doc_file,
                            proof_type=loan_application_form.proof_type.value
                        )
                    )
                app_logger.info(f"{len(loan_application_form.document_file or [])} income proof documents prepared.")

            # Property documents (only for LAP)
            if loan_application_form.loan_type == LoanType.LAP and loan_application_form.property_document_file:
                for doc_file in loan_application_form.property_document_file:
                    all_documents.append(
                        doc_creator(
                            DocumentType.PROPERTY_DOCUMENTS.value,
                            "",
                            doc_file
                        )
                    )
                app_logger.info(f"{len(loan_application_form.property_document_file)} property documents prepared.")

            # Save all documents
            loan_document_interface = DBInterface(LoanDocument)
            document_instances = loan_document_interface.bulk_create(data_list=all_documents)
            app_logger.info(f"Documents uploaded successfully for applicant ID {applicant_id}.")

            # NOTE: Send Email Feature
            try:
                # Prepare email
                subject = "New Loan Application Submitted"
                recipient = os.environ.get("RECIPIENT_ADMIN_EMAIL", "")
                email_service_obj = EmailService()
                plain_body, html_body = build_loan_email_bodies(loan_application_form, applicant_obj, applicant_id)
                if os.environ.get("IS_PROD").lower() == "true" and is_created_by_admin == False:
                    background_tasks.add_task(email_service_obj.send_email, subject, plain_body, recipient, html_body)
            except Exception as e:
                app_logger.error(f"Error scheduling email for {loan_application_form.email}: {str(e)}")
            return {
                "success": True,
                "message": gettext("added_successfully").format("Loan Application"),
                "status_code": status.HTTP_200_OK,
                "data": {
                    "applicant_details": applicant_obj,
                    "documents": document_instances
                }
            }

        except Exception as e:
            app_logger.error(
                f"{gettext('error_adding_data_to_db').format('Loan Application')} {user_id}: {str(e)}", exc_info=True
            )
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {
                    "err": str(e)
                }
            }

    def get_loan_applications(self, user_id: str, order_by: Optional[str] = "id", order_dir: Optional[str] = "desc") -> Dict[str, Any]:
        try:
            app_logger.info(f"Fetching all loan applications for user: {user_id}")
            with DBSession() as session:
                order_column = {
                    "id": LoanApplicant.id,
                    "created_at": LoanApplicant.created_at
                }.get(order_by, LoanApplicant.id)  # fallback to id if unknown column
                order_func = asc if order_dir == "asc" else desc
                loan_with_docs = (
                    session.query(LoanApplicant)
                    .options(selectinload(LoanApplicant.documents),
                             selectinload(LoanApplicant.bank_accounts),
                             selectinload(LoanApplicant.credit_score_range_rate),
                             selectinload(LoanApplicant.loan_disbursement),
                             selectinload(LoanApplicant.plans).selectinload(Plan.subscriptions).selectinload(Subscription.foreclosures).selectinload(ForeClosure.payment_details),
                             selectinload(LoanApplicant.approval_details)
                             )
                    .filter(LoanApplicant.created_by == user_id, LoanApplicant.is_deleted == False)
                    .order_by(order_func(order_column))
                    .all()
                )
            loan_list = []
            for loan in loan_with_docs:
                plan_data = format_plan_and_subscriptions(loan.plans)
                loan_data = {
                    "id": loan.id,
                    "loan_uid": loan.loan_uid,
                    "name": loan.name,
                    "email": loan.email,
                    "phone_number": loan.phone_number,
                    "loan_type": loan.loan_type,
                    "status": loan.status,
                    "created_at": loan.created_at,
                    "approved_loan": loan.approved_loan,
                    "effective_interest_rate": self.get_effective_rate(loan),
                    "credit_score": loan.credit_score,
                    "desired_loan": loan.desired_loan,
                    "annual_income": loan.annual_income,
                    "purpose_of_loan": loan.purpose_of_loan,
                    "aadhaar_verified": loan.aadhaar_verified,
                    "pan_verified": loan.pan_verified,
                    "available_for_disbursement": loan.available_for_disbursement,
                    "plan_details": plan_data,
                    "documents": [
                        {
                            "id": doc.id,
                            "proof_type": doc.proof_type,
                            "document_type": doc.document_type,
                            "document_number": doc.document_number,
                            "document_file": doc.document_file,
                        } for doc in loan.documents
                    ],
                    "bank_accounts": [
                        {
                            "id": bank_account.id,
                            "applicant_id": bank_account.applicant_id,
                            "account_number": bank_account.account_number,
                            "account_holder_name": bank_account.account_holder_name,
                            "bank_name": bank_account.bank_name,
                            "ifsc_code": bank_account.ifsc_code
                    
                        }
                    for bank_account in loan.bank_accounts ],
                    "approval_details" : [
                    {
                        "id": approval_detail.id,
                        "applicant_id": approval_detail.applicant_id,
                        "user_accepted_amount": approval_detail.user_accepted_amount,
                        "disbursed_amount": approval_detail.disbursed_amount,
                        "approved_interest_rate": approval_detail.approved_interest_rate,
                        "approved_processing_fee": approval_detail.approved_processing_fee,
                        "approved_tenure_months": approval_detail.approved_tenure_months
                    }
                    for approval_detail in loan.approval_details],
                    "loan_acceptance_agreement_consent" : loan.loan_acceptance_agreement_consent,
                    "loan_insurance_agreement_consent" : loan.loan_insurance_agreement_consent,
                    "loan_policy_and_assignment_consent" : loan.loan_policy_and_assignment_consent
                }
                loan_list.append(loan_data)
            return {
                "success": True,
                "message": gettext("retrieved_successfully").format("Loan Applications") if loan_list else gettext(
                    "no_module_found"
                ).format("Loan Applications"),
                "status_code": status.HTTP_200_OK if loan_list else status.HTTP_404_NOT_FOUND,
                "data": {"loan_applications": loan_list}
            }
        except Exception as e:
            app_logger.error(
                f"{gettext('error_fetching_data_from_db').format('Loan Application')} {user_id}: {str(e)}",
                exc_info=True
            )
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {"er": str(e)}
            }
            
    def get_loan_foreclosure_details(
        self,
        loan_application_id: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch foreclosure details for a loan application.

        Args:
            loan_application_id (str): The ID of the loan application.
            user_id (Optional[str]): The ID of the user (optional).

        Returns:
            Dict[str, Any]: A dictionary containing success status, message, status code, and foreclosure data.
        """
        try:
            app_logger.info(
                f"Fetching foreclosure details for user: {user_id}, loan_application_id: {loan_application_id}"
            )

            # Define query filters
            filters = [
                LoanApplicant.id == loan_application_id,
                LoanApplicant.is_deleted == False
            ]
            if user_id:
                filters.append(LoanApplicant.created_by == user_id)

            # Query loan details with related data
            with DBSession() as session:
                loan_details = (
                    session.query(LoanApplicant)
                    .options(
                        selectinload(LoanApplicant.documents),
                        selectinload(LoanApplicant.approval_details),
                        selectinload(LoanApplicant.credit_score_range_rate),
                        selectinload(LoanApplicant.loan_disbursement),
                        selectinload(LoanApplicant.plans)
                        .selectinload(Plan.subscriptions)
                        .selectinload(Subscription.foreclosures)
                        .selectinload(ForeClosure.payment_details),
                        with_loader_criteria(LoanDocument, LoanDocument.is_deleted == False)
                    )
                    .filter(*filters)
                    .first()
                )

                if not loan_details:
                    app_logger.error(gettext('not_found').format('Loan Application'))
                    return {
                    "success": False,
                    "message": gettext("something_went_wrong"),
                    "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "data": default_data
                }

            # Initialize default response data
            default_data = {
                "foreclosure_amount": 0.0,
                "principal_amount": 0.0,
                "calculate_foreclosure_details": 0.0,
                "processing_fee": 0.0,
                "other_charges": 0.0,
                "total_charges": 0.0
            }
            # Process plan and subscription data
            plan_data = format_plan_and_subscriptions(loan_details.plans)
            if not plan_data:
                return {
                    "success": False,
                    "message": "E-mandate Process Is Not Done Yet!",
                    "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "data": default_data
                }
            current_plan = plan_data[0]
            plan_id = current_plan.get("razorpay_plan_id")
            if not plan_id:
                app_logger.warning("No Razorpay plan ID found for the loan application")
                return {
                    "success": False,
                    "message": "No Razorpay plan ID found for the loan application",
                    "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "data": default_data
                }

            # Fetch Razorpay plan and subscription data
            razorpay_plan_data = razorpay_service_obj.fetch_plan(plan_id=plan_id)
            if not razorpay_plan_data or 'item' not in razorpay_plan_data:
                app_logger.error("Failed to fetch valid Razorpay plan data")
                return {
                    "success": False,
                    "message": "Failed to fetch valid Razorpay plan data",
                    "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "data": default_data
                }

            subscriptions = current_plan.get("subscriptions", [])
            if not subscriptions:
                return {
                    "success": False,
                    "message": "E-mandate Process Is Not Done Yet!",
                    "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "data": default_data
                }

            current_subscription = subscriptions[0]
            razorpay_sub_id = current_subscription.get("razorpay_subscription_id")
            if not razorpay_sub_id:
                app_logger.warning("No Razorpay subscription ID found")
                return {
                    "success": False,
                    "message": "E-mandate Process Is Not Done Yet!",
                    "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "data": default_data
                }

            razorpay_sub_data = razorpay_service_obj.fetch_subscription(subscription_id=razorpay_sub_id)
            if not razorpay_sub_data:
                app_logger.error("Failed to fetch valid Razorpay subscription data")
                return {
                    "success": False,
                    "message": "Failed to fetch valid Razorpay subscription data",
                    "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "data": default_data
                }

            # Calculate foreclosure details
            effective_processing_fee = self.get_effective_processing_fee(loan_details)
            foreclosure_details = calculate_foreclosure_details(
                razorpay_plan_data,
                razorpay_sub_data,
                loan_details,
                effective_processing_fee
            )

            return {
                "success": True,
                "message": gettext("retrieved_successfully").format("Foreclousure Details"),
                "status_code": status.HTTP_200_OK,
                "data": foreclosure_details
            }

        except Exception as e:
            app_logger.error(
                f"{gettext('error_fetching_data_from_db').format('Loan Application')} {user_id}: {str(e)}",
                exc_info=True
            )
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {"error": str(e)}
            }

    def get_loan_application_details(self, loan_application_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            app_logger.info(
                f"Fetching loan application details for user: {user_id}, loan_application_id: {loan_application_id}"
            )
            filters = [
                LoanApplicant.id == loan_application_id,
                LoanApplicant.is_deleted == False
            ]
            if user_id:
                filters.append(LoanApplicant.created_by == user_id)
            with DBSession() as session:
                loan_with_docs = (
                    session.query(LoanApplicant)
                    .options(
                        selectinload(LoanApplicant.documents),
                        selectinload(LoanApplicant.bank_accounts),
                        selectinload(LoanApplicant.approval_details),
                        selectinload(LoanApplicant.credit_score_range_rate),
                        selectinload(LoanApplicant.loan_disbursement),
                        selectinload(LoanApplicant.loan_approved_document),
                        selectinload(LoanApplicant.plans).selectinload(Plan.subscriptions).selectinload(Subscription.foreclosures).selectinload(ForeClosure.payment_details),
                        with_loader_criteria(LoanDocument, LoanDocument.is_deleted == False)
                    )
                    .filter(*filters)
                    .first()
                )
                if not loan_with_docs:
                    app_logger.error(gettext('not_found').format('Loan Application'))
                    return {
                        "success": False,
                        "message": gettext('not_found').format('Loan Application'),
                        "status_code": status.HTTP_404_NOT_FOUND,
                        "data": {}
                    }
                plan_data = format_plan_and_subscriptions(loan_with_docs.plans)
                loan_response = LoanApplicantResponseSchema.model_validate(loan_with_docs).model_dump()
                loan_response["min_loan_amount"]=10000
                loan_response["min_tenure_months"]=12
                loan_response["max_tenure_months"]=loan_with_docs.tenure_months
                loan_response["tenure_months_steps"]=6
                loan_response["effective_interest_rate"] = self.get_effective_rate(loan_with_docs)
                formatted_documents = format_loan_documents(loan_with_docs.documents) if loan_with_docs else []
                loan_response["loan_acceptance_agreement_consent"] = loan_with_docs.loan_acceptance_agreement_consent
                loan_response["loan_insurance_agreement_consent"] = loan_with_docs.loan_insurance_agreement_consent
                loan_response["loan_policy_and_assignment_consent"] = loan_with_docs.loan_policy_and_assignment_consent
                loan_response["available_for_disbursement"] = loan_with_docs.available_for_disbursement
                loan_response["disbursement_apply_date"] = loan_with_docs.disbursement_apply_date
                loan_response["is_disbursement_manual"] = loan_with_docs.is_disbursement_manual
                loan_response["pan_verified"] = loan_with_docs.pan_verified
                loan_response["aadhaar_verified"] = loan_with_docs.aadhaar_verified
                loan_response["plan_details"] = plan_data
                #NOTE: Fetch Subscription Details and Proceed with The start date and End Date details for "Consumer durable loan Details" Page
                loan_response["e_mandate_payment_track"] = {}
                razorpay_sub_id = None
                razorpay_sub_detail = None
                razorpay_sub_invoice_detail = None

                if plan_data and isinstance(plan_data, list) and len(plan_data) > 0 and "subscriptions" in plan_data[0]:
                    subs = plan_data[0].get("subscriptions")
                    if subs and len(subs) > 0:
                        razorpay_sub_id = subs[0].get("razorpay_subscription_id")

                if razorpay_sub_id:
                    razorpay_sub_detail = razorpay_service_obj.fetch_subscription(subscription_id=razorpay_sub_id)
                    razorpay_sub_invoice_detail = razorpay_service_obj.fetch_invoices_for_subscription(subscription_id=razorpay_sub_id)

                if razorpay_sub_detail:
                    try:
                        loan_response["e_mandate_payment_track"] = {
                            "start_at": unix_to_yyyy_mm_dd(razorpay_sub_detail.get("start_at")),
                            "end_at": unix_to_yyyy_mm_dd(razorpay_sub_detail.get("end_at")),
                            "charge_at": unix_to_yyyy_mm_dd(razorpay_sub_detail.get("charge_at")),
                            "auth_attempts": razorpay_sub_detail.get("auth_attempts"),
                            "paid_count": razorpay_sub_detail.get("paid_count"),
                            "total_count": razorpay_sub_detail.get("total_count"),
                            "remaining_count": razorpay_sub_detail.get("remaining_count"),
                            "status":razorpay_sub_detail.get("status"),
                            "latest_paid_at": unix_to_yyyy_mm_dd(get_latest_paid_at(razorpay_sub_invoice_detail)) if razorpay_sub_invoice_detail else None,
                        }
                    except Exception as e:
                        print(f"Error processing e_mandate_payment_track: {e}")
                        loan_response["e_mandate_payment_track"] = {}
                loan_response["approval_details"] = [
                    {
                        "id": approval_detail.id,
                        "applicant_id": approval_detail.applicant_id,
                        "user_accepted_amount": approval_detail.user_accepted_amount,
                        "disbursed_amount": approval_detail.disbursed_amount,
                        "approved_interest_rate": approval_detail.approved_interest_rate,
                        "approved_processing_fee": approval_detail.approved_processing_fee,
                        "approved_tenure_months": approval_detail.approved_tenure_months
                    }
                for approval_detail in loan_with_docs.approval_details ]

                loan_response["loan_approved_document"] = [
                    {
                        "id": approved_document.id,
                        "document_name": approved_document.document_name,
                        "document_file": approved_document.document_file,
                        "is_deleted": approved_document.is_deleted,
                    }
                    for approved_document in loan_with_docs.loan_approved_document]

                loan_response["bank_accounts"] = [
                        {
                            "id": bank_account.id,
                            "applicant_id": bank_account.applicant_id,
                            "account_number": bank_account.account_number,
                            "account_holder_name": bank_account.account_holder_name,
                            "bank_name": bank_account.bank_name,
                            "ifsc_code": bank_account.ifsc_code
                        }
                    for bank_account in loan_with_docs.bank_accounts ]
                loan_response["documents"] = formatted_documents

                loan_response["loan_disbursement"] = [
                    {
                        "id": loan_disbursement_obj.id,
                        "applicant_id": loan_disbursement_obj.applicant_id,
                        "payment_date": loan_disbursement_obj.payment_date,
                        "transferred_amount": loan_disbursement_obj.transferred_amount,
                        "payment_type": loan_disbursement_obj.payment_type,
                        "bank_name": loan_disbursement_obj.bank_name,
                        "account_number": loan_disbursement_obj.account_number,
                        "account_holder_name": loan_disbursement_obj.account_holder_name,
                        "payment_file": loan_disbursement_obj.payment_file,
                        "cheque_number": loan_disbursement_obj.cheque_number,
                        "ifsc_code": loan_disbursement_obj.ifsc_code,
                        "upi_id": loan_disbursement_obj.upi_id,
                        "transaction_id": loan_disbursement_obj.transaction_id,
                        "remarks": loan_disbursement_obj.remarks
                    }
                    for loan_disbursement_obj in loan_with_docs.loan_disbursement]
                loan_response["documents"] = formatted_documents

                effective_processing_fee = self.get_effective_processing_fee(loan_with_docs)

                gst_charge = app_config.GST_CHARGE
                if loan_with_docs.approved_loan and loan_with_docs.status == "APPROVED":
                    emi_result = calculate_emi_schedule(
                        loan_amount=loan_with_docs.approved_loan,
                        tenure_months=loan_with_docs.tenure_months,
                        annual_interest_rate=loan_response["effective_interest_rate"],
                        processing_fee=effective_processing_fee,
                        is_fee_percentage=True,
                        loan_type=loan_with_docs.loan_type
                    )

                    if emi_result.get("success"):
                        loan_response["emi_info"] = emi_result["data"]
                    else:
                        loan_response["emi_info"] = {}

                    processing_fee = ((effective_processing_fee * loan_with_docs.approved_loan) / 100)
                    other_charges = ((processing_fee * int(gst_charge)) / 100)
                    charges = processing_fee + other_charges
                    loan_response["charges"] = charges
                    loan_response["processing_fee_charge"] = processing_fee
                    loan_response["other_charges"] = other_charges

                elif loan_with_docs.approved_loan and loan_with_docs.status in ["USER_ACCEPTED", "DISBURSED", "COMPLETED", "CLOSED", "E_MANDATE_GENERATED", "BANK_VERIFIED", "DISBURSEMENT_APPROVAL_PENDING"]:
                    user_filter = [
                        LoanApprovalDetail.applicant_id == loan_application_id
                    ]
                    loan_approval_detail = (
                        session.query(LoanApprovalDetail)
                        .join(LoanApprovalDetail.applicant)
                        .filter(*user_filter)
                        .first()
                    )

                    if loan_approval_detail:
                        emi_result = calculate_emi_schedule(
                            loan_amount=loan_approval_detail.user_accepted_amount,
                            tenure_months=loan_approval_detail.approved_tenure_months,
                            annual_interest_rate=loan_approval_detail.approved_interest_rate,
                            processing_fee=effective_processing_fee,
                            is_fee_percentage=True,
                            loan_type=loan_with_docs.loan_type
                        )
                        if emi_result.get("success"):
                            loan_response["emi_info"] = emi_result["data"]
                        else:
                            # loan_response["emi_info"] = {"error": emi_result["message"]}
                            loan_response["emi_info"] = {}
                    else:
                        # loan_response["emi_info"] = {"error": "Approved loan not set"}
                        loan_response["emi_info"] = {}

                    processing_fee = ((effective_processing_fee * loan_approval_detail.user_accepted_amount) / 100)
                    other_charges = ((processing_fee * int(gst_charge)) / 100)
                    charges = processing_fee + other_charges
                    loan_response["charges"] = charges
                    loan_response["processing_fee_charge"] = processing_fee
                    loan_response["other_charges"] = other_charges
                else:
                    loan_response["emi_info"] = {}
                    loan_response["charges"] = 0.0
                    loan_response["processing_fee_charge"] = 0.0
                    loan_response["other_charges"] = 0.0
            return {
                "success": True,
                "message": gettext("retrieved_successfully").format("Loan Application"),
                "status_code": status.HTTP_200_OK,
                "data": {"loan_application": loan_response}
            }
        except Exception as e:
            app_logger.error(
                f"{gettext('error_fetching_data_from_db').format('Loan Application')} {user_id}: {str(e)}",
                exc_info=True
            )
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {
                    "error": str(e)
                }

            }

    async def upload_files_to_s3(self, file_type: UploadFileType, files: List[UploadFile]):
        try:
            upload_results = []
            aws_client = AWSClient()
            for file in files:
                validate_file_type(file)
                filename = f"{uuid.uuid4().hex}_{file.filename}"
                file_bytes = await file.read()

                upload_response = await aws_client.upload_to_s3(
                    file_name=filename,
                    binary_data=file_bytes,
                    file_type=file_type.value
                )
                app_logger.info(f"File uploaded: {upload_response['s3_object_url']}")
                upload_results.append(upload_response)
            return {
                "success": True,
                "message": gettext("uploaded_successfully").format("File"),
                "status_code": status.HTTP_200_OK,
                "data": upload_results,
            }

        except Exception as e:
            app_logger.error(f"Error uploading files to S3: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }

    def add_user_approved_loan(self, user_id: int, loan_application_form: UserApprovedLoanForm):
        approval_interface = DBInterface(LoanApprovalDetail)
        applicant_interface = DBInterface(LoanApplicant)

        try:
            app_logger.info(
                f"[add_user_approved_loan] Starting approval process for applicant_id: {loan_application_form.applicant_id}"
            )

            gst_charge = app_config.GST_CHARGE
            processing_fee = ((loan_application_form.approved_processing_fee * loan_application_form.user_accepted_amount) / 100)
            other_charges = ((processing_fee * int(gst_charge)) / 100)
            charges = processing_fee + other_charges

            # Step 1: Create LoanApprovalDetail
            approval_data = {
                "applicant_id": loan_application_form.applicant_id,
                "approved_interest_rate": loan_application_form.approved_interest_rate,
                "final_interest_rate": loan_application_form.final_interest_rate,
                "custom_interest_rate": loan_application_form.custom_interest_rate if loan_application_form.custom_interest_rate != 0 else None,
                "approved_processing_fee": loan_application_form.approved_processing_fee,
                "processing_fee_amount": loan_application_form.processing_fee_amount,
                "custom_processing_fee": loan_application_form.custom_processing_fee if loan_application_form.custom_processing_fee != 0 else None,
                "approved_tenure_months": loan_application_form.approved_tenure_months,
                "final_tenure_months": loan_application_form.final_tenure_months,
                "user_accepted_amount": loan_application_form.user_accepted_amount,
                "approved_loan_amount": loan_application_form.approved_loan_amount,
                "created_by": user_id,
                "modified_by": user_id,
                "disbursed_amount": loan_application_form.user_accepted_amount - charges
            }

            approval_instance = approval_interface.create(approval_data)
            app_logger.info(f"[add_user_approved_loan] LoanApprovalDetail created: ID {approval_instance.id}")

            # Step 2: Update LoanApplicant status
            updated_applicant = applicant_interface.update(
                _id=str(loan_application_form.applicant_id),
                data={
                    "status": LoanStatus.USER_ACCEPTED,
                    "modified_by": user_id
                }
            )
            app_logger.info(f"[add_user_approved_loan] LoanApplicant status updated to USER_ACCEPTED")

            return {
                "success": True,
                "message": gettext("approved_successfully"),
                "status_code": status.HTTP_200_OK,
                "data": {
                    "loan_approval_detail": approval_instance,
                    "loan_applicant": updated_applicant
                }
            }

        except Exception as e:
            print(str(e))
            app_logger.error(f"[add_user_approved_loan] Failed to approve loan: {str(e)}")
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }


    def calculate_emi_for_instant_cash(self, user_id: int, loan_application_form: InstantCashForm):

        try:
            app_logger.info(
                f"[calculate_emi_for_instant_cash] Starting calculate emi applicant_id: {loan_application_form.applicant_id}"
            )

            emi_result = calculate_emi_schedule(
                loan_amount=loan_application_form.accepted_amount,
                tenure_months=loan_application_form.tenure_months,
                annual_interest_rate=loan_application_form.interest_rate,
                processing_fee=loan_application_form.processing_fee,
                is_fee_percentage=True,
            )

            emi = 0.0

            if emi_result["status_code"] == status.HTTP_200_OK:
                data = emi_result["data"]
                emi = data.get("monthly_emi")

            if not emi:
                app_logger.error(f"[calculate_emi_for_instant_cash] Failed for applicant_id: {loan_application_form.applicant_id}")
                return {
                    "success": False,
                    "message": gettext("something_went_wrong"),
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "data": {}
                }

            gst_charge = app_config.GST_CHARGE

            processing_fee = ((loan_application_form.processing_fee * loan_application_form.accepted_amount)/100)

            other_charges = ((processing_fee * int(gst_charge))/100)

            charges = processing_fee + other_charges

            return {
                "success": True,
                "message": gettext("instant_cash_fetched_successfully"),
                "status_code": status.HTTP_200_OK,
                "data": {
                    "loan_amount": loan_application_form.accepted_amount,
                    "emi": emi,
                    "tenure_months": loan_application_form.tenure_months,
                    "interest_rate": loan_application_form.interest_rate,
                    "charges": charges,
                    "gst_charge": int(gst_charge),
                }
            }

        except Exception as e:
            app_logger.error(f"[calculate_emi_for_instant_cash] Failed to approve loan: {str(e)}")
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }


    def update_loan_consent(self, user_id: int, loan_consent_form: LoanConsentForm):

        try:
            app_logger.info(
                f"[update_loan_consent] applicant_id: {loan_consent_form.applicant_id}"
            )

            if not self.db_interface.exists_by_id(_id=str(loan_consent_form.applicant_id)):
                return {
                    "success": False,
                    "message": "Loan Data not exists.",
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "data": {}
                }

            loan_data = loan_consent_form.model_dump(exclude_unset=True)
            loan_data['modified_by'] = user_id
            loan_updated_instance = self.db_interface.update(_id=str(loan_consent_form.applicant_id), data=loan_data)
            app_logger.info(f"{gettext('updated_successfully').format('Loan Consent')}: {loan_updated_instance}")

            return {
                "success": True,
                "message": gettext("loan_consent_updated_successfully"),
                "status_code": status.HTTP_200_OK,
                "data": {
                }
            }

        except Exception as e:
            app_logger.error(f"[update_loan_consent] Failed to update loan consent: {str(e)}")
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }

    def apply_for_disbursement(self, user_id: int, loan_disbursement_form: LoanDisbursementForm):

        try:
            app_logger.info(
                f"[apply_for_disbursement] applicant_id: {loan_disbursement_form.applicant_id}"
            )

            if not self.db_interface.exists_by_id(_id=str(loan_disbursement_form.applicant_id)):
                return {
                    "success": False,
                    "message": "Loan Data not exists.",
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "data": {}
                }

            loan_data = loan_disbursement_form.model_dump(exclude_unset=True)
            loan_data['modified_by'] = user_id
            loan_data['disbursement_apply_date'] = datetime.now(ZoneInfo("Asia/Kolkata"))
            loan_data['is_disbursement_manual'] = True
            loan_data['status'] = LoanStatus.DISBURSEMENT_APPROVAL_PENDING
            loan_updated_instance = self.db_interface.update(_id=str(loan_disbursement_form.applicant_id), data=loan_data)
            app_logger.info(f"{gettext('updated_successfully').format('Loan Disbursement data')}: {loan_updated_instance}")

            return {
                "success": True,
                "message": gettext("loan_disbursement_updated_successfully"),
                "status_code": status.HTTP_200_OK,
                "data": {
                }
            }

        except Exception as e:
            app_logger.error(f"[apply_for_disbursement] Failed to update loan consent: {str(e)}")
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }

    def update_aadhar_verify_status(self, user_id: int, loan_aadhar_verify_form: LoanAadharVerifiedStatusForm):

        try:
            app_logger.info(
                f"[update_aadhar_verify_status] applicant_id: {loan_aadhar_verify_form.applicant_id}"
            )

            if not self.db_interface.exists_by_id(_id=str(loan_aadhar_verify_form.applicant_id)):
                return {
                    "success": False,
                    "message": "Loan Data not exists.",
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "data": {}
                }

            loan_data = loan_aadhar_verify_form.model_dump(exclude_unset=True)
            loan_data['modified_by'] = user_id
            loan_data['status'] = LoanStatus.AADHAR_VERIFIED
            loan_updated_instance = self.db_interface.update(_id=str(loan_aadhar_verify_form.applicant_id), data=loan_data)
            app_logger.info(f"{gettext('updated_successfully').format('Loan Aadhar verify status')}: {loan_updated_instance}")

            return {
                "success": True,
                "message": gettext("aadhar_status_update_successfully"),
                "status_code": status.HTTP_200_OK,
                "data": {
                }
            }

        except Exception as e:
            app_logger.error(f"[update_aadhar_verify_status] Failed to update loan aadhar verify status: {str(e)}")
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }