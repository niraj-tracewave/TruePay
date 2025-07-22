from fastapi import APIRouter, Request

from common.response import ApiResponse
from schemas.surpass_schemas import GetCibilReportData, PanCardDetails
from services.surpass_service import SurpassService

router = APIRouter(prefix="/surpass", tags=["Surpass API's"])
surpass_service = SurpassService()


@router.post("/get-cibil-score", summary="Get CIBIL Score")
async def get_cibil_score_api(request: Request, payload_data: GetCibilReportData):
    user_state = getattr(request.state, "user", None)
    response = await surpass_service.fetch_cibil_score(user_id=user_state.get("id"), payload_data=payload_data)
    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code"),
        data=response.get("data")
    )


@router.get("/get-cibil-report/{cibil_score_id}", summary="Get CIBIL Report")
async def get_cibil_report_api(request: Request, cibil_score_id: int):
    user_state = getattr(request.state, "user", None)
    response = await surpass_service.fetch_cibil_report(user_id=user_state.get("id"), cibil_score_id=cibil_score_id)
    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code"),
        data=response.get("data")
    )


@router.post("/validate-pan-card", summary="Validate Pan Card.")
async def validate_pan_card(request: Request, pan_detail: PanCardDetails):
    user_state = getattr(request.state, "user", None)
    response = await surpass_service.validate_pan_card(user_id=user_state.get("id"), pan_detail=pan_detail)
    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code"),
        data=response.get("data")
    )
