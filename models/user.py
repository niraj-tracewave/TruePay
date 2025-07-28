import re

from sqlalchemy import (
    Column, Integer, String, Boolean, Date, Enum, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship

from common.enums import UserRole, DocumentType
from db_domains import CreateUpdateTime
from models.loan import BankAccount


class User(CreateUpdateTime):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True, nullable=True)
    password = Column(String(255), nullable=True)
    phone = Column(String(15), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=True)
    birth_date = Column(Date, nullable=True)
    address = Column(String(500), nullable=True)
    role = Column(Enum(UserRole), default=UserRole.user, nullable=False, index=True)
    is_active = Column(Boolean, default=True, index=True)
    profile_image = Column(String(255), nullable=True)

    documents = relationship(
        "UserDocument",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    bank_accounts = relationship(
        "BankAccount", back_populates="user", cascade="all, delete-orphan", foreign_keys=[BankAccount.user_id]
    )

    def __repr__(self):
        return f"<User id={self.id} phone={self.phone} role={self.role}>"

    @classmethod
    def validate_phone(cls, phone: str) -> bool:
        return bool(re.fullmatch(r"[\d\s\-]+", phone)) and (10 <= sum(c.isdigit() for c in phone) <= 15)

    @classmethod
    def validate_email(cls, email: str) -> bool:
        return bool(re.fullmatch(r"[^@]+@[^@]+\.[^@]+", email)) if email else True


class UserDocument(CreateUpdateTime):
    __tablename__ = "user_documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    document_type = Column(Enum(DocumentType), nullable=False, index=True)
    document_number = Column(String(50), nullable=False, index=True)
    document_file = Column(String(255), nullable=False)
    # status = Column(
    #     Enum(DocumentStatus), default=DocumentStatus.PENDING, server_default=DocumentStatus.PENDING.value,
    #     nullable=False
    # )

    user = relationship("User", back_populates="documents")

    __table_args__ = (
        UniqueConstraint('user_id', 'document_type', name='_user_doc_uc'),
    )

    def __repr__(self):
        return f"<UserDocument id={self.id} user_id={self.user_id} type={self.document_type}>"
