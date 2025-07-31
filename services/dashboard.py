from starlette import status

from app_logging import app_logger
from common.enums import LoanStatus, UserRole
from config import app_config
from db_domains import Base
from db_domains.db_interface import DBInterface
from models.loan import LoanApplicant
from models.user import User


class DashboardService:
    def __init__(self, db_model: type[Base]) -> None:
        self.db_class: type[Base] = db_model
        self.db_interface = DBInterface(self.db_class)
        self.S3_BUCKET_URL = app_config.S3_BUCKET_URL

    def get_counts(self):
        try:
            app_logger.info("Starting to fetch loan and user counts.")

            # Total Loans
            loan_filter = [LoanApplicant.is_deleted == False]
            total_loans = self.db_interface.count_all_by_fields(loan_filter)
            app_logger.info(f"Total loans count fetched: {total_loans}")

            # Total Pending Loans
            pending_loan_filter = [LoanApplicant.is_deleted == False, LoanApplicant.status == LoanStatus.PENDING]
            total_pending_loans = self.db_interface.count_all_by_fields(pending_loan_filter)
            app_logger.info(f"Total pending loans count fetched: {total_pending_loans}")

            # Total Approved Loans
            approved_loan_filter = [LoanApplicant.is_deleted == False, LoanApplicant.status == LoanStatus.APPROVED]
            total_approved_loans = self.db_interface.count_all_by_fields(approved_loan_filter)
            app_logger.info(f"Total approved loans count fetched: {total_approved_loans}")

            # Total Rejected Loans
            rejected_loan_filter = [LoanApplicant.is_deleted == False, LoanApplicant.status == LoanStatus.REJECTED]
            total_rejected_loans = self.db_interface.count_all_by_fields(rejected_loan_filter)
            app_logger.info(f"Total rejected loans count fetched: {total_rejected_loans}")

            # Total Canceled Loans
            cancelled_loan_filter = [LoanApplicant.is_deleted == False, LoanApplicant.status == LoanStatus.CANCELLED]
            total_cancelled_loans = self.db_interface.count_all_by_fields(cancelled_loan_filter)
            app_logger.info(f"Total cancelled loans count fetched: {total_cancelled_loans}")

            # Total Hold Loans
            hold_loan_filter = [LoanApplicant.is_deleted == False, LoanApplicant.status == LoanStatus.ON_HOLD]
            total_hold_loans = self.db_interface.count_all_by_fields(hold_loan_filter)
            app_logger.info(f"Total Hold loans count fetched: {total_hold_loans}")

            # Total Hold Loans
            closed_loan_filter = [LoanApplicant.is_deleted == False, LoanApplicant.status == LoanStatus.CLOSED]
            total_closed_loans = self.db_interface.count_all_by_fields(closed_loan_filter)
            app_logger.info(f"Total Hold loans count fetched: {total_closed_loans}")

            # Total Users
            user_interface = DBInterface(User)
            user_filter = [User.is_deleted == False, User.role == UserRole.user]
            total_users = user_interface.count_all_by_fields(user_filter)
            app_logger.info(f"Total users count fetched: {total_users}")

            app_logger.info("Successfully fetched all counts.")

            return {
                "success": True,
                "message": "Counts of Loans",
                "data": {
                    "total_loans": total_loans,
                    "total_pending_loans": total_pending_loans,
                    "total_approved_loans": total_approved_loans,
                    "total_cancelled_loans": total_cancelled_loans,
                    "total_rejected_loans": total_rejected_loans,
                    "total_hold_loans": total_hold_loans,
                    "total_closed_loans": total_closed_loans,
                    "total_users": total_users,
                },
                "status_code": status.HTTP_200_OK,
            }

        except Exception as e:
            app_logger.error(f"Error fetching counts: {e}", exc_info=True)
            return {
                "success": False,
                "message": str(e),
                "data": {},
                "status_code": status.HTTP_400_BAD_REQUEST,
            }
