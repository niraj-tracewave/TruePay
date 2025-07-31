from fastapi import APIRouter
from starlette import status

from common.response import ApiResponse
from models.loan import LoanApplicant
from services.dashboard import DashboardService

router = APIRouter(prefix="/admin/dashboard", tags=["Dashboard API's"])
dashboard_service = DashboardService(LoanApplicant)


@router.get("/get-counts", summary="Get All Counts")
async def get_counts():
    response = dashboard_service.get_counts()

    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code") if response.get("status_code") else status.HTTP_200_OK,
        data=response.get("data")
    )
