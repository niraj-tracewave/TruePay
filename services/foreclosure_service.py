from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from starlette import status

from app_logging import app_logger
from common.cache_string import gettext
from db_domains.db_interface import DBInterface
from models.razorpay import ForeClosure
from schemas.foreclosure_schemas import ForeClosureCreateSchema, ForeClosureResponseSchema, ForeClosureUpdateSchema


class ForeClosureService:
    def __init__(self, db_interface: DBInterface = None):
        self.db_interface = db_interface or DBInterface(ForeClosure)

    def create_foreclosure(
            self, form_data: ForeClosureCreateSchema
    ) -> Dict[str, Any]:
        try:
            app_logger.info("Creating new foreclosure entry")

            # foreclosure_data = form_data.model_dump()

            foreclosure_instance = self.db_interface.create(form_data)
            # UserResponseSchema.model_validate(user_details)
            foreclosure_response = ForeClosureResponseSchema.model_validate(
                foreclosure_instance)

            return {
                "success": True,
                "message": gettext("created_successfully").format("Foreclosure Entry"),
                "status_code": status.HTTP_201_CREATED,
                "data": foreclosure_response
            }

        except Exception as e:
            app_logger.error(
                f"Error creating foreclosure entry: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {
                    "error": str(e)
                }
            }

    def get_all_foreclosures(
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
            app_logger.info("Fetching all foreclosure entries")

            filter_def = {
                "AND": [
                    {"field": "is_deleted", "op": "==", "value": False}
                ]
            }
            total_foreclosures = self.db_interface.count_all_by_fields(
                filters=[ForeClosure.is_deleted == False]
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
                ForeClosure, order_by, ForeClosure.created_at
            ) if order_by else ForeClosure.created_at
            order_direction = order_direction.lower() if order_direction else "desc"

            if offset != 0:
                final_offset = (offset - 1) * limit
            else:
                final_offset = offset

            foreclosures = self.db_interface.read_all_by_filters(
                filter_expr=filter_expr,
                order_by=order_column,
                order_direction=order_direction,
                limit=limit,
                offset=final_offset
            )

            foreclosure_list = [
                ForeClosureResponseSchema.model_validate(
                    foreclosure).model_dump()
                for foreclosure in foreclosures
            ]

            return {
                "success": True,
                "message": gettext("retrieved_successfully").format("Foreclosure Entries") if foreclosure_list else gettext(
                    "no_module_found"
                ).format("Foreclosure Entry"),
                "status_code": status.HTTP_200_OK if foreclosure_list else status.HTTP_404_NOT_FOUND,
                "data": {
                    "foreclosure_entries": foreclosure_list,
                    "total_db_foreclosures": total_foreclosures,
                    "total_count": total_foreclosures
                }
            }

        except Exception as e:
            app_logger.error(
                f"Error retrieving foreclosure entries: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": str(e),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": []
            }

    def update_foreclosure(
            self, logged_in_user_id: str, foreclosure_id: str, form_data: ForeClosureUpdateSchema
    ) -> Dict[str, Any]:
        try:
            app_logger.info(
                f"Updating foreclosure entry with ID: {foreclosure_id}")

            foreclosure_data = form_data.model_dump(exclude_unset=True)
            foreclosure_data = {
                k: v for k, v in foreclosure_data.items()
                if k in ["amount", "reason", "status"] and v is not None
            }
            foreclosure_data["modified_by"] = logged_in_user_id

            foreclosure_updated_instance = self.db_interface.update(
                _id=foreclosure_id, data=foreclosure_data)
            if not foreclosure_updated_instance:
                app_logger.error(
                    f"Foreclosure entry with ID {foreclosure_id} not found")
                return {
                    "success": False,
                    "message": gettext("not_found").format("Foreclosure Entry"),
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "data": {}
                }

            foreclosure_updated_data = ForeClosureResponseSchema.model_validate(
                foreclosure_updated_instance).model_dump()
            app_logger.info(
                f"Foreclosure entry updated successfully: {foreclosure_updated_data['id']}")

            return {
                "success": True,
                "message": gettext("updated_successfully").format("Foreclosure Entry"),
                "status_code": status.HTTP_200_OK,
                "data": foreclosure_updated_data
            }

        except Exception as e:
            app_logger.error(
                f"Error updating foreclosure entry with ID {foreclosure_id}: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }

    def delete_foreclosure(self, logged_in_user_id: str, foreclosure_id: str) -> Dict[str, Any]:
        try:
            app_logger.info(
                f"Deleting foreclosure entry with ID: {foreclosure_id}")

            foreclosure_filter = [ForeClosure.id == foreclosure_id,
                                  ForeClosure.is_deleted == False]
            if not self.db_interface.soft_delete(foreclosure_filter, logged_in_user_id):
                app_logger.error(
                    f"Foreclosure entry with ID {foreclosure_id} not found")
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
                f"Error deleting foreclosure entry with ID {foreclosure_id}: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }
