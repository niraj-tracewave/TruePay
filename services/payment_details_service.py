from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from starlette import status

from app_logging import app_logger
from common.cache_string import gettext
from db_domains.db_interface import DBInterface
from models.razorpay import PaymentDetails
from schemas.payment_details_schemas import PaymentDetailsCreateSchema, PaymentDetailsResponseSchema, PaymentDetailsUpdateSchema


class PaymentDetailsService:
    def __init__(self, db_interface: DBInterface = None):
        self.db_interface = db_interface or DBInterface(PaymentDetails)

    def create_payment_details(
            self, form_data: PaymentDetailsCreateSchema
    ) -> Dict[str, Any]:
        try:
            app_logger.info("Creating new payment details entry")

            payment_data = form_data

            payment_instance = self.db_interface.create(payment_data)
            payment_response = PaymentDetailsResponseSchema.model_validate(
                payment_instance).model_dump()

            return {
                "success": True,
                "message": gettext("created_successfully").format("Payment Details Entry"),
                "status_code": status.HTTP_201_CREATED,
                "data": payment_response
            }

        except Exception as e:
            breakpoint()
            app_logger.error(
                f"Error creating payment details entry: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {
                    "error": str(e)
                }
            }

    def get_all_payment_details(
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
            app_logger.info("Fetching all payment details entries")

            filter_def = {
                "AND": [
                    {"field": "is_deleted", "op": "==", "value": False}
                ]
            }
            total_payments = self.db_interface.count_all_by_fields(
                filters=[PaymentDetails.is_deleted == False]
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
                            {"field": "payment_id", "op": "ilike",
                                "value": like_value},
                            {"field": "status", "op": "ilike", "value": like_value},
                            {"field": "payment_method",
                                "op": "ilike", "value": like_value}
                        ]
                    }
                )

            filter_expr = self.db_interface.build_filter_expression(filter_def)

            order_column = getattr(
                PaymentDetails, order_by, PaymentDetails.created_at
            ) if order_by else PaymentDetails.created_at
            order_direction = order_direction.lower() if order_direction else "desc"

            if offset != 0:
                final_offset = (offset - 1) * limit
            else:
                final_offset = offset

            payments = self.db_interface.read_all_by_filters(
                filter_expr=filter_expr,
                order_by=order_column,
                order_direction=order_direction,
                limit=limit,
                offset=final_offset
            )

            payment_list = [
                PaymentDetailsResponseSchema.model_validate(
                    payment).model_dump()
                for payment in payments
            ]

            return {
                "success": True,
                "message": gettext("retrieved_successfully").format("Payment Details Entries") if payment_list else gettext(
                    "no_module_found"
                ).format("Payment Details Entry"),
                "status_code": status.HTTP_200_OK if payment_list else status.HTTP_404_NOT_FOUND,
                "data": {
                    "payment_details_entries": payment_list,
                    "total_db_payments": total_payments,
                    "total_count": total_payments
                }
            }

        except Exception as e:
            app_logger.error(
                f"Error retrieving payment details entries: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": str(e),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": []
            }

    def update_payment_details(
            self, logged_in_user_id: str, payment_id: str, form_data: PaymentDetailsUpdateSchema
    ) -> Dict[str, Any]:
        try:
            app_logger.info(
                f"Updating payment details entry with ID: {payment_id}")

            payment_data = form_data.model_dump(exclude_unset=True)
            payment_data = {
                k: v for k, v in payment_data.items()
                if k in ["amount", "currency", "status", "payment_method"] and v is not None
            }
            payment_data["modified_by"] = logged_in_user_id

            payment_updated_instance = self.db_interface.update(
                _id=payment_id, data=payment_data)
            if not payment_updated_instance:
                app_logger.error(
                    f"Payment details entry with ID {payment_id} not found")
                return {
                    "success": False,
                    "message": gettext("not_found").format("Payment Details Entry"),
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "data": {}
                }

            payment_updated_data = PaymentDetailsResponseSchema.model_validate(
                payment_updated_instance).model_dump()
            app_logger.info(
                f"Payment details entry updated successfully: {payment_updated_data['id']}")

            return {
                "success": True,
                "message": gettext("updated_successfully").format("Payment Details Entry"),
                "status_code": status.HTTP_200_OK,
                "data": payment_updated_data
            }

        except Exception as e:
            app_logger.error(
                f"Error updating payment details entry with ID {payment_id}: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }

    def delete_payment_details(self, logged_in_user_id: str, payment_id: str) -> Dict[str, Any]:
        try:
            app_logger.info(
                f"Deleting payment details entry with ID: {payment_id}")

            payment_filter = [PaymentDetails.id == payment_id,
                              PaymentDetails.is_deleted == False]
            if not self.db_interface.soft_delete(payment_filter, logged_in_user_id):
                app_logger.error(
                    f"Payment details entry with ID {payment_id} not found")
                return {
                    "success": False,
                    "message": gettext("not_found").format("Payment Details Entry"),
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "data": {}
                }

            return {
                "success": True,
                "message": gettext("deleted_successfully").format("Payment Details Entry"),
                "status_code": status.HTTP_200_OK,
                "data": {}
            }

        except Exception as e:
            app_logger.error(
                f"Error deleting payment details entry with ID {payment_id}: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }
