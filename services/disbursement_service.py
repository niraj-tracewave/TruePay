from datetime import datetime
from typing import Any

from starlette import status

from app_logging import app_logger
from common.enums import LoanStatus
from db_domains import Base
from db_domains.db_interface import DBInterface
from models.loan import LoanDisbursementDetail, LoanApplicant
from schemas.disbursement_schemas import LoanDisbursementForm


class LoanDisbursementService:
    def __init__(self, db_model: type[Base]) -> None:
        self.db_class: type[Base] = db_model
        self.db_interface = DBInterface(self.db_class)


    def add_disbursement_history(self, user_id: int, form_data: LoanDisbursementForm) -> Any:
        try:
            self.db_interface = DBInterface(LoanDisbursementDetail)

            app_logger.info(
                f"[UserID: {user_id}] add disbursement history for applicant_id : {form_data.applicant_id}"
            )
            existing_entry = self.db_interface.read_by_fields(fields=[
                    LoanDisbursementDetail.applicant_id == form_data.applicant_id,
                    LoanDisbursementDetail.is_deleted == False,
                ])
            if existing_entry:
                self.db_interface.update(
                    _id=str(form_data.applicant_id),
                    data={"is_deleted": True, "modified_by": user_id},
                    lookup_field="applicant_id",
                    update_all=True
                )
            if not existing_entry:
                loan_disbursement_detail_interface = DBInterface(LoanApplicant)
                update_fields = {
                    "modified_by": user_id,
                    "status": LoanStatus.DISBURSED.value,
                    "available_for_disbursement": False,
                }
                loan_disbursement_detail_interface.update(_id=str(form_data.applicant_id), data=update_fields)

            data = form_data.model_dump(exclude_unset=True)
            data["created_by"] = user_id
            new_entry = self.db_interface.create(data=data)

            return {
                "success": True,
                "message": "Disbursement History Added successfully",
                "status_code": status.HTTP_200_OK,
                "data": {
                    "disbursement_history": {
                        "id": new_entry.id,
                        "applicant_id": new_entry.applicant_id,
                        "payment_type": new_entry.payment_type.value,
                        "payment_date": new_entry.payment_date,
                        "transferred_amount": new_entry.transferred_amount,
                    }
                }
            }

        except Exception as e:
            app_logger.exception(f"[UserID: {user_id}] Error adding disbursement history: {str(e)}")
            return {
                "success": False,
                "message": str(e),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }