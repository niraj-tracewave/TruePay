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
from common.utills_webhook import WebhookDBService

razorpay_service_obj = RazorpayService(
                app_config.RAZORPAY_KEY_ID, app_config.RAZORPAY_SECRET)
webhook_dbService = WebhookDBService()

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
                        sub_data.plan.applicant.status = "E_MANDATE_GENERATED"
                        session.commit()
            
            case "payment_link.paid":
                try:
                    # Extract entity safely
                    entity = data.get("payload", {}).get("payment_link", {}).get("entity")
                    if not entity:
                        print("⚠ No payment link entity found in webhook payload.")
                        pass

                    payment_link_id = entity.get("id")
                    if not payment_link_id:
                        print("⚠ No payment link ID found in entity.")
                        pass

                    # Step 3: Update the payment link status in the database
                    print(f" Payment Link ID: {payment_link_id}")
                    # Example: update_payment_link_status(payment_link_id, "paid")
                    webhook_dbService.update_payment_link_status(
                        payment_link_id, "paid"
                    )
                    print(f" Payment link {payment_link_id} status updated to 'paid' in database.")

                except Exception as e:
                        print(f"Error processing payment_link.paid event: {e}")

            case _:
                # logger.warning("Unhandled event: %s", event)
                return JSONResponse(content={"status": "success"})
    except Exception as e:
        print("Webhook Error:", str(e))
        return JSONResponse(content={"status": "error"}, status_code=500)
