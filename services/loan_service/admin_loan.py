from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from starlette import status

from app_logging import app_logger
from common.cache_string import gettext
from common.enums import DocumentType, IncomeProofType, LoanType
from db_domains.db_interface import DBInterface
from models.credit import CreditScoreRangeRate
from models.loan import LoanDocument, LoanApplicant
from schemas.loan_schemas import LoanApplicantResponseSchema, UpdateLoanForm
from services.loan_service.user_loan import UserLoanService


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
            total_loans = self.db_interface.count_all_by_fields(
                filters=[LoanApplicant.is_deleted == False]
            )

            if status_filter:
                filter_def["AND"].append({"field": "status", "op": "==", "value": status_filter})

            date_format = "%Y-%m-%d"
            if start_date and end_date:
                try:
                    start = datetime.strptime(start_date, date_format)
                    end = datetime.strptime(end_date, date_format) + timedelta(days=1) - timedelta(seconds=1)

                    filter_def["AND"].append({"field": "created_at", "op": ">=", "value": start})
                    filter_def["AND"].append({"field": "created_at", "op": "<=", "value": end})

                except ValueError:
                    raise ValueError("Invalid date format. Use YYYY-MM-DD for both start_date and end_date.")

            # 🔍 Search filter
            if search and search.strip() != "":
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

            if offset != 0:
                final_offset = (offset - 1) * limit
            else:
                final_offset = offset

            loans = self.db_interface.read_all_by_filters(
                filter_expr=filter_expr,
                order_by=order_column,
                order_direction=order_direction,
                limit=limit,
                offset=final_offset
            )

            loan_list = []
            credit_score_range_rate = DBInterface(CreditScoreRangeRate)
            for loan in loans:
                loan_data = LoanApplicantResponseSchema.model_validate(loan).model_dump(exclude={"documents"})

                # Fetch matching interest rate info for this loan's type
                rate_entry = credit_score_range_rate.read_by_fields(
                    fields=[CreditScoreRangeRate.loan_type == loan.loan_type]
                )

                # Attach rate info if available
                if rate_entry:
                    credit_score_rate_info = [{
                        "id": i.id,
                        "min_score": i.min_score,
                        "max_score": i.max_score,
                        "rate_percentage": i.rate_percentage
                    } for i in rate_entry]
                    loan_data["credit_score_rate_info"] = credit_score_rate_info
                else:
                    loan_data["credit_score_rate_info"] = {}

                loan_list.append(loan_data)

            return {
                "success": True,
                "message": gettext("retrieved_successfully").format("Loan Applications") if loan_list else gettext(
                    "no_module_found"
                ).format("Loan Application"),
                "status_code": status.HTTP_200_OK if loan_list else status.HTTP_404_NOT_FOUND,
                "data": {
                    "loan_applications": loan_list,
                    "total_count": total_loans
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
                    "remarks", "is_deleted", "loan_type", "approved_loan", "interest_rate",
                    "credit_score_range_rate_id", "credit_score_range_rate_percentage", "custom_rate_percentage",
                    "processing_fee", "processing_fee_id", "custom_processing_fee", "tenure_months"
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

    def get_all_user_approved_loans(
            self, search: Optional[str] = None, status_filter: Optional[List[str]] = None,
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
            total_loans = self.db_interface.count_all_by_fields(
                filters=[LoanApplicant.is_deleted == False]
            )

            if status_filter:
                filter_def["AND"].append({
                    "field": "status",
                    "op": "in",
                    "value": status_filter
                })
            date_format = "%Y-%m-%d"
            if start_date and end_date:
                try:
                    start = datetime.strptime(start_date, date_format)
                    end = datetime.strptime(end_date, date_format) + timedelta(days=1) - timedelta(seconds=1)

                    filter_def["AND"].append({"field": "created_at", "op": ">=", "value": start})
                    filter_def["AND"].append({"field": "created_at", "op": "<=", "value": end})

                except ValueError:
                    raise ValueError("Invalid date format. Use YYYY-MM-DD for both start_date and end_date.")

            # 🔍 Search filter
            if search and search.strip() != "":
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

            if offset != 0:
                final_offset = (offset - 1) * limit
            else:
                final_offset = offset

            loans = self.db_interface.read_all_by_filters(
                filter_expr=filter_expr,
                order_by=order_column,
                order_direction=order_direction,
                limit=limit,
                offset=final_offset
            )

            loan_list = []
            credit_score_range_rate = DBInterface(CreditScoreRangeRate)
            for loan in loans:
                loan_data = LoanApplicantResponseSchema.model_validate(loan).model_dump(exclude={"documents"})

                # Fetch matching interest rate info for this loan's type
                rate_entry = credit_score_range_rate.read_by_fields(
                    fields=[CreditScoreRangeRate.loan_type == loan.loan_type]
                )

                # Attach rate info if available
                if rate_entry:
                    credit_score_rate_info = [{
                        "id": i.id,
                        "min_score": i.min_score,
                        "max_score": i.max_score,
                        "rate_percentage": i.rate_percentage
                    } for i in rate_entry]
                    loan_data["credit_score_rate_info"] = credit_score_rate_info
                else:
                    loan_data["credit_score_rate_info"] = {}

                loan_list.append(loan_data)

            return {
                "success": True,
                "message": gettext("retrieved_successfully").format("Loan Applications") if loan_list else gettext(
                    "no_module_found"
                ).format("Loan Application"),
                "status_code": status.HTTP_200_OK if loan_list else status.HTTP_404_NOT_FOUND,
                "data": {
                    "loan_applications": loan_list,
                    "total_count": total_loans
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