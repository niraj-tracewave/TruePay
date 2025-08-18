
import traceback
from db_domains.db import DBSession
from models.razorpay import Subscription, PaymentDetails
from services.razorpay_service import RazorpayService
from config import app_config

razorpay_service_obj = RazorpayService(
    app_config.RAZORPAY_KEY_ID, app_config.RAZORPAY_SECRET)


class WebhookDBService:

    @staticmethod
    def update_subscription_status(sub_id: str, status: str):
        """Update subscription status by Razorpay subscription ID."""
        with DBSession() as session:
            sub_data = (
                session.query(Subscription)
                .filter(
                    Subscription.razorpay_subscription_id == sub_id,
                    Subscription.is_deleted == False
                )
                .first()
            )
            if not sub_data:
                print(f"⚠ No subscription found for ID: {sub_id}")
                return False

            sub_data.status = status
            session.commit()
            print(f" Subscription {sub_id} updated to {status}")
            return True

    @staticmethod
    def update_payment_link_status(payment_link_id: str, status: str) -> bool:
        try:
            if not payment_link_id:
                print("⚠ No payment link ID provided.")
                return False

            with DBSession() as session:
                #NOTE: Fetch Applicant details and change the status of the particular loan
                payment_data = (
                    session.query(PaymentDetails)
                    .filter(
                        PaymentDetails.payment_id == payment_link_id,
                        PaymentDetails.is_deleted == False
                    )
                    .first()
                )

                if not payment_data:
                    print(f"⚠ No payment link found for ID: {payment_link_id}")
                    return False

                # Update PaymentDetails status
                payment_data.status = status

                # Fetch related subscription
                subscription = payment_data.foreclosure.subscription if payment_data.foreclosure else None
                if subscription:
                    subscription_id = subscription.id
                    razorpay_subscription_id = subscription.razorpay_subscription_id
                    print(
                        f"Found Subscription ID: {subscription_id}, Razorpay ID: {razorpay_subscription_id}")

                    # Map payment status to subscription status
                    if status == "paid":
                        subscription.status = "cancelled"
                        print(
                            f"Subscription {razorpay_subscription_id} status set to 'cancelled'")
                        # change loan status
                        loan = payment_data.foreclosure.subscription.plan.applicant
                        if loan:
                            loan.status = "COMPLETED"

                else:
                    print(
                        f"No subscription found for payment link {payment_link_id}")

                # Commit all DB changes
                session.commit()

                # Call external API after DB commit
                if status == "paid" and subscription:
                    try:
                        razorpay_service_obj.cancel_subscription(
                            razorpay_subscription_id)
                        print(
                            f"Subscription {razorpay_subscription_id} cancelled in Razorpay.")
                    except Exception as api_exc:
                        print(f"⚠ Razorpay cancellation failed: {api_exc}")

                print(f"Payment Link {payment_link_id} updated to '{status}'")
                return True

        except Exception as e:
            print(f"Error updating payment link {payment_link_id}: {e}")
            traceback.print_exc()
            return False
