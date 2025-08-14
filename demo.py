import razorpay
import time  # Optional, if you want to wait or simulate

# Initialize Razorpay client with your API keys
# Replace 'YOUR_KEY_ID' and 'YOUR_KEY_SECRET' with your actual Razorpay API keys
client = razorpay.Client(auth=("rzp_test_ksbxGR8ZgbHtkv", "SIbiNOSS6bJwX9wEIxuLZ93c"))

# Step 1: Create a Razorpay Plan
# This plan is for 3000 INR per month (amount in paise: 3000 * 100 = 300000)
plan_data = {
    "period": "monthly",  # Billing period: monthly
    "interval": 1,        # Interval between charges: 1 month
    "item": {
        "name": "10-Month Subscription Plan",
        "description": "3000 INR per month for 10 months, totaling 30,000 INR",
        "amount": 300000,  # Amount in paise (smallest currency unit)
        "currency": "INR"
    }
}

plan = client.plan.create(data=plan_data)
print("Created Plan ID:", plan['id'])

# Step 2: Create a Subscription based on the Plan
# Total count is 10 for 10 monthly payments
subscription_data = {
    "plan_id": plan['id'],  # Link to the created plan
    "total_count": 10,      # Total number of billing cycles (10 months)
    "quantity": 1,          # Quantity of the plan (default 1)
    "customer_notify": 1,   # Notify customer via email/SMS (1: yes, 0: no)
    # Optional: Add 'start_at': unix_timestamp to start in future
    # Optional: Add 'notify_info': {'notify_email': 'customer@example.com', 'notify_phone': '9999999999'}
}

subscription = client.subscription.create(data=subscription_data)
print("Created Subscription ID:", subscription['id'])

# Step 3: The Payment Link is the short_url from the subscription response
# This link is used by the customer to authenticate and make the first payment manually
payment_link = subscription['short_url']
print("Payment Link for Initial Subscription:", payment_link)

# Explanation:
# - The customer visits the payment_link to provide payment details and complete the first payment (manual for the current month).
# - Upon successful payment/authentication, the subscription status changes to 'active', and paid_count is updated to 1 automatically by Razorpay.
# - Auto-debit stops for the current month (since it's handled manually via the link), and continues automatically from the next month onwards for the remaining 9 cycles.
# - Total: 10 payments of 3000 INR each = 30,000 INR.

# Step 4: To check/update on paid_count (it's updated automatically, but you can fetch to view)
# Note: Run this part after the customer has completed the payment via the link.
# For demonstration, you can uncomment and run separately after payment.

# time.sleep(60)  # Simulate waiting for payment (in real scenario, use webhooks or poll)

fetched_subscription = client.subscription.fetch(subscription['id'])
print("Updated Paid Count:", fetched_subscription['paid_count'])
print("Remaining Count:", fetched_subscription['remaining_count'])

# In a real application, use Razorpay webhooks to listen for 'subscription.charged' or 'subscription.activated' events
# to confirm payment and update your database accordingly. No manual update to paid_count is needed or possible via API.
# Create a payment link for a missed EMI
# payment_link_data = {
#     "amount": 300000,  # Amount in paise (₹3,000)
#     "currency": "INR",
#     "description": "Retry Payment for Monthly EMI",
    
#     "reminder_enable": True,
#     "notes": {
#         "subscription_id": subscription['id'],
#         "emi_month": "Month 2"  # Track which EMI this is for
#     },
#     "callback_url": "https://yourwebsite.com/callback",  # Optional: Redirect after payment
#     "callback_method": "get"
# }

# payment_link = client.payment_link.create(data=payment_link_data)
# print("Retry Payment Link:", payment_link['short_url'])
# # Pause the subscription
# client.subscription.pause( subscription['id'])
# print("Subscription Paused")

# # Resume the subscription to start from the next month
# # Note: Set 'resume_at' to the desired Unix timestamp (e.g., start of next billing cycle)
# resume_data = {
#     "resume_at": "now"  # Or specify a Unix timestamp for the next month
# }
# client.subscription.resume( subscription['id'], resume_data)
# print("Subscription Resumed")