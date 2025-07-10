from typing import Optional

from fastapi import APIRouter, Query, Request
from starlette import status

from common.response import ApiResponse
from models.loan import LoanApplicant
from schemas.loan_schemas import LoanForm, UpdateLoanForm
from services.loan_service import AdminLoanService

router = APIRouter(prefix="/admin/loan", tags=["Admin Panel Loan API's"])
admin_loan_service = AdminLoanService(LoanApplicant)


@router.get("/get-all-loans", summary="Get All Loan Application")
def get_all_loans(
        search: Optional[str] = Query(None, description="Search text for name, phone, email"),
        status_filter: Optional[str] = Query(None, description="Filter by User Active - InActive Status"),
        order_by: Optional[str] = Query(None, description="Field Name to Order By"),
        order_direction: Optional[str] = Query(None, description="Field Name to Order Direction"),
        limit: int = Query(10, description="Number of items per page"),
        offset: int = Query(0, description="Number of items to skip"),
        start_date: Optional[str] = Query(None, description="Start Date for Range Filter"),
        end_date: Optional[str] = Query(None, description="End Date for Range Filter"),
):
    response = admin_loan_service.get_all_loans(
        search=search, status_filter=status_filter, order_by=order_by, order_direction=order_direction, limit=limit,
        offset=offset, start_date=start_date, end_date=end_date
    )

    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )


@router.get("/get-loan-details/{loan_id}", summary="Get Loan Details")
def get_all_loan(loan_id: str):
    response = admin_loan_service.get_loan_application_details(loan_application_id=loan_id)

    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )


@router.post("/create-loan-application", summary="Create Loan Application")
async def create_loan_application(request: Request, form_data: LoanForm):
    user_state = getattr(request.state, "user", None)
    response = admin_loan_service.add_loan_application(user_id=user_state.get("id"), loan_application_form=form_data)

    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )

@router.put("/update-loan-application/{loan_id}", summary="Update Loan Application")
async def update_loan_application(request: Request, loan_id: str, form_data: UpdateLoanForm):
    user_state = getattr(request.state, "user", None)

    response = admin_loan_service.update_loan_applications(logged_in_user_id=user_state.get("id"), loan_id=loan_id, form_data=form_data)

    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code") if response.get("status_code") else status.HTTP_200_OK,
        data=response.get("data")
    )
