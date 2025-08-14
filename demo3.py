import razorpay
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pytz

# Initialize Razorpay client
client = razorpay.Client(auth=("rzp_test_ksbxGR8ZgbHtkv", "SIbiNOSS6bJwX9wEIxuLZ93c"))
# Step 1: Fetch subscription to determine the next due EMI
subscription_id = "sub_R5BNRsye1gwRQD"
try:
    subscription = client.subscription.fetch(subscription_id)
    current_paid_count = subscription['paid_count']
    next_emi_month = current_paid_count + 1  # e.g., Month 2
    print(f"Next Due EMI: Month {next_emi_month}")
except Exception as e:
    print(f"Error fetching subscription: {e}")
    exit()

# Step 2: Create a payment link for the next due EMI (Month 2)
payment_link_data = {
    "amount": 300000,  # ₹3,000 in paise, including 18% GST
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

# Step 3: Pause the subscription to skip Month 2 auto-debit
try:
    client.subscription.pause(subscription_id)
    print(f"Subscription Paused for Month {next_emi_month}")
except Exception as e:
    print(f"Error pausing subscription: {e}")
    exit()

# # Step 4: Confirm payment (simulate or use webhook in production)
# time.sleep(5)  # Replace with webhook or periodic polling in production
# try:
#     payment_link_details = client.payment_link.fetch(payment_link_id)
#     if payment_link_details['status'] == 'paid':
#         print(f"Month {next_emi_month} EMI Payment Confirmed")
#         # Track in your system (e.g., database)
#         # Example: your_database.update_paid_count(subscription_id, f"Month {next_emi_month}", "paid")
#         print(f"Custom Paid Count Updated: Month {next_emi_month} marked as paid")
#     else:
#         print(f"Payment not completed. Status: {payment_link_details['status']}")
#         exit()
# except Exception as e:
#     print(f"Error fetching payment link: {e}")
#     exit()

# Step 5: Resume subscription for the next month (Month 3)
# Set resume_at to one month after the current billing cycle
current_date = datetime.now(pytz.timezone('Asia/Kolkata'))  # IST timezone
resume_date = (current_date + relativedelta(months=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
resume_timestamp = int(resume_date.timestamp())

resume_data = {
    "resume_at": resume_timestamp  # Start of next month (e.g., October 1, 2025)
}

try:
    client.subscription.resume(subscription_id, resume_data)
    subscription = client.subscription.fetch(subscription_id)
    update_data =  {
                    "remaining_count": subscription['remaining_count'] - 1,
                    "paid_count":subscription['paid_count']+1,
                    "schedule_change_at": "now",
                    }
    breakpoint()
    client.subscription.edit(subscription_id, update_data)
    print(f"Subscription Resumed from {resume_date.strftime('%Y-%m-%d')} for Month {next_emi_month + 1} onward")
except Exception as e:
    print(f"Error resuming subscription: {e}")
    exit()

# Step 6: Verify subscription status and next billing date
try:
    subscription = client.subscription.fetch(subscription_id)
    print("Subscription Status:", subscription['status'])
    print("Razorpay Paid Count:", subscription['paid_count'])  # Won't reflect manual payment
    print("Remaining Count:", subscription['remaining_count'])
    print("Next Billing Date (Unix Timestamp):", subscription['current_end'])
except Exception as e:
    print(f"Error fetching subscription: {e}")