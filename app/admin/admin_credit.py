from fastapi import APIRouter, Request
from starlette import status

from common.response import ApiResponse
from models.credit import CreditScoreRange
from schemas.credit import CombinedLoanConfigCreate
from services.credit import CreditScoreService

router = APIRouter(prefix="/admin/credit", tags=["Admin Panel Credit API's"])
credit_service = CreditScoreService(CreditScoreRange)


@router.post("/add-credit-interest")
def add_credit_score_rate_interest(request: Request, data: CombinedLoanConfigCreate):
    user_state = getattr(request.state, "user", {})

    response = credit_service.add_credit_score_rate_interest(user_id=user_state.get("id"), form_data=data)
    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )
