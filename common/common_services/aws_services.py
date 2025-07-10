import mimetypes

import aioboto3
from botocore.config import Config

from common.cache_string import gettext
from config import app_config


class AWSClient:
    """Handles AWS authentication and S3 client creation."""

    def __init__(self):
        self.AWS_ACCESS_KEY = app_config.AWS_ACCESS_KEY
        self.AWS_SECRET_KEY = app_config.AWS_SECRET_KEY
        self.AWS_REGION = app_config.AWS_REGION
        self.S3_BUCKET_NAME = app_config.AWS_BUCKET_NAME

    async def get_s3_client(self):
        """Returns an async S3 client session."""
        try:
            session = aioboto3.Session()
            return session.client("s3", aws_access_key_id=self.AWS_ACCESS_KEY,
                                  aws_secret_access_key=self.AWS_SECRET_KEY,
                                  region_name=self.AWS_REGION, config=Config(signature_version='s3v4'))
        except Exception as e:
            print(e)
            return {"success": False, "message": gettext("aws_client_error"), "status_code": 422, "data": []}

    async def upload_to_s3(self, file_name: str, binary_data: bytes, file_type: str) -> dict:
        """Uploads a file to S3 and returns the S3 Object URL."""
        async with await self.get_s3_client() as s3_client:
            if file_type in ["aadhar_card", "pan_card", "income_proof", "self_employed", "salaried", "profile_image", "property_documents"]:
                s3_key = f"{file_type}/{file_name}"
            else:
                raise ValueError("Invalid file type for S3 upload.")

            content_type, _ = mimetypes.guess_type(file_name)
            content_type = content_type or "application/octet-stream"

            await s3_client.put_object(
                Bucket=self.S3_BUCKET_NAME,
                Key=s3_key,
                Body=binary_data,
                ContentType=content_type
            )

            s3_object_url = f"https://{self.S3_BUCKET_NAME}.s3.{self.AWS_REGION}.amazonaws.com/{s3_key}"
            return {"s3_object_url": s3_object_url}
