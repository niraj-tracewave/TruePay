from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from starlette import status

from app_logging import app_logger
from common.cache_string import gettext
from db_domains.db_interface import DBInterface
from models.contact_us import ContactUs
from schemas.contact_us_schema import ContactUsCreateSchema, ContactUsResponseSchema, ContactUsUpdateSchema


class ContactUsService:
    def __init__(self, db_interface: DBInterface = None):
        self.db_interface = db_interface or DBInterface(ContactUs)

    def create_contact(
            self, form_data: ContactUsCreateSchema
    ) -> Dict[str, Any]:
        try:
            app_logger.info("Creating new contact entry")

            contact_data = form_data.model_dump()

            contact_instance = self.db_interface.create(contact_data)
            contact_response = ContactUsResponseSchema.model_validate(
                contact_instance).model_dump()

            # app_logger.info(f"Contact entry created successfully: {contact_response['id']}")

            return {
                "success": True,
                "message": gettext("created_successfully").format("Contact Entry"),
                "status_code": status.HTTP_201_CREATED,
                "data": contact_response
            }

        except Exception as e:
            app_logger.error(
                f"Error creating contact entry: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {
                    "error": str(e)
                }
            }

    def get_all_contacts(
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
            app_logger.info("Fetching all contact entries")

            filter_def = {
                "AND": [
                    {"field": "is_deleted", "op": "==", "value": False}
                ]
            }
            total_contacts = self.db_interface.count_all_by_fields(
                filters=[ContactUs.is_deleted == False]
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
                            {"field": "first_name", "op": "ilike",
                                "value": like_value},
                            {"field": "last_name", "op": "ilike",
                                "value": like_value},
                            {"field": "email", "op": "ilike", "value": like_value},
                            {"field": "service", "op": "ilike", "value": like_value}
                        ]
                    }
                )

            filter_expr = self.db_interface.build_filter_expression(filter_def)

            order_column = getattr(
                ContactUs, order_by, ContactUs.created_at
            ) if order_by else ContactUs.created_at
            order_direction = order_direction.lower() if order_direction else "desc"

            if offset != 0:
                final_offset = (offset - 1) * limit
            else:
                final_offset = offset

            contacts = self.db_interface.read_all_by_filters(
                filter_expr=filter_expr,
                order_by=order_column,
                order_direction=order_direction,
                limit=limit,
                offset=final_offset
            )

            contact_list = [
                ContactUsResponseSchema.model_validate(contact).model_dump()
                for contact in contacts
            ]

            return {
                "success": True,
                "message": gettext("retrieved_successfully").format("Contact Entries") if contact_list else gettext(
                    "no_module_found"
                ).format("Contact Entry"),
                "status_code": status.HTTP_200_OK if contact_list else status.HTTP_404_NOT_FOUND,
                "data": {
                    "contact_entries": contact_list,
                    "total_db_contacts": total_contacts,
                    "total_count": total_contacts
                }
            }

        except Exception as e:
            app_logger.error(
                f"Error retrieving contact entries: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": str(e),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": []
            }

    def update_contact(
            self, logged_in_user_id: str, contact_id: str, form_data: ContactUsUpdateSchema
    ) -> Dict[str, Any]:
        try:
            app_logger.info(f"Updating contact entry with ID: {contact_id}")

            contact_data = form_data.model_dump(exclude_unset=True)
            contact_data = {
                k: v for k, v in contact_data.items()
                if k in ["first_name", "last_name", "email", "service", "message"] and v is not None
            }
            contact_data["modified_by"] = logged_in_user_id

            contact_updated_instance = self.db_interface.update(
                _id=contact_id, data=contact_data)
            if not contact_updated_instance:
                app_logger.error(
                    f"Contact entry with ID {contact_id} not found")
                return {
                    "success": False,
                    "message": gettext("not_found").format("Contact Entry"),
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "data": {}
                }

            contact_updated_data = ContactUsResponseSchema.model_validate(
                contact_updated_instance).model_dump()
            app_logger.info(
                f"Contact entry updated successfully: {contact_updated_data['id']}")

            return {
                "success": True,
                "message": gettext("updated_successfully").format("Contact Entry"),
                "status_code": status.HTTP_200_OK,
                "data": contact_updated_data
            }

        except Exception as e:
            app_logger.error(
                f"Error updating contact entry with ID {contact_id}: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }

    def delete_contact(self, logged_in_user_id: str, contact_id: str) -> Dict[str, Any]:
        try:
            app_logger.info(f"Deleting contact entry with ID: {contact_id}")

            contact_filter = [ContactUs.id == contact_id,
                              ContactUs.is_deleted == False]
            if not self.db_interface.soft_delete(contact_filter, logged_in_user_id):
                app_logger.error(
                    f"Contact entry with ID {contact_id} not found")
                return {
                    "success": False,
                    "message": gettext("not_found").format("Contact Entry"),
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "data": {}
                }

            return {
                "success": True,
                "message": gettext("deleted_successfully").format("Contact Entry"),
                "status_code": status.HTTP_200_OK,
                "data": {}
            }

        except Exception as e:
            app_logger.error(
                f"Error deleting contact entry with ID {contact_id}: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": gettext("something_went_wrong"),
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }
