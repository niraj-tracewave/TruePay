import re
from sqlalchemy import (
    Column, Integer, String, Text
)
from db_domains import CreateUpdateTime, CreateByUpdateBy


class ContactUs(CreateUpdateTime, CreateByUpdateBy):
    __tablename__ = "contact_us"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False, index=True)
    service = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)

    def __repr__(self):
        return f"<ContactUs id={self.id} first_name={self.first_name} last_name={self.last_name} email={self.email}>"

    @classmethod
    def is_valid_email(cls, email: str) -> bool:
        return bool(re.fullmatch(r"[^@]+@[^@]+\.[^@]+", email)) if email else True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Perform email validation during initialization
        if not self.is_valid_email(self.email):
            raise ValueError(f"Invalid email address: {self.email}")
