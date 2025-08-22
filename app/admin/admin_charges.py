from fastapi import APIRouter, Request
from starlette import status

from common.response import ApiResponse
from models.loan import Charges
from schemas.loan_payment_charge import ChargeCreate, ChargeUpdate
from services.loan_payment_charge import LoanPaymentChargeScheduleService

router = APIRouter(prefix="/admin/charge", tags=["Admin Panel Loan Payment Charge API's"])
charge_service = LoanPaymentChargeScheduleService(Charges)


@router.post("/add-charge")
def add_charge(request: Request, data: ChargeCreate):
    user_state = getattr(request.state, "user", {})
    response = charge_service.add_charge(user_id=user_state.get("id"), form_data=data)
    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )

@router.put("/update-charge/{charge_id}")
def update_charge(request: Request, charge_id: int, data: ChargeUpdate):
    user_state = getattr(request.state, "user", {})

    response = charge_service.update_charge(
        user_id=user_state.get("id"), charge_id=charge_id, form_data=data
    )
    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )


@router.get("/get-all-charges")
def get_all_charges(request: Request):
    user_state = getattr(request.state, "user", {})
    response = charge_service.get_all_charges(user_id=user_state.get("id"))
    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )


@router.get("/get-charge-details/{charge_id}")
def get_charge_details(request: Request, charge_id: int):
    user_state = getattr(request.state, "user", {})
    response = charge_service.get_charge_detail(user_id=user_state.get("id"), charge_id=charge_id)
    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )
