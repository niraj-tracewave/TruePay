from fastapi import APIRouter, Depends
from services.dependencies import get_razorpay_service
from services.razorpay_service import RazorpayService
from schemas.razorpay_schema import CreatePlanSchema, CreateSubscriptionSchema
router = APIRouter(prefix="/razorpay", tags=["RazorPay API's"])


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
