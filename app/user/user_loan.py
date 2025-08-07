from typing import List

from fastapi import APIRouter, Request, Form, UploadFile, File, BackgroundTasks, Query
from starlette import status

from common.enums import UploadFileType
from common.response import ApiResponse
from models.loan import LoanApplicant
from schemas.loan_schemas import LoanForm, UserApprovedLoanForm, InstantCashForm, LoanConsentForm, LoanDisbursementForm, \
    LoanAadharVerifiedStatusForm
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
def get_all_loan_applications(
    request: Request, 
    order_by: str = Query("id", enum=["id", "created_at"]),
    order_dir: str = Query("desc", enum=["asc", "desc"])):
    user_state = getattr(request.state, "user", None)
    response = loan_service.get_loan_applications(user_id=user_state.get("id"),  order_by=order_by,
        order_dir=order_dir)

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

@router.post("/add-user-approved-loan", summary="Add User Approved Loan")
def add_user_approved_loan(request: Request, form_data: UserApprovedLoanForm):
    user_state = getattr(request.state, "user", None)
    response = loan_service.add_user_approved_loan(user_id=user_state.get("id"), loan_application_form=form_data)

    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )

@router.post("/calculate-emi", summary="Calculate EMI for Instant Loan")
def calculate_instant_cash(request: Request, form_data: InstantCashForm):
    user_state = getattr(request.state, "user", None)

    response = loan_service.calculate_emi_for_instant_cash(user_id=user_state.get("id"), loan_application_form=form_data)
    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )

@router.post("/accept-consent", summary="Accept Consent of Loan")
def update_loan_consent(request: Request, form_data: LoanConsentForm):
    user_state = getattr(request.state, "user", None)

    response = loan_service.update_loan_consent(user_id=user_state.get("id"), loan_consent_form=form_data)
    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )

@router.post("/loan-proceed-for-disbursement", summary="Approve Loan for Disbursement")
def proceed_for_disbursement(request: Request, form_data: LoanDisbursementForm):
    user_state = getattr(request.state, "user", None)

    response = loan_service.apply_for_disbursement(user_id=user_state.get("id"), loan_disbursement_form=form_data)
    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )


@router.post("/update-aadhar-verify-status", summary="Update Aadhar Verify Status")
def update_aadhar_verify_status(request: Request, form_data: LoanAadharVerifiedStatusForm):
    user_state = getattr(request.state, "user", None)

    response = loan_service.update_aadhar_verify_status(user_id=user_state.get("id"), loan_aadhar_verify_form=form_data)
    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data")
    )