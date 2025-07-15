import json

import jwt
from fastapi import Request
from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware

from app_logging import app_logger
from common.cache_string import gettext
from common.common_services.jwt_service import JWTService
from common.response import ApiResponse
from config import app_config

# Initialize JWT service
jwt_service_obj = JWTService()
SECRET_KEY = app_config.JWT_SECRET_KEY

# Public paths with a full prefix
PUBLIC_PATHS = {
    "user": [
        "/api/base/user/send-otp",
        "/api/base/user/verify-otp",
        "/api/base/user/register",
        "/api/base/user/refresh-token",
    ],
    "admin": [
        "/api/base/admin/user/auth"
    ],
    "global": [
        "/api/base/docs",
        "/api/base/openapi.json",
        "/api/base/open-api",
        "/api/base/media"
    ]
}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Normalize request path
        request_path = request.url.path.rstrip("/")
        app_logger.info(f"[AuthMiddleware] Request path: {request_path}")

        # Combine and normalize all public paths
        all_public_paths = PUBLIC_PATHS["user"] + PUBLIC_PATHS["admin"] + PUBLIC_PATHS["global"]
        normalized_paths = [path.rstrip("/") for path in all_public_paths]
        app_logger.info(f"[AuthMiddleware] All public paths: {normalized_paths}")

        # Allow if a request matches any public path
        if request_path in normalized_paths:
            app_logger.info("[AuthMiddleware] Matched public path → skipping auth")
            return await call_next(request)

        # Require Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            app_logger.warning("[AuthMiddleware] Missing or invalid Authorization header")
            return ApiResponse.create_response(
                success=False,
                message=gettext("access_token_required"),
                status_code=status.HTTP_401_UNAUTHORIZED
            )

        # Extract token
        token = auth_header.split(" ")[1]
        app_logger.info(f"[AuthMiddleware] Found token: {token[:10]}...")

        try:
            payload = jwt_service_obj.verify_access_token(token)

            # Decode if necessary
            if not isinstance(payload, dict):
                response_body = payload.body
                payload = json.loads(response_body.decode('utf-8'))

            user_id = payload.get("id")
            if not user_id:
                app_logger.error("[AuthMiddleware] Invalid token payload: missing user ID")
                return ApiResponse.create_response(
                    success=False,
                    message=gettext("invalid_token"),
                    status_code=status.HTTP_403_FORBIDDEN
                )

            app_logger.info(f"[AuthMiddleware] Token verified | user_id: {user_id}")
            request.state.user = payload

        except jwt.ExpiredSignatureError:
            app_logger.warning("[AuthMiddleware] Token expired")
            return ApiResponse.create_response(
                success=False,
                message=gettext("token_expired"),
                status_code=status.HTTP_403_FORBIDDEN
            )

        except jwt.InvalidTokenError:
            app_logger.warning("[AuthMiddleware] Invalid token")
            return ApiResponse.create_response(
                success=False,
                message=gettext("invalid_token"),
                status_code=status.HTTP_403_FORBIDDEN
            )

        # All good, proceed
        return await call_next(request)
