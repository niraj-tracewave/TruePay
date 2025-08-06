from config import app_config
from typing import Any

from starlette import status

from app_logging import app_logger
from db_domains import Base
from db_domains.db_interface import DBInterface
from models.razorpay import Plan
from schemas.razorpay_schema import CreatePlanSchema
from services.razorpay_service import RazorpayService
from fastapi import HTTPException


class PlanService:
    def __init__(self, db_model: type[Base]) -> None:
        self.db_class: type[Base] = db_model
        self.db_interface = DBInterface(self.db_class)

    def add_plan(self, applicant_id: int, user_id: int, form_data: CreatePlanSchema) -> Any:
        try:
            self.db_interface = DBInterface(Plan)

            app_logger.info(
                f"[Creating Loan Plan]"
            )
            existing_entry = self.db_interface.read_single_by_fields(
                fields=[
                    Plan.applicant_id == applicant_id,
                    Plan.is_deleted == False,
                ]
            )

            if existing_entry:
               raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"EMI Plan already exists for loan detail {applicant_id}."
                )
            service = RazorpayService(
                app_config.RAZORPAY_KEY_ID, app_config.RAZORPAY_SECRET)
            plan_data = form_data
            plan = service.create_plan(plan_data)
            data = {
                "applicant_id": applicant_id,
                "razorpay_plan_id": plan.get("id"),
                "entity": plan.get("entity"),
                "period": plan.get("period"),
                "interval": plan.get("interval"),
                "item_id": plan.get("item").get("id"),
                "item_name":  plan.get("item").get("name"),
                "item_amount":    plan.get("item").get("amount"),
                "item_currency":  plan.get("item").get("currency"),
                "item_description": plan.get("item").get("description"),
                "plan_data": plan
            }
            data["created_by"] = user_id
            new_entry = self.db_interface.create(data=data)
            return new_entry

        except Exception as e:
            raise e
            
