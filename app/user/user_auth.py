from fastapi import APIRouter, Request
from starlette import status

from common.response import ApiResponse
from models.user import User
from schemas.auth_schemas import LoginRequest, VerifyOTPRequest, RefreshToken, UpdateProfileRequest
from services.auth_service import UserAuthService

router = APIRouter(prefix="/user", tags=["User Authentication API's"])
auth_service = UserAuthService(User)


@router.post("/send-otp", summary="Send OTP for Login")
async def send_otp(request: Request, login_request: LoginRequest):
    response = auth_service.send_otp(login_request=login_request)
    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data"),
    )


@router.post("/verify-otp", summary="Verify OTP for Login")
async def verify_otp(verify_otp_request: VerifyOTPRequest):
    response = auth_service.verify_otp(verify_otp_request=verify_otp_request)
    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data"),
    )


@router.post("/refresh-token", summary="Refresh Access Token")
async def refresh_token(token: RefreshToken):
    response = auth_service.refresh_token(token)
    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )


@router.put("/update-profile/{user_id}", summary="Update User Profile")
async def update_profile(user_id: str, form_data: UpdateProfileRequest):
    response = auth_service.update_profile(user_id, form_data=form_data)

    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code") if response.get("status_code") else status.HTTP_200_OK,
        data=response.get("data") if response.get("data") else []
    )


@router.get("/get-profile/{user_id}", summary="Get User Profile")
async def get_profile(user_id: str):
    response = auth_service.get_profile_details(user_id)

    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code") if response.get("status_code") else status.HTTP_200_OK,
        data=response.get("data") if response.get("data") else []
    )