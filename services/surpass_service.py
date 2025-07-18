from datetime import date, timedelta
from typing import Any, Dict

import httpx
from starlette import status

from config import app_config
from db_domains.db_interface import DBInterface
from models.surpass import UserCibilReport
from schemas.surpass_schemas import GetCibilReportData


class SurpassService:
    def __init__(self):
        self.base_url = app_config.SURPASS_API_BASE_URL
        self.bearer_token = app_config.SURPASS_TOKEN
        self.api_prefix = "api/v1"
        self.headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json"
        }

    async def make_request(self, endpoint: str, method: str = "POST", data=None, params=None):
        url = f"{self.base_url}/{self.api_prefix}/{endpoint}"
        response = None

        try:
            async with httpx.AsyncClient() as client:
                if method.upper() == "GET":
                    response = await client.get(url, params=params, headers=self.headers)
                elif method.upper() == "POST":
                    response = await client.post(url, json=data, headers=self.headers)
                else:
                    return None, status.HTTP_400_BAD_REQUEST, "Unsupported HTTP method"
                response_data = response.json()

                if response.status_code >= 400:
                    error_message = response_data.get("message", "API returned an error")
                    return response_data, response.status_code, error_message
                return response.json(), response.status_code, None

        except httpx.RequestError as e:
            return None, status.HTTP_500_INTERNAL_SERVER_ERROR, f"Request error: {str(e)}"
        except httpx.HTTPStatusError as e:
            return None, e.response.status_code, f"HTTP error: {str(e)}"
        except Exception as e:
            return None, status.HTTP_500_INTERNAL_SERVER_ERROR, f"Unexpected error: {str(e)}"

    async def fetch_cibil_score(self, user_id: str, payload_data: GetCibilReportData) -> Dict[str, Any]:
        data_dict = payload_data.model_dump(mode="json", by_alias=True)
        user_cibil_report = DBInterface(UserCibilReport)
        current_date = date.today()

        existing_report = user_cibil_report.read_single_by_fields(
            fields=[
                UserCibilReport.pan_number == data_dict.get("pan"),
                UserCibilReport.mobile == data_dict.get("mobile")
            ]
        )

        async def get_and_save_cibil_report(existing_id: str = None):
            """Fetch from Surpass and create or update report."""
            response_data, status_code, error = await self.make_request(
                endpoint="credit-report-cibil/fetch-report", method="POST", data=data_dict
            )
            if error:
                return None, status_code, error

            data = response_data.get("data", {})
            report_data = {
                "user_id": user_id,
                "client_id": data.get("client_id"),
                "pan_number": data.get("pan"),
                "mobile": data.get("mobile"),
                "credit_score": data.get("credit_score"),
                "credit_report": data.get("credit_report", {}),
                "credit_report_link": data.get("credit_report_link"),
                "report_refresh_date": current_date,
                "next_eligible_date": current_date + timedelta(days=30)
            }

            if existing_id:
                user_cibil_report.update(object_id=existing_id, data=report_data)
            else:
                user_cibil_report.create(data=report_data)

            return data.get("credit_score"), status_code, None

        # Logic conditions
        if not existing_report:
            print("Not Exitign")
            credit_score, status_code, error = await get_and_save_cibil_report()
        elif existing_report.next_eligible_date and current_date > existing_report.next_eligible_date:
            print("Not perfect date")
            credit_score, status_code, error = await get_and_save_cibil_report(existing_report.id)
        else:
            credit_score = existing_report.credit_score
            status_code = status.HTTP_200_OK
            error = None

        if error:
            return {
                "success": False,
                "message": error,
                "status_code": status_code,
                "data": {}
            }

        return {
            "success": True,
            "message": "CIBIL score retrieved successfully",
            "status_code": status_code,
            "data": {
                "credit_score": credit_score
            }
        }
