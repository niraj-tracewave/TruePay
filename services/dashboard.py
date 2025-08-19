from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette import status

from app_logging import app_logger
from common.enums import LoanStatus, UserRole
from config import app_config
from db_domains import Base
from db_domains.db import DBSession
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

            # Total User Accepted Loans
            user_accepted_loan_filter = [
                LoanApplicant.is_deleted == False, LoanApplicant.status == LoanStatus.USER_ACCEPTED
            ]
            total_user_accepted_loans = self.db_interface.count_all_by_fields(user_accepted_loan_filter)
            app_logger.info(f"Total Hold loans count fetched: {total_user_accepted_loans}")

            session: Session = DBSession()
            db_results = (
                session.query(
                    LoanApplicant.status,
                    func.count().label("count")
                )
                .filter(LoanApplicant.is_deleted == False)
                .group_by(LoanApplicant.status)
                .all()
            )

            # Build dict with default 0 for all LoanStatus
            status_counts = {loan_status.name: 0 for loan_status in LoanStatus}
            for db_status, count in db_results:
                status_key = db_status.name if isinstance(db_status, LoanStatus) else str(db_status)
                status_counts[status_key] = count
            total_loans = sum(status_counts.values())
            status_counts["TOTAL_LOAN"] = total_loans

            app_logger.info(f"[Dashboard] Loan status counts: {status_counts}")
            print(status_counts)

            # Total Users
            user_interface = DBInterface(User)
            user_filter = [User.is_deleted == False, User.role == UserRole.user]
            total_users = user_interface.count_all_by_fields(user_filter)
            status_counts["TOTAL_USERS"] = total_users
            app_logger.info(f"Total users count fetched: {total_users}")

            app_logger.info("Successfully fetched all counts.")

            return {
                "success": True,
                "message": "Counts of Loans",
                "data": status_counts,
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
