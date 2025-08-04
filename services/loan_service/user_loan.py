import os
import uuid
from typing import Dict, Any, List, Optional

from fastapi import UploadFile, BackgroundTasks
from sqlalchemy.orm import selectinload, with_loader_criteria
from starlette import status

from app_logging import app_logger
from common.cache_string import gettext
from common.common_services.aws_services import AWSClient
from common.common_services.email_service import EmailService
from common.email_html_utils import build_loan_email_bodies
from common.enums import DocumentType, IncomeProofType, LoanType, UploadFileType, LoanStatus
from common.utils import format_loan_documents, validate_file_type, calculate_emi_schedule
from db_domains import Base
from db_domains.db import DBSession
from db_domains.db_interface import DBInterface
from models.loan import LoanDocument, LoanApplicant, LoanApprovalDetail
from schemas.loan_schemas import LoanForm, LoanApplicantResponseSchema, UserApprovedLoanForm


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
                "data": {}
            }

    def get_loan_applications(self, user_id: str) -> Dict[str, Any]:
        try:
            app_logger.info(f"Fetching all loan applications for user: {user_id}")
            with DBSession() as session:
                loan_with_docs = (
                    session.query(LoanApplicant)
                    .options(selectinload(LoanApplicant.documents),  selectinload(LoanApplicant.bank_accounts), selectinload(LoanApplicant.credit_score_range_rate))
                    .filter(LoanApplicant.created_by == user_id, LoanApplicant.is_deleted == False)
                    .all()
                )
            loan_list = []
            for loan in loan_with_docs:
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
                    for bank_account in loan.bank_accounts ]
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
                "data": {}
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
                        selectinload(LoanApplicant.credit_score_range_rate),
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
                loan_response = LoanApplicantResponseSchema.model_validate(loan_with_docs).model_dump()
                loan_response["min_loan_amount"]=100
                loan_response["min_tenure_months"]=12
                loan_response["max_tenure_months"]=loan_with_docs.tenure_months
                loan_response["tenure_months_steps"]=6
                loan_response["effective_interest_rate"] = self.get_effective_rate(loan_with_docs)
                formatted_documents = format_loan_documents(loan_with_docs.documents) if loan_with_docs else []
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

                effective_processing_fee = self.get_effective_processing_fee(loan_with_docs)

                if loan_with_docs.approved_loan and loan_with_docs.status == "APPROVED":
                    emi_result = calculate_emi_schedule(
                        loan_amount=loan_with_docs.approved_loan,
                        tenure_months=loan_with_docs.tenure_months,
                        annual_interest_rate=loan_response["effective_interest_rate"],
                        processing_fee=effective_processing_fee,
                        is_fee_percentage=True
                    )

                    if emi_result.get("success"):
                        loan_response["emi_info"] = emi_result["data"]
                    else:
                        loan_response["emi_info"] = {"error": emi_result["message"]}
                elif loan_with_docs.approved_loan and loan_with_docs.status == "USER_ACCEPTED":
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
                            is_fee_percentage=True
                        )
                        if emi_result.get("success"):
                            loan_response["emi_info"] = emi_result["data"]
                        else:
                            loan_response["emi_info"] = {"error": emi_result["message"]}
                    else:
                        loan_response["emi_info"] = {"error": "Approved loan not set"}
                else:
                    loan_response["emi_info"] = {"error": "Approved loan not set"}
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
                "data": {}
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
                "modified_by": user_id
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
            app_logger.error(f"[add_user_approved_loan] Failed to approve loan: {str(e)}")
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }
