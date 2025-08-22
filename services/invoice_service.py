
from datetime import datetime
from typing import Dict, Any, Optional
from starlette import status

from app_logging import app_logger
from common.cache_string import gettext
from db_domains.db_interface import DBInterface
from schemas.invoice_schemas import InvoiceCreateSchema, InvoiceUpdateSchema, InvoiceResponseSchema
from models.razorpay import Invoice


class InvoiceService:
    def __init__(self, db_interface: DBInterface = None):
        self.db_interface = db_interface or DBInterface(Invoice)

    def create_invoice(self, form_data: InvoiceCreateSchema) -> Dict[str, Any]:
        try:
            app_logger.info("Creating new invoice")

            invoice_instance = self.db_interface.create(form_data)
            invoice_response = InvoiceResponseSchema.model_validate(
                invoice_instance).model_dump()

            return {
                "success": True,
                "message": gettext("created_successfully").format("Invoice"),
                "status_code": status.HTTP_201_CREATED,
                "data": invoice_response
            }

        except Exception as e:
            app_logger.error(
                f"Error creating invoice: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {"error": str(e)}
            }

    def get_all_invoices(
        self,
        search: Optional[str] = None,
        order_by: Optional[str] = None,
        order_direction: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        subscription_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        try:
            app_logger.info("Fetching all invoices")

            filter_def = {
                "AND": [
                    {"field": "is_deleted", "op": "==", "value": False}
                ]
            }
            total_invoices = self.db_interface.count_all_by_fields(
                filters=[Invoice.is_deleted == False]
            )

            if search and search.strip() != "":
                like_value = f"%{search.lower()}%"
                filter_def["AND"].append(
                    {
                        "OR": [
                            {"field": "razorpay_invoice_id",
                                "op": "ilike", "value": like_value},
                            {"field": "entity", "op": "ilike", "value": like_value},
                            {"field": "notes", "op": "ilike", "value": like_value},
                        ]
                    }
                )

            if subscription_id is not None:
                filter_def["AND"].append(
                    {"field": "subscription_id", "op": "==",
                        "value": subscription_id}
                )

            filter_expr = self.db_interface.build_filter_expression(filter_def)

            order_column = getattr(
                Invoice, order_by, Invoice.created_at
            ) if order_by else Invoice.created_at
            order_direction = order_direction.lower() if order_direction else "desc"

            if offset != 0:
                final_offset = (offset - 1) * limit
            else:
                final_offset = offset

            invoices, total_counts = self.db_interface.read_all_by_filters(
                filter_expr=filter_expr,
                order_by=order_column,
                order_direction=order_direction,
                limit=limit,
                offset=final_offset
            )

            invoice_list = [
                InvoiceResponseSchema.model_validate(invoice).model_dump()
                for invoice in invoices
            ]

            return invoice_list

        except Exception as e:
            app_logger.error(
                f"Error retrieving invoices: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": str(e),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": []
            }

    def update_invoice(
        self, invoice_id: int, form_data: InvoiceUpdateSchema
    ) -> Dict[str, Any]:
        try:
            app_logger.info(f"Updating invoice with ID: {invoice_id}")
            invoice_updated_instance = self.db_interface.update(
                _id=invoice_id, data=form_data)
            if not invoice_updated_instance:
                app_logger.error(f"Invoice with ID {invoice_id} not found")
                return {
                    "success": False,
                    "message": gettext("not_found").format("Invoice"),
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "data": {}
                }

            invoice_updated_data = InvoiceResponseSchema.model_validate(
                invoice_updated_instance).model_dump()

            return {
                "success": True,
                "message": gettext("updated_successfully").format("Invoice"),
                "status_code": status.HTTP_200_OK,
                "data": invoice_updated_data
            }

        except Exception as e:
            app_logger.error(
                f"Error updating invoice with ID {invoice_id}: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {"error": str(e)}
            }

    def delete_invoice(self, logged_in_user_id: str, invoice_id: int) -> Dict[str, Any]:
        try:
            app_logger.info(f"Deleting invoice with ID: {invoice_id}")

            invoice_filter = [Invoice.id == invoice_id,
                              Invoice.is_deleted == False]
            if not self.db_interface.soft_delete(invoice_filter, logged_in_user_id):
                app_logger.error(f"Invoice with ID {invoice_id} not found")
                return {
                    "success": False,
                    "message": gettext("not_found").format("Invoice"),
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "data": {}
                }

            return {
                "success": True,
                "message": gettext("deleted_successfully").format("Invoice"),
                "status_code": status.HTTP_200_OK,
                "data": {}
            }

        except Exception as e:
            app_logger.error(
                f"Error deleting invoice with ID {invoice_id}: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {"error": str(e)}
            }
