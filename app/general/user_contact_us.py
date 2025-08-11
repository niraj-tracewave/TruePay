from fastapi import APIRouter, Request
from starlette import status

from common.response import ApiResponse
from schemas.contact_us_schema import ContactUsCreateSchema, ContactUsUpdateSchema
from services.contact_us_service import ContactUsService

router = APIRouter(prefix="/contact-us", tags=["Contact Us API's"])
contact_service = ContactUsService()


@router.post("/create-contact-message", summary="Create a new contact entry")
async def create_contact(request: Request, form_data: ContactUsCreateSchema):
    response = contact_service.create_contact(form_data=form_data)
    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_201_CREATED),
        data=response.get("data", {})
    )


@router.get("/get-all-contact-messages", summary="Get all contact entries")
async def get_all_contacts(
    search: str | None = None,
    order_by: str | None = None,
    order_direction: str | None = None,
    limit: int = 10,
    offset: int = 0,
    start_date: str | None = None,
    end_date: str | None = None
):
    response = contact_service.get_all_contacts(
        search=search,
        order_by=order_by,
        order_direction=order_direction,
        limit=limit,
        offset=offset,
        start_date=start_date,
        end_date=end_date
    )
    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data", [])
    )


@router.put("/update-contact-message/{contact_id}", summary="Update a contact entry")
async def update_contact(contact_id: str, form_data: ContactUsUpdateSchema, logged_in_user_id: str):
    response = contact_service.update_contact(
        logged_in_user_id=logged_in_user_id,
        contact_id=contact_id,
        form_data=form_data
    )
    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data", {})
    )


@router.delete("/delete-contact-message/{contact_id}", summary="Delete a contact entry")
async def delete_contact(contact_id: str, logged_in_user_id: str):
    response = contact_service.delete_contact(
        logged_in_user_id=logged_in_user_id, contact_id=contact_id)
    return ApiResponse.create_response(
        success=response.get("success"),
        message=response.get("message"),
        status_code=response.get("status_code", status.HTTP_200_OK),
        data=response.get("data", {})
    )
