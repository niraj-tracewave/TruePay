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
from common.enums import InvoiceStatus
from common.utils import map_razorpay_invoice_to_db

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
                        current_loan_status = sub_data.plan.applicant.status
                        if current_loan_status not in ["DISBURSED", "DISBURSEMENT_APPROVAL_PENDING", "COMPLETED", "CANCELLED", "CLOSED"]: 
                            sub_data.plan.applicant.status = "E_MANDATE_GENERATED"
                        session.commit()
            
            case "payment_link.paid":
                try:
                    # NOTE: Here Check wether the paid payment is from foreclosure or pre-payment
                    # Extract entity safely
                    entity = data.get("payload", {}).get("payment_link", {}).get("entity")
                    description_flag = entity.get("description")
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
                        payment_link_id, "paid", description_flag
                    )
                    print(f" Payment link {payment_link_id} status updated to 'paid' in database.")

                except Exception as e:
                        print(f"Error processing payment_link.paid event: {e}")

            case event if event.startswith("invoice."):
                invoice_data = data.get("payload", {}).get("invoice", {}).get("entity", {})
                razorpay_invoice_id = invoice_data.get("id")
                if not razorpay_invoice_id:
                    print("No invoice ID found in payload")
                    
                invoice_data = data.get("payload", {}).get("invoice", {}).get("entity", {})
                

                match event:
                    case "invoice.draft":
                        invoice_status = InvoiceStatus.DRAFT
                    case "invoice.issued":
                        invoice_status = InvoiceStatus.ISSUED
                    case "invoice.paid":
                        invoice_status = InvoiceStatus.PAID
                    case "invoice.partially_paid":
                        invoice_status = InvoiceStatus.PARTIALLY_PAID
                    case "invoice.cancelled":
                        invoice_status = InvoiceStatus.CANCELLED
                    case "invoice.expired":
                        invoice_status = InvoiceStatus.EXPIRED
                    case _:
                        print(f"Unsupported invoice event: {event}")
                        invoice_status = None  # or handle as needed
                
                breakpoint() #NOTE WIP
                payment_detail_id = invoice_data.get("payment_id")  # e.g., "pay_R8OMiogb7wcP1w"
                subscription_id = invoice_data.get("subscription_id")  # e.g., "sub_R7ydKxyc2QrqUV"
                emi_number = 1  # Example: Set based on your business logic
                    
                # Map to database format
                db_invoice = map_razorpay_invoice_to_db(
                    invoice_json=invoice_data,
                    emi_number=emi_number,
                    payment_detail_id=None,
                    subscription_id=subscription_id if subscription_id else None
                )
                # Update status based on event if needed
                db_invoice["status"] = invoice_status.value if invoice_status else invoice_data.get("status", "draft")

                print(f"Mapped invoice data: {db_invoice}")
            case _:
                # logger.warning("Unhandled event: %s", event)
                return JSONResponse(content={"status": "success"})
    except Exception as e:
        print("Webhook Error:", str(e))
        return JSONResponse(content={"status": "error"}, status_code=500)
