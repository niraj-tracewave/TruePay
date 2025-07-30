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
from common.enums import DocumentType, IncomeProofType, LoanType, UploadFileType
from common.utils import format_loan_documents, validate_file_type, calculate_emi_schedule
from db_domains import Base
from db_domains.db import DBSession
from db_domains.db_interface import DBInterface
from models.loan import LoanDocument, LoanApplicant
from schemas.loan_schemas import LoanForm, LoanApplicantResponseSchema


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

    def add_loan_application(self, user_id: str, loan_application_form: LoanForm, background_tasks: BackgroundTasks):
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
            doc_creator = lambda doc_type, number, file, proof_type=None: {
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
                        loan_application_form.pan_file
                    )
                )
                app_logger.info("PAN document prepared for upload.")

            # Aadhaar document
            if loan_application_form.aadhaar_number and loan_application_form.aadhaar_file:
                all_documents.append(
                    doc_creator(
                        DocumentType.AADHAR.value,
                        loan_application_form.aadhaar_number,
                        loan_application_form.aadhaar_file
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
            
            #NOTE: SEND EMAIL before sending successfully returning added
            try:
                # Prepare email
                subject = "New Loan Application Submitted"
                recipient =  os.environ.get("RECIPIENT_ADMIN_EMAIL", "") 
                email_service_obj = EmailService()
                #NOTE: backup format [ignore for now]
                # plain_body = (
                #     f"Dear {loan_application_form.name},\n\n"
                #     f"Thank you for applying for a loan with us.\n\n"
                #     f"Applicant ID: {applicant_id}\n"
                #     f"Loan Type: {loan_application_form.loan_type.name}\n"
                #     f"Requested Loan Amount: ₹{loan_application_form.desired_loan}\n"
                #     f"..."
                # )
                # html_body = f"""
                # <html>
                #     <body>
                #         <p>Dear {loan_application_form.name},</p>
                #         <p>Thank you for applying for a loan with us.</p>
                #         <h4>Your Application Details:</h4>
                #         <ul>
                #             <li><strong>Applicant ID:</strong> {applicant_id}</li>
                #             <li><strong>Loan Type:</strong> {loan_application_form.loan_type.name}</li>
                #             <li><strong>Requested Loan Amount:</strong> ₹{loan_application_form.desired_loan}</li>
                #             <li><strong>Annual Income:</strong> ₹{loan_application_form.annual_income}</li>
                #             <li><strong>Credit Score:</strong> {loan_application_form.credit_score if loan_application_form.credit_score else 'N/A'}</li>
                #             <li><strong>Purpose of Loan:</strong> {loan_application_form.purpose_of_loan}</li>
                #         </ul>
                #         <p>Our team will review your application and get back to you shortly.</p>
                #         <p>Regards,<br/>Loan Processing Team</p>
                #     </body>
                # </html>
                # """
                plain_body = (
                    f"Information:\n"
                    f"A new loan application has been submitted.\n\n"
                    f"🧾 Applicant Details:\n"
                    f"Name: {loan_application_form.name}\n"
                    f"Email: {loan_application_form.email}\n"
                    f"Phone: {loan_application_form.phone_number}\n"
                    f"Loan UID: {applicant_id}\n"
                    f"Desired Loan Amount: ₹{loan_application_form.desired_loan}\n"
                    f"Applied At: {applicant_obj.created_at.strftime('%d-%m-%Y %I:%M %p') if applicant_obj.created_at else 'N/A'}\n\n"
                    f"Thanks & Regards,\n"
                    f"Loan Processing Team"
                )
                html_body = f"""
                <html>
                    <body>
                        <p>A new loan application has been submitted.</p>
                        <h4>Applicant Details:</h4>
                        <ul>
                            <li><strong>Name:</strong> {loan_application_form.name}</li>
                            <li><strong>Email :</strong> {loan_application_form.email}</li>
                            <li><strong>Phone:</strong> {loan_application_form.phone_number}</li>
                            <li><strong>Loan UID:</strong> {applicant_obj.loan_uid}</li>
                            <li><strong>Desired Loan Amount:</strong>₹ {loan_application_form.desired_loan}</li>
                            <li><strong>Applied At:</strong> {applicant_obj.created_at.strftime('%d-%m-%Y %I:%M %p') if applicant_obj.created_at else "N/A"} </li>
                        </ul>
                        <p>Kindly go to <a href="https://admin.truepay.co.in/">https://admin.truepay.co.in/</a> admin panel and check the details.</p>
                        <p>Thanks & Regards,<br/>   TruePay Loan Processing Team</p>
                    </body>
                </html>
                """
                if os.environ.get("IS_PROD").lower() == "true":
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
                    .options(selectinload(LoanApplicant.documents), selectinload(LoanApplicant.credit_score_range_rate))
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
                    "documents": [
                        {
                            "id": doc.id,
                            "proof_type": doc.proof_type,
                            "document_type": doc.document_type,
                            "document_number": doc.document_number,
                            "document_file": doc.document_file,
                        } for doc in loan.documents
                    ]
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
                loan_response["effective_interest_rate"] = self.get_effective_rate(loan_with_docs)
                formatted_documents = format_loan_documents(loan_with_docs.documents) if loan_with_docs else []
                loan_response["documents"] = formatted_documents

                if loan_with_docs.approved_loan and loan_with_docs.status == "APPROVED":
                    emi_result = calculate_emi_schedule(
                        loan_amount=loan_with_docs.approved_loan,
                        tenure_months=12,
                        annual_interest_rate=loan_response["effective_interest_rate"],
                        processing_fee=2.0,
                        is_fee_percentage=True
                    )

                    if emi_result.get("success"):
                        loan_response["emi_info"] = emi_result["data"]
                    else:
                        loan_response["emi_info"] = {"error": emi_result["message"]}
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
