from fastapi import APIRouter, Depends
from services.dependencies import get_razorpay_service
from services.razorpay_service import RazorpayService
from datetime import datetime, timedelta

router = APIRouter(prefix="/razorpay", tags=["Surpass API's"])


@router.post("/create-emi-plan")
def create_emi_plan(service: RazorpayService = Depends(get_razorpay_service)):
    plan = service.create_plan(
    name=f"Loan EMI Plan ₹{55000}",
    amount=int(5500 * 100),  # Convert to paise
    interval=10,
    period="monthly"
)
    return {"plan": plan}

@router.post("/create-subscription/{plan_id}")
def create_subscription(plan_id: str, service: RazorpayService = Depends(get_razorpay_service)):
    start_at = int((datetime.now() + timedelta(days=1)).timestamp())
    subscription = service.create_subscription(plan_id=plan_id, total_count=12, start_at=start_at)
    return {"subscription": subscription}