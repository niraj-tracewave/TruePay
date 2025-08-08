from pydantic import BaseModel, EmailStr, Field
from datetime import datetime


class ContactUsCreateSchema(BaseModel):
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    email: EmailStr
    service: str = Field(..., max_length=255)
    message: str


class ContactUsUpdateSchema(BaseModel):
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    email: EmailStr | None = None
    service: str | None = Field(None, max_length=255)
    message: str | None = None


class ContactUsResponseSchema(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    service: str
    message: str
    # created_at: datetime
    # modified_at: datetime
    # created_by: str
    # modified_by: str
    is_deleted: bool

    class Config:
        from_attributes = True
