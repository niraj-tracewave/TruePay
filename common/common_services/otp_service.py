import base64
import random
from datetime import datetime, UTC

import pyotp

from app_logging import app_logger


class OTPService:
    @staticmethod
    def generate_secret():
        """Generate a random secret key for TOTP."""
        random_bytes = random.randbytes(10)
        return base64.b32encode(random_bytes).decode("utf-8")

    @classmethod
    def generate_otp(cls, phone: str):
        """Generate and store OTP for a given phone number."""
        secret = cls.generate_secret()
        totp = pyotp.TOTP(secret, interval=60)
        otp = totp.now()

        # print(f"OTP for {phone}: {otp}")
        # print(f"OTP Secret for {phone}: {secret}")

        return otp, secret

    @classmethod
    def verify_otp(cls, otp: str, otp_secret: str):
        """Verify OTP for a given phone number."""

        try:
            totp = pyotp.TOTP(otp_secret, interval=60)
            now = datetime.now(UTC)

            app_logger.info(f"Entered OTP        : {otp}")
            app_logger.info(f"Current OTP (0s)   : {totp.at(int(now.timestamp()))}")
            app_logger.info(f"Previous OTP (-60s): {totp.at(int(now.timestamp() - 60))}")
            app_logger.info(f"Next OTP (+60s)    : {totp.at(int(now.timestamp() + 60))}")
            app_logger.info(f"Current Time (UTC) : {now.isoformat()}")

            # Use valid_window=1 to allow ±1 time window
            if totp.verify(otp, valid_window=1):
                return True, "OTP verified successfully"
            else:
                return False, "Invalid or expired OTP"
        except Exception as e:
            return False, f"Verification failed: {str(e)}"
