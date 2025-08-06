from fastapi import APIRouter, Request
from starlette import status

from common.response import ApiResponse
from models.loan import LoanDisbursementDetail
from schemas.disbursement_schemas import LoanDisbursementForm
from services.disbursement_service import LoanDisbursementService

router = APIRouter(prefix="/admin/loan-disbursement", tags=["Admin Disbursement API's"])
admin_disbursement_service = LoanDisbursementService(LoanDisbursementDetail)



@router.post("/add-disbursement-payment-history", summary="Add Loan Disbursement History")
def update_loan_consent(request: Request, form_data: LoanDisbursementForm):
    user_state = getattr(request.state, "user", None)

    response = admin_disbursement_service.add_disbursement_history(user_id=user_state.get("id"), form_data=form_data)
    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )