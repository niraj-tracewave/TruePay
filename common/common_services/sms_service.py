import requests

from app_logging import app_logger


class SMSService:
    @staticmethod
    def send_sms(phone_number: str, message: str) -> bool:
        try:
            sms_url = (
                f"http://ahd.sendsmsbox.com/api/mt/SendSMS?"
                f"user=tracewave&password=tracewave14&senderid=TRNSWV&channel=Trans&DCS=0&"
                f"flashsms=0&number={phone_number}&text={message}"
                f"&Peid=0&DLTTemplateId=1707173510885060059"
            )
            response = requests.get(sms_url)
            if response.status_code == 200:
                app_logger.info(f"SMS sent to {phone_number}")
                return True
            else:
                app_logger.error(f"SMS failed for {phone_number}. Status: {response.status_code}")
                return False
        except Exception as e:
            app_logger.exception(f"SMS send failed. Error: {str(e)}")
            return False
