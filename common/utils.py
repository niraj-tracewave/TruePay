from typing import Optional

from app_logging import app_logger
from models.user import User, UserDocument
from passlib.context import CryptContext


def format_user_response(user: User, documents: Optional[list[UserDocument]] = None) -> dict:
    """
        Formats a User SQLAlchemy object along with related documents (PAN, Aadhaar).

        Args:
            user (User): User SQLAlchemy ORM object
            documents (List[UserDocument] | None): List of related document objects, or None

        Returns:
            dict: Formatted user data with document URLs and numbers
    """
    app_logger.info("Formatting user response with S3 URLs for profile image and documents.")

    pan_doc = aadhaar_doc = None

    if documents:
        pan_doc = next((doc for doc in documents if doc.document_type.value == "PAN"), None)
        aadhaar_doc = next((doc for doc in documents if doc.document_type.value == "AADHAR"), None)

    return {
        "id": user.id,
        "name": user.name or "",
        "address": user.address or "",
        "phone_number": user.phone or "",
        "email": user.email or "",
        "role": user.role.value if user.role else "",
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else "",
        "profile_image": user.profile_image or "",

        "pan_number": pan_doc.document_number if pan_doc else "",
        "pan_document": pan_doc.document_file if pan_doc else "",

        "aadhaar_number": aadhaar_doc.document_number if aadhaar_doc else "",
        "aadhaar_document": aadhaar_doc.document_file if aadhaar_doc else "",
    }

class PasswordHashing:
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    # Hash password
    def hash_password(self, password: str) -> str:
        return self.pwd_context.hash(password)

    # Verify password
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return self.pwd_context.verify(plain_password, hashed_password)