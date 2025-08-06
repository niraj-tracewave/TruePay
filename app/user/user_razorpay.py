from fastapi import Request
from fastapi import APIRouter, Depends
from starlette import status
from db_domains.db import DBSession
from sqlalchemy.orm import selectinload
from models.loan import LoanApplicant
from models.razorpay import Plan, Subscription
from services.plan_service import PlanService
from services.subscription_service import SubscriptionService
from services.loan_service.user_loan import UserLoanService
from services.razorpay_service import RazorpayService
from services.dependencies import get_razorpay_service
from schemas.razorpay_schema import CreatePlanSchema, CreateSubscriptionSchema
from common.utils import calculate_emi_schedule


router = APIRouter(prefix="/razorpay", tags=["RazorPay API's"])

loan_service = UserLoanService(LoanApplicant)
plan_service = PlanService(Plan)
sub_service = SubscriptionService(Subscription)


@router.post("/create-razorpay-plan-sub/{applicant_id}")
def create_emi_mandate(request: Request, applicant_id: str, payload: CreatePlanSchema, service: RazorpayService = Depends(get_razorpay_service)):
    user_state = getattr(request.state, "user", None)
    # NOTE: ADD LOAN PLAN AND SUBSCRIPTIONS HERE
    # Step-1: Fetch Loan Details
    filters = [
        LoanApplicant.id == applicant_id,
        LoanApplicant.is_deleted == False
    ]
    with DBSession() as session:
        loan_details = (
            session.query(LoanApplicant)
            .options(
                selectinload(LoanApplicant.plans).selectinload(Plan.subscriptions),
                selectinload(LoanApplicant.approval_details),
            )
            .filter(*filters)
            .first()
        )
    if not loan_details:
        return {
            "success": False,
            "message": "Loan applicant not found",
            "status_code": status.HTTP_404_NOT_FOUND,
            "data": {}
        }

    first_plan = loan_details.plans[0] if loan_details.plans else None
    subscription = first_plan.subscriptions[0] if first_plan and first_plan.subscriptions   else None
    
    if first_plan and subscription:
        return {
            "success": True,
            "message": "Successfully retrieved Plan & corresponding Subscription",
            "status_code": status.HTTP_200_OK,
            "data": {
                "plan_data": first_plan,
                "subscription_data": subscription
            }
        }
    loan_approval_detail = loan_details.approval_details[0]
    # Step -2 Fetch Approved Loan
    # if loan_approval_detail:
    user_accepted_amount = loan_approval_detail.user_accepted_amount
    approved_interest_rate = loan_approval_detail.approved_interest_rate
    approved_tenure_months = loan_approval_detail.approved_tenure_months
    approved_processing_fee = loan_approval_detail.approved_processing_fee
    # Step - 3 Calculate EMI
    emi_result = calculate_emi_schedule(
        loan_amount=user_accepted_amount,
        tenure_months=approved_tenure_months,
        annual_interest_rate=approved_interest_rate,
        processing_fee=approved_processing_fee,
        is_fee_percentage=True
    )
    emi = 0.0
    if emi_result["status_code"] == status.HTTP_200_OK:
        data = emi_result["data"]
        emi = data.get("monthly_emi")
    # Step-2 Create Plan Based On provided Loan
    try:
        created_plan = plan_service.add_plan(
            applicant_id=loan_details.id,
            user_id=user_state.get("id"),
            form_data={
                "period": "monthly",
                "interval": 1,
                "item": {
                    "name": f"{loan_details.loan_uid}_" + "05082025",
                    "amount": emi*100,  # NOTE: RAZORPAY *100 LOGIC
                    "currency": "INR",
                    "description": f"₹{user_accepted_amount} loan at {approved_interest_rate}% interest for {approved_tenure_months} months"
                },
            }
        )
        if created_plan:
            # plan_db_obj = created_plan.get("data")
            # Step-3 After Creating Plan Create Subscription
            # if created_plan.get("success") == True:
            created_sub = sub_service.add_subscription(
                plan_id=created_plan.id,
                user_id=user_state.get("id"),
                form_data={
                    "plan_id": created_plan.razorpay_plan_id,
                    "total_count": approved_tenure_months,
                    "quantity": 1,
                    # "start_at": Optional[int] = None  # Unix timestamp
                    # "expire_by": Optional[int] = None  # Unix timestamp
                    "customer_notify": 1,
                    # "addons": [],
                    # "offer_id": Optional[str] = None
                    # "notes": Optional[Notes] = None
                }
            )

            if created_sub:
                return {
                    "success": True,
                    "message": f"Successfully Created Plan & corresponding Subscription",
                    "status_code": status.HTTP_200_OK,
                    "data": {
                        "plan_data": created_plan,
                        "subscription_data": created_sub
                    }
                }
            else:
                return {
                    "success": False,
                    "message": "Something went wrong",
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "data": {}
                }
        else:
            return {
                "success": False,
                "message": "Something went wrong",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "status_code": status.HTTP_400_BAD_REQUEST,
            "data": {}
        }


@router.post("/create-emi-plan")
def create_emi_plan(payload: CreatePlanSchema, service: RazorpayService = Depends(get_razorpay_service)):
    plan_data = payload.dict(exclude_none=True)  # exclude None values
    plan = service.create_plan(plan_data)
    return {"plan": plan}


@router.post("/create-subscription")
def create_subscription(payload: CreateSubscriptionSchema, service: RazorpayService = Depends(get_razorpay_service)):
    subscription_data = payload.dict(exclude_none=True)
    subscription = service.create_subscription(subscription_data)
    return {"subscription": subscription}
