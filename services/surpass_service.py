import re
from datetime import date, timedelta, datetime
from typing import Any, Dict

from starlette import status

from app_logging import app_logger
from common.cache_string import gettext
from common.common_services.surpass_service import SurpassRequestService
from db_domains.db_interface import DBInterface
from models.loan import BankAccount
from models.surpass import UserCibilReport
from schemas.surpass_schemas import GetCibilReportData, PanCardDetails, BankDetails, AadharCardDetails


class SurpassService:
    def __init__(self) -> None:
        self.surpass_request_obj = SurpassRequestService()

    async def fetch_cibil_score(self, user_id: int, payload_data: GetCibilReportData) -> Dict[str, Any]:
        data_dict = payload_data.model_dump(mode="json", by_alias=True)
        user_cibil_report = DBInterface(UserCibilReport)
        current_date = date.today()

        existing_report = user_cibil_report.read_single_by_fields(
            fields=[
                UserCibilReport.user_id == user_id,
                UserCibilReport.pan_number == data_dict.get("pan"),
                UserCibilReport.mobile == data_dict.get("mobile")
            ]
        )

        async def get_and_save_cibil_report(existing_id: str = None):
            """Fetch from Surpass and create or update a report."""
            response_data, request_status_code, request_error = await self.surpass_request_obj.make_request(
                endpoint="credit-report-cibil/fetch-report", method="POST", data=data_dict
            )
            if request_error:
                return None, request_status_code, request_error

            data = response_data.get("data", {})
            report_data = {
                "user_id": user_id,
                "client_id": data.get("client_id"),
                "name": data.get("name"),
                "pan_number": data.get("pan"),
                "mobile": data.get("mobile"),
                "credit_score": data.get("credit_score"),
                "credit_report": data.get("credit_report", {}),
                "report_refresh_date": current_date,
                "next_eligible_date": current_date + timedelta(days=30)
            }

            if existing_id:
                user_cibil_report.update(_id=existing_id, data=report_data)
            else:
                create_response = user_cibil_report.create(data=report_data)
                existing_id = create_response.id

            return {
                "id": existing_id,
                "credit_score": data.get("credit_score"),
                "client_id": data.get("client_id"),
                "name": data.get("name"),
                "refresh_date": report_data.get("report_refresh_date"),
                "next_eligible_date": report_data.get("next_eligible_date"),
            }, request_status_code, None

        # Logic conditions
        if not existing_report:
            print("Not Exiting")
            credit_score_data, status_code, error = await get_and_save_cibil_report()
        elif existing_report.next_eligible_date and current_date > existing_report.next_eligible_date:
            print("Not perfect date")
            credit_score_data, status_code, error = await get_and_save_cibil_report(existing_report.id)
        else:
            credit_score_data = {
                "id": existing_report.id,
                "name": existing_report.name,
                "credit_score": existing_report.credit_score,
                "client_id": existing_report.client_id,
                "refresh_date": existing_report.report_refresh_date,
                "next_eligible_date": existing_report.next_eligible_date,
            }

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
            "data": credit_score_data
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
            if not cibil_report:
                return {
                    "success": False,
                    "message": gettext("not_found").format("CIBIL report ID"),
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "data": {}
                }

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
            print(e)
            app_logger.error(f"Error fetching CIBIL report: {str(e)}")
            return {
                "success": False,
                "message": "Error fetching CIBIL report",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }

    async def validate_pan_card(self, user_id: int, pan_detail: PanCardDetails):
        try:
            pan_card_number = pan_detail.pan_card
            app_logger.info(f"User {user_id} submitted PAN: {pan_card_number}")

            pan_regex_check = re.compile(r'^[A-Z]{5}[0-9]{4}[A-Z]$')

            if not pan_regex_check.fullmatch(pan_card_number):
                app_logger.info(f"User {user_id} submitted invalid PAN format: {pan_card_number}")

                return {
                    "success": False,
                    "message": "Invalid PAN card format",
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "data": {}
                }

            app_logger.info(f"User {user_id} submitted valid PAN format. Initiating Surpass API validation.")
            response_data, request_status_code, request_error = await self.surpass_request_obj.make_request(
                endpoint="pan/pan", method="POST", data={"id_number": pan_card_number}
            )

            if request_error:
                app_logger.error(
                    f"Surpass API error for PAN {pan_card_number} by user {user_id}: {request_error}"
                )
                return {
                    "success": False,
                    "message": request_error,
                    "status_code": request_status_code,
                    "data": {}
                }

            app_logger.info(f"PAN {pan_card_number} validated successfully for user {user_id} via Surpass API.")
            return {
                "success": True,
                "message": "PAN card validated successfully",
                "status_code": status.HTTP_200_OK,
                "data": response_data.get("data", {})
            }

        except Exception as e:
            app_logger.error(f"Error validating PAN card for user {user_id}: {str(e)}")
            return {
                "success": False,
                "message": "Error validating PAN card",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }

    async def bank_verifications(self, user_id, bank_detail: BankDetails):
        try:
            app_logger.info(
                f"[bank_verifications] Initiated by user_id={user_id} for account_number={bank_detail.id_number}"
            )

            bank_verification_payload_data = {
                "id_number": bank_detail.id_number,
                "ifsc": bank_detail.ifsc,
                "ifsc_details": True
            }

            bank_account_interface = DBInterface(BankAccount)
            bank_account = bank_account_interface.read_by_fields(fields=[BankAccount.applicant_id == bank_detail.applicant_id, BankAccount.account_number == bank_detail.id_number, BankAccount.ifsc_code == bank_detail.ifsc, BankAccount.is_deleted == False])

            if bank_account:
                return {
                    "success": False,
                    "message": "Bank detail already verified for this loan.",
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "data": {}
                }


            app_logger.debug(f"[bank_verifications] Sending payload to surpass API: {bank_verification_payload_data}")

            response_data, request_status_code, request_error = await self.surpass_request_obj.make_request(
                endpoint="bank-verification/", method="POST", data=bank_verification_payload_data
            )

            app_logger.info(
                f"[bank_verifications] Received response from surpass API: status_code={request_status_code}"
            )

            if request_status_code != 200:
                app_logger.info(f"Error Data => {response_data}")
                error_message = request_error
                if response_data:
                    error_data = response_data.get("data")
                    if error_data and error_data.get("remarks"):
                        error_message = error_data.get("remarks")

                app_logger.warning(f"[bank_verifications] Verification failed: {error_message}")
                return {
                    "success": False,
                    "message": error_message,
                    "status_code": request_status_code,
                    "data": {}
                }

            data = response_data.get("data", {})

            bank_data = {
                "user_id": bank_detail.user_id,
                "applicant_id": bank_detail.applicant_id,
                "account_number": bank_detail.id_number,
                "ifsc_code": bank_detail.ifsc,
                "account_holder_name": data.get("full_name") if data and data.get(
                    "full_name"
                ) else bank_detail.account_holder_name,
                "bank_name": data.get("ifsc_details").get("bank_name") if data and data.get(
                    "ifsc_details"
                ) else bank_detail.bank_name,
                "client_id": data.get("client_id") if data and data.get("client_id") else None,
                "type": "credit",
                "is_verified": True,
                "verified_at": datetime.now(),
                "created_by": user_id,
                "modified_by": user_id,
            }

            app_logger.debug(f"[bank_verifications] Saving verified bank data to DB: {bank_data}")

            bank_account_response = bank_account_interface.create(data=bank_data)

            app_logger.info(f"[bank_verifications] Bank details saved successfully for user_id={user_id}")
            return {
                "success": True,
                "message": "Bank details validated successfully",
                "status_code": status.HTTP_200_OK,
                "data": {
                    "bank_details": bank_account_response
                }
            }

        except Exception as e:
            app_logger.exception(f"[bank_verifications] Exception occurred: {str(e)}")
            return {
                "success": False,
                "message": "Error validating bank details",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }

    async def validate_aadhar_card(self, user_id, aadhar_details: AadharCardDetails):
        try:
            app_logger.info(f"User {user_id} submitted valid PAN format. Initiating Surpass API validation.")

            request_payload = {
                "data": {
                    "signup_flow": True,
                    "redirect_url": aadhar_details.redirect_url,
                    "webhook_url": aadhar_details.webhook_url
                }
            }

            app_logger.debug(f"User {user_id} - Request Payload for Surpass API: {request_payload}")

            response_data, request_status_code, request_error = await self.surpass_request_obj.make_request(
                endpoint="digilocker/initialize",
                method="POST",
                data=request_payload
            )

            app_logger.debug(f"User {user_id} - Surpass API Response Status: {request_status_code}")
            app_logger.debug(f"User {user_id} - Surpass API Response Data: {response_data}")
            if request_error:
                app_logger.error(
                    f"User {user_id} - Surpass API returned an error: {request_error} "
                    f"with status code {request_status_code}"
                )
                return {
                    "success": False,
                    "message": request_error,
                    "status_code": request_status_code,
                    "data": {}
                }

            return {
                "success": True,
                "message": "Verify Aadhar card with this link",
                "status_code": status.HTTP_200_OK,
                "data": response_data.get("data", {})
            }

        except Exception as e:
            import traceback
            app_logger.error(f"Exception occurred while validating Aadhar card for user {user_id}: {str(e)}")
            app_logger.error(f"Traceback:\n{traceback.format_exc()}")
            return {
                "success": False,
                "message": "Error validating Aadhar Card",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }

    async def download_aadhar_data(self, client_id: str, user_id: int):
        try:
            endpoint = f"digilocker/download-aadhaar/{client_id}"
            app_logger.info(f"User {user_id} is downloading Aadhaar using client_id={client_id}")

            response_data, status_code, request_error = await self.surpass_request_obj.make_request(
                endpoint=endpoint,
                method="GET"
            )

            if request_error:
                app_logger.error(f"Aadhaar download failed for client_id={client_id}, error: {request_error}")
                return {
                    "success": False,
                    "message": request_error,
                    "status_code": status_code,
                    "data": {}
                }

            aadhaar_data = response_data.get("data", {})
            app_logger.info(f"Aadhaar data fetched for user_id={user_id}: {aadhaar_data}")

            return {
                "success": True,
                "message": "Aadhaar details fetched successfully",
                "status_code": status.HTTP_200_OK,
                "data": aadhaar_data
            }

        except Exception as e:
            app_logger.error(f"Exception during Aadhaar data download for client_id={client_id}: {str(e)}")
            return {
                "success": False,
                "message": "Error downloading Aadhaar data",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }
