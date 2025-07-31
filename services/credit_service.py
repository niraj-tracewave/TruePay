from datetime import datetime
from typing import Any

from starlette import status

from app_logging import app_logger
from db_domains import Base
from db_domains.db_interface import DBInterface
from models.credit import CreditScoreRangeRate, ProcessingFee
from schemas.credit_schemas import CombinedLoanConfigCreate, CombinedLoanConfigUpdate, ProcessingFeeCreate, \
    ProcessingFeeUpdate


class CreditScoreService:
    def __init__(self, db_model: type[Base]) -> None:
        self.db_class: type[Base] = db_model
        self.db_interface = DBInterface(self.db_class)

    def add_credit_score_rate_interest(self, user_id: int, form_data: CombinedLoanConfigCreate) -> Any:
        try:
            self.db_interface = DBInterface(CreditScoreRangeRate)

            app_logger.info(
                f"[UserID: {user_id}] Checking if combined entry exists for min={form_data.min_score}, "
                f"max={form_data.max_score}, loan_type={form_data.loan_type}"
            )
            existing_entry = self.db_interface.read_single_by_fields(
                fields=[
                    CreditScoreRangeRate.min_score == form_data.min_score,
                    CreditScoreRangeRate.max_score == form_data.max_score,
                    CreditScoreRangeRate.loan_type == form_data.loan_type,
                    CreditScoreRangeRate.is_deleted == False,
                ]
            )

            if existing_entry:
                return {
                    "success": False,
                    "message": "Interest Rate already exists for this Credit Score range and Loan Type",
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "data": {}
                }

            data = {
                "label": form_data.label,
                "min_score": form_data.min_score,
                "max_score": form_data.max_score,
                "loan_type": form_data.loan_type,
                "rate_percentage": form_data.rate_percentage
            }

            app_logger.info(
                f"[UserID: {user_id}] Creating new credit score + interest rate entry: {form_data.dict()}"
            )
            data["created_by"] = user_id
            print(f"Data => {data}")
            new_entry = self.db_interface.create(data=data)

            return {
                "success": True,
                "message": "Credit score and interest rate added successfully",
                "status_code": status.HTTP_200_OK,
                "data": {
                    "credit_range_rate": {
                        "id": new_entry.id,
                        "label": new_entry.label,
                        "min_score": new_entry.min_score,
                        "max_score": new_entry.max_score,
                        "loan_type": new_entry.loan_type.value,
                        "rate_percentage": new_entry.rate_percentage
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

    def update_credit_score_rate_interest(
            self, user_id: int, credit_range_id: int, form_data: CombinedLoanConfigUpdate
    ):
        try:

            # Read the existing combined entry
            existing_entry = self.db_interface.read_by_id(credit_range_id)
            if not existing_entry:
                return {
                    "success": False,
                    "message": f"CreditScoreRangeRate with ID {credit_range_id} not found.",
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "data": {}
                }

            # Prepare update fields based on provided data
            update_fields = {}
            if form_data.label is not None:
                update_fields["label"] = form_data.label
            if form_data.min_score is not None:
                update_fields["min_score"] = form_data.min_score
            if form_data.max_score is not None:
                update_fields["max_score"] = form_data.max_score
            if form_data.rate_percentage is not None:
                update_fields["rate_percentage"] = form_data.rate_percentage
            if form_data.is_deleted is not None:
                update_fields["is_deleted"] = form_data.is_deleted
                update_fields["deleted_at"] = datetime.now()

            if update_fields:
                update_fields["modified_by"] = user_id
                app_logger.info(
                    f"[UserID: {user_id}] Updating CreditScoreRateCombined ID={credit_range_id} with: {update_fields}"
                )
                self.db_interface.update(_id=str(credit_range_id), data=update_fields)

            return {
                "success": True,
                "message": "Credit score rate information updated successfully",
                "status_code": status.HTTP_200_OK,
                "data": {
                    "credit_range_rate": {
                        "id": credit_range_id,
                        **update_fields
                    }
                }
            }

        except Exception as e:
            app_logger.exception(f"[UserID: {user_id}] Error updating CreditScoreRateCombined: {str(e)}")
            return {
                "success": False,
                "message": "Something went wrong during update.",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }

    def get_all_credit_range_rates(self, user_id: int) -> dict:
        try:
            all_entries = self.db_interface.read_by_fields(fields=[CreditScoreRangeRate.is_deleted == False])
            result = [
                {
                    "id": entry.id,
                    "label": entry.label,
                    "min_score": entry.min_score,
                    "max_score": entry.max_score,
                    "loan_type": entry.loan_type.value,
                    "rate_percentage": entry.rate_percentage
                }
                for entry in all_entries
            ]

            return {
                "success": True,
                "message": "Fetched all credit score ranges with interest rates",
                "status_code": status.HTTP_200_OK,
                "data": {"credit_range_rates": result}
            }

        except Exception as e:
            app_logger.exception(f"[UserID: {user_id}] Error fetching all credit score rate entries: {str(e)}")
            return {
                "success": False,
                "message": "Failed to fetch credit range rate data",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }

    def get_credit_range_rate_detail(self, user_id: int, credit_range_id: int) -> dict:
        try:
            entry = self.db_interface.read_by_id(credit_range_id)
            if not entry:
                return {
                    "success": False,
                    "message": f"CreditScoreRateCombined with ID {credit_range_id} not found",
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "data": {}
                }

            return {
                "success": True,
                "message": "Fetched credit score rate detail successfully",
                "status_code": status.HTTP_200_OK,
                "data": {
                    "credit_range_rate": {
                        "id": entry.id,
                        "label": entry.label,
                        "min_score": entry.min_score,
                        "max_score": entry.max_score,
                        "loan_type": entry.loan_type.value,
                        "rate_percentage": entry.rate_percentage
                    }
                }
            }

        except Exception as e:
            app_logger.exception(f"[UserID: {user_id}] Error fetching credit score rate detail: {str(e)}")
            return {
                "success": False,
                "message": "Failed to fetch credit score detail",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }

    def add_processing_fee(self, user_id: int, form_data: ProcessingFeeCreate) -> dict:
        try:
            processing_fee_db_interface = DBInterface(ProcessingFee)
            app_logger.info(
                f"[UserID: {user_id}] Checking for existing ProcessingFee with min={form_data.min_score}, "
                f"max={form_data.max_score}"
            )

            existing_entry = processing_fee_db_interface.read_single_by_fields(
                fields=[
                    ProcessingFee.min_score == form_data.min_score,
                    ProcessingFee.max_score == form_data.max_score,
                    ProcessingFee.is_deleted == False,
                ]
            )

            if existing_entry:
                return {
                    "success": False,
                    "message": "Processing fee already exists for this Credit Score range",
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "data": {}
                }

            data = {
                "label": form_data.label,
                "min_score": form_data.min_score,
                "max_score": form_data.max_score,
                "min_fee_percent": form_data.min_fee_percent,
                "max_fee_percent": form_data.max_fee_percent,
                "created_by": user_id
            }
            app_logger.info(f"[UserID: {user_id}] Creating new ProcessingFee: {form_data.dict()}")
            new_entry = processing_fee_db_interface.create(data=data)

            return {
                "success": True,
                "message": "Processing fee saved successfully",
                "status_code": status.HTTP_200_OK,
                "data": {
                    "processing_fee": {
                        "id": new_entry.id,
                        "label": new_entry.label,
                        "min_score": new_entry.min_score,
                        "max_score": new_entry.max_score,
                        "min_fee_percent": new_entry.min_fee_percent,
                        "max_fee_percent": new_entry.max_fee_percent,
                    }
                }
            }

        except Exception as e:
            app_logger.exception(f"[UserID: {user_id}] Error saving processing fee: {str(e)}")
            return {
                "success": False,
                "message": "Failed to save processing fee",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }

    def update_processing_fee(self, user_id: int, fee_id: int, form_data: ProcessingFeeUpdate) -> dict:
        try:
            processing_fee_db_interface = DBInterface(ProcessingFee)
            existing_entry = processing_fee_db_interface.read_by_id(fee_id)
            if not existing_entry:
                return {
                    "success": False,
                    "message": f"ProcessingFee with ID {fee_id} not found",
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "data": {}
                }

            update_fields = {}
            if form_data.label is not None:
                update_fields["label"] = form_data.label
            if form_data.min_score is not None:
                update_fields["min_score"] = form_data.min_score
            if form_data.max_score is not None:
                update_fields["max_score"] = form_data.max_score
            if form_data.min_fee_percent is not None:
                update_fields["min_fee_percent"] = form_data.min_fee_percent
            if form_data.max_fee_percent is not None:
                update_fields["max_fee_percent"] = form_data.max_fee_percent
            if form_data.is_deleted is not None:
                update_fields["is_deleted"] = form_data.is_deleted
                update_fields["deleted_at"] = datetime.now()

            if update_fields:
                update_fields["modified_by"] = user_id
                app_logger.info(f"[UserID: {user_id}] Updating ProcessingFee ID={fee_id} with: {update_fields}")
                processing_fee_db_interface.update(_id=str(fee_id), data=update_fields)

            return {
                "success": True,
                "message": "Processing fee updated successfully",
                "status_code": status.HTTP_200_OK,
                "data": {
                    "processing_fee": {
                        "id": fee_id,
                        **update_fields
                    }
                }
            }

        except Exception as e:
            app_logger.exception(f"[UserID: {user_id}] Error updating processing fee: {str(e)}")
            return {
                "success": False,
                "message": "Something went wrong during update.",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }

    def get_all_processing_fees(self, user_id: int) -> dict:
        try:
            processing_fee_db_interface = DBInterface(ProcessingFee)
            all_entries = processing_fee_db_interface.read_by_fields(fields=[ProcessingFee.is_deleted == False])
            if not all_entries:
                return {
                    "success": True,
                    "message": "No processing fees found",
                    "status_code": status.HTTP_200_OK,
                    "data": {}
                }
            result = [
                {
                    "id": entry.id,
                    "label": entry.label,
                    "min_score": entry.min_score,
                    "max_score": entry.max_score,
                    "min_fee_percent": entry.min_fee_percent,
                    "max_fee_percent": entry.max_fee_percent,
                }
                for entry in all_entries
            ]

            return {
                "success": True,
                "message": "Fetched all processing fee entries",
                "status_code": status.HTTP_200_OK,
                "data": {"processing_fees": result}
            }

        except Exception as e:
            app_logger.exception(f"[UserID: {user_id}] Error fetching processing fees: {str(e)}")
            return {
                "success": False,
                "message": "Failed to fetch processing fee entries",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }

    def get_processing_fee_detail(self, user_id: int, fee_id: int) -> dict:
        try:
            processing_fee_db_interface = DBInterface(ProcessingFee)
            entry = processing_fee_db_interface.read_by_id(fee_id)
            if not entry:
                return {
                    "success": False,
                    "message": f"ProcessingFee with ID {fee_id} not found",
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "data": {}
                }

            return {
                "success": True,
                "message": "Fetched processing fee detail successfully",
                "status_code": status.HTTP_200_OK,
                "data": {
                    "processing_fee": {
                        "id": entry.id,
                        "label": entry.label,
                        "min_score": entry.min_score,
                        "max_score": entry.max_score,
                        "min_fee_percent": entry.min_fee_percent,
                        "max_fee_percent": entry.max_fee_percent,
                    }
                }
            }

        except Exception as e:
            app_logger.exception(f"[UserID: {user_id}] Error fetching processing fee detail: {str(e)}")
            return {
                "success": False,
                "message": "Failed to fetch processing fee detail",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }
