from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from starlette import status

from app_logging import app_logger
from common.cache_string import gettext
from db_domains.db_interface import DBInterface
from models.razorpay import PrePayment
from schemas.prepayment_schemas import PrePaymentCreateSchema, PrePaymentResponseSchema, PrePaymentUpdateSchema


class PrePaymentService:
    def __init__(self, db_interface: DBInterface = None):
        self.db_interface = db_interface or DBInterface(PrePayment)

    def create_pre_payment(
            self, form_data: PrePaymentCreateSchema
    ) -> Dict[str, Any]:
        try:
            app_logger.info("Creating new pre_payment entry")

            # pre_payment_data = form_data.model_dump()

            pre_payment_instance = self.db_interface.create(form_data)
            # UserResponseSchema.model_validate(user_details)
            pre_payment_response = PrePaymentResponseSchema.model_validate(
                pre_payment_instance)

            return {
                "success": True,
                "message": gettext("created_successfully").format("Foreclosure Entry"),
                "status_code": status.HTTP_201_CREATED,
                "data": pre_payment_response
            }

        except Exception as e:
            app_logger.error(
                f"Error creating pre_payment entry: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {
                    "error": str(e)
                }
            }

    def get_all_pre_payments(
            self,
            search: Optional[str] = None,
            order_by: Optional[str] = None,
            order_direction: Optional[str] = None,
            limit: int = 10,
            offset: int = 0,
            start_date: Optional[str] = None,
            end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            app_logger.info("Fetching all pre_payment entries")

            filter_def = {
                "AND": [
                    {"field": "is_deleted", "op": "==", "value": False}
                ]
            }
            total_pre_payments = self.db_interface.count_all_by_fields(
                filters=[PrePayment.is_deleted == False]
            )

            date_format = "%Y-%m-%d"
            if start_date and end_date:
                try:
                    start = datetime.strptime(start_date, date_format)
                    end = datetime.strptime(
                        end_date, date_format) + timedelta(days=1) - timedelta(seconds=1)

                    filter_def["AND"].append(
                        {"field": "created_at", "op": ">=", "value": start})
                    filter_def["AND"].append(
                        {"field": "created_at", "op": "<=", "value": end})

                except ValueError:
                    raise ValueError(
                        "Invalid date format. Use YYYY-MM-DD for both start_date and end_date.")

            if search and search.strip() != "":
                like_value = f"%{search.lower()}%"
                filter_def["AND"].append(
                    {
                        "OR": [
                            {"field": "reason", "op": "ilike", "value": like_value},
                            {"field": "status", "op": "ilike", "value": like_value}
                        ]
                    }
                )

            filter_expr = self.db_interface.build_filter_expression(filter_def)

            order_column = getattr(
                PrePayment, order_by, PrePayment.created_at
            ) if order_by else PrePayment.created_at
            order_direction = order_direction.lower() if order_direction else "desc"

            if offset != 0:
                final_offset = (offset - 1) * limit
            else:
                final_offset = offset

            pre_payments, total_counts = self.db_interface.read_all_by_filters(
                filter_expr=filter_expr,
                order_by=order_column,
                order_direction=order_direction,
                limit=limit,
                offset=final_offset
            )

            pre_payment_list = [
                PrePaymentResponseSchema.model_validate(
                    pre_payment).model_dump()
                for pre_payment in pre_payments
            ]

            return {
                "success": True,
                "message": gettext("retrieved_successfully").format("Foreclosure Entries") if pre_payment_list else gettext(
                    "no_module_found"
                ).format("Foreclosure Entry"),
                "status_code": status.HTTP_200_OK if pre_payment_list else status.HTTP_404_NOT_FOUND,
                "data": {
                    "pre_payment_entries": pre_payment_list,
                    "total_db_pre_payments": total_pre_payments,
                    "total_count": total_counts
                }
            }

        except Exception as e:
            app_logger.error(
                f"Error retrieving pre_payment entries: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": str(e),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": []
            }

    def update_pre_payment(
            self, logged_in_user_id: str, pre_payment_id: str, form_data: PrePaymentUpdateSchema
    ) -> Dict[str, Any]:
        try:
            app_logger.info(
                f"Updating pre_payment entry with ID: {pre_payment_id}")

            pre_payment_data = form_data.model_dump(exclude_unset=True)
            pre_payment_data = {
                k: v for k, v in pre_payment_data.items()
                if k in ["amount", "reason", "status"] and v is not None
            }
            pre_payment_data["modified_by"] = logged_in_user_id

            pre_payment_updated_instance = self.db_interface.update(
                _id=pre_payment_id, data=pre_payment_data)
            if not pre_payment_updated_instance:
                app_logger.error(
                    f"Foreclosure entry with ID {pre_payment_id} not found")
                return {
                    "success": False,
                    "message": gettext("not_found").format("Foreclosure Entry"),
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "data": {}
                }

            pre_payment_updated_data = PrePaymentResponseSchema.model_validate(
                pre_payment_updated_instance).model_dump()
            app_logger.info(
                f"Foreclosure entry updated successfully: {pre_payment_updated_data['id']}")

            return {
                "success": True,
                "message": gettext("updated_successfully").format("Foreclosure Entry"),
                "status_code": status.HTTP_200_OK,
                "data": pre_payment_updated_data
            }

        except Exception as e:
            app_logger.error(
                f"Error updating pre_payment entry with ID {pre_payment_id}: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }

    def delete_pre_payment(self, logged_in_user_id: str, pre_payment_id: str) -> Dict[str, Any]:
        try:
            app_logger.info(
                f"Deleting pre_payment entry with ID: {pre_payment_id}")

            pre_payment_filter = [PrePayment.id == pre_payment_id,
                                  PrePayment.is_deleted == False]
            if not self.db_interface.soft_delete(pre_payment_filter, logged_in_user_id):
                app_logger.error(
                    f"Foreclosure entry with ID {pre_payment_id} not found")
                return {
                    "success": False,
                    "message": gettext("not_found").format("Foreclosure Entry"),
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "data": {}
                }

            return {
                "success": True,
                "message": gettext("deleted_successfully").format("Foreclosure Entry"),
                "status_code": status.HTTP_200_OK,
                "data": {}
            }

        except Exception as e:
            app_logger.error(
                f"Error deleting pre_payment entry with ID {pre_payment_id}: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }
