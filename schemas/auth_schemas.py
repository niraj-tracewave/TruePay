import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, constr, model_validator

from common.enums import UserRole


class LoginRequest(BaseModel):
    phone_number: constr(min_length=10, max_length=15)


class VerifyOTPRequest(BaseModel):
    phone_number: str
    otp: str
    otp_secret: str


class RefreshToken(BaseModel):
    refresh_token: str


class UpdateProfileRequest(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[constr(min_length=10, max_length=15)] = None
    address: str
    profile_image: Optional[str] = None
    pan_number: Optional[constr(min_length=10, max_length=10)] = None
    aadhaar_number: Optional[constr(min_length=12, max_length=12)] = None
    pan_file: Optional[str] = None
    aadhaar_file: Optional[str] = None

    @model_validator(mode="after")
    def check_files_required_if_numbers_provided(cls, values):
        pan_number = values.pan_number
        pan_file = values.pan_file
        aadhaar_number = values.aadhaar_number
        aadhaar_file = values.aadhaar_file

        if pan_number and not pan_file:
            raise ValueError('PAN document file is required if PAN number is provided.')

        if aadhaar_number and not aadhaar_file:
            raise ValueError('Aadhaar document file is required if Aadhaar number is provided.')

        return values


# Admin Schemas
class AdminLoginRequest(BaseModel):
    login: str
    password: str

    @model_validator(mode='after')
    def validate_login_and_password(self):
        email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        phone_pattern = r'^\+?\d{10,15}$'

        if not (re.match(email_pattern, self.login) or re.match(phone_pattern, self.login)):
            raise ValueError('Login must be a valid email or phone number')

        if len(self.password) < 6:
            raise ValueError('Password must be at least 6 characters long')

        return self


class AddUserRequest(BaseModel):
    name: str
    email: EmailStr
    phone: constr(min_length=10, max_length=15)
    address: str
    profile_image: Optional[str] = None
    pan_number: constr(min_length=10, max_length=10)
    aadhaar_number: constr(min_length=12, max_length=12)
    pan_file: Optional[str] = None
    aadhaar_file: Optional[str] = None

    @model_validator(mode="after")
    def check_files_required_if_numbers_provided(cls, values):
        pan_number = values.pan_number
        pan_file = values.pan_file
        aadhaar_number = values.aadhaar_number
        aadhaar_file = values.aadhaar_file

        if pan_number and not pan_file:
            raise ValueError('pan_file is required when pan_number is provided')

        if aadhaar_number and not aadhaar_file:
            raise ValueError('aadhaar_file is required when aadhaar_number is provided')

        return values


class UserResponseSchema(BaseModel):
    id: int
    name: str
    email: Optional[str]
    phone: str
    profile_image: Optional[str] = None
    pan_number: Optional[str] = None
    pan_document: Optional[str] = None
    aadhaar_number: Optional[str] = None
    aadhaar_document: Optional[str] = None
    is_active: bool
    is_deleted: bool
    created_at: datetime
    modified_at: datetime

    model_config = {
        "from_attributes": True
    }


class UserUpdateData(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[constr(min_length=10, max_length=15)] = None
    address: Optional[str] = None
    profile_image: Optional[str] = None
    pan_number: Optional[constr(min_length=10, max_length=10)] = None
    aadhaar_number: Optional[constr(min_length=12, max_length=12)] = None
    pan_file: Optional[str] = None
    aadhaar_file: Optional[str] = None
    is_deleted: Optional[bool] = None
    is_active: Optional[bool] = None

    @model_validator(mode="after")
    def check_files_required_if_numbers_provided(cls, values):
        pan_number = values.pan_number
        pan_file = values.pan_file
        aadhaar_number = values.aadhaar_number
        aadhaar_file = values.aadhaar_file

        if pan_number and not pan_file:
            raise ValueError('pan_file is required when pan_number is provided')

        if aadhaar_number and not aadhaar_file:
            raise ValueError('aadhaar_file is required when aadhaar_number is provided')

        return values
