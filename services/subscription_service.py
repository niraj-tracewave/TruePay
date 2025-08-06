from typing import Any
from fastapi import HTTPException
from starlette import status

from config import app_config
from app_logging import app_logger
from db_domains import Base
from db_domains.db_interface import DBInterface
from models.razorpay import Subscription
from schemas.razorpay_schema import CreateSubscriptionSchema
from services.razorpay_service import RazorpayService


class SubscriptionService:
    def __init__(self, db_model: type[Base]) -> None:
        self.db_class: type[Base] = db_model
        self.db_interface = DBInterface(self.db_class)

    def add_subscription(self, plan_id: int, user_id: int, form_data: CreateSubscriptionSchema) -> Any:
        try:
            self.db_interface = DBInterface(Subscription)

            app_logger.info(
                f"[Creating Plan's Subscription ]"
            )
            existing_entry = self.db_interface.read_single_by_fields(
                fields=[
                    Subscription.plan_id == plan_id,
                    Subscription.is_deleted == False,
                ]
            )

            if existing_entry:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"EMI Subscription Is already exists for plan detail {plan_id}."
                )
            service = RazorpayService(
                app_config.RAZORPAY_KEY_ID, app_config.RAZORPAY_SECRET)
            new_sub = service.create_subscription(form_data)
            print("new sub", new_sub)
            data = {
                "status": "created",
                "razorpay_subscription_id": new_sub.get("id"),
                "entity": new_sub.get("entity"),
                "plan_id": plan_id,
                "quantity": new_sub.get("quantity"),
                "total_count": new_sub.get("total_count"),
                "paid_count": new_sub.get("paid_count"),
                "remaining_count": new_sub.get("remaining_count"),
                "start_at": new_sub.get("start_at"),
                "end_at": new_sub.get("end_at"),
                "charge_at": new_sub.get("charge_at"),
                "expire_by": new_sub.get("expire_by"),
                "customer_notify": new_sub.get("customer_notify"),
                "short_url": new_sub.get("short_url"),
                "has_scheduled_changes": new_sub.get("has_scheduled_changes"),
                "change_scheduled_at": new_sub.get("change_scheduled_at"),
                # upcoming_invoice_id = Column(String, nullable=True)
                # addons = Column(JSON, nullable=True)  # JSON string
                "auth_attempts": new_sub.get("auth_attempts"),
                "subscription_data":  new_sub

            }
            data["created_by"] = user_id
            new_entry = self.db_interface.create(data=data)
            return new_entry

        except Exception as e:
            raise e
