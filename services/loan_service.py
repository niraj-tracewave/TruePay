import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

from fastapi import UploadFile
from sqlalchemy.orm import selectinload, with_loader_criteria
from starlette import status

from app_logging import app_logger
from common.cache_string import gettext
from common.common_services.aws_services import AWSClient
from common.enums import DocumentType, IncomeProofType, LoanType, UploadFileType
from common.utils import format_loan_documents, validate_file_type
from db_domains import Base
from db_domains.db import DBSession
from db_domains.db_interface import DBInterface
from models.loan import LoanDocument, LoanApplicant
from schemas.loan_schemas import LoanForm, LoanApplicantResponseSchema, UpdateLoanForm


class UserLoanService:
    def __init__(self, db_model: type[Base]) -> None:
        self.db_class: type[Base] = db_model
        self.db_interface = DBInterface(self.db_class)

    def add_loan_application(self, user_id: str, loan_application_form: LoanForm):
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
                    .options(selectinload(LoanApplicant.documents))
                    .filter(LoanApplicant.created_by == user_id, LoanApplicant.is_deleted == False).all()
                )
            return {
                "success": True,
                "message": gettext("retrieved_successfully").format("Loan Applications") if loan_with_docs else gettext(
                    "no_module_found"
                ).format("Loan Applications"),
                "status_code": status.HTTP_200_OK if loan_with_docs else status.HTTP_404_NOT_FOUND,
                "data": {"loan_applications": loan_with_docs}
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
                formatted_documents = format_loan_documents(loan_with_docs.documents) if loan_with_docs else []
                loan_response["documents"] = formatted_documents
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


class AdminLoanService(UserLoanService):

    def get_all_loans(
            self, search: Optional[str] = None, status_filter: Optional[bool] = None,
            order_by: Optional[str] = None, order_direction: Optional[str] = None, limit: int = 10, offset: int = 0,
            start_date: Optional[str] = None, end_date: Optional[str] = None
    ):
        try:
            app_logger.info("Fetching all loan applications")

            filter_def = {
                "AND": [
                    {"field": "is_deleted", "op": "==", "value": False}
                ]
            }

            if status_filter:
                filter_def["AND"].append({"field": "status", "op": "==", "value": status_filter})

            date_format = "%Y-%m-%d"
            if start_date and end_date:
                try:
                    start = datetime.strptime(start_date, date_format)
                    end = datetime.strptime(end_date, date_format)

                    filter_def["AND"].append({"field": "created_at", "op": ">=", "value": start})
                    filter_def["AND"].append({"field": "created_at", "op": "<=", "value": end})

                except ValueError:
                    raise ValueError("Invalid date format. Use YYYY-MM-DD for both start_date and end_date.")

            # 🔍 Search filter
            if search:
                like_value = f"%{search.lower()}%"
                filter_def["AND"].append(
                    {
                        "OR": [
                            {"field": "name", "op": "ilike", "value": like_value},
                            {"field": "email", "op": "ilike", "value": like_value},
                            {"field": "phone_number", "op": "ilike", "value": like_value},
                            {"field": "loan_uid", "op": "ilike", "value": like_value}
                        ]
                    }
                )

            filter_expr = self.db_interface.build_filter_expression(filter_def)

            order_column = getattr(
                LoanApplicant, order_by, LoanApplicant.created_at
            ) if order_by else LoanApplicant.created_at
            order_direction = order_direction.lower() if order_direction else "desc"
            final_offset = offset * limit if offset > 0 else 0

            loans = self.db_interface.read_all_by_filters(
                filter_expr=filter_expr,
                order_by=order_column,
                order_direction=order_direction,
                limit=limit,
                offset=final_offset
            )

            loan_list = [LoanApplicantResponseSchema.model_validate(loan).model_dump(exclude={"documents"}) for loan in
                         loans]

            return {
                "success": True,
                "message": gettext("retrieved_successfully").format("Loan Applications") if loan_list else gettext(
                    "no_module_found"
                ).format("Loan Application"),
                "status_code": status.HTTP_200_OK if loan_list else status.HTTP_404_NOT_FOUND,
                "data": {
                    "loan_applications": loan_list,
                    "total_count": len(loan_list)
                }
            }

        except Exception as e:
            app_logger.error(f"Error retrieving loans: {e}", exc_info=True)
            return {
                "success": False,
                "message": str(e),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": []
            }

    def update_loan_applications(self, logged_in_user_id: str, loan_id: str, form_data: UpdateLoanForm):
        try:
            loan_data = form_data.model_dump(exclude_unset=True)
            loan_data = {
                k: v for k, v in loan_data.items()
                if k in [
                    "name", "email", "phone_number", "annual_income", "desired_loan", "date_of_birth", "gender",
                    "address", "company_name", "company_address", "designation", "purpose_of_loan", "status",
                    "remarks", "is_deleted", "loan_type"
                ] and v is not None
            }
            loan_data["modified_by"] = logged_in_user_id

            loan_updated_instance = self.db_interface.update(_id=loan_id, data=loan_data)
            loan_updated_data = LoanApplicantResponseSchema.model_validate(loan_updated_instance).model_dump()
            app_logger.info(f"{gettext('updated_successfully').format('Loan Applications')}: {loan_updated_data}")

            loan_document_interface = DBInterface(LoanDocument)

            # PAN Card
            if form_data.pan_number and form_data.pan_file:
                pan_filter_list = [
                    LoanDocument.applicant_id == loan_id,
                    LoanDocument.document_type == DocumentType.PAN.value,
                    LoanDocument.is_deleted == False
                ]
                pan_doc_data = {
                    "applicant_id": loan_id,
                    "document_type": DocumentType.PAN.value,
                    "document_number": form_data.pan_number,
                    "document_file": form_data.pan_file,
                    "modified_by": logged_in_user_id
                }

                existing_pan_doc = loan_document_interface.read_single_by_fields(pan_filter_list)
                if existing_pan_doc:
                    loan_document_interface.update(_id=existing_pan_doc.id, data=pan_doc_data)
                    app_logger.info("PAN document updated")
                else:
                    pan_doc_data["created_by"] = logged_in_user_id
                    loan_document_interface.create(pan_doc_data)
                    app_logger.info("PAN document created")

            # Aadhaar Card
            if form_data.aadhaar_number and form_data.aadhaar_file:
                aadhar_filter_list = [
                    LoanDocument.applicant_id == loan_id,
                    LoanDocument.document_type == DocumentType.AADHAR.value,
                    LoanDocument.is_deleted == False
                ]
                aadhar_doc_data = {
                    "applicant_id": loan_id,
                    "document_type": DocumentType.AADHAR.value,
                    "document_number": form_data.aadhaar_number,
                    "document_file": form_data.aadhaar_file,
                    "modified_by": logged_in_user_id
                }

                existing_aadhar_doc = loan_document_interface.read_single_by_fields(aadhar_filter_list)
                if existing_aadhar_doc:
                    loan_document_interface.update(_id=existing_aadhar_doc.id, data=aadhar_doc_data)
                    app_logger.info("Aadhaar document updated")
                else:
                    aadhar_doc_data["created_by"] = logged_in_user_id
                    loan_document_interface.create(aadhar_doc_data)
                    app_logger.info("Aadhaar document created")

            # Income Proofs (Other Documents)
            if form_data.proof_type in IncomeProofType.__members__.values():
                doc_filter_list = [
                    LoanDocument.applicant_id == loan_id,
                    LoanDocument.document_type == form_data.document_type.value,
                    LoanDocument.proof_type == form_data.proof_type.value,
                    LoanDocument.is_deleted == False
                ]
                existing_docs = loan_document_interface.read_by_fields(fields=doc_filter_list)
                for i, doc_file in enumerate(form_data.document_file):
                    doc_data = {
                        "applicant_id": loan_id,
                        "proof_type": form_data.proof_type.value,
                        "document_type": form_data.document_type.value,
                        "document_number": "",
                        "document_file": doc_file,
                        "modified_by": logged_in_user_id
                    }

                    if i < len(existing_docs):
                        doc_id = existing_docs[i].id
                        loan_document_interface.update(doc_id, doc_data)
                    else:
                        doc_data["created_by"] = logged_in_user_id
                        loan_document_interface.create(doc_data)

                if len(form_data.document_file) < len(existing_docs):
                    for doc in existing_docs[len(form_data.document_file):]:
                        loan_document_interface.soft_delete([LoanDocument.id == doc.id])

            # If a loan type is LAP and document_type is PROPERTY_DOCUMENTS
            if form_data.loan_type == LoanType.LAP.value:
                prop_filter_list = [
                    LoanDocument.applicant_id == loan_id,
                    LoanDocument.document_type == DocumentType.PROPERTY_DOCUMENTS,
                    LoanDocument.is_deleted == False
                ]

                existing_property_docs = loan_document_interface.read_by_fields(fields=prop_filter_list)

                if existing_property_docs:
                    for prop_doc in existing_property_docs:
                        loan_document_interface.delete([LoanDocument.id == prop_doc.id])
                    app_logger.info(f"Deleted existing PROPERTY_DOCUMENTS for LAP loan_id: {loan_id}")

                # Use property_document_file instead of document_file
                for doc_file in form_data.property_document_file:
                    doc_data = {
                        "applicant_id": loan_id,
                        "document_type": DocumentType.PROPERTY_DOCUMENTS,
                        "document_number": "",
                        "document_file": doc_file,
                        "proof_type": form_data.proof_type.value if form_data.proof_type else None,
                        "created_by": logged_in_user_id,
                        "modified_by": logged_in_user_id,
                    }
                    loan_document_interface.create(doc_data)
                    app_logger.info("New PROPERTY_DOCUMENT document created")

            return {
                "success": True,
                "message": gettext("updated_successfully").format("Loan Applications"),
                "status_code": status.HTTP_200_OK,
                "data": loan_updated_data
            }

        except Exception as e:
            app_logger.error(f"Error updating Loan with ID {loan_id}: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }

    def delete_loan_applications(self, logged_in_user_id: str, loan_id: str) -> Dict[str, Any]:
        try:
            loan_application_filter = [LoanApplicant.id == loan_id, LoanApplicant.is_deleted == False]
            if self.db_interface.soft_delete(loan_application_filter, logged_in_user_id):
                loan_document_filter = [LoanDocument.applicant_id == loan_id, LoanDocument.is_deleted == False]
                loan_document_interface = DBInterface(LoanDocument)
                loan_document_interface.soft_delete(loan_document_filter, logged_in_user_id)
            else:
                app_logger.error(f"Error deleting Loan with ID {loan_id}")
                return {
                    "success": False,
                    "message": gettext("not_found").format("Loan Application"),
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "data": {}
                }
            return {
                "success": True,
                "message": gettext("deleted_successfully").format("Loan Application"),
                "status_code": status.HTTP_200_OK,
                "data": {}
            }
        except Exception as e:
            app_logger.error(f"Error deleting Loan with ID {loan_id}: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }
