import json
import re

import jwt
from fastapi import Request
from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware

from app_logging import app_logger
from common.cache_string import gettext
from common.common_services.jwt_service import JWTService
from common.enums import UserRole
from common.response import ApiResponse
from config import app_config

# Initialize JWT service
jwt_service_obj = JWTService()
SECRET_KEY = app_config.JWT_SECRET_KEY

# Public paths with a full prefix
API_PREFIX = "/api/base"

PUBLIC_PATHS = {
    "user": [
        "/user/send-otp",
        "/user/verify-otp",
        "/user/register",
        "/user/refresh-token"
    ],
    "admin": [
        "/admin/user/auth"
    ],
    "global": [
        "/docs",
        "/openapi.json",
        "/open-api",
        "/media"
    ],
    "razorpay":[
        "/razorpay/webhook"
    ],
    "general":[
        "/contact-us/create-contact-message"
    ]
    
}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Normalize request path
        request_path = request.url.path.rstrip("/")
        app_logger.info(f"[AuthMiddleware] Request path: {request_path}")

        # Combine and normalize all public paths
        all_public_paths = PUBLIC_PATHS["user"] + PUBLIC_PATHS["admin"] + PUBLIC_PATHS["global"] + PUBLIC_PATHS["razorpay"] + PUBLIC_PATHS["general"]
        regex_patterns = []

        for path in all_public_paths:
            path = path.rstrip("/")

            # Generate both the base-prefixed and short variants
            full_path = f"{API_PREFIX}{path}"
            short_path = path

            for variant in [full_path, short_path]:
                # Convert FastAPI-style path params ({param}) to regex
                pattern = re.sub(r"{[^/]+}", r"[^/]+", variant)
                pattern = f"^{pattern}$"
                regex_patterns.append(pattern)

        # Match against regex patterns
        for pattern in regex_patterns:
            if re.fullmatch(pattern, request_path):
                app_logger.info(f"[AuthMiddleware] Matched public path via regex → skipping auth: {pattern}")
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
            user_role = payload.get("user_role")
            if not user_id:
                app_logger.error("[AuthMiddleware] Invalid token payload: missing user ID")
                return ApiResponse.create_response(
                    success=False,
                    message=gettext("invalid_token"),
                    status_code=status.HTTP_403_FORBIDDEN
                )

            app_logger.info(f"[AuthMiddleware] Token verified | user_id: {user_id}")

            # is_admin_route = request_path.startswith(f"{API_PREFIX}/admin")
            # if is_admin_route and user_role != UserRole.admin:
            #     app_logger.warning("[AuthMiddleware] Non-admin tried accessing admin route")
            #     return ApiResponse.create_response(
            #         success=False,
            #         message=gettext("unauthorized_access"),
            #         status_code=status.HTTP_403_FORBIDDEN
            #     )

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
