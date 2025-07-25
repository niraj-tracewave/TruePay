from fastapi import APIRouter, Request
from starlette import status

from common.response import ApiResponse
from models.credit import CreditScoreRangeRate
from schemas.credit_schemas import CombinedLoanConfigCreate, CombinedLoanConfigUpdate
from services.credit import CreditScoreService

router = APIRouter(prefix="/admin/credit", tags=["Admin Panel Credit API's"])
credit_service = CreditScoreService(CreditScoreRangeRate)


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


@router.put("/update-credit-interest/{credit_id}")
def update_credit_score_rate_interest(request: Request, credit_id: int, data: CombinedLoanConfigUpdate):
    user_state = getattr(request.state, "user", {})

    response = credit_service.update_credit_score_rate_interest(
        user_id=user_state.get("id"), credit_range_id=credit_id, form_data=data
    )
    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )


@router.get("/credit-score-interest", response_model=dict)
def get_all_credit_score_interest(request: Request):
    user_state = getattr(request.state, "user", {})
    response = credit_service.get_all_credit_range_rates(user_id=user_state.get("id"))

    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )


@router.get("/credit-score-interest/{credit_range_id}", response_model=dict)
def get_credit_score_interest_detail(request: Request, credit_range_id: int):
    user_state = getattr(request.state, "user", {})
    response = credit_service.get_credit_range_rate_detail(
        user_id=user_state.get("id"), credit_range_id=credit_range_id
    )

    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )
