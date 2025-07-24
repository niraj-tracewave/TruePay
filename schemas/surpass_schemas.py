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
