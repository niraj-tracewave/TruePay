from typing import List

from fastapi import APIRouter, Request, Form, UploadFile, File, BackgroundTasks
from starlette import status

from common.enums import UploadFileType
from common.response import ApiResponse
from models.loan import LoanApplicant
from schemas.loan_schemas import LoanForm
from services.loan_service.user_loan import UserLoanService

router = APIRouter(prefix="/loan", tags=["User Panel Loan API's"])
loan_service = UserLoanService(LoanApplicant)


@router.post("/add-loan-application", summary="Add Loan Application")
def add_loan_application(request: Request, form_data: LoanForm, background_tasks:BackgroundTasks):
    user_state = getattr(request.state, "user", None)
    response = loan_service.add_loan_application(user_id=user_state.get("id"), loan_application_form=form_data, background_tasks= background_tasks, is_created_by_admin=False)

    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )


@router.get("/get-loan-application", summary="Get All Loan Application")
def get_all_loan_applications(request: Request):
    user_state = getattr(request.state, "user", None)
    response = loan_service.get_loan_applications(user_id=user_state.get("id"))

    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )


@router.get("/get-loan-application-details/{loan_application_id}", summary="Get Loan Application Details")
def get_loan_application_details(request: Request, loan_application_id: str):
    user_state = getattr(request.state, "user", None)
    response = loan_service.get_loan_application_details(
        user_id=user_state.get("id"),
        loan_application_id=loan_application_id
    )

    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )


@router.post("/upload-file", summary="Upload Documents")
async def upload_file(request: Request, file_type: UploadFileType = Form(...), files: List[UploadFile] = File(...)):
    user = getattr(request.state, "user", None)
    response = await loan_service.upload_files_to_s3(file_type=file_type, files=files)

    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )
