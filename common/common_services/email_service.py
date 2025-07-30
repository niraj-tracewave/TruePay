# import os
# import smtplib
# from email.message import EmailMessage

# from dotenv import load_dotenv 
# load_dotenv()

# SMTP_USER_EMAIL = os.environ.get("SMTP_USER_EMAIL")
# SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")

# def send_email(subject, body, to_email):
#     msg = EmailMessage()
#     msg['Subject'] = subject
#     msg['From'] = SMTP_USER_EMAIL
#     msg['To'] = to_email
#     msg.set_content(body)

#     with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
#         smtp.login(SMTP_USER_EMAIL, SMTP_PASSWORD)
#         smtp.send_message(msg)


import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

# Configure logging
from app_logging import app_logger

# Load environment variables
load_dotenv()

class EmailService:
    def __init__(self):
        self.smtp_user_email = os.environ.get("SMTP_USER_EMAIL")
        self.smtp_password = os.environ.get("SMTP_PASSWORD")
        self.smtp_host = "smtp.gmail.com"
        self.smtp_port = 465

    def send_email(self, subject, body, to_email):
        """
        Sends an email with the given subject and body to the specified recipient.
        Errors are logged and silenced without raising exceptions.
        """
        try:
            # Create email message
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = self.smtp_user_email
            msg['To'] = to_email
            msg.set_content(body)

            # Connect to SMTP server and send email
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port) as smtp:
                smtp.login(self.smtp_user_email, self.smtp_password)
                smtp.send_message(msg)
                app_logger.info(f"Email sent successfully to {to_email}")

        except Exception as e:
            app_logger.error(f"Failed to send email to {to_email}: {str(e)}")
            # Silently handle the error without raising
            pass