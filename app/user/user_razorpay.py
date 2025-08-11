from datetime import datetime
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
def create_emi_mandate(
    request: Request,
    applicant_id: str,  # Assuming this is needed; otherwise, remove
    service: RazorpayService = Depends(get_razorpay_service)
):
    user_state = getattr(request.state, "user", None)
    if not user_state or "id" not in user_state:
        return {
            "success": False,
            "message": "User authentication failed",
            "status_code": status.HTTP_401_UNAUTHORIZED,
            "data": {}
        }

    # Step 1: Fetch Loan Details
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

        # Step 2: Check for approval details
        if not loan_details.approval_details:
            return {
                "success": False,
                "message": "No approval details found for the applicant",
                "status_code": status.HTTP_404_NOT_FOUND,
                "data": {}
            }

        # Step 3: Check for existing plan/subscription (optional, based on requirements)
        if loan_details.plans:
            first_plan = loan_details.plans[0]
            subscription = first_plan.subscriptions[0] if first_plan.subscriptions else None
            if subscription:
                # Serialize to avoid exposing raw SQLAlchemy objects
                plan_data = {
                    "id": first_plan.id,
                    "razorpay_plan_id": first_plan.razorpay_plan_id,
                    "period": first_plan.period,
                    "interval": first_plan.interval,
                    "item_name": first_plan.item_name,
                    "item_amount": first_plan.item_amount,
                    "item_currency": first_plan.item_currency
                }
                subscription_data = {
                    "id": subscription.id,
                    "razorpay_subscription_id": subscription.razorpay_subscription_id,
                    "status": subscription.status.value,
                    "start_at": subscription.start_at if subscription.start_at else None,
                    "end_at": subscription.end_at if subscription.end_at else None,
                    "short_url": subscription.short_url if subscription.short_url else None
                    
                }
                return {
                    "success": True,
                    "message": "Plan and subscription already exist",
                    "status_code": status.HTTP_200_OK,
                    "data": {
                        "plan_data": plan_data,
                        "subscription_data": subscription_data
                    }
                }

        # Step 4: Fetch Approved Loan Details
        loan_approval_detail = loan_details.approval_details[0]
        user_accepted_amount = loan_approval_detail.user_accepted_amount
        approved_interest_rate = loan_approval_detail.approved_interest_rate
        approved_tenure_months = loan_approval_detail.approved_tenure_months
        approved_processing_fee = loan_approval_detail.approved_processing_fee

        # Step 5: Calculate EMI
        emi_result = calculate_emi_schedule(
            loan_amount=user_accepted_amount,
            tenure_months=approved_tenure_months,
            annual_interest_rate=approved_interest_rate,
            processing_fee=approved_processing_fee,
            is_fee_percentage=True,
            loan_type=loan_details.loan_type
        )
        if emi_result["status_code"] != status.HTTP_200_OK:
            return {
                "success": False,
                "message": "Failed to calculate EMI",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }
        emi = emi_result["data"].get("monthly_emi", 0.0)

        # Step 6: Create Plan
        try:
            created_plan = plan_service.add_plan(
                applicant_id=loan_details.id,
                user_id=user_state["id"],
                form_data={
                    "period": "monthly",
                    "interval": 1,
                    "item": {
                        "name": f"{loan_details.loan_uid}_{datetime.now().strftime('%d%m%Y')}",
                        "amount": int(emi * 100),  # Convert to paise, ensure integer
                        "currency": "INR",
                        "description": f"₹{user_accepted_amount} loan at {approved_interest_rate}% interest for {approved_tenure_months} months"
                    }
                }
            )
            if not created_plan:
                return {
                    "success": False,
                    "message": "Failed to create plan",
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "data": {}
                }

            # Step 7: Create Subscription
            created_sub = sub_service.add_subscription(
                plan_id=created_plan.id,
                user_id=user_state["id"],
                form_data={
                    "plan_id": created_plan.razorpay_plan_id,
                    "total_count": approved_tenure_months,
                    "quantity": 1,
                    "customer_notify": 1
                }
            )
            if not created_sub:
                return {
                    "success": False,
                    "message": "Failed to create subscription",
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "data": {}
                }

            # Commit the transaction
            session.commit()

            # Serialize response
            plan_data = {
                "id": created_plan.id,
                "razorpay_plan_id": created_plan.razorpay_plan_id,
                "period": created_plan.period,
                "interval": created_plan.interval,
                "item_name": created_plan.item_name,
                "item_amount": created_plan.item_amount,
                "item_currency": created_plan.item_currency
            }
            subscription_data = {
                "id": created_sub.id,
                "razorpay_subscription_id": created_sub.razorpay_subscription_id,
                "status": created_sub.status.value,
                "start_at": created_sub.start_at if created_sub.start_at else None,
                "end_at": created_sub.end_at if created_sub.end_at else None,
                "short_url": created_sub.short_url if created_sub.short_url else None
            }

            return {
                "success": True,
                "message": "Successfully created plan and subscription",
                "status_code": status.HTTP_201_CREATED,  # Use 201 for creation
                "data": {
                    "plan_data": plan_data,
                    "subscription_data": subscription_data
                }
            }

        except ValueError as ve:
            session.rollback()
            return {
                "success": False,
                "message": f"Invalid input: {str(ve)}",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }
        except Exception as e:
            session.rollback()
            # Log the error internally (e.g., using logging module)
            print(f"Error: {str(e)}")  # Replace with proper logging
            return {
                "success": False,
                "message": "An error occurred while creating plan or subscription",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "data": {
                    "error": str(e)
                }
            }

@router.post("/create-emi-plan")
def create_emi_plan(payload: CreatePlanSchema, service: RazorpayService = Depends(get_razorpay_service)):
    plan_data = payload.dict(exclude_none=True)  # exclude None values
    plan = service.create_plan(plan_data)
    return {"plan": plan}


@router.post("/create-subscription")
def create_subscription(payload: CreateSubscriptionSchema, service: RazorpayService = Depends(get_razorpay_service)):
    subscription_data = payload.dict(exclude_none=True)
    if 'callback_url' in subscription_data:
        callback_url = "https://api.razorpay.com/"
        subscription_data['notes'] = subscription_data.get('notes', {})
        subscription_data['notes']['callback_url'] = str(callback_url)
    subscription = service.create_subscription(subscription_data)
    return {"subscription": subscription}

@router.get("/get-subscription/{subscription_id}")
def get_subscription(subscription_id: str, service: RazorpayService = Depends(get_razorpay_service)):
    try:
        subscription = service.fetch_subscription(subscription_id)
        return {
                "success": True,
                "message": "Subscription Details Fetched Successfully!",
                "status_code": status.HTTP_200_OK,
                "data":  {"subscription": subscription}
            }
    except Exception as e:
        return {
                "success": False,
                "message": "Internal Server Error",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "data": {
                    "error": str(e)
                }
            }
    
@router.get("/get-closure-payment-link/{subscription_id}")
def get_closure_payment_link(subscription_id: str, service: RazorpayService = Depends(get_razorpay_service)):
    """AI is creating summary for get_closure_payment_link

    Args:
        subscription_id (str): The ID of the subscription for which the closure payment link is to be created.
        service (RazorpayService, optional): The Razorpay service instance. Defaults to Depends(get_razorpay_service).

    Returns:
        [type]: [description]
    """
    try:
        sub = service.fetch_subscription(subscription_id)
        if not sub:
            return {
                "success": False,
                "message": "Subscription not found",
                "status_code": status.HTTP_404_NOT_FOUND,
                "data": {}
            }
        if sub['status'] != 'active':
            return {
                "success": False,
                "message": "Subscription is not active",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }
        # Step -2 Fetch Plan details
        plan = service.fetch_plan(sub['plan_id'])
        if not plan:
            return {
                "success": False,
                "message": "Plan not found",
                "status_code": status.HTTP_404_NOT_FOUND,
                "data": {}
            }
            
        amount_paise = plan['item']['amount']
        amount_inr = amount_paise / 100
        print(f"Amount: ₹{amount_inr}")
        remaining_emis = sub['total_count'] - sub['paid_count']
        amount_per_emi = plan['item']['amount']  # amount per billing cycle in paise
        closure_amount_paise = amount_per_emi * remaining_emis

        payment = service.create_payment_link(amount=closure_amount_paise, currency="INR", description="Closure Payment for Subscription")
        return {
            "success": True,
            "message": "Payment Link Created Successfully!",
            "status_code": status.HTTP_200_OK,
            "data": {"payment": payment}
        }
            
    except Exception as e:
        return {
                "success": False,
                "message": "Internal Server Error",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "data": {
                    "error": str(e)
                }
            }
        

@router.get("/get-subscription-invoices/{subscription_id}")
def get_subscription_invoices(subscription_id: str, service: RazorpayService = Depends(get_razorpay_service), count: int = 10, skip: int = 0):
    """
    Fetch all invoices for a given subscription with optional pagination params.
    """
    try:
        invoices = service.fetch_invoices_for_subscription(subscription_id, count=count, skip=skip)
        return {
            "success": True,
            "message": "Invoices fetched successfully!",
            "status_code": status.HTTP_200_OK,
            "data": {"invoices": invoices}
        }
    except Exception as e:
        return {
            "success": False,
            "message": "Failed to fetch invoices",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "data": {"error": str(e)}
        }