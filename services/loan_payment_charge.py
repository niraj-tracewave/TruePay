from datetime import datetime
from typing import Any

from starlette import status

from app_logging import app_logger
from db_domains import Base
from db_domains.db_interface import DBInterface
from models.loan import Charges
from schemas.loan_payment_charge import ChargeCreate, ChargeUpdate


class LoanPaymentChargeScheduleService:
    def __init__(self, db_model: type[Base]) -> None:
        self.db_class: type[Base] = db_model
        self.db_interface = DBInterface(self.db_class)

    def add_charge(self, user_id: int, form_data: ChargeCreate) -> Any:
        try:
            self.db_interface = DBInterface(Charges)

            app_logger.info(
                f"[UserID: {user_id}] Checking if entry exists for charges : {form_data.status.value}"
            )
            existing_entry = self.db_interface.read_single_by_fields(
                fields=[
                    Charges.status == form_data.status.value,
                    Charges.is_deleted == False,
                ]
            )

            if existing_entry:
                return {
                    "success": False,
                    "message": "Payment charges already exists.",
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "data": {}
                }

            data = {
                "amount": form_data.amount,
                "status": form_data.status,
            }

            app_logger.info(
                f"[UserID: {user_id}] Creating new charge entry: {form_data.dict()}"
            )
            data["created_by"] = user_id
            new_entry = self.db_interface.create(data=data)

            return {
                "success": True,
                "message": "Payment charges added successfully.",
                "status_code": status.HTTP_200_OK,
                "data": {
                    "emi_schedule_entry": {
                        "id": new_entry.id,
                        "status": new_entry.status,
                        "amount": new_entry.amount,
                    }
                }
            }

        except Exception as e:
            app_logger.exception(f"[UserID: {user_id}] Error adding charge: {str(e)}")
            return {
                "success": False,
                "message": str(e),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }

    def update_charge(
            self, user_id: int, charge_id: int, form_data: ChargeUpdate
    ):
        try:

            # Read the existing combined entry
            existing_entry = self.db_interface.read_by_id(charge_id)
            if not existing_entry:
                return {
                    "success": False,
                    "message": f"Charge with ID {charge_id} not found.",
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "data": {}
                }

            # Prepare update fields based on provided data
            update_fields = {}
            if form_data.status is not None:
                update_fields["status"] = form_data.status
            if form_data.amount is not None:
                update_fields["amount"] = form_data.amount
            if form_data.is_deleted is not None:
                update_fields["is_deleted"] = form_data.is_deleted
                update_fields["deleted_at"] = datetime.now()

            if update_fields:
                update_fields["modified_by"] = user_id
                app_logger.info(
                    f"[UserID: {user_id}] Updating Charge ID={charge_id} with: {update_fields}"
                )
                self.db_interface.update(_id=str(charge_id), data=update_fields)

            return {
                "success": True,
                "message": "Charge updated successfully.",
                "status_code": status.HTTP_200_OK,
                "data": {
                    "credit_range_rate": {
                        "id": charge_id,
                        **update_fields
                    }
                }
            }

        except Exception as e:
            app_logger.exception(f"[UserID: {user_id}] Error updating charge: {str(e)}")
            return {
                "success": False,
                "message": "Something went wrong during update.",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }

    def get_all_charges(self, user_id: int) -> dict:
        try:
            charge_db_interface = DBInterface(Charges)
            all_entries = charge_db_interface.read_all()
            if not all_entries:
                return {
                    "success": True,
                    "message": "No charge entry found",
                    "status_code": status.HTTP_200_OK,
                    "data": {}
                }
            result = [
                {
                    "id": entry.id,
                    "status": entry.status,
                    "amount": entry.amount,
                    "is_deleted": entry.is_deleted
                }
                for entry in all_entries
            ]

            return {
                "success": True,
                "message": "Fetched all charge entries",
                "status_code": status.HTTP_200_OK,
                "data": {"charges": result}
            }

        except Exception as e:
            app_logger.exception(f"[UserID: {user_id}] Error fetching charge: {str(e)}")
            return {
                "success": False,
                "message": "Failed to fetch charge date entries",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }

    def get_charge_detail(self, user_id: int, charge_id: int) -> dict:
        try:
            charge_db_interface = DBInterface(Charges)
            entry = charge_db_interface.read_by_id(charge_id)
            if not entry:
                return {
                    "success": False,
                    "message": f"Charge with ID {charge_id} not found",
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "data": {}
                }

            return {
                "success": True,
                "message": "Charge detail fetch successfully",
                "status_code": status.HTTP_200_OK,
                "data": {
                    "charge": {
                        "id": entry.id,
                        "status": entry.status,
                        "amount": entry.amount,
                        "is_deleted": entry.is_deleted
                    }
                }
            }

        except Exception as e:
            app_logger.exception(f"[UserID: {user_id}] Error fetching charge detail: {str(e)}")
            return {
                "success": False,
                "message": "Failed to fetch charge detail",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }
