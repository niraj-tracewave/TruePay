import time
from datetime import datetime, timedelta
from fastapi import Request, Query
from fastapi import APIRouter, Depends
from starlette import status
from db_domains.db import DBSession
from sqlalchemy.orm import selectinload
from models.loan import LoanApplicant, EmiScheduleDate
from models.razorpay import Plan, Subscription,  Invoice, ForeClosure, PrePayment
from services import razorpay_service
from services.plan_service import PlanService
from services.subscription_service import SubscriptionService
from services.foreclosure_service import ForeClosureService
from services.prepayment_service import PrePaymentService
from services.payment_details_service import PaymentDetailsService
from services.loan_service.user_loan import UserLoanService
from services.razorpay_service import RazorpayService
from services.invoice_service import InvoiceService
from services.dependencies import get_razorpay_service
from schemas.razorpay_schema import CreatePlanSchema, CreateSubscriptionSchema
from common.utils import calculate_emi_schedule, map_razorpay_invoice_to_db, map_payment_link_to_invoice_obj
from fastapi.responses import JSONResponse
from db_domains.db_interface import DBInterface



router = APIRouter(prefix="/razorpay", tags=["RazorPay API's"])

loan_service = UserLoanService(LoanApplicant)
plan_service = PlanService(Plan)
sub_service = SubscriptionService(Subscription)
foreclosure_service = ForeClosureService()
pre_payment_service = PrePaymentService()
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
            loan_type=loan_details.loan_type,
            emi_start_day_atm=loan_details.emi_start_day_atm
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
            emi_schedule_date = 5
            try:
                emi_schedule_db_interface = DBInterface(EmiScheduleDate)
                existing_entry = emi_schedule_db_interface.read_single_by_fields(
                        fields=[
                            EmiScheduleDate.emi_schedule_loan_type == loan_details.loan_type,
                            EmiScheduleDate.is_deleted == False,
                        ]
                    )
                emi_schedule_date = int(existing_entry.emi_schedule_date) if existing_entry else 5
            except Exception as e:
                print(f"Error fetching EMI schedule date: {e}")
                
            # NOTE: calculation for start_at date in unix value
            # Get current date
            current_date = datetime.now()

            # Calculate the first day of the next month
            if current_date.month == 12:
                next_month = 1
                next_year = current_date.year + 1
            else:
                next_month = current_date.month + 1
                next_year = current_date.year

            # Create datetime object for the emi_schedule_date of next month
            try:
                next_month_date = datetime(next_year, next_month, emi_schedule_date)
            except ValueError:
                # Handle case where emi_schedule_date is invalid for the month (e.g., 31st in February)
                # Use the last day of the month instead
                next_month_first = datetime(next_year, next_month, 1)
                next_month_date = (next_month_first.replace(day=1, month=next_month % 12 + 1, year=next_year if next_month < 12 else next_year + 1) - timedelta(days=1))

            # Convert to Unix timestamp (seconds since epoch)
            unix_timestamp = int(time.mktime(next_month_date.timetuple()))
            created_sub = sub_service.add_subscription(
                plan_id=created_plan.id,
                user_id=user_state["id"],
                form_data={
                    "plan_id": created_plan.razorpay_plan_id,
                    "total_count": approved_tenure_months,
                    "quantity": 1,
                    "customer_notify": 1,
                    "start_at": unix_timestamp
                }
            )
            if not created_sub:
                return {
                    "success": False,
                    "message": "Failed to create subscription",
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "data": {}
                }

            loan_details.emi_start_day_atm = emi_schedule_date

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
 
@router.get("/get-subscription-actual-invoices/{subscription_id}")
def get_subscription_invoices(subscription_id: str, service: RazorpayService = Depends(get_razorpay_service), count: int = 10, skip: int = 0):
    """
    Fetch all invoices for a given subscription with optional pagination params.
    """
    try:
        razorpay_invoices = service.fetch_invoices_for_subscription(subscription_id, count=count, skip=skip)
        #NOTE: Create or Update Invoices inside Invoice Table
        invoice_service = InvoiceService(DBInterface(Invoice))
        with DBSession() as session:
            # Find the database subscription ID
            subscription = (
                session.query(Subscription)
                .options(
                    selectinload(Subscription.foreclosures).selectinload(ForeClosure.payment_details),
                    selectinload(Subscription.prepayment).selectinload(PrePayment.payment_details),
                    selectinload(Subscription.invoices).selectinload(Invoice.payment_details),
                )
                .filter_by(
                    razorpay_subscription_id=subscription_id,
                    is_deleted=False
                )
                .first()
            )
            if not subscription:
                return {
                    "success": False,
                    "message": f"Subscription {subscription_id} not found",
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "data": {"error": f"Subscription {subscription_id} not found"}
                }
                
            # Process each invoice: create or update
            emi_number = 1
            for invoice_data in razorpay_invoices.get("items"):
                razorpay_invoice_id = invoice_data.get("id")
                if not razorpay_invoice_id:
                    print("Skipping invoice with no ID")
                    continue
               
                # Prepare invoice data
                invoice_common_data = map_razorpay_invoice_to_db(invoice_json=invoice_data, emi_number=emi_number, payment_detail_id=None, subscription_id=subscription.id)
                
                # Check for existing invoice
                existing_invoice = session.query(Invoice).filter_by(
                    razorpay_invoice_id=razorpay_invoice_id,
                    is_deleted=False
                ).first()

                if not existing_invoice:
                    print(f"Creating new invoice: {razorpay_invoice_id}")
                    data = invoice_service.create_invoice(invoice_common_data)
                else:
                    print(f"Updating existing invoice: {razorpay_invoice_id}")
                    update_data = {k: v for k, v in invoice_common_data.items() if v is not None}
                    data = invoice_service.update_invoice(
                        invoice_id=existing_invoice.id,
                        form_data=update_data
                    )
                emi_number+=1
            # Fetch All existed EMI Invoices 
            #NOTE Fetch all payment.subscription invoice as well
            # Lets fetch Foreclosure and Pre-payment invoice details       
            sub_foreclosure = subscription.foreclosures
            sub_pre_payments =  subscription.prepayment
            
            for foreclosure in sub_foreclosure:
                foreclosure_payment_links = foreclosure.payment_details
                payment_details = service.get_payment_link_details(foreclosure_payment_links.payment_id) 
                # check status 
                if payment_details.get("status") == "paid":
                    create_prepayment_invoice = map_payment_link_to_invoice_obj(payment=payment_details,
                                                                                emi_number=1,
                                                                                payment_detail_id = foreclosure_payment_links.id,
                                                                                subscription_id=subscription.id,
                                                                                invoice_type="foreclosure"
                                                                                )
                    # Check for existing invoice
                    existing_invoice_1 = session.query(Invoice).filter_by(
                        razorpay_invoice_id=create_prepayment_invoice.get("razorpay_invoice_id"),
                        subscription_id=subscription.id,
                        is_deleted=False
                    ).first()
                    if not existing_invoice_1:
                        print(f"Creating new invoice: {razorpay_invoice_id}")
                        data = invoice_service.create_invoice(create_prepayment_invoice)
                    else:
                        print(f"Updating existing invoice: {razorpay_invoice_id}")
                        update_data = {k: v for k, v in create_prepayment_invoice.items() if v is not None}
                        data = invoice_service.update_invoice(
                            invoice_id=existing_invoice_1.id,
                            form_data=update_data
                        )
                    
                                    
            for pre_payments in sub_pre_payments:
                pre_payments_payment_links = pre_payments.payment_details
                payment_details = service.get_payment_link_details(pre_payments_payment_links.payment_id) 
                if payment_details.get("status") == "paid":
                    create_prepayment_invoice = map_payment_link_to_invoice_obj(payment=payment_details,
                                                                                emi_number=1,
                                                                                payment_detail_id = pre_payments_payment_links.id,
                                                                                subscription_id=subscription.id,
                                                                                invoice_type="pre_payment"
                                                                                )
                    # Check for existing invoice
                    existing_invoice_1 = session.query(Invoice).filter_by(
                        razorpay_invoice_id=create_prepayment_invoice.get("razorpay_invoice_id"),
                        subscription_id=subscription.id,
                        is_deleted=False
                    ).first()
                    if not existing_invoice_1:
                        print(f"Creating new invoice: {razorpay_invoice_id}")
                        data = invoice_service.create_invoice(create_prepayment_invoice)
                    else:
                        print(f"Updating existing invoice: {razorpay_invoice_id}")
                        update_data = {k: v for k, v in create_prepayment_invoice.items() if v is not None}
                        data = invoice_service.update_invoice(
                            invoice_id=existing_invoice_1.id,
                            form_data=update_data
                        )
            invoices = invoice_service.get_all_invoices(subscription_id=subscription.id)   
                
        return {
            "success": True,
            "message": "Invoices fetched successfully!",
            "status_code": status.HTTP_200_OK,
            "data": invoices
        }
    except Exception as e:
        return {
            "success": False,
            "message": "Failed to fetch invoices",
            "status_code": 500,
            "data": {"error": str(e)}
        }

@router.get("/get-closure-payment-link/{subscription_id}")
def get_closure_payment_link(
    subscription_id: str,
    callback_url: str = Query(..., description="URL to redirect after payment"),
    service: RazorpayService = Depends(get_razorpay_service)
):
    try:
        # Step 1: Fetch subscription from Razorpay
        sub = service.fetch_subscription(subscription_id)
        if not sub:
            return {
                "success": False,
                "message": "Subscription not found",
                "status_code": status.HTTP_404_NOT_FOUND,
                "data": {}
            }

        # Step 2: Fetch plan from Razorpay
        plan = service.fetch_plan(sub['plan_id'])
        if not plan:
            return {
                "success": False,
                "message": "Plan not found",
                "status_code": status.HTTP_404_NOT_FOUND,
                "data": {}
            }

        # Step 3: Fetch local subscription details with related entities
        filters = [
            Subscription.razorpay_subscription_id == subscription_id,
            Subscription.is_deleted == False
        ]
        with DBSession() as session:
            local_subscription = (
                session.query(Subscription)
                .options(
                    selectinload(Subscription.plan),
                    selectinload(Subscription.plan).selectinload(Plan.applicant),
                    selectinload(Subscription.plan).selectinload(Plan.applicant).selectinload(LoanApplicant.approval_details)
                )
                .filter(*filters)
                .first()
            )

            if not local_subscription:
                return {
                    "success": False,
                    "message": "Subscription not found in DB",
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "data": {}
                }

            # Access loan details
            loan = local_subscription.plan.applicant if local_subscription.plan else None
            if not loan or not loan.approval_details:
                return {
                    "success": False,
                    "message": "No loan or approval details associated with this subscription",
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "data": {}
                }

            loan_approval_detail = loan.approval_details[0]
            user_accepted_amount = loan_approval_detail.user_accepted_amount
            approved_interest_rate = loan_approval_detail.approved_interest_rate
            approved_tenure_months = loan_approval_detail.approved_tenure_months
            approved_processing_fee = loan_approval_detail.approved_processing_fee

            # Step 4: Calculate EMI schedule
            emi_result = calculate_emi_schedule(
                loan_amount=user_accepted_amount,
                tenure_months=approved_tenure_months,
                annual_interest_rate=approved_interest_rate,
                processing_fee=approved_processing_fee,
                is_fee_percentage=True,
                loan_type=loan.loan_type,
                emi_start_day_atm=loan.emi_start_day_atm,
            )
            if not emi_result:
                return {
                    "success": False,
                    "message": "Failed to calculate EMI schedule",
                    "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "data": {}
                }

        # Step 5: Validate and compute foreclosure amount from EMI schedule
        required_sub_keys = ['paid_count', 'total_count', 'remaining_count']
        if not all(key in sub for key in required_sub_keys):
            raise KeyError(f"Missing required keys in 'sub': {required_sub_keys}")

        paid_based_on_data = sub['total_count'] - sub['remaining_count']
        if paid_based_on_data < 0:
            raise ValueError("'paid_based_on_data' cannot be negative")

        paid_principal_amt = 0.0
        interest_paid_amt = 0.0
        foreclosure_amt = 0.0

        if paid_based_on_data > 0:
            schedule = emi_result.get("data", {}).get("schedule", [])
            if len(schedule) < paid_based_on_data:
                raise IndexError(f"Schedule length ({len(schedule)}) is less than required ({paid_based_on_data})")

            for emi in schedule[:paid_based_on_data]:
                if not isinstance(emi, dict):
                    raise TypeError("EMI entry must be a dictionary")

                paid_principal_amt += emi.get("principal_paid", 0.0)
                interest_paid_amt += emi.get("interest_paid", 0.0)
                foreclosure_amt = emi.get("balance", 0.0)
            # Set foreclosure_amt to the balance of the next EMI (if available)
            if paid_based_on_data < len(schedule):
                foreclosure_amt = schedule[paid_based_on_data].get("balance", 0.0)
            else:
                foreclosure_amt = 0.0  # No balance left if all EMIs are paid
        elif paid_based_on_data == 0:
            foreclosure_amt = user_accepted_amount

        # If foreclosure_amt is still 0 and remaining_count > 0, set to full loan amount or handle appropriately
        if foreclosure_amt == 0.0 and sub['remaining_count'] > 0:
            foreclosure_amt = user_accepted_amount  # Fallback to principal if no payments

        # Step 6: Create unique reference ID and payment link
        ref_id = f"{sub['id']}+{int(time.time() * 1000)}"
        max_retries = 3  # To handle duplicate reference_id
        for attempt in range(max_retries):
            try:
                payment = service.create_payment_link(
                    amount=foreclosure_amt * 100,
                    currency="INR",
                    description="forclosure_payment",
                    subscription_id=ref_id,
                    callback_url=callback_url
                )
                if not payment:
                    raise ValueError("Failed to create payment link")
                break  # Success, exit retry loop
            except Exception as e:
                error_message = str(e)
                if "payment link with given reference_id" in error_message and "already exists" in error_message:
                    if attempt < max_retries - 1:
                        ref_id = f"{sub['id']}+{int(time.time() * 1000)}"  # Regenerate ref_id
                        continue
                    else:
                        return {
                            "success": False,
                            "message": "Failed to create unique payment link after retries",
                            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                            "data": {}
                        }
                else:
                    raise  # Rethrow other exceptions

        # Step 7: Create foreclosure and payment details in DB
        foreclosure_data = {
            "subscription_id": local_subscription.id,
            "amount": foreclosure_amt,
            "reason": "Subscription Closure",
            "status": "pending"
        }
        foreclosure_response = foreclosure_service.create_foreclosure(foreclosure_data)
        if not foreclosure_response['success']:
            return {
                "success": False,
                "message": foreclosure_response,
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "data": {}
            }

        payment_details_data = {
            "payment_id": payment['id'],
            "amount": foreclosure_amt,
            "currency": "INR",
            "status": payment['status'],
            "payment_method": None,
            "foreclosure_id": foreclosure_response["data"].id
        }
        payment_details_response = payment_details_service.create_payment_details(payment_details_data)
        if not payment_details_response['success']:
            return {
                "success": False,
                "message": payment_details_response,
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "data": {}
            }

        # Step 8: Return success
        return {
            "success": True,
            "message": "Payment Link Created Successfully!",
            "status_code": status.HTTP_200_OK,
            "data": {"payment": payment}
        }

    except KeyError as ke:
        return {
            "success": False,
            "message": f"Key error: {str(ke)}",
            "status_code": status.HTTP_400_BAD_REQUEST,
            "data": {}
        }
    except ValueError as ve:
        return {
            "success": False,
            "message": f"Value error: {str(ve)}",
            "status_code": status.HTTP_400_BAD_REQUEST,
            "data": {}
        }
    except IndexError as ie:
        return {
            "success": False,
            "message": f"Index error: {str(ie)}",
            "status_code": status.HTTP_400_BAD_REQUEST,
            "data": {}
        }
    except TypeError as te:
        return {
            "success": False,
            "message": f"Type error: {str(te)}",
            "status_code": status.HTTP_400_BAD_REQUEST,
            "data": {}
        }
    except Exception as e:
        return {
            "success": False,
            "message": "Internal Server Error",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "data": {"error": str(e)}
        }
        
@router.get("/get-payment-details/{payment_id}")
def get_payment_details(payment_id: str, service: RazorpayService = Depends(get_razorpay_service)):
    """
    API to fetch payment details from Razorpay.
    """
    try:
        payment_link_details = service.get_payment_link_details(payment_id)
        return {
            "success": True,
            "message": "Payment link details fetched successfully!",
            "status_code": status.HTTP_200_OK,
            "data": {"payment_link_data": payment_link_details}
        }
    except Exception as e:
        return {
            "success": False,
            "message": "Failed to fetch paymengt link details",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "data": {"error": str(e)}
        }
        
        
@router.get("/get-pre-payment-link/{subscription_id}")
def get_closure_payment_link(
    subscription_id: str,
    callback_url: str = Query(..., description="URL to redirect after payment"),
    is_due_payment: bool = Query(..., description="Checks if its Pre-Payment or Due-Payment"),
    service: RazorpayService = Depends(get_razorpay_service)
):
    try:
        # Step 1: Fetch subscription from Razorpay
        sub = service.fetch_subscription(subscription_id)
        if not sub:
            return JSONResponse(
                content={"success": False, "message": "Subscription not found", "data": {}},
                status_code=status.HTTP_404_NOT_FOUND
            )
            
        if sub.get("status") != "active":
             return JSONResponse(
                content={"success": False, "message": "The subscription status is not Active. To proceed with pre-payment, the subscription must be in Active status.", "data": {}},
                status_code=status.HTTP_404_NOT_FOUND
            )

        # Step 2: Fetch plan from Razorpay
        plan = service.fetch_plan(sub['plan_id'])
        if not plan:
            return JSONResponse(
                content={"success": False, "message": "Plan not found", "data": {}},
                status_code=status.HTTP_404_NOT_FOUND
            )

        # Step 3: Fetch local subscription details with related entities
        filters = [
            Subscription.razorpay_subscription_id == subscription_id,
            Subscription.is_deleted == False
        ]
        with DBSession() as session:
            local_subscription = (
                session.query(Subscription)
                .options(
                    selectinload(Subscription.plan),
                    selectinload(Subscription.plan).selectinload(Plan.applicant),
                    selectinload(Subscription.plan).selectinload(Plan.applicant).selectinload(LoanApplicant.approval_details)
                )
                .filter(*filters)
                .first()
            )

            if not local_subscription:
                return JSONResponse(
                    content={"success": False, "message": "Subscription not found in DB", "data": {}},
                    status_code=status.HTTP_404_NOT_FOUND
                )

            # Access loan details
            loan = local_subscription.plan.applicant if local_subscription.plan else None
            if not loan or not loan.approval_details:
                return JSONResponse(
                    content={"success": False, "message": "No loan or approval details associated with this subscription", "data": {}},
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            loan_approval_detail = loan.approval_details[0]
            user_accepted_amount = loan_approval_detail.user_accepted_amount
            approved_interest_rate = loan_approval_detail.approved_interest_rate
            approved_tenure_months = loan_approval_detail.approved_tenure_months
            approved_processing_fee = loan_approval_detail.approved_processing_fee

            # Step 4: Calculate EMI schedule
            emi_result = calculate_emi_schedule(
                loan_amount=user_accepted_amount,
                tenure_months=approved_tenure_months,
                annual_interest_rate=approved_interest_rate,
                processing_fee=approved_processing_fee,
                is_fee_percentage=True,
                loan_type=loan.loan_type
            )
            if not emi_result:
                return JSONResponse(
                    content={"success": False, "message": "Failed to calculate EMI schedule", "data": {}},
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        # Step 5: Fetch The Value for Next Payment
        required_sub_keys = ['paid_count', 'total_count', 'remaining_count']
        if not all(key in sub for key in required_sub_keys):
            raise KeyError(f"Missing required keys in 'sub': {required_sub_keys}")

        paid_based_on_data = sub['total_count'] - sub['remaining_count']
        if paid_based_on_data < 0:
            raise ValueError("'paid_based_on_data' cannot be negative")
        
        schedule = emi_result.get("data", {}).get("schedule", [])
        emi_amount_each_month = schedule[0].get("emi")
        if paid_based_on_data == 0 : # User has not paid any EMI yet
            emi_stepper = 1
        else: # User
            emi_stepper = paid_based_on_data + 1
        # Step 6: Create unique reference ID and payment link
        ref_id = f"{sub['id']}+{int(time.time() * 1000)}"
        max_retries = 3  # To handle duplicate reference_id
        for attempt in range(max_retries):
            try:
                payment = service.create_payment_link(
                    amount=emi_amount_each_month * 100,
                    currency="INR",
                    description="pre_payment" if is_due_payment == False else "due_payment",
                    subscription_id=ref_id,
                    callback_url=callback_url,
                    is_due_payment=is_due_payment
                )
                if not payment:
                    raise ValueError("Failed to create payment link")
                break  # Success, exit retry loop
            except Exception as e:
                error_message = str(e)
                if "payment link with given reference_id" in error_message and "already exists" in error_message:
                    if attempt < max_retries - 1:
                        ref_id = f"{sub['id']}+{int(time.time() * 1000)}"  # Regenerate ref_id
                        continue
                    else:
                        return JSONResponse(
                            content={"success": False, "message": "Failed to create unique payment link after retries", "data": {}},
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                        )
                else:
                    raise  # Rethrow other exceptions

        # Step 7: Create PrePayment and payment details in DB
        pre_payment_data = {
            "subscription_id": local_subscription.id,
            "amount": emi_amount_each_month,
            "reason": "Subscription Pre Payment",
            "status": "pending",
            "emi_stepper": emi_stepper,
            "is_due_payment": is_due_payment
        }
        prepayment_response = pre_payment_service.create_pre_payment(pre_payment_data)
        if not prepayment_response['success']:
            return JSONResponse(
                content=prepayment_response,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        payment_details_data = {
            "payment_id": payment['id'],
            "amount": emi_amount_each_month,
            "currency": "INR",
            "status": payment['status'],
            "payment_method": None,
            "prepayment_id": prepayment_response["data"].id
        }
        payment_details_response = payment_details_service.create_payment_details(payment_details_data)
        if not payment_details_response['success']:
            return JSONResponse(
                content=payment_details_response,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Step 8: Return success
        return JSONResponse(
            content={"success": True, "message": "Payment Link Created Successfully!", "data": {"payment": payment}},
            status_code=status.HTTP_200_OK
        )

    except KeyError as ke:
        return JSONResponse(
            content={"success": False, "message": f"Key error: {str(ke)}", "data": {}},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except ValueError as ve:
        return JSONResponse(
            content={"success": False, "message": f"Value error: {str(ve)}", "data": {}},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except IndexError as ie:
        return JSONResponse(
            content={"success": False, "message": f"Index error: {str(ie)}", "data": {}},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except TypeError as te:
        return JSONResponse(
            content={"success": False, "message": f"Type error: {str(te)}", "data": {}},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return JSONResponse(
            content={"success": False, "message": "Internal Server Error", "data": {"error": str(e)}},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        
