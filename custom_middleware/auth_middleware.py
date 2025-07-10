import json

import jwt
from fastapi import Request
from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware

from common.cache_string import gettext
from common.common_services.jwt_service import JWTService
from common.response import ApiResponse
from config import app_config

SECRET_KEY = app_config.JWT_SECRET_KEY
jwt_service_obj = JWTService()

PUBLIC_PATHS = {
    "user": [
        "/user/send-otp",
        "/user/verify-otp",
        "/user/register",
        "/user/refresh-token",
    ],
    "admin": [
        "/admin/user/auth"
    ],
    "global": [
        "/docs", "/openapi.json", "/open-api", "/media/"
    ]
}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Combine all public routes
        all_public_paths = PUBLIC_PATHS["user"] + PUBLIC_PATHS["admin"] + PUBLIC_PATHS["global"]

        if any(request.url.path.startswith(path) for path in all_public_paths):
            return await call_next(request)

        # Get Authorization Header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return ApiResponse.create_response(
                success=False,
                message=gettext("access_token_required"),
                status_code=status.HTTP_401_UNAUTHORIZED
            )

        # Extract Token
        token = auth_header.split(" ")[1]

        try:
            payload = jwt_service_obj.verify_access_token(token)
            if not isinstance(payload, dict):
                response_body = payload.body
                payload = json.loads(response_body.decode('utf-8'))
            user_id = payload.get("id")
            if not user_id:
                return ApiResponse.create_response(
                    success=False,
                    message=gettext("invalid_token"),
                    status_code=status.HTTP_403_FORBIDDEN
                )

            request.state.user = payload

        except jwt.ExpiredSignatureError:
            return ApiResponse.create_response(
                success=False,
                message=gettext("token_expired"),
                status_code=status.HTTP_403_FORBIDDEN
            )

        except jwt.InvalidTokenError:
            return ApiResponse.create_response(
                success=False,
                message=gettext("invalid_token"),
                status_code=status.HTTP_403_FORBIDDEN
            )

        # Proceed with request
        response = await call_next(request)
        return response
