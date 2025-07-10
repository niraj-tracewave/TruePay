from typing import Optional

from fastapi import APIRouter, Request, Query
from starlette import status

from common.response import ApiResponse
from models.user import User
from schemas.auth_schemas import AdminLoginRequest, AddUserRequest, UserUpdateData
from services.auth_service import AdminAuthService

router = APIRouter(prefix="/admin/user", tags=["User Authentication API's"])
admin_auth_service = AdminAuthService(User)


@router.post("/auth", summary="Admin Authentication")
def admin_authentication(request: Request, login_request: AdminLoginRequest):
    response = admin_auth_service.login(login_request=login_request)

    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )


@router.get("/get-all-user", summary="Admin Authentication")
def get_all_users(
        search: Optional[str] = Query(None, description="Search text for name, phone, email"),
        status_filter: Optional[str] = Query(None, description="Filter by User Active - InActive Status"),
        order_by: Optional[str] = Query(None, description="Field Name to Order By"),
        order_direction: Optional[str] = Query(None, description="Field Name to Order Direction"),
        limit: int = Query(10, description="Number of items per page"),
        offset: int = Query(0, description="Number of items to skip")
):
    response = admin_auth_service.get_all_users(
        search=search, status_filter=status_filter,
        order_by=order_by, order_direction=order_direction, limit=limit, offset=offset
    )

    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )


@router.get("/get-user-details/{user_id}", summary="Get User Details")
def get_users_details(user_id: str):
    response = admin_auth_service.get_profile_details(user_id)

    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data") if response.get("data") else []
    )


@router.post("/add-user", summary="Add User")
def add_user(request: Request, form_data: AddUserRequest):
    response = admin_auth_service.create_user(form_data)

    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )


@router.put("/update-user/{user_id}", summary="Update User Details")
async def update_user_details(user_id: str, form_data: UserUpdateData):
    response = admin_auth_service.update_user(user_id, form_data)
    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )


@router.delete("/delete-user/{user_id}", summary="Delete User")
async def delete_user(user_id: str):
    response = admin_auth_service.delete_user(user_id)
    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )

