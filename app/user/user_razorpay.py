import time
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
from services.foreclosure_service import ForeClosureService
from services.payment_details_service import PaymentDetailsService
from services.loan_service.user_loan import UserLoanService
from services.razorpay_service import RazorpayService
from services.dependencies import get_razorpay_service
from schemas.razorpay_schema import CreatePlanSchema, CreateSubscriptionSchema
from common.utils import calculate_emi_schedule
from fastapi.responses import JSONResponse
from db_domains.db_interface import DBInterface



router = APIRouter(prefix="/razorpay", tags=["RazorPay API's"])

loan_service = UserLoanService(LoanApplicant)
plan_service = PlanService(Plan)
sub_service = SubscriptionService(Subscription)
foreclosure_service = ForeClosureService()
payment_details_service = PaymentDetailsService()

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
        
@router.get("/get-closure-payment-link/{subscription_id}")
def get_closure_payment_link(subscription_id: str, service: RazorpayService = Depends(get_razorpay_service)):
    
    try:
        sub = service.fetch_subscription(subscription_id)
        if not sub:
            return JSONResponse(
                content={"success": False, "message": "Subscription not found", "data": {}},
                status_code=status.HTTP_404_NOT_FOUND
            )
        #NOTE: Check the status == "active" IF Condition is --> If 1 or more EMIs needs to be paid before foreclosure
        # if sub['status'] != 'active':
        #     return {
        #         "success": False,
        #         "message": "Subscription is not active",
        #         "status_code": status.HTTP_400_BAD_REQUEST,
        #         "data": {}
        #     }
        
        # step-2 Fetch Plan details
        plan = service.fetch_plan(sub['plan_id'])
        if not plan:
            return JSONResponse(
                content={"success": False, "message": "Plan not found", "data": {}},
                status_code=status.HTTP_404_NOT_FOUND
            )

        amount_per_emi = plan['item']['amount']
        remaining_emis = max(0, sub['total_count'] - sub['paid_count'])
        closure_amount_paise = amount_per_emi * remaining_emis

        try:
            ref_id = f"{sub['id']}+{int(time.time() * 1000)}"
            payment = service.create_payment_link(
                amount=closure_amount_paise,
                currency="INR",
                description="Closure Payment",
                subscription_id=ref_id
            )
        except Exception as e:
            # Check if the error message matches the "reference_id already exists" case
            error_message = str(e)
            if "payment link with given reference_id" in error_message and "already exists" in error_message:
                # Handle the duplicate reference_id error specifically
                print("Duplicate reference_id detected. Please generate a unique reference_id.")
                # You can either generate a new reference_id here or return an error response
            else:
                # For other exceptions, raise or handle differently
                raise
        else:
            # No error, continue normally
            print("Payment link created successfully:", payment)
        if not payment:
            return JSONResponse(
                content={"success": False, "message": "Failed to create payment link", "data": {}},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        #NOTE: Update the foreclosure details with the payment link [ ForeClosure, PaymentDetails ]
        sub_db_interface = DBInterface(Subscription)
        existing_sub = sub_db_interface.read_single_by_fields([
            Subscription.razorpay_subscription_id == sub["id"],
            Subscription.is_deleted == False
        ])
        if not existing_sub:
            return JSONResponse(
                content={"success": False, "message": "Subscription not found in DB", "data": {}},
                status_code=status.HTTP_404_NOT_FOUND
            )

        foreclosure_data = {
            "subscription_id": existing_sub.id,
            "amount": closure_amount_paise / 100,
            "reason": "Subscription Closure",
            "status": "pending"
        }
        foreclosure_response = foreclosure_service.create_foreclosure(foreclosure_data)
        if not foreclosure_response['success']:
            return foreclosure_response
        payment_details_data = {
            "payment_id": payment['id'],
            "amount": closure_amount_paise / 100,
            "currency": "INR",
            "status": payment['status'],
            "payment_method": None,
            "foreclosure_id": foreclosure_response["data"].id
        }
        payment_details_response = payment_details_service.create_payment_details(payment_details_data)
        if not payment_details_response['success']:
            return payment_details_response
        #NOTE: Afterwards
        #Track the payment status if Success --> Cancel The subscription and update the foreclosure status     
        return JSONResponse(
            content={"success": True, "message": "Payment Link Created Successfully!", "data": {"payment": payment}},
            status_code=status.HTTP_200_OK
        )

    except Exception as e:
        return JSONResponse(
            content={"success": False, "message": "Internal Server Error", "data": {"error": str(e)}},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

        
@router.get("/get-payment-details/{payment_id}")
def get_payment_details(payment_id: str, service: RazorpayService = Depends(get_razorpay_service)):
    """
    API to fetch payment details from Razorpay.
    """
    return service.get_payment_link_details(payment_id)