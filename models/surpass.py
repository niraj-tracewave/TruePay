from sqlalchemy import (
    Column, JSON, String, Integer, ForeignKey, Date, Enum
)
from sqlalchemy.orm import relationship

from common.enums import GenderEnum
from db_domains import CreateUpdateTime


class UserCibilReport(CreateUpdateTime):
    __tablename__ = "user_cibil_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    client_id = Column(String, nullable=True, index=True)
    name = Column(String, nullable=True, index=True)
    pan_number = Column(String, nullable=True, index=True)
    mobile = Column(String, nullable=True, index=True)
    credit_score = Column(String, nullable=True, index=True)
    credit_report = Column(JSON, nullable=True)

    report_refresh_date = Column(Date, nullable=True, index=True)
    next_eligible_date = Column(Date, nullable=True, index=True)
    gender = Column(Enum(GenderEnum), nullable=False, server_default="male")

    user = relationship("User", backref="cibil_reports")
