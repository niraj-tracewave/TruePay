import razorpay
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pytz

# Initialize Razorpay client
client = razorpay.Client(auth=("rzp_test_ksbxGR8ZgbHtkv", "SIbiNOSS6bJwX9wEIxuLZ93c"))

# Step 1: Create a payment link for the next month's EMI (Month 2)
payment_link_data = {
    "amount": 300000,  # Amount in paise (₹3,000, including 18% GST)
    "currency": "INR",
    "description": "Manual Payment for Month 2 EMI",
    "reminder_enable": True,
    "notes": {
        "subscription_id": "sub_R5B13JlUeW9sgB",
        "emi_month": "Month 2"
    },
    "callback_url": "https://yourwebsite.com/callback",  # Redirect after payment
    "callback_method": "get"
}

payment_link = client.payment_link.create(data=payment_link_data)
print("Manual Payment Link for Month 2 EMI:", payment_link['short_url'])

# Step 2: Pause the subscription to skip the next month's auto-debit
subscription_id = "sub_R5B13JlUeW9sgB"
client.subscription.pause(subscription_id)
print("Subscription Paused for Month 2")

# Step 3: Simulate waiting for payment confirmation (in production, use webhooks)
# For demo purposes, assume payment is completed after a delay
time.sleep(5)  # Replace with webhook or API polling in production

# Verify payment (optional: check payment status via payment_link ID)
# payment_link_id = payment_link['id']
# payment_link_details = client.payment_link.fetch(payment_link_id)
# if payment_link_details['status'] == 'paid':
#     print("Month 2 EMI Payment Confirmed")
#     # Update your system's paid_count (Razorpay doesn't allow updating subscription's paid_count directly)
#     # Example: Log in your database (pseudo-code)
#     # your_database.update_paid_count(subscription_id, current_paid_count + 1)
#     print("Custom Paid Count Updated (e.g., in your database): Month 2 marked as paid")
# else:
#     print("Payment not yet completed. Check again or notify customer.")

# Step 4: Resume the subscription for the next billing cycle (Month 3)
# Calculate the resume date (e.g., first day of the next month after Month 2)
current_date = datetime.now(pytz.UTC)
resume_date = (current_date + relativedelta(months=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
resume_timestamp = int(resume_date.timestamp())

resume_data = {
    "resume_at": resume_timestamp  # Unix timestamp for start of Month 3
}
client.subscription.resume(subscription_id, resume_data)
breakpoint()
print(f"Subscription Resumed from {resume_date.strftime('%Y-%m-%d')} for Month 3 onward")

# Step 5: Fetch subscription details to confirm status
subscription = client.subscription.fetch(subscription_id)
print("Subscription Status:", subscription['status'])
print("Paid Count (Razorpay):", subscription['paid_count'])  # Note: This won't reflect manual payment
print("Remaining Count:", subscription['remaining_count'])
print("Next Billing Date (Unix Timestamp):", subscription['current_end'])