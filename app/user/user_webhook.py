from fastapi import FastAPI, Request, Header
from fastapi.responses import JSONResponse
import hmac
import hashlib
import json

app = FastAPI()
 
WEBHOOK_SECRET = "@eQq3b23y6f9_kr"  # Same as Razorpay dashboard

from fastapi import APIRouter, Request, Query
from models.user import User

router = APIRouter(prefix="/razorpay")

@router.post("/webhook/")
async def razorpay_webhook(request: Request, x_razorpay_signature: str = Header(None)):
    try:
        headers = request.headers
        print("Incoming Headers:", headers)
        print("x_razorpay_signature:", x_razorpay_signature)
        body_bytes = await request.body()
        body_str = body_bytes.decode("utf-8")
        print("Raw Body:", body_str)

        # Verify signature
        generated_sig = hmac.new(
            WEBHOOK_SECRET.encode('utf-8'),
            body_bytes,
            hashlib.sha256
        ).hexdigest()

        print("Generated Signature:", generated_sig)
        print("Received Signature:", x_razorpay_signature)
        if generated_sig != x_razorpay_signature:
            return JSONResponse(content={"status": "invalid signature"}, status_code=400)

        # Parse event data
        data = json.loads(body_str)
        event = data.get("event")

        if event == "subscription.authenticated":
            print("Subscription Authenticated:", data)

        elif event == "subscription.charged":
            print("EMI Charged:", data)

        elif event == "payment.failed":
            print("Payment Failed:", data)

        elif event == "subscription.completed":
            print("Subscription Completed:", data)

        return JSONResponse(content={"status": "success"})
    except Exception as e:
        print("Webhook Error:", str(e))
        return JSONResponse(content={"status": "error"}, status_code=500)

# @router.post("/webhook/")
# async def razorpay_webhook(request: Request):
#     try:
#         body_bytes = await request.body()
#         print("Raw Body Bytes:", body_bytes)
#         body_str = body_bytes.decode("utf-8")
#         print("Raw Body String (repr):", repr(body_str))
#         print("Content-Length:", request.headers.get("content-length"))

#         signature = request.headers.get("X-Razorpay-Signature")
#         print("Received Signature:", signature)

#         if not signature:
#             return JSONResponse(content={"status": "missing signature"}, status_code=400)

#         generated_sig = hmac.new(
#             WEBHOOK_SECRET.encode('utf-8'),
#             body_bytes,
#             hashlib.sha256
#         ).hexdigest()

#         print("Generated Signature:", generated_sig)
#         if generated_sig != signature:
#             return JSONResponse(content={"status": "invalid signature"}, status_code=400)

#         data = json.loads(body_str)
#         event = data.get("event")

#         # handle events...
#         return JSONResponse(content={"status": "success"})

#     except Exception as e:
#         print("Webhook Error:", str(e))
#         return JSONResponse(content={"status": "error"}, status_code=500)
