from sqlalchemy import (Column, Integer, String, Float, Enum, ForeignKey, UniqueConstraint, Index)
from sqlalchemy.orm import relationship

from common.enums import LoanType
from db_domains import CreateUpdateTime, CreateByUpdateBy


class CreditScoreRange(CreateUpdateTime, CreateByUpdateBy):
    __tablename__ = "credit_score_ranges"

    id = Column(Integer, primary_key=True, index=True)
    label = Column(String, nullable=False, unique=True)  # E.g., "750+", "700–749", etc.
    min_score = Column(Integer, nullable=True)
    max_score = Column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint('min_score', 'max_score', name='uq_score_range_min_max'),

        Index('ix_credit_score_range_min', 'min_score'),
        Index('ix_credit_score_range_max', 'max_score'),

    )


class InterestRate(CreateUpdateTime, CreateByUpdateBy):
    __tablename__ = "interest_rates"

    id = Column(Integer, primary_key=True, index=True)
    credit_score_range_id = Column(Integer, ForeignKey("credit_score_ranges.id"))
    rate_percentage = Column(Float, nullable=False)
    loan_type = Column(
        Enum(LoanType), default=LoanType.PERSONAL, server_default=LoanType.PERSONAL.value, nullable=False
    )
    credit_score_range = relationship("CreditScoreRange")
    __table_args__ = (
        Index('ix_interest_score_range', 'credit_score_range_id'),
    )


class ProcessingFee(CreateUpdateTime, CreateByUpdateBy):
    __tablename__ = "processing_fees"

    id = Column(Integer, primary_key=True, index=True)
    rate_percent = Column(Float, nullable=False)
    amount = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint('rate_percent', 'amount', name='uq_processing_fee_rate_amount'),
        Index('ix_processing_fee_rate_percent', 'rate_percent'),
        Index('ix_processing_fee_amount', 'amount'),
    )
