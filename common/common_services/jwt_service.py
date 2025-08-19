import datetime
from typing import Any

import jwt
from fastapi import status
from starlette.responses import JSONResponse

from app_logging import app_logger
from common.cache_string import gettext
from common.response import ApiResponse
from config import app_config


class JWTService:
    """
        A service class for handling JWT-based authentication, including access token and refresh token generation,
        verification, and revocation.
    """

    # Secret keys (Load from environment variables)
    SECRET_KEY = app_config.JWT_SECRET_KEY
    REFRESH_SECRET_KEY = app_config.JWT_REFRESH_SECRET_KEY
    ALGORITHM = "HS256"

    # Token Expiry Durations
    ACCESS_TOKEN_EXPIRY_MINUTES = 150
    REFRESH_TOKEN_EXPIRY_DAYS = 7

    REVOKED_REFRESH_TOKENS = set()

    @classmethod
    def create_tokens(cls, data: dict, is_refresh: bool = True) -> JSONResponse | dict[str, Any]:
        """
        Generates both access and refresh tokens with respective expiration times.

        Args:
            data (dict): The payload data to encode in the tokens.
            is_refresh (bool, optional): Indicates whether to generate a refresh token. Defaults to False.

        Returns:
            dict: A dictionary containing both access and refresh tokens.
        """
        try:
            now = datetime.datetime.now(datetime.UTC)
            data_dict = {}

            # Create Access Token
            access_payload = data.copy()
            access_payload.update({"exp": now + datetime.timedelta(minutes=cls.ACCESS_TOKEN_EXPIRY_MINUTES)})
            access_token = jwt.encode(access_payload, cls.SECRET_KEY, algorithm=cls.ALGORITHM)
            data_dict["access_token"] = access_token

            if is_refresh:
                # Create Refresh Token
                refresh_payload = data.copy()
                refresh_payload.update({"exp": now + datetime.timedelta(days=cls.REFRESH_TOKEN_EXPIRY_DAYS)})
                refresh_token = jwt.encode(refresh_payload, cls.REFRESH_SECRET_KEY, algorithm=cls.ALGORITHM)
                data_dict["refresh_token"] = refresh_token

            return data_dict

        except Exception as e:
            return ApiResponse.create_response(success=False, message=f"Error generating tokens: {str(e)}",
                                               status_code=status.HTTP_400_BAD_REQUEST)

    @classmethod
    def revoke_refresh_token(cls, refresh_token: str) -> JSONResponse | Any | None:
        """
            Invalidates a refresh token by adding it to a revoked token list.

            Args:
                refresh_token (str): The refresh token to revoke.
        """
        try:
            cls.REVOKED_REFRESH_TOKENS.add(refresh_token)
            return None
        except Exception as e:
            return ApiResponse.create_response(success=False, message=f"Error revoking refresh token: {str(e)}",
                                               status_code=status.HTTP_400_BAD_REQUEST)

    @classmethod
    def is_refresh_token_revoked(cls, refresh_token: str) -> JSONResponse | bool:
        """
            Checks if a given refresh token has been revoked.

            Args:
                refresh_token (str): The refresh token to check.

            Returns:
                bool: True if the token is revoked, False otherwise.
        """
        try:
            return refresh_token in cls.REVOKED_REFRESH_TOKENS
        except Exception as e:
            return ApiResponse.create_response(success=False,
                                               message=f"Error checking refresh token revocation: {str(e)}",
                                               status_code=status.HTTP_400_BAD_REQUEST)

    @classmethod
    def verify_access_token(cls, token: str) -> JSONResponse | Any:
        """
        Verifies and decodes the given access token.

        Args:
            token (str): The JWT access token.

        Returns:
            dict: The decoded payload.

        Raises:
            HTTPException: If the token is invalid or expired.
        """
        try:
            return jwt.decode(token, cls.SECRET_KEY, algorithms=[cls.ALGORITHM])
        except jwt.ExpiredSignatureError:
            return ApiResponse.create_response(success=False, message=gettext("token_expired"),
                                               status_code=status.HTTP_403_FORBIDDEN)
        except jwt.InvalidTokenError:
            return ApiResponse.create_response(success=False, message=gettext("invalid_token"),
                                               status_code=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            print(f"ERROR ===> {e}")
            return ApiResponse.create_response(success=False, message=f"Error verifying access token: {str(e)}",
                                               status_code=status.HTTP_400_BAD_REQUEST)

    @classmethod
    def refresh_token(cls, token: str) -> JSONResponse | dict[str, bool | int | Any] | Any:
        """
            Verifies and decodes the given refresh token.

            Args:
                token (str): The JWT refresh token.

            Returns:
                dict: The decoded payload.

            Raises:
                HTTPException: If the token is invalid, expired, or revoked.
            """
        try:
            if cls.is_refresh_token_revoked(token):
                return ApiResponse.create_response(success=False, message=gettext("invalid_token"),
                                                   status_code=status.HTTP_410_GONE)

            payload = jwt.decode(token, cls.REFRESH_SECRET_KEY, algorithms=[cls.ALGORITHM])
            app_logger.error(f"JWT ERROR ===> {payload}")
            filtered_payload = {k: v for k, v in payload.items() if k not in ["exp", "iat", "nbf"]}
            app_logger.error(f"JWT ERROR 2 ===> {filtered_payload}")

            return cls.create_tokens(filtered_payload, is_refresh=False)
        except (jwt.ExpiredSignatureError, Exception):
            return {
                "success": False,
                "message": gettext("token_expired"),
                "status_code": status.HTTP_410_GONE,
            }
        except jwt.InvalidTokenError:
            return {
                "success": False,
                "message": gettext("invalid_token"),
                "status_code": status.HTTP_410_GONE,
            }
