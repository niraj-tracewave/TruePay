import razorpay
from typing import Dict
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
        subscription_data["start_at"]= self.get_next_month_fifth_timestamp()
        return self.client.subscription.create(subscription_data)
    
    def fetch_plan(self, plan_id: str) -> Dict:
        """
        Fetch plan details
        """
        return self.client.plan.fetch(plan_id)

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

    def fetch_invoices_for_subscription(self, subscription_id: str, count: int = 10, skip: int = 0) -> Dict:
        """
        Fetch all invoices for a given subscription.
        :param subscription_id: The Razorpay subscription ID.
        :param count: Number of invoices to fetch (max 100).
        :param skip: Number of invoices to skip (for pagination).
        """
        return self.client.invoice.all({
            "subscription_id": subscription_id,
            "count": count,
            "skip": skip
        })

    def create_payment_link(self, amount: int, currency: str, description: str, subscription_id: str):
        """
        Create a payment link for a specific amount and description.
        :param amount: Amount in paise (e.g., 10000 for ₹100).
        :param currency: Currency code (e.g., "INR").
        :param description: Description of the payment link.
        """
        return self.client.payment_link.create({
            "amount": amount,
            "currency": currency,
            "description": description,
            "accept_partial": False,
            "first_min_partial_amount": amount,
            "reference_id": subscription_id, #NOTE This to capture paymenet based on subscription
            "notify": {
                "sms": True,
                "email": True
            },
            "notes": {
                "subscription_id": subscription_id
            },
            "reminder_enable": True,
            "callback_url": "https://truepay.co.in/",
            "callback_method": "get"
        })

    def get_payment_link_details(self, payment_id: str):
        """
        Fetch payment details from Razorpay.
        :param payment_id: Razorpay payment ID (e.g., 'pay_29QQoUBi66xm2f').
        """
        try:
            payment = self.client.payment_link.fetch(payment_id)
            return payment
        except Exception as e:
            raise Exception(f"Error fetching payment details for {payment_id}: {str(e)}")

    def fetch_payment_details(self, payment_id: str):
        try:
            payment = self.client.payment.fetch(payment_id)
            return payment
        except Exception as e:
            raise Exception(f"Error fetching payment details for {payment_id}: {str(e)}")
