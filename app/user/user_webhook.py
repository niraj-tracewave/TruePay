import json
import hmac
import hashlib
from db_domains.db import DBSession
from models.razorpay import Subscription
from fastapi import Request, APIRouter
from fastapi.responses import JSONResponse
from config import app_config
from fastapi import APIRouter, Request
from services.razorpay_service import RazorpayService
razorpay_service_obj = RazorpayService(
                app_config.RAZORPAY_KEY_ID, app_config.RAZORPAY_SECRET)

router = APIRouter(prefix="/razorpay", tags=["RazorPay API's"])

@router.post("/webhook")
async def razorpay_webhook(request: Request):
    body = await request.body()

    x_razorpay_signature = request.headers.get("X-Razorpay-Signature")

    try:
        headers = request.headers
        body_bytes = await request.body()
        body_str = body_bytes.decode("utf-8")

        # Verify signature
        generated_sig = hmac.new(
            app_config.WEBHOOK_SECRET.encode('utf-8'),
            body_bytes,
            hashlib.sha256
        ).hexdigest()

        if generated_sig != x_razorpay_signature:
            return JSONResponse(content={"status": "invalid signature"}, status_code=400)

        # Parse event data
        data = json.loads(body_str)
        event = data.get("event")
        match event:
            case "subscription.activated":
                sub_id = data.get("payload").get(
                    "subscription", {}).get("entity", {}).get("id")
                print("sub_id", sub_id)
                if sub_id:
                    filters = [
                        Subscription.razorpay_subscription_id == sub_id,
                        Subscription.is_deleted == False
                    ]
                    with DBSession() as session:
                        sub_data = (
                            session.query(Subscription)

                            .filter(*filters)
                            .first()
                        )
                        print("sub_data", sub_data)
                        if not sub_data:
                            pass
                        sub_data.status = "active"
                        session.commit()
            case "subscription.authenticated":
                sub_id = data.get("payload").get(
                    "subscription", {}).get("entity", {}).get("id")
                print("sub_id", sub_id)
                if sub_id:
                    filters = [
                        Subscription.razorpay_subscription_id == sub_id,
                        Subscription.is_deleted == False
                    ]
                    with DBSession() as session:
                        sub_data = (
                            session.query(Subscription)

                            .filter(*filters)
                            .first()
                        )
                        print("sub_data", sub_data)
                        if not sub_data:
                            pass
                        sub_data.status = "authenticated"
                        session.commit()
            case "payment.authenticated":
                print("Payment Authenticated:", data)
                print("Event:", event)
            case "payment.captured":
                print("Payment Captured:", data)
                print("Event:", event)
                payload = data.get("payload")
                payment_id = payload["payment"]["entity"]["id"]
                # Step 1: Fetch payment details from Razorpay
                payment = razorpay_service_obj.fetch_payment_details(payment_id)
                breakpoint()
                # Step 2: This contains the payment link ID
                payment_link_id = payment.get("payment_link_id")

            case _:
                # logger.warning("Unhandled event: %s", event)
                return JSONResponse(content={"status": "success"})
    except Exception as e:
        print("Webhook Error:", str(e))
        return JSONResponse(content={"status": "error"}, status_code=500)
