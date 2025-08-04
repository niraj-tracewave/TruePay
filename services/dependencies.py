from services.razorpay_service import RazorpayService

def get_razorpay_service():
    RAZORPAY_KEY_ID = ""
    RAZORPAY_SECRET = ""
    return RazorpayService(RAZORPAY_KEY_ID, RAZORPAY_SECRET)
