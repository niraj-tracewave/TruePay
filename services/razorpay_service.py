import razorpay
from typing import  Dict
from datetime import datetime

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

    def create_plan(self, plan_data: Dict) -> Dict:
        """
            Create a subscription plan for EMI
            plan_data should follow Razorpay API structure:
            {
                "period": "weekly",
                "interval": 1,
                "item": {
                    "name": "Test plan",
                    "amount": 69900,
                    "currency": "INR",
                    "description": "Optional description"
                },
                "notes": {
                    "notes_key_1": "Optional note 1",
                    "notes_key_2": "Optional note 2"
                }
            }
        """
        return self.client.plan.create(plan_data)
    # Function to calculate the Unix timestamp for the 5th of the next month
    
    def get_next_month_fifth_timestamp(self):
        # Get current date
        today = datetime.now()
        # Calculate next month
        next_month = today.month % 12 + 1
        year = today.year if next_month != 1 else today.year + 1
        # Set to the 5th of the next month
        next_month_date = datetime(year, next_month, 5)
        # Convert to Unix timestamp (seconds since epoch)
        return int(next_month_date.timestamp())

    def create_subscription(self, subscription_data: Dict) -> Dict:
        """
            Create a subscription for a plan using full payload structure:
            {
            "plan_id":"{plan_id}",
            "total_count":6,
            "quantity":1,
            "start_at":1735689600,
            "expire_by":1893456000,
            "customer_notify":1,
            "addons":[
                {
                "item":{
                    "name":"Delivery charges",
                    "amount":30000,
                    "currency":"INR"
                }
                }
            ],
            "offer_id":"{offer_id}",
            "notes":{
                "notes_key_1":"Tea, Earl Grey, Hot",
                "notes_key_2":"Tea, Earl Grey… decaf."
            }
            }
        """
        breakpoint()
        subscription_data["start_at"]= self.get_next_month_fifth_timestamp()
        return self.client.subscription.create(subscription_data)

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
            self.client.utility.verify_webhook_signature(
                payload_body, signature, secret)
            return True
        except razorpay.errors.SignatureVerificationError:
            return False
