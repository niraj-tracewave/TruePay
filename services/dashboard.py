from starlette import status

from common.enums import LoanStatus
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
            # Total Loans
            loan_filter = [LoanApplicant.is_deleted == False]
            total_loans = self.db_interface.count_all_by_fields(loan_filter)

            # Total Pending Loans
            pending_loan_filter = [LoanApplicant.is_deleted == False, LoanApplicant.status == LoanStatus.PENDING]
            total_pending_loans = self.db_interface.count_all_by_fields(pending_loan_filter)

            # Total Approved Loans
            approved_loan_filter = [LoanApplicant.is_deleted == False, LoanApplicant.status == LoanStatus.APPROVED]
            total_approved_loans = self.db_interface.count_all_by_fields(approved_loan_filter)

            # Total Rejected Loans
            rejected_loan_filter = [LoanApplicant.is_deleted == False, LoanApplicant.status == LoanStatus.REJECTED]
            total_rejected_loans = self.db_interface.count_all_by_fields(rejected_loan_filter)

            # Total Cancelled Loans
            cancelled_loan_filter = [LoanApplicant.is_deleted == False, LoanApplicant.status == LoanStatus.CANCELLED]
            total_cancelled_loans = self.db_interface.count_all_by_fields(cancelled_loan_filter)

            # Total Users
            user_interface = DBInterface(User)
            user_fiter = [User.is_deleted == False]
            total_users = user_interface.count_all_by_fields(user_fiter)

            return {
                "success": True,
                "message": "Counts of Loans",
                "data": {
                    "total_loans": total_loans,
                    "total_pending_loans": total_pending_loans,
                    "total_approved_loans": total_approved_loans,
                    "total_cancelled_loans": total_cancelled_loans,
                    "total_rejected_loans": total_rejected_loans,
                    "total_users": total_users,
                },
                "status_code": status.HTTP_200_OK,
            }
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
                "data": {},
                "status_code": status.HTTP_400_BAD_REQUEST,

            }
