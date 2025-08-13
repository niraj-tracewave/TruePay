
import traceback
from db_domains.db import DBSession
from models.razorpay import Subscription, PaymentDetails

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
        """
        Update payment link status by ID.
        
        Args:
            payment_link_id (str): Razorpay payment link ID.
            status (str): New status to set.
        
        Returns:
            bool: True if updated, False otherwise.
        """
        try:
            if not payment_link_id:
                print("⚠ No payment link ID provided.")
                return False

            with DBSession() as session:
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
    
                payment_data.status = status
                session.commit()
                print(f" Payment Link {payment_link_id} updated to '{status}'")
                return True

        except Exception as e:
            print(f"Error updating payment link {payment_link_id}: {e}")
            traceback.print_exc()
            return False