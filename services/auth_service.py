import os
from typing import Dict, Any, Optional

from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload
from starlette import status

from app_logging import app_logger
from common.cache_string import gettext
from common.common_services.jwt_service import JWTService
from common.common_services.otp_service import OTPService
from common.common_services.sms_service import SMSService
from common.enums import UserRole, DocumentType
from common.message_template import get_otp_message
from common.utils import format_user_response, PasswordHashing
from db_domains import Base
from db_domains.db import DBSession
from db_domains.db_interface import DBInterface
from models.surpass import UserCibilReport
from models.user import User, UserDocument
from schemas.auth_schemas import LoginRequest, VerifyOTPRequest, RefreshToken, UpdateProfileRequest, AdminLoginRequest, \
    AddUserRequest, UserResponseSchema, UserUpdateData


class UserAuthService:
    def __init__(self, db_model: type[Base]) -> None:
        self.db_class: type[Base] = db_model
        self.db_interface = DBInterface(self.db_class)

    @staticmethod
    def send_otp(login_request: LoginRequest) -> Dict[str, Any]:
        phone_number = login_request.phone_number
        app_logger.info(f"Initiating OTP send process for: {phone_number}")

        try:
            whitelisted_mobile_numbers = os.getenv("WHITELIST_MOBILE_NUMBER", "")
            whitelisted_numbers = [num.strip() for num in whitelisted_mobile_numbers.split(",") if num.strip()]

            if os.getenv("ENV_FASTAPI_SERVER_TYPE") == "local":
                otp, secret = "123456", "1234567"
                app_logger.debug("Local environment detected. Using static OTP.")
            elif phone_number in whitelisted_numbers:
                otp, secret = "123456", "1234567"
                app_logger.debug("Whitelisted number detected. Using static OTP.")
            else:
                otp, secret = OTPService.generate_otp(phone_number)
                message = get_otp_message(otp)

                if not SMSService.send_sms(phone_number, message):
                    return {
                        "success": False,
                        "message": gettext("error_sending_OTP"),
                        "status_code": status.HTTP_400_BAD_REQUEST,
                        "data": {},
                    }

            return {
                "success": True,
                "message": gettext("sent_successfully").format("OTP"),
                "data": {"otp": otp, "secret": secret},
            }

        except Exception as e:
            app_logger.exception(f"Unexpected error while sending OTP to {phone_number}: {str(e)}")
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {},
            }

    def verify_otp(self, verify_otp_request: VerifyOTPRequest) -> Dict[str, Any]:
        try:
            phone_number = verify_otp_request.phone_number
            app_logger.info(f"Verifying OTP for phone: {phone_number}")

            # Fetch user from DB
            user = self.db_interface.read_single_by_fields([User.phone == phone_number])
            is_new_user = False

            if not user:
                # Create a user if not exists
                user_data = {
                    "phone": phone_number,
                    "name": None,
                    "email": None,
                    "birth_date": None,
                    "address": None,
                    "role": UserRole.user,
                    "is_active": True,
                }
                user = self.db_interface.create(user_data)
                is_new_user = True

            # OTP Verification
            whitelisted_mobile_numbers = os.getenv("WHITELIST_MOBILE_NUMBER", "")
            whitelisted_numbers = [num.strip() for num in whitelisted_mobile_numbers.split(",") if num.strip()]
            is_skip_otp = os.getenv("ENV_FASTAPI_SERVER_TYPE") == "local" or phone_number in whitelisted_numbers

            if is_skip_otp:
                app_logger.info(
                    f"OTP verification skipped due to {'local env' if os.getenv('ENV_FASTAPI_SERVER_TYPE') == 'local' else 'whitelisted number'}"
                )
                if verify_otp_request.otp == "123456":
                    success, message = True, gettext("verified_successfully").format("OTP")
                else:
                    app_logger.error(gettext("invalid_otp_or_expired"))
                    return {
                        "success": False,
                        "message": gettext("invalid_otp_or_expired"),
                        "status_code": status.HTTP_400_BAD_REQUEST,
                        "data": {}
                    }
            else:
                success, message = OTPService.verify_otp(
                    otp=verify_otp_request.otp, otp_secret=verify_otp_request.otp_secret
                )

            if not success:
                app_logger.error(message)
                return {
                    "success": False,
                    "message": message,
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "data": {}
                }

            # Generate token
            token_data = {
                "id": user.id,
                "name": user.name,
                "phone_number": user.phone,
                "email": user.email,
                "role": user.role
            }
            jwt_response = JWTService().create_tokens(token_data)

            app_logger.info(f"OTP verified. Returning user profile for phone: {phone_number}")
            with DBSession() as session:
                user_with_docs = (
                    session.query(User)
                    .options(
                        selectinload(User.documents),
                        selectinload(User.cibil_reports)
                    )
                    .filter(User.phone == phone_number)
                    .first()
                )
                res = format_user_response(user_with_docs, user_with_docs.documents)
            return {
                "success": True,
                "message": message,
                "data": {
                    "token": jwt_response,
                    "user": res,
                    "is_new_user": is_new_user
                }
            }
        except Exception as e:
            app_logger.exception(f'{gettext("error_verifying_OTP")}, Error: {e}')
            return {
                "success": False,
                "message": str(e),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": []
            }

    def refresh_token(self, refresh_token_data: RefreshToken) -> dict[str, Any]:
        try:
            app_logger.info("Refreshing access token using refresh token")

            jwt_response = JWTService().refresh_token(refresh_token_data.refresh_token)

            if not isinstance(jwt_response, dict) or not jwt_response.get("access_token"):
                app_logger.error(jwt_response.get("message", gettext("token_refresh_failed")))
                return {
                    "success": False,
                    "message": jwt_response.get("message", gettext("token_refresh_failed")),
                    "status_code": jwt_response.get("status_code", status.HTTP_410_GONE),
                    "data": []
                }

            app_logger.info(gettext("token_refreshed"))
            return {
                "success": True,
                "message": gettext("token_refreshed"),
                "data": jwt_response,
                "status_code": status.HTTP_200_OK
            }

        except Exception as e:
            app_logger.exception(f"Error refreshing token: {str(e)}")
            return {
                "success": False,
                "message": str(e),
                "status_code": status.HTTP_410_GONE,
                "data": []
            }

    def update_profile(self, user_id: str, form_data: UpdateProfileRequest) -> Dict[str, Any]:
        try:
            pan_file = form_data.pan_file
            aadhaar_file = form_data.aadhaar_file

            # Prepare user data
            user_data = form_data.model_dump(exclude_unset=True)
            user_data = {k: v for k, v in user_data.items() if
                         k in ["name", "email", "phone", "address", "profile_image"]}

            # Update user
            user_updated_obj = self.db_interface.update(_id=user_id, data=user_data)
            app_logger.info(f"Profile Updated: {user_updated_obj}")

            # Prepare UserDocument interface
            user_document_interface = DBInterface(UserDocument)

            # PAN handling
            if pan_file:
                pan_filter = [
                    UserDocument.user_id == user_id,
                    UserDocument.document_type == DocumentType.PAN
                ]
                existing_pan_doc = user_document_interface.read_single_by_fields(pan_filter)

                pan_doc_data = {
                    "user_id": user_id,
                    "document_type": DocumentType.PAN,
                    "document_number": form_data.pan_number,
                    "document_file": pan_file,
                }

                if existing_pan_doc:
                    updated_pan = user_document_interface.update(_id=existing_pan_doc.id, data=pan_doc_data)
                    app_logger.info(f"PAN document updated for user_id: {user_id}")
                else:
                    updated_pan = user_document_interface.create(pan_doc_data)
                    app_logger.info(f"PAN document created for user_id: {user_id}")

            # Aadhaar handling
            if aadhaar_file:
                aadhaar_filter = [
                    UserDocument.user_id == user_id,
                    UserDocument.document_type == DocumentType.AADHAR
                ]
                existing_aadhaar_doc = user_document_interface.read_single_by_fields(aadhaar_filter)

                aadhaar_doc_data = {
                    "user_id": user_id,
                    "document_type": DocumentType.AADHAR,
                    "document_number": form_data.aadhaar_number,
                    "document_file": aadhaar_file,
                }

                if existing_aadhaar_doc:
                    updated_aadhaar = user_document_interface.update(_id=existing_aadhaar_doc.id, data=aadhaar_doc_data)
                    app_logger.info(f"Aadhaar document updated for user_id: {user_id}")
                else:
                    updated_aadhaar = user_document_interface.create(aadhaar_doc_data)
                    app_logger.info(f"Aadhaar document created for user_id: {user_id}")

            app_logger.info(f"Profile updated successfully for user_id: {user_id}")
            with DBSession() as session:
                user_with_docs = (
                    session.query(User)
                    .options(
                        selectinload(User.documents),
                        selectinload(User.cibil_reports)
                    )
                    .filter(User.id == user_id)
                    .first()
                )
                user_details = format_user_response(user_with_docs, user_with_docs.documents)
            return {
                "success": True,
                "message": "Profile updated successfully",
                "data": {
                    "user": user_details
                },
                "status_code": status.HTTP_200_OK,
            }

        except SQLAlchemyError as e:
            app_logger.error(f"DB Error: {gettext('error_updating_data_to_db').format('Profile Details')}: {str(e)}")
            return {
                "success": False,
                "message": gettext("error_updating_data_to_db").format("Profile Update"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }

        except Exception as e:
            app_logger.error(
                f"General Error: {gettext('error_updating_data_to_db').format('Profile Details')}: {str(e)}"
            )
            return {
                "success": False,
                "message": gettext("error_updating_data_to_db").format("Profile Update"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }

    def get_profile_details(self, user_id: str) -> Dict[str, Any]:
        try:
            app_logger.info(f"Fetching profile for user_id: {user_id}")
            user_filter = [
                User.id == user_id, User.is_deleted == False, User.role == UserRole.user, User.is_active == True
            ]

            user_filter = self.db_interface.read_single_by_fields(fields=user_filter)
            if not user_filter:
                return {
                    "success": False,
                    "message": gettext("does_not_exists").format("User"),
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "data": {}
                }

            with DBSession() as session:
                user_with_docs = (
                    session.query(User)
                    .options(
                        selectinload(User.documents),
                        selectinload(User.cibil_reports)
                    )
                    .filter(User.id == user_id)
                    .first()
                )
                user_details = format_user_response(user_with_docs, user_with_docs.documents)
            return {
                "success": True,
                "message": gettext("retrieved_successfully").format("Profile Details"),
                "data": {
                    "user": user_details,
                },
                "status_code": status.HTTP_200_OK,
            }
        except SQLAlchemyError as e:
            app_logger.error(f"DB Error: {gettext('error_fetching_data_from_db').format('Profile Details')}: {str(e)}")
            return {
                "success": False,
                "message": str(e),
                "status_code": gettext("something_went_wrong"),
                "data": {}
            }
        except Exception as e:
            app_logger.error(
                f"General Error: {gettext('error_fetching_data_from_db').format('Profile Details')}: {str(e)}"
            )
            return {
                "success": False,
                "message": str(e),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }


class AdminAuthService(UserAuthService):
    def login(self, login_request: AdminLoginRequest) -> Dict[str, Any]:
        password_hashing_obj = PasswordHashing()

        try:
            login_input = login_request.login
            password_input = login_request.password
            app_logger.info(f"Authentication attempt for admin login: {login_input}")

            # Step 1: Find admin by email or phone
            # Assuming this returns a single user instance or None
            admin_filter = [
                or_(User.phone == login_input, User.email == login_input),
                User.is_active == True, User.role == UserRole.admin
            ]
            admin = self.db_interface.read_single_by_fields(fields=admin_filter)

            if not admin:
                app_logger.error(gettext("not_found").format("User"))
                return {
                    "success": False,
                    "message": gettext("not_found").format("User"),
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "data": {},
                }

            if not password_hashing_obj.verify_password(password_input.strip(), admin.password):
                app_logger.error(gettext("invalid_password"))
                return {
                    "success": False,
                    "message": gettext("invalid_password"),
                    "status_code": status.HTTP_401_UNAUTHORIZED,
                    "data": {},
                }

            payload = {
                "sub": str(admin.id),
                "id": str(admin.id),
                "role": "admin",
                "name": admin.name,
                "email": admin.email,
                "phone": admin.phone,
                "address": admin.address,
                "is_active": admin.is_active,
            }

            token = JWTService.create_tokens(payload)
            app_logger.info(gettext("logged_in_successfully"))
            with DBSession() as session:
                user_with_docs = (
                    session.query(User)
                    .options(
                        selectinload(User.documents),
                        selectinload(User.cibil_reports)
                    ).filter(User.id == admin.id)
                    .first()
                )
                user_details = format_user_response(user_with_docs, user_with_docs.documents)

            return {
                "success": True,
                "message": gettext("logged_in_successfully"),
                "data": {
                    "token": token,
                    "user": user_details,
                },
                "status_code": status.HTTP_200_OK,
            }

        except Exception as e:
            app_logger.error(f"Error during admin authentication: {e}")
            return {
                "success": False,
                "message": str(e),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {},
            }

    def get_all_users(
            self, search: Optional[str] = None, status_filter: Optional[bool] = None,
            order_by: Optional[str] = None, order_direction: Optional[str] = None, limit: int = 10, offset: int = 0
    ) -> Dict[str, Any]:
        try:
            app_logger.info("Fetching all non-admin users")

            filter_def = {
                "AND": [
                    {"field": "role", "op": "!=", "value": "admin"},
                    {"field": "is_deleted", "op": "==", "value": False}
                ]
            }

            # 🔍 Add status filter
            if status_filter is not None:
                is_active = str(status_filter).lower() in ["true", "1", "active"]
                filter_def["AND"].append({"field": "is_active", "op": "==", "value": is_active})

            # 🔎 Add search filter
            if search and search.strip() != "":
                like_value = f"%{search.lower()}%"
                filter_def["AND"].append(
                    {
                        "OR": [
                            {"field": "name", "op": "ilike", "value": like_value},
                            {"field": "phone", "op": "ilike", "value": like_value},
                            {"field": "email", "op": "ilike", "value": like_value}
                        ]
                    }
                )

            filter_expr = self.db_interface.build_filter_expression(filter_def)

            # 📦 Handle ordering
            order_column = getattr(User, order_by, User.created_at) if order_by else User.created_at
            order_direction = order_direction.lower() if order_direction else "asc"

            # ⏱ Calculate pagination offset
            if offset != 0:
                final_offset = (offset - 1) * limit
            else:
                final_offset = offset

            users = self.db_interface.read_all_by_filters_with_joins(
                filter_expr=filter_expr,
                order_by=order_column,
                order_direction=order_direction,
                limit=limit,
                offset=final_offset,
                join_model=UserCibilReport,
                join_on_left="id",
                join_on_right="user_id",
                relationship_name="cibil_reports"
            )

            user_list = [format_user_response(user) for user in users]

            return {
                "success": True,
                "message": gettext("retrieved_successfully").format("All Users") if user_list else gettext(
                    "no_module_found"
                ).format("User"),
                "status_code": status.HTTP_200_OK if user_list else status.HTTP_404_NOT_FOUND,
                "data": {
                    "user": user_list,
                    "total_count": len(user_list) or 0,
                }
            }

        except Exception as e:
            app_logger.error(f"Error retrieving users: {e}", exc_info=True)
            return {
                "success": False,
                "message": str(e),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": []
            }

    def create_user(self, form_data: AddUserRequest) -> Dict[str, Any]:
        user_id = None
        try:
            pan_file = form_data.pan_file
            aadhaar_file = form_data.aadhaar_file

            # Filter only the required fields for User
            user_data = form_data.model_dump(exclude_unset=True)
            user_data = {k: v for k, v in user_data.items() if
                         k in ["name", "email", "phone", "address", "profile_image"]}

            # Check if a phone number already exists
            phone_number_filter = [User.phone == form_data.phone]
            is_phone_exists = self.db_interface.read_by_fields(phone_number_filter)
            if is_phone_exists:
                return {
                    "success": False,
                    "message": gettext("already_exists").format("User Phone Number"),
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "data": {}
                }

            # Create user and get model instance
            user_details = self.db_interface.create(data=user_data)
            app_logger.info(f"{gettext('created_successfully').format('User')}: {user_details}")
            user_id = user_details.id

            document_data = {}
            user_document_interface = DBInterface(UserDocument)

            # Handle PAN document
            if pan_file:
                user_document_pan_data = {
                    "user_id": user_id,
                    "document_type": DocumentType.PAN.value,
                    "document_number": form_data.pan_number,
                    "document_file": pan_file
                }

                user_pan_document = user_document_interface.create(user_document_pan_data)
                document_data[DocumentType.PAN.value] = user_pan_document
                app_logger.info(f"PAN document created for user_id: {user_id}")

                # Update user model instance
                user_details.pan_number = user_pan_document.document_number
                user_details.pan_document = user_pan_document.document_file

            # Handle Aadhaar document
            if aadhaar_file:
                user_document_aadhar_data = {
                    "user_id": user_id,
                    "document_type": DocumentType.AADHAR.value,
                    "document_number": form_data.aadhaar_number,
                    "document_file": aadhaar_file
                }

                user_aadhar_document = user_document_interface.create(user_document_aadhar_data)
                document_data[DocumentType.AADHAR.value] = user_aadhar_document
                app_logger.info(f"Aadhaar document created for user_id: {user_id}")

                # Update user model instance
                user_details.aadhaar_number = user_aadhar_document.document_number
                user_details.aadhaar_document = user_aadhar_document.document_file

            # Return success response
            return {
                "success": True,
                "message": gettext('created_successfully').format('User'),
                "data": {
                    "user": UserResponseSchema.model_validate(user_details)
                },
                "status_code": status.HTTP_200_OK,
            }

        except Exception as e:
            app_logger.error(f'{gettext("error_inserting_data_to_db")}: {e}')
            delete_filter = [User.id == user_id]
            self.db_interface.delete(filters=delete_filter)
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }

    def update_user(self, user_id: str, form_data: UserUpdateData):
        try:
            # Check if a user exists
            user_details = self.db_interface.read_by_id(_id=user_id)
            if not user_details:
                app_logger.error(gettext('not_found').format('User'))
                return {
                    "success": False,
                    "message": gettext('not_found').format('User'),
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "data": {}
                }

            # Check for duplicate phone number (excluding current user)
            if form_data.phone:
                phone_number_filter = [
                    User.phone == form_data.phone, User.id != user_id, User.is_deleted == False, User.is_active == True
                ]
                is_phone_exists = self.db_interface.read_by_fields(phone_number_filter)
                if is_phone_exists:
                    return {
                        "success": False,
                        "message": gettext("already_exists").format("User Phone Number"),
                        "status_code": status.HTTP_400_BAD_REQUEST,
                        "data": {}
                    }

            # Extract and sanitize user data for update
            user_data = form_data.model_dump(exclude_unset=True)
            user_data = {
                k: v for k, v in user_data.items()
                if
                k in ["name", "email", "phone", "address", "profile_image", "is_deleted", "is_active"] and v is not None
            }

            # Update user record
            user_details = self.db_interface.update(_id=user_id, data=user_data)
            app_logger.info(f"User updated: {user_details}")

            # Prepare UserDocument interface
            user_document_interface = DBInterface(UserDocument)

            # Update or create PAN document
            if form_data.pan_file:
                pan_filter = [
                    UserDocument.user_id == user_id,
                    UserDocument.document_type == DocumentType.PAN.value
                ]
                existing_pan_doc = user_document_interface.read_single_by_fields(pan_filter)
                pan_data = {
                    "user_id": user_id,
                    "document_type": DocumentType.PAN.value,
                    "document_number": form_data.pan_number,
                    "document_file": form_data.pan_file
                }

                if existing_pan_doc:
                    updated_pan = user_document_interface.update(_id=existing_pan_doc.id, data=pan_data)
                    app_logger.info(f"PAN document updated for user_id: {user_id}")
                else:
                    updated_pan = user_document_interface.create(pan_data)
                    app_logger.info(f"PAN document created for user_id: {user_id}")

                # Attach updated PAN data to a user object for response
                user_details.pan_number = updated_pan.document_number
                user_details.pan_document = updated_pan.document_file

            # Update or create Aadhaar document
            if form_data.aadhaar_file:
                aadhaar_filter = [
                    UserDocument.user_id == user_id,
                    UserDocument.document_type == DocumentType.AADHAR.value
                ]
                existing_aadhaar_doc = user_document_interface.read_single_by_fields(aadhaar_filter)
                aadhaar_data = {
                    "user_id": user_id,
                    "document_type": DocumentType.AADHAR.value,
                    "document_number": form_data.aadhaar_number,
                    "document_file": form_data.aadhaar_file
                }

                if existing_aadhaar_doc:
                    updated_aadhaar = user_document_interface.update(_id=existing_aadhaar_doc.id, data=aadhaar_data)
                    app_logger.info(f"Aadhaar document updated for user_id: {user_id}")
                else:
                    updated_aadhaar = user_document_interface.create(aadhaar_data)
                    app_logger.info(f"Aadhaar document created for user_id: {user_id}")

                user_details.aadhaar_number = updated_aadhaar.document_number
                user_details.aadhaar_document = updated_aadhaar.document_file

            # Final log and response
            app_logger.info(f"{gettext('updated_successfully').format('User')}: {user_id}")
            return {
                "success": True,
                "message": gettext('updated_successfully').format('User'),
                "data": {
                    "user": UserResponseSchema.model_validate(user_details)
                },
                "status_code": status.HTTP_200_OK,
            }

        except SQLAlchemyError as e:
            app_logger.error(f"SQLAlchemy error while updating user: {str(e)}")
            return {
                "success": False,
                "message": str(e),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": []
            }

        except Exception as e:
            app_logger.error(f"Unhandled error while updating user: {str(e)}")
            return {
                "success": False,
                "message": str(e),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": []
            }

    def delete_user(self, logged_in_user_id: str, user_id: str):
        try:
            is_user_exists = self.db_interface.read_by_id(_id=user_id)
            if not is_user_exists:
                app_logger.error(gettext('not_found').format('User'))
                return {
                    "success": False,
                    "message": gettext('not_found').format('User'),
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "data": []
                }
            # with DBSession() as session:
            #     session.query(User).filter(User.id == user_id).update(
            #         {
            #             User.is_deleted: True,
            #             User.is_active: False,
            #         }
            #     )
            self.db_interface.soft_delete(filters=[User.id == user_id], modified_id=logged_in_user_id)
            return {
                "success": True,
                "message": gettext('deleted_successfully').format('User'),
                "status_code": status.HTTP_200_OK,
                "data": {}
            }
        except Exception as e:
            app_logger.error(f'Error deleting user: {e}')
            return {
                "success": False,
                "message": str(e),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": []
            }
