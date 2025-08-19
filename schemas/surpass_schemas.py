from pydantic import BaseModel, field_validator

from common.enums import ConsentEnum, GenderEnum


class GetCibilReportData(BaseModel):
    mobile: str
    pan: str
    name: str
    gender: GenderEnum
    consent: ConsentEnum

    @field_validator("gender", mode="before")
    def normalize_gender(cls, v: str):
        return v.lower()

    @field_validator("consent", mode="before")
    @classmethod
    def normalize_consent(cls, v: str):
        return v.upper()


class PanCardDetails(BaseModel):
    pan_card: str


class BankDetails(BaseModel):
    applicant_id: int
    user_id: int
    id_number: str
    ifsc: str
    bank_name: str
    account_holder_name: str


class AadharCardDetails(BaseModel):
    signup_flow: bool = True
    redirect_url: str
    webhook_url: str
