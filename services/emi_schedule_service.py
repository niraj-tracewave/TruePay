from datetime import datetime
from typing import Any

from starlette import status

from app_logging import app_logger
from db_domains import Base
from db_domains.db_interface import DBInterface
from models.loan import EmiScheduleDate
from schemas.emi_schedule_schemas import EmiScheduleCreate, EmiScheduleUpdate


class EmiScheduleService:
    def __init__(self, db_model: type[Base]) -> None:
        self.db_class: type[Base] = db_model
        self.db_interface = DBInterface(self.db_class)

    def add_emi_schedule_date(self, user_id: int, form_data: EmiScheduleCreate) -> Any:
        try:
            self.db_interface = DBInterface(EmiScheduleDate)

            app_logger.info(
                f"[UserID: {user_id}] Checking if entry exists for loantype : {form_data.emi_schedule_loan_type.value}"
            )
            existing_entry = self.db_interface.read_single_by_fields(
                fields=[
                    EmiScheduleDate.emi_schedule_loan_type == form_data.emi_schedule_loan_type.value,
                    EmiScheduleDate.is_deleted == False,
                ]
            )

            if existing_entry:
                return {
                    "success": False,
                    "message": "Emi Schedule Date already exists for this loan type.",
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "data": {}
                }

            data = {
                "emi_schedule_loan_type": form_data.emi_schedule_loan_type,
                "emi_schedule_date": form_data.emi_schedule_date,
            }

            app_logger.info(
                f"[UserID: {user_id}] Creating new emi schedule entry: {form_data.dict()}"
            )
            data["created_by"] = user_id
            new_entry = self.db_interface.create(data=data)

            return {
                "success": True,
                "message": "Emi Schedule date added successfully",
                "status_code": status.HTTP_200_OK,
                "data": {
                    "emi_schedule_entry": {
                        "id": new_entry.id,
                        "emi_schedule_loan_type": new_entry.emi_schedule_loan_type,
                        "emi_schedule_date": new_entry.emi_schedule_date,
                    }
                }
            }

        except Exception as e:
            app_logger.exception(f"[UserID: {user_id}] Error adding credit score + rate: {str(e)}")
            return {
                "success": False,
                "message": str(e),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }

    def update_emi_schedule_date(
            self, user_id: int, emi_schedule_id: int, form_data: EmiScheduleUpdate
    ):
        try:

            # Read the existing combined entry
            existing_entry = self.db_interface.read_by_id(emi_schedule_id)
            if not existing_entry:
                return {
                    "success": False,
                    "message": f"EmiScheduleDate with ID {emi_schedule_id} not found.",
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "data": {}
                }

            # Prepare update fields based on provided data
            update_fields = {}
            if form_data.emi_schedule_date is not None:
                update_fields["emi_schedule_date"] = form_data.emi_schedule_date
            if form_data.is_deleted is not None:
                update_fields["is_deleted"] = form_data.is_deleted
                update_fields["deleted_at"] = datetime.now()

            if update_fields:
                update_fields["modified_by"] = user_id
                app_logger.info(
                    f"[UserID: {user_id}] Updating EmiScheduleDate ID={emi_schedule_id} with: {update_fields}"
                )
                self.db_interface.update(_id=str(emi_schedule_id), data=update_fields)

            return {
                "success": True,
                "message": "Emi schedule date updated successfully.",
                "status_code": status.HTTP_200_OK,
                "data": {
                    "credit_range_rate": {
                        "id": emi_schedule_id,
                        **update_fields
                    }
                }
            }

        except Exception as e:
            app_logger.exception(f"[UserID: {user_id}] Error updating EmiScheduleDate: {str(e)}")
            return {
                "success": False,
                "message": "Something went wrong during update.",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }

    def get_all_emi_schedule_dates(self, user_id: int) -> dict:
        try:
            emi_schedule_db_interface = DBInterface(EmiScheduleDate)
            all_entries = emi_schedule_db_interface.read_by_fields(fields=[EmiScheduleDate.is_deleted == False])
            if not all_entries:
                return {
                    "success": True,
                    "message": "No Emi Schedule entry found",
                    "status_code": status.HTTP_200_OK,
                    "data": {}
                }
            result = [
                {
                    "id": entry.id,
                    "emi_schedule_loan_type": entry.emi_schedule_loan_type,
                    "emi_schedule_date": entry.emi_schedule_date
                }
                for entry in all_entries
            ]

            return {
                "success": True,
                "message": "Fetched all emi schedule entries",
                "status_code": status.HTTP_200_OK,
                "data": {"emi_schedule_dates": result}
            }

        except Exception as e:
            app_logger.exception(f"[UserID: {user_id}] Error fetching emi schedule date: {str(e)}")
            return {
                "success": False,
                "message": "Failed to fetch emi schedule date entries",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }

    def get_emi_schedule_date_detail(self, user_id: int, emi_schedule_id: int) -> dict:
        try:
            emi_schedule_db_interface = DBInterface(EmiScheduleDate)
            entry = emi_schedule_db_interface.read_by_id(emi_schedule_id)
            if not entry:
                return {
                    "success": False,
                    "message": f"Emi schedule date with ID {emi_schedule_id} not found",
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "data": {}
                }

            return {
                "success": True,
                "message": "Emi schedule date detail successfully",
                "status_code": status.HTTP_200_OK,
                "data": {
                    "processing_fee": {
                        "id": entry.id,
                        "emi_schedule_loan_type": entry.emi_schedule_loan_type,
                        "emi_schedule_date": entry.emi_schedule_date,
                    }
                }
            }

        except Exception as e:
            app_logger.exception(f"[UserID: {user_id}] Error fetching emi schedule date detail: {str(e)}")
            return {
                "success": False,
                "message": "Failed to fetch processing fee detail",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }
