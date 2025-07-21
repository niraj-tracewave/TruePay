import re
from datetime import date, timedelta, datetime
from typing import Any, Dict

import httpx
from starlette import status

from app_logging import app_logger
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

    async def fetch_cibil_report(self, user_id: int, cibil_score_id: int):
        try:
            def get_payment_rating(value):
                return "Excellent" if value == 100 else "Good" if value >= 95 else "Fair"

            def get_utilization_rating(value):
                if value <= 10:
                    return "Excellent"
                elif value <= 30:
                    return "Good"
                elif value <= 50:
                    return "Fair"
                else:
                    return "Poor"

            def get_credit_history_rating(years, months):
                total_months = years * 12 + months
                if total_months >= 60:
                    return "Excellent"
                elif total_months >= 24:
                    return "Good"
                else:
                    return "Average"

            def get_loan_accounts_rating(count):
                if count <= 2:
                    return "Excellent"
                elif count <= 5:
                    return "Good"
                elif count <= 7:
                    return "Fair"
                else:
                    return "Poor"

            app_logger.info(f"Fetching CIBIL report for user_id: {user_id}, cibil_score_id: {cibil_score_id}")
            user_cibil_report = DBInterface(UserCibilReport)
            cibil_report = user_cibil_report.read_single_by_fields(
                [
                    UserCibilReport.id == cibil_score_id
                ]
            )

            accounts = cibil_report.credit_report[0].get("accounts", [])

            # 1. Credit Utilization
            total_used, total_limit = 0, 0
            for acc in accounts:
                account_type = acc.get("accountType", "").lower()
                account_status = acc.get("accountStatus", "").lower()

                if "credit card" in account_type and "closed" not in account_status:
                    try:
                        high = int(acc.get("highCreditAmount", 0))
                        balance = int(acc.get("currentBalance", 0))
                        if high > 0 and balance >= 0:
                            total_used += balance
                            total_limit += high
                    except (ValueError, TypeError) as e:
                        app_logger.warning(f"Skipping credit card due to error: {e}")
                        continue

            avg_utilization = round((total_used / total_limit) * 100, 2) if total_limit > 0 else 0
            app_logger.info(f"Total Used: {total_used} | Total Limit: {total_limit} | Utilization: {avg_utilization}%")

            # 2. Payment History
            on_time, total_blocks = 0, 0
            for acc in accounts:
                payment_history = acc.get("paymentHistory", "")
                if isinstance(payment_history, str):
                    history_blocks = re.findall(r"...", payment_history)
                    valid_blocks = [b for b in history_blocks if re.fullmatch(r"\d{3}", b)]
                    total_blocks += len(valid_blocks)
                    on_time += sum(1 for b in valid_blocks if b == "000")

            payment_history_percent = round((on_time / total_blocks) * 100, 2) if total_blocks > 0 else 0
            app_logger.info(f"On Time Payments: {on_time} / {total_blocks} = {payment_history_percent}%")

            # 3. Credit History
            opened_dates = []
            for acc in accounts:
                date_str = acc.get("dateOpened")
                try:
                    opened_date = datetime.strptime(date_str, "%Y-%m-%d")
                    opened_dates.append(opened_date)
                except (ValueError, TypeError) as e:
                    app_logger.warning(f"Skipping account due to invalid date: {date_str} | Error: {e}")
                    continue

            years, months = 0, 0
            if opened_dates:
                oldest_date = min(opened_dates)
                today = datetime.today()
                years = today.year - oldest_date.year
                months = today.month - oldest_date.month
                if months < 0:
                    years -= 1
                    months += 12

            app_logger.info(f"Credit History: {years} years, {months} months")

            # 4. Loan Accounts
            loan_accounts = len(accounts)
            app_logger.info(f"Total Loan Accounts: {loan_accounts}")

            report_summary = {
                "payment_history": {
                    "value": f"{payment_history_percent}%",
                    "message": get_payment_rating(payment_history_percent)
                },
                "credit_utilization": {
                    "value": f"{avg_utilization}%",
                    "message": get_utilization_rating(avg_utilization)
                },
                "credit_history": {
                    "value": f"{years} Year {months} Months",
                    "message": f"{years} Year {months} Months Credit History is {get_credit_history_rating(years, months)}"
                },
                "loan_accounts": {
                    "value": loan_accounts,
                    "message": f"{loan_accounts} Accounts Level is {get_loan_accounts_rating(loan_accounts)}"
                }
            }

            return {
                "success": True,
                "message": "CIBIL report retrieved successfully",
                "status_code": status.HTTP_200_OK,
                "data": {"report_details": report_summary}
            }

        except Exception as e:
            app_logger.error(f"Error fetching CIBIL report: {str(e)}")
            return {
                "success": False,
                "message": "Error fetching CIBIL report",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }

