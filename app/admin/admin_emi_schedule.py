from fastapi import APIRouter, Request
from starlette import status

from common.response import ApiResponse
from models.loan import EmiScheduleDate
from schemas.emi_schedule_schemas import EmiScheduleCreate, EmiScheduleUpdate
from services.emi_schedule_service import EmiScheduleService

router = APIRouter(prefix="/admin/emi-schedule-date", tags=["Admin Panel Emi schedule Date API's"])
credit_service = EmiScheduleService(EmiScheduleDate)


@router.post("/add-emi-schedule-date")
def add_credit_score_rate_interest(request: Request, data: EmiScheduleCreate):
    user_state = getattr(request.state, "user", {})
    response = credit_service.add_emi_schedule_date(user_id=user_state.get("id"), form_data=data)
    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )

#
@router.put("/update-emi-schedule-date/{emi_schedule_id}")
def update_emi_schedule_date(request: Request, emi_schedule_id: int, data: EmiScheduleUpdate):
    user_state = getattr(request.state, "user", {})

    response = credit_service.update_emi_schedule_date(
        user_id=user_state.get("id"), emi_schedule_id=emi_schedule_id, form_data=data
    )
    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )


@router.get("/get-all-emi-schedule-dates")
def get_all_emi_schedule_dates(request: Request):
    user_state = getattr(request.state, "user", {})
    response = credit_service.get_all_emi_schedule_dates(user_id=user_state.get("id"))
    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )


@router.get("/get-emi-schedule-date-details/{emi_schedule_id}")
def get_processing_fee_details(request: Request, emi_schedule_id: int):
    user_state = getattr(request.state, "user", {})
    response = credit_service.get_emi_schedule_date_detail(user_id=user_state.get("id"), emi_schedule_id=emi_schedule_id)
    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )
