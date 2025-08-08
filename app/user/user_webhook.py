import json
import hmac
import hashlib
from db_domains.db import DBSession
from models.razorpay import Subscription
from fastapi import Request, APIRouter
from fastapi.responses import JSONResponse
from config import app_config
from fastapi import APIRouter, Request

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


                # subscription_id = data.get("payload", {}).get("subscription", {}).get("entity", {}).get("id")
                # logger.info("--------authenticated", body)
                # logger.info("Subscription Authenticated:", data)
                # logger.info("Subscription ID:", subscription_id)

            # case "subscription.charged":
            #     logger.info("--------charged %s", body)
            #     print("EMI Charged:", data)

            # case "payment.failed":
            #     print("Payment Failed:", data)

            # case "subscription.completed":
            #     logger.info("--------completed %s", body)
            #     print("Subscription Completed:", data)

            case _:
                # logger.warning("Unhandled event: %s", event)
                return JSONResponse(content={"status": "success"})
    except Exception as e:
        print("Webhook Error:", str(e))
        return JSONResponse(content={"status": "error"}, status_code=500)
