import razorpay
from typing import Optional, Dict

class RazorpayService:
    def __init__(self, key_id: str, key_secret: str):
        self.client = razorpay.Client(auth=(key_id, key_secret))

    def create_customer(self, name: str, email: str, contact: str) -> Dict:
        """
        Create a customer in Razorpay
        """
        return self.client.customer.create({
            "name": name,
            "email": email,
            "contact": contact
        })

    def create_plan(self, name: str, amount: int, interval: int = 1, period: str = "monthly") -> Dict:
        """
        Create a subscription plan for EMI
        amount in paise
        """
        return self.client.plan.create({
            "period": period,
            "interval": interval,
            "item": {
                "name": name,
                "amount": amount,
                "currency": "INR"
            }
        })

    def create_subscription(self, plan_id: str, total_count: int, customer_notify: int = 1, start_at: Optional[int] = None) -> Dict:
        """
        Create a subscription for a plan
        start_at: Unix timestamp (optional)
        """
        data = {
            "plan_id": plan_id,
            "customer_notify": customer_notify,
            "total_count": total_count
        }
        if start_at:
            data["start_at"] = start_at
        return self.client.subscription.create(data)

    def fetch_subscription(self, subscription_id: str) -> Dict:
        """
        Fetch subscription details
        """
        return self.client.subscription.fetch(subscription_id)

    def cancel_subscription(self, subscription_id: str) -> Dict:
        """
        Cancel a subscription
        """
        return self.client.subscription.cancel(subscription_id)

    def verify_webhook_signature(self, payload_body: str, signature: str, secret: str) -> bool:
        """
        Verify Razorpay webhook signature
        """
        try:
            self.client.utility.verify_webhook_signature(payload_body, signature, secret)
            return True
        except razorpay.errors.SignatureVerificationError:
            return False
