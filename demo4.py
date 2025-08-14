import razorpay
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pytz

# Initialize Razorpay client
client = razorpay.Client(auth=("rzp_test_ksbxGR8ZgbHtkv", "SIbiNOSS6bJwX9wEIxuLZ93c"))


# Simulated database to track paid EMIs and counts
class SubscriptionTracker:
    def __init__(self):
        self.paid_emis = {}  # {subscription_id: {emi_month: status}}
        self.custom_counts = {}  # {subscription_id: {paid_count: int, remaining_count: int}}

    def update_paid_emi(self, subscription_id, emi_month, status, total_count=10):
        if subscription_id not in self.paid_emis:
            self.paid_emis[subscription_id] = {}
            self.custom_counts[subscription_id] = {"paid_count": 0, "remaining_count": total_count}
        self.paid_emis[subscription_id][emi_month] = status
        # if status == "paid":
        self.custom_counts[subscription_id]["paid_count"] += 1
        self.custom_counts[subscription_id]["remaining_count"] -= 1
        print(f"Updated {subscription_id}: {emi_month} marked as {status}")
        print(f"Custom Counts: Paid = {self.custom_counts[subscription_id]['paid_count']}, "
              f"Remaining = {self.custom_counts[subscription_id]['remaining_count']}")

tracker = SubscriptionTracker()

# Step 1: Fetch subscription to determine the next due EMI
subscription_id = "sub_R5B13JlUeW9sgB"  # Replace with actual ID
try:
    subscription = client.subscription.fetch(subscription_id)
    current_paid_count = subscription['paid_count']
    next_emi_month = current_paid_count + 1  # e.g., Month 2
    print(f"Next Due EMI: Month {next_emi_month}")
except Exception as e:
    print(f"Error fetching subscription: {e}")
    exit()

# Step 2: Pause subscription to skip next due EMI auto-debit
try:
    client.subscription.pause(subscription_id)
    print(f"Subscription Paused for Month {next_emi_month}")
except Exception as e:
    print(f"Error pausing subscription: {e}")
    exit()

# Step 3: Create payment link for the next due EMI
payment_link_data = {
    "amount": 300000,  # ₹3,000 in paise, including 18% GST (base ~₹2,542.37 + ₹457.63)
    "currency": "INR",
    "description": f"Manual Payment for Month {next_emi_month} EMI",
    "reminder_enable": True,
    "notes": {
        "subscription_id": subscription_id,
        "emi_month": f"Month {next_emi_month}"
    },
    "callback_url": "https://yourwebsite.com/callback",
    "callback_method": "get"
}

try:
    payment_link = client.payment_link.create(data=payment_link_data)
    print(f"Manual Payment Link for Month {next_emi_month} EMI:", payment_link['short_url'])
    payment_link_id = payment_link['id']
except Exception as e:
    print(f"Error creating payment link: {e}")
    exit()

# Step 4: Confirm payment and mark as paid (simulate or use webhook in production)
time.sleep(5)  # Replace with webhook or periodic polling
try:
    payment_link_details = client.payment_link.fetch(payment_link_id)
    # if payment_link_details['status'] == 'paid':
    #     print(f"Month {next_emi_month} EMI Payment Confirmed")
    # else:
    #     print(f"Payment not completed. Status: {payment_link_details['status']}")
    #     exit()
    tracker.update_paid_emi(subscription_id, f"Month {next_emi_month}", "paid")
except Exception as e:
    print(f"Error fetching payment link: {e}")
    exit()

# Step 5: Resume subscription for the next month (Month 3)
current_date = datetime.now(pytz.timezone('Asia/Kolkata'))  # IST timezone (04:05 PM, Aug 14, 2025)
resume_date = (current_date + relativedelta(months=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
resume_timestamp = int(resume_date.timestamp())

resume_data = {
    "resume_at": 1760400000  # Start of next month (e.g., October 1, 2025)
}

try:
    client.subscription.resume(subscription_id, resume_data)
    print(f"Subscription Resumed from {resume_date.strftime('%Y-%m-%d')} for Month {next_emi_month + 1} onward")
except Exception as e:
    print(f"Error resuming subscription: {e}")
    exit()

# Step 6: Verify subscription status and next billing date
try:
    subscription = client.subscription.fetch(subscription_id)
    print("Subscription Status:", subscription['status'])
    print("Razorpay Paid Count:", subscription['paid_count'])  # Won't reflect manual payment
    print("Razorpay Remaining Count:", subscription['remaining_count'])
    print("Next Billing Date (Unix Timestamp):", subscription['current_end'])
    print("Custom Paid EMIs:", tracker.paid_emis.get(subscription_id, {}))
    print("Custom Counts:", tracker.custom_counts.get(subscription_id, {}))
except Exception as e:
    print(f"Error fetching subscription: {e}")