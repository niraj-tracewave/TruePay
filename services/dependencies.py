from config import app_config
from services.razorpay_service import RazorpayService

def get_razorpay_service():
    return RazorpayService(app_config.RAZORPAY_KEY_ID, app_config.RAZORPAY_SECRET)
