from typing import Any

from starlette import status

from app_logging import app_logger
from db_domains import Base
from db_domains.db_interface import DBInterface
from models.credit import CreditScoreRange, InterestRate
from schemas.credit import CombinedLoanConfigCreate


class CreditScoreService:
    def __init__(self, db_model: type[Base]) -> None:
        self.db_class: type[Base] = db_model
        self.db_interface = DBInterface(self.db_class)

    def add_credit_score_rate_interest(self, user_id: int, form_data: CombinedLoanConfigCreate) -> Any:
        try:
            interest_rate_db_interface = DBInterface(InterestRate)

            app_logger.debug(
                f"[UserID: {user_id}] Checking if credit score range exists for min={form_data.min_score}, max={form_data.max_score}"
            )
            credit_score_range = self.db_interface.read_single_by_fields(
                fields=[
                    CreditScoreRange.min_score == form_data.min_score,
                    CreditScoreRange.max_score == form_data.max_score
                ]
            )
            if not credit_score_range:
                app_logger.info(f"[UserID: {user_id}] Creating new credit score range: {form_data.dict()}")
                credit_score_range = self.db_interface.create(
                    data={"label": form_data.label, "min_score": form_data.min_score, "max_score": form_data.max_score}
                )
            else:
                app_logger.info(f"[UserID: {user_id}] Updating existing credit score range ID={credit_score_range.id}")
                self.db_interface.update(
                    credit_score_range.id, data={
                        "label": form_data.label, "min_score": form_data.min_score, "max_score": form_data.max_score
                    }
                )

            app_logger.debug(
                f"[UserID: {user_id}] Checking if interest rate exists for loan_type={form_data.loan_type}, range_id={credit_score_range.id}"
            )
            interest_rate = interest_rate_db_interface.read_single_by_fields(
                [
                    InterestRate.credit_score_range_id == credit_score_range.id,
                    InterestRate.loan_type == form_data.loan_type,
                    InterestRate.rate_percentage == form_data.rate_percentage
                ]
            )
            if not interest_rate:
                app_logger.info(f"[UserID: {user_id}] Creating new interest rate entry")
                interest_rate_db_interface.create(
                    data={
                        "credit_score_range_id": credit_score_range.id, "rate_percentage": form_data.rate_percentage,
                        "loan_type": form_data.loan_type
                    }
                )
            else:
                app_logger.info(f"[UserID: {user_id}] Updating existing interest rate ID={interest_rate.id}")
                interest_rate_db_interface.update(
                    interest_rate.id, data={
                        "credit_score_range_id": credit_score_range.id, "rate_percentage": form_data.rate_percentage,
                        "loan_type": form_data.loan_type
                    }
                )

            return {
                "success": True,
                "message": "Credit score and interest rate updated successfully",
                "status_code": status.HTTP_200_OK,
                "data": {
                    "credit_score_range": {
                        "label": credit_score_range.label,
                        "min_score": credit_score_range.min_score,
                        "max_score": credit_score_range.max_score
                    },
                    "interest_rate": {
                        "loan_type": form_data.loan_type,
                        "rate_percentage": form_data.rate_percentage
                    }
                }
            }
        except Exception as e:
            app_logger.exception(f"Error adding credit score rate interest: {str(e)}")
            return {
                "success": False,
                "message": str(e),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }
